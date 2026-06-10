"""
migrate_kanban_stages.py — One-time migration of kanban stage names.

Changes:
  - 'Idea' → 'Proposed' (rename — semantic upgrade)
  - 'Denver Approval' → 'Angela QC' (per Tia 09 Jun 2026: Denver's gate
    moves to the front of the pipeline via the View Details popup)

Affects two Supabase tables:
  - planner_status.status (CB247)
  - mwcc_planner_status.status (MWCC)

Browser-side localStorage migration runs separately when cbState.planner
.init() loads — that path is in docs/index.html, not this script.

Usage:
  # 1. Dry-run first — shows what WOULD change
  python scripts/migrate_kanban_stages.py --dry-run

  # 2. After reviewing the dry-run, apply for real:
  python scripts/migrate_kanban_stages.py --apply

Safety:
  - Default mode is dry-run (no flag = nothing changes)
  - Connects to live Supabase — but only modifies the `status` column
  - Logs every row before + after change to migration-log-{ts}.json
  - Idempotent: re-running after a successful migration is a no-op
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Use the same credentials sync_to_supabase.py uses (public publishable key)
SUPABASE_URL = os.environ.get(
    "SUPABASE_URL",
    "https://ckjwzwktuiavyfuolbgx.supabase.co",
).rstrip("/")
SUPABASE_KEY = os.environ.get(
    "SUPABASE_PUBLISHABLE_KEY",
    "sb_publishable_3giOfPJ92JW7DN8w9jPvoQ_cFo4rd0s",
)

# The vocabulary change
RENAME_MAP = {
    "Idea": "Proposed",
    "Denver Approval": "Angela QC",
}

# Tables to migrate
TABLES = ["planner_status", "mwcc_planner_status"]


def _h():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _get(table: str) -> list[dict]:
    """Fetch all rows from a Supabase table."""
    url = f"{SUPABASE_URL}/rest/v1/{table}?select=*"
    req = urllib.request.Request(url, headers=_h())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  ⚠️  GET {table} failed: HTTP {e.code} — {e.read().decode()[:200]}")
        return []
    except Exception as e:
        print(f"  ⚠️  GET {table} failed: {e}")
        return []


def _patch(table: str, item_id: str, new_status: str) -> bool:
    """Update a single row's status via PATCH."""
    url = f"{SUPABASE_URL}/rest/v1/{table}?item_id=eq.{urllib.parse.quote(item_id)}"
    body = json.dumps({"status": new_status}).encode()
    req = urllib.request.Request(url, data=body, headers=_h(), method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
            return True
    except urllib.error.HTTPError as e:
        print(f"    ❌ PATCH {table}.{item_id}: HTTP {e.code} — {e.read().decode()[:200]}")
        return False
    except Exception as e:
        print(f"    ❌ PATCH {table}.{item_id}: {e}")
        return False


def main():
    import urllib.parse  # for _patch
    globals()["urllib"].parse = urllib.parse

    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="Actually apply changes. Without this, runs in dry-run mode.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Explicit dry-run mode (same as no flags).")
    args = parser.parse_args()

    is_dry_run = not args.apply
    mode_label = "DRY-RUN" if is_dry_run else "APPLY"
    print(f"[migrate] Mode: {mode_label}")
    print(f"[migrate] Supabase: {SUPABASE_URL}")
    print(f"[migrate] Rename map:")
    for old, new in RENAME_MAP.items():
        print(f"            '{old}' → '{new}'")
    print()

    log = {
        "started_at": datetime.now().isoformat(),
        "mode": mode_label,
        "rename_map": RENAME_MAP,
        "tables": {},
    }

    grand_total_changes = 0
    grand_total_errors = 0

    for table in TABLES:
        print(f"[migrate] Table: {table}")
        rows = _get(table)
        table_log = {
            "total_rows": len(rows),
            "rows_to_change": [],
            "rows_unchanged": 0,
            "changes_applied": 0,
            "errors": 0,
        }

        for row in rows:
            old_status = row.get("status")
            new_status = RENAME_MAP.get(old_status)
            if new_status is None:
                table_log["rows_unchanged"] += 1
                continue
            change_record = {
                "item_id": row.get("item_id"),
                "old_status": old_status,
                "new_status": new_status,
                "updated_by": row.get("updated_by"),
            }
            table_log["rows_to_change"].append(change_record)

            if is_dry_run:
                print(f"  [dry] would update {row.get('item_id')}: '{old_status}' → '{new_status}'")
            else:
                ok = _patch(table, row.get("item_id"), new_status)
                if ok:
                    table_log["changes_applied"] += 1
                    print(f"  ✅ updated {row.get('item_id')}: '{old_status}' → '{new_status}'")
                else:
                    table_log["errors"] += 1

        n_to_change = len(table_log["rows_to_change"])
        n_unchanged = table_log["rows_unchanged"]
        if n_to_change == 0:
            print(f"          → {len(rows)} rows scanned, 0 to change (already migrated or never used old names)")
        else:
            print(f"          → {len(rows)} rows scanned, {n_to_change} to change, {n_unchanged} unchanged")
            if not is_dry_run:
                print(f"          → Applied {table_log['changes_applied']} changes, {table_log['errors']} errors")

        grand_total_changes += n_to_change
        grand_total_errors += table_log["errors"]
        log["tables"][table] = table_log
        print()

    log["finished_at"] = datetime.now().isoformat()
    log["grand_total_changes"] = grand_total_changes
    log["grand_total_errors"] = grand_total_errors

    # Write log
    ts = datetime.now().strftime("%Y-%m-%d-%H%M")
    log_file = BASE_DIR / "state" / f"migration-kanban-{ts}-{mode_label.lower()}.json"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text(json.dumps(log, indent=2, default=str))
    print(f"[migrate] Log written → {log_file.relative_to(BASE_DIR)}")
    print()

    if is_dry_run:
        if grand_total_changes == 0:
            print("[migrate] ℹ️  Dry-run found 0 rows to change.")
            print("           Supabase is already clean — no migration needed on the data side.")
            print("           The kanban label/code changes still need to ship.")
        else:
            print(f"[migrate] ℹ️  Dry-run would change {grand_total_changes} rows.")
            print("           Review above, then re-run with --apply to commit.")
        return 0

    if grand_total_errors > 0:
        print(f"[migrate] ⚠️  Completed with {grand_total_errors} errors. Review log file.")
        return 1

    print(f"[migrate] ✅ Migration complete. {grand_total_changes} rows updated.")
    return 0


if __name__ == "__main__":
    import urllib.parse  # noqa — used in _patch
    sys.exit(main())
