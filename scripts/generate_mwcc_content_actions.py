"""
generate_mwcc_content_actions.py — Split the MWCC school-holidays content
calendar (a markdown brief with per-phase day-by-day tables) into individual
work-queue actions in CB247's PLANNER_ITEMS shape.

WHY THIS EXISTS
---------------
Until 08 Jun 2026 the MWCC Work Queue had 4 mega-actions (P1/P2/P3/P4) —
each one collapsing 1-3 weeks of daily posts into a single Joanne-owned
card. Useless for execution: Joanne would open P4 and see "12-day campaign"
with no individual posts to action.

CB247 by contrast has 14 individual content items, each one ready to
execute in 5-30 min (one GBP post, one Reel, one blog, one email).

This script reads the parent strategy doc and emits one action per row of
the day-by-day phase tables. ~63 actions total across the 8-week window.

INPUT  : outputs/mwcc/content/content-calendar-school-holidays-2026.md
OUTPUT : state/mwcc-content-calendar.json   (CB247 PLANNER_ITEMS shape)

OWNERSHIP RULES (per MWCC team roster)
---------------------------------------
  EMAIL BROADCAST         → Joanne (scheduling + email tool)
  Meta retargeting / paid → Joanne
  GBP × N                 → Kelley (GBP + reviews)
  IG feed / story         → Jordan (content creative)
  FB                      → Jordan
  SEO blog                → John  (SEO writer)  + Mark (publisher)
  Mixed channels in one row → split into separate actions per platform.

DATE BASE
---------
The brief lists dates as "Mon 8 Jun" etc. We compute `day` offset from
2026-06-08 (Mon 8 Jun = day 0). Re-running the script after the window
closes will skip actions whose day is in the past — caller-controlled.
"""
import json
import re
from datetime import date, datetime
from pathlib import Path

BASE_DIR  = Path(__file__).resolve().parent.parent
SRC_FILE  = BASE_DIR / "outputs" / "mwcc" / "content" / "content-calendar-school-holidays-2026.md"
OUT_FILE  = BASE_DIR / "state" / "mwcc-content-calendar.json"

# Day 0 = Mon 8 Jun 2026 (first day of P1 Week 1)
DAY_ZERO = date(2026, 6, 8)

# Channel → (platform key, type label, owner) mapping. The owner is the
# CONTENT-EXECUTION owner (who creates / sends the asset); Joanne schedules
# IG/FB posts but the creative origin is Jordan's.
CHANNEL_MAP = {
    "EMAIL BROADCAST": ("email", "Email Broadcast", "Joanne", "Lead — Scheduling + Paid"),
    "SEO blog":        ("blog",  "SEO Blog",        "John",   "SEO writer"),
    "GBP":             ("gbp",   "GBP Post",        "Kelley", "Manager — GBP + Reviews"),
    "IG feed":         ("instagram", "Instagram Feed", "Jordan", "Content creative"),
    "IG story":        ("instagram", "Instagram Story", "Jordan", "Content creative"),
    "IG stories":      ("instagram", "Instagram Story", "Jordan", "Content creative"),
    "FB":              ("facebook", "Facebook Post", "Jordan", "Content creative"),
}

# Month → number (for parsing "Mon 8 Jun" → date)
MONTHS = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
          "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}


def _parse_date(s: str) -> date | None:
    """Convert 'Mon 8 Jun', 'Tue 30 Jun', etc. → date(2026, m, d). Default year 2026."""
    m = re.match(r"(?:[A-Z][a-z]{2}\s+)?(\d{1,2})\s+([A-Z][a-z]{2})", s)
    if not m:
        return None
    day = int(m.group(1))
    mo  = MONTHS.get(m.group(2))
    if not mo:
        return None
    return date(2026, mo, day)


def _slugify(s: str, max_len: int = 50) -> str:
    out = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return out[:max_len].rstrip("-")


def _split_channels(channel: str) -> list[str]:
    """Split 'IG feed + FB' or 'FB + IG story' or 'GBP × 5' into atomic channels.
    Note: 'GBP × 5' stays as one channel — we represent it as a single action
    with note that 5 centres are covered (not 5 separate cards)."""
    # First strip bold markers
    channel = channel.replace("**", "").strip()
    # Strip ' × N' (we keep the multiplier as context in the title, not as separate cards)
    multiplier = ""
    mx = re.search(r"\s*×\s*\d+(?:\s+\w+)?", channel)
    if mx:
        multiplier = mx.group(0).strip()
        channel = channel[:mx.start()].strip()
    # Split on " + "
    parts = [p.strip() for p in re.split(r"\s*\+\s*", channel)]
    return parts, multiplier


def _resolve_channel(piece: str) -> tuple[str, str, str, str] | None:
    """Match a channel piece against CHANNEL_MAP. Tolerates case + minor variations."""
    p = piece.strip()
    # Direct match
    if p in CHANNEL_MAP:
        return CHANNEL_MAP[p]
    # Case-insensitive lookup with normalised whitespace
    for key, val in CHANNEL_MAP.items():
        if p.lower() == key.lower():
            return val
    # Fuzzy: handle "IG feed (all day)" etc by stripping parens
    base = re.sub(r"\s*\([^)]*\)", "", p).strip()
    for key, val in CHANNEL_MAP.items():
        if base.lower() == key.lower():
            return val
    return None


def _phase_meta(phase_num: int) -> dict:
    return {
        1: {"label": "P1 · Awareness", "code": "p1",
            "strategic_job": "Build awareness before parents search. Educate, not sell."},
        2: {"label": "P2 · Vacation Care booking push", "code": "p2",
            "strategic_job": "Convert browsers into bookers. 5-day intensity. Paid + organic in lock-step."},
        3: {"label": "P3 · During holidays", "code": "p3",
            "strategic_job": "Document the holiday experience + push LDC tours hard."},
        4: {"label": "P4 · Term 3 enrolment close", "code": "p4",
            "strategic_job": "Convert tour-bookers into enrolments. Build 2027 waitlist."},
    }.get(phase_num, {"label": f"P{phase_num}", "code": f"p{phase_num}",
                       "strategic_job": ""})


def _build_action(phase_num: int, dt: date, channel_piece: str, multiplier: str,
                   theme: str, recipe: str, seq: int) -> dict | None:
    """Build one action dict in CB247 PLANNER_ITEMS shape."""
    resolved = _resolve_channel(channel_piece)
    if not resolved:
        return None
    platform, type_label, owner, owner_role = resolved
    day_offset = (dt - DAY_ZERO).days
    phase = _phase_meta(phase_num)

    # Title — keep concise but date + channel + first 4-6 words of theme
    theme_short = re.sub(r"\*\*", "", theme).strip()
    if len(theme_short) > 70:
        theme_short = theme_short[:67].rstrip(",;.") + "…"
    multiplier_suffix = f" ({multiplier})" if multiplier else ""
    dt_label = dt.strftime("%a %d %b")
    title = f"{dt_label} · {type_label}{multiplier_suffix} — {theme_short}"

    # Caption skeleton — for text-led channels we pre-draft what the post
    # itself will say (something Joanne/Jordan/Kelley can copy/paste + tune).
    caption = _draft_caption(platform, theme_short, recipe)

    # Instructions = recipe column + multiplier context + phase context
    instructions = recipe.strip()
    if multiplier:
        instructions = f"{instructions}\n\n[Channel multiplier: {multiplier} — execute per centre.]"
    instructions = (
        f"PHASE: {phase['label']}\n"
        f"STRATEGIC JOB: {phase['strategic_job']}\n\n"
        f"{instructions}"
    )

    aid = f"mwcc-cc-{phase['code']}-d{day_offset:02d}-{platform}-{seq}"

    return {
        "id":           aid,
        "kind":         "content",
        "day":          day_offset,
        "publish_date": dt.isoformat(),
        "platform":     platform,
        "type":         type_label,
        "title":        title,
        "owner":        owner,
        "owner_role":   owner_role,
        "caption":      caption,
        "instructions": instructions,
        "phase":        phase["code"],
        "source_page":  "organic-social" if platform in ("instagram","facebook","gbp") else
                        ("enrolment" if platform == "email" else "seo-organic"),
        "category":     "organic-social" if platform in ("instagram","facebook","gbp") else
                        ("enrolment" if platform == "email" else "seo-organic"),
        "priority":     _phase_to_priority(phase_num, dt),
        "effort_hours": _estimate_effort(platform, type_label),
        "source_run_at": datetime.utcnow().isoformat() + "Z",
    }


def _phase_to_priority(phase_num: int, dt: date) -> str:
    """Items in the next 7 days get P1, next 8-21 P2, beyond P3."""
    days_out = (dt - date.today()).days
    if days_out <= 7:  return "P1"
    if days_out <= 21: return "P2"
    return "P3"


def _estimate_effort(platform: str, type_label: str) -> str:
    """Rough effort tag in CB247 S/M/L convention."""
    if platform == "blog": return "L"            # 3-5 hr draft + review
    if platform == "email": return "M"           # 1-2 hr (AI draft + send)
    if "Story" in type_label: return "S"         # 15 min
    if platform == "instagram": return "M"       # 1 hr per feed post
    if platform == "facebook": return "S"        # 30 min
    if platform == "gbp": return "M"             # 25 min for 5-centre batch
    return "S"


def _draft_caption(platform: str, theme: str, recipe: str) -> str:
    """Pull the most caption-like fragment from the recipe column.
    Look for the first quoted/inline caption hint; otherwise return a
    one-liner template based on platform + theme."""
    # Look for "Caption: ..." in recipe
    m = re.search(r"[Cc]aption[:\.]?\s*\"?([^\"\n.]{20,200})", recipe)
    if m:
        return m.group(1).strip()
    # Look for quoted phrase in recipe (the strategic line)
    m = re.search(r'"([^"]{20,200})"', recipe)
    if m:
        return m.group(1).strip()
    # Fallback template
    if platform == "email":
        return f"[Email body] {theme} — personalised by ICP. AI draft below; review before send."
    if platform == "blog":
        return f"[Blog draft] {theme}"
    return f"[{platform.upper()} caption — draft below from recipe; Jordan to finalise.]"


# ─── Main parse ──────────────────────────────────────────────────────────
def parse():
    if not SRC_FILE.exists():
        print(f"ERROR: source brief not found at {SRC_FILE}")
        return 1

    text = SRC_FILE.read_text()
    actions = []
    seq = 0

    # Find each "## N. PHASE X" block
    phase_iter = list(re.finditer(r"^## (\d+)\. PHASE (\d)", text, re.MULTILINE))
    for i, ph in enumerate(phase_iter):
        phase_num = int(ph.group(2))
        block_start = ph.end()
        block_end = phase_iter[i+1].start() if i+1 < len(phase_iter) else \
                    text.find("\n## ", block_start) if text.find("\n## ", block_start) > 0 else len(text)
        block = text[block_start:block_end]

        # Within block, find all markdown tables. Each row → row data.
        # A table starts with `| Day | Channel | Theme | Post recipe |` or similar.
        # Simple row parser: lines starting with `|` containing 3+ pipes, skipping header + separator.
        rows = []
        in_table = False
        for raw_line in block.split("\n"):
            line = raw_line.strip()
            if not line.startswith("|"):
                if in_table:
                    in_table = False
                continue
            # Skip separator lines (| --- | --- |)
            if re.match(r"\|[\s\-:|]+\|", line):
                in_table = True
                continue
            # Skip header (Day | Channel | Theme | ...)
            cols = [c.strip() for c in line.strip("|").split("|")]
            if cols and cols[0].lower() in ("day", "cadence"):
                continue
            if len(cols) < 3:
                continue
            rows.append(cols)

        # Each row → one or more actions
        for row in rows:
            day_str  = row[0]
            channel  = row[1]
            theme    = row[2] if len(row) > 2 else ""
            recipe   = row[3] if len(row) > 3 else ""

            # Skip rows that don't parse to a date (e.g., P3 Track A cadence rows
            # like "Daily 9am" — those need fanning out separately; treat as a
            # series header for now and skip from individual actions).
            dt = _parse_date(day_str)
            if not dt:
                # Daily-cadence rows from Phase 3 Track A — generate one action
                # per day for the holiday window (4-17 Jul = 14 days).
                if day_str.lower().startswith(("daily", "mon, wed, fri", "tue, thu")):
                    actions.extend(_fan_out_cadence(phase_num, day_str, channel, theme, recipe, seq))
                continue

            channels, multiplier = _split_channels(channel)
            for ch in channels:
                action = _build_action(phase_num, dt, ch, multiplier, theme, recipe, seq)
                if action:
                    actions.append(action)
                    seq += 1

    out = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "source":       str(SRC_FILE.relative_to(BASE_DIR)),
        "window":       "8 Jun – 31 Jul 2026 (school holidays)",
        "day_zero":     DAY_ZERO.isoformat(),
        "actions":      actions,
    }
    OUT_FILE.parent.mkdir(exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, indent=2))

    # Summary
    by_phase = {}
    by_owner = {}
    by_platform = {}
    for a in actions:
        by_phase[a["phase"]] = by_phase.get(a["phase"], 0) + 1
        by_owner[a["owner"]] = by_owner.get(a["owner"], 0) + 1
        by_platform[a["platform"]] = by_platform.get(a["platform"], 0) + 1
    print(f"[mwcc-cc] Wrote {OUT_FILE}")
    print(f"[mwcc-cc] Generated {len(actions)} actions")
    print(f"[mwcc-cc]   By phase:    {sorted(by_phase.items())}")
    print(f"[mwcc-cc]   By owner:    {sorted(by_owner.items())}")
    print(f"[mwcc-cc]   By platform: {sorted(by_platform.items())}")
    return 0


def _fan_out_cadence(phase_num: int, cadence: str, channel: str, theme: str,
                     recipe: str, seq_start: int) -> list[dict]:
    """Phase 3 Track A has 'Daily 9am' and 'Daily 4pm' rows — these need to
    be expanded into 14 individual actions (4 Jul – 17 Jul).
    Mon/Wed/Fri and Tue/Thu rows expand to 6 and 4 actions respectively.
    """
    holiday_dates = []
    # P3 window: 4 Jul – 17 Jul
    for d in range(4, 18):
        holiday_dates.append(date(2026, 7, d))
    weekday_filter = None
    if cadence.lower().startswith("daily"):
        weekday_filter = None
    elif "mon, wed, fri" in cadence.lower():
        weekday_filter = {0, 2, 4}
    elif "tue, thu" in cadence.lower():
        weekday_filter = {1, 3}
    out = []
    seq = seq_start
    for dt in holiday_dates:
        if weekday_filter is not None and dt.weekday() not in weekday_filter:
            continue
        channels, multiplier = _split_channels(channel)
        for ch in channels:
            a = _build_action(phase_num, dt, ch, multiplier, theme, recipe, seq)
            if a:
                out.append(a)
                seq += 1
    return out


if __name__ == "__main__":
    raise SystemExit(parse())
