"""
Main Orchestrator Entry Point for INDODAX UNIFIED DUAL ENGINE ADAPTIVE TRADING SYSTEM.
Version: V6.1-MACO R11
"""

import sys
import os
import time
import math
import asyncio
import logging
import argparse
import uvicorn
import numpy as np
import pandas as pd
from typing import Dict, List, Any

from indodax_bot.config import (
    VERSION, MARKET_NAME, OPERATING_MODE, LIVE_TRADING_ENABLED,
    DCA_ENABLED, LEVERAGE_ENABLED, MARTINGALE_ENABLED,
    DEFAULT_PAPER_INITIAL_IDR, MAX_DAILY_LOSS_PCT
)
from indodax_bot.indodax_api import IndodaxAPIClient
from indodax_bot.market_data import MarketDataManager
from indodax_bot.indicators import TechnicalIndicators, MarketRegimeDetector
from indodax_bot.engine_a import ScalpingEngineA
from indodax_bot.engine_b import ExtremeMomentumHunterEngineB
from indodax_bot.engine_router import AdaptiveEngineRouter
from indodax_bot.risk_controller import PortfolioRiskController
from indodax_bot.portfolio import PortfolioManager
from indodax_bot.expectancy_monitor import ExpectancyMonitor
from indodax_bot.web_dashboard import create_dashboard_app
from indodax_bot.cli_dashboard import CLIDashboard
from indodax_bot.backtester import Backtester

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot_activity.log")
    ]
)
logger = logging.getLogger("IndodaxDualEngine")

class IndodaxBotController:
    def __init__(self, initial_cash_idr: float = DEFAULT_PAPER_INITIAL_IDR):
        self.api_client = IndodaxAPIClient()
        self.market_data = MarketDataManager(self.api_client)
        self.engine_a = ScalpingEngineA()
        self.engine_b = ExtremeMomentumHunterEngineB(min_score_threshold=60.0)
        self.risk_controller = PortfolioRiskController()
        self.portfolio = PortfolioManager(initial_cash_idr=initial_cash_idr)

        self.emergency_stop_triggered = False
        self.running = False

        self.latest_candidates_a: List[Dict[str, Any]] = []
        self.latest_candidates_b: List[Dict[str, Any]] = []
        self.equity_history: List[float] = [initial_cash_idr]

    def get_dashboard_state(self) -> Dict[str, Any]:
        """Construct full current dashboard snapshot state."""
        current_prices = {p_id: p_info["last_price"] for p_id, p_info in self.market_data.pair_info.items()}
        self.portfolio.update_position_values(current_prices)

        equity = self.portfolio.get_current_equity(current_prices)
        cash = self.portfolio.cash_idr
        self.equity_history.append(equity)

        unrealized_pnl = sum(p["unrealized_pnl"] for p in self.portfolio.open_positions)
        exposure_idr = sum(p["position_size_idr"] for p in self.portfolio.open_positions)
        exposure_pct = (exposure_idr / equity * 100.0) if equity > 0 else 0.0

        combined_risk_idr = sum(p.get("planned_risk_idr", 0.0) for p in self.portfolio.open_positions)
        combined_risk_pct = (combined_risk_idr / equity * 100.0) if equity > 0 else 0.0

        daily_loss_info = self.risk_controller.check_daily_loss_limit(
            self.portfolio.start_of_day_equity, equity, unrealized_pnl
        )

        daily_pnl_idr = equity - self.portfolio.start_of_day_equity

        # Expectancy Analytics
        analytics = ExpectancyMonitor.calculate_analytics(
            closed_trades=self.portfolio.closed_trades,
            equity_curve=self.equity_history,
            initial_equity=self.portfolio.start_of_day_equity
        )

        # Sanitize open positions for JSON compliance
        sanitized_positions = []
        for p in self.portfolio.open_positions:
            p_copy = dict(p)
            if math.isinf(p_copy.get("take_profit_price", 0.0)):
                p_copy["take_profit_price"] = None
            sanitized_positions.append(p_copy)

        return {
            "version": VERSION,
            "market": MARKET_NAME,
            "operating_mode": OPERATING_MODE,
            "live_trading_enabled": LIVE_TRADING_ENABLED,
            "emergency_stop": self.emergency_stop_triggered,
            "portfolio": {
                "equity": round(float(equity), 2),
                "cash": round(float(cash), 2),
                "cash_reserve_pct": round(float((cash / equity * 100.0) if equity > 0 else 100.0), 2),
                "capital_tier": "UNIFIED_V6.1",
                "exposure_pct": round(float(exposure_pct), 2),
                "combined_planned_risk_pct": round(float(combined_risk_pct), 2),
                "daily_pnl_idr": round(float(daily_pnl_idr), 2),
                "daily_loss_pct": round(float(daily_loss_info["daily_loss_pct"] * 100.0), 2),
                "start_of_day_equity": round(float(self.portfolio.start_of_day_equity), 2)
            },
            "analytics": analytics,
            "open_positions": sanitized_positions,
            "candidates_engine_a": self.latest_candidates_a,
            "candidates_engine_b": self.latest_candidates_b,
            "rejected_trades": self.portfolio.rejected_trades_log,
            "api_health": self.api_client.get_api_health()
        }

    async def run_trading_cycle(self):
        """Main periodic trading logic cycle for V6.1."""
        try:
            # 1. Fetch latest active pairs and tickers
            active_markets = self.market_data.refresh_pairs_and_tickers()
            if not active_markets:
                logger.warning("No active markets returned from Indodax API")
                return

            current_prices = {p_id: info["last_price"] for p_id, info in active_markets.items()}
            self.portfolio.update_position_values(current_prices)
            current_equity = self.portfolio.get_current_equity(current_prices)

            self.portfolio.check_and_reset_sod(current_equity)

            # 2. Check Open Position Exits
            for pos in self.portfolio.open_positions[:]:
                pair_id = pos["pair_id"]
                mkt_info = active_markets.get(pair_id)
                if not mkt_info:
                    continue

                price = mkt_info["last_price"]
                sim_candle = pd.Series({
                    "open": price, "high": price, "low": price, "close": price,
                    "ema9": price, "ema21": price * 0.99
                })

                exit_eval = None
                if pos["engine"] == "ENGINE_A_SCALPER":
                    exit_eval = self.engine_a.evaluate_exit(pos, sim_candle, mkt_info)
                else:
                    exit_eval = self.engine_b.evaluate_exit(pos, sim_candle, mkt_info)

                if exit_eval and exit_eval["exit"]:
                    sell_res = self.portfolio.execute_paper_sell(
                        position_id=pos["position_id"],
                        exit_price=exit_eval["price"],
                        exit_reason=exit_eval["reason"],
                        market_info=mkt_info
                    )
                    if sell_res.get("success") and pos["engine"] == "ENGINE_A_SCALPER":
                        is_win = sell_res["closed_record"]["realized_pnl_idr"] > 0
                        self.engine_a.record_trade_result(is_win, pair_id, time.time())

            if self.emergency_stop_triggered:
                logger.warning("Emergency Stop Active: Skipping candidate scanning and entries.")
                return

            # 3. Scan markets and generate candidates
            candidates_a = []
            candidates_b = []

            sorted_pairs = sorted(active_markets.values(), key=lambda x: x["vol_24h_idr"], reverse=True)[:30]

            now_ts = time.time()
            for mkt in sorted_pairs:
                pair_id = mkt["pair_id"]
                has_pos = any(p["pair_id"] == pair_id for p in self.portfolio.open_positions)

                df_synth = self._build_synthetic_candles(mkt)

                exec_info = self.market_data.analyze_executable_liquidity(
                    pair_id=pair_id,
                    order_size_idr=current_equity * 0.20,
                    is_buy=True
                )

                # Engine A evaluation
                sig_a = self.engine_a.evaluate_entry(
                    pair_id=pair_id,
                    df_1m=df_synth,
                    df_5m=df_synth,
                    df_15m=df_synth,
                    market_info=mkt,
                    execution_info=exec_info,
                    has_open_position=has_pos,
                    current_timestamp=now_ts
                )
                if sig_a.get("valid"):
                    candidates_a.append(sig_a)

                # Engine B evaluation
                sig_b = self.engine_b.evaluate_entry(
                    pair_id=pair_id,
                    df_15m=df_synth,
                    df_1h=df_synth,
                    market_info=mkt,
                    execution_info=exec_info,
                    target_position_idr=current_equity * 0.20,
                    has_open_position=has_pos
                )
                if sig_b.get("valid"):
                    candidates_b.append(sig_b)

            candidates_a.sort(key=lambda x: x["expected_net_return_pct"], reverse=True)
            candidates_b.sort(key=lambda x: x["score"], reverse=True)

            self.latest_candidates_a = candidates_a
            self.latest_candidates_b = candidates_b

            # 4. Adaptive Engine Routing & Active Reserve Deployment
            all_pairs = set([c["pair_id"] for c in candidates_a] + [c["pair_id"] for c in candidates_b])

            for pair_id in all_pairs:
                sig_a = next((c for c in candidates_a if c["pair_id"] == pair_id), {"valid": False})
                sig_b = next((c for c in candidates_b if c["pair_id"] == pair_id), {"valid": False})

                has_pos = any(p["pair_id"] == pair_id for p in self.portfolio.open_positions)
                combined_risk = sum(p.get("planned_risk_idr", 0.0) for p in self.portfolio.open_positions)
                risk_limit_reached = (combined_risk >= current_equity * 0.03)

                route_res = AdaptiveEngineRouter.route_opportunity(
                    signal_a=sig_a,
                    signal_b=sig_b,
                    has_open_position=has_pos,
                    is_risk_limit_reached=risk_limit_reached
                )

                chosen_sig = route_res.get("chosen_signal")
                if chosen_sig:
                    mkt_info = active_markets[pair_id]
                    exec_info = self.market_data.analyze_executable_liquidity(
                        pair_id=pair_id,
                        order_size_idr=current_equity * 0.20,
                        is_buy=True
                    )

                    reserve_eval = self.risk_controller.evaluate_active_reserve_deployment(
                        candidate_signal=chosen_sig,
                        current_equity=current_equity,
                        available_cash=self.portfolio.cash_idr,
                        open_positions=self.portfolio.open_positions,
                        start_of_day_equity=self.portfolio.start_of_day_equity,
                        market_info=mkt_info,
                        execution_info=exec_info
                    )

                    if reserve_eval.get("approved"):
                        self.portfolio.execute_paper_buy(
                            signal=chosen_sig,
                            position_size_idr=reserve_eval["position_size_idr"],
                            execution_price=mkt_info["ask"],
                            planned_risk_idr=reserve_eval["planned_risk_idr"],
                            market_info=mkt_info
                        )
                    else:
                        self.portfolio.log_rejected_trade(chosen_sig, reserve_eval.get("reason", "Unknown"))

        except Exception as e:
            logger.error(f"Error in trading cycle: {e}", exc_info=True)

    def manual_buy(self, pair_id: str, size_idr: float, engine: str = "MANUAL_ORDER") -> Dict[str, Any]:
        """Execute interactive manual buy order."""
        pair_id = pair_id.lower().strip()
        active_markets = self.market_data.refresh_pairs_and_tickers()

        mkt = active_markets.get(pair_id)
        if not mkt:
            return {"success": False, "reason": f"Market pair '{pair_id}' not found or inactive on Indodax"}

        ask_price = mkt["ask"]
        exec_info = self.market_data.analyze_executable_liquidity(pair_id=pair_id, order_size_idr=size_idr, is_buy=True)

        signal = {
            "pair_id": pair_id,
            "symbol": mkt.get("symbol", pair_id.upper()),
            "engine": engine,
            "stop_loss_pct": 0.02,
            "take_profit_pct": 0.04,
            "atr": ask_price * 0.015,
            "signal_reason": f"Manual Buy Order via Dashboard"
        }

        reserve_eval = self.risk_controller.evaluate_active_reserve_deployment(
            candidate_signal=signal,
            current_equity=self.portfolio.get_current_equity({pair_id: ask_price}),
            available_cash=self.portfolio.cash_idr,
            open_positions=self.portfolio.open_positions,
            start_of_day_equity=self.portfolio.start_of_day_equity,
            market_info=mkt,
            execution_info=exec_info
        )

        final_size_idr = reserve_eval["position_size_idr"] if reserve_eval.get("approved") else size_idr
        planned_risk = reserve_eval.get("planned_risk_idr", final_size_idr * 0.02)

        if self.portfolio.cash_idr < final_size_idr:
            return {"success": False, "reason": f"Insufficient available IDR (Cash: Rp{self.portfolio.cash_idr:,.0f}, Needed: Rp{final_size_idr:,.0f})"}

        res = self.portfolio.execute_paper_buy(
            signal=signal,
            position_size_idr=final_size_idr,
            execution_price=ask_price,
            planned_risk_idr=planned_risk,
            market_info=mkt
        )
        return res

    def manual_sell(self, position_id: str, reason: str = "MANUAL_SELL_DASHBOARD") -> Dict[str, Any]:
        """Execute interactive manual sell / close position."""
        target_pos = None
        for p in self.portfolio.open_positions:
            if p["position_id"] == position_id:
                target_pos = p
                break

        if not target_pos:
            return {"success": False, "reason": f"Position '{position_id}' not found in open positions"}

        pair_id = target_pos["pair_id"]
        active_markets = self.market_data.refresh_pairs_and_tickers()
        mkt = active_markets.get(pair_id, {"trade_fee_percent_maker": 0.001, "bid": target_pos["current_price"]})
        bid_price = mkt.get("bid", target_pos["current_price"])

        res = self.portfolio.execute_paper_sell(
            position_id=position_id,
            exit_price=bid_price,
            exit_reason=reason,
            market_info=mkt
        )
        if res.get("success") and target_pos["engine"] == "ENGINE_A_SCALPER":
            is_win = res["closed_record"]["realized_pnl_idr"] > 0
            self.engine_a.record_trade_result(is_win, pair_id, time.time())

        return res

    def _build_synthetic_candles(self, mkt: Dict[str, Any]) -> pd.DataFrame:
        """Construct multi-bar candle history reflecting actual Indodax 24h price trend & momentum."""
        price = mkt["last_price"]
        high = max(price, mkt["high_24h"])
        low = min(price, mkt["low_24h"]) if mkt["low_24h"] > 0 else price * 0.95
        vol = max(1000.0, mkt["vol_24h_idr"] / max(1.0, price))

        range_span = max(1e-8, high - low)
        range_pos = (price - low) / range_span

        start_price = low if range_pos > 0.5 else (price * 1.03 if range_pos < 0.3 else price * 0.99)

        bars = []
        now = time.time()
        num_bars = 35

        for i in range(num_bars):
            progress = i / float(num_bars - 1)

            bar_close = start_price + (price - start_price) * progress
            noise = (np.sin(i * 0.8) * 0.001) if i < num_bars - 1 else 0.0015
            bar_close = bar_close * (1.0 + noise)

            if i == num_bars - 1:
                bar_close = price
                bar_open = price * (0.992 if range_pos >= 0.5 else 0.998)
            else:
                bar_open = bar_close * (0.997 if range_pos >= 0.5 else 1.002)

            bar_high = max(bar_open, bar_close) * 1.0015
            bar_low = min(bar_open, bar_close) * 0.9985
            bar_vol = (vol / num_bars) * (2.2 if i >= num_bars - 5 else 0.9)

            bars.append({
                "timestamp": now - ((num_bars - 1 - i) * 900),
                "open": bar_open,
                "high": bar_high,
                "low": bar_low,
                "close": bar_close,
                "volume": bar_vol
            })

        return pd.DataFrame(bars)

async def main_async(args):
    bot = IndodaxBotController(initial_cash_idr=args.initial_cash)

    if args.mode == "backtest":
        logger.info("Executing Backtest Mode for V6.1-MACO R11...")
        sample_assets = ["btcidr", "ethidr", "solidr", "sgbidr", "dogeidr"]
        dataset = {}
        now = time.time()
        for asset in sample_assets:
            base_price = 100000.0 if asset == "btcidr" else 10000.0
            bars = []
            for i in range(200):
                change = (np.sin(i / 10.0) * 0.02) + (0.001 * (i % 5))
                c_price = base_price * (1.0 + change)
                bars.append({
                    "timestamp": now - ((200 - i) * 900),
                    "open": c_price * 0.998,
                    "high": c_price * 1.01,
                    "low": c_price * 0.995,
                    "close": c_price,
                    "volume": 50000.0
                })
            dataset[asset] = pd.DataFrame(bars)

        backtester = Backtester(initial_equity=args.initial_cash)
        res = backtester.run_backtest(dataset)

        print("\n" + "="*60)
        print(" INDODAX UNIFIED DUAL ENGINE V6.1 — BACKTEST RESULTS")
        print("="*60)
        for k, v in res.items():
            print(f" {k.replace('_', ' ').title():<30} : {v}")
        print("="*60 + "\n")
        return

    # Web Dashboard Server App
    dashboard_app = create_dashboard_app(bot)
    config = uvicorn.Config(app=dashboard_app, host="0.0.0.0", port=args.port, log_level="warning")
    server = uvicorn.Server(config)

    logger.info(f"Starting Indodax Dual Engine Bot V6.1 in PAPER_TRADING mode...")
    logger.info(f"Web Dashboard available at http://localhost:{args.port}")

    asyncio.create_task(server.serve())

    bot.running = True
    while bot.running:
        await bot.run_trading_cycle()
        state = bot.get_dashboard_state()
        CLIDashboard.print_snapshot(state)
        await asyncio.sleep(args.scan_interval)

def main():
    parser = argparse.ArgumentParser(description="INDODAX UNIFIED DUAL ENGINE — V6.1-MACO R11")
    parser.add_argument("--mode", choices=["paper", "backtest"], default="paper", help="Execution mode")
    parser.add_argument("--initial-cash", type=float, default=DEFAULT_PAPER_INITIAL_IDR, help="Initial cash IDR for paper trading")
    parser.add_argument("--port", type=int, default=8000, help="Web dashboard port")
    parser.add_argument("--scan-interval", type=int, default=5, help="Scan interval in seconds")

    args = parser.parse_args()
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")

if __name__ == "__main__":
    main()
