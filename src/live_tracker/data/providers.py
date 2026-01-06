"""
Data Providers.

Modular data provider implementations for different market data sources.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


class DataProvider(ABC):
    """Abstract base class for market data providers."""

    @abstractmethod
    def get_historical(
        self,
        symbol: str,
        period: str = "1mo",
        interval: str = "1d",
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data.

        Args:
            symbol: Ticker symbol (e.g., 'AAPL', 'BTC-USD')
            period: Data period ('1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', 'max')
            interval: Data interval ('1m', '5m', '15m', '1h', '1d', '1wk', '1mo')

        Returns:
            DataFrame with columns: open, high, low, close, volume
        """
        pass

    @abstractmethod
    def get_quote(self, symbol: str) -> dict:
        """
        Fetch current quote for a symbol.

        Args:
            symbol: Ticker symbol

        Returns:
            Dictionary with current price, change, volume, etc.
        """
        pass

    @abstractmethod
    def get_info(self, symbol: str) -> dict:
        """
        Fetch symbol information.

        Args:
            symbol: Ticker symbol

        Returns:
            Dictionary with symbol info (name, sector, market cap, etc.)
        """
        pass


class YFinanceProvider(DataProvider):
    """
    Yahoo Finance data provider.

    Free, reliable data source for stocks, ETFs, crypto, and more.
    Good for daily and historical data, limited for real-time.
    """

    def __init__(self):
        try:
            import yfinance as yf
            self.yf = yf
            self._cache = {}
            self._cache_ttl = 60  # Cache TTL in seconds
        except ImportError:
            raise ImportError("yfinance is required. Install with: pip install yfinance")

    def _get_ticker(self, symbol: str):
        """Get or create a cached ticker object."""
        now = datetime.now()
        if symbol in self._cache:
            ticker, timestamp = self._cache[symbol]
            if (now - timestamp).seconds < self._cache_ttl:
                return ticker

        ticker = self.yf.Ticker(symbol)
        self._cache[symbol] = (ticker, now)
        return ticker

    def get_historical(
        self,
        symbol: str,
        period: str = "1mo",
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Fetch historical data from Yahoo Finance."""
        try:
            ticker = self._get_ticker(symbol)
            df = ticker.history(period=period, interval=interval)

            if df.empty:
                logger.warning(f"No data returned for {symbol}")
                return pd.DataFrame()

            # Normalize column names to lowercase
            df.columns = df.columns.str.lower()

            # Ensure required columns exist
            required_cols = ["open", "high", "low", "close", "volume"]
            for col in required_cols:
                if col not in df.columns:
                    logger.warning(f"Missing column {col} for {symbol}")
                    return pd.DataFrame()

            # Keep only required columns
            df = df[required_cols]

            return df

        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return pd.DataFrame()

    def get_quote(self, symbol: str) -> dict:
        """Fetch current quote from Yahoo Finance."""
        try:
            ticker = self._get_ticker(symbol)
            info = ticker.info

            # Get fast info for current price
            fast_info = ticker.fast_info

            return {
                "symbol": symbol,
                "price": fast_info.get("lastPrice", info.get("regularMarketPrice", 0)),
                "change": info.get("regularMarketChange", 0),
                "change_percent": info.get("regularMarketChangePercent", 0),
                "volume": info.get("regularMarketVolume", 0),
                "avg_volume": info.get("averageVolume", 0),
                "high": info.get("regularMarketDayHigh", 0),
                "low": info.get("regularMarketDayLow", 0),
                "open": info.get("regularMarketOpen", 0),
                "prev_close": info.get("regularMarketPreviousClose", 0),
                "market_cap": info.get("marketCap", 0),
                "bid": info.get("bid", 0),
                "ask": info.get("ask", 0),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return {"symbol": symbol, "error": str(e)}

    def get_info(self, symbol: str) -> dict:
        """Fetch symbol information from Yahoo Finance."""
        try:
            ticker = self._get_ticker(symbol)
            info = ticker.info

            return {
                "symbol": symbol,
                "name": info.get("shortName", info.get("longName", symbol)),
                "type": info.get("quoteType", "Unknown"),
                "sector": info.get("sector", "N/A"),
                "industry": info.get("industry", "N/A"),
                "market_cap": info.get("marketCap", 0),
                "pe_ratio": info.get("trailingPE", 0),
                "forward_pe": info.get("forwardPE", 0),
                "dividend_yield": info.get("dividendYield", 0),
                "52w_high": info.get("fiftyTwoWeekHigh", 0),
                "52w_low": info.get("fiftyTwoWeekLow", 0),
                "avg_volume": info.get("averageVolume", 0),
                "beta": info.get("beta", 0),
                "currency": info.get("currency", "USD"),
                "exchange": info.get("exchange", "Unknown"),
            }

        except Exception as e:
            logger.error(f"Error fetching info for {symbol}: {e}")
            return {"symbol": symbol, "error": str(e)}

    def get_multiple_quotes(self, symbols: list[str]) -> dict[str, dict]:
        """Fetch quotes for multiple symbols."""
        results = {}
        for symbol in symbols:
            results[symbol] = self.get_quote(symbol)
        return results


class AlphaVantageProvider(DataProvider):
    """
    Alpha Vantage data provider.

    Requires API key. Provides real-time and historical data.
    Free tier: 5 calls/minute, 500 calls/day.
    """

    def __init__(self, api_key: str):
        import requests
        self.api_key = api_key
        self.base_url = "https://www.alphavantage.co/query"
        self.requests = requests

    def get_historical(
        self,
        symbol: str,
        period: str = "1mo",
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Fetch historical data from Alpha Vantage."""
        try:
            # Map intervals to Alpha Vantage functions
            if interval in ["1m", "5m", "15m", "30m", "1h"]:
                function = "TIME_SERIES_INTRADAY"
                interval_map = {"1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min", "1h": "60min"}
                av_interval = interval_map.get(interval, "5min")
                params = {
                    "function": function,
                    "symbol": symbol,
                    "interval": av_interval,
                    "apikey": self.api_key,
                    "outputsize": "full",
                }
            else:
                function = "TIME_SERIES_DAILY"
                params = {
                    "function": function,
                    "symbol": symbol,
                    "apikey": self.api_key,
                    "outputsize": "full",
                }

            response = self.requests.get(self.base_url, params=params)
            data = response.json()

            # Find the time series key
            ts_key = None
            for key in data.keys():
                if "Time Series" in key:
                    ts_key = key
                    break

            if not ts_key:
                logger.warning(f"No data returned for {symbol}: {data}")
                return pd.DataFrame()

            # Parse data
            ts_data = data[ts_key]
            records = []
            for date_str, values in ts_data.items():
                record = {
                    "date": pd.to_datetime(date_str),
                    "open": float(values["1. open"]),
                    "high": float(values["2. high"]),
                    "low": float(values["3. low"]),
                    "close": float(values["4. close"]),
                    "volume": int(values["5. volume"]),
                }
                records.append(record)

            df = pd.DataFrame(records)
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)

            # Filter by period
            period_days = {
                "1d": 1, "5d": 5, "1mo": 30, "3mo": 90,
                "6mo": 180, "1y": 365, "2y": 730, "5y": 1825,
            }
            days = period_days.get(period, 30)
            cutoff = datetime.now() - timedelta(days=days)
            df = df[df.index >= cutoff]

            return df

        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return pd.DataFrame()

    def get_quote(self, symbol: str) -> dict:
        """Fetch current quote from Alpha Vantage."""
        try:
            params = {
                "function": "GLOBAL_QUOTE",
                "symbol": symbol,
                "apikey": self.api_key,
            }
            response = self.requests.get(self.base_url, params=params)
            data = response.json()

            quote = data.get("Global Quote", {})
            return {
                "symbol": symbol,
                "price": float(quote.get("05. price", 0)),
                "change": float(quote.get("09. change", 0)),
                "change_percent": float(quote.get("10. change percent", "0%").rstrip("%")),
                "volume": int(quote.get("06. volume", 0)),
                "high": float(quote.get("03. high", 0)),
                "low": float(quote.get("04. low", 0)),
                "open": float(quote.get("02. open", 0)),
                "prev_close": float(quote.get("08. previous close", 0)),
                "timestamp": quote.get("07. latest trading day", ""),
            }

        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return {"symbol": symbol, "error": str(e)}

    def get_info(self, symbol: str) -> dict:
        """Fetch symbol information from Alpha Vantage."""
        try:
            params = {
                "function": "OVERVIEW",
                "symbol": symbol,
                "apikey": self.api_key,
            }
            response = self.requests.get(self.base_url, params=params)
            data = response.json()

            return {
                "symbol": symbol,
                "name": data.get("Name", symbol),
                "type": data.get("AssetType", "Unknown"),
                "sector": data.get("Sector", "N/A"),
                "industry": data.get("Industry", "N/A"),
                "market_cap": int(data.get("MarketCapitalization", 0)),
                "pe_ratio": float(data.get("TrailingPE", 0) or 0),
                "forward_pe": float(data.get("ForwardPE", 0) or 0),
                "dividend_yield": float(data.get("DividendYield", 0) or 0),
                "52w_high": float(data.get("52WeekHigh", 0) or 0),
                "52w_low": float(data.get("52WeekLow", 0) or 0),
                "beta": float(data.get("Beta", 0) or 0),
                "currency": data.get("Currency", "USD"),
                "exchange": data.get("Exchange", "Unknown"),
            }

        except Exception as e:
            logger.error(f"Error fetching info for {symbol}: {e}")
            return {"symbol": symbol, "error": str(e)}
