"""
mwcc_seo_emitter.py — emit structured SEO actions for MWCC.

Reads state/mwcc-gsc-data.json (Google Search Console: top_queries + top_pages).
Same OAuth flow as CB247 — cb_agent@chasingbetter.com.au added as restricted
user on myworldcc.com.au GSC property.

Three archetypes — same as CB247 seo_emitter.py:
  1. OPTIMISE  — keywords ranking #4-#20 with traffic (quickest wins)
  2. BUILD     — high-impression keywords ranking #21+ (no dedicated page yet)
  3. PROTECT   — keywords already #1-#3 generating clicks (defend, don't lose)

Strategic goal: same as CB247 — shift traffic from paid Google Ads to organic
by ranking the best keywords. Reduce paid spend over time.

Future enhancement (Monday cron): cross-reference with state/mwcc-ahrefs-data.json
to enrich BUILD archetype with competitor gap signal (keywords competitors
rank for that MWCC doesn't).

Run:
    .venv/bin/python3.13 scripts/work_queue/mwcc_seo_emitter.py

Writes/updates: state/mwcc-work-queue.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Tuple

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))
sys.path.insert(0, str(_HERE.parent.parent))

from work_queue.schema import (  # noqa: E402
    WorkQueueAction,
    ProjectedKPI,
    make_action_id,
    now_iso,
    week_iso,
    to_jsonable,
)

BASE_DIR = _HERE.parent.parent
STATE_DIR = BASE_DIR / "state"
WORK_QUEUE_FILE = STATE_DIR / "mwcc-work-queue.json"
DATA_FILE = STATE_DIR / "mwcc-gsc-data.json"
AHREFS_FILE = STATE_DIR / "mwcc-ahrefs-data.json"   # optional supplementary data

# ── Thresholds — sized for MWCC current GSC volume (low overall) ───────────

MAX_OPTIMISE_ACTIONS = 5
MAX_BUILD_ACTIONS = 4
MAX_PROTECT_ACTIONS = 2

# OPTIMISE — keywords ranking #4-#20 (page exists, needs tuning)
OPTIMISE_MIN_IMPRESSIONS = 1
OPTIMISE_POSITION_RANGE = (4, 20)

# BUILD — keywords ranking #21+ with impressions (no dedicated page yet)
BUILD_MIN_IMPRESSIONS = 3
BUILD_MIN_POSITION = 21

# PROTECT — top-3 keywords already generating clicks
PROTECT_MIN_CLICKS = 1   # low threshold — MWCC has small volumes
PROTECT_MAX_POSITION = 3


def _load_data() -> dict:
    if not DATA_FILE.exists():
        return {}
    try:
        return json.loads(DATA_FILE.read_text())
    except Exception:
        return {}


# ── Archetype emitters ───────────────────────────────────────────────────────


def _emit_optimise(queries: list, week: str, start_serial: int) -> Tuple[List[WorkQueueAction], int]:
    """OPTIMISE: keywords ranking #4-#20 — page exists, just needs tuning."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    candidates = [
        q for q in queries
        if q.get("position") is not None
        and OPTIMISE_POSITION_RANGE[0] <= q["position"] <= OPTIMISE_POSITION_RANGE[1]
        and (q.get("impressions") or 0) >= OPTIMISE_MIN_IMPRESSIONS
        and len((q.get("query") or "").split()) >= 2   # skip single-word vague queries
    ]
    candidates.sort(key=lambda q: (q.get("impressions") or 0), reverse=True)

    for q in candidates[:MAX_OPTIMISE_ACTIONS]:
        keyword = q["query"]
        position = float(q["position"])
        clicks = int(q.get("clicks") or 0)
        impressions = int(q.get("impressions") or 0)

        target_pos = 3 if position > 5 else max(1, round(position) - 2)
        delta_min = max(1, int(impressions * 0.15))
        delta_max = max(3, int(impressions * 0.5))
        priority = "P1" if position <= 8 and clicks >= 1 else "P2"

        actions.append(WorkQueueAction(
            id=make_action_id("seo-mwcc", week, serial),
            source_page="seo-organic",
            source_run_at=ts,
            title=f"Optimise on-page for '{keyword}' — currently #{position:.1f}",
            description=(
                f"'{keyword}' is ranking #{position:.1f} with {clicks} clicks and {impressions} "
                f"impressions per week (MWCC GSC). On-page tune: tighten H1 + title + meta description, "
                f"add 1-2 internal links from related centre or service pages, expand content depth if thin. "
                f"Target: push to #{target_pos}. "
                f"Strategic — ranking organically here means less paid Google Ads spend on this query."
            ),
            owner="John",
            owner_role="SEO / Web Specialist",
            priority=priority,
            effort_hours=0.5,
            category="seo",
            data_quality="high",
            projected_kpis=[
                ProjectedKPI(
                    metric="gsc_position",
                    keyword=keyword,
                    baseline=round(position, 1),
                    target=float(target_pos),
                    measurement_window_days=14,
                    confidence="high",
                ),
                ProjectedKPI(
                    metric="gsc_clicks_weekly",
                    keyword=keyword,
                    baseline=clicks,
                    delta_min=delta_min,
                    delta_max=delta_max,
                    measurement_window_days=14,
                    confidence="medium",
                ),
            ],
        ))
        serial += 1

    return actions, serial


def _emit_build(queries: list, week: str, start_serial: int) -> Tuple[List[WorkQueueAction], int]:
    """BUILD: high-impression keywords ranking #21+ — no dedicated page yet."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    candidates = [
        q for q in queries
        if q.get("position") is not None
        and q["position"] >= BUILD_MIN_POSITION
        and (q.get("impressions") or 0) >= BUILD_MIN_IMPRESSIONS
    ]
    candidates.sort(key=lambda q: (q.get("impressions") or 0), reverse=True)

    for q in candidates[:MAX_BUILD_ACTIONS]:
        keyword = q["query"]
        position = float(q["position"])
        impressions = int(q.get("impressions") or 0)
        clicks = int(q.get("clicks") or 0)

        actions.append(WorkQueueAction(
            id=make_action_id("seo-mwcc", week, serial),
            source_page="seo-organic",
            source_run_at=ts,
            title=f"Build new content for '{keyword}' — {impressions} impressions, ranking #{position:.0f}",
            description=(
                f"'{keyword}' has {impressions} weekly impressions but ranks #{position:.0f}, "
                f"only generating {clicks} clicks. MWCC has no dedicated page targeting this query.\n\n"
                f"Flow: AI drafts → Brand Manager QC → publish to Webflow. "
                f"Jordan provides centre-specific copy + photos if the query targets a specific suburb. "
                f"Target: rank top 10 within 4 weeks."
            ),
            owner="AI",
            owner_role="Content Agent (→ Jordan → Mark)",
            priority="P2",
            effort_hours=2.0,
            category="seo",
            data_quality="high",
            projected_kpis=[
                ProjectedKPI(
                    metric="gsc_position",
                    keyword=keyword,
                    baseline=round(position, 1),
                    target=10.0,
                    measurement_window_days=28,   # new pages take longer to index + rank
                    confidence="medium",
                ),
                ProjectedKPI(
                    metric="gsc_clicks_weekly",
                    keyword=keyword,
                    baseline=clicks,
                    delta_min=2,
                    delta_max=max(5, int(impressions * 0.1)),
                    measurement_window_days=28,
                    confidence="medium",
                ),
            ],
        ))
        serial += 1

    return actions, serial


def _emit_protect(queries: list, week: str, start_serial: int) -> Tuple[List[WorkQueueAction], int]:
    """PROTECT: keywords already top-3 generating clicks."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    candidates = [
        q for q in queries
        if q.get("position") is not None
        and q["position"] <= PROTECT_MAX_POSITION
        and (q.get("clicks") or 0) >= PROTECT_MIN_CLICKS
    ]
    candidates.sort(key=lambda q: (q.get("clicks") or 0), reverse=True)

    for q in candidates[:MAX_PROTECT_ACTIONS]:
        keyword = q["query"]
        position = float(q["position"])
        clicks = int(q.get("clicks") or 0)
        impressions = int(q.get("impressions") or 0)

        actions.append(WorkQueueAction(
            id=make_action_id("seo-mwcc", week, serial),
            source_page="seo-organic",
            source_run_at=ts,
            title=f"Protect '{keyword}' — currently #{position:.1f} with {clicks} clicks/wk",
            description=(
                f"'{keyword}' ranks #{position:.1f} and generates {clicks} clicks per week "
                f"({impressions} impressions). Defensive: build 1-2 new internal links from related "
                f"centre or service content, monitor for position decay, refresh page date stamp if "
                f"not updated in 90 days. Target: hold #{position:.1f} ± 1."
            ),
            owner="John",
            owner_role="SEO / Web Specialist",
            priority="P3",
            effort_hours=0.5,
            category="seo",
            data_quality="high",
            projected_kpis=[
                ProjectedKPI(
                    metric="gsc_position",
                    keyword=keyword,
                    baseline=round(position, 1),
                    target=round(position, 1),
                    measurement_window_days=14,
                    confidence="high",
                ),
            ],
        ))
        serial += 1

    return actions, serial


# ── Orchestration ────────────────────────────────────────────────────────────


def emit_all() -> List[WorkQueueAction]:
    data = _load_data()
    if not data:
        print("[mwcc-seo-emitter] no state/mwcc-gsc-data.json — run pull_mwcc_gsc.py first")
        return []

    queries = data.get("top_queries") or []
    if not queries:
        print("[mwcc-seo-emitter] no top_queries in GSC data — exiting")
        return []

    totals = data.get("totals") or {}
    print(f"MWCC SEO data (GSC):")
    print(f"  date_range: {data.get('date_range', {}).get('start')} → {data.get('date_range', {}).get('end')}")
    print(f"  totals: {totals.get('clicks', 0)} clicks, {totals.get('impressions', 0)} impressions, "
          f"avg pos {totals.get('position', 0):.1f}")
    print(f"  top_queries: {len(queries)}")

    week = week_iso()
    serial = 1

    optimise, serial = _emit_optimise(queries, week, serial)
    build,    serial = _emit_build(queries, week, serial)
    protect,  serial = _emit_protect(queries, week, serial)

    return optimise + build + protect


def merge_with_existing(new_actions: List[WorkQueueAction]) -> dict:
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
        "generator_version": "1.0.0-mwcc",
        "business": "mwcc",
        "actions": merged,
        "_added_this_run": added,
    }


def main():
    print(f"\n=== MWCC SEO Work Queue Emitter — {now_iso()} ===")

    actions = emit_all()
    print(f"\nGenerated {len(actions)} MWCC SEO actions for week {week_iso()}")

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
            tgt = primary.target if primary.target is not None else "?"
            print(f"  - {a.title}")
            print(f"      → {primary.metric} baseline={base} target={tgt}")
        print()

    STATE_DIR.mkdir(exist_ok=True)
    merged = merge_with_existing(actions)
    WORK_QUEUE_FILE.write_text(json.dumps(merged, indent=2, default=str))
    print(
        f"[mwcc-seo-emitter] {merged['_added_this_run']} new + "
        f"{len(merged['actions']) - merged['_added_this_run']} existing = "
        f"{len(merged['actions'])} total actions in {WORK_QUEUE_FILE}"
    )


if __name__ == "__main__":
    main()
