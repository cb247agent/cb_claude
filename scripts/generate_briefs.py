"""
generate_briefs.py — Generate per-action brief HTML files for CB247.

CB247 mirror of generate_mwcc_briefs.py. One HTML file per Work Queue action
named docs/briefs/{action_id}.html — these are what the dashboard's modal
"View Brief" link opens.

Replaces the 14 legacy hand-written p1.html–p14.html files (still kept as
historical reference) with one brief per CURRENT action in state/work-queue.json.

Run after the weekly emitter pass:
    .venv/bin/python3.13 scripts/generate_briefs.py

Wired into scripts/weekly-report.sh AFTER sync_to_supabase so briefs
regenerate every Monday cron.

USAGE: python scripts/generate_briefs.py
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = BASE_DIR / "state" / "work-queue.json"
PROMO_FILE = BASE_DIR / "state" / "promo-pipeline.json"
BRIEFS_DIR = BASE_DIR / "docs" / "briefs"

# Shared creative context (12 Jun 2026 — hybrid brief generator).
# Per-action briefs for Shauna AND the monthly shoot pack both pull
# context from build_creative_brief_context.py so they stay aligned.
sys.path.insert(0, str(BASE_DIR / "scripts"))
try:
    from work_queue.build_creative_brief_context import build_context as _build_creative_context
except Exception as _e:    # pragma: no cover — keep brief gen resilient
    print(f"[cb247-briefs] WARN — creative context helper unavailable: {_e}")
    _build_creative_context = None

# CB247 teal palette (matches docs/index.html CSS vars)
CB247_TEAL = "#3FA69A"
CB247_TEAL_DEEP = "#2d7d72"
CB247_TEAL_MIST = "#f0fdf4"
CB247_TEAL_SOFT = "rgba(63,166,154,.15)"
CB247_DARK = "#1a1a2e"

# Category → badge colours (matches dashboard verdict-source-badge classes)
CATEGORY_BADGE = {
    "seo-organic":     {"bg": "#f3e8ff", "fg": "#6b21a8"},
    "seo":             {"bg": "#f3e8ff", "fg": "#6b21a8"},
    "meta-ads":        {"bg": "#ede9fe", "fg": "#5b21b6"},
    "google-ads":      {"bg": "#fef3c7", "fg": "#92400e"},
    "organic-social":  {"bg": "#fce7f3", "fg": "#9d174d"},
    "gbp":             {"bg": CB247_TEAL_SOFT, "fg": CB247_TEAL_DEEP},
    "membership":      {"bg": "#f0fdf4", "fg": "#15803d"},
    "opportunity":     {"bg": "#fef3c7", "fg": "#92400e"},
    "overview":        {"bg": "#f3f4f6", "fg": "#374151"},
}

PRIORITY_COLOR = {
    "P1": "#ef4444",
    "P2": "#f59e0b",
    "P3": CB247_TEAL,
}


def _escape(s):
    """Minimal HTML escape (titles, descriptions, captions)."""
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _safe_filename(action_id):
    """Map action id → safe filename component (lowercase, alphanum + dash/underscore)."""
    return re.sub(r"[^a-z0-9_-]", "-", action_id.lower())


def _load_promo_lookup():
    """Build {promo_id: promo_dict} for parent_promo_id resolution."""
    if not PROMO_FILE.exists():
        return {}
    try:
        data = json.loads(PROMO_FILE.read_text())
    except Exception:
        return {}
    out = {}
    for track in ("acquisition", "retention"):
        for p in data.get(track, []) or []:
            if p.get("id"):
                out[p["id"]] = p
    return out


def _draft_block(action):
    """Return a 'Draft — Ready for Review' section if the action has draft_link.
    Mirrors CB247's #modal-draft-link-wrap pattern."""
    draft = action.get("draft_link") or action.get("draftLink")
    if not draft:
        return ""
    # Strip leading 'docs/' — GitHub Pages serves from docs/, so the URL path
    # doesn't include 'docs'. Then prefix with ../ so it resolves from docs/briefs/.
    _draft = draft.replace("docs/", "", 1) if draft.startswith("docs/") else draft
    draft_url = _draft if _draft.startswith("http") else f"../{_draft}"
    return f"""<div class="section" style="background:{CB247_TEAL_MIST};border-left:4px solid {CB247_TEAL};border-radius:4px;padding:14px 18px;margin:14px 0">
    <div class="label" style="color:{CB247_TEAL_DEEP};margin-bottom:8px">Draft — Ready for Review</div>
    <a href="{draft_url}" target="_blank" style="display:inline-block;background:{CB247_TEAL};color:#fff;padding:10px 22px;border-radius:5px;text-decoration:none;font-weight:700;font-size:13px">Open Draft →</a>
    <div style="font-size:11px;color:#6b7280;margin-top:8px">Open the draft, review, then return here and pick an approval decision below.</div>
  </div>"""


def _promo_block(action, promos):
    """If action has parent_promo_id, render a Promo Context section linking
    to the parent concept."""
    ppid = action.get("parent_promo_id")
    if not ppid:
        return ""
    p = promos.get(ppid)
    if not p:
        return f"""<div class="section">
    <div class="label">Parent Promo</div>
    <div style="font-size:12px;color:#6b7280"><code style="background:#f3f4f6;padding:2px 6px;border-radius:3px">{_escape(ppid)}</code> · concept not found in promo-pipeline.json</div>
  </div>"""
    track_color = "#92400e" if p.get("track") == "retention" else CB247_TEAL_DEEP
    track_bg    = "#fef3c7" if p.get("track") == "retention" else CB247_TEAL_MIST
    return f"""<div class="section" style="background:{track_bg};border-radius:4px;margin:0 28px 14px;padding:14px 18px">
    <div class="label" style="color:{track_color}">Parent Promo — {_escape(p.get('track','').title())} Track</div>
    <div style="font-size:14px;font-weight:700;color:{CB247_DARK};margin-bottom:4px">{_escape(p.get('label',''))}</div>
    <div style="font-size:12px;color:#374151;margin-bottom:8px">{_escape(p.get('subtitle',''))}</div>
    <div style="font-size:11.5px;color:#6b7280;line-height:1.6">
      <b>Offer:</b> {_escape((p.get('offer') or {}).get('headline',''))}<br>
      <b>Audience:</b> {_escape(p.get('target_audience',''))} · <b>Stage:</b> {_escape(p.get('stage',''))}
    </div>
  </div>"""


# ─────────────────────────────────────────────────────────────────────────
# CREATIVE ACTION DETECTION + SECTION RENDERER (12 Jun 2026)
# Shauna only works one shoot day per month. Per-action briefs for her
# need the SHOT, the ANGLE, the VIRAL REFERENCE, and a Higgsfield AI
# fallback — far richer than a standard CTA-tweak brief.
# ─────────────────────────────────────────────────────────────────────────

# Trigger words in the title that imply a creative deliverable
_CREATIVE_TITLE_VERBS = ("refresh", "add", "test", "swap", "shoot", "capture", "produce")
_CREATIVE_TITLE_NOUNS = (
    "reel", "photo", "image", "video", "carousel", "creative",
    "shoot", "asset", "story", "vlog", "tiktok",
)


def _is_creative_action(action: dict) -> bool:
    """True if this action belongs in Shauna's shoot pack.

    Heuristic mirrors what _classifyActionKind() does on the dashboard
    side, plus an owner_role check so Shauna's GBP photo refresh + social
    trend-rides ALL surface as creative even when the title doesn't say
    'reel' or 'photo' explicitly.
    """
    role  = (action.get("owner_role") or "").lower()
    owner = (action.get("owner") or "").lower()
    title = (action.get("title") or "").lower()
    if "assets creator" in role or "asset creator" in role:
        return True
    if "shauna" in owner:
        return True
    # Title-based — verb + creative noun, e.g. "Refresh Deep Heat reel"
    if any(v in title for v in _CREATIVE_TITLE_VERBS) and any(
        n in title for n in _CREATIVE_TITLE_NOUNS
    ):
        return True
    return False


def _render_winners_html(winners: list) -> str:
    if not winners:
        return "<i style='color:#9ca3af;font-size:12px'>No standout winners last week.</i>"
    rows = []
    for w in winners:
        rows.append(
            f"<tr><td style='padding:6px 8px;border-bottom:1px solid #f0f2f5'>{_escape(w['name'])}</td>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #f0f2f5;color:#6b7280'>{_escape(w['location'])}</td>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #f0f2f5;text-align:right'>"
            f"<b>{w['ctr']}%</b></td>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #f0f2f5;text-align:right;color:#6b7280'>"
            f"${w['spend']}</td></tr>"
        )
    return (
        "<table style='width:100%;border-collapse:collapse;font-size:12px;margin-top:6px'>"
        "<thead><tr style='border-bottom:2px solid #e5e7eb'>"
        "<th style='padding:6px 8px;text-align:left;font-size:10px;color:#6b7280;text-transform:uppercase'>Ad name</th>"
        "<th style='padding:6px 8px;text-align:left;font-size:10px;color:#6b7280;text-transform:uppercase'>Loc</th>"
        "<th style='padding:6px 8px;text-align:right;font-size:10px;color:#6b7280;text-transform:uppercase'>CTR</th>"
        "<th style='padding:6px 8px;text-align:right;font-size:10px;color:#6b7280;text-transform:uppercase'>Spend</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def _render_viral_html(viral: dict) -> str:
    parts = []
    hashtags = viral.get("trending_hashtags") or []
    if hashtags:
        chips = " ".join(
            f"<span style='display:inline-block;background:#f3f4f6;color:#374151;border-radius:99px;padding:3px 10px;font-size:11px;margin:2px 4px 2px 0'>"
            f"#{_escape(h.get('hashtag'))} <span style='color:#9ca3af'>·{h.get('count')}</span></span>"
            for h in hashtags
        )
        parts.append(f"<div style='margin-bottom:10px'><b style='font-size:11px;color:#6b7280'>TRENDING HASHTAGS</b><br>{chips}</div>")
    posts = viral.get("top_posts") or []
    if posts:
        bullets = []
        for p in posts[:3]:
            txt = _escape((p.get("text") or "")[:160])
            eng = p.get("engagement") or p.get("plays") or p.get("likes") or 0
            plat = _escape(p.get("platform") or "—")
            bullets.append(f"<li style='margin-bottom:6px;line-height:1.5'><b>[{plat}]</b> {txt}… <span style='color:#9ca3af;font-size:11px'>({eng:,} eng)</span></li>")
        parts.append(f"<div><b style='font-size:11px;color:#6b7280'>VIRAL POSTS WORTH MIRRORING</b><ul style='margin:6px 0 0 18px;font-size:12px;color:#374151'>{''.join(bullets)}</ul></div>")
    fb = viral.get("competitor_fb_ads") or []
    if fb:
        bullets = []
        for ad in fb[:3]:
            body = _escape((ad.get("body") or "")[:150])
            page = _escape(ad.get("page") or "—")
            bullets.append(f"<li style='margin-bottom:6px;line-height:1.5'><b>{page}:</b> {body}…</li>")
        parts.append(f"<div style='margin-top:10px'><b style='font-size:11px;color:#6b7280'>COMPETITOR ADS RUNNING (defensive watch)</b><ul style='margin:6px 0 0 18px;font-size:12px;color:#374151'>{''.join(bullets)}</ul></div>")
    return "".join(parts) if parts else "<i style='color:#9ca3af;font-size:12px'>No viral signals captured this week.</i>"


def _render_higgsfield_html(suggestions: list) -> str:
    if not suggestions:
        return ""
    rows = []
    for s in suggestions:
        rows.append(
            f"<div style='border:1px dashed #d1d5db;border-radius:6px;padding:10px 12px;margin-bottom:8px;background:#fafafa'>"
            f"<div style='font-size:12px;font-weight:700;color:{CB247_DARK};margin-bottom:4px'>"
            f"{_escape(s.get('shot'))}</div>"
            f"<div style='font-family:Menlo,Monaco,monospace;font-size:11px;color:#374151;line-height:1.5;background:#fff;padding:8px;border-radius:4px;border:1px solid #f0f2f5'>"
            f"{_escape(s.get('prompt'))}</div>"
            f"</div>"
        )
    return (
        f"<div style='margin-top:10px'>"
        f"<div style='font-size:11px;color:#6b7280;margin-bottom:6px'>"
        f"<b>FALLBACK</b> — if this shot can't be captured in-club, use Higgsfield with:</div>"
        + "".join(rows) + "</div>"
    )


def _render_compliance_html(reminders: list) -> str:
    items = "".join(f"<li style='margin-bottom:4px;line-height:1.5'>{_escape(r)}</li>" for r in reminders)
    return (
        f"<ul style='margin:6px 0 0 18px;font-size:12px;color:#7f1d1d;line-height:1.5'>{items}</ul>"
    )


def _creative_section(action: dict) -> str:
    """The extra section appended to Shauna's per-action brief."""
    if _build_creative_context is None:
        return ""
    try:
        ctx = _build_creative_context(action)
    except Exception as e:
        return f"<div class='section'><div class='label'>Creative Context</div><i style='color:#9ca3af;font-size:12px'>Context unavailable: {_escape(str(e))}</i></div>"

    winners   = ctx.get("past_winners") or []
    viral     = ctx.get("viral") or {}
    higgs     = ctx.get("higgsfield_suggestions") or []
    compliance = ctx.get("compliance_reminders") or []

    return f"""<div class="section" style="background:#fafbfc">
    <div class="label" style="color:{CB247_TEAL_DEEP}">Shauna's Creative Context — Past Winners</div>
    <div style="font-size:12px;color:#6b7280;margin-bottom:8px">Top Meta ads from last week. Mirror the angle / hook / location split.</div>
    {_render_winners_html(winners)}
  </div>
  <div class="section">
    <div class="label" style="color:{CB247_TEAL_DEEP}">Viral Signals — What's Hot This Week</div>
    {_render_viral_html(viral)}
  </div>
  <div class="section" style="background:#fef2f2">
    <div class="label" style="color:#991b1b">Compliance — Read Before Shooting</div>
    {_render_compliance_html(compliance)}
  </div>
  <div class="section">
    <div class="label" style="color:{CB247_TEAL_DEEP}">Higgsfield AI Fallback</div>
    {_render_higgsfield_html(higgs) or "<i style='color:#9ca3af;font-size:12px'>No specific Higgsfield prompts for this action — try to capture in-club.</i>"}
  </div>"""


def render_brief(action, promos):
    aid       = action.get("id", "")
    title     = _escape(action.get("title", "Untitled action"))
    # Description is rendered RAW (not _escape'd) so action authors can
    # embed clickable links, bold person names, and <code> for filenames.
    # 12 Jun 2026 — Tia: HTML tags were leaking as text in the brief.
    # The trade-off: action authors must produce trusted markup. All
    # current authors (strategist YAMLs + dashboard hand-coded actions)
    # are internal, so this is safe. Bold/code/anchor/br only — no
    # external sources feed this field.
    desc_raw = action.get("description", "(No description)")
    desc     = desc_raw.replace("\n", "<br>") if desc_raw else "(No description)"
    owner     = _escape(action.get("owner", "Team"))
    role      = _escape(action.get("owner_role", ""))
    priority  = action.get("priority", "P3")
    category  = action.get("category", "")
    source    = action.get("source_page", "")
    effort    = _escape(action.get("effort_hours", ""))

    # Primary KPI projection → caption-style line
    pks = action.get("projected_kpis") or []
    primary = pks[0] if pks else {}
    kpi_metric  = _escape(primary.get("metric", ""))
    kpi_base    = primary.get("baseline", "?")
    kpi_target  = primary.get("target", "?")
    kpi_delta_min = primary.get("delta_min", None)
    kpi_delta_max = primary.get("delta_max", None)
    kpi_window  = _escape(primary.get("measurement_window_days", ""))
    if kpi_metric == "qualitative_assessment":
        caption_html = f"<b>Qualitative action</b> — verdict captured by the team after the measurement window ({kpi_window} days) elapses."
    elif kpi_metric:
        if kpi_target not in (None, "?"):
            target_str = f"<b>{_escape(kpi_target)}</b>"
        elif kpi_delta_min is not None and kpi_delta_max is not None:
            target_str = f"<b>+{_escape(kpi_delta_min)}–{_escape(kpi_delta_max)}</b>"
        else:
            target_str = "<b>—</b>"
        caption_html = (
            f"<b>{kpi_metric}</b>: {_escape(kpi_base)} → {target_str}"
            + (f" · measured over {kpi_window} days" if kpi_window else "")
        )
    else:
        caption_html = "No projected KPI on this action."

    # All KPI projections (table)
    all_kpis_html = ""
    if len(pks) > 1:
        rows = []
        for k in pks:
            m = _escape(k.get("metric", ""))
            b = _escape(k.get("baseline", "?"))
            t = _escape(k.get("target", "?"))
            w = _escape(k.get("measurement_window_days", ""))
            rows.append(f"<tr><td style='padding:6px 8px;border-bottom:1px solid #f0f2f5'>{m}</td><td style='padding:6px 8px;border-bottom:1px solid #f0f2f5;text-align:right'>{b}</td><td style='padding:6px 8px;border-bottom:1px solid #f0f2f5;text-align:right'><b>{t}</b></td><td style='padding:6px 8px;border-bottom:1px solid #f0f2f5;text-align:right;color:#6b7280'>{w}d</td></tr>")
        all_kpis_html = f"""<div class="section">
    <div class="label">All Projected KPIs ({len(pks)})</div>
    <table style="width:100%;border-collapse:collapse;font-size:12px;margin-top:6px">
      <thead><tr style="border-bottom:2px solid #e5e7eb">
        <th style="padding:6px 8px;text-align:left;font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:.05em">Metric</th>
        <th style="padding:6px 8px;text-align:right;font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:.05em">Baseline</th>
        <th style="padding:6px 8px;text-align:right;font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:.05em">Target</th>
        <th style="padding:6px 8px;text-align:right;font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:.05em">Window</th>
      </tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </div>"""

    badge = CATEGORY_BADGE.get(source, CATEGORY_BADGE.get(category, {"bg": "#f0f0f0", "fg": "#374151"}))
    prio_color = PRIORITY_COLOR.get(priority, CB247_TEAL)

    cat_label = (source or category or "CB247").upper().replace("-", " ")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} · CB247 Brief</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f0f2f5;color:{CB247_DARK};padding:24px}}
  .brief-card{{max-width:740px;margin:0 auto;background:#fff;border-radius:12px;box-shadow:0 2px 16px rgba(0,0,0,.08);overflow:hidden}}
  .brief-header{{background:{CB247_DARK};padding:24px 28px;color:#fff}}
  .brief-header .logo{{font-size:13px;color:{CB247_TEAL};font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px}}
  .brief-header h1{{font-size:20px;font-weight:700;line-height:1.3}}
  .meta-row{{display:flex;gap:10px;flex-wrap:wrap;padding:16px 28px;background:#f8f9fa;border-bottom:1px solid #e5e7eb}}
  .meta-chip{{border-radius:99px;padding:4px 12px;font-size:11px;font-weight:700}}
  .section{{padding:18px 28px;border-bottom:1px solid #f0f2f5}}
  .section:last-child{{border-bottom:none}}
  .label{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:#6b7280;margin-bottom:8px}}
  .instructions{{font-size:13px;line-height:1.8;color:#374151;white-space:pre-wrap}}
  .caption-box{{background:{CB247_TEAL_MIST};border-left:3px solid {CB247_TEAL};border-radius:0 8px 8px 0;padding:14px 16px;font-size:13px;line-height:1.7;color:{CB247_DARK}}}
  .src{{display:inline-block;background:{CB247_TEAL_MIST};color:{CB247_TEAL_DEEP};border-radius:99px;padding:4px 14px;font-size:12px;font-weight:700}}
  .approval-section{{background:#fffbeb;padding:18px 28px}}
  .approval-section .label{{color:#92400e}}
  .approval-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:14px}}
  .appr-btn{{border:2px solid #e5e7eb;border-radius:8px;padding:12px 8px;text-align:center;cursor:pointer;transition:all .15s;font-size:12px;font-weight:700;background:#fff}}
  .appr-btn:hover{{border-color:{CB247_TEAL};background:{CB247_TEAL_MIST}}}
  .appr-btn.selected-approved{{border-color:#16a34a;background:#dcfce7;color:#166534}}
  .appr-btn.selected-adjustment{{border-color:#d97706;background:#fef9c3;color:#92400e}}
  .appr-btn.selected-rejected{{border-color:#dc2626;background:#fee2e2;color:#991b1b}}
  .notes-area{{width:100%;border:1px solid #e5e7eb;border-radius:8px;padding:10px 12px;font-size:13px;font-family:inherit;resize:vertical;min-height:80px}}
  .notes-area:focus{{outline:none;border-color:{CB247_TEAL}}}
  .save-btn{{background:{CB247_TEAL_DEEP};color:#fff;border:none;border-radius:8px;padding:10px 24px;font-size:13px;font-weight:700;cursor:pointer;margin-top:10px}}
  .save-btn:hover{{background:#1f5e57}}
  .saved-notice{{display:none;color:#16a34a;font-size:12px;font-weight:600;margin-top:8px}}
  .footer{{text-align:center;padding:16px;font-size:11px;color:#9ca3af}}
  @media print{{body{{background:#fff}}.brief-card{{box-shadow:none}}.approval-section{{display:none}}}}
</style>
</head>
<body>
<div class="brief-card">
  <div class="brief-header">
    <div class="logo">ChasingBetter247 — Action Brief</div>
    <h1>{title}</h1>
  </div>
  <div class="meta-row">
    <span class="meta-chip" style="background:{badge['bg']};color:{badge['fg']}">{cat_label}</span>
    <span class="meta-chip" style="background:{CB247_TEAL_MIST};color:{CB247_TEAL_DEEP}">{owner}{(' · ' + role) if role else ''}</span>
    <span class="meta-chip" style="background:{prio_color};color:#fff">{priority}</span>
    {f'<span class="meta-chip" style="background:#f3f4f6;color:#374151">Effort: {effort}h</span>' if effort else ''}
  </div>
  <div class="section">
    <div class="label">Instructions for {owner}</div>
    <div class="instructions">{desc}</div>
  </div>
  <div class="section">
    <div class="label">Primary Projected KPI</div>
    <div class="caption-box">{caption_html}</div>
  </div>
  {all_kpis_html}
  <div class="section">
    <div class="label">Source Page · Action ID</div>
    <span class="src">{source or '–'}</span>
    <code style="background:#f3f4f6;padding:3px 8px;border-radius:3px;font-size:11px;color:#6b7280;margin-left:8px">{_escape(aid)}</code>
  </div>

  {_promo_block(action, promos)}
  {_draft_block(action)}
  {_creative_section(action) if _is_creative_action(action) else ""}

  <div class="approval-section">
    <div class="label">Review — {priority}</div>
    <div class="approval-grid">
      <div class="appr-btn" id="btn-approved" onclick="setApproval('approved')">Approved<br><span style="font-size:10px;font-weight:400">Ready to go</span></div>
      <div class="appr-btn" id="btn-adjustment" onclick="setApproval('adjustment')">Needs Adjustment<br><span style="font-size:10px;font-weight:400">Review notes below</span></div>
      <div class="appr-btn" id="btn-rejected" onclick="setApproval('rejected')">Rejected<br><span style="font-size:10px;font-weight:400">Do not proceed</span></div>
    </div>
    <div class="label" style="margin-bottom:6px">Notes / Adjustments</div>
    <textarea class="notes-area" id="approval-notes" placeholder="Add adjustment notes or feedback here..."></textarea>
    <br>
    <button class="save-btn" onclick="saveApproval()">Save Review</button>
    <div class="saved-notice" id="saved-notice">Saved locally</div>
  </div>
  <div style="padding:16px 28px;background:#fafbfc;border-top:1px solid #f0f2f5;text-align:center">
    <a href="../index.html" style="display:inline-block;background:{CB247_TEAL_DEEP};color:#fff;text-decoration:none;padding:10px 22px;border-radius:6px;font-size:12.5px;font-weight:700;font-family:inherit">← Back to Marketing OS</a>
    <div style="font-size:10.5px;color:#9ca3af;margin-top:10px">CB247 Marketing OS · Action Brief · Generated {datetime.now():%d %b %Y}</div>
  </div>
</div>
<script>
const KEY = 'cb247-brief-{aid}';
function load() {{
  const s = JSON.parse(localStorage.getItem(KEY)||'{{}}');
  if(s.status) setApproval(s.status, false);
  if(s.notes) document.getElementById('approval-notes').value = s.notes;
}}
function setApproval(val, save=true) {{
  ['approved','adjustment','rejected'].forEach(v => {{
    const btn = document.getElementById('btn-'+v);
    btn.className = 'appr-btn' + (v===val ? ' selected-'+v : '');
  }});
  if(save) {{ const s = JSON.parse(localStorage.getItem(KEY)||'{{}}'); s.status=val; localStorage.setItem(KEY,JSON.stringify(s)); }}
}}
function saveApproval() {{
  const s = JSON.parse(localStorage.getItem(KEY)||'{{}}');
  s.notes = document.getElementById('approval-notes').value;
  localStorage.setItem(KEY, JSON.stringify(s));
  const n = document.getElementById('saved-notice');
  n.style.display='block'; setTimeout(()=>n.style.display='none',2500);
}}
load();
</script>
</body>
</html>
"""


def main():
    if not STATE_FILE.exists():
        print(f"[cb247-briefs] {STATE_FILE} not found — skipping")
        return 1

    BRIEFS_DIR.mkdir(parents=True, exist_ok=True)
    d = json.loads(STATE_FILE.read_text())
    actions = d.get("actions") or []
    if not actions:
        print("[cb247-briefs] No actions in queue — nothing to generate")
        return 0

    promos = _load_promo_lookup()

    generated = 0
    for action in actions:
        aid = action.get("id")
        if not aid:
            continue
        out = BRIEFS_DIR / f"{_safe_filename(aid)}.html"
        out.write_text(render_brief(action, promos))
        generated += 1

    print(f"[cb247-briefs] Generated {generated} action briefs → {BRIEFS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
