# Skills Brand Contract

**Version: 1.0 · Effective from 07 Jun 2026**

This is a binding contract that every Layer 2 skill in `skills/*/SKILL.md` MUST follow when reading brand context.

## Why this contract exists

Before this contract, all skills hardcoded `context/brand-voice.md`, `context/marketing-strategy.md`, etc. — these files held **CB247-specific** content. Running a skill for MWCC produced gym-positioned copy with teal accents and "FIFO-friendly" claims.

This contract makes skills **brand-aware** — they read different context files depending on the active business, so the same skill produces correct CB247 OR MWCC content with no per-business duplication.

---

## The contract

Every skill MUST include this "Brand-Aware Context Loading" section near the top of its SKILL.md, BEFORE any `Read:` instructions:

```markdown
## Brand-Aware Context Loading (mandatory — read this first)

1. Read `context/_active_business.txt` — it contains one of: `cb247` · `mwcc` · `kb` · `sp`
2. Based on the active business, use the matching context file paths from this resolution table:

| Generic path (do NOT use directly) | CB247 (default) | MWCC |
|---|---|---|
| `context/brand-voice.md` | `context/brand-voice.md` | `context/mwcc-brand-voice.md` |
| `context/brand-guideline.md` | `context/brand-voice.md` (no separate file) | `context/mwcc-brand-context.md` |
| `context/marketing-strategy.md` | `context/marketing-strategy.md` | `context/mwcc-marketing-strategy.md` |
| `context/seo-targets.md` | `context/seo-targets-cb247.md` | `context/mwcc-seo-targets.md` |
| `context/seo-priorities.md` | `context/seo-priorities-cb247.md` | `context/mwcc-seo-priorities.md` |
| `context/design-standards.md` | `context/design-standards.md` | `context/mwcc-design-standards.md` |
| `context/research-competitors.md` | `context/research-competitors.md` | `context/mwcc-competitors.md` |
| `context/business-config.json` | (CB247 lives in `context/` root files) | `context/mwcc-business-config.json` |
| `context/team-roster.md` | `context/team-roster.md` | `context/mwcc-team-roster.md` |
| `context/session-start.md` | `context/session-start.md` | `context/mwcc-session-start.md` |
| `context/seasonal-calendar.md` | `context/seasonal-calendar.md` | `context/mwcc-seasonal-calendar.md` |
| `context/psychology-triggers.md` | `context/psychology-triggers.md` | `context/mwcc-psychology-triggers.md` |

3. Shared (brand-agnostic) files — always read these regardless of active business:
   - `context/utm-convention.md`
   - `context/strategy-pestle-swot.md` (cross-business strategy doc)
```

---

## Default behaviour

If `context/_active_business.txt` is missing or contains an unknown value, default to `cb247`. This keeps backwards compatibility — every existing skill continues to work for CB247 without any change.

## Switching active business

Tia runs:

```bash
echo "mwcc" > context/_active_business.txt    # switch to MWCC mode
echo "cb247" > context/_active_business.txt   # switch back
```

Or use the helper (recommended):

```bash
python scripts/set_active_business.py mwcc
python scripts/set_active_business.py cb247
```

The helper prints what's active and lists what files the resolution table maps to.

## How a skill SHOULD reference context

**Before (CB247-only — wrong for cross-business):**
```markdown
**Reads:** `context/brand-voice.md`, `context/seo-targets-cb247.md`
```

**After (brand-aware — correct):**
```markdown
**Reads:** (brand-resolved per Brand-Aware Context Loading section above)
- Brand voice file (resolves to either `context/brand-voice.md` or `context/mwcc-brand-voice.md`)
- SEO targets file (resolves to either `context/seo-targets-cb247.md` or `context/mwcc-seo-targets.md`)
```

Or shorter (when the skill is verbose enough already):
```markdown
**Reads:** brand-voice · seo-targets (resolved per Brand-Aware Context Loading)
```

## Identity section also needs updating

Skills that open with "You are a copywriter for CB247" hardcode the persona. After this contract, the persona should read:

```markdown
## Identity

You are a world-class DTC copywriter for the active business (read
`context/_active_business.txt`). Your specific brand identity comes from
the brand-voice file resolved in Brand-Aware Context Loading.

If active = `cb247`: positioning = ChasingBetter247 Health & Fitness Club
                    (Perth gym, $11.95/wk, sauna + ice bath + reformer)
If active = `mwcc`:  positioning = My World Childcare (Perth childcare,
                    5 centres, CCS-approved, OSHC + LDC + vacation care)
```

## Backwards compatibility

- All existing skills continue to work without modification — they default to CB247 context, same as today.
- Refactoring a skill to be brand-aware requires adding the "Brand-Aware Context Loading" boilerplate + replacing hardcoded paths with the generic names from the resolution table.
- Skills can be refactored individually — no global migration required.

## Migration order (recommended)

When refactoring skills, prioritise the ones most likely to be run for MWCC:

1. `seo-landing-page-writer/SKILL.md` — landing pages for each centre
2. `seo-blog-generator/SKILL.md` — childcare blogs
3. `content-writer/SKILL.md` — generic content
4. `social-content-calendar/SKILL.md` — IG / FB / GBP calendars
5. `email-funnel-builder/SKILL.md` — enrolment follow-up
6. `seo-content-strategist/SKILL.md` — keyword strategy
7. `paid-ads-creative-pipeline/SKILL.md` — Meta ad copy
8. `creative-brief-engine/SKILL.md` — Jordan's briefs
9. `meta-ads-optimizer/SKILL.md` — ad set optimisation
10. `local-seo-optimizer/SKILL.md` — per-centre GBP

The other 28 skills can be refactored later when they're first needed for MWCC.

## Why not refactor all 38 at once?

Risk minimisation. Each refactor needs:
- Read existing SKILL.md
- Identify all CB247-specific references
- Replace hardcoded paths with brand-aware ones
- Update Identity section
- Test on a real MWCC task to verify output is correct

Doing all 38 in one batch introduces high risk of subtle persona drift errors. Doing them as-needed lets us validate each one before relying on it.
