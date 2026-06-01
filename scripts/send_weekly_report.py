"""
send_weekly_report.py — Send weekly CB247 performance email.
Reads state/*.json for GA4, GSC, Google Ads, Meta Ads, GBP data.
Sends the HTML weekly report as email with JSON attachments.

Gmail / Google Workspace SMTP setup (one-time):
  1. Go to myaccount.google.com → Security → 2-Step Verification (enable if not already)
  2. Go to myaccount.google.com → Security → App Passwords
     → Select app: Mail → Select device: Other → Name it "CB247 Agent" → Generate
     → Copy the 16-character app password
  3. Add to CB_Marketing/.env:
       SMTP_HOST=smtp.gmail.com
       SMTP_PORT=587
       SMTP_USER=your@chasingbetter247.com.au
       SMTP_PASS=xxxx-xxxx-xxxx-xxxx   (the 16-char app password, no spaces)
       WEEKLY_REPORT_RECIPIENT=tia@chasingbetter247.com.au
  4. Test: python3 scripts/send_weekly_report.py
"""

import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
REPORTS_DIR = BASE_DIR / "outputs" / "reports"
load_dotenv(BASE_DIR / ".env")

RECIPIENT = os.getenv("WEEKLY_REPORT_RECIPIENT", "tia@chasingbetter.com.au")
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


def get_latest_report():
    """Find the most recent weekly report HTML."""
    reports = sorted(REPORTS_DIR.glob("cb247-weekly-report-*.html"), reverse=True)
    if reports:
        return reports[0]
    # Fallback to master report
    masters = sorted(REPORTS_DIR.glob("cb247-weekly-master-*.html"), reverse=True)
    if masters:
        return masters[0]
    return None


def load_gbp_data():
    """Extract CB247 GBP snapshot from apify-data.json."""
    apify_path = BASE_DIR / "state" / "apify-data.json"
    if not apify_path.exists():
        return None, None
    try:
        apify = json.loads(apify_path.read_text())
        targets = apify.get("competitor_maps", {}).get("targets", [])
        malaga = next((t for t in targets if t.get("location") == "Malaga"), {})
        ellenbrook = next((t for t in targets if t.get("location") == "Ellenbrook"), {})
        return malaga, ellenbrook
    except Exception:
        return None, None


def build_email_body(ga4, gsc, google_ads, meta_ads, report_date):
    """Build a plain-text + HTML summary email with key metrics."""
    today = datetime.now().strftime("%d %B %Y")

    # GA4
    ga4_c = (ga4.get("current") or {}) if ga4 else {}
    ga4_p = (ga4.get("previous") or {}) if ga4 else {}
    sessions = int(ga4_c.get("sessions", 0) or 0)
    p_sessions = int(ga4_p.get("sessions", 0) or 0)
    new_users = ga4_c.get("new_users", "—")
    p_new_users = ga4_p.get("new_users", "—")
    conversions = ga4_c.get("conversions", "N/A")
    p_conversions = ga4_p.get("conversions", "—")

    # GSC
    gsc_s = (gsc.get("summary") or {}) if gsc else {}
    gsc_prev = (gsc.get("previous_summary") or {}) if gsc else {}
    date_range = (gsc.get("date_range") or {}) if gsc else {}
    gsc_clicks = gsc_s.get("total_clicks", 0)
    gsc_p_clicks = gsc_prev.get("total_clicks", 0)
    gsc_impr = gsc_s.get("total_impressions", 0)
    gsc_p_impr = gsc_prev.get("total_impressions", 0)
    gsc_ctr = gsc_s.get("avg_ctr", 0)
    gsc_p_ctr = gsc_prev.get("avg_ctr", 0)
    gsc_pos = gsc_s.get("avg_position", 0)
    gsc_p_pos = gsc_prev.get("avg_position", 0)
    top_queries = (gsc.get("top_queries") or [])[:5]

    # Google Ads — list of weekly rows with malaga/ellenbrook keys
    # Most recent week is first (sorted newest-first by pull_local_ads.py)
    gads_list = google_ads.get("google_ads", []) if google_ads else []
    if gads_list and isinstance(gads_list[0], dict) and "malaga" in gads_list[0]:
        latest_gads = gads_list[0]
        malaga_spend = float(latest_gads.get("malaga", {}).get("spend", 0))
        malaga_clicks = int(latest_gads.get("malaga", {}).get("clicks", 0))
        malaga_convs = int(latest_gads.get("malaga", {}).get("conv", 0))
        ellenbrook_spend = float(latest_gads.get("ellenbrook", {}).get("spend", 0))
        ellenbrook_clicks = int(latest_gads.get("ellenbrook", {}).get("clicks", 0))
        ellenbrook_convs = int(latest_gads.get("ellenbrook", {}).get("conv", 0))
        total_spend = float(latest_gads.get("combined", {}).get("spend", 0))
        total_clicks = int(latest_gads.get("combined", {}).get("clicks", 0))
        total_convs = int(latest_gads.get("combined", {}).get("conv", 0))
        gads_week_label = latest_gads.get("week_label", "")
    else:
        malaga_spend = malaga_clicks = malaga_convs = 0
        ellenbrook_spend = ellenbrook_clicks = ellenbrook_convs = 0
        total_spend = total_clicks = total_convs = 0
        gads_week_label = ""

    # Meta Ads — list of weekly rows with malaga/ellenbrook keys (no results field, use clicks)
    meta_list = meta_ads.get("meta_ads", []) if meta_ads else []
    if meta_list and isinstance(meta_list[0], dict) and "malaga" in meta_list[0]:
        latest_meta = meta_list[0]
        malaga_meta_spend = float(latest_meta.get("malaga", {}).get("spend", 0))
        ellenbrook_meta_spend = float(latest_meta.get("ellenbrook", {}).get("spend", 0))
        malaga_meta_results = int(latest_meta.get("malaga", {}).get("clicks", 0))
        ellenbrook_meta_results = int(latest_meta.get("ellenbrook", {}).get("clicks", 0))
        meta_spend = malaga_meta_spend + ellenbrook_meta_spend
        meta_results = malaga_meta_results + ellenbrook_meta_results
        meta_cpr = f"${meta_spend/meta_results:.2f}" if meta_results > 0 else "—"
        meta_week_label = latest_meta.get("week_label", "")
    else:
        malaga_meta_spend = ellenbrook_meta_spend = meta_spend = 0
        malaga_meta_results = ellenbrook_meta_results = meta_results = 0
        meta_cpr = "—"
        meta_week_label = ""

    # GBP
    gbp_malaga, gbp_ellenbrook = load_gbp_data()
    gbp_available = gbp_malaga is not None

    q_rows = "".join(
        f"<tr><td>{q.get('query','')}</td><td>{q.get('clicks',0)}</td>"
        f"<td>{q.get('impressions',0)}</td><td>{q.get('ctr',0)*100:.1f}%</td>"
        f"<td>#{q.get('position',0):.1f}</td></tr>"
        for q in top_queries
    ) if top_queries else "<tr><td colspan='5' style='color:#555'>No query data.</td></tr>"

    text_body = f"""CB247 Weekly Performance Report — {date_range.get('start','?')} to {date_range.get('end','?')}

GA4: {sessions:,} sessions ({pct(sessions,p_sessions)} vs prev) | {new_users} new users
GSC: {gsc_clicks:,} clicks ({pct(gsc_clicks,gsc_p_clicks)}) | {gsc_impr:,} impr | {gsc_ctr*100:.2f}% CTR | pos #{gsc_pos:.1f}
Google Ads: ${total_spend:.2f} spend | {total_clicks} clicks | {total_convs} conversions
Meta Ads: ${meta_spend:.2f} spend | {meta_results:,} results | CPR {meta_cpr}

Full HTML report attached or at: outputs/reports/cb247-weekly-report-{report_date}.html
"""

    # GBP table — pre-built so it can be safely injected into the f-string below
    if gbp_available and gbp_malaga and gbp_ellenbrook:
        gbp_table_html = (
            "<table>"
            "<tr><th>Location</th><th>Rating</th><th>Reviews</th><th>Target</th><th>Photos</th><th>Profile %</th></tr>"
            f"<tr><td>Malaga</td><td>⭐ {gbp_malaga.get('rating','—')}</td>"
            f"<td>{gbp_malaga.get('reviews','—')}</td><td>530+</td>"
            f"<td>{gbp_malaga.get('photos','—')}</td><td>{gbp_malaga.get('completeness_score','—')}%</td></tr>"
            f"<tr><td>Ellenbrook</td><td>⭐ {gbp_ellenbrook.get('rating','—')}</td>"
            f"<td>{gbp_ellenbrook.get('reviews','—')}</td><td>280+</td>"
            f"<td>{gbp_ellenbrook.get('photos','—')}</td><td>{gbp_ellenbrook.get('completeness_score','—')}%</td></tr>"
            "</table>"
        )
    else:
        gbp_table_html = "<p style='color:#666'>GBP data not available — run: python3 scripts/pull_apify.py</p>"

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
  .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #1e1e1e; color: #444; font-size: 0.7rem; text-align: center; }}
  .tag {{ display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 0.65rem; margin-left: 6px; }}
  .tag-ga4 {{ background: rgba(0,150,255,0.2); color: #0096ff }}
  .tag-gsc {{ background: rgba(63,166,154,0.2); color: #3FA69A }}
  .tag-gads {{ background: rgba(224,85,85,0.2); color: #e05555 }}
  .tag-meta {{ background: rgba(0,100,200,0.2); color: #64b5f6 }}
  .section-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
</style>
</head>
<body>
<div class="container">

<div class="header">
  <h1>CB247 Weekly Performance Report</h1>
  <p class="subhead">{date_range.get('start','?')} – {date_range.get('end','?')} &nbsp;|&nbsp; Generated {today}</p>
</div>

<div class="section-grid">
  <div>
    <h2><span class="tag tag-ga4">GA4</span> Google Analytics</h2>
    <table>
      <tr><th>Metric</th><th>This Week</th><th>Prev Week</th><th>Change</th></tr>
      <tr><td>Sessions</td><td>{sessions:,}</td><td>{p_sessions:,}</td><td>{arrow(sessions-p_sessions)} {pct(sessions,p_sessions)}</td></tr>
      <tr><td>New Users</td><td>{new_users}</td><td>{p_new_users}</td><td>—</td></tr>
      <tr><td>Conversions</td><td>{conversions}</td><td>{p_conversions}</td><td>—</td></tr>
    </table>
  </div>
  <div>
    <h2><span class="tag tag-gsc">GSC</span> Google Search Console</h2>
    <table>
      <tr><th>Metric</th><th>This Period</th><th>Prev Period</th><th>Change</th></tr>
      <tr><td>Clicks</td><td>{gsc_clicks:,}</td><td>{gsc_p_clicks:,}</td><td>{arrow(gsc_clicks-gsc_p_clicks)} {pct(gsc_clicks,gsc_p_clicks)}</td></tr>
      <tr><td>Impressions</td><td>{gsc_impr:,}</td><td>{gsc_p_impr:,}</td><td>{arrow(gsc_impr-gsc_p_impr)} {pct(gsc_impr,gsc_p_impr)}</td></tr>
      <tr><td>Avg CTR</td><td>{gsc_ctr*100:.2f}%</td><td>{gsc_p_ctr*100:.2f}%</td><td>{arrow(gsc_ctr-gsc_p_ctr)} vs prev</td></tr>
      <tr><td>Avg Position</td><td>#{gsc_pos:.1f}</td><td>#{gsc_p_pos:.1f}</td><td>—</td></tr>
    </table>
  </div>
</div>

<div class="section-grid">
  <div>
    <h2><span class="tag tag-gads">Google Ads</span> Campaign Summary</h2>
    <table>
      <tr><th>Location</th><th>Spend</th><th>Clicks</th><th>Conv</th></tr>
      <tr><td>Malaga</td><td>${malaga_spend:.2f}</td><td>{malaga_clicks}</td><td>{malaga_convs}</td></tr>
      <tr><td>Ellenbrook</td><td>${ellenbrook_spend:.2f}</td><td>{ellenbrook_clicks}</td><td>{ellenbrook_convs}</td></tr>
      <tr><td><strong>Total</strong></td><td><strong>${total_spend:.2f}</strong></td><td><strong>{total_clicks}</strong></td><td><strong>{total_convs}</strong></td></tr>
    </table>
  </div>
  <div>
    <h2><span class="tag tag-meta">Meta Ads</span> Campaign Summary</h2>
    <table>
      <tr><th>Location</th><th>Spend</th><th>Results</th><th>CPR</th></tr>
      <tr><td>Malaga</td><td>${malaga_meta_spend:.2f}</td><td>{malaga_meta_results:,}</td><td>—</td></tr>
      <tr><td>Ellenbrook</td><td>${ellenbrook_meta_spend:.2f}</td><td>{ellenbrook_meta_results:,}</td><td>—</td></tr>
      <tr><td><strong>Total</strong></td><td><strong>${meta_spend:.2f}</strong></td><td><strong>{meta_results:,}</strong></td><td><strong>{meta_cpr}</strong></td></tr>
    </table>
  </div>
</div>

<h2>Top 5 Search Queries <span class="tag tag-gsc">GSC</span></h2>
<table><tr><th>Query</th><th>Clicks</th><th>Impressions</th><th>CTR</th><th>Position</th></tr>{q_rows}</table>

<h2>📍 Google Business Profile — Local Visibility</h2>
{gbp_table_html}

<div class="footer">
CB247 Marketing — Automated Weekly Performance Report<br>
Data: GA4 · Google Search Console · Google Ads · Meta Ads<br>
Full HTML report: outputs/reports/cb247-weekly-report-{report_date}.html<br>
Pipeline: scripts/weekly-report.sh
</div>
</div>
</body>
</html>"""
    return html, text_body


def send_email(html, subject, text_body, recipient, attachments=None):
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")   # Gmail default
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = SENDER
    smtp_pass = os.getenv("SMTP_PASS", "")

    if not smtp_user or not smtp_pass:
        print("[Email] SMTP credentials not set in .env — skipping email.")
        print("[Email] Required in .env:")
        print("          SMTP_USER=your@chasingbetter247.com.au")
        print("          SMTP_PASS=xxxx-xxxx-xxxx-xxxx  (Gmail app password)")
        print("          WEEKLY_REPORT_RECIPIENT=tia@chasingbetter247.com.au")
        print("[Email] Setup guide: see docstring at top of this file.")
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

    print(f"Weekly report emailed to {recipient} [{len(attachments or [])} attachments]")
    return True


if __name__ == "__main__":
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    subject = f"CB247 Weekly Performance Report — {today.strftime('%d %b %Y')}"

    ga4 = load_json(STATE_DIR / "ga4-data.json")
    gsc = load_json(STATE_DIR / "gsc-data.json")
    ads_data = load_json(STATE_DIR / "ads-data.json")
    # Both Google Ads and Meta Ads come from ads-data.json (pull_local_ads.py)
    google_ads = ads_data
    meta_ads = ads_data

    html_body, text_body = build_email_body(ga4, gsc, google_ads, meta_ads, date_str)

    attachments = [
        REPORTS_DIR / f"cb247-weekly-report-{date_str}.html",
    ]
    existing = [str(a) for a in attachments if a.exists()]

    sent = send_email(html_body, subject, text_body, RECIPIENT, existing)

    if not sent:
        print(f"Email not sent. Reports at: {REPORTS_DIR}")
        print(f"Attachments: {existing}")
