"""
Adaptive Engine Router for V6.1-MACO R11.
Routes opportunities to ENGINE_A, ENGINE_B, HOLD, or NO_TRADE.
"""

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class AdaptiveEngineRouter:
    """
    Section 6: Adaptive Engine Router selecting optimal execution route.
    """
    ROUTE_ENGINE_A = "ENGINE_A"
    ROUTE_ENGINE_B = "ENGINE_B"
    ROUTE_HOLD = "HOLD"
    ROUTE_NO_TRADE = "NO_TRADE"

    @classmethod
    def route_opportunity(
        cls,
        signal_a: Dict[str, Any],
        signal_b: Dict[str, Any],
        has_open_position: bool,
        is_risk_limit_reached: bool
    ) -> Dict[str, Any]:
        """
        Determines the optimal route for an asset opportunity.
        """
        if is_risk_limit_reached:
            return {"route": cls.ROUTE_NO_TRADE, "chosen_signal": None, "reason": "Portfolio risk limit reached"}

        if has_open_position:
            return {"route": cls.ROUTE_HOLD, "chosen_signal": None, "reason": "Asset already has open position"}

        valid_a = signal_a.get("valid", False)
        valid_b = signal_b.get("valid", False)

        if not valid_a and not valid_b:
            reason_a = signal_a.get("reason", "No Engine A signal")
            reason_b = signal_b.get("reason", "No Engine B signal")
            return {"route": cls.ROUTE_NO_TRADE, "chosen_signal": None, "reason": f"A: {reason_a} | B: {reason_b}"}

        # If both are valid, pick the engine with higher expected net return
        if valid_a and valid_b:
            net_a = signal_a.get("expected_net_return_pct", 0.0)
            net_b = signal_b.get("expected_net_return_pct", 0.0)
            if net_b > net_a * 1.5:  # Engine B offers significantly larger net upside
                return {"route": cls.ROUTE_ENGINE_B, "chosen_signal": signal_b, "reason": "Engine B offers superior net momentum upside"}
            else:
                return {"route": cls.ROUTE_ENGINE_A, "chosen_signal": signal_a, "reason": "Engine A offers high-confidence scalping expectancy"}

        if valid_a:
            return {"route": cls.ROUTE_ENGINE_A, "chosen_signal": signal_a, "reason": signal_a.get("signal_reason")}

        if valid_b:
            return {"route": cls.ROUTE_ENGINE_B, "chosen_signal": signal_b, "reason": signal_b.get("signal_reason")}

        return {"route": cls.ROUTE_NO_TRADE, "chosen_signal": None, "reason": "NO_TRADE"}
