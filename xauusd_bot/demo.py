"""
demo.py
-------
Runs the full fetch -> score -> report pipeline using synthetic sample
data, so you can see exactly what the bot produces without needing a
FRED API key or live internet access.

Usage:
    python -m xauusd_bot.demo                 # mixed/neutral scenario
    python -m xauusd_bot.demo --scenario bullish
    python -m xauusd_bot.demo --scenario bearish
"""

from __future__ import annotations

import argparse
from datetime import date

from xauusd_bot.analysis import scoring
from xauusd_bot.data import sample_data
from xauusd_bot.report import generator


def run_demo(scenario: str = "mixed") -> scoring.BiasResult:
    fred_data = sample_data.sample_fred_data(scenario)
    market_data = sample_data.sample_market_data(scenario)

    result = scoring.compute_bias(fred_data, market_data)
    gold_price = market_data["gold_spot"].latest_close

    print(f"\n{'='*70}\nDEMO MODE -- using synthetic '{scenario}' scenario data, NOT live data\n{'='*70}\n")
    print(generator.to_markdown(result, report_date=date.today(), gold_price=gold_price))
    return result


def parse_args():
    parser = argparse.ArgumentParser(description="Demo the XAUUSD bot with synthetic data")
    parser.add_argument("--scenario", choices=["bullish", "bearish", "mixed"], default="mixed")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_demo(args.scenario)
