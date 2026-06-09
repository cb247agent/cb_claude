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
APIFY_DATA_FILE = STATE_DIR / "apify-data.json"      # keyword_tracking + competitor_serp for Organic Ranking Overlap


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
    auction_insights = []
    auction_insights_status = {}   # per-location: 'ok'|'awaiting_standard_access'|'query_error'|'no_data'
    if GADS_DATA_FILE.exists():
        try:
            gads = json.loads(GADS_DATA_FILE.read_text())
            search_terms       = gads.get("search_terms")       or []
            quality_scores     = gads.get("quality_scores")     or []
            conversion_actions = gads.get("conversion_actions") or []
            auction_insights   = gads.get("auction_insights")   or []
            auction_insights_status = gads.get("auction_insights_status") or {}
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

    # Prior-week WoW comparison data for Location Summary section
    # Render reads top-level p_malaga / p_ellenbrook / p_week_label (NOT
    # nested under history). Bug spotted 09 Jun 2026 — was returning None.
    prior = weeks[1] if len(weeks) >= 2 else {}
    prior_combined = prior.get("combined") or {}

    # Spend WoW deltas
    spend_chg = None
    if combined.get("spend") and prior_combined.get("spend"):
        spend_chg = round((combined["spend"] - prior_combined["spend"]) / prior_combined["spend"] * 100, 1)

    # ── Keyword Recommendations — derive from search terms with conv > 0 ──
    # Render reads bid.new_recs where bid = ads.bidding. We populate this
    # from search terms that converted but aren't yet exact-match keywords
    # (typically triggered via broad/phrase variants you can't bid up).
    # Filter: cost < $5, conv >= 1, not a brand keyword.
    import re as _re
    BRAND_PATTERNS = [
        r"chasing\s*better", r"\bcb247\b", r"chasingbetter247",
    ]
    def _is_brand(term):
        t = (term or "").lower()
        return any(_re.search(p, t) for p in BRAND_PATTERNS)

    promote_candidates = sorted(
        [s for s in search_terms
         if (s.get("cost", 0) or 0) < 5
         and (s.get("conv", 0) or 0) >= 1
         and not _is_brand(s.get("search_term", ""))],
        key=lambda s: -(s.get("conv", 0) or 0),
    )[:8]

    new_recs = []
    for s in promote_candidates:
        cost = s.get("cost", 0) or 0
        conv = s.get("conv", 0) or 0
        cpa_obs = round(cost / conv, 2) if conv > 0 else 0
        # Suggested bid = current CPC × 1.5 (give it room to win the auction)
        impressions = s.get("impressions", 0) or 0
        clicks = s.get("clicks", 0) or 0
        cpc_obs = round(cost / clicks, 2) if clicks > 0 else cpa_obs
        suggested_bid = round(cpc_obs * 1.5, 2)
        priority = "High" if conv >= 3 else "Medium" if conv >= 2 else "Low"
        new_recs.append({
            "keyword":  s.get("search_term"),
            "vol":      f"~{impressions}",          # 7-day observed impressions
            "bid":      f"${suggested_bid}",
            "priority": priority,
            "reason":   f"{conv:g} conv at ${cpa_obs} CPA from broad/phrase match — promote to exact match to bid up directly. {s.get('location', '')}",
        })

    # ── Organic Ranking Overlap — pull keyword_tracking + competitor_serp ─
    # from apify-data.json. The Apify weekly run pulls:
    #   apify-data.json.keyword_tracking → list of {keyword, position, clicks, impressions, ctr}
    #     (where 'position' is CB247's organic SERP position; null if we don't rank)
    #   apify-data.json.competitor_serp → list of {keyword, organic:[{title,url,position}], local_pack}
    #     (top 5 organic results per tracked keyword — includes CB247 if we rank)
    # Render expects ads.keyword_tracking = [{keyword, position, competitors:[domain,...]}].
    # We merge: take keyword_tracking entries with non-null position, enrich each with the
    # top 3 non-CB247 competitor domains from the matching competitor_serp entry.
    keyword_tracking = []
    apify_pulled_at = None
    if APIFY_DATA_FILE.exists():
        try:
            apify = json.loads(APIFY_DATA_FILE.read_text())
            apify_pulled_at = apify.get("date_pulled")
            kt_raw = apify.get("keyword_tracking") or []
            serp_raw = apify.get("competitor_serp") or []

            # Build keyword → top-3 competitor-domains map from competitor_serp.
            # Match keys are lowercased; fuzzy lookup is substring overlap (gym malaga
            # in keyword_tracking matches "gym malaga perth" in competitor_serp).
            def _domain(url):
                try:
                    from urllib.parse import urlparse
                    h = urlparse(url).netloc.lower()
                    return h.replace("www.", "")
                except Exception:
                    return ""

            serp_competitors_by_kw = {}
            for s in serp_raw:
                kw = (s.get("keyword") or "").lower().strip()
                if not kw:
                    continue
                organic = s.get("organic") or []
                # Top non-CB247 organic domains, dedup, max 3
                comps = []
                seen = set()
                for o in organic:
                    d = _domain(o.get("url", ""))
                    if not d or "chasingbetter247" in d:
                        continue
                    if d in seen:
                        continue
                    seen.add(d)
                    comps.append(d)
                    if len(comps) >= 3:
                        break
                serp_competitors_by_kw[kw] = comps

            def _lookup_competitors(kw):
                """Fuzzy lookup — exact, then substring match either direction."""
                kw_l = (kw or "").lower().strip()
                if not kw_l:
                    return []
                if kw_l in serp_competitors_by_kw:
                    return serp_competitors_by_kw[kw_l]
                for s_kw, comps in serp_competitors_by_kw.items():
                    if kw_l in s_kw or s_kw in kw_l:
                        return comps
                return []

            # Pass 1: keyword_tracking entries with a real position
            seen_kws = set()
            for k in kt_raw:
                kw = (k.get("keyword") or "").strip()
                if not kw or k.get("position") in (None, 0):
                    continue
                seen_kws.add(kw.lower())
                keyword_tracking.append({
                    "keyword":     kw,
                    "position":    k.get("position"),
                    "clicks":      k.get("clicks", 0),
                    "impressions": k.get("impressions", 0),
                    "competitors": _lookup_competitors(kw),
                    "source":      "gsc",
                })

            # Pass 2: competitor_serp entries where CB247 appears in organic[]
            # — gives us additional ranked keywords beyond the GSC-tracked list.
            for s in serp_raw:
                kw = (s.get("keyword") or "").strip()
                if not kw or kw.lower() in seen_kws:
                    continue
                cb_pos = None
                for o in (s.get("organic") or []):
                    d = _domain(o.get("url", ""))
                    if "chasingbetter247" in d:
                        cb_pos = o.get("position")
                        break
                if not cb_pos:
                    continue
                seen_kws.add(kw.lower())
                keyword_tracking.append({
                    "keyword":     kw,
                    "position":    cb_pos,
                    "clicks":      0,
                    "impressions": 0,
                    "competitors": serp_competitors_by_kw.get(kw.lower(), []),
                    "source":      "serp",
                })

            # Sort: best position first
            keyword_tracking.sort(key=lambda x: (x.get("position") or 999))
        except Exception as e:
            print(f"[google-ads] could not parse {APIFY_DATA_FILE}: {e}")

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
        "spend_chg":  spend_chg,   # WoW % spend change for verdict text
        # ── Prior-week for WoW deltas in Location Summary ─────────────
        # Render reads ads.p_malaga.spend, ads.p_ellenbrook.cpa, etc.
        "p_malaga":     prior.get("malaga") or {},
        "p_ellenbrook": prior.get("ellenbrook") or {},
        "p_week_label": prior.get("week_label", ""),
        # Rich tables for Search Terms / QS / Conv Tracking sections
        # Sourced from state/google-ads-data.json (same date scope as latest week)
        "search_terms":       search_terms,
        "quality_scores":     quality_scores,
        "conversion_actions": conversion_actions,
        # Auction Insights — populated when Standard Access is granted. Until
        # then, auction_insights_status carries 'awaiting_standard_access' per
        # location so the render can show the right message instead of generic
        # 'No data'. Sourced from state/google-ads-data.json.
        "auction_insights":          auction_insights,
        "auction_insights_status":   auction_insights_status,
        # Organic Ranking Overlap — sourced from state/apify-data.json.
        # Each entry: {keyword, position, clicks, impressions, competitors:[domain,...], source}.
        # source ∈ {'gsc','serp'} — GSC = Google Search Console (real CTR data),
        # SERP = scraped Google SERP (position only, no CTR).
        "keyword_tracking":     keyword_tracking,
        "apify_pulled_at":      apify_pulled_at,
        # Keyword recommendations — derived from converting search terms not yet
        # exact-match keywords. Read by render under ads.bidding.new_recs.
        "bidding": {
            "new_recs": new_recs,
        },
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
