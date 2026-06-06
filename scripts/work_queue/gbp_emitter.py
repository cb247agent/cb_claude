"""
gbp_emitter.py — emit structured GBP (Google Business Profile) actions to
state/work-queue.json.

Reads state/gbp-data.json (Apify scrape with per-location profile data +
competitor benchmarks). Note: state/gbp-performance.json (Google Business
Profile Performance API) is currently HTTP 429 quota-blocked, so engagement
metrics (website_clicks, phone_clicks) are not used yet.

Three action archetypes:
  1. REVIEW_GROWTH   — one per location, drive new review acquisition
                        (frontline review-prompt cadence, post-class, post-PT)
  2. PHOTO_REFRESH   — one per location, add fresh photos (asset creator owns)
  3. COMPETITOR_GAP  — fires only when a competitor's rating > ours AND that
                        competitor has ≥ 30 reviews (filters out small-volume
                        rating noise). Defensive review-volume push.

Run:
    .venv/bin/python3.13 scripts/work_queue/gbp_emitter.py

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
    gbp_location_full,
    gbp_review_count_for,
    gbp_photos_count_for,
    gbp_rating_for,
    gbp_top_competitor,
)


BASE_DIR = _HERE.parent.parent
STATE_DIR = BASE_DIR / "state"
WORK_QUEUE_FILE = STATE_DIR / "work-queue.json"

LOCATIONS = ("malaga", "ellenbrook")

# ── Thresholds ──────────────────────────────────────────────────────────────

# REVIEW_GROWTH — universal routine
REVIEW_GROWTH_TARGET_DELTA = 15        # +15 reviews per 28d (achievable for 8K members)
REVIEW_GROWTH_WINDOW_DAYS = 28

# PHOTO_REFRESH — universal routine
PHOTO_REFRESH_TARGET_DELTA = 5         # +5 photos per 14d
PHOTO_REFRESH_WINDOW_DAYS = 14

# COMPETITOR_GAP — only fires when competitor strictly out-rates us
COMPETITOR_MIN_REVIEWS = 30            # filter out small-volume rating noise
COMPETITOR_DEFENSIVE_TARGET = 25       # accelerated push when behind
COMPETITOR_WINDOW_DAYS = 28


# ── Helpers ──────────────────────────────────────────────────────────────────


def _display_location(loc: str) -> str:
    return loc.capitalize()


# ── Archetype emitters ───────────────────────────────────────────────────────


def _emit_review_growth(loc: str, week: str, start_serial: int) -> Tuple[List[WorkQueueAction], int]:
    """One REVIEW_GROWTH action per location."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    baseline = gbp_review_count_for(loc)
    if baseline is None:
        return actions, serial

    rating = gbp_rating_for(loc)
    display = _display_location(loc)
    target = baseline + REVIEW_GROWTH_TARGET_DELTA

    actions.append(WorkQueueAction(
        id=make_action_id("gbp", week, serial),
        source_page="gbp",
        source_run_at=ts,
        title=f"Drive review growth at {display} — {baseline} reviews, {rating} stars",
        description=(
            f"{display} sits at {baseline} reviews ({rating} stars). Compounding new "
            f"reviews keeps recency signals strong in Google's local algorithm and dilutes "
            f"any single 1-star outlier. Frontline cadence: trainers ask post-PT, reception "
            f"prompts post-class with the GBP review QR card, follow-up SMS 24h after first "
            f"visit. Target: +{REVIEW_GROWTH_TARGET_DELTA} new reviews in "
            f"{REVIEW_GROWTH_WINDOW_DAYS} days."
        ),
        owner="Tia",
        owner_role="OS Owner / Operations",
        priority="P2",
        effort_hours=2.0,
        category="gbp",
        data_quality="high",
        projected_kpis=[
            ProjectedKPI(
                metric="gbp_reviews_count",
                keyword=loc,
                baseline=baseline,
                target=float(target),
                measurement_window_days=REVIEW_GROWTH_WINDOW_DAYS,
                confidence="medium",
            ),
        ],
    ))
    serial += 1

    return actions, serial


def _emit_photo_refresh(loc: str, week: str, start_serial: int) -> Tuple[List[WorkQueueAction], int]:
    """One PHOTO_REFRESH action per location."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    baseline = gbp_photos_count_for(loc)
    if baseline is None:
        return actions, serial

    display = _display_location(loc)
    target = baseline + PHOTO_REFRESH_TARGET_DELTA

    actions.append(WorkQueueAction(
        id=make_action_id("gbp", week, serial),
        source_page="gbp",
        source_run_at=ts,
        title=f"Refresh GBP photos at {display} — {baseline} photos, +{PHOTO_REFRESH_TARGET_DELTA} target",
        description=(
            f"{display} GBP currently shows {baseline} photos. Fresh photo uploads signal an "
            f"active business to Google and lift listing engagement. Capture and upload 5 new "
            f"shots — facility detail (sauna, ice bath, Kids Hub), a class in session, a recent "
            f"transformation, and one exterior daytime shot for fresh map-pin imagery. "
            f"Upload via the Google Business Profile app. "
            f"Target: {target} photos in {PHOTO_REFRESH_WINDOW_DAYS} days."
        ),
        owner="Shauna",
        owner_role="Asset Creator (CB247)",
        priority="P3",
        effort_hours=1.5,
        category="gbp",
        data_quality="high",
        projected_kpis=[
            ProjectedKPI(
                metric="gbp_photos_count",
                keyword=loc,
                baseline=baseline,
                target=float(target),
                measurement_window_days=PHOTO_REFRESH_WINDOW_DAYS,
                confidence="high",
            ),
        ],
    ))
    serial += 1

    return actions, serial


def _emit_competitor_gap(loc: str, week: str, start_serial: int) -> Tuple[List[WorkQueueAction], int]:
    """COMPETITOR_GAP fires only when a competitor strictly out-rates CB247
    at this location (with ≥30 reviews for signal)."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    our_rating = gbp_rating_for(loc)
    our_reviews = gbp_review_count_for(loc)
    if our_rating is None or our_reviews is None:
        return actions, serial

    top_competitor = gbp_top_competitor(loc, min_reviews=COMPETITOR_MIN_REVIEWS)
    if not top_competitor:
        return actions, serial

    comp_rating = float(top_competitor.get("rating") or 0)
    if comp_rating <= our_rating:
        return actions, serial  # we lead or tie — no defensive action needed

    comp_name = top_competitor.get("name") or "competitor"
    comp_reviews = int(top_competitor.get("reviews") or 0)
    display = _display_location(loc)
    target = our_reviews + COMPETITOR_DEFENSIVE_TARGET

    actions.append(WorkQueueAction(
        id=make_action_id("gbp", week, serial),
        source_page="gbp",
        source_run_at=ts,
        title=(
            f"Close GBP rating gap at {display} — {comp_name} {comp_rating} stars "
            f"vs CB247 {our_rating}"
        ),
        description=(
            f"{comp_name} is rated {comp_rating} stars ({comp_reviews} reviews) at {display}, "
            f"strictly above CB247 at {our_rating} ({our_reviews} reviews). Sustained gap risks "
            f"losing local-pack tiebreakers and intent-driven foot traffic to a higher-rated "
            f"alternative. Accelerate review acquisition: weekend front-desk push, SMS to "
            f"members hitting 30-day attendance milestone, hand-trained PTs personally asking "
            f"top clients. Volume of new 5-star reviews dilutes older mid-rating reviews and "
            f"lifts the average. Target: +{COMPETITOR_DEFENSIVE_TARGET} new reviews in "
            f"{COMPETITOR_WINDOW_DAYS} days (faster than routine REVIEW_GROWTH cadence)."
        ),
        owner="Tia",
        owner_role="OS Owner / Operations",
        priority="P1",
        effort_hours=3.0,
        category="gbp",
        data_quality="high",
        projected_kpis=[
            ProjectedKPI(
                metric="gbp_reviews_count",
                keyword=loc,
                baseline=our_reviews,
                target=float(target),
                measurement_window_days=COMPETITOR_WINDOW_DAYS,
                confidence="medium",
            ),
            ProjectedKPI(
                metric="gbp_rating",
                keyword=loc,
                baseline=round(our_rating, 2),
                delta_min=0.05,
                delta_max=0.20,
                measurement_window_days=COMPETITOR_WINDOW_DAYS,
                confidence="low",   # rating is slow-moving even under heavy review push
            ),
        ],
    ))
    serial += 1

    return actions, serial


# ── Orchestration ────────────────────────────────────────────────────────────


def emit_all_gbp_actions() -> List[WorkQueueAction]:
    week = week_iso()
    serial = 1
    all_actions: List[WorkQueueAction] = []

    # Validate data is present
    any_data = False
    for loc in LOCATIONS:
        if gbp_location_full(loc):
            any_data = True
            break
    if not any_data:
        print("[gbp-emitter] no location data in gbp-data.json — exiting")
        return []

    # Order: REVIEW_GROWTH (P2) + PHOTO_REFRESH (P3) + COMPETITOR_GAP (P1)
    # We emit them per-location to keep IDs contiguous
    for loc in LOCATIONS:
        review_actions, serial = _emit_review_growth(loc, week, serial)
        photo_actions, serial = _emit_photo_refresh(loc, week, serial)
        gap_actions, serial = _emit_competitor_gap(loc, week, serial)
        all_actions.extend(review_actions + photo_actions + gap_actions)

    return all_actions


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
        "generator_version": "1.3.0",   # bumped for Session 5c
        "actions": merged,
        "_added_this_run": added,
    }


def main():
    print(f"\n=== GBP Work Queue Emitter — {now_iso()} ===")

    for loc in LOCATIONS:
        full = gbp_location_full(loc) or {}
        if not full:
            print(f"  {_display_location(loc)}: no data")
            continue
        print(
            f"  {_display_location(loc)}: rating={full.get('rating')} "
            f"reviews={full.get('reviews')} photos={full.get('photos')}"
        )

    actions = emit_all_gbp_actions()
    print(f"\nGenerated {len(actions)} candidate GBP actions for week {week_iso()}")

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
            base = primary.baseline if primary.baseline is not None else "?"
            tgt = (
                primary.target
                if primary.target is not None
                else f"{primary.delta_min}..{primary.delta_max}"
            )
            print(f"  - {a.title}")
            print(f"      → {primary.metric} baseline={base} target={tgt}")
        print()

    # Merge + write
    STATE_DIR.mkdir(exist_ok=True)
    merged = merge_with_existing(actions)
    WORK_QUEUE_FILE.write_text(json.dumps(merged, indent=2, default=str))
    print(
        f"[gbp-emitter] {merged['_added_this_run']} new + "
        f"{len(merged['actions']) - merged['_added_this_run']} existing = "
        f"{len(merged['actions'])} total actions in {WORK_QUEUE_FILE}"
    )


if __name__ == "__main__":
    main()
