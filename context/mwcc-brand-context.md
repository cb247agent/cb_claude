# Brand Context — My World Childcare

**Purpose:** Reference for all MWCC content generation, marketing copy, ad creative, SEO, and communications. Read before any MWCC content work.

---

## Identity

- **Full name:** My World Childcare (MWCC)
- **Short name:** My World / MWCC (internal)
- **Website:** myworldcc.com.au
- **Location:** Perth, WA — 5 centres
- **Operator type:** Private childcare group — Long Day Care (LDC) + Outside School Hours Care (OSHC)

---

## The 5 Centres

| Centre | Suburb | Service Type | Rooms |
|--------|--------|-------------|-------|
| Armadale | Armadale | OSHC only | Before School, After School |
| Midvale | Midvale | LDC + OSHC | Babies, Toddlers, Kindy, Before School, After School |
| Rockingham | Rockingham | OSHC only | Before School, After School |
| Seville Grove | Seville Grove | LDC + OSHC | Babies, Toddlers, Kindy, Before School, After School |
| Waikiki | Waikiki | LDC only | Babies, Toddlers, Kindy |

**Service definitions:**
- **LDC (Long Day Care):** Full-day care for children 0–6 years. Rooms: Babies (0–12m), Toddlers (1–3y), Kindy (3–5y).
- **OSHC (Outside School Hours Care):** Before School Care, After School Care, Vacation Care. School-age children (5–12y).
- **Vacation Care:** Holiday program for school-age children — runs during WA school holidays.

---

## What MWCC Sells

Not just childcare. A safe, nurturing world where children grow.

- **For parents:** Confidence that their child is safe, stimulated, and cared for by qualified educators
- **For children:** A rich early learning environment built around play-based education
- **For families:** Flexibility that fits working parents — consistent care across LDC + OSHC in one trusted group
- **Value proposition:** Quality care at competitive fees with CCS (Child Care Subsidy) accepted

---

## Voice & Tone

**Overall:** Warm, professional, reassuring. Parents are trusting us with the most important people in their lives — every word should feel like it comes from someone they can trust.

**Tone descriptors:**
- Caring and nurturing — not clinical or corporate
- Confident without being boastful
- Family-first — parents and children are always the centre
- Perth-local — community-connected
- Educational but approachable — not academic jargon

**NOT:**
- Edgy, intense, or sales-aggressive (that's CB247)
- Corporate press release language
- Passive voice
- Overclaiming ("best childcare in Perth" without evidence)

---

## Language Rules

| Use | Avoid |
|-----|-------|
| "Educators" not "staff" or "workers" | "childminders", "babysitters" |
| "Families" not "customers" | "clients", "consumers" |
| "Children" or "little ones" not "kids" in formal copy | "brats", "rugrats" |
| "Enrol" not "sign up" | "register", "buy" |
| "Qualified educators" when referring to staff | Unqualified claims about staff |
| "Approved provider" when citing regulation compliance | Vague regulatory claims |
| "Child Care Subsidy (CCS)" by full name first use | "CCS" without explaining it |

**NEVER write:**
- "Guaranteed" in relation to child outcomes or development milestones
- "Best" or "number one" childcare without evidence
- Any therapeutic or developmental claims without ACECQA / qualified basis
- Competitor names in published content
- Specific staff names without permission

---

## Tone by Channel

| Channel | Direction |
|---------|-----------|
| **Meta Ads (Facebook/Instagram)** | Warm, parent-focused. Lead with child safety, qualified educators, and community. Parent testimonials perform well. |
| **Google Ads** | Intent-based. Parents are searching for a specific need — lead with location, age group, and availability. Urgency (limited spots) works. |
| **Instagram Feed** | Authentic moments — children playing, learning, celebrating. Real photos from real centres. No stock photography. |
| **Instagram Stories** | Enrolment CTAs, holiday program promo, fee info, vacancy alerts — short-lived content is right for direct info. |
| **Facebook Page** | Community hub. Event announcements, holiday care dates, parent news, centre milestones. |
| **Website / Landing Pages** | Trust-building. Lead with ACECQA/NQS ratings, qualified educators, CCS eligibility, virtual tour. |
| **Email to families** | Personal, short, actionable. Newsletter-style for enrolled families. Enrolment CTA for enquirers. |
| **SEO / Blogs** | Educational parent content: childcare transition tips, CCS explainers, school readiness, holiday care guides. |

---

## Marketing Accounts

| Platform | Account / ID |
|----------|-------------|
| Meta Ads | act_2835637326727066 |
| Google Ads | 917-218-6113 (Manager: 569-719-3495) |
| GA4 Property | 315149021 |
| GSC Site | sc-domain:myworldcc.com.au |

---

## Regulatory & Compliance Context

MWCC operates under:
- **National Quality Framework (NQF)** — ACECQA standards
- **National Quality Standard (NQS)** — 7 quality areas rated by assessors
- **WA DGE** — Department of Education licensing (WA-specific)
- **Child Care Subsidy (CCS)** — Federal subsidy administered by Services Australia

**Content compliance rules:**
- Never imply a specific NQS rating unless confirmed and current
- Never promise specific developmental or educational outcomes
- Never use imagery of children without explicit signed consent from guardians
- CCS claims: always add "subject to eligibility" — never guarantee subsidy amount
- Vacancy claims: always verify current availability before publishing "spots available"
- Staff qualification claims: only say "qualified educators" — don't specify Cert III / Diploma / ECT ratios in marketing unless confirmed

---

## Key Marketing Messages (approved angles)

1. **Safety & trust** — "Your child is safe with us" — qualified educators, secure environments, approved provider
2. **Learning through play** — Play-based early learning, school-readiness focus for Kindy rooms
3. **Flexibility for working families** — LDC + OSHC under one group, consistent care
4. **CCS accepted** — "Reduce your fees with the Child Care Subsidy"
5. **Community connection** — Perth families, local educators, community events
6. **Holiday care** — Vacation Care programs for school-age children during WA school holidays

---

## CTA Hierarchy

1. **Primary:** "Enquire about a place" / "Book a tour"
2. **Secondary:** "Check your CCS eligibility"
3. **Tertiary:** "View our holiday program"

---

## OWNA — Operations Platform

MWCC uses **OWNA** as its childcare management platform.

- **MYWORLD_REPORT.xlsx** — Weekly Wage Monitor (exported from OWNA → Reports)
- **utilisation.xlsx** — Occupancy / Utilisation report (exported from OWNA → Reports)
- Both files dropped to `mwcc-inbox/` by 1:55pm Monday before the weekly pipeline runs
- Parsed by `scripts/parse_mwcc_ops.py` → `state/mwcc-ops.json`

---

## Connected Files

| File | Purpose |
|------|---------|
| `CB_Brain/wiki/MWCC-Knowledge-Base.md` | Persistent DOs/DON'Ts, centre facts, compliance learnings |
| `context/mwcc-brand-context.md` | This file — brand voice and positioning |
| `state/mwcc-ops.json` | Weekly ops data (occupancy, wages, enrolments) |
| `state/mwcc-meta.json` | Meta Ads performance data |
| `state/mwcc-ads.json` | Google Ads performance data |
| `state/mwcc-ga4.json` | Website analytics (when connected) |
| `scripts/bake-mwcc-report.py` | Weekly report baker |
| `scripts/weekly-report-mwcc.sh` | Monday pipeline shell script |

---

*Last updated: 2026-06-05 | Append updates, never overwrite*
