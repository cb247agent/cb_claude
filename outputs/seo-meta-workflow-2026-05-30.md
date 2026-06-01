# CB247 Workflow — SEO & Meta Ads (Data → Analysis → Output)
_Last updated: 2026-05-30_

End-to-end map of how data flows from source → analysis → deliverables (**draft blogs**, **dashboards**, **weekly reports/email**, **Notion**). Reflects the real current state of `scripts/`, `state/`, `skills/`, `outputs/`.

---

## 0. The Big Picture

```
 SOURCES                     RAW DATA (state/*.json)         ANALYSIS               OUTPUTS
 ───────                     ───────────────────────         ────────               ───────
 GA4, GSC          (API)     ga4-data, gsc-data                                     outputs/seo/      (blog drafts)
 Google Ads        (API)     google-ads-data                 skills + agents        dashboards/       (command center HTML)
 GBP               (API)     gbp-data                  ──►    read + reason   ──►    outputs/reports/  (weekly HTML + email)
 Ahrefs            (API)     ahrefs-data                                            Notion            (dashboard + sub-pages)
 Apify SERP/Maps/Social      apify-data, social-trends                              CB_Brain/wiki     (learnings)
 Meta Ads          (CSV!)    meta-ads-data, ads-data
 Site crawl        (crawler) screaming-frog-data
```

**SEO/API data, one command:** `python scripts/pull_all.py`
→ GA4 → GSC → Google Ads → GBP → Ahrefs → Apify, then **auto-bakes the dashboard**.
**Meta is CSV-based and separate** (see §2). **Site crawl** runs in the weekly-SEO job.

---

## 1. SEO WORKFLOW

### Step 1 — Pull the data
| Script | Source | Saves to |
|--------|--------|----------|
| `pull_gsc.py` | Search Console (API) | `state/gsc-data.json` — queries, impressions, clicks, CTR, position |
| `pull_ga4.py` | GA4 (API) | `state/ga4-data.json` — sessions, conversions, sources, top pages |
| `pull_ahrefs.py` | Ahrefs API v3 | `state/ahrefs-data.json` — Domain Rating, organic keywords, backlinks, refdomains |
| `pull_apify.py` | Apify | `state/apify-data.json` + `state/social-trends.json` |
| `pull_gbp.py` | Google Business Profile | `state/gbp-data.json` — local listing performance |
| `run_site_crawl.py` | Privacy-compliant crawler (replaced Screaming Frog) | `state/screaming-frog-data.json` — technical SEO; `--competitors` also crawls Revo/Anytime |

`pull_apify.py` runs **three sub-pipelines**:
1. **SERP** — organic + local-pack rankings (CB247 + competitor keywords)
2. **Google Maps** — competitor GBP benchmark (rating, reviews, photos, completeness)
3. **Social trends** — TikTok + Instagram fitness hashtags → top posts by weighted engagement + trending hashtags → `social-trends.json`

➡️ Run all API SEO sources at once: `python scripts/pull_all.py`

### Step 2 — Analyse (skills/agents read the JSON and reason)
There is no separate "analysis script" — intelligence lives in the skills:
- **`seo-site-audit`** — reads gsc + screaming-frog-data → technical audit, fixes
- **`seo-content-strategist`** / `seo-agent` — gsc + ga4 → keyword gaps, opportunity keywords (high impressions / low rank = quick wins)
- **`seo-blog-generator`** — reads `gsc-data.json`, `ga4-data.json`, **`social-trends.json`**, `context/brand-voice.md`, `context/seo-targets-cb247.md` → picks topic + trend hook
- **`competitor-seo-scraper` / `competitor-spy`** — `apify-data.json` (Maps + SERP) → competitive positioning
- **`local-seo-optimizer`** — `gbp-data.json` + Maps benchmark → GBP optimisation
- Cadence: 4-week topic rotation (Fitness Tips → Local Community → Competitor Comparison → Data-Driven)

### Step 3 — Outputs

**A) Draft blog** — trigger `/blog` (or "run seo-agent")
- Engine: `seo-blog-generator` skill + `seo_blog_scheduler.py`
- **Mandatory in every blog now:** ≥2 **cited scientific facts** (+ `## SOURCES`, no fabricated stats) and a **current social trend hook** from `state/social-trends.json` (fallback: web search)
- Output: `outputs/seo/blog-[topic]-YYYY-MM-DD.md` (or `.html` in `outputs/seo/content/`); `PostToolUse` hook makes a `-final.md`
- Live examples: `blog-best-gym-malaga-2026-05-30.md`, `blog-fifo-24-7-gym-2026-05-11.html`

**B) Dashboard** — `bake-dashboard.py` (auto-runs at end of `pull_all.py`)
- Reads ga4 + gsc + google-ads **+ ahrefs + apify** → `dashboards/cb247-command-center.html` (SEO Intel block: DR, top keywords, local pack, Maps benchmark)

**C) Weekly SEO report** — `bash scripts/weekly-seo.sh`
- `pull_all.py` → `run_site_crawl.py --competitors` → `pull_ahrefs.py` → `pull_apify.py` → `generate_seo_report.py` → `send_seo_report.py` (email)

---

## 2. META ADS WORKFLOW

> **Meta is NOT an API pull — it's CSV-based.** Export weekly Meta Ads reports from Meta Ads Manager and drop them into the `metaads/` folder.

### Step 1 — Get the data in
1. Export Meta Ads CSVs → place in `metaads/` (combined `metaads/metaads.csv`, and/or per-location under `metaads/Malaga/`, `metaads/Ellenbrook/`)
2. Parse them:
   - `python scripts/pull_ads_data.py` → parses `metaads/metaads.csv` (+ Google Ads CSVs) → `state/meta-ads-data.json` (+ `state/google-ads-data.json`)
   - `python scripts/pull_local_ads.py` → unified `state/ads-data.json` (Google + Meta) for the dashboard/performance agent
- Requires no token — purely CSV → JSON.

### Step 2 — Analyse
- **`meta-ads-optimizer`** — reads `meta-ads-data.json` → spend, CPM, CTR, CPL by campaign/ad/location; flags under/over-performers; budget reallocation
- **`ads-manager` / `performance-dashboard`** — combined Google + Meta view from `ads-data.json`
- **`competitor-ads-scraper`** — competitor Meta creative/positioning
- Pre-req for new copy: a campaign blueprint in `outputs/blueprints/`

### Step 3 — Outputs
**A) Ad creative / copy** — "run paid-ads" or `paid ads pipeline` (6-stage: competitor ads → audience → meta copy → google copy → creative briefs → UTM audit)
- Output: `outputs/creatives/[campaign]/paid-ads/meta-ads-complete.md`
- UTMs follow `context/utm-convention.md` (`utm_source=meta`, `utm_medium=paid_social`, `utm_campaign=[objective]-[location]-[month]-[year]`)

**B) Dashboard + weekly report** — `bake-weekly-report.py` builds a **Meta Ads section** (`build_meta_ads_section` / `build_meta_ads_campaigns`) from `meta-ads-data.json` → Malaga + Ellenbrook KPI cards, spend, ad-level table, week-over-week trend.

---

## 3. AUTOMATION & CADENCE (cron, Mondays 11am AWST)

| Job | Wrapper | Pipeline |
|-----|---------|----------|
| Data refresh | `run-refresh.sh` | `pull_all.py` (+ auto dashboard bake) |
| **Weekly performance report** | `weekly-report.sh` | `pull_all.py` → `bake-weekly-report.py` → `send_weekly_report.py` (email) → `push_to_notion.py` → `push_dashboard.py` (Notion) |
| **Weekly SEO report** | `weekly-seo.sh` | `pull_all.py` → `run_site_crawl.py --competitors` → `pull_ahrefs.py` → `pull_apify.py` → `generate_seo_report.py` → `send_seo_report.py` |
| Weekly blog | `/blog` | `seo-blog-generator` → `outputs/seo/blog-*.md` |
| Meta refresh | _manual_ | drop CSV in `metaads/` → `pull_ads_data.py` + `pull_local_ads.py` |

---

## 4. KNOWN GAPS / NEXT IMPROVEMENTS
1. **Meta CSV step is manual & not in `pull_all.py`.** `weekly-report.sh`'s comment says it pulls "Meta Ads," but `pull_all.py` does **not** parse Meta — the weekly report relies on `meta-ads-data.json` already existing from a prior `pull_ads_data.py` run. ✅ *Fix option:* add `pull_ads_data.py` to `pull_all.py` (or to `weekly-report.sh` step 1.5) so the latest dropped CSVs are always parsed before baking.
2. **Meta could move to the Graph API** for full automation (no manual CSV export) — not built yet.
3. **SERP local-pack presence** returns low/None (Apify SERP actor limitation); the Maps pipeline covers competitor benchmarking instead.
4. **Social trends skew global** — add AU hashtags (`#perthgym`, `#fitnessaustralia`) to `SOCIAL_HASHTAGS` for local signal.
5. **Two slightly different ads parsers** exist (`pull_ads_data.py` → `meta-ads-data.json`; `pull_local_ads.py` → `ads-data.json`) — worth consolidating to avoid drift.

---

## 5. QUICK REFERENCE — file map
```
scripts/
  pull_all.py            → SEO API pulls (GA4/GSC/GAds/GBP/Ahrefs/Apify) + bakes dashboard
  pull_gsc / ga4 / ahrefs / apify / gbp .py     → SEO data (API)
  run_site_crawl.py      → privacy-compliant technical crawl
  pull_ads_data.py       → metaads/metaads.csv + Google CSV → meta-ads-data.json / google-ads-data.json
  pull_local_ads.py      → Google + Meta CSV → unified ads-data.json
  bake-dashboard.py      → dashboards/cb247-command-center.html (SEO Intel + Ads)
  bake-weekly-report.py  → outputs/reports/cb247-weekly-report-*.html (SEO Intel + Meta section)
  generate_seo_report.py / send_seo_report.py / send_weekly_report.py
  push_to_notion.py / push_dashboard.py         → Notion sync
  seo_blog_scheduler.py  → blog generation runner
  *.sh                   → run-refresh / weekly-report / weekly-seo (cron)
state/*.json             → data snapshots (never commit)
metaads/                 → Meta Ads CSV exports (Malaga/, Ellenbrook/, metaads.csv)
skills/                  → seo-blog-generator, seo-content-strategist, seo-site-audit,
                           local-seo-optimizer, seo-reporting, meta-ads-optimizer,
                           google-ads-optimizer, ads-manager, performance-dashboard,
                           competitor-seo-scraper, competitor-ads-scraper, compliance-checker
outputs/seo/             → blog drafts        outputs/creatives/ → ad copy
outputs/reports/         → weekly reports     dashboards/        → command center
CB_Brain/wiki/           → SEO-Learnings.md, Campaign-History.md, Agent-Learnings.md
```
```
SEO loop:  pull_all → state/*.json → seo-blog-generator/seo-agent → outputs/seo + dashboard + weekly-seo email → wiki
Meta loop: CSV → pull_ads_data → meta-ads-data.json → meta-ads-optimizer/paid-ads → outputs/creatives + weekly report → wiki
```
