"""
build_context.py — Layer 1 context builder (Python only, zero LLM).

Reads state/*.json files, extracts only what each agent needs,
compresses to ~1-2k tokens, writes context/{agent}-context.json.

Run after every data pull:
    python context/build_context.py

Output files (never commit — add to .claudeignore):
    context/performance-context.json
    context/seo-context.json
    context/competitor-context.json
    context/content-intel-context.json
    context/audience-context.json
    context/paid-ads-context.json
    context/research-context.json
    context/content-agent-context.json
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATE = BASE_DIR / "state"
CTX = BASE_DIR / "context"


def load(name):
    p = STATE / f"{name}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception as e:
        print(f"  WARN: could not load {name}.json — {e}")
        return None


def save(name, data):
    out = CTX / f"{name}-context.json"
    out.write_text(json.dumps(data, indent=2))
    size = len(json.dumps(data)) // 4
    print(f"  ✅ {name}-context.json (~{size} tokens)")


def build_performance():
    ga4 = load("ga4-data")
    gsc = load("gsc-data")
    ads = load("ads-data")
    gads = load("google-ads-data")

    ctx = {"agent": "performance", "generated_at": _now()}

    if ga4:
        ctx["ga4"] = {
            "date_range": ga4.get("date_range"),
            "current": ga4.get("current"),
            "previous": ga4.get("previous"),
            "top_pages": ga4.get("top_pages", [])[:5],
            "traffic_sources": ga4.get("traffic_sources", []),
        }

    if gsc:
        ctx["gsc"] = {
            "date_range": gsc.get("date_range"),
            "top_queries": gsc.get("top_queries", [])[:15],
        }

    if ads:
        weeks = ads.get("google_ads", [])
        latest = weeks[0] if weeks else {}
        ctx["ads_this_week"] = {
            "week_label": latest.get("week_label"),
            "combined": latest.get("combined"),
            "malaga": latest.get("malaga"),
            "ellenbrook": latest.get("ellenbrook"),
            "active_campaigns": [
                c for c in latest.get("campaigns", [])
                if c.get("spend", 0) > 0
            ],
        }

    if gads:
        ctx["google_ads_accounts"] = gads.get("accounts")

    save("performance", ctx)


def build_seo():
    ahrefs = load("ahrefs-data")
    gsc = load("gsc-data")
    sf = load("screaming-frog-data")
    apify = load("apify-data")  # local pack presence only

    ctx = {"agent": "seo", "generated_at": _now()}

    if ahrefs:
        # domain_rating — API returns None when rate-limited (429)
        dr = ahrefs.get("domain_rating") or {}
        ctx["domain_rating"] = dr.get("domain_rating", {}).get("domain_rating") if isinstance(dr, dict) else None

        # organic_value — may be partial (wow_change_pct can be None)
        ov = ahrefs.get("organic_value") or {}
        ctx["organic_value"] = {
            "current_week": ov.get("current_week"),
            "previous_week": ov.get("previous_week"),
            "wow_change_pct": ov.get("wow_change_pct"),
        }

        # WoW ranking changes — top 20 movers
        ctx["wow_changes"] = (ahrefs.get("wow_changes") or [])[:20]

        # Target keyword positions
        tkp = ahrefs.get("target_keyword_positions") or {}
        ctx["target_keywords"] = {
            "date": tkp.get("date"),
            "keywords": tkp.get("keywords") or [],
            "summary": tkp.get("summary"),
        }

        # Keyword gap — top 10 per competitor (guard None values from 429 failures)
        gap = ahrefs.get("keyword_gap") or {}
        ctx["keyword_gap"] = {
            comp: (kws or [])[:10] for comp, kws in gap.items()
        }

        # Broken backlinks only (actionable)
        bb = ahrefs.get("broken_backlinks") or {}
        ctx["broken_backlinks"] = (bb.get("backlinks") or [])[:10]

    if gsc:
        ctx["gsc_top_queries"] = gsc.get("top_queries", [])[:20]

    if apify:
        ctx["local_pack"] = {
            "summary": apify.get("local_pack_summary"),
            "by_keyword": [
                {
                    "keyword": r.get("keyword"),
                    "cb247_in_pack": r.get("cb247_in_local_pack"),
                }
                for r in apify.get("competitor_serp", [])
            ],
        }

    # Site Audit — prefer Ahrefs Site Audit (Monday cron) over Screaming Frog
    site_audit = (ahrefs or {}).get("site_audit") if ahrefs else None
    if site_audit:
        ctx["site_audit"] = {
            "source":        "ahrefs",
            "crawl_date":    site_audit.get("crawl_date"),
            "health_score":  site_audit.get("health_score"),
            "pages_crawled": site_audit.get("pages_crawled"),
            "errors":        site_audit.get("errors"),
            "warnings":      site_audit.get("warnings"),
            "notices":       site_audit.get("notices"),
            "top_issues":    (site_audit.get("top_issues") or [])[:10],
        }
    elif sf:
        # Fallback: Screaming Frog manual crawl
        ctx["site_audit"] = {
            "source":     "screaming_frog",
            "crawl_date": sf.get("date_crawled"),
            "summary":    sf.get("summary"),
            "top_issues": [
                {
                    "name":        i.get("name"),
                    "priority":    i.get("priority"),
                    "count":       i.get("count"),
                    "description": i.get("description"),
                }
                for i in sf.get("issues", [])[:10]
            ],
        }

    save("seo", ctx)


def build_competitor():
    apify = load("apify-data")
    social = load("social-trends")

    ctx = {"agent": "competitor", "generated_at": _now()}

    if apify:
        ctx["local_pack_summary"] = apify.get("local_pack_summary")
        ctx["competitor_maps"] = apify.get("competitor_maps")
        ctx["facebook_ads"] = apify.get("facebook_ads")
        # SERP positions for the tracked keywords
        ctx["competitor_serp"] = [
            {
                "keyword": r.get("keyword"),
                "cb247_in_local_pack": r.get("cb247_in_local_pack"),
                "top3_organic": r.get("organic", [])[:3],
            }
            for r in apify.get("competitor_serp", [])
        ]

    if social:
        ctx["trending_hashtags"] = social.get("trending_hashtags", [])[:15]
        ctx["top_posts_summary"] = [
            {
                "platform": p.get("platform"),
                "text": (p.get("text") or "")[:120],
                "engagement": p.get("engagement"),
                "likes": p.get("likes"),
            }
            for p in social.get("top_posts", [])[:5]
        ]

    save("competitor", ctx)


def build_content_intel():
    social = load("social-trends")

    ctx = {"agent": "content-intel", "generated_at": _now()}

    if social:
        ctx["scraped"] = social.get("scraped")
        ctx["trending_hashtags"] = social.get("trending_hashtags", [])[:20]
        ctx["top_posts"] = [
            {
                "platform": p.get("platform"),
                "text": (p.get("text") or "")[:150],
                "likes": p.get("likes"),
                "shares": p.get("shares"),
                "plays": p.get("plays"),
                "engagement": p.get("engagement"),
            }
            for p in social.get("top_posts", [])[:10]
        ]

    save("content-intel", ctx)


def build_audience():
    ga4 = load("ga4-data")

    ctx = {"agent": "audience", "generated_at": _now()}

    if ga4:
        ctx["date_range"] = ga4.get("date_range")
        ctx["current"] = ga4.get("current")
        ctx["previous"] = ga4.get("previous")
        ctx["traffic_sources"] = ga4.get("traffic_sources", [])
        ctx["top_pages"] = ga4.get("top_pages", [])[:5]
        ctx["devices"] = ga4.get("devices")

    save("audience", ctx)


def build_paid_ads():
    ads = load("ads-data")
    gads = load("google-ads-data")
    ahrefs = load("ahrefs-data")

    ctx = {"agent": "paid-ads", "generated_at": _now()}

    if ads:
        weeks = ads.get("google_ads", [])
        # Current + previous week for trend
        for i, week in enumerate(weeks[:2]):
            label = "this_week" if i == 0 else "last_week"
            ctx[label] = {
                "week_label": week.get("week_label"),
                "combined": week.get("combined"),
                "malaga": week.get("malaga"),
                "ellenbrook": week.get("ellenbrook"),
                "active_campaigns": [
                    c for c in week.get("campaigns", [])
                    if c.get("spend", 0) > 0
                ],
            }

    if gads:
        # Full campaign list with CPC (needed for pause/reduce decisions)
        ctx["campaigns_detail"] = [
            {
                "name": c.get("name"),
                "location": c.get("location"),
                "status": c.get("status"),
                "spend": c.get("spend"),
                "cpc": c.get("cpc"),
                "ctr": c.get("ctr"),
                "conversions": c.get("conversions"),
            }
            for c in gads.get("campaigns", [])
            if c.get("spend", 0) > 0
        ]

    if ahrefs:
        # Which target keywords rank organically — used to recommend ad pauses
        tkp = ahrefs.get("target_keyword_positions", {})
        ctx["organic_keyword_positions"] = [
            {
                "keyword": kw.get("keyword"),
                "position": kw.get("position"),
                "url": kw.get("url"),
            }
            for kw in tkp.get("keywords", [])
        ]

    save("paid-ads", ctx)


def build_research():
    apify = load("apify-data")
    social = load("social-trends")

    ctx = {"agent": "research", "generated_at": _now()}

    if apify:
        ctx["keyword_tracking"] = apify.get("keyword_tracking", [])
        ctx["local_pack_summary"] = apify.get("local_pack_summary")
        ctx["facebook_ads"] = apify.get("facebook_ads")
        ctx["reddit_intel"] = apify.get("reddit_intel")
        ctx["google_trends"] = apify.get("google_trends")
        # Competitor SERP — just positions, not full organic listings
        ctx["competitor_serp_summary"] = [
            {
                "keyword": r.get("keyword"),
                "cb247_in_local_pack": r.get("cb247_in_local_pack"),
                "cb247_position": next(
                    (o.get("position") for o in r.get("organic", [])
                     if "chasingbetter" in (o.get("url") or "")),
                    None
                ),
            }
            for r in apify.get("competitor_serp", [])
        ]

    if social:
        ctx["trending_hashtags"] = social.get("trending_hashtags", [])[:15]
        ctx["top_posts_summary"] = [
            {
                "platform": p.get("platform"),
                "text": (p.get("text") or "")[:120],
                "engagement": p.get("engagement"),
            }
            for p in social.get("top_posts", [])[:5]
        ]

    save("research", ctx)


def build_content_agent():
    social = load("social-trends")

    ctx = {"agent": "content-agent", "generated_at": _now()}

    if social:
        ctx["trending_hashtags"] = social.get("trending_hashtags", [])[:10]
        ctx["top_posts_hooks"] = [
            {
                "platform": p.get("platform"),
                "text": (p.get("text") or "")[:100],
                "engagement": p.get("engagement"),
            }
            for p in social.get("top_posts", [])[:5]
        ]

    ctx["note"] = (
        "Content agent reads prior agent outputs (seo-brief, content-intel, "
        "audience, competitor) for main data. This context provides trend signals only."
    )

    save("content-agent", ctx)


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    print(f"\n{'='*55}")
    print(f"  CB247 Context Builder — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*55}\n")

    builders = [
        ("performance",   build_performance),
        ("seo",           build_seo),
        ("competitor",    build_competitor),
        ("content-intel", build_content_intel),
        ("audience",      build_audience),
        ("paid-ads",      build_paid_ads),
        ("research",      build_research),
        ("content-agent", build_content_agent),
    ]

    errors = []
    for name, fn in builders:
        try:
            fn()
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            errors.append(name)

    print(f"\n{'='*55}")
    if errors:
        print(f"  ⚠️  {len(errors)} context file(s) failed: {', '.join(errors)}")
        sys.exit(1)
    else:
        print(f"  ✅ All 8 context files written to context/")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
