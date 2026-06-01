# A/B Test Design: Cockburn Pre-Launch Headline Framing Test
**Date:** 2026-05-11 | **Status:** Draft

---

## 1. Test Overview

| Field | Value |
|-------|-------|
| Test Name | Cockburn Pre-Launch Headline Framing Test |
| Platform | Website (Cockburn Landing Page) |
| Test ID | WEBSITE_CockburnHeadline_20260511 |
| Hypothesis | "Founding Member" framing (Option A) will outperform "Be First" framing (Option B) because it creates a sense of exclusivity and tangible benefit rather than just urgency. |
| Target Audience | Cold Traffic (Spearwood, Bibra Lake, Hamilton Hill, Coogee, Cockburn) |
| Traffic Split | 50/50 |
| Duration | 14 days minimum |

---

## 2. Variant Descriptions

### Option A (Control): Founding Member Framing
Focuses on the status and longevity of the benefit.
- **Headline:** "Claim Your Founding Member Spot — Cockburn's First 24/7 Gym + Bath House"
- **CTA:** "Secure Founding Status"
- **Secondary Element:** "Only 50 founding spots remaining"

### Option B (Variant): Urgency / "Be First" Framing
Focuses on speed and being a pioneer in the area.
- **Headline:** "Be the First to Train in Cockburn — Founding Member Pricing Locked In"
- **CTA:** "Join the Waitlist"
- **Secondary Element:** "Opening mid-2026"

---

## 3. Traffic Allocation
- **Variant A:** 50% of incoming traffic.
- **Variant B:** 50% of incoming traffic.
- **Audience:** Visitors from Meta Ads (Cockburn targeting) and Organic Search for "Gym Cockburn".

---

## 4. Success Metrics

### Primary Metric: Waitlist Form Submissions
- **Goal:** +15% conversion rate lift.
- **Definition:** User completes the name/email form and reaches the success message.

### Secondary Metrics
- **Bounce Rate:** Does framing affect immediate page exit?
- **Time on Page:** Does "Founding Spot" framing lead to more reading of the benefits?
- **Scroll Depth:** Tracking if visitors reach the FAQ section.

---

## 5. Sample Size Calculation
Using the `ab-testing-framework` baseline for low conversion rates (<5%):

- **Baseline Conv. Rate (Estimate):** 3-5% for cold pre-launch traffic.
- **Min. Impressions per Variant:** 5,000 (10,000 total).
- **Target Significance:** 95% (p-value < 0.05).

---

## 6. Implementation Notes

### Setup in Google Ads / Meta
1. **Meta Ads:** Run as an A/B split test at the Campaign level. Use identical creative (image/video) but match the Ad Headline to the Landing Page Variant Headline to ensure message match.
2. **Landing Page:** Use a tool like Google Optimize (or replacement), Unbounce, or a simple JS redirect based on a 50/50 cookie split to serve the different headlines/CTAs.
3. **UTM Check:** Ensure Variant A uses `utm_content=founding_member` and Variant B uses `utm_content=be_first` for tracking in Google Analytics 4.

---

## 7. Test Results Template

*To be populated in `outputs/seo/tests/cockburn-headline-test-results.md` after 14 days.*

| Variant | Impressions | Conv. Rate | CPL | Significance |
|---------|-------------|------------|-----|--------------|
| Option A | [n] | [%] | [$] | [%] |
| Option B | [n] | [%] | [$] | [%] |

---

## 8. Go/No-Go Criteria

### When to Launch
- [ ] Landing page draft is finalized and technical form tracking is verified.
- [ ] Ad creative for Cockburn (Bath House renders + Gym floor) is ready.
- [ ] Tracking pixels (Meta/GA4) are firing on form submission.

### When to Wait/Stop
- [ ] Stop if one variant crashes conversion by >50% in the first 72 hours (Safety Halt).
- [ ] Wait if traffic volume is <500 visitors/day (extend duration to 21 days).

---

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
