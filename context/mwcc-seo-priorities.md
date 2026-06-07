# MWCC SEO Priorities

**Tactical priority list for SEO work. Read this with `context/mwcc-seo-targets.md` when planning SEO sprints.**

---

## Priority levels

- **P1** — act this fortnight. Blocks downstream work or addresses urgent gap.
- **P2** — act this quarter. Important but no immediate blocker.
- **P3** — backlog. Worth doing when capacity allows.

---

## P1 — Next fortnight

### 1. Build 5 centre landing pages
- **What:** One `LocalBusiness`-schema-rich page per centre at `/centres/[suburb]/`
- **Why:** Local pack rankings need a dedicated page per location. Currently MWCC may share a single contact page.
- **Owner:** John (web) + Jordan (creative brief)
- **Effort:** 5 days
- **Success metric:** All 5 centres appear in local pack for their primary suburb query within 30 days

### 2. Build the `/oshc/` service hub
- **What:** Single page targeting "OSHC Perth" + "before and after school care perth"
- **Why:** OSHC is 4 of 5 centres — high-leverage page
- **Owner:** John
- **Effort:** 2 days
- **Success metric:** Pos 11–20 within 30 days for "oshc perth"

### 3. Fix any per-page title tag with "—" or missing brand suffix
- **What:** Run `scripts/run_screaming_frog.py` (when wired for MWCC), audit titles, fix any not ending in "| My World Childcare"
- **Why:** Brand consistency + SERP click-through
- **Owner:** Mark (publishing)
- **Effort:** Half day

---

## P2 — This quarter

### 4. Build `/long-day-care/` service hub
- Same pattern as `/oshc/` but for LDC centres (Midvale, Seville Grove, Waikiki)
- Effort: 2 days
- Owner: John

### 5. Build `/vacation-care/` service hub with seasonal CTAs
- Updated each term break
- Effort: 2 days + ongoing maintenance
- Owner: John + Jordan (content)

### 6. Publish 4 long-tail content pieces
- "What is CCS and how do I apply"
- "What age can my child start LDC in WA"
- "Settling your child into childcare"
- "Long day care vs family day care"
- Owner: Jordan briefs, John publishes
- Effort: 1 day per piece (briefing + writing + technical SEO)

### 7. Migrate URL structure to convention
- Move existing pages to `/centres/[suburb]/` if currently at `/[suburb]/` or other paths
- 301 redirect from old URLs
- Owner: Mark (Webflow)
- Effort: 1 day

### 8. Schema markup audit + fix
- Add `LocalBusiness` + `EarlyChildhoodEducation` schema to centre pages
- Add `Service` + `offers` to service hubs
- Validate with Google Rich Results Test
- Effort: Half day
- Owner: John

---

## P3 — Backlog

### 9. Local guide pages (`/[suburb]-childcare-guide/`)
- Review-style page comparing MWCC + competitors in each suburb
- Long-tail value but lower commercial intent
- 5 pages — one per centre suburb
- Effort: 2 days per page (research + writing)

### 10. Topical blog cluster — "first day at childcare"
- 6-8 posts covering settling, first day prep, what to pack, sleep transition, etc.
- Drives top-of-funnel awareness
- Effort: 1 day per post

### 11. Citation building — Aussie childcare directories
- Add MWCC to: Care for Kids, KindiCare, Toddle, ChildcareCentral
- Each gives a DR-40+ backlink + local pack signal
- Effort: 0.5 day per directory

### 12. Branded internal search optimisation
- "My World Childcare [suburb]" — improve SERP click-through for branded variant queries
- Add FAQ schema to each centre page
- Effort: 0.5 day per page

---

## What's already done

(Update this section as items move from P1/P2 to done.)

- [x] GSC connected — confirmed via state/mwcc-gsc-data.json (07 Jun 2026)
- [x] GA4 connected — confirmed 3,272 sessions this week (07 Jun 2026)
- [x] cb_agent@chasingbetter.com.au granted Restricted user on GSC + Viewer on GA4

---

## Performance targets

| Metric | Now (07 Jun 2026) | Target (end Q3) |
|---|---|---|
| Total ranking keywords | ~10 branded | 50+ commercial |
| Avg position (commercial keywords) | unknown — needs GSC pull | <15 |
| Organic clicks/wk | <50 | 200+ |
| Pages on the GBP local pack | 0 of 5 | 5 of 5 |
| Schema-validated pages | ~0 | All centre + hub pages |

---

## How to use this doc

1. SEO Agent reads this every Monday during Phase 2.
2. SEO emitter (`mwcc_seo_emitter.py`) refers to this when proposing actions — actions should map to the P1/P2 backlog when possible, vs ad-hoc proposals.
3. Tia + John review at the end of each quarter — promote P3 items if completed P1+P2, demote P1 items that haven't moved in 4 weeks (reprioritise or kill).
