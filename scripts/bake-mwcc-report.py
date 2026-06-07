"""
bake-mwcc-report.py — Generates the MWCC weekly marketing HTML report.

Reads from state/:
  mwcc-ga4.json          → Website tab + overall users
  mwcc-ads.json          → Google Ads tab
  mwcc-ads-history.json  → Google Ads WoW comparisons
  mwcc-meta.json         → Meta Ads tab
  mwcc-meta-history.json → Meta Ads WoW comparisons
  mwcc-ops.json          → Centre Occupancy tab

Output: outputs/reports/mwcc/mwcc-marketing-YYYY-MM-DD.html

Run: python scripts/bake-mwcc-report.py
"""

import json
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR   = Path(__file__).resolve().parent.parent
STATE_DIR  = BASE_DIR / "state"
OUTPUT_DIR = BASE_DIR / "outputs" / "reports" / "mwcc"
DOCS_DIR   = BASE_DIR / "docs"           # GitHub Pages root
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BRAND_COLOR = "#01696f"
WAGE_BREACH = 42.0


# ─────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────

def _load(filename, default=None):
    path = STATE_DIR / filename
    if not path.exists():
        return default or {}
    try:
        return json.loads(path.read_text())
    except Exception as e:
        print(f"[Baker] ⚠️  Could not load {filename}: {e}")
        return default or {}


# ─────────────────────────────────────────────────────────────────
# HTML helpers
# ─────────────────────────────────────────────────────────────────

def _f(v, decimals=2):
    """Safe float."""
    try: return round(float(v or 0), decimals)
    except: return 0.0

def _i(v):
    """Safe int."""
    try: return int(float(v or 0))
    except: return 0

def _money(v):
    return f"${_f(v):,.2f}"

def _pct(v):
    return f"{_f(v):.2f}%"

def _num(v):
    n = _i(v)
    return f"{n:,}"

def _wow(curr, prev, invert=False, fmt="pct"):
    """Generate WoW HTML span. invert=True means lower is better (e.g. CPC)."""
    try:
        c, p = float(curr or 0), float(prev or 0)
        if p == 0:
            return '<span class="kpi-fl">—</span>'
        pct = (c - p) / abs(p) * 100
        up  = pct >= 0
        if invert:
            up = not up
        cls   = "kpi-up" if up else "kpi-dn"
        arrow = "↑" if pct >= 0 else "↓"
        return f'<span class="{cls}">{arrow} {abs(pct):.1f}%</span>'
    except:
        return '<span class="kpi-fl">—</span>'

def _badge(text, colour="teal"):
    cls_map = {
        "green": "b-green", "red": "b-red", "amber": "b-amber",
        "blue":  "b-blue",  "teal": "b-teal", "grey": "b-grey",
    }
    cls = cls_map.get(colour, "b-grey")
    return f'<span class="badge {cls}">{text}</span>'

def _occ_badge(pct):
    p = _f(pct)
    if p > 100:  return _badge("Compliance Risk", "red")
    if p >= 80:  return _badge("Strong", "green")
    if p >= 60:  return _badge("Healthy", "green")
    if p >= 40:  return _badge("Growing", "blue")
    if p >= 20:  return _badge("Underused", "amber")
    return _badge("Critical", "red")

def _freq_badge(freq):
    f = _f(freq)
    if f >= 3.0:  return _badge("Saturated", "red")
    if f >= 2.5:  return _badge("High freq", "red")
    if f >= 2.0:  return _badge("Rising", "amber")
    if f >= 1.5:  return _badge("Normal", "blue")
    return _badge("Fresh audience", "green")

def _dur_fmt(seconds):
    s = _i(seconds)
    m, sec = divmod(s, 60)
    return f"{m}:{sec:02d}"


# ─────────────────────────────────────────────────────────────────
# CSS + page shell
# ─────────────────────────────────────────────────────────────────

def _css():
    return """<style>
:root{--primary:#01696f;--success:#437a22;--warn:#d19900;--danger:#b91c1c;
--bg:#f7f6f2;--card:#ffffff;--border:#e2e0da;--text:#1a1a18;--muted:#6b6b65;
--font:'Inter',sans-serif}
[data-theme="dark"]{--bg:#0f1110;--card:#1a1e1d;--border:#2a302e;--text:#e8e6e0;--muted:#8a8a82}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:var(--font);background:var(--bg);color:var(--text);font-size:14px;line-height:1.6}
a{color:var(--primary)}
.topbar{background:var(--primary);color:#fff;display:flex;align-items:center;
justify-content:space-between;padding:20px 28px;position:sticky;top:0;z-index:100}
.topbar-title{font-size:1rem;font-weight:700;letter-spacing:.01em}
.dark-toggle{background:rgba(255,255,255,.15);border:none;color:#fff;padding:4px 14px;
border-radius:20px;cursor:pointer;font-family:var(--font);font-size:12px}
.tab-nav{display:flex;gap:2px;background:var(--card);border-bottom:2px solid var(--border);
padding:0 28px;overflow-x:auto}
.tab-btn{padding:10px 18px;border:none;background:none;color:var(--muted);cursor:pointer;
font-family:var(--font);font-size:13px;font-weight:500;white-space:nowrap;
border-bottom:2px solid transparent;margin-bottom:-2px;transition:all .2s}
.tab-btn:hover{color:var(--primary)}
.tab-btn.active{color:var(--primary);border-bottom-color:var(--primary);font-weight:700}
.tab-panel{display:none;padding:28px}.tab-panel.active{display:block}
.hero{background:linear-gradient(135deg,var(--primary) 0%,#014d51 100%);color:#fff;
border-radius:14px;padding:24px 28px;margin-bottom:24px;display:flex;
justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:16px}
.hero h1{font-size:1.5rem;font-weight:700;margin-bottom:4px}
.hero p{font-size:12px;opacity:.85}
.hero-right{text-align:right;font-size:12px;opacity:.85}
.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:24px}
.kpi-grid-3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:24px}
.kpi-grid-5{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:24px}
@media(max-width:900px){.kpi-grid,.kpi-grid-3,.kpi-grid-5{grid-template-columns:repeat(2,1fr)}}
@media(max-width:560px){.kpi-grid,.kpi-grid-3,.kpi-grid-5{grid-template-columns:1fr}}
.kpi-card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:16px 18px}
.kpi-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;
color:var(--muted);margin-bottom:4px}
.kpi-value{font-size:2rem;font-weight:700;color:var(--primary);line-height:1.1;margin-bottom:4px}
.kpi-sub{font-size:11px;color:var(--muted)}
.kpi-up{color:var(--success);font-weight:600}
.kpi-dn{color:var(--danger);font-weight:600}
.kpi-fl{color:var(--muted)}
.badge{display:inline-block;border-radius:5px;padding:2px 9px;font-size:11px;
font-weight:700;white-space:nowrap}
.b-green{background:#d5ecc2;color:#437a22}.b-amber{background:#fef3cc;color:#d19900}
.b-red{background:#fee2e2;color:#b91c1c}.b-blue{background:#dbeafe;color:#1d4ed8}
.b-teal{background:#ccf0ef;color:#01696f}.b-grey{background:#f0efeb;color:#6b6b65}
.section-title{font-size:1rem;font-weight:700;color:var(--text);margin-bottom:14px;margin-top:4px}
.card{background:var(--card);border:1px solid var(--border);border-radius:10px;
padding:18px;margin-bottom:20px}
.card-title{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;
color:var(--muted);margin-bottom:12px}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px}
@media(max-width:800px){.two-col{grid-template-columns:1fr}}
.tbl{width:100%;border-collapse:collapse;font-size:12px}
.tbl th{background:var(--bg);color:var(--muted);font-weight:700;text-transform:uppercase;
font-size:10px;letter-spacing:.06em;padding:8px 10px;border-bottom:2px solid var(--border);
text-align:left;white-space:nowrap}
.tbl td{padding:8px 10px;border-bottom:1px solid var(--border);vertical-align:middle}
.tbl tr:last-child td{border-bottom:none}
.tbl tr:hover td{background:var(--bg)}
.tbl-total td{font-weight:700;border-top:2px solid var(--border)}
.bm-row{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px}
.bm-cell{flex:1;min-width:100px;background:var(--card);border:1px solid var(--border);
border-radius:8px;padding:10px 12px;text-align:center}
.bm-metric{font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;
letter-spacing:.06em;margin-bottom:4px}
.bm-actual{font-size:1.3rem;font-weight:700;margin-bottom:2px}
.bm-verdict{font-size:11px;font-weight:600}
.v-exc{color:var(--success)}.v-good{color:#3b82f6}.v-avg{color:var(--warn)}.v-poor{color:var(--danger)}
.funnel{display:flex;gap:0;margin-bottom:20px;border-radius:10px;overflow:hidden;
border:1px solid var(--border)}
.funnel-step{flex:1;padding:14px 12px;text-align:center;border-right:1px solid var(--border);
background:var(--card)}
.funnel-step:last-child{border-right:none}
.funnel-val{font-size:1.4rem;font-weight:700;color:var(--primary)}
.funnel-lbl{font-size:10px;color:var(--muted);font-weight:600;text-transform:uppercase;
letter-spacing:.05em;margin-top:2px}
.funnel-sub{font-size:11px;color:var(--muted);margin-top:2px}
@media(max-width:700px){.funnel{flex-direction:column}
.funnel-step{border-right:none;border-bottom:1px solid var(--border)}}
.insight-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px;margin-bottom:20px}
@media(max-width:700px){.insight-grid{grid-template-columns:1fr}}
.insight-card{border-radius:10px;padding:16px;border-left:4px solid}
.ic-green{background:#f0faf0;border-color:var(--success)}
.ic-red{background:#fff5f5;border-color:var(--danger)}
.ic-amber{background:#fffbeb;border-color:var(--warn)}
.ic-blue{background:#f0f7ff;border-color:#3b82f6}
[data-theme="dark"] .ic-green{background:#1a2a1a}
[data-theme="dark"] .ic-red{background:#2a1a1a}
[data-theme="dark"] .ic-amber{background:#2a2510}
[data-theme="dark"] .ic-blue{background:#0d1f30}
.ic-title{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;margin-bottom:8px}
.ic-green .ic-title{color:var(--success)}.ic-red .ic-title{color:var(--danger)}
.ic-amber .ic-title{color:var(--warn)}.ic-blue .ic-title{color:#3b82f6}
.bullets{list-style:none;padding:0}
.bullets li{padding:3px 0 3px 14px;font-size:12px;position:relative}
.bullets li::before{content:"▸";position:absolute;left:0;opacity:.55}
.ch-table{width:100%;border-collapse:collapse;font-size:12px}
.ch-table th{background:var(--bg);color:var(--muted);font-weight:700;text-transform:uppercase;
font-size:10px;letter-spacing:.06em;padding:10px 12px;border-bottom:2px solid var(--border);
text-align:left;white-space:nowrap}
.ch-table td{padding:10px 12px;border-bottom:1px solid var(--border);vertical-align:middle}
.ch-table tr:last-child td{border-bottom:none}
.ch-table tr:hover td{background:var(--bg)}
.na-box{background:var(--bg);border:2px dashed var(--border);border-radius:10px;
padding:32px;text-align:center;color:var(--muted);margin-bottom:20px}
.na-box strong{display:block;margin-bottom:6px;font-size:14px;color:var(--text)}
</style>"""


# ─────────────────────────────────────────────────────────────────
# TAB 1 — Executive Summary
# ─────────────────────────────────────────────────────────────────

def _tab_summary(ga4, ads, meta, ops, ads_hist, meta_hist):
    ga4_curr = ga4.get("current", {})
    ga4_prev = ga4.get("previous", {})
    ads_tot  = ads.get("totals", {})
    meta_sum = meta.get("summary", {})
    net_sum  = ops.get("network_summary", {})
    period   = ops.get("period", {})
    dr       = ga4.get("date_range", ads.get("date_range", {}))

    # Previous week totals for WoW
    ads_prev = ads_hist[1].get("totals", {}) if len(ads_hist) > 1 else {}
    meta_prev = meta_hist[1].get("summary", {}) if len(meta_hist) > 1 else {}

    total_spend  = _f(ads_tot.get("spend", 0)) + _f(meta_sum.get("spend", 0))
    google_conv  = _f(ads_tot.get("conversions", 0))
    active_users = _i(ga4_curr.get("active_users", 0))
    net_movement = _i(net_sum.get("net_movement", 0))
    enrolments   = _i(net_sum.get("total_enrolments", 0))
    exits        = _i(net_sum.get("total_exits", 0))
    enquiries    = _i(net_sum.get("total_enquiries", 0))

    prev_active_users = _i(ga4_prev.get("active_users", 0))
    wow_users   = _wow(active_users, prev_active_users)
    wow_conv    = _wow(google_conv, _f(ads_prev.get("conversions", 0)))
    wow_spend   = _wow(total_spend, _f(ads_prev.get("spend", 0)) + _f(meta_prev.get("spend", 0)))

    # Period label
    start_str = dr.get("start", period.get("start", ""))
    end_str   = dr.get("end",   period.get("end",   ""))
    try:
        s = datetime.strptime(start_str, "%Y-%m-%d")
        e = datetime.strptime(end_str,   "%Y-%m-%d")
        period_label = f"{s.strftime('%-d %b')}–{e.strftime('%-d %b %Y')}"
    except:
        period_label = f"{start_str} to {end_str}"

    meta_ctr = _f(meta_sum.get("ctr", 0))
    meta_cpc = _f(meta_sum.get("cpc", 0))
    google_cpc = _f(ads_tot.get("cpc", 0))
    google_sessions = sum(
        _i(t.get("sessions", 0)) for t in ga4.get("traffic_sources", [])
        if "paid" in t.get("sessionDefaultChannelGroup", "").lower()
    )

    # Auto-generate insight bullets from data
    breach = net_sum.get("centres_in_wage_breach", [])
    compliance = net_sum.get("rooms_with_compliance_risk", [])

    improved_bullets = []
    declined_bullets = []
    concern_bullets  = []
    action_bullets   = []

    if _f(ga4_curr.get("active_users", 0)) > _f(ga4_prev.get("active_users", 0)):
        improved_bullets.append(f"Website active users improved to <strong>{_num(active_users)}</strong> {wow_users}")
    if meta_ctr >= 2.2:
        improved_bullets.append(f"Meta CTR at <strong>{meta_ctr:.2f}%</strong> — above childcare Perth benchmark (2.2%+)")
    if meta_cpc <= 1.0:
        improved_bullets.append(f"Meta CPC at <strong>${meta_cpc:.2f}</strong> — excellent efficiency (benchmark &lt;$1.00)")
    if google_conv > 0:
        improved_bullets.append(f"Google Ads delivered <strong>{google_conv:.0f} conversions</strong> at ${ads_tot.get('cost_per_conv', 0):.2f}/conv")
    if net_movement > 0:
        improved_bullets.append(f"Net enrolment movement <strong>+{net_movement}</strong> ({enrolments} enrolments, {exits} exits)")

    if _f(ga4_curr.get("key_events", 0)) < _f(ga4_prev.get("key_events", 0)):
        declined_bullets.append(f"Key events fell to <strong>{_num(ga4_curr.get('key_events',0))}</strong> {_wow(ga4_curr.get('key_events',0), ga4_prev.get('key_events',0))} — fewer enquiry-intent actions")
    if _f(ads_tot.get("conversions", 0)) < _f(ads_prev.get("conversions", 0)):
        declined_bullets.append(f"Google conversions down {_wow(ads_tot.get('conversions',0), ads_prev.get('conversions',0))} — review campaign bid strategy")
    if _f(ga4_curr.get("avg_session_duration_s", 60)) < 30:
        declined_bullets.append(f"Avg session duration collapsed to <strong>{_dur_fmt(ga4_curr.get('avg_session_duration_s',0))}</strong> — investigate landing page quality")

    if breach:
        concern_bullets.append(f"Wage breach at <strong>{', '.join(breach)}</strong> — exceeds 42% threshold, review staffing")
    if compliance:
        concern_bullets.append(f"Compliance risk: <strong>{', '.join(compliance)}</strong> — room over licensed capacity")
    if enquiries > 0 and enrolments == 0:
        concern_bullets.append(f"{enquiries} enquiries received but 0 converted — review tour follow-up process")

    action_bullets.append("Review /book-a-tour engagement rate — high-traffic, lower-conversion page")
    if breach:
        action_bullets.append(f"Address wage overspend at {', '.join(breach)} — review roster vs occupancy")
    if compliance:
        action_bullets.append(f"Resolve capacity compliance at {', '.join(compliance)}")
    action_bullets.append("Scale best-performing Meta creatives — review Top Ads tab for CTR leaders")

    def _bullets(items, fallback="No significant changes this week."):
        if not items:
            return f"<li>{fallback}</li>"
        return "\n".join(f"<li>{b}</li>" for b in items[:4])

    # Channel snapshot table rows
    meta_impr  = _num(meta_sum.get("impr", 0))
    meta_clk   = _num(meta_sum.get("clicks", 0))
    meta_spend = _money(meta_sum.get("spend", 0))
    ads_impr   = _num(ads_tot.get("impressions", 0))
    ads_clk    = _num(ads_tot.get("clicks", 0))
    ads_spend  = _money(ads_tot.get("spend", 0))
    web_sess   = _num(ga4_curr.get("sessions", 0))
    web_users  = _num(active_users)
    web_events = _num(ga4_curr.get("key_events", 0))

    meta_status = _badge("Performing", "green") if meta_ctr >= 2.2 else _badge("Monitor", "amber")
    ads_status  = _badge("Monitor", "blue")
    web_status  = _badge("Growing", "green") if active_users > prev_active_users else _badge("Monitor", "amber")
    ops_status  = _badge("Active", "teal")

    return f"""
<div id="overview" class="tab-panel active">
  <div class="hero">
    <div>
      <h1>Marketing Weekly Report</h1>
      <p>Period: <strong>{period_label}</strong> &nbsp;|&nbsp; Generated: {datetime.now().strftime('%-d %b %Y')} &nbsp;|&nbsp; My World Childcare</p>
    </div>
    <div class="hero-right">
      <div>Chasing Better Group</div>
      <div style="margin-top:4px;font-size:11px;opacity:.7">Confidential · Internal Use Only</div>
    </div>
  </div>

  <div class="section-title">Week at a Glance</div>
  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-label">Total Ad Spend</div>
      <div class="kpi-value">{_money(total_spend)}</div>
      <div class="kpi-sub">Meta {_money(meta_sum.get("spend",0))} · Google {_money(ads_tot.get("spend",0))} &nbsp;|&nbsp; {wow_spend}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Google Conversions</div>
      <div class="kpi-value">{google_conv:.2f}</div>
      <div class="kpi-sub">{wow_conv} · CPC ${google_cpc:.2f}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Website Active Users</div>
      <div class="kpi-value">{_num(active_users)}</div>
      <div class="kpi-sub">{wow_users} week-on-week</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Net Enrolment Movement</div>
      <div class="kpi-value">{net_movement:+d}</div>
      <div class="kpi-sub">{enrolments} enrolments · {exits} exits · {enquiries} enquiries</div>
    </div>
  </div>

  <div class="section-title">Channel Snapshot</div>
  <div class="card" style="padding:0;overflow:hidden">
    <table class="ch-table">
      <thead><tr><th>Channel</th><th>Key Metric 1</th><th>Key Metric 2</th><th>Key Metric 3</th><th>Key Metric 4</th><th>Status</th></tr></thead>
      <tbody>
        <tr>
          <td><strong>Meta Ads</strong></td>
          <td>Spend <strong>{meta_spend}</strong></td>
          <td>Impressions <strong>{meta_impr}</strong></td>
          <td>Clicks <strong>{meta_clk}</strong></td>
          <td>CTR <strong>{meta_ctr:.2f}%</strong> · CPC <strong>${meta_cpc:.2f}</strong></td>
          <td>{meta_status}</td>
        </tr>
        <tr>
          <td><strong>Google Ads</strong></td>
          <td>Spend <strong>{ads_spend}</strong></td>
          <td>Impressions <strong>{ads_impr}</strong></td>
          <td>Clicks <strong>{ads_clk}</strong></td>
          <td>Conv <strong>{google_conv:.2f}</strong> · CPC <strong>${google_cpc:.2f}</strong></td>
          <td>{ads_status}</td>
        </tr>
        <tr>
          <td><strong>Website</strong></td>
          <td>Active Users <strong>{web_users}</strong></td>
          <td>Sessions <strong>{web_sess}</strong></td>
          <td>Key Events <strong>{web_events}</strong></td>
          <td>Avg Duration <strong>{_dur_fmt(ga4_curr.get("avg_session_duration_s",0))}</strong></td>
          <td>{web_status}</td>
        </tr>
        <tr>
          <td><strong>Centre Ops</strong></td>
          <td>Enquiries <strong>{enquiries}</strong></td>
          <td>Enrolments <strong>{enrolments}</strong></td>
          <td>Exits <strong>{exits}</strong></td>
          <td>Net <strong>{net_movement:+d}</strong></td>
          <td>{ops_status}</td>
        </tr>
      </tbody>
    </table>
  </div>

  <div class="section-title">Week-on-Week Highlights</div>
  <div class="insight-grid">
    <div class="insight-card ic-green">
      <div class="ic-title">What Improved</div>
      <ul class="bullets">{_bullets(improved_bullets, "No significant improvements vs prior week.")}</ul>
    </div>
    <div class="insight-card ic-red">
      <div class="ic-title">What Declined</div>
      <ul class="bullets">{_bullets(declined_bullets, "No significant declines vs prior week.")}</ul>
    </div>
    <div class="insight-card ic-amber">
      <div class="ic-title">Ongoing Concerns</div>
      <ul class="bullets">{_bullets(concern_bullets, "No active threshold breaches this week.")}</ul>
    </div>
    <div class="insight-card ic-blue">
      <div class="ic-title">Priority Actions This Week</div>
      <ul class="bullets">{_bullets(action_bullets)}</ul>
    </div>
  </div>
</div>"""


# ─────────────────────────────────────────────────────────────────
# TAB 2 — Centre Occupancy
# ─────────────────────────────────────────────────────────────────

def _tab_centres(ops):
    ns     = ops.get("network_summary", {})
    period = ops.get("period", {})
    centres = ops.get("centres", {})

    if not centres:
        return """<div id="centres" class="tab-panel">
  <div class="na-box"><strong>No operations data available</strong>
  Drop MYWORLD_REPORT.xlsx + utilisation.xlsx into mwcc-inbox/ then re-run the pipeline.</div>
</div>"""

    enq   = _i(ns.get("total_enquiries", 0))
    enrol = _i(ns.get("total_enrolments", 0))
    exits = _i(ns.get("total_exits", 0))
    net   = _i(ns.get("net_movement", 0))
    rev   = _f(ns.get("total_revenue", 0))
    breach_centres = ns.get("centres_in_wage_breach", [])

    # Per-centre rows
    centre_rows = ""
    for name, c in sorted(centres.items()):
        c_enq   = _i(c.get("enquiries", 0))
        c_enrol = _i(c.get("enrolments", 0))
        c_exit  = _i(c.get("exits", 0))
        c_net   = c_enrol - c_exit
        net_html = f'<span class="kpi-up">+{c_net}</span>' if c_net > 0 else \
                   f'<span class="kpi-dn">{c_net}</span>' if c_net < 0 else \
                   '<span class="kpi-fl">0</span>'
        centre_rows += f"<tr><td>{name}</td><td>{c_enq}</td><td>{c_enrol}</td><td>{c_exit}</td><td>{net_html}</td></tr>\n"

    # Room-level occupancy rows (from rooms_detail or occupancy fallback)
    room_rows = ""
    occ_map = {
        "Babies": "Babies", "Toddlers": "Toddlers", "Kindy": "Kindy",
        "Before School": "B/S", "After School": "A/S", "Overall": "Overall",
    }
    for name, c in sorted(centres.items()):
        rooms = c.get("rooms_detail", {})
        if rooms:
            for room, rd in rooms.items():
                if room == "Vacation":
                    continue
                occ = _f(rd.get("occupancy_pct", 0))
                comp = ' <span class="badge b-red" style="font-size:9px">⚠ Compliance</span>' if rd.get("compliance_risk") else ""
                room_rows += f"<tr><td>{name} — {room}{comp}</td><td>{occ:.0f}%</td><td>{_occ_badge(occ)}</td></tr>\n"
        else:
            # Fall back to MYWORLD_REPORT per-room %
            occ_data = c.get("occupancy", {})
            for room_key in ["Before School", "After School", "Kindy", "Babies", "Toddlers"]:
                occ = _i(occ_data.get(room_key, 0))
                if occ > 0:
                    room_rows += f"<tr><td>{name} — {room_key}</td><td>{occ}%</td><td>{_occ_badge(occ)}</td></tr>\n"

    # Revenue & wage table
    fin_rows = ""
    for name, c in sorted(centres.items()):
        wage = _f(c.get("wage_exc_leave_pct", 0))
        rev_c = _f(c.get("revenue", 0))
        breach_html = f' <span class="badge b-red" style="font-size:9px">⚠ Breach</span>' if c.get("wage_breach") else " ✓"
        fin_rows += f"<tr><td>{name}</td><td>{_money(rev_c)}</td><td>{wage:.2f}%{breach_html}</td><td>{_i(c.get('occupancy', {}).get('Overall', 0))}%</td></tr>\n"

    period_label = period.get("label", "—")

    return f"""
<div id="centres" class="tab-panel">
  <div class="hero">
    <div><h1>Centre Occupancy</h1><p>{period_label} · My World Childcare</p></div>
    <div class="hero-right">
      <div>Enquiries: <strong>{enq}</strong></div>
      <div>Net Movement: <strong>{net:+d}</strong></div>
    </div>
  </div>

  <div class="kpi-grid">
    <div class="kpi-card"><div class="kpi-label">Enquiries</div><div class="kpi-value">{enq}</div></div>
    <div class="kpi-card"><div class="kpi-label">Enrolments</div><div class="kpi-value">{enrol}</div></div>
    <div class="kpi-card"><div class="kpi-label">Exits</div><div class="kpi-value">{exits}</div></div>
    <div class="kpi-card">
      <div class="kpi-label">Net Movement</div>
      <div class="kpi-value">{net:+d}</div>
      <div class="kpi-sub">Total revenue: {_money(rev)}</div>
    </div>
  </div>

  <div class="two-col">
    <div class="card">
      <div class="card-title">Enquiries · Enrolments · Exits by Centre</div>
      <table class="tbl">
        <thead><tr><th>Centre</th><th>Enquiries</th><th>Enrolments</th><th>Exits</th><th>Net</th></tr></thead>
        <tbody>{centre_rows}<tr class="tbl-total"><td>Total</td><td>{enq}</td><td>{enrol}</td><td>{exits}</td><td>{net:+d}</td></tr></tbody>
      </table>
    </div>
    <div class="card">
      <div class="card-title">Revenue · Wage Health · Occupancy</div>
      <table class="tbl">
        <thead><tr><th>Centre</th><th>Revenue</th><th>Wage Exc Leave</th><th>Overall Occ</th></tr></thead>
        <tbody>{fin_rows}</tbody>
      </table>
      <div style="margin-top:8px;font-size:11px;color:var(--muted)">Wage breach threshold: {WAGE_BREACH}% exc. leave. Occupancy from OWNA weekly report.</div>
    </div>
  </div>

  <div class="section-title">Room-Level Occupancy</div>
  <div class="card">
    <table class="tbl">
      <thead><tr><th>Centre / Room</th><th>Weekly Avg Occupancy</th><th>Status</th></tr></thead>
      <tbody>{room_rows}</tbody>
    </table>
    <div style="margin-top:8px;font-size:11px;color:var(--muted)">Occupancy = avg Mon–Fri enrolments ÷ licensed capacity. &gt;100% = compliance risk.</div>
  </div>
</div>"""


# ─────────────────────────────────────────────────────────────────
# TAB 3 — Meta Ads
# ─────────────────────────────────────────────────────────────────

def _tab_meta(meta, meta_hist):
    summary  = meta.get("summary", {})
    by_centre = meta.get("by_centre", {})
    ad_sets  = meta.get("ad_sets", [])
    top_ads  = meta.get("top_ads", [])
    campaigns = meta.get("campaigns", [])
    dr       = meta.get("date_range", {})

    if not summary:
        return """<div id="meta" class="tab-panel">
  <div class="na-box"><strong>No Meta Ads data</strong>
  Ensure META_ACCESS_TOKEN and MWCC_META_AD_ACCOUNT_ID are set in .env and run pull_mwcc_meta.py</div>
</div>"""

    prev = meta_hist[1].get("summary", {}) if len(meta_hist) > 1 else {}

    spend  = _f(summary.get("spend", 0))
    impr   = _i(summary.get("impr", 0))
    clicks = _i(summary.get("clicks", 0))
    ctr    = _f(summary.get("ctr", 0))
    cpc    = _f(summary.get("cpc", 0))
    cpm    = _f(summary.get("cpm", 0))
    lpv    = _i(summary.get("lpv", 0))
    cost_lpv = _f(summary.get("cost_per_lpv", 0))

    # Benchmarks (childcare Perth/AU)
    def _bm(label, val, good_thresh, exc_thresh, lower_better=False, prefix="", suffix=""):
        fv = f"{prefix}{val:.2f}{suffix}"
        if lower_better:
            if val <= exc_thresh:  cls, verdict = "v-exc", "Excellent"
            elif val <= good_thresh: cls, verdict = "v-good", "Good"
            else:                  cls, verdict = "v-poor", "Below benchmark"
        else:
            if val >= exc_thresh:  cls, verdict = "v-exc", "Excellent"
            elif val >= good_thresh: cls, verdict = "v-good", "Good"
            else:                  cls, verdict = "v-poor", "Below benchmark"
        return f"""<div class="bm-cell">
  <div class="bm-metric">{label}</div>
  <div class="bm-actual" style="color:var({'--success' if cls=='v-exc' else '--danger' if cls=='v-poor' else '#3b82f6'})">{fv}</div>
  <div class="bm-verdict {cls}">{verdict}</div>
</div>"""

    benchmarks = f"""<div class="bm-row">
{_bm("CTR", ctr, 1.5, 2.2, suffix="%")}
{_bm("CPC", cpc, 1.00, 0.75, lower_better=True, prefix="$")}
{_bm("CPM", cpm, 8.0, 6.0, lower_better=True, prefix="$")}
{_bm("Cost/LPV", cost_lpv, 1.50, 1.00, lower_better=True, prefix="$")}
</div>"""

    # Funnel
    funnel = f"""<div class="funnel" style="margin-bottom:24px">
  <div class="funnel-step"><div class="funnel-val">{_num(impr)}</div><div class="funnel-lbl">Impressions</div><div class="funnel-sub">{_wow(impr, prev.get("impr",0))}</div></div>
  <div class="funnel-step"><div class="funnel-val">{_num(clicks)}</div><div class="funnel-lbl">Link Clicks</div><div class="funnel-sub">{_wow(clicks, prev.get("clicks",0))}</div></div>
  <div class="funnel-step"><div class="funnel-val">{_num(lpv)}</div><div class="funnel-lbl">Landing Page Views</div><div class="funnel-sub">{_wow(lpv, prev.get("lpv",0))}</div></div>
  <div class="funnel-step"><div class="funnel-val">{ctr:.2f}%</div><div class="funnel-lbl">CTR</div><div class="funnel-sub">{_wow(ctr, prev.get("ctr",0))}</div></div>
  <div class="funnel-step"><div class="funnel-val">${cpc:.2f}</div><div class="funnel-lbl">CPC</div><div class="funnel-sub">{_wow(cpc, prev.get("cpc",0), invert=True)}</div></div>
  <div class="funnel-step"><div class="funnel-val">${spend:,.2f}</div><div class="funnel-lbl">Total Spend</div><div class="funnel-sub">{_wow(spend, prev.get("spend",0))}</div></div>
</div>"""

    # Campaign table
    camp_rows = ""
    for c in campaigns:
        camp_rows += f"""<tr>
  <td>{c.get("name","")}</td>
  <td>{_money(c.get("spend",0))}</td>
  <td>{_num(c.get("impr",0))}</td>
  <td>{_num(c.get("clicks",0))}</td>
  <td>{_f(c.get("ctr",0)):.2f}%</td>
  <td>${_f(c.get("cpc",0)):.2f}</td>
  <td>{_num(c.get("lpv",0))}</td>
  <td>${_f(c.get("cost_per_lpv",0)):.2f}</td>
</tr>\n"""

    # Ad set by centre table
    adset_rows = ""
    for s in ad_sets[:12]:
        freq = _f(s.get("frequency", 0))
        adset_rows += f"""<tr>
  <td>{s.get("campaign_name","")}</td>
  <td>{s.get("adset_name","")}</td>
  <td>{s.get("centre","Other")}</td>
  <td>{_money(s.get("spend",0))}</td>
  <td>{_num(s.get("impr",0))}</td>
  <td>{_num(s.get("reach",0))}</td>
  <td>{_num(s.get("clicks",0))}</td>
  <td>{_f(s.get("ctr",0)):.2f}%</td>
  <td>{_num(s.get("lpv",0))}</td>
  <td>{freq:.2f}× {_freq_badge(freq)}</td>
</tr>\n"""

    # Top ads table
    ad_rows = ""
    for i, ad in enumerate(top_ads):
        ad_rows += f"""<tr>
  <td>{i+1}</td>
  <td>{ad.get("name","")}</td>
  <td>{ad.get("centre","")}</td>
  <td>{_badge("Active","green")}</td>
  <td>{_money(ad.get("spend",0))}</td>
  <td>{_num(ad.get("impr",0))}</td>
  <td>{_num(ad.get("clicks",0))}</td>
  <td><strong>{_f(ad.get("ctr",0)):.2f}%</strong></td>
  <td>${_f(ad.get("cpc",0)):.2f}</td>
</tr>\n"""

    # By-centre summary
    centre_sum_rows = ""
    for centre in ["Armadale","Midvale","Rockingham","Seville Grove","Waikiki","Other"]:
        if centre in by_centre:
            m = by_centre[centre]
            centre_sum_rows += f"""<tr>
  <td><strong>{centre}</strong></td>
  <td>{_money(m.get("spend",0))}</td>
  <td>{_num(m.get("impr",0))}</td>
  <td>{_num(m.get("clicks",0))}</td>
  <td>{_f(m.get("ctr",0)):.2f}%</td>
  <td>${_f(m.get("cpc",0)):.2f}</td>
  <td>{_num(m.get("lpv",0))}</td>
</tr>\n"""

    return f"""
<div id="meta" class="tab-panel">
  <div class="hero">
    <div><h1>Meta Ads Performance</h1><p>{dr.get("start","")}&nbsp;–&nbsp;{dr.get("end","")} · Facebook &amp; Instagram Paid</p></div>
    <div class="hero-right"><div>Spend: <strong>{_money(spend)}</strong></div><div>Impressions: <strong>{_num(impr)}</strong></div></div>
  </div>

  <div class="section-title">Performance vs Benchmarks (Childcare Perth/AU)</div>
  {benchmarks}
  {funnel}

  <div class="card">
    <div class="card-title">Spend by Centre</div>
    <table class="tbl">
      <thead><tr><th>Centre</th><th>Spend</th><th>Impressions</th><th>Clicks</th><th>CTR</th><th>CPC</th><th>LPVs</th></tr></thead>
      <tbody>{centre_sum_rows}</tbody>
    </table>
  </div>

  <div class="card">
    <div class="card-title">Campaign Performance</div>
    <table class="tbl">
      <thead><tr><th>Campaign</th><th>Spend</th><th>Impressions</th><th>Clicks</th><th>CTR</th><th>CPC</th><th>LPVs</th><th>Cost/LPV</th></tr></thead>
      <tbody>{camp_rows}</tbody>
    </table>
  </div>

  <div class="card">
    <div class="card-title">Ad Set Breakdown by Centre (Frequency Monitor)</div>
    <table class="tbl">
      <thead><tr><th>Campaign</th><th>Ad Set</th><th>Centre</th><th>Spend</th><th>Impr</th><th>Reach</th><th>Clicks</th><th>CTR</th><th>LPVs</th><th>Frequency</th></tr></thead>
      <tbody>{adset_rows}</tbody>
    </table>
    <div style="margin-top:8px;font-size:11px;color:var(--muted)">Frequency = Impressions ÷ Reach. &gt;3× = audience saturation risk.</div>
  </div>

  <div class="card">
    <div class="card-title">Top 10 Ads by CTR (min $1 spend)</div>
    <table class="tbl">
      <thead><tr><th>#</th><th>Ad</th><th>Centre</th><th>Status</th><th>Spend</th><th>Impr</th><th>Clicks</th><th>CTR</th><th>CPC</th></tr></thead>
      <tbody>{ad_rows if ad_rows else "<tr><td colspan='9' style='color:var(--muted);text-align:center'>Ad-level data not available this week</td></tr>"}</tbody>
    </table>
  </div>
</div>"""


# ─────────────────────────────────────────────────────────────────
# TAB 4 — Google Ads
# ─────────────────────────────────────────────────────────────────

def _tab_google(ads, ads_hist):
    totals   = ads.get("totals", {})
    campaigns = ads.get("campaigns", [])
    dr       = ads.get("date_range", {})

    if not totals:
        return """<div id="google" class="tab-panel">
  <div class="na-box"><strong>No Google Ads data</strong>
  Ensure MWCC_GOOGLE_ADS_CUSTOMER_ID is set in .env and run pull_mwcc_ads.py</div>
</div>"""

    prev = ads_hist[1].get("totals", {}) if len(ads_hist) > 1 else {}

    spend  = _f(totals.get("spend", 0))
    impr   = _i(totals.get("impressions", 0))
    clicks = _i(totals.get("clicks", 0))
    conv   = _f(totals.get("conversions", 0))
    cpc    = _f(totals.get("cpc", 0))
    ctr    = _f(totals.get("ctr", 0))
    cpconv = _f(totals.get("cost_per_conv", 0))
    cpm    = round(spend / impr * 1000, 2) if impr else 0

    def _bm(label, val, good_thresh, exc_thresh, lower_better=False, prefix="", suffix=""):
        fv = f"{prefix}{val:.2f}{suffix}"
        if lower_better:
            if val <= exc_thresh:  cls, verdict = "v-exc", "Excellent"
            elif val <= good_thresh: cls, verdict = "v-good", "Good"
            else:                  cls, verdict = "v-poor", "Below"
        else:
            if val >= exc_thresh:  cls, verdict = "v-exc", "Excellent"
            elif val >= good_thresh: cls, verdict = "v-good", "Good"
            else:                  cls, verdict = "v-poor", "Below"
        col = '--success' if cls == 'v-exc' else '--danger' if cls == 'v-poor' else '#3b82f6'
        return f"""<div class="bm-cell">
  <div class="bm-metric">{label}</div>
  <div class="bm-actual" style="color:var({col})">{fv}</div>
  <div class="bm-verdict {cls}">{verdict}</div>
</div>"""

    benchmarks = f"""<div class="bm-row">
{_bm("CTR", ctr, 3.0, 4.0, suffix="%")}
{_bm("CPC", cpc, 4.00, 3.00, lower_better=True, prefix="$")}
{_bm("CPM", cpm, 70.0, 40.0, lower_better=True, prefix="$")}
{_bm("Cost/Conv", cpconv, 50.0, 30.0, lower_better=True, prefix="$")}
</div>"""

    funnel = f"""<div class="funnel" style="margin-bottom:24px">
  <div class="funnel-step"><div class="funnel-val">{_num(impr)}</div><div class="funnel-lbl">Impressions</div><div class="funnel-sub">{_wow(impr, prev.get("impressions",0))}</div></div>
  <div class="funnel-step"><div class="funnel-val">{_num(clicks)}</div><div class="funnel-lbl">Clicks</div><div class="funnel-sub">{_wow(clicks, prev.get("clicks",0))}</div></div>
  <div class="funnel-step"><div class="funnel-val">{conv:.2f}</div><div class="funnel-lbl">Conversions</div><div class="funnel-sub">{_wow(conv, prev.get("conversions",0))}</div></div>
  <div class="funnel-step"><div class="funnel-val">{ctr:.2f}%</div><div class="funnel-lbl">CTR</div><div class="funnel-sub">{_wow(ctr, _f(prev.get("ctr",0)))}</div></div>
  <div class="funnel-step"><div class="funnel-val">${cpconv:.2f}</div><div class="funnel-lbl">Cost/Conv</div><div class="funnel-sub">{_wow(cpconv, _f(prev.get("cost_per_conv",0)), invert=True)}</div></div>
  <div class="funnel-step"><div class="funnel-val">{_money(spend)}</div><div class="funnel-lbl">Total Spend</div><div class="funnel-sub">{_wow(spend, prev.get("spend",0))}</div></div>
</div>"""

    # Previous week campaign lookup
    prev_camps = {}
    if len(ads_hist) > 1:
        for c in ads_hist[1].get("campaigns", []):
            prev_camps[c.get("name","")] = c

    camp_rows = ""
    for c in campaigns:
        name    = c.get("name", "")
        camp_type = c.get("type", "")
        csp     = _f(c.get("spend", 0))
        cclicks = _i(c.get("clicks", 0))
        cconv   = _f(c.get("conversions", 0))
        ccpc    = _f(c.get("cpc", 0))
        ccpa    = _f(c.get("cost_per_conv", 0))
        pcv     = prev_camps.get(name, {})
        camp_rows += f"""<tr>
  <td>{name}</td><td><span class="badge b-grey">{camp_type}</span></td>
  <td>{_money(csp)} {_wow(csp, pcv.get("spend",0))}</td>
  <td>{_num(cclicks)} {_wow(cclicks, pcv.get("clicks",0))}</td>
  <td><strong>{cconv:.2f}</strong> {_wow(cconv, pcv.get("conversions",0))}</td>
  <td>${ccpc:.2f} {_wow(ccpc, pcv.get("cpc",0), invert=True)}</td>
  <td>${ccpa:.2f}</td>
</tr>\n"""

    return f"""
<div id="google" class="tab-panel">
  <div class="hero">
    <div><h1>Google Ads Performance</h1><p>{dr.get("start","")}&nbsp;–&nbsp;{dr.get("end","")} · Search + Performance Max</p></div>
    <div class="hero-right"><div>Spend: <strong>{_money(spend)}</strong></div><div>Conversions: <strong>{conv:.2f}</strong></div></div>
  </div>

  <div class="section-title">Performance vs Benchmarks (Childcare Perth/AU)</div>
  {benchmarks}
  {funnel}

  <div class="card">
    <div class="card-title">Campaign Performance (WoW)</div>
    <table class="tbl">
      <thead><tr><th>Campaign</th><th>Type</th><th>Spend</th><th>Clicks</th><th>Conversions</th><th>CPC</th><th>Cost/Conv</th></tr></thead>
      <tbody>{camp_rows}</tbody>
    </table>
  </div>
</div>"""


# ─────────────────────────────────────────────────────────────────
# TAB 5 — Organic Social (placeholder — no automated pull)
# ─────────────────────────────────────────────────────────────────

def _tab_organic():
    return """
<div id="organic" class="tab-panel">
  <div class="hero">
    <div><h1>Organic Social</h1><p>Facebook &amp; Instagram Organic</p></div>
    <div class="hero-right"><div>Data source: Metricool</div></div>
  </div>
  <div class="na-box">
    <strong>Organic social data is sourced from Metricool — not yet automated</strong>
    <span>To add organic social data to this report, export from Metricool and paste key metrics below.<br>
    A pull_mwcc_organic.py script (Metricool or Meta Graph API) can be added in a future phase.</span>
  </div>
  <div class="card">
    <div class="card-title">How to view organic social data</div>
    <ol style="font-size:13px;padding-left:20px;line-height:2">
      <li>Log in to <a href="https://app.metricool.com" target="_blank">Metricool</a></li>
      <li>Select the My World Childcare brand</li>
      <li>Go to Analytics → set the date range to match this report week</li>
      <li>Download the PDF or review Facebook + Instagram tabs for followers, reach, and engagement</li>
    </ol>
  </div>
</div>"""


# ─────────────────────────────────────────────────────────────────
# TAB 6 — Website
# ─────────────────────────────────────────────────────────────────

def _tab_website(ga4):
    curr   = ga4.get("current", {})
    prev   = ga4.get("previous", {})
    pages  = ga4.get("top_pages", [])
    channels = ga4.get("traffic_sources", [])
    dr     = ga4.get("date_range", {})

    if not curr:
        return """<div id="website" class="tab-panel">
  <div class="na-box"><strong>No GA4 data</strong>
  Ensure MWCC_GA4_PROPERTY_ID is set in .env and run pull_mwcc_ga4.py</div>
</div>"""

    active = _i(curr.get("active_users", 0))
    sessions = _i(curr.get("sessions", 0))
    key_ev  = _i(curr.get("key_events", 0))
    dur_s   = _f(curr.get("avg_session_duration_s", 0))
    eng_r   = _f(curr.get("engagement_rate", 0)) * 100

    prev_key_ev = _i(prev.get("key_events", 0))
    prev_dur    = _f(prev.get("avg_session_duration_s", 0))

    dur_alert = ""
    if dur_s < 30 and dur_s > 0:
        dur_alert = " · <span class='kpi-dn'>↓ investigate urgently</span>"

    # Top pages
    page_rows = ""
    prev_pages = {p.get("pagePath",""): p for p in ga4.get("top_pages", [])}
    for p in pages[:10]:
        path     = p.get("pagePath", "")
        sess     = _i(p.get("sessions", 0))
        pv       = _i(p.get("screenPageViews", 0))
        eng      = _f(p.get("engagementRate", 0)) * 100
        eng_cls  = "kpi-up" if eng >= 20 else "kpi-dn" if eng < 5 else "kpi-fl"
        page_rows += f"<tr><td>{path}</td><td>{_num(sess)}</td><td>{_num(pv)}</td><td><span class='{eng_cls}'>{eng:.2f}%</span></td></tr>\n"

    # Channel table
    ch_rows = ""
    channels_sorted = sorted(channels, key=lambda x: _i(x.get("sessions",0)), reverse=True)
    for ch in channels_sorted[:10]:
        name = ch.get("sessionDefaultChannelGroup", "Unknown")
        sess = _i(ch.get("sessions", 0))
        ev   = _i(ch.get("keyEvents", 0))
        ch_rows += f"<tr><td>{name}</td><td>{_num(sess)}</td><td>{_num(ev)}</td></tr>\n"

    return f"""
<div id="website" class="tab-panel">
  <div class="hero">
    <div><h1>Website Performance</h1><p>{dr.get("start","")}&nbsp;–&nbsp;{dr.get("end","")} · myworldcc.com.au</p></div>
    <div class="hero-right"><div>GA4 Property: 315149021</div></div>
  </div>

  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-label">Active Users</div>
      <div class="kpi-value">{_num(active)}</div>
      <div class="kpi-sub">{_wow(active, prev.get("active_users",0))} week-on-week</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Total Sessions</div>
      <div class="kpi-value">{_num(sessions)}</div>
      <div class="kpi-sub">{_wow(sessions, prev.get("sessions",0))} WoW</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Key Events</div>
      <div class="kpi-value">{_num(key_ev)}</div>
      <div class="kpi-sub">{_wow(key_ev, prev_key_ev)} from {_num(prev_key_ev)} prior week</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Avg Session Duration</div>
      <div class="kpi-value">{_dur_fmt(dur_s)}</div>
      <div class="kpi-sub">{_wow(dur_s, prev_dur)}{dur_alert}</div>
    </div>
  </div>

  <div class="two-col">
    <div class="card">
      <div class="card-title">Top Pages by Sessions</div>
      <table class="tbl">
        <thead><tr><th>Page</th><th>Sessions</th><th>Page Views</th><th>Eng Rate</th></tr></thead>
        <tbody>{page_rows}</tbody>
      </table>
    </div>
    <div class="card">
      <div class="card-title">Sessions by Channel</div>
      <table class="tbl">
        <thead><tr><th>Channel</th><th>Sessions</th><th>Key Events</th></tr></thead>
        <tbody>{ch_rows}</tbody>
      </table>
    </div>
  </div>
</div>"""


# ─────────────────────────────────────────────────────────────────
# Assemble full HTML
# ─────────────────────────────────────────────────────────────────

def bake_mwcc_report():
    print("[Baker] Loading state files...")
    ga4       = _load("mwcc-ga4.json")
    ads       = _load("mwcc-ads.json")
    ads_hist  = _load("mwcc-ads-history.json", default=[])
    meta      = _load("mwcc-meta.json")
    meta_hist = _load("mwcc-meta-history.json", default=[])
    ops       = _load("mwcc-ops.json")

    if not isinstance(ads_hist, list):  ads_hist  = []
    if not isinstance(meta_hist, list): meta_hist = []

    # Current data is always index 0 in history (inserted by pull scripts)
    # For WoW we want the PREVIOUS week = index 1
    ads_hist_with_curr  = [{"totals": ads.get("totals",{}), "campaigns": ads.get("campaigns",[])}] + ads_hist
    meta_hist_with_curr = [{"summary": meta.get("summary",{}), "by_centre": meta.get("by_centre",{})}] + meta_hist

    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"mwcc-marketing-{date_str}.html"
    outfile  = OUTPUT_DIR / filename

    print("[Baker] Building tabs...")

    html = f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>My World Childcare Marketing Weekly Report – {date_str}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
{_css()}
</head>
<body>

<div class="topbar">
  <div class="topbar-title">My World Childcare Marketing Weekly Report</div>
  <button class="dark-toggle" onclick="document.documentElement.setAttribute('data-theme',
    document.documentElement.getAttribute('data-theme')==='dark'?'light':'dark')">Dark</button>
</div>

<div class="tab-nav">
  <button class="tab-btn active" onclick="showTab('overview',this)">Executive Summary</button>
  <button class="tab-btn" onclick="showTab('centres',this)">Centre Occupancy</button>
  <button class="tab-btn" onclick="showTab('meta',this)">Meta Ads</button>
  <button class="tab-btn" onclick="showTab('google',this)">Google Ads</button>
  <button class="tab-btn" onclick="showTab('organic',this)">Organic Social</button>
  <button class="tab-btn" onclick="showTab('website',this)">Website</button>
</div>

{_tab_summary(ga4, ads, meta, ops, ads_hist_with_curr, meta_hist_with_curr)}
{_tab_centres(ops)}
{_tab_meta(meta, meta_hist_with_curr)}
{_tab_google(ads, ads_hist_with_curr)}
{_tab_organic()}
{_tab_website(ga4)}

<script>
function showTab(id,btn){{
  document.querySelectorAll('.tab-panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  btn.classList.add('active');
}}
</script>
</body>
</html>"""

    # Write dated archive copy
    outfile.write_text(html, encoding="utf-8")
    print(f"[Baker] Report archive  → {outfile}")

    # Write to docs/mwcc-report.html (GitHub Pages — always latest)
    docs_outfile = DOCS_DIR / "mwcc-report.html"
    docs_outfile.write_text(html, encoding="utf-8")
    print(f"[Baker] ✅ Published     → {docs_outfile}")
    print(f"[Baker] Live URL: https://cb247agent.github.io/cb_claude/mwcc-report.html")

    # Write companion data JS for unified dashboard (docs/mwcc-data.js)
    _bake_mwcc_data_js(ga4, ads, meta, ops)

    return str(docs_outfile)


def _bake_mwcc_data_js(ga4, ads, meta, ops):
    """Inject MWCC data inline into docs/index.html (replaces the mwcc-data-block script tag).

    Inline injection avoids GitHub Pages CDN caching of a separate mwcc-data.js file.
    Also writes docs/mwcc-data.js as a backup / for local dev use.

    Sets window.MWCC_DATA = { generated, period, ops, meta, ads, ads_history, meta_history,
                              ops_history, ga4, gsc, ahrefs }.
    """
    # Load rolling histories so the dashboard can render WoW deltas + 8-week trends
    ads_history  = _load("mwcc-ads-history.json", default=[])
    meta_history = _load("mwcc-meta-history.json", default=[])
    ops_history  = _load("mwcc-ops-history.json",  default=[])
    if not isinstance(ads_history,  list): ads_history  = []
    if not isinstance(meta_history, list): meta_history = []
    if not isinstance(ops_history,  list): ops_history  = []

    # Load GSC + Ahrefs for SEO page (Tia direction 07 Jun 2026 — SEO page was reading
    # md.gsc / md.ahrefs but baker wasn't populating them, so page showed "Awaiting GSC")
    gsc       = _load("mwcc-gsc-data.json", default={})
    ahrefs    = _load("mwcc-ahrefs.json",    default={})
    social    = _load("mwcc-social.json",    default={})
    gbp_perf  = _load("mwcc-gbp-performance.json", default={})
    if not isinstance(gsc,      dict): gsc      = {}
    if not isinstance(ahrefs,   dict): ahrefs   = {}
    if not isinstance(social,   dict): social   = {}
    if not isinstance(gbp_perf, dict): gbp_perf = {}

    data = {
        "generated":       datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC"),
        "period":          ops.get("period") or ops.get("network_summary", {}).get("period", {}),
        "ops":             ops,
        "meta":            meta,
        "ads":             ads,
        "ads_history":     ads_history,
        "meta_history":    meta_history,
        "ops_history":     ops_history,
        "ga4":             ga4,
        "gsc":             gsc,
        "ahrefs":          ahrefs,
        "social":          social,
        "gbp_performance": gbp_perf,
    }
    json_payload = json.dumps(data, indent=2, default=str)

    # ── 1. Inject inline into index.html ──────────────────────────────────────
    index_path = DOCS_DIR / "index.html"
    if index_path.exists():
        html = index_path.read_text(encoding="utf-8")
        import re
        new_block = (
            '<script id="mwcc-data-block">\n'
            '// MWCC dashboard data — auto-generated by bake-mwcc-report.py\n'
            '// DO NOT EDIT — regenerated every Monday 2pm AWST\n'
            f'window.MWCC_DATA = {json_payload};\n'
            '</script>'
        )
        updated = re.sub(
            r'<script id="mwcc-data-block">.*?</script>',
            lambda _: new_block,
            html,
            flags=re.DOTALL,
        )
        if updated != html:
            index_path.write_text(updated, encoding="utf-8")
            print(f"[Baker] ✅ Data injected → docs/index.html (inline, no CDN cache)")
        else:
            print(f"[Baker] ⚠️  mwcc-data-block marker not found in index.html — skipped inline injection")
    else:
        print(f"[Baker] ⚠️  docs/index.html not found — skipped inline injection")

    # ── 2. Also write standalone mwcc-data.js (backup / local dev) ────────────
    js_content = (
        "// MWCC dashboard data — auto-generated by bake-mwcc-report.py\n"
        "// DO NOT EDIT — regenerated every Monday 2pm AWST\n"
        f"window.MWCC_DATA = {json_payload};\n"
    )
    out = DOCS_DIR / "mwcc-data.js"
    out.write_text(js_content, encoding="utf-8")
    print(f"[Baker] ✅ Data JS (backup) → {out}")


if __name__ == "__main__":
    bake_mwcc_report()
