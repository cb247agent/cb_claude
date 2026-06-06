"""
baselines.py — pre-compute KPI baselines from existing state/*.json files.

This is the Flag 1 solution: avoid making the LLM look up baselines from
scratch. Python reads the data and emitters get pre-formed baseline numbers.

Each function returns the current baseline value for a metric, or None if
data is missing (Flag 2 — emitters then mark data_quality='low' or skip the
specific KPI).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STATE_DIR = BASE_DIR / "state"


def _load(filename: str) -> Optional[dict]:
    p = STATE_DIR / filename
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


# ── GSC (search console) ─────────────────────────────────────────────────────


def gsc_position_for(keyword: str) -> Optional[float]:
    """Current GSC position for a keyword. Case-insensitive exact match."""
    gsc = _load("gsc-data.json")
    if not gsc:
        return None
    for q in gsc.get("top_queries") or []:
        if (q.get("query") or "").strip().lower() == keyword.strip().lower():
            pos = q.get("position")
            return float(pos) if pos is not None else None
    return None


def gsc_clicks_for(keyword: str) -> Optional[int]:
    """Current GSC weekly clicks for a keyword."""
    gsc = _load("gsc-data.json")
    if not gsc:
        return None
    for q in gsc.get("top_queries") or []:
        if (q.get("query") or "").strip().lower() == keyword.strip().lower():
            c = q.get("clicks")
            return int(c) if c is not None else None
    return None


def gsc_impressions_for(keyword: str) -> Optional[int]:
    """Current GSC weekly impressions for a keyword."""
    gsc = _load("gsc-data.json")
    if not gsc:
        return None
    for q in gsc.get("top_queries") or []:
        if (q.get("query") or "").strip().lower() == keyword.strip().lower():
            i = q.get("impressions")
            return int(i) if i is not None else None
    return None


def gsc_clicks_for_pattern(pattern: str) -> Optional[int]:
    """Total weekly clicks across all keywords matching a regex pattern."""
    gsc = _load("gsc-data.json")
    if not gsc:
        return None
    rx = re.compile(pattern, re.IGNORECASE)
    total = 0
    matched = 0
    for q in gsc.get("top_queries") or []:
        if rx.search(q.get("query") or ""):
            total += int(q.get("clicks") or 0)
            matched += 1
    return total if matched else None


def gsc_all_queries() -> list:
    """Raw list of all GSC query records — for emitters to filter as they need."""
    gsc = _load("gsc-data.json")
    if not gsc:
        return []
    return gsc.get("top_queries") or []


def gsc_date_range() -> Optional[dict]:
    """The {start, end} date range of the current GSC pull."""
    gsc = _load("gsc-data.json")
    if not gsc:
        return None
    return gsc.get("date_range")


# ── Meta Ads ─────────────────────────────────────────────────────────────────


def _meta_latest_week_full() -> Optional[dict]:
    """Latest week's full Meta block (combined + per-location + ads array)."""
    ads = _load("ads-data.json")
    if not ads:
        return None
    weeks = ads.get("meta_ads") or []
    if not weeks:
        return None
    return weeks[0]


def meta_latest_week() -> Optional[dict]:
    """Latest week's combined Meta Ads stats."""
    wk = _meta_latest_week_full()
    if not wk:
        return None
    return wk.get("combined") or None


def meta_ctr_baseline() -> Optional[float]:
    w = meta_latest_week()
    if not w:
        return None
    # Meta data uses 'impr' (not 'impressions') in some snapshots
    impressions = w.get("impressions") or w.get("impr") or 0
    clicks = w.get("clicks") or 0
    if impressions == 0:
        # Fall back to the pre-computed ctr if present
        ctr = w.get("ctr")
        return float(ctr) if ctr is not None else None
    return round(clicks / impressions * 100, 2)


def meta_cpa_baseline() -> Optional[float]:
    w = meta_latest_week()
    if not w:
        return None
    spend = w.get("spend") or 0
    results = w.get("results") or w.get("clicks") or 0   # fallback to clicks
    if not results:
        return None
    return round(spend / results, 2)


def meta_combined_metric(metric_field: str) -> Optional[float]:
    """Account-level Meta metric. metric_field is the key in the combined dict
    (ctr, cpc, cpm, spend, clicks, impr, reach)."""
    w = meta_latest_week()
    if not w:
        return None
    v = w.get(metric_field)
    return float(v) if v is not None else None


def meta_all_ads_latest() -> list:
    """Raw list of ads from the latest week (each ad has name, spend, clicks,
    impr, reach, ctr, cpc, etc.). Empty list if not available."""
    wk = _meta_latest_week_full()
    if not wk:
        return []
    return wk.get("ads") or []


def meta_ad_metric_for(ad_name: str, metric_field: str) -> Optional[float]:
    """Look up a single ad's metric_field (ctr, cpc, clicks, impr, spend, reach).
    Case-insensitive substring match — ad names get truncated in the snapshot
    so exact match is unreliable."""
    if not ad_name:
        return None
    ads = meta_all_ads_latest()
    needle = ad_name.strip().lower()
    for ad in ads:
        nm = (ad.get("name") or "").strip().lower()
        if nm == needle or nm.startswith(needle) or needle.startswith(nm[:40]):
            v = ad.get(metric_field)
            return float(v) if v is not None else None
    return None


def meta_metric_from_field(metric: str) -> Optional[str]:
    """Map a VALID_METRICS name (meta_ctr, meta_cpc, ...) to the JSON field name."""
    return {
        "meta_ctr":               "ctr",
        "meta_cpc":               "cpc",
        "meta_cpm":               "cpm",
        "meta_results_weekly":    "clicks",   # results == clicks until conv tracking exists
        "meta_ad_clicks_weekly":  "clicks",
        "meta_ad_reach_weekly":   "reach",
    }.get(metric)


# ── Google Ads ───────────────────────────────────────────────────────────────


def _google_ads_latest_week_full() -> Optional[dict]:
    """Latest week's full Google Ads block (combined + per-location + campaigns)."""
    ads = _load("ads-data.json")
    if not ads:
        return None
    weeks = ads.get("google_ads") or []
    if not weeks:
        return None
    return weeks[0]


def google_ads_latest_week() -> Optional[dict]:
    """Latest week's combined Google Ads stats."""
    wk = _google_ads_latest_week_full()
    if not wk:
        return None
    return wk.get("combined") or None


def google_ads_cpa_baseline() -> Optional[float]:
    w = google_ads_latest_week()
    if not w:
        return None
    spend = w.get("spend") or 0
    conv = w.get("conv") or 0
    if not conv:
        return None
    return round(spend / conv, 2)


def google_ads_combined_metric(metric_field: str) -> Optional[float]:
    """Account-level Google Ads metric. metric_field is the key in the combined
    dict (cpa, conv, spend, clicks, impressions, ctr, cpc)."""
    w = google_ads_latest_week()
    if not w:
        return None
    v = w.get(metric_field)
    return float(v) if v is not None else None


def google_ads_all_campaigns_latest() -> list:
    """Raw list of campaigns from the latest week. Each row has name, spend,
    clicks, conv, cpa, status, location."""
    wk = _google_ads_latest_week_full()
    if not wk:
        return []
    return wk.get("campaigns") or []


def _parse_scope(scope: str) -> tuple:
    """Split 'Name [Loc]' into (name, location). 'Name' alone → (name, None)."""
    if not scope:
        return ("", None)
    s = scope.strip()
    if s.endswith("]") and "[" in s:
        name, _, loc = s.rpartition("[")
        return (name.strip(), loc.rstrip("]").strip())
    return (s, None)


def google_ads_campaign_metric_for(scope: str, metric_field: str) -> Optional[float]:
    """Look up a campaign's metric_field. `scope` is either 'Campaign Name' or
    'Campaign Name [Location]' (for PMax-style cross-location campaigns).
    Case-insensitive exact-name match on `name`."""
    name, loc = _parse_scope(scope)
    if not name:
        return None
    needle = name.lower()
    loc_needle = loc.lower() if loc else None

    for c in google_ads_all_campaigns_latest():
        cn = (c.get("name") or "").strip().lower()
        cl = (c.get("location") or "").strip().lower()
        if cn != needle:
            continue
        if loc_needle and cl != loc_needle:
            continue
        v = c.get(metric_field)
        return float(v) if v is not None else None
    return None


def google_ads_metric_from_field(metric: str) -> Optional[str]:
    """Map a VALID_METRICS name (google_ads_cpa, ...) to the JSON field name."""
    return {
        "google_ads_cpa":                  "cpa",
        "google_ads_cpc":                  "cpc",
        "google_ads_ctr":                  "ctr",
        "google_ads_conversions_weekly":   "conv",
        "google_ads_clicks_weekly":        "clicks",
        "google_ads_spend_weekly":         "spend",
    }.get(metric)


# ── GBP (Google Business Profile) ────────────────────────────────────────────


def gbp_review_count_for(location: str) -> Optional[int]:
    """Review count for malaga / ellenbrook."""
    gbp = _load("gbp-data.json")
    if not gbp:
        return None
    loc = gbp.get(location.lower()) or {}
    rc = loc.get("reviews")
    return int(rc) if rc is not None else None


def gbp_photos_count_for(location: str) -> Optional[int]:
    gbp = _load("gbp-data.json")
    if not gbp:
        return None
    loc = gbp.get(location.lower()) or {}
    pc = loc.get("photos")
    return int(pc) if pc is not None else None


def gbp_rating_for(location: str) -> Optional[float]:
    gbp = _load("gbp-data.json")
    if not gbp:
        return None
    loc = gbp.get(location.lower()) or {}
    r = loc.get("rating")
    return float(r) if r is not None else None


def gbp_location_full(location: str) -> Optional[dict]:
    """Return the full Apify-scraped profile block for a location."""
    gbp = _load("gbp-data.json")
    if not gbp:
        return None
    return gbp.get(location.lower())


def gbp_competitors_for(location: str) -> list:
    """Return competitor dicts scoped to this location (case-insensitive match
    on the competitor's 'location' field). Returns [] if data missing."""
    gbp = _load("gbp-data.json")
    if not gbp:
        return []
    target = location.strip().lower()
    return [
        c for c in (gbp.get("competitors") or [])
        if (c.get("location") or "").strip().lower() == target
    ]


def gbp_top_competitor(location: str, min_reviews: int = 30) -> Optional[dict]:
    """Highest-rated competitor at the location with at least `min_reviews`
    reviews (filters out small-volume rating noise). Returns None if no
    competitor qualifies."""
    competitors = [
        c for c in gbp_competitors_for(location)
        if (c.get("reviews") or 0) >= min_reviews
        and c.get("rating") is not None
    ]
    if not competitors:
        return None
    return max(competitors, key=lambda c: float(c.get("rating") or 0))


def gbp_metric_from_field(metric: str) -> Optional[str]:
    """Map a VALID_METRICS name to the gbp-data.json field name."""
    return {
        "gbp_reviews_count": "reviews",
        "gbp_photos_count":  "photos",
        "gbp_rating":        "rating",
    }.get(metric)
