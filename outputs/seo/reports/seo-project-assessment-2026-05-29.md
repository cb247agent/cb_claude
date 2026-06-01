# CB247 SEO Project Assessment — 2026-05-29
**Goal: Improve organic traffic + reduce Google Ads spend**
**Data sources:** GA4 (May 18–24), GSC (May 18–24), Google Ads CSV (Apr 20–May 24), SERP crawl (May 28), Site crawl (May 28)

---

## Executive Summary

The project has excellent infrastructure — data pipelines, content drafts, analysis tools, and a 3-week action plan — but is **stuck at the analysis stage**. None of the SEO fixes that would grow organic traffic have been implemented on the actual website. Until they are, organic traffic will not grow and Google Ads spend cannot be reduced. This report maps exactly what is done, what is not, and what to do first.

---

## 1. Where We Are vs. the Goal

### Google Ads Spend (5 weeks, Apr 20–May 24)
| Week | Malaga Spend | Ellenbrook Spend | Combined | CPA |
|------|-------------|-----------------|---------|-----|
| Apr 20–26 | $332.71 | $260.97 | **$593.68** | $18.55 |
| Apr 27–May 3 | $301.38 | $256.85 | **$558.23** | $22.33 |
| May 4–10 | $314.58 | $295.34 | **$609.92** | $32.10 |
| May 11–17 | $316.58 | $295.64 | **$612.22** | $43.73 |
| May 18–24 | $316.24 | $241.44 | **$557.68** | $19.92 |

**Monthly Google Ads spend: ~$2,500–$2,450/month**. CPA target is $20. We hit it only 2 out of 5 weeks.

### Campaign CPA Breakdown (Latest Week May 18–24)
| Campaign | Spend | Conversions | CPA | Status |
|----------|-------|-------------|-----|--------|
| Gym Geo | $276.12 | 23 | **$12.01** ✅ | Working — keep |
| Malaga Gym | $153.17 | 2 | **$76.58** ❌ | 4× over target — pause/restructure |
| Ellenbrook Gym | $128.39 | 3 | **$42.80** ⚠️ | 2× over target — optimise |

### Organic Traffic (week May 18–24, GA4)
| Channel | Sessions | Conversions | CVR |
|---------|---------|-------------|-----|
| Paid Social | 1,193 | 3 | **0.25%** ❌ |
| Organic Search | 941 | 87 | **9.2%** ✅ Best channel |
| Direct | 606 | 270 | 44.6% (existing members) |
| Paid Search | 216 | 31 | 14.4% |

**Key finding:** Organic Search converts at 9.2% — the best non-direct channel. Paid Social converts at 0.25%. Every session gained organically is worth 37× a paid social session.

### GSC Non-Branded Clicks (week May 18–24)
| Query | Clicks | Impressions | Position |
|-------|--------|-------------|----------|
| gyms malaga | 2 | 19 | 1.8 |
| gym ellenbrook | 1 | 39 | **4.2** |
| ellenbrook gyms | 1 | 17 | 4.0 |
| crossfit | 1 | 6 | 2.0 |
| gym malaga | 1 | 19 | 1.8 |

Non-branded organic is nearly invisible. Almost all 941 organic sessions come from existing members searching the brand name. **This is why we can't reduce paid spend yet — organic isn't replacing it.**

---

## 2. What Is Done (Assets Ready to Deploy)

### ✅ Technical Audit Complete
- 29 pages with missing H1 tags identified
- 3 broken 404 pages identified
- 0 schema markup on 40 pages confirmed
- 21 thin content pages identified
- 17 meta descriptions too long identified

### ✅ Content Drafted — Ready to Publish
These pages are written and sitting in `outputs/seo/content/` — none are live yet:
| Draft File | Target Keyword | Status |
|-----------|---------------|--------|
| `draft-24-7-gym-ellenbrook-page.html` | "24/7 gym ellenbrook perth" | ✅ Ready |
| `draft-24-7-gym-malaga-page.html` | "24/7 gym malaga perth" | ✅ Ready |
| `draft-kids-hub-malaga-page.html` | "gym with childcare malaga perth" | ✅ Ready |
| `draft-recovery-hub-malaga-page.html` | "gym with sauna ice bath perth" | ✅ Ready |
| `draft-gym-bath-house-cockburn-prelaunch-page.html` | "gym cockburn" | ✅ Ready |
| `blog-fifo-24-7-gym-2026-05-11.html` | "gym membership fifo workers perth" | ✅ Ready |
| `comparison-cb247-vs-revo.html` | "best gym malaga" comparison | ✅ Ready |
| `faq-page-cb247.html` | FAQ schema candidate | ✅ Ready |

### ✅ SEO Analysis Complete
- Competitor SERP positions confirmed (May 28 live data via Apify)
- Keyword gap analysis done
- CB247 owns #1 for "24/7 gym malaga perth"
- CB247 is #2 for "gym ellenbrook perth" (Revo not in top 9 — 4–8 week window)

### ✅ System Infrastructure
- GA4, GSC, Google Ads CSV pipelines operational
- 37 skills built (SEO, content, ads, analytics)
- 9 agents operational
- Weekly report auto-generation working

---

## 3. What Is NOT Done (Critical Gaps)

### 🔴 On-Site Technical Fixes — None Implemented
Every fix below costs $0 and is high impact. None have been done.

| Fix | Pages Affected | Impact |
|-----|---------------|--------|
| Add H1 tags | 29 pages (all service pages) | Critical — Google can't identify page topic |
| Fix 3 broken pages | /2026free, /nhung-dam, /briana-peterson | High — crawl errors + bad UX |
| Shorten homepage meta desc | 1 page (248 → <155 chars) | High — CTR improvement |
| Fix duplicate meta descriptions | 8 pages | Medium |
| Add LocalBusiness schema | Homepage | Medium — rich snippets |
| Add FAQPage schema | /faqs | Medium — rich snippets |
| Fix 18 missing alt texts | /chasing-better-app | Medium |

### 🔴 Content Not Published — Zero New Organic Pages Live
All the content drafts above exist locally. None have been published to the CB247 website. Until these go live, Google cannot rank them.

### 🔴 Keyword Targeting Errors — Not Fixed
Three key pages target Spanish "Malaga" instead of Perth WA:
- "kids gym malaga" → should be "gym with childcare malaga perth"
- "bath house malaga" → should be "gym with sauna ice bath perth"
- "gym malaga family" → dominated by Spanish results, wrong market

### 🔴 Google Ads — Underperforming Campaign Not Fixed
- "Malaga Gym" campaign: $153/week, CPA $76.58 (4× over $20 target)
- Recommendation from May 28 audit: pause or restructure. Still running.
- Fix: Either pause and redirect budget to "Gym Geo" (CPA $12.01), or restructure with new ad copy targeting non-branded terms only.

### 🟠 Data/Tooling Gaps
| Tool | Status | Impact |
|------|--------|--------|
| Google Ads API | ❌ Missing credentials (GOOGLE_ADS_DEVELOPER_TOKEN, GOOGLE_ADS_CUSTOMER_ID) | Can't automate campaign monitoring |
| Ahrefs API | ❌ No API key in .env | No backlink data, no rank tracking for 5 sites |
| Data freshness | ⚠️ GA4/GSC stale 9+ days | Reports show old data |
| Weekly automation | ⚠️ Scripts exist but not scheduled | Reports not auto-running weekly |

---

## 4. Priority Action Plan

### IMMEDIATE (This Week) — Highest ROI Actions

**A. Pause "Malaga Gym" Campaign**
- Save ~$153/week ($612/month) immediately
- Redirect budget to "Gym Geo" campaign (CPA $12.01 — proven efficient)
- This alone reduces ad spend by ~24% without losing conversions
- **Action: Do this in Google Ads today**

**B. Add H1 Tags to 29 Pages**
- The single most impactful SEO fix on the site
- Google cannot properly identify page topic without H1
- All service pages (reformer-pilates, kids-hub, personal-training, spin, ChasingRX, FIFO, recovery) affected
- **Action: Developer or CMS edit — H1 text for each page is below in Appendix A**

**C. Fix 3 Broken Pages**
- /2026free → redirect to homepage or delete
- /personal-training/nhung-dam → redirect to /personal-training
- /personal-training/briana-peterson → redirect to /personal-training
- **Action: 301 redirects in website CMS or .htaccess**

**D. Shorten Homepage Meta Description**
- Current (248 chars — too long, truncated in Google): *"Discover ChasingBetter247, the premier health and fitness club in Perth…"*
- Replace with (148 chars): *"24/7 gym in Malaga & Ellenbrook from $11.95/wk. Sauna, ice bath, Kids Hub, Reformer Pilates, Neon21 + no lock-in. Perth's most premium budget gym."*
- **Action: CMS homepage settings → Meta Description field**

---

### WEEK 2 — Publish New Organic Pages

**E. Publish Ellenbrook Landing Page**
- File: `outputs/seo/content/draft-24-7-gym-ellenbrook-page.html`
- Target: "24/7 gym ellenbrook perth" (CB247 currently #2, Revo absent from top 9)
- Window: 4–8 weeks before Revo optimises their Ellenbrook page
- **Action: Add as new page /ellenbrook on the website**

**F. Publish FIFO Landing Page**
- File: `outputs/seo/content/blog-fifo-24-7-gym-2026-05-11.html`
- Target: "gym membership fifo workers perth"
- CB247 is the ONLY gym in northern Perth offering FIFO freeze — zero competition for this keyword
- **Action: Expand /resources/fifo-members OR publish as new /fifo page**

**G. Publish Kids Hub + Recovery Pages**
- `draft-kids-hub-malaga-page.html` → publish to /kids-hub (replace existing thin 144-word page)
- `draft-recovery-hub-malaga-page.html` → publish to /resources/post-workout-recovery

---

### WEEK 3 — Schema + Technical Completeness

**H. Add Schema Markup**
- Zero schema on 40 pages is a major missed opportunity for rich snippets
- Priority 1: LocalBusiness schema on homepage (both locations)
- Priority 2: FAQPage schema on /faqs (1,649 words of perfect FAQ content)
- Priority 3: Service schema on /reformer-pilates, /personal-training, /kids-hub
- **Action: Developer adds JSON-LD to page `<head>` — templates in Appendix B**

**I. Fix Duplicate Meta Descriptions**
- 8 pages sharing the "contact us" meta description
- Action: CMS edit for each page — unique descriptions per page

---

### ONGOING — Monitoring & Optimisation

**J. Connect Google Ads API**
- Credentials needed: GOOGLE_ADS_DEVELOPER_TOKEN, GOOGLE_ADS_CUSTOMER_ID
- Add to .env → run `python scripts/pull_google_ads.py`
- Enables automated weekly CPA monitoring and campaign health alerts

**K. Set Up Ahrefs Lite**
- Recommended plan: Lite ($129/mo) for 5 websites
- Add API key to .env as AHREFS_API_KEY
- Enables: keyword rank tracking, backlink monitoring, competitor gap analysis per site

**L. Schedule Weekly Automation**
- Run: `bash scripts/weekly-seo.sh` and `bash scripts/weekly-report.sh` weekly
- Or schedule via cron/launchd using `scripts/launchd.plist.template`

---

## 5. Projected Impact If Actions Are Taken

| Action | Organic Traffic Impact | Ads Spend Impact | Timeline |
|--------|----------------------|-----------------|---------|
| H1 tags added | +15–25% page rankings improvement | — | 4–8 weeks post-fix |
| Ellenbrook page live | "gym ellenbrook perth" #1 (currently #2) | Reduce Ellenbrook Gym campaign need | 4–8 weeks |
| FIFO page live | Capture "fifo gym perth" (currently 0) | Reduce FIFO-targeted ad spend | 6–10 weeks |
| Kids Hub page live | Capture "gym childcare perth" (currently 0) | Reduce family ad targeting | 6–10 weeks |
| Schema markup | Rich snippets → higher CTR | — | 2–4 weeks |
| Pause Malaga Gym campaign | — | **Save $612/month immediately** | Today |
| Fix keyword targeting errors | 3 pages start getting WA traffic | — | 1–2 weeks |

**Conservative 3-month projection:** If technical fixes + new pages are live by end of June, organic non-branded clicks could grow from ~5 clicks/week to 50–100 clicks/week. At 9.2% CVR, that's 5–9 additional organic conversions/week that currently cost $20 CPA via Google Ads.

---

## 6. What the AI System Needs from You

The AI system can generate, analyse, and recommend — but **these items require human action:**

| Item | Who Does It | Time to Complete |
|------|------------|-----------------|
| Publish HTML pages to website | Web developer or CMS admin | 1–2 hours |
| Add H1 tags to 29 pages | Web developer or CMS admin | 1–2 hours |
| 301 redirects for 3 broken pages | Web developer | 15 minutes |
| Pause "Malaga Gym" Google Ads campaign | Google Ads account manager | 5 minutes |
| Update homepage meta description | CMS admin | 5 minutes |
| Add Google Ads API credentials to .env | Tia (has account access) | 10 minutes |
| Add Ahrefs API key to .env | Tia (after subscribing) | 2 minutes |
| Add schema markup JSON-LD to pages | Web developer | 1–2 hours |

---

## 7. Critical Risk — Revo Fitness Ellenbrook Window

Revo recently added studio space at Ellenbrook (confirmed via perthisok.com). They will optimise their Ellenbrook page. Currently they're **not in the top 9** for "gym ellenbrook perth" and CB247 is #2.

**Window: 4–8 weeks.** If the Ellenbrook landing page is published and the existing /ellenbrook content is strengthened before Revo acts, CB247 can consolidate #1 and reduce Ellenbrook Google Ads dependency entirely.

**Deadline: Publish the Ellenbrook page before end of June 2026.**

---

## Appendix A — H1 Tags to Add (Implementation-Ready)

Copy these H1 tags directly into the corresponding pages in the CMS:

| Page URL | H1 Tag to Add |
|----------|--------------|
| /reformer-pilates | `Reformer Pilates in Malaga & Ellenbrook` |
| /kids-hub | `Kids Hub — Gym with Childcare in Perth` |
| /personal-training | `Personal Training at ChasingBetter247` |
| /spin-classes | `Spin Classes in Malaga & Ellenbrook` |
| /chasingrx-classes | `ChasingRX — High-Intensity Training Perth` |
| /resources/fifo-members | `FIFO Gym Membership — Freeze When You're Away` |
| /resources/post-workout-recovery | `Recovery Hub — Sauna & Ice Bath in Perth` |
| /neon21 | `Neon21 — Perth's High-Intensity Group Fitness` |
| /casual-passes | `Casual Gym Passes — Malaga & Ellenbrook` |
| /book-a-tour | `Book a Free Tour of Our Perth Gyms` |
| /massage | `Sports Massage in Malaga` |
| /resources/fitness-passport | `Fitness Passport Gym — ChasingBetter247` |
| /faqs | `ChasingBetter247 — Frequently Asked Questions` |
| /contact | `Contact ChasingBetter247` |
| /about | `About ChasingBetter247 — Perth's Community Gym` |

---

## Appendix B — Schema Markup Templates

### LocalBusiness Schema (add to homepage `<head>`)
```json
{
  "@context": "https://schema.org",
  "@type": "GymOrHealthClub",
  "name": "ChasingBetter247",
  "url": "https://www.chasingbetter247.com.au",
  "logo": "https://www.chasingbetter247.com.au/logo.png",
  "description": "24/7 gym in Malaga and Ellenbrook, Perth WA. From $11.95/week. Sauna, ice bath, Kids Hub, Reformer Pilates, no lock-in.",
  "priceRange": "$",
  "telephone": "reception@chasingbetter247.com.au",
  "openingHours": "Mo-Su 00:00-24:00",
  "location": [
    {
      "@type": "GymOrHealthClub",
      "name": "ChasingBetter247 Malaga",
      "address": {
        "@type": "PostalAddress",
        "addressLocality": "Malaga",
        "addressRegion": "WA",
        "postalCode": "6090",
        "addressCountry": "AU"
      }
    },
    {
      "@type": "GymOrHealthClub",
      "name": "ChasingBetter247 Ellenbrook",
      "address": {
        "@type": "PostalAddress",
        "addressLocality": "Ellenbrook",
        "addressRegion": "WA",
        "postalCode": "6069",
        "addressCountry": "AU"
      }
    }
  ]
}
```

### FAQPage Schema (add to /faqs `<head>`)
```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "How much does ChasingBetter247 membership cost?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "ChasingBetter247 membership starts from $11.95 per week with no lock-in contract."
      }
    },
    {
      "@type": "Question",
      "name": "Does ChasingBetter247 offer a FIFO gym membership?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Yes. ChasingBetter247 offers a FIFO freeze — pause your membership when you're working away and only pay when you're home. Available at Malaga and Ellenbrook."
      }
    },
    {
      "@type": "Question",
      "name": "Does ChasingBetter247 have childcare or a kids area?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Yes. ChasingBetter247 has a Kids Hub with supervised childminding so you can train while your kids are looked after."
      }
    }
  ]
}
```

---

*Generated: 2026-05-29 | Compliance: AU Privacy Act 1988, Spam Act 2003*
