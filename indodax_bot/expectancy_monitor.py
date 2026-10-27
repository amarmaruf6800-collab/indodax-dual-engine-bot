"""
Expectancy Monitor & Performance Analytics for V6.1-MACO R11.
Calculates Net Expectancy, Win Rate, Profit Factor, Max Drawdown, and Engine Comparison.
"""

import math
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class ExpectancyMonitor:
    """
    Section 10: Expectancy Monitor & Performance Validation.
    """
    @classmethod
    def calculate_analytics(
        cls,
        closed_trades: List[Dict[str, Any]],
        equity_curve: List[float],
        initial_equity: float
    ) -> Dict[str, Any]:
        if not closed_trades:
            return {
                "total_trades": 0,
                "win_rate_pct": 0.0,
                "average_net_win_idr": 0.0,
                "average_net_loss_idr": 0.0,
                "net_expectancy_idr": 0.0,
                "profit_factor": 0.0,
                "max_drawdown_pct": 0.0,
                "total_fees_idr": 0.0,
                "total_slippage_idr": 0.0,
                "engine_a_trades": 0,
                "engine_b_trades": 0
            }

        wins = [t for t in closed_trades if t.get("realized_pnl_idr", 0.0) > 0]
        losses = [t for t in closed_trades if t.get("realized_pnl_idr", 0.0) <= 0]

        total_trades = len(closed_trades)
        win_rate = len(wins) / total_trades if total_trades > 0 else 0.0
        loss_rate = 1.0 - win_rate

        total_gross_win = sum(t.get("realized_pnl_idr", 0.0) for t in wins)
        total_gross_loss = abs(sum(t.get("realized_pnl_idr", 0.0) for t in losses))

        avg_net_win = (total_gross_win / len(wins)) if wins else 0.0
        avg_net_loss = (total_gross_loss / len(losses)) if losses else 0.0

        # EXPECTANCY = (WIN_RATE * AVG_NET_WIN) - (LOSS_RATE * AVG_NET_LOSS)
        net_expectancy_idr = (win_rate * avg_net_win) - (loss_rate * avg_net_loss)

        profit_factor = (total_gross_win / total_gross_loss) if total_gross_loss > 0 else (total_gross_win if total_gross_win > 0 else 0.0)

        # Drawdown calculation
        max_dd_pct = 0.0
        if equity_curve:
            eq_series = pd.Series(equity_curve)
            rolling_max = eq_series.cummax()
            dd_series = (eq_series - rolling_max) / rolling_max
            max_dd_pct = abs(float(dd_series.min())) * 100.0

        total_fees = sum(t.get("entry_fee_idr", 0.0) + t.get("exit_fee_idr", 0.0) for t in closed_trades)
        total_slippage = sum(t.get("slippage_cost_idr", 0.0) for t in closed_trades)

        engine_a_trades = len([t for t in closed_trades if t.get("engine") == "ENGINE_A_SCALPER"])
        engine_b_trades = len([t for t in closed_trades if t.get("engine") == "ENGINE_B_MOMENTUM_HUNTER"])

        return {
            "total_trades": total_trades,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate_pct": round(win_rate * 100.0, 2),
            "average_net_win_idr": round(avg_net_win, 2),
            "average_net_loss_idr": round(avg_net_loss, 2),
            "net_expectancy_idr": round(net_expectancy_idr, 2),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown_pct": round(max_dd_pct, 2),
            "total_fees_idr": round(total_fees, 2),
            "total_slippage_idr": round(total_slippage, 2),
            "engine_a_trades": engine_a_trades,
            "engine_b_trades": engine_b_trades
        }
