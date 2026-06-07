"""
pull_mwcc_gsc.py — Pulls search performance data from Google Search Console for MWCC.
Saves top queries, impressions, clicks, CTR, position to state/mwcc-gsc-data.json.

Same OAuth flow as CB247 (uses scripts/google_auth.py + secrets/token.json with
webmasters.readonly scope). Requires cb_agent@chasingbetter.com.au to have been
added as a user on the myworldcc.com.au GSC property.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from googleapiclient.discovery import build

import google_auth

BASE_DIR    = Path(__file__).resolve().parent.parent
STATE_DIR   = BASE_DIR / "state"
OUTPUT_FILE = STATE_DIR / "mwcc-gsc-data.json"

# MWCC GSC site URL — domain property format (no https://)
MWCC_GSC_SITE_URL = os.getenv("MWCC_GSC_SITE_URL", "sc-domain:myworldcc.com.au")


def pull_mwcc_gsc():
    """Fetch MWCC GSC data and save to state/mwcc-gsc-data.json"""
    print(f"Authenticating for MWCC GSC pull ({MWCC_GSC_SITE_URL})…")
    creds = google_auth.get_valid_credentials()

    service = build("searchconsole", "v1", credentials=creds)

    # Date range: last completed Sat–Fri week (matches CB247 pull_gsc + MWCC ads pulls)
    today = datetime.today()
    days_since_friday = (today.weekday() - 4) % 7
    _end = today - timedelta(days=days_since_friday)
    _start = _end - timedelta(days=6)
    end_date = _end.strftime("%Y-%m-%d")
    start_date = _start.strftime("%Y-%m-%d")

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "brand":        "mwcc",
        "date_range":   {"start": start_date, "end": end_date},
        "site_url":     MWCC_GSC_SITE_URL,
    }

    # ── Top queries (1-100) ──
    print(f"  Pulling top queries for {start_date} → {end_date}…")
    queries_req = {
        "startDate":  start_date,
        "endDate":    end_date,
        "dimensions": ["query"],
        "rowLimit":   100,
    }
    queries_resp = service.searchanalytics().query(
        siteUrl=MWCC_GSC_SITE_URL, body=queries_req
    ).execute()
    queries = []
    for row in queries_resp.get("rows", []):
        queries.append({
            "query":       row["keys"][0],
            "clicks":      row.get("clicks", 0),
            "impressions": row.get("impressions", 0),
            "ctr":         round((row.get("ctr") or 0) * 100, 2),
            "position":    round(row.get("position") or 0, 2),
        })
    output["top_queries"] = queries
    print(f"  Got {len(queries)} queries")

    # ── Top pages ──
    print(f"  Pulling top pages…")
    pages_req = {
        "startDate":  start_date,
        "endDate":    end_date,
        "dimensions": ["page"],
        "rowLimit":   50,
    }
    pages_resp = service.searchanalytics().query(
        siteUrl=MWCC_GSC_SITE_URL, body=pages_req
    ).execute()
    pages = []
    for row in pages_resp.get("rows", []):
        pages.append({
            "url":         row["keys"][0],
            "clicks":      row.get("clicks", 0),
            "impressions": row.get("impressions", 0),
            "ctr":         round((row.get("ctr") or 0) * 100, 2),
            "position":    round(row.get("position") or 0, 2),
        })
    output["top_pages"] = pages
    print(f"  Got {len(pages)} pages")

    # ── Totals ──
    print(f"  Pulling totals…")
    totals_req = {
        "startDate":  start_date,
        "endDate":    end_date,
        "dimensions": [],
        "rowLimit":   1,
    }
    totals_resp = service.searchanalytics().query(
        siteUrl=MWCC_GSC_SITE_URL, body=totals_req
    ).execute()
    if totals_resp.get("rows"):
        r = totals_resp["rows"][0]
        output["totals"] = {
            "clicks":      r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "ctr":         round((r.get("ctr") or 0) * 100, 2),
            "position":    round(r.get("position") or 0, 2),
        }
    else:
        output["totals"] = {"clicks": 0, "impressions": 0, "ctr": 0, "position": 0}

    # ── Save ──
    STATE_DIR.mkdir(exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))
    print(f"\n[saved] {OUTPUT_FILE}")
    print(f"  totals: {output['totals']}")
    return output


if __name__ == "__main__":
    pull_mwcc_gsc()
