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

    # --- Date range: most recently completed Mon–Sun week ---
    today = datetime.today()
    # days_since_sunday: Mon=1, Tue=2, ..., Sat=6, Sun=0
    days_since_sunday = (today.weekday() + 1) % 7
    end   = today if days_since_sunday == 0 else today - timedelta(days=days_since_sunday)
    start = end - timedelta(days=6)
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
    }

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))
    print(f"\n[Google Ads] Done — {len(all_campaigns)} campaigns total | ${round(gt_spend,2)} combined spend")
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
