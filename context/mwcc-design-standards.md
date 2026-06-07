# Design Standards — My World Childcare Marketing OS

> **SYSTEM FILE — do not edit unless explicitly instructed.**
> These rules apply to ALL MWCC dashboard pages, HTML outputs, kanban boards, reports, ad creative, landing pages, GBP posts, email broadcasts — anything that renders in `docs/` (MWCC pages) or `outputs/mwcc/` or paid creative deliverables.

---

## Core Rule: Three Colour Groups Only

The MWCC visual system uses exactly three colour groups. No others.

| Token | Hex | Usage |
|---|---|---|
| **PURPLE / LAVENDER (brand primary)** | | |
| `--mwcc-purple` | `#8B6FD9` | Brand primary — active states, primary CTA buttons, accent borders |
| `--mwcc-deep` | `#4A2F8A` | Headings, dark UI text, button hover, deep accents |
| `--mwcc-soft` | `#C5B6F0` | Soft borders, secondary UI, divider lines |
| `--mwcc-pale` | `#EDE7FA` | Pale background tints, highlight blocks (max 0.5 opacity equivalent) |
| `--mwcc-mist` | `#F5F1FC` | Subtle background washes, alternating table rows |
| **BLACK / NEAR-BLACK** | | |
| Body text | `#1a1a1a` | Default body copy |
| Strong text | `#0d0d0d` | Headers, KPI numbers |
| Dark badges | `#1a1a1a` | Risk badges, compliance flags |
| **GRAY SCALE** | | |
| `--mwcc-gray-0` | `#f9fafb` | Card surfaces, alternate rows |
| `--mwcc-gray-1` | `#f3f4f6` | Borders, dividers, muted backgrounds |
| `--mwcc-gray-2` | `#e6e6e6` | Light borders, separator lines |
| `--mwcc-gray-3` | `#888` | Muted text, helper copy |
| `--mwcc-gray-4` | `#bbb` | Disabled state text |

### Accent colours — use sparingly + only for these purposes

| Accent | Hex | Single allowed use |
|---|---|---|
| `--mwcc-risk` | `#ef4444` | Compliance risk badge ONLY. Never decorative. |
| `--mwcc-warn` | `#f59e0b` | Wage-breach amber alert ONLY. Never decorative. |

### Banned colours — never use in any MWCC component

- **Teal / green** (`#3FA69A`, `#00c4b4`, `#16a34a`, etc.) — that's CB247 / other brands
- **Blue** (any blue token — `#dbeafe`, `#1e40af`, `#0ea5e9`, etc.)
- **Pink / rose / fuchsia** (any)
- **Yellow / bright amber** (use `--mwcc-warn` only when justified)
- **Bright red** (use `--mwcc-risk` only when justified)
- **Brown / earth tones**

---

## Typography

### Web + dashboard
- **Headings:** `Poppins`, fallback `'Helvetica Neue', sans-serif`. Weight: 600 (semibold) or 700 (bold). Letter spacing: `0` for body, `-0.01em` for big H1.
- **Body:** `Poppins`, fallback `'Helvetica Neue', sans-serif`. Weight: 400 or 500. Line-height: 1.6 for paragraphs, 1.4 for UI text.
- **Numbers / KPIs:** `Poppins` weight 700, tabular figures preferred. `font-variant-numeric: tabular-nums;`

### Email + marketing print
- **Headers:** `Poppins` if available; safe fallback to `'Helvetica Neue', Arial, sans-serif`
- **Body:** Same fallback chain. Don't use display fonts in email — they degrade poorly across clients.

### Sizes — UI baseline

| Element | Size | Weight |
|---|---|---|
| H1 (page title) | 32px desktop / 24px mobile | 700 |
| H2 (section) | 22px desktop / 18px mobile | 600 |
| H3 (sub-section) | 18px desktop / 16px mobile | 600 |
| Body | 15px | 400 |
| UI label | 13px | 500 |
| Badge / chip | 9px ALL CAPS, letter-spacing 0.3px | 700 |

---

## No Emojis in UI

Never use emojis in:
- Column headers, labels, section titles
- Button text, KPI card labels, badge text
- Table headers or cell values
- Status indicators or alerts

**Exception:** emojis are allowed only in user-generated **content copy** for IG / FB organic captions — never in structural UI, never in email subject lines, never on landing pages, never on GBP posts.

---

## Dashboard Layout — Fit to Screen

### Sidebar + main scroll pattern
```css
.main { height: 100vh; overflow-y: auto; }
.content { padding: 28px; padding-bottom: 60px; }
.topbar { flex-shrink: 0; position: sticky; top: 0; background: #fff; }
```

### Per-centre comparison grids
For multi-centre KPI displays (used on Overview, Occupancy, Enrolments pages):
- Always `display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; align-items: start;`
- `align-items: start` is mandatory — prevents columns stretching
- Per-centre card padding: `12px 14px`
- No `overflow-x: auto` wrapper on the grid itself
- Each centre card has a 3px purple left border indicating the centre badge

### Work Queue kanban
- Same 5-column grid pattern (Idea · In Progress · Kelley QC · Denver Approval · Scheduled)
- Column top-border: `2px solid var(--mwcc-purple)` for active columns, `2px solid var(--mwcc-gray-2)` for Idea
- Background: `var(--mwcc-gray-0)`
- Card padding: `8px 10px`

---

## Badge & Chip Rules

### Centre badges (shown on per-centre cards + Work Queue items)

| Centre | Background | Border-left | Text |
|---|---|---|---|
| Armadale | `var(--mwcc-pale)` | `3px solid var(--mwcc-purple)` | `var(--mwcc-deep)` |
| Midvale | `var(--mwcc-pale)` | `3px solid var(--mwcc-purple)` | `var(--mwcc-deep)` |
| Rockingham | `var(--mwcc-pale)` | `3px solid var(--mwcc-purple)` | `var(--mwcc-deep)` |
| Seville Grove | `var(--mwcc-pale)` | `3px solid var(--mwcc-purple)` | `var(--mwcc-deep)` |
| Waikiki | `var(--mwcc-pale)` | `3px solid var(--mwcc-purple)` | `var(--mwcc-deep)` |

(Centre differentiation is by name + suburb text, not by colour. Consistent visual hierarchy.)

### Service-type badges

| Service | Background | Text |
|---|---|---|
| LDC | `var(--mwcc-pale)` | `var(--mwcc-deep)` |
| OSHC | `var(--mwcc-mist)` | `var(--mwcc-purple)` |
| Vacation Care | `var(--mwcc-soft)` | `var(--mwcc-deep)` |

Font: 9px ALL CAPS, letter-spacing 0.3px, weight 700. No emoji prefix.

### Assignee badges (Work Queue)

| Person | Background | Text |
|---|---|---|
| Tia | `var(--mwcc-purple)` | `#fff` (filled purple) |
| Denver | `#1a1a1a` | `#fff` (dark — approval role) |
| Kelley | `#1a1a1a` | `#fff` (dark — QC role) |
| Joanne | `var(--mwcc-pale)` | `var(--mwcc-deep)` |
| Jordan | `var(--mwcc-pale)` | `var(--mwcc-deep)` |
| John | `var(--mwcc-pale)` | `var(--mwcc-deep)` |
| Mark | `var(--mwcc-pale)` | `var(--mwcc-deep)` |
| AI | `var(--mwcc-mist)` | `var(--mwcc-purple)` |

### Status colours

| Status | Text colour |
|---|---|
| Published / Scheduled / In Progress / Approved | `var(--mwcc-purple)` |
| Kelley QC / Denver Approval | `#1a1a1a` (dark) |
| Idea / default | `var(--mwcc-gray-3)` |

### Risk badges (compliance + occupancy)

| Risk | Background | Text | Notes |
|---|---|---|---|
| Compliance risk (room > capacity) | `var(--mwcc-risk)` `0.15` opacity | `var(--mwcc-risk)` solid | Always pair with text label "Risk" — never icon-only |
| Wage breach (wage > 42%) | `var(--mwcc-warn)` `0.15` opacity | `var(--mwcc-warn)` solid | Always pair with text label "Wage" — never icon-only |

---

## Section Title Rule

Section titles must be plain text — no emoji, no icon prefix.

```python
# Correct
sectionTitle('Network Occupancy')
sectionTitle('Per-Centre Enrolments')
sectionTitle('Next 2 Weeks — Prioritised Action List')

# Wrong
sectionTitle('🏠 Network Occupancy')
sectionTitle('📊 Per-Centre Enrolments')
```

---

## KPI Cards

- No icon argument — pass `''` as first arg to `kpiCard()`
- Color class: only `'purple'` (brand), `'amber'` (wage warning), `'risk'` (compliance), or `''` (neutral)
- Sub-text: plain English, no emoji, max 60 chars
- KPI number format:
  - Counts: integer with commas (`1,247`)
  - Percentages: 1 decimal (`72.4%`)
  - Currency: `$` prefix, no decimals for amounts > $100 (`$1,250`)
  - Ratios: 1 decimal (`1:4`)

---

## HTML Report Outputs (`outputs/mwcc/*.md` → `*-final.md`)

The `report-formatter` skill applies the MWCC palette when active business = mwcc. When generating MWCC HTML reports:

- Page background: `#ffffff` or `var(--mwcc-mist)`
- Headings: `var(--mwcc-deep)` (`#4A2F8A`) for H1, `var(--mwcc-purple)` (`#8B6FD9`) for H2
- Accent borders: `var(--mwcc-purple)` only
- Tables: white rows, `var(--mwcc-mist)` alternating, `var(--mwcc-deep)` header background with white text
- Alert / highlight boxes: `var(--mwcc-pale)` background, `var(--mwcc-purple)` left border `4px`
- Print-safe: no purple backgrounds wider than 50% of page width (ink coverage)

---

## Email Broadcasts

- Header: white background, MWCC logo top-left, `var(--mwcc-purple)` accent bar 4px tall under header
- Body: `#ffffff` background, `#1a1a1a` text
- CTA buttons: `var(--mwcc-purple)` background, white text, 14px font, padding 14px 28px, border-radius 8px
- Secondary CTA buttons (rare): `var(--mwcc-mist)` background, `var(--mwcc-deep)` text, same dimensions
- Footer: `var(--mwcc-mist)` background, `var(--mwcc-deep)` 13px text, unsubscribe link + physical address
- Max email width: 600px (universal email standard)
- Hero images: 600x300 max, alt text required, file size <100KB
- **NEVER include children in hero or body imagery** (per locked policy 2026-06-07)

---

## Landing Pages (per-centre + service pages on myworldcc.com.au)

- Hero block: 60% white space, 40% content. H1 in `var(--mwcc-deep)`. Sub-headline in `#1a1a1a`. Single CTA button in `var(--mwcc-purple)`.
- Hero image: centre exterior / interior space (no children visible) OR educator-led tour preview shot (with consent)
- Body: max-width 720px for prose blocks
- CTA repetition: at least 3 CTAs on every landing page (top, mid, bottom). Same button style.
- Trust strip: educator qualifications + ACECQA approval + CCS approved + per-centre suburb
- Per-centre pages: include the 3px purple left-border centre card pattern from §badges
- CSS variables MUST be the MWCC palette tokens (no Webflow defaults)

---

## Paid Ad Creative — Meta + Google Display

### Meta image / video ads
- 1:1 ratio: 1080x1080 (feed). 9:16 ratio: 1080x1920 (stories/reels)
- Brand text overlay: `var(--mwcc-deep)` on white card, or white on `var(--mwcc-purple)` card. Never gradient.
- Single CTA on overlay. Match landing page CTA exactly.
- Logo: bottom-right OR top-left, never centred
- Body image: same rules as landing page (centre spaces, educators with consent, materials, branded graphics) — NEVER children
- Carousels: 5 slides max. Slide 1 = title card (brand colour). Slides 2-5 = content. Final slide = CTA.

### Google Display banners
- Standard sizes: 300x250, 728x90, 160x600
- Always include MWCC logo + single CTA + brand-tied headline
- Background: white preferred. `var(--mwcc-mist)` acceptable.
- CTA button: `var(--mwcc-purple)` on white, OR white on `var(--mwcc-deep)`

---

## GBP Posts (5 centres × 1/week minimum)

- Image dimensions: 1200x900 (4:3) or 1080x1080 (square)
- Visual: centre space, educator (with consent), materials, or branded graphic
- Copy: 90-120 words. Suburb must appear in body. Single CTA button (Book / Call / Learn more).
- No children in imagery. Ever.
- Avoid hashtags — Google doesn't render them on GBP posts.

---

## Brand Voice + Visual Consistency Check

Before any MWCC visual asset goes out, verify against this checklist:

- [ ] No teal, no green, no blue, no pink — palette is purple + black + gray only
- [ ] No emojis in UI / structural elements (captions excepted on IG/FB)
- [ ] No children visible in any image, illustration, or video
- [ ] Educator imagery has written consent on file
- [ ] CTA matches brand-voice CTA hierarchy (Book a tour > Join waitlist > Get quote > Call > Download)
- [ ] Suburb / centre name appears wherever location is relevant
- [ ] Font is Poppins (or safe fallback) — not Webflow default
- [ ] No claims requiring NQS rating verification (those need `state/mwcc-nqs-ratings.json` clearance)
- [ ] Australian spelling (centre / programme / colour)

---

## Python Bake Script Conventions (`bake-mwcc-report.py`)

When editing the MWCC bake script, use these palette constants:

```python
MWCC_COLOURS = {
    "purple":      "#8B6FD9",
    "deep_purple": "#4A2F8A",
    "soft_purple": "#C5B6F0",
    "pale_purple": "#EDE7FA",
    "mist":        "#F5F1FC",
    "risk":        "#ef4444",
    "warn":        "#f59e0b",
    "text":        "#1a1a1a",
    "text_strong": "#0d0d0d",
    "white":       "#ffffff",
    "gray_0":      "#f9fafb",
    "gray_1":      "#f3f4f6",
    "gray_2":      "#e6e6e6",
    "gray_3":      "#888888",
}

# Role colours dict
role_colors = {
    "Tia":     ("#8B6FD9", "#ffffff"),
    "Denver":  ("#1a1a1a", "#ffffff"),
    "Kelley":  ("#1a1a1a", "#ffffff"),
    "Joanne":  ("#EDE7FA", "#4A2F8A"),
    "Jordan":  ("#EDE7FA", "#4A2F8A"),
    "John":    ("#EDE7FA", "#4A2F8A"),
    "Mark":    ("#EDE7FA", "#4A2F8A"),
    "AI":      ("#F5F1FC", "#8B6FD9"),
}

# Channel colours dict
channel_colors = {
    "gbp":       ("#F5F1FC", "#8B6FD9"),
    "instagram": ("#EDE7FA", "#4A2F8A"),
    "facebook":  ("#F5F1FC", "#8B6FD9"),
    "blog":      ("#f3f4f6", "#1a1a1a"),
    "email":     ("#f3f4f6", "#1a1a1a"),
    "meta":      ("#EDE7FA", "#4A2F8A"),
    "google":    ("#F5F1FC", "#8B6FD9"),
}
```

---

*Last updated: 2026-06-07 · Append updates with date · Never strip or change locked rules without Tia approval*
