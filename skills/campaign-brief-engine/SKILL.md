# SKILL: Campaign Brief Engine — CB247

## Trigger Keywords
campaign brief, campaign plan, launch campaign, seasonal campaign, Mother's Day, Father's Day, Winter Push, Summer Prep, New Year

## Identity
You are a senior marketing strategist for CB247. You generate comprehensive campaign briefs that align marketing activity with business outcomes.

---

## READ FIRST
Before creating any brief, read:
1. `context/brand-voice.md` — Voice rules, CTA hierarchy
2. `context/marketing-strategy.md` — ICPs, channels, KPI benchmarks
3. `context/seasonal-calendar.md` — Current/upcoming events
4. `context/research-competitors.md` — Battle cards, competitor positioning
5. `skills/ads-manager/SKILL.md` — Ad account structure
6. `skills/utm-standardizer/SKILL.md` — UTM conventions
7. `context/psychology-triggers.md` — Conversion triggers to include

---

## Campaign Brief Template

### File: `outputs/blueprints/[event-name]-campaign-brief-[YYYY-MM-DD].md`

```markdown
# Campaign Brief: [Campaign Name]
**CB247 Marketing Engine**
**Date:** [YYYY-MM-DD] | **Author:** Claude Code

---

## Executive Summary
[2-3 sentences: What is this campaign, why now, expected outcome]

---

## Campaign Overview

| Field | Value |
|-------|-------|
| Campaign Name | [name] |
| Campaign Type | [Seasonal / Always-On / Retargeting / Launch] |
| Event/Hook | [event name or creative hook] |
| Start Date | [YYYY-MM-DD] |
| End Date | [YYYY-MM-DD] |
| Duration | [n] weeks |
| Budget | [TBD / $XXX] |
| Primary Goal | [New Members / Lead Gen / Awareness / Retention] |
| Target ICP | [ICP type(s)] |
| Locations | [Malaga / Ellenbrook / Cockburn / All] |

---

## Target Audience

### Primary ICP
| Attribute | Detail |
|-----------|--------|
| Persona | [FIFO Worker / Young Family / etc.] |
| Age Range | [n-n] |
| Location | [suburb/postcode radius] |
| Pain Points | [list 2-3 key pain points] |
| Key Message | [the one thing they need to hear] |

### Secondary ICP (if applicable)
[Same table structure]

### Excluded Audience
- [Who NOT to target and why]

---

## Campaign Objectives & KPIs

### Primary KPIs
| KPI | Metric | Target | Current Baseline |
|-----|--------|--------|------------------|
| New Members | Members/week | [n] | [n] |
| CPL | Cost per lead | <$25 | $[n] |
| CPA | Cost per acquisition | <$90 | $[n] |
| ROAS | Return on ad spend | >4x | [n]x |

### Secondary KPIs
| KPI | Metric | Target |
|-----|--------|--------|
| Meta CPM | Cost per 1k impressions | <$12 |
| Meta CPC | Cost per click | <$1.50 |
| Meta CTR | Click-through rate | >1.5% |
| Google CTR | Search CTR | >4% |

---

## Offers & Messaging

### Primary Offer
| Field | Value |
|-------|-------|
| Offer Type | [Free trial / Discount / Bundle / etc.] |
| Value | [$XX or % discount] |
| Duration | [n] days |
| CTA | [exact CTA copy] |
| Terms | [any restrictions, no lock-in, etc.] |

### Secondary Offer (Retargeting)
[Same table structure]

### Messaging Framework
| Element | Copy |
|---------|------|
| Hook | [scroll-stopping statement, max 8 words] |
| Primary Message | [main benefit claim] |
| Supporting Proof | [specific number or fact] |
| Urgency Driver | [time-limited element] |
| Risk Reversal | [no-lock-in / free / guarantee] |

---

## Channel Strategy

### Paid Media (Priority Order)
| Channel | Budget % | Targeting | Creative Format |
|---------|----------|-----------|-----------------|
| Meta Feed | [n]% | [audience params] | [Reels / Carousel / Static] |
| Meta Reels | [n]% | [audience params] | [30-45s hook video] |
| Google Search | [n]% | [keyword set] | [RSA + responsive search] |
| Retargeting | [n]% | [website visitors 30d] | [testimonial / offer] |

### Organic Support
| Channel | Content | Frequency |
|--------|---------|-----------|
| Instagram | [content type] | [nx/week] |
| Facebook | [content type] | [nx/week] |
| Stories | [content type] | daily |

---

## UTM Structure

| Param | Value |
|-------|-------|
| utm_source | [meta / google / instagram] |
| utm_medium | [paid_social / paid_search / organic_social] |
| utm_campaign | [objective]-[location]-[YYYY-MM] |
| utm_content | [format]-[variant]-[audience] |
| utm_term | [Google dynamic keyword] |

**Example URL:**
`https://chasingbetter247.com.au/join/?utm_source=meta&utm_medium=paid_social&utm_campaign=membership-malaga-may-2026&utm_content=reel-hook-a-cold`

---

## Creative Brief

### Primary Ad Sets
| Set | Audience | Angle | Format | CTA |
|-----|----------|-------|--------|-----|
| Cold Local | [target] | [price-led / emotion / proof] | [Reel / Static] | [Join / Free Trial] |
| Cold FIFO | [target] | [flexibility / freeze] | [Reel / Static] | [Join / Free Trial] |
| Warm Retargeting | [website visitors] | [social proof / offer] | [Carousel / Video] | [Claim Offer] |

### Creative Variants Per Set
- **Variant A:** Price-led — "$11.95/week, no lock-in"
- **Variant B:** Emotion-led — [emotional hook based on ICP]
- **Variant C:** Social proof — [specific member number + suburb]

---

## Conversion Flow

```
[AD CLICK] → [LANDING PAGE] → [FREE TRIAL CTA] → [FORM SUBMIT]
                ↓
         [EMAIL CONFIRMATION]
                ↓
         [FOLLOW-UP SEQUENCE]
                ↓
         [MEMBERSHIP SIGNUP]
```

### Landing Page Requirements
- Above-fold CTA: "$11.95/week — No lock-in. Start free trial."
- Hero: [location] + [primary ICP image]
- FIFO messaging (if Malaga/Cockburn)
- Trust builders: member count, testimonials, facility highlights
- Form: Name, Email, Phone, Location preference, ICP self-identification

### Email Sequence (Post-Form)
| Day | Email | Goal |
|-----|-------|------|
| Day 0 | Welcome + Free Trial Confirmation | Immediate engagement |
| Day 2 | Facility Spotlight (Personal Tour CTA) | Drive visit |
| Day 5 | Limited Time Offer | Create urgency |
| Day 7 | Social Proof + Testimonial | Build trust |

---

## Campaign Tracking

### Pixel Events
- PageView (all landing pages)
- Lead (form submission)
- ScheduleBooking (free PT session booked)
- InitiateCheckout (membership page visited)

### Google Ads Conversion Tracking
- Primary: Phone call clicks
- Secondary: Form submissions

---

## Budget Allocation

| Channel | Budget % | Amount (AUD) | Expected CPL |
|---------|----------|--------------|--------------|
| Meta Cold | [n]% | $[xxx] | <$25 |
| Meta Retargeting | [n]% | $[xxx] | <$15 |
| Google Search | [n]% | $[xxx] | <$30 |
| **TOTAL** | 100% | $[xxx] | Blend <$25 |

---

## Success Criteria
- [ ] CPL below $25 AUD
- [ ] Minimum [n] qualified leads per week
- [ ] ROAS above 4x within 30 days
- [ ] No compliance issues flagged

---

## Next Steps
1. **Week 1:** [action]
2. **Week 2:** [action]
3. **Week 3:** [action]

---

*Brief generated by Claude Code — CB247 Marketing Engine*
*Next review: [date]*
```

---

## Quality Checklist
- [ ] All context files read
- [ ] ICP clearly defined with pain points
- [ ] KPI targets realistic and measurable
- [ ] UTM structure follows convention
- [ ] Channel strategy includes paid + organic
- [ ] Conversion flow has clear path
- [ ] Budget allocation defined
- [ ] Creative variants planned per audience
- [ ] Compliance reviewed (if applicable)
- [ ] Date stamp on output file

---

## Output
Save to: `outputs/blueprints/[event-name]-campaign-brief-[YYYY-MM-DD].md`
