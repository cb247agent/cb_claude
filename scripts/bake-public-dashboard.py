"""
bake-public-dashboard.py — Generates CB247 team dashboard as a self-contained HTML file.

Output: docs/index.html  (GitHub Pages convention — push repo to deploy)

Run:
    python scripts/bake-public-dashboard.py

Deploy (GitHub Pages):
    git add docs/index.html && git commit -m "dashboard update" && git push
"""

import json
import os
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
DOCS_DIR  = BASE_DIR / "docs"
OUT_FILE  = DOCS_DIR / "index.html"


def load(filename):
    p = STATE_DIR / filename
    try:
        return json.loads(p.read_text()) if p.exists() else None
    except Exception:
        return None


def pct(a, b):
    if not b:
        return None
    return ((a - b) / b) * 100


def arrow(val):
    if val is None:
        return ""
    return "↑" if val > 0 else "↓"


def fmt_pct(val):
    if val is None:
        return "n/a"
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:.1f}%"


def safe(val, fmt=None, fallback="—"):
    if val is None or val == "" or val == 0 and fmt:
        return fallback
    try:
        if fmt == "currency":
            return f"${float(val):,.2f}"
        if fmt == "int":
            return f"{int(val):,}"
        if fmt == "pct":
            return f"{float(val):.1f}%"
        return str(val)
    except Exception:
        return fallback


def build():
    ga4      = load("ga4-data.json")
    gsc      = load("gsc-data.json")
    ads_data = load("ads-data.json")
    apify    = load("apify-data.json")
    ahrefs   = load("ahrefs-data.json")
    refresh  = load("last-refresh.json")

    now = datetime.utcnow().strftime("%d %b %Y, %H:%M UTC")
    refresh_ts = (refresh or {}).get("timestamp", now)

    # ── GA4 ──────────────────────────────────────────────────────────────
    ga4_c = (ga4.get("current")  or {}) if ga4 else {}
    ga4_p = (ga4.get("previous") or {}) if ga4 else {}
    sessions    = int(ga4_c.get("sessions",    0) or 0)
    p_sessions  = int(ga4_p.get("sessions",    0) or 0)
    convs       = int(ga4_c.get("conversions", 0) or 0)
    p_convs     = int(ga4_p.get("conversions", 0) or 0)
    users       = int(ga4_c.get("users",       0) or 0)
    new_users   = int(ga4_c.get("new_users",   0) or 0)
    p_users     = int(ga4_p.get("users",       0) or 0)
    conv_rate   = convs / sessions * 100 if sessions else 0
    p_conv_rate = p_convs / p_sessions * 100 if p_sessions else 0

    ses_chg   = pct(sessions, p_sessions)
    conv_chg  = pct(convs, p_convs)

    devices      = ga4.get("devices", []) if ga4 else []
    mob_sessions = next((int(d.get("sessions", 0) or 0) for d in devices if d.get("deviceCategory") == "mobile"), 0)
    mob_share    = mob_sessions / sessions * 100 if sessions else 0

    sources   = (ga4.get("traffic_sources") or []) if ga4 else []
    total_s   = sessions or 1
    src_labels = json.dumps([s.get("sessionDefaultChannelGroup","") for s in sources[:6]])
    src_vals   = json.dumps([int(s.get("sessions", 0) or 0) for s in sources[:6]])
    src_pcts   = json.dumps([round(int(s.get("sessions",0) or 0) / total_s * 100, 1) for s in sources[:6]])

    top_pages  = (ga4.get("top_pages") or []) if ga4 else []
    ga4_dr     = (ga4.get("date_range") or {}) if ga4 else {}
    ga4_period = f"{ga4_dr.get('start','?')} → {ga4_dr.get('end','?')}"

    # ── GSC ──────────────────────────────────────────────────────────────
    gsc_sum  = (gsc.get("summary") or {}) if gsc else {}
    gsc_dr   = (gsc.get("date_range") or {}) if gsc else {}
    gsc_period = f"{gsc_dr.get('start','?')} → {gsc_dr.get('end','?')}"
    gsc_clicks = int(gsc_sum.get("total_clicks", 0) or 0)
    gsc_impr   = int(gsc_sum.get("total_impressions", 0) or 0)
    gsc_ctr    = float(gsc_sum.get("avg_ctr", 0) or 0) * 100
    gsc_pos    = float(gsc_sum.get("avg_position", 0) or 0)
    top_q      = (gsc.get("top_queries") or [])[:8] if gsc else []

    # ── GOOGLE ADS ───────────────────────────────────────────────────────
    gads_list   = (ads_data.get("google_ads") or []) if ads_data else []
    latest_ads  = gads_list[0] if gads_list else {}
    prev_ads    = gads_list[1] if len(gads_list) > 1 else {}
    combined    = latest_ads.get("combined", {}) or {}
    p_combined  = prev_ads.get("combined",   {}) or {}
    ads_spend   = float(combined.get("spend", 0) or 0)
    p_spend     = float(p_combined.get("spend", 0) or 0)
    ads_cpa     = float(combined.get("cpa", 0) or 0)
    ads_clicks  = int(combined.get("clicks", 0) or 0)
    ad_convs    = int(combined.get("conv", 0) or 0)
    spend_chg   = pct(ads_spend, p_spend)

    mal  = latest_ads.get("malaga",     {}) or {}
    ell  = latest_ads.get("ellenbrook", {}) or {}
    p_mal = prev_ads.get("malaga",     {}) or {}
    p_ell = prev_ads.get("ellenbrook", {}) or {}

    malaga_cpa     = float(mal.get("cpa", 0) or 0)
    ellenbrook_cpa = float(ell.get("cpa", 0) or 0)

    # 3-week trend data for chart
    trend_labels = json.dumps([w.get("week_label","") for w in gads_list[:3]][::-1])
    trend_spend  = json.dumps([float((w.get("combined",{}) or {}).get("spend",0) or 0) for w in gads_list[:3]][::-1])
    trend_cpa    = json.dumps([float((w.get("combined",{}) or {}).get("cpa",0) or 0) for w in gads_list[:3]][::-1])

    campaigns = latest_ads.get("campaigns", [])

    # ── GBP ──────────────────────────────────────────────────────────────
    targets    = (apify.get("competitor_maps", {}) or {}).get("targets", []) if apify else []
    competitors = (apify.get("competitor_maps", {}) or {}).get("competitors", []) if apify else []
    malaga_gbp = next((t for t in targets if t.get("location") == "Malaga"),     {})
    ell_gbp    = next((t for t in targets if t.get("location") == "Ellenbrook"), {})

    mal_reviews = int(malaga_gbp.get("reviews", 0) or 0)
    ell_reviews = int(ell_gbp.get("reviews",   0) or 0)
    mal_photos  = int(malaga_gbp.get("photos",  0) or 0)
    ell_photos  = int(ell_gbp.get("photos",     0) or 0)
    mal_rev_pct = min(100, round(mal_reviews / 530 * 100)) if mal_reviews else 0
    ell_rev_pct = min(100, round(ell_reviews / 280 * 100)) if ell_reviews else 0
    mal_ph_pct  = min(100, round(mal_photos  / 100 * 100)) if mal_photos  else 0
    ell_ph_pct  = min(100, round(ell_photos  / 100 * 100)) if ell_photos  else 0

    # ── AHREFS / SEO ─────────────────────────────────────────────────
    ov_curr      = ((ahrefs or {}).get("organic_value") or {}).get("current_week", {}) or {}
    ov_prev      = ((ahrefs or {}).get("organic_value") or {}).get("previous_week", {}) or {}
    organic_value     = float(ov_curr.get("organic_traffic_value") or 0)
    organic_value_prev= float(ov_prev.get("organic_traffic_value") or 0)
    organic_traffic   = int(ov_curr.get("organic_traffic") or 0)
    ov_chg       = pct(organic_value, organic_value_prev)

    dr_data      = ((ahrefs or {}).get("domain_rating") or {}).get("domain_rating") or {}
    domain_rating= dr_data.get("domain_rating") if dr_data else None

    # Target keyword tracker
    tkp          = (ahrefs or {}).get("target_keyword_positions") or {}
    tk_summary   = tkp.get("summary") or {}
    tk_keywords  = tkp.get("keywords") or []

    # WoW overall keyword changes
    wow_changes  = (ahrefs or {}).get("wow_changes") or []
    wow_up       = [w for w in wow_changes if w.get("direction") == "up"][:5]
    wow_down     = [w for w in wow_changes if w.get("direction") == "down"][:5]

    # Keyword gap
    kw_gap       = (ahrefs or {}).get("keyword_gap") or {}
    gap_revo     = (kw_gap.get("revofitness.com.au") or [])[:8]
    gap_anytime  = (kw_gap.get("anytimefitness.com.au") or [])[:5]

    # Broken backlinks
    broken_bl    = ((ahrefs or {}).get("broken_backlinks") or {}).get("backlinks") or []

    # SEO health score 0–100
    def seo_score():
        score = 0
        if domain_rating:
            score += min(20, int(domain_rating) // 2)     # DR up to 20pts
        top3  = tk_summary.get("top_3_count") or 0
        top10 = tk_summary.get("top_10_count") or 0
        score += min(25, top3 * 5)                         # Top-3 keywords  up to 25pts
        score += min(15, top10 * 2)                        # Page-1 keywords up to 15pts
        if organic_value > 1000:
            score += min(20, int(organic_value // 200))    # Organic value   up to 20pts
        local_pack = (apify or {}).get("local_pack_summary", {}) or {}
        pack_rate  = local_pack.get("pack_presence_rate") or 0
        score += min(20, int(pack_rate // 5))              # Local pack      up to 20pts
        return min(100, score)

    seo_health = seo_score()
    seo_color  = "#22c55e" if seo_health >= 70 else "#f59e0b" if seo_health >= 40 else "#ef4444"

    # Data status flags
    status_ga4    = "✅ Live"    if ga4      else "⚠️ Missing"
    status_gsc    = "✅ Live"    if gsc      else "⚠️ Missing"
    status_ads    = "✅ Live"    if ads_data else "⚠️ Missing"
    status_gbp    = "✅ Live"    if apify    else "⚠️ Missing"
    status_ahrefs = "✅ Live"    if ahrefs   else "⚠️ Missing"
    status_meta   = "⚠️ Suspended" if not (ads_data and ads_data.get("meta_ads")) else "✅ Live"

    # ── TARGET KEYWORD TABLE HTML ─────────────────────────────────────
    def pos_badge(pos):
        if pos is None: return '<span style="color:#999">–</span>'
        if pos <= 3:    return f'<span style="background:#dcfce7;color:#16a34a;padding:1px 7px;border-radius:12px;font-weight:700">#{pos}</span>'
        if pos <= 10:   return f'<span style="background:#dbeafe;color:#1d4ed8;padding:1px 7px;border-radius:12px;font-weight:700">#{pos}</span>'
        if pos <= 20:   return f'<span style="background:#fef9c3;color:#854d0e;padding:1px 7px;border-radius:12px;font-weight:600">#{pos}</span>'
        return f'<span style="background:#fee2e2;color:#991b1b;padding:1px 7px;border-radius:12px">#{pos}</span>'

    def wow_badge(kw):
        d = kw.get("wow_direction")
        c = kw.get("wow_change")
        if d == "up":   return f'<span style="color:#16a34a;font-weight:700">↑{c}</span>'
        if d == "down": return f'<span style="color:#dc2626;font-weight:700">↓{c}</span>'
        if d == "new":  return '<span style="color:#7c3aed;font-size:10px">NEW</span>'
        return '<span style="color:#999">—</span>'

    kw_rows = ""
    for kw in tk_keywords[:20]:
        vol = kw.get("volume") or 0
        kw_rows += f"""<tr>
          <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{kw.get('keyword','')}</td>
          <td class="num">{pos_badge(kw.get('position'))}</td>
          <td class="num">{wow_badge(kw)}</td>
          <td class="num" style="color:var(--muted)">{vol:,}</td>
          <td style="font-size:10px;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--teal)">{(kw.get('url') or '').replace('https://chasingbetter247.com.au','')[:40]}</td>
        </tr>"""

    # ── KEYWORD GAP TABLE HTML ────────────────────────────────────────
    gap_rows = ""
    for gk in gap_revo[:6]:
        cb_pos   = gk.get("cb247_position")
        comp_pos = gk.get("competitor_pos")
        gap_rows += f"""<tr>
          <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{gk.get('keyword','')}</td>
          <td class="num">{gk.get('volume',0):,}</td>
          <td class="num" style="color:#dc2626">{pos_badge(cb_pos) if cb_pos else '<span style="color:#dc2626">–</span>'}</td>
          <td class="num" style="color:#16a34a">{pos_badge(comp_pos) if comp_pos else '–'}</td>
        </tr>"""

    # ── TOP PAGES HTML ────────────────────────────────────────────────────
    pages_rows = ""
    for i, pg in enumerate(top_pages[:10], 1):
        path  = pg.get("pagePath", "")
        views = int(pg.get("screenPageViews", 0) or 0)
        sess  = int(pg.get("sessions",        0) or 0)
        pages_rows += f"""
        <tr>
          <td class="rank">#{i}</td>
          <td class="page-path">{path}</td>
          <td class="num">{views:,}</td>
          <td class="num">{sess:,}</td>
        </tr>"""

    # ── QUERIES HTML ─────────────────────────────────────────────────────
    query_rows = ""
    for i, q in enumerate(top_q, 1):
        query_rows += f"""
        <tr>
          <td class="rank">#{i}</td>
          <td class="query-text">{q.get('query','')}</td>
          <td class="num">{q.get('clicks',0)}</td>
          <td class="num">{q.get('impressions',0):,}</td>
          <td class="num">{q.get('ctr',0)*100:.1f}%</td>
          <td class="num">#{q.get('position',0):.1f}</td>
        </tr>"""

    # ── CAMPAIGNS HTML ───────────────────────────────────────────────────
    camp_rows = ""
    for c in campaigns[:8]:
        cpa_v  = float(c.get("cpa", 0) or 0)
        cpa_cls = "cpa-high" if cpa_v > 50 else "cpa-ok"
        camp_rows += f"""
        <tr>
          <td>{c.get('name','—')[:45]}</td>
          <td class="num">${c.get('spend',0):.2f}</td>
          <td class="num">{int(c.get('clicks',0)):,}</td>
          <td class="num">{int(c.get('conv',0))}</td>
          <td class="num {cpa_cls}">${cpa_v:.2f}</td>
        </tr>"""

    # ── COMPETITOR HTML ──────────────────────────────────────────────────
    comp_rows = ""
    for c in competitors[:6]:
        name    = (c.get("title") or c.get("query","—"))[:35]
        loc     = c.get("location","—")
        rating  = c.get("rating","—")
        reviews = c.get("reviews","—")
        comp_rows += f"""
        <tr>
          <td>{name}</td>
          <td>{loc}</td>
          <td class="num">⭐ {rating}</td>
          <td class="num">{reviews}</td>
        </tr>"""

    # ── WoW MOVERS HTML ──────────────────────────────────────────────
    wow_up_html = ""
    for w in wow_up:
        wow_up_html += (
            '<div style="display:flex;justify-content:space-between;padding:4px 0;'
            'font-size:12px;border-bottom:1px solid var(--border)">'
            '<span>' + w["keyword"] + '</span>'
            '<span style="color:#16a34a;font-weight:700">+' + str(w["change"]) + ' &rarr; #' + str(w["current_pos"]) + '</span></div>'
        )
    wow_down_html = ""
    for w in wow_down:
        wow_down_html += (
            '<div style="display:flex;justify-content:space-between;padding:4px 0;'
            'font-size:12px;border-bottom:1px solid var(--border)">'
            '<span>' + w["keyword"] + '</span>'
            '<span style="color:#dc2626;font-weight:700">-' + str(w["change"]) + ' &rarr; #' + str(w["current_pos"]) + '</span></div>'
        )
    if wow_up_html or wow_down_html:
        wow_movers_html = (
            '<div style="margin-top:14px">'
            '<div style="font-size:12px;font-weight:700;color:var(--muted);'
            'text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px">Biggest Movers This Week</div>'
            + wow_up_html + wow_down_html + '</div>'
        )
    else:
        wow_movers_html = '<p style="color:var(--muted);font-size:12px;margin-top:8px">No WoW data yet</p>'

    # ── KW GAP TABLE HTML ────────────────────────────────────────────
    if gap_rows:
        gap_extra = ('<div style="margin-top:8px;font-size:11px;color:var(--muted)">+'
                     + str(len(gap_revo)-6) + ' more in SEO brief</div>') if len(gap_revo) > 6 else ""
        gap_table_html = (
            '<table><thead><tr><th>Keyword</th><th class="num">Vol</th>'
            '<th class="num">Us</th><th class="num">Revo</th></tr></thead>'
            '<tbody>' + gap_rows + '</tbody></table>' + gap_extra
        )
    else:
        gap_table_html = '<p style="color:var(--muted);font-size:12px;padding:10px 0">No Ahrefs data yet — run pull_ahrefs.py</p>'

    # ── KW TRACKER TABLE HTML ─────────────────────────────────────────
    if kw_rows:
        kw_table_html = (
            '<table><thead><tr>'
            '<th>Keyword</th><th class="num">Position</th>'
            '<th class="num">WoW</th><th class="num">Volume</th><th>Page</th>'
            '</tr></thead><tbody>' + kw_rows + '</tbody></table>'
        )
    else:
        kw_table_html = '<p style="color:var(--muted);font-size:12px;padding:10px 0">No Ahrefs data yet — run pull_ahrefs.py</p>'

    # ── KW TRACKER SUMMARY ───────────────────────────────────────────
    tk_summary_str = (
        str(tk_summary.get("top_3_count", 0)) + " top-3 · " +
        str(tk_summary.get("top_10_count", 0)) + " page-1 · " +
        str(tk_summary.get("not_ranking", 0)) + " not ranking"
    )

    # ─────────────────────────────────────────────────────────────────────
    # HTML
    # ─────────────────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CB247 Marketing Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.5.1" integrity="sha384-jb8JQMbMoBUzgWatfe6COACi2ljcDdZQ2OxczGA3bGNeWe+6DChMTBJemed7ZnvJ" crossorigin="anonymous"></script>
<style>
/* ── Reset & Base ────────────────────────────────────────────── */
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
:root {{
  --teal:       #3FA69A;
  --teal-dark:  #2d8a7e;
  --teal-light: #e8f5f4;
  --bg:         #F0F2F5;
  --card:       #ffffff;
  --text:       #1a1a2e;
  --muted:      #6b7280;
  --border:     #e5e7eb;
  --red:        #ef4444;
  --green:      #22c55e;
  --amber:      #f59e0b;
  --radius:     10px;
  --shadow:     0 1px 4px rgba(0,0,0,0.08), 0 2px 12px rgba(0,0,0,0.04);
  --gap:        16px;
}}
body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg);
  color: var(--text);
  font-size: 14px;
  line-height: 1.5;
}}
a {{ color: var(--teal); text-decoration: none; }}

/* ── Layout ────────────────────────────────────────────────────── */
.wrap {{ max-width: 1400px; margin: 0 auto; padding: 16px; }}
.grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: var(--gap); }}
.grid-3 {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--gap); }}
.grid-4 {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--gap); }}
.mb {{ margin-bottom: var(--gap); }}
.section-title {{
  font-size: 13px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.6px; color: var(--muted); margin-bottom: 12px;
  display: flex; align-items: center; gap: 6px;
}}
.section-title::after {{
  content: ''; flex: 1; height: 1px; background: var(--border);
}}

/* ── Header ───────────────────────────────────────────────────── */
header {{
  background: linear-gradient(135deg, #1a1a2e 0%, var(--teal-dark) 100%);
  color: #fff;
  border-radius: var(--radius);
  padding: 20px 24px;
  margin-bottom: var(--gap);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}}
header h1 {{
  font-size: 20px; font-weight: 700; letter-spacing: -0.3px;
}}
header h1 span {{
  color: #7ee8e0;
}}
.header-meta {{
  text-align: right; font-size: 12px; opacity: 0.8; line-height: 1.8;
}}
.header-badge {{
  display: inline-block; background: rgba(255,255,255,0.15);
  border-radius: 20px; padding: 2px 10px; font-size: 11px; margin-top: 4px;
}}

/* ── Status bar ───────────────────────────────────────────────── */
.status-bar {{
  background: var(--card);
  border-radius: var(--radius);
  padding: 10px 20px;
  margin-bottom: var(--gap);
  display: flex; gap: 24px; flex-wrap: wrap;
  box-shadow: var(--shadow);
  font-size: 12px;
}}
.status-item {{ display: flex; align-items: center; gap: 6px; }}
.status-label {{ color: var(--muted); }}

/* ── KPI Cards ────────────────────────────────────────────────── */
.kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--gap); margin-bottom: var(--gap); }}
.kpi-card {{
  background: var(--card);
  border-radius: var(--radius);
  padding: 20px 22px;
  box-shadow: var(--shadow);
  border-left: 4px solid var(--teal);
  position: relative;
  overflow: hidden;
}}
.kpi-card::before {{
  content: '';
  position: absolute; top: 0; right: 0;
  width: 60px; height: 60px;
  background: var(--teal-light);
  border-radius: 50%;
  transform: translate(20px, -20px);
}}
.kpi-icon {{
  font-size: 20px; margin-bottom: 10px; display: block;
}}
.kpi-label {{
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.5px; color: var(--muted); margin-bottom: 4px;
}}
.kpi-value {{
  font-size: 30px; font-weight: 800; color: var(--text);
  letter-spacing: -1px; line-height: 1;
}}
.kpi-change {{
  font-size: 12px; font-weight: 600; margin-top: 6px;
  display: flex; align-items: center; gap: 3px;
}}
.kpi-change.up   {{ color: var(--green); }}
.kpi-change.down {{ color: var(--red); }}
.kpi-change.flat {{ color: var(--muted); }}
.kpi-sub {{ font-size: 11px; color: var(--muted); margin-top: 2px; }}
.kpi-alert {{ border-left-color: var(--red); }}
.kpi-good  {{ border-left-color: var(--green); }}

/* ── Cards ────────────────────────────────────────────────────── */
.card {{
  background: var(--card);
  border-radius: var(--radius);
  padding: 20px 22px;
  box-shadow: var(--shadow);
}}
.card h3 {{
  font-size: 14px; font-weight: 700; margin-bottom: 14px;
  color: var(--text); display: flex; align-items: center; gap: 6px;
}}
.card-period {{
  font-size: 11px; color: var(--muted); font-weight: 400; margin-left: auto;
}}

/* ── Stat rows ───────────────────────────────────────────────── */
.stat-row {{
  display: flex; justify-content: space-between;
  align-items: center;
  padding: 7px 0;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
}}
.stat-row:last-child {{ border-bottom: none; }}
.stat-label {{ color: var(--muted); }}
.stat-value {{ font-weight: 600; color: var(--text); }}
.stat-value.good {{ color: var(--green); }}
.stat-value.warn {{ color: var(--amber); }}
.stat-value.bad  {{ color: var(--red); }}

/* ── Location cards ──────────────────────────────────────────── */
.loc-card {{
  background: var(--card);
  border-radius: var(--radius);
  padding: 20px 22px;
  box-shadow: var(--shadow);
}}
.loc-header {{
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 14px;
}}
.loc-dot {{
  width: 10px; height: 10px; border-radius: 50%;
  flex-shrink: 0;
}}
.dot-green {{ background: #22c55e; }}
.dot-blue  {{ background: #3b82f6; }}
.loc-name {{ font-weight: 700; font-size: 15px; }}
.cpa-badge {{
  margin-left: auto;
  font-size: 11px; font-weight: 700;
  padding: 2px 8px; border-radius: 20px;
}}
.cpa-ok  {{ background: #dcfce7; color: #16a34a; }}
.cpa-hi  {{ background: #fee2e2; color: #dc2626; }}

/* ── Progress bars ───────────────────────────────────────────── */
.progress-wrap {{ margin: 10px 0 4px; }}
.progress-label {{
  display: flex; justify-content: space-between;
  font-size: 11px; color: var(--muted); margin-bottom: 4px;
}}
.progress-track {{
  background: var(--border); border-radius: 99px;
  height: 6px; overflow: hidden;
}}
.progress-fill {{
  background: var(--teal); height: 100%; border-radius: 99px;
  transition: width 0.5s ease;
}}

/* ── Stars ───────────────────────────────────────────────────── */
.stars {{ color: #f59e0b; letter-spacing: 1px; }}

/* ── Charts ──────────────────────────────────────────────────── */
.chart-wrap {{ position: relative; height: 180px; }}

/* ── Tables ──────────────────────────────────────────────────── */
table {{
  width: 100%; border-collapse: collapse; font-size: 12px;
}}
thead th {{
  text-align: left; padding: 7px 10px;
  font-size: 11px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.4px; color: var(--muted);
  border-bottom: 2px solid var(--border);
  white-space: nowrap;
}}
tbody td {{
  padding: 7px 10px; border-bottom: 1px solid var(--border);
}}
tbody tr:last-child td {{ border-bottom: none; }}
tbody tr:hover {{ background: #f9fafb; }}
.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
.rank {{ color: var(--muted); font-size: 11px; width: 28px; }}
.page-path {{ font-family: monospace; font-size: 11px; color: var(--teal); }}
.query-text {{ max-width: 200px; }}
.cpa-high {{ color: var(--red); font-weight: 700; }}
.cpa-ok   {{ color: var(--green); }}

/* ── Action checklist ────────────────────────────────────────── */
.actions-grid {{
  display: grid; grid-template-columns: 1fr 1fr 1fr;
  gap: var(--gap); margin-bottom: var(--gap);
}}
.action-group {{ background: var(--card); border-radius: var(--radius); padding: 18px 20px; box-shadow: var(--shadow); }}
.action-group h4 {{
  font-size: 12px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.5px; margin-bottom: 12px;
  display: flex; align-items: center; gap: 6px;
}}
.action-item {{
  display: flex; align-items: flex-start; gap: 8px;
  padding: 6px 0; border-bottom: 1px solid var(--border);
  font-size: 12px; line-height: 1.4;
}}
.action-item:last-child {{ border-bottom: none; }}
.action-dot {{
  width: 8px; height: 8px; border-radius: 50%;
  flex-shrink: 0; margin-top: 4px;
}}
.dot-red    {{ background: var(--red); }}
.dot-amber  {{ background: var(--amber); }}
.dot-yellow {{ background: #eab308; }}

/* ── Footer ──────────────────────────────────────────────────── */
footer {{
  text-align: center; font-size: 11px; color: var(--muted);
  padding: 24px 0 12px;
}}

/* ── Responsive ──────────────────────────────────────────────── */
@media (max-width: 1100px) {{
  .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
  .grid-4   {{ grid-template-columns: repeat(2, 1fr); }}
  .actions-grid {{ grid-template-columns: 1fr 1fr; }}
}}
@media (max-width: 700px) {{
  .kpi-grid, .grid-2, .grid-3, .grid-4, .actions-grid {{
    grid-template-columns: 1fr;
  }}
}}
</style>
</head>
<body>
<div class="wrap">

<!-- ── HEADER ─────────────────────────────────────────────────── -->
<header>
  <div>
    <h1>ChasingBetter<span>247</span> — Marketing Dashboard</h1>
    <div style="font-size:12px;opacity:0.7;margin-top:4px;">
      📍 Malaga + Ellenbrook &nbsp;·&nbsp; Perth, WA &nbsp;·&nbsp; $11.95/week, no lock-in
    </div>
  </div>
  <div class="header-meta">
    <div>Updated: <strong>{now}</strong></div>
    <div>Data refresh: {refresh_ts}</div>
    <span class="header-badge">Auto-updates every Monday</span>
  </div>
</header>

<!-- ── DATA STATUS ────────────────────────────────────────────── -->
<div class="status-bar">
  <div class="status-item"><span class="status-label">GA4:</span> <strong>{status_ga4}</strong></div>
  <div class="status-item"><span class="status-label">Search Console:</span> <strong>{status_gsc}</strong></div>
  <div class="status-item"><span class="status-label">Google Ads:</span> <strong>{status_ads}</strong></div>
  <div class="status-item"><span class="status-label">Ahrefs:</span> <strong>{status_ahrefs}</strong></div>
  <div class="status-item"><span class="status-label">GBP / Maps:</span> <strong>{status_gbp}</strong></div>
  <div class="status-item"><span class="status-label">Meta Ads:</span> <strong>{status_meta}</strong></div>
  <div style="margin-left:auto;font-size:11px;color:var(--muted);">
    Run <code>bash scripts/weekly-report.sh</code> to refresh all data + run agents
  </div>
</div>

<!-- ── KPI ROW — 6 cards ──────────────────────────────────────── -->
<div class="kpi-grid mb" style="grid-template-columns:repeat(3,1fr)">
  <div class="kpi-card">
    <span class="kpi-icon">📊</span>
    <div class="kpi-label">Weekly Sessions</div>
    <div class="kpi-value">{sessions:,}</div>
    <div class="kpi-change {'up' if (ses_chg or 0) >= 0 else 'down'}">
      {arrow(ses_chg)} {fmt_pct(ses_chg)} vs prior week
    </div>
    <div class="kpi-sub">Prior: {p_sessions:,}</div>
  </div>

  <div class="kpi-card {'kpi-good' if convs > p_convs else ''}">
    <span class="kpi-icon">🎯</span>
    <div class="kpi-label">Conversions</div>
    <div class="kpi-value">{convs}</div>
    <div class="kpi-change {'up' if (conv_chg or 0) >= 0 else 'down'}">
      {arrow(conv_chg)} {fmt_pct(conv_chg)} vs prior week
    </div>
    <div class="kpi-sub">Conv. rate: {conv_rate:.1f}% (prior {p_conv_rate:.1f}%)</div>
  </div>

  <div class="kpi-card">
    <span class="kpi-icon">💰</span>
    <div class="kpi-label">Google Ads Spend</div>
    <div class="kpi-value">${ads_spend:,.0f}</div>
    <div class="kpi-change {'up' if (spend_chg or 0) >= 0 else 'down'}">
      {arrow(spend_chg)} {fmt_pct(spend_chg)} vs prior week
    </div>
    <div class="kpi-sub">{ad_convs} conversions · {ads_clicks:,} clicks</div>
  </div>

  <div class="kpi-card {'kpi-alert' if ads_cpa > 50 else 'kpi-good'}">
    <span class="kpi-icon">{'⚠️' if ads_cpa > 50 else '✅'}</span>
    <div class="kpi-label">Blended CPA</div>
    <div class="kpi-value">${ads_cpa:.2f}</div>
    <div class="kpi-change {'down' if ads_cpa > 50 else 'up'}">
      {'⚠️ Above $50 target' if ads_cpa > 50 else '✅ Within target'}
    </div>
    <div class="kpi-sub">Mal: ${malaga_cpa:.2f} · Ell: ${ellenbrook_cpa:.2f}</div>
  </div>

  <!-- SEO Health Score -->
  <div class="kpi-card" style="border-left-color:{seo_color}">
    <span class="kpi-icon">🔍</span>
    <div class="kpi-label">SEO Health Score</div>
    <div class="kpi-value" style="color:{seo_color}">{seo_health}<small style="font-size:16px;font-weight:400;color:var(--muted)">/100</small></div>
    <div class="kpi-change {'up' if seo_health >= 60 else 'down'}">
      {'🟢 Strong' if seo_health >= 70 else '🟡 Building' if seo_health >= 40 else '🔴 Needs work'}
    </div>
    <div class="kpi-sub">
      {tk_summary.get('top_3_count',0)} top-3 · {tk_summary.get('top_10_count',0)} page-1 · DR {domain_rating or '–'}
    </div>
  </div>

  <!-- Organic Value ($) -->
  <div class="kpi-card {'kpi-good' if organic_value > organic_value_prev else ''}">
    <span class="kpi-icon">🌱</span>
    <div class="kpi-label">Organic Value (SEO)</div>
    <div class="kpi-value">${organic_value:,.0f}</div>
    <div class="kpi-change {'up' if (ov_chg or 0) >= 0 else 'down'}">
      {arrow(ov_chg)} {fmt_pct(ov_chg)} vs prior week
    </div>
    <div class="kpi-sub">Equiv. ad spend replaced · {organic_traffic:,} visits</div>
  </div>
</div>

<!-- ── GA4 + GSC ──────────────────────────────────────────────── -->
<div class="section-title">📊 Web Traffic · {ga4_period}</div>
<div class="grid-2 mb">
  <div class="card">
    <h3>Google Analytics 4 <span class="card-period">{ga4_period}</span></h3>
    <div class="stat-row"><span class="stat-label">Sessions</span><span class="stat-value">{sessions:,} ({fmt_pct(ses_chg)})</span></div>
    <div class="stat-row"><span class="stat-label">Users</span><span class="stat-value">{users:,}</span></div>
    <div class="stat-row"><span class="stat-label">New Users</span><span class="stat-value">{new_users:,}</span></div>
    <div class="stat-row"><span class="stat-label">Conversions</span><span class="stat-value">{convs} ({fmt_pct(conv_chg)})</span></div>
    <div class="stat-row"><span class="stat-label">Conv. Rate</span><span class="stat-value">{conv_rate:.1f}%</span></div>
    <div class="stat-row"><span class="stat-label">Mobile Share</span><span class="stat-value {'warn' if mob_share > 80 else ''}">{mob_share:.0f}%</span></div>
    <div style="margin-top:14px;">
      <div style="font-size:12px;color:var(--muted);margin-bottom:8px;font-weight:600;">TRAFFIC BY CHANNEL</div>
      <div class="chart-wrap"><canvas id="channelChart"></canvas></div>
    </div>
  </div>

  <div class="card">
    <h3>Google Search Console <span class="card-period">{gsc_period}</span></h3>
    <div class="stat-row"><span class="stat-label">Organic Clicks</span><span class="stat-value">{gsc_clicks:,}</span></div>
    <div class="stat-row"><span class="stat-label">Impressions</span><span class="stat-value">{gsc_impr:,}</span></div>
    <div class="stat-row"><span class="stat-label">Avg. CTR</span><span class="stat-value">{gsc_ctr:.2f}%</span></div>
    <div class="stat-row"><span class="stat-label">Avg. Position</span><span class="stat-value">#{gsc_pos:.1f}</span></div>
    <div style="margin-top:14px;">
      <div style="font-size:12px;color:var(--muted);margin-bottom:8px;font-weight:600;">TOP QUERIES</div>
      <table>
        <thead><tr><th></th><th>Query</th><th class="num">Clicks</th><th class="num">Impr</th><th class="num">CTR</th><th class="num">Pos</th></tr></thead>
        <tbody>{query_rows or '<tr><td colspan="6" style="color:var(--muted);padding:10px;">No data — run pull_gsc.py</td></tr>'}</tbody>
      </table>
    </div>
  </div>
</div>

<!-- ── SEO KEYWORD TRACKER ────────────────────────────────────── -->
<div class="section-title">🔍 SEO — Keyword Rankings &amp; Organic Value</div>
<div class="grid-2 mb">

  <!-- Organic value tracker -->
  <div class="card">
    <h3>🌱 Organic Value Tracker <span class="card-period">SEO replacing Google Ads</span></h3>
    <div class="stat-row">
      <span class="stat-label">Organic traffic value</span>
      <span class="stat-value {'good' if organic_value > 0 else ''}">${organic_value:,.0f}/wk</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">WoW change</span>
      <span class="stat-value {'good' if (ov_chg or 0) >= 0 else 'bad'}">{fmt_pct(ov_chg)} {arrow(ov_chg or 0)}</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">Organic traffic</span>
      <span class="stat-value">{organic_traffic:,} visits/wk</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">Domain Rating</span>
      <span class="stat-value">{domain_rating or '–'}</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">Keywords ranking</span>
      <span class="stat-value">{tk_summary.get('top_3_count',0)} top-3 &nbsp;·&nbsp; {tk_summary.get('top_10_count',0)} page-1 &nbsp;·&nbsp; {tk_summary.get('top_20_count',0)} page-2</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">Not yet ranking</span>
      <span class="stat-value {'warn' if tk_summary.get('not_ranking',0) > 5 else ''}">{tk_summary.get('not_ranking',0)} / 20 priority KWs</span>
    </div>

    <!-- WoW movers -->
    {wow_movers_html}
  </div>

  <!-- Keyword gap vs Revo -->
  <div class="card">
    <h3>🎯 Keyword Gap — vs Revo Fitness <span class="card-period">AU rankings</span></h3>
    <div style="font-size:11px;color:var(--muted);margin-bottom:10px">
      Keywords Revo ranks for that CB247 doesn't — highest-priority content opportunities
    </div>
    {gap_table_html}
  </div>
</div>

<!-- Target keyword ranking table -->
<div class="card mb">
  <h3>📋 20 Priority Keywords — Ranking Tracker
    <span class="card-period">{tk_summary_str}</span>
  </h3>
  {kw_table_html}
</div>

<!-- ── TOP PAGES ──────────────────────────────────────────────── -->
<div class="section-title">📄 Top Pages</div>
<div class="card mb">
  <table>
    <thead><tr><th></th><th>Page</th><th class="num">Views</th><th class="num">Sessions</th></tr></thead>
    <tbody>{pages_rows or '<tr><td colspan="4" style="color:var(--muted);padding:10px;">No data — run pull_ga4.py</td></tr>'}</tbody>
  </table>
</div>

<!-- ── GOOGLE ADS ─────────────────────────────────────────────── -->
<div class="section-title">📈 Google Ads — Paid Search</div>
<div class="grid-2 mb">
  <div class="loc-card">
    <div class="loc-header">
      <span class="loc-dot dot-green"></span>
      <span class="loc-name">🟢 Malaga</span>
      <span class="cpa-badge {'cpa-hi' if malaga_cpa > 50 else 'cpa-ok'}">CPA ${malaga_cpa:.2f} {'⚠️' if malaga_cpa > 50 else '✅'}</span>
    </div>
    <div class="stat-row"><span class="stat-label">Spend</span><span class="stat-value">${mal.get('spend',0):.2f} <small style="color:var(--muted)">prior ${p_mal.get('spend',0):.2f}</small></span></div>
    <div class="stat-row"><span class="stat-label">Clicks</span><span class="stat-value">{int(mal.get('clicks',0)):,} · CTR {mal.get('ctr',0):.2f}%</span></div>
    <div class="stat-row"><span class="stat-label">Conversions</span><span class="stat-value">{int(mal.get('conv',0))}</span></div>
    <div class="stat-row"><span class="stat-label">CPA</span>
      <span class="stat-value {'bad' if malaga_cpa > 50 else 'good'}">${malaga_cpa:.2f}</span>
    </div>
  </div>

  <div class="loc-card">
    <div class="loc-header">
      <span class="loc-dot dot-blue"></span>
      <span class="loc-name">🔵 Ellenbrook</span>
      <span class="cpa-badge {'cpa-hi' if ellenbrook_cpa > 50 else 'cpa-ok'}">CPA ${ellenbrook_cpa:.2f} {'⚠️' if ellenbrook_cpa > 50 else '✅'}</span>
    </div>
    <div class="stat-row"><span class="stat-label">Spend</span><span class="stat-value">${ell.get('spend',0):.2f} <small style="color:var(--muted)">prior ${p_ell.get('spend',0):.2f}</small></span></div>
    <div class="stat-row"><span class="stat-label">Clicks</span><span class="stat-value">{int(ell.get('clicks',0)):,} · CTR {ell.get('ctr',0):.2f}%</span></div>
    <div class="stat-row"><span class="stat-label">Conversions</span><span class="stat-value">{int(ell.get('conv',0))}</span></div>
    <div class="stat-row"><span class="stat-label">CPA</span>
      <span class="stat-value {'bad' if ellenbrook_cpa > 50 else 'good'}">${ellenbrook_cpa:.2f}</span>
    </div>
  </div>
</div>

<!-- 3-week trend + campaigns -->
<div class="grid-2 mb">
  <div class="card">
    <h3>📅 3-Week Spend Trend</h3>
    <div class="chart-wrap"><canvas id="trendChart"></canvas></div>
  </div>
  <div class="card">
    <h3>Campaign Breakdown</h3>
    <table>
      <thead><tr><th>Campaign</th><th class="num">Spend</th><th class="num">Clicks</th><th class="num">Conv</th><th class="num">CPA</th></tr></thead>
      <tbody>{camp_rows or '<tr><td colspan="5" style="color:var(--muted);padding:10px;">No campaign data</td></tr>'}</tbody>
    </table>
  </div>
</div>

<!-- ── GBP ────────────────────────────────────────────────────── -->
<div class="section-title">📍 Google Business Profile — Local Visibility</div>
<div class="grid-2 mb">
  <div class="loc-card">
    <div class="loc-header">
      <span class="loc-dot dot-green"></span>
      <span class="loc-name">🟢 Malaga GBP</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">Rating</span>
      <span class="stat-value">
        <span class="stars">{'★' * round(float(malaga_gbp.get('rating',0) or 0))}{'☆' * (5 - round(float(malaga_gbp.get('rating',0) or 0)))}</span>
        {malaga_gbp.get('rating','—')}
      </span>
    </div>
    <div class="progress-wrap">
      <div class="progress-label"><span>Reviews: {mal_reviews} / 530 target</span><span>{mal_rev_pct}%</span></div>
      <div class="progress-track"><div class="progress-fill" style="width:{mal_rev_pct}%"></div></div>
    </div>
    <div class="progress-wrap">
      <div class="progress-label"><span>Photos: {mal_photos} / 100 target</span><span>{mal_ph_pct}%</span></div>
      <div class="progress-track"><div class="progress-fill" style="width:{mal_ph_pct}%"></div></div>
    </div>
    <div class="stat-row" style="margin-top:8px;"><span class="stat-label">Profile</span><span class="stat-value">{malaga_gbp.get('completeness_score','—')}% complete</span></div>
  </div>

  <div class="loc-card">
    <div class="loc-header">
      <span class="loc-dot dot-blue"></span>
      <span class="loc-name">🔵 Ellenbrook GBP</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">Rating</span>
      <span class="stat-value">
        <span class="stars">{'★' * round(float(ell_gbp.get('rating',0) or 0))}{'☆' * (5 - round(float(ell_gbp.get('rating',0) or 0)))}</span>
        {ell_gbp.get('rating','—')}
      </span>
    </div>
    <div class="progress-wrap">
      <div class="progress-label"><span>Reviews: {ell_reviews} / 280 target</span><span>{ell_rev_pct}%</span></div>
      <div class="progress-track"><div class="progress-fill" style="width:{ell_rev_pct}%"></div></div>
    </div>
    <div class="progress-wrap">
      <div class="progress-label"><span>Photos: {ell_photos} / 100 target</span><span>{ell_ph_pct}%</span></div>
      <div class="progress-track"><div class="progress-fill" style="width:{ell_ph_pct}%"></div></div>
    </div>
    <div class="stat-row" style="margin-top:8px;"><span class="stat-label">Profile</span><span class="stat-value">{ell_gbp.get('completeness_score','—')}% complete</span></div>
  </div>
</div>

<!-- Competitor table -->
{f'''<div class="card mb">
  <h3>📊 Competitor Benchmarking</h3>
  <table>
    <thead><tr><th>Competitor</th><th>Location</th><th class="num">Rating</th><th class="num">Reviews</th></tr></thead>
    <tbody>{comp_rows}</tbody>
  </table>
</div>''' if comp_rows else ''}

<!-- ── KEY ACTIONS ────────────────────────────────────────────── -->
<div class="section-title">⚡ Key Actions This Week</div>
<div class="actions-grid">
  <div class="action-group">
    <h4 style="color:var(--red);">🔴 Critical — Do Now</h4>
    <div class="action-item"><span class="action-dot dot-red"></span><span>Print QR code review cards — place at Malaga + Ellenbrook reception</span></div>
    <div class="action-item"><span class="action-dot dot-red"></span><span>Brief front desk on verbal review ask script</span></div>
    <div class="action-item"><span class="action-dot dot-red"></span><span>Submit disavow file to Google Search Console (37 toxic domains)</span></div>
    <div class="action-item"><span class="action-dot dot-red"></span><span>Fix 3 broken pages — add 301 redirects</span></div>
    <div class="action-item"><span class="action-dot dot-red"></span><span>Add H1 tags to 29 pages (dev task)</span></div>
  </div>
  <div class="action-group">
    <h4 style="color:var(--amber);">🟠 High — This Week</h4>
    <div class="action-item"><span class="action-dot dot-amber"></span><span>Rewrite GBP descriptions with local keywords (both locations)</span></div>
    <div class="action-item"><span class="action-dot dot-amber"></span><span>Seed GBP Q&amp;A with 6 pre-answered questions</span></div>
    <div class="action-item"><span class="action-dot dot-amber"></span><span>Audit + complete all GBP Services/Products listings</span></div>
    <div class="action-item"><span class="action-dot dot-amber"></span><span>Add LocalBusiness schema markup (40 pages)</span></div>
    <div class="action-item"><span class="action-dot dot-amber"></span><span>Create /ellenbrook landing page — saves ~$386/week in ads</span></div>
  </div>
  <div class="action-group">
    <h4 style="color:#ca8a04;">🟡 Medium — This Month</h4>
    <div class="action-item"><span class="action-dot dot-yellow"></span><span>Begin weekly GBP posts every Tuesday (4-week rotation)</span></div>
    <div class="action-item"><span class="action-dot dot-yellow"></span><span>Upload 10 priority photos per location (sauna, ice bath, Kids Hub)</span></div>
    <div class="action-item"><span class="action-dot dot-yellow"></span><span>Publish blog: 'Best Gym in Malaga' (targets $137/wk ad keyword)</span></div>
    <div class="action-item"><span class="action-dot dot-yellow"></span><span>Expand /massage page — 1,300 searches/month at position #16</span></div>
    <div class="action-item"><span class="action-dot dot-yellow"></span><span>Submit NAP listings to AU directories (True Local, Yelp, etc.)</span></div>
  </div>
</div>

<!-- ── FOOTER ─────────────────────────────────────────────────── -->
<footer>
  CB247 Marketing Agent — Auto-updated every Monday &nbsp;·&nbsp;
  Contact: <a href="mailto:tia@chasingbetter.com.au">tia@chasingbetter.com.au</a> &nbsp;·&nbsp;
  Generated: {now}
</footer>

</div><!-- /wrap -->

<script>
// ── Channel chart ────────────────────────────────────────────────
const srcLabels = {src_labels};
const srcVals   = {src_vals};
const srcPcts   = {src_pcts};
const TEAL = '#3FA69A';

if (document.getElementById('channelChart') && srcLabels.length) {{
  new Chart(document.getElementById('channelChart'), {{
    type: 'bar',
    data: {{
      labels: srcLabels,
      datasets: [{{
        label: 'Sessions',
        data: srcVals,
        backgroundColor: [
          '#3FA69A','#2d8a7e','#5bbdb5','#7dccc6','#a0dbd8','#c3ecea'
        ],
        borderRadius: 4,
      }}]
    }},
    options: {{
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          callbacks: {{
            label: ctx => ` ${{ctx.parsed.x.toLocaleString()}} sessions (${{srcPcts[ctx.dataIndex]}}%)`
          }}
        }}
      }},
      scales: {{
        x: {{ beginAtZero: true, grid: {{ color: '#f0f0f0' }}, ticks: {{ font: {{ size: 11 }} }} }},
        y: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 11 }} }} }}
      }}
    }}
  }});
}}

// ── 3-week trend chart ───────────────────────────────────────────
const trendLabels = {trend_labels};
const trendSpend  = {trend_spend};
const trendCpa    = {trend_cpa};

if (document.getElementById('trendChart') && trendLabels.length) {{
  new Chart(document.getElementById('trendChart'), {{
    type: 'bar',
    data: {{
      labels: trendLabels,
      datasets: [
        {{
          label: 'Spend ($)',
          data: trendSpend,
          backgroundColor: '#3FA69A',
          borderRadius: 4,
          yAxisID: 'y',
        }},
        {{
          label: 'CPA ($)',
          data: trendCpa,
          type: 'line',
          borderColor: '#ef4444',
          backgroundColor: 'transparent',
          borderWidth: 2,
          pointRadius: 4,
          pointBackgroundColor: '#ef4444',
          tension: 0.3,
          yAxisID: 'y2',
        }}
      ]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{
        legend: {{ position: 'top', labels: {{ usePointStyle: true, padding: 16, font: {{ size: 11 }} }} }},
        tooltip: {{
          callbacks: {{
            label: ctx => ` ${{ctx.dataset.label}}: ${{ctx.parsed.y.toFixed(2)}}`
          }}
        }}
      }},
      scales: {{
        x:  {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 11 }} }} }},
        y:  {{ beginAtZero: true, position: 'left',  ticks: {{ callback: v => '$' + v, font: {{ size: 11 }} }}, grid: {{ color: '#f0f0f0' }} }},
        y2: {{ beginAtZero: true, position: 'right', ticks: {{ callback: v => '$' + v, font: {{ size: 11 }} }}, grid: {{ display: false }} }}
      }}
    }}
  }});
}}
</script>
</body>
</html>
"""

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(html, encoding="utf-8")
    print(f"✅ Dashboard generated → {OUT_FILE}")
    print(f"   Open: file://{OUT_FILE}")
    return OUT_FILE


if __name__ == "__main__":
    build()
