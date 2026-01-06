"""
Support and Resistance Indicators.

These indicators identify key price levels where buying or selling
pressure is likely to emerge.
"""

import numpy as np
import pandas as pd

from live_tracker.indicators.base import BaseIndicator, IndicatorResult, IndicatorSignal


class PivotPoints(BaseIndicator):
    """
    Pivot Points.

    Classic floor trader pivot points. Calculates support and resistance
    levels based on prior period's high, low, and close.

    Hedge Fund Usage:
    - Pivot (P): Key psychological level
    - R1, R2, R3: Resistance levels for profit targets
    - S1, S2, S3: Support levels for stop-loss and entries
    - Price reaction at pivots confirms level strength
    """

    def __init__(self, method: str = "classic"):
        """
        Initialize Pivot Points.

        Args:
            method: Pivot calculation method ('classic', 'fibonacci', 'camarilla')
        """
        super().__init__(f"Pivot Points ({method})")
        self.method = method

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Pivot Points."""
        self.validate_data(df, ["high", "low", "close"])
        df = df.copy()

        # Use previous period's values
        prev_high = df["high"].shift(1)
        prev_low = df["low"].shift(1)
        prev_close = df["close"].shift(1)

        # Pivot Point
        pivot = (prev_high + prev_low + prev_close) / 3

        if self.method == "classic":
            df["pivot"] = pivot
            df["r1"] = (2 * pivot) - prev_low
            df["s1"] = (2 * pivot) - prev_high
            df["r2"] = pivot + (prev_high - prev_low)
            df["s2"] = pivot - (prev_high - prev_low)
            df["r3"] = prev_high + 2 * (pivot - prev_low)
            df["s3"] = prev_low - 2 * (prev_high - pivot)

        elif self.method == "fibonacci":
            range_hl = prev_high - prev_low
            df["pivot"] = pivot
            df["r1"] = pivot + 0.382 * range_hl
            df["s1"] = pivot - 0.382 * range_hl
            df["r2"] = pivot + 0.618 * range_hl
            df["s2"] = pivot - 0.618 * range_hl
            df["r3"] = pivot + 1.000 * range_hl
            df["s3"] = pivot - 1.000 * range_hl

        elif self.method == "camarilla":
            range_hl = prev_high - prev_low
            df["pivot"] = pivot
            df["r1"] = prev_close + range_hl * 1.1 / 12
            df["s1"] = prev_close - range_hl * 1.1 / 12
            df["r2"] = prev_close + range_hl * 1.1 / 6
            df["s2"] = prev_close - range_hl * 1.1 / 6
            df["r3"] = prev_close + range_hl * 1.1 / 4
            df["s3"] = prev_close - range_hl * 1.1 / 4

        return df

    def get_signal(self, df: pd.DataFrame) -> IndicatorResult:
        """Generate trading signal from Pivot Points."""
        if "pivot" not in df.columns:
            df = self.calculate(df)

        price = df["close"].iloc[-1]
        pivot = df["pivot"].iloc[-1]
        r1 = df["r1"].iloc[-1]
        r2 = df["r2"].iloc[-1]
        s1 = df["s1"].iloc[-1]
        s2 = df["s2"].iloc[-1]

        prev_price = df["close"].iloc[-2] if len(df) > 1 else price

        # Determine position relative to pivots
        tolerance = (r1 - s1) * 0.02  # 2% of range

        # Check for breakouts or tests
        if price > r2:
            signal = IndicatorSignal.STRONG_BUY
            desc = f"Price above R2 ({r2:.2f}) - strong bullish breakout"
            confidence = 0.75
        elif price < s2:
            signal = IndicatorSignal.STRONG_SELL
            desc = f"Price below S2 ({s2:.2f}) - strong bearish breakdown"
            confidence = 0.75
        elif abs(price - s1) < tolerance and price > s1:
            signal = IndicatorSignal.BUY
            desc = f"Price bouncing off S1 support ({s1:.2f})"
            confidence = 0.7
        elif abs(price - r1) < tolerance and price < r1:
            signal = IndicatorSignal.SELL
            desc = f"Price rejected at R1 resistance ({r1:.2f})"
            confidence = 0.7
        elif prev_price <= pivot and price > pivot:
            signal = IndicatorSignal.BUY
            desc = f"Price crossed above pivot ({pivot:.2f})"
            confidence = 0.65
        elif prev_price >= pivot and price < pivot:
            signal = IndicatorSignal.SELL
            desc = f"Price crossed below pivot ({pivot:.2f})"
            confidence = 0.65
        elif price > pivot:
            signal = IndicatorSignal.BUY
            desc = f"Price above pivot ({pivot:.2f}), targeting R1={r1:.2f}"
            confidence = 0.55
        elif price < pivot:
            signal = IndicatorSignal.SELL
            desc = f"Price below pivot ({pivot:.2f}), targeting S1={s1:.2f}"
            confidence = 0.55
        else:
            signal = IndicatorSignal.NEUTRAL
            desc = f"Price at pivot ({pivot:.2f})"
            confidence = 0.5

        return IndicatorResult(
            name=self.name,
            value=pivot,
            signal=signal,
            description=desc,
            confidence=confidence,
        )


class FibonacciLevels(BaseIndicator):
    """
    Fibonacci Retracement and Extension Levels.

    Calculates key Fibonacci ratios from swing high/low to identify
    potential support, resistance, and price targets.

    Hedge Fund Usage:
    - 38.2%: Shallow retracement in strong trends
    - 50.0%: Psychological midpoint
    - 61.8%: Golden ratio, key reversal level
    - 78.6%: Deep retracement, last defense before trend break
    - Extensions (1.272, 1.618): Profit targets
    """

    def __init__(self, lookback: int = 50):
        super().__init__("Fibonacci Levels")
        self.lookback = lookback
        self.fib_levels = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
        self.extension_levels = [1.272, 1.618, 2.0, 2.618]

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Fibonacci Levels."""
        self.validate_data(df, ["high", "low", "close"])
        df = df.copy()

        # Find swing high and low in lookback period
        recent = df.tail(self.lookback)
        swing_high = recent["high"].max()
        swing_low = recent["low"].min()

        # Determine trend direction
        high_idx = recent["high"].idxmax()
        low_idx = recent["low"].idxmin()

        # Get integer positions for comparison
        high_pos = df.index.get_loc(high_idx)
        low_pos = df.index.get_loc(low_idx)

        uptrend = low_pos < high_pos  # Low came before high = uptrend

        price_range = swing_high - swing_low

        if uptrend:
            # In uptrend, retracement levels are from high going down
            for level in self.fib_levels:
                df[f"fib_{int(level*100)}"] = swing_high - (price_range * level)
            for level in self.extension_levels:
                df[f"fib_ext_{int(level*100)}"] = swing_high + (price_range * (level - 1))
        else:
            # In downtrend, retracement levels are from low going up
            for level in self.fib_levels:
                df[f"fib_{int(level*100)}"] = swing_low + (price_range * level)
            for level in self.extension_levels:
                df[f"fib_ext_{int(level*100)}"] = swing_low - (price_range * (level - 1))

        df["fib_trend"] = 1 if uptrend else -1
        df["fib_high"] = swing_high
        df["fib_low"] = swing_low

        return df

    def get_signal(self, df: pd.DataFrame) -> IndicatorResult:
        """Generate trading signal from Fibonacci Levels."""
        if "fib_38" not in df.columns:
            df = self.calculate(df)

        price = df["close"].iloc[-1]
        fib_trend = df["fib_trend"].iloc[-1]
        fib_38 = df["fib_38"].iloc[-1]
        fib_50 = df["fib_50"].iloc[-1]
        fib_61 = df["fib_61"].iloc[-1]
        fib_78 = df["fib_78"].iloc[-1]

        tolerance = abs(fib_61 - fib_50) * 0.1  # 10% of level spacing

        # Check proximity to key levels
        near_38 = abs(price - fib_38) < tolerance
        near_50 = abs(price - fib_50) < tolerance
        near_61 = abs(price - fib_61) < tolerance
        near_78 = abs(price - fib_78) < tolerance

        if fib_trend == 1:  # Uptrend - buying retracements
            if near_61:
                signal = IndicatorSignal.STRONG_BUY
                desc = f"Price at 61.8% Fibonacci support ({fib_61:.2f}) - golden ratio"
                confidence = 0.8
            elif near_50:
                signal = IndicatorSignal.BUY
                desc = f"Price at 50% Fibonacci support ({fib_50:.2f})"
                confidence = 0.7
            elif near_38:
                signal = IndicatorSignal.BUY
                desc = f"Price at 38.2% Fibonacci support ({fib_38:.2f})"
                confidence = 0.65
            elif near_78:
                signal = IndicatorSignal.BUY
                desc = f"Price at 78.6% Fibonacci - deep retracement ({fib_78:.2f})"
                confidence = 0.6
            elif price > fib_38:
                signal = IndicatorSignal.BUY
                desc = f"Price above 38.2% Fib - healthy uptrend"
                confidence = 0.55
            else:
                signal = IndicatorSignal.NEUTRAL
                desc = f"Price in Fibonacci retracement zone"
                confidence = 0.5
        else:  # Downtrend - selling retracements
            if near_61:
                signal = IndicatorSignal.STRONG_SELL
                desc = f"Price at 61.8% Fibonacci resistance ({fib_61:.2f}) - golden ratio"
                confidence = 0.8
            elif near_50:
                signal = IndicatorSignal.SELL
                desc = f"Price at 50% Fibonacci resistance ({fib_50:.2f})"
                confidence = 0.7
            elif near_38:
                signal = IndicatorSignal.SELL
                desc = f"Price at 38.2% Fibonacci resistance ({fib_38:.2f})"
                confidence = 0.65
            elif near_78:
                signal = IndicatorSignal.SELL
                desc = f"Price at 78.6% Fibonacci - deep retracement ({fib_78:.2f})"
                confidence = 0.6
            elif price < fib_38:
                signal = IndicatorSignal.SELL
                desc = f"Price below 38.2% Fib - healthy downtrend"
                confidence = 0.55
            else:
                signal = IndicatorSignal.NEUTRAL
                desc = f"Price in Fibonacci retracement zone"
                confidence = 0.5

        return IndicatorResult(
            name=self.name,
            value=fib_61,  # Return golden ratio as primary value
            signal=signal,
            description=desc,
            confidence=confidence,
        )
