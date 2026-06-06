"""
membership_emitter.py — emit structured Membership actions to state/work-queue.json.

Reads state/membership-data.json (parsed weekly XLSX export from the CRM).
This is the richest dataset of any source: per-club signups + cancellations,
categorised exit reasons, exit-survey ("Cleverwaiver") responses, addon
penetration, and a future-cancellations queue (literal save-call list).

Four action archetypes:
  1. SAVE_CALL        — per location, fires when future_cancellations > 50.
                         The queue is the most valuable single asset in this
                         dataset — every member who filed but hasn't left yet.
  2. CHURN_REASON     — fires per top actionable reason (Not Using, Switched
                         to Gym). Skips non-actionable reasons (Relocating,
                         End of Contract).
  3. SWITCH_DEFENCE   — fires when combined PGM + Cleverwaiver "switched to
                         another gym" count ≥ 5. Direct competitive loss.
  4. ADDON_UPSELL     — Recovery (Sauna + Ice Bath) penetration grow. The
                         single biggest premium differentiator vs Revo and
                         Anytime. Massive headroom.

Run:
    .venv/bin/python3.13 scripts/work_queue/membership_emitter.py

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
    membership_period,
    membership_signups_for,
    membership_cancellations_for,
    membership_future_cancellations_for,
    membership_addon_count_for,
    membership_top_addons,
    membership_switched_to_gym_count,
    membership_not_using_count,
)


BASE_DIR = _HERE.parent.parent
STATE_DIR = BASE_DIR / "state"
WORK_QUEUE_FILE = STATE_DIR / "work-queue.json"

LOCATIONS = ("malaga", "ellenbrook")

# ── Thresholds ──────────────────────────────────────────────────────────────

# SAVE_CALL — per location
SAVE_CALL_MIN_FUTURE_CANCELLATIONS = 50    # below this, queue isn't worth a dedicated action
SAVE_CALL_TARGET_REDUCTION_PCT = 0.10      # 10% retention rate on the queue is realistic
SAVE_CALL_WINDOW_DAYS = 14

# CHURN_REASON — actionable reasons only
CHURN_REASON_NOT_USING_MIN = 10            # "not using membership enough" min count
CHURN_REASON_WINDOW_DAYS = 28              # behaviour change is slow

# SWITCH_DEFENCE — combined PGM + Cleverwaiver "switched to another gym"
SWITCH_DEFENCE_MIN_COUNT = 5
SWITCH_DEFENCE_WINDOW_DAYS = 28

# ADDON_UPSELL — Recovery is the premium differentiator
ADDON_TARGET_DELTA_RECOVERY = 30           # +30 active over 28d (doubling 30 → 60)
ADDON_UPSELL_WINDOW_DAYS = 28


# ── Helpers ──────────────────────────────────────────────────────────────────


def _display_location(loc: str) -> str:
    return loc.capitalize()


# ── Archetype emitters ───────────────────────────────────────────────────────


def _emit_save_call(week: str, start_serial: int) -> Tuple[List[WorkQueueAction], int]:
    """Per location, fires when future_cancellations > 50."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    for loc in LOCATIONS:
        queue_size = membership_future_cancellations_for(loc)
        if queue_size is None or queue_size <= SAVE_CALL_MIN_FUTURE_CANCELLATIONS:
            continue

        display = _display_location(loc)
        cancellations_baseline = membership_cancellations_for(loc) or 0
        # Target: 10% retention on the queue = (queue_size * 0.10) fewer cancellations
        save_count = max(5, int(queue_size * SAVE_CALL_TARGET_REDUCTION_PCT))
        target_cancellations = max(0, cancellations_baseline - save_count)
        target_future_queue = max(0, queue_size - save_count)

        actions.append(WorkQueueAction(
            id=make_action_id("mem", week, serial),
            source_page="membership",
            source_run_at=ts,
            title=f"Save-call queue at {display} — {queue_size} pending exits, target {save_count} saves",
            description=(
                f"{queue_size} members at {display} have filed cancellation but haven't left yet. "
                f"This is the highest-leverage queue in the dataset. Joanne pulls the future-cancellation "
                f"list from the CRM, prioritises members who joined ≥6 months ago (long-tenure save is "
                f"highest LTV), and runs save calls with a personalised offer: 1 month freeze + free PT "
                f"intro session OR addon upgrade trial. "
                f"Target: {save_count} retained ({SAVE_CALL_TARGET_REDUCTION_PCT*100:.0f}% conversion on "
                f"the queue), measured as a drop in weekly cancellations and a smaller future-queue."
            ),
            owner="Joanne",
            owner_role="Lead / Coord",
            priority="P1",
            effort_hours=4.0,
            category="membership",
            data_quality="high",
            projected_kpis=[
                ProjectedKPI(
                    metric="membership_cancellations_weekly",
                    keyword=loc,
                    baseline=cancellations_baseline,
                    target=float(target_cancellations),
                    measurement_window_days=SAVE_CALL_WINDOW_DAYS,
                    confidence="medium",
                ),
                ProjectedKPI(
                    metric="membership_future_cancellations",
                    keyword=loc,
                    baseline=queue_size,
                    target=float(target_future_queue),
                    measurement_window_days=SAVE_CALL_WINDOW_DAYS,
                    confidence="medium",
                ),
            ],
        ))
        serial += 1

    return actions, serial


def _emit_churn_reason(week: str, start_serial: int) -> Tuple[List[WorkQueueAction], int]:
    """Actionable churn reasons get dedicated campaigns."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    # 1) Not Using Membership Enough — onboarding / habit-build campaign
    not_using = membership_not_using_count()
    if not_using >= CHURN_REASON_NOT_USING_MIN:
        combined_cancel = membership_cancellations_for(None) or 0
        # Target: halve "not using" churn → estimated direct reduction
        target_total = max(0, combined_cancel - int(not_using * 0.50))

        actions.append(WorkQueueAction(
            id=make_action_id("mem", week, serial),
            source_page="membership",
            source_run_at=ts,
            title=f"Habit-build campaign — {not_using} 'not using enough' churns this week",
            description=(
                f"{not_using} members cited 'not using the membership enough' as their cancellation "
                f"reason (combined PGM + Cleverwaiver). This is the highest-leverage actionable reason "
                f"in the dataset — the member wanted value, the value wasn't activated. "
                f"Launch a habit-build sequence triggered at the 14-day post-signup mark: "
                f"(1) class booking nudge with personalised time recommendations, "
                f"(2) PT intro at 30d for members with <2 visits, "
                f"(3) addon trial day at 45d. "
                f"Target: halve 'not using' churn (~{int(not_using * 0.5)} retained) over 28 days, "
                f"reflected as a drop in combined weekly cancellations."
            ),
            owner="Joanne",
            owner_role="Lead / Coord",
            priority="P1",
            effort_hours=5.0,
            category="membership",
            data_quality="high",
            projected_kpis=[
                ProjectedKPI(
                    metric="membership_cancellations_weekly",
                    keyword=None,    # combined / totals
                    baseline=combined_cancel,
                    target=float(target_total),
                    measurement_window_days=CHURN_REASON_WINDOW_DAYS,
                    confidence="medium",
                ),
            ],
        ))
        serial += 1

    return actions, serial


def _emit_switch_defence(week: str, start_serial: int) -> Tuple[List[WorkQueueAction], int]:
    """Combined PGM + Cleverwaiver 'switched to another gym' ≥ threshold."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    switched = membership_switched_to_gym_count()
    if switched < SWITCH_DEFENCE_MIN_COUNT:
        return actions, serial

    combined_cancel = membership_cancellations_for(None) or 0
    # Target: halve switched-to-competitor losses
    target_total = max(0, combined_cancel - int(switched * 0.50))

    actions.append(WorkQueueAction(
        id=make_action_id("mem", week, serial),
        source_page="membership",
        source_run_at=ts,
        title=f"Competitive defence — {switched} members switched to another gym this week",
        description=(
            f"{switched} members cited 'switched to another gym' as their cancellation reason "
            f"(combined PGM + Cleverwaiver exit survey). This is direct competitive loss — these "
            f"members chose a specific alternative over CB247. "
            f"Investigate WHICH competitor (likely Revo Fitness — $9.69–$12.69/wk vs our $11.95 — "
            f"is the most price-aggressive Perth alternative). Pull the cancel notes from CRM for "
            f"these 20 members and flag any patterns: pricing, hours, specific facility. "
            f"Counter-campaign options: a 'don't leave for less' offer card at front desk, OR a "
            f"reinforced premium-differentiation push (Kids Hub + Sauna + Ice Bath — Revo doesn't "
            f"have ALL three). "
            f"Target: halve switched-to-competitor losses over 28 days."
        ),
        owner="Tia",
        owner_role="OS Owner / Operations",
        priority="P1",
        effort_hours=3.0,
        category="membership",
        data_quality="high",
        projected_kpis=[
            ProjectedKPI(
                metric="membership_cancellations_weekly",
                keyword=None,
                baseline=combined_cancel,
                target=float(target_total),
                measurement_window_days=SWITCH_DEFENCE_WINDOW_DAYS,
                confidence="medium",
            ),
        ],
    ))
    serial += 1

    return actions, serial


def _emit_addon_upsell(week: str, start_serial: int) -> Tuple[List[WorkQueueAction], int]:
    """Recovery (Sauna + Ice Bath) addon is THE premium differentiator vs Revo."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    recovery_addon = "Recovery (Sauna + Ice Bath)"
    current = membership_addon_count_for(recovery_addon)
    if current is None:
        return actions, serial

    target = current + ADDON_TARGET_DELTA_RECOVERY

    actions.append(WorkQueueAction(
        id=make_action_id("mem", week, serial),
        source_page="membership",
        source_run_at=ts,
        title=(
            f"Grow Recovery addon penetration — {current} active members, "
            f"target +{ADDON_TARGET_DELTA_RECOVERY} in {ADDON_UPSELL_WINDOW_DAYS}d"
        ),
        description=(
            f"Recovery (Sauna + Ice Bath) addon currently has only {current} active members — out "
            f"of an 8,000+ member base. This is CB247's strongest premium differentiator vs Revo "
            f"and Anytime (neither has both sauna + ice bath at all sites). "
            f"Three-prong upsell: "
            f"(1) Front-desk demo days — 'come try the contrast therapy', "
            f"(2) Member email campaign with the recovery-after-training value angle "
            f"(post-workout muscle soreness research), "
            f"(3) Bundle offer — Recovery addon + first month half-price for members hitting 6+ "
            f"visits/month (highest-engagement segment most likely to upgrade). "
            f"Target: {target} active Recovery members in {ADDON_UPSELL_WINDOW_DAYS} days "
            f"(doubling penetration)."
        ),
        owner="Tia",
        owner_role="OS Owner / Operations",
        priority="P2",
        effort_hours=4.0,
        category="membership",
        data_quality="high",
        projected_kpis=[
            ProjectedKPI(
                metric="membership_addon_active_count",
                keyword=recovery_addon,
                baseline=current,
                target=float(target),
                measurement_window_days=ADDON_UPSELL_WINDOW_DAYS,
                confidence="medium",
            ),
        ],
    ))
    serial += 1

    return actions, serial


# ── Orchestration ────────────────────────────────────────────────────────────


def emit_all_membership_actions() -> List[WorkQueueAction]:
    period = membership_period()
    if not period:
        print("[mem-emitter] no membership-data.json summary — exiting")
        return []

    week = week_iso()
    serial = 1

    save,    serial = _emit_save_call(week, serial)
    reason,  serial = _emit_churn_reason(week, serial)
    defend,  serial = _emit_switch_defence(week, serial)
    upsell,  serial = _emit_addon_upsell(week, serial)

    return save + reason + defend + upsell


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
        "generator_version": "1.5.0",   # bumped for Session 5e — ALL EMITTERS COMPLETE
        "actions": merged,
        "_added_this_run": added,
    }


def main():
    print(f"\n=== Membership Work Queue Emitter — {now_iso()} ===")

    period = membership_period()
    if period:
        print(f"Membership snapshot: {period.get('raw')}")

    # Print key context numbers
    combined_signups = membership_signups_for(None)
    combined_cancel = membership_cancellations_for(None)
    print(f"\nNet member movement this week: {combined_signups} new vs {combined_cancel} ended"
          f" = {(combined_signups or 0) - (combined_cancel or 0):+d}")

    for loc in LOCATIONS:
        s = membership_signups_for(loc)
        c = membership_cancellations_for(loc)
        f = membership_future_cancellations_for(loc)
        print(f"  {_display_location(loc):12s} signups={s}  ended={c}  future_queue={f}")

    print(f"\n  Switched-to-other-gym (combined): {membership_switched_to_gym_count()}")
    print(f"  Not-using-enough (combined):      {membership_not_using_count()}")
    print(f"  Top addons: {membership_top_addons(4)}")

    actions = emit_all_membership_actions()
    print(f"\nGenerated {len(actions)} candidate Membership actions for week {week_iso()}")

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
        f"[mem-emitter] {merged['_added_this_run']} new + "
        f"{len(merged['actions']) - merged['_added_this_run']} existing = "
        f"{len(merged['actions'])} total actions in {WORK_QUEUE_FILE}"
    )


if __name__ == "__main__":
    main()
