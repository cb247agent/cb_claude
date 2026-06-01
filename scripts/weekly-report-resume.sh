#!/bin/bash
# weekly-report-resume.sh — Resume pipeline from Agent 4 onwards.
# Used when the full weekly-report.sh is interrupted mid-run (e.g. rate limit).
# Skips data pull and agents 1-3 if their outputs already exist for today.

set -e
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# ── Load environment safely ──
if [ -f "$BASE_DIR/.env" ]; then
    while IFS='=' read -r key val; do
        [[ -z "$key" || "$key" =~ ^[[:space:]]*# || ! "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] && continue
        export "$key"="$val"
    done < "$BASE_DIR/.env"
fi

PYTHON="$BASE_DIR/.venv/bin/python3.13"
CLAUDE="/Users/tiachasingbetter/.local/bin/claude"
LOG="$BASE_DIR/state/weekly-report.log"
DATE=$(date '+%Y-%m-%d')
OUTPUTS="$BASE_DIR/outputs"

mkdir -p "$OUTPUTS/research" "$OUTPUTS/seo" "$OUTPUTS/content" \
         "$OUTPUTS/blueprints" "$OUTPUTS/creatives"

log()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"; }
fail() { log "ERROR: $1"; }
run_agent() {
    local name="$1"
    local prompt="$2"
    local out="$3"
    log "  → Running $name..."
    if "$CLAUDE" \
        --allowedTools "Read,Write,Bash,Glob,Grep" \
        --model "${ANTHROPIC_MODEL:-claude-sonnet-4-5}" \
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
log "  CB247 MARKETING OS — RESUME FROM AGENT 4"
log "================================================================"
cd "$BASE_DIR"

log "Skipping Phase 1 (data already pulled today)"
log "Skipping Agents 1-5 (outputs exist for $DATE)"
log ""
log "─── PHASE 2: AGENT PIPELINE (resuming at 6/9) ───"

# ── Agent 4: Performance — SKIP (already done) ──
# ── Agent 5: SEO — SKIP (already done) ──

# ── Agent 6: Competitor Spy ──
log "Agent 4/9 — Performance Agent (SKIP — already done)"
log "Agent 5/9 — SEO Agent (SKIP — already done)"
log "Agent 6/9 — Competitor Spy"
run_agent "performance" \
"You are the CB247 Performance Agent. Today is $DATE.

Read these files and synthesise a weekly performance report:
- state/ga4-data.json           (sessions, conversions, bounce rate, top pages)
- state/gsc-data.json           (organic clicks, impressions, avg position, CTR)
- state/google-ads-data.json    (spend, CPA, conversions, ROAS by campaign)
- state/ahrefs-data.json        (domain rating, organic keywords, organic value)
- state/apify-data.json         (local pack presence, Maps ratings)

Output a structured markdown performance report covering:
1. KPI DASHBOARD — Full table: metric | this week | last week | target | RAG status (🔴🟡🟢)
   Include: sessions, conversions, organic clicks, avg position, ad spend, CPA, organic value (\$)
2. ORGANIC vs PAID RATIO — is SEO replacing Google Ads? Trend direction?
3. ORGANIC VALUE — \$ equivalent traffic value this week vs last week
4. WINS THIS WEEK — what worked well (specific, data-backed)
5. ISSUES THIS WEEK — what needs attention (specific, data-backed)
6. BUDGET RECOMMENDATION — based on organic coverage, what ad spend is still needed?
7. FORECAST — if current SEO trajectory continues, when does organic cover X% of paid traffic?

Be precise. Every number must come from the data files.
Save to: outputs/research/performance-week-$DATE.md" \
"$OUTPUTS/research/performance-week-$DATE.md"

# ── Agent 5: SEO Agent ──
log "Agent 5/9 — SEO Agent"
run_agent "seo-agent" \
"You are the CB247 SEO Agent. Today is $DATE. SEO is the PRIMARY growth driver — the goal
is to grow organic search and REDUCE Google Ads spend by replacing paid traffic with organic.

Read these files:
- state/ahrefs-data.json        (rankings, WoW changes, keyword gap, organic value, backlinks)
- state/gsc-data.json           (clicks, impressions, CTR, avg position by query/page)
- state/apify-data.json         (SERP local pack presence, competitor rankings)
- state/google-trends.json      (trending topics Perth/WA — may be empty)
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
- outputs/research/weekly-research-$DATE.md

CB247 competitors: Revo Fitness (biggest threat), Anytime Fitness, Snap Fitness, Ryderwear Gym Malaga.

Output a structured markdown competitive intelligence report covering:
1. COMPETITOR MOVES THIS WEEK — ranked by threat level (🔴 high / 🟡 medium / 🟢 low)
2. GBP BATTLE TABLE — CB247 vs Revo vs Anytime: rating | reviews | photos | local pack presence
3. KEYWORD THREATS — competitors gaining positions on CB247's keywords (WoW movements)
4. AD INTEL — what competitors are spending on right now (angles, offers, CTAs)
5. OPPORTUNITIES — what competitors are ignoring that CB247 can own right now
6. STRATEGIC RECOMMENDATION — one specific counter-move CB247 should make this week

Save to: outputs/research/competitor-weekly-$DATE.md" \
"$OUTPUTS/research/competitor-weekly-$DATE.md"

# ── Agent 7: Paid Ads ──
log "Agent 7/9 — Paid Ads Agent"
run_agent "paid-ads" \
"You are the CB247 Paid Ads Agent. Today is $DATE.
Primary directive: REDUCE Google Ads spend as SEO takes over.

Read these files:
- state/google-ads-data.json    (campaigns, spend, CPA, conversions by campaign)
- state/ahrefs-data.json        (target keyword tracker — which KWs we rank organically)
- outputs/seo/weekly-seo-brief-$DATE.md
- outputs/research/audience-weekly-$DATE.md
- outputs/research/content-intel-$DATE.md

Output a structured markdown paid ads report covering:
GOOGLE ADS:
1. PAUSE IMMEDIATELY — keywords/ads where CB247 ranks organically #1–3 (specific campaign + estimated weekly saving)
2. REDUCE BUDGET — keywords where CB247 ranks #4–10 (50% budget reduction recommended)
3. KEEP RUNNING — keywords with no organic coverage
4. CUMULATIVE SAVINGS TRACKER — total saved this month vs start of programme
5. CAMPAIGN HEALTH — each active campaign: spend | CPA | conversions | recommendation

META ADS (prepared for reinstatement):
6. AUDIENCE TARGETING — 3 audience segments from Audience Intel brief
7. CREATIVE BRIEF — top 3 ad angles from Content Intel (hook + body + CTA)
8. BUDGET SPLIT — recommended spend by ICP when account reinstates

Save to: outputs/research/paid-ads-weekly-$DATE.md" \
"$OUTPUTS/research/paid-ads-weekly-$DATE.md"

# ── Agent 8: Content Agent ──
log "Agent 8/9 — Content Agent"
run_agent "content-agent" \
"You are the CB247 Content Agent. Today is $DATE.
Generate a full week of READY-TO-PUBLISH content — the team should be able to copy-paste.

Read these files:
- outputs/seo/weekly-seo-brief-$DATE.md
- outputs/research/content-intel-$DATE.md
- outputs/research/audience-weekly-$DATE.md
- outputs/research/competitor-weekly-$DATE.md
- outputs/research/weekly-research-$DATE.md
- context/brand-voice.md
- context/seasonal-calendar.md

CB247: AlwaysBetter. Teal. \$11.95/week. Malaga + Ellenbrook. No lock-in.
Services: 24/7 gym, Reformer Pilates, Sauna, Ice Bath, Kids Hub, CrossFit, Spin, Yoga, PT, FIFO freeze.

Generate ALL of the following — complete, copy-paste ready:

1. GBP POSTS (4 posts — keyword-rich, one per Tuesday for a month)
2. BLOG DRAFTS (2 drafts — from SEO content briefs)
3. SOCIAL POSTS (5 posts — Instagram/TikTok, with viral hooks)
4. REEL SCRIPTS (2 scripts — 30 sec + 45 sec)
5. REVIEW RESPONSE TEMPLATES (5 templates — for Joanne/front desk)
6. META AD COPY (3 variations — for when account reinstates)

Save EVERYTHING to: outputs/content/weekly-content-$DATE.md" \
"$OUTPUTS/content/weekly-content-$DATE.md"

# ── Agent 9: Strategist ──
log "Agent 9/9 — Strategist"
run_agent "strategist" \
"You are the CB247 Marketing Strategist. Today is $DATE.
Synthesise ALL agent outputs into ONE executive strategy document for Tia.

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

Output a concise executive strategy document:
0. SEASONAL STATUS — Active campaign now. What's within 21 days. What needs planning in 60 days.

1. WEEKLY SCORECARD
   - SEO Health Score: X/100
   - Organic Traffic Value: \$X/week (WoW change)
   - Google Ads Saved (cumulative): \$X
   - Organic vs Paid ratio: X% organic
   - GBP Rating: X.X ⭐ (X reviews)

2. TOP 5 PRIORITIES THIS WEEK — ranked by revenue/growth impact
   Each: what | why (data reason) | who owns it | deadline

3. DECISIONS NEEDED FROM TIA — anything requiring approval or direction

4. TEAM SUMMARY (one line per person):
   Ange | Jane | John | Mark | Agust & Ivan | Shauna | Joanne

5. WEEKLY NARRATIVE — 3 sentences: where we are, what moved, what matters most

Save to: outputs/blueprints/weekly-strategy-$DATE.md" \
"$OUTPUTS/blueprints/weekly-strategy-$DATE.md"

log "Phase 2 complete — agents 4-9 done."


# ══════════════════════════════════════════════════════════════════
# PHASE 3 — GENERATE OUTPUTS
# ══════════════════════════════════════════════════════════════════
log ""
log "─── PHASE 3: GENERATING OUTPUTS ───"

log "Step 3a — Generating HTML weekly report..."
"$PYTHON" "$BASE_DIR/scripts/bake-weekly-report.py" >> "$LOG" 2>&1 \
    || fail "bake-weekly-report.py had issues"

log "Step 3b — Rebuilding Marketing OS dashboard..."
"$PYTHON" "$BASE_DIR/scripts/bake-public-dashboard.py" >> "$LOG" 2>&1 \
    || fail "bake-public-dashboard.py had issues"

log "Step 3c — Deploying dashboard to GitHub Pages..."
bash "$BASE_DIR/scripts/deploy-dashboard.sh" >> "$LOG" 2>&1 \
    || fail "deploy-dashboard.sh had issues"

log "Phase 3 complete."


# ══════════════════════════════════════════════════════════════════
# PHASE 4 — EMAIL TIA
# ══════════════════════════════════════════════════════════════════
log ""
log "─── PHASE 4: SENDING TIA'S OS REPORT ───"

"$PYTHON" "$BASE_DIR/scripts/send_weekly_report.py" >> "$LOG" 2>&1 \
    || fail "Tia OS report email had issues"

log ""
log "================================================================"
log "  CB247 MARKETING OS — RESUME COMPLETE"
log "================================================================"
log "  ✅ Agents 4-9 complete"
log "  ✅ Dashboard live : https://cb247agent.github.io/cb_claude/"
log "  📧 Tia notified   : OS report + approval prompt sent"
log "  ⏸  Team emails   : HELD — awaiting Tia approval"
log "================================================================"
