"""
test_scoring.py
----------------
Unit tests for the scoring engine. Uses the synthetic sample data in
xauusd_bot.data.sample_data so tests are deterministic and require no
network access or API key.

Run with:
    python -m pytest tests/
or:
    python -m unittest discover tests
"""

import unittest

from xauusd_bot.analysis import scoring
from xauusd_bot.data import sample_data
from xauusd_bot.fetchers.fred_fetcher import Observation
from xauusd_bot.fetchers.market_fetcher import MarketSeries
from xauusd_bot.report import generator
from datetime import datetime, timedelta
import pandas as pd


class TestScaleLinear(unittest.TestCase):
    def test_midpoint_is_zero(self):
        self.assertAlmostEqual(scoring._scale_linear(0, -30, 30), 0.0)

    def test_endpoints(self):
        self.assertAlmostEqual(scoring._scale_linear(-30, -30, 30), -2.0)
        self.assertAlmostEqual(scoring._scale_linear(30, -30, 30), 2.0)

    def test_clamps_beyond_range(self):
        self.assertAlmostEqual(scoring._scale_linear(1000, -30, 30), 2.0)
        self.assertAlmostEqual(scoring._scale_linear(-1000, -30, 30), -2.0)

    def test_inverted_relationship(self):
        # x_bear > x_bull: higher x should score lower, lower x should score higher
        self.assertAlmostEqual(scoring._scale_linear(30, 30, -30), -2.0)   # at x_bear -> -2
        self.assertAlmostEqual(scoring._scale_linear(-30, 30, -30), 2.0)   # at x_bull -> +2


class TestFactorScorers(unittest.TestCase):
    def setUp(self):
        self.fred_bull = sample_data.sample_fred_data("bullish")
        self.fred_bear = sample_data.sample_fred_data("bearish")
        self.market_bull = sample_data.sample_market_data("bullish")
        self.market_bear = sample_data.sample_market_data("bearish")

    def test_real_yields_bullish_scenario_is_positive(self):
        f = scoring.score_real_yields(self.fred_bull)
        self.assertGreater(f.score, 0)

    def test_real_yields_bearish_scenario_is_negative(self):
        f = scoring.score_real_yields(self.fred_bear)
        self.assertLess(f.score, 0)

    def test_dollar_index_bullish_scenario_is_positive(self):
        f = scoring.score_dollar_index(self.market_bull, self.fred_bull)
        self.assertGreater(f.score, 0)

    def test_dollar_index_bearish_scenario_is_negative(self):
        f = scoring.score_dollar_index(self.market_bear, self.fred_bear)
        self.assertLess(f.score, 0)

    def test_inflation_bullish_scenario_is_positive(self):
        f = scoring.score_inflation(self.fred_bull)
        self.assertGreater(f.score, 0)

    def test_inflation_bearish_scenario_is_non_positive(self):
        f = scoring.score_inflation(self.fred_bear)
        self.assertLessEqual(f.score, 0)

    def test_fed_policy_cutting_is_bullish(self):
        f = scoring.score_fed_policy(self.fred_bull)
        self.assertGreater(f.score, 0)

    def test_fed_policy_hiking_is_bearish(self):
        f = scoring.score_fed_policy(self.fred_bear)
        self.assertLess(f.score, 0)

    def test_labor_market_rising_unemployment_is_bullish(self):
        f = scoring.score_labor_market(self.fred_bull)
        self.assertGreater(f.score, 0)

    def test_labor_market_falling_unemployment_is_bearish(self):
        f = scoring.score_labor_market(self.fred_bear)
        self.assertLess(f.score, 0)

    def test_risk_sentiment_risk_off_is_bullish(self):
        f = scoring.score_risk_sentiment(self.market_bull)
        self.assertGreater(f.score, 0)

    def test_risk_sentiment_risk_on_is_bearish(self):
        f = scoring.score_risk_sentiment(self.market_bear)
        self.assertLess(f.score, 0)

    def test_money_supply_expansion_is_bullish(self):
        f = scoring.score_money_supply(self.fred_bull)
        self.assertGreater(f.score, 0)

    def test_missing_data_returns_neutral_not_crash(self):
        f = scoring.score_real_yields({})
        self.assertEqual(f.score, 0.0)
        f2 = scoring.score_dollar_index({}, {})
        self.assertEqual(f2.score, 0.0)


class TestComposite(unittest.TestCase):
    def test_bullish_scenario_scores_high(self):
        fred_data = sample_data.sample_fred_data("bullish")
        market_data = sample_data.sample_market_data("bullish")
        result = scoring.compute_bias(fred_data, market_data)
        self.assertGreater(result.bias_score_0_100, 60)
        self.assertIn(result.label, ("Bullish", "Strongly Bullish"))

    def test_bearish_scenario_scores_low(self):
        fred_data = sample_data.sample_fred_data("bearish")
        market_data = sample_data.sample_market_data("bearish")
        result = scoring.compute_bias(fred_data, market_data)
        self.assertLess(result.bias_score_0_100, 40)
        self.assertIn(result.label, ("Bearish", "Strongly Bearish"))

    def test_mixed_scenario_scores_near_neutral(self):
        fred_data = sample_data.sample_fred_data("mixed")
        market_data = sample_data.sample_market_data("mixed")
        result = scoring.compute_bias(fred_data, market_data)
        self.assertTrue(30 < result.bias_score_0_100 < 70)

    def test_score_bounds_always_0_to_100(self):
        for scenario in ("bullish", "bearish", "mixed"):
            fred_data = sample_data.sample_fred_data(scenario)
            market_data = sample_data.sample_market_data(scenario)
            result = scoring.compute_bias(fred_data, market_data)
            self.assertGreaterEqual(result.bias_score_0_100, 0)
            self.assertLessEqual(result.bias_score_0_100, 100)

    def test_empty_input_is_neutral(self):
        result = scoring.compute_bias({}, {})
        self.assertAlmostEqual(result.bias_score_0_100, 50.0)
        self.assertEqual(result.label, "Neutral")

    def test_all_seven_factors_present(self):
        fred_data = sample_data.sample_fred_data("mixed")
        market_data = sample_data.sample_market_data("mixed")
        result = scoring.compute_bias(fred_data, market_data)
        self.assertEqual(len(result.factor_scores), 7)


class TestReportGeneration(unittest.TestCase):
    def setUp(self):
        fred_data = sample_data.sample_fred_data("mixed")
        market_data = sample_data.sample_market_data("mixed")
        self.result = scoring.compute_bias(fred_data, market_data)

    def test_markdown_contains_key_sections(self):
        md = generator.to_markdown(self.result, gold_price=2400.0)
        self.assertIn("Overall Bias Score", md)
        self.assertIn("Factor Breakdown", md)
        self.assertIn("Explanations", md)
        self.assertIn("Summary", md)
        self.assertIn("not financial advice", md)

    def test_json_is_valid_and_complete(self):
        import json
        raw = generator.to_json(self.result, gold_price=2400.0)
        payload = json.loads(raw)
        self.assertIn("bias_score_0_100", payload)
        self.assertIn("factors", payload)
        self.assertEqual(len(payload["factors"]), 7)
        self.assertEqual(payload["gold_price_proxy"], 2400.0)


class TestFredHelpers(unittest.TestCase):
    def test_percent_change_basic(self):
        from xauusd_bot.fetchers.fred_fetcher import percent_change
        obs = [
            Observation(date=datetime(2024, 1, 1), value=100.0),
            Observation(date=datetime(2024, 2, 1), value=110.0),
        ]
        self.assertAlmostEqual(percent_change(obs, 1), 10.0)

    def test_percent_change_handles_nulls(self):
        from xauusd_bot.fetchers.fred_fetcher import percent_change
        obs = [
            Observation(date=datetime(2024, 1, 1), value=100.0),
            Observation(date=datetime(2024, 2, 1), value=None),
            Observation(date=datetime(2024, 3, 1), value=120.0),
        ]
        # skips the null when counting "periods back"
        self.assertAlmostEqual(percent_change(obs, 1), 20.0)

    def test_latest_value_skips_trailing_nulls(self):
        from xauusd_bot.fetchers.fred_fetcher import latest_value
        obs = [
            Observation(date=datetime(2024, 1, 1), value=100.0),
            Observation(date=datetime(2024, 2, 1), value=None),
        ]
        self.assertEqual(latest_value(obs), 100.0)


class TestMarketSeries(unittest.TestCase):
    def test_pct_change(self):
        today = datetime.today()
        dates = [today - timedelta(days=4 - i) for i in range(5)]
        df = pd.DataFrame({"Close": [100, 102, 104, 103, 110]}, index=pd.DatetimeIndex(dates))
        series = MarketSeries(ticker="TEST", history=df)
        self.assertAlmostEqual(series.pct_change(4), 10.0)

    def test_pct_change_insufficient_history(self):
        today = datetime.today()
        df = pd.DataFrame({"Close": [100.0]}, index=pd.DatetimeIndex([today]))
        series = MarketSeries(ticker="TEST", history=df)
        self.assertIsNone(series.pct_change(5))


if __name__ == "__main__":
    unittest.main()
