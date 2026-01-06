#!/usr/bin/env python3
"""
Basic usage example for Live Tracker.

This script demonstrates how to use the Live Tracker library
for market analysis and signal generation.
"""

from live_tracker import LiveTracker, SignalEngine
from live_tracker.data import MarketDataFetcher
from live_tracker.alerts import AlertManager, ConsoleChannel, FileChannel


def analyze_single_symbol():
    """Analyze a single symbol and print the signal."""
    print("=" * 60)
    print("SINGLE SYMBOL ANALYSIS")
    print("=" * 60)

    # Initialize components
    fetcher = MarketDataFetcher()
    engine = SignalEngine()

    # Fetch data for NVDA
    symbol = "NVDA"
    print(f"\nFetching data for {symbol}...")

    df = fetcher.get_data_with_indicators(symbol, period="3mo", interval="1d")

    if df.empty:
        print(f"No data available for {symbol}")
        return

    print(f"Got {len(df)} data points")

    # Generate signal
    signal = engine.analyze(df, symbol)

    # Display results
    print(f"\n{'='*40}")
    print(f"SIGNAL: {signal.strength.value} {signal.signal_type.value}")
    print(f"{'='*40}")
    print(f"Symbol: {signal.symbol}")
    print(f"Price: ${signal.price:.2f}")
    print(f"Score: {signal.score:.1f} / 100")
    print(f"Stop Loss: ${signal.stop_loss:.2f}" if signal.stop_loss else "Stop Loss: N/A")
    print(f"Take Profit: ${signal.take_profit:.2f}" if signal.take_profit else "Take Profit: N/A")

    print("\nTop Indicators:")
    for name, data in list(signal.indicators.items())[:5]:
        print(f"  - {name}: {data['signal']} ({data['confidence']:.0%})")


def scan_multiple_symbols():
    """Scan multiple symbols and find opportunities."""
    print("\n" + "=" * 60)
    print("MULTI-SYMBOL SCAN")
    print("=" * 60)

    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "AMD"]

    fetcher = MarketDataFetcher()
    engine = SignalEngine()

    signals = []
    for symbol in symbols:
        print(f"Analyzing {symbol}...")
        df = fetcher.get_data_with_indicators(symbol, period="3mo")
        if not df.empty:
            signal = engine.analyze(df, symbol)
            signals.append(signal)

    # Sort by score
    signals.sort(key=lambda s: s.score, reverse=True)

    print("\nRESULTS (sorted by score):")
    print("-" * 50)
    for s in signals:
        emoji = "🟢" if s.is_buy else "🔴" if s.is_sell else "⚪"
        print(f"{emoji} {s.symbol:6} | Score: {s.score:6.1f} | {s.signal_type.value:4} | ${s.price:.2f}")


def live_monitoring_example():
    """Example of live monitoring (runs briefly for demo)."""
    print("\n" + "=" * 60)
    print("LIVE MONITORING DEMO")
    print("=" * 60)

    # Setup with minimal symbols for demo
    symbols = ["SPY", "QQQ", "NVDA"]

    # Create alert manager with console output
    alert_manager = AlertManager(
        channels=[
            ConsoleChannel(use_color=True),
            FileChannel(file_path="demo_alerts.log"),
        ],
        min_score=20.0,  # Lower threshold for demo
    )

    # Create tracker
    tracker = LiveTracker(
        symbols=symbols,
        alert_manager=alert_manager,
        scan_interval=60,  # 1 minute intervals
    )

    # Run a single scan (for demo purposes)
    print(f"\nScanning {len(symbols)} symbols...")
    signals = tracker.scan_once()

    print("\nScan Results:")
    for s in signals:
        print(f"  {s.symbol}: {s.signal_type.value} (Score: {s.score:.1f})")

    # Print status
    status = tracker.get_status()
    print(f"\nTracker Status:")
    print(f"  Symbols monitored: {status['symbols_count']}")
    print(f"  Actionable signals: {status['actionable_signals']}")
    print(f"  Buy signals: {status['buy_signals']}")
    print(f"  Sell signals: {status['sell_signals']}")

    # Note: To run continuous monitoring, uncomment below:
    # print("\nStarting continuous monitoring (Ctrl+C to stop)...")
    # tracker.start(blocking=True)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("LIVE TRACKER - EXAMPLE USAGE")
    print("=" * 60 + "\n")

    # Run examples
    analyze_single_symbol()
    scan_multiple_symbols()
    live_monitoring_example()

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
