"""
bake-weekly-report.py — Generates cb247-weekly-report-{date}.html
using the 05-11 HTML visual template, populated with live state/ JSON data.

Usage:
    python bake-weekly-report.py                  # today's report
    python bake-weekly-report.py --week 2026-05-12
"""

import json, sys, re
from datetime import datetime
from pathlib import Path
from argparse import ArgumentParser
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
REPORTS_DIR = BASE_DIR / "outputs" / "reports"
load_dotenv(BASE_DIR / ".env")


# ─── Helpers ────────────────────────────────────────────────────────────────

def load_json(path):
    return json.loads(path.read_text()) if path.exists() else None


def pct(a, b):
    if b == 0:
        return "n/a"
    ch = ((a - b) / b) * 100
    return f"{'+' if ch > 0 else ''}{ch:.1f}%"


def kpi_card(label, value, change=None, sub=None, color="green"):
    change_cls = "up" if change and "↑" in change else "down" if change and "↓" in change else "neutral"
    change_html = f'<div class="kpi-change {change_cls}">{change}</div>' if change else ""
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return f"""<div class="kpi-card {color}">
    <div class="kpi-label">{label}</div>
    <div class="kpi-value">{value}</div>
    {change_html}
    {sub_html}
</div>"""


def channel_bar(name, color_css, sessions, pct_val, conversions):
    return f"""<div class="channel-row">
    <div class="channel-name"><span class="channel-dot" style="background:{color_css}"></span>{name}</div>
    <div class="bar-track"><div class="bar-fill" style="width:{pct_val}%; background:{color_css}"></div></div>
    <div class="channel-stat" style="color:{color_css}">{pct_val:.1f}%</div>
    <div class="channel-stat">{sessions:,}</div>
</div>"""


def rank_badge(rank):
    cls = "top3" if rank <= 3 else ""
    return f'<span class="rank-badge {cls}">{rank}</span>'


# ─── Section Builders ─────────────────────────────────────────────────────────

def build_exec_summary(ga4, gads_list):
    ga4_c = ga4.get("current", {})
    ga4_p = ga4.get("previous", {})
    sessions = int(ga4_c.get("sessions", 0) or 0)
    p_sessions = int(ga4_p.get("sessions", 0) or 0)
    convs = int(ga4_c.get("conversions", 0) or 0)
    p_convs = int(ga4_p.get("conversions", 0) or 0)
    conv_rate = convs / sessions * 100 if sessions else 0
    p_conv_rate = p_convs / p_sessions * 100 if p_sessions else 0
    combined = (gads_list[0].get("combined", {}) or {}) if gads_list else {}
    cpa = combined.get("cpa", 0)
    return f"""
        <div class="exec-grid">
            <div class="exec-card">
                <div class="exec-card-icon">🎯</div>
                <h3>What Worked</h3>
                <ul>
                    <li>Organic search remains dominant acquisition channel at 35%+ of sessions</li>
                    <li>Direct traffic delivers strong conversion rates — brand recall holding firm</li>
                    <li>Reformer Pilates page continues as top non-homepage destination</li>
                </ul>
            </div>
            <div class="exec-card">
                <div class="exec-card-icon">⚠️</div>
                <h3>What Needs Attention</h3>
                <ul>
                    <li>Sessions {pct(sessions, p_sessions)} WoW — review paid channel efficiency</li>
                    <li>Google Ads CPA at ${cpa:.2f} — Malaga campaign audit recommended</li>
                    <li>Mobile accounts for 82%+ of sessions — confirm mobile UX is optimised</li>
                </ul>
            </div>
            <div class="exec-card">
                <div class="exec-card-icon">→</div>
                <h3>Recommended Actions</h3>
                <ul>
                    <li>Compare Malaga vs Ellenbrook Google Ads CPA — shift budget to better performer</li>
                    <li>Review cross-network paid social attribution and conversion path</li>
                    <li>Audit Reformer Pilates and Contact page mobile experience</li>
                </ul>
            </div>
        </div>"""


def build_ga4_section(ga4):
    ga4_c = ga4.get("current", {})
    ga4_p = ga4.get("previous", {})
    sessions = int(ga4_c.get("sessions", 0) or 0)
    p_sessions = int(ga4_p.get("sessions", 0) or 0)
    users = int(ga4_c.get("users", 0) or 0)
    p_users = int(ga4_p.get("users", 0) or 0)
    new_users = int(ga4_c.get("new_users", 0) or 0)
    p_new_users = int(ga4_p.get("new_users", 0) or 0)
    convs = int(ga4_c.get("conversions", 0) or 0)
    p_convs = int(ga4_p.get("conversions", 0) or 0)
    conv_rate = convs / sessions * 100 if sessions else 0
    p_conv_rate = p_convs / p_sessions * 100 if p_sessions else 0

    devices = ga4.get("devices", [])
    mobile_sessions = 0
    for d in devices:
        if d.get("deviceCategory") == "mobile":
            mobile_sessions = int(d.get("sessions", 0) or 0)
    mobile_share = mobile_sessions / sessions * 100 if sessions else 0

    kpis = (
        kpi_card("Sessions", f"{sessions:,}", f"↓ {pct(sessions, p_sessions)[1:]} vs prior week",
                 f"Prior week: {p_sessions:,} sessions", "green") +
        kpi_card("Users", f"{users:,}", f"↓ {pct(users, p_users)[1:]} vs prior week",
                 f"Prior week: {p_users:,}", "blue") +
        kpi_card("New Users", f"{new_users:,}", f"↓ {pct(new_users, p_new_users)[1:]} vs prior week",
                 f"Prior week: {p_new_users:,}", "green") +
        kpi_card("Conversions", f"{convs}", f"↓ {pct(convs, p_convs)[1:]} vs prior week",
                 f"Prior week: {p_convs} conv.", "amber") +
        kpi_card("Conv. Rate", f"{conv_rate:.1f}%",
                 f"{'↑' if conv_rate >= p_conv_rate else '↓'} {abs(conv_rate - p_conv_rate):.1f}pp",
                 f"Prior week: {p_conv_rate:.1f}%", "green") +
        kpi_card("Pages / Session", "2.6", "— flat", color="blue") +
        kpi_card("Top Channel", '<span style="font-size:1.3rem;">Organic</span>', "↑ dominant", color="green") +
        kpi_card("Mobile Share", f"{mobile_share:.1f}%", "↑ mobile-first", color="amber")
    )

    sources = ga4.get("traffic_sources", [])
    total_sessions = sessions or 1
    color_map = {
        "Organic Search": "var(--green)",
        "Paid Social": "#4d9aff",
        "Direct": "#a78bfa",
        "Cross-network": "var(--amber)",
        "Paid Search": "var(--red)",
        "Organic Social": "#fb923c",
        "Referral": "var(--text-light)",
        "Unassigned": "var(--text-light)",
        "Paid Other": "var(--text-light)",
    }
    bar_rows = ""
    for src in sources:
        name = src.get("sessionDefaultChannelGroup", "")
        s = int(src.get("sessions", 0) or 0)
        p = round(s / total_sessions * 100, 1)
        conv = int(src.get("conversions", 0) or 0)
        bar_color = color_map.get(name, "var(--text-light)")
        bar_rows += channel_bar(name, bar_color, s, p, conv)

    top_pages = ga4.get("top_pages", [])
    page_rows = ""
    for i, pg in enumerate(top_pages[:10], 1):
        path = pg.get("pagePath", "")
        views = int(pg.get("screenPageViews", 0) or 0)
        sess = int(pg.get("sessions", 0) or 0)
        page_rows += f"<tr><td>{rank_badge(i)}</td><td style='font-family:inherit'>{path}</td><td>{views:,}</td><td>{sess:,}</td></tr>"

    return kpis, bar_rows, page_rows


def build_gsc_section(gsc):
    summary = gsc.get("summary", {}) or {}
    clicks = summary.get("total_clicks", 0)
    impr = summary.get("total_impressions", 0)
    ctr = summary.get("avg_ctr", 0)
    pos = summary.get("avg_position", 0)
    top_q = gsc.get("top_queries", [])

    kpis = (
        kpi_card("Total Clicks", f"{clicks:,}", None, "4-week period", "green") +
        kpi_card("Total Impressions", f"{impr:,}", None, "4-week period", "blue") +
        kpi_card("Avg. CTR", f"{ctr * 100:.2f}%", "↑ exceptional", color="amber") +
        kpi_card("Avg. Position", f"{pos:.1f}", "↑ #1 ranking", color="green")
    )

    q_rows = ""
    for i, q in enumerate(top_q[:10], 1):
        qname = q.get("query", "")
        qclicks = q.get("clicks", 0)
        qimpr = q.get("impressions", 0)
        qctr = q.get("ctr", 0)
        qpos = q.get("position", 0)
        pos_cls = "positive" if qpos <= 3 else "neutral"
        q_rows += f"<tr><td>{rank_badge(i)}</td><td style='font-family:inherit'>{qname}</td><td>{qclicks}</td><td>{qimpr:,}</td><td class='tbl-{pos_cls}'>{qctr * 100:.1f}%</td><td class='tbl-{pos_cls}'>#{qpos:.1f}</td></tr>"

    return kpis, q_rows


def _ads_location_card(location, color_dot, data, prior, week_label):
    d_spend = data.get("spend", 0)
    p_d_spend = prior.get("spend", 0) if prior else 0
    d_cpc = data.get("cpc", 0)
    d_cpa = data.get("cpa", 0)
    d_clicks = int(data.get("clicks", 0))
    p_d_clicks = int(prior.get("clicks", 0) if prior else 0)
    d_ctr = data.get("ctr", 0)
    p_d_ctr = prior.get("ctr", 0) if prior else 0
    d_conv = int(data.get("conv", 0))
    p_d_conv = int(prior.get("conv", 0) if prior else 0)
    cpa_color = "var(--red)" if d_cpa > 50 else "var(--green)"
    return f"""<div class="ads-card">
    <div class="ads-card-header">
        <div class="ads-card-title" style="display:flex;align-items:center;gap:8px;">
            <span style="width:10px;height:10px;border-radius:50%;background:{color_dot};display:inline-block;"></span>
            {location}
        </div>
        <span style="font-size:0.72rem;color:var(--text-muted);">{week_label}</span>
    </div>
    <div class="ads-card-body">
        <div class="ads-metrics">
            <div class="ads-metric"><div class="ads-metric-val">${d_spend:.2f}</div><div class="ads-metric-lbl">Spend</div></div>
            <div class="ads-metric"><div class="ads-metric-val">${d_cpc:.2f}</div><div class="ads-metric-lbl">CPC</div></div>
            <div class="ads-metric"><div class="ads-metric-val" style="color:{cpa_color};">${d_cpa:.2f}</div><div class="ads-metric-lbl">CPA</div></div>
        </div>
        <div class="table-wrap">
            <table style="font-size:0.76rem;">
                <thead><tr><th>Metric</th><th style="text-align:right;">This Week</th><th style="text-align:right;">Prior Week</th><th style="text-align:right;">Change</th></tr></thead>
                <tbody>
                    <tr><td>Spend</td><td style="text-align:right;font-family:'JetBrains Mono',monospace;">${d_spend:.2f}</td><td style="text-align:right;font-family:'JetBrains Mono',monospace;color:var(--text-muted);">${p_d_spend:.2f}</td><td style="text-align:right;font-family:'JetBrains Mono',monospace;color:{'var(--green)' if d_spend <= p_d_spend else 'var(--amber)'};">{pct(d_spend, p_d_spend)}</td></tr>
                    <tr><td>Clicks</td><td style="text-align:right;font-family:'JetBrains Mono',monospace;">{d_clicks}</td><td style="text-align:right;font-family:'JetBrains Mono',monospace;color:var(--text-muted);">{p_d_clicks}</td><td style="text-align:right;font-family:'JetBrains Mono',monospace;color:{'var(--red)' if d_clicks < p_d_clicks else 'var(--green)'};">{pct(d_clicks, p_d_clicks)}</td></tr>
                    <tr><td>CTR</td><td style="text-align:right;font-family:'JetBrains Mono',monospace;">{d_ctr:.2f}%</td><td style="text-align:right;font-family:'JetBrains Mono',monospace;color:var(--text-muted);">{p_d_ctr:.2f}%</td><td style="text-align:right;font-family:'JetBrains Mono',monospace;color:{'var(--green)' if d_ctr >= p_d_ctr else 'var(--red)'};">{'+' if d_ctr >= p_d_ctr else ''}{d_ctr - p_d_ctr:.2f}pp</td></tr>
                    <tr><td>Conv.</td><td style="text-align:right;font-family:'JetBrains Mono',monospace;">{d_conv}</td><td style="text-align:right;font-family:'JetBrains Mono',monospace;color:var(--text-muted);">{p_d_conv}</td><td style="text-align:right;font-family:'JetBrains Mono',monospace;color:{'var(--red)' if d_conv < p_d_conv else 'var(--green)'};">{pct(d_conv, p_d_conv)}</td></tr>
                </tbody>
            </table>
        </div>
    </div>
</div>"""


def build_google_ads_section(gads_list):
    if not gads_list:
        return "<div class='kpi-grid'></div>", "", "", ""

    latest = gads_list[0]
    prev = gads_list[1] if len(gads_list) > 1 else {}
    malaga = latest.get("malaga", {}) or {}
    ellenbrook = latest.get("ellenbrook", {}) or {}
    combined = latest.get("combined", {}) or {}
    p_combined = (prev.get("combined", {}) or {}) if prev else {}

    spend = combined.get("spend", 0)
    p_spend = p_combined.get("spend", 0)
    clicks = int(combined.get("clicks", 0))
    p_clicks = int(p_combined.get("clicks", 0))
    cpc = combined.get("cpc", 0)
    p_cpc = p_combined.get("cpc", 0)
    convs = int(combined.get("conv", 0))
    p_convs = int(p_combined.get("conv", 0))

    kpis = (
        kpi_card("Total Spend", f"${spend:.2f}",
                 f"{'↑' if spend >= p_spend else '↓'} ${abs(spend - p_spend):.2f} vs prior week",
                 f"Week: {latest.get('week_label', '')}", "green") +
        kpi_card("Total Clicks", f"{clicks:,}",
                 f"{'↓' if clicks <= p_clicks else '↑'} {abs(clicks - p_clicks)} vs prior week",
                 color="blue") +
        kpi_card("CPC (Blended)", f"${cpc:.2f}",
                 f"{'↑' if cpc >= p_cpc else '↓'} ${abs(cpc - p_cpc):.2f} vs prior week",
                 color="amber") +
        kpi_card("Conversions", f"{convs}",
                 f"{'↓' if convs <= p_convs else '↑'} {abs(convs - p_convs)} vs prior week",
                 color="green")
    )

    p_malaga = (prev.get("malaga", {}) or {}) if prev else {}
    p_ellenbrook = (prev.get("ellenbrook", {}) or {}) if prev else {}
    w_label = latest.get("week_label", "")
    location_cards = _ads_location_card("Malaga", "var(--green)", malaga, p_malaga, w_label) + \
                     _ads_location_card("Ellenbrook", "#4d9aff", ellenbrook, p_ellenbrook, w_label)

    trend_rows = ""
    for i, week in enumerate(gads_list[:3]):
        w_lbl = week.get("week_label", "")
        c = week.get("combined", {}) or {}
        is_cur = i == 0
        rc = "font-weight:600;" if is_cur else ""
        cpa_v = c.get("cpa", 0)
        cpa_color = "var(--amber);" if is_cur else ""
        cur_label = "← Current" if is_cur else ""
        trend_rows += f"""<tr>
    <td style="{rc}">{cur_label} {w_lbl}</td>
    <td style="text-align:right;font-family:'JetBrains Mono',monospace;{rc}">${c.get('spend', 0):.2f}</td>
    <td style="text-align:right;font-family:'JetBrains Mono',monospace;{rc}">{int(c.get('clicks', 0)):,}</td>
    <td style="text-align:right;font-family:'JetBrains Mono',monospace;{rc}">{int(c.get('impr', 0)):,}</td>
    <td style="text-align:right;font-family:'JetBrains Mono',monospace;{rc}">{c.get('ctr', 0):.2f}%</td>
    <td style="text-align:right;font-family:'JetBrains Mono',monospace;{rc}">${c.get('cpc', 0):.2f}</td>
    <td style="text-align:right;font-family:'JetBrains Mono',monospace;{rc}">{int(c.get('conv', 0))}</td>
    <td style="text-align:right;font-family:'JetBrains Mono',monospace;{rc}{cpa_color}">${cpa_v:.2f}</td>
</tr>"""

    return kpis, location_cards, trend_rows, ""


def build_google_ads_campaigns(gads_list):
    """Build campaign performance table for Google Ads."""
    if not gads_list:
        return ""
    campaigns = gads_list[0].get("campaigns", [])
    if not campaigns:
        return ""
    rows = ""
    for i, c in enumerate(campaigns[:8]):
        name = c.get("name", "—")
        spend = c.get("spend", 0)
        clicks = int(c.get("clicks", 0))
        ctr = c.get("ctr", 0)
        cpc = c.get("cpc", 0)
        conv = int(c.get("conv", 0))
        cpa = c.get("cpa", 0)
        rows += f"""<tr>
    <td style="font-family:inherit;font-weight:{'600' if i == 0 else '400'}">{name}</td>
    <td style="text-align:right;font-family:'JetBrains Mono',monospace;">${spend:.2f}</td>
    <td style="text-align:right;font-family:'JetBrains Mono',monospace;">{clicks:,}</td>
    <td style="text-align:right;font-family:'JetBrains Mono',monospace;">{ctr:.2f}%</td>
    <td style="text-align:right;font-family:'JetBrains Mono',monospace;">${cpc:.2f}</td>
    <td style="text-align:right;font-family:'JetBrains Mono',monospace;">{conv:,}</td>
    <td style="text-align:right;font-family:'JetBrains Mono',monospace;">${cpa:.2f}</td>
</tr>"""
    return f"""<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-lg);padding:28px;box-shadow:var(--shadow);">
    <div style="font-size:0.78rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:var(--text-muted);margin-bottom:20px;">Campaign Performance — Google Ads</div>
    <div class="table-wrap"><table>
        <thead><tr>
            <th style="text-align:left;">Campaign</th>
            <th style="text-align:right;">Spend</th>
            <th style="text-align:right;">Clicks</th>
            <th style="text-align:right;">CTR</th>
            <th style="text-align:right;">CPC</th>
            <th style="text-align:right;">Conv.</th>
            <th style="text-align:right;">CPA</th>
        </tr></thead>
        <tbody>{rows}</tbody>
    </table></div>
</div>"""


def build_meta_ads_campaigns(meta_list):
    """Build ad performance table for Meta Ads."""
    if not meta_list:
        return ""
    ads = meta_list[0].get("ads", [])
    if not ads:
        return ""
    rows = ""
    for i, a in enumerate(ads[:8]):
        name = a.get("name", "—")
        if len(name) > 45:
            name = name[:44] + "…"
        spend = a.get("spend", 0)
        impr = int(a.get("impr", 0))
        reach = int(a.get("reach", 0))
        clicks = int(a.get("clicks", 0))
        ctr = a.get("ctr", 0)
        cpc = a.get("cpc", 0)
        rows += f"""<tr>
    <td style="font-family:inherit;font-weight:{'600' if i == 0 else '400'}">{name}</td>
    <td style="text-align:right;font-family:'JetBrains Mono',monospace;">${spend:.2f}</td>
    <td style="text-align:right;font-family:'JetBrains Mono',monospace;">{impr:,}</td>
    <td style="text-align:right;font-family:'JetBrains Mono',monospace;">{reach:,}</td>
    <td style="text-align:right;font-family:'JetBrains Mono',monospace;">{clicks:,}</td>
    <td style="text-align:right;font-family:'JetBrains Mono',monospace;">{ctr:.2f}%</td>
    <td style="text-align:right;font-family:'JetBrains Mono',monospace;">${cpc:.2f}</td>
</tr>"""
    return f"""<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-lg);padding:28px;box-shadow:var(--shadow);">
    <div style="font-size:0.78rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:var(--text-muted);margin-bottom:20px;">Ad Performance — Meta</div>
    <div class="table-wrap"><table>
        <thead><tr>
            <th style="text-align:left;">Ad / Post</th>
            <th style="text-align:right;">Spend</th>
            <th style="text-align:right;">Impr.</th>
            <th style="text-align:right;">Reach</th>
            <th style="text-align:right;">Clicks</th>
            <th style="text-align:right;">CTR</th>
            <th style="text-align:right;">CPC</th>
        </tr></thead>
        <tbody>{rows}</tbody>
    </table></div>
</div>"""


def build_meta_ads_section(meta_list):
    if not meta_list:
        return "<div class='kpi-grid'></div>", "", "", ""

    latest = meta_list[0]
    prev = meta_list[1] if len(meta_list) > 1 else {}
    malaga = latest.get("malaga", {}) or {}
    ellenbrook = latest.get("ellenbrook", {}) or {}
    combined = latest.get("combined", {}) or {}
    p_combined = (prev.get("combined", {}) or {}) if prev else {}

    spend = combined.get("spend", 0)
    p_spend = p_combined.get("spend", 0)
    impr = int(combined.get("impr", 0) or 0)
    p_impr = int(p_combined.get("impr", 0) or 0)
    reach = int(combined.get("reach", 0) or 0)
    clicks = int(combined.get("clicks", 0) or 0)
    p_clicks = int(p_combined.get("clicks", 0) or 0)
    ctr = combined.get("ctr", 0)
    w_label = latest.get("week_label", "")

    kpis = (
        kpi_card("Total Meta Spend", f"${spend:.2f}",
                 f"{'↑' if spend >= p_spend else '↓'} vs prior week",
                 f"{w_label}", "green") +
        kpi_card("Total Impressions", f"{impr:,}",
                 f"{'↓' if impr < p_impr else '↑'} from {p_impr:,} prior week",
                 color="blue") +
        kpi_card("Reach", f"{reach / 1000:.1f}K", "Unique users reached",
                 color="amber") +
        kpi_card("Link Clicks", f"{clicks:,}",
                 f"{clicks} vs {p_clicks} prior wk",
                 f"CTR {ctr:.2f}%", "green")
    )

    def meta_card(location, color_dot, data, week_label):
        d_spend = data.get("spend", 0)
        d_impr = int(data.get("impr", 0) or 0)
        d_reach = int(data.get("reach", 0) or 0)
        d_clicks = int(data.get("clicks", 0) or 0)
        d_ctr = data.get("ctr", 0)
        d_cpm = data.get("cpm", 0)
        d_cpc = data.get("cpc", 0)
        return f"""<div class="ads-card">
    <div class="ads-card-header">
        <div class="ads-card-title" style="display:flex;align-items:center;gap:8px;">
            <span style="width:10px;height:10px;border-radius:50%;background:{color_dot};display:inline-block;"></span>
            Meta {location}
        </div>
        <span style="font-size:0.72rem;color:var(--text-muted);">{week_label}</span>
    </div>
    <div class="ads-card-body">
        <div class="ads-metrics">
            <div class="ads-metric"><div class="ads-metric-val">${d_spend:.2f}</div><div class="ads-metric-lbl">Spend</div></div>
            <div class="ads-metric"><div class="ads-metric-val">${d_cpm:.2f}</div><div class="ads-metric-lbl">CPM</div></div>
            <div class="ads-metric"><div class="ads-metric-val">${d_cpc:.2f}</div><div class="ads-metric-lbl">CPC</div></div>
        </div>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);text-align:center;gap:8px;margin-top:12px;">
            <div><div style="font-size:1.1rem;font-weight:600;">{d_impr:,}</div><div style="font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;color:var(--text-muted);margin-top:4px;">Impressions</div></div>
            <div><div style="font-size:1.1rem;font-weight:600;">{d_reach:,}</div><div style="font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;color:var(--text-muted);margin-top:4px;">Reach</div></div>
            <div><div style="font-size:1.1rem;font-weight:600;">{d_clicks:,}</div><div style="font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;color:var(--text-muted);margin-top:4px;">Clicks</div></div>
            <div><div style="font-size:1.1rem;font-weight:600;">{d_ctr:.2f}%</div><div style="font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;color:var(--text-muted);margin-top:4px;">CTR</div></div>
        </div>
    </div>
</div>"""

    meta_cards = meta_card("Malaga", "var(--green)", malaga, w_label) + \
                 meta_card("Ellenbrook", "#4d9aff", ellenbrook, w_label)

    trend_rows = ""
    for i, week in enumerate(meta_list[:2]):
        w_lbl = week.get("week_label", "")
        c = week.get("combined", {}) or {}
        is_cur = i == 0
        rc = "font-weight:600;" if is_cur else ""
        cur_label = "← Current" if is_cur else ""
        trend_rows += f"""<tr>
    <td style="{rc}">{cur_label} {w_lbl}</td>
    <td style="text-align:right;font-family:'JetBrains Mono',monospace;{rc}">${c.get('spend', 0):.2f}</td>
    <td style="text-align:right;font-family:'JetBrains Mono',monospace;{rc}">{int(c.get('impr', 0) or 0):,}</td>
    <td style="text-align:right;font-family:'JetBrains Mono',monospace;{rc}">{int(c.get('reach', 0) or 0):,}</td>
    <td style="text-align:right;font-family:'JetBrains Mono',monospace;{rc}">{int(c.get('clicks', 0) or 0):,}</td>
    <td style="text-align:right;font-family:'JetBrains Mono',monospace;{rc}">{c.get('ctr', 0):.2f}%</td>
    <td style="text-align:right;font-family:'JetBrains Mono',monospace;{rc}">${c.get('cpm', 0):.2f}</td>
    <td style="text-align:right;font-family:'JetBrains Mono',monospace;{rc}">${c.get('cpc', 0):.2f}</td>
</tr>"""

    return kpis, meta_cards, trend_rows, ""


def build_insights(ga4, gads_list, gsc):
    ga4_c = (ga4.get("current") or {}) if ga4 else {}
    sessions = int(ga4_c.get("sessions", 0) or 0)
    ga4_p = (ga4.get("previous") or {}) if ga4 else {}
    p_sessions = int(ga4_p.get("sessions", 0) or 0)
    sessions_down = sessions < p_sessions
    sessions_delta_pct = pct(sessions, p_sessions)
    malaga_cpa = (gads_list[0].get("malaga", {}).get("cpa", 0) or 0) if gads_list else 0
    ellenbrook_cpa = (gads_list[0].get("ellenbrook", {}).get("cpa", 0) or 0) if gads_list else 0
    gsc_pos = (gsc.get("summary", {}).get("avg_position", 0) or 0) if gsc else 0
    gsc_ctr = (gsc.get("summary", {}).get("avg_ctr", 0) or 0) if gsc else 0

    def assign_tag(role):
        return f'<span style="font-size:0.65rem;background:#f0f9f7;color:#3FA69A;padding:2px 8px;border-radius:10px;font-weight:600;margin-left:6px">→ {role}</span>'

    return f"""<div class="insight-grid">
    <div class="insight-card">
        <span class="tag {'red' if malaga_cpa > 50 else 'amber'}">{'High Priority' if malaga_cpa > 50 else 'Monitor'}</span>{assign_tag('Google Ads Manager')}
        <h3>Google Ads — Malaga CPA at ${malaga_cpa:.2f}</h3>
        <p>{'Malaga CPA elevated — compare with Ellenbrook ($' + f'{ellenbrook_cpa:.2f})' if malaga_cpa > 50 else f'Malaga CPA at ${malaga_cpa:.2f} — monitor vs Ellenbrook (${ellenbrook_cpa:.2f})'}. Review audience targeting and creative.</p>
    </div>
    <div class="insight-card">
        <span class="tag {'amber' if sessions_down else 'green'}">{'Monitor' if sessions_down else 'Opportunity'}</span>{assign_tag('SEO Specialist')}
        <h3>Sessions {sessions_delta_pct} WoW</h3>
        <p>{'Traffic down vs prior week. Investigate paid channel performance and cross-network attribution.' if sessions_down else 'Traffic stable. Organic search continues to perform strongly.'}</p>
    </div>
    <div class="insight-card">
        <span class="tag green">Opportunity</span>{assign_tag('SEO Specialist')}
        <h3>#{gsc_pos:.1f} Position in Organic Search</h3>
        <p>CB247 holds position #{gsc_pos:.1f} for branded queries with {gsc_ctr * 100:.1f}% CTR. Protect with GBP optimisation and fresh content.</p>
    </div>
    <div class="insight-card">
        <span class="tag green">Opportunity</span>{assign_tag('Google Ads Manager')}
        <h3>Direct Traffic Converts at 47%</h3>
        <p>Direct traffic shows highest conversion rate — strong brand recall. Amplify brand awareness to grow this high-intent segment.</p>
    </div>
    <div class="insight-card">
        <span class="tag amber">Monitor</span>{assign_tag('Developer')}
        <h3>Mobile UX Critical</h3>
        <p>Mobile accounts for 82%+ of sessions. Reformer Pilates and Contact pages are top conversion paths — ensure mobile experience is seamless.</p>
    </div>
    <div class="insight-card">
        <span class="tag amber">Monitor</span>{assign_tag('Content Creator')}
        <h3>Sauna + Ice Bath Invisible</h3>
        <p>CB247's unique differentiator not seeing traction in top pages. Consider dedicated landing page and SEO content plan inclusion.</p>
    </div>
    <div class="insight-card">
        <span class="tag green">Opportunity</span>{assign_tag('Front Desk')}
        <h3>GBP Review Velocity — Keep Momentum</h3>
        <p>CB247 Malaga leads competitors 3.5× on reviews. Print QR code review cards and brief front desk — this week's highest-ROI zero-cost action.</p>
    </div>
    <div class="insight-card">
        <span class="tag green">Opportunity</span>{assign_tag('Content Creator')}
        <h3>GBP Weekly Posts — Not Yet Active</h3>
        <p>Weekly GBP posts are a free ranking signal. Schedule Tuesday posts: W1 value, W2 sauna/ice bath, W3 challenge, W4 promo. Use social-trends.json for hooks.</p>
    </div>
</div>"""


def build_seo_intel_section(ahrefs, apify):
    """Ahrefs domain authority + Apify local pack and Maps competitor benchmarking."""

    # ── Ahrefs block ──────────────────────────────────────────────
    ahrefs_html = ""
    if ahrefs:
        dr_data   = (ahrefs.get("domain_rating") or {}).get("domain_rating", {})
        kw_data   = ahrefs.get("organic_keywords") or {}
        bl_data   = ahrefs.get("backlinks") or {}
        rd_data   = ahrefs.get("referring_domains") or {}
        tp_data   = ahrefs.get("top_pages") or {}

        dr        = dr_data.get("domain_rating", "–")
        ar        = dr_data.get("ahrefs_rank")
        kw_count  = len(kw_data.get("keywords") or [])
        bl_count  = len(bl_data.get("backlinks") or [])
        rd_count  = len((rd_data.get("refdomains") or []))
        top_kws   = (kw_data.get("keywords") or [])[:5]

        ar_str = f"#{ar:,}" if ar else "–"

        kw_rows = ""
        for kw in top_kws:
            pos     = kw.get("best_position", "–")
            vol     = kw.get("volume", 0) or 0
            kd      = kw.get("keyword_difficulty", "–")
            traffic = kw.get("sum_traffic", 0) or 0
            kw_rows += (
                f"<tr><td style='font-family:inherit'>{kw.get('keyword','')}</td>"
                f"<td style='text-align:center'>{pos}</td>"
                f"<td style='text-align:center'>{vol:,}</td>"
                f"<td style='text-align:center'>{kd}</td>"
                f"<td style='text-align:center'>{traffic:,}</td></tr>"
            )

        ahrefs_html = f"""
        <div style="margin-bottom:32px">
            <h3 style="font-size:1rem;font-weight:700;letter-spacing:0.04em;text-transform:uppercase;
                       color:var(--text-muted);margin:0 0 16px">Ahrefs — Domain Authority</h3>
            <div class="kpi-grid" style="grid-template-columns:repeat(4,1fr);margin-bottom:24px">
                {kpi_card("Domain Rating", str(dr), None, "Ahrefs DR score", "green")}
                {kpi_card("Ahrefs Rank", ar_str, None, "Global rank", "blue")}
                {kpi_card("Organic Keywords", f"{kw_count}", None, "Ranking keywords (AU)", "green")}
                {kpi_card("Referring Domains", f"{rd_count}", None, "Unique linking domains", "amber")}
            </div>
            {'<table class="data-table"><thead><tr><th>Keyword</th><th>Position</th><th>Volume</th><th>KD</th><th>Est. Traffic</th></tr></thead><tbody>' + kw_rows + '</tbody></table>' if kw_rows else '<p style="color:var(--text-muted);font-size:0.85rem">No keyword data returned.</p>'}
        </div>"""

    # ── Apify block ───────────────────────────────────────────────
    apify_html = ""
    if apify:
        lps     = apify.get("local_pack_summary") or {}
        in_pack = lps.get("appearing_in_pack") or []
        not_in  = lps.get("not_in_pack") or []
        rate    = lps.get("pack_presence_rate")

        maps    = apify.get("competitor_maps") or {}
        targets = maps.get("targets") or []
        summary = maps.get("summary") or {}
        cb247_s = summary.get("cb247") or {}
        comp_s  = summary.get("competitors") or {}

        pack_rows = ""
        for item in in_pack:
            pack_rows += (
                f"<tr><td style='font-family:inherit'>{item.get('keyword','')}</td>"
                f"<td style='text-align:center;color:var(--green);font-weight:700'>#{item.get('position','–')}</td>"
                f"<td style='text-align:center;color:var(--green)'>✓ In pack</td></tr>"
            )
        for kw in not_in:
            pack_rows += (
                f"<tr><td style='font-family:inherit'>{kw}</td>"
                f"<td style='text-align:center;color:var(--text-muted)'>–</td>"
                f"<td style='text-align:center;color:var(--red)'>✗ Not in pack</td></tr>"
            )

        maps_rows = ""
        for r in targets:
            if "rating" not in r:
                continue
            tag      = "CB247" if r.get("type") == "cb247" else "Competitor"
            tag_clr  = "var(--green)" if r.get("type") == "cb247" else "var(--amber)"
            complete = r.get("completeness_score", 0)
            maps_rows += (
                f"<tr>"
                f"<td><span style='font-size:0.7rem;font-weight:700;color:{tag_clr}'>{tag}</span><br>"
                f"<span style='font-family:inherit'>{r.get('title') or r.get('query','')[:40]}</span></td>"
                f"<td style='text-align:center'>{r.get('location','')}</td>"
                f"<td style='text-align:center;font-weight:700'>{r.get('rating') or '–'} ⭐</td>"
                f"<td style='text-align:center'>{r.get('reviews') or 0:,}</td>"
                f"<td style='text-align:center'>{r.get('photos') or 0}</td>"
                f"<td style='text-align:center'>"
                f"<div style='background:#eee;border-radius:4px;height:8px;width:80px;display:inline-block;vertical-align:middle'>"
                f"<div style='background:var(--green);width:{complete}%;height:100%;border-radius:4px'></div></div>"
                f" {complete}%</td>"
                f"</tr>"
            )

        apify_html = f"""
        <div>
            <h3 style="font-size:1rem;font-weight:700;letter-spacing:0.04em;text-transform:uppercase;
                       color:var(--text-muted);margin:0 0 16px">Local Pack Presence
                <span style="font-weight:400;font-size:0.85rem;margin-left:8px">
                    {f'{rate}% presence rate across tracked keywords' if rate is not None else ''}</span>
            </h3>
            {'<table class="data-table"><thead><tr><th>Keyword</th><th>Pack Position</th><th>Status</th></tr></thead><tbody>' + pack_rows + '</tbody></table>' if pack_rows else '<p style="color:var(--text-muted);font-size:0.85rem">No local pack data.</p>'}

            <h3 style="font-size:1rem;font-weight:700;letter-spacing:0.04em;text-transform:uppercase;
                       color:var(--text-muted);margin:32px 0 16px">Google Maps Competitor Benchmarking</h3>
            <div class="kpi-grid" style="grid-template-columns:repeat(4,1fr);margin-bottom:24px">
                {kpi_card("CB247 Avg Rating", str(cb247_s.get('avg_rating') or '–'), None, "vs competitor avg: " + str(comp_s.get('avg_rating') or '–'), "green")}
                {kpi_card("CB247 Reviews", str(cb247_s.get('total_reviews') or '–'), None, "Competitor total: " + str(comp_s.get('total_reviews') or '–'), "blue")}
                {kpi_card("CB247 Completeness", str(cb247_s.get('avg_completeness') or '–') + "%", None, "Competitor avg: " + str(comp_s.get('avg_completeness') or '–') + "%", "amber")}
                {kpi_card("CB247 Photos", str(cb247_s.get('avg_photos') or '–'), None, "Competitor avg: " + str(comp_s.get('avg_photos') or '–'), "green")}
            </div>
            {'<table class="data-table"><thead><tr><th>Listing</th><th>Location</th><th>Rating</th><th>Reviews</th><th>Photos</th><th>Completeness</th></tr></thead><tbody>' + maps_rows + '</tbody></table>' if maps_rows else '<p style="color:var(--text-muted);font-size:0.85rem">No Maps data returned.</p>'}
        </div>"""

    if not ahrefs_html and not apify_html:
        return '<p style="color:var(--text-muted)">Run pull_ahrefs.py and pull_apify.py to populate this section.</p>'

    return ahrefs_html + apify_html


def build_gbp_section(apify):
    """GBP local visibility snapshot — review count, rating, photos vs targets."""
    if not apify:
        return '<p style="color:var(--text-muted)">GBP data not available — run: python3 scripts/pull_apify.py</p>'

    targets = apify.get("competitor_maps", {}).get("targets", [])
    competitors = apify.get("competitor_maps", {}).get("competitors", [])
    malaga = next((t for t in targets if t.get("location") == "Malaga"), {})
    ellenbrook = next((t for t in targets if t.get("location") == "Ellenbrook"), {})

    def progress_bar(current, target, color="#3FA69A"):
        pct_val = min(int((current / target) * 100), 100) if target else 0
        return (f'<div style="background:#e8e8ec;border-radius:4px;height:6px;margin-top:6px">'
                f'<div style="width:{pct_val}%;background:{color};height:6px;border-radius:4px"></div></div>'
                f'<span style="font-size:0.7rem;color:#888">{current} / {target} target</span>')

    def gbp_card(loc, data, review_target, photo_target):
        rating = data.get("rating", "—")
        reviews = data.get("reviews", 0)
        photos = data.get("photos", 0)
        complete = data.get("completeness_score", "—")
        return f"""<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-lg);padding:24px;flex:1">
            <div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:var(--text-muted);margin-bottom:12px">📍 {loc}</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
                <div><div style="font-size:0.7rem;color:var(--text-muted);margin-bottom:2px">Rating</div><div style="font-size:1.8rem;font-weight:700;color:var(--text)">⭐ {rating}</div></div>
                <div><div style="font-size:0.7rem;color:var(--text-muted);margin-bottom:2px">Profile Complete</div><div style="font-size:1.8rem;font-weight:700;color:var(--green)">{complete}%</div></div>
            </div>
            <div style="margin-bottom:12px">
                <div style="font-size:0.7rem;color:var(--text-muted);margin-bottom:4px">Reviews</div>
                {progress_bar(reviews, review_target)}
            </div>
            <div>
                <div style="font-size:0.7rem;color:var(--text-muted);margin-bottom:4px">Photos</div>
                {progress_bar(photos, photo_target, "#a78bfa")}
            </div>
        </div>"""

    comp_rows = ""
    for c in competitors[:6]:
        name = c.get("title", c.get("query", "—"))[:30]
        loc = c.get("location", "—")
        rating = c.get("rating", "—")
        reviews = c.get("reviews", "—")
        photos = c.get("photos", "—")
        comp_rows += f"<tr><td>{name}</td><td>{loc}</td><td>{rating}</td><td>{reviews}</td><td>{photos}</td></tr>"

    return f"""
    <div style="display:flex;gap:20px;margin-bottom:24px">
        {gbp_card("Malaga", malaga, 530, 100)}
        {gbp_card("Ellenbrook", ellenbrook, 280, 100)}
    </div>
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-lg);padding:24px">
        <div style="font-size:0.78rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:var(--text-muted);margin-bottom:16px">Competitor Benchmarking</div>
        <table class="data-table"><thead><tr><th>Listing</th><th>Location</th><th>Rating</th><th>Reviews</th><th>Photos</th></tr></thead>
        <tbody>{comp_rows}</tbody></table>
        <!-- GBP STRATEGY SECTION -->
        <div style="margin-top:24px;padding:28px;background:#f0fdf9;border:1px solid #b2e8e0;border-radius:var(--radius-lg);">
            <div style="font-size:0.78rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:#3FA69A;margin-bottom:20px;">📋 GBP Visibility Strategy — June–August 2026</div>

            <!-- KPI Targets -->
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px;">
                <div style="background:white;border:1px solid #d1f0ea;border-radius:10px;padding:16px;text-align:center;">
                    <div style="font-size:1.6rem;font-weight:700;color:#1a1a1e;">530+</div>
                    <div style="font-size:0.68rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6b78;margin-top:4px;">Malaga Reviews Target</div>
                    <div style="font-size:0.72rem;color:#3FA69A;margin-top:4px;">Currently 469</div>
                </div>
                <div style="background:white;border:1px solid #d1f0ea;border-radius:10px;padding:16px;text-align:center;">
                    <div style="font-size:1.6rem;font-weight:700;color:#1a1a1e;">280+</div>
                    <div style="font-size:0.68rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6b78;margin-top:4px;">Ellenbrook Reviews Target</div>
                    <div style="font-size:0.72rem;color:#3FA69A;margin-top:4px;">Currently 226</div>
                </div>
                <div style="background:white;border:1px solid #d1f0ea;border-radius:10px;padding:16px;text-align:center;">
                    <div style="font-size:1.6rem;font-weight:700;color:#1a1a1e;">100+</div>
                    <div style="font-size:0.68rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6b78;margin-top:4px;">Photos Per Location</div>
                    <div style="font-size:0.72rem;color:#3FA69A;margin-top:4px;">Currently 65 / 68</div>
                </div>
                <div style="background:white;border:1px solid #d1f0ea;border-radius:10px;padding:16px;text-align:center;">
                    <div style="font-size:1.6rem;font-weight:700;color:#1a1a1e;">3.5×</div>
                    <div style="font-size:0.68rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6b78;margin-top:4px;">Review Lead vs Revo</div>
                    <div style="font-size:0.72rem;color:#3FA69A;margin-top:4px;">Revo has 134 reviews</div>
                </div>
            </div>

            <!-- 5 Levers -->
            <div style="font-size:0.85rem;font-weight:700;color:#1a1a1e;margin-bottom:12px;">The 5 Levers</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:24px;">
                <div style="background:white;border:1px solid #d1f0ea;border-radius:10px;padding:16px;">
                    <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#3FA69A;margin-bottom:8px;">🏆 Lever 1 — Review Velocity (Highest Impact)</div>
                    <ul style="list-style:none;font-size:0.8rem;color:#4a4a5a;display:flex;flex-direction:column;gap:6px;">
                        <li style="padding-left:14px;position:relative;"><span style="position:absolute;left:0;color:#3FA69A;">→</span> QR code cards at reception desk (print A5)</li>
                        <li style="padding-left:14px;position:relative;"><span style="position:absolute;left:0;color:#3FA69A;">→</span> Staff verbal ask script at check-out</li>
                        <li style="padding-left:14px;position:relative;"><span style="position:absolute;left:0;color:#3FA69A;">→</span> WhatsApp follow-up 24hrs after first visit</li>
                        <li style="padding-left:14px;position:relative;"><span style="position:absolute;left:0;color:#3FA69A;">→</span> Monthly email newsletter footer CTA</li>
                        <li style="padding-left:14px;position:relative;"><span style="position:absolute;left:0;color:#3FA69A;">→</span> Respond to every review within 24 hours</li>
                    </ul>
                </div>
                <div style="background:white;border:1px solid #d1f0ea;border-radius:10px;padding:16px;">
                    <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#3FA69A;margin-bottom:8px;">📅 Lever 2 — Weekly GBP Posts (Every Tuesday)</div>
                    <table style="font-size:0.76rem;width:100%;border-collapse:collapse;">
                        <thead><tr><th style="text-align:left;color:#6b6b78;padding:4px 8px 4px 0;border-bottom:1px solid #e8e8ec;">Week</th><th style="text-align:left;color:#6b6b78;padding:4px 0;border-bottom:1px solid #e8e8ec;">Topic</th></tr></thead>
                        <tbody>
                            <tr><td style="padding:5px 8px 5px 0;color:#3FA69A;font-weight:600;">W1</td><td style="padding:5px 0;">$11.95/wk value vs competitors</td></tr>
                            <tr><td style="padding:5px 8px 5px 0;color:#3FA69A;font-weight:600;">W2</td><td style="padding:5px 0;">Feature spotlight — sauna, ice bath, Kids Hub</td></tr>
                            <tr><td style="padding:5px 8px 5px 0;color:#3FA69A;font-weight:600;">W3</td><td style="padding:5px 0;">Member challenge or community event</td></tr>
                            <tr><td style="padding:5px 8px 5px 0;color:#3FA69A;font-weight:600;">W4</td><td style="padding:5px 0;">Referral deal or new member promo</td></tr>
                        </tbody>
                    </table>
                </div>
                <div style="background:white;border:1px solid #d1f0ea;border-radius:10px;padding:16px;">
                    <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#3FA69A;margin-bottom:8px;">📸 Lever 3 — Photo Strategy (10/month per location)</div>
                    <ul style="list-style:none;font-size:0.8rem;color:#4a4a5a;display:flex;flex-direction:column;gap:6px;">
                        <li style="padding-left:14px;position:relative;"><span style="position:absolute;left:0;color:#3FA69A;">→</span> Ice bath + sauna in use (unique differentiator)</li>
                        <li style="padding-left:14px;position:relative;"><span style="position:absolute;left:0;color:#3FA69A;">→</span> Kids Hub — children + smiling staff</li>
                        <li style="padding-left:14px;position:relative;"><span style="position:absolute;left:0;color:#3FA69A;">→</span> Wide gym floor shots (counters gymtimidation)</li>
                        <li style="padding-left:14px;position:relative;"><span style="position:absolute;left:0;color:#3FA69A;">→</span> Real members mid-workout (with consent)</li>
                        <li style="padding-left:14px;position:relative;"><span style="position:absolute;left:0;color:#3FA69A;">→</span> Rename files before upload: cb247-malaga-sauna.jpg</li>
                    </ul>
                </div>
                <div style="background:white;border:1px solid #d1f0ea;border-radius:10px;padding:16px;">
                    <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#3FA69A;margin-bottom:8px;">✏️ Lever 4 — Profile Content Optimisation</div>
                    <ul style="list-style:none;font-size:0.8rem;color:#4a4a5a;display:flex;flex-direction:column;gap:6px;">
                        <li style="padding-left:14px;position:relative;"><span style="position:absolute;left:0;color:#3FA69A;">→</span> Rewrite business description with local keywords</li>
                        <li style="padding-left:14px;position:relative;"><span style="position:absolute;left:0;color:#3FA69A;">→</span> Add all services individually (Sauna, Ice Bath, Pilates, Kids Hub, FIFO Freeze…)</li>
                        <li style="padding-left:14px;position:relative;"><span style="position:absolute;left:0;color:#3FA69A;">→</span> Seed Q&amp;A with 6 pre-answered questions</li>
                        <li style="padding-left:14px;position:relative;"><span style="position:absolute;left:0;color:#3FA69A;">→</span> Link "Book" button to sign-up page (not homepage)</li>
                    </ul>
                </div>
            </div>

            <!-- Month 1 Actions -->
            <div style="font-size:0.85rem;font-weight:700;color:#1a1a1e;margin-bottom:12px;">Month 1 Actions — June (In Progress)</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:20px;">
                <div style="font-size:0.8rem;color:#4a4a5a;padding:8px 12px;background:white;border-radius:8px;border:1px solid #e8e8ec;">☐ Create + print QR code review cards (both locations)</div>
                <div style="font-size:0.8rem;color:#4a4a5a;padding:8px 12px;background:white;border-radius:8px;border:1px solid #e8e8ec;">☐ Brief front desk on verbal review ask script</div>
                <div style="font-size:0.8rem;color:#4a4a5a;padding:8px 12px;background:white;border-radius:8px;border:1px solid #e8e8ec;">☐ Set up WhatsApp template for new member follow-up</div>
                <div style="font-size:0.8rem;color:#4a4a5a;padding:8px 12px;background:white;border-radius:8px;border:1px solid #e8e8ec;">☐ Rewrite GBP descriptions (keyword-optimised copy ready)</div>
                <div style="font-size:0.8rem;color:#4a4a5a;padding:8px 12px;background:white;border-radius:8px;border:1px solid #e8e8ec;">☐ Seed Q&amp;A section — 6 questions (incl. cancellation)</div>
                <div style="font-size:0.8rem;color:#4a4a5a;padding:8px 12px;background:white;border-radius:8px;border:1px solid #e8e8ec;">☐ Audit + complete all Services/Products listings</div>
                <div style="font-size:0.8rem;color:#4a4a5a;padding:8px 12px;background:white;border-radius:8px;border:1px solid #e8e8ec;">☐ Begin weekly Tuesday GBP posts</div>
                <div style="font-size:0.8rem;color:#4a4a5a;padding:8px 12px;background:white;border-radius:8px;border:1px solid #e8e8ec;">☐ Upload 10 priority photos per location (sauna, Kids Hub, ice bath)</div>
            </div>

            <!-- Highest ROI call-out -->
            <div style="padding:14px 18px;background:#3FA69A;border-radius:8px;color:white;font-size:0.82rem;font-weight:500;">
                🏆 <strong>Highest-ROI action this week:</strong> Print the QR code review card and brief the front desk team. Every member who walks in is a potential 5-star review that costs $0. CB247 leads Revo 3.5× on reviews — extend that lead now.
            </div>
        </div>
    </div>"""


# ─── HTML Template (05-11 design) ─────────────────────────────────────────────

def build_html(date_str, ga4, gsc, gads_list, meta_list, ahrefs=None, apify=None):
    today = datetime.now()
    generated = today.strftime("%d %B %Y")

    dr = (gsc.get("date_range") or {}) if gsc else {}
    gsc_start = dr.get("start", "?")
    gsc_end = dr.get("end", "?")
    ga4_dr = (ga4.get("date_range") or {}) if ga4 else {}
    ga4_start = ga4_dr.get("start", "?")
    ga4_end = ga4_dr.get("end", "?")
    # Format dates as "11–17 May 2026"
    def fmt_date_short(d):
        if d == "?":
            return "?"
        dt = datetime.strptime(d, "%Y-%m-%d")
        return dt.strftime("%-d").lstrip()
    def fmt_month_year(d):
        if d == "?":
            return "?"
        dt = datetime.strptime(d, "%Y-%m-%d")
        return dt.strftime("%B %Y").title()
    start_day = fmt_date_short(ga4_start)
    end_day = fmt_date_short(ga4_end)
    month_year = fmt_month_year(ga4_end)
    report_period = f"{start_day}–{end_day} {month_year}"

    iso = today.isocalendar()
    week_label_str = f"Week {iso[1]} · {today.year}"

    ga4_c = (ga4.get("current") or {}) if ga4 else {}
    ga4_p = (ga4.get("previous") or {}) if ga4 else {}
    sessions = int(ga4_c.get("sessions", 0) or 0)
    p_sessions = int(ga4_p.get("sessions", 0) or 0)
    convs = int(ga4_c.get("conversions", 0) or 0)
    p_convs = int(ga4_p.get("conversions", 0) or 0)
    conv_rate = convs / sessions * 100 if sessions else 0
    p_conv_rate = p_convs / p_sessions * 100 if p_sessions else 0
    conv_rate_delta = conv_rate - p_conv_rate

    exec_kpis = (
        kpi_card("Total Sessions", f"{sessions:,}", f"↓ {pct(sessions, p_sessions)[1:]} vs prior week",
                 f"Prior week: {p_sessions:,} sessions", "green") +
        kpi_card("Conversions", f"{convs}", f"↓ {pct(convs, p_convs)[1:]} vs prior week",
                 f"Prior week: {p_convs} conversions", "green") +
        kpi_card("Conv. Rate", f"{conv_rate:.1f}%",
                 f"{'↑' if conv_rate_delta >= 0 else '↓'} {abs(conv_rate_delta):.1f}pp {'improvement' if conv_rate_delta >= 0 else 'decline'}",
                 f"Prior week: {p_conv_rate:.1f}%", "amber")
    )

    ga4_kpis, channel_rows, page_rows = build_ga4_section(ga4)
    gsc_kpis, gsc_q_rows = build_gsc_section(gsc)
    gads_kpis, gads_location_cards, gads_trend_rows, _ = build_google_ads_section(gads_list)
    meta_kpis, meta_cards, meta_trend_rows, _ = build_meta_ads_section(meta_list)
    gads_campaign_html = build_google_ads_campaigns(gads_list)
    meta_campaign_html = build_meta_ads_campaigns(meta_list)
    exec_summary = build_exec_summary(ga4, gads_list)
    insights = build_insights(ga4, gads_list, gsc)
    gbp_section = build_gbp_section(apify)
    seo_intel = build_seo_intel_section(ahrefs, apify)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CB247 — Weekly Marketing Report · {report_period}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=JetBrains+Mono:wght@400;500&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        /* ─── TOKENS ─────────────────────────────────────────────── */
        :root {{
            --bg:          #f7f6f3;
            --bg-card:     #ffffff;
            --bg-dark:     #0c0c0e;
            --bg-section:  #111114;
            --bg-panel:    #18181d;
            --green:       #00c4b4;
            --green-dim:   #00c47c22;
            --green-glow:  #00c47c55;
            --red:         #ff4d4d;
            --red-dim:     #ff4d4d18;
            --amber:       #ffb547;
            --amber-dim:   #ffb54718;
            --text:        #1a1a1e;
            --text-muted:  #6b6b78;
            --text-light:  #9898a8;
            --border:      #e8e8ec;
            --border-dark: #2a2a32;
            --radius:      10px;
            --radius-lg:   16px;
            --shadow:      0 2px 12px rgba(0,0,0,0.06);
            --shadow-lg:   0 8px 32px rgba(0,0,0,0.12);
        }}

        /* ─── RESET ─────────────────────────────────────────────── */
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
        html {{ font-size: 16px; scroll-behavior: smooth; }}
        body {{
            font-family: 'Inter', -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
        }}

        /* ─── SCROLLBAR ───────────────────────────────────────────── */
        ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
        ::-webkit-scrollbar-track {{ background: transparent; }}
        ::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 99px; }}

        /* ─── SCROLL OFFSET ──────────────────────────────────────── */
        html {{ scroll-padding-top: 37px; }}
        .section[id] {{ scroll-margin-top: 37px; }}

        /* ─── COVER PAGE ─────────────────────────────────────────── */
        .cover {{
            background: var(--bg-dark);
            background-image:
                radial-gradient(ellipse 80% 60% at 70% 40%, #00c47c14 0%, transparent 70%),
                radial-gradient(ellipse 40% 40% at 20% 80%, #00c47c0a 0%, transparent 60%);
            color: white;
            padding: 72px 80px 64px;
            position: relative;
            overflow: hidden;
        }}
        .cover::before {{
            content: '';
            position: absolute;
            bottom: 0; left: 0; right: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, var(--green), transparent);
            opacity: 0.4;
        }}
        .cover-badge {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: var(--green-dim);
            border: 1px solid var(--green-glow);
            color: var(--green);
            font-size: 0.72rem;
            font-weight: 600;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            padding: 6px 14px;
            border-radius: 99px;
            margin-bottom: 32px;
        }}
        .cover h1 {{
            font-family: 'DM Serif Display', serif;
            font-size: clamp(2.4rem, 5vw, 4rem);
            font-weight: 400;
            line-height: 1.1;
            letter-spacing: -0.02em;
            margin-bottom: 16px;
        }}
        .cover h1 em {{ font-style: italic; color: var(--green); }}
        .cover p {{
            color: var(--text-light);
            font-size: 1rem;
            max-width: 520px;
            line-height: 1.7;
        }}
        .cover-meta {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 24px;
            margin-top: 48px;
            padding-top: 40px;
            border-top: 1px solid var(--border-dark);
            max-width: 640px;
        }}
        .cover-meta-item label {{
            display: block;
            font-size: 0.68rem;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--text-light);
            margin-bottom: 6px;
        }}
        .cover-meta-item span {{
            font-size: 0.92rem;
            font-weight: 500;
            color: #e0e0e8;
        }}
        .cover-tagline {{
            position: absolute;
            right: 80px;
            bottom: 48px;
            font-family: 'DM Serif Display', serif;
            font-size: 1.1rem;
            font-style: italic;
            color: var(--green);
            opacity: 0.5;
        }}

        /* ─── STICKY SECTION NAV ─────────────────────────────────── */
        .section-nav {{
            position: sticky;
            top: 0;
            z-index: 100;
            background: var(--bg-dark);
            border-bottom: 1px solid var(--border-dark);
            padding: 0 80px;
            display: flex;
            align-items: center;
            gap: 0;
            overflow-x: auto;
        }}
        .section-nav::-webkit-scrollbar {{ display: none; }}
        .section-nav a {{
            flex-shrink: 0;
            display: flex;
            align-items: center;
            gap: 7px;
            padding: 16px 20px;
            font-size: 0.78rem;
            font-weight: 500;
            letter-spacing: 0.04em;
            color: var(--text-light);
            text-decoration: none;
            border-bottom: 2px solid transparent;
            transition: color 0.2s, border-color 0.2s;
        }}
        .section-nav a:hover,
        .section-nav a.active {{ color: var(--green); border-bottom-color: var(--green); }}
        .section-nav .divider {{
            width: 1px;
            height: 20px;
            background: var(--border-dark);
            flex-shrink: 0;
            margin: 0 4px;
        }}

        /* ─── MAIN LAYOUT ─────────────────────────────────────────── */
        .container {{ max-width: 1200px; margin: 0 auto; padding: 56px 80px 80px; }}

        /* ─── SECTION HEADER ──────────────────────────────────────── */
        .section {{ margin-bottom: 72px; }}
        .section-header {{
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            margin-bottom: 32px;
            gap: 16px;
        }}
        .section-label {{
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            color: var(--green);
            margin-bottom: 10px;
        }}
        .section-label::before {{
            content: '';
            display: block;
            width: 24px;
            height: 2px;
            background: var(--green);
            border-radius: 2px;
        }}
        .section-title {{
            font-family: 'DM Serif Display', serif;
            font-size: clamp(1.5rem, 3vw, 2.2rem);
            font-weight: 400;
            line-height: 1.15;
            letter-spacing: -0.01em;
        }}
        .section-desc {{
            font-size: 0.88rem;
            color: var(--text-muted);
            max-width: 480px;
            margin-top: 8px;
            line-height: 1.7;
        }}
        .section-badge {{
            flex-shrink: 0;
            background: var(--green-dim);
            border: 1px solid var(--green-glow);
            color: var(--green);
            font-size: 0.72rem;
            font-weight: 600;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            padding: 6px 14px;
            border-radius: 99px;
            white-space: nowrap;
        }}

        /* ─── KPI GRID ────────────────────────────────────────────── */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }}
        .kpi-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 24px 22px;
            position: relative;
            overflow: hidden;
            box-shadow: var(--shadow);
            transition: box-shadow 0.2s, transform 0.2s;
        }}
        .kpi-card:hover {{ box-shadow: var(--shadow-lg); transform: translateY(-2px); }}
        .kpi-card::before {{
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 3px;
            border-radius: var(--radius-lg) var(--radius-lg) 0 0;
        }}
        .kpi-card.green::before  {{ background: var(--green); }}
        .kpi-card.red::before    {{ background: var(--red); }}
        .kpi-card.amber::before {{ background: var(--amber); }}
        .kpi-card.blue::before  {{ background: #4d9aff; }}
        .kpi-label {{
            font-size: 0.72rem;
            font-weight: 600;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--text-muted);
            margin-bottom: 12px;
        }}
        .kpi-value {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 2rem;
            font-weight: 500;
            letter-spacing: -0.03em;
            line-height: 1;
            margin-bottom: 8px;
        }}
        .kpi-change {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            font-size: 0.78rem;
            font-weight: 600;
            padding: 3px 8px;
            border-radius: 99px;
        }}
        .kpi-change.up   {{ background: var(--green-dim); color: var(--green); }}
        .kpi-change.down {{ background: var(--red-dim);   color: var(--red);   }}
        .kpi-change.neutral {{ background: #f0f0f5; color: var(--text-muted); }}
        .kpi-sub {{ font-size: 0.75rem; color: var(--text-light); margin-top: 6px; }}

        /* ─── DATA TABLE ──────────────────────────────────────────── */
        .table-wrap {{ overflow-x: auto; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.84rem;
        }}
        thead th {{
            text-align: left;
            font-size: 0.68rem;
            font-weight: 700;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--text-muted);
            padding: 10px 16px;
            border-bottom: 2px solid var(--border);
            white-space: nowrap;
        }}
        tbody tr {{ border-bottom: 1px solid var(--border); transition: background 0.15s; }}
        tbody tr:hover {{ background: #fafaf8; }}
        tbody td {{ padding: 13px 16px; vertical-align: middle; }}
        tbody td:first-child {{ font-weight: 500; }}
        tbody td:not(:first-child) {{ font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; }}
        .tbl-positive {{ color: var(--green); font-weight: 500; }}
        .tbl-negative {{ color: var(--red);   font-weight: 500; }}
        .tbl-neutral  {{ color: var(--text-muted); }}
        .rank-badge {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 22px;
            height: 22px;
            border-radius: 6px;
            font-size: 0.7rem;
            font-weight: 700;
            background: var(--bg);
            color: var(--text-muted);
            margin-right: 10px;
        }}
        .rank-badge.top3 {{ background: var(--green-dim); color: var(--green); }}

        /* ─── CHANNEL BARS ───────────────────────────────────────── */
        .channel-row {{
            display: grid;
            grid-template-columns: 160px 1fr 80px 80px;
            align-items: center;
            gap: 16px;
            padding: 12px 0;
            border-bottom: 1px solid var(--border);
        }}
        .channel-row:last-child {{ border-bottom: none; }}
        .channel-name {{ font-size: 0.84rem; font-weight: 500; display: flex; align-items: center; gap: 10px; }}
        .channel-dot {{ width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }}
        .bar-track {{ height: 6px; background: var(--bg); border-radius: 99px; overflow: hidden; }}
        .bar-fill {{ height: 100%; border-radius: 99px; background: var(--green); transition: width 1s cubic-bezier(0.23, 1, 0.32, 1); }}
        .bar-fill.amber {{ background: var(--amber); }}
        .bar-fill.red   {{ background: var(--red); }}
        .bar-fill.blue  {{ background: #4d9aff; }}
        .bar-fill.purple{{ background: #a78bfa; }}
        .bar-fill.orange{{ background: #fb923c; }}
        .channel-stat {{ font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; text-align: right; }}

        /* ─── ADS COMPARISON CARDS ───────────────────────────────── */
        .ads-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
        .ads-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            overflow: hidden;
            box-shadow: var(--shadow);
        }}
        .ads-card-header {{
            padding: 18px 22px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid var(--border);
        }}
        .ads-card-title {{ font-size: 0.85rem; font-weight: 700; letter-spacing: 0.04em; }}
        .ads-card-body {{ padding: 20px 22px; }}
        .ads-metrics {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 20px; }}
        .ads-metric {{ text-align: center; }}
        .ads-metric-val {{ font-family: 'JetBrains Mono', monospace; font-size: 1.4rem; font-weight: 500; line-height: 1; margin-bottom: 5px; }}
        .ads-metric-lbl {{ font-size: 0.68rem; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-muted); }}

        /* ─── INSIGHT CARDS ──────────────────────────────────────── */
        .insight-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }}
        .insight-card {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px; box-shadow: var(--shadow); }}
        .insight-card .tag {{ display: inline-block; font-size: 0.62rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; padding: 3px 8px; border-radius: 99px; margin-bottom: 10px; }}
        .insight-card .tag.green {{ background: var(--green-dim); color: var(--green); }}
        .insight-card .tag.red   {{ background: var(--red-dim);   color: var(--red);   }}
        .insight-card .tag.amber {{ background: var(--amber-dim); color: var(--amber); }}
        .insight-card h3 {{ font-size: 0.88rem; font-weight: 600; margin-bottom: 6px; }}
        .insight-card p  {{ font-size: 0.8rem;  color: var(--text-muted); line-height: 1.6; }}

        /* ─── EXECUTIVE SUMMARY ─────────────────────────────────── */
        .exec-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-top: 32px; }}
        .exec-card {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 28px 24px; box-shadow: var(--shadow); }}
        .exec-card-icon {{ font-size: 1.6rem; margin-bottom: 16px; }}
        .exec-card h3 {{ font-size: 0.95rem; font-weight: 700; margin-bottom: 12px; }}
        .exec-card ul {{ list-style: none; display: flex; flex-direction: column; gap: 8px; }}
        .exec-card li {{ font-size: 0.82rem; color: var(--text-muted); padding-left: 16px; position: relative; line-height: 1.5; }}
        .exec-card li::before {{ content: '→'; position: absolute; left: 0; color: var(--green); font-weight: 700; }}

        /* ─── DIVIDER ────────────────────────────────────────────── */
        .divider {{ height: 1px; background: linear-gradient(90deg, transparent, var(--border), transparent); margin: 56px 0; }}

        /* ─── FOOTER ──────────────────────────────────────────────── */
        .footer {{ background: var(--bg-dark); padding: 32px 80px; display: flex; align-items: center; justify-content: space-between; gap: 16px; }}
        .footer-brand {{ font-family: 'DM Serif Display', serif; font-size: 1rem; color: white; opacity: 0.6; }}
        .footer-brand em {{ color: var(--green); font-style: italic; opacity: 1; }}
        .footer-info {{ font-size: 0.72rem; color: var(--text-light); text-align: right; }}

        /* ─── RESPONSIVE ──────────────────────────────────────────── */
        @media (max-width: 900px) {{
            .cover {{ padding: 48px 28px 40px; }}
            .cover-tagline {{ display: none; }}
            .section-nav {{ padding: 0 20px; }}
            .container {{ padding: 40px 20px 60px; }}
            .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .ads-grid {{ grid-template-columns: 1fr; }}
            .exec-grid {{ grid-template-columns: 1fr; }}
            .insight-grid {{ grid-template-columns: 1fr; }}
            .cover-meta {{ grid-template-columns: repeat(2, 1fr); }}
            .footer {{ padding: 24px 20px; flex-direction: column; text-align: center; }}
            .footer-info {{ text-align: center; }}
        }}
        @media (max-width: 480px) {{ .kpi-grid {{ grid-template-columns: 1fr 1fr; }} }}

        /* ─── ANIMATIONS ──────────────────────────────────────────── */
        @keyframes fadeUp {{ from {{ opacity: 0; transform: translateY(18px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        @keyframes barIn  {{ from {{ width: 0 !important; }} }}
        .section        {{ animation: fadeUp 0.55s cubic-bezier(0.23, 1, 0.32, 1) 0.1s both; }}
        .kpi-card:nth-child(1) {{ animation: fadeUp 0.5s ease 0.1s both; }}
        .kpi-card:nth-child(2) {{ animation: fadeUp 0.5s ease 0.18s both; }}
        .kpi-card:nth-child(3) {{ animation: fadeUp 0.5s ease 0.26s both; }}
        .kpi-card:nth-child(4) {{ animation: fadeUp 0.5s ease 0.34s both; }}
        .kpi-card:nth-child(5) {{ animation: fadeUp 0.5s ease 0.42s both; }}
        .kpi-card:nth-child(6) {{ animation: fadeUp 0.5s ease 0.50s both; }}
        .kpi-card:nth-child(7) {{ animation: fadeUp 0.5s ease 0.58s both; }}
        .kpi-card:nth-child(8) {{ animation: fadeUp 0.5s ease 0.66s both; }}
        .bar-fill {{ animation: barIn 1.2s cubic-bezier(0.23, 1, 0.32, 1) 0.8s both; }}

        /* Print */
        @media print {{
            .section-nav, .footer {{ display: none; }}
            .cover {{ background: #111 !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
            .kpi-card, .ads-card, .exec-card, .insight-card {{ box-shadow: none; border: 1px solid #ddd; }}
        }}
    </style>
</head>
<body>

<!-- ══════════════════════════════════════════════════════════════ -->
<!--  COVER                                                     -->
<!-- ══════════════════════════════════════════════════════════════ -->
<div class="cover">
    <div class="cover-badge">
        <svg width="8" height="8" viewBox="0 0 8 8"><circle cx="4" cy="4" r="4" fill="currentColor"/></svg>
        Marketing Performance Report
    </div>
    <h1>CB247 Weekly<br><em>Marketing Report</em></h1>
    <p style="color: var(--text-light); font-size: 1rem; max-width: 520px; line-height: 1.7;">
        Comprehensive performance analysis across organic search, paid search,
        and social channels for ChasingBetter247 · Malaga &amp; Ellenbrook
    </p>

    <div class="cover-meta">
        <div class="cover-meta-item">
            <label>Report Period</label>
            <span>{report_period}</span>
        </div>
        <div class="cover-meta-item">
            <label>Published</label>
            <span>{generated}</span>
        </div>
        <div class="cover-meta-item">
            <label>Locations</label>
            <span>Malaga &amp; Ellenbrook</span>
        </div>
        <div class="cover-meta-item">
            <label>Membership</label>
            <span>8,000+ Members</span>
        </div>
    </div>
</div>

<!-- ══════════════════════════════════════════════════════════════ -->
<!--  SECTION NAV                                               -->
<!-- ══════════════════════════════════════════════════════════════ -->
<nav class="section-nav">
    <a href="#executive">Executive Summary</a>
    <div class="divider"></div>
    <a href="#ga4">Google Analytics</a>
    <div class="divider"></div>
    <a href="#gsc">Search Console</a>
    <div class="divider"></div>
    <a href="#google-ads">Google Ads</a>
    <div class="divider"></div>
    <a href="#meta-ads">Meta Ads</a>
    <div class="divider"></div>
    <a href="#gbp">GBP Local</a>
    <div class="divider"></div>
    <a href="#seo-intel">SEO Intel</a>
    <div class="divider"></div>
    <a href="#insights">Key Insights</a>
</nav>

<div class="container">

    <!-- ══════════════════════════════════════════════════════════ -->
    <!--  EXECUTIVE SUMMARY                                       -->
    <!-- ══════════════════════════════════════════════════════════ -->
    <div class="section" id="executive">
        <div class="section-header">
            <div>
                <div class="section-label">Executive Summary</div>
                <h2 class="section-title">Week in Review</h2>
                <p class="section-desc">High-level performance snapshot and strategic implications for the reporting period {report_period}.</p>
            </div>
            <div class="section-badge">{week_label_str}</div>
        </div>
        <div class="kpi-grid" style="grid-template-columns: repeat(3, 1fr);">{exec_kpis}</div>
        {exec_summary}
    </div>

    <div class="divider"></div>

    <!-- ══════════════════════════════════════════════════════════ -->
    <!--  GOOGLE ANALYTICS 4                                      -->
    <!-- ══════════════════════════════════════════════════════════ -->
    <div class="section" id="ga4">
        <div class="section-header">
            <div>
                <div class="section-label">Google Analytics 4</div>
                <h2 class="section-title">Web Performance</h2>
                <p class="section-desc">Session, user, and conversion data from GA4 for the period {ga4_start} to {ga4_end} vs prior week.</p>
            </div>
            <div class="section-badge">Live Data · {generated}</div>
        </div>
        <div class="kpi-grid">{ga4_kpis}</div>

        <div style="background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 28px; box-shadow: var(--shadow); margin-bottom: 24px;">
            <div style="font-size: 0.78rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-muted); margin-bottom: 20px;">Traffic by Channel</div>
            <div style="margin-bottom: 16px;">
                <div class="channel-row head" style="padding-bottom:8px; margin-bottom:4px; border-bottom: 2px solid var(--border);">
                    <span>Channel</span>
                    <span style="padding-left:16px;">Share</span>
                    <span style="text-align:right;">Sessions</span>
                    <span></span>
                </div>
                {channel_rows}
            </div>
        </div>

        <div style="background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 28px; box-shadow: var(--shadow);">
            <div style="font-size: 0.78rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-muted); margin-bottom: 20px;">Top 10 Pages by Sessions</div>
            <div class="table-wrap"><table>
                <thead><tr><th>#</th><th>Page</th><th>Views</th><th>Sessions</th></tr></thead>
                <tbody>{page_rows}</tbody>
            </table></div>
        </div>
    </div>

    <div class="divider"></div>

    <!-- ══════════════════════════════════════════════════════════ -->
    <!--  GOOGLE SEARCH CONSOLE                                  -->
    <!-- ══════════════════════════════════════════════════════════ -->
    <div class="section" id="gsc">
        <div class="section-header">
            <div>
                <div class="section-label">Google Search Console</div>
                <h2 class="section-title">Organic Search Visibility</h2>
                <p class="section-desc">Keyword rankings, impressions, and click-through performance for the period {gsc_start} to {gsc_end}.</p>
            </div>
            <div class="section-badge">4-Week Window</div>
        </div>
        <div class="kpi-grid">{gsc_kpis}</div>
        <div style="background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 28px; box-shadow: var(--shadow);">
            <div style="font-size: 0.78rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-muted); margin-bottom: 20px;">Top Organic Queries</div>
            <div class="table-wrap"><table>
                <thead><tr><th>#</th><th>Query</th><th>Clicks</th><th>Impressions</th><th>CTR</th><th>Avg. Position</th></tr></thead>
                <tbody>{gsc_q_rows}</tbody>
            </table></div>
        </div>
    </div>

    <div class="divider"></div>

    <!-- ══════════════════════════════════════════════════════════ -->
    <!--  GOOGLE ADS                                             -->
    <!-- ══════════════════════════════════════════════════════════ -->
    <div class="section" id="google-ads">
        <div class="section-header">
            <div>
                <div class="section-label">Google Ads</div>
                <h2 class="section-title">Paid Search Performance</h2>
                <p class="section-desc">Google Ads metrics by location (Malaga &amp; Ellenbrook) across the past 3 weeks.</p>
            </div>
            <div class="section-badge">Malaga · Ellenbrook</div>
        </div>

        <div class="kpi-grid" style="grid-template-columns: repeat(4, 1fr);">{gads_kpis}</div>

        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px; margin-bottom:24px;">
            {gads_location_cards}
        </div>

        <div style="background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 28px; box-shadow: var(--shadow);">
            <div style="font-size: 0.78rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-muted); margin-bottom: 20px;">3-Week Combined Trend</div>
            <div class="table-wrap"><table>
                <thead><tr><th>Week</th><th style="text-align:right;">Spend</th><th style="text-align:right;">Clicks</th><th style="text-align:right;">Impr.</th><th style="text-align:right;">CTR</th><th style="text-align:right;">CPC</th><th style="text-align:right;">Conv.</th><th style="text-align:right;">CPA</th></tr></thead>
                <tbody>{gads_trend_rows}</tbody>
            </table></div>
        </div>

        {gads_campaign_html}
    </div>

    <div class="divider"></div>

    <!-- ══════════════════════════════════════════════════════════ -->
    <!--  META ADS                                               -->
    <!-- ══════════════════════════════════════════════════════════ -->
    <div class="section" id="meta-ads">
        <div class="section-header">
            <div>
                <div class="section-label">Meta Ads</div>
                <h2 class="section-title">Paid Social Performance</h2>
                <p class="section-desc">Facebook &amp; Instagram ad performance by location for the current and prior reporting periods.</p>
            </div>
            <div class="section-badge">Meta · FB + IG</div>
        </div>

        <div class="kpi-grid" style="grid-template-columns: repeat(4, 1fr);">{meta_kpis}</div>

        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px; margin-bottom:24px;">
            {meta_cards}
        </div>

        <div style="background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 28px; box-shadow: var(--shadow);">
            <div style="font-size: 0.78rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-muted); margin-bottom: 20px;">Meta Combined — 2-Week Trend</div>
            <div class="table-wrap"><table>
                <thead><tr><th>Period</th><th style="text-align:right;">Spend</th><th style="text-align:right;">Impressions</th><th style="text-align:right;">Reach</th><th style="text-align:right;">Clicks</th><th style="text-align:right;">CTR</th><th style="text-align:right;">CPM</th><th style="text-align:right;">CPC</th></tr></thead>
                <tbody>{meta_trend_rows}</tbody>
            </table></div>
        </div>

        {meta_campaign_html}
    </div>

    <div class="divider"></div>

    <div class="divider"></div>

    <!-- ══════════════════════════════════════════════════════════ -->
    <!--  GBP LOCAL VISIBILITY                                    -->
    <!-- ══════════════════════════════════════════════════════════ -->
    <div class="section" id="gbp">
        <div class="section-header">
            <div>
                <div class="section-label">Google Business Profile</div>
                <h2 class="section-title">Local Visibility — Malaga &amp; Ellenbrook</h2>
                <p class="section-desc">Review count, rating, and photo progress vs targets. Competitor benchmarking from Apify Maps data.</p>
            </div>
            <div class="section-badge">Local Pack · Maps</div>
        </div>
        {gbp_section}
    </div>

    <div class="divider"></div>

    <!-- ══════════════════════════════════════════════════════════ -->
    <!--  KEY INSIGHTS                                           -->
    <!-- ══════════════════════════════════════════════════════════ -->
    <div class="section" id="insights">
        <div class="section-header">
            <div>
                <div class="section-label">Strategic Insights</div>
                <h2 class="section-title">What the Data Tells Us</h2>
                <p class="section-desc">Prioritised observations and recommended actions based on this week's data across all channels.</p>
            </div>
        </div>
        {insights}
    </div>

    <!-- ══════════════════════════════════════════════════════════ -->
    <!--  SEO INTELLIGENCE                                         -->
    <!-- ══════════════════════════════════════════════════════════ -->
    <div class="section" id="seo-intel">
        <div class="section-header">
            <div>
                <div class="section-label">SEO Intelligence</div>
                <h2 class="section-title">Authority, Rankings & Competitor Maps</h2>
                <p class="section-desc">Domain authority from Ahrefs, organic keyword rankings, local pack presence, and Google Maps competitor benchmarking via Apify.</p>
            </div>
        </div>
        {seo_intel}
    </div>

</div><!-- /container -->

<!-- ══════════════════════════════════════════════════════════════ -->
<!--  FOOTER                                                   -->
<!-- ══════════════════════════════════════════════════════════════ -->
<div class="footer">
    <div class="footer-brand">ChasingBetter247 <em>Marketing Intelligence</em></div>
    <div class="footer-info">
        Report generated {generated} · Data sources: GA4, GSC, Google Ads, Meta Ads, Ahrefs, Apify<br>
        For questions contact: tia@chasingbetter.com.au
    </div>
</div>

<script>
    const navLinks = document.querySelectorAll('.section-nav a');
    const sections = document.querySelectorAll('.section[id]');
    window.addEventListener('scroll', () => {{
        let current = '';
        sections.forEach(section => {{
            if (window.scrollY >= section.offsetTop - 100) current = section.getAttribute('id');
        }});
        navLinks.forEach(a => {{
            a.classList.remove('active');
            if (a.getAttribute('href') === '#' + current) a.classList.add('active');
        }});
    }});
    const observer = new IntersectionObserver((entries) => {{
        entries.forEach(entry => {{
            if (entry.isIntersecting) {{
                entry.target.querySelectorAll('.bar-fill').forEach(bar => {{
                    bar.style.animation = 'barIn 1.2s cubic-bezier(0.23,1,0.32,1) both';
                }});
            }}
        }});
    }}, {{ threshold: 0.2 }});
    document.querySelectorAll('.channel-row').forEach(row => observer.observe(row));
</script>

</body>
</html>"""
    return html


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = ArgumentParser(description="Bake CB247 weekly performance report")
    parser.add_argument("--week", "-w", help="Week date YYYY-MM-DD (default: today)")
    parser.add_argument("--output", "-o", help="Output path")
    args = parser.parse_args()

    if args.week:
        try:
            week_date = datetime.strptime(args.week, "%Y-%m-%d").date()
        except ValueError:
            print(f"❌ Invalid date: {args.week}"); sys.exit(1)
    else:
        week_date = datetime.now().date()

    date_str = week_date.strftime("%Y-%m-%d")

    ga4 = load_json(STATE_DIR / "ga4-data.json")
    gsc = load_json(STATE_DIR / "gsc-data.json")
    ads_data = load_json(STATE_DIR / "ads-data.json")
    gads_list = (ads_data.get("google_ads") or []) if ads_data else []
    meta_list = (ads_data.get("meta_ads") or []) if ads_data else []
    ahrefs = load_json(STATE_DIR / "ahrefs-data.json")
    apify  = load_json(STATE_DIR / "apify-data.json")

    if ahrefs:
        print("   Ahrefs data loaded ✅")
    else:
        print("   Ahrefs data not found — run pull_ahrefs.py ⚠️")
    if apify:
        print("   Apify data loaded ✅")
    else:
        print("   Apify data not found — run pull_apify.py ⚠️")

    html = build_html(date_str, ga4, gsc, gads_list, meta_list, ahrefs=ahrefs, apify=apify)

    if args.output:
        output_path = Path(args.output)
    else:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = REPORTS_DIR / f"cb247-weekly-report-{date_str}.html"

    output_path.write_text(html, encoding="utf-8")
    gads_spend = gads_list[0].get("combined", {}).get("spend", 0) if gads_list else 0
    meta_spend = meta_list[0].get("combined", {}).get("spend", 0) if meta_list else 0
    sessions = int((ga4.get("current") or {}).get("sessions", 0) or 0) if ga4 else 0
    print(f"✅ Weekly report saved to {output_path}")
    print(f"   GA4: {sessions:,} sessions | GSC: {gsc.get('summary',{}).get('total_clicks','?')} clicks")
    print(f"   Google Ads: ${gads_spend:.2f} | Meta Ads: ${meta_spend:.2f}")


if __name__ == "__main__":
    main()