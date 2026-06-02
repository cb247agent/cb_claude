# Design Standards — ChasingBetter247 Marketing OS

> **SYSTEM FILE — do not edit unless explicitly instructed.**
> These rules apply to ALL dashboard pages, HTML outputs, kanban boards, reports, and any UI rendered in `docs/` or `outputs/`.

---

## Core Rule: Three Colours Only

The Marketing OS uses exactly three colour groups. No others.

| Token | Value | Usage |
|-------|-------|-------|
| `--teal` | `#3FA69A` | Brand primary — active states, borders, badges, teal-tinted backgrounds |
| `--teal-dim` | `#2d8a80` | Hover / darker teal |
| `--teal-mist` | `rgba(63,166,154,0.08)` | Light teal background tints (max 0.15 opacity) |
| Black | `#0d0d0d` / `#1a1a1a` / `#111` | Text, dark badges, TikTok chip |
| White | `#ffffff` | Card backgrounds, modal backgrounds |
| Gray scale | `#f9fafb` `#f3f4f6` `#e6e6e6` `#888` `#bbb` | Surfaces, borders, muted text |

### Banned colours — never use in any UI component:

- Any blue (`#dbeafe`, `#1e40af`, `#0ea5e9`, `#0369a1`, etc.)
- Any pink / rose / fuchsia (`#fce7f3`, `#9d174d`, `#ec4899`, etc.)
- Any yellow / amber (`#fef9c3`, `#854d0e`, `#d97706`, `#f59e0b`, etc.)
- Any green other than teal (`#dcfce7`, `#16a34a`, `#166534`, etc.)
- Any purple / violet (`#ede9fe`, `#7c3aed`, `#5b21b6`, etc.)
- Any red (`#fee2e2`, `#ef4444`, `#dc2626`, `#991b1b`, etc.)

---

## No Emojis in UI

Never use emojis in:
- Column headers or labels
- Badge text
- Button text
- Section titles (`sectionTitle()` calls)
- KPI card labels or sub-labels
- Table headers or cell values
- Status indicators
- Insight / alert labels

Exception: emoji are allowed only in user-generated **content copy** (captions, blog drafts) — never in structural UI elements.

---

## Dashboard Layout — Fit to Screen

### Sidebar + main scroll pattern
```css
.main { height: 100vh; overflow-y: auto; }         /* main scrolls, sidebar stays fixed */
.content { padding: 28px; padding-bottom: 60px; }  /* 60px bottom pad so last item is never clipped */
.topbar { flex-shrink: 0; position: sticky; top: 0; }
```

### Kanban board
- Always `display:grid; grid-template-columns:repeat(5,1fr); align-items:start`
- `align-items:start` is mandatory — prevents columns stretching and clipping
- Gap: `8px` between columns
- No `overflow-x:auto` wrapper on the kanban grid itself
- Card padding: `7px 8px` max — keeps cards compact enough for 5 columns on screen

### Column colours (kanban)
```
All columns:  background #f9fafb, border-top teal (#3FA69A) for active stages
Idea column:  border-top #d1d5db (gray — not yet started)
Published:    background rgba(63,166,154,0.06), border-top #3FA69A
```

---

## Badge & Chip Rules

### Platform badges
- Background: `rgba(63,166,154,0.12)` teal tint OR `#f3f4f6` gray
- Text: `#3FA69A` for teal-background; `#111` for gray-background
- TikTok exception: `background:#1a1a1a; color:#fff` (dark chip only)
- Font size: 8–9px, `font-weight:700`, `letter-spacing:.3px`, ALL CAPS
- No emoji prefix

### Assignee badges
- Tia: `background:#3FA69A; color:#fff` (teal filled)
- AI: `background:rgba(63,166,154,0.15); color:#2d8a80` (teal tint)
- Angela: `background:#1a1a1a; color:#fff` (dark — QC role)
- All others: `background:#f3f4f6; color:#444` (gray neutral)

### Status colours
- Published / Scheduled / In Progress / Approved: `#3FA69A` teal text
- Angela QC: `#111` black text
- Idea / default: `#999` gray text

---

## Section Title Rule

`sectionTitle()` text must be plain text — no emoji, no icon prefix.

```python
# Correct
sectionTitle('Kanban Board')
sectionTitle('2-Week Content Calendar')
sectionTitle('All Content Items — 12 items this cycle')

# Wrong
sectionTitle('📋 Kanban Board')
sectionTitle('💡 Ideas')
```

---

## Approval / Status Flow Labels

Button text must be descriptive, no emoji:
- "Approved — advance stage"
- "Needs Adjustment"
- "Rejected — back to Idea"
- "Move to: [Stage] →"

---

## KPI Cards

- No icon argument — pass `''` as first arg to `kpiCard()`
- Color class: only `'green'` (teal), `'amber'` (maps to teal in practice), or `''` (neutral)
- Sub-text: plain English, no emoji

---

## HTML Report Outputs (`outputs/*.md` → `*-final.md`)

The `report-formatter` skill applies the same palette. When generating HTML reports:
- Headings: black (`#0d0d0d`) or teal (`#3FA69A`)
- Accent borders: teal only
- Tables: white rows, `#f9fafb` alternating, teal header
- Alert / highlight boxes: `rgba(63,166,154,0.08)` background, teal left border

---

## Python Bake Script Conventions (`bake-public-dashboard.py`)

When editing the bake script, follow these colour token rules:

```python
# Role colours dict — only these values allowed
role_colors = {
    "SEO Specialist":       "#f3f4f6",   # gray
    "Video Creator":        "#f3f4f6",
    "Social Media Manager": "#f3f4f6",
    "Assets Creator":       "#f3f4f6",
    "Web Developer":        "#f3f4f6",
    "Content Agent":        "rgba(63,166,154,0.12)",  # teal tint
    "Brand Manager":        "#1a1a1a",   # dark (QC)
    "QC Manager":           "#1a1a1a",
    "Marketing Manager":    "#f3f4f6",
}

# Platform colours dict
platform_colors = {
    "gbp":       ("#e8f5f4", "#3FA69A"),   # teal tint
    "instagram": ("rgba(63,166,154,0.12)", "#3FA69A"),
    "tiktok":    ("#1a1a1a", "#ffffff"),   # dark
    "blog":      ("#f3f4f6", "#111111"),   # gray
    "email":     ("#f3f4f6", "#111111"),
    "meta":      ("#f3f4f6", "#111111"),
}
```
