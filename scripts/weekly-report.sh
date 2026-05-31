#!/bin/bash
# weekly-report.sh — CB247 Marketing OS  (full 9-agent pipeline)
#
# Runs every Monday 10:00 AM Perth Time (AWST = UTC+8) via cron.
# Cron entry:
#   0 2 * * 1 /Users/tiachasingbetter/Documents/ChasingBetter/CB_Marketing/scripts/weekly-report.sh >> /Users/tiachasingbetter/Documents/ChasingBetter/CB_Marketing/state/weekly-report.log 2>&1
#
# APPROVAL FLOW:
#   Agents generate → Tia reviews (dashboard + OS report email) → Tia approves
#   → Jane receives content pipeline for QC → Jane approves → Joanne gets posting schedule
#
# Pipeline:
#   Phase 1  Data Pull      pull_all + pull_ahrefs + pull_apify
#   Phase 2  Agent Pipeline 9 agents in sequence (research → ... → strategist)
#   Phase 3  Outputs        bake reports + push Notion + deploy dashboard
#   Phase 4  Email Delivery Tia OS report ONLY — team emails held until Tia approves

set -e
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$BASE_DIR/.venv/bin/python3"
CLAUDE="/Users/tiachasingbetter/.local/bin/claude"
LOG="$BASE_DIR/state/weekly-report.log"
DATE=$(date '+%Y-%m-%d')
OUTPUTS="$BASE_DIR/outputs"
STATE="$BASE_DIR/state"

# ── Ensure output directories exist ──
mkdir -p "$OUTPUTS/research" "$OUTPUTS/seo" "$OUTPUTS/content" \
         "$OUTPUTS/blueprints" "$OUTPUTS/creatives"

log()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"; }
fail() { log "ERROR: $1"; }
run_agent() {
    local name="$1"
    local prompt="$2"
    local out="$3"
    log "  → Running $name..."
    if "$CLAUDE" --model minimax/minimax-m2.7 \
        --allowedTools "Read,Write,Bash,Glob,Grep" \
        --print \
        --output-format text \
        "$prompt" > "$out" 2>>"$LOG"; then
        log "  ✅ $name complete → $(basename "$out")"
        return 0
    else
        log "  ⚠️  $name had issues — check $out"
        return 1
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

log "Phase 1 complete."


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

Read these data files and synthesise the weekly market intelligence report:
- state/apify-data.json        (SERP, Maps, social trends, Reddit, Google Trends, FB Ads)
- state/reddit-intel.json      (Perth/fitness Reddit discussions)
- state/google-trends.json     (trending topics in Perth/WA)
- state/fb-ads-intel.json      (Revo + Anytime active Facebook ads)

Output a structured markdown report covering:
1. TOP 5 TRENDING FITNESS TOPICS in Perth/AU this week (from Google Trends + Reddit)
2. PERTH MARKET SIGNALS — what's happening: FIFO seasons, events, cost-of-living sentiment
3. WHAT COMPETITORS ARE RUNNING — Revo Fitness + Anytime Fitness Meta/FB ads right now (themes, offers, angles)
4. 5 CONTENT ANGLES CB247 should use this week (specific, actionable, tied to data)
5. REDDIT PAIN POINTS — exact language Perth people use about gyms (use for copy)
6. OPPORTUNITIES — what competitors are NOT saying that CB247 should own

Be specific. Use actual data from the files. No filler.
Save to: outputs/research/weekly-research-$DATE.md" \
"$OUTPUTS/research/weekly-research-$DATE.md"

# ── Agent 2: Audience Intel ──
log "Agent 2/9 — Audience Intel"
run_agent "audience-intel" \
"You are the CB247 Audience Intel Agent. Today is $DATE.

Read these files:
- state/ga4-data.json           (who is converting: age, location, device)
- state/reddit-intel.json       (pain points, language, competitor mentions)
- outputs/research/weekly-research-$DATE.md (this week's market signals)

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
"$OUTPUTS/research/audience-weekly-$DATE.md"

# ── Agent 3: Content Intel ──
log "Agent 3/9 — Content Intel"
run_agent "content-intel" \
"You are the CB247 Content Intel Agent. Today is $DATE.

Read these files:
- state/social-trends.json      (TikTok + Instagram top posts by engagement)
- state/google-trends.json      (trending topics Perth/WA)
- state/fb-ads-intel.json       (competitor FB ad creatives + messaging)
- outputs/research/weekly-research-$DATE.md
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
"$OUTPUTS/research/content-intel-$DATE.md"

# ── Agent 4: Performance ──
log "Agent 4/9 — Performance Agent"
run_agent "performance" \
"You are the CB247 Performance Agent. Today is $DATE.

Read these files:
- state/ga4-data.json           (sessions, conversions, bounce rate, top pages)
- state/gsc-data.json           (organic clicks, impressions, avg position, CTR)
- state/google-ads-data.json    (spend, CPA, conversions, ROAS by campaign)
- state/ahrefs-data.json        (domain rating, organic keywords, organic value)
- state/apify-data.json         (local pack presence, Maps ratings)

Output a structured markdown performance report covering:
1. KPI DASHBOARD — Full table: metric | this week | last week | target | RAG status (🔴🟡🟢)
   Include: sessions, conversions, organic clicks, avg position, ad spend, CPA, organic value ($)
2. ORGANIC vs PAID RATIO — is SEO replacing Google Ads? Trend direction?
3. ORGANIC VALUE — \$ equivalent traffic value this week vs last week
4. WINS THIS WEEK — what worked well (specific, data-backed)
5. ISSUES THIS WEEK — what needs attention (specific, data-backed)
6. BUDGET RECOMMENDATION — based on organic coverage, what ad spend is still needed?
7. FORECAST — if current SEO trajectory continues, when does organic cover X% of paid traffic?

Be precise. Every number must come from the data files.
Save to: outputs/research/performance-week-$DATE.md" \
"$OUTPUTS/research/performance-week-$DATE.md"

# ── Agent 5: SEO Agent (primary growth driver) ──
log "Agent 5/9 — SEO Agent"
run_agent "seo-agent" \
"You are the CB247 SEO Agent. Today is $DATE. SEO is the PRIMARY growth driver — the goal
is to grow organic search and REDUCE Google Ads spend by replacing paid traffic with organic.

Read these files:
- state/ahrefs-data.json        (MAIN: rankings, WoW changes, keyword gap, organic value,
                                  broken backlinks, target keyword tracker)
- state/gsc-data.json           (clicks, impressions, CTR, avg position by query/page)
- state/apify-data.json         (SERP local pack presence, competitor rankings)
- state/google-trends.json      (trending topics Perth/WA)
- outputs/research/performance-week-$DATE.md

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
"$OUTPUTS/seo/weekly-seo-brief-$DATE.md"

# ── Agent 6: Competitor Spy ──
log "Agent 6/9 — Competitor Spy"
run_agent "competitor-spy" \
"You are the CB247 Competitor Spy Agent. Today is $DATE.

Read these files:
- state/ahrefs-data.json        (keyword gap vs Revo + Anytime, their rankings)
- state/apify-data.json         (Maps ratings/reviews, SERP positions, local pack)
- state/fb-ads-intel.json       (Revo + Anytime + Snap active Facebook ads)
- outputs/research/weekly-research-$DATE.md

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
"$OUTPUTS/research/competitor-weekly-$DATE.md"

# ── Agent 7: Paid Ads ──
log "Agent 7/9 — Paid Ads Agent"
run_agent "paid-ads" \
"You are the CB247 Paid Ads Agent. Today is $DATE.
Primary directive: REDUCE Google Ads spend as SEO takes over. Every dollar saved on ads
that are now covered by organic is a win.

Read these files:
- state/google-ads-data.json    (campaigns, spend, CPA, conversions by keyword/campaign)
- state/ahrefs-data.json        (target keyword tracker — which KWs we rank #1-3 organically)
- outputs/seo/weekly-seo-brief-$DATE.md    (Google Ads offset recommendations)
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
"$OUTPUTS/research/paid-ads-weekly-$DATE.md"

# ── Agent 8: Content Agent ──
log "Agent 8/9 — Content Agent"
run_agent "content-agent" \
"You are the CB247 Content Agent. Today is $DATE.
Generate a full week of READY-TO-PUBLISH content — the team should be able to copy-paste.
Content is SEO-led, ICP-driven, and informed by viral trends.

Read these files:
- outputs/seo/weekly-seo-brief-$DATE.md          (keyword briefs, ranking data)
- outputs/research/content-intel-$DATE.md         (viral hooks, formats, audio)
- outputs/research/audience-weekly-$DATE.md       (ICP language, tone, pain points)
- outputs/research/competitor-weekly-$DATE.md     (competitor gaps to exploit)
- context/brand-voice.md                          (CB247 tone and voice rules)

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
"$OUTPUTS/content/weekly-content-$DATE.md"

# ── Agent 9: Strategist ──
log "Agent 9/9 — Strategist"
run_agent "strategist" \
"You are the CB247 Marketing Strategist. Today is $DATE.
Synthesise ALL 8 agent outputs into ONE executive strategy document.
This is the single source of truth Tia reviews before anything goes to the team.

Read ALL of these:
- outputs/research/weekly-research-$DATE.md
- outputs/research/audience-weekly-$DATE.md
- outputs/research/content-intel-$DATE.md
- outputs/research/performance-week-$DATE.md
- outputs/seo/weekly-seo-brief-$DATE.md
- outputs/research/competitor-weekly-$DATE.md
- outputs/research/paid-ads-weekly-$DATE.md
- outputs/content/weekly-content-$DATE.md

Output a concise executive strategy document covering:
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
"$OUTPUTS/blueprints/weekly-strategy-$DATE.md"

log "Phase 2 complete — all 9 agents run."


# ══════════════════════════════════════════════════════════════════
# PHASE 3 — GENERATE OUTPUTS
# ══════════════════════════════════════════════════════════════════
log ""
log "─── PHASE 3: GENERATING OUTPUTS ───"

log "Step 3a — Generating HTML weekly report..."
"$PYTHON" "$BASE_DIR/scripts/bake-weekly-report.py" >> "$LOG" 2>&1 \
    || fail "bake-weekly-report.py had issues"

log "Step 3b — Rebuilding public dashboard..."
"$PYTHON" "$BASE_DIR/scripts/bake-public-dashboard.py" >> "$LOG" 2>&1 \
    || fail "bake-public-dashboard.py had issues"

log "Step 3c — Pushing to Notion..."
"$PYTHON" "$BASE_DIR/scripts/push_to_notion.py" >> "$LOG" 2>&1 \
    || fail "push_to_notion.py had issues"

log "Step 3d — Deploying dashboard to GitHub Pages..."
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

log "Step 4b — How to release team emails after Tia approves:"
log "    python scripts/send_team_emails.py --approve"
log "    OR per-person: python scripts/send_team_emails.py --role jane"

log ""
log "================================================================"
log "  CB247 MARKETING OS — RUN COMPLETE"
log "================================================================"
log "  ✅ Data pulled    : GA4 + GSC + Google Ads + Ahrefs + Apify"
log "  ✅ Agents run     : 9/9"
log "  ✅ Outputs baked  : HTML report + dashboard"
log "  ✅ Notion updated"
log "  ✅ Dashboard live : https://cb247agent.github.io/cb_claude/"
log "  📧 Tia notified   : OS report + approval prompt sent"
log "  ⏸  Team emails   : HELD — awaiting Tia approval"
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
