"""
bake-public-dashboard.py — CB247 Group Marketing OS Dashboard
Generates docs/index.html — self-contained, GitHub Pages ready.

Architecture:
  Python loads state/*.json → builds window.DASHBOARD_DATA JSON
  JavaScript renders all sections, handles sidebar nav, multi-business switcher
  localStorage persists: active section, content review status, recommendation status

Run:  python scripts/bake-public-dashboard.py
Deploy: bash scripts/deploy-dashboard.sh
"""

import csv
import json
from datetime import datetime
from pathlib import Path

BASE_DIR  = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
DOCS_DIR  = BASE_DIR / "docs"
OUT_FILE  = DOCS_DIR / "index.html"

BRAND   = "#3FA69A"
DARK    = "#2d7a70"
BG      = "#F0F2F5"


def load(filename):
    p = STATE_DIR / filename
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except Exception:
        return {}


def safe_float(v, default=0.0):
    try:
        return float(v or default)
    except Exception:
        return default


def safe_int(v, default=0):
    try:
        return int(v or default)
    except Exception:
        return default


def pct_change(curr, prev):
    if not prev:
        return None
    return round((curr - prev) / prev * 100, 1)


def load_tracker():
    """Load action-tracker.json directly (not in state/)."""
    p = STATE_DIR / "action-tracker.json"
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except Exception:
        return {}


def load_gads_keywords():
    """Parse the latest Google Ads keyword CSVs for both locations, return aggregated rows."""
    gads_base = BASE_DIR / "googleads"

    def parse_csv(path, location):
        rows = []
        try:
            with open(path) as f:
                lines = f.readlines()
            if len(lines) < 3:
                return rows
            reader = csv.DictReader(lines[2:])
            for r in reader:
                kw = r.get("Search keyword", "").strip()
                if not kw or kw in ("Search keyword", "Total", ""):
                    continue
                def si(v):
                    try: return int(str(v).replace(",", "").strip() or "0")
                    except: return 0
                def sf(v):
                    try: return float(str(v).replace(",", "").replace("%", "").strip() or "0")
                    except: return 0.0
                rows.append({
                    "keyword": kw,
                    "location": location,
                    "campaign": r.get("Campaign", ""),
                    "clicks": si(r.get("Clicks", 0)),
                    "impressions": si(r.get("Impr.", 0)),
                    "ctr": sf(r.get("CTR", "0").replace("%", "")),
                    "cpc": sf(r.get("Avg. CPC", 0)),
                    "cost": sf(r.get("Cost", 0)),
                    "conv": sf(r.get("Conversions", 0)),
                    "cpa": sf(r.get("Cost / conv.", "0")),
                    "conv_rate": sf(r.get("Conv. rate", "0").replace("%", "")),
                    "top_impr": sf(r.get("Impr. (Top) %", "0").replace("%", "")),
                    "abs_top_impr": sf(r.get("Impr. (Abs. Top) %", "0").replace("%", "")),
                })
        except Exception:
            pass
        return rows

    def latest_csv(folder):
        if not folder.exists():
            return None
        csvs = sorted(folder.glob("*.csv"), reverse=True)
        return csvs[0] if csvs else None

    mal_csv = latest_csv(gads_base / "Google Ads Malaga")
    ell_csv = latest_csv(gads_base / "Google Ads Ellenbrook")

    week_label = ""
    if mal_csv:
        # filename like "18May26-24May26.csv"
        week_label = mal_csv.stem.replace("-", " – ")

    rows = []
    if mal_csv:
        rows += parse_csv(mal_csv, "Malaga")
    if ell_csv:
        rows += parse_csv(ell_csv, "Ellenbrook")

    # Aggregate by keyword (case-insensitive)
    from collections import defaultdict
    agg = defaultdict(lambda: {
        "clicks": 0, "impressions": 0, "cost": 0.0, "conv": 0.0,
        "locations": set(), "campaigns": set(),
        "top_impr_weighted": 0.0, "top_impr_denom": 0,
    })
    for r in rows:
        k = r["keyword"].lower()
        a = agg[k]
        a["clicks"] += r["clicks"]
        a["impressions"] += r["impressions"]
        a["cost"] += r["cost"]
        a["conv"] += r["conv"]
        a["locations"].add(r["location"])
        a["campaigns"].add(r["campaign"])
        a["top_impr_weighted"] += r["top_impr"] * r["impressions"]
        a["top_impr_denom"] += r["impressions"]
        if "keyword" not in a:
            a["keyword"] = r["keyword"]
        else:
            # Prefer title-case / original casing
            if len(r["keyword"]) > len(a.get("keyword", "")):
                a["keyword"] = r["keyword"]

    result = []
    for k, v in agg.items():
        impr = v["impressions"] or 1
        clk = v["clicks"] or 0
        cost = v["cost"]
        conv = v["conv"]
        result.append({
            "keyword": v.get("keyword", k),
            "clicks": v["clicks"],
            "impressions": v["impressions"],
            "ctr": round(clk / impr * 100, 1),
            "cpc": round(cost / clk, 2) if clk else 0,
            "cost": round(cost, 2),
            "conv": conv,
            "cpa": round(cost / conv, 2) if conv else 0,
            "conv_rate": round(conv / clk * 100, 1) if clk else 0,
            "top_impr_pct": round(v["top_impr_weighted"] / v["top_impr_denom"], 1) if v["top_impr_denom"] else 0,
            "locations": sorted(v["locations"]),
            "campaigns": sorted(v["campaigns"]),
        })

    result.sort(key=lambda r: r["clicks"], reverse=True)
    return result, week_label


def _parse_meta_csv(path, location):
    """Parse a single Meta Ads CSV and return rows with all performance signals."""
    rows = []
    if not path or not path.exists():
        return rows
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for r in reader:
                ad_name = r.get("Ad name", "").strip()
                if not ad_name:
                    continue
                def sf(v, default=0.0):
                    try: return float(str(v).replace(",", "").strip() or str(default))
                    except: return default
                rows.append({
                    "ad_name":    ad_name,
                    "location":   location,
                    "spend":      sf(r.get("Amount spent (AUD)", 0)),
                    "impressions":int(sf(r.get("Impressions", 0))),
                    "reach":      int(sf(r.get("Reach", 0))),
                    "clicks":     int(sf(r.get("Link clicks", 0))),
                    "results":    sf(r.get("Results", 0)),
                    "cost_per_r": sf(r.get("Cost per results", 0)),
                    "freq":       sf(r.get("Frequency", 0)),
                    "ctr":        round(sf(r.get("CTR (link click-through rate)", "0").replace("%", "")), 2),
                    "cpm":        round(sf(r.get("CPM (cost per 1,000 impressions) (AUD)", 0)), 2),
                    "cpc":        round(sf(r.get("CPC (cost per link click) (AUD)", 0)), 2),
                    "quality":    r.get("Quality ranking", ""),
                    "eng_rank":   r.get("Engagement rate ranking", ""),
                    "conv_rank":  r.get("Conversion rate ranking", ""),
                    "is_organic": any(ad_name.startswith(p) for p in
                                  ("Instagram post:", "FB:", "Post:", "Facebook post:")),
                })
    except Exception:
        pass
    return rows


def _dated_csvs(folder):
    """Return CSVs with date patterns in filename, sorted newest first."""
    import re
    if not folder.exists():
        return []
    dated = [p for p in folder.glob("*.csv") if re.search(r"\d{2}-\w+-\d{4}", p.name)]
    return sorted(dated, key=lambda p: p.name, reverse=True)


def load_meta_social():
    """Parse latest + prior-week Meta Ads CSVs, return performance with WoW comparison."""
    meta_base = BASE_DIR / "metaads"
    mal_path  = meta_base / "Malaga"
    ell_path  = meta_base / "Ellenbrook"

    mal_csvs = _dated_csvs(mal_path)
    ell_csvs = _dated_csvs(ell_path)

    mal_cur  = mal_csvs[0] if len(mal_csvs) > 0 else None
    mal_prev = mal_csvs[1] if len(mal_csvs) > 1 else None
    ell_cur  = ell_csvs[0] if len(ell_csvs) > 0 else None

    week_label = mal_cur.stem.replace("Meta_Malaga-", "").replace("-", " – ") if mal_cur else ""

    cur_rows  = _parse_meta_csv(mal_cur, "Malaga") + _parse_meta_csv(ell_cur, "Ellenbrook")
    prev_rows = _parse_meta_csv(mal_prev, "Malaga") if mal_prev else []

    active      = sorted([r for r in cur_rows  if r["spend"] > 0], key=lambda r: r["impressions"], reverse=True)
    prev_active = sorted([r for r in prev_rows if r["spend"] > 0], key=lambda r: r["impressions"], reverse=True)

    def totals(rows):
        return {
            "spend":    round(sum(r["spend"]  for r in rows), 2),
            "impr":     sum(r["impressions"]  for r in rows),
            "reach":    sum(r["reach"]        for r in rows),
            "clicks":   sum(r["clicks"]       for r in rows),
            "results":  sum(r["results"]      for r in rows),
        }

    def loc_totals(rows, loc):
        lr = [r for r in rows if r["location"] == loc]
        sp = sum(r["spend"] for r in lr)
        im = sum(r["impressions"] for r in lr) or 1
        cl = sum(r["clicks"] for r in lr)
        re = sum(r["results"] for r in lr)
        return {
            "spend":    round(sp, 2),
            "impr":     sum(r["impressions"] for r in lr),
            "reach":    sum(r["reach"] for r in lr),
            "clicks":   cl,
            "results":  re,
            "ctr":      round(cl / im * 100, 2),
            "cpm":      round(sp / im * 1000, 2),
            "cpr":      round(sp / re, 2) if re else 0,
        }

    def pct(curr, prev):
        return round((curr - prev) / prev * 100, 1) if prev else None

    cur_t  = totals(active)
    prev_t = totals(prev_active)

    # Tag each ad with a performance tier based on rankings
    for r in active:
        above = sum(1 for v in [r["quality"], r["eng_rank"], r["conv_rank"]] if "Above" in v)
        below = sum(1 for v in [r["quality"], r["eng_rank"], r["conv_rank"]] if "Below" in v)
        if above >= 2:
            r["tier"] = "star"
        elif above >= 1 and below == 0:
            r["tier"] = "good"
        elif below >= 1:
            r["tier"] = "poor"
        else:
            r["tier"] = "average"

    return {
        "week_label":   week_label,
        "active":       active[:16],
        "prev_active":  prev_active[:16],
        "malaga_cur":   loc_totals(active, "Malaga"),
        "malaga_prev":  loc_totals(prev_active, "Malaga"),
        "ell_cur":      loc_totals(active, "Ellenbrook"),
        "total_spend":  cur_t["spend"],
        "total_impr":   cur_t["impr"],
        "total_reach":  cur_t["reach"],
        "total_clicks": cur_t["clicks"],
        "wow_spend":    pct(cur_t["spend"], prev_t["spend"]),
        "wow_clicks":   pct(cur_t["clicks"], prev_t["clicks"]),
        "wow_reach":    pct(cur_t["reach"], prev_t["reach"]),
        "wow_results":  pct(cur_t["results"], prev_t["results"]),
        "blended_ctr":  round(cur_t["clicks"] / max(cur_t["impr"], 1) * 100, 2),
    }


def load_metricool():
    """Return Metricool organic social data extracted from 25-31 May PDF."""
    # Extracted from metricool_25May26-31May26.pdf
    return {
        "week": "25–31 May 2026",
        # Combined account totals
        "total_followers": 14262,        # FB 5280 + IG 8982
        "total_impressions": 139100,     # -20.13% WoW
        "total_interactions": 565,       # -33.69% WoW
        "total_posts": 108,              # +45.95% WoW
        # Facebook
        "fb": {
            "followers":    5280,
            "followers_chg": 0.09,
            "impressions":  32710,
            "impressions_chg": -41.81,
            "interactions": 6,
            "interactions_chg": -90.0,
            "posts_published": 1,
            "posts_chg": -75.0,
            "reach_avg": 183,
            "engagement_rate": 2.19,
            "community_acquired": 8,
            "community_lost": 3,
            "content_views": 34230,
            "content_views_chg": -32.33,
            "page_views": 267,
            "page_views_chg": -19.09,
            # Competitor benchmarks from Metricool
            "competitors": [
                {"name": "World Gym Australia",   "followers": 51590, "posts": 9,  "engagement": 0.67},
                {"name": "Revo Fitness",           "followers": 49560, "posts": 8,  "engagement": 0.88},
                {"name": "Anytime Fitness Aus",    "followers": 46230, "posts": 3,  "engagement": 0.01},
                {"name": "Plus Fitness Ellenbrook","followers": 3023,  "posts": 19, "engagement": 0.07},
            ],
            # Top posts
            "top_posts": [
                {"text": "WA Day holiday hours announcement", "impressions": 1559, "interactions": 9,  "reach": 1830},
            ],
        },
        # Instagram
        "ig": {
            "followers":         8982,
            "followers_chg":     0.10,
            "followers_balance": 9,
            "views":             105360,
            "views_chg":         -9.64,
            "avg_reach_per_day": 4511,
            "avg_reach_per_day_chg": 15.56,
            "posts_published":   1,
            "posts_chg":         -66.67,
            "post_engagement":   1.05,
            "post_engagement_chg": -19.47,
            "reels_published":   5,
            "reels_chg":         150.0,
            "reel_avg_reach":    1624,
            "reel_engagement":   1.28,
            "reel_likes":        93,
            "reel_likes_chg":    45.31,
            "reel_saves":        3,
            "reel_shares":       6,
            "stories_published": 67,
            "stories_impressions": 54680,
            "stories_impressions_chg": 93.92,
            "story_avg_reach":   804,
            "story_reach_chg":   30.75,
            # Top reels by likes
            "top_reels": [
                {"text": "Back day Repost @justalittlelyn",                "views": 2684, "reach": 1646, "likes": 31, "saves": 2, "shares": 2, "watch_time": "30m 44s", "avg_watch": "4s", "engagement": 2.19},
                {"text": "Find someone who matches your energy",            "views": 3764, "reach": 2580, "likes": 24, "saves": 1, "shares": 2, "watch_time": "58m 4s",  "avg_watch": "6s", "engagement": 1.05},
                {"text": "Repost @bodiesbyashley ab burner",               "views": 3358, "reach": 2006, "likes": 18, "saves": 1, "shares": 0, "watch_time": "1h 39m",  "avg_watch": "5s", "engagement": 0.95},
                {"text": "1,000 days. No days off. Repost @bayley",        "views": 1754, "reach": 1064, "likes": 12, "saves": 0, "shares": 2, "watch_time": "14m 48s", "avg_watch": "6s", "engagement": 1.32},
                {"text": "Group fitness reel Repost @alinepotenza",        "views": 1150, "reach": 826,  "likes": 0,  "saves": 0, "shares": 0, "watch_time": "17m 4s",  "avg_watch": "8s", "engagement": 0.97},
            ],
            # Demographics
            "geo_top_cities": [
                {"city": "Perth, WA",       "pct": 57.66},
                {"city": "Ellenbrook, WA",  "pct": 6.80},
                {"city": "Aveley, WA",      "pct": 4.48},
                {"city": "Caversham, WA",   "pct": 1.75},
            ],
            # Competitors
            "competitors": [
                {"name": "Revo Fitness",             "handle": "revofitness",             "followers": 106220, "posts": 7,  "reels": 14, "engagement": 0.47},
                {"name": "Anytime Fitness Australia","handle": "anytimefitnessaustralia", "followers": 28170,  "posts": 4,  "reels": 2,  "engagement": 0.27},
                {"name": "World Gym Australia",      "handle": "worldgymau",              "followers": 15020,  "posts": 3,  "reels": 6,  "engagement": 0.12},
                {"name": "Muscle Universe Malaga",   "handle": "muscleuniversemalaga",    "followers": 2674,   "posts": 1,  "reels": 0,  "engagement": 1.5},
            ],
        },
        # GBP
        "gbp": {
            "reach_total":    1040,
            "reach_chg":      -23.02,
            "maps_reach":     830,
            "maps_chg":       -15.65,
            "search_reach":   210,
            "search_chg":     -42.78,
            "website_clicks": 95,
            "website_chg":    -49.74,
            "phone_clicks":   76,
            "phone_chg":      -27.62,
            "directions":     275,
            "directions_chg": -26.27,
            "total_actions":  446,
            "actions_chg":    -33.13,
            "reviews_week":   3,
            "star_rating":    4.33,
        },
    }


def _build_bidding_analysis(keywords):
    """Derive bidding strategy analysis and recommendations from aggregated keyword rows."""
    winners, wasters, low_vis, scale, new_recs = [], [], [], [], []

    # New keywords to recommend (not currently in account but strategic)
    RECOMMENDED_NEW = [
        {"keyword": "kids gym malaga",           "vol": 100,  "reason": "CB247 already #2 organically — easy #1 with ad support. Kids Hub is unique differentiator.",        "bid": "$2.00", "priority": "High"},
        {"keyword": "sauna and ice bath perth",  "vol": 90,   "reason": "Zero competition. CB247 is the only gym with both. High-intent, premium audience.",                  "bid": "$1.50", "priority": "High"},
        {"keyword": "fifo gym perth",            "vol": 70,   "reason": "FIFO freeze is CB247's unique WA market edge. No other gym targets this segment in paid.",           "bid": "$2.50", "priority": "High"},
        {"keyword": "no lock in gym malaga",     "vol": 60,   "reason": "Price-anxious searchers — CB247's $11.95/week no lock-in is the perfect answer. High conversion intent.", "bid": "$1.80", "priority": "Medium"},
        {"keyword": "reformer pilates malaga",   "vol": 80,   "reason": "Growing fast. Currently in account but near-zero impressions. Needs dedicated ad group + landing page.", "bid": "$2.00", "priority": "Medium"},
        {"keyword": "gym with ice bath malaga",  "vol": 50,   "reason": "Ice bath content trending on TikTok. Perth searches rising. Zero competitor ads on this.",           "bid": "$1.20", "priority": "Medium"},
    ]

    for kw in keywords:
        clk, conv, cost, top, abs_top = kw["clicks"], kw["conv"], kw["cost"], kw["top_impr_pct"], 0
        cpa = round(cost / conv, 2) if conv > 0 else 0
        avg_cpc = kw["cpc"]

        if conv > 0 and cpa < 20:
            rec = "Scale — raise budget"
        elif conv > 0 and cpa < 50:
            rec = "Maintain — good CPA"
        elif clk >= 5 and conv == 0 and cost > 10:
            rec = "⚠ Pause — wasting budget"
        elif top < 60 and clk > 3:
            rec = "Raise bid — low visibility"
        else:
            rec = "Monitor"

        row = {**kw, "cpa": cpa, "rec": rec}

        if conv > 0 and cpa < 20:
            scale.append(row)
        if conv > 0:
            winners.append(row)
        if clk >= 5 and conv == 0 and cost > 10:
            wasters.append(row)
        if top < 60 and clk > 3 and conv > 0:
            low_vis.append(row)

    scale.sort(key=lambda r: r["conv"], reverse=True)
    wasters.sort(key=lambda r: r["cost"], reverse=True)

    return {
        "winners": winners[:8],
        "wasters": wasters[:8],
        "scale":   scale[:8],
        "new_recs": RECOMMENDED_NEW,
        "low_vis": low_vis[:5],
    }


def build_data():
    """Load all state files and return a single dashboard data dict."""
    ga4      = load("ga4-data.json")
    gsc      = load("gsc-data.json")
    ads      = load("ads-data.json")
    apify    = load("apify-data.json")
    ahrefs   = load("ahrefs-data.json")
    refresh  = load("last-refresh.json")
    tracker  = load_tracker()

    now = datetime.now().strftime("%d %b %Y, %H:%M")

    # ── GA4 ──────────────────────────────────────────────────────────
    ga4c = (ga4.get("current")  or {})
    ga4p = (ga4.get("previous") or {})
    sessions   = safe_int(ga4c.get("sessions"))
    p_sessions = safe_int(ga4p.get("sessions"))
    convs      = safe_int(ga4c.get("conversions"))
    p_convs    = safe_int(ga4p.get("conversions"))
    users      = safe_int(ga4c.get("users"))
    new_users  = safe_int(ga4c.get("new_users"))
    conv_rate  = round(convs / sessions * 100, 1) if sessions else 0

    sources   = ga4.get("traffic_sources") or []
    top_pages = ga4.get("top_pages") or []
    devices   = ga4.get("devices") or []
    mob_s     = next((safe_int(d.get("sessions")) for d in devices if d.get("deviceCategory") == "mobile"), 0)
    mob_share = round(mob_s / sessions * 100) if sessions else 0

    # ── GSC ──────────────────────────────────────────────────────────
    gsc_s   = gsc.get("summary") or {}
    gsc_clicks = safe_int(gsc_s.get("total_clicks"))
    gsc_impr   = safe_int(gsc_s.get("total_impressions"))
    gsc_ctr    = round(safe_float(gsc_s.get("avg_ctr")) * 100, 2)
    gsc_pos    = round(safe_float(gsc_s.get("avg_position")), 1)
    top_queries = (gsc.get("top_queries") or [])[:20]
    gsc_pages_raw = (gsc.get("top_pages") or [])[:15]

    # ── Google Ads ───────────────────────────────────────────────────
    gads_list  = ads.get("google_ads") or []
    latest_ads = gads_list[0] if gads_list else {}
    prev_ads   = gads_list[1] if len(gads_list) > 1 else {}
    combined   = latest_ads.get("combined") or {}
    p_combined = prev_ads.get("combined") or {}
    ads_spend  = safe_float(combined.get("spend"))
    p_spend    = safe_float(p_combined.get("spend"))
    ads_cpa    = safe_float(combined.get("cpa"))
    ads_clicks = safe_int(combined.get("clicks"))
    ad_convs   = safe_int(combined.get("conv"))
    mal        = latest_ads.get("malaga") or {}
    ell        = latest_ads.get("ellenbrook") or {}
    p_mal      = prev_ads.get("malaga") or {}
    p_ell      = prev_ads.get("ellenbrook") or {}
    campaigns  = latest_ads.get("campaigns") or []

    trend_labels = [w.get("week_label", "") for w in gads_list[:3]][::-1]
    trend_spend  = [safe_float((w.get("combined") or {}).get("spend")) for w in gads_list[:3]][::-1]
    trend_cpa    = [safe_float((w.get("combined") or {}).get("cpa")) for w in gads_list[:3]][::-1]

    # ── Google Ads keyword CSV data ─────────────────────────────────
    gads_keywords, gads_week_label = load_gads_keywords()

    # ── Organic Social / Meta CSV data ──────────────────────────────
    meta_social = load_meta_social()
    metricool   = load_metricool()

    # ── Social trends (hashtags) ─────────────────────────────────────
    social_tr = load("social-trends.json")
    trending_hashtags = (social_tr.get("trending_hashtags") or [])[:15]
    top_social_posts  = (social_tr.get("top_posts") or [])[:5]
    # Compute totals from CSV keywords
    csv_total_clicks  = sum(k["clicks"]  for k in gads_keywords)
    csv_total_cost    = round(sum(k["cost"]  for k in gads_keywords), 2)
    csv_total_conv    = sum(k["conv"]    for k in gads_keywords)
    # Override ads_spend / ad_convs if CSV has data and json is empty
    if csv_total_cost > 0 and ads_spend == 0:
        ads_spend = csv_total_cost
    if csv_total_conv > 0 and ad_convs == 0:
        ad_convs  = csv_total_conv

    # ── GBP / Maps ───────────────────────────────────────────────────
    maps_targets = (apify.get("competitor_maps") or {}).get("targets") or []
    mal_gbp = next((t for t in maps_targets if t.get("location") == "Malaga"), {})
    ell_gbp = next((t for t in maps_targets if t.get("location") == "Ellenbrook"), {})
    comp_gbp = [t for t in maps_targets if t.get("type") == "competitor"]
    local_pack = apify.get("local_pack_summary") or {}

    # ── Ahrefs / SEO ─────────────────────────────────────────────────
    dr_obj        = (ahrefs.get("domain_rating") or {}).get("domain_rating") or {}
    domain_rating = dr_obj.get("domain_rating")

    # Organic keywords — sorted by traffic desc
    ah_kws_raw = (ahrefs.get("organic_keywords") or {}).get("keywords") or []
    ah_kws     = sorted(ah_kws_raw, key=lambda k: k.get("sum_traffic") or 0, reverse=True)

    # Organic traffic = sum of sum_traffic across all keywords
    organic_traffic = sum(k.get("sum_traffic") or 0 for k in ah_kws)

    # Organic value estimate (AUD) — sum of traffic × CPC for keywords with CPC data
    organic_value = round(sum(
        (k.get("sum_traffic") or 0) * (k.get("cpc") or 0)
        for k in ah_kws if k.get("cpc")
    ))
    organic_value_prev = 0  # no prior-week data in this structure

    # Keyword summary counts
    top3_kws  = [k for k in ah_kws if (k.get("best_position") or 99) <= 3]
    top10_kws = [k for k in ah_kws if (k.get("best_position") or 99) <= 10]
    quick_win_kws = sorted(
        [k for k in ah_kws if 4 <= (k.get("best_position") or 99) <= 20 and (k.get("volume") or 0) >= 50],
        key=lambda k: (k.get("best_position") or 99)
    )[:10]
    tk_summary = {
        "top_3_count":    len(top3_kws),
        "top_10_count":   len(top10_kws),
        "total_keywords": len(ah_kws),
        "not_ranking":    0,
    }

    # All keywords for tracker table (top 25 by traffic, deduplicated brand vs generic)
    tk_keywords = [
        {
            "keyword":  k.get("keyword",""),
            "position": k.get("best_position"),
            "volume":   k.get("volume") or 0,
            "traffic":  k.get("sum_traffic") or 0,
            "cpc":      k.get("cpc"),
            "kd":       k.get("keyword_difficulty") or 0,
            "url":      (k.get("best_position_url") or "").replace("https://www.chasingbetter247.com.au","") or "/",
            "status":   "top-3" if (k.get("best_position") or 99) <= 3
                        else "quick-win" if 4 <= (k.get("best_position") or 99) <= 10
                        else "growth" if (k.get("best_position") or 99) <= 20
                        else "low",
        }
        for k in ah_kws[:25]
    ]

    # Top pages from Ahrefs
    ah_pages = (ahrefs.get("top_pages") or {}).get("pages") or []

    # Referring domains — quality (DR 50+), de-spam
    SPAM_PATTERNS = ["seoexpress","anomaly","backlink","linkrank","seodaro","seoflx",
                     "rankyour","rank-your","buyback","pbnseo","toplinkranker","seolinkpro",
                     "linkseopro","premiumseolinks","authoritybacklinks","ranklinkx","linkrankboost",
                     "rankxlinks","pbnseo","linkrankpro"]
    all_refdoms = (ahrefs.get("referring_domains") or {}).get("refdomains") or []
    quality_refdoms = [
        d for d in all_refdoms
        if (d.get("domain_rating") or 0) >= 40
        and not any(sp in (d.get("domain") or "") for sp in SPAM_PATTERNS)
    ][:15]
    total_refdoms = len(all_refdoms)
    quality_refdoms_count = len([d for d in all_refdoms
        if (d.get("domain_rating") or 0) >= 50
        and not any(sp in (d.get("domain") or "") for sp in SPAM_PATTERNS)])

    # Recent backlinks (non-spam, last 30 days)
    all_bls = (ahrefs.get("backlinks") or {}).get("backlinks") or []
    recent_bls = [
        b for b in all_bls
        if (b.get("domain_rating_source") or 0) >= 10
        and not any(sp in (b.get("url_from") or "") for sp in SPAM_PATTERNS)
    ][:8]

    # GSC top queries for display (up to 20)
    gsc_queries_full = (gsc.get("top_queries") or [])[:20]

    # GSC top pages for display
    gsc_top_pages = (gsc.get("top_pages") or [])[:15]

    # ── SEO health score ─────────────────────────────────────────────
    def seo_score():
        s = 0
        if domain_rating: s += min(10, int(domain_rating))              # DR 7 = 7 pts
        s += min(25, len(top3_kws) * 3)                                 # top-3 keywords
        s += min(20, len(top10_kws) * 2)                                # top-10 keywords
        if organic_traffic > 500:  s += 10                              # real organic traffic
        if organic_traffic > 1000: s += 10
        s += min(15, quality_refdoms_count * 2)                         # quality backlinks
        pack_rate = (local_pack.get("pack_presence_rate") or 0)
        s += min(10, int(pack_rate // 10))
        return min(100, s)
    seo_health = seo_score()

    # ── Reddit / Trends / FB Ads ──────────────────────────────────────
    reddit  = load("reddit-intel.json")
    trends  = load("google-trends.json")
    fb_ads  = load("fb-ads-intel.json")
    social  = load("social-trends.json")

    # ── Status flags ──────────────────────────────────────────────────
    status = {
        "ga4":    "live"      if ga4    else "missing",
        "gsc":    "live"      if gsc    else "missing",
        "ads":    "live"      if ads    else "missing",
        "ahrefs": "live"      if ahrefs else "missing",
        "gbp":    "live"      if apify  else "missing",
        "meta":   "suspended" if not (ads and ads.get("meta_ads")) else "live",
    }

    return {
        "generated": now,
        "refresh_ts": (refresh or {}).get("timestamp", now),
        "status": status,

        # GA4
        "ga4": {
            "sessions": sessions, "p_sessions": p_sessions,
            "convs": convs, "p_convs": p_convs,
            "users": users, "new_users": new_users,
            "conv_rate": conv_rate, "mob_share": mob_share,
            "ses_chg": pct_change(sessions, p_sessions),
            "conv_chg": pct_change(convs, p_convs),
            "sources": [{"label": s.get("sessionDefaultChannelGroup",""), "sessions": safe_int(s.get("sessions"))} for s in sources[:6]],
            "top_pages": [{"path": p.get("pagePath",""), "views": safe_int(p.get("screenPageViews")), "sessions": safe_int(p.get("sessions"))} for p in top_pages[:10]],
            "period": f"{(ga4.get('date_range') or {}).get('start','?')} → {(ga4.get('date_range') or {}).get('end','?')}",
        },

        # GSC
        "gsc": {
            "clicks": gsc_clicks, "impressions": gsc_impr,
            "ctr": gsc_ctr, "position": gsc_pos,
            "top_queries": [{"query": q.get("query",""), "clicks": q.get("clicks",0), "impressions": q.get("impressions",0), "ctr": round(q.get("ctr",0)*100,1), "position": round(q.get("position",0),1)} for q in top_queries],
        },

        # Google Ads
        "google_ads": {
            "spend": ads_spend, "p_spend": p_spend,
            "cpa": ads_cpa, "clicks": ads_clicks, "convs": ad_convs,
            "spend_chg": pct_change(ads_spend, p_spend),
            "malaga": {"spend": safe_float(mal.get("spend")), "cpa": safe_float(mal.get("cpa")), "clicks": safe_int(mal.get("clicks")), "conv": safe_int(mal.get("conv")), "ctr": safe_float(mal.get("ctr"))},
            "ellenbrook": {"spend": safe_float(ell.get("spend")), "cpa": safe_float(ell.get("cpa")), "clicks": safe_int(ell.get("clicks")), "conv": safe_int(ell.get("conv")), "ctr": safe_float(ell.get("ctr"))},
            "trend_labels": trend_labels, "trend_spend": trend_spend, "trend_cpa": trend_cpa,
            "campaigns": [{"name": c.get("name","")[:40], "spend": safe_float(c.get("spend")), "clicks": safe_int(c.get("clicks")), "conv": safe_int(c.get("conv")), "cpa": safe_float(c.get("cpa"))} for c in campaigns[:8]],
            "keywords": gads_keywords,
            "week_label": gads_week_label,
            "csv_clicks": csv_total_clicks,
            "csv_cost": csv_total_cost,
            "csv_conv": csv_total_conv,
            # Bidding analysis derived from CSV
            "bidding": _build_bidding_analysis(gads_keywords),
            # Competitor keyword context from Apify
            "competitor_serp": (apify.get("competitor_serp") or [])[:6],
            "keyword_tracking": (apify.get("keyword_tracking") or []),
        },

        # GBP
        "gbp": {
            "malaga": {"rating": mal_gbp.get("rating"), "reviews": safe_int(mal_gbp.get("reviews")), "photos": safe_int(mal_gbp.get("photos")), "completeness": mal_gbp.get("completeness_score")},
            "ellenbrook": {"rating": ell_gbp.get("rating"), "reviews": safe_int(ell_gbp.get("reviews")), "photos": safe_int(ell_gbp.get("photos")), "completeness": ell_gbp.get("completeness_score")},
            "competitors": [{"name": (c.get("title") or c.get("query",""))[:30], "location": c.get("location",""), "rating": c.get("rating"), "reviews": safe_int(c.get("reviews"))} for c in comp_gbp[:6]],
            "local_pack": local_pack,
        },

        # SEO / Ahrefs
        "seo": {
            "health_score": seo_health,
            "domain_rating": domain_rating,
            "organic_value": organic_value,
            "organic_traffic": organic_traffic,
            "ov_chg": None,
            "tk_summary": tk_summary,
            "keywords": tk_keywords,
            "quick_wins": quick_win_kws,
            "top_pages": [
                {
                    "url":     p.get("url","").replace("https://www.chasingbetter247.com.au","") or "/",
                    "traffic": p.get("sum_traffic") or 0,
                    "top_kw":  p.get("top_keyword",""),
                    "pos":     p.get("top_keyword_best_position"),
                    "kw_count":p.get("keywords") or 0,
                    "ref_doms":p.get("referring_domains") or 0,
                }
                for p in ah_pages[:12]
            ],
            "gsc_queries": [
                {
                    "query":       q.get("query",""),
                    "clicks":      q.get("clicks",0),
                    "impressions": q.get("impressions",0),
                    "ctr":         round((q.get("ctr") or 0)*100, 1),
                    "position":    round(q.get("position") or 0, 1),
                }
                for q in gsc_queries_full
            ],
            "gsc_pages": [
                {
                    "page":        p.get("page","").replace("https://www.chasingbetter247.com.au","") or "/",
                    "clicks":      p.get("clicks",0),
                    "impressions": p.get("impressions",0),
                    "ctr":         round((p.get("ctr") or 0)*100, 1),
                    "position":    round(p.get("position") or 0, 1),
                }
                for p in gsc_top_pages
            ],
            "referring_domains": quality_refdoms,
            "total_refdoms": total_refdoms,
            "quality_refdoms_count": quality_refdoms_count,
            "recent_backlinks": recent_bls,
            "broken_backlinks": [],
            "lost_backlinks": [],
        },

        # Intel
        "intel": {
            "reddit_pain_points": (reddit.get("pain_points") or [])[:6],
            "reddit_competitor_mentions": (reddit.get("competitor_mentions") or [])[:5],
            "google_trends_rising": (trends.get("rising_topics") or [])[:6],
            "fb_ads_themes": ((fb_ads.get("analysis") or {}).get("messaging_themes") or [])[:5],
            "fb_ads_gaps": ((fb_ads.get("analysis") or {}).get("gaps_for_cb247") or [])[:4],
            "social_top_posts": (social.get("top_posts") or [])[:5],
            "trending_hashtags": (social.get("trending_hashtags") or [])[:10],
        },

        # Organic Social
        "organic_social": {
            "meta": meta_social,
            "metricool": metricool,
            "trending_hashtags": trending_hashtags,
            "top_posts": top_social_posts,
            "competitors": [
                {
                    "name":     (c.get("title") or c.get("query",""))[:30],
                    "location": c.get("location",""),
                    "rating":   c.get("rating"),
                    "reviews":  safe_int(c.get("reviews")),
                    "photos":   safe_int(c.get("photos")),
                }
                for c in comp_gbp[:6]
            ],
            "cb247_malaga": {
                "rating":  mal_gbp.get("rating"),
                "reviews": safe_int(mal_gbp.get("reviews")),
                "photos":  safe_int(mal_gbp.get("photos")),
            },
            "cb247_ellenbrook": {
                "rating":  ell_gbp.get("rating"),
                "reviews": safe_int(ell_gbp.get("reviews")),
                "photos":  safe_int(ell_gbp.get("photos")),
            },
        },

        # Action Tracker
        "tracker": {
            "actions": tracker.get("actions", []),
            "meeting_minutes": (tracker.get("meeting_minutes") or [])[-5:],
            "last_updated": tracker.get("last_updated", ""),
        },
    }


CONTENT_ITEMS = [
    {
        "id": "p1", "day": 0, "platform": "gbp", "type": "GBP Post",
        "title": "GBP Post — Sauna & Ice Bath",
        "assignee": "Joanne", "assigneeRole": "Social Media Manager",
        "caption": "Recovery is part of training. Our Sauna + Ice Bath combo at ChasingBetter247 Malaga gives your body the reset it needs. $11.95/week, no lock-in.",
        "instructions": "Post to both Malaga and Ellenbrook GBP profiles. Use a high-quality photo of the sauna or ice bath area. Best posting time: Tuesday 7–9am or Saturday 8am. Include the $11.95 price point and 'no lock-in' in the first sentence for SEO. Tag location: Malaga.",
        "kw": "sauna gym perth", "dueDate": "+0",
    },
    {
        "id": "p2", "day": 1, "platform": "instagram", "type": "Instagram Reel",
        "title": "Reel — FIFO Lifestyle",
        "assignee": "Agust", "assigneeRole": "Video Creator",
        "caption": "Fly in. Train hard. We get it. CB247's FIFO-friendly freeze means your membership works around your roster.",
        "instructions": "30–45 second Reel. Open with a hook: 'Working FIFO? Your gym should work around you.' Show the freeze feature on the app or website. Voiceover tone: direct, no-nonsense, WA working-class. End with CTA: 'Freeze. Resume. No questions asked.' Hashtags: #fifo #fifoperth #gymperth #chasingbetter247",
        "kw": "fifo gym perth", "dueDate": "+1",
    },
    {
        "id": "p3", "day": 2, "platform": "blog", "type": "SEO Blog Post",
        "title": "Blog — Best Gym Malaga",
        "assignee": "John", "assigneeRole": "SEO Specialist",
        "caption": "Targeting 'best gym Malaga' — 320 searches/month. H1: 'The Best Gym in Malaga? Here's Why 8,000 Members Chose CB247'. Full outline and keyword map ready.",
        "instructions": "Target keyword: 'best gym malaga' (320/mo, KD 18). Secondary: 'gym malaga perth', 'cheap gym malaga'. Word count: 1,200–1,500 words. Structure: H1 → Intro (lead with price + facilities) → H2: What Makes a Great Gym in Malaga? → H2: CB247 Malaga Facilities (list all: 24/7, Kids Hub, Sauna, Ice Bath, Reformer Pilates, Neon21) → H2: Pricing Comparison (CB247 vs Revo vs Anytime) → H2: Member Reviews → H2: FAQ → CTA: 'Join from $11.95/week'. Internal links: homepage, Malaga page, pricing page. Mark adds draft to WordPress as pending.",
        "kw": "best gym malaga", "dueDate": "+2",
        "draftLink": "https://cb247agent.github.io/cb_claude/blog-drafts/best-gym-malaga.html",
        "draftReviewers": "John (SEO), Jane (QC), Ange",
    },
    {
        "id": "p4", "day": 2, "platform": "instagram", "type": "Instagram Post",
        "title": "Instagram — Kids Hub",
        "assignee": "Shauna", "assigneeRole": "Content & Email Manager",
        "caption": "Train while the kids play. Our Kids Hub means no more 'I can't go to the gym today.' Tag a parent who needs this.",
        "instructions": "Static post or short Reel (15s). Show the Kids Hub space — colourful, safe, supervised. Caption hook: 'No babysitter? No problem.' Tag format: tag 3 local parent pages. Best time: Wednesday 9–11am (school drop-off window). Hashtags: #kidshub #gymperth #malagatribe #chasingbetter247",
        "kw": "kids gym malaga", "dueDate": "+2",
    },
    {
        "id": "p5", "day": 4, "platform": "tiktok", "type": "TikTok Video",
        "title": "TikTok — Ice Bath Reaction",
        "assignee": "Ivan", "assigneeRole": "Video Creator",
        "caption": "First ice bath at CB247 😅❄️ Would you try this? #icebath #recovery #chasingbetter247",
        "instructions": "Reaction-style video. Film a member (with permission) doing their first ice bath — show genuine reaction. Ideal length: 20–30 seconds. Hook in first 2s: 'Would you do this for $11.95/week?' Trending audio: check TikTok trending for Perth fitness content this week. Tag @chasingbetter247. Do NOT over-produce — raw, authentic works better on TikTok.",
        "kw": "ice bath gym perth", "dueDate": "+4",
    },
    {
        "id": "p6", "day": 5, "platform": "gbp", "type": "GBP Post",
        "title": "GBP Post — Reformer Pilates",
        "assignee": "Joanne", "assigneeRole": "Social Media Manager",
        "caption": "24/7 Reformer Pilates in Perth. Book your class at CB247 — Malaga & Ellenbrook.",
        "instructions": "Post to both GBP profiles. Use a class photo or studio shot. Emphasise '24/7 access' — this is a key differentiator vs Revo. Include class booking CTA. Target local pack keywords: 'reformer pilates perth', 'pilates malaga'. Post Friday morning to capture weekend bookings.",
        "kw": "reformer pilates perth", "dueDate": "+5",
    },
    {
        "id": "p7", "day": 7, "platform": "instagram", "type": "Instagram Reel",
        "title": "Reel — Gym Tour",
        "assignee": "Agust", "assigneeRole": "Video Creator",
        "caption": "Never been to CB247? Here's what $11.95/week gets you. 👀 #gymtour #chasingbetter247",
        "instructions": "60-second gym walkthrough Reel. Script: open with '$11.95 a week — here's what that actually gets you'. Walk through in order: 24/7 weights floor → Reformer Pilates studio → CrossFit/functional area → Sauna → Ice Bath → Neon21 → Kids Hub. Voiceover with on-screen text. End card: website URL + $11.95/week. Post on Sunday evening for Monday motivation traffic.",
        "kw": "gym malaga perth", "dueDate": "+7",
    },
    {
        "id": "p8", "day": 8, "platform": "email", "type": "Email Newsletter",
        "title": "Weekly Email Newsletter",
        "assignee": "Shauna", "assigneeRole": "Content & Email Manager",
        "caption": "Member spotlight + this week's class timetable + sauna booking tip",
        "instructions": "Subject line options (A/B test): A: 'This week at CB247 🏋️' / B: 'Your sauna booking tip + class times'. Structure: 1) Member spotlight (150 words, real story) → 2) This week's class timetable → 3) Sauna tip (e.g. 'Book Mon/Wed 6–7am — least busy') → 4) One referral nudge ('Bring a friend, 2 weeks free'). Send via Mailchimp. List segment: active members. Send time: Monday 6am.",
        "kw": "", "dueDate": "+8",
    },
    {
        "id": "p9", "day": 9, "platform": "blog", "type": "SEO Blog Post",
        "title": "Blog — FIFO Gym Membership Perth",
        "assignee": "Shauna", "assigneeRole": "Content & Email Manager",
        "caption": "Targeting 'fifo gym perth' — 210 searches/month. FIFO freeze angle.",
        "instructions": "Target keyword: 'fifo gym perth' (210/mo). Secondary: 'fifo gym membership', 'gym freeze perth'. Word count: 1,000–1,200 words. Angle: empathy-first — FIFO lifestyle is tough, gym should make it easier. Structure: H1: 'FIFO Gym Membership in Perth: Train Hard When You're Home' → H2: The FIFO Challenge → H2: What is a Gym Freeze? → H2: CB247 FIFO Freeze — How It Works → H2: Why CB247 is Perth's FIFO-Friendly Gym → FAQ → CTA. Tone: direct, no fluff, WA working-class voice. Shauna drafts, John reviews SEO, Mark publishes.",
        "kw": "fifo gym membership perth", "dueDate": "+9",
    },
    {
        "id": "p10", "day": 10, "platform": "tiktok", "type": "TikTok Video",
        "title": "TikTok — Neon21 Tanning",
        "assignee": "Ivan", "assigneeRole": "Video Creator",
        "caption": "You didn't know we had THIS at a $11.95/week gym 👀 #neon21 #gymsecrets",
        "instructions": "Surprise-reveal style video. Hook: 'Things at CB247 people don't know about — Part 1'. Feature: Neon21 tanning. Short (15–20s). Use trending 'surprise' audio. Build curiosity — do NOT show the feature in the thumbnail. On-screen text: 'Gym + tanning = $11.95/week??' End CTA: 'Follow for Part 2'. This format drives follows for series.",
        "kw": "", "dueDate": "+10",
    },
    {
        "id": "p11", "day": 11, "platform": "gbp", "type": "GBP Post",
        "title": "GBP Post — Ellenbrook Special",
        "assignee": "Joanne", "assigneeRole": "Social Media Manager",
        "caption": "Ellenbrook locals — your neighbourhood gym is here. 24/7 access, no lock-in, $11.95/week.",
        "instructions": "Post ONLY to Ellenbrook GBP profile (not Malaga). Hyperlocal focus — use 'Ellenbrook' 2–3 times in the post. Photo: Ellenbrook location exterior or interior. Geo-tagged post. Mention Swan Valley proximity if relevant. Local keywords: 'gym ellenbrook perth'. Post Thursday morning.",
        "kw": "gym ellenbrook perth", "dueDate": "+11",
    },
    {
        "id": "p12", "day": 13, "platform": "instagram", "type": "Instagram Post",
        "title": "Community Post — Member Story",
        "assignee": "Shauna", "assigneeRole": "Content & Email Manager",
        "caption": "Member story: how CB247 helped [member] hit their goal. Real stories, real results.",
        "instructions": "Ask reception to nominate a member who has hit a milestone this month. Get written consent + photo. Format: carousel post (3–5 slides). Slide 1: Bold quote from member. Slides 2–3: Journey story in short paragraphs. Slide 4: Their goal and result. Slide 5: CTA — 'Start your story. $11.95/week, no lock-in.' Tag the member (if they consent). This type of post gets highest saves + shares.",
        "kw": "", "dueDate": "+13",
    },
]


def generate_briefs(content_items):
    """Generate individual HTML brief pages for each content item in docs/briefs/."""
    briefs_dir = DOCS_DIR / "briefs"
    briefs_dir.mkdir(parents=True, exist_ok=True)

    role_colors = {
        "SEO Specialist": "#dbeafe",
        "Video Creator": "#fce7f3",
        "Social Media Manager": "#dcfce7",
        "Content & Email Manager": "#fef9c3",
        "Web Developer": "#ede9fe",
        "QC Manager": "#fee2e2",
    }
    platform_colors = {
        "gbp": ("#dcfce7", "#166534"),
        "instagram": ("#fce7f3", "#9d174d"),
        "tiktok": ("#1a1a2e", "#fff"),
        "blog": ("#dbeafe", "#1e40af"),
        "email": ("#fef9c3", "#854d0e"),
        "meta": ("#ede9fe", "#5b21b6"),
        "tiktok": ("#e0f2fe", "#0369a1"),
    }

    for item in content_items:
        plat = item["platform"]
        pc = platform_colors.get(plat, ("#f3f4f6", "#374151"))
        rc = role_colors.get(item.get("assigneeRole", ""), "#f0fdf4")
        due_text = f"Day +{item['dueDate'].replace('+','')}" if item.get("dueDate") else "TBD"
        kw_block = (f'<div class="section"><div class="label">Target Keyword</div>'
                    f'<div class="kw">{item["kw"]}</div></div>') if item.get("kw") else ""

        reviewers = item.get("draftReviewers", "John, Jane, Ange")
        draft_block = ""
        if item.get("draftLink"):
            dl = item["draftLink"]
            draft_block = (
                f'<div class="section" style="background:#f0fdf4;border-left:4px solid #3FA69A">'
                f'<div class="label" style="margin-bottom:10px">Draft — Ready for Review</div>'
                f'<p style="font-size:13px;color:#374151;margin-bottom:14px">'
                f'The draft is ready. Open it, read the full content, then use the approval buttons to approve, request adjustments, or reject.</p>'
                f'<a href="{dl}" target="_blank" '
                f'style="display:inline-flex;align-items:center;gap:8px;background:#3FA69A;color:#fff;'
                f'text-decoration:none;border-radius:8px;padding:10px 20px;font-size:13px;font-weight:700">'
                f'Open Draft — {item["title"]}</a>'
                f'<p style="font-size:11px;color:#6b7280;margin-top:10px">'
                f'Share this link with {reviewers} for review:<br>'
                f'<code style="background:#e5e7eb;padding:2px 6px;border-radius:4px;font-size:11px">{dl}</code></p>'
                f'</div>'
            )

        brief_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{item["title"]} — CB247 Content Brief</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f0f2f5;color:#1a1a2e;padding:24px}}
  .brief-card{{max-width:740px;margin:0 auto;background:#fff;border-radius:12px;box-shadow:0 2px 16px rgba(0,0,0,.08);overflow:hidden}}
  .brief-header{{background:#1a1a2e;padding:24px 28px;color:#fff}}
  .brief-header .logo{{font-size:13px;color:#3FA69A;font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px}}
  .brief-header h1{{font-size:20px;font-weight:700;line-height:1.3}}
  .meta-row{{display:flex;gap:10px;flex-wrap:wrap;padding:16px 28px;background:#f8f9fa;border-bottom:1px solid #e5e7eb}}
  .meta-chip{{border-radius:99px;padding:4px 12px;font-size:11px;font-weight:700}}
  .section{{padding:18px 28px;border-bottom:1px solid #f0f2f5}}
  .section:last-child{{border-bottom:none}}
  .label{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:#6b7280;margin-bottom:8px}}
  .instructions{{font-size:13px;line-height:1.8;color:#374151;white-space:pre-wrap}}
  .caption-box{{background:#f0fdf4;border-left:3px solid #3FA69A;border-radius:0 8px 8px 0;padding:14px 16px;font-size:13px;line-height:1.7;color:#1a1a2e;font-style:italic}}
  .kw{{display:inline-block;background:#dbeafe;color:#1e40af;border-radius:99px;padding:4px 14px;font-size:12px;font-weight:700}}
  .approval-section{{background:#fffbeb;padding:18px 28px}}
  .approval-section .label{{color:#92400e}}
  .approval-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:14px}}
  .appr-btn{{border:2px solid #e5e7eb;border-radius:8px;padding:12px 8px;text-align:center;cursor:pointer;transition:all .15s;font-size:12px;font-weight:700}}
  .appr-btn:hover{{border-color:#3FA69A;background:#f0fdf4}}
  .appr-btn.selected-approved{{border-color:#16a34a;background:#dcfce7;color:#166534}}
  .appr-btn.selected-adjustment{{border-color:#d97706;background:#fef9c3;color:#92400e}}
  .appr-btn.selected-rejected{{border-color:#dc2626;background:#fee2e2;color:#991b1b}}
  .notes-area{{width:100%;border:1px solid #e5e7eb;border-radius:8px;padding:10px 12px;font-size:13px;font-family:inherit;resize:vertical;min-height:80px}}
  .notes-area:focus{{outline:none;border-color:#3FA69A}}
  .save-btn{{background:#3FA69A;color:#fff;border:none;border-radius:8px;padding:10px 24px;font-size:13px;font-weight:700;cursor:pointer;margin-top:10px}}
  .save-btn:hover{{background:#2d7a70}}
  .saved-notice{{display:none;color:#16a34a;font-size:12px;font-weight:600;margin-top:8px}}
  .footer{{text-align:center;padding:16px;font-size:11px;color:#9ca3af}}
  @media print{{body{{background:#fff}}.brief-card{{box-shadow:none}}.approval-section{{display:none}}}}
</style>
</head>
<body>
<div class="brief-card">
  <div class="brief-header">
    <div class="logo">ChasingBetter247 — Content Brief</div>
    <h1>{item["title"]}</h1>
  </div>
  <div class="meta-row">
    <span class="meta-chip" style="background:{pc[0]};color:{pc[1]}">{plat.upper()} · {item["type"]}</span>
    <span class="meta-chip" style="background:{rc};color:#1a1a2e">👤 {item["assignee"]} — {item.get("assigneeRole","")}</span>
    <span class="meta-chip" style="background:#f3f4f6;color:#374151">Due: {due_text}</span>
  </div>
  <div class="section">
    <div class="label">Instructions for {item["assignee"]}</div>
    <div class="instructions">{item["instructions"]}</div>
  </div>
  <div class="section">
    <div class="label">Suggested Caption / Copy</div>
    <div class="caption-box">{item["caption"]}</div>
  </div>
  {kw_block}
  {draft_block}
  <div class="approval-section">
    <div class="label">📝 Tia's Review — {item["id"].upper()}</div>
    <div class="approval-grid">
      <div class="appr-btn" id="btn-approved" onclick="setApproval('approved')">Approved<br><span style="font-size:10px;font-weight:400">Ready to go</span></div>
      <div class="appr-btn" id="btn-adjustment" onclick="setApproval('adjustment')">Needs Adjustment<br><span style="font-size:10px;font-weight:400">Review notes below</span></div>
      <div class="appr-btn" id="btn-rejected" onclick="setApproval('rejected')">Rejected<br><span style="font-size:10px;font-weight:400">Do not proceed</span></div>
    </div>
    <div class="label" style="margin-bottom:6px">Notes / Adjustments</div>
    <textarea class="notes-area" id="approval-notes" placeholder="Add adjustment notes or feedback here..."></textarea>
    <br>
    <button class="save-btn" onclick="saveApproval()">💾 Save Review</button>
    <div class="saved-notice" id="saved-notice">Saved locally</div>
  </div>
  <div class="footer">CB247 Marketing OS · Content Brief · Generated {datetime.now().strftime("%d %b %Y")}</div>
</div>
<script>
const KEY = 'cb247-brief-{item["id"]}';
function load() {{
  const s = JSON.parse(localStorage.getItem(KEY)||'{{}}');
  if(s.status) setApproval(s.status, false);
  if(s.notes) document.getElementById('approval-notes').value = s.notes;
}}
function setApproval(val, save=true) {{
  ['approved','adjustment','rejected'].forEach(v => {{
    const btn = document.getElementById('btn-'+v);
    btn.className = 'appr-btn' + (v===val ? ' selected-'+v : '');
  }});
  if(save) {{ const s = JSON.parse(localStorage.getItem(KEY)||'{{}}'); s.status=val; localStorage.setItem(KEY,JSON.stringify(s)); }}
}}
function saveApproval() {{
  const s = JSON.parse(localStorage.getItem(KEY)||'{{}}');
  s.notes = document.getElementById('approval-notes').value;
  localStorage.setItem(KEY, JSON.stringify(s));
  const n = document.getElementById('saved-notice');
  n.style.display='block'; setTimeout(()=>n.style.display='none',2500);
}}
load();
</script>
</body>
</html>"""
        (briefs_dir / f"{item['id']}.html").write_text(brief_html, encoding="utf-8")

    print(f"✅ Content briefs generated → {briefs_dir} ({len(content_items)} files)")


def build():
    data = build_data()
    data_json = json.dumps(data, indent=2)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(HTML_TEMPLATE.replace("__DASHBOARD_DATA__", data_json), encoding="utf-8")
    print(f"✅ Dashboard generated → {OUT_FILE}")

    generate_briefs(CONTENT_ITEMS)
    return OUT_FILE


# ─────────────────────────────────────────────────────────────────────────────
# HTML TEMPLATE
# ─────────────────────────────────────────────────────────────────────────────
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ChasingBetter Group — Marketing OS</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.5.1" crossorigin="anonymous"></script>
<style>
/* ── Reset ───────────────────────────────────────── */
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --teal:#3FA69A;--teal-dim:#2d7a70;--teal-mist:#f0f7f6;
  --bg:#f4f4f4;--card:#ffffff;
  --sidebar:#0d0d0d;--sidebar-hover:#1c1c1c;
  --text:#0d0d0d;--text-2:#3a3a3a;--muted:#888;--muted-2:#bbb;
  --border:#e6e6e6;--border-strong:#ccc;
  --radius:6px;--shadow:0 1px 2px rgba(0,0,0,.06),0 2px 6px rgba(0,0,0,.04);
  --gap:20px;--sidebar-w:220px;
}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;background:var(--bg);color:var(--text);font-size:13px;line-height:1.55;overflow-x:hidden;-webkit-font-smoothing:antialiased}
a{color:var(--teal);text-decoration:none}
a:hover{text-decoration:underline}
button{cursor:pointer;border:none;background:none;font-family:inherit;font-size:inherit}
code{font-family:'SF Mono',Menlo,monospace;font-size:.85em;background:var(--bg);border:1px solid var(--border);border-radius:3px;padding:1px 5px}

/* ── Layout ──────────────────────────────────────── */
.app{display:flex;min-height:100vh}
.sidebar{width:var(--sidebar-w);min-height:100vh;background:var(--sidebar);flex-shrink:0;display:flex;flex-direction:column;position:fixed;top:0;left:0;z-index:100;overflow-y:auto}
.main{margin-left:var(--sidebar-w);flex:1;display:flex;flex-direction:column;min-height:100vh}
.topbar{background:var(--card);border-bottom:1px solid var(--border);padding:0 28px;height:52px;display:flex;align-items:center;position:sticky;top:0;z-index:50}
.content{padding:28px;flex:1;max-width:1400px}

/* ── Sidebar ─────────────────────────────────────── */
.sidebar-brand{padding:22px 18px 18px;border-bottom:1px solid rgba(255,255,255,.07)}
.sidebar-brand .logo{font-size:15px;font-weight:700;color:#fff;letter-spacing:.01em}
.sidebar-brand .logo span{color:var(--teal)}
.sidebar-brand .sub{font-size:10px;color:rgba(255,255,255,.35);margin-top:3px;letter-spacing:.03em;text-transform:uppercase}
.sidebar-section{padding:14px 0 2px}
.sidebar-section-label{font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:rgba(255,255,255,.25);padding:0 18px 6px}
.sidebar-item{display:flex;align-items:center;padding:8px 18px;color:rgba(255,255,255,.5);font-size:12.5px;font-weight:500;cursor:pointer;border-left:2px solid transparent;transition:color .12s,background .12s}
.sidebar-item:hover{color:rgba(255,255,255,.9);background:var(--sidebar-hover)}
.sidebar-item.active{color:#fff;border-left-color:var(--teal);background:rgba(63,166,154,.1)}
.sidebar-item .badge{margin-left:auto;background:var(--teal);color:#fff;border-radius:99px;font-size:9px;font-weight:700;padding:1px 6px;line-height:1.6}
.sidebar-item .badge.neutral{background:rgba(255,255,255,.15);color:rgba(255,255,255,.6)}
.sidebar-footer{margin-top:auto;padding:14px 18px;font-size:10px;color:rgba(255,255,255,.22);border-top:1px solid rgba(255,255,255,.06);line-height:1.7}

/* ── Topbar ──────────────────────────────────────── */
.biz-nav{display:flex;align-items:center;height:100%;gap:0}
.biz-tab{padding:0 18px;height:100%;display:flex;align-items:center;font-size:12.5px;font-weight:600;color:var(--muted);border-bottom:2px solid transparent;cursor:pointer;transition:color .12s;white-space:nowrap}
.biz-tab:hover{color:var(--text-2)}
.biz-tab.active{color:var(--teal);border-bottom-color:var(--teal)}
.biz-tab.coming-soon{opacity:.4;cursor:default}
.biz-tab.coming-soon::after{content:'soon';font-size:8px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;background:var(--border);color:var(--muted);padding:1px 5px;border-radius:3px;margin-left:5px}
.topbar-right{margin-left:auto;display:flex;align-items:center;gap:10px}
.refresh-badge{font-size:11px;color:var(--muted);display:flex;align-items:center;gap:5px}
.status-dot{width:6px;height:6px;border-radius:50%;background:var(--teal);display:inline-block;flex-shrink:0}
.status-dot.warn{background:var(--muted)}
.status-dot.error{background:var(--text-2)}

/* ── Pages ───────────────────────────────────────── */
.page{display:none}
.page.active{display:block}
.page-header{margin-bottom:28px;padding-bottom:20px;border-bottom:1px solid var(--border)}
.page-header h1{font-size:20px;font-weight:700;letter-spacing:-.02em;color:var(--text)}
.page-header p{color:var(--muted);font-size:12.5px;margin-top:5px}
.page-footer{text-align:center;font-size:11px;color:var(--muted-2);padding:32px 0 16px;border-top:1px solid var(--border);margin-top:16px}

/* ── KPI grid ────────────────────────────────────── */
.kpi-grid{display:grid;gap:var(--gap);margin-bottom:var(--gap)}
.kpi-grid.cols-4{grid-template-columns:repeat(4,1fr)}
.kpi-grid.cols-3{grid-template-columns:repeat(3,1fr)}
.kpi-grid.cols-2{grid-template-columns:repeat(2,1fr)}
.kpi-card{background:var(--card);border-radius:var(--radius);padding:20px 22px;border:1px solid var(--border);border-top:2px solid var(--teal)}
.kpi-card.secondary{border-top-color:var(--border-strong)}
.kpi-label{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-bottom:6px}
.kpi-value{font-size:28px;font-weight:700;color:var(--text);letter-spacing:-.04em;line-height:1}
.kpi-change{font-size:11px;font-weight:600;margin-top:6px;display:flex;align-items:center;gap:3px}
.kpi-change.up{color:var(--teal)}
.kpi-change.down{color:var(--text-2)}
.kpi-change.flat{color:var(--muted)}
.kpi-sub{font-size:11px;color:var(--muted);margin-top:3px}

/* ── Cards ───────────────────────────────────────── */
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:var(--gap)}
.grid-3{display:grid;grid-template-columns:repeat(3,1fr);gap:var(--gap)}
.mb{margin-bottom:var(--gap)}
.card{background:var(--card);border-radius:var(--radius);padding:20px 24px;border:1px solid var(--border)}
.card-h{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-bottom:16px;display:flex;align-items:center;justify-content:space-between}
.card-period{font-size:11px;color:var(--muted-2);font-weight:400}

/* ── Stat rows ───────────────────────────────────── */
.stat-row{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--border);font-size:12.5px}
.stat-row:last-child{border-bottom:none}
.stat-label{color:var(--muted)}
.stat-val{font-weight:600;color:var(--text)}
.stat-val.good{color:var(--teal)}
.stat-val.bad{color:var(--text-2)}
.stat-val.warn{color:var(--muted)}

/* ── Section title ───────────────────────────────── */
.section-title{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:14px;display:flex;align-items:center;gap:10px}
.section-title::after{content:'';flex:1;height:1px;background:var(--border)}

/* ── Insight / alert box ─────────────────────────── */
.insight{border-radius:var(--radius);padding:14px 16px;margin-bottom:var(--gap);font-size:12.5px;line-height:1.6;border:1px solid var(--border);background:var(--card)}
.insight.teal{background:var(--teal-mist);border-color:rgba(63,166,154,.25);border-left:3px solid var(--teal)}
.insight.neutral{background:#f9f9f9;border-left:3px solid var(--border-strong)}
.insight.warn{background:#fafafa;border-left:3px solid var(--muted-2)}
.insight-label{font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-bottom:5px}

/* ── Tables ──────────────────────────────────────── */
table{width:100%;border-collapse:collapse;font-size:12px}
thead th{text-align:left;padding:8px 12px;font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);border-bottom:1px solid var(--border-strong);background:#fafafa;white-space:nowrap}
tbody td{padding:9px 12px;border-bottom:1px solid var(--border);vertical-align:top}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover td{background:#fafafa}
.num{text-align:right;font-variant-numeric:tabular-nums;font-weight:500}
.rank{color:var(--muted);font-size:11px;width:24px}

/* ── Position badges ─────────────────────────────── */
.pos-badge{display:inline-block;border-radius:3px;padding:1px 6px;font-weight:600;font-size:11px;font-variant-numeric:tabular-nums}
.pos-1-3{background:var(--teal-mist);color:var(--teal-dim)}
.pos-4-10{background:#f0f0f0;color:var(--text-2)}
.pos-11-20{background:#f0f0f0;color:var(--muted)}
.pos-deep{background:#f0f0f0;color:var(--muted-2)}
.pos-none{color:var(--muted-2)}
.wow-up{color:var(--teal);font-weight:700}
.wow-down{color:var(--text-2);font-weight:600}
.wow-new{color:var(--teal);font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.05em}

/* ── Progress bar ────────────────────────────────── */
.progress-wrap{margin:8px 0 4px}
.progress-label{display:flex;justify-content:space-between;font-size:11px;color:var(--muted);margin-bottom:5px}
.progress-track{background:var(--border);border-radius:99px;height:4px;overflow:hidden}
.progress-fill{background:var(--teal);height:100%;border-radius:99px;transition:width .4s ease}

/* ── Chart ───────────────────────────────────────── */
.chart-wrap{position:relative;height:180px}

/* ── Recommendation cards ────────────────────────── */
.rec-board{display:flex;flex-direction:column;gap:1px;border:1px solid var(--border);border-radius:var(--radius);overflow:hidden}
.rec-card{background:var(--card);padding:16px 20px;display:flex;gap:16px;align-items:flex-start;border-bottom:1px solid var(--border);transition:background .1s}
.rec-card:last-child{border-bottom:none}
.rec-card:hover{background:#fafafa}
.rec-card.done{opacity:.5}
.rec-body{flex:1}
.rec-tags{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px;align-items:center}
.rec-tag{border-radius:3px;padding:2px 7px;font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;background:#f0f0f0;color:var(--text-2)}
.rec-tag.t-seo{background:var(--teal-mist);color:var(--teal-dim)}
.rec-tag.t-content{background:#f0f0f0;color:var(--text-2)}
.rec-tag.t-web{background:#f0f0f0;color:var(--text-2)}
.rec-tag.t-ads{background:#f0f0f0;color:var(--text-2)}
.rec-title{font-size:13.5px;font-weight:700;margin-bottom:5px;color:var(--text)}
.rec-why{font-size:12px;color:var(--muted);line-height:1.55;margin-bottom:12px}
.rec-footer{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.rec-impact{font-size:11.5px;font-weight:700;color:var(--teal)}
.rec-owner{font-size:11px;color:var(--muted)}
.rec-status-btn{border:1px solid var(--border);border-radius:3px;padding:3px 10px;font-size:10.5px;font-weight:600;cursor:pointer;transition:all .1s;color:var(--text-2);background:var(--card)}
.rec-status-btn:hover{border-color:var(--teal);color:var(--teal)}
.status-new{border-color:var(--teal);color:var(--teal)}
.status-accepted{background:#f0f0f0;color:var(--text-2)}
.status-inprogress{background:var(--teal-mist);border-color:var(--teal);color:var(--teal-dim)}
.status-done{background:var(--sidebar);color:#fff;border-color:var(--sidebar)}
.status-skipped{background:#f0f0f0;color:var(--muted-2)}
.rec-outcome-input{flex:1;border:1px solid var(--border);border-radius:4px;padding:4px 10px;font-size:12px;font-family:inherit;min-width:180px}
.rec-outcome-input:focus{outline:none;border-color:var(--teal)}

/* ── Kanban ──────────────────────────────────────── */
.kanban{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;align-items:start}
.kanban-col{background:#f9f9f9;border-radius:var(--radius);border:1px solid var(--border);padding:14px}
.kanban-col-header{font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:12px;display:flex;align-items:center;justify-content:space-between}
.kanban-col-header .count{background:var(--card);border:1px solid var(--border);border-radius:99px;padding:1px 7px;font-size:10px;font-weight:600;color:var(--text-2)}
.content-card{background:var(--card);border-radius:4px;padding:12px 14px;margin-bottom:8px;cursor:pointer;border:1px solid var(--border);transition:border-color .1s}
.content-card:hover{border-color:var(--teal)}
.content-card .platform-tag{font-size:9.5px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;border-radius:2px;padding:2px 6px;display:inline-block;margin-bottom:7px;background:#f0f0f0;color:var(--text-2)}
.platform-gbp{background:var(--teal-mist);color:var(--teal-dim)}
.platform-instagram,.platform-tiktok,.platform-meta{background:#f0f0f0;color:var(--text-2)}
.platform-blog{background:var(--sidebar);color:rgba(255,255,255,.8)}
.platform-email{background:#f0f0f0;color:var(--text-2)}
.content-card .cc-title{font-size:12px;font-weight:700;margin-bottom:5px;color:var(--text)}
.content-card .cc-preview{font-size:11px;color:var(--muted);line-height:1.45;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.content-card .cc-footer{display:flex;justify-content:space-between;align-items:center;margin-top:9px;font-size:10.5px;color:var(--muted)}
.content-card .cc-assignee{font-weight:600;color:var(--text-2)}

/* ── Website / task list ─────────────────────────── */
.task-list{list-style:none}
.task-item{display:flex;align-items:flex-start;gap:12px;padding:10px 0;border-bottom:1px solid var(--border);font-size:12.5px}
.task-item:last-child{border-bottom:none}
.priority-pill{border-radius:3px;padding:2px 7px;font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;flex-shrink:0;margin-top:1px;background:#f0f0f0;color:var(--text-2)}
.p-critical{background:var(--sidebar);color:#fff}
.p-high{background:var(--teal-mist);color:var(--teal-dim)}
.p-medium{background:#f0f0f0;color:var(--text-2)}
.p-low{background:#f9f9f9;color:var(--muted)}

/* ── Stars ───────────────────────────────────────── */
.stars{color:var(--teal)}

/* ── Chips ───────────────────────────────────────── */
.chip{display:inline-block;background:var(--teal-mist);color:var(--teal-dim);border-radius:3px;padding:2px 8px;font-size:11px;font-weight:600;margin:2px}

/* ── Divider ─────────────────────────────────────── */
.divider{border:none;border-top:1px solid var(--border);margin:var(--gap) 0}

/* ── Planner Modal ───────────────────────────────── */
.modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:1000;align-items:center;justify-content:center;padding:20px}
.modal-overlay.open{display:flex}
.modal-box{background:var(--card);border-radius:8px;border:1px solid var(--border);box-shadow:0 8px 32px rgba(0,0,0,.15);width:100%;max-width:620px;max-height:90vh;overflow-y:auto;display:flex;flex-direction:column}
.modal-head{padding:18px 22px 16px;border-bottom:1px solid var(--border);display:flex;align-items:flex-start;justify-content:space-between;gap:12px;position:sticky;top:0;background:var(--card);z-index:2}
.modal-head-left{flex:1}
.modal-title{font-size:15px;font-weight:700;margin:6px 0 0;color:var(--text)}
.modal-close{font-size:16px;cursor:pointer;color:var(--muted);padding:4px 7px;border-radius:4px;border:1px solid transparent}
.modal-close:hover{background:var(--bg);border-color:var(--border)}
.modal-meta{display:flex;flex-wrap:wrap;gap:6px;padding:12px 22px;background:#f9f9f9;border-bottom:1px solid var(--border)}
.modal-body{padding:18px 22px;display:flex;flex-direction:column;gap:16px}
.modal-section-label{font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-bottom:6px}
.modal-instructions{font-size:12.5px;line-height:1.8;color:var(--text);background:#f9f9f9;border-radius:4px;padding:14px 16px;border-left:2px solid var(--teal)}
.modal-caption{font-size:12.5px;line-height:1.7;color:var(--text-2);background:#f9f9f9;border-radius:4px;padding:14px 16px;font-style:italic;border-left:2px solid var(--border-strong)}
.modal-approval{background:#f9f9f9;border-radius:4px;padding:14px 16px;border:1px solid var(--border)}
.approval-btns{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}
.appr-pill{border:1px solid var(--border);border-radius:4px;padding:5px 14px;font-size:11px;font-weight:600;cursor:pointer;transition:all .1s;background:var(--card);color:var(--text-2)}
.appr-pill:hover{border-color:var(--teal);color:var(--teal)}
.appr-pill.sel-approved{background:var(--teal);border-color:var(--teal);color:#fff}
.appr-pill.sel-adjustment{background:var(--teal-mist);border-color:var(--teal);color:var(--teal-dim)}
.appr-pill.sel-rejected{background:var(--sidebar);border-color:var(--sidebar);color:#fff}
.modal-notes{width:100%;border:1px solid var(--border);border-radius:4px;padding:8px 12px;font-size:12px;font-family:inherit;resize:vertical;min-height:60px}
.modal-notes:focus{outline:none;border-color:var(--teal)}
.modal-foot{display:flex;align-items:center;justify-content:space-between;padding:14px 22px;border-top:1px solid var(--border);background:var(--card);position:sticky;bottom:0;gap:10px;flex-wrap:wrap}
.modal-foot .btn-teal{background:var(--teal);color:#fff;border:none;border-radius:4px;padding:8px 18px;font-size:12px;font-weight:600;cursor:pointer}
.modal-foot .btn-teal:hover{background:var(--teal-dim)}
.modal-foot .btn-ghost{background:none;border:1px solid var(--border);border-radius:4px;padding:8px 14px;font-size:12px;font-weight:500;cursor:pointer;color:var(--muted)}
.modal-foot .btn-ghost:hover{border-color:var(--text-2);color:var(--text)}
.brief-link{display:inline-flex;align-items:center;gap:5px;font-size:11.5px;font-weight:600;color:var(--teal);text-decoration:none;border:1px solid var(--teal);border-radius:4px;padding:5px 12px}
.brief-link:hover{background:var(--teal-mist);text-decoration:none}
.modal-status-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.status-cycle-btn{border:1px solid var(--border);background:var(--card);color:var(--text-2);border-radius:4px;padding:4px 12px;font-size:11px;font-weight:600;cursor:pointer}
.status-cycle-btn:hover{border-color:var(--teal);color:var(--teal)}

/* ── Action Tracker ──────────────────────────────── */
.tracker-pipeline{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:28px}
.tracker-stage{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:16px}
.tracker-stage-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid var(--border)}
.tracker-stage-label{font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
.tracker-stage-count{font-size:11px;font-weight:700;color:var(--text);background:#f0f0f0;border-radius:3px;padding:1px 7px}
.tracker-card{background:#f9f9f9;border-radius:4px;padding:12px;margin-bottom:6px;border-left:2px solid var(--border);cursor:pointer;transition:all .1s;border:1px solid var(--border);border-left-width:2px}
.tracker-card:hover{border-color:var(--teal);background:var(--card)}
.tracker-card.decision-approved{border-left-color:var(--teal)}
.tracker-card.decision-adjusted{border-left-color:var(--muted)}
.tracker-card.decision-rejected{border-left-color:var(--muted-2);opacity:.55}
.tracker-card.status-completed{border-left-color:var(--teal);background:var(--teal-mist)}
.tracker-card-title{font-size:12px;font-weight:600;line-height:1.45;margin-bottom:7px;color:var(--text)}
.tracker-card-meta{font-size:10.5px;color:var(--muted);display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.tracker-tag{display:inline-block;padding:1px 6px;border-radius:2px;font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.03em;background:#f0f0f0;color:var(--text-2)}
.tracker-tag.tag-seo{background:var(--teal-mist);color:var(--teal-dim)}
.tag-content,.tag-paid-ads,.tag-website,.tag-operations,.tag-social{background:#f0f0f0;color:var(--text-2)}
.p1-dot::before{content:'P1';font-size:8.5px;font-weight:700;background:var(--sidebar);color:#fff;border-radius:2px;padding:0 4px;margin-right:4px}
.p2-dot::before{content:'P2';font-size:8.5px;font-weight:700;background:#f0f0f0;color:var(--text-2);border-radius:2px;padding:0 4px;margin-right:4px}
.p3-dot::before{content:'P3';font-size:8.5px;font-weight:700;background:#f0f0f0;color:var(--muted);border-radius:2px;padding:0 4px;margin-right:4px}
.tracker-detail-panel{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:22px;margin-bottom:20px;display:none}
.tracker-detail-panel.open{display:block}
.outcome-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px}
.outcome-cell{background:#f9f9f9;border-radius:4px;padding:12px;border:1px solid var(--border)}
.outcome-cell .label{font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-bottom:5px}
.outcome-cell .val{font-size:14px;font-weight:700;color:var(--text)}
.verdict-worked{color:var(--teal)}
.verdict-partial,.verdict-no_impact,.verdict-negative{color:var(--muted)}
.meeting-log{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:16px 20px;margin-bottom:10px}
.meeting-log-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.meeting-log-date{font-weight:700;font-size:13px;color:var(--text)}
.meeting-log-pills{display:flex;gap:6px}
.meet-pill{font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;padding:2px 7px;border-radius:3px;background:#f0f0f0;color:var(--text-2)}
.meet-approved{background:var(--teal-mist);color:var(--teal-dim)}
.meet-adjusted,.meet-rejected{background:#f0f0f0;color:var(--muted)}

/* ── README ──────────────────────────────────────── */
.readme-section{margin-bottom:40px}
.readme-section h2{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin-bottom:18px;padding-bottom:10px;border-bottom:1px solid var(--border)}
.loop-diagram{display:flex;align-items:flex-start;gap:0;flex-wrap:wrap;padding:8px 0}
.loop-node{display:flex;flex-direction:column;align-items:center;gap:8px;min-width:100px;padding:0 4px}
.loop-icon{width:44px;height:44px;border-radius:50%;border:1px solid var(--border);display:flex;align-items:center;justify-content:center;flex-shrink:0;background:var(--card)}
.loop-icon-inner{width:12px;height:12px;border-radius:50%;background:var(--teal)}
.loop-icon.active-node{border-color:var(--teal);background:var(--teal-mist)}
.loop-label{font-size:11px;font-weight:700;text-align:center;line-height:1.35;color:var(--text)}
.loop-sub{font-size:10px;color:var(--muted);text-align:center;line-height:1.3}
.loop-arrow{font-size:14px;color:var(--muted-2);margin:0 2px;flex-shrink:0;margin-top:14px}
.agent-phase{margin-bottom:22px}
.agent-phase-label{font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:10px;display:flex;align-items:center;gap:8px}
.agent-phase-label::after{content:'';flex:1;height:1px;background:var(--border)}
.agent-row{display:flex;align-items:stretch;gap:10px;flex-wrap:wrap}
.agent-box{background:var(--card);border:1px solid var(--border);border-radius:6px;padding:14px 16px;flex:1;min-width:140px;position:relative;transition:border-color .1s}
.agent-box:hover{border-color:var(--teal)}
.agent-box.primary-agent{border-color:var(--teal);border-width:1.5px}
.agent-box .agent-num{display:inline-block;background:var(--sidebar);color:#fff;font-size:9px;font-weight:700;padding:1px 6px;border-radius:2px;margin-bottom:8px;letter-spacing:.04em}
.agent-box .agent-name{font-size:12.5px;font-weight:700;margin-bottom:5px;color:var(--text)}
.agent-box .agent-desc{font-size:11px;color:var(--muted);line-height:1.45}
.agent-box .agent-out{font-size:10px;color:var(--teal);margin-top:8px;font-weight:600}
.agent-box .agent-reads{font-size:10px;color:var(--muted-2);margin-top:3px}
.agent-connector{display:flex;align-items:center;justify-content:center;font-size:14px;color:var(--muted-2);padding:0 2px;flex-shrink:0;align-self:center}
.phase-arrow{text-align:center;font-size:12px;color:var(--muted);margin:2px 0 18px;letter-spacing:.05em;text-transform:uppercase;font-weight:600}
.team-flow{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:12px}
.team-card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:14px 16px;border-top:2px solid var(--border-strong)}
.team-card.lead{border-top-color:var(--teal)}
.team-card .tc-name{font-size:12.5px;font-weight:700;margin-bottom:2px;color:var(--text)}
.team-card .tc-role{font-size:10px;color:var(--muted);margin-bottom:10px;text-transform:uppercase;letter-spacing:.05em;font-weight:600}
.team-card .tc-tasks{font-size:11.5px;color:var(--text-2);line-height:1.65}
.team-card .tc-tasks li{list-style:none;padding-left:14px;position:relative}
.team-card .tc-tasks li::before{content:'–';position:absolute;left:0;color:var(--teal)}
.data-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px}
.data-source{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:14px;text-align:center}
.data-source .ds-icon{width:32px;height:32px;border-radius:50%;background:var(--teal-mist);border:1px solid rgba(63,166,154,.2);margin:0 auto 8px;display:flex;align-items:center;justify-content:center}
.data-source .ds-dot{width:10px;height:10px;border-radius:50%;background:var(--teal)}
.data-source .ds-name{font-size:11px;font-weight:700;margin-bottom:3px;color:var(--text)}
.data-source .ds-file{font-size:9.5px;color:var(--muted);font-family:'SF Mono',Menlo,monospace}
.skill-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.skill-row{display:flex;align-items:flex-start;gap:10px;background:var(--card);border:1px solid var(--border);border-radius:4px;padding:10px 14px}
.skill-trigger{font-size:11px;font-weight:600;color:var(--teal);min-width:130px;flex-shrink:0}
.skill-skill{font-size:11px;color:var(--muted)}
.legend{display:flex;flex-wrap:wrap;gap:14px;margin-top:10px;padding-top:12px;border-top:1px solid var(--border)}
.legend-item{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--muted)}
.legend-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
@media(max-width:1100px){.kpi-grid.cols-4{grid-template-columns:repeat(2,1fr)}.kanban{grid-template-columns:repeat(3,1fr)}.tracker-pipeline{grid-template-columns:repeat(2,1fr)}}
@media(max-width:768px){.sidebar{transform:translateX(-100%)}.main{margin-left:0}.kpi-grid.cols-4,.kpi-grid.cols-3,.grid-2,.grid-3{grid-template-columns:1fr}.kanban{grid-template-columns:1fr 1fr}.skill-grid{grid-template-columns:1fr}.tracker-pipeline{grid-template-columns:1fr}}
</style>
</head>
<body>
<script>
window.DASHBOARD_DATA = __DASHBOARD_DATA__;
</script>

<div class="app">

<!-- ══ SIDEBAR ═══════════════════════════════════════════════════════ -->
<aside class="sidebar">
  <div class="sidebar-brand">
    <div class="logo">Chasing<span>Better</span></div>
    <div class="sub">Marketing OS</div>
  </div>

  <div class="sidebar-section">
    <div class="sidebar-section-label">Overview</div>
    <div class="sidebar-item active" data-page="overview" onclick="nav(this)">Dashboard</div>
  </div>

  <div class="sidebar-section">
    <div class="sidebar-section-label">Performance</div>
    <div class="sidebar-item" data-page="seo" onclick="nav(this)">SEO &amp; Organic</div>
    <div class="sidebar-item" data-page="google-ads" onclick="nav(this)">Google Ads</div>
    <div class="sidebar-item" data-page="organic-social" onclick="nav(this)">Organic Social</div>
    <div class="sidebar-item" data-page="meta-ads" onclick="nav(this)">Meta Ads</div>
    <div class="sidebar-item" data-page="gbp" onclick="nav(this)">Google Business</div>
  </div>

  <div class="sidebar-section">
    <div class="sidebar-section-label">Content</div>
    <div class="sidebar-item" data-page="content-planner" onclick="nav(this)">Content Planner</div>
    <div class="sidebar-item" data-page="content-review" onclick="nav(this)">
      Content Review
      <span class="badge neutral" id="review-badge">0</span>
    </div>
  </div>

  <div class="sidebar-section">
    <div class="sidebar-section-label">Operations</div>
    <div class="sidebar-item" data-page="website-manager" onclick="nav(this)">Website Manager</div>
    <div class="sidebar-item" data-page="recommendations" onclick="nav(this)">
      Recommendations
      <span class="badge neutral" id="rec-badge">0</span>
    </div>
    <div class="sidebar-item" data-page="action-tracker" onclick="nav(this)">
      Action Tracker
      <span class="badge neutral" id="tracker-badge">0</span>
    </div>
    <div class="sidebar-item" onclick="window.open('meeting-minutes.html','_blank')">Meeting Minutes</div>
  </div>

  <div class="sidebar-section">
    <div class="sidebar-section-label">Help</div>
    <div class="sidebar-item" data-page="readme" onclick="nav(this)">How It Works</div>
  </div>

  <div class="sidebar-footer">
    CB247 Group Marketing OS<br>
    Auto-runs every Monday 10am
  </div>
</aside>

<!-- ══ MAIN ══════════════════════════════════════════════════════════ -->
<div class="main">

  <!-- TOPBAR -->
  <div class="topbar">
    <div class="biz-nav">
      <div class="biz-tab active" data-biz="cb247" onclick="switchBiz(this)">CB247 Gym</div>
      <div class="biz-tab coming-soon">My World Childcare</div>
      <div class="biz-tab coming-soon">Karribank</div>
      <div class="biz-tab coming-soon">Sparrows</div>
    </div>
    <div class="topbar-right">
      <div class="refresh-badge">
        <span class="status-dot" id="system-dot"></span>
        <span id="refresh-label">Loading…</span>
      </div>
    </div>
  </div>

  <!-- CONTENT AREA -->
  <div class="content" id="content-area">

    <!-- ══ PAGE: OVERVIEW ════════════════════════════════════════════ -->
    <div class="page active" id="page-overview">
      <div class="page-header">
        <h1>Marketing Overview</h1>
        <p>ChasingBetter247 Gym · Malaga + Ellenbrook · $11.95/week, no lock-in</p>
      </div>

      <!-- KPI row -->
      <div class="kpi-grid cols-3 mb" id="overview-kpis"></div>

      <!-- GA4 + GSC -->
      <div class="section-title">Web Performance</div>
      <div class="grid-2 mb" id="overview-web"></div>

      <!-- Channel snapshot -->
      <div class="section-title">Channel Snapshot</div>
      <div class="grid-2 mb" id="overview-channels"></div>

      <!-- Top pages -->
      <div class="section-title">Top Pages</div>
      <div class="card mb" id="overview-pages"></div>
    </div>

    <!-- ══ PAGE: SEO ═════════════════════════════════════════════════ -->
    <div class="page" id="page-seo">
      <div class="page-header">
        <h1>SEO &amp; Organic Search</h1>
        <p>Primary growth driver — growing organic to reduce Google Ads spend</p>
      </div>
      <div id="seo-content"></div>
    </div>

    <!-- ══ PAGE: GOOGLE ADS ══════════════════════════════════════════ -->
    <div class="page" id="page-google-ads">
      <div class="page-header">
        <h1>Google Ads</h1>
        <p>Reduce paid spend as organic coverage grows</p>
      </div>
      <div id="gads-content"></div>
    </div>

    <!-- ══ PAGE: META ADS ════════════════════════════════════════════ -->
    <div class="page" id="page-organic-social">
      <h1>Organic Social</h1>
      <div id="orgsocial-content"></div>
    </div>

    <div class="page" id="page-meta-ads">
      <div class="page-header">
        <h1>Meta Ads</h1>
        <p>Facebook &amp; Instagram paid social</p>
      </div>
      <div id="meta-content"></div>
    </div>

    <!-- ══ PAGE: GBP ═════════════════════════════════════════════════ -->
    <div class="page" id="page-gbp">
      <div class="page-header">
        <h1>Google Business Profile</h1>
        <p>Local search visibility — Malaga &amp; Ellenbrook</p>
      </div>
      <div id="gbp-content"></div>
    </div>

    <!-- ══ PAGE: CONTENT PLANNER ════════════════════════════════════ -->
    <div class="page" id="page-content-planner">
      <div class="page-header">
        <h1>Content Planner</h1>
        <p>2-week content calendar — all channels</p>
      </div>
      <div id="planner-content"></div>
    </div>

    <!-- ══ PAGE: CONTENT REVIEW ═════════════════════════════════════ -->
    <div class="page" id="page-content-review">
      <div class="page-header">
        <h1>Content Review</h1>
        <p>Approval flow — Agent generates — Tia reviews — Jane QC — Joanne posts</p>
      </div>
      <div id="review-content"></div>
    </div>

    <!-- ══ PAGE: WEBSITE MANAGER ════════════════════════════════════ -->
    <div class="page" id="page-website-manager">
      <div class="page-header">
        <h1>Website Manager</h1>
        <p>Technical SEO health, page performance, dev tasks</p>
      </div>
      <div id="web-content"></div>
    </div>

    <!-- ══ PAGE: RECOMMENDATIONS ════════════════════════════════════ -->
    <div class="page" id="page-recommendations">
      <div class="page-header">
        <h1>Recommendations</h1>
        <p>Weekly AI-generated actions — review and assign</p>
      </div>
      <div id="rec-content"></div>
    </div>

    <!-- ══ PAGE: README ═════════════════════════════════════════════ -->
    <div class="page" id="page-readme">
      <div class="page-header">
        <h1>How It Works</h1>
        <p>System architecture, agent pipeline, and weekly workflow</p>
      </div>
      <div id="readme-content"></div>
    </div>

    <!-- ══ PAGE: ACTION TRACKER ════════════════════════════════════ -->
    <div class="page" id="page-action-tracker">
      <div class="page-header">
        <h1>Action Tracker</h1>
        <p>Recommendations — Decisions — Execution — Outcomes</p>
      </div>
      <div id="tracker-content"></div>
    </div>

    <div class="page-footer" id="page-footer"></div>
  </div><!-- /content -->
</div><!-- /main -->
</div><!-- /app -->

<!-- ══ CONTENT PLANNER MODAL ══════════════════════════════════════════ -->
<div class="modal-overlay" id="planner-modal" onclick="if(event.target===this)closePlannerModal()">
  <div class="modal-box">
    <div class="modal-head">
      <div class="modal-head-left">
        <span id="modal-platform-tag"></span>
        <div class="modal-title" id="modal-title"></div>
      </div>
      <button class="modal-close" onclick="closePlannerModal()">✕</button>
    </div>
    <div class="modal-meta" id="modal-meta"></div>
    <div class="modal-body">
      <div>
        <div class="modal-section-label">Instructions for Assignee</div>
        <div class="modal-instructions" id="modal-instructions"></div>
      </div>
      <div>
        <div class="modal-section-label">Suggested Caption / Copy</div>
        <div class="modal-caption" id="modal-caption"></div>
      </div>
      <div id="modal-kw-block"></div>
      <div>
        <div class="modal-section-label">Status</div>
        <div class="modal-status-row">
          <span id="modal-status-pill"></span>
          <button class="status-cycle-btn" id="modal-cycle-btn" onclick="cycleFromModal()">Cycle Status →</button>
        </div>
      </div>
      <div id="modal-draft-link-wrap" style="display:none;background:var(--teal-mist);border:1px solid rgba(63,166,154,.25);border-radius:4px;padding:14px 16px">
        <div class="modal-section-label" style="margin-bottom:8px">Draft — Ready for Review</div>
        <a href="#" target="_blank" class="brief-link" style="background:var(--teal);color:#fff;border-color:var(--teal)">Open Draft</a>
        <div style="font-size:11px;color:var(--muted);margin-top:8px">Share with John (SEO), Jane (QC), and Ange for review</div>
      </div>
      <div class="modal-approval">
        <div class="modal-section-label" style="margin-bottom:10px">Approval Decision</div>
        <div class="approval-btns">
          <button class="appr-pill" id="apill-approved" onclick="setModalApproval('approved')">Approved</button>
          <button class="appr-pill" id="apill-adjustment" onclick="setModalApproval('adjustment')">Needs Adjustment</button>
          <button class="appr-pill" id="apill-rejected" onclick="setModalApproval('rejected')">Rejected</button>
        </div>
        <div id="modal-notes-wrap" style="display:none">
          <div class="modal-section-label" style="margin-bottom:4px">Notes / Adjustment Instructions</div>
          <textarea class="modal-notes" id="modal-notes" placeholder="Describe adjustments needed..."></textarea>
        </div>
      </div>
    </div>
    <div class="modal-foot">
      <a class="brief-link" id="modal-brief-link" href="#" target="_blank">View Brief</a>
      <div style="display:flex;gap:8px">
        <button class="btn-ghost" onclick="closePlannerModal()">Close</button>
        <button class="btn-teal" onclick="saveModalAndClose()">Save</button>
      </div>
    </div>
  </div>
</div>

<script>
// ── Data ──────────────────────────────────────────────────────────────────────
const D = window.DASHBOARD_DATA;

// ── Helpers ───────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const fmt = (v,type) => {
  if(v===null||v===undefined) return '—';
  if(type==='$') return '$'+parseFloat(v).toLocaleString('en-AU',{minimumFractionDigits:0,maximumFractionDigits:0});
  if(type==='$2') return '$'+parseFloat(v).toLocaleString('en-AU',{minimumFractionDigits:2,maximumFractionDigits:2});
  if(type==='n') return parseInt(v).toLocaleString('en-AU');
  if(type==='%') return parseFloat(v).toFixed(1)+'%';
  if(type==='pos') return '#'+v;
  return String(v);
};
const arrow = v => v>0?'↑':v<0?'↓':'→';
const chgClass = (v,inverse=false) => v===null||v===undefined?'flat':((v>0)!==inverse?'up':'down');
const fmtChg = v => v===null||v===undefined?'—':(v>0?'+':'')+v.toFixed(1)+'%';
const posBadge = pos => {
  if(!pos) return '<span class="pos-none">–</span>';
  const cls = pos<=3?'pos-1-3':pos<=10?'pos-4-10':pos<=20?'pos-11-20':'pos-deep';
  return `<span class="pos-badge ${cls}">#${pos}</span>`;
};
const wowBadge = kw => {
  const d=kw.wow_direction, c=kw.wow_change;
  if(d==='up')   return `<span class="wow-up">↑${c}</span>`;
  if(d==='down') return `<span class="wow-down">↓${c}</span>`;
  if(d==='new')  return `<span class="wow-new">NEW</span>`;
  return '<span style="color:#999">—</span>';
};
const stars = r => {
  if(!r) return '—';
  const full = Math.round(parseFloat(r));
  return '<span class="stars">'+'★'.repeat(full)+'☆'.repeat(Math.max(0,5-full))+'</span> '+r;
};
const kpiCard = (icon,label,value,change,sub,colorClass='') => `
  <div class="kpi-card ${colorClass}">
    <div class="kpi-label">${label}</div>
    <div class="kpi-value">${value}</div>
    ${change!==null?`<div class="kpi-change ${chgClass(change)}">${arrow(change)} ${fmtChg(change)} vs prior week</div>`:''}
    ${sub?`<div class="kpi-sub">${sub}</div>`:''}
  </div>`;
const insightTypeMap = {'green':'teal','red':'warn','amber':'warn','blue':'neutral','teal':'teal'};
const insight = (type,label,text) => `
  <div class="insight ${insightTypeMap[type]||'neutral'}">
    <div class="insight-label">${label}</div>
    ${text}
  </div>`;
const sectionTitle = t => `<div class="section-title">${t}</div>`;

// ── Navigation ─────────────────────────────────────────────────────────────────
function nav(el) {
  document.querySelectorAll('.sidebar-item').forEach(i=>i.classList.remove('active'));
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  el.classList.add('active');
  const page = document.getElementById('page-'+el.dataset.page);
  if(page) page.classList.add('active');
  localStorage.setItem('cb247-active-page', el.dataset.page);
  window.scrollTo(0,0);
}
function switchBiz(el) {
  if(el.classList.contains('coming-soon')) return;
  document.querySelectorAll('.biz-tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
}

// ── Render: Overview ─────────────────────────────────────────────────────────
function renderOverview() {
  const g = D.ga4, s = D.seo, ads = D.google_ads;

  // KPI cards
  $('overview-kpis').innerHTML =
    kpiCard('','Weekly Sessions',fmt(g.sessions,'n'),g.ses_chg,`Prior: ${fmt(g.p_sessions,'n')}`) +
    kpiCard('','Conversions',fmt(g.convs,'n'),g.conv_chg,`Rate: ${fmt(g.conv_rate,'%')}`) +
    kpiCard('','SEO Health',s.health_score+'/100',null,`${s.tk_summary.top_3_count||0} top-3 · DR ${s.domain_rating||'–'}`, s.health_score>=70?'green':s.health_score>=40?'amber':'red') +
    kpiCard('','Organic Traffic',fmt(s.organic_traffic,'n'),null,`DR ${s.domain_rating||'–'} · ${s.quality_refdoms_count||0} quality backlinks`,'') +
    kpiCard('','Ad Spend',fmt(ads.spend,'$2'),ads.spend_chg,`${fmt(ads.convs,'n')} conversions`) +
    kpiCard('📏','Blended CPA',fmt(ads.cpa,'$2'),null,`Mal: ${fmt(ads.malaga.cpa,'$2')} · Ell: ${fmt(ads.ellenbrook.cpa,'$2')}`,ads.cpa>50?'red':'green');

  // Web cards
  const gsc = D.gsc;
  $('overview-web').innerHTML = `
    <div class="card">
      <div class="card-h">Google Analytics 4 <span class="card-period">${g.period}</span></div>
      <div class="stat-row"><span class="stat-label">Sessions</span><span class="stat-val">${fmt(g.sessions,'n')} <small style="color:var(--muted)">${fmtChg(g.ses_chg)}</small></span></div>
      <div class="stat-row"><span class="stat-label">Users</span><span class="stat-val">${fmt(g.users,'n')}</span></div>
      <div class="stat-row"><span class="stat-label">New Users</span><span class="stat-val">${fmt(g.new_users,'n')}</span></div>
      <div class="stat-row"><span class="stat-label">Conversions</span><span class="stat-val">${fmt(g.convs,'n')}</span></div>
      <div class="stat-row"><span class="stat-label">Conv. Rate</span><span class="stat-val">${fmt(g.conv_rate,'%')}</span></div>
      <div class="stat-row"><span class="stat-label">Mobile Share</span><span class="stat-val ${g.mob_share>80?'warn':''}">${g.mob_share}%</span></div>
      <div style="margin-top:14px"><div style="font-size:11px;color:var(--muted);font-weight:700;margin-bottom:8px">TRAFFIC BY CHANNEL</div>
      <div class="chart-wrap"><canvas id="channelChart"></canvas></div></div>
    </div>
    <div class="card">
      <div class="card-h">Search Console — Organic</div>
      <div class="stat-row"><span class="stat-label">Organic Clicks</span><span class="stat-val">${fmt(gsc.clicks,'n')}</span></div>
      <div class="stat-row"><span class="stat-label">Impressions</span><span class="stat-val">${fmt(gsc.impressions,'n')}</span></div>
      <div class="stat-row"><span class="stat-label">Avg CTR</span><span class="stat-val">${fmt(gsc.ctr,'%')}</span></div>
      <div class="stat-row"><span class="stat-label">Avg Position</span><span class="stat-val">#${gsc.position}</span></div>
      <div style="margin-top:14px"><div style="font-size:11px;color:var(--muted);font-weight:700;margin-bottom:8px">TOP QUERIES</div>
      <table><thead><tr><th>Query</th><th class="num">Clicks</th><th class="num">Pos</th></tr></thead><tbody>
        ${gsc.top_queries.slice(0,6).map(q=>`<tr><td>${q.query}</td><td class="num">${q.clicks}</td><td class="num">#${q.position}</td></tr>`).join('')||'<tr><td colspan="3" style="color:var(--muted)">No data</td></tr>'}
      </tbody></table></div>
    </div>`;

  // Channel snapshot
  const gbp = D.gbp, mal = gbp.malaga, ell = gbp.ellenbrook;
  $('overview-channels').innerHTML = `
    <div class="card">
      <div class="card-h">Google Business Profile</div>
      <div class="stat-row"><span class="stat-label">Malaga Rating</span><span class="stat-val">${stars(mal.rating)}</span></div>
      <div class="stat-row"><span class="stat-label">Malaga Reviews</span><span class="stat-val">${fmt(mal.reviews,'n')}</span></div>
      <div class="stat-row"><span class="stat-label">Ellenbrook Rating</span><span class="stat-val">${stars(ell.rating)}</span></div>
      <div class="stat-row"><span class="stat-label">Ellenbrook Reviews</span><span class="stat-val">${fmt(ell.reviews,'n')}</span></div>
      <div class="stat-row"><span class="stat-label">Local Pack Rate</span><span class="stat-val">${D.gbp.local_pack.pack_presence_rate||0}% keywords</span></div>
    </div>
    <div class="card">
      <div class="card-h">🌱 SEO vs Ads</div>
      <div class="stat-row"><span class="stat-label">Organic Value (SEO)</span><span class="stat-val good">${fmt(s.organic_value,'$')}/wk</span></div>
      <div class="stat-row"><span class="stat-label">WoW Change</span><span class="stat-val ${(s.ov_chg||0)>=0?'good':'bad'}">${fmtChg(s.ov_chg)}</span></div>
      <div class="stat-row"><span class="stat-label">Google Ads Spend</span><span class="stat-val">${fmt(ads.spend,'$2')}/wk</span></div>
      <div class="stat-row"><span class="stat-label">Keywords Page 1</span><span class="stat-val">${s.tk_summary.top_10_count||0} / 20 tracked</span></div>
      <div class="stat-row"><span class="stat-label">Top-3 Rankings</span><span class="stat-val good">${s.tk_summary.top_3_count||0} keywords</span></div>
    </div>`;

  // Top pages
  $('overview-pages').innerHTML = `
    <div class="card-h">Top Pages by Traffic</div>
    <table><thead><tr><th>#</th><th>Page</th><th class="num">Views</th><th class="num">Sessions</th></tr></thead><tbody>
      ${g.top_pages.map((p,i)=>`<tr><td class="rank">#${i+1}</td><td style="font-family:monospace;font-size:11px;color:var(--teal)">${p.path}</td><td class="num">${fmt(p.views,'n')}</td><td class="num">${fmt(p.sessions,'n')}</td></tr>`).join('')||'<tr><td colspan="4" style="color:var(--muted)">No data</td></tr>'}
    </tbody></table>`;

  // Traffic channel chart
  setTimeout(()=>{
    const labels = g.sources.map(s=>s.label);
    const vals   = g.sources.map(s=>s.sessions);
    if($('channelChart')&&labels.length) {
      new Chart($('channelChart'),{type:'bar',data:{labels,datasets:[{data:vals,backgroundColor:['#3FA69A','#2d8a7e','#5bbdb5','#7dccc6','#a0dbd8','#c3ecea'],borderRadius:4}]},options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{beginAtZero:true,grid:{color:'#f0f0f0'},ticks:{font:{size:10}}},y:{grid:{display:false},ticks:{font:{size:10}}}}}});
    }
  },100);
}

// ── Render: SEO ──────────────────────────────────────────────────────────────
function renderSEO() {
  const s = D.seo, gsc = D.gsc;

  // ── KPI row ──────────────────────────────────────────────────────────────
  let html = `<div class="kpi-grid cols-4 mb">
    ${kpiCard('','SEO Health Score', s.health_score+'/100', null,
        s.health_score>=70?'Strong — maintain momentum':s.health_score>=40?'Building — keep publishing':'Early stage — focus on quick wins')}
    ${kpiCard('','Organic Traffic', fmt(s.organic_traffic,'n'), null, 'Monthly visits from search')}
    ${kpiCard('','Domain Rating', s.domain_rating||'–', null,
        `${s.quality_refdoms_count||0} quality referring domains`)}
    ${kpiCard('','Page 1 Keywords', s.tk_summary.top_10_count||0, null,
        `${s.tk_summary.top_3_count||0} in top 3 · ${s.tk_summary.total_keywords||0} total ranking`)}
  </div>`;

  // ── Quick wins ───────────────────────────────────────────────────────────
  const qw = s.quick_wins || [];
  html += sectionTitle('Quick Wins — Positions 4–20 with Real Volume');
  html += `<div class="card mb"><table>
    <thead><tr>
      <th>Keyword</th><th class="num">Position</th>
      <th class="num">Volume/mo</th><th class="num">Traffic</th>
      <th class="num">KD</th><th>Page</th><th>Fix</th>
    </tr></thead><tbody>
    ${qw.map(k=>{
      const fix = k.position<=10
        ? 'Add keyword to H1 + meta description + 1 internal link'
        : 'Build a dedicated page or expand existing content';
      return `<tr>
        <td style="font-weight:600">${k.keyword}</td>
        <td class="num">${posBadge(k.position)}</td>
        <td class="num">${fmt(k.volume,'n')}</td>
        <td class="num">${fmt(k.traffic,'n')}</td>
        <td class="num" style="color:var(--muted)">${k.kd}</td>
        <td style="font-size:10px;color:var(--muted)">${k.url||'/'}</td>
        <td style="font-size:10px;color:var(--text-2)">${fix}</td>
      </tr>`;
    }).join('')||'<tr><td colspan="7" style="color:var(--muted)">No quick-win keywords found in positions 4–20</td></tr>'}
    </tbody></table></div>`;

  // ── Full keyword rankings ────────────────────────────────────────────────
  const statusLabel = {
    'top-3':    '<span style="font-size:10px;color:var(--teal);font-weight:600">Top 3</span>',
    'quick-win':'<span style="font-size:10px;color:var(--text-2);font-weight:600">Quick Win</span>',
    'growth':   '<span style="font-size:10px;color:var(--muted)">Growth</span>',
    'low':      '<span style="font-size:10px;color:var(--muted-2)">Low</span>',
  };
  html += sectionTitle('Keyword Rankings — Top 25 by Traffic');
  html += `<div class="card mb"><table>
    <thead><tr>
      <th>Keyword</th><th class="num">Position</th>
      <th class="num">Volume</th><th class="num">Traffic</th>
      <th class="num">CPC</th><th>Status</th>
    </tr></thead><tbody>
    ${(s.keywords||[]).map(kw=>`<tr>
      <td>${kw.keyword}</td>
      <td class="num">${posBadge(kw.position)}</td>
      <td class="num" style="color:var(--muted)">${fmt(kw.volume,'n')}</td>
      <td class="num">${fmt(kw.traffic,'n')}</td>
      <td class="num" style="color:var(--muted)">${kw.cpc ? '$'+kw.cpc : '–'}</td>
      <td>${statusLabel[kw.status]||'–'}</td>
    </tr>`).join('')||'<tr><td colspan="6" style="color:var(--muted)">No keyword data</td></tr>'}
    </tbody></table></div>`;

  // ── GSC queries ─────────────────────────────────────────────────────────
  html += sectionTitle('Search Console — Top Queries (28 days)');
  html += `<div class="grid-2 mb">
    <div class="card">
      <div class="card-h">Top 20 Queries by Clicks</div>
      <table><thead><tr>
        <th>Query</th><th class="num">Clicks</th>
        <th class="num">Impressions</th><th class="num">CTR</th><th class="num">Position</th>
      </tr></thead><tbody>
      ${(s.gsc_queries||[]).map(q=>`<tr>
        <td style="font-size:11px">${q.query}</td>
        <td class="num">${fmt(q.clicks,'n')}</td>
        <td class="num" style="color:var(--muted)">${fmt(q.impressions,'n')}</td>
        <td class="num">${q.ctr}%</td>
        <td class="num">${posBadge(q.position)}</td>
      </tr>`).join('')||'<tr><td colspan="5" style="color:var(--muted)">No GSC data</td></tr>'}
      </tbody></table>
    </div>
    <div class="card">
      <div class="card-h">Top Pages by Clicks</div>
      <table><thead><tr>
        <th>Page</th><th class="num">Clicks</th>
        <th class="num">Impressions</th><th class="num">CTR</th>
      </tr></thead><tbody>
      ${(s.gsc_pages||[]).map(p=>`<tr>
        <td style="font-size:10px;color:var(--text-2)">${p.page||'/'}</td>
        <td class="num">${fmt(p.clicks,'n')}</td>
        <td class="num" style="color:var(--muted)">${fmt(p.impressions,'n')}</td>
        <td class="num">${p.ctr}%</td>
      </tr>`).join('')||'<tr><td colspan="4" style="color:var(--muted)">No GSC page data</td></tr>'}
      </tbody></table>
    </div>
  </div>`;

  // ── Top pages (Ahrefs) ───────────────────────────────────────────────────
  html += sectionTitle('Top Pages — Organic Traffic (Ahrefs)');
  html += `<div class="card mb"><table>
    <thead><tr>
      <th>Page</th><th class="num">Traffic</th>
      <th>Top Keyword</th><th class="num">Position</th>
      <th class="num">Keywords</th><th class="num">Ref Domains</th>
    </tr></thead><tbody>
    ${(s.top_pages||[]).map(p=>`<tr>
      <td style="font-size:11px;color:var(--text-2)">${p.url||'/'}</td>
      <td class="num">${fmt(p.traffic,'n')}</td>
      <td style="font-size:11px">${p.top_kw||'–'}</td>
      <td class="num">${posBadge(p.pos)}</td>
      <td class="num" style="color:var(--muted)">${p.kw_count}</td>
      <td class="num" style="color:var(--muted)">${p.ref_doms}</td>
    </tr>`).join('')||'<tr><td colspan="6" style="color:var(--muted)">No page data</td></tr>'}
    </tbody></table></div>`;

  // ── Backlink profile ────────────────────────────────────────────────────
  html += sectionTitle('Backlink Profile');
  html += `<div class="grid-2 mb">
    <div class="card">
      <div class="card-h">Quality Referring Domains (DR 40+, non-spam)</div>
      <table><thead><tr>
        <th>Domain</th><th class="num">DR</th>
        <th class="num">Dofollow</th><th class="num">Links</th>
      </tr></thead><tbody>
      ${(s.referring_domains||[]).map(d=>`<tr>
        <td style="font-size:11px">${d.domain||'–'}</td>
        <td class="num">${d.domain_rating||'–'}</td>
        <td class="num">${d.dofollow_links||0}</td>
        <td class="num" style="color:var(--muted)">${d.links_to_target||0}</td>
      </tr>`).join('')||'<tr><td colspan="4" style="color:var(--muted)">No quality referring domains found</td></tr>'}
      </tbody></table>
      <p style="font-size:10px;color:var(--muted);margin-top:8px;padding:0 4px">
        ${s.total_refdoms||0} total referring domains · ${s.quality_refdoms_count||0} quality (DR 50+, non-spam)
      </p>
    </div>
    <div class="card">
      <div class="card-h">Recent Backlinks (quality, last 30 days)</div>
      <table><thead><tr>
        <th>From</th><th>To</th><th class="num">DR</th><th>Date</th>
      </tr></thead><tbody>
      ${(s.recent_backlinks||[]).map(b=>`<tr>
        <td style="font-size:10px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:140px">${(b.url_from||'').replace(/https?:\/\//,'')}</td>
        <td style="font-size:10px;color:var(--muted)">${(b.url_to||'').replace('https://www.chasingbetter247.com.au','') || '/'}</td>
        <td class="num">${b.domain_rating_source||'–'}</td>
        <td style="font-size:10px;color:var(--muted)">${(b.first_seen||'').slice(0,10)}</td>
      </tr>`).join('')||'<tr><td colspan="4" style="color:var(--muted)">No recent quality backlinks</td></tr>'}
      </tbody></table>
    </div>
  </div>`;

  // ── SEO recommendation ──────────────────────────────────────────────────
  const topQW = qw[0];
  html += insight('teal', 'This Week\'s SEO Priorities',
    (topQW
      ? `<b>Priority 1 — Quick win:</b> "${topQW.keyword}" sits at #${topQW.position} with ${topQW.volume}/mo searches. Add to H1, meta description, and one internal link on ${topQW.url||'the homepage'} to push to top 3.<br>`
      : '') +
    `<b>Priority 2 — Content:</b> Any keyword in positions 11–20 with volume needs a dedicated landing page, not just a mention.<br>
     <b>Priority 3 — Authority:</b> DR is ${s.domain_rating||'low'}. Focus on earning links from local Perth business directories, fitness publications, and partner gyms. Target 2 new quality links per month.`);

  $('seo-content').innerHTML = html;
}

// ── Render: Google Ads ───────────────────────────────────────────────────────
function renderGAds() {
  const ads = D.google_ads, mal = ads.malaga, ell = ads.ellenbrook, seo = D.seo;
  const kws      = ads.keywords || [];
  const bid      = ads.bidding  || {};
  const weekLabel = ads.week_label || 'Latest week';
  const compSerp  = ads.competitor_serp || [];
  const kwTrack   = ads.keyword_tracking || [];

  // Use CSV totals if json is empty
  const totalSpend  = ads.csv_cost   > 0 ? ads.csv_cost   : ads.spend;
  const totalConv   = ads.csv_conv   > 0 ? ads.csv_conv   : ads.convs;
  const totalClicks = ads.csv_clicks > 0 ? ads.csv_clicks : ads.clicks;
  const blendedCPA  = (totalConv > 0 && totalSpend > 0) ? (totalSpend / totalConv) : ads.cpa;
  const malSpend    = kws.filter(k=>k.locations&&k.locations.includes('Malaga')).reduce((s,k)=>s+k.cost,0);
  const ellSpend    = kws.filter(k=>k.locations&&k.locations.includes('Ellenbrook')).reduce((s,k)=>s+k.cost,0);
  const malConv     = kws.filter(k=>k.locations&&k.locations.includes('Malaga')).reduce((s,k)=>s+k.conv,0);
  const ellConv     = kws.filter(k=>k.locations&&k.locations.includes('Ellenbrook')).reduce((s,k)=>s+k.conv,0);

  // ── KPI Cards ────────────────────────────────────────────────────────────
  let html = `<div class="kpi-grid cols-4 mb">
    ${kpiCard('','Total Spend',fmt(totalSpend,'$2'),ads.spend_chg,`${totalClicks} clicks · ${weekLabel}`)}
    ${kpiCard('','Conversions',fmt(totalConv,'n'),null,`Blended CPA: ${fmt(blendedCPA,'$2')}`,(blendedCPA>50&&blendedCPA>0)?'red':'green')}
    ${kpiCard('','Malaga',fmt(malSpend||mal.spend,'$2'),null,`${malConv||mal.conv||0} conversions`)}
    ${kpiCard('','Ellenbrook',fmt(ellSpend||ell.spend,'$2'),null,`${ellConv||ell.conv||0} conversions`)}
  </div>`;

  // ── Bidding Strategy Analysis ────────────────────────────────────────────
  html += sectionTitle('Bidding Strategy Analysis');

  // Detect strategy from max_cpc values
  const allSmartBid = kws.length > 0 && kws.every(k => !k.cpc || k.cpc <= 0.01);
  const avgCPCAll   = kws.length ? (kws.reduce((s,k)=>s+k.cpc,0)/kws.length).toFixed(2) : 0;

  html += `<div class="grid-3 mb">
    <div class="card">
      <div class="card-h">Current Strategy</div>
      <div style="font-size:1.2rem;font-weight:700;color:var(--teal);margin-bottom:8px">
        ${allSmartBid ? 'Smart Bidding — Maximise Conversions' : 'Manual CPC'}
      </div>
      <div class="stat-row"><span class="stat-label">Avg CPC (actual)</span><span class="stat-val">$${avgCPCAll}</span></div>
      <div class="stat-row"><span class="stat-label">Max CPC set</span><span class="stat-val">${allSmartBid?'$0.01 (automated)':'Manual'}</span></div>
      <div class="stat-row"><span class="stat-label">Blended CPA</span><span class="stat-val ${blendedCPA>50&&blendedCPA>0?'bad':'good'}">${blendedCPA>0?fmt(blendedCPA,'$2'):'No conv data'}</span></div>
      <p style="font-size:11px;color:var(--muted);margin-top:10px">
        ${allSmartBid
          ? 'Max CPC = $0.01 means Google\'s algorithm fully controls bids. This is correct for Smart Bidding. The algorithm adjusts in real-time based on conversion signals.'
          : 'Manual CPC — you control individual keyword bids.'}
      </p>
    </div>
    <div class="card">
      <div class="card-h">Bidding Health Check</div>
      ${(()=>{
        const checks = [];
        const convKws = kws.filter(k=>k.conv>0);
        const wstKws  = kws.filter(k=>k.clicks>=5&&k.conv===0&&k.cost>10);
        const lowVis  = kws.filter(k=>k.top_impr_pct<60&&k.clicks>=5&&k.conv>0);
        checks.push(`<div class="stat-row"><span class="stat-label">Converting keywords</span><span class="stat-val good">${convKws.length} / ${kws.length}</span></div>`);
        checks.push(`<div class="stat-row"><span class="stat-label">Budget wasters</span><span class="stat-val ${wstKws.length>0?'bad':'good'}">${wstKws.length} keywords</span></div>`);
        checks.push(`<div class="stat-row"><span class="stat-label">Low visibility (top% &lt;60)</span><span class="stat-val ${lowVis.length>0?'amber':''}">${lowVis.length} converting kws</span></div>`);
        const brandKwZeroConv = kws.find(k=>k.keyword.toLowerCase().includes('chasing better')&&k.conv===0&&k.clicks>3);
        if(brandKwZeroConv) checks.push(`<div class="stat-row"><span class="stat-label">Brand term not converting</span><span class="stat-val bad">⚠ Check tracking</span></div>`);
        return checks.join('');
      })()}
      <p style="font-size:11px;color:var(--muted);margin-top:10px">
        ${totalConv > 0
          ? `${totalConv} conversions tracked this week at blended $${blendedCPA.toFixed(2)} CPA. Smart Bidding has enough signal to optimise.`
          : 'Low conversion volume — Smart Bidding may be learning. Ensure conversion tracking fires correctly on the membership sign-up page.'}
      </p>
    </div>
    <div class="card">
      <div class="card-h">Recommended Strategy Moves</div>
      <div style="font-size:12px;line-height:1.7">
        <div style="margin-bottom:8px"><b style="color:var(--teal)">1. Set Target CPA = $25</b><br>
        <span style="color:var(--muted)">Winners avg $4–$17 CPA. Cap at $25 to prevent Smart Bidding from over-spending on low-quality clicks while keeping all converters.</span></div>
        <div style="margin-bottom:8px"><b style="color:var(--teal)">2. Separate brand campaign</b><br>
        <span style="color:var(--muted)">Brand terms ("chasing better") should be in their own campaign with higher bid priority. Generic keywords compete for budget unnecessarily.</span></div>
        <div><b style="color:var(--teal)">3. Pause-and-reinvest rule</b><br>
        <span style="color:var(--muted)">Any keyword with 10+ clicks and 0 conversions = pause. Move budget to converting keywords and new strategic additions below.</span></div>
      </div>
    </div>
  </div>`;

  // ── Keyword Performance (Top 10 SEO-aligned) ─────────────────────────────
  const SEO_TARGETS = [
    'malaga gym','gym malaga','gym near me','gyms near me','gym in malaga',
    'best gyms perth','fifo gym membership','gym with sauna and ice bath',
    'reformer pilates','gym with kids club','ellenbrook gym','gyms in ellenbrook',
    'gym with sauna','malaga fitness','24 hour gym','fitness centre','health club',
    'gyms ellenbrook','ellenbrook fitness centre','gym with creche',
  ];
  function locBadge(locs) {
    if (!locs||locs.length===0) return '–';
    if (locs.length===2) return '<span style="font-size:9px;background:#e8f5f4;color:#3FA69A;padding:1px 5px;border-radius:3px">Both</span>';
    return `<span style="font-size:9px;background:#f0f2f5;color:var(--muted);padding:1px 5px;border-radius:3px">${locs[0]}</span>`;
  }
  function recBadge(kw) {
    const cpa = kw.conv>0?kw.cost/kw.conv:0;
    if (kw.conv>0&&cpa<20)           return '<span style="font-size:10px;font-weight:700;color:#00c4b4">Scale</span>';
    if (kw.conv>0)                   return '<span style="font-size:10px;font-weight:600;color:var(--text-2)">Maintain</span>';
    if (kw.clicks>=5&&kw.conv===0&&kw.cost>10) return '<span style="font-size:10px;font-weight:700;color:#ef4444">Pause</span>';
    if (kw.top_impr_pct<60&&kw.clicks>3)       return '<span style="font-size:10px;color:var(--teal)">Raise bid</span>';
    return '<span style="font-size:10px;color:var(--muted-2)">Monitor</span>';
  }
  const seoKws   = kws.filter(k=>SEO_TARGETS.some(t=>k.keyword.toLowerCase().includes(t)||t.includes(k.keyword.toLowerCase()))).slice(0,10);
  const top10Kws = seoKws.length>=5 ? seoKws : kws.slice(0,10);

  html += sectionTitle('Keyword Performance — Top 10 SEO-Aligned · ' + weekLabel);
  html += `<div class="insight neutral mb" style="font-size:12px">
    <b>SEO strategy link:</b> These keywords mirror your organic ranking targets.
    Goal: dominate paid while SEO builds → reduce bids as each keyword hits organic top 3 → reinvest in new keywords still outside top 3.
  </div>`;
  html += `<div class="card mb"><table><thead><tr>
    <th>Keyword</th><th class="num">Clicks</th><th class="num">Impr</th><th class="num">CTR</th>
    <th class="num">Avg CPC</th><th class="num">Spend</th><th class="num">Conv</th>
    <th class="num">CPA</th><th class="num">Top Impr%</th><th>Location</th><th>Action</th>
  </tr></thead><tbody>
  ${top10Kws.map(kw=>{const cpa=kw.conv>0?Math.round(kw.cost/kw.conv*100)/100:0;return`<tr>
    <td style="font-size:12px;max-width:190px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${kw.keyword}</td>
    <td class="num"><b>${kw.clicks}</b></td>
    <td class="num" style="color:var(--muted)">${kw.impressions}</td>
    <td class="num">${kw.ctr}%</td>
    <td class="num" style="color:var(--muted)">$${kw.cpc}</td>
    <td class="num">$${kw.cost}</td>
    <td class="num ${kw.conv>0?'good':''}">${kw.conv||'–'}</td>
    <td class="num ${cpa>50&&cpa>0?'bad':cpa>0?'good':''}">${cpa>0?'$'+cpa:'–'}</td>
    <td class="num ${kw.top_impr_pct<60?'amber':''}">${kw.top_impr_pct}%</td>
    <td>${locBadge(kw.locations)}</td>
    <td>${recBadge(kw)}</td>
  </tr>`}).join('')||'<tr><td colspan="11" style="color:var(--muted)">No keyword data</td></tr>'}
  </tbody></table></div>`;

  // ── Winners vs Wasters ────────────────────────────────────────────────────
  const winnerKws = [...kws].filter(k=>k.conv>0).sort((a,b)=>a.cost/a.conv-b.cost/b.conv).slice(0,8);
  const wasteKws  = [...kws].filter(k=>k.clicks>=5&&k.conv===0&&k.cost>10).sort((a,b)=>b.cost-a.cost).slice(0,8);
  html += `<div class="grid-2 mb">
    <div class="card">
      <div class="card-h" style="color:#00c4b4">Converting Keywords — Scale These</div>
      <table><thead><tr><th>Keyword</th><th class="num">Conv</th><th class="num">CPA</th><th class="num">Spend</th><th class="num">Top%</th></tr></thead><tbody>
      ${winnerKws.length?winnerKws.map(k=>{const cpa=Math.round(k.cost/k.conv*100)/100;return`<tr>
        <td style="font-size:12px">${k.keyword}</td>
        <td class="num good"><b>${k.conv}</b></td>
        <td class="num good">$${cpa}</td>
        <td class="num" style="color:var(--muted)">$${k.cost}</td>
        <td class="num ${k.top_impr_pct<80?'amber':''}">${k.top_impr_pct}%</td>
      </tr>`}).join(''):'<tr><td colspan="5" style="color:var(--muted);font-size:12px">No conversions yet — check conversion tracking</td></tr>'}
      </tbody></table>
    </div>
    <div class="card">
      <div class="card-h" style="color:#ef4444">Budget Wasters — Pause These</div>
      <table><thead><tr><th>Keyword</th><th class="num">Clicks</th><th class="num">Wasted $</th><th class="num">Top%</th></tr></thead><tbody>
      ${wasteKws.length?wasteKws.map(k=>`<tr>
        <td style="font-size:12px">${k.keyword}</td>
        <td class="num">${k.clicks}</td>
        <td class="num bad">$${k.cost}</td>
        <td class="num">${k.top_impr_pct}%</td>
      </tr>`).join(''):'<tr><td colspan="4" style="color:var(--muted);font-size:12px">No wasted spend detected</td></tr>'}
      </tbody></table>
      ${wasteKws.length?`<p style="font-size:10px;color:#ef4444;margin-top:8px;padding:0 4px">
        Total wasted: $${wasteKws.reduce((s,k)=>s+k.cost,0).toFixed(2)} this week →
        pause in Google Ads and add as negative keywords
      </p>`:''}
    </div>
  </div>`;

  // ── Recommended New Keywords ──────────────────────────────────────────────
  html += sectionTitle('Keyword Recommendations — Add to Account');
  html += `<div class="insight teal mb" style="font-size:12px">
    These keywords are not yet in your account (or have near-zero spend) but represent high-value opportunities based on your facilities, organic rankings, and competitor gaps.
  </div>`;
  const newRecs = (bid.new_recs || []);
  html += `<div class="card mb"><table><thead><tr>
    <th>Recommended Keyword</th><th class="num">Est Volume</th>
    <th class="num">Suggested Bid</th><th>Priority</th><th>Why add this</th>
  </tr></thead><tbody>
  ${newRecs.map(r=>`<tr>
    <td style="font-size:12px;font-weight:600">${r.keyword}</td>
    <td class="num" style="color:var(--muted)">${r.vol}/mo</td>
    <td class="num">$${r.bid.replace('$','')}</td>
    <td><span style="font-size:9px;padding:2px 7px;border-radius:3px;font-weight:700;background:${r.priority==='High'?'#e8f5f4':'#f5f5f5'};color:${r.priority==='High'?'#3FA69A':'var(--muted)'}">${r.priority}</span></td>
    <td style="font-size:11px;color:var(--muted);max-width:280px">${r.reason}</td>
  </tr>`).join('')}
  </tbody></table></div>`;

  // ── 3-week trend + campaign breakdown ────────────────────────────────────
  html += sectionTitle('Spend Trend &amp; Campaign Breakdown');
  html += `<div class="grid-2 mb">
    <div class="card">
      <div class="card-h">3-Week Spend &amp; CPA Trend</div>
      <div class="chart-wrap"><canvas id="adsChart"></canvas></div>
    </div>
    <div class="card">
      <div class="card-h">Campaign Breakdown</div>
      <table><thead><tr><th>Campaign</th><th class="num">Spend</th><th class="num">Conv</th><th class="num">CPA</th></tr></thead><tbody>
      ${(()=>{
        if(ads.campaigns&&ads.campaigns.length){
          return ads.campaigns.map(c=>`<tr><td style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px">${c.name}</td><td class="num">${fmt(c.spend,'$2')}</td><td class="num">${c.conv}</td><td class="num ${c.cpa>50?'bad':'good'}">${fmt(c.cpa,'$2')}</td></tr>`).join('');
        }
        const campMap={};
        kws.forEach(k=>{k.campaigns.forEach(camp=>{if(!campMap[camp])campMap[camp]={name:camp,spend:0,conv:0};campMap[camp].spend+=k.cost;campMap[camp].conv+=k.conv;});});
        const camps=Object.values(campMap).sort((a,b)=>b.spend-a.spend);
        return camps.length?camps.map(c=>`<tr><td style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px">${c.name}</td><td class="num">$${c.spend.toFixed(2)}</td><td class="num">${c.conv}</td><td class="num ${c.conv>0&&c.spend/c.conv>50?'bad':c.conv>0?'good':''}">${c.conv>0?'$'+(c.spend/c.conv).toFixed(2):'–'}</td></tr>`).join(''):'<tr><td colspan="4" style="color:var(--muted)">No campaign data</td></tr>';
      })()}
      </tbody></table>
    </div>
  </div>`;

  // ── Competitor context ────────────────────────────────────────────────────
  html += sectionTitle('Competitor Context');
  html += `<div class="grid-2 mb">
    <div class="card">
      <div class="card-h">Organic Ranking Overlap — Who You're Competing Against</div>
      <table><thead><tr><th>Keyword</th><th class="num">Your Org Pos</th><th>Organic Competitors</th></tr></thead><tbody>
      ${kwTrack.filter(k=>k.position).slice(0,6).map(k=>`<tr>
        <td style="font-size:12px">${k.keyword}</td>
        <td class="num">${k.position<=3?'<span style="color:var(--teal);font-weight:700">#'+k.position+'</span>':'#'+k.position}</td>
        <td style="font-size:11px;color:var(--muted)">Revo Fitness, Anytime Fitness, Snap Fitness</td>
      </tr>`).join('')||'<tr><td colspan="3" style="color:var(--muted)">Run pull_apify.py for live SERP data</td></tr>'}
      </tbody></table>
    </div>
    <div class="card">
      <div class="card-h">Competitor Ad Intelligence</div>
      <div style="font-size:12px;line-height:1.7">
        <div class="stat-row"><span class="stat-label">Revo Fitness</span><span class="stat-val">$9.69–$12.69/wk</span></div>
        <div style="font-size:11px;color:var(--muted);margin-bottom:10px">Bidding on: "reformer pilates", "gym perth", "24/7 gym". Weakness: no Kids Hub, no sauna/ice bath.</div>
        <div class="stat-row"><span class="stat-label">Anytime Fitness</span><span class="stat-val">~$15+/wk</span></div>
        <div style="font-size:11px;color:var(--muted);margin-bottom:10px">Bidding on: "gym near me", "24 hour gym". Weakness: expensive, no premium recovery facilities.</div>
        <div class="stat-row"><span class="stat-label">Ryderwear Gym</span><span class="stat-val">Malaga</span></div>
        <div style="font-size:11px;color:var(--muted)">Lifters-focused. Not competing on family, FIFO, or recovery segments — CB247's strongest differentiators.</div>
      </div>
      <div style="font-size:11px;color:var(--teal);margin-top:10px"><b>CB247 gap:</b> No competitor bids on "sauna and ice bath perth", "kids gym malaga", or "fifo gym perth" — add these immediately.</div>
    </div>
  </div>`;

  // ── Audience context ──────────────────────────────────────────────────────
  html += sectionTitle('Audience Context — Who to Target in Google Ads');
  html += `<div class="grid-2 mb">
    <div class="card">
      <div class="card-h">Search Intent Audience Map</div>
      <table><thead><tr><th>Search term</th><th>Intent</th><th>Target audience</th><th>Ad message</th></tr></thead><tbody>
        <tr><td style="font-size:12px">gym near me</td><td style="font-size:11px;color:var(--teal)">High</td><td style="font-size:11px">Local, ready to join</td><td style="font-size:11px;color:var(--muted)">$11.95/wk, no lock-in. Join today.</td></tr>
        <tr><td style="font-size:12px">malaga gym / gym malaga</td><td style="font-size:11px;color:var(--teal)">High</td><td style="font-size:11px">Malaga residents</td><td style="font-size:11px;color:var(--muted)">Perth's best-reviewed gym on Marshall Rd.</td></tr>
        <tr><td style="font-size:12px">gym with kids club</td><td style="font-size:11px;color:var(--text-2)">Medium</td><td style="font-size:11px">Parents 28–45</td><td style="font-size:11px;color:var(--muted)">Train while kids play. Kids Hub included.</td></tr>
        <tr><td style="font-size:12px">gym with sauna and ice bath</td><td style="font-size:11px;color:var(--teal)">High</td><td style="font-size:11px">Recovery seekers 30–55</td><td style="font-size:11px;color:var(--muted)">The only Perth gym with sauna + ice bath.</td></tr>
        <tr><td style="font-size:12px">fifo gym membership</td><td style="font-size:11px;color:var(--teal)">High</td><td style="font-size:11px">FIFO workers WA</td><td style="font-size:11px;color:var(--muted)">Freeze your membership any time. No fuss.</td></tr>
        <tr><td style="font-size:12px">reformer pilates ellenbrook</td><td style="font-size:11px;color:var(--text-2)">Medium</td><td style="font-size:11px">Women 25–45</td><td style="font-size:11px;color:var(--muted)">24/7 reformer pilates. Included in membership.</td></tr>
      </tbody></table>
    </div>
    <div class="card">
      <div class="card-h">Audience Targeting Recommendations</div>
      <div style="font-size:12px;line-height:1.8">
        <div style="margin-bottom:10px">
          <b style="color:var(--teal)">Location radius</b><br>
          <span style="color:var(--muted)">Malaga: 8km radius (covers Dianella, Morley, Mirrabooka, Beechboro, Noranda). Ellenbrook: 10km (covers Aveley, Brabham, Swan Valley, Henley Brook).</span>
        </div>
        <div style="margin-bottom:10px">
          <b style="color:var(--teal)">Ad scheduling</b><br>
          <span style="color:var(--muted)">Peak search: Mon–Fri 6–9am and 5–8pm. Weekends 7–11am. Reduce bids overnight — gym searchers rarely convert after 9pm.</span>
        </div>
        <div style="margin-bottom:10px">
          <b style="color:var(--teal)">Device bidding</b><br>
          <span style="color:var(--muted)">82% of website sessions are mobile (GA4 data). Set mobile bid adjustment +20% — most local gym searches happen on phone.</span>
        </div>
        <div>
          <b style="color:var(--teal)">Audience layering (RLSA)</b><br>
          <span style="color:var(--muted)">Add website visitor audiences with +30% bid boost — people who visited pricing or contact page are ready to convert.</span>
        </div>
      </div>
    </div>
  </div>`;

  // ── This Week's Google Ads Priorities ────────────────────────────────────
  const topWinner    = kws.find(k => k.conv > 0);
  const topWaster    = kws.find(k => k.clicks >= 5 && k.conv === 0 && k.cost > 10);
  const highCTRNoConv = kws.find(k => k.ctr >= 20 && k.conv === 0 && k.clicks >= 3);
  const organicTop3  = (D.seo && D.seo.keywords || []).filter(k => k.position <= 3).map(k => k.keyword.toLowerCase());
  const overlapKws   = kws.filter(k => organicTop3.some(ok => ok.includes(k.keyword.toLowerCase()) || k.keyword.toLowerCase().includes(ok)));

  const priorities = [];
  if (topWinner) priorities.push(`<b>1. Scale winners:</b> "${topWinner.keyword}" converting at $${(topWinner.cost/topWinner.conv).toFixed(2)} CPA — well below $25 target. Increase campaign budget or set Target CPA = $25 to let Google spend more on this.`);
  if (topWaster) priorities.push(`<b>${priorities.length+1}. Pause wasted spend:</b> "${topWaster.keyword}" spent $${topWaster.cost} with ${topWaster.clicks} clicks and zero conversions. Pause now and reallocate to winning keywords.`);
  if (highCTRNoConv) priorities.push(`<b>${priorities.length+1}. Fix landing page:</b> "${highCTRNoConv.keyword}" has ${highCTRNoConv.ctr}% CTR (people are clicking) but 0 conversions. The landing page CTA is broken or the page doesn't match search intent.`);
  if (overlapKws.length) priorities.push(`<b>${priorities.length+1}. Organic overlap:</b> "${overlapKws[0].keyword}" already ranks top 3 organically — pause the paid ad, watch organic clicks for 2 weeks, reinvest budget.`);
  priorities.push(`<b>${priorities.length+1}. Add 3 new keywords this week:</b> "kids gym malaga", "sauna and ice bath perth", "fifo gym perth" — all uncontested by competitors, aligned with CB247's unique facilities.`);
  if (!allSmartBid) priorities.push(`<b>${priorities.length+1}. Switch to Smart Bidding:</b> Current manual CPC setup. Upgrade to Maximise Conversions with Target CPA = $25 to let Google's algorithm optimise in real-time.`);

  html += insight('teal', "This Week's Google Ads Priorities",
    priorities.join('<br><br>'));

  $('gads-content').innerHTML = html;

  setTimeout(()=>{
    if($('adsChart') && ads.trend_labels && ads.trend_labels.length) {
      new Chart($('adsChart'),{type:'bar',data:{labels:ads.trend_labels,datasets:[{label:'Spend ($)',data:ads.trend_spend,backgroundColor:'#3FA69A',borderRadius:4,yAxisID:'y'},{label:'CPA ($)',data:ads.trend_cpa,type:'line',borderColor:'#ef4444',backgroundColor:'transparent',borderWidth:2,pointRadius:4,pointBackgroundColor:'#ef4444',tension:.3,yAxisID:'y2'}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'top',labels:{usePointStyle:true,font:{size:10}}}},scales:{x:{grid:{display:false},ticks:{font:{size:10}}},y:{beginAtZero:true,position:'left',ticks:{callback:v=>'$'+v,font:{size:10}},grid:{color:'#f0f0f0'}},y2:{beginAtZero:true,position:'right',ticks:{callback:v=>'$'+v,font:{size:10}},grid:{display:false}}}}});
    }
  },100);
}

// ── Render: Organic Social ───────────────────────────────────────────────────
function renderOrgSocial() {
  const os  = D.organic_social;
  const m   = os.metricool || {};
  const fb  = m.fb || {};
  const ig  = m.ig || {};
  const gbp = m.gbp || {};
  const hashtags = os.trending_hashtags || [];
  const week = m.week || '25–31 May 2026';
  const comps = os.competitors || {};

  function chg(v, suffix='%') {
    if (v == null) return '';
    const col = v > 0 ? 'color:#00c4b4' : 'color:#ef4444';
    return `<span style="font-size:10px;font-weight:600;${col}">${v > 0 ? '▲' : '▼'}${Math.abs(v)}${suffix} WoW</span>`;
  }
  function rankBadge(r) {
    if (!r) return '';
    if (r.includes('Above')) return '<span style="font-size:9px;background:#e8f5f4;color:#00c4b4;padding:1px 5px;border-radius:3px;font-weight:700">Above avg</span>';
    if (r.includes('Below')) return '<span style="font-size:9px;background:#fee2e2;color:#ef4444;padding:1px 5px;border-radius:3px;font-weight:700">Below avg</span>';
    return '<span style="font-size:9px;background:#f0f2f5;color:var(--muted);padding:1px 5px;border-radius:3px">Average</span>';
  }
  function tierBadge(t) {
    if (t==='star')    return '<span style="font-size:9px;background:#e8f5f4;color:#00c4b4;padding:2px 7px;border-radius:3px;font-weight:700">⭐ Star</span>';
    if (t==='good')    return '<span style="font-size:9px;background:#fff8e1;color:#d97706;padding:2px 7px;border-radius:3px;font-weight:700">Good</span>';
    if (t==='poor')    return '<span style="font-size:9px;background:#fee2e2;color:#ef4444;padding:2px 7px;border-radius:3px;font-weight:700">Poor</span>';
    return '<span style="font-size:9px;background:#f0f2f5;color:var(--muted);padding:2px 7px;border-radius:3px">Average</span>';
  }

  let html = '';

  // ── KPI cards — week overview ─────────────────────────────────────────────
  html += `<div class="kpi-grid cols-4 mb">
    ${kpiCard('','IG Followers',fmt(ig.followers||0,'n'),ig.followers_chg,'Net +'+( ig.followers_balance||0)+' this week')}
    ${kpiCard('','FB Followers',fmt(fb.followers||0,'n'),fb.followers_chg,'Net +'+(fb.community_acquired||0)+' acquired')}
    ${kpiCard('','IG Avg Reach/Day',fmt(ig.avg_reach_per_day||0,'n'),ig.avg_reach_per_day_chg,'Views: '+(ig.views?(ig.views/1000).toFixed(0)+'K':'-'),'green')}
    ${kpiCard('','GBP Actions',fmt(gbp.total_actions||0,'n'),gbp.actions_chg,'Website+Phone+Directions','red')}
  </div>`;

  // ── Critical observations ─────────────────────────────────────────────────
  html += sectionTitle('Key Observations — ' + week);
  html += `<div class="grid-2 mb">
    <div class="insight red">
      <div class="insight-label" style="color:#ef4444">Facebook Organic — Critical Issue</div>
      <b>FB interactions collapsed −90% WoW</b> (6 total interactions from 32,710 impressions).
      That's a 0.02% engagement rate on 5,280 followers. Root cause: <b>only 1 post published</b> this week (down 75%),
      and organic reach per post averages 183 — less than 3.5% of the follower base.
      Facebook organic is not working. Repoint effort to Instagram and Stories.
      <br><br><b>Competitor gap:</b> CB247 has 5,280 FB followers. Revo: 49,560 (9.4× more). World Gym: 51,590.
      This is an existential gap — FB will not close it. Redirect budget and content to Instagram.
    </div>
    <div class="insight teal">
      <div class="insight-label">Instagram — Reels Are the Growth Engine</div>
      <b>5 Reels published this week drove 93 likes, +45% vs prior</b> — far outperforming the 1 post published (9 interactions total).
      Stories hit 54,680 impressions (+93.9% WoW) with avg reach per story of 804.
      <b>The problem:</b> avg reel watch time is 4–8 seconds. Industry benchmark for good retention = 15s+.
      The hook in the first 2 seconds is not holding attention.
      <br><br><b>Action:</b> Lead every reel with a pattern interrupt — a bold on-screen text hook within 0.5 seconds.
      "Would you do this for $11.95/week?" beats a slow gym walkthrough open every time.
    </div>
    <div class="insight red">
      <div class="insight-label">Google Business Profile — All Signals Down</div>
      <b>Website clicks −49.7%</b>, Google Search reach −42.8%, total actions −33.1%.
      This is a broad signal drop, not a single metric anomaly. Likely causes:
      (1) GBP post cadence dropped, (2) no new photos uploaded this week, (3) competitor listings moving up.
      <b>3 reviews received this week</b> (4.33 star avg). One negative review mentions "issues with the gym" — reply publicly and professionally within 24h.
      <br><br><b>Fix this week:</b> Post 1 GBP update, add 3 interior/facility photos, respond to all 3 reviews.
    </div>
    <div class="insight amber">
      <div class="insight-label">Content Volume — Organic Reach Is a Volume Game</div>
      CB247 published <b>1 post + 5 Reels this week</b>. Revo publishes 7 posts + 14 Reels/week.
      The organic algorithm rewards consistency: accounts posting 7+ Reels/week receive up to 3× more
      distribution than accounts posting 1–2. At 5 Reels/week CB247 is close, but posting cadence
      dropped vs prior week (−66.7% posts, same Reels).
      <br><br><b>Fix:</b> Maintain 5–7 Reels/week minimum. Batch-film on Sundays — 1 filming session
      can produce 4–6 Reels (ice bath, sauna, class snippet, facility tour, member moment, hook clip).
    </div>
  </div>`;

  // ── Instagram breakdown ───────────────────────────────────────────────────
  html += sectionTitle('Instagram Organic — @chasingbetter247');
  html += `<div class="grid-3 mb">
    <div class="card">
      <div class="card-h">Posts</div>
      <div class="stat-row"><span class="stat-label">Published</span><span class="stat-val">${ig.posts_published||0} <span style="font-size:10px;color:#ef4444">▼66.7% WoW</span></span></div>
      <div class="stat-row"><span class="stat-label">Avg reach/post</span><span class="stat-val">855</span></div>
      <div class="stat-row"><span class="stat-label">Engagement rate</span><span class="stat-val">${ig.post_engagement||'–'}% ${chg(ig.post_engagement_chg,'%')}</span></div>
      <div class="stat-row"><span class="stat-label">Interactions</span><span class="stat-val bad">9 total</span></div>
    </div>
    <div class="card">
      <div class="card-h">Reels</div>
      <div class="stat-row"><span class="stat-label">Published</span><span class="stat-val">${ig.reels_published||0} ${chg(ig.reels_chg,'%')}</span></div>
      <div class="stat-row"><span class="stat-label">Avg reach/reel</span><span class="stat-val">${fmt(ig.reel_avg_reach||0,'n')}</span></div>
      <div class="stat-row"><span class="stat-label">Likes</span><span class="stat-val">${ig.reel_likes||0} ${chg(ig.reel_likes_chg,'%')}</span></div>
      <div class="stat-row"><span class="stat-label">Avg watch time</span><span class="stat-val bad">4–8 sec ⚠</span></div>
    </div>
    <div class="card">
      <div class="card-h">Stories</div>
      <div class="stat-row"><span class="stat-label">Published</span><span class="stat-val">${ig.stories_published||0} ${chg(50,'%')}</span></div>
      <div class="stat-row"><span class="stat-label">Total impressions</span><span class="stat-val">${fmt(ig.stories_impressions||0,'n')} ${chg(ig.stories_impressions_chg,'%')}</span></div>
      <div class="stat-row"><span class="stat-label">Avg reach/story</span><span class="stat-val">${fmt(ig.story_avg_reach||0,'n')}</span></div>
      <div class="stat-row"><span class="stat-label">View rate</span><span class="stat-val">Stories = highest-reach format this week</span></div>
    </div>
  </div>`;

  // Top reels table
  html += `<div class="card mb">
    <div class="card-h">Top Reels — by Likes (Instagram)</div>
    <table><thead><tr>
      <th>Content</th><th class="num">Views</th><th class="num">Reach</th>
      <th class="num">Likes</th><th class="num">Saves</th><th class="num">Shares</th>
      <th class="num">Avg Watch</th><th class="num">Engagement</th>
    </tr></thead><tbody>
    ${(ig.top_reels||[]).map(r=>`<tr>
      <td style="font-size:11px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${r.text}</td>
      <td class="num">${fmt(r.views,'n')}</td>
      <td class="num" style="color:var(--muted)">${fmt(r.reach,'n')}</td>
      <td class="num ${r.likes>=20?'good':''}">${r.likes}</td>
      <td class="num">${r.saves||0}</td>
      <td class="num">${r.shares||0}</td>
      <td class="num ${parseInt(r.avg_watch)<6?'bad':''}">${r.avg_watch}</td>
      <td class="num">${r.engagement}%</td>
    </tr>`).join('')}
    </tbody></table>
    <p style="font-size:11px;color:var(--muted);margin-top:8px;padding:0 4px">
      <b>Pattern:</b> All top reels are reposts from other creators — 0 original CB247 branded reels in the top 5.
      Reposts get the views but don't build brand equity or drive direct signups. Create at least 2 original reels/week:
      member story, facility showcase (sauna/ice bath), or staff walkthrough. These should carry the "$11.95/week" CTA.
    </p>
  </div>`;

  // ── Instagram competitor benchmark ────────────────────────────────────────
  html += sectionTitle('Instagram Competitor Benchmark');
  html += `<div class="card mb"><table><thead><tr>
    <th>Account</th><th class="num">Followers</th><th class="num">Posts/wk</th>
    <th class="num">Reels/wk</th><th class="num">Engagement</th><th>Gap to CB247</th>
  </tr></thead><tbody>
  <tr style="background:#f0f9f7">
    <td style="font-weight:700;color:var(--teal)">@chasingbetter247</td>
    <td class="num good"><b>${fmt(ig.followers||0,'n')}</b></td>
    <td class="num">${ig.posts_published||0}</td>
    <td class="num">${ig.reels_published||0}</td>
    <td class="num">${ig.reel_engagement||'–'}%</td>
    <td style="font-size:11px;color:var(--teal)">Baseline</td>
  </tr>
  ${(ig.competitors||[]).map(c=>{const gap=c.followers-(ig.followers||0);return`<tr>
    <td style="font-size:12px">@${c.handle}</td>
    <td class="num ${gap>0?'bad':''}">${fmt(c.followers,'n')}</td>
    <td class="num">${c.posts}</td>
    <td class="num">${c.reels}</td>
    <td class="num">${c.engagement}%</td>
    <td style="font-size:11px;${gap>0?'color:#ef4444':'color:var(--teal)'}">
      ${gap>0?'+'+(gap/1000).toFixed(1)+'K ahead':'ahead by '+(Math.abs(gap)/1000).toFixed(1)+'K'}
    </td>
  </tr>`}).join('')}
  </tbody></table>
  <p style="font-size:11px;color:#ef4444;margin-top:10px;padding:0 4px;font-weight:600">
    Revo Fitness (106K) is 11.8× larger on Instagram. They post 7 posts + 14 reels/week.
    CB247 needs to increase reel frequency to 7+/week and create original branded content to close this gap.
    At current growth rate of +9 followers/week, closing to within 50K of Revo would take 10+ years.
    The only shortcut is viral reels — facility content (sauna, ice bath) has that potential.
  </p></div>`;

  // ── Facebook competitor benchmark ─────────────────────────────────────────
  html += sectionTitle('Facebook Competitor Benchmark');
  html += `<div class="card mb"><table><thead><tr>
    <th>Page</th><th class="num">Followers</th><th class="num">Posts/wk</th>
    <th class="num">Engagement</th><th>Interpretation</th>
  </tr></thead><tbody>
  <tr style="background:#f0f9f7">
    <td style="font-weight:700;color:var(--teal)">CB247</td>
    <td class="num"><b>${fmt(fb.followers||0,'n')}</b></td>
    <td class="num">${fb.posts_published||0}</td>
    <td class="num">${fb.engagement_rate||'–'}%</td>
    <td style="font-size:11px;color:var(--teal)">Baseline</td>
  </tr>
  ${(fb.competitors||[]).map(c=>`<tr>
    <td style="font-size:12px">${c.name}</td>
    <td class="num bad">${fmt(c.followers,'n')}</td>
    <td class="num">${c.posts}</td>
    <td class="num">${c.engagement}%</td>
    <td style="font-size:11px;color:var(--muted)">${(c.followers/1000).toFixed(0)}K followers — ${c.followers>fb.followers?Math.round(c.followers/fb.followers)+'× larger':'smaller'}</td>
  </tr>`).join('')}
  </tbody></table>
  <p style="font-size:11px;color:var(--muted);margin-top:8px;padding:0 4px">
    <b>Recommendation:</b> Stop treating Facebook as a primary organic channel. Post 1–2× per week (vs 35 this week) for SEO and GBP signals only.
    Redirect Facebook content effort to Instagram Reels. Paid Facebook ads remain valid for FIFO and family targeting.
  </p></div>`;

  // ── Audience from geo data ────────────────────────────────────────────────
  html += sectionTitle('Audience Profile — Where Your Followers Are');
  html += `<div class="grid-2 mb">
    <div class="card">
      <div class="card-h">Instagram Audience — Top Cities</div>
      ${(ig.geo_top_cities||[]).map(g=>`
        <div class="stat-row"><span class="stat-label">${g.city}</span><span class="stat-val">${g.pct}%</span></div>
        <div style="background:#f0f2f5;border-radius:3px;height:5px;margin-bottom:8px">
          <div style="background:var(--teal);width:${Math.min(g.pct*1.7,100)}%;height:100%;border-radius:3px"></div>
        </div>`).join('')}
      <p style="font-size:11px;color:var(--muted);margin-top:8px">
        57.7% Perth + 6.8% Ellenbrook = strong local concentration.
        Aveley (4.5%) and Caversham (1.75%) confirm Ellenbrook catchment resonance.
        Content should be hyper-local: suburb name-drop, local events, WA-specific hooks.
      </p>
    </div>
    <div class="card">
      <div class="card-h">Audience Targeting Recommendations</div>
      <div style="font-size:12px;line-height:1.8">
        <div style="margin-bottom:10px"><b style="color:var(--teal)">Reels target:</b>
        <span style="color:var(--muted)">Women 25–40, Perth metro. Interest: gym, pilates, wellness. The top reel formats (partner workouts, fitness challenges) index highest with this demographic.</span></div>
        <div style="margin-bottom:10px"><b style="color:var(--teal)">Stories target:</b>
        <span style="color:var(--muted)">Existing followers — stories reach 804 avg. Use for time-sensitive offers, class schedule reminders, behind-the-scenes. High tap-forward rate = keep stories under 7 frames.</span></div>
        <div style="margin-bottom:10px"><b style="color:var(--teal)">Facebook paid (only):</b>
        <span style="color:var(--muted)">FIFO workers (Perth postcode + mining interest), families 30–45, Malaga/Ellenbrook radius. Organic FB content is not worth the effort at current follower count.</span></div>
        <div><b style="color:var(--teal)">GBP:</b>
        <span style="color:var(--muted)">Post Tuesday 7am — captures Monday gym-resolution searches. Use: class highlights, member milestones, local suburb mentions. Each GBP post = free SEO signal for "gym malaga" local pack.</span></div>
      </div>
    </div>
  </div>`;

  // ── Trending hashtags ─────────────────────────────────────────────────────
  html += sectionTitle('Trending Fitness Hashtags — Use in Reels This Week');
  html += `<div class="card mb">
    <div style="display:flex;flex-wrap:wrap;gap:8px;padding-top:4px;margin-bottom:12px">
      ${hashtags.map(h=>`<span style="background:#e8f5f4;color:#3FA69A;border-radius:99px;padding:4px 12px;font-size:12px;font-weight:600">#${h.hashtag} <span style="font-weight:400;color:var(--muted);font-size:10px">${h.count}</span></span>`).join('')||'<span style="color:var(--muted)">Run pull_apify.py for hashtag data</span>'}
    </div>
    <div style="font-size:11px;color:var(--muted)">
      <b>CB247-specific stack for this week's reels:</b>
      #gymtok #coldplunge #icebath (trending) + #malaggym #ellenbrookgym #gymperth (local SEO) + #chasingbetter247 #alwaysbetter (brand).
      Avoid generic #fitness #gym — too broad, won't surface to local audience.
    </div>
  </div>`;

  // ── This week's social priorities ────────────────────────────────────────
  html += insight('teal', "This Week's Organic Social Priorities",
    `<b>1. Publish 2 original branded Reels:</b> All top organic reels this week were reposts from other creators — 0 original CB247 branded content in the top 5. Priority: (1) ice bath/sauna reel with hook "The only gym in Malaga with THIS" and (2) a real member story with suburb name + "$11.95/week changed my routine." Original branded reels build equity; reposts do not.<br><br>
     <b>2. Fix the hook — avg watch time is 4–8 seconds (benchmark: 15s+):</b> Lead every Reel with a bold on-screen text hook in the first 0.5 seconds before any music or movement. Example: "Would you do THIS for $11.95/week?" Pattern interrupts in the first frame = longer retention = more distribution.<br><br>
     <b>3. Stop treating Facebook as a primary organic channel:</b> 6 interactions from 32,710 impressions = 0.02% rate. Post 1–2× per week max (for GBP signal only). Redirect all content effort to Instagram Reels. Facebook organic is not recoverable without significant paid support.<br><br>
     <b>4. Respond to all 3 GBP reviews within 24h:</b> Including the 1 critical review — public replies signal to Google the listing is actively managed and directly affect local pack ranking. Template for critical: acknowledge, apologise, invite them to resolve offline. Never argue.<br><br>
     <b>5. Post 1 GBP update today:</b> Winter Push is live — post "Perth winters made for the gym ❄️ Join from $11.95/week" to both GBP profiles with a warm facility photo (sauna, heated gym floor, or ice bath contrast). Each GBP post = free local SEO signal.`);

  $('orgsocial-content').innerHTML = html;
}

// ── Render: Meta Ads ─────────────────────────────────────────────────────────
function renderMeta() {
  const meta = (D.organic_social && D.organic_social.meta) || {};
  const malC  = meta.malaga_cur  || {};
  const malP  = meta.malaga_prev || {};
  const ellC  = meta.ell_cur     || {};
  const ads   = meta.active      || [];
  const week  = meta.week_label  || '25–31 May 2026';

  function rankBadge(r) {
    if (!r) return '';
    if (r.includes('Above')) return '<span style="font-size:9px;background:#e8f5f4;color:#00c4b4;padding:1px 5px;border-radius:3px;font-weight:700">Above avg</span>';
    if (r.includes('Below')) return '<span style="font-size:9px;background:#fee2e2;color:#ef4444;padding:1px 5px;border-radius:3px;font-weight:700">Below avg</span>';
    return '<span style="font-size:9px;background:#f0f2f5;color:var(--muted);padding:1px 5px;border-radius:3px">Average</span>';
  }
  function tierBadge(t) {
    if (t==='star') return '<span style="font-size:9px;background:#e8f5f4;color:#00c4b4;padding:2px 7px;border-radius:3px;font-weight:700">⭐ Star</span>';
    if (t==='good') return '<span style="font-size:9px;background:#fff8e1;color:#d97706;padding:2px 7px;border-radius:3px;font-weight:700">Good</span>';
    if (t==='poor') return '<span style="font-size:9px;background:#fee2e2;color:#ef4444;padding:2px 7px;border-radius:3px;font-weight:700">Poor</span>';
    return '<span style="font-size:9px;background:#f0f2f5;color:var(--muted);padding:2px 7px;border-radius:3px">Average</span>';
  }

  // Derived totals
  const totalSpend   = (malC.spend||0) + (ellC.spend||0);
  const totalResults = (malC.results||0) + (ellC.results||0);
  const totalReach   = (malC.reach||0) + (ellC.reach||0);
  const blendedCPR   = totalResults > 0 ? (totalSpend / totalResults).toFixed(2) : '–';
  const prevSpend    = (malP.spend||0);
  const spendChg     = prevSpend > 0 ? ((totalSpend - prevSpend) / prevSpend * 100).toFixed(1) : null;

  let html = '';

  // ── KPI cards ──────────────────────────────────────────────────────────────
  html += `<div class="kpi-grid cols-4 mb">
    ${kpiCard('','Total Spend','$'+totalSpend.toFixed(2),spendChg?parseFloat(spendChg):null,'Both locations this week')}
    ${kpiCard('','Total Results',totalResults||'–',null,'Link clicks / leads across all ads')}
    ${kpiCard('','Malaga CPR',malC.cpr?'$'+malC.cpr:'–',null,'Prev: $'+(malP.cpr||'–')+' — '+(malC.cpr&&malP.cpr?(malC.cpr>malP.cpr?'⚠ worse this week':'improved'):''),malC.cpr&&malP.cpr?(malC.cpr>malP.cpr?'red':'green'):'')}
    ${kpiCard('','Ellenbrook CPR',ellC.cpr?'$'+ellC.cpr:'–',null,ellC.ctr+'% CTR · $'+ellC.cpm+' CPM','green')}
  </div>`;

  // ── Key observations ────────────────────────────────────────────────────────
  html += sectionTitle('Key Observations — ' + week);
  html += `<div class="grid-2 mb">
    <div class="insight red">
      <div class="insight-label">Malaga Efficiency Declining — CPR Up 44% WoW</div>
      Malaga CPR rose from <b>$0.27 → $0.39 (+44%)</b> week-on-week with the <b>same $281 spend</b>.
      Clicks dropped −29.5% (912 → 643). This means the same budget is generating fewer results at a higher cost.
      Root cause: ad fatigue on underperforming creatives. The Pilates Reel ($122 spend) drives the most impressions
      but scores <b>Average across all three quality signals</b> — it's not converting.
      <br><br><b>Action:</b> Pause lowest-performing ads. Shift budget to the proven creative immediately.
    </div>
    <div class="insight teal">
      <div class="insight-label">Star Creative — "Deep Heat. Deep Recovery" Must Be Scaled</div>
      <b>"Deep heat. Deep recovery"</b> (sauna + massage post) is the <b>only ad with dual Above average signals</b>:
      Above average engagement ranking AND Above average conversion rate ranking. No other active ad achieves this.
      This recovery/wellness angle maps directly to CB247's sauna + ice bath differentiation — the strongest
      competitive moat in the Malaga market.
      <br><br><b>Action:</b> Scale budget from ~$49 → $100 this week. Create a matching organic Reel
      using the same visual and messaging angle. Test a second variation: "Ice bath. Then sauna. $11.95/week."
    </div>
    <div class="insight amber">
      <div class="insight-label">Ellenbrook — Fewer Ads, Better Efficiency</div>
      Ellenbrook is running fewer ads than Malaga but with stronger CPR and CTR signals.
      The location is underinvested — budget concentration in Malaga means Ellenbrook reach
      is lower than its member growth potential justifies.
      <br><br><b>Action:</b> Increase Ellenbrook daily budget by $5–10/day. Test 1 Ellenbrook-specific
      creative: "Your neighbourhood gym, 24/7" — hyperlocal messaging performs better in suburban markets.
    </div>
    <div class="insight amber">
      <div class="insight-label">Ad Quality Signals — Most Ads Are Average, Not Outstanding</div>
      Across all active ads, only "Deep heat. Deep recovery" scores Above average on 2+ signals.
      The remaining ads score Average or Below on at least one quality dimension.
      Meta's algorithm distributes budget toward higher-quality ads — poor-scoring ads get progressively
      worse delivery, compounding cost inefficiency over time.
      <br><br><b>Action:</b> Retire any ad with a Below average signal. Refresh creative every 3–4 weeks
      — Meta quality signals degrade with frequency cap and audience saturation.
    </div>
  </div>`;

  // ── WoW comparison — Malaga ─────────────────────────────────────────────────
  html += sectionTitle('Malaga — Week-on-Week Comparison');
  html += `<div class="card mb"><table><thead><tr>
    <th>Metric</th><th class="num">This Week (${week})</th><th class="num">Prior Week</th><th class="num">Change</th>
  </tr></thead><tbody>
    <tr><td>Spend</td><td class="num">$${(malC.spend||0).toFixed(2)}</td><td class="num">$${(malP.spend||0).toFixed(2)}</td>
      <td class="num ${Math.abs((malC.spend||0)-(malP.spend||0))<1?'':'flat'}">${malP.spend?((malC.spend-malP.spend)/malP.spend*100).toFixed(1)+'%':'–'}</td></tr>
    <tr><td>Clicks</td><td class="num">${fmt(malC.clicks||0,'n')}</td><td class="num">${fmt(malP.clicks||0,'n')}</td>
      <td class="num ${malC.clicks<malP.clicks?'bad':'good'}">${malP.clicks?((malC.clicks-malP.clicks)/malP.clicks*100).toFixed(1)+'%':'–'}</td></tr>
    <tr><td>Reach</td><td class="num">${fmt(malC.reach||0,'n')}</td><td class="num">${fmt(malP.reach||0,'n')}</td>
      <td class="num">${malP.reach?((malC.reach-malP.reach)/malP.reach*100).toFixed(1)+'%':'–'}</td></tr>
    <tr><td>Results</td><td class="num">${malC.results||'–'}</td><td class="num">${malP.results||'–'}</td><td class="num">–</td></tr>
    <tr><td>Cost per Result (CPR)</td>
      <td class="num ${malC.cpr>malP.cpr?'bad':'good'}">$${malC.cpr||'–'}</td>
      <td class="num">$${malP.cpr||'–'}</td>
      <td class="num ${malC.cpr>malP.cpr?'bad':'good'}">${malC.cpr&&malP.cpr?((malC.cpr-malP.cpr)/malP.cpr*100).toFixed(1)+'%':'–'}</td></tr>
    <tr><td>CTR</td><td class="num">${malC.ctr||'–'}%</td><td class="num">–</td><td class="num">–</td></tr>
    <tr><td>CPM</td><td class="num">$${malC.cpm||'–'}</td><td class="num">–</td><td class="num">–</td></tr>
  </tbody></table></div>`;

  // ── Ad performance table ────────────────────────────────────────────────────
  html += sectionTitle('Active Ads — Quality Ranking & Performance · ' + week);
  html += `<div class="card mb" style="overflow-x:auto"><table><thead><tr>
    <th>Ad Creative</th><th>Location</th>
    <th class="num">Spend</th><th class="num">Reach</th>
    <th class="num">Impressions</th><th class="num">CTR</th><th class="num">CPM</th>
    <th class="num">Results</th><th class="num">CPR</th>
    <th>Quality</th><th>Engagement</th><th>Conv Rate</th><th>Tier</th>
  </tr></thead><tbody>
  ${ads.map(a=>{
    const cpr = a.results>0 ? (a.spend/a.results).toFixed(2) : '–';
    const rowStyle = a.tier==='star' ? 'style="background:#f0fdf4"' : a.tier==='poor' ? 'style="background:#fff5f5"' : '';
    return `<tr ${rowStyle}>
      <td style="font-size:11px;max-width:200px;word-break:break-word">${a.ad_name}</td>
      <td><span style="font-size:9px;background:#f0f2f5;color:var(--muted);padding:1px 5px;border-radius:3px">${a.location}</span></td>
      <td class="num">$${a.spend.toFixed(2)}</td>
      <td class="num">${fmt(a.reach,'n')}</td>
      <td class="num">${fmt(a.impressions||0,'n')}</td>
      <td class="num ${a.ctr>=3?'good':a.ctr<1?'bad':''}">${a.ctr}%</td>
      <td class="num ${a.cpm>15?'bad':''}">${a.cpm>0?'$'+a.cpm:'–'}</td>
      <td class="num ${a.results>0?'good':''}">${a.results||'–'}</td>
      <td class="num ${a.results>0&&(a.spend/a.results)<0.5?'good':''}">${cpr!=='–'?'$'+cpr:'–'}</td>
      <td>${rankBadge(a.quality)}</td>
      <td>${rankBadge(a.eng_rank)}</td>
      <td>${rankBadge(a.conv_rank)}</td>
      <td>${tierBadge(a.tier)}</td>
    </tr>`;
  }).join('')||'<tr><td colspan="13" style="color:var(--muted);padding:16px">No active ads — upload Meta CSV files to load ad data.</td></tr>'}
  </tbody></table>
  <div style="font-size:10px;color:var(--muted);margin-top:8px;padding:0 4px">
    <b>Tier logic:</b> ⭐ Star = ≥2 Above average ranking signals. Good = 1 Above, no Below. Poor = any Below average signal. Average = remainder.
    Meta's algorithm gives better placement and lower CPMs to higher-tier ads — poor-tier ads erode over time.
  </div></div>`;

  // ── Location summary cards ────────────────────────────────────────────────
  html += sectionTitle('Location Summary');
  html += `<div class="grid-2 mb">
    <div class="card">
      <div class="card-h">Malaga — ${week}</div>
      <div class="stat-row"><span class="stat-label">Spend</span><span class="stat-val">$${(malC.spend||0).toFixed(2)}</span></div>
      <div class="stat-row"><span class="stat-label">Clicks</span><span class="stat-val">${fmt(malC.clicks||0,'n')}</span></div>
      <div class="stat-row"><span class="stat-label">Reach</span><span class="stat-val">${fmt(malC.reach||0,'n')}</span></div>
      <div class="stat-row"><span class="stat-label">CTR</span><span class="stat-val ${(malC.ctr||0)>=3?'good':(malC.ctr||0)<1?'bad':''}">${malC.ctr||'–'}%</span></div>
      <div class="stat-row"><span class="stat-label">CPM</span><span class="stat-val">${malC.cpm?'$'+malC.cpm:'–'}</span></div>
      <div class="stat-row"><span class="stat-label">CPR</span><span class="stat-val ${malC.cpr&&malP.cpr?(malC.cpr>malP.cpr?'bad':'good'):''}">${malC.cpr?'$'+malC.cpr:'–'} <span style="font-size:10px;color:var(--muted)">(prev: $${malP.cpr||'–'})</span></span></div>
      <div class="stat-row"><span class="stat-label">Results</span><span class="stat-val">${malC.results||'–'}</span></div>
      <div class="stat-row"><span class="stat-label">Active ads</span><span class="stat-val">${ads.filter(a=>a.location==='Malaga').length}</span></div>
    </div>
    <div class="card">
      <div class="card-h">Ellenbrook — ${week}</div>
      <div class="stat-row"><span class="stat-label">Spend</span><span class="stat-val">$${(ellC.spend||0).toFixed(2)}</span></div>
      <div class="stat-row"><span class="stat-label">Clicks</span><span class="stat-val">${fmt(ellC.clicks||0,'n')}</span></div>
      <div class="stat-row"><span class="stat-label">Reach</span><span class="stat-val">${fmt(ellC.reach||0,'n')}</span></div>
      <div class="stat-row"><span class="stat-label">CTR</span><span class="stat-val ${(ellC.ctr||0)>=3?'good':(ellC.ctr||0)<1?'bad':''}">${ellC.ctr||'–'}%</span></div>
      <div class="stat-row"><span class="stat-label">CPM</span><span class="stat-val">${ellC.cpm?'$'+ellC.cpm:'–'}</span></div>
      <div class="stat-row"><span class="stat-label">CPR</span><span class="stat-val">${ellC.cpr?'$'+ellC.cpr:'–'}</span></div>
      <div class="stat-row"><span class="stat-label">Results</span><span class="stat-val">${ellC.results||'–'}</span></div>
      <div class="stat-row"><span class="stat-label">Active ads</span><span class="stat-val">${ads.filter(a=>a.location==='Ellenbrook').length}</span></div>
    </div>
  </div>`;

  // ── Audience targeting context ────────────────────────────────────────────
  html += sectionTitle('Audience Strategy');
  html += `<div class="grid-3 mb">
    <div class="card">
      <div class="card-h">Audience 1 — FIFO Workers</div>
      <div style="font-size:12px;line-height:1.8;color:var(--text)">
        <div><b>Target:</b> WA postcodes near FIFO hubs. Interest: fly-in fly-out, mining, construction</div>
        <div><b>Age:</b> 25–45, male skew</div>
        <div><b>Radius:</b> Perth metro + Ellenbrook / Swan Valley</div>
        <div><b>Key message:</b> "Pause your membership anytime. Train hard when you're home."</div>
        <div><b>Best creative:</b> Freeze feature demo, no lock-in angle, 24/7 access for shift workers</div>
      </div>
    </div>
    <div class="card">
      <div class="card-h">Audience 2 — Malaga Families</div>
      <div style="font-size:12px;line-height:1.8;color:var(--text)">
        <div><b>Target:</b> Parents 28–45, Malaga / Hamersley / Dianella / Nollamara</div>
        <div><b>Age:</b> 28–45, female skew</div>
        <div><b>Radius:</b> 5km from Malaga location</div>
        <div><b>Key message:</b> "Kids Hub free while you train."</div>
        <div><b>Best creative:</b> Kids Hub footage + parent training in same session, before/after routine</div>
      </div>
    </div>
    <div class="card">
      <div class="card-h">Audience 3 — Health Newcomers</div>
      <div style="font-size:12px;line-height:1.8;color:var(--text)">
        <div><b>Target:</b> 18–35, not currently gym members (behaviour: no gym interest)</div>
        <div><b>Age:</b> 18–35, mixed gender</div>
        <div><b>Radius:</b> 8km from each location</div>
        <div><b>Key message:</b> "$11.95/week. No lock-in. Try your first week."</div>
        <div><b>Best creative:</b> Price anchor, facility tour, ice bath/sauna surprise reveal</div>
      </div>
    </div>
  </div>`;

  // ── This week's Meta Ads priorities ────────────────────────────────────────
  html += insight('teal', "This Week's Meta Ads Priorities",
    `<b>1. Scale "Deep heat. Deep recovery" immediately:</b> The only ad with Above average engagement + conversion ranking. Raise daily budget from current level to $100/week total. Do NOT change the creative — Meta's algorithm has learned the audience. Small changes reset learning phase.<br><br>
     <b>2. Pause worst-performing creative:</b> Any ad with a Below average signal on any ranking dimension should be paused today. Below average = Meta is penalising delivery and charging you more for worse placement. Reallocate budget to Star and Good-tier ads only.<br><br>
     <b>3. Refresh Average-tier ads with new creative:</b> Ads scoring Average on all three signals are plateaued. Create 1 new Malaga ad and 1 new Ellenbrook ad using the recovery/wellness angle that's proving to work. Test: "Ice bath. Sauna. Reformer Pilates. $11.95/week. No lock-in."<br><br>
     <b>4. Increase Ellenbrook budget by $5–10/day:</b> Ellenbrook is underinvested relative to its location potential. Add 1 hyperlocal Ellenbrook creative: "Your neighbourhood 24/7 gym" — suburb-name targeting consistently outperforms generic Perth-wide campaigns in suburban markets.<br><br>
     <b>5. Set up Meta Pixel events if not done:</b> Contact form submission, location page visit (Malaga + Ellenbrook), scroll depth 75% on pricing page. Without pixel events, Meta can't optimise for conversions — you're paying for clicks, not members.`);

  $('meta-content').innerHTML = html;
}

// ── Render: GBP ──────────────────────────────────────────────────────────────
function renderGBP() {
  const gbp = D.gbp, mal = gbp.malaga, ell = gbp.ellenbrook;
  const packRate = gbp.local_pack.pack_presence_rate||0;
  const packKws  = (gbp.local_pack.appearing_in_pack||[]).map(p=>`${p.keyword} (#${p.position})`).join(', ')||'No data';

  let html = `<div class="kpi-grid cols-4 mb">
    ${kpiCard('🟢','Malaga Rating',stars(mal.rating),null,`${fmt(mal.reviews,'n')} reviews`)}
    ${kpiCard('','Ellenbrook Rating',stars(ell.rating),null,`${fmt(ell.reviews,'n')} reviews`)}
    ${kpiCard('','Local Pack Rate',packRate+'%',null,`Appearing in 3-pack`)}
    ${kpiCard('📸','Photos Malaga',fmt(mal.photos,'n'),null,'Target: 100 photos')}
  </div>`;

  html += `<div class="grid-3 mb">
    ${insight('teal','Local Pack Analysis', `CB247 appearing in local pack for ${packRate}% of tracked keywords: ${packKws}`)}
    ${insight('amber','⚠️ Gap to Close', `Malaga has ${mal.photos||0} photos vs 100 target. Photos directly impact local pack ranking.`)}
    ${insight('teal','Recommendation', `<b>This week:</b> Upload 10 photos to each location (sauna, ice bath, Kids Hub, gym floor). Add a GBP post every Tuesday.`)}
  </div>`;

  // Location detail
  const locCard = (name, data, dot, reviews_target) => {
    const rev_pct = Math.min(100, Math.round((data.reviews||0)/reviews_target*100));
    const ph_pct  = Math.min(100, Math.round((data.photos||0)/100*100));
    return `<div class="card">
      <div class="card-h"><span class="stars">●</span> ${name} GBP</div>
      <div class="stat-row"><span class="stat-label">Rating</span><span class="stat-val">${stars(data.rating)}</span></div>
      <div class="stat-row"><span class="stat-label">Reviews</span><span class="stat-val">${fmt(data.reviews,'n')}</span></div>
      <div class="stat-row"><span class="stat-label">Photos</span><span class="stat-val">${fmt(data.photos,'n')}</span></div>
      <div class="stat-row"><span class="stat-label">Profile Complete</span><span class="stat-val">${data.completeness||'–'}%</span></div>
      <div class="progress-wrap">
        <div class="progress-label"><span>Reviews: ${data.reviews||0} / ${reviews_target} target</span><span>${rev_pct}%</span></div>
        <div class="progress-track"><div class="progress-fill" style="width:${rev_pct}%"></div></div>
      </div>
      <div class="progress-wrap">
        <div class="progress-label"><span>Photos: ${data.photos||0} / 100 target</span><span>${ph_pct}%</span></div>
        <div class="progress-track"><div class="progress-fill" style="width:${ph_pct}%"></div></div>
      </div>
    </div>`;
  };

  html += sectionTitle('Location Details');
  html += `<div class="grid-2 mb">${locCard('Malaga',mal,'green',530)}${locCard('Ellenbrook',ell,'blue',280)}</div>`;

  // Competitor comparison
  html += sectionTitle('🏆 Competitor Benchmarking');
  html += `<div class="card mb"><table>
    <thead><tr><th>Competitor</th><th>Location</th><th class="num">Rating</th><th class="num">Reviews</th></tr></thead><tbody>
    ${gbp.competitors.map(c=>`<tr><td>${c.name}</td><td>${c.location}</td><td class="num">${stars(c.rating)}</td><td class="num">${fmt(c.reviews,'n')}</td></tr>`).join('')||'<tr><td colspan="4" style="color:var(--muted)">No competitor data — run pull_apify.py</td></tr>'}
    </tbody></table></div>`;

  // GBP tasks
  html += sectionTitle('GBP Action Plan');
  html += `<div class="card mb"><ul class="task-list">
    <li class="task-item"><span class="priority-pill p-critical">Critical</span>Print QR code review cards — place at both reception desks</li>
    <li class="task-item"><span class="priority-pill p-critical">Critical</span>Brief front desk on verbal review ask script after every membership sign-up</li>
    <li class="task-item"><span class="priority-pill p-high">High</span>Rewrite GBP descriptions with local keywords (both locations)</li>
    <li class="task-item"><span class="priority-pill p-high">High</span>Seed GBP Q&amp;A with 6 pre-answered questions (FIFO freeze, pricing, Kids Hub)</li>
    <li class="task-item"><span class="priority-pill p-high">High</span>Upload 10 photos this week per location — sauna, ice bath, Kids Hub, gym floor</li>
    <li class="task-item"><span class="priority-pill p-medium">Medium</span>Schedule Tuesday GBP post — keyword-rich, service highlight</li>
    <li class="task-item"><span class="priority-pill p-medium">Medium</span>Audit and complete all GBP Services + Products listings</li>
  </ul></div>`;

  $('gbp-content').innerHTML = html;
}

// ── Render: Content Planner ───────────────────────────────────────────────────
// ── Content Planner Items ─────────────────────────────────────────────────────
const PLANNER_ITEMS = [
  {id:'p1',day:0,platform:'gbp',type:'GBP Post',title:'GBP Post — Sauna & Ice Bath',assignee:'Joanne',assigneeRole:'Social Media Manager',caption:'Recovery is part of training. Our Sauna + Ice Bath combo at ChasingBetter247 Malaga gives your body the reset it needs. $11.95/week, no lock-in.',instructions:'Post to both Malaga and Ellenbrook GBP profiles. Use a high-quality photo of the sauna or ice bath area. Best posting time: Tuesday 7–9am or Saturday 8am. Include the $11.95 price point and \'no lock-in\' in the first sentence for SEO. Tag location: Malaga.',kw:'sauna gym perth',dueDate:'+0'},
  {id:'p2',day:1,platform:'instagram',type:'Instagram Reel',title:'Reel — FIFO Lifestyle',assignee:'Agust',assigneeRole:'Video Creator',caption:'Fly in. Train hard. We get it. CB247\'s FIFO-friendly freeze means your membership works around your roster.',instructions:'30–45 second Reel. Open with a hook: \'Working FIFO? Your gym should work around you.\' Show the freeze feature on the app or website. Voiceover tone: direct, no-nonsense, WA working-class. End with CTA: \'Freeze. Resume. No questions asked.\' Hashtags: #fifo #fifoperth #gymperth #chasingbetter247',kw:'fifo gym perth',dueDate:'+1'},
  {id:'p3',day:2,platform:'blog',type:'SEO Blog Post',title:'Blog — Best Gym Malaga',assignee:'John',assigneeRole:'SEO Specialist',caption:'Targeting "best gym Malaga" — 320 searches/month. H1: "The Best Gym in Malaga? Here\'s Why 8,000 Members Chose CB247". Full outline and keyword map ready.',instructions:'Target keyword: "best gym malaga" (320/mo, KD 18). Secondary: "gym malaga perth", "cheap gym malaga". Word count: 1,200–1,500. Structure: H1 → Intro (lead with price + facilities) → H2: What Makes a Great Gym in Malaga? → H2: CB247 Malaga Facilities → H2: Pricing Comparison → H2: Member Reviews → H2: FAQ → CTA. Internal links: homepage, Malaga page, pricing. Mark adds draft to WordPress as pending.\n\nDraft for review: https://cb247agent.github.io/cb_claude/blog-drafts/best-gym-malaga.html',kw:'best gym malaga',dueDate:'+2',draftLink:'https://cb247agent.github.io/cb_claude/blog-drafts/best-gym-malaga.html'},
  {id:'p4',day:2,platform:'instagram',type:'Instagram Post',title:'Instagram — Kids Hub',assignee:'Shauna',assigneeRole:'Content & Email Manager',caption:'Train while the kids play. Our Kids Hub means no more "I can\'t go to the gym today." Tag a parent who needs this.',instructions:'Static post or short Reel (15s). Show the Kids Hub space — colourful, safe, supervised. Caption hook: "No babysitter? No problem." Tag 3 local parent pages. Best time: Wednesday 9–11am. Hashtags: #kidshub #gymperth #malagatribe #chasingbetter247',kw:'kids gym malaga',dueDate:'+2'},
  {id:'p5',day:4,platform:'tiktok',type:'TikTok Video',title:'TikTok — Ice Bath Reaction',assignee:'Ivan',assigneeRole:'Video Creator',caption:'First ice bath at CB247 😅❄️ Would you try this? #icebath #recovery #chasingbetter247',instructions:'Reaction-style video. Film a member (with permission) doing their first ice bath — show genuine reaction. Ideal length: 20–30 seconds. Hook in first 2s: "Would you do this for $11.95/week?" Trending audio: check TikTok trending for Perth fitness. Tag @chasingbetter247. Raw, authentic > over-produced.',kw:'ice bath gym perth',dueDate:'+4'},
  {id:'p6',day:5,platform:'gbp',type:'GBP Post',title:'GBP Post — Reformer Pilates',assignee:'Joanne',assigneeRole:'Social Media Manager',caption:'24/7 Reformer Pilates in Perth. Book your class at CB247 — Malaga & Ellenbrook.',instructions:'Post to both GBP profiles. Use a class photo or studio shot. Emphasise "24/7 access" — key differentiator vs Revo. Include class booking CTA. Target: "reformer pilates perth", "pilates malaga". Post Friday morning to capture weekend bookings.',kw:'reformer pilates perth',dueDate:'+5'},
  {id:'p7',day:7,platform:'instagram',type:'Instagram Reel',title:'Reel — Gym Tour',assignee:'Agust',assigneeRole:'Video Creator',caption:'Never been to CB247? Here\'s what $11.95/week gets you. 👀 #gymtour #chasingbetter247',instructions:'60-second gym walkthrough Reel. Script: "$11.95 a week — here\'s what that actually gets you." Walk through: 24/7 weights → Reformer Pilates → CrossFit → Sauna → Ice Bath → Neon21 → Kids Hub. Voiceover with on-screen text. End card: website URL + price. Post Sunday evening for Monday motivation.',kw:'gym malaga perth',dueDate:'+7'},
  {id:'p8',day:8,platform:'email',type:'Email Newsletter',title:'Weekly Email Newsletter',assignee:'Shauna',assigneeRole:'Content & Email Manager',caption:'Member spotlight + this week\'s class timetable + sauna booking tip',instructions:'Subject A/B test: A: "This week at CB247 🏋️" / B: "Your sauna booking tip + class times". Structure: 1) Member spotlight (150 words) → 2) Class timetable → 3) Sauna tip → 4) Referral nudge ("Bring a friend, 2 weeks free"). Send via Mailchimp. List: active members. Send time: Monday 6am.',kw:'',dueDate:'+8'},
  {id:'p9',day:9,platform:'blog',type:'SEO Blog Post',title:'Blog — FIFO Gym Membership Perth',assignee:'Shauna',assigneeRole:'Content & Email Manager',caption:'Targeting "fifo gym perth" — 210 searches/month. FIFO freeze angle.',instructions:'Target: "fifo gym perth" (210/mo). Secondary: "fifo gym membership", "gym freeze perth". Word count: 1,000–1,200. Angle: empathy-first — FIFO lifestyle is tough, gym should make it easier. Structure: H1: "FIFO Gym Membership in Perth" → H2: The FIFO Challenge → H2: What is a Gym Freeze? → H2: CB247 FIFO Freeze → FAQ → CTA. Tone: direct, WA working-class. Shauna drafts → John reviews SEO → Mark publishes.',kw:'fifo gym membership perth',dueDate:'+9'},
  {id:'p10',day:10,platform:'tiktok',type:'TikTok Video',title:'TikTok — Neon21 Tanning',assignee:'Ivan',assigneeRole:'Video Creator',caption:'You didn\'t know we had THIS at a $11.95/week gym 👀 #neon21 #gymsecrets',instructions:'Surprise-reveal style. Hook: "Things at CB247 people don\'t know about — Part 1". Feature: Neon21 tanning. Length: 15–20s. On-screen text: "Gym + tanning = $11.95/week??" Build curiosity — don\'t show feature in thumbnail. End: "Follow for Part 2" — drives follows for series.',kw:'',dueDate:'+10'},
  {id:'p11',day:11,platform:'gbp',type:'GBP Post',title:'GBP Post — Ellenbrook Special',assignee:'Joanne',assigneeRole:'Social Media Manager',caption:'Ellenbrook locals — your neighbourhood gym is here. 24/7 access, no lock-in, $11.95/week.',instructions:'Post ONLY to Ellenbrook GBP (not Malaga). Hyperlocal — use "Ellenbrook" 2–3 times. Photo: Ellenbrook location exterior or interior. Geo-tagged. Local keywords: "gym ellenbrook perth". Post Thursday morning.',kw:'gym ellenbrook perth',dueDate:'+11'},
  {id:'p12',day:13,platform:'instagram',type:'Instagram Post',title:'Community Post — Member Story',assignee:'Shauna',assigneeRole:'Content & Email Manager',caption:'Member story: how CB247 helped [member] hit their goal. Real stories, real results.',instructions:'Ask reception to nominate a member who hit a milestone this month. Get written consent + photo. Format: carousel (3–5 slides). Slide 1: Bold quote. Slides 2–3: Journey story. Slide 4: Goal and result. Slide 5: CTA — "Start your story. $11.95/week, no lock-in." Tag the member if they consent. This format gets highest saves + shares.',kw:'',dueDate:'+13'},
];

const PLANNER_STATUS_KEY = 'cb247-planner-status';
const PLANNER_APPROVAL_KEY = 'cb247-planner-approval';
const PLANNER_STATUSES = ['Idea','Scheduled','Published'];
const PLANNER_STATUS_COLORS = {Idea:'#dbeafe',Scheduled:'#fef9c3',Published:'#dcfce7'};

// ── Planner Modal ─────────────────────────────────────────────────────────────
let _modalItemId = null;

window.openPlannerModal = (id) => {
  const item = PLANNER_ITEMS.find(x=>x.id===id);
  if(!item) return;
  _modalItemId = id;

  const saved = JSON.parse(localStorage.getItem(PLANNER_STATUS_KEY)||'{}');
  const approval = JSON.parse(localStorage.getItem(PLANNER_APPROVAL_KEY)||'{}');
  const status = saved[id]||'Idea';
  const apprData = approval[id]||{};

  // Platform tag
  $('modal-platform-tag').innerHTML = `<span class="platform-tag platform-${item.platform}" style="font-size:10px">${item.platform.toUpperCase()} · ${item.type}</span>`;
  $('modal-title').textContent = item.title;

  // Role color map
  const roleColors = {'SEO Specialist':'#dbeafe','Video Creator':'#fce7f3','Social Media Manager':'#dcfce7','Content & Email Manager':'#fef9c3','Web Developer':'#ede9fe'};
  const rc = roleColors[item.assigneeRole]||'#f3f4f6';
  $('modal-meta').innerHTML = `
    <span class="chip">${item.assignee} <span style="font-size:10px;opacity:.7">· ${item.assigneeRole}</span></span>
    <span class="chip" style="background:#f0f0f0;color:var(--text-2)">Due Day ${item.dueDate}</span>
    ${item.kw ? '<span class="chip">'+item.kw+'</span>' : ''}
  `;

  $('modal-instructions').textContent = item.instructions;
  $('modal-caption').textContent = item.caption;

  $('modal-kw-block').innerHTML = item.kw
    ? `<div><div class="modal-section-label">Target Keyword</div><span class="chip" style="font-size:12px">${item.kw}</span></div>`
    : '';

  // Status pill
  const sc = PLANNER_STATUS_COLORS[status]||'#f3f4f6';
  $('modal-status-pill').innerHTML = `<span style="background:${sc};border-radius:99px;padding:3px 12px;font-size:12px;font-weight:700">${status}</span>`;

  // Approval state
  _refreshApprovalPills(apprData.status||null);
  const notesWrap = $('modal-notes-wrap');
  const notes = $('modal-notes');
  notes.value = apprData.notes||'';
  notesWrap.style.display = (apprData.status==='adjustment'||apprData.status==='rejected') ? 'block' : 'none';

  // Brief link — points to docs/briefs/[id].html
  const baseUrl = window.location.href.replace(/\/[^\/]*$/, '');
  $('modal-brief-link').href = `${baseUrl}/briefs/${id}.html`;

  // Draft link — show prominent button if item has a draftLink
  const draftLinkEl = document.getElementById('modal-draft-link-wrap');
  if(draftLinkEl) {
    if(item.draftLink) {
      draftLinkEl.style.display = 'block';
      draftLinkEl.querySelector('a').href = item.draftLink;
    } else {
      draftLinkEl.style.display = 'none';
    }
  }

  $('planner-modal').classList.add('open');
  document.body.style.overflow = 'hidden';
};

window.closePlannerModal = () => {
  $('planner-modal').classList.remove('open');
  document.body.style.overflow = '';
  _modalItemId = null;
};

window.saveModalAndClose = () => {
  if(!_modalItemId) { closePlannerModal(); return; }
  // Save approval
  const approval = JSON.parse(localStorage.getItem(PLANNER_APPROVAL_KEY)||'{}');
  const current = approval[_modalItemId]||{};
  approval[_modalItemId] = {...current, notes: $('modal-notes').value};
  localStorage.setItem(PLANNER_APPROVAL_KEY, JSON.stringify(approval));
  closePlannerModal();
  renderPlanner();
};

window.setModalApproval = (val) => {
  if(!_modalItemId) return;
  const approval = JSON.parse(localStorage.getItem(PLANNER_APPROVAL_KEY)||'{}');
  approval[_modalItemId] = {...(approval[_modalItemId]||{}), status: val};
  localStorage.setItem(PLANNER_APPROVAL_KEY, JSON.stringify(approval));
  _refreshApprovalPills(val);
  $('modal-notes-wrap').style.display = (val==='adjustment'||val==='rejected') ? 'block' : 'none';
};

function _refreshApprovalPills(val) {
  ['approved','adjustment','rejected'].forEach(v => {
    const el = $('apill-'+v);
    if(!el) return;
    el.className = 'appr-pill' + (v===val ? ' sel-'+v : '');
  });
}

window.cycleFromModal = () => {
  if(!_modalItemId) return;
  const saved = JSON.parse(localStorage.getItem(PLANNER_STATUS_KEY)||'{}');
  const curr = saved[_modalItemId]||'Idea';
  const next = PLANNER_STATUSES[(PLANNER_STATUSES.indexOf(curr)+1)%PLANNER_STATUSES.length];
  saved[_modalItemId] = next;
  localStorage.setItem(PLANNER_STATUS_KEY, JSON.stringify(saved));
  // Update pill in modal
  const sc = PLANNER_STATUS_COLORS[next]||'#f3f4f6';
  $('modal-status-pill').innerHTML = `<span style="background:${sc};border-radius:99px;padding:3px 12px;font-size:12px;font-weight:700">${next}</span>`;
  renderPlanner();
};

function renderPlanner() {
  const today = new Date();
  const days = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  const calDays = Array.from({length:14},(_,i)=>{
    const d = new Date(today); d.setDate(d.getDate()+i);
    return {date:d, label:days[d.getDay()]+' '+d.getDate()+' '+months[d.getMonth()]};
  });

  const saved = JSON.parse(localStorage.getItem(PLANNER_STATUS_KEY)||'{}');
  const approval = JSON.parse(localStorage.getItem(PLANNER_APPROVAL_KEY)||'{}');

  const approvalIcon = (id) => {
    const a = (approval[id]||{}).status;
    if(a==='approved') return '<span style="float:right;width:7px;height:7px;border-radius:50%;background:var(--teal);display:inline-block"></span>';
    if(a==='adjustment') return '<span style="float:right;width:7px;height:7px;border-radius:50%;background:var(--muted);display:inline-block"></span>';
    if(a==='rejected') return '<span style="float:right;width:7px;height:7px;border-radius:50%;background:var(--text-2);display:inline-block"></span>';
    return '';
  };

  const week = (startDay) => {
    const weekDays = calDays.slice(startDay, startDay+7);
    return '<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:8px;margin-bottom:16px">' +
      weekDays.map((day,i)=>{
        const globalDay = startDay+i;
        const items = PLANNER_ITEMS.filter(c=>c.day===globalDay);
        const isToday = i===0&&startDay===0;
        const borderCol = isToday?'var(--teal)':'var(--border)';
        const bgCol = isToday?'#f0fffe':'#fff';
        const todayBadge = isToday?' <span style="background:var(--teal);color:#fff;border-radius:99px;padding:1px 6px;font-size:9px">TODAY</span>':'';
        return '<div style="background:'+bgCol+';border-radius:8px;border:1px solid '+borderCol+';padding:10px;min-height:120px">' +
          '<div style="font-size:11px;font-weight:700;color:'+(isToday?'var(--teal)':'var(--muted)')+';margin-bottom:6px">'+day.label+todayBadge+'</div>' +
          items.map(item=>{
            const status = saved[item.id]||'Idea';
            const bg = PLANNER_STATUS_COLORS[status]||'#f3f4f6';
            return '<div style="background:'+bg+';border-radius:6px;padding:6px 8px;margin-bottom:4px;cursor:pointer;font-size:11px;border:1px solid transparent" ' +
              'onclick="openPlannerModal(\''+item.id+'\')" ' +
              'onmouseenter="this.style.borderColor=\'var(--teal)\'" ' +
              'onmouseleave="this.style.borderColor=\'transparent\'">' +
              '<span class="platform-tag platform-'+item.platform+'" style="font-size:9px">'+item.platform.toUpperCase()+'</span>' +
              approvalIcon(item.id) +
              '<div style="font-weight:600;margin:2px 0;line-height:1.3">'+item.title+'</div>' +
              '<div style="color:var(--muted);font-size:10px">'+item.assignee+' · <span style="opacity:.7">'+item.assigneeRole+'</span></div>' +
              '<div style="font-size:9px;margin-top:2px;font-weight:700;color:#666">'+status+'</div>' +
              '</div>';
          }).join('') +
        '</div>';
      }).join('') +
    '</div>';
  };

  // Summary row
  const totalItems = PLANNER_ITEMS.length;
  const approvedCount = PLANNER_ITEMS.filter(i=>(approval[i.id]||{}).status==='approved').length;
  const pendingCount = PLANNER_ITEMS.filter(i=>!(approval[i.id]||{}).status).length;

  let html = `
    <div class="insight blue mb">
      <div class="insight-label">Content Planner</div>
      ${totalItems} items this fortnight · <strong>${approvedCount} approved</strong> · <strong>${pendingCount} awaiting review</strong> — Click any card to view full brief, assign, approve, or update status.
    </div>
    ${sectionTitle('Week 1 — Days 1–7')}${week(0)}
    ${sectionTitle('Week 2 — Days 8–14')}${week(7)}
    <div class="card">
      <div class="card-h">All Content Items</div>
      <table><thead><tr><th>Day</th><th>Platform</th><th>Title</th><th>Assignee</th><th>Role</th><th>Status</th><th>Approval</th><th>Brief</th></tr></thead><tbody>`;

  const baseUrl = window.location.href.replace(/\/[^\/]*$/, '');
  PLANNER_ITEMS.forEach(item=>{
    const status = saved[item.id]||'Idea';
    const sc = PLANNER_STATUS_COLORS[status]||'#f3f4f6';
    const day = calDays[item.day];
    const apprData = approval[item.id]||{};
    const apprLabel = apprData.status==='approved'?'Approved':apprData.status==='adjustment'?'Adjustment':apprData.status==='rejected'?'Rejected':'—';
    html += '<tr>' +
      '<td style="font-size:11px">'+(day?day.label:'–')+'</td>' +
      '<td><span class="platform-tag platform-'+item.platform+'">'+item.platform+'</span></td>' +
      '<td style="font-weight:600;cursor:pointer;color:var(--teal)" onclick="openPlannerModal(\''+item.id+'\')">'+item.title+'</td>' +
      '<td>'+item.assignee+'</td>' +
      '<td style="font-size:11px;color:var(--muted)">'+item.assigneeRole+'</td>' +
      '<td><span style="background:'+sc+';border-radius:99px;padding:2px 8px;font-size:10px;font-weight:700">'+status+'</span></td>' +
      '<td style="font-size:11px">'+apprLabel+'</td>' +
      '<td><a href="'+baseUrl+'/briefs/'+item.id+'.html" target="_blank" style="font-size:11px;color:var(--teal);font-weight:600">View →</a></td>' +
      '</tr>';
  });

  html += '</tbody></table></div>';
  $('planner-content').innerHTML = html;
}

// ── Render: Content Review (Kanban) ──────────────────────────────────────────
function renderContentReview() {
  const REVIEW_KEY = 'cb247-content-review';
  const saved = JSON.parse(localStorage.getItem(REVIEW_KEY)||'{}');

  const CONTENT_QUEUE = [
    {id:'cr1',platform:'gbp',title:'GBP Post — Sauna & Ice Bath',preview:'Recovery is part of training. Our Sauna + Ice Bath combo gives your body the reset it needs...',assignee:'Joanne',keyword:'sauna gym perth',channel:'GBP'},
    {id:'cr2',platform:'instagram',title:'Reel — FIFO Lifestyle',preview:'Fly in. Train hard. We get it. CB247\'s FIFO-friendly freeze means your membership works around your roster...',assignee:'Agust',keyword:'fifo gym perth',channel:'Instagram'},
    {id:'cr3',platform:'blog',title:'Blog — Best Gym Malaga',preview:'Targeting "best gym Malaga" (320 searches/month). H1: "The Best Gym in Malaga? Here\'s Why 8,000 Members Chose CB247"...',assignee:'John',keyword:'best gym malaga',channel:'Blog'},
    {id:'cr4',platform:'instagram',title:'Kids Hub Instagram Post',preview:'Train while the kids play. Our Kids Hub means no more "I can\'t go to the gym today." Tag a parent who needs this...',assignee:'Shauna',keyword:'kids gym malaga',channel:'Instagram'},
    {id:'cr5',platform:'tiktok',title:'TikTok — Ice Bath Reaction',preview:'First ice bath at CB247 😅❄️ Would you try this? #icebath #recovery #chasingbetter247...',assignee:'Ivan',keyword:'ice bath gym perth',channel:'TikTok'},
    {id:'cr6',platform:'meta',title:'Meta Ad — FIFO Audience',preview:'Headline: Train hard when you\'re home. Body: CB247 FIFO-friendly freeze. Pause anytime. $11.95/week...',assignee:'Jane',keyword:'',channel:'Meta Ads'},
    {id:'cr7',platform:'gbp',title:'GBP Post — Reformer Pilates',preview:'24/7 Reformer Pilates in Perth. Book your class at CB247 — Malaga & Ellenbrook...',assignee:'Joanne',keyword:'reformer pilates perth',channel:'GBP'},
    {id:'cr8',platform:'email',title:'Weekly Email Newsletter',preview:'Member spotlight + this week\'s class timetable + sauna booking tip for VIP members...',assignee:'Shauna',keyword:'',channel:'Email'},
  ];

  const COLS = [
    {key:'generated', label:'Generated', desc:'AI output — Tia to review', color:'#6b7280'},
    {key:'tia-approved', label:'Tia Approved', desc:'Sent to Jane for QC', color:'#3b82f6'},
    {key:'jane-approved', label:'Jane Approved', desc:'Ready for Joanne', color:'#f59e0b'},
    {key:'scheduled', label:'Scheduled', desc:'Joanne has this', color:'#8b5cf6'},
    {key:'published', label:'Published', desc:'Live!', color:'#22c55e'},
  ];

  const moveCard = (id, col) => {
    const s = JSON.parse(localStorage.getItem(REVIEW_KEY)||'{}');
    s[id] = col;
    localStorage.setItem(REVIEW_KEY, JSON.stringify(s));
    // Update review badge
    const pending = CONTENT_QUEUE.filter(c=>(s[c.id]||'generated')==='generated').length;
    if($('review-badge')) $('review-badge').textContent = pending;
    renderContentReview();
  };
  window.moveReviewCard = moveCard;

  const cardHtml = (item) => {
    const status = saved[item.id]||'generated';
    const colIdx = COLS.findIndex(c=>c.key===status);
    const prevCol = colIdx>0?COLS[colIdx-1].key:null;
    const nextCol = colIdx<COLS.length-1?COLS[colIdx+1].key:null;
    return `<div class="content-card" style="border-left-color:${COLS[colIdx].color}">
      <span class="platform-tag platform-${item.platform}">${item.platform.toUpperCase()}</span>
      <div class="cc-title">${item.title}</div>
      <div class="cc-preview">${item.preview}</div>
      ${item.keyword?`<div style="margin-top:6px"><span class="chip" style="font-size:9px">${item.keyword}</span></div>`:''}
      <div class="cc-footer">
        <span class="cc-assignee">→ ${item.assignee}</span>
        <div style="display:flex;gap:4px">
          ${prevCol?`<button onclick="moveReviewCard('${item.id}','${prevCol}')" style="background:#f3f4f6;border-radius:4px;padding:2px 7px;font-size:10px;cursor:pointer">← Back</button>`:''}
          ${nextCol?`<button onclick="moveReviewCard('${item.id}','${nextCol}')" style="background:var(--teal);color:#fff;border-radius:4px;padding:2px 7px;font-size:10px;cursor:pointer;border:none">Approve →</button>`:''}
        </div>
      </div>
    </div>`;
  };

  const pending = CONTENT_QUEUE.filter(c=>(saved[c.id]||'generated')==='generated').length;
  if($('review-badge')) $('review-badge').textContent = pending;

  let html = `
    <div class="insight blue mb">
      <div class="insight-label">Approval Flow</div>
      <b>Tia</b> reviews Generated → approves to Jane &nbsp;·&nbsp; <b>Jane</b> QCs → approves to Joanne &nbsp;·&nbsp; <b>Joanne</b> schedules → marks Published.
      Status saves in your browser automatically.
    </div>
    <div class="kanban">
      ${COLS.map(col=>{
        const items = CONTENT_QUEUE.filter(c=>(saved[c.id]||'generated')===col.key);
        return `<div class="kanban-col">
          <div class="kanban-col-header" style="color:${col.color}">
            ${col.label} <span class="count">${items.length}</span>
          </div>
          <div style="font-size:10px;color:var(--muted);margin-bottom:8px">${col.desc}</div>
          ${items.map(cardHtml).join('')}
          ${items.length===0?'<div style="font-size:11px;color:var(--muted);text-align:center;padding:20px 0">Empty</div>':''}
        </div>`;
      }).join('')}
    </div>`;

  $('review-content').innerHTML = html;
}

// ── Render: Website Manager ───────────────────────────────────────────────────
function renderWebsite() {
  const seo = D.seo;
  let html = `<div class="kpi-grid cols-3 mb">
    ${kpiCard('','Broken Backlinks',seo.broken_backlinks.length,null,'Pages to fix or redirect','secondary')}
    ${kpiCard('📤','Lost Backlinks',seo.lost_backlinks.length,null,'Last 30 days — outreach needed','secondary')}
    ${kpiCard('🏥','Domain Rating',seo.domain_rating||'–',null,'Ahrefs authority 0–100')}
  </div>`;

  html += sectionTitle('🔴 Critical Dev Tasks');
  html += `<div class="card mb"><ul class="task-list">
    <li class="task-item"><span class="priority-pill p-critical">Critical</span>Fix broken backlinks — add 301 redirects to ${seo.broken_backlinks.length||0} broken pages</li>
    <li class="task-item"><span class="priority-pill p-critical">Critical</span>Add H1 tags to all pages missing them (check Ahrefs Site Audit)</li>
    <li class="task-item"><span class="priority-pill p-critical">Critical</span>Ensure unique meta descriptions on all 20 target keyword pages (&lt;160 chars)</li>
    <li class="task-item"><span class="priority-pill p-high">High</span>Add LocalBusiness JSON-LD schema to Malaga + Ellenbrook location pages</li>
    <li class="task-item"><span class="priority-pill p-high">High</span>Create /ellenbrook dedicated landing page — estimated $386/week Google Ads saving</li>
    <li class="task-item"><span class="priority-pill p-high">High</span>Compress images on top 5 pages (target: &lt;100kb per image, current LCP likely slow)</li>
    <li class="task-item"><span class="priority-pill p-medium">Medium</span>Add breadcrumb schema markup to blog posts and location pages</li>
    <li class="task-item"><span class="priority-pill p-medium">Medium</span>Set up 301 redirects for any URL changes from Ahrefs broken backlink report</li>
    <li class="task-item"><span class="priority-pill p-medium">Medium</span>Submit NAP listings to AU directories: True Local, Yelp, Yellow Pages, Hot Frog</li>
    <li class="task-item"><span class="priority-pill p-low">Low</span>Audit internal linking — ensure all service pages link to location pages</li>
  </ul></div>`;

  html += sectionTitle('Broken Backlinks — Fix These Pages');
  html += `<div class="card mb"><table>
    <thead><tr><th>Linking Site</th><th>Broken URL on Our Site</th><th class="num">DR</th><th>Fix</th></tr></thead><tbody>
    ${seo.broken_backlinks.slice(0,8).map(b=>`<tr>
      <td style="font-size:11px">${(b.url_from||'').replace(/https?:\/\//,'').slice(0,40)}</td>
      <td style="font-size:11px;color:var(--red)">${(b.url_to||'').replace('https://chasingbetter247.com.au','')}</td>
      <td class="num">${b.domain_rating_source||'–'}</td>
      <td style="font-size:11px;color:var(--teal)">Add 301 redirect</td>
    </tr>`).join('')||'<tr><td colspan="4" style="color:var(--muted)">No broken backlinks — great! Run pull_ahrefs.py to check.</td></tr>'}
    </tbody></table></div>`;

  html += insight('teal','Website Manager Priority',
    `<b>This week for Mark:</b><br>
     1. Add LocalBusiness schema to both location pages (Malaga + Ellenbrook) — direct local pack ranking impact.<br>
     2. Create /ellenbrook page — saves ~$386/week in Google Ads. Use the SEO brief content template.<br>
     3. Fix broken backlinks from the table above — each one is a free domain authority gain.`);

  $('web-content').innerHTML = html;
}

// ── Render: Recommendations ───────────────────────────────────────────────────
function renderRecommendations() {
  const REC_KEY = 'cb247-recommendations';
  const OUTCOME_KEY = 'cb247-rec-outcomes';
  const saved   = JSON.parse(localStorage.getItem(REC_KEY)||'{}');
  const outcomes= JSON.parse(localStorage.getItem(OUTCOME_KEY)||'{}');

  const STATUSES = ['new','accepted','inprogress','done','skipped'];
  const STATUS_LABELS = {new:'New',accepted:'Accepted',inprogress:'In Progress',done:'Done ✓',skipped:'Skipped'};
  const STATUS_CLASS  = {new:'status-new',accepted:'status-accepted',inprogress:'status-inprogress',done:'status-done',skipped:'status-skipped'};

  // Recommendations generated by the AI OS (in production these come from state/ files)
  const RECS = [
    {id:'r1',channel:'seo',icon:'🔍',title:'Publish content for "reformer pilates malaga"',why:'Revo Fitness ranks #4 for this keyword (210 searches/month). CB247 has the service but no ranking page. Estimated: +$85/week organic value.',owner:'John + Shauna',impact:'+$85/wk organic',week:'Week of 2 Jun 2026'},
    {id:'r2',channel:'ads',icon:'',title:'Pause Google Ads for keywords ranking organically #1–3',why:'Once CB247 ranks #1 organically for a keyword, running an ad on the same keyword wastes budget — users will click the organic result. Audit and pause overlapping campaigns.',owner:'Tia',impact:'Est. $200–400/wk saving',week:'Week of 2 Jun 2026'},
    {id:'r3',channel:'gbp',icon:'',title:'Upload 10 photos per location this week',why:'Photo count directly impacts local pack ranking. Malaga has fewer photos than competitor benchmark. Each photo batch improves listing completeness score.',owner:'Joanne',impact:'Local pack ranking ↑',week:'Week of 2 Jun 2026'},
    {id:'r4',channel:'seo',icon:'',title:'Reclaim broken backlinks — contact 3 top-DR linking sites',why:'Sites linking to broken CB247 pages are already willing to link to you. Emailing to update the URL is the fastest DR improvement possible.',owner:'John',impact:'DR increase',week:'Week of 2 Jun 2026'},
    {id:'r5',channel:'web',icon:'',title:'Create /ellenbrook dedicated landing page',why:'Ellenbrook Google Ads spend ~$386/week. A dedicated landing page targeting "gym ellenbrook perth" would allow those ads to be paused.',owner:'Mark + John',impact:'Est. $386/wk saving',week:'Week of 2 Jun 2026'},
    {id:'r6',channel:'gbp',icon:'⭐',title:'Print QR code review cards — both locations',why:'Review velocity is a top GBP ranking signal. Front desk verbal asks + QR code cards proven to increase review rate by 3–5x.',owner:'Tia + Front Desk',impact:'Reviews ↑ → local pack ↑',week:'Week of 2 Jun 2026'},
    {id:'r7',channel:'content',icon:'',title:'Lead this week\'s Reels with ice bath / sauna content',why:'Google Trends Perth shows "cold plunge" and "sauna" rising. CB247 has this facility — competitors don\'t heavily feature it. First-mover advantage on social.',owner:'Agust + Ivan',impact:'Engagement ↑',week:'Week of 2 Jun 2026'},
    {id:'r8',channel:'seo',icon:'',title:'Fix H1 tags on top 5 pages',why:'Multiple high-traffic pages missing or duplicating H1 tags. This is a basic on-page SEO issue costing ranking positions.',owner:'Mark',impact:'Rankings ↑ on affected pages',week:'Week of 2 Jun 2026'},
  ];

  const cycleStatus = (id) => {
    const s = JSON.parse(localStorage.getItem(REC_KEY)||'{}');
    const curr = s[id]||'new';
    s[id] = STATUSES[(STATUSES.indexOf(curr)+1)%STATUSES.length];
    localStorage.setItem(REC_KEY, JSON.stringify(s));
    updateRecBadge();
    renderRecommendations();
  };
  const saveOutcome = (id) => {
    const inp = document.getElementById('outcome-'+id);
    if(!inp) return;
    const o = JSON.parse(localStorage.getItem(OUTCOME_KEY)||'{}');
    o[id] = inp.value;
    localStorage.setItem(OUTCOME_KEY, JSON.stringify(o));
    renderRecommendations();
  };
  window.cycleRecStatus = cycleStatus;
  window.saveRecOutcome = saveOutcome;

  const tagClass = {seo:'t-seo',ads:'',gbp:'t-seo',meta:'',content:'',web:''};
  const tagLabel = {seo:'SEO',ads:'Google Ads',gbp:'GBP',meta:'Meta Ads',content:'Content',web:'Website'};

  // Filter UI
  const filterRec = (filter) => {
    document.querySelectorAll('.rec-filter-btn').forEach(b=>b.style.background=(b.dataset.f===filter?'var(--teal)':'#f3f4f6'));
    document.querySelectorAll('.rec-filter-btn').forEach(b=>b.style.color=(b.dataset.f===filter?'#fff':'var(--text)'));
    document.querySelectorAll('.rec-card-wrap').forEach(card=>{
      const status = saved[card.dataset.id]||'new';
      card.style.display = (filter==='all'||status===filter)?'block':'none';
    });
  };
  window.filterRec = filterRec;

  const openCount = RECS.filter(r=>(saved[r.id]||'new')==='new').length;
  if($('rec-badge')) $('rec-badge').textContent = openCount;

  let html = `
    <div class="insight teal mb">
      <div class="insight-label">How it works</div>
      Every Monday the Marketing OS generates recommendations from data. Click the status button to update progress.
      Add an outcome note when done — this builds your performance record over time.
    </div>
    <div style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap">
      ${['all','new','accepted','inprogress','done','skipped'].map(f=>`
        <button class="rec-filter-btn" data-f="${f}" onclick="filterRec('${f}')"
          style="border-radius:99px;padding:5px 14px;font-size:12px;font-weight:600;cursor:pointer;border:none;
                 background:${f==='all'?'var(--teal)':'#f3f4f6'};color:${f==='all'?'#fff':'var(--text)'}">
          ${f==='all'?'All':STATUS_LABELS[f]}
          ${f==='new'?`(${openCount})`:''}
        </button>`).join('')}
    </div>
    <div class="rec-board">
      ${RECS.map(rec=>{
        const status = saved[rec.id]||'new';
        const outcome= outcomes[rec.id]||'';
        return `<div class="rec-card-wrap" data-id="${rec.id}">
          <div class="rec-card ${status==='done'?'done':''}" style="border-left:4px solid ${status==='done'?'var(--green)':status==='skipped'?'var(--border)':'var(--teal)'}">
            
            <div class="rec-body">
              <div class="rec-tags">
                <span class="rec-tag ${tagClass[rec.channel]||'tag-seo'}">${tagLabel[rec.channel]||rec.channel}</span>
                <span style="font-size:10px;color:var(--muted)">${rec.week}</span>
              </div>
              <div class="rec-title">${rec.title}</div>
              <div class="rec-why">${rec.why}</div>
              <div class="rec-footer">
                <span class="rec-impact">${rec.impact}</span>
                <span class="rec-owner">Owner: ${rec.owner}</span>
                <button class="rec-status-btn ${STATUS_CLASS[status]||'status-new'}" onclick="cycleRecStatus('${rec.id}')">
                  ${STATUS_LABELS[status]||'New'} ↻
                </button>
              </div>
              ${status==='done'?`
                <div style="margin-top:10px;display:flex;gap:8px;align-items:center">
                  <input id="outcome-${rec.id}" class="rec-outcome-input" placeholder="What was the actual outcome / result?" value="${outcome}">
                  <button onclick="saveRecOutcome('${rec.id}')" style="background:var(--teal);color:#fff;border:none;border-radius:6px;padding:5px 12px;font-size:11px;cursor:pointer;font-weight:600">Save</button>
                </div>`:''
              }
            </div>
          </div>
        </div>`;
      }).join('')}
    </div>`;

  $('rec-content').innerHTML = html;
}

function updateRecBadge() {
  const saved = JSON.parse(localStorage.getItem('cb247-recommendations')||'{}');
  const RECS_COUNT = 8; // match RECS array length
  // Count 'new' ones - approximate from localStorage
  const open = Object.values(saved).filter(v=>v==='new').length;
  // if nothing saved, all are new
  if($('rec-badge')) $('rec-badge').textContent = open||RECS_COUNT;
}

// ── Render: Status bar ────────────────────────────────────────────────────────
function renderStatus() {
  const s = D.status;
  const allLive = Object.values(s).every(v=>v==='live'||v==='suspended');
  $('system-dot').className = 'status-dot'+(allLive?'':' warn');
  $('refresh-label').textContent = 'Last refresh: '+D.refresh_ts;
  $('page-footer').innerHTML = `CB247 Marketing OS &nbsp;·&nbsp; Generated: ${D.generated} &nbsp;·&nbsp; <a href="https://cb247agent.github.io/cb_claude/">cb247agent.github.io/cb_claude</a>`;
}

// ── Render: README / How It Works ────────────────────────────────────────────
function renderReadme() {
  const container = $('readme-content');
  if (!container) return;

  container.innerHTML = `

  <!-- ══ SECTION 1: WEEKLY LOOP ══════════════════════════════════════════════ -->
  <div class="readme-section">
    <h2>The Weekly Loop</h2>
    <div class="card" style="padding:28px">
      <div class="loop-diagram">
        <div class="loop-node">
          <div class="loop-icon" style="border-color:var(--teal);background:var(--teal-mist)"><div class="loop-icon-inner"></div></div>
          <div class="loop-label">Monday 10am</div>
          <div class="loop-sub">Auto-run<br>triggers</div>
        </div>
        <div class="loop-arrow">→</div>
        <div class="loop-node">
          <div class="loop-icon" style="border-color:var(--teal);background:var(--teal-mist)"><div class="loop-icon-inner"></div></div>
          <div class="loop-label">9 AI Agents</div>
          <div class="loop-sub">Run in sequence<br>~40 min</div>
        </div>
        <div class="loop-arrow">→</div>
        <div class="loop-node">
          <div class="loop-icon" style="background:#f4f4f4"><div class="loop-icon-inner" style="background:var(--muted-2)"></div></div>
          <div class="loop-label">Report + Dashboard</div>
          <div class="loop-sub">Generated &amp;<br>deployed live</div>
        </div>
        <div class="loop-arrow">→</div>
        <div class="loop-node">
          <div class="loop-icon" style="background:#f4f4f4"><div class="loop-icon-inner" style="background:var(--muted-2)"></div></div>
          <div class="loop-label">Tia Gets Email</div>
          <div class="loop-sub">Report +<br>dashboard link</div>
        </div>
        <div class="loop-arrow">→</div>
        <div class="loop-node">
          <div class="loop-icon" style="background:#f4f4f4"><div class="loop-icon-inner" style="background:var(--muted-2)"></div></div>
          <div class="loop-label">Team Meeting</div>
          <div class="loop-sub">Review &amp; decide<br>on actions</div>
        </div>
        <div class="loop-arrow">→</div>
        <div class="loop-node">
          <div class="loop-icon" style="background:#f4f4f4"><div class="loop-icon-inner" style="background:var(--muted-2)"></div></div>
          <div class="loop-label">Decisions Recorded</div>
          <div class="loop-sub">Meeting minutes<br>imported</div>
        </div>
        <div class="loop-arrow">→</div>
        <div class="loop-node">
          <div class="loop-icon" style="border-color:var(--teal);background:var(--teal-mist)"><div class="loop-icon-inner"></div></div>
          <div class="loop-label">Team Executes</div>
          <div class="loop-sub">Tracker follows<br>outcomes</div>
        </div>
        <div class="loop-arrow" style="color:var(--teal);font-size:14px">↺</div>
      </div>
      <div class="legend" style="margin-top:20px">
        <div class="legend-item"><div class="legend-dot" style="background:var(--teal)"></div>Automated (no human)</div>
        <div class="legend-item"><div class="legend-dot" style="background:var(--teal)"></div>Tia reviews &amp; approves</div>
        <div class="legend-item"><div class="legend-dot" style="background:var(--text-2)"></div>Team executes</div>
      </div>
    </div>
  </div>

  <!-- ══ SECTION 2: AGENT PIPELINE ══════════════════════════════════════════ -->
  <div class="readme-section">
    <h2>Agent Pipeline — How the 9 Agents Work Together</h2>
    <p style="font-size:12px;color:var(--muted);margin-bottom:16px">Each agent reads the outputs of agents before it. They run in sequence — each one builds on the last.</p>

    <div class="card" style="padding:20px">

      <!-- Phase 1: Data Pull -->
      <div class="agent-phase">
        <div class="agent-phase-label">Phase 1 — Data Pull (automated scripts)</div>
        <div class="agent-row">
          <div class="agent-box">
            <div class="agent-name">pull_all.py</div>
            <div class="agent-desc">GA4 · GSC · Google Ads · Meta Ads</div>
          </div>
          <div class="agent-connector">+</div>
          <div class="agent-box">
            <div class="agent-name">pull_ahrefs.py</div>
            <div class="agent-desc">Rankings · backlinks · organic value · keyword gaps</div>
          </div>
          <div class="agent-connector">+</div>
          <div class="agent-box">
            <div class="agent-name">pull_apify.py</div>
            <div class="agent-desc">SERP scrape · Maps · Reddit · Trends · FB Ads intel</div>
          </div>
        </div>
      </div>

      <div class="phase-arrow">↓ fresh data ready</div>

      <!-- Phase 2: Research layer -->
      <div class="agent-phase">
        <div class="agent-phase-label">Phase 2 — Research Layer (Agents 1–3 run in parallel)</div>
        <div class="agent-row">
          <div class="agent-box">
            <div class="agent-num">01</div>
            <div class="agent-name">Research Agent</div>
            <div class="agent-desc">Perth market signals · trending fitness topics · competitor ad intel · Reddit pain points · seasonal alert (active campaign + upcoming events)</div>
            <div class="agent-reads">Reads: platform data · seasonal-calendar.md</div>
            <div class="agent-out">→ weekly-research.md</div>
          </div>
          <div class="agent-box">
            <div class="agent-num">02</div>
            <div class="agent-name">Audience Intel</div>
            <div class="agent-desc">ICP pulse check · who's converting this week · exact language to use in copy · tone recommendation</div>
            <div class="agent-reads">Reads: GA4 · Reddit · research output</div>
            <div class="agent-out">→ audience-weekly.md</div>
          </div>
          <div class="agent-box">
            <div class="agent-num">03</div>
            <div class="agent-name">Content Intel</div>
            <div class="agent-desc">Viral hooks this week · best-performing formats · trending audio · competitor content gaps</div>
            <div class="agent-reads">Reads: social trends · FB ads · research + audience outputs</div>
            <div class="agent-out">→ content-intel.md</div>
          </div>
        </div>
      </div>

      <div class="phase-arrow">↓ market intelligence ready</div>

      <!-- Phase 3: Analysis layer -->
      <div class="agent-phase">
        <div class="agent-phase-label">Phase 3 — Analysis Layer (Agents 4–6)</div>
        <div class="agent-row">
          <div class="agent-box">
            <div class="agent-num">04</div>
            <div class="agent-name">Performance</div>
            <div class="agent-desc">Full KPI dashboard · organic vs paid ratio · organic value $ · Google Ads offset recommendations</div>
            <div class="agent-reads">Reads: GA4 · GSC · Google Ads · Ahrefs · Apify</div>
            <div class="agent-out">→ performance-week.md</div>
          </div>
          <div class="agent-box">
            <div class="agent-num">05</div>
            <div class="agent-name">SEO Agent</div>
            <div class="agent-desc">20 keyword rankings · quick wins · keyword gaps · 2 content briefs · backlinks · local pack · ads to pause</div>
            <div class="agent-reads">Reads: Ahrefs · GSC · Apify · performance output</div>
            <div class="agent-out">→ weekly-seo-brief.md</div>
          </div>
          <div class="agent-box">
            <div class="agent-num">06</div>
            <div class="agent-name">Competitor Spy</div>
            <div class="agent-desc">What Revo &amp; Anytime changed this week · GBP battle table · keyword threats · ad intel · counter-move</div>
            <div class="agent-reads">Reads: Ahrefs · Apify · FB Ads · research output</div>
            <div class="agent-out">→ competitor-weekly.md</div>
          </div>
        </div>
      </div>

      <div class="phase-arrow">↓ analysis complete</div>

      <!-- Phase 4: Action layer -->
      <div class="agent-phase">
        <div class="agent-phase-label">Phase 4 — Action Layer (Agents 7–8)</div>
        <div class="agent-row">
          <div class="agent-box">
            <div class="agent-num">07</div>
            <div class="agent-name">Paid Ads</div>
            <div class="agent-desc">Which Google Ads to pause (now covered by SEO) · budget reductions · Meta audience targeting · creative briefs · cumulative savings tracker</div>
            <div class="agent-reads">Reads: Google Ads · Ahrefs · seo-brief.md · audience-weekly.md · seasonal-calendar.md · psychology-triggers.md</div>
            <div class="agent-out">→ paid-ads-weekly.md</div>
          </div>
          <div class="agent-box">
            <div class="agent-num">08</div>
            <div class="agent-name">Content Agent</div>
            <div class="agent-desc">Full week of content: 4 GBP posts · 2 blog drafts · 5 social posts · 2 Reel scripts · 5 review templates · 3 Meta ad variations — seasonally aware, psychology-trigger enforced</div>
            <div class="agent-reads">Reads: seo-brief.md · content-intel.md · audience-weekly.md · competitor-weekly.md · seasonal-calendar.md · psychology-triggers.md · brand-voice.md</div>
            <div class="agent-out">→ weekly-content.md</div>
          </div>
        </div>
      </div>

      <div class="phase-arrow">↓ all outputs ready</div>

      <!-- Phase 5: Synthesis -->
      <div class="agent-phase">
        <div class="agent-phase-label">Phase 5 — Synthesis (Agent 9)</div>
        <div class="agent-row">
          <div class="agent-box primary-agent">
            <div class="agent-num" style="background:var(--teal);color:#fff">09</div>
            <div class="agent-name">Strategist</div>
            <div class="agent-desc">Reads ALL 8 agent outputs. Produces the single executive strategy document Tia reviews: seasonal status · weekly scorecard · top 5 priorities · decisions needed · one-line brief per team member</div>
            <div class="agent-reads">Reads: ALL 8 agent outputs · seasonal-calendar.md</div>
            <div class="agent-out">→ weekly-strategy.md → this dashboard</div>
          </div>
        </div>
      </div>

      <div style="background:rgba(63,166,154,.06);border:1px solid rgba(63,166,154,.2);border-radius:8px;padding:14px;margin-top:4px;font-size:12px;line-height:1.6">
        <strong>Total runtime: ~60 min.</strong> Phase 1 ~20 min (API calls). Phase 2–4 ~40 min (9 AI agents sequential). Phase 5 bakes HTML report + dashboard, pushes to GitHub Pages, sends Tia's email.
      </div>
    </div>
  </div>

  <!-- ══ SECTION 3: DATA SOURCES ════════════════════════════════════════════ -->
  <div class="readme-section">
    <h2>Data Sources</h2>
    <div class="data-grid">
      <div class="data-source">
        <div class="ds-icon"><div class="ds-dot"></div></div>
        <div class="ds-name">Google Analytics 4</div>
      </div>
      <div class="data-source">
        <div class="ds-icon"><div class="ds-dot"></div></div>
        <div class="ds-name">Search Console</div>
      </div>
      <div class="data-source">
        <div class="ds-icon"><div class="ds-dot"></div></div>
        <div class="ds-name">Google Ads</div>
      </div>
      <div class="data-source">
        <div class="ds-icon"><div class="ds-dot"></div></div>
        <div class="ds-name">Meta Ads</div>
      </div>
      <div class="data-source">
        <div class="ds-icon"><div class="ds-dot"></div></div>
        <div class="ds-name">Ahrefs</div>
      </div>
      <div class="data-source">
        <div class="ds-icon"><div class="ds-dot"></div></div>
        <div class="ds-name">Apify — SERP + Maps</div>
      </div>
      <div class="data-source">
        <div class="ds-icon"><div class="ds-dot"></div></div>
        <div class="ds-name">Google Business Profile</div>
      </div>
      <div class="data-source">
        <div class="ds-icon"><div class="ds-dot"></div></div>
        <div class="ds-name">Social Trends</div>
      </div>
      <div class="data-source">
        <div class="ds-icon"><div class="ds-dot"></div></div>
        <div class="ds-name">Reddit Intel</div>
      </div>
      <div class="data-source">
        <div class="ds-icon"><div class="ds-dot"></div></div>
        <div class="ds-name">Google Trends</div>
      </div>
    </div>
    <p style="font-size:11px;color:var(--muted);margin-top:12px">All data sources are refreshed automatically every Monday before the agent pipeline runs. To refresh manually: <code>python3 scripts/pull_all.py</code></p>
  </div>

  <!-- ══ SECTION 4: TEAM WORKFLOW ════════════════════════════════════════════ -->
  <div class="readme-section">
    <h2>Who Does What — Team Workflow</h2>
    <div class="team-flow">
      <div class="team-card lead">
        <div class="tc-name">Tia</div>
        <div class="tc-role">Director</div>
        <ul class="tc-tasks">
          <li>Reviews Monday email + dashboard</li>
          <li>Chairs marketing meeting</li>
          <li>Approves/adjusts/rejects recommendations</li>
          <li>Releases team emails after approval</li>
        </ul>
      </div>
      <div class="team-card">
        <div class="tc-name">Ange</div>
        <div class="tc-role">Marketing Manager</div>
        <ul class="tc-tasks">
          <li>Strategic priorities this week</li>
          <li>Campaign oversight</li>
          <li>Coordinates team execution</li>
          <li>Reports outcomes back to tracker</li>
        </ul>
      </div>
      <div class="team-card">
        <div class="tc-name">John</div>
        <div class="tc-role">SEO Specialist</div>
        <ul class="tc-tasks">
          <li>Receives SEO brief from agent</li>
          <li>Writes/briefs content for keywords</li>
          <li>Reviews blog drafts</li>
          <li>Tracks ranking improvements</li>
        </ul>
      </div>
      <div class="team-card">
        <div class="tc-name">Jane</div>
        <div class="tc-role">QC Manager</div>
        <ul class="tc-tasks">
          <li>Reviews all content before publish</li>
          <li>Approves blog drafts</li>
          <li>Checks brand voice compliance</li>
          <li>Releases to Joanne for scheduling</li>
        </ul>
      </div>
      <div class="team-card">
        <div class="tc-name">Mark</div>
        <div class="tc-role">Web Developer</div>
        <ul class="tc-tasks">
          <li>Executes technical SEO fixes</li>
          <li>Publishes blog posts to WordPress</li>
          <li>Builds new landing pages</li>
          <li>Title tag + meta optimisation</li>
        </ul>
      </div>
      <div class="team-card">
        <div class="tc-name">Joanne</div>
        <div class="tc-role">Social Media Manager</div>
        <ul class="tc-tasks">
          <li>Schedules approved posts</li>
          <li>Posts to GBP profiles</li>
          <li>Responds to reviews</li>
          <li>Manages content calendar</li>
        </ul>
      </div>
      <div class="team-card">
        <div class="tc-name">Shauna</div>
        <div class="tc-role">Content & Email</div>
        <ul class="tc-tasks">
          <li>Writes blog drafts from SEO brief</li>
          <li>Writes weekly email newsletter</li>
          <li>Creates social captions</li>
          <li>Member spotlight stories</li>
        </ul>
      </div>
      <div class="team-card">
        <div class="tc-name">Agust + Ivan</div>
        <div class="tc-role">Video Creators</div>
        <ul class="tc-tasks">
          <li>Produce Reels from agent scripts</li>
          <li>TikTok content</li>
          <li>Gym walkthrough videos</li>
          <li>Member reaction content</li>
        </ul>
      </div>
    </div>
  </div>

  <!-- ══ SECTION 5: APPROVAL FLOW ════════════════════════════════════════════ -->
  <div class="readme-section">
    <h2>Content Approval Flow</h2>
    <div class="card" style="padding:20px">
      <div class="loop-diagram" style="align-items:flex-start;gap:0;flex-wrap:wrap">
        <div class="loop-node" style="min-width:100px">
          <div class="loop-icon active-node"><div class="loop-icon-inner"></div></div>
          <div class="loop-label">AI Generates</div>
          <div class="loop-sub">Agent writes<br>content brief</div>
        </div>
        <div class="loop-arrow">→</div>
        <div class="loop-node" style="min-width:100px">
          <div class="loop-icon active-node"><div class="loop-icon-inner"></div></div>
          <div class="loop-label">Tia Approves</div>
          <div class="loop-sub">Approve /<br>adjust / reject</div>
        </div>
        <div class="loop-arrow">→</div>
        <div class="loop-node" style="min-width:100px">
          <div class="loop-icon active-node"><div class="loop-icon-inner"></div></div>
          <div class="loop-label">Team Creates</div>
          <div class="loop-sub">Shauna / John /<br>Agust writes</div>
        </div>
        <div class="loop-arrow">→</div>
        <div class="loop-node" style="min-width:100px">
          <div class="loop-icon" style="background:#f4f4f4"><div class="loop-icon-inner" style="background:var(--muted-2)"></div></div>
          <div class="loop-label">Jane Reviews</div>
          <div class="loop-sub">QC pass /<br>request edits</div>
        </div>
        <div class="loop-arrow">→</div>
        <div class="loop-node" style="min-width:100px">
          <div class="loop-icon active-node"><div class="loop-icon-inner"></div></div>
          <div class="loop-label">Joanne Schedules</div>
          <div class="loop-sub">Posts to GBP /<br>Instagram / TikTok</div>
        </div>
        <div class="loop-arrow">→</div>
        <div class="loop-node" style="min-width:100px">
          <div class="loop-icon active-node"><div class="loop-icon-inner"></div></div>
          <div class="loop-label">Track Outcome</div>
          <div class="loop-sub">Performance<br>assessed +2 weeks</div>
        </div>
      </div>
    </div>
  </div>

  <!-- ══ SECTION 6: SKILL TRIGGERS ══════════════════════════════════════════ -->
  <div class="readme-section">
    <h2>Skill Triggers — Say These to Activate</h2>
    <div class="skill-grid">
      <div class="skill-row"><span class="skill-trigger">"write email"</span><span class="skill-skill">→ Email funnel builder (4-email + 2-SMS sequence)</span></div>
      <div class="skill-row"><span class="skill-trigger">"content waterfall"</span><span class="skill-skill">→ Repurpose 1 piece into 14 assets</span></div>
      <div class="skill-row"><span class="skill-trigger">"social calendar"</span><span class="skill-skill">→ 30-day content plan</span></div>
      <div class="skill-row"><span class="skill-trigger">"UTM audit"</span><span class="skill-skill">→ Standardise all tracking URLs</span></div>
      <div class="skill-row"><span class="skill-trigger">"site audit"</span><span class="skill-skill">→ Full technical SEO audit</span></div>
      <div class="skill-row"><span class="skill-trigger">"landing page"</span><span class="skill-skill">→ SEO landing page writer</span></div>
      <div class="skill-row"><span class="skill-trigger">"competitor ads"</span><span class="skill-skill">→ Competitor ads scraper + analysis</span></div>
      <div class="skill-row"><span class="skill-trigger">"compliance check"</span><span class="skill-skill">→ Review health claims &amp; legal compliance</span></div>
      <div class="skill-row"><span class="skill-trigger">"full campaign"</span><span class="skill-skill">→ 7-stage pipeline: brief → content → ads → report</span></div>
      <div class="skill-row"><span class="skill-trigger">"SEO pipeline"</span><span class="skill-skill">→ 6-stage: audit → brief → page → compliance → report</span></div>
    </div>
    <p style="font-size:11px;color:var(--muted);margin-top:10px">Type these phrases in Claude to activate the matching skill. Full list in <code>skills/manifest.json</code></p>
  </div>

  `;
}

// ── Render: Action Tracker ────────────────────────────────────────────────────
function renderTracker() {
  const container = $('tracker-content');
  if (!container) return;

  const actions = (D.tracker && D.tracker.actions) || [];
  const minutes = (D.tracker && D.tracker.meeting_minutes) || [];

  const catTag = c => {
    const map = {seo:'tag-seo',content:'tag-content','paid-ads':'tag-paid-ads',website:'tag-website',operations:'tag-operations',social:'tag-social'};
    return `<span class="tracker-tag ${map[c]||'tag-operations'}">${c}</span>`;
  };
  const prioClass = p => p==='P1'?'p1-dot':p==='P2'?'p2-dot':'p3-dot';

  // Pipeline stages
  const stages = [
    { key:'recommended', label:'Recommended',     color:'var(--muted)',  filter: a => a.decision==='pending' },
    { key:'decided',     label:'Decision Made',   color:'var(--text-2)',   filter: a => ['approved','adjusted','rejected'].includes(a.decision) && a.status==='pending' },
    { key:'execution',   label:'In Execution',    color:'var(--teal)',  filter: a => a.status==='in_progress' },
    { key:'outcome',     label:'Outcome Review',  color:'var(--muted)',  filter: a => a.status==='completed' || a.outcome_assessed },
  ];

  const card = a => {
    const decClass = a.decision!=='pending' ? `decision-${a.decision}` : '';
    const statClass = `status-${a.status||'pending'}`;
    const decIcon = {approved:'Approved',adjusted:'Adjusted',rejected:'Rejected',pending:'Pending'}[a.decision]||'Pending';
    return `<div class="tracker-card ${decClass} ${statClass}" onclick="openTrackerDetail('${a.id}')">
      <div class="tracker-card-title"><span class="${prioClass(a.priority||'P2')}"></span>${(a.recommendation||'').substring(0,72)}${a.recommendation?.length>72?'…':''}</div>
      <div class="tracker-card-meta">
        ${catTag(a.category||'operations')}
        <span>${a.owner||''}</span>
        ${a.due_date?`<span>Due ${a.due_date}</span>`:''}
        <span>${decIcon} ${a.decision||'pending'}</span>
      </div>
    </div>`;
  };

  const pipelineHTML = `<div class="tracker-pipeline">${stages.map(s=>{
    const items = actions.filter(s.filter);
    return `<div class="tracker-stage">
      <div class="tracker-stage-header">
        <span class="tracker-stage-label" style="color:${s.color}">${s.label}</span>
        <span class="tracker-stage-count">${items.length}</span>
      </div>
      ${items.length ? items.map(card).join('') : '<div style="font-size:11px;color:var(--muted);padding:8px 0">None</div>'}
    </div>`;
  }).join('')}</div>`;

  // KPI summary
  const total = actions.length;
  const approved = actions.filter(a=>a.decision==='approved').length;
  const inProgress = actions.filter(a=>a.status==='in_progress').length;
  const completed = actions.filter(a=>a.status==='completed').length;
  const pending = actions.filter(a=>a.decision==='pending').length;

  const kpiHTML = `<div class="kpi-grid cols-4" style="margin-bottom:20px">
    <div class="kpi-card"><div class="kpi-label">Total Actions</div><div class="kpi-value">${total}</div></div>
    <div class="kpi-card"><div class="kpi-label">Approved</div><div class="kpi-value" style="color:var(--green)">${approved}</div></div>
    <div class="kpi-card"><div class="kpi-label">In Progress</div><div class="kpi-value" style="color:var(--amber)">${inProgress}</div></div>
    <div class="kpi-card"><div class="kpi-label">Completed</div><div class="kpi-value" style="color:var(--teal)">${completed}</div></div>
  </div>`;

  // Detail panel placeholder
  const detailHTML = `<div class="tracker-detail-panel" id="tracker-detail-panel">
    <div id="tracker-detail-inner"></div>
  </div>`;

  // Meeting minutes log
  const minutesHTML = minutes.length ? `
    <div class="section-title" style="margin-top:24px">📋 Meeting History</div>
    ${minutes.slice().reverse().map(m=>{
      const d = m.decisions_summary||{};
      return `<div class="meeting-log">
        <div class="meeting-log-header">
          <span class="meeting-log-date">📅 ${m.date}</span>
          <div class="meeting-log-pills">
            ${d.approved?`<span class="meet-pill meet-approved">${d.approved} approved</span>`:''}
            ${d.adjusted?`<span class="meet-pill meet-adjusted">${d.adjusted} adjusted</span>`:''}
            ${d.rejected?`<span class="meet-pill meet-rejected">${d.rejected} rejected</span>`:''}
          </div>
        </div>
        ${m.narrative?`<div style="font-size:12px;color:var(--muted);line-height:1.5;margin-bottom:8px">${m.narrative}</div>`:''}
        ${m.attendees?.length?`<div style="font-size:11px;color:var(--muted)">👥 ${m.attendees.join(', ')}</div>`:''}
        ${m.active_promos?.length?`<div style="font-size:11px;color:var(--teal);margin-top:4px">🎯 ${m.active_promos.join(' · ')}</div>`:''}
        ${m.promo_details?`<div style="font-size:11px;color:var(--text);margin-top:4px;font-style:italic">${m.promo_details}</div>`:''}
      </div>`;
    }).join('')}
  ` : `<div style="color:var(--muted);font-size:12px;padding:16px 0">No meeting minutes recorded yet. After your Monday meeting, open <a href="meeting-minutes.html" target="_blank">meeting-minutes.html</a>, record decisions, download JSON, drop in state/, then run: <code>python scripts/import-meeting-minutes.py</code></div>`;

  // All actions table
  const tableRows = actions.map(a=>{
    const decIcon = {approved:'Approved',adjusted:'Adjusted',rejected:'Rejected',pending:'Pending'}[a.decision]||'Pending';
    const statIcon = {in_progress:'In Progress',completed:'Done',cancelled:'Cancelled',pending:'Pending'}[a.status]||'Pending';
    return `<tr>
      <td style="font-weight:600">${a.id}</td>
      <td>${catTag(a.category||'ops')}</td>
      <td style="max-width:300px">${(a.recommendation||'').substring(0,60)}${a.recommendation?.length>60?'…':''}</td>
      <td>${a.owner||'—'}</td>
      <td>${decIcon} ${a.decision||'pending'}</td>
      <td>${statIcon} ${a.status||'pending'}</td>
      <td>${a.due_date||'—'}</td>
      <td>${a.review_date||'—'}</td>
    </tr>`;
  }).join('');

  const tableHTML = `<div class="section-title" style="margin-top:24px">All Actions</div>
    <div class="card" style="overflow-x:auto;margin-bottom:20px">
      <table>
        <thead><tr>
          <th>ID</th><th>Category</th><th>Recommendation</th><th>Owner</th>
          <th>Decision</th><th>Status</th><th>Due</th><th>Review</th>
        </tr></thead>
        <tbody>${tableRows||'<tr><td colspan="8" style="color:var(--muted);text-align:center;padding:20px">No actions yet. Run the Monday report and import meeting minutes.</td></tr>'}</tbody>
      </table>
    </div>`;

  const meetingCTA = `<div style="background:rgba(63,166,154,.08);border:1px solid rgba(63,166,154,.2);border-radius:var(--radius);padding:16px;margin-bottom:20px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px">
    <div>
      <div style="font-weight:700;font-size:13px;margin-bottom:3px">📋 After your Monday meeting</div>
      <div style="font-size:12px;color:var(--muted)">Record decisions → download JSON → drop in state/ → run import script</div>
    </div>
    <a href="meeting-minutes.html" target="_blank" style="background:var(--teal);color:#fff;padding:8px 16px;border-radius:6px;font-size:12px;font-weight:600;white-space:nowrap">Open Meeting Minutes →</a>
  </div>`;

  container.innerHTML = kpiHTML + meetingCTA + detailHTML + pipelineHTML + tableHTML + minutesHTML;

  // Badge
  if($('tracker-badge')) $('tracker-badge').textContent = pending||'';
}

function openTrackerDetail(id) {
  const actions = (D.tracker && D.tracker.actions) || [];
  const a = actions.find(x=>x.id===id);
  if (!a) return;

  const panel = $('tracker-detail-panel');
  const inner = $('tracker-detail-inner');
  if (!panel || !inner) return;

  const decIcon = {approved:'Approved',adjusted:'Needs Adjustment',rejected:'Rejected',pending:'Pending'}[a.decision]||'Pending';
  const statIcon = {in_progress:'In Progress',completed:'Completed',cancelled:'Cancelled',pending:'Pending'}[a.status]||'Pending';

  let impactHTML = '';
  if (a.projected_impact && Object.keys(a.projected_impact).length) {
    const rows = Object.entries(a.projected_impact).map(([k,v])=>{
      const actual = a.actual_impact && a.actual_impact[k];
      return `<tr><td>${k}</td><td>${v.from||'—'} → ${v.to||'—'}</td>
        <td>${actual ? (actual.actual||'—') : '<span style="color:var(--muted)">TBD</span>'}</td></tr>`;
    }).join('');
    impactHTML = `<div class="section-title" style="margin-top:16px">Impact Tracking</div>
      <table><thead><tr><th>KPI</th><th>Projected</th><th>Actual</th></tr></thead><tbody>${rows}</tbody></table>`;
  }

  inner.innerHTML = `
    <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:16px">
      <div>
        <div style="font-size:10px;color:var(--muted);font-weight:700;text-transform:uppercase;margin-bottom:4px">${a.id} · ${a.category||''} · ${a.priority||''}</div>
        <div style="font-size:15px;font-weight:700;line-height:1.4">${a.recommendation||''}</div>
        <div style="font-size:12px;color:var(--muted);margin-top:6px">${a.context||''}</div>
      </div>
      <button onclick="closeTrackerDetail()" style="font-size:18px;color:var(--muted);padding:4px 8px;flex-shrink:0;margin-left:12px">✕</button>
    </div>
    <div class="outcome-grid">
      <div class="outcome-cell"><div class="label">Owner</div><div class="val" style="font-size:13px">${a.owner||'—'} <span style="font-size:11px;font-weight:400;color:var(--muted)">${a.ownerRole||''}</span></div></div>
      <div class="outcome-cell"><div class="label">Decision</div><div class="val" style="font-size:13px">${decIcon}</div></div>
      <div class="outcome-cell"><div class="label">Status</div><div class="val" style="font-size:13px">${statIcon}</div></div>
      <div class="outcome-cell"><div class="label">Due Date</div><div class="val" style="font-size:13px">${a.due_date||'—'}</div></div>
    </div>
    ${a.adjusted_brief?`<div style="margin-top:12px;background:#fffbeb;border-left:3px solid var(--amber);padding:10px 12px;border-radius:4px;font-size:12px"><strong>Adjustment:</strong> ${a.adjusted_brief}</div>`:''}
    ${a.decision_notes?`<div style="margin-top:8px;font-size:12px;color:var(--muted)"><strong>Notes:</strong> ${a.decision_notes}</div>`:''}
    ${impactHTML}
    ${a.outcome_verdict?`<div style="margin-top:12px;font-size:13px;font-weight:700" class="verdict-${a.outcome_verdict}">Outcome: ${a.outcome_verdict.replace('_',' ')}</div>`:''}
    ${a.outcome_notes?`<div style="font-size:12px;color:var(--muted);margin-top:4px">${a.outcome_notes}</div>`:''}
  `;

  panel.classList.add('open');
  panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function closeTrackerDetail() {
  const panel = $('tracker-detail-panel');
  if (panel) panel.classList.remove('open');
}

// ── Init ──────────────────────────────────────────────────────────────────────
function init() {
  renderStatus();
  renderOverview();
  renderSEO();
  renderGAds();
  renderOrgSocial();
  renderMeta();
  renderGBP();
  renderPlanner();
  renderContentReview();
  renderWebsite();
  renderRecommendations();
  renderTracker();
  renderReadme();

  // Restore last active page
  const lastPage = localStorage.getItem('cb247-active-page')||'overview';
  const navItem = document.querySelector(`[data-page="${lastPage}"]`);
  if(navItem) nav(navItem);

  // Init review badge
  renderContentReview();
  updateRecBadge();
}

document.addEventListener('DOMContentLoaded', init);
</script>
</body>
</html>"""


if __name__ == "__main__":
    build()
