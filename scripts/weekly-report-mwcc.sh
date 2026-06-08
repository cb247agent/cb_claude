#!/bin/bash
# weekly-report-mwcc.sh — My World Childcare Marketing OS pipeline
#
# Runs every Monday 1:00 PM Perth Time (AWST = UTC+8) via cron.
# Cron entry (Monday 5am UTC = 1pm AWST):
#   0 5 * * 1 /Users/tiachasingbetter/Documents/ChasingBetter/CB_Marketing/scripts/weekly-report-mwcc.sh >> /Users/tiachasingbetter/Documents/ChasingBetter/CB_Marketing/logs/mwcc-weekly-report.log 2>&1
#
# INBOX REQUIREMENT (before this runs):
#   Drop both files to mwcc-inbox/ by 12:55 PM Monday:
#     - MYWORLD_REPORT.xlsx  (OWNA → Reports → Weekly Wage Monitor)
#     - utilisation.xlsx     (OWNA → Reports → Utilisation)
#
# Pipeline:
#   Step 1  GA4 pull           state/mwcc-ga4.json
#   Step 2  Google Ads pull    state/mwcc-ads.json + state/mwcc-ads-history.json
#   Step 3  Meta pull          state/mwcc-meta.json + state/mwcc-meta-history.json
#   Step 4  Ops parse (OWNA)   state/mwcc-ops.json (graceful skip if inbox is empty)
#   Step 5  Bake report        outputs/reports/mwcc/mwcc-marketing-YYYY-MM-DD.html
#                               + docs/mwcc-report.html (GitHub Pages, fixed URL)
#   Step 6  Deploy             git commit + push docs/mwcc-report.html

# No set -e — step failures are tracked in FAILED_STEPS[], not script-killing.
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PIPELINE_START=$(date +%s)
FAILED_STEPS=()
OPS_SKIPPED=false

# ── Load environment (API keys, credentials) — safe parser skips bad lines ──
if [ -f "$BASE_DIR/.env" ]; then
    while IFS='=' read -r key val; do
        [[ -z "$key" || "$key" =~ ^[[:space:]]*# || ! "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] && continue
        export "$key"="$val"
    done < "$BASE_DIR/.env"
fi

PYTHON="$BASE_DIR/.venv/bin/python3.13"
LOG="$BASE_DIR/logs/mwcc-weekly-report.log"
DATE=$(date '+%Y-%m-%d')

# ── Ensure directories exist ──
mkdir -p "$BASE_DIR/logs" \
         "$BASE_DIR/outputs/reports/mwcc" \
         "$BASE_DIR/state"

log()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"; }
fail() { log "ERROR: $1"; }

# ─────────────────────────────────────────────────────────────────
log "================================================================"
log "  MWCC MARKETING OS — MONDAY RUN STARTED"
log "  My World Childcare · 5 centres · Perth WA"
log "================================================================"
cd "$BASE_DIR"


# ─────────────────────────────────────────────────────────────────
# STEP 1 — GA4 PULL
# ─────────────────────────────────────────────────────────────────
log ""
log "─── STEP 1: GA4 (myworldcc.com.au) ───"
if "$PYTHON" "$BASE_DIR/scripts/pull_mwcc_ga4.py" >> "$LOG" 2>&1; then
    log "  ✅ GA4 pull complete → state/mwcc-ga4.json"
else
    FAILED_STEPS+=("ga4")
    log "  ❌ GA4 pull failed — report will show placeholder"
fi


# ─────────────────────────────────────────────────────────────────
# STEP 2 — GOOGLE ADS PULL
# ─────────────────────────────────────────────────────────────────
log ""
log "─── STEP 2: Google Ads (account 917-218-6113) ───"
if GRPC_DNS_RESOLVER=native "$PYTHON" "$BASE_DIR/scripts/pull_mwcc_ads.py" >> "$LOG" 2>&1; then
    log "  ✅ Google Ads pull complete → state/mwcc-ads.json"
else
    FAILED_STEPS+=("google-ads")
    log "  ❌ Google Ads pull failed — report will show placeholder"
fi


# ─────────────────────────────────────────────────────────────────
# STEP 3 — META PULL
# ─────────────────────────────────────────────────────────────────
log ""
log "─── STEP 3: Meta (account act_2835637326727066) ───"
if "$PYTHON" "$BASE_DIR/scripts/pull_mwcc_meta.py" >> "$LOG" 2>&1; then
    log "  ✅ Meta pull complete → state/mwcc-meta.json"
else
    FAILED_STEPS+=("meta")
    log "  ❌ Meta pull failed — report will show placeholder"
fi


# ─────────────────────────────────────────────────────────────────
# STEP 4 — OWNA OPS PARSE (graceful skip if inbox is empty)
# ─────────────────────────────────────────────────────────────────
log ""
log "─── STEP 4: OWNA Ops Parse ───"

INBOX="$BASE_DIR/mwcc-inbox"
WAGE_FILE=$(ls "$INBOX/MYWORLD_REPORT.xlsx" "$INBOX"/MYWORLD_REPORT*.xlsx 2>/dev/null | head -1)
UTIL_FILE=$(ls "$INBOX/utilisation.xlsx" "$INBOX"/utilisation*.xlsx 2>/dev/null | head -1)

if [ -z "$WAGE_FILE" ] && [ -z "$UTIL_FILE" ]; then
    OPS_SKIPPED=true
    log "  ⚠️  No OWNA files in mwcc-inbox/ — ops data skipped"
    log "     Drop MYWORLD_REPORT.xlsx and utilisation.xlsx before 1pm Monday"
elif [ -z "$WAGE_FILE" ]; then
    log "  ⚠️  Missing MYWORLD_REPORT.xlsx — parsing with utilisation only"
    if "$PYTHON" "$BASE_DIR/scripts/parse_mwcc_ops.py" >> "$LOG" 2>&1; then
        log "  ✅ Ops parse complete (partial) → state/mwcc-ops.json"
    else
        FAILED_STEPS+=("ops")
        log "  ❌ Ops parse failed"
    fi
elif [ -z "$UTIL_FILE" ]; then
    log "  ⚠️  Missing utilisation.xlsx — parsing with MYWORLD_REPORT only"
    if "$PYTHON" "$BASE_DIR/scripts/parse_mwcc_ops.py" >> "$LOG" 2>&1; then
        log "  ✅ Ops parse complete (partial) → state/mwcc-ops.json"
    else
        FAILED_STEPS+=("ops")
        log "  ❌ Ops parse failed"
    fi
else
    log "  Found: $(basename "$WAGE_FILE") + $(basename "$UTIL_FILE")"
    if "$PYTHON" "$BASE_DIR/scripts/parse_mwcc_ops.py" >> "$LOG" 2>&1; then
        log "  ✅ Ops parse complete → state/mwcc-ops.json"
    else
        FAILED_STEPS+=("ops")
        log "  ❌ Ops parse failed — report will show placeholder"
    fi
fi


# ─────────────────────────────────────────────────────────────────
# STEP 4.1 — ROTATE OPS HISTORY (enables WoW deltas in dashboard)
# Snapshots the freshly-parsed mwcc-ops.json into mwcc-ops-history.json.
# Idempotent — re-running same week is safe (overwrites that week's entry).
# Graceful: if mwcc-ops.json wasn't written this run, the script just no-ops.
# ─────────────────────────────────────────────────────────────────
log ""
log "─── STEP 4.1: Rotate ops history ───"
if "$PYTHON" "$BASE_DIR/scripts/rotate_mwcc_ops_history.py" >> "$LOG" 2>&1; then
    log "  ✅ Ops history rotated → state/mwcc-ops-history.json"
else
    FAILED_STEPS+=("ops-rotate")
    log "  ⚠️  Ops history rotation failed (non-fatal)"
fi


# ─────────────────────────────────────────────────────────────────
# STEP 4.5 — GSC PULL + AHREFS PULL (SEO data sources)
# ─────────────────────────────────────────────────────────────────
log ""
log "─── STEP 4.5a: MWCC GSC Pull ───"
"$PYTHON" "$BASE_DIR/scripts/pull_mwcc_gsc.py" >> "$LOG" 2>&1 \
    && log "  ✅ MWCC GSC pull complete → state/mwcc-gsc-data.json" \
    || { FAILED_STEPS+=("mwcc-gsc"); log "  ⚠️  MWCC GSC pull failed — check $LOG"; }

log "─── STEP 4.5b: MWCC Ahrefs (CSV fallback first, then API) ───"
# Prefer manual CSV exports in mwcc-inbox/ahrefs/ — used while AHREFS_API_KEY
# is rotating / locked out (Jun 2026). Tia drops 7 CSVs each Monday from
# Ahrefs UI; the parser writes state/mwcc-ahrefs.json in the dashboard shape.
# Falls back to the API script if no CSVs are present.
AHREFS_CSV_COUNT=$(ls "$BASE_DIR/mwcc-inbox/ahrefs"/*.csv 2>/dev/null | wc -l | tr -d ' ')
if [ "$AHREFS_CSV_COUNT" -gt 0 ]; then
    log "  Found $AHREFS_CSV_COUNT CSV(s) in mwcc-inbox/ahrefs/ — using manual parser"
    if "$PYTHON" "$BASE_DIR/scripts/parse_mwcc_ahrefs_csvs.py" >> "$LOG" 2>&1; then
        log "  ✅ MWCC Ahrefs parsed (manual) → state/mwcc-ahrefs.json"
    else
        FAILED_STEPS+=("mwcc-ahrefs-csv")
        log "  ⚠️  Ahrefs CSV parse failed — check $LOG"
    fi
else
    log "  No CSVs in mwcc-inbox/ahrefs/ — falling back to API pull"
    "$PYTHON" "$BASE_DIR/scripts/pull_mwcc_ahrefs.py" >> "$LOG" 2>&1 \
        && log "  ✅ MWCC Ahrefs pull complete → state/mwcc-ahrefs-data.json" \
        || { FAILED_STEPS+=("mwcc-ahrefs"); log "  ⚠️  MWCC Ahrefs pull failed (units exhausted?) — check $LOG"; }
fi

# ─────────────────────────────────────────────────────────────────
# STEP 4.6 — MWCC Metricool PDF parse (organic social)
# Jordan drops mwcc-inbox/metricool.pdf each Monday. Parser extracts
# FB + IG + GBP per-centre metrics. Graceful skip if no PDF.
# ─────────────────────────────────────────────────────────────────
log ""
log "─── STEP 4.6: MWCC Metricool PDF Parse ───"
if "$PYTHON" "$BASE_DIR/scripts/parse_mwcc_metricool_pdf.py" >> "$LOG" 2>&1; then
    log "  ✅ MWCC Metricool parse complete → state/mwcc-social.json"
else
    FAILED_STEPS+=("mwcc-metricool")
    log "  ⚠️  MWCC Metricool parse failed — check $LOG"
fi


# ─────────────────────────────────────────────────────────────────
# STEP 4.6b — MWCC GBP Performance API pull (all 5 centres)
# Pulls website clicks, calls, directions, impressions per location.
# Metricool only tracks 1 GBP per workspace (Seville Grove currently),
# so this API pull covers all 5 — Armadale, Midvale, Rockingham,
# Seville Grove, Waikiki.
# Currently returns 429 (quota=0) — Tia to submit quota increase in GCP.
# Script auto-fires the moment quota lands; until then, it writes an
# "available:false" placeholder and the dashboard shows Metricool data.
# ─────────────────────────────────────────────────────────────────
log ""
log "─── STEP 4.6b: MWCC GBP Performance API Pull (5 centres) ───"
if "$PYTHON" "$BASE_DIR/scripts/pull_mwcc_gbp_performance.py" >> "$LOG" 2>&1; then
    log "  ✅ MWCC GBP performance pull complete → state/mwcc-gbp-performance.json"
else
    FAILED_STEPS+=("mwcc-gbp-perf")
    log "  ⚠️  MWCC GBP performance pull failed (quota=0?) — check $LOG"
fi

# ─────────────────────────────────────────────────────────────────
# STEP 4.7 — WORK QUEUE EMITTERS
# ─────────────────────────────────────────────────────────────────
log ""
log "─── STEP 4.7a: MWCC Google Ads Emitter ───"
"$PYTHON" "$BASE_DIR/scripts/work_queue/mwcc_google_ads_emitter.py" >> "$LOG" 2>&1 \
    && log "  ✅ Google Ads actions emitted" \
    || { FAILED_STEPS+=("mwcc-gads-emit"); log "  ⚠️  Google Ads emitter failed"; }

log "─── STEP 4.7b: MWCC Meta Emitter ───"
"$PYTHON" "$BASE_DIR/scripts/work_queue/mwcc_meta_emitter.py" >> "$LOG" 2>&1 \
    && log "  ✅ Meta actions emitted" \
    || { FAILED_STEPS+=("mwcc-meta-emit"); log "  ⚠️  Meta emitter failed"; }

log "─── STEP 4.7c: MWCC SEO Emitter ───"
"$PYTHON" "$BASE_DIR/scripts/work_queue/mwcc_seo_emitter.py" >> "$LOG" 2>&1 \
    && log "  ✅ SEO actions emitted" \
    || { FAILED_STEPS+=("mwcc-seo-emit"); log "  ⚠️  SEO emitter failed"; }

log "─── STEP 4.7d: MWCC Enrolment Emitter ───"
"$PYTHON" "$BASE_DIR/scripts/work_queue/mwcc_enrolment_emitter.py" >> "$LOG" 2>&1 \
    && log "  ✅ Enrolment actions emitted" \
    || { FAILED_STEPS+=("mwcc-enrol-emit"); log "  ⚠️  Enrolment emitter failed"; }

log "─── STEP 4.7d2: Extract Agent Action Proposals (Agent Action Contract) ───"
# Layer 3 (Agents): when MWCC agents produce markdown output ending with a
# ```json proposed_actions block, extract them as WorkQueueAction objects
# and merge into mwcc-work-queue.json. See agents/AGENT_ACTION_CONTRACT.md.
# Graceful no-op if no agents have produced output yet (early days).
"$PYTHON" "$BASE_DIR/scripts/extract_agent_actions.py" --business mwcc >> "$LOG" 2>&1 \
    && log "  ✅ MWCC agent action proposals extracted" \
    || { FAILED_STEPS+=("mwcc-agent-extract"); log "  ⚠️  Agent extraction failed (non-fatal)"; }

log "─── STEP 4.7e0: Compute Enrolment Funnel ───"
# Stitches GA4 + OWNA into a 5-stage funnel (sessions → conversions →
# enquiries → enrolments — exits). Writes state/mwcc-funnel.json. Used
# by the future dashboard widget + email digest "Funnel Health" block.
"$PYTHON" "$BASE_DIR/scripts/compute_mwcc_funnel.py" >> "$LOG" 2>&1 \
    && log "  ✅ Funnel computed → state/mwcc-funnel.json" \
    || { FAILED_STEPS+=("mwcc-funnel"); log "  ⚠️  Funnel compute failed (non-fatal)"; }

log "─── STEP 4.7e: Sync Work Queue → Supabase ───"
"$PYTHON" "$BASE_DIR/scripts/work_queue/mwcc_sync_to_supabase.py" >> "$LOG" 2>&1 \
    && log "  ✅ MWCC Work Queue synced to Supabase" \
    || { FAILED_STEPS+=("mwcc-sync"); log "  ⚠️  Supabase sync failed"; }

log "─── STEP 4.7f: Generate per-action briefs (docs/briefs/mwcc-*.html) ───"
"$PYTHON" "$BASE_DIR/scripts/generate_mwcc_briefs.py" >> "$LOG" 2>&1 \
    && log "  ✅ MWCC per-action briefs generated" \
    || { FAILED_STEPS+=("mwcc-briefs"); log "  ⚠️  Brief generation failed (non-fatal)"; }

# ─────────────────────────────────────────────────────────────────
# STEP 5 — BAKE REPORT
# ─────────────────────────────────────────────────────────────────
log ""
log "─── STEP 5: Bake Report ───"
if "$PYTHON" "$BASE_DIR/scripts/bake-mwcc-report.py" >> "$LOG" 2>&1; then
    REPORT_FILE="$BASE_DIR/outputs/reports/mwcc/mwcc-marketing-$DATE.html"
    REPORT_SIZE=$(du -sh "$BASE_DIR/docs/mwcc-report.html" 2>/dev/null | cut -f1)
    log "  ✅ Report baked:"
    log "     Archive : outputs/reports/mwcc/mwcc-marketing-$DATE.html"
    log "     Live    : docs/mwcc-report.html ($REPORT_SIZE)"
else
    FAILED_STEPS+=("baker")
    log "  ❌ Baker failed — GitHub Pages not updated"
fi


# ─────────────────────────────────────────────────────────────────
# STEP 6 — DEPLOY TO GITHUB PAGES
# ─────────────────────────────────────────────────────────────────
log ""
log "─── STEP 6: Deploy to GitHub Pages ───"

# Only deploy if baker succeeded
if [[ " ${FAILED_STEPS[*]} " != *" baker "* ]]; then
    cd "$BASE_DIR"
    git add docs/mwcc-report.html >> "$LOG" 2>&1

    if git diff --cached --quiet; then
        log "  No changes in docs/mwcc-report.html — skipping commit"
    else
        if git commit -m "mwcc-report: weekly update $DATE" >> "$LOG" 2>&1; then
            if git push >> "$LOG" 2>&1; then
                log "  ✅ Deployed → https://cb247agent.github.io/cb_claude/"
                log "     Live in ~1 minute. Tab: My World Childcare → Weekly Report"
            else
                FAILED_STEPS+=("deploy-push")
                log "  ❌ git push failed — committed locally but not pushed"
                log "     Run manually: git push"
            fi
        else
            FAILED_STEPS+=("deploy-commit")
            log "  ❌ git commit failed"
        fi
    fi
else
    log "  ⏭  Skipped (baker failed)"
fi


# ─────────────────────────────────────────────────────────────────
# STEP 6 — EMAIL DIGEST
# Sends Monday-morning summary to Tia (+ optional CC list).
# Uses SMTP creds from .env (same as CB247 weekly report email).
# Set MWCC_REPORT_RECIPIENT in .env to route to a different inbox than CB247.
# ─────────────────────────────────────────────────────────────────
log ""
log "─── STEP 5.5: Bake Management Report (private, integrated) ───"
# Generates outputs/mwcc/management-report-{date}.html — confidential
# weekly view for Robert (CEO), Denver, Kelley, Jordan, Dana that
# integrates marketing performance with operational outcomes.
"$PYTHON" "$BASE_DIR/scripts/bake_mwcc_management_report.py" >> "$LOG" 2>&1 \
    && log "  ✅ Management report baked → outputs/mwcc/management-report-$DATE.html" \
    || { FAILED_STEPS+=("mwcc-mgmt-bake"); log "  ⚠️  Management report bake failed"; }

log ""
log "─── STEP 6: Email Digest ───"
if "$PYTHON" "$BASE_DIR/scripts/send_mwcc_weekly_report.py" >> "$LOG" 2>&1; then
    log "  ✅ MWCC weekly digest emailed (marketing, to Tia)"
else
    FAILED_STEPS+=("mwcc-email")
    log "  ⚠️  Email send failed (non-fatal — check SMTP env + log)"
fi

log ""
log "─── STEP 6.5: Email Management Report (private, integrated) ───"
# Sends the management report HTML to MWCC_MANAGEMENT_RECIPIENTS (.env).
# Falls back to WEEKLY_REPORT_RECIPIENT (Tia only) when not set.
"$PYTHON" "$BASE_DIR/scripts/send_mwcc_management_report.py" >> "$LOG" 2>&1 \
    && log "  ✅ Management report emailed" \
    || { FAILED_STEPS+=("mwcc-mgmt-email"); log "  ⚠️  Management email failed (non-fatal)"; }


# ─────────────────────────────────────────────────────────────────
# RUN SUMMARY
# ─────────────────────────────────────────────────────────────────
PIPELINE_END=$(date +%s)
PIPELINE_DURATION=$((PIPELINE_END - PIPELINE_START))
RUN_STATUS=$( [ ${#FAILED_STEPS[@]} -eq 0 ] && echo "success" || echo "partial" )
FAILED_CSV="$(IFS=,; echo "${FAILED_STEPS[*]}")"

log ""
log "================================================================"
log "  MWCC MARKETING OS — RUN COMPLETE"
log "  Status   : $RUN_STATUS | Duration: ${PIPELINE_DURATION}s"
log "  Date     : $DATE"
log "================================================================"

if [ ${#FAILED_STEPS[@]} -eq 0 ]; then
    log "  ✅ All steps complete (5/5)"
    if [ "$OPS_SKIPPED" = true ]; then
        log "  ⚠️  Ops skipped (no OWNA files in inbox)"
    fi
else
    STEP_COUNT=$(( 5 - ${#FAILED_STEPS[@]} ))
    log "  ⚠️  Steps complete: ${STEP_COUNT}/5 — failed: $FAILED_CSV"
fi

log ""
log "  Outputs:"
log "    Archive  : outputs/reports/mwcc/mwcc-marketing-$DATE.html"
log "    Live     : https://cb247agent.github.io/cb_claude/ → My World Childcare"
log "    State    : state/mwcc-ga4.json · mwcc-ads.json · mwcc-meta.json · mwcc-ops.json"
log ""
log "  Inbox status:"
[ -n "$WAGE_FILE"  ] && log "    ✅ $(basename "$WAGE_FILE")" || log "    ❌ MYWORLD_REPORT.xlsx (missing)"
[ -n "$UTIL_FILE"  ] && log "    ✅ $(basename "$UTIL_FILE")"  || log "    ❌ utilisation.xlsx (missing)"
log "================================================================"
