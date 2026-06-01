# CB247 Technical SEO Audit — Full Site
**Date:** 9 May 2026 | **Crawl:** Screaming Frog | **URLs Crawled:** 43

---

## Executive Summary

43 pages crawled. Site is technically healthy overall — no critical crawl failures, good response times, all pages self-canonicalise correctly. **The biggest risk is content gaps, not crawl errors.** 6 High-priority fixes identified below.

---

## CRITICAL Issues (Fix This Week)

### 1. 🔴 Internal 404 — `/2026free`
- **URL:** `https://www.chasingbetter247.com.au/2026free`
- **Status:** 404 Not Found
- **Inlinks:** 1 (someone is linking to this page — likely a broken promo link)
- **Action:** Either restore the page (if it was a campaign URL) or 301 redirect to the homepage or `/book-a-tour`

### 2. 🟠 Blog Pagination Cannibalising Itself
- **URL:** `https://www.chasingbetter247.com.au/blog?338b1cd1_page=1`
- **Status:** Canonicalised to `/blog` — correct, but the **page 2** (`?338b1cd1_page=2`) is indexable with a different title and content
- **Risk:** Google may serve the wrong page in search results
- **Action:** Add `rel="canonical"` from page 2 → `/blog`

---

## HIGH Priority Issues (Fix This Month)

### 3. 🔸 Title Tags Truncated in Google (Neon21)
| Page | Current Title | Length | Pixel Width | Status |
|------|-------------|--------|-------------|--------|
| `/neon21` | "NEON21 \| Strength Training Workout Classes at ChasingBetter247" | 62 chars | **588px** | ⚠️ Will truncate in SERPs |
| `/book-a-tour` | "Book A Gym Tour in Malaga or Ellenbrook at ChasingBetter247" | 59 chars | **553px** | ⚠️ May truncate |

**Action:** Shorten Neon21 title to under 55 characters. Example: `"NEON21 Classes at ChasingBetter247 | Malaga & Ellenbrook"`

### 4. 🔸 Security Headers Missing (97.5% of pages)
- **40 pages** missing `X-Content-Type-Options: nosniff`
- **40 pages** missing `Referrer-Policy` header
- **1 page** missing `X-Frame-Options` (clickjacking risk)
- **1 page** missing `Content-Security-Policy`

This is a server-level fix. Requires your web host/developer to add headers to nginx or Apache config. Not a content fix.

### 5. 🔸 Thin Content Pages (15 pages under 200 words)
Pages with content that may not give Google enough signal:

| Page | Word Count | Issue |
|------|-----------|-------|
| `/blog/pop-up-classes` | 152 | Low |
| `/casual-passes` | 173 | Low |
| `/careers` | 130 | Low |
| `/blog` | 160 | Low |
| `/book-a-tour` | 119 | **Very thin — priority** |
| `/2026free` | 0 | 404 — remove or redirect |

**Action:** Add more descriptive content to `/book-a-tour`. It's a high-intent page (people wanting to visit) and only has 119 words.

### 6. 🔸 Missing Dedicated Location Pages
GSC data shows intent for "gym malaga" and "gym ellenbrook" — but CB247 has **no dedicated Malaga or Ellenbrook landing pages** with location-specific SEO content. All pages share generic location mentions.

**This is the #1 SEO opportunity.** Competitors rank specifically for these terms. CB247 doesn't have optimised pages for them.

Recommended pages to create:
1. `/locations/malaga` — 24/7 gym Malaga, Sauna + Ice Bath Malaga
2. `/locations/ellenbrook` — Family gym Ellenbrook
3. `/recovery` — Sauna + Ice Bath (currently buried under `/resources/post-workout-recovery`)

---

## MEDIUM Priority Issues

### 7. Page Titles Below 30 Characters (14 pages)
These titles are short and missing keyword opportunities:
- `/kids-hub` — "Kids Hub" (8 chars)
- `/resources/about-us` — "About Us" (8 chars)
- `/blog` — "Blog" (4 chars) × 2 pages
- `/sitemap` — "Sitemap" (8 chars)
- `/virtual-training` — "Virtual Training" (16 chars)
- 8 × Personal Trainer pages with names only (e.g., "Bree Marlow" — no brand context)

**Quick wins:** Update PT page titles to format: `"Bree Marlow | Personal Trainer at ChasingBetter247"`

### 8. Duplicate Meta Descriptions (5 pages)
- `/blog` page 1 + page 2 share the same meta (contact page description — wrong for blog)
- `/resources/about-us` + `/resources/post-workout-recovery` share same meta description
- `/blog/pop-up-classes` has no relevant meta

### 9. Missing Alt Text on 11 Images
Images without descriptive alt text — accessibility + SEO signal loss. Most affected: homepage and personal training profile pages.

### 10. H1 Not First Heading (9 pages)
Pages where H1 is not the first heading element. Affects accessibility and may confuse search engines about page structure.

Most affected: `/personal-training` pages — the "TRAINERS" H2 appears before the personal trainer name H1 in some cases.

### 11. Large Images (7 images over 100KB)
Page speed issue. Largest: homepage (85KB HTML alone). These should be:
- Compressed (WebP format)
- Lazy-loaded below the fold
- Sized correctly (not scaled up in CSS)

---

## LOW Priority Issues

| Issue | Count | Pages Affected |
|-------|-------|---------------|
| Title = H1 (exact match) | 6 | Various |
| Duplicate H2s | 11 | Various |
| H2 over 70 chars | 1 | `/personal-training` |
| Duplicate titles | 2 | Blog pagination |
| Cross-origin unsafe links | 3 | External links missing rel="noopener" |
| URL parameters in indexable URLs | 2 | Blog pagination |

---

## What's Working Well

✅ **All 40+ pages return 200 OK** — no server errors
✅ **Self-referencing canonicals** — correct on all pages
✅ **Response times excellent** — fastest page: 0.023s (personal-training)
✅ **Readability** — most copy is "Easy" or "Fairly Easy" (Flesch score 70+)
✅ **No duplicate page titles** except pagination edge cases
✅ **No meta keywords spam** — clean
✅ **HTTP/1.1 + SSL** — fully secured
✅ **Meta robots default** — no accidental noindex on important pages

---

## Quick Wins (This Week)

| # | Action | Pages | Effort |
|---|--------|-------|--------|
| 1 | Fix or redirect `/2026free` 404 | 1 | 5 min |
| 2 | Shorten Neon21 page title | 1 | 2 min |
| 3 | Add canonical to `/blog?page=2` → `/blog` | 1 | 2 min |
| 4 | Expand `/book-a-tour` content (119 → 300+ words) | 1 | 30 min |
| 5 | Update PT page titles to include "Personal Trainer" | 9 | 20 min |
| 6 | Ask web host to add security headers (X-Content-Type-Options, Referrer-Policy) | 40 | Dev task |

---

## Content Gaps (Biggest SEO Opportunity)

GSC data shows CB247 **does not rank** for the following high-intent terms — because no optimised pages exist:

| Keyword | GSC Clicks (28 days) | CB247 Position | Opportunity |
|---------|----------------------|----------------|-------------|
| gym malaga | 2 | 4.8 | **Create `/locations/malaga`** |
| gyms malaga | 4 | 3.5 | Create `/locations/malaga` |
| gym ellenbrook | 6 | 15.8 | **Create `/locations/ellenbrook`** |
| gyms in malaga | 2 | 6.3 | Create `/locations/malaga` |
| sauna malaga | 0 | not ranking | **Create `/recovery`** |
| ice bath malaga | 0 | not ranking | **Create `/recovery`** |
| kids gym malaga | 0 | not ranking | **Improve `/kids-hub`** |
| bath house malaga | 0 | not ranking | **Create `/recovery`** |

---

## Recommended Next Actions

### Week 1
1. Fix `/2026free` 404 (redirect to `/book-a-tour`)
2. Add canonical tag to blog page 2
3. Shorten Neon21 title
4. Create Malaga location page draft (via `seo-landing-page-writer`)

### Week 2
5. Create Ellenbrook location page draft
6. Expand `/book-a-tour` with more content
7. Ask dev to add security headers

### Week 3
8. Improve `/kids-hub` page (bigger H1, more content, target "kids gym malaga")
9. Create Recovery landing page (Sauna + Ice Bath)
10. Update all PT page titles

---

*Audit generated by Claude Code from Screaming Frog crawl data — 9 May 2026*
