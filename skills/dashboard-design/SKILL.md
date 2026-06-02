# SKILL: Dashboard Design System — ChasingBetter247 Marketing OS

## Trigger
Auto-activate when any task involves:
- `bake-public-dashboard.py`
- `docs/index.html`
- kanban, dashboard, UI, colour, color, design, badge, card, layout, modal
- any HTML file in `docs/` or `outputs/`
- "fix design", "update dashboard", "adjust layout", "add page", "build page"

## Authority
This skill overrides all other colour or layout decisions for dashboard work.
Read `context/design-standards.md` for the full rules. Key rules are restated below for quick reference.

---

## Rule 1 — Three Colours Only

ALLOWED:
- Teal: `#3FA69A` (brand primary)
- Teal tint: `rgba(63,166,154,0.08)` to `rgba(63,166,154,0.15)` for backgrounds
- Teal dark: `#2d8a80` for hover states
- Black: `#0d0d0d`, `#1a1a1a`, `#111`
- White: `#ffffff`
- Gray scale: `#f9fafb`, `#f3f4f6`, `#e6e6e6`, `#888`, `#bbb`

BANNED — never use in any UI element:
- Blues, pinks, yellows, ambers, purples, reds, greens (other than brand teal)
- Examples of banned: `#dbeafe`, `#fce7f3`, `#fef9c3`, `#dcfce7`, `#ede9fe`, `#fee2e2`, `#e0f2fe`

---

## Rule 2 — No Emojis in UI

Never add emojis to:
- Column headers, button text, badge labels, section titles, KPI labels, table headers

Allowed only in: user-generated content copy (captions, blog text)

Before shipping any dashboard change, grep for emoji in the generated section:
```bash
grep -P "[\x{1F300}-\x{1F9FF}]|✅|✔|❌|⚠|⭐|Ὂ1|ὒ7|ὐD|Ὄ5|✅" docs/index.html
```

---

## Rule 3 — Dashboard Layout Must Fit Screen

### Required CSS pattern for sidebar-layout pages:
```css
.main  { height: 100vh; overflow-y: auto; flex-shrink: 0; }
.content { padding: 28px; padding-bottom: 60px; width: 100%; box-sizing: border-box; }
.topbar { position: sticky; top: 0; flex-shrink: 0; z-index: 50; }
```

### Kanban grid — mandatory attributes:
```html
<div style="display:grid;
            grid-template-columns:repeat(5,1fr);
            gap:8px;
            align-items:start;
            margin-bottom:28px">
```
- `align-items:start` is **mandatory** — without it columns stretch and bottom cards clip
- No `overflow-x:auto` on the kanban wrapper — it must fit in the content width

### Card sizing — keeps 5 columns on screen without overflow:
```html
<!-- Column wrapper -->
<div style="background:#f9fafb;border-top:3px solid #3FA69A;border-radius:6px;padding:8px;min-height:100px">

<!-- Individual card -->
<div style="background:#fff;border:1px solid var(--border);border-radius:4px;padding:7px 8px;margin-bottom:6px">
  <!-- platform badge: font-size 8px -->
  <!-- title: font-size 10px -->
  <!-- meta: font-size 9px -->
</div>
```

---

## Rule 4 — Section Titles

Always plain text. No emoji prefix.

```python
# Correct
sectionTitle('Kanban Board')
sectionTitle('2-Week Content Calendar')

# Wrong — will be rejected
sectionTitle('📋 Kanban Board')
```

---

## Rule 5 — Approval & Status Buttons

Use descriptive text:
- "Approved — advance stage" (moves card to next column)
- "Needs Adjustment" (keeps card, shows notes)
- "Rejected — back to Idea" (resets card to Idea column)
- "Move to: [ColumnName] →" (manual cycle)

---

## Quality Checklist

Before committing any dashboard change:

- [ ] No colour hex values outside the allowed palette
- [ ] No emoji characters in UI elements
- [ ] Kanban grid has `align-items:start`
- [ ] `.main` has `height:100vh; overflow-y:auto`
- [ ] `.content` has `padding-bottom:60px`
- [ ] Card padding is `7px 8px` or tighter (not `12px 16px`)
- [ ] Badge font-size is 8–9px
- [ ] `bake-public-dashboard.py` bakes cleanly with no Python errors
- [ ] `docs/index.html` committed and pushed to `main`

---

## Reference
Full design rules: `context/design-standards.md`
Bake script: `scripts/bake-public-dashboard.py`
Output: `docs/index.html` → GitHub Pages: https://cb247agent.github.io/cb_claude/
