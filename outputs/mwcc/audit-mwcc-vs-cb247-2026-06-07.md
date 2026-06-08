# MWCC vs CB247 Architecture Audit — 7 Jun 2026

**Author:** AI (manual audit, not skill-driven)
**Active business when audit ran:** MWCC
**Scope:** Compare every layer of the marketing OS — recommend gaps to close in MWCC.

---

## 0. Headline

MWCC is **75% architectural parity** with CB247 — pipelines exist, emitters exist, agents exist, dashboard exists, email digest exists, brand-aware skills foundation exists.

What's missing now is **not more architecture — it's depth in the things MWCC already has**, plus a small number of MWCC-specific items that CB247 simply doesn't need (regulatory compliance, photo consent, multi-centre aggregation, school holiday seasonality).

The big risk areas are **compliance, manual data ingest, and content quality at scale** — not technical infrastructure.

---

## 1. Side-by-side inventory

| Layer | CB247 | MWCC | Gap |
|---|---|---|---|
| **Agents (.yml)** | 9 | 4 | 5 agents missing — biggest: Performance Agent, SEO Agent, Paid Ads Agent |
| **Skills (brand-aware)** | 38 (all default-CB247) | 2/38 refactored | 36 unrefactored — MWCC content via skills currently produces CB247-flavoured output unless skill is one of the 2 done |
| **Context files** | 21 files | 8 files | Missing: session-start, seasonal-calendar, psychology-triggers, design-standards, content/audience/competitor JSON contexts |
| **Pull scripts** | 12 | 6 | Missing: GBP (Metricool — quota pending), Apify (social), automated OWNA ingest |
| **Work Queue emitters** | 6 (meta, gads, gbp, social, membership, seo) | 4 (meta, gads, seo, enrolment) | MWCC missing GBP emitter + social emitter |
| **Bake scripts** | 3 | 1 | MWCC: report baker only (no separate dashboard baker — intentional) |
| **State files** | 20+ | 11 | MWCC missing: campaign-history, kpi-ledger, photo-consent registry, NQS rating tracker |
| **Knowledge Base** | 243 lines, mature | 185 lines, foundation | MWCC needs: blog standard, campaign history, more historical learnings |
| **Dashboard pages** | 9 (+ KB pages) | 13 (more granular per-centre views) | MWCC actually ahead here — Enrolments + Occupancy + Action Tracker |
| **Email digest** | 3 scripts (weekly, team, SEO) | 1 script (weekly) | MWCC missing team emails + SEO digest |
| **Cron jobs** | 3 launchd + crontab entries | 1 crontab entry | MWCC missing: data refresh launchd, SEO email cadence |
| **Brain wiki pages** | 5 MWCC-relevant | 2 (MWCC-KB, Agent-Learnings shared) | Missing: SEO-Learnings-MWCC, Campaign-History-MWCC |

---

## 2. What MWCC does BETTER than CB247

Before listing gaps — credit where due:

1. **More granular dashboard pages.** MWCC has 13 render functions vs CB247's 9 — per-centre Enrolments + Occupancy + Action Tracker. CB247 only has Group Overview at the multi-location level.
2. **Cleaner per-archetype emitter design.** MWCC Enrolment emitter is purpose-built for childcare (per-room, regulatory ratios, wage_breach flag) — more domain-tight than membership_emitter is for gym.
3. **Tighter brand voice doc.** mwcc-brand-voice.md has explicit Do/Don't tables with example posts (good + bad). CB247's brand-voice.md is older and lighter.
4. **Per-centre Work Queue ownership matrix.** mwcc-team-roster.md explicitly maps every archetype to a default owner — better-documented than the equivalent on CB247.
5. **Locked business-config.json with versioning.** MWCC has a canonical config doc (5 centres, competitors, owners, thresholds, KPI targets) versioned 1.0.0. CB247's equivalent is scattered across files.

---

## 3. Gaps — grouped by tier

### TIER 1 — Fix in the next 2 weeks (high-impact, mostly compliance + reliability)

These have the biggest downside risk if left unfixed.

#### 1.1 No automated OWNA file ingest

**Current state:** Kelley manually exports `MYWORLD_REPORT.xlsx` + `utilisation.xlsx` from OWNA every Monday and drops them in `mwcc-inbox/` before 1:55pm. Pipeline parses them at 2pm.

**Why it's a problem:** Manual = fragile. If Kelley is sick / forgets / drops the wrong file → entire MWCC week's report is wrong. No fallback. This is the single biggest operational risk.

**Recommendation:** Pick one of:
- **(a) Google Drive watch folder** — Kelley schedules OWNA export to her Drive on Sundays. Scheduled task pulls Sunday-night file into `mwcc-inbox/` automatically. Cheapest fix.
- **(b) OWNA API integration** — if OWNA exposes API. Best long-term.
- **(c) Email-parse fallback** — Kelley sends report to a dedicated inbox; scheduled task pulls + parses. Middle option.

**Owner:** Tia (decision) + Kelley (procedural change) + AI (implementation).
**Effort:** 4-8 hours depending on option.

#### 1.2 No photo consent registry

**Current state:** Brand voice doc says "DON'T use children's photos without parental consent — always check before publishing." But "checking" is informal. There's no source of truth.

**Why it's a problem:** Regulatory + reputational risk. If a photo is published without consent, it's a real complaint with potential ACECQA implications. Currently relies on Jordan/Kelley memory.

**Recommendation:** Build `state/mwcc-photo-consent.json` — registry per image. Each entry: image hash, centre, children visible, consent file location, consent expiry date, OK to publish flag. Hook into output pipeline: before publishing a post with an image, check the registry.

**Owner:** Kelley (data entry) + AI (system).
**Effort:** 6 hours system + ongoing maintenance.

#### 1.3 No compliance check at sync-to-Supabase

**Current state:** Actions written by emitters / extracted from agent outputs flow directly to Work Queue. No filter for banned language.

**Why it's a problem:** A skill or agent could output "Best childcare in Armadale — book now before spots run out" — and that action goes into the Work Queue, gets approved by Kelley (who might miss it), gets published. Compliance breach.

**Recommendation:** Add a `compliance_check()` step inside `mwcc_sync_to_supabase.py`. Reject any action whose title/description contains banned terms: `best`, `premier`, `leading`, `#1`, `guaranteed`, specific NQS rating numbers without verification flag. Log rejections to `state/mwcc-compliance-rejections.json` for review.

**Owner:** AI.
**Effort:** 2 hours.

#### 1.4 No MWCC-specific session-start file

**Current state:** Per CLAUDE.md session start protocol, CB247 has `context/session-start.md` (ops state, priorities, what's done, what's missing). MWCC has nothing.

**Why it's a problem:** Every new session targeting MWCC has to re-derive context from scratch. AI doesn't know what's actively running, what's blocked, what's the immediate priority. Wasted tokens + wrong defaults.

**Recommendation:** Create `context/mwcc-session-start.md` mirroring CB247's structure. Update it weekly when the cron runs. Add a step to `weekly-report-mwcc.sh` that regenerates it.

**Owner:** AI.
**Effort:** 2 hours.

#### 1.5 No MWCC-specific seasonal calendar

**Current state:** Seasonal info is buried in `mwcc-marketing-strategy.md` §"Seasonal calendar". CB247 has standalone `context/seasonal-calendar.md` that's checked by session start protocol every session.

**Why it's a problem:** School holidays are MWCC's biggest demand spike (4×/year) — Vacation Care + LDC tour booking. Currently sessions don't know which holiday is next or how many days away. The content calendar I just built knew because I checked manually. That's not scalable.

**Recommendation:** Create `context/mwcc-seasonal-calendar.md`. Include: per-term WA school holiday dates, Vacation Care booking windows, Term 3/4 enrolment closes, 2027 Kindy waitlist opens, public holidays. Update annually. Session start protocol reads it.

**Owner:** AI.
**Effort:** 2 hours.

---

### TIER 2 — Build in the next 4-8 weeks (content quality + operational depth)

These don't fail loudly but compound over time.

#### 2.1 Performance Agent for MWCC

**Current state:** CB247 has `agents/performance.yml` — synthesises GA4 + GSC + Google Ads + Meta + GBP weekly into a narrative. MWCC has none. Centre Performance agent exists but it's per-centre narrative, not cross-channel synthesis.

**Recommendation:** Build `agents/mwcc/performance-mwcc.yml` modelled on CB247's. Reads all MWCC state files weekly, writes `outputs/research/performance-mwcc-YYYY-MM-DD.md`. Outputs proposed_actions block per Agent Action Contract.

**Owner:** AI build + Tia review.
**Effort:** 3 hours.

#### 2.2 Brand-aware refactor — next 6 skills

Per the contract migration order from `SKILLS_BRAND_CONTRACT.md`:

| Priority | Skill | Why this one next |
|---|---|---|
| 3 | content-writer | Most-invoked generic content skill |
| 4 | social-content-calendar | Required to make content calendars repeatable (currently I built one manually) |
| 5 | email-funnel-builder | Email broadcasts in Phase 2 + Phase 4 of school holiday calendar |
| 6 | paid-ads-creative-pipeline | Joanne needs MWCC ad creative briefs |
| 7 | creative-brief-engine | Jordan's weekly creative brief intake |
| 8 | local-seo-optimizer | Per-centre GBP + local-pack optimisation |

**Owner:** AI.
**Effort:** ~12 hours total (~2 hrs/skill including testing).

#### 2.3 MWCC psychology-triggers.md

**Current state:** Shared `context/psychology-triggers.md` is written for gym/fitness buyer psychology. Childcare-buyer psychology is fundamentally different — loss aversion on missing spots, social proof from peer parents, future-orientation (child outcomes), guilt management (working parent guilt), trust-building (safety of child).

**Why it's a problem:** Content skills pulling from generic triggers will produce off-target copy for childcare. Subtle but persistent voice drift.

**Recommendation:** Write `context/mwcc-psychology-triggers.md`. 8-12 triggers specific to childcare. Add to brand contract resolution table.

**Owner:** AI + Tia review.
**Effort:** 3 hours.

#### 2.4 MWCC design-standards.md (currently marked "todo")

**Current state:** `scripts/set_active_business.py` resolution table has `design-standards → mwcc-design-standards.md (todo)`. File doesn't exist. CB247 has `context/design-standards.md` — covers colours, fonts, blog layout, image sizes, button styles.

**Why it's a problem:** Anyone (Jordan, AI, Mark) producing MWCC visual content has no canonical reference. Lavender palette is documented in brand-voice.md but other standards (fonts, blog hero ratio, button styles, mobile breakpoints) aren't.

**Recommendation:** Write `context/mwcc-design-standards.md` — clone CB247's structure, swap palette + fonts + brand-specific elements.

**Owner:** AI + Tia review.
**Effort:** 2 hours.

#### 2.5 NQS rating tracker

**Current state:** Brand voice doc says "NEVER imply a specific NQS rating unless confirmed and current". But "current" is checked manually. No source of truth.

**Why it's a problem:** ACECQA NQS rating can change — re-assessment updates the rating. If a centre's rating drops and content still claims old rating → compliance issue.

**Recommendation:** Build `state/mwcc-nqs-ratings.json` — per centre: current rating, rating date, next assessment due, evidence link. Surface on dashboard. Block content that mentions a rating not matching this file.

**Owner:** Kelley (data) + AI (system).
**Effort:** 4 hours.

#### 2.6 SEO Agent for MWCC

**Current state:** CB247 has `agents/seo-agent.yml`. MWCC has none. SEO emitter exists but it's rule-based — no agent-level strategy synthesis.

**Recommendation:** Build `agents/mwcc/seo-agent-mwcc.yml`. Reads GSC + Ahrefs + per-centre keyword targets. Writes weekly SEO narrative + proposed_actions for John.

**Owner:** AI.
**Effort:** 3 hours.

---

### TIER 3 — Build when scale demands (depth features)

These matter when MWCC volume grows. Not blocking now.

#### 3.1 Vacation Care booking funnel dashboard

Per-centre, per-holiday-window: bookings opened, current bookings, capacity remaining. Wire into work-queue alerts when capacity < 80% with 7 days to go.

#### 3.2 Tour-booking conversion dashboard

GA4 events: tour-form-view → tour-form-submit → tour-attended → enrolled. Show conversion rate at each step per centre. Identify which centre has the lead-leak.

#### 3.3 ~~CCS quote calculator integration~~ — OUT OF SCOPE (08 Jun 2026)

**Scope ruling:** Removed from the audit per Tia direction.

**Why out of scope:** The CCS calculator itself is a **website feature** owned by Mark + Webflow, not a marketing OS feature. Building it sits with the website/product team. The marketing OS would only track its conversion rate if/when the calculator exists — and even that tracking would land in the existing enrolment funnel (item 3.2), not as a separate workstream.

**What would re-open it:** If Mark builds the calculator and we need a dedicated funnel widget to track quote-start → quote-complete → tour-booking, raise it as a Layer-1 tracking task at that point. Until then, the marketing OS does not own this.

#### 3.4 Per-centre deep-dive pages

CB247 pattern: per-location dashboard. MWCC has 5 centres. Group overview is good. But per-centre deep-dive (showing only that centre's GA4, Meta, Google Ads, GBP, occupancy, wage ratio) would let Kelley action centre-specific issues without filtering across the whole network.

#### 3.5 Paid Ads Agent for MWCC

Cross-channel paid synthesis (Meta + Google Ads + budget reallocation recommendations) for Joanne.

#### 3.6 Audience-intel + content-intel subagents

Lightweight Haiku subagents for fast research lookups (cf CB247's audience-intel.yml + content-intel.yml).

#### 3.7 Refactor remaining 30 skills

Lower priority — most don't apply to MWCC weekly content rhythm.

#### 3.8 Automated review monitoring

5 GBPs + Facebook + Google Reviews — currently Kelley manually checks. Build a daily pull + sentiment classifier + alert when negative review fires.

#### 3.9 Engineering / Handoff docs MWCC section

CB247 has HANDOFF.md and ENGINEERING.md. Add MWCC-specific sections (file paths differ, OWNA flow specific, compliance rules specific).

#### 3.10 Campaign-history file for MWCC

`state/mwcc-campaign-history.json` — track every campaign run, outcome, learnings. Currently no campaigns ran. Set up the file structure now so first campaign auto-logs.

---

## 4. Tier 1 — recommended execution order

If you want to fix the biggest risks first, this is the order:

| # | Task | Effort | Why first |
|---|---|---|---|
| 1 | Compliance check at sync-to-Supabase | 2h | Cheapest fix, eliminates banned-language risk immediately |
| 2 | MWCC session-start.md + seasonal-calendar.md | 4h | Every future session benefits — compounding payoff |
| 3 | Photo consent registry | 6h | Hard compliance rule needs system-enforced answer |
| 4 | Automated OWNA file ingest | 4-8h | Single biggest operational fragility |

Total: ~16-20 hours of work. Could be done in a focused 2-day sprint.

---

## 5. What I am explicitly NOT recommending

To prevent scope drift:

- **Don't rebuild the dashboard.** MWCC dashboard is actually richer than CB247's. Leave it.
- **Don't build a second MWCC agent set right away.** 4 agents is enough for current data volume. Add more when first 4 have a hit-rate baseline.
- **Don't refactor all 38 skills now.** Per the contract, refactor lazily. 6 more in Tier 2 is enough.
- **Don't build OWNA-API integration if a Drive watch folder works.** Lower complexity beats elegance.
- **Don't add per-centre deep-dives until Group Overview proves insufficient.** Premature.

---

## 6. Open questions that should drive decisions

These need answers from you before some of the above can proceed:

1. **OWNA API access** — does OWNA expose an API? If yes, option (b) for §1.1 becomes viable.
2. **Photo consent storage** — where do signed consent forms live now (Google Drive / OWNA / paper)? Affects §1.2 design.
3. **Who maintains seasonal-calendar.md** — Tia annually, or auto-pulled from a public WA Education term-dates feed?
4. **NQS rating refresh cadence** — Kelley monthly check, or alert-driven from ACECQA website scrape?
5. **Email digest expansion to Kelley + Denver** — was paused, want to revisit?

---

## 7. Suggested next session plan

If you want to attack Tier 1 in a single session:

1. **Hour 1:** I write compliance check + `mwcc-session-start.md` template + `mwcc-seasonal-calendar.md`.
2. **Hour 2:** I write photo-consent registry schema + sync hook.
3. **Hour 3-4:** I design + implement OWNA ingest option (choice required first).
4. **Hour 5:** Test full pipeline + commit + push.

Or you can pick individual items — they're independent.
