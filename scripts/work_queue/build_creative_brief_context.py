"""
build_creative_brief_context.py — Shared context helper for creative briefs.

WHY THIS EXISTS
    Both `generate_briefs.py` (per-action HTML briefs that surface in the
    dashboard's View Brief modal) and `generate_monthly_shoot_pack.py`
    (one monthly markdown shoot pack for Shauna) need the SAME context to
    produce useful briefs:

      - Past winning Meta ads (top CTR from last 6 weeks) — what creative
        angles worked recently
      - Apify viral signals (trending hashtags, top posts, competitor FB ads)
        — what's hot in the fitness vertical right now
      - Image inventory (which on-hand assets can be reused vs. needing a
        fresh shoot)
      - Compliance reminders (don't say "only gym with", TGA claims, etc.)
      - Higgsfield AI fallback prompts for shots Shauna can't capture

    Keeping this in ONE module means: per-action briefs and monthly pack
    stay perfectly aligned, and adding a new signal (e.g., a new Apify data
    source) updates both surfaces at once.

OUTPUT
    A `CreativeContext` dict — pure data, no formatting. The two callers
    render it differently:
      - per-action brief: HTML section appended to docs/briefs/{id}.html
      - monthly pack: markdown sections in outputs/asset-library/shoot-pack-*.md

DESIGN NOTE
    All paths and signal extractors are defensive — missing state files or
    empty Apify blocks degrade gracefully to empty lists, never raise.
    Shauna only works once a month — a pipeline error during a Friday cron
    must NOT block her shoot pack.

Shipped: 12 Jun 2026 (hybrid brief generator, per Tia direction).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE_DIR  = Path(__file__).resolve().parent.parent.parent
STATE_DIR = BASE_DIR / "state"
IMAGE_DIR = BASE_DIR / "Image"

ADS_FILE       = STATE_DIR / "ads-data.json"
APIFY_FILE     = STATE_DIR / "apify-data.json"
METRICOOL_FILE = STATE_DIR / "metricool-data.json"

# Account-level Meta benchmark for declaring an ad a "winner". 1.84% was
# the rolling 4-week CTR account avg as of 12 Jun 2026 — anything > 1.5x
# this is a clear outperform.
WINNER_CTR_MULTIPLIER = 1.5
MIN_WINNER_SPEND = 50   # AUD — ignore < $50 spend (too noisy to call a winner)


def _safe_load(p: Path) -> dict:
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def _past_winners(ads_blob: dict) -> list[dict]:
    """Top 5 Meta ads by CTR from the most recent week. We surface the
    winners so Shauna's next shoot can mirror what's already working —
    angle, format, hook, location — rather than reinventing.
    """
    meta = ads_blob.get("meta_ads") or []
    if not isinstance(meta, list) or not meta:
        return []
    # Pick latest week by `end` date
    latest = max(meta, key=lambda w: w.get("end", ""))
    combined = latest.get("combined") or {}
    account_ctr = combined.get("ctr", 1.8) or 1.8
    winner_threshold = account_ctr * WINNER_CTR_MULTIPLIER

    ads = latest.get("ads") or []
    winners = []
    for a in ads:
        if not isinstance(a, dict):
            continue
        ctr   = a.get("ctr") or 0
        spend = a.get("spend") or 0
        if ctr >= winner_threshold and spend >= MIN_WINNER_SPEND:
            winners.append({
                "name":     a.get("name") or a.get("ad_name") or "(unnamed)",
                "location": a.get("location") or a.get("campaign") or "—",
                "ctr":      round(ctr, 2),
                "spend":    round(spend, 2),
                "format":   _infer_format_from_name(a.get("name") or ""),
            })
    # Sort by CTR descending, top 5
    winners.sort(key=lambda x: x["ctr"], reverse=True)
    return winners[:5]


def _infer_format_from_name(ad_name: str) -> str:
    """Heuristic to infer creative format from ad name conventions."""
    n = ad_name.lower()
    if "reel" in n:     return "Reel"
    if "story" in n:    return "Story"
    if "carousel" in n: return "Carousel"
    if "video" in n:    return "Video"
    if "static" in n or "image" in n or "photo" in n: return "Static"
    return "Unknown"


def _viral_signals(apify_blob: dict) -> dict:
    """Extract the high-signal viral content cues for Shauna's brief.
    Empty sub-blocks are skipped silently — Apify scrapes intermittently
    fail and we don't want briefs to look broken.
    """
    social = apify_blob.get("social_trends") or {}
    return {
        "trending_hashtags": (social.get("trending_hashtags") or [])[:8],
        "top_posts":         (social.get("top_posts") or [])[:5],
        "competitor_ig":     _competitor_ig_summary(apify_blob),
        "competitor_fb_ads": _competitor_fb_ads(apify_blob),
        "google_trends":     (apify_blob.get("google_trends") or {}),
        "reddit_threads":    (apify_blob.get("reddit_intel") or {}).get("top_threads", [])[:5],
    }


def _competitor_ig_summary(apify_blob: dict) -> list[dict]:
    """One row per competitor IG profile we're tracking — follower count
    and last post date are enough signal for a brief."""
    ig = (apify_blob.get("instagram_profiles") or {}).get("competitors") or {}
    if not isinstance(ig, dict):
        return []
    out = []
    for handle, info in ig.items():
        if not isinstance(info, dict):
            continue
        out.append({
            "handle":      handle,
            "followers":   info.get("followers") or info.get("followers_count") or "—",
            "last_post":   info.get("latest_post_at") or info.get("last_post") or "—",
            "post_count":  info.get("posts_count") or info.get("post_count") or "—",
        })
    return out[:6]


def _competitor_fb_ads(apify_blob: dict) -> list[dict]:
    """Active competitor FB ads with a CB247-relevant offer. We only
    surface offer-y ads (free month, no joining fee, kids hub promo) —
    pure brand ads are noise."""
    fb = apify_blob.get("facebook_ads") or []
    if not isinstance(fb, list):
        return []
    OFFER_KEYWORDS = [
        "free", "no joining", "no contract", "first month",
        "kids hub", "personal training", "reformer", "trial",
    ]
    out = []
    for ad in fb[:30]:   # cap scan
        if not isinstance(ad, dict):
            continue
        body = (ad.get("ad_text") or ad.get("body") or "").lower()
        if any(k in body for k in OFFER_KEYWORDS):
            out.append({
                "page":  ad.get("page_name") or ad.get("page") or "—",
                "body":  (ad.get("ad_text") or ad.get("body") or "")[:240],
                "running_since": ad.get("start_date") or "—",
            })
    return out[:6]


def _image_inventory() -> list[dict]:
    """List on-hand images. Shauna's brief should note what we already
    have so she doesn't reshoot something usable."""
    if not IMAGE_DIR.exists():
        return []
    out = []
    for p in sorted(IMAGE_DIR.iterdir()):
        if p.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        out.append({
            "filename":  p.name,
            "size_kb":   round(p.stat().st_size / 1024, 1),
            "relpath":   f"Image/{p.name}",
        })
    return out


def _compliance_reminders() -> list[str]:
    """CB247-specific compliance rules every creative brief must respect.
    Pulled verbatim from CB247-Knowledge-Base.md banned-patterns list so
    Shauna's photo direction never produces a frame that triggers a
    rewrite at QC.
    """
    return [
        "NEVER say 'only gym with' — Ryderwear also has sauna + reformer (ACL risk).",
        "NEVER claim therapeutic benefit (heals/cures/treats/burns fat) — TGA breach.",
        "NEVER name a competitor (Revo / Anytime / Snap / Ryderwear) in copy.",
        "NEVER show alcohol, smoking, or anything that conflicts with health-club positioning.",
        "Add-ons (Reformer, ChasingRX, Sauna+Ice) are PAID extras — never imply included in $11.95/wk.",
        "Brand voice: confident, no buzz words (leverage/synergy/utilize/facilitate).",
        "Cite price as '$11.95/week' in promotional copy only — body copy keeps numbers off.",
    ]


def _higgsfield_fallback_suggestions(creative_action: dict) -> list[dict]:
    """If Shauna can't capture a shot in-club, suggest a Higgsfield AI prompt.
    Per Tia direction 12 Jun 2026: AI is a SAFETY NET, not the primary plan."""
    title = (creative_action.get("title") or "").lower()
    suggestions = []
    if "kids hub" in title or "school holiday" in title:
        suggestions.append({
            "shot":   "Kids Hub interior — kids playing while parent trains in background",
            "prompt": "Bright modern gym kids zone, 5-10 year olds playing safely, "
                      "blurred parent on treadmill in distance, warm natural light, "
                      "Australian aesthetic, no faces visible, lifestyle photo",
        })
    if "sauna" in title or "ice bath" in title or "recovery" in title:
        suggestions.append({
            "shot":   "Traditional sauna or ice bath scene — recovery zone hero",
            "prompt": "Steamy traditional Finnish sauna interior at golden hour, "
                      "warm cedar wood, single person silhouette towel-wrapped, "
                      "premium spa-grade lighting, Perth wellness studio",
        })
    if "reformer" in title or "pilates" in title:
        suggestions.append({
            "shot":   "Reformer Pilates studio — class in session",
            "prompt": "Modern reformer pilates studio, 4 women mid-session on reformers, "
                      "clean white interior, athletic wear, focused expressions, "
                      "morning light through floor-to-ceiling windows",
        })
    if "fifo" in title or "freeze" in title:
        suggestions.append({
            "shot":   "FIFO worker — high-vis at airport / departure",
            "prompt": "FIFO worker in high-vis orange shirt at Perth airport gate, "
                      "gym duffel bag, optimistic but tired expression, golden hour, "
                      "documentary-style photography",
        })
    if "outdoor" in title or "winter" in title or "save" in title:
        suggestions.append({
            "shot":   "Winter motivation scene — Perth context",
            "prompt": "Perth winter morning, person in athleisure walking toward gym entrance, "
                      "low sun, breath visible, contemplative mood, "
                      "tagline-friendly negative space top-left",
        })
    return suggestions


def build_context(creative_action: dict | None = None) -> dict[str, Any]:
    """Main entry point. Returns a full context dict.

    creative_action is optional — when present we tailor the Higgsfield
    suggestions to that one action; when None (monthly pack) we surface
    the generic signal set and let the renderer slot per-shot prompts in.
    """
    ads_blob   = _safe_load(ADS_FILE)
    apify_blob = _safe_load(APIFY_FILE)

    return {
        "past_winners":          _past_winners(ads_blob),
        "viral":                 _viral_signals(apify_blob),
        "image_inventory":       _image_inventory(),
        "compliance_reminders":  _compliance_reminders(),
        "higgsfield_suggestions": (
            _higgsfield_fallback_suggestions(creative_action)
            if creative_action else []
        ),
        # Provide raw blobs for renderers that want extra signals
        "_account_meta_ctr":  (
            (ads_blob.get("meta_ads") or [{}])[-1].get("combined", {}).get("ctr")
            if (ads_blob.get("meta_ads") or []) else None
        ),
    }


def cli_dump():
    """Quick debug — `python build_creative_brief_context.py` prints the
    context tree for sanity-checking signal extraction."""
    ctx = build_context()
    print(json.dumps(ctx, indent=2, default=str))


if __name__ == "__main__":
    cli_dump()
