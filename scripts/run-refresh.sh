#!/bin/bash
# run-refresh.sh — CB247 daily data refresh + downstream bake.
# Usage: ./run-refresh.sh
# Can be called manually or from a launchd cron job.
#
# Pipeline:
#   1. pull_all.py        — refresh GA4, GSC, Google Ads, Meta into state/*.json
#   2. build_context.py   — compress state/ into per-agent context/*.json (~5 sec, zero LLM)
#   3. bake-public-dashboard.py  — rebuild HTML dashboard from fresh data
#   4. push_dashboard.py  — deploy dashboard to GitHub Pages
#
# If pull_all.py fails, all downstream steps are skipped (stale data > broken dashboard).

REFRESH_START=$(date +%s)
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$BASE_DIR/.venv/bin/python3.13"

cd "$BASE_DIR" || exit 1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting CB247 data refresh..."

"$PYTHON" "$BASE_DIR/scripts/pull_all.py"
exit_code=$?

if [ $exit_code -ne 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Data refresh failed (exit $exit_code) — skipping dashboard bake."
    exit $exit_code
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Data refresh complete."

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Building agent contexts..."
"$PYTHON" "$BASE_DIR/context/build_context.py" \
    || echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARN: context build had issues — agents will use prior context"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Baking dashboard..."
"$PYTHON" "$BASE_DIR/scripts/bake-public-dashboard.py" \
    || echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARN: dashboard bake failed — dashboard may be stale"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Pushing dashboard..."
"$PYTHON" "$BASE_DIR/scripts/push_dashboard.py" \
    || echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARN: dashboard push failed — check GitHub Pages access"

REFRESH_END=$(date +%s)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] run-refresh.sh complete. Duration: $((REFRESH_END - REFRESH_START))s"
