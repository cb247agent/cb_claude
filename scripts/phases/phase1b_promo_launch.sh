#!/bin/bash
# phase1b_promo_launch.sh — event-driven campaign-launch-strategist runner.
#
# WHY THIS EXISTS (13 Jun 2026 — Path B)
#   When Angela marks a promo concept "Approved" in the dashboard, the
#   campaign-launch-strategist needs to fire ONCE for that concept to write
#   the full Meta + Google media plan to outputs/media-plans/.
#
#   This runs DAILY (4am AWST via launchd) and:
#     1. Reads state/promo-pipeline.json to find concepts with enriched fields
#     2. Reads Supabase promo_pipeline_state for newly-Approved concepts
#     3. For each concept where stage IN ('Approved','Asset Shoot Scheduled')
#        AND no media plan exists yet at outputs/media-plans/media-plan-{id}-*.md,
#        fire campaign-launch-strategist
#     4. Extract the proposed Launch action from each plan into work-queue.json
#     5. Sync to Supabase
#
# Idempotency: the agent's prompt mandates skip-if-media-plan-exists, so
# re-running this script is safe — only NEW Approved concepts trigger work.

set -uo pipefail

# Source the common helpers (DATE, run_agent, log, MODEL_OPUS, etc.)
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

# This phase has its own log file so it doesn't clobber the weekly run log.
LOG="$BASE_DIR/logs/phase1b-promo-launch-$(date +%Y%m%d-%H%M).log"
log "=== Phase 1b · Promo Launch Strategist · started ${DATE} $(date +%H:%M:%S) ==="

# Ensure output directories exist
mkdir -p "$OUTPUTS/media-plans" "$OUTPUTS/campaign-launch-strategist" "$BASE_DIR/docs/media-plans"

# ── Discover newly-Approved concepts without a media plan ──
# Lightweight Python helper rather than jq — handles Supabase fetch +
# state/promo-pipeline.json + outputs/media-plans/ existence check in one
# pass. Prints concept IDs one per line to stdout.
APPROVED_IDS=$("$PYTHON" "$BASE_DIR/scripts/work_queue/find_launch_ready_promos.py" 2>>"$LOG" || true)

if [[ -z "$APPROVED_IDS" ]]; then
    log "No Approved concepts pending a media plan. Exiting."
    exit 0
fi

# ── For each, fire the strategist ──
count=0
while IFS= read -r CONCEPT_ID; do
    [[ -z "$CONCEPT_ID" ]] && continue
    count=$((count + 1))
    log "  → Concept ${CONCEPT_ID} — firing campaign-launch-strategist..."

    OUT_PATH="$OUTPUTS/campaign-launch-strategist/campaign-launch-${CONCEPT_ID}-${DATE}.md"

    run_agent "campaign-launch-strategist" \
"You are the CB247 Campaign Launch Strategist. Today is $DATE.

Your job is to write a FULL media plan for promo concept '$CONCEPT_ID' that
Joanne (Meta) and Tia (Google) can copy-paste into Ads Manager / Google Ads
without making any decisions. The concept's enriched fields (audience_seed,
conversion_event, budget_envelope, historical_cpa_baseline, launch_window,
kill_criteria, creative_hints) are already populated by promo-concept-
strategist — read them and translate them into a Meta campaign + Google
campaign + day-7 kill criteria.

Read these files:
- state/promo-pipeline.json    (CONCENTRATE on the concept where id == '$CONCEPT_ID')
- state/membership-data.json   (audience seed counts)
- state/ga4-data.json          (funnel — which channel converts better for this audience)
- state/meta-ads-data.json     (current Meta CPM + frequency baselines)
- state/google-ads-data.json   (current Google CPC + conversion-rate)
- state/meta-ads-history.json  (prior similar campaigns CPA — if file exists)
- state/work-queue.json        (avoid duplicate launch actions)
- context/utm-convention.md    (UTM naming — mandatory)
- context/brand-voice.md       (voice constraints)
- CB_Brain/wiki/Campaign-History.md (prior media-plan winners)

Workflow + Meta-side / Google-side structure + kill criteria: see
agents/campaign-launch-strategist.yml.

Output:
1. Write the full media plan to outputs/media-plans/media-plan-${CONCEPT_ID}-${DATE}.md
   via the Write tool (this is the ONE agent allowed to Write — see tools list).
2. Output a SHORT markdown summary to stdout containing:
   - Concept · Total budget · Channel split · Baseline CPA · Kill threshold
   - One \`\`\`json proposed_actions block with the SINGLE Launch action that
     references the media plan path in its description (so the brief surfaces
     a View the media plan button).

CRITICAL: the Launch action MUST include the literal string
'outputs/media-plans/media-plan-${CONCEPT_ID}-${DATE}.md' in its description.
Owner: Joanne, owner_role: Meta Ads Specialist. parent_promo_id: ${CONCEPT_ID}.
source_agent: campaign-launch-strategist.

CRITICAL OUTPUT INSTRUCTION: The SHORT summary goes to stdout (bash wrapper
saves it). The FULL media plan goes to outputs/media-plans/ via Write tool." \
        "$OUT_PATH" \
        "Read(state/promo-pipeline.json),Read(state/membership-data.json),Read(state/ga4-data.json),Read(state/meta-ads-data.json),Read(state/google-ads-data.json),Read(state/work-queue.json),Read(context/utm-convention.md),Read(context/brand-voice.md),Read(/Users/tiachasingbetter/Documents/ChasingBetter/CB_Brain/wiki/Campaign-History.md),Write(outputs/media-plans/**)" \
        "$MODEL_OPUS"
done <<< "$APPROVED_IDS"

log "Step 2 — Extract Launch actions from campaign-launch-strategist outputs..."
"$PYTHON" "$BASE_DIR/scripts/extract_agent_actions.py" --business cb247 --agent campaign-launch-strategist >> "$LOG" 2>&1 \
    || log "  ⚠️  Launch action extraction had issues — check $LOG"

log "Step 3 — Render media plans .md → docs/media-plans/*.html..."
"$PYTHON" "$BASE_DIR/scripts/render_media_plan_html.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  Media-plan rendering had issues — check $LOG"

log "Step 4 — Sync Work Queue → Supabase..."
"$PYTHON" "$BASE_DIR/scripts/work_queue/sync_to_supabase.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  Work Queue sync had issues — check $LOG"

log "=== Phase 1b complete · processed ${count} concept(s) · $(date +%H:%M:%S) ==="
