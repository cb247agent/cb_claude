#!/bin/bash
# phase5_runlog.sh — Write structured JSON run log for cron monitoring.
#
# Reads FAILED_AGENTS[] + pipeline duration, writes logs/run-YYYYMMDD-...json.
# Used by the monitoring dashboard to spot run health drifting.
#
# Sourced + run from scripts/weekly-report.sh.

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

# ══════════════════════════════════════════════════════════════════
# PHASE 5 — RUN LOG (structured JSON, zero LLM)
# ══════════════════════════════════════════════════════════════════
PIPELINE_END=$(date +%s)
PIPELINE_DURATION=$((PIPELINE_END - PIPELINE_START))
RUN_STATUS=$( [ ${#FAILED_AGENTS[@]} -eq 0 ] && echo "success" || echo "partial" )
FAILED_CSV="$(IFS=,; echo "${FAILED_AGENTS[*]}")"

log ""
log "─── PHASE 5: WRITING RUN LOG ───"
"$PYTHON" "$BASE_DIR/scripts/log_run.py" \
    --business cb247 \
    --status "$RUN_STATUS" \
    --failed-agents "$FAILED_CSV" \
    --duration-seconds "$PIPELINE_DURATION" \
    | tee -a "$LOG"

log ""
log "================================================================"
log "  CB247 MARKETING OS — RUN COMPLETE"
log "================================================================"
log "  Status    : $RUN_STATUS | Duration: ${PIPELINE_DURATION}s"
log "  ✅ Data pulled    : GA4 + GSC + Google Ads + Ahrefs + Apify"
if [ ${#FAILED_AGENTS[@]} -eq 0 ]; then
    log "  ✅ Agents run     : 9/9"
else
    log "  ⚠️  Agents run     : $(( 9 - ${#FAILED_AGENTS[@]} ))/9 — failed: $FAILED_CSV"
fi
log "  ✅ Outputs baked  : HTML report + dashboard"
log "  ✅ Dashboard live : https://cb247agent.github.io/cb_claude/"
log "  📧 Tia notified   : OS report + approval prompt sent"
log "  ⏸  Team emails   : HELD — awaiting Tia approval"
log "  📋 Run log        : logs/last-run.json"
log "================================================================"
log "  Outputs:"
log "    Research   : $OUTPUTS/research/weekly-research-$DATE.md"
log "    Audience   : $OUTPUTS/research/audience-weekly-$DATE.md"
log "    Content Intel: $OUTPUTS/research/content-intel-$DATE.md"
log "    Performance: $OUTPUTS/research/performance-week-$DATE.md"
log "    SEO Brief  : $OUTPUTS/seo/weekly-seo-brief-$DATE.md"
log "    Competitor : $OUTPUTS/research/competitor-weekly-$DATE.md"
log "    Paid Ads   : $OUTPUTS/research/paid-ads-weekly-$DATE.md"
log "    Content    : $OUTPUTS/content/weekly-content-$DATE.md"
log "    Strategy   : $OUTPUTS/blueprints/weekly-strategy-$DATE.md"
log "================================================================"
