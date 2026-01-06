"""
Signal Engine.

The brain of the trading system. Combines multiple technical indicators
to generate weighted trading signals with confidence scores.
"""

import logging
from datetime import datetime
from typing import Optional

import pandas as pd

from live_tracker.indicators import (
    RSI,
    MACD,
    BollingerBands,
    ATR,
    EMA,
    SMA,
    Stochastic,
    ADX,
    SuperTrend,
    OBV,
    VWAP,
    PivotPoints,
)
from live_tracker.indicators.base import IndicatorResult, IndicatorSignal
from live_tracker.signals.types import (
    Signal,
    SignalType,
    SignalStrength,
    AlertThresholds,
)

logger = logging.getLogger(__name__)


class SignalEngine:
    """
    Signal generation engine that combines multiple indicators.

    Uses a weighted voting system where each indicator casts a vote
    (buy/sell/neutral) weighted by its confidence and configured weight.
    The final score determines the signal strength and direction.

    Hedge Fund Approach:
    - Multiple timeframe confirmation
    - Confluence of indicators
    - Risk-adjusted position sizing
    - Dynamic stop-loss based on ATR
    """

    # Default indicator weights (can be customized)
    DEFAULT_WEIGHTS = {
        "RSI": 1.2,           # Momentum indicator, reliable for extremes
        "MACD": 1.5,          # Trend + momentum, highly reliable
        "Bollinger Bands": 1.0,  # Volatility/mean reversion
        "Stochastic": 0.8,    # Momentum, good for confirmation
        "ADX": 1.0,           # Trend strength
        "SuperTrend": 1.3,    # Trend following with clear signals
        "EMA(20)": 0.8,       # Short-term trend
        "EMA(50)": 1.0,       # Medium-term trend
        "SMA(200)": 1.2,      # Long-term trend (major signal)
        "OBV": 0.9,           # Volume confirmation
        "VWAP": 0.8,          # Institutional reference
        "Pivot Points (classic)": 0.7,  # Support/Resistance
    }

    def __init__(
        self,
        weights: Optional[dict[str, float]] = None,
        thresholds: Optional[AlertThresholds] = None,
    ):
        """
        Initialize the signal engine.

        Args:
            weights: Custom indicator weights (optional)
            thresholds: Custom alert thresholds (optional)
        """
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self.thresholds = thresholds or AlertThresholds()

        # Initialize indicators
        self.indicators = [
            RSI(period=14),
            MACD(fast=12, slow=26, signal=9),
            BollingerBands(period=20, std_dev=2.0),
            Stochastic(k_period=14, d_period=3),
            ADX(period=14),
            SuperTrend(period=10, multiplier=3.0),
            EMA(period=20),
            EMA(period=50),
            SMA(period=200),
            OBV(signal_period=20),
            VWAP(),
            PivotPoints(method="classic"),
        ]

        # ATR for stop-loss calculation (not for signal)
        self.atr = ATR(period=14)

    def analyze(self, df: pd.DataFrame, symbol: str = "UNKNOWN") -> Signal:
        """
        Analyze price data and generate a trading signal.

        Args:
            df: DataFrame with OHLCV data
            symbol: Ticker symbol for the signal

        Returns:
            Signal object with complete analysis
        """
        if df.empty or len(df) < 20:
            logger.warning(f"Insufficient data for {symbol}")
            return Signal(
                symbol=symbol,
                signal_type=SignalType.HOLD,
                strength=SignalStrength.NEUTRAL,
                score=0.0,
                price=0.0,
                description="Insufficient data for analysis",
            )

        current_price = df["close"].iloc[-1]
        indicator_results: dict[str, IndicatorResult] = {}
        total_score = 0.0
        total_weight = 0.0

        # Calculate ATR for stop-loss
        df = self.atr.calculate(df)
        atr_value = df["atr"].iloc[-1]

        # Run all indicators
        for indicator in self.indicators:
            try:
                df = indicator.calculate(df)
                result = indicator.get_signal(df)
                indicator_results[result.name] = result

                # Get weight for this indicator
                weight = self.weights.get(result.name, 1.0)

                # Calculate weighted score
                # Signal value: -2 (strong sell) to +2 (strong buy)
                signal_value = result.signal.value
                weighted_score = signal_value * result.confidence * weight

                total_score += weighted_score
                total_weight += weight

                logger.debug(
                    f"{result.name}: {result.signal.name} "
                    f"(confidence={result.confidence:.2f}, weight={weight})"
                )

            except Exception as e:
                logger.error(f"Error calculating {indicator.name}: {e}")

        # Normalize score to -100 to +100 range
        if total_weight > 0:
            # Maximum possible score is if all indicators gave strong buy (2.0)
            # with confidence 1.0 and their weights
            max_score = 2.0 * total_weight
            normalized_score = (total_score / max_score) * 100
        else:
            normalized_score = 0.0

        # Determine signal type and strength
        signal_type = self.thresholds.get_signal_type(normalized_score)
        signal_strength = self.thresholds.get_signal_strength(normalized_score)

        # Calculate stop-loss and take-profit
        stop_loss, take_profit, risk_reward = self._calculate_risk_levels(
            current_price, atr_value, signal_type
        )

        # Build indicator summary
        indicator_summary = {
            name: {
                "signal": result.signal.name,
                "value": result.value,
                "confidence": result.confidence,
                "description": result.description,
            }
            for name, result in indicator_results.items()
        }

        # Count bullish vs bearish indicators
        bullish_count = sum(
            1 for r in indicator_results.values()
            if r.signal in [IndicatorSignal.BUY, IndicatorSignal.STRONG_BUY]
        )
        bearish_count = sum(
            1 for r in indicator_results.values()
            if r.signal in [IndicatorSignal.SELL, IndicatorSignal.STRONG_SELL]
        )

        # Generate detailed description
        description = self._generate_description(
            symbol, signal_type, signal_strength, normalized_score,
            current_price, bullish_count, bearish_count, len(indicator_results)
        )

        return Signal(
            symbol=symbol,
            signal_type=signal_type,
            strength=signal_strength,
            score=normalized_score,
            price=current_price,
            timestamp=datetime.now(),
            indicators=indicator_summary,
            description=description,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward=risk_reward,
        )

    def _calculate_risk_levels(
        self,
        price: float,
        atr: float,
        signal_type: SignalType,
    ) -> tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Calculate stop-loss and take-profit levels based on ATR.

        Uses 2x ATR for stop-loss and targets 2:1 risk/reward ratio.
        """
        if signal_type == SignalType.HOLD or atr == 0:
            return None, None, None

        atr_multiplier = 2.0  # Risk 2x ATR
        risk_reward_target = 2.0  # Target 2:1 R/R

        if signal_type == SignalType.BUY:
            stop_loss = price - (atr * atr_multiplier)
            risk = price - stop_loss
            take_profit = price + (risk * risk_reward_target)
        else:  # SELL
            stop_loss = price + (atr * atr_multiplier)
            risk = stop_loss - price
            take_profit = price - (risk * risk_reward_target)

        return stop_loss, take_profit, risk_reward_target

    def _generate_description(
        self,
        symbol: str,
        signal_type: SignalType,
        strength: SignalStrength,
        score: float,
        price: float,
        bullish: int,
        bearish: int,
        total: int,
    ) -> str:
        """Generate a comprehensive signal description."""
        if signal_type == SignalType.HOLD:
            return (
                f"{symbol} @ ${price:.2f}: HOLD - Mixed signals "
                f"({bullish} bullish, {bearish} bearish out of {total} indicators). "
                f"Score: {score:.1f}"
            )

        action = "BUY" if signal_type == SignalType.BUY else "SELL"
        strength_word = strength.value.lower()

        if strength == SignalStrength.STRONG:
            conviction = f"{bullish if signal_type == SignalType.BUY else bearish}/{total} indicators aligned"
        else:
            conviction = f"Mixed signals with {bullish} bullish, {bearish} bearish"

        return (
            f"{symbol} @ ${price:.2f}: {strength_word.upper()} {action} "
            f"(Score: {score:.1f}). {conviction}."
        )

    def get_indicator_weights(self) -> dict[str, float]:
        """Get current indicator weights."""
        return self.weights.copy()

    def set_indicator_weight(self, indicator_name: str, weight: float):
        """Set weight for a specific indicator."""
        self.weights[indicator_name] = weight

    def quick_scan(self, df: pd.DataFrame, symbol: str = "UNKNOWN") -> dict:
        """
        Perform a quick scan with key indicators only.

        Faster than full analysis, good for screening many symbols.

        Args:
            df: DataFrame with OHLCV data
            symbol: Ticker symbol

        Returns:
            Dictionary with quick scan results
        """
        if df.empty or len(df) < 20:
            return {"symbol": symbol, "error": "Insufficient data"}

        current_price = df["close"].iloc[-1]

        # Quick indicators
        rsi = RSI(period=14)
        macd = MACD()
        bb = BollingerBands()

        df = rsi.calculate(df)
        df = macd.calculate(df)
        df = bb.calculate(df)

        rsi_result = rsi.get_signal(df)
        macd_result = macd.get_signal(df)
        bb_result = bb.get_signal(df)

        # Quick score
        score = (
            rsi_result.signal.value * rsi_result.confidence
            + macd_result.signal.value * macd_result.confidence
            + bb_result.signal.value * bb_result.confidence
        ) / 3 * 50  # Normalize to -100 to +100

        return {
            "symbol": symbol,
            "price": current_price,
            "score": score,
            "rsi": df["rsi"].iloc[-1],
            "macd_hist": df["macd_hist"].iloc[-1],
            "bb_pct": df["bb_pct"].iloc[-1],
            "quick_signal": "BUY" if score > 20 else "SELL" if score < -20 else "HOLD",
        }

    def screen_symbols(
        self,
        data: dict[str, pd.DataFrame],
        min_score: float = 30.0,
    ) -> list[Signal]:
        """
        Screen multiple symbols and return actionable signals.

        Args:
            data: Dictionary mapping symbols to their OHLCV DataFrames
            min_score: Minimum absolute score to include

        Returns:
            List of signals sorted by absolute score (strongest first)
        """
        signals = []

        for symbol, df in data.items():
            try:
                signal = self.analyze(df, symbol)
                if abs(signal.score) >= min_score:
                    signals.append(signal)
            except Exception as e:
                logger.error(f"Error screening {symbol}: {e}")

        # Sort by absolute score (strongest signals first)
        signals.sort(key=lambda s: abs(s.score), reverse=True)

        return signals
