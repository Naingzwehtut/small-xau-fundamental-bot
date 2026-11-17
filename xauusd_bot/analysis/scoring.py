"""
scoring.py
----------
Turns raw macro + market data into:
  1. Individual factor scores in [-2, +2]  (bearish <-> bullish for gold)
  2. A weighted composite "bias score" on a 0-100 scale
  3. Plain-English explanations for each factor

The rules encoded here reflect well-established, textbook relationships
between gold and macro variables:

  * Real yields UP  -> gold BEARISH (holding non-yielding gold gets more
    expensive relative to yielding assets like TIPS)
  * US Dollar UP    -> gold BEARISH (gold is dollar-priced; strong dollar
    makes it more expensive for foreign buyers, and often coincides with
    tighter global liquidity)
  * Inflation UP    -> gold BULLISH (gold is a traditional inflation hedge)
  * Fed Funds Rate rising / hawkish -> gold BEARISH (higher opportunity
    cost of holding gold); falling / dovish -> BULLISH
  * Unemployment rising -> gold BULLISH (weak labor market raises odds
    of rate cuts and safe-haven demand)
  * Risk-off (VIX spiking, equities selling off) -> gold BULLISH
    (safe-haven flows)
  * M2 money supply growth -> gold BULLISH (currency debasement hedge)

This module is intentionally pure (no I/O): it takes already-fetched
data structures and returns scores, so it's easy to unit test.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from xauusd_bot import config
from xauusd_bot.fetchers.fred_fetcher import Observation, latest_value, percent_change
from xauusd_bot.fetchers.market_fetcher import MarketSeries


@dataclass
class FactorScore:
    key: str
    label: str
    score: float          # raw score in [-2, +2]
    weight: float
    explanation: str
    data_points: Dict[str, str]  # human-readable values used in the calc, for transparency


def _clamp(value: float, lo: float = -2.0, hi: float = 2.0) -> float:
    return max(lo, min(hi, value))


def _scale_linear(x: float, x_bear: float, x_bull: float) -> float:
    """
    Map x linearly onto [-2, +2] where x_bear -> -2 and x_bull -> +2.
    Handles both increasing and inverted (x_bear > x_bull) relationships.
    Clamped at the ends so outlier data doesn't blow up the score.
    """
    if x_bear == x_bull:
        return 0.0
    t = (x - x_bear) / (x_bull - x_bear)
    return _clamp(-2.0 + 4.0 * t)


# ---------------------------------------------------------------------------
# Individual factor scorers
# ---------------------------------------------------------------------------

def score_real_yields(fred_data: Dict[str, List[Observation]]) -> FactorScore:
    key, w = "real_yields", config.WEIGHTS["real_yields"]
    obs = fred_data.get("real_yield_10y")
    if not obs:
        return FactorScore(key, w.label, 0.0, w.weight, "No real yield data available.", {})

    latest = latest_value(obs)
    change_bp = None
    prior = None
    non_null = [o for o in obs if o.value is not None]
    if len(non_null) >= 2:
        prior = non_null[-2].value
        change_bp = (latest - prior) * 100  # percentage points -> basis points

    # Falling real yields = bullish for gold. Score primarily off the recent
    # trend (change), since level alone doesn't tell you direction of flow.
    if change_bp is None:
        score = 0.0
        explanation = f"10Y real (TIPS) yield is {latest:.2f}% with insufficient history for a trend read."
    else:
        # -30bp move or more over the observation window -> max bullish;
        # +30bp or more -> max bearish.
        score = _scale_linear(-change_bp, -30, 30)
        direction = "falling" if change_bp < 0 else "rising" if change_bp > 0 else "flat"
        explanation = (
            f"10Y real (TIPS) yield is {latest:.2f}%, {direction} "
            f"{abs(change_bp):.0f}bp vs. the prior reading. "
            f"{'Falling real yields lower the opportunity cost of holding non-yielding gold (bullish).' if change_bp < 0 else ''}"
            f"{'Rising real yields raise the opportunity cost of holding gold (bearish).' if change_bp > 0 else ''}"
        ).strip()

    return FactorScore(key, w.label, score, w.weight, explanation,
                        {"latest_real_yield_pct": f"{latest:.2f}" if latest is not None else "N/A",
                         "change_bp": f"{change_bp:+.0f}" if change_bp is not None else "N/A"})


def score_dollar_index(market_data: Dict[str, MarketSeries], fred_data: Dict[str, List[Observation]]) -> FactorScore:
    key, w = "dollar_index", config.WEIGHTS["dollar_index"]
    series = market_data.get("dxy")

    if series is not None:
        pct_5d = series.pct_change(5)
        latest = series.latest_close
        source = "DXY (Yahoo Finance)"
    else:
        # Fallback to FRED's broad trade-weighted dollar index
        obs = fred_data.get("trade_weighted_dollar")
        if not obs:
            return FactorScore(key, w.label, 0.0, w.weight, "No US dollar index data available.", {})
        latest = latest_value(obs)
        pct_5d = percent_change(obs, 5)
        source = "Trade-Weighted USD Index (FRED)"

    if pct_5d is None or latest is None:
        return FactorScore(key, w.label, 0.0, w.weight, f"{source} data insufficient for a trend read.", {})

    # Dollar UP = bearish for gold. +1.5% over the window -> max bearish;
    # -1.5% -> max bullish.
    score = _scale_linear(-pct_5d, -1.5, 1.5)
    direction = "strengthening" if pct_5d > 0 else "weakening" if pct_5d < 0 else "flat"
    explanation = (
        f"{source} is at {latest:.2f}, {direction} {abs(pct_5d):.2f}% recently. "
        f"{'A stronger dollar makes gold costlier for foreign buyers and typically pressures prices (bearish).' if pct_5d > 0 else ''}"
        f"{'A weaker dollar makes gold cheaper for foreign buyers, supporting prices (bullish).' if pct_5d < 0 else ''}"
    ).strip()

    return FactorScore(key, w.label, score, w.weight, explanation,
                        {"latest_index": f"{latest:.2f}", "pct_change_5d": f"{pct_5d:+.2f}%"})


def score_inflation(fred_data: Dict[str, List[Observation]]) -> FactorScore:
    key, w = "inflation", config.WEIGHTS["inflation"]
    cpi_obs = fred_data.get("cpi_yoy")
    pce_obs = fred_data.get("core_pce_yoy")

    readings = []
    if cpi_obs:
        cpi_yoy = percent_change(cpi_obs, 12)  # monthly series -> 12 periods back = YoY
        if cpi_yoy is not None:
            readings.append(("CPI YoY", cpi_yoy))
    if pce_obs:
        pce_yoy = percent_change(pce_obs, 12)
        if pce_yoy is not None:
            readings.append(("Core PCE YoY", pce_yoy))

    if not readings:
        return FactorScore(key, w.label, 0.0, w.weight, "No inflation data available.", {})

    avg_yoy = sum(v for _, v in readings) / len(readings)
    # Fed's 2% target is the neutral anchor. Above target -> bullish for
    # gold (inflation hedge demand); at/below -> neutral to bearish.
    score = _scale_linear(avg_yoy, 1.0, 4.0)  # 1% YoY -> max bearish, 4% YoY -> max bullish
    reading_str = ", ".join(f"{name}: {val:.1f}%" for name, val in readings)
    explanation = (
        f"Inflation readings ({reading_str}) vs. the Fed's 2% target. "
        f"{'Inflation running above target supports gold as an inflation hedge (bullish).' if avg_yoy > 2.0 else ''}"
        f"{'Inflation near or below target reduces hedge demand for gold (neutral/bearish).' if avg_yoy <= 2.0 else ''}"
    ).strip()

    return FactorScore(key, w.label, score, w.weight, explanation,
                        {name: f"{val:.1f}%" for name, val in readings})


def score_fed_policy(fred_data: Dict[str, List[Observation]]) -> FactorScore:
    key, w = "fed_policy", config.WEIGHTS["fed_policy"]
    obs = fred_data.get("fed_funds_rate")
    if not obs:
        return FactorScore(key, w.label, 0.0, w.weight, "No Fed funds rate data available.", {})

    latest = latest_value(obs)
    non_null = [o for o in obs if o.value is not None]
    change_3m = None
    if len(non_null) >= 4:
        change_3m = (latest - non_null[-4].value) * 100  # bp change over ~3 months

    if change_3m is None:
        return FactorScore(key, w.label, 0.0, w.weight,
                            f"Fed funds rate is {latest:.2f}% with insufficient history for a trend read.",
                            {"fed_funds_rate": f"{latest:.2f}%"})

    # Falling rate = dovish = bullish for gold. -50bp over ~3mo -> max bullish;
    # +50bp -> max bearish.
    score = _scale_linear(-change_3m, -50, 50)
    stance = "cutting (dovish)" if change_3m < 0 else "hiking (hawkish)" if change_3m > 0 else "holding steady"
    explanation = (
        f"Fed funds rate is {latest:.2f}%, with the Fed {stance} over the recent period "
        f"({change_3m:+.0f}bp change). "
        f"{'A dovish/cutting stance lowers the opportunity cost of holding gold (bullish).' if change_3m < 0 else ''}"
        f"{'A hawkish/hiking stance raises the opportunity cost of holding gold (bearish).' if change_3m > 0 else ''}"
        f"{'A steady stance is broadly neutral for gold.' if change_3m == 0 else ''}"
    ).strip()

    return FactorScore(key, w.label, score, w.weight, explanation,
                        {"fed_funds_rate": f"{latest:.2f}%", "change_3m_bp": f"{change_3m:+.0f}"})


def score_labor_market(fred_data: Dict[str, List[Observation]]) -> FactorScore:
    key, w = "labor_market", config.WEIGHTS["labor_market"]
    obs = fred_data.get("unemployment_rate")
    if not obs:
        return FactorScore(key, w.label, 0.0, w.weight, "No unemployment data available.", {})

    latest = latest_value(obs)
    non_null = [o for o in obs if o.value is not None]
    change = None
    if len(non_null) >= 4:
        change = (latest - non_null[-4].value) * 100  # bp change over ~3 months

    if change is None:
        return FactorScore(key, w.label, 0.0, w.weight,
                            f"Unemployment rate is {latest:.1f}% with insufficient history for a trend read.",
                            {"unemployment_rate": f"{latest:.1f}%"})

    # Rising unemployment -> weaker labor market -> more likely rate cuts
    # + safe-haven demand -> bullish for gold.
    score = _scale_linear(change, -30, 30)
    direction = "rising" if change > 0 else "falling" if change < 0 else "flat"
    explanation = (
        f"Unemployment rate is {latest:.1f}%, {direction} {abs(change):.0f}bp recently. "
        f"{'A softening labor market raises rate-cut odds and safe-haven demand (bullish for gold).' if change > 0 else ''}"
        f"{'A tightening labor market reduces rate-cut urgency (bearish for gold).' if change < 0 else ''}"
    ).strip()

    return FactorScore(key, w.label, score, w.weight, explanation,
                        {"unemployment_rate": f"{latest:.1f}%", "change_3m_bp": f"{change:+.0f}"})


def score_risk_sentiment(market_data: Dict[str, MarketSeries]) -> FactorScore:
    key, w = "risk_sentiment", config.WEIGHTS["risk_sentiment"]
    vix = market_data.get("vix")
    spx = market_data.get("spx")

    if vix is None and spx is None:
        return FactorScore(key, w.label, 0.0, w.weight, "No risk-sentiment data available.", {})

    parts = []
    scores = []
    data_points = {}

    if vix is not None and vix.latest_close is not None:
        vix_level = vix.latest_close
        # VIX > 25 = elevated fear (bullish gold); < 15 = complacency (bearish gold)
        s = _scale_linear(vix_level, 15, 30)
        scores.append(s)
        parts.append(f"VIX at {vix_level:.1f}")
        data_points["vix_level"] = f"{vix_level:.1f}"

    if spx is not None:
        pct_5d = spx.pct_change(5)
        if pct_5d is not None:
            # Equities selling off -> risk-off -> bullish gold
            s = _scale_linear(-pct_5d, -3, 3)
            scores.append(s)
            parts.append(f"S&P 500 {pct_5d:+.2f}% over 5 days")
            data_points["spx_pct_change_5d"] = f"{pct_5d:+.2f}%"

    if not scores:
        return FactorScore(key, w.label, 0.0, w.weight, "Risk-sentiment data insufficient for a read.", {})

    score = sum(scores) / len(scores)
    explanation = (
        f"Risk sentiment snapshot: {', '.join(parts)}. "
        f"{'Elevated volatility / equity weakness typically drives safe-haven flows into gold (bullish).' if score > 0.3 else ''}"
        f"{'Low volatility / equity strength typically reduces safe-haven demand for gold (bearish).' if score < -0.3 else ''}"
        f"{'Risk sentiment is broadly balanced.' if -0.3 <= score <= 0.3 else ''}"
    ).strip()

    return FactorScore(key, w.label, score, w.weight, explanation, data_points)


def score_money_supply(fred_data: Dict[str, List[Observation]]) -> FactorScore:
    key, w = "money_supply", config.WEIGHTS["money_supply"]
    obs = fred_data.get("m2_money_supply")
    if not obs:
        return FactorScore(key, w.label, 0.0, w.weight, "No M2 money supply data available.", {})

    yoy = percent_change(obs, 12)
    if yoy is None:
        latest = latest_value(obs)
        return FactorScore(key, w.label, 0.0, w.weight,
                            f"M2 money supply is {latest:,.0f} (insufficient history for YoY calc).",
                            {})

    # Faster money-supply growth -> currency debasement concerns -> bullish gold.
    # 0% YoY -> max bearish-ish (contraction), 8% YoY -> max bullish.
    score = _scale_linear(yoy, 0, 8)
    explanation = (
        f"M2 money supply growth is {yoy:+.1f}% YoY. "
        f"{'Expanding money supply raises currency-debasement / inflation-hedge demand for gold (bullish).' if yoy > 3 else ''}"
        f"{'Slow or contracting money supply growth reduces debasement concerns (neutral/bearish).' if yoy <= 3 else ''}"
    ).strip()

    return FactorScore(key, w.label, score, w.weight, explanation, {"m2_yoy": f"{yoy:+.1f}%"})


# ---------------------------------------------------------------------------
# Composite
# ---------------------------------------------------------------------------

@dataclass
class BiasResult:
    bias_score_0_100: float
    weighted_avg_raw: float  # in [-2, +2]
    label: str
    factor_scores: List[FactorScore]


def _band_label(score_0_100: float) -> str:
    for lo, hi, label in config.BIAS_BANDS:
        if lo <= score_0_100 < hi:
            return label
    return "Neutral"


def compute_bias(
    fred_data: Dict[str, List[Observation]],
    market_data: Dict[str, MarketSeries],
) -> BiasResult:
    """
    Run every factor scorer, combine with configured weights, and produce
    the final 0-100 bias score plus a human-readable label.

    Factors with zero underlying data still contribute 0.0 * weight (i.e.
    they act as neutral rather than being silently dropped) so the total
    weight base stays consistent and comparable day to day.
    """
    factor_scores = [
        score_real_yields(fred_data),
        score_dollar_index(market_data, fred_data),
        score_inflation(fred_data),
        score_fed_policy(fred_data),
        score_labor_market(fred_data),
        score_risk_sentiment(market_data),
        score_money_supply(fred_data),
    ]

    weighted_sum = sum(f.score * f.weight for f in factor_scores)
    total_weight = sum(f.weight for f in factor_scores)
    weighted_avg_raw = weighted_sum / total_weight if total_weight else 0.0

    # Rescale from [-2, +2] to [0, 100]
    bias_0_100 = (weighted_avg_raw + 2) / 4 * 100
    bias_0_100 = max(0.0, min(100.0, bias_0_100))

    return BiasResult(
        bias_score_0_100=round(bias_0_100, 1),
        weighted_avg_raw=round(weighted_avg_raw, 3),
        label=_band_label(bias_0_100),
        factor_scores=factor_scores,
    )
