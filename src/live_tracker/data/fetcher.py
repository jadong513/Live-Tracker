"""
Market Data Fetcher.

Main interface for fetching market data with caching and rate limiting.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from live_tracker.data.providers import DataProvider, YFinanceProvider

logger = logging.getLogger(__name__)


class MarketDataFetcher:
    """
    Main market data fetcher with caching and rate limiting.

    Provides a unified interface for fetching market data from
    various providers with built-in caching and error handling.
    """

    def __init__(
        self,
        provider: Optional[DataProvider] = None,
        cache_ttl: int = 60,
        rate_limit: float = 0.5,
    ):
        """
        Initialize the market data fetcher.

        Args:
            provider: Data provider to use (defaults to YFinance)
            cache_ttl: Cache time-to-live in seconds
            rate_limit: Minimum seconds between API calls
        """
        self.provider = provider or YFinanceProvider()
        self.cache_ttl = cache_ttl
        self.rate_limit = rate_limit

        self._price_cache: dict[str, tuple[pd.DataFrame, datetime]] = {}
        self._quote_cache: dict[str, tuple[dict, datetime]] = {}
        self._info_cache: dict[str, tuple[dict, datetime]] = {}
        self._last_call = 0.0

    def _rate_limit_wait(self):
        """Wait if necessary to respect rate limits."""
        now = time.time()
        elapsed = now - self._last_call
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_call = time.time()

    def _is_cache_valid(self, timestamp: datetime) -> bool:
        """Check if cached data is still valid."""
        return (datetime.now() - timestamp).seconds < self.cache_ttl

    def get_historical(
        self,
        symbol: str,
        period: str = "1mo",
        interval: str = "1d",
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data.

        Args:
            symbol: Ticker symbol (e.g., 'AAPL', 'BTC-USD')
            period: Data period ('1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y')
            interval: Data interval ('1m', '5m', '15m', '1h', '1d', '1wk')
            use_cache: Whether to use cached data if available

        Returns:
            DataFrame with columns: open, high, low, close, volume
        """
        cache_key = f"{symbol}_{period}_{interval}"

        # Check cache
        if use_cache and cache_key in self._price_cache:
            df, timestamp = self._price_cache[cache_key]
            if self._is_cache_valid(timestamp):
                logger.debug(f"Using cached data for {symbol}")
                return df

        # Fetch from provider
        self._rate_limit_wait()
        df = self.provider.get_historical(symbol, period, interval)

        # Update cache
        if not df.empty:
            self._price_cache[cache_key] = (df, datetime.now())

        return df

    def get_quote(self, symbol: str, use_cache: bool = True) -> dict:
        """
        Fetch current quote for a symbol.

        Args:
            symbol: Ticker symbol
            use_cache: Whether to use cached data if available

        Returns:
            Dictionary with current price, change, volume, etc.
        """
        if use_cache and symbol in self._quote_cache:
            quote, timestamp = self._quote_cache[symbol]
            if self._is_cache_valid(timestamp):
                logger.debug(f"Using cached quote for {symbol}")
                return quote

        self._rate_limit_wait()
        quote = self.provider.get_quote(symbol)

        if "error" not in quote:
            self._quote_cache[symbol] = (quote, datetime.now())

        return quote

    def get_info(self, symbol: str, use_cache: bool = True) -> dict:
        """
        Fetch symbol information.

        Args:
            symbol: Ticker symbol
            use_cache: Whether to use cached data if available

        Returns:
            Dictionary with symbol info (name, sector, market cap, etc.)
        """
        if use_cache and symbol in self._info_cache:
            info, timestamp = self._info_cache[symbol]
            # Info doesn't change often, use longer TTL
            if (datetime.now() - timestamp).seconds < self.cache_ttl * 60:
                logger.debug(f"Using cached info for {symbol}")
                return info

        self._rate_limit_wait()
        info = self.provider.get_info(symbol)

        if "error" not in info:
            self._info_cache[symbol] = (info, datetime.now())

        return info

    def get_multiple_historical(
        self,
        symbols: list[str],
        period: str = "1mo",
        interval: str = "1d",
    ) -> dict[str, pd.DataFrame]:
        """
        Fetch historical data for multiple symbols.

        Args:
            symbols: List of ticker symbols
            period: Data period
            interval: Data interval

        Returns:
            Dictionary mapping symbols to DataFrames
        """
        results = {}
        for symbol in symbols:
            results[symbol] = self.get_historical(symbol, period, interval)
        return results

    def get_multiple_quotes(self, symbols: list[str]) -> dict[str, dict]:
        """
        Fetch quotes for multiple symbols.

        Args:
            symbols: List of ticker symbols

        Returns:
            Dictionary mapping symbols to quote dictionaries
        """
        results = {}
        for symbol in symbols:
            results[symbol] = self.get_quote(symbol)
        return results

    def clear_cache(self, symbol: Optional[str] = None):
        """
        Clear cached data.

        Args:
            symbol: Specific symbol to clear, or None for all
        """
        if symbol:
            # Clear specific symbol from all caches
            keys_to_remove = [k for k in self._price_cache if k.startswith(symbol)]
            for key in keys_to_remove:
                del self._price_cache[key]
            self._quote_cache.pop(symbol, None)
            self._info_cache.pop(symbol, None)
        else:
            # Clear all caches
            self._price_cache.clear()
            self._quote_cache.clear()
            self._info_cache.clear()

    def get_data_with_indicators(
        self,
        symbol: str,
        period: str = "3mo",
        interval: str = "1d",
    ) -> pd.DataFrame:
        """
        Fetch historical data ready for indicator calculation.

        Args:
            symbol: Ticker symbol
            period: Data period (recommend at least 3mo for accurate indicators)
            interval: Data interval

        Returns:
            DataFrame with OHLCV data
        """
        df = self.get_historical(symbol, period, interval)

        if df.empty:
            logger.warning(f"No data available for {symbol}")
            return df

        # Ensure we have enough data for indicators
        min_periods = 50
        if len(df) < min_periods:
            logger.warning(
                f"Only {len(df)} periods for {symbol}, "
                f"some indicators may be incomplete (recommend {min_periods}+)"
            )

        return df
