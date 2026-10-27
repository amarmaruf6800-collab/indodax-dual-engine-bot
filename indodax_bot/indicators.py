"""
Technical Indicators Engine, Market Regime Detector & False Breakout Filter for V6.1-MACO R11.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional

class MarketRegimeDetector:
    """
    Section 3: Classifies asset condition into 7 distinct market regimes.
    """
    SIDEWAYS_LOW_VOLATILITY = "SIDEWAYS_LOW_VOLATILITY"
    NORMAL_TREND = "NORMAL_TREND"
    BULLISH_MOMENTUM = "BULLISH_MOMENTUM"
    EXTREME_MOMENTUM_BREAKOUT = "EXTREME_MOMENTUM_BREAKOUT"
    OVEREXTENDED_PUMP_EXHAUSTION = "OVEREXTENDED_PUMP_EXHAUSTION"
    BEARISH_HIGH_RISK = "BEARISH_HIGH_RISK"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

    @classmethod
    def classify_regime(cls, df: pd.DataFrame, spread_pct: float = 0.003) -> Dict[str, Any]:
        if len(df) < 25:
            return {"regime": cls.INSUFFICIENT_DATA, "reason": "Insufficient candle history (<25)"}

        df = df.copy()
        df['ema9'] = TechnicalIndicators.compute_ema(df['close'], 9)
        df['ema21'] = TechnicalIndicators.compute_ema(df['close'], 21)
        df['ema50'] = TechnicalIndicators.compute_ema(df['close'], 50)
        df['atr'] = TechnicalIndicators.compute_atr(df, 14)
        df['rvol'] = TechnicalIndicators.compute_rvol(df, 20)
        df['roc'] = TechnicalIndicators.compute_roc(df['close'], 10)

        latest = df.iloc[-1]
        price = float(latest['close'])
        rvol = float(latest['rvol'])
        roc = float(latest['roc'])
        ema9 = float(latest['ema9'])
        ema21 = float(latest['ema21'])
        ema50 = float(latest['ema50'])
        atr = float(latest['atr'])

        atr_sma = df['atr'].rolling(window=20, min_periods=1).mean().iloc[-1]
        atr_ratio = (atr / atr_sma) if atr_sma > 0 else 1.0

        # Check Overextended / Pump Exhaustion
        dist_from_ema50 = (price - ema50) / ema50 if ema50 > 0 else 0.0
        candle_range = max(1e-8, float(latest['high'] - latest['low']))
        upper_wick = float(latest['high'] - max(latest['open'], latest['close']))
        wick_ratio = upper_wick / candle_range

        if dist_from_ema50 > 0.08 and wick_ratio > 0.40 and roc > 5.0:
            return {
                "regime": cls.OVEREXTENDED_PUMP_EXHAUSTION,
                "reason": f"Price {dist_from_ema50*100:.1f}% above EMA50 with upper wick rejection ({wick_ratio*100:.0f}%)",
                "metrics": {"dist_from_ema50": dist_from_ema50, "wick_ratio": wick_ratio}
            }

        # Check Bearish High Risk
        if ema9 < ema21 < ema50 or roc < -3.0:
            return {
                "regime": cls.BEARISH_HIGH_RISK,
                "reason": f"Bearish EMA alignment (EMA9<21<50) or sharp drop (ROC={roc:.1f}%)",
                "metrics": {"roc_pct": roc}
            }

        # Check Extreme Momentum Breakout
        breakout_info = TechnicalIndicators.detect_breakout_retest(df, lookback=20)
        if breakout_info["is_breakout"] and rvol >= 1.8 and atr_ratio >= 1.3:
            return {
                "regime": cls.EXTREME_MOMENTUM_BREAKOUT,
                "reason": f"Confirmed Breakout with RVOL={rvol:.1f} & ATR expansion ratio {atr_ratio:.2f}",
                "metrics": {"rvol": rvol, "atr_ratio": atr_ratio, "breakout_info": breakout_info}
            }

        # Check Bullish Momentum
        if ema9 > ema21 and rvol >= 1.2 and roc >= 0.3:
            return {
                "regime": cls.BULLISH_MOMENTUM,
                "reason": f"Bullish EMA alignment (EMA9>21) with RVOL={rvol:.1f} & ROC={roc:.1f}%",
                "metrics": {"rvol": rvol, "roc_pct": roc}
            }

        # Check Sideways / Low Volatility
        if atr_ratio < 0.85 or (abs(roc) < 0.3 and rvol < 1.0):
            return {
                "regime": cls.SIDEWAYS_LOW_VOLATILITY,
                "reason": f"Low volatility (ATR ratio={atr_ratio:.2f}, ROC={roc:.1f}%)",
                "metrics": {"atr_ratio": atr_ratio, "rvol": rvol}
            }

        return {
            "regime": cls.NORMAL_TREND,
            "reason": "Orderly market trend without extreme momentum",
            "metrics": {"rvol": rvol, "roc_pct": roc}
        }


class FalseBreakoutFilter:
    """
    Section 4.F: False Breakout Filter to protect capital against fakeouts.
    """
    @staticmethod
    def evaluate_breakout(df: pd.DataFrame, spread_pct: float, slippage_pct: float) -> Dict[str, Any]:
        if len(df) < 25:
            return {"is_valid": False, "reason": "Insufficient candles for breakout evaluation"}

        latest = df.iloc[-1]
        candle_range = max(1e-8, float(latest['high'] - latest['low']))
        upper_wick = float(latest['high'] - max(latest['open'], latest['close']))
        wick_ratio = upper_wick / candle_range

        # 1. Wick Rejection Filter
        if wick_ratio > 0.40:
            return {
                "is_valid": False,
                "reason": f"Upper wick rejection ({wick_ratio*100:.1f}% > 40%) indicates sell pressure at resistance"
            }

        # 2. Breakout Level Verification
        breakout_info = TechnicalIndicators.detect_breakout_retest(df, lookback=20)
        resistance = breakout_info.get("resistance", 0.0)
        price = float(latest['close'])

        if resistance > 0 and price > resistance * 1.05:
            return {
                "is_valid": False,
                "reason": f"Price is overextended ({((price - resistance)/resistance)*100:.1f}% > 5%) above broken resistance"
            }

        # 3. Volume Surge Filter
        rvol = TechnicalIndicators.compute_rvol(df).iloc[-1]
        if rvol < 1.1:
            return {
                "is_valid": False,
                "reason": f"Insufficient relative volume surge (RVOL {rvol:.2f} < 1.1) on breakout"
            }

        # 4. Spread & Execution Filter
        if spread_pct > 0.005:
            return {
                "is_valid": False,
                "reason": f"Excessive spread ({spread_pct*100:.2f}% > 0.5%) threatens breakout net expectancy"
            }

        return {
            "is_valid": True,
            "reason": f"Valid breakout: RVOL={rvol:.1f}, low wick rejection ({wick_ratio*100:.0f}%), tight spread",
            "resistance": resistance
        }


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
        """Detects if price recently broke above resistance and is retesting or maintaining breakout."""
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
        """Checks for Higher Highs and Higher Lows (HH & HL)."""
        if len(df) < window * 3:
            return {"is_uptrend": False, "structure_score": 0.0}

        highs = df['high'].values
        lows = df['low'].values

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
        pts_ob = 0.0
        if spread_pct <= 0.003:
            pts_ob += 7.5
        elif spread_pct <= 0.008:
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
        if roc >= 5.0:
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
