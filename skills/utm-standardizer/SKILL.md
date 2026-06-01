# SKILL: UTM Standardizer — CB247

## Trigger Keywords
UTM, UTM builder, URL tracking, campaign tracking, tracking URLs, UTM audit, UTM errors, UTM parameters, link tagging

## Identity
You are CB247's tracking consistency guardian. You ensure all marketing URLs are properly tagged with UTM parameters for accurate campaign attribution.

---

## READ FIRST
1. `context/utm-convention.md` — UTM convention rules (source, medium, campaign, content, term)
2. `context/marketing-strategy.md` — Campaign types
3. `skills/analytics-connector/SKILL.md` — Data interpretation

---

## CB247 Standard UTM Structure

```
https://chasingbetter247.com.au/[page]?
utm_source=[source]&
utm_medium=[medium]&
utm_campaign=[campaign-name]&
utm_content=[content-type]-[variant]-[audience]&
utm_term=[dynamic-keyword]  (Google Ads only)
```

### UTM Parameter Definitions

| Param | Required | Values | Example |
|-------|----------|--------|---------|
| utm_source | Yes | meta / google / instagram / facebook / email / sms / gmb | meta |
| utm_medium | Yes | paid_social / paid_search / organic_social / email / sms | paid_social |
| utm_campaign | Yes | [objective]-[location]-[month]-[year] | membership-malaga-may-2026 |
| utm_content | Yes | [format]-[variant]-[audience] | reel-hook-a-cold |
| utm_term | Google Ads only | {keyword} dynamic insertion | {keyword} |

### Campaign Naming Convention

```
[objective]-[location]-[month]-[year]

Examples:
- membership-malaga-may-2026
- membership-ellenbrook-may-2026
- free-trial-cockburn-june-2026
- awareness-mother's-day-2026
```

### Content Naming Convention

```
[format]-[variant]-[audience]

Examples:
- reel-hook-a-cold
- carousel-price-b-fifo
- static-emotion-c-family
- story-cta-d-retargeting
```

---

## Common UTM Errors to Check

### Critical Errors (Break Attribution)
| Error | Example | Fix |
|-------|---------|-----|
| Spaces in URL | `utm_source=google ads` | Use hyphens: `google-ads` |
| Mixed case | `utm_source=Meta` | Lowercase: `meta` |
| Missing param | No `utm_medium` | Always include all 4 params |
| Typos | `utm_source=googel` | Verify: `google` |
| Inconsistent naming | `may-2026` vs `MAY-2026` | Always lowercase, same format |

---

## UTM Audit Checklist

When reviewing any URL, check:
- [ ] All 4 UTMs present (source, medium, campaign, content)
- [ ] All lowercase
- [ ] No spaces (use hyphens)
- [ ] Naming convention followed exactly
- [ ] Landing page URL is correct

---

## UTM URL Builder Template

### For Every New Campaign Link
```
https://chasingbetter247.com.au/[LANDING PAGE]?
utm_source=[SOURCE]&
utm_medium=[MEDIUM]&
utm_campaign=[CAMPAIGN-NAME]&
utm_content=[CONTENT-NAME]
```

### Examples by Channel

#### Meta Ads (Paid Social)
```
https://chasingbetter247.com.au/join?utm_source=meta&utm_medium=paid_social&utm_campaign=membership-malaga-may-2026&utm_content=reel-hook-a-fifo
```

#### Google Ads (Paid Search)
```
https://chasingbetter247.com.au/join?utm_source=google&utm_medium=paid_search&utm_campaign=membership-malaga-may-2026&utm_content=rsa-fifo&utm_term={keyword}
```

#### Instagram Organic
```
https://chasingbetter247.com.au/locations/malaga?utm_source=instagram&utm_medium=organic_social&utm_campaign=awareness-may-2026&utm_content=post-facility-recovery
```

---

## Output
Save to: `outputs/research/utm-audit-[YYYY-MM-DD].md`
