"""
send_mwcc_weekly_report.py — Send Monday MWCC executive digest email.

Mirrors CB247's send_weekly_report.py but for MWCC. Sends a concise HTML
summary with the key Monday-meeting numbers + a link to the live dashboard.

Recipient:
  Single recipient from .env WEEKLY_REPORT_RECIPIENT (Tia).
  Policy (07 Jun 2026, Tia direction): all business digest emails are sent
  ONLY to Tia. No CC. No per-business recipient overrides. Matches CB247's
  send_weekly_report.py pattern for consistency across the group.

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
# Netlify-deployed weekly Operations report (revenue · wage · projections per centre).
# Override per cycle via .env: MWCC_OPS_REPORT_URL=https://myworldcc.netlify.app/2026-06-01-to-2026-06-05
OPS_REPORT_URL = os.getenv("MWCC_OPS_REPORT_URL", "https://myworldcc.netlify.app")


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

    # ── Capacity-weighted network occupancy (08 Jun 2026, Tia direction) ──
    # Matches the methodology used by bake_mwcc_management_report.py so both
    # reports show the same headline number. Previously this was a SIMPLE
    # average of per-centre Overall %, which gave equal weight to every
    # centre regardless of room capacity. Now it's weighted by total
    # licensed capacity across all rooms — answers 'what % of our physical
    # capacity is actually filled?'.
    def _capacity_weighted_occupancy(centres_dict):
        total_cap = 0
        total_filled = 0
        for c in (centres_dict or {}).values():
            for _, d in (c.get("rooms_detail") or {}).items():
                cap = d.get("capacity") or 0
                occ_pct = d.get("occupancy_pct")
                if cap and occ_pct is not None:
                    total_cap += cap
                    total_filled += cap * (occ_pct / 100.0)
        if not total_cap:
            return None
        return round(100.0 * total_filled / total_cap, 1)

    # KPIs
    centres = ops.get("centres", {}) or {}
    centre_arr = list(centres.values())
    avg_occ = _capacity_weighted_occupancy(centres)
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

    # Prior week ops (for occupancy WoW) — also capacity-weighted for consistency
    prior_centres = (ops_history[-2].get("centres", {}) if len(ops_history) >= 2 else {}) or {}
    prior_avg_occ = _capacity_weighted_occupancy(prior_centres) if prior_centres else None

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

    # ── Operations Summary block (08 Jun 2026, Tia direction) ──
    # Mirrors the Netlify Operations Report (https://myworldcc.netlify.app)
    # so recipients see the same headline numbers without leaving Gmail.
    # Source: state/mwcc-ops.json (already parsed from MYWORLD_REPORT.xlsx
    # by parse_mwcc_ops.py). All money in AUD.
    total_revenue   = ops.get("network_summary", {}).get("total_revenue", 0) or 0
    total_roster    = sum((c.get("roster_cost") or 0) for c in centre_arr)
    total_leave     = sum((c.get("leave_cost") or 0) for c in centre_arr)
    # Prior week roster (for WoW)
    prior_centres_dict = (ops_history[-2].get("centres", {}) if len(ops_history) >= 2 else {}) or {}
    prior_revenue = (ops_history[-2].get("network_summary", {}).get("total_revenue", 0)
                     if len(ops_history) >= 2 else None) or None
    prior_roster  = sum((c.get("roster_cost") or 0) for c in prior_centres_dict.values()) if prior_centres_dict else None
    # Wage % network-wide — weighted by roster cost (NOT simple average) so
    # bigger centres count more. = total roster / total revenue.
    wage_pct_network = round(100 * total_roster / total_revenue, 1) if total_revenue else None
    # Wage breaches (Inc. Leave > 42% threshold per FairWork ECEC benchmark)
    over_threshold = [c["name"] for c in centre_arr if (c.get("wage_inc_leave_pct") or 0) > 42]
    under_threshold = [c["name"] for c in centre_arr if (c.get("wage_exc_leave_pct") or 0) <= 42]

    # Next-week projection: sum revenue across all centres.
    # NOTE on field naming (parse_mwcc_ops.py legacy): the field labelled
    # `this_week_projection` in state actually represents the NEXT week
    # (Mon-Fri after the reporting week) — OWNA's "this week" relative to
    # report generation is "next week" relative to the email recipient
    # who reads it the following Monday. `next_week_projection` is the
    # week-after-that. Netlify Operations Report uses the same convention.
    next_revenue = sum((c.get("this_week_projection", {}) or {}).get("revenue") or 0 for c in centre_arr)
    next_revenue_delta = (next_revenue - total_revenue) if (next_revenue and total_revenue) else None
    # Top opportunity: lowest-occupancy room with most absolute headroom (capacity × gap)
    top_opp = None
    biggest_room_gap = 0
    for c in centre_arr:
        for rname, r in (c.get("rooms_detail") or {}).items():
            cap = r.get("capacity") or 0
            occ = r.get("occupancy_pct") or 0
            if cap > 0 and occ < 80:
                headroom = cap * (80 - occ) / 100
                if headroom > biggest_room_gap:
                    biggest_room_gap = headroom
                    top_opp = f"{c['name']} {rname} ({int(occ)}% occ, {cap}-place)"

    ops_summary = {
        "total_revenue":      total_revenue,
        "prior_revenue":      prior_revenue,
        "total_roster":       total_roster,
        "prior_roster":       prior_roster,
        "total_leave":        total_leave,
        "wage_pct_network":   wage_pct_network,
        "over_threshold":     over_threshold,
        "under_threshold":    under_threshold,
        "next_revenue":       next_revenue,
        "next_revenue_delta": next_revenue_delta,
        "top_opp":            top_opp,
        "unique_starters_rolling": ops.get("network_summary", {}).get("unique_starters_rolling"),
        "unique_exits_rolling":    ops.get("network_summary", {}).get("unique_exits_rolling"),
    }

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
        "ops_summary":     ops_summary,
    }


def _minify_html(html: str) -> str:
    """Strip HTML comments + collapse whitespace between tags to keep the
    raw MIME size well under Gmail's 102 KB clip threshold (which triggers
    the "..." trimmed-content link). Preserves whitespace inside <pre>,
    <textarea>, and <script> tags — none of which we use here, so safe.
    """
    import re
    # Drop HTML comments (incl. our section dividers)
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
    # Collapse runs of whitespace (incl. newlines) into one space
    html = re.sub(r"\s+", " ", html)
    # Strip whitespace between tags: >  <  →  ><
    html = re.sub(r">\s+<", "><", html)
    return html.strip()


def render_html(d: dict, dashboard_url: str, ops_report_url: str = OPS_REPORT_URL) -> str:
    """Compose the email HTML."""
    avg_occ, prior_occ = d["kpis"]["avg_occ"]
    total_spend, prior_spend = d["kpis"]["total_spend"]
    ops_s = d.get("ops_summary", {}) or {}

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

  <!-- Operations Snapshot (mirrors Netlify Operations Report) -->
  <div style="padding:20px 28px;background:#faf9ff;border-bottom:1px solid #e5e7eb;border-left:4px solid #8B6FD9">
    <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:12px">
      <div style="font-size:10px;font-weight:700;color:#4A2F8A;text-transform:uppercase;letter-spacing:.07em">Operations Snapshot · {d['ops_period']}</div>
      <a href="{ops_report_url}" style="font-size:10px;color:#8B6FD9;font-weight:700;text-decoration:none">Open full Operations Report →</a>
    </div>
    <table style="width:100%;border-collapse:collapse;font-size:13px">
      <tr>
        <td style="padding:8px 10px;width:50%;vertical-align:top">
          <div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;font-weight:700;margin-bottom:2px">Total Revenue</div>
          <div style="font-size:22px;font-weight:800;color:#4A2F8A">${ops_s.get('total_revenue', 0):,.0f}</div>
          <div style="font-size:11px;color:#6b7280">{_fmt_wow(ops_s.get('total_revenue'), ops_s.get('prior_revenue')) or 'WoW —'}</div>
        </td>
        <td style="padding:8px 10px;width:50%;vertical-align:top">
          <div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;font-weight:700;margin-bottom:2px">Roster Cost</div>
          <div style="font-size:22px;font-weight:800;color:#4A2F8A">${ops_s.get('total_roster', 0):,.0f}</div>
          <div style="font-size:11px;color:#6b7280">{ops_s.get('wage_pct_network','—')}% of revenue · Leave ${ops_s.get('total_leave',0):,.0f}</div>
        </td>
      </tr>
      <tr>
        <td style="padding:8px 10px;vertical-align:top">
          <div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;font-weight:700;margin-bottom:2px">Next Week Projection</div>
          <div style="font-size:22px;font-weight:800;color:#4A2F8A">${ops_s.get('next_revenue', 0):,.0f}</div>
          <div style="font-size:11px;color:{'#b91c1c' if (ops_s.get('next_revenue_delta') or 0) < 0 else '#15803d'}">{('+$' if (ops_s.get('next_revenue_delta') or 0) >= 0 else '-$') + f"{abs(ops_s.get('next_revenue_delta') or 0):,.0f}"} vs this week</div>
        </td>
        <td style="padding:8px 10px;vertical-align:top">
          <div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;font-weight:700;margin-bottom:2px">Cycle-To-Date · Since 1 May</div>
          <div style="font-size:22px;font-weight:800;color:#4A2F8A">{ops_s.get('unique_starters_rolling','—')} starters · {ops_s.get('unique_exits_rolling','—')} exits</div>
          <div style="font-size:11px;color:#6b7280">Deduped by child name (centre transfers excluded)</div>
        </td>
      </tr>
    </table>
    <div style="margin-top:10px;font-size:11.5px;color:#374151;line-height:1.6">
      {'<b style="color:#4A2F8A">Top occupancy opportunity:</b> ' + ops_s['top_opp'] + '.' if ops_s.get('top_opp') else ''}
    </div>
  </div>

  <!-- KPIs -->
  <div style="padding:20px 28px;background:#fff;border-bottom:1px solid #e5e7eb">
    <div style="font-size:10px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:.07em;margin-bottom:10px">Marketing KPIs</div>
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
    <a href="{dashboard_url}" style="display:inline-block;background:#8B6FD9;color:#fff;padding:10px 20px;border-radius:4px;text-decoration:none;font-weight:700;font-size:13px;margin:0 4px 4px">Open Marketing Dashboard</a>
    <a href="{ops_report_url}" style="display:inline-block;background:#01696f;color:#fff;padding:10px 20px;border-radius:4px;text-decoration:none;font-weight:700;font-size:13px;margin:0 4px 4px">Open Operations Report</a>
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
    html = _minify_html(render_html(d, DASHBOARD_URL, OPS_REPORT_URL))
    subject = f"[MWCC] Weekly Digest · {d['ops_period']}"

    if args.dry_run:
        print(f"Subject: {subject}\n")
        print(html)
        return 0

    # Single recipient policy (Tia direction 07 Jun 2026):
    # All business digest emails go ONLY to WEEKLY_REPORT_RECIPIENT (Tia).
    # No CC. No per-business overrides. Matches CB247's send_weekly_report.py.
    recipient = os.getenv("WEEKLY_REPORT_RECIPIENT", "").strip()
    if not recipient:
        print("[mwcc-email] WEEKLY_REPORT_RECIPIENT not set in .env — skipping")
        return 1
    ok = send(html, subject, [recipient])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
