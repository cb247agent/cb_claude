"""
generate_mwcc_briefs.py — Generate per-action brief HTML files for MWCC.

Mirrors CB247's brief format (docs/briefs/p*.html). One HTML file per MWCC
Work Queue action, named docs/briefs/mwcc-{action_id}.html.

The MWCC modal's "View Brief" link points to these files. CB247 has 60+
per-action briefs in docs/briefs/ — this script gives MWCC the same.

Wired into scripts/weekly-report-mwcc.sh AFTER mwcc_sync_to_supabase
so briefs regenerate every Monday cron.

USAGE: python scripts/generate_mwcc_briefs.py
"""
import json
import re
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = BASE_DIR / "state" / "mwcc-work-queue.json"
BRIEFS_DIR = BASE_DIR / "docs" / "briefs"

# MWCC purple palette (matches docs/index.html CSS vars)
MWCC_PURPLE = "#8b6fd9"
MWCC_PURPLE_DEEP = "#5b3ec7"
MWCC_PURPLE_MIST = "#f8f4ff"
MWCC_PURPLE_SOFT = "#d4c5f2"

# Category → badge colours
CATEGORY_BADGE = {
    "seo-organic":     {"bg": "#f3e8ff", "fg": "#6b21a8"},
    "seo":             {"bg": "#f3e8ff", "fg": "#6b21a8"},
    "meta-ads":        {"bg": "#ede9fe", "fg": "#5b21b6"},
    "google-ads":      {"bg": "#fef3c7", "fg": "#92400e"},
    "enrolment":       {"bg": "#f0fdf4", "fg": "#15803d"},
    "organic-social":  {"bg": "#fce7f3", "fg": "#9d174d"},
    "gbp":             {"bg": "#dcfce7", "fg": "#166534"},
}

PRIORITY_COLOR = {
    "P1": "#ef4444",
    "P2": "#f59e0b",
    "P3": MWCC_PURPLE,
    "P4": "#6b7280",
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
    """Map action id → safe filename component."""
    return re.sub(r"[^a-z0-9_-]", "-", action_id.lower())


def _draft_block(action):
    """Return a 'Draft — Ready for Review' section if the action has draft_link.
    Mirrors CB247's #modal-draft-link-wrap pattern."""
    draft = action.get("draft_link") or action.get("draftLink")
    if not draft:
        return ""
    # If relative path, prefix with ../ so it resolves from docs/briefs/
    draft_url = draft if draft.startswith("http") else f"../{draft}"
    return f"""<div class="section" style="background:{MWCC_PURPLE_MIST};border-left:4px solid {MWCC_PURPLE};border-radius:4px;padding:14px 18px;margin:14px 0">
    <div class="label" style="color:{MWCC_PURPLE_DEEP};margin-bottom:8px">Draft — Ready for Review</div>
    <a href="{draft_url}" target="_blank" style="display:inline-block;background:{MWCC_PURPLE};color:#fff;padding:10px 22px;border-radius:5px;text-decoration:none;font-weight:700;font-size:13px">Open Draft Blog →</a>
    <div style="font-size:11px;color:#6b7280;margin-top:8px">Share with Kelley for brand QC, then Denver for COO sign-off before Mark publishes to Webflow.</div>
  </div>"""


def render_brief(action):
    aid       = action.get("id", "")
    title     = _escape(action.get("title", "Untitled action"))
    desc      = _escape(action.get("description", "(No description)"))
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
    kpi_delta   = primary.get("delta", None)
    kpi_window  = _escape(primary.get("measurement_window", ""))
    caption_html = (
        f"<b>{kpi_metric}</b>: {_escape(kpi_base)} → <b>{_escape(kpi_target)}</b>"
        + (f" (target delta {_escape(kpi_delta)})" if kpi_delta is not None else "")
        + (f" · measured over {kpi_window}" if kpi_window else "")
        if kpi_metric else "Qualitative action — no projected KPI."
    )

    badge = CATEGORY_BADGE.get(source, CATEGORY_BADGE.get(category, {"bg": "#f0f0f0", "fg": "#374151"}))
    prio_color = PRIORITY_COLOR.get(priority, MWCC_PURPLE)

    cat_label = (source or category or "MWCC").upper().replace("-", " ")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} · MWCC Brief</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f0f2f5;color:#1a1a2e;padding:24px}}
  .brief-card{{max-width:740px;margin:0 auto;background:#fff;border-radius:12px;box-shadow:0 2px 16px rgba(0,0,0,.08);overflow:hidden}}
  .brief-header{{background:{MWCC_PURPLE_DEEP};padding:24px 28px;color:#fff}}
  .brief-header .logo{{font-size:13px;color:{MWCC_PURPLE_SOFT};font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px}}
  .brief-header h1{{font-size:20px;font-weight:700;line-height:1.3}}
  .meta-row{{display:flex;gap:10px;flex-wrap:wrap;padding:16px 28px;background:#f8f9fa;border-bottom:1px solid #e5e7eb}}
  .meta-chip{{border-radius:99px;padding:4px 12px;font-size:11px;font-weight:700}}
  .section{{padding:18px 28px;border-bottom:1px solid #f0f2f5}}
  .section:last-child{{border-bottom:none}}
  .label{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:#6b7280;margin-bottom:8px}}
  .instructions{{font-size:13px;line-height:1.8;color:#374151;white-space:pre-wrap}}
  .caption-box{{background:{MWCC_PURPLE_MIST};border-left:3px solid {MWCC_PURPLE};border-radius:0 8px 8px 0;padding:14px 16px;font-size:13px;line-height:1.7;color:#1a1a2e}}
  .src{{display:inline-block;background:{MWCC_PURPLE_MIST};color:{MWCC_PURPLE_DEEP};border-radius:99px;padding:4px 14px;font-size:12px;font-weight:700}}
  .approval-section{{background:#fffbeb;padding:18px 28px}}
  .approval-section .label{{color:#92400e}}
  .approval-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:14px}}
  .appr-btn{{border:2px solid #e5e7eb;border-radius:8px;padding:12px 8px;text-align:center;cursor:pointer;transition:all .15s;font-size:12px;font-weight:700;background:#fff}}
  .appr-btn:hover{{border-color:{MWCC_PURPLE};background:{MWCC_PURPLE_MIST}}}
  .appr-btn.selected-approved{{border-color:#16a34a;background:#dcfce7;color:#166534}}
  .appr-btn.selected-adjustment{{border-color:#d97706;background:#fef9c3;color:#92400e}}
  .appr-btn.selected-rejected{{border-color:#dc2626;background:#fee2e2;color:#991b1b}}
  .notes-area{{width:100%;border:1px solid #e5e7eb;border-radius:8px;padding:10px 12px;font-size:13px;font-family:inherit;resize:vertical;min-height:80px}}
  .notes-area:focus{{outline:none;border-color:{MWCC_PURPLE}}}
  .save-btn{{background:{MWCC_PURPLE_DEEP};color:#fff;border:none;border-radius:8px;padding:10px 24px;font-size:13px;font-weight:700;cursor:pointer;margin-top:10px}}
  .save-btn:hover{{background:#4a30a3}}
  .saved-notice{{display:none;color:#16a34a;font-size:12px;font-weight:600;margin-top:8px}}
  .footer{{text-align:center;padding:16px;font-size:11px;color:#9ca3af}}
  @media print{{body{{background:#fff}}.brief-card{{box-shadow:none}}.approval-section{{display:none}}}}
</style>
</head>
<body>
<div class="brief-card">
  <div class="brief-header">
    <div class="logo">MyWorld Childcare — Action Brief</div>
    <h1>{title}</h1>
  </div>
  <div class="meta-row">
    <span class="meta-chip" style="background:{badge['bg']};color:{badge['fg']}">{cat_label}</span>
    <span class="meta-chip" style="background:{MWCC_PURPLE_MIST};color:{MWCC_PURPLE_DEEP}">{owner}{(' · ' + role) if role else ''}</span>
    <span class="meta-chip" style="background:{prio_color};color:#fff">{priority}</span>
    {f'<span class="meta-chip" style="background:#f3f4f6;color:#374151">Effort: {effort}</span>' if effort else ''}
  </div>
  <div class="section">
    <div class="label">Instructions for {owner}</div>
    <div class="instructions">{desc}</div>
  </div>
  <div class="section">
    <div class="label">Projected KPI Target</div>
    <div class="caption-box">{caption_html}</div>
  </div>
  <div class="section">
    <div class="label">Source Page</div>
    <span class="src">{source or '–'}</span>
  </div>

  {_draft_block(action)}

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
  <div class="footer">MWCC Marketing OS · Action Brief · Generated {datetime.now():%d %b %Y}</div>
</div>
<script>
const KEY = 'mwcc-brief-{aid}';
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
        print(f"[mwcc-briefs] {STATE_FILE} not found — skipping")
        return 1

    BRIEFS_DIR.mkdir(parents=True, exist_ok=True)
    d = json.loads(STATE_FILE.read_text())
    actions = d.get("actions") or []
    if not actions:
        print("[mwcc-briefs] No actions in queue — nothing to generate")
        return 0

    generated = 0
    for action in actions:
        aid = action.get("id")
        if not aid:
            continue
        out = BRIEFS_DIR / f"mwcc-{_safe_filename(aid)}.html"
        out.write_text(render_brief(action))
        generated += 1

    print(f"[mwcc-briefs] Generated {generated} action briefs → {BRIEFS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
