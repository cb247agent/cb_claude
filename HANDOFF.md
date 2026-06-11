# CB_Marketing — Operator Handoff

This document is for whoever takes over running the CB247 Marketing OS. Read
it once end-to-end before touching anything. It covers what runs, how to
restart it, where credentials live, and the known gotchas that bite people.

For deeper architecture, read `ENGINEERING.md` after this. For the day-to-day
content workflow, see `context/team-roster.md`.

---

## 1. What this system actually is

A weekly marketing automation pipeline for ChasingBetter247 (Perth gym chain,
two locations). Every Monday at 10:00 AWST:

1. Cron pulls fresh data from Google Analytics, Search Console, Google Ads,
   Meta Ads, Apify (competitor + social), Ahrefs, and Google Business Profile.
2. Six **emitter** scripts read that data and produce ~37 typed action
   recommendations per week (SEO / Meta / Google Ads / GBP / Organic Social /
   Membership).
3. Nine **agents** (LLM-powered) produce strategic narratives saved as
   markdown in `outputs/`.
4. A dashboard at https://cb247agent.github.io/cb_claude/ shows everything
   in real time (Supabase backend).
5. Team picks actions, executes during the week, marks Published.
6. 7-28 days later, a measurement runner compares projected vs actual KPIs
   and assigns verdicts (winner / partial / no_change / underperforming).

If you want one mental model: **data goes in, typed actions come out, team
does the work, system tells you whether it worked.** Everything else is
plumbing.

---

## 2. Getting access

You need:

| Asset | Who to ask | Notes |
|---|---|---|
| GitHub repo | Tia | `github.com/cb247agent/cb_claude` — main branch deploys to GitHub Pages |
| Supabase project | Tia | URL: `https://ckjwzwktuiavyfuolbgx.supabase.co` (publishable key is in code — anon role, RLS-protected) |
| Google service account | Tia | JSON file lives in `secrets/` — never commit |
| Anthropic API key | Tia | For agents that hit the Claude API directly |
| Apify token | Tia | Plan is paid weekly — see "subscription notes" below |
| Ahrefs API key | Tia | Lite plan, 100k units/month |
| Meta App access token | Tia | For `pull_meta.py` |
| Notion integration | Tia | Used by some agents for output sync |

The full list of `.env` variables expected is in section 8 below. Tia or her
delegate must hand you the actual values out-of-band — they are NOT in this
repo.

---

## 3. The system runs in three layers

### Layer 1: macOS launchd jobs (continuous, low frequency)

Loaded from `~/Library/LaunchAgents/`. Currently active:

```
com.cb247.data-refresh   — runs pull_all.py daily at 06:00 AWST
com.cb247.weekly-report  — backup invocation of weekly pipeline
com.cb247.weekly-seo     — legacy, deprecated (merged into weekly-report)
```

To inspect: `launchctl list | grep cb247`
To reload after editing a plist:
```
launchctl bootout gui/$(id -u)/com.cb247.<name>
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.cb247.<name>.plist
```

### Layer 2: cron (weekly pipeline)

```
0  10 * * 1   weekly-report.sh        Monday 10:00 AWST — full pipeline
30 11 * * 1   refresh-social.sh        Monday 11:30 AWST — Metricool late drop
0  6  * * 1   weekly-report-mwcc.sh   Monday 06:00 AWST — MWCC business
```

To inspect: `crontab -l`
To edit: `crontab -e`

### Layer 3: GitHub Pages deploy

Every git push to `main` triggers a deploy of `docs/index.html` (the
dashboard). No CI/CD beyond that. If the dashboard breaks after a deploy,
revert via `git revert <commit>` and push.

---

## 4. The Monday 10am sequence (most important)

`scripts/weekly-report.sh` runs three phases:

**Phase 1 — Data + Emitters (5-10 min)**
```
Step 1a    pull_weekly.py          Google Ads + Meta Ads (weekly only)
Step 1a'   pull_all.py             GA4 + GSC + GBP (free sources)
Step 1b    pull_ahrefs.py          Backlinks + rankings
Step 1c    pull_apify.py           SERP + Maps + Trends + Reddit
Step 1d    run_screaming_frog.py   Site crawl
Step 1e    parse_metricool_pdf.py  IG/TikTok engagement
Step 1f    pull_gbp_performance.py GBP API actions
Step 1g    parse_membership_data.py CRM XLSX → JSON
Step 1h    seo_emitter.py          11 SEO actions
Step 1h'   meta_emitter.py         7 Meta actions
Step 1h''  google_ads_emitter.py   4 Google actions
Step 1h''' gbp_emitter.py          5 GBP actions
Step 1h''''  social_emitter.py     5 Social actions
Step 1h''''' membership_emitter.py 5 Membership actions
Step 1h''''''  opportunity_emitter.py   Up to 5 PAUSE + 3 REDUCE (ROI)
Step 1h''''''' attribution_emitter.py   1 ROI Summary card
Step 1h'''''''' extract_agent_actions.py  Layer 3 agent proposals
Step 1i    sync_to_supabase.py     Upsert all actions
```

**Phase 2 — Agents (30-45 min)**
```
Agent 1   research-agent          Market trends + PESTLE/SWOT
Agent 2   audience-intel          ICP profiles
Agent 3   content-intel           Viral content patterns
Agent 4   performance             Budget allocation recommendation
Agent 5   seo-agent               Strategic SEO briefs
Agent 6   competitor-spy          Revo + Anytime + Ryderwear movements
Agent 7   paid-ads                Ad copy
Agent 8   content-agent           Social posts + reels + emails
Agent 9   strategist              Campaign blueprint synthesis
```

**Phase 3 — Output + Deploy (2-3 min)**
```
Step 3pre   import-meeting-minutes.py
Step 3a     bake-weekly-report.py    HTML executive report
Step 3b'    inject-*.py              Inline data into dashboard
Step 3c     deploy-dashboard.sh      git push → GitHub Pages
```

**By 11:00 AWST:** Dashboard is refreshed, agent outputs are in `outputs/`,
Tia gets an email with the weekly report link.

---

## 4.1 ROI cards — paid→organic switch loop (09 Jun 2026)

The Work Queue now includes a structured ROI loop that identifies CB247
paid keywords where CB247 already ranks organically. **This is the
executive ROI lever** — every $ saved on paid that organic absorbs is
real bottom-line.

**You'll see these in the Work Queue:**

- **PAUSE actions** (P1, owner Tia) — keywords ranking organic #1-3.
  Description includes the projected $/month saving. Action: pause that
  keyword in the named Google Ads campaign. Brand-defence keywords
  (`chasingbetter`, `cb247`) are NEVER suggested for pause.

- **REDUCE 50% actions** (P2, owner Tia) — keywords ranking organic #4-10.
  Action: cut daily budget in half. Revisit after 14 days.

- **ROI Summary card** (P3, info-only) — single card showing pipeline
  ($/mo identified but not yet executed) and realised ($/mo proven via
  measurement). This is what Robert + Denver see weekly.

**Operator workflow:**

1. Open Work Queue, filter `category=opportunity` (or look for orange
   tags labelled "OPPORTUNITY")
2. For each PAUSE/REDUCE card: open Google Ads, find the named campaign +
   keyword, execute the change, mark verdict on the card:
   - `winner` if executed cleanly
   - `partial_win` if executed with caveat (e.g., paused but kept brand match)
   - `no_change` if too risky / decision deferred
3. Two weeks later: measurement_runner auto-fills `actual_kpis` showing
   the real $ saved. No action needed from operator.
4. Four weeks later: attribution_emitter aggregates into "ROI Realised:
   $X this month" — appears in management email automatically.

**Caveats:**

- The opportunity emitter runs against THIS week's Google Ads spend. If
  spend on a keyword swings (campaign restructure, seasonal), opportunities
  may re-shuffle. Stable signals across 2+ weeks are most actionable.
- Brand-defence guard means brand keywords NEVER get pause recommendations.
  Currently hardcoded: `chasing better`, `cb247`, `chasingbetter247`. Add
  more via the `BRAND_DEFENCE_PATTERNS` list in `opportunity_emitter.py`.
- First "ROI Realised" message lands ~4 weeks after first execution
  (measurement window).

---

## 5. How to run things manually

If cron didn't fire or something failed, you can run each piece manually.

```bash
cd /Users/tiachasingbetter/Documents/ChasingBetter/CB_Marketing

# Refresh free-source data only (GA4 + GSC + GBP)
.venv/bin/python3.13 scripts/pull_all.py

# Refresh paid sources (Google Ads + Meta) — weekly cadence only
.venv/bin/python3.13 scripts/pull_weekly.py

# Re-emit all Work Queue actions for this week
for e in seo_emitter meta_emitter google_ads_emitter gbp_emitter social_emitter membership_emitter; do
    .venv/bin/python3.13 scripts/work_queue/$e.py
done

# Push to Supabase
.venv/bin/python3.13 scripts/work_queue/sync_to_supabase.py

# Force a verdict measurement on a specific action
.venv/bin/python3.13 scripts/work_queue/measurement_runner.py --force-id seo-act-2026w23-001

# Dry-run (no Supabase writes) — useful for testing
.venv/bin/python3.13 scripts/work_queue/measurement_runner.py --dry-run

# Full weekly pipeline (what cron runs)
bash scripts/weekly-report.sh

# Deploy dashboard manually
bash scripts/deploy-dashboard.sh
```

---

## 6. Where outputs land

| Directory | What goes here |
|---|---|
| `state/*.json` | Live data snapshots, last-refresh timestamps. **Never commit.** |
| `outputs/research/` | Performance reports, audience analysis, competitor research |
| `outputs/seo/` | SEO audits, content strategy, briefs |
| `outputs/content/` | Social posts, reels, email drafts |
| `outputs/blueprints/` | Campaign blueprints from strategist |
| `outputs/creatives/` | Ad copy + creative briefs |
| `outputs/reports/` | HTML executive reports (the Monday email) |
| `docs/index.html` | The live dashboard. Committed + deployed. |
| Supabase `work_queue_actions` | Action cards visible in dashboard |
| Supabase `planner_status` | Stage of each card (Idea / In Progress / etc.) |
| Supabase `planner_approval` | Per-card approval decisions + notes |

---

## 7. Known pending items (KEEP THESE LIVE)

These are flagged in `~/.claude/projects/-Users-tiachasingbetter-Documents-ChasingBetter/memory/MEMORY.md`. Don't forget about them.

1. **Baker consolidation pending** — `bake-public-dashboard.py` WIPES
   multi-business work. Sentinel file `state/.baker-disabled` blocks it.
   Step 3b in `weekly-report.sh` is DISABLED. Re-enable only after
   consolidating bake logic. Trigger this when CB247 KPI data goes stale.

2. **GBP API Quota** — `pull_gbp_performance.py` currently returns HTTP 429.
   Location IDs confirmed (`locations/9370517448306562177` for Malaga,
   `locations/15427870753118893794` for Ellenbrook). Need to submit quota
   increase request via Google Cloud Console.

3. **Google Ads API Standard Access** — submitted 2026-06-05, awaiting
   Google review. DO NOT run `pull_google_ads.py` directly until approved
   — basic access has tight limits.

4. **Apify Actor Fixes** — 4 actors broken (TikTok, Reddit, Trends, FB Ads).
   Empty data blocks in `state/apify-data.json` reflect this. Fix blocked
   on subscription top-up (paid 02 Jun 2026, actors may need re-triggering).

5. **Performance Review verdict picker** — works for organic-social
   qualitative actions, but the UI doesn't yet show a "pick verdict"
   confirmation for newly-measured items. Workaround: team writes verdict
   word in `notes_human` field.

---

## 8. Environment variables (.env)

`.env` is gitignored. Required keys (Tia hands over actual values):

```
# Anthropic / Claude
ANTHROPIC_AUTH_TOKEN
ANTHROPIC_API_KEY
ANTHROPIC_BASE_URL
ANTHROPIC_MODEL
ANTHROPIC_DEFAULT_SONNET_MODEL=claude-sonnet-4-5
ANTHROPIC_DEFAULT_HAIKU_MODEL=claude-haiku-4-5
ANTHROPIC_DEFAULT_OPUS_MODEL=claude-opus-4-5
CLAUDE_MODEL_STANDARD
CLAUDE_MODEL_HEAVY

# Third-party APIs
APIFY_API_KEY
META_ACCESS_TOKEN
NOTION_API_KEY
NOTION_PARENT_PAGE_ID
SLACK_BOT_TOKEN

# Google APIs (service account JSON files in secrets/)
GA4_MEASUREMENT_ID
GA4_PROPERTY_ID

# Email (weekly report delivery)
SMTP_HOST
SMTP_PORT
SMTP_USER
SMTP_PASS

# Misc
OLLAMA_BASE_URL    # optional local-LLM fallback
```

For Google Ads + Meta + GBP + GA4 service-account JSONs: `secrets/` folder.
NEVER commit. Currently in `.claudeignore` + `.gitignore`.

---

## 8.5 Dev cycle (Wave A · 11 Jun 2026)

The dev cycle is 4 scripts + a wrapper that catch the bug classes we kept
hitting (schema drift, stale workflow vocab, strategist regressions,
vulnerable deps) BEFORE they ship to the live dashboard.

### When the dev cycle runs

| Trigger | Mode | What it runs | Total time |
|---|---|---|---|
| Monday cron pipeline (auto) | `--pre-flight` | All 4 checks incl. live Supabase probe + dep audit | ~30-60s |
| Before any commit (manual) | `--pre-commit` | 3 fast checks (no live probe, no dep audit) | <10s |

The wrapper is `scripts/dev-cycle.sh`. It's wired into `weekly-report.sh`
as Phase 0 — runs before Phase 1 data pulls so we fail fast on schema
drift instead of crashing partway through a sync.

### Manual invocation

```bash
# Quick check before commit (recommended habit):
bash scripts/dev-cycle.sh --pre-commit

# Full check before Monday's pipeline (the cron already does this):
bash scripts/dev-cycle.sh --pre-flight

# Strict mode — exit 1 on findings (use sparingly until rules are tuned):
bash scripts/dev-cycle.sh --pre-commit --strict
```

### What each script catches

| Script | Catches | Source of truth | Log file |
|---|---|---|---|
| `scripts/scan_brand_voice.py` | Stale workflow vocab (Angela QC / Denver / Mark publishes), banned ACL claims ("only gym with..."), TGA therapeutic claims, AI buzz words, $11.95 in editorial copy | `scripts/work_queue/compliance.py` CB247_BANNED_PATTERNS | `logs/scan-brand-voice-YYYY-MM-DD.json` |
| `scripts/check_supabase_schema_drift.py` | Python `VALID_STAGE`/`VALID_*` enums declaring values that Supabase CHECK constraints reject. Optional `--live` flag probes real DB. | `scripts/work_queue/schema.py` + `db/schema.sql` | `logs/schema-drift-YYYY-MM-DD.json` |
| `scripts/test_strategist_chain.py` | Regressions in strategist → normalise → schema-validate chain. Fixture-driven, no Claude/Supabase. | Fixture inline in the script | `logs/strategist-chain-test-YYYY-MM-DD.json` |
| `scripts/audit_dependencies.py` | Known CVEs in `scripts/requirements.txt` via pip-audit | `scripts/requirements.txt` | `logs/dep-audit-YYYY-MM-DD.json` |

### Warn-only by default

All 4 scripts exit 0 even when findings exist — they print warnings and
move on. The pipeline never blocks. This is intentional: it lets you see
what's drifting before you have to fix it.

**Promote a check to blocking** by adding `--strict` to that check's
invocation in `scripts/dev-cycle.sh`. Example:

```bash
# In scripts/dev-cycle.sh, change:
run_check "Schema drift" \
    "$PYTHON scripts/check_supabase_schema_drift.py --log $STRICT_FLAG"
# to:
run_check "Schema drift" \
    "$PYTHON scripts/check_supabase_schema_drift.py --log --strict"
```

### What the checks WON'T catch (yet)

These are in Wave B (next session) — agents that exercise the dashboard
and watch for regressions in rendered output:

- Layout regressions on the dashboard (wrong list, wrong column, wrong order)
- Brand voice issues that need LLM judgement (e.g. "this paragraph sounds passive-aggressive")
- Visual changes (font, color, spacing) — needs screenshot diffing
- RLS policy regressions on Supabase

---

## 9. Common failure modes + fixes

| Symptom | Likely cause | Fix |
|---|---|---|
| Dashboard shows old data after Monday | Cron failed | Check `state/weekly-report.log` — find which step errored, run manually |
| `pull_all.py` errors with DNS resolution | gRPC c-ares on macOS | `GRPC_DNS_RESOLVER=native` is set in launchd plist; if running manually, `export GRPC_DNS_RESOLVER=native` first |
| Emitter writes 0 actions | Source data missing or empty | Check `state/*.json` for that source — does it have a recent timestamp? |
| `sync_to_supabase.py` fails with 401 | Anon key expired/changed | Update `SUPABASE_KEY` constant in scripts AND in `docs/index.html` |
| `measurement_runner.py` returns "not eligible" | Action not Published OR window not elapsed | Confirm action's `planner_status` row says `Published`. Window comes from action's projected_kpis. |
| Dashboard not updating despite git push | GitHub Pages build failed | Check `github.com/cb247agent/cb_claude/actions` for the failed build |
| Realtime cards not syncing across browsers | Supabase publication missing tables | `ALTER PUBLICATION supabase_realtime ADD TABLE work_queue_actions;` plus `REPLICA IDENTITY FULL` |

---

## 10. Security boundaries — DO NOT VIOLATE

- **Never commit `.env`, `secrets/`, `state/*.json`.** All three are in
  `.gitignore` and `.claudeignore`. If a key leaks via commit, rotate it
  immediately in the source platform.
- **Never run `bake-public-dashboard.py`** unless the baker-consolidation
  work is complete. It wipes multi-business pages. Sentinel
  `state/.baker-disabled` exists to block it — do not delete that file.
- **Never grant agents write access to live ad platforms.** Agents only
  read context files and write `outputs/*.md`. Budget decisions are HUMAN
  execution.
- **RLS policies on Supabase** allow the anon role to insert + update +
  select on planner_status / planner_approval / work_queue_actions. This
  is intentional — the dashboard is client-side and uses the publishable
  key. If you ever expose service-role keys, rotate everything.

---

## 11. Backup / restore

- **Code:** GitHub repo is the canonical source.
- **Supabase data:** Use Supabase's built-in daily snapshots (Settings →
  Database → Backups). If you ever rebuild from scratch, the schema +
  policies are in `db/schema.sql` and `db/policies.sql` — apply via SQL
  Editor.
- **state/*.json files:** Not backed up. They are re-generated by cron.
  If you need a historical snapshot, look in `state/ahrefs-snapshot-*.json`
  (manually frozen) or the git history of `outputs/reports/*.html`.
- **Secrets:** Tia maintains a separate password manager. Replicate there.

---

## 12. Who owns what (team roster)

See `context/team-roster.md` for the full version. Quick reference:

| Name | Role |
|---|---|
| Tia | OS Owner — strategic + paid Google Ads + competitive defence |
| Denver | COO — final sign-off on every action |
| Angela | Manager CB247 Gym — brand QC + frontline ops (save calls, member habit, review cadence) |
| Joanne | Lead/Coord — Meta + TikTok paid ads + creative team coordination |
| John | SEO/Web — on-page optimisation, content briefs |
| Mark | Webflow developer — page builds + publishes |
| Shauna | Asset Creator — content production + GBP photos |
| Shaun + Jane | Graphic design (shared across all 4 businesses) |
| Ivan + Agust | Video (shared across all 4 businesses) |

---

## 13. Where to look next

- **System architecture:** `ENGINEERING.md`
- **Decision history:** commit log + `CB_Brain/wiki/Work-Queue-Architecture.md`
- **Active priorities:** `CB_Brain/wiki/00-Index.md`
- **Brand voice + content rules:** `context/brand-voice.md`, `skills/*/SKILL.md`
- **Database schema:** `db/schema.sql` + `db/policies.sql`

---

**Last updated:** 07 Jun 2026  
**Document owner:** Tia (until handover)
