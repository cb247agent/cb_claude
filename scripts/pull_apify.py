"""
pull_apify.py — SERP + Maps + Social + Reddit + Trends + FB Ads via Apify.
Saves to state/apify-data.json  +  state/social-trends.json

Pipelines:
  1. SERP Analysis — organic + local pack rankings for CB247 target keywords
     Actor: nFJndFXA5zjCTuudP (google-search-scraper)
     Fallback: Google Custom Search API → SerpAPI

  2. Competitor GBP Benchmarking — Google Maps listing data for competitors + CB247
     Actor: compass~crawler-google-places

  3. Social Trends — TikTok + Instagram trending fitness content
     Actors: clockworks~tiktok-scraper, apify~instagram-hashtag-scraper

  4. Reddit Intel — r/Perth + r/fitness audience language + pain points
     Actor: trudax~reddit-scraper

  5. Google Trends Perth — trending fitness topics in WA right now
     Actor: emastra~google-trends-scraper

  6. Facebook Ads Library — Revo Fitness + Anytime Fitness active creatives
     Actor: curious_coder~facebook-ads-scraper

Auth: APIFY_API_KEY in .env
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import requests

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
load_dotenv(BASE_DIR / ".env")

APIFY_API_KEY          = os.getenv("APIFY_API_KEY", "")
GOOGLE_SEARCH_API_KEY  = os.getenv("GOOGLE_SEARCH_API_KEY", "")
SEARCH_ENGINE_ID       = os.getenv("GOOGLE_SEARCH_ENGINE_ID", "")
SERPAPI_API_KEY        = os.getenv("SERPAPI_API_KEY", "")

APIFY_SERP_ACTOR_ID    = "nFJndFXA5zjCTuudP"              # Google Search Scraper
APIFY_MAPS_ACTOR_ID    = "compass~crawler-google-places"   # Google Maps Scraper
APIFY_TIKTOK_ACTOR_ID  = "clockworks~tiktok-scraper"        # TikTok hashtag/post scraper
APIFY_IG_ACTOR_ID      = "apify~instagram-hashtag-scraper"  # Instagram hashtag scraper
APIFY_REDDIT_ACTOR_ID  = "trudax~reddit-scraper-lite"       # Reddit LITE (FREE — fixed 09 Jun 2026; apify/reddit-scraper 404)
APIFY_TRENDS_ACTOR_ID  = "emastra~google-trends-scraper"    # Google Trends (geo must be ISO-2 country code)
APIFY_FBADS_ACTOR_ID   = "apify~facebook-ads-scraper"       # FB Ads Library (tilde format; uses startUrls[])
APIFY_IG_PROFILE_ACTOR_ID = "apify~instagram-profile-scraper"  # Instagram profile + recent posts/reels (public)
APIFY_FB_PAGE_ACTOR_ID    = "apify~facebook-pages-scraper"     # Facebook page + recent posts (public)
APIFY_BASE_URL         = "https://api.apify.com/v2"

# ── Own + competitor handles for organic social pulls (Recommendation B) ──
# Replaces the previous hardcoded load_metricool() block. Public data only:
# follower counts, recent post / reel public engagement. Apify cannot
# access private metrics (story reach, post saves, demographics).
CB247_IG_USERNAME  = "chasingbetter247"
CB247_FB_PAGE_URL  = "https://www.facebook.com/chasingbetter247"

COMPETITOR_IG_USERNAMES = [
    "revofitness",                # Revo Fitness — Perth 24/7 chain (biggest threat)
    "anytimefitnessaustralia",    # Anytime Fitness AU — national chain
    "worldgymau",                 # World Gym Australia
    "muscleuniversemalaga",       # Local Malaga competitor
]

COMPETITOR_FB_PAGE_URLS = [
    "https://www.facebook.com/RevoFitnessAU",
    "https://www.facebook.com/AnytimeFitnessAustralia",
    "https://www.facebook.com/WorldGymAU",
    "https://www.facebook.com/PlusFitnessEllenbrook",
]

# Cost-conscious caps — weekly pull, so small numbers are enough
SOCIAL_PROFILE_POSTS_LIMIT = 12  # recent posts per profile
SOCIAL_PROFILE_REELS_LIMIT = 8   # recent reels per profile

# Fitness hashtags to monitor for trending content ideas (feeds the SEO blog generator)
SOCIAL_HASHTAGS = [
    "gymperth", "pertfitness", "coldplunge",   # 3 tags only — Perth-relevant + viral format
]
SOCIAL_POSTS_PER_TAG = 5   # 5 posts per tag (was 15) — enough signal, minimal cost


# ─────────────────────────────────────────────
# Core Apify helper
# ─────────────────────────────────────────────

def _run_apify_actor(actor_id, payload, timeout_checks=90):
    """
    Generic Apify actor runner.
    Starts the actor, polls until SUCCEEDED/FAILED, returns raw dataset items.
    timeout_checks: max polling iterations (2s sleep each → default 3 min).
    """
    if not APIFY_API_KEY:
        return None

    run_url = f"{APIFY_BASE_URL}/acts/{actor_id}/runs"
    try:
        r = requests.post(
            run_url,
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
    poll_interval = 5  # seconds — less noisy than 2s
    for i in range(timeout_checks):
        try:
            r = requests.get(status_url, params={"token": APIFY_API_KEY}, timeout=10)
            r.raise_for_status()
            status = r.json()["data"].get("status")
            if status == "SUCCEEDED":
                break
            elif status in ("FAILED", "ABORTED", "TIMED_OUT"):
                print(f"  Apify run {status} [{actor_id}]")
                return None
            if i % 6 == 0:  # Print progress every ~30s
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


# ─────────────────────────────────────────────
# Pipeline 1: SERP — organic + local pack
# ─────────────────────────────────────────────

def run_apify_serp(query, max_results=5):   # was 10 — top 5 results enough for rank tracking
    """
    Run Apify Google Search Scraper for a single query.
    Returns dict with 'organic' results and 'local_pack' results.
    local_pack = map pack (3-pack) positions — key for local SEO tracking.
    """
    items = _run_apify_actor(
        APIFY_SERP_ACTOR_ID,
        {
            "queries":        query,
            "countryCode":    "au",
            "languageCode":   "en",
            "resultsPerPage": max_results,
            "mobileResults":  False,
        },
    )
    if not items:
        return None

    organic    = []
    local_pack = []

    for item in items:
        # Organic results
        for result in item.get("organicResults", []):
            organic.append({
                "title":    result.get("title", ""),
                "url":      result.get("url", ""),
                "snippet":  result.get("snippet", ""),
                "position": result.get("position", len(organic) + 1),
            })
            if len(organic) >= max_results:
                break

        # Local pack (3-map-pack) — field name varies by actor version
        for result in (item.get("localResults") or item.get("locals") or []):
            local_pack.append({
                "position":     result.get("position"),
                "title":        result.get("title", ""),
                "rating":       result.get("rating"),
                "reviews":      result.get("reviewsCount") or result.get("reviews"),
                "address":      result.get("address", ""),
                "website":      result.get("website", ""),
                "phone":        result.get("phone", ""),
                "category":     result.get("type") or result.get("category", ""),
            })

    return {
        "organic":    organic    or None,
        "local_pack": local_pack or None,
    }


def search_google(query, num_results=10):
    """Fallback: Google Custom Search API (organic only)."""
    if not GOOGLE_SEARCH_API_KEY or not SEARCH_ENGINE_ID:
        return None
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_SEARCH_API_KEY,
        "cx":  SEARCH_ENGINE_ID,
        "q":   query,
        "num": min(num_results, 10),
        "hl":  "en",
        "gl":  "au",
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        results = []
        for item in r.json().get("items", [])[:num_results]:
            results.append({
                "title":    item.get("title", ""),
                "url":      item.get("link", ""),
                "snippet":  item.get("snippet", ""),
                "position": len(results) + 1,
            })
        return {"organic": results, "local_pack": None}
    except Exception as e:
        print(f"  Google Search error: {e}")
        return None


def search_serpapi(query, num_results=10):
    """Fallback: SerpAPI (organic + local pack if available)."""
    if not SERPAPI_API_KEY:
        return None
    url    = "https://serpapi.com/search"
    params = {
        "q":        query,
        "api_key":  SERPAPI_API_KEY,
        "num":      num_results,
        "gl":       "au",
        "hl":       "en",
        "location": "Perth, Western Australia, Australia",
    }
    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        data    = r.json()
        organic = []
        for item in data.get("organic_results", [])[:num_results]:
            organic.append({
                "title":    item.get("title", ""),
                "url":      item.get("link", ""),
                "snippet":  item.get("snippet", ""),
                "position": item.get("position", len(organic) + 1),
            })

        local_pack = []
        for item in data.get("local_results", {}).get("places", []):
            local_pack.append({
                "position": item.get("position"),
                "title":    item.get("title", ""),
                "rating":   item.get("rating"),
                "reviews":  item.get("reviews"),
                "address":  item.get("address", ""),
                "website":  item.get("links", {}).get("website", ""),
                "phone":    item.get("phone", ""),
            })

        return {
            "organic":    organic    or None,
            "local_pack": local_pack or None,
        }
    except Exception as e:
        print(f"  SerpAPI error: {e}")
        return None


def run_serp_analysis():
    """Run SERP analysis for CB247 + competitor keywords. Returns organic + local pack per query."""
    # CREDIT CONTROL: 5 keywords only — highest conversion intent + top competitor
    # Full list previously was 14 keywords. Reduced to save Apify pay-per-event credits.
    keywords = [
        "gym malaga perth",           # highest-volume local target
        "gym ellenbrook perth",        # second location
        "reformer pilates perth",      # premium service differentiator
        "revo fitness malaga",         # top competitor — must monitor
        "fifo gym membership perth",   # unique CB247 angle
    ]

    results = []
    for kw in keywords:
        print(f"  SERP: {kw}")
        data = (
            run_apify_serp(kw)
            or search_google(kw)
            or search_serpapi(kw)
        )
        if data:
            entry = {"keyword": kw, **data}
            # Flag if CB247 is in local pack for this keyword
            entry["cb247_in_local_pack"] = _check_cb247_in_local_pack(
                data.get("local_pack") or []
            )
        else:
            entry = {"keyword": kw, "organic": [], "local_pack": [], "note": "No data"}
        results.append(entry)
        time.sleep(2)  # Rate limit

    return results


def _check_cb247_in_local_pack(local_pack):
    """Returns position (1/2/3) if CB247 appears in the local pack, else None."""
    cb247_signals = ["chasingbetter", "chasing better", "cb247"]
    for result in local_pack or []:
        title   = (result.get("title") or "").lower()
        website = (result.get("website") or "").lower()
        if any(s in title or s in website for s in cb247_signals):
            return result.get("position")
    return None


# ─────────────────────────────────────────────
# Pipeline 2: Google Maps competitor benchmarking
# ─────────────────────────────────────────────

# Locations to benchmark: CB247 + direct competitors
# CREDIT CONTROL: 4 listings only (was 7). CB247 both locations + top 2 competitors.
MAPS_TARGETS = [
    # CB247 own listings — always needed
    {"query": "ChasingBetter247 Malaga",       "type": "cb247",      "location": "Malaga"},
    {"query": "ChasingBetter247 Ellenbrook WA","type": "cb247",      "location": "Ellenbrook"},
    # Top competitor only — Revo is the #1 threat
    {"query": "Revo Fitness Malaga WA",        "type": "competitor", "location": "Malaga"},
    {"query": "Revo Fitness Ellenbrook WA",    "type": "competitor", "location": "Ellenbrook"},
]


def _scrape_single_listing(target):
    """
    Scrape one Maps listing. Returns the matched place dict or None.
    Runs one actor call per listing to avoid batch timeouts.
    """
    items = _run_apify_actor(
        APIFY_MAPS_ACTOR_ID,
        {
            "searchStringsArray":        [target["query"]],
            "maxCrawledPlacesPerSearch": 1,   # Only top result needed
            "language":                  "en",
            "countryCode":               "au",
            "includeHistogram":          False,
            "includeOpeningHours":       True,
            "maxImages":                 0,
            "maxReviews":                0,
            "scrapeReviewsPersonalData": False,
        },
        timeout_checks=60,  # 5 min per listing — should be plenty for 1 result
    )
    if not items:
        return None
    # Show returned titles so we can tune the matcher if needed
    for item in items:
        print(f"     [debug] returned: '{item.get('title','')}' @ {item.get('address','')}")
    # Take top result directly (we asked for maxCrawledPlacesPerSearch=1)
    if items:
        return items[0]
    return None


def pull_competitor_maps():
    """
    Scrape Google Maps listings for CB247 + competitors one at a time.
    Returns structured data per location: rating, review count, photo count,
    listing completeness score, and key GBP attributes.
    """
    if not APIFY_API_KEY:
        print("  APIFY_API_KEY not set — skipping Maps competitor scrape.")
        return None

    results = []
    for target in MAPS_TARGETS:
        print(f"  → {target['query']}")
        match = _scrape_single_listing(target)
        if match:
            results.append({
                "query":              target["query"],
                "type":               target["type"],
                "location":           target["location"],
                "title":              match.get("title", ""),
                "rating":             match.get("totalScore"),
                "reviews":            match.get("reviewsCount"),
                "photos":             match.get("imagesCount"),
                "address":            match.get("address", ""),
                "website":            match.get("website", ""),
                "phone":              match.get("phone", ""),
                "category":           match.get("categoryName", ""),
                "hours_set":          bool(match.get("openingHours")),
                "permanently_closed": match.get("permanentlyClosed", False),
                "completeness_score": _listing_completeness(match),
            })
            print(f"     ✅ {match.get('title','')} — ⭐{match.get('totalScore')} ({match.get('reviewsCount',0)} reviews)")
        else:
            results.append({
                "query":    target["query"],
                "type":     target["type"],
                "location": target["location"],
                "note":     "No match found",
            })
            print(f"     ⚠️  No match found")
        time.sleep(3)  # Brief pause between actor runs

    if not any("rating" in r for r in results):
        print("  Maps scrape returned no usable data.")
        return None

    summary = _maps_competitive_summary(results)
    return {
        "targets": results,
        "summary": summary,
    }


def _find_best_maps_match(items, query):
    """Find the best-matching place from Maps results for a given search query."""
    query_lower  = query.lower()
    query_tokens = set(query_lower.replace(" wa", "").split())

    best       = None
    best_score = 0
    for item in items:
        title = (item.get("title") or "").lower()
        token_overlap = len(set(title.split()) & query_tokens)
        if token_overlap > best_score:
            best_score = token_overlap
            best       = item

    return best if best_score >= 2 else None


def _listing_completeness(place):
    """
    Score GBP listing completeness 0–100.
    Checks: name, address, phone, website, category, hours, photos, reviews.
    """
    checks = {
        "name":     bool(place.get("title")),
        "address":  bool(place.get("address")),
        "phone":    bool(place.get("phone")),
        "website":  bool(place.get("website")),
        "category": bool(place.get("categoryName")),
        "hours":    bool(place.get("openingHours")),
        "photos":   (place.get("imagesCount") or 0) >= 5,
        "reviews":  (place.get("reviewsCount") or 0) >= 10,
    }
    score = int(sum(checks.values()) / len(checks) * 100)
    return score


def _maps_competitive_summary(results):
    """Build a head-to-head summary: CB247 vs competitors."""
    cb247     = [r for r in results if r.get("type") == "cb247" and "rating" in r]
    comp      = [r for r in results if r.get("type") == "competitor" and "rating" in r]

    def avg(lst, key):
        vals = [x[key] for x in lst if x.get(key) is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    return {
        "cb247": {
            "avg_rating":    avg(cb247, "rating"),
            "total_reviews": sum(r.get("reviews") or 0 for r in cb247),
            "avg_photos":    avg(cb247, "photos"),
            "avg_completeness": avg(cb247, "completeness_score"),
        },
        "competitors": {
            "avg_rating":    avg(comp, "rating"),
            "total_reviews": sum(r.get("reviews") or 0 for r in comp),
            "avg_photos":    avg(comp, "photos"),
            "avg_completeness": avg(comp, "completeness_score"),
        },
    }


# ─────────────────────────────────────────────
# Pipeline 3: Social trend scraping (TikTok + Instagram) → blog content ideas
# ─────────────────────────────────────────────

def _normalise_social_post(item, platform):
    """Normalise a TikTok/Instagram item into a common shape with an engagement score."""
    if platform == "tiktok":
        text = item.get("text") or ""
        likes = item.get("diggCount") or 0
        comments = item.get("commentCount") or 0
        shares = item.get("shareCount") or 0
        plays = item.get("playCount") or 0
        url = item.get("webVideoUrl") or item.get("url") or ""
        tags = [h.get("name") for h in (item.get("hashtags") or []) if isinstance(h, dict) and h.get("name")]
    else:  # instagram
        text = item.get("caption") or ""
        likes = item.get("likesCount") or 0
        comments = item.get("commentsCount") or 0
        shares = 0
        plays = item.get("videoViewCount") or 0
        url = item.get("url") or ""
        tags = item.get("hashtags") or []
    # Weighted engagement: comments + shares signal "talked about", not just passive likes
    engagement = likes + comments * 3 + shares * 5 + int(plays * 0.01)
    return {
        "platform": platform,
        "text": (text or "").strip()[:300],
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "plays": plays,
        "engagement": engagement,
        "hashtags": [t.lower() for t in tags if t],
        "url": url,
    }


def _scrape_tiktok(hashtags, per_tag):
    items = _run_apify_actor(
        APIFY_TIKTOK_ACTOR_ID,
        {
            "hashtags": hashtags,
            "resultsPerPage": per_tag,
            "shouldDownloadVideos": False,
            "shouldDownloadCovers": False,
            "proxyCountryCode": "AU",
        },
        timeout_checks=72,
    )
    if not items:
        return []
    return [_normalise_social_post(i, "tiktok") for i in items if isinstance(i, dict)]


def _scrape_instagram(hashtags, per_tag):
    items = _run_apify_actor(
        APIFY_IG_ACTOR_ID,
        {
            "hashtags": hashtags,
            "resultsLimit": per_tag,
        },
        timeout_checks=72,
    )
    if not items:
        return []
    return [_normalise_social_post(i, "instagram") for i in items if isinstance(i, dict)]


def _extract_trending_hashtags(posts, top_n=20):
    """Count hashtag frequency across collected posts."""
    from collections import Counter
    c = Counter()
    for p in posts:
        for tag in set(p.get("hashtags", [])):
            c[tag] += 1
    return [{"hashtag": t, "count": n} for t, n in c.most_common(top_n)]


def pull_social_trends():
    """
    Scrape trending fitness content from TikTok + Instagram for blog content ideas.
    Returns top posts by engagement + most-used hashtags. Degrades gracefully
    if an actor is unavailable on the account.
    """
    if not APIFY_API_KEY:
        print("  APIFY_API_KEY not set — skipping social trends.")
        return None

    print(f"  → Scraping {len(SOCIAL_HASHTAGS)} hashtags: {', '.join('#'+h for h in SOCIAL_HASHTAGS)}")
    all_posts = []

    print("  → TikTok...")
    try:
        all_posts += _scrape_tiktok(SOCIAL_HASHTAGS, SOCIAL_POSTS_PER_TAG)
    except Exception as e:
        print(f"     TikTok scrape failed: {e}")

    print("  → Instagram...")
    try:
        all_posts += _scrape_instagram(SOCIAL_HASHTAGS, SOCIAL_POSTS_PER_TAG)
    except Exception as e:
        print(f"     Instagram scrape failed: {e}")

    if not all_posts:
        print("  No social posts returned (check actor access on your Apify plan).")
        return None

    all_posts.sort(key=lambda p: p["engagement"], reverse=True)
    top_posts = all_posts[:25]

    return {
        "scraped": datetime.now().isoformat(),
        "hashtags_monitored": SOCIAL_HASHTAGS,
        "posts_collected": len(all_posts),
        "trending_hashtags": _extract_trending_hashtags(all_posts),
        "top_posts": top_posts,
    }


# ─────────────────────────────────────────────
# Pipeline 4: Reddit Intel — r/Perth + r/fitness
# ─────────────────────────────────────────────

# CREDIT CONTROL: 3 searches only (was 6). Highest-signal subreddits for CB247.
REDDIT_SEARCHES = [
    {"subreddit": "perth",   "query": "gym",          "label": "perth_gym"},
    {"subreddit": "perth",   "query": "cheap gym",    "label": "perth_cheap_gym"},
    {"subreddit": "FIFO",    "query": "gym fitness",  "label": "fifo_gym"},
]


def pull_reddit_intel():
    """
    Scrape Reddit posts and comments from r/Perth and r/fitness for:
    - Gym complaints / questions (audience pain points)
    - Language people use to describe gyms (for copy/SEO)
    - Mentions of CB247 / Revo / Anytime / competitors
    - Trending fitness topics in Perth
    """
    if not APIFY_API_KEY:
        print("  APIFY_API_KEY not set — skipping Reddit scrape.")
        return None

    all_posts = []
    for search in REDDIT_SEARCHES:
        print(f"  → Reddit r/{search['subreddit']}: '{search['query']}'")
        # trudax~reddit-scraper-lite (FREE) — same startUrls input shape as
        # the old apify/reddit-scraper, but does not accept maxComments or
        # proxy fields. Verified working 09 Jun 2026 via MWCC smoke test.
        items = _run_apify_actor(
            APIFY_REDDIT_ACTOR_ID,
            {
                "startUrls": [
                    {
                        "url": f"https://www.reddit.com/r/{search['subreddit']}/search/?q={search['query'].replace(' ', '+')}&restrict_sr=1&sort=hot",
                        "method": "GET",
                    }
                ],
                "maxItems":     10,   # 10 posts per search
                "skipComments": False,
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
        print("  Reddit scrape returned no posts.")
        return None

    # Extract competitor mentions and pain points
    competitor_mentions = _extract_competitor_mentions(all_posts)
    pain_points         = _extract_pain_points(all_posts)
    key_phrases         = _extract_key_phrases(all_posts)

    all_posts.sort(key=lambda p: p.get("score", 0), reverse=True)

    return {
        "scraped":              datetime.now().isoformat(),
        "posts_collected":      len(all_posts),
        "top_posts":            all_posts[:20],
        "competitor_mentions":  competitor_mentions,
        "pain_points":          pain_points,
        "key_phrases":          key_phrases,
    }


def _normalise_reddit_post(item, search):
    """Normalise a Reddit post into common shape."""
    title = item.get("title") or ""
    body  = item.get("body") or item.get("selftext") or ""
    # Pull top comments
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


def _extract_competitor_mentions(posts):
    """Count mentions of CB247, Revo, Anytime, etc. across all posts + comments."""
    brands = {
        "cb247":         ["chasingbetter", "cb247", "chasing better"],
        "revo":          ["revo fitness", "revo gym", "revofitness"],
        "anytime":       ["anytime fitness"],
        "snap":          ["snap fitness"],
        "ryderwear":     ["ryderwear"],
        "goodlife":      ["goodlife", "good life gym"],
    }
    counts = {brand: 0 for brand in brands}
    for post in posts:
        text = post.get("full_text", "") + " " + " ".join(post.get("comments", []))
        text = text.lower()
        for brand, signals in brands.items():
            if any(s in text for s in signals):
                counts[brand] += 1
    return sorted(
        [{"brand": b, "mentions": c} for b, c in counts.items() if c > 0],
        key=lambda x: x["mentions"], reverse=True
    )


def _extract_pain_points(posts):
    """
    Identify gym pain points from Reddit posts based on signal words.
    These are the objections CB247 content should address.
    """
    pain_signals = {
        "price":       ["expensive", "cheap", "cost", "price", "afford", "worth"],
        "contract":    ["lock-in", "contract", "cancel", "cancellation"],
        "hours":       ["24/7", "hours", "closing", "open late", "early"],
        "kids":        ["kids", "children", "childcare", "family"],
        "crowd":       ["crowded", "busy", "peak hour", "wait"],
        "equipment":   ["equipment", "machines", "weights", "broken"],
        "parking":     ["parking", "park"],
        "cleanliness": ["clean", "dirty", "hygiene", "smell"],
    }
    pain_counts = {k: 0 for k in pain_signals}
    pain_examples = {k: [] for k in pain_signals}

    for post in posts:
        text = post.get("full_text", "") + " " + " ".join(post.get("comments", []))
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


def _extract_key_phrases(posts):
    """Extract the most common phrases people use when talking about gyms."""
    from collections import Counter
    words = Counter()
    stop = {"the","a","an","is","in","it","to","of","and","or","for","my","i","you",
            "at","on","with","this","that","was","be","are","they","we","has","have",
            "not","but","if","so","just","like","as","do","gym","perth","fitness"}
    for post in posts:
        text = (post.get("full_text", "") + " " + " ".join(post.get("comments", []))).lower()
        for word in text.split():
            word = word.strip(".,?!()\"'")
            if word and len(word) > 3 and word not in stop:
                words[word] += 1
    return [{"phrase": w, "count": c} for w, c in words.most_common(30)]


# ─────────────────────────────────────────────
# Pipeline 5: Google Trends Perth
# ─────────────────────────────────────────────

TRENDS_KEYWORDS = [
    "gym membership",
    "personal trainer perth",
    "reformer pilates",
    "cold plunge",
    "ice bath",
    "sauna",
    "FIFO fitness",
    "cheap gym",
    "24 hour gym",
    "weight loss perth",
]


def pull_google_trends():
    """
    Pull Google Trends data for fitness keywords in Perth/WA.
    Identifies which topics are rising vs declining — informs content calendar.
    """
    if not APIFY_API_KEY:
        print("  APIFY_API_KEY not set — skipping Google Trends.")
        return None

    # Fixed 09 Jun 2026 (via MWCC schema discovery):
    # - geo: ONLY ISO-2 country codes ("AU"), NOT subregions ("AU-WA" rejected 400)
    # - 'category' int triggered validation error — removed
    # - actor returns 'interestBySubregion' as a free bonus — WA-specific
    #   interest can be filtered post-hoc from there
    # - Actor takes ~45s per keyword (bumped timeout to 20 min ceiling)
    print(f"  → Google Trends: {len(TRENDS_KEYWORDS)} keywords, geo=AU (WA bonus via interestBySubregion)")
    items = _run_apify_actor(
        APIFY_TRENDS_ACTOR_ID,
        {
            "searchTerms": TRENDS_KEYWORDS,
            "geo":         "AU",
            "timeRange":   "today 3-m",
            "isMultiple":  False,
        },
        timeout_checks=240,
    )

    if not items:
        print("  Google Trends returned no data.")
        return None

    # Actor field names (verified 09 Jun 2026 — actor returns flattened schema):
    #   searchTerm / inputUrlOrTerm     (instead of 'keyword')
    #   interestOverTime_timelineData   (instead of 'interestOverTime')
    #   interestBySubregion             (bonus — for WA-specific signal)
    #   relatedTopics_top               (instead of 'relatedTopics')
    trends = []
    for item in items:
        keyword = item.get("searchTerm") or item.get("inputUrlOrTerm") or item.get("keyword") or ""
        timeline = item.get("interestOverTime_timelineData") or item.get("interestOverTime") or []

        def _val(point):
            v = point.get("value")
            if isinstance(v, list) and v:
                return v[0]
            return v

        current_value = _val(timeline[-1]) if timeline else None
        prev_value    = _val(timeline[-4]) if len(timeline) >= 4 else None

        trend_dir = "stable"
        if current_value and prev_value:
            if current_value > prev_value * 1.15:
                trend_dir = "rising"
            elif current_value < prev_value * 0.85:
                trend_dir = "declining"

        # Pull WA-specific interest from the subregion data (bonus signal)
        wa_interest = None
        for sr in (item.get("interestBySubregion") or []):
            if "western australia" in (sr.get("geoName", "") or "").lower():
                wa_interest = _val(sr)
                break

        trends.append({
            "keyword":       keyword,
            "current_value": current_value,   # 0-100 relative interest (national)
            "prev_value":    prev_value,
            "direction":     trend_dir,
            "wa_interest":   wa_interest,     # bonus WA signal (CB247 Perth focus)
            "interest_data": timeline[-12:],
            "related":       item.get("relatedTopics_top") or item.get("relatedTopics") or [],
        })

    # Sort by current interest descending
    trends.sort(key=lambda t: t.get("current_value") or 0, reverse=True)

    rising   = [t for t in trends if t["direction"] == "rising"]
    declining = [t for t in trends if t["direction"] == "declining"]

    return {
        "scraped":         datetime.now().isoformat(),
        "geo":             "AU-WA (Perth)",
        "keywords_tracked": len(trends),
        "trends":          trends,
        "rising_topics":   rising,
        "declining_topics": declining,
        "content_signal":  _trends_content_signal(rising),
    }


def _trends_content_signal(rising_trends):
    """Convert rising trends into actionable content signals."""
    signals = []
    for t in rising_trends[:5]:
        signals.append({
            "topic":   t["keyword"],
            "signal":  f"Interest rising in Perth — publish content now to catch the wave",
            "urgency": "high" if (t.get("current_value") or 0) > 60 else "medium",
        })
    return signals


# ─────────────────────────────────────────────
# Pipeline 6: Facebook Ads Library — competitor creatives
# ─────────────────────────────────────────────

# apify~facebook-ads-scraper requires page_url (FB page direct URL), not
# a search keyword. Discovered via inputSchema 09 Jun 2026.
FB_ADS_COMPETITORS = [
    {"name": "Revo Fitness",    "page_url": "https://www.facebook.com/RevoFitnessAU"},
    {"name": "Anytime Fitness", "page_url": "https://www.facebook.com/AnytimeFitnessAustralia"},
    {"name": "Snap Fitness",    "page_url": "https://www.facebook.com/SnapFitnessAU"},
]


def pull_facebook_ads():
    """
    Scrape the Facebook Ads Library for active ads run by:
    - Revo Fitness, Anytime Fitness, Snap Fitness

    Returns: ad copy, creative type, CTA, start date, impressions estimate.
    Used by: Content Intel + Paid Ads agents to understand competitor messaging.
    """
    if not APIFY_API_KEY:
        print("  APIFY_API_KEY not set — skipping Facebook Ads Library.")
        return None

    # Fixed 09 Jun 2026 (via MWCC schema discovery):
    # - required startUrls[] pointing to each competitor's FB PAGE (not
    #   ads library search URL)
    # - drop activeStatus filter (returned no_items wrappers when set)
    # - resultsLimit replaces maxItems
    # - Single batched call across all competitors (cheaper than per-page)
    print(f"  → FB Ads: {len(FB_ADS_COMPETITORS)} competitors")
    items = _run_apify_actor(
        APIFY_FBADS_ACTOR_ID,
        {
            "startUrls":    [{"url": c["page_url"]} for c in FB_ADS_COMPETITORS],
            "resultsLimit": 20,
        },
        timeout_checks=120,
    )

    all_ads = []
    if items:
        # Tag each ad with the competitor by inputUrl match
        url_to_name = {c["page_url"].lower(): c["name"] for c in FB_ADS_COMPETITORS}
        for item in items:
            # Skip wrapper items for pages with no public ads
            if item.get("error") == "no_items":
                continue
            input_url = (item.get("inputUrl") or "").lower()
            competitor_name = next(
                (name for url, name in url_to_name.items() if url in input_url or input_url in url),
                "Unknown",
            )
            ad = _normalise_fb_ad(item, competitor_name)
            if ad:
                all_ads.append(ad)

    if not all_ads:
        print("  FB Ads Library returned no results.")
        return None

    # Analyse what competitors are saying
    analysis = _analyse_competitor_ads(all_ads)

    return {
        "scraped":            datetime.now().isoformat(),
        "competitors_checked": [c["name"] for c in FB_ADS_COMPETITORS],
        "ads_found":          len(all_ads),
        "ads":                all_ads,
        "analysis":           analysis,
    }


def _normalise_fb_ad(item, competitor_name):
    """Normalise a Facebook Ads Library item.

    apify~facebook-ads-scraper return shape verified 09 Jun 2026:
      pageInfo (dict), pageID, adArchiveID, startDateFormatted,
      endDateFormatted, collationCount, ad_creative_body, etc.
    """
    page_info = item.get("pageInfo") or {}

    body = item.get("ad_creative_bodies", [])
    body_text = body[0] if body else (item.get("ad_creative_body") or "")

    title = item.get("ad_creative_link_titles", [])
    title_text = title[0] if title else (item.get("ad_creative_link_title") or "")

    cta = item.get("ad_creative_link_captions", [])
    cta_text = cta[0] if cta else (item.get("cta_text") or "")

    return {
        "competitor":      competitor_name,
        "page_name":       page_info.get("name") or "",
        "ad_id":           item.get("adArchiveID") or item.get("adArchiveId") or item.get("ad_archive_id") or "",
        "headline":        title_text[:200],
        "body":            body_text[:500],
        "cta":             cta_text,
        "format":          item.get("ad_creative_media_type") or item.get("media_type") or "unknown",
        "started":         item.get("startDateFormatted") or item.get("ad_delivery_start_time") or "",
        "ended":           item.get("endDateFormatted") or "",
        "collation_count": item.get("collationCount"),   # how many variants
        "impressions_min": (item.get("impressions") or {}).get("lower_bound"),
        "impressions_max": (item.get("impressions") or {}).get("upper_bound"),
        "is_active":       item.get("is_active", True),
        "url":             item.get("snapshot_url") or item.get("url") or "",
    }


def _analyse_competitor_ads(ads):
    """Extract patterns from competitor ads: angles, CTAs, offers."""
    from collections import Counter

    cta_counter    = Counter()
    format_counter = Counter()
    themes         = []

    offer_signals = ["free", "no lock", "join now", "first week", "trial",
                     "discount", "$", "week", "month", "limited", "offer"]
    theme_signals = {
        "price":     ["$", "week", "per week", "cheap", "affordable"],
        "community": ["family", "community", "together", "members"],
        "facilities": ["sauna", "pool", "pilates", "classes", "equipment"],
        "no_contract": ["no lock", "no contract", "cancel", "flexible"],
        "results":   ["transform", "lose weight", "gain muscle", "results", "stronger"],
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
        "top_ctas":         [{"cta": k, "count": v} for k, v in cta_counter.most_common(5)],
        "ad_formats":       [{"format": k, "count": v} for k, v in format_counter.most_common()],
        "messaging_themes": [{"theme": k, "count": v} for k, v in theme_counts.most_common()],
        "gaps_for_cb247":   _find_ad_gaps(theme_counts),
    }


def _find_ad_gaps(theme_counts):
    """
    Identify what CB247 SHOULD advertise that competitors are NOT saying much about.
    """
    gaps = []
    cb247_unique = {
        "kids_hub":  "Kids Hub — free childcare while you train",
        "sauna_ice": "Sauna + Ice Bath combo — recovery lifestyle",
        "fifo":      "FIFO-friendly freeze — pause anytime",
        "neon21":    "Neon21 — premium tanning",
        "reformer":  "Reformer Pilates 24/7",
    }
    theme_map = {
        "kids_hub":  "community",
        "sauna_ice": "facilities",
        "fifo":      "no_contract",
    }
    for feature, message in cb247_unique.items():
        mapped_theme = theme_map.get(feature, "")
        if theme_counts.get(mapped_theme, 0) < 2:
            gaps.append({
                "cb247_advantage": feature,
                "message":         message,
                "competitor_coverage": "low",
            })
    return gaps


# ─────────────────────────────────────────────
# Pipeline 7: Instagram Profile Scraping (own + competitors)
# Replaces Metricool — public follower count + recent posts/reels engagement
# ─────────────────────────────────────────────

def pull_instagram_profiles():
    """Pull CB247 + competitor Instagram public profiles via Apify.

    Returns dict with:
      cb247: { handle, followers, follows, posts_count, latest_posts:[...] }
      competitors: [ {...}, ... ]

    Apify cannot access: story metrics, post reach (vs impressions), post saves,
    follower demographics. Those Metricool fields will be permanently unavailable.
    """
    if not APIFY_API_KEY:
        print("  Instagram profiles skipped — no APIFY_API_KEY")
        return None

    usernames = [CB247_IG_USERNAME] + COMPETITOR_IG_USERNAMES
    payload = {
        "usernames":       usernames,
        "resultsType":     "details",          # full profile + latest posts
        "resultsLimit":    SOCIAL_PROFILE_POSTS_LIMIT,
        "addParentData":   False,
        # Some profile-scraper variants want "directUrls" with full URLs
        "directUrls":      [f"https://www.instagram.com/{u}/" for u in usernames],
    }

    print(f"  Instagram profiles: scraping {len(usernames)} accounts...")
    items = _run_apify_actor(APIFY_IG_PROFILE_ACTOR_ID, payload, timeout_checks=60)
    if not items:
        print("  Instagram profiles: actor returned no data")
        return None

    profiles_by_user = {}
    for item in items:
        username = (item.get("username") or item.get("ownerUsername") or "").lower()
        if not username:
            continue

        # The Apify IG profile scraper returns posts as either `latestPosts`
        # or via a separate dataset. Normalise here.
        latest_posts_raw = item.get("latestPosts") or item.get("posts") or []
        latest_posts = []
        for p in latest_posts_raw[:SOCIAL_PROFILE_POSTS_LIMIT]:
            ptype = (p.get("type") or "").lower()
            latest_posts.append({
                "url":         p.get("url") or p.get("postUrl") or "",
                "type":        ptype,           # "image" / "video" / "sidecar"
                "is_reel":     ptype == "video" or "reel" in (p.get("url") or "").lower(),
                "timestamp":   p.get("timestamp") or p.get("takenAt") or "",
                "caption":     (p.get("caption") or "")[:200],
                "likes":       p.get("likesCount") or p.get("likes") or 0,
                "comments":    p.get("commentsCount") or p.get("comments") or 0,
                "views":       p.get("videoViewCount") or p.get("videoPlayCount") or 0,
                "hashtags":    p.get("hashtags") or [],
            })

        profile = {
            "handle":           username,
            "full_name":        item.get("fullName") or "",
            "followers":        item.get("followersCount") or 0,
            "follows":          item.get("followsCount") or 0,
            "posts_count":      item.get("postsCount") or 0,
            "biography":        (item.get("biography") or "")[:240],
            "verified":         item.get("verified") or False,
            "is_business":      item.get("isBusinessAccount") or False,
            "category":         item.get("businessCategoryName") or item.get("categoryName") or "",
            "external_url":     item.get("externalUrl") or item.get("externalUrls") or "",
            "latest_posts":     latest_posts,
            "scraped_at":       datetime.now().isoformat(),
        }
        profiles_by_user[username] = profile

    if not profiles_by_user:
        return None

    own = profiles_by_user.get(CB247_IG_USERNAME.lower())
    competitors = [profiles_by_user[u.lower()] for u in COMPETITOR_IG_USERNAMES
                   if u.lower() in profiles_by_user]

    print(f"  Instagram profiles: pulled {len(profiles_by_user)} accounts "
          f"({'CB247 ok' if own else 'CB247 MISSING'} · {len(competitors)} competitors)")

    return {
        "scraped_at":  datetime.now().isoformat(),
        "cb247":       own,
        "competitors": competitors,
        "note":        "Public data only. Stories/reach/saves/demographics not available — Metricool replacement is partial.",
    }


# ─────────────────────────────────────────────
# Pipeline 8: Facebook Page Scraping (own + competitors)
# ─────────────────────────────────────────────

def pull_facebook_pages():
    """Pull CB247 + competitor Facebook public pages via Apify.

    Returns dict with cb247 + competitors. Public data only — no page insights,
    no post reach, no engagement breakdown beyond likes/comments/shares.
    """
    if not APIFY_API_KEY:
        print("  Facebook pages skipped — no APIFY_API_KEY")
        return None

    start_urls = [CB247_FB_PAGE_URL] + COMPETITOR_FB_PAGE_URLS
    payload = {
        "startUrls":      [{"url": u} for u in start_urls],
        "resultsLimit":   SOCIAL_PROFILE_POSTS_LIMIT,
        "scrapePosts":    True,
    }

    print(f"  Facebook pages: scraping {len(start_urls)} pages...")
    items = _run_apify_actor(APIFY_FB_PAGE_ACTOR_ID, payload, timeout_checks=60)
    if not items:
        print("  Facebook pages: actor returned no data")
        return None

    # Group by URL — the FB scraper returns one item per page (with posts nested)
    # plus sometimes separate post items.
    pages_by_url = {}
    for item in items:
        page_url = (item.get("pageUrl") or item.get("url") or "").rstrip("/")
        if not page_url:
            continue
        # Normalise the URL for matching (strip protocol + trailing slash)
        norm_url = page_url.lower().rstrip("/")
        if "facebook.com" not in norm_url:
            continue

        # Posts may be on this item or aggregated separately. Take what's on item.
        posts_raw = item.get("posts") or item.get("latestPosts") or []
        posts = []
        for p in posts_raw[:SOCIAL_PROFILE_POSTS_LIMIT]:
            posts.append({
                "url":       p.get("url") or "",
                "timestamp": p.get("timestamp") or p.get("publishedAt") or "",
                "text":      (p.get("text") or p.get("message") or "")[:300],
                "likes":     p.get("likes") or p.get("reactionsCount") or 0,
                "comments":  p.get("comments") or p.get("commentsCount") or 0,
                "shares":    p.get("shares")   or p.get("sharesCount")   or 0,
                "media_type": p.get("mediaType") or "",
            })

        page = {
            "url":            page_url,
            "name":           item.get("title") or item.get("pageName") or "",
            "followers":      item.get("followers") or item.get("followersCount") or 0,
            "likes":          item.get("likes") or item.get("likesCount") or 0,
            "about":          (item.get("about") or item.get("description") or "")[:240],
            "categories":     item.get("categories") or [],
            "posts":          posts,
            "scraped_at":     datetime.now().isoformat(),
        }
        pages_by_url[norm_url] = page

    if not pages_by_url:
        return None

    # Match CB247 + each competitor by case-insensitive URL contains
    def _find(target_url):
        target = target_url.lower().rstrip("/")
        for k, v in pages_by_url.items():
            if target in k or k in target:
                return v
        return None

    own = _find(CB247_FB_PAGE_URL)
    competitors = []
    for url in COMPETITOR_FB_PAGE_URLS:
        match = _find(url)
        if match:
            competitors.append(match)

    print(f"  Facebook pages: pulled {len(pages_by_url)} pages "
          f"({'CB247 ok' if own else 'CB247 MISSING'} · {len(competitors)} competitors)")

    return {
        "scraped_at":  datetime.now().isoformat(),
        "cb247":       own,
        "competitors": competitors,
        "note":        "Public data only. Page insights (reach, post-by-post impressions) require Page admin API.",
    }


# ─────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────

def load_json(path):
    if path.exists():
        return json.loads(path.read_text())
    return {}


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    # ── Monday-only guard — Apify is pay-per-event, never run on routine refreshes ──
    import sys as _sys
    _force = "--force" in _sys.argv
    _today_dow = datetime.now().weekday()   # 0=Monday
    if _today_dow != 0 and not _force:
        print("⏭  Apify skipped — only runs on Mondays (weekly pipeline).")
        print("   To run manually: python3 scripts/pull_apify.py --force")
        return None

    print("Pulling SERP + Maps + Social + Reddit via Apify (Monday weekly run)...\n")

    # ── Pipeline 1: SERP (organic + local pack) ──
    print("--- Pipeline 1: SERP Analysis ---")
    serp = run_serp_analysis()

    # ── Pipeline 2: Maps competitor benchmarking ──
    print("\n--- Pipeline 2: Google Maps Competitor Benchmarking ---")
    maps = pull_competitor_maps()

    # ── Keyword tracking from GSC ──
    gsc      = load_json(STATE_DIR / "gsc-data.json")
    gsc_q    = {q.get("query", "").lower(): q for q in (gsc.get("top_queries", []) or [])}
    target_kw = [
        "gym malaga", "24/7 gym malaga", "gym ellenbrook", "24/7 gym ellenbrook",
        "sauna malaga", "ice bath malaga", "kids gym malaga", "reformer pilates perth",
    ]
    keyword_tracking = []
    for kw in target_kw:
        q = gsc_q.get(kw.lower())
        keyword_tracking.append({
            "keyword":     kw,
            "position":    q.get("position")    if q else None,
            "clicks":      q.get("clicks")      if q else 0,
            "impressions": q.get("impressions") if q else 0,
            "ctr":         q.get("ctr")         if q else 0,
        })

    # ── Pipeline 3: Social trend scraping (TikTok + Instagram) ──
    print("\n--- Pipeline 3: Social Trends (TikTok + Instagram) ---")
    social = pull_social_trends()
    if social:
        (STATE_DIR / "social-trends.json").write_text(json.dumps(social, indent=2))

    # ── Pipeline 4: Reddit Intel ──
    print("\n--- Pipeline 4: Reddit Intel (r/Perth + r/fitness) ---")
    reddit = pull_reddit_intel()
    if reddit:
        (STATE_DIR / "reddit-intel.json").write_text(json.dumps(reddit, indent=2))

    # ── Pipeline 5: Google Trends ──
    print("\n--- Pipeline 5: Google Trends Perth/WA ---")
    trends = pull_google_trends()
    if trends:
        (STATE_DIR / "google-trends.json").write_text(json.dumps(trends, indent=2))

    # ── Pipeline 6: Facebook Ads Library ──
    print("\n--- Pipeline 6: Facebook Ads Library (Competitors) ---")
    fb_ads = pull_facebook_ads()
    if fb_ads:
        (STATE_DIR / "fb-ads-intel.json").write_text(json.dumps(fb_ads, indent=2))

    # ── Pipeline 7: Instagram Profiles (CB247 + competitors — Metricool replacement) ──
    print("\n--- Pipeline 7: Instagram Profiles (CB247 + 4 competitors) ---")
    ig_profiles = pull_instagram_profiles()

    # ── Pipeline 8: Facebook Pages (CB247 + competitors — Metricool replacement) ──
    print("\n--- Pipeline 8: Facebook Pages (CB247 + 4 competitors) ---")
    fb_pages = pull_facebook_pages()

    # ── Local pack summary ──
    local_pack_summary = _summarise_local_pack(serp)

    # ── Preserve previously-good data when actors fail (402/404) ──────
    # If a field comes back None this run, keep the last known-good value
    # rather than overwriting with null. This protects against cron runs
    # where the subscription lapses or an actor is temporarily unavailable.
    existing = {}
    out_path = STATE_DIR / "apify-data.json"
    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text())
        except Exception:
            existing = {}

    def keep_if_none(new_val, key):
        """Return new_val if it has content, else fall back to existing."""
        if new_val is not None:
            return new_val
        old = existing.get(key)
        if old is not None:
            print(f"  [preserve] {key}: actor returned None — keeping last known-good data")
        return old

    result = {
        "date_pulled":         datetime.now().isoformat(),
        "competitor_serp":     serp if serp else existing.get("competitor_serp", []),
        "keyword_tracking":    keyword_tracking,
        "local_pack_summary":  local_pack_summary if local_pack_summary.get("pack_presence_rate") is not None
                               else existing.get("local_pack_summary", local_pack_summary),
        "competitor_maps":     keep_if_none(maps,   "competitor_maps"),
        "social_trends":       keep_if_none(social, "social_trends"),
        "reddit_intel":        keep_if_none(reddit, "reddit_intel"),
        "google_trends":       keep_if_none(trends, "google_trends"),
        "facebook_ads":        keep_if_none(fb_ads, "facebook_ads"),
        # ── Recommendation B — Metricool replacement (public data) ──
        "instagram_profiles":  keep_if_none(ig_profiles, "instagram_profiles"),
        "facebook_pages":      keep_if_none(fb_pages,    "facebook_pages"),
    }

    out_path.write_text(json.dumps(result, indent=2))
    print(f"\nSaved to {out_path}")

    # ── Print summary ──
    _print_summary(local_pack_summary, maps, social)
    _print_intel_summary(reddit, trends, fb_ads)

    return result


def _summarise_local_pack(serp_results):
    """Summarise CB247 local pack presence across all SERP queries."""
    in_pack   = []
    not_found = []
    for entry in (serp_results or []):
        kw  = entry.get("keyword", "")
        pos = entry.get("cb247_in_local_pack")
        if pos:
            in_pack.append({"keyword": kw, "position": pos})
        elif entry.get("local_pack"):
            not_found.append(kw)

    return {
        "appearing_in_pack":    in_pack,
        "not_in_pack":          not_found,
        "pack_presence_rate":   (
            round(len(in_pack) / (len(in_pack) + len(not_found)) * 100)
            if (in_pack or not_found) else None
        ),
    }


def _print_summary(local_pack_summary, maps, social=None):
    print("\n─── Local Pack Presence ───")
    if local_pack_summary:
        rate = local_pack_summary.get("pack_presence_rate")
        print(f"  In map pack: {len(local_pack_summary['appearing_in_pack'])} keywords "
              f"({rate}% presence rate)")
        for item in local_pack_summary["appearing_in_pack"]:
            print(f"    #{item['position']} — {item['keyword']}")
        if local_pack_summary["not_in_pack"]:
            print(f"  Not in pack: {', '.join(local_pack_summary['not_in_pack'])}")

    print("\n─── Maps Competitor Benchmarking ───")
    if maps and maps.get("summary"):
        s = maps["summary"]
        cb  = s.get("cb247", {})
        cmp = s.get("competitors", {})
        print(f"  {'':25} {'CB247':>10}  {'Competitors':>12}")
        print(f"  {'─'*50}")
        print(f"  {'Avg Rating':25} {str(cb.get('avg_rating') or '–'):>10}  "
              f"{str(cmp.get('avg_rating') or '–'):>12}")
        print(f"  {'Total Reviews':25} {str(cb.get('total_reviews') or '–'):>10}  "
              f"{str(cmp.get('total_reviews') or '–'):>12}")
        print(f"  {'Avg Photos':25} {str(cb.get('avg_photos') or '–'):>10}  "
              f"{str(cmp.get('avg_photos') or '–'):>12}")
        print(f"  {'Listing Completeness %':25} {str(cb.get('avg_completeness') or '–'):>10}  "
              f"{str(cmp.get('avg_completeness') or '–'):>12}")

        print("\n  Per-location:")
        for r in maps.get("targets", []):
            if "rating" in r:
                tag = "CB247" if r["type"] == "cb247" else "COMP "
                print(f"  [{tag}] {r['title'] or r['query'][:35]:<35} "
                      f"⭐ {r.get('rating') or '–'}  "
                      f"💬 {r.get('reviews') or 0} reviews  "
                      f"📸 {r.get('photos') or 0} photos  "
                      f"✅ {r.get('completeness_score') or 0}% complete")
    else:
        print("  Maps data not available (check APIFY_API_KEY and Maps actor access).")

    print("\n─── Social Trends (TikTok + Instagram) ───")
    if social:
        print(f"  Posts collected: {social.get('posts_collected')}")
        top_tags = social.get("trending_hashtags", [])[:8]
        if top_tags:
            print("  Trending hashtags: " + ", ".join(f"#{t['hashtag']}({t['count']})" for t in top_tags))
        for p in social.get("top_posts", [])[:5]:
            snippet = (p.get("text") or "").replace("\n", " ")[:80]
            print(f"  [{p['platform'][:2].upper()}] {p['engagement']:>8} eng — {snippet}")
    else:
        print("  Social trends not available (check TikTok/Instagram actor access on your Apify plan).")


def _print_intel_summary(reddit, trends, fb_ads):
    print("\n─── Reddit Intel ───")
    if reddit:
        print(f"  Posts collected: {reddit.get('posts_collected')}")
        for pain in (reddit.get("pain_points") or [])[:5]:
            print(f"  Pain: {pain['pain_point']:<15} ({pain['mentions']} mentions)")
        for mention in (reddit.get("competitor_mentions") or [])[:5]:
            print(f"  Brand mention: {mention['brand']:<15} {mention['mentions']} posts")
    else:
        print("  Reddit data not available.")

    print("\n─── Google Trends (Perth/WA) ───")
    if trends:
        rising = trends.get("rising_topics", [])
        if rising:
            print("  Rising topics:")
            for t in rising[:5]:
                print(f"    ↑ {t['keyword']:<30} interest: {t.get('current_value')}/100")
        declining = trends.get("declining_topics", [])
        if declining:
            print("  Declining:")
            for t in declining[:3]:
                print(f"    ↓ {t['keyword']}")
    else:
        print("  Google Trends data not available.")

    print("\n─── Facebook Ads (Competitors) ───")
    if fb_ads:
        print(f"  Ads found: {fb_ads.get('ads_found')}")
        analysis = fb_ads.get("analysis", {})
        themes = analysis.get("messaging_themes", [])
        if themes:
            print("  Competitor themes: " + ", ".join(f"{t['theme']}({t['count']})" for t in themes[:5]))
        gaps = analysis.get("gaps_for_cb247", [])
        if gaps:
            print("  CB247 gaps to exploit:")
            for g in gaps:
                print(f"    ✓ {g['message']}")
    else:
        print("  Facebook Ads data not available.")


if __name__ == "__main__":
    main()
