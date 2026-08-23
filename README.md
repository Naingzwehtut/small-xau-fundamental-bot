# XAUUSD Fundamental Analysis Bot

Automatically fetches macroeconomic data relevant to gold (XAUUSD) and
produces a daily **bullish / bearish bias score (0–100)** with a plain-English
explanation of what's driving it.

Instead of predicting price, the bot answers a narrower, more honest question:
*"Given today's macro backdrop, does the fundamental picture favor gold
being bid up or sold off?"*

## How it works

The bot pulls two kinds of data every day:

1. **Macro data from [FRED](https://fred.stlouisfed.org/)** (Federal Reserve
   Economic Data) — real yields, inflation, Fed policy, unemployment, money
   supply.
2. **Market data from Yahoo Finance** (via `yfinance`) — the US Dollar Index,
   VIX, S&P 500, and gold spot price. No API key needed for this part.

It then scores **7 independent factors**, each on a scale from **-2
(strongly bearish) to +2 (strongly bullish)**, using well-documented
gold-macro relationships:

| Factor | Weight | Bullish for gold when... |
|---|---|---|
| Real Yields (10Y TIPS) | 25% | Real yields are falling (lower opportunity cost of holding gold) |
| US Dollar Index (DXY) | 20% | The dollar is weakening (gold gets cheaper for foreign buyers) |
| Inflation (CPI / Core PCE) | 15% | Inflation is running above the Fed's 2% target |
| Fed Funds Rate / Policy | 15% | The Fed is cutting rates / turning dovish |
| Labor Market (Unemployment) | 10% | Unemployment is rising (raises rate-cut odds) |
| Risk Sentiment (VIX / S&P 500) | 10% | Volatility is elevated / equities are selling off (safe-haven flows) |
| Money Supply Growth (M2) | 5% | M2 is expanding faster (currency-debasement hedge demand) |

The 7 weighted scores are combined into a single **0–100 bias score**:

- **0–20** Strongly Bearish
- **20–40** Bearish
- **40–60** Neutral
- **60–80** Bullish
- **80–100** Strongly Bullish

Every factor comes with its own explanation and the underlying data point,
so the final number is never a black box.

## Project structure

```
xauusd_bot/
├── xauusd_bot/
│   ├── main.py                 # entry point — fetch, score, report (live data)
│   ├── demo.py                 # entry point — same pipeline, synthetic data
│   ├── config.py                # series IDs, tickers, weights, thresholds
│   ├── fetchers/
│   │   ├── fred_fetcher.py      # FRED API client
│   │   └── market_fetcher.py    # Yahoo Finance client (yfinance)
│   ├── analysis/
│   │   └── scoring.py           # the 7 factor scorers + composite bias score
│   ├── report/
│   │   └── generator.py         # renders Markdown + JSON reports
│   └── data/
│       └── sample_data.py       # synthetic data for demo.py and tests
├── tests/
│   └── test_scoring.py          # 31 unit tests, no network required
├── output/                       # daily reports get saved here
├── requirements.txt
├── .env.example
├── run_daily.sh                  # cron-friendly wrapper
└── README.md
```

## Setup

```bash
cd xauusd_bot
python3 -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Get a **free** FRED API key at
https://fred.stlouisfed.org/docs/api/api_key.html and paste it into `.env`:

```
FRED_API_KEY=your_key_here
```

Yahoo Finance data via `yfinance` needs no API key, just internet access.

## Usage

### Try it instantly, no API key needed (synthetic data)

```bash
python -m xauusd_bot.demo --scenario bullish
python -m xauusd_bot.demo --scenario bearish
python -m xauusd_bot.demo --scenario mixed
```

This runs the full fetch → score → report pipeline against realistic,
hand-crafted synthetic data so you can see the exact report format before
wiring up live data.

### Run against live data

```bash
python -m xauusd_bot.main
```

This will:
1. Pull the latest FRED and Yahoo Finance data
2. Compute the composite bias score
3. Print a Markdown report to the terminal
4. Save `output/daily_report_<date>.md` and `output/daily_report_<date>.json`

Other flags:

```bash
python -m xauusd_bot.main --no-save      # print only, don't write files
python -m xauusd_bot.main --json-only    # print JSON instead of Markdown
```

### Schedule it to run daily

Use the included wrapper with cron:

```bash
crontab -e
# add this line to run every weekday at 7:00 AM:
0 7 * * 1-5 /full/path/to/xauusd_bot/run_daily.sh >> /full/path/to/xauusd_bot/output/cron.log 2>&1
```

(Gold-relevant macro releases mostly land on US business days, so running
on weekdays is usually sufficient — adjust as you like.)

### Run the tests

```bash
python -m pytest tests/ -v
```

31 tests cover the scaling math, each individual factor scorer under
bullish/bearish synthetic conditions, the composite score, missing-data
edge cases, and report generation.

## Sample output

```
# XAUUSD Fundamental Bias Report — 2026-08-23

**Gold spot (proxy):** $2,490.00
**Overall Bias Score:** 86.6 / 100 — **Strongly Bullish**
**Weighted Raw Score:** +1.46 (range -2.0 bearish to +2.0 bullish)

## Factor Breakdown

| Factor | Weight | Score | Visual | Read |
|---|---|---|---|---|
| Real Yields (10Y TIPS) | 25% | +1.67 | [##################--] | Bullish |
| US Dollar Index (DXY) | 20% | +2.00 | [####################] | Bullish |
| Fed Funds Rate / Policy Stance | 15% | +2.00 | [####################] | Bullish |
...

## Explanations

**Real Yields (10Y TIPS)** (+1.67, weight 25%)
> 10Y real (TIPS) yield is 1.60%, falling 25bp vs. the prior reading.
> Falling real yields lower the opportunity cost of holding non-yielding
> gold (bullish).
```

## Extending the bot

- **Add a new factor:** write a `score_xxx()` function in `scoring.py`
  following the existing pattern (return a `FactorScore`), add it to
  `compute_bias()`, and add a weight to `config.WEIGHTS` (weights must
  sum to 1.0 across all active factors — enforced by an assertion in
  `config.py`).
- **Change weights or thresholds:** everything tunable lives in
  `config.py` — no need to touch the scoring logic itself.
- **Send alerts:** `generator.to_json()` returns a clean payload you can
  pipe into Slack/Discord/email webhooks from `main.py`.
- **Backtest:** `sample_data.py` shows the data shapes expected by
  `scoring.compute_bias()` — swap in historical FRED/Yahoo pulls for a
  given date to backtest how the score would have read historically.

## Important notes

- **This is not financial advice.** The bot encodes textbook, well-known
  macro/gold relationships as transparent rules — it does not predict
  price, is not a trading signal generator, and past macro relationships
  can and do break down (e.g. during acute geopolitical shocks).
- **Data quality depends on your sources.** FRED updates on each series'
  own release schedule (some monthly, some daily) — the bot always uses
  the latest available print, which may lag the calendar date.
- **Rate limits:** FRED's free tier allows generous request volume for a
  once-daily job; Yahoo Finance via `yfinance` is unofficial and can
  occasionally throttle or change format — `main.py` degrades gracefully
  (skips a factor) rather than crashing if one series fails.
