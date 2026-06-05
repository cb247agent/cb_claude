"""
pull_mwcc_ga4.py — Pulls key metrics from GA4 for My World Childcare.
Property: MWCC_GA4_PROPERTY_ID (315149021)

Saves sessions, active users, key events, session duration, top pages,
traffic sources, and devices to state/mwcc-ga4.json.

Extra metrics vs CB247 pull_ga4.py:
  - activeUsers       → "Website Active Users" KPI in MWCC report
  - keyEvents         → "Key Events" KPI (enquiry-intent actions)
  - averageSessionDuration → session quality indicator
  - engagementRate    → per-page engagement (tracks /book-a-tour conversion leak)
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest

import google_auth

BASE_DIR    = Path(__file__).resolve().parent.parent
STATE_DIR   = BASE_DIR / "state"
OUTPUT_FILE = STATE_DIR / "mwcc-ga4.json"

# MWCC GA4 Property ID — set MWCC_GA4_PROPERTY_ID in .env
GA4_PROPERTY_ID = os.getenv("MWCC_GA4_PROPERTY_ID", "")


def get_default_date_range():
    """Returns (start_date, end_date) for last completed Sat–Fri week.
    Pulled on Monday — Friday conversions have had 72hrs to fully settle."""
    today = datetime.today()
    days_since_friday = (today.weekday() - 4) % 7
    end   = today - timedelta(days=days_since_friday)   # last Friday
    start = end - timedelta(days=6)                     # preceding Saturday
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


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


def pull_mwcc_ga4():
    """Fetch GA4 data for MWCC and save to state/mwcc-ga4.json"""
    if not GA4_PROPERTY_ID:
        print("[MWCC GA4] ERROR: MWCC_GA4_PROPERTY_ID not set in .env")
        _write_empty("MWCC_GA4_PROPERTY_ID not configured in .env")
        return None

    creds  = google_auth.get_valid_credentials()
    client = BetaAnalyticsDataClient(credentials=creds)

    start, end = get_default_date_range()
    prev_start = (datetime.strptime(start, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
    prev_end   = (datetime.strptime(end,   "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "brand":        "mwcc",
        "date_range":   {"start": start, "end": end},
        "property_id":  GA4_PROPERTY_ID,
    }

    # --- Overview: sessions, users, active users, key events, session quality ---
    # activeUsers = users with ≥1 engaged session (used as main "users" KPI in MWCC report)
    # keyEvents   = enquiry-intent actions (book-a-tour clicks, form starts, etc.)
    # averageSessionDuration — flagged in report when it collapsed to 24s
    overview = run_report(
        client, GA4_PROPERTY_ID, start, end,
        dimension_names=[],
        metrics=[
            "sessions",
            "totalUsers",
            "activeUsers",
            "newUsers",
            "keyEvents",
            "averageSessionDuration",
            "engagementRate",
        ]
    )
    prev_overview = run_report(
        client, GA4_PROPERTY_ID, prev_start, prev_end,
        dimension_names=[],
        metrics=[
            "sessions",
            "totalUsers",
            "activeUsers",
            "newUsers",
            "keyEvents",
            "averageSessionDuration",
            "engagementRate",
        ]
    )

    def flat(d):
        return {
            "sessions":               int(float(d.get("sessions", 0))),
            "users":                  int(float(d.get("totalUsers", 0))),
            "active_users":           int(float(d.get("activeUsers", 0))),
            "new_users":              int(float(d.get("newUsers", 0))),
            "key_events":             int(float(d.get("keyEvents", 0))),
            "avg_session_duration_s": round(float(d.get("averageSessionDuration", 0)), 1),
            "engagement_rate":        round(float(d.get("engagementRate", 0)), 4),
        }

    output["current"]  = flat(overview[0])      if overview else {}
    output["previous"] = flat(prev_overview[0]) if prev_overview else {}

    # --- Top pages by sessions (+ engagement rate — tracks /book-a-tour conversion) ---
    output["top_pages"] = run_report(
        client, GA4_PROPERTY_ID, start, end,
        dimension_names=["pagePath"],
        metrics=["screenPageViews", "sessions", "engagementRate"]
    )[:10]

    # --- Traffic sources (sessions + key events per channel) ---
    # Paid Social sessions are a key KPI in the MWCC Website tab
    output["traffic_sources"] = run_report(
        client, GA4_PROPERTY_ID, start, end,
        dimension_names=["sessionDefaultChannelGroup"],
        metrics=["sessions", "keyEvents"]
    )

    # --- Devices ---
    output["devices"] = run_report(
        client, GA4_PROPERTY_ID, start, end,
        dimension_names=["deviceCategory"],
        metrics=["sessions"]
    )

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))

    curr = output["current"]
    prev = output["previous"]
    def wow(curr_val, prev_val):
        if prev_val and prev_val > 0:
            return f"{((curr_val - prev_val) / prev_val * 100):+.1f}% WoW"
        return "no prior data"

    print(f"[MWCC GA4] Saved → {OUTPUT_FILE}")
    print(f"[MWCC GA4] Period : {start} to {end}")
    print(f"[MWCC GA4] Active Users    : {curr.get('active_users', 0):,}  ({wow(curr.get('active_users',0), prev.get('active_users',0))})")
    print(f"[MWCC GA4] Sessions        : {curr.get('sessions', 0):,}  ({wow(curr.get('sessions',0), prev.get('sessions',0))})")
    print(f"[MWCC GA4] Key Events      : {curr.get('key_events', 0):,}  ({wow(curr.get('key_events',0), prev.get('key_events',0))})")
    print(f"[MWCC GA4] Avg Session Dur : {curr.get('avg_session_duration_s', 0):.0f}s  ({wow(curr.get('avg_session_duration_s',0), prev.get('avg_session_duration_s',0))})")
    return output


def _write_empty(skip_reason):
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "brand":        "mwcc",
        "available":    False,
        "skip_reason":  skip_reason,
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))


if __name__ == "__main__":
    pull_mwcc_ga4()
