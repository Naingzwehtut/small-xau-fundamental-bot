"""
sample_data.py
--------------
Synthetic-but-realistic data used for:
  * `python -m xauusd_bot.demo` (no API key / no internet required)
  * Unit tests

This lets anyone try the full pipeline (fetch -> score -> report) instantly,
and lets us test scoring.py deterministically without hitting live APIs.

Values are loosely modeled on a plausible macro snapshot; they are NOT
live data and should never be mistaken for it (the demo report is labeled
clearly as sample data).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List

import pandas as pd

from xauusd_bot.fetchers.fred_fetcher import Observation
from xauusd_bot.fetchers.market_fetcher import MarketSeries


def _make_series(values: List[float], freq_days: int = 30) -> List[Observation]:
    """Build a chronological Observation list ending 'today', spaced freq_days apart."""
    n = len(values)
    today = datetime.today()
    dates = [today - timedelta(days=freq_days * (n - 1 - i)) for i in range(n)]
    return [Observation(date=d, value=v) for d, v in zip(dates, values)]


def sample_fred_data(scenario: str = "mixed") -> Dict[str, List[Observation]]:
    """
    scenario: 'bullish', 'bearish', or 'mixed' -- lets you demo different
    market regimes without needing live data to line up that way.

    CPI / Core PCE / M2 need 13 monthly points (12 periods back) to compute
    a YoY change, so those lists are longer than the others.
    """
    if scenario == "bullish":
        real_yield = [2.30, 2.20, 2.05, 1.85, 1.60]        # falling real yields
        # rising, accelerating CPI (from 305 a year ago to 315.4 now -> ~3.4% YoY)
        cpi = [305.0, 305.8, 306.5, 307.3, 308.1, 309.0, 309.9, 310.8, 311.8, 312.8, 313.8, 314.6, 315.4]
        core_pce = [122.5, 123.1, 123.7, 124.3, 124.9, 125.5, 126.1, 126.7, 127.3, 127.8, 128.3, 128.6, 128.9]
        fed_funds = [5.33, 5.33, 5.08, 4.83, 4.33]          # cutting
        unrate = [3.7, 3.9, 4.1, 4.4, 4.7]                  # rising unemployment
        # M2 growing from 20100 a year ago to 21750 now -> ~8.2% YoY
        m2 = [20100, 20250, 20400, 20560, 20720, 20880, 21040, 21200, 21350, 21500, 21600, 21680, 21750]
        dollar_idx = [106.0, 104.8, 103.2, 101.5, 99.8]     # weakening dollar
    elif scenario == "bearish":
        real_yield = [1.60, 1.85, 2.05, 2.25, 2.55]         # rising real yields
        # tame CPI, from 306 a year ago to 308.1 now -> ~0.7% YoY
        cpi = [306.0, 306.2, 306.4, 306.6, 306.8, 307.0, 307.2, 307.4, 307.6, 307.8, 307.9, 308.0, 308.1]
        core_pce = [124.8, 124.9, 125.0, 125.1, 125.2, 125.3, 125.3, 125.4, 125.4, 125.5, 125.5, 125.6, 125.6]
        fed_funds = [4.33, 4.58, 4.83, 5.08, 5.33]          # hiking
        unrate = [4.5, 4.3, 4.1, 3.9, 3.7]                  # falling unemployment
        # M2 contracting slightly YoY
        m2 = [21400, 21350, 21300, 21250, 21200, 21150, 21100, 21050, 21000, 20950, 20900, 20850, 20800]
        dollar_idx = [99.0, 101.0, 103.0, 105.2, 107.5]     # strengthening dollar
    else:  # mixed / neutral-ish
        real_yield = [1.95, 2.00, 1.90, 1.98, 1.93]
        # CPI right around 2% YoY -- neutral for the inflation factor
        cpi = [303.5, 304.1, 304.7, 305.3, 305.9, 306.5, 307.1, 307.7, 308.3, 308.7, 309.1, 309.4, 309.6]
        core_pce = [123.4, 123.7, 124.0, 124.3, 124.6, 124.9, 125.2, 125.5, 125.7, 125.9, 126.0, 126.1, 126.2]
        fed_funds = [5.33, 5.33, 5.33, 5.08, 5.08]
        unrate = [3.9, 4.0, 4.0, 4.1, 4.0]
        m2 = [20500, 20600, 20700, 20800, 20870, 20940, 21000, 21050, 21100, 21140, 21170, 21190, 21200]
        dollar_idx = [104.0, 104.3, 103.9, 104.2, 104.0]

    return {
        "real_yield_10y": _make_series(real_yield),
        "cpi_yoy": _make_series(cpi),
        "core_pce_yoy": _make_series(core_pce),
        "fed_funds_rate": _make_series(fed_funds),
        "unemployment_rate": _make_series(unrate),
        "m2_money_supply": _make_series(m2),
        "trade_weighted_dollar": _make_series(dollar_idx),
    }


def _make_market_series(ticker: str, closes: List[float]) -> MarketSeries:
    today = datetime.today()
    dates = [today - timedelta(days=(len(closes) - 1 - i)) for i in range(len(closes))]
    df = pd.DataFrame({"Close": closes}, index=pd.DatetimeIndex(dates))
    return MarketSeries(ticker=ticker, history=df)


def sample_market_data(scenario: str = "mixed") -> Dict[str, MarketSeries]:
    if scenario == "bullish":
        dxy = [106.0, 105.2, 104.5, 103.6, 102.8, 101.9]
        vix = [14.0, 15.5, 17.2, 19.8, 22.5, 26.0]
        spx = [5600, 5580, 5550, 5490, 5420, 5350]
        gold = [2350, 2370, 2395, 2420, 2455, 2490]
    elif scenario == "bearish":
        dxy = [101.9, 102.8, 103.6, 104.5, 105.2, 106.0]
        vix = [26.0, 22.5, 19.8, 17.2, 15.5, 13.0]
        spx = [5350, 5420, 5490, 5550, 5580, 5650]
        gold = [2490, 2460, 2430, 2400, 2370, 2340]
    else:
        dxy = [104.0, 104.2, 103.9, 104.1, 104.0, 104.1]
        vix = [16.0, 16.5, 15.8, 16.2, 16.0, 16.1]
        spx = [5500, 5510, 5495, 5505, 5500, 5502]
        gold = [2400, 2405, 2398, 2403, 2401, 2402]

    return {
        "gold_spot": _make_market_series("GC=F", gold),
        "dxy": _make_market_series("DX-Y.NYB", dxy),
        "vix": _make_market_series("^VIX", vix),
        "spx": _make_market_series("^GSPC", spx),
    }
