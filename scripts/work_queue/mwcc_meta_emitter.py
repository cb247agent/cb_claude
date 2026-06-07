"""
mwcc_meta_emitter.py — emit structured Meta Ads actions for MWCC.

Reads state/mwcc-meta.json. MWCC Meta has 10 campaigns + 18 ad sets across
5 centres (Armadale, Midvale, Rockingham, Seville Grove, Waikiki).

Same archetype design as CB247 meta_emitter:
  1. PAUSE     — ads with high spend + low CTR (waste)
  2. SCALE     — ads with high CTR + low CPC (winners)
  3. REFRESH   — mid-tier ads where creative needs a swap

Operates at AD SET level (richer per-centre data than campaign level).

Run:
    .venv/bin/python3.13 scripts/work_queue/mwcc_meta_emitter.py

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
DATA_FILE = STATE_DIR / "mwcc-meta.json"

# ── Thresholds — MWCC weekly Meta spend ~$1,300, account CTR ~1.1%, CPC ~$0.50

MAX_PAUSE_ACTIONS = 3
MAX_SCALE_ACTIONS = 3
MAX_REFRESH_ACTIONS = 3

PAUSE_MIN_SPEND = 20.0
PAUSE_MAX_CTR = 0.80         # below account avg (1.11%)

SCALE_MIN_CTR = 1.50         # above account avg
SCALE_MAX_CPC = 0.80
SCALE_MIN_SPEND = 30.0
SCALE_MIN_CLICKS = 30

REFRESH_MIN_SPEND = 30.0
REFRESH_CTR_RANGE = (0.80, 1.50)   # in-between


def _load_data() -> dict:
    if not DATA_FILE.exists():
        return {}
    try:
        return json.loads(DATA_FILE.read_text())
    except Exception:
        return {}


# ── Archetype emitters ───────────────────────────────────────────────────────


def _emit_pause(ad_sets: list, week: str, start_serial: int) -> Tuple[List[WorkQueueAction], int]:
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    candidates = [
        a for a in ad_sets
        if (a.get("spend") or 0) >= PAUSE_MIN_SPEND
        and (a.get("ctr") or 0) < PAUSE_MAX_CTR
        and (a.get("clicks") or 0) >= 1
    ]
    candidates.sort(key=lambda a: (a.get("ctr") or 0))   # worst CTR first

    for ad in candidates[:MAX_PAUSE_ACTIONS]:
        name = (ad.get("adset_name") or "").strip()
        centre = (ad.get("centre") or "—").strip()
        spend = float(ad.get("spend") or 0)
        ctr = float(ad.get("ctr") or 0)
        cpc = float(ad.get("cpc") or 0)
        clicks = int(ad.get("clicks") or 0)

        actions.append(WorkQueueAction(
            id=make_action_id("meta-mwcc", week, serial),
            source_page="meta-ads",
            source_run_at=ts,
            title=f"Pause MWCC Meta ad set '{name}' ({centre}) — CTR {ctr:.2f}% at ${spend:.0f}/wk",
            description=(
                f"This ad set spent ${spend:.0f} last week at {ctr:.2f}% CTR (CPC ${cpc:.2f}, {clicks} "
                f"clicks) — well below the account {PAUSE_MAX_CTR:.2f}% floor. Centre: {centre}. "
                f"Pause in Meta Ads Manager. Reallocate budget to SCALE candidates. "
                f"Jordan to brief on new creative angle before relaunching."
            ),
            owner="Joanne",
            owner_role="Paid Social + Scheduling",
            priority="P1",
            effort_hours=0.25,
            category="meta",
            data_quality="high",
            projected_kpis=[
                ProjectedKPI(
                    metric="meta_ctr",
                    keyword=name,
                    baseline=round(ctr, 2),
                    target=round(max(0.20, ctr * 0.5), 2),
                    measurement_window_days=7,
                    confidence="medium",
                ),
            ],
        ))
        serial += 1

    return actions, serial


def _emit_scale(ad_sets: list, week: str, start_serial: int) -> Tuple[List[WorkQueueAction], int]:
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    candidates = [
        a for a in ad_sets
        if (a.get("ctr") or 0) >= SCALE_MIN_CTR
        and (a.get("cpc") or 999) <= SCALE_MAX_CPC
        and (a.get("spend") or 0) >= SCALE_MIN_SPEND
        and (a.get("clicks") or 0) >= SCALE_MIN_CLICKS
    ]
    candidates.sort(key=lambda a: (a.get("ctr") or 0), reverse=True)

    for ad in candidates[:MAX_SCALE_ACTIONS]:
        name = (ad.get("adset_name") or "").strip()
        centre = (ad.get("centre") or "—").strip()
        spend = float(ad.get("spend") or 0)
        ctr = float(ad.get("ctr") or 0)
        cpc = float(ad.get("cpc") or 0)
        clicks = int(ad.get("clicks") or 0)

        clicks_target = int(clicks * 1.45)

        actions.append(WorkQueueAction(
            id=make_action_id("meta-mwcc", week, serial),
            source_page="meta-ads",
            source_run_at=ts,
            title=f"Scale MWCC Meta ad set '{name}' ({centre}) — CTR {ctr:.2f}%, CPC ${cpc:.2f}",
            description=(
                f"This ad set is a winner: {ctr:.2f}% CTR, ${cpc:.2f} CPC, {clicks} clicks at "
                f"${spend:.0f} spend last week. Centre: {centre}. Increase daily budget by 50% in "
                f"Meta Ads Manager. Monitor CPC for 3 days — if it stays under ${cpc * 1.30:.2f}, "
                f"hold the new budget. Target: +45% clicks at similar or better CPC."
            ),
            owner="Joanne",
            owner_role="Paid Social + Scheduling",
            priority="P1",
            effort_hours=0.25,
            category="meta",
            data_quality="high",
            projected_kpis=[
                ProjectedKPI(
                    metric="meta_ad_clicks_weekly",
                    keyword=name,
                    baseline=clicks,
                    target=float(clicks_target),
                    measurement_window_days=7,
                    confidence="medium",
                ),
                ProjectedKPI(
                    metric="meta_cpc",
                    keyword=name,
                    baseline=round(cpc, 2),
                    target=round(cpc * 1.20, 2),
                    measurement_window_days=7,
                    confidence="medium",
                ),
            ],
        ))
        serial += 1

    return actions, serial


def _emit_refresh(ad_sets: list, week: str, start_serial: int) -> Tuple[List[WorkQueueAction], int]:
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    ctr_min, ctr_max = REFRESH_CTR_RANGE
    candidates = [
        a for a in ad_sets
        if (a.get("spend") or 0) >= REFRESH_MIN_SPEND
        and ctr_min <= (a.get("ctr") or 0) <= ctr_max
    ]
    candidates.sort(key=lambda a: (a.get("spend") or 0), reverse=True)

    for ad in candidates[:MAX_REFRESH_ACTIONS]:
        name = (ad.get("adset_name") or "").strip()
        centre = (ad.get("centre") or "—").strip()
        spend = float(ad.get("spend") or 0)
        ctr = float(ad.get("ctr") or 0)
        clicks = int(ad.get("clicks") or 0)

        ctr_target = round(min(2.50, ctr + 0.40), 2)

        actions.append(WorkQueueAction(
            id=make_action_id("meta-mwcc", week, serial),
            source_page="meta-ads",
            source_run_at=ts,
            title=f"Refresh MWCC Meta creative '{name}' ({centre}) — CTR {ctr:.2f}% needs a lift",
            description=(
                f"This ad set has reasonable reach (${spend:.0f} spend, {clicks} clicks at {centre}) "
                f"but CTR is stuck at {ctr:.2f}% — neither bad enough to pause nor strong enough to "
                f"scale. Jordan produces a fresh creative variation (new hook, new visual, same "
                f"offer). Joanne swaps in Meta Ads Manager and runs for 7 days. "
                f"Target: CTR {ctr_target:.2f}% (+0.40pp absolute)."
            ),
            owner="Jordan",
            owner_role="Content / Assets Creator",
            priority="P2",
            effort_hours=2.0,
            category="meta",
            data_quality="high",
            projected_kpis=[
                ProjectedKPI(
                    metric="meta_ctr",
                    keyword=name,
                    baseline=round(ctr, 2),
                    target=ctr_target,
                    measurement_window_days=7,
                    confidence="medium",
                ),
            ],
        ))
        serial += 1

    return actions, serial


# ── Orchestration ────────────────────────────────────────────────────────────


def emit_all() -> List[WorkQueueAction]:
    data = _load_data()
    if not data:
        print("[mwcc-meta-emitter] no state/mwcc-meta.json — exiting")
        return []

    # Operate on ad_sets (richer per-centre data than campaigns)
    ad_sets = data.get("ad_sets") or []
    if not ad_sets:
        print("[mwcc-meta-emitter] no ad_sets in data — exiting")
        return []

    summary = data.get("summary") or {}
    print(f"MWCC Meta window: {data.get('date_range', {}).get('start')} → {data.get('date_range', {}).get('end')}")
    print(f"Account: spend=${summary.get('spend', 0):.0f}  CTR={summary.get('ctr', 0):.2f}%  CPC=${summary.get('cpc', 0):.2f}")
    print(f"Operating on {len(ad_sets)} ad sets")

    week = week_iso()
    serial = 1

    pause,   serial = _emit_pause(ad_sets, week, serial)
    scale,   serial = _emit_scale(ad_sets, week, serial)
    refresh, serial = _emit_refresh(ad_sets, week, serial)

    return pause + scale + refresh


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
    print(f"\n=== MWCC Meta Ads Work Queue Emitter — {now_iso()} ===")

    actions = emit_all()
    print(f"\nGenerated {len(actions)} MWCC Meta actions for week {week_iso()}")

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
        f"[mwcc-meta-emitter] {merged['_added_this_run']} new + "
        f"{len(merged['actions']) - merged['_added_this_run']} existing = "
        f"{len(merged['actions'])} total actions in {WORK_QUEUE_FILE}"
    )


if __name__ == "__main__":
    main()
