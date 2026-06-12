#!/bin/bash
# phase2_agents.sh — 9 LLM marketing agents in sequence (~40 min).
#
# Order: research-agent → audience-intel → content-intel → performance →
# seo-agent → competitor-spy → paid-ads → content-agent → strategist.
# Each writes to outputs/<category>/<name>-$DATE.md.
#
# Failures are tracked in FAILED_AGENTS[] (set in _common.sh) — they don't
# abort the pipeline. The Phase 4 email reports any failures.
#
# Sourced + run from scripts/weekly-report.sh.

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

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
