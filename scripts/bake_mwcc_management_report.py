"""
bake_mwcc_management_report.py — Generate the weekly MWCC management report.

This report is the PRIVATE management view — intended for Robert (CEO),
Denver (COO), Kelley (Manager), Jordan (Content), Dana. It integrates
marketing performance with operational outcomes so management can see
the complete decision-making picture in one document.

Output: outputs/mwcc/management-report-{YYYY-MM-DD}.html

Inputs (all from state/ — produced earlier in the same cron run):
    state/mwcc-ops.json       — occupancy, enrolments, exits, wage, revenue, compliance
    state/mwcc-ga4.json       — website sessions + conversions
    state/mwcc-gsc-data.json  — search performance
    state/mwcc-ads.json       — Google Ads
    state/mwcc-meta.json      — Meta Ads
    state/mwcc-social.json    — Metricool
    state/mwcc-funnel.json    — enrolment funnel
    state/mwcc-work-queue.json — actions in flight + verdicts

AI verdict (optional):
    If `outputs/mwcc/mwcc-weekly-strategy-{date}.md` exists from a
    strategist-mwcc run, its narrative is embedded. Otherwise a
    deterministic Python verdict is generated from the KPI deltas.

Cron position: Runs AFTER all data parsers + emitters + sync, BEFORE
the dashboard bake. Wired into scripts/weekly-report-mwcc.sh.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any, Dict

BASE_DIR    = Path(__file__).resolve().parent.parent
STATE_DIR   = BASE_DIR / "state"
OUTPUTS_DIR = BASE_DIR / "outputs" / "mwcc"


# ── MWCC palette (matches context/mwcc-design-standards.md) ──
PALETTE = {
    "purple":      "#8B6FD9",
    "deep":        "#4A2F8A",
    "soft":        "#C5B6F0",
    "pale":        "#EDE7FA",
    "mist":        "#F5F1FC",
    "risk":        "#ef4444",
    "warn":        "#f59e0b",
    "ok":          "#16a34a",
    "text":        "#1a1a1a",
    "text_strong": "#0d0d0d",
    "muted":       "#6b6b65",
    "white":       "#ffffff",
    "gray_0":      "#f9fafb",
    "gray_1":      "#f3f4f6",
    "gray_2":      "#e6e6e6",
}


def _load(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception as e:
        print(f"[mwcc-mgmt-report] WARN failed to read {path.name}: {e}")
        return {}


def _fmt_money(n):
    if n is None: return "—"
    return f"${n:,.0f}"


def _fmt_int(n):
    if n is None: return "—"
    return f"{int(n):,}"


def _fmt_pct(n, suffix="%"):
    if n is None: return "—"
    return f"{n:.1f}{suffix}"


def _delta_chip(cur, prev, *, lower_is_better=False):
    """Build an HTML chip showing the delta with directional colour."""
    if cur is None or prev is None or prev == 0:
        return ""
    delta = cur - prev
    pct = (delta / prev) * 100
    good = (delta < 0) if lower_is_better else (delta > 0)
    color = PALETTE["ok"] if good else PALETTE["risk"]
    arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "■")
    return (
        f'<span style="color:{color};font-size:11px;font-weight:600;'
        f'margin-left:6px">{arrow} {pct:+.1f}%</span>'
    )


def _verdict_paragraph(ops, ga4, meta, ads):
    """Deterministic verdict — used when AI verdict unavailable.

    Builds 2-3 sentences from KPI deltas. Stays factual.
    """
    bits = []
    net = ops.get("network_summary", {})
    n_enrol = net.get("total_enrolments", 0)
    n_exits = net.get("total_exits", 0)
    n_enq   = net.get("total_enquiries", 0)
    n_net   = net.get("net_movement", 0)

    if n_net > 0:
        bits.append(f"Net positive on enrolments (+{n_net}) — {n_enrol} starters offset {n_exits} exits this week.")
    elif n_net < 0:
        bits.append(f"Net negative on enrolments ({n_net}) — {n_exits} exits exceeded {n_enrol} starters this week.")
    else:
        bits.append(f"Net flat on enrolments — {n_enrol} starters matched {n_exits} exits.")

    risk_rooms = net.get("rooms_with_compliance_risk", [])
    if risk_rooms:
        bits.append(f"⚠️ Compliance risk: {len(risk_rooms)} room(s) over capacity — {', '.join(risk_rooms[:3])}.")

    breach = net.get("centres_in_wage_breach", [])
    if breach:
        bits.append(f"Wage breach at {len(breach)} centre(s): {', '.join(breach)}.")

    # Marketing efficiency
    ga4_cur = (ga4 or {}).get("current", {})
    ga4_prev = (ga4 or {}).get("previous", {})
    if ga4_cur and ga4_prev:
        sessions = ga4_cur.get("sessions")
        prev_sessions = ga4_prev.get("sessions")
        if sessions and prev_sessions and prev_sessions > 0:
            pct = (sessions - prev_sessions) / prev_sessions * 100
            if abs(pct) >= 5:
                direction = "up" if pct > 0 else "down"
                bits.append(f"Web traffic {direction} {abs(pct):.0f}% week-on-week ({sessions:,} vs {prev_sessions:,} sessions).")

    bits.append(f"Active enquiry pipeline: {n_enq} this week.")

    return " ".join(bits)


def _find_strategist_md(date_str: str) -> Path | None:
    """Look for a strategist-mwcc output from this week's run."""
    candidates = [
        OUTPUTS_DIR / f"mwcc-weekly-strategy-{date_str}.md",
        BASE_DIR / "outputs" / "research" / f"strategist-mwcc-{date_str}.md",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _strategist_narrative_html(date_str: str) -> str:
    """Extract narrative from strategist-mwcc output if present.

    Returns HTML-safe rendering of sections 1-2 ("Week in one sentence"
    + "Where we are"), or empty string if file not found.
    """
    md_path = _find_strategist_md(date_str)
    if not md_path:
        return ""
    try:
        text = md_path.read_text()
    except Exception:
        return ""

    # Crude markdown → HTML for the narrative bits we want
    out = []
    capture = False
    section_buf = []
    for line in text.splitlines():
        # Section header
        if line.startswith("## 1.") or line.startswith("## 2.") or line.startswith("## 3."):
            if section_buf:
                out.append("<p>" + " ".join(section_buf).strip() + "</p>")
                section_buf = []
            capture = True
            heading = line.lstrip("# ").strip()
            out.append(f'<h4 style="color:{PALETTE["deep"]};font-size:13px;font-weight:600;margin-top:10px">{heading}</h4>')
            continue
        # Stop capturing at later sections
        if line.startswith("## 4.") or line.startswith("## 5.") or line.startswith("```"):
            if section_buf:
                out.append("<p>" + " ".join(section_buf).strip() + "</p>")
                section_buf = []
            capture = False
            continue
        if capture and line.strip():
            section_buf.append(line.strip())
    if section_buf:
        out.append("<p>" + " ".join(section_buf).strip() + "</p>")
    if not out:
        return ""
    return (
        f'<div style="background:{PALETTE["mist"]};border-left:4px solid {PALETTE["purple"]};'
        f'padding:14px 18px;border-radius:6px;margin-bottom:20px">'
        f'<div style="font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:{PALETTE["deep"]};font-weight:700;margin-bottom:6px">AI Strategy Synthesis</div>'
        f'{"".join(out)}</div>'
    )


# ── Section builders ─────────────────────────────────────────────

def _network_occupancy(ops):
    """Compute network occupancy % weighted by room capacity across all centres + rooms."""
    total_cap = 0
    total_filled = 0
    for c in (ops.get("centres") or {}).values():
        for room, d in (c.get("rooms_detail") or {}).items():
            cap = d.get("capacity") or 0
            occ_pct = d.get("occupancy_pct")
            if cap and occ_pct is not None:
                total_cap += cap
                total_filled += cap * (occ_pct / 100.0)
    if not total_cap:
        return None
    return round(100.0 * total_filled / total_cap, 1)


def _section_verdict(ops, ga4, meta, ads, date_str):
    verdict = _verdict_paragraph(ops, ga4, meta, ads)
    period = (ops.get("period") or {}).get("label", "—")
    strategist_html = _strategist_narrative_html(date_str)
    return f"""
    <section style="background:linear-gradient(135deg,{PALETTE['deep']} 0%,{PALETTE['purple']} 100%);color:#fff;padding:24px 28px;border-radius:12px;margin-bottom:20px">
      <div style="font-size:10px;letter-spacing:.08em;text-transform:uppercase;opacity:.7;font-weight:600">Verdict of the week · {period}</div>
      <h2 style="font-size:18px;font-weight:700;margin:6px 0 10px;letter-spacing:-0.01em">This week in one paragraph</h2>
      <p style="font-size:14px;line-height:1.6;opacity:.95">{verdict}</p>
    </section>
    {strategist_html}
    """


def _section_network_kpis(ops, ga4):
    """Top-line network KPIs with WoW deltas. Sits below the verdict."""
    network_occ = _network_occupancy(ops)
    net = ops.get("network_summary", {}) or {}
    revenue = net.get("total_revenue")
    enrolments = net.get("total_enrolments", 0)
    exits = net.get("total_exits", 0)
    net_move = net.get("net_movement", 0)
    enquiries_pipeline = sum(
        (c.get("enquiries_pipeline") or 0) for c in (ops.get("centres") or {}).values()
    )

    ga4_cur = (ga4 or {}).get("current") or {}
    ga4_prev = (ga4 or {}).get("previous") or {}
    sessions_cur = ga4_cur.get("sessions")
    sessions_prev = ga4_prev.get("sessions")
    conv_cur = ga4_cur.get("key_events")
    conv_prev = ga4_prev.get("key_events")

    # Build a 4-column KPI row
    occ_color = (
        PALETTE["risk"] if (network_occ is not None and network_occ > 100) else
        PALETTE["warn"] if (network_occ is not None and network_occ < 50) else
        PALETTE["deep"]
    )
    cards = [
        ("Network Occupancy", _fmt_pct(network_occ), None, occ_color),
        ("Network Revenue",   _fmt_money(revenue), None, PALETTE["deep"]),
        ("Web Sessions",      _fmt_int(sessions_cur), _delta_chip(sessions_cur, sessions_prev), PALETTE["purple"]),
        ("Web Conversions",   _fmt_int(conv_cur), _delta_chip(conv_cur, conv_prev), PALETTE["purple"]),
        ("Active Enquiry Pipeline", _fmt_int(enquiries_pipeline), None, PALETTE["purple"]),
        ("Net Enrolments (this wk)", f"{net_move:+d}", None, PALETTE["ok"] if net_move >= 0 else PALETTE["risk"]),
    ]
    grid = "".join(
        f'<div style="background:{PALETTE["white"]};border:1px solid {PALETTE["gray_2"]};border-left:3px solid {color};border-radius:8px;padding:14px 16px">'
        f'<div style="font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:{PALETTE["muted"]};font-weight:600">{label}</div>'
        f'<div style="font-size:22px;font-weight:700;color:{PALETTE["text_strong"]};margin-top:4px;line-height:1.1">{val}{chip or ""}</div>'
        f'</div>'
        for label, val, chip, color in cards
    )
    return f"""
    <section style="margin-bottom:24px">
      <h3 style="font-size:14px;font-weight:700;color:{PALETTE['deep']};text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px">Network KPIs (Week-on-Week)</h3>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px">{grid}</div>
    </section>
    """


def _section_funnel(ops, ga4, funnel):
    """Conversion story — ad spend → enquiries → tours → enrolments → revenue."""
    ga4_cur = (ga4 or {}).get("current", {}) or {}
    f_net = (funnel or {}).get("network") or {}

    sessions = f_net.get("web_sessions") or ga4_cur.get("sessions")
    convs = f_net.get("web_conversions") or ga4_cur.get("key_events")
    enquiries = f_net.get("enquiries") or (ops.get("network_summary") or {}).get("total_enquiries")
    enrolments = f_net.get("enrolments") or (ops.get("network_summary") or {}).get("total_enrolments")
    exits = f_net.get("exits") or (ops.get("network_summary") or {}).get("total_exits")
    revenue = (ops.get("network_summary") or {}).get("total_revenue")
    net_move = (ops.get("network_summary") or {}).get("net_movement", 0)

    stages = [
        ("Web sessions", _fmt_int(sessions),    PALETTE["soft"]),
        ("Conversions", _fmt_int(convs),         PALETTE["soft"]),
        ("Enquiries",   _fmt_int(enquiries),     PALETTE["purple"]),
        ("Enrolments",  _fmt_int(enrolments),    PALETTE["deep"]),
        ("Net move",    f"{net_move:+d}",        PALETTE["ok"] if net_move >= 0 else PALETTE["risk"]),
    ]
    cards = "".join(
        f'<div style="background:{PALETTE["white"]};border:1px solid {PALETTE["gray_2"]};border-top:3px solid {colour};border-radius:8px;padding:14px 10px;text-align:center;min-width:0">'
        f'<div style="font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:{PALETTE["muted"]};font-weight:600;white-space:nowrap">{label}</div>'
        f'<div style="font-size:22px;font-weight:700;color:{PALETTE["text_strong"]};margin-top:4px">{val}</div>'
        f'</div>'
        for label, val, colour in stages
    )
    return f"""
    <section style="margin-bottom:24px">
      <h3 style="font-size:14px;font-weight:700;color:{PALETTE['deep']};text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px">The Conversion Story</h3>
      <div style="background:{PALETTE['mist']};padding:18px;border-radius:10px">
        <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:10px">{cards}</div>
        <div style="font-size:11px;color:{PALETTE['muted']};text-align:center;margin-top:12px">
          Network revenue this week: <b style="color:{PALETTE['text_strong']}">{_fmt_money(revenue)}</b>
        </div>
      </div>
    </section>
    """


def _section_per_centre(ops):
    centres = ops.get("centres", {}) or {}
    cards = []
    for name, c in centres.items():
        occ = c.get("occupancy_pct")
        revenue = c.get("revenue")
        wage = c.get("wage_inc_leave_pct")
        wage_breach = c.get("wage_breach", False)
        enquiries = c.get("enquiries", 0)
        pipeline = c.get("enquiries_pipeline", 0)
        enrol = c.get("enrolments", 0)
        exits = c.get("exits", 0)
        risk_rooms = [
            r for r, d in (c.get("rooms_detail") or {}).items()
            if d.get("compliance_risk", False)
        ]
        # Border tint by risk
        border_color = PALETTE["risk"] if risk_rooms else (PALETTE["warn"] if wage_breach else PALETTE["purple"])
        wage_chip = (
            f'<span style="background:{PALETTE["warn"]}26;color:{PALETTE["warn"]};font-size:10px;padding:2px 6px;border-radius:4px;font-weight:600">WAGE</span>'
            if wage_breach else ""
        )
        risk_chip = (
            f'<span style="background:{PALETTE["risk"]}26;color:{PALETTE["risk"]};font-size:10px;padding:2px 6px;border-radius:4px;font-weight:600;margin-left:4px">RISK</span>'
            if risk_rooms else ""
        )
        cards.append(f"""
        <div style="background:{PALETTE['white']};border:1px solid {PALETTE['gray_2']};border-left:4px solid {border_color};border-radius:8px;padding:14px">
          <div style="display:flex;justify-content:space-between;align-items:flex-start">
            <div>
              <div style="font-size:13px;font-weight:700;color:{PALETTE['text_strong']}">{name}</div>
              <div style="font-size:10px;color:{PALETTE['muted']};margin-top:2px">{c.get('week_label','—')}</div>
            </div>
            <div>{wage_chip}{risk_chip}</div>
          </div>
          <table style="width:100%;margin-top:10px;font-size:11px;color:{PALETTE['text']}">
            <tr><td style="padding:3px 0;color:{PALETTE['muted']}">Occupancy</td><td style="text-align:right;font-weight:600">{_fmt_pct(occ)}</td></tr>
            <tr><td style="padding:3px 0;color:{PALETTE['muted']}">Revenue</td><td style="text-align:right;font-weight:600">{_fmt_money(revenue)}</td></tr>
            <tr><td style="padding:3px 0;color:{PALETTE['muted']}">Wage %</td><td style="text-align:right;font-weight:600">{_fmt_pct(wage)}</td></tr>
            <tr><td style="padding:3px 0;color:{PALETTE['muted']}">Enquiries this wk</td><td style="text-align:right;font-weight:600">{enquiries} <span style="color:{PALETTE['muted']};font-weight:400">· {pipeline} pipeline</span></td></tr>
            <tr><td style="padding:3px 0;color:{PALETTE['muted']}">Starters · Exits</td><td style="text-align:right;font-weight:600">{enrol} · {exits}</td></tr>
          </table>
        </div>
        """)
    grid = "".join(cards)
    return f"""
    <section style="margin-bottom:24px">
      <h3 style="font-size:14px;font-weight:700;color:{PALETTE['deep']};text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px">Per-Centre Snapshot</h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px">{grid}</div>
    </section>
    """


def _section_marketing_perf(ga4, meta, ads, gsc):
    """Marketing performance summary — by channel."""
    rows = []
    # GA4
    ga4_cur = (ga4 or {}).get("current", {}) or {}
    ga4_prev = (ga4 or {}).get("previous", {}) or {}
    if ga4_cur:
        for k, label, lower in [
            ("sessions", "Web sessions", False),
            ("key_events", "Conversions", False),
            ("engagement_rate", "Engagement rate", False),
        ]:
            cur = ga4_cur.get(k)
            prev = ga4_prev.get(k)
            val_fmt = _fmt_pct(cur * 100) if k == "engagement_rate" and cur is not None else _fmt_int(cur)
            chip = _delta_chip(cur, prev, lower_is_better=lower)
            rows.append(f"<tr><td>GA4</td><td>{label}</td><td style='text-align:right'>{val_fmt} {chip}</td></tr>")
    # Meta
    meta_cur = (meta or {}).get("current") or {}
    if meta_cur:
        rows.append(f"<tr><td>Meta</td><td>Spend</td><td style='text-align:right'>{_fmt_money(meta_cur.get('spend'))}</td></tr>")
        rows.append(f"<tr><td>Meta</td><td>CTR</td><td style='text-align:right'>{_fmt_pct(meta_cur.get('ctr'))}</td></tr>")
        rows.append(f"<tr><td>Meta</td><td>CPC</td><td style='text-align:right'>{_fmt_money(meta_cur.get('cpc'))}</td></tr>")
    # Google Ads
    ads_cur = (ads or {}).get("current") or {}
    if ads_cur:
        rows.append(f"<tr><td>Google Ads</td><td>Spend</td><td style='text-align:right'>{_fmt_money(ads_cur.get('spend'))}</td></tr>")
        rows.append(f"<tr><td>Google Ads</td><td>Clicks</td><td style='text-align:right'>{_fmt_int(ads_cur.get('clicks'))}</td></tr>")
    # GSC
    gsc_cur = (gsc or {}).get("totals", {}) if isinstance(gsc, dict) else {}
    if gsc_cur:
        rows.append(f"<tr><td>Organic Search</td><td>Clicks</td><td style='text-align:right'>{_fmt_int(gsc_cur.get('clicks'))}</td></tr>")
        rows.append(f"<tr><td>Organic Search</td><td>Impressions</td><td style='text-align:right'>{_fmt_int(gsc_cur.get('impressions'))}</td></tr>")

    if not rows:
        return ""
    body = "".join(rows)
    return f"""
    <section style="margin-bottom:24px">
      <h3 style="font-size:14px;font-weight:700;color:{PALETTE['deep']};text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px">Marketing Performance</h3>
      <table style="width:100%;border-collapse:collapse;background:{PALETTE['white']};border:1px solid {PALETTE['gray_2']};border-radius:8px;overflow:hidden;font-size:12px">
        <thead><tr style="background:{PALETTE['pale']}">
          <th style="text-align:left;padding:8px 12px;color:{PALETTE['deep']};font-weight:600">Channel</th>
          <th style="text-align:left;padding:8px 12px;color:{PALETTE['deep']};font-weight:600">Metric</th>
          <th style="text-align:right;padding:8px 12px;color:{PALETTE['deep']};font-weight:600">Value</th>
        </tr></thead>
        <tbody>{body}</tbody>
      </table>
    </section>
    """


def _section_compliance(ops):
    net = ops.get("network_summary", {}) or {}
    wage_centres = net.get("centres_in_wage_breach", []) or []
    risk_rooms = net.get("rooms_with_compliance_risk", []) or []
    if not wage_centres and not risk_rooms:
        return f"""
        <section style="margin-bottom:24px">
          <div style="background:{PALETTE['ok']}14;border-left:4px solid {PALETTE['ok']};padding:12px 16px;border-radius:6px">
            <div style="font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:{PALETTE['ok']};font-weight:700">✓ No compliance flags this week</div>
            <div style="font-size:12px;color:{PALETTE['text']};margin-top:4px">All centres within wage targets and licensed capacity.</div>
          </div>
        </section>
        """
    items = []
    for r in risk_rooms:
        items.append(f'<li style="margin:4px 0"><b style="color:{PALETTE["risk"]}">RISK</b> · {r} <span style="color:{PALETTE["muted"]}">(over licensed capacity — cap intake immediately)</span></li>')
    for c in wage_centres:
        items.append(f'<li style="margin:4px 0"><b style="color:{PALETTE["warn"]}">WAGE</b> · {c} <span style="color:{PALETTE["muted"]}">(wage % above 42% breach threshold)</span></li>')
    return f"""
    <section style="margin-bottom:24px">
      <h3 style="font-size:14px;font-weight:700;color:{PALETTE['risk']};text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px">Compliance &amp; Risk Panel</h3>
      <div style="background:{PALETTE['risk']}10;border-left:4px solid {PALETTE['risk']};padding:14px 18px;border-radius:6px">
        <ul style="list-style:none;padding:0;margin:0;font-size:12px;color:{PALETTE['text']}">{"".join(items)}</ul>
      </div>
    </section>
    """


def _section_next_week(work_queue):
    actions = (work_queue or {}).get("actions") or []
    upcoming = [
        a for a in actions
        if a.get("priority") == "P1" and a.get("overall_verdict") in (None, "pending")
    ][:6]
    if not upcoming:
        return ""
    rows = []
    for i, a in enumerate(upcoming, start=1):
        rows.append(f"""
        <tr>
          <td style="padding:6px 10px;color:{PALETTE['muted']}">{i}</td>
          <td style="padding:6px 10px">{a.get('title','')}</td>
          <td style="padding:6px 10px;color:{PALETTE['muted']}">{a.get('owner','—')}</td>
          <td style="padding:6px 10px;text-align:right;color:{PALETTE['muted']}">{a.get('effort_hours','—')}h</td>
        </tr>
        """)
    return f"""
    <section style="margin-bottom:24px">
      <h3 style="font-size:14px;font-weight:700;color:{PALETTE['deep']};text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px">What's Planned Next Week (P1 Actions)</h3>
      <table style="width:100%;border-collapse:collapse;background:{PALETTE['white']};border:1px solid {PALETTE['gray_2']};border-radius:8px;overflow:hidden;font-size:12px">
        <thead><tr style="background:{PALETTE['pale']}">
          <th style="text-align:left;padding:8px 12px;color:{PALETTE['deep']};font-weight:600">#</th>
          <th style="text-align:left;padding:8px 12px;color:{PALETTE['deep']};font-weight:600">Action</th>
          <th style="text-align:left;padding:8px 12px;color:{PALETTE['deep']};font-weight:600">Owner</th>
          <th style="text-align:right;padding:8px 12px;color:{PALETTE['deep']};font-weight:600">Effort</th>
        </tr></thead>
        <tbody>{"".join(rows)}</tbody>
      </table>
    </section>
    """


# ── Page assembly ─────────────────────────────────────────────────

def build_html(date_str: str) -> str:
    ops    = _load(STATE_DIR / "mwcc-ops.json")
    ga4    = _load(STATE_DIR / "mwcc-ga4.json")
    gsc    = _load(STATE_DIR / "mwcc-gsc-data.json")
    ads    = _load(STATE_DIR / "mwcc-ads.json")
    meta   = _load(STATE_DIR / "mwcc-meta.json")
    funnel = _load(STATE_DIR / "mwcc-funnel.json")
    wq     = _load(STATE_DIR / "mwcc-work-queue.json")

    period_label = (ops.get("period") or {}).get("label", date_str)

    sections = [
        _section_verdict(ops, ga4, meta, ads, date_str),
        _section_network_kpis(ops, ga4),
        _section_funnel(ops, ga4, funnel),
        _section_per_centre(ops),
        _section_compliance(ops),
        _section_marketing_perf(ga4, meta, ads, gsc),
        _section_next_week(wq),
    ]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>MWCC Management Report · {period_label}</title>
<style>
body {{ margin:0;font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",sans-serif;background:{PALETTE['gray_0']};color:{PALETTE['text']};line-height:1.5; }}
.wrap {{ max-width:920px;margin:0 auto;padding:24px 20px 40px; }}
.head {{ background:{PALETTE['white']};border-radius:10px;padding:18px 22px;margin-bottom:20px;border:1px solid {PALETTE['gray_2']};position:relative }}
.head h1 {{ font-size:20px;font-weight:700;color:{PALETTE['deep']};letter-spacing:-0.01em;margin:0 }}
.head p  {{ font-size:11px;color:{PALETTE['muted']};margin:4px 0 0 }}
.head-badge {{ position:absolute;top:14px;right:18px;background:{PALETTE['deep']};color:{PALETTE['white']};padding:4px 10px;border-radius:4px;font-size:9px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;box-shadow:0 1px 3px rgba(0,0,0,.08) }}
.footer {{ font-size:10px;color:{PALETTE['muted']};text-align:center;margin-top:30px;padding-top:14px;border-top:1px solid {PALETTE['gray_2']} }}
table {{ font-size:12px; }}
@media print {{ body {{ background:white }} .head-badge {{ display:none }} }}
</style>
</head>
<body>
<div class="wrap">
  <div class="head">
    <div class="head-badge">CONFIDENTIAL · MANAGEMENT</div>
    <h1>MWCC Management Report</h1>
    <p>{period_label} · My World Childcare · 5 centres</p>
  </div>
  {"".join(sections)}
  <div class="footer">
    Generated {_dt.datetime.now().strftime("%a %d %b %Y %H:%M %Z")} ·
    Recipients: Robert (CEO) · Denver (COO) · Kelley · Jordan · Dana ·
    For internal use only — do not forward
  </div>
</div>
</body>
</html>"""


def main() -> int:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    today = _dt.date.today().strftime("%Y-%m-%d")
    html = build_html(today)
    out_path = OUTPUTS_DIR / f"management-report-{today}.html"
    out_path.write_text(html, encoding="utf-8")
    size_kb = out_path.stat().st_size // 1024
    print(f"[mwcc-mgmt-report] ✅ Wrote {out_path.relative_to(BASE_DIR)} ({size_kb} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
