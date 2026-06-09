"""
inject-google-ads.py — Inject the latest Google Ads block into docs/index.html.

Same inline-injection pattern as inject-meta-ads.py and inject-seo-extras.py.
Reads state/ads-data.json google_ads (newest week first) and writes:
  <script id="google-ads-block">window.GOOGLE_ADS_LIVE = {...}</script>

The dashboard's main app patches window.DASHBOARD_DATA.google_ads with this
live override at startup (single line after `const D = window.DASHBOARD_DATA`),
so renderGoogleAds, renderOverview, and renderGroupOverview all read fresh
weekly numbers without needing to run the destructive baker.

Run after pull_weekly.py (which itself calls this script):
  python scripts/pull_google_ads.py
  python scripts/inject-google-ads.py
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
INDEX_PATH = BASE_DIR / "docs" / "index.html"
ADS_DATA_FILE = STATE_DIR / "ads-data.json"          # weekly summary (history + combined)
GADS_DATA_FILE = STATE_DIR / "google-ads-data.json"  # rich tables (search terms, QS, conv actions)


def build_payload():
    if not ADS_DATA_FILE.exists():
        return None
    try:
        ads_data = json.loads(ADS_DATA_FILE.read_text())
    except Exception as e:
        print(f"[google-ads] could not parse {ADS_DATA_FILE}: {e}")
        return None

    weeks = ads_data.get("google_ads") or []
    if not weeks:
        return None

    latest = weeks[0]
    history = weeks[:4]   # 4 weeks for trend chart

    combined = latest.get("combined") or {}

    # ── Pull RICH tables from google-ads-data.json (this week only) ────────
    # ads-data.json has only summary stats. google-ads-data.json has the full
    # search_terms / quality_scores / conversion_actions arrays needed by the
    # dashboard's "Search Terms", "Quality Score", "Conversion Tracking"
    # sections. We pull from the latter and merge into the payload.
    #
    # Date-filter integrity: google-ads-data.json is written by the same pull
    # script for the same week as ads-data.json's latest entry, so the
    # search_terms / QS / conv_actions are inherently scoped to the same
    # 30May-05Jun window. Verified 09 Jun 2026.
    search_terms = []
    quality_scores = []
    conversion_actions = []
    if GADS_DATA_FILE.exists():
        try:
            gads = json.loads(GADS_DATA_FILE.read_text())
            search_terms       = gads.get("search_terms")       or []
            quality_scores     = gads.get("quality_scores")     or []
            conversion_actions = gads.get("conversion_actions") or []
        except Exception as e:
            print(f"[google-ads] could not parse {GADS_DATA_FILE}: {e}")

    # ── Build campaigns with field aliases the render expects ──────────────
    # Render reads c.impr (NOT c.impressions), c.conv (already aliased in
    # ads-data.json), c.cpa (computed). Map source → render shape.
    campaigns_raw = latest.get("campaigns") or []
    campaigns_for_render = []
    for c in campaigns_raw:
        spend = c.get("spend", 0)
        conv = c.get("conv", 0)
        # Pull impressions from google-ads-data.json if available
        impr = c.get("impr") or c.get("impressions") or 0
        # If not in ads-data.json campaign, look up by name in gads campaigns
        if not impr and GADS_DATA_FILE.exists():
            try:
                gads = json.loads(GADS_DATA_FILE.read_text())
                for gc in gads.get("campaigns", []):
                    if gc.get("name") == c.get("name"):
                        impr = gc.get("impressions") or 0
                        break
            except Exception:
                pass
        campaigns_for_render.append({
            **c,
            "impr": impr,
            "cpa":  (spend / conv) if (conv and conv > 0) else 0,
        })

    return {
        "generated_at":  datetime.now(timezone.utc).isoformat(),
        "week_label":    latest.get("week_label", ""),
        "date_start":    latest.get("date_start", ""),
        "date_end":      latest.get("date_end", ""),
        # Match dashboard's expected D.google_ads shape — the render code
        # reads: D.google_ads.malaga.spend, D.google_ads.ellenbrook.cpa, etc.
        "malaga":     latest.get("malaga") or {},
        "ellenbrook": latest.get("ellenbrook") or {},
        "combined":   combined,
        "campaigns":  campaigns_for_render,
        # Top-level shorthand for renderGAds() KPI cards. Render reads
        # ads.spend / ads.clicks / ads.convs (plural-s) / ads.cpa at TOP
        # level — not nested under combined. Bug spotted 09 Jun 2026.
        "spend":      combined.get("spend", 0),
        "clicks":     combined.get("clicks", 0),
        "convs":      combined.get("conv", 0),
        "cpa":        combined.get("cpa", 0),
        # Rich tables for Search Terms / QS / Conv Tracking sections
        # Sourced from state/google-ads-data.json (same date scope as latest week)
        "search_terms":       search_terms,
        "quality_scores":     quality_scores,
        "conversion_actions": conversion_actions,
        # Weekly trend for line/bar charts
        "history": [
            {
                "week_label": w.get("week_label", ""),
                "combined":   w.get("combined") or {},
                "malaga":     w.get("malaga") or {},
                "ellenbrook": w.get("ellenbrook") or {},
            }
            for w in history
        ],
    }


def inject():
    payload = build_payload()
    if payload is None:
        print("[google-ads] No Google Ads data to inject — run pull_google_ads.py first.")
        return

    json_payload = json.dumps(payload, indent=2, default=str)
    html = INDEX_PATH.read_text(encoding="utf-8")

    new_block = (
        '<script id="google-ads-block">\n'
        '// CB247 Google Ads — live override for window.DASHBOARD_DATA.google_ads\n'
        '// Auto-generated by scripts/inject-google-ads.py from state/ads-data.json\n'
        f'window.GOOGLE_ADS_LIVE = {json_payload};\n'
        '</script>'
    )

    if 'id="google-ads-block"' in html:
        updated = re.sub(
            r'<script id="google-ads-block">.*?</script>',
            lambda _: new_block,
            html,
            flags=re.DOTALL,
        )
        action = "replaced"
    else:
        # Insert just before window.DASHBOARD_DATA, like sibling injectors.
        # Anchor on the literal assignment "window.DASHBOARD_DATA = {" rather
        # than just "window.DASHBOARD_DATA" — other inject blocks' comments
        # also contain "window.DASHBOARD_DATA" and would match first.
        anchor = 'window.DASHBOARD_DATA = {'
        idx = html.find(anchor)
        if idx == -1:
            updated = html.replace("</body>", new_block + "\n</body>")
        else:
            script_open = html.rfind("<script>", 0, idx)
            if script_open == -1:
                updated = html.replace("</body>", new_block + "\n</body>")
            else:
                updated = html[:script_open] + new_block + "\n" + html[script_open:]
        action = "inserted"

    if updated == html:
        print("[google-ads] WARN — no change to index.html")
        return

    INDEX_PATH.write_text(updated, encoding="utf-8")
    n_campaigns = len(payload.get("campaigns") or [])
    n_history = len(payload.get("history") or [])
    combined = payload.get("combined") or {}
    print(f"[google-ads] OK — block {action} in docs/index.html")
    print(f"             Week:      {payload.get('week_label','?')}")
    print(f"             Spend:     ${combined.get('spend', 0):,.2f} combined")
    print(f"             Clicks:    {combined.get('clicks', 0):,}")
    print(f"             Conv:      {combined.get('conv', 0):,.1f}")
    print(f"             Campaigns: {n_campaigns}")
    print(f"             History:   {n_history} weeks")


if __name__ == "__main__":
    inject()
