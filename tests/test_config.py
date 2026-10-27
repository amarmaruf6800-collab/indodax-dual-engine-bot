"""
Unit tests for configuration and V6.1 master command parameters.
"""

import unittest
from indodax_bot.config import (
    VERSION, MARKET_NAME, OPERATING_MODE, LIVE_TRADING_ENABLED,
    DCA_ENABLED, LEVERAGE_ENABLED, MARTINGALE_ENABLED,
    DEFAULT_PAPER_INITIAL_IDR, MAX_PLANNED_RISK_PER_TRADE,
    MAX_COMBINED_PLANNED_RISK, MAX_DAILY_LOSS_PCT,
    MAX_POSITION_ALLOC_CAP_PCT, MIN_UNALLOCATED_RESERVE_PCT
)

class TestConfigV61(unittest.TestCase):
    def test_v61_master_command_constraints(self):
        self.assertEqual(VERSION, "V6.1-MACO R11")
        self.assertEqual(MARKET_NAME, "Indodax IDR Spot")
        self.assertEqual(OPERATING_MODE, "PAPER_TRADING")
        self.assertEqual(DEFAULT_PAPER_INITIAL_IDR, 5_000_000.0)
        self.assertFalse(LIVE_TRADING_ENABLED)
        self.assertFalse(DCA_ENABLED)
        self.assertFalse(LEVERAGE_ENABLED)
        self.assertFalse(MARTINGALE_ENABLED)

    def test_v61_risk_limits(self):
        self.assertEqual(MAX_PLANNED_RISK_PER_TRADE, 0.005)   # 0.5% per trade
        self.assertEqual(MAX_COMBINED_PLANNED_RISK, 0.030)    # 3.0% max aggregate risk
        self.assertEqual(MAX_DAILY_LOSS_PCT, 0.030)           # 3.0% max daily loss
        self.assertEqual(MAX_POSITION_ALLOC_CAP_PCT, 0.40)   # 40% position cap
        self.assertEqual(MIN_UNALLOCATED_RESERVE_PCT, 0.20)  # 20% min reserve

if __name__ == '__main__':
    unittest.main()
