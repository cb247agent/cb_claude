#!/bin/bash
# phase4_email.sh — Send Tia the OS report + approval prompt.
#
# Team emails are HELD until Tia approves the recommendations via the
# dashboard. This phase only fires the OS-Owner email.
#
# Sourced + run from scripts/weekly-report.sh.

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

# ══════════════════════════════════════════════════════════════════
# PHASE 4 — EMAIL: TIA ONLY (OS REPORT + APPROVAL PROMPT)
# ══════════════════════════════════════════════════════════════════
log ""
log "─── PHASE 4: SENDING TIA'S OS REPORT ───"
log "NOTE: Team emails are HELD until Tia approves."

"$PYTHON" "$BASE_DIR/scripts/send_weekly_report.py" >> "$LOG" 2>&1 \
    || fail "Tia OS report email had issues"

log "Step 4b — Generating + sending SEO report..."
"$PYTHON" "$BASE_DIR/scripts/generate_seo_report.py" >> "$LOG" 2>&1 \
    || fail "generate_seo_report.py had issues"
"$PYTHON" "$BASE_DIR/scripts/send_seo_report.py" >> "$LOG" 2>&1 \
    || fail "send_seo_report.py had issues"

log "Step 4c — How to release team emails after Tia approves:"
log "    python scripts/send_team_emails.py --approve"
log "    OR per-person: python scripts/send_team_emails.py --role jane"


