#!/bin/bash
# weekly-seo.sh — Full weekly SEO data refresh + comprehensive report email.
# Runs every Monday 11:00 AM Perth Time (AWST = UTC+8) via cron.
# Cron: 0 11 * * 1  (local time)
#
# To install cron manually:
#   crontab -e
#   0 11 * * 1 /Users/tiachasingbetter/Documents/ChasingBetter/CB_Marketing/scripts/weekly-seo.sh >> /Users/tiachasingbetter/Documents/ChasingBetter/CB_Marketing/state/weekly-seo.log 2>&1
#
# Perth Time (AWST = UTC+8): Monday 11am = 03:00 UTC

set -e
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PYTHON="$BASE_DIR/.venv/bin/python3.13"
LOG="$BASE_DIR/state/weekly-seo.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"; }
cd "$BASE_DIR"
log "=== CB247 Weekly SEO Run Started ==="

# 1. Pull GA4 + GSC + Google Ads
log "Step 1/5 — Pulling GA4 + GSC + Google Ads..."
"$VENV_PYTHON" "$BASE_DIR/scripts/pull_all.py" >> "$LOG" 2>&1 || log "WARNING: pull_all.py had issues"

# 2. Privacy-compliant site crawl (replaces Screaming Frog)
# run_site_crawl.py honours robots.txt, applies PII redaction, and enforces SSL.
# Produces state/screaming-frog-data.json in the same format all SEO skills expect.
# Use --competitors to also benchmark Revo + Anytime Fitness pages.
log "Step 2/5 — Running site crawler (run_site_crawl.py)..."
"$VENV_PYTHON" "$BASE_DIR/scripts/run_site_crawl.py" --competitors >> "$LOG" 2>&1 || log "WARNING: site crawl had issues (check crawl-logs/)"

# 3. Ahrefs backlink + keyword data
log "Step 3/5 — Pulling Ahrefs data..."
"$VENV_PYTHON" "$BASE_DIR/scripts/pull_ahrefs.py" >> "$LOG" 2>&1 || log "WARNING: Ahrefs API not available (skipping)"

# 4. Apify content + competitor analysis
log "Step 4/5 — Running Apify content analysis..."
"$VENV_PYTHON" "$BASE_DIR/scripts/pull_apify.py" >> "$LOG" 2>&1 || log "WARNING: Apify not available (skipping)"

# 5. Generate comprehensive report + send email with all attachments
log "Step 5/5 — Generating report and sending email..."
"$VENV_PYTHON" "$BASE_DIR/scripts/generate_seo_report.py" >> "$LOG" 2>&1
"$VENV_PYTHON" "$BASE_DIR/scripts/send_seo_report.py" >> "$LOG" 2>&1 || log "WARNING: email send had issues"

log "=== Weekly SEO Run Complete ==="