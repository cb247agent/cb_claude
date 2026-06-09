"""
pull_mwcc_apify.py — MWCC market-intelligence scrapes via Apify.

Mirrors the 4 missing pipelines from scripts/pull_apify.py (CB247) for the
childcare niche:

  1. SERP        → state/mwcc-apify-serp.json
       Track MWCC's organic + local pack position for childcare keywords
       per suburb (Armadale, Midvale, Rockingham, Seville Grove, Waikiki)
       + service-type queries (oshc perth, vacation care perth, ccs perth).
       Feeds: seo-agent-mwcc.

  2. Reddit      → state/mwcc-reddit-intel.json
       Scrape r/perth + r/perthAustralia for parent pain points around
       childcare ("can't find a centre", "ccs confusion", "waitlist",
       "vacation care"). Extracts competitor mentions, pain-point themes,
       and most-common parent phrases. Feeds: research-perth-childcare +
       audience-intel-mwcc.

  3. Google Trends → state/mwcc-google-trends.json
       AU-WA region trends for childcare-related queries — "ccs",
       "vacation care", "perth childcare", "oshc", "long day care",
       "out of school hours care", "child care subsidy". Identifies
       rising vs declining topics. Feeds: content-intel-mwcc +
       research-perth-childcare.

  4. FB Ads Library → state/mwcc-fb-ads-intel.json
       Scrape active Facebook Ads from MWCC's competitors (Goodstart,
       Nido Early School, Care for Kids). Extract headlines, body copy,
       CTAs, format mix. Feeds: competitor-spy-mwcc + paid-ads-mwcc.

Cost-conscious (Tia subscription set to "once a week"):
  - SERP:    1 actor call × 7 queries        ≈ $0.05-0.15
  - Reddit:  1 actor call × 4 searches × 10  ≈ $0.10-0.25
  - Trends:  1 actor call × 7 keywords        ≈ $0.05-0.10
  - FB Ads:  1 actor call × 3 competitors × 20 ≈ $0.30-0.50
  Total per weekly run: ~$0.50-1.00

All 4 fail gracefully — each pipeline writes an available=false placeholder
if the actor is unavailable, so the agent layer always has a file to read.

Run (default = all 4 pipelines):
    .venv/bin/python3.13 scripts/pull_mwcc_apify.py
    .venv/bin/python3.13 scripts/pull_mwcc_apify.py --serp     (single pipeline)
    .venv/bin/python3.13 scripts/pull_mwcc_apify.py --reddit
    .venv/bin/python3.13 scripts/pull_mwcc_apify.py --trends
    .venv/bin/python3.13 scripts/pull_mwcc_apify.py --fbads

Wires into weekly-report-mwcc.sh as Step 4.6c (between viral hashtag scrape
and GBP performance pull).
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

BASE_DIR  = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"

# ── .env loader (matches the pattern other MWCC scripts use) ────────────
def _load_env():
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val

_load_env()

APIFY_API_KEY        = os.environ.get("APIFY_API_KEY", "")
APIFY_BASE_URL       = "https://api.apify.com/v2"
APIFY_SERP_ACTOR_ID   = "nFJndFXA5zjCTuudP"              # Google Search Scraper
APIFY_REDDIT_ACTOR_ID = "trudax~reddit-scraper"          # Reddit (verified 09 Jun 2026 — CB247's apify/reddit-scraper is gone)
APIFY_TRENDS_ACTOR_ID = "emastra~google-trends-scraper"  # Google Trends (verified live, but needs minimal payload)
APIFY_FBADS_ACTOR_ID  = "apify~facebook-ads-scraper"     # FB Ads (verified — tilde, not slash)

# ── MWCC SERP keywords — childcare + suburb + service-type queries ─────
SERP_QUERIES = [
    # Suburb-level (highest commercial intent per centre)
    "childcare midvale",
    "childcare seville grove",
    "childcare armadale",
    "childcare rockingham",
    "childcare waikiki",
    # Service-type (broader awareness queries)
    "oshc perth",
    "vacation care perth",
    "ccs perth",
]
SERP_RESULTS_PER_QUERY = 5  # Top 5 is enough for rank tracking

# ── Reddit searches — Perth-relevant subs, childcare pain queries ──────
REDDIT_SEARCHES = [
    {"subreddit": "perth",           "query": "childcare",      "label": "perth_childcare"},
    {"subreddit": "perth",           "query": "daycare",        "label": "perth_daycare"},
    {"subreddit": "perth",           "query": "vacation care",  "label": "perth_vacation_care"},
    {"subreddit": "AusFinance",      "query": "ccs childcare",  "label": "ausfinance_ccs"},
]
REDDIT_MAX_ITEMS_PER_SEARCH = 10  # 4 searches × 10 = max 40 posts
REDDIT_MAX_COMMENTS_PER_POST = 3

# ── Google Trends — AU-WA childcare keywords ───────────────────────────
TRENDS_KEYWORDS = [
    "ccs",
    "vacation care",
    "perth childcare",
    "oshc",
    "long day care",
    "child care subsidy",
    "kindy enrolment",
]

# ── FB Ads Library — MWCC competitors ──────────────────────────────────
# Goodstart national + Nido national + Care for Kids aggregator.
# Midvale Hub doesn't run visible national FB ads (confirmed in earlier
# research) so excluded — would return empty.
FB_ADS_COMPETITORS = [
    {"name": "Goodstart Early Learning", "page_name": "goodstartearlylearning"},
    {"name": "Nido Early School",        "page_name": "nidoearlyschool"},
    {"name": "Care for Kids",            "page_name": "careforkids"},
]
FB_ADS_MAX_PER_COMPETITOR = 20


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Apify generic runner (ported from pull_apify.py) ───────────────────

def _run_apify_actor(actor_id: str, payload: dict, timeout_checks: int = 72) -> list | None:
    """Start actor, poll till SUCCEEDED, return dataset items.

    Returns None on any failure (no key / actor errors / timeout). Caller
    treats None as 'this platform unavailable this run'.
    """
    if not APIFY_API_KEY:
        return None

    try:
        r = requests.post(
            f"{APIFY_BASE_URL}/acts/{actor_id}/runs",
            params={"token": APIFY_API_KEY},
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        run_data   = r.json()
        run_id     = run_data["data"]["id"]
        dataset_id = run_data["data"]["defaultDatasetId"]
    except Exception as e:
        print(f"  Apify start error [{actor_id}]: {e}")
        return None

    status_url = f"{APIFY_BASE_URL}/acts/{actor_id}/runs/{run_id}"
    poll_interval = 5
    for i in range(timeout_checks):
        try:
            r = requests.get(status_url, params={"token": APIFY_API_KEY}, timeout=10)
            r.raise_for_status()
            status = r.json()["data"].get("status")
            if status == "SUCCEEDED":
                break
            if status in ("FAILED", "ABORTED", "TIMED_OUT"):
                print(f"  Apify run {status} [{actor_id}]")
                return None
            if i % 6 == 0:
                print(f"  Apify waiting... ({i * poll_interval}s elapsed, status={status})")
        except Exception:
            pass
        time.sleep(poll_interval)
    else:
        print(f"  Apify run timed out [{actor_id}]")
        return None

    try:
        r = requests.get(
            f"{APIFY_BASE_URL}/datasets/{dataset_id}/items",
            params={"token": APIFY_API_KEY, "clean": "true"},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  Apify fetch error [{actor_id}]: {e}")
        return None


def _write_placeholder(path: Path, reason: str, extra: dict | None = None) -> None:
    """Write an available=false placeholder file."""
    out = {
        "scraped":         _now_iso(),
        "brand":           "mwcc",
        "available":       False,
        "limitation_note": reason,
    }
    if extra:
        out.update(extra)
    STATE_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"  ⚠️  Placeholder → {path.relative_to(BASE_DIR)}: {reason}")


# ═══════════════════════════════════════════════════════════════════════
# Pipeline 1 — SERP (childcare keyword rankings + local pack)
# ═══════════════════════════════════════════════════════════════════════

def pull_serp() -> dict | None:
    """Track MWCC organic + local pack position per childcare query."""
    out_path = STATE_DIR / "mwcc-apify-serp.json"
    if not APIFY_API_KEY:
        _write_placeholder(out_path, "APIFY_API_KEY not set.")
        return None

    print(f"  → SERP: {len(SERP_QUERIES)} queries (top {SERP_RESULTS_PER_QUERY})")

    all_results = []
    for query in SERP_QUERIES:
        print(f"     · '{query}'")
        items = _run_apify_actor(
            APIFY_SERP_ACTOR_ID,
            {
                "queries":        query,
                "countryCode":    "au",
                "languageCode":   "en",
                "resultsPerPage": SERP_RESULTS_PER_QUERY,
                "mobileResults":  False,
            },
        )
        if not items:
            continue

        organic, local_pack = [], []
        for item in items:
            for r in item.get("organicResults", []):
                organic.append({
                    "title":    r.get("title", ""),
                    "url":      r.get("url", ""),
                    "snippet":  r.get("snippet", ""),
                    "position": r.get("position", len(organic) + 1),
                })
                if len(organic) >= SERP_RESULTS_PER_QUERY:
                    break
            for r in (item.get("localResults") or item.get("locals") or []):
                local_pack.append({
                    "position": r.get("position"),
                    "title":    r.get("title", ""),
                    "rating":   r.get("rating"),
                    "reviews":  r.get("reviewsCount") or r.get("reviews"),
                    "address":  r.get("address", ""),
                    "website":  r.get("website", ""),
                    "phone":    r.get("phone", ""),
                })
        # MWCC presence flag — was the brand in top 5 organic or local pack?
        mwcc_organic_pos   = next((o["position"] for o in organic
                                   if "myworldcc" in (o.get("url") or "").lower()), None)
        mwcc_local_pack_pos = next((l["position"] for l in local_pack
                                    if "my world" in (l.get("title") or "").lower()), None)
        all_results.append({
            "query":               query,
            "organic":             organic,
            "local_pack":          local_pack,
            "mwcc_organic_pos":    mwcc_organic_pos,
            "mwcc_local_pack_pos": mwcc_local_pack_pos,
        })
        time.sleep(2)

    if not all_results:
        _write_placeholder(out_path, "All SERP queries returned no data.")
        return None

    out = {
        "scraped":         _now_iso(),
        "brand":           "mwcc",
        "available":       True,
        "queries_tracked": len(SERP_QUERIES),
        "queries_with_data": len(all_results),
        "results":         all_results,
    }
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    found_in = sum(1 for r in all_results
                   if r["mwcc_organic_pos"] or r["mwcc_local_pack_pos"])
    print(f"  ✅ SERP saved → mwcc-apify-serp.json  ({found_in}/{len(all_results)} queries show MWCC)")
    return out


# ═══════════════════════════════════════════════════════════════════════
# Pipeline 2 — Reddit Intel (parent pain points + competitor mentions)
# ═══════════════════════════════════════════════════════════════════════

def pull_reddit_intel() -> dict | None:
    """Scrape r/perth + r/AusFinance for childcare parent voice."""
    out_path = STATE_DIR / "mwcc-reddit-intel.json"
    if not APIFY_API_KEY:
        _write_placeholder(out_path, "APIFY_API_KEY not set.")
        return None

    print(f"  → Reddit: {len(REDDIT_SEARCHES)} searches")

    all_posts = []
    for search in REDDIT_SEARCHES:
        print(f"     · r/{search['subreddit']} '{search['query']}'")
        items = _run_apify_actor(
            APIFY_REDDIT_ACTOR_ID,
            {
                "startUrls": [{
                    "url": (
                        f"https://www.reddit.com/r/{search['subreddit']}/search/"
                        f"?q={search['query'].replace(' ', '+')}"
                        f"&restrict_sr=1&sort=hot"
                    ),
                    "method": "GET",
                }],
                "maxItems":     REDDIT_MAX_ITEMS_PER_SEARCH,
                "maxComments":  REDDIT_MAX_COMMENTS_PER_POST,
                "skipComments": False,
                "proxy":        {"useApifyProxy": True},
            },
            timeout_checks=60,
        )
        if items:
            for item in items:
                post = _normalise_reddit_post(item, search)
                if post:
                    all_posts.append(post)
        time.sleep(2)

    if not all_posts:
        _write_placeholder(out_path,
            "Reddit scrape returned no posts. Apify subscription credit may "
            "be depleted (Reddit actor is on the broken-actors list) or "
            "search terms too niche this week.")
        return None

    competitor_mentions = _extract_competitor_mentions(all_posts)
    pain_points         = _extract_pain_points(all_posts)
    key_phrases         = _extract_key_phrases(all_posts)
    all_posts.sort(key=lambda p: p.get("score", 0), reverse=True)

    out = {
        "scraped":             _now_iso(),
        "brand":               "mwcc",
        "available":           True,
        "posts_collected":     len(all_posts),
        "top_posts":           all_posts[:20],
        "competitor_mentions": competitor_mentions,
        "pain_points":         pain_points,
        "key_phrases":         key_phrases,
    }
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"  ✅ Reddit saved → mwcc-reddit-intel.json  ({len(all_posts)} posts, "
          f"{len(pain_points)} pain themes, {len(competitor_mentions)} brand mentions)")
    return out


def _normalise_reddit_post(item: dict, search: dict) -> dict | None:
    title = item.get("title") or ""
    body  = item.get("body") or item.get("selftext") or ""
    comments = []
    for c in (item.get("comments") or [])[:5]:
        body_c = (c.get("body") or "").strip()
        if body_c and len(body_c) > 10:
            comments.append(body_c[:300])
    return {
        "subreddit":   search["subreddit"],
        "label":       search["label"],
        "title":       title[:200],
        "body":        body[:500],
        "score":       item.get("score") or 0,
        "comments":    comments,
        "url":         item.get("url") or "",
        "created_utc": item.get("createdAt") or "",
        "full_text":   f"{title} {body}".lower(),
    }


def _extract_competitor_mentions(posts: list[dict]) -> list[dict]:
    """Count mentions of MWCC + childcare competitors across posts + comments."""
    brands = {
        "mwcc":         ["my world childcare", "myworldcc", "my world child care"],
        "midvale_hub":  ["midvale hub", "midvalehub"],
        "goodstart":    ["goodstart", "good start early learning"],
        "nido":         ["nido", "nido early"],
        "care_for_kids": ["care for kids", "careforkids"],
        "kindicare":    ["kindicare"],
        "guardian":     ["guardian early learning", "guardian childcare"],
        "ymca":         ["ymca childcare", "ymca oshc"],
    }
    counts = {brand: 0 for brand in brands}
    for post in posts:
        text = (post.get("full_text", "") + " " + " ".join(post.get("comments", []))).lower()
        for brand, signals in brands.items():
            if any(s in text for s in signals):
                counts[brand] += 1
    return sorted(
        [{"brand": b, "mentions": c} for b, c in counts.items() if c > 0],
        key=lambda x: x["mentions"], reverse=True,
    )


def _extract_pain_points(posts: list[dict]) -> list[dict]:
    """MWCC-specific pain points — childcare parent concerns."""
    pain_signals = {
        "waitlist":      ["waitlist", "wait list", "waiting list", "no places", "fully booked"],
        "ccs_confusion": ["ccs", "subsidy", "rebate", "centrelink"],
        "fees":          ["expensive", "fees", "cost", "afford", "price", "$"],
        "hours":         ["hours", "drop off", "drop-off", "pick up", "pick-up", "closing"],
        "settling":      ["settling", "settle in", "first day", "crying", "anxiety"],
        "educators":     ["educator", "staff", "carer", "qualifications", "ratio"],
        "food":          ["food", "meals", "lunch", "menu", "nutrition"],
        "communication": ["app", "kinderloop", "xplor", "owna", "updates", "photos"],
        "nqs":           ["nqs", "rating", "exceeding", "meeting", "acecqa"],
        "holidays":      ["holiday", "vacation care", "school holidays", "term break"],
    }
    pain_counts   = {k: 0 for k in pain_signals}
    pain_examples = {k: [] for k in pain_signals}
    for post in posts:
        text = (post.get("full_text", "") + " " + " ".join(post.get("comments", []))).lower()
        for pain, signals in pain_signals.items():
            if any(s in text for s in signals):
                pain_counts[pain] += 1
                if len(pain_examples[pain]) < 3:
                    pain_examples[pain].append(post.get("title", "")[:100])
    return [
        {"pain_point": k, "mentions": v, "examples": pain_examples[k]}
        for k, v in sorted(pain_counts.items(), key=lambda x: x[1], reverse=True)
        if v > 0
    ]


def _extract_key_phrases(posts: list[dict]) -> list[dict]:
    """Most common parent phrases when talking childcare."""
    words: Counter = Counter()
    stop = {
        "the", "a", "an", "is", "in", "it", "to", "of", "and", "or", "for",
        "my", "i", "you", "at", "on", "with", "this", "that", "was", "be",
        "are", "they", "we", "has", "have", "not", "but", "if", "so", "just",
        "like", "as", "do", "childcare", "child", "care", "perth", "kids",
        "daycare", "what", "any", "anyone", "your", "their", "from", "would",
        "could", "should", "would", "really", "very",
    }
    for post in posts:
        text = (post.get("full_text", "") + " " + " ".join(post.get("comments", []))).lower()
        for word in text.split():
            word = word.strip(".,?!()\"'")
            if word and len(word) > 3 and word not in stop:
                words[word] += 1
    return [{"phrase": w, "count": c} for w, c in words.most_common(30)]


# ═══════════════════════════════════════════════════════════════════════
# Pipeline 3 — Google Trends (childcare topic momentum in WA)
# ═══════════════════════════════════════════════════════════════════════

def pull_google_trends() -> dict | None:
    """AU-WA region trends for childcare-related queries."""
    out_path = STATE_DIR / "mwcc-google-trends.json"
    if not APIFY_API_KEY:
        _write_placeholder(out_path, "APIFY_API_KEY not set.")
        return None

    print(f"  → Google Trends: {len(TRENDS_KEYWORDS)} keywords, geo=AU-WA, range=3m")

    # NOTE: emastra google-trends-scraper rejected payload with 'category' int.
    # Stripped to minimal schema — matches the actor's current example.
    items = _run_apify_actor(
        APIFY_TRENDS_ACTOR_ID,
        {
            "searchTerms": TRENDS_KEYWORDS,
            "geo":         "AU-WA",      # Western Australia
            "timeRange":   "today 3-m",  # Last 3 months
        },
    )
    if not items:
        _write_placeholder(out_path,
            "Google Trends actor returned no data. May be on the "
            "broken-actors list pending subscription top-up.")
        return None

    trends = []
    for item in items:
        keyword = item.get("keyword") or item.get("query") or ""
        interest = item.get("interestOverTime") or item.get("values") or []
        current_value = interest[-1].get("value") if interest else None
        prev_value    = interest[-4].get("value") if len(interest) >= 4 else None

        trend_dir = "stable"
        if current_value and prev_value:
            if current_value > prev_value * 1.15:
                trend_dir = "rising"
            elif current_value < prev_value * 0.85:
                trend_dir = "declining"

        trends.append({
            "keyword":       keyword,
            "current_value": current_value,
            "prev_value":    prev_value,
            "direction":     trend_dir,
            "interest_data": interest[-12:],
            "related":       item.get("relatedTopics") or item.get("relatedQueries") or [],
        })
    trends.sort(key=lambda t: t.get("current_value") or 0, reverse=True)
    rising   = [t for t in trends if t["direction"] == "rising"]
    declining = [t for t in trends if t["direction"] == "declining"]

    out = {
        "scraped":          _now_iso(),
        "brand":            "mwcc",
        "available":        True,
        "geo":              "AU-WA (Western Australia)",
        "keywords_tracked": len(trends),
        "trends":           trends,
        "rising_topics":    rising,
        "declining_topics": declining,
        "content_signal":   _trends_content_signal(rising),
    }
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"  ✅ Trends saved → mwcc-google-trends.json  "
          f"({len(rising)} rising, {len(declining)} declining)")
    return out


def _trends_content_signal(rising_trends: list[dict]) -> list[dict]:
    """Convert rising trends into actionable content signals."""
    signals = []
    for t in rising_trends[:5]:
        signals.append({
            "topic":   t["keyword"],
            "signal":  "Interest rising in WA — publish content now to catch the wave",
            "urgency": "high" if (t.get("current_value") or 0) > 60 else "medium",
        })
    return signals


# ═══════════════════════════════════════════════════════════════════════
# Pipeline 4 — FB Ads Library (competitor childcare ad creatives)
# ═══════════════════════════════════════════════════════════════════════

def pull_facebook_ads() -> dict | None:
    """Scrape active FB Ads from MWCC's national chain competitors."""
    out_path = STATE_DIR / "mwcc-fb-ads-intel.json"
    if not APIFY_API_KEY:
        _write_placeholder(out_path, "APIFY_API_KEY not set.")
        return None

    print(f"  → FB Ads: {len(FB_ADS_COMPETITORS)} competitors")

    all_ads = []
    for competitor in FB_ADS_COMPETITORS:
        print(f"     · {competitor['name']}")
        items = _run_apify_actor(
            APIFY_FBADS_ACTOR_ID,
            {
                "searchPageOrAdLibraryUrl": (
                    f"https://www.facebook.com/ads/library/?active_status=active"
                    f"&ad_type=all&country=AU"
                    f"&q={competitor['page_name']}"
                    f"&search_type=keyword_unordered"
                ),
                "maxItems": FB_ADS_MAX_PER_COMPETITOR,
                "proxy":    {"useApifyProxy": True, "apifyProxyCountry": "AU"},
            },
            timeout_checks=90,
        )
        if items:
            for item in items:
                ad = _normalise_fb_ad(item, competitor["name"])
                if ad:
                    all_ads.append(ad)
        time.sleep(3)

    if not all_ads:
        _write_placeholder(out_path,
            "FB Ads Library returned no results. Competitors may not be "
            "running national AU ads this week, or actor on broken list.")
        return None

    analysis = _analyse_competitor_ads(all_ads)
    out = {
        "scraped":             _now_iso(),
        "brand":               "mwcc",
        "available":           True,
        "competitors_checked": [c["name"] for c in FB_ADS_COMPETITORS],
        "ads_found":           len(all_ads),
        "ads":                 all_ads,
        "analysis":            analysis,
    }
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"  ✅ FB Ads saved → mwcc-fb-ads-intel.json  "
          f"({len(all_ads)} ads across {len(set(a['competitor'] for a in all_ads))} competitors)")
    return out


def _normalise_fb_ad(item: dict, competitor_name: str) -> dict | None:
    body = item.get("ad_creative_bodies", [])
    body_text = body[0] if body else (item.get("ad_creative_body") or "")

    title = item.get("ad_creative_link_titles", [])
    title_text = title[0] if title else (item.get("ad_creative_link_title") or "")

    cta = item.get("ad_creative_link_captions", [])
    cta_text = cta[0] if cta else (item.get("cta_text") or "")

    return {
        "competitor":      competitor_name,
        "ad_id":           item.get("id") or item.get("ad_archive_id") or "",
        "headline":        title_text[:200],
        "body":            body_text[:500],
        "cta":             cta_text,
        "format":          item.get("ad_creative_media_type") or item.get("media_type") or "unknown",
        "started":         item.get("ad_delivery_start_time") or "",
        "impressions_min": (item.get("impressions") or {}).get("lower_bound"),
        "impressions_max": (item.get("impressions") or {}).get("upper_bound"),
        "spend_min":       (item.get("spend") or {}).get("lower_bound"),
        "is_active":       item.get("is_active", True),
        "url":             item.get("snapshot_url") or "",
    }


def _analyse_competitor_ads(ads: list[dict]) -> dict:
    """Extract patterns from competitor ads — childcare-specific themes."""
    cta_counter:    Counter = Counter()
    format_counter: Counter = Counter()
    themes:         list[str] = []

    theme_signals = {
        "ccs":            ["ccs", "subsidy", "child care subsidy", "rebate"],
        "enrolment":      ["enrol", "enrolment", "enroll", "spots", "places", "waitlist"],
        "nqs":            ["nqs", "exceeding", "meeting", "rating", "quality"],
        "educators":      ["educator", "qualified", "experienced", "team"],
        "curriculum":     ["learning", "curriculum", "play-based", "programme", "program"],
        "facilities":     ["facility", "centre", "garden", "playground", "kitchen"],
        "free_trial":     ["free", "trial", "first day", "free day", "first week"],
        "tour":           ["tour", "visit", "book", "appointment"],
        "premium":        ["premium", "exclusive", "boutique", "leading"],
    }

    for ad in ads:
        text = (ad.get("headline", "") + " " + ad.get("body", "")).lower()
        if ad.get("cta"):
            cta_counter[ad["cta"]] += 1
        if ad.get("format"):
            format_counter[ad["format"]] += 1
        for theme, signals in theme_signals.items():
            if any(s in text for s in signals):
                themes.append(theme)

    theme_counts = Counter(themes)
    return {
        "top_ctas":     [{"cta": c, "count": n} for c, n in cta_counter.most_common(5)],
        "format_mix":   [{"format": f, "count": n} for f, n in format_counter.most_common(5)],
        "top_themes":   [{"theme": t, "count": n} for t, n in theme_counts.most_common(10)],
    }


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--serp",    action="store_true", help="SERP pipeline only")
    parser.add_argument("--reddit",  action="store_true", help="Reddit pipeline only")
    parser.add_argument("--trends",  action="store_true", help="Google Trends pipeline only")
    parser.add_argument("--fbads",   action="store_true", help="FB Ads pipeline only")
    args = parser.parse_args()

    run_all = not (args.serp or args.reddit or args.trends or args.fbads)

    print(f"\n=== MWCC Apify Pull — {_now_iso()} ===")
    if not APIFY_API_KEY:
        print("⚠️  APIFY_API_KEY missing from .env — all 4 pipelines will write placeholders.")

    if args.serp or run_all:
        print("\n── Pipeline 1: SERP ──")
        pull_serp()

    if args.reddit or run_all:
        print("\n── Pipeline 2: Reddit Intel ──")
        pull_reddit_intel()

    if args.trends or run_all:
        print("\n── Pipeline 3: Google Trends ──")
        pull_google_trends()

    if args.fbads or run_all:
        print("\n── Pipeline 4: FB Ads Library ──")
        pull_facebook_ads()

    print(f"\n=== Done at {_now_iso()} ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
