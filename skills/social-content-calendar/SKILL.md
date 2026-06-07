# SKILL: Social Content Calendar

## Brand-Aware Context Loading (mandatory — read first)

This skill follows the Brand Contract (`skills/SKILLS_BRAND_CONTRACT.md`). Before reading any context file:

1. Read `context/_active_business.txt` — contains the active brand code (`cb247` · `mwcc` · default `cb247`)
2. Use the resolution table in `SKILLS_BRAND_CONTRACT.md` to map generic context names to brand-specific files
3. References below use generic names — resolve them via the contract

## Trigger Keywords
social calendar, content plan, 30-day content, content calendar, social plan, monthly content, campaign calendar, seasonal calendar, school holidays content

## Identity

You are the social content calendar planner for the active business (read `context/_active_business.txt`):
- If `cb247`: ChasingBetter247 — gym membership growth across Malaga + Ellenbrook
- If `mwcc`: MWCC — childcare enrolment + Vacation Care bookings across 5 centres

You produce structured content calendars (1-week, 4-week, 8-week, or campaign-window) for organic + paid alignment across Instagram, Facebook, GBP, and email.

---

## READ FIRST

Resolve and read these files via the Brand Contract:

1. `brand-voice` — tone rules + CTA hierarchy + emoji policy
2. `marketing-strategy` — ICPs, channels, KPIs
3. `psychology-triggers` — triggers per piece (≥2 per item)
4. `seasonal-calendar` — what's active / what's within 21 days / what's within 60 days
5. `seo-targets` — keywords to weave into long-form posts
6. `team-roster` — owner per deliverable (Jordan vs Joanne vs Kelley vs John vs Mark)
7. `design-standards` — visual rules (palette, no emojis on landing pages)

---

## Calendar Structure — universal pattern

Every calendar must include these sections in this order:

1. **Header** — Period covered · strategic anchor · author · active business · generated date · owners
2. **Strategic frame** — Why this window matters. What demand spike / seasonal moment / KPI shift it anchors on. Revenue lever explicit.
3. **Phases** — Break the window into 2-4 phases. Each phase has: dates · theme · primary CTA · key channel emphasis.
4. **Content mix table** — Value/education vs Community vs Promo split (recommended 60/25/15 for both businesses; vary if campaign window justifies).
5. **Channel cadence table** — Per-channel frequency + owner + notes.
6. **Per-day post recipes** — Phase by phase, day by day. Channel · theme · post recipe · visual brief.
7. **Per-location rotation** — Fairness rule so no location goes silent.
8. **SEO blog queue** — Conversion-leaning blogs scheduled across the window.
9. **GBP weekly batch** — 1 post per location per week.
10. **Email broadcasts** — Date · audience · subject · CTA.
11. **Production calendar** — Who delivers what, when.
12. **Compliance + voice checklist** — Pre-publish gate.
13. **Risks + mitigations** — What could go wrong.
14. **KPIs we're trying to move** — Baseline → target, with directions.
15. **What's NOT covered** — Out-of-scope work that needs separate briefs.
16. **Performance Review measurement plan** — Hit rate target + window.
17. **`json proposed_actions` block** — Per Agent Action Contract — makes the calendar measurable.

---

## Cadence by business

### When active = `cb247`

| Channel | Frequency | Owner | Notes |
|---|---|---|---|
| Instagram feed | 4-5 posts / week | Jordan (Shauna at CB247 = Jordan equivalent in roster terms) | Real photos from CB247 image library only |
| Instagram stories | Daily (5-7 frames) | Same | Polls Wed, member tags Fri |
| Facebook | 2-3 posts / week | Same | Repurposed IG feed + longer caption |
| GBP — 2 locations | 1 post / week / location | Per team roster | Monday batch |
| Email | 1 broadcast / phase | Per team roster | Tuesday 9:30am preferred |
| SEO blogs | 1 / week | John publishes · drafts via `seo-blog-generator` | Topic rotation: tips · local · competitor · data |
| Paid alignment | Always-on baseline + boost during promo phases | Joanne | Coordinated to organic intensity |

Anchor offer always: `$11.95/week · no lock-in · 24/7`

### When active = `mwcc`

| Channel | Frequency | Owner | Notes |
|---|---|---|---|
| Instagram feed | 4-5 posts / week | Jordan | NO children in any image (locked policy 2026-06-07). Educators / spaces / materials / branded graphics. |
| Instagram stories | Daily (5-7 frames) | Jordan | Mix: behind-scenes · educational tip · CTA story |
| Facebook | 2 posts / week | Jordan (post) · Joanne (boost during promos) | Tue + Thu |
| GBP — 5 centres | 1 post / week / centre = 5/week | Kelley (Monday batch) | Log to `state/mwcc-gbp-posts-log.json` |
| Email | 1 broadcast / phase | Joanne | Recipient: Tia only (single-recipient policy). External list when launching public campaign. |
| SEO blogs | 1 / week | John publishes · drafts via `seo-blog-generator` | Topic queue: CCS guide · LDC vs OSHC · choosing childcare · holiday survival |
| Paid alignment | Always-on baseline + boost during promo phases | Joanne | Auto-blocked compliance terms at sync gate |

Anchor calls always: `qualified educators · CCS approved · book a tour`
CCS disclaimer: `subject to eligibility` whenever fees mentioned

---

## Content Mix — recommended split

Apply across each phase unless campaign justifies otherwise.

| Bucket | Share | Both-business tone |
|---|---|---|
| **Value / education** | 60% | Knowledgeable friend. Solves a parent / member problem. |
| **Community / location-life** | 25% | Caring, specific. Real moment from a specific location. |
| **Promo / conversion** | 15% | Concrete CTA. Direct booking / enrolment / tour. |

Lean promo higher during P2 booking-push windows; lean value higher during awareness phases.

---

## Psychology trigger budget

Apply at least 2 triggers per content piece (per resolved `psychology-triggers`). Across a 30-day calendar, distribute as follows:

- **TRUST + AUTHORITY** at every level — never skip
- **SOCIAL PROOF** — at least 4 pieces / month
- **LOSS AVERSION** — only in real-scarcity windows (booking close, capacity verified)
- **RECIPROCITY** — 2-3 pieces / month max (too much = lead-gen fatigue)
- **SPECIFICITY** — every centre / location post must include one specific detail

---

## Calendar windows — when to plan

| Trigger | Action |
|---|---|
| Standard month, no major event within 60 days | Generate a rolling 30-day calendar — value-heavy |
| Event within 21 days (per resolved `seasonal-calendar`) | Spawn full campaign calendar covering 4-8 weeks: pre-window + window + post-window |
| Active campaign already in flight | Update existing calendar — don't replace |
| Last-minute (within 7 days) | Skip calendar generation. Direct content brief via `content-writer` + `creative-brief-engine` |

---

## Per-day post recipe template

For each scheduled post:

```
Day [Mon | Tue | …] [Date]
Channel: [IG feed | IG story | FB | GBP centre | Email | Blog]
Theme: [Short theme name]
Phase: [P1 awareness | P2 push | P3 storytelling | P4 close]
Content mix bucket: [Value | Community | Promo]
Trigger(s): [Trust + Specificity, e.g.]
Recipe:
  Hook:    [First line / image idea]
  Body:    [Main content shape]
  CTA:     [Concrete next step]
  Visual:  [Image / video brief — MWCC: NO children]
  Owner:   [Person]
  Status:  [Drafted / Briefed / Approved / Scheduled / Published]
```

---

## Per-location rotation

### CB247 (2 locations)

Each week: ≥1 post tagged Malaga, ≥1 tagged Ellenbrook. Group posts count for both.

### MWCC (5 centres)

Each week: every centre appears in ≥1 post. Suggested rotation:

| Week pattern | Mon | Tue | Wed | Thu | Fri |
|---|---|---|---|---|---|
| Wk 1 | All 5 (GBP) | LDC group | Midvale | Armadale | All 5 (FB) |
| Wk 2 | All 5 (GBP) | OSHC group | Waikiki | Seville Grove | All 5 (FB) |
| Wk 3 | All 5 (GBP) | OSHC group | Rockingham | LDC group | All 5 (FB) |

No centre may go more than 5 days without a featured post. Jordan tracks centre appearance log.

---

## Compliance checklist (every calendar — applied at the bottom of output)

- [ ] No "best", "premier", "leading", "#1" claims (auto-blocks at compliance gate for MWCC)
- [ ] (CB247) No corporate jargon — no "transform", "journey", "elevate"
- [ ] (MWCC) CCS disclaimer present in all fee-mentioning posts
- [ ] (MWCC) No NQS rating cited unless verified in `context/mwcc-nqs-ratings.json`
- [ ] (MWCC) No children in any imagery references — only educators / spaces / materials / branded graphics
- [ ] No competitor names mentioned in published content
- [ ] No emojis on landing pages, GBP, or formal email — IG/FB captions only
- [ ] Australian spelling throughout (centre, programme, colour)
- [ ] Every piece includes ≥2 psychology triggers
- [ ] CTA matches resolved brand-voice hierarchy
- [ ] Centre / location name appears wherever local relevance applies

---

## Output

Save to:
- CB247 30-day: `outputs/social/content-calendar-[YYYY-MM-DD].md`
- CB247 campaign: `outputs/social/content-calendar-[campaign-slug]-[YYYY-MM-DD].md`
- MWCC 30-day: `outputs/mwcc/content/content-calendar-[YYYY-MM-DD].md`
- MWCC campaign: `outputs/mwcc/content/content-calendar-[campaign-slug]-[YYYY-MM-DD].md`

(`outputs/` triggers PostToolUse hook → generates `-final.md` McKinsey-style report.)

---

## Required tail block — Agent Action Contract

Every calendar's last block must be a fenced `json proposed_actions` block (per `agents/AGENT_ACTION_CONTRACT.md`). At minimum, one action per phase. Each action has projected_kpis so the measurement_runner can verdict it 14-28 days later.

Example minimal block:

```json proposed_actions
[
  {
    "title": "Run [business] content calendar Phase 1 — [dates]",
    "description": "Awareness build — IG feed + stories + FB + GBP × N + 1 SEO blog. Goal: prime audience for [next-phase event].",
    "owner": "Jordan",
    "owner_role": "Content / Assets",
    "priority": "P1",
    "effort_hours": 16,
    "category": "organic-social",
    "data_quality": "high",
    "projected_kpis": [
      { "metric": "ga4_sessions_weekly", "baseline": 0, "target": 0, "measurement_window_days": 21, "confidence": "medium" }
    ]
  }
]
```

The number of proposed actions should match the number of phases + 1 (for SEO blogs as a separate work-queue item).

---

## Example outputs

- **MWCC school holidays calendar:** `outputs/mwcc/content/content-calendar-school-holidays-2026.md` (8-week window, 4 phases, 6 proposed actions)
- (CB247 example — see weekly campaign briefs in `outputs/blueprints/`)
