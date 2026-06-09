"""
opportunity_emitter.py — emit paid→organic SWITCH opportunities to Work Queue.

Closes Tia's stated strategic loop: reduce Google Ads spend by replacing
paid traffic with organic. Joins Google Ads search-terms ↔ GSC queries,
identifies keywords where CB247 ranks organically well enough to safely
reduce paid spend.

Three action archetypes (priority order):
  1. PAUSE     — paid keywords where CB247 ranks GSC #1-#3 organically
                 (don't pause brand-defence keywords — exception list)
  2. REDUCE    — paid keywords where CB247 ranks GSC #4-#10 (50% budget cut)
  3. (MAINTAIN — paid keywords where CB247 ranks GSC #11+ or no rank — KEEP
                 paid; no action emitted, but logged for visibility)

Each action carries a projected_kpi of `ads_spend_saved_monthly` with
baseline=current_monthly_spend and target=0 (PAUSE) or target=0.5×baseline
(REDUCE). measurement_runner.py picks them up at verdict time and computes
the actual saving from next-month Google Ads pull.

Inputs:
    state/google-ads-data.json  → search_terms array (cost + impressions)
    state/gsc-data.json         → top_queries array (position + clicks)

Output:
    Merged into state/work-queue.json (source_page='opportunity').
    Picked up by sync_to_supabase.py in the same Phase 1 sequence.

Run:
    .venv/bin/python3.13 scripts/work_queue/opportunity_emitter.py
"""

from __future__ import annotations

import json
import re
import sys
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

# ─── Tunable thresholds ───────────────────────────────────────────────────
PAUSE_MIN_WEEKLY_SPEND   = 5.0      # Only worth pausing if spending ≥$5/wk
PAUSE_MAX_GSC_POSITION   = 3.0      # Organic #1-#3 → pause paid

REDUCE_MIN_WEEKLY_SPEND  = 10.0     # Slightly higher bar for budget cut
REDUCE_GSC_POSITION_MIN  = 4.0
REDUCE_GSC_POSITION_MAX  = 10.0
REDUCE_BUDGET_CUT_PCT    = 0.50     # 50% of baseline

MAX_PAUSE_ACTIONS  = 5
MAX_REDUCE_ACTIONS = 3

# ─── Brand-defence keyword guard (NEVER pause these even if organic #1) ──
# Pausing brand keywords risks competitor poaching the SERP.
BRAND_DEFENCE_PATTERNS = [
    r"chasing\s*better",
    r"\bcb247\b",
    r"chasingbetter247",
]


def _is_brand_defence(term: str) -> bool:
    t = (term or "").lower()
    return any(re.search(p, t) for p in BRAND_DEFENCE_PATTERNS)


# ─── Data loaders ────────────────────────────────────────────────────────

def _load_search_terms() -> list[dict]:
    """Load Google Ads search-terms from this week's pull."""
    f = STATE_DIR / "google-ads-data.json"
    if not f.exists():
        print("[opportunity-emitter] state/google-ads-data.json missing")
        return []
    try:
        d = json.loads(f.read_text())
        return d.get("search_terms") or []
    except Exception as e:
        print(f"[opportunity-emitter] could not parse google-ads-data.json: {e}")
        return []


def _gsc_position_index() -> dict[str, dict]:
    """Build a {lowercased_query: {position, clicks, impressions, ctr}} map."""
    f = STATE_DIR / "gsc-data.json"
    if not f.exists():
        return {}
    try:
        d = json.loads(f.read_text())
    except Exception:
        return {}
    idx: dict[str, dict] = {}
    for q in (d.get("top_queries") or []):
        key = (q.get("query") or "").strip().lower()
        if key:
            idx[key] = q
    return idx


def _match_gsc(term: str, gsc_idx: dict[str, dict]) -> dict | None:
    """Find a GSC row matching this Ads search term. Exact match first, then
    suffix/substring fallback. Returns the matched GSC row or None."""
    if not term:
        return None
    t = term.lower().strip()
    if t in gsc_idx:
        return gsc_idx[t]
    # Try variant: GSC sometimes has 'chasing better malaga' vs Ads 'cb247 malaga'
    # Skip variant matching for now — exact + substring is enough for v1.
    for key, row in gsc_idx.items():
        if t in key or key in t:
            return row
    return None


# ─── Emitters ────────────────────────────────────────────────────────────

def _emit_pause(search_terms: list[dict], gsc_idx: dict[str, dict],
                week: str, start_serial: int) -> tuple[List[WorkQueueAction], int]:
    """Emit PAUSE actions for paid keywords MWCC ranks GSC #1-#3."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    # Build candidate list — keep all the data we need for ranking + brief
    candidates = []
    for st in search_terms:
        term = st.get("search_term", "")
        weekly_spend = float(st.get("cost") or 0)
        if weekly_spend < PAUSE_MIN_WEEKLY_SPEND:
            continue
        if _is_brand_defence(term):
            continue
        gsc_row = _match_gsc(term, gsc_idx)
        if not gsc_row:
            continue
        gsc_pos = gsc_row.get("position")
        if gsc_pos is None or gsc_pos > PAUSE_MAX_GSC_POSITION:
            continue
        # Compute projected monthly saving — weekly_spend × 4.3 (avg weeks/mo)
        # × 0.95 safety (organic CTR may need slight ramp-up)
        projected_monthly_saving = round(weekly_spend * 4.3 * 0.95, 2)
        candidates.append({
            "term":             term,
            "weekly_spend":     weekly_spend,
            "projected_saving": projected_monthly_saving,
            "campaign":         st.get("campaign", ""),
            "location":         st.get("location", ""),
            "gsc_position":     gsc_pos,
            "gsc_clicks":       gsc_row.get("clicks", 0),
            "gsc_ctr":          gsc_row.get("ctr", 0),
            "ads_clicks":       st.get("clicks", 0),
            "ads_conv":         st.get("conv", 0),
        })

    candidates.sort(key=lambda c: c["projected_saving"], reverse=True)

    for c in candidates[:MAX_PAUSE_ACTIONS]:
        baseline = round(c["weekly_spend"] * 4.3, 2)  # current monthly spend
        target   = 0
        action = WorkQueueAction(
            id=make_action_id("opp", week, serial),
            source_page="opportunity",
            source_run_at=ts,
            title=(
                f"Pause Google Ads for '{c['term']}' — projected ${c['projected_saving']:.0f}/mo saving "
                f"(organic #{c['gsc_position']:.1f})"
            ),
            description=(
                f"Currently spending ${c['weekly_spend']:.2f}/wk on this keyword "
                f"({c['campaign']}, {c['location'] or 'all locations'}). CB247 "
                f"ranks organic position #{c['gsc_position']:.1f} with "
                f"{c['gsc_clicks']} clicks/wk at {c['gsc_ctr']*100:.1f}% CTR. "
                f"Pausing paid will redirect that intent to organic at $0 cost. "
                f"Risk: low — strong organic CTR confirms users find us. "
                f"Action: pause keyword in Google Ads. Re-emit if organic clicks "
                f"drop materially after 2 weeks."
            ),
            owner="Tia",
            owner_role="OS Owner",
            priority="P1",
            effort_hours=0.5,
            category="opportunity",
            data_quality="high",
            projected_kpis=[ProjectedKPI(
                metric="ads_spend_saved_monthly",
                measurement_window_days=28,
                keyword=c["term"],
                baseline=baseline,
                target=target,
                confidence="high",
            )],
            source_agent="opportunity-emitter",
        )
        actions.append(action)
        serial += 1
    return actions, serial


def _emit_reduce(search_terms: list[dict], gsc_idx: dict[str, dict],
                 week: str, start_serial: int) -> tuple[List[WorkQueueAction], int]:
    """Emit REDUCE-50% actions for paid keywords ranking GSC #4-#10."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    candidates = []
    for st in search_terms:
        term = st.get("search_term", "")
        weekly_spend = float(st.get("cost") or 0)
        if weekly_spend < REDUCE_MIN_WEEKLY_SPEND:
            continue
        if _is_brand_defence(term):
            continue
        gsc_row = _match_gsc(term, gsc_idx)
        if not gsc_row:
            continue
        gsc_pos = gsc_row.get("position")
        if gsc_pos is None:
            continue
        if not (REDUCE_GSC_POSITION_MIN <= gsc_pos <= REDUCE_GSC_POSITION_MAX):
            continue
        projected_monthly_saving = round(weekly_spend * 4.3 * REDUCE_BUDGET_CUT_PCT, 2)
        candidates.append({
            "term":             term,
            "weekly_spend":     weekly_spend,
            "projected_saving": projected_monthly_saving,
            "campaign":         st.get("campaign", ""),
            "location":         st.get("location", ""),
            "gsc_position":     gsc_pos,
            "gsc_clicks":       gsc_row.get("clicks", 0),
        })

    candidates.sort(key=lambda c: c["projected_saving"], reverse=True)

    for c in candidates[:MAX_REDUCE_ACTIONS]:
        baseline = round(c["weekly_spend"] * 4.3, 2)
        target   = round(baseline * REDUCE_BUDGET_CUT_PCT, 2)
        action = WorkQueueAction(
            id=make_action_id("opp", week, serial),
            source_page="opportunity",
            source_run_at=ts,
            title=(
                f"Reduce Google Ads budget 50% on '{c['term']}' — projected "
                f"${c['projected_saving']:.0f}/mo saving (organic #{c['gsc_position']:.1f})"
            ),
            description=(
                f"Currently spending ${c['weekly_spend']:.2f}/wk on this keyword "
                f"({c['campaign']}). CB247 ranks organic #{c['gsc_position']:.1f} "
                f"with {c['gsc_clicks']} clicks/wk — organic is climbing but not yet "
                f"top-3. Cut budget 50% now; revisit when organic hits #3 to pause "
                f"entirely. Risk: low-medium. Action: halve daily budget on this "
                f"ad group. Re-evaluate after 14 days."
            ),
            owner="Tia",
            owner_role="OS Owner",
            priority="P2",
            effort_hours=0.3,
            category="opportunity",
            data_quality="high",
            projected_kpis=[ProjectedKPI(
                metric="ads_spend_saved_monthly",
                measurement_window_days=14,
                keyword=c["term"],
                baseline=baseline,
                target=target,
                confidence="medium",
            )],
            source_agent="opportunity-emitter",
        )
        actions.append(action)
        serial += 1
    return actions, serial


# ─── Pipeline orchestration ───────────────────────────────────────────────

def emit_all_opportunity_actions() -> List[WorkQueueAction]:
    """Top-level: load data, run emitters, return action list."""
    search_terms = _load_search_terms()
    gsc_idx      = _gsc_position_index()

    if not search_terms:
        print("[opportunity-emitter] no Google Ads search terms — nothing to emit")
        return []
    if not gsc_idx:
        print("[opportunity-emitter] no GSC queries — cannot match opportunities")
        return []

    week = week_iso()
    pause_actions, next_serial = _emit_pause(search_terms, gsc_idx, week, 1)
    reduce_actions, _ = _emit_reduce(search_terms, gsc_idx, week, next_serial)

    return pause_actions + reduce_actions


def merge_with_existing(new_actions: List[WorkQueueAction]) -> dict:
    """Idempotent merge into state/work-queue.json. Replace any existing
    opportunity-emitter actions from this week — they get re-derived from
    the same source data, so re-emission should be a no-op semantically."""
    existing: dict = {"actions": []}
    if WORK_QUEUE_FILE.exists():
        try:
            existing = json.loads(WORK_QUEUE_FILE.read_text())
        except Exception:
            existing = {"actions": []}

    actions = existing.get("actions") or []
    # Strip prior opportunity-emitter actions from this week (avoid stacking)
    week = week_iso()
    actions = [
        a for a in actions
        if not (a.get("source_agent") == "opportunity-emitter"
                and (a.get("id") or "").split("-")[-2:-1] == [week.replace("W","w")])
    ]
    # Catch-all: strip ALL prior opportunity actions (simpler — they'll
    # re-emit if the underlying opportunity still exists)
    actions = [a for a in actions if a.get("source_agent") != "opportunity-emitter"]

    actions.extend(to_jsonable(a) for a in new_actions)
    existing["actions"] = actions
    existing["updated_at"] = now_iso()
    return existing


def main():
    print(f"[opportunity-emitter] {now_iso()}")
    new_actions = emit_all_opportunity_actions()

    # Validate before writing
    errors_found = False
    for a in new_actions:
        errs = a.validate()
        if errs:
            errors_found = True
            print(f"  ❌ {a.id}: {errs}")

    if errors_found:
        print("[opportunity-emitter] validation failed — refusing to write")
        sys.exit(1)

    merged = merge_with_existing(new_actions)
    WORK_QUEUE_FILE.write_text(json.dumps(merged, indent=2, ensure_ascii=False))

    summary_by_type: dict = {}
    for a in new_actions:
        cat = "PAUSE" if a.priority == "P1" else "REDUCE"
        summary_by_type[cat] = summary_by_type.get(cat, 0) + 1

    total_saving = sum(
        kpi.baseline - (kpi.target or 0)
        for a in new_actions for kpi in a.projected_kpis
        if kpi.baseline is not None and kpi.target is not None
    )

    print(f"[opportunity-emitter] OK — {len(new_actions)} actions emitted")
    for cat, n in summary_by_type.items():
        print(f"    {cat:<8} {n}")
    print(f"    Total projected monthly saving: ${total_saving:.2f}")
    print(f"    Written to {WORK_QUEUE_FILE.relative_to(BASE_DIR)}")


if __name__ == "__main__":
    main()
