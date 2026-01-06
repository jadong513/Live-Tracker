"""
Live Tracker.

Real-time market monitoring with signal generation and alerts.
"""

import asyncio
import logging
import signal as sys_signal
import time
from datetime import datetime
from typing import Callable, Optional

from live_tracker.alerts.manager import AlertManager
from live_tracker.data.fetcher import MarketDataFetcher
from live_tracker.signals.engine import SignalEngine
from live_tracker.signals.types import Signal, SignalType

logger = logging.getLogger(__name__)


class LiveTracker:
    """
    Real-time market tracker with live monitoring and alerts.

    Features:
    - Continuous monitoring of configured symbols
    - Automatic signal generation at configurable intervals
    - Multi-channel alert system
    - Watchlist management
    - Performance tracking
    """

    def __init__(
        self,
        symbols: Optional[list[str]] = None,
        data_fetcher: Optional[MarketDataFetcher] = None,
        signal_engine: Optional[SignalEngine] = None,
        alert_manager: Optional[AlertManager] = None,
        scan_interval: int = 60,
        data_period: str = "3mo",
        data_interval: str = "1d",
    ):
        """
        Initialize the live tracker.

        Args:
            symbols: List of symbols to track
            data_fetcher: Market data fetcher instance
            signal_engine: Signal generation engine
            alert_manager: Alert manager instance
            scan_interval: Seconds between scans
            data_period: Historical data period for analysis
            data_interval: Data interval (1d, 1h, etc.)
        """
        self.symbols = symbols or []
        self.data_fetcher = data_fetcher or MarketDataFetcher()
        self.signal_engine = signal_engine or SignalEngine()
        self.alert_manager = alert_manager or AlertManager()
        self.scan_interval = scan_interval
        self.data_period = data_period
        self.data_interval = data_interval

        # Tracking state
        self._running = False
        self._last_signals: dict[str, Signal] = {}
        self._scan_count = 0
        self._start_time: Optional[datetime] = None

        # Callbacks
        self._on_signal: Optional[Callable[[Signal], None]] = None
        self._on_scan_complete: Optional[Callable[[list[Signal]], None]] = None

    def add_symbol(self, symbol: str):
        """Add a symbol to the watchlist."""
        symbol = symbol.upper()
        if symbol not in self.symbols:
            self.symbols.append(symbol)
            logger.info(f"Added {symbol} to watchlist")

    def remove_symbol(self, symbol: str):
        """Remove a symbol from the watchlist."""
        symbol = symbol.upper()
        if symbol in self.symbols:
            self.symbols.remove(symbol)
            self._last_signals.pop(symbol, None)
            logger.info(f"Removed {symbol} from watchlist")

    def set_watchlist(self, symbols: list[str]):
        """Set the entire watchlist."""
        self.symbols = [s.upper() for s in symbols]
        logger.info(f"Watchlist set to: {self.symbols}")

    def on_signal(self, callback: Callable[[Signal], None]):
        """Register callback for new signals."""
        self._on_signal = callback

    def on_scan_complete(self, callback: Callable[[list[Signal]], None]):
        """Register callback for scan completion."""
        self._on_scan_complete = callback

    def scan_once(self) -> list[Signal]:
        """
        Perform a single scan of all symbols.

        Returns:
            List of signals for all symbols
        """
        signals = []
        self._scan_count += 1

        logger.info(f"Starting scan #{self._scan_count} of {len(self.symbols)} symbols...")

        for symbol in self.symbols:
            try:
                # Fetch data
                df = self.data_fetcher.get_data_with_indicators(
                    symbol,
                    period=self.data_period,
                    interval=self.data_interval,
                )

                if df.empty:
                    logger.warning(f"No data for {symbol}")
                    continue

                # Generate signal
                signal = self.signal_engine.analyze(df, symbol)
                signals.append(signal)
                self._last_signals[symbol] = signal

                # Trigger callback
                if self._on_signal:
                    self._on_signal(signal)

                # Process alert
                self.alert_manager.send_alert(signal)

            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")

        # Trigger completion callback
        if self._on_scan_complete:
            self._on_scan_complete(signals)

        logger.info(
            f"Scan #{self._scan_count} complete. "
            f"Generated {len(signals)} signals, "
            f"{sum(1 for s in signals if s.is_actionable)} actionable."
        )

        return signals

    def start(self, blocking: bool = True):
        """
        Start continuous monitoring.

        Args:
            blocking: If True, blocks until stopped. If False, returns immediately.
        """
        self._running = True
        self._start_time = datetime.now()

        logger.info(
            f"Starting Live Tracker monitoring {len(self.symbols)} symbols "
            f"every {self.scan_interval} seconds..."
        )

        if blocking:
            self._run_loop()
        else:
            import threading
            thread = threading.Thread(target=self._run_loop, daemon=True)
            thread.start()

    def _run_loop(self):
        """Main monitoring loop."""
        # Handle graceful shutdown
        def handle_shutdown(signum, frame):
            logger.info("Received shutdown signal...")
            self.stop()

        sys_signal.signal(sys_signal.SIGINT, handle_shutdown)
        sys_signal.signal(sys_signal.SIGTERM, handle_shutdown)

        while self._running:
            try:
                self.scan_once()

                # Wait for next scan
                if self._running:
                    logger.debug(f"Waiting {self.scan_interval}s until next scan...")
                    time.sleep(self.scan_interval)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                if self._running:
                    time.sleep(5)  # Brief pause before retry

        logger.info("Live Tracker stopped.")

    async def start_async(self):
        """Start monitoring asynchronously."""
        self._running = True
        self._start_time = datetime.now()

        logger.info(
            f"Starting async Live Tracker monitoring {len(self.symbols)} symbols..."
        )

        while self._running:
            try:
                self.scan_once()

                if self._running:
                    await asyncio.sleep(self.scan_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in async monitoring loop: {e}")
                if self._running:
                    await asyncio.sleep(5)

    def stop(self):
        """Stop monitoring."""
        self._running = False
        logger.info("Stopping Live Tracker...")

    def get_last_signal(self, symbol: str) -> Optional[Signal]:
        """Get the last signal for a symbol."""
        return self._last_signals.get(symbol.upper())

    def get_all_signals(self) -> dict[str, Signal]:
        """Get all latest signals."""
        return self._last_signals.copy()

    def get_actionable_signals(self) -> list[Signal]:
        """Get only actionable signals from the last scan."""
        return [s for s in self._last_signals.values() if s.is_actionable]

    def get_buy_signals(self) -> list[Signal]:
        """Get all buy signals from the last scan."""
        return [
            s for s in self._last_signals.values()
            if s.signal_type == SignalType.BUY
        ]

    def get_sell_signals(self) -> list[Signal]:
        """Get all sell signals from the last scan."""
        return [
            s for s in self._last_signals.values()
            if s.signal_type == SignalType.SELL
        ]

    def get_status(self) -> dict:
        """Get tracker status information."""
        uptime = None
        if self._start_time:
            uptime = (datetime.now() - self._start_time).total_seconds()

        actionable = self.get_actionable_signals()
        buy_signals = [s for s in actionable if s.is_buy]
        sell_signals = [s for s in actionable if s.is_sell]

        return {
            "running": self._running,
            "symbols_count": len(self.symbols),
            "symbols": self.symbols,
            "scan_count": self._scan_count,
            "scan_interval": self.scan_interval,
            "uptime_seconds": uptime,
            "start_time": self._start_time.isoformat() if self._start_time else None,
            "last_scan_signals": len(self._last_signals),
            "actionable_signals": len(actionable),
            "buy_signals": len(buy_signals),
            "sell_signals": len(sell_signals),
            "alert_stats": self.alert_manager.get_stats(),
        }

    def print_summary(self):
        """Print a formatted summary of current signals."""
        print("\n" + "=" * 60)
        print(f"📊 LIVE TRACKER SUMMARY - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        if not self._last_signals:
            print("No signals generated yet.")
            return

        # Sort by score
        sorted_signals = sorted(
            self._last_signals.values(),
            key=lambda s: s.score,
            reverse=True,
        )

        # Top buys
        buys = [s for s in sorted_signals if s.is_buy]
        if buys:
            print("\n🟢 TOP BUY SIGNALS:")
            for s in buys[:5]:
                strength_icon = "🚀" if s.strength.value == "STRONG" else "📈"
                print(f"  {strength_icon} {s.symbol}: Score {s.score:.1f} @ ${s.price:.2f}")

        # Top sells
        sells = [s for s in sorted_signals if s.is_sell]
        if sells:
            print("\n🔴 TOP SELL SIGNALS:")
            for s in sells[:5]:
                strength_icon = "🔻" if s.strength.value == "STRONG" else "📉"
                print(f"  {strength_icon} {s.symbol}: Score {s.score:.1f} @ ${s.price:.2f}")

        # Neutral/Hold
        holds = [s for s in sorted_signals if not s.is_buy and not s.is_sell]
        if holds:
            print(f"\n⚪ NEUTRAL: {len(holds)} symbols")

        print("\n" + "=" * 60)


class WatchlistManager:
    """Manages multiple watchlists for different strategies."""

    def __init__(self):
        self.watchlists: dict[str, list[str]] = {
            "default": [],
        }

    def create_watchlist(self, name: str, symbols: Optional[list[str]] = None):
        """Create a new watchlist."""
        self.watchlists[name] = symbols or []

    def delete_watchlist(self, name: str):
        """Delete a watchlist."""
        if name != "default":
            self.watchlists.pop(name, None)

    def add_to_watchlist(self, name: str, symbol: str):
        """Add symbol to a watchlist."""
        if name in self.watchlists:
            symbol = symbol.upper()
            if symbol not in self.watchlists[name]:
                self.watchlists[name].append(symbol)

    def remove_from_watchlist(self, name: str, symbol: str):
        """Remove symbol from a watchlist."""
        if name in self.watchlists:
            symbol = symbol.upper()
            if symbol in self.watchlists[name]:
                self.watchlists[name].remove(symbol)

    def get_watchlist(self, name: str) -> list[str]:
        """Get symbols in a watchlist."""
        return self.watchlists.get(name, [])

    def get_all_symbols(self) -> list[str]:
        """Get all unique symbols across all watchlists."""
        all_symbols = set()
        for symbols in self.watchlists.values():
            all_symbols.update(symbols)
        return list(all_symbols)

    # Pre-defined watchlists for common use cases
    @classmethod
    def create_default_watchlists(cls) -> "WatchlistManager":
        """Create manager with common default watchlists."""
        manager = cls()

        # Tech giants
        manager.create_watchlist("tech", [
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"
        ])

        # Major indices ETFs
        manager.create_watchlist("indices", [
            "SPY", "QQQ", "IWM", "DIA"
        ])

        # Crypto
        manager.create_watchlist("crypto", [
            "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD"
        ])

        # Financials
        manager.create_watchlist("financials", [
            "JPM", "BAC", "GS", "MS", "C"
        ])

        # High volatility / momentum
        manager.create_watchlist("momentum", [
            "NVDA", "AMD", "TSLA", "COIN", "MSTR"
        ])

        return manager
