# CB247 Marketing System — Complete Blueprint
**Created:** 2026-05-22 | **Type:** System Architecture Blueprint

---

## What Is This Project?

CB_Marketing is an **AI-powered marketing ops system** for ChasingBetter247 Health & Fitness Club (Perth, WA). It is not a software product — there is no build/test pipeline. Content and data are **generated**, not compiled. Everything runs via Claude Code agents, skills, and Python data-pull scripts.

**The core job:** Automate marketing content creation, competitor monitoring, ad copy generation, SEO, and performance reporting for a dual-location gym with 8,000+ members at $11.95/week.

---

## Business Context

| Fact | Value |
|------|-------|
| Gym name | ChasingBetter247 |
| Locations | Malaga + Ellenbrook, Perth WA |
| Members | 8,000+ |
| Price | $11.95/week, no lock-in |
| Brand color | #3FA69A (teal) |
| Tagline | AlwaysBetter |
| Contact | reception@chasingbetter247.com.au |
| Instagram | @chasingbetter247 |

**Services:** 24/7 Gym, Neon21, Yoga, Spin, CrossFit, Reformer Pilates, ChasingRX, Sauna + Ice Bath, Kids Hub, Personal Training, FIFO-friendly freeze

**Competitive Edge (unique to WA market):**
- Kids Hub + Sauna + Ice Bath + Reformer Pilates + 24/7 access — only gym with this combination
- FIFO-friendly freeze feature
- Cheaper than Anytime/Snap with MORE premium facilities

**Top Competitors:** Revo Fitness (biggest threat, $9.69–$12.69/wk), Ryderwear Gym Malaga, Anytime Fitness, Snap Fitness

---

## System Architecture

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                    CB_Marketing                          │
                    │              (Marketing Ops System)                     │
                    └─────────────────────────────────────────────────────────┘
                                      │
           ┌──────────────────────────┼──────────────────────────┐
           ▼                          ▼                          ▼
    ┌──────────────┐         ┌──────────────┐          ┌──────────────┐
    │   Context    │         │    Skills    │          │    Agents    │
    │  (brand,     │         │  (37 SKILL.md│          │  (9 YAML     │
    │  strategy,   │         │  auto-fire   │          │  autonomous  │
    │  research)   │         │  on trigger) │          │  task agents)│
    └──────────────┘         └──────────────┘          └──────────────┘
                                      │                          │
           ┌──────────────────────────┼──────────────────────────┘
           ▼                          ▼
    ┌──────────────┐         ┌──────────────────────────────┐
    │   Scripts    │         │        Outputs               │
    │  (Python     │         │  (content, campaigns,       │
    │  data pull)  │         │  reports, date-stamped)      │
    └──────────────┘         └──────────────────────────────┘
           │
           ▼
    ┌──────────────┐
    │   State      │
    │  (JSON data  │
    │  snapshots)  │
    └──────────────┘
```

---

## The 9 Agents

| Agent | Trigger | What It Does | Output | Prerequisites |
|-------|---------|--------------|--------|---------------|
| `strategist` | `run strategist` | Builds campaign blueprints from research | `outputs/blueprints/[name]-blueprint.md` | Research files in `outputs/research/` |
| `competitor-spy` | `run competitor-spy` | Full competitor analysis | `outputs/research/competitor-full-analysis.md` | None |
| `audience-intel` | `run audience-intel` | 5 ICP profiles for Malaga + Ellenbrook | `outputs/research/audience-analysis.md` | None |
| `content-intel` | `run content-intel` | Viral fitness content research | `outputs/research/content-intel.md` | None |
| `research-agent` | `run research-agent` | Market trends, PESTLE/SWOT | `outputs/research/` | `context/research-competitors.md`, `context/strategy-pestle-swot.md` |
| `content-agent` | `run content-agent` | Social content, reels, ad copy | `outputs/content/`, `outputs/creatives/` | `context/brand-voice.md` |
| `paid-ads` | `run paid-ads` | Google + Meta ad copy | `outputs/creatives/[campaign]/paid-ads/` | Blueprint in `outputs/blueprints/` |
| `performance` | `run performance` | Weekly performance report | `outputs/research/performance-week-[N].md` | `state/ga4-data.json`, `state/google-ads-data.json` |
| `seo-agent` | `run seo-agent` | SEO audit, keyword research, content strategy | `outputs/seo/` | `context/seo-targets-cb247.md`, `context/seo-priorities-cb247.md` |

**All agents use:** `minimax/minimax-m2.7` via OpenRouter

---

## The 37 Skills (Auto-Fire on Keywords)

Skills live in `skills/*/SKILL.md` and activate when task contains trigger keywords.

### Foundation Skills
| Skill | Triggers | Purpose |
|-------|----------|---------|
| brand-voice | (always active) | Brand tone, language rules, CTA hierarchy |
| utm-standardizer | `UTM audit`, `tag URLs` | UTM tagging + audit per convention |
| psychology-triggers | (in context) | Emotional drivers for fitness audience |
| competitor-battle-cards | `competitor` | Revo, Ryderwear, Anytime, Snap battle cards |
| marketing-strategy | `strategy` | Campaign strategy framework |
| seasonal-calendar | `seasonal`, `calendar` | Annual marketing calendar |
| seo-targets | `SEO targets` | Target keywords per location |
| seo-priorities | `SEO priorities` | Priority keywords |
| pestle-swot | `PESTLE`, `SWOT` | Market analysis framework |

### Content Skills
| Skill | Triggers | Purpose |
|-------|----------|---------|
| content-writer | `write content`, `draft` | General content generation |
| social-analyst | `social analysis` | Social media performance analysis |
| viral-content-finder | `viral content`, `trending` | Find viral fitness hooks |
| content-waterfall | `content waterfall`, `repurpose` | 1 piece → 14 assets |
| social-content-calendar | `social calendar`, `30-day` | 30-day content plan |
| creative-brief-engine | `creative brief`, `storyboard` | AI prompts + storyboards |
| email-funnel-builder | `write email`, `email sequence` | 4-email + 2-SMS sequences |
| member-onboarding | `onboarding`, `welcome` | New member emails |

### Ads Skills
| Skill | Triggers | Purpose |
|-------|----------|---------|
| ads-manager | `Google Ads`, `Meta Ads` | Audience targeting |
| meta-ads-optimizer | `meta ads` | 12 ad variants across 4 ad sets |
| google-ads-optimizer | `google ads` | RSA + 7 keyword clusters + 3 campaigns |
| competitor-ads-scraper | `competitor ads` | Scrape competitor ads |

### SEO Skills
| Skill | Triggers | Purpose |
|-------|----------|---------|
| seo-site-audit | `site audit`, `SEO audit` | Technical SEO audit |
| competitor-seo-scraper | `competitor SEO` | Competitor keyword analysis |
| seo-content-strategist | `SEO content` | Content strategy |
| seo-landing-page-writer | `landing page` | Full HTML landing pages |
| local-seo-optimizer | `local SEO` | Google Business Profile optimization |
| seo-reporting | `SEO report` | SEO performance reports |

### Analytics/Intel Skills
| Skill | Triggers | Purpose |
|-------|----------|---------|
| analytics-connector | `analytics` | GA4/GSC/Ads data connector |
| performance-dashboard | `dashboard` | Full GA4/GSC/Meta/Google Ads dashboard |
| audience-segmentation | `audience`, `segment` | Member segmentation |
| market-intelligence | `market intel` | Competitor + market intel |
| ab-testing-framework | `A/B test`, `hypothesis` | Test framework |
| compliance-checker | `compliance`, `check claims` | Marketing claims validation |

### Pipeline Orchestrators
| Skill | Triggers | Purpose |
|-------|----------|---------|
| seo-creative-pipeline | `SEO pipeline`, `end-to-end SEO` | 6-stage: audit → competitor SEO → brief → landing page → compliance → report |
| paid-ads-creative-pipeline | `paid ads pipeline` | 6-stage: competitor → audience → meta copy → google copy → briefs → UTM audit |
| campaign-output-skill | `campaign output`, `full campaign` | 7-stage: brief → waterfall → email → social → paid ads → landing page → report |
| report-formatter | (auto via hook) | Converts `.md` in `outputs/` to McKinsey-style executive report |

---

## Data Pipeline

### Python Scripts (`scripts/`)

```
scripts/
├── pull_all.py              ← Combined refresh: GA4 + GSC + Google Ads + Meta
├── pull_ga4.py              ← GA4 sessions, conversions, funnel
├── pull_gsc.py              ← GSC impressions, clicks, rankings
├── pull_google_ads.py       ← Google Ads spend, CPC, conversions by location
├── pull_ahrefs.py           ← Backlinks + keyword rankings
├── pull_apify.py           ← Scraped competitor/market data
├── pull_local_ads.py       ← Local ad performance (ISO-week parsing from CSV)
├── run_screaming_frog.py   ← Technical SEO site crawl
├── bake-dashboard.py        ← HTML dashboard generator
├── bake-weekly-report.py   ← Weekly HTML performance report
└── run-refresh.sh          ← Shell wrapper for scheduled refreshes
```

### Data Output Locations
| Data | Location |
|------|----------|
| GA4 | `state/ga4-data.json` |
| GSC | `state/gsc-data.json` |
| Google Ads CSV | `googleads/Google Ads {Malaga,Ellenbrook}/[week].csv` |
| Meta Ads CSV | `metaads/Malaga/Meta_Malaga.csv`, `metaads/Ellenbrook/Meta_Ellenbrook.csv` |
| Combined Ads | `state/ads-data.json` |
| Last refresh | `state/last-refresh.json` |

### Weekly Report (`outputs/reports/`)
Generated by `bake-weekly-report.py` — canonical template:
- Warm-light theme: `#f7f6f3` bg, `#00c4b4` teal accent, DM Serif Display font
- Sections: Executive Summary, GA4, GSC, Google Ads, Meta Ads, Key Insights
- Google Ads: Malaga vs Ellenbrook location cards (Spend/CPC/CPA) + prior-week comparison
- Meta Ads: Malaga vs Ellenbrook location cards (Spend/CPM/CPC) + 4-metric grid
- 6-card insight grid with red/amber/green priority tags
- Sticky section nav, scroll animations, responsive

---

## Key Conventions

### UTM Convention
```
utm_source = meta | google | instagram | facebook | email | sms | gmb
utm_medium = paid_social | paid_search | organic_social | email | sms
utm_campaign = [objective]-[location]-[month]-[year]
  Example: membership-malaga-may-2026
utm_content = [format]-[variant]-[audience]
  Example: reel-hook-a-cold
utm_term = {keyword} (Google Ads dynamic insertion only)
```

### Output Conventions
- **Date stamp:** All output files as `filename-YYYY-MM-DD.md`
- **Auto-report:** `.md` files saved to `outputs/` trigger `report-formatter` skill → creates `[filename]-final.md` (McKinsey-style executive report)
- **Only edit source file** — never edit the `-final.md` (it's auto-generated)

### Brand Voice
- **Tone:** Direct, warm, energetic, Perth-local. Write like a coach talking to a mate.
- **Never:** corporate language, passive voice, "leverage", "synergy", "utilize", "facilitate"
- **Use:** "train" not "exercise", "members" not "customers", "join" not "sign up"
- **Primary CTA:** "Join for $11.95/week — No Lock-in"

---

## CB_Brain Integration

Knowledge base lives at `~/Documents/ChasingBetter/CB_Brain/wiki/`

**Session rules:**
1. Start every session: read `wiki/00-Index.md` first
2. After competitor research: update `wiki/research-competitors.md`
3. After any campaign: update `wiki/Campaign-History.md`
4. After any agent run: update `wiki/Agent-Learnings.md`
5. After SEO work: update `wiki/SEO-Learnings.md`
6. Never delete wiki files — append only

---

## Folder Structure

```
CB_Marketing/
├── context/           ← Brand voice, strategy, research (read on session start)
│   ├── brand-voice.md
│   ├── utm-convention.md
│   ├── session-start.md
│   └── [strategy, psychology, competitors, SEO targets...]
├── skills/           ← 37 auto-activated SKILL.md engines
│   └── manifest.json  ← All trigger → skill mappings
├── agents/           ← 9 YAML configs for autonomous agents
│   ├── strategist.yml
│   ├── content-agent.yml
│   └── [7 more...]
├── outputs/          ← Generated content (date-stamped)
│   ├── blueprints/   ← Campaign blueprints
│   ├── content/      ← Social content, reels
│   ├── creatives/    ← Ad copy, creative briefs
│   ├── research/     ← Competitor analysis, audience, performance
│   ├── reports/      ← HTML weekly reports
│   ├── seo/          ← SEO audits, content, reports
│   └── social/      ← Content calendars
├── dashboards/       ← HTML monitoring dashboards
├── googleads/        ← Google Ads CSV data + configs
├── metaads/         ← Meta Ads CSV data
├── Image/           ← Creative assets (photos, graphics)
├── scripts/          ← Python data-pull scripts
├── state/           ← JSON data snapshots, campaign history
├── secrets/         ← Google OAuth JSON (never commit)
├── .claude/         ← Hooks, settings
│   └── settings.json  ← PostToolUse hook for auto-report-formatting
└── CLAUDE.md        ← This file's parent
```

---

## How to Run Things

### Full Campaign (say this)
```
"campaign output" / "full campaign" / "launch campaign" / "seasonal campaign"
```
→ 7-stage pipeline: brief → content waterfall → email → social calendar → paid ads → landing page → executive report

### SEO Pipeline (say this)
```
"SEO pipeline" / "end-to-end SEO" / "build SEO landing page"
```
→ 6-stage: audit → competitor SEO → brief → landing page → compliance → report

### Paid Ads Pipeline (say this)
```
"paid ads pipeline" / "ad creative pipeline" / "generate ad copy"
```
→ 6-stage: competitor ads → audience → meta copy → google copy → briefs → UTM audit

### Individual Agents
| Say this | Agent runs |
|----------|-----------|
| `run strategist` | Campaign blueprint builder |
| `run competitor-spy` | Full competitor analysis |
| `run audience-intel` | 5 ICP profiles |
| `run content-intel` | Viral content research |
| `run content-agent` | Social content, reels, ads |
| `run paid-ads` | Google + Meta ad copy |
| `run performance` | Weekly performance report |
| `run seo-agent` | SEO audit + strategy |
| `run research-agent` | Market trends + PESTLE/SWOT |

### Data Refresh
```bash
python scripts/pull_all.py            # Refresh all sources
python scripts/bake-weekly-report.py  # Generate weekly HTML report
```

---

## Model Configuration

| Task Type | Model | Source |
|-----------|-------|--------|
| Default content tasks | `minimax/minimax-m2.7` | OpenRouter |
| Subagents | `google/gemini-3-flash-preview` | OpenRouter (via `CLAUDE_CODE_SUBAGENT_MODEL`) |
| Heavy analysis/reports | `gemma4:31b-cloud` | Ollama localhost:11434 |

### Token Budget
- 0–60%: normal operation
- 60–75%: summarize older context
- 75–85%: use `/compact`
- 85%+: STOP and run `/compact`

---

## Excluded from Git

```
.env / .env.*
.claude/settings.json
secrets/
*.pem / *.key
state/*.json  ← live data snapshots
```

---

## Current System Status (2026-05-22)

**Operational:**
- ✅ 37 skills built and operational
- ✅ 9 agents configured (all tested)
- ✅ 3 pipeline orchestrators: campaign output, paid ads, SEO
- ✅ GA4 + GSC + Google Ads CSV + Meta Ads CSV live
- ✅ Weekly HTML report template deployed

**Remaining/Incomplete:**
- Apify, Screaming Frog, Ahrefs scripts written but need real API keys
- CB_Brain wiki updates not actively maintained (rules exist but lapsed)