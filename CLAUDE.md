# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Critical Behavior: Check Before Asserting

**Before answering any question about system state, always verify with the relevant tool first. Never assert from memory.**

This applies to: cron jobs (`crontab -l`), scheduled tasks, scripts, config files, API status, file contents, environment state, or anything that exists on disk or in the system. Read it, then answer.

## Critical Behavior: Read ENGINEERING.md Before Architectural Changes

**Before modifying ANY of these areas, read `ENGINEERING.md` first.** It contains cookbooks, dispatcher patterns, RLS rules, and the cbState frontend conventions that prevent silent breakage:

| If the change touches... | What ENGINEERING.md tells you |
|---|---|
| `scripts/work_queue/*` (emitters, measurement, sync, schema) | The 9-step cookbook for adding a new emitter — covers schema extension, baseline helpers, measurement dispatch, weekly-report.sh wiring |
| `db/*.sql` or Supabase tables | RLS policies, REPLICA IDENTITY FULL requirement, realtime publication setup |
| `docs/index.html` render functions or `cbState.*` | The cbState namespace pattern, localStorage cache + Supabase sync, realtime postgres_changes flow |
| `agents/*.yml` | Layer 2 boundary — agents read `context/*.json` not `state/*.json` (with documented exceptions) |
| `scripts/weekly-report.sh` phase ordering | Why each Phase runs in the order it does, what depends on what |

**Does NOT apply to:** content tasks (blogs, social posts, emails), brand voice work, agent skill content generation, or answering questions about the project. For those, this CLAUDE.md is sufficient.

**Why this rule exists:** the closed-loop architecture (emitter → Supabase → dashboard → team → measurement → verdict) has multiple invariants that aren't obvious from code alone. Skipping ENGINEERING.md and improvising has caused silent breakage in the past — forgetting REPLICA IDENTITY FULL means realtime stops working, forgetting to register a metric in VALID_METRICS means actions fail validation, etc.

Operational tasks (running scripts, debugging cron, restoring data) — read `HANDOFF.md` instead.

# ChasingBetter247 — CB_Marketing

AI-powered marketing automation for ChasingBetter247 Health & Fitness Club (Perth, WA).
Locations: Malaga + Ellenbrook | Members: 8,000+ | Price: $11.95/week, no lock-in
Contact: reception@chasingbetter247.com.au | Instagram: @chasingbetter247 | Tagline: AlwaysBetter | Brand color: #3FA69A (teal)

## Services
24/7 Gym, Neon21, Yoga, Spin, CrossFit, Reformer Pilates, ChasingRX, Sauna + Ice Bath, Kids Hub, Personal Training, FIFO-friendly freeze

## Top Competitors
1. Revo Fitness — $9.69–$12.69/week, 24/7 Reformer Pilates (biggest threat)
2. Ryderwear Gym Malaga — same suburb, lifters-focused
3. Anytime Fitness / Snap Fitness — ~$15+/week, no premium facilities

## CB247 Competitive Edge
- Cheaper than Anytime/Snap with MORE premium facilities
- Genuine differentiators (competitors don't have ALL of these): Kids Hub + Traditional Sauna + Ice Bath + 24/7 access + FIFO freeze
- ⚠️ Never write "only gym with" in content — Ryderwear has sauna + reformer pilates. Verify before using "only" claims (ACL risk).
- FIFO-friendly membership freeze — no other Perth chain offers this

## Architecture

This is a marketing ops system, not a software project. There is no build/test/lint system — content and data are generated, not compiled.

**Common commands** (run from project root):
```bash
python scripts/pull_all.py            # Refresh all data sources (GA4, GSC, Google Ads, Meta)
python scripts/bake-dashboard.py      # Generate HTML dashboards
python scripts/bake-weekly-report.py  # Generate weekly performance reports
bash scripts/run-refresh.sh           # Scheduled data refresh
```

**Skills** (`skills/*/SKILL.md`) — Auto-activate when task contains trigger keywords. Each defines rules, formulas, templates, and quality checklists for that content type.
**Agents** (`agents/*.yml`) — YAML configs for autonomous agents. Each specifies: `model`, `skills`, `tools`, `Input required`, `Output`, `End` (completion signal).
**Context files** (`context/*.md`) — Brand voice, strategy, research. Read on every session start.
**Hooks** (`.claude/settings.json`) — `PostToolUse` hook fires on every `Write`; if the target path matches `outputs/*.md` and doesn't already end in `-final.md`, it triggers the `report-formatter` skill to generate a McKinsey-style executive report saved as `[filename]-final.md`.

## Dashboard Design Standards (MANDATORY)

**Any work on `bake-public-dashboard.py`, `docs/index.html`, or any dashboard UI must follow `context/design-standards.md` and `skills/dashboard-design/SKILL.md`.**

Rules in brief:
- **Three colours only**: teal `#3FA69A`, black `#0d0d0d`/`#1a1a1a`, white `#fff`, and gray scale. No blues, pinks, yellows, purples, reds, or other greens.
- **No emojis** in any UI element (columns, buttons, badges, labels, titles). Allowed only in content copy.
- **Kanban must fit screen**: `grid-template-columns:repeat(5,1fr); align-items:start`. Main area: `height:100vh; overflow-y:auto`. Content: `padding-bottom:60px`.
- Full spec: `context/design-standards.md`

## Agent Catalog
| Agent | Purpose |
|-------|---------|
| `strategist` | Campaign blueprints from research |
| `content-agent` | Multi-format content generation |
| `audience-intel` | ICP and segmentation analysis |
| `competitor-spy` | Competitor monitoring and analysis |
| `paid-ads` | Google/Meta ads management |
| `performance` | Dashboard and reporting |
| `research-agent` | Deep research tasks |
| `content-intel` | Content performance analysis |
| `seo-agent` | SEO audits, content strategy, keyword research |

**Model**: Agents use Claude models routed by task complexity (see Context Management below).
**Invocation**: Say "run [agent-name]" to fire any agent (see Agent Invocation below).

## Folder Structure
```
context/          → Brand voice, strategy, research (read every session)
skills/           → 37 auto-activated skill engines (SKILL.md files)
agents/           → 9 autonomous task agents (YAML configs)
outputs/          → Generated content, campaigns, reports (date-stamped)
    outputs/blueprints/    → Campaign blueprints
    outputs/content/       → Social content, reels, ad copy (content-agent)
  outputs/creatives/     → Ad copy, creative briefs
  outputs/research/      → Competitor research, audience analysis, performance reports
  outputs/reports/       → Weekly performance HTML reports (cb247-weekly-report-YYYY-MM-DD.html)
  outputs/seo/           → SEO audits, content drafts, reports
  outputs/social/       → Social content calendars
dashboards/       → Agent monitoring dashboard + HTML performance dashboards
googleads/        → Google Ads data and account configs
metaads/          → Meta Ads data and account configs
Image/            → Marketing creative assets (photos, graphics)
scripts/          → Python data-pull scripts (GA4, GSC, Google Ads)
state/            → Agent memory, campaign history, status.json
secrets/          → Google credentials JSON (never commit, never git)
```

## Data Pipeline

Python scripts in `scripts/` pull live data from Google APIs and third-party tools:
- `pull_ga4.py` — GA4 session, conversion, and funnel data
- `pull_gsc.py` — Google Search Console impressions, clicks, rankings
- `pull_google_ads.py` — Google Ads spend, CPC, conversions by location
- `pull_all.py` — Combined refresh of all data sources
- `pull_ahrefs.py` — Backlink and keyword ranking data
- `pull_apify.py` — Scraped competitor and market data
- `pull_local_ads.py` — Local ad performance data
- `run_screaming_frog.py` — Technical SEO site crawl
- `bake-dashboard.py` — Compiles data into HTML dashboards
- `bake-weekly-report.py` — Generates weekly performance reports
- `run-refresh.sh` — Shell wrapper for scheduled refresh runs

Data lands in `state/ga4-data.json`, `state/gsc-data.json`, `state/google-ads-data.json`. Last refresh timestamp tracked in `state/last-refresh.json`.

## Key Conventions

**UTM Convention** (`context/utm-convention.md`):
- `utm_source`: meta / google / instagram / facebook / email / sms / gmb
- `utm_medium`: paid_social / paid_search / organic_social / email / sms
- `utm_campaign`: `[objective]-[location]-[month]-[year]` (e.g., `membership-malaga-may-2026`)

**Output files**: Always date-stamp as `filename-YYYY-MM-DD.md`
**Report outputs**: Any `.md` file written to `outputs/` auto-formats into a McKinsey-style executive report via a `PostToolUse` hook. Save as `[filename]-YYYY-MM-DD.md` — the hook creates `[filename]-final.md`.

## Context Management

**Model** (Claude Max subscription — configured in `.claude/settings.json`):
- Default (Sonnet): `claude-sonnet-4-5` — analysis, writing, SEO, competitor, paid ads, research
- Lightweight (Haiku): `claude-haiku-4-5` — fast extraction (audience intel, content intel, subagents)
- Heavy (Opus): `claude-opus-4-5` — high-volume creative generation and strategic synthesis

**Token budget**: 0–60% normal | 60–75% summarize older context | 75–85% use /compact | 85%+ STOP and run /compact
**Auto-compact**: Enabled (`autoCompact: true`), threshold at 70% context window.

**Session start**: Read `context/session-start.md` first — it has the full project state, what's done, what's missing, and all keywords to run things. Then confirm "CB247 context loaded. Ready."

**Skill triggers** (auto-activate on these keywords):
- `write email` / `draft email` / `email sequence` → email funnel builder (4-email + 2-SMS sequences)
- `content waterfall` / `repurpose this` / `content repurposing` → content waterfall (1→14 assets)
- `social calendar` / `content plan` / `30-day content` → social content calendar
- `UTM audit` / `tag URLs` / `UTM tagging` → utm-standardizer
- `competitor ads` / `competitor analysis` → competitor-ads-scraper
- `site audit` / `SEO audit` / `technical SEO` → seo-site-audit
- `landing page` / `write page` / `build page` → seo-landing-page-writer
- `A/B test` / `hypothesis` → ab-testing-framework
- `compliance` / `check claims` → compliance-checker
- `campaign brief` → campaign-brief-engine
- `creative brief` / `storyboard` → creative-brief-engine
- `market intel` / `competitor intel` → market-intelligence
- `keyword research` / `SEO content` → seo-agent (full pipeline; for audit only, use `SEO audit` → seo-site-audit above)
- `competitor` / `competitive analysis` → competitor-spy
- `Google Ads` / `Meta Ads` / `paid ads` → paid-ads
- `performance` / `dashboard` / `analytics` → performance

**Output flow**: Save drafts to `outputs/` with date stamp (e.g., `email-2026-05-11.md`) → PostToolUse hook auto-generates `[name]-final.md` McKinsey-style report. Only edit the source file, not the `-final.md`.

**MCP context**: `filesystem` MCP server has access to both CB_Marketing and CB_Brain/wiki — use for cross-referencing knowledge base content.

**Concise mode**: Prefix tasks with "keep it concise" or "output only key points" for shorter responses when using minimax.

**Output discipline**:
- Save outputs to `outputs/` folder
- **Never edit `context/`, `skills/`, or `agents/` files** unless explicitly instructed — these are system files
- Date-stamp all output files: `[filename]-YYYY-MM-DD.md`

**If task is too complex**: Break into sub-tasks, complete and save each, use /compact between steps.

## Agent Invocation

Say **"run [agent]"** to fire any agent:

| Say this | Agent runs | Output |
|---------|-----------|--------|
| `run strategist` | Campaign blueprint builder | `outputs/blueprints/[name]-blueprint.md` |
| `run competitor-spy` | Full competitor analysis | `outputs/research/competitor-full-analysis.md` |
| `run research-agent` | Market trends + PESTLE/SWOT | `outputs/research/` |
| `run audience-intel` | 5 ICP profiles | `outputs/research/audience-analysis.md` |
| `run content-intel` | Viral content research | `outputs/research/content-intel.md` |
| `run content-agent` | Social content, reels, ads | `outputs/content/` |
| `run paid-ads` | Google + Meta ad copy | `outputs/creatives/[campaign]/paid-ads/` |
| `run performance` | Weekly performance report | `outputs/research/performance-week-[N].md` |
| `run seo-agent` | Site audit + SEO strategy | `outputs/seo/` |

**Pipeline Orchestrators** (say one of these phrases):
| Say this | Runs |
|---------|------|
| `campaign output` / `full campaign` / `launch campaign` | 7-stage: brief → waterfall → email → social calendar → paid ads → landing page → executive report |
| `paid ads pipeline` / `ad creative pipeline` | 6-stage: competitor ads → audience → meta copy → google copy → creative briefs → UTM audit |
| `SEO pipeline` / `end-to-end SEO` / `build SEO landing page` | 6-stage: audit → competitor SEO → brief → landing page → compliance → report |

**Prerequisites**:
- `paid-ads` requires a blueprint in `outputs/blueprints/` first
- `strategist` requires research files in `outputs/research/` first
- `performance` works best after running `scripts/pull_all.py`

**Full manifest**: `skills/manifest.json` has all trigger→agent mappings.

## CB_Brain Integration
Knowledge base: `~/Documents/ChasingBetter/CB_Brain/wiki/`
Raw inbox: `~/Documents/ChasingBetter/CB_Brain/raw/`

**Rules**:
- Start every session: read `wiki/00-Index.md` first
- After competitor research: update `wiki/research-competitors.md`
- After any campaign: update `wiki/Campaign-History.md`
- After any agent run: update `wiki/Agent-Learnings.md`
- After SEO work: update `wiki/SEO-Learnings.md`
- Never delete wiki files — append only

## Team Member Onboarding

**Non-technical team members** can access CB_Marketing via Claude Cowork using these slash commands:


| Command | What it does |
|---------|-------------|
| `/blog` | Generate this week's SEO blog draft |
| `/meeting prepare` | Generate pre-meeting recommendations from data |
| `/meeting record [notes]` | Convert meeting notes into structured minutes |
| `/meeting actions` | Create tracked actions from selected recommendations |
| `/status` | View active actions and KPI performance |
| `/creative [brief]` | Generate image/video using Higgsfield AI |


**Workflow for management meetings:**
1. Run `/meeting prepare` → AI generates recommendations
2. Review recommendations at meeting
3. Run `/meeting record` with your notes
4. Run `/meeting actions` to create tracked items
5. Execute actions, then run `/performance review [action-id]` after 14 days

---


## Excluded from Git

The following are in `.claudeignore` and must never be committed:
- `.env` and `.env.*` — API keys and credentials
- `.claude/settings.json` — contains auth tokens
- `secrets/` — Google OAuth and service account JSONs
- `*.pem`, `*.key` — private keys
- `state/*.json` — live data snapshots (GA4, GSC, Google Ads, last refresh timestamp)