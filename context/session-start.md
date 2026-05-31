# CB247 Session Start

## DO THIS FIRST
Read this file completely at the start of every session. It replaces re-explaining the project.
Then read `context/seasonal-calendar.md` and check:
- What campaign is ACTIVE right now?
- Is any event within 21 days? → spawn full campaign brief
- Is any event within 60 days? → flag as prep priority

After reading both files, confirm "CB247 context loaded. [Active campaign: X. Next event: Y in Z days.]"

---

## PROJECT STATE — 2026-05-27

### DONE — 37 Skills Built
**Foundation:** brand voice, UTM conventions, psychology triggers, competitor battle cards, marketing strategy, seasonal calendar, SEO targets/priorities, PESTLE/SWOT

**Content:** content writer, social analyst, viral content finder, content waterfall (1→14 assets), social content calendar (30-day), creative brief engine (AI prompts + storyboards), email funnel builder (4-email + 2-SMS sequences), member onboarding

**Ads:** ads manager (audiences), meta-ads-optimizer (12 ad variants across 4 ad sets), google-ads-optimizer (RSA, 7 keyword clusters, 3 campaigns), utm-standardizer (tagging + audit), competitor-ads-scraper

**SEO:** seo-site-audit, competitor-seo-scraper, seo-content-strategist, seo-landing-page-writer (full HTML), local-seo-optimizer, seo-reporting

**Analytics/Intel:** analytics-connector (GA4/GSC/Ads), performance-dashboard (FULL — GA4/GSC/Meta/Google Ads), audience-segmentation, market-intelligence, ab-testing-framework, compliance-checker

**Agents:** strategist (OPERATIONAL), agent-runner (full integration)

**Pipeline Orchestrators:**
- `seo-creative-pipeline` — 6-stage: audit → competitor SEO → content brief → landing page → compliance → report
- `paid-ads-creative-pipeline` — 6-stage: competitor ads → audience → meta ads → google ads → creative briefs → UTM audit
- `campaign-output-skill` — 7-stage: brief → content waterfall → email → social calendar → paid ads → landing page → executive report
- `report-formatter` — McKinsey-style executive reports

### DATA STATUS (2026-05-27)
| Source | Status | Location |
|--------|--------|----------|
| GA4 | ✅ LIVE | `state/ga4-data.json` (last pull: 2026-05-18) |
| GSC | ✅ LIVE | `state/gsc-data.json` (28-day, last pull: 2026-05-18) |
| Google Ads (CSV) | ✅ LIVE | `googleads/Google Ads {Malaga,Ellenbrook}/` through week 18–24 May |
| Meta Ads (CSV) | ✅ LIVE | `metaads/Malaga/Meta_Malaga.csv` · `metaads/Ellenbrook/Meta_Ellenbrook.csv` through 18–24 May |
| Combined Ads | ✅ PROCESSED | `state/ads-data.json` |
| Pull Script | ✅ OPERATIONAL | `scripts/pull_local_ads.py` (reads ISO weeks from daily rows) |

> ⚠️ Data is 9 days stale. Run `python scripts/pull_all.py` to refresh. Ad CSVs for 25–31 May not yet uploaded.

### REPORTS GENERATED
- `outputs/reports/cb247-weekly-report-2026-05-25.html` — **Latest weekly report** (warm-light theme, canonical template)
- `outputs/reports/cb247-weekly-report-2026-05-12.html` — Weekly report (61 KB, canonical design locked)
- `outputs/reports/cb247-weekly-report-2026-05-11.html` — **Canonical weekly report template** (warm-light, DM Serif Display, teal #00c4b4)
  - Sections: Executive Summary, GA4, GSC, Google Ads, Meta Ads, Key Insights
  - Google Ads: Malaga vs Ellenbrook location cards + 4-row prior-week comparison + 3-week combined trend
  - Meta Ads: location cards + 4-metric grid (Impressions/Reach/Clicks/CTR) + 2-week trend
  - Sticky nav, staggered KPI animations, bar-fill animations, print-ready, responsive; scroll offset 37px
- `outputs/seo/reports/seo-report-cb247-week-02.docx` — SEO Week 2 report (2026-05-27)
- `outputs/email-final-cost-estimation-2026-05-27.md` — Tool stack cost pitch for CEO/Manager ($355/mo for 5 locations)

### MISSING / INCOMPLETE
- Google Ads + Meta Ads CSVs for 25–31 May not yet uploaded (both Malaga + Ellenbrook)
- GA4/GSC data stale — last refresh 2026-05-18, run `python scripts/pull_all.py`
- Scripts (Apify, Screaming Frog, Ahrefs) — written but need real API keys
- CB_Brain wiki updates — rules exist but not actively maintained (ICP-Profiles.md empty)

### LAST SESSION (2026-05-27)
- Created root-level `CLAUDE.md` at `/Users/tiachasingbetter/Documents/ChasingBetter/CLAUDE.md`
- Generated cost estimation email for CEO/Manager: `outputs/email-final-cost-estimation-2026-05-27.md` (tool stack for 5 locations: $355/mo)
- Generated SEO Week 2 report: `outputs/seo/reports/seo-report-cb247-week-02.docx`
- Generated weekly performance report: `outputs/reports/cb247-weekly-report-2026-05-25.html`
- Generated system blueprint: `cb247-system-blueprint-2026-05-22.md`

### LAST SESSION (2026-05-12)
- Locked in canonical weekly report template (bake-weekly-report.py → 05-11 design):
  - Warm-light: `--bg: #f7f6f3`, `--green: #00c4b4`, `--text: #1a1a1e`
  - Cover page, sticky nav, channel bars, location cards, 6-card insight grid
  - GA4 mobile share computed from `devices` data; CTR row added to Google Ads cards
- Regenerated cb247-weekly-report-2026-05-12.html (61 KB)

---

## HOW TO RUN THINGS

### Pipeline Orchestrators (say one of these):
| Say this | Runs |
|---------|------|
| `campaign output` / `full campaign` / `launch campaign` / `seasonal campaign` | 7-stage: brief → waterfall → email → social → paid ads → landing page → report |
| `paid ads pipeline` / `ad creative pipeline` / `generate ad copy` | 6-stage: competitor → audience → meta copy → google copy → briefs → UTM audit |
| `SEO pipeline` / `end-to-end SEO` / `build SEO landing page` | 6-stage: audit → competitor SEO → brief → landing page → compliance → report |
| *(any `.md` saved to `outputs/`) | Auto-triggers `report-formatter` → McKinsey-style final report |

### Agents (say `run [name]`):
| Say this | Output |
|---------|--------|
| `run strategist` | Campaign blueprint → `outputs/blueprints/` |
| `run competitor-spy` | Competitor analysis → `outputs/research/competitor-full-analysis.md` |
| `run audience-intel` | 5 ICP profiles → `outputs/research/audience-analysis.md` |
| `run content-intel` | Viral content research → `outputs/research/content-intel.md` |
| `run content-agent` | Social content, reels, ads → `outputs/creatives/` |
| `run paid-ads` | Ad copy → `outputs/creatives/[campaign]/paid-ads/` |
| `run performance` | Weekly report → `outputs/research/performance-week-[N].md` |
| `run seo-agent` | SEO audit + strategy → `outputs/seo/` |
| `run research-agent` | Market trends → `outputs/research/` |

### Skill Triggers (include in any task):
- `write email` / `draft email` / `email sequence` → email funnel builder (4-email + 2-SMS sequences)
- `content waterfall` / `repurpose this` / `content repurposing` → content waterfall (1→14 assets)
- `social calendar` / `content plan` / `30-day content` → social content calendar
- `UTM audit` / `tag URLs` / `UTM tagging` → utm-standardizer
- `competitor ads` / `spy competitors` / `competitor analysis` → competitor-ads-scraper
- `site audit` / `SEO audit` / `technical SEO` → seo-site-audit
- `landing page` / `write page` / `build page` → seo-landing-page-writer (full HTML output)
- `A/B test` / `hypothesis` / `split test` → ab-testing-framework
- `compliance` / `check claims` / `legal check` → compliance-checker
- `brief` / `campaign brief` / `blueprint` → campaign-brief-engine
- `creative brief` / `storyboard` / `video script` → creative-brief-engine
- `market intel` / `competitor intel` / `market research` → market-intelligence

---

## KEY FACTS (don't re-explain these)
- CB247: Malaga + Ellenbrook, Perth WA | $11.95/week | no lock-in | 8,000+ members
- Brand color: #3FA69A (teal) | Tagline: AlwaysBetter
- Top competitors: Revo Fitness, Anytime Fitness, Snap Fitness, Ryderwear
- CB247 edge: Kids Hub + Sauna + Ice Bath + Reformer Pilates + 24/7 + FIFO freeze
- UTM: `utm_source=meta|google&utm_medium=paid_social|paid_search&utm_campaign=[objective]-[location]-[month]-[year]`
- All outputs: date-stamp as `filename-YYYY-MM-DD.md`, save to `outputs/`
- .md files in `outputs/` auto-format into executive reports via PostToolUse hook

---

## TOKEN BUDGET
- 0–60%: normal | 60–75%: summarize older context | 75–85%: use /compact | 85%+: STOP and run /compact
- If task is large: break into sub-tasks, complete and save each, use /compact between steps
- Keep responses concise — don't repeat what's in this file