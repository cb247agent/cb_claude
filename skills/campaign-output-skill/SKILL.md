# SKILL: Campaign Output Skill — CB247

## Trigger Keywords
campaign output, full campaign output, multi-channel campaign, generate campaign, campaign delivery, campaign production, full campaign, end-to-end campaign, campaign execution, launch campaign, seasonal campaign execution

---

## Identity
You are the campaign delivery orchestrator for CB247. You take a campaign brief and produce the complete multi-channel content output: paid ads + organic social + email funnel + landing page + stakeholder report. All from one brief.

---

## READ FIRST
1. `context/brand-voice.md` — Voice rules, CTA hierarchy
2. `context/marketing-strategy.md` — ICPs, channels, KPI benchmarks
3. `context/seasonal-calendar.md` — Current/upcoming events
4. `context/research-competitors.md` — Battle cards, competitor positioning
5. `context/psychology-triggers.md` — Conversion triggers per ICP
6. `context/utm-convention.md` — UTM parameter definitions

---

## Pipeline Stages (Run in Order)

### STAGE 1 — Campaign Brief (Core Strategy)
**Skill:** `campaign-brief-engine`
**Reads:** All context files above, competitor intelligence
**Output:** `outputs/blueprints/[event-name]-campaign-brief-[YYYY-MM-DD].md`

Run the campaign-brief-engine skill. Produce the full campaign brief including:
- Campaign overview (name, type, dates, duration, budget, KPIs)
- Primary + secondary ICP definitions with pain points
- Offers (primary + secondary with terms, CTA, risk reversal)
- Channel strategy (paid + organic split, budget %)
- UTM structure (source, medium, campaign, content naming)
- Creative brief (ad sets × variants × formats)
- Conversion flow (ad → landing → form → nurture → signup)
- Email sequence (Day 0 / 2 / 5 / 7)
- Pixel events, budget allocation, success criteria

If a campaign brief already exists in `outputs/blueprints/`, skip this stage and use the existing brief for Stages 2–6.

**This stage answers:** What's the campaign strategy, who are we targeting, and what's the full plan?

---

### STAGE 2 — Multi-Channel Content Waterfall
**Skill:** `content-waterfall`
**Reads:** `context/brand-voice.md`, `context/marketing-strategy.md`, `skills/brand-guideline/SKILL.md`, `skills/content-writer/SKILL.md`, campaign brief from Stage 1
**Output:** `outputs/content/waterfall-[topic]-[YYYY-MM-DD].md`

Run the content-waterfall skill. Take the core campaign idea and explode it across all platforms. Produce:
- 1 IG feed caption + hashtag set
- 3 IG Reel scripts (Story Hook / Contrast Hook / Stat Hook)
- 5 IG Story frames
- 1 FB long-form post
- 2 Meta ad variants (Price-Led / Emotion-Led)
- 1 promotional email
- 1 SMS message

Each asset must carry the campaign offer consistently. Adapt tone per platform per brand-voice.md rules.

**This stage answers:** How do we express the campaign across every channel from one core idea?

---

### STAGE 3 — Email Nurture Sequence
**Skill:** `email-funnel-builder`
**Reads:** `skills/member-onboarding/SKILL.md`, `context/psychology-triggers.md`, campaign brief from Stage 1
**Output:** `outputs/content/email-sequence-[campaign]-[YYYY-MM-DD].md`

Run the email-funnel-builder skill. Build the full email + SMS sequence for the campaign:
- Sequence type: New Lead (4 emails + 2 SMS) for acquisition / Re-engage (1 email + 1 SMS) for retargeting
- Day 0: Welcome + campaign offer confirmation
- Day 2: Facility spotlight with tour CTA
- Day 5: Urgency or limited-time hook (if applicable)
- Day 7: Social proof + testimonial + final CTA
- SMS schedule: Day 5 urgency + Day 7 final call
- Rules: Subject ≤40 chars, 1 CTA per email, SMS ≤160 chars

**This stage answers:** What's the post-signup nurture sequence that converts leads to members?

---

### STAGE 4 — Organic Social Calendar
**Skill:** `social-content-calendar`
**Reads:** `skills/social-analyst/SKILL.md`, `context/research-competitors.md`, campaign brief from Stage 1
**Output:** `outputs/content/social-calendar-[campaign]-[YYYY-MM-DD].md`

Run the social-content-calendar skill. Build a 30-day organic social plan aligned with the campaign:
- Frequency: IG feed 4–5x/week + stories daily + FB 3x/week
- Content split: 60% value / 25% community / 15% promo
- Schedule anchored to campaign offer dates (Days 1–3 launch, Days 4–7 offer window, Days 8–10 close)
- Organic posts support paid ads — no conflicting messaging
- Platform: Instagram primary, Facebook secondary

**This stage answers:** How does organic social support the campaign over 30 days?

---

### STAGE 5 — Paid Ads (Meta + Google)
**Skill:** `paid-ads-creative-pipeline` (this pipeline — triggers recursively)
**Reads:** Campaign brief from Stage 1, all context files
**Output:** `outputs/creatives/[campaign]/paid-ads/`

Invoke the `paid-ads-creative-pipeline` skill as a sub-task. This runs its own full pipeline:
- Stage 1: Competitor ads analysis
- Stage 2: Audience persona selection
- Stage 3: Meta ad copy (4 ad sets × 3 variants)
- Stage 4: Google ad copy (3 campaigns with RSA + keywords)
- Stage 5: Creative briefs (visual + video specs)
- Stage 6: UTM audit

**This stage answers:** What paid ads support this campaign across Meta and Google?

---

### STAGE 6 — Landing Page (for campaign offer)
**Skill:** `seo-landing-page-writer`
**Reads:** Campaign brief from Stage 1, `context/brand-voice.md`, `skills/brand-guideline/SKILL.md`
**Output:** `outputs/seo/content/draft-[campaign]-landing-[YYYY-MM-DD].html`

Run the seo-landing-page-writer skill. Build a campaign-specific landing page:
- Hero: Campaign offer headline + subhead
- Above-fold CTA: Campaign offer (e.g., "$0 Joining Fee — ends May 10")
- Sections: Problem → Offer → Features → Social proof → FIFO/family angle (if relevant) → FAQ
- 3 CTAs: Top (offer), Middle (free trial), Bottom (join)
- Dark premium theme (#0a0a0a / #3FA69A)
- Landing page must match the ad promise exactly

**This stage answers:** Where do people land after clicking the ad? Does the page close the loop?

---

### STAGE 7 — Executive Summary Report
**Skill:** `report-formatter`
**Reads:** All outputs from Stages 1–6
**Output:** `outputs/reports/campaign-output-[campaign]-[YYYY-MM-DD]-final.md`

Run the report-formatter skill. Produce a McKinsey-style executive summary of the full campaign delivery:
- Campaign overview (1 paragraph)
- What was produced (by stage)
- Key offers, channels, ICPs
- Budget summary (if available)
- Next actions for launch

**This stage answers:** What was delivered and what's next to launch?

---

## Pipeline Inputs

| Input | Required | Source |
|-------|----------|--------|
| Campaign name | Yes | Task prompt |
| Campaign type | Yes | Seasonal / Always-On / Retargeting / Launch |
| Event/hook | Recommended | From seasonal-calendar.md or task prompt |
| Start date | Yes | Task prompt |
| End date | Yes | Task prompt |
| Primary ICP | Yes | FIFO / Young Family / Serious Trainer / Newcomer |
| Primary offer | Yes | Free trial / $0 joining fee / Discount |
| Budget | Recommended | Total budget or per-channel |

---

## Pipeline Outputs

```
outputs/
  blueprints/[campaign]-campaign-brief-[YYYY-MM-DD].md
  content/
    waterfall-[topic]-[YYYY-MM-DD].md
    email-sequence-[campaign]-[YYYY-MM-DD].md
    social-calendar-[campaign]-[YYYY-MM-DD].md
  creatives/[campaign]/paid-ads/
    meta-ads-complete.md
    google-ads-complete.md
    utm-audit-[YYYY-MM-DD].md
    creative-briefs/creative-brief-[YYYY-MM-DD].md
  seo/content/draft-[campaign]-landing-[YYYY-MM-DD].html
  reports/campaign-output-[campaign]-[YYYY-MM-DD]-final.md
```

---

## Quality Checklist
- [ ] Stage 1: Campaign brief complete with all sections filled
- [ ] Stage 2: Waterfall produces ≥14 assets across 7+ platforms
- [ ] Stage 2: All assets consistent with campaign offer (no mixed messaging)
- [ ] Stage 3: Email sequence has 4 emails + 2 SMS, each ≤160 chars (SMS), subjects ≤40 chars
- [ ] Stage 3: Email CTA is single, direct, and matches campaign offer
- [ ] Stage 4: Social calendar covers 30 days with correct frequency
- [ ] Stage 5: Paid ads pipeline invoked — meta + google ads complete
- [ ] Stage 5: All Meta ads have price anchor ($11.95/week) and "no lock-in"
- [ ] Stage 5: All Google RSAs have headlines ≤30 chars and descriptions ≤90 chars
- [ ] Stage 6: Landing page has 3 CTAs, PAS framework, dark theme
- [ ] Stage 6: Landing page offer matches ad promise exactly
- [ ] Stage 7: Executive report summarizes all 7 stages with specific outputs
- [ ] All output files date-stamped YYYY-MM-DD
- [ ] UTM naming convention followed across all stages (lowercase, hyphens, correct format)
- [ ] Brand voice consistent — no corporate language anywhere
- [ ] Campaign name used consistently in all file paths
- [ ] Pipeline run for a specific campaign with dates, offer, and ICP defined