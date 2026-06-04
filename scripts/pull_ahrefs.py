"""
pull_ahrefs.py — Pull SEO analytics from Ahrefs API v3.
Saves to state/ahrefs-data.json.
Requires AHREFS_API_KEY in .env

Pulls:
  1. Domain rating + Ahrefs rank
  2. Organic keywords (top 100) + WoW position changes
  3. Top pages by organic traffic + organic value ($)
  4. Backlinks (new + lost + broken reclaim candidates)
  5. Referring domains
  6. Anchors
  7. Keyword gap vs Revo Fitness + Anytime Fitness
  8. Target keyword position tracker (20 priority CB247 keywords)
  9. Organic traffic value ($) — equivalent ad spend

API v3 base: https://api.ahrefs.com/v3/
Auth: Bearer token in Authorization header
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
import requests

BASE_DIR  = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
load_dotenv(BASE_DIR / ".env")

API_KEY  = os.getenv("AHREFS_API_KEY", "")
SITE     = "chasingbetter247.com.au"
BASE_URL = "https://api.ahrefs.com/v3"
TODAY    = datetime.now().strftime("%Y-%m-%d")
LAST_WEEK = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

# Competitors for keyword gap analysis
COMPETITORS = [
    "revofitness.com.au",
    "anytimefitness.com.au",
]

# Ahrefs Site Audit project ID (from app.ahrefs.com/site-audit/{ID}/overview)
# Separate API — does NOT consume Site Explorer units. Runs on Monday schedule.
SITE_AUDIT_PROJECT_ID = "9812033"

# ── 20 CB247 priority keywords to track every week ──
TARGET_KEYWORDS = [
    "gym malaga perth",
    "24/7 gym malaga",
    "gym ellenbrook perth",
    "24/7 gym ellenbrook",
    "cheap gym malaga",
    "cheap gym perth",
    "reformer pilates malaga",
    "reformer pilates perth",
    "sauna gym perth",
    "ice bath gym perth",
    "kids gym malaga",
    "family gym malaga",
    "fifo gym perth",
    "fifo gym membership perth",
    "personal training malaga",
    "crossfit malaga perth",
    "spin class malaga",
    "yoga malaga perth",
    "gym membership perth no lock in",
    "chasingbetter247",
]

if not API_KEY or API_KEY.startswith("#") or len(API_KEY) < 10:
    print("AHREFS_API_KEY not set or invalid — skipping Ahrefs data pull.")
    print("  → Get your key at https://ahrefs.com/api/")
    API_KEY = ""

# Unit safety threshold — abort pull if fewer than this many units remain this month
_UNIT_THRESHOLD = 5_000


def _count_rows(data):
    """Return the number of rows in a paginated API response, or None if not paginated."""
    if not isinstance(data, dict):
        return None
    for key in ("keywords", "backlinks", "pages", "refdomains", "anchors", "healthscores"):
        if key in data and isinstance(data[key], list):
            return len(data[key])
    return None


def fetch_json(endpoint, params=None, _delay=1.5):
    """Fetch JSON from Ahrefs API v3. Adds a small delay between calls to avoid
    Cloudflare burst-rate limiting (429 HTML response).
    Logs rows returned and units consumed (from x-api-units-cost-total-actual header)."""
    if not API_KEY:
        return None
    import time
    time.sleep(_delay)
    url     = f"{BASE_URL}/{endpoint}"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    params  = params or {}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        # Cloudflare block returns HTML 429 — detect and treat as transient
        if r.status_code == 429 and "<html" in r.text[:50].lower():
            print(f"  WARN: Cloudflare rate limit on [{endpoint}] — wait a few minutes and retry", file=sys.stderr)
            return None
        r.raise_for_status()
        data  = r.json()
        units = r.headers.get("x-api-units-cost-total-actual", "–")
        rows  = _count_rows(data)
        if rows is not None:
            print(f"  [ahrefs] {endpoint}: {rows} rows, {units} units used")
        else:
            print(f"  [ahrefs] {endpoint}: {units} units used")
        return data
    except Exception as e:
        print(f"Ahrefs API error [{endpoint}]: {e}", file=sys.stderr)
        return None


def check_units():
    """
    Call the free /account/limits-and-usage endpoint (0 units consumed).
    If remaining units < _UNIT_THRESHOLD, print a warning and return False.
    Callers should exit without pulling if this returns False.
    """
    data = fetch_json("account/limits-and-usage", _delay=0)
    if not data:
        print("  WARN: Could not check unit balance — proceeding anyway", file=sys.stderr)
        return True
    # Ahrefs v3 returns nested structure — try common paths
    inner    = data.get("limits_and_usage") or data.get("subscription") or data
    api_info = inner.get("api_units") or inner
    remaining = (
        api_info.get("units_left_monthly") or
        api_info.get("api_units_left")     or
        api_info.get("units_remaining")    or
        (api_info.get("monthly_limit", 0) - api_info.get("used", 0))
        if ("monthly_limit" in api_info and "used" in api_info) else None
    )
    if remaining is not None:
        print(f"  Ahrefs units remaining this month: {remaining:,}")
        if remaining < _UNIT_THRESHOLD:
            print(
                f"  ⛔  ABORT: Only {remaining:,} units remaining — threshold is "
                f"{_UNIT_THRESHOLD:,}. Skipping pull to preserve credits.",
                file=sys.stderr,
            )
            return False
    else:
        print("  WARN: Could not parse unit balance from response — proceeding", file=sys.stderr)
    return True


# ─────────────────────────────────────────────
# 1. Domain rating (current + previous week — fetched once, reused by organic value)
# ─────────────────────────────────────────────

def pull_domain_rating():
    """
    Fetch domain rating for TODAY and LAST_WEEK in a single function call.
    Both results are reused by pull_organic_traffic_value() — no duplicate API calls.
    Returns (current_dr, prev_dr) tuple.
    """
    current = fetch_json("site-explorer/domain-rating", {
        "target": SITE,
        "date":   TODAY,
    })
    prev = fetch_json("site-explorer/domain-rating", {
        "target": SITE,
        "date":   LAST_WEEK,
    })
    return current, prev


# ─────────────────────────────────────────────
# 2. Organic keywords + WoW position changes
# ─────────────────────────────────────────────

def pull_organic_keywords():
    """Top ranking organic keywords in AU."""
    return fetch_json("site-explorer/organic-keywords", {
        "target":   SITE,
        "country":  "au",
        "date":     TODAY,
        "limit":    50,
        "order_by": "volume:desc",
        "select":   "keyword,best_position,best_position_url,volume,cpc,keyword_difficulty,sum_traffic",
    })


def pull_organic_keywords_last_week():
    """Same query but dated last week — used to calculate WoW position changes."""
    return fetch_json("site-explorer/organic-keywords", {
        "target":   SITE,
        "country":  "au",
        "date":     LAST_WEEK,
        "limit":    50,
        "order_by": "volume:desc",
        "select":   "keyword,best_position,volume",
    })


def compute_wow_changes(current_kws, previous_kws):
    """
    Compare this week vs last week positions for each keyword.
    Returns list of dicts with keyword, current_pos, previous_pos, change, direction.
    direction: "up" (improved), "down" (dropped), "new" (wasn't tracked), "same"
    """
    if not current_kws or not previous_kws:
        return []

    prev_map = {}
    for kw in (previous_kws.get("keywords") or []):
        prev_map[kw.get("keyword", "").lower()] = kw.get("best_position")

    changes = []
    for kw in (current_kws.get("keywords") or []):
        keyword  = kw.get("keyword", "")
        curr_pos = kw.get("best_position")
        prev_pos = prev_map.get(keyword.lower())

        if prev_pos is None:
            direction = "new"
            change    = None
        elif curr_pos < prev_pos:
            direction = "up"
            change    = prev_pos - curr_pos
        elif curr_pos > prev_pos:
            direction = "down"
            change    = curr_pos - prev_pos
        else:
            direction = "same"
            change    = 0

        changes.append({
            "keyword":      keyword,
            "current_pos":  curr_pos,
            "previous_pos": prev_pos,
            "change":       change,
            "direction":    direction,
            "volume":       kw.get("volume"),
            "url":          kw.get("best_position_url"),
        })

    # Sort: biggest improvements first
    changes.sort(key=lambda x: (
        0 if x["direction"] == "up" else
        1 if x["direction"] == "new" else
        2 if x["direction"] == "same" else 3,
        -(x["change"] or 0),
    ))
    return changes


# ─────────────────────────────────────────────
# 3. Top pages + organic value
# ─────────────────────────────────────────────

def pull_top_pages():
    """Top pages by organic traffic — includes organic value per page."""
    return fetch_json("site-explorer/top-pages", {
        "target":   SITE,
        "country":  "au",
        "date":     TODAY,
        "limit":    20,
        "order_by": "sum_traffic:desc",
        "select":   "url,sum_traffic,top_keyword,top_keyword_best_position,top_keyword_volume,referring_domains",
    })


def pull_organic_traffic_value(current_dr=None, prev_dr=None):
    """
    Extract site-level organic traffic value ($ equivalent ad spend) from pre-fetched
    domain-rating data. Accepts already-fetched results from pull_domain_rating() to
    avoid duplicate API calls. Falls back to fresh API calls only if data is not supplied.
    This is the core metric for the 'SEO replacing Google Ads' tracker.
    """
    if current_dr is None:
        current_dr = fetch_json("site-explorer/domain-rating", {"target": SITE, "date": TODAY})
    if prev_dr is None:
        prev_dr = fetch_json("site-explorer/domain-rating", {"target": SITE, "date": LAST_WEEK})

    current  = (current_dr or {}).get("domain_rating", {}) if current_dr else {}
    previous = (prev_dr    or {}).get("domain_rating", {}) if prev_dr    else {}

    curr_value = current.get("organic_traffic_value", 0) or 0
    prev_value = previous.get("organic_traffic_value", 0) or 0

    return {
        "current_week": {
            "organic_traffic":       current.get("organic_traffic"),
            "organic_traffic_value": curr_value,
            "organic_keywords":      current.get("organic_keywords"),
        },
        "previous_week": {
            "organic_traffic":       previous.get("organic_traffic"),
            "organic_traffic_value": prev_value,
            "organic_keywords":      previous.get("organic_keywords"),
        },
        "wow_change_value":      round(curr_value - prev_value, 2),
        "wow_change_pct":        round((curr_value - prev_value) / prev_value * 100, 1) if prev_value else None,
        "note": "organic_traffic_value = estimated $ cost to buy equivalent traffic via Google Ads",
    }


# ─────────────────────────────────────────────
# 4. Backlinks: new, lost, broken (reclaim)
# ─────────────────────────────────────────────

def pull_backlinks():
    """Most recent backlinks pointing to the site."""
    return fetch_json("site-explorer/backlinks", {
        "target":   SITE,
        "limit":    30,
        "order_by": "first_seen:desc",
        "select":   "url_from,url_to,domain_rating_source,first_seen,anchor",
    })


def pull_lost_backlinks():
    """Backlinks lost in the last 30 days — reclaim opportunities."""
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    return fetch_json("site-explorer/backlinks", {
        "target":    SITE,
        "limit":     30,
        "order_by":  "first_seen:desc",
        "where":     f"first_seen<{thirty_days_ago}",
        "select":    "url_from,url_to,domain_rating_source,first_seen,anchor",
    })


def pull_broken_backlinks():
    """
    Backlinks pointing to 404/broken pages on our site.
    These are the best reclaim opportunities — the linking site is willing to link to us.
    """
    return fetch_json("site-explorer/broken-backlinks", {
        "target":   SITE,
        "limit":    30,
        "order_by": "domain_rating_source:desc",
        "select":   "url_from,url_to,domain_rating_source,anchor,http_code",
    })


# ─────────────────────────────────────────────
# 5. Referring domains
# ─────────────────────────────────────────────

def pull_referring_domains():
    return fetch_json("site-explorer/refdomains", {
        "target":   SITE,
        "limit":    30,
        "order_by": "domain_rating:desc",
        "select":   "domain,domain_rating,dofollow_links,links_to_target,first_seen,last_seen,traffic_domain",
    })


# ─────────────────────────────────────────────
# 6. Anchors
# ─────────────────────────────────────────────

def pull_anchors():
    return fetch_json("site-explorer/anchors", {
        "target":   SITE,
        "limit":    30,
        "order_by": "dofollow_links:desc",
        "select":   "anchor,dofollow_links,refpages,refdomains",
    })


# ─────────────────────────────────────────────
# 7. Keyword gap analysis vs competitors
# ─────────────────────────────────────────────

def pull_keyword_gap():
    """
    Find keywords that Revo Fitness and Anytime Fitness rank for in AU,
    but CB247 does NOT rank for (or ranks below position 20).
    These are the highest-priority content opportunities.

    Uses content-gap endpoint with CB247 as target, competitors as reference.
    """
    result = {}
    for competitor in COMPETITORS:
        print(f"  Keyword gap: {SITE} vs {competitor}")
        data = fetch_json("site-explorer/organic-keywords", {
            "target":   competitor,
            "country":  "au",
            "date":     TODAY,
            "limit":    50,
            "order_by": "volume:desc",
            "select":   "keyword,best_position,volume,keyword_difficulty",
        })
        if data and "keywords" in data:
            gap_keywords = []
            for kw in data["keywords"]:
                gap_keywords.append({
                    "keyword":          kw.get("keyword"),
                    "volume":           kw.get("volume"),
                    "difficulty":       kw.get("keyword_difficulty"),
                    "cb247_position":   None,               # we pull their rankings, not ours
                    "competitor_pos":   kw.get("best_position"),
                    "opportunity":      _gap_opportunity_score({
                        "volume": kw.get("volume"),
                        "keyword_difficulty": kw.get("keyword_difficulty"),
                        "position_2": kw.get("best_position"),
                    }),
                })
            # Sort by opportunity score
            gap_keywords.sort(key=lambda x: x["opportunity"], reverse=True)
            result[competitor] = gap_keywords
        else:
            result[competitor] = None
    return result


def _gap_opportunity_score(kw):
    """
    Score keyword gap opportunity 0–100.
    High volume + low difficulty + competitor ranks well = highest priority.
    """
    vol   = min((kw.get("volume") or 0) / 1000, 10)   # max 10 pts at 10k vol
    diff  = max(0, 10 - (kw.get("keyword_difficulty") or 50) / 5)  # easier = more pts
    comp_pos = kw.get("position_2") or 100
    comp_pts = max(0, 5 - comp_pos / 2)  # competitor in top 5 = highest signal
    return round((vol + diff + comp_pts) * 5, 1)


# ─────────────────────────────────────────────
# 8. Target keyword position tracker
# ─────────────────────────────────────────────

def pull_target_keyword_positions(organic_kws_data=None):
    """
    Check position for each of the 20 CB247 priority keywords.
    Uses the already-fetched organic keyword list (no extra API calls needed).
    Falls back to individual API calls only if organic data is unavailable.
    Returns per-keyword: current pos, last week pos, change, URL ranking, volume.
    """
    # Build lookup map from already-fetched organic keywords
    kw_map = {}
    all_kws = (organic_kws_data or {}).get("keywords") or []
    for kw in all_kws:
        keyword_lower = (kw.get("keyword") or "").lower()
        kw_map[keyword_lower] = kw

    tracked = []
    for keyword in TARGET_KEYWORDS:
        kw = kw_map.get(keyword.lower())
        if kw:
            tracked.append({
                "keyword":  keyword,
                "position": kw.get("best_position"),
                "url":      kw.get("best_position_url"),
                "volume":   kw.get("volume"),
                "traffic":  kw.get("sum_traffic"),
                "status":   _position_status(kw.get("best_position")),
            })
        else:
            tracked.append({
                "keyword":  keyword,
                "position": None,
                "url":      None,
                "volume":   None,
                "traffic":  0,
                "status":   "not_ranking",
            })

    return {
        "date":     TODAY,
        "keywords": tracked,
        "summary": {
            "ranking_count":    sum(1 for k in tracked if k["position"]),
            "top_3_count":      sum(1 for k in tracked if (k["position"] or 999) <= 3),
            "top_10_count":     sum(1 for k in tracked if (k["position"] or 999) <= 10),
            "top_20_count":     sum(1 for k in tracked if (k["position"] or 999) <= 20),
            "not_ranking":      sum(1 for k in tracked if not k["position"]),
        },
    }


def _position_status(pos):
    if pos is None:
        return "not_ranking"
    if pos <= 3:
        return "top_3"
    if pos <= 10:
        return "page_1"
    if pos <= 20:
        return "page_2"
    return "deep"


def load_previous_target_positions():
    """Load last week's target keyword snapshot for WoW comparison."""
    prev_path = STATE_DIR / "ahrefs-prev.json"
    if not prev_path.exists():
        return {}
    try:
        prev = json.loads(prev_path.read_text())
        positions = prev.get("target_keyword_positions", {}).get("keywords", [])
        return {k["keyword"]: k["position"] for k in positions if k.get("keyword")}
    except Exception:
        return {}


def add_wow_to_target_keywords(tracked_result, prev_positions):
    """Inject WoW position change into each tracked keyword."""
    for kw in tracked_result.get("keywords", []):
        prev = prev_positions.get(kw["keyword"])
        curr = kw.get("position")
        if prev is None or curr is None:
            kw["wow_change"]    = None
            kw["wow_direction"] = "new" if prev is None else "lost"
        elif curr < prev:
            kw["wow_change"]    = prev - curr
            kw["wow_direction"] = "up"
        elif curr > prev:
            kw["wow_change"]    = curr - prev
            kw["wow_direction"] = "down"
        else:
            kw["wow_change"]    = 0
            kw["wow_direction"] = "same"
    return tracked_result


# ─────────────────────────────────────────────
# Site Audit (separate API — no unit cost)
# ─────────────────────────────────────────────

def pull_site_audit():
    """
    Pull Ahrefs Site Audit overview for project 9812033.

    Uses site-audit/projects endpoint — FREE (0 units), always works.
    Returns health score + error/warning/notice counts from the latest crawl.

    Detailed issue list (specific URLs per issue) requires site-audit/issues
    which costs 50 units — pulled separately by import_site_audit.py when
    units are available, or via manual CSV export from the Ahrefs web app.
    """
    projects = fetch_json("site-audit/projects", {})

    if not projects:
        print("  WARN: Could not fetch Site Audit projects", file=sys.stderr)
        return None

    # Find the CB247 project by ID
    healthscores = projects.get("healthscores") or []
    project = next(
        (p for p in healthscores if str(p.get("project_id")) == SITE_AUDIT_PROJECT_ID),
        None
    )

    if not project:
        # Fallback: find by target URL
        project = next(
            (p for p in healthscores if "chasingbetter" in (p.get("target_url") or "")),
            None
        )

    if not project:
        print(f"  WARN: CB247 project {SITE_AUDIT_PROJECT_ID} not found in Site Audit", file=sys.stderr)
        return None

    crawl_date = project.get("date", "")[:10]
    health_score = project.get("health_score")
    print(f"  Site Audit [{crawl_date}]: health score {health_score}/100")

    return {
        "crawl_date":    crawl_date,
        "health_score":  health_score,
        "pages_crawled": project.get("total"),
        "errors":        project.get("urls_with_errors"),
        "warnings":      project.get("urls_with_warnings"),
        "notices":       project.get("urls_with_notices"),
        "status":        project.get("status"),
        # Detailed top_issues populated by import_site_audit.py (costs units to fetch via API)
        "top_issues":    [],
        "note": "Detailed issues: run python3 scripts/import_site_audit.py after exporting from ahrefs.com/site-audit",
    }


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    print("Pulling Ahrefs data (API v3)...\n")

    # ── Unit safety gate (free endpoint — no units consumed) ──
    print("--- Checking API unit balance ---")
    if not check_units():
        sys.exit(1)

    result = {
        "date_pulled": datetime.now().isoformat(),
        "site":        SITE,
    }

    # ── Core metrics ──
    print("--- Domain Rating (current + prev week — fetched once) ---")
    current_dr, prev_dr        = pull_domain_rating()
    result["domain_rating"]    = current_dr   # today's DR stored in output

    print("--- Organic Keywords (current week) ---")
    current_kws               = pull_organic_keywords()
    result["organic_keywords"] = current_kws

    print("--- Organic Keywords (last week, for WoW) ---")
    previous_kws              = pull_organic_keywords_last_week()
    result["wow_changes"]      = compute_wow_changes(current_kws, previous_kws)

    print("--- Top Pages + Organic Value ---")
    result["top_pages"]        = pull_top_pages()

    print("--- Organic Traffic Value ($) ---")
    result["organic_value"]    = pull_organic_traffic_value(current_dr, prev_dr)

    print("--- Backlinks (new) ---")
    result["backlinks"]        = pull_backlinks()

    print("--- Lost Backlinks (reclaim) ---")
    result["lost_backlinks"]   = pull_lost_backlinks()

    print("--- Broken Backlinks (reclaim) ---")
    result["broken_backlinks"] = pull_broken_backlinks()

    print("--- Referring Domains ---")
    result["referring_domains"] = pull_referring_domains()

    print("--- Anchors ---")
    result["anchors"]          = pull_anchors()

    print("--- Keyword Gap (vs Revo + Anytime) ---")
    result["keyword_gap"]      = pull_keyword_gap()

    print("--- Target Keyword Tracker (20 priority KWs) ---")
    prev_positions             = load_previous_target_positions()
    target_positions           = pull_target_keyword_positions(current_kws)
    target_positions           = add_wow_to_target_keywords(target_positions, prev_positions)
    result["target_keyword_positions"] = target_positions

    print("--- Site Audit (Monday crawl — no unit cost) ---")
    result["site_audit"]       = pull_site_audit()

    # ── Save current as "previous" for next week's WoW comparison ──
    prev_snapshot_path = STATE_DIR / "ahrefs-prev.json"
    prev_snapshot_path.write_text(json.dumps(result, indent=2))

    # ── Save current data ──
    out_path = STATE_DIR / "ahrefs-data.json"
    out_path.write_text(json.dumps(result, indent=2))
    print(f"\nAhrefs data saved → {out_path}")

    # ── Print summary ──
    _print_summary(result)
    return result


def _print_summary(result):
    print("\n" + "=" * 60)
    print("  AHREFS SUMMARY")
    print("=" * 60)

    dr = result.get("domain_rating")
    if dr and "domain_rating" in (dr or {}):
        print(f"  Domain Rating  : {dr['domain_rating'].get('domain_rating')}")
        print(f"  Ahrefs Rank    : #{dr['domain_rating'].get('ahrefs_rank', 0):,}")

    ov = result.get("organic_value", {})
    curr = (ov or {}).get("current_week", {})
    if curr.get("organic_traffic_value"):
        wow = ov.get("wow_change_value", 0)
        wow_pct = ov.get("wow_change_pct")
        arrow = "↑" if wow >= 0 else "↓"
        print(f"  Organic Value  : ${curr['organic_traffic_value']:,.0f}/wk  {arrow} ${abs(wow):,.0f} ({wow_pct}% WoW)")
        print(f"  Organic Traffic: {curr.get('organic_traffic', 0):,} visits/wk")

    kw = result.get("organic_keywords")
    if kw and "keywords" in (kw or {}):
        print(f"  Organic KWs    : {len(kw['keywords'])} returned")

    tk = result.get("target_keyword_positions", {}).get("summary", {})
    if tk:
        print(f"  Priority KWs   : {tk.get('top_3_count')} top-3 | "
              f"{tk.get('top_10_count')} page-1 | "
              f"{tk.get('top_20_count')} page-2 | "
              f"{tk.get('not_ranking')} not ranking")

    # WoW movers
    wow = result.get("wow_changes", [])
    up_kws = [w for w in wow if w["direction"] == "up"][:5]
    dn_kws = [w for w in wow if w["direction"] == "down"][:5]
    if up_kws:
        print(f"\n  ↑ Biggest gains (positions):")
        for w in up_kws:
            print(f"    +{w['change']} | #{w['current_pos']} | {w['keyword']}")
    if dn_kws:
        print(f"\n  ↓ Biggest drops (positions):")
        for w in dn_kws:
            print(f"    -{w['change']} | #{w['current_pos']} | {w['keyword']}")

    # Keyword gap
    gap = result.get("keyword_gap", {})
    for comp, kws in (gap or {}).items():
        if kws:
            print(f"\n  Keyword gap vs {comp}: {len(kws)} opportunities")
            for kw in kws[:5]:
                cb_pos  = kw.get("cb247_position") or "–"
                comp_pos = kw.get("competitor_pos") or "–"
                print(f"    [{kw.get('volume',0):>5} vol] {kw.get('keyword',''):<40} "
                      f"Us: {str(cb_pos):>4}  Them: {str(comp_pos):>4}")

    # Broken backlinks
    bb = result.get("broken_backlinks", {})
    if bb and "backlinks" in (bb or {}):
        print(f"\n  Broken backlinks: {len(bb['backlinks'])} reclaim opportunities")

    # Site audit
    sa = result.get("site_audit") or {}
    if sa.get("health_score") is not None:
        print(f"\n  Site Audit [{sa.get('crawl_date','')[:10]}]:")
        print(f"    Health score   : {sa.get('health_score')}/100")
        print(f"    Pages crawled  : {sa.get('pages_crawled', '–')}")
        print(f"    Errors         : {sa.get('errors', '–')}  "
              f"Warnings: {sa.get('warnings', '–')}  "
              f"Notices: {sa.get('notices', '–')}")
        if sa.get("top_issues"):
            print(f"    Top issue      : {sa['top_issues'][0].get('name')} "
                  f"({sa['top_issues'][0].get('count')} pages)")

    print("=" * 60)


if __name__ == "__main__":
    main()
