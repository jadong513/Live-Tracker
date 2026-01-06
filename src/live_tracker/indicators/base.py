"""
Base class for all technical indicators.

Provides a common interface and shared functionality for indicators.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd


class IndicatorSignal(Enum):
    """Signal strength from an indicator."""

    STRONG_BUY = 2
    BUY = 1
    NEUTRAL = 0
    SELL = -1
    STRONG_SELL = -2


@dataclass
class IndicatorResult:
    """Result from an indicator calculation."""

    name: str
    value: float
    signal: IndicatorSignal
    description: str
    confidence: float  # 0.0 to 1.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "signal": self.signal.name,
            "signal_value": self.signal.value,
            "description": self.description,
            "confidence": self.confidence,
        }


class BaseIndicator(ABC):
    """Abstract base class for all technical indicators."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate the indicator values.

        Args:
            df: DataFrame with OHLCV data (open, high, low, close, volume)

        Returns:
            DataFrame with indicator values added as new columns
        """
        pass

    @abstractmethod
    def get_signal(self, df: pd.DataFrame) -> IndicatorResult:
        """
        Get the current trading signal from the indicator.

        Args:
            df: DataFrame with calculated indicator values

        Returns:
            IndicatorResult with signal and metadata
        """
        pass

    def validate_data(self, df: pd.DataFrame, required_columns: list[str]) -> None:
        """Validate that required columns exist in the DataFrame."""
        missing = set(required_columns) - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

    @staticmethod
    def safe_divide(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
        """Safely divide arrays, returning 0 where denominator is 0."""
        with np.errstate(divide='ignore', invalid='ignore'):
            result = np.divide(numerator, denominator)
            result[~np.isfinite(result)] = 0
        return result
