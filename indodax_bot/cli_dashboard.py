"""
Terminal CLI Dashboard Renderer for INDODAX UNIFIED DUAL ENGINE V6.1-MACO R11.
"""

import os
import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class CLIDashboard:
    @staticmethod
    def print_snapshot(state: Dict[str, Any]):
        """Render clean terminal summary snapshot."""
        p = state.get("portfolio", {})
        analytics = state.get("analytics", {})
        open_pos = state.get("open_positions", [])
        cand_a = state.get("candidates_engine_a", [])
        cand_b = state.get("candidates_engine_b", [])
        api_h = state.get("api_health", {})

        os.system('cls' if os.name == 'nt' else 'clear')
        print("==================================================================================")
        print(" INDODAX UNIFIED DUAL ENGINE V6.1-MACO R11 — PAPER TRADING ACTIVE")
        print(" Cost-Aware Adaptive Scalper (A) + Extreme Momentum Hunter (B)")
        print("==================================================================================")
        print(f" Total Equity     : Rp {p.get('equity', 0):,.0f}")
        print(f" Available Cash   : Rp {p.get('cash', 0):,.0f} (Reserve: {p.get('cash_reserve_pct', 100):.1f}%)")
        print(f" Net Expectancy   : Rp {analytics.get('net_expectancy_idr', 0):,.0f} (Win Rate: {analytics.get('win_rate_pct', 0):.1f}%)")
        print(f" Total Exposure   : {p.get('exposure_pct', 0):.1f}% (Max Ceiling: 80%)")
        print(f" Portfolio Risk   : {p.get('combined_planned_risk_pct', 0):.2f}% (Max Limit: 3.0%)")
        print(f" Daily PnL / Loss : Rp {p.get('daily_pnl_idr', 0):,.0f} ({p.get('daily_loss_pct', 0):.2f}%)")
        print("----------------------------------------------------------------------------------")
        print(f" ACTIVE POSITIONS ({len(open_pos)}):")
        if not open_pos:
            print("   [No active positions]")
        else:
            for pos in open_pos:
                print(f"   • {pos['symbol']} [{pos['engine']}]: Entry=Rp{pos['entry_price']:,.0f} | "
                      f"Current=Rp{pos['current_price']:,.0f} | Size=Rp{pos['position_size_idr']:,.0f} | "
                      f"PnL=Rp{pos['unrealized_pnl']:,.0f} ({pos['unrealized_pnl_pct']*100:.2f}%)")

        print("----------------------------------------------------------------------------------")
        print(f" CANDIDATE SIGNALS:")
        print(f"   • Engine A Scalper  : {len(cand_a)} valid candidates")
        for c in cand_a[:3]:
            rvol = c.get('rvol', 0.0)
            roc = c.get('roc_pct', 0.0)
            price = c.get('entry_price', 0.0)
            print(f"     -> {c.get('symbol', '')} @ Rp{price:,.0f} | RVOL={rvol:.1f} | ROC={roc:.1f}%")
        print(f"   • Engine B Momentum : {len(cand_b)} valid candidates")
        for c in cand_b[:3]:
            score = c.get('score', 0.0)
            spread = c.get('spread_pct', 0.0)
            price = c.get('entry_price', 0.0)
            print(f"     -> {c.get('symbol', '')} @ Rp{price:,.0f} | Score={score}/100 | Spread={spread*100:.2f}%")

        print("----------------------------------------------------------------------------------")
        print(f" API HEALTH: Status={api_h.get('status', 'OK')} | Latency={api_h.get('last_latency_ms', 0)}ms | Success={api_h.get('success_rate_pct', 100)}%")
        print("==================================================================================")
