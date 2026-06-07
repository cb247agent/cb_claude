# MWCC Per-Centre Deep-Dive Page — Build Spec

**Audit reference:** Tier 3 item 3.4 (`outputs/mwcc/audit-mwcc-vs-cb247-2026-06-07.md`)
**Status:** Spec'd · ready for next focused session in `docs/index.html`
**Owner of build:** AI (engineering pass) + Tia (acceptance)

---

## Why this page is needed

MWCC has 5 centres with different service mixes, occupancy profiles, and competitive pressures. Existing per-centre views are **scoped to one metric type at a time**:

| Existing page | Scope |
|---|---|
| `renderMwccOccupancy` | Occupancy + compliance risk per centre |
| `renderMwccEnrolments` | Enrolment + enquiry + wage per centre |
| `renderMwccOverview` | Network-level rollup |
| `renderMwccSeo` / `renderMwccGads` / `renderMwccMeta` | Cross-centre but channel-scoped |

**What's missing:** A single-screen view where Kelley or Tia picks ONE centre (e.g., Midvale) and sees **every metric for that centre** — occupancy, enrolments, ads spend, organic search, GBP performance, Work Queue actions in flight, recent campaign performance.

Today this requires clicking across 4-5 pages and filtering each. The deep-dive page would collapse that to one click.

---

## What data already exists per centre

| Metric | Source | Granularity | Ready? |
|---|---|---|---|
| Occupancy % per room | `state/mwcc-ops.json` → `centres[*].occupancy` | Per room (Babies, Toddlers, etc) per centre | ✅ |
| Enquiries | `state/mwcc-ops.json` → `centres[*].enquiries` | Per centre | ✅ |
| Revenue | `state/mwcc-ops.json` → `centres[*].revenue` | Per centre | ✅ |
| Wage % | `state/mwcc-ops.json` → `centres[*].wage_inc_leave_pct` + `wage_breach` | Per centre | ✅ |
| Compliance risk rooms | `state/mwcc-ops.json` → `network_summary.rooms_with_compliance_risk` | Per centre via lookup | ✅ |
| Google Ads spend / clicks / conv | `state/mwcc-ads.json` campaigns | Per centre ONLY IF campaigns are named by centre — check current naming convention | ⚠️ partial |
| Meta spend / CTR / CPC | `state/mwcc-meta.json` ad sets | Per centre ONLY IF ad sets are named by centre | ⚠️ partial |
| GA4 sessions / conv / device | `state/mwcc-ga4.json` | Currently NETWORK-LEVEL only — no per-centre attribution | ❌ needs UTM landing-page tagging |
| GSC clicks / position / impressions | `state/mwcc-gsc-data.json` | Per page (centre pages) | ✅ via URL filter |
| GBP actions (calls, directions, etc) | `state/mwcc-gbp-performance.json` | Per centre location ID | 🚫 quota pending |
| Vacation Care booking fill | `context/mwcc-vacation-care-bookings.json` | Per centre per window | ✅ (scaffolded) |
| Work Queue actions in flight | `state/mwcc-work-queue.json` filtered by centre name in title/description | Per centre via filter | ✅ (heuristic match) |
| NQS rating | `context/mwcc-nqs-ratings.json` | Per centre | ⚠️ scaffolded, Kelley to populate |

---

## Render function signature (proposed)

```js
function renderMwccCentreDeepDive(centreId) {
  // centreId is one of: 'armadale' | 'midvale' | 'rockingham' | 'seville-grove' | 'waikiki'
  // Default: read from URL hash on first load, default 'midvale' (highest enrolment risk)
  // Persist selection to localStorage 'mwcc-deep-dive-centre' so refresh holds
}
```

Trigger from nav: add "Centre Deep-Dive" entry in MWCC sidebar — same chip pattern as existing pages. Centre picker is a 5-button bar at the top of the page (purple-pill style per `mwcc-design-standards.md`).

---

## Page layout (top → bottom)

1. **Centre picker bar** — 5 buttons (one per centre, purple-pill design). Active centre highlighted.
2. **Hero strip** — Centre name + suburb + service-type badges (LDC/OSHC) + current occupancy % + alerts (compliance risk · wage breach)
3. **KPI row** — 6 KPI cards in a row:
   - Occupancy %
   - Enquiries this week
   - Revenue (weekly)
   - Wage ratio %
   - GBP rating (if data available, else "pending")
   - Work Queue actions in flight
4. **Funnel block** — narrowed to this centre's enquiries → enrolments (uses `state/mwcc-funnel.json` per-centre block)
5. **Per-room occupancy table** — for LDC + OSHC mix centres, show each room's occupancy + capacity + compliance status
6. **Paid performance row** — Google Ads (if centre-scoped campaign exists) + Meta (if ad set exists). If not scoped, show "Network-level paid — open Google Ads / Meta page for breakdown."
7. **Organic search row** — top GSC queries for this centre's URL (`/centres/{slug}/`) + position + clicks
8. **Vacation Care section** — only for 4 OSHC-providing centres (Armadale, Midvale, Rockingham, Seville Grove). Shows current window fill % + days to close.
9. **Work Queue actions panel** — full list of Work Queue actions whose title or description mentions this centre. Use 6-column standard layout: no. · action · owner · effort · priority · expected impact.
10. **Compliance status panel** — NQS rating from `context/mwcc-nqs-ratings.json`, wage status, compliance risk rooms. Locked policies reminders.
11. **Recent campaigns** — last 2 campaigns where this centre was in scope (read from `CB_Brain/wiki/MWCC-Campaign-History.md` — needs a parser hook).

---

## CSS / palette

Per `mwcc-design-standards.md`:
- Lavender + black + gray only
- Centre badge: `var(--mwcc-pale)` background + 3px purple left border
- Risk badges: `var(--mwcc-risk)` (#ef4444) for compliance, `var(--mwcc-warn)` (#f59e0b) for wage
- KPI cards: same purple variants used in `renderMwccOverview`

---

## State plumbing

```js
cbState.mwccDeepDive = {
  centre: 'midvale',                     // selected centre id
  data: null,                            // per-centre composite computed on switch
};

window.switchMwccCentre = function(centreId) {
  cbState.mwccDeepDive.centre = centreId;
  localStorage.setItem('mwcc-deep-dive-centre', centreId);
  cbState.mwccDeepDive.data = composeCentreView(centreId); // helper that filters state files
  renderMwccCentreDeepDive(centreId);
};
```

`composeCentreView(centreId)` is a new helper that takes the centre id and returns an object containing the filtered slices of `mwccOps`, `mwccAds`, `mwccMeta`, `mwccGa4`, `mwccGsc`, `mwccGbp`, `mwccFunnel`, `mwccWorkQueue`, `mwccVacationCare`. Centralised so each section just reads from `cbState.mwccDeepDive.data`.

---

## Per-centre attribution gaps to flag in UI

When data isn't truly per-centre (GA4, sometimes Google Ads / Meta), show an info chip on the relevant block:

> ⓘ Network-level metric — per-centre attribution requires UTM landing-page tagging on `/centres/{slug}/`. Open Google Ads page for full breakdown.

Don't hide the network number — just be honest about the granularity.

---

## Build sequence (estimated)

| Step | Task | Effort |
|---|---|---|
| 1 | Add nav entry + URL hash routing | 30 min |
| 2 | Add `cbState.mwccDeepDive` + `switchMwccCentre` + `composeCentreView` helper | 1h |
| 3 | Write `renderMwccCentreDeepDive` function — sections 1-6 (the data-ready ones) | 2h |
| 4 | Sections 7-9 (organic search + vacation care + work queue panel) | 1.5h |
| 5 | Sections 10-11 (compliance + campaign history) | 1h |
| 6 | Test all 5 centres, refresh-persistence, palette compliance | 30 min |
| 7 | Commit + deploy | 15 min |

**Total estimated:** ~6.5 hours focused work on `docs/index.html`.

---

## When to actually build this

The audit deferred this to "build when Group Overview proves insufficient." Specifically: build when Kelley reports she's clicking across multiple pages weekly to assess a single centre — that's the signal the page would have measurable value.

If Kelley currently manages without it, defer to Q4 2026 when MWCC volume grows and the multi-page navigation becomes friction.

---

*Spec drafted 2026-06-07 · Build estimated 6.5h focused on docs/index.html · Build when Kelley flags multi-page friction*
