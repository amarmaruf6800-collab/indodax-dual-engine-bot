"""
Unit tests for Engine A (Pure Scalper) and Engine B (Extreme Momentum Hunter).
"""

import unittest
import numpy as np
import pandas as pd
from indodax_bot.engine_a import ScalpingEngineA
from indodax_bot.engine_b import ExtremeMomentumHunterEngineB
from indodax_bot.indicators import TechnicalIndicators

class TestEngines(unittest.TestCase):
    def setUp(self):
        self.engine_a = ScalpingEngineA()
        self.engine_b = ExtremeMomentumHunterEngineB(min_score_threshold=60.0)

    def _create_bullish_candles(self, n=35):
        bars = []
        base = 1000.0
        for i in range(n):
            close_p = base * (1.0 + (i * 0.005))  # strong upward trend
            open_p = close_p * 0.995
            high_p = close_p * 1.002
            low_p = open_p * 0.998
            vol = 1000.0 * (2.5 if i >= n-3 else 1.0) # volume surge at end
            bars.append({
                "open": open_p, "high": high_p, "low": low_p, "close": close_p, "volume": vol
            })
        return pd.DataFrame(bars)

    def test_engine_a_eval(self):
        df_bullish = self._create_bullish_candles(35)
        mkt_info = {
            "symbol": "BTCIDR",
            "spread_pct": 0.002,
            "trade_fee_percent_taker": 0.002,
            "trade_fee_percent_maker": 0.001
        }
        exec_info = {"slippage_pct": 0.001, "total_available_idr": 10_000_000}

        sig = self.engine_a.evaluate_entry(
            pair_id="btcidr",
            df_1m=df_bullish,
            df_5m=df_bullish,
            df_15m=df_bullish,
            market_info=mkt_info,
            execution_info=exec_info,
            has_open_position=False
        )

        self.assertTrue(sig["valid"])
        self.assertEqual(sig["engine"], "ENGINE_A_SCALPER")
        self.assertGreater(sig["expected_net_return_pct"], 0)

    def test_engine_b_momentum_score(self):
        df_bullish = self._create_bullish_candles(40)

        score_res = TechnicalIndicators.calculate_engine_b_momentum_score(
            df=df_bullish,
            spread_pct=0.002,
            orderbook_depth_idr=10_000_000.0,
            target_position_idr=1_000_000.0
        )

        total_score = score_res["total_score"]
        self.assertGreaterEqual(total_score, 60.0)
        self.assertIn("relative_volume", score_res["components"])

        mkt_info = {"symbol": "BTCIDR", "spread_pct": 0.002, "trade_fee_percent_taker": 0.002}
        exec_info = {"slippage_pct": 0.001, "total_available_idr": 10_000_000}

        sig_b = self.engine_b.evaluate_entry(
            pair_id="btcidr",
            df_15m=df_bullish,
            df_1h=df_bullish,
            market_info=mkt_info,
            execution_info=exec_info,
            target_position_idr=1_000_000.0,
            has_open_position=False
        )

        self.assertTrue(sig_b["valid"])
        self.assertEqual(sig_b["engine"], "ENGINE_B_MOMENTUM_HUNTER")
        self.assertIsNone(sig_b["take_profit_pct"])  # Let winners run per master spec

if __name__ == '__main__':
    unittest.main()
