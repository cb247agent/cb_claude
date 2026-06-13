#!/bin/bash
# phase1c_content_drafter.sh — Path C · weekly AI content drafter.
#
# WHY THIS EXISTS (13 Jun 2026)
#   seo-strategist proposes actions like "Build blog: X" / "Build landing
#   page: X" / "Build service page: X" with owner=AI Content Agent. Until
#   today, no agent actually existed to do the writing — actions sat on
#   the team's lists and were ignored.
#
#   This phase runs every Monday (after phase1_data.sh completes) and:
#     1. Reads state/work-queue.json
#     2. Finds AI-owned SEO actions (owner=="AI") with prefix "Build "
#     3. For each, checks whether the draft already exists in outputs/
#        — idempotent, skips if so
#     4. Fires content-writer for each missing draft
#     5. Runs extract_content_writer_output.py to emit "Review + publish"
#        follow-up actions assigned to John (SEO QC) + Angela (brand QC)
#     6. Renders the .md files to docs/{blogs,landing-pages,service-pages}/*.html
#     7. Syncs the new actions to Supabase
#
# CADENCE
#   Cron: Monday 12:00 AWST (after weekly-report.sh at 10am, after promo-
#   launch at 09:00 Tue would be too late — content needs to be ready for
#   review same week as proposal). Actually wait — Tuesday morning is
#   fine because the team reviews on Tuesday/Wednesday anyway.
#
#   Tue 09:30 AWST — runs after phase1b_promo_launch.sh (09:00).
#   Add to crontab when ready:
#     30 9 * * 2 /Users/tiachasingbetter/Documents/ChasingBetter/CB_Marketing/scripts/phases/phase1c_content_drafter.sh
#
# COST
#   ~$0.50-1 per blog · $1-2 per landing or service page.
#   Typical month: 3-5 drafts → ~$3-5/month.

set -uo pipefail

# Source the common helpers
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

# Phase-specific log file
LOG="$BASE_DIR/logs/phase1c-content-drafter-$(date +%Y%m%d-%H%M).log"
log "=== Phase 1c · AI Content Drafter · started ${DATE} $(date +%H:%M:%S) ==="

# Ensure output directories exist
mkdir -p "$OUTPUTS/blogs" \
         "$OUTPUTS/landing-pages" \
         "$OUTPUTS/service-pages" \
         "$OUTPUTS/content-writer" \
         "$BASE_DIR/docs/blogs" \
         "$BASE_DIR/docs/landing-pages" \
         "$BASE_DIR/docs/service-pages"

# ── Discover AI-owned content actions without a draft ──
# Python helper handles work-queue read + outputs/ existence check.
# Prints one "<action_id>|<format>" per line to stdout.
DRAFT_TARGETS=$("$PYTHON" "$BASE_DIR/scripts/work_queue/find_pending_content.py" 2>>"$LOG" || true)

if [[ -z "$DRAFT_TARGETS" ]]; then
    log "No AI-owned content actions pending a draft. Exiting."
    exit 0
fi

# ── For each target, fire content-writer ──
count=0
while IFS='|' read -r ACTION_ID FORMAT; do
    [[ -z "$ACTION_ID" ]] && continue
    count=$((count + 1))
    log "  → ${ACTION_ID} (${FORMAT}) — firing content-writer..."

    OUT_PATH="$OUTPUTS/content-writer/content-writer-${ACTION_ID}-${DATE}.md"

    run_agent "content-writer" \
"You are the CB247 Content Writer. Today is $DATE.

Your job: write the FULL draft for the AI-owned SEO action with id
'$ACTION_ID' so John (SEO QC) and Angela (brand QC) can review + publish
without writing from scratch.

The action is in state/work-queue.json. Inputs.target_action_id is
'$ACTION_ID'. Detect the format from the title prefix (blog / landing
page / service page). Follow agents/content-writer.yml's Format_Rules
exactly.

Brand compliance is MANDATORY:
- \$11.95/wk anchor, no lock-in
- 1-3 differentiators relevant to the topic
- NEVER name Revo / Anytime / Snap / Ryderwear
- NEVER use 'only gym with', 'best gym', 'burns fat', 'heals', 'cures',
  'treats', 'guarantee'
- Recovery / Reformer / ChasingRX are PAID add-ons, NEVER bundled in \$11.95

Output: write the full content to the appropriate outputs/ directory using
the Write tool. Format YAML front-matter at the top (title, meta_description,
slug, primary_keyword, format, internal_links, author, generated_at).

Then output a SHORT markdown summary to stdout (the bash wrapper saves it).
Summary structure: action processed · compliance check · notes for John ·
notes for Angela.

CRITICAL: Do NOT emit a proposed_actions JSON block. The follow-up
'Review + publish' action is emitted by the extractor script based on
what file you wrote." \
        "$OUT_PATH" \
        "Read(state/work-queue.json),Read(state/gsc-data.json),Read(state/ahrefs-data.json),Read(state/screaming-frog-data.json),Read(context/brand-voice.md),Read(context/seo-priorities-cb247.md),Read(context/icp-profiles.md),Read(/Users/tiachasingbetter/Documents/ChasingBetter/CB_Brain/wiki/CB247-Knowledge-Base.md),Read(/Users/tiachasingbetter/Documents/ChasingBetter/CB_Brain/wiki/SEO-Learnings.md),Write(outputs/blogs/**),Write(outputs/landing-pages/**),Write(outputs/service-pages/**)" \
        "$MODEL_OPUS"

done <<< "$DRAFT_TARGETS"

# ── Emit Review + publish follow-up actions ──
log "Step 2 — Extract follow-up Review + publish actions from new drafts..."
"$PYTHON" "$BASE_DIR/scripts/work_queue/extract_content_writer_output.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  Content writer extraction had issues — check $LOG"

# ── Step 2b — Path D · SEO Refresh Drafter (13 Jun 2026) ───────────────────
# Fires seo-refresh-drafter for every SEO refresh action (edit-an-existing-
# page actions like "Improve organic content for X"). Output → outputs/
# seo-refreshes/{slug}.md → rendered to docs/seo-refreshes/{slug}.html →
# surfaced in View Brief as "View AI Draft → ". John pastes into Webflow.
mkdir -p "$OUTPUTS/seo-refreshes" "$BASE_DIR/docs/seo-refreshes"
log "Step 2b — Path D · SEO Refresh Drafter..."

REFRESH_TARGETS=$("$PYTHON" "$BASE_DIR/scripts/work_queue/find_pending_seo_refresh.py" 2>>"$LOG" || true)

if [[ -z "$REFRESH_TARGETS" ]]; then
    log "  No SEO refresh actions pending a draft. Skipping seo-refresh-drafter."
else
    refresh_count=0
    while IFS='|' read -r ACTION_ID SLUG; do
        [[ -z "$ACTION_ID" ]] && continue
        refresh_count=$((refresh_count + 1))
        log "  → ${ACTION_ID} (slug=${SLUG}) — firing seo-refresh-drafter..."

        OUT_PATH="$OUTPUTS/seo-refreshes/seo-refresh-drafter-${ACTION_ID}-${DATE}.md"

        run_agent "seo-refresh-drafter" \
"You are the CB247 SEO Refresh Drafter. Today is $DATE.

Your job: draft the SEO refresh content (new H1, meta title, meta description,
5 FAQs, internal link table) for the action with id '$ACTION_ID' so John
(SEO / Web) can paste everything directly into Webflow — NO writing.

The action is in state/work-queue.json. Inputs.target_action_id is
'$ACTION_ID'. Follow agents/seo-refresh-drafter.yml's Workflow exactly.

Output file path: outputs/seo-refreshes/${SLUG}.md

Brand compliance is MANDATORY:
- \$11.95/wk anchor, no lock-in
- 1-3 differentiators relevant to the page
- NEVER name Revo / Anytime / Snap / Ryderwear
- NEVER use 'only gym with', 'best gym', 'burns fat', 'heals', 'cures',
  'detox', 'guaranteed'
- Recovery / Reformer / ChasingRX are PAID add-ons, NEVER bundled in \$11.95

CRITICAL: Do NOT emit a proposed_actions JSON block. The original SEO action
stays in the queue — your draft attaches via View Brief, not by emitting a
new follow-up action.

Then output a SHORT markdown summary to stdout: action ID processed,
compliance check, notes for John, notes for Angela." \
            "$OUT_PATH" \
            "Read(state/work-queue.json),Read(state/gsc-data.json),Read(state/ahrefs-data.json),Read(state/screaming-frog-data.json),Read(context/brand-voice.md),Read(context/seo-priorities-cb247.md),Read(context/icp-profiles.md),Read(context/team-workflow-mapping.md),Read(/Users/tiachasingbetter/Documents/ChasingBetter/CB_Brain/wiki/CB247-Knowledge-Base.md),Read(/Users/tiachasingbetter/Documents/ChasingBetter/CB_Brain/wiki/SEO-Learnings.md),Write(outputs/seo-refreshes/**)" \
            "$MODEL_SONNET"

    done <<< "$REFRESH_TARGETS"
    log "  Processed $refresh_count SEO refresh action(s)."
fi

# ── Render markdown → HTML so team can preview ──
log "Step 3 — Render content .md → docs/{blogs,landing-pages,service-pages,seo-refreshes}/*.html..."
"$PYTHON" "$BASE_DIR/scripts/render_content_html.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  Content HTML rendering had issues — check $LOG"

# ── Sync new follow-up actions to Supabase ──
log "Step 4 — Sync Work Queue → Supabase..."
"$PYTHON" "$BASE_DIR/scripts/work_queue/sync_to_supabase.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  Work Queue sync had issues — check $LOG"

log "=== Phase 1c complete · processed ${count} content action(s) · $(date +%H:%M:%S) ==="
