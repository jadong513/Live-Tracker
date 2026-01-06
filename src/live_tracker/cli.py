"""
Command Line Interface.

Professional CLI for the Live Tracker market monitoring system.
"""

import argparse
import logging
import sys
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout

from live_tracker.config import TrackerConfig, DEFAULT_WATCHLISTS, get_default_symbols
from live_tracker.data.fetcher import MarketDataFetcher
from live_tracker.signals.engine import SignalEngine
from live_tracker.signals.types import SignalType
from live_tracker.alerts.manager import AlertManager
from live_tracker.alerts.channels import (
    ConsoleChannel,
    FileChannel,
    WebhookChannel,
    SlackChannel,
    DiscordChannel,
)
from live_tracker.tracker import LiveTracker

console = Console()


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("tracker.log"),
        ]
    )


def create_alert_manager(config: TrackerConfig) -> AlertManager:
    """Create alert manager from config."""
    channels = []

    if config.console_alerts:
        channels.append(ConsoleChannel(use_color=True))

    if config.file_alerts:
        channels.append(FileChannel(file_path=config.alert_file))

    if config.webhook_url:
        channels.append(WebhookChannel(url=config.webhook_url))

    if config.slack_webhook:
        channels.append(SlackChannel(webhook_url=config.slack_webhook))

    if config.discord_webhook:
        channels.append(DiscordChannel(webhook_url=config.discord_webhook))

    return AlertManager(
        channels=channels,
        min_score=config.min_alert_score,
        cooldown_minutes=config.alert_cooldown,
    )


def cmd_scan(args):
    """Run a single scan of symbols."""
    config = TrackerConfig.load() if args.config else TrackerConfig()

    # Override symbols if provided
    if args.symbols:
        config.symbols = [s.strip().upper() for s in args.symbols.split(",")]
    elif args.watchlist:
        config.symbols = DEFAULT_WATCHLISTS.get(args.watchlist, get_default_symbols())

    console.print(f"\n[bold cyan]🔍 Scanning {len(config.symbols)} symbols...[/bold cyan]\n")

    # Initialize components
    fetcher = MarketDataFetcher()
    engine = SignalEngine()

    # Scan and collect results
    results = []
    with console.status("[bold green]Analyzing markets...") as status:
        for i, symbol in enumerate(config.symbols):
            status.update(f"[bold green]Analyzing {symbol} ({i+1}/{len(config.symbols)})...")

            try:
                df = fetcher.get_data_with_indicators(symbol, period="3mo", interval="1d")
                if not df.empty:
                    signal = engine.analyze(df, symbol)
                    results.append(signal)
            except Exception as e:
                console.print(f"[red]Error scanning {symbol}: {e}[/red]")

    # Display results
    display_scan_results(results, args.detailed)


def display_scan_results(signals: list, detailed: bool = False):
    """Display scan results in a formatted table."""
    if not signals:
        console.print("[yellow]No signals generated.[/yellow]")
        return

    # Sort by score
    signals.sort(key=lambda s: s.score, reverse=True)

    # Create table
    table = Table(title="📊 Market Scan Results", show_header=True, header_style="bold magenta")
    table.add_column("Symbol", style="cyan", width=10)
    table.add_column("Price", justify="right", width=12)
    table.add_column("Signal", width=10)
    table.add_column("Strength", width=10)
    table.add_column("Score", justify="right", width=10)
    if detailed:
        table.add_column("Stop Loss", justify="right", width=12)
        table.add_column("Take Profit", justify="right", width=12)

    for signal in signals:
        # Color coding
        if signal.signal_type == SignalType.BUY:
            signal_style = "[green]BUY[/green]"
            strength_style = f"[green]{signal.strength.value}[/green]"
            score_style = f"[green]{signal.score:.1f}[/green]"
        elif signal.signal_type == SignalType.SELL:
            signal_style = "[red]SELL[/red]"
            strength_style = f"[red]{signal.strength.value}[/red]"
            score_style = f"[red]{signal.score:.1f}[/red]"
        else:
            signal_style = "[yellow]HOLD[/yellow]"
            strength_style = f"[yellow]{signal.strength.value}[/yellow]"
            score_style = f"[yellow]{signal.score:.1f}[/yellow]"

        row = [
            signal.symbol,
            f"${signal.price:.2f}",
            signal_style,
            strength_style,
            score_style,
        ]

        if detailed:
            sl = f"${signal.stop_loss:.2f}" if signal.stop_loss else "N/A"
            tp = f"${signal.take_profit:.2f}" if signal.take_profit else "N/A"
            row.extend([sl, tp])

        table.add_row(*row)

    console.print(table)

    # Summary
    buys = [s for s in signals if s.signal_type == SignalType.BUY]
    sells = [s for s in signals if s.signal_type == SignalType.SELL]

    console.print(f"\n[bold]Summary:[/bold] {len(buys)} buy signals, {len(sells)} sell signals")

    # Top opportunities
    if buys:
        top_buy = max(buys, key=lambda s: s.score)
        console.print(f"[green]🚀 Top Buy: {top_buy.symbol} (Score: {top_buy.score:.1f})[/green]")

    if sells:
        top_sell = min(sells, key=lambda s: s.score)
        console.print(f"[red]🔻 Top Sell: {top_sell.symbol} (Score: {top_sell.score:.1f})[/red]")


def cmd_analyze(args):
    """Analyze a single symbol in detail."""
    symbol = args.symbol.upper()

    console.print(f"\n[bold cyan]📈 Detailed Analysis: {symbol}[/bold cyan]\n")

    fetcher = MarketDataFetcher()
    engine = SignalEngine()

    with console.status(f"[bold green]Fetching data for {symbol}..."):
        df = fetcher.get_data_with_indicators(symbol, period="6mo", interval="1d")

    if df.empty:
        console.print(f"[red]No data available for {symbol}[/red]")
        return

    signal = engine.analyze(df, symbol)

    # Display main signal
    if signal.signal_type == SignalType.BUY:
        color = "green"
        emoji = "🟢"
    elif signal.signal_type == SignalType.SELL:
        color = "red"
        emoji = "🔴"
    else:
        color = "yellow"
        emoji = "🟡"

    panel = Panel(
        f"""
[bold]{emoji} {signal.strength.value} {signal.signal_type.value}[/bold]

Price: ${signal.price:.2f}
Score: {signal.score:.1f}/100

Stop Loss: ${signal.stop_loss:.2f if signal.stop_loss else 'N/A'}
Take Profit: ${signal.take_profit:.2f if signal.take_profit else 'N/A'}
Risk/Reward: 1:{signal.risk_reward:.1f if signal.risk_reward else 'N/A'}
        """,
        title=f"[bold {color}]{symbol} Signal[/bold {color}]",
        border_style=color,
    )
    console.print(panel)

    # Indicator breakdown
    console.print("\n[bold]📊 Indicator Breakdown:[/bold]")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Indicator", width=25)
    table.add_column("Signal", width=15)
    table.add_column("Confidence", justify="right", width=12)
    table.add_column("Description", width=40)

    for name, data in signal.indicators.items():
        sig = data["signal"]
        if "BUY" in sig:
            sig_style = f"[green]{sig}[/green]"
        elif "SELL" in sig:
            sig_style = f"[red]{sig}[/red]"
        else:
            sig_style = f"[yellow]{sig}[/yellow]"

        table.add_row(
            name,
            sig_style,
            f"{data['confidence']:.0%}",
            data.get("description", "")[:40],
        )

    console.print(table)

    # Price info
    info = fetcher.get_info(symbol)
    if "error" not in info:
        console.print(f"\n[bold]ℹ️ Symbol Info:[/bold]")
        console.print(f"  Name: {info.get('name', 'N/A')}")
        console.print(f"  Sector: {info.get('sector', 'N/A')}")
        console.print(f"  52W High: ${info.get('52w_high', 0):.2f}")
        console.print(f"  52W Low: ${info.get('52w_low', 0):.2f}")
        console.print(f"  P/E Ratio: {info.get('pe_ratio', 'N/A')}")


def cmd_monitor(args):
    """Start live monitoring."""
    config = TrackerConfig.load() if args.config else TrackerConfig()

    # Override settings
    if args.symbols:
        config.symbols = [s.strip().upper() for s in args.symbols.split(",")]
    elif args.watchlist:
        config.symbols = DEFAULT_WATCHLISTS.get(args.watchlist, get_default_symbols())

    if args.interval:
        config.scan_interval = args.interval

    console.print(Panel(
        f"""
[bold cyan]🔴 LIVE TRACKER[/bold cyan]

Monitoring: {len(config.symbols)} symbols
Interval: {config.scan_interval} seconds
Symbols: {', '.join(config.symbols[:5])}{'...' if len(config.symbols) > 5 else ''}

[dim]Press Ctrl+C to stop[/dim]
        """,
        title="Starting Live Monitor",
        border_style="cyan",
    ))

    # Setup components
    alert_manager = create_alert_manager(config)
    tracker = LiveTracker(
        symbols=config.symbols,
        alert_manager=alert_manager,
        scan_interval=config.scan_interval,
    )

    # Define callback for scan completion
    def on_scan_complete(signals):
        console.print(f"\n[dim]{datetime.now().strftime('%H:%M:%S')} - Scan complete: {len(signals)} signals[/dim]")

    tracker.on_scan_complete(on_scan_complete)

    try:
        tracker.start(blocking=True)
    except KeyboardInterrupt:
        tracker.stop()
        console.print("\n[yellow]Monitoring stopped.[/yellow]")


def cmd_watchlists(args):
    """List available watchlists."""
    console.print("\n[bold cyan]📋 Available Watchlists[/bold cyan]\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Watchlist", style="cyan", width=15)
    table.add_column("Symbols", width=60)

    for name, symbols in DEFAULT_WATCHLISTS.items():
        table.add_row(name, ", ".join(symbols))

    console.print(table)
    console.print("\n[dim]Use --watchlist <name> to scan a specific watchlist[/dim]")


def cmd_config(args):
    """Manage configuration."""
    if args.show:
        config = TrackerConfig.load()
        console.print("\n[bold cyan]Current Configuration:[/bold cyan]\n")
        for key, value in config.to_dict().items():
            console.print(f"  {key}: {value}")

    elif args.init:
        config = TrackerConfig()
        config.save()
        console.print("[green]Configuration file created: config.json[/green]")

    elif args.set:
        key, value = args.set.split("=", 1)
        config = TrackerConfig.load()
        if hasattr(config, key):
            # Type conversion
            current_value = getattr(config, key)
            if isinstance(current_value, bool):
                value = value.lower() in ("true", "1", "yes")
            elif isinstance(current_value, int):
                value = int(value)
            elif isinstance(current_value, float):
                value = float(value)
            elif isinstance(current_value, list):
                value = [v.strip() for v in value.split(",")]

            setattr(config, key, value)
            config.save()
            console.print(f"[green]Set {key} = {value}[/green]")
        else:
            console.print(f"[red]Unknown config key: {key}[/red]")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Live Tracker - Professional Market Monitoring System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  live-tracker scan                    # Scan default symbols
  live-tracker scan -s AAPL,MSFT,TSLA  # Scan specific symbols
  live-tracker scan -w tech            # Scan tech watchlist
  live-tracker analyze NVDA            # Detailed analysis of NVDA
  live-tracker monitor                 # Start live monitoring
  live-tracker monitor -i 30           # Monitor every 30 seconds
  live-tracker watchlists              # Show available watchlists
        """
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("-c", "--config", action="store_true", help="Use config file")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Scan command
    scan_parser = subparsers.add_parser("scan", help="Run a single market scan")
    scan_parser.add_argument("-s", "--symbols", help="Comma-separated symbols to scan")
    scan_parser.add_argument("-w", "--watchlist", help="Watchlist name to scan")
    scan_parser.add_argument("-d", "--detailed", action="store_true", help="Show detailed output")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Detailed analysis of a symbol")
    analyze_parser.add_argument("symbol", help="Symbol to analyze")

    # Monitor command
    monitor_parser = subparsers.add_parser("monitor", help="Start live monitoring")
    monitor_parser.add_argument("-s", "--symbols", help="Comma-separated symbols to monitor")
    monitor_parser.add_argument("-w", "--watchlist", help="Watchlist name to monitor")
    monitor_parser.add_argument("-i", "--interval", type=int, help="Scan interval in seconds")

    # Watchlists command
    subparsers.add_parser("watchlists", help="Show available watchlists")

    # Config command
    config_parser = subparsers.add_parser("config", help="Manage configuration")
    config_group = config_parser.add_mutually_exclusive_group()
    config_group.add_argument("--show", action="store_true", help="Show current config")
    config_group.add_argument("--init", action="store_true", help="Create config file")
    config_group.add_argument("--set", help="Set config value (key=value)")

    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.command == "scan":
        cmd_scan(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "monitor":
        cmd_monitor(args)
    elif args.command == "watchlists":
        cmd_watchlists(args)
    elif args.command == "config":
        cmd_config(args)
    else:
        # Default: show help
        parser.print_help()


if __name__ == "__main__":
    main()
