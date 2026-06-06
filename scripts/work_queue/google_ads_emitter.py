"""
google_ads_emitter.py — emit structured Google Ads actions to state/work-queue.json.

Reads state/ads-data.json (google_ads block, latest week), picks campaign-level
opportunities, and emits WorkQueueAction records with structured projected_kpis.

Three action archetypes (in priority order):
  1. PAUSE      — campaigns with cpa > 3x account avg OR zero conv at 50+ clicks
  2. SCALE      — campaigns with cpa ≤ 0.5x account avg AND conv ≥ 5
  3. OPTIMISE   — mid-tier campaigns (1.5x < cpa ≤ 3x) needing keyword/landing tune

Run:
    .venv/bin/python3.13 scripts/work_queue/google_ads_emitter.py

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
    _google_ads_latest_week_full,
    google_ads_all_campaigns_latest,
    google_ads_cpa_baseline,
    google_ads_latest_week,
)


BASE_DIR = _HERE.parent.parent
STATE_DIR = BASE_DIR / "state"
WORK_QUEUE_FILE = STATE_DIR / "work-queue.json"

# ── Tunable thresholds (CB247: combined Google Ads spend ~$720/wk, CPA ~$10) ──

MAX_PAUSE_ACTIONS = 3
MAX_SCALE_ACTIONS = 3
MAX_OPTIMISE_ACTIONS = 3

# PAUSE — campaigns burning money
PAUSE_CPA_MULTIPLIER = 3.0      # >3x account CPA = bleeding
PAUSE_MIN_SPEND = 50.0          # ignore micro-spend campaigns
PAUSE_ZERO_CONV_MIN_CLICKS = 50 # zero-conv kill rule (broken funnel)
PAUSE_ZERO_CONV_MIN_SPEND = 30.0

# SCALE — campaigns crushing it
SCALE_CPA_MULTIPLIER = 0.5      # ≤0.5x account CPA = stellar
SCALE_MIN_CONV = 5              # at least 5 conversions
SCALE_MIN_SPEND = 50.0

# OPTIMISE — mid-tier
OPTIMISE_CPA_MIN_MULTIPLIER = 1.5
OPTIMISE_CPA_MAX_MULTIPLIER = 3.0   # PAUSE territory above this
OPTIMISE_MIN_SPEND = 50.0


# ── Helpers ──────────────────────────────────────────────────────────────────


def _enabled(c: dict) -> bool:
    return (c.get("status") or "").upper() == "ENABLED"


def _scope_key(c: dict) -> str:
    """Build the keyword scope used by lookups. PMax appears in both locations,
    so always disambiguate with [Location] suffix when location is present."""
    name = (c.get("name") or "").strip()
    loc = (c.get("location") or "").strip()
    return f"{name} [{loc}]" if loc else name


# ── Archetype emitters ───────────────────────────────────────────────────────


def _emit_pause(campaigns: list, account_cpa: float, week: str, start_serial: int) -> Tuple[List[WorkQueueAction], int]:
    """PAUSE: campaigns bleeding money at >3x account CPA or zero-conv with clicks."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    high_cpa_threshold = account_cpa * PAUSE_CPA_MULTIPLIER

    candidates = []
    for c in campaigns:
        if not _enabled(c):
            continue
        spend = float(c.get("spend") or 0)
        clicks = int(c.get("clicks") or 0)
        conv = int(c.get("conv") or 0)
        cpa = float(c.get("cpa") or 0)

        # Rule A: high CPA + meaningful spend + has converted at least once
        if cpa > high_cpa_threshold and spend >= PAUSE_MIN_SPEND and conv >= 1:
            candidates.append((c, "high_cpa"))
            continue
        # Rule B: zero conv but real click traffic = broken funnel
        if conv == 0 and clicks >= PAUSE_ZERO_CONV_MIN_CLICKS and spend >= PAUSE_ZERO_CONV_MIN_SPEND:
            candidates.append((c, "zero_conv"))

    # Worst CPA / biggest spend first
    candidates.sort(
        key=lambda pair: (pair[0].get("cpa") or 0, pair[0].get("spend") or 0),
        reverse=True,
    )

    for c, reason in candidates[:MAX_PAUSE_ACTIONS]:
        name = (c.get("name") or "").strip()
        location = (c.get("location") or "").strip() or "Combined"
        spend = float(c.get("spend") or 0)
        clicks = int(c.get("clicks") or 0)
        conv = int(c.get("conv") or 0)
        cpa = float(c.get("cpa") or 0)

        if reason == "zero_conv":
            description = (
                f"This campaign spent ${spend:.0f} on {clicks} clicks last week and produced 0 conversions. "
                f"Either the landing page is broken, the keyword–intent match is wrong, or tracking is "
                f"misfiring. Pause in Google Ads, audit conversion tracking + landing page CTA, then "
                f"restart only after the funnel issue is fixed. Reallocate spend to PMax: Local Campaign "
                f"(Ellenbrook) which is converting at $2.48 CPA."
            )
        else:
            description = (
                f"Campaign CPA is ${cpa:.2f} — {cpa / account_cpa:.1f}x the account average of "
                f"${account_cpa:.2f}. Spent ${spend:.0f} for only {conv} conversions. Pause in Google Ads, "
                f"audit the negative keyword list + search-term report to find low-intent waste, then "
                f"relaunch with tighter targeting. Reallocate budget to high-efficiency PMax (Ellenbrook)."
            )

        # Account-level CPA should drop when we kill drag.
        target_account_cpa = round(account_cpa * 0.90, 2)

        actions.append(WorkQueueAction(
            id=make_action_id("gads", week, serial),
            source_page="google-ads",
            source_run_at=ts,
            title=f"Pause Google Ads campaign '{name}' ({location}) — CPA ${cpa:.2f} on ${spend:.0f}/wk",
            description=description,
            owner="Tia",
            owner_role="OS Owner / Paid Ads",
            priority="P1",
            effort_hours=0.5,
            category="google-ads",
            data_quality="high",
            projected_kpis=[
                ProjectedKPI(
                    metric="google_ads_cpa",
                    keyword=None,    # account-level (drag removal benefit)
                    baseline=round(account_cpa, 2),
                    target=target_account_cpa,
                    measurement_window_days=14,
                    confidence="medium",
                ),
                ProjectedKPI(
                    metric="google_ads_spend_weekly",
                    keyword=_scope_key(c),   # this specific campaign should drop to ~0
                    baseline=round(spend, 2),
                    target=5.0,
                    measurement_window_days=14,
                    confidence="high",
                ),
            ],
        ))
        serial += 1

    return actions, serial


def _emit_scale(campaigns: list, account_cpa: float, week: str, start_serial: int) -> Tuple[List[WorkQueueAction], int]:
    """SCALE: campaigns with CPA ≤ 0.5x account avg AND conv ≥ 5."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    low_cpa_threshold = account_cpa * SCALE_CPA_MULTIPLIER

    candidates = [
        c for c in campaigns
        if _enabled(c)
        and (c.get("cpa") or 999) <= low_cpa_threshold
        and (c.get("conv") or 0) >= SCALE_MIN_CONV
        and (c.get("spend") or 0) >= SCALE_MIN_SPEND
        and (c.get("cpa") or 0) > 0   # cpa=0 means no conversion data, not "free"
    ]
    # Most efficient first
    candidates.sort(key=lambda c: (c.get("cpa") or 0))

    for c in candidates[:MAX_SCALE_ACTIONS]:
        name = (c.get("name") or "").strip()
        location = (c.get("location") or "").strip() or "Combined"
        spend = float(c.get("spend") or 0)
        conv = int(c.get("conv") or 0)
        cpa = float(c.get("cpa") or 0)
        clicks = int(c.get("clicks") or 0)

        # +50% budget → expect +35–45% conv (some saturation)
        conv_target = int(conv * 1.40)
        clicks_target = int(clicks * 1.40)

        actions.append(WorkQueueAction(
            id=make_action_id("gads", week, serial),
            source_page="google-ads",
            source_run_at=ts,
            title=f"Scale Google Ads campaign '{name}' ({location}) — CPA ${cpa:.2f}, {conv} conv",
            description=(
                f"This campaign is a winner: ${cpa:.2f} CPA ({cpa / account_cpa:.2f}x the $%.2f account "
                f"average), {conv} conversions on ${spend:.0f} spend last week. Increase daily budget by "
                f"50%% in Google Ads. Monitor CPA for 5 days — if it stays under ${cpa * 1.35:.2f}, hold "
                f"the new budget through the cycle. Target: +40%% conversions at similar or better CPA."
            ) % account_cpa,
            owner="Tia",
            owner_role="OS Owner / Paid Ads",
            priority="P1",
            effort_hours=0.25,
            category="google-ads",
            data_quality="high",
            projected_kpis=[
                ProjectedKPI(
                    metric="google_ads_conversions_weekly",
                    keyword=_scope_key(c),
                    baseline=conv,
                    target=float(conv_target),
                    measurement_window_days=14,
                    confidence="medium",
                ),
                ProjectedKPI(
                    metric="google_ads_clicks_weekly",
                    keyword=_scope_key(c),
                    baseline=clicks,
                    target=float(clicks_target),
                    measurement_window_days=14,
                    confidence="medium",
                ),
                ProjectedKPI(
                    metric="google_ads_cpa",
                    keyword=_scope_key(c),
                    baseline=round(cpa, 2),
                    target=round(cpa * 1.35, 2),   # allow up to 35% CPA drift before "broken"
                    measurement_window_days=14,
                    confidence="medium",
                ),
            ],
        ))
        serial += 1

    return actions, serial


def _emit_optimise(campaigns: list, account_cpa: float, week: str, start_serial: int) -> Tuple[List[WorkQueueAction], int]:
    """OPTIMISE: mid-tier campaigns (1.5x < CPA ≤ 3x account avg)."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    cpa_floor = account_cpa * OPTIMISE_CPA_MIN_MULTIPLIER
    cpa_ceiling = account_cpa * OPTIMISE_CPA_MAX_MULTIPLIER

    candidates = [
        c for c in campaigns
        if _enabled(c)
        and (c.get("spend") or 0) >= OPTIMISE_MIN_SPEND
        and (c.get("cpa") or 0) > cpa_floor
        and (c.get("cpa") or 0) <= cpa_ceiling
    ]
    # Highest spend first (biggest dollars to recover with optimisation)
    candidates.sort(key=lambda c: (c.get("spend") or 0), reverse=True)

    for c in candidates[:MAX_OPTIMISE_ACTIONS]:
        name = (c.get("name") or "").strip()
        location = (c.get("location") or "").strip() or "Combined"
        spend = float(c.get("spend") or 0)
        conv = int(c.get("conv") or 0)
        cpa = float(c.get("cpa") or 0)

        # Target: pull CPA down to the account average (achievable if waste is real)
        cpa_target = round(account_cpa, 2)

        actions.append(WorkQueueAction(
            id=make_action_id("gads", week, serial),
            source_page="google-ads",
            source_run_at=ts,
            title=f"Optimise '{name}' ({location}) — CPA ${cpa:.2f} vs ${account_cpa:.2f} account avg",
            description=(
                f"Campaign CPA is ${cpa:.2f} ({cpa / account_cpa:.1f}x account avg of ${account_cpa:.2f}) — "
                f"not bad enough to pause, but leaving money on the table. "
                f"Spent ${spend:.0f} for {conv} conversions last week. "
                f"Action: pull the 14-day search-term report and add the bottom 20 zero-conversion terms "
                f"as negatives. Check landing page match — does the page headline match the ad headline "
                f"and the searcher intent? Target: pull CPA to account average (${cpa_target:.2f}) "
                f"within 14 days."
            ),
            owner="John",
            owner_role="SEO / Web Specialist",
            priority="P2",
            effort_hours=1.5,
            category="google-ads",
            data_quality="high",
            projected_kpis=[
                ProjectedKPI(
                    metric="google_ads_cpa",
                    keyword=_scope_key(c),
                    baseline=round(cpa, 2),
                    target=cpa_target,
                    measurement_window_days=14,
                    confidence="medium",
                ),
            ],
        ))
        serial += 1

    return actions, serial


# ── Orchestration ────────────────────────────────────────────────────────────


def emit_all_google_ads_actions() -> List[WorkQueueAction]:
    campaigns = google_ads_all_campaigns_latest()
    if not campaigns:
        print("[gads-emitter] no campaign rows in latest google_ads week — exiting")
        return []

    account_cpa = google_ads_cpa_baseline()
    if account_cpa is None or account_cpa <= 0:
        print("[gads-emitter] could not compute account CPA baseline — exiting")
        return []

    print(f"Account CPA baseline: ${account_cpa:.2f}")
    print(f"  PAUSE threshold:    cpa > ${account_cpa * PAUSE_CPA_MULTIPLIER:.2f}")
    print(f"  OPTIMISE threshold: ${account_cpa * OPTIMISE_CPA_MIN_MULTIPLIER:.2f} < cpa ≤ ${account_cpa * OPTIMISE_CPA_MAX_MULTIPLIER:.2f}")
    print(f"  SCALE threshold:    cpa ≤ ${account_cpa * SCALE_CPA_MULTIPLIER:.2f} AND conv ≥ {SCALE_MIN_CONV}")

    week = week_iso()
    serial = 1

    pause,    serial = _emit_pause(campaigns, account_cpa, week, serial)
    scale,    serial = _emit_scale(campaigns, account_cpa, week, serial)
    optimise, serial = _emit_optimise(campaigns, account_cpa, week, serial)

    return pause + scale + optimise


def merge_with_existing(new_actions: List[WorkQueueAction]) -> dict:
    """
    Merge into state/work-queue.json without overwriting existing IDs.
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
        "generator_version": "1.2.0",   # bumped for Session 5b
        "actions": merged,
        "_added_this_run": added,
    }


def main():
    print(f"\n=== Google Ads Work Queue Emitter — {now_iso()} ===")

    wk = _google_ads_latest_week_full()
    if wk:
        print(f"Google Ads window: {wk.get('date_start')} → {wk.get('date_end')} ({wk.get('week_label')})")
        combined = wk.get("combined") or {}
        print(
            f"Combined: spend=${combined.get('spend', 0):.0f}  conv={combined.get('conv', 0)}  "
            f"CPA=${combined.get('cpa', 0):.2f}  CTR={combined.get('ctr', 0):.2f}%"
        )

    actions = emit_all_google_ads_actions()
    print(f"\nGenerated {len(actions)} candidate Google Ads actions for week {week_iso()}")

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
        f"[gads-emitter] {merged['_added_this_run']} new + "
        f"{len(merged['actions']) - merged['_added_this_run']} existing = "
        f"{len(merged['actions'])} total actions in {WORK_QUEUE_FILE}"
    )


if __name__ == "__main__":
    main()
