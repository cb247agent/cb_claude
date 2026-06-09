"""
inject-seo-extras.py — Inject SEO data into docs/index.html inline.

Same pattern as bake-mwcc-report.py: replaces a sentinel <script id="seo-extras-block">
with a JSON payload. This keeps the SEO page improvements live without re-running
the (currently stale) CB247 baker, which would wipe the MWCC/KB/Sparrows render
functions added directly to docs/index.html.

Sources:
  state/ahrefs-snapshot-YYYY-MM-DD.json — Newest available Ahrefs snapshot.
                                          Picked dynamically by date in filename
                                          (was hardcoded to 1 Jun; now follows the
                                          newest export landed via either
                                          pull_ahrefs.py or parse_cb247_ahrefs_csvs.py).
  state/screaming-frog-data.json        — Technical crawl (errors, warnings)
  state/ga4-data.json                   — GA4 current + previous (for organic WoW)
  state/gsc-data.json                   — GSC date range (for dynamic period label)
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
INDEX_PATH = BASE_DIR / "docs" / "index.html"


def _newest_ahrefs_snapshot():
    """Find the newest state/ahrefs-snapshot-*.json by the date in the filename.

    Filename format: ahrefs-snapshot-YYYY-MM-DD.json
    Sort by the embedded date (not mtime) so a manually-touched older snapshot
    doesn't override a fresh export.
    """
    pattern = re.compile(r"ahrefs-snapshot-(\d{4}-\d{2}-\d{2})\.json$")
    candidates = []
    for f in STATE_DIR.glob("ahrefs-snapshot-*.json"):
        m = pattern.match(f.name)
        if m:
            candidates.append((m.group(1), f))
    if not candidates:
        return None
    candidates.sort(key=lambda c: c[0], reverse=True)
    return candidates[0][1]


def _load(filename, default=None):
    p = STATE_DIR / filename
    if not p.exists():
        return default if default is not None else {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return default if default is not None else {}


def _safe_int(v, default=0):
    try:
        return int(float(v))
    except Exception:
        return default


def build_seo_extras():
    # Pick the newest dated snapshot — previously hardcoded to 1 Jun, now follows
    # whatever parse_cb247_ahrefs_csvs.py or pull_ahrefs.py last wrote.
    snapshot = _newest_ahrefs_snapshot()
    if snapshot:
        try:
            ahrefs_frozen = json.loads(snapshot.read_text())
        except Exception:
            ahrefs_frozen = {}
    else:
        # Backward-compat fallback (older snapshot if no dated one exists)
        ahrefs_frozen = _load("ahrefs-snapshot-2026-06-01.json", default={})
    frog = _load("screaming-frog-data.json", default={})
    ga4 = _load("ga4-data.json", default={})
    gsc = _load("gsc-data.json", default={})

    # ── GA4 organic-channel WoW (Organic Search row from traffic_sources) ──
    def _organic_row(srcs):
        for s in srcs or []:
            if (s.get("sessionDefaultChannelGroup") or "").lower() == "organic search":
                return {
                    "sessions": _safe_int(s.get("sessions")),
                    "conversions": _safe_int(s.get("conversions")),
                }
        return {"sessions": 0, "conversions": 0}

    cur_org = _organic_row(ga4.get("traffic_sources"))
    prev_org = _organic_row((ga4.get("previous") or {}).get("traffic_sources"))

    def _pct(cur, prev):
        if not prev:
            return None
        return round(((cur - prev) / prev) * 100, 1)

    # GA4 previous period doesn't carry traffic_sources channel split — fall back
    # to overall WoW (all channels) and label it honestly in the UI.
    overall_cur_sessions  = _safe_int((ga4.get("current") or {}).get("sessions"))
    overall_prev_sessions = _safe_int((ga4.get("previous") or {}).get("sessions"))
    overall_cur_conv      = _safe_int((ga4.get("current") or {}).get("conversions"))
    overall_prev_conv     = _safe_int((ga4.get("previous") or {}).get("conversions"))

    # ── Tech health (errors + warnings only — skip notices) ──
    tech_issues = [
        {
            "name": i.get("name", ""),
            "priority": i.get("priority", "notice"),
            "count": i.get("count", 0),
            "description": i.get("description", ""),
            "affected_urls": (i.get("affected_urls") or [])[:5],
        }
        for i in (frog.get("issues") or [])
        if i.get("priority") in ("error", "warning")
    ][:10]

    extras = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gsc_date_range": gsc.get("date_range") or {},
        "ga4_organic": {
            "current_sessions":     cur_org["sessions"],
            "current_conversions":  cur_org["conversions"],
            "previous_sessions":    prev_org["sessions"],
            "previous_conversions": prev_org["conversions"],
            "sessions_wow_pct":     _pct(cur_org["sessions"], prev_org["sessions"]),
            "conversions_wow_pct":  _pct(cur_org["conversions"], prev_org["conversions"]),
            # Fallback: overall (all-channel) WoW when channel-split prev is missing
            "overall_sessions_wow_pct":    _pct(overall_cur_sessions, overall_prev_sessions),
            "overall_conversions_wow_pct": _pct(overall_cur_conv,    overall_prev_conv),
        },
        "ahrefs_frozen": ahrefs_frozen,
        "tech_health": {
            "crawled_at": frog.get("date_crawled") or "",
            "errors":     (frog.get("summary") or {}).get("errors", 0),
            "warnings":   (frog.get("summary") or {}).get("warnings", 0),
            "notices":    (frog.get("summary") or {}).get("notices", 0),
            "total_issue_types": (frog.get("summary") or {}).get("total_issue_types", 0),
            "issues": tech_issues,
        },
    }
    return extras


def inject():
    extras = build_seo_extras()
    payload = json.dumps(extras, indent=2, default=str)

    html = INDEX_PATH.read_text(encoding="utf-8")
    new_block = (
        '<script id="seo-extras-block">\n'
        '// CB247 SEO extras — injected by scripts/inject-seo-extras.py\n'
        '// Sources: frozen Ahrefs (1 Jun), Screaming Frog (1 Jun), live GA4 organic, live GSC\n'
        f'window.SEO_EXTRAS = {payload};\n'
        '</script>'
    )

    if 'id="seo-extras-block"' in html:
        updated = re.sub(
            r'<script id="seo-extras-block">.*?</script>',
            lambda _: new_block,
            html,
            flags=re.DOTALL,
        )
        action = "replaced"
    else:
        # First-run: insert just before window.DASHBOARD_DATA script (or </body> fallback)
        # Anchor on "window.DASHBOARD_DATA = {" not just "window.DASHBOARD_DATA"
        # because other inject blocks' comments also contain "window.DASHBOARD_DATA".
        anchor = 'window.DASHBOARD_DATA = {'
        idx = html.find(anchor)
        if idx == -1:
            updated = html.replace("</body>", new_block + "\n</body>")
        else:
            # Find the <script tag opening before DASHBOARD_DATA
            script_open = html.rfind("<script>", 0, idx)
            if script_open == -1:
                updated = html.replace("</body>", new_block + "\n</body>")
            else:
                updated = html[:script_open] + new_block + "\n" + html[script_open:]
        action = "inserted"

    if updated == html:
        print("⚠️  No change to index.html — sentinel not found and no anchor matched.")
        return

    INDEX_PATH.write_text(updated, encoding="utf-8")
    print(f"✅ SEO extras {action} → docs/index.html")
    print(f"   - Ahrefs as-of: {(extras['ahrefs_frozen'].get('_meta') or {}).get('as_of_date', '—')}")
    print(f"   - Frog crawl:   {extras['tech_health']['crawled_at']}")
    print(f"   - Tech issues:  {extras['tech_health']['errors']} errors · {extras['tech_health']['warnings']} warnings")
    print(f"   - GA4 organic:  {extras['ga4_organic']['current_sessions']} sessions "
          f"(WoW {extras['ga4_organic']['sessions_wow_pct']}%) · "
          f"{extras['ga4_organic']['current_conversions']} conv")


if __name__ == "__main__":
    inject()
