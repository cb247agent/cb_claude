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
    local tools="${4:-Read(context/**),Read(outputs/**),Write(outputs/**)}"
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
# PHASE 1 — DATA PULL  (~20 min)
# ══════════════════════════════════════════════════════════════════
log ""
log "─── PHASE 1: DATA PULL ───"

log "Step 1a — GA4 + GSC + Google Ads + Meta..."
"$PYTHON" "$BASE_DIR/scripts/pull_all.py" >> "$LOG" 2>&1 \
    || fail "pull_all.py had issues — continuing"

log "Step 1b — Ahrefs (rankings + gaps + organic value)..."
"$PYTHON" "$BASE_DIR/scripts/pull_ahrefs.py" >> "$LOG" 2>&1 \
    || fail "pull_ahrefs.py had issues — continuing"

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
Save to: outputs/research/weekly-research-$DATE.md" \
"$OUTPUTS/research/weekly-research-$DATE.md" \
"Read(context/research-context.json),Read(context/seasonal-calendar.md),Write(outputs/research/**)" \
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
Save to: outputs/research/audience-weekly-$DATE.md" \
"$OUTPUTS/research/audience-weekly-$DATE.md" \
"Read(context/audience-context.json),Read(outputs/research/**),Write(outputs/research/**)" \
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
Save to: outputs/research/content-intel-$DATE.md" \
"$OUTPUTS/research/content-intel-$DATE.md" \
"Read(context/content-intel-context.json),Read(outputs/research/**),Write(outputs/research/**)" \
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
Save to: outputs/research/performance-week-$DATE.md" \
"$OUTPUTS/research/performance-week-$DATE.md" \
"Read(context/performance-context.json),Write(outputs/research/**)" \
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
Save to: outputs/seo/weekly-seo-brief-$DATE.md" \
"$OUTPUTS/seo/weekly-seo-brief-$DATE.md" \
"Read(context/seo-context.json),Read(outputs/research/**),Write(outputs/seo/**)" \
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
Save to: outputs/research/competitor-weekly-$DATE.md" \
"$OUTPUTS/research/competitor-weekly-$DATE.md" \
"Read(context/competitor-context.json),Read(outputs/research/**),Read(outputs/seo/**),Write(outputs/research/**)" \
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
Save to: outputs/research/paid-ads-weekly-$DATE.md" \
"$OUTPUTS/research/paid-ads-weekly-$DATE.md" \
"Read(context/paid-ads-context.json),Read(outputs/seo/**),Read(outputs/research/**),Write(outputs/research/**)" \
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

Save EVERYTHING to: outputs/content/weekly-content-$DATE.md" \
"$OUTPUTS/content/weekly-content-$DATE.md" \
"Read(context/content-agent-context.json),Read(context/brand-voice.md),Read(context/seasonal-calendar.md),Read(context/psychology-triggers.md),Read(outputs/**),Write(outputs/content/**)" \
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

Save to: outputs/blueprints/weekly-strategy-$DATE.md" \
"$OUTPUTS/blueprints/weekly-strategy-$DATE.md" \
"Read(context/seasonal-calendar.md),Read(outputs/**),Write(outputs/blueprints/**)" \
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
