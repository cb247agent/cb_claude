"""
generate_monthly_shoot_pack.py — Aggregate one month of creative actions
into ONE shoot-day pack for Shauna (CB247 Assets Creator).

WHY THIS EXISTS
    Shauna only works one shoot day per month. Per-action briefs are great
    for the dashboard (one-tap "View Brief" for Tia + Brand Manager), but
    Shauna needs a single document that captures EVERYTHING she has to
    shoot for the next 30 days — sorted by location, deduped by setup,
    with all the angles, viral references, and Higgsfield fallbacks in one
    place.

    Per Tia direction (12 Jun 2026, "hybrid please"): per-action briefs
    keep working for the team's daily workflow, and this monthly pack is
    Shauna's deliverable.

OUTPUT
    docs/asset-library/shoot-pack-YYYY-MM.html  (styled, served by GH Pages)

TRIGGER
    First Monday of each month (wired into phase1_data.sh). Re-running
    mid-month is safe — it overwrites with the current snapshot.

USAGE
    python scripts/generate_monthly_shoot_pack.py
    python scripts/generate_monthly_shoot_pack.py --month 2026-07  # specific
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date as _date, timedelta
from pathlib import Path

BASE_DIR  = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
# Write into docs/ so GitHub Pages serves it.
OUTPUT_DIR = BASE_DIR / "docs" / "asset-library"

sys.path.insert(0, str(BASE_DIR / "scripts"))
from work_queue.build_creative_brief_context import build_context  # noqa: E402

# Reuse the same creative detector from generate_briefs.py so per-action
# briefs and the shoot pack agree on which actions Shauna owns.
from generate_briefs import _is_creative_action  # noqa: E402

# CB247 brand tokens (mirrors generate_briefs.py palette)
TEAL       = "#3FA69A"
TEAL_DEEP  = "#2d7d72"
TEAL_MIST  = "#f0fdf4"
TEAL_SOFT  = "rgba(63,166,154,.15)"
DARK       = "#1a1a2e"

PRIORITY_COLOR = {
    "P1": "#ef4444",
    "P2": "#f59e0b",
    "P3": TEAL,
}


def _escape(s) -> str:
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ─── domain helpers ──────────────────────────────────────────────────────
def _shoot_day_for_month(month_iso: str) -> str:
    """Recommend the LAST FRIDAY of the month as shoot day."""
    y, m = (int(x) for x in month_iso.split("-"))
    if m == 12:
        next_first = _date(y + 1, 1, 1)
    else:
        next_first = _date(y, m + 1, 1)
    last_day = next_first - timedelta(days=1)
    while last_day.weekday() != 4:    # Fri
        last_day -= timedelta(days=1)
    return last_day.isoformat()


def _location_of(action: dict) -> str:
    title = (action.get("title") or "").lower()
    desc  = (action.get("description") or "").lower()
    if "malaga" in title or "malaga" in desc:        return "Malaga"
    if "ellenbrook" in title or "ellenbrook" in desc: return "Ellenbrook"
    return "Both / Either"


def _category_of(action: dict) -> str:
    cat = (action.get("category") or action.get("source_page") or "other").lower()
    if "gbp" in cat:                       return "GBP Photos"
    if "meta" in cat:                      return "Meta Ad Creative"
    if "social" in cat or "organic" in cat: return "Organic Social"
    return "Other"


def _pending(action: dict) -> bool:
    status = (action.get("planner_status") or action.get("status") or "").lower()
    return status not in ("published", "rejected", "scheduled")


def _filter_creative_pending(actions: list) -> list:
    return [a for a in actions if _is_creative_action(a) and _pending(a)]


def _countdown_chip(days: int) -> str:
    if days < 0:
        return f"<span style='background:#fee2e2;color:#991b1b'>{abs(days)} days overdue</span>"
    if days == 0:
        return "<span style='background:#fee2e2;color:#991b1b'>TODAY</span>"
    if days <= 3:
        return f"<span style='background:#fee2e2;color:#991b1b'>{days} days away</span>"
    if days <= 7:
        return f"<span style='background:#fef3c7;color:#92400e'>{days} days away</span>"
    return f"<span style='background:{TEAL_MIST};color:{TEAL_DEEP}'>{days} days away</span>"


# ─── HTML section renderers ──────────────────────────────────────────────
def _render_summary_table(by_loc: dict) -> str:
    if not by_loc:
        return "<p class='muted'>No pending creative actions this month.</p>"
    rows = []
    for loc, items in by_loc.items():
        cats = sorted({_category_of(a) for a in items})
        cat_chips = "".join(
            f"<span class='chip-mini'>{_escape(c)}</span>" for c in cats
        )
        rows.append(
            f"<tr><td><b>{_escape(loc)}</b></td>"
            f"<td class='num'>{len(items)}</td>"
            f"<td>{cat_chips}</td></tr>"
        )
    return (
        "<table class='summary-table'><thead><tr>"
        "<th>Location</th><th class='num'>Shots</th><th>Categories</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def _render_winners(winners: list) -> str:
    if not winners:
        return "<p class='muted'>No standout winners last week — pack is forward-looking only.</p>"
    cards = []
    for w in winners:
        cards.append(f"""
        <div class='winner-card'>
          <div class='winner-name'>{_escape(w['name'])}</div>
          <div class='winner-loc'>{_escape(w['location'])} · {_escape(w['format'])}</div>
          <div class='winner-stats'>
            <span class='winner-ctr'>{w['ctr']}%<span class='unit'> CTR</span></span>
            <span class='winner-spend'>${w['spend']}<span class='unit'> spent</span></span>
          </div>
        </div>""")
    return f"<div class='winner-grid'>{''.join(cards)}</div>"


def _render_hashtags(hashtags: list) -> str:
    if not hashtags:
        return ""
    chips = "".join(
        f"<span class='chip'>#{_escape(h.get('hashtag'))} <span class='chip-count'>·{h.get('count')}</span></span>"
        for h in hashtags
    )
    return f"<div class='subsection-label'>Trending hashtags</div><div class='chip-row'>{chips}</div>"


def _render_top_posts(posts: list) -> str:
    if not posts:
        return ""
    cards = []
    for p in posts[:5]:
        txt = _escape((p.get("text") or "")[:240])
        plat = _escape(p.get("platform") or "—")
        eng = p.get("engagement") or p.get("plays") or p.get("likes") or 0
        cards.append(f"""
        <div class='post-card'>
          <div class='post-platform'>{plat}</div>
          <div class='post-text'>{txt}…</div>
          <div class='post-eng'>{eng:,} engagement</div>
        </div>""")
    return (
        f"<div class='subsection-label'>Top viral posts — worth mirroring</div>"
        f"<div class='post-grid'>{''.join(cards)}</div>"
    )


def _render_fb_ads(ads: list) -> str:
    if not ads:
        return ""
    items = []
    for ad in ads[:5]:
        body = _escape((ad.get("body") or "")[:220])
        page = _escape(ad.get("page") or "—")
        items.append(
            f"<li><b>{page}:</b> <span class='ad-body'>{body}…</span></li>"
        )
    return (
        f"<div class='subsection-label'>Competitor FB ads — defensive watch (never name them in copy)</div>"
        f"<ul class='ad-list'>{''.join(items)}</ul>"
    )


def _render_viral(viral: dict) -> str:
    parts = [
        _render_hashtags(viral.get("trending_hashtags") or []),
        _render_top_posts(viral.get("top_posts") or []),
        _render_fb_ads(viral.get("competitor_fb_ads") or []),
    ]
    parts = [p for p in parts if p]
    if not parts:
        return "<p class='muted'>No viral signals captured this week.</p>"
    return "\n".join(parts)


def _render_compliance(reminders: list) -> str:
    items = "".join(f"<li>{_escape(r)}</li>" for r in reminders)
    return f"<ul class='compliance-list'>{items}</ul>"


def _render_inventory(inv: list) -> str:
    if not inv:
        return "<p class='muted'>No on-hand images detected.</p>"
    rows = []
    for i in inv:
        rows.append(
            f"<tr><td><code>{_escape(i['filename'])}</code></td>"
            f"<td class='num muted'>{i['size_kb']} KB</td></tr>"
        )
    return f"<table class='inventory'><tbody>{''.join(rows)}</tbody></table>"


def _render_higgsfield(suggestions: list) -> str:
    if not suggestions:
        return ""
    cards = []
    for s in suggestions:
        cards.append(f"""
        <div class='higgs-card'>
          <div class='higgs-shot'>{_escape(s.get('shot'))}</div>
          <div class='higgs-prompt'>{_escape(s.get('prompt'))}</div>
        </div>""")
    return f"<div class='higgs-block'><div class='higgs-label'>Higgsfield fallback if not shootable in-club</div>{''.join(cards)}</div>"


def _render_action_card(a: dict) -> str:
    aid = _escape(a.get("id", ""))
    title = _escape(a.get("title", "Untitled"))
    desc  = _escape(a.get("description", "(no description)"))
    pri   = a.get("priority", "P3")
    effort = _escape(a.get("effort_hours", "—"))
    pks = a.get("projected_kpis") or []
    kpi_line = ""
    if pks:
        k = pks[0]
        metric = _escape(k.get("metric", ""))
        baseline = _escape(k.get("baseline", "?"))
        target = _escape(k.get("target", "?"))
        window = _escape(k.get("measurement_window_days", 14))
        kpi_line = (
            f"<div class='kpi-line'><b>Target:</b> "
            f"<span class='metric'>{metric}</span> "
            f"{baseline} → <b>{target}</b> "
            f"<span class='muted'>({window}d)</span></div>"
        )

    try:
        ctx = build_context(a)
        higgs = ctx.get("higgsfield_suggestions") or []
    except Exception:
        higgs = []
    higgs_html = _render_higgsfield(higgs)

    pri_color = PRIORITY_COLOR.get(pri, TEAL)
    return f"""
    <div class='action-card' id='{aid}'>
      <div class='action-head'>
        <span class='pri-badge' style='background:{pri_color}'>{pri}</span>
        <span class='action-title'>{title}</span>
      </div>
      <div class='action-meta'>
        <code>{aid}</code> · {effort}h effort
      </div>
      <div class='action-desc'>{desc}</div>
      {kpi_line}
      {higgs_html}
    </div>"""


def _render_location_block(loc: str, actions: list) -> str:
    if not actions:
        return ""
    by_cat: dict[str, list] = {}
    for a in actions:
        by_cat.setdefault(_category_of(a), []).append(a)
    cat_blocks = []
    for cat in sorted(by_cat.keys()):
        cards = "".join(_render_action_card(a) for a in by_cat[cat])
        cat_blocks.append(
            f"<div class='cat-block'>"
            f"<h3 class='cat-head'>{_escape(cat)} <span class='cat-count'>({len(by_cat[cat])})</span></h3>"
            f"{cards}</div>"
        )
    return f"""
    <div class='location-block'>
      <h2 class='loc-head'>
        <span class='loc-pin'>•</span> {_escape(loc)}
        <span class='loc-count'>{len(actions)} shot{'s' if len(actions) != 1 else ''}</span>
      </h2>
      {''.join(cat_blocks)}
    </div>"""


# ─── main page assembly ──────────────────────────────────────────────────
CSS = f"""
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f0f2f5;color:{DARK};line-height:1.6}}
  .page{{max-width:980px;margin:0 auto;background:#fff;min-height:100vh;box-shadow:0 0 32px rgba(0,0,0,.06)}}

  /* HERO */
  .hero{{background:linear-gradient(135deg,{DARK} 0%,#2a2a4e 100%);color:#fff;padding:36px 48px}}
  .hero-tag{{display:inline-block;font-size:11px;color:{TEAL};font-weight:700;letter-spacing:2px;text-transform:uppercase;margin-bottom:8px;background:rgba(63,166,154,.15);padding:5px 12px;border-radius:99px}}
  .hero h1{{font-size:34px;font-weight:800;margin-bottom:8px}}
  .hero-sub{{font-size:14px;color:rgba(255,255,255,.7);margin-bottom:24px}}
  .hero-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}
  .hero-stat{{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.12);border-radius:10px;padding:16px 18px}}
  .hero-stat-label{{font-size:10px;color:rgba(255,255,255,.6);text-transform:uppercase;letter-spacing:1px;font-weight:600;margin-bottom:6px}}
  .hero-stat-value{{font-size:24px;font-weight:700;color:#fff;font-variant-numeric:tabular-nums}}
  .hero-stat-sub{{font-size:12px;margin-top:6px}}
  .hero-stat-sub span{{display:inline-block;padding:3px 10px;border-radius:99px;font-weight:600;font-size:11px}}

  /* SECTIONS */
  section{{padding:32px 48px;border-bottom:1px solid #f0f2f5}}
  section:last-child{{border-bottom:none}}
  h2{{font-size:18px;font-weight:700;color:{DARK};margin-bottom:16px;padding-bottom:8px;border-bottom:3px solid {TEAL};display:inline-block}}
  .subsection-label{{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:{TEAL_DEEP};font-weight:700;margin:16px 0 10px}}

  /* SUMMARY TABLE */
  .summary-table{{width:100%;border-collapse:collapse;font-size:14px}}
  .summary-table th{{text-align:left;font-size:10px;letter-spacing:.08em;color:#6b7280;text-transform:uppercase;padding:10px 8px;border-bottom:2px solid #e5e7eb}}
  .summary-table td{{padding:12px 8px;border-bottom:1px solid #f0f2f5}}
  .summary-table .num{{text-align:right;font-variant-numeric:tabular-nums;font-weight:700}}

  /* CHIPS */
  .chip-row{{display:flex;flex-wrap:wrap;gap:8px}}
  .chip{{background:{TEAL_MIST};color:{TEAL_DEEP};border-radius:99px;padding:5px 12px;font-size:12px;font-weight:600}}
  .chip-count{{color:#9ca3af;font-weight:400}}
  .chip-mini{{display:inline-block;background:#f3f4f6;color:#374151;border-radius:3px;padding:2px 7px;font-size:10.5px;margin-right:4px}}

  /* WINNER CARDS */
  .winner-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px}}
  .winner-card{{background:{TEAL_MIST};border-left:4px solid {TEAL};padding:14px 16px;border-radius:6px}}
  .winner-name{{font-size:14px;font-weight:700;color:{DARK};margin-bottom:4px}}
  .winner-loc{{font-size:11px;color:#6b7280;margin-bottom:10px}}
  .winner-stats{{display:flex;gap:14px;font-size:13px}}
  .winner-ctr{{font-weight:800;color:{TEAL_DEEP};font-size:18px;font-variant-numeric:tabular-nums}}
  .winner-spend{{font-weight:700;color:#374151;font-variant-numeric:tabular-nums}}
  .unit{{font-size:10px;color:#9ca3af;font-weight:400}}

  /* VIRAL */
  .post-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}}
  .post-card{{background:#fff;border:1px solid #e5e7eb;border-radius:6px;padding:12px 14px}}
  .post-platform{{display:inline-block;font-size:9px;text-transform:uppercase;letter-spacing:.08em;background:#1a1a2e;color:#fff;padding:2px 8px;border-radius:3px;font-weight:700;margin-bottom:6px}}
  .post-text{{font-size:12px;color:#374151;line-height:1.5;margin-bottom:6px}}
  .post-eng{{font-size:11px;color:#9ca3af;font-weight:600}}
  .ad-list{{margin:0;padding-left:20px;font-size:13px;color:#374151}}
  .ad-list li{{margin-bottom:8px;line-height:1.55}}
  .ad-body{{color:#6b7280}}

  /* COMPLIANCE */
  .compliance-section{{background:#fef2f2}}
  .compliance-section h2{{border-bottom-color:#991b1b}}
  .compliance-list{{list-style:none;padding:0;margin:0}}
  .compliance-list li{{padding:10px 12px;background:#fff;border-left:4px solid #991b1b;margin-bottom:8px;font-size:13px;color:#7f1d1d;border-radius:0 4px 4px 0}}

  /* INVENTORY */
  .inventory{{width:100%;border-collapse:collapse;font-size:12.5px;background:#fafbfc;border-radius:6px;overflow:hidden}}
  .inventory td{{padding:8px 12px;border-bottom:1px solid #f0f2f5}}
  .inventory code{{font-family:Menlo,monospace;font-size:11.5px;color:{TEAL_DEEP}}}

  /* LOCATION BLOCKS */
  .location-block{{margin-bottom:32px}}
  .loc-head{{font-size:22px;font-weight:800;color:{DARK};margin-bottom:14px;padding:12px 18px;background:linear-gradient(90deg,{TEAL_MIST} 0%,#fff 100%);border-left:6px solid {TEAL};border-radius:0 6px 6px 0;display:flex;align-items:center;gap:10px}}
  .loc-pin{{color:{TEAL};font-size:26px;line-height:0}}
  .loc-count{{margin-left:auto;font-size:13px;color:#6b7280;font-weight:600;background:#fff;padding:4px 12px;border-radius:99px;border:1px solid {TEAL_SOFT}}}

  .cat-block{{margin-bottom:18px;margin-left:14px}}
  .cat-head{{font-size:13px;font-weight:700;color:{TEAL_DEEP};text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px;padding-bottom:6px;border-bottom:1px dashed #e5e7eb}}
  .cat-count{{color:#9ca3af;font-weight:400}}

  /* ACTION CARD */
  .action-card{{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:14px 16px;margin-bottom:10px;transition:box-shadow .15s}}
  .action-card:hover{{box-shadow:0 2px 8px rgba(0,0,0,.05);border-color:{TEAL_SOFT}}}
  .action-head{{display:flex;align-items:center;gap:10px;margin-bottom:6px}}
  .pri-badge{{color:#fff;font-size:10px;font-weight:800;padding:3px 8px;border-radius:3px;letter-spacing:.04em;font-variant-numeric:tabular-nums}}
  .action-title{{font-size:14px;font-weight:700;color:{DARK};flex:1}}
  .action-meta{{font-size:10.5px;color:#9ca3af;margin-bottom:8px}}
  .action-meta code{{background:#f3f4f6;padding:1px 6px;border-radius:3px;font-size:10.5px}}
  .action-desc{{font-size:12.5px;color:#374151;line-height:1.6;margin-bottom:8px}}
  .kpi-line{{background:{TEAL_MIST};border-left:3px solid {TEAL};padding:6px 10px;font-size:12px;color:{DARK};border-radius:0 4px 4px 0;margin-bottom:8px}}
  .kpi-line .metric{{font-family:Menlo,monospace;font-size:11px;color:{TEAL_DEEP}}}

  /* HIGGSFIELD */
  .higgs-block{{background:#fafbfc;border:1px dashed #d1d5db;border-radius:6px;padding:10px 12px;margin-top:8px}}
  .higgs-label{{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:#6b7280;font-weight:700;margin-bottom:8px}}
  .higgs-card{{background:#fff;border:1px solid #f0f2f5;border-radius:4px;padding:8px 10px;margin-bottom:6px}}
  .higgs-shot{{font-size:12px;font-weight:700;color:{DARK};margin-bottom:4px}}
  .higgs-prompt{{font-family:Menlo,monospace;font-size:10.5px;color:#374151;line-height:1.5;background:#fafbfc;padding:6px 8px;border-radius:3px}}

  /* AFTER */
  .after-section{{background:{TEAL_MIST}}}
  .after-list{{counter-reset:step;list-style:none;padding:0}}
  .after-list li{{counter-increment:step;position:relative;padding:8px 0 8px 36px;font-size:13px;line-height:1.6;color:#374151}}
  .after-list li::before{{content:counter(step);position:absolute;left:0;top:8px;width:24px;height:24px;background:{TEAL};color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:11px}}

  /* MISC */
  .muted{{color:#9ca3af;font-size:12px}}
  .footer{{padding:24px 48px;text-align:center;font-size:11px;color:#9ca3af;background:#fafbfc;border-top:1px solid #f0f2f5}}

  /* PRINT */
  @media print{{
    body{{background:#fff}}
    .page{{box-shadow:none;max-width:none}}
    .hero{{background:{DARK} !important;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
    section{{padding:20px 32px;page-break-inside:avoid}}
    .action-card{{page-break-inside:avoid}}
  }}

  /* MOBILE */
  @media (max-width:640px){{
    .hero{{padding:24px}}
    .hero h1{{font-size:24px}}
    .hero-grid{{grid-template-columns:1fr}}
    section{{padding:20px 24px}}
  }}
"""


def build_pack(month_iso: str) -> str:
    wq_file = STATE_DIR / "work-queue.json"
    if not wq_file.exists():
        return _empty_page(month_iso, "work-queue.json not found")

    wq = json.loads(wq_file.read_text())
    actions = wq.get("actions") or []
    creative_pending = _filter_creative_pending(actions)

    by_loc: dict[str, list] = {}
    for a in creative_pending:
        by_loc.setdefault(_location_of(a), []).append(a)

    ctx = build_context()
    winners    = ctx.get("past_winners") or []
    viral      = ctx.get("viral") or {}
    inventory  = ctx.get("image_inventory") or []
    compliance = ctx.get("compliance_reminders") or []
    account_ctr = ctx.get("_account_meta_ctr")

    shoot_day_iso = _shoot_day_for_month(month_iso)
    shoot_day_d   = _date.fromisoformat(shoot_day_iso)
    today         = _date.today()
    days_until    = (shoot_day_d - today).days
    today_iso     = today.isoformat()
    month_label   = shoot_day_d.strftime("%B %Y")

    locations_str = ", ".join(by_loc.keys()) or "—"

    # ── Hero ─────────────────────────────────────────────────────────────
    hero = f"""
    <header class='hero'>
      <div class='hero-tag'>Monthly Shoot Pack · {month_iso}</div>
      <h1>Shauna's Shoot Day — {month_label}</h1>
      <div class='hero-sub'>Brief generated {today_iso} · Account Meta CTR baseline: <b>{account_ctr or '—'}%</b></div>
      <div class='hero-grid'>
        <div class='hero-stat'>
          <div class='hero-stat-label'>Recommended Shoot Day</div>
          <div class='hero-stat-value'>{shoot_day_iso}</div>
          <div class='hero-stat-sub'>{_countdown_chip(days_until)}</div>
        </div>
        <div class='hero-stat'>
          <div class='hero-stat-label'>Pending Creative Actions</div>
          <div class='hero-stat-value'>{len(creative_pending)}</div>
          <div class='hero-stat-sub' style='color:rgba(255,255,255,.6)'>across {len(by_loc)} location{'s' if len(by_loc) != 1 else ''}</div>
        </div>
        <div class='hero-stat'>
          <div class='hero-stat-label'>Locations</div>
          <div class='hero-stat-value' style='font-size:16px;line-height:1.4;padding-top:4px'>{locations_str}</div>
        </div>
      </div>
    </header>"""

    # ── Sections ────────────────────────────────────────────────────────
    sections = [
        f"""<section>
            <h2>Shoot Day Summary</h2>
            <p class='muted' style='margin-bottom:14px'>Plan: morning at Malaga (heavier load), Ellenbrook after lunch. Start with GBP photos — highest ROI per minute (5 fresh photos lift GBP rank measurably). Then Meta ad creative, then social trend-rides.</p>
            {_render_summary_table(by_loc)}
        </section>""",
        f"""<section>
            <h2>What's Working — Past Winners (Last Week)</h2>
            <p class='muted' style='margin-bottom:14px'>Top Meta ads. Mirror the angle / hook / location split.</p>
            {_render_winners(winners)}
        </section>""",
        f"""<section>
            <h2>Viral Signals — What to Mirror This Month</h2>
            {_render_viral(viral)}
        </section>""",
        f"""<section class='compliance-section'>
            <h2>Compliance — Read Before Every Shot</h2>
            {_render_compliance(compliance)}
        </section>""",
        f"""<section>
            <h2>On-Hand Image Inventory</h2>
            <p class='muted' style='margin-bottom:14px'>Reuse before reshooting — saves a setup.</p>
            {_render_inventory(inventory)}
        </section>""",
    ]

    # ── Shot List per Location ──────────────────────────────────────────
    if not by_loc:
        shot_section = """<section>
            <h2>Shot List — Per Location</h2>
            <p class='muted'>No pending creative actions found in work-queue.json. Use this month for a GBP photo refresh at both locations to keep rankings warm.</p>
        </section>"""
    else:
        loc_blocks = []
        for loc in sorted(by_loc.keys()):
            loc_blocks.append(_render_location_block(loc, by_loc[loc]))
        shot_section = f"""<section>
            <h2>Shot List — Per Location</h2>
            {''.join(loc_blocks)}
        </section>"""
    sections.append(shot_section)

    # ── After the Shoot ─────────────────────────────────────────────────
    sections.append(f"""<section class='after-section'>
        <h2>After the Shoot</h2>
        <ol class='after-list'>
          <li>Drop captured assets into <code>Image/</code> with descriptive filenames (<code>&lt;location&gt;_&lt;scene&gt;_&lt;date&gt;.jpg</code>)</li>
          <li>Tag Tia in Slack with the asset folder link</li>
          <li>Tia uses the per-action briefs in the dashboard (View Brief) to match raw assets to action IDs</li>
          <li>Brand Manager QCs the deliverables in the Work Queue kanban</li>
          <li>Measurement runner auto-checks the projected KPI on day 14 — verdict (Win / Mixed / Loss) appears on Performance Review</li>
        </ol>
    </section>""")

    footer = f"""<div class='footer'>
        Generated by <code>scripts/generate_monthly_shoot_pack.py</code> · CB247 Marketing OS · {today_iso}
    </div>"""

    return f"""<!DOCTYPE html>
<html lang='en'>
<head>
<meta charset='UTF-8'>
<meta name='viewport' content='width=device-width, initial-scale=1.0'>
<title>CB247 Shoot Pack · {month_label}</title>
<style>{CSS}</style>
</head>
<body>
<div class='page'>
  {hero}
  {''.join(sections)}
  {footer}
</div>
</body>
</html>"""


def _empty_page(month_iso: str, reason: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset='UTF-8'><title>CB247 Shoot Pack · {month_iso}</title>
<style>body{{font-family:sans-serif;max-width:600px;margin:80px auto;padding:0 24px;color:#374151}}</style></head>
<body><h1>CB247 Shoot Pack · {month_iso}</h1><p>{_escape(reason)}</p></body></html>"""


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--month", default=_date.today().strftime("%Y-%m"),
                   help="Month to plan for (YYYY-MM). Default: this month.")
    args = p.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"shoot-pack-{args.month}.html"
    pack = build_pack(args.month)
    out_path.write_text(pack, encoding="utf-8")
    print(f"[shoot-pack] Wrote {out_path.relative_to(BASE_DIR)} ({len(pack):,} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
