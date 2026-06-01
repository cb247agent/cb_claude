# CB247 Competitor SEO Analysis — 2026-05-28
**Data sources:** Apify SERP (15 keywords, live), CB247-SEO-Auditor site crawl (43 pages)
**Competitors:** Revo Fitness (Malaga + Ellenbrook), Anytime Fitness (Malaga — SERP only, robots-blocked)

---

## 1. SERP Positioning Summary

| Keyword | CB247 | Revo | Anytime | Notes |
|---------|-------|------|---------|-------|
| "24/7 gym malaga perth" | **#1** | Not ranking | #2 (Instagram), #4 (global site) | CB247 owns this |
| "gym ellenbrook perth" | **#2** | **Not in top 9** | Not ranking | Revo absent — big opportunity to push to #1 |
| "chasing better gym malaga" | **#1** | — | — | Branded, expected |
| "chasingbetter247" | **#1** | — | — | Branded, expected |
| "revo fitness malaga" | Not ranking | #1 | — | Competitor branded |
| "anytime fitness malaga" | Not ranking | — | #1 | Competitor branded |
| "sauna gym perth" | **Not ranking** | Not ranking | Not ranking | Reddit thread #1 — content gap |
| "ice bath gym perth" | **Not ranking** | Not ranking | Not ranking | Reddit thread #1, Reclab #2 |
| "fifo gym membership perth" | **Not ranking** | Not ranking | Not ranking | Reddit #1, Movement Fitness #2 |
| "reformer pilates perth" | **Not ranking** | Not ranking | Not ranking | Dedicated studios dominate |
| "kids gym malaga" | **Not ranking** | Not ranking | Not ranking | Spanish "Malaga" dominates — wrong keyword |
| "gym malaga family" | **Not ranking** | Not ranking | #6 (Instagram) | Spanish results dominate — wrong keyword |
| "bath house malaga" | **Not ranking** | Not ranking | Not ranking | All Spanish results — wrong keyword entirely |

---

## 2. CB247 Site Audit — Critical Issues

### 🔴 Critical (Fix This Week)

**A. 29 pages missing H1 tags — including all key service pages**

Every money page on the site has no H1. This is the most impactful SEO fix available.

| Page | Title (exists) | H1 | Priority |
|------|---------------|-----|----------|
| /reformer-pilates | "Reformer Pilates at ChasingBetter247" | ❌ Missing | High |
| /kids-hub | "Kids Hub" | ❌ Missing | High |
| /personal-training | "Personal Training at ChasingBetter247" | ❌ Missing | High |
| /spin-classes | "Spin at ChasingBetter247" | ❌ Missing | Medium |
| /chasingrx-classes | "ChasingRX at ChasingBetter247" | ❌ Missing | Medium |
| /resources/fifo-members | "FIFO Members at ChasingBetter247" | ❌ Missing | Medium |
| /resources/post-workout-recovery | "Post-Workout Recovery at ChasingBetter247" | ❌ Missing | Medium |
| /neon21 | Long title | ❌ Missing | Medium |
| /casual-passes | Correct title | ❌ Missing | Lower |
| /book-a-tour | Correct title | ❌ Missing | Lower |

**B. 3 broken pages (404/error)**
- `/2026free` — returning error, likely a dead promo page
- `/personal-training/nhung-dam` — PT profile returning error
- `/personal-training/briana-peterson` — PT profile returning error

Action: Fix or redirect all 3 immediately.

**C. 2 pages with no meta description**
- `/job-roles/combat-based-coach---chasing-better`
- `/job-roles/personaltrainers`

---

### 🟠 High Priority

**D. Meta descriptions too long (>155 chars) on 17 pages**
Most affected: homepage, group fitness timetable, personal training, ChasingRX, spin classes.
Truncation in SERPs = lower CTR.

Homepage current (248 chars — way too long):
> "Discover ChasingBetter247, the premier health and fitness club in Perth. Enjoy 24/7 access to fully equipped gyms, top-quality free weights, ChasingRX, group classes (Yoga, Pilates, Spin), saunas, ice baths, and Perth's first Neon21 high-intensity group fitness classes."

Suggested (under 155 chars):
> "24/7 gym in Malaga & Ellenbrook from $11.95/wk. Sauna, ice bath, Kids Hub, Reformer Pilates, Neon21 + no lock-in. Perth's most premium budget gym."

**E. Duplicate meta descriptions — 8 pages**
Blog listing pages, about-us, and contact page all share the "contact us" meta description. Google will auto-generate snippets instead.

**F. Duplicate title tags — 7 pages**
Homepage with and without www, blog pages, and two job listing pages all share identical titles.

**G. Thin content (<200 words) on 21 pages**
Key thin pages:
- `/resources/fifo-members` — 144 words, no H1 — FIFO is a core differentiator
- `/casual-passes` — 167 words — conversion page
- `/massage` — 157 words
- `/resources/fitness-passport` — 67 words (almost no content)
- `/book-a-tour` — 118 words — conversion page

---

### 🟡 Medium Priority

**H. Zero schema markup across entire site (40 pages)**
Not a single page has LocalBusiness, GymOrHealthClub, FAQPage, or BreadcrumbList schema. Competitors running schema get rich snippets in SERPs.

Minimum to implement:
- `LocalBusiness` / `GymOrHealthClub` on homepage with both locations
- `FAQPage` on /faqs (1,649 words of FAQ content — perfect candidate)
- `Service` on reformer-pilates, kids-hub, personal-training

**I. 18 images missing alt text on /chasing-better-app**
App page has 18 images with no alt text — accessibility + image SEO gap.

---

## 3. Competitor Analysis

### Revo Fitness (Malaga + Ellenbrook)

**SERP Presence:**
- Dominates their branded keywords (#1 for "revo fitness malaga", "revo fitness ellenbrook")
- **Absent from "gym ellenbrook perth"** — CB247 is #2, Revo not in top 9. This is a major gap Revo will try to close.
- Revo Ellenbrook was recently upgraded (perthisok.com article confirms new studio space — they're investing in Ellenbrook)

**URL Structure:**
- Old: `revofitness.com.au/locations/malaga` → now redirects to `revofitness.com.au/gyms/malaga/`
- Updated URL structure suggests a recent site rebuild

**Technical (from crawl):**
Both Revo location pages are fully JavaScript-rendered — BeautifulSoup returns 0 content. This means:
- Their on-page SEO can't be assessed via static crawl
- They rely on JS rendering for all content — potential crawlability risk with Googlebot
- Load times: Malaga 1.5s, Ellenbrook 1.0s (slower than CB247's ~50ms average)

**Known intelligence (from SERP snippets + prior research):**
- Price: $9.69–$12.69/week (cheaper than CB247)
- 24/7 access, reformer pilates included
- Biggest threat in both suburbs

**Gap CB247 can exploit:** Revo's Ellenbrook absence from "gym ellenbrook perth" SERP is a window. CB247 should publish an Ellenbrook-specific landing page targeting this term before Revo fixes it.

---

### Anytime Fitness Malaga

**SERP Presence:**
- #1 for "anytime fitness malaga" (branded)
- #2 for "24/7 gym malaga perth" (Instagram account — strong social signal)
- Appears via Instagram on "gym malaga family" — social-driven visibility
- robots.txt blocks all automated crawlers — no direct page data available

**Key observation:**
Anytime Fitness's SERP visibility in Malaga is predominantly Instagram-driven, not website-driven. Their website ranks via the global US domain (anytimefitness.com/en-au/locations/...) rather than a local .com.au page. This is an SEO structural weakness CB247 can capitalise on with a strong local AU domain.

---

### Ryderwear Gym Malaga

- #1–#2 for "ryderwear gym malaga" (branded)
- #6 for "24/7 gym malaga perth"
- Positioned as lifters/powerlifting gym — different audience to CB247
- Price: $8.95/week (cheaper, but no premium facilities)
- Not a direct threat for family, FIFO, or recovery-focused members

---

## 4. Keyword Gaps — CB247's Untapped Opportunities

CB247 has unique features that no competitor offers. None of them are ranking in Google for those features.

| Feature | Current keyword used | Better keyword to target | Monthly intent |
|---------|---------------------|--------------------------|----------------|
| Sauna + ice bath | "bath house malaga" (❌ Spanish results) | "gym with sauna and ice bath perth" | High |
| Kids Hub | "kids gym malaga" (❌ Spanish results) | "gym with childcare perth northern suburbs" | High |
| FIFO freeze | "fifo gym membership perth" (not ranking) | "gym membership fifo workers perth" | Medium |
| Reformer Pilates | "reformer pilates perth" (not ranking) | "reformer pilates northern suburbs perth" | Medium |
| Ellenbrook | Generic | "24/7 gym ellenbrook" | High |

**Immediate action:** Fix keyword targeting on the FIFO page, kids-hub page, and recovery page to use the correct AU-specific terms. "Malaga" without "Perth" or "WA" returns Spanish results for most of these queries.

---

## 5. CB247 Strengths in Search

1. **Owns "24/7 gym malaga perth"** at #1 — the highest-intent local query
2. **Beats Revo Ellenbrook** in "gym ellenbrook perth" — Revo isn't even in top 9
3. **Strong branded search presence** — website + Instagram + Facebook + App Store all rank
4. **Homepage is well-optimised** — 914 words, good H1 ("24/7 Gym Memberships in Malaga and Ellenbrook"), 18 internal links, 66ms load time
5. **Blog content exists** — 4+ posts with good word counts (1,649-word FAQ, 1,211-word gym guide)

---

## 6. Priority Action Plan

### Week 1 — Quick Wins (Technical Fixes)
| Action | Pages | Impact |
|--------|-------|--------|
| Add H1 tags to all service pages | reformer-pilates, kids-hub, personal-training, spin, ChasingRX, FIFO, recovery | 🔴 Critical |
| Fix/redirect 3 broken pages | /2026free, /nhung-dam, /briana-peterson | 🔴 Critical |
| Shorten homepage meta description to <155 chars | Homepage | 🟠 High |
| Fix duplicate meta descriptions | Blog, about, contact pages | 🟠 High |

### Week 2 — Content Expansion
| Action | Target keyword | Page |
|--------|---------------|------|
| Expand FIFO page to 400+ words with correct keyword | "gym membership fifo workers perth" | /resources/fifo-members |
| Expand Kids Hub page with H1 and local keyword | "gym with childcare malaga perth" | /kids-hub |
| Expand recovery page with sauna + ice bath copy | "gym with sauna ice bath perth" | /resources/post-workout-recovery |
| Create Ellenbrook-specific landing page | "24/7 gym ellenbrook perth" | New page: /ellenbrook |

### Week 3 — Schema + Technical SEO
| Action | Pages |
|--------|-------|
| Add LocalBusiness schema with both locations | Homepage |
| Add FAQPage schema | /faqs |
| Add Service schema | reformer-pilates, personal-training, kids-hub |
| Fix 18 missing image alt texts | /chasing-better-app |

---

## 7. Revo Fitness — Watch List

Revo recently added studio space at Ellenbrook (perthisok.com confirmed). They will likely optimise their Ellenbrook page soon. CB247 has a window of ~4–8 weeks to consolidate the #2 position and push to #1 before Revo's SEO catches up.

**Recommended:** Publish a dedicated `/ellenbrook` landing page targeting "24/7 gym ellenbrook" before end of June.

---

*Generated: 2026-05-28 | Data: Apify SERP (live), CB247-SEO-Auditor v1.0 crawl | Compliance: AU Privacy Act 1988, Spam Act 2003, GDPR*
