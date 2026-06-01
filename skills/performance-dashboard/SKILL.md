# Performance Dashboard — Weekly Analytics Analysis
Purpose: Analyze GA4 + GSC performance data and produce a structured weekly performance report.

## Trigger
Activate when user says "run performance", "performance report", "KPI report", "ad performance", "weekly performance", "analytics review".

## Inputs (read in this order)
1. `state/ga4-data.json` — sessions, users, conversions, top pages, traffic sources, devices
2. `state/gsc-data.json` — organic clicks, impressions, CTR, rankings (28 days)
3. `state/google-ads-data.json` — ad spend, CPC, conversions (if available)
4. `context/brand-voice.md` — for brand-safe language in recommendations

## Data Availability Check
```
IF ga4-data.json available = true → proceed
IF gsc-data.json available = true → include GSC section
IF google-ads-data.json available = true AND available = true → include paid section
IF google-ads-data.json missing/unavailable → skip paid ads section, note in report
```

## KPI Benchmarks (CB247)
| Channel | Metric | Target | Warning | Critical |
|---------|--------|--------|---------|---------|
| Meta (Paid Social) | CPM | < $12 | $12-18 | > $18 |
| Meta (Paid Social) | CPC | < $1.50 | $1.50-2.50 | > $2.50 |
| Meta (Paid Social) | CPL | < $25 | $25-40 | > $40 |
| Google (Paid Search) | CTR | > 4% | 2-4% | < 2% |
| Google (Paid Search) | CPC | < $3 | $3-5 | > $5 |
| Google (Paid Search) | Conv Rate | > 5% | 2-5% | < 2% |
| GA4 (Organic) | CTR | > 3% | 1-3% | < 1% |
| GA4 (Overall) | Bounce Rate | < 55% | 55-70% | > 70% |

## Report Structure

### Section 1: Executive Summary
```
## Weekly Performance Report — [Date Range]
**Week:** [start] to [end] | **Report Generated:** [timestamp]

| Metric | This Week | Last Week | Change | Status |
|--------|-----------|-----------|--------|--------|
| Sessions | X | Y | +Z% / -Z% | ✅ / ⚠️ / 🔴 |
| Users | X | Y | +Z% | ✅ / ⚠️ / 🔴 |
| New Users | X | Y | +Z% | ✅ / ⚠️ / 🔴 |
| Conversions | X | Y | +Z% | ✅ / ⚠️ / 🔴 |
| Conv Rate | X% | Y% | +Z pp | ✅ / ⚠️ / 🔴 |
```

### Section 2: GA4 Analysis

#### Traffic Overview
```
### Traffic Overview

**Sessions:** [current] (vs [previous] — [+/-]%)
**Users:** [current] (vs [previous] — [+/-]%)
**New Users:** [current] (vs [previous] — [+/-]%)
**Conversions:** [current] (vs [previous] — [+/-]%)

Interpretation: [1-2 sentences on what the numbers mean]
```

#### Traffic Sources
```
### Traffic Sources

| Source | Sessions | Conv | Conv % | Status |
|--------|----------|------|--------|--------|
| Organic Search | X | Y | Z% | ✅/⚠️/🔴 |
| Paid Social | X | Y | Z% | ✅/⚠️/🔴 |
| Direct | X | Y | Z% | ✅/⚠️/🔴 |
| Paid Search | X | Y | Z% | ✅/⚠️/🔴 |
| Cross-network | X | Y | Z% | ✅/⚠️/🔴 |
| Organic Social | X | Y | Z% | ✅/⚠️/🔴 |
| Referral | X | Y | Z% | ✅/⚠️/🔴 |

Key insight: [1-2 sentences on traffic mix]
```

#### Top Pages
```
### Top 10 Pages by Sessions

| Page | Views | Sessions | Avg Time |
|------|-------|---------|----------|
| / | X | Y | mm:ss |
| /reformer-pilates | X | Y | mm:ss |
[...top 10...]
```

#### Device Breakdown
```
### Device Breakdown

| Device | Sessions | % | Insight |
|--------|----------|---|---------|
| Mobile | X | X% | [comment] |
| Desktop | X | X% | [comment] |
| Tablet | X | X% | [comment] |
```

### Section 3: GSC Analysis (if available)
```
### Organic Search Performance (28 Days)

| Metric | Value | Status |
|--------|-------|--------|
| Total Clicks | X | ✅/⚠️/🔴 |
| Total Impressions | X | — |
| Average CTR | X% | ✅/⚠️/🔴 |
| Average Position | X | ✅/⚠️/🔴 |

#### Top 10 Queries
| Query | Clicks | Impressions | CTR | Position |
|-------|--------|-------------|-----|----------|
| [query] | X | X | X% | X |
[...top 10...]

#### Top 10 Pages
| Page | Clicks | Impressions | CTR | Position |
|------|--------|-------------|-----|----------|
| [url] | X | X | X% | X |
[...top 10...]

**SEO Wins:**
- [List 2-3 positive observations from GSC data]

**SEO Issues:**
- [List 2-3 concerns or declining metrics]
```

### Section 4: Paid Ads Analysis (if google-ads-data.json available)
```
### Paid Ads Performance

[Note: Google Ads data unavailable — missing GOOGLE_ADS_DEVELOPER_TOKEN and GOOGLE_ADS_CUSTOMER_ID. Add these to .env to enable paid reporting.]

OR (if data available):

| Campaign | Spend | Impressions | Clicks | CPC | CTR | Conv | CPA |
|---------|-------|------------|--------|-----|-----|------|-----|
| [name] | $X | X | X | $X | X% | X | $X |

KPI Scorecard:
- CPM: $X [vs $12 target] → ✅/⚠️/🔴
- CPC: $X [vs $1.50 target] → ✅/⚠️/🔴
- CPL: $X [vs $25 target] → ✅/⚠️/🔴
- CTR: X% [vs 4% target] → ✅/⚠️/🔴
```

### Section 5: Wins & Issues
```
## Wins ✅
1. [Biggest win this week — specific metric + context]
2. [Second win — specific metric + context]
3. [Third win — specific metric + context]

## Issues 🔴
1. [Biggest issue — specific metric + what's causing it]
2. [Second issue — specific metric + contributing factors]
3. [Third issue — specific metric + context]
```

### Section 6: 3 Actionable Recommendations
```
## 3 Actions for Next Week

### 1. [Priority Action]
**What:** [Specific action to take]
**Why:** [Data-driven reason]
**Owner:** [Meta / Google / Content / Email]
**Timeline:** [By what date]

### 2. [Priority Action]
[...same structure...]

### 3. [Priority Action]
[...same structure...]
```

### Section 7: Budget Recommendation
```
## Budget Recommendation

**Current Weekly Spend:** $[X] (if available)

**Recommendation:**
- **[Platform]:** [Increase/Decrease/Maintain] by $[X]
- **[Platform]:** [Increase/Decrease/Maintain] by $[X]

**Rationale:** [1-2 sentences based on ROAS/CPA data]

**Next Week Budget:** $[X] total
```

## Analysis Formulas

### Conversion Rate
```
conv_rate = (conversions / sessions) × 100
```

### Week-over-Week Change
```
change = ((current - previous) / previous) × 100
```

### CPM (Cost Per Mille)
```
CPM = (spend / impressions) × 1000
```

### CPC (Cost Per Click)
```
CPC = spend / clicks
```

### CPA (Cost Per Acquisition)
```
CPA = spend / conversions
```

## Status Thresholds
```
Green ✅: Metric within target range
Warning ⚠️: Metric 10-50% outside target
Critical 🔴: Metric >50% outside target or declining >20% WoW
```

## Quality Checklist
- [ ] All numbers cited are from the data files (not hallucinated)
- [ ] Week-over-week change calculated correctly
- [ ] GSC data included if available
- [ ] Google Ads data noted as missing if unavailable
- [ ] 3 actions are specific, data-driven, and actionable
- [ ] Budget recommendation is grounded in actual performance
- [ ] No brand-unsafe language used
- [ ] Report ends with "PERFORMANCE ANALYSIS COMPLETE"

## Output
Save report to: `outputs/research/performance-week-[N]-YYYY-MM-DD.md`
Where N = week number of the year (1-52)
Print: "PERFORMANCE ANALYSIS COMPLETE"

---

## Action KPI Review (Post-Execution)

When user runs `/performance review [action-id]` or asks to review an action's KPI performance:

**Trigger Phrases:**
- "review action KPIs"
- "action impact report"
- "performance review [action-id]"

**Inputs:**
1. `state/actions.json` — Get action details including projected impact
2. `state/kpi_ledger.json` — Historical KPI data for comparison
3. `state/ga4-data.json`, `state/google-ads-data.json` — Current metrics


**Process:**
1. Read action from `state/actions.json` by ID
2. Get selected KPIs and projected values
3. Calculate actual KPIs from current data:
   - CPL: `spend / conversions`
   - ROAS: `revenue / spend`
   - CPM: `(spend / impressions) × 1000`
   - CPC: `spend / clicks`
   - CTR: `(clicks / impressions) × 100`
4. Compare projected vs actual
5. Rate each KPI: Exceeds / Meets / Below / Misses
6. Generate overall rating

**KPI Ratings:**
| Rating | Criteria |
|--------|----------|
| Exceeds | Actual >10% better than projected |
| Meets | Actual meets or is within 10% of projected |
| Below | Actual 10-20% worse than projected |
| Misses | Actual >20% worse than projected |

**Output:**
- Save to: `outputs/meetings/impact-[action-id]-YYYY-MM-DD.md`
- Update `state/kpi_ledger.json` with new entry
- Update `state/actions.json` with actual_impact

**Report Template:**
```markdown
# KPI Impact Report — [action-id]

**Action:** [description]
**Completed:** [date]
**Reviewed:** [date]
**Overall Rating:** [EXCEEDS / MEETS / BELOW / MISSES]

## KPI Performance

| KPI | Projected | Actual | Delta | Rating |
|-----|-----------|--------|-------|--------|
| CPL | $X | $Y | -Z% | 🟢 EXCEEDS |
| ROAS | 3.5x | 3.8x | +8.6% | 🟢 EXCEEDS |

## Summary
[Overall assessment]
```
