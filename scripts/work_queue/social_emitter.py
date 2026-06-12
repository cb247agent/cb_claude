"""
social_emitter.py — emit structured Organic Social actions to state/work-queue.json.

Reads state/social-trends.json (Apify scrape of trending fitness hashtags +
top-performing posts in the niche). Note: CB247's own IG/TikTok analytics are
NOT in state/*.json, so this emitter is opportunity-driven (surface external
signals), not deficit-driven (we can't measure CB247's own cadence yet).

Two action archetypes:
  1. TREND_RIDE      — top 3 trending hashtags → CB247-branded posts that
                        ride the trend before the 14-day half-life closes
  2. CREATIVE_INSPO  — top 2 high-engagement posts in the niche → format
                        briefs (replicate the angle, not the content)

All KPIs use `qualitative_assessment` because automated engagement lookup
isn't available without IG API integration. Verdicts appear as 'pending'
in Performance Review — team writes a learnings note 14 days post-publish
to mark winner / partial_win / no_change / underperforming.

When IG/TikTok APIs are wired (Session 5d+), measurement.py can be patched
to fetch actual engagement and these actions auto-verdict like the others.

Run:
    .venv/bin/python3.13 scripts/work_queue/social_emitter.py

Writes/updates: state/work-queue.json (merges with existing actions)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Tuple

# Allow direct script run AND module import
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))         # scripts/
sys.path.insert(0, str(_HERE.parent.parent))  # repo root

from work_queue.schema import (  # noqa: E402
    WorkQueueAction,
    ProjectedKPI,
    make_action_id,
    now_iso,
    week_iso,
    to_jsonable,
)
from work_queue.baselines import (  # noqa: E402
    social_scraped_at,
    social_top_hashtags,
    social_top_posts_by_engagement,
)


BASE_DIR = _HERE.parent.parent
STATE_DIR = BASE_DIR / "state"
WORK_QUEUE_FILE = STATE_DIR / "work-queue.json"

# ── Thresholds ──────────────────────────────────────────────────────────────

TREND_RIDE_COUNT = 3        # top-3 hashtags emitted as actions
TREND_RIDE_MIN_COUNT = 8    # hashtag must appear ≥8 times in the scrape to be "trending"

CREATIVE_INSPO_COUNT = 2    # top-2 posts emitted as inspiration briefs
INSPO_MIN_ENGAGEMENT = 30   # filter post noise below this

# Generic hashtags that aren't worth a dedicated action (too broad to ride)
GENERIC_HASHTAGS = {
    "gym", "fitness", "workout", "fyp", "foryou", "instagram", "explore",
    "instagood", "love", "photooftheday", "follow", "like",
}

# ── Helpers ──────────────────────────────────────────────────────────────────


def _is_generic(hashtag: str) -> bool:
    return (hashtag or "").strip().lower() in GENERIC_HASHTAGS


def _format_post_preview(text: str, max_chars: int = 140) -> str:
    """Truncate the post text for the action description."""
    t = (text or "").strip().replace("\n", " ")
    if len(t) > max_chars:
        t = t[:max_chars - 1] + "…"
    return t


def _hashtag_label(h: str) -> str:
    """#GymMotivation style."""
    h = (h or "").strip().lstrip("#")
    if not h:
        return ""
    return "#" + h


# ── Archetype emitters ───────────────────────────────────────────────────────


def _emit_trend_ride(week: str, start_serial: int) -> Tuple[List[WorkQueueAction], int]:
    """Top trending fitness hashtags → CB247-branded posts."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    # Pull more candidates than needed in case some are filtered as generic
    candidates = social_top_hashtags(n=TREND_RIDE_COUNT * 3)
    filtered = [
        h for h in candidates
        if not _is_generic(h.get("hashtag"))
        and int(h.get("count") or 0) >= TREND_RIDE_MIN_COUNT
    ]

    for h in filtered[:TREND_RIDE_COUNT]:
        tag = h.get("hashtag") or ""
        count = int(h.get("count") or 0)
        label = _hashtag_label(tag)

        actions.append(WorkQueueAction(
            id=make_action_id("soc", week, serial),
            source_page="organic-social",
            source_run_at=ts,
            title=f"Trend-ride {label} on CB247 socials — {count} hits in this week's scrape",
            description=(
                f"Hashtag {label} appeared {count} times across this week's fitness-niche scrape — "
                f"high-signal trending content with a typical 14-day half-life. Concept a CB247-branded "
                f"post (Reel preferred) that authentically rides this trend: connect it to a real CB247 "
                f"member or moment, NOT a stock-feeling overlay. Shoot, edit, post within 5 days. "
                f"Post should use {label} as primary tag + 4–6 supporting tags ({', '.join(['#chasingbetter247', '#malaga', '#ellenbrook'])}). "
                f"After 14 days, write a 1-sentence learning in Performance Review: did engagement beat "
                f"your weekly median? Yes / no / partial — that's the verdict."
            ),
            # Joanne owns Organic Social (posting/scheduling/captions).
            # Shauna provides reusable assets via the monthly shoot day —
            # Joanne picks from the asset library and adapts copy/format.
            # (12 Jun 2026 — team role clarification, Tia direction)
            owner="Joanne",
            owner_role="Organic Social",
            priority="P2",
            effort_hours=2.5,
            category="organic-social",
            data_quality="medium",   # signal source is Apify scrape — directional, not exact
            projected_kpis=[
                ProjectedKPI(
                    metric="qualitative_assessment",
                    keyword=label,
                    delta_min=1,    # +1 = "did better than median" (qualitative scale)
                    delta_max=1,
                    measurement_window_days=14,
                    confidence="medium",
                ),
            ],
        ))
        serial += 1

    return actions, serial


def _emit_creative_inspo(week: str, start_serial: int) -> Tuple[List[WorkQueueAction], int]:
    """Top high-engagement posts → format inspiration briefs."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    posts = social_top_posts_by_engagement(
        n=CREATIVE_INSPO_COUNT,
        min_engagement=INSPO_MIN_ENGAGEMENT,
    )

    for p in posts:
        platform = (p.get("platform") or "instagram").capitalize()
        engagement = int(p.get("engagement") or 0)
        likes = int(p.get("likes") or 0)
        comments = int(p.get("comments") or 0)
        plays = int(p.get("plays") or 0)
        text_preview = _format_post_preview(p.get("text") or "")
        tags = p.get("hashtags") or []
        url = p.get("url") or "(no url)"
        tag_str = ", ".join("#" + t for t in tags[:5]) if tags else "(no hashtags)"

        actions.append(WorkQueueAction(
            id=make_action_id("soc", week, serial),
            source_page="organic-social",
            source_run_at=ts,
            title=(
                f"Adapt high-engagement {platform} format — {engagement} engagement "
                f"({likes} likes, {comments} comments)"
            ),
            description=(
                f"Top-performing fitness-niche post this week (URL: {url}). "
                f"Engagement: {likes} likes, {comments} comments, {plays} plays. "
                f"Caption excerpt: \"{text_preview}\". "
                f"Tags used: {tag_str}. "
                f"Adapt the FORMAT/ANGLE for CB247, not the content. If it's a POV reel, do CB247's "
                f"version of that POV. If it's a transformation hook, frame a CB247 member's "
                f"transformation. Don't replicate the exact caption — use the engagement structure. "
                f"After 14 days, write a 1-sentence learning: did our adapted version match or beat "
                f"the source post's engagement rate? Yes / no / partial — that's the verdict."
            ),
            # Joanne owns Organic Social (posting/scheduling/captions).
            # Shauna provides reusable assets via the monthly shoot day —
            # Joanne picks from the asset library and adapts copy/format.
            # (12 Jun 2026 — team role clarification, Tia direction)
            owner="Joanne",
            owner_role="Organic Social",
            priority="P3",
            effort_hours=3.0,
            category="organic-social",
            data_quality="medium",
            projected_kpis=[
                ProjectedKPI(
                    metric="qualitative_assessment",
                    keyword=url,        # post URL is the unique scope
                    delta_min=1,
                    delta_max=1,
                    measurement_window_days=14,
                    confidence="low",   # creative replication is inherently lower-confidence
                ),
            ],
        ))
        serial += 1

    return actions, serial


# ── Orchestration ────────────────────────────────────────────────────────────


def emit_all_social_actions() -> List[WorkQueueAction]:
    scraped = social_scraped_at()
    if not scraped:
        print("[social-emitter] no social-trends.json data — exiting")
        return []

    week = week_iso()
    serial = 1

    trend,    serial = _emit_trend_ride(week, serial)
    inspo,    serial = _emit_creative_inspo(week, serial)

    return trend + inspo


def merge_with_existing(new_actions: List[WorkQueueAction]) -> dict:
    """Merge into state/work-queue.json without overwriting existing IDs.
    Action IDs are week-scoped so re-running in the same week is idempotent."""
    if WORK_QUEUE_FILE.exists():
        try:
            existing = json.loads(WORK_QUEUE_FILE.read_text())
        except Exception:
            existing = {}
    else:
        existing = {}

    existing_actions = existing.get("actions", []) or []
    existing_ids = {a.get("id") for a in existing_actions if a.get("id")}

    merged = list(existing_actions)
    added = 0
    for a in new_actions:
        d = to_jsonable(a)
        if d["id"] not in existing_ids:
            merged.append(d)
            existing_ids.add(d["id"])
            added += 1

    return {
        "generated_at": now_iso(),
        "generator_version": "1.4.0",   # bumped for Session 5d
        "actions": merged,
        "_added_this_run": added,
    }


def main():
    print(f"\n=== Organic Social Work Queue Emitter — {now_iso()} ===")

    scraped = social_scraped_at()
    if scraped:
        print(f"Source: state/social-trends.json scraped {scraped}")

    top_tags = social_top_hashtags(n=10)
    print("\nTop 10 hashtags this week (pre-filter):")
    for t in top_tags:
        marker = " (generic — skipped)" if _is_generic(t.get("hashtag")) else ""
        print(f"  #{t.get('hashtag'):25s} count={t.get('count')}{marker}")

    actions = emit_all_social_actions()
    print(f"\nGenerated {len(actions)} candidate organic social actions for week {week_iso()}")

    # Validate
    all_errors = []
    for a in actions:
        for err in a.validate():
            all_errors.append(f"{a.id}: {err}")
    if all_errors:
        print(f"\nVALIDATION ERRORS ({len(all_errors)}):")
        for e in all_errors:
            print(f"  - {e}")
        sys.exit(1)
    print("All actions validate clean.\n")

    # Preview
    by_priority = {"P1": [], "P2": [], "P3": []}
    for a in actions:
        by_priority[a.priority].append(a)
    for p in ("P1", "P2", "P3"):
        items = by_priority[p]
        if not items:
            continue
        print(f"--- {p} ({len(items)}) ---")
        for a in items:
            primary = a.projected_kpis[0]
            print(f"  - {a.title}")
            print(f"      → {primary.metric} (window {primary.measurement_window_days}d)")
        print()

    # Merge + write
    STATE_DIR.mkdir(exist_ok=True)
    merged = merge_with_existing(actions)
    WORK_QUEUE_FILE.write_text(json.dumps(merged, indent=2, default=str))
    print(
        f"[social-emitter] {merged['_added_this_run']} new + "
        f"{len(merged['actions']) - merged['_added_this_run']} existing = "
        f"{len(merged['actions'])} total actions in {WORK_QUEUE_FILE}"
    )


if __name__ == "__main__":
    main()
