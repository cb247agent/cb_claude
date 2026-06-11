#!/bin/bash
# dev-cycle.sh — Wave A wrapper (11 Jun 2026) — orchestrate the 4 dev-cycle
# checks (brand voice scan, schema drift, integration test, dep audit) with
# two scope profiles:
#
#   --pre-commit  — light + fast (<10s total). Run before every commit.
#                   Skips the slow live Supabase probe and the dep audit.
#   --pre-flight  — heavy (~30-60s). Run before Monday's weekly data pull.
#                   Includes everything: live drift probe + dep audit.
#
# DEFAULT MODE: warn-only. None of the underlying scripts exit non-zero on
# findings unless --strict is passed individually. This wrapper preserves
# that — it ALWAYS exits 0 unless --strict is passed. Promote a check to
# blocking by adding --strict in the individual script invocation below.
#
# OUTPUT
#   Each script's JSON findings land in logs/<check>-<date>.json so you can
#   see what was found without re-running.
#
# WIRED IN
#   scripts/weekly-report.sh Step 0  — runs --pre-flight before the data
#                                       pulls so we fail fast on schema
#                                       drift instead of crashing during
#                                       sync_to_supabase.
#   Recommended pre-commit hook (manual, not enforced):
#     bash scripts/dev-cycle.sh --pre-commit

set -u   # treat unset vars as errors (not -e — we want all checks to run even if one fails)

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$BASE_DIR" || exit 2

PYTHON="$BASE_DIR/.venv/bin/python3.13"
LOG_DIR="$BASE_DIR/logs"
mkdir -p "$LOG_DIR"

DATE=$(date '+%Y-%m-%d')
LOG="$LOG_DIR/dev-cycle-$DATE.log"

MODE="${1:---pre-commit}"
STRICT_FLAG=""
if [[ "${2:-}" == "--strict" ]] || [[ "${1:-}" == "--strict" ]]; then
    STRICT_FLAG="--strict"
fi

log() {
    local line="[$(date '+%H:%M:%S')] $1"
    echo "$line" | tee -a "$LOG"
}

log "════════════════════════════════════════════════════════════════"
log "  CB247 DEV CYCLE — $MODE  (strict=${STRICT_FLAG:-no})"
log "════════════════════════════════════════════════════════════════"

ANY_BLOCKING_FAILURE=0
run_check() {
    local label="$1"
    local cmd="$2"
    log "─── $label ───"
    if bash -c "$cmd" 2>&1 | tee -a "$LOG" | sed 's/^/    /'; then
        local exit_code=${PIPESTATUS[0]}
        if [[ $exit_code -ne 0 ]] && [[ -n "$STRICT_FLAG" ]]; then
            log "✗ $label exited $exit_code (blocking under --strict)"
            ANY_BLOCKING_FAILURE=1
        elif [[ $exit_code -ne 0 ]]; then
            log "⚠ $label exited $exit_code (warn-only mode — not blocking)"
        else
            log "✓ $label clean"
        fi
    else
        log "⚠ $label crashed — see log"
    fi
    log ""
}

if [[ "$MODE" == "--pre-commit" ]]; then
    # Light + fast: code-vs-code checks only. <10s total.
    run_check "Brand voice + compliance scan" \
        "$PYTHON scripts/scan_brand_voice.py --log $STRICT_FLAG"
    run_check "Schema drift (code-vs-code only)" \
        "$PYTHON scripts/check_supabase_schema_drift.py --log $STRICT_FLAG"
    run_check "Strategist chain integration test" \
        "$PYTHON scripts/test_strategist_chain.py --log $STRICT_FLAG"

elif [[ "$MODE" == "--pre-flight" ]]; then
    # Heavy: everything, including live Supabase probe + slow dep audit.
    run_check "Brand voice + compliance scan" \
        "$PYTHON scripts/scan_brand_voice.py --log $STRICT_FLAG"
    run_check "Schema drift (incl. live Supabase probe)" \
        "$PYTHON scripts/check_supabase_schema_drift.py --live --log $STRICT_FLAG"
    run_check "Strategist chain integration test" \
        "$PYTHON scripts/test_strategist_chain.py --log $STRICT_FLAG"
    run_check "Dependency vulnerability audit" \
        "$PYTHON scripts/audit_dependencies.py --log $STRICT_FLAG"

else
    log "Unknown mode: $MODE"
    log "Usage:"
    log "  scripts/dev-cycle.sh --pre-commit  [--strict]"
    log "  scripts/dev-cycle.sh --pre-flight  [--strict]"
    exit 2
fi

log "════════════════════════════════════════════════════════════════"
if [[ $ANY_BLOCKING_FAILURE -eq 0 ]]; then
    log "  DEV CYCLE COMPLETE — clean (warnings may have been printed)"
    log "════════════════════════════════════════════════════════════════"
    exit 0
else
    log "  DEV CYCLE FAILED — $ANY_BLOCKING_FAILURE check(s) hit blocking errors"
    log "════════════════════════════════════════════════════════════════"
    exit 1
fi
