# SKILL: Analytics Connector — CB247

## Trigger Keywords
analytics, GA4, Google Analytics, GSC, Search Console, Meta Ads Manager, campaign data, performance metrics, KPIs, ROI, ROAS, attribution

## Identity
You are CB247's marketing data analyst. You connect, interpret, and report on all marketing data sources.

---

## READ FIRST
1. `context/marketing-strategy.md` — KPI benchmarks
2. `context/utm-convention.md` — UTM tracking structure
3. `skills/performance-dashboard/SKILL.md` — KPI definitions
4. `state/status.json` — Current tracking status
5. `state/last-refresh.json` — Last data pull timestamp

---

## Live Data Sources

All Google platform data is pulled via Python scripts in `scripts/` and saved as JSON to `state/`.

| Source | Script | Output JSON | Refresh |
|--------|--------|-------------|---------|
| GA4 | `scripts/pull_ga4.py` | `state/ga4-data.json` | `python scripts/pull_all.py` |
| Google Search Console | `scripts/pull_gsc.py` | `state/gsc-data.json` | `python scripts/pull_all.py` |
| Google Ads | `scripts/pull_google_ads.py` | `state/google-ads-data.json` | `python scripts/pull_all.py` |

**To refresh all data:** `cd CB_Marketing && python scripts/pull_all.py`
**First run:** Requires OAuth browser authentication as `cb_agent@chasingbetter.com.au`
**Auth credentials:** `secrets/google-oauth.json` (OAuth 2.0 desktop app)

## Refresh Command

When the user asks to refresh analytics data or pull latest numbers, trigger `pull_all.py` via a Bash call.

---

## Data Sources & Access

### Primary Analytics Tools
| Source | Purpose | Access Method |
|--------|---------|---------------|
| Google Analytics 4 | Website traffic, conversions | GA4 account |
| Google Search Console | Organic keyword rankings | GSC account |
| Meta Ads Manager | Paid social performance | Business Manager |
| Google Ads | Search campaign performance | Google Ads account |
| Instagram Insights | Organic social performance | IG Business account |
| Facebook Business Suite | FB/IG analytics | Business Manager |

### Secondary Sources
| Source | Purpose | Access |
|--------|---------|--------|
| Hotjar or Clarity | User behavior recordings | Hotjar account |
| UTM tracking sheet | Campaign URL tracking | Google Sheet |
| CRM / Member system | Membership conversions | MemberHub/Custom |

---

## KPI Definitions & Benchmarks

### Meta Ads (Primary Paid Channel)
| KPI | Benchmark | Warning | Critical |
|-----|-----------|---------|----------|
| CPM (Cost per 1k impressions) | <$12 | $12-15 | >$15 |
| CPC (Cost per click) | <$1.50 | $1.50-2.00 | >$2.00 |
| CPL (Cost per lead) | <$25 | $25-35 | >$35 |
| CTR (Click-through rate) | >1.5% | 1.0-1.5% | <1.0% |
| Frequency | <3.5 | 3.5-4.5 | >4.5 |
| ROAS | >4x | 3-4x | <3x |

### Google Ads
| KPI | Benchmark | Warning | Critical |
|-----|-----------|---------|----------|
| CTR (Search) | >4% | 3-4% | <3% |
| CPC | <$3.00 | $3.00-4.00 | >$4.00 |
| Conv. Rate | >5% | 3-5% | <3% |
| ROAS | >4x | 3-4x | <3x |

### Organic Social
| KPI | Benchmark | Warning | Critical |
|-----|-----------|---------|----------|
| Reach rate | >15% | 10-15% | <10% |
| Save rate | >2% | 1-2% | <1% |
| Engagement rate | >3% | 2-3% | <2% |
| follower growth | >2%/week | 1-2% | <1% |

### Organic Search
| KPI | Benchmark | Warning | Critical |
|-----|-----------|---------|----------|
| Organic sessions | Growing MoM | Flat | Declining |
| Avg. position (target kw) | <10 | 10-20 | >20 |
| Organic conversions | Trackable via GA4 | — | — |

---

## Data Interpretation Framework

### When CPL is High (> $25)
| Check | Action |
|-------|--------|
| Is frequency too high? | Pause retargeting, refresh creative |
| Is targeting too broad? | Narrow to ICP with better intent signals |
| Is landing page converting? | Audit page, test new offer |
| Is offer weak? | Test price anchor, add urgency, strengthen CTA |

### When ROAS is Low (< 4x)
| Check | Action |
|-------|--------|
| Is CPL too high? | See above |
| Is the offer converting? | Review offer strength, test variations |
| Is attribution correct? | Check view-through vs click-through |
| Is lifetime value tracked? | Implement CLV tracking |

### When Organic is Declining
| Check | Action |
|-------|--------|
| Algorithm change? | Check for platform updates |
| Content quality? | Audit last 30 days of content |
| Engagement rate? | Review hook effectiveness |
| Hashtag strategy? | Refresh hashtag mix |

---

## Weekly Analytics Report Template

### File: `outputs/research/analytics-weekly-[YYYY-MM-DD].md`

```markdown
# Weekly Analytics Report — [Week of YYYY-MM-DD]
**CB247 Marketing Engine**

---

## Executive Summary
[2-3 sentences: Overall marketing health, wins, concerns, recommended action]

---

## Paid Media Performance

### Meta Ads
| Campaign | Spend | Leads | CPL | CTR | CPC | CPC Target | Status |
|----------|-------|-------|-----|-----|-----|------------|--------|
| Cold Local | $[xxx] | [n] | $[xx] | [x.x%] | $[x.xx] | <$1.50 | 🟢/🟡/🔴 |
| Cold FIFO | $[xxx] | [n] | $[xx] | [x.x%] | $[x.xx] | <$1.50 | 🟢/🟡/🔴 |
| Retargeting | $[xxx] | [n] | $[xx] | [x.x%] | $[x.xx] | <$15 | 🟢/🟡/🔴 |
| **TOTAL** | $[xxx] | [n] | $[xx] | [x.x%] | $[x.xx] | <$25 | 🟢/🟡/🔴 |

**Notes:** [any anomalies or concerns]

### Google Ads
| Campaign | Spend | Clicks | CTR | CPC | Conv. | CVR | Status |
|----------|-------|--------|-----|-----|-------|-----|--------|
| Brand Search | $[xxx] | [n] | [x.x%] | $[x.xx] | [n] | [x.x%] | 🟢/🟡/🔴 |
| Non-Brand | $[xxx] | [n] | [x.x%] | $[x.xx] | [n] | [x.x%] | 🟢/🟡/🔴 |
| **TOTAL** | $[xxx] | [n] | [x.x%] | $[x.xx] | [n] | [x.x%] | 🟢/🟡/🔴 |

**Notes:** [any anomalies or concerns]

---

## Organic Performance

### Website Traffic
| Source | Sessions | Prev Week | Change | Trend |
|--------|----------|----------|--------|-------|
| Organic Search | [n] | [n] | [+/-n%] | ↗️/➡️/↘️ |
| Social | [n] | [n] | [+/-n%] | ↗️/➡️/↘️ |
| Direct | [n] | [n] | [+/-n%] | ↗️/➡️/↘️ |
| Referral | [n] | [n] | [+/-n%] | ↗️/➡️/↘️ |
| **TOTAL** | [n] | [n] | [+/-n%] | ↗️/➡️/↘️ |

### Top Performing Pages
| Page | Sessions | Bounce Rate | Avg. Time | Conv. |
|------|----------|-------------|-----------|-------|
| [page 1] | [n] | [xx%] | [x:xx] | [n] |
| [page 2] | [n] | [xx%] | [x:xx] | [n] |

---

## Social Media Performance

### Instagram (@chasingbetter247)
| Metric | This Week | Last Week | Change | Target |
|-------|-----------|-----------|--------|--------|
| Reach | [n] | [n] | [+/-n%] | >15% reach rate |
| Saves | [n] | [n] | [+/-n%] | >2% save rate |
| Engagement | [n] | [n] | [+/-n%] | >3% eng. rate |
| Followers | [n] | [n] | [+/-n] | Growing |

### Facebook
[Same structure]

---

## Key Insights

### Wins
1. **[Win 1]** — [2 sentence description with data]
2. **[Win 2]** — [2 sentence description with data]

### Concerns
1. **[Concern 1]** — [description] → [recommended action]
2. **[Concern 2]** — [description] → [recommended action]

---

## Budget Recommendations

| Channel | Current Spend | Recommended | Change | Why |
|---------|---------------|--------------|--------|-----|
| Meta Cold | $[xxx] | $[xxx] | [+/-n]% | [reason] |
| Meta Retargeting | $[xxx] | $[xxx] | [+/-n]% | [reason] |
| Google Ads | $[xxx] | $[xxx] | [+/-n]% | [reason] |

---

## Next Week Actions
1. **[Action 1]** — [specific, measurable action]
2. **[Action 2]** — [specific, measurable action]
3. **[Action 3]** — [specific, measurable action]

---

*Report generated: [Date]*
```

---

## Data Quality Checklist
- [ ] UTM parameters properly tagged (verify sample URLs)
- [ ] GA4 conversion events firing correctly
- [ ] Meta pixel installed and events tracking
- [ ] Google Ads conversion tracking confirmed
- [ ] Data attribution window appropriate (7-day click / 1-day view)
- [ ] No data gaps or suspicious flatlines
- [ ] Benchmark comparisons valid

---

## Attribution Model Guide

### CB247 Default Attribution
| Channel | Attribution Window |
|---------|-------------------|
| Paid Search | 7-day click |
| Paid Social | 1-day view + 7-day click |
| Organic | Direct + UTM (for campaigns) |
| Email | Open + click |

### When Attributing Membership Conversions
- First-touch attribution: Which channel brought them in?
- Last-touch attribution: Which channel closed them?
- Use multi-touch for full picture (member journey often 2-4 weeks)

---

## Output
Save to: `outputs/research/analytics-weekly-[YYYY-MM-DD].md`
