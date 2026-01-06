"""
Volatility Indicators.

These indicators measure market volatility and help identify potential
breakouts, reversals, and optimal position sizing.
"""

import numpy as np
import pandas as pd

from live_tracker.indicators.base import BaseIndicator, IndicatorResult, IndicatorSignal


class BollingerBands(BaseIndicator):
    """
    Bollinger Bands.

    A volatility indicator consisting of a middle band (SMA) and upper/lower
    bands based on standard deviation.

    Hedge Fund Usage:
    - Price touching lower band: Potential buy (mean reversion)
    - Price touching upper band: Potential sell (mean reversion)
    - Band squeeze: Low volatility, breakout imminent
    - Band expansion: High volatility, trend confirmation
    - Walking the bands: Strong trend in progress
    """

    def __init__(self, period: int = 20, std_dev: float = 2.0):
        super().__init__("Bollinger Bands")
        self.period = period
        self.std_dev = std_dev

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Bollinger Bands."""
        self.validate_data(df, ["close"])
        df = df.copy()

        # Middle Band = SMA
        df["bb_middle"] = df["close"].rolling(window=self.period).mean()

        # Standard Deviation
        rolling_std = df["close"].rolling(window=self.period).std()

        # Upper and Lower Bands
        df["bb_upper"] = df["bb_middle"] + (rolling_std * self.std_dev)
        df["bb_lower"] = df["bb_middle"] - (rolling_std * self.std_dev)

        # Band Width (volatility measure)
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"]

        # %B (position within bands)
        df["bb_pct"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])

        return df

    def get_signal(self, df: pd.DataFrame) -> IndicatorResult:
        """Generate trading signal from Bollinger Bands."""
        if "bb_middle" not in df.columns:
            df = self.calculate(df)

        price = df["close"].iloc[-1]
        upper = df["bb_upper"].iloc[-1]
        lower = df["bb_lower"].iloc[-1]
        middle = df["bb_middle"].iloc[-1]
        bb_pct = df["bb_pct"].iloc[-1]
        bb_width = df["bb_width"].iloc[-1]

        # Calculate average bandwidth for squeeze detection
        avg_width = df["bb_width"].rolling(window=self.period).mean().iloc[-1]
        is_squeeze = bb_width < avg_width * 0.75

        if bb_pct <= 0:  # Below lower band
            signal = IndicatorSignal.STRONG_BUY
            desc = f"Price below lower Bollinger Band (oversold)"
            confidence = 0.75
        elif bb_pct >= 1:  # Above upper band
            signal = IndicatorSignal.STRONG_SELL
            desc = f"Price above upper Bollinger Band (overbought)"
            confidence = 0.75
        elif bb_pct < 0.2:  # Near lower band
            signal = IndicatorSignal.BUY
            desc = f"Price near lower Bollinger Band (%B={bb_pct:.2f})"
            confidence = 0.65
        elif bb_pct > 0.8:  # Near upper band
            signal = IndicatorSignal.SELL
            desc = f"Price near upper Bollinger Band (%B={bb_pct:.2f})"
            confidence = 0.65
        elif is_squeeze:
            signal = IndicatorSignal.NEUTRAL
            desc = f"Bollinger Band squeeze - breakout imminent"
            confidence = 0.6
        else:
            signal = IndicatorSignal.NEUTRAL
            desc = f"Price within Bollinger Bands (%B={bb_pct:.2f})"
            confidence = 0.5

        return IndicatorResult(
            name=self.name,
            value=bb_pct,
            signal=signal,
            description=desc,
            confidence=confidence,
        )


class ATR(BaseIndicator):
    """
    Average True Range (ATR).

    Measures market volatility by analyzing the complete range of price
    movement for each period.

    Hedge Fund Usage:
    - Position sizing: Higher ATR = smaller positions
    - Stop-loss placement: Use 2-3x ATR from entry
    - Volatility filter: Trade only when ATR is in desired range
    - Breakout confirmation: Compare move size to ATR
    """

    def __init__(self, period: int = 14):
        super().__init__("ATR")
        self.period = period

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate ATR values."""
        self.validate_data(df, ["high", "low", "close"])
        df = df.copy()

        # Calculate True Range
        high_low = df["high"] - df["low"]
        high_close = abs(df["high"] - df["close"].shift(1))
        low_close = abs(df["low"] - df["close"].shift(1))

        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

        # Calculate ATR using Wilder's smoothing
        df["atr"] = tr.ewm(alpha=1 / self.period, min_periods=self.period, adjust=False).mean()

        # ATR as percentage of price
        df["atr_pct"] = (df["atr"] / df["close"]) * 100

        return df

    def get_signal(self, df: pd.DataFrame) -> IndicatorResult:
        """Generate trading signal from ATR."""
        if "atr" not in df.columns:
            df = self.calculate(df)

        atr = df["atr"].iloc[-1]
        atr_pct = df["atr_pct"].iloc[-1]
        prev_atr = df["atr"].iloc[-2] if len(df) > 1 else atr

        # Calculate ATR trend
        atr_ma = df["atr"].rolling(window=self.period).mean().iloc[-1]
        volatility_high = atr > atr_ma * 1.5
        volatility_low = atr < atr_ma * 0.7
        atr_rising = atr > prev_atr

        if volatility_high:
            signal = IndicatorSignal.NEUTRAL
            desc = f"High volatility (ATR={atr:.4f}, {atr_pct:.2f}% of price) - reduce position size"
            confidence = 0.7
        elif volatility_low:
            signal = IndicatorSignal.NEUTRAL
            desc = f"Low volatility (ATR={atr:.4f}) - potential breakout setup"
            confidence = 0.6
        elif atr_rising:
            signal = IndicatorSignal.NEUTRAL
            desc = f"Volatility increasing (ATR={atr:.4f})"
            confidence = 0.5
        else:
            signal = IndicatorSignal.NEUTRAL
            desc = f"Normal volatility (ATR={atr:.4f}, {atr_pct:.2f}% of price)"
            confidence = 0.5

        return IndicatorResult(
            name=self.name,
            value=atr,
            signal=signal,
            description=desc,
            confidence=confidence,
        )


class KeltnerChannel(BaseIndicator):
    """
    Keltner Channel.

    Similar to Bollinger Bands but uses ATR instead of standard deviation.
    More stable during volatile markets.

    Hedge Fund Usage:
    - Breakout above upper channel: Strong bullish momentum
    - Breakout below lower channel: Strong bearish momentum
    - Combined with Bollinger Bands for "squeeze" detection
    - Used for trend-following entries
    """

    def __init__(self, ema_period: int = 20, atr_period: int = 10, multiplier: float = 2.0):
        super().__init__("Keltner Channel")
        self.ema_period = ema_period
        self.atr_period = atr_period
        self.multiplier = multiplier

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Keltner Channel values."""
        self.validate_data(df, ["high", "low", "close"])
        df = df.copy()

        # Middle line = EMA
        df["kc_middle"] = df["close"].ewm(span=self.ema_period, adjust=False).mean()

        # Calculate ATR
        high_low = df["high"] - df["low"]
        high_close = abs(df["high"] - df["close"].shift(1))
        low_close = abs(df["low"] - df["close"].shift(1))
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1 / self.atr_period, min_periods=self.atr_period, adjust=False).mean()

        # Upper and Lower Channels
        df["kc_upper"] = df["kc_middle"] + (atr * self.multiplier)
        df["kc_lower"] = df["kc_middle"] - (atr * self.multiplier)

        # Position within channel
        channel_range = df["kc_upper"] - df["kc_lower"]
        df["kc_pct"] = (df["close"] - df["kc_lower"]) / channel_range

        return df

    def get_signal(self, df: pd.DataFrame) -> IndicatorResult:
        """Generate trading signal from Keltner Channel."""
        if "kc_middle" not in df.columns:
            df = self.calculate(df)

        price = df["close"].iloc[-1]
        upper = df["kc_upper"].iloc[-1]
        lower = df["kc_lower"].iloc[-1]
        middle = df["kc_middle"].iloc[-1]
        kc_pct = df["kc_pct"].iloc[-1]

        prev_price = df["close"].iloc[-2] if len(df) > 1 else price
        prev_upper = df["kc_upper"].iloc[-2] if len(df) > 1 else upper
        prev_lower = df["kc_lower"].iloc[-2] if len(df) > 1 else lower

        # Check for breakouts
        upper_breakout = prev_price <= prev_upper and price > upper
        lower_breakout = prev_price >= prev_lower and price < lower

        if upper_breakout:
            signal = IndicatorSignal.STRONG_BUY
            desc = f"Breakout above Keltner Channel upper band"
            confidence = 0.75
        elif lower_breakout:
            signal = IndicatorSignal.STRONG_SELL
            desc = f"Breakout below Keltner Channel lower band"
            confidence = 0.75
        elif price > upper:
            signal = IndicatorSignal.BUY
            desc = f"Price above upper Keltner Channel - strong bullish"
            confidence = 0.65
        elif price < lower:
            signal = IndicatorSignal.SELL
            desc = f"Price below lower Keltner Channel - strong bearish"
            confidence = 0.65
        elif price > middle:
            signal = IndicatorSignal.BUY
            desc = f"Price above Keltner middle line"
            confidence = 0.55
        elif price < middle:
            signal = IndicatorSignal.SELL
            desc = f"Price below Keltner middle line"
            confidence = 0.55
        else:
            signal = IndicatorSignal.NEUTRAL
            desc = f"Price at Keltner Channel midline"
            confidence = 0.5

        return IndicatorResult(
            name=self.name,
            value=kc_pct,
            signal=signal,
            description=desc,
            confidence=confidence,
        )
