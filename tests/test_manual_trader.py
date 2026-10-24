"""
Unit tests for Manual Buy and Manual Sell controls in IndodaxBotController.
"""

import unittest
from indodax_bot.main import IndodaxBotController

class TestManualTrader(unittest.TestCase):
    def setUp(self):
        self.bot = IndodaxBotController(initial_cash_idr=10_000_000.0)
        self.bot.portfolio.open_positions = []  # Start with clean test list
        self.bot.portfolio.cash_idr = 10_000_000.0

    def test_manual_buy_and_sell_flow(self):
        # 1. Manual Buy BTCIDR
        buy_res = self.bot.manual_buy(pair_id="btcidr", size_idr=1_000_000.0, engine="MANUAL_ORDER")
        self.assertTrue(buy_res["success"])
        self.assertEqual(len(self.bot.portfolio.open_positions), 1)

        pos_id = self.bot.portfolio.open_positions[0]["position_id"]

        # 2. Manual Sell / Close Position
        sell_res = self.bot.manual_sell(position_id=pos_id, reason="TEST_MANUAL_SELL")
        self.assertTrue(sell_res["success"])
        self.assertEqual(len(self.bot.portfolio.open_positions), 0)

if __name__ == '__main__':
    unittest.main()
