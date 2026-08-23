"""
market_fetcher.py
------------------
Pulls live/near-live market data (gold, DXY, yields, VIX, S&P 500) from
Yahoo Finance via the `yfinance` package. No API key required.

Like fred_fetcher, failures are raised as MarketFetchError so the caller
can decide whether to abort, retry, or degrade gracefully.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd

try:
    import yfinance as yf
except ImportError:  # pragma: no cover - surfaced clearly at runtime instead
    yf = None

from xauusd_bot import config

logger = logging.getLogger(__name__)


class MarketFetchError(RuntimeError):
    """Raised when a Yahoo Finance fetch fails or returns unusable data."""


@dataclass
class MarketSeries:
    ticker: str
    history: pd.DataFrame  # columns include at least 'Close'

    @property
    def latest_close(self) -> Optional[float]:
        if self.history.empty:
            return None
        return float(self.history["Close"].iloc[-1])

    def close_n_days_ago(self, n: int) -> Optional[float]:
        if len(self.history) <= n:
            return None
        return float(self.history["Close"].iloc[-1 - n])

    def pct_change(self, n_days: int) -> Optional[float]:
        latest = self.latest_close
        prior = self.close_n_days_ago(n_days)
        if latest is None or prior is None or prior == 0:
            return None
        return (latest - prior) / prior * 100.0


def fetch_ticker(ticker: str, period_days: int = None) -> MarketSeries:
    if yf is None:
        raise MarketFetchError(
            "yfinance is not installed. Run: pip install yfinance --break-system-packages"
        )
    period_days = period_days or config.LOOKBACK_DAYS_MARKET
    try:
        hist = yf.Ticker(ticker).history(period=f"{period_days}d")
    except Exception as exc:  # yfinance can raise many different exception types
        raise MarketFetchError(f"Failed to fetch ticker '{ticker}': {exc}") from exc

    if hist is None or hist.empty:
        raise MarketFetchError(f"No price history returned for ticker '{ticker}'")

    return MarketSeries(ticker=ticker, history=hist)


def fetch_all(ticker_map: dict = None) -> Dict[str, MarketSeries]:
    ticker_map = ticker_map or config.MARKET_TICKERS
    results = {}
    for internal_name, ticker in ticker_map.items():
        try:
            results[internal_name] = fetch_ticker(ticker)
        except MarketFetchError as exc:
            logger.warning("Skipping '%s' (%s): %s", internal_name, ticker, exc)
    return results
