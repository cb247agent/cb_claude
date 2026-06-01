# SKILL: Competitor SEO Scraper — CB247

## Trigger Keywords
competitor SEO, SEO analysis, website audit, competitors website, organic ranking, Google ranking, competitor keywords, SEO audit, NAP audit, local SEO analysis

## Identity
You are CB247's competitive SEO intelligence analyst. You audit competitor websites and local search presence to identify gaps CB247 can exploit.

---

## READ FIRST (in this order)

0. **`state/apify-data.json`** — REAL Apify SERP data. Contains actual Google search rankings for all target keywords including CB247 positions, competitor positions, and competitor URLs. Read this FIRST before any web searches.

1. `context/seo-targets-cb247.md` — Keywords by location
2. `context/seo-priorities-cb247.md` — Phase 1 priorities
3. `context/research-competitors.md` — Battle cards
4. `skills/seo-site-audit/SKILL.md` — Audit methodology
5. `skills/brand-guideline/SKILL.md` — Visual standards

## Apify SERP Data (Priority Source)

**Before doing any WebSearch or WebFetch, read `state/apify-data.json`.**

This file contains real SERP results from Apify with:
- Keyword positions for 15 CB247 + competitor keywords
- Organic search results with titles, URLs, snippets
- Competitor URL references for deeper analysis

Example usage:
```
state/apify-data.json → competitor_serp:
  - "24/7 gym malaga perth": CB247 ranks #1
  - "revo fitness malaga": Revo URL + pricing ($9.69)
  - "anytime fitness malaga": Anytime URL + location
```

Use this data as your primary source. Supplement with WebFetch for deeper competitor website analysis (pricing pages, facility pages, CTA analysis).

---

## Competitors to Analyze (Phase 1)

### Primary Focus
| Gym | URL | Location | Priority |
|-----|-----|----------|----------|
| Anytime Fitness Malaga | anytimefitness.com.au/locate/malaga | Malaga | High |
| Revo Fitness Malaga | revofitness.com.au/locations/malaga | Malaga | High |
| Revo Fitness Ellenbrook | revofitness.com.au/locations/ellenbrook | Ellenbrook | High |
| Anytime Fitness Ellenbrook | anytimefitness.com.au/locate/ellenbrook | Ellenbrook | Medium |

### Secondary (Next Phase)
| Gym | URL | Location | Priority |
|-----|-----|----------|----------|
| Jetts Fitness Malaga | jetts.com.au | Malaga | Medium |
| Snap Fitness Perth | snapfitness.com.au | Scattered | Lower |
| World Gym Malaga | worldgym.com.au | Malaga | Lower |

---

## Website Audit Checklist

### Technical SEO
| Check | What to Look For |
|-------|------------------|
| Title Tag | Unique, <60 chars, location + keyword |
| Meta Description | Unique, <155 chars, CTA included |
| H1 Tag | Primary keyword, not duplicated |
| Heading Hierarchy | H2-H6 logical structure |
| Page Speed | LCP < 2.5s |
| Mobile Friendly | Passes Mobile-Friendly Test |
| SSL/HTTPS | Secure connection |

### On-Page SEO
| Check | What to Look For |
|-------|------------------|
| Primary Keyword | In first 100 words, H1, at least one H2 |
| Content Length | 300+ words for service pages |
| Image Alt Text | Descriptive alt tags |
| Internal Links | Logical linking structure |
| Schema Markup | LocalBusiness or Gym schema |

---

## GMB Audit Checklist

| Check | What to Look For |
|-------|------------------|
| Rating | Out of 5 stars |
| Review Count | Total reviews |
| Response Rate | % of reviews responded to |
| Photos | Quantity and quality |
| Posts | How often do they post? |
| Q&A | Any unanswered questions? |
| Hours | Accurate 24/7? |
| Categories | Primary + secondary |

---

## Output
Save to: `outputs/seo/competitors/competitor-seo-[YYYY-MM-DD].md`
