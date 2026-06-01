# SKILL: A/B Testing Framework — CB247

## Trigger Keywords
A/B test, split test, test design, variant, control, statistical significance, hypothesis, test results, experiment

## Identity
You are CB247's experimentation strategist. You design rigorous A/B tests that deliver actionable insights.

---

## READ FIRST
1. `context/marketing-strategy.md` — KPI benchmarks
2. `skills/performance-dashboard/SKILL.md` — What metrics to track
3. `skills/analytics-connector/SKILL.md` — Data interpretation

---

## Why A/B Testing Matters

Marketing without testing is guesswork. A/B testing removes the guesswork by:
- Proving which variations actually convert
- Justifying budget allocation decisions
- Building a data-driven culture
- Learning what works for CB247's specific ICPs

---

## Testing Hierarchy

### Tier 1: High-Impact, Long-Term Tests (Quarterly)
| Test | Impact | Effort | Why |
|------|--------|--------|-----|
| Landing page headline | 🟢 High | Medium | First impression determines bounce |
| CTA button color/text | 🟢 High | Low | Direct conversion driver |
| Offer framing ($ vs % vs benefit) | 🟢 High | Low | Can significantly affect CPL |

### Tier 2: Medium-Impact, Regular Tests (Monthly)
| Test | Impact | Effort | Why |
|------|--------|--------|-----|
| Ad creative (image vs video vs carousel) | 🟡 Medium | Medium | CPM efficiency |
| Audience targeting narrow vs broad | 🟡 Medium | Low | CPC optimization |
| Caption length (short vs long) | 🟡 Medium | Low | Engagement rates |
| Posting time optimization | 🟡 Medium | Low | Reach improvement |

### Tier 3: Low-Impact, Quick Wins (Weekly)
| Test | Impact | Effort | Why |
|------|--------|--------|-----|
| Hashtag set variations | 🟢 Low | Low | Discovery reach |
| Story/Reel hook variations | 🟢 Low | Low | View completion |
| Email subject lines | 🟢 Low | Low | Open rates |

---

## Test Design Framework

### Step 1: Define the Hypothesis

Every test starts with a hypothesis, not a "let's try this."

| Good Hypothesis | Bad Hypothesis |
|-----------------|---------------|
| "Price-led CTAs will convert better than benefit-led CTAs for FIFO workers" | "Let's try a different button color" |
| "A/B testing will tell us which is better" | "Let's see what happens" |

**Hypothesis Template:**
"If we [change X], then [Y metric] will [increase/decrease] by [amount], because [reason]."

### Step 2: Define Success Metric

| Primary Metric | What It Measures |
|----------------|-----------------|
| CPL | Lead generation efficiency |
| CTR | Click-through from impression |
| Conversion rate | Landing page to form submit |
| Engagement rate | Social content resonance |

### Step 3: Calculate Sample Size

Use this formula for significance:

```
Minimum sample size per variant = (16 × σ²) / δ²

Where:
- σ = standard deviation of baseline conversion
- δ = minimum detectable effect (e.g., 10% improvement)
```

**Quick Rule:** For <5% baseline conversion rate:
- Need ~5,000 impressions per variant minimum
- 1-week test at $500 spend should suffice
- If you're stopping early, you're lying to yourself

### Step 4: Set Test Duration

| Test Type | Minimum Duration | Why |
|----------|------------------|-----|
| Landing page | 2 weeks | Traffic patterns vary by day |
| Paid social | 7 days | Full weekly cycle |
| Email | 24 hours | Enough for open rate |
| Organic post | 3 days | Engagement stabilizes |

**Never stop a test early** unless:
- It's catastrophically failing (losing 50%+ on primary metric)
- You have a pre-defined stopping rule based on severity

---

## Meta Ads Test Design

### Creative Testing Framework

#### Test: Ad Format
| Variant A (Control) | Variant B (Test) |
|--------------------|--------------------|
| Static image | Video Reel (15s) |
| Headline: [A] | Headline: [B] |
| Body: [standard] | Body: [standard] |

**Hypothesis:** Video Reels will achieve lower CPL than static images due to higher engagement in feed.

#### Test: Offer Framing
| Variant A | Variant B | Variant C |
|-----------|-----------|-----------|
| "$11.95/week" | "$0 join. $11.95/week." | "Less than coffee per day" |

**Hypothesis:** "Less than coffee per day" will attract more price-conscious conversions but may attract lower-intent leads.

#### Test: Audience Angle
| Cold FIFO | Cold General + FIFO interest targeting |
|-----------|----------------------------------------|
| Age 28-50, Perth NOR | Age 28-50, Perth NOR, FIFO interest |

**Hypothesis:** Interest-based targeting will lower CPL for FIFO segment.

---

## Google Ads Test Design

### RSA (Responsive Search Ads) Testing

**Test 1: Headline Angle**
| Control | Variant |
|---------|---------|
| "24/7 Gym Malaga - $11.95/week" | "No Lock-In Gym Malaga - Join Free" |
| "Train Any Time" | "FIFO Friendly Gym" |
| "Sauna + Ice Bath Included" | "Kids Hub On-Site" |

**Hypothesis:** FIFO-specific headline will improve CTR for FIFO workers.

**Test 2: Description Focus**
| Control | Variant |
|---------|---------|
| "Join CB247 Malaga" | "Your membership works around FIFO" |

---

## Email Test Design

### Test 1: Subject Lines
| Control | Variant A | Variant B |
|---------|-----------|-----------|
| "Welcome to CB247" | "Your 7-day free trial starts today" | "We saved your spot" |

**Metric:** Open rate (primary), CTR (secondary)

### Test 2: Send Time
| Control | Variant |
|---------|---------|
| Tuesday 10am | Saturday 9am |

**Metric:** Open rate, click rate, reply rate

---

## Test Results Analysis Template

### File: `outputs/research/test-results-[test-name]-[YYYY-MM-DD].md`

```markdown
# A/B Test Results: [Test Name]
**Date:** YYYY-MM-DD | **Status:** [Concluded / In Progress / Paused]

---

## Test Overview

| Field | Value |
|-------|-------|
| Test ID | [unique identifier] |
| Platform | [Meta / Google / Email / Website] |
| Start Date | YYYY-MM-DD |
| End Date | YYYY-MM-DD |
| Duration | [n] days |
| Total Sample | [n] impressions |

---

## Hypothesis
"If we [change X], then [Y metric] will [increase/decrease] by [amount], because [reason]."

---

## Test Setup

### Control (Variant A)
[Detailed description of control]

### Test (Variant B)
[Detailed description of test]

### Traffic Split
[50/50 / 60/40 / 70/30] — **Note:** Asymmetric splits require more complex analysis

---

## Results

### Primary Metric: [Metric Name]

| Variant | Impressions | Clicks | CTR | Conversions | Conv. Rate | CPL |
|---------|-------------|--------|-----|------------|-------------|-----|
| Control (A) | [n] | [n] | [x.x%] | [n] | [x.x%] | $[xx.xx] |
| Test (B) | [n] | [n] | [x.x%] | [n] | [x.x%] | $[xx.xx] |
| **Difference** | — | — | [+/-x.x%] | — | [+/-x.x%] | [+/-x.x%] |

### Statistical Significance
| Metric | Result | Significance |
|--------|--------|--------------|
| CTR lift | [+/-x.x%] | ✅ Significant / ⚠️ Not Significant / 🔄 Inconclusive |
| Conversion rate | [+/-x.x%] | ✅ Significant / ⚠️ Not Significant / 🔄 Inconclusive |

**Confidence Level:** [95% / 99%] — Required minimum: 95%

### Secondary Metrics
| Metric | Control | Test | Difference |
|--------|---------|------|------------|
| CPM | $[xx.xx] | $[xx.xx] | [+/-x.x%] |
| Reach | [n] | [n] | [+/-x.x%] |
| Frequency | [x.xx] | [x.xx] | [+/-x.x%] |

---

## Winner Declaration

**🏆 WINNER:** [Control A / Variant B / INCONCLUSIVE]

**Confidence:** [95% / 99%] statistical significance achieved

**Reasoning:** [2-3 sentences explaining why]

---

## Insights & Learnings

### What This Test Taught Us
1. **[Insight 1]** — [what it means for CB247]
2. **[Insight 2]** — [what it means for CB247]

### Unexpected Findings
[Any surprising results that warrant further testing]

---

## Recommendations

### Immediate Actions
- [ ] Implement winner variant in [channel]
- [ ] Pause underperforming variant

### Next Tests
| Test Idea | Hypothesis | Priority |
|-----------|------------|----------|
| [test idea] | [hypothesis] | [P1/P2/P3] |

---

## Appendices

### Raw Data
[Link to raw data source]

### Notes
[Any methodological notes or caveats]

---

*Test analysis completed by Claude Code — CB247 Marketing Engine*
```

---

## Test Naming Convention

```
[Platform]_[Element-Tested]_[YYYYMMDD]
```

**Examples:**
- `META_CtaColor_20260503`
- `GOOGLE_RSAFIFO_20260510`
- `EMAIL_SubjectLine_20260515`
- `WEBSITE_HeroHeadline_20260520`

---

## Common Testing Mistakes to Avoid

| Mistake | Why It's Bad | How to Avoid |
|---------|--------------|--------------|
| Stopping test early | Results aren't statistically valid | Set sample size upfront |
| Testing too many things | Can't isolate what caused the change | One change per test |
| No hypothesis | Directionless testing | State hypothesis before running |
| Ignoring secondary metrics | May hide negative impacts | Track both primary and secondary |
| Not documenting learnings | Same mistakes repeated | Save results to shared doc |
| Testing on holidays | Irregular behavior | Avoid Christmas, Easter, etc. |

---

## Quality Checklist
- [ ] Hypothesis clearly stated
- [ ] Sample size calculated
- [ ] Test duration set
- [ ] Primary metric defined
- [ ] Secondary metrics identified
- [ ] Statistical significance threshold set (95% minimum)
- [ ] Results documented with full data
- [ ] Learnings extracted and saved
- [ ] Next test ideas generated

---

## Output
Save test designs to: `outputs/research/test-design-[test-name]-[YYYY-MM-DD].md`
Save test results to: `outputs/research/test-results-[test-name]-[YYYY-MM-DD].md`
