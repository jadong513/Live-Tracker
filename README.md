# Live Tracker 📈

A professional-grade live market monitoring system with institutional-quality technical indicators, real-time signal generation, and multi-channel alerts.

## Features

### Technical Indicators
- **Momentum**: RSI, Stochastic, Williams %R
- **Trend**: SMA, EMA, MACD, ADX, SuperTrend
- **Volatility**: Bollinger Bands, ATR, Keltner Channel
- **Volume**: OBV, VWAP, Volume Profile
- **Support/Resistance**: Pivot Points, Fibonacci Levels

### Signal Generation
- Weighted indicator voting system
- Confidence-based scoring (-100 to +100)
- Automatic stop-loss and take-profit calculation
- Risk/reward ratio optimization

### Alert System
- Console alerts with rich formatting
- File logging (JSON or text)
- Webhook integration
- Slack notifications
- Discord notifications
- Alert deduplication and cooldown

### Live Monitoring
- Continuous symbol tracking
- Configurable scan intervals
- Multiple watchlist support
- Performance tracking

## Installation

```bash
# Clone the repository
git clone https://github.com/jadong513/Live-Tracker.git
cd Live-Tracker

# Install with pip
pip install -e .

# Or install with optional dependencies
pip install -e ".[notifications]"  # For Slack/Discord
pip install -e ".[dev]"            # For development
```

## Quick Start

### Scan Symbols
```bash
# Scan default symbols
live-tracker scan

# Scan specific symbols
live-tracker scan -s AAPL,MSFT,NVDA,TSLA

# Scan a watchlist
live-tracker scan -w tech

# Detailed output
live-tracker scan -s NVDA -d
```

### Analyze a Symbol
```bash
# Get detailed analysis with all indicators
live-tracker analyze NVDA
```

### Live Monitoring
```bash
# Start monitoring default symbols
live-tracker monitor

# Monitor specific symbols every 30 seconds
live-tracker monitor -s AAPL,TSLA -i 30

# Monitor a watchlist
live-tracker monitor -w crypto
```

### View Watchlists
```bash
live-tracker watchlists
```

## Configuration

### Create Config File
```bash
live-tracker config --init
```

### View Config
```bash
live-tracker config --show
```

### Set Config Values
```bash
live-tracker config --set scan_interval=30
live-tracker config --set min_alert_score=40
live-tracker config --set symbols=AAPL,MSFT,NVDA
```

### Environment Variables
```bash
export TRACKER_SYMBOLS=AAPL,MSFT,NVDA
export TRACKER_INTERVAL=60
export TRACKER_MIN_SCORE=30
export SLACK_WEBHOOK=https://hooks.slack.com/...
export DISCORD_WEBHOOK=https://discord.com/api/webhooks/...
```

## Python API

```python
from live_tracker import LiveTracker, SignalEngine
from live_tracker.data import MarketDataFetcher

# Analyze a single symbol
fetcher = MarketDataFetcher()
engine = SignalEngine()

df = fetcher.get_data_with_indicators("NVDA", period="3mo")
signal = engine.analyze(df, "NVDA")

print(f"Signal: {signal.signal_type.value}")
print(f"Score: {signal.score:.1f}")
print(f"Stop Loss: ${signal.stop_loss:.2f}")
print(f"Take Profit: ${signal.take_profit:.2f}")

# Start live monitoring
tracker = LiveTracker(
    symbols=["AAPL", "MSFT", "NVDA", "TSLA"],
    scan_interval=60,
)
tracker.start()
```

## Signal Interpretation

| Score Range | Signal | Action |
|-------------|--------|--------|
| 60 to 100 | Strong Buy | High confidence buy opportunity |
| 30 to 60 | Buy | Moderate buy opportunity |
| -30 to 30 | Hold | No clear direction |
| -60 to -30 | Sell | Moderate sell signal |
| -100 to -60 | Strong Sell | High confidence sell signal |

## Indicator Weights

Default weights (customizable):
- **MACD**: 1.5 (trend + momentum, highly reliable)
- **SuperTrend**: 1.3 (clear trend signals)
- **RSI**: 1.2 (reliable at extremes)
- **SMA(200)**: 1.2 (major trend indicator)
- **ADX**: 1.0 (trend strength)
- **Bollinger Bands**: 1.0 (volatility/mean reversion)
- **EMA(50)**: 1.0 (medium-term trend)
- **OBV**: 0.9 (volume confirmation)
- **EMA(20)**: 0.8 (short-term trend)
- **Stochastic**: 0.8 (momentum confirmation)
- **VWAP**: 0.8 (institutional reference)
- **Pivot Points**: 0.7 (support/resistance)

## Available Watchlists

| Name | Symbols |
|------|---------|
| tech | AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA, AMD, INTC, CRM |
| indices | SPY, QQQ, IWM, DIA, VTI |
| crypto | BTC-USD, ETH-USD, SOL-USD, XRP-USD, ADA-USD, DOGE-USD |
| financials | JPM, BAC, GS, MS, C, WFC, BLK |
| energy | XOM, CVX, COP, SLB, EOG |
| healthcare | JNJ, UNH, PFE, ABBV, MRK, LLY |
| consumer | WMT, COST, HD, MCD, NKE, SBUX |

## Disclaimer

This software is for educational and research purposes only. It is not financial advice. Always do your own research and consult with a qualified financial advisor before making investment decisions. Trading involves significant risk of loss.

## License

MIT License
