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
    """Stubbed — Google Ads data now comes from the API (state/google-ads-data.json).
    The googleads/ CSV folder is no longer used by this script."""
    return [], ""


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


def load_agent_outputs():
    """Parse today's agent markdown outputs into structured data for the dashboard."""
    import re
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")
    outputs_dir = BASE_DIR / "outputs"

    def read_md(path):
        try:
            return path.read_text(encoding="utf-8") if path.exists() else ""
        except Exception:
            return ""

    def extract_section(text, heading):
        """Extract text under a markdown ## heading until the next ## heading.
        Splits only on ## level so ### sub-headings are included in the section body."""
        # Split only on ## (level-2) headings to keep ### sub-sections intact
        parts = re.split(r'\n(?=## )', text)
        for part in parts:
            first_line = part.split("\n", 1)[0]
            if heading.upper() in first_line.upper():
                body = part.split("\n", 1)[1] if "\n" in part else ""
                return body.strip()
        # Fallback: split on any heading level
        parts2 = re.split(r'\n(?=#{1,3} )', text)
        for part in parts2:
            first_line = part.split("\n", 1)[0]
            if heading.upper() in first_line.upper():
                body = part.split("\n", 1)[1] if "\n" in part else ""
                return body.strip()
        return ""

    # ── Load agent outputs ──
    strategy_md    = read_md(outputs_dir / "blueprints" / f"weekly-strategy-{today}.md")
    performance_md = read_md(outputs_dir / "research"   / f"performance-week-{today}.md")
    seo_md         = read_md(outputs_dir / "seo"        / f"weekly-seo-brief-{today}.md")
    competitor_md  = read_md(outputs_dir / "research"   / f"competitor-weekly-{today}.md")
    paid_ads_md    = read_md(outputs_dir / "research"   / f"paid-ads-weekly-{today}.md")
    content_md     = read_md(outputs_dir / "content"    / f"weekly-content-{today}.md")

    # ── Parse strategy scorecard table ──
    scorecard = []
    sc_section = extract_section(strategy_md, "WEEKLY SCORECARD")
    for row in re.findall(r'\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|', sc_section):
        metric, value, wow, status_cell = row
        emoji = "🟢" if "🟢" in status_cell else ("🔴" if "🔴" in status_cell else "🟡")
        scorecard.append({"metric": metric.strip(), "value": value.strip(), "wow": wow.strip(), "status": emoji})

    # ── Parse top 5 priorities ──
    priorities = []
    pri_section = extract_section(strategy_md, "TOP 5 PRIORITIES")
    for m in re.finditer(r'###\s*Priority\s*\d+[:\s]*\*\*(.+?)\*\*.*?\n(.*?)(?=###\s*Priority|\Z)', pri_section, re.DOTALL):
        title = m.group(1).strip()
        body  = m.group(2).strip()
        who   = re.search(r'\*\*Who:\*\*\s*(.+)', body)
        why   = re.search(r'\*\*Why:\*\*\s*(.+)', body)
        dead  = re.search(r'\*\*Deadline:\*\*\s*(.+)', body)
        rag   = "🔴" if "🔴" in title or "URGENT" in title or "CRITICAL" in title else ("💰" if "💰" in title else "🟡")
        priorities.append({
            "title": re.sub(r'[🔴💰🎯⚔️🟡]', '', title).strip(),
            "rag": rag,
            "why":  why.group(1).strip()  if why  else "",
            "who":  who.group(1).strip()  if who  else "",
            "deadline": dead.group(1).strip() if dead else "",
        })

    # ── Parse decisions needed ──
    decisions = []
    dec_section = extract_section(strategy_md, "DECISIONS NEEDED")
    for m in re.finditer(r'###\s*Decision\s*\d+[:\s]*\*\*(.+?)\*\*.*?\n(.*?)(?=###\s*Decision|\Z)', dec_section, re.DOTALL):
        title = m.group(1).strip()
        body  = m.group(2).strip()
        rec   = re.search(r'\*\*Recommendation.*?:\*\*\s*\n?(.*?)(?=\*\*Question|\Z)', body, re.DOTALL)
        q     = re.search(r'\*\*Question.*?:\*\*\s*(.+)', body)
        decisions.append({
            "title": title,
            "recommendation": rec.group(1).strip()[:300] if rec else "",
            "question": q.group(1).strip() if q else "",
        })

    # ── Parse team summary ──
    team = []
    team_section = extract_section(strategy_md, "TEAM SUMMARY")
    for m in re.finditer(r'\*\*(.+?)\s*\((.+?)\)\s*:\*\*\s*\n(.*?)(?=\*\*[A-Z]|\Z)', team_section, re.DOTALL):
        name, role, tasks_raw = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        tasks = [t.strip("- \n") for t in tasks_raw.split("\n") if t.strip().startswith("-")]
        team.append({"name": name, "role": role, "tasks": tasks[:3]})

    # ── Parse weekly narrative ──
    narrative = extract_section(strategy_md, "WEEKLY NARRATIVE")
    narrative_clean = re.sub(r'\*\*(.*?)\*\*', r'\1', narrative).strip()

    # ── Parse seasonal status ──
    seasonal = extract_section(strategy_md, "SEASONAL STATUS")
    seasonal_clean = re.sub(r'\*\*(.*?)\*\*', r'\1', seasonal).strip()[:500]

    return {
        "date":         today,
        "has_outputs":  bool(strategy_md),
        "scorecard":    scorecard,
        "priorities":   priorities[:5],
        "decisions":    decisions[:3],
        "team":         team,
        "narrative":    narrative_clean[:800],
        "seasonal":     seasonal_clean,
        "raw": {
            "strategy":    strategy_md[:2000],
            "performance": performance_md[:1000],
            "seo":         seo_md[:1000],
            "competitor":  competitor_md[:1000],
        }
    }


def load_all_agent_outputs():
    """Load full text of all 9 agent output files for today. Used to wire each dashboard page."""
    from datetime import date as _date
    today = _date.today().strftime("%Y-%m-%d")
    outputs_dir = BASE_DIR / "outputs"

    def _read(path):
        try:
            return path.read_text(encoding="utf-8") if path.exists() else ""
        except Exception:
            return ""

    seo       = _read(outputs_dir / "seo"      / f"weekly-seo-brief-{today}.md")
    paid_ads  = _read(outputs_dir / "research" / f"paid-ads-weekly-{today}.md")
    content   = _read(outputs_dir / "content"  / f"weekly-content-{today}.md")
    perf      = _read(outputs_dir / "research" / f"performance-week-{today}.md")
    competitor= _read(outputs_dir / "research" / f"competitor-weekly-{today}.md")
    strategy  = _read(outputs_dir / "blueprints"/ f"weekly-strategy-{today}.md")
    audience  = _read(outputs_dir / "research" / f"audience-weekly-{today}.md")

    has = any([seo, paid_ads, content, perf, competitor, strategy])

    # ── Parse structured highlights from SEO brief ────────────────────────────
    import re as _re3
    seo_highlights = {}
    if seo:
        # Big wins — only match lines with quoted keyword: 🟢 **"keyword"** action
        wins = []
        for m in _re3.finditer(r'[\-\*\s]*🟢\s*\*\*"([^"]+)"\*\*\s+([^\n]+)', seo):
            wins.append(f'"{m.group(1).strip()}" {m.group(2).strip()}')
        seo_highlights['wins'] = wins[:3]

        # Critical issues (🔴 lines from Key Findings)
        crits = []
        for m in _re3.finditer(r'🔴\s*\*\*([^*\n]+)\*\*[:\s]*\n?(.*?)(?=\n###|\n---|\Z)', seo, _re3.DOTALL):
            crits.append({'title': m.group(1).strip(), 'desc': m.group(2).strip()[:200]})
        seo_highlights['critical'] = crits[:2]

        # Top 3 actions (numbered list after "Top 3 Actions" heading)
        top_actions = []
        act_m = _re3.search(r'## Top 3 Actions.*?\n(.*?)(?=\n---|\n##|\Z)', seo, _re3.DOTALL)
        if act_m:
            for m in _re3.finditer(r'\d+\.\s*\*\*([^*\n]+)\*\*\s*[—–-]+\s*([^\n]+)', act_m.group(1)):
                top_actions.append({'title': m.group(1).strip(), 'desc': m.group(2).strip()})
        seo_highlights['top_actions'] = top_actions[:3]

        # Organic value
        ov_m = _re3.search(r'\$([0-9,]+)/week', seo)
        seo_highlights['organic_value'] = '$' + ov_m.group(1) + '/week' if ov_m else ''

        # Content briefs — parse each "CONTENT BRIEF N" section
        content_briefs = []
        for m in _re3.finditer(
            r'## \d+\. CONTENT BRIEF \d+\s*[—–-]+\s*"?([^"\n]+)"?(.*?)(?=\n## \d+\.|\Z)',
            seo, _re3.DOTALL
        ):
            b_title = m.group(1).strip()
            b_body  = m.group(2)
            kw_m   = _re3.search(r'\*\*Target Keyword:\*\*\s*(.+)', b_body)
            url_m  = _re3.search(r'\*\*Target URL:\*\*\s*(.+)', b_body)
            h1_m   = _re3.search(r'\*\*H1:\*\*\s*(.+)', b_body)
            meta_m = _re3.search(r'\*\*Meta Description[^:]*:\*\*\s*\n(.+)', b_body)
            why_m  = _re3.search(r'\*\*Why This Matters:\*\*\s*(.+)', b_body)
            wc_m   = _re3.search(r'\*\*Word Count:\*\*\s*(.+)', b_body)
            cta_m  = _re3.search(r'\*\*CTA:\*\*.*?- Primary:\s*(.+)', b_body)
            content_briefs.append({
                'title':      b_title,
                'keyword':    kw_m.group(1).strip()  if kw_m  else '',
                'url':        url_m.group(1).strip()  if url_m  else '',
                'h1':         h1_m.group(1).strip()   if h1_m   else b_title,
                'meta':       meta_m.group(1).strip() if meta_m else '',
                'why':        why_m.group(1).strip()  if why_m  else '',
                'word_count': wc_m.group(1).strip()   if wc_m   else '',
                'cta':        cta_m.group(1).strip()  if cta_m  else '',
                'full':       b_body[:4000],
            })
        seo_highlights['content_briefs'] = content_briefs

    return {
        "date":          today,
        "has_outputs":   has,
        "seo":           seo,
        "seo_highlights": seo_highlights,
        "paid_ads":      paid_ads,
        "content":       content,
        "performance":   perf,
        "competitor":    competitor,
        "strategy":      strategy,
        "audience":      audience,
    }


def build_data():
    """Load all state files and return a single dashboard data dict."""
    ga4      = load("ga4-data.json")
    gsc      = load("gsc-data.json")
    ads      = load("ads-data.json")
    gads     = load("google-ads-data.json")   # separate API pull — has own generated_at
    apify    = load("apify-data.json")
    ahrefs   = load("ahrefs-data.json")
    refresh  = load("last-refresh.json")
    tracker  = load_tracker()

    now = datetime.now().strftime("%d %b %Y, %H:%M")

    # ── Per-source timestamp helper (ISO UTC → Perth AWST readable) ───
    from datetime import timezone as _tz, timedelta as _td
    def _fmt_ts(iso_str):
        """Convert ISO UTC timestamp to '4 Jun 2026, 15:57 AWST'. Returns 'No data' if blank."""
        if not iso_str:
            return "No data"
        try:
            _utc = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
            _awst = _utc.astimezone(_tz(_td(hours=8)))
            return _awst.strftime("%-d %b %Y, %H:%M AWST")
        except Exception:
            return str(iso_str)[:16]  # best-effort fallback

    # ── Per-source timestamps (used to label each dashboard section) ──
    # Sources: ga4/gsc from their own files; google_ads from google-ads-data.json (API pull);
    # meta_ads from ads-data.json (written by pull_meta.py); gbp from apify-data.json
    _ts = {
        "ga4":        _fmt_ts((ga4   or {}).get("generated_at", "")),
        "gsc":        _fmt_ts((gsc   or {}).get("generated_at", "")),
        "google_ads": _fmt_ts((gads  or {}).get("generated_at", "")),
        "meta_ads":   _fmt_ts((ads   or {}).get("generated_at", "")),
        "gbp":        _fmt_ts((apify or {}).get("generated_at", "")),
        "ahrefs":     _fmt_ts((ahrefs or {}).get("generated_at", "")),
    }
    # Global "last refresh" = most recent successful source pull
    _all_raw = [s.get("generated_at","") for s in [ga4, gsc, gads, ads, apify] if s and s.get("generated_at")]
    _refresh_ts_fmt = _fmt_ts(max(_all_raw)) if _all_raw else now

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
    # Detect API error state from google-ads-data.json (gads loaded separately)
    _gads_accounts = (gads or {}).get("accounts", {})
    _gads_has_error = isinstance(_gads_accounts, dict) and any(
        isinstance(v, dict) and "error" in v for v in _gads_accounts.values()
    )
    _gads_error_msg = ""
    if _gads_has_error:
        _first_err = next((v.get("error","") for v in _gads_accounts.values() if isinstance(v,dict) and "error" in v), "")
        if "429" in _first_err or "exhausted" in _first_err.lower():
            _gads_error_msg = "rate_limited"
        elif "DNS" in _first_err or "hostname" in _first_err:
            _gads_error_msg = "dns_error"
        else:
            _gads_error_msg = "api_error"

    gads_list  = ads.get("google_ads") or []

    # Find last week with real (non-zero) spend — used as fallback when API errors
    _last_good_gads = next(
        (w for w in gads_list if safe_float((w.get("combined") or {}).get("spend")) > 0),
        None
    )
    _last_good_gads_label = _last_good_gads.get("week_label", "") if _last_good_gads else ""

    # When API is errored, fall back to the last known-good week so the page
    # shows real figures instead of misleading zeros.
    if _gads_has_error and _last_good_gads:
        _lg_idx    = next((i for i, w in enumerate(gads_list) if w is _last_good_gads), 0)
        latest_ads = _last_good_gads
        prev_ads   = gads_list[_lg_idx + 1] if len(gads_list) > _lg_idx + 1 else {}
    else:
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

    # ── Meta Ads (ads-data.json) — for Overview KPI card ────────────
    meta_ads_list   = ads.get("meta_ads") or []
    meta_ads_latest = meta_ads_list[0] if meta_ads_list else {}
    meta_ads_prev   = meta_ads_list[1] if len(meta_ads_list) > 1 else {}
    meta_combined   = meta_ads_latest.get("combined") or {}
    meta_total_spend = safe_float(meta_combined.get("spend"))
    meta_mal_spend   = safe_float((meta_ads_latest.get("malaga") or {}).get("spend"))
    meta_ell_spend   = safe_float((meta_ads_latest.get("ellenbrook") or {}).get("spend"))

    # ── Organic Social / Meta CSV data ──────────────────────────────
    meta_social = load_meta_social()
    metricool   = load_metricool()

    # ── Social trends (hashtags) ─────────────────────────────────────
    social_tr = load("social-trends.json")
    trending_hashtags = (social_tr.get("trending_hashtags") or [])[:15]
    top_social_posts  = (social_tr.get("top_posts") or [])[:5]

    # ── GBP / Maps ───────────────────────────────────────────────────
    maps_targets = (apify.get("competitor_maps") or {}).get("targets") or []
    mal_gbp = next((t for t in maps_targets if t.get("type") == "cb247" and t.get("location") == "Malaga"), {})
    ell_gbp = next((t for t in maps_targets if t.get("type") == "cb247" and t.get("location") == "Ellenbrook"), {})
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

    # ── Fallback: parse SEO brief when Ahrefs data is null ───────────────
    # Search for most recent weekly-seo-brief in the last 7 days
    from datetime import date as _d2, timedelta as _td2
    _seo_dir = BASE_DIR / "outputs" / "seo"
    _brief_path = None
    for _days_ago in range(0, 8):
        _candidate = _seo_dir / f"weekly-seo-brief-{(_d2.today() - _td2(days=_days_ago)).strftime('%Y-%m-%d')}.md"
        if _candidate.exists():
            _brief_path = _candidate
            break
    if _brief_path and not ah_kws:
        import re as _re2
        _brief = _brief_path.read_text(encoding="utf-8")

        # Domain rating
        _dr_m = _re2.search(r'\bDR\s*(\d+)', _brief)
        if _dr_m and not domain_rating:
            domain_rating = int(_dr_m.group(1))

        # Organic value  e.g. "$7,976/week"
        _ov_m = _re2.search(r'\$([\d,]+)/week', _brief)
        if _ov_m and not organic_value:
            organic_value = int(_ov_m.group(1).replace(',', ''))

        # Keyword table rows: | keyword | #pos | wow | vol | url | status |
        _kw_rows = []
        for _m in _re2.finditer(
            r'\|\s*([^|\n]+?)\s*\|\s*#(\d+)\s*\|\s*([→↑↓🆕\-]+)\s*\|\s*([\d,]+)\s*\|\s*([^|\n]+?)\s*\|\s*([^|\n]+?)\s*\|',
            _brief
        ):
            _kw, _pos_s, _wow, _vol_s, _url, _st = _m.groups()
            _pos = int(_pos_s)
            _vol = int(_vol_s.replace(',', ''))
            # Rough traffic estimate: top-3 ~20% CTR, pos 4-10 ~5%, pos 11-20 ~1%
            _ctr = 0.20 if _pos <= 3 else (0.05 if _pos <= 10 else 0.01)
            _traffic = max(1, round(_vol * _ctr))
            _status = "top-3" if _pos <= 3 else ("quick-win" if _pos <= 10 else ("growth" if _pos <= 20 else "low"))
            _url_clean = _url.strip()
            if _url_clean in ("—", "-", ""):
                _url_clean = "/"
            _kw_rows.append({
                "keyword": _kw.strip(),
                "position": _pos,
                "volume": _vol,
                "traffic": _traffic,
                "cpc": None,
                "kd": None,
                "url": _url_clean,
                "status": _status,
            })

        if _kw_rows:
            tk_keywords    = sorted(_kw_rows, key=lambda k: k["traffic"], reverse=True)[:20]
            top3_kws       = [k for k in tk_keywords if k["position"] <= 3]
            top10_kws      = [k for k in tk_keywords if k["position"] <= 10]
            quick_win_kws  = sorted(
                [k for k in tk_keywords if 4 <= k["position"] <= 20 and k["volume"] >= 50],
                key=lambda k: k["position"]
            )[:10]
            tk_summary     = {
                "top_3_count":    len(top3_kws),
                "top_10_count":   len(top10_kws),
                "total_keywords": len(tk_keywords),
                "not_ranking":    0,
            }
            organic_traffic = sum(k["traffic"] for k in tk_keywords)

    # ── Final fallback: GSC top_queries when both Ahrefs and brief are empty ──
    if not tk_keywords:
        _gsc_all_q = gsc.get("top_queries") or []
        _gsc_kw_rows = []
        for q in sorted(_gsc_all_q, key=lambda x: x.get("clicks",0), reverse=True)[:20]:
            _qpos = round(q.get("position") or 0, 1)
            _qclicks = int(q.get("clicks") or 0)
            if _qclicks == 0:
                continue
            _qs = "top-3" if _qpos <= 3 else ("quick-win" if _qpos <= 10 else ("growth" if _qpos <= 20 else "low"))
            _gsc_kw_rows.append({
                "keyword":  q.get("query",""),
                "position": _qpos,
                "volume":   None,   # GSC doesn't provide monthly volume
                "traffic":  _qclicks,
                "cpc":      None,
                "kd":       None,
                "url":      "",
                "status":   _qs,
                "source":   "gsc",
            })
        if _gsc_kw_rows:
            tk_keywords = _gsc_kw_rows
            top3_kws    = [k for k in tk_keywords if k["position"] <= 3]
            top10_kws   = [k for k in tk_keywords if k["position"] <= 10]
            tk_summary  = {
                "top_3_count":    len(top3_kws),
                "top_10_count":   len(top10_kws),
                "total_keywords": len(tk_keywords),
                "not_ranking":    0,
            }
            organic_traffic = sum(k["traffic"] for k in tk_keywords)

    # ── Known referring domains (curated from SEO brief when Ahrefs unavailable) ──
    if not all_refdoms:
        domain_rating = domain_rating or 7
        total_refdoms = total_refdoms or 68
        quality_refdoms = [
            {"domain": "yellowpages.com.au",   "domain_rating": 68, "dofollow_links": 234, "note": "Already listed — optimise listing"},
            {"domain": "truelocal.com.au",     "domain_rating": 55, "dofollow_links": 244, "note": "Already listed — add photos & respond to reviews"},
            {"domain": "google.com",            "domain_rating": 98, "dofollow_links": 12,  "note": "Google Business Profile citations"},
            {"domain": "facebook.com",          "domain_rating": 96, "dofollow_links": 8,   "note": "Facebook page links back to site"},
            {"domain": "instagram.com",         "domain_rating": 93, "dofollow_links": 4,   "note": "Instagram bio link"},
        ]
        quality_refdoms_count = len(quality_refdoms)

    # GSC position breakdown — non-branded queries for ranking gap analysis
    BRAND_TERMS = ["chasing better", "chasingbetter", "chasing fitness", "cb247", "chasingbetter247"]
    def _is_branded(q):
        ql = (q.get("query") or "").lower()
        return any(b in ql for b in BRAND_TERMS)
    gsc_all_q = gsc.get("top_queries") or []
    gsc_nonbrand = [q for q in gsc_all_q if not _is_branded(q)]
    gsc_p11_25 = sorted(
        [q for q in gsc_nonbrand if 11 <= (q.get("position") or 0) <= 25],
        key=lambda q: q.get("impressions", 0), reverse=True
    )
    gsc_p4_10 = sorted(
        [q for q in gsc_nonbrand if 4 <= (q.get("position") or 0) < 11],
        key=lambda q: q.get("impressions", 0), reverse=True
    )

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
        "meta":   "live" if (meta_social and meta_social.get("total_spend", 0) > 0) else "manual-data",
    }

    # ── Report period label ───────────────────────────────────────────
    from datetime import datetime as _dt
    _dr = ga4.get("date_range") or {}
    try:
        _s = _dt.strptime(_dr.get("start", ""), "%Y-%m-%d")
        _e = _dt.strptime(_dr.get("end",   ""), "%Y-%m-%d") - __import__("datetime").timedelta(days=1)
        _report_period = f"{_s.strftime('%-d %b')} – {_e.strftime('%-d %b %Y')}"
    except Exception:
        _report_period = "25 May – 31 May 2026"

    return {
        "generated": now,
        "report_period": _report_period,
        "refresh_ts": _refresh_ts_fmt,
        "timestamps": _ts,
        "status": status,

        # Meta Ads — top-level key for Overview KPI card + full paid data for Meta Ads page
        "meta": {
            "total_spend":  meta_total_spend,
            "malaga_spend": meta_mal_spend,
            "ell_spend":    meta_ell_spend,
            "week_label":   meta_ads_latest.get("week_label", ""),
            # Full Graph API paid data — used by renderMeta() when CSV exports are absent
            "data_pulled_at": _fmt_ts(
                (ads or {}).get("last_updated") or (ads or {}).get("generated_at", "")
            ),
            "combined":   dict(meta_combined),
            "malaga_paid": dict(meta_ads_latest.get("malaga") or {}),
            "ell_paid":    dict(meta_ads_latest.get("ellenbrook") or {}),
            "top_ads":     (meta_ads_latest.get("ads") or [])[:10],
            "history": [
                {
                    "week_label": w.get("week_label", ""),
                    "spend":  safe_float((w.get("combined") or {}).get("spend")),
                    "clicks": safe_int((w.get("combined") or {}).get("clicks")),
                    "impr":   safe_int((w.get("combined") or {}).get("impr")),
                    "ctr":    safe_float((w.get("combined") or {}).get("ctr")),
                    "cpm":    safe_float((w.get("combined") or {}).get("cpm")),
                    "cpc":    safe_float((w.get("combined") or {}).get("cpc")),
                }
                for w in meta_ads_list[:4]
            ],
        },

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
            "period": _report_period,
        },

        # GSC
        "gsc": {
            "clicks": gsc_clicks, "impressions": gsc_impr,
            "ctr": gsc_ctr, "position": gsc_pos,
            "top_queries": [{"query": q.get("query",""), "clicks": q.get("clicks",0), "impressions": q.get("impressions",0), "ctr": round(q.get("ctr",0)*100,1), "position": round(q.get("position",0),1)} for q in top_queries],
        },

        # Google Ads
        "google_ads": {
            "api_status": _gads_error_msg or "ok",
            # When api_status != "ok", figures below are from last_good_week (fallback)
            "last_good_week": _last_good_gads_label,
            "data_pulled_at": _fmt_ts((ads or {}).get("generated_at", "")),
            "spend": ads_spend, "p_spend": p_spend,
            "cpa": ads_cpa, "clicks": ads_clicks, "convs": ad_convs,
            "spend_chg": pct_change(ads_spend, p_spend),
            "malaga": {"spend": safe_float(mal.get("spend")), "cpa": safe_float(mal.get("cpa")), "clicks": safe_int(mal.get("clicks")), "conv": safe_int(mal.get("conv")), "ctr": safe_float(mal.get("ctr"))},
            "ellenbrook": {"spend": safe_float(ell.get("spend")), "cpa": safe_float(ell.get("cpa")), "clicks": safe_int(ell.get("clicks")), "conv": safe_int(ell.get("conv")), "ctr": safe_float(ell.get("ctr"))},
            "trend_labels": trend_labels, "trend_spend": trend_spend, "trend_cpa": trend_cpa,
            "campaigns": [{"name": c.get("name","")[:35], "spend": safe_float(c.get("spend")), "clicks": safe_int(c.get("clicks")), "conv": safe_int(c.get("conv")), "cpa": safe_float(c.get("cpa")), "location": c.get("location","")} for c in campaigns if safe_float(c.get("spend") or 0) > 0][:10],
            "keywords": [],
            "week_label": _last_good_gads_label if _gads_error_msg else _report_period,
            "csv_clicks": 0,
            "csv_cost": 0,
            "csv_conv": 0,
            "bidding": {"new_recs": [
                {"keyword": "gym malaga", "vol": "590", "bid": "$2.50", "priority": "High", "reason": "Core target — top 3 organic not yet achieved. Paid coverage essential while SEO builds."},
                {"keyword": "24/7 gym malaga", "vol": "260", "bid": "$2.80", "priority": "High", "reason": "High-intent modifier. CB247 brand fits perfectly. Lower competition than generic 'gym malaga'."},
                {"keyword": "gym ellenbrook perth", "vol": "390", "bid": "$2.40", "priority": "High", "reason": "Primary Ellenbrook keyword — currently no dedicated paid coverage for this location."},
                {"keyword": "reformer pilates perth", "vol": "880", "bid": "$3.20", "priority": "High", "reason": "Premium service differentiator. Revo Fitness bids on this — defend share and highlight 24/7 access."},
                {"keyword": "gym with sauna perth", "vol": "170", "bid": "$2.60", "priority": "Medium", "reason": "Sauna + ice bath is a unique CB247 offering. Low competition, high purchase intent."},
                {"keyword": "kids gym malaga", "vol": "140", "bid": "$2.20", "priority": "Medium", "reason": "Kids Hub is unique in area. Parents searching = high conversion intent and long membership tenure."},
                {"keyword": "fifo gym membership perth", "vol": "210", "bid": "$2.90", "priority": "Medium", "reason": "FIFO freeze is a unique CB247 offer. Target workers home between rotations — high value members."},
            ]},
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
            "top_pages": (
                [
                    {
                        "url":     p.get("url","").replace("https://www.chasingbetter247.com.au","") or "/",
                        "traffic": p.get("sum_traffic") or 0,
                        "top_kw":  p.get("top_keyword",""),
                        "pos":     p.get("top_keyword_best_position"),
                        "kw_count":p.get("keywords") or 0,
                        "ref_doms":p.get("referring_domains") or 0,
                        "source":  "ahrefs",
                    }
                    for p in ah_pages[:12]
                ] if ah_pages else [
                    {
                        "url":     (p.get("page","") or "").replace("https://www.chasingbetter247.com.au","") or "/",
                        "traffic": safe_int(p.get("clicks", 0)),
                        "top_kw":  "",
                        "pos":     round(safe_float(p.get("position") or 0), 1) if p.get("position") else None,
                        "kw_count": 0,
                        "ref_doms": 0,
                        "source":  "gsc",
                    }
                    for p in gsc_top_pages[:12]
                    if safe_int(p.get("clicks", 0)) > 0
                ]
            ),
            "top_pages_source": "ahrefs" if ah_pages else "gsc",
            "gsc_p11_25": [
                {
                    "keyword":     q.get("query",""),
                    "position":    round(q.get("position") or 0, 1),
                    "impressions": q.get("impressions",0),
                    "clicks":      q.get("clicks",0),
                    "ctr":         round((q.get("ctr") or 0)*100, 1),
                }
                for q in gsc_p11_25
            ],
            "gsc_p4_10": [
                {
                    "keyword":     q.get("query",""),
                    "position":    round(q.get("position") or 0, 1),
                    "impressions": q.get("impressions",0),
                    "clicks":      q.get("clicks",0),
                    "ctr":         round((q.get("ctr") or 0)*100, 1),
                }
                for q in gsc_p4_10
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

        # Agent Outputs — weekly intelligence from 9-agent pipeline
        "agent_outputs": load_agent_outputs(),
        "raw_agent_outputs": load_all_agent_outputs(),
    }


CONTENT_ITEMS = [
    {
        "id": "p1", "day": 0, "platform": "gbp", "type": "GBP Post",
        "title": "GBP Post — Sauna & Ice Bath",
        "assignee": "Tia", "assigneeRole": "Director",
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
        "assignee": "AI", "assigneeRole": "Content Agent",
        "caption": "Targeting 'best gym Malaga' — 320 searches/month. H1: 'The Best Gym in Malaga? Here's Why 8,000 Members Chose CB247'. Full outline and keyword map ready.",
        "instructions": "AI drafts full post. Target keyword: 'best gym malaga' (320/mo, KD 18). Secondary: 'gym malaga perth', 'cheap gym malaga'. Word count: 1,200–1,500 words. Structure: H1 → Intro (lead with price + facilities) → H2: What Makes a Great Gym in Malaga? → H2: CB247 Malaga Facilities (list all: 24/7, Kids Hub, Sauna, Ice Bath, Reformer Pilates, Neon21) → H2: Pricing Comparison (CB247 vs Revo vs Anytime) → H2: Member Reviews → H2: FAQ → CTA: 'Join from $11.95/week'. Internal links: homepage, Malaga page, pricing page. Angela reviews for brand voice. Mark publishes to WordPress.",
        "kw": "best gym malaga", "dueDate": "+2",
        "draftLink": "https://cb247agent.github.io/cb_claude/blog-drafts/best-gym-malaga.html",
        "draftReviewers": "Angela (Brand Manager / QC)",
    },
    {
        "id": "p4", "day": 2, "platform": "instagram", "type": "Instagram Post",
        "title": "Instagram — Kids Hub",
        "assignee": "Shauna", "assigneeRole": "Assets Creator",
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
        "assignee": "Tia", "assigneeRole": "Director",
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
        "assignee": "AI", "assigneeRole": "Content Agent",
        "caption": "Member spotlight + this week's class timetable + sauna booking tip",
        "instructions": "AI drafts full email. Subject line options (A/B test): A: 'This week at CB247 🏋️' / B: 'Your sauna booking tip + class times'. Structure: 1) Member spotlight (150 words, real story) → 2) This week's class timetable → 3) Sauna tip (e.g. 'Book Mon/Wed 6–7am — least busy') → 4) One referral nudge ('Bring a friend, 2 weeks free'). Angela reviews before send. Send via Mailchimp. List segment: active members. Send time: Monday 6am.",
        "kw": "", "dueDate": "+8",
    },
    {
        "id": "p9", "day": 9, "platform": "blog", "type": "SEO Blog Post",
        "title": "Blog — FIFO Gym Membership Perth",
        "assignee": "AI", "assigneeRole": "Content Agent",
        "caption": "Ads-to-Organic P3. GSC: fifo gym membership pos 7.2, 15 imp/wk. ACTION: add homepage internal link to push to pos 4–5. Draft live.",
        "instructions": "Ads-to-Organic Priority 3 — 3 Jun 2026.\n\nGSC: fifo gym membership pos 7.2, 15 imp/wk, 1 click.\nDraft: https://cb247agent.github.io/cb_claude/blog-drafts/fifo-gym-membership-perth.html\n\nACTION REQUIRED (do this week — adds 2–3 organic positions):\n→ Add FIFO freeze mention + link to this blog from the CB247 homepage\n→ Add internal link from /memberships page FIFO section\n→ Monitor GSC weekly after links are live\n\nPublish at: /blog/fifo-gym-membership-perth\nCompliance: outputs/research/compliance-review-blogs-2026-06-03.md — CONDITIONAL APPROVAL.",
        "kw": "fifo gym membership perth", "dueDate": "+9",
        "draftLink": "https://cb247agent.github.io/cb_claude/blog-drafts/fifo-gym-membership-perth.html",
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
        "assignee": "Tia", "assigneeRole": "Director",
        "caption": "Ellenbrook locals — your neighbourhood gym is here. 24/7 access, no lock-in, $11.95/week.",
        "instructions": "Post ONLY to Ellenbrook GBP profile (not Malaga). Hyperlocal focus — use 'Ellenbrook' 2–3 times in the post. Photo: Ellenbrook location exterior or interior. Geo-tagged post. Mention Swan Valley proximity if relevant. Local keywords: 'gym ellenbrook perth'. Post Thursday morning.",
        "kw": "gym ellenbrook perth", "dueDate": "+11",
    },
    {
        "id": "p12", "day": 13, "platform": "instagram", "type": "Instagram Post",
        "title": "Community Post — Member Story",
        "assignee": "Shauna", "assigneeRole": "Assets Creator",
        "caption": "Member story: how CB247 helped [member] hit their goal. Real stories, real results.",
        "instructions": "Shauna captures photo/video asset. AI writes the carousel copy and caption from the story notes. Ask reception to nominate a member who has hit a milestone this month. Get written consent + photo. Format: carousel post (3–5 slides). Slide 1: Bold quote from member. Slides 2–3: Journey story in short paragraphs. Slide 4: Their goal and result. Slide 5: CTA — 'Start your story. $11.95/week, no lock-in.' Tag the member (if they consent). Angela QCs before scheduling.",
        "kw": "", "dueDate": "+13",
    },
    {
        "id": "p13", "day": 16, "platform": "blog", "type": "SEO Blog Post",
        "title": "Blog — Best Gym Ellenbrook",
        "assignee": "AI", "assigneeRole": "Content Agent",
        "caption": "Ads-to-Organic P2. gym ellenbrook pos 3.7, 19 imp/wk. Ellenbrook Gym campaign $128/wk. Draft live — review and publish.",
        "instructions": "Ads-to-Organic Priority 2 — 3 Jun 2026.\n\nTarget: gym ellenbrook / ellenbrook gym / 24/7 gym ellenbrook / family gym ellenbrook.\nICP: young families + shift workers + newcomers.\nCurrent GSC pos: 3.7 — target pos 1–2.\n\nDraft: https://cb247agent.github.io/cb_claude/blog-drafts/gym-ellenbrook-perth.html\nPublish at: /blog/gym-ellenbrook-perth\n\nOnce pos 1–2: pause Ellenbrook Gym campaign ($128/wk saving).\nAdd internal link from Ellenbrook location page + homepage.\n\nCompliance: outputs/research/compliance-review-blogs-2026-06-03.md — CONDITIONAL APPROVAL.",
        "kw": "gym ellenbrook", "dueDate": "+16",
        "draftLink": "https://cb247agent.github.io/cb_claude/blog-drafts/gym-ellenbrook-perth.html",
    },
    {
        "id": "p14", "day": 23, "platform": "blog", "type": "SEO Blog Post",
        "title": "Blog — Reformer Pilates Malaga",
        "assignee": "AI", "assigneeRole": "Content Agent",
        "caption": "Ads-to-Organic P4. Pilates campaign paused — organic content fills the gap. Draft live.",
        "instructions": "Ads-to-Organic Priority 4 — 3 Jun 2026.\n\nPilates campaign was paused (CPL too high). Organic gap confirmed.\nTarget: reformer pilates malaga / pilates classes malaga / pilates ellenbrook.\nICP: recovery-focused, women 25–45. Trend: #hotgirlwalk.\n\nDraft: https://cb247agent.github.io/cb_claude/blog-drafts/reformer-pilates-malaga.html\nPublish at: /blog/reformer-pilates-malaga\n\nBEFORE PUBLISHING: verify Perth Pilates studio pricing ($25–$40/class claim).\nCompliance: outputs/research/compliance-review-blogs-2026-06-03.md — CONDITIONAL APPROVAL.",
        "kw": "reformer pilates malaga", "dueDate": "+23",
        "draftLink": "https://cb247agent.github.io/cb_claude/blog-drafts/reformer-pilates-malaga.html",
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
        "Assets Creator": "#fef9c3",
        "Web Developer": "#ede9fe",
        "QC Manager": "#fee2e2",
        "Brand Manager": "#fee2e2",
        "Content Agent": "#e0f2fe",
        "Marketing Manager": "#f3e8ff",
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

        reviewers = item.get("draftReviewers", "Angela (Brand Manager / QC)")
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
.main{margin-left:var(--sidebar-w);flex:1;display:flex;flex-direction:column;height:100vh;overflow-y:auto}
.topbar{background:var(--card);border-bottom:1px solid var(--border);padding:0 28px;height:52px;display:flex;align-items:center;position:sticky;top:0;z-index:50;flex-shrink:0}
.content{padding:28px;max-width:1400px;width:100%;box-sizing:border-box;padding-bottom:60px}

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
.insight.green{background:var(--teal-mist);border-color:rgba(63,166,154,.25);border-left:3px solid var(--teal)}
.insight.red{background:#fff5f5;border-color:#fecaca;border-left:3px solid #ef4444}
.insight.amber{background:#fffbeb;border-color:#fde68a;border-left:3px solid #f59e0b}
.insight.neutral{background:#f9f9f9;border-left:3px solid var(--border-strong)}
.insight.warn{background:#fffbeb;border-color:#fde68a;border-left:3px solid #f59e0b}
.insight-label{font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-bottom:5px}
.insight.red .insight-label{color:#b91c1c}
.insight.amber .insight-label{color:#92400e}
.insight.teal .insight-label,.insight.green .insight-label{color:var(--teal-dim)}

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
    <div class="sub" style="margin-top:4px;color:rgba(255,255,255,.55);font-size:9px">WEEK: <span id="sidebar-week"></span></div>
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
    <div class="sidebar-item" data-page="action-tracker" onclick="nav(this)">
      Action Tracker
      <span class="badge neutral" id="tracker-badge">0</span>
    </div>
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
      <div class="kpi-grid cols-4 mb" id="overview-kpis"></div>

      <!-- Insight strip -->
      <div id="overview-insights"></div>

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
      <div class="page-header">
        <h1>Organic Social</h1>
        <p>Instagram · Facebook · Google Business Profile organic performance</p>
      </div>
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
        <p>Plan, approve, and track every piece of content — blogs, Instagram, TikTok, GBP posts, and emails — across a 2-week rolling schedule. Move cards through the workflow as they progress from draft to published.</p>
      </div>
      <div id="planner-content"></div>
    </div>

    <!-- ══ PAGE: CONTENT REVIEW ═════════════════════════════════════ -->
    <div class="page" id="page-content-review">
      <div class="page-header">
        <h1>Content Review</h1>
        <p>Review performance of published content — track what worked, what needs adjustment, and feed learnings back into the next planning cycle.</p>
      </div>
      <div id="review-content"></div>
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
        <div style="font-size:11px;color:var(--muted);margin-top:8px">Share with Angela (Brand Manager) for QC review before publish</div>
      </div>
      <div class="modal-approval">
        <div class="modal-section-label" style="margin-bottom:4px">Approval Decision</div>
        <div style="font-size:10px;color:var(--muted);margin-bottom:10px">Approved moves the card to the next stage. Rejected sends it back to Idea.</div>
        <div class="approval-btns">
          <button class="appr-pill" id="apill-approved" onclick="setModalApproval('approved')">Approved — advance stage</button>
          <button class="appr-pill" id="apill-adjustment" onclick="setModalApproval('adjustment')">Needs Adjustment</button>
          <button class="appr-pill" id="apill-rejected" onclick="setModalApproval('rejected')">Rejected — back to Idea</button>
        </div>
        <div id="modal-notes-wrap" style="display:none">
          <div class="modal-section-label" style="margin-bottom:4px">Adjustment Instructions</div>
          <textarea class="modal-notes" id="modal-notes" placeholder="Describe exactly what needs to change — e.g. &quot;Soften the headline, remove the price comparison in paragraph 3&quot;"></textarea>
          <div id="modal-adjust-status" style="display:none;margin-top:8px;padding:10px 14px;border-radius:4px;font-size:12px;font-weight:500;line-height:1.5"></div>
        </div>
      </div>
    </div>
    <div class="modal-foot">
      <a class="brief-link" id="modal-brief-link" href="#" target="_blank">View Brief</a>
      <div style="display:flex;gap:8px">
        <button class="btn-ghost" onclick="closePlannerModal()">Close</button>
        <button class="btn-teal" id="modal-save-btn" onclick="saveModalAndClose()">Save</button>
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
const insightTypeMap = {'green':'teal','red':'red','amber':'amber','blue':'neutral','teal':'teal'};
const insight = (type,label,text) => `
  <div class="insight ${insightTypeMap[type]||'neutral'}">
    <div class="insight-label">${label}</div>
    ${text}
  </div>`;
const sectionTitle = t => `<div class="section-title">${t}</div>`;

// ── Global shared helpers ──────────────────────────────────────────────────────
function rankBadge(r) {
  if (!r) return '';
  if (r.includes('Above')) return '<span style="font-size:9px;background:#e8f5f4;color:#00c4b4;padding:1px 5px;border-radius:3px;font-weight:700">Above avg</span>';
  if (r.includes('Below')) return '<span style="font-size:9px;background:#fff5f5;color:#ef4444;padding:1px 5px;border-radius:3px;font-weight:700">Below avg</span>';
  return '<span style="font-size:9px;background:#f0f2f5;color:var(--muted);padding:1px 5px;border-radius:3px">Average</span>';
}
function tierBadge(t) {
  if (t==='star') return '<span style="font-size:9px;background:#e8f5f4;color:#00c4b4;padding:2px 7px;border-radius:3px;font-weight:700">⭐ Star</span>';
  if (t==='good') return '<span style="font-size:9px;background:#fff8e1;color:#d97706;padding:2px 7px;border-radius:3px;font-weight:700">Good</span>';
  if (t==='poor') return '<span style="font-size:9px;background:#fff5f5;color:#ef4444;padding:2px 7px;border-radius:3px;font-weight:700">Poor</span>';
  return '<span style="font-size:9px;background:#f0f2f5;color:var(--muted);padding:2px 7px;border-radius:3px">Average</span>';
}
function agentBrief(title, text) {
  return `${sectionTitle('🤖 AI Brief — ' + title)}
  <div class="insight teal mb">
    <div class="insight-label">Agent priorities · This week's recommended actions</div>
    ${text}
  </div>`;
}

// ── Agent markdown renderer ────────────────────────────────────────────────────
function formatAgentMd(text) {
  if (!text) return '<p style="color:var(--muted)">No agent data for this period.</p>';
  return text
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
    .replace(/^# (.+)$/gm,'<h3 style="margin:18px 0 6px;color:var(--teal);font-size:14px">$1</h3>')
    .replace(/^## (.+)$/gm,'<h4 style="margin:14px 0 5px;color:var(--text);font-size:13px;border-bottom:1px solid var(--border);padding-bottom:4px">$1</h4>')
    .replace(/^### (.+)$/gm,'<h5 style="margin:10px 0 3px;color:var(--text);font-size:12px">$1</h5>')
    .replace(/^---$/gm,'<hr style="border:none;border-top:1px solid var(--border);margin:10px 0">')
    .replace(/^- (.+)$/gm,'<li style="margin:2px 0 2px 16px;font-size:12px">$1</li>')
    .replace(/\n\n/g,'</p><p style="margin:6px 0;font-size:12px;line-height:1.6">')
    .replace(/\n/g,'<br>');
}

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
  const metaSpend   = (D.meta&&D.meta.total_spend)||0;
  const totalSpend  = ads.spend + metaSpend;
  const organicMult = totalSpend > 0 ? Math.round(s.organic_value / totalSpend * 10) / 10 : 0;
  const mal = D.gbp.malaga, ell = D.gbp.ellenbrook;

  // ── 4 KPI cards ──────────────────────────────────────────────────────────
  $('overview-kpis').innerHTML =
    kpiCard('','Weekly Sessions', fmt(g.sessions,'n'), g.ses_chg, `Prior week: ${fmt(g.p_sessions,'n')}`, g.ses_chg<-10?'red':g.ses_chg>5?'green':'') +
    kpiCard('','Conversions',     fmt(g.convs,'n'),    g.conv_chg, `Conv. rate: ${fmt(g.conv_rate,'%')}`, g.conv_chg>0?'green':'') +
    kpiCard('','Total Ad Spend',  fmt(totalSpend,'$2'),ads.spend_chg, metaSpend>0?`Google ${fmt(ads.spend,'$2')} · Meta ${fmt(metaSpend,'$2')}`:`CPA: ${fmt(ads.cpa,'$2')}`) +
    kpiCard('','Organic Value',   fmt(s.organic_value,'$')+'/wk', null, organicMult>1?`${organicMult}× return vs ad spend`:`DR ${s.domain_rating||'–'} · ${s.tk_summary.top_3_count||0} top-3 keywords`, 'green');

  // ── Insight strip ─────────────────────────────────────────────────────────
  const insightEl = document.getElementById('overview-insights');
  if (insightEl) {
    const sesDown = (g.ses_chg||0) < -10;
    const cpaHigh = ads.cpa > 15 && ads.cpa > 0;
    insightEl.innerHTML = `<div class="grid-2 mb">
      <div class="insight ${sesDown||cpaHigh?'red':'amber'}">
        <div class="insight-label">${sesDown ? '⚠️ Traffic Drop — Investigate' : cpaHigh ? '⚠️ CPA Above $15 — Review Campaigns' : '⚠️ Watch: Paid Social Conversions'}</div>
        ${sesDown
          ? `Sessions fell <b>${Math.abs(g.ses_chg||0)}% WoW</b> (${fmt(g.p_sessions,'n')} → ${fmt(g.sessions,'n')}). Check which channel dropped in GA4 — most likely paid campaign paused or a ranking lost.`
          : cpaHigh
          ? `Blended CPA is <b>${fmt(ads.cpa,'$2')}</b> — above the $15 target. Malaga: ${fmt(ads.malaga.cpa,'$2')} · Ellenbrook: ${fmt(ads.ellenbrook.cpa,'$2')}. Review low-converting campaigns and pause underperformers.`
          : `Meta Ads spent <b>${fmt(metaSpend,'$2')}</b> this week. Ensure conversion events are firing in Meta Events Manager — disconnected tracking inflates CPR.`
        }
      </div>
      <div class="insight teal">
        <div class="insight-label">${organicMult>1 ? `✅ Organic Delivers ${organicMult}× More Value Than Paid` : '✅ Conversion Rate Strong'}</div>
        ${organicMult>1
          ? `SEO organic is worth <b>${fmt(s.organic_value,'$')}/wk</b> vs <b>${fmt(totalSpend,'$2')}</b> in ad spend. Organic traffic compounds — every page published keeps delivering without paying per click.`
          : `CB247 converts at <b>${fmt(g.conv_rate,'%')}</b> — well above the gym industry average of 5–8%. The site copy and UX are working.`
        }
        <br><br><b>Organic top-3 rankings:</b> ${s.tk_summary.top_3_count||0} keywords &nbsp;·&nbsp; <b>GBP:</b> Malaga ${mal.rating}⭐ (${fmt(mal.reviews,'n')} reviews) &nbsp;·&nbsp; Ellenbrook ${ell.rating}⭐ (${fmt(ell.reviews,'n')} reviews)
      </div>
    </div>`;
  }

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
  const gbp = D.gbp;
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
  const s = D.seo;
  const qw = s.quick_wins || [];
  const _ao_seo = D.raw_agent_outputs || {};
  const _h = (_ao_seo.seo_highlights) || {};

  // ── 1. KPI cards — always first ──────────────────────────────────────────
  let html = `<div class="kpi-grid cols-4 mb">
    ${kpiCard('','SEO Health Score', s.health_score+'/100', null,
      s.health_score>=70?'Strong — maintain momentum':s.health_score>=40?'Building — keep publishing':'Early stage — focus on quick wins',
      s.health_score>=70?'green':s.health_score>=40?'amber':'red')}
    ${kpiCard('','Organic Traffic', fmt(s.organic_traffic,'n'), null, 'Monthly visits from search')}
    ${kpiCard('','Domain Rating', s.domain_rating||'–', null, `${s.quality_refdoms_count||0} quality referring domains`)}
    ${kpiCard('','Page 1 Keywords', s.tk_summary.top_10_count||0, null,
      `${s.tk_summary.top_3_count||0} in top 3 · ${s.tk_summary.total_keywords||0} total tracking`)}
  </div>`;

  // ── 2. Insight strip (red left, teal right) — always 2 cards ───────────────
  const topQW   = qw[0];
  const p11_25  = s.gsc_p11_25 || [];
  const p4_10   = s.gsc_p4_10  || [];
  const gsc_top3 = (s.gsc_queries||[]).filter(q=>q.position<=3);
  html += sectionTitle('Key Observations');
  html += `<div class="grid-2 mb">
    <div class="insight red">
      <div class="insight-label">⚠️ Ranking Gap — Page 2+ Keywords Getting Near-Zero Clicks</div>
      <b>${p11_25.length || 'Several'} non-branded keyword${p11_25.length!==1?'s':''}</b> rank positions 11–25.
      Page 2 CTR averages 0.5% — these keywords exist in Google's index but no searcher ever sees them.
      The fix is <b>dedicated landing pages</b> — one page per keyword, not tweaking existing content.
      ${p11_25.length > 0
        ? `<br><br>${p11_25.slice(0,5).map(k=>{const slug=k.keyword.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');return`<div style="display:flex;justify-content:space-between;font-size:11px;padding:3px 0;border-bottom:1px solid rgba(239,68,68,.1)"><span style="font-weight:600">${k.keyword}</span><span>${posBadge(k.position)} <span style="color:var(--muted);font-size:10px">→ /${slug}/</span></span></div>`}).join('')}
          <p style="font-size:10px;color:var(--muted);margin-top:8px">Source: GSC 7-day · Non-branded only</p>`
        : '<br><br><span style="color:var(--muted);font-size:12px">Connect Ahrefs API to see full keyword universe.</span>'}
      <br><b>Authority gap:</b> CB247 DR ${s.domain_rating||'—'} · ${s.quality_refdoms_count||0} quality referring domains. Target: 2 new quality links/month via True Local, Yelp Australia.
    </div>
    <div class="insight teal">
      <div class="insight-label">✅ What's Working — Top 3 Positions</div>
      CB247 ranks <b>top 3</b> for <b>${gsc_top3.length} queries</b> — zero ad spend, high CTR.
      ${gsc_top3.length > 0
        ? '<br><br>' + gsc_top3.slice(0,5).map(q=>`<div style="display:flex;justify-content:space-between;font-size:11px;padding:3px 0;border-bottom:1px solid rgba(63,166,154,.1)"><span>${q.query}</span><span>${posBadge(q.position)} <span style="color:var(--muted)">${fmt(q.clicks,'n')} clicks</span></span></div>`).join('')
        : '<br><br><span style="color:var(--muted);font-size:12px">No GSC data — run pull_gsc.py.</span>'}
      ${p4_10.length > 0 ? `<br><b>Quick wins (pos 4–10):</b> ${p4_10.slice(0,3).map(k=>`<span style="font-weight:600">${k.keyword}</span> ${posBadge(k.position)}`).join(' · ')} — update H1 + meta to push these to top 3.` : ''}
      <br><br><b>Protect these:</b> Add internal links from every new blog post back to these pages. Never change URL slugs without 301 redirects.
    </div>
  </div>`;

  // ── Top 10 keywords by traffic (compact) ────────────────────────────────────
  const top10 = (s.keywords||[]).slice(0, 10);
  const kwSource = top10.length > 0 && top10[0].source === 'gsc' ? 'gsc' : (top10.length > 0 ? 'ahrefs' : 'none');
  const statusPill = {
    'top-3':     '<span style="font-size:9px;background:#e8f5f4;color:#00c4b4;padding:1px 6px;border-radius:3px;font-weight:700">Top 3</span>',
    'quick-win': '<span style="font-size:9px;background:#fff8e1;color:#d97706;padding:1px 6px;border-radius:3px;font-weight:700">Quick Win</span>',
    'growth':    '<span style="font-size:9px;background:#f0f2f5;color:var(--muted);padding:1px 6px;border-radius:3px">Growth</span>',
    'low':       '<span style="font-size:9px;background:#f0f2f5;color:var(--muted-2);padding:1px 6px;border-radius:3px">Low</span>',
  };
  html += sectionTitle('Top 10 Keywords by Traffic');
  html += `<div class="card mb"><table>
    <thead><tr>
      <th>Keyword</th>
      <th class="num">Pos</th>
      ${kwSource!=='gsc'?'<th class="num">Vol/mo</th>':''}
      <th class="num">${kwSource==='gsc'?'Clicks (7d)':'Traffic'}</th>
      ${kwSource!=='gsc'?'<th class="num">KD</th><th class="num">CPC</th>':''}
      <th>Status</th>
      <th style="font-size:10px">Action</th>
    </tr></thead><tbody>
    ${top10.map(kw=>{
      const isQW = kw.status==='quick-win';
      const pos  = typeof kw.position==='number' ? kw.position : parseFloat(kw.position||99);
      const action = pos<=3
        ? 'Protect — add internal links'
        : pos<=10
          ? 'Optimise H1 + meta description'
          : 'Build dedicated landing page';
      return `<tr ${isQW?'style="background:#fffbeb"':''}>
        <td style="font-weight:${pos<=3?'700':'400'}">${kw.keyword}</td>
        <td class="num">${posBadge(pos)}</td>
        ${kwSource!=='gsc'?`<td class="num" style="color:var(--muted)">${kw.volume?fmt(kw.volume,'n'):'–'}</td>`:''}
        <td class="num" style="font-weight:600">${fmt(kw.traffic,'n')}</td>
        ${kwSource!=='gsc'?`<td class="num" style="color:var(--muted);font-size:10px">${kw.kd||'–'}</td><td class="num" style="color:var(--muted);font-size:10px">${kw.cpc ? '$'+kw.cpc : '–'}</td>`:''}
        <td>${statusPill[kw.status]||'–'}</td>
        <td style="font-size:10px;color:var(--text-2)">${action}</td>
      </tr>`;
    }).join('')||'<tr><td colspan="8" style="color:var(--muted);padding:16px">No keyword data — Ahrefs API units exhausted. Data resets on next billing date.</td></tr>'}
    </tbody></table>
    <p style="font-size:10px;color:var(--muted);padding:8px 4px 0">
      ${kwSource==='gsc'
        ? 'Source: Google Search Console (7-day clicks + avg. position). Connect Ahrefs for monthly volume and KD.'
        : kwSource==='ahrefs'
          ? 'Showing top 10 by monthly traffic. Quick Win = positions 4–20 with volume ≥50 — highest ROI SEO actions.'
          : 'Source: weekly SEO brief. Showing top 10 by estimated traffic.'}
    </p>
  </div>`;

  // ── Search Console + Top Pages (side by side, compact) ─────────────────────
  html += sectionTitle('Search Console — Top Queries (7 days: 25–31 May)');
  html += `<div class="grid-2 mb">
    <div class="card">
      <div class="card-h">Top 10 Queries by Clicks</div>
      <table><thead><tr>
        <th>Query</th><th class="num">Clicks</th><th class="num">CTR</th><th class="num">Pos</th>
      </tr></thead><tbody>
      ${(s.gsc_queries||[]).slice(0,10).map(q=>`<tr>
        <td style="font-size:11px">${q.query}</td>
        <td class="num">${fmt(q.clicks,'n')}</td>
        <td class="num">${q.ctr}%</td>
        <td class="num">${posBadge(q.position)}</td>
      </tr>`).join('')||'<tr><td colspan="4" style="color:var(--muted)">No GSC data — run pull_gsc.py</td></tr>'}
      </tbody></table>
    </div>
    <div class="card">
      <div class="card-h">Top Pages by Organic Traffic
        <span class="card-period">${s.top_pages_source==='gsc'?'Source: GSC clicks (Ahrefs not connected)':'Source: Ahrefs'}</span>
      </div>
      <table><thead><tr>
        <th>Page</th><th class="num">${s.top_pages_source==='gsc'?'Clicks':'Traffic'}</th><th>${s.top_pages_source==='gsc'?'Avg Pos':'Top KW'}</th><th class="num">Pos</th>
      </tr></thead><tbody>
      ${(s.top_pages||[]).slice(0,10).map(p=>`<tr>
        <td style="font-size:10px;color:var(--text-2);max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${(p.url||'/').replace('https://www.chasingbetter247.com.au','')}</td>
        <td class="num">${fmt(p.traffic,'n')}</td>
        <td style="font-size:10px;color:var(--muted);max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${p.top_kw||'–'}</td>
        <td class="num">${posBadge(p.pos)}</td>
      </tr>`).join('')||'<tr><td colspan="4" style="color:var(--muted)">No page data</td></tr>'}
      </tbody></table>
    </div>
  </div>`;

  // ── Backlinks (compact, side by side) ───────────────────────────────────────
  const _refdomsCurated = s.referring_domains && s.referring_domains.length > 0 && s.referring_domains[0].note;
  html += sectionTitle('Backlink Profile');
  html += `<div class="grid-2 mb">
    <div class="card">
      <div class="card-h">Quality Referring Domains (DR 40+)
        <span class="card-period">${_refdomsCurated?'Source: SEO brief · Ahrefs refreshing':'Source: Ahrefs'}</span>
      </div>
      <div style="font-size:11px;color:var(--muted);margin-bottom:8px">
        ${s.total_refdoms||0} total referring domains · DR ${s.domain_rating||'–'} · ${s.quality_refdoms_count||0} quality (DR 40+)
      </div>
      <table><thead><tr>
        <th>Domain</th><th class="num">DR</th><th class="num">Links</th>
        ${_refdomsCurated?'<th style="font-size:10px">Status / Action</th>':''}
      </tr></thead><tbody>
      ${(s.referring_domains||[]).slice(0,8).map(d=>`<tr>
        <td style="font-size:11px;font-weight:${(d.domain_rating||0)>=60?'600':'400'}">${d.domain||'–'}</td>
        <td class="num"><span style="font-size:10px;background:${(d.domain_rating||0)>=60?'#e8f5f4':'#f0f2f5'};color:${(d.domain_rating||0)>=60?'#00c4b4':'var(--muted)'};padding:1px 5px;border-radius:3px;font-weight:700">${d.domain_rating||'–'}</span></td>
        <td class="num" style="color:var(--muted)">${d.dofollow_links||0}</td>
        ${_refdomsCurated?`<td style="font-size:10px;color:var(--text-2)">${d.note||''}</td>`:''}
      </tr>`).join('')||`<tr><td colspan="4" style="padding:16px 12px">
        <div style="font-size:12px;color:var(--muted);line-height:1.6">
          No referring domain data. Ahrefs API units reset on next billing date.<br>
          <b style="color:var(--text-2)">Action: build 2 links this week —</b><br>
          <span style="font-size:11px">• yellowpages.com.au — already listed, optimise the listing<br>
          • truelocal.com.au — already listed, add photos + reply to reviews<br>
          • yelp.com.au — free listing, 30-min setup</span>
        </div>
      </td></tr>`}
      </tbody></table>
    </div>
    <div class="card">
      <div class="card-h">Recent Backlinks (last 30 days)
        <span class="card-period">${(s.recent_backlinks||[]).length>0?'Source: Ahrefs':'Ahrefs API refreshing'}</span>
      </div>
      <table><thead><tr>
        <th>From domain</th><th class="num">DR</th><th>Date</th>
      </tr></thead><tbody>
      ${(s.recent_backlinks||[]).slice(0,8).map(b=>`<tr>
        <td style="font-size:10px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:180px">${(b.url_from||'').replace(/https?:\/\//,'')}</td>
        <td class="num">${b.domain_rating_source||'–'}</td>
        <td style="font-size:10px;color:var(--muted)">${(b.first_seen||'').slice(0,10)}</td>
      </tr>`).join('')||`<tr><td colspan="3" style="padding:16px 12px">
        <div style="font-size:12px;color:var(--muted);line-height:1.6">
          <b style="color:var(--text-2)">No new backlinks in the last 30 days.</b><br>
          Last known backlink: May 13, 2026 (low-quality). <br>
          Current DR: <b>7</b> · Target: <b>10</b> (need 10–15 quality local links).<br><br>
          <b>This week's outreach targets (free):</b><br>
          <span style="font-size:11px">
          • <b>yelp.com.au</b> — DR 91 — create free business listing<br>
          • <b>healthengine.com.au</b> — DR 58 — list massage + wellness services<br>
          • <b>perthlocal.com.au</b> — DR 42 — local business directory<br>
          • <b>fitness.com.au</b> — DR 38 — gym listing page
          </span>
        </div>
      </td></tr>`}
      </tbody></table>
    </div>
  </div>`;

  // ── 5. Agent Brief — wins + top actions from SEO brief ─────────────────────
  const _wins    = _h.wins    || [];
  const _crits   = _h.critical|| [];
  const _actions = _h.top_actions || [];
  const _ov      = _h.organic_value || '';
  let briefText = '';
  if (_wins.length) {
    briefText += `<div style="margin-bottom:10px"><b>🟢 Big wins this week:</b><br>${_wins.map(w=>`✅ ${w}`).join('<br>')}</div>`;
    if (_ov) briefText += `<div style="margin-bottom:10px">💰 Organic value: <b>${_ov}</b></div>`;
  }
  if (_actions.length) {
    briefText += `<b>Top actions:</b><br>`;
    briefText += _actions.map((a,i)=>`<div style="margin:6px 0;padding:8px 12px;background:rgba(63,166,154,.06);border-radius:4px;border-left:3px solid var(--teal)"><b>${i+1}. ${a.title}</b><br><span style="font-size:11px;color:var(--muted)">${a.desc}</span></div>`).join('');
  }
  if (!briefText) {
    briefText = (topQW
      ? `<b>1. Quick win — "${topQW.keyword}" (pos #${topQW.position}, ${fmt(topQW.volume,'n')}/mo):</b> Update H1, meta title, meta description on ${topQW.url||'its page'}. Add 1 internal link from homepage. Can move to top 5 in 2–4 weeks.<br><br>`
      : '<b>1. Run pull_ahrefs.py</b> to load keyword data — quick win opportunities require ranking data.<br><br>') +
      `<b>2. Build missing pages:</b> "kids gym malaga", "sauna ice bath malaga", "fifo gym perth" — each needs a 500–800 word dedicated landing page.<br><br>
       <b>3. Homepage title tag fix:</b> Add "24/7 Gym Malaga WA" to &lt;title&gt; — 30-min WordPress edit, immediate ranking impact.<br><br>
       <b>4. Two quality backlinks:</b> True Local + Yelp Australia — free directories, permanent dofollow links.`;
  }
  html += agentBrief('SEO Agent', briefText);

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

  // ── API status banner ────────────────────────────────────────────────────
  let statusBanner = '';
  if (ads.api_status === 'rate_limited') {
    const lastWeek = ads.last_good_week ? ` — week of <strong>${ads.last_good_week}</strong>` : '';
    const pulledAt = ads.data_pulled_at ? `<span style="margin-left:8px;font-size:11px;background:rgba(146,64,14,.12);padding:2px 8px;border-radius:99px;font-weight:600">${ads.data_pulled_at}</span>` : '';
    statusBanner = `<div style="background:#fef9c3;border:1px solid #fbbf24;border-radius:8px;padding:14px 18px;margin-bottom:20px;display:flex;align-items:flex-start;gap:12px">
      <div>
        <div style="font-weight:700;color:#92400e;margin-bottom:6px">Google Ads API — Pending access upgrade${pulledAt}</div>
        <div style="font-size:12.5px;color:#78350f;line-height:1.7">
          API quota exhausted (Explorer-level token). Figures below are the <strong>last known real data${lastWeek}</strong> — not zeros.<br>
          They will auto-update once Basic Access is approved and the next pull runs.<br>
          <strong>Action:</strong> Google Ads → Tools &amp; Settings → API Centre → Apply for Basic Access (1–2 days).
        </div>
      </div>
    </div>`;
  } else if (ads.api_status === 'dns_error') {
    statusBanner = `<div style="background:#fee2e2;border:1px solid #fca5a5;border-radius:8px;padding:14px 18px;margin-bottom:20px">
      <strong style="color:#991b1b">Google Ads API — DNS error</strong><br>
      <span style="font-size:12px;color:#7f1d1d">Run <code>python3 scripts/pull_all.py</code> from Terminal to retry.</span>
    </div>`;
  } else if (ads.api_status === 'api_error') {
    statusBanner = `<div style="background:#fee2e2;border:1px solid #fca5a5;border-radius:8px;padding:14px 18px;margin-bottom:20px">
      <strong style="color:#991b1b">Google Ads API — Connection error</strong><br>
      <span style="font-size:12px;color:#7f1d1d">Check credentials and run <code>python3 scripts/pull_all.py</code>.</span>
    </div>`;
  }

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
  let html = statusBanner + `<div class="kpi-grid cols-4 mb">
    ${kpiCard('','Total Spend',fmt(totalSpend,'$2'),ads.spend_chg,`${totalClicks} clicks · ${weekLabel}`)}
    ${kpiCard('','Conversions',fmt(totalConv,'n'),null,`Blended CPA: ${fmt(blendedCPA,'$2')}`,(blendedCPA>50&&blendedCPA>0)?'red':'green')}
    ${kpiCard('','Malaga',fmt(malSpend||mal.spend,'$2'),null,`${malConv||mal.conv||0} conversions`)}
    ${kpiCard('','Ellenbrook',fmt(ellSpend||ell.spend,'$2'),null,`${ellConv||ell.conv||0} conversions`)}
  </div>`;

  // ── Insight strip ────────────────────────────────────────────────────────
  const wasteKwsQuick = kws.filter(k=>k.clicks>=5&&k.conv===0&&k.cost>10);
  const winnerKwTop   = [...kws].filter(k=>k.conv>0).sort((a,b)=>a.cost/a.conv-b.cost/b.conv)[0];
  html += sectionTitle('Key Observations');
  html += `<div class="grid-2 mb">
    <div class="insight ${(blendedCPA>15&&blendedCPA>0)||wasteKwsQuick.length>0?'red':'amber'}">
      <div class="insight-label">${blendedCPA>15&&blendedCPA>0?'⚠️ CPA Above Target — Review Campaigns':wasteKwsQuick.length>0?'⚠️ Budget Waste Detected — Pause These Keywords':'⚠️ Monitor — Account Stable'}</div>
      ${blendedCPA>15&&blendedCPA>0
        ? `Blended CPA is <b>${fmt(blendedCPA,'$2')}</b> — above the $15 target. Malaga: ${fmt(mal.cpa,'$2')} · Ellenbrook: ${fmt(ell.cpa,'$2')}. Review low-converting campaigns and pause underperformers.`
        : wasteKwsQuick.length>0
          ? `<b>${wasteKwsQuick.length} keyword${wasteKwsQuick.length>1?'s':''}</b> have 5+ clicks, 0 conversions, and $10+ spend this week. Total wasted: <b>$${wasteKwsQuick.reduce((s,k)=>s+k.cost,0).toFixed(2)}</b>. Pause these immediately and add as negative keywords.
            <br><br>${wasteKwsQuick.slice(0,3).map(k=>`<div style="font-size:11px;padding:3px 0;border-bottom:1px solid rgba(239,68,68,.1)"><b>${k.keyword}</b> — ${k.clicks} clicks, $${k.cost} wasted</div>`).join('')}`
          : `Account CPA (${fmt(blendedCPA,'$2')}) is within target. ${totalConv} conversions tracked at ${fmt(blendedCPA,'$2')} CPA. Continue current strategy.`
      }
    </div>
    <div class="insight teal">
      <div class="insight-label">✅ ${winnerKwTop?'Best Performing Keyword — Scale This':'Conversion Tracking Active'}</div>
      ${winnerKwTop
        ? `<b>"${winnerKwTop.keyword}"</b> — ${winnerKwTop.conv} conversions at <b>${fmt(winnerKwTop.cost/winnerKwTop.conv,'$2')} CPA</b> this week.
          Top impression share: ${winnerKwTop.top_impr_pct}%. ${winnerKwTop.top_impr_pct<80?'Raise bid to increase visibility — this keyword is proving ROI.':'Bid is competitive. Maintain and protect budget allocation.'}
          <br><br><b>SEO link:</b> As this keyword moves up organically, reduce bid progressively — reinvest savings into keywords with no organic coverage.`
        : `${totalConv} conversions at ${fmt(blendedCPA,'$2')} CPA this week. Google Ads is active and tracking correctly.
          <br><br>Strategy goal: reduce paid coverage for keywords ranking top 3 organically. Current organic value: ${fmt(D.seo.organic_value,'$')}/wk vs ${fmt(totalSpend,'$2')} ad spend.`
      }
    </div>
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
        const camps = ads.campaigns || [];
        const convCamps = camps.filter(c=>c.conv>0);
        const highCPA   = camps.filter(c=>c.conv>0&&c.cpa>25);
        const lowClick  = camps.filter(c=>c.clicks<10&&c.spend>20);
        const checks = [];
        checks.push(`<div class="stat-row"><span class="stat-label">Active campaigns</span><span class="stat-val">${camps.length}</span></div>`);
        checks.push(`<div class="stat-row"><span class="stat-label">Converting campaigns</span><span class="stat-val good">${convCamps.length} / ${camps.length}</span></div>`);
        checks.push(`<div class="stat-row"><span class="stat-label">CPA above $25</span><span class="stat-val ${highCPA.length>0?'bad':'good'}">${highCPA.length} campaigns</span></div>`);
        checks.push(`<div class="stat-row"><span class="stat-label">Total conversions</span><span class="stat-val good">${totalConv}</span></div>`);
        checks.push(`<div class="stat-row"><span class="stat-label">Blended CPA</span><span class="stat-val ${blendedCPA>25?'bad':'good'}">${fmt(blendedCPA,'$2')}</span></div>`);
        return checks.join('');
      })()}
      <p style="font-size:11px;color:var(--muted);margin-top:10px">
        ${totalConv > 0
          ? `${totalConv} conversions tracked this week at ${fmt(blendedCPA,'$2')} blended CPA. Smart Bidding has enough conversion signal to optimise effectively.`
          : 'Low conversion volume — Smart Bidding may still be learning. Ensure conversion tracking fires on the membership sign-up confirmation page.'}
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

  // ── Campaign Performance ──────────────────────────────────────────────────
  html += sectionTitle('Campaign Performance — Active Campaigns · ' + weekLabel);
  html += `<div class="insight neutral mb" style="font-size:12px">
    <b>SEO strategy link:</b> Goal — dominate paid while SEO builds. As each keyword cluster hits organic top 3, reduce campaign bid and reinvest budget into keywords with no organic coverage yet.
  </div>`;
  function campAction(c) {
    if (c.conv>0 && c.cpa<15) return '<span style="font-size:10px;font-weight:700;color:#00c4b4">Scale ↑</span>';
    if (c.conv>0 && c.cpa<30) return '<span style="font-size:10px;font-weight:600;color:var(--text-2)">Maintain</span>';
    if (c.conv>0)              return '<span style="font-size:10px;color:#f59e0b">Review CPA</span>';
    if (c.clicks>20)           return '<span style="font-size:10px;font-weight:700;color:#ef4444">Check Conv</span>';
    return '<span style="font-size:10px;color:var(--muted-2)">Monitor</span>';
  }
  const campsSorted = [...(ads.campaigns||[])].sort((a,b)=>b.spend-a.spend);
  html += `<div class="card mb"><table><thead><tr>
    <th>Campaign</th><th>Location</th><th class="num">Clicks</th>
    <th class="num">Spend</th><th class="num">Conv</th><th class="num">CPA</th><th class="num">CTR</th><th>Action</th>
  </tr></thead><tbody>
  ${campsSorted.map(c=>{
    const ctr = c.clicks>0?(c.conv/c.clicks*100).toFixed(1):0;
    return`<tr>
    <td style="font-size:12px;max-width:170px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:600">${c.name}</td>
    <td><span style="font-size:9px;background:${c.location==='Ellenbrook'?'#e8f5f4':'#f0f2f5'};color:${c.location==='Ellenbrook'?'#3FA69A':'var(--muted)'};padding:1px 6px;border-radius:3px">${c.location||'–'}</span></td>
    <td class="num"><b>${c.clicks}</b></td>
    <td class="num">${fmt(c.spend,'$2')}</td>
    <td class="num ${c.conv>0?'good':''}">${c.conv||'–'}</td>
    <td class="num ${c.conv>0&&c.cpa>25?'bad':c.conv>0?'good':''}">${c.conv>0?fmt(c.cpa,'$2'):'–'}</td>
    <td class="num" style="color:var(--muted)">${ctr}%</td>
    <td>${campAction(c)}</td>
  </tr>`;}).join('')||'<tr><td colspan="8" style="color:var(--muted);padding:16px">No campaign data</td></tr>'}
  </tbody></table></div>`;

  // ── Best Campaigns + Location Head-to-Head ────────────────────────────────
  const bestCamps = [...(ads.campaigns||[])].filter(c=>c.conv>0).sort((a,b)=>a.cpa-b.cpa);
  html += `<div class="grid-2 mb">
    <div class="card">
      <div class="card-h" style="color:#00c4b4">Top Campaigns — Best CPA</div>
      <table><thead><tr><th>Campaign</th><th>Location</th><th class="num">Conv</th><th class="num">CPA</th><th class="num">Spend</th></tr></thead><tbody>
      ${bestCamps.length?bestCamps.map(c=>`<tr>
        <td style="font-size:12px;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${c.name}</td>
        <td style="font-size:10px;color:var(--muted)">${c.location||'–'}</td>
        <td class="num good"><b>${c.conv}</b></td>
        <td class="num good">${fmt(c.cpa,'$2')}</td>
        <td class="num" style="color:var(--muted)">${fmt(c.spend,'$2')}</td>
      </tr>`).join(''):'<tr><td colspan="5" style="color:var(--muted);font-size:12px;padding:12px">No converting campaigns yet</td></tr>'}
      </tbody></table>
    </div>
    <div class="card">
      <div class="card-h">Location Head-to-Head</div>
      <table><thead><tr><th>Metric</th><th class="num">Malaga</th><th class="num">Ellenbrook</th><th class="num">Winner</th></tr></thead><tbody>
      ${(()=>{
        const m = mal, e = ell;
        const rows = [
          ['Spend',      fmt(m.spend,'$2'),  fmt(e.spend,'$2'),  m.spend>e.spend?'Malaga':'Ellenbrook'],
          ['Conversions',m.conv,             e.conv,             m.conv>e.conv?'Malaga':'Ellenbrook'],
          ['CPA',        m.cpa>0?fmt(m.cpa,'$2'):'–',  e.cpa>0?fmt(e.cpa,'$2'):'–',  m.cpa>0&&e.cpa>0?(m.cpa<e.cpa?'✅ Malaga':'✅ Ellenbrook'):'–'],
          ['CTR',        m.ctr+'%',          e.ctr+'%',          m.ctr>e.ctr?'Malaga':'Ellenbrook'],
        ];
        return rows.map(([label,mv,ev,winner])=>`<tr>
          <td style="font-size:12px;color:var(--muted)">${label}</td>
          <td class="num" style="font-weight:600">${mv}</td>
          <td class="num" style="font-weight:600">${ev}</td>
          <td style="font-size:10px;color:var(--teal);font-weight:700">${winner}</td>
        </tr>`).join('');
      })()}
      </tbody></table>
      <p style="font-size:11px;color:var(--muted);margin-top:12px;line-height:1.6">
        ${ell.cpa>0&&mal.cpa>0?(ell.cpa<mal.cpa
          ? `Ellenbrook converting at <b>${fmt(ell.cpa,'$2')} CPA</b> — ${Math.round((1-ell.cpa/mal.cpa)*100)}% cheaper than Malaga. Consider shifting budget toward Ellenbrook campaigns.`
          : `Malaga converting at <b>${fmt(mal.cpa,'$2')} CPA</b> — ${Math.round((1-mal.cpa/ell.cpa)*100)}% cheaper than Ellenbrook. Prioritise Malaga budget this week.`)
          : 'Review individual campaign CPAs above to determine budget allocation.'}
      </p>
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
    <td class="num">${r.bid}</td>
    <td><span style="font-size:9px;padding:2px 7px;border-radius:3px;font-weight:700;background:${r.priority==='High'?'#e8f5f4':'#f5f5f5'};color:${r.priority==='High'?'#3FA69A':'var(--muted)'}">${r.priority}</span></td>
    <td style="font-size:11px;color:var(--muted);max-width:280px">${r.reason}</td>
  </tr>`).join('')||'<tr><td colspan="5" style="color:var(--muted);text-align:center;padding:16px">No recommendations — connect Ahrefs API for live keyword gap analysis.</td></tr>'}
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
      <table><thead><tr><th>Campaign</th><th>Location</th><th class="num">Spend</th><th class="num">Conv</th><th class="num">CPA</th></tr></thead><tbody>
      ${(()=>{
        if(ads.campaigns&&ads.campaigns.length){
          return ads.campaigns.map(c=>`<tr>
            <td style="max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px">${c.name}</td>
            <td style="font-size:10px;color:var(--muted)">${c.location||'–'}</td>
            <td class="num">${fmt(c.spend,'$2')}</td>
            <td class="num ${c.conv>0?'good':''}">${c.conv||'–'}</td>
            <td class="num ${c.conv>0&&c.cpa>50?'bad':c.conv>0?'good':''}">${c.conv>0?fmt(c.cpa,'$2'):'–'}</td>
          </tr>`).join('');
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

  // ── This Week's Google Ads Priorities (campaign-level data) ─────────────
  const _camps       = ads.campaigns || [];
  const _convCamps   = _camps.filter(c => c.conv > 0).sort((a,b) => a.cpa - b.cpa);
  const _noConvCamps = _camps.filter(c => c.conv === 0 && c.spend > 0).sort((a,b) => b.spend - a.spend);
  const _bestCamp    = _convCamps[0];
  const _worstCamp   = _noConvCamps[0];
  const _malCamps    = _camps.filter(c => (c.location||'').toLowerCase().includes('malaga'));
  const _ellCamps    = _camps.filter(c => (c.location||'').toLowerCase().includes('ellenbrook'));
  const _malConvTot  = _malCamps.reduce((s,c)=>s+c.conv,0);
  const _ellConvTot  = _ellCamps.reduce((s,c)=>s+c.conv,0);
  const _malSpendTot = _malCamps.reduce((s,c)=>s+c.spend,0);
  const _ellSpendTot = _ellCamps.reduce((s,c)=>s+c.spend,0);
  const _malCPA      = _malConvTot > 0 ? _malSpendTot / _malConvTot : null;
  const _ellCPA      = _ellConvTot > 0 ? _ellSpendTot / _ellConvTot : null;

  const priorities = [];
  let _pn = 1;

  if (_bestCamp) {
    priorities.push(`<b>${_pn++}. Scale your best campaign:</b> <em>${_bestCamp.name}</em> is converting at <b>$${_bestCamp.cpa.toFixed(2)} CPA</b> with ${_bestCamp.conv} conversion${_bestCamp.conv!==1?'s':''} — your most efficient campaign this week. Increase its daily budget by 20–30% to capture more volume while CPA is below the $25 target.`);
  }

  if (_worstCamp) {
    priorities.push(`<b>${_pn++}. Review non-converting campaign:</b> <em>${_worstCamp.name}</em> spent <b>$${_worstCamp.spend.toFixed(2)}</b> with 0 conversions. Check ad copy relevance, landing page alignment, and audience targeting. If no improvement in 7 days, pause and reallocate budget to converting campaigns.`);
  }

  if (_malCPA !== null && _ellCPA !== null) {
    const _cheaperLoc = _malCPA < _ellCPA ? 'Malaga' : 'Ellenbrook';
    const _cheaperCPA = Math.min(_malCPA, _ellCPA);
    const _dearer     = _malCPA < _ellCPA ? 'Ellenbrook' : 'Malaga';
    const _dearerCPA  = Math.max(_malCPA, _ellCPA);
    priorities.push(`<b>${_pn++}. Shift budget toward ${_cheaperLoc}:</b> ${_cheaperLoc} CPA is <b>$${_cheaperCPA.toFixed(2)}</b> vs ${_dearer} at <b>$${_dearerCPA.toFixed(2)}</b>. Reallocate 15–20% of ${_dearer} budget to ${_cheaperLoc} campaigns to lower blended CPA without reducing total volume.`);
  } else if (_malCPA !== null && _ellConvTot === 0 && _ellSpendTot > 0) {
    priorities.push(`<b>${_pn++}. Ellenbrook conversion check:</b> Malaga is converting at <b>$${_malCPA.toFixed(2)} CPA</b> but Ellenbrook has <b>0 conversions</b> on $${_ellSpendTot.toFixed(2)} spend. Review Ellenbrook ad copy and landing page — ensure it mentions Ellenbrook specifically and shows the correct facilities.`);
  } else if (_ellCPA !== null && _malConvTot === 0 && _malSpendTot > 0) {
    priorities.push(`<b>${_pn++}. Malaga conversion check:</b> Ellenbrook is converting at <b>$${_ellCPA.toFixed(2)} CPA</b> but Malaga has <b>0 conversions</b> on $${_malSpendTot.toFixed(2)} spend. Review Malaga campaigns for landing page and audience alignment.`);
  }

  if (totalConv === 0 && totalSpend > 0) {
    priorities.push(`<b>${_pn++}. Verify conversion tracking:</b> <b>$${totalSpend.toFixed(2)} spent</b> this week with 0 conversions recorded. Either tracking is broken (check Google Ads → Tools → Conversions) or the contact/join form isn't firing the pixel. Fix before running more spend.`);
  }

  priorities.push(`<b>${_pn++}. Expand keyword coverage:</b> Add "kids gym malaga", "sauna and ice bath perth", and "fifo gym perth" as exact-match keywords in relevant campaigns. These are uncontested by competitors and aligned with CB247's unique facilities — high conversion intent, low CPC.`);

  if (_convCamps.length > 0 && _convCamps.every(c => c.cpa < 20)) {
    priorities.push(`<b>${_pn++}. Test budget increase:</b> All converting campaigns are below $20 CPA — well within target. Run a 2-week test with 25% higher daily budgets across converting campaigns. Google's algorithm will allocate toward best-performing ad groups automatically.`);
  }

  // ── Agent Brief ──────────────────────────────────────────────────────────
  const _ao_ads = D.raw_agent_outputs || {};
  let adsAgentText = priorities.join('<br><br>');
  if (_ao_ads.has_outputs && _ao_ads.paid_ads) {
    adsAgentText += `<div style="margin-top:14px;padding-top:12px;border-top:1px solid rgba(63,166,154,.2)">
      <b>Full Paid Ads Agent Report — ${_ao_ads.date}</b><br>
      <div style="font-size:12px;line-height:1.7;max-height:300px;overflow-y:auto;margin-top:8px">
        ${formatAgentMd(_ao_ads.paid_ads)}
      </div>
    </div>`;
  }
  html += agentBrief('Paid Ads Agent', adsAgentText);

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

  function chg(v, suffix='%') {
    if (v == null) return '';
    const col = v > 0 ? 'color:#00c4b4' : 'color:#ef4444';
    return `<span style="font-size:10px;font-weight:600;${col}">${v > 0 ? '▲' : '▼'}${Math.abs(v)}${suffix} WoW</span>`;
  }

  let html = '';

  // ── 1. KPI cards — always first ──────────────────────────────────────────
  html += `<div class="kpi-grid cols-4 mb">
    ${kpiCard('','IG Followers',fmt(ig.followers||0,'n'),ig.followers_chg,'Net +'+(ig.followers_balance||0)+' this week')}
    ${kpiCard('','FB Followers',fmt(fb.followers||0,'n'),fb.followers_chg,'Net +'+(fb.community_acquired||0)+' acquired')}
    ${kpiCard('','IG Avg Reach/Day',fmt(ig.avg_reach_per_day||0,'n'),ig.avg_reach_per_day_chg,'Views: '+(ig.views?(ig.views/1000).toFixed(0)+'K':'–'),'green')}
    ${kpiCard('','GBP Actions',fmt(gbp.total_actions||0,'n'),gbp.actions_chg,'Website + Phone + Directions',(gbp.actions_chg||0)<0?'red':'')}
  </div>`;

  // ── 2. Insight strip — 2 cards only ──────────────────────────────────────
  html += sectionTitle('Key Observations — ' + week);
  html += `<div class="grid-2 mb">
    <div class="insight red">
      <div class="insight-label">⚠️ Facebook Organic — Critical: Not Worth the Effort</div>
      <b>FB interactions collapsed −90% WoW</b> (6 total interactions from 32,710 impressions = 0.02% engagement).
      Root cause: 1 post published (down 75%) with avg reach of 183 — less than 3.5% of 5,280 followers.
      <br><br><b>Competitor gap:</b> CB247 5.3K followers. Revo: 49.6K (9.4×). World Gym: 51.6K.
      Facebook organic cannot close this gap. <b>Post 1–2×/week for GBP signals only. Redirect all effort to Instagram Reels.</b>
      <br><br><b>GBP signal drop:</b> Website clicks −49.7%, Search reach −42.8%, Total actions −33.1%. Post 1 GBP update + 3 photos this week.
    </div>
    <div class="insight teal">
      <div class="insight-label">✅ Instagram Reels — Growth Engine, Fix the Hook</div>
      <b>5 Reels this week drove 93 likes (+45% WoW)</b> — far outperforming all posts combined (9 interactions total).
      Stories hit 54,680 impressions (+93.9% WoW), avg reach per story: 804.
      <br><br><b>The one problem:</b> avg reel watch time = 4–8 sec. Benchmark = 15s+.
      The hook in the first 2 seconds is not stopping the scroll.
      <br><br><b>Fix:</b> Lead every reel with bold on-screen text within 0.5 sec.
      "Would you do THIS for $11.95/week?" beats a slow gym walkthrough open every time.
      Batch-film Sundays — 1 session = 4–6 Reels (sauna/ice bath/classes/member moment).
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

  html += agentBrief('Social Agent',
    `<b>1. Publish 2 original branded Reels:</b> All top reels this week were reposts — 0 original CB247 branded content in top 5. Priority: (1) ice bath/sauna reel with hook "The only gym in Malaga with THIS" and (2) real member story + "$11.95/week changed my routine."<br><br>
     <b>2. Fix the hook — avg watch time 4–8 sec (benchmark 15s+):</b> Lead every Reel with bold on-screen text in the first 0.5 sec. "Would you do THIS for $11.95/week?" — pattern interrupt = longer retention = more distribution.<br><br>
     <b>3. Stop treating Facebook as a primary channel:</b> 6 interactions from 32,710 impressions. Post 1–2×/week for GBP signal only. Redirect all effort to Instagram Reels.<br><br>
     <b>4. Respond to all 3 GBP reviews within 24h:</b> For the critical review — acknowledge, apologise, invite offline. Never argue. Professional replies are visible to every prospective member.<br><br>
     <b>5. Post 1 GBP update today:</b> "Perth winters made for the gym ❄️ From $11.95/week" to both profiles with a warm facility photo (sauna, heated gym floor, ice bath).`);

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
  // rankBadge and tierBadge are global helpers (defined above)

  // Graph API paid data — used as fallback when no CSV exports are present
  const paid     = D.meta || {};
  const paidComb = paid.combined   || {};
  const paidMal  = paid.malaga_paid || {};
  const paidEll  = paid.ell_paid   || {};
  const paidAds  = paid.top_ads    || [];

  // If no CSV data, override variables with Graph API figures
  const csvEmpty = (malC.spend||0) + (ellC.spend||0) === 0;
  const totalSpend   = csvEmpty ? (paidComb.spend  || paid.total_spend || 0) : (malC.spend||0) + (ellC.spend||0);
  const totalResults = csvEmpty ? (paidComb.clicks || 0) : (malC.results||0) + (ellC.results||0);
  const totalReach   = csvEmpty ? (paidComb.reach  || 0) : (malC.reach||0) + (ellC.reach||0);
  const blendedCPR   = totalResults > 0 ? (totalSpend / totalResults).toFixed(2) : '–';
  const prevSpend    = (malP.spend||0);
  const spendChg     = prevSpend > 0 ? ((totalSpend - prevSpend) / prevSpend * 100).toFixed(1) : null;
  const dispWeek     = csvEmpty ? (paid.week_label || week) : week;

  // Per-location overrides from API when no CSV
  const malSpend = csvEmpty ? (paidMal.spend||0) : (malC.spend||0);
  const ellSpend = csvEmpty ? (paidEll.spend||0) : (ellC.spend||0);
  const malCPC   = csvEmpty ? (paidMal.cpc  || 0) : (malC.cpr || 0);
  const ellCPC   = csvEmpty ? (paidEll.cpc  || 0) : (ellC.cpr || 0);
  const malCTR   = csvEmpty ? (paidMal.ctr  || 0) : (malC.ctr || 0);
  const ellCTR   = csvEmpty ? (paidEll.ctr  || 0) : (ellC.ctr || 0);
  const malCPM   = csvEmpty ? (paidMal.cpm  || 0) : (malC.cpm || 0);
  const ellCPM   = csvEmpty ? (paidEll.cpm  || 0) : (ellC.cpm || 0);
  const activeAds = csvEmpty ? paidAds : ads;

  let html = '';

  // ── KPI cards ──────────────────────────────────────────────────────────────
  html += `<div class="kpi-grid cols-4 mb">
    ${kpiCard('','Total Spend',fmt(totalSpend,'$2'),spendChg?parseFloat(spendChg):null,dispWeek+' · Both locations')}
    ${kpiCard('','Clicks',fmt(totalResults,'n'),null,'Reach: '+fmt(totalReach,'n'))}
    ${kpiCard('','Malaga CPC',malCPC?fmt(malCPC,'$2'):'–',null,fmt(malSpend,'$2')+' spend · '+malCTR+'% CTR')}
    ${kpiCard('','Ellenbrook CPC',ellCPC?fmt(ellCPC,'$2'):'–',null,fmt(ellSpend,'$2')+' spend · '+ellCTR+'% CTR')}
  </div>`;

  // ── 2. Insight strip — 2 cards only (red + teal) ────────────────────────
  const starAd  = activeAds.find(a=>a.tier==='star');
  const poorAds = activeAds.filter(a=>a.tier==='poor');
  html += sectionTitle('Key Observations — ' + dispWeek);
  html += `<div class="grid-2 mb">
    <div class="insight amber">
      <div class="insight-label">⚠️ Malaga CPC — Monitor Weekly Trend</div>
      Malaga CPC: <b>${malCPC?fmt(malCPC,'$2'):'–'}</b> · CTR: ${malCTR}% · CPM: ${fmt(malCPM,'$2')}.
      ${poorAds.length>0?`<b>⚠ ${poorAds.length} poor-tier ad${poorAds.length>1?'s':''}</b> detected — pause and refresh.`:'Monitor ad fatigue — refresh creatives every 3–4 weeks before signal decay.'}
      <br><br>Ellenbrook CPC: <b>${ellCPC?fmt(ellCPC,'$2'):'–'}</b> · CTR: ${ellCTR}% · Spend: ${fmt(ellSpend,'$2')} — underinvested. Add $5–10/day and test 1 hyperlocal creative.
      <br><br>Total reach: ${fmt(totalReach,'n')} across both locations.
    </div>
    <div class="insight teal">
      <div class="insight-label">✅ ${starAd?'Star Creative — Scale Immediately':'Focus Budget on Top-Performing Ads'}</div>
      ${starAd
        ? `<b>"${starAd.ad_name}"</b> (${starAd.location}) is the <b>only ad with dual Above average signals</b> — engagement + conversion ranking.
          This recovery/wellness angle = CB247's strongest moat (sauna + ice bath).
          <br><br><b>Scale budget → $100/week on this ad.</b> Do NOT change the creative — Meta's algorithm has learned the audience.
          Create a matching organic Reel: "Ice bath. Then sauna. $11.95/week." Test a second variation with the same angle.`
        : `Blended CPR: <b>$${blendedCPR}</b> · Total results: ${totalResults||'–'}.
          No star-tier ads currently. <b>Create new creatives</b> using the recovery/wellness angle — sauna + ice bath content maps to CB247's strongest competitive moat.
          Test: "Ice bath. Then sauna. $11.95/week." · "Deep heat. Deep recovery."`
      }
    </div>
  </div>`;

  // ── WoW comparison — Malaga ─────────────────────────────────────────────────
  const malClicks = csvEmpty ? (paidMal.clicks||0) : (malC.clicks||0);
  const malReach  = csvEmpty ? (paidMal.reach||0)  : (malC.reach||0);
  const malImpr   = csvEmpty ? (paidMal.impr||0)   : (malC.impr||0);
  html += sectionTitle('Malaga — Week-on-Week Comparison');
  html += `<div class="card mb"><table><thead><tr>
    <th>Metric</th><th class="num">This Week (${dispWeek})</th><th class="num">Prior Week</th><th class="num">Change</th>
  </tr></thead><tbody>
    <tr><td>Spend</td><td class="num">${fmt(malSpend,'$2')}</td><td class="num">$${(malP.spend||0).toFixed(2)}</td>
      <td class="num">${malP.spend?((malSpend-malP.spend)/malP.spend*100).toFixed(1)+'%':'–'}</td></tr>
    <tr><td>Clicks</td><td class="num">${fmt(malClicks,'n')}</td><td class="num">${fmt(malP.clicks||0,'n')}</td>
      <td class="num ${malClicks<(malP.clicks||0)?'bad':'good'}">${malP.clicks?((malClicks-malP.clicks)/malP.clicks*100).toFixed(1)+'%':'–'}</td></tr>
    <tr><td>Reach</td><td class="num">${fmt(malReach,'n')}</td><td class="num">${fmt(malP.reach||0,'n')}</td>
      <td class="num">${malP.reach?((malReach-malP.reach)/malP.reach*100).toFixed(1)+'%':'–'}</td></tr>
    <tr><td>Impressions</td><td class="num">${fmt(malImpr,'n')}</td><td class="num">–</td><td class="num">–</td></tr>
    <tr><td>CPC</td><td class="num ${malCPC>0.5?'bad':'good'}">${malCPC?fmt(malCPC,'$2'):'–'}</td><td class="num">–</td><td class="num">–</td></tr>
    <tr><td>CTR</td><td class="num">${malCTR||'–'}%</td><td class="num">–</td><td class="num">–</td></tr>
    <tr><td>CPM</td><td class="num">$${malCPM||'–'}</td><td class="num">–</td><td class="num">–</td></tr>
  </tbody></table></div>`;

  // ── Ad performance table ────────────────────────────────────────────────────
  html += sectionTitle('Active Ads — Performance · ' + dispWeek);
  html += `<div class="card mb" style="overflow-x:auto"><table><thead><tr>
    <th>Ad Creative</th><th>Location</th>
    <th class="num">Spend</th><th class="num">Reach</th>
    <th class="num">Impressions</th><th class="num">CTR</th><th class="num">CPM</th>
    <th class="num">Clicks</th><th class="num">CPC</th>
    <th>Quality</th><th>Engagement</th><th>Conv Rate</th><th>Tier</th>
  </tr></thead><tbody>
  ${activeAds.map(a=>{
    const cpc = a.clicks>0 ? (a.spend/a.clicks).toFixed(2) : (a.cpc||'–');
    const rowStyle = a.tier==='star' ? 'style="background:#f0fdf4"' : a.tier==='poor' ? 'style="background:#fff5f5"' : '';
    const adName = a.ad_name || a.name || '';
    return `<tr ${rowStyle}>
      <td style="font-size:11px;max-width:200px;word-break:break-word" title="${adName}">${adName.substring(0,60)}${adName.length>60?'…':''}</td>
      <td><span style="font-size:9px;background:#f0f2f5;color:var(--muted);padding:1px 5px;border-radius:3px">${a.location||'–'}</span></td>
      <td class="num">${fmt(a.spend,'$2')}</td>
      <td class="num">${fmt(a.reach||0,'n')}</td>
      <td class="num">${fmt(a.impr||a.impressions||0,'n')}</td>
      <td class="num ${(a.ctr||0)>=3?'good':(a.ctr||0)<1?'bad':''}">${a.ctr||0}%</td>
      <td class="num ${(a.cpm||0)>15?'bad':''}">${(a.cpm||0)>0?fmt(a.cpm,'$2'):'–'}</td>
      <td class="num">${fmt(a.clicks||0,'n')}</td>
      <td class="num">${cpc!=='–'?'$'+cpc:'–'}</td>
      <td>${rankBadge(a.quality)}</td>
      <td>${rankBadge(a.eng_rank)}</td>
      <td>${rankBadge(a.conv_rank)}</td>
      <td>${tierBadge(a.tier)}</td>
    </tr>`;
  }).join('')||'<tr><td colspan="13" style="color:var(--muted);padding:16px">No ad data available.</td></tr>'}
  </tbody></table></div>`;

  // ── Location summary cards ────────────────────────────────────────────────
  const ellClicks = csvEmpty ? (paidEll.clicks||0) : (ellC.clicks||0);
  const ellReach  = csvEmpty ? (paidEll.reach||0)  : (ellC.reach||0);
  html += sectionTitle('Location Summary');
  html += `<div class="grid-2 mb">
    <div class="card">
      <div class="card-h">Malaga — ${dispWeek}</div>
      <div class="stat-row"><span class="stat-label">Spend</span><span class="stat-val">${fmt(malSpend,'$2')}</span></div>
      <div class="stat-row"><span class="stat-label">Clicks</span><span class="stat-val">${fmt(malClicks,'n')}</span></div>
      <div class="stat-row"><span class="stat-label">Reach</span><span class="stat-val">${fmt(malReach,'n')}</span></div>
      <div class="stat-row"><span class="stat-label">Impressions</span><span class="stat-val">${fmt(malImpr,'n')}</span></div>
      <div class="stat-row"><span class="stat-label">CTR</span><span class="stat-val ${malCTR>=3?'good':malCTR<1?'bad':''}">${malCTR||'–'}%</span></div>
      <div class="stat-row"><span class="stat-label">CPM</span><span class="stat-val">${malCPM?fmt(malCPM,'$2'):'–'}</span></div>
      <div class="stat-row"><span class="stat-label">CPC</span><span class="stat-val">${malCPC?fmt(malCPC,'$2'):'–'}</span></div>
      <div class="stat-row"><span class="stat-label">Active ads</span><span class="stat-val">${activeAds.filter(a=>(a.location||'').includes('Malaga')).length}</span></div>
    </div>
    <div class="card">
      <div class="card-h">Ellenbrook — ${dispWeek}</div>
      <div class="stat-row"><span class="stat-label">Spend</span><span class="stat-val">${fmt(ellSpend,'$2')}</span></div>
      <div class="stat-row"><span class="stat-label">Clicks</span><span class="stat-val">${fmt(ellClicks,'n')}</span></div>
      <div class="stat-row"><span class="stat-label">Reach</span><span class="stat-val">${fmt(ellReach,'n')}</span></div>
      <div class="stat-row"><span class="stat-label">Impressions</span><span class="stat-val">${fmt(paidEll.impr||0,'n')}</span></div>
      <div class="stat-row"><span class="stat-label">CTR</span><span class="stat-val ${ellCTR>=3?'good':ellCTR<1?'bad':''}">${ellCTR||'–'}%</span></div>
      <div class="stat-row"><span class="stat-label">CPM</span><span class="stat-val">${ellCPM?fmt(ellCPM,'$2'):'–'}</span></div>
      <div class="stat-row"><span class="stat-label">CPC</span><span class="stat-val">${ellCPC?fmt(ellCPC,'$2'):'–'}</span></div>
      <div class="stat-row"><span class="stat-label">Active ads</span><span class="stat-val">${activeAds.filter(a=>(a.location||'').includes('Ellenbrook')).length}</span></div>
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
  html += agentBrief('Meta Ads Agent',
    `<b>1. Scale star creative immediately:</b> ${starAd?`"${starAd.ad_name}" is the only ad with dual Above average signals. Raise to $100/week total. Do NOT change the creative — Meta has learned the audience.`:'Create new ad using recovery/wellness angle (sauna + ice bath). This is CB247\'s strongest moat.'}<br><br>
     <b>2. Pause worst-performing ads:</b> ${poorAds.length>0?`Pause now: ${poorAds.map(a=>`"${a.ad_name}"`).join(', ')}. Below average = Meta penalising delivery and charging more for worse placement.`:'No poor-tier ads currently. Retire any ad scoring Below average on any signal dimension.'}<br><br>
     <b>3. Refresh Average-tier ads:</b> Create 1 new Malaga + 1 new Ellenbrook ad. Test: "Ice bath. Sauna. Reformer Pilates. $11.95/week. No lock-in."<br><br>
     <b>4. Increase Ellenbrook budget $5–10/day:</b> Underinvested vs potential. Test: "Your neighbourhood 24/7 gym" — hyperlocal outperforms generic Perth-wide.<br><br>
     <b>5. Set up Meta Pixel events:</b> Contact form submit + location page visits (Malaga + Ellenbrook) + 75% scroll on pricing page. Without events, Meta optimises for clicks — not members.`);

  $('meta-content').innerHTML = html;
}

// ── Render: GBP ──────────────────────────────────────────────────────────────
function renderGBP() {
  const gbp     = D.gbp, mal = gbp.malaga, ell = gbp.ellenbrook;
  const packRate = gbp.local_pack.pack_presence_rate || 0;
  const packKws  = (gbp.local_pack.appearing_in_pack || []).map(p=>`${p.keyword} (#${p.position})`).join(', ') || 'No data';
  // Pull this week's GBP signal data from Metricool
  const mc = (D.organic_social && D.organic_social.metricool && D.organic_social.metricool.gbp) || {};

  // ── KPI cards ───────────────────────────────────────────────────────────────
  let html = `<div class="kpi-grid cols-4 mb">
    ${kpiCard('','Malaga Rating', stars(mal.rating), null, `${fmt(mal.reviews,'n')} reviews`)}
    ${kpiCard('','Ellenbrook Rating', stars(ell.rating), null, `${fmt(ell.reviews,'n')} reviews`)}
    ${kpiCard('','Local Pack Rate', packRate+'%', null, 'Appearing in 3-pack for tracked keywords')}
    ${kpiCard('','GBP Actions (wk)', fmt(mc.total_actions||0,'n'), mc.actions_chg||null, 'Clicks + calls + directions', (mc.actions_chg||0)<0?'red':'green')}
  </div>`;

  // ── 2. Insight strip — 2 cards (red + teal) ──────────────────────────────
  const gbpSignalsDown = (mc.actions_chg||0) < 0;
  html += sectionTitle('Key Observations — This Week');
  html += `<div class="grid-2 mb">
    <div class="insight ${gbpSignalsDown?'red':'amber'}">
      <div class="insight-label">⚠️ ${gbpSignalsDown?'GBP Signals Down — System-Wide Drop':'GBP — Watch Weekly Trend'}</div>
      ${gbpSignalsDown
        ? `Three metrics declined simultaneously — <b>system-wide signal drop</b>, not a one-off.
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin:10px 0">
            <div style="text-align:center;background:rgba(239,68,68,.06);border-radius:6px;padding:8px">
              <div style="font-size:1.1rem;font-weight:700;color:#ef4444">${mc.website_chg||'–49.7'}%</div>
              <div style="font-size:10px;color:var(--muted)">Website Clicks</div>
            </div>
            <div style="text-align:center;background:rgba(239,68,68,.06);border-radius:6px;padding:8px">
              <div style="font-size:1.1rem;font-weight:700;color:#ef4444">${mc.reach_chg||'–23'}%</div>
              <div style="font-size:10px;color:var(--muted)">Search Reach</div>
            </div>
            <div style="text-align:center;background:rgba(239,68,68,.06);border-radius:6px;padding:8px">
              <div style="font-size:1.1rem;font-weight:700;color:#ef4444">${mc.actions_chg||'–33.1'}%</div>
              <div style="font-size:10px;color:var(--muted)">Total Actions</div>
            </div>
          </div>
          Root causes: GBP post cadence dropped, no new photos, competitor listings gaining ground.
          <b>Fix today:</b> Post 1 GBP update + add 3 photos + respond to all open reviews within 24h.`
        : `GBP actions: ${fmt(mc.total_actions||0,'n')} this week. Local pack rate: ${packRate}%.
          Photos: Malaga ${mal.photos||0}/100 · Ellenbrook ${ell.photos||0}/100.
          <b>Maintain cadence:</b> 1 GBP post/week + 5 photos/week per location.`
      }
      <br><br><b>Photo gap:</b> Malaga ${mal.photos||0}/100 · Ellenbrook ${ell.photos||0}/100. Listings with 100+ photos get 520% more calls. Upload 10 priority shots this week: sauna, ice bath, Kids Hub, gym floor, classes.
    </div>
    <div class="insight teal">
      <div class="insight-label">✅ Local Pack Presence — ${packRate}% Coverage · Reviews Strong</div>
      CB247 appears in the Google local 3-pack for <b>${packRate}% of tracked keywords</b>.
      ${packKws ? `<br><br><b>In pack:</b> ${packKws}` : ''}
      <br><br><b>Review stats:</b>
      <div class="stat-row" style="margin-top:4px"><span class="stat-label">Malaga</span><span class="stat-val">${stars(mal.rating)} · ${fmt(mal.reviews,'n')} reviews</span></div>
      <div class="stat-row"><span class="stat-label">Ellenbrook</span><span class="stat-val">${stars(ell.rating)} · ${fmt(ell.reviews,'n')} reviews</span></div>
      <br><b>Ranking signals (priority):</b> ① Review velocity · ② Photo recency · ③ Post frequency · ④ Listing clicks
      <br>CB247 is strong on ratings but needs higher weekly review velocity (target: 5+/week/location).
    </div>
  </div>`;

  // ── Location summary (side by side, compact) ────────────────────────────────
  html += sectionTitle('Location Details');
  html += `<div class="grid-2 mb">
    <div class="card">
      <div class="card-h">Malaga GBP</div>
      <div class="stat-row"><span class="stat-label">Rating</span><span class="stat-val">${stars(mal.rating)}</span></div>
      <div class="stat-row"><span class="stat-label">Reviews</span><span class="stat-val">${fmt(mal.reviews,'n')} <span style="font-size:10px;color:var(--muted)">/ 530 target</span></span></div>
      <div class="stat-row"><span class="stat-label">Photos</span><span class="stat-val">${fmt(mal.photos,'n')} <span style="font-size:10px;color:var(--muted)">/ 100 target</span></span></div>
      <div class="stat-row"><span class="stat-label">Profile complete</span><span class="stat-val">${mal.completeness||'–'}%</span></div>
      <div class="stat-row"><span class="stat-label">Website clicks (wk)</span><span class="stat-val bad">${mc.website_clicks||95} <span style="font-size:10px;color:#ef4444">${mc.website_chg||'–49.7'}% WoW</span></span></div>
    </div>
    <div class="card">
      <div class="card-h">Ellenbrook GBP</div>
      <div class="stat-row"><span class="stat-label">Rating</span><span class="stat-val">${stars(ell.rating)}</span></div>
      <div class="stat-row"><span class="stat-label">Reviews</span><span class="stat-val">${fmt(ell.reviews,'n')} <span style="font-size:10px;color:var(--muted)">/ 280 target</span></span></div>
      <div class="stat-row"><span class="stat-label">Photos</span><span class="stat-val">${fmt(ell.photos,'n')} <span style="font-size:10px;color:var(--muted)">/ 100 target</span></span></div>
      <div class="stat-row"><span class="stat-label">Profile complete</span><span class="stat-val">${ell.completeness||'–'}%</span></div>
      <div class="stat-row"><span class="stat-label">Total actions (wk)</span><span class="stat-val">${mc.total_actions||446}</span></div>
    </div>
  </div>`;

  // ── Competitor benchmark ────────────────────────────────────────────────────
  html += sectionTitle('Competitor Benchmark');
  html += `<div class="card mb"><table>
    <thead><tr>
      <th>Business</th><th>Location</th>
      <th class="num">Rating</th><th class="num">Reviews</th><th>Gap to CB247</th>
    </tr></thead><tbody>
    <tr style="background:#f0f9f7">
      <td style="font-weight:700;color:var(--teal)">ChasingBetter247</td>
      <td>Malaga + Ellenbrook</td>
      <td class="num">${stars(mal.rating)}</td>
      <td class="num"><b>${fmt((mal.reviews||0)+(ell.reviews||0),'n')}</b></td>
      <td style="font-size:11px;color:var(--teal)">Baseline</td>
    </tr>
    ${gbp.competitors.map(c=>{
      const gap = (c.reviews||0) - ((mal.reviews||0)+(ell.reviews||0));
      return `<tr>
        <td>${c.name}</td><td style="font-size:11px;color:var(--muted)">${c.location}</td>
        <td class="num">${stars(c.rating)}</td>
        <td class="num ${gap>0?'bad':''}">${fmt(c.reviews,'n')}</td>
        <td style="font-size:11px;${gap>0?'color:#ef4444':'color:var(--teal)'}">
          ${gap>0?'+'+gap.toLocaleString()+' reviews ahead':'–'}
        </td>
      </tr>`;
    }).join('')||'<tr><td colspan="5" style="color:var(--muted)">No competitor data — run pull_apify.py</td></tr>'}
    </tbody></table>
  <p style="font-size:11px;color:var(--muted);margin-top:8px;padding:0 4px">
    Review count vs competitors is a long-term signal. More impactful <b>this week</b>:
    respond to all reviews, post 1 GBP update, and upload 10 photos — these move local pack rank faster than waiting for review volume to grow.
  </p></div>`;

  html += agentBrief('GBP Agent',
    `<b>1. Respond to all reviews today (including any critical ones):</b> Critical replies are public — every prospective member sees them. Template: "Thank you for your feedback. We're sorry your experience didn't meet expectations. Please contact us at reception@chasingbetter247.com.au." Never argue.<br><br>
     <b>2. Post 1 GBP update today — Winter Push:</b> "Perth winters were made for the gym ❄️ Train 24/7 from $11.95/week." Post to BOTH Malaga + Ellenbrook. Use warm facility photo (sauna/gym floor). GBP posts have 7-day half-life — post every Tuesday.<br><br>
     <b>3. Upload 10 photos per location this week:</b> Priority: sauna, ice bath, Kids Hub, gym floor, reception, Reformer Pilates studio. Name files descriptively (e.g. "chasingbetter247-malaga-sauna.jpg"). 100+ photos = 520% more calls.<br><br>
     <b>4. Add 3 Q&A entries:</b> (1) "Do you have a kids area?" (2) "Can I freeze my membership for FIFO?" (3) "What's the price?" Pre-answered Q&As appear directly in Google search results.<br><br>
     <b>5. Weekly review-request protocol:</b> Ask every new member sign-up verbally + QR code on reception desk. Target: 5+ reviews/week/location. Review velocity = #1 local pack ranking signal.`);

  $('gbp-content').innerHTML = html;
}

// ── Helper: Coming Soon page ──────────────────────────────────────────────────
function comingSoon(title, what, needs) {
  return `<div style="max-width:560px;margin:48px auto;text-align:center">
    <div style="font-size:36px;margin-bottom:14px">🚧</div>
    <div style="font-size:18px;font-weight:700;margin-bottom:8px">${title}</div>
    <div style="font-size:13px;color:var(--muted);margin-bottom:24px;line-height:1.6">${what}</div>
    <div style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:20px;text-align:left">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin-bottom:12px">Activates when connected</div>
      ${needs.map(n=>`<div style="display:flex;align-items:flex-start;gap:10px;padding:8px 0;border-bottom:1px solid var(--border)">
        <span style="width:8px;height:8px;border-radius:50%;background:var(--border);flex-shrink:0;margin-top:4px"></span>
        <span style="font-size:12px;line-height:1.5">${n}</span>
      </div>`).join('')}
    </div>
  </div>`;
}

// ── Render: Content Planner ───────────────────────────────────────────────────
// ── Content Planner Items ─────────────────────────────────────────────────────
const PLANNER_ITEMS = [
  {id:'p1',day:0,platform:'gbp',type:'GBP Post',title:'GBP Post — Sauna & Ice Bath',assignee:'Tia',assigneeRole:'Director',caption:'Recovery is part of training. Our Sauna + Ice Bath combo at ChasingBetter247 Malaga gives your body the reset it needs. $11.95/week, no lock-in.',instructions:'Post to both Malaga and Ellenbrook GBP profiles. Use a high-quality photo of the sauna or ice bath area. Best posting time: Tuesday 7–9am or Saturday 8am. Include the $11.95 price point and \'no lock-in\' in the first sentence for SEO. Tag location: Malaga.',kw:'sauna gym perth',dueDate:'+0'},
  {id:'p2',day:1,platform:'instagram',type:'Instagram Reel',title:'Reel — FIFO Lifestyle',assignee:'Agust',assigneeRole:'Video Creator',caption:'Fly in. Train hard. We get it. CB247\'s FIFO-friendly freeze means your membership works around your roster.',instructions:'30–45 second Reel. Open with a hook: \'Working FIFO? Your gym should work around you.\' Show the freeze feature on the app or website. Voiceover tone: direct, no-nonsense, WA working-class. End with CTA: \'Freeze. Resume. No questions asked.\' Hashtags: #fifo #fifoperth #gymperth #chasingbetter247',kw:'fifo gym perth',dueDate:'+1'},
  {id:'p3',day:2,platform:'blog',type:'SEO Blog Post',title:'Blog — Best Gym Malaga',assignee:'AI',assigneeRole:'Content Agent',caption:'Targeting "best gym Malaga" — 320 searches/month. H1: "The Best Gym in Malaga? Here\'s Why 8,000 Members Chose CB247". Full outline and keyword map ready.',instructions:'AI drafts full post. Target keyword: "best gym malaga" (320/mo, KD 18). Secondary: "gym malaga perth", "cheap gym malaga". Word count: 1,200–1,500. Structure: H1 → Intro (lead with price + facilities) → H2: What Makes a Great Gym in Malaga? → H2: CB247 Malaga Facilities → H2: Pricing Comparison → H2: Member Reviews → H2: FAQ → CTA. Internal links: homepage, Malaga page, pricing. Angela reviews for brand voice. Mark publishes to WordPress.\n\nDraft for review: https://cb247agent.github.io/cb_claude/blog-drafts/best-gym-malaga.html',kw:'best gym malaga',dueDate:'+2',draftLink:'https://cb247agent.github.io/cb_claude/blog-drafts/best-gym-malaga.html'},
  {id:'p4',day:2,platform:'instagram',type:'Instagram Post',title:'Instagram — Kids Hub',assignee:'Shauna',assigneeRole:'Assets Creator',caption:'Train while the kids play. Our Kids Hub means no more "I can\'t go to the gym today." Tag a parent who needs this.',instructions:'Shauna captures photo or short video of Kids Hub. AI writes caption. Show the Kids Hub space — colourful, safe, supervised. Caption hook: "No babysitter? No problem." Tag 3 local parent pages. Best time: Wednesday 9–11am. Angela QCs before Joanne schedules. Hashtags: #kidshub #gymperth #malagatribe #chasingbetter247',kw:'kids gym malaga',dueDate:'+2'},
  {id:'p5',day:4,platform:'tiktok',type:'TikTok Video',title:'TikTok — Ice Bath Reaction',assignee:'Ivan',assigneeRole:'Video Creator',caption:'First ice bath at CB247 😅❄️ Would you try this? #icebath #recovery #chasingbetter247',instructions:'Reaction-style video. Film a member (with permission) doing their first ice bath — show genuine reaction. Ideal length: 20–30 seconds. Hook in first 2s: "Would you do this for $11.95/week?" Trending audio: check TikTok trending for Perth fitness. Tag @chasingbetter247. Raw, authentic > over-produced.',kw:'ice bath gym perth',dueDate:'+4'},
  {id:'p6',day:5,platform:'gbp',type:'GBP Post',title:'GBP Post — Reformer Pilates',assignee:'Tia',assigneeRole:'Director',caption:'24/7 Reformer Pilates in Perth. Book your class at CB247 — Malaga & Ellenbrook.',instructions:'Post to both GBP profiles. Use a class photo or studio shot. Emphasise "24/7 access" — key differentiator vs Revo. Include class booking CTA. Target: "reformer pilates perth", "pilates malaga". Post Friday morning to capture weekend bookings.',kw:'reformer pilates perth',dueDate:'+5'},
  {id:'p7',day:7,platform:'instagram',type:'Instagram Reel',title:'Reel — Gym Tour',assignee:'Agust',assigneeRole:'Video Creator',caption:'Never been to CB247? Here\'s what $11.95/week gets you. 👀 #gymtour #chasingbetter247',instructions:'60-second gym walkthrough Reel. Script: "$11.95 a week — here\'s what that actually gets you." Walk through: 24/7 weights → Reformer Pilates → CrossFit → Sauna → Ice Bath → Neon21 → Kids Hub. Voiceover with on-screen text. End card: website URL + price. Post Sunday evening for Monday motivation.',kw:'gym malaga perth',dueDate:'+7'},
  {id:'p8',day:8,platform:'email',type:'Email Newsletter',title:'Weekly Email Newsletter',assignee:'AI',assigneeRole:'Content Agent',caption:'Member spotlight + this week\'s class timetable + sauna booking tip',instructions:'AI drafts full email. Subject A/B test: A: "This week at CB247 🏋️" / B: "Your sauna booking tip + class times". Structure: 1) Member spotlight (150 words) → 2) Class timetable → 3) Sauna tip → 4) Referral nudge ("Bring a friend, 2 weeks free"). Angela reviews before send. Send via Mailchimp. List: active members. Send time: Monday 6am.',kw:'',dueDate:'+8'},
  {id:'p9',day:9,platform:'blog',type:'SEO Blog Post',title:'Blog — FIFO Gym Membership Perth',assignee:'AI',assigneeRole:'Content Agent',caption:'Ads-to-Organic P3. GSC: fifo gym membership pos 7.2, 15 imp/wk. ACTION: add homepage internal link. Draft live.',instructions:'Ads-to-Organic Priority 3.\\n\\nGSC: fifo gym membership pos 7.2, 15 imp/wk.\\nDraft live — review and publish.\\n\\nACTION REQUIRED:\\n→ Add FIFO freeze mention + link to this blog from CB247 homepage\\n→ Add internal link from /memberships page FIFO section\\n\\nPublish at: /blog/fifo-gym-membership-perth\\nCompliance: outputs/research/compliance-review-blogs-2026-06-03.md',kw:'fifo gym membership perth',dueDate:'+9',draftLink:'https://cb247agent.github.io/cb_claude/blog-drafts/fifo-gym-membership-perth.html'},
  {id:'p10',day:10,platform:'tiktok',type:'TikTok Video',title:'TikTok — Neon21 Tanning',assignee:'Ivan',assigneeRole:'Video Creator',caption:'You didn\'t know we had THIS at a $11.95/week gym 👀 #neon21 #gymsecrets',instructions:'Surprise-reveal style. Hook: "Things at CB247 people don\'t know about — Part 1". Feature: Neon21 tanning. Length: 15–20s. On-screen text: "Gym + tanning = $11.95/week??" Build curiosity — don\'t show feature in thumbnail. End: "Follow for Part 2" — drives follows for series.',kw:'',dueDate:'+10'},
  {id:'p11',day:11,platform:'gbp',type:'GBP Post',title:'GBP Post — Ellenbrook Special',assignee:'Tia',assigneeRole:'Director',caption:'Ellenbrook locals — your neighbourhood gym is here. 24/7 access, no lock-in, $11.95/week.',instructions:'Post ONLY to Ellenbrook GBP (not Malaga). Hyperlocal — use "Ellenbrook" 2–3 times. Photo: Ellenbrook location exterior or interior. Geo-tagged. Local keywords: "gym ellenbrook perth". Post Thursday morning.',kw:'gym ellenbrook perth',dueDate:'+11'},
  {id:'p12',day:13,platform:'instagram',type:'Instagram Post',title:'Community Post — Member Story',assignee:'Shauna',assigneeRole:'Assets Creator',caption:'Member story: how CB247 helped [member] hit their goal. Real stories, real results.',instructions:'Shauna captures the member photo/video. AI writes all carousel copy and caption from story notes provided. Ask reception to nominate a member who hit a milestone. Get written consent + photo. Format: carousel (3–5 slides). Slide 1: Bold quote. Slides 2–3: Journey story. Slide 4: Goal and result. Slide 5: CTA — "Start your story. $11.95/week, no lock-in." Angela QCs before Joanne schedules.',kw:'',dueDate:'+13'},
  {id:'p13',day:16,platform:'blog',type:'SEO Blog Post',title:'Blog — Best Gym Ellenbrook',assignee:'AI',assigneeRole:'Content Agent',caption:'Ads-to-Organic P2. gym ellenbrook pos 3.7, 19 imp/wk. Ellenbrook Gym campaign $128/wk. Draft live — review and publish.',instructions:'Ads-to-Organic Priority 2.\\n\\nTarget: gym ellenbrook / ellenbrook gym / 24/7 gym ellenbrook / family gym ellenbrook.\\nICP: young families + shift workers + newcomers.\\nCurrent GSC pos: 3.7 — target pos 1–2.\\n\\nDraft live — review before publishing to WordPress.\\nPublish at: /blog/gym-ellenbrook-perth\\nOnce pos 1–2: pause Ellenbrook Gym campaign ($128/wk saving).\\n\\nCompliance: outputs/research/compliance-review-blogs-2026-06-03.md — CONDITIONAL APPROVAL.',kw:'gym ellenbrook',dueDate:'+16',draftLink:'https://cb247agent.github.io/cb_claude/blog-drafts/gym-ellenbrook-perth.html'},
  {id:'p14',day:23,platform:'blog',type:'SEO Blog Post',title:'Blog — Reformer Pilates Malaga',assignee:'AI',assigneeRole:'Content Agent',caption:'Ads-to-Organic P4. Pilates campaign paused — organic content fills the gap. Draft live.',instructions:'Ads-to-Organic Priority 4.\\n\\nPilates campaign paused (CPL too high). Organic gap confirmed.\\nTarget: reformer pilates malaga / pilates classes malaga / pilates ellenbrook.\\nICP: recovery-focused, women 25–45.\\n\\nBEFORE PUBLISHING: verify Perth Pilates studio pricing ($25–$40/class claim).\\nPublish at: /blog/reformer-pilates-malaga\\n\\nCompliance: outputs/research/compliance-review-blogs-2026-06-03.md — CONDITIONAL APPROVAL.',kw:'reformer pilates malaga',dueDate:'+23',draftLink:'https://cb247agent.github.io/cb_claude/blog-drafts/reformer-pilates-malaga.html'},
];

const PLANNER_STATUS_KEY = 'cb247-planner-status';
const PLANNER_APPROVAL_KEY = 'cb247-planner-approval';
const PLANNER_STATUSES = ['Idea','Scheduled','Published'];
const PLANNER_STATUS_COLORS = {Idea:'#f3f4f6',Scheduled:'rgba(63,166,154,.1)',Published:'rgba(63,166,154,.15)'};

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
  const roleColors = {'SEO Specialist':'#f3f4f6','Video Creator':'#f3f4f6','Social Media Manager':'#f3f4f6','Content & Email Manager':'#f3f4f6','Web Developer':'#f3f4f6','Content Agent':'rgba(63,166,154,0.12)','Brand Manager':'#1a1a1a','Assets Creator':'#f3f4f6'};
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

  // Status pill + cycle button label
  const sc = PLANNER_STATUS_COLORS[status]||'#f3f4f6';
  $('modal-status-pill').innerHTML = `<span style="background:${sc};border-radius:99px;padding:3px 12px;font-size:12px;font-weight:700">${status}</span>`;
  const _cidx = KANBAN_COLS.findIndex(c=>c.key===status);
  const _cnext = KANBAN_COLS[Math.min(_cidx+1,KANBAN_COLS.length-1)].key;
  $('modal-cycle-btn').textContent = 'Move to: ' + _cnext + ' →';
  _pendingApproval = null;

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

  // Reset action button + status panel on every open
  const _sb = $('modal-save-btn');
  if(_sb) { _sb.textContent = 'Save'; _sb.disabled = false; }
  const _st = $('modal-adjust-status');
  if(_st) _st.style.display = 'none';

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

  const notes = ($('modal-notes').value || '').trim();

  // Always persist notes + approval decision to localStorage
  const approval = JSON.parse(localStorage.getItem(PLANNER_APPROVAL_KEY)||'{}');
  const current = approval[_modalItemId]||{};
  approval[_modalItemId] = {...current, notes, status: _pendingApproval||current.status};
  localStorage.setItem(PLANNER_APPROVAL_KEY, JSON.stringify(approval));

  // If "Needs Adjustment" was selected and there are notes + a draft link, auto-apply
  if(_pendingApproval === 'adjustment' && notes) {
    const item = PLANNER_ITEMS.find(x => x.id === _modalItemId);
    if(item && item.draftLink) {
      _applyAdjustmentViaServer(item, notes);
      return; // don't close yet — wait for server response
    }
  }

  closePlannerModal();
  renderPlanner();
};

async function _applyAdjustmentViaServer(item, notes) {
  const statusEl  = $('modal-adjust-status');
  const saveBtn   = $('modal-save-btn');

  // Show loading state
  statusEl.style.display     = 'block';
  statusEl.style.background  = 'rgba(63,166,154,.08)';
  statusEl.style.color       = '#3FA69A';
  statusEl.style.border      = '1px solid rgba(63,166,154,.25)';
  statusEl.textContent       = 'Applying adjustment to draft — this takes 15–30 seconds...';
  if(saveBtn) { saveBtn.disabled = true; saveBtn.textContent = 'Applying...'; }

  try {
    const res = await fetch('http://localhost:5055/apply-adjustment', {
      method:  'POST',
      headers: {'Content-Type': 'application/json'},
      body:    JSON.stringify({
        itemId:    item.id,
        notes,
        draftLink: item.draftLink,
        title:     item.title
      }),
      signal: AbortSignal.timeout(120000)   // 2-minute timeout
    });

    const data = await res.json();

    if(res.ok) {
      statusEl.style.background = '#dcfce7';
      statusEl.style.color      = '#166534';
      statusEl.style.border     = '1px solid #bbf7d0';
      statusEl.innerHTML        = `<b>Done.</b> Adjustment applied and pushed to GitHub — <span style="font-family:monospace;font-size:11px">${data.file}</span>. The live draft will update in ~60 seconds.`;
      if(saveBtn) saveBtn.textContent = 'Done';
      setTimeout(() => { closePlannerModal(); renderPlanner(); }, 3000);
    } else {
      throw new Error(data.error || 'Server returned an error');
    }

  } catch(err) {
    // Server not running, or network error — save locally and show instructions
    statusEl.style.background = '#fef9c3';
    statusEl.style.color      = '#92400e';
    statusEl.style.border     = '1px solid #fde68a';
    statusEl.innerHTML =
      `<b>Adjustment saved.</b> To auto-apply, start the server in a terminal:<br>` +
      `<code style="display:block;background:#fff;padding:5px 8px;border-radius:3px;margin-top:6px;font-size:11px">` +
      `python3 scripts/adjustment-server.py</code>`;
    if(saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'Close'; }
    setTimeout(() => { closePlannerModal(); renderPlanner(); }, 5000);
  }
}

// _pendingApproval tracks what the user has selected before saving
let _pendingApproval = null;

window.setModalApproval = (val) => {
  if(!_modalItemId) return;
  _pendingApproval = val;
  _refreshApprovalPills(val);
  $('modal-notes-wrap').style.display = (val==='adjustment'||val==='rejected') ? 'block' : 'none';

  // Update Save button label to reflect the action
  const saveBtn = $('modal-save-btn');
  if(saveBtn) {
    if(val === 'adjustment') {
      saveBtn.textContent = 'Apply Adjustment';
      saveBtn.title = 'Saves notes and applies the adjustment to the blog draft automatically';
    } else if(val === 'approved') {
      saveBtn.textContent = 'Approve & Advance';
    } else if(val === 'rejected') {
      saveBtn.textContent = 'Reject & Reset';
    } else {
      saveBtn.textContent = 'Save';
    }
  }

  // Reset status feedback if user changes their mind
  const statusEl = $('modal-adjust-status');
  if(statusEl) statusEl.style.display = 'none';

  // Apply status change immediately based on decision:
  // Approved  → advance to next stage
  // Rejected  → send back to Idea
  // Adjustment → stay in current stage (just flag it)
  const saved = JSON.parse(localStorage.getItem(PLANNER_STATUS_KEY)||'{}');
  const curr = saved[_modalItemId]||'Idea';
  let newStatus = curr;
  if(val==='approved') {
    const idx = KANBAN_COLS.findIndex(c=>c.key===curr);
    const lastIdx = KANBAN_COLS.length - 1;
    newStatus = KANBAN_COLS[Math.min(idx+1, lastIdx)].key;
  } else if(val==='rejected') {
    newStatus = 'Idea';
  }
  if(newStatus !== curr) {
    saved[_modalItemId] = newStatus;
    localStorage.setItem(PLANNER_STATUS_KEY, JSON.stringify(saved));
    // Update status pill in modal to reflect new position
    const sc = PLANNER_STATUS_COLORS[newStatus]||'#f3f4f6';
    $('modal-status-pill').innerHTML = `<span style="background:${sc};border-radius:99px;padding:3px 12px;font-size:12px;font-weight:700">${newStatus}</span>`;
    // Update cycle button label
    const nextIdx = KANBAN_COLS.findIndex(c=>c.key===newStatus);
    const nextStage = KANBAN_COLS[Math.min(nextIdx+1,KANBAN_COLS.length-1)].key;
    $('modal-cycle-btn').textContent = 'Move to: ' + nextStage + ' →';
    renderPlanner();
  }

  // Also save approval decision to storage
  const approval = JSON.parse(localStorage.getItem(PLANNER_APPROVAL_KEY)||'{}');
  approval[_modalItemId] = {...(approval[_modalItemId]||{}), status: val};
  localStorage.setItem(PLANNER_APPROVAL_KEY, JSON.stringify(approval));
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
  const idx = KANBAN_COLS.findIndex(c=>c.key===curr);
  const next = KANBAN_COLS[(idx+1)%KANBAN_COLS.length].key;
  saved[_modalItemId] = next;
  localStorage.setItem(PLANNER_STATUS_KEY, JSON.stringify(saved));
  const sc = PLANNER_STATUS_COLORS[next]||'#f3f4f6';
  $('modal-status-pill').innerHTML = `<span style="background:${sc};border-radius:99px;padding:3px 12px;font-size:12px;font-weight:700">${next}</span>`;
  const nextIdx = KANBAN_COLS.findIndex(c=>c.key===next);
  const nextStage = KANBAN_COLS[Math.min(nextIdx+1,KANBAN_COLS.length-1)].key;
  $('modal-cycle-btn').textContent = 'Move to: ' + nextStage + ' →';
  renderPlanner();
};

// ── Platform colours + icons ────────────────────────────────────────────────
const PLAT_CFG = {
  instagram: {bg:'#dbeafe', color:'#1d4ed8', border:'#3b82f6', label:'Instagram'},
  tiktok:    {bg:'#fef2f2', color:'#991b1b', border:'#ef4444', label:'TikTok'},
  blog:      {bg:'#fef9c3', color:'#854d0e', border:'#f59e0b', label:'Blog'},
  email:     {bg:'#ecfdf5', color:'#166534', border:'#10b981', label:'Email'},
  gbp:       {bg:'rgba(63,166,154,.15)', color:'#3FA69A', border:'#3FA69A', label:'GBP'},
  meta:      {bg:'#ede9fe', color:'#5b21b6', border:'#8b5cf6', label:'Meta Ad'},
};
const ASSIGNEE_CFG = {
  'AI':     {bg:'rgba(63,166,154,.15)',color:'#2d8a80'},
  'Shauna': {bg:'#f3f4f6',            color:'#444'},
  'Tia':    {bg:'#3FA69A',            color:'#fff'},
  'Joanne': {bg:'#f3f4f6',            color:'#444'},
  'Angela': {bg:'#1a1a1a',            color:'#fff'},
  'Agust':  {bg:'#f3f4f6',            color:'#444'},
  'Ivan':   {bg:'#f3f4f6',            color:'#444'},
};
function platBadge(p) {
  const c = PLAT_CFG[p] || {bg:'#f3f4f6',color:'#444',border:'#ccc',label:p};
  return `<span style="background:${c.bg};color:${c.color};border:1px solid ${c.border};font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px;white-space:nowrap;letter-spacing:.3px">${c.label.toUpperCase()}</span>`;
}
function assigneeBadge(a) {
  const c = ASSIGNEE_CFG[a] || {bg:'#f3f4f6',color:'#444'};
  return `<span style="background:${c.bg};color:${c.color};font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px">${a}</span>`;
}

// ── KANBAN STATUS CONFIG ──────────────────────────────────────────────────────
const KANBAN_COLS = [
  {key:'Idea',       label:'Idea',        color:'#f9fafb', border:'#d1d5db'},
  {key:'In Progress',label:'In Progress', color:'#f9fafb', border:'#3FA69A'},
  {key:'Angela QC',  label:'Angela QC',   color:'#f9fafb', border:'#1a1a1a'},
  {key:'Scheduled',  label:'Scheduled',   color:'#f9fafb', border:'#3FA69A'},
  {key:'Published',  label:'Published',   color:'rgba(63,166,154,.06)', border:'#3FA69A'},
];

// Calendar week offset — 0 = current week, 1 = next week, etc.
let _calWeekOffset = 0;

function renderPlanner() {
  const saved    = JSON.parse(localStorage.getItem(PLANNER_STATUS_KEY)||'{}');
  const approved = JSON.parse(localStorage.getItem(PLANNER_APPROVAL_KEY)||'{}');

  // ── Status counts for KPI bar ────────────────────────────────────────────
  const counts = {};
  KANBAN_COLS.forEach(c => counts[c.key] = 0);
  PLANNER_ITEMS.forEach(item => {
    const s = saved[item.id] || 'Idea';
    counts[s] = (counts[s]||0) + 1;
  });
  const pendingQC  = counts['Angela QC'] || 0;
  const scheduled  = counts['Scheduled'] || 0;
  const published  = counts['Published'] || 0;
  const totalItems = PLANNER_ITEMS.length;

  let html = '';

  // ── Page intro ────────────────────────────────────────────────────────
  html += `<p style="font-size:12.5px;color:var(--text-2);line-height:1.7;margin:0 0 20px">
    Your 2-week publishing schedule for every CB247 channel — blogs, Instagram, TikTok, GBP posts, and emails. Each card is one piece of content moving from draft to published.
  </p>`;

  // ── KPI bar ────────────────────────────────────────────────────────────
  html += `<div class="kpi-grid cols-4 mb">
    ${kpiCard('','Total Items', totalItems, null, 'In this 2-week plan')}
    ${kpiCard('','Pending QC', pendingQC, null, 'Waiting for Angela review', pendingQC>0?'amber':'')}
    ${kpiCard('','Scheduled', scheduled, null, 'Approved + in scheduler', scheduled>0?'green':'')}
    ${kpiCard('','Published', published, null, 'Live this cycle', published>0?'green':'')}
  </div>`;

  // ── Approval flow reminder ───────────────────────────────────────────────
  html += `<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:20px;padding:10px 14px;background:rgba(63,166,154,.06);border:1px solid rgba(63,166,154,.2);border-radius:6px;font-size:11px;color:var(--text-2)">
    <span style="font-weight:700;color:var(--teal)">Approval flow:</span>
    <span>AI drafts</span><span style="color:var(--muted)">→</span>
    <b>Tia</b> reviews<span style="color:var(--muted)">→</span>
    In Progress<span style="color:var(--muted)">→</span>
    <b>Angela QC</b><span style="color:var(--muted)">→</span>
    <b>Joanne</b> schedules social &amp; <b>Tia</b> posts GBP
  </div>`;

  // ── Kanban board ──────────────────────────────────────────────────────
  html += sectionTitle('Kanban Board');
  html += `<div style="background:#f9fafb;border:1px solid var(--border);border-radius:6px;padding:12px 16px;margin-bottom:14px;display:flex;gap:24px;flex-wrap:wrap">
    <div style="flex:1;min-width:200px">
      <div style="font-size:11px;font-weight:700;color:var(--text);margin-bottom:3px">What it is</div>
      <div style="font-size:11px;color:var(--text-2);line-height:1.6">All content items grouped by workflow stage — Idea, In Progress, Angela QC, Scheduled, and Published. Card colour shows the platform type.</div>
    </div>
    <div style="flex:1;min-width:200px">
      <div style="font-size:11px;font-weight:700;color:var(--text);margin-bottom:3px">How to use it</div>
      <div style="font-size:11px;color:var(--text-2);line-height:1.6">Click any card to open its brief, read the instructions, leave notes, and approve or reject it. Cards advance one stage at a time through the approval flow.</div>
    </div>
  </div>`;
  html += `<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-bottom:28px;align-items:start">`;

  KANBAN_COLS.forEach(col => {
    const items = PLANNER_ITEMS.filter(item => (saved[item.id]||'Idea') === col.key);
    html += `<div style="background:${col.color};border-top:3px solid ${col.border};border-radius:6px;padding:8px;min-height:100px">
      <div style="font-size:10px;font-weight:700;margin-bottom:8px;color:var(--text);text-transform:uppercase;letter-spacing:.5px">${col.label} <span style="font-size:10px;color:var(--muted);font-weight:400;text-transform:none">(${items.length})</span></div>
      ${items.map(item => {
        const pc = PLAT_CFG[item.platform] || {bg:'#f3f4f6',color:'#444'};
        const ac = ASSIGNEE_CFG[item.assignee] || {bg:'#f3f4f6',color:'#444'};
        return `<div onclick="openPlannerModal('${item.id}')" style="background:#fff;border:1px solid var(--border);border-left:3px solid ${pc.border||'#ccc'};border-radius:4px;padding:7px 8px;margin-bottom:6px;cursor:pointer;transition:box-shadow .15s" onmouseover="this.style.boxShadow='0 2px 8px rgba(0,0,0,.1)'" onmouseout="this.style.boxShadow='none'">
          <div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:4px">
            <span style="background:${pc.bg};color:${pc.color};border:1px solid ${pc.border||'#ccc'};font-size:8px;font-weight:700;padding:1px 5px;border-radius:2px;letter-spacing:.3px">${item.platform.toUpperCase()}</span>
            <span style="background:${ac.bg};color:${ac.color};font-size:8px;font-weight:700;padding:1px 5px;border-radius:2px">${item.assignee}</span>
          </div>
          <div style="font-size:10px;font-weight:600;line-height:1.35;margin-bottom:3px;color:var(--text)">${item.title}</div>
          <div style="font-size:9px;color:var(--muted)">Day ${item.day} · ${item.dueDate}</div>
        </div>`;
      }).join('')}
      ${items.length===0 ? `<div style="font-size:10px;color:var(--muted);text-align:center;padding:16px 0;border:1px dashed var(--border);border-radius:4px">—</div>` : ''}
    </div>`;
  });
  html += `</div>`;

  // ── Mon-Sun calendar grid with week navigation ───────────────────────
  html += sectionTitle('Weekly Content Calendar');
  html += `<div style="background:#f9fafb;border:1px solid var(--border);border-radius:6px;padding:12px 16px;margin-bottom:14px;display:flex;gap:24px;flex-wrap:wrap">
    <div style="flex:1;min-width:200px">
      <div style="font-size:11px;font-weight:700;color:var(--text);margin-bottom:3px">What it is</div>
      <div style="font-size:11px;color:var(--text-2);line-height:1.6">A Monday-to-Sunday view of what is scheduled each day across all channels. Today's column is highlighted. Empty days show gaps in the plan.</div>
    </div>
    <div style="flex:1;min-width:200px">
      <div style="font-size:11px;font-weight:700;color:var(--text);margin-bottom:3px">How to use it</div>
      <div style="font-size:11px;color:var(--text-2);line-height:1.6">Use Prev and Next to browse weeks. Click any card to open the brief. Content scheduled beyond this week appears in future weeks — keep clicking Next.</div>
    </div>
  </div>`;

  // Find Monday of the current week
  const _calToday = new Date(); _calToday.setHours(0,0,0,0);
  const _dow = _calToday.getDay(); // 0=Sun,1=Mon..6=Sat
  const _daysToMon = _dow === 0 ? -6 : 1 - _dow;
  const _thisMonday = new Date(_calToday);
  _thisMonday.setDate(_calToday.getDate() + _daysToMon);

  // Displayed week start/end
  const _wkStart = new Date(_thisMonday);
  _wkStart.setDate(_thisMonday.getDate() + _calWeekOffset * 7);
  const _wkEnd = new Date(_wkStart);
  _wkEnd.setDate(_wkStart.getDate() + 6);

  const _wkLabel = _wkStart.toLocaleDateString('en-AU',{day:'numeric',month:'short'}) + ' – ' + _wkEnd.toLocaleDateString('en-AU',{day:'numeric',month:'short',year:'numeric'});
  const _DOW = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];

  // Count items in this week
  const _wkItemCount = PLANNER_ITEMS.filter(item => {
    const d = new Date(_calToday); d.setDate(_calToday.getDate()+item.day); d.setHours(0,0,0,0);
    return d >= _wkStart && d <= _wkEnd;
  }).length;

  html += `<div style="margin-bottom:28px">

    <!-- Week nav bar -->
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;gap:12px;flex-wrap:wrap">
      <button onclick="if(_calWeekOffset>0){_calWeekOffset--;renderPlanner()}" style="display:flex;align-items:center;gap:5px;padding:6px 14px;border:1px solid var(--border);border-radius:4px;background:var(--card);color:${_calWeekOffset===0?'var(--muted)':'var(--text)'};font-size:12px;font-weight:600;cursor:${_calWeekOffset===0?'default':'pointer'};opacity:${_calWeekOffset===0?'.4':'1'}" ${_calWeekOffset===0?'disabled':''}>&#8592; Prev</button>
      <div style="text-align:center">
        <div style="font-size:14px;font-weight:700;color:var(--text)">${_wkLabel}</div>
        <div style="font-size:11px;color:var(--muted);margin-top:2px">${_wkItemCount} item${_wkItemCount!==1?'s':''} scheduled this week</div>
      </div>
      <button onclick="_calWeekOffset++;renderPlanner()" style="display:flex;align-items:center;gap:5px;padding:6px 14px;border:1px solid #3FA69A;border-radius:4px;background:rgba(63,166,154,.08);color:#3FA69A;font-size:12px;font-weight:600;cursor:pointer">Next &#8594;</button>
    </div>

    <!-- 7-column Mon-Sun grid -->
    <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:6px;min-width:700px;overflow-x:auto">
      ${_DOW.map((dayName, i) => {
        const _colDate = new Date(_wkStart);
        _colDate.setDate(_wkStart.getDate() + i);
        _colDate.setHours(0,0,0,0);
        const _isToday = _colDate.getTime() === _calToday.getTime();
        const _colItems = PLANNER_ITEMS.filter(item => {
          const d = new Date(_calToday); d.setDate(_calToday.getDate()+item.day); d.setHours(0,0,0,0);
          return d.getTime() === _colDate.getTime();
        });
        const _colDateStr = _colDate.toLocaleDateString('en-AU',{day:'numeric',month:'short'});
        return `<div style="background:#f9fafb;border:1px solid ${_isToday?'#3FA69A':'var(--border)'};border-radius:6px;overflow:hidden">
          <div style="padding:7px 8px;background:${_isToday?'rgba(63,166,154,.08)':'var(--bg)'};border-bottom:2px solid ${_isToday?'#3FA69A':'var(--border)'}">
            <div style="font-size:10px;font-weight:700;color:${_isToday?'#3FA69A':'var(--text-2)'};text-transform:uppercase;letter-spacing:.05em">${dayName}${_isToday?' ·&nbsp;Today':''}</div>
            <div style="font-size:10px;color:var(--muted);margin-top:1px">${_colDateStr}</div>
          </div>
          <div style="padding:5px">
            ${_colItems.map(item => {
              const pc = PLAT_CFG[item.platform] || {bg:'#f3f4f6',color:'#444',border:'#ccc'};
              const st = saved[item.id] || 'Idea';
              const stColor = st==='Published'?'#3FA69A':st==='Scheduled'?'#3FA69A':st==='Angela QC'?'#111':st==='In Progress'?'#3FA69A':'#999';
              return `<div onclick="openPlannerModal('${item.id}')" style="background:#fff;border:1px solid var(--border);border-left:3px solid ${pc.border};border-radius:4px;padding:6px 7px;margin-bottom:5px;cursor:pointer;font-size:10px;transition:box-shadow .15s" onmouseover="this.style.boxShadow='0 2px 6px rgba(0,0,0,.09)'" onmouseout="this.style.boxShadow='none'">
                <div style="font-size:8px;font-weight:700;background:${pc.bg};color:${pc.color};border:1px solid ${pc.border};padding:1px 5px;border-radius:2px;display:inline-block;margin-bottom:4px;letter-spacing:.3px">${item.platform.toUpperCase()}</div>
                <div style="font-weight:600;line-height:1.3;color:var(--text);margin-bottom:3px;font-size:10px">${item.title}</div>
                <div style="font-size:9px;font-weight:700;color:${stColor}">${st}</div>
              </div>`;
            }).join('')}
            ${_colItems.length===0 ? `<div style="height:36px;display:flex;align-items:center;justify-content:center;border:1px dashed var(--border);border-radius:4px;font-size:10px;color:var(--muted-2)">—</div>` : ''}
          </div>
        </div>`;
      }).join('')}
    </div>
  </div>`;

  // ── All items list ─────────────────────────────────────────────────────
  html += sectionTitle('All Content Items — ' + totalItems + ' items this cycle');
  html += `<div style="background:#f9fafb;border:1px solid var(--border);border-radius:6px;padding:12px 16px;margin-bottom:14px;display:flex;gap:24px;flex-wrap:wrap">
    <div style="flex:1;min-width:200px">
      <div style="font-size:11px;font-weight:700;color:var(--text);margin-bottom:3px">What it is</div>
      <div style="font-size:11px;color:var(--text-2);line-height:1.6">A flat list of every content item in this cycle — platform, title, assignee, target keyword, day, and current status all in one place.</div>
    </div>
    <div style="flex:1;min-width:200px">
      <div style="font-size:11px;font-weight:700;color:var(--text);margin-bottom:3px">How to use it</div>
      <div style="font-size:11px;color:var(--text-2);line-height:1.6">Click View to open the full brief. Use the arrow button (→ Stage) to advance a card to the next stage without opening it — useful for bulk updates.</div>
    </div>
  </div>`;
  html += `<div class="card mb" style="overflow-x:auto"><table><thead><tr>
    <th>Platform</th><th>Title</th><th>Assignee</th><th>Keyword</th><th class="num">Day</th><th>Status</th><th>Action</th>
  </tr></thead><tbody>
  ${PLANNER_ITEMS.map(item => {
    const st = saved[item.id] || 'Idea';
    const stColor = st==='Published'?'#3FA69A':st==='Scheduled'?'#3FA69A':st==='Angela QC'?'#111':st==='In Progress'?'#3FA69A':'#999';
    const nextSt = KANBAN_COLS[(KANBAN_COLS.findIndex(c=>c.key===st)+1) % KANBAN_COLS.length].key;
    return `<tr>
      <td>${platBadge(item.platform)}</td>
      <td style="font-size:12px;font-weight:600;max-width:200px">${item.title}</td>
      <td>${assigneeBadge(item.assignee)}</td>
      <td style="font-size:10px;color:var(--muted)">${item.kw||'–'}</td>
      <td class="num">${item.day}</td>
      <td><span style="font-size:10px;font-weight:700;color:${stColor}">${st}</span></td>
      <td style="white-space:nowrap">
        <button onclick="openPlannerModal('${item.id}')" style="font-size:10px;padding:3px 8px;border:1px solid var(--border);border-radius:4px;cursor:pointer;background:var(--bg-2)">View</button>
        <button onclick="advanceStatus('${item.id}')" style="font-size:10px;padding:3px 8px;border:1px solid var(--teal);border-radius:4px;cursor:pointer;background:rgba(63,166,154,.08);color:var(--teal);margin-left:4px">→ ${nextSt}</button>
      </td>
    </tr>`;
  }).join('')}
  </tbody></table></div>`;

  // ── SEO Content Briefs ─────────────────────────────────────────────────
  const _ao_seo_p = D.raw_agent_outputs || {};
  const _seoBriefs = (_ao_seo_p.seo_highlights || {}).content_briefs || [];
  if (_seoBriefs.length) {
    html += `<div style="margin-top:8px">
      ${sectionTitle('SEO Pages to Build — From SEO Agent')}
      <div style="display:grid;gap:10px">
        ${_seoBriefs.map((b,i)=>`
        <div class="card" style="border-left:4px solid var(--teal);padding:16px">
          <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--teal);margin-bottom:4px">SEO Brief ${i+1}</div>
          <div style="font-weight:700;font-size:14px;margin-bottom:6px">${b.title}</div>
          ${b.keyword?`<div style="font-size:11px;color:var(--muted)">Keyword: ${b.keyword}</div>`:''}
          ${b.why?`<div style="font-size:11px;color:var(--muted);margin-top:4px">Why: ${b.why}</div>`:''}
          <div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap">
            ${b.url?`<span style="background:rgba(63,166,154,.1);color:var(--teal);padding:2px 8px;border-radius:3px;font-size:10px;font-family:monospace">${b.url}</span>`:''}
            ${b.word_count?`<span style="background:#f3f4f6;color:var(--muted);padding:2px 8px;border-radius:3px;font-size:10px">${b.word_count} words</span>`:''}
            <span style="background:#f3f4f6;color:#444;padding:2px 8px;border-radius:3px;font-size:10px;font-weight:700">AI drafts → Angela QC → Mark publishes</span>
          </div>
        </div>`).join('')}
      </div>
    </div>`;
  }

  $('planner-content').innerHTML = html;
}

// Advance a planner item to next status without opening modal
window.advanceStatus = (id) => {
  const saved = JSON.parse(localStorage.getItem(PLANNER_STATUS_KEY)||'{}');
  const curr = saved[id] || 'Idea';
  const idx = KANBAN_COLS.findIndex(c=>c.key===curr);
  const next = KANBAN_COLS[(idx+1) % KANBAN_COLS.length].key;
  saved[id] = next;
  localStorage.setItem(PLANNER_STATUS_KEY, JSON.stringify(saved));
  renderPlanner();
};

// ── Render: Content Review ────────────────────────────────────────────────────
function renderContentReview() {
  const saved    = JSON.parse(localStorage.getItem(PLANNER_STATUS_KEY)||'{}');
  const seo      = D.seo || {};
  const gscQ     = seo.gsc_queries || [];
  const gscPages = seo.top_pages   || [];
  const meta     = (D.organic_social && D.organic_social.meta) || {};
  const ads      = meta.active || [];
  const mal      = meta.malaga_cur || {};
  const ell      = meta.ell_cur    || {};

  // Items marked Published or Scheduled
  const published = PLANNER_ITEMS.filter(i => saved[i.id]==='Published');
  const scheduled = PLANNER_ITEMS.filter(i => saved[i.id]==='Scheduled');
  const pendingQC = PLANNER_ITEMS.filter(i => saved[i.id]==='Angela QC');

  // Top performing GSC query
  const topQuery = [...gscQ].sort((a,b)=>(b.clicks||0)-(a.clicks||0))[0];
  const topPage  = [...gscPages].sort((a,b)=>(b.traffic||0)-(a.traffic||0))[0];

  // Star ad from Meta
  const starAd = ads.find(a=>a.tier==='star');
  const poorAds = ads.filter(a=>a.tier==='poor');

  let html = '';

  // ── Intro / How-to-use panel ─────────────────────────────────────────────
  html += `<div style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:22px 26px;margin-bottom:22px">
    <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:24px;flex-wrap:wrap">
      <div style="flex:1;min-width:260px">
        <div style="font-size:14px;font-weight:700;color:var(--text);margin-bottom:6px">What is Content Review?</div>
        <p style="font-size:12px;color:var(--text-2);line-height:1.7;margin:0 0 14px">
          Content Review is where the team checks performance after content goes live. Once an item is marked <b>Published</b> in the Content Planner, it appears here so you can see how it is tracking — clicks, impressions, and engagement — and decide what to do next.
        </p>
        <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-bottom:8px">Review workflow</div>
        <div style="display:flex;flex-direction:column;gap:6px">
          <div style="display:flex;align-items:flex-start;gap:10px"><span style="flex-shrink:0;width:18px;height:18px;background:#3FA69A;color:#fff;border-radius:50%;font-size:9px;font-weight:700;display:flex;align-items:center;justify-content:center;margin-top:1px">1</span><div><span style="font-size:12px;font-weight:600;color:var(--text)">Check what has been published</span><span style="font-size:11px;color:var(--muted);display:block;margin-top:1px">Items from the Content Planner marked Published appear in the table below</span></div></div>
          <div style="display:flex;align-items:flex-start;gap:10px"><span style="flex-shrink:0;width:18px;height:18px;background:#3FA69A;color:#fff;border-radius:50%;font-size:9px;font-weight:700;display:flex;align-items:center;justify-content:center;margin-top:1px">2</span><div><span style="font-size:12px;font-weight:600;color:var(--text)">Review performance data</span><span style="font-size:11px;color:var(--muted);display:block;margin-top:1px">GSC shows organic clicks and position. Meta panel shows paid ad performance.</span></div></div>
          <div style="display:flex;align-items:flex-start;gap:10px"><span style="flex-shrink:0;width:18px;height:18px;background:#3FA69A;color:#fff;border-radius:50%;font-size:9px;font-weight:700;display:flex;align-items:center;justify-content:center;margin-top:1px">3</span><div><span style="font-size:12px;font-weight:600;color:var(--text)">Approve or flag for adjustment</span><span style="font-size:11px;color:var(--muted);display:block;margin-top:1px">Open the item card and use the approval buttons</span></div></div>
          <div style="display:flex;align-items:flex-start;gap:10px"><span style="flex-shrink:0;width:18px;height:18px;background:#3FA69A;color:#fff;border-radius:50%;font-size:9px;font-weight:700;display:flex;align-items:center;justify-content:center;margin-top:1px">4</span><div><span style="font-size:12px;font-weight:600;color:var(--text)">Feed learnings back into next cycle</span><span style="font-size:11px;color:var(--muted);display:block;margin-top:1px">What performed well becomes the brief for next fortnight</span></div></div>
        </div>
      </div>
      <div style="flex-shrink:0;min-width:200px">
        <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-bottom:10px">Who reviews what</div>
        <div style="display:flex;flex-direction:column;gap:8px">
          <div style="display:flex;align-items:flex-start;gap:8px"><span style="flex-shrink:0;background:#3FA69A;color:#fff;font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px;white-space:nowrap">Tia</span><span style="font-size:11px;color:var(--text-2);line-height:1.5">All content — final approval, GBP posts</span></div>
          <div style="display:flex;align-items:flex-start;gap:8px"><span style="flex-shrink:0;background:#1a1a1a;color:#fff;font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px;white-space:nowrap">Angela</span><span style="font-size:11px;color:var(--text-2);line-height:1.5">Blog copy, captions, tone of voice</span></div>
          <div style="display:flex;align-items:flex-start;gap:8px"><span style="flex-shrink:0;background:#f3f4f6;color:#444;font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px;white-space:nowrap">Joanne</span><span style="font-size:11px;color:var(--text-2);line-height:1.5">Scheduling, Instagram, TikTok timing</span></div>
          <div style="display:flex;align-items:flex-start;gap:8px"><span style="flex-shrink:0;background:#f3f4f6;color:#444;font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px;white-space:nowrap">Mark</span><span style="font-size:11px;color:var(--text-2);line-height:1.5">WordPress blog publishing</span></div>
        </div>
        <div style="margin-top:14px;padding-top:12px;border-top:1px solid var(--border);font-size:11px;color:var(--text-2);line-height:1.6">
          <b>2-week rule:</b> Content needs at least 2 weeks of data before drawing performance conclusions.
        </div>
      </div>
    </div>
  </div>`;

  // ── KPI bar ────────────────────────────────────────────────────────────
  html += `<div class="kpi-grid cols-4 mb">
    ${kpiCard('','Published', published.length, null, 'Items marked live this cycle', published.length>0?'green':'')}
    ${kpiCard('','Pending QC', pendingQC.length, null, 'Waiting for Angela review', pendingQC.length>0?'amber':'')}
    ${kpiCard('','Top Organic Query', topQuery?topQuery.query:'–', null, topQuery?topQuery.clicks+' clicks · pos '+topQuery.position:'No GSC data')}
    ${kpiCard('','Star Ad', starAd?'✅ Found':'None', null, starAd?starAd.ad_name:'No star-tier ads this week', starAd?'green':'amber')}
  </div>`;

  // ── Performance loop reminder ─────────────────────────────────────────
  html += `<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:20px;padding:10px 14px;background:rgba(63,166,154,.06);border:1px solid rgba(63,166,154,.2);border-radius:6px;font-size:11px;color:var(--text-2)">
    <span style="font-weight:700;color:var(--teal)">Review loop:</span>
    Content goes live → <b>2 weeks</b> to gather data → review here → learnings feed next Content Planner cycle
  </div>`;

  // ── Section 1: Content items by status ───────────────────────────────
  html += sectionTitle('Content Items — Current Status');
  if (published.length === 0 && scheduled.length === 0 && pendingQC.length === 0) {
    html += `<div class="card mb" style="padding:20px;text-align:center;color:var(--muted);font-size:13px">
      No items published or scheduled yet. Use the <b>Content Planner</b> to advance items through the workflow.
    </div>`;
  } else {
    const reviewGroups = [
      {label:'Published — check performance in 2 weeks', items: published, color:'#3FA69A', bg:'rgba(63,166,154,.08)'},
      {label:'Scheduled — going out soon', items: scheduled, color:'#3FA69A', bg:'rgba(63,166,154,.05)'},
      {label:'Waiting Angela QC', items: pendingQC, color:'#111', bg:'#f9fafb'},
    ];
    reviewGroups.forEach(g => {
      if (!g.items.length) return;
      html += `<div class="card mb">
        <div style="font-size:11px;font-weight:700;color:${g.color};background:${g.bg};padding:8px 12px;border-radius:4px;margin-bottom:12px">${g.label}</div>
        <table><thead><tr>
          <th>Platform</th><th>Title</th><th>Assignee</th><th style="font-size:10px">Caption preview</th><th>Action</th>
        </tr></thead><tbody>
        ${g.items.map(item=>`<tr>
          <td>${platBadge(item.platform)}</td>
          <td style="font-size:12px;font-weight:600">${item.title}</td>
          <td>${assigneeBadge(item.assignee)}</td>
          <td style="font-size:10px;color:var(--muted);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${item.caption||'–'}</td>
          <td><button onclick="advanceStatus('${item.id}')" style="font-size:10px;padding:3px 8px;border:1px solid var(--border);border-radius:4px;cursor:pointer;background:var(--bg-2)">Advance ›</button></td>
        </tr>`).join('')}
        </tbody></table>
      </div>`;
    });
  }

  // ── Section 2: Organic content performance (GSC) ──────────────────────
  html += sectionTitle('Organic Content Performance — Google Search Console (7 days)');
  html += `<div class="grid-2 mb">
    <div class="card">
      <div class="card-h">Top Queries by Clicks</div>
      <table><thead><tr>
        <th>Query</th><th class="num">Clicks</th><th class="num">CTR</th><th class="num">Pos</th><th style="font-size:10px">Signal</th>
      </tr></thead><tbody>
      ${gscQ.slice(0,10).map(q=>{
        const signal = q.clicks>=50 ? '🟢 Strong' : q.clicks>=10 ? '🟡 Growing' : '🔴 Low';
        const action = q.position>3&&q.position<=10 ? '⚡ Optimise H1' : q.position>10 ? '📄 Build page' : '🔒 Protect';
        return `<tr>
          <td style="font-size:11px">${q.query}</td>
          <td class="num">${fmt(q.clicks,'n')}</td>
          <td class="num">${q.ctr}%</td>
          <td class="num">${posBadge(q.position)}</td>
          <td style="font-size:9px;color:var(--muted)">${action}</td>
        </tr>`;
      }).join('')||'<tr><td colspan="5" style="color:var(--muted)">No GSC data</td></tr>'}
      </tbody></table>
    </div>
    <div class="card">
      <div class="card-h">Top Pages by Traffic</div>
      <table><thead><tr>
        <th>Page</th><th class="num">Clicks</th><th class="num">Pos</th><th style="font-size:10px">Action</th>
      </tr></thead><tbody>
      ${gscPages.slice(0,10).map(p=>{
        const url = (p.url||'/').replace('https://www.chasingbetter247.com.au','') || '/';
        const action = (p.pos||99)<=3 ? 'Protect' : (p.pos||99)<=10 ? 'Optimise' : 'Build page';
        return `<tr>
          <td style="font-size:10px;color:var(--text-2);max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${url}</td>
          <td class="num">${fmt(p.traffic,'n')}</td>
          <td class="num">${posBadge(p.pos)}</td>
          <td style="font-size:10px;color:var(--muted)">${action}</td>
        </tr>`;
      }).join('')||'<tr><td colspan="4" style="color:var(--muted)">No page data</td></tr>'}
      </tbody></table>
    </div>
  </div>`;

  // ── Section 3: Paid ad creative performance (Meta) ────────────────────
  html += sectionTitle('Paid Ad Creative Performance — Meta Ads');
  if (ads.length > 0) {
    const sortedAds = [...ads].sort((a,b) => (b.tier==='star'?3:b.tier==='good'?2:b.tier==='poor'?0:1) - (a.tier==='star'?3:a.tier==='good'?2:a.tier==='poor'?0:1));
    html += `<div class="card mb" style="overflow-x:auto"><table><thead><tr>
      <th>Creative</th><th>Location</th><th class="num">Spend</th><th class="num">CTR</th>
      <th class="num">CPM</th><th class="num">Results</th><th>Tier</th><th style="font-size:10px">Verdict</th>
    </tr></thead><tbody>
    ${sortedAds.map(a=>{
      const verdict = a.tier==='star' ? '🚀 Scale — raise budget 30%'
        : a.tier==='good'  ? '✅ Keep — maintain budget'
        : a.tier==='poor'  ? '⛔ Pause — below average signal'
        : '⏸ Monitor — refresh in 2 weeks';
      return `<tr style="${a.tier==='star'?'background:#f0fdf4':a.tier==='poor'?'background:#fff5f5':''}">
        <td style="font-size:11px;max-width:180px;word-break:break-word">${a.ad_name}</td>
        <td style="font-size:10px">${a.location||'–'}</td>
        <td class="num">$${(a.spend||0).toFixed(2)}</td>
        <td class="num ${(a.ctr||0)>=3?'good':(a.ctr||0)<1?'bad':''}">${a.ctr||'–'}%</td>
        <td class="num">${a.cpm>0?'$'+a.cpm:'–'}</td>
        <td class="num ${a.results>0?'good':''}">${a.results||'–'}</td>
        <td>${tierBadge(a.tier)}</td>
        <td style="font-size:10px;color:var(--text-2)">${verdict}</td>
      </tr>`;
    }).join('')}
    </tbody></table></div>`;
  } else {
    html += `<div class="card mb" style="padding:20px;color:var(--muted);font-size:13px;text-align:center">
      No active Meta ad data. Upload Meta CSV files to <code>metaads/</code> folder and run <code>python3 scripts/bake-public-dashboard.py</code>.
    </div>`;
  }

  // ── Section 4: What's working — learning summary ──────────────────────
  html += sectionTitle('What\'s Working — Learnings for Next Cycle');
  const topGscQ = gscQ.filter(q=>q.clicks>=5).slice(0,3);
  const brandQ  = gscQ.filter(q=>['chasing better','chasingbetter'].some(b=>(q.query||'').toLowerCase().includes(b)));
  const nonBrand = gscQ.filter(q=>!['chasing better','chasingbetter','cb247'].some(b=>(q.query||'').toLowerCase().includes(b)) && q.clicks>0);
  html += `<div class="grid-2 mb">
    <div class="insight teal">
      <div class="insight-label">✅ What to repeat</div>
      ${starAd ? `<b>Meta:</b> "${starAd.ad_name}" has dual Above Average signals — duplicate this angle and test a new variation.<br><br>` : ''}
      ${topGscQ.length ? `<b>SEO:</b> Top queries — ${topGscQ.map(q=>`"${q.query}" (${q.clicks} clicks)`).join(', ')} — these pages are working. Add internal links from new content back to them.<br><br>` : ''}
      ${nonBrand.length ? `<b>Non-brand traffic:</b> ${nonBrand.slice(0,3).map(q=>`"${q.query}"`).join(', ')} are generating organic clicks — expand with more content on these topics.` : 'Focus on building non-brand keyword content — currently most traffic is brand-name searches.'}
    </div>
    <div class="insight ${poorAds.length>0||nonBrand.length===0?'red':'amber'}">
      <div class="insight-label">⚠️ What to fix or retire</div>
      ${poorAds.length > 0 ? `<b>Meta:</b> ${poorAds.length} ad${poorAds.length>1?'s':''} with Below Average signals — <b>pause now</b>: ${poorAds.map(a=>`"${a.ad_name}"`).join(', ')}. Replace with new creative using the star ad angle.<br><br>` : '<b>Meta:</b> No poor-tier ads this week. Refresh any Average-tier ads every 3–4 weeks to prevent fatigue.<br><br>'}
      ${brandQ.length > (gscQ.length * 0.7) ? `<b>SEO:</b> ${Math.round(brandQ.length/gscQ.length*100)}% of clicks are brand searches (people already know CB247). Build non-brand content to attract new audiences — "gym malaga", "reformer pilates perth", "kids gym malaga".` : '<b>SEO:</b> Good mix of brand and non-brand traffic. Keep publishing keyword-targeted content to grow non-brand share.'}
    </div>
  </div>`;

  $('review-content').innerHTML = html;
  if($('review-badge')) $('review-badge').textContent = pendingQC.length > 0 ? pendingQC.length : '';
}


// ── Render: Status bar ────────────────────────────────────────────────────────
function renderStatus() {
  const s = D.status;
  const allLive = Object.values(s).every(v=>v==='live'||v==='suspended');
  $('system-dot').className = 'status-dot'+(allLive?'':' warn');
  $('refresh-label').textContent = 'Latest data: '+D.refresh_ts;
  $('page-footer').innerHTML = `CB247 Marketing OS &nbsp;·&nbsp; Report period: <strong>${D.report_period}</strong> &nbsp;·&nbsp; Built: ${D.generated} &nbsp;·&nbsp; <a href="https://cb247agent.github.io/cb_claude/">cb247agent.github.io/cb_claude</a>`;
  if($('sidebar-week')) $('sidebar-week').textContent = D.report_period || '';

  // ── Inject per-source timestamps into each page subtitle ──────────
  const ts = D.timestamps || {};
  const badge = (label, t) => t && t !== 'No data'
    ? ` <span style="font-size:11px;font-weight:500;color:var(--teal);background:rgba(63,166,154,.1);padding:2px 8px;border-radius:99px;margin-left:6px;white-space:nowrap">Data: ${t}</span>`
    : ` <span style="font-size:11px;color:#ef4444;background:rgba(239,68,68,.08);padding:2px 8px;border-radius:99px;margin-left:6px">No data</span>`;

  const pageTs = {
    'page-seo':         ts.gsc,
    'page-google-ads':  ts.google_ads,
    'page-meta-ads':    ts.meta_ads,
    'page-gbp':         ts.gbp,
    'page-organic-social': ts.gsc,
  };
  // Overview: show the oldest source so users know the least-fresh data
  const allTs = Object.values(ts).filter(t => t && t !== 'No data');
  if (allTs.length) {
    const oldest = allTs.sort()[0];
    const ovEl = document.querySelector('#page-overview .page-header p');
    if (ovEl) ovEl.innerHTML += badge('overview', oldest);
  }
  Object.entries(pageTs).forEach(([pageId, t]) => {
    const el = document.querySelector('#' + pageId + ' .page-header p');
    if (el) el.innerHTML += badge(pageId, t);
  });
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
            <div class="agent-desc">Reads ALL 8 agent outputs. Produces the single executive strategy document Denver leads in the meeting: seasonal status · weekly scorecard · top 5 priorities · decisions needed · one-line brief per team member</div>
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
        <div class="tc-role">Director — OS Owner</div>
        <ul class="tc-tasks">
          <li>Maintains the Marketing OS</li>
          <li>Quality checks reports + data accuracy</li>
          <li>Delivers the weekly report to the team</li>
          <li>Posts to both GBP profiles (Malaga + Ellenbrook)</li>
        </ul>
      </div>
      <div class="team-card lead">
        <div class="tc-name">Denver</div>
        <div class="tc-role">COO — Decision Maker</div>
        <ul class="tc-tasks">
          <li>Leads all marketing meetings</li>
          <li>Final decision on strategy + spend</li>
          <li>Sets weekly priorities for the team</li>
          <li>Escalates outcomes + risks to Tia</li>
        </ul>
      </div>
      <div class="team-card">
        <div class="tc-name">Angela</div>
        <div class="tc-role">Brand Manager (QC)</div>
        <ul class="tc-tasks">
          <li>Reviews all AI-generated content</li>
          <li>Approves blog drafts + email copy</li>
          <li>Checks brand voice compliance</li>
          <li>Releases approved content to Joanne</li>
        </ul>
      </div>
      <div class="team-card" style="border-left:3px solid #3FA69A">
        <div class="tc-name" style="color:#3FA69A">AI (Content Agent)</div>
        <div class="tc-role">Content & Copy</div>
        <ul class="tc-tasks">
          <li>Writes all blog drafts from SEO brief</li>
          <li>Writes weekly email newsletter</li>
          <li>Writes social captions + carousel copy</li>
          <li>Generates content recommendations</li>
        </ul>
      </div>
      <div class="team-card">
        <div class="tc-name">Shauna</div>
        <div class="tc-role">Assets Creator</div>
        <ul class="tc-tasks">
          <li>Photography — gym, facilities, members</li>
          <li>Video shoots for Reels + TikTok</li>
          <li>Captures member stories on camera</li>
          <li>Provides raw assets to video editors</li>
        </ul>
      </div>
      <div class="team-card">
        <div class="tc-name">Mark</div>
        <div class="tc-role">Web Developer</div>
        <ul class="tc-tasks">
          <li>Executes technical SEO fixes</li>
          <li>Publishes AI blog drafts to WordPress</li>
          <li>Builds new landing pages</li>
          <li>Title tag + meta optimisation</li>
        </ul>
      </div>
      <div class="team-card">
        <div class="tc-name">Joanne</div>
        <div class="tc-role">Social Media Manager</div>
        <ul class="tc-tasks">
          <li>Schedules Angela-approved posts</li>
          <li>Posts to Instagram + TikTok</li>
          <li>Responds to reviews</li>
          <li>Manages content calendar</li>
        </ul>
      </div>
      <div class="team-card">
        <div class="tc-name">Agust + Ivan</div>
        <div class="tc-role">Video Editors</div>
        <ul class="tc-tasks">
          <li>Edit Reels from Shauna's raw footage</li>
          <li>TikTok editing + captions overlay</li>
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
          <div class="loop-label">AI + Assets</div>
          <div class="loop-sub">AI writes copy<br>Shauna captures</div>
        </div>
        <div class="loop-arrow">→</div>
        <div class="loop-node" style="min-width:100px">
          <div class="loop-icon active-node"><div class="loop-icon-inner"></div></div>
          <div class="loop-label">Angela QC</div>
          <div class="loop-sub">Brand review /<br>approve / edit</div>
        </div>
        <div class="loop-arrow">→</div>
        <div class="loop-node" style="min-width:100px">
          <div class="loop-icon active-node"><div class="loop-icon-inner"></div></div>
          <div class="loop-label">Tia Posts GBP</div>
          <div class="loop-sub">Both locations<br>Malaga + Ellenbrook</div>
        </div>
        <div class="loop-arrow">+</div>
        <div class="loop-node" style="min-width:100px">
          <div class="loop-icon active-node"><div class="loop-icon-inner"></div></div>
          <div class="loop-label">Joanne Schedules</div>
          <div class="loop-sub">Instagram /<br>TikTok</div>
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

// ── Render: This Week removed — priorities shown on Recommendations page ──────
// function renderThisWeek() { /* deleted */ }


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
    <div class="section-title" style="margin-top:24px">Meeting History</div>
    ${minutes.slice().reverse().map(m=>{
      const d = m.decisions_summary||{};
      return `<div class="meeting-log">
        <div class="meeting-log-header">
          <span class="meeting-log-date">${m.date}</span>
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
      <div style="font-weight:700;font-size:13px;margin-bottom:3px">After your Monday meeting</div>
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
  renderTracker();
  renderReadme();

  // Restore last active page
  const lastPage = localStorage.getItem('cb247-active-page')||'overview';
  const navItem = document.querySelector(`[data-page="${lastPage}"]`);
  if(navItem) nav(navItem);

  // Init review badge
  renderContentReview();
}

document.addEventListener('DOMContentLoaded', init);
</script>
</body>
</html>"""


if __name__ == "__main__":
    build()
