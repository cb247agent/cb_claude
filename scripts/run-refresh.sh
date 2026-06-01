#!/bin/bash
# run-refresh.sh — Wrapper script to run CB247 Google data refresh.
# Usage: ./run-refresh.sh
# Can be called manually or from a launchd cron job.

cd "$(dirname "$0")/.." || exit 1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting CB247 data refresh..."
VENV_PYTHON="$(dirname "$0")/../.venv/bin/python3.13"
"$VENV_PYTHON" "$(dirname "$0")/pull_all.py"
exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Data refresh complete."
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Data refresh failed with exit code $exit_code."
fi

exit $exit_code