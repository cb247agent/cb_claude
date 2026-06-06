# CB247 Team Roster + Work Queue Ownership

**Locked 06 Jun 2026 per Tia direction. Source of truth for emitter owner assignment.**

This document maps each team member to the specific Work Queue archetypes they
own. The emitters (`scripts/work_queue/*_emitter.py`) hard-code these owners so
that every action lands in the right person's column on Monday morning.

---

## Team Members

| Name | Role | Decision authority |
|---|---|---|
| **Tia** | OS Owner | Strategic decisions, paid ads strategy, budget approvals, competitive defence |
| **Denver** | COO | Final sign-off on all approved actions (DECISION MAKER) |
| **Angela** | Manager CB247 Gym | Brand QC + frontline operations (save calls, review cadence, member habit) |
| **Joanne** | Lead / Coord | Meta + TikTok paid ads, creative team coordination |
| **John** | SEO / Web Specialist | SEO actions execution |
| **Mark** | Web Developer (Webflow) | Page builds + publishes |
| **Shauna** | Asset Creator | Content production + GBP photos + ad creative |
| **Shaun Malabanan** | Graphic Design | Static creative for ads + social |
| **Jane Real** | Graphic Design | Static creative for ads + social |
| **Ivan Arevalo** | Video | Video production |
| **Agust Macababayao** | Video | Video production |

**Approval flow:** AI / team drafts → Tia reviews → In Progress → Angela QC (brand) → Denver sign-off → Scheduled → Mark publishes (Webflow) / Tia posts (GBP) / Joanne posts (Meta + TikTok)

---

## Work Queue Owner Map

### SEO emitter (`seo_emitter.py`)

| Archetype | Owner | Why |
|---|---|---|
| OPTIMISE | John | On-page tuning is his daily work |
| BUILD | AI (drafts) + Mark (publishes) | AI drafts page, Angela QC, Denver signs, Mark publishes to Webflow |
| PROTECT | John | Internal linking + content refresh |

### Meta Ads emitter (`meta_emitter.py`)

| Archetype | Owner | Why |
|---|---|---|
| PAUSE | **Joanne** | Joanne runs Meta + TikTok paid (changed from Tia 06 Jun) |
| SCALE | **Joanne** | Same as above |
| REFRESH | Shauna | Creative production is her job |

### Google Ads emitter (`google_ads_emitter.py`)

| Archetype | Owner | Why |
|---|---|---|
| PAUSE | Tia | Tia owns Google Ads end-to-end |
| SCALE | Tia | Same |
| OPTIMISE | John | Keyword + landing page tuning lives in SEO scope |

### GBP emitter (`gbp_emitter.py`)

| Archetype | Owner | Why |
|---|---|---|
| REVIEW_GROWTH | **Angela** | Frontline cadence = manager + reception (changed from Tia 06 Jun) |
| PHOTO_REFRESH | Shauna | Photo capture + upload |
| COMPETITOR_GAP | Tia (strategic) + Angela (execution) | Tia owns counter-positioning, Angela's team executes |

### Organic Social emitter (`social_emitter.py`)

| Archetype | Owner | Why |
|---|---|---|
| TREND_RIDE | Shauna | Creative production |
| CREATIVE_INSPO | Shauna | Format adaptation |

### Membership emitter (`membership_emitter.py`)

| Archetype | Owner | Why |
|---|---|---|
| SAVE_CALL | **Angela + reception team** | Save calls = manager + reception (changed from Joanne 06 Jun) |
| CHURN_REASON (habit-build) | **Angela + reception team** | Member habit campaigns = manager + reception (changed from Joanne 06 Jun) |
| SWITCH_DEFENCE | Tia | Strategic competitive defence |
| ADDON_UPSELL | Tia | Strategic positioning + bundle design |

---

## Member Habit Campaign — what it actually is

The CHURN_REASON archetype emits an action like "Habit-build campaign — 49 'not using
enough' churns this week" because that many members cancelled this week citing they
weren't using the membership enough.

A **habit-build campaign** = a sequence of touchpoints that activate new members
BEFORE they fall into the "I'm paying but not using" trap. Concretely:

- **Day 14 after signup** — Reception sends an SMS: *"Hey [name], how's the first two
  weeks been? Want help booking your first class? Reply CLASS and we'll find you a
  time that fits."*
- **Day 30 after signup, ONLY for members with <2 visits** — Front desk flags them
  on next entry: *"Hey, let's get you a 15-min PT intro session — free, just helps
  you find your routine."*
- **Day 45 after signup** — Members who hit a routine get a Recovery (Sauna + Ice
  Bath) trial day to upsell into addon.

Owned by Angela + reception (they see members face-to-face daily and can flag
behaviour patterns). The CHURN_REASON action IS the campaign — build the SMS/in-gym
touchpoint sequence, set up triggers in the CRM, run for a cycle, measure if
cancellations drop.

---

## Important — these are EMITTER defaults, not locks

When the Monday meeting runs, Tia + team can reassign any individual action to
a different person via the dashboard card edit. The emitter owners are just the
sensible Monday-morning default.

If a default looks wrong consistently for a particular archetype, edit the
relevant emitter (`owner="..."` lines) and this roster, then commit.
