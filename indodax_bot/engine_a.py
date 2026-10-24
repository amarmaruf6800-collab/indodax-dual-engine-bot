"""
Engine A — Pure Scalping Strategy
Fast momentum scalping on 1m, 5m, 15m timeframes.
"""

import logging
import pandas as pd
from typing import Dict, Any, List, Optional
from indodax_bot.indicators import TechnicalIndicators

logger = logging.getLogger(__name__)

class ScalpingEngineA:
    def __init__(self):
        self.engine_name = "ENGINE_A_SCALPER"

    def evaluate_entry(
        self,
        pair_id: str,
        df_1m: Optional[pd.DataFrame],
        df_5m: Optional[pd.DataFrame],
        df_15m: Optional[pd.DataFrame],
        market_info: Dict[str, Any],
        execution_info: Dict[str, Any],
        has_open_position: bool
    ) -> Dict[str, Any]:
        """
        Evaluates Pure Scalping entry conditions on short timeframes.
        Returns signal dict with 'valid', 'reason', 'expected_net_return_pct', 'stop_loss_pct', 'take_profit_pct'.
        """
        if has_open_position:
            return {"valid": False, "reason": f"Open position already exists in {pair_id}"}

        df = df_5m if df_5m is not None and len(df_5m) >= 25 else df_15m
        if df is None or len(df) < 25:
            return {"valid": False, "reason": "Insufficient candle data for Engine A"}

        df = df.copy()
        df['ema9'] = TechnicalIndicators.compute_ema(df['close'], 9)
        df['ema21'] = TechnicalIndicators.compute_ema(df['close'], 21)
        df['atr'] = TechnicalIndicators.compute_atr(df, 14)
        df['rvol'] = TechnicalIndicators.compute_rvol(df, 20)
        df['roc'] = TechnicalIndicators.compute_roc(df['close'], 6)

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        price = float(latest['close'])
        atr = float(latest['atr'])

        if price <= 0 or atr <= 0:
            return {"valid": False, "reason": "Invalid price or ATR"}

        # 1. Indicator Filters
        ema_bullish = latest['ema9'] > latest['ema21']
        rvol_ok = float(latest['rvol']) >= 1.2
        roc_ok = float(latest['roc']) >= 0.3

        # Candlestick Momentum: Green candle with body > 50% of range
        candle_range = max(1e-8, float(latest['high'] - latest['low']))
        candle_body = float(latest['close'] - latest['open'])
        body_ratio = candle_body / candle_range
        candle_ok = candle_body > 0 and body_ratio >= 0.4

        if not (ema_bullish and rvol_ok and roc_ok and candle_ok):
            reasons = []
            if not ema_bullish: reasons.append("EMA9 <= EMA21")
            if not rvol_ok: reasons.append(f"RVOL {latest['rvol']:.2f} < 1.2")
            if not roc_ok: reasons.append(f"ROC {latest['roc']:.2f}% < 0.3%")
            if not candle_ok: reasons.append("Weak candle momentum")
            return {"valid": False, "reason": ", ".join(reasons)}

        # 2. Execution & Costs
        spread_pct = market_info.get("spread_pct", 0.005)
        slippage_pct = execution_info.get("slippage_pct", 0.0015)
        taker_fee = market_info.get("trade_fee_percent_taker", 0.002)
        maker_fee = market_info.get("trade_fee_percent_maker", 0.001)

        total_cost_pct = spread_pct + taker_fee + maker_fee + slippage_pct

        # Expected target move based on ATR
        atr_pct = (atr / price)
        expected_target_pct = max(0.015, atr_pct * 2.0)
        expected_net_return_pct = expected_target_pct - total_cost_pct

        if expected_net_return_pct <= 0.002: # Requires net profit > 0.2% after all costs
            return {
                "valid": False,
                "reason": f"Expected net return {expected_net_return_pct*100:.2f}% insufficient vs total cost {total_cost_pct*100:.2f}%"
            }

        # Stop loss and take profit distances
        stop_loss_distance_pct = max(0.01, atr_pct * 1.5 + total_cost_pct)
        take_profit_distance_pct = expected_target_pct

        return {
            "valid": True,
            "engine": self.engine_name,
            "pair_id": pair_id,
            "symbol": market_info.get("symbol", pair_id.upper()),
            "entry_price": price,
            "atr": atr,
            "rvol": float(latest['rvol']),
            "roc_pct": float(latest['roc']),
            "spread_pct": spread_pct,
            "total_cost_pct": total_cost_pct,
            "expected_net_return_pct": expected_net_return_pct,
            "stop_loss_pct": stop_loss_distance_pct,
            "take_profit_pct": take_profit_distance_pct,
            "signal_reason": f"Scalp breakout: EMA9>EMA21, RVOL={latest['rvol']:.1f}, ROC={latest['roc']:.1f}%"
        }

    def evaluate_exit(
        self,
        position: Dict[str, Any],
        latest_candle: pd.Series,
        market_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluates Scalping exit rules:
        - Take profit hit
        - Stop loss hit
        - Trailing stop hit
        - Momentum reversal (EMA9 crossing below EMA21)
        """
        entry_price = position["entry_price"]
        current_price = float(latest_candle['close'])
        highest_price = position.get("highest_price", entry_price)
        highest_price = max(highest_price, current_price, float(latest_candle['high']))
        position["highest_price"] = highest_price

        pnl_pct = (current_price - entry_price) / entry_price
        stop_loss_price = position["stop_loss_price"]
        take_profit_price = position["take_profit_price"]

        # Trailing stop update
        atr = position.get("atr", entry_price * 0.01)
        if current_price >= entry_price + atr * 1.0:
            trailing_stop = highest_price - atr * 1.2
            if trailing_stop > stop_loss_price:
                position["stop_loss_price"] = trailing_stop
                stop_loss_price = trailing_stop

        # 1. Stop Loss
        if current_price <= stop_loss_price or float(latest_candle['low']) <= stop_loss_price:
            return {"exit": True, "reason": "STOP_LOSS_HIT", "price": stop_loss_price}

        # 2. Take Profit
        if current_price >= take_profit_price or float(latest_candle['high']) >= take_profit_price:
            return {"exit": True, "reason": "TAKE_PROFIT_HIT", "price": take_profit_price}

        # 3. Reversal Signal (EMA 9 < EMA 21)
        ema9 = latest_candle.get("ema9")
        ema21 = latest_candle.get("ema21")
        if ema9 and ema21 and ema9 < ema21 and pnl_pct > 0.003:
            return {"exit": True, "reason": "MOMENTUM_REVERSAL", "price": current_price}

        return {"exit": False, "reason": None}
