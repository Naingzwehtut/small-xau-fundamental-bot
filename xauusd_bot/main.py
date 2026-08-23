"""
main.py
-------
Entry point for the XAUUSD Fundamental Analysis Bot.

Usage:
    python -m xauusd_bot.main                 # fetch live data, print + save report
    python -m xauusd_bot.main --no-save        # print only, don't write files
    python -m xauusd_bot.main --json-only      # only print the JSON payload

Requires FRED_API_KEY to be set as an environment variable (or in a .env
file loaded by python-dotenv). Market data via yfinance needs no key but
does need internet access to Yahoo Finance.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional; env vars can be set another way

from xauusd_bot import config
from xauusd_bot.fetchers import fred_fetcher, market_fetcher
from xauusd_bot.analysis import scoring
from xauusd_bot.report import generator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("xauusd_bot.main")


def run(save: bool = True, print_json: bool = False) -> scoring.BiasResult:
    logger.info("Fetching macroeconomic data from FRED...")
    fred_data = fred_fetcher.fetch_all()
    logger.info("Fetched %d/%d FRED series successfully.", len(fred_data), len(config.FRED_SERIES))

    logger.info("Fetching market data from Yahoo Finance...")
    market_data = market_fetcher.fetch_all()
    logger.info("Fetched %d/%d market tickers successfully.", len(market_data), len(config.MARKET_TICKERS))

    if not fred_data and not market_data:
        logger.error(
            "No data could be fetched at all. Check your FRED_API_KEY and internet connectivity."
        )
        sys.exit(1)

    logger.info("Computing fundamental bias score...")
    result = scoring.compute_bias(fred_data, market_data)

    gold_price = None
    if "gold_spot" in market_data:
        gold_price = market_data["gold_spot"].latest_close

    today = date.today()
    md_report = generator.to_markdown(result, report_date=today, gold_price=gold_price)
    json_report = generator.to_json(result, report_date=today, gold_price=gold_price)

    if print_json:
        print(json_report)
    else:
        print(md_report)

    if save:
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        md_path = os.path.join(config.OUTPUT_DIR, f"daily_report_{today.isoformat()}.md")
        json_path = os.path.join(config.OUTPUT_DIR, f"daily_report_{today.isoformat()}.json")
        with open(md_path, "w") as f:
            f.write(md_report)
        with open(json_path, "w") as f:
            f.write(json_report)
        logger.info("Saved reports to %s and %s", md_path, json_path)

    return result


def parse_args():
    parser = argparse.ArgumentParser(description="XAUUSD Fundamental Analysis Bot")
    parser.add_argument("--no-save", action="store_true", help="Don't write report files to disk")
    parser.add_argument("--json-only", action="store_true", help="Print JSON instead of Markdown")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(save=not args.no_save, print_json=args.json_only)
