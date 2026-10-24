"""
Unit tests for PortfolioRiskController and Shared Position Sizing.
"""

import unittest
from indodax_bot.risk_controller import PortfolioRiskController

class TestPortfolioRiskController(unittest.TestCase):
    def setUp(self):
        self.risk_ctrl = PortfolioRiskController()

    def test_capital_tier_determination(self):
        # Tier 1: Rp 10M
        tier1 = self.risk_ctrl.determine_capital_tier(10_000_000)
        self.assertEqual(tier1["tier"], "TIER_1")
        self.assertTrue(tier1["allow_new_entries"])
        self.assertEqual(tier1["asset_alloc_cap_pct"], 0.40)

        # Tier 2: Rp 50M
        tier2 = self.risk_ctrl.determine_capital_tier(50_000_000)
        self.assertEqual(tier2["tier"], "TIER_2")
        self.assertTrue(tier2["allow_new_entries"])
        self.assertEqual(tier2["asset_alloc_cap_pct"], 0.10)

        # Exceeded Tier 2 (> 100M)
        tier_exceed = self.risk_ctrl.determine_capital_tier(120_000_000)
        self.assertEqual(tier_exceed["tier"], "EQUITY_HALT_EXCEEDED")
        self.assertFalse(tier_exceed["allow_new_entries"])

    def test_daily_loss_limit(self):
        sod_equity = 10_000_000.0

        # Loss = Rp 100k (1% loss) -> Not breached
        res1 = self.risk_ctrl.check_daily_loss_limit(sod_equity, 9_900_000.0, 0.0)
        self.assertFalse(res1["breached"])

        # Loss = Rp 250k (2.5% loss) -> Breached
        res2 = self.risk_ctrl.check_daily_loss_limit(sod_equity, 9_750_000.0, 0.0)
        self.assertTrue(res2["breached"])

    def test_shared_position_sizing(self):
        # Current equity = 10,000,000 IDR
        # Risk budget = 1% = 100,000 IDR
        # Stop loss = 2%, fees = 0.3%, execution cost = 0.15% -> total loss fraction = 2.45% = 0.0245
        # Expected position size by risk = 100,000 / 0.0245 = 4,081,632 IDR (~40.8% equity)

        size_res = self.risk_ctrl.calculate_position_size(
            current_equity=10_000_000.0,
            available_cash=10_000_000.0,
            current_exposure_idr=0.0,
            stop_loss_distance_pct=0.02,
            entry_fee_pct=0.002,
            exit_fee_pct=0.001,
            execution_cost_pct=0.0015,
            asset_alloc_cap_pct=0.40,
            liquidity_cap_idr=5_000_000.0,
            min_exchange_order_idr=10_000.0
        )

        self.assertTrue(size_res["valid"])
        # Should be capped at asset_alloc_cap (4,000,000 IDR) because 4,081,632 > 4,000,000
        self.assertAlmostEqual(size_res["position_size_idr"], 4_000_000.0, delta=100.0)

    def test_active_reserve_deployment_rejection_on_duplicate(self):
        signal = {
            "pair_id": "btcidr",
            "engine": "ENGINE_A_SCALPER",
            "stop_loss_pct": 0.02
        }
        open_pos = [{"pair_id": "btcidr", "engine": "ENGINE_B_MOMENTUM_HUNTER", "position_size_idr": 2_000_000}]

        res = self.risk_ctrl.evaluate_active_reserve_deployment(
            candidate_signal=signal,
            current_equity=10_000_000.0,
            available_cash=8_000_000.0,
            open_positions=open_pos,
            start_of_day_equity=10_000_000.0,
            market_info={"trade_fee_percent_taker": 0.002, "trade_fee_percent_maker": 0.001, "trade_min_base_currency": 10000},
            execution_info={"slippage_pct": 0.0015, "total_available_idr": 5_000_000}
        )

        self.assertFalse(res["approved"])
        self.assertIn("Duplicate", res["reason"])

if __name__ == '__main__':
    unittest.main()
