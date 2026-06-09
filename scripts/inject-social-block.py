"""
inject-social-block.py — Inject organic social data into docs/index.html.

Same inline-injection pattern as inject-seo-extras.py and bake-mwcc-report.py.
Reads:
  state/apify-data.json       -> instagram_profiles + facebook_pages (new)
  state/gbp-performance.json  -> GBP API metrics (new)
  state/gbp-data.json         -> GBP ratings/reviews (existing Apify)
  state/social-trends.json    -> trending hashtags (existing)

Writes a <script id="social-data-block">window.SOCIAL_DATA = {...}</script>
into docs/index.html. The frontend renderOrgSocial reads window.SOCIAL_DATA
first, falls back to the hardcoded Metricool block in D.organic_social
when SOCIAL_DATA is empty.

Run after pull_apify.py + pull_gbp_performance.py to refresh the page.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
INDEX_PATH = BASE_DIR / "docs" / "index.html"


def _load(filename, default=None):
    p = STATE_DIR / filename
    if not p.exists():
        return default if default is not None else {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return default if default is not None else {}


def _engagement(post):
    """Combined engagement signal — likes + comments + shares + views."""
    return (
        (post.get("likes") or 0)
        + (post.get("comments") or 0)
        + (post.get("shares") or 0)
        + ((post.get("views") or 0) // 10)  # views weighted 10× lower than likes
    )


def build_payload():
    apify = _load("apify-data.json", {})
    gbp_perf = _load("gbp-performance.json", {})
    gbp_ratings = _load("gbp-data.json", {})
    trends = _load("social-trends.json", {})
    metricool = _load("metricool-data.json", {})  # parsed weekly PDF (richest source)

    ig_block = apify.get("instagram_profiles") or {}
    fb_block = apify.get("facebook_pages") or {}

    # ── Process Instagram CB247 own ──
    cb247_ig = ig_block.get("cb247") or {}
    ig_competitors = ig_block.get("competitors") or []

    # Split CB247 posts into Reels vs Posts (based on is_reel flag)
    own_posts = cb247_ig.get("latest_posts") or []
    own_reels = [p for p in own_posts if p.get("is_reel")]
    own_static = [p for p in own_posts if not p.get("is_reel")]

    # Top by engagement
    top_reels = sorted(own_reels, key=_engagement, reverse=True)[:5]
    top_posts = sorted(own_static, key=_engagement, reverse=True)[:5]

    cb247_ig_summary = {
        "handle":            cb247_ig.get("handle") or "chasingbetter247",
        "followers":         cb247_ig.get("followers") or 0,
        "follows":           cb247_ig.get("follows") or 0,
        "posts_count":       cb247_ig.get("posts_count") or 0,
        "verified":          cb247_ig.get("verified") or False,
        "is_business":       cb247_ig.get("is_business") or False,
        "reels_recent":      len(own_reels),
        "posts_recent":      len(own_static),
        "top_reels":         top_reels,
        "top_posts":         top_posts,
        "available":         bool(cb247_ig),
    }

    ig_competitors_summary = [
        {
            "handle":      c.get("handle"),
            "followers":   c.get("followers") or 0,
            "posts_count": c.get("posts_count") or 0,
            "recent_posts": len(c.get("latest_posts") or []),
            "recent_reels": len([p for p in (c.get("latest_posts") or []) if p.get("is_reel")]),
        }
        for c in ig_competitors
    ]

    # ── Process Facebook CB247 own ──
    cb247_fb = fb_block.get("cb247") or {}
    fb_competitors = fb_block.get("competitors") or []

    fb_own_posts = cb247_fb.get("posts") or []
    fb_top_posts = sorted(fb_own_posts, key=_engagement, reverse=True)[:5]

    cb247_fb_summary = {
        "name":         cb247_fb.get("name") or "ChasingBetter247",
        "followers":    cb247_fb.get("followers") or 0,
        "likes":        cb247_fb.get("likes") or 0,
        "posts_recent": len(fb_own_posts),
        "top_posts":    fb_top_posts,
        "available":    bool(cb247_fb),
    }

    fb_competitors_summary = [
        {
            "name":         c.get("name"),
            "url":          c.get("url"),
            "followers":    c.get("followers") or 0,
            "likes":        c.get("likes") or 0,
            "posts_recent": len(c.get("posts") or []),
        }
        for c in fb_competitors
    ]

    # ── GBP performance + ratings merged ──
    # Priority order:
    #   1. Google Business Profile Performance API (state/gbp-performance.json)
    #      — when GCP enables the API. Currently NOT enabled.
    #   2. Metricool PDF GBP sections (state/metricool-data.json:gbp)
    #      — covers Malaga (main PDF) + Ellenbrook (sidecar PDF) when Tia
    #      drops them weekly.
    #   3. Empty placeholder.
    # Field name mapping metricool → dashboard:
    #   directions   → direction_requests
    #   reach_total  → total_impressions
    gbp_combined = gbp_perf.get("combined") or {}
    gbp_locs = gbp_perf.get("locations") or {}
    mc_gbp = metricool.get("gbp") or {}
    mc_mal = mc_gbp.get("malaga_perf") or {}
    mc_ell = mc_gbp.get("ellenbrook_perf") or {}

    def _mc_perf(loc):
        return {
            "total_actions":      loc.get("total_actions"),
            "website_clicks":     loc.get("website_clicks"),
            "phone_clicks":       loc.get("phone_clicks"),
            "direction_requests": loc.get("directions"),
            "total_impressions":  loc.get("reach_total"),
            "maps_reach":         loc.get("maps_reach"),
            "search_reach":       loc.get("search_reach"),
            "website_chg":        loc.get("website_chg"),
            "phone_chg":          loc.get("phone_chg"),
            "directions_chg":     loc.get("directions_chg"),
            "actions_chg":        loc.get("actions_chg"),
            "reach_chg":          loc.get("reach_chg"),
        }

    use_metricool_gbp = (not gbp_combined and not gbp_locs) and bool(mc_mal or mc_ell)

    if use_metricool_gbp:
        mal_perf = _mc_perf(mc_mal)
        ell_perf = _mc_perf(mc_ell)
        gbp_payload = {
            "available": True,
            "source":    "metricool_pdf",
            "date_range": metricool.get("date_range") or {},
            "combined": {
                "total_actions":      (mc_mal.get("total_actions") or 0) + (mc_ell.get("total_actions") or 0),
                "website_clicks":     (mc_mal.get("website_clicks") or 0) + (mc_ell.get("website_clicks") or 0),
                "phone_clicks":       (mc_mal.get("phone_clicks") or 0) + (mc_ell.get("phone_clicks") or 0),
                "direction_requests": (mc_mal.get("directions") or 0) + (mc_ell.get("directions") or 0),
                "total_impressions":  (mc_mal.get("reach_total") or 0) + (mc_ell.get("reach_total") or 0),
            },
            "malaga": {
                "performance": mal_perf,
                "rating":      (gbp_ratings.get("malaga") or {}).get("rating"),
                "reviews":     (gbp_ratings.get("malaga") or {}).get("reviews"),
                "photos":      (gbp_ratings.get("malaga") or {}).get("photos"),
            },
            "ellenbrook": {
                "performance": ell_perf,
                "rating":      (gbp_ratings.get("ellenbrook") or {}).get("rating") or mc_ell.get("star_rating"),
                "reviews":     (gbp_ratings.get("ellenbrook") or {}).get("reviews") or mc_ell.get("reviews_total"),
                "photos":      (gbp_ratings.get("ellenbrook") or {}).get("photos"),
            },
        }
    else:
        gbp_payload = {
            "available": bool(gbp_combined or gbp_locs),
            "source":    "gbp_performance_api" if gbp_combined else "none",
            "date_range": gbp_perf.get("date_range") or {},
            "combined":   gbp_combined,
            "malaga": {
                "performance": gbp_locs.get("malaga") or {},
                "rating":      (gbp_ratings.get("malaga") or {}).get("rating"),
                "reviews":     (gbp_ratings.get("malaga") or {}).get("reviews"),
                "photos":      (gbp_ratings.get("malaga") or {}).get("photos"),
            },
            "ellenbrook": {
                "performance": gbp_locs.get("ellenbrook") or {},
                "rating":      (gbp_ratings.get("ellenbrook") or {}).get("rating"),
                "reviews":     (gbp_ratings.get("ellenbrook") or {}).get("reviews"),
                "photos":      (gbp_ratings.get("ellenbrook") or {}).get("photos"),
            },
        }

    # ── Metricool parsed PDF (preferred source — richest private data) ──
    metricool_available = bool(metricool.get("available"))
    metricool_payload = {
        "available":     metricool_available,
        "parsed_at":     metricool.get("parsed_at") or "",
        "date_range":    metricool.get("date_range") or {},
        "combined":      metricool.get("combined") or {},
        "fb":            metricool.get("fb") or {},
        "ig":            metricool.get("ig") or {},
        "gbp":           metricool.get("gbp") or {},
        "parse_quality": metricool.get("parse_quality") or {},
    }

    payload = {
        "generated_at":    datetime.now(timezone.utc).isoformat(),
        "data_freshness": {
            "metricool_parsed_at":   metricool.get("parsed_at") or "",
            "metricool_date_range":  (metricool.get("date_range") or {}).get("raw") or "",
            "metricool_available":   metricool_available,
            "apify_pulled_at":       apify.get("date_pulled") or "",
            "gbp_perf_pulled_at":    gbp_perf.get("generated_at") or "",
            "gbp_ratings_pulled_at": gbp_ratings.get("generated_at") or "",
            "trends_pulled_at":      trends.get("scraped") or "",
            "gbp_api_enabled":       bool(gbp_combined or gbp_locs),
        },
        "metricool": metricool_payload,
        "instagram": {
            "available":   cb247_ig_summary["available"],
            "cb247":       cb247_ig_summary,
            "competitors": ig_competitors_summary,
        },
        "facebook": {
            "available":   cb247_fb_summary["available"],
            "cb247":       cb247_fb_summary,
            "competitors": fb_competitors_summary,
        },
        "gbp": gbp_payload,
        "trending_hashtags": trends.get("trending_hashtags") or [],
        "unavailable_metrics": [
            "Story metrics (impressions, reach, tap-forwards, exits)",
            "Post reach (only impressions/views available publicly)",
            "Post saves",
            "Follower demographics (age, gender, geo split)",
            "Best-time-to-post audience hours",
        ],
        "data_source_note": "Apify (public Instagram + Facebook) + Google Business Profile Performance API. Replaces Metricool (subscription not available).",
    }
    return payload


def inject():
    payload = build_payload()
    json_payload = json.dumps(payload, indent=2, default=str)

    html = INDEX_PATH.read_text(encoding="utf-8")
    new_block = (
        '<script id="social-data-block">\n'
        '// CB247 organic social data — auto-generated by scripts/inject-social-block.py\n'
        '// Sources: Apify (Instagram + Facebook public scrapes) + Google Business Profile Performance API\n'
        f'window.SOCIAL_DATA = {json_payload};\n'
        '</script>'
    )

    if 'id="social-data-block"' in html:
        updated = re.sub(
            r'<script id="social-data-block">.*?</script>',
            lambda _: new_block,
            html,
            flags=re.DOTALL,
        )
        action = "replaced"
    else:
        anchor = 'window.DASHBOARD_DATA = {'
        idx = html.find(anchor)
        if idx == -1:
            updated = html.replace("</body>", new_block + "\n</body>")
        else:
            script_open = html.rfind("<script>", 0, idx)
            if script_open == -1:
                updated = html.replace("</body>", new_block + "\n</body>")
            else:
                updated = html[:script_open] + new_block + "\n" + html[script_open:]
        action = "inserted"

    if updated == html:
        print("[social] WARN — no change to index.html (anchor not matched)")
        return

    INDEX_PATH.write_text(updated, encoding="utf-8")
    print(f"[social] OK — block {action} in docs/index.html")
    df = payload["data_freshness"]
    print(f"        Metricool PDF:   {'OK (' + (df['metricool_date_range'] or 'no range') + ')' if df['metricool_available'] else 'NOT PARSED — drop metricool.pdf in cb247-inbox/'}")
    print(f"        Apify pulled:    {df['apify_pulled_at'][:19] if df['apify_pulled_at'] else 'no data'}")
    print(f"        GBP perf pulled: {df['gbp_perf_pulled_at'][:19] if df['gbp_perf_pulled_at'] else 'no data'}")
    print(f"        Instagram CB247: {'OK' if payload['instagram']['available'] else 'MISSING'}")
    print(f"        Facebook CB247:  {'OK' if payload['facebook']['available'] else 'MISSING'}")
    print(f"        GBP API:         {'enabled' if df['gbp_api_enabled'] else 'NOT enabled in GCP yet'}")


if __name__ == "__main__":
    inject()
