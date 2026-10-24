"""
Technical Indicators Engine & Momentum Scoring System.
Calculates EMA, ATR, RVOL, ROC, Breakouts, Compression, and Engine B 0-100 Momentum Score.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional

class TechnicalIndicators:
    @staticmethod
    def compute_ema(series: pd.Series, period: int) -> pd.Series:
        """Exponential Moving Average."""
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Average True Range (ATR)."""
        high = df['high']
        low = df['low']
        close = df['close']

        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period, min_periods=1).mean()

    @staticmethod
    def compute_rvol(df: pd.DataFrame, period: int = 20) -> pd.Series:
        """Relative Volume (RVOL) = current volume / rolling SMA of volume."""
        vol_sma = df['volume'].rolling(window=period, min_periods=1).mean()
        # Avoid div by zero
        vol_sma = vol_sma.replace(0, 1.0)
        return df['volume'] / vol_sma

    @staticmethod
    def compute_roc(series: pd.Series, period: int = 12) -> pd.Series:
        """Rate of Change (ROC) in percent."""
        prev = series.shift(period)
        prev = prev.replace(0, np.nan)
        return ((series - prev) / prev) * 100.0

    @staticmethod
    def detect_breakout_retest(df: pd.DataFrame, lookback: int = 20) -> Dict[str, Any]:
        """
        Detects if price recently broke above resistance and is retesting or maintaining breakout.
        """
        if len(df) < lookback + 2:
            return {"is_breakout": False, "is_retest": False, "resistance": 0.0}

        recent_df = df.iloc[-lookback-2:-2]
        resistance = recent_df['high'].max()

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        is_breakout = prev['close'] > resistance or latest['close'] > resistance
        is_retest = (latest['low'] <= resistance * 1.005) and (latest['close'] >= resistance * 0.995)

        breakout_quality = min(1.0, max(0.0, (latest['close'] - resistance) / resistance)) if resistance > 0 else 0.0

        return {
            "is_breakout": is_breakout,
            "is_retest": is_retest,
            "resistance": resistance,
            "breakout_pct": breakout_quality * 100.0
        }

    @staticmethod
    def detect_trend_structure(df: pd.DataFrame, window: int = 5) -> Dict[str, Any]:
        """
        Checks for Higher Highs and Higher Lows (HH & HL).
        """
        if len(df) < window * 3:
            return {"is_uptrend": False, "structure_score": 0.0}

        highs = df['high'].values
        lows = df['low'].values

        # Local peaks and troughs
        p1_high = np.max(highs[-window*3:-window*2])
        p2_high = np.max(highs[-window*2:-window])
        p3_high = np.max(highs[-window:])

        t1_low = np.min(lows[-window*3:-window*2])
        t2_low = np.min(lows[-window*2:-window])
        t3_low = np.min(lows[-window:])

        hh = (p3_high > p2_high) and (p2_high > p1_high)
        hl = (t3_low > t2_low) and (t2_low > t1_low)

        is_uptrend = hh and hl
        structure_score = (1.0 if hh else 0.5) * (1.0 if hl else 0.5)

        return {
            "is_uptrend": is_uptrend,
            "hh": hh,
            "hl": hl,
            "structure_score": structure_score
        }

    @classmethod
    def calculate_engine_b_momentum_score(
        cls,
        df: pd.DataFrame,
        spread_pct: float,
        orderbook_depth_idr: float,
        target_position_idr: float
    ) -> Dict[str, Any]:
        """
        Calculates Engine B Momentum Score (0 - 100 points):
        - Relative Volume: 20 pts
        - Breakout Quality: 20 pts
        - Volatility Expansion: 15 pts
        - Trend Structure: 15 pts
        - Order-book Quality: 15 pts
        - Price Acceleration: 15 pts
        """
        if len(df) < 30:
            return {"total_score": 0.0, "details": "Insufficient candle data"}

        df = df.copy()
        df['ema9'] = cls.compute_ema(df['close'], 9)
        df['ema21'] = cls.compute_ema(df['close'], 21)
        df['atr'] = cls.compute_atr(df)
        df['rvol'] = cls.compute_rvol(df)
        df['roc'] = cls.compute_roc(df['close'], 10)

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # 1. Relative Volume (20 points)
        rvol = float(latest['rvol'])
        if rvol >= 3.0:
            pts_rvol = 20.0
        elif rvol >= 2.0:
            pts_rvol = 15.0 + (rvol - 2.0) * 5.0
        elif rvol >= 1.2:
            pts_rvol = 10.0 + (rvol - 1.2) * 6.25
        else:
            pts_rvol = max(0.0, rvol * 8.0)

        # 2. Breakout Quality (20 points)
        breakout_info = cls.detect_breakout_retest(df, lookback=20)
        pts_breakout = 0.0
        if breakout_info["is_breakout"]:
            pts_breakout += 15.0
            if breakout_info["is_retest"] or latest['close'] > prev['high']:
                pts_breakout += 5.0
        elif latest['close'] > df['high'].iloc[-10:].max() * 0.995:
            pts_breakout = 10.0

        # 3. Volatility Expansion (15 points)
        # Ratio of current ATR to 20-period ATR SMA
        atr_sma = df['atr'].rolling(window=20, min_periods=1).mean().iloc[-1]
        atr_ratio = float(latest['atr']) / atr_sma if atr_sma > 0 else 1.0
        if atr_ratio >= 1.8:
            pts_volatility = 15.0
        elif atr_ratio >= 1.2:
            pts_volatility = 10.0 + (atr_ratio - 1.2) * 8.33
        else:
            pts_volatility = max(0.0, atr_ratio * 7.5)

        # 4. Trend Structure (15 points)
        trend_info = cls.detect_trend_structure(df)
        pts_trend = trend_info["structure_score"] * 15.0
        if latest['ema9'] > latest['ema21']:
            pts_trend = min(15.0, pts_trend + 3.0)

        # 5. Order-book Quality (15 points)
        # Tight spread (<0.5%) and sufficient depth (>2x target size)
        pts_ob = 0.0
        if spread_pct <= 0.003:  # <= 0.3%
            pts_ob += 7.5
        elif spread_pct <= 0.008: # <= 0.8%
            pts_ob += 5.0
        else:
            pts_ob += max(0.0, 7.5 * (1.0 - spread_pct / 0.02))

        depth_ratio = orderbook_depth_idr / max(1.0, target_position_idr)
        if depth_ratio >= 3.0:
            pts_ob += 7.5
        elif depth_ratio >= 1.0:
            pts_ob += 3.75
        else:
            pts_ob += max(0.0, depth_ratio * 3.75)

        # 6. Price Acceleration (15 points)
        roc = float(latest['roc'])
        if roc >= 5.0:  # +5% ROC
            pts_accel = 15.0
        elif roc >= 2.0:
            pts_accel = 10.0 + (roc - 2.0) * 1.66
        elif roc > 0:
            pts_accel = roc * 5.0
        else:
            pts_accel = 0.0

        total_score = round(
            min(100.0, pts_rvol + pts_breakout + pts_volatility + pts_trend + pts_ob + pts_accel),
            1
        )

        return {
            "total_score": total_score,
            "components": {
                "relative_volume": round(pts_rvol, 1),
                "breakout_quality": round(pts_breakout, 1),
                "volatility_expansion": round(pts_volatility, 1),
                "trend_structure": round(pts_trend, 1),
                "orderbook_quality": round(pts_ob, 1),
                "price_acceleration": round(pts_accel, 1)
            },
            "metrics": {
                "rvol": round(rvol, 2),
                "roc_pct": round(roc, 2),
                "atr_ratio": round(atr_ratio, 2),
                "spread_pct": round(spread_pct * 100.0, 2)
            }
        }
