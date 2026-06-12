#!/bin/bash
# weekly-report.sh — CB247 Marketing OS  (full pipeline orchestrator)
#
# THIS IS A THIN ORCHESTRATOR. The real work lives in scripts/phases/.
# Before 12 Jun 2026 this file was 985 lines of inline data pulls + agent
# invocations. After the split, each phase is its own self-contained script
# that you can read + edit + smoke-test in isolation.
#
# Cron entry (Monday 10:00 AM Perth, AWST = UTC+8):
#   0 10 * * 1 /Users/tiachasingbetter/Documents/ChasingBetter/CB_Marketing/scripts/weekly-report.sh \
#       >> /Users/tiachasingbetter/Documents/ChasingBetter/CB_Marketing/state/weekly-report.log 2>&1
#
# Companion cron (Monday 11:30 AM Perth) — late Metricool PDF drops:
#   30 11 * * 1 .../scripts/refresh-social.sh >> .../state/refresh-social.log 2>&1
#
# PIPELINE
#   Phase 0    — Dev cycle pre-flight + Security agent       (~30-60s)
#   Phase 1    — Data pulls + emitters + sync + briefs + QA + visual reg  (~25 min)
#   Phase 1.5  — Build compressed context files               (~5 sec)
#   Phase 2    — 9 LLM marketing agents in sequence           (~40 min)
#   Phase 3    — Bake HTML reports + dashboard deploy         (~2 min)
#   Phase 4    — Email Tia OS report + approval prompt        (~5 sec)
#   Phase 5    — Structured JSON run log for monitoring       (~1 sec)
#
# APPROVAL FLOW
#   Agents generate → Tia reviews (dashboard + OS report email) → Tia approves
#   → Brand Manager receives content pipeline for QC → Brand Manager approves
#   → Joanne gets posting schedule
#
# NOTE: weekly-seo.sh is merged into this pipeline. Do NOT run weekly-seo.sh
# separately — all data pulls happen once here to preserve API quotas.

# Master script does NOT use `set -e` — Phase scripts each handle their own
# error tolerance (failed agents/pulls are tracked in FAILED_AGENTS[], not
# script-killing).

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PIPELINE_START=$(date +%s)

# Source the shared setup — gives us $PYTHON, $CLAUDE, $LOG, log(), run_agent(),
# FAILED_AGENTS[] etc. Each phase script ALSO sources this; it's idempotent.
source "$BASE_DIR/scripts/phases/_common.sh"

cd "$BASE_DIR" || exit 2

log "================================================================"
log "  CB247 MARKETING OS — MONDAY RUN STARTED"
log "================================================================"

# ── Run each phase in order. They share the shell (no subshells), so
# FAILED_AGENTS[] survives across phases. Any phase that exits non-zero
# would propagate here, but the phase scripts intentionally return 0 in
# all soft-failure paths (the FAILED_AGENTS[] array is the real signal).
source "$BASE_DIR/scripts/phases/phase0_preflight.sh"
source "$BASE_DIR/scripts/phases/phase1_data.sh"
source "$BASE_DIR/scripts/phases/phase1_5_context.sh"
source "$BASE_DIR/scripts/phases/phase2_agents.sh"
source "$BASE_DIR/scripts/phases/phase3_reports.sh"
source "$BASE_DIR/scripts/phases/phase4_email.sh"
source "$BASE_DIR/scripts/phases/phase5_runlog.sh"

# ── Final summary ────────────────────────────────────────────────────────
PIPELINE_END=$(date +%s)
DURATION=$((PIPELINE_END - PIPELINE_START))
DURATION_MIN=$((DURATION / 60))

log ""
log "================================================================"
log "  CB247 MARKETING OS — MONDAY RUN COMPLETE ($DURATION_MIN min)"
if [[ ${#FAILED_AGENTS[@]} -gt 0 ]]; then
    log "  ⚠️  ${#FAILED_AGENTS[@]} agent failure(s): ${FAILED_AGENTS[*]}"
else
    log "  ✅ All phases ran clean"
fi
log "================================================================"
