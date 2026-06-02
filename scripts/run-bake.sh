#!/bin/bash
# run-bake.sh — Post-pull bake step (Layer 1, zero LLM).
#
# Runs after every data pull to:
#   1. Build per-agent context files from state/*.json
#   2. Bake the HTML dashboard from fresh state data
#
# Called by weekly-report.sh between Phase 1 and Phase 2,
# and by the com.cb247.data-refresh launchd job independently.
#
# Usage:
#   bash scripts/run-bake.sh
#   bash scripts/run-bake.sh --context-only   # skip dashboard bake
#   bash scripts/run-bake.sh --dashboard-only # skip context build

set -e
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${BASE_DIR}/.venv/bin/python3.13"
LOG="${BASE_DIR}/state/run-bake.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"; }
fail() { log "ERROR: $1"; }

CONTEXT_ONLY=false
DASHBOARD_ONLY=false
for arg in "$@"; do
    case "$arg" in
        --context-only)   CONTEXT_ONLY=true ;;
        --dashboard-only) DASHBOARD_ONLY=true ;;
    esac
done

log "=== CB247 Bake Step Started ==="
cd "$BASE_DIR"

if [ "$DASHBOARD_ONLY" = false ]; then
    log "Step 1 — Building per-agent context files..."
    if "$PYTHON" "$BASE_DIR/context/build_context.py" >> "$LOG" 2>&1; then
        log "  ✅ Context files built (8 agents)"
    else
        fail "build_context.py failed — agents will use stale context files"
    fi
fi

if [ "$CONTEXT_ONLY" = false ]; then
    log "Step 2 — Baking HTML dashboard..."
    if "$PYTHON" "$BASE_DIR/scripts/bake-dashboard.py" >> "$LOG" 2>&1; then
        log "  ✅ Dashboard baked"
    else
        fail "bake-dashboard.py had issues — check $LOG"
    fi
fi

log "=== CB247 Bake Step Complete ==="
