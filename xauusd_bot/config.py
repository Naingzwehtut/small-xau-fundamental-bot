"""
config.py
---------
Central configuration for the XAUUSD Fundamental Analysis Bot.

Holds:
  * Which macro series to pull (FRED series IDs)
  * Which market tickers to pull (Yahoo Finance symbols)
  * The weighting scheme used to combine individual factor scores
    into one overall bullish/bearish bias score for gold.

Nothing in here does any network I/O -- it is pure data / settings,
so it is safe to import from anywhere in the project without side effects.
"""

import os
from dataclasses import dataclass
from typing import Dict

# ---------------------------------------------------------------------------
# API keys / environment
# ---------------------------------------------------------------------------
# Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# ---------------------------------------------------------------------------
# Macro series pulled from FRED
# ---------------------------------------------------------------------------
# Each entry: internal_name -> FRED series ID
# These are the macro drivers with the most consistent, well-documented
# relationship to gold prices.
FRED_SERIES: Dict[str, str] = {
    "real_yield_10y": "DFII10",     # 10-Year TIPS (real) yield  -> inverse to gold
    "nominal_yield_10y": "DGS10",   # 10-Year Treasury nominal yield
    "cpi_yoy": "CPIAUCSL",          # CPI, all urban consumers (index, we derive YoY %)
    "core_pce_yoy": "PCEPILFE",     # Core PCE price index (Fed's preferred inflation gauge)
    "fed_funds_rate": "FEDFUNDS",   # Effective federal funds rate
    "unemployment_rate": "UNRATE",  # Unemployment rate
    "m2_money_supply": "M2SL",      # M2 money supply (debasement / liquidity proxy)
    "trade_weighted_dollar": "DTWEXBGS",  # Broad trade-weighted USD index (FRED alt to DXY)
}

# ---------------------------------------------------------------------------
# Market data pulled from Yahoo Finance (via yfinance) - no API key needed
# ---------------------------------------------------------------------------
MARKET_TICKERS: Dict[str, str] = {
    "gold_spot": "GC=F",     # COMEX Gold futures (front month) - proxy for XAUUSD
    "dxy": "DX-Y.NYB",       # US Dollar Index
    "us10y_yield": "^TNX",   # 10Y Treasury yield (CBOE index, /10 = actual %)
    "vix": "^VIX",           # CBOE Volatility Index - risk-sentiment / safe-haven proxy
    "spx": "^GSPC",          # S&P 500 - risk appetite cross-check
}

LOOKBACK_DAYS_MARKET = 90     # how much market history to pull for trend/momentum calcs
LOOKBACK_OBS_FRED = 24        # how many periodic observations to pull per FRED series


# ---------------------------------------------------------------------------
# Scoring configuration
# ---------------------------------------------------------------------------
# Each factor contributes a score in the range [-2, +2]:
#   +2  strongly bullish for gold
#   +1  mildly bullish
#    0  neutral / no clear signal
#   -1  mildly bearish
#   -2  strongly bearish
#
# Factor scores are combined with weights (must sum to 1.0 across all
# active factors) to produce a single weighted average in [-2, +2],
# which is then rescaled to a 0-100 "bias score" for reporting
# (0 = max bearish, 50 = neutral, 100 = max bullish).

@dataclass
class FactorWeight:
    weight: float
    label: str


WEIGHTS: Dict[str, FactorWeight] = {
    "real_yields":        FactorWeight(0.25, "Real Yields (10Y TIPS)"),
    "dollar_index":       FactorWeight(0.20, "US Dollar Index (DXY)"),
    "inflation":          FactorWeight(0.15, "Inflation (CPI / Core PCE)"),
    "fed_policy":         FactorWeight(0.15, "Fed Funds Rate / Policy Stance"),
    "labor_market":       FactorWeight(0.10, "Labor Market (Unemployment Rate)"),
    "risk_sentiment":     FactorWeight(0.10, "Risk Sentiment (VIX / Safe-Haven Flows)"),
    "money_supply":       FactorWeight(0.05, "Money Supply Growth (M2)"),
}

assert abs(sum(w.weight for w in WEIGHTS.values()) - 1.0) < 1e-6, \
    "Factor weights must sum to 1.0"

# Bias score bands (0-100 scale) used to label the final verdict
BIAS_BANDS = [
    (0, 20, "Strongly Bearish"),
    (20, 40, "Bearish"),
    (40, 60, "Neutral"),
    (60, 80, "Bullish"),
    (80, 101, "Strongly Bullish"),
]

# Where daily reports get written
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
