"""
Live Tracker - Professional-grade market monitoring and alert system.

A hedge fund-quality trading signal system with institutional-grade
technical indicators, real-time monitoring, and multi-channel alerts.
"""

__version__ = "1.0.0"
__author__ = "Live Tracker Team"

from live_tracker.tracker import LiveTracker
from live_tracker.signals import SignalEngine, Signal, SignalStrength

__all__ = ["LiveTracker", "SignalEngine", "Signal", "SignalStrength"]
