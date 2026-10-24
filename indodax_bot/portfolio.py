"""
Portfolio, Balance, Position Tracker & State Persister for Paper Trading.
"""

import os
import json
import time
import logging
from typing import Dict, List, Any, Optional
from indodax_bot.config import STATE_FILE_PATH, TRADE_LOG_PATH, DEFAULT_PAPER_INITIAL_IDR, INDODAX_TAKER_FEE, INDODAX_MAKER_FEE

logger = logging.getLogger(__name__)

class PortfolioManager:
    def __init__(self, initial_cash_idr: float = DEFAULT_PAPER_INITIAL_IDR, state_file: str = STATE_FILE_PATH):
        self.state_file = state_file
        self.trade_log_file = TRADE_LOG_PATH

        self.cash_idr: float = initial_cash_idr
        self.start_of_day_equity: float = initial_cash_idr
        self.sod_timestamp: float = time.time()

        self.open_positions: List[Dict[str, Any]] = []
        self.closed_trades: List[Dict[str, Any]] = []

        self.total_realized_pnl: float = 0.0
        self.rejected_trades_log: List[Dict[str, Any]] = []

        # Try loading state on startup
        self.load_state()

    def get_current_equity(self, current_prices: Dict[str, float]) -> float:
        """
        Calculate total account equity = cash + market value of open positions.
        """
        position_value = 0.0
        for pos in self.open_positions:
            pair_id = pos["pair_id"]
            price = current_prices.get(pair_id, pos["entry_price"])
            position_value += pos["units"] * price
        return self.cash_idr + position_value

    def update_position_values(self, current_prices: Dict[str, float]):
        """
        Update current price, highest price, and unrealized PnL for open positions.
        """
        for pos in self.open_positions:
            pair_id = pos["pair_id"]
            if pair_id in current_prices:
                price = current_prices[pair_id]
                pos["current_price"] = price
                pos["highest_price"] = max(pos.get("highest_price", price), price)

                mkt_val = pos["units"] * price
                pos["unrealized_pnl"] = mkt_val - pos["position_size_idr"]
                pos["unrealized_pnl_pct"] = (pos["unrealized_pnl"] / pos["position_size_idr"]) if pos["position_size_idr"] > 0 else 0.0

    def check_and_reset_sod(self, current_equity: float):
        """
        Reset Start-Of-Day equity every 24 hours.
        """
        now = time.time()
        if now - self.sod_timestamp >= 86400.0:  # 24 hours
            self.start_of_day_equity = current_equity
            self.sod_timestamp = now
            logger.info(f"Reset Start-Of-Day equity to Rp{current_equity:,.0f}")
            self.save_state()

    def execute_paper_buy(
        self,
        signal: Dict[str, Any],
        position_size_idr: float,
        execution_price: float,
        planned_risk_idr: float,
        market_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Simulates buy order execution in Paper Trading mode.
        Deducts position_size_idr and taker fee from cash.
        """
        pair_id = signal["pair_id"]
        taker_fee_pct = market_info.get("trade_fee_percent_taker", INDODAX_TAKER_FEE)
        fee_idr = position_size_idr * taker_fee_pct

        net_investment_idr = position_size_idr - fee_idr
        units = net_investment_idr / execution_price if execution_price > 0 else 0.0

        if self.cash_idr < position_size_idr:
            return {"success": False, "reason": "Insufficient cash balance"}

        # Deduct cash
        self.cash_idr -= position_size_idr

        # Calculate stop loss and take profit prices
        stop_loss_pct = float(signal.get("stop_loss_pct", 0.02))
        take_profit_pct = signal.get("take_profit_pct")

        stop_loss_price = float(execution_price * (1.0 - stop_loss_pct))
        take_profit_price = float(execution_price * (1.0 + take_profit_pct)) if take_profit_pct else float('inf')

        position = {
            "position_id": f"POS_{int(time.time()*1000)}",
            "pair_id": pair_id,
            "symbol": signal.get("symbol", pair_id.upper()),
            "engine": signal["engine"],
            "entry_time": float(time.time()),
            "entry_price": float(execution_price),
            "current_price": float(execution_price),
            "highest_price": float(execution_price),
            "units": float(units),
            "position_size_idr": float(position_size_idr),
            "entry_fee_idr": float(fee_idr),
            "planned_risk_idr": float(planned_risk_idr),
            "stop_loss_price": float(stop_loss_price),
            "take_profit_price": float(take_profit_price),
            "atr": float(signal.get("atr", execution_price * 0.01)),
            "unrealized_pnl": 0.0,
            "unrealized_pnl_pct": 0.0,
            "signal_reason": str(signal.get("signal_reason", ""))
        }

        self.open_positions.append(position)
        logger.info(f"PAPER BUY {pair_id} via {signal['engine']}: Size Rp{position_size_idr:,.0f} @ Rp{execution_price:,.0f}")
        self.save_state()

        return {"success": True, "position": position}

    def execute_paper_sell(
        self,
        position_id: str,
        exit_price: float,
        exit_reason: str,
        market_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Simulates sell order execution in Paper Trading mode.
        Adds proceeds minus maker/taker fee back to cash balance.
        """
        target_pos = None
        for pos in self.open_positions:
            if pos["position_id"] == position_id:
                target_pos = pos
                break

        if not target_pos:
            return {"success": False, "reason": "Position not found"}

        maker_fee_pct = market_info.get("trade_fee_percent_maker", INDODAX_MAKER_FEE)
        gross_proceeds = target_pos["units"] * exit_price
        exit_fee = gross_proceeds * maker_fee_pct
        net_proceeds = gross_proceeds - exit_fee

        realized_pnl = net_proceeds - target_pos["position_size_idr"]
        realized_pnl_pct = realized_pnl / target_pos["position_size_idr"]

        # Add net proceeds back to cash
        self.cash_idr += net_proceeds
        self.total_realized_pnl += realized_pnl

        closed_record = {
            **target_pos,
            "exit_time": time.time(),
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "exit_fee_idr": exit_fee,
            "net_proceeds_idr": net_proceeds,
            "realized_pnl_idr": realized_pnl,
            "realized_pnl_pct": realized_pnl_pct,
            "holding_duration_sec": time.time() - target_pos["entry_time"]
        }

        self.open_positions.remove(target_pos)
        self.closed_trades.append(closed_record)

        logger.info(f"PAPER SELL {target_pos['pair_id']} [{exit_reason}]: PnL Rp{realized_pnl:,.0f} ({realized_pnl_pct*100:.2f}%) @ Rp{exit_price:,.0f}")
        self.save_state()
        self.save_trade_history()

        return {"success": True, "closed_record": closed_record}

    def log_rejected_trade(self, candidate: Dict[str, Any], reason: str):
        """Record rejected signals for reporting on dashboard."""
        entry = {
            "timestamp": time.time(),
            "pair_id": candidate.get("pair_id"),
            "engine": candidate.get("engine"),
            "reason": reason
        }
        self.rejected_trades_log.append(entry)
        if len(self.rejected_trades_log) > 50:
            self.rejected_trades_log.pop(0)

    def save_state(self):
        """Persist state to JSON file."""
        state = {
            "cash_idr": self.cash_idr,
            "start_of_day_equity": self.start_of_day_equity,
            "sod_timestamp": self.sod_timestamp,
            "total_realized_pnl": self.total_realized_pnl,
            "open_positions": self.open_positions,
            "rejected_trades_count": len(self.rejected_trades_log)
        }
        try:
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def load_state(self):
        """Load state from JSON file if exists."""
        if not os.path.exists(self.state_file):
            return

        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)
                self.cash_idr = state.get("cash_idr", self.cash_idr)
                self.start_of_day_equity = state.get("start_of_day_equity", self.start_of_day_equity)
                self.sod_timestamp = state.get("sod_timestamp", self.sod_timestamp)
                self.total_realized_pnl = state.get("total_realized_pnl", 0.0)
                self.open_positions = state.get("open_positions", [])
                logger.info(f"Loaded state from {self.state_file}: Cash=Rp{self.cash_idr:,.0f}, OpenPositions={len(self.open_positions)}")
        except Exception as e:
            logger.error(f"Failed to load state: {e}")

    def save_trade_history(self):
        """Save closed trades log."""
        try:
            with open(self.trade_log_file, "w") as f:
                json.dump(self.closed_trades, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save trade history: {e}")
