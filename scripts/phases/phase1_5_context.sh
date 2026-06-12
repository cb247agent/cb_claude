#!/bin/bash
# phase1_5_context.sh — Build compressed context files for Phase 2 agents.
#
# The agents in Phase 2 read context/*.json (compressed views) not raw
# state/*.json (Layer 2 boundary). This phase generates the context files
# AFTER Phase 1 has refreshed all the state files.
#
# Sourced + run from scripts/weekly-report.sh.

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

# ══════════════════════════════════════════════════════════════════
# PHASE 1.5 — BUILD CONTEXT FILES (Python only, zero LLM, ~5 sec)
# Compresses state/*.json into per-agent context files (~1-2k tokens each)
# Agents in Phase 2 read ONLY these context files — not state/ directly
# ══════════════════════════════════════════════════════════════════
log ""
log "─── PHASE 1.5: BUILD CONTEXT FILES ───"
bash "$BASE_DIR/scripts/run-bake.sh" --context-only >> "$LOG" 2>&1 \
    || fail "run-bake.sh context build had issues — agents will use stale context files"
log "Phase 1.5 complete."
