"""
Unit tests for PortfolioManager and Paper Trading execution.
"""

import os
import unittest
from indodax_bot.portfolio import PortfolioManager

class TestPortfolioManager(unittest.TestCase):
    def setUp(self):
        self.state_file = "test_state.json"
        if os.path.exists(self.state_file):
            os.remove(self.state_file)
        self.pm = PortfolioManager(initial_cash_idr=10_000_000.0, state_file=self.state_file)

    def tearDown(self):
        if os.path.exists(self.state_file):
            os.remove(self.state_file)

    def test_paper_buy_and_sell(self):
        mkt_info = {"trade_fee_percent_taker": 0.002, "trade_fee_percent_maker": 0.001}
        signal = {
            "pair_id": "btcidr",
            "symbol": "BTCIDR",
            "engine": "ENGINE_A_SCALPER",
            "stop_loss_pct": 0.02,
            "take_profit_pct": 0.04,
            "atr": 200.0
        }

        # Execute Buy of 2,000,000 IDR
        buy_res = self.pm.execute_paper_buy(
            signal=signal,
            position_size_idr=2_000_000.0,
            execution_price=10_000.0,
            planned_risk_idr=40_000.0,
            market_info=mkt_info
        )

        self.assertTrue(buy_res["success"])
        self.assertEqual(len(self.pm.open_positions), 1)
        self.assertEqual(self.pm.cash_idr, 8_000_000.0)

        pos_id = self.pm.open_positions[0]["position_id"]

        # Execute Sell at 10,500 IDR (+5% price move)
        sell_res = self.pm.execute_paper_sell(
            position_id=pos_id,
            exit_price=10_500.0,
            exit_reason="TAKE_PROFIT_HIT",
            market_info=mkt_info
        )

        self.assertTrue(sell_res["success"])
        self.assertEqual(len(self.pm.open_positions), 0)
        self.assertGreater(self.pm.cash_idr, 10_000_000.0)
        self.assertGreater(self.pm.total_realized_pnl, 0.0)

if __name__ == '__main__':
    unittest.main()
