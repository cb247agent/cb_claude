#!/bin/bash
# qa.sh — Wave C (12 Jun 2026) — one-shot pre-push QA.
#
# Runs the full dev cycle (Wave A scripts) + visual regression (Wave C)
# against the local working tree + the live deployed dashboard. The
# Wave B agents (qa-agent, security-agent) are NOT run here — they're
# weekly-cron-only because they call Claude and cost tokens.
#
# WHAT IT CATCHES
#   - Brand voice / stale workflow vocab (Wave A scan_brand_voice)
#   - Schema drift between Python ↔ SQL (Wave A check_supabase_schema_drift)
#   - Strategist chain regressions (Wave A test_strategist_chain)
#   - Visual regressions on the live dashboard (Wave C visual_regression)
#
# DEFAULT: warn-only. Exit 0 even with findings — just prints them so you
# can decide. Pass --strict to exit 1 on any error finding.
#
# USAGE
#   bash scripts/qa.sh
#   bash scripts/qa.sh --strict
#   bash scripts/qa.sh --no-visual   # skip slow Playwright pass
#
# OUTPUT
#   Findings printed to terminal. JSON logs in logs/ for offline review.

set -u
cd "$(cd "$(dirname "$0")/.." && pwd)" || exit 2

PYTHON=".venv/bin/python3.13"
LOG_DIR="logs"
mkdir -p "$LOG_DIR"

STRICT=""
SKIP_VISUAL=0
for arg in "$@"; do
    case "$arg" in
        --strict)     STRICT="--strict" ;;
        --no-visual)  SKIP_VISUAL=1 ;;
        --help|-h)
            cat <<EOF
Usage: bash scripts/qa.sh [--strict] [--no-visual]
  --strict     Exit 1 on any error finding (default: warn-only)
  --no-visual  Skip Playwright visual regression (saves ~30s)
EOF
            exit 0
            ;;
    esac
done

echo "════════════════════════════════════════════════════════════════"
echo "  /qa — CB247 pre-push quality check  (strict=${STRICT:-no})"
echo "════════════════════════════════════════════════════════════════"
echo ""

FAILED=0

run_step() {
    local label="$1"
    local cmd="$2"
    echo "─── $label ───"
    if eval "$cmd"; then
        echo "✓ $label clean"
    else
        local code=$?
        if [[ -n "$STRICT" ]]; then
            echo "✗ $label exit $code (BLOCKING under --strict)"
            FAILED=$((FAILED + 1))
        else
            echo "⚠ $label exit $code (warn-only)"
        fi
    fi
    echo ""
}

# Wave A pre-commit (light + fast — no live Supabase probe, no dep audit)
run_step "Brand voice scan" \
    "$PYTHON scripts/scan_brand_voice.py --log $STRICT"

run_step "Schema drift (code-vs-code)" \
    "$PYTHON scripts/check_supabase_schema_drift.py --log $STRICT"

run_step "Strategist chain integration test" \
    "$PYTHON scripts/test_strategist_chain.py --log $STRICT"

# Wave C — visual regression (slow, can be skipped)
if [[ $SKIP_VISUAL -eq 0 ]]; then
    run_step "Visual regression vs baselines" \
        "$PYTHON scripts/visual_regression.py --source live --log $STRICT"
else
    echo "─── Visual regression ───"
    echo "⏭️  Skipped (--no-visual)"
    echo ""
fi

echo "════════════════════════════════════════════════════════════════"
if [[ $FAILED -eq 0 ]]; then
    echo "  /qa COMPLETE — all checks passed (or warn-only)"
    echo "════════════════════════════════════════════════════════════════"
    exit 0
else
    echo "  /qa FAILED — $FAILED check(s) hit blocking errors"
    echo "════════════════════════════════════════════════════════════════"
    exit 1
fi
