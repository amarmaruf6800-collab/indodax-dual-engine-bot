"""
Unified Risk Manager & Portfolio Reserve Controller for V6.1-MACO R11.
Enforces 0.5% per-trade risk, 3% aggregate open risk, 3% daily loss limit, 40% position cap, and 20% reserve floor.
"""

import math
import logging
from typing import Dict, List, Any, Optional, Tuple
from indodax_bot.config import (
    MAX_PLANNED_RISK_PER_TRADE, MAX_COMBINED_PLANNED_RISK, MAX_DAILY_LOSS_PCT,
    MAX_POSITION_ALLOC_CAP_PCT, MAX_CONCURRENT_POSITIONS, MIN_UNALLOCATED_RESERVE_PCT
)

logger = logging.getLogger(__name__)

class PortfolioRiskController:
    """
    Section 7 & 8: Unified Risk Manager & Portfolio Reserve Manager for V6.1-MACO R11.
    """
    def __init__(self):
        self.safe_mode_active = False
        self.safe_mode_reason: Optional[str] = None

    def trigger_safe_mode(self, reason: str):
        """Triggers SAFE_MODE on data invalidity or error."""
        self.safe_mode_active = True
        self.safe_mode_reason = reason
        logger.error(f"SAFE_MODE ACTIVATED: {reason}")

    def check_daily_loss_limit(
        self,
        start_of_day_equity: float,
        current_equity: float,
        unrealized_pnl: float
    ) -> Dict[str, Any]:
        """
        Section 7: Daily Safety Control.
        Calculates daily loss from Start-Of-Day equity. Halt entries if 3% daily loss limit hit.
        """
        if start_of_day_equity <= 0:
            return {"breached": False, "daily_loss_pct": 0.0}

        total_daily_equity = current_equity + unrealized_pnl
        daily_loss_idr = start_of_day_equity - total_daily_equity
        daily_loss_pct = (daily_loss_idr / start_of_day_equity)

        if daily_loss_pct >= MAX_DAILY_LOSS_PCT:
            return {
                "breached": True,
                "daily_loss_pct": daily_loss_pct,
                "daily_loss_idr": daily_loss_idr,
                "reason": f"Daily loss limit hit ({daily_loss_pct*100:.2f}% >= {MAX_DAILY_LOSS_PCT*100:.2f}%). All new entries halted."
            }

        return {
            "breached": False,
            "daily_loss_pct": daily_loss_pct,
            "daily_loss_idr": daily_loss_idr
        }

    def calculate_position_size(
        self,
        current_equity: float,
        available_cash: float,
        current_exposure_idr: float,
        stop_loss_distance_pct: float,
        entry_fee_pct: float,
        exit_fee_pct: float,
        execution_cost_pct: float,
        liquidity_cap_idr: float,
        min_exchange_order_idr: float
    ) -> Dict[str, Any]:
        """
        Section 4.H & 8: Dynamic Position Sizing Formula for V6.1.
        Max planned risk = 0.5% equity (Rp 25,000 on Rp 5,000,000).
        """
        risk_budget = current_equity * MAX_PLANNED_RISK_PER_TRADE  # 0.5% equity

        # Cash reserve floor (20% of initial equity)
        required_cash_reserve = current_equity * MIN_UNALLOCATED_RESERVE_PCT
        usable_cash = max(0.0, available_cash - required_cash_reserve)

        # Expected Loss Fraction
        expected_loss_fraction = (
            stop_loss_distance_pct
            + entry_fee_pct
            + exit_fee_pct
            + execution_cost_pct
        )

        if expected_loss_fraction <= 0.001:
            expected_loss_fraction = 0.01

        # Position size by 0.5% risk budget
        position_by_risk = risk_budget / expected_loss_fraction

        # Per-position allocation cap (40% of equity)
        position_alloc_cap = current_equity * MAX_POSITION_ALLOC_CAP_PCT

        # Final position size = MIN of all constraints
        final_position_size = min(
            position_by_risk,
            position_alloc_cap,
            liquidity_cap_idr,
            usable_cash
        )

        if final_position_size < min_exchange_order_idr:
            return {
                "valid": False,
                "position_size_idr": 0.0,
                "reason": f"Calculated position Rp{final_position_size:,.0f} is below exchange minimum order size Rp{min_exchange_order_idr:,.0f}"
            }

        planned_risk_idr = final_position_size * expected_loss_fraction
        planned_risk_pct = planned_risk_idr / current_equity

        return {
            "valid": True,
            "position_size_idr": round(final_position_size, 2),
            "planned_risk_idr": round(planned_risk_idr, 2),
            "planned_risk_pct": round(planned_risk_pct, 4),
            "expected_loss_fraction": round(expected_loss_fraction, 4),
            "allocation_pct_of_equity": round(final_position_size / current_equity, 4),
            "usable_cash": round(usable_cash, 2)
        }

    def evaluate_active_reserve_deployment(
        self,
        candidate_signal: Dict[str, Any],
        current_equity: float,
        available_cash: float,
        open_positions: List[Dict[str, Any]],
        start_of_day_equity: float,
        market_info: Dict[str, Any],
        execution_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Section 7 & 8: Active Reserve Deployment Decision Logic.
        """
        if self.safe_mode_active:
            return {"approved": False, "reason": f"SAFE_MODE ACTIVE: {self.safe_mode_reason}"}

        pair_id = candidate_signal["pair_id"]
        engine_type = candidate_signal["engine"]

        # 1. Daily Loss Check (3.0% threshold)
        unrealized_pnl = sum(p.get("unrealized_pnl", 0.0) for p in open_positions)
        daily_loss_res = self.check_daily_loss_limit(start_of_day_equity, current_equity, unrealized_pnl)
        if daily_loss_res["breached"]:
            return {"approved": False, "reason": daily_loss_res["reason"]}

        # 2. Duplicate Position Prevention
        existing_assets = [p["pair_id"] for p in open_positions]
        if pair_id in existing_assets:
            return {"approved": False, "reason": f"Duplicate position in {pair_id} prohibited across engines."}

        # 3. Concurrent Position Limit Check (Max 2 positions)
        if len(open_positions) >= MAX_CONCURRENT_POSITIONS:
            return {"approved": False, "reason": f"Max concurrent open positions ({MAX_CONCURRENT_POSITIONS}) reached."}

        # 4. Aggregate Open Risk Check (Max 3.0% combined planned risk)
        current_combined_risk = sum(p.get("planned_risk_idr", 0.0) for p in open_positions)
        max_combined_risk_budget = current_equity * MAX_COMBINED_PLANNED_RISK  # 3% equity

        remaining_risk_budget = max_combined_risk_budget - current_combined_risk
        if remaining_risk_budget <= 0:
            return {"approved": False, "reason": "Aggregate portfolio open risk limit (3.0% equity) reached."}

        # 5. Position Sizing
        stop_loss_pct = candidate_signal.get("stop_loss_pct", 0.02)
        taker_fee = market_info.get("trade_fee_percent_taker", 0.002)
        maker_fee = market_info.get("trade_fee_percent_maker", 0.001)
        slippage_pct = execution_info.get("slippage_pct", 0.0015)
        min_order_idr = market_info.get("trade_min_base_currency", 10000.0)
        liquidity_cap_idr = execution_info.get("total_available_idr", current_equity * 0.40)

        current_exposure_idr = sum(p.get("position_size_idr", 0.0) for p in open_positions)

        size_res = self.calculate_position_size(
            current_equity=current_equity,
            available_cash=available_cash,
            current_exposure_idr=current_exposure_idr,
            stop_loss_distance_pct=stop_loss_pct,
            entry_fee_pct=taker_fee,
            exit_fee_pct=maker_fee,
            execution_cost_pct=slippage_pct,
            liquidity_cap_idr=liquidity_cap_idr,
            min_exchange_order_idr=min_order_idr
        )

        if not size_res["valid"]:
            return {"approved": False, "reason": size_res["reason"]}

        pos_size = size_res["position_size_idr"]
        planned_risk_idr = size_res["planned_risk_idr"]

        # Scale down if planned risk exceeds remaining risk budget
        if planned_risk_idr > remaining_risk_budget:
            scaling_factor = remaining_risk_budget / planned_risk_idr
            pos_size = pos_size * scaling_factor
            if pos_size < min_order_idr:
                return {"approved": False, "reason": "Position size after risk scaling is below exchange minimum order size."}

            size_res["position_size_idr"] = round(pos_size, 2)
            size_res["planned_risk_idr"] = round(remaining_risk_budget, 2)

        # 6. Reserve Floor Check
        projected_remaining_cash = available_cash - pos_size
        if projected_remaining_cash < (current_equity * MIN_UNALLOCATED_RESERVE_PCT) - 1.0:
            return {"approved": False, "reason": "Projected cash violates 20% unallocated reserve floor."}

        return {
            "approved": True,
            "position_size_idr": size_res["position_size_idr"],
            "planned_risk_idr": size_res["planned_risk_idr"],
            "planned_risk_pct": size_res["planned_risk_pct"],
            "allocation_pct": size_res["allocation_pct_of_equity"]
        }
