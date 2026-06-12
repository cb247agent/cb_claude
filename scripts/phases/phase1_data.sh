#!/bin/bash
# phase1_data.sh — DATA PULL + EMITTERS + SYNC + BRIEFS + QA + VISUAL (~25 min)
#
# This is the BIG phase. It runs every data source pull (GA4, GSC, Ads,
# Ahrefs, Apify, site crawl, Metricool, GBP, Membership), every emitter
# (Meta, Google, GBP, Social, Membership, Opportunity, Attribution, Promo
# Concept), the SEO Strategist LLM, normalisation, extraction, Supabase
# sync, brief generation, blog-draft index injection, the QA Agent, and
# visual regression — in that order.
#
# Why all in one phase: each step depends on the previous (sync needs
# emitter output, briefs need sync output, QA needs everything synced,
# visual regression needs the deployed dashboard). Tightly coupled.
#
# Sourced + run from scripts/weekly-report.sh.

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

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
# DISABLED 12 Jun 2026 (Option C #3 second channel, Tia direction):
# The rule-based meta_emitter.py only saw ad-level CTR + spend thresholds.
# It missed strategic plays: creative fatigue patterns (14d CTR decay),
# audience overlap (two ad sets bidding against each other), format-mix
# imbalance (account leans static when reels have 2x CTR in fitness),
# competitor offer response, and organic-paid handoff (when IG is hot,
# reduce retargeting). Replaced by agents/meta-strategist.yml — runs in
# Step 1h0meta below, output extracted by Step 1h'''''''''' downstream.
# Re-enable this line if the strategist is down for an extended period.
# "$PYTHON" "$BASE_DIR/scripts/work_queue/meta_emitter.py" >> "$LOG" 2>&1 \
#     || log "  ⚠️  Meta emitter had issues — check $LOG"
log "  ⏭️  Rule-based Meta emitter disabled — strategist agent owns Meta action emission (Step 1h0meta)"

log "Step 1h'' — Emit Work Queue actions (Google Ads)..."
# DISABLED 12 Jun 2026 (Option C #3 build, Tia direction):
# The rule-based google_ads_emitter.py only saw campaign-level CPA + spend
# thresholds. It missed the strategic plays: paid→organic cannibalisation
# (where we rank #1-3 organically, paid clicks are wasted), Quality Score
# breakdowns, search-term intent mismatches, competitor auction movement.
# Replaced by agents/google-ads-strategist.yml — runs in Step 1h0gads
# below, output extracted by Step 1h'''''''''' (extract_agent_actions).
# Re-enable this line if the strategist is down for an extended period.
# "$PYTHON" "$BASE_DIR/scripts/work_queue/google_ads_emitter.py" >> "$LOG" 2>&1 \
#     || log "  ⚠️  Google Ads emitter had issues — check $LOG"
log "  ⏭️  Rule-based Google Ads emitter disabled — strategist agent owns Google Ads action emission (Step 1h0gads)"

log "Step 1h''' — Emit Work Queue actions (GBP)..."
"$PYTHON" "$BASE_DIR/scripts/work_queue/gbp_emitter.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  GBP emitter had issues — check $LOG"

log "Step 1h'''' — Organic Social: rule emitter DISABLED 12 Jun 2026 — replaced by LLM strategist below"
# Rule-based social_emitter mechanically emitted one action per Apify
# hashtag + one per top viral post (noisy). Replaced by
# agents/social-strategist.yml which produces 4-7 archetyped strategic
# moves per week instead. See Step 1h0social.
# "$PYTHON" "$BASE_DIR/scripts/work_queue/social_emitter.py" >> "$LOG" 2>&1 \
#     || log "  ⚠️  Social emitter had issues — check $LOG"

log "Step 1h''''' — Membership: rule emitter DISABLED 12 Jun 2026 — replaced by LLM strategist below"
# Rule-based membership_emitter saw only save-call queue size + 'not using
# enough' counts. Replaced by agents/membership-strategist.yml which reads
# the FULL retention picture (capture-rate, addon uptake, reactivation,
# promo attribution, per-club cancel reasons). See Step 1h0mem.
# "$PYTHON" "$BASE_DIR/scripts/work_queue/membership_emitter.py" >> "$LOG" 2>&1 \
#     || log "  ⚠️  Membership emitter had issues — check $LOG"

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

# ── Step 1h0gads — Google Ads Strategist (LLM, replaces rule-based google_ads_emitter) ──
# Shipped 12 Jun 2026 as Option C #3. Reads campaign performance + search
# terms + Quality Score breakdowns + organic ranking overlap + competitor
# auction insights. Outputs strategic Ops actions (Pause/Scale/Optimise/
# Add negative). Title verbs are Ops-classified so they land in the Google
# Ads page's Operational Prioritised List.
log "Step 1h0gads — Google Ads Strategist (LLM, replaces rule-based emitter)..."
mkdir -p "$OUTPUTS/google-ads"
run_agent "google-ads-strategist" \
"You are the CB247 Google Ads Strategist. Today is $DATE.

Read:
- state/google-ads-data.json   (totals, campaigns[16], search_terms[86], quality_scores[43], conversion_actions, auction_insights)
- state/gsc-data.json           (organic top_queries — to find paid↔organic overlap)
- state/apify-data.json         (competitor SERP + Google Ads scrapes)
- context/brand-voice.md        (tone)
- context/seo-targets-cb247.md  (which keywords we care about strategically)

Workflow (do all six steps before writing):
1. ACCOUNT SNAPSHOT — note totals (weekly spend, CPL, conversions) +
   per-location split (Malaga vs Ellenbrook). Flag if total spend
   exceeds \$800/wk ceiling.
2. ORGANIC OVERLAP — for each high-spend Google Ads keyword, check GSC
   organic position. Flag candidates where:
     · Organic rank #1-3  → P1 PAUSE/REDUCE (paid is cannibalising)
     · Rank #4-10         → P2 OPTIMISE landing page (compounds with seo-strategist)
     · Rank 11+ / unranked → keep paid, monitor CPA
3. QUALITY SCORE — for each keyword with QS < 6, identify the weakest
   sub-score (ad_relevance / lp_experience / expected_ctr) and the
   specific fix.
4. SEARCH-TERM AUDIT — find high-spend search terms not matching CB247
   services (negatives), strong-intent local terms not covered
   (new exact-match keywords), and competitor-comparison search terms.
5. COMPETITIVE CHECK — auction_insights + Apify competitor data. Has
   Revo/Anytime/Snap entered any of our auctions with stronger offers?
6. STRATEGIC DECISIONS — for each insight, choose ONE archetype:
   (a) PAUSE / REDUCE   — title 'Pause [X]' or 'Reduce bid on [X]'
   (b) SCALE            — title 'Scale [X]: +\$Y/wk'
   (c) OPTIMISE         — title 'Optimise [X]: [specific edit]'
   (d) ADD NEG/KEYWORD  — title 'Add negative keyword: [term]'

Output markdown to stdout with these sections:
  # CB247 Google Ads Strategist — $DATE
  ## Account Snapshot          (paragraph)
  ## Organic Overlap           (table — keyword | CPC | organic rank | recommendation)
  ## Quality Score Issues      (table — keyword | QS | weakest sub | fix)
  ## Search-Term Insights      (bullets — negatives, exact-match opportunities, comparisons)
  ## Competitive Note          (paragraph)
  ## Considered but Skipped    (bullets)
  ## Proposed Actions

  \\\`\\\`\\\`json proposed_actions
  [ ... 6-10 actions per agents/AGENT_ACTION_CONTRACT.md ... ]
  \\\`\\\`\\\`

JSON RULES (CRITICAL):
- category: 'google-ads' always
- title MUST start with an Ops verb (Pause/Scale/Optimise/Add/Lift/Reduce/
  Switch) so the dashboard classifier puts it in the Ops list
- owner: 'Tia' + owner_role: 'OS Owner / Paid Ads' for budget/bid changes
- owner: 'John' + owner_role: 'SEO Specialist' ONLY for landing-page edits
- priority: P1 cost-saving / cannibalisation, P2 QS fix, P3 search-term hygiene
- effort_hours: 0.25 budget/bid/negative · 0.5-1 creative/landing-page
- data_quality: 'high' if Google Ads + GSC both confirm, else 'medium'
- projected_kpis: at least one. Preferred metrics:
    google_ads_cpa, google_ads_ctr, google_ads_cpc, google_ads_spend_weekly,
    google_ads_conversions_weekly, google_ads_clicks_weekly,
    ads_spend_saved_monthly (for paid→organic switches)
- description: 200-400 chars. Include campaign/keyword name, baseline +
  target metric, weekly \$ impact, and the SPECIFIC action (exact term,
  exact budget delta).

CRITICAL OUTPUT INSTRUCTION: Do NOT use the Write tool. OUTPUT the full
markdown directly to stdout. The bash wrapper saves your stdout to
outputs/google-ads/google-ads-strategist-$DATE.md." \
"$OUTPUTS/google-ads/google-ads-strategist-$DATE.md" \
"Read(state/google-ads-data.json),Read(state/gsc-data.json),Read(state/apify-data.json),Read(context/brand-voice.md),Read(context/seo-targets-cb247.md),Read(context/utm-convention.md)" \
"$MODEL_OPUS"

# ── Step 1h0meta — Meta Strategist (LLM, replaces rule-based meta_emitter) ──
# Shipped 12 Jun 2026 as Option C #3 second channel. Reads ad-level
# performance + 6-week history + organic Metricool data + competitor FB
# ads. Outputs strategic Ops actions (Pause/Scale/Refresh/Test). Title
# verbs Ops-classify so they land in Meta Ads Operational Prioritised List.
log "Step 1h0meta — Meta Strategist (LLM, replaces rule-based emitter)..."
mkdir -p "$OUTPUTS/meta-ads"
run_agent "meta-strategist" \
"You are the CB247 Meta Strategist. Today is $DATE.

Read:
- state/ads-data.json           (meta_ads block — 6 weeks of history, ads list per week)
- state/metricool-data.json     (organic FB + IG performance, WoW deltas)
- state/apify-data.json         (facebook_ads — competitor FB Ad Library)
- context/brand-voice.md        (tone, USPs, voice rules)
- context/seasonal-calendar.md  (active campaigns)

Workflow (do all six steps before writing):
1. ACCOUNT SNAPSHOT — latest week vs prior: spend, CTR, CPC, reach,
   per-location split. Flag if total > \$600 ceiling.
2. CREATIVE FATIGUE — for each ad, compare CTR + CPC over 14d:
     · CTR drop > 25% → REFRESH (creative swap, specify new angle)
     · CPC rise > 30% flat CTR → AUDIENCE FATIGUE (expand/rotate)
     · Spend dropping but reach holding → algo throttling (stale)
3. FORMAT MIX — infer creative type from ad name (Reel/Static/Carousel/
   Video). Compare format CTR. Propose scaling winners + retiring
   underperformers. If a format hasn't been tested in 30d, A/B TEST.
4. ORGANIC-PAID HANDOFF — Metricool fb + ig blocks:
     · IG/FB WoW UP > 15% → REDUCE retargeting OR shift to prospecting
     · FB flat + paid CTR declining → defend creative + audience
5. COMPETITOR OFFER CHECK — facebook_ads. If Revo/Anytime/Snap/Ryderwear
   running a CB247-relevant offer, propose either defensive counter-ad
   or differentiator-led ad. NEVER name competitors in proposed ad copy.
6. DECISIONS:
   (a) PAUSE   — bleeding spend (CTR < 1.0% AND > 14d running)
                  OR duplicate audiences
   (b) SCALE   — CTR > 2x avg + spend cap hit. Lift budget or duplicate
   (c) REFRESH — fatigue detected. Specify new angle/hook/format
   (d) TEST    — net-new ad/format/audience experiment

Output markdown to stdout with sections:
  # CB247 Meta Strategist — $DATE
  ## Account Snapshot
  ## Creative Fatigue          (table — ad/loc/weeks_running/CTR/CTR_chg/rec)
  ## Format Mix                (table or paragraph)
  ## Organic-Paid Handoff      (paragraph re Metricool trends)
  ## Competitor Offer Watch    (paragraph, never name competitors in ad copy)
  ## Considered but Skipped    (bullets)
  ## Proposed Actions

  Then a BARE JSON ARRAY [...] — NOT wrapped in {\"proposed_actions\": ...}.

JSON RULES (CRITICAL):
- category: 'meta-ads' always. Do NOT also set source_page (the extractor
  derives it from category — your source_page would get overridden anyway).
- title MUST start with an Ops verb (Pause/Scale/Refresh/Test/Add/Lift/
  Reduce/Swap) so the dashboard classifier sends to Ops list.
- owner: 'Tia' + 'OS Owner / Paid Ads' for budget/state moves
- owner: 'Shauna' + 'Assets Creator' if a new photo/video is needed
- priority: P1 cost-saving / fatigue, P2 scale / format test, P3 hygiene
- effort_hours: 0.25 budget/state · 0.5 audience · 1-2 new creative
- data_quality: 'high' if Meta+Metricool confirm, else 'medium'
- projected_kpis: list of {metric, baseline, target, measurement_window_days, confidence='high'/'medium'/'low'}
  metrics: meta_ctr, meta_cpc, meta_cpm, meta_cpa, meta_results_weekly,
           meta_ad_clicks_weekly, meta_ad_reach_weekly
- description: 200-400 chars. Include ad name + location + baseline metric
  + target + SPECIFIC angle/budget/audience change.

CRITICAL OUTPUT INSTRUCTION: Do NOT use the Write tool. OUTPUT the full
markdown directly to stdout. The bash wrapper saves your stdout to
outputs/meta-ads/meta-strategist-$DATE.md." \
"$OUTPUTS/meta-ads/meta-strategist-$DATE.md" \
"Read(state/ads-data.json),Read(state/metricool-data.json),Read(state/apify-data.json),Read(context/brand-voice.md),Read(context/seasonal-calendar.md),Read(context/utm-convention.md)" \
"$MODEL_OPUS"

# ── Step 1h0mem — Membership Strategist (LLM · revenue side) ─────────────
# Option C #4 (12 Jun 2026 — Tia direction). Replaces rule-based
# membership_emitter.py which only saw save-call queue size + 'not using
# enough' counts. The LLM strategist sees the FULL retention picture and
# produces archetyped actions: SAVE / DEFEND / CONVERT / UPSELL / REACTIVATE.
log "Step 1h0mem — Membership Strategist (LLM, replaces rule-based emitter)..."
mkdir -p "$OUTPUTS/membership"
run_agent "membership-strategist" \
"You are the CB247 Membership Strategist. Today is $DATE. Membership
is the revenue spine — net new members minus churn is the bottom line.

Read:
- state/membership-data.json    (this week PGM + Cleverwaiver per-club,
                                 cancel reasons, addon active counts,
                                 suspended pool, promo tracking)
- state/membership-history.json (prior weeks for trend computation)
- state/promo-pipeline.json     (active promo concepts to attribute to)
- state/work-queue.json         (past membership actions — avoid duplicate emits)
- context/brand-voice.md        (tone, USPs, compliance lines)
- context/seasonal-calendar.md  (winter retention, FIFO swap cycles)

Workflow (do all six steps before writing):
1. WEEKLY SNAPSHOT — total signups vs ended vs suspended (unique members
   only — use summary.unique_base). Per-club split. NET change. WoW trend.
   Flag NEGATIVE 2 weeks in a row as urgent retention crisis.
2. CANCEL REASON DEEP-DIVE — summary.cancel_reasons_pgm vs
   submitted_cancellation_truth (Cleverwaiver). For each top reason:
     EndOfContract / Relocating / Not Using enough / TurnedOff / Switched.
     What's getting better / worse vs last week.
3. CAPTURE RATE AUDIT — submitted_cancellation_truth.capture_rate_pct
   per club vs 70% target. If a club is below, propose a SAVE action
   targeting that club specifically (not generic).
4. ADDON UPTAKE — contracts.addon_active per club. Compute % of base.
   If Recovery < 8% in winter season, UPSELL. If Reformer < 8%, UPSELL
   via Meta paid (Joanne).
5. REACTIVATION OPPORTUNITY — suspended contracts pool. Recent vs aging.
   If aging out without return signal, REACTIVATE archetype (Angela copy
   + Joanne send).
6. PROMO ATTRIBUTION — promo_tracking active promos. Accelerating
   promos → propose EXTEND (handoff to Tia/Joanne for budget lift).
   Decelerating → REFRESH angle.

Decision archetypes — one per action:
  (a) SAVE      — fix capture rate, reception training, save-call refresh
  (b) DEFEND    — outbound campaign rebutting a specific cancel reason
  (c) CONVERT   — extend/accelerate a winning promo
  (d) UPSELL    — add-on uptake push (Recovery / Reformer / ChasingRX)
  (e) REACTIVATE — nudge suspended pool back

Output markdown to stdout with sections:
  # CB247 Membership Strategist — $DATE
  ## This Week — Net Movement
  ## Cancel Reason Deep-Dive       (table — reason/count/per-club/trend/recoverable)
  ## Capture Rate Audit            (paragraph)
  ## Add-on Uptake                 (table)
  ## Reactivation Opportunity      (paragraph)
  ## Promo Attribution             (paragraph)
  ## Considered but Skipped        (bullets)
  ## Proposed Actions

  Then a BARE JSON ARRAY [...] of 5-9 actions.

JSON RULES (CRITICAL):
- category: 'membership' always.
- title MUST start with an Ops verb (Run/Brief/Refresh/Push/Extend/Reactivate/Train).
- owner + owner_role MUST come from this exact roster:
    'Tia'    + 'OS Owner' or 'OS Owner / Paid Ads' — system/data + Google Ads paid
    'Joanne' + 'Meta Ads Specialist' — Meta paid retention/acquisition
    'Joanne' + 'Organic Social' — organic posts about save offers
    'Angela' + 'Brand Manager' — save-call training, retention copy, reception scripts
  Denver is NEVER an owner. NEVER use bare role labels (no 'Brand Manager'
  alone).
- priority: P1 if revenue-immediate, P2 trend, P3 cosmetic.
- effort_hours: 0.5 budget · 1-2 copy · 3+ training rollout.
- data_quality: 'high' if PGM+Cleverwaiver confirm, else 'medium'.
- projected_kpis: list of {metric, baseline, target, measurement_window_days,
  confidence}. Allowed metrics ONLY (Projection Guard enforces):
    membership_signups_weekly · membership_cancellations_weekly ·
    membership_future_cancellations · membership_addon_active_count ·
    qualitative_assessment
  Realistic targets, 14d window for tactical, 28d for training.
- description: 200-400 chars. Specific club, baseline number, target,
  cancel reason or addon being addressed, SPECIFIC action.

CRITICAL OUTPUT INSTRUCTION: Do NOT use the Write tool. OUTPUT the full
markdown directly to stdout. The bash wrapper saves your stdout to
outputs/membership/membership-strategist-$DATE.md." \
"$OUTPUTS/membership/membership-strategist-$DATE.md" \
"Read(state/membership-data.json),Read(state/membership-history.json),Read(state/promo-pipeline.json),Read(state/work-queue.json),Read(context/brand-voice.md),Read(context/seasonal-calendar.md)" \
"$MODEL_OPUS"

# ── Step 1h0social — Social Strategist (LLM · organic channels) ──────────
# Option C #5 (12 Jun 2026 — Tia direction). Replaces noisy rule-based
# social_emitter.py which mechanically emitted one action per hashtag.
# This strategist produces 4-7 archetyped strategic moves per week:
# TREND-RIDE / AMPLIFY / GAP-FILL / FORMAT-MIX / REDUCE / SHOOT-DEPEND.
log "Step 1h0social — Social Strategist (LLM, replaces rule-based emitter)..."
mkdir -p "$OUTPUTS/organic-social"
run_agent "social-strategist" \
"You are the CB247 Social Strategist. Today is $DATE. Organic social is
CB247's primary brand-awareness lever — IG Reels especially. Joanne owns
all posting/scheduling; Shauna only if a NEW shoot is required.

Read:
- state/apify-data.json         (hashtags + viral posts + competitor IG)
- state/metricool-data.json     (CB247 fb + ig own-performance)
- state/work-queue.json         (past social actions — avoid duplicate emits)
- context/brand-voice.md
- context/seasonal-calendar.md

Workflow (do all six steps before writing):
1. CB247 OWN PERFORMANCE — Metricool ig + fb blocks. Posts this week,
   reach + engagement + WoW deltas, engagement rate. Format wins.
2. HASHTAG RELEVANCE FILTER — Apify trending_hashtags. Reject generic
   (#fitness #gym alone). Prioritise local-SEO (#malagagym
   #ellenbrookgym #perthgym) and niche-aligned (#coldplunge #icebath
   #contrasttherapy — CB247 has those facilities, direct match).
   Output: 2-4 hashtags worth a TREND-RIDE this week (NOT 8).
3. VIRAL POST ANGLE MINING — Apify top_posts. Extract WINNING ANGLE
   (POV / transformation / day-in-life), match to a CB247 scene.
   Output: 1-2 worth an AMPLIFY action.
4. COMPETITOR WATCH — Apify instagram_profiles.competitors. Follower
   delta, posting frequency, standout posts. If a competitor has a
   viral hit CB247 has a better asset for → GAP-FILL action. NEVER
   name competitors in proposed copy.
5. FACEBOOK ORGANIC REVIEW — If FB engagement rate < 1.0% AND IG is
   healthy, propose REDUCE FB to 1-2 posts/wk (minimum for GBP/SEO
   signal). Don't close FB entirely.
6. DECISIONS — pick ONE archetype per action, AIM for 4-7 actions
   total (not one per hashtag).

Decision archetypes:
  (a) TREND-RIDE — 1-2 high-relevance hashtags, CB247-branded Reel
  (b) AMPLIFY    — recreate winning viral angle with CB247 scene
  (c) GAP-FILL   — counter competitor viral hit with CB247 differentiator
                   (NEVER name competitor in copy)
  (d) FORMAT-MIX — shift posting mix to winning format (Reels usually win)
  (e) REDUCE     — cut output on dying channel/format
  (f) SHOOT-DEPEND — Reel needs NEW capture (Shauna owns, post queued for Joanne)

Output markdown to stdout with sections:
  # CB247 Social Strategist — $DATE
  ## CB247 Own Performance
  ## Viral Hashtag Shortlist     (table — hashtag/count/relevance/action)
  ## Viral Post Angles           (bullets — angle + CB247 scene)
  ## Competitor Watch            (paragraph, no names in proposed copy)
  ## FB Organic Health           (paragraph + recommendation)
  ## Considered but Skipped      (bullets with reason)
  ## Proposed Actions

  Then a BARE JSON ARRAY [...] of 4-7 actions.

JSON RULES (CRITICAL):
- category: 'organic-social' always.
- title MUST start with an Ops verb (Post / Adapt / Shift / Reduce /
  Counter / Test / Schedule).
- owner + owner_role MUST come from this exact roster:
    'Joanne' + 'Organic Social'       — DEFAULT for all posting/scheduling
    'Joanne' + 'Meta Ads Specialist'  — only if action crosses into paid Meta
    'Angela' + 'Brand Manager'        — concept review on sensitive content
    'Shauna' + 'Asset Creator'        — ONLY when new shoot capture needed
  NEVER 'Content', 'Tia', or 'Reception' for social actions.
- priority: P1 if viral window closing <7d, P2 trend-rides, P3 cadence.
- effort_hours: 0.25 cadence · 1-2 reuse-asset · 3 shoot-dependent.
- data_quality: 'high' if Apify+Metricool confirm, else 'medium'.
- projected_kpis: at least one. Allowed metrics ONLY (Guard enforces):
    qualitative_assessment (default — organic mostly qualitative).
  Use measurement_window_days=14.
- description: 200-400 chars. Specific hashtag/angle/scene, which asset
  (existing or shoot needed), brand-compliance reminder, verdict
  criterion (e.g. 'beat weekly median engagement on IG').

CRITICAL OUTPUT INSTRUCTION: Do NOT use the Write tool. OUTPUT the full
markdown directly to stdout. The bash wrapper saves your stdout to
outputs/organic-social/social-strategist-$DATE.md." \
"$OUTPUTS/organic-social/social-strategist-$DATE.md" \
"Read(state/apify-data.json),Read(state/metricool-data.json),Read(state/work-queue.json),Read(context/brand-voice.md),Read(context/seasonal-calendar.md)" \
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

# ── Step 1i-bis: Playbook writer + HTML renderer (12 Jun 2026) ──────────
# Angela can't draft .md playbooks and can't open them either. When the
# membership-strategist proposes "Refresh Unsure-objection playbook · save
# to outputs/playbooks/X.md", the playbook-writer agent generates the
# content (using Don't Quit Winter playbook as the quality bar) and
# render_playbook_html.py converts it to a CB247-styled HTML page Angela
# can view via the brief's "View the playbook" button.
log ""
log "─── Step 1i-bis: PLAYBOOK WRITER (auto-generate .md content) ───"
mkdir -p "$OUTPUTS/playbooks"
run_agent "playbook-writer" \
"You are the CB247 Playbook Writer. Today is $DATE.

Read state/work-queue.json. Find every action whose description references
'outputs/playbooks/{slug}.md'. For each candidate where the target file
does NOT already exist (idempotent — never overwrite human edits):

1. Read the gold-standard template: outputs/playbooks/dont-quit-winter-save-call.md
2. Read context/brand-voice.md + context/seasonal-calendar.md
3. Write a complete playbook to outputs/playbooks/{slug}.md using the
   structure: Top matter · The Offer (blockquote) · Eligibility ·
   Scripts in fenced code blocks · Do / Don't pairs · PGM tracking +
   Day-14 verdict · Footer.

Length: 1200-2200 words.

Brand-voice CRITICAL:
- \$11.95/wk price anchor
- CB247 differentiators: Kids Hub · 24/7 access · Traditional Sauna +
  Ice Bath · FIFO-friendly freeze
- NEVER name competitors (Revo / Anytime / Snap / Ryderwear)
- NEVER 'only gym with' (ACL risk — Ryderwear has sauna + reformer)
- NEVER therapeutic claims (heals / cures / treats / burns fat — TGA)
- Recovery + Reformer + ChasingRX are PAID add-ons, not bundled in \$11.95/wk

After writing all playbooks, output a SHORT markdown summary to stdout
listing each playbook written + skipped + any compliance flags.

CRITICAL OUTPUT INSTRUCTION: Use the Write tool to save each playbook
to outputs/playbooks/{slug}.md. Then output the markdown summary to
stdout. The bash wrapper saves your stdout to
outputs/playbooks/playbook-writer-\$DATE.md." \
"$OUTPUTS/playbooks/playbook-writer-$DATE.md" \
"Read(state/work-queue.json),Read(context/brand-voice.md),Read(context/seasonal-calendar.md),Read(outputs/playbooks/dont-quit-winter-save-call.md),Read(outputs/playbooks/dont-quit-winter-training-brief.md),Write(outputs/playbooks/**)" \
"$MODEL_OPUS"

log "Step 1i-bis.2 — Render playbooks .md → docs/playbooks/*.html..."
"$PYTHON" "$BASE_DIR/scripts/render_playbook_html.py" >> "$LOG" 2>&1 \
    && log "  ✓ Playbook HTML rendered" \
    || log "  ⚠️  Playbook HTML render had issues — check $LOG"

# ── Step 1i-tris: Deliverable drafter (12 Jun 2026) ─────────────────────
# Tia principle: "agentic AI = ready action, not blank-page work for team."
# Every action whose title says "Draft + send EDM / SMS / social post / ad
# copy" should arrive at Angela / Joanne with the copy already written.
# This agent generates the draft .md, then render_drafts_html.py converts
# to a CB247-styled HTML page the brief links to via "View the draft" button.
log ""
log "─── Step 1i-tris: DELIVERABLE DRAFTER (EDM / SMS / social / ad copy) ───"
mkdir -p "$OUTPUTS/drafts"
run_agent "deliverable-drafter" \
"You are the CB247 Deliverable Drafter. Today is $DATE.

Tia's principle: agentic AI must produce READY DRAFTS, not blank-page work.
When a proposed action's title says 'Draft + send EDM' / 'Send SMS' / 'Post
trend-ride' / 'Refresh Meta ad copy', the team must arrive at a pre-drafted
artefact they review and approve — never write from scratch.

Read state/work-queue.json. Find every action whose title indicates a
deliverable to draft. Classify by type using these patterns (case-insensitive):

  EDM       — title matches (draft|send|write|refresh).{0,15}(edm|email)
  SMS       — title matches (draft|send|write|refresh).{0,15}(sms|text|message)
  SOCIAL    — title matches (post|trend-ride|adapt|caption).{0,40}(reel|story|instagram|tiktok|facebook|social)
  AD COPY   — title matches (refresh|test|swap|add).{0,30}(meta ad|google ad|ad copy|ad creative) AND projected_kpis has meta_* or google_ads_*

For each candidate, compute target file:
  outputs/drafts/{type-prefix}-{slug-from-title-keywords}-$DATE.md

Skip if file already exists (idempotent — keep human edits).

Read outputs/drafts/edm-kids-hub-holiday-spotlight-2026-06-12.md as the
GOLD STANDARD for EDM structure. Read context/brand-voice.md +
context/seasonal-calendar.md + context/utm-convention.md.

For each candidate, write the draft using the type-specific structure
(detailed in agents/deliverable-drafter.yml). Each draft must include:
- Top matter (audience, send window, status)
- The copy itself in fenced code blocks for easy copy-paste
- Image / video brief if visual asset needed
- Compliance check (\$11.95/wk anchor, NO competitor names, NO 'only gym
  with', NO TGA claims, paid add-ons never bundled)
- Day-14 verdict criteria
- Footer with owner / sender / QC / next step

Save each via Write tool to outputs/drafts/{slug}.md.

After all drafts written, output a SHORT markdown summary to stdout listing
generated + skipped + compliance flags + per-draft next-step recommendation.

CRITICAL: Do NOT emit a proposed_actions JSON block. This agent's product
is the draft files — downstream work is team review." \
"$OUTPUTS/drafts/deliverable-drafter-$DATE.md" \
"Read(state/work-queue.json),Read(state/promo-pipeline.json),Read(context/brand-voice.md),Read(context/seasonal-calendar.md),Read(context/utm-convention.md),Read(outputs/drafts/edm-kids-hub-holiday-spotlight-2026-06-12.md),Read(outputs/playbooks/dont-quit-winter-save-call.md),Write(outputs/drafts/**)" \
"$MODEL_OPUS"

log "Step 1i-tris.2 — Render drafts .md → docs/drafts/*.html..."
"$PYTHON" "$BASE_DIR/scripts/render_drafts_html.py" >> "$LOG" 2>&1 \
    && log "  ✓ Drafts HTML rendered" \
    || log "  ⚠️  Drafts HTML render had issues — check $LOG"

# ── Step 1j: Regenerate per-action HTML briefs (Fix 10 Jun 2026) ──
# CB247 mirror of generate_mwcc_briefs.py. The dashboard modal's "View Brief"
# link opens docs/briefs/{action_id}.html — these files must exist for every
# current Work Queue ID or the link 404s. This script reads
# state/work-queue.json + state/promo-pipeline.json and bakes one HTML brief
# per action (with parent_promo_id linkage for child items).
log "Step 1j — Regenerate per-action briefs..."
"$PYTHON" "$BASE_DIR/scripts/generate_briefs.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  Brief generation had issues — check $LOG"

# ── Step 1j-bis: Monthly shoot pack for Shauna (12 Jun 2026) ─────────────
# Shauna (CB247 Assets Creator) works ONE shoot day per month. She needs
# a single document covering all creative actions due in the next 30 days,
# bucketed by location with viral references and Higgsfield fallbacks.
#
# Trigger: only generate on first Monday of the month so we don't spam
# the asset-library directory with overwrites every weekly run. The
# generator is idempotent — safe to re-run manually mid-month if Tia
# wants a refreshed pack mid-cycle.
TODAY_DOW=$(date +%u)   # 1=Mon, 7=Sun
TODAY_DOM=$(date +%d)   # day of month
if [[ "$TODAY_DOW" == "1" && "$TODAY_DOM" -le "07" ]]; then
    log "Step 1j-bis — First Monday of month detected, generating Shauna's monthly shoot pack..."
    "$PYTHON" "$BASE_DIR/scripts/generate_monthly_shoot_pack.py" >> "$LOG" 2>&1 \
        && log "  ✓ Monthly shoot pack written to docs/asset-library/" \
        || log "  ⚠️  Monthly shoot pack generation had issues — check $LOG"
else
    log "Step 1j-bis — Skipping monthly shoot pack (only fires on first Mon of month)"
fi

# ── Step 1j-tris: Parse future-cancellations CSV → callable list (12 Jun 2026)
# Tia drops a fresh CSV at cb247-inbox/future-cancellations-YYYY-MM-DD.csv
# any time she pulls the export from PGM. This step renders the latest CSV
# into a styled docs/lists/future-cancellations-*.html and updates the
# state/future-cancellations-manifest.json so the Membership page's
# Save-call action surfaces a working link. Idempotent — re-running the
# same CSV is a no-op overwrite.
log "Step 1j-tris — Parse future-cancellations CSV (if present)..."
"$PYTHON" "$BASE_DIR/scripts/parse_future_cancellations.py" >> "$LOG" 2>&1 \
    || log "  ⚠️  Future cancellations parser had issues — check $LOG"

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
