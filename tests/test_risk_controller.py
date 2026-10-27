"""
Unit tests for PortfolioRiskController in V6.1.
"""

import unittest
from indodax_bot.risk_controller import PortfolioRiskController

class TestPortfolioRiskControllerV61(unittest.TestCase):
    def setUp(self):
        self.risk_ctrl = PortfolioRiskController()

    def test_daily_loss_limit_v61(self):
        sod_equity = 5_000_000.0

        # Loss = Rp 100k (2% loss) -> Not breached (3% limit)
        res1 = self.risk_ctrl.check_daily_loss_limit(sod_equity, 4_900_000.0, 0.0)
        self.assertFalse(res1["breached"])

        # Loss = Rp 160k (3.2% loss) -> Breached
        res2 = self.risk_ctrl.check_daily_loss_limit(sod_equity, 4_840_000.0, 0.0)
        self.assertTrue(res2["breached"])

    def test_position_sizing_v61(self):
        # Current equity = 5,000,000 IDR
        # Risk budget = 0.5% = 25,000 IDR
        # Stop loss = 2%, fees = 0.3%, execution cost = 0.15% -> total loss fraction = 2.45% = 0.0245
        # Expected position size by risk = 25,000 / 0.0245 = 1,020,408 IDR (~20.4% equity)

        size_res = self.risk_ctrl.calculate_position_size(
            current_equity=5_000_000.0,
            available_cash=5_000_000.0,
            current_exposure_idr=0.0,
            stop_loss_distance_pct=0.02,
            entry_fee_pct=0.002,
            exit_fee_pct=0.001,
            execution_cost_pct=0.0015,
            liquidity_cap_idr=2_000_000.0,
            min_exchange_order_idr=10_000.0
        )

        self.assertTrue(size_res["valid"])
        self.assertAlmostEqual(size_res["position_size_idr"], 1_020_408.16, delta=100.0)
        self.assertAlmostEqual(size_res["planned_risk_idr"], 25_000.0, delta=100.0)

if __name__ == '__main__':
    unittest.main()
