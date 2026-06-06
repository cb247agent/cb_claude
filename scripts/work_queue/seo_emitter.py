"""
seo_emitter.py — emit structured SEO actions to state/work-queue.json.

Reads state/gsc-data.json, picks high-leverage keyword opportunities,
emits WorkQueueAction records with structured projected_kpis.

Three action archetypes (in priority order):
  1. OPTIMISE — for keywords ranking #4-#15 with traffic (quickest wins)
  2. BUILD     — for high-impression keywords ranking #20+ (no dedicated page)
  3. PROTECT   — for keywords already #1-#3 (defend, don't lose ground)

Run:
    python -m scripts.work_queue.seo_emitter
    OR
    .venv/bin/python3.13 scripts/work_queue/seo_emitter.py

Writes/updates: state/work-queue.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List

# Allow direct script run AND module import
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))   # scripts/
sys.path.insert(0, str(_HERE.parent.parent))   # repo root

from work_queue.schema import (  # noqa: E402
    WorkQueueAction,
    ProjectedKPI,
    make_action_id,
    now_iso,
    week_iso,
    to_jsonable,
)
from work_queue.baselines import gsc_all_queries, gsc_date_range  # noqa: E402


BASE_DIR = _HERE.parent.parent
STATE_DIR = BASE_DIR / "state"
WORK_QUEUE_FILE = STATE_DIR / "work-queue.json"

# Tunable thresholds — sized for CB247 current traffic level (brand-heavy,
# sparse non-brand). Raise these as overall organic traffic grows.
MAX_OPTIMISE_ACTIONS = 5
MAX_BUILD_ACTIONS = 4
MAX_PROTECT_ACTIONS = 2

# OPTIMISE — keywords ranking #4-#20 (a page probably exists, just needs tweaking)
OPTIMISE_MIN_IMPRESSIONS = 1
OPTIMISE_POSITION_RANGE = (4, 20)

# BUILD — keywords ranking #21+ (no dedicated page — needs creation)
# Mutually exclusive with OPTIMISE to avoid double-counting.
BUILD_MIN_IMPRESSIONS = 3
BUILD_MIN_POSITION = 21

# PROTECT — top-3 keywords already generating real traffic
PROTECT_MIN_CLICKS = 20
PROTECT_MAX_POSITION = 3


# ── Emitters ─────────────────────────────────────────────────────────────────


def _emit_optimise(queries: list, week: str, start_serial: int) -> tuple[List[WorkQueueAction], int]:
    """Optimise the title tag / on-page for near-top keywords."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    candidates = [
        q for q in queries
        if q.get("position") is not None
        and OPTIMISE_POSITION_RANGE[0] <= q["position"] <= OPTIMISE_POSITION_RANGE[1]
        and (q.get("impressions") or 0) >= OPTIMISE_MIN_IMPRESSIONS
        # Skip generic noise queries (single-word, too vague)
        and len((q.get("query") or "").split()) >= 2
    ]
    candidates.sort(key=lambda q: q.get("impressions", 0) or 0, reverse=True)

    for q in candidates[:MAX_OPTIMISE_ACTIONS]:
        keyword = q["query"]
        baseline_pos = float(q["position"])
        baseline_clicks = int(q.get("clicks") or 0)
        baseline_impr = int(q.get("impressions") or 0)

        # Target: top 3 if currently 8+, else current-2
        target_pos = 3 if baseline_pos > 5 else max(1, round(baseline_pos) - 2)
        delta_min = max(2, int(baseline_clicks * 0.3))
        delta_max = max(5, int(baseline_clicks * 1.5))

        # Priority logic: P1 if low position + good clicks, else P2
        priority = "P1" if baseline_pos <= 8 and baseline_clicks >= 10 else "P2"

        actions.append(WorkQueueAction(
            id=make_action_id("seo", week, serial),
            source_page="seo-organic",
            source_run_at=ts,
            title=f"Optimise on-page for '{keyword}' — currently #{baseline_pos:.1f}",
            description=(
                f"Keyword '{keyword}' is ranking #{baseline_pos:.1f} with {baseline_clicks} clicks "
                f"and {baseline_impr} impressions per week. "
                f"Optimise the title tag, meta description, and H1 of the ranking page. "
                f"Add 1-2 internal links from related content. Tighten content depth if needed. "
                f"Target: push to #{target_pos}."
            ),
            owner="John",
            owner_role="SEO Specialist",
            priority=priority,
            effort_hours=0.5,
            category="seo",
            data_quality="high",
            projected_kpis=[
                ProjectedKPI(
                    metric="gsc_position",
                    keyword=keyword,
                    baseline=round(baseline_pos, 1),
                    target=float(target_pos),
                    measurement_window_days=14,
                    confidence="high",
                ),
                ProjectedKPI(
                    metric="gsc_clicks_weekly",
                    keyword=keyword,
                    baseline=baseline_clicks,
                    delta_min=delta_min,
                    delta_max=delta_max,
                    measurement_window_days=14,
                    confidence="medium",
                ),
            ],
        ))
        serial += 1

    return actions, serial


def _emit_build(queries: list, week: str, start_serial: int) -> tuple[List[WorkQueueAction], int]:
    """Build new content for high-impression, deep-ranking keywords."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    candidates = [
        q for q in queries
        if q.get("position") is not None
        and q["position"] >= BUILD_MIN_POSITION
        and (q.get("impressions") or 0) >= BUILD_MIN_IMPRESSIONS
    ]
    candidates.sort(key=lambda q: q.get("impressions", 0) or 0, reverse=True)

    for q in candidates[:MAX_BUILD_ACTIONS]:
        keyword = q["query"]
        baseline_pos = float(q["position"])
        baseline_impr = int(q.get("impressions") or 0)
        baseline_clicks = int(q.get("clicks") or 0)

        actions.append(WorkQueueAction(
            id=make_action_id("seo", week, serial),
            source_page="seo-organic",
            source_run_at=ts,
            title=f"Build new content for '{keyword}' — {baseline_impr} impressions, ranking #{baseline_pos:.0f}",
            description=(
                f"Keyword '{keyword}' has {baseline_impr} weekly impressions but ranks #{baseline_pos:.0f}, "
                f"only generating {baseline_clicks} clicks. No dedicated page targeting this query. "
                f"AI drafts a focused page → Angela QC → Denver sign-off → Mark publishes to Webflow. "
                f"Target: rank top 10 within 4 weeks."
            ),
            owner="AI",
            owner_role="Content Agent",
            priority="P2",
            effort_hours=2.0,
            category="seo",
            data_quality="high",
            projected_kpis=[
                ProjectedKPI(
                    metric="gsc_position",
                    keyword=keyword,
                    baseline=round(baseline_pos, 1),
                    target=10.0,
                    measurement_window_days=28,   # new pages take longer to index + rank
                    confidence="medium",
                ),
                ProjectedKPI(
                    metric="gsc_clicks_weekly",
                    keyword=keyword,
                    baseline=baseline_clicks,
                    delta_min=5,
                    delta_max=max(10, int(baseline_impr * 0.1)),
                    measurement_window_days=28,
                    confidence="medium",
                ),
            ],
        ))
        serial += 1

    return actions, serial


def _emit_protect(queries: list, week: str, start_serial: int) -> tuple[List[WorkQueueAction], int]:
    """Protect keywords already in top 3 with strong click traffic."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    candidates = [
        q for q in queries
        if q.get("position") is not None
        and q["position"] <= PROTECT_MAX_POSITION
        and (q.get("clicks") or 0) >= PROTECT_MIN_CLICKS
    ]
    candidates.sort(key=lambda q: q.get("clicks", 0) or 0, reverse=True)

    for q in candidates[:MAX_PROTECT_ACTIONS]:
        keyword = q["query"]
        baseline_pos = float(q["position"])
        baseline_clicks = int(q.get("clicks") or 0)

        actions.append(WorkQueueAction(
            id=make_action_id("seo", week, serial),
            source_page="seo-organic",
            source_run_at=ts,
            title=f"Protect '{keyword}' — currently #{baseline_pos:.1f} with {baseline_clicks} clicks/wk",
            description=(
                f"This keyword ranks #{baseline_pos:.1f} and generates {baseline_clicks} clicks per week. "
                f"Defensive work: build 1-2 new internal links from related content, monitor for position decay, "
                f"refresh the page date stamp if not updated in 90 days. "
                f"Target: hold position #{baseline_pos:.1f} ± 1."
            ),
            owner="John",
            owner_role="SEO Specialist",
            priority="P3",
            effort_hours=0.5,
            category="seo",
            data_quality="high",
            projected_kpis=[
                ProjectedKPI(
                    metric="gsc_position",
                    keyword=keyword,
                    baseline=round(baseline_pos, 1),
                    target=round(baseline_pos, 1),   # hold steady
                    measurement_window_days=14,
                    confidence="high",
                ),
            ],
        ))
        serial += 1

    return actions, serial


# ── Orchestration ────────────────────────────────────────────────────────────


def emit_all_seo_actions() -> List[WorkQueueAction]:
    queries = gsc_all_queries()
    if not queries:
        print("[seo-emitter] no top_queries in gsc-data.json — exiting")
        return []

    week = week_iso()
    serial = 1

    optimise, serial = _emit_optimise(queries, week, serial)
    build,    serial = _emit_build(queries, week, serial)
    protect,  serial = _emit_protect(queries, week, serial)

    return optimise + build + protect


def merge_with_existing(new_actions: List[WorkQueueAction]) -> dict:
    """
    Merge new actions into state/work-queue.json without overwriting existing IDs.
    Action IDs are week-scoped so re-running in the same week is idempotent.
    """
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
        "generator_version": "1.0.0",
        "actions": merged,
        "_added_this_run": added,
    }


def main():
    print(f"\n=== SEO Work Queue Emitter — {now_iso()} ===")
    rng = gsc_date_range()
    if rng:
        print(f"GSC data window: {rng.get('start')} → {rng.get('end')}")

    actions = emit_all_seo_actions()
    print(f"Generated {len(actions)} candidate SEO actions for week {week_iso()}")

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
        f"[seo-emitter] {merged['_added_this_run']} new + "
        f"{len(merged['actions']) - merged['_added_this_run']} existing = "
        f"{len(merged['actions'])} total actions in {WORK_QUEUE_FILE}"
    )


if __name__ == "__main__":
    main()
