"""
generate_monthly_shoot_pack.py — Aggregate one month of creative actions
into ONE shoot-day pack for Shauna (CB247 Assets Creator).

WHY THIS EXISTS
    Shauna only works one shoot day per month. Per-action briefs are great
    for the dashboard (one-tap "View Brief" for Tia + Brand Manager), but
    Shauna needs a single document that captures EVERYTHING she has to
    shoot for the next 30 days — sorted by location, deduped by setup,
    with all the angles, viral references, and Higgsfield fallbacks in one
    place.

    Per Tia direction (12 Jun 2026, "hybrid please"): per-action briefs
    keep working for the team's daily workflow, and this monthly pack is
    Shauna's deliverable.

OUTPUT
    outputs/asset-library/shoot-pack-YYYY-MM.md

TRIGGER
    First Monday of each month (wired into phase1_data.sh). Re-running
    mid-month is safe — it overwrites with the current snapshot.

USAGE
    python scripts/generate_monthly_shoot_pack.py
    python scripts/generate_monthly_shoot_pack.py --month 2026-07  # specific
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date as _date
from pathlib import Path

BASE_DIR  = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
# Write into docs/ so GitHub Pages serves it. The dashboard's Asset
# Library card links to asset-library/shoot-pack-YYYY-MM.md relative
# to docs/index.html. Earlier write to outputs/asset-library/ 404'd
# because Pages only serves files inside docs/.
OUTPUT_DIR = BASE_DIR / "docs" / "asset-library"

sys.path.insert(0, str(BASE_DIR / "scripts"))
from work_queue.build_creative_brief_context import build_context  # noqa: E402

# Reuse the same creative detector from generate_briefs.py so per-action
# briefs and the shoot pack agree on which actions Shauna owns. We import
# rather than copy so the rule stays in one place.
from generate_briefs import _is_creative_action  # noqa: E402


def _shoot_day_for_month(month_iso: str) -> str:
    """Recommend the LAST FRIDAY of the month as shoot day.
    Per Tia direction — first Monday is when we plan, last Friday is when
    Shauna actually shoots. Gives 3-4 weeks notice.
    """
    y, m = (int(x) for x in month_iso.split("-"))
    # Find last day of month
    if m == 12:
        next_first = _date(y + 1, 1, 1)
    else:
        next_first = _date(y, m + 1, 1)
    from datetime import timedelta
    last_day = next_first - timedelta(days=1)
    # Walk backwards to Friday (weekday=4)
    while last_day.weekday() != 4:
        last_day -= timedelta(days=1)
    return last_day.isoformat()


def _location_of(action: dict) -> str:
    """Bucket actions by location for grouping. Shauna can batch all
    Malaga shots in the morning, Ellenbrook after lunch."""
    title = (action.get("title") or "").lower()
    desc  = (action.get("description") or "").lower()
    if "malaga" in title or "malaga" in desc:        return "Malaga"
    if "ellenbrook" in title or "ellenbrook" in desc: return "Ellenbrook"
    return "Both / Either"


def _category_of(action: dict) -> str:
    """For sub-grouping within a location section. Shauna can knock out
    all GBP photos as one batch, then move to socials, etc."""
    cat = (action.get("category") or action.get("source_page") or "other").lower()
    if "gbp" in cat:                       return "GBP Photos"
    if "meta" in cat:                      return "Meta Ad Creative"
    if "social" in cat or "organic" in cat: return "Organic Social"
    return "Other"


def _pending(action: dict) -> bool:
    """A creative action is shootable if it's NOT already published or
    rejected. Verdicts approved-with-adjustments still shoot."""
    status = (action.get("planner_status") or action.get("status") or "").lower()
    return status not in ("published", "rejected", "scheduled")


def _filter_creative_pending(actions: list) -> list:
    """Apply the same _is_creative_action() rule + status filter."""
    return [a for a in actions if _is_creative_action(a) and _pending(a)]


# ─── markdown helpers ────────────────────────────────────────────────────
def _md_table(rows: list, headers: list) -> str:
    if not rows:
        return "_No data._"
    sep = "|" + "|".join("---" for _ in headers) + "|"
    head = "| " + " | ".join(headers) + " |"
    body = "\n".join("| " + " | ".join(str(r.get(h.lower().replace(" ", "_"), "")) for h in headers) + " |" for r in rows)
    return f"{head}\n{sep}\n{body}"


def _section_winners(winners: list) -> str:
    if not winners:
        return "_No standout winners last week — shoot pack is forward-looking only._"
    rows = []
    for w in winners:
        rows.append(
            f"- **{w['name']}** ({w['location']}) — CTR **{w['ctr']}%**, spend ${w['spend']}, format: {w['format']}"
        )
    return "\n".join(rows)


def _section_viral(viral: dict) -> str:
    parts = []
    hashtags = viral.get("trending_hashtags") or []
    if hashtags:
        ht = ", ".join(f"#{h.get('hashtag')} ({h.get('count')})" for h in hashtags[:8])
        parts.append(f"**Trending hashtags this week:** {ht}")
    posts = viral.get("top_posts") or []
    if posts:
        parts.append("\n**Top viral posts (worth mirroring the angle):**")
        for p in posts[:5]:
            txt = (p.get("text") or "")[:200].replace("\n", " ")
            plat = p.get("platform") or "—"
            eng = p.get("engagement") or p.get("plays") or p.get("likes") or 0
            parts.append(f"- [{plat}] {txt}… _({eng:,} eng)_")
    fb = viral.get("competitor_fb_ads") or []
    if fb:
        parts.append("\n**Competitor FB ads running (defensive watch — DO NOT name them in copy):**")
        for ad in fb[:5]:
            body = (ad.get("body") or "")[:200].replace("\n", " ")
            page = ad.get("page") or "—"
            parts.append(f"- **{page}:** {body}…")
    return "\n".join(parts) if parts else "_No viral signals captured this week._"


def _section_inventory(inv: list) -> str:
    if not inv:
        return "_No on-hand images detected._"
    rows = ["- `{relpath}` — {size_kb} KB".format(**i) for i in inv]
    return "\n".join(rows)


def _section_higgsfield(suggestions: list) -> str:
    if not suggestions:
        return "_No specific fallback prompts — shoot in-club._"
    out = []
    for s in suggestions:
        out.append(f"### {s.get('shot')}\n```\n{s.get('prompt')}\n```")
    return "\n\n".join(out)


def _section_action(a: dict) -> str:
    """Render ONE creative action as a sub-section of the shoot pack."""
    aid = a.get("id", "")
    title = a.get("title", "Untitled")
    desc  = a.get("description", "(no description)")
    pri   = a.get("priority", "P3")
    effort = a.get("effort_hours", "—")
    pks = a.get("projected_kpis") or []
    kpi_line = ""
    if pks:
        k = pks[0]
        kpi_line = f"- **Projected KPI:** {k.get('metric')}: {k.get('baseline','?')} → **{k.get('target','?')}** ({k.get('measurement_window_days', 14)}d)"
    # Per-action Higgsfield fallback (built fresh against THIS action)
    try:
        ctx = build_context(a)
        higgs = ctx.get("higgsfield_suggestions") or []
    except Exception:
        higgs = []
    higgs_md = ""
    if higgs:
        higgs_md = "\n**Higgsfield fallback if not shootable in-club:**\n" + _section_higgsfield(higgs)

    return f"""### {pri} · {title}
_Action ID: `{aid}` · Effort: {effort}h_

**Brief:** {desc}

{kpi_line}
{higgs_md}
"""


def _section_location(loc: str, actions: list) -> str:
    """Group actions under one location heading, then sub-group by category
    so Shauna can batch GBP-photo work, then move to social, etc."""
    if not actions:
        return ""
    out = [f"## Location: {loc} ({len(actions)} shot{'s' if len(actions) != 1 else ''})\n"]
    by_cat: dict[str, list] = {}
    for a in actions:
        by_cat.setdefault(_category_of(a), []).append(a)
    for cat in sorted(by_cat.keys()):
        out.append(f"\n### {cat}\n")
        for a in by_cat[cat]:
            out.append(_section_action(a))
    return "\n".join(out)


# ─── main ─────────────────────────────────────────────────────────────────
def build_pack(month_iso: str) -> str:
    wq_file = STATE_DIR / "work-queue.json"
    if not wq_file.exists():
        return f"# Shoot Pack — {month_iso}\n\n_work-queue.json not found — nothing to shoot._\n"

    wq = json.loads(wq_file.read_text())
    actions = wq.get("actions") or []
    creative_pending = _filter_creative_pending(actions)

    # Bucket by location
    by_loc: dict[str, list] = {}
    for a in creative_pending:
        by_loc.setdefault(_location_of(a), []).append(a)

    # Generic (no action-specific) context for the top of the pack
    ctx = build_context()
    winners   = ctx.get("past_winners") or []
    viral     = ctx.get("viral") or {}
    inventory = ctx.get("image_inventory") or []
    compliance = ctx.get("compliance_reminders") or []
    account_ctr = ctx.get("_account_meta_ctr")

    shoot_day = _shoot_day_for_month(month_iso)
    today = _date.today().isoformat()

    # Header
    head = f"""# CB247 Monthly Shoot Pack — {month_iso}

**Brief generated:** {today}
**Recommended shoot day:** {shoot_day}  _(last Friday of {month_iso})_
**Pending creative actions:** {len(creative_pending)}
**Locations covered:** {len(by_loc)} ({', '.join(by_loc.keys())})

---

## Shoot Day Summary

| Location | Shots | Categories |
|---|---|---|
"""
    for loc, items in by_loc.items():
        cats = sorted({_category_of(a) for a in items})
        head += f"| **{loc}** | {len(items)} | {', '.join(cats)} |\n"

    head += f"""
**Setup:** Plan to spend the morning at Malaga (typically heavier shot load), Ellenbrook after lunch. Cover GBP photos first (highest ROI per minute — 5 fresh photos lift GBP rank measurably), then Meta ad creative, then social trend-rides.

**Account-level Meta CTR baseline:** {account_ctr or '—'}%. Winning ad CTRs below.

---

## What's Working — Past Winners (Meta Ads, Last Week)

{_section_winners(winners)}

---

## Viral Signals — What to Mirror This Month

{_section_viral(viral)}

---

## Compliance — Read Before Every Shot

"""
    for c in compliance:
        head += f"- {c}\n"
    head += "\n---\n\n## On-Hand Image Inventory (reuse before reshooting)\n\n"
    head += _section_inventory(inventory)
    head += "\n\n---\n\n# Shot List — Per Location\n\n"

    # Body — per-location sections
    body = []
    for loc in sorted(by_loc.keys()):
        body.append(_section_location(loc, by_loc[loc]))

    if not body:
        body = ["_No pending creative actions found in work-queue.json. Shauna can take this month off, or use the time to refresh GBP photos at both locations._"]

    foot = """

---

## After the Shoot

1. Drop captured assets into `Image/` with descriptive filenames (`<location>_<scene>_<date>.jpg`)
2. Tag Tia in Slack with the asset folder link
3. Tia uses the per-action briefs in the dashboard (View Brief) to match raw assets to action IDs
4. Brand Manager QCs the deliverables in the Work Queue kanban

## After 14 Days

The measurement runner auto-checks each action's projected KPI on day 14. Verdict (Win / Mixed / Loss) appears on the Performance Review page. Wins inform next month's shoot pack — the winning angles get shot again with variations.

---

_Generated by `scripts/generate_monthly_shoot_pack.py` (CB247 Marketing OS)._
"""

    return head + "\n".join(body) + foot


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--month", default=_date.today().strftime("%Y-%m"),
                   help="Month to plan for (YYYY-MM). Default: this month.")
    args = p.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"shoot-pack-{args.month}.md"
    pack = build_pack(args.month)
    out_path.write_text(pack, encoding="utf-8")
    print(f"[shoot-pack] Wrote {out_path.relative_to(BASE_DIR)} ({len(pack):,} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
