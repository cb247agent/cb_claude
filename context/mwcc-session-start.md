# MWCC Session Start

## DO THIS FIRST

Read these files completely at the start of every MWCC session — in order:

1. **Switch active business to MWCC** — run `python3 scripts/set_active_business.py mwcc`
2. **This file** — project state, what's done, what's missing
3. **`CB_Brain/wiki/MWCC-Knowledge-Base.md`** — MWCC Master DOs/DON'Ts and historical learnings. Read before any content work. Contains: centre facts, compliance rules, content DOs/DON'Ts, SEO context, AD accounts, open questions.
4. **`context/mwcc-seasonal-calendar.md`** — Check:
   - What campaign or window is ACTIVE right now?
   - Is any event within 21 days? → spawn full campaign brief
   - Is any event within 60 days? → flag as prep priority

After reading all four files, confirm: **"MWCC context loaded. [Active window: X. Next event: Y in Z days.]"**

**At the end of every MWCC session:** Append new learnings to `CB_Brain/wiki/MWCC-Knowledge-Base.md` under the relevant category with today's date.

---

## PROJECT STATE — 2026-06-07

### DONE — Core architecture in parity with CB247

**Layer 1 — Data pulls (6 sources live):**
- `pull_mwcc_ga4.py` · `pull_mwcc_gsc.py` · `pull_mwcc_ads.py` (Google) · `pull_mwcc_meta.py` · `pull_mwcc_ahrefs.py` · `pull_mwcc_gbp_performance.py` (quota pending)
- OWNA Excel files (`MYWORLD_REPORT.xlsx` + `utilisation.xlsx`) — **manual drop by Tia/Kelley to `mwcc-inbox/` by Monday 12pm**

**Layer 2 — Skills (2 of 38 brand-aware):**
- `seo-landing-page-writer/SKILL.md` (full pattern — both palettes inline)
- `seo-blog-generator/SKILL.md` (lean pattern — points to brand contract)
- Other 36 skills default to CB247 — refactor when MWCC needs them. See `skills/SKILLS_BRAND_CONTRACT.md` for the refactor pattern.

**Layer 3 — Agents (6 built):**
- `agents/mwcc/strategist-mwcc.yml` — weekly synthesis
- `agents/mwcc/research-perth-childcare.yml` — Perth market intel
- `agents/mwcc/centre-performance.yml` — per-centre narrative
- `agents/mwcc/content-brief.yml` — weekly creative brief for Jordan
- `agents/mwcc/performance-mwcc.yml` — cross-channel budget allocation for Joanne (added 7 Jun 2026, Tier 2)
- `agents/mwcc/seo-agent-mwcc.yml` — strategic SEO briefs expanding emitter actions for John (added 7 Jun 2026, Tier 2)

**Layer 4 — Emitters (4 + 1 sync):**
- `mwcc_google_ads_emitter.py` · `mwcc_meta_emitter.py` · `mwcc_seo_emitter.py` · `mwcc_enrolment_emitter.py` · `mwcc_sync_to_supabase.py`
- Compliance gate added 7 Jun 2026 — rejects banned language pre-sync

**Pipeline:**
- `scripts/weekly-report-mwcc.sh` — Monday 2pm AWST via cron (0 6 * * 1 UTC)
- `scripts/bake-mwcc-report.py` — generates HTML weekly report
- `scripts/send_mwcc_weekly_report.py` — emails report to Tia only

**Dashboard pages (13):**
Overview · SEO & Organic · Google Ads · Meta Ads · GBP · Occupancy · Enrolments · Work Queue · Performance Review · How It Works · Action Tracker (legacy) · Website · Org Social

---

### DATA STATUS (2026-06-07)

| Source | Status | How it pulls | Location |
|--------|--------|-------------|----------|
| GA4 (MWCC property 315149021) | ✅ LIVE | `pull_mwcc_ga4.py` (cb_agent@chasingbetter.com.au) | `state/mwcc-ga4.json` |
| GSC (sc-domain:myworldcc.com.au) | ✅ LIVE | `pull_mwcc_gsc.py` | `state/mwcc-gsc-data.json` |
| Google Ads (917-218-6113, manager 569-719-3495) | ✅ LIVE | `pull_mwcc_ads.py` | `state/mwcc-ads.json` |
| Meta Ads (act_2835637326727066) | ✅ LIVE | `pull_mwcc_meta.py` | `state/mwcc-meta.json` |
| Ahrefs (myworldcc.com.au) | ✅ LIVE (weekly) | `pull_mwcc_ahrefs.py` | (Ahrefs key required) |
| GBP Performance (5 centres) | ⚠️ BLOCKED | `pull_mwcc_gbp_performance.py` | quota=0 pending Google approval |
| OWNA ops (occupancy + wages + enrolment) | 🟢 MANUAL DROP | `parse_mwcc_ops.py` after file drop | `state/mwcc-ops.json` |
| Social (Metricool PDF — Seville Grove only) | 🟡 PARTIAL | `parse_mwcc_metricool_pdf.py` | `state/mwcc-social.json` |

> **To refresh all live data:** `bash scripts/weekly-report-mwcc.sh` (Monday pipeline) or invoke individual pull scripts.
> ⚠️ **GBP API quota=0** — Tia to submit quota increase via GCP Console for project chasingbetter-247. 3 APIs enabled, location IDs verified.
> ⚠️ **OWNA file drop deadline: Monday 12:00 PM Perth** — pipeline runs at 2:00 PM. If file is late, the parse step uses last week's data and flags staleness.

---

### REPORTS GENERATED

- `outputs/mwcc/content/content-calendar-school-holidays-2026.md` — **8-week school holidays content calendar** (7 Jun 2026)
- `outputs/mwcc/audit-mwcc-vs-cb247-2026-06-07.md` — **Architecture parity audit + improvement plan** (7 Jun 2026)
- HTML weekly reports — generated each Monday by `bake-mwcc-report.py`

---

### MISSING / INCOMPLETE

- **GBP API quota pending** (`pull_mwcc_gbp_performance.py` returns 429 until approved)
- **36 skills still default to CB247** — refactor lazily as MWCC needs each one (per `SKILLS_BRAND_CONTRACT.md` migration order)
- **No NQS rating tracker** — `state/mwcc-nqs-ratings.json` not yet built (deferred to Tier 2)
- **No MWCC psychology-triggers.md** — currently uses generic file (gym-flavoured)
- **No MWCC design-standards.md** — marked todo in resolution table
- **3 missing agent equivalents vs CB247** (Paid Ads · audience-intel · content-intel — non-blocking, episodic use)
- **Apify (TikTok/Reddit/Trends/FB Ads) not configured for MWCC**
- **Campaign history file not created** — `state/mwcc-campaign-history.json` not present (no campaigns ran yet)
- **Email digest single-recipient** — Tia only. Kelley + Denver paused per Tia direction (7 Jun 2026)

### LAST SESSION (2026-06-07)

- Switched active business to MWCC (brand-aware skills foundation Phase 1 shipped commit `9ecd8c7`)
- Built 8-week MWCC content calendar anchored on Term 2 school holidays (4-17 Jul)
- Ran full architecture audit MWCC vs CB247 → saved to `outputs/mwcc/audit-mwcc-vs-cb247-2026-06-07.md`
- Confirmed: OWNA ingest stays manual (Tia commits Monday 12pm drop), photo consent registry NOT needed (MWCC does NOT publish child photos)
- Tier 1 fixes shipped:
  1. ✅ Compliance gate in `mwcc_sync_to_supabase.py` (rejects "best childcare", "guaranteed", "award-winning", unverified NQS claims)
  2. ✅ This file (MWCC session start)
  3. ✅ `context/mwcc-seasonal-calendar.md`

---

## LOCKED POLICIES — DO NOT BREAK

- **NO child photos in MWCC marketing.** Locked 7 Jun 2026 by Tia. Use educators (with consent), spaces, materials, text-quote cards, or branded graphics. If any content mentions/implies child imagery, REJECT and flag for human review.
- **Email digests go to Tia only** (`tia@chasingbetter.com.au`). No Kelley / Denver / Joanne.
- **OWNA file drop deadline: Monday 12:00 PM Perth.** Pipeline runs at 2 PM. If late → parse uses last week's data + staleness flag.
- **Compliance gate is mandatory** — never bypass `compliance.py` in sync pipelines. Reject any PR that disables it.
- **Active business switch is canonical** — every MWCC session must run `set_active_business.py mwcc` first.

---

## HOW TO RUN THINGS (MWCC)

### Active business switch (every session):
```bash
python3 scripts/set_active_business.py mwcc      # MWCC mode
python3 scripts/set_active_business.py cb247     # switch back
python3 scripts/set_active_business.py           # check current
```

### Pipeline (Monday 2pm via cron):
```bash
bash scripts/weekly-report-mwcc.sh
```

### Individual emitters (if you need to re-run one):
```bash
python3 scripts/work_queue/mwcc_google_ads_emitter.py
python3 scripts/work_queue/mwcc_meta_emitter.py
python3 scripts/work_queue/mwcc_seo_emitter.py
python3 scripts/work_queue/mwcc_enrolment_emitter.py
python3 scripts/work_queue/mwcc_sync_to_supabase.py
```

### Agents (say `run [agent-name]`):
| Say this | Output | Reads |
|---|---|---|
| `run strategist-mwcc` | Weekly synthesis → `outputs/mwcc/mwcc-weekly-strategy-YYYY-MM-DD.md` | all state/mwcc-*.json + work queue |
| `run research-perth-childcare` | Perth childcare market intel → `outputs/mwcc/research/` | competitor list + web |
| `run centre-performance` | Per-centre narrative → `outputs/mwcc/research/` | state/mwcc-ops.json |
| `run content-brief` | Weekly creative brief for Jordan → `outputs/mwcc/creatives/` | strategy + calendar |
| `run performance-mwcc` | Cross-channel budget allocation for Joanne → `outputs/mwcc/budget-allocation-week-YYYY-MM-DD.md` | mwcc-ads + mwcc-meta + work queue |
| `run seo-agent-mwcc` | Strategic SEO briefs for John → `outputs/mwcc/seo/strategic-briefs-YYYY-MM-DD.md` | mwcc-gsc + work queue SEO actions + competitors |

### Skill triggers (brand-aware — runs in MWCC mode if active business = mwcc):
- `write landing page` / `build page` → `seo-landing-page-writer` (MWCC palette + voice when active)
- `write blog` / `blog post` → `seo-blog-generator`
- (other 36 skills still default to CB247 — refactor when needed)

### Extract agent actions to Work Queue:
```bash
python3 scripts/extract_agent_actions.py --business mwcc --since-days 8
```

### Email report manually:
```bash
python3 scripts/send_mwcc_weekly_report.py
```

---

## KEY FACTS — MWCC

- **Identity:** My World Childcare · myworldcc.com.au · Perth, WA · private childcare group
- **Centres (5):**
  - **Armadale** — OSHC only (Before/After School)
  - **Midvale** — LDC + OSHC (Babies, Toddlers, Kindy, Before/After School)
  - **Rockingham** — OSHC only
  - **Seville Grove** — LDC + OSHC
  - **Waikiki** — LDC only (Babies, Toddlers, Kindy)
- **Brand colour:** Lavender purple `#8B6FD9` · deep purple `#4A2F8A` · NO teal (that's CB247)
- **ICPs (4):** Working parents needing LDC · OSHC term-3 parents · CCS-aware budget-conscious · Vacation Care families
- **Top competitors:** Goodstart (national) · Nido (national premium) · Midvale Hub (local) · KindiCare + Care for Kids (aggregators)
- **CCS:** All centres CCS-approved · always include "subject to eligibility" disclaimer when discussing fees
- **Regulatory:** ACECQA / NQS / WA DGE / Federal CCS — heavier compliance than CB247
- **CTA hierarchy:** Book a tour > Join the waitlist > Get a quote > Call us > Download info pack
- **DO say:** "childcare" / "early learning" / "educators" / "children" / "centre" / "programme"
- **DON'T say:** "daycare" alone / "staff" / "kids" in formal copy / "best" / "premier" / "leading" / "guaranteed" / "award-winning" without named award
- **NO child photos in marketing** (locked 7 Jun 2026)

---

## TOKEN BUDGET

Same protocol as CB247:
- 0–60%: normal | 60–75%: summarize older context | 75–85%: use `/compact` | 85%+: STOP and run `/compact`
- If task is large: break into sub-tasks, complete and save each, use `/compact` between steps
- Keep responses concise — don't repeat what's in this file

---

*Last updated: 2026-06-07 | Update at the end of every MWCC session*
