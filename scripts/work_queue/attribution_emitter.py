"""
attribution_emitter.py — emit a weekly CUMULATIVE ROI summary card.

Closes the loop opened by opportunity_emitter.py:
  opportunity_emitter   → emits per-keyword PAUSE/REDUCE actions
                          with projected_kpi ads_spend_saved_monthly
  team executes         → marks verdict (hit / partial / miss)
  measurement_runner    → updates each action's actual_kpis from current
                          Google Ads spend on that keyword
  attribution_emitter   → THIS SCRIPT. Aggregates the verdict-ed actions
                          into a SINGLE summary card with metric
                          cumulative_ads_savings_monthly.

The summary card is what Tia + Robert + Denver see in the management
report each week. Without it, the per-action measurements are operational
detail with no executive headline.

Window: rolling 28 days. Each weekly run produces ONE summary action for
the trailing 28-day period. Older summary cards are NOT deleted — they
form the historical trajectory ('SEO programme saved $X in May, $Y in
June, $Z in July...').

Inputs:
    state/work-queue.json    — read opportunity actions + their actual_kpis

Output:
    Merged into state/work-queue.json (one summary action per weekly run).

Run:
    .venv/bin/python3.13 scripts/work_queue/attribution_emitter.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

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


BASE_DIR        = _HERE.parent.parent
STATE_DIR       = BASE_DIR / "state"
WORK_QUEUE_FILE = STATE_DIR / "work-queue.json"

ATTRIBUTION_WINDOW_DAYS = 28


# ─── Load + filter ────────────────────────────────────────────────────────

def _load_work_queue() -> dict:
    if not WORK_QUEUE_FILE.exists():
        return {"actions": []}
    try:
        return json.loads(WORK_QUEUE_FILE.read_text())
    except Exception:
        return {"actions": []}


def _within_window(iso_ts: str, window_days: int) -> bool:
    """Was this timestamp within the last N days?"""
    if not iso_ts:
        return False
    try:
        ts = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except Exception:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    return ts >= cutoff


def _measured_savings(action: dict) -> float | None:
    """Extract actual $ saved from a verdict-ed opportunity action.

    Returns:
        positive number = saving achieved (baseline_spend - actual_current_spend)
        zero            = no saving (action shipped but spend stayed up)
        None            = no measurement yet (verdict still pending)
    """
    actuals = action.get("actual_kpis") or []
    if not actuals:
        return None
    projected = (action.get("projected_kpis") or [{}])[0]
    baseline = projected.get("baseline")
    if baseline is None:
        return None
    # Find the corresponding actual_kpi for ads_spend_saved_monthly
    for a in actuals:
        if a.get("metric") == "ads_spend_saved_monthly":
            current = a.get("actual_value")
            if current is None:
                return None
            saving = max(0, baseline - current)
            return saving
    return None


def _aggregate_savings() -> dict:
    """Walk work-queue, sum savings across opportunity actions verdict-ed
    in the last 28 days. Returns a summary dict."""
    wq = _load_work_queue()
    actions = wq.get("actions") or []

    # All opportunity actions verdict-ed in window
    window_actions = [
        a for a in actions
        if a.get("source_agent") == "opportunity-emitter"
        and a.get("overall_verdict") in {"winner", "partial_win"}
        and _within_window(a.get("measured_at", ""), ATTRIBUTION_WINDOW_DAYS)
    ]

    # Pending (emitted, not yet measured)
    pending_actions = [
        a for a in actions
        if a.get("source_agent") == "opportunity-emitter"
        and (a.get("overall_verdict") in (None, "pending"))
    ]

    total_saving = 0.0
    pause_count = 0
    reduce_count = 0
    keyword_list: list[str] = []
    for a in window_actions:
        s = _measured_savings(a)
        if s is None or s <= 0:
            continue
        total_saving += s
        title = (a.get("title") or "")
        if title.startswith("Pause"):
            pause_count += 1
        elif title.startswith("Reduce"):
            reduce_count += 1
        kpi = (a.get("projected_kpis") or [{}])[0]
        kw = kpi.get("keyword")
        if kw:
            keyword_list.append(kw)

    # Projected pipeline = what opportunity actions COULD save if hit
    projected_pipeline = 0.0
    for a in pending_actions:
        kpi = (a.get("projected_kpis") or [{}])[0]
        baseline = kpi.get("baseline") or 0
        target   = kpi.get("target") or 0
        projected_pipeline += (baseline - target)

    return {
        "actions_in_window": len(window_actions),
        "actions_pending":   len(pending_actions),
        "total_savings_mo":  round(total_saving, 2),
        "projected_pipeline_mo": round(projected_pipeline, 2),
        "pause_count":       pause_count,
        "reduce_count":      reduce_count,
        "top_keywords":      keyword_list[:5],
    }


# ─── Emit the summary card ────────────────────────────────────────────────

def _emit_summary(stats: dict) -> WorkQueueAction:
    week = week_iso()
    saved = stats["total_savings_mo"]
    pipeline = stats["projected_pipeline_mo"]
    pause_n = stats["pause_count"]
    reduce_n = stats["reduce_count"]
    pending_n = stats["actions_pending"]
    n_actioned = stats["actions_in_window"]

    if n_actioned == 0:
        # First-week state — no measured actions yet, only pipeline
        title = (
            f"ROI Pipeline: ${pipeline:.0f}/mo in identified savings opportunities "
            f"({pending_n} actions awaiting execution)"
        )
        description = (
            f"No paid→organic switches measured yet in the last "
            f"{ATTRIBUTION_WINDOW_DAYS} days — programme is still in pipeline phase. "
            f"opportunity_emitter has identified ${pipeline:.0f}/mo in potential "
            f"savings across {pending_n} keywords. Once Tia + John execute, "
            f"attribution measurement starts ~14 days after action."
        )
        priority = "P3"
        target = pipeline
    else:
        title = (
            f"ROI Realised: ${saved:.0f}/mo saved this month "
            f"({pause_n} paused + {reduce_n} reduced) "
            f"· Pipeline: ${pipeline:.0f}/mo more identified"
        )
        description = (
            f"Last {ATTRIBUTION_WINDOW_DAYS} days: {n_actioned} paid→organic "
            f"switches executed and measured. Actual savings: ${saved:.0f}/mo. "
            f"Top keywords: {', '.join(stats['top_keywords'][:3]) or '—'}. "
            f"Pipeline (not yet executed): ${pipeline:.0f}/mo across "
            f"{pending_n} additional opportunities. "
            f"Annualised: ${saved * 12:.0f}/year proven + ${pipeline * 12:.0f}/year potential."
        )
        priority = "P3"  # Informational summary, not an action
        target = saved + pipeline  # Total opportunity

    return WorkQueueAction(
        id=make_action_id("roi", week, 1),
        source_page="opportunity",
        source_run_at=now_iso(),
        title=title,
        description=description,
        owner="Tia",
        owner_role="OS Owner",
        priority=priority,
        effort_hours=0.1,   # ~6 min review only — informational summary
        category="roi-summary",
        data_quality="high",
        projected_kpis=[ProjectedKPI(
            metric="cumulative_ads_savings_monthly",
            measurement_window_days=ATTRIBUTION_WINDOW_DAYS,
            baseline=0,                              # Start of programme
            target=round(target, 2),                 # Total opportunity
            confidence="high",
        )],
        source_agent="attribution-emitter",
        # Optional: include the aggregate breakdown in notes for transparency
        notes_human=(
            f"Stats: {n_actioned} measured, {pending_n} pending. "
            f"Pause {pause_n}, Reduce {reduce_n}. "
            f"Realised ${saved:.2f}/mo, pipeline ${pipeline:.2f}/mo."
        ),
    )


def merge_with_existing(new_summary: WorkQueueAction) -> dict:
    """Replace any prior attribution-emitter summary card from THIS WEEK
    (matched by source_run_at within current ISO week — robust to ID
    format changes). Older summaries are preserved to form the trajectory."""
    wq = _load_work_queue()
    actions = wq.get("actions") or []
    week = week_iso()

    def _in_current_week(a: dict) -> bool:
        ts = a.get("source_run_at") or ""
        if not ts:
            return False
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            yr, wk, _ = dt.isocalendar()
            return f"{yr}w{wk:02d}" == week
        except Exception:
            return False

    actions = [
        a for a in actions
        if not (
            a.get("source_agent") == "attribution-emitter"
            and _in_current_week(a)
        )
    ]
    actions.append(to_jsonable(new_summary))
    wq["actions"] = actions
    wq["updated_at"] = now_iso()
    return wq


def main():
    print(f"[attribution-emitter] {now_iso()}")
    stats = _aggregate_savings()
    print(f"  In-window measured: {stats['actions_in_window']} actions")
    print(f"  Pending:            {stats['actions_pending']} actions")
    print(f"  Realised savings:   ${stats['total_savings_mo']:.2f}/mo")
    print(f"  Pipeline:           ${stats['projected_pipeline_mo']:.2f}/mo")

    summary = _emit_summary(stats)

    # Validate before writing
    errs = summary.validate()
    if errs:
        print(f"[attribution-emitter] validation failed: {errs}")
        sys.exit(1)

    merged = merge_with_existing(summary)
    WORK_QUEUE_FILE.write_text(json.dumps(merged, indent=2, ensure_ascii=False))
    print(f"[attribution-emitter] OK — summary card saved.")
    print(f"    Title: {summary.title}")


if __name__ == "__main__":
    main()
