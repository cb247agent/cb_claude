"""
mwcc_enrolment_emitter.py — emit structured Enrolment actions for MWCC.

Reads state/mwcc-ops.json (parsed weekly OWNA exports). 5 centres each
with: enrolments, exits, enquiries, occupancy per room, wage_inc_leave_pct,
wage_breach flag, compliance_risk flag per room.

Three archetypes:
  1. ENROLMENT_GAP    — centres with enquiries but no enrolments (broken
                         lead-to-tour-to-enrol funnel)
  2. OCCUPANCY_FILL   — per centre + room: occupancy < 80% AND NOT
                         compliance_risk (rooms with headroom)
  3. WAGE_RATIO_ALERT — centres flagged wage_breach by OWNA parse logic

MWCC-specific archetypes — different from CB247 because childcare has
per-room capacity, regulatory ratios, and centre-level wage targets
that don't apply to gym.

Run:
    .venv/bin/python3.13 scripts/work_queue/mwcc_enrolment_emitter.py

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
DATA_FILE = STATE_DIR / "mwcc-ops.json"

# ── Thresholds ──────────────────────────────────────────────────────────────

MAX_ENROLMENT_GAP_ACTIONS = 3
MAX_OCCUPANCY_FILL_ACTIONS = 4
MAX_WAGE_ALERT_ACTIONS = 3

ENROLMENT_GAP_MIN_ENQUIRIES = 1     # ≥1 enquiry but 0 enrolments → funnel issue
OCCUPANCY_FILL_PCT_FLOOR = 80.0
OCCUPANCY_FILL_MIN_ABSOLUTE_GAP = 3.0   # at least 3 children of headroom (don't surface tiny rooms)
WAGE_RATIO_TARGET_PCT = 42.0


def _load_data() -> dict:
    if not DATA_FILE.exists():
        return {}
    try:
        return json.loads(DATA_FILE.read_text())
    except Exception:
        return {}


# ── Archetype emitters ───────────────────────────────────────────────────────


def _emit_enrolment_gap(centres: dict, week: str, start_serial: int) -> Tuple[List[WorkQueueAction], int]:
    """Centres receiving enquiries but failing to convert to enrolments."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    candidates = []
    for name, c in centres.items():
        enquiries = int(c.get("enquiries") or 0)
        enrolments = int(c.get("enrolments") or 0)
        exits = int(c.get("exits") or 0)
        net = enrolments - exits
        # Fires when there's enquiry pipeline but no conversions, OR net is negative
        if enquiries >= ENROLMENT_GAP_MIN_ENQUIRIES and enrolments == 0:
            candidates.append((name, c, "no_conversion"))
        elif net < 0:
            candidates.append((name, c, "negative_net"))

    # Worst gaps first (highest enquiries with 0 enrolments, then most negative net)
    candidates.sort(key=lambda x: (
        -(int(x[1].get("enquiries") or 0) if x[2] == "no_conversion" else 0),
         (int(x[1].get("enrolments") or 0) - int(x[1].get("exits") or 0))
    ))

    for name, c, reason in candidates[:MAX_ENROLMENT_GAP_ACTIONS]:
        enquiries = int(c.get("enquiries") or 0)
        enrolments = int(c.get("enrolments") or 0)
        exits = int(c.get("exits") or 0)
        revenue = float(c.get("revenue") or 0)

        if reason == "no_conversion":
            description = (
                f"{name} received {enquiries} enquiry{'ies' if enquiries != 1 else ''} this week "
                f"but converted 0 to enrolments. That's a broken tour-to-enrol funnel. "
                f"Kelley to pull the enquiry list from OWNA → call each within 24h → book a tour. "
                f"For tours that don't enrol immediately, follow up at 48h with a centre photo + "
                f"vacancy reminder. Target: lift week-over-week enrolments at {name}."
            )
            target_enrolments = 1
        else:  # negative_net
            description = (
                f"{name} net member movement: {enrolments} enrolled vs {exits} exited = "
                f"{enrolments - exits:+d}. We're losing members faster than we're gaining at "
                f"this centre. Kelley investigates exit reasons via OWNA CleverWaiver equivalent. "
                f"If competitor switching is the reason, escalate to Tia for counter-positioning. "
                f"Target: net positive movement at {name} next week."
            )
            target_enrolments = exits + 1   # at least break even

        actions.append(WorkQueueAction(
            id=make_action_id("enrol-mwcc", week, serial),
            source_page="enrolment",
            source_run_at=ts,
            title=f"Close enrolment gap at {name} — {enquiries} enquiries, {enrolments} enrolled",
            description=description,
            owner="Kelley",
            owner_role="Manager / Frontline Ops",
            priority="P1",
            effort_hours=2.0,
            category="membership",
            data_quality="high",
            projected_kpis=[
                ProjectedKPI(
                    metric="membership_signups_weekly",
                    keyword=name,    # centre name as scope
                    baseline=enrolments,
                    target=float(target_enrolments),
                    measurement_window_days=7,
                    confidence="medium",
                ),
            ],
        ))
        serial += 1

    return actions, serial


def _emit_occupancy_fill(centres: dict, week: str, start_serial: int) -> Tuple[List[WorkQueueAction], int]:
    """Per centre + room: occupancy < 80% AND not compliance_risk → headroom to fill."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    candidates = []   # (centre_name, room_name, room_data)
    for name, c in centres.items():
        rooms = c.get("rooms_detail") or {}
        if not isinstance(rooms, dict):
            continue
        for room_name, room in rooms.items():
            if room.get("compliance_risk"):
                continue
            occ_pct = float(room.get("occupancy_pct") or 0)
            if occ_pct >= OCCUPANCY_FILL_PCT_FLOOR:
                continue
            capacity = int(room.get("capacity") or 0)
            avg_daily = float(room.get("avg_daily") or 0)
            absolute_gap = capacity - avg_daily
            if absolute_gap < OCCUPANCY_FILL_MIN_ABSOLUTE_GAP:
                continue
            candidates.append((name, room_name, room, absolute_gap))

    # Biggest absolute gap first (most children we could enrol)
    candidates.sort(key=lambda x: x[3], reverse=True)

    for centre_name, room_name, room, abs_gap in candidates[:MAX_OCCUPANCY_FILL_ACTIONS]:
        occ_pct = float(room.get("occupancy_pct") or 0)
        capacity = int(room.get("capacity") or 0)
        avg_daily = float(room.get("avg_daily") or 0)
        scope = f"{centre_name} — {room_name}"

        target_pct = OCCUPANCY_FILL_PCT_FLOOR + 5  # aim for 85%
        target_avg_daily = round(capacity * target_pct / 100, 1)

        actions.append(WorkQueueAction(
            id=make_action_id("enrol-mwcc", week, serial),
            source_page="enrolment",
            source_run_at=ts,
            title=f"Fill {scope} — {occ_pct:.0f}% occupancy ({avg_daily:.1f}/{capacity} avg daily)",
            description=(
                f"{scope} is at {occ_pct:.0f}% occupancy this week — {avg_daily:.1f} children "
                f"average daily against {capacity} capacity ({capacity - avg_daily:.1f} seats "
                f"available daily). Kelley + reception team to: "
                f"(1) Call waitlist for this room — they may have moved on, but worth confirming, "
                f"(2) Run Meta + Google Ads with hyperlocal targeting (postcodes within 5km of "
                f"{centre_name}), "
                f"(3) Brief Jordan on a centre-specific creative angle for the {room_name} room. "
                f"Target: {target_pct:.0f}% occupancy ({target_avg_daily} avg daily)."
            ),
            owner="Kelley",
            owner_role="Manager / Frontline Ops",
            priority="P2",
            effort_hours=3.0,
            category="membership",
            data_quality="high",
            projected_kpis=[
                ProjectedKPI(
                    metric="mwcc_occupancy_pct",
                    keyword=scope,
                    baseline=round(occ_pct, 1),
                    target=float(target_pct),
                    measurement_window_days=14,
                    confidence="medium",
                ),
            ],
        ))
        serial += 1

    return actions, serial


def _emit_wage_ratio_alert(centres: dict, week: str, start_serial: int) -> Tuple[List[WorkQueueAction], int]:
    """Centres flagged wage_breach by OWNA parse logic."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    candidates = []
    for name, c in centres.items():
        if c.get("wage_breach"):
            candidates.append((name, c))

    # Worst wage % first
    candidates.sort(key=lambda x: float(x[1].get("wage_inc_leave_pct") or 0), reverse=True)

    for name, c in candidates[:MAX_WAGE_ALERT_ACTIONS]:
        wage_inc = float(c.get("wage_inc_leave_pct") or 0)
        wage_exc = float(c.get("wage_exc_leave_pct") or 0)
        revenue = float(c.get("revenue") or 0)
        roster = float(c.get("roster_cost") or 0)
        leave = float(c.get("leave_cost") or 0)

        actions.append(WorkQueueAction(
            id=make_action_id("enrol-mwcc", week, serial),
            source_page="enrolment",
            source_run_at=ts,
            title=f"Wage ratio breach at {name} — {wage_inc:.1f}% (target ≤ {WAGE_RATIO_TARGET_PCT:.0f}%)",
            description=(
                f"{name} wage % is {wage_inc:.1f}% (inc leave) / {wage_exc:.1f}% (exc leave) on "
                f"${revenue:,.0f} revenue. Above the {WAGE_RATIO_TARGET_PCT:.0f}% target. "
                f"Roster cost ${roster:,.0f} + leave cost ${leave:,.0f}. "
                f"Denver makes the strategic call: (a) reduce headcount via roster optimisation, "
                f"(b) increase revenue via enrolments to dilute wage ratio, or (c) both. "
                f"Kelley executes the chosen path — adjusts rostering or runs an enrolment push "
                f"for {name}. Target: wage % drops to {WAGE_RATIO_TARGET_PCT:.0f}% within 28 days."
            ),
            owner="Denver",
            owner_role="COO (Strategic) + Kelley (Execution)",
            priority="P1",
            effort_hours=2.0,
            category="membership",
            data_quality="high",
            projected_kpis=[
                ProjectedKPI(
                    metric="mwcc_wage_ratio_pct",
                    keyword=name,
                    baseline=round(wage_inc, 1),
                    target=float(WAGE_RATIO_TARGET_PCT),
                    measurement_window_days=28,
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
        print("[mwcc-enrol-emitter] no state/mwcc-ops.json — exiting")
        return []

    centres = data.get("centres") or {}
    if not centres:
        print("[mwcc-enrol-emitter] no centres in data — exiting")
        return []

    summary = data.get("network_summary") or {}
    print(f"MWCC ops period: {data.get('period')}")
    print(f"Network summary: {summary.get('total_enrolments')} enrolments, "
          f"{summary.get('total_exits')} exits, {summary.get('total_enquiries')} enquiries, "
          f"${summary.get('total_revenue', 0):,.0f} revenue")
    print(f"Wage breach centres: {summary.get('centres_in_wage_breach', [])}")
    print(f"Compliance risks: {summary.get('rooms_with_compliance_risk', [])}")

    week = week_iso()
    serial = 1

    gap,      serial = _emit_enrolment_gap(centres, week, serial)
    occ,      serial = _emit_occupancy_fill(centres, week, serial)
    wage,     serial = _emit_wage_ratio_alert(centres, week, serial)

    return gap + occ + wage


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
    print(f"\n=== MWCC Enrolment Work Queue Emitter — {now_iso()} ===")

    actions = emit_all()
    print(f"\nGenerated {len(actions)} MWCC Enrolment actions for week {week_iso()}")

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
        f"[mwcc-enrol-emitter] {merged['_added_this_run']} new + "
        f"{len(merged['actions']) - merged['_added_this_run']} existing = "
        f"{len(merged['actions'])} total actions in {WORK_QUEUE_FILE}"
    )


if __name__ == "__main__":
    main()
