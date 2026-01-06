"""
Signal Types and Data Classes.

Defines the data structures used for trading signals.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class SignalType(Enum):
    """Type of trading signal."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class SignalStrength(Enum):
    """Strength/confidence of the signal."""

    STRONG = "STRONG"      # High confidence, multiple indicators aligned
    MODERATE = "MODERATE"  # Good confidence, majority of indicators aligned
    WEAK = "WEAK"          # Low confidence, mixed signals
    NEUTRAL = "NEUTRAL"    # No clear direction


@dataclass
class Signal:
    """
    Trading signal with all relevant information.

    Attributes:
        symbol: Ticker symbol
        signal_type: BUY, SELL, or HOLD
        strength: Signal strength/confidence level
        score: Numeric score from -100 (strong sell) to +100 (strong buy)
        price: Current price when signal was generated
        timestamp: When the signal was generated
        indicators: Individual indicator signals that contributed
        description: Human-readable summary of the signal
        stop_loss: Suggested stop-loss price
        take_profit: Suggested take-profit price
        risk_reward: Risk/reward ratio
    """

    symbol: str
    signal_type: SignalType
    strength: SignalStrength
    score: float  # -100 to +100
    price: float
    timestamp: datetime = field(default_factory=datetime.now)
    indicators: dict = field(default_factory=dict)
    description: str = ""
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_reward: Optional[float] = None

    def __post_init__(self):
        """Generate description if not provided."""
        if not self.description:
            self.description = self._generate_description()

    def _generate_description(self) -> str:
        """Generate a human-readable description of the signal."""
        strength_desc = {
            SignalStrength.STRONG: "Strong",
            SignalStrength.MODERATE: "Moderate",
            SignalStrength.WEAK: "Weak",
            SignalStrength.NEUTRAL: "Neutral",
        }

        if self.signal_type == SignalType.HOLD:
            return f"HOLD {self.symbol} - No clear direction (Score: {self.score:.1f})"

        action = "BUY" if self.signal_type == SignalType.BUY else "SELL"
        return (
            f"{strength_desc[self.strength]} {action} signal for {self.symbol} "
            f"at ${self.price:.2f} (Score: {self.score:.1f})"
        )

    def to_dict(self) -> dict:
        """Convert signal to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "signal_type": self.signal_type.value,
            "strength": self.strength.value,
            "score": self.score,
            "price": self.price,
            "timestamp": self.timestamp.isoformat(),
            "indicators": self.indicators,
            "description": self.description,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "risk_reward": self.risk_reward,
        }

    @property
    def is_actionable(self) -> bool:
        """Check if signal is strong enough to act on."""
        return (
            self.signal_type != SignalType.HOLD
            and self.strength in [SignalStrength.STRONG, SignalStrength.MODERATE]
        )

    @property
    def is_buy(self) -> bool:
        """Check if this is a buy signal."""
        return self.signal_type == SignalType.BUY

    @property
    def is_sell(self) -> bool:
        """Check if this is a sell signal."""
        return self.signal_type == SignalType.SELL

    def __str__(self) -> str:
        return self.description

    def __repr__(self) -> str:
        return (
            f"Signal(symbol={self.symbol!r}, type={self.signal_type.value}, "
            f"strength={self.strength.value}, score={self.score:.1f})"
        )


@dataclass
class AlertThresholds:
    """Configurable thresholds for generating alerts."""

    # Score thresholds
    strong_buy_threshold: float = 60.0    # Score >= this = strong buy
    buy_threshold: float = 30.0           # Score >= this = buy
    sell_threshold: float = -30.0         # Score <= this = sell
    strong_sell_threshold: float = -60.0  # Score <= this = strong sell

    # Confidence thresholds
    min_confidence: float = 0.5           # Minimum indicator confidence
    min_indicators: int = 3               # Minimum agreeing indicators

    # Alert filters
    alert_on_strong_only: bool = False    # Only alert on strong signals
    alert_on_new_only: bool = True        # Only alert on new signals (not repeats)

    def get_signal_type(self, score: float) -> SignalType:
        """Determine signal type from score."""
        if score >= self.buy_threshold:
            return SignalType.BUY
        elif score <= self.sell_threshold:
            return SignalType.SELL
        else:
            return SignalType.HOLD

    def get_signal_strength(self, score: float) -> SignalStrength:
        """Determine signal strength from score."""
        abs_score = abs(score)
        if abs_score >= abs(self.strong_buy_threshold):
            return SignalStrength.STRONG
        elif abs_score >= abs(self.buy_threshold):
            return SignalStrength.MODERATE
        elif abs_score >= abs(self.buy_threshold) * 0.5:
            return SignalStrength.WEAK
        else:
            return SignalStrength.NEUTRAL
