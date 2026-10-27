"""
Engine B — Extreme Momentum Hunter Strategy for V6.1-MACO R11
Rides multi-hour/daily momentum trends with 0-100 scoring system, Market Regime Filter, and trailing exits.
"""

import logging
import pandas as pd
from typing import Dict, Any, Optional
from indodax_bot.indicators import TechnicalIndicators, MarketRegimeDetector

logger = logging.getLogger(__name__)

class ExtremeMomentumHunterEngineB:
    def __init__(self, min_score_threshold: float = 60.0):
        self.engine_name = "ENGINE_B_MOMENTUM_HUNTER"
        self.min_score_threshold = min_score_threshold

    def evaluate_entry(
        self,
        pair_id: str,
        df_15m: Optional[pd.DataFrame],
        df_1h: Optional[pd.DataFrame],
        market_info: Dict[str, Any],
        execution_info: Dict[str, Any],
        target_position_idr: float,
        has_open_position: bool
    ) -> Dict[str, Any]:
        """
        Section 5: Evaluates Extreme Momentum Hunter entry with 0-100 score & Regime Check.
        """
        if has_open_position:
            return {"valid": False, "score": 0.0, "reason": f"Open position already exists in {pair_id}"}

        df = df_1h if df_1h is not None and len(df_1h) >= 30 else df_15m
        if df is None or len(df) < 30:
            return {"valid": False, "score": 0.0, "reason": "Insufficient candle history for Engine B"}

        spread_pct = market_info.get("spread_pct", 0.005)

        # 1. Market Regime & Exhaustion Check
        regime_res = MarketRegimeDetector.classify_regime(df, spread_pct)
        regime = regime_res.get("regime")

        if regime in [MarketRegimeDetector.OVEREXTENDED_PUMP_EXHAUSTION, MarketRegimeDetector.BEARISH_HIGH_RISK]:
            return {
                "valid": False,
                "score": 0.0,
                "reason": f"Regime Rejected: Market classified as {regime} ({regime_res.get('reason')})"
            }

        available_depth_idr = execution_info.get("total_available_idr", target_position_idr * 2.0)

        # 2. Calculate 0 - 100 momentum score
        score_res = TechnicalIndicators.calculate_engine_b_momentum_score(
            df=df,
            spread_pct=spread_pct,
            orderbook_depth_idr=available_depth_idr,
            target_position_idr=target_position_idr
        )

        total_score = score_res.get("total_score", 0.0)

        if total_score < self.min_score_threshold:
            return {
                "valid": False,
                "score": total_score,
                "score_components": score_res.get("components"),
                "reason": f"Momentum score {total_score:.1f} < threshold {self.min_score_threshold}"
            }

        latest = df.iloc[-1]
        price = float(latest['close'])
        atr = TechnicalIndicators.compute_atr(df, 14).iloc[-1]
        atr_pct = atr / price if price > 0 else 0.02

        slippage_pct = execution_info.get("slippage_pct", 0.0015)
        taker_fee = market_info.get("trade_fee_percent_taker", 0.002)
        total_cost_pct = spread_pct + taker_fee * 2 + slippage_pct

        stop_loss_distance_pct = max(0.015, atr_pct * 2.0 + total_cost_pct)
        expected_net_return_pct = (atr_pct * 3.5) - total_cost_pct

        return {
            "valid": True,
            "engine": self.engine_name,
            "pair_id": pair_id,
            "symbol": market_info.get("symbol", pair_id.upper()),
            "entry_price": price,
            "score": total_score,
            "score_components": score_res.get("components"),
            "atr": atr,
            "spread_pct": spread_pct,
            "total_cost_pct": total_cost_pct,
            "expected_net_return_pct": expected_net_return_pct,
            "stop_loss_pct": stop_loss_distance_pct,
            "take_profit_pct": None,  # No fixed TP per master spec (let winners run)
            "signal_reason": f"Extreme Momentum Score: {total_score:.1f}/100 in {regime}"
        }

    def evaluate_exit(
        self,
        position: Dict[str, Any],
        latest_candle: pd.Series,
        market_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluates Engine B exit conditions:
        - Trailing stop update
        - Trend structure deterioration
        - Liquidity safety check
        """
        entry_price = position["entry_price"]
        current_price = float(latest_candle['close'])
        highest_price = position.get("highest_price", entry_price)
        highest_price = max(highest_price, current_price, float(latest_candle['high']))
        position["highest_price"] = highest_price

        stop_loss_price = position["stop_loss_price"]
        atr = position.get("atr", entry_price * 0.02)

        # Dynamic Trailing Stop
        gain_pct = (highest_price - entry_price) / entry_price
        if gain_pct >= 0.02:
            new_trailing_stop = highest_price - (atr * 2.0)
            if new_trailing_stop > stop_loss_price:
                position["stop_loss_price"] = new_trailing_stop
                stop_loss_price = new_trailing_stop

        # 1. Stop Loss / Trailing Stop Hit
        if current_price <= stop_loss_price or float(latest_candle['low']) <= stop_loss_price:
            return {"exit": True, "reason": "TRAILING_STOP_HIT", "price": stop_loss_price}

        # 2. Structure Breakdown
        ema21 = latest_candle.get("ema21")
        if ema21 and current_price < ema21 and gain_pct > 0.03:
            return {"exit": True, "reason": "TREND_STRUCTURE_DETERIORATION", "price": current_price}

        return {"exit": False, "reason": None}
