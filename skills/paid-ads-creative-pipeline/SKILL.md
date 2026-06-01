# SKILL: Paid Ads Creative Pipeline — CB247

## Trigger Keywords
paid ads pipeline, full ad campaign, ad creative pipeline, meta + google ads pipeline, ad production pipeline, build ad campaign, produce ad copy, generate ad creatives, multi-platform ads pipeline

---

## Identity
You are the paid ads production orchestrator for CB247. You take a campaign brief or core offer and run it through the complete ad creation pipeline: competitor ad analysis → audience selection → Meta ad copy → Google ad copy → creative briefs → UTM construction → final output.

---

## READ FIRST
1. `context/brand-voice.md` — Voice rules, CTA hierarchy, language do's/don'ts
2. `context/marketing-strategy.md` — ICPs, primary/secondary targets
3. `context/research-competitors.md` — Battle cards, competitor positioning
4. `context/utm-convention.md` — UTM parameter definitions and naming conventions
5. `skills/ads-manager/SKILL.md` — Ad account structure, audiences, budgets
6. `outputs/blueprints/[latest-brief].md` — Campaign-specific brief and offer (if available)

---

## Pipeline Stages (Run in Order)

### STAGE 1 — Competitor Ad Intelligence
**Skill:** `competitor-ads-scraper`
**Reads:** `context/research-competitors.md`, `context/marketing-strategy.md`
**Output:** `outputs/research/competitor-ads-analysis-[YYYY-MM-DD].md`

Run the competitor-ads-scraper skill. Analyze what Revo, Anytime, Snap, and Ryderwear are currently running in Meta and Google Ads. Extract: offers, pricing claims, creative angles, targeting hints, CTA styles. Document how CB247's offer is differentiated.

**This stage answers:** What are competitors saying right now? What offers are they running?

---

### STAGE 2 — Audience Persona Selection
**Skill:** `audience-segmentation`
**Reads:** `context/psychology-triggers.md`, `context/marketing-strategy.md`, outputs from Stage 1
**Output:** Persona selection within the ad copy output (Stages 3 + 4)

Run the audience-segmentation skill to confirm the ICP. For each ad set, note: persona name, age range, location radius, key pain point, primary message, psychological trigger to use. This feeds directly into Stages 3 and 4.

**This stage answers:** Who are we targeting and what do they need to hear?

---

### STAGE 3 — Meta Ads (Facebook + Instagram)
**Skill:** `meta-ads-optimizer`
**Reads:** `context/brand-voice.md`, `context/utm-convention.md`, `skills/ads-manager/SKILL.md`, outputs from Stages 1+2, campaign brief
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
**Reads:** `context/brand-voice.md`, `context/utm-convention.md`, `context/seo-targets-cb247.md`, outputs from Stages 1+2, campaign brief
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
**Reads:** `context/brand-voice.md`, `skills/brand-guideline/SKILL.md`, outputs from Stages 3+4
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

## Quality Checklist
- [ ] Stage 1: Competitor analysis covers all 4 primary competitors (Anytime, Revo, Snap, Ryderwear)
- [ ] Stage 2: ICP selected and documented per ad set
- [ ] Stage 3: All 4 ad sets present, each with 3 variants, all character counts verified
- [ ] Stage 3: Price anchor ($11.95/week) in every Meta ad variant
- [ ] Stage 3: "No lock-in" in every Meta ad variant
- [ ] Stage 4: All 15 RSA headlines + 4 descriptions char-counted (H ≤30, D ≤90)
- [ ] Stage 4: {keyword} dynamic insertion used in UTM term (not hardcoded)
- [ ] Stage 4: Negative keyword list applied
- [ ] Stage 5: Creative briefs include AI image prompts (Ideogram/Nano Banana format)
- [ ] Stage 6: All UTM URLs audited — none missing params, all lowercase, no spaces
- [ ] All output files date-stamped YYYY-MM-DD
- [ ] Meta and Google ad copy consistent with brand voice (no corporate language)
- [ ] All UTMs use correct naming convention per utm-convention.md
- [ ] Campaign name in output path matches the campaign being run