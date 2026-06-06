"""
sync_to_supabase.py — push state/work-queue.json → Supabase work_queue_actions.

Reads the JSON file written by each source emitter and upserts every action
to the Supabase REST API. The publishable key is hard-coded (it's already
public in docs/index.html and designed for client-side use).

Idempotent: upsert via id. Re-running with the same JSON is a no-op.

Run:
    .venv/bin/python3.13 scripts/work_queue/sync_to_supabase.py

Wired into: scripts/weekly-report.sh Step 1i (after Step 1h emitter).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import List

import requests

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STATE_DIR = BASE_DIR / "state"
WORK_QUEUE_FILE = STATE_DIR / "work-queue.json"

# Supabase credentials — publishable key is safe to embed (designed for client use)
# RLS policies on work_queue_actions allow anon role to insert/update/select.
SUPABASE_URL = os.environ.get(
    "SUPABASE_URL",
    "https://ckjwzwktuiavyfuolbgx.supabase.co",
)
SUPABASE_KEY = os.environ.get(
    "SUPABASE_PUBLISHABLE_KEY",
    "sb_publishable_3giOfPJ92JW7DN8w9jPvoQ_cFo4rd0s",
)
TABLE = "work_queue_actions"


def _headers() -> dict:
    return {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
        # resolution=merge-duplicates makes POST act as upsert on PK conflict
        "Prefer":        "resolution=merge-duplicates,return=minimal",
    }


def _to_db_row(action: dict) -> dict:
    """Convert WorkQueueAction dict shape to DB column shape."""
    return {
        "id":              action["id"],
        "source_page":     action["source_page"],
        "source_run_at":   action["source_run_at"],
        "title":           action["title"],
        "description":     action.get("description") or "",
        "owner":           action.get("owner"),
        "owner_role":      action.get("owner_role"),
        "priority":        action["priority"],
        "effort_hours":    action.get("effort_hours"),
        "category":        action.get("category"),
        "data_quality":    action.get("data_quality"),
        "projected_kpis":  action.get("projected_kpis") or [],
        "urgent":          bool(action.get("urgent", False)),
        "related_actions": action.get("related_actions") or [],
        # measurement-time fields — filled later by the verdict job (Session 3)
        "actual_kpis":     action.get("actual_kpis"),
        "overall_verdict": action.get("overall_verdict"),
        "measured_at":     action.get("measured_at"),
        "notes_human":     action.get("notes_human") or "",
    }


def _upsert_batch(rows: List[dict]) -> tuple[int, str]:
    """POST a batch of rows. Returns (status_code, response_text)."""
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}"
    resp = requests.post(url, headers=_headers(), data=json.dumps(rows), timeout=30)
    return resp.status_code, resp.text


def main():
    if not WORK_QUEUE_FILE.exists():
        print(f"[sync] no {WORK_QUEUE_FILE} yet — run an emitter first")
        sys.exit(0)

    try:
        wq = json.loads(WORK_QUEUE_FILE.read_text())
    except Exception as e:
        print(f"[sync] could not parse {WORK_QUEUE_FILE}: {e}")
        sys.exit(1)

    actions = wq.get("actions") or []
    if not actions:
        print("[sync] no actions to sync")
        sys.exit(0)

    print(f"[sync] {len(actions)} actions queued for upsert to {TABLE}")

    rows = [_to_db_row(a) for a in actions]

    # Upsert in batches of 50 to stay well under any payload limits
    BATCH = 50
    synced = 0
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        status, body = _upsert_batch(chunk)
        if 200 <= status < 300:
            synced += len(chunk)
            print(f"  batch {i // BATCH + 1}: {len(chunk)} OK ({status})")
        else:
            print(f"  batch {i // BATCH + 1}: FAILED ({status})")
            print(f"    response (first 500 chars): {body[:500]}")
            sys.exit(2)

    print(f"[sync] OK — {synced}/{len(rows)} actions synced to Supabase {TABLE}")


if __name__ == "__main__":
    main()
