"""
fred_fetcher.py
---------------
Thin wrapper around the FRED (Federal Reserve Economic Data) REST API.

We use plain `requests` rather than the `fredapi` package to keep the
dependency footprint tiny and the behaviour transparent.

All functions here are network I/O and can raise `FredFetchError`.
Callers (main.py) are responsible for catching that and falling back
to cached data if desired.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import requests

from xauusd_bot import config

logger = logging.getLogger(__name__)


class FredFetchError(RuntimeError):
    """Raised when a FRED API call fails or returns unusable data."""


@dataclass
class Observation:
    date: datetime
    value: Optional[float]


def _parse_observations(raw_obs: list) -> List[Observation]:
    parsed = []
    for row in raw_obs:
        val_str = row.get("value", ".")
        value = None if val_str in (".", "", None) else float(val_str)
        parsed.append(Observation(date=datetime.strptime(row["date"], "%Y-%m-%d"), value=value))
    return parsed


def fetch_series(series_id: str, api_key: str = None, limit: int = None) -> List[Observation]:
    """
    Fetch observations for a single FRED series, most recent last.

    Raises FredFetchError on any network/API/parsing problem so the
    caller can decide how to degrade gracefully.
    """
    api_key = api_key or config.FRED_API_KEY
    limit = limit or config.LOOKBACK_OBS_FRED

    if not api_key:
        raise FredFetchError(
            "No FRED_API_KEY configured. Get a free key at "
            "https://fred.stlouisfed.org/docs/api/api_key.html and set it "
            "as an environment variable."
        )

    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": limit,
    }

    try:
        resp = requests.get(config.FRED_BASE_URL, params=params, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise FredFetchError(f"Network error fetching series '{series_id}': {exc}") from exc

    try:
        payload = resp.json()
        raw_obs = payload["observations"]
    except (ValueError, KeyError) as exc:
        raise FredFetchError(f"Unexpected FRED response for '{series_id}': {exc}") from exc

    if not raw_obs:
        raise FredFetchError(f"FRED returned no observations for series '{series_id}'")

    observations = _parse_observations(raw_obs)
    # API returns newest-first; flip to chronological order for downstream math
    observations.reverse()
    return observations


def fetch_all(series_map: dict = None, api_key: str = None) -> dict:
    """
    Fetch every series configured in config.FRED_SERIES.

    Returns: { internal_name: List[Observation] }
    Series that fail to fetch are omitted (and logged), rather than
    aborting the whole run -- a single stale/missing indicator shouldn't
    take down the entire report.
    """
    series_map = series_map or config.FRED_SERIES
    results = {}
    for internal_name, series_id in series_map.items():
        try:
            results[internal_name] = fetch_series(series_id, api_key=api_key)
        except FredFetchError as exc:
            logger.warning("Skipping '%s' (%s): %s", internal_name, series_id, exc)
    return results


def latest_value(observations: List[Observation]) -> Optional[float]:
    """Most recent non-null value in a chronologically-sorted observation list."""
    for obs in reversed(observations):
        if obs.value is not None:
            return obs.value
    return None


def value_n_periods_ago(observations: List[Observation], n: int) -> Optional[float]:
    """
    Value from n valid (non-null) observations back from the latest one.
    n=0 is equivalent to latest_value(). Used for YoY / MoM change calcs.
    """
    non_null = [obs for obs in observations if obs.value is not None]
    idx = len(non_null) - 1 - n
    if idx < 0:
        return None
    return non_null[idx].value


def percent_change(observations: List[Observation], periods_back: int) -> Optional[float]:
    """Percent change between the latest value and the value `periods_back` earlier."""
    latest = latest_value(observations)
    prior = value_n_periods_ago(observations, periods_back)
    if latest is None or prior is None or prior == 0:
        return None
    return (latest - prior) / prior * 100.0
