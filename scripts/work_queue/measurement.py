"""
measurement.py — pure functions for computing actual vs projected KPI status.

No I/O, no Supabase, no requests. Given a ProjectedKPI + the actual measured
value, return an ActualKPI dict with delta, target_hit, status.

Used by measurement_runner.py to compute verdicts on Done actions.
"""

from __future__ import annotations

from typing import Dict, List, Optional


# Metrics where a HIGHER number is better (improvement)
HIGHER_IS_BETTER = {
    "gsc_clicks_weekly",
    "gsc_impressions_weekly",
    "gsc_ctr",
    "ahrefs_domain_rating",
    "meta_ctr",
    "meta_results_weekly",
    "google_ads_conversions_weekly",
    "gbp_review_response_rate",
    "gbp_reviews_count",
    "gbp_photos_count",
    "gbp_posts_per_week",
    "ig_engagement_rate",
    "ig_followers",
    "membership_signups_weekly",
}

# Metrics where a LOWER number is better (improvement)
LOWER_IS_BETTER = {
    "gsc_position",
    "meta_cpa",
    "meta_cpm",
    "google_ads_cpa",
    "google_ads_cpc",
    "membership_cancellations_weekly",
}


def kpi_direction(metric: str) -> str:
    """Returns 'higher', 'lower', or 'unknown'."""
    if metric in HIGHER_IS_BETTER:
        return "higher"
    if metric in LOWER_IS_BETTER:
        return "lower"
    return "unknown"


def compute_kpi_status(projected: Dict, actual: Optional[float]) -> Dict:
    """
    Given a projected_kpi dict + the actual measured value, return an
    actual_kpi dict matching the schema's ActualKPI shape.

    Status rules:
      target_hit   → 'winner'
      moved-but-not-hit (delta > tolerance) → 'partial_win'
      no-meaningful-change (|delta| < tolerance) → 'no_change'
      moved-backwards → 'underperforming'
    """
    metric = projected.get("metric", "")
    keyword = projected.get("keyword")
    keyword_pattern = projected.get("keyword_pattern")
    baseline = projected.get("baseline")
    target = projected.get("target")
    delta_min = projected.get("delta_min")
    delta_max = projected.get("delta_max")
    direction = kpi_direction(metric)

    base_dict = {
        "metric":          metric,
        "keyword":         keyword,
        "keyword_pattern": keyword_pattern,
        "baseline":        baseline,
        "target":          target,
        "actual":          actual,
        "delta":           None,
        "target_hit":      None,
        "status":          "no_change",
    }

    # No actual value means we couldn't fetch the data
    if actual is None:
        base_dict["status"] = "no_change"
        return base_dict

    # Compute signed delta in the "better" direction
    delta: Optional[float] = None
    if baseline is not None:
        if direction == "higher":
            delta = float(actual) - float(baseline)
        elif direction == "lower":
            delta = float(baseline) - float(actual)
        else:
            delta = abs(float(actual) - float(baseline))
        base_dict["delta"] = round(delta, 2)

    # Determine target_hit
    target_hit: Optional[bool] = None
    if target is not None:
        if direction == "higher":
            target_hit = actual >= target
        elif direction == "lower":
            target_hit = actual <= target
    elif delta_min is not None and delta is not None:
        target_hit = delta >= delta_min
    base_dict["target_hit"] = target_hit

    # Determine status with a sensible tolerance (avoids flapping on tiny moves)
    tolerance = _tolerance_for(metric)
    if target_hit:
        base_dict["status"] = "winner"
    elif delta is not None and delta > tolerance:
        base_dict["status"] = "partial_win"
    elif delta is not None and abs(delta) <= tolerance:
        base_dict["status"] = "no_change"
    elif delta is not None and delta < 0:
        base_dict["status"] = "underperforming"
    else:
        base_dict["status"] = "no_change"

    return base_dict


def _tolerance_for(metric: str) -> float:
    """Per-metric noise tolerance. Movement within tolerance = 'no_change'."""
    if metric == "gsc_position":
        return 0.5            # half a position is noise
    if metric in ("gsc_clicks_weekly", "gsc_impressions_weekly"):
        return 2              # 2 clicks/impressions noise
    if metric == "gsc_ctr":
        return 0.5            # half a percentage point
    if metric in ("meta_cpa", "google_ads_cpa"):
        return 1.0            # $1 noise
    if metric == "ahrefs_domain_rating":
        return 0.5            # half a DR point
    return 0


def compute_overall_verdict(actual_kpis: List[Dict]) -> str:
    """
    Aggregate per-KPI statuses into one overall verdict.
      All winners                          → 'winner'
      Mix of winners + partials             → 'partial_win'
      Majority underperforming              → 'underperforming'
      Otherwise (mostly no_change)          → 'no_change'
    """
    if not actual_kpis:
        return "pending"

    total = len(actual_kpis)
    statuses = [k.get("status", "no_change") for k in actual_kpis]
    winners      = statuses.count("winner")
    partials     = statuses.count("partial_win")
    no_changes   = statuses.count("no_change")
    underperforms = statuses.count("underperforming")

    if winners == total:
        return "winner"
    if winners + partials >= (total + 1) // 2:   # majority moved positively
        return "partial_win"
    if underperforms > total / 2:                 # majority regressed
        return "underperforming"
    return "no_change"
