"""
pull_gbp_performance.py — Pull Google Business Profile *performance* metrics
for CB247 locations (Malaga + Ellenbrook).

This complements scripts/pull_gbp.py:
  pull_gbp.py             → ratings + reviews + photos (via Apify Maps scraper)
  pull_gbp_performance.py → calls + directions + website clicks (via GBP API)

Together they replace the GBP section that used to come from Metricool's
hardcoded load_metricool() block.

Output: state/gbp-performance.json

Auth: shares the same OAuth token as GA4/GSC/Ads pulls
      (secrets/token.json, scope: business.manage already included).

Metrics pulled per location (7-day window, last completed Sat-Fri):
  - WEBSITE_CLICKS
  - CALL_CLICKS
  - BUSINESS_DIRECTION_REQUESTS
  - BUSINESS_IMPRESSIONS_DESKTOP_MAPS / MOBILE_MAPS
  - BUSINESS_IMPRESSIONS_DESKTOP_SEARCH / MOBILE_SEARCH

Required env vars (set in .env, only needed once):
  CB247_GBP_MALAGA_LOCATION_ID      e.g. "locations/12345..."
  CB247_GBP_ELLENBROOK_LOCATION_ID  e.g. "locations/67890..."

If the location IDs are missing, the script enters first-run setup mode
and lists all accessible locations so the user can populate .env.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

STATE_DIR = BASE_DIR / "state"
OUTPUT_FILE = STATE_DIR / "gbp-performance.json"

MALAGA_LOC_ID     = os.getenv("CB247_GBP_MALAGA_LOCATION_ID", "").strip()
ELLENBROOK_LOC_ID = os.getenv("CB247_GBP_ELLENBROOK_LOCATION_ID", "").strip()

METRICS = [
    "WEBSITE_CLICKS",
    "CALL_CLICKS",
    "BUSINESS_DIRECTION_REQUESTS",
    "BUSINESS_IMPRESSIONS_DESKTOP_MAPS",
    "BUSINESS_IMPRESSIONS_MOBILE_MAPS",
    "BUSINESS_IMPRESSIONS_DESKTOP_SEARCH",
    "BUSINESS_IMPRESSIONS_MOBILE_SEARCH",
]


def _date_range():
    """Last completed Sat-Fri week — matches all other pulls."""
    today = datetime.today()
    days_since_friday = (today.weekday() - 4) % 7
    end   = today - timedelta(days=days_since_friday)
    start = end - timedelta(days=6)
    return start, end


def _build_services():
    """Return (performance_svc, info_svc, account_svc) authorised clients."""
    sys.path.insert(0, str(BASE_DIR / "scripts"))
    try:
        from google_auth import get_valid_credentials
    except ImportError as e:
        print(f"[GBP-perf] Could not import google_auth: {e}")
        return None, None, None
    try:
        from googleapiclient.discovery import build
    except ImportError:
        print("[GBP-perf] google-api-python-client not installed — "
              "run: pip install google-api-python-client")
        return None, None, None

    creds = get_valid_credentials()
    perf_svc = build("businessprofileperformance", "v1",
                     credentials=creds, cache_discovery=False)
    info_svc = build("mybusinessbusinessinformation", "v1",
                     credentials=creds, cache_discovery=False)
    acct_svc = build("mybusinessaccountmanagement", "v1",
                     credentials=creds, cache_discovery=False)
    return perf_svc, info_svc, acct_svc


def list_accessible_locations(info_svc, acct_svc):
    """First-run helper — print all accounts + locations visible to this
    OAuth token so the user can populate .env."""
    print("\n[GBP-perf] First-run setup — listing all accessible locations:\n")
    try:
        accts_resp = acct_svc.accounts().list().execute()
        accounts = accts_resp.get("accounts", [])
    except Exception as e:
        print(f"  Account list failed: {e}")
        return

    if not accounts:
        print("  No GBP accounts visible to this OAuth token.")
        print("  Confirm cb_agent@chasingbetter.com.au has Owner/Manager")
        print("  access to the CB247 GBP profiles.")
        return

    for a in accounts:
        acct_name = a.get("name", "")
        display   = a.get("accountName", "")
        print(f"  ACCOUNT: {acct_name}  ({display})")
        try:
            locs_resp = info_svc.accounts().locations().list(
                parent=acct_name,
                readMask="name,title,storefrontAddress,storeCode",
            ).execute()
        except Exception as e:
            print(f"    (location list error: {str(e)[:120]})")
            continue
        for loc in locs_resp.get("locations", []):
            print(f"    LOCATION ID: {loc.get('name')}")
            print(f"    TITLE:       {loc.get('title','')}")
            addr = loc.get("storefrontAddress") or {}
            lines = addr.get("addressLines") or []
            if lines:
                print(f"    ADDRESS:     {', '.join(lines)}, {addr.get('locality','')}")
            print()

    print("Copy the LOCATION IDs into .env then re-run this script:")
    print("  CB247_GBP_MALAGA_LOCATION_ID=locations/...")
    print("  CB247_GBP_ELLENBROOK_LOCATION_ID=locations/...")


def pull_location_metrics(perf_svc, location_id, start, end):
    """Pull all configured metrics for one location, summed across the
    date range. Returns dict { metric_name: weekly_total }."""
    try:
        # fetchMultiDailyMetricsTimeSeries — daily counts per metric.
        # The googleapiclient builder doesn't accept nested object args
        # cleanly here; pass them as flat keyword args matching the URL params.
        resp = perf_svc.locations().fetchMultiDailyMetricsTimeSeries(
            location=location_id,
            dailyMetrics=METRICS,
            **{
                "dailyRange_startDate_year":  start.year,
                "dailyRange_startDate_month": start.month,
                "dailyRange_startDate_day":   start.day,
                "dailyRange_endDate_year":    end.year,
                "dailyRange_endDate_month":   end.month,
                "dailyRange_endDate_day":     end.day,
            },
        ).execute()
    except TypeError:
        # The discovery client may use dot-notation kwargs instead. Retry.
        try:
            resp = perf_svc.locations().fetchMultiDailyMetricsTimeSeries(
                location=location_id,
                dailyMetrics=METRICS,
                **{
                    "dailyRange.startDate.year":  start.year,
                    "dailyRange.startDate.month": start.month,
                    "dailyRange.startDate.day":   start.day,
                    "dailyRange.endDate.year":    end.year,
                    "dailyRange.endDate.month":   end.month,
                    "dailyRange.endDate.day":     end.day,
                },
            ).execute()
        except Exception as e:
            return {"error": str(e)[:200], "metrics": {}}
    except Exception as e:
        return {"error": str(e)[:200], "metrics": {}}

    series_list = resp.get("multiDailyMetricTimeSeries") or []
    totals = {m: 0 for m in METRICS}
    for s in series_list:
        dms = s.get("dailyMetricTimeSeries") or {}
        metric_name = dms.get("dailyMetric")
        if metric_name not in totals:
            continue
        time_series = dms.get("timeSeries") or {}
        dated_values = time_series.get("datedValues") or []
        total = 0
        for dv in dated_values:
            try:
                total += int(dv.get("value") or 0)
            except (TypeError, ValueError):
                continue
        totals[metric_name] = total

    return {"error": None, "metrics": totals}


def _write_empty(skip_reason):
    OUTPUT_FILE.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "available":    False,
        "skip_reason":  skip_reason,
    }, indent=2))


def main():
    perf_svc, info_svc, acct_svc = _build_services()
    if perf_svc is None:
        _write_empty("services could not be built — check google_auth + google-api-python-client install")
        sys.exit(1)

    # First-run setup if location IDs not in .env
    if not MALAGA_LOC_ID or not ELLENBROOK_LOC_ID:
        list_accessible_locations(info_svc, acct_svc)
        print("\n[GBP-perf] Location IDs missing from .env — first-run setup mode.")
        print("           Copy the IDs above into .env then re-run this script.")
        _write_empty("location IDs not set in .env — run script once to see available IDs")
        return

    start, end = _date_range()
    start_str = start.strftime("%Y-%m-%d")
    end_str   = end.strftime("%Y-%m-%d")
    print(f"[GBP-perf] Period: {start_str} -> {end_str}")

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date_range":   {"start": start_str, "end": end_str},
        "locations":    {},
    }

    for label, loc_id in [("malaga", MALAGA_LOC_ID), ("ellenbrook", ELLENBROOK_LOC_ID)]:
        print(f"[GBP-perf] Pulling {label} ({loc_id})...")
        result = pull_location_metrics(perf_svc, loc_id, start, end)
        m = result.get("metrics") or {}

        maps_impr   = m.get("BUSINESS_IMPRESSIONS_DESKTOP_MAPS", 0) + m.get("BUSINESS_IMPRESSIONS_MOBILE_MAPS", 0)
        search_impr = m.get("BUSINESS_IMPRESSIONS_DESKTOP_SEARCH", 0) + m.get("BUSINESS_IMPRESSIONS_MOBILE_SEARCH", 0)
        total_actions = (
            m.get("WEBSITE_CLICKS", 0)
            + m.get("CALL_CLICKS", 0)
            + m.get("BUSINESS_DIRECTION_REQUESTS", 0)
        )

        output["locations"][label] = {
            "location_id":         loc_id,
            "error":               result.get("error"),
            "website_clicks":      m.get("WEBSITE_CLICKS", 0),
            "phone_clicks":        m.get("CALL_CLICKS", 0),
            "direction_requests":  m.get("BUSINESS_DIRECTION_REQUESTS", 0),
            "maps_impressions":    maps_impr,
            "search_impressions":  search_impr,
            "total_impressions":   maps_impr + search_impr,
            "total_actions":       total_actions,
            "raw_metrics":         m,
        }
        if result.get("error"):
            print(f"           ERROR: {result['error']}")
        else:
            print(f"           actions={total_actions}, impressions={maps_impr + search_impr}, "
                  f"calls={m.get('CALL_CLICKS', 0)}, directions={m.get('BUSINESS_DIRECTION_REQUESTS', 0)}, "
                  f"web_clicks={m.get('WEBSITE_CLICKS', 0)}")

    locs = output["locations"]
    output["combined"] = {
        "total_actions":      sum(l.get("total_actions", 0) for l in locs.values()),
        "total_impressions":  sum(l.get("total_impressions", 0) for l in locs.values()),
        "website_clicks":     sum(l.get("website_clicks", 0) for l in locs.values()),
        "phone_clicks":       sum(l.get("phone_clicks", 0) for l in locs.values()),
        "direction_requests": sum(l.get("direction_requests", 0) for l in locs.values()),
        "maps_impressions":   sum(l.get("maps_impressions", 0) for l in locs.values()),
        "search_impressions": sum(l.get("search_impressions", 0) for l in locs.values()),
    }

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2, default=str))
    print(f"\n[GBP-perf] Saved to {OUTPUT_FILE}")
    print(f"[GBP-perf] Combined: {output['combined']['total_actions']} actions, "
          f"{output['combined']['total_impressions']} impressions across both locations")


if __name__ == "__main__":
    main()
