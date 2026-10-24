"""
Unit tests for configuration and master command parameters.
"""

import unittest
from indodax_bot.config import (
    VERSION, MARKET_NAME, OPERATING_MODE, LIVE_TRADING_ENABLED,
    DCA_ENABLED, LEVERAGE_ENABLED, MARTINGALE_ENABLED,
    MAX_PLANNED_RISK_PER_TRADE, MAX_COMBINED_PLANNED_RISK, MAX_DAILY_LOSS_PCT,
    MAX_PORTFOLIO_EXPOSURE, MIN_CASH_RESERVE
)

class TestConfig(unittest.TestCase):
    def test_master_command_constraints(self):
        self.assertEqual(VERSION, "V5.3-MACO R3")
        self.assertEqual(MARKET_NAME, "Indodax IDR Spot")
        self.assertEqual(OPERATING_MODE, "PAPER_TRADING")
        self.assertFalse(LIVE_TRADING_ENABLED)
        self.assertFalse(DCA_ENABLED)
        self.assertFalse(LEVERAGE_ENABLED)
        self.assertFalse(MARTINGALE_ENABLED)

    def test_risk_limits(self):
        self.assertEqual(MAX_PLANNED_RISK_PER_TRADE, 0.01)   # 1% per trade
        self.assertEqual(MAX_COMBINED_PLANNED_RISK, 0.02)    # 2% max portfolio risk
        self.assertEqual(MAX_DAILY_LOSS_PCT, 0.02)           # 2% max daily loss
        self.assertEqual(MAX_PORTFOLIO_EXPOSURE, 0.80)       # 80% max exposure
        self.assertEqual(MIN_CASH_RESERVE, 0.20)             # 20% min reserve

if __name__ == '__main__':
    unittest.main()
