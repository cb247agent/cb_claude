# Strategist Conversion — Path B Execution Plan

## What changed in this update (13 Jun 2026)

Original Option C draft converted 2 emitters → 2 LLM strategists. Path B
adds the missing **performance-marketer** layer: a third strategist that
reads the enriched concepts and writes full media plans Joanne / Tia can
copy-paste into Ads Manager.

Path B is the full upgrade — **3 strategists, 1 enriched schema, end-to-end ready-action**.

---

## Drafts ready for review

| File | What it replaces / adds | Cadence | Cost/run |
|---|---|---|---|
| `promo-concept-strategist.yml.draft` ✏️ updated | Replaces `scripts/work_queue/promo_concept_emitter.py` AND emits enriched fields (audience_seed, conversion_event, budget_envelope, historical_cpa_baseline, launch_window, kill_criteria, creative_hints) | Monthly (1st) | ~$3-5 |
| `campaign-launch-strategist.yml.draft` 🆕 NEW | Net-new agent — reads enriched concepts, writes full media plan to `outputs/media-plans/`, emits a single launch action to Work Queue | Per Approved concept (event-driven) | ~$2-4 |
| `opportunity-strategist.yml.draft` (unchanged) | Replaces `scripts/work_queue/opportunity_emitter.py` | Weekly (Mon) | ~$1-2 |

**Total new cost:** ~$15-25/month (vs ~$11 in original Option C).

---

## Read each draft and tell me

1. **`promo-concept-strategist`** — is the enriched schema (workflow step `enrich-for-campaign-launch`) complete? Anything in the audience/budget/kill fields I missed?
2. **`campaign-launch-strategist`** — are the Meta + Google campaign-setup structures right? Should I add anything (e.g., dynamic creative optimization, ad scheduling rules per CB247's daypart performance, lead-form follow-up sequences)?
3. **`opportunity-strategist`** — same as before. Anything missing?

---

## When approved — what I'll execute (NOT now, only after your sign-off)

### Step 1 — Move drafts into production (3 files)
```
mv outputs/strategist-drafts/promo-concept-strategist.yml.draft agents/promo-concept-strategist.yml
mv outputs/strategist-drafts/campaign-launch-strategist.yml.draft agents/campaign-launch-strategist.yml
mv outputs/strategist-drafts/opportunity-strategist.yml.draft agents/opportunity-strategist.yml
```

### Step 2 — Wire into `phase1_data.sh` + new event-driven trigger

**Weekly (phase1_data.sh — runs every Monday):**
- `opportunity-strategist` runs after `pull_google_ads + pull_gsc + pull_apify`
- Disable `scripts/work_queue/opportunity_emitter.py` (comment out)

**Monthly (phase1_data.sh — runs only on 1st of month):**
- `promo-concept-strategist` runs after `membership-strategist` (sees fresh signals)
- Disable `scripts/work_queue/promo_concept_emitter.py`

**Event-driven (new — runs when promo enters Approved stage):**
- `campaign-launch-strategist` runs from a dashboard hook OR a new daily `phase1b_promo_launch.sh` script that scans for newly-Approved concepts without a media plan and fires for each
- **Recommended:** add a new daily script `phase1b_promo_launch.sh` cron'd at 4am AWST — same pattern as existing phase scripts

### Step 3 — Output extractor changes (3 paths)

**For `promo-concept-strategist`** — outputs TWO JSON blocks (`proposed_promos` + `proposed_actions`):
- New file: `scripts/work_queue/extract_promo_strategist_output.py` (~80 lines)
- Parses both blocks, merges into `state/promo-pipeline.json` + `state/work-queue.json`
- Preserves in-flight promos past Concept stage

**For `campaign-launch-strategist`** — outputs ONE JSON block (`proposed_actions`) + writes media-plan .md files directly:
- The agent has `Write(outputs/media-plans/**)` permission — files are written during the agent run
- Existing `normalize_strategist_output.py` handles the action extraction
- New: `scripts/render_media_plan_html.py` renders `.md → .html` (same pattern as `render_playbook_html.py`) for dashboard viewing
- New: `state/media-plans-manifest.json` index for the dashboard

**For `opportunity-strategist`** — same as Option C, existing extractor handles it

### Step 4 — Brief detection update (dashboard)

The action brief renderer (`_renderProposedActionBriefHTML` in `docs/index.html`) already auto-detects:
- `outputs/playbooks/*.md` → "View the playbook" button
- `outputs/drafts/*.md` → "View the draft" button

**Add detection for `outputs/media-plans/*.md`** → "View the media plan" button. Same pattern, ~20 lines of JS.

### Step 4b — Promo approval UI (the missing trigger)

Today the Promo Pipeline modal (`openPromoDetailModal` at `docs/index.html:19942`) has NO approve button — only Close. The renderer comment at line 19873 says "Approve concepts at the Monday meeting via the View Details popup" but the button never got built. Without it, `campaign-launch-strategist` has no clean trigger because nobody can change a concept's stage from Concept → Approved without editing `state/promo-pipeline.json` by hand.

Work required (~1.5 hours):

**4b.i — Supabase table for promo state** (`db/migrations/2026-06-13-promo-pipeline-stage.sql`):
- New table `promo_pipeline_state` with columns: `id` (text PK, matches concept id), `stage` (text), `notes` (text — for rejection reasons), `updated_at` (timestamptz), `updated_by` (text)
- RLS policy: allow team role to upsert
- REPLICA IDENTITY FULL + add to realtime publication (per ENGINEERING.md pattern)

**4b.ii — Modal buttons** in `openPromoDetailModal`:
- Add a footer row with stage buttons that reflect the current stage:
  - From `Concept`: [Reject] [Approve →]
  - From `Approved`: [Send back to Concept] [Asset Shoot Scheduled →]
  - From `Asset Shoot Scheduled`: [Send back] [In Production →]
  - From `In Production`: [Send back] [Active →]
- Each button calls `setPromoStage(id, newStage)` which upserts to `promo_pipeline_state` via Supabase REST
- Optimistic UI update — modal closes, kanban re-renders with new stage

**4b.iii — Dashboard read path** (small change to `_promoData()` at line 19812):
- Merge `state/promo-pipeline.json` (the strategist output) with the live `promo_pipeline_state` Supabase rows (the team's stage overrides)
- Team's stage override always wins
- This means: strategist proposes, team approves, the merged view drives the kanban + the campaign-launch trigger

**4b.iv — Strategist trigger** (in the new `phase1b_promo_launch.sh`):
- Script queries Supabase `promo_pipeline_state` for rows where `stage IN ('Approved','Asset Shoot Scheduled')` AND no media plan exists in `outputs/media-plans/`
- For each, fires `campaign-launch-strategist` with the concept id as input
- Logs which concepts were processed to prevent re-fire on the same day

### Step 5 — Projection Guard whitelist update
`scripts/work_queue/normalize_strategist_output.py` MEASURABLE_METRICS — verify all required:

promo-concept-strategist needs:
- `membership_signups_weekly` ✓
- `membership_cancellations_weekly` ✓
- `membership_future_cancellations` ✓
- `membership_addon_active_count` ✓
- `org_social_engagement_rate` — verify
- `qualitative_assessment` ✓

campaign-launch-strategist needs:
- `meta_cpc` ✓
- `meta_ctr` ✓
- `meta_frequency` — verify (might be new — would need schema + measurement_runner extension)
- `google_ads_clicks_weekly` ✓
- `google_ads_spend_weekly` ✓
- `membership_signups_weekly` ✓
- `qualitative_assessment` ✓

opportunity-strategist needs:
- `ads_spend_saved_monthly` — verify
- `gsc_clicks_weekly` ✓
- `seo_keyword_count_ranked` — verify
- `qualitative_assessment` ✓

If any are missing, I add them to `schema.py` MEASURABLE_METRICS + extend `measurement_runner._fetch_actual` to handle them.

### Step 6 — Smoke test in dry-run mode
```bash
.venv/bin/python3.13 -m agents.run promo-concept-strategist --dry-run
.venv/bin/python3.13 -m agents.run campaign-launch-strategist --dry-run
.venv/bin/python3.13 -m agents.run opportunity-strategist --dry-run
```
Verify in this order:
1. promo-concept-strategist outputs enriched concepts with all required fields
2. campaign-launch-strategist successfully reads the enriched concepts and writes media-plan .md files
3. All proposed_actions pass Projection Guard
4. No duplicate `promo_id` + action collisions

### Step 7 — Retire the Python emitters
Once strategists are validated:
- `scripts/work_queue/promo_concept_emitter.py` → archive as `scripts/_archive/promo_concept_emitter.py.retired-{DATE}`
- `scripts/work_queue/opportunity_emitter.py` → same
- Update `Work-Queue-Architecture.md` with the new 3-strategist + media-plan flow

### Step 8 — Commit + push + 1-week soak
- Commit each strategist + wiring as its own commit
- Watch Monday's run, then the first event-driven campaign-launch-strategist fire
- Verdict at +14 days

---

## Risks + mitigations

| Risk | Mitigation |
|---|---|
| LLM hallucinates audience seed counts | promo-concept-strategist prompt mandates `audience_seed.lookalike_seeds[].size MUST come from state files — never invent counts`. campaign-launch-strategist verifies enrichment fields exist before proceeding. |
| LLM hallucinates dollar figures | Projection Guard rejects unwhitelisted metrics; measurement_runner computes actuals from raw API data |
| campaign-launch-strategist proposes audience < 200 (Meta minimum) | Prompt enforces `min_audience_size_meta = 200` and logs warnings below |
| Joanne launches before Denver approves a >$500 budget | Media plan file header explicitly flags `Denver approval required: YES if total_aud > $500`. Dashboard's existing Denver-approval chip catches the launch action. |
| Angela accidentally approves the wrong concept | Modal includes [Send back to Concept] button on Approved+ stages — one click reverts. campaign-launch-strategist is idempotent (won't re-fire if media plan exists), so a revert + re-approve produces the same plan, not a stale one. |
| Media plan goes stale (concept changes after plan written) | campaign-launch-strategist re-runs on every concept stage change OR weekly stale-check (any plan > 30d old + concept still Approved = regen) |
| LLM forgets UTM convention | Prompt explicitly cites `context/utm-convention.md` in `tools:` and the writeup section enforces UTM table structure |
| Token cost spirals | Promo-concept monthly (~$5/mo). Campaign-launch event-driven (3-5/mo = ~$15/mo). Opportunity weekly (~$8/mo). Total ~$28/mo. Well within reasonable bounds. |
| Dashboard doesn't show the media plan to Joanne | Brief detection update in Step 4 — same pattern as existing playbook/draft detection. Existing code precedent. |

---

## Total session time when approved

- Step 1 (move 3 drafts): 1 min
- Step 2 (wire phase1 + new phase1b_promo_launch.sh script): 1 hour
- Step 3 (extractors + render_media_plan_html.py): 2 hours
- Step 4 (brief renderer update — media plan button): 30 min
- **Step 4b (promo approval UI + Supabase table + read-merge): 1.5 hours**
- Step 5 (whitelist + schema extensions if needed): 30 min
- Step 6 (smoke test all 3 strategists end-to-end including approve→trigger): 1 hour
- Step 7 (archive emitters): 5 min
- Step 8 (commit/push): 15 min

**~6.5 hours from sign-off to shipped.**

Plus 1 week of soak time before considering it stable.

---

## End-to-end workflow after Path B is live

1. **Monthly (1st)** — `promo-concept-strategist` runs. Outputs enriched concepts to `state/promo-pipeline.json`. Outputs child asset actions (with EDM/SMS/social draft links) to `state/work-queue.json`.

2. **Within the same phase1 run** — `deliverable-drafter` runs. Reads work-queue, pre-writes EDM/SMS/social/ad-copy drafts to `outputs/drafts/*.md`.

3. **Brand Manager (Angela)** opens the Promo Pipeline page, clicks the concept card. **The modal now has stage buttons** — she reviews the offer, tone, asset requirements, then clicks **[Approve →]**. The button upserts `promo_pipeline_state` in Supabase. Dashboard kanban re-renders with concept moved to Approved column.

4. **Daily 4am AWST** — new `phase1b_promo_launch.sh` script runs. Queries Supabase `promo_pipeline_state` for stage IN ('Approved','Asset Shoot Scheduled') WHERE no media plan exists yet. Detects Angela's newly-Approved concept. Fires `campaign-launch-strategist` for it.

5. **Within ~3 minutes** — campaign-launch-strategist writes the full media plan to `outputs/media-plans/media-plan-{concept_id}-{DATE}.md`. Emits a "Launch Meta + Google campaign" action to Work Queue.

6. **Joanne** opens the action brief. Sees THREE buttons:
   - View the EDM draft (creative copy ready)
   - View the social post draft (organic ready)
   - **View the media plan** (objective + audiences + budget + bid + placement + kill criteria — Meta and Google sides both filled in)

7. **Joanne** copies media plan into Meta Ads Manager. Uploads creatives. Launches.

8. **Tia** does the Google side from the same plan.

9. **Day 7** — `meta-strategist` + `google-ads-strategist` (existing) read live performance vs the plan's kill criteria. If CPA > kill threshold, they emit a "Pause campaign" action automatically. If healthy, they emit "Maintain" or "Scale" actions.

10. **Day 14** — `measurement_runner` (existing) computes actuals vs the launch action's projected KPIs. Auto-promotes to Performance Review for verdict capture. Verdict feeds back into next month's `promo-concept-strategist` via Wave 6 archive.

---

## Files to review (in this order)

1. `outputs/strategist-drafts/promo-concept-strategist.yml.draft` — esp. the new `enrich-for-campaign-launch` workflow step
2. `outputs/strategist-drafts/campaign-launch-strategist.yml.draft` — esp. `design-meta-campaign` + `design-google-campaign` sections
3. `outputs/strategist-drafts/opportunity-strategist.yml.draft` — unchanged from Option C
4. (This file) — confirm you're OK with the steps + risks

Tell me when you've reviewed and I'll execute the 8-step rollout.
