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


# ── Opportunity savings (closed-loop, 12 Jun 2026) ───────────────────────────


def google_ads_search_term_weekly_spend(search_term: str) -> Optional[float]:
    """Latest weekly spend on a Google Ads SEARCH TERM (not campaign).

    Used by `_fetch_actual("ads_spend_saved_monthly")` — when the team pauses
    a wasteful search term per opportunity_emitter's recommendation, this
    function returns the current weekly spend on that term. The verdict
    layer multiplies by 4.3 to get monthly equivalent and compares to the
    projected $0 (PAUSE) or 50%-cut target (REDUCE).

    Returns 0.0 if the search term has fully dropped out of the latest pull
    (paused successfully). Returns None only when the data file is missing —
    that's a data-quality problem, not a verdict signal.
    """
    ads = _load("google-ads-data.json")
    if not ads:
        return None
    needle = (search_term or "").strip().lower()
    if not needle:
        return None
    terms = ads.get("search_terms") or ads.get("topSearchTerms") or []
    for t in terms:
        term = (t.get("search_term") or t.get("term") or t.get("query") or "").strip().lower()
        if term == needle:
            spend = t.get("cost") or t.get("spend") or 0
            return float(spend)
    # Search term has dropped out — the pause worked, current weekly spend = 0
    return 0.0


def ads_spend_saved_monthly_for(search_term: str) -> Optional[float]:
    """Monthly-equivalent spend STILL going to a search term we tried to cut.

    This is the metric measurement_runner uses to verdict an
    ads_spend_saved_monthly action. Returns weekly_spend × 4.3 (i.e., what
    we're still spending). If we projected target=0 and actual=0, perfect
    save. If actual is much lower than baseline but not 0, partial save.
    """
    weekly = google_ads_search_term_weekly_spend(search_term)
    if weekly is None:
        return None
    return round(weekly * 4.3, 2)


def cumulative_ads_savings_monthly() -> Optional[float]:
    """Account-level rolling monthly-equivalent paid spend.

    For the cumulative-savings projection, the "actual" is the account's
    total monthly spend at verdict time. Compared against the baseline
    snapshot at action-emit time, the delta IS the realised cumulative
    savings. We deliberately don't try to compute the delta here —
    measurement_runner has both numbers and can compute it cleanly.
    """
    wk = google_ads_latest_week()
    if not wk:
        return None
    spend = wk.get("spend")
    if spend is None:
        return None
    return round(float(spend) * 4.3, 2)


# ── Technical SEO ops (Screaming Frog crawl, 12 Jun 2026) ────────────────────


def _screaming_frog_blob() -> Optional[dict]:
    return _load("screaming-frog-data.json")


def pages_4xx_count() -> Optional[int]:
    """Current count of pages returning 4xx/5xx status.

    Closed-loop pairing: opportunity emitters that propose "fix HTTP errors"
    project this metric with target=0. measurement_runner reads this
    function 7d later and verdicts.
    """
    sf = _screaming_frog_blob()
    if not sf:
        return None
    summary = sf.get("summary") or {}
    v = summary.get("pages_4xx_5xx")
    return int(v) if v is not None else None


def _sf_issue_count(issue_name_lower: str) -> Optional[int]:
    """Helper — pull a specific issue's count from the issues list. Returns
    0 if the issue isn't listed at all (Screaming Frog only emits issues
    that have at least one occurrence, so 'not listed' = 'all clean')."""
    sf = _screaming_frog_blob()
    if not sf:
        return None
    for issue in sf.get("issues") or []:
        name = (issue.get("name") or "").strip().lower()
        if issue_name_lower in name:
            return int(issue.get("count") or 0)
    return 0


def schema_implemented_count() -> Optional[int]:
    """Pages with structured-data schema markup detected.

    Computed as: total_crawled - pages_missing_schema. Strategist projects
    target=N (some growth from baseline). Used by 'add LocalBusiness
    schema' actions.
    """
    sf = _screaming_frog_blob()
    if not sf:
        return None
    summary = sf.get("summary") or {}
    total = summary.get("total_pages_crawled")
    missing = _sf_issue_count("no schema markup")
    if total is None or missing is None:
        return None
    return max(int(total) - int(missing), 0)


def duplicate_metas_count() -> Optional[int]:
    """Sum of pages with duplicate meta descriptions OR duplicate titles.

    Strategist projects target=0 on dedup actions. Combining duplicate
    descriptions + duplicate titles mirrors how the SEO strategist scopes
    'dedup metadata' tasks (it treats them as one workstream).
    """
    desc_dupes = _sf_issue_count("duplicate meta description")
    title_dupes = _sf_issue_count("duplicate title")
    if desc_dupes is None and title_dupes is None:
        return None
    return (desc_dupes or 0) + (title_dupes or 0)


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


# ── Organic Social ───────────────────────────────────────────────────────────


def social_scraped_at() -> Optional[str]:
    """Timestamp of the latest social-trends.json scrape."""
    s = _load("social-trends.json")
    return s.get("scraped") if s else None


def social_top_hashtags(n: int = 3) -> list:
    """Top-N trending hashtags by count from state/social-trends.json.
    Returns list of dicts {hashtag, count} ranked descending by count."""
    s = _load("social-trends.json")
    if not s:
        return []
    tags = list(s.get("trending_hashtags") or [])
    tags.sort(key=lambda t: int(t.get("count") or 0), reverse=True)
    return tags[:n]


# ── Membership ───────────────────────────────────────────────────────────────


def _membership_summary() -> Optional[dict]:
    """The latest summary block from state/membership-data.json."""
    m = _load("membership-data.json")
    if not m:
        return None
    return m.get("summary")


def _membership_contracts() -> Optional[dict]:
    """The contracts block (addon counts + active base)."""
    m = _load("membership-data.json")
    if not m:
        return None
    return m.get("contracts")


def _membership_cleverwaiver() -> Optional[dict]:
    """The exit survey block."""
    m = _load("membership-data.json")
    if not m:
        return None
    return m.get("cleverwaiver")


def membership_period() -> Optional[dict]:
    """Period {raw, start, end} of the latest snapshot."""
    s = _membership_summary()
    return s.get("period") if s else None


def _resolve_club_key(location: str) -> Optional[str]:
    """Normalise location → 'Malaga' / 'Ellenbrook' / None=combined."""
    if not location:
        return None
    l = location.strip().lower()
    if l in ("malaga", "mlg"):
        return "Malaga"
    if l in ("ellenbrook", "ebk"):
        return "Ellenbrook"
    return None  # treated as combined


def membership_signups_for(location: Optional[str]) -> Optional[int]:
    """Per-location new contracts for the latest snapshot. Pass None or
    'combined' for the totals row."""
    s = _membership_summary()
    if not s:
        return None
    club = _resolve_club_key(location) if location else None
    if club:
        v = (s.get("per_club") or {}).get(club, {}).get("NewContracts")
    else:
        v = (s.get("totals") or {}).get("NewContracts")
    return int(v) if v is not None else None


def membership_cancellations_for(location: Optional[str]) -> Optional[int]:
    """Per-location ended contracts for the latest snapshot."""
    s = _membership_summary()
    if not s:
        return None
    club = _resolve_club_key(location) if location else None
    if club:
        v = (s.get("per_club") or {}).get(club, {}).get("EndedContracts")
    else:
        v = (s.get("totals") or {}).get("EndedContracts")
    return int(v) if v is not None else None


def membership_future_cancellations_for(location: Optional[str]) -> Optional[int]:
    """Per-location future-dated cancellations (save-call queue size)."""
    s = _membership_summary()
    if not s:
        return None
    club = _resolve_club_key(location) if location else None
    if club:
        v = (s.get("per_club") or {}).get(club, {}).get("FutureCancellations")
    else:
        v = (s.get("totals") or {}).get("FutureCancellations")
    return int(v) if v is not None else None


def membership_addon_count_for(addon: str) -> Optional[int]:
    """Active member count for a specific addon (combined across locations).
    Pass the exact addon label as it appears in the JSON, e.g.
    'Recovery (Sauna + Ice Bath)' or 'Reformer Pilates'."""
    c = _membership_contracts()
    if not c:
        return None
    v = (c.get("addon_active") or {}).get(addon)
    return int(v) if v is not None else None


def membership_top_addons(n: int = 4) -> list:
    """Top addons ranked by active count descending."""
    c = _membership_contracts()
    if not c:
        return []
    items = list((c.get("addon_active") or {}).items())
    items.sort(key=lambda kv: int(kv[1] or 0), reverse=True)
    return [{"addon": k, "count": int(v or 0)} for k, v in items[:n]]


def membership_cancel_reason_count(reason: str, source: str = "combined") -> Optional[int]:
    """Count of a specific cancel reason. `source` ∈ {'pgm', 'cleverwaiver', 'combined'}.
    Reasons across sources don't always use identical strings — caller passes the
    canonical reason and we sum partial-match across both sources."""
    s = _membership_summary()
    cw = _membership_cleverwaiver()
    needle = (reason or "").strip().lower()
    if not needle:
        return None
    total = 0
    matched = False

    if source in ("pgm", "combined") and s:
        for r, count in (s.get("cancel_reasons_pgm") or {}).items():
            if needle in r.strip().lower():
                total += int(count or 0)
                matched = True

    if source in ("cleverwaiver", "combined") and cw:
        for r, count in (cw.get("reasons") or {}).items():
            if needle in r.strip().lower():
                total += int(count or 0)
                matched = True

    return total if matched else None


def membership_switched_to_gym_count() -> int:
    """Combined count of members who churned citing 'switched to another gym'
    across PGM cancel reasons and Cleverwaiver exit-survey. The strongest
    competitive-loss signal in the dataset."""
    pgm = membership_cancel_reason_count("switched", source="pgm") or 0
    cw  = membership_cancel_reason_count("switched", source="cleverwaiver") or 0
    return pgm + cw


def membership_not_using_count() -> int:
    """Combined count of 'not using membership enough' churns. Highest-leverage
    actionable reason — these members were paying without engaging, an onboarding
    + habit-build campaign can move the needle."""
    pgm = membership_cancel_reason_count("not using", source="pgm") or 0
    cw  = membership_cancel_reason_count("not using", source="cleverwaiver") or 0
    return pgm + cw


# Insert just before social_top_posts_by_engagement definition
def social_top_posts_by_engagement(n: int = 2, min_engagement: int = 30) -> list:
    """Top-N posts from state/social-trends.json ranked by engagement,
    filtered to those with at least `min_engagement` (filters out low-signal
    noise). Returns the raw post dicts."""
    s = _load("social-trends.json")
    if not s:
        return []
    posts = [
        p for p in (s.get("top_posts") or [])
        if int(p.get("engagement") or 0) >= min_engagement
    ]
    posts.sort(key=lambda p: int(p.get("engagement") or 0), reverse=True)
    return posts[:n]
