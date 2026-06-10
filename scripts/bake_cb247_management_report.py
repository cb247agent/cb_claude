"""
bake_cb247_management_report.py — Generate the weekly CB247 management report.

This is the CB247 mirror of bake_mwcc_management_report.py. Produces a
single-page HTML executive summary intended for Tia (OS Owner) only —
sender for now is tia@chasingbetter.com.au, no other recipients.

Output: outputs/reports/cb247-management-report-{YYYY-MM-DD}.html

Inputs (all from state/, produced earlier in the same cron run or
parsed manually from cb247-membership-inbox/):
    state/membership-data.json   — PGM contracts + CleverWaiver + promo tracking
    state/ads-data.json          — Google Ads weekly summary
    state/metricool-data.json    — Organic social PDF parse
    state/ahrefs-data.json       — SEO domain rating, organic value

Prominent section: external links to estimated weekly revenue + wages
per location (Netlify-hosted dashboards):
    https://cb247-weekly-revenue-malaga.netlify.app
    https://cb247-weekly-revenue-ellenbrook.netlify.app

Run:
    python scripts/bake_cb247_management_report.py
    python scripts/send_cb247_management_report.py
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

BASE_DIR    = Path(__file__).resolve().parent.parent
STATE_DIR   = BASE_DIR / "state"
OUTPUTS_DIR = BASE_DIR / "outputs" / "reports"

# ── CB247 brand palette (teal accent, per context/design-standards.md) ──
PALETTE = {
    "teal":        "#3FA69A",
    "teal_deep":   "#2d7d72",
    "teal_pale":   "#e8f5f4",
    "teal_mist":   "#f3faf9",
    "risk":        "#dc2626",
    "warn":        "#f59e0b",
    "ok":          "#16a34a",
    "text":        "#1a1a1a",
    "text_strong": "#0d0d0d",
    "text_2":      "#4b5563",
    "muted":       "#6b7280",
    "white":       "#ffffff",
    "gray_0":      "#f9fafb",
    "gray_1":      "#f3f4f6",
    "gray_2":      "#e5e7eb",
    "gray_3":      "#d1d5db",
}

# Revenue + wages dashboard URLs (external, Tia's Netlify deploys)
REVENUE_LINKS = {
    "Malaga":     "https://cb247-weekly-revenue-malaga.netlify.app",
    "Ellenbrook": "https://cb247-weekly-revenue-ellenbrook.netlify.app",
}


def _load(name: str, default=None):
    p = STATE_DIR / name
    if not p.exists():
        return default if default is not None else {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return default if default is not None else {}


def _fmt_n(n, default="—"):
    if n is None:
        return default
    try:
        return f"{int(n):,}"
    except (ValueError, TypeError):
        return str(n)


def _fmt_pct(n, default="—"):
    if n is None:
        return default
    try:
        return f"{float(n):+.1f}%"
    except (ValueError, TypeError):
        return default


def _fmt_dollars(n, default="—"):
    if n is None:
        return default
    try:
        return f"${int(n):,}"
    except (ValueError, TypeError):
        return default


def build_report() -> str:
    P = PALETTE
    today = _dt.date.today().strftime("%Y-%m-%d")
    today_long = _dt.date.today().strftime("%a %d %b %Y")

    # ── Pull data ────────────────────────────────────────────────────────
    membership = _load("membership-data.json")
    ads = _load("ads-data.json")
    metricool = _load("metricool-data.json")
    ahrefs = _load("ahrefs-data.json")

    # Period (from membership data — authoritative source)
    period_obj = (membership.get("summary") or {}).get("period") or {}
    period_raw = period_obj.get("raw") or "—"
    period_start = period_obj.get("start") or ""
    period_end = period_obj.get("end") or ""

    # Membership KPIs
    s = membership.get("summary") or {}
    t = s.get("totals") or {}
    ub = s.get("unique_base") or {}
    cw = membership.get("cleverwaiver") or {}
    pc = s.get("per_club") or {}
    ctx = membership.get("contracts") or {}
    submTruth = membership.get("submitted_cancellation_truth") or {}
    promo_tracking = membership.get("promo_tracking") or {}

    new_ppl    = (ub.get("new") or {}).get("Total", 0) or 0
    new_mal    = (ub.get("new") or {}).get("Malaga", 0) or 0
    new_ell    = (ub.get("new") or {}).get("Ellenbrook", 0) or 0
    subm_ppl   = (submTruth.get("by_club") or {}).get("Total") or 0
    subm_mal   = (submTruth.get("by_club") or {}).get("Malaga") or 0
    subm_ell   = (submTruth.get("by_club") or {}).get("Ellenbrook") or 0
    future_ppl = (ub.get("future") or {}).get("Total", 0) or 0
    future_mal = (ub.get("future") or {}).get("Malaga", 0) or 0
    future_ell = (ub.get("future") or {}).get("Ellenbrook", 0) or 0
    net_ppl    = new_ppl - subm_ppl
    net_mal    = new_mal - subm_mal
    net_ell    = new_ell - subm_ell

    new_contracts   = t.get("NewContracts") or 0
    ended_contracts = t.get("EndedContracts") or 0
    active_base     = ctx.get("total_active_base_combined") or 0
    capture_pct     = (submTruth.get("capture_rate_pct") or {}).get("Total")

    # Top cancellation reason
    reasons = cw.get("reasons") or {}
    top_reason, top_reason_count = (None, 0)
    if reasons:
        top_reason, top_reason_count = list(reasons.items())[0]
    top_reason_pct = round(top_reason_count / (cw.get("total_responses") or 1) * 100) if top_reason_count else 0

    # Marketing — Google Ads
    gads_weeks = ads.get("google_ads") or []
    gads_this = (gads_weeks[0] if gads_weeks else {}).get("combined") or {}
    gads_spend = gads_this.get("spend") or 0
    gads_conv = gads_this.get("conv") or 0
    gads_cpa = gads_this.get("cpa") or 0
    gads_clicks = gads_this.get("clicks") or 0

    # SEO
    ahrefs_dr = ahrefs.get("domain_rating") or "—"
    ahrefs_kw_total = ahrefs.get("organic_keywords_total") or "—"
    ahrefs_top3 = ahrefs.get("top_3_keywords") or "—"
    ahrefs_traffic_value = ahrefs.get("organic_traffic_value") or 0
    ahrefs_value_per_week = round(ahrefs_traffic_value / 4.3) if ahrefs_traffic_value else 0

    # Social
    mc_ig = metricool.get("ig") or {}
    mc_fb = metricool.get("fb") or {}
    mc_gbp = metricool.get("gbp") or {}
    ig_followers = mc_ig.get("followers") or 0
    fb_followers = mc_fb.get("followers") or 0
    ig_reels = mc_ig.get("reels_published") or 0
    ig_stories_impr = mc_ig.get("stories_impressions") or 0

    # GBP combined
    mal_gbp = mc_gbp.get("malaga_perf") or {}
    ell_gbp = mc_gbp.get("ellenbrook_perf") or {}
    gbp_actions = (mal_gbp.get("total_actions") or 0) + (ell_gbp.get("total_actions") or 0)
    gbp_reach = (mal_gbp.get("reach_total") or 0) + (ell_gbp.get("reach_total") or 0)

    # ── Verdict heuristic ────────────────────────────────────────────────
    verdict_tone = "ok"
    if net_ppl < 0:
        verdict_tone = "risk"
        verdict_headline = f"Net negative {net_ppl} people · save-call programme is the priority"
    elif future_ppl > (new_ppl * 2.5 if new_ppl else 200):
        verdict_tone = "warn"
        verdict_headline = f"Future-cancel pipeline ({future_ppl}) is {round(future_ppl/(new_ppl or 1),1)}× new joins · save calls drive next week's net"
    else:
        verdict_tone = "ok"
        verdict_headline = f"Net positive +{net_ppl} people · sustain save-call cadence into next week"

    # Promo summary
    promo_summary = ""
    for promo_key, promo in promo_tracking.items():
        p_new = (promo.get("new_this_week") or {}).get("Total") or 0
        p_active = (promo.get("active") or {}).get("Total") or 0
        share = round(p_new / new_ppl * 100) if new_ppl else 0
        promo_summary = (
            f"<b>{promo.get('label', promo_key)}</b> · "
            f"{p_active} active · {p_new} new this week ({share}% of new joins)"
        )
        break  # Show only the first active promo in the headline

    # ── Build HTML ────────────────────────────────────────────────────────
    verdict_grad = f"linear-gradient(135deg,{P['teal_deep']} 0%,{P['teal']} 100%)"

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>CB247 Management Report · {period_raw}</title>
<style>
body {{ margin:0;font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",sans-serif;background:{P['gray_0']};color:{P['text']};line-height:1.5; }}
.wrap {{ max-width:920px;margin:0 auto;padding:24px 20px 40px; }}
.head {{ background:{P['white']};border-radius:10px;padding:18px 22px;margin-bottom:20px;border:1px solid {P['gray_2']};position:relative }}
.head h1 {{ font-size:20px;font-weight:700;color:{P['teal_deep']};letter-spacing:-0.01em;margin:0 }}
.head p {{ font-size:11px;color:{P['muted']};margin:4px 0 0 }}
.head-badge {{ position:absolute;top:14px;right:18px;background:{P['teal_deep']};color:{P['white']};padding:4px 10px;border-radius:4px;font-size:9px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;box-shadow:0 1px 3px rgba(0,0,0,.08) }}
.card {{ background:{P['white']};border:1px solid {P['gray_2']};border-radius:8px;padding:18px 20px;margin-bottom:14px }}
.section-label {{ font-size:10px;letter-spacing:.08em;text-transform:uppercase;font-weight:700;color:{P['muted']};margin-bottom:10px }}
.kpi-grid {{ display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px }}
.kpi {{ background:{P['white']};border:1px solid {P['gray_2']};border-radius:6px;padding:12px 14px }}
.kpi-label {{ font-size:9.5px;letter-spacing:.06em;text-transform:uppercase;color:{P['muted']};font-weight:600 }}
.kpi-value {{ font-size:22px;font-weight:700;color:{P['text_strong']};margin:4px 0 2px }}
.kpi-sub {{ font-size:10.5px;color:{P['muted']} }}
.kpi.good .kpi-value {{ color:{P['ok']} }}
.kpi.bad .kpi-value {{ color:{P['risk']} }}
.kpi.warn .kpi-value {{ color:{P['warn']} }}
table {{ width:100%;border-collapse:collapse;font-size:12px;margin-top:4px }}
th,td {{ text-align:left;padding:8px 10px;border-bottom:1px solid {P['gray_1']} }}
th {{ font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:{P['muted']};font-weight:600;background:{P['gray_0']} }}
td.num {{ text-align:right;font-variant-numeric:tabular-nums;font-feature-settings:"tnum" }}
.footer {{ font-size:10px;color:{P['muted']};text-align:center;margin-top:30px;padding-top:14px;border-top:1px solid {P['gray_2']} }}
.link-card {{ display:block;background:{P['white']};border:1px solid {P['teal']};border-left:4px solid {P['teal']};border-radius:8px;padding:14px 18px;text-decoration:none;color:{P['text']};margin-bottom:10px;transition:background .15s }}
.link-card:hover {{ background:{P['teal_mist']} }}
.link-card-loc {{ font-size:14px;font-weight:700;color:{P['teal_deep']};margin-bottom:2px }}
.link-card-desc {{ font-size:11px;color:{P['muted']} }}
.link-card-url {{ font-size:10.5px;color:{P['teal']};font-family:Menlo,Monaco,monospace;margin-top:4px }}
@media print {{ body {{ background:white }} .head-badge {{ display:none }} }}
</style>
</head>
<body>
<div class="wrap">

  <div class="head">
    <div class="head-badge">Confidential · Owner</div>
    <h1>CB247 Management Report</h1>
    <p>{period_raw} · ChasingBetter247 · Malaga + Ellenbrook</p>
  </div>

  <!-- Verdict of the week -->
  <section style="background:{verdict_grad};color:#fff;padding:24px 28px;border-radius:12px;margin-bottom:20px">
    <div style="font-size:10px;letter-spacing:.08em;text-transform:uppercase;opacity:.75;font-weight:600">Verdict of the week · {period_raw}</div>
    <h2 style="font-size:18px;font-weight:700;margin:6px 0 12px;line-height:1.35">{verdict_headline}</h2>
    {f'<div style="font-size:13px;opacity:.92;line-height:1.6">{promo_summary}</div>' if promo_summary else ''}
  </section>

  <!-- Estimated weekly revenue + wages — PROMINENT external dashboards -->
  <div class="card" style="background:{P['teal_mist']};border-color:{P['teal']}">
    <div class="section-label" style="color:{P['teal_deep']}">Estimated Weekly Revenue + Wages — Per Location</div>
    <p style="font-size:12px;color:{P['text_2']};margin:0 0 14px">
      Live revenue + wage cost dashboards (external). Open in browser for the up-to-date figure with WoW deltas.
    </p>
    <a class="link-card" href="{REVENUE_LINKS['Malaga']}" target="_blank" rel="noopener">
      <div class="link-card-loc">Malaga</div>
      <div class="link-card-desc">Estimated weekly revenue and wages — Malaga club</div>
      <div class="link-card-url">{REVENUE_LINKS['Malaga']}</div>
    </a>
    <a class="link-card" href="{REVENUE_LINKS['Ellenbrook']}" target="_blank" rel="noopener">
      <div class="link-card-loc">Ellenbrook</div>
      <div class="link-card-desc">Estimated weekly revenue and wages — Ellenbrook club</div>
      <div class="link-card-url">{REVENUE_LINKS['Ellenbrook']}</div>
    </a>
  </div>

  <!-- Headline KPIs -->
  <div class="card">
    <div class="section-label">Membership · This Week</div>
    <div class="kpi-grid">
      <div class="kpi {'good' if net_ppl >= 0 else 'bad'}">
        <div class="kpi-label">New People</div>
        <div class="kpi-value">{_fmt_n(new_ppl)}</div>
        <div class="kpi-sub">Mal {_fmt_n(new_mal)} · Ell {_fmt_n(new_ell)} · {_fmt_n(new_contracts)} contracts</div>
      </div>
      <div class="kpi bad">
        <div class="kpi-label">Submitted Cancels</div>
        <div class="kpi-value">{_fmt_n(subm_ppl)}</div>
        <div class="kpi-sub">Mal {_fmt_n(subm_mal)} · Ell {_fmt_n(subm_ell)} · CleverWaiver source</div>
      </div>
      <div class="kpi {'good' if net_ppl >= 0 else 'bad'}">
        <div class="kpi-label">Net Movement</div>
        <div class="kpi-value">{'+' if net_ppl >= 0 else ''}{_fmt_n(net_ppl)}</div>
        <div class="kpi-sub">Mal {'+' if net_mal>=0 else ''}{_fmt_n(net_mal)} · Ell {'+' if net_ell>=0 else ''}{_fmt_n(net_ell)}</div>
      </div>
      <div class="kpi {'warn' if future_ppl > new_ppl * 2 else ''}">
        <div class="kpi-label">Future-Cancel Pipeline</div>
        <div class="kpi-value">{_fmt_n(future_ppl)}</div>
        <div class="kpi-sub">Mal {_fmt_n(future_mal)} · Ell {_fmt_n(future_ell)} · save-call target</div>
      </div>
    </div>
    <p style="font-size:11px;color:{P['muted']};margin:6px 0 0">
      Active base: <b>{_fmt_n(active_base)}</b> members (Live status, base contracts only, deduped by user).
      Exit-survey capture: <b>{_fmt_pct(capture_pct) if capture_pct else '—'}</b> (target ≥70%, source CleverWaiver / PGM).
    </p>
  </div>

  <!-- Promo tracking -->
  {''.join(_render_promo_card(pk, p, new_ppl, period_end, P) for pk, p in promo_tracking.items())}

  <!-- Cancellation reasons -->
  {f'''<div class="card">
    <div class="section-label">Top Cancellation Reason</div>
    <p style="font-size:13px;margin:0 0 10px">
      <b style="color:{P['risk']}">"{top_reason}"</b> · {top_reason_count} of {cw.get('total_responses', 0)} responses
      ({top_reason_pct}% of cancellations)
    </p>
    <p style="font-size:11px;color:{P['muted']};margin:0">
      Save-call playbook should lead with this objection. Save-team should action the
      future-cancel pipeline within 48 hours of contract entry.
    </p>
  </div>''' if top_reason else ''}

  <!-- Marketing performance -->
  <div class="card">
    <div class="section-label">Marketing · This Week</div>
    <table>
      <thead><tr><th>Channel</th><th class="num">Headline</th><th>Read</th></tr></thead>
      <tbody>
        <tr>
          <td><b>Google Ads</b></td>
          <td class="num"><b>{_fmt_dollars(gads_spend)}</b> · {_fmt_n(gads_conv)} conv · {_fmt_dollars(gads_cpa)} CPA</td>
          <td style="font-size:11px;color:{P['muted']}">{_fmt_n(gads_clicks)} clicks combined</td>
        </tr>
        <tr>
          <td><b>SEO (Ahrefs)</b></td>
          <td class="num"><b>{ahrefs_kw_total} keywords</b> · {ahrefs_top3} top-3 · DR {ahrefs_dr}</td>
          <td style="font-size:11px;color:{P['muted']}">Organic value ≈ {_fmt_dollars(ahrefs_value_per_week)}/wk</td>
        </tr>
        <tr>
          <td><b>Instagram</b></td>
          <td class="num"><b>{_fmt_n(ig_followers)} followers</b> · {_fmt_n(ig_reels)} reels · {_fmt_n(ig_stories_impr)} story impr</td>
          <td style="font-size:11px;color:{P['muted']}">@chasingbetter247 organic</td>
        </tr>
        <tr>
          <td><b>Facebook</b></td>
          <td class="num"><b>{_fmt_n(fb_followers)} followers</b></td>
          <td style="font-size:11px;color:{P['muted']}">GBP signal only · de-prioritised</td>
        </tr>
        <tr>
          <td><b>Google Business Profile</b></td>
          <td class="num"><b>{_fmt_n(gbp_actions)} actions</b> · {_fmt_n(gbp_reach)} reach</td>
          <td style="font-size:11px;color:{P['muted']}">Malaga + Ellenbrook combined</td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- Per-club scorecard -->
  <div class="card">
    <div class="section-label">Per-Club Scorecard · People-Based</div>
    <table>
      <thead><tr><th>Club</th><th class="num">New</th><th class="num">Submitted Cancel</th><th class="num">Net</th><th class="num">Future Pipeline</th></tr></thead>
      <tbody>
        <tr>
          <td><b>Malaga</b></td>
          <td class="num">{_fmt_n(new_mal)}</td>
          <td class="num" style="color:{P['risk']}">{_fmt_n(subm_mal)}</td>
          <td class="num" style="color:{P['ok'] if net_mal>=0 else P['risk']};font-weight:700">{'+' if net_mal>=0 else ''}{_fmt_n(net_mal)}</td>
          <td class="num">{_fmt_n(future_mal)}</td>
        </tr>
        <tr>
          <td><b>Ellenbrook</b></td>
          <td class="num">{_fmt_n(new_ell)}</td>
          <td class="num" style="color:{P['risk']}">{_fmt_n(subm_ell)}</td>
          <td class="num" style="color:{P['ok'] if net_ell>=0 else P['risk']};font-weight:700">{'+' if net_ell>=0 else ''}{_fmt_n(net_ell)}</td>
          <td class="num">{_fmt_n(future_ell)}</td>
        </tr>
        <tr style="font-weight:700;background:{P['gray_0']}">
          <td>Total</td>
          <td class="num">{_fmt_n(new_ppl)}</td>
          <td class="num" style="color:{P['risk']}">{_fmt_n(subm_ppl)}</td>
          <td class="num" style="color:{P['ok'] if net_ppl>=0 else P['risk']}">{'+' if net_ppl>=0 else ''}{_fmt_n(net_ppl)}</td>
          <td class="num">{_fmt_n(future_ppl)}</td>
        </tr>
      </tbody>
    </table>
  </div>

  <div class="footer">
    Generated {today_long} · auto-baked from PGM + CleverWaiver + Google Ads + Ahrefs + Metricool
    <br>Full live dashboard: <a href="https://cb247agent.github.io/cb_claude/" style="color:{P['teal_deep']}">cb247agent.github.io/cb_claude</a>
    · This report: <code style="font-family:Menlo,Monaco,monospace;font-size:10px">outputs/reports/cb247-management-report-{today}.html</code>
  </div>

</div>
</body></html>
"""
    return html


def _render_promo_card(promo_key: str, promo: dict, new_ppl: int, period_end: str, P: dict) -> str:
    """Render the active promo card."""
    p_new = (promo.get("new_this_week") or {}).get("Total") or 0
    p_active = (promo.get("active") or {}).get("Total") or 0
    p_new_mal = (promo.get("new_this_week") or {}).get("Malaga") or 0
    p_new_ell = (promo.get("new_this_week") or {}).get("Ellenbrook") or 0
    started = promo.get("started") or ""
    share = round(p_new / new_ppl * 100) if new_ppl else 0

    days_running = "—"
    if started and period_end:
        try:
            s_dt = _dt.date.fromisoformat(started)
            e_dt = _dt.date.fromisoformat(period_end)
            days = (e_dt - s_dt).days + 1
            if days >= 1:
                days_running = f"{days} day{'s' if days != 1 else ''}"
        except Exception:
            pass

    return f"""
  <div class="card">
    <div class="section-label">Active Promo Tracking</div>
    <p style="font-size:14px;font-weight:700;margin:0 0 6px;color:{P['text_strong']}">{promo.get('label', promo_key)}</p>
    <p style="font-size:11px;color:{P['muted']};margin:0 0 12px">
      Started {started} · running {days_running} ({started} → {period_end})
    </p>
    <div class="kpi-grid">
      <div class="kpi good"><div class="kpi-label">Active on Promo</div><div class="kpi-value">{p_active}</div><div class="kpi-sub">currently paying</div></div>
      <div class="kpi"><div class="kpi-label">New This Week</div><div class="kpi-value">{p_new}</div><div class="kpi-sub">Mal {p_new_mal} · Ell {p_new_ell}</div></div>
      <div class="kpi {'good' if share>=30 else 'warn' if share>=15 else ''}"><div class="kpi-label">Share of New Joins</div><div class="kpi-value">{share}%</div><div class="kpi-sub">{p_new} of {new_ppl} new people</div></div>
      <div class="kpi"><div class="kpi-label">Days Running</div><div class="kpi-value">{days_running.split()[0] if days_running != '—' else '—'}</div><div class="kpi-sub">within data window</div></div>
    </div>
  </div>"""


def main() -> int:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    html = build_report()
    today = _dt.date.today().strftime("%Y-%m-%d")
    out_path = OUTPUTS_DIR / f"cb247-management-report-{today}.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"[cb247-mgmt-report] ✅ Written → {out_path.relative_to(BASE_DIR)}")
    print(f"                       Size: {len(html):,} chars")
    return 0


if __name__ == "__main__":
    sys.exit(main())
