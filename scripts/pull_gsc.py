"""
pull_gsc.py — Pulls search performance data from Google Search Console API.
Saves top queries, impressions, clicks, CTR, position to state/gsc-data.json.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow

import google_auth

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
OUTPUT_FILE = STATE_DIR / "gsc-data.json"

# GSC site URL — from GSC property settings
# Format: https://www.chasingbetter247.com.au/  (include trailing slash)
GSC_SITE_URL = os.getenv("GSC_SITE_URL", "sc-domain:chasingbetter247.com.au")

SCOPES_GSC = ["https://www.googleapis.com/auth/webmasters.readonly"]


def pull_gsc():
    """Fetch GSC data and save to state/gsc-data.json"""
    creds = google_auth.get_valid_credentials()

    # Build the service with webmasters scope
    service = build("searchconsole", "v1", credentials=creds)

    # Date range: last 7 days (matches GA4 + Google Ads weekly reporting window)
    end_date   = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")   # yesterday = May 31
    start_date = (datetime.today() - timedelta(days=7)).strftime("%Y-%m-%d")   # 7 days back = May 25

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "date_range": {"start": start_date, "end": end_date},
        "site_url": GSC_SITE_URL,
    }

    # --- Search analytics: queries ---
    request = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": ["query"],
        "rowLimit": 100,
    }

    response = service.searchanalytics().query(
        siteUrl=GSC_SITE_URL,
        body=request
    ).execute()

    rows = []
    for row in response.get("rows", []):
        rows.append({
            "query":      row["keys"][0],
            "clicks":     row.get("clicks", 0),
            "impressions":row.get("impressions", 0),
            "ctr":        round(row.get("ctr", 0), 4),
            "position":   round(row.get("position", 0), 1),
        })

    # Sort by clicks descending
    rows.sort(key=lambda x: x["clicks"], reverse=True)
    output["top_queries"] = rows[:50]  # top 50

    # --- Aggregate summary ---
    total_clicks     = sum(r["clicks"]      for r in rows)
    total_impressions= sum(r["impressions"] for r in rows)
    avg_ctr          = total_clicks / total_impressions if total_impressions > 0 else 0
    avg_position     = sum(r["position"] * r["clicks"] for r in rows) / total_clicks if total_clicks > 0 else 0

    output["summary"] = {
        "total_clicks":      total_clicks,
        "total_impressions": total_impressions,
        "avg_ctr":           round(avg_ctr, 4),
        "avg_position":      round(avg_position, 1),
        "total_queries":     len(rows),
    }

    # --- Pages breakdown ---
    request_pages = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": ["page"],
        "rowLimit": 20,
    }
    pages_response = service.searchanalytics().query(
        siteUrl=GSC_SITE_URL,
        body=request_pages
    ).execute()

    output["top_pages"] = [
        {
            "page":       row["keys"][0],
            "clicks":     row.get("clicks", 0),
            "impressions":row.get("impressions", 0),
            "ctr":        round(row.get("ctr", 0), 4),
            "position":   round(row.get("position", 0), 1),
        }
        for row in pages_response.get("rows", [])
    ]

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))
    print(f"GSC data saved to {OUTPUT_FILE}")
    return output


if __name__ == "__main__":
    pull_gsc()