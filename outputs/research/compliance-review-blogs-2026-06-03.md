# Compliance Review: Blog Drafts — Ads-to-Organic Series
**Date:** 2026-06-03 | **Reviewer:** Claude Code (CB247 Marketing OS)

---

## Blogs Reviewed
1. `docs/blog-drafts/best-gym-malaga.html` — Best Gym Malaga
2. `docs/blog-drafts/fifo-gym-membership-perth.html` — FIFO Gym Membership Perth
3. `docs/blog-drafts/gym-ellenbrook-perth.html` — Best Gym Ellenbrook
4. `docs/blog-drafts/reformer-pilates-malaga.html` — Reformer Pilates Malaga

---

## Overall Compliance Status

| Check | Blog 1 — Malaga | Blog 2 — FIFO | Blog 3 — Ellenbrook | Blog 4 — Pilates |
|-------|----------------|--------------|---------------------|-----------------|
| AANA Code of Ethics | ⚠️ REVIEW | ⚠️ REVIEW | ✅ PASS | ⚠️ REVIEW |
| ACL Truth in Advertising | ❌ FIX | ❌ FIX | ✅ PASS | ⚠️ REVIEW |
| Therapeutic Claims (TGA) | ✅ PASS | ⚠️ REVIEW | ✅ PASS | ⚠️ REVIEW |
| Membership Pricing Rules | ✅ PASS | ✅ PASS | ✅ PASS | ✅ PASS |
| Scientific Citations | ✅ PASS | ✅ PASS | ✅ PASS | ⚠️ REVIEW |
| Doctor/Safety Disclaimer | ❌ MISSING | ❌ MISSING | ❌ MISSING | ❌ MISSING |
| Privacy/Spam Act | ✅ N/A | ✅ N/A | ✅ N/A | ✅ N/A |

---

## Critical Issues — Must Fix Before Publishing

### ISSUE 1 — "Unique to CB247" ice bath claim (Blog 1: best-gym-malaga.html)
**Location:** Features table — `Ice Bath ✔ Malaga (unique to CB247)`
**Regulation:** ACL s29 — False or misleading representations
**Problem:** "Unique to CB247" is a provable claim. If any other gym in Perth has an ice bath, this is false advertising under ACL. World Gym, Revo, and other facilities may have cold water immersion.
**Fix:** Change to `"One of the only gyms in Malaga with an ice bath"` or `"Ice bath included — check competitors before making this claim"`
**Status:** ❌ FIXED in blog HTML (see changes below)

---

### ISSUE 2 — "Only gym in the suburb with both" (Blog 2: fifo-gym-membership-perth.html)
**Location:** Body copy — `"CB247 Malaga has a sauna and an ice bath. It's the only gym in the suburb with both."`
**Regulation:** ACL s29 — False or misleading representations
**Problem:** Unverified "only" claim. If Ryderwear Gym Malaga or any other local gym has both, this is a breach.
**Fix:** Change to `"CB247 Malaga has a sauna and an ice bath — rare in a $11.95/week gym."`
**Status:** ❌ FIXED in blog HTML (see changes below)

---

### ISSUE 3 — Doctor/safety disclaimer missing from ALL 4 blogs
**Location:** All blogs — none include a fitness safety disclaimer
**Regulation:** AANA Code Section 6 — Safety; industry standard for fitness content
**Problem:** All 4 blogs describe exercises, training routines, or fitness benefits without the standard disclaimer required for fitness content in Australia.
**Fix:** Add to the footer of every blog: `"Always consult your doctor or healthcare professional before starting any new fitness or exercise program."`
**Status:** ❌ FIXED in all 4 blog HTML files (see changes below)

---

## Warnings — Should Fix Before Publishing

### WARNING 1 — Unverified competitor pricing (Blog 4: reformer-pilates-malaga.html)
**Location:** `"Most dedicated Pilates studios charge $25–$40 per class"`
**Regulation:** ACL s29 — competitor comparisons must be accurate
**Problem:** No source cited for this price range. If studios in Perth charge differently, this is misleading.
**Fix:** Add `[verify — check local Perth Pilates studio pricing before publishing]` or replace with `"Many dedicated Pilates studios charge a per-class fee on top of any membership."`
**Status:** ⚠️ FLAGGED in blog HTML

---

### WARNING 2 — Pilates blog implies study applies to Reformer Pilates (Blog 4)
**Location:** `"A 2022 review in the BJSM (Momma et al.) confirmed that even moderate resistance training... is associated with a 10–20% reduction in all-cause mortality risk. Low impact, high return. The reformer format delivers this consistently."`
**Regulation:** AANA Truth and Accuracy — implied misleading connection
**Problem:** Momma et al. studied muscle-strengthening activities broadly — not Reformer Pilates specifically. Saying "the reformer format delivers this consistently" implies the study validates Reformer Pilates. It does not.
**Fix:** Break the implied link. State the study separately, then say Reformer Pilates is a form of resistance training, not that the study proves Reformer specifically.
**Status:** ⚠️ FLAGGED in blog HTML

---

### WARNING 3 — "Post-injury" therapeutic language (Blog 4: reformer-pilates-malaga.html)
**Location:** `"It's also lower impact on joints, which makes it a good choice post-injury or during recovery phases."`
**Regulation:** TGA — therapeutic/medical claims
**Problem:** "Post-injury" comes close to a therapeutic recommendation. This implies CB247 is recommending Reformer Pilates as a treatment for injury.
**Fix:** Add qualifier: `"Some people find lower-impact training suits them during recovery — always follow advice from your physio or doctor."`
**Status:** ⚠️ FLAGGED in blog HTML

---

### WARNING 4 — Sauna mortality stat study population (Blog 2: fifo-gym-membership-perth.html)
**Location:** Laukkanen et al. 2015 sauna citation
**Note:** Blog already includes `[verify exact figures against original study before publishing]` — good. The claim is directionally accurate based on the study. No change needed beyond existing flag.
**Status:** ✅ Already flagged correctly

---

### WARNING 5 — Yorks 2017 "26% less stress" — study population context
**Location:** All 4 blogs reference this study
**Note:** The original study used medical students, not general gym populations. The claim is scientifically valid, but the population context is narrow.
**Recommendation:** When citing this stat, use: `"In a study of medical students (Yorks et al., 2017)..."` — already correctly cited in all blogs. Acceptable.
**Status:** ✅ Acceptable as cited

---

### WARNING 6 — "#hotgirlwalk 500M+ TikTok views" (Blog 4: reformer-pilates-malaga.html)
**Location:** Front matter brief section
**Problem:** View count is unverified. Not in published body copy — only in the brief section visible to internal team.
**Fix:** Mark as `[verify view count before using in any published copy]`
**Status:** ✅ Internal brief only — no action needed for publish

---

## Required Disclaimers — Add Before Publishing

All 4 blogs need the following added before WordPress publish:

1. **Doctor disclaimer** (all 4 blogs):
   > *"Always consult your doctor or healthcare professional before starting any new fitness or exercise program."*

2. **Results disclaimer** (if any results-based language added to future versions):
   > *"Results vary. Individual circumstances affect outcomes."*

3. **Membership terms** (already present in all 4 blogs via CTA blocks):
   > *"$11.95/week. No lock-in. No joining fee."* ✅

---

## Summary of Changes Made to Blog Files

| Blog | Critical Fix | Warning Flag | Disclaimer Added |
|------|-------------|-------------|-----------------|
| best-gym-malaga.html | "unique to CB247" → "one of the only" | — | Doctor disclaimer ✅ |
| fifo-gym-membership-perth.html | "only gym in suburb" → softer claim | Sauna stat already flagged ✅ | Doctor disclaimer ✅ |
| gym-ellenbrook-perth.html | No critical issues | — | Doctor disclaimer ✅ |
| reformer-pilates-malaga.html | — | Competitor pricing [verify], study link, post-injury language | Doctor disclaimer ✅ |

---

## Approval Status

**Status:** ⚠️ CONDITIONAL APPROVAL

**Conditions for publish:**
1. ✅ Critical fixes applied (done — see blog HTML changes)
2. ✅ Doctor disclaimer added to all 4 blogs (done)
3. ⚠️ Blog 4 — verify Perth Pilates studio pricing before publishing `$25–$40/class` claim
4. ⚠️ Blog 2 — verify Laukkanen sauna stat exact figures against original JAMA paper before publishing

---

*Compliance review completed by Claude Code — CB247 Marketing OS · skills/compliance-checker/SKILL.md*
*Regulations referenced: AANA Code of Ethics, ACL s29 (misleading representations), TGA therapeutic claims guidelines*
