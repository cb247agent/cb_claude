# MWCC SEO Targets

**Read this when generating SEO landing pages, blog briefs, or keyword research for My World Childcare.**

For business context, see `context/mwcc-brand-context.md`. For competitors, see `context/mwcc-competitors.md`.

---

## Domain

- **Website:** `myworldcc.com.au`
- **Live status:** confirmed via GA4 + GSC
- **Local pack target:** all 5 centres for their suburb's main query

---

## Primary keyword targets — per centre

For each centre, the top 5 commercial-intent keywords (highest priority):

### Armadale (OSHC only)
1. `oshc armadale`
2. `before school care armadale`
3. `after school care armadale`
4. `vacation care armadale`
5. `before and after school care armadale`

### Midvale (LDC + OSHC + Midland)
1. `childcare midvale`
2. `long day care midvale`
3. `oshc midvale`
4. `childcare midland`
5. `early learning midvale`

### Rockingham (OSHC only)
1. `oshc rockingham`
2. `before school care rockingham`
3. `after school care rockingham`
4. `vacation care rockingham`
5. `school holiday program rockingham`

### Seville Grove (LDC + OSHC)
1. `childcare seville grove`
2. `long day care seville grove`
3. `oshc seville grove`
4. `early learning seville grove`
5. `daycare seville grove`

### Waikiki (LDC only)
1. `childcare waikiki`
2. `long day care waikiki`
3. `babies room waikiki`
4. `early learning waikiki`
5. `kindy waikiki`

---

## Secondary keyword targets — group-level

These don't have a single centre — drive traffic to the homepage or service hub pages:

| Keyword | Search intent | Target page |
|---|---|---|
| `childcare perth` | Discovery | Homepage |
| `oshc perth` | Discovery — OSHC service hub | `/oshc/` |
| `long day care perth` | Discovery — LDC service hub | `/long-day-care/` |
| `vacation care perth` | Seasonal (Apr/Jul/Oct/Dec) | `/vacation-care/` |
| `childcare with CCS` | Subsidy-aware discovery | `/ccs/` |
| `CCS approved childcare perth` | Same as above, variant | `/ccs/` |
| `early learning perth` | LDC umbrella term | `/early-learning/` |
| `nqs rated childcare perth` | Quality-conscious | `/nqs/` |
| `childcare near me` | Location-aware mobile | Homepage with location-targeted ads |
| `daycare perth` | Informal variant | Homepage |
| `before and after school care perth` | OSHC group-level | `/oshc/` |
| `school holiday program perth` | Vacation Care variant | `/vacation-care/` |

---

## Long-tail content targets (blog briefs)

Content marketing keywords — long-tail, informational intent. Each one is a blog post topic.

**Parent education topics (highest volume):**
- "what is CCS and how do I apply"
- "what age can my child start daycare in WA"
- "long day care vs family day care"
- "what is the NQS rating system"
- "childcare subsidy calculator WA"

**Local guides (suburb + topic):**
- "best childcare in [suburb]" — review of multiple options including MWCC
- "how to choose childcare in [suburb]"
- "schools near [centre suburb] with OSHC"

**Operational topics (low volume but high conversion):**
- "what to pack for childcare first day"
- "settling your child into daycare"
- "transitioning from baby room to toddler room"

---

## Competitor keyword overlap (where we compete)

| Keyword | Currently ranking | Top competitor | Our position |
|---|---|---|---|
| `childcare armadale` | Yes — need GSC pull to confirm pos | Goodstart Armadale | TBD |
| `oshc perth` | Variable | Camp Australia | TBD |
| `long day care perth` | Variable | Goodstart | TBD |
| `childcare with CCS` | Generic high volume | Care for Kids, KindiCare | Below pos 20 |

**Where MWCC has unique opportunity** (competitors don't bid consistently):
- `vacation care [suburb]` — seasonal demand, competitors often miss
- `CCS approved childcare perth` — subsidy-aware parents, lower competition
- "early learning [suburb]" — premium positioning, less commercial than "daycare"

---

## URL structure conventions

| Page type | URL pattern | Example |
|---|---|---|
| Centre landing | `/centres/[suburb]/` | `/centres/armadale/` |
| Service hub | `/[service]/` | `/oshc/`, `/long-day-care/`, `/vacation-care/` |
| Centre + service combo | `/centres/[suburb]/[service]/` | `/centres/midvale/oshc/` |
| Topical content | `/blog/[slug]/` | `/blog/what-is-ccs/` |
| Local guide | `/[suburb]-childcare-guide/` | `/armadale-childcare-guide/` |

URLs should be lowercase, hyphen-separated, no trailing slash on file paths (trailing slash OK on directories).

---

## Schema markup priorities

| Page | Schema |
|---|---|
| Centre landing | `LocalBusiness` + `EarlyChildhoodEducation` + address + opening hours + reviews |
| Service hub | `Service` + `offers` |
| Blog | `Article` + author + publish date |
| Homepage | `Organization` + `EarlyChildhoodEducation` |

---

## Technical SEO baseline (must-do per page)

- **Title tag** — 50-60 chars · includes primary keyword · ends with " | My World Childcare"
- **Meta description** — 130-155 chars · includes CTA ("Book a tour", "Get a quote") · mentions CCS if fee-relevant
- **H1** — One per page · primary keyword · includes suburb if local
- **First paragraph** — Primary keyword in first 100 words · answers searcher intent immediately
- **Internal links** — Centre pages link to relevant service hubs · service hubs link to all relevant centres
- **Image alt text** — Descriptive · includes centre name when relevant
- **Mobile-first** — All pages must pass Google's mobile-friendly check
- **Page speed** — LCP <2.5s · CLS <0.1 (run PageSpeed Insights monthly)
