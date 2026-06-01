"""
send_seo_report.py — Send weekly SEO email with all report attachments.
Reads state/*.json for all data sources.
Sends markdown + HTML reports as email attachments.
"""

import json
import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
OUTPUT_DIR = BASE_DIR / "outputs" / "seo" / "reports"
load_dotenv(BASE_DIR / ".env")

RECIPIENT = os.getenv("SEO_REPORT_RECIPIENT", "tia@chasingbetter.com.au")
SENDER = os.getenv("SENDER_EMAIL", os.getenv("SMTP_USER", "cb_agent@chasingbetter.com.au"))


def load_json(path):
    if path.exists():
        return json.loads(path.read_text())
    return None


def pct(a, b):
    if b == 0:
        return "n/a"
    change = ((a - b) / b) * 100
    return f"{'+' if change > 0 else ''}{change:.1f}%"


def arrow(val, inverse=False):
    if val > 0:
        return "↗️" if not inverse else "↘️"
    if val < 0:
        return "↘️" if not inverse else "↗️"
    return "➡️"


def build_html(gsc, ga4, ahrefs, sf, apify):
    """Build comprehensive HTML email from all data sources."""
    today = datetime.now().strftime("%d %B %Y")

    gsc_s = gsc.get("summary", {}) if gsc else {}
    gsc_prev = gsc.get("previous_summary", {}) if gsc else {}
    date_range = (gsc.get("date_range", {}) or {}) if gsc else {}
    gsc_top_q = (gsc.get("top_queries", []) or [])[:10]
    gsc_top_p = (gsc.get("top_pages", []) or [])[:10]

    ga4_c = ga4.get("current", {}) if ga4 else {}
    ga4_p = ga4.get("previous", {}) if ga4 else {}
    sessions = int(ga4_c.get("sessions", 0) or 0)
    p_sessions = int(ga4_p.get("sessions", 0) or 0)

    ahrefs_dr = (ahrefs.get("domain_rating", {}) or {}) if ahrefs else {}
    ahrefs_kw = (ahrefs.get("organic_keywords", []) or [])[:10]
    ahrefs_new = ((ahrefs.get("new_lost_links", {}) or {}).get("new") or [])[:3]
    ahrefs_lost = ((ahrefs.get("new_lost_links", {}) or {}).get("lost") or [])[:3]
    dr_val = ahrefs_dr.get("domain_rating", "—") if isinstance(ahrefs_dr, dict) else "—"

    sf_issues = (sf.get("issues") or []) if sf else []
    critical = [i for i in sf_issues if i.get("priority") == "High"][:5]
    medium = [i for i in sf_issues if i.get("priority") == "Medium"][:5]

    target_kw = [
        {"kw": "gym malaga", "location": "Malaga"},
        {"kw": "24/7 gym malaga", "location": "Malaga"},
        {"kw": "gym ellenbrook", "location": "Ellenbrook"},
        {"kw": "24/7 gym ellenbrook", "location": "Ellenbrook"},
        {"kw": "sauna malaga", "location": "Malaga"},
        {"kw": "ice bath malaga", "location": "Malaga"},
        {"kw": "kids gym malaga", "location": "Malaga"},
        {"kw": "reformer pilates perth", "location": "Perth"},
        {"kw": "bath house malaga", "location": "Malaga"},
    ]
    gsc_q = {q.get("query", "").lower(): q for q in (gsc.get("top_queries", []) or [])}
    kw_rows = []
    for tk in target_kw:
        q = gsc_q.get(tk["kw"].lower())
        pos = q.get("position", 0) if q else None
        if pos:
            cls = "pos-good" if pos <= 3 else "pos-mid" if pos <= 10 else "pos-bad"
            label = f"#{pos:.1f}"
        else:
            cls = "pos-none"
            label = "Not tracked"
        kw_rows.append(
            f'<tr><td>{tk["kw"]}</td><td>{tk["location"]}</td>'
            f'<td class="{cls}">{label}</td></tr>'
        )

    q_rows = "".join(
        f'<tr><td>{q["query"]}</td><td>{q["clicks"]}</td>'
        f'<td>{q["impressions"]}</td><td>{q["ctr"]*100:.1f}%</td>'
        f'<td>#{q["position"]:.1f}</td></tr>'
        for q in gsc_top_q
    ) if gsc_top_q else "<tr><td colspan='5' style='color:#555'>No query data.</td></tr>"

    p_rows = "".join(
        f'<tr><td>{p["page"][:60]}</td><td>{p["clicks"]}</td>'
        f'<td>{p["impressions"]}</td><td>{p["ctr"]*100:.1f}%</td>'
        f'<td>#{p["position"]:.1f}</td></tr>'
        for p in gsc_top_p
    ) if gsc_top_p else "<tr><td colspan='5' style='color:#555'>No page data.</td></tr>"

    ahrefs_kw_rows = "".join(
        f'<tr><td>{k.get("keyword","—")}</td><td>#{k.get("position","—")}</td>'
        f'<td>{k.get("volume","—")}</td><td>{k.get("cpc","—")}</td></tr>'
        for k in ahrefs_kw
    ) if ahrefs_kw else "<tr><td colspan='4' style='color:#555'>No Ahrefs data.</td></tr>"

    sf_critical_rows = "".join(
        f'<tr><td>{i["name"][:50]}</td><td>{i["type"]}</td><td>{i["count"]}</td></tr>'
        for i in critical
    ) if critical else "<tr><td colspan='3' style='color:#555'>None</td></tr>"
    sf_medium_rows = "".join(
        f'<tr><td>{i["name"][:50]}</td><td>{i["type"]}</td><td>{i["count"]}</td></tr>'
        for i in medium
    ) if medium else "<tr><td colspan='3' style='color:#555'>None</td></tr>"

    pos_is_worse = gsc_s.get('avg_position', 0) > gsc_prev.get('avg_position', 0)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0a; color: #fff; margin: 0; padding: 32px; }}
  .container {{ max-width: 900px; margin: 0 auto; }}
  .header {{ background: linear-gradient(135deg, #0d1f1c, #1a2e28); border: 1px solid #3FA69A; border-radius: 12px; padding: 24px 32px; margin-bottom: 32px; }}
  h1 {{ color: #3FA69A; font-size: 1.75rem; margin: 0 0 8px; }}
  h2 {{ color: #3FA69A; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.08em; border-bottom: 1px solid #222; padding-bottom: 8px; margin: 28px 0 14px; }}
  .subhead {{ color: #888; font-size: 0.875rem; margin: 0; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; }}
  .badge-red {{ background: rgba(224,85,85,0.15); color: #e05555 }}
  .badge-yellow {{ background: rgba(255,217,61,0.15); color: #ffd93d }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }}
  .kpi {{ background: #141414; border: 1px solid #1e1e1e; border-radius: 8px; padding: 16px; }}
  .kpi .label {{ color: #666; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }}
  .kpi .value {{ font-size: 1.5rem; font-weight: 700; color: #fff; }}
  .kpi .delta {{ font-size: 0.7rem; margin-top: 4px; }}
  .delta-pos {{ color: #3FA69A; }}
  .delta-neg {{ color: #e05555; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.8rem; margin-bottom: 16px; }}
  th {{ color: #888; text-align: left; padding: 8px 10px; border-bottom: 1px solid #2a2a2a; background: #0f0f0f; font-size: 0.7rem; text-transform: uppercase; }}
  td {{ padding: 8px 10px; border-bottom: 1px solid #161616; color: #bbb; }}
  tr:hover td {{ background: #141414; }}
  .pos-good {{ color: #00cc77; font-weight: 700; }}
  .pos-mid {{ color: #ffd93d; font-weight: 700; }}
  .pos-bad {{ color: #e05555; }}
  .pos-none {{ color: #555; }}
  .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #1e1e1e; color: #444; font-size: 0.7rem; text-align: center; }}
  .tag {{ display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 0.65rem; margin-left: 6px; }}
  .tag-gsc {{ background: rgba(63,166,154,0.2); color: #3FA69A }}
  .tag-ahrefs {{ background: rgba(255,107,53,0.2); color: #ff6b35 }}
  .tag-sf {{ background: rgba(255,217,61,0.2); color: #ffd93d }}
  .tag-ga4 {{ background: rgba(0,150,255,0.2); color: #0096ff }}
  .section-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
</style>
</head>
<body>
<div class="container">

<div class="header">
  <h1>CB247 Weekly SEO Report</h1>
  <p class="subhead">{date_range.get('start','?')} – {date_range.get('end','?')} &nbsp;|&nbsp; Generated {today} &nbsp;|&nbsp; 5 data sources combined</p>
</div>

<h2><span class="tag tag-gsc">GSC</span> Google Search Console</h2>
<div class="kpi-grid">
  <div class="kpi"><div class="label">Clicks</div><div class="value">{gsc_s.get('total_clicks', 0):,}</div><div class="delta delta-pos">{arrow(gsc_s.get('total_clicks',0) - gsc_prev.get('total_clicks',0))} {pct(gsc_s.get('total_clicks',0), gsc_prev.get('total_clicks',0))} vs prev</div></div>
  <div class="kpi"><div class="label">Impressions</div><div class="value">{gsc_s.get('total_impressions', 0):,}</div><div class="delta delta-pos">{arrow(gsc_s.get('total_impressions',0) - gsc_prev.get('total_impressions',0))} {pct(gsc_s.get('total_impressions',0), gsc_prev.get('total_impressions',0))} vs prev</div></div>
  <div class="kpi"><div class="label">Avg CTR</div><div class="value">{gsc_s.get('avg_ctr',0)*100:.2f}%</div><div class="delta">{arrow(gsc_s.get('avg_ctr',0) - gsc_prev.get('avg_ctr',0))} vs prev</div></div>
  <div class="kpi"><div class="label">Avg Position</div><div class="value">{gsc_s.get('avg_position',0):.1f}</div><div class="delta {'delta-neg' if pos_is_worse else 'delta-pos'}">{'worse' if pos_is_worse else 'better'}</div></div>
</div>

<h2><span class="tag tag-ga4">GA4</span> Google Analytics</h2>
<div class="kpi-grid">
  <div class="kpi"><div class="label">Total Sessions</div><div class="value">{sessions:,}</div><div class="delta delta-pos">{arrow(sessions - p_sessions)} {pct(sessions, p_sessions)} vs prev</div></div>
  <div class="kpi"><div class="label">New Users</div><div class="value">{ga4_c.get('new_users','—')}</div><div class="delta">{ga4_p.get('new_users','—')} prev week</div></div>
  <div class="kpi"><div class="label">Conversions</div><div class="value">{ga4_c.get('conversions','N/A')}</div><div class="delta">{ga4_p.get('conversions','—')}</div></div>
  <div class="kpi"><div class="label">Domain Rating</div><div class="value">{dr_val}</div><div class="delta"><span class="tag tag-ahrefs">Ahrefs</span></div></div>
</div>

<div class="section-grid">
  <div>
    <h2>Target Keyword Rankings</h2>
    <table><tr><th>Keyword</th><th>Location</th><th>Position</th></tr>{''.join(kw_rows)}</table>
  </div>
  <div>
    <h2>Top Ahrefs Keywords</h2>
    <table><tr><th>Keyword</th><th>Position</th><th>Volume</th><th>CPC</th></tr>{ahrefs_kw_rows}</table>
  </div>
</div>

<h2>Top 10 Queries <span class="tag tag-gsc">GSC</span></h2>
<table><tr><th>Query</th><th>Clicks</th><th>Impressions</th><th>CTR</th><th>Position</th></tr>{q_rows}</table>

<h2>Top 10 Pages <span class="tag tag-gsc">GSC</span></h2>
<table><tr><th>Page</th><th>Clicks</th><th>Impressions</th><th>CTR</th><th>Position</th></tr>{p_rows}</table>

<div class="section-grid">
  <div>
    <h2><span class="tag tag-sf">SF</span> Critical Tech Issues</h2>
    <table><tr><th>Issue</th><th>Type</th><th>Count</th></tr>{sf_critical_rows}</table>
  </div>
  <div>
    <h2><span class="tag tag-sf">SF</span> Medium Priority Issues</h2>
    <table><tr><th>Issue</th><th>Type</th><th>Count</th></tr>{sf_medium_rows}</table>
  </div>
</div>

<div class="section-grid">
  <div>
    <h2><span class="tag tag-ahrefs">AHREFS</span> New Links This Week</h2>
    <table><tr><th>URL</th><th>First Seen</th></tr>{''.join(f'<tr><td>{l.get("url","—")[:50]}</td><td>{l.get("first_seen","—")}</td></tr>' for l in ahrefs_new) if ahrefs_new else '<tr><td colspan="2" style="color:#555">None this week</td></tr>'}</table>
  </div>
  <div>
    <h2><span class="tag tag-ahrefs">AHREFS</span> Lost Links This Week</h2>
    <table><tr><th>URL</th><th>Last Seen</th></tr>{''.join(f'<tr><td>{l.get("url","—")[:50]}</td><td>{l.get("last_seen","—")}</td></tr>' for l in ahrefs_lost) if ahrefs_lost else '<tr><td colspan="2" style="color:#555">None this week</td></tr>'}</table>
  </div>
</div>

<h2>Priority Actions This Week</h2>
<table>
  <tr><th>Action</th><th>Priority</th><th>Source</th></tr>
  <tr><td>"gym malaga" position #{gsc_s.get('avg_position','—')} — target top 3 with Malaga landing page + backlinks</td><td><span class="badge badge-red">P1</span></td><td><span class="tag tag-gsc">GSC</span></td></tr>
  <tr><td>Add "bath house malaga" content — competitor gap from Ahrefs keyword data</td><td><span class="badge badge-red">P1</span></td><td><span class="tag tag-ahrefs">AHREFS</span></td></tr>
  <tr><td>Fix {len(critical)} critical Screaming Frog issues</td><td><span class="badge badge-red">P1</span></td><td><span class="tag tag-sf">SF</span></td></tr>
  <tr><td>Implement {len(medium)} medium priority SEO fixes</td><td><span class="badge badge-yellow">P2</span></td><td><span class="tag tag-sf">SF</span></td></tr>
  <tr><td>Ahrefs DR #{dr_val} — build 5+ new backlinks this week</td><td><span class="badge badge-yellow">P2</span></td><td><span class="tag tag-ahrefs">AHREFS</span></td></tr>
</table>

<div class="footer">
CB247 Marketing — Automated Weekly SEO Report<br>
Data: GA4 · Google Search Console · Ahrefs · Apify · Screaming Frog<br>
Full attachments: outputs/seo/reports/ | Pipeline: scripts/weekly-seo.sh
</div>
</div>
</body>
</html>"""
    return html


def build_text(gsc, ga4, ahrefs, sf):
    gsc_s = gsc.get("summary", {}) if gsc else {}
    ga4_c = ga4.get("current", {}) if ga4 else {}
    date_range = (gsc.get("date_range", {}) or {}) if gsc else {}
    dr_val = "—"
    if ahrefs and isinstance(ahrefs.get("domain_rating"), dict):
        dr_val = ahrefs["domain_rating"].get("domain_rating", "—")
    return f"""CB247 Weekly SEO Report — {date_range.get('start','?')} to {date_range.get('end','?')}

GSC: {gsc_s.get('total_clicks',0):,} clicks | {gsc_s.get('total_impressions',0):,} impr | {gsc_s.get('avg_ctr',0)*100:.2f}% CTR | avg pos {gsc_s.get('avg_position',0):.1f}
GA4: {int(ga4_c.get('sessions',0)):,} sessions | {ga4_c.get('conversions','N/A')} conversions
AHREFS: DR #{dr_val}

Full HTML report + attachments sent separately. See outputs/seo/reports/
"""


def send_email(html, subject, text_body, recipient, attachments=None):
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = SENDER
    smtp_pass = os.getenv("SMTP_PASS", "")

    if not smtp_host or not smtp_user or not smtp_pass:
        print("SMTP credentials not set — skipping email.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = recipient

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html, "html"))

    if attachments:
        for path in attachments:
            p = Path(path)
            if p.exists() and p.stat().st_size < 10_000_000:
                with open(p, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f'attachment; filename="{p.name}"'
                )
                msg.attach(part)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, recipient, msg.as_string())

    print(f"Report emailed to {recipient} [{len(attachments or [])} attachments]")
    return True


if __name__ == "__main__":
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    subject = f"CB247 Weekly SEO Report — {today.strftime('%d %b %Y')}"

    gsc = load_json(STATE_DIR / "gsc-data.json")
    ga4 = load_json(STATE_DIR / "ga4-data.json")
    ahrefs = load_json(STATE_DIR / "ahrefs-data.json")
    sf = load_json(STATE_DIR / "screaming-frog-data.json")
    apify = load_json(STATE_DIR / "apify-data.json")

    html_body = build_html(gsc, ga4, ahrefs, sf, apify)
    text_body = build_text(gsc, ga4, ahrefs, sf)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    html_path = OUTPUT_DIR / f"full-seo-email-{date_str}.html"
    html_path.write_text(html_body)

    attachments = [
        OUTPUT_DIR / f"full-seo-report-{date_str}.md",
        OUTPUT_DIR / f"full-seo-report-{date_str}.html",
        STATE_DIR / "gsc-data.json",
        STATE_DIR / "ga4-data.json",
        STATE_DIR / "ahrefs-data.json",
        STATE_DIR / "apify-data.json",
        STATE_DIR / "screaming-frog-data.json",
    ]
    existing = [str(a) for a in attachments if a.exists()]

    sent = send_email(html_body, subject, text_body, RECIPIENT, existing)

    if not sent:
        print(f"Email not sent. Reports at: {OUTPUT_DIR}")
        print(f"Attachments: {existing}")