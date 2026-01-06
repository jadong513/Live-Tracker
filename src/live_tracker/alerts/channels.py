"""
Alert Channels.

Different channels for sending trading alerts.
"""

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional

from live_tracker.signals.types import Signal, SignalStrength

logger = logging.getLogger(__name__)


class AlertChannel(ABC):
    """Abstract base class for alert channels."""

    def __init__(self, name: str):
        self.name = name
        self.enabled = True

    @abstractmethod
    def send(self, signal: Signal) -> bool:
        """
        Send an alert for the given signal.

        Args:
            signal: The trading signal to alert on

        Returns:
            True if alert was sent successfully
        """
        pass

    def format_message(self, signal: Signal) -> str:
        """Format signal into a readable message."""
        emoji = self._get_emoji(signal)

        lines = [
            f"{emoji} {signal.strength.value} {signal.signal_type.value} SIGNAL",
            f"Symbol: {signal.symbol}",
            f"Price: ${signal.price:.2f}",
            f"Score: {signal.score:.1f}/100",
            f"Time: {signal.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
        ]

        if signal.stop_loss:
            lines.append(f"Stop Loss: ${signal.stop_loss:.2f}")
        if signal.take_profit:
            lines.append(f"Take Profit: ${signal.take_profit:.2f}")
        if signal.risk_reward:
            lines.append(f"Risk/Reward: 1:{signal.risk_reward:.1f}")

        # Add top indicators
        if signal.indicators:
            lines.append("\nTop Indicators:")
            sorted_indicators = sorted(
                signal.indicators.items(),
                key=lambda x: abs(x[1].get("confidence", 0)),
                reverse=True,
            )[:5]
            for name, data in sorted_indicators:
                lines.append(f"  • {name}: {data['signal']} ({data['confidence']:.0%})")

        return "\n".join(lines)

    def _get_emoji(self, signal: Signal) -> str:
        """Get emoji based on signal type and strength."""
        if signal.signal_type.value == "BUY":
            if signal.strength == SignalStrength.STRONG:
                return "🚀"
            return "📈"
        elif signal.signal_type.value == "SELL":
            if signal.strength == SignalStrength.STRONG:
                return "🔻"
            return "📉"
        return "➡️"


class ConsoleChannel(AlertChannel):
    """Console/terminal alert channel with rich formatting."""

    def __init__(self, use_color: bool = True):
        super().__init__("Console")
        self.use_color = use_color

    def send(self, signal: Signal) -> bool:
        """Print alert to console."""
        try:
            if self.use_color:
                self._print_colored(signal)
            else:
                print(self.format_message(signal))
                print("-" * 50)
            return True
        except Exception as e:
            logger.error(f"Console alert failed: {e}")
            return False

    def _print_colored(self, signal: Signal):
        """Print with ANSI color codes."""
        # Color codes
        RESET = "\033[0m"
        BOLD = "\033[1m"
        GREEN = "\033[92m"
        RED = "\033[91m"
        YELLOW = "\033[93m"
        BLUE = "\033[94m"
        CYAN = "\033[96m"

        if signal.signal_type.value == "BUY":
            signal_color = GREEN
        elif signal.signal_type.value == "SELL":
            signal_color = RED
        else:
            signal_color = YELLOW

        print(f"\n{BOLD}{'=' * 50}{RESET}")
        print(
            f"{signal_color}{BOLD}"
            f"{self._get_emoji(signal)} {signal.strength.value} {signal.signal_type.value} SIGNAL"
            f"{RESET}"
        )
        print(f"{CYAN}Symbol:{RESET} {signal.symbol}")
        print(f"{CYAN}Price:{RESET} ${signal.price:.2f}")
        print(f"{CYAN}Score:{RESET} {signal_color}{signal.score:.1f}/100{RESET}")
        print(f"{CYAN}Time:{RESET} {signal.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

        if signal.stop_loss:
            print(f"{CYAN}Stop Loss:{RESET} ${signal.stop_loss:.2f}")
        if signal.take_profit:
            print(f"{CYAN}Take Profit:{RESET} ${signal.take_profit:.2f}")

        if signal.indicators:
            print(f"\n{BLUE}Top Indicators:{RESET}")
            sorted_indicators = sorted(
                signal.indicators.items(),
                key=lambda x: abs(x[1].get("confidence", 0)),
                reverse=True,
            )[:5]
            for name, data in sorted_indicators:
                ind_signal = data["signal"]
                if "BUY" in ind_signal:
                    ind_color = GREEN
                elif "SELL" in ind_signal:
                    ind_color = RED
                else:
                    ind_color = YELLOW
                print(
                    f"  • {name}: {ind_color}{ind_signal}{RESET} "
                    f"({data['confidence']:.0%})"
                )

        print(f"{BOLD}{'=' * 50}{RESET}\n")


class FileChannel(AlertChannel):
    """File-based alert channel for logging signals."""

    def __init__(
        self,
        file_path: str = "alerts.log",
        json_format: bool = False,
    ):
        super().__init__("File")
        self.file_path = Path(file_path)
        self.json_format = json_format

        # Ensure directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def send(self, signal: Signal) -> bool:
        """Write alert to file."""
        try:
            with open(self.file_path, "a") as f:
                if self.json_format:
                    f.write(json.dumps(signal.to_dict()) + "\n")
                else:
                    f.write(f"\n{'=' * 50}\n")
                    f.write(self.format_message(signal))
                    f.write(f"\n{'=' * 50}\n")
            return True
        except Exception as e:
            logger.error(f"File alert failed: {e}")
            return False


class WebhookChannel(AlertChannel):
    """Webhook alert channel for external integrations."""

    def __init__(
        self,
        url: str,
        headers: Optional[dict] = None,
        timeout: int = 10,
    ):
        super().__init__("Webhook")
        self.url = url
        self.headers = headers or {"Content-Type": "application/json"}
        self.timeout = timeout

    def send(self, signal: Signal) -> bool:
        """Send alert via webhook."""
        try:
            import requests

            payload = {
                "signal": signal.to_dict(),
                "message": self.format_message(signal),
                "timestamp": datetime.now().isoformat(),
            }

            response = requests.post(
                self.url,
                json=payload,
                headers=self.headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return True

        except ImportError:
            logger.error("requests library required for webhook alerts")
            return False
        except Exception as e:
            logger.error(f"Webhook alert failed: {e}")
            return False


class SlackChannel(AlertChannel):
    """Slack alert channel."""

    def __init__(self, webhook_url: str):
        super().__init__("Slack")
        self.webhook_url = webhook_url

    def send(self, signal: Signal) -> bool:
        """Send alert to Slack."""
        try:
            import requests

            # Format as Slack blocks for rich formatting
            color = "#36a64f" if signal.signal_type.value == "BUY" else "#ff0000"
            if signal.signal_type.value == "HOLD":
                color = "#ffcc00"

            payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": f"{self._get_emoji(signal)} {signal.strength.value} {signal.signal_type.value}: {signal.symbol}",
                        "fields": [
                            {"title": "Price", "value": f"${signal.price:.2f}", "short": True},
                            {"title": "Score", "value": f"{signal.score:.1f}/100", "short": True},
                            {"title": "Stop Loss", "value": f"${signal.stop_loss:.2f}" if signal.stop_loss else "N/A", "short": True},
                            {"title": "Take Profit", "value": f"${signal.take_profit:.2f}" if signal.take_profit else "N/A", "short": True},
                        ],
                        "footer": "Live Tracker",
                        "ts": int(signal.timestamp.timestamp()),
                    }
                ]
            }

            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            return True

        except Exception as e:
            logger.error(f"Slack alert failed: {e}")
            return False


class DiscordChannel(AlertChannel):
    """Discord alert channel."""

    def __init__(self, webhook_url: str):
        super().__init__("Discord")
        self.webhook_url = webhook_url

    def send(self, signal: Signal) -> bool:
        """Send alert to Discord."""
        try:
            import requests

            # Format as Discord embed
            color = 0x36A64F if signal.signal_type.value == "BUY" else 0xFF0000
            if signal.signal_type.value == "HOLD":
                color = 0xFFCC00

            embed = {
                "title": f"{self._get_emoji(signal)} {signal.strength.value} {signal.signal_type.value}: {signal.symbol}",
                "color": color,
                "fields": [
                    {"name": "Price", "value": f"${signal.price:.2f}", "inline": True},
                    {"name": "Score", "value": f"{signal.score:.1f}/100", "inline": True},
                    {"name": "Stop Loss", "value": f"${signal.stop_loss:.2f}" if signal.stop_loss else "N/A", "inline": True},
                    {"name": "Take Profit", "value": f"${signal.take_profit:.2f}" if signal.take_profit else "N/A", "inline": True},
                ],
                "footer": {"text": "Live Tracker"},
                "timestamp": signal.timestamp.isoformat(),
            }

            payload = {"embeds": [embed]}

            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            return True

        except Exception as e:
            logger.error(f"Discord alert failed: {e}")
            return False
