# Strategist — Campaign Blueprint Builder
Purpose: Generate full campaign blueprints from research inputs for CB247.

## Trigger
Activate when user says "run strategist", "build campaign", "campaign blueprint", "create blueprint", or when `outputs/research/` files exist and user wants a campaign plan.

## Inputs (read in this order)
1. `outputs/research/competitor-full-analysis-YYYY-MM-DD.md` — competitor intelligence
2. `outputs/research/pestle-update-YYYY-MM-DD.md` — market context
3. `outputs/research/swot-update-YYYY-MM-DD.md` — SWOT analysis
4. `outputs/research/trends-YYYY-MM-DD.md` — fitness trends
5. `context/brand-voice.md` — brand guidelines
6. `context/seasonal-calendar.md` — upcoming events/hooks
7. `context/psychology-triggers.md` — conversion psychology
8. `state/ga4-data.json` — current traffic/conversion baseline
9. `state/gsc-data.json` — organic search performance

## Campaign Naming Formula
```
[Season]-[Event]-[Year]-[Location] → winter-beginners-2026-malaga
```

## Blueprint Output Template
Save to: `outputs/blueprints/[campaign-name]-blueprint-YYYY-MM-DD.md`

```markdown
# Campaign Blueprint: [CAMPAIGN NAME]

## 1. Overview
- **Campaign Name:** [name]
- **Tagline:** [one-liner]
- **Offer:** [specific offer/value prop]
- **Primary Goal:** [sign-ups / leads / engagement]
- **Target:** [X per location]
- **Brand Color:** #3FA69A

## 2. Meta Ads Strategy
### Ad Set 1: [Audience] ([Age range])
- **Headline:** [hook headline]
- **Body:** [psychology-driven body copy, 3-5 sentences]
- **CTA:** [Book Now / Learn More / Join Free]
- **Triggers:** [list psychology triggers used]
- **UTM:** utm_source=meta&utm_medium=paid_social&utm_campaign=[name]&utm_content=ad-[variant]

### Ad Set 2: [Audience] ([Age range])
[... same structure ...]

## 3. Google Ads (Search)
- **Keywords:** [5-7 keyword clusters]
- **RSA Headlines:** [6 headlines, max 30 chars each]
- **RSA Descriptions:** [4 descriptions, max 90 chars each]
- **UTM:** utm_source=google&utm_medium=paid_search&utm_campaign=[name]&utm_term={keyword}

## 4. Email & SMS Sequence
### Email 1: [Day] — [Subject]
[Full email copy with subject, preview, body, CTA, footer]

### SMS 1: [Day] — [message]
[140 char SMS with UTM link]

## 5. Organic Content Calendar ([Start]–[End])
| Date | IG Post | IG Story | FB Post | Hook |
|------|---------|----------|---------|------|
| Day 1 | [post desc] | [story desc] | [post desc] | [hook] |
[...7-14 rows...]

## 6. UTM Summary
- **Meta:** utm_source=meta&utm_medium=paid_social&utm_campaign=[name]&utm_content=[variant]
- **Google:** utm_source=google&utm_medium=paid_search&utm_campaign=[name]&utm_term={keyword}
- **Email:** utm_source=email&utm_medium=email&utm_campaign=[name]&utm_content=[content]
- **SMS:** utm_source=sms&utm_medium=sms&utm_campaign=[name]&utm_content=[content]

## 7. Budget Allocation (if applicable)
- Meta: $[X]/day
- Google: $[X]/day
- Total: $[X]/day × [Y] days = $[Z]
```

## Campaign Type Formulas

### 1. New Membership Acquisition
**Use when:** Seasonal hook, price promotion, new facility capability
**Offer options:** $0 joining fee / Free first PT session / Free week / Reduced rate
**Audience:** Cold (28-50 Malaga/Ellenbrook) + Warm retargeting (website visitors)
**Platform priority:** Meta → Google Search → Email → SMS

### 2. Re-Engagement (Lapsed Members)
**Use when:** Post-season, after freeze period, 60+ days inactive
**Offer options:** Free freeze extension / $0 rejoin / Bring a friend credit
**Audience:** Lapsed members from CRM
**Platform priority:** Email → SMS → Meta retargeting

### 3. Facility Launch (New Service)
**Use when:** New Reformer Pilates / New class type / Expanded hours
**Offer options:** First 50 members get X / Launch special pricing
**Audience:** Existing members (refer) + Cold local
**Platform priority:** IG/Reels → Meta → Google

### 4. FIFO Campaign
**Use when:** Fly-in/fly-out workers, shift workers, non-standard schedules
**Offer options:** FIFO freeze guarantee / Shift-worker pricing / Opaque schedule access
**Audience:** FIFO workers in mining/oil/gas Perth northern suburbs
**Platform priority:** LinkedIn → Meta → Google Search

### 5. Kids Hub / Family Campaign
**Use when:** School holidays / Active parents segment
**Offer options:** Kids stay free / Family bundle / School holiday special
**Audience:** Parents 28-45, Malaga/Ellenbrook
**Platform priority:** Meta → Instagram → Email → SMS

## Seasonal Hook Calendar (2026)
| Month | Event | Campaign Angle |
|-------|-------|---------------|
| May | Winter prep season | "Cold weather, hot results" |
| June | EOFY | "Invest in yourself" / gym as asset |
| July | School holidays | Kids Hub focus |
| August | Winter wellness | Recovery, sauna, ice bath |
| September | Spring re-entry | "Fresh start" / New season |
| Oct | Perth fitness month | Community challenge |
| Nov | Pre-summer | "Summer body" urgency |
| Dec | Holiday / New Year | "New Year, AlwaysBetter" |

## Psychology Triggers to Weave In
- **Loss Aversion:** "Offer ends [date]"
- **Social Proof:** "8,000+ Perth members"
- **Identity:** "You're already one of us"
- **Authority:** "$11.95/week — best value in Perth"
- **Safety:** "No lock-in. Cancel anytime"
- **Reciprocity:** "Free [X] when you join"
- **Scarcity:** "Only X spots available"

## Quality Checklist
- [ ] Offer is specific and time-bound
- [ ] All 3 Meta ad sets have distinct audiences
- [ ] Google keywords match search intent
- [ ] UTM tags follow convention exactly
- [ ] Email sequence has 3+ emails with psychology triggers
- [ ] SMS messages under 160 chars with UTM
- [ ] Content calendar covers every day of campaign
- [ ] Brand color #3FA69A referenced in creative briefs
- [ ] Tagline "AlwaysBetter" used at least once
- [ ] CTA links to correct landing page (/join or /book-a-tour)

## Output
Save blueprint to: `outputs/blueprints/[campaign-name]-blueprint-YYYY-MM-DD.md`
Then update `state/status.json` with `"last_strategist_run": "YYYY-MM-DD"` and `"blueprint_ready": "[campaign-name]"`
Print: "BLUEPRINT READY — awaiting review"
