#!/bin/bash
# refresh-social.sh — Monday 11:30am AWST refresh for the Organic Social page.
#
# Runs after the main 10am weekly-report.sh has completed. Picks up any
# Metricool PDF dropped between 10am and 11:30am, re-parses, and re-injects
# the social-data-block into docs/index.html.
#
# Cron entry:
#   30 11 * * 1 /Users/tiachasingbetter/Documents/ChasingBetter/CB_Marketing/scripts/refresh-social.sh >> /Users/tiachasingbetter/Documents/ChasingBetter/CB_Marketing/state/refresh-social.log 2>&1
#
# What it does:
#   1. Parse Metricool PDF (catches late drops between 10am and 11:30am)
#   2. Pull GBP Performance API (cheap, free — refresh per-location actions)
#   3. Re-inject window.SOCIAL_DATA block into docs/index.html
#   4. Re-inject window.SEO_EXTRAS block (kept in sync alongside)
#   5. Deploy refreshed index.html to GitHub Pages
#
# Failure modes:
#   - PDF missing      → skip parse, dashboard uses earlier parse or fallback
#   - GBP API errors   → skip, dashboard uses earlier pull
#   - inject fails     → log only, no destructive action

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PIPELINE_START=$(date +%s)

# ── Load environment ──
if [ -f "$BASE_DIR/.env" ]; then
    while IFS='=' read -r key val; do
        [[ -z "$key" || "$key" =~ ^[[:space:]]*# || ! "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] && continue
        export "$key"="$val"
    done < "$BASE_DIR/.env"
fi

PYTHON="$BASE_DIR/.venv/bin/python3.13"
LOG="$BASE_DIR/state/refresh-social.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"; }

log "================================================================"
log "  CB247 SOCIAL REFRESH — MONDAY 11:30 AM AWST"
log "================================================================"
cd "$BASE_DIR"

# ── Step 1: Parse Metricool PDF (catches PDFs dropped between 10am-11:30am) ──
log "Step 1 — Parse Metricool PDF (cb247-inbox/metricool.pdf)..."
if "$PYTHON" "$BASE_DIR/scripts/parse_metricool_pdf.py" >> "$LOG" 2>&1; then
    log "  ✅ Metricool parse complete → state/metricool-data.json"
else
    log "  ⚠️  Metricool parse skipped — PDF missing or unparseable (preserved last good data)"
fi

# ── Step 2: GBP Performance API (free, weekly cadence) ──
log "Step 2 — GBP Performance API (per-location actions)..."
if "$PYTHON" "$BASE_DIR/scripts/pull_gbp_performance.py" >> "$LOG" 2>&1; then
    log "  ✅ GBP Performance pull complete → state/gbp-performance.json"
else
    log "  ⚠️  GBP Performance skipped — first-run setup or API not enabled"
fi

# ── Step 3: Re-inject window.SOCIAL_DATA block ──
log "Step 3 — Inject SOCIAL_DATA block into docs/index.html..."
if "$PYTHON" "$BASE_DIR/scripts/inject-social-block.py" >> "$LOG" 2>&1; then
    log "  ✅ SOCIAL_DATA block injected"
else
    log "  ❌ SOCIAL_DATA injection failed — see log above"
fi

# ── Step 4: Re-inject SEO extras (kept in sync alongside) ──
log "Step 4 — Inject SEO_EXTRAS block (sibling refresh)..."
if "$PYTHON" "$BASE_DIR/scripts/inject-seo-extras.py" >> "$LOG" 2>&1; then
    log "  ✅ SEO_EXTRAS block injected"
else
    log "  ⚠️  SEO_EXTRAS injection had issues"
fi

# ── Step 5: Deploy to GitHub Pages ──
log "Step 5 — Deploy refreshed index.html..."
if git add docs/index.html >> "$LOG" 2>&1; then
    if git diff --cached --quiet; then
        log "  No changes in docs/index.html — skipping commit"
    else
        if git commit -m "social-refresh: Monday 11:30am AWST $(date +%Y-%m-%d)" >> "$LOG" 2>&1; then
            if git push >> "$LOG" 2>&1; then
                log "  ✅ Deployed → https://cb247agent.github.io/cb_claude/"
            else
                log "  ❌ git push failed — committed locally but not pushed"
            fi
        else
            log "  ❌ git commit failed"
        fi
    fi
else
    log "  ❌ git add failed"
fi

PIPELINE_END=$(date +%s)
DURATION=$((PIPELINE_END - PIPELINE_START))

log ""
log "================================================================"
log "  SOCIAL REFRESH COMPLETE — ${DURATION}s"
log "================================================================"
