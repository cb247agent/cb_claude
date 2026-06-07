"""
send_mwcc_weekly_report.py — Send Monday MWCC executive digest email.

Mirrors CB247's send_weekly_report.py but for MWCC. Sends a concise HTML
summary with the key Monday-meeting numbers + a link to the live dashboard.

Recipients:
  Primary:   MWCC_REPORT_RECIPIENT (from .env)
  Fallback:  WEEKLY_REPORT_RECIPIENT (CB247's recipient — usually Tia)
  Optional:  MWCC_REPORT_CC (comma-separated additional recipients)

What's in the email:
  - Period (Mon-Fri OWNA + Sat-Fri marketing — both date ranges shown)
  - Executive Verdict (Where we are / Biggest risk / Top priority) — same
    logic as the dashboard's verdict cards, computed once + sent
  - Top 5 KPIs with WoW deltas (Avg occupancy · Net enrolments · GA4 sessions ·
    Total ad spend · WoW change)
  - Top 5 P1/P2 actions across all source pages
  - Per-centre 1-line status (✓ Healthy / ⚠ Watch / ❌ Risk)
  - Link to live dashboard
  - Link to MWCC weekly HTML report (archived in outputs/reports/mwcc/)

Run manually:
  python scripts/send_mwcc_weekly_report.py
  python scripts/send_mwcc_weekly_report.py --dry-run    # print to stdout, no send

Wired into:
  scripts/weekly-report-mwcc.sh — runs as the final step after bake + deploy.
"""

from __future__ import annotations

import argparse
import json
import os
import smtplib
import ssl
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR  = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"

load_dotenv(BASE_DIR / ".env")

DASHBOARD_URL = "https://cb247agent.github.io/cb_claude/"


def _load(name: str, default=None):
    p = STATE_DIR / name
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def _fmt_num(v):
    if v is None or v == "":
        return "—"
    try:
        n = float(v)
        if abs(n) >= 1000:
            return f"{n:,.0f}"
        return f"{n:.2f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(v)


def _fmt_wow(curr, prev, suffix=""):
    if prev is None or prev == 0:
        return ""
    try:
        pct = ((curr - prev) / prev) * 100
        arrow = "↑" if pct > 0 else "↓" if pct < 0 else "→"
        return f' <span style="color:{"#10b981" if pct > 0 else "#ef4444"};font-size:11px;font-weight:600">{arrow} {abs(pct):.1f}% WoW{suffix}</span>'
    except (TypeError, ValueError, ZeroDivisionError):
        return ""


def build_digest() -> dict:
    """Read all MWCC state files and compose a digest."""
    ops          = _load("mwcc-ops.json",          default={})
    ops_history  = _load("mwcc-ops-history.json",  default=[])
    ga4          = _load("mwcc-ga4.json",          default={})
    meta         = _load("mwcc-meta.json",         default={})
    ads          = _load("mwcc-ads.json",          default={})
    meta_history = _load("mwcc-meta-history.json", default=[])
    ads_history  = _load("mwcc-ads-history.json",  default=[])
    work_queue   = _load("mwcc-work-queue.json",   default={"actions": []})

    # Period labels
    ops_period = ops.get("period", {}).get("label", "—")
    mkt_period = "—"
    if meta.get("date_range"):
        mkt_period = f"{meta['date_range'].get('start','—')} – {meta['date_range'].get('end','—')}"

    # KPIs
    centres = ops.get("centres", {}) or {}
    centre_arr = list(centres.values())
    avg_occ = (
        round(sum(c.get("occupancy", {}).get("Overall", 0) for c in centre_arr) / len(centre_arr))
        if centre_arr else None
    )
    net_enrol = ops.get("network_summary", {}).get("net_movement")
    total_enrol = ops.get("network_summary", {}).get("total_enrolments", 0)
    total_exits = ops.get("network_summary", {}).get("total_exits", 0)
    # GA4 sessions live at ga4.current.sessions in the pull_mwcc_ga4.py shape
    ga4_sessions = (ga4.get("current") or {}).get("sessions", 0) or ga4.get("sessions", 0)
    meta_spend = meta.get("summary", {}).get("spend", 0)
    ads_spend  = ads.get("totals", {}).get("spend", 0)
    total_spend = meta_spend + ads_spend

    # Prior week (for WoW)
    prior_meta_spend = (meta_history[1].get("summary", {}).get("spend", 0)) if len(meta_history) > 1 else None
    prior_ads_spend  = (ads_history[1].get("totals", {}).get("spend", 0))   if len(ads_history)  > 1 else None
    prior_total_spend = ((prior_meta_spend or 0) + (prior_ads_spend or 0)) if (prior_meta_spend is not None or prior_ads_spend is not None) else None

    # Prior week ops (for occupancy WoW)
    prior_centres = (ops_history[-2].get("centres", {}) if len(ops_history) >= 2 else {}) or {}
    prior_avg_occ = (
        round(sum(c.get("occupancy", {}).get("Overall", 0) for c in prior_centres.values()) / max(1, len(prior_centres)))
        if prior_centres else None
    )

    # Compliance risks
    risk_rooms = ops.get("network_summary", {}).get("rooms_with_compliance_risk", []) or []

    # Top P1+P2 actions
    actions = work_queue.get("actions") or []
    saved_published = set()  # we treat all as active for the digest
    p1_p2 = sorted(
        [a for a in actions if (a.get("priority") or "").upper() in ("P1", "P2")],
        key=lambda a: (a.get("priority", "P4"), a.get("source_run_at", "")),
        reverse=False,
    )[:5]

    # Per-centre status lines
    centre_status = []
    for name in ["Armadale", "Midvale", "Rockingham", "Seville Grove", "Waikiki"]:
        c = centres.get(name)
        if not c:
            centre_status.append((name, "—", "Not in OWNA report"))
            continue
        occ = c.get("occupancy", {}).get("Overall", 0)
        rooms = c.get("rooms_detail", {}) or {}
        at_risk = any(
            (r.get("capacity", 0) or 0) > 0
            and (r.get("compliance_risk") or (r.get("occupancy_pct", 0) or 0) >= 100)
            for r in rooms.values()
        )
        if at_risk:
            centre_status.append((name, f"{occ}%", "⚠ Compliance risk"))
        elif occ >= 70:
            centre_status.append((name, f"{occ}%", "✓ Within capacity"))
        else:
            centre_status.append((name, f"{occ}%", "Below target"))

    # Executive verdict (same logic as dashboard)
    where_we_are = (
        f"{total_enrol} enrolments · {total_exits} exits · "
        f"avg occupancy {avg_occ if avg_occ is not None else '—'}% · "
        f"${total_spend:.0f} ad spend · {_fmt_num(ga4_sessions)} GA4 sessions."
    )
    if risk_rooms:
        biggest_risk = f"<b>{', '.join(risk_rooms)}</b> — over licensed capacity. Cap intake or activate waitlist."
    elif net_enrol is not None and net_enrol < 0:
        biggest_risk = f"<b>Net enrolments {net_enrol}</b> — exits outpace enrolments. Kelley pulls cancel reasons from OWNA."
    elif avg_occ is not None and avg_occ < 50:
        biggest_risk = f"<b>Network occupancy {avg_occ}%</b> — under-utilised. Push paid spend to under-occupied rooms."
    else:
        biggest_risk = "No critical risks. Monitor at-risk rooms + WoW deltas."

    if risk_rooms:
        top_priority = f"Kelley to cap {risk_rooms[0]} intake by Friday and brief families on transition."
    elif p1_p2:
        top_priority = f"Review {len(p1_p2)} P1/P2 actions below. Top: {p1_p2[0].get('title','—')}"
    else:
        top_priority = "Review Work Queue for assigned actions across SEO / Meta / Google Ads / Enrolment."

    return {
        "ops_period":      ops_period,
        "mkt_period":      mkt_period,
        "where_we_are":    where_we_are,
        "biggest_risk":    biggest_risk,
        "top_priority":    top_priority,
        "kpis": {
            "avg_occ":     (avg_occ, prior_avg_occ),
            "net_enrol":   net_enrol,
            "total_enrol": total_enrol,
            "ga4":         ga4_sessions,
            "total_spend": (total_spend, prior_total_spend),
        },
        "centre_status":   centre_status,
        "p1_p2":           p1_p2,
        "action_count":    len(actions),
    }


def render_html(d: dict, dashboard_url: str) -> str:
    """Compose the email HTML."""
    avg_occ, prior_occ = d["kpis"]["avg_occ"]
    total_spend, prior_spend = d["kpis"]["total_spend"]

    rows_centre = ""
    for name, occ, status in d["centre_status"]:
        colour = "#ef4444" if "Compliance" in status else "#10b981" if "Within" in status else "#f59e0b" if "Below" in status else "#9ca3af"
        rows_centre += (
            f'<tr><td style="padding:6px 10px;font-weight:600">{name}</td>'
            f'<td style="padding:6px 10px;font-family:monospace">{occ}</td>'
            f'<td style="padding:6px 10px;color:{colour}">{status}</td></tr>'
        )

    rows_actions = ""
    for a in d["p1_p2"]:
        prio = a.get("priority", "—")
        prio_clr = "#ef4444" if prio == "P1" else "#f59e0b"
        rows_actions += (
            f'<tr><td style="padding:6px 10px"><span style="background:{prio_clr};color:#fff;padding:2px 7px;border-radius:3px;font-size:10px;font-weight:700">{prio}</span></td>'
            f'<td style="padding:6px 10px">{a.get("title","—")}</td>'
            f'<td style="padding:6px 10px;color:#6b7280">{a.get("owner","—")}</td></tr>'
        )
    if not rows_actions:
        rows_actions = '<tr><td colspan="3" style="padding:10px;color:#9ca3af;text-align:center">No P1/P2 actions queued</td></tr>'

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;background:#f9fafb;margin:0;padding:20px;color:#1f2937">
<div style="max-width:680px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;border:1px solid #e5e7eb">

  <!-- Header -->
  <div style="padding:24px 28px;background:#fff;border-bottom:1px solid #e5e7eb;border-left:4px solid #8B6FD9">
    <div style="font-size:11px;font-weight:700;color:#8B6FD9;text-transform:uppercase;letter-spacing:.1em;margin-bottom:6px">My World Childcare — Weekly Digest</div>
    <div style="font-size:18px;font-weight:700;color:#1f2937">{d['ops_period']} (operations) · {d['mkt_period']} (marketing)</div>
  </div>

  <!-- Verdict -->
  <div style="padding:20px 28px;background:#fff;border-bottom:1px solid #e5e7eb">
    <div style="font-size:10px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:.07em;margin-bottom:10px">This Week — Verdict</div>
    <div style="font-size:13px;line-height:1.7;color:#374151">
      <div><b>Where we are:</b> {d['where_we_are']}</div>
      <div style="margin-top:6px"><b style="color:#b91c1c">Biggest risk:</b> {d['biggest_risk']}</div>
      <div style="margin-top:6px"><b style="color:#4A2F8A">Top priority this week:</b> {d['top_priority']}</div>
    </div>
  </div>

  <!-- KPIs -->
  <div style="padding:20px 28px;background:#fff;border-bottom:1px solid #e5e7eb">
    <div style="font-size:10px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:.07em;margin-bottom:10px">Headline KPIs</div>
    <table style="width:100%;border-collapse:collapse;font-size:12.5px">
      <tr><td style="padding:6px 10px;width:60%">Network occupancy</td>
          <td style="padding:6px 10px;font-weight:700">{avg_occ if avg_occ is not None else '—'}%{_fmt_wow(avg_occ, prior_occ, 'pt')}</td></tr>
      <tr><td style="padding:6px 10px">Net enrolments</td>
          <td style="padding:6px 10px;font-weight:700">{d['kpis']['net_enrol'] if d['kpis']['net_enrol'] is not None else '—'} <span style="color:#6b7280;font-weight:500">({d['kpis']['total_enrol']} in)</span></td></tr>
      <tr><td style="padding:6px 10px">Total ad spend</td>
          <td style="padding:6px 10px;font-weight:700">${total_spend:.0f}{_fmt_wow(total_spend, prior_spend)}</td></tr>
      <tr><td style="padding:6px 10px">GA4 sessions</td>
          <td style="padding:6px 10px;font-weight:700">{_fmt_num(d['kpis']['ga4'])}</td></tr>
      <tr><td style="padding:6px 10px">Work queue actions</td>
          <td style="padding:6px 10px;font-weight:700">{d['action_count']} total</td></tr>
    </table>
  </div>

  <!-- Centres -->
  <div style="padding:20px 28px;background:#fff;border-bottom:1px solid #e5e7eb">
    <div style="font-size:10px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:.07em;margin-bottom:10px">5 Centres — At a Glance</div>
    <table style="width:100%;border-collapse:collapse;font-size:12.5px">
      {rows_centre}
    </table>
  </div>

  <!-- Top actions -->
  <div style="padding:20px 28px;background:#fff;border-bottom:1px solid #e5e7eb">
    <div style="font-size:10px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:.07em;margin-bottom:10px">Top P1 / P2 Actions This Week</div>
    <table style="width:100%;border-collapse:collapse;font-size:12.5px">
      {rows_actions}
    </table>
  </div>

  <!-- CTA -->
  <div style="padding:24px 28px;background:#fff;text-align:center">
    <a href="{dashboard_url}" style="display:inline-block;background:#8B6FD9;color:#fff;padding:10px 20px;border-radius:4px;text-decoration:none;font-weight:700;font-size:13px">Open live dashboard</a>
    <div style="font-size:11px;color:#9ca3af;margin-top:12px">My World Childcare Marketing OS · auto-generated by weekly-report-mwcc.sh</div>
  </div>

</div>
</body></html>"""


def send(html: str, subject: str, recipients: list[str]) -> bool:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    pwd  = os.getenv("SMTP_PASS")
    if not (host and user and pwd):
        print("[mwcc-email] SMTP_HOST / SMTP_USER / SMTP_PASS not set in .env — skipping")
        return False
    if not recipients:
        print("[mwcc-email] No recipients — skipping")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls(context=ctx)
            s.login(user, pwd)
            s.sendmail(user, recipients, msg.as_string())
        print(f"[mwcc-email] ✅ Sent to {', '.join(recipients)}")
        return True
    except Exception as e:
        print(f"[mwcc-email] SMTP send failed: {e}")
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Print HTML to stdout, don't send")
    args = ap.parse_args()

    d = build_digest()
    html = render_html(d, DASHBOARD_URL)
    subject = f"[MWCC] Weekly Digest · {d['ops_period']}"

    if args.dry_run:
        print(f"Subject: {subject}\n")
        print(html)
        return 0

    # Recipients
    primary = os.getenv("MWCC_REPORT_RECIPIENT") or os.getenv("WEEKLY_REPORT_RECIPIENT", "")
    cc      = os.getenv("MWCC_REPORT_CC", "")
    recipients = [r.strip() for r in (primary + "," + cc).split(",") if r.strip()]
    ok = send(html, subject, recipients)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
