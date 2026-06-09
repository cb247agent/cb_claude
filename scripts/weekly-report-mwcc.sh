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
FAILED_AGENTS=()
OPS_SKIPPED=false

# ── Load environment (API keys, credentials) — safe parser skips bad lines ──
if [ -f "$BASE_DIR/.env" ]; then
    while IFS='=' read -r key val; do
        [[ -z "$key" || "$key" =~ ^[[:space:]]*# || ! "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] && continue
        export "$key"="$val"
    done < "$BASE_DIR/.env"
fi

PYTHON="$BASE_DIR/.venv/bin/python3.13"
CLAUDE="/Users/tiachasingbetter/.local/bin/claude"
LOG="$BASE_DIR/logs/mwcc-weekly-report.log"
DATE=$(date '+%Y-%m-%d')
OUTPUTS="$BASE_DIR/outputs/mwcc"

# ── Model routing (Claude Max sub — same as CB247 weekly-report.sh) ──
# Haiku:  lightweight extraction (audience intel, content intel)
# Sonnet: standard analysis + writing (research, performance, seo)
# Opus:   heavy synthesis + high-volume creative (content brief, strategist)
MODEL_HAIKU="${ANTHROPIC_DEFAULT_HAIKU_MODEL:-claude-haiku-4-5}"
MODEL_SONNET="${ANTHROPIC_DEFAULT_SONNET_MODEL:-claude-sonnet-4-5}"
MODEL_OPUS="${ANTHROPIC_DEFAULT_OPUS_MODEL:-claude-opus-4-5}"

# ── Ensure directories exist (Layer 2 agent outputs land under outputs/mwcc/*) ──
mkdir -p "$BASE_DIR/logs" \
         "$BASE_DIR/logs/agents" \
         "$BASE_DIR/outputs/reports/mwcc" \
         "$OUTPUTS/research" \
         "$OUTPUTS/seo" \
         "$OUTPUTS/content" \
         "$OUTPUTS/blueprints" \
         "$BASE_DIR/state"

log()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"; }
fail() { log "ERROR: $1"; }

# ── run_agent helper — ported verbatim from weekly-report.sh ──
# Tracks failures in FAILED_AGENTS[] so a single agent failing doesn't abort
# the pipeline (the strategist agent injects this list into its synthesis).
run_agent() {
    local name="$1"
    local prompt="$2"
    local out="$3"
    local tools="${4:-Read(context/**),Read(outputs/**),Write(outputs/**)}"
    local model="${5:-$MODEL_SONNET}"
    local agent_log="$BASE_DIR/logs/agents/$(date +%Y-%m-%d)-mwcc-${name}.log"

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
        return 0   # pipeline continues — failures tracked in FAILED_AGENTS[]
    fi
}

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
        && log "  ✅ MWCC Ahrefs pull complete → state/mwcc-ahrefs.json" \
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
# STEP 4.6a2 — MWCC Viral Hashtag Scrape (Apify TikTok + Instagram)
# Powers content-intel-mwcc with real viral signals from Perth childcare
# niche hashtags (#childcareperth, #perthmums, #workingparents, etc.).
# Graceful: writes available=false placeholder if Apify is down / no key.
# Cost: ~$0.20/run (capped at 5 posts × 7 tags × 2 platforms).
# ─────────────────────────────────────────────────────────────────
log ""
log "─── STEP 4.6a2: MWCC Viral Hashtag Scrape (Apify) ───"
if "$PYTHON" "$BASE_DIR/scripts/pull_mwcc_social_trends.py" >> "$LOG" 2>&1; then
    log "  ✅ MWCC viral trends scraped → state/mwcc-social-trends.json"
else
    FAILED_STEPS+=("mwcc-social-trends")
    log "  ⚠️  MWCC viral trends scrape failed (non-fatal — content-intel will degrade)"
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


# ══════════════════════════════════════════════════════════════════
# PHASE 4.8 — MWCC AGENT PIPELINE  (~40 min, sequential, 9-agent parity with CB247)
# ══════════════════════════════════════════════════════════════════
# Mirrors CB247's 9-agent pipeline (weekly-report.sh PHASE 2):
#   1. research-perth-childcare ← research-agent
#   2. audience-intel-mwcc      ← audience-intel
#   3. content-intel-mwcc       ← content-intel  (now powered by Step 4.6a2
#                                                  viral-trends scrape)
#   4. performance-mwcc         ← performance
#   5. seo-agent-mwcc           ← seo-agent (primary growth driver)
#   6. competitor-spy-mwcc      ← competitor-spy (added 09 Jun 2026)
#   7. paid-ads-mwcc            ← paid-ads      (added 09 Jun 2026)
#   8. content-brief            ← content-agent
#   9. strategist-mwcc          ← strategist
log ""
log "─── PHASE 4.8: MWCC AGENT PIPELINE (9 agents — full CB247 parity) ───"
log "Running 9 agents sequentially to enrich the emitter cards into strategic briefs."

# ── Agent 1/9: Research (Perth childcare market signals) ──
log "Agent 1/9 — research-perth-childcare"
run_agent "research-perth-childcare" \
"You are the MWCC (My World Childcare) Research Agent. Today is $DATE.

MWCC operates 5 centres in Perth WA: Armadale (OSHC), Midvale (LDC+OSHC), Rockingham (OSHC),
Seville Grove (LDC+OSHC), Waikiki (LDC). Brand voice: warm, professional, CCS-aware,
no \"best\" claims, no scarcity tactics, no child photos.

Read these files for market intelligence:
- context/mwcc-competitors.md         (Midvale Hub, Goodstart, Nido Early School, Care for Kids, KindiCare)
- context/mwcc-business-config.json   (centres, services, thresholds)
- context/mwcc-seasonal-calendar.md   (active campaigns + upcoming term/holiday windows)
- state/mwcc-gsc-data.json            (organic search performance)
- state/mwcc-ops.json                 (per-centre occupancy + room utilisation)

Output a structured markdown report covering:
1. SEASONAL ALERT — read context/mwcc-seasonal-calendar.md: what is ACTIVE right now (Term enrolment window? Vacation Care booking push? 2027 waitlist?). What is within 21 days. What needs prep within 60 days.
2. PERTH CHILDCARE SIGNALS — what's moving in the local market: enrolment seasonality, government CCS changes, holiday period demand, competitor centre openings/closures.
3. COMPETITOR ACTIVITY — recent moves by Midvale Hub, Goodstart, Nido — pricing, capacity claims, marketing angles.
4. PARENT PAIN POINTS — what working Perth parents are saying about childcare (waitlist anxiety, CCS confusion, OSHC scarcity, drop-off stress).
5. 5 CONTENT ANGLES MWCC should use this week — aligned with seasonal context.
6. OPPORTUNITIES — gaps competitors are NOT filling that MWCC can own (e.g., transparent CCS quotes, real educator faces, room-by-room tour content).

Be specific. No fluff. No \"best\" claims. CCS mention required wherever fees come up.
Save to: outputs/mwcc/research/mwcc-weekly-research-$DATE.md" \
"$OUTPUTS/research/mwcc-weekly-research-$DATE.md" \
"Read(context/mwcc-competitors.md),Read(context/mwcc-business-config.json),Read(context/mwcc-seasonal-calendar.md),Read(state/mwcc-gsc-data.json),Read(state/mwcc-ops.json),Write(outputs/mwcc/research/**)" \
"$MODEL_SONNET"

# ── Agent 2/9: Audience Intel (MWCC parent ICPs) ──
log "Agent 2/9 — audience-intel-mwcc"
run_agent "audience-intel-mwcc" \
"You are the MWCC Audience Intel Agent. Today is $DATE.

Read these files:
- context/mwcc-marketing-strategy.md       (ICPs + channel strategy)
- context/mwcc-psychology-triggers.md      (conversion triggers per ICP)
- context/mwcc-business-config.json
- context/mwcc-brand-context.md
- state/mwcc-ga4.json                       (website sessions, top pages, traffic sources)
- state/mwcc-gsc-data.json                  (search queries by parent intent)
- outputs/mwcc/research/mwcc-weekly-research-$DATE.md  (market signals from Agent 1)

MWCC's parent ICPs (verify against context/mwcc-marketing-strategy.md before writing):
1. Working Parents — both partners working, time-poor, fee-conscious, want predictable care
2. FIFO Families — one partner away on swings, single-handler drop-off, need flexible casual days
3. OSHC Parents — primary school children, before/after school + Vacation Care, near school
4. New-to-Childcare — first child or relocating to Perth, CCS confusion, NQS/rating-focused
5. Subsidy-Reliant — high CCS percentage, fees are make-or-break, need quote transparency

Output a structured markdown report covering:
1. ICP PULSE — for each ICP: what they care about THIS week (based on Agent 1 signals)
2. ICP CONVERSION — which ICP is converting best this week (from GA4 traffic + GSC clicks)
3. EXACT PARENT LANGUAGE to use in copy this week (pulled from GSC query patterns + Agent 1 pain points)
4. TOP 3 OBJECTIONS to address in content this week (e.g., \"is my child too young\", \"how much will CCS actually cover\", \"can I trust the educators\")
5. CHANNEL MIX RECOMMENDATION — IG / FB / email / GBP — which ICP responds where
6. TONE RECOMMENDATION — how MWCC should sound this week. Warm, knowledgeable, specific. NEVER salesy.

Be specific. No \"best\" claims. CCS always mentioned with \"subject to eligibility\".
Save to: outputs/mwcc/research/mwcc-audience-weekly-$DATE.md" \
"$OUTPUTS/research/mwcc-audience-weekly-$DATE.md" \
"Read(context/mwcc-*.md),Read(context/mwcc-business-config.json),Read(state/mwcc-ga4.json),Read(state/mwcc-gsc-data.json),Read(outputs/mwcc/research/**),Write(outputs/mwcc/research/**)" \
"$MODEL_HAIKU"

# ── Agent 3/9: Content Intel (MWCC content patterns — now with live viral signal) ──
# 09 Jun 2026 (later): added pull_mwcc_social_trends.py (Step 4.6a2). Apify
# now scrapes #childcareperth, #perthmums, #workingparents etc. weekly. If
# the placeholder file is present (available=false), the agent still runs
# but degrades to own-page signals only.
log "Agent 3/9 — content-intel-mwcc"
run_agent "content-intel-mwcc" \
"You are the MWCC Content Intel Agent. Today is $DATE.

Read these files:
- context/mwcc-brand-voice.md                          (warm, knowledgeable, no superlatives)
- context/mwcc-psychology-triggers.md                  (conversion triggers per ICP)
- context/mwcc-marketing-strategy.md
- state/mwcc-social.json                                (MWCC's own IG + FB + GBP performance)
- state/mwcc-social-trends.json                         (Apify scrape of #childcareperth, #perthmums, #workingparents, etc. — top viral posts + co-occurring hashtags. Check 'available' field first; if false, fall back to own-page + competitor signals.)
- outputs/mwcc/research/mwcc-weekly-research-$DATE.md  (market + competitor signals from Agent 1)
- outputs/mwcc/research/mwcc-audience-weekly-$DATE.md  (ICP pulse from Agent 2)

MWCC: 5 Perth centres (Armadale OSHC, Midvale LDC+OSHC, Rockingham OSHC, Seville Grove LDC+OSHC, Waikiki LDC).
Lavender/purple palette. NO photos of children — locked rule. CCS mention required wherever fees come up.

Output a structured markdown report covering:
1. TOP 5 VIRAL HOOKS THIS WEEK — pulled FROM state/mwcc-social-trends.json top_posts. For each: hook 12-18 words (adapt the viral angle for MWCC voice — never copy verbatim) + which underlying viral post inspired it (cite engagement number + platform).
2. TRENDING HASHTAG MIX — top 8 co-occurring hashtags from mwcc-social-trends.json (use these on IG/FB this week).
3. TOP 3 CONTENT FORMATS that suit MWCC voice — Reel script outline, carousel outline, Story sequence.
4. COMPETITOR CONTENT GAPS — what Midvale Hub / Goodstart / Nido are NOT covering that MWCC can own.
5. OWN-PAGE WINNERS — from state/mwcc-social.json: which MWCC posts performed best last week, what pattern do they share?
6. APPROVED VISUAL CATEGORIES — pick from: educators (with consent) · centre spaces · materials/artwork · branded graphics · parent quote graphics · storytelling captions. NEVER children's faces.
7. CONTENT CALENDAR SIGNALS — which ICP to target on which platform this week (from Agent 2 ICP pulse).

If state/mwcc-social-trends.json has 'available': false — note the limitation at the top of section 1 and fall back to own-page winners + competitor gaps as the hook source.

Be specific. Include actual caption openers, not generic templates. No emojis on email or landing pages (limited IG/FB OK).
Save to: outputs/mwcc/research/mwcc-content-intel-$DATE.md" \
"$OUTPUTS/research/mwcc-content-intel-$DATE.md" \
"Read(context/mwcc-*.md),Read(state/mwcc-social.json),Read(state/mwcc-social-trends.json),Read(outputs/mwcc/research/**),Write(outputs/mwcc/research/**)" \
"$MODEL_HAIKU"

# ── Agent 4/9: Performance ──
log "Agent 4/9 — performance-mwcc"
run_agent "performance-mwcc" \
"You are the MWCC Performance Agent. Today is $DATE.

Read these files:
- state/mwcc-ads.json                  (Google Ads spend, conversions by campaign + location)
- state/mwcc-meta.json                 (Meta paid + organic performance)
- state/mwcc-ga4.json                  (website sessions + conversions)
- state/mwcc-work-queue.json           (live tactical actions across all emitters)
- state/mwcc-funnel.json               (sessions → conversions → enquiries → enrolments → exits)
- state/mwcc-ops.json                  (per-centre occupancy + room utilisation)
- context/mwcc-business-config.json    (KPI targets + thresholds)
- context/mwcc-team-roster.md          (who owns what)

KPI focus for childcare:
- Enrolments per week vs target (per-centre)
- Occupancy % per centre per room
- Cost-per-Enquiry (Google Ads + Meta)
- Wage ratio % (target ≤50%, alert at ≥55%)
- Organic vs paid traffic ratio

Output a structured markdown performance report covering:
1. KPI DASHBOARD — table: metric | this week | last week | target | RAG status (🔴🟡🟢).
   Include: enrolments, exits, enquiries, occupancy% (per centre), wage ratio%, organic sessions, paid CPA.
2. ORGANIC vs PAID RATIO — is SEO replacing Google Ads? Trend direction this week?
3. PER-CENTRE PULSE — Armadale · Midvale · Rockingham · Seville Grove · Waikiki — one line each on health.
4. WINS THIS WEEK — what worked (specific, data-backed).
5. ISSUES THIS WEEK — what needs attention (specific, data-backed).
6. BUDGET RECOMMENDATION — based on current CPA, what ad spend is still needed?
7. 3 ACTIONS — one each for Organic, Paid, Operations (centre-level).

Every number must come from state/mwcc-*.json. No fabricated metrics.
Save to: outputs/mwcc/research/mwcc-performance-week-$DATE.md" \
"$OUTPUTS/research/mwcc-performance-week-$DATE.md" \
"Read(state/mwcc-*.json),Read(context/mwcc-*),Write(outputs/mwcc/research/**)" \
"$MODEL_SONNET"

# ── Agent 5/9: SEO (primary growth driver — same role as CB247) ──
# Same directive as CB247 seo-agent: grow organic, reduce Google Ads spend.
log "Agent 5/9 — seo-agent-mwcc (primary growth driver)"
run_agent "seo-agent-mwcc" \
"You are the MWCC SEO Agent. Today is $DATE. SEO is the PRIMARY growth driver — the goal
is to grow organic search and REDUCE Google Ads spend by replacing paid traffic with organic.

Read these files:
- state/mwcc-work-queue.json                            (live emitter cards — your INPUT, expand each)
- state/mwcc-gsc-data.json                              (top queries, CTR, position)
- state/mwcc-ahrefs.json                                (domain rating, target keywords, competitor gap)
- state/mwcc-ads.json                                   (Google Ads spend per campaign — for paid→organic swap recs)
- context/mwcc-seo-targets.md                           (MWCC target keywords by suburb + service)
- context/mwcc-seo-priorities.md                        (P1/P2/P3 SEO priorities)
- context/mwcc-brand-voice.md                           (CCS-aware, no \"best\")
- context/mwcc-business-config.json                     (5 centres + service map)
- outputs/mwcc/research/mwcc-performance-week-$DATE.md
- outputs/mwcc/research/mwcc-weekly-research-$DATE.md

MWCC target keyword themes (verify exact list against context/mwcc-seo-targets.md):
childcare perth, childcare midvale, childcare waikiki, childcare armadale, childcare seville grove,
childcare rockingham, oshc perth, oshc midvale, vacation care perth, long day care perth,
ccs perth, before school care perth, after school care perth, kindy perth, my world childcare.

Output a structured markdown SEO report covering:
1. RANKING TABLE — all target keywords from context/mwcc-seo-targets.md: current pos | WoW change (↑↓) | URL | volume | status.
2. QUICK WINS — keywords ranking #4–20 with specific fix per page (exact H1 change, meta description, internal link).
3. KEYWORD GAP — top 10 keywords competitors rank for, MWCC doesn't. Priority order with content recommendation.
4. CONTENT BRIEF 1 — full brief for highest-opportunity keyword: keyword, H1, meta desc, outline (H2s + key points), schema type, word count, internal link suggestions, mandatory CCS mention placement.
5. CONTENT BRIEF 2 — second content brief (same format).
6. GOOGLE ADS OFFSET — which keywords MWCC now ranks #1–3 organically → recommend pausing those ads (with estimated weekly saving).
7. LOCAL PACK STATUS — which centre keywords MWCC appears in 3-pack, which is missing.
8. EMITTER CARD EXPANSION — for EACH SEO action card in mwcc-work-queue.json (source_page=seo-organic, source_agent != mwcc-content-calendar), write a 1-paragraph strategic brief: why it matters, page structure rec, expected impact, who owns (John / Mark / Kelley).

Be actionable. No \"best\" claims. CCS mention required in every blog brief.
Save to: outputs/mwcc/seo/mwcc-weekly-seo-brief-$DATE.md" \
"$OUTPUTS/seo/mwcc-weekly-seo-brief-$DATE.md" \
"Read(state/mwcc-*.json),Read(context/mwcc-*),Read(outputs/mwcc/research/**),Write(outputs/mwcc/seo/**)" \
"$MODEL_SONNET"

# ── Agent 6/9: Competitor Spy (MWCC competitor moves this week) ──
log "Agent 6/9 — competitor-spy-mwcc"
run_agent "competitor-spy-mwcc" \
"You are the MWCC Competitor Spy Agent. Today is $DATE.

MWCC competitors (verify scope against context/mwcc-competitors.md):
- Midvale Hub                (local — battles Midvale + Seville Grove)
- Goodstart Early Learning   (national chain — battles all 5 centres)
- Nido Early School          (national premium — battles Waikiki + Seville Grove)
- Care for Kids              (aggregator — battles all)
- KindiCare                  (aggregator — battles all)

Read these files:
- context/mwcc-competitors.md                            (curated battle cards)
- context/mwcc-business-config.json                      (MWCC's 5 centres + service mix)
- context/mwcc-brand-voice.md                            (NEVER name a competitor disparagingly)
- state/mwcc-gsc-data.json                               (organic position vs competitor keywords)
- state/mwcc-ahrefs.json                                 (competitor keyword gap)
- state/mwcc-gbp-performance.json                        (MWCC's own GBP performance — context for compare)
- outputs/mwcc/research/mwcc-weekly-research-$DATE.md   (Agent 1 already flagged competitor moves — go DEEPER, don't repeat)
- outputs/mwcc/seo/mwcc-weekly-seo-brief-$DATE.md       (SEO Agent's keyword gap analysis)

Use WebFetch sparingly for: ACECQA register (https://www.acecqa.gov.au/resources/national-registers/services) per-centre NQS lookup; competitor public GBP pages for review count + recent review sentiment.

COMPLIANCE GATE (MANDATORY):
- This report is OBSERVATIONAL, not adversarial.
- NEVER write 'Goodstart is worse' / 'Midvale Hub is failing' / 'Nido overcharges'.
- Frame all comparisons as 'MWCC's [X] is stronger' or 'opportunity for MWCC to differentiate on [Y]'.
- Per mwcc-brand-voice.md: 'Never name a competitor disparagingly'.

Output a structured markdown report:
1. PIPELINE NOTE — if Agent 1 (research-perth-childcare) already flagged a competitor move, reference it briefly and go deeper.
2. COMPETITOR MOVES THIS WEEK — ranked by threat level for MWCC enrolments (🔴 high / 🟡 medium / 🟢 low). For each: what changed, why it matters for which MWCC centres, recommended MWCC response (specific, time-boxed, named owner).
3. GBP BATTLE TABLE — MWCC centres vs overlapping competitors per suburb. Columns: centre/competitor | suburb | rating | reviews count | photos count | recent review sentiment (last 5).
4. NQS RATING CHANGES — for each competitor centre, current NQS rating from ACECQA register. Flag any \"Working Towards → Meeting\" or \"Meeting → Exceeding\" moves since last week (real marketing signals).
5. KEYWORD THREATS — top 5 keywords where competitors GAINED position on MWCC this week (from Ahrefs WoW delta). For each: keyword | MWCC pos | competitor that gained | counter-move (existing MWCC page to update OR new content).
6. OPPORTUNITIES — what competitors are NOT covering that MWCC can own (transparent CCS quotes, real educator stories, room-by-room virtual tours, parent quote graphics).
7. STRATEGIC RECOMMENDATION — ONE specific counter-move MWCC should make this week. Concrete, time-boxed, named owner (Tia / Denver / Kelley / John / Mark).

Save to: outputs/mwcc/research/mwcc-competitor-weekly-$DATE.md" \
"$OUTPUTS/research/mwcc-competitor-weekly-$DATE.md" \
"Read(context/mwcc-*),Read(state/mwcc-gsc-data.json),Read(state/mwcc-ahrefs.json),Read(state/mwcc-gbp-performance.json),Read(outputs/mwcc/**),Write(outputs/mwcc/research/**),WebFetch" \
"$MODEL_SONNET"

# ── Agent 7/9: Paid Ads (paid→organic switch — closes the loop with SEO Agent) ──
log "Agent 7/9 — paid-ads-mwcc"
run_agent "paid-ads-mwcc" \
"You are the MWCC Paid Ads Agent. Today is $DATE.
PRIMARY DIRECTIVE: REDUCE Google Ads spend as SEO takes over. Every dollar saved on an
ad that's now covered by organic is a measurable win for the SEO programme.

Read these files:
- state/mwcc-ads.json                                    (Google Ads spend, conversions per campaign + location)
- state/mwcc-ads-history.json                            (WoW trend)
- state/mwcc-meta.json                                   (Meta paid + organic performance)
- state/mwcc-meta-history.json                           (WoW trend)
- state/mwcc-work-queue.json                             (live SEO emitter cards — which keywords rank where)
- context/mwcc-business-config.json                      (CPA targets + pause/scale/optimise thresholds)
- context/mwcc-brand-voice.md                            (NO 'best', NO 'limited spots' unless Kelley confirms)
- context/mwcc-psychology-triggers.md                    (every ad copy variation needs ≥2 named triggers)
- outputs/mwcc/seo/mwcc-weekly-seo-brief-$DATE.md       (THE KEY INPUT — read the GOOGLE ADS OFFSET section)
- outputs/mwcc/research/mwcc-audience-weekly-$DATE.md   (ICP targeting brief for Meta)
- outputs/mwcc/research/mwcc-content-intel-$DATE.md     (creative angles + viral hooks from Step 4.6a2 scrape)

COMPLIANCE GATE (MANDATORY before saving):
- NO 'best childcare' / 'leading childcare' / 'premier' — ACL undefendable.
- NO 'limited spots' / 'spots filling fast' unless Kelley confirms capacity in writing.
- CCS mention mandatory wherever fees appear in ad copy.
- Service-type accuracy: don't advertise LDC at Armadale or Rockingham (OSHC-only); don't advertise OSHC at Waikiki (LDC-only).
- NO photos of children in any visual brief — approved categories only.
- Any creative copy needs ≥2 named psychology triggers from context/mwcc-psychology-triggers.md.

Output a structured markdown report:

GOOGLE ADS:
1. PAUSE IMMEDIATELY — keywords MWCC now ranks organically #1-3 (from SEO Agent's GOOGLE ADS OFFSET section). For each: specific campaign + ad group + estimated weekly saving. EXCEPTION: never pause brand keywords ('my world childcare', 'my world child care') even if ranked #1 — defensive bid.
2. REDUCE BUDGET — keywords MWCC ranks #4-10 (50% budget reduction recommended). Specific campaigns + new daily budget.
3. KEEP RUNNING — keywords with no organic coverage where MWCC must hold paid presence.
4. CUMULATIVE SAVINGS TRACKER — total saved this month vs start of programme (read prior week's paid-ads report to compute; if first week, start at \$0).
5. CAMPAIGN HEALTH — each active Google Ads campaign: spend | CPA vs target (\$25 enquiry target) | conversions | RAG status | specific recommended action (with owner: Tia).

META ADS:
6. ACCOUNT HEALTH — any rejected ads, account warnings, audience saturation flags.
7. AUDIENCE TARGETING — 3 segments from Audience Intel brief, ready to activate.
8. CREATIVE REFRESH — top 3 ad copy variations using hooks from Content Intel. Each: headline (40 chars) | body (≤90 words) | CTA | visual brief (which approved category — NEVER children's faces) | named psychology triggers used.
9. BUDGET SPLIT — recommended spend by suburb (Armadale, Midvale, Rockingham, Seville Grove, Waikiki) + ICP.

UTM HYGIENE:
10. UTM ISSUES — any miss-tagged live campaigns (utm_source / utm_medium / utm_campaign) for Tia to fix.

ATTRIBUTION LOOP:
11. PAID → ORGANIC CONFIRMED — keywords paused in prior weeks that organic has now successfully replaced. Measure: did organic clicks on that query meet/exceed last-month paid clicks for the same query? Cite specific keywords + numbers.

Be specific: name exact campaign IDs, keyword groups, dollar amounts.
Save to: outputs/mwcc/research/mwcc-paid-ads-weekly-$DATE.md" \
"$OUTPUTS/research/mwcc-paid-ads-weekly-$DATE.md" \
"Read(state/mwcc-*.json),Read(context/mwcc-*),Read(outputs/mwcc/**),Write(outputs/mwcc/research/**)" \
"$MODEL_SONNET"

# ── Agent 8/9: Content Brief (replaces content-agent) ──
log "Agent 8/9 — content-brief (multi-format weekly content)"
run_agent "content-brief" \
"You are the MWCC Content Brief Agent. Today is $DATE.
Generate a full week of READY-TO-PUBLISH content briefs — Jordan/Joanne should be able to
take each block and execute without inventing copy from scratch.

Read these files:
- state/mwcc-social.json                                (MWCC IG/FB/GBP performance per centre)
- state/mwcc-ops.json                                   (per-centre occupancy — under-utilised rooms need promotion)
- state/mwcc-meta.json                                  (paid Meta performance, audience response)
- context/mwcc-team-roster.md                           (who owns what)
- context/mwcc-brand-voice.md                           (knowledgeable friend, not salesperson)
- context/mwcc-business-config.json                     (5 centres + room mix)
- context/mwcc-seasonal-calendar.md                     (active campaigns + upcoming events)
- context/mwcc-psychology-triggers.md                   (every piece needs ≥2 triggers)
- outputs/mwcc/seo/mwcc-weekly-seo-brief-$DATE.md       (SEO content briefs from Agent 5)
- outputs/mwcc/research/mwcc-content-intel-$DATE.md    (viral hooks + hashtags from Agent 3)
- outputs/mwcc/research/mwcc-audience-weekly-$DATE.md  (ICP language, tone, pain points from Agent 2)
- outputs/mwcc/research/mwcc-weekly-research-$DATE.md  (seasonal alert from Agent 1)
- outputs/mwcc/research/mwcc-competitor-weekly-$DATE.md (competitor gaps to exploit from Agent 6)
- outputs/mwcc/research/mwcc-paid-ads-weekly-$DATE.md  (Meta creative briefs from Agent 7)

HARD RULES (NEVER violate):
- NO photos of children. Approved visual categories ONLY: educators (with consent) · centre spaces · materials/artwork · branded graphics · parent quotes · storytelling captions.
- NO \"best\" claims. NO scarcity manipulation. NO emojis on email/landing pages (limited IG/FB OK).
- MENTION CCS wherever fees come up. \"Eligible for CCS\" or \"subject to eligibility\".
- Centres: Armadale (OSHC), Midvale (LDC+OSHC), Rockingham (OSHC), Seville Grove (LDC+OSHC), Waikiki (LDC). Get the service mix RIGHT.

SEASONAL RULE: If Agent 1 flagged a seasonal alert (Term enrolment, Vacation Care booking, 2027 waitlist), at least 3 of the 5 social posts and 1 GBP post must reflect the active campaign angle.

Generate ALL of the following — complete, copy-paste ready briefs (NOT final published copy — drafts for Jordan to refine + Jane/Kelley to QC):

1. GBP POSTS (5 — one per centre, 150-200 words each, localised to suburb)
   Format: [Centre] [Headline] [Body 150-200 words, suburb in first sentence, CCS mention if fees come up] [CTA: Book / Call / Learn more]

2. BLOG BRIEFS (2 — from the SEO Agent's content briefs above)
   Format: [Title] [Meta description ≤155 chars] [H1] [Intro 100 words draft] [H2 outline with key points] [Mandatory CCS mention placement] [Internal links to add]
   → Goes to John (SEO) + Mark (Webflow publish) — Kelley QC

3. IG/FB POSTS (5 — one per workday, with hook from Content Intel)
   Format: [Platform IG/FB/both] [Hook 12-18 words] [Caption 80-180 words] [Hashtags 8-12 mix #perthdaycare + suburb] [Visual brief: which approved category + exact shot description] [Best post time]
   → Joanne schedules; Jordan creates assets

4. IG STORY SEQUENCE (3 frames — single-day campaign)
   Format: [Frame text 15-30 words] [Visual brief] [Sticker recommendation: Poll/Question/Countdown/Link] [Best time]

5. EMAIL BROADCAST (1 — to enquiry list + past enrolment families)
   Format: [Subject A keyword-led] [Subject B curiosity-led] [Preheader 60-80 chars] [Body ≤4 paragraphs, plain-text fallback, NO emojis] [CTA button]
   → Joanne sends

6. REVIEW RESPONSE TEMPLATES (3 — positive / negative / neutral)
   Format: [Trigger] [Response 50-75 words, warm, CCS-aware, never combative]
   → Kelley / centre directors use

Use psychology triggers from context/mwcc-psychology-triggers.md — name which triggers each piece uses at the top.

Save EVERYTHING to: outputs/mwcc/content/mwcc-weekly-content-$DATE.md" \
"$OUTPUTS/content/mwcc-weekly-content-$DATE.md" \
"Read(state/mwcc-*.json),Read(context/mwcc-*),Read(outputs/mwcc/**),Write(outputs/mwcc/content/**)" \
"$MODEL_OPUS"

# ── Agent 9/9: Strategist — inject upstream failure context ──
log "Agent 9/9 — strategist-mwcc"
if [ ${#FAILED_AGENTS[@]} -gt 0 ]; then
    MWCC_FAILURE_NOTE="PIPELINE WARNING: The following MWCC agents failed this run and their outputs may be missing or incomplete: ${FAILED_AGENTS[*]}. Add a 'PIPELINE ISSUES' section at the top of your strategy document listing each failed agent and what data is therefore missing."
else
    MWCC_FAILURE_NOTE="All 8 upstream MWCC agents completed successfully this run."
fi

run_agent "strategist-mwcc" \
"You are the MWCC Marketing Strategist. Today is $DATE.
Synthesise ALL 8 upstream agent outputs into ONE executive strategy document.
This is the single source of truth Tia + Denver review before anything goes to the team.

PIPELINE STATUS: $MWCC_FAILURE_NOTE

Read ALL of these:
- outputs/mwcc/research/mwcc-weekly-research-$DATE.md     (market signals)
- outputs/mwcc/research/mwcc-audience-weekly-$DATE.md     (ICP pulse)
- outputs/mwcc/research/mwcc-content-intel-$DATE.md       (viral hooks + hashtags)
- outputs/mwcc/research/mwcc-performance-week-$DATE.md    (KPI scorecard)
- outputs/mwcc/seo/mwcc-weekly-seo-brief-$DATE.md         (SEO strategy + briefs)
- outputs/mwcc/research/mwcc-competitor-weekly-$DATE.md   (competitor moves + threats)
- outputs/mwcc/research/mwcc-paid-ads-weekly-$DATE.md     (paid→organic switch recs)
- outputs/mwcc/content/mwcc-weekly-content-$DATE.md       (multi-format briefs)
- context/mwcc-seasonal-calendar.md                       (campaign calendar)
- context/mwcc-team-roster.md                             (team owners)

Output a concise MWCC executive strategy document covering:

0. SEASONAL STATUS — Always first. What campaign is ACTIVE right now (Term enrolment? Vacation Care? 2027 waitlist?). What is within 21 days (trigger full campaign brief). What needs planning within 60 days. One clear directive for Tia + Denver on seasonal priority this week.

1. WEEKLY SCORECARD
   - Enrolments this week (target vs actual)
   - Exits this week
   - Network occupancy % (weighted) + WoW change
   - Google Ads spend + CPA + WoW change
   - Organic vs paid ratio + trend direction
   - Wage ratio % + RAG status
   - Per-centre health: Armadale · Midvale · Rockingham · Seville Grove · Waikiki

2. TOP 5 PRIORITIES THIS WEEK — ranked by enrolment/revenue/spend impact
   Each: what | why (data reason) | who owns it (Tia / Denver / Kelley / Jordan / Joanne / John / Mark) | deadline

3. DECISIONS NEEDED FROM TIA / DENVER — anything requiring approval or direction
   Each: decision | context | recommended action | deadline

4. TEAM SUMMARY (one line per person):
   - Kelley:  [centre ops priority this week — occupancy / wage / enrolment chase]
   - Jordan:  [content + creative tasks — number of pieces to produce]
   - Joanne:  [posts to schedule — pending Kelley/Jane approval]
   - John:    [SEO tasks — page tunes + new blog briefs]
   - Mark:    [Webflow publishes + technical fixes]
   - Dana:    [marketing strategy support tasks]

5. WEEKLY NARRATIVE — 3 sentences: where MWCC is, what moved, what matters most.

Save to: outputs/mwcc/blueprints/mwcc-weekly-strategy-$DATE.md" \
"$OUTPUTS/blueprints/mwcc-weekly-strategy-$DATE.md" \
"Read(context/mwcc-*),Read(outputs/mwcc/**),Write(outputs/mwcc/blueprints/**)" \
"$MODEL_OPUS"

log "Phase 4.8 complete — 9 MWCC agents run (full CB247 parity)."


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
