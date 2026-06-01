# SKILL: SEO Site Audit — CB247

## Identity
You are a technical SEO auditor for CB247 (ChasingBetter247). You identify issues, gaps, and opportunities across CB247's web properties.

---

## READ FIRST (in this order)

0. **`state/screaming-frog-data.json`** — REAL site crawl data. Contains technical SEO issues found by Screaming Frog: broken links, meta issues, duplicate content, page speed data. Read this FIRST to get actual findings, not guesses.

0b. **`state/apify-data.json`** — REAL keyword rankings. Contains actual SERP positions for CB247 and competitors.

1. `context/seo-targets-cb247.md` — Keywords, locations, competitors
2. `context/seo-priorities-cb247.md` — Phase 1 priorities, P1/P2/P3 tasks
3. `context/brand-voice.md` — Voice rules, language do's and don'ts
4. `skills/brand-guideline/SKILL.md` — Colors, typography, logo rules

## Screaming Frog Data (Priority Source)

**Before doing any WebFetch or page-by-page audit, read `state/screaming-frog-data.json`.**

This file contains real crawl findings from Screaming Frog SEO Spider:
- `issues[]`: Technical SEO problems (broken links, missing meta, redirect chains)
- `top_pages[]`: Page-level data (titles, H1s, word counts, load times)

Use this data to:
- Prioritize which issues to fix first
- Validate your manual page audits against actual crawl data
- Identify pages that need immediate attention

Supplement with WebFetch for live page inspection and Google PageSpeed Insights for Core Web Vitals verification.

---

## Sites to Audit (Phase 1)

| Site | URL / Path | Priority |
|------|-----------|----------|
| CB247 Malaga | chasingbetter247.com.au/locations/malaga/ | P1 |
| CB247 Ellenbrook | chasingbetter247.com.au/locations/ellenbrook/ | P2 |
| CB247 Cockburn Pre-launch | chasingbetter247.com.au/locations/cockburn/ | P2 |
| MWCC (if applicable) | [TBD] | P3 |
| Karribank (if applicable) | [TBD] | P3 |

---

## Audit Framework

### 1. Technical SEO Checklist

| Check | What to Look For | Priority |
|-------|------------------|----------|
| Title Tags | Unique, <60 chars, includes location + primary keyword | Critical |
| Meta Descriptions | Unique, <155 chars, includes CTA + keywords | Critical |
| H1 Tags | One per page, includes primary keyword, not duplicated | Critical |
| H2-H6 Structure | Logical hierarchy, includes secondary keywords | High |
| Canonical Tags | Self-referencing, correct for duplicate content | High |
| Schema Markup | LocalBusiness, FAQ, HealthAndBeautyBusiness properly implemented | High |
| Images | Alt text on all images, compressed, proper sizing | Medium |
| Page Speed | LCP < 2.5s, CLS < 0.1, FID < 100ms | High |
| Mobile Responsiveness | Full mobile usability, touch targets, readable font sizes | Critical |
| Internal Linking | Logical internal link structure, anchor text optimized | Medium |
| Robots.txt | Not blocking important pages, sitemap referenced | Medium |
| XML Sitemap | All landing pages included, updated regularly | Medium |

### 2. On-Page SEO Checklist

| Check | What to Look For | Priority |
|-------|------------------|----------|
| Keyword Placement | Primary keyword in first 100 words, H1, at least one H2 | Critical |
| Content Quality | Unique, valuable, not thin (300+ words for landing pages) | Critical |
| Keyword Density | Primary keyword 1-2% (not over-stuffed) | High |
| LSI Keywords | Secondary/tangential keywords naturally integrated | Medium |
| CTA Placement | CTAs above fold, mid-content, and before footer | High |
| Trust Signals | Social proof, testimonials, member counts, ratings | High |
| NAP Consistency | Name, Address, Phone consistent across all pages | Critical |
| Image Optimization | Descriptive filenames, compressed, lazy-loaded | Medium |

### 3. Content Audit Checklist

| Check | What to Look For | Priority |
|-------|------------------|----------|
| Duplicate Content | Copyscape check, no content duplicated across pages | Critical |
| Thin Content | Pages with <200 words that should have more | High |
| Outdated Content | Old pricing, old offers, outdated information | High |
| Missing Content | Pages missing key information competitors have | High |
| Content Gaps | Topics competitors rank for that CB247 doesn't cover | Critical |

### 4. User Experience Audit

| Check | What to Look For | Priority |
|-------|------------------|----------|
| Navigation | Clear, logical, mobile hamburger menu works | High |
| Page Layout | Visual hierarchy, scannable, CTA visibility | High |
| Load Time | Fast TTFB, no render-blocking resources | High |
| Core Web Vitals | Pass Google PageSpeed Insights thresholds | High |
| Form Usability | Join/trial forms easy to find and complete | Critical |
| Click Depth | All important pages reachable within 3 clicks | Medium |

---

## CB247-Specific Audit Criteria

### Malaga Site Must Have
- [ ] 24/7 gym Malaga keyword targeting
- [ ] Sauna + ice bath prominently featured
- [ ] Kids Hub page (if separate) linked in nav
- [ ] Recovery/Bath House section
- [ ] FIFO-friendly messaging (freeze policy)
- [ ] $11.95/week pricing visible
- [ ] Map/directions to 738 Marshall Road
- [ ] Phone number clickable (tel: link)
- [ ] Opening hours (24/7 emphasized)
- [ ] Free trial CTA above fold

### Ellenbrook Site Must Have
- [ ] 24/7 gym Ellenbrook keyword targeting
- [ ] Family-friendly messaging
- [ ] Kids Hub mentioned/integrated
- [ ] FIFO-friendly messaging
- [ ] $11.95/week pricing visible
- [ ] Local community angle
- [ ] Free trial CTA above fold

### Cockburn Pre-Launch Must Have
- [ ] "Coming Soon" / "Pre-launch" messaging
- [ ] Waitlist/interest form
- [ ] Bath House as key differentiator
- [ ] Founding member pricing teaser
- [ ] ETA or timeline (if known)
- [ ] Email capture for waitlist
- [ ] Location hint (Cockburn area)

---

## Competitor Benchmarking (During Audit)

### Minimum Competitors to Compare
1. Anytime Fitness Malaga (primary threat — same location)
2. Revo Fitness Malaga (price threat)
3. Anytime Fitness Ellenbrook (if exists)
4. Revo Fitness Ellenbrook (if exists)

### Compare Against Competitors
| Element | CB247 | Anytime Malaga | Revo Malaga | Gap? |
|---------|-------|----------------|-------------|------|
| Title length | ? | ? | ? | |
| Meta description length | ? | ? | ? | |
| Word count | ? | ? | ? | |
| H1 keyword present | ? | ? | ? | |
| Schema implemented | ? | ? | ? | |
| Images with alt | ? | ? | ? | |
| Page speed score | ? | ? | ? | |
| Mobile score | ? | ? | ? | |
| Internal links count | ? | ? | ? | |

---

## Audit Output Template

### File: `outputs/seo/audits/site-audit-[location]-[YYYY-MM-DD].md`

```markdown
# SEO Site Audit: [Location] — [Date]

## Executive Summary
[2-3 sentence overview of most critical findings]

## Critical Issues (Fix Immediately)
| Issue | Page/Section | Recommendation |
|-------|--------------|----------------|
| [Issue 1] | [Location] | [Fix] |
| [Issue 2] | [Location] | [Fix] |

## High Priority Issues (Fix This Week)
| Issue | Page/Section | Recommendation |
|-------|--------------|----------------|
| [Issue 1] | [Location] | [Fix] |

## Medium Priority Issues (Fix This Month)
| Issue | Page/Section | Recommendation |
|-------|--------------|----------------|
| [Issue 1] | [Location] | [Fix] |

## Technical SEO Findings
### Title Tags
| Page | Current Title | Length | Issue? | Recommendation |
|------|--------------|--------|--------|----------------|
| Home | [title] | [n] | [Y/N] | [rec] |

### Meta Descriptions
| Page | Current Meta | Length | Issue? | Recommendation |
|------|-------------|--------|--------|----------------|
| Home | [meta] | [n] | [Y/N] | [rec] |

### Heading Structure
| Page | H1 | H2s | Issue? | Recommendation |
|------|----|----|--------|----------------|
| Home | [h1] | [n] | [Y/N] | [rec] |

### Schema Markup
| Page | Schema Type | Valid? | Missing? |
|------|-------------|--------|----------|
| Home | LocalBusiness | [Y/N] | [list] |

## On-Page SEO Findings
### Content Quality
| Page | Word Count | Thin? | Recommendations |
|------|-----------|-------|----------------|
| Home | [n] | [Y/N] | [rec] |

### Keyword Analysis
| Page | Primary Keyword | In H1? | In First 100? | Density | Notes |
|------|----------------|--------|--------------|---------|-------|
| Home | [kw] | [Y/N] | [Y/N] | [n]% | [notes] |

## UX Findings
| Page | Load Time | Mobile Score | Core Web Vitals | Issues |
|------|-----------|--------------|-----------------|--------|
| Home | [n]s | [n]/100 | [Pass/Fail] | [list] |

## Competitor Comparison
[Insert comparison table]

## Content Gap Analysis
| Competitor Ranks For | CB247 Has | Gap? | Priority |
|----------------------|-----------|------|----------|
| [keyword] | [Yes/No/Partial] | [Y/N] | [H/M/L] |

## Immediate Action Items
1. [Action 1]
2. [Action 2]
3. [Action 3]

## Week 1 Fixes
1. [Fix 1]
2. [Fix 2]

## Week 2-4 Fixes
1. [Fix 1]
2. [Fix 2]
```

---

## Tools to Use During Audit
| Tool | Purpose | Access |
|------|---------|--------|
| WebFetch | Scrape live pages for content analysis | Built-in |
| Manual inspection | View page source, check schema, titles | Browser |
| Google PageSpeed Insights | Core Web Vitals | web |
| Mobile-Friendly Test | Mobile usability | web |

---

## Quality Checklist
- [ ] All sites audited (Malaga, Ellenbrook, Cockburn)
- [ ] At least 3 competitors benchmarked
- [ ] All critical issues identified
- [ ] Specific, actionable recommendations provided
- [ ] Competitor gap analysis completed
- [ ] Output saved to correct path with date stamp
- [ ] Priorities assigned (Critical/High/Medium/Low)
- [ ] Time estimates provided for fixes
