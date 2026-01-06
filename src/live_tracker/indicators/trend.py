"""
Trend Indicators.

These indicators help identify the direction and strength of market trends,
which is crucial for trend-following strategies.
"""

import numpy as np
import pandas as pd

from live_tracker.indicators.base import BaseIndicator, IndicatorResult, IndicatorSignal


class SMA(BaseIndicator):
    """
    Simple Moving Average.

    The average price over a specified period. Used for trend identification
    and as dynamic support/resistance levels.

    Hedge Fund Usage:
    - Price above SMA: Bullish trend
    - Price below SMA: Bearish trend
    - SMA crossovers (e.g., 50/200) are key trend signals
    """

    def __init__(self, period: int = 20, column: str = "close"):
        super().__init__(f"SMA({period})")
        self.period = period
        self.column = column
        self.col_name = f"sma_{period}"

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate SMA values."""
        self.validate_data(df, [self.column])
        df = df.copy()
        df[self.col_name] = df[self.column].rolling(window=self.period).mean()
        return df

    def get_signal(self, df: pd.DataFrame) -> IndicatorResult:
        """Generate trading signal from SMA."""
        if self.col_name not in df.columns:
            df = self.calculate(df)

        price = df["close"].iloc[-1]
        sma = df[self.col_name].iloc[-1]
        prev_price = df["close"].iloc[-2] if len(df) > 1 else price
        prev_sma = df[self.col_name].iloc[-2] if len(df) > 1 else sma

        # Calculate distance from SMA as percentage
        distance_pct = ((price - sma) / sma) * 100

        # Check for crossovers
        bullish_cross = prev_price <= prev_sma and price > sma
        bearish_cross = prev_price >= prev_sma and price < sma

        if bullish_cross:
            signal = IndicatorSignal.BUY
            desc = f"Price crossed above {self.col_name.upper()}"
            confidence = 0.65
        elif bearish_cross:
            signal = IndicatorSignal.SELL
            desc = f"Price crossed below {self.col_name.upper()}"
            confidence = 0.65
        elif price > sma:
            signal = IndicatorSignal.BUY
            desc = f"Price {distance_pct:.1f}% above {self.col_name.upper()}"
            confidence = 0.55
        elif price < sma:
            signal = IndicatorSignal.SELL
            desc = f"Price {abs(distance_pct):.1f}% below {self.col_name.upper()}"
            confidence = 0.55
        else:
            signal = IndicatorSignal.NEUTRAL
            desc = f"Price at {self.col_name.upper()}"
            confidence = 0.5

        return IndicatorResult(
            name=self.name,
            value=sma,
            signal=signal,
            description=desc,
            confidence=confidence,
        )


class EMA(BaseIndicator):
    """
    Exponential Moving Average.

    Gives more weight to recent prices, making it more responsive
    than SMA to price changes.

    Hedge Fund Usage:
    - EMA responds faster to price changes than SMA
    - 8/21 EMA crossover for short-term trends
    - 12/26 EMA used in MACD calculation
    - 50/200 EMA for major trend identification
    """

    def __init__(self, period: int = 20, column: str = "close"):
        super().__init__(f"EMA({period})")
        self.period = period
        self.column = column
        self.col_name = f"ema_{period}"

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate EMA values."""
        self.validate_data(df, [self.column])
        df = df.copy()
        df[self.col_name] = df[self.column].ewm(span=self.period, adjust=False).mean()
        return df

    def get_signal(self, df: pd.DataFrame) -> IndicatorResult:
        """Generate trading signal from EMA."""
        if self.col_name not in df.columns:
            df = self.calculate(df)

        price = df["close"].iloc[-1]
        ema = df[self.col_name].iloc[-1]
        prev_price = df["close"].iloc[-2] if len(df) > 1 else price
        prev_ema = df[self.col_name].iloc[-2] if len(df) > 1 else ema

        distance_pct = ((price - ema) / ema) * 100
        bullish_cross = prev_price <= prev_ema and price > ema
        bearish_cross = prev_price >= prev_ema and price < ema

        if bullish_cross:
            signal = IndicatorSignal.BUY
            desc = f"Price crossed above {self.col_name.upper()}"
            confidence = 0.7
        elif bearish_cross:
            signal = IndicatorSignal.SELL
            desc = f"Price crossed below {self.col_name.upper()}"
            confidence = 0.7
        elif price > ema:
            signal = IndicatorSignal.BUY
            desc = f"Price {distance_pct:.1f}% above {self.col_name.upper()}"
            confidence = 0.55
        elif price < ema:
            signal = IndicatorSignal.SELL
            desc = f"Price {abs(distance_pct):.1f}% below {self.col_name.upper()}"
            confidence = 0.55
        else:
            signal = IndicatorSignal.NEUTRAL
            desc = f"Price at {self.col_name.upper()}"
            confidence = 0.5

        return IndicatorResult(
            name=self.name,
            value=ema,
            signal=signal,
            description=desc,
            confidence=confidence,
        )


class MACD(BaseIndicator):
    """
    Moving Average Convergence Divergence (MACD).

    One of the most reliable trend-following momentum indicators.
    Consists of MACD line, Signal line, and Histogram.

    Hedge Fund Usage:
    - MACD crossing above Signal: Bullish signal
    - MACD crossing below Signal: Bearish signal
    - Histogram expansion: Trend strengthening
    - Divergence with price: Potential reversal
    - Zero line crossover: Major trend change
    """

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        super().__init__("MACD")
        self.fast = fast
        self.slow = slow
        self.signal_period = signal

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate MACD, Signal, and Histogram."""
        self.validate_data(df, ["close"])
        df = df.copy()

        # Calculate EMAs
        ema_fast = df["close"].ewm(span=self.fast, adjust=False).mean()
        ema_slow = df["close"].ewm(span=self.slow, adjust=False).mean()

        # MACD Line = Fast EMA - Slow EMA
        df["macd"] = ema_fast - ema_slow

        # Signal Line = EMA of MACD
        df["macd_signal"] = df["macd"].ewm(span=self.signal_period, adjust=False).mean()

        # Histogram = MACD - Signal
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        return df

    def get_signal(self, df: pd.DataFrame) -> IndicatorResult:
        """Generate trading signal from MACD."""
        if "macd" not in df.columns:
            df = self.calculate(df)

        macd = df["macd"].iloc[-1]
        signal_line = df["macd_signal"].iloc[-1]
        histogram = df["macd_hist"].iloc[-1]
        prev_macd = df["macd"].iloc[-2] if len(df) > 1 else macd
        prev_signal = df["macd_signal"].iloc[-2] if len(df) > 1 else signal_line
        prev_hist = df["macd_hist"].iloc[-2] if len(df) > 1 else histogram

        # Check for crossovers
        bullish_cross = prev_macd <= prev_signal and macd > signal_line
        bearish_cross = prev_macd >= prev_signal and macd < signal_line

        # Check for zero line crossover
        zero_cross_up = prev_macd <= 0 and macd > 0
        zero_cross_down = prev_macd >= 0 and macd < 0

        # Check histogram momentum
        hist_expanding = abs(histogram) > abs(prev_hist)

        if bullish_cross and macd < 0:
            # Bullish crossover below zero - strong reversal signal
            signal = IndicatorSignal.STRONG_BUY
            desc = "MACD bullish crossover below zero line"
            confidence = 0.8
        elif bullish_cross:
            signal = IndicatorSignal.BUY
            desc = "MACD bullish crossover"
            confidence = 0.7
        elif bearish_cross and macd > 0:
            # Bearish crossover above zero - strong reversal signal
            signal = IndicatorSignal.STRONG_SELL
            desc = "MACD bearish crossover above zero line"
            confidence = 0.8
        elif bearish_cross:
            signal = IndicatorSignal.SELL
            desc = "MACD bearish crossover"
            confidence = 0.7
        elif zero_cross_up:
            signal = IndicatorSignal.STRONG_BUY
            desc = "MACD crossed above zero line"
            confidence = 0.75
        elif zero_cross_down:
            signal = IndicatorSignal.STRONG_SELL
            desc = "MACD crossed below zero line"
            confidence = 0.75
        elif histogram > 0 and hist_expanding:
            signal = IndicatorSignal.BUY
            desc = f"MACD histogram expanding bullish ({histogram:.4f})"
            confidence = 0.6
        elif histogram < 0 and hist_expanding:
            signal = IndicatorSignal.SELL
            desc = f"MACD histogram expanding bearish ({histogram:.4f})"
            confidence = 0.6
        else:
            signal = IndicatorSignal.NEUTRAL
            desc = f"MACD neutral (Hist: {histogram:.4f})"
            confidence = 0.5

        return IndicatorResult(
            name=self.name,
            value=macd,
            signal=signal,
            description=desc,
            confidence=confidence,
        )


class ADX(BaseIndicator):
    """
    Average Directional Index (ADX).

    Measures trend strength regardless of direction. +DI and -DI
    indicate trend direction.

    Hedge Fund Usage:
    - ADX > 25: Strong trend (trend-following strategies work)
    - ADX < 20: Weak/no trend (range-bound strategies work)
    - +DI > -DI: Bullish trend
    - -DI > +DI: Bearish trend
    - Rising ADX: Trend strengthening
    """

    def __init__(self, period: int = 14):
        super().__init__("ADX")
        self.period = period

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate ADX, +DI, and -DI."""
        self.validate_data(df, ["high", "low", "close"])
        df = df.copy()

        # Calculate True Range
        high_low = df["high"] - df["low"]
        high_close = abs(df["high"] - df["close"].shift(1))
        low_close = abs(df["low"] - df["close"].shift(1))
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

        # Calculate directional movement
        up_move = df["high"] - df["high"].shift(1)
        down_move = df["low"].shift(1) - df["low"]

        plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0)

        # Smooth with Wilder's method
        atr = tr.ewm(alpha=1 / self.period, min_periods=self.period, adjust=False).mean()
        plus_dm_smooth = plus_dm.ewm(alpha=1 / self.period, min_periods=self.period, adjust=False).mean()
        minus_dm_smooth = minus_dm.ewm(alpha=1 / self.period, min_periods=self.period, adjust=False).mean()

        # Calculate +DI and -DI
        df["plus_di"] = (plus_dm_smooth / atr) * 100
        df["minus_di"] = (minus_dm_smooth / atr) * 100

        # Calculate DX and ADX
        di_diff = abs(df["plus_di"] - df["minus_di"])
        di_sum = df["plus_di"] + df["minus_di"]
        dx = self.safe_divide(di_diff.values, di_sum.values) * 100
        df["adx"] = pd.Series(dx, index=df.index).ewm(
            alpha=1 / self.period, min_periods=self.period, adjust=False
        ).mean()

        return df

    def get_signal(self, df: pd.DataFrame) -> IndicatorResult:
        """Generate trading signal from ADX."""
        if "adx" not in df.columns:
            df = self.calculate(df)

        adx = df["adx"].iloc[-1]
        plus_di = df["plus_di"].iloc[-1]
        minus_di = df["minus_di"].iloc[-1]
        prev_adx = df["adx"].iloc[-2] if len(df) > 1 else adx

        trend_strength = "strong" if adx > 25 else "weak" if adx < 20 else "moderate"
        adx_rising = adx > prev_adx

        if adx > 25:
            if plus_di > minus_di:
                signal = IndicatorSignal.BUY if adx_rising else IndicatorSignal.NEUTRAL
                desc = f"Strong bullish trend (ADX={adx:.1f}, +DI={plus_di:.1f})"
                confidence = 0.7 if adx_rising else 0.55
            else:
                signal = IndicatorSignal.SELL if adx_rising else IndicatorSignal.NEUTRAL
                desc = f"Strong bearish trend (ADX={adx:.1f}, -DI={minus_di:.1f})"
                confidence = 0.7 if adx_rising else 0.55
        elif adx < 20:
            signal = IndicatorSignal.NEUTRAL
            desc = f"No clear trend (ADX={adx:.1f}), range-bound market"
            confidence = 0.6
        else:
            if plus_di > minus_di:
                signal = IndicatorSignal.BUY
                desc = f"Moderate bullish trend (ADX={adx:.1f})"
                confidence = 0.55
            else:
                signal = IndicatorSignal.SELL
                desc = f"Moderate bearish trend (ADX={adx:.1f})"
                confidence = 0.55

        return IndicatorResult(
            name=self.name,
            value=adx,
            signal=signal,
            description=desc,
            confidence=confidence,
        )


class SuperTrend(BaseIndicator):
    """
    SuperTrend Indicator.

    A trend-following indicator that combines ATR with price action.
    Provides clear buy/sell signals with defined stop-loss levels.

    Hedge Fund Usage:
    - Price above SuperTrend: Bullish, use as trailing stop
    - Price below SuperTrend: Bearish, use as trailing stop
    - SuperTrend flip: Strong trend change signal
    """

    def __init__(self, period: int = 10, multiplier: float = 3.0):
        super().__init__("SuperTrend")
        self.period = period
        self.multiplier = multiplier

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate SuperTrend values."""
        self.validate_data(df, ["high", "low", "close"])
        df = df.copy()

        # Calculate ATR
        high_low = df["high"] - df["low"]
        high_close = abs(df["high"] - df["close"].shift(1))
        low_close = abs(df["low"] - df["close"].shift(1))
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1 / self.period, min_periods=self.period, adjust=False).mean()

        # Calculate basic bands
        hl2 = (df["high"] + df["low"]) / 2
        upper_band = hl2 + (self.multiplier * atr)
        lower_band = hl2 - (self.multiplier * atr)

        # Initialize SuperTrend
        supertrend = pd.Series(index=df.index, dtype=float)
        direction = pd.Series(index=df.index, dtype=int)

        # First valid value
        first_valid = atr.first_valid_index()
        if first_valid is not None:
            idx = df.index.get_loc(first_valid)
            supertrend.iloc[idx] = upper_band.iloc[idx]
            direction.iloc[idx] = -1

            # Calculate SuperTrend
            for i in range(idx + 1, len(df)):
                if direction.iloc[i - 1] == 1:  # Previous was bullish
                    if df["close"].iloc[i] < lower_band.iloc[i - 1]:
                        supertrend.iloc[i] = upper_band.iloc[i]
                        direction.iloc[i] = -1
                    else:
                        supertrend.iloc[i] = max(lower_band.iloc[i], supertrend.iloc[i - 1])
                        direction.iloc[i] = 1
                else:  # Previous was bearish
                    if df["close"].iloc[i] > upper_band.iloc[i - 1]:
                        supertrend.iloc[i] = lower_band.iloc[i]
                        direction.iloc[i] = 1
                    else:
                        supertrend.iloc[i] = min(upper_band.iloc[i], supertrend.iloc[i - 1])
                        direction.iloc[i] = -1

        df["supertrend"] = supertrend
        df["supertrend_dir"] = direction

        return df

    def get_signal(self, df: pd.DataFrame) -> IndicatorResult:
        """Generate trading signal from SuperTrend."""
        if "supertrend" not in df.columns:
            df = self.calculate(df)

        price = df["close"].iloc[-1]
        st = df["supertrend"].iloc[-1]
        direction = df["supertrend_dir"].iloc[-1]
        prev_dir = df["supertrend_dir"].iloc[-2] if len(df) > 1 else direction

        # Check for direction change
        flipped_bullish = prev_dir == -1 and direction == 1
        flipped_bearish = prev_dir == 1 and direction == -1

        if flipped_bullish:
            signal = IndicatorSignal.STRONG_BUY
            desc = f"SuperTrend flipped bullish at {st:.2f}"
            confidence = 0.8
        elif flipped_bearish:
            signal = IndicatorSignal.STRONG_SELL
            desc = f"SuperTrend flipped bearish at {st:.2f}"
            confidence = 0.8
        elif direction == 1:
            signal = IndicatorSignal.BUY
            desc = f"Price above SuperTrend ({st:.2f}), bullish"
            confidence = 0.65
        else:
            signal = IndicatorSignal.SELL
            desc = f"Price below SuperTrend ({st:.2f}), bearish"
            confidence = 0.65

        return IndicatorResult(
            name=self.name,
            value=st,
            signal=signal,
            description=desc,
            confidence=confidence,
        )
