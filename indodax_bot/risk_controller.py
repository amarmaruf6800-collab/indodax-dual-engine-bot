"""
Portfolio Risk Controller & Active Reserve Deployment Manager.
Enforces Capital Tiers, Shared Position Sizing, Daily Loss Limits, and Correlation Rules.
"""

import math
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from indodax_bot.config import (
    TIER_1_MIN_EQUITY, TIER_1_MAX_EQUITY, TIER_1_MAX_ENGINE_A_ALLOC, TIER_1_MAX_ENGINE_B_ALLOC,
    TIER_1_MAX_POSITIONS_PER_ENGINE, TIER_1_MAX_TOTAL_POSITIONS,
    TIER_2_MIN_EQUITY, TIER_2_MAX_EQUITY, TIER_2_ASSET_ALLOC_MIN, TIER_2_ASSET_ALLOC_MAX,
    EQUITY_HALT_THRESHOLD,
    MAX_PLANNED_RISK_PER_TRADE, MAX_COMBINED_PLANNED_RISK, MAX_DAILY_LOSS_PCT,
    MAX_PORTFOLIO_EXPOSURE, MIN_CASH_RESERVE
)

logger = logging.getLogger(__name__)

class PortfolioRiskController:
    def __init__(self):
        pass

    def determine_capital_tier(self, equity: float) -> Dict[str, Any]:
        """
        Determines current Capital Tier based on equity level per Section 2.
        """
        if equity > EQUITY_HALT_THRESHOLD:
            return {
                "tier": "EQUITY_HALT_EXCEEDED",
                "allow_new_entries": False,
                "reason": f"Current equity Rp{equity:,.0f} exceeds Tier 2 ceiling (Rp100,000,000). Entries halted per Section 2."
            }
        elif equity >= TIER_1_MIN_EQUITY and equity <= TIER_1_MAX_EQUITY:
            return {
                "tier": "TIER_1",
                "allow_new_entries": True,
                "engine_a_max_alloc": TIER_1_MAX_ENGINE_A_ALLOC, # 40%
                "engine_b_max_alloc": TIER_1_MAX_ENGINE_B_ALLOC, # 40%
                "max_positions_per_engine": TIER_1_MAX_POSITIONS_PER_ENGINE, # 1
                "max_concurrent_positions": TIER_1_MAX_TOTAL_POSITIONS, # 2
                "asset_alloc_cap_pct": 0.40
            }
        elif equity > TIER_1_MAX_EQUITY and equity <= TIER_2_MAX_EQUITY:
            return {
                "tier": "TIER_2",
                "allow_new_entries": True,
                "engine_a_max_alloc": TIER_2_ASSET_ALLOC_MAX, # 10% per asset
                "engine_b_max_alloc": TIER_2_ASSET_ALLOC_MAX, # 10% per asset
                "max_positions_per_engine": 10,
                "max_concurrent_positions": 8,
                "asset_alloc_cap_pct": TIER_2_ASSET_ALLOC_MAX # 10%
            }
        else:
            return {
                "tier": "BELOW_TIER_1",
                "allow_new_entries": False,
                "reason": f"Equity Rp{equity:,.0f} below minimum required Rp{TIER_1_MIN_EQUITY:,.0f}"
            }

    def check_daily_loss_limit(
        self,
        start_of_day_equity: float,
        current_equity: float,
        unrealized_pnl: float
    ) -> Dict[str, Any]:
        """
        Section 9: Daily Safety Controls.
        Calculates daily loss from start-of-day equity.
        Includes realized + unrealized PnL. Stop new entries if daily loss threshold (2%) hit.
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
                "reason": f"Daily loss limit hit ({daily_loss_pct*100:.2f}% >= {MAX_DAILY_LOSS_PCT*100:.2f}%). New entries halted."
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
        asset_alloc_cap_pct: float,
        liquidity_cap_idr: float,
        min_exchange_order_idr: float
    ) -> Dict[str, Any]:
        """
        Section 6: Shared Position Sizing Master Formulas.
        """
        risk_budget = current_equity * MAX_PLANNED_RISK_PER_TRADE  # 1% equity

        # Total portfolio limits
        max_total_exposure = current_equity * MAX_PORTFOLIO_EXPOSURE  # 80%
        required_cash_reserve = current_equity * MIN_CASH_RESERVE     # 20%

        # Cash available for new positions after preserving 20% reserve floor
        usable_cash = max(0.0, available_cash - required_cash_reserve)

        # Remaining exposure room
        remaining_exposure_room = max(0.0, max_total_exposure - current_exposure_idr)

        # Expected Loss Fraction = stop_loss + entry_fee + exit_fee + conservative_execution_cost
        expected_loss_fraction = (
            stop_loss_distance_pct
            + entry_fee_pct
            + exit_fee_pct
            + execution_cost_pct
        )

        if expected_loss_fraction <= 0.001:
            expected_loss_fraction = 0.01  # Safe default lower bound

        # Position size purely driven by 1% risk budget
        position_by_risk = risk_budget / expected_loss_fraction

        # Per-asset allocation cap in IDR
        asset_allocation_cap = current_equity * asset_alloc_cap_pct

        # Final position size = MIN of all constraints
        final_position_size = min(
            position_by_risk,
            asset_allocation_cap,
            remaining_exposure_room,
            liquidity_cap_idr,
            usable_cash
        )

        # Check minimum exchange order constraint
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
        Section 5: Active Reserve Deployment Decision Logic.
        Returns authorization status and calculated position size.
        """
        pair_id = candidate_signal["pair_id"]
        engine_type = candidate_signal["engine"]

        # 1. Tier & Entry Permission Check
        tier_info = self.determine_capital_tier(current_equity)
        if not tier_info.get("allow_new_entries", False):
            return {"approved": False, "reason": tier_info.get("reason", "Capital tier prohibits entries")}

        # 2. Daily Loss Check
        unrealized_pnl = sum(p.get("unrealized_pnl", 0.0) for p in open_positions)
        daily_loss_res = self.check_daily_loss_limit(start_of_day_equity, current_equity, unrealized_pnl)
        if daily_loss_res["breached"]:
            return {"approved": False, "reason": daily_loss_res["reason"]}

        # 3. Duplicate Position Prevention (Section 1 & 7)
        existing_assets = [p["pair_id"] for p in open_positions]
        if pair_id in existing_assets:
            return {"approved": False, "reason": f"Duplicate position in {pair_id} prohibited across engines."}

        # 4. Engine Position Limits Check
        engine_positions = [p for p in open_positions if p.get("engine") == engine_type]
        max_per_engine = tier_info.get("max_positions_per_engine", 1)
        if len(engine_positions) >= max_per_engine:
            return {"approved": False, "reason": f"{engine_type} max position count ({max_per_engine}) reached."}

        max_concurrent = tier_info.get("max_concurrent_positions", 2)
        if len(open_positions) >= max_concurrent:
            return {"approved": False, "reason": f"Max total concurrent positions ({max_concurrent}) reached."}

        # 5. Combined Planned Risk Check (Section 7: Max 2% total combined planned risk)
        current_combined_risk = sum(p.get("planned_risk_idr", 0.0) for p in open_positions)
        max_combined_risk_budget = current_equity * MAX_COMBINED_PLANNED_RISK  # 2% equity

        remaining_risk_budget = max_combined_risk_budget - current_combined_risk
        if remaining_risk_budget <= 0:
            return {"approved": False, "reason": "Combined portfolio risk limit (2% equity) reached."}

        # 6. Current Exposure
        current_exposure_idr = sum(p.get("position_size_idr", 0.0) for p in open_positions)

        # 7. Sizing Calculation
        stop_loss_pct = candidate_signal.get("stop_loss_pct", 0.02)
        taker_fee = market_info.get("trade_fee_percent_taker", 0.002)
        maker_fee = market_info.get("trade_fee_percent_maker", 0.001)
        slippage_pct = execution_info.get("slippage_pct", 0.0015)
        min_order_idr = market_info.get("trade_min_base_currency", 10000)
        liquidity_cap_idr = execution_info.get("total_available_idr", current_equity * 0.40)

        size_res = self.calculate_position_size(
            current_equity=current_equity,
            available_cash=available_cash,
            current_exposure_idr=current_exposure_idr,
            stop_loss_distance_pct=stop_loss_pct,
            entry_fee_pct=taker_fee,
            exit_fee_pct=maker_fee,
            execution_cost_pct=slippage_pct,
            asset_alloc_cap_pct=tier_info.get("asset_alloc_cap_pct", 0.40),
            liquidity_cap_idr=liquidity_cap_idr,
            min_exchange_order_idr=min_order_idr
        )

        if not size_res["valid"]:
            return {"approved": False, "reason": size_res["reason"]}

        pos_size = size_res["position_size_idr"]

        # 8. Re-check risk after calculated size
        planned_risk_idr = size_res["planned_risk_idr"]
        if planned_risk_idr > remaining_risk_budget:
            # Scale down position size to fit remaining combined risk budget
            scaling_factor = remaining_risk_budget / planned_risk_idr
            pos_size = pos_size * scaling_factor
            if pos_size < min_order_idr:
                return {"approved": False, "reason": "Position size after risk scaling is below exchange minimum order size."}

            size_res["position_size_idr"] = round(pos_size, 2)
            size_res["planned_risk_idr"] = round(remaining_risk_budget, 2)

        # 9. Final Reserve & Exposure Check
        projected_exposure = current_exposure_idr + pos_size
        projected_exposure_pct = projected_exposure / current_equity

        if projected_exposure_pct > MAX_PORTFOLIO_EXPOSURE + 1e-5:
            return {"approved": False, "reason": f"Projected exposure {projected_exposure_pct*100:.1f}% exceeds 80% ceiling."}

        projected_remaining_cash = available_cash - pos_size
        if projected_remaining_cash < (current_equity * MIN_CASH_RESERVE) - 1.0:
            return {"approved": False, "reason": "Projected cash violates 20% minimum reserve."}

        return {
            "approved": True,
            "tier": tier_info["tier"],
            "position_size_idr": size_res["position_size_idr"],
            "planned_risk_idr": size_res["planned_risk_idr"],
            "planned_risk_pct": size_res["planned_risk_pct"],
            "allocation_pct": size_res["allocation_pct_of_equity"],
            "projected_exposure_pct": round(projected_exposure_pct, 4)
        }
