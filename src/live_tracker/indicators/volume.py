"""
Volume Indicators.

Volume is the fuel that drives price movements. These indicators help
confirm trends and identify potential reversals through volume analysis.
"""

import numpy as np
import pandas as pd

from live_tracker.indicators.base import BaseIndicator, IndicatorResult, IndicatorSignal


class OBV(BaseIndicator):
    """
    On-Balance Volume (OBV).

    Cumulative indicator that adds volume on up days and subtracts
    on down days. Confirms trends and signals potential breakouts.

    Hedge Fund Usage:
    - OBV rising with price: Confirms uptrend
    - OBV falling with price: Confirms downtrend
    - OBV divergence from price: Early reversal warning
    - OBV breakout before price: Anticipates price move
    """

    def __init__(self, signal_period: int = 20):
        super().__init__("OBV")
        self.signal_period = signal_period

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate OBV values."""
        self.validate_data(df, ["close", "volume"])
        df = df.copy()

        # Calculate OBV
        price_change = df["close"].diff()
        obv = pd.Series(index=df.index, dtype=float)
        obv.iloc[0] = 0

        for i in range(1, len(df)):
            if price_change.iloc[i] > 0:
                obv.iloc[i] = obv.iloc[i - 1] + df["volume"].iloc[i]
            elif price_change.iloc[i] < 0:
                obv.iloc[i] = obv.iloc[i - 1] - df["volume"].iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i - 1]

        df["obv"] = obv

        # OBV Signal Line (EMA)
        df["obv_signal"] = df["obv"].ewm(span=self.signal_period, adjust=False).mean()

        # OBV Momentum
        df["obv_momentum"] = df["obv"] - df["obv_signal"]

        return df

    def get_signal(self, df: pd.DataFrame) -> IndicatorResult:
        """Generate trading signal from OBV."""
        if "obv" not in df.columns:
            df = self.calculate(df)

        obv = df["obv"].iloc[-1]
        obv_signal = df["obv_signal"].iloc[-1]
        momentum = df["obv_momentum"].iloc[-1]

        prev_obv = df["obv"].iloc[-2] if len(df) > 1 else obv
        prev_signal = df["obv_signal"].iloc[-2] if len(df) > 1 else obv_signal

        # Check price vs OBV divergence
        price_change = df["close"].iloc[-1] - df["close"].iloc[-5] if len(df) > 5 else 0
        obv_change = obv - df["obv"].iloc[-5] if len(df) > 5 else 0

        bullish_divergence = price_change < 0 and obv_change > 0
        bearish_divergence = price_change > 0 and obv_change < 0

        # Check for signal crossovers
        bullish_cross = prev_obv <= prev_signal and obv > obv_signal
        bearish_cross = prev_obv >= prev_signal and obv < obv_signal

        if bullish_divergence:
            signal = IndicatorSignal.STRONG_BUY
            desc = "Bullish OBV divergence - volume accumulation despite falling price"
            confidence = 0.8
        elif bearish_divergence:
            signal = IndicatorSignal.STRONG_SELL
            desc = "Bearish OBV divergence - volume distribution despite rising price"
            confidence = 0.8
        elif bullish_cross:
            signal = IndicatorSignal.BUY
            desc = "OBV crossed above signal line"
            confidence = 0.65
        elif bearish_cross:
            signal = IndicatorSignal.SELL
            desc = "OBV crossed below signal line"
            confidence = 0.65
        elif momentum > 0:
            signal = IndicatorSignal.BUY
            desc = f"Positive OBV momentum"
            confidence = 0.55
        elif momentum < 0:
            signal = IndicatorSignal.SELL
            desc = f"Negative OBV momentum"
            confidence = 0.55
        else:
            signal = IndicatorSignal.NEUTRAL
            desc = "OBV neutral"
            confidence = 0.5

        return IndicatorResult(
            name=self.name,
            value=obv,
            signal=signal,
            description=desc,
            confidence=confidence,
        )


class VWAP(BaseIndicator):
    """
    Volume Weighted Average Price (VWAP).

    The average price weighted by volume. Critical benchmark for
    institutional traders.

    Hedge Fund Usage:
    - Price above VWAP: Bullish intraday bias
    - Price below VWAP: Bearish intraday bias
    - VWAP as support/resistance during the day
    - Execution benchmark for institutional orders
    """

    def __init__(self, anchor: str = "D"):
        """
        Initialize VWAP.

        Args:
            anchor: Resample anchor ('D' for daily, 'W' for weekly)
        """
        super().__init__("VWAP")
        self.anchor = anchor

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate VWAP values."""
        self.validate_data(df, ["high", "low", "close", "volume"])
        df = df.copy()

        # Typical Price
        typical_price = (df["high"] + df["low"] + df["close"]) / 3

        # Cumulative calculations (reset daily if anchor is 'D')
        if self.anchor == "D" and hasattr(df.index, "date"):
            # Group by date and calculate cumulative sums
            df["tp_vol"] = typical_price * df["volume"]

            # For intraday data with date index
            cum_tp_vol = df.groupby(df.index.date)["tp_vol"].cumsum()
            cum_vol = df.groupby(df.index.date)["volume"].cumsum()
            df["vwap"] = cum_tp_vol / cum_vol
        else:
            # Simple cumulative for daily data
            tp_vol = typical_price * df["volume"]
            cum_tp_vol = tp_vol.cumsum()
            cum_vol = df["volume"].cumsum()
            df["vwap"] = cum_tp_vol / cum_vol

        # Calculate VWAP bands using standard deviation
        df["vwap_upper"] = df["vwap"] * 1.01  # 1% above
        df["vwap_lower"] = df["vwap"] * 0.99  # 1% below

        return df

    def get_signal(self, df: pd.DataFrame) -> IndicatorResult:
        """Generate trading signal from VWAP."""
        if "vwap" not in df.columns:
            df = self.calculate(df)

        price = df["close"].iloc[-1]
        vwap = df["vwap"].iloc[-1]
        vwap_upper = df["vwap_upper"].iloc[-1]
        vwap_lower = df["vwap_lower"].iloc[-1]

        prev_price = df["close"].iloc[-2] if len(df) > 1 else price
        prev_vwap = df["vwap"].iloc[-2] if len(df) > 1 else vwap

        # Calculate distance from VWAP
        distance_pct = ((price - vwap) / vwap) * 100

        # Check for VWAP crossovers
        bullish_cross = prev_price <= prev_vwap and price > vwap
        bearish_cross = prev_price >= prev_vwap and price < vwap

        if bullish_cross:
            signal = IndicatorSignal.BUY
            desc = f"Price crossed above VWAP"
            confidence = 0.7
        elif bearish_cross:
            signal = IndicatorSignal.SELL
            desc = f"Price crossed below VWAP"
            confidence = 0.7
        elif price > vwap_upper:
            signal = IndicatorSignal.BUY
            desc = f"Price {distance_pct:.2f}% above VWAP - strong bullish"
            confidence = 0.6
        elif price < vwap_lower:
            signal = IndicatorSignal.SELL
            desc = f"Price {abs(distance_pct):.2f}% below VWAP - strong bearish"
            confidence = 0.6
        elif price > vwap:
            signal = IndicatorSignal.BUY
            desc = f"Price above VWAP ({distance_pct:.2f}%)"
            confidence = 0.55
        elif price < vwap:
            signal = IndicatorSignal.SELL
            desc = f"Price below VWAP ({distance_pct:.2f}%)"
            confidence = 0.55
        else:
            signal = IndicatorSignal.NEUTRAL
            desc = f"Price at VWAP"
            confidence = 0.5

        return IndicatorResult(
            name=self.name,
            value=vwap,
            signal=signal,
            description=desc,
            confidence=confidence,
        )


class VolumeProfile(BaseIndicator):
    """
    Volume Profile Analysis.

    Analyzes volume distribution across price levels to identify
    high-volume nodes (support/resistance) and low-volume areas.

    Hedge Fund Usage:
    - High Volume Nodes (HVN): Act as support/resistance
    - Low Volume Nodes (LVN): Price moves quickly through these
    - Point of Control (POC): Highest volume price level
    - Value Area: Where 70% of volume occurred
    """

    def __init__(self, lookback: int = 20, num_bins: int = 50):
        super().__init__("Volume Profile")
        self.lookback = lookback
        self.num_bins = num_bins

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Volume Profile metrics."""
        self.validate_data(df, ["high", "low", "close", "volume"])
        df = df.copy()

        # Use recent data for profile
        recent_df = df.tail(self.lookback)

        # Create price bins
        price_min = recent_df["low"].min()
        price_max = recent_df["high"].max()
        price_range = price_max - price_min

        if price_range == 0:
            df["vp_poc"] = df["close"]
            df["vp_val"] = df["close"] * 0.99
            df["vp_vah"] = df["close"] * 1.01
            return df

        bin_size = price_range / self.num_bins

        # Distribute volume across price levels
        volume_profile = np.zeros(self.num_bins)

        for _, row in recent_df.iterrows():
            # Determine which bins this candle spans
            low_bin = int((row["low"] - price_min) / bin_size)
            high_bin = int((row["high"] - price_min) / bin_size)

            low_bin = max(0, min(low_bin, self.num_bins - 1))
            high_bin = max(0, min(high_bin, self.num_bins - 1))

            # Distribute volume across bins
            bins_span = high_bin - low_bin + 1
            volume_per_bin = row["volume"] / bins_span

            for b in range(low_bin, high_bin + 1):
                volume_profile[b] += volume_per_bin

        # Find Point of Control (POC) - highest volume level
        poc_bin = np.argmax(volume_profile)
        poc_price = price_min + (poc_bin + 0.5) * bin_size

        # Calculate Value Area (70% of volume)
        total_volume = volume_profile.sum()
        target_volume = total_volume * 0.70

        cumulative_volume = volume_profile[poc_bin]
        lower_bin = poc_bin
        upper_bin = poc_bin

        while cumulative_volume < target_volume:
            lower_add = volume_profile[lower_bin - 1] if lower_bin > 0 else 0
            upper_add = volume_profile[upper_bin + 1] if upper_bin < self.num_bins - 1 else 0

            if lower_add >= upper_add and lower_bin > 0:
                lower_bin -= 1
                cumulative_volume += lower_add
            elif upper_bin < self.num_bins - 1:
                upper_bin += 1
                cumulative_volume += upper_add
            else:
                break

        val_price = price_min + (lower_bin + 0.5) * bin_size  # Value Area Low
        vah_price = price_min + (upper_bin + 0.5) * bin_size  # Value Area High

        # Store values
        df["vp_poc"] = poc_price
        df["vp_val"] = val_price
        df["vp_vah"] = vah_price

        return df

    def get_signal(self, df: pd.DataFrame) -> IndicatorResult:
        """Generate trading signal from Volume Profile."""
        if "vp_poc" not in df.columns:
            df = self.calculate(df)

        price = df["close"].iloc[-1]
        poc = df["vp_poc"].iloc[-1]
        val = df["vp_val"].iloc[-1]
        vah = df["vp_vah"].iloc[-1]

        # Determine position relative to value area
        if price > vah:
            signal = IndicatorSignal.BUY
            desc = f"Price above Value Area High (VAH={vah:.2f}) - bullish breakout zone"
            confidence = 0.65
        elif price < val:
            signal = IndicatorSignal.SELL
            desc = f"Price below Value Area Low (VAL={val:.2f}) - bearish breakdown zone"
            confidence = 0.65
        elif abs(price - poc) / poc < 0.005:  # Within 0.5% of POC
            signal = IndicatorSignal.NEUTRAL
            desc = f"Price at Point of Control ({poc:.2f}) - high volume consolidation"
            confidence = 0.6
        elif price > poc:
            signal = IndicatorSignal.BUY
            desc = f"Price above POC ({poc:.2f}) within value area"
            confidence = 0.55
        elif price < poc:
            signal = IndicatorSignal.SELL
            desc = f"Price below POC ({poc:.2f}) within value area"
            confidence = 0.55
        else:
            signal = IndicatorSignal.NEUTRAL
            desc = f"Price in value area (POC={poc:.2f})"
            confidence = 0.5

        return IndicatorResult(
            name=self.name,
            value=poc,
            signal=signal,
            description=desc,
            confidence=confidence,
        )
