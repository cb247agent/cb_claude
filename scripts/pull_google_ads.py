"""
pull_google_ads.py — Pulls campaign performance from Google Ads API.
Saves spend, clicks, impressions, CTR, CPC by campaign to state/google-ads-data.json.

Supports two accounts: Malaga (GOOGLE_ADS_CUSTOMER_ID_MALAGA) and
Ellenbrook (GOOGLE_ADS_CUSTOMER_ID_ELLENBROOK). Results are tagged by location
and combined totals are included.

NOTE: Requires Google Ads API to be enabled in GCP and cb_agent@chasingbetter.com.au
to have access to the Google Ads account (MCC or direct). If not configured, this
script will skip gracefully and log a warning.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
STATE_DIR = BASE_DIR / "state"
OUTPUT_FILE = STATE_DIR / "google-ads-data.json"

DEVELOPER_TOKEN = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")
MANAGER_ID      = os.getenv("GOOGLE_ADS_MANAGER_ID", "")

# Two location accounts
ACCOUNTS = [
    {"location": "Malaga",      "customer_id": os.getenv("GOOGLE_ADS_CUSTOMER_ID_MALAGA", "").replace("-", "")},
    {"location": "Ellenbrook",  "customer_id": os.getenv("GOOGLE_ADS_CUSTOMER_ID_ELLENBROOK", "").replace("-", "")},
]


def pull_google_ads():
    """
    Fetch Google Ads campaign performance for both Malaga and Ellenbrook accounts.
    Saves combined + per-location results to state/google-ads-data.json.
    Skips gracefully if credentials are not configured.
    """
    # --- Prerequisites check ---
    missing = []
    if not DEVELOPER_TOKEN:
        missing.append("GOOGLE_ADS_DEVELOPER_TOKEN")
    active_accounts = [a for a in ACCOUNTS if a["customer_id"]]
    if not active_accounts:
        missing.append("GOOGLE_ADS_CUSTOMER_ID_MALAGA and/or GOOGLE_ADS_CUSTOMER_ID_ELLENBROOK")
    if missing:
        print(f"[Google Ads] Skipping — missing env vars: {', '.join(missing)}")
        _write_empty(skip_reason=f"Missing env vars: {', '.join(missing)}")
        return None

    try:
        from google.ads.googleads.client import GoogleAdsClient
        from google.ads.googleads.errors import GoogleAdsException
    except ImportError:
        print("[Google Ads] google-ads-python not installed. Run: pip install google-ads")
        _write_empty(skip_reason="google-ads not installed")
        return None

    # --- Load shared auth credentials ---
    try:
        base_config = {
            "developer_token": DEVELOPER_TOKEN,
            "refresh_token":   _get_refresh_token(),
            "client_id":       _get_oauth_client_id(),
            "client_secret":   _get_oauth_client_secret(),
            "use_proto_plus":  True,
        }
    except Exception as e:
        print(f"[Google Ads] Failed to load credentials: {e}")
        _write_empty(skip_reason=str(e))
        return None

    # --- Date range: most recently completed Sat–Fri week ---
    # Pulled on Monday — Friday conversions have had 72hrs to fully settle.
    # days_since_friday: Mon=3, Tue=4, Wed=5, Thu=6, Fri=0, Sat=1, Sun=2
    today = datetime.today()
    days_since_friday = (today.weekday() - 4) % 7
    end   = today - timedelta(days=days_since_friday)      # last Friday
    start = end - timedelta(days=6)                        # preceding Saturday
    end_date   = end.strftime("%Y-%m-%d")
    start_date = start.strftime("%Y-%m-%d")

    query = f"""
        SELECT
          campaign.id,
          campaign.name,
          campaign.status,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.ctr,
          metrics.average_cpc,
          metrics.conversions
        FROM campaign
        WHERE campaign.status != 'REMOVED'
          AND segments.date BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY metrics.cost_micros DESC
    """

    all_campaigns = []
    location_summaries = {}
    grand_totals = {"spend": 0, "clicks": 0, "impressions": 0, "conversions": 0}
    # Tier 2 accumulators (search terms, QS, conv actions, auction insights)
    search_terms       = []
    quality_scores     = []
    conversion_actions = []
    auction_insights   = []

    for account in active_accounts:
        cid      = account["customer_id"]
        location = account["location"]
        print(f"[Google Ads] Pulling {location} (ID: {cid[:3]}***{cid[-4:]})...")

        # Each account is standalone — login as the account itself
        try:
            client = GoogleAdsClient.load_from_dict({
                **base_config,
                "login_customer_id": cid,
            })
            ga_service = client.get_service("GoogleAdsService")
            response = ga_service.search(customer_id=cid, query=query)
        except GoogleAdsException as e:
            print(f"[Google Ads] API error for {location}: {e}")
            location_summaries[location] = {"error": str(e)}
            continue
        except Exception as e:
            print(f"[Google Ads] Failed to init client for {location}: {e}")
            location_summaries[location] = {"error": str(e)}
            continue

        campaigns   = []
        loc_spend   = 0
        loc_clicks  = 0
        loc_impr    = 0
        loc_conv    = 0

        for row in response:
            spend       = row.metrics.cost_micros / 1_000_000
            clicks      = row.metrics.clicks
            impressions = row.metrics.impressions
            conversions = row.metrics.conversions or 0

            campaign = {
                "id":          row.campaign.id,
                "name":        row.campaign.name,
                "location":    location,
                "status":      row.campaign.status.name,
                "impressions": impressions,
                "clicks":      clicks,
                "spend":       round(spend, 2),
                "ctr":         round(row.metrics.ctr * 100, 2) if row.metrics.ctr else 0,
                "cpc":         round(row.metrics.average_cpc / 1_000_000, 2) if row.metrics.average_cpc else 0,
                "conversions": conversions,
            }
            campaigns.append(campaign)
            loc_spend += spend
            loc_clicks += clicks
            loc_impr += impressions
            loc_conv += conversions

        all_campaigns.extend(campaigns)
        grand_totals["spend"]       += loc_spend
        grand_totals["clicks"]      += loc_clicks
        grand_totals["impressions"] += loc_impr
        grand_totals["conversions"] += loc_conv

        location_summaries[location] = {
            "customer_id": cid,
            "campaigns":   len(campaigns),
            "spend":       round(loc_spend, 2),
            "clicks":      loc_clicks,
            "impressions": loc_impr,
            "ctr":         round(loc_clicks / loc_impr * 100, 2) if loc_impr else 0,
            "conversions": loc_conv,
            "cpl":         round(loc_spend / loc_conv, 2) if loc_conv else 0,
        }
        print(f"[Google Ads]   {location}: {len(campaigns)} campaigns | ${round(loc_spend,2)} spend | {loc_conv} conversions")

        # ── Tier 2 pulls — Search Terms, Quality Scores, Conversion Actions,
        #    Auction Insights. Each wrapped in try/except so a single failure
        #    (most commonly RESOURCE_EXHAUSTED on Explorer tokens) doesn't
        #    kill the rest of the pull. ──────────────────────────────────────
        search_terms.extend(
            _pull_search_terms(ga_service, cid, location, start_date, end_date))
        quality_scores.extend(
            _pull_quality_scores(ga_service, cid, location, start_date, end_date))
        conversion_actions.extend(
            _pull_conversion_actions(ga_service, cid, location, start_date, end_date))
        auction_insights.extend(
            _pull_auction_insights(ga_service, cid, location, start_date, end_date))

    # --- Combined totals ---
    gt_spend = grand_totals["spend"]
    gt_impr  = grand_totals["impressions"]
    gt_click = grand_totals["clicks"]
    gt_conv  = grand_totals["conversions"]

    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "date_range":   {"start": start_date, "end": end_date},
        "accounts":     location_summaries,
        "campaigns":    all_campaigns,
        "totals": {
            "spend":       round(gt_spend, 2),
            "clicks":      gt_click,
            "impressions": gt_impr,
            "ctr":         round(gt_click / gt_impr * 100, 2) if gt_impr else 0,
            "conversions": gt_conv,
            "cpl":         round(gt_spend / gt_conv, 2) if gt_conv else 0,
        },
        # ── Tier 2 deep-dives — empty arrays if all 4 helpers failed/skipped ──
        "search_terms":       search_terms,
        "quality_scores":     quality_scores,
        "conversion_actions": conversion_actions,
        "auction_insights":   auction_insights,
    }

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))
    print(f"\n[Google Ads] Done — {len(all_campaigns)} campaigns total | ${round(gt_spend,2)} combined spend")
    print(f"[Google Ads] Tier 2: {len(search_terms)} search terms | {len(quality_scores)} QS rows | "
          f"{len(conversion_actions)} conv actions | {len(auction_insights)} competitor domains")
    print(f"[Google Ads] Saved to {OUTPUT_FILE}")

    # ── Also write a weekly entry into ads-data.json (dashboard format) ──
    _update_ads_data(output, start_date, end_date, all_campaigns, location_summaries, grand_totals)

    return output


def _update_ads_data(output, start_date, end_date, all_campaigns, location_summaries, grand_totals):
    """Merge current week data into ads-data.json (the format bake-public-dashboard reads)."""
    ADS_FILE = STATE_DIR / "ads-data.json"

    # Load existing ads-data.json or start fresh
    if ADS_FILE.exists():
        try:
            existing = json.loads(ADS_FILE.read_text())
        except Exception:
            existing = {}
    else:
        existing = {}

    # Build week label e.g. "25May26-01Jun26"
    try:
        s = datetime.strptime(start_date, "%Y-%m-%d")
        e = datetime.strptime(end_date,   "%Y-%m-%d")
        week_label = f"{s.strftime('%d%b%y')}-{e.strftime('%d%b%y')}"
    except Exception:
        week_label = f"{start_date}-{end_date}"

    gt = grand_totals
    gt_spend = gt["spend"]
    gt_click = gt["clicks"]
    gt_impr  = gt["impressions"]
    gt_conv  = gt["conversions"]

    mal_raw = location_summaries.get("Malaga") or {}
    ell_raw = location_summaries.get("Ellenbrook") or {}

    new_entry = {
        "week_label":  week_label,
        "date_start":  start_date,
        "date_end":    end_date,
        "combined": {
            "spend":       round(gt_spend, 2),
            "clicks":      gt_click,
            "impressions": gt_impr,
            "ctr":         round(gt_click / gt_impr * 100, 2) if gt_impr else 0,
            "conv":        int(gt_conv),
            "cpa":         round(gt_spend / gt_conv, 2) if gt_conv else 0,
        },
        "malaga": {
            "spend":  mal_raw.get("spend", 0),
            "clicks": mal_raw.get("clicks", 0),
            "conv":   int(mal_raw.get("conversions", 0)),
            "cpa":    mal_raw.get("cpl", 0),
            "ctr":    mal_raw.get("ctr", 0),
        },
        "ellenbrook": {
            "spend":  ell_raw.get("spend", 0),
            "clicks": ell_raw.get("clicks", 0),
            "conv":   int(ell_raw.get("conversions", 0)),
            "cpa":    ell_raw.get("cpl", 0),
            "ctr":    ell_raw.get("ctr", 0),
        },
        "campaigns": [
            {
                "name":    c.get("name", ""),
                "spend":   c.get("spend", 0),
                "clicks":  c.get("clicks", 0),
                "conv":    int(c.get("conversions", 0)),
                "cpa":     round(c["spend"] / c["conversions"], 2) if c.get("conversions") else 0,
                "status":  c.get("status", ""),
                "location": c.get("location", ""),
            }
            for c in all_campaigns
        ],
    }

    # Prepend new entry; drop entries with same week_label (dedup); keep 8 weeks
    google_ads_history = [w for w in (existing.get("google_ads") or []) if w.get("week_label") != week_label]
    google_ads_history = [new_entry] + google_ads_history[:7]

    ads_data = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "source":       "google-ads-api",
        "google_ads":   google_ads_history,
        "meta_ads":     existing.get("meta_ads") or [],
    }

    ADS_FILE.write_text(json.dumps(ads_data, indent=2))
    print(f"[Google Ads] ads-data.json updated — week {week_label}, ${round(gt_spend,2)} combined")


def _qs_enum_to_label(val):
    """Map Google Ads quality_score component enum to human label.
    Returns one of 'Above average', 'Average', 'Below average', or '' for unknown.
    """
    # QualityScoreBucketEnum: 0=UNSPECIFIED 1=UNKNOWN 2=BELOW_AVERAGE 3=AVERAGE 4=ABOVE_AVERAGE
    if val is None:
        return ""
    # Both .name attribute access (proto-plus) and bare int values supported
    name = getattr(val, "name", None) or str(val)
    name = name.upper()
    if "ABOVE_AVERAGE" in name or name == "4":
        return "Above average"
    if "BELOW_AVERAGE" in name or name == "2":
        return "Below average"
    if "AVERAGE" in name or name == "3":
        return "Average"
    return ""


def _pull_search_terms(ga_service, cid, location, start_date, end_date):
    """Pull search_term_view — terms users typed that triggered ads."""
    query = f"""
        SELECT
          search_term_view.search_term,
          campaign.name,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions
        FROM search_term_view
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
          AND metrics.cost_micros > 0
        ORDER BY metrics.cost_micros DESC
        LIMIT 100
    """
    try:
        rows = ga_service.search(customer_id=cid, query=query)
        out = []
        for r in rows:
            spend = (r.metrics.cost_micros or 0) / 1_000_000
            out.append({
                "search_term": r.search_term_view.search_term,
                "campaign":    r.campaign.name,
                "location":    location,
                "impressions": r.metrics.impressions,
                "clicks":      r.metrics.clicks,
                "cost":        round(spend, 2),
                "conv":        round(r.metrics.conversions or 0, 2),
            })
        print(f"[Google Ads]   {location}: {len(out)} search terms pulled")
        return out
    except Exception as e:
        print(f"[Google Ads]   {location}: search_term_view skipped — {str(e)[:120]}")
        return []


def _pull_quality_scores(ga_service, cid, location, start_date, end_date):
    """Pull keyword_view with QS components."""
    query = f"""
        SELECT
          ad_group_criterion.keyword.text,
          ad_group_criterion.quality_info.quality_score,
          ad_group_criterion.quality_info.creative_quality_score,
          ad_group_criterion.quality_info.post_click_quality_score,
          ad_group_criterion.quality_info.search_predicted_ctr,
          campaign.name,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions
        FROM keyword_view
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
          AND ad_group_criterion.status = 'ENABLED'
          AND metrics.cost_micros > 0
        ORDER BY metrics.cost_micros DESC
        LIMIT 100
    """
    try:
        rows = ga_service.search(customer_id=cid, query=query)
        out = []
        for r in rows:
            qi = r.ad_group_criterion.quality_info
            spend = (r.metrics.cost_micros or 0) / 1_000_000
            out.append({
                "keyword":       r.ad_group_criterion.keyword.text,
                "campaign":      r.campaign.name,
                "location":      location,
                "quality_score": qi.quality_score or 0,
                "ad_relevance":  _qs_enum_to_label(qi.creative_quality_score),
                "lp_experience": _qs_enum_to_label(qi.post_click_quality_score),
                "expected_ctr":  _qs_enum_to_label(qi.search_predicted_ctr),
                "impressions":   r.metrics.impressions,
                "clicks":        r.metrics.clicks,
                "cost":          round(spend, 2),
                "conv":          round(r.metrics.conversions or 0, 2),
            })
        print(f"[Google Ads]   {location}: {len(out)} keywords with QS pulled")
        return out
    except Exception as e:
        print(f"[Google Ads]   {location}: keyword_view (QS) skipped — {str(e)[:120]}")
        return []


def _pull_conversion_actions(ga_service, cid, location, start_date, end_date):
    """Pull conversion actions firing in the period.
    Uses campaign segmentation to get conversion counts + last-fire date.
    """
    query = f"""
        SELECT
          segments.conversion_action_name,
          segments.conversion_action_category,
          segments.date,
          metrics.all_conversions
        FROM campaign
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
          AND metrics.all_conversions > 0
    """
    try:
        rows = ga_service.search(customer_id=cid, query=query)
        # Aggregate by conversion_action_name
        agg = {}
        for r in rows:
            name = r.segments.conversion_action_name
            if not name:
                continue
            cat = getattr(r.segments.conversion_action_category, "name", "") or ""
            date = r.segments.date
            count = r.metrics.all_conversions or 0
            entry = agg.setdefault(name, {
                "name": name,
                "category": cat,
                "location": location,
                "count": 0,
                "last_fired": "",
            })
            entry["count"] += count
            if date > (entry["last_fired"] or ""):
                entry["last_fired"] = date
        out = [
            {**v, "count": round(v["count"], 2)}
            for v in agg.values()
        ]
        out.sort(key=lambda x: x["count"], reverse=True)
        print(f"[Google Ads]   {location}: {len(out)} conversion actions pulled")
        return out
    except Exception as e:
        print(f"[Google Ads]   {location}: conversion_actions skipped — {str(e)[:120]}")
        return []


def _pull_auction_insights(ga_service, cid, location, start_date, end_date):
    """Pull auction_insight_view — competitors appearing in your auctions."""
    # Note: auction_insight_view aggregates differ from standard metrics.
    # Per-domain rollup gives the cleanest competitor view.
    query = f"""
        SELECT
          segments.auction_insight_domain,
          metrics.search_impression_share,
          metrics.overlap_rate,
          metrics.position_above_rate,
          metrics.outranking_share
        FROM campaign
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
    """
    try:
        rows = ga_service.search(customer_id=cid, query=query)
        # Aggregate by domain — average the share metrics (campaigns × domain)
        agg = {}
        for r in rows:
            domain = r.segments.auction_insight_domain
            if not domain:
                continue
            entry = agg.setdefault(domain, {
                "domain": domain,
                "location": location,
                "_n": 0,
                "impression_share": 0.0,
                "overlap_rate": 0.0,
                "position_above_rate": 0.0,
                "outranking_share": 0.0,
            })
            entry["_n"] += 1
            entry["impression_share"]    += float(r.metrics.search_impression_share or 0)
            entry["overlap_rate"]        += float(r.metrics.overlap_rate or 0)
            entry["position_above_rate"] += float(r.metrics.position_above_rate or 0)
            entry["outranking_share"]    += float(r.metrics.outranking_share or 0)
        out = []
        for d in agg.values():
            n = d.pop("_n") or 1
            for k in ("impression_share", "overlap_rate", "position_above_rate", "outranking_share"):
                d[k] = round(d[k] / n, 4)
            out.append(d)
        out.sort(key=lambda x: x["impression_share"], reverse=True)
        print(f"[Google Ads]   {location}: {len(out)} competitor domains in auction insights")
        return out[:20]
    except Exception as e:
        print(f"[Google Ads]   {location}: auction_insights skipped — {str(e)[:120]}")
        return []


def _write_empty(skip_reason):
    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "available":    False,
        "skip_reason":  skip_reason,
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))


def _get_refresh_token() -> str:
    token_file = BASE_DIR / "secrets" / "token.json"
    if not token_file.exists():
        raise FileNotFoundError("No token found. Run google_auth.py first to authenticate.")
    return json.loads(token_file.read_text()).get("refresh_token", "")


def _get_oauth_client_id() -> str:
    creds_file = BASE_DIR / "secrets" / "google-oauth.json"
    if not creds_file.exists():
        raise FileNotFoundError("secrets/google-oauth.json not found.")
    data = json.loads(creds_file.read_text())
    return data.get("installed", {}).get("client_id", data.get("client_id", ""))


def _get_oauth_client_secret() -> str:
    creds_file = BASE_DIR / "secrets" / "google-oauth.json"
    data = json.loads(creds_file.read_text())
    return data.get("installed", {}).get("client_secret", data.get("client_secret", ""))


if __name__ == "__main__":
    pull_google_ads()
