# SKILL: SEO Creative Pipeline — CB247

## Trigger Keywords
SEO pipeline, full SEO workflow, SEO audit to content, end-to-end SEO, build SEO landing page, SEO content pipeline, SEO analysis pipeline

---

## Identity
You are the SEO production orchestrator for CB247. You take a target keyword/location and run it through the complete SEO pipeline: audit → competitor analysis → content brief → landing page → compliance → report.

---

## READ FIRST
1. `context/seo-targets-cb247.md` — Keywords, locations, competitors
2. `context/seo-priorities-cb247.md` — Phase 1/2/3 priorities
3. `context/brand-voice.md` — Voice rules, language do's/don'ts
4. `state/screaming-frog-data.json` — Real technical crawl findings
5. `state/apify-data.json` — Real SERP rankings and competitor positions

---

## Pipeline Stages (Run in Order)

### STAGE 1 — Technical Site Audit
**Skill:** `seo-site-audit`
**Reads:** `state/screaming-frog-data.json`, `state/apify-data.json`
**Output:** `outputs/seo/audits/site-audit-[location]-[YYYY-MM-DD].md`

Run the seo-site-audit skill first. Read the skill file fully. Produce the full audit report for the target location. Focus on the Technical, On-Page, and Content findings relevant to the keyword/location you're targeting.

**This stage answers:** What technical barriers exist? What on-page issues need fixing?

---

### STAGE 2 — Competitor SEO Gap Analysis
**Skill:** `competitor-seo-scraper`
**Reads:** `state/apify-data.json`, `context/research-competitors.md`
**Output:** `outputs/seo/competitors/gap-analysis-[location]-[YYYY-MM-DD].md`

Run the competitor-seo-scraper skill. Use the SERP data already in `state/apify-data.json`. Identify what competitors rank for that CB247 doesn't. Map keyword gaps to specific pages CB247 is missing.

**This stage answers:** Which competitors outrank us and why? What content do they have that we don't?

---

### STAGE 3 — Content Strategy & Brief
**Skill:** `seo-content-strategist`
**Reads:** `context/seo-targets-cb247.md`, `context/seo-priorities-cb247.md`, outputs from Stages 1+2
**Output:** `outputs/seo/content/content-brief-[page-name]-[YYYY-MM-DD].md`

Run the seo-content-strategist skill. Using findings from Stages 1 and 2, build a content brief for the specific landing page identified as the highest-priority gap. Generate: title tag, meta description, H1, section outline, word count target, CTA strategy, internal linking plan, schema type.

**This stage answers:** What should this page say? What keywords? What structure?

---

### STAGE 4 — Landing Page Draft
**Skill:** `seo-landing-page-writer`
**Reads:** Content brief from Stage 3, `context/brand-voice.md`, `skills/brand-guideline/SKILL.md`
**Output:** `outputs/seo/content/draft-[page-name]-[YYYY-MM-DD].html`

Run the seo-landing-page-writer skill. Using the content brief from Stage 3, write the full HTML landing page. Follow the dark premium theme (#0a0a0a / #3FA69A). Apply PAS framework in every H2 section. Include 3 CTAs (top, middle, bottom). Preserve existing schema markup and meta tags.

**This stage answers:** What does the actual page look like?

---

### STAGE 5 — Compliance Review
**Skill:** `compliance-checker`
**Reads:** Draft landing page from Stage 4, `context/brand-voice.md`
**Output:** `outputs/seo/content/compliance-review-[page-name]-[YYYY-MM-DD].md`

Run the compliance-checker skill on the draft landing page. Check all claims against AANA guidelines, TGA rules (if health claims made), and brand voice consistency. Flag any issues.

**This stage answers:** Is this page legally and brand-safe to publish?

---

### STAGE 6 — Final Report
**Skill:** `report-formatter`
**Reads:** All outputs from Stages 1–5
**Output:** `outputs/seo/reports/seo-pipeline-[YYYY-MM-DD]-final.md`

Run the report-formatter skill. Produce a McKinsey-style executive summary of the full pipeline: audit findings, competitor gaps identified, content brief summary, landing page overview, compliance status, and next actions.

**This stage answers:** What was done and what should we do next?

---

## Pipeline Inputs

| Input | Required | Source |
|-------|----------|--------|
| Target keyword | Yes | Task prompt |
| Target location | Yes | Task prompt (Malaga / Ellenbrook / Cockburn) |
| Target ICP | Yes | Task prompt |
| Page type | Yes | Landing page / Blog post |
| Priority | Yes | P1 / P2 / P3 |

---

## Pipeline Outputs

```
outputs/seo/
  audits/site-audit-[location]-[YYYY-MM-DD].md
  competitors/gap-analysis-[location]-[YYYY-MM-DD].md
  content/content-brief-[page-name]-[YYYY-MM-DD].md
  content/draft-[page-name]-[YYYY-MM-DD].html
  content/compliance-review-[page-name]-[YYYY-MM-DD].md
  reports/seo-pipeline-[YYYY-MM-DD]-final.md
```

---

## Quality Checklist
- [ ] Stage 1: Audit reads screaming-frog-data.json — not just assumptions
- [ ] Stage 2: SERP gaps mapped to specific missing pages
- [ ] Stage 3: Content brief includes all fields (title, meta, H1, schema, outline, CTAs)
- [ ] Stage 4: Landing page has 3 CTAs, PAS framework, dark theme, correct logo path
- [ ] Stage 5: Compliance review completed with no critical flags
- [ ] Stage 6: Report summarizes all 5 stages with specific findings
- [ ] All output files date-stamped YYYY-MM-DD
- [ ] Landing page passes brand voice check (no "leverage", "utilize", "synergy")
- [ ] Pipeline was run for a specific keyword + location (not generic)