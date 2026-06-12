#!/bin/bash
# weekly-report.sh — CB247 Marketing OS  (full 9-agent pipeline)
#
# Runs every Monday 10:00 AM Perth Time (AWST = UTC+8) via cron.
# Cron entry:
#   0 10 * * 1 /Users/tiachasingbetter/Documents/ChasingBetter/CB_Marketing/scripts/weekly-report.sh >> /Users/tiachasingbetter/Documents/ChasingBetter/CB_Marketing/state/weekly-report.log 2>&1
#
# Companion cron — Monday 11:30 AM Perth — picks up late Metricool PDF drops:
#   30 11 * * 1 /Users/tiachasingbetter/Documents/ChasingBetter/CB_Marketing/scripts/refresh-social.sh >> /Users/tiachasingbetter/Documents/ChasingBetter/CB_Marketing/state/refresh-social.log 2>&1
#
# APPROVAL FLOW:
#   Agents generate → Tia reviews (dashboard + OS report email) → Tia approves
#   → Jane receives content pipeline for QC → Jane approves → Joanne gets posting schedule
#
# Pipeline:
#   Phase 1  Data Pull      pull_all + pull_ahrefs + pull_apify + site crawl (no duplicate pulls)
#   Phase 2  Agent Pipeline 9 agents in sequence (research → ... → strategist)
#   Phase 3  Outputs        bake reports + deploy dashboard (source of truth)
#   Phase 4  Email Delivery Tia OS report + SEO report — team emails held until Tia approves
#
# NOTE: weekly-seo.sh is merged into this pipeline. Do NOT run weekly-seo.sh separately
#       — all data pulls happen once here to preserve API quotas.

# No set -e — agent failures are tracked in FAILED_AGENTS[], not script-killing.
# Each phase uses explicit || handling so one failed pull/agent doesn't abort the run.
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PIPELINE_START=$(date +%s)
FAILED_AGENTS=()

# ── Load environment (API keys, credentials) — safe parser skips bad lines ──
if [ -f "$BASE_DIR/.env" ]; then
    while IFS='=' read -r key val; do
        # Skip blank lines, comments, and lines without a valid VAR name
        [[ -z "$key" || "$key" =~ ^[[:space:]]*# || ! "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] && continue
        export "$key"="$val"
    done < "$BASE_DIR/.env"
fi

PYTHON="$BASE_DIR/.venv/bin/python3.13"
CLAUDE="/Users/tiachasingbetter/.local/bin/claude"

# ── Model routing — Max subscription ──
# Haiku:  lightweight extraction (audience intel, content intel)
# Sonnet: standard analysis + writing (research, performance, seo, competitor, paid-ads)
# Opus:   heavy synthesis + high-volume creative (content agent, strategist)
MODEL_HAIKU="${ANTHROPIC_DEFAULT_HAIKU_MODEL:-claude-haiku-4-5}"
MODEL_SONNET="${ANTHROPIC_DEFAULT_SONNET_MODEL:-claude-sonnet-4-5}"
MODEL_OPUS="${ANTHROPIC_DEFAULT_OPUS_MODEL:-claude-opus-4-5}"

LOG="$BASE_DIR/state/weekly-report.log"
DATE=$(date '+%Y-%m-%d')
OUTPUTS="$BASE_DIR/outputs"
STATE="$BASE_DIR/state"

# ── Ensure output directories exist ──
mkdir -p "$OUTPUTS/research" "$OUTPUTS/seo" "$OUTPUTS/content" \
         "$OUTPUTS/blueprints" "$OUTPUTS/creatives" \
         "$BASE_DIR/logs/agents"

log()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"; }
fail() { log "ERROR: $1"; }

run_agent() {
    local name="$1"
    local prompt="$2"
    local out="$3"
    local tools="${4:-Read(context/**),Read(outputs/**)}"
    local model="${5:-$MODEL_SONNET}"
    local agent_log="$BASE_DIR/logs/agents/$(date +%Y-%m-%d)-${name}.log"

    log "  → [$model] Running $name..."
    if "$CLAUDE" \
        --allowedTools "$tools" \
        --model "$model" \
        --print \
        --output-format text \
        "$prompt" > "$out" 2>"$agent_log"; then
        log "  ✅ $name complete → $(basename "$out")"
        return 0
    else
        FAILED_AGENTS+=("$name")
        log "  ❌ $name FAILED — log: logs/agents/$(basename "$agent_log")"
        return 0   # return 0 so pipeline continues — failure tracked in FAILED_AGENTS[]
    fi
}

log "================================================================"
log "  CB247 MARKETING OS — MONDAY RUN STARTED"
log "================================================================"
cd "$BASE_DIR"


# ══════════════════════════════════════════════════════════════════
# PHASE 0 — DEV CYCLE PRE-FLIGHT  (~30-60s)
# ══════════════════════════════════════════════════════════════════
# Added 11 Jun 2026 (Wave A). Runs brand voice + schema drift + integration
# test + dep audit BEFORE any data pulls or agent runs. Catches the class
# of bugs we kept hitting:
#   - Schema drift between schema.py and Supabase CHECK constraints
#     (e.g. 'Proposed' rejected silently because SQL still had 'Idea')
#   - Stale workflow vocab in emitter descriptions
#   - Strategist chain regressions (KPI shape, missing metrics)
#   - Vulnerable dependencies in requirements.txt
# Warn-only by default — pipeline continues even if findings are reported.
# Promote any individual check to blocking by editing scripts/dev-cycle.sh.
log ""
log "─── PHASE 0: DEV CYCLE PRE-FLIGHT ───"
bash "$BASE_DIR/scripts/dev-cycle.sh" --pre-flight >> "$LOG" 2>&1 \
    || log "  ⚠️  dev-cycle pre-flight had blocking errors — check $LOG"
log "Phase 0a complete."

# ── Phase 0b: Security audit (Wave B) ────────────────────────────────────
# Runs before any data work. If a secret has leaked or RLS has regressed,
# we want to know BEFORE we touch live data with the suspect credentials.
# Warn-only — pipeline continues but findings are surfaced as P1 ops
# actions via the Agent Action Contract.
log ""
log "─── PHASE 0b: SECURITY AGENT ───"
mkdir -p "$OUTPUTS/security"
run_agent "security-agent" \
"You are the CB247 Security Agent. Today is $DATE.

Walk the last 7 days of commits + the working tree for leaked credentials,
verify .gitignore strength, probe Supabase RLS coverage on the 4 critical
tables, and audit .claude/settings.json.

Read these files:
- .gitignore
- .claudeignore
- db/policies.sql
- db/schema.sql

Critical safety rule: NEVER print actual secret values. When you find a
leaked secret, redact the middle (first 4 chars + '...' + last 4 chars)
and name the platform the key belongs to.

Use grep against the working tree + git log --since=\"7 days ago\" for
known credential patterns (sk-ant-, sk-or-v1-, apify_api_, sb_secret_,
AKIA, GOCSPX-, BEGIN PRIVATE KEY).

Probe Supabase RLS via curl: anon DELETE on each table should fail with
401/403. anon SELECT + UPSERT should succeed.

Output structured markdown ending with a json proposed_actions block.
Each P1 finding (leaked secret, missing gitignore pattern, RLS gap)
becomes an ops action assigned to Tia. Title must start with 'Fix',
'Audit', or 'Rotate' so the classifier puts it in the Ops bucket.

CRITICAL OUTPUT INSTRUCTION: Do NOT use the Write tool. Output the
markdown directly to stdout. The bash wrapper saves your stdout to
outputs/security/security-agent-$DATE.md." \
"$OUTPUTS/security/security-agent-$DATE.md" \
"Read(.gitignore),Read(.claudeignore),Read(db/policies.sql),Read(db/schema.sql),Bash(grep),Bash(git log),Bash(git ls-files),Bash(curl)" \
"$MODEL_SONNET"

log "Phase 0 complete."


# ══════════════════════════════════════════════════════════════════
# PHASE 1 — DATA PULL  (~20 min)
# ══════════════════════════════════════════════════════════════════
log ""
log "─── PHASE 1: DATA PULL ───"

log "Step 1a — Weekly paid-source pull (Google Ads + Meta Ads)..."
"$PYTHON" "$BASE_DIR/scripts/pull_weekly.py" >> "$LOG" 2>&1 \
    || fail "pull_weekly.py had issues — continuing"

log "Step 1a' — Free-source pull (GA4 + GSC + GBP) + inject blocks..."
"$PYTHON" "$BASE_DIR/scripts/pull_all.py" >> "$LOG" 2>&1 \
    || fail "pull_all.py had issues — continuing"

log "Step 1b — Ahrefs (rankings + gaps + organic value)..."
"$PYTHON" "$BASE_DIR/scripts/pull_ahrefs.py" >> "$LOG" 2>&1 \
    || fail "pull_ahrefs.py had issues — continuing"

log "Step 1b' — Manual Ahrefs CSV/PDF parse (fallback for API token outage)..."
# Reads cb247-inbox/ahrefs/*.csv + Overview_*.pdf — if Tia drops fresh exports
# in there, this overwrites state/ahrefs-data.json + state/ahrefs-snapshot-*.json
# with manual data. Falls through silently if inbox is empty or unchanged.
"$PYTHON" "$BASE_DIR/scripts/parse_cb247_ahrefs_csvs.py" >> "$LOG" 2>&1 \
    || fail "parse_cb247_ahrefs_csvs.py had issues — continuing"

log "Step 1c — Apify (SERP + Maps + Reddit + Trends + FB Ads)..."
"$PYTHON" "$BASE_DIR/scripts/pull_apify.py" >> "$LOG" 2>&1 \
    || fail "pull_apify.py had issues — continuing"

log "Step 1d — Site crawl (CB247 + competitors, privacy-compliant)..."
"$PYTHON" "$BASE_DIR/scripts/run_site_crawl.py" --competitors >> "$LOG" 2>&1 \
    || fail "run_site_crawl.py had issues — continuing"

# ── Step 1e: Metricool PDF parse (drop metricool.pdf into cb247-inbox/ before 1:55am AWST) ──
# Drops state/metricool-data.json with the rich Metricool weekly data
# (stories, reach, demographics, GBP actions). Failure mode: preserves
# last good JSON file rather than blanking it.
log "Step 1e — Parse Metricool PDF (cb247-inbox/metricool.pdf)..."
"$PYTHON" "$BASE_DIR/scripts/parse_metricool_pdf.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  Metricool parse skipped — PDF missing or unparseable. Dashboard uses previous parse or hardcoded fallback."

# ── Step 1f: GBP Performance API (per-location actions for Malaga + Ellenbrook) ──
# Requires CB247_GBP_MALAGA_LOCATION_ID + CB247_GBP_ELLENBROOK_LOCATION_ID in .env.
# First-run mode lists accessible locations; subsequent runs pull the metrics.
log "Step 1f — GBP Performance API (per-location actions)..."
"$PYTHON" "$BASE_DIR/scripts/pull_gbp_performance.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  GBP Performance skipped — first-run setup or API not enabled. Dashboard shows aggregate GBP only."

# ── Step 1g: Membership data — parse Perfect Gym + CleverWaiver XLSX exports ──
# Requires PGM_ContractsSummary.xlsx + PGM_AllContracts.xlsx + Cleverwaiver.xlsx
# dropped into cb247-membership-inbox/ before 1:55am Monday. Parser skips
# gracefully if files missing (keeps previous parse).
log "Step 1g — Parse Membership XLSX exports..."
"$PYTHON" "$BASE_DIR/scripts/parse_membership_data.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  Membership parse skipped — XLSX files missing or unparseable. Dashboard uses previous parse."

# ── Step 1h: Work Queue action emission ──
# Reads fresh state/*.json data and emits structured WorkQueueAction records
# to state/work-queue.json. Each performance page contributes its own
# emitter; Session 1 ships only the SEO emitter. Session 2 ingests JSON
# into Supabase so the dashboard displays them as Work Queue cards.
# See: CB_Brain/wiki/Work-Queue-Architecture.md
log "Step 1h — Emit Work Queue actions (SEO)..."
# DISABLED 11 Jun 2026 (Option C build, Tia direction):
# The rule-based seo_emitter.py produced false positives like "Build service
# page: '24/7 gym'" when the CB247 homepage H1 already targeted that
# keyword. It saw only GSC stats (no site URL inventory, no SERP intent
# check, no competitor read), so it couldn't tell whether a page already
# existed for a query. Replaced by agents/seo-strategist.yml — an LLM-driven
# strategic agent that reads the full picture (site map + GSC + Ahrefs)
# and proposes actions via the Agent Action Contract.
# The strategist runs in Step 1h0 below; its proposed_actions block is
# extracted by Step 1h'''''''''' (extract_agent_actions.py) and synced via
# Step 1i (sync_to_supabase.py). Same destination — work_queue_actions
# table — different (smarter) producer.
# Re-enable this line ONLY if the strategist is down for an extended period
# and you need rule-based SEO actions as a safety net.
# "$PYTHON" "$BASE_DIR/scripts/work_queue/seo_emitter.py" >> "$LOG" 2>&1 \
#     || log "  ⚠️  SEO emitter had issues — check $LOG"
log "  ⏭️  Rule-based SEO emitter disabled — strategist agent owns SEO action emission (Step 1h0)"

log "Step 1h' — Emit Work Queue actions (Meta Ads)..."
"$PYTHON" "$BASE_DIR/scripts/work_queue/meta_emitter.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  Meta emitter had issues — check $LOG"

log "Step 1h'' — Emit Work Queue actions (Google Ads)..."
"$PYTHON" "$BASE_DIR/scripts/work_queue/google_ads_emitter.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  Google Ads emitter had issues — check $LOG"

log "Step 1h''' — Emit Work Queue actions (GBP)..."
"$PYTHON" "$BASE_DIR/scripts/work_queue/gbp_emitter.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  GBP emitter had issues — check $LOG"

log "Step 1h'''' — Emit Work Queue actions (Organic Social)..."
"$PYTHON" "$BASE_DIR/scripts/work_queue/social_emitter.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  Social emitter had issues — check $LOG"

log "Step 1h''''' — Emit Work Queue actions (Membership)..."
"$PYTHON" "$BASE_DIR/scripts/work_queue/membership_emitter.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  Membership emitter had issues — check $LOG"

# ── ROI BLOCK (added 09 Jun 2026) — runs AFTER all data-source emitters ──
# opportunity_emitter joins Google Ads search-terms ↔ GSC queries to identify
# keywords where CB247 ranks organically well enough to safely reduce paid
# spend. attribution_emitter aggregates verdict-ed opportunity actions into
# a CUMULATIVE monthly ROI summary card (executive headline).
# Together they close Tia's "reduce Google Ads spend as SEO catches up" loop
# with structured, measurable, programmatic outputs.
log "Step 1h'''''' — Emit ROI Opportunity actions (paid→organic switch)..."
"$PYTHON" "$BASE_DIR/scripts/work_queue/opportunity_emitter.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  Opportunity emitter had issues — check $LOG"

log "Step 1h''''''' — Emit ROI Attribution summary (cumulative savings)..."
"$PYTHON" "$BASE_DIR/scripts/work_queue/attribution_emitter.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  Attribution emitter had issues — check $LOG"

# ── PROMO PIPELINE BLOCK (Wave 5 · 10 Jun 2026) ──────────────────────────────
# promo_concept_emitter reads seasonal calendar + membership signals (future-
# cancel pool, exit reasons, add-on uptake) and emits monthly promo concepts
# split into Acquisition + Retention tracks. Each concept also seeds child
# Work Queue actions tagged with parent_promo_id, which lights up the
# "Awaiting Assets" badge on In Progress kanban cards.
# inject-promo-pipeline rewrites the docs/index.html <script id="promo-
# pipeline-block"> so renderPromoPipeline + renderAssetLibrary consume the
# latest concepts at next page load.
log "Step 1h'''''''' — Emit Promo Concepts (acquisition + retention)..."
"$PYTHON" "$BASE_DIR/scripts/work_queue/promo_concept_emitter.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  Promo concept emitter had issues — check $LOG"

log "Step 1h''''''''' — Inject promo pipeline into dashboard..."
"$PYTHON" "$BASE_DIR/scripts/inject-promo-pipeline.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  Promo pipeline injector had issues — check $LOG"

# ── Step 1h0 — SEO Strategist (LLM, replaces rule-based seo_emitter) ──
# Shipped 11 Jun 2026 as Option C per Tia direction. Strategist reads the
# raw GSC + Screaming Frog + Ahrefs state files and reasons about
# page-keyword fit (does an existing CB247 URL already target this query?
# does this keyword map to a CB247 service?) before proposing actions. Its
# output ends with a ```json proposed_actions block consumed by Step
# 1h'''''''''' (extract_agent_actions). The strategist runs HERE — in
# Phase 1, before extraction — so its actions land in the dashboard in the
# same weekly run, not next week's. See agents/seo-strategist.yml.
log "Step 1h0 — SEO Strategist (LLM, replaces rule-based emitter)..."
run_agent "seo-strategist" \
"You are the CB247 SEO Strategist. Today is $DATE.

Your job is to look at the WHOLE picture — GSC keyword stats, the actual
CB247 URL inventory (Screaming Frog), and competitor positions (Ahrefs) —
and propose 8-12 SEO actions for this week with REAL strategic reasoning,
not rule-based aggregation.

Read these files:
- state/gsc-data.json              (top_queries: keyword, position, impressions, clicks, ctr)
- state/screaming-frog-data.json   (top_pages: url, h1, meta_description, word_count, h2s)
- state/ahrefs-data.json           (CB247 domain rating, competitor positions)
- context/brand-voice.md           (tone)
- context/seo-targets-cb247.md     (priority keyword list)
- context/seo-priorities-cb247.md  (strategic priorities)

Workflow (do all four steps before writing anything):
1. PAGE-KEYWORD INVENTORY — for each CB247 URL in top_pages, note the slug,
   H1, word count, and 1-2 GSC keywords it most plausibly targets.
2. OPPORTUNITY SHORTLIST — pick 12-18 high-leverage GSC queries
   (position × impressions × commercial intent). Drop brand queries
   ('chasing better 247'), drop queries already top-3 (defensive PROTECT
   isn't in scope here), drop near-zero impression long-tail.
3. STRATEGIC DECISION PER KEYWORD — for each, choose ONE of:
     (a) OPTIMISE EXISTING — page exists, edit it. Specify the URL +
         exact edits (H1, meta, internal links).
     (b) BUILD NEW — no existing page. Choose artifact:
           service-page  if keyword matches a CB247 service program
                         (crossfit, reformer pilates, sauna, kids hub,
                         personal training, 24/7, neon21, yoga, spin,
                         chasingrx) — title prefix 'Build service page: '
           landing-page  if local commercial without specific service
                         (e.g. 'gym near me', 'best gym perth') —
                         title prefix 'Build landing page: '
           blog          if informational/question intent ('how to',
                         'best foods', 'tips for') — title prefix
                         'Post blog: '
     (c) SKIP — low impressions + not trending OR no commercial fit.
         Mention in narrative, don't emit an action.

4. WRITE THE REPORT — markdown with these sections (in order):
   # CB247 SEO Strategist — $DATE
   ## Page-Keyword Inventory  (table)
   ## Top GSC Opportunities (Shortlist)  (table)
   ## Strategic Decisions  (one paragraph per proposed action)
   ## Considered but Skipped  (bullets)
   ## Competitive Note  (1 paragraph re Revo/Anytime gaps)
   ## Proposed Actions
   \`\`\`json proposed_actions
   [ ... 8-12 actions per agents/AGENT_ACTION_CONTRACT.md ... ]
   \`\`\`

JSON RULES (CRITICAL):
- category: \"seo-organic\" always
- owner: \"John\" + owner_role: \"SEO Specialist\" for OPTIMISE
- owner: \"AI\"   + owner_role: \"Content Agent\" for BUILD
- priority: P1 if position ≤ 10 AND impressions ≥ 10, else P2, else P3
- effort_hours: 0.5 for meta/H1 edit · 2 for blog · 4 for landing page · 6 for service page
- data_quality: 'high' if Screaming Frog + GSC both confirm, else 'medium'
- projected_kpis: at least one (always gsc_position), with realistic targets
- description: 200-400 chars — include the existing URL (for OPTIMISE) or
  suggested slug (for BUILD), the keyword, the baseline + target position,
  and the SPECIFIC edits or page structure expected.

CRITICAL OUTPUT INSTRUCTION: Do NOT use the Write tool. OUTPUT the entire markdown
report directly to stdout. The bash wrapper saves your stdout to
outputs/seo/seo-strategist-$DATE.md. Do NOT summarise — emit the full
report including the proposed_actions JSON block at the end." \
"$OUTPUTS/seo/seo-strategist-$DATE.md" \
"Read(state/gsc-data.json),Read(state/screaming-frog-data.json),Read(state/ahrefs-data.json),Read(context/brand-voice.md),Read(context/seo-targets-cb247.md),Read(context/seo-priorities-cb247.md)" \
"$MODEL_OPUS"

# ── Step 1h0a — Normalise strategist JSON output ──
# The LLM sometimes outputs projected_kpis as a dict ({"gsc_position":{...}})
# instead of the required list-of-objects shape, or uses metrics not in
# VALID_METRICS (pages_4xx, schema_implemented). This script cleans up the
# proposed_actions JSON block in the strategist's markdown so extraction
# downstream just works. Idempotent — re-running on clean JSON is a no-op.
log "Step 1h0a — Normalise strategist JSON output..."
"$PYTHON" "$BASE_DIR/scripts/work_queue/normalize_strategist_output.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  Strategist normalisation had issues — check $LOG (non-fatal)"

# ── Step 1h'''''''''' — Extract Agent Action Proposals (Agent Action Contract) ──
# Layer 3 (Agents): when CB247 agents produce markdown output ending with a
# ```json proposed_actions block, extract them as WorkQueueAction objects
# and merge into state/work-queue.json. See agents/AGENT_ACTION_CONTRACT.md.
# Graceful no-op if no agents have produced output yet (early days for the
# new contract). Must run BEFORE sync_to_supabase so extracted actions get
# pushed up.
#
# As of 11 Jun 2026 (Option C), the seo-strategist's output at
# outputs/seo/seo-strategist-$DATE.md is the primary SEO action source —
# extraction here pulls those into the queue.
log "Step 1h'''''''''' — Extract Agent action proposals (Agent Action Contract)..."
"$PYTHON" "$BASE_DIR/scripts/extract_agent_actions.py" --business cb247 >> "$LOG" 2>&1 \
    || log "  ⚠️  Agent action extraction had issues — check $LOG (non-fatal)"

# ── Step 1i: Sync Work Queue → Supabase ──
# Pushes state/work-queue.json into the work_queue_actions table so the
# dashboard renders fresh actions in real-time. Idempotent on PK (id).
log "Step 1i — Sync Work Queue to Supabase..."
"$PYTHON" "$BASE_DIR/scripts/work_queue/sync_to_supabase.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  Work Queue sync had issues — check $LOG"

# ── Step 1j: Regenerate per-action HTML briefs (Fix 10 Jun 2026) ──
# CB247 mirror of generate_mwcc_briefs.py. The dashboard modal's "View Brief"
# link opens docs/briefs/{action_id}.html — these files must exist for every
# current Work Queue ID or the link 404s. This script reads
# state/work-queue.json + state/promo-pipeline.json and bakes one HTML brief
# per action (with parent_promo_id linkage for child items).
log "Step 1j — Regenerate per-action briefs..."
"$PYTHON" "$BASE_DIR/scripts/generate_briefs.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  Brief generation had issues — check $LOG"

# ── Step 1k: Re-index blog drafts (Wave 2.15 · 11 Jun 2026) ──
# Scans docs/blog-drafts/*.html and writes the slug list into
# docs/index.html as window.BLOG_DRAFTS_INDEX. The dashboard's
# _findExistingDraft() helper uses this to auto-attach drafts to
# matching content actions (e.g. "Improve organic content for
# 'gym ellenbrook perth'" → gym-ellenbrook-perth.html).
log "Step 1k — Inject blog-drafts index..."
"$PYTHON" "$BASE_DIR/scripts/inject-blog-drafts-index.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  Blog drafts index injection had issues — check $LOG"

# ── Step 1l: QA agent (Wave B · 11 Jun 2026) ─────────────────────────────
# Runs AFTER all data + emitter + sync + brief generation steps so it can
# cross-check the live Supabase state against the rendered dashboard and
# local state. Output is a markdown report with a proposed_actions block;
# findings get extracted by the existing Agent Action Contract pipeline
# on the NEXT weekly run (or you can re-run extract_agent_actions manually
# this same run if you want findings to surface immediately).
log ""
log "─── Step 1l: QA AGENT (post-sync dashboard cross-check) ───"
mkdir -p "$OUTPUTS/qa"
run_agent "qa-agent" \
"You are the CB247 QA Agent. Today is $DATE.

Cross-check three sources of truth that should all agree:
  1. state/work-queue.json (local authoritative file)
  2. Live Supabase work_queue_actions rows (via curl)
  3. docs/index.html render functions (renderSEO etc.) + hand-coded items

Read these files:
- state/work-queue.json
- state/promo-pipeline.json
- docs/index.html
- agents/AGENT_ACTION_CONTRACT.md (for your own output contract)

Pull live Supabase rows via:
  curl https://ckjwzwktuiavyfuolbgx.supabase.co/rest/v1/work_queue_actions?select=id,source_page,title,priority,owner -H 'apikey: sb_publishable_3giOfPJ92JW7DN8w9jPvoQ_cFo4rd0s'

Catch these bug classes:
  - Stale 'seo-act-*' or 'prop-*' rows still in Supabase (should be 0
    after the Wave A.6 cleanup)
  - Count mismatch: Supabase rows per source_page vs state file rows
  - Hand-coded items in renderSEO/renderMeta/renderGAds/etc. that
    pre-date the LLM strategist (look for inline 'actions.push({...})'
    blocks; modern flow merges from cbState.workQueue only)
  - Wrong classification: title starts with 'Fix'/'Add * schema'/etc.
    but bucketed as Content instead of Ops per _classifyActionKind
  - Missing brief files: every non-prop-* row should have a
    docs/briefs/{id}.html
  - Draft attachment gaps: content actions whose slug matches a
    docs/blog-drafts/ file but draft_link is empty in Supabase

Output markdown to stdout with sections:
  ## Source-of-truth counts
  ## Classification mismatches
  ## Stale-ID survivors
  ## Brief file integrity
  ## Draft attachment gaps
  ## Orphan drafts
  ## Proposed Actions   (with \`\`\`json proposed_actions block)

JSON rules per agents/AGENT_ACTION_CONTRACT.md:
- title must start with a verb that classifies to Ops (Fix/Audit/Rotate/
  Clean/Remove) so QA findings appear in the Ops list, not Content
- category: 'seo-organic' (default Ops routing)
- owner: 'John' (SEO Specialist) for content/data issues, 'Tia'
  (OS Owner) for infrastructure/sync issues
- priority: P1 if misleading the team today, P2 if risk in 7d, P3 cosmetic
- effort_hours: 0.25-1.0
- data_quality: 'high'
- projected_kpis: at least one — use 'qualitative_assessment' for QA
  findings (a yes/no the team verifies after fixing)

If everything is clean, emit proposed_actions: [] and a one-paragraph
'Dashboard healthy as of $DATE' summary.

CRITICAL OUTPUT INSTRUCTION: Do NOT use the Write tool. Output the
markdown directly to stdout. The bash wrapper saves your stdout to
outputs/qa/qa-agent-$DATE.md." \
"$OUTPUTS/qa/qa-agent-$DATE.md" \
"Read(state/work-queue.json),Read(state/promo-pipeline.json),Read(docs/index.html),Read(docs/briefs/**),Read(docs/blog-drafts/**),Bash(curl)" \
"$MODEL_SONNET"

# ── Step 1m: Visual regression (Wave C · 12 Jun 2026) ────────────────────
# Screenshots every dashboard page via headless Chromium, image-diffs
# against docs/baselines/. Catches the class of UI bugs Wave A + B can't
# see (wrong column, broken spacing, accent shift). Runs against the LIVE
# deployed dashboard so it sees the same thing the team sees. Warn-only.
log ""
log "─── Step 1m: VISUAL REGRESSION (Wave C) ───"
"$PYTHON" "$BASE_DIR/scripts/visual_regression.py" --source live --log >> "$LOG" 2>&1 \
    || log "  ⚠️  Visual regression had blocking errors — check $LOG"

log "Phase 1 complete."


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


# ══════════════════════════════════════════════════════════════════
# PHASE 2 — AGENT PIPELINE  (~40 min, sequential)
# ══════════════════════════════════════════════════════════════════
log ""
log "─── PHASE 2: AGENT PIPELINE ───"

# ── Agent 1: Research Agent ──
# Reads: Apify trends + Reddit + competitor ads → market signals
log "Agent 1/9 — Research Agent"
run_agent "research-agent" \
"You are the CB247 Research Agent. Today is $DATE.

Read these files for all market intelligence data:
- context/research-context.json  (competitor SERP positions, local pack, Revo/Anytime Facebook ads, Reddit intel, Google Trends, social trends — pre-compressed from live data)
- context/seasonal-calendar.md   (active campaigns, upcoming events, trigger rules)

Output a structured markdown report covering:
1. SEASONAL ALERT — check context/seasonal-calendar.md: what is ACTIVE right now, what is within 21 days, what needs prep within 60 days. Flag if a campaign should be spawned this week.
2. TOP 5 TRENDING FITNESS TOPICS in Perth/AU this week (from Google Trends + Reddit)
3. PERTH MARKET SIGNALS — what's happening: FIFO seasons, events, cost-of-living sentiment
4. WHAT COMPETITORS ARE RUNNING — Revo Fitness + Anytime Fitness Meta/FB ads right now (themes, offers, angles)
5. 5 CONTENT ANGLES CB247 should use this week — aligned with seasonal context + data
6. REDDIT PAIN POINTS — exact language Perth people use about gyms (use for copy)
7. OPPORTUNITIES — what competitors are NOT saying that CB247 should own

Be specific. Use actual data from the files. No filler.

CRITICAL OUTPUT INSTRUCTION: Do NOT use the Write tool. OUTPUT THE FULL MARKDOWN REPORT AS YOUR DIRECT RESPONSE. The bash wrapper saves your stdout to outputs/research/weekly-research-$DATE.md automatically. Generate the FULL report content directly in your response — do NOT summarise, do NOT say 'I will write...' or 'saved to...' — just write the report markdown directly." \
"$OUTPUTS/research/weekly-research-$DATE.md" \
"Read(context/research-context.json),Read(context/seasonal-calendar.md)" \
"$MODEL_SONNET"

# ── Agent 2: Audience Intel ──
log "Agent 2/9 — Audience Intel"
run_agent "audience-intel" \
"You are the CB247 Audience Intel Agent. Today is $DATE.

Read these files:
- context/audience-context.json              (GA4: sessions, conversions by channel, top pages, device split — pre-compressed from live data)
- outputs/research/weekly-research-$DATE.md  (market signals + Reddit language from Agent 1)

CB247's 4 key ICPs:
1. FIFO Workers — fly in/fly out, need flexible freeze, train hard in their weeks off
2. Malaga Families — parents with kids, value Kids Hub, cost-conscious
3. Ellenbrook Locals — community-driven, newer suburb, want to belong
4. Health-Seeker Newcomers — new to fitness, intimidated by big gyms, want guidance

Output a structured markdown report covering:
1. ICP PULSE — for each ICP: what they care about THIS week (based on trends/Reddit data)
2. ICP CONVERSION — which ICP is converting best this week (from GA4)
3. EXACT LANGUAGE to use in copy this week (pulled from Reddit/reviews — real phrases)
4. TOP 3 OBJECTIONS to address in content this week
5. META TARGETING BRIEF — audience targeting recommendations for when Meta account reinstated
6. TONE RECOMMENDATION — how CB247 should sound this week (based on market mood)

Be specific and data-driven.

CRITICAL OUTPUT INSTRUCTION: Do NOT use the Write tool. OUTPUT THE FULL MARKDOWN REPORT AS YOUR DIRECT RESPONSE. The bash wrapper saves your stdout to outputs/research/audience-weekly-$DATE.md automatically. Generate the FULL report content directly — do NOT summarise, do NOT say 'I will write...' — just write the report markdown directly." \
"$OUTPUTS/research/audience-weekly-$DATE.md" \
"Read(context/audience-context.json),Read(outputs/research/**)" \
"$MODEL_HAIKU"

# ── Agent 3: Content Intel ──
log "Agent 3/9 — Content Intel"
run_agent "content-intel" \
"You are the CB247 Content Intel Agent. Today is $DATE.

Read these files:
- context/content-intel-context.json         (TikTok + Instagram top posts by engagement, trending hashtags — pre-compressed from live data)
- outputs/research/weekly-research-$DATE.md  (Google Trends, competitor ads intel from Agent 1)
- outputs/research/audience-weekly-$DATE.md

CB247 brand: health & fitness club in Perth (Malaga + Ellenbrook). Teal brand.
Tagline: AlwaysBetter. Services: 24/7 gym, Neon21 tanning, Yoga, Spin, CrossFit,
Reformer Pilates, ChasingRX, Sauna + Ice Bath, Kids Hub, PT, FIFO freeze.
Price: \$11.95/week, no lock-in.

Output a structured markdown report covering:
1. TOP 5 VIRAL HOOKS this week — adapted for CB247 (with example caption for each)
2. TOP 3 CONTENT FORMATS with full script/template (Reel script, carousel outline, story sequence)
3. COMPETITOR CONTENT GAPS — what Revo/Anytime are NOT covering that CB247 can own
4. TRENDING AUDIO RECOMMENDATIONS — 3 trending sounds for Reels/TikTok this week
5. REPEAT WINNERS — content types/angles that consistently perform for fitness brands right now
6. CONTENT CALENDAR SIGNALS — which of the 4 ICPs to target on which platform this week

Be specific. Include actual hooks word-for-word. This feeds directly into content creation.

CRITICAL OUTPUT INSTRUCTION: Do NOT use the Write tool. OUTPUT THE FULL MARKDOWN REPORT AS YOUR DIRECT RESPONSE. The bash wrapper saves your stdout to outputs/research/content-intel-$DATE.md automatically. Generate the FULL report content directly — do NOT summarise, do NOT say 'I will write...' — just write the report markdown directly." \
"$OUTPUTS/research/content-intel-$DATE.md" \
"Read(context/content-intel-context.json),Read(outputs/research/**)" \
"$MODEL_HAIKU"

# ── Agent 4: Performance ──
log "Agent 4/9 — Performance Agent"
run_agent "performance" \
"You are the CB247 Performance Agent. Today is $DATE.

Read this file for all performance data:
- context/performance-context.json  (GA4 sessions/conversions, GSC queries, Google Ads spend/CPA by campaign and location — pre-compressed from live data)

KPI targets: Google CTR>4% | CPC<\$3 | Meta CPM<\$12 | CPL<\$25

Output a structured markdown performance report covering:
1. KPI DASHBOARD — Full table: metric | this week | last week | target | RAG status (🔴🟡🟢)
   Include: sessions, conversions, organic clicks, avg position, ad spend, CPA by location
2. ORGANIC vs PAID RATIO — is SEO replacing Google Ads? Trend direction?
3. WINS THIS WEEK — what worked well (specific, data-backed)
4. ISSUES THIS WEEK — what needs attention (specific, data-backed)
5. BUDGET RECOMMENDATION — based on current CPA, what ad spend is still needed?
6. 3 ACTIONS — one each for Organic, Paid, and Content

Be precise. Every number must come from context/performance-context.json.

CRITICAL OUTPUT INSTRUCTION: Do NOT use the Write tool. OUTPUT THE FULL MARKDOWN REPORT AS YOUR DIRECT RESPONSE. The bash wrapper saves your stdout to outputs/research/performance-week-$DATE.md automatically. Generate the FULL report content directly — do NOT summarise, do NOT say 'I will write...' — just write the report markdown directly." \
"$OUTPUTS/research/performance-week-$DATE.md" \
"Read(context/performance-context.json)" \
"$MODEL_SONNET"

# ── Agent 5: SEO Agent (primary growth driver) ──
log "Agent 5/9 — SEO Agent"
run_agent "seo-agent" \
"You are the CB247 SEO Agent. Today is $DATE. SEO is the PRIMARY growth driver — the goal
is to grow organic search and REDUCE Google Ads spend by replacing paid traffic with organic.

Read these files:
- context/seo-context.json               (Ahrefs: target keyword positions, WoW changes, keyword gap vs Revo/Anytime, broken backlinks, organic value \$/week; GSC: top queries + CTR + position; site crawl issues; local pack presence — pre-compressed from live data)
- outputs/research/performance-week-$DATE.md
- outputs/research/weekly-research-$DATE.md  (trending topics for content brief angles)

CB247 target keywords (20 priority KWs tracked in ahrefs-data):
gym malaga perth, 24/7 gym malaga, gym ellenbrook perth, 24/7 gym ellenbrook,
cheap gym perth, reformer pilates malaga, reformer pilates perth, sauna gym perth,
ice bath gym perth, kids gym malaga, family gym malaga, fifo gym perth,
fifo gym membership perth, personal training malaga, crossfit malaga perth,
spin class malaga, yoga malaga perth, gym membership perth no lock in, chasingbetter247

Output a structured markdown SEO report covering:
1. RANKING TABLE — all 20 target keywords: current pos | WoW change (↑↓) | URL | volume | status
2. QUICK WINS — keywords in positions 4–20 with specific fix per page (exact: H1 change, meta description, internal link to add)
3. KEYWORD GAP — top 10 keywords Revo/Anytime rank for, we don't. Priority order with content recommendation.
4. CONTENT BRIEF 1 — full brief for highest-opportunity keyword: keyword, H1, meta desc, outline (H2s + key points), schema type, word count, internal link suggestions
5. CONTENT BRIEF 2 — second content brief (same format)
6. BACKLINK REPORT — new backlinks gained, broken backlinks to reclaim (with fix), lost backlinks
7. ORGANIC VALUE TRACKER — current \$/week, WoW change, cumulative Google Ads offset
8. GOOGLE ADS OFFSET — which keywords we now rank #1–3 organically → recommend pausing those ads
9. LOCAL PACK STATUS — which keywords CB247 appears in 3-pack, which it's missing from

Be actionable. Every recommendation must have a specific fix, not just 'improve this page'.

CRITICAL OUTPUT INSTRUCTION: Do NOT use the Write tool. OUTPUT THE FULL MARKDOWN REPORT AS YOUR DIRECT RESPONSE. The bash wrapper saves your stdout to outputs/seo/weekly-seo-brief-$DATE.md automatically. Generate the FULL report content directly — do NOT summarise, do NOT say 'I will write...' — just write the report markdown directly." \
"$OUTPUTS/seo/weekly-seo-brief-$DATE.md" \
"Read(context/seo-context.json),Read(outputs/research/**)" \
"$MODEL_SONNET"

# ── Agent 6: Competitor Spy ──
log "Agent 6/9 — Competitor Spy"
run_agent "competitor-spy" \
"You are the CB247 Competitor Spy Agent. Today is $DATE.

Read these files:
- context/competitor-context.json          (SERP positions for each keyword, local pack presence, Maps ratings, Revo/Anytime/Snap Facebook ads — pre-compressed from live data)
- outputs/research/weekly-research-$DATE.md
- outputs/seo/weekly-seo-brief-$DATE.md    (keyword gap analysis from SEO agent)

CB247 competitors: Revo Fitness (biggest threat), Anytime Fitness, Snap Fitness, Ryderwear Gym Malaga.

Output a structured markdown competitive intelligence report covering:
1. COMPETITOR MOVES THIS WEEK — ranked by threat level (🔴 high / 🟡 medium / 🟢 low)
   Include: what they changed, why it matters, recommended CB247 response
2. GBP BATTLE TABLE — CB247 vs Revo vs Anytime: rating | reviews | photos | local pack presence
3. KEYWORD THREATS — competitors gaining positions on CB247's keywords (WoW movements)
4. AD INTEL — what Revo + Anytime are spending on right now (angles, offers, CTAs from FB Ads)
5. OPPORTUNITIES — what competitors are ignoring that CB247 can own right now
6. STRATEGIC RECOMMENDATION — one specific counter-move CB247 should make this week

Be competitive and specific. Name actual keywords, prices, and tactics.

CRITICAL OUTPUT INSTRUCTION: Do NOT use the Write tool. OUTPUT THE FULL MARKDOWN REPORT AS YOUR DIRECT RESPONSE. The bash wrapper saves your stdout to outputs/research/competitor-weekly-$DATE.md automatically. Generate the FULL report content directly — do NOT summarise, do NOT say 'I will write...' — just write the report markdown directly." \
"$OUTPUTS/research/competitor-weekly-$DATE.md" \
"Read(context/competitor-context.json),Read(outputs/research/**),Read(outputs/seo/**)" \
"$MODEL_SONNET"

# ── Agent 7: Paid Ads ──
log "Agent 7/9 — Paid Ads Agent"
run_agent "paid-ads" \
"You are the CB247 Paid Ads Agent. Today is $DATE.
Primary directive: REDUCE Google Ads spend as SEO takes over. Every dollar saved on ads
that are now covered by organic is a win.

Read these files:
- context/paid-ads-context.json             (Google Ads spend/CPA/conversions by campaign + location, current and prior week; which target keywords rank organically #1-3 — pre-compressed from live data)
- outputs/seo/weekly-seo-brief-$DATE.md    (Google Ads offset recommendations from SEO agent)
- outputs/research/audience-weekly-$DATE.md (ICP targeting brief)
- outputs/research/content-intel-$DATE.md  (creative angles for Meta)

Output a structured markdown paid ads report covering:
GOOGLE ADS:
1. PAUSE IMMEDIATELY — keywords/ads where CB247 ranks organically #1–3 (specific campaign + ad group + estimated weekly saving)
2. REDUCE BUDGET — keywords where CB247 ranks #4–10 (50% budget reduction recommended)
3. KEEP RUNNING — keywords with no organic coverage (must maintain paid presence)
4. CUMULATIVE SAVINGS TRACKER — total saved this month vs start of programme
5. CAMPAIGN HEALTH — each active campaign: spend | CPA | conversions | recommendation

META ADS (prepared for reinstatement):
6. AUDIENCE TARGETING — 3 audience segments from Audience Intel brief (ready to activate)
7. CREATIVE BRIEF — top 3 ad angles from Content Intel (hook + body + CTA)
8. BUDGET SPLIT — recommended spend by ICP when account reinstates

Be specific: name exact campaigns, keyword groups, and dollar amounts.

CRITICAL OUTPUT INSTRUCTION: Do NOT use the Write tool. OUTPUT THE FULL MARKDOWN REPORT AS YOUR DIRECT RESPONSE. The bash wrapper saves your stdout to outputs/research/paid-ads-weekly-$DATE.md automatically. Generate the FULL report content directly — do NOT summarise, do NOT say 'I will write...' — just write the report markdown directly." \
"$OUTPUTS/research/paid-ads-weekly-$DATE.md" \
"Read(context/paid-ads-context.json),Read(outputs/seo/**),Read(outputs/research/**)" \
"$MODEL_SONNET"

# ── Agent 8: Content Agent ──
log "Agent 8/9 — Content Agent"
run_agent "content-agent" \
"You are the CB247 Content Agent. Today is $DATE.
Generate a full week of READY-TO-PUBLISH content — the team should be able to copy-paste.
Content is SEO-led, ICP-driven, seasonally aware, and informed by viral trends.

Read these files:
- context/content-agent-context.json             (trending hashtags + top viral hooks — pre-compressed trend signals)
- outputs/seo/weekly-seo-brief-$DATE.md          (keyword briefs, ranking data)
- outputs/research/content-intel-$DATE.md         (viral hooks, formats, audio)
- outputs/research/audience-weekly-$DATE.md       (ICP language, tone, pain points)
- outputs/research/competitor-weekly-$DATE.md     (competitor gaps to exploit)
- outputs/research/weekly-research-$DATE.md       (seasonal alert from Agent 1 — check this first)
- context/brand-voice.md                          (CB247 tone and voice rules)
- context/seasonal-calendar.md                    (active campaigns + upcoming events)
- context/psychology-triggers.md                  (conversion triggers — every piece needs min 2)

SEASONAL RULE: If Agent 1 flagged a seasonal alert, at least 2 of the 5 social posts and 1 reel script must reflect the active campaign angle. If a school holiday or event is within 14 days, include Kids Hub content.

PSYCHOLOGY RULE: Every ad copy variation and every reel script must use at least 2 triggers from context/psychology-triggers.md. Name which triggers you used at the top of each piece.

CB247: AlwaysBetter. Teal. \$11.95/week. Malaga + Ellenbrook. No lock-in.
Services: 24/7 gym, Reformer Pilates, Sauna, Ice Bath, Kids Hub, CrossFit, Spin, Yoga, PT, FIFO freeze.

Generate ALL of the following — complete, copy-paste ready:

1. GBP POSTS (4 posts — keyword-rich, one per Tuesday for a month)
   Format: [Title] [Body 150–200 words, include target keyword naturally] [CTA]

2. BLOG DRAFTS (2 drafts — from SEO content briefs)
   Format: [Title] [Meta description] [H1] [Introduction 100 words] [H2 outline with key points]
   → These go to John (SEO) + Shauna (content) to complete

3. SOCIAL POSTS (5 posts — Instagram/TikTok, with viral hooks from Content Intel)
   Format: [Platform] [Hook] [Caption 100–150 words] [Hashtags 10–15] [Image/video brief]

4. REEL SCRIPTS (2 scripts — 30 sec + 45 sec)
   Format: [Hook (first 3 sec)] [Body (scene by scene)] [CTA (last 3 sec)] [Trending audio suggestion]
   → These go to Agust + Ivan (video editors)

5. REVIEW RESPONSE TEMPLATES (5 templates — for Joanne/front desk)
   Format: [Trigger: positive / negative / neutral] [Response 50–75 words]

6. META AD COPY (3 variations — for when account reinstates)
   Format: [Audience] [Headline] [Body 90 words] [CTA] [Format: image/video/carousel]

CRITICAL OUTPUT INSTRUCTION: Do NOT use the Write tool. OUTPUT EVERYTHING (all 6 sections — GBP posts, blog drafts, social posts, reel scripts, review templates, Meta ad copy) AS YOUR DIRECT RESPONSE. The bash wrapper saves your stdout to outputs/content/weekly-content-$DATE.md automatically. Generate ALL content directly — do NOT summarise, do NOT say 'I will write...' — just write everything in your response." \
"$OUTPUTS/content/weekly-content-$DATE.md" \
"Read(context/content-agent-context.json),Read(context/brand-voice.md),Read(context/seasonal-calendar.md),Read(context/psychology-triggers.md),Read(outputs/**)" \
"$MODEL_OPUS"

# ── Agent 9: Strategist — inject upstream failure context ──
log "Agent 9/9 — Strategist"
if [ ${#FAILED_AGENTS[@]} -gt 0 ]; then
    FAILURE_NOTE="PIPELINE WARNING: The following agents failed this run and their outputs may be missing or incomplete: ${FAILED_AGENTS[*]}. Add a 'PIPELINE ISSUES' section at the top of your strategy document listing each failed agent and what data is therefore missing."
else
    FAILURE_NOTE="All 8 upstream agents completed successfully this run."
fi

run_agent "strategist" \
"You are the CB247 Marketing Strategist. Today is $DATE.
Synthesise ALL 8 agent outputs into ONE executive strategy document.
This is the single source of truth Tia reviews before anything goes to the team.

PIPELINE STATUS: $FAILURE_NOTE

Read ALL of these:
- outputs/research/weekly-research-$DATE.md
- outputs/research/audience-weekly-$DATE.md
- outputs/research/content-intel-$DATE.md
- outputs/research/performance-week-$DATE.md
- outputs/seo/weekly-seo-brief-$DATE.md
- outputs/research/competitor-weekly-$DATE.md
- outputs/research/paid-ads-weekly-$DATE.md
- outputs/content/weekly-content-$DATE.md
- context/seasonal-calendar.md

Output a concise executive strategy document covering:
0. SEASONAL STATUS — Always first. What campaign is ACTIVE right now. What is within 21 days (trigger full campaign brief). What needs planning within 60 days. One clear directive for Tia on seasonal priority this week.

1. WEEKLY SCORECARD
   - SEO Health Score: X/100 (from ranking data)
   - Organic Traffic Value: \$X/week (WoW change)
   - Google Ads Saved (cumulative): \$X since programme started
   - Organic vs Paid ratio: X% organic
   - GBP Rating: X.X ⭐ (X reviews)

2. TOP 5 PRIORITIES THIS WEEK — ranked by revenue/growth impact
   Each: what | why (data reason) | who owns it | deadline

3. DECISIONS NEEDED FROM TIA — anything requiring approval or direction
   Each: decision | context | recommended action | deadline

4. TEAM SUMMARY (one line per person):
   - Ange: [strategic priority this week]
   - Jane: [QC items this week — count of content pieces to review]
   - John: [SEO tasks this week]
   - Mark: [Dev/technical tasks this week]
   - Agust & Ivan: [Video briefs ready]
   - Shauna: [Content creation tasks]
   - Joanne: [Posts to schedule — pending Jane approval]

5. WEEKLY NARRATIVE — 3 sentences: where we are, what moved, what matters most

CRITICAL OUTPUT INSTRUCTION: Do NOT use the Write tool. OUTPUT THE FULL EXECUTIVE STRATEGY MARKDOWN AS YOUR DIRECT RESPONSE. The bash wrapper saves your stdout to outputs/blueprints/weekly-strategy-$DATE.md automatically. Generate the FULL strategy directly — do NOT summarise, do NOT say 'I will write...' or 'ready to save once permission granted' — just write the strategy markdown directly." \
"$OUTPUTS/blueprints/weekly-strategy-$DATE.md" \
"Read(context/seasonal-calendar.md),Read(outputs/**)" \
"$MODEL_OPUS"

log "Phase 2 complete — all 9 agents run."


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
