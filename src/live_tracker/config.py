"""
Configuration Management.

Handles loading and saving tracker configuration.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class TrackerConfig:
    """Configuration for the Live Tracker."""

    # Symbols to track
    symbols: list[str] = field(default_factory=lambda: [
        "SPY", "QQQ", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA"
    ])

    # Scanning settings
    scan_interval: int = 60  # seconds between scans
    data_period: str = "3mo"  # historical data period
    data_interval: str = "1d"  # data interval

    # Alert settings
    min_alert_score: float = 30.0  # minimum score to trigger alert
    alert_cooldown: int = 15  # minutes between repeat alerts

    # Notification channels
    console_alerts: bool = True
    file_alerts: bool = True
    alert_file: str = "alerts.log"
    webhook_url: Optional[str] = None
    slack_webhook: Optional[str] = None
    discord_webhook: Optional[str] = None

    # Indicator weights (optional overrides)
    indicator_weights: dict = field(default_factory=dict)

    # API keys (for premium data sources)
    alpha_vantage_key: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TrackerConfig":
        """Create config from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def save(self, path: str = "config.json"):
        """Save config to file."""
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str = "config.json") -> "TrackerConfig":
        """Load config from file."""
        if not Path(path).exists():
            return cls()

        with open(path) as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_env(cls) -> "TrackerConfig":
        """Create config from environment variables."""
        config = cls()

        # Override with environment variables
        if symbols := os.getenv("TRACKER_SYMBOLS"):
            config.symbols = [s.strip() for s in symbols.split(",")]

        if interval := os.getenv("TRACKER_INTERVAL"):
            config.scan_interval = int(interval)

        if min_score := os.getenv("TRACKER_MIN_SCORE"):
            config.min_alert_score = float(min_score)

        if webhook := os.getenv("TRACKER_WEBHOOK"):
            config.webhook_url = webhook

        if slack := os.getenv("SLACK_WEBHOOK"):
            config.slack_webhook = slack

        if discord := os.getenv("DISCORD_WEBHOOK"):
            config.discord_webhook = discord

        if av_key := os.getenv("ALPHA_VANTAGE_KEY"):
            config.alpha_vantage_key = av_key

        return config


# Default watchlists
DEFAULT_WATCHLISTS = {
    "tech": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AMD", "INTC", "CRM"],
    "indices": ["SPY", "QQQ", "IWM", "DIA", "VTI"],
    "crypto": ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD", "DOGE-USD"],
    "financials": ["JPM", "BAC", "GS", "MS", "C", "WFC", "BLK"],
    "energy": ["XOM", "CVX", "COP", "SLB", "EOG"],
    "healthcare": ["JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY"],
    "consumer": ["WMT", "COST", "HD", "MCD", "NKE", "SBUX"],
}


def get_default_symbols() -> list[str]:
    """Get default symbols for tracking."""
    return [
        # Major tech
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
        # Indices
        "SPY", "QQQ",
        # Volatile/Momentum
        "TSLA", "AMD",
    ]
