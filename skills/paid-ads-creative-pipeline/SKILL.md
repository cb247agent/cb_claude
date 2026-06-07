# SKILL: Paid Ads Creative Pipeline

## Brand-Aware Context Loading (mandatory — read first)

This skill follows the Brand Contract (`skills/SKILLS_BRAND_CONTRACT.md`). Before reading any context file:

1. Read `context/_active_business.txt` — contains the active brand code (`cb247` · `mwcc` · default `cb247`)
2. Use the resolution table in `SKILLS_BRAND_CONTRACT.md` to map generic context names (e.g., `brand-voice`, `research-competitors`) to brand-specific files
3. References below use generic names — resolve them via the contract

## Trigger Keywords
paid ads pipeline, full ad campaign, ad creative pipeline, meta + google ads pipeline, ad production pipeline, build ad campaign, produce ad copy, generate ad creatives, multi-platform ads pipeline

---

## Identity
You are the paid ads production orchestrator for the active business (read `context/_active_business.txt`):
- If `cb247`: CB247 — gym membership acquisition, FIFO + family + recovery + 24/7 angles
- If `mwcc`: MWCC — childcare enrolment + Vacation Care + tour booking, 5 centres, CCS angle

You take a campaign brief or core offer and run it through the complete ad creation pipeline: competitor ad analysis → audience selection → Meta ad copy → Google ad copy → creative briefs → UTM construction → final output.

---

## READ FIRST
Resolve and read these files via the Brand Contract before generating:

1. `brand-voice` — voice rules, CTA hierarchy, language do's/don'ts
2. `marketing-strategy` — ICPs, primary/secondary targets
3. `research-competitors` — battle cards, competitor positioning
4. `psychology-triggers` — required triggers per ad variant
5. `context/utm-convention.md` — UTM parameter definitions and naming conventions (shared, brand-agnostic)
6. `skills/ads-manager/SKILL.md` — ad account structure, audiences, budgets
7. `outputs/blueprints/[latest-brief].md` — campaign-specific brief and offer (if available)

---

## Business-Specific Pipeline Constraints

### When active = `cb247`
- **Ad accounts:** Meta `act_2835637326727066` (shared), Google Ads `917-218-6113` (shared via manager `569-719-3495`)
- **Required price anchor:** `$11.95/week` + `no lock-in` in every Meta variant
- **Locations:** Malaga / Ellenbrook / Perth-wide
- **CTA hierarchy:** "Start free trial" > "Book a tour" > "Sign Up" > "Learn More"
- **Compliance:** doctor disclaimer if exercise content, no TGA-prohibited language
- **Add-ons (NEVER as included):** sauna+ice bath, Kids Hub, Reformer Pilates, ChasingRX, yoga, spin

### When active = `mwcc`
- **Ad accounts:** Meta `act_2835637326727066` (shared), Google Ads `917-218-6113` (shared)
- **Required disclaimers:** CCS "subject to eligibility" when fees mentioned
- **Locations:** Armadale / Midvale / Rockingham / Seville Grove / Waikiki — match centre service type (OSHC vs LDC vs both)
- **CTA hierarchy:** "Book a tour" > "Join the waitlist" > "Get a quote" > "Call us" > "Download info pack"
- **Compliance:** auto-blocked at sync gate — no "best childcare", "premier", "guaranteed", "award-winning", unverified NQS claims
- **Imagery rule:** ad creative briefs (Stage 5) MUST specify educators / spaces / materials / branded graphics — NEVER children

---

## Pipeline Stages (Run in Order)

### STAGE 1 — Competitor Ad Intelligence
**Skill:** `competitor-ads-scraper`
**Reads:** research-competitors (resolved), marketing-strategy (resolved)
**Output:** `outputs/research/competitor-ads-analysis-[YYYY-MM-DD].md`

Run the competitor-ads-scraper skill. Analyze what Revo, Anytime, Snap, and Ryderwear are currently running in Meta and Google Ads. Extract: offers, pricing claims, creative angles, targeting hints, CTA styles. Document how CB247's offer is differentiated.

**This stage answers:** What are competitors saying right now? What offers are they running?

---

### STAGE 2 — Audience Persona Selection
**Skill:** `audience-segmentation`
**Reads:** psychology-triggers (resolved), marketing-strategy (resolved), outputs from Stage 1
**Output:** Persona selection within the ad copy output (Stages 3 + 4)

Run the audience-segmentation skill to confirm the ICP. For each ad set, note: persona name, age range, location radius, key pain point, primary message, psychological trigger to use. This feeds directly into Stages 3 and 4.

**This stage answers:** Who are we targeting and what do they need to hear?

---

### STAGE 3 — Meta Ads (Facebook + Instagram)
**Skill:** `meta-ads-optimizer`
**Reads:** brand-voice (resolved), `context/utm-convention.md`, `skills/ads-manager/SKILL.md`, outputs from Stages 1+2, campaign brief
**Output:** `outputs/creatives/[campaign]/paid-ads/meta-ads-complete.md`

Run the meta-ads-optimizer skill. Produce ad copy for all 4 ad sets:
- Ad Set 1: Cold Local (3 variants — price anchor / emotion / social proof)
- Ad Set 2: Cold FIFO (3 variants — pain / identity / price+identity)
- Ad Set 3: Warm 90-Day Engagers (3 variants — soft offer / social proof+urgency / identity+facility)
- Ad Set 4: Retargeting 30-Day (3 variants — free PT / last chance / no-risk)

For each variant produce: Primary Text (≤125 chars), Headline (≤27 chars), Description (≤30 chars), Image Idea, UTM URL. Use the campaign brief for offer/offer timing if provided.

**This stage answers:** What does the Meta ad copy look like for each audience and variant?

---

### STAGE 4 — Google Ads (Search + Display)
**Skill:** `google-ads-optimizer`
**Reads:** brand-voice (resolved), `context/utm-convention.md`, seo-targets (resolved), outputs from Stages 1+2, campaign brief
**Output:** `outputs/creatives/[campaign]/paid-ads/google-ads-complete.md`

Run the google-ads-optimizer skill. Produce the full Google Ads output:
- 3 campaigns: Brand Search / Non-Brand Local / Performance Max
- 15 RSA headlines + 4 descriptions (all char-counted, H ≤30, D ≤90)
- Keyword clusters mapped to ad groups (7 clusters)
- Ad copy formulas: Price Anchor / FIFO / Local Authority / Social Proof / Facility Feature
- Ad extensions checklist
- Negative keyword list
- UTM construction with {keyword} dynamic insertion

**This stage answers:** What does the Google Ads structure and copy look like?

---

### STAGE 5 — Creative Briefs (Visual + Video)
**Skill:** `creative-brief-engine`
**Reads:** brand-voice (resolved), `skills/brand-guideline/SKILL.md`, outputs from Stages 3+4
**Output:** `outputs/creatives/[campaign]/creative-briefs/creative-brief-[YYYY-MM-DD].md`

Run the creative-brief-engine skill. For each ad variant produced in Stages 3 and 4, generate:
- Image concept + AI prompt (Ideogram/Nano Banana) + text overlay spec + dimensions
- Video storyboard per scene + shot list + music direction
- Format specs by placement (Feed / Reels / Story / Display)

**This stage answers:** What visual assets should be created and how?

---

### STAGE 6 — UTM Audit + URL Construction
**Skill:** `utm-standardizer`
**Reads:** `context/utm-convention.md`, outputs from Stages 3+4
**Output:** `outputs/creatives/[campaign]/paid-ads/utm-audit-[YYYY-MM-DD].md`

Run the utm-standardizer skill. Audit every UTM URL produced in Stages 3 and 4. Check for: all 4 params present, lowercase, no spaces, correct naming convention, landing page URL correct. Flag any broken or inconsistent URLs.

**This stage answers:** Are all URLs properly tagged for accurate attribution?

---

## Pipeline Inputs

| Input | Required | Source |
|-------|----------|--------|
| Campaign name | Yes | Task prompt |
| Core offer | Yes | Task prompt or blueprint |
| Target location | Yes | Malaga / Ellenbrook / Perth-wide |
| Campaign type | Yes | Acquisition / Retargeting / Seasonal |
| Budget | Recommended | Total or per-channel |
| Offer end date | Recommended | If time-limited |

If a campaign blueprint exists in `outputs/blueprints/`, reference it for: offer details, target ICP, KPI targets, channel budget split.

---

## Pipeline Outputs

```
outputs/
  research/competitor-ads-analysis-[YYYY-MM-DD].md
  creatives/[campaign]/paid-ads/
    meta-ads-complete.md      (all 4 ad sets × 3 variants)
    google-ads-complete.md   (all 3 campaigns with RSA + keywords)
    utm-audit-[YYYY-MM-DD].md
  creatives/[campaign]/creative-briefs/
    creative-brief-[YYYY-MM-DD].md
```

---

## Quality Checklist — Universal
- [ ] Stage 1: Competitor analysis covers the primary competitors per the resolved `research-competitors` file
- [ ] Stage 2: ICP selected and documented per ad set
- [ ] Stage 3: All ad sets present, each with 3 variants, all character counts verified
- [ ] Stage 4: All 15 RSA headlines + 4 descriptions char-counted (H ≤30, D ≤90)
- [ ] Stage 4: {keyword} dynamic insertion used in UTM term (not hardcoded)
- [ ] Stage 4: Negative keyword list applied
- [ ] Stage 5: Creative briefs include AI image prompts (Ideogram / Nano Banana format)
- [ ] Stage 6: All UTM URLs audited — none missing params, all lowercase, no spaces
- [ ] All output files date-stamped YYYY-MM-DD
- [ ] Meta and Google ad copy consistent with brand voice (no corporate language)
- [ ] All UTMs use correct naming convention per `utm-convention.md`
- [ ] Campaign name in output path matches the campaign being run
- [ ] ≥2 psychology triggers applied per ad variant (per resolved `psychology-triggers`)

## CB247-Only Quality Items
- [ ] Stage 1: Competitor analysis covers Anytime, Revo, Snap, Ryderwear
- [ ] Stage 3: Price anchor ($11.95/week) in every Meta ad variant
- [ ] Stage 3: "No lock-in" in every Meta ad variant
- [ ] Add-on services (sauna/ice bath, Kids Hub, Pilates, ChasingRX, yoga, spin) never described as included

## MWCC-Only Quality Items
- [ ] Stage 1: Competitor analysis covers Goodstart, Nido, KindiCare, Care for Kids, Midvale Hub (local)
- [ ] Stage 3: CCS "subject to eligibility" disclaimer in every Meta variant that mentions fees
- [ ] Stage 3: No "best childcare", "premier", "leading", "guaranteed", "award-winning" language (auto-blocks at sync gate)
- [ ] Stage 5: Creative brief specifies educators / spaces / materials / branded graphics — NO children in imagery (locked policy 2026-06-07)
- [ ] Stage 3+4: CTA matches MWCC hierarchy — "Book a tour" / "Join the waitlist" / "Get a quote" — NEVER "Sign Up"
- [ ] No NQS rating claim cited unless verified in `context/mwcc-nqs-ratings.json`