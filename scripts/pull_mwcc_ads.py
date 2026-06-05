"""
pull_mwcc_ads.py — Pulls Google Ads campaign performance for My World Childcare.
Account: MWCC_GOOGLE_ADS_CUSTOMER_ID (917-218-6113)
Manager: MWCC_GOOGLE_ADS_MANAGER_ID (569-719-3495)

Saves current week + rolling 8-week history to:
  state/mwcc-ads.json         ← current week snapshot (report baker reads this)
  state/mwcc-ads-history.json ← rolling 8-week history (WoW trend charts)

MWCC campaign structure (3 campaigns, all under one account):
  MWCC | Brand         — Search (branded keywords)
  MWCC | Q2 2026       — Search (generic childcare/OSHC keywords)
  Leads-Perf Max-2     — Performance Max
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

STATE_DIR       = BASE_DIR / "state"
OUTPUT_FILE     = STATE_DIR / "mwcc-ads.json"
HISTORY_FILE    = STATE_DIR / "mwcc-ads-history.json"

DEVELOPER_TOKEN = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")
CUSTOMER_ID     = os.getenv("MWCC_GOOGLE_ADS_CUSTOMER_ID", "").replace("-", "")
MANAGER_ID      = os.getenv("MWCC_GOOGLE_ADS_MANAGER_ID", "").replace("-", "")


def pull_mwcc_ads(start_override: str = "", end_override: str = ""):
    """Fetch Google Ads data for MWCC and save to state/mwcc-ads.json.

    Args:
        start_override: Optional date string YYYY-MM-DD. Overrides automatic week calc.
        end_override:   Optional date string YYYY-MM-DD. Overrides automatic week calc.
    """

    # --- Prerequisites check ---
    missing = []
    if not DEVELOPER_TOKEN:
        missing.append("GOOGLE_ADS_DEVELOPER_TOKEN")
    if not CUSTOMER_ID:
        missing.append("MWCC_GOOGLE_ADS_CUSTOMER_ID")
    if missing:
        print(f"[MWCC Ads] Skipping — missing env vars: {', '.join(missing)}")
        _write_empty(f"Missing env vars: {', '.join(missing)}")
        return None

    try:
        from google.ads.googleads.client import GoogleAdsClient
        from google.ads.googleads.errors import GoogleAdsException
    except ImportError:
        print("[MWCC Ads] google-ads-python not installed. Run: pip install google-ads")
        _write_empty("google-ads not installed")
        return None

    # --- Auth credentials ---
    try:
        base_config = {
            "developer_token": DEVELOPER_TOKEN,
            "refresh_token":   _get_refresh_token(),
            "client_id":       _get_oauth_client_id(),
            "client_secret":   _get_oauth_client_secret(),
            "use_proto_plus":  True,
        }
    except Exception as e:
        print(f"[MWCC Ads] Failed to load credentials: {e}")
        _write_empty(str(e))
        return None

    # --- Date range: custom override or most recently completed Sat–Fri week ---
    if start_override and end_override:
        start_date = start_override
        end_date   = end_override
        print(f"[MWCC Ads] Using custom date range: {start_date} → {end_date}")
    else:
        today  = datetime.today()
        days_since_friday = (today.weekday() - 4) % 7
        end    = today - timedelta(days=days_since_friday)   # last Friday
        start  = end - timedelta(days=6)                     # preceding Saturday
        end_date   = end.strftime("%Y-%m-%d")
        start_date = start.strftime("%Y-%m-%d")

    query = f"""
        SELECT
          campaign.id,
          campaign.name,
          campaign.status,
          campaign.advertising_channel_type,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.ctr,
          metrics.average_cpc,
          metrics.conversions,
          metrics.conversion_rate
        FROM campaign
        WHERE campaign.status != 'REMOVED'
          AND segments.date BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY metrics.cost_micros DESC
    """

    # --- Login via manager (MWCC is a child account under the MCC) ---
    login_id = MANAGER_ID if MANAGER_ID else CUSTOMER_ID
    try:
        client = GoogleAdsClient.load_from_dict({
            **base_config,
            "login_customer_id": login_id,
        })
        ga_service = client.get_service("GoogleAdsService")
        response   = ga_service.search(customer_id=CUSTOMER_ID, query=query)
    except Exception as e:
        print(f"[MWCC Ads] API error: {e}")
        _write_empty(str(e))
        return None

    campaigns  = []
    tot_spend  = 0
    tot_clicks = 0
    tot_impr   = 0
    tot_conv   = 0

    for row in response:
        spend       = row.metrics.cost_micros / 1_000_000
        clicks      = row.metrics.clicks
        impressions = row.metrics.impressions
        conversions = row.metrics.conversions or 0

        campaign = {
            "id":           row.campaign.id,
            "name":         row.campaign.name,
            "type":         row.campaign.advertising_channel_type.name,
            "status":       row.campaign.status.name,
            "impressions":  impressions,
            "clicks":       clicks,
            "spend":        round(spend, 2),
            "ctr":          round(row.metrics.ctr * 100, 2) if row.metrics.ctr else 0,
            "cpc":          round(row.metrics.average_cpc / 1_000_000, 2) if row.metrics.average_cpc else 0,
            "conversions":  conversions,
            "conv_rate":    round(row.metrics.conversion_rate * 100, 2) if row.metrics.conversion_rate else 0,
            "cost_per_conv": round(spend / conversions, 2) if conversions else 0,
        }
        campaigns.append(campaign)
        tot_spend  += spend
        tot_clicks += clicks
        tot_impr   += impressions
        tot_conv   += conversions

    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "brand":        "mwcc",
        "date_range":   {"start": start_date, "end": end_date},
        "customer_id":  CUSTOMER_ID,
        "campaigns":    campaigns,
        "totals": {
            "spend":       round(tot_spend, 2),
            "clicks":      tot_clicks,
            "impressions": tot_impr,
            "ctr":         round(tot_clicks / tot_impr * 100, 2) if tot_impr else 0,
            "conversions": round(tot_conv, 2),
            "cpc":         round(tot_spend / tot_clicks, 2) if tot_clicks else 0,
            "cost_per_conv": round(tot_spend / tot_conv, 2) if tot_conv else 0,
        },
    }

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))

    # --- Update rolling history file ---
    _update_history(output, start_date, end_date)

    print(f"[MWCC Ads] Saved → {OUTPUT_FILE}")
    print(f"[MWCC Ads] Period     : {start_date} to {end_date}")
    print(f"[MWCC Ads] Campaigns  : {len(campaigns)}")
    print(f"[MWCC Ads] Spend      : ${round(tot_spend, 2):,.2f}")
    print(f"[MWCC Ads] Clicks     : {tot_clicks:,}  |  Conversions: {tot_conv:.2f}")
    print(f"[MWCC Ads] Cost/Conv  : ${round(tot_spend / tot_conv, 2) if tot_conv else 'N/A'}")
    for c in campaigns:
        print(f"[MWCC Ads]   {c['name']:<35} ${c['spend']:>8,.2f}  {c['conversions']:>6.2f} conv  CPC ${c['cpc']:.2f}")
    return output


def _update_history(output, start_date, end_date):
    """Append current week to mwcc-ads-history.json (keeps last 8 weeks)."""
    try:
        s = datetime.strptime(start_date, "%Y-%m-%d")
        e = datetime.strptime(end_date,   "%Y-%m-%d")
        week_label = f"{s.strftime('%d%b%y')}-{e.strftime('%d%b%y')}"
    except Exception:
        week_label = f"{start_date}_{end_date}"

    entry = {
        "week_label":  week_label,
        "date_start":  start_date,
        "date_end":    end_date,
        "totals":      output["totals"],
        "campaigns":   [
            {
                "name":         c["name"],
                "type":         c["type"],
                "spend":        c["spend"],
                "clicks":       c["clicks"],
                "conversions":  c["conversions"],
                "cost_per_conv": c["cost_per_conv"],
                "ctr":          c["ctr"],
                "cpc":          c["cpc"],
            }
            for c in output["campaigns"]
        ],
    }

    history = []
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text())
        except Exception:
            history = []

    # Remove same week if re-running, then prepend, cap at 8 weeks
    history = [w for w in history if w.get("week_label") != week_label]
    history = [entry] + history[:7]

    HISTORY_FILE.write_text(json.dumps(history, indent=2))
    print(f"[MWCC Ads] History updated → {HISTORY_FILE.name} ({len(history)} weeks)")


def _write_empty(skip_reason):
    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "brand":        "mwcc",
        "available":    False,
        "skip_reason":  skip_reason,
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))


def _get_refresh_token() -> str:
    token_file = BASE_DIR / "secrets" / "token.json"
    if not token_file.exists():
        raise FileNotFoundError("No token found. Run google_auth.py first.")
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
    parser = argparse.ArgumentParser(description="Pull MWCC Google Ads data")
    parser.add_argument("--start", default="", help="Start date YYYY-MM-DD (default: auto Sat–Fri week)")
    parser.add_argument("--end",   default="", help="End date   YYYY-MM-DD (default: auto Sat–Fri week)")
    args = parser.parse_args()
    pull_mwcc_ads(start_override=args.start, end_override=args.end)
