"""
Unit tests for ExpectancyMonitor and V6.1 Analytics.
"""

import unittest
from indodax_bot.expectancy_monitor import ExpectancyMonitor

class TestExpectancyMonitor(unittest.TestCase):
    def test_expectancy_formulation(self):
        closed_trades = [
            {"engine": "ENGINE_A_SCALPER", "realized_pnl_idr": 50_000.0, "entry_fee_idr": 2000, "exit_fee_idr": 1000},
            {"engine": "ENGINE_A_SCALPER", "realized_pnl_idr": -20_000.0, "entry_fee_idr": 2000, "exit_fee_idr": 1000},
            {"engine": "ENGINE_B_MOMENTUM_HUNTER", "realized_pnl_idr": 100_000.0, "entry_fee_idr": 2000, "exit_fee_idr": 1000}
        ]
        equity_curve = [5_000_000.0, 5_050_000.0, 5_030_000.0, 5_130_000.0]

        analytics = ExpectancyMonitor.calculate_analytics(
            closed_trades=closed_trades,
            equity_curve=equity_curve,
            initial_equity=5_000_000.0
        )

        self.assertEqual(analytics["total_trades"], 3)
        self.assertEqual(analytics["winning_trades"], 2)
        self.assertEqual(analytics["losing_trades"], 1)
        self.assertAlmostEqual(analytics["win_rate_pct"], 66.67, delta=0.1)
        self.assertGreater(analytics["net_expectancy_idr"], 0)
        self.assertGreater(analytics["profit_factor"], 1.0)

if __name__ == '__main__':
    unittest.main()
