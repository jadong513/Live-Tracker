"""
Signal Generation Module.

Combines multiple technical indicators to generate trading signals
with confidence scores.
"""

from live_tracker.signals.engine import SignalEngine
from live_tracker.signals.types import Signal, SignalStrength, SignalType

__all__ = ["SignalEngine", "Signal", "SignalStrength", "SignalType"]
