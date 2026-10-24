"""
Market Data Manager, Candle Aggregator, Order Book Depth Analyzer, and Liquidity Evaluator.
"""

import time
import math
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from indodax_bot.indodax_api import IndodaxAPIClient
from indodax_bot.config import INDODAX_TAKER_FEE, INDODAX_MAKER_FEE, CONSERVATIVE_SLIPPAGE_DEFAULT

logger = logging.getLogger(__name__)

class MarketDataManager:
    def __init__(self, api_client: IndodaxAPIClient):
        self.api = api_client
        self.pair_info: Dict[str, Dict[str, Any]] = {}
        self.candle_history: Dict[str, Dict[str, pd.DataFrame]] = {} # symbol -> {tf -> df}
        self.orderbook_cache: Dict[str, Dict[str, Any]] = {}
        self.last_ticker_time = 0.0
        self.tickers_cache: Dict[str, Any] = {}

    def refresh_pairs_and_tickers(self) -> Dict[str, Dict[str, Any]]:
        """Fetch pairs info and latest tickers for all active IDR markets."""
        try:
            pairs = self.api.get_pairs()
            ticker_data = self.api.get_ticker_all()
            tickers = ticker_data.get("tickers", {})
            self.tickers_cache = tickers

            active_markets = {}
            for p in pairs:
                p_id = p.get("id")  # e.g. 'btcidr'
                ticker_id = p.get("ticker_id", p_id)
                base_curr = p.get("base_currency", "").lower()

                # Check eligibility: must be IDR spot, active, non-maintenance, non-suspended
                if base_curr != "idr":
                    continue
                if p.get("is_maintenance", 0) == 1 or p.get("is_market_suspended", 0) == 1:
                    continue

                t_info = tickers.get(ticker_id, {})
                if not t_info:
                    continue

                last_price = float(t_info.get("last", 0) or 0)
                buy_bid = float(t_info.get("buy", 0) or 0)
                sell_ask = float(t_info.get("sell", 0) or 0)
                vol_24h_idr = float(t_info.get("vol_idr", 0) or 0)
                high_24h = float(t_info.get("high", 0) or 0)
                low_24h = float(t_info.get("low", 0) or 0)

                if last_price <= 0 or buy_bid <= 0 or sell_ask <= 0:
                    continue

                active_markets[p_id] = {
                    "pair_id": p_id,
                    "symbol": p.get("symbol", p_id.upper()),
                    "traded_currency": p.get("traded_currency", "").upper(),
                    "base_currency": "IDR",
                    "trade_min_base_currency": float(p.get("trade_min_base_currency", 10000)),
                    "trade_fee_percent_taker": float(p.get("trade_fee_percent_taker", 0.2)) / 100.0,
                    "trade_fee_percent_maker": float(p.get("trade_fee_percent_maker", 0.1)) / 100.0,
                    "volume_precision": p.get("volume_precision", 0),
                    "price_round": p.get("price_round", 0),
                    "last_price": last_price,
                    "bid": buy_bid,
                    "ask": sell_ask,
                    "high_24h": high_24h,
                    "low_24h": low_24h,
                    "vol_24h_idr": vol_24h_idr,
                    "spread_pct": ((sell_ask - buy_bid) / buy_bid) if buy_bid > 0 else 0.0
                }

                self.pair_info[p_id] = active_markets[p_id]

            return active_markets
        except Exception as e:
            logger.error(f"Failed to refresh pairs and tickers: {e}")
            return self.pair_info

    def get_orderbook_depth(self, pair_id: str) -> Optional[Dict[str, Any]]:
        """Fetch and cache order book depth with fast timeout and fallback."""
        try:
            depth = self.api.get_depth(pair_id, timeout=3.0)
            if depth and ("buy" in depth or "sell" in depth):
                self.orderbook_cache[pair_id] = depth
                return depth
        except Exception as e:
            logger.debug(f"Orderbook depth fetch fast fallback for {pair_id}: {e}")
        return self.orderbook_cache.get(pair_id)

    def analyze_executable_liquidity(
        self,
        pair_id: str,
        order_size_idr: float,
        is_buy: bool
    ) -> Dict[str, Any]:
        """
        Walk order book to estimate executable price, slippage, and market impact for order_size_idr.
        Section 8: Evaluate executable order-book depth rather than displayed volume alone.
        """
        pair = self.pair_info.get(pair_id)
        if not pair:
            return {"executable": False, "reason": "Pair info unavailable"}

        depth = self.get_orderbook_depth(pair_id)
        if not depth:
            # Fallback to ticker spread estimate
            fallback_price = pair["ask"] if is_buy else pair["bid"]
            return {
                "executable": True,
                "avg_price": fallback_price,
                "slippage_pct": CONSERVATIVE_SLIPPAGE_DEFAULT,
                "market_impact_pct": CONSERVATIVE_SLIPPAGE_DEFAULT,
                "total_available_idr": order_size_idr * 10,
                "is_fallback": True
            }

        orders = depth.get("sell" if is_buy else "buy", [])
        if not orders:
            return {"executable": False, "reason": "Order book side is empty"}

        accumulated_idr = 0.0
        accumulated_base = 0.0
        reference_price = float(orders[0][0])  # top of book price

        for item in orders:
            price = float(item[0])
            amount = float(item[1])  # traded currency amount
            item_idr = price * amount

            needed_idr = order_size_idr - accumulated_idr
            if needed_idr <= item_idr:
                take_base = needed_idr / price
                accumulated_idr += needed_idr
                accumulated_base += take_base
                break
            else:
                accumulated_idr += item_idr
                accumulated_base += amount

        if accumulated_idr < order_size_idr * 0.99 and accumulated_idr < pair["trade_min_base_currency"]:
            return {
                "executable": False,
                "reason": f"Insufficient orderbook depth. Available: Rp{accumulated_idr:,.0f}, Needed: Rp{order_size_idr:,.0f}",
                "total_available_idr": accumulated_idr
            }

        avg_price = accumulated_idr / accumulated_base if accumulated_base > 0 else reference_price

        # Slippage: percentage difference between weighted average execution price and top-of-book price
        if is_buy:
            slippage_pct = max(0.0, (avg_price - reference_price) / reference_price)
        else:
            slippage_pct = max(0.0, (reference_price - avg_price) / reference_price)

        return {
            "executable": True,
            "avg_price": avg_price,
            "slippage_pct": slippage_pct,
            "market_impact_pct": slippage_pct,
            "total_available_idr": accumulated_idr,
            "is_fallback": False
        }

    def update_candles(self, pair_id: str, df_candles: pd.DataFrame, timeframe: str):
        """Store candles DataFrame (columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume'])."""
        if pair_id not in self.candle_history:
            self.candle_history[pair_id] = {}
        self.candle_history[pair_id][timeframe] = df_candles

    def get_candles(self, pair_id: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Get candle history DataFrame for a pair and timeframe."""
        return self.candle_history.get(pair_id, {}).get(timeframe)
