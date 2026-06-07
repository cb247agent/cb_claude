# MWCC Team Roster + Work Queue Ownership

**Locked 07 Jun 2026 per Tia direction. Source of truth for MWCC emitter
owner assignment. Mirrors `context/team-roster.md` pattern used for CB247.**

## Team Members

| Name | Role | Notes |
|---|---|---|
| **Tia** | OS Owner | Shared with CB247. Strategic + paid Google Ads decisions. |
| **Denver** | COO | Shared with CB247. Final sign-off on every action. Strategic wage/budget decisions for MWCC. |
| **Kelley** | Manager / Frontline Ops | MWCC-only. Brand QC + frontline operations across 5 centres. Equivalent of Angela's role in CB247. |
| **Joanne** | Paid Social + Scheduling | Shared with CB247. Offshore staff (Philippines). Runs Meta + TikTok paid execution for both businesses. |
| **John** | SEO / Web Specialist | Shared with CB247. SEO actions execution. |
| **Mark** | Web Developer (Webflow) | Shared with CB247. Page builds + publishes. |
| **Jordan** | Content / Assets Creator | MWCC-only. Equivalent of Shauna's role at CB247. Content production + creative refresh + Meta creative. |

**Approval flow:** AI / team drafts → Tia reviews → In Progress → **Kelley QC** (brand) → Denver sign-off → Scheduled → Mark publishes (Webflow) / Tia posts (GBP) / Joanne posts (Meta + TikTok)

---

## MWCC Work Queue Owner Map

### Google Ads emitter (`mwcc_google_ads_emitter.py`)

| Archetype | Owner | Why |
|---|---|---|
| PAUSE | Tia | Paid Google Ads strategy = OS Owner |
| SCALE | Tia | Same |
| OPTIMISE | John | Keyword + landing page tuning lives in SEO scope |

### Meta Ads emitter (`mwcc_meta_emitter.py`)

| Archetype | Owner | Why |
|---|---|---|
| PAUSE | Joanne | Runs Meta + TikTok paid for both businesses |
| SCALE | Joanne | Same |
| REFRESH | Jordan | Creative production for MWCC |

### SEO emitter (`mwcc_seo_emitter.py`)

| Archetype | Owner | Why |
|---|---|---|
| OPTIMISE | John | On-page tuning is his daily work |
| BUILD | AI (drafts) + Jordan (content) + Mark (publishes) | AI drafts page → Kelley QC → Denver signs → Mark publishes |
| PROTECT | John | Internal linking + content refresh |

### Enrolment emitter (`mwcc_enrolment_emitter.py`) — MWCC-specific

| Archetype | Owner | Why |
|---|---|---|
| ENROLMENT_GAP | Kelley | Frontline ops drives enrolment recovery |
| OCCUPANCY_FILL | Kelley | Frontline ops fills underutilised rooms |
| WAGE_RATIO_ALERT | Denver (strategic) + Kelley (execution) | Strategic call on wage % targets, frontline executes corrections |

---

## Important — these are EMITTER defaults, not locks

Same rule as CB247: Tia + team can reassign any individual action in the
dashboard. The emitter owners are just the sensible Monday-morning default.

If a default looks wrong consistently for a particular archetype, edit the
relevant emitter (`owner="..."` lines) and this roster, then commit.
