#!/bin/bash
# phase3_reports.sh — Generate HTML performance reports + dashboards.
#
# Reads outputs/research/* + state/* and produces the McKinsey-style
# weekly HTML reports under outputs/reports/. Also deploys the dashboard
# inject blocks if any data file changed in Phase 1.
#
# Sourced + run from scripts/weekly-report.sh.

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

# ══════════════════════════════════════════════════════════════════
# PHASE 3 — GENERATE OUTPUTS
# ══════════════════════════════════════════════════════════════════
log ""
log "─── PHASE 3: GENERATING OUTPUTS ───"

log "Step 3pre — Auto-importing pending meeting minutes..."
LATEST_MINUTES=$(ls -t "$BASE_DIR/state/meeting-minutes-"*.json 2>/dev/null | head -1)
if [ -n "$LATEST_MINUTES" ]; then
    MINUTES_DATE=$(basename "$LATEST_MINUTES" | sed 's/meeting-minutes-//;s/.json//')
    log "  Found meeting minutes: $MINUTES_DATE"
    "$PYTHON" "$BASE_DIR/scripts/import-meeting-minutes.py" "$LATEST_MINUTES" >> "$LOG" 2>&1 \
        && log "  ✅ Meeting minutes imported" \
        || log "  ⚠️  Meeting minutes import had issues"
else
    log "  No pending meeting minutes found — skipping"
fi

log "Step 3a — Generating HTML weekly report..."
"$PYTHON" "$BASE_DIR/scripts/bake-weekly-report.py" >> "$LOG" 2>&1 \
    || fail "bake-weekly-report.py had issues"

# ── Step 3b: DISABLED until baker consolidation ──
# bake-public-dashboard.py regenerates docs/index.html from scratch and does
# not know about the multi-business render functions (MWCC, Karribank,
# Sparrows) or the recent SEO/Google Ads/Organic Social page rebuilds.
# Running it wipes all of that.
#
# Until baker consolidation (a separate session of work), the data pulls
# still run (Phase 1), agents still produce briefs (Phase 2), and the
# 11:30am refresh-social.sh cron re-injects fresh data blocks. The HTML
# structure stays as currently deployed.
#
# To re-enable after consolidation:
#   uncomment the two lines below + remove this block.
log "Step 3b — SKIPPED — bake-public-dashboard.py disabled (baker consolidation pending)"
# "$PYTHON" "$BASE_DIR/scripts/bake-public-dashboard.py" >> "$LOG" 2>&1 \
#     || fail "bake-public-dashboard.py had issues"

# ── Step 3b' (replacement): Refresh the inline injection blocks ──
# Re-inject SEO_EXTRAS + SOCIAL_DATA + META_ADS_LIVE so the dashboard picks up
# fresh Metricool/GBP/Apify/Meta data without rebuilding the whole HTML.
log "Step 3b' — Re-injecting SEO_EXTRAS + SOCIAL_DATA + META_ADS_LIVE blocks (replacement for full bake)..."
"$PYTHON" "$BASE_DIR/scripts/inject-seo-extras.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  SEO extras injection had issues"
"$PYTHON" "$BASE_DIR/scripts/inject-social-block.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  Social block injection had issues"
"$PYTHON" "$BASE_DIR/scripts/inject-meta-ads.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  Meta ads injection had issues"
"$PYTHON" "$BASE_DIR/scripts/inject-membership-data.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  Membership block injection had issues"

log "Step 3c — Deploying dashboard to GitHub Pages..."
bash "$BASE_DIR/scripts/deploy-dashboard.sh" >> "$LOG" 2>&1 \
    || fail "deploy-dashboard.sh had issues"

log "Phase 3 complete."
