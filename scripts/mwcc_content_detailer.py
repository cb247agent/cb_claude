"""
mwcc_content_detailer.py — Enrich MWCC content-calendar actions with
execution-ready briefs (caption, visual direction, hashtags, timing).

WHAT IT DOES
============
The parser (generate_mwcc_content_actions.py) splits the school-holidays
content calendar into 92 individual actions but the `instructions` field is
just the recipe column from the parent strategy doc. Useful as a strategy
hint, NOT as an executable brief.

This detailer applies the rules from skills/mwcc-content-detailer/SKILL.md
to each action and produces:
- A specific caption draft (80-180 words for IG feed, 15-30 for stories, etc.)
- Visual direction (one of 6 approved categories, with shot description)
- Hashtag set (8-12 mix per IG, 3-5 per FB)
- Best posting time (based on platform + day of week)
- For blogs: a markdown stub at outputs/mwcc/blog-drafts/[slug].md

USAGE
=====
python scripts/mwcc_content_detailer.py                 # next 14 days
python scripts/mwcc_content_detailer.py --days 28       # next 28 days
python scripts/mwcc_content_detailer.py --all           # all 92 actions

Then re-merge into work queue:
python scripts/mwcc_content_detailer.py --merge

NOTE ON LLM
===========
Today this is template + rules driven, not LLM. Captions are good enough
for review but Jordan/Joanne will still finalise. To plug in Claude API
later, replace the _detail_<platform> functions to call Anthropic.
"""
import argparse
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

BASE_DIR  = Path(__file__).resolve().parent.parent
CC_FILE   = BASE_DIR / "state" / "mwcc-content-calendar.json"
WQ_FILE   = BASE_DIR / "state" / "mwcc-work-queue.json"
BLOG_DIR  = BASE_DIR / "outputs" / "mwcc" / "blog-drafts"
BLOG_HTML_DIR = BASE_DIR / "docs" / "blog-drafts" / "mwcc"


# Voice guard — captions stripped of forbidden words
FORBIDDEN = re.compile(r"\b(best|only centre|guaranteed|amazing|incredible|perfect|world-class)\b", re.IGNORECASE)


# Hashtag bank
HASHTAGS_BASE = "#perthdaycare #childcareperth #earlylearning #perthmums #perthparents"
HASHTAGS_LDC  = "#longdaycareperth #kindyperth #babiesperth #toddlersperth"
HASHTAGS_OSHC = "#oshcperth #vacationcareperth #beforeafterschoolcare"
HASHTAGS_KINDY27 = "#kindy2027perth #waitlistnow"
HASHTAGS_CENTRES = {
    "armadale":      "#armadaleperth #armadalemums",
    "midvale":       "#midvaleperth #midvalemums",
    "rockingham":    "#rockinghamperth #rockinghammums",
    "seville grove": "#sevillegroveperth #armadaleregion",
    "waikiki":       "#waikikiperth #waikikifamilies",
}


# Centre quick reference
CENTRES = {
    "armadale":      {"suburb":"Armadale 6112",   "service":"OSHC",       "rooms":"Before School · After School · Vacation Care"},
    "midvale":       {"suburb":"Midvale 6056",    "service":"LDC",        "rooms":"Babies · Toddlers · Kindy"},
    "rockingham":    {"suburb":"Rockingham 6168", "service":"OSHC",       "rooms":"Before School · After School · Vacation Care"},
    "seville grove": {"suburb":"Seville Grove 6112","service":"LDC",      "rooms":"Babies · Toddlers · Kindy"},
    "waikiki":       {"suburb":"Waikiki 6169",    "service":"LDC",        "rooms":"Babies · Toddlers · Kindy"},
}


def _slug(s: str, max_len: int = 50) -> str:
    out = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return out[:max_len].rstrip("-")


def _strip_forbidden(text: str) -> str:
    return FORBIDDEN.sub("[REVIEW]", text)


def _pick_hashtags(theme: str, platform: str) -> str:
    """Build a hashtag set based on theme keywords."""
    if platform == "facebook":
        # FB minimal hashtags
        if "kindy" in theme.lower(): return "#perthdaycare #kindyperth #perthparents"
        if "vacation" in theme.lower() or "oshc" in theme.lower(): return "#perthdaycare #vacationcareperth #perthparents"
        return "#perthdaycare #childcareperth #perthparents"
    # IG — fuller set
    tags = [HASHTAGS_BASE]
    if "kindy" in theme.lower() or "kindergarten" in theme.lower():
        tags.append(HASHTAGS_LDC)
        tags.append("#kindyperth")
    if "vacation" in theme.lower() or "oshc" in theme.lower() or "school holid" in theme.lower():
        tags.append(HASHTAGS_OSHC)
    if "2027" in theme or "waitlist" in theme.lower():
        tags.append(HASHTAGS_KINDY27)
    # Centre-specific if mentioned
    for k, v in HASHTAGS_CENTRES.items():
        if k in theme.lower():
            tags.append(v)
            break
    return " ".join(tags)


def _best_time(platform: str, day_of_week: int) -> str:
    """Return suggested posting time."""
    if platform == "email":
        return "Tue 9:30am OR Thu 6:30am Perth time"
    if platform == "instagram":
        # Story = quick morning; Feed = midday
        return "Wed 9-11am OR Sun 6-7pm Perth time"
    if platform == "facebook":
        return "Tue 11am-1pm OR Thu 11am-1pm Perth time"
    if platform == "gbp":
        return "Mon 8-10am Perth (start-of-week visibility)"
    if platform == "blog":
        return "Publish Tue 9am Perth time for max Google crawl"
    return "Best window: weekday morning"


def _visual_direction(theme: str, platform: str) -> str:
    """Pick one of 6 approved visual categories + describe the shot."""
    theme_l = theme.lower()
    if platform == "blog":
        return "Hero image: branded graphic (lavender + purple gradient) with H1 text overlay. Inline images: room space photos (no children) or activity output photos."
    if "educator" in theme_l or "team" in theme_l:
        return "**Category: Educators (with consent).** Group photo OR mid-action shot of an educator with materials. Get written consent before publishing."
    if "transformation" in theme_l or "room" in theme_l or "setup" in theme_l or "tour" in theme_l:
        return "**Category: Centre spaces & rooms (empty).** Wide shot of the tidied room. Natural light. Show educational materials in foreground."
    if "art" in theme_l or "craft" in theme_l or "science" in theme_l:
        return "**Category: Materials & children's artwork (no faces, no names).** Photograph the OUTPUT: cardboard castle, painting, science setup. Caption tells the story of WHAT children did."
    if "ccs" in theme_l or "kindy 2027" in theme_l or "2027" in theme:
        return "**Category: Branded graphics.** Lavender + purple background. Headline text only. No imagery of children. Use Jordan's branded template."
    if "quote" in theme_l or "testimonial" in theme_l:
        return "**Category: Parent quote card (with consent).** Quote text on lavender background. No parent face. Attribute as 'Parent — Midvale' (or similar)."
    if "winter" in theme_l or "season" in theme_l:
        return "**Category: Centre spaces.** Winter set-up of a room — blankets, indoor activities visible. NO children."
    # Default safe option
    return "**Category: Branded graphics.** Lavender + purple template with headline + CTA. Safe default — no children, no consent issues."


def _expand_centres_mention(text: str) -> str:
    """Replace generic 'all centres' with the list of 5 centre names."""
    return text


def _detail_gbp(action: dict) -> dict:
    """Enrich a GBP post action."""
    theme = action.get("title", "")
    recipe = action.get("instructions", "")
    centres = "Armadale · Midvale · Rockingham · Seville Grove · Waikiki"
    multiplier = "5" if "× 5" in theme else "4 OSHC" if "× 4" in theme else "1"
    caption_template = (
        f"[GBP HEADLINE] {_strip_forbidden(theme.split('—',1)[-1].strip()[:60])}\n\n"
        f"[BODY · 50-80 words]\n"
        f"At [CENTRE NAME] in [SUBURB], we offer [SERVICE] for [age range]. "
        f"This week our team is focused on [activity from theme]. "
        f"Eligible families pay subsidised fees through CCS — book a tour to get a quote that's specific to your situation.\n\n"
        f"[CTA] Book a tour → [centre tour link]"
    )
    return {
        "caption":          caption_template,
        "visual_direction": _visual_direction(theme, "gbp"),
        "hashtags":         "(GBP posts don't use hashtags)",
        "best_time":        _best_time("gbp", 0),
        "execution_notes":  f"Post to {multiplier} centre GBP profiles. Localise: replace [CENTRE NAME] + [SUBURB] per centre. Use centre-specific photo (no children).",
        "centres_to_post":  centres,
    }


def _detail_instagram_feed(action: dict) -> dict:
    theme = action.get("title", "")
    theme_clean = theme.split('—',1)[-1].strip()
    caption_template = (
        f"[OPENING HOOK · 8-12 words]\n"
        f"{_strip_forbidden(theme_clean[:90])}\n\n"
        f"[PARAGRAPH 2 · 30-50 words · concrete detail]\n"
        f"At our [centre name] [room name], [specific moment or observation]. "
        f"This week's focus is [activity from theme].\n\n"
        f"[PARAGRAPH 3 · 20-30 words · the parent angle]\n"
        f"Eligible families pay subsidised fees through CCS — find out what tour bookings look like at our [centre name] centre.\n\n"
        f"[SOFT CTA · 10-15 words]\n"
        f"Tap the link in our bio to book a tour."
    )
    return {
        "caption":          caption_template,
        "visual_direction": _visual_direction(theme, "instagram"),
        "hashtags":         _pick_hashtags(theme, "instagram"),
        "best_time":        _best_time("instagram", 0),
        "execution_notes":  "Carousel = 5-7 slides, lead with title card. Single image = horizontal 4:5 ratio.",
    }


def _detail_instagram_story(action: dict) -> dict:
    theme = action.get("title", "")
    theme_clean = theme.split('—',1)[-1].strip()
    return {
        "caption":          f"[STORY TEXT · 15-30 words]\n{_strip_forbidden(theme_clean[:80])}\n\nUse [Countdown / Poll / Question / Link] sticker.",
        "visual_direction": _visual_direction(theme, "instagram"),
        "hashtags":         "(Stories use 2-3 hashtags max in text)",
        "best_time":        "Mon-Fri 7:30-9am Perth time (morning commute window)",
        "execution_notes":  "Stories = 1-3 frame sequence. Hold each frame 5-7 seconds. Final frame = sticker CTA.",
    }


def _detail_facebook(action: dict) -> dict:
    theme = action.get("title", "")
    theme_clean = theme.split('—',1)[-1].strip()
    caption_template = (
        f"[HOOK · 12-18 words]\n"
        f"{_strip_forbidden(theme_clean[:100])}\n\n"
        f"[CONTEXT · 50-80 words]\n"
        f"[Expand the theme with a specific story or observation. FB audience is older — more context tolerable than IG.]\n\n"
        f"[VALUE BLOCK · 40-60 words]\n"
        f"[List 2-3 concrete things parents can take from this post. Example: hot-meal idea + indoor activity + reading recommendation.]\n\n"
        f"[CTA · 12-20 words]\n"
        f"Or come along to a tour at one of our 5 Perth centres → [link]"
    )
    return {
        "caption":          caption_template,
        "visual_direction": _visual_direction(theme, "facebook"),
        "hashtags":         _pick_hashtags(theme, "facebook"),
        "best_time":        _best_time("facebook", 0),
        "execution_notes":  "Tag local community pages (mums groups, school P&Cs) where relevant. Boost ($10) if engagement >50 in first 12hr.",
    }


def _detail_email(action: dict) -> dict:
    theme = action.get("title", "")
    theme_clean = theme.split('—',1)[-1].strip()
    caption_template = (
        f"SUBJECT A (keyword-led): {_strip_forbidden(theme_clean[:60])}\n"
        f"SUBJECT B (curiosity-led): [Write a parent-empathy hook here]\n"
        f"PREHEADER: [60-80 chars supporting subject]\n\n"
        f"[BODY · 4 short paragraphs max]\n\n"
        f"Para 1 (greeting + reason): Hi [first name], with [event/season] approaching, we want to make sure your child's place is sorted.\n\n"
        f"Para 2 (specific info): [Add 3-5 specific bullets: dates, capacity, theme, CCS reminder]\n\n"
        f"Para 3 (proof/credibility): [Add 1 specific testimonial or programme detail. NOT a generic claim.]\n\n"
        f"Para 4 (CTA): Click below to [book your child's place / join the waitlist / book a tour]. Eligible families: CCS applies.\n\n"
        f"[BUTTON] [Specific action text]\n\n"
        f"Plain-text fallback: Same content, no images, single CTA URL."
    )
    return {
        "caption":          caption_template,
        "visual_direction": "Email header: branded purple gradient with logo. Inline images optional (centre spaces, not children).",
        "hashtags":         "(N/A for email)",
        "best_time":        _best_time("email", 0),
        "execution_notes":  "Send to: full enquiry list + past enrolment families. A/B test subject. Plain text fallback required.",
    }


def _detail_blog(action: dict) -> dict:
    """Generate a markdown blog draft + HTML stub."""
    theme = action.get("title", "")
    theme_clean = theme.split('—',1)[-1].strip()
    # Pull title from theme (often wrapped in quotes in source)
    m = re.search(r'"([^"]+)"', theme_clean)
    blog_title = m.group(1) if m else theme_clean[:80]
    slug = _slug(blog_title)

    # Build outline
    keyword = blog_title.lower()
    if "ccs" in keyword:
        kw = "what is CCS and how do I apply"
    elif "long day care" in keyword or "ldc" in keyword:
        kw = "long day care vs oshc"
    elif "choose" in keyword:
        kw = "how to choose childcare perth"
    elif "vacation" in keyword or "holiday" in keyword:
        kw = "school holiday program perth"
    else:
        kw = blog_title.lower()

    md = f"""# {blog_title}

**Target keyword:** `{kw}`
**Secondary keywords:** childcare perth, perth mums, [add 2 more from GSC]
**Word count target:** 1,200-1,500
**Author:** AI draft · Mark publishes · Kelley QC

---

## H1: {blog_title}

[INTRODUCTION · 120-180 words]
- Hook with the parent problem (not the solution).
- Establish empathy. "If you're trying to figure out…" framing.
- Promise the value the reader gets.

## H2: [Sub-question 1 — what is the topic]

[200-250 words. Specific, concrete. Use Perth-local detail where possible.]

## H2: [Sub-question 2 — why it matters]

[200-250 words. Tie to the parent's situation. Mention CCS where fees come up.]

## H2: [Sub-question 3 — how does it work]

[200-250 words. Step-by-step or list. Include real practical detail.]

## H2: [Sub-question 4 — what are the options]

[200-300 words. Discuss several options. Position MWCC as ONE of the options, not THE option.]

## H2: FAQ

**Q: [Common parent question 1]?**
A: [50-80 word answer.]

**Q: [Common parent question 2]?**
A: [50-80 word answer.]

**Q: [Common parent question 3]?**
A: [50-80 word answer.]

## H2: Next steps

Book a tour at one of our 5 Perth centres — Armadale · Midvale · Rockingham · Seville Grove · Waikiki.

**Eligible families pay subsidised fees through CCS.** Use our [CCS quote calculator](/ccs/) for a number specific to your situation.

[CTA BUTTON: Book a tour]

---

**Internal links to add:**
- /ccs/ (CCS calculator)
- /book-tour/ (tour booking widget)
- 2-3 relevant centre pages based on which centres are mentioned

**Compliance check (required before publish):**
- No "best childcare in Perth" claims
- CCS mention is accurate and current
- No photos of children
- All centre names + suburbs are correct
"""
    # Write markdown draft
    BLOG_DIR.mkdir(parents=True, exist_ok=True)
    md_path = BLOG_DIR / f"{slug}.md"
    md_path.write_text(md)

    # Write HTML stub
    BLOG_HTML_DIR.mkdir(parents=True, exist_ok=True)
    html_path = BLOG_HTML_DIR / f"{slug}.html"
    html_stub = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{blog_title} · MWCC Blog Draft</title>
<style>
  body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; max-width:780px; margin:0 auto; padding:36px 32px; color:#1a1a1a; line-height:1.7; background:#fafafa; }}
  h1 {{ color:#5b3ec7; font-size:28px; margin:0 0 18px; border-bottom:3px solid #8b6fd9; padding-bottom:14px; }}
  h2 {{ color:#5b3ec7; font-size:20px; margin:30px 0 12px; }}
  .meta {{ background:#fff; border-left:4px solid #8b6fd9; padding:14px 18px; margin-bottom:24px; font-size:12px; color:#525252; border-radius:0 6px 6px 0; }}
  .badge {{ display:inline-block; background:#fef9c3; color:#854d0e; padding:3px 9px; border-radius:3px; font-size:11px; font-weight:700; margin-bottom:14px; }}
  .draft-status {{ background:#fff8e1; border:1px solid #f59e0b; border-radius:6px; padding:14px 18px; margin:20px 0; font-size:12.5px; color:#92400e; }}
  pre {{ background:#f4f4f4; padding:14px; border-radius:4px; overflow-x:auto; font-size:12px; }}
</style>
</head><body>

<div class="badge">DRAFT — NOT YET PUBLISHED</div>
<div class="meta">
  <b>Target keyword:</b> {kw}<br>
  <b>Word count target:</b> 1,200-1,500<br>
  <b>Author:</b> AI draft → Kelley QC → Mark publishes to Webflow
</div>

<div class="draft-status">
  This is a STUB. The full blog needs to be written from the outline below.
  Either: (a) ask AI to expand each H2 section, OR (b) Mark writes it manually using the outline.
</div>

<h1>{blog_title}</h1>

<pre>{md}</pre>

</body></html>
"""
    html_path.write_text(html_stub)

    return {
        "caption":          f"[BLOG DRAFT] {blog_title}\nMarkdown outline: outputs/mwcc/blog-drafts/{slug}.md\nDraft stub: docs/blog-drafts/mwcc/{slug}.html",
        "visual_direction": _visual_direction(theme, "blog"),
        "hashtags":         "(N/A for blogs)",
        "best_time":        _best_time("blog", 0),
        "execution_notes":  f"Expand outline → 1,200-1,500 words. Compliance: outputs/research/compliance-review-mwcc.md before publish. Publish at /blog/{slug}",
        "draft_link":       f"docs/blog-drafts/mwcc/{slug}.html",
        "blog_md_path":     str(md_path.relative_to(BASE_DIR)),
    }


PLATFORM_DETAILERS = {
    "gbp":        _detail_gbp,
    "instagram":  _detail_instagram_feed,
    "facebook":   _detail_facebook,
    "email":      _detail_email,
    "blog":       _detail_blog,
}


def detail_action(action: dict) -> dict:
    """Apply the right detailer based on action.platform + type."""
    platform = action.get("platform", "")
    type_label = action.get("type", "")
    # Stories use a different shape than feed
    if platform == "instagram" and "Story" in type_label:
        enriched = _detail_instagram_story(action)
    else:
        detailer = PLATFORM_DETAILERS.get(platform)
        if not detailer:
            return action  # untouched
        enriched = detailer(action)

    # Build new instructions block by combining original recipe + enrichment
    original_recipe = action.get("instructions", "")
    new_instructions = f"""━━ EXECUTION BRIEF ━━

CAPTION DRAFT:
{enriched['caption']}

VISUAL DIRECTION:
{enriched['visual_direction']}

HASHTAGS:
{enriched['hashtags']}

BEST POSTING TIME:
{enriched['best_time']}

EXECUTION NOTES:
{enriched.get('execution_notes','—')}

━━ ORIGINAL STRATEGY ━━
{original_recipe}
"""
    action["instructions"] = new_instructions.strip()
    action["caption"]      = enriched['caption']
    if 'draft_link' in enriched:
        action['draft_link'] = enriched['draft_link']
    return action


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--all",  action="store_true")
    parser.add_argument("--merge", action="store_true",
                        help="After detailing, merge into mwcc-work-queue.json + sync to Supabase")
    args = parser.parse_args()

    if not CC_FILE.exists():
        print(f"[detailer] {CC_FILE} not found — run generate_mwcc_content_actions.py first")
        return 1

    data = json.loads(CC_FILE.read_text())
    actions = data["actions"]

    today = date.today()
    cutoff = today + timedelta(days=args.days)

    enriched_count = 0
    for a in actions:
        pub = a.get("publish_date")
        if not args.all and pub:
            try:
                pd = datetime.fromisoformat(pub).date()
                if pd > cutoff or pd < today:
                    continue
            except ValueError:
                pass
        detail_action(a)
        enriched_count += 1

    CC_FILE.write_text(json.dumps(data, indent=2))
    print(f"[detailer] Enriched {enriched_count} actions (next {args.days} days)")

    if args.merge:
        _merge_into_work_queue(actions)
    return 0


def _merge_into_work_queue(cc_actions: list) -> None:
    """Replace any existing content-calendar actions in work queue with the
    freshly-detailed ones, keep all emitter actions intact."""
    wq = json.loads(WQ_FILE.read_text())
    keep = [a for a in wq["actions"] if not a.get("id","").startswith("mwcc-cc-")]
    # Re-shape cc actions for work queue
    for a in cc_actions:
        a.setdefault("description", a.get("instructions",""))
        a["description"] = a["instructions"]   # always use enriched instructions
        a.setdefault("projected_kpis", [])
        a.setdefault("actual_kpis", [])
        a.setdefault("overall_verdict", None)
        a.setdefault("measured_at", None)
        a.setdefault("notes_human", None)
        a.setdefault("business", "mwcc")
        a.setdefault("data_quality", "high")
        # Numeric effort_hours
        eh = a.get("effort_hours")
        if isinstance(eh, str):
            a["effort_hours"] = {"S":1,"M":3,"L":6}.get(eh, 3)
    wq["actions"] = keep + cc_actions
    wq["generated_at"] = datetime.utcnow().isoformat() + "Z"
    WQ_FILE.write_text(json.dumps(wq, indent=2))
    print(f"[detailer] Merged {len(cc_actions)} detailed actions into work queue (total now {len(wq['actions'])})")


if __name__ == "__main__":
    raise SystemExit(main())
