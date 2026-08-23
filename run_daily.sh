#!/usr/bin/env bash
# run_daily.sh
#
# Convenience wrapper for scheduling the bot with cron (or Task Scheduler
# via WSL, or a CI scheduled workflow). Activates the venv if present,
# runs the bot, and lets stdout/stderr get redirected to a log by cron.
#
# Example crontab entry (runs every day at 07:00 server time):
#   0 7 * * * /path/to/xauusd_bot/run_daily.sh >> /path/to/xauusd_bot/output/cron.log 2>&1

set -euo pipefail
cd "$(dirname "$0")"

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

python3 -m xauusd_bot.main
