"""
Momentum Indicators.

These indicators measure the rate of change in price, helping identify
overbought/oversold conditions and potential trend reversals.
"""

import numpy as np
import pandas as pd

from live_tracker.indicators.base import BaseIndicator, IndicatorResult, IndicatorSignal


class RSI(BaseIndicator):
    """
    Relative Strength Index (RSI).

    The RSI is a momentum oscillator that measures the speed and magnitude
    of recent price changes. Values range from 0-100.

    Hedge Fund Usage:
    - RSI < 30: Oversold territory, potential buy signal
    - RSI > 70: Overbought territory, potential sell signal
    - Divergence between RSI and price is a strong reversal signal
    - RSI crossing 50 indicates momentum shift
    """

    def __init__(self, period: int = 14, overbought: float = 70, oversold: float = 30):
        super().__init__("RSI")
        self.period = period
        self.overbought = overbought
        self.oversold = oversold

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate RSI values."""
        self.validate_data(df, ["close"])
        df = df.copy()

        # Calculate price changes
        delta = df["close"].diff()

        # Separate gains and losses
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        # Calculate average gain and loss using Wilder's smoothing
        avg_gain = gain.ewm(alpha=1 / self.period, min_periods=self.period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / self.period, min_periods=self.period, adjust=False).mean()

        # Calculate RS and RSI
        rs = self.safe_divide(avg_gain.values, avg_loss.values)
        df["rsi"] = 100 - (100 / (1 + rs))

        return df

    def get_signal(self, df: pd.DataFrame) -> IndicatorResult:
        """Generate trading signal from RSI."""
        if "rsi" not in df.columns:
            df = self.calculate(df)

        current_rsi = df["rsi"].iloc[-1]
        prev_rsi = df["rsi"].iloc[-2] if len(df) > 1 else current_rsi

        # Determine signal based on RSI levels and momentum
        if current_rsi <= self.oversold:
            if current_rsi < 20:  # Extremely oversold
                signal = IndicatorSignal.STRONG_BUY
                desc = f"RSI extremely oversold at {current_rsi:.1f}"
                confidence = 0.85
            else:
                signal = IndicatorSignal.BUY
                desc = f"RSI oversold at {current_rsi:.1f}"
                confidence = 0.7
        elif current_rsi >= self.overbought:
            if current_rsi > 80:  # Extremely overbought
                signal = IndicatorSignal.STRONG_SELL
                desc = f"RSI extremely overbought at {current_rsi:.1f}"
                confidence = 0.85
            else:
                signal = IndicatorSignal.SELL
                desc = f"RSI overbought at {current_rsi:.1f}"
                confidence = 0.7
        elif current_rsi > 50 and prev_rsi <= 50:
            signal = IndicatorSignal.BUY
            desc = f"RSI crossed above 50 ({current_rsi:.1f}), bullish momentum"
            confidence = 0.55
        elif current_rsi < 50 and prev_rsi >= 50:
            signal = IndicatorSignal.SELL
            desc = f"RSI crossed below 50 ({current_rsi:.1f}), bearish momentum"
            confidence = 0.55
        else:
            signal = IndicatorSignal.NEUTRAL
            desc = f"RSI neutral at {current_rsi:.1f}"
            confidence = 0.5

        return IndicatorResult(
            name=self.name,
            value=current_rsi,
            signal=signal,
            description=desc,
            confidence=confidence,
        )


class Stochastic(BaseIndicator):
    """
    Stochastic Oscillator.

    Compares closing price to price range over a period. The %K line
    and %D (signal) line crossovers generate trading signals.

    Hedge Fund Usage:
    - %K < 20 with %K crossing above %D: Strong buy signal
    - %K > 80 with %K crossing below %D: Strong sell signal
    - Divergence with price indicates potential reversal
    """

    def __init__(
        self,
        k_period: int = 14,
        d_period: int = 3,
        smooth_k: int = 3,
        overbought: float = 80,
        oversold: float = 20,
    ):
        super().__init__("Stochastic")
        self.k_period = k_period
        self.d_period = d_period
        self.smooth_k = smooth_k
        self.overbought = overbought
        self.oversold = oversold

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Stochastic %K and %D values."""
        self.validate_data(df, ["high", "low", "close"])
        df = df.copy()

        # Calculate highest high and lowest low over the period
        lowest_low = df["low"].rolling(window=self.k_period).min()
        highest_high = df["high"].rolling(window=self.k_period).max()

        # Calculate raw %K
        range_hl = highest_high - lowest_low
        raw_k = self.safe_divide(
            (df["close"] - lowest_low).values,
            range_hl.values
        ) * 100

        # Smooth %K (Fast Stochastic becomes Slow Stochastic)
        df["stoch_k"] = pd.Series(raw_k, index=df.index).rolling(window=self.smooth_k).mean()

        # Calculate %D (Signal line)
        df["stoch_d"] = df["stoch_k"].rolling(window=self.d_period).mean()

        return df

    def get_signal(self, df: pd.DataFrame) -> IndicatorResult:
        """Generate trading signal from Stochastic."""
        if "stoch_k" not in df.columns:
            df = self.calculate(df)

        k = df["stoch_k"].iloc[-1]
        d = df["stoch_d"].iloc[-1]
        prev_k = df["stoch_k"].iloc[-2] if len(df) > 1 else k
        prev_d = df["stoch_d"].iloc[-2] if len(df) > 1 else d

        # Check for crossovers
        bullish_cross = prev_k <= prev_d and k > d
        bearish_cross = prev_k >= prev_d and k < d

        if k <= self.oversold and bullish_cross:
            signal = IndicatorSignal.STRONG_BUY
            desc = f"Stochastic bullish crossover in oversold zone (%K={k:.1f})"
            confidence = 0.8
        elif k >= self.overbought and bearish_cross:
            signal = IndicatorSignal.STRONG_SELL
            desc = f"Stochastic bearish crossover in overbought zone (%K={k:.1f})"
            confidence = 0.8
        elif bullish_cross:
            signal = IndicatorSignal.BUY
            desc = f"Stochastic bullish crossover (%K={k:.1f})"
            confidence = 0.6
        elif bearish_cross:
            signal = IndicatorSignal.SELL
            desc = f"Stochastic bearish crossover (%K={k:.1f})"
            confidence = 0.6
        elif k <= self.oversold:
            signal = IndicatorSignal.BUY
            desc = f"Stochastic oversold (%K={k:.1f})"
            confidence = 0.55
        elif k >= self.overbought:
            signal = IndicatorSignal.SELL
            desc = f"Stochastic overbought (%K={k:.1f})"
            confidence = 0.55
        else:
            signal = IndicatorSignal.NEUTRAL
            desc = f"Stochastic neutral (%K={k:.1f}, %D={d:.1f})"
            confidence = 0.5

        return IndicatorResult(
            name=self.name,
            value=k,
            signal=signal,
            description=desc,
            confidence=confidence,
        )


class WilliamsR(BaseIndicator):
    """
    Williams %R (Williams Percent Range).

    Similar to Stochastic but inverted. Ranges from -100 to 0.

    Hedge Fund Usage:
    - %R < -80: Oversold, potential buy
    - %R > -20: Overbought, potential sell
    - Quick indicator for short-term reversals
    """

    def __init__(self, period: int = 14, overbought: float = -20, oversold: float = -80):
        super().__init__("Williams %R")
        self.period = period
        self.overbought = overbought
        self.oversold = oversold

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Williams %R values."""
        self.validate_data(df, ["high", "low", "close"])
        df = df.copy()

        highest_high = df["high"].rolling(window=self.period).max()
        lowest_low = df["low"].rolling(window=self.period).min()

        range_hl = highest_high - lowest_low
        df["williams_r"] = self.safe_divide(
            (highest_high - df["close"]).values,
            range_hl.values
        ) * -100

        return df

    def get_signal(self, df: pd.DataFrame) -> IndicatorResult:
        """Generate trading signal from Williams %R."""
        if "williams_r" not in df.columns:
            df = self.calculate(df)

        wr = df["williams_r"].iloc[-1]
        prev_wr = df["williams_r"].iloc[-2] if len(df) > 1 else wr

        # Check for reversals from extreme levels
        if wr <= self.oversold:
            if prev_wr < wr:  # Turning up from oversold
                signal = IndicatorSignal.STRONG_BUY
                desc = f"Williams %R reversing from oversold ({wr:.1f})"
                confidence = 0.75
            else:
                signal = IndicatorSignal.BUY
                desc = f"Williams %R oversold ({wr:.1f})"
                confidence = 0.6
        elif wr >= self.overbought:
            if prev_wr > wr:  # Turning down from overbought
                signal = IndicatorSignal.STRONG_SELL
                desc = f"Williams %R reversing from overbought ({wr:.1f})"
                confidence = 0.75
            else:
                signal = IndicatorSignal.SELL
                desc = f"Williams %R overbought ({wr:.1f})"
                confidence = 0.6
        else:
            signal = IndicatorSignal.NEUTRAL
            desc = f"Williams %R neutral ({wr:.1f})"
            confidence = 0.5

        return IndicatorResult(
            name=self.name,
            value=wr,
            signal=signal,
            description=desc,
            confidence=confidence,
        )
