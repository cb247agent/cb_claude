"""
measurement_runner.py — daily measurement job.

Finds work_queue_actions that:
  - Have planner_status.status = 'Published'
  - Have measurement_window_days elapsed since planner_status.updated_at
  - Have not yet been measured (actual_kpis IS NULL)

For each, fetches the actual KPI value from the source page's data
(state/gsc-data.json for SEO; Meta/Google/GBP added in Session 5+)
and computes per-KPI status + overall verdict. Writes both back to
Supabase as a single PATCH.

Idempotent: re-running is safe — once actual_kpis is set, the row is
filtered out by the eligibility check.

Run:
    .venv/bin/python3.13 scripts/work_queue/measurement_runner.py
    # Optional flags:
    #   --force-id ID    measure this id regardless of elapsed time
    #   --dry-run        compute + print but don't PATCH Supabase

Wired into: scripts/pull_all.py at end (runs every 6 hours via launchd)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

# Allow direct run + module import
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))   # scripts/
sys.path.insert(0, str(_HERE.parent.parent))   # repo root

from work_queue.baselines import (  # noqa: E402
    gsc_position_for,
    gsc_clicks_for,
    gsc_impressions_for,
    gsc_clicks_for_pattern,
    meta_combined_metric,
    meta_ad_metric_for,
    meta_metric_from_field,
    google_ads_combined_metric,
    google_ads_campaign_metric_for,
    google_ads_metric_from_field,
    gbp_review_count_for,
    gbp_photos_count_for,
    gbp_rating_for,
    gbp_metric_from_field,
)
from work_queue.measurement import (  # noqa: E402
    compute_kpi_status,
    compute_overall_verdict,
)
from work_queue.schema import now_iso  # noqa: E402


SUPABASE_URL = "https://ckjwzwktuiavyfuolbgx.supabase.co"
SUPABASE_KEY = "sb_publishable_3giOfPJ92JW7DN8w9jPvoQ_cFo4rd0s"


def _headers() -> dict:
    return {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
    }


def _fetch_unmeasured_actions() -> list:
    """Get all work_queue_actions where actual_kpis IS NULL."""
    url = (
        f"{SUPABASE_URL}/rest/v1/work_queue_actions"
        "?actual_kpis=is.null"
        "&select=id,title,projected_kpis,source_page,source_run_at"
    )
    r = requests.get(url, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def _fetch_planner_status(item_id: str) -> Optional[dict]:
    """Get planner_status row for an item."""
    url = f"{SUPABASE_URL}/rest/v1/planner_status?item_id=eq.{item_id}&select=item_id,status,updated_at"
    r = requests.get(url, headers=_headers(), timeout=30)
    r.raise_for_status()
    rows = r.json()
    return rows[0] if rows else None


def _is_eligible(action: dict, planner_row: Optional[dict]) -> tuple[bool, str]:
    """Return (eligible, reason). Reason is a short string for the log."""
    if not planner_row:
        return False, "not in planner_status (not yet published)"
    if planner_row.get("status") != "Published":
        return False, f"status='{planner_row.get('status')}' (not Published)"

    updated_at_str = planner_row.get("updated_at")
    if not updated_at_str:
        return False, "no updated_at timestamp"

    try:
        # Postgres timestamptz format varies — handle both forms
        cleaned = updated_at_str.replace("Z", "+00:00")
        if "+" not in cleaned and "-" not in cleaned[-6:]:
            cleaned = cleaned + "+00:00"
        updated_at = datetime.fromisoformat(cleaned)
    except Exception as e:
        return False, f"could not parse updated_at: {e}"

    elapsed_days = (datetime.now(timezone.utc) - updated_at).days
    windows = [
        int(k.get("measurement_window_days", 14) or 14)
        for k in (action.get("projected_kpis") or [])
    ]
    max_window = max(windows) if windows else 14

    if elapsed_days < max_window:
        return False, f"only {elapsed_days}d elapsed (need {max_window}d)"
    return True, f"{elapsed_days}d elapsed (window {max_window}d)"


def _fetch_actual(metric: str, keyword: Optional[str], pattern: Optional[str]) -> Optional[float]:
    """Fetch the current value of a metric from state/*.json files.

    For Meta metrics, `keyword` doubles as the ad name. If no ad name is
    given, falls back to the account-level (combined) value.
    """
    # ── GSC ──
    if metric == "gsc_position" and keyword:
        return gsc_position_for(keyword)
    if metric == "gsc_clicks_weekly":
        if keyword:
            return gsc_clicks_for(keyword)
        if pattern:
            return gsc_clicks_for_pattern(pattern)
    if metric == "gsc_impressions_weekly" and keyword:
        return gsc_impressions_for(keyword)

    # ── Meta Ads (Session 5a) ──
    field = meta_metric_from_field(metric)
    if field is not None:
        if keyword:
            v = meta_ad_metric_for(keyword, field)
            if v is not None:
                return v
            # ad disappeared from latest pull (paused / archived) — fall through
            # to account-level so the verdict still resolves with directional info
        return meta_combined_metric(field)

    # ── Google Ads (Session 5b) ──
    field = google_ads_metric_from_field(metric)
    if field is not None:
        if keyword:
            v = google_ads_campaign_metric_for(keyword, field)
            if v is not None:
                return v
            # campaign was paused / renamed — fall through to account-level
        return google_ads_combined_metric(field)

    # ── GBP (Session 5c) ── keyword field carries location name (malaga/ellenbrook)
    if metric == "gbp_reviews_count" and keyword:
        v = gbp_review_count_for(keyword)
        return float(v) if v is not None else None
    if metric == "gbp_photos_count" and keyword:
        v = gbp_photos_count_for(keyword)
        return float(v) if v is not None else None
    if metric == "gbp_rating" and keyword:
        return gbp_rating_for(keyword)

    # Session 5d+: ig_*, membership_* lookups
    return None


def measure_action(action: dict) -> tuple[list, str]:
    """Compute actual_kpis + overall_verdict for one action."""
    actual_kpis = []
    for projected in action.get("projected_kpis") or []:
        metric  = projected.get("metric")
        keyword = projected.get("keyword")
        pattern = projected.get("keyword_pattern")
        actual  = _fetch_actual(metric, keyword, pattern)
        actual_kpis.append(compute_kpi_status(projected, actual))
    overall = compute_overall_verdict(actual_kpis)
    return actual_kpis, overall


def update_action_row(action_id: str, actual_kpis: list, overall_verdict: str, dry_run: bool = False) -> bool:
    """PATCH the Supabase row with measurement results."""
    if dry_run:
        return True
    url = f"{SUPABASE_URL}/rest/v1/work_queue_actions?id=eq.{action_id}"
    payload = {
        "actual_kpis":     actual_kpis,
        "overall_verdict": overall_verdict,
        "measured_at":     now_iso(),
    }
    headers = _headers()
    headers["Prefer"] = "return=minimal"
    r = requests.patch(url, headers=headers, json=payload, timeout=30)
    if r.status_code >= 300:
        print(f"  ⚠️  update failed [{r.status_code}]: {r.text[:200]}")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Work Queue measurement runner")
    parser.add_argument("--force-id", help="Measure this action id regardless of elapsed time")
    parser.add_argument("--dry-run",  action="store_true", help="Compute + print but don't PATCH")
    args = parser.parse_args()

    print(f"\n=== Work Queue Measurement Runner — {now_iso()} ===")
    if args.dry_run:
        print("(DRY RUN — no Supabase writes)")

    actions = _fetch_unmeasured_actions()
    print(f"Found {len(actions)} unmeasured actions")

    measured = 0
    skipped  = 0

    for a in actions:
        if args.force_id:
            if a["id"] != args.force_id:
                continue
            print(f"\n[FORCED] {a['title']}")
            actual_kpis, overall = measure_action(a)
        else:
            planner = _fetch_planner_status(a["id"])
            ok, reason = _is_eligible(a, planner)
            if not ok:
                skipped += 1
                continue
            print(f"\n[ELIGIBLE — {reason}] {a['title']}")
            actual_kpis, overall = measure_action(a)

        # Print per-KPI breakdown
        for k in actual_kpis:
            kw = k.get("keyword") or k.get("keyword_pattern") or "—"
            base = k.get("baseline") if k.get("baseline") is not None else "?"
            actual = k.get("actual") if k.get("actual") is not None else "?"
            tgt = k.get("target") if k.get("target") is not None else "?"
            print(f"    {k['metric']} ({kw}): baseline={base} actual={actual} target={tgt} → {k['status']}")
        print(f"    OVERALL: {overall}")

        if update_action_row(a["id"], actual_kpis, overall, dry_run=args.dry_run):
            measured += 1

    print(f"\nMeasured: {measured}, Skipped: {skipped} (not eligible)")


if __name__ == "__main__":
    main()
