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


def build_data():
    """Load all state files and return a single dashboard data dict."""
    ga4      = load("ga4-data.json")
    gsc      = load("gsc-data.json")
    ads      = load("ads-data.json")
    apify    = load("apify-data.json")
    ahrefs   = load("ahrefs-data.json")
    refresh  = load("last-refresh.json")

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
    top_queries = (gsc.get("top_queries") or [])[:10]

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

    # ── GBP / Maps ───────────────────────────────────────────────────
    maps_targets = (apify.get("competitor_maps") or {}).get("targets") or []
    mal_gbp = next((t for t in maps_targets if t.get("location") == "Malaga"), {})
    ell_gbp = next((t for t in maps_targets if t.get("location") == "Ellenbrook"), {})
    comp_gbp = [t for t in maps_targets if t.get("type") == "competitor"]
    local_pack = apify.get("local_pack_summary") or {}

    # ── Ahrefs / SEO ─────────────────────────────────────────────────
    ov_curr   = (ahrefs.get("organic_value") or {}).get("current_week") or {}
    ov_prev   = (ahrefs.get("organic_value") or {}).get("previous_week") or {}
    organic_value      = safe_float(ov_curr.get("organic_traffic_value"))
    organic_value_prev = safe_float(ov_prev.get("organic_traffic_value"))
    organic_traffic    = safe_int(ov_curr.get("organic_traffic"))

    dr_obj     = (ahrefs.get("domain_rating") or {}).get("domain_rating") or {}
    domain_rating = dr_obj.get("domain_rating")

    tkp        = ahrefs.get("target_keyword_positions") or {}
    tk_summary = tkp.get("summary") or {}
    tk_keywords= tkp.get("keywords") or []
    wow_changes= ahrefs.get("wow_changes") or []
    kw_gap     = ahrefs.get("keyword_gap") or {}
    gap_revo   = (kw_gap.get("revofitness.com.au") or [])[:10]
    gap_anytime= (kw_gap.get("anytimefitness.com.au") or [])[:8]
    broken_bl  = ((ahrefs.get("broken_backlinks") or {}).get("backlinks") or [])[:10]
    lost_bl    = ((ahrefs.get("lost_backlinks") or {}).get("backlinks") or [])[:8]

    # ── SEO health score ─────────────────────────────────────────────
    def seo_score():
        s = 0
        if domain_rating: s += min(20, int(domain_rating) // 2)
        s += min(25, (tk_summary.get("top_3_count") or 0) * 5)
        s += min(15, (tk_summary.get("top_10_count") or 0) * 2)
        if organic_value > 1000: s += min(20, int(organic_value // 200))
        pack_rate = (local_pack.get("pack_presence_rate") or 0)
        s += min(20, int(pack_rate // 5))
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
            "organic_value_prev": organic_value_prev,
            "organic_traffic": organic_traffic,
            "ov_chg": pct_change(organic_value, organic_value_prev),
            "tk_summary": tk_summary,
            "keywords": tk_keywords,
            "wow_changes": wow_changes[:20],
            "wow_up": [w for w in wow_changes if w.get("direction") == "up"][:5],
            "wow_down": [w for w in wow_changes if w.get("direction") == "down"][:5],
            "gap_revo": gap_revo,
            "gap_anytime": gap_anytime,
            "broken_backlinks": broken_bl,
            "lost_backlinks": lost_bl,
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
    }


def build():
    data = build_data()
    data_json = json.dumps(data, indent=2)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(HTML_TEMPLATE.replace("__DASHBOARD_DATA__", data_json), encoding="utf-8")
    print(f"✅ Dashboard generated → {OUT_FILE}")
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
/* ── Reset ────────────────────────────────────────── */
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --teal:#3FA69A;--teal-dark:#2d7a70;--teal-light:#e8f5f4;
  --bg:#F0F2F5;--card:#fff;--sidebar:#1a1a2e;--sidebar-hover:#2a2a3e;
  --text:#1a1a2e;--muted:#6b7280;--border:#e5e7eb;
  --red:#ef4444;--green:#22c55e;--amber:#f59e0b;--blue:#3b82f6;--purple:#8b5cf6;
  --radius:10px;--shadow:0 1px 4px rgba(0,0,0,.08),0 2px 12px rgba(0,0,0,.04);
  --gap:16px;--sidebar-w:240px;
}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--text);font-size:14px;line-height:1.5;overflow-x:hidden}
a{color:var(--teal);text-decoration:none}
button{cursor:pointer;border:none;background:none;font-family:inherit}

/* ── Layout ───────────────────────────────────────── */
.app{display:flex;min-height:100vh}
.sidebar{width:var(--sidebar-w);min-height:100vh;background:var(--sidebar);flex-shrink:0;display:flex;flex-direction:column;position:fixed;top:0;left:0;z-index:100;overflow-y:auto}
.main{margin-left:var(--sidebar-w);flex:1;display:flex;flex-direction:column;min-height:100vh}
.topbar{background:#fff;border-bottom:1px solid var(--border);padding:0 24px;height:56px;display:flex;align-items:center;gap:0;position:sticky;top:0;z-index:50;box-shadow:0 1px 4px rgba(0,0,0,.06)}
.content{padding:24px;flex:1}

/* ── Sidebar ──────────────────────────────────────── */
.sidebar-brand{padding:20px 16px 16px;border-bottom:1px solid rgba(255,255,255,.08)}
.sidebar-brand .logo{font-size:18px;font-weight:800;color:#fff;letter-spacing:-.3px}
.sidebar-brand .logo span{color:#7ee8e0}
.sidebar-brand .sub{font-size:11px;color:rgba(255,255,255,.45);margin-top:2px}

.sidebar-section{padding:12px 0 4px}
.sidebar-section-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:rgba(255,255,255,.3);padding:0 16px 6px}
.sidebar-item{display:flex;align-items:center;gap:10px;padding:9px 16px;color:rgba(255,255,255,.65);font-size:13px;font-weight:500;cursor:pointer;border-radius:0;transition:all .15s;border-left:3px solid transparent;position:relative}
.sidebar-item:hover{background:var(--sidebar-hover);color:#fff}
.sidebar-item.active{background:rgba(63,166,154,.15);color:#7ee8e0;border-left-color:#3FA69A}
.sidebar-item .icon{font-size:16px;width:20px;text-align:center;flex-shrink:0}
.sidebar-item .badge{margin-left:auto;background:var(--red);color:#fff;border-radius:99px;font-size:10px;font-weight:700;padding:1px 6px}
.sidebar-item .badge.green{background:var(--green)}
.sidebar-item .badge.amber{background:var(--amber);color:var(--text)}
.sidebar-footer{margin-top:auto;padding:12px 16px;font-size:11px;color:rgba(255,255,255,.3);border-top:1px solid rgba(255,255,255,.08)}

/* ── Business nav (topbar) ────────────────────────── */
.biz-nav{display:flex;align-items:center;gap:0;height:100%}
.biz-tab{padding:0 20px;height:100%;display:flex;align-items:center;font-size:13px;font-weight:600;color:var(--muted);border-bottom:3px solid transparent;cursor:pointer;transition:all .15s;white-space:nowrap}
.biz-tab:hover{color:var(--text)}
.biz-tab.active{color:var(--teal);border-bottom-color:var(--teal)}
.biz-tab.coming-soon{opacity:.45;cursor:default;font-size:12px}
.biz-tab.coming-soon::after{content:'Soon';background:var(--border);color:var(--muted);font-size:9px;font-weight:700;padding:1px 5px;border-radius:99px;margin-left:6px}
.topbar-right{margin-left:auto;display:flex;align-items:center;gap:12px}
.refresh-badge{font-size:11px;color:var(--muted);display:flex;align-items:center;gap:5px}
.status-dot{width:7px;height:7px;border-radius:50%;background:var(--green);display:inline-block}
.status-dot.warn{background:var(--amber)}
.status-dot.error{background:var(--red)}

/* ── Page sections ────────────────────────────────── */
.page{display:none}
.page.active{display:block}

/* ── Page header ──────────────────────────────────── */
.page-header{margin-bottom:24px}
.page-header h1{font-size:22px;font-weight:800;letter-spacing:-.3px}
.page-header p{color:var(--muted);font-size:13px;margin-top:4px}

/* ── KPI grid ─────────────────────────────────────── */
.kpi-grid{display:grid;gap:var(--gap);margin-bottom:var(--gap)}
.kpi-grid.cols-4{grid-template-columns:repeat(4,1fr)}
.kpi-grid.cols-3{grid-template-columns:repeat(3,1fr)}
.kpi-grid.cols-2{grid-template-columns:repeat(2,1fr)}
.kpi-card{background:var(--card);border-radius:var(--radius);padding:18px 20px;box-shadow:var(--shadow);border-left:4px solid var(--teal)}
.kpi-card.red{border-left-color:var(--red)}
.kpi-card.green{border-left-color:var(--green)}
.kpi-card.amber{border-left-color:var(--amber)}
.kpi-card.blue{border-left-color:var(--blue)}
.kpi-card.purple{border-left-color:var(--purple)}
.kpi-icon{font-size:18px;margin-bottom:8px;display:block}
.kpi-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);margin-bottom:3px}
.kpi-value{font-size:26px;font-weight:800;color:var(--text);letter-spacing:-1px;line-height:1}
.kpi-change{font-size:11px;font-weight:600;margin-top:5px}
.kpi-change.up{color:var(--green)}
.kpi-change.down{color:var(--red)}
.kpi-change.flat{color:var(--muted)}
.kpi-sub{font-size:11px;color:var(--muted);margin-top:2px}

/* ── Cards ────────────────────────────────────────── */
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:var(--gap)}
.grid-3{display:grid;grid-template-columns:repeat(3,1fr);gap:var(--gap)}
.mb{margin-bottom:var(--gap)}
.card{background:var(--card);border-radius:var(--radius);padding:20px 22px;box-shadow:var(--shadow)}
.card-h{font-size:14px;font-weight:700;margin-bottom:14px;display:flex;align-items:center;gap:6px}
.card-period{font-size:11px;color:var(--muted);font-weight:400;margin-left:auto}

/* ── Stat rows ────────────────────────────────────── */
.stat-row{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid var(--border);font-size:13px}
.stat-row:last-child{border-bottom:none}
.stat-label{color:var(--muted)}
.stat-val{font-weight:600}
.stat-val.good{color:var(--green)}
.stat-val.bad{color:var(--red)}
.stat-val.warn{color:var(--amber)}

/* ── Section title ────────────────────────────────── */
.section-title{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);margin-bottom:12px;display:flex;align-items:center;gap:6px}
.section-title::after{content:'';flex:1;height:1px;background:var(--border)}

/* ── Insight box ──────────────────────────────────── */
.insight{border-radius:var(--radius);padding:14px 16px;margin-bottom:var(--gap);font-size:13px;line-height:1.6}
.insight.green{background:#f0fdf4;border-left:4px solid var(--green)}
.insight.red{background:#fef2f2;border-left:4px solid var(--red)}
.insight.amber{background:#fffbeb;border-left:4px solid var(--amber)}
.insight.blue{background:#eff6ff;border-left:4px solid var(--blue)}
.insight.teal{background:var(--teal-light);border-left:4px solid var(--teal)}
.insight-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;opacity:.7}

/* ── Tables ───────────────────────────────────────── */
table{width:100%;border-collapse:collapse;font-size:12px}
thead th{text-align:left;padding:7px 10px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;color:var(--muted);border-bottom:2px solid var(--border);white-space:nowrap}
tbody td{padding:7px 10px;border-bottom:1px solid var(--border)}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover{background:#f9fafb}
.num{text-align:right;font-variant-numeric:tabular-nums}
.rank{color:var(--muted);font-size:11px;width:24px}

/* ── Position badges ──────────────────────────────── */
.pos-badge{display:inline-block;border-radius:12px;padding:1px 7px;font-weight:700;font-size:11px}
.pos-1-3{background:#dcfce7;color:#16a34a}
.pos-4-10{background:#dbeafe;color:#1d4ed8}
.pos-11-20{background:#fef9c3;color:#854d0e}
.pos-deep{background:#fee2e2;color:#991b1b}
.pos-none{color:#999}
.wow-up{color:#16a34a;font-weight:700}
.wow-down{color:#dc2626;font-weight:700}
.wow-new{color:#7c3aed;font-size:10px;font-weight:700}

/* ── Progress bar ─────────────────────────────────── */
.progress-wrap{margin:8px 0 4px}
.progress-label{display:flex;justify-content:space-between;font-size:11px;color:var(--muted);margin-bottom:4px}
.progress-track{background:var(--border);border-radius:99px;height:6px;overflow:hidden}
.progress-fill{background:var(--teal);height:100%;border-radius:99px}

/* ── Chart ────────────────────────────────────────── */
.chart-wrap{position:relative;height:180px}

/* ── Recommendation cards ─────────────────────────── */
.rec-board{display:flex;flex-direction:column;gap:12px}
.rec-card{background:var(--card);border-radius:var(--radius);box-shadow:var(--shadow);padding:16px 18px;display:flex;gap:14px;align-items:flex-start}
.rec-card.done{opacity:.6}
.rec-icon{font-size:22px;flex-shrink:0;margin-top:2px}
.rec-body{flex:1}
.rec-tags{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px;align-items:center}
.rec-tag{border-radius:99px;padding:2px 9px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.3px}
.tag-seo{background:#dbeafe;color:#1e40af}
.tag-ads{background:#fef9c3;color:#854d0e}
.tag-gbp{background:#dcfce7;color:#166534}
.tag-meta{background:#f3e8ff;color:#6b21a8}
.tag-content{background:#ffe4e6;color:#9f1239}
.tag-web{background:#f0fdf4;color:#166534}
.rec-title{font-size:14px;font-weight:700;margin-bottom:4px}
.rec-why{font-size:12px;color:var(--muted);line-height:1.5;margin-bottom:10px}
.rec-footer{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.rec-impact{font-size:12px;font-weight:700;color:var(--green)}
.rec-owner{font-size:11px;color:var(--muted)}
.rec-status-btn{border:none;border-radius:99px;padding:4px 12px;font-size:11px;font-weight:700;cursor:pointer;transition:all .15s}
.status-new{background:#dbeafe;color:#1e40af}
.status-accepted{background:#fef9c3;color:#854d0e}
.status-inprogress{background:#fed7aa;color:#9a3412}
.status-done{background:#dcfce7;color:#166534}
.status-skipped{background:#f3f4f6;color:#6b7280}
.rec-outcome-input{flex:1;border:1px solid var(--border);border-radius:6px;padding:4px 10px;font-size:12px;font-family:inherit;min-width:180px}
.rec-outcome-input:focus{outline:none;border-color:var(--teal)}

/* ── Kanban (content review) ──────────────────────── */
.kanban{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;align-items:start}
.kanban-col{background:#f8f9fa;border-radius:var(--radius);padding:12px}
.kanban-col-header{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);margin-bottom:10px;display:flex;align-items:center;justify-content:space-between}
.kanban-col-header .count{background:var(--border);border-radius:99px;padding:1px 7px;font-size:10px}
.content-card{background:var(--card);border-radius:8px;padding:12px 14px;margin-bottom:8px;box-shadow:0 1px 3px rgba(0,0,0,.06);cursor:pointer;border-left:3px solid var(--border);transition:box-shadow .15s}
.content-card:hover{box-shadow:0 2px 8px rgba(0,0,0,.1)}
.content-card .platform-tag{font-size:10px;font-weight:700;border-radius:4px;padding:2px 7px;display:inline-block;margin-bottom:6px}
.platform-gbp{background:#dcfce7;color:#166534}
.platform-instagram{background:#fce7f3;color:#9d174d}
.platform-tiktok{background:#1a1a2e;color:#fff}
.platform-blog{background:#dbeafe;color:#1e40af}
.platform-email{background:#fef9c3;color:#854d0e}
.platform-meta{background:#ede9fe;color:#5b21b6}
.content-card .cc-title{font-size:12px;font-weight:700;margin-bottom:4px}
.content-card .cc-preview{font-size:11px;color:var(--muted);line-height:1.4;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.content-card .cc-footer{display:flex;justify-content:space-between;align-items:center;margin-top:8px;font-size:10px;color:var(--muted)}
.content-card .cc-assignee{font-weight:600}

/* ── Website manager ──────────────────────────────── */
.task-list{list-style:none}
.task-item{display:flex;align-items:flex-start;gap:10px;padding:10px 0;border-bottom:1px solid var(--border);font-size:13px}
.task-item:last-child{border-bottom:none}
.priority-pill{border-radius:4px;padding:2px 8px;font-size:10px;font-weight:700;flex-shrink:0;margin-top:1px}
.p-critical{background:#fee2e2;color:#991b1b}
.p-high{background:#fef9c3;color:#854d0e}
.p-medium{background:#dbeafe;color:#1e40af}
.p-low{background:#f3f4f6;color:#6b7280}

/* ── Stars ────────────────────────────────────────── */
.stars{color:#f59e0b}

/* ── Tags / chips ─────────────────────────────────── */
.chip{display:inline-block;background:var(--teal-light);color:var(--teal-dark);border-radius:99px;padding:3px 10px;font-size:11px;font-weight:600;margin:2px}

/* ── Footer ───────────────────────────────────────── */
.page-footer{text-align:center;font-size:11px;color:var(--muted);padding:24px;border-top:1px solid var(--border);margin-top:8px}

/* ── Responsive ───────────────────────────────────── */
@media(max-width:1100px){.kpi-grid.cols-4{grid-template-columns:repeat(2,1fr)}.kanban{grid-template-columns:repeat(3,1fr)}}
@media(max-width:768px){.sidebar{transform:translateX(-100%)}.main{margin-left:0}.kpi-grid.cols-4,.kpi-grid.cols-3,.grid-2,.grid-3{grid-template-columns:1fr}.kanban{grid-template-columns:1fr 1fr}}
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
    <div class="sidebar-item active" data-page="overview" onclick="nav(this)">
      <span class="icon">📊</span> Dashboard
    </div>
  </div>

  <div class="sidebar-section">
    <div class="sidebar-section-label">Channel Performance</div>
    <div class="sidebar-item" data-page="seo" onclick="nav(this)">
      <span class="icon">🔍</span> SEO &amp; Organic
    </div>
    <div class="sidebar-item" data-page="google-ads" onclick="nav(this)">
      <span class="icon">🎯</span> Google Ads
    </div>
    <div class="sidebar-item" data-page="meta-ads" onclick="nav(this)">
      <span class="icon">📱</span> Meta Ads
    </div>
    <div class="sidebar-item" data-page="gbp" onclick="nav(this)">
      <span class="icon">📍</span> Google Business
    </div>
  </div>

  <div class="sidebar-section">
    <div class="sidebar-section-label">Content</div>
    <div class="sidebar-item" data-page="content-planner" onclick="nav(this)">
      <span class="icon">📅</span> Content Planner
    </div>
    <div class="sidebar-item" data-page="content-review" onclick="nav(this)">
      <span class="icon">✅</span> Content Review
      <span class="badge" id="review-badge">0</span>
    </div>
  </div>

  <div class="sidebar-section">
    <div class="sidebar-section-label">Operations</div>
    <div class="sidebar-item" data-page="website-manager" onclick="nav(this)">
      <span class="icon">🌐</span> Website Manager
    </div>
    <div class="sidebar-item" data-page="recommendations" onclick="nav(this)">
      <span class="icon">💡</span> Recommendations
      <span class="badge amber" id="rec-badge">0</span>
    </div>
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
      <div class="section-title">📊 Web Performance</div>
      <div class="grid-2 mb" id="overview-web"></div>

      <!-- Channel snapshot -->
      <div class="section-title">📡 Channel Snapshot</div>
      <div class="grid-2 mb" id="overview-channels"></div>

      <!-- Top pages -->
      <div class="section-title">📄 Top Pages</div>
      <div class="card mb" id="overview-pages"></div>
    </div>

    <!-- ══ PAGE: SEO ═════════════════════════════════════════════════ -->
    <div class="page" id="page-seo">
      <div class="page-header">
        <h1>🔍 SEO &amp; Organic Search</h1>
        <p>Primary growth driver — growing organic to reduce Google Ads spend</p>
      </div>
      <div id="seo-content"></div>
    </div>

    <!-- ══ PAGE: GOOGLE ADS ══════════════════════════════════════════ -->
    <div class="page" id="page-google-ads">
      <div class="page-header">
        <h1>🎯 Google Ads</h1>
        <p>Reduce paid spend as organic coverage grows</p>
      </div>
      <div id="gads-content"></div>
    </div>

    <!-- ══ PAGE: META ADS ════════════════════════════════════════════ -->
    <div class="page" id="page-meta-ads">
      <div class="page-header">
        <h1>📱 Meta Ads</h1>
        <p>Facebook &amp; Instagram paid social</p>
      </div>
      <div id="meta-content"></div>
    </div>

    <!-- ══ PAGE: GBP ═════════════════════════════════════════════════ -->
    <div class="page" id="page-gbp">
      <div class="page-header">
        <h1>📍 Google Business Profile</h1>
        <p>Local search visibility — Malaga &amp; Ellenbrook</p>
      </div>
      <div id="gbp-content"></div>
    </div>

    <!-- ══ PAGE: CONTENT PLANNER ════════════════════════════════════ -->
    <div class="page" id="page-content-planner">
      <div class="page-header">
        <h1>📅 Content Planner</h1>
        <p>2-week content calendar — all channels</p>
      </div>
      <div id="planner-content"></div>
    </div>

    <!-- ══ PAGE: CONTENT REVIEW ═════════════════════════════════════ -->
    <div class="page" id="page-content-review">
      <div class="page-header">
        <h1>✅ Content Review</h1>
        <p>Approval flow: Agent generates → Tia reviews → Jane QC → Joanne posts</p>
      </div>
      <div id="review-content"></div>
    </div>

    <!-- ══ PAGE: WEBSITE MANAGER ════════════════════════════════════ -->
    <div class="page" id="page-website-manager">
      <div class="page-header">
        <h1>🌐 Website Manager</h1>
        <p>Technical SEO health, page performance, dev tasks</p>
      </div>
      <div id="web-content"></div>
    </div>

    <!-- ══ PAGE: RECOMMENDATIONS ════════════════════════════════════ -->
    <div class="page" id="page-recommendations">
      <div class="page-header">
        <h1>💡 Recommendation Tracker</h1>
        <p>AI-generated actions — track from idea to outcome</p>
      </div>
      <div id="rec-content"></div>
    </div>

    <div class="page-footer" id="page-footer"></div>
  </div><!-- /content -->
</div><!-- /main -->
</div><!-- /app -->

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
    <span class="kpi-icon">${icon}</span>
    <div class="kpi-label">${label}</div>
    <div class="kpi-value">${value}</div>
    ${change!==null?`<div class="kpi-change ${chgClass(change)}">${arrow(change)} ${fmtChg(change)} vs prior week</div>`:''}
    ${sub?`<div class="kpi-sub">${sub}</div>`:''}
  </div>`;
const insight = (type,label,text) => `
  <div class="insight ${type}">
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
    kpiCard('📊','Weekly Sessions',fmt(g.sessions,'n'),g.ses_chg,`Prior: ${fmt(g.p_sessions,'n')}`) +
    kpiCard('🎯','Conversions',fmt(g.convs,'n'),g.conv_chg,`Rate: ${fmt(g.conv_rate,'%')}`) +
    kpiCard('🔍','SEO Health',s.health_score+'/100',null,`${s.tk_summary.top_3_count||0} top-3 · DR ${s.domain_rating||'–'}`, s.health_score>=70?'green':s.health_score>=40?'amber':'red') +
    kpiCard('🌱','Organic Value',fmt(s.organic_value,'$'),s.ov_chg,`${fmt(s.organic_traffic,'n')} organic visits/wk`,'green') +
    kpiCard('💰','Ad Spend',fmt(ads.spend,'$2'),ads.spend_chg,`${fmt(ads.convs,'n')} conversions`) +
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
      <div class="card-h">📍 Google Business Profile</div>
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
    <div class="card-h">📄 Top Pages by Traffic</div>
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
  const scoreColor = s.health_score>=70?'#22c55e':s.health_score>=40?'#f59e0b':'#ef4444';

  let html = `
    <div class="kpi-grid cols-4 mb">
      ${kpiCard('🏆','SEO Health Score',s.health_score+'/100',null,s.health_score>=70?'🟢 Strong':s.health_score>=40?'🟡 Building':'🔴 Needs work')}
      ${kpiCard('🌱','Organic Value',fmt(s.organic_value,'$'),s.ov_chg,`${fmt(s.organic_traffic,'n')} visits/wk`,'green')}
      ${kpiCard('🔗','Domain Rating',s.domain_rating||'–',null,'Authority score 0–100')}
      ${kpiCard('📍','Page 1 Keywords',s.tk_summary.top_10_count||0,null,`${s.tk_summary.top_3_count||0} top-3 · ${s.tk_summary.not_ranking||0} not ranking`)}
    </div>`;

  // Key analysis
  const upKws  = s.wow_up.slice(0,3).map(w=>`<b>${w.keyword}</b> (+${w.change} → #${w.current_pos})`).join(', ')||'No data yet';
  const dnKws  = s.wow_down.slice(0,3).map(w=>`<b>${w.keyword}</b> (-${w.change} → #${w.current_pos})`).join(', ')||'No drops this week';
  const topGap = (s.gap_revo[0]||{}).keyword;

  html += `
    <div class="grid-3 mb">
      ${insight('green','↑ Biggest Gains This Week', upKws)}
      ${insight('red','↓ Biggest Drops', dnKws)}
      ${insight('blue','🎯 Top Keyword Gap', topGap?`Revo ranks for <b>${topGap}</b> — CB247 not ranking. Publish a page targeting this keyword.`:'Run pull_ahrefs.py to see keyword gaps')}
    </div>`;

  // Recommendation
  html += insight('teal','💡 This Week\'s SEO Recommendation',
    `<b>Priority 1:</b> Fix any keywords in positions #4–10 with simple on-page changes (H1, meta description, internal links). These are your fastest wins.<br>
     <b>Priority 2:</b> Publish content targeting your top keyword gap vs Revo Fitness.<br>
     <b>Priority 3:</b> Reclaim ${s.broken_backlinks.length} broken backlinks — contact linking sites to update URLs.`);

  // Keyword tracker table
  html += sectionTitle('📋 20 Priority Keywords — Ranking Tracker');
  html += `<div class="card mb"><table>
    <thead><tr><th>Keyword</th><th class="num">Position</th><th class="num">WoW</th><th class="num">Volume</th><th>Status</th></tr></thead><tbody>
    ${s.keywords.map(kw=>`<tr>
      <td>${kw.keyword}</td>
      <td class="num">${posBadge(kw.position)}</td>
      <td class="num">${wowBadge(kw)}</td>
      <td class="num" style="color:var(--muted)">${fmt(kw.volume,'n')}</td>
      <td><span style="font-size:10px;color:var(--muted)">${kw.status||'–'}</span></td>
    </tr>`).join('')||'<tr><td colspan="5" style="color:var(--muted)">No data — run pull_ahrefs.py</td></tr>'}
    </tbody></table></div>`;

  // Keyword gap
  html += sectionTitle('🎯 Keyword Gap — vs Competitors');
  html += `<div class="grid-2 mb">
    <div class="card">
      <div class="card-h">vs Revo Fitness</div>
      <table><thead><tr><th>Keyword</th><th class="num">Volume</th><th class="num">Us</th><th class="num">Revo</th></tr></thead><tbody>
      ${s.gap_revo.map(g=>`<tr><td>${g.keyword}</td><td class="num">${fmt(g.volume,'n')}</td><td class="num">${posBadge(g.cb247_position)}</td><td class="num">${posBadge(g.competitor_pos)}</td></tr>`).join('')||'<tr><td colspan="4" style="color:var(--muted)">No data</td></tr>'}
      </tbody></table>
    </div>
    <div class="card">
      <div class="card-h">vs Anytime Fitness</div>
      <table><thead><tr><th>Keyword</th><th class="num">Volume</th><th class="num">Us</th><th class="num">Them</th></tr></thead><tbody>
      ${s.gap_anytime.map(g=>`<tr><td>${g.keyword}</td><td class="num">${fmt(g.volume,'n')}</td><td class="num">${posBadge(g.cb247_position)}</td><td class="num">${posBadge(g.competitor_pos)}</td></tr>`).join('')||'<tr><td colspan="4" style="color:var(--muted)">No data</td></tr>'}
      </tbody></table>
    </div>
  </div>`;

  // Backlinks
  html += sectionTitle('🔗 Backlink Health');
  html += `<div class="grid-2 mb">
    <div class="card">
      <div class="card-h">Broken Backlinks — Reclaim Opportunities</div>
      <table><thead><tr><th>From</th><th>To (broken)</th><th class="num">DR</th></tr></thead><tbody>
      ${s.broken_backlinks.slice(0,6).map(b=>`<tr><td style="font-size:11px;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${(b.url_from||'').replace(/https?:\/\//,'')}</td><td style="font-size:11px;color:var(--red);max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${(b.url_to||'').replace('https://chasingbetter247.com.au','')}</td><td class="num">${b.domain_rating_source||'–'}</td></tr>`).join('')||'<tr><td colspan="3" style="color:var(--muted)">No broken backlinks — great!</td></tr>'}
      </tbody></table>
    </div>
    <div class="card">
      <div class="card-h">Lost Backlinks (last 30 days)</div>
      <table><thead><tr><th>From</th><th class="num">DR</th><th>Lost</th></tr></thead><tbody>
      ${s.lost_backlinks.slice(0,6).map(b=>`<tr><td style="font-size:11px">${(b.url_from||'').replace(/https?:\/\//,'').slice(0,35)}</td><td class="num">${b.domain_rating_source||'–'}</td><td style="font-size:10px;color:var(--muted)">${(b.lost_date||'').slice(0,10)}</td></tr>`).join('')||'<tr><td colspan="3" style="color:var(--muted)">No lost backlinks this period</td></tr>'}
      </tbody></table>
    </div>
  </div>`;

  $('seo-content').innerHTML = html;
}

// ── Render: Google Ads ───────────────────────────────────────────────────────
function renderGAds() {
  const ads = D.google_ads, mal = ads.malaga, ell = ads.ellenbrook, seo = D.seo;

  let html = `<div class="kpi-grid cols-4 mb">
    ${kpiCard('💰','Total Spend',fmt(ads.spend,'$2'),ads.spend_chg,`${fmt(ads.convs,'n')} conversions`)}
    ${kpiCard('📏','Blended CPA',fmt(ads.cpa,'$2'),null,'Target: $50',ads.cpa>50?'red':'green')}
    ${kpiCard('🟢','Malaga CPA',fmt(mal.cpa,'$2'),null,`${fmt(mal.conv,'n')} conv · ${fmt(mal.spend,'$2')} spend`,mal.cpa>50?'red':'green')}
    ${kpiCard('🔵','Ellenbrook CPA',fmt(ell.cpa,'$2'),null,`${fmt(ell.conv,'n')} conv · ${fmt(ell.spend,'$2')} spend`,ell.cpa>50?'red':'green')}
  </div>`;

  // Key analysis
  html += `<div class="grid-3 mb">
    ${insight('green','✅ Organic Coverage Growing', `Organic value is ${fmt(seo.organic_value,'$')}/wk — equivalent ad spend being replaced by SEO.`)}
    ${insight('amber','💡 Pause Recommendation', `Review keywords where CB247 now ranks #1–3 organically — those ad campaigns can be paused to save budget.`)}
    ${insight('blue','📈 Trend', `${fmtChg(ads.spend_chg)} spend vs prior week. Monitor CPA trend — target is under $50.`)}
  </div>`;

  // Recommendation
  html += insight('teal','💡 This Week\'s Google Ads Recommendation',
    `<b>1. Audit keyword coverage:</b> Check which of your 20 target keywords now rank organically #1–3. Pause those ad groups.<br>
     <b>2. Reallocate budget:</b> Move saved spend to keywords with no organic coverage yet.<br>
     <b>3. Ellenbrook focus:</b> If CPA is higher in Ellenbrook, check if ad copy matches local intent.`);

  // 3-week trend
  html += sectionTitle('📅 3-Week Spend Trend');
  html += `<div class="grid-2 mb">
    <div class="card">
      <div class="card-h">Spend &amp; CPA Trend</div>
      <div class="chart-wrap"><canvas id="adsChart"></canvas></div>
    </div>
    <div class="card">
      <div class="card-h">Campaign Breakdown</div>
      <table><thead><tr><th>Campaign</th><th class="num">Spend</th><th class="num">Conv</th><th class="num">CPA</th></tr></thead><tbody>
      ${ads.campaigns.map(c=>`<tr><td style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${c.name}</td><td class="num">${fmt(c.spend,'$2')}</td><td class="num">${c.conv}</td><td class="num ${c.cpa>50?'bad':'good'}">${fmt(c.cpa,'$2')}</td></tr>`).join('')||'<tr><td colspan="4" style="color:var(--muted)">No campaign data</td></tr>'}
      </tbody></table>
    </div>
  </div>`;

  $('gads-content').innerHTML = html;

  setTimeout(()=>{
    if($('adsChart')&&ads.trend_labels.length) {
      new Chart($('adsChart'),{type:'bar',data:{labels:ads.trend_labels,datasets:[{label:'Spend ($)',data:ads.trend_spend,backgroundColor:'#3FA69A',borderRadius:4,yAxisID:'y'},{label:'CPA ($)',data:ads.trend_cpa,type:'line',borderColor:'#ef4444',backgroundColor:'transparent',borderWidth:2,pointRadius:4,pointBackgroundColor:'#ef4444',tension:.3,yAxisID:'y2'}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'top',labels:{usePointStyle:true,font:{size:10}}}},scales:{x:{grid:{display:false},ticks:{font:{size:10}}},y:{beginAtZero:true,position:'left',ticks:{callback:v=>'$'+v,font:{size:10}},grid:{color:'#f0f0f0'}},y2:{beginAtZero:true,position:'right',ticks:{callback:v=>'$'+v,font:{size:10}},grid:{display:false}}}}});
    }
  },100);
}

// ── Render: Meta Ads ─────────────────────────────────────────────────────────
function renderMeta() {
  const intel = D.intel;
  let html = `
    <div class="insight amber mb">
      <div class="insight-label">Account Status</div>
      <b>Meta Ads account is currently suspended.</b> Content below is preparation for reinstatement.
    </div>`;

  html += `<div class="grid-2 mb">
    <div class="card">
      <div class="card-h">📊 Competitor Ad Themes (from FB Ads Library)</div>
      ${intel.fb_ads_themes.length?
        intel.fb_ads_themes.map(t=>`<div class="stat-row"><span class="stat-label">${t.theme}</span><span class="stat-val">${t.count} competitors using this</span></div>`).join('')
        :'<p style="color:var(--muted);font-size:13px">Run pull_apify.py to load competitor ad intelligence.</p>'}
    </div>
    <div class="card">
      <div class="card-h">🎯 CB247 Advantages Competitors Aren't Using</div>
      ${intel.fb_ads_gaps.length?
        intel.fb_ads_gaps.map(g=>`<div class="stat-row"><span class="stat-label">${g.cb247_advantage}</span><span class="stat-val" style="color:var(--green)">🎯 Own this</span></div><div style="font-size:11px;color:var(--muted);padding:0 0 6px">${g.message}</div>`).join('')
        :'<p style="color:var(--muted);font-size:13px">Run pull_apify.py to load competitor intelligence.</p>'}
    </div>
  </div>`;

  html += insight('teal','💡 Meta Ads Recommendation — When Reinstated',
    `<b>Audience 1 (FIFO):</b> Target WA postcodes near FIFO hubs. Interest: fly-in fly-out, mining, construction. Key message: "Pause your membership anytime. Train hard when you're home."<br>
     <b>Audience 2 (Malaga Families):</b> Parents 28–45, Malaga/Hamersley/Dianella. Key message: "Kids Hub free while you train."<br>
     <b>Audience 3 (Health Newcomers):</b> 18–35 not currently gym members. Key message: "$11.95/week. No lock-in. Try your first week."<br>
     <b>Creative:</b> Lead with Sauna + Ice Bath content — highest engagement in current fitness trends.`);

  html += `<div class="card mb">
    <div class="card-h">📋 Reinstatement Checklist</div>
    <ul class="task-list">
      <li class="task-item"><span class="priority-pill p-critical">Critical</span>Submit identity verification documents to Meta</li>
      <li class="task-item"><span class="priority-pill p-critical">Critical</span>Review ad copy compliance — remove any claims Meta flagged</li>
      <li class="task-item"><span class="priority-pill p-high">High</span>Pre-load 3 audience segments in Ads Manager (FIFO, Families, Newcomers)</li>
      <li class="task-item"><span class="priority-pill p-high">High</span>Create 3 ad creatives — Sauna, Kids Hub, FIFO freeze</li>
      <li class="task-item"><span class="priority-pill p-medium">Medium</span>Set up Meta Pixel events: contact form, location page visit, scroll depth</li>
    </ul>
  </div>`;

  $('meta-content').innerHTML = html;
}

// ── Render: GBP ──────────────────────────────────────────────────────────────
function renderGBP() {
  const gbp = D.gbp, mal = gbp.malaga, ell = gbp.ellenbrook;
  const packRate = gbp.local_pack.pack_presence_rate||0;
  const packKws  = (gbp.local_pack.appearing_in_pack||[]).map(p=>`${p.keyword} (#${p.position})`).join(', ')||'No data';

  let html = `<div class="kpi-grid cols-4 mb">
    ${kpiCard('🟢','Malaga Rating',stars(mal.rating),null,`${fmt(mal.reviews,'n')} reviews`)}
    ${kpiCard('🔵','Ellenbrook Rating',stars(ell.rating),null,`${fmt(ell.reviews,'n')} reviews`)}
    ${kpiCard('📍','Local Pack Rate',packRate+'%',null,`Appearing in 3-pack`)}
    ${kpiCard('📸','Photos Malaga',fmt(mal.photos,'n'),null,'Target: 100 photos')}
  </div>`;

  html += `<div class="grid-3 mb">
    ${insight('green','✅ Key Analysis', `CB247 appearing in local pack for ${packRate}% of tracked keywords: ${packKws}`)}
    ${insight('amber','⚠️ Gap to Close', `Malaga has ${mal.photos||0} photos vs 100 target. Photos directly impact local pack ranking.`)}
    ${insight('teal','💡 Recommendation', `<b>This week:</b> Upload 10 photos to each location (sauna, ice bath, Kids Hub, gym floor). Add a GBP post every Tuesday.`)}
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

  html += sectionTitle('📍 Location Details');
  html += `<div class="grid-2 mb">${locCard('Malaga',mal,'green',530)}${locCard('Ellenbrook',ell,'blue',280)}</div>`;

  // Competitor comparison
  html += sectionTitle('🏆 Competitor Benchmarking');
  html += `<div class="card mb"><table>
    <thead><tr><th>Competitor</th><th>Location</th><th class="num">Rating</th><th class="num">Reviews</th></tr></thead><tbody>
    ${gbp.competitors.map(c=>`<tr><td>${c.name}</td><td>${c.location}</td><td class="num">${stars(c.rating)}</td><td class="num">${fmt(c.reviews,'n')}</td></tr>`).join('')||'<tr><td colspan="4" style="color:var(--muted)">No competitor data — run pull_apify.py</td></tr>'}
    </tbody></table></div>`;

  // GBP tasks
  html += sectionTitle('✅ GBP Action Plan');
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
function renderPlanner() {
  const today = new Date();
  const days = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  // Generate 14 days from today
  const calDays = Array.from({length:14},(_,i)=>{
    const d = new Date(today); d.setDate(d.getDate()+i);
    return {date:d, label:days[d.getDay()]+' '+d.getDate()+' '+months[d.getMonth()]};
  });

  // Sample content items (in real use these come from agent output)
  const CONTENT_ITEMS = [
    {id:'p1',day:0,platform:'gbp',title:'GBP Post — Sauna & Ice Bath',caption:'Recovery is part of training. Our Sauna + Ice Bath combo at ChasingBetter247 Malaga gives your body the reset it needs. $11.95/week, no lock-in.',kw:'sauna gym perth',assignee:'Joanne'},
    {id:'p2',day:1,platform:'instagram',title:'Reel — FIFO Lifestyle',caption:'Fly in. Train hard. We get it. CB247\'s FIFO-friendly freeze means your membership works around your roster.',kw:'fifo gym perth',assignee:'Agust'},
    {id:'p3',day:2,platform:'blog',title:'Blog — Best Gym Malaga',caption:'Targeting "best gym Malaga" — 320 searches/month. Full outline ready for John.',kw:'best gym malaga',assignee:'John'},
    {id:'p4',day:2,platform:'instagram',title:'Instagram — Kids Hub',caption:'Train while the kids play. Our Kids Hub means no more "I can\'t go to the gym today." Tag a parent who needs this.',kw:'kids gym malaga',assignee:'Shauna'},
    {id:'p5',day:4,platform:'tiktok',title:'TikTok — Ice Bath Reaction',caption:'First ice bath at CB247 😅❄️ Would you try this? #icebath #recovery #chasingbetter247',kw:'ice bath gym perth',assignee:'Ivan'},
    {id:'p6',day:5,platform:'gbp',title:'GBP Post — Reformer Pilates',caption:'24/7 Reformer Pilates in Perth. Book your class at CB247 — Malaga & Ellenbrook.',kw:'reformer pilates perth',assignee:'Joanne'},
    {id:'p7',day:7,platform:'instagram',title:'Reel — Gym Tour',caption:'Never been to CB247? Here\'s what $11.95/week gets you. 👀 #gymtour #chasingbetter247',kw:'gym malaga perth',assignee:'Agust'},
    {id:'p8',day:8,platform:'email',title:'Weekly Email Newsletter',caption:'Member spotlight + this week\'s class timetable + sauna booking tip',kw:'',assignee:'Shauna'},
    {id:'p9',day:9,platform:'blog',title:'Blog — FIFO Gym Membership Perth',caption:'Targeting "fifo gym perth" — 210 searches/month. FIFO freeze angle.',kw:'fifo gym membership perth',assignee:'Shauna'},
    {id:'p10',day:10,platform:'tiktok',title:'TikTok — Neon21 Tanning',caption:'You didn\'t know we had THIS at a $11.95/week gym 👀 #neon21 #gymsecrets',kw:'',assignee:'Ivan'},
    {id:'p11',day:11,platform:'gbp',title:'GBP Post — Ellenbrook Special',caption:'Ellenbrook locals — your neighbourhood gym is here. 24/7 access, no lock-in, $11.95/week.',kw:'gym ellenbrook perth',assignee:'Joanne'},
    {id:'p12',day:13,platform:'instagram',title:'Community Post — Member Story',caption:'Member story: how CB247 helped [member] hit their goal. Real stories, real results.',kw:'',assignee:'Shauna'},
  ];

  const statusKey = 'cb247-planner-status';
  const saved = JSON.parse(localStorage.getItem(statusKey)||'{}');
  const STATUSES = ['Idea','Scheduled','Published'];
  const STATUS_COLORS = {Idea:'#dbeafe',Scheduled:'#fef9c3',Published:'#dcfce7'};

  const week = (startDay) => {
    const weekDays = calDays.slice(startDay, startDay+7);
    return `<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:8px;margin-bottom:16px">
      ${weekDays.map((day,i)=>{
        const globalDay = startDay+i;
        const items = CONTENT_ITEMS.filter(c=>c.day===globalDay);
        const isToday = i===0&&startDay===0;
        return `<div style="background:${isToday?'#f0fffe':'#fff'};border-radius:8px;border:1px solid ${isToday?'var(--teal)':'var(--border)'};padding:10px;min-height:120px">
          <div style="font-size:11px;font-weight:700;color:${isToday?'var(--teal)':'var(--muted)'};margin-bottom:6px">${day.label}${isToday?' <span style="background:var(--teal);color:#fff;border-radius:99px;padding:1px 6px;font-size:9px">TODAY</span>':''}</div>
          ${items.map(item=>{
            const status = saved[item.id]||'Idea';
            const bg = STATUS_COLORS[status]||'#f3f4f6';
            return `<div style="background:${bg};border-radius:6px;padding:6px 8px;margin-bottom:4px;cursor:pointer;font-size:11px" onclick="cyclePlannerStatus('${item.id}')">
              <span class="platform-tag platform-${item.platform}" style="font-size:9px">${item.platform.toUpperCase()}</span>
              <div style="font-weight:600;margin:2px 0;line-height:1.3">${item.title}</div>
              <div style="color:var(--muted);font-size:10px">${item.assignee}</div>
              <div style="font-size:9px;margin-top:2px;font-weight:700;color:#666">${status}</div>
            </div>`;
          }).join('')}
        </div>`;
      }).join('')}
    </div>`;
  };

  window.cyclePlannerStatus = (id) => {
    const saved2 = JSON.parse(localStorage.getItem(statusKey)||'{}');
    const curr = saved2[id]||'Idea';
    const next = STATUSES[(STATUSES.indexOf(curr)+1)%STATUSES.length];
    saved2[id] = next;
    localStorage.setItem(statusKey, JSON.stringify(saved2));
    renderPlanner();
  };

  let html = `
    <div class="insight blue mb">
      <div class="insight-label">How to use</div>
      Click any content card to cycle status: Idea → Scheduled → Published. Status saves automatically.
    </div>
    ${sectionTitle('Week 1 — Days 1–7')}${week(0)}
    ${sectionTitle('Week 2 — Days 8–14')}${week(7)}
    <div class="card">
      <div class="card-h">📋 All Content Items</div>
      <table><thead><tr><th>Day</th><th>Platform</th><th>Title</th><th>Assignee</th><th>Keyword</th><th>Status</th></tr></thead><tbody>
      ${CONTENT_ITEMS.map(item=>{
        const status = saved[item.id]||'Idea';
        const day = calDays[item.day];
        return `<tr><td style="font-size:11px">${day?day.label:'–'}</td><td><span class="platform-tag platform-${item.platform}">${item.platform}</span></td><td style="font-weight:600">${item.title}</td><td>${item.assignee}</td><td style="font-size:11px;color:var(--muted)">${item.kw||'–'}</td><td><span style="background:${STATUS_COLORS[status]};border-radius:99px;padding:2px 8px;font-size:10px;font-weight:700">${status}</span></td></tr>`;
      }).join('')}
      </tbody></table>
    </div>`;

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
      ${item.keyword?`<div style="margin-top:6px"><span class="chip" style="font-size:9px">🔍 ${item.keyword}</span></div>`:''}
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
    ${kpiCard('🔗','Broken Backlinks',seo.broken_backlinks.length,null,'Pages to fix or redirect','red')}
    ${kpiCard('📤','Lost Backlinks',seo.lost_backlinks.length,null,'Last 30 days — outreach needed','amber')}
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

  html += sectionTitle('🔗 Broken Backlinks — Fix These Pages');
  html += `<div class="card mb"><table>
    <thead><tr><th>Linking Site</th><th>Broken URL on Our Site</th><th class="num">DR</th><th>Fix</th></tr></thead><tbody>
    ${seo.broken_backlinks.slice(0,8).map(b=>`<tr>
      <td style="font-size:11px">${(b.url_from||'').replace(/https?:\/\//,'').slice(0,40)}</td>
      <td style="font-size:11px;color:var(--red)">${(b.url_to||'').replace('https://chasingbetter247.com.au','')}</td>
      <td class="num">${b.domain_rating_source||'–'}</td>
      <td style="font-size:11px;color:var(--teal)">Add 301 redirect</td>
    </tr>`).join('')||'<tr><td colspan="4" style="color:var(--muted)">No broken backlinks — great! Run pull_ahrefs.py to check.</td></tr>'}
    </tbody></table></div>`;

  html += insight('teal','💡 Website Manager Recommendation',
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
    {id:'r2',channel:'ads',icon:'💰',title:'Pause Google Ads for keywords ranking organically #1–3',why:'Once CB247 ranks #1 organically for a keyword, running an ad on the same keyword wastes budget — users will click the organic result. Audit and pause overlapping campaigns.',owner:'Tia',impact:'Est. $200–400/wk saving',week:'Week of 2 Jun 2026'},
    {id:'r3',channel:'gbp',icon:'📍',title:'Upload 10 photos per location this week',why:'Photo count directly impacts local pack ranking. Malaga has fewer photos than competitor benchmark. Each photo batch improves listing completeness score.',owner:'Joanne',impact:'Local pack ranking ↑',week:'Week of 2 Jun 2026'},
    {id:'r4',channel:'seo',icon:'🔗',title:'Reclaim broken backlinks — contact 3 top-DR linking sites',why:'Sites linking to broken CB247 pages are already willing to link to you. Emailing to update the URL is the fastest DR improvement possible.',owner:'John',impact:'DR increase',week:'Week of 2 Jun 2026'},
    {id:'r5',channel:'web',icon:'🌐',title:'Create /ellenbrook dedicated landing page',why:'Ellenbrook Google Ads spend ~$386/week. A dedicated landing page targeting "gym ellenbrook perth" would allow those ads to be paused.',owner:'Mark + John',impact:'Est. $386/wk saving',week:'Week of 2 Jun 2026'},
    {id:'r6',channel:'gbp',icon:'⭐',title:'Print QR code review cards — both locations',why:'Review velocity is a top GBP ranking signal. Front desk verbal asks + QR code cards proven to increase review rate by 3–5x.',owner:'Tia + Front Desk',impact:'Reviews ↑ → local pack ↑',week:'Week of 2 Jun 2026'},
    {id:'r7',channel:'content',icon:'📱',title:'Lead this week\'s Reels with ice bath / sauna content',why:'Google Trends Perth shows "cold plunge" and "sauna" rising. CB247 has this facility — competitors don\'t heavily feature it. First-mover advantage on social.',owner:'Agust + Ivan',impact:'Engagement ↑',week:'Week of 2 Jun 2026'},
    {id:'r8',channel:'seo',icon:'🎯',title:'Fix H1 tags on top 5 pages',why:'Multiple high-traffic pages missing or duplicating H1 tags. This is a basic on-page SEO issue costing ranking positions.',owner:'Mark',impact:'Rankings ↑ on affected pages',week:'Week of 2 Jun 2026'},
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

  const tagClass = {seo:'tag-seo',ads:'tag-ads',gbp:'tag-gbp',meta:'tag-meta',content:'tag-content',web:'tag-web'};
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
            <div class="rec-icon">${rec.icon}</div>
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

// ── Init ──────────────────────────────────────────────────────────────────────
function init() {
  renderStatus();
  renderOverview();
  renderSEO();
  renderGAds();
  renderMeta();
  renderGBP();
  renderPlanner();
  renderContentReview();
  renderWebsite();
  renderRecommendations();

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
