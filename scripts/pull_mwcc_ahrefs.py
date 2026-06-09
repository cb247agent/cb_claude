"""
pull_mwcc_ahrefs.py — Pull SEO analytics from Ahrefs API v3 for My World Childcare.
Saves to state/mwcc-ahrefs.json (same path as the CSV fallback parser
parse_mwcc_ahrefs_csvs.py, so both write to the same canonical file).
Requires AHREFS_API_KEY in .env (same key as CB247).

Pulls:
  1. Domain rating + Ahrefs rank for myworldcc.com.au
  2. Organic keywords (top 100) + WoW position changes
  3. Top pages by organic traffic + organic value ($)
  4. Referring domains (high-level only — backlinks deferred to save units)
  5. Keyword gap vs MWCC competitors
  6. Target keyword position tracker (20 priority MWCC keywords)

API v3 base: https://api.ahrefs.com/v3/
Auth: Bearer token in Authorization header

Lighter than pull_ahrefs.py (CB247 version): skips backlinks deep-dive +
site audit + anchors to stay under unit budget. SEO emitter reads
organic_keywords + keyword_gap which is the core data.
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
SITE     = "myworldcc.com.au"
BASE_URL = "https://api.ahrefs.com/v3"
TODAY    = datetime.now().strftime("%Y-%m-%d")
LAST_WEEK = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

# MWCC competitors for keyword gap analysis (saved in context/mwcc-competitors.md)
COMPETITORS = [
    "midvalehub.org.au",
    "goodstart.org.au",
    "nido.edu.au",
    "careforkids.com.au",
    "kindicare.com",
]

# ── 20 MWCC priority keywords to track every week ──
# Covers service types (LDC, OSHC, vacation care), locations (5 centres),
# generic high-intent + CCS subsidy queries.
TARGET_KEYWORDS = [
    # Generic high-intent
    "childcare perth",
    "daycare perth",
    "childcare subsidy perth",
    # Per-centre (LDC suburbs)
    "childcare midvale",
    "childcare seville grove",
    "childcare waikiki",
    # Per-centre (OSHC suburbs)
    "oshc armadale",
    "oshc rockingham",
    "oshc midvale",
    "oshc seville grove",
    # Service-specific
    "long day care perth",
    "before school care perth",
    "after school care perth",
    "vacation care perth",
    "baby room perth",
    # Sub-segment
    "kindy program perth",
    "early learning perth",
    "play based learning perth",
    # Brand
    "my world childcare",
    "myworldcc",
]

if not API_KEY or API_KEY.startswith("#") or len(API_KEY) < 10:
    print("AHREFS_API_KEY not set or invalid — skipping MWCC Ahrefs data pull.")
    print("  → Get your key at https://ahrefs.com/api/")
    API_KEY = ""

_UNIT_THRESHOLD = 5_000


def _count_rows(data):
    if not isinstance(data, dict):
        return None
    for key in ("keywords", "backlinks", "pages", "refdomains", "anchors", "healthscores"):
        if key in data and isinstance(data[key], list):
            return len(data[key])
    return None


def fetch_json(endpoint, params=None, _delay=1.5):
    """Fetch JSON from Ahrefs API v3. Same pattern as pull_ahrefs.py."""
    if not API_KEY:
        return None
    import time
    time.sleep(_delay)
    url     = f"{BASE_URL}/{endpoint}"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    params  = params or {}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        if r.status_code == 429 and "<html" in r.text[:50].lower():
            print(f"  WARN: Cloudflare rate limit on [{endpoint}] — wait a few minutes", file=sys.stderr)
            return None
        r.raise_for_status()
        data  = r.json()
        units = r.headers.get("x-api-units-cost-total-actual", "–")
        rows  = _count_rows(data)
        if rows is not None:
            print(f"  [ahrefs] {endpoint}: {rows} rows, {units} units")
        return data
    except requests.exceptions.HTTPError as e:
        print(f"  ERR [{endpoint}]: {e}", file=sys.stderr)
        return None


def check_units():
    """Check remaining Ahrefs API units."""
    data = fetch_json("subscription-info/limits-and-usage", _delay=0)
    if not data:
        return None
    units = data.get("limits_and_usage", {}).get("api_units_balance", 0)
    print(f"  Ahrefs units remaining: {units:,}")
    if units < _UNIT_THRESHOLD:
        print(f"  WARN: below safety threshold ({_UNIT_THRESHOLD:,}) — aborting")
        return None
    return units


def pull_domain_rating():
    data = fetch_json("site-explorer/domain-rating", {
        "target": SITE,
        "date":   TODAY,
        "protocol": "https",
    })
    if not data:
        return None
    return {
        "domain_rating":  data.get("domain_rating"),
        "ahrefs_rank":    data.get("ahrefs_rank"),
    }


def pull_organic_keywords(date=None):
    """Top 100 organic keywords by traffic."""
    data = fetch_json("site-explorer/organic-keywords", {
        "target":   SITE,
        "country":  "au",
        "date":     date or TODAY,
        "select":   "keyword,position,volume,cpc,traffic,url,kd",
        "limit":    100,
        "order_by": "traffic:desc",
    })
    return data.get("keywords", []) if data else []


def pull_top_pages():
    """Top 20 pages by organic traffic."""
    data = fetch_json("site-explorer/top-pages", {
        "target":   SITE,
        "country":  "au",
        "date":     TODAY,
        "select":   "url,traffic,value,top_keyword,top_keyword_volume,top_keyword_position",
        "limit":    20,
        "order_by": "traffic:desc",
    })
    return data.get("pages", []) if data else []


def pull_referring_domains():
    """Top 20 referring domains (high-level only)."""
    data = fetch_json("site-explorer/refdomains", {
        "target":   SITE,
        "select":   "domain,dr,refdomain_ahrefs_rank,traffic,linked_pages",
        "limit":    20,
        "order_by": "dr:desc",
    })
    return data.get("refdomains", []) if data else []


def pull_keyword_gap():
    """For each competitor, find keywords they rank for that MWCC doesn't."""
    gaps = {}
    for competitor in COMPETITORS:
        print(f"  [gap] {competitor}…")
        data = fetch_json("site-explorer/competitors-overview/keyword-intersections", {
            "target":            SITE,
            "competitors":       competitor,
            "country":           "au",
            "intersection_type": "include_other_targets_exclude_target",
            "select":            "keyword,volume,kd,cpc",
            "limit":             20,
            "order_by":          "volume:desc",
        })
        if data:
            gaps[competitor] = data.get("keywords", [])
        else:
            gaps[competitor] = []
    return gaps


def pull_target_keyword_positions():
    """For each of the 20 priority MWCC keywords, fetch current position."""
    tracked = []
    for keyword in TARGET_KEYWORDS:
        print(f"  [tracker] {keyword[:40]}…")
        data = fetch_json("keywords-explorer/overview", {
            "keywords": keyword,
            "country":  "au",
            "select":   "keyword,volume,cpc,difficulty",
        })
        # Get SERP position for our domain
        serp = fetch_json("serp-overview", {
            "keyword": keyword,
            "country": "au",
            "date":    TODAY,
            "select":  "url,position",
            "limit":   100,
        })
        position = None
        if serp:
            for row in serp.get("positions", []):
                url = (row.get("url") or "").lower()
                if SITE in url:
                    position = row.get("position")
                    break
        tracked.append({
            "keyword":    keyword,
            "position":   position,
            "volume":     (data or {}).get("volume"),
            "cpc":        (data or {}).get("cpc"),
            "difficulty": (data or {}).get("difficulty"),
        })
    return tracked


def main():
    print(f"\n=== MWCC Ahrefs Pull — {TODAY} ===")
    print(f"Target: {SITE}")
    print(f"Competitors: {', '.join(COMPETITORS)}")

    if not check_units():
        print("Aborting — units depleted or invalid API key.")
        return

    print("\n[1/5] Domain rating…")
    dr = pull_domain_rating()

    print("\n[2/5] Organic keywords (current week)…")
    current_kws = pull_organic_keywords()

    print("\n[3/5] Top pages…")
    pages = pull_top_pages()

    print("\n[4/5] Keyword gap…")
    gaps = pull_keyword_gap()

    print("\n[5/5] Target keyword position tracker…")
    tracked = pull_target_keyword_positions()

    out = {
        "generated_at":     datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "brand":            "mwcc",
        "domain":           SITE,
        "competitors":      COMPETITORS,
        "domain_rating":    dr,
        "organic_keywords": current_kws,
        "top_pages":        pages,
        "keyword_gap":      gaps,
        "target_keywords":  tracked,
    }

    STATE_DIR.mkdir(exist_ok=True)
    output_file = STATE_DIR / "mwcc-ahrefs.json"
    output_file.write_text(json.dumps(out, indent=2))
    print(f"\n[saved] {output_file}")
    print(f"  organic_keywords: {len(current_kws)}")
    print(f"  top_pages:        {len(pages)}")
    print(f"  keyword_gap:      {sum(len(g) for g in gaps.values())} keywords across {len(gaps)} competitors")
    print(f"  target_tracked:   {len(tracked)} priority keywords")


if __name__ == "__main__":
    main()
