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


def meta_latest_week() -> Optional[dict]:
    """Latest week's combined Meta Ads stats."""
    ads = _load("ads-data.json")
    if not ads:
        return None
    weeks = ads.get("meta_ads") or []
    if not weeks:
        return None
    return weeks[0].get("combined") or None


def meta_ctr_baseline() -> Optional[float]:
    w = meta_latest_week()
    if not w:
        return None
    impressions = w.get("impressions") or 0
    clicks = w.get("clicks") or 0
    if impressions == 0:
        return None
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


# ── Google Ads ───────────────────────────────────────────────────────────────


def google_ads_latest_week() -> Optional[dict]:
    ads = _load("ads-data.json")
    if not ads:
        return None
    weeks = ads.get("google_ads") or []
    if not weeks:
        return None
    return weeks[0].get("combined") or None


def google_ads_cpa_baseline() -> Optional[float]:
    w = google_ads_latest_week()
    if not w:
        return None
    spend = w.get("spend") or 0
    conv = w.get("conv") or 0
    if not conv:
        return None
    return round(spend / conv, 2)


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
