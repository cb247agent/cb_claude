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
import re as _re
import sys
from pathlib import Path
from typing import Any, Dict


def _minify_html(html: str) -> str:
    """Strip excess whitespace so Gmail/Outlook don't clip the email.

    Keeps inline styles intact (needed for email compat). Removes:
      - whitespace between adjacent tags (>< instead of > <)
      - multiple consecutive spaces inside tag bodies
      - leading/trailing whitespace on each line
      - line breaks outside <pre>/<textarea> (none of which we use)
    Typically shrinks output by 30-40%.
    """
    # Remove whitespace between tags
    html = _re.sub(r'>\s+<', '><', html)
    # Collapse runs of whitespace (multiple spaces, tabs, newlines) to single space
    html = _re.sub(r'\s{2,}', ' ', html)
    # Final pass: strip newlines that crept in around attributes
    html = html.replace('\n', '')
    return html.strip()

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


def _section_network_kpis_combined(ops, ga4, funnel):
    """Merged Network KPIs + Conversion Story — single section.

    Row 1 (funnel): Sessions → Conversions → Enquiries → Enrolments → Exits → Net Move
    Row 2 (state):  Network Occupancy · Network Revenue · Active Pipeline
    """
    network_occ = _network_occupancy(ops)
    net = ops.get("network_summary", {}) or {}
    revenue = net.get("total_revenue")
    n_enrolments = net.get("total_enrolments", 0)
    n_exits = net.get("total_exits", 0)
    n_enquiries = net.get("total_enquiries", 0)
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

    occ_color = (
        PALETTE["risk"] if (network_occ is not None and network_occ > 100) else
        PALETTE["warn"] if (network_occ is not None and network_occ < 50) else
        PALETTE["deep"]
    )

    # Row 1 — the funnel left-to-right (6 cards)
    funnel_cards = [
        ("Web Sessions",      _fmt_int(sessions_cur), _delta_chip(sessions_cur, sessions_prev), PALETTE["soft"]),
        ("Conversions",       _fmt_int(conv_cur),     _delta_chip(conv_cur, conv_prev),         PALETTE["soft"]),
        ("Enquiries",         _fmt_int(n_enquiries),  None,                                     PALETTE["purple"]),
        ("Enrolments",        _fmt_int(n_enrolments), None,                                     PALETTE["deep"]),
        ("Exits",             _fmt_int(n_exits),      None,                                     PALETTE["risk"]),
        ("Net Move",          f"{net_move:+d}",       None,                                     PALETTE["ok"] if net_move >= 0 else PALETTE["risk"]),
    ]

    # Row 2 — network state (3 cards)
    state_cards = [
        ("Network Occupancy",       _fmt_pct(network_occ),       None, occ_color),
        ("Network Revenue",         _fmt_money(revenue),         None, PALETTE["deep"]),
        ("Active Enquiry Pipeline", _fmt_int(enquiries_pipeline),None, PALETTE["purple"]),
    ]

    def _card_cell(label, val, chip, color, *, width_pct):
        return (
            f'<td style="width:{width_pct}%;padding:6px 6px;vertical-align:top">'
            f'  <div style="background:{PALETTE["white"]};border:1px solid {PALETTE["gray_2"]};border-top:3px solid {color};border-radius:8px;padding:14px 8px;text-align:center">'
            f'    <div style="font-size:9px;text-transform:uppercase;letter-spacing:.05em;color:{PALETTE["muted"]};font-weight:600;white-space:nowrap">{label}</div>'
            f'    <div style="font-size:20px;font-weight:700;color:{PALETTE["text_strong"]};margin-top:4px;line-height:1.1">{val}{chip or ""}</div>'
            f'  </div>'
            f'</td>'
        )

    # Row 1: 6 cards at ~14% each, with 8% spacer either side
    row1_cells = "".join(_card_cell(*c, width_pct=14) for c in funnel_cards)
    # Row 2: 3 cards at ~28% each, with 8% spacer either side
    row2_cells = "".join(_card_cell(*c, width_pct=28) for c in state_cards)

    return f"""
    <section style="margin-bottom:24px">
      <h3 style="font-size:14px;font-weight:700;color:{PALETTE['deep']};text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px">Network KPIs &amp; Conversion Story (Week-on-Week)</h3>
      <div style="background:{PALETTE['mist']};padding:20px;border-radius:10px">
        <table style="width:100%;border-collapse:separate;border-spacing:0;table-layout:fixed">
          <tr><td style="width:8%"></td>{row1_cells}<td style="width:8%"></td></tr>
        </table>
        <table style="width:100%;border-collapse:separate;border-spacing:0;table-layout:fixed;margin-top:8px">
          <tr><td style="width:8%"></td>{row2_cells}<td style="width:8%"></td></tr>
        </table>
      </div>
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
    # Use table layout for bulletproof centering across email clients.
    # 5 cells at 20% width each + outer cells (5%) to centre the group.
    card_cells = "".join(
        f'<td style="width:18%;padding:0 8px;vertical-align:top">'
        f'  <div style="background:{PALETTE["white"]};border:1px solid {PALETTE["gray_2"]};border-top:3px solid {colour};border-radius:8px;padding:16px 12px;text-align:center">'
        f'    <div style="font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:{PALETTE["muted"]};font-weight:600;white-space:nowrap">{label}</div>'
        f'    <div style="font-size:22px;font-weight:700;color:{PALETTE["text_strong"]};margin-top:4px">{val}</div>'
        f'  </div>'
        f'</td>'
        for label, val, colour in stages
    )
    return f"""
    <section style="margin-bottom:24px">
      <h3 style="font-size:14px;font-weight:700;color:{PALETTE['deep']};text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px">The Conversion Story</h3>
      <div style="background:{PALETTE['mist']};padding:20px;border-radius:10px">
        <table style="width:100%;border-collapse:separate;border-spacing:0;table-layout:fixed">
          <tr>
            <td style="width:5%"></td>
            {card_cells}
            <td style="width:5%"></td>
          </tr>
        </table>
        <div style="font-size:11px;color:{PALETTE['muted']};text-align:center;margin-top:14px">
          Network revenue this week: <b style="color:{PALETTE['text_strong']}">{_fmt_money(revenue)}</b>
        </div>
      </div>
    </section>
    """


def _occ_chip(pct):
    """Return an occupancy chip with colour by tier."""
    if pct is None:
        return f'<span style="color:{PALETTE["muted"]}">—</span>'
    if pct >= 80:
        bg, fg = PALETTE["ok"] + "26", PALETTE["ok"]
    elif pct >= 60:
        bg, fg = PALETTE["warn"] + "26", PALETTE["warn"]
    elif pct >= 40:
        bg, fg = "#fef9c326", "#a16207"  # yellow
    else:
        bg, fg = PALETTE["risk"] + "26", PALETTE["risk"]
    return f'<span style="background:{bg};color:{fg};padding:2px 8px;border-radius:6px;font-size:11px;font-weight:700">{pct}%</span>'


def _wage_bar(label, pct, *, color, helper_text=""):
    """Render a wage-percentage bar with colour-coded fill + chip + helper."""
    if pct is None:
        return ""
    width_pct = min(100, max(0, pct))
    return f"""
    <div style="margin-top:10px">
      <div style="display:flex;justify-content:space-between;align-items:center;font-size:11px;color:{PALETTE['text']}">
        <b>{label}</b>
        <span style="background:{color}26;color:{color};padding:2px 8px;border-radius:6px;font-size:11px;font-weight:700">{pct}%</span>
      </div>
      <div style="background:{PALETTE['gray_1']};border-radius:4px;height:6px;margin-top:6px;overflow:hidden">
        <div style="width:{width_pct}%;height:100%;background:{color}"></div>
      </div>
      {f'<div style="font-size:10px;color:{PALETTE["muted"]};margin-top:4px">{helper_text}</div>' if helper_text else ''}
    </div>
    """


def _service_util_table(rooms_detail, revenue_total):
    """Render the service-utilisation table for a centre's THIS-WEEK column."""
    if not rooms_detail:
        return ""
    rows = []
    for room, d in rooms_detail.items():
        occ = d.get("occupancy_pct")
        avg = d.get("avg_daily") or 0
        cap = d.get("capacity") or 0
        att = round(100.0 * avg / cap, 0) if cap else 0
        children = int(avg) if avg else 0
        # Per-service revenue isn't broken out — leave blank
        rows.append(f"""
        <tr>
          <td style="padding:4px 0;color:{PALETTE['text']}">{room}</td>
          <td style="padding:4px 0;text-align:center">{_occ_chip(occ)}</td>
          <td style="padding:4px 0;text-align:center;color:{PALETTE['text']}">{int(att)}%</td>
          <td style="padding:4px 0;text-align:center;color:{PALETTE['text']}">{children}</td>
        </tr>
        """)
    # Totals
    occ_avg = (
        sum(d.get("occupancy_pct", 0) for d in rooms_detail.values()) / len(rooms_detail)
        if rooms_detail else 0
    )
    return f"""
    <div style="margin-top:12px">
      <div style="font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:{PALETTE['deep']};font-weight:700;margin-bottom:4px">Service Utilisation — This Week</div>
      <table style="width:100%;font-size:11px;border-collapse:collapse">
        <thead><tr style="border-bottom:1px solid {PALETTE['gray_2']}">
          <th style="text-align:left;padding:4px 0;color:{PALETTE['muted']};font-weight:600">SERVICE</th>
          <th style="text-align:center;padding:4px 0;color:{PALETTE['muted']};font-weight:600">OCC %</th>
          <th style="text-align:center;padding:4px 0;color:{PALETTE['muted']};font-weight:600">ATT %</th>
          <th style="text-align:center;padding:4px 0;color:{PALETTE['muted']};font-weight:600">CHILDREN</th>
        </tr></thead>
        <tbody>{"".join(rows)}
          <tr style="border-top:1px solid {PALETTE['gray_2']}">
            <td style="padding:6px 0;font-weight:700">Total</td>
            <td style="padding:6px 0;text-align:center">{_occ_chip(round(occ_avg, 0))}</td>
            <td colspan="2"></td>
          </tr>
        </tbody>
      </table>
    </div>
    """


def _centre_period_card(title, period, data, *, is_actuals, rooms_detail=None,
                       enquiries=None, exits=None, enrolments=None,
                       leave_color=None):
    """Render ONE column (one week) of a centre's row.

    title:       'THIS WEEK — 25-31 May 2026 (Actuals)' etc
    is_actuals:  True for the leftmost column (shows extra rows)
    """
    rev = data.get("revenue")
    roster = data.get("roster_cost")
    leave = data.get("leave_cost")
    wage_inc = data.get("wage_inc_leave_pct")
    wage_exc = data.get("wage_exc_leave_pct")
    occ = data.get("overall_occupancy") if data.get("overall_occupancy") is not None else data.get("Overall")

    leave_text = _fmt_money(leave) if leave is not None and leave > 0 else "$0"
    leave_style = f"color:{PALETTE['warn']};font-weight:600" if leave and leave > 0 else "color:{PALETTE['text']};font-weight:600"

    body = f"""
    <div style="font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:{PALETTE['muted']};font-weight:700;margin-bottom:10px">{title}</div>
    <table style="width:100%;font-size:12px;border-collapse:collapse">
      <tr><td style="padding:5px 0;color:{PALETTE['text']}">Revenue</td><td style="text-align:right;color:{PALETTE['deep']};font-weight:700">{_fmt_money(rev)}</td></tr>
      <tr><td style="padding:5px 0;color:{PALETTE['text']}">Roster Cost</td><td style="text-align:right;font-weight:600">{_fmt_money(roster)}</td></tr>
      <tr><td style="padding:5px 0;color:{PALETTE['text']}">Leave Cost</td><td style="text-align:right;{leave_style}">{leave_text}</td></tr>
      <tr><td style="padding:5px 0;color:{PALETTE['text']}">Overall Occupancy</td><td style="text-align:right">{_occ_chip(occ)}</td></tr>
    </table>
    """

    # Wage bars — actuals shows both inc + exc, projections show inc only
    if is_actuals and wage_exc is not None:
        threshold = 42.0
        ratio_to_thresh = round(100.0 * wage_exc / threshold, 1) if threshold else 0
        under_by = round(threshold - wage_exc, 2)
        healthy = wage_exc < threshold
        helper = (
            f"{wage_exc} / {threshold} × 100 = {ratio_to_thresh}% of threshold. "
            f"{'Under by' if healthy else 'Over by'} {abs(under_by)}pp. "
            f"{'✓ Healthy.' if healthy else '⚠ Breach.'}"
        )
        body += _wage_bar("Wage Exc. Leave", wage_exc,
                          color=PALETTE["ok"] if healthy else PALETTE["risk"],
                          helper_text=helper)
        body += _wage_bar("Wage Inc. Leave", wage_inc,
                          color=PALETTE["purple"],
                          helper_text="No leave this week. Inc. Leave = Exc. Leave." if (leave or 0) == 0 else "")
    else:
        body += _wage_bar("Wage Inc. Leave", wage_inc,
                          color=PALETTE["purple"],
                          helper_text="Inc. Leave shown for reference only.")

    # Service utilisation table REMOVED (Tia direction 08 Jun 2026) —
    # only Enquiries / Exits / Enrolments pills retained below.

    # Status pills at bottom (only on actuals column)
    if is_actuals and any(v is not None for v in (enquiries, exits, enrolments)):
        body += f"""
        <div style="display:flex;gap:6px;margin-top:14px;flex-wrap:wrap">
          <span style="background:{PALETTE['pale']};color:{PALETTE['deep']};padding:4px 10px;border-radius:20px;font-size:11px;font-weight:600">{enquiries or 0} Enquiries</span>
          <span style="background:{PALETTE['risk']}1a;color:{PALETTE['risk']};padding:4px 10px;border-radius:20px;font-size:11px;font-weight:600">{exits or 0} Exits</span>
          <span style="background:{PALETTE['ok']}1a;color:{PALETTE['ok']};padding:4px 10px;border-radius:20px;font-size:11px;font-weight:600">{enrolments or 0} Enrolments</span>
        </div>
        """

    return f"""
    <td style="width:33%;padding:8px;vertical-align:top">
      <div style="background:{PALETTE['white']};border:1px solid {PALETTE['gray_2']};border-radius:8px;padding:16px">
        {body}
      </div>
    </td>
    """


def _section_per_centre(ops):
    centres = ops.get("centres", {}) or {}
    out = []
    period_label = (ops.get("period") or {}).get("label", "—")

    for name, c in centres.items():
        wage_breach = c.get("wage_breach", False)
        risk_rooms = [r for r, d in (c.get("rooms_detail") or {}).items()
                      if d.get("compliance_risk", False)]
        wage_chip = (
            f'<span style="background:{PALETTE["warn"]}26;color:{PALETTE["warn"]};font-size:10px;padding:3px 8px;border-radius:4px;font-weight:700;margin-left:8px">WAGE BREACH</span>'
            if wage_breach else ""
        )
        risk_chip = (
            f'<span style="background:{PALETTE["risk"]}26;color:{PALETTE["risk"]};font-size:10px;padding:3px 8px;border-radius:4px;font-weight:700;margin-left:8px">COMPLIANCE RISK</span>'
            if risk_rooms else ""
        )

        # Actuals: this week from main parser block
        actuals = {
            "revenue":            c.get("revenue"),
            "roster_cost":        c.get("roster_cost"),
            "leave_cost":         c.get("leave_cost"),
            "wage_inc_leave_pct": c.get("wage_inc_leave_pct"),
            "wage_exc_leave_pct": c.get("wage_exc_leave_pct"),
            "Overall":            (c.get("occupancy") or {}).get("Overall"),
        }
        proj_this = c.get("this_week_projection") or {}
        proj_next = c.get("next_week_projection") or {}

        actual_title = f"THIS WEEK — {period_label} (Actuals)"
        proj_this_title = (
            f"NEXT WEEK — projection · {proj_this.get('date')}"
            if proj_this.get("date") else "NEXT WEEK — projection"
        )
        proj_next_title = (
            f"WEEK AFTER — projection · {proj_next.get('date')}"
            if proj_next.get("date") else "WEEK AFTER — projection"
        )

        cells = (
            _centre_period_card(actual_title, period_label, actuals,
                              is_actuals=True,
                              rooms_detail=c.get("rooms_detail"),
                              enquiries=c.get("enquiries"),
                              exits=c.get("exits"),
                              enrolments=c.get("enrolments"))
            + _centre_period_card(proj_this_title, proj_this.get("date"), proj_this,
                                is_actuals=False)
            + _centre_period_card(proj_next_title, proj_next.get("date"), proj_next,
                                is_actuals=False)
        )

        out.append(f"""
        <div style="margin-bottom:24px">
          <div style="font-size:14px;font-weight:700;color:{PALETTE['text_strong']};margin-bottom:10px">
            {name} OSHC/LDC — Centre Performance{wage_chip}{risk_chip}
          </div>
          <table style="width:100%;border-collapse:separate;border-spacing:0;table-layout:fixed">
            <tr>{cells}</tr>
          </table>
        </div>
        """)

    return f"""
    <section style="margin-bottom:24px">
      <h3 style="font-size:14px;font-weight:700;color:{PALETTE['deep']};text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px">Per-Centre Performance — Actuals + 2-Week Projection</h3>
      {"".join(out)}
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
    # Per Kelley rule (09 Jun 2026): risk_rooms is now always [] at the
    # room level (operational rebalance, not compliance). True compliance
    # check is centre-total — TODO: needs licensed_centre_capacity per centre.
    for r in risk_rooms:
        items.append(f'<li style="margin:4px 0"><b style="color:{PALETTE["risk"]}">RISK</b> · {r} <span style="color:{PALETTE["muted"]}">(centre total exceeds licensed — compliance review)</span></li>')
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

    # Section order (per Tia direction 08 Jun 2026):
    #   - Verdict
    #   - Network KPIs + Conversion Story MERGED into one section
    #   - Per-centre 3-column performance
    #   - Marketing performance breakdown
    #   - What's planned next week
    # REMOVED: standalone funnel section (merged into Network KPIs)
    # REMOVED: standalone Network KPIs section (merged into one with funnel)
    # REMOVED: Compliance & Risk panel section (centre-level chips remain)
    sections = [
        _section_verdict(ops, ga4, meta, ads, date_str),
        _section_network_kpis_combined(ops, ga4, funnel),
        _section_per_centre(ops),
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
  <div style="text-align:center;padding:20px 0;margin-top:20px;border-top:1px solid {PALETTE['gray_2']}">
    <a href="https://cb247agent.github.io/cb_claude/" style="display:inline-block;background:{PALETTE['purple']};color:#fff;padding:10px 22px;border-radius:4px;text-decoration:none;font-weight:700;font-size:13px;margin:0 4px 4px">Open Marketing Dashboard</a>
    <a href="https://myworldcc.netlify.app" style="display:inline-block;background:#01696f;color:#fff;padding:10px 22px;border-radius:4px;text-decoration:none;font-weight:700;font-size:13px;margin:0 4px 4px">Open Operations Report</a>
  </div>
  <div class="footer">
    Generated {_dt.datetime.now().strftime("%a %d %b %Y %H:%M %Z")} ·
    Recipients: Robert · Denver · Kelley · Jordan · Dana ·
    For internal use only — do not forward
  </div>
</div>
</body>
</html>"""


def main() -> int:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    today = _dt.date.today().strftime("%Y-%m-%d")
    raw_html = build_html(today)
    # Minify so Gmail doesn't clip the email body (102 KB threshold).
    html = _minify_html(raw_html)
    out_path = OUTPUTS_DIR / f"management-report-{today}.html"
    out_path.write_text(html, encoding="utf-8")
    raw_kb  = len(raw_html.encode("utf-8")) // 1024
    size_kb = out_path.stat().st_size // 1024
    print(f"[mwcc-mgmt-report] ✅ Wrote {out_path.relative_to(BASE_DIR)} ({size_kb} KB · minified from {raw_kb} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
