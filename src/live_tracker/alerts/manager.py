"""
Alert Manager.

Manages alert channels and handles deduplication, filtering, and routing.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from live_tracker.alerts.channels import AlertChannel, ConsoleChannel
from live_tracker.signals.types import Signal, SignalStrength, SignalType

logger = logging.getLogger(__name__)


class AlertManager:
    """
    Manages trading alerts across multiple channels.

    Features:
    - Multi-channel support (console, file, webhook, Slack, Discord)
    - Alert deduplication (prevent spam)
    - Signal filtering by strength, type, and score
    - Alert history tracking
    - Rate limiting
    """

    def __init__(
        self,
        channels: Optional[list[AlertChannel]] = None,
        cooldown_minutes: int = 15,
        min_score: float = 30.0,
        min_strength: SignalStrength = SignalStrength.MODERATE,
    ):
        """
        Initialize the alert manager.

        Args:
            channels: List of alert channels (defaults to console only)
            cooldown_minutes: Minimum minutes between alerts for same symbol
            min_score: Minimum absolute score to trigger alert
            min_strength: Minimum signal strength to trigger alert
        """
        self.channels = channels or [ConsoleChannel()]
        self.cooldown_minutes = cooldown_minutes
        self.min_score = min_score
        self.min_strength = min_strength

        # Track recent alerts for deduplication
        self._alert_history: dict[str, datetime] = {}

        # Track all alerts for analysis
        self._all_alerts: list[Signal] = []

    def add_channel(self, channel: AlertChannel):
        """Add a new alert channel."""
        self.channels.append(channel)

    def remove_channel(self, channel_name: str):
        """Remove a channel by name."""
        self.channels = [c for c in self.channels if c.name != channel_name]

    def should_alert(self, signal: Signal) -> bool:
        """
        Check if a signal should trigger an alert.

        Args:
            signal: The trading signal to check

        Returns:
            True if alert should be sent
        """
        # Check signal type
        if signal.signal_type == SignalType.HOLD:
            return False

        # Check score threshold
        if abs(signal.score) < self.min_score:
            logger.debug(
                f"Skipping alert for {signal.symbol}: "
                f"score {signal.score:.1f} below threshold {self.min_score}"
            )
            return False

        # Check strength threshold
        strength_order = {
            SignalStrength.NEUTRAL: 0,
            SignalStrength.WEAK: 1,
            SignalStrength.MODERATE: 2,
            SignalStrength.STRONG: 3,
        }
        if strength_order[signal.strength] < strength_order[self.min_strength]:
            logger.debug(
                f"Skipping alert for {signal.symbol}: "
                f"strength {signal.strength.value} below threshold"
            )
            return False

        # Check cooldown (deduplication)
        cache_key = f"{signal.symbol}_{signal.signal_type.value}"
        if cache_key in self._alert_history:
            last_alert = self._alert_history[cache_key]
            cooldown_delta = timedelta(minutes=self.cooldown_minutes)
            if datetime.now() - last_alert < cooldown_delta:
                logger.debug(
                    f"Skipping alert for {signal.symbol}: "
                    f"cooldown not expired"
                )
                return False

        return True

    def send_alert(self, signal: Signal, force: bool = False) -> bool:
        """
        Send an alert for the given signal.

        Args:
            signal: The trading signal
            force: Bypass filtering and cooldown checks

        Returns:
            True if at least one channel sent successfully
        """
        # Check if we should alert
        if not force and not self.should_alert(signal):
            return False

        # Update alert history
        cache_key = f"{signal.symbol}_{signal.signal_type.value}"
        self._alert_history[cache_key] = datetime.now()
        self._all_alerts.append(signal)

        # Send to all enabled channels
        success_count = 0
        for channel in self.channels:
            if not channel.enabled:
                continue

            try:
                if channel.send(signal):
                    success_count += 1
                    logger.info(f"Alert sent via {channel.name} for {signal.symbol}")
                else:
                    logger.warning(f"Alert failed via {channel.name}")
            except Exception as e:
                logger.error(f"Error sending alert via {channel.name}: {e}")

        return success_count > 0

    def process_signals(self, signals: list[Signal]) -> int:
        """
        Process multiple signals and send alerts for qualifying ones.

        Args:
            signals: List of trading signals

        Returns:
            Number of alerts sent
        """
        alert_count = 0
        for signal in signals:
            if self.send_alert(signal):
                alert_count += 1
        return alert_count

    def get_alert_history(
        self,
        symbol: Optional[str] = None,
        signal_type: Optional[SignalType] = None,
        since: Optional[datetime] = None,
    ) -> list[Signal]:
        """
        Get alert history with optional filtering.

        Args:
            symbol: Filter by symbol
            signal_type: Filter by signal type
            since: Filter to alerts after this time

        Returns:
            List of historical signals
        """
        alerts = self._all_alerts

        if symbol:
            alerts = [a for a in alerts if a.symbol == symbol]

        if signal_type:
            alerts = [a for a in alerts if a.signal_type == signal_type]

        if since:
            alerts = [a for a in alerts if a.timestamp >= since]

        return alerts

    def clear_history(self):
        """Clear alert history and cooldown tracking."""
        self._alert_history.clear()
        self._all_alerts.clear()

    def get_stats(self) -> dict:
        """Get alert statistics."""
        if not self._all_alerts:
            return {
                "total_alerts": 0,
                "buy_signals": 0,
                "sell_signals": 0,
                "strong_signals": 0,
                "avg_score": 0,
            }

        buy_signals = [a for a in self._all_alerts if a.signal_type == SignalType.BUY]
        sell_signals = [a for a in self._all_alerts if a.signal_type == SignalType.SELL]
        strong_signals = [a for a in self._all_alerts if a.strength == SignalStrength.STRONG]

        return {
            "total_alerts": len(self._all_alerts),
            "buy_signals": len(buy_signals),
            "sell_signals": len(sell_signals),
            "strong_signals": len(strong_signals),
            "avg_score": sum(abs(a.score) for a in self._all_alerts) / len(self._all_alerts),
            "symbols_alerted": list(set(a.symbol for a in self._all_alerts)),
        }
