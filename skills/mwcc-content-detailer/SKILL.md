# MWCC Content Detailer Skill

**Purpose:** Take a thin content-calendar action (channel + theme + recipe) and
elaborate it into an execution-ready brief: specific caption, visual direction,
hashtags, posting time, and (for blogs) a draft stub. Mirrors what CB247's
`content-agent` does for the gym's PLANNER_ITEMS.

**Active business:** mwcc
**Triggered by:** running `python scripts/mwcc_content_detailer.py` or by
naming this skill in a `/blog`, `/post`, or `/email draft` request when active
business is mwcc.

---

## Hard rules (NEVER violate)

1. **NO photos of children.** Locked 7 Jun 2026. Visual direction MUST pick
   from one of these 6 approved categories:
   - Educators (with written consent)
   - Centre spaces & rooms (empty or with educators)
   - Materials & children's artwork (no faces, no names)
   - Branded graphics (lavender + purple palette)
   - Parent text quotes on graphics (with consent)
   - Storytelling captions (descriptions, no images of kids)
2. **NO "best" claims.** No "best childcare in Perth". No "only centre that…"
3. **NO scarcity manipulation.** "Limited spots" only if Kelley confirms true capacity.
4. **MENTION CCS wherever fees come up.** "Eligible for CCS" is the standard line.
5. **NO emojis on landing pages or email subject lines.** Limited OK on IG/FB.
6. **Brand voice:** knowledgeable friend, not salesperson. Specific over generic.

---

## Voice attributes

- **Tone:** Warm, specific, practical. Talks TO parents not AT them.
- **Cadence:** Short sentences. Concrete details (room names, days, times).
- **Avoid:** "amazing", "incredible", "perfect", "guaranteed", any superlative.
- **Prefer:** "Last Tuesday at Armadale…", "Our Babies room at Midvale…",
  "Three educators in the Toddlers room this week…"

---

## Per-platform output requirements

### Instagram Feed
- Caption: 80-180 words. Opening hook 8-12 words. Concrete centre detail in
  paragraph 2. Soft CTA at end.
- Visual direction: pick exact approved category + describe the shot.
- Hashtags: 8-12 mix of #perthdaycare + #childcareperth + 1-2 centre-specific
  (#midvalemums, #waikikifamilies) + #earlylearning.
- Best time: Wed/Thu 9-11am OR Sun 6-7pm (based on Metricool peaks).

### Instagram Story (single frame)
- Caption text: 15-30 words.
- Visual: approved category + sticker recommendation (Poll, Question, Countdown,
  Link).
- Best time: Tue/Wed 7:30-9am.

### Facebook Post
- Caption: 100-200 words. Longer than IG (FB audience is older — more context tolerable).
- Visual: same approved categories.
- Hashtags: 3-5 max (FB hashtag etiquette).
- Best time: Tue/Thu 11am-1pm.

### GBP Post (× N centres)
- Headline-style: 15-25 words.
- Body: 50-80 words. Localise per centre (suburb name in first sentence).
- CTA button: Book / Call / Learn more.
- Image: branded graphic OR centre exterior (NOT children).
- Frequency rule: 1 GBP post per centre per week max.

### Email Broadcast
- Subject A: keyword-led ("Vacation Care bookings close Friday")
- Subject B: curiosity-led ("Was this you last holiday?")
- Preheader: 60-80 chars supporting the subject.
- Body: short — 4-paragraph max. CTA button, plain-text fallback.
- Send time: Tue 9:30am OR Thu 6:30am.

### SEO Blog Post
- Target keyword + 2 secondary keywords.
- Word count: 1,200-1,500.
- Outline: H1 → Intro → 4-5 H2 sections → FAQ → CTA.
- Internal links: 3-5 (centre pages, /ccs/ calculator, /book-tour/).
- Output: full markdown draft at `outputs/mwcc/blog-drafts/[slug].md` AND
  HTML stub at `docs/blog-drafts/mwcc/[slug].html`.

---

## Centre quick reference

| Centre | Suburb | Service | Rooms |
|---|---|---|---|
| Armadale | Armadale 6112 | OSHC only | Before School + After School + Vacation Care |
| Midvale | Midvale 6056 | LDC | Babies + Toddlers + Kindy |
| Rockingham | Rockingham 6168 | OSHC only | Before School + After School + Vacation Care |
| Seville Grove | Seville Grove 6112 | LDC | Babies + Toddlers + Kindy |
| Waikiki | Waikiki 6169 | LDC | Babies + Toddlers + Kindy |

LDC = Long Day Care (year-round, ages 0-5). OSHC = Outside School Hours Care.

---

## Hashtag library

**Always-on:** #perthdaycare #childcareperth #earlylearning #perthmums #perthparents

**Service-specific:**
- LDC: #longdaycareperth #kindyperth #babiesperth #toddlersperth
- OSHC: #oshcperth #vacationcareperth #beforeafterschoolcare
- Kindy 2027: #kindy2027perth #waitlistnow

**Centre-specific:**
- Armadale: #armadaleperth #armadalemums
- Midvale: #midvaleperth #midvalemums
- Rockingham: #rockinghamperth #rockinghammums
- Seville Grove: #sevillegroveperth #armadaleregion
- Waikiki: #waikikiperth #waikikifamilies

---

## Detailer execution flow

1. Load `state/mwcc-content-calendar.json` (92 actions from parser)
2. Filter to next N days (default 14)
3. For each action:
   - Read its `recipe` (current `instructions` field)
   - Apply the per-platform rules above
   - Generate enriched `caption`, `visual_direction`, `hashtags`, `best_time`
   - For blogs: write full markdown to `outputs/mwcc/blog-drafts/[slug].md`
   - Update the action's `instructions` field with the enriched brief
4. Write back to `state/mwcc-content-calendar.json`
5. Re-merge into work queue, sync to Supabase
6. Regenerate brief HTMLs

---

## Future enhancement

LLM-driven caption generation via Claude API. Today the executor uses
deterministic templates + brand voice rules. Tia can manually run a Claude
session for any single action to generate richer copy when needed.
