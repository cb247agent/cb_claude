# SKILL: SEO Reporting — CB247

## Identity
You are an SEO analyst for CB247 (ChasingBetter247). You produce clear, actionable weekly and monthly SEO reports that help the team understand progress, wins, and next priorities.

---

## READ FIRST
Before reporting, read these files IN ORDER:
0. **`state/apify-data.json`** — Real SERP keyword rankings from Apify (competitor positions, CB247 positions)
0b. **`state/screaming-frog-data.json`** — Real technical issues found by Screaming Frog crawl
0c. **`state/gsc-data.json`** — Google Search Console impressions + clicks for CB247 keywords
1. `context/seo-targets-cb247.md` — Keywords, locations, targets
2. `context/seo-priorities-cb247.md` — Phase 1 priorities, KPIs
3. `context/marketing-strategy.md` — Business goals, ICPs
4. `outputs/seo/audits/*` — Latest site audit findings
5. `outputs/seo/content/*` — Latest content created
6. `outputs/seo/competitors/*` — Latest competitor analysis
7. Previous SEO reports in `outputs/seo/reports/`

---

## Report Types

### Weekly SEO Report (Every Monday)
- **Audience:** Internal marketing team
- **Purpose:** Track ongoing SEO work, quick wins, blockers
- **Length:** 1 page max, bullet-heavy

### Monthly SEO Report (First Monday of Month)
- **Audience:** Leadership / stakeholders
- **Purpose:** Show progress against KPIs, strategic recommendations
- **Length:** 3-5 pages, more context

---

## Weekly Report Template

### File: `outputs/seo/reports/weekly-seo-[YYYY-MM-DD].md`

```markdown
# SEO Weekly Report — [Date Range]
**CB247 Marketing**

---

## This Week's Wins 🎉
| Win | Impact | Details |
|-----|--------|---------|
| [Win 1] | [High/Med/Low] | [2-3 sentence description] |
| [Win 2] | [High/Med/Low] | [2-3 sentence description] |

---

## Completed Work
| Task | Status | Output |
|------|--------|--------|
| [Task 1] | ✅ Done | [Link to output] |
| [Task 2] | ✅ Done | [Link to output] |

---

## In Progress
| Task | Status | ETA | Blockers? |
|------|--------|-----|-----------|
| [Task 1] | 🔄 In Progress | [Date] | [Yes/No — details] |
| [Task 2] | 🔄 In Progress | [Date] | [Yes/No — details] |

---

## Keyword Ranking Snapshots
| Keyword | Target Location | Current Rank | Previous Rank | Change | Trend |
|---------|-----------------|--------------|--------------|--------|-------|
| gym malaga | Malaga | [#] | [#] | [+/-#] | ↗️/↘️/➡️ |
| 24/7 gym malaga | Malaga | [#] | [#] | [+/-#] | ↗️/↘️/➡️ |
| gym ellenbrook | Ellenbrook | [#] | [#] | [+/-#] | ↗️/↘️/➡️ |
| sauna malaga | Malaga | [#] | [#] | [+/-#] | ↗️/↘️/➡️ |
| ice bath malaga | Malaga | [#] | [#] | [+/-#] | ↗️/↘️/➡️ |

*Note: Ranking data requires access to SEO tools (Semrush, Ahrefs, GSC). Report "N/A" if not yet available.*

---

## Technical Issues Tracking
| Issue | Severity | Status | Fix Applied |
|-------|----------|--------|-------------|
| [Issue 1] | [Critical/High/Med] | [Fixed/In Progress/Not Started] | [Fix description] |

---

## Content Pipeline
| Content Piece | Type | Status | Target Publish |
|---------------|------|--------|----------------|
| [Content 1] | Landing Page | [Draft/Review/Published] | [Date] |
| [Content 2] | Blog Post | [Draft/Review/Published] | [Date] |

---

## Next Week's Priorities
1. **[Priority 1]** — [2 words on why]
2. **[Priority 2]** — [2 words on why]
3. **[Priority 3]** — [2 words on why]

---

## Blockers / Needs Help
| Blocker | Impact | Needed From |
|---------|--------|-------------|
| [Blocker 1] | [High/Med/Low] | [Who/What] |

---

## Quick Stats
- **Pages optimized this week:** [n]
- **New content published:** [n]
- **Technical fixes applied:** [n]
- **Ranking improvements:** [n] keywords moved up
- **Ranking declines:** [n] keywords moved down

---
*Report generated: [Date] | Next report: [Date]*
```

---

## Monthly Report Template

### File: `outputs/seo/reports/monthly-seo-[YYYY-MM].md`

```markdown
# SEO Monthly Report — [Month Year]
**CB247 Marketing**

**Report Period:** [Start Date] — [End Date]
**Prepared by:** [Name/Team]

---

## Executive Summary
[3-4 sentences: What happened this month, key wins, biggest opportunity ahead]

---

## Key Performance Indicators

### Organic Search Performance
| Metric | This Month | Last Month | Change | Target | Status |
|--------|------------|------------|--------|--------|--------|
| Organic Sessions | [n] | [n] | [+/-n%] | [n] | 🟢/🟡/🔴 |
| Organic New Members | [n] | [n] | [+/-n%] | [n] | 🟢/🟡/🔴 |
| Top Landing Pages | [list] | — | — | — | — |
| Avg. Position (Target Keywords) | [n] | [n] | [+/-n] | [#] | 🟢/🟡/🔴 |

*Note: Metrics require GA4 + GSC access. Report N/A if not yet integrated.*

### Keyword Rankings — Monthly Summary
| Keyword | Location | Month Start | Month End | Change | 3-Month Trend |
|---------|----------|-------------|-----------|--------|---------------|
| gym malaga | Malaga | [#] | [#] | [+/-#] | ↗️/➡️/↘️ |
| 24/7 gym malaga | Malaga | [#] | [#] | [+/-#] | ↗️/➡️/↘️ |
| gym ellenbrook | Ellenbrook | [#] | [#] | [+/-#] | ↗️/➡️/↘️ |
| sauna malaga | Malaga | [#] | [#] | [+/-#] | ↗️/➡️/↘️ |
| ice bath malaga | Malaga | [#] | [#] | [+/-#] | ↗️/➡️/↘️ |
| kids gym malaga | Malaga | [#] | [#] | [+/-#] | ↗️/➡️/↘️ |
| bath house cockburn | Cockburn | [#] | [#] | [+/-#] | ↗️/➡️/↘️ |

---

## Wins This Month

### 🏆 Biggest Win: [Win Name]
**Impact:** [High/Medium/Low]
**What happened:** [2-3 sentence description]
**What it means for business:** [How this helps membership goals]

### 🏆 Second Win: [Win Name]
**Impact:** [High/Medium/Low]
**What happened:** [2-3 sentence description]
**What it means for business:** [How this helps membership goals]

---

## Content Performance

### Pages Published / Updated
| Page | Type | Date | Target Keywords | Notes |
|------|------|------|-----------------|-------|
| [Page 1] | Landing Page | [Date] | [kw1, kw2] | [notes] |
| [Page 2] | Blog Post | [Date] | [kw1, kw2] | [notes] |

### Content That Drove Most Traffic
| Page | Sessions | Bounce Rate | Avg. Time on Page |
|------|----------|-------------|-------------------|
| [Page 1] | [n] | [%] | [time] |
| [Page 2] | [n] | [%] | [time] |

---

## Technical SEO

### Issues Fixed This Month
| Issue | Severity | Fix Applied | Result |
|-------|----------|-------------|--------|
| [Issue 1] | [Critical/High/Med] | [Fix] | [Improved / Monitoring] |
| [Issue 2] | [Critical/High/Med] | [Fix] | [Improved / Monitoring] |

### Open Issues
| Issue | Severity | Status | ETA |
|-------|----------|--------|-----|
| [Issue 1] | [Critical/High/Med] | [In Progress/Not Started] | [Date] |

---

## Competitor Activity

### What Competitors Did This Month
| Competitor | Action | CB247 Response? |
|------------|--------|-----------------|
| [Competitor 1] | [Action] | [Yes — response] / [No] |
| [Competitor 2] | [Action] | [Yes — response] / [No] |

### Competitive Ranking Changes
| Keyword | CB247 Rank | Competitor Rank | Gap | Action Needed? |
|---------|-----------|-----------------|-----|---------------|
| [Keyword] | [#] | [Competitor @ #] | [+/- n] | [Yes/No] |

---

## Gaps and Opportunities

### Content Gaps Identified
| Gap | Competitor Has? | CB247 Should Add? | Priority |
|-----|-----------------|-------------------|----------|
| [Gap 1] | [Yes/No] | [Yes/No] | [P1/P2/P3] |

### Quick Wins Available
| Quick Win | Effort | Impact | Recommendation |
|-----------|--------|--------|----------------|
| [Win 1] | [Low/Med/High] | [Low/Med/High] | [Action] |

---

## Recommendations for Next Month

### Immediate (Week 1)
1. **[Recommendation 1]** — [Why it matters]
2. **[Recommendation 2]** — [Why it matters]

### Short-Term (Weeks 2-4)
1. **[Recommendation 1]** — [Why it matters]
2. **[Recommendation 2]** — [Why it matters]

### Strategic (Next Quarter)
1. **[Recommendation 1]** — [Why it matters]

---

## Resources / Access Needed
| Resource | Purpose | Requested From |
|----------|---------|---------------|
| [Resource 1] | [Purpose] | [Who] |

---

## Appendix: Data Sources
- Keyword rankings: [Tool name / N/A]
- Traffic data: [GA4 / N/A]
- Competitor data: [Tool name / Manual research]
- Technical issues: [Tool name / Audit findings]

---
*Report generated: [Date]*
```

---

## Report Frequency

| Report | Frequency | Day | Audience |
|--------|-----------|-----|----------|
| Weekly SEO | Every Monday | Monday | Internal marketing team |
| Monthly SEO | 1st Monday of month | Monday | Leadership/stakeholders |
| Quarterly Strategy | 1st Monday of quarter | Monday | Leadership/stakeholders |

---

## Dashboard Integration

For ongoing tracking, maintain a simple Google Sheets or Notion dashboard with:

### Tab 1: Keyword Rankings
| Keyword | Location | Target | Week 1 | Week 2 | Week 3 | Week 4 | Monthly Avg |
|---------|----------|--------|--------|--------|--------|--------|-------------|
| gym malaga | Malaga | Top 3 | | | | | |

### Tab 2: Content Pipeline
| Content | Type | Status | Assigned | Due | Published |
|---------|------|--------|----------|-----|-----------|
| Malaga LP Rewrite | Landing Page | Draft | [Name] | [Date] | [Date] |

### Tab 3: Technical Issues
| Issue | Severity | Reported | Status | Fixed Date | Notes |
|-------|----------|---------|--------|------------|-------|
| [Issue] | [Critical/High/Med] | [Date] | [Open/Fixed] | [Date] | [Notes] |

---

## Quality Checklist
- [ ] Weekly report sent every Monday (even if no wins, still report)
- [ ] Monthly report includes all KPIs from seo-targets-cb247.md
- [ ] Ranking data updated (or N/A noted if tools unavailable)
- [ ] Traffic data included (or N/A noted if GA4 not connected)
- [ ] Competitor activity tracked
- [ ] Actionable next steps in every report
- [ ] No jargon — write for non-SEO people
- [ ] Reports saved with correct naming convention and date stamp
- [ ] Distribution list confirmed (who receives the report)
