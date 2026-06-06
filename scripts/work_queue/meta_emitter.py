"""
meta_emitter.py — emit structured Meta Ads actions to state/work-queue.json.

Reads state/ads-data.json (meta_ads block, latest week), picks ad-level
opportunities, and emits WorkQueueAction records with structured
projected_kpis.

Three action archetypes (in priority order):
  1. PAUSE     — ads burning spend at low CTR (kill the bleed)
  2. SCALE     — star performers hitting CTR + CPC thresholds
                 (lift budget to extract more from a working creative)
  3. REFRESH   — mid-tier ads w/ reasonable spend but mediocre CTR
                 (creative needs a swap)

Run:
    .venv/bin/python3.13 scripts/work_queue/meta_emitter.py

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
    meta_all_ads_latest,
    meta_latest_week,
    _meta_latest_week_full,
)


BASE_DIR = _HERE.parent.parent
STATE_DIR = BASE_DIR / "state"
WORK_QUEUE_FILE = STATE_DIR / "work-queue.json"

# ── Tunable thresholds (sized for CB247 current Meta spend ~$560/wk combined) ─

MAX_PAUSE_ACTIONS = 3
MAX_SCALE_ACTIONS = 3
MAX_REFRESH_ACTIONS = 3

# PAUSE — kill ads bleeding spend at low CTR
PAUSE_MIN_SPEND = 20.0          # AUD — ignore tiny spend ads
PAUSE_MAX_CTR = 1.30            # below this CTR = drag on account
PAUSE_MAX_CPC = 999.0           # not used as filter (high CPC is what we kill)

# SCALE — star performers worth more budget
SCALE_MIN_CTR = 2.00            # CTR ≥ 2.0%
SCALE_MAX_CPC = 0.50            # CPC ≤ $0.50
SCALE_MIN_SPEND = 20.0          # has to be spending real money already
SCALE_MIN_CLICKS = 50           # at least 50 clicks this week (signal not noise)

# REFRESH — mid-tier ads (creative needs a swap)
REFRESH_MIN_SPEND = 30.0
REFRESH_CTR_RANGE = (1.30, 2.00)   # in the meh zone


# ── Helpers ──────────────────────────────────────────────────────────────────


def _clean_ad_name(raw: str) -> str:
    """Tidy ad names for display (strip 'Instagram post: ', truncate)."""
    if not raw:
        return "(unnamed ad)"
    s = raw.strip()
    for prefix in ("Instagram post: ", "Post: ", "Promoting website: "):
        if s.startswith(prefix):
            s = s[len(prefix):].strip()
            break
    # Remove unicode escapes leftover in the JSON
    s = s.replace("—", "—").replace("…", "…")
    if len(s) > 60:
        s = s[:57] + "…"
    return s


def _account_label(ad: dict) -> str:
    """e.g. 'Malaga' or 'Ellenbrook'."""
    return (ad.get("location") or ad.get("account_name") or "CB247").strip()


# ── Archetype emitters ───────────────────────────────────────────────────────


def _emit_pause(ads: list, week: str, start_serial: int) -> Tuple[List[WorkQueueAction], int]:
    """Pause ads burning spend at low CTR."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    candidates = [
        ad for ad in ads
        if (ad.get("spend") or 0) >= PAUSE_MIN_SPEND
        and (ad.get("ctr") is not None)
        and ad["ctr"] < PAUSE_MAX_CTR
        and (ad.get("clicks") or 0) >= 1   # not a zero-click ad (different problem)
    ]
    # Worst CTR first (biggest drag = most urgent)
    candidates.sort(key=lambda a: (a.get("ctr") or 0))

    for ad in candidates[:MAX_PAUSE_ACTIONS]:
        name = _clean_ad_name(ad.get("name") or "")
        location = _account_label(ad)
        spend = float(ad.get("spend") or 0)
        ctr = float(ad.get("ctr") or 0)
        cpc = float(ad.get("cpc") or 0)
        clicks = int(ad.get("clicks") or 0)

        # CPC target: assume freed spend reallocates to better ads at the
        # account average — fairly aggressive but defensible.
        # (Account-level CPC is the verdict-time metric.)
        account_cpc = float(meta_latest_week().get("cpc") or 0.40) if meta_latest_week() else 0.40
        cpc_target = round(max(0.20, account_cpc * 0.90), 2)

        actions.append(WorkQueueAction(
            id=make_action_id("meta", week, serial),
            source_page="meta-ads",
            source_run_at=ts,
            title=f"Pause Meta ad '{name}' ({location}) — CTR {ctr:.2f}% at ${spend:.0f}/wk",
            description=(
                f"This ad spent ${spend:.0f} last week at {ctr:.2f}% CTR (CPC ${cpc:.2f}, {clicks} clicks) — "
                f"below the {PAUSE_MAX_CTR:.2f}% CTR floor for {location}. Pause in Meta Ads Manager and "
                f"reallocate the budget to the SCALE candidates this same cycle. Re-evaluate the creative "
                f"angle before relaunching."
            ),
            owner="Tia",
            owner_role="OS Owner / Paid Ads",
            priority="P1",
            effort_hours=0.25,
            category="meta",
            data_quality="high",
            projected_kpis=[
                ProjectedKPI(
                    metric="meta_cpc",
                    keyword=None,   # account-level
                    baseline=round(account_cpc, 2),
                    target=cpc_target,
                    measurement_window_days=7,
                    confidence="medium",
                ),
                ProjectedKPI(
                    metric="meta_ctr",
                    keyword=None,   # account-level lifts when drag is removed
                    baseline=round(float(meta_latest_week().get("ctr") or 1.9), 2),
                    delta_min=0.10,
                    delta_max=0.40,
                    measurement_window_days=7,
                    confidence="medium",
                ),
            ],
        ))
        serial += 1

    return actions, serial


def _emit_scale(ads: list, week: str, start_serial: int) -> Tuple[List[WorkQueueAction], int]:
    """Scale ads with strong CTR + low CPC + meaningful spend."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    candidates = [
        ad for ad in ads
        if (ad.get("ctr") or 0) >= SCALE_MIN_CTR
        and (ad.get("cpc") or 999) <= SCALE_MAX_CPC
        and (ad.get("spend") or 0) >= SCALE_MIN_SPEND
        and (ad.get("clicks") or 0) >= SCALE_MIN_CLICKS
    ]
    # Best CTR first
    candidates.sort(key=lambda a: (a.get("ctr") or 0), reverse=True)

    for ad in candidates[:MAX_SCALE_ACTIONS]:
        raw_name = ad.get("name") or ""
        name = _clean_ad_name(raw_name)
        location = _account_label(ad)
        spend = float(ad.get("spend") or 0)
        ctr = float(ad.get("ctr") or 0)
        cpc = float(ad.get("cpc") or 0)
        clicks = int(ad.get("clicks") or 0)
        reach = int(ad.get("reach") or 0)

        clicks_target = int(clicks * 1.45)         # +45% with +50% budget (some saturation)
        reach_target = int(reach * 1.30)

        actions.append(WorkQueueAction(
            id=make_action_id("meta", week, serial),
            source_page="meta-ads",
            source_run_at=ts,
            title=f"Scale Meta ad '{name}' ({location}) — CTR {ctr:.2f}%, CPC ${cpc:.2f}",
            description=(
                f"This ad is a winner: {ctr:.2f}% CTR, ${cpc:.2f} CPC, {clicks} clicks at ${spend:.0f} spend "
                f"last week. Increase daily budget by 50% in Meta Ads Manager. Monitor CPC for 3 days — "
                f"if CPC stays under ${cpc * 1.30:.2f}, hold the new budget through the cycle. "
                f"Target: +45% clicks at similar or better CPC."
            ),
            owner="Tia",
            owner_role="OS Owner / Paid Ads",
            priority="P1",
            effort_hours=0.25,
            category="meta",
            data_quality="high",
            projected_kpis=[
                ProjectedKPI(
                    metric="meta_ad_clicks_weekly",
                    keyword=raw_name,   # exact-or-prefix match to find this ad next week
                    baseline=clicks,
                    target=float(clicks_target),
                    measurement_window_days=7,
                    confidence="medium",
                ),
                ProjectedKPI(
                    metric="meta_ad_reach_weekly",
                    keyword=raw_name,
                    baseline=reach,
                    target=float(reach_target),
                    measurement_window_days=7,
                    confidence="medium",
                ),
                ProjectedKPI(
                    metric="meta_cpc",
                    keyword=raw_name,   # hold this ad's CPC steady
                    baseline=round(cpc, 2),
                    target=round(cpc * 1.20, 2),   # allow 20% drift up before we call it broken
                    measurement_window_days=7,
                    confidence="medium",
                ),
            ],
        ))
        serial += 1

    return actions, serial


def _emit_refresh(ads: list, week: str, start_serial: int) -> Tuple[List[WorkQueueAction], int]:
    """Mid-tier ads — reasonable spend, mediocre CTR — creative needs a swap."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    candidates = [
        ad for ad in ads
        if (ad.get("spend") or 0) >= REFRESH_MIN_SPEND
        and (ad.get("ctr") is not None)
        and REFRESH_CTR_RANGE[0] <= ad["ctr"] <= REFRESH_CTR_RANGE[1]
    ]
    # Highest spend first (biggest impact if creative lift sticks)
    candidates.sort(key=lambda a: (a.get("spend") or 0), reverse=True)

    for ad in candidates[:MAX_REFRESH_ACTIONS]:
        raw_name = ad.get("name") or ""
        name = _clean_ad_name(raw_name)
        location = _account_label(ad)
        spend = float(ad.get("spend") or 0)
        ctr = float(ad.get("ctr") or 0)
        clicks = int(ad.get("clicks") or 0)

        # Conservative target: +0.4pp absolute lift on CTR
        ctr_target = round(ctr + 0.40, 2)

        actions.append(WorkQueueAction(
            id=make_action_id("meta", week, serial),
            source_page="meta-ads",
            source_run_at=ts,
            title=f"Refresh creative for '{name}' ({location}) — CTR {ctr:.2f}% needs a lift",
            description=(
                f"This ad has reasonable reach (${spend:.0f} spend, {clicks} clicks) but CTR is stuck at "
                f"{ctr:.2f}% — neither bad enough to pause nor strong enough to scale. Shauna produces a "
                f"fresh creative variation (new hook, new visual, same offer). Swap in Meta Ads Manager "
                f"and run for 7 days. Target: CTR {ctr_target:.2f}% (+0.40pp absolute)."
            ),
            owner="Shauna",
            owner_role="Asset Creator (CB247)",
            priority="P2",
            effort_hours=2.0,
            category="meta",
            data_quality="high",
            projected_kpis=[
                ProjectedKPI(
                    metric="meta_ctr",
                    keyword=raw_name,
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


def emit_all_meta_actions() -> List[WorkQueueAction]:
    ads = meta_all_ads_latest()
    if not ads:
        print("[meta-emitter] no ad-level rows in latest meta_ads week — exiting")
        return []

    week = week_iso()
    serial = 1

    pause,   serial = _emit_pause(ads, week, serial)
    scale,   serial = _emit_scale(ads, week, serial)
    refresh, serial = _emit_refresh(ads, week, serial)

    return pause + scale + refresh


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
        "generator_version": "1.1.0",   # bumped for Session 5a
        "actions": merged,
        "_added_this_run": added,
    }


def main():
    print(f"\n=== Meta Ads Work Queue Emitter — {now_iso()} ===")

    wk = _meta_latest_week_full()
    if wk:
        print(f"Meta data window: {wk.get('start')} → {wk.get('end')} ({wk.get('week_label')})")
        combined = wk.get("combined") or {}
        print(
            f"Combined: spend=${combined.get('spend', 0):.0f}  clicks={combined.get('clicks', 0)}  "
            f"CTR={combined.get('ctr', 0):.2f}%  CPC=${combined.get('cpc', 0):.2f}"
        )

    actions = emit_all_meta_actions()
    print(f"Generated {len(actions)} candidate Meta actions for week {week_iso()}")

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
        f"[meta-emitter] {merged['_added_this_run']} new + "
        f"{len(merged['actions']) - merged['_added_this_run']} existing = "
        f"{len(merged['actions'])} total actions in {WORK_QUEUE_FILE}"
    )


if __name__ == "__main__":
    main()
