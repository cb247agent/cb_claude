"""
pull_mwcc_gbp_performance.py — Pull Google Business Profile performance
metrics for all 5 My World Childcare centres.

Output: state/mwcc-gbp-performance.json

Why this script exists:
  Metricool only allows 1 GBP connection per workspace, so it covers only
  Seville Grove. The other 4 centres (Armadale, Midvale & Midland, Rockingham,
  Waikiki) are invisible to the dashboard via Metricool.

  This script pulls directly from the GBP Performance API for each location,
  giving complete coverage of all 5 centres.

Auth: shares the same OAuth token as GA4/GSC/Ads pulls
      (secrets/token.json, scope: business.manage already included).

Metrics pulled per location (Sat–Fri window — matches all marketing pulls):
  - WEBSITE_CLICKS
  - CALL_CLICKS
  - BUSINESS_DIRECTION_REQUESTS
  - BUSINESS_IMPRESSIONS_DESKTOP_MAPS / MOBILE_MAPS
  - BUSINESS_IMPRESSIONS_DESKTOP_SEARCH / MOBILE_SEARCH

Required .env (all 5 location IDs in format "locations/<id>"):
  GBP_MWCC_ARMADALE_ID
  GBP_MWCC_MIDVALE_AND_MIDLAND_ID
  GBP_MWCC_ROCKINGHAM_ID
  GBP_MWCC_SEVILLEGROVE_ID
  GBP_MWCC_WAKIKI_ID

If GBP API quota is still 0 (project memory: pending quota increase request),
the script will write an "unavailable" placeholder with the error so the
dashboard can render a friendly "awaiting GBP API quota" state.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

STATE_DIR   = BASE_DIR / "state"
OUTPUT_FILE = STATE_DIR / "mwcc-gbp-performance.json"

# 5 MWCC centres — display name → env var with location ID
CENTRES = [
    ("Armadale",      "GBP_MWCC_ARMADALE_ID"),
    ("Midvale",       "GBP_MWCC_MIDVALE_AND_MIDLAND_ID"),
    ("Rockingham",    "GBP_MWCC_ROCKINGHAM_ID"),
    ("Seville Grove", "GBP_MWCC_SEVILLEGROVE_ID"),
    ("Waikiki",       "GBP_MWCC_WAKIKI_ID"),
]

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
    """Last completed Sat-Fri week — matches all marketing pulls."""
    today = datetime.today()
    days_since_friday = (today.weekday() - 4) % 7
    end   = today - timedelta(days=days_since_friday)
    start = end - timedelta(days=6)
    return start, end


def _build_perf_service():
    """Return authorised GBP Performance API client, or None."""
    sys.path.insert(0, str(BASE_DIR / "scripts"))
    try:
        from google_auth import get_valid_credentials
    except ImportError as e:
        print(f"[mwcc-gbp-perf] Could not import google_auth: {e}")
        return None
    try:
        from googleapiclient.discovery import build
    except ImportError:
        print("[mwcc-gbp-perf] google-api-python-client not installed.")
        return None

    creds = get_valid_credentials()
    return build("businessprofileperformance", "v1",
                 credentials=creds, cache_discovery=False)


def _pull_location(perf_svc, location_id, start, end) -> dict:
    """Pull all configured metrics for one location, totalled over the
    date range. Returns dict { metric_name: weekly_total, error: str|None }."""
    try:
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
        # Some discovery client versions use dot-notation kwargs
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
            return {"error": str(e)[:250], "metrics": {}}
    except Exception as e:
        return {"error": str(e)[:250], "metrics": {}}

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


def _write_unavailable(reason: str):
    """Write an unavailable-state file the dashboard can read."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "brand":        "mwcc",
        "available":    False,
        "skip_reason":  reason,
    }, indent=2))
    print(f"[mwcc-gbp-perf] Wrote unavailable state → {OUTPUT_FILE.relative_to(BASE_DIR)}")
    print(f"[mwcc-gbp-perf] Reason: {reason}")


def main() -> int:
    perf_svc = _build_perf_service()
    if perf_svc is None:
        _write_unavailable("GBP Performance API client could not be built")
        return 1

    # Check all 5 IDs are present
    missing = [centre for centre, env_var in CENTRES if not os.getenv(env_var, "").strip()]
    if missing:
        _write_unavailable(f"Missing env vars for: {', '.join(missing)}")
        return 1

    start, end = _date_range()
    start_str = start.strftime("%Y-%m-%d")
    end_str   = end.strftime("%Y-%m-%d")
    print(f"[mwcc-gbp-perf] Period: {start_str} → {end_str}")
    print(f"[mwcc-gbp-perf] Pulling {len(CENTRES)} MWCC centres...\n")

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "brand":        "mwcc",
        "available":    True,
        "date_range":   {"start": start_str, "end": end_str},
        "centres":      {},
        "errors":       [],
    }

    centres_with_data = 0
    for centre_name, env_var in CENTRES:
        loc_id = os.getenv(env_var, "").strip()
        # Normalise: env values may or may not have "locations/" prefix
        if not loc_id.startswith("locations/"):
            loc_id = f"locations/{loc_id}"

        print(f"  Pulling {centre_name} ({loc_id})...")
        result = _pull_location(perf_svc, loc_id, start, end)
        m = result.get("metrics") or {}

        maps_impr   = m.get("BUSINESS_IMPRESSIONS_DESKTOP_MAPS", 0) + m.get("BUSINESS_IMPRESSIONS_MOBILE_MAPS", 0)
        search_impr = m.get("BUSINESS_IMPRESSIONS_DESKTOP_SEARCH", 0) + m.get("BUSINESS_IMPRESSIONS_MOBILE_SEARCH", 0)
        total_actions = (
            m.get("WEBSITE_CLICKS", 0)
            + m.get("CALL_CLICKS", 0)
            + m.get("BUSINESS_DIRECTION_REQUESTS", 0)
        )

        output["centres"][centre_name] = {
            "location_id":        loc_id,
            "error":              result.get("error"),
            "website_clicks":     m.get("WEBSITE_CLICKS", 0),
            "phone_clicks":       m.get("CALL_CLICKS", 0),
            "direction_requests": m.get("BUSINESS_DIRECTION_REQUESTS", 0),
            "maps_impressions":   maps_impr,
            "search_impressions": search_impr,
            "total_impressions":  maps_impr + search_impr,
            "total_actions":      total_actions,
            "raw_metrics":        m,
        }
        if result.get("error"):
            print(f"    ERROR: {result['error']}")
            output["errors"].append({"centre": centre_name, "error": result["error"]})
        else:
            centres_with_data += 1
            print(f"    actions={total_actions}, impressions={maps_impr + search_impr}, "
                  f"calls={m.get('CALL_CLICKS', 0)}, directions={m.get('BUSINESS_DIRECTION_REQUESTS', 0)}, "
                  f"web_clicks={m.get('WEBSITE_CLICKS', 0)}")

    # Combined totals across all 5 centres
    centres = output["centres"]
    output["combined"] = {
        "total_actions":      sum(c.get("total_actions", 0) for c in centres.values()),
        "total_impressions":  sum(c.get("total_impressions", 0) for c in centres.values()),
        "website_clicks":     sum(c.get("website_clicks", 0) for c in centres.values()),
        "phone_clicks":       sum(c.get("phone_clicks", 0) for c in centres.values()),
        "direction_requests": sum(c.get("direction_requests", 0) for c in centres.values()),
        "maps_impressions":   sum(c.get("maps_impressions", 0) for c in centres.values()),
        "search_impressions": sum(c.get("search_impressions", 0) for c in centres.values()),
        "centres_with_data":  centres_with_data,
        "centres_total":      len(CENTRES),
    }

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2, default=str))

    print(f"\n[mwcc-gbp-perf] Saved → {OUTPUT_FILE.relative_to(BASE_DIR)}")
    print(f"[mwcc-gbp-perf] {centres_with_data}/{len(CENTRES)} centres returned data")
    if output["combined"]["centres_with_data"] > 0:
        print(f"[mwcc-gbp-perf] Combined: {output['combined']['total_actions']} actions, "
              f"{output['combined']['total_impressions']} impressions")
    if output["errors"]:
        print(f"[mwcc-gbp-perf] ⚠️  {len(output['errors'])} centres had errors:")
        for err in output["errors"]:
            print(f"    {err['centre']}: {err['error'][:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
