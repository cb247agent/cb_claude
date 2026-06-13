# Team Workflow Mapping (CB247)

**Canonical owner table. ALL strategists must reference this when emitting actions.**

Each strategic goal that requires multiple workflow steps MUST be decomposed into ATOMIC actions — one action per step, one owner per action. Do NOT bundle multiple steps under one owner.

---

## Owner ↔ Step Type

| Step Type | Owner | Owner Role Field | Notes |
|---|---|---|---|
| **New photo/video shoot** | Shauna | `Asset Creator` | Only if a NEW asset is needed. Skip if existing assets work. Monthly cadence. |
| **Draft caption / Story script / EDM copy / blog / landing page** | AI (content-writer agent) | — | NOT a human action. Path C auto-drafts. Do NOT emit "Angela drafts X" or "Joanne writes Y" — these are AI tasks. |
| **Graphic design (Story template, ad creative)** | AI (graphic-designer agent — planned) | — | Hidden from team views. Hand-off to Angela for QC. |
| **Quality check (brand voice, compliance, claim audit)** | Angela | `Brand Manager` | Angela QCs the AI draft. She does NOT draft. |
| **Reception briefing / talking points / save-call playbook briefing** | Angela | `Brand Manager` | Angela writes briefs FOR reception, not the post copy itself. |
| **Schedule + post IG/FB/TikTok content** | Joanne | `Organic Social` | Posts pre-approved drafts to Metricool or direct. |
| **Send EDM / SMS campaign** | Joanne | `Organic Social` | Sends after Angela QC. |
| **Schedule + post GBP update** | Tia or Joanne | `OS Owner` / `Organic Social` | Joanne if it's marketing post; Tia if it's hours/structural update. |
| **Paid Meta ad spend / campaign launch** | Joanne | `Meta Ads Specialist` | Owns paid Meta from brief → live. |
| **Paid Google Ads spend / campaign launch** | Tia | `OS Owner / Paid Ads` | Owns paid Google end-to-end. |
| **Webflow CMS edit (H1, meta, FAQ, internal links, blog publish)** | John | `SEO Specialist` or `SEO / Web` | Opens Webflow → pastes AI draft → publishes. |
| **Webflow asset upload (image, PDF)** | John or Mark | `SEO / Web` | John for SEO-pages; Mark for service content if delegated. |
| **GBP location data (hours, photos, posts)** | Tia | `OS Owner` | Owns the GBP listings. |
| **PGM data extract / membership data tracking** | Tia | `OS Owner` | Pulls from Perfect Gym Manager. |
| **Strategic review / verdict / approve-reject** | Denver | `COO (approver)` | Approver only — NEVER assign action ownership to Denver. |

---

## Atomic Action Decomposition Rule

When a strategic goal (e.g. "Scale Recovery add-on") requires multiple workflow steps with different owners, emit each step as its OWN WorkQueueAction. Do NOT bundle them under one owner.

### Example — DO NOT

```
Action: "Scale Recovery add-on"
Owner: "Angela (Brand Manager (copy) + Joanne (Story post))"
Description: "Angela drafts 1 IG Story arc + 1 Reception talking point. Joanne posts the Story Tues + Thurs. Reception team has the talking point printed at desk."
```

Problems: multiple owners crammed into one field; Angela is wrongly assigned to "draft"; team can't see who's blocked or done; no kanban per step.

### Example — DO

Emit FOUR atomic actions, all prefixed with "Recovery push:" so the user sees they're related:

```json
[
  {
    "title": "Recovery push: Shoot Sauna + Ice Bath assets",
    "owner": "Shauna",
    "owner_role": "Asset Creator",
    "description": "Capture 2× photos + 1× short video of Sauna + Ice Bath corner. For use in IG Story arc + Reception talking point card. Skip if Asset Library already has fresh assets (check first).",
    "priority": "P2",
    "effort_hours": 2,
    "dependency": "(none — gates the rest)"
  },
  {
    "title": "Recovery push: QC the AI-drafted IG Story arc + Reception talking point",
    "owner": "Angela",
    "owner_role": "Brand Manager",
    "description": "AI drafts the Story arc (3-card hook) + Reception talking point card via content-writer. Angela reviews for brand voice + compliance (no TGA claims like 'detox' or 'burns fat'; no 'only gym with'). Sign-off triggers Joanne's schedule action.",
    "priority": "P2",
    "effort_hours": 0.5,
    "dependency": "After Shauna asset"
  },
  {
    "title": "Recovery push: Schedule + post IG Story Tues + Thurs (this week + next)",
    "owner": "Joanne",
    "owner_role": "Organic Social",
    "description": "Post the QCd Story to IG Tues 9am + Thurs 6pm, this week + next. Schedule via Metricool. Copy comes from outputs/drafts/social-recovery-push.md.",
    "priority": "P2",
    "effort_hours": 0.5,
    "dependency": "After Angela QC"
  },
  {
    "title": "Recovery push: Print Reception talking point + brief team in Monday huddle",
    "owner": "Angela",
    "owner_role": "Brand Manager",
    "description": "Print A5 Reception talking point card + brief team for 5 min in Monday huddle: 'ask every check-in if they've tried Recovery'. Target: convert curiosity into add-on signups.",
    "priority": "P2",
    "effort_hours": 0.5,
    "dependency": "After Angela QC"
  }
]
```

Result: 4 atomic actions, each with single owner, in respective queues. Visually grouped by "Recovery push:" prefix. Each can be Approved / Adjusted / Rejected independently.

---

## Hidden AI Steps

These step types are handled by AI and should NOT appear as human actions in the Work Queue:

- Draft caption / Story script
- Draft EDM / SMS copy
- Draft blog / landing page / service page
- Draft Reception talking point copy
- Draft FAQ block
- Draft H1 / meta title / meta description
- Graphic design (Story template, ad creative — once `graphic-designer` agent ships)

The strategist's job is to **trigger** these via content-writer (or future agents) and then emit the HUMAN follow-up action (QC + post + publish). Never emit the draft itself as a human task.

---

## Title Prefix Convention

When multiple atomic actions descend from one goal, prefix each with the goal name + colon:

- `Recovery push: ...`
- `Don't Quit Winter: ...`
- `Kids Hub Holiday: ...`
- `FIFO landing page: ...`
- `Save-call training: ...`

This groups them visually in the prioritised list and Work Queue without needing the parent/child Supabase schema yet.

---

Last updated: 2026-06-13. Owner: Tia.
