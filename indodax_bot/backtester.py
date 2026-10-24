"""
Backtesting Framework, Stress Tester, and Performance Metrics Calculator.
Simulates Engine A & Engine B over historical price & orderbook datasets with realistic fees and slippage.
"""

import time
import math
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional
from indodax_bot.engine_a import ScalpingEngineA
from indodax_bot.engine_b import ExtremeMomentumHunterEngineB
from indodax_bot.risk_controller import PortfolioRiskController
from indodax_bot.portfolio import PortfolioManager
from indodax_bot.config import INDODAX_TAKER_FEE, INDODAX_MAKER_FEE, CONSERVATIVE_SLIPPAGE_DEFAULT

logger = logging.getLogger(__name__)

class Backtester:
    def __init__(self, initial_equity: float = 10_000_000.0):
        self.initial_equity = initial_equity
        self.engine_a = ScalpingEngineA()
        self.engine_b = ExtremeMomentumHunterEngineB()
        self.risk_controller = PortfolioRiskController()

    def run_backtest(
        self,
        candle_data_dict: Dict[str, pd.DataFrame],  # symbol -> df with datetime, open, high, low, close, volume
        timeframe: str = "15m"
    ) -> Dict[str, Any]:
        """
        Runs full historical backtest across supplied asset candle DataFrames.
        """
        cash = self.initial_equity
        start_of_day_equity = cash
        equity_curve = [cash]
        open_positions: List[Dict[str, Any]] = []
        closed_trades: List[Dict[str, Any]] = []
        rejected_trades: List[Dict[str, Any]] = []

        # Find common index length
        if not candle_data_dict:
            return {"error": "No candle data supplied for backtest"}

        # Get maximum index length
        max_bars = max(len(df) for df in candle_data_dict.values())
        min_required_bars = 30

        logger.info(f"Starting Backtest on {len(candle_data_dict)} assets across {max_bars} bars...")

        for i in range(min_required_bars, max_bars):
            # Calculate current prices and total equity
            current_prices = {}
            for sym, df in candle_data_dict.items():
                if i < len(df):
                    current_prices[sym] = float(df['close'].iloc[i])

            # Update position values and peak tracking
            pos_val = 0.0
            for pos in open_positions[:]:
                sym = pos["pair_id"]
                if sym in current_prices:
                    price = current_prices[sym]
                    high_price = float(candle_data_dict[sym]['high'].iloc[i])
                    low_price = float(candle_data_dict[sym]['low'].iloc[i])

                    pos["highest_price"] = max(pos.get("highest_price", price), high_price)

                    # Simulated bar for exit evaluation
                    sim_candle = pd.Series({
                        'open': float(candle_data_dict[sym]['open'].iloc[i]),
                        'high': high_price,
                        'low': low_price,
                        'close': price,
                        'ema9': price,
                        'ema21': price * 0.99
                    })

                    mkt_info = {"trade_fee_percent_maker": INDODAX_MAKER_FEE}

                    # Check exit logic
                    exit_res = None
                    if pos["engine"] == "ENGINE_A_SCALPER":
                        exit_res = self.engine_a.evaluate_exit(pos, sim_candle, mkt_info)
                    else:
                        exit_res = self.engine_b.evaluate_exit(pos, sim_candle, mkt_info)

                    if exit_res and exit_res["exit"]:
                        exit_price = exit_res["price"]
                        gross_proceeds = pos["units"] * exit_price
                        exit_fee = gross_proceeds * INDODAX_MAKER_FEE
                        net_proceeds = gross_proceeds - exit_fee
                        realized_pnl = net_proceeds - pos["position_size_idr"]

                        cash += net_proceeds
                        closed_trades.append({
                            **pos,
                            "exit_price": exit_price,
                            "exit_reason": exit_res["reason"],
                            "realized_pnl_idr": realized_pnl,
                            "realized_pnl_pct": realized_pnl / pos["position_size_idr"]
                        })
                        open_positions.remove(pos)

            # Recalculate total current equity
            current_pos_val = sum(pos["units"] * current_prices.get(pos["pair_id"], pos["entry_price"]) for pos in open_positions)
            current_equity = cash + current_pos_val
            equity_curve.append(current_equity)

            # Check new entries for each asset
            for sym, df in candle_data_dict.items():
                if i >= len(df):
                    continue

                sub_df = df.iloc[:i+1]
                latest_price = float(sub_df['close'].iloc[-1])
                spread_pct = 0.003
                slippage_pct = CONSERVATIVE_SLIPPAGE_DEFAULT

                market_info = {
                    "symbol": sym,
                    "spread_pct": spread_pct,
                    "trade_fee_percent_taker": INDODAX_TAKER_FEE,
                    "trade_fee_percent_maker": INDODAX_MAKER_FEE,
                    "trade_min_base_currency": 10000.0
                }

                execution_info = {
                    "slippage_pct": slippage_pct,
                    "total_available_idr": current_equity * 0.5
                }

                has_open_pos = any(p["pair_id"] == sym for p in open_positions)

                # Evaluate Engine A
                sig_a = self.engine_a.evaluate_entry(
                    pair_id=sym,
                    df_1m=None,
                    df_5m=sub_df if timeframe == "5m" else None,
                    df_15m=sub_df if timeframe in ["15m", "1h"] else None,
                    market_info=market_info,
                    execution_info=execution_info,
                    has_open_position=has_open_pos
                )

                # Evaluate Engine B
                sig_b = self.engine_b.evaluate_entry(
                    pair_id=sym,
                    df_15m=sub_df if timeframe == "15m" else None,
                    df_1h=sub_df if timeframe in ["1h", "1d"] else sub_df,
                    market_info=market_info,
                    execution_info=execution_info,
                    target_position_idr=current_equity * 0.10,
                    has_open_position=has_open_pos
                )

                chosen_sig = None
                if sig_a.get("valid") and sig_b.get("valid"):
                    # Choose signal with higher expected net return
                    chosen_sig = sig_a if sig_a["expected_net_return_pct"] >= sig_b["expected_net_return_pct"] else sig_b
                elif sig_a.get("valid"):
                    chosen_sig = sig_a
                elif sig_b.get("valid"):
                    chosen_sig = sig_b

                if chosen_sig:
                    reserve_eval = self.risk_controller.evaluate_active_reserve_deployment(
                        candidate_signal=chosen_sig,
                        current_equity=current_equity,
                        available_cash=cash,
                        open_positions=open_positions,
                        start_of_day_equity=start_of_day_equity,
                        market_info=market_info,
                        execution_info=execution_info
                    )

                    if reserve_eval.get("approved"):
                        pos_size = reserve_eval["position_size_idr"]
                        entry_fee = pos_size * INDODAX_TAKER_FEE
                        net_invest = pos_size - entry_fee
                        units = net_invest / latest_price

                        cash -= pos_size

                        stop_loss_pct = chosen_sig.get("stop_loss_pct", 0.02)
                        stop_loss_price = latest_price * (1.0 - stop_loss_pct)
                        take_profit_pct = chosen_sig.get("take_profit_pct")
                        take_profit_price = latest_price * (1.0 + take_profit_pct) if take_profit_pct else float('inf')

                        pos_record = {
                            "position_id": f"BACKTEST_POS_{len(closed_trades)+len(open_positions)}",
                            "pair_id": sym,
                            "engine": chosen_sig["engine"],
                            "entry_price": latest_price,
                            "units": units,
                            "position_size_idr": pos_size,
                            "planned_risk_idr": reserve_eval["planned_risk_idr"],
                            "stop_loss_price": stop_loss_price,
                            "take_profit_price": take_profit_price,
                            "highest_price": latest_price,
                            "atr": chosen_sig.get("atr", latest_price * 0.01)
                        }
                        open_positions.append(pos_record)
                    else:
                        rejected_trades.append({"symbol": sym, "reason": reserve_eval.get("reason")})

        # Calculate backtest performance metrics
        final_equity = equity_curve[-1]
        net_profit_idr = final_equity - self.initial_equity
        net_profit_pct = (net_profit_idr / self.initial_equity) * 100.0

        # Drawdown calculation
        eq_series = pd.Series(equity_curve)
        rolling_max = eq_series.cummax()
        drawdown_series = (eq_series - rolling_max) / rolling_max
        max_drawdown_pct = abs(float(drawdown_series.min())) * 100.0

        wins = [t for t in closed_trades if t["realized_pnl_idr"] > 0]
        losses = [t for t in closed_trades if t["realized_pnl_idr"] <= 0]

        win_rate = (len(wins) / len(closed_trades) * 100.0) if closed_trades else 0.0
        total_gross_profit = sum(t["realized_pnl_idr"] for t in wins)
        total_gross_loss = abs(sum(t["realized_pnl_idr"] for t in losses))
        profit_factor = (total_gross_profit / total_gross_loss) if total_gross_loss > 0 else (total_gross_profit if total_gross_profit > 0 else 0.0)

        avg_win = (total_gross_profit / len(wins)) if wins else 0.0
        avg_loss = (total_gross_loss / len(losses)) if losses else 0.0
        expectancy = (avg_win * (win_rate / 100.0)) - (avg_loss * (1.0 - win_rate / 100.0))

        return {
            "initial_equity_idr": self.initial_equity,
            "final_equity_idr": round(final_equity, 2),
            "net_profit_idr": round(net_profit_idr, 2),
            "net_profit_pct": round(net_profit_pct, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "total_trades": len(closed_trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate_pct": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "expectancy_idr": round(expectancy, 2),
            "rejected_signals_count": len(rejected_trades)
        }
