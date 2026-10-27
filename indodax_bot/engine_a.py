"""
Engine A — Cost-Aware Adaptive Scalper for V6.1-MACO R11
Implements Liquidity Gate, Net Profitability Gate, False Breakout Filter, and Structure-Based Stop Loss.
"""

import logging
import pandas as pd
from typing import Dict, Any, List, Optional
from indodax_bot.indicators import TechnicalIndicators, FalseBreakoutFilter, MarketRegimeDetector
from indodax_bot.config import SCALPER_SPREAD_BASELINE_MAX, EXPECTED_NET_REWARD_RISK_RATIO_MIN

logger = logging.getLogger(__name__)

class ScalpingEngineA:
    def __init__(self):
        self.engine_name = "ENGINE_A_SCALPER"
        self.consecutive_losses = 0
        self.asset_cooldowns: Dict[str, float] = {}

    def record_trade_result(self, is_win: bool, pair_id: str, timestamp: float):
        """Track trade outcome for anti-overtrading cooldowns."""
        if is_win:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            # 1 hour cooldown on asset after SL
            self.asset_cooldowns[pair_id] = timestamp + 3600.0

    def evaluate_entry(
        self,
        pair_id: str,
        df_1m: Optional[pd.DataFrame],
        df_5m: Optional[pd.DataFrame],
        df_15m: Optional[pd.DataFrame],
        market_info: Dict[str, Any],
        execution_info: Dict[str, Any],
        has_open_position: bool,
        current_timestamp: float = 0.0
    ) -> Dict[str, Any]:
        """
        Section 4: Evaluates Cost-Aware Adaptive Scalper entry conditions.
        """
        if has_open_position:
            return {"valid": False, "reason": f"Open position already exists in {pair_id}"}

        # Check consecutive loss halt
        if self.consecutive_losses >= 2:
            return {"valid": False, "reason": f"Engine A halted: {self.consecutive_losses} consecutive losses. Awaiting market regime re-evaluation."}

        # Check asset cooldown
        if pair_id in self.asset_cooldowns and current_timestamp < self.asset_cooldowns[pair_id]:
            return {"valid": False, "reason": f"Asset {pair_id} is in post-loss cooldown"}

        df = df_5m if df_5m is not None and len(df_5m) >= 25 else df_15m
        if df is None or len(df) < 25:
            return {"valid": False, "reason": "Insufficient candle data for Engine A"}

        spread_pct = market_info.get("spread_pct", 0.005)
        slippage_pct = execution_info.get("slippage_pct", 0.0015)
        taker_fee = market_info.get("trade_fee_percent_taker", 0.002)
        maker_fee = market_info.get("trade_fee_percent_maker", 0.001)

        # 1. Section 4.C: Liquidity Gate
        if spread_pct > SCALPER_SPREAD_BASELINE_MAX * 1.5:  # Spread > 0.45%
            return {
                "valid": False,
                "reason": f"Liquidity Gate Rejected: Spread ({spread_pct*100:.2f}%) exceeds baseline filter ({SCALPER_SPREAD_BASELINE_MAX*100:.2f}%)"
            }

        total_cost_pct = spread_pct + taker_fee + maker_fee + slippage_pct

        # 2. Section 4.F: False Breakout Filter
        fb_eval = FalseBreakoutFilter.evaluate_breakout(df, spread_pct, slippage_pct)
        if not fb_eval["is_valid"]:
            return {"valid": False, "reason": f"False Breakout Filter Rejected: {fb_eval['reason']}"}

        # 3. Technical Indicator Confirmation
        df = df.copy()
        df['ema9'] = TechnicalIndicators.compute_ema(df['close'], 9)
        df['ema21'] = TechnicalIndicators.compute_ema(df['close'], 21)
        df['atr'] = TechnicalIndicators.compute_atr(df, 14)
        df['rvol'] = TechnicalIndicators.compute_rvol(df, 20)
        df['roc'] = TechnicalIndicators.compute_roc(df['close'], 6)

        latest = df.iloc[-1]
        price = float(latest['close'])
        atr = float(latest['atr'])

        if price <= 0 or atr <= 0:
            return {"valid": False, "reason": "Invalid price or ATR"}

        ema_bullish = latest['ema9'] > latest['ema21']
        rvol_ok = float(latest['rvol']) >= 1.2
        roc_ok = float(latest['roc']) >= 0.3

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

        # 4. Section 4.G: Structure-Based Stop Loss
        swing_low_5 = float(df['low'].iloc[-5:].min())
        stop_loss_distance_pct = max(
            (price - swing_low_5) / price,
            (atr * 1.5 / price) + total_cost_pct
        )

        # 5. Section 4.B & 4.D: Dynamic Target & Net Profitability Gate
        # Dynamic gross target around 1.5% - 3.0%
        atr_pct = atr / price
        expected_target_gross_pct = max(0.015, min(0.030, atr_pct * 2.2))
        expected_net_reward_pct = expected_target_gross_pct - total_cost_pct

        if expected_net_reward_pct <= 0.002:
            return {
                "valid": False,
                "reason": f"Net Profitability Gate Rejected: Expected net reward {expected_net_reward_pct*100:.2f}% <= 0.20% minimum"
            }

        # Reward to Risk Ratio check (Expected Net Reward / Expected Net Risk >= 1:2)
        reward_risk_ratio = expected_net_reward_pct / max(1e-4, stop_loss_distance_pct)
        if reward_risk_ratio < (1.0 / EXPECTED_NET_REWARD_RISK_RATIO_MIN): # Reward/Risk < 0.5
            return {
                "valid": False,
                "reason": f"Net Profitability Gate Rejected: Expected Net Reward/Risk Ratio ({reward_risk_ratio:.2f}) < 1:2 threshold"
            }

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
            "expected_net_return_pct": expected_net_reward_pct,
            "stop_loss_pct": stop_loss_distance_pct,
            "take_profit_pct": expected_target_gross_pct,
            "signal_reason": f"Scalp breakout: EMA9>EMA21, RVOL={latest['rvol']:.1f}, Reward/Risk={reward_risk_ratio:.2f}"
        }

    def evaluate_exit(
        self,
        position: Dict[str, Any],
        latest_candle: pd.Series,
        market_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluates Scalping exit rules with dynamic trailing stop and momentum reversal.
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

        # 3. Momentum Reversal
        ema9 = latest_candle.get("ema9")
        ema21 = latest_candle.get("ema21")
        if ema9 and ema21 and ema9 < ema21 and pnl_pct > 0.003:
            return {"exit": True, "reason": "MOMENTUM_REVERSAL", "price": current_price}

        return {"exit": False, "reason": None}
