"""
pull_ga4.py — Pulls key metrics from GA4 Data API.
Saves sessions, users, conversions, top pages, traffic sources to state/ga4-data.json.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

# Load .env from CB_Marketing root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest

import google_auth

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
OUTPUT_FILE = STATE_DIR / "ga4-data.json"

# GA4 numeric Property ID — from .env (GA4 Admin → Property Settings → Property ID)
GA4_PROPERTY_ID = os.getenv("GA4_PROPERTY_ID", "")


def get_default_date_range():
    """Returns (start_date, end_date) for last 7 days"""
    end = datetime.today().strftime("%Y-%m-%d")
    start = (datetime.today() - timedelta(days=7)).strftime("%Y-%m-%d")
    return start, end


def run_report(client, property_id, start_date, end_date, dimension_names, metrics):
    """Run a GA4 report and return results as a list of dicts."""
    request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        dimensions=[Dimension(name=n) for n in dimension_names] if dimension_names else [],
        metrics=[Metric(name=m) for m in metrics],
    )
    response = client.run_report(request)

    rows = []
    for row in response.rows:
        row_dict = {}
        for i, dim_val in enumerate(row.dimension_values):
            row_dict[dimension_names[i]] = dim_val.value
        for i, metric_val in enumerate(row.metric_values):
            row_dict[metrics[i]] = metric_val.value
        rows.append(row_dict)
    return rows


def pull_ga4():
    """Fetch GA4 data and save to state/ga4-data.json"""
    if not GA4_PROPERTY_ID:
        print("[GA4] ERROR: GA4_PROPERTY_ID not set in .env")
        _write_empty("GA4_PROPERTY_ID not configured in .env")
        return None

    creds = google_auth.get_valid_credentials()
    client = BetaAnalyticsDataClient(credentials=creds)

    start, end = get_default_date_range()
    prev_start = (datetime.strptime(start, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
    prev_end   = (datetime.strptime(end,   "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "date_range": {"start": start, "end": end},
        "property_id": GA4_PROPERTY_ID,
    }

    # --- Sessions & Users overview (current week) ---
    overview = run_report(
        client, GA4_PROPERTY_ID, start, end,
        dimension_names=[],
        metrics=["sessions", "totalUsers", "newUsers", "conversions"]
    )
    prev_overview = run_report(
        client, GA4_PROPERTY_ID, prev_start, prev_end,
        dimension_names=[],
        metrics=["sessions", "totalUsers", "newUsers", "conversions"]
    )

    def flat(d):
        return {
            "sessions":    int(d.get("sessions", 0)),
            "users":       int(d.get("totalUsers", 0)),
            "new_users":   int(d.get("newUsers", 0)),
            "conversions": int(d.get("conversions", 0)),
        }

    output["current"]  = flat(overview[0])      if overview else {}
    output["previous"] = flat(prev_overview[0]) if prev_overview else {}

    # --- Top pages by sessions ---
    output["top_pages"] = run_report(
        client, GA4_PROPERTY_ID, start, end,
        dimension_names=["pagePath"],
        metrics=["screenPageViews", "sessions"]
    )[:10]

    # --- Traffic sources ---
    output["traffic_sources"] = run_report(
        client, GA4_PROPERTY_ID, start, end,
        dimension_names=["sessionDefaultChannelGroup"],
        metrics=["sessions", "conversions"]
    )

    # --- Devices ---
    output["devices"] = run_report(
        client, GA4_PROPERTY_ID, start, end,
        dimension_names=["deviceCategory"],
        metrics=["sessions"]
    )

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))
    print(f"GA4 data saved to {OUTPUT_FILE}")
    return output


def _write_empty(skip_reason):
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "available": False,
        "skip_reason": skip_reason,
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))


if __name__ == "__main__":
    pull_ga4()