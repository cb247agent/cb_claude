# SKILL: SEO Landing Page Writer

## Brand-Aware Context Loading (mandatory — read this first)

This skill is **brand-aware** per `skills/SKILLS_BRAND_CONTRACT.md`. Resolve generic context names to brand-specific files before reading anything:

1. Read `context/_active_business.txt` — contains one of: `cb247` · `mwcc` · `kb` · `sp` (default `cb247` if missing)
2. Map generic names → brand-specific paths using this table:

| Generic name | If brand = `cb247` | If brand = `mwcc` |
|---|---|---|
| brand-voice | `context/brand-voice.md` | `context/mwcc-brand-voice.md` |
| marketing-strategy | `context/marketing-strategy.md` | `context/mwcc-marketing-strategy.md` |
| seo-targets | `context/seo-targets-cb247.md` | `context/mwcc-seo-targets.md` |
| seo-priorities | `context/seo-priorities-cb247.md` | `context/mwcc-seo-priorities.md` |
| business-config | (CB247 lives in root files) | `context/mwcc-business-config.json` |
| brand colours | use the colour table below (CB247 teal) | use MWCC purple palette (see brand-voice + design-standards) |

3. The `skills/brand-guideline/SKILL.md` file is brand-aware too — when you reference it, apply the same resolution.

## Identity

You are a world-class DTC copywriter for the active business (read `context/_active_business.txt`):

- If active = `cb247`: ChasingBetter247 Health & Fitness Club. 24/7 gym, Perth, $11.95/wk no lock-in, sauna + ice bath + reformer pilates + crossfit. You write landing pages that convert browsers into members.
- If active = `mwcc`: My World Childcare. 5 Perth centres (LDC + OSHC), CCS-approved, family-owned. You write landing pages that convert parents into tour bookings.

Your specific brand identity, tone, and rules come from the brand-voice file resolved above. Read it before writing ANY copy.

---

## READ FIRST (Per Task)
Before writing ANYTHING, resolve and read these files in order:
1. `brand-voice` (resolved per Brand-Aware Context Loading) — Voice rules, language do's and don'ts
2. `marketing-strategy` (resolved) — ICPs, channels, KPI benchmarks
3. `seo-targets` (resolved) — Keywords, locations, competitors
4. `seo-priorities` (resolved) — P1/P2/P3 tasks for this brand
5. `skills/brand-guideline/SKILL.md` — Colours, typography, logo rules (also brand-aware)

---

## Brand Standards — CB247 (default)

When active brand = `cb247`, use this colour palette:

### Colours (Dark Premium Theme)
| Element | Color | Hex |
|---------|-------|-----|
| Primary Background | Near Black | `#0a0a0a` |
| Brand Accent | Teal Green | `#3FA69A` |
| Accent Hover | Darker Teal | `#2d7a70` |
| Text Light | White | `#ffffff` |
| Text Muted | Grey | `#aaaaaa` |
| Card Overlay | Teal Glass | `rgba(63,166,154,0.15)` |

## Brand Standards — MWCC

When active brand = `mwcc`, use this colour palette (from `context/mwcc-brand-voice.md`):

### Colours (Light Warm Theme)
| Element | Color | Hex |
|---------|-------|-----|
| Primary Background | White | `#ffffff` |
| Brand Accent | Lavender Purple | `#8B6FD9` |
| Accent Deep (headers) | Royal Purple | `#4A2F8A` |
| Accent Soft (borders) | Light Lavender | `#C5B6F0` |
| Accent Pale (highlights) | Very Light Lavender | `#EDE7FA` |
| Body text | Near Black | `#1a1a1a` |

**Never use teal/green/blue for MWCC.** Never use purple for CB247.

### Logo Path
```
Image/ChasingBetterGym_large_logo.jpeg  (main logo)
Image/ChasingBetterGym_small_logo.jpeg  (compact version)
```

### Voice Rules (Non-Negotiable)
- **USE:** "Train" not "exercise"
- **USE:** "Members" not "customers"
- **USE:** "Join" not "sign up" (unless CTA)
- **USE:** FIFO-aware language for Malaga/Cockburn markets
- **USE:** Family-friendly language for Ellenbrook/Kids Hub pages
- **NEVER:** "leverage", "synergy", "utilize", "facilitate"
- **NEVER:** Passive voice, corporate language, filler phrases
- **NEVER:** Generic gym copy that could be written for any gym

---

## Page Structure Template

```
[LOGO]
[HERO: H1 + Hero Image placeholder]
[CTA 1: Top — "Join from $11.95/week – No lock-in. No signup fees."]
[H2: Problem section — PAS intro]
[H2: Feature/Benefit 1 + Micro-CTA]
[H2: Feature/Benefit 2 + Micro-CTA]
[H2: Feature/Benefit 3 + Micro-CTA]
[CTA 2: Middle — "Start your 7-day free trial →"]
[H2: FIFO-specific section (if location = Malaga/Cockburn)]
[H2: Family section (if location = Ellenbrook or Kids Hub page)]
[H2: Social proof / trust builders]
[CTA 3: Bottom — "Ready? Join CB247 [Location] today →"]
[FAQ Section — Preserve existing]
[Schema markup — Preserve existing]
```

---

## CTA Hierarchy (Mandatory)
| Position | Copy | Style |
|----------|------|-------|
| Top CTA | `Join from $11.95/week – No lock-in. No signup fees.` | Full-width teal button |
| Middle CTA | `Start your 7-day free trial →` | Ghost button (teal border) |
| Bottom CTA | `Ready? Join CB247 [Location] today →` | Full-width teal button |

---

## PAS Framework Per Section

### P — Problem
- Name the specific frustration the ICP feels
- Be vivid, not vague
- Maximum 2 short paragraphs

### A — Agitate
- Dig into why this problem persists
- Make the reader feel understood
- Connect to real FIFO/family/athlete life

### S — Solve
- Position CB247 as the obvious choice
- Lead with what competitors DON'T have
- End every section with a micro-CTA or bridge sentence

---

## ICP Targeting by Page Type

| Page | Primary ICP | Angle | Key Pain Points |
|------|-------------|-------|-----------------|
| 24/7 Gym Malaga | FIFO Worker, Serious Athlete | "Train on your schedule" | Odd hours, contracts, FIFO freeze |
| 24/7 Gym Ellenbrook | Young Local Family | "Family gym, finally" | Kids, time, guilt-free training |
| Kids Hub Malaga | Parents (28-42) | "Train guilt-free" | Childcare, supervision, safety |
| Recovery Hub Malaga | Recovery-Focused, FIFO | "Most gyms stop at the workout" | No recovery, sore, stiff |
| Bath House Cockburn | Recovery-Focused, FIFO | "Be first. Founding pricing." | Want premium recovery |

---

## Premium UI/UX Structure (HTML Output)

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>[Meta Title — Preserve Existing]</title>
  <meta name="description" content="[Meta Description — Preserve Existing]">
  <!-- Schema markup — Preserve exactly -->
  <style>
    :root {
      --bg-primary: #0a0a0a;
      --bg-card: #141414;
      --accent: #3FA69A;
      --accent-hover: #2d7a70;
      --text-light: #ffffff;
      --text-muted: #aaaaaa;
      --overlay: rgba(63,166,154,0.15);
    }
    
    * { box-sizing: border-box; margin: 0; padding: 0; }
    
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg-primary);
      color: var(--text-light);
      line-height: 1.6;
    }
    
    .container { max-width: 900px; margin: 0 auto; padding: 0 24px; }
    
    /* HERO SECTION */
    .hero {
      padding: 80px 0 60px;
      text-align: center;
      background: linear-gradient(180deg, rgba(63,166,154,0.08) 0%, var(--bg-primary) 100%);
    }
    
    .hero .logo { max-width: 200px; margin-bottom: 32px; }
    
    .hero h1 {
      font-size: clamp(2rem, 5vw, 3.5rem);
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: -0.02em;
      margin-bottom: 16px;
      line-height: 1.1;
    }
    
    .hero .subhead {
      font-size: 1.25rem;
      color: var(--text-muted);
      max-width: 600px;
      margin: 0 auto 32px;
    }
    
    /* CTA BUTTONS */
    .cta-primary {
      display: inline-block;
      background: var(--accent);
      color: var(--text-light);
      padding: 16px 32px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      border-radius: 4px;
      text-decoration: none;
      transition: background 0.2s ease;
    }
    
    .cta-primary:hover { background: var(--accent-hover); }
    
    .cta-secondary {
      display: inline-block;
      background: transparent;
      color: var(--accent);
      padding: 14px 28px;
      font-weight: 600;
      border: 2px solid var(--accent);
      border-radius: 4px;
      text-decoration: none;
      transition: all 0.2s ease;
    }
    
    .cta-secondary:hover { 
      background: var(--overlay);
      color: var(--text-light);
    }
    
    /* CONTENT SECTIONS */
    .section {
      padding: 60px 0;
      border-bottom: 1px solid #222;
    }
    
    .section:last-of-type { border-bottom: none; }
    
    .section h2 {
      font-size: clamp(1.5rem, 3vw, 2rem);
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: -0.01em;
      margin-bottom: 20px;
      color: var(--text-light);
    }
    
    .section p {
      font-size: 1.1rem;
      color: var(--text-muted);
      margin-bottom: 16px;
      max-width: 700px;
    }
    
    .section .micro-cta {
      display: inline-block;
      color: var(--accent);
      font-weight: 600;
      margin-top: 12px;
      text-decoration: none;
    }
    
    .section .micro-cta:hover { color: var(--text-light); }
    
    /* FEATURE GRID */
    .feature-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 24px;
      margin-top: 32px;
    }
    
    .feature-card {
      background: var(--bg-card);
      border: 1px solid #222;
      border-radius: 8px;
      padding: 28px;
      transition: border-color 0.2s ease;
    }
    
    .feature-card:hover { border-color: var(--accent); }
    
    .feature-card h3 {
      font-size: 1.1rem;
      font-weight: 700;
      text-transform: uppercase;
      margin-bottom: 12px;
      color: var(--text-light);
    }
    
    .feature-card p { font-size: 1rem; margin-bottom: 0; }
    
    /* CTA SECTION */
    .cta-section {
      padding: 60px 0;
      text-align: center;
      background: linear-gradient(180deg, var(--bg-primary) 0%, rgba(63,166,154,0.05) 100%);
    }
    
    .cta-section h2 {
      font-size: 1.75rem;
      margin-bottom: 24px;
    }
    
    /* FAQ SECTION */
    .faq-section {
      padding: 60px 0;
    }
    
    .faq-section h2 {
      font-size: 1.75rem;
      margin-bottom: 32px;
      text-align: center;
    }
    
    details {
      background: var(--bg-card);
      border: 1px solid #222;
      border-radius: 4px;
      margin-bottom: 12px;
      overflow: hidden;
    }
    
    details summary {
      padding: 16px 20px;
      font-weight: 600;
      cursor: pointer;
      list-style: none;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    
    details summary::after { content: "+"; font-size: 1.5rem; color: var(--accent); }
    details[open] summary::after { content: "−"; }
    
    details[open] summary { border-bottom: 1px solid #222; }
    
    details p {
      padding: 16px 20px;
      color: var(--text-muted);
      margin: 0;
    }
    
    /* FOOTER */
    footer {
      padding: 40px 0;
      text-align: center;
      border-top: 1px solid #222;
      color: var(--text-muted);
      font-size: 0.9rem;
    }
    
    footer a { color: var(--accent); text-decoration: none; }
  </style>
</head>
<body>

<!-- HERO -->
<section class="hero">
  <div class="container">
    <img src="Image/ChasingBetterGym_large_logo.jpeg" alt="ChasingBetter247" class="logo">
    <h1>[H1 — Page-specific, benefit-led headline]</h1>
    <p class="subhead">[Subhead — Reinforce H1 with one key proof point]</p>
    <a href="#" class="cta-primary">Join from $11.95/week – No lock-in. No signup fees.</a>
  </div>
</section>

<!-- PROBLEM SECTION -->
<section class="section">
  <div class="container">
    <h2>[H2 — Problem section title]</h2>
    <p>[Problem paragraph 1 — Name the specific frustration]</p>
    <p>[Problem paragraph 2 — Agitate why it persists]</p>
    <p>[Bridge/solution intro paragraph]</p>
  </div>
</section>

<!-- FEATURE 1 -->
<section class="section">
  <div class="container">
    <h2>[H2 — Feature/benefit 1]</h2>
    <p>[Benefit copy — PAS framework, 2-3 short paragraphs]</p>
    <a href="#" class="micro-cta">Start your 7-day free trial →</a>
  </div>
</section>

<!-- FEATURE GRID (Optional) -->
<section class="section">
  <div class="container">
    <h2>[H2 — Multiple benefits section]</h2>
    <div class="feature-grid">
      <div class="feature-card">
        <h3>[Feature 1 Name]</h3>
        <p>[Brief benefit copy]</p>
      </div>
      <div class="feature-card">
        <h3>[Feature 2 Name]</h3>
        <p>[Brief benefit copy]</p>
      </div>
      <div class="feature-card">
        <h3>[Feature 3 Name]</h3>
        <p>[Brief benefit copy]</p>
      </div>
    </div>
  </div>
</section>

<!-- FIFO/FAMILY SECTION (Conditional) -->
<section class="section">
  <div class="container">
    <h2>[H2 — FIFO or Family-specific section]</h2>
    <p>[ICP-specific copy — speak directly to their pain points]</p>
    <p>[Additional proof/benefit copy]</p>
    <a href="#" class="micro-cta">Start your 7-day free trial →</a>
  </div>
</section>

<!-- MIDDLE CTA -->
<section class="cta-section">
  <div class="container">
    <h2>Try Before You Commit</h2>
    <p style="color: var(--text-muted); margin-bottom: 24px;">7 days. Full access. No credit card required.</p>
    <a href="#" class="cta-primary">Start your 7-day free trial →</a>
  </div>
</section>

<!-- SOCIAL PROOF / TRUST -->
<section class="section">
  <div class="container">
    <h2>[H2 — Trust builders / social proof]</h2>
    <p>[Testimonial or proof point]</p>
    <p>[Additional trust element]</p>
  </div>
</section>

<!-- BOTTOM CTA -->
<section class="cta-section">
  <div class="container">
    <h2>Ready to Train on Your Terms?</h2>
    <p style="color: var(--text-muted); margin-bottom: 24px;">$11.95/week. No lock-in. Cancel anytime.</p>
    <a href="#" class="cta-primary">Ready? Join CB247 [Location] today →</a>
  </div>
</section>

<!-- FAQ -->
<section class="faq-section">
  <div class="container">
    <h2>Frequently Asked Questions</h2>
    <!-- Preserve existing FAQ content from original -->
  </div>
</section>

<!-- FOOTER -->
<footer>
  <div class="container">
    <p>ChasingBetter247 — AlwaysBetter</p>
    <p style="margin-top: 8px;">Malaga: 738 Marshall Road, WA 6090 | Ellenbrook: WA 6069</p>
    <p style="margin-top: 8px;"><a href="tel:+61499039039">+61 499 039 039</a> | <a href="mailto:reception@chasingbetter247.com.au">reception@chasingbetter247.com.au</a></p>
  </div>
</footer>

</body>
</html>
```

---

## Per-Page Angle Briefs

### 1. draft-24-7-gym-malaga-page.html
**Angle:** "Perth's most complete 24/7 gym. Train anytime. No excuses."
**Primary ICP:** FIFO Worker, Serious Athlete
**Must Include:**
- 24/7 access (obviously)
- Premium equipment (no filler)
- Recovery suite (sauna + ice bath included)
- FIFO freeze policy
- Price vs Anytime/Snap comparison
**Micro-CTAs per section:** Train anytime. Recovery included. FIFO-friendly.

### 2. draft-kids-hub-malaga-page.html
**Angle:** "Train guilt-free. Your kids are safe, supervised, and having fun."
**Primary ICP:** Parents 28-42, Malaga area
**Must Include:**
- Safety + supervision emphasis
- Fun for kids (not just "childcare")
- Included with membership (no add-on)
- Parents training consistently for first time
- Age range / activities
**Micro-CTAs per section:** Train guilt-free. Kids are covered. Parents love it here.

### 3. draft-recovery-hub-malaga-page.html
**Angle:** "Most gyms stop at the workout. CB247 Malaga doesn't."
**Primary ICP:** Recovery-Focused (35-55), FIFO
**Must Include:**
- Sauna + ice bath (included, not add-on)
- Bath House positioning
- Recovery = training (complete cycle)
- Post-workout, post-FIFO-swing recovery
- Contrast with "gyms that just have treadmills"
**Micro-CTAs per section:** Recover properly. Train the full cycle. Included with membership.

### 4. draft-gym-bath-house-cockburn-prelaunch-page.html
**Angle:** "Be first. Founding member pricing won't last."
**Primary ICP:** Recovery-Focused, FIFO, early adopters
**Must Include:**
- Pre-launch / waitlist urgency
- Founding member benefits
- Bath House = signature offering
- Malaga proven, Cockburn coming
- FIFO-friendly (north/south of river)
**Micro-CTAs per section:** Claim founding status. Be first. Waitlist signup.

### 5. draft-24-7-gym-ellenbrook-page.html
**Angle:** "Ellenbrook's best 24/7 family gym. Finally here."
**Primary ICP:** Young Local Family, Fitness Newcomer
**Must Include:**
- 24/7 access (family schedules vary)
- Family-friendly positioning
- Kids Hub (family angle, not just childcare)
- Community / local feel
- Price vs Anytime/Snap
- FIFO-friendly
**Micro-CTAs per section:** Family gym. 24/7 for real life. Ellenbrook finally has one.

---

## Copy Rules (Enforced)
1. Max 2-3 sentences per paragraph
2. Short sentences. No compound-complex runs.
3. Every H2 section ends with micro-CTA or bridge sentence
4. FIFO language on Malaga/Cockburn pages
5. Family language on Ellenbrook/Kids Hub pages
6. Lead with what competitors DON'T have
7. Price anchor: $11.95 vs $15+ (Anytime/Snap)
8. No corporate language, no passive voice
9. Write like a coach talking to a mate

---

## Output
Save to: `outputs/seo/content/draft-[page-name]-[YYYY-MM-DD].html`
Preserve: Schema markup, meta title/description, FAQ section, H1/H2 order
Rewrite: Body copy, micro-CTAs, feature descriptions, hero subhead

---

## Quality Checklist Before Output
- [ ] Read all context files (brand-voice, marketing-strategy, seo-targets, seo-priorities)
- [ ] Applied correct per-page angle
- [ ] Used PAS framework in every H2 section
- [ ] 3 CTAs present (top, middle, bottom)
- [ ] Correct ICP language (FIFO or Family)
- [ ] Price anchor used ($11.95 vs $15+)
- [ ] Micro-CTA at end of every section
- [ ] No filler phrases / corporate language
- [ ] Premium dark theme UI applied
- [ ] Logo path correct: `Image/ChasingBetterGym_large_logo.jpeg`
- [ ] Schema + meta preserved unchanged
