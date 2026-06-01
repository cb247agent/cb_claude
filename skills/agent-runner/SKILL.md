# Agent Runner
Purpose: Invoke any of the 9 CB247 marketing agents via trigger phrases.

## How It Works
When user says "run [agent]" or matches a trigger phrase:
1. Match trigger → identify target agent YAML
2. Read the YAML config
3. **READ DATA FILES FIRST** — see Data Priority section below
4. Spawn the agent via the `Agent` tool with full context + data
5. Return completion signal when End condition is met

## Agent Catalog

| Agent | Trigger Phrases | Output |
|-------|----------------|--------|
| `strategist` | "run strategist", "build campaign", "campaign blueprint", "new campaign" | `outputs/blueprints/[name]-blueprint-YYYY-MM-DD.md` |
| `audience-intel` | "run audience-intel", "audience analysis", "ICP" | `outputs/research/audience-analysis.md` |
| `competitor-spy` | "run competitor-spy", "competitor research" | `outputs/research/competitor-full-analysis.md` |
| `content-agent` | "run content-agent", "generate content", "weekly content" | `outputs/content/` |
| `content-intel` | "run content-intel", "viral content", "trending content" | `outputs/research/content-intel.md` |
| `research-agent` | "run research-agent", "market research", "trend monitor" | `outputs/research/` |
| `paid-ads` | "run paid-ads", "google ads", "meta ads" | `outputs/creatives/[campaign]/paid-ads/` |
| `performance` | "run performance", "performance report", "KPI report", "weekly performance", "ad performance" | `outputs/research/performance-week-[N]-YYYY-MM-DD.md` + `outputs/reports/cb247-weekly-report-YYYY-MM-DD.html` |
| `seo-agent` | "run seo-agent", "SEO audit", "keyword research" | `outputs/seo/audits/`, `competitors/`, `content/`, `reports/` |

## Data Priority — Always Read These First

| Agent | Data Files to Read FIRST | Purpose |
|-------|-------------------------|---------|
| `competitor-spy` | `state/apify-data.json` | Real SERP rankings + competitor positions |
| `seo-agent` | `state/screaming-frog-data.json` + `state/apify-data.json` | Real crawl issues + keyword rankings |
| `research-agent` | `state/apify-data.json` + `state/ahrefs-data.json` | SERP data + backlink analysis |
| `performance` | `state/ga4-data.json` + `state/gsc-data.json` + `state/ads-data.json` | Live GA4, GSC, and combined Google+Meta ads data |
| `strategist` | `outputs/research/*.md` files + `state/ga4-data.json` + `state/gsc-data.json` | Research files + current traffic baseline |

**Rule**: Always read data files BEFORE doing WebSearch or WebFetch. Data files are the source of truth — web searches supplement only.

## Data Refresh Commands

Before running certain agents, refresh data:

| Agent | Command | Output |
|-------|---------|--------|
| All (full refresh) | `python3 scripts/pull_all.py` | `state/ga4-data.json`, `state/gsc-data.json`, `state/google-ads-data.json` |
| Ads (local CSVs) | `python3 scripts/pull_local_ads.py` | `state/ads-data.json` (Google Ads + Meta Ads from CSV exports) |
| SEO crawl | `python3 scripts/run_screaming_frog.py` | `state/screaming-frog-data.json` |
| SERP data | `python3 scripts/pull_apify.py` | `state/apify-data.json` |

## Execution Rules

1. **Always use minimax** — All agents configured for `minimax/minimax-m2.7`
2. **Read data files first** — Load `state/*.json` before starting any research
3. **Create missing directories** — Before writing, ensure output folders exist:
   - `outputs/content/` for content-agent
   - `outputs/creatives/[campaign]/paid-ads/` for paid-ads
   - `outputs/seo/audits/`, `outputs/seo/competitors/`, `outputs/seo/content/`, `outputs/seo/reports/` for seo-agent
   - `outputs/reports/` for performance reports
4. **Print End signal** — When agent completes, print the exact End message from YAML
5. **Update status.json** — For agents that update state/status.json (competitor-spy, strategist, performance), do so
6. **HTML report** — After running performance agent, also save the report as `outputs/reports/cb247-weekly-report-YYYY-MM-DD.html` (self-contained, no external dependencies except Chart.js CDN)

## Skills Available to Each Agent

| Agent | Skills Loaded |
|-------|--------------|
| strategist | seasonal-events, strategist |
| audience-intel | audience-segmentation |
| competitor-spy | competitor-ads-scraper, competitor-seo-scraper |
| content-agent | content-writer, brand-guideline |
| content-intel | viral-content-finder |
| research-agent | market-intelligence |
| paid-ads | meta-ads-optimizer, google-ads-optimizer, utm-standardizer |
| performance | performance-dashboard |
| seo-agent | seo-site-audit, competitor-seo-scraper, seo-content-strategist, seo-reporting |

## Prerequisites Per Agent

Before running certain agents, verify inputs exist:

- **paid-ads**: `outputs/blueprints/` must contain at least one blueprint file
- **strategist**: `outputs/research/` must contain research files first (competitor-full-analysis, pestle, swot, trends)
- **performance**: Run `python3 scripts/pull_local_ads.py` then `python3 scripts/pull_all.py` first to refresh all analytics + ads data
- **seo-agent**: Run `python3 scripts/run_screaming_frog.py` first to refresh crawl data
- **competitor-spy**: Run `python3 scripts/pull_apify.py` first to refresh SERP data

## HTML Report Generation (Performance Agent)

When generating a performance report, create TWO outputs:
1. **Markdown source** — `outputs/research/performance-week-[N]-YYYY-MM-DD.md` (editable)
2. **HTML deployment** — `outputs/reports/cb247-weekly-report-YYYY-MM-DD.html` (self-contained, consultant-style)

The HTML report should:
- Use CB247 brand color (#3FA69A) as primary accent
- Be fully self-contained (inline CSS + Chart.js from CDN)
- Include all 8 sections: Executive Summary, GA4, GSC, Google Ads, Meta Ads, Wins/Issues, Recommendations, Budget
- Be deployable immediately (just copy to web server or Netlify drop)