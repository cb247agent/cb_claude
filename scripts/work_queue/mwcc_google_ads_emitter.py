"""
mwcc_google_ads_emitter.py — emit structured Google Ads actions for MWCC.

Reads state/mwcc-ads.json (MWCC Google Ads, 19 campaigns total — only 3
typically active per week with spend > 0).

DATA QUIRK: MWCC Google Ads tracks conversions at account-level only, NOT
per-campaign. So per-campaign CPA shows as $0 / 0 conversions. We adapt
CB247's CPA-based archetypes to use CTR + spend signals instead.

Three archetypes:
  1. PAUSE     — active campaigns with poor CTR (< 1.0%) burning spend
  2. SCALE     — active campaigns with great CTR (> 2.0%) worth more budget
  3. OPTIMISE  — mid-tier campaigns (CTR 1.0–2.0%) needing tuning

Run:
    .venv/bin/python3.13 scripts/work_queue/mwcc_google_ads_emitter.py

Writes/updates: state/mwcc-work-queue.json (merges with existing actions)
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


BASE_DIR = _HERE.parent.parent
STATE_DIR = BASE_DIR / "state"
WORK_QUEUE_FILE = STATE_DIR / "mwcc-work-queue.json"
DATA_FILE = STATE_DIR / "mwcc-ads.json"

# ── Thresholds — sized for MWCC current weekly spend ~$1,800 ────────────────

MAX_PAUSE_ACTIONS = 3
MAX_SCALE_ACTIONS = 3
MAX_OPTIMISE_ACTIONS = 3

# PAUSE — campaigns with poor CTR burning spend
PAUSE_MIN_SPEND = 50.0
PAUSE_MAX_CTR = 1.00       # below 1% CTR with meaningful spend = waste
PAUSE_ZERO_CONV_MIN_CLICKS = 50  # broken funnel rule (if conversions per-campaign improves)
PAUSE_ZERO_CONV_MIN_SPEND = 50.0

# SCALE — high-CTR campaigns worth more budget
SCALE_MIN_CTR = 2.00
SCALE_MIN_SPEND = 50.0
SCALE_MIN_CLICKS = 20

# OPTIMISE — mid-tier
OPTIMISE_MIN_SPEND = 50.0
OPTIMISE_CTR_RANGE = (1.00, 2.00)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _load_data() -> dict:
    if not DATA_FILE.exists():
        return {}
    try:
        return json.loads(DATA_FILE.read_text())
    except Exception:
        return {}


def _enabled(c: dict) -> bool:
    """MWCC ads-data doesn't expose status reliably — treat any campaign with
    spend > 0 this week as 'active enough to action'."""
    return (c.get("spend") or 0) > 0


# ── Archetype emitters ───────────────────────────────────────────────────────


def _emit_pause(campaigns: list, week: str, start_serial: int) -> Tuple[List[WorkQueueAction], int]:
    """PAUSE: campaigns with poor CTR burning spend."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    candidates = [
        c for c in campaigns
        if _enabled(c)
        and (c.get("spend") or 0) >= PAUSE_MIN_SPEND
        and (c.get("ctr") or 0) < PAUSE_MAX_CTR
        and (c.get("clicks") or 0) >= 1
    ]
    candidates.sort(key=lambda c: (c.get("ctr") or 0))  # worst CTR first

    for c in candidates[:MAX_PAUSE_ACTIONS]:
        name = (c.get("name") or "").strip()
        spend = float(c.get("spend") or 0)
        ctr = float(c.get("ctr") or 0)
        cpc = float(c.get("cpc") or 0)
        clicks = int(c.get("clicks") or 0)

        actions.append(WorkQueueAction(
            id=make_action_id("gads-mwcc", week, serial),
            source_page="google-ads",
            source_run_at=ts,
            title=f"Pause MWCC Google Ads '{name}' — CTR {ctr:.2f}% on ${spend:.0f}/wk",
            description=(
                f"This campaign spent ${spend:.0f} last week at {ctr:.2f}% CTR ({clicks} clicks, "
                f"CPC ${cpc:.2f}) — below the {PAUSE_MAX_CTR:.2f}% floor. Pause in Google Ads, audit "
                f"keywords + ad copy, relaunch with tighter targeting. Reallocate budget to "
                f"higher-CTR campaigns (Brand or Performance Max if performing). "
                f"Note: MWCC tracks conversions at account-level only — per-campaign attribution "
                f"isn't available yet. CTR is the proxy signal."
            ),
            owner="Tia",
            owner_role="OS Owner / Paid Ads",
            priority="P1",
            effort_hours=0.5,
            category="google-ads",
            data_quality="medium",
            projected_kpis=[
                ProjectedKPI(
                    metric="google_ads_ctr",
                    keyword=name,
                    baseline=round(ctr, 2),
                    target=round(max(0.50, ctr * 0.5), 2),  # spend drops, CTR effectively zero
                    measurement_window_days=14,
                    confidence="medium",
                ),
                ProjectedKPI(
                    metric="google_ads_spend_weekly",
                    keyword=name,
                    baseline=round(spend, 2),
                    target=5.0,
                    measurement_window_days=14,
                    confidence="high",
                ),
            ],
        ))
        serial += 1

    return actions, serial


def _emit_scale(campaigns: list, week: str, start_serial: int) -> Tuple[List[WorkQueueAction], int]:
    """SCALE: high-CTR campaigns worth more budget."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    candidates = [
        c for c in campaigns
        if _enabled(c)
        and (c.get("ctr") or 0) >= SCALE_MIN_CTR
        and (c.get("spend") or 0) >= SCALE_MIN_SPEND
        and (c.get("clicks") or 0) >= SCALE_MIN_CLICKS
    ]
    candidates.sort(key=lambda c: (c.get("ctr") or 0), reverse=True)

    for c in candidates[:MAX_SCALE_ACTIONS]:
        name = (c.get("name") or "").strip()
        spend = float(c.get("spend") or 0)
        ctr = float(c.get("ctr") or 0)
        cpc = float(c.get("cpc") or 0)
        clicks = int(c.get("clicks") or 0)

        clicks_target = int(clicks * 1.40)

        actions.append(WorkQueueAction(
            id=make_action_id("gads-mwcc", week, serial),
            source_page="google-ads",
            source_run_at=ts,
            title=f"Scale MWCC Google Ads '{name}' — CTR {ctr:.2f}%, CPC ${cpc:.2f}",
            description=(
                f"This campaign is winning: {ctr:.2f}% CTR (above {SCALE_MIN_CTR:.1f}% threshold), "
                f"{clicks} clicks at ${spend:.0f} spend with ${cpc:.2f} CPC. Increase daily budget "
                f"by 50% in Google Ads. Monitor CPC for 5 days — if it stays under ${cpc * 1.30:.2f}, "
                f"hold the new budget through the cycle. Target: +40% clicks at similar or better CPC."
            ),
            owner="Tia",
            owner_role="OS Owner / Paid Ads",
            priority="P1",
            effort_hours=0.25,
            category="google-ads",
            data_quality="medium",
            projected_kpis=[
                ProjectedKPI(
                    metric="google_ads_clicks_weekly",
                    keyword=name,
                    baseline=clicks,
                    target=float(clicks_target),
                    measurement_window_days=14,
                    confidence="medium",
                ),
                ProjectedKPI(
                    metric="google_ads_ctr",
                    keyword=name,
                    baseline=round(ctr, 2),
                    target=round(ctr, 2),  # hold the high CTR
                    measurement_window_days=14,
                    confidence="medium",
                ),
            ],
        ))
        serial += 1

    return actions, serial


def _emit_optimise(campaigns: list, week: str, start_serial: int) -> Tuple[List[WorkQueueAction], int]:
    """OPTIMISE: mid-tier campaigns (CTR 1.0-2.0%) — room to tune."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    ctr_min, ctr_max = OPTIMISE_CTR_RANGE
    candidates = [
        c for c in campaigns
        if _enabled(c)
        and (c.get("spend") or 0) >= OPTIMISE_MIN_SPEND
        and ctr_min <= (c.get("ctr") or 0) <= ctr_max
    ]
    candidates.sort(key=lambda c: (c.get("spend") or 0), reverse=True)  # highest spend first

    for c in candidates[:MAX_OPTIMISE_ACTIONS]:
        name = (c.get("name") or "").strip()
        spend = float(c.get("spend") or 0)
        ctr = float(c.get("ctr") or 0)

        ctr_target = round(min(2.50, ctr + 0.50), 2)

        actions.append(WorkQueueAction(
            id=make_action_id("gads-mwcc", week, serial),
            source_page="google-ads",
            source_run_at=ts,
            title=f"Optimise MWCC Google Ads '{name}' — CTR {ctr:.2f}% (target +0.5pp)",
            description=(
                f"This campaign spent ${spend:.0f} last week at {ctr:.2f}% CTR — not bad enough to "
                f"pause, not strong enough to scale. Audit search-term report for low-relevance "
                f"clicks, add negatives. Test new ad copy variations. Check landing page match — "
                f"does the ad headline match the page H1 and the searcher intent? "
                f"Target: CTR {ctr_target:.2f}% within 14 days."
            ),
            owner="John",
            owner_role="SEO / Web Specialist",
            priority="P2",
            effort_hours=1.5,
            category="google-ads",
            data_quality="medium",
            projected_kpis=[
                ProjectedKPI(
                    metric="google_ads_ctr",
                    keyword=name,
                    baseline=round(ctr, 2),
                    target=ctr_target,
                    measurement_window_days=14,
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
        print("[mwcc-gads-emitter] no state/mwcc-ads.json — exiting")
        return []

    campaigns = data.get("campaigns") or []
    if not campaigns:
        print("[mwcc-gads-emitter] no campaigns in data — exiting")
        return []

    print(f"MWCC Google Ads window: {data.get('date_range', {}).get('start')} → {data.get('date_range', {}).get('end')}")
    totals = data.get("totals") or {}
    print(f"Account totals: spend=${totals.get('spend', 0):.0f}  CTR={totals.get('ctr', 0):.2f}%  CPC=${totals.get('cpc', 0):.2f}")

    week = week_iso()
    serial = 1

    pause,    serial = _emit_pause(campaigns, week, serial)
    scale,    serial = _emit_scale(campaigns, week, serial)
    optimise, serial = _emit_optimise(campaigns, week, serial)

    return pause + scale + optimise


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
    print(f"\n=== MWCC Google Ads Work Queue Emitter — {now_iso()} ===")

    actions = emit_all()
    print(f"\nGenerated {len(actions)} MWCC Google Ads actions for week {week_iso()}")

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
            tgt = primary.target if primary.target is not None else "?"
            print(f"  - {a.title}")
            print(f"      → {primary.metric} baseline={base} target={tgt}")
        print()

    STATE_DIR.mkdir(exist_ok=True)
    merged = merge_with_existing(actions)
    WORK_QUEUE_FILE.write_text(json.dumps(merged, indent=2, default=str))
    print(
        f"[mwcc-gads-emitter] {merged['_added_this_run']} new + "
        f"{len(merged['actions']) - merged['_added_this_run']} existing = "
        f"{len(merged['actions'])} total actions in {WORK_QUEUE_FILE}"
    )


if __name__ == "__main__":
    main()
