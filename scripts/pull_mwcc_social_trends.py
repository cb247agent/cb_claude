"""
pull_mwcc_social_trends.py — MWCC viral-trend scrape via Apify.

Mirrors the social-trends portion of pull_apify.py (CB247) but adapted for
the childcare niche on Perth-relevant hashtags. Output is the same shape
as state/social-trends.json so the brand-aware content-intel-mwcc agent
can read it identically to how CB247's content-intel reads its own.

Hashtags scraped (Perth childcare-relevant + viral format):
    #childcareperth, #perthmums, #workingparents, #perthparents,
    #vacationcareperth, #oshcperth, #perthfamily

Output:
    state/mwcc-social-trends.json
        {
          "scraped":            ISO timestamp,
          "brand":              "mwcc",
          "available":          true / false,
          "hashtags_monitored": [...],
          "posts_collected":    int,
          "trending_hashtags":  [{hashtag, count}, ...] (co-occurring tags),
          "top_posts":          [{platform, text, engagement, hashtags, url}, ...],
          "limitation_note":    string (when available=false)
        }

Cost-conscious (Tia has Apify on "once a week" + subscription credit
constraint): 5 posts per hashtag, 7 hashtags = max 70 API calls. Each
~$0.001-0.003 → ~$0.20 per weekly run. Falls through cleanly if
APIFY_API_KEY is missing or actors are unavailable.

Wire into weekly-report-mwcc.sh after STEP 4.6b (GBP performance) and
before the agent pipeline so content-intel-mwcc has fresh signal.

Run:
    .venv/bin/python3.13 scripts/pull_mwcc_social_trends.py
"""

from __future__ import annotations

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
OUTPUT    = STATE_DIR / "mwcc-social-trends.json"

# ── Load .env (matches the pattern other MWCC scripts use) ─────────────
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

APIFY_API_KEY    = os.environ.get("APIFY_API_KEY", "")
APIFY_BASE_URL   = "https://api.apify.com/v2"
APIFY_TIKTOK_ACTOR_ID = "clockworks~tiktok-scraper"
APIFY_IG_ACTOR_ID     = "apify~instagram-hashtag-scraper"

# ── Hashtag list (Perth childcare niche — verified against context/mwcc-brand-voice.md
# language: parent + childcare + early-learning vocabulary, NOT child-photo trigger words)
SOCIAL_HASHTAGS = [
    "childcareperth",
    "perthmums",
    "workingparents",
    "perthparents",
    "vacationcareperth",
    "oshcperth",
    "perthfamily",
]
POSTS_PER_TAG = 5  # 5 posts per tag × 2 platforms × 7 tags = ~70 results max


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Apify generic runner (ported from pull_apify.py for self-containment) ─

def _run_apify_actor(actor_id: str, payload: dict, timeout_checks: int = 72) -> list | None:
    """Start an actor, poll till SUCCEEDED, return dataset items.

    Returns None on any failure (key missing, actor errors, timeout). Caller
    should treat None as "this platform is unavailable this run".
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


def _normalise_social_post(item: dict, platform: str) -> dict:
    """Normalise a TikTok/Instagram dataset item into the shared post shape.

    Engagement is a weighted combination so we can rank cross-platform:
      comments × 3 → "actually talked about" beats passive likes
      shares × 5   → strongest signal
      plays × 0.01 → completion-weighted reach
    """
    if platform == "tiktok":
        text     = item.get("text") or ""
        likes    = item.get("diggCount") or 0
        comments = item.get("commentCount") or 0
        shares   = item.get("shareCount") or 0
        plays    = item.get("playCount") or 0
        url      = item.get("webVideoUrl") or item.get("url") or ""
        tags     = [h.get("name") for h in (item.get("hashtags") or [])
                    if isinstance(h, dict) and h.get("name")]
    else:  # instagram
        text     = item.get("caption") or ""
        likes    = item.get("likesCount") or 0
        comments = item.get("commentsCount") or 0
        shares   = 0
        plays    = item.get("videoViewCount") or 0
        url      = item.get("url") or ""
        tags     = item.get("hashtags") or []

    engagement = likes + comments * 3 + shares * 5 + int(plays * 0.01)
    return {
        "platform":   platform,
        "text":       (text or "").strip()[:300],
        "likes":      likes,
        "comments":   comments,
        "shares":     shares,
        "plays":      plays,
        "engagement": engagement,
        "hashtags":   [t.lower() for t in tags if t],
        "url":        url,
    }


def _scrape_tiktok(hashtags: list[str], per_tag: int) -> list[dict]:
    items = _run_apify_actor(
        APIFY_TIKTOK_ACTOR_ID,
        {
            "hashtags":              hashtags,
            "resultsPerPage":        per_tag,
            "shouldDownloadVideos":  False,
            "shouldDownloadCovers":  False,
            "proxyCountryCode":      "AU",
        },
    )
    if not items:
        return []
    return [_normalise_social_post(i, "tiktok") for i in items if isinstance(i, dict)]


def _scrape_instagram(hashtags: list[str], per_tag: int) -> list[dict]:
    items = _run_apify_actor(
        APIFY_IG_ACTOR_ID,
        {
            "hashtags":     hashtags,
            "resultsLimit": per_tag,
        },
    )
    if not items:
        return []
    return [_normalise_social_post(i, "instagram") for i in items if isinstance(i, dict)]


def _extract_trending_hashtags(posts: list[dict], top_n: int = 20) -> list[dict]:
    """Count co-occurring hashtags across collected posts.

    Useful for content-intel-mwcc: tells us which adjacent tags MWCC could
    bolt onto its own posts to expand reach without straying off-niche.
    """
    c: Counter = Counter()
    for p in posts:
        for tag in set(p.get("hashtags", [])):
            c[tag] += 1
    return [{"hashtag": t, "count": n} for t, n in c.most_common(top_n)]


def _write_placeholder(reason: str) -> None:
    """Write an available=false placeholder so the bash script + agent
    know the scrape ran but produced no signal."""
    out = {
        "scraped":            _now_iso(),
        "brand":              "mwcc",
        "available":          False,
        "hashtags_monitored": SOCIAL_HASHTAGS,
        "posts_collected":    0,
        "trending_hashtags":  [],
        "top_posts":          [],
        "limitation_note":    reason,
    }
    STATE_DIR.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"[mwcc-social-trends] placeholder written → {OUTPUT.relative_to(BASE_DIR)} (reason: {reason})")


def main() -> int:
    if not APIFY_API_KEY:
        _write_placeholder("APIFY_API_KEY not set in .env — agent will degrade to own-page signals only.")
        return 0

    print(f"[mwcc-social-trends] Scraping {len(SOCIAL_HASHTAGS)} hashtags: "
          f"{', '.join('#' + h for h in SOCIAL_HASHTAGS)}")
    print(f"  Posts per tag: {POSTS_PER_TAG} (capped to stay under weekly Apify budget)")

    all_posts: list[dict] = []

    print("  → TikTok...")
    try:
        tiktok = _scrape_tiktok(SOCIAL_HASHTAGS, POSTS_PER_TAG)
        all_posts.extend(tiktok)
        print(f"     {len(tiktok)} TikTok posts collected")
    except Exception as e:
        print(f"     TikTok scrape failed: {e}")

    print("  → Instagram...")
    try:
        ig = _scrape_instagram(SOCIAL_HASHTAGS, POSTS_PER_TAG)
        all_posts.extend(ig)
        print(f"     {len(ig)} Instagram posts collected")
    except Exception as e:
        print(f"     Instagram scrape failed: {e}")

    if not all_posts:
        _write_placeholder(
            "Both TikTok and Instagram actors returned no posts. "
            "Possible causes: Apify subscription credit depleted (top-up due 2026-06-02), "
            "actor access expired, or hashtags too niche this week. "
            "Agent will degrade to own-page signals only."
        )
        return 0

    all_posts.sort(key=lambda p: p["engagement"], reverse=True)
    top_posts = all_posts[:25]
    trending  = _extract_trending_hashtags(all_posts, top_n=20)

    out = {
        "scraped":            _now_iso(),
        "brand":              "mwcc",
        "available":          True,
        "hashtags_monitored": SOCIAL_HASHTAGS,
        "posts_collected":    len(all_posts),
        "trending_hashtags":  trending,
        "top_posts":          top_posts,
    }
    STATE_DIR.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(out, indent=2, ensure_ascii=False))

    print(f"\n[mwcc-social-trends] OK")
    print(f"  Posts collected: {len(all_posts)}")
    print(f"  Top 5 hashtags:  {', '.join('#' + t['hashtag'] for t in trending[:5])}")
    print(f"  Top post: {top_posts[0]['platform']} · engagement={top_posts[0]['engagement']}")
    print(f"  Saved → {OUTPUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
