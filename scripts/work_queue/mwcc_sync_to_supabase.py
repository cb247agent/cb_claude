"""
mwcc_sync_to_supabase.py — push state/mwcc-work-queue.json → Supabase
mwcc_work_queue_actions table.

Mirrors sync_to_supabase.py exactly but targets the mwcc_ prefixed table.
This keeps MWCC isolated from CB247 — a query that targets the wrong
prefix returns wrong data, but the businesses cannot be mixed.

Compliance gate (added 2026-06-07):
    Every action is passed through scripts/work_queue/compliance.py before
    upsert. Actions with banned language (per mwcc-brand-voice.md DON'Ts)
    are rejected, logged to state/mwcc-compliance-rejections.json, and
    NOT synced. Pattern set includes ACL undefendable superlatives ('best
    childcare'), outcome guarantees ('guarantee your child will'), and
    unverified award/NQS claims.

Idempotent: upsert via id. Re-running with the same JSON is a no-op.

Run:
    .venv/bin/python3.13 scripts/work_queue/mwcc_sync_to_supabase.py

Wired into: scripts/weekly-report-mwcc.sh (after emitters complete).
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import sys
from pathlib import Path
from typing import List

import requests

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))  # so we can import compliance.py beside us
from compliance import check_actions  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STATE_DIR = BASE_DIR / "state"
WORK_QUEUE_FILE = STATE_DIR / "mwcc-work-queue.json"
REJECTIONS_FILE = STATE_DIR / "mwcc-compliance-rejections.json"

SUPABASE_URL = os.environ.get(
    "SUPABASE_URL",
    "https://ckjwzwktuiavyfuolbgx.supabase.co",
)
SUPABASE_KEY = os.environ.get(
    "SUPABASE_PUBLISHABLE_KEY",
    "sb_publishable_3giOfPJ92JW7DN8w9jPvoQ_cFo4rd0s",
)
TABLE = "mwcc_work_queue_actions"


def _headers() -> dict:
    return {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
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
        "actual_kpis":     action.get("actual_kpis"),
        "overall_verdict": action.get("overall_verdict"),
        "measured_at":     action.get("measured_at"),
        "notes_human":     action.get("notes_human") or "",
        # draft_link / publish_date NOT synced — columns don't exist in
        # mwcc_work_queue_actions table yet. The dashboard derives draft
        # URLs from the action title for blog actions as a fallback.
    }


def _upsert_batch(rows: List[dict]) -> tuple[int, str]:
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}"
    resp = requests.post(url, headers=_headers(), data=json.dumps(rows), timeout=30)
    return resp.status_code, resp.text


def _retry_one_by_one(chunk: List[dict], batch_label: str) -> tuple[int, list]:
    """Fix 10 Jun 2026 (mirrors sync_to_supabase.py): when a batch fails
    atomically, retry each row alone to isolate the bad row IDs."""
    print(f"    ⚠️  batch {batch_label} atomic failure — retrying row-by-row to isolate bad rows...")
    synced = 0
    failed: list = []
    for row in chunk:
        status, body = _upsert_batch([row])
        if 200 <= status < 300:
            synced += 1
        else:
            failed.append({
                "id":          row.get("id", "?"),
                "source_page": row.get("source_page", "?"),
                "status":      status,
                "error":       body[:200],
            })
    if synced:
        print(f"    ✅ {synced} of {len(chunk)} rows synced individually")
    if failed:
        print(f"    ❌ {len(failed)} rows could NOT be synced (bad data — fix manually):")
        for f in failed[:20]:
            print(f"       id={f['id']:50s} source={f['source_page']:15s} {f['status']} · {f['error']}")
    return synced, failed


def main():
    if not WORK_QUEUE_FILE.exists():
        print(f"[mwcc-sync] no {WORK_QUEUE_FILE} yet — run an emitter first")
        sys.exit(0)

    try:
        wq = json.loads(WORK_QUEUE_FILE.read_text())
    except Exception as e:
        print(f"[mwcc-sync] could not parse {WORK_QUEUE_FILE}: {e}")
        sys.exit(1)

    actions = wq.get("actions") or []
    if not actions:
        print("[mwcc-sync] no actions to sync")
        sys.exit(0)

    # ── Compliance gate ────────────────────────────────────────────────
    # Reject any action containing banned MWCC language (per
    # mwcc-brand-voice.md DON'Ts + Australian Consumer Law).
    clean_actions, rejected_actions = check_actions(actions, business="mwcc")
    if rejected_actions:
        print(f"[mwcc-sync] 🚫 COMPLIANCE: {len(rejected_actions)} action(s) blocked from sync:")
        for r in rejected_actions:
            print(f"  - {r.get('id', '?')[:24]:<24} | {r.get('title', '')[:60]}")
            print(f"      reason: {r['_rejection_reason']}")

        # Append to rejections log for audit. Never overwrite — only append.
        existing_rejections = []
        if REJECTIONS_FILE.exists():
            try:
                existing_rejections = json.loads(REJECTIONS_FILE.read_text()).get("rejections", [])
            except Exception:
                existing_rejections = []
        now_iso = _dt.datetime.now(_dt.timezone.utc).isoformat()
        for r in rejected_actions:
            existing_rejections.append({
                "rejected_at": now_iso,
                "id": r.get("id"),
                "title": r.get("title"),
                "description": r.get("description"),
                "source_agent": r.get("source_agent"),
                "source_page": r.get("source_page"),
                "reason": r["_rejection_reason"],
            })
        REJECTIONS_FILE.write_text(json.dumps(
            {"updated_at": now_iso, "rejections": existing_rejections},
            indent=2,
            ensure_ascii=False,
        ))
        print(f"[mwcc-sync] logged rejections → {REJECTIONS_FILE.relative_to(BASE_DIR)}")

    if not clean_actions:
        print("[mwcc-sync] no clean actions remaining after compliance gate — nothing to sync")
        sys.exit(0)

    print(f"[mwcc-sync] {len(clean_actions)} actions cleared compliance, queued for upsert to {TABLE}")

    rows = [_to_db_row(a) for a in clean_actions]

    # On atomic batch failure: fall through to row-by-row retry instead of
    # exiting — preserves remaining batches + isolates the bad row IDs.
    # Fix 10 Jun 2026 (mirrors sync_to_supabase.py).
    BATCH = 50
    synced = 0
    all_failed: list = []
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        batch_num = i // BATCH + 1
        status, body = _upsert_batch(chunk)
        if 200 <= status < 300:
            synced += len(chunk)
            print(f"  batch {batch_num}: {len(chunk)} OK ({status})")
        else:
            print(f"  batch {batch_num}: FAILED ({status})")
            print(f"    response (first 500 chars): {body[:500]}")
            ok, bad = _retry_one_by_one(chunk, str(batch_num))
            synced += ok
            all_failed.extend(bad)

    print()
    print(f"[mwcc-sync] {synced}/{len(rows)} actions synced to Supabase {TABLE}")
    if all_failed:
        print(f"[mwcc-sync] ⚠️  {len(all_failed)} rows could not be synced — see above for details.")
        sys.exit(3)


if __name__ == "__main__":
    main()
