"""
generator.py
------------
Turns a BiasResult into user-facing artifacts:
  * A Markdown daily report (human-readable, with factor breakdown table)
  * A JSON payload (machine-readable, for feeding into other systems /
    dashboards / alerting)
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Optional

from xauusd_bot.analysis.scoring import BiasResult


def _score_bar(score: float, width: int = 20) -> str:
    """Render a simple text bar for a [-2, +2] score, for terminal/markdown display."""
    normalized = (score + 2) / 4  # -> [0, 1]
    filled = round(normalized * width)
    filled = max(0, min(width, filled))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def to_markdown(result: BiasResult, report_date: Optional[date] = None,
                 gold_price: Optional[float] = None) -> str:
    report_date = report_date or date.today()
    lines = []
    lines.append(f"# XAUUSD Fundamental Bias Report — {report_date.isoformat()}")
    lines.append("")
    if gold_price is not None:
        lines.append(f"**Gold spot (proxy):** ${gold_price:,.2f}")
    lines.append(f"**Overall Bias Score:** {result.bias_score_0_100:.1f} / 100 — **{result.label}**")
    lines.append(f"**Weighted Raw Score:** {result.weighted_avg_raw:+.2f} (range -2.0 bearish to +2.0 bullish)")
    lines.append("")
    lines.append("## Factor Breakdown")
    lines.append("")
    lines.append("| Factor | Weight | Score | Visual | Read |")
    lines.append("|---|---|---|---|---|")
    for f in sorted(result.factor_scores, key=lambda x: -x.weight):
        direction = "Bullish" if f.score > 0.3 else "Bearish" if f.score < -0.3 else "Neutral"
        lines.append(
            f"| {f.label} | {f.weight:.0%} | {f.score:+.2f} | `{_score_bar(f.score)}` | {direction} |"
        )
    lines.append("")
    lines.append("## Explanations")
    lines.append("")
    for f in sorted(result.factor_scores, key=lambda x: -x.weight):
        lines.append(f"**{f.label}** ({f.score:+.2f}, weight {f.weight:.0%})")
        lines.append(f"> {f.explanation}")
        if f.data_points:
            details = ", ".join(f"{k}: {v}" for k, v in f.data_points.items())
            lines.append(f"> *Data: {details}*")
        lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(_narrative_summary(result))
    lines.append("")
    lines.append("---")
    lines.append(
        "*This report is generated automatically from public macroeconomic and market data. "
        "It reflects a rules-based interpretation of well-documented gold-macro relationships and "
        "is provided for informational purposes only — it is not financial advice.*"
    )
    return "\n".join(lines)


def _narrative_summary(result: BiasResult) -> str:
    bullish_factors = [f for f in result.factor_scores if f.score > 0.3]
    bearish_factors = [f for f in result.factor_scores if f.score < -0.3]
    neutral_factors = [f for f in result.factor_scores if -0.3 <= f.score <= 0.3]

    parts = [f"The overall fundamental bias for gold is **{result.label}** "
             f"(score {result.bias_score_0_100:.1f}/100)."]

    if bullish_factors:
        names = ", ".join(f.label for f in bullish_factors)
        parts.append(f"Bullish support comes from: {names}.")
    if bearish_factors:
        names = ", ".join(f.label for f in bearish_factors)
        parts.append(f"Bearish pressure comes from: {names}.")
    if neutral_factors and not (bullish_factors or bearish_factors):
        parts.append("Most factors are currently reading close to neutral, suggesting a balanced "
                      "macro backdrop with no strong directional edge.")

    return " ".join(parts)


def to_json(result: BiasResult, report_date: Optional[date] = None,
            gold_price: Optional[float] = None) -> str:
    report_date = report_date or date.today()
    payload = {
        "date": report_date.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gold_price_proxy": gold_price,
        "bias_score_0_100": result.bias_score_0_100,
        "weighted_raw_score": result.weighted_avg_raw,
        "label": result.label,
        "factors": [
            {
                "key": f.key,
                "label": f.label,
                "weight": f.weight,
                "score": f.score,
                "explanation": f.explanation,
                "data": f.data_points,
            }
            for f in result.factor_scores
        ],
    }
    return json.dumps(payload, indent=2)
