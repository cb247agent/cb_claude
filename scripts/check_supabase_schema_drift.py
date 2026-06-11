"""
check_supabase_schema_drift.py — Wave A.2 (dev cycle) — detect when the
Python schema, the SQL schema, and the live Supabase DB disagree about
allowed values for enum-like columns.

WHY THIS EXISTS
    On 10 Jun 2026 we renamed Kanban stages in the Python schema
    (VALID_STAGE = {'Proposed', 'In Progress', 'Brand Manager QC', ...}),
    but Supabase still had the old CHECK constraint with 'Idea', 'Angela
    QC', 'Denver Approval'. Upserts with new values were silently
    rejected. The dashboard appeared to work but Approved items never
    surfaced cross-browser. Tia spotted it manually after a few days.

    This script detects that drift in 3 ways:
      1. Python (schema.py constants) vs SQL (db/schema.sql CHECK clauses)
      2. Live Supabase canary probe (optional --live flag) — attempt an
         upsert with each known-allowed value, see if Supabase accepts it.
         Auto-cleans up canary rows. Reveals drift between schema.sql and
         what's actually applied to the live DB.

EXIT CODES
    0 = no drift detected (or warnings only — default)
    1 = drift detected AND --strict was passed (promote to blocking)
    2 = scanner itself errored

USAGE
    .venv/bin/python3.13 scripts/check_supabase_schema_drift.py
    .venv/bin/python3.13 scripts/check_supabase_schema_drift.py --live    # probe live DB
    .venv/bin/python3.13 scripts/check_supabase_schema_drift.py --strict  # block on drift

CALLED BY
    - scripts/dev-cycle.sh --pre-commit  (code-vs-code check, fast)
    - scripts/dev-cycle.sh --pre-flight  (with --live, before Monday's data pull)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from work_queue.schema import (   # noqa: E402
    VALID_SOURCE_PAGES,
    VALID_PRIORITY,
    VALID_DATA_QUALITY,
    VALID_VERDICT,
)

BASE_DIR = _HERE.parent
LOG_DIR = BASE_DIR / "logs"
SCHEMA_SQL = BASE_DIR / "db" / "schema.sql"

load_dotenv(BASE_DIR / ".env")

SUPABASE_URL = os.environ.get(
    "SUPABASE_URL",
    "https://ckjwzwktuiavyfuolbgx.supabase.co",
)
SUPABASE_KEY = os.environ.get(
    "SUPABASE_PUBLISHABLE_KEY",
    "sb_publishable_3giOfPJ92JW7DN8w9jPvoQ_cFo4rd0s",
)


# ── Step 1: extract CHECK IN clauses from db/schema.sql ─────────────────────


CHECK_IN_RE = re.compile(
    r"CHECK\s*\(\s*(\w+)\s+IN\s*\(([^)]+)\)",
    re.IGNORECASE | re.DOTALL,
)


def _strip_sql_comments(sql: str) -> str:
    """Remove '-- ...' line comments — they often contain the constraint
    list inside narrative text, which would otherwise be captured as if
    it were SQL."""
    out_lines = []
    for line in sql.split("\n"):
        idx = line.find("--")
        if idx >= 0:
            line = line[:idx]
        out_lines.append(line)
    return "\n".join(out_lines)


def extract_sql_check_values(sql_text: str) -> dict[str, set[str]]:
    """Parse all `CHECK (column IN ('a', 'b', ...))` clauses out of
    schema.sql and return {column_name: {allowed values...}}."""
    out: dict[str, set[str]] = {}
    sql_text = _strip_sql_comments(sql_text)
    for match in CHECK_IN_RE.finditer(sql_text):
        column = match.group(1).strip()
        values_blob = match.group(2)
        values = {
            v.strip().strip("'\"")
            for v in values_blob.split(",")
            if v.strip().strip("'\"")
        }
        out.setdefault(column, set()).update(values)
    return out


# ── Step 2: code-vs-code drift check ────────────────────────────────────────


PYTHON_ENUMS = {
    "source_page":     VALID_SOURCE_PAGES,
    "priority":        VALID_PRIORITY,
    "data_quality":    VALID_DATA_QUALITY,
    "overall_verdict": VALID_VERDICT,
}


def check_python_vs_sql() -> list[dict]:
    """Compare Python schema enums against SQL CHECK IN clauses."""
    findings: list[dict] = []
    if not SCHEMA_SQL.exists():
        findings.append({
            "severity": "ERROR",
            "kind":     "missing-file",
            "detail":   f"{SCHEMA_SQL.relative_to(BASE_DIR)} missing — can't compare",
        })
        return findings

    sql_values = extract_sql_check_values(SCHEMA_SQL.read_text())

    for column, python_set in PYTHON_ENUMS.items():
        sql_set = sql_values.get(column, set())
        if not sql_set:
            findings.append({
                "severity": "WARN",
                "kind":     "missing-sql-constraint",
                "column":   column,
                "detail":   f"Python declares values {sorted(python_set)} but db/schema.sql has no CHECK IN clause for column '{column}' — either skipped intentionally or the column was renamed.",
            })
            continue

        # Allow legacy values in SQL that aren't in Python (kept around for
        # in-flight rows during a migration). But flag anything Python
        # declares as valid that SQL refuses — THAT'S the bug we hit.
        python_only = python_set - sql_set
        sql_only    = sql_set - python_set

        if python_only:
            findings.append({
                "severity": "ERROR",
                "kind":     "python-ahead-of-sql",
                "column":   column,
                "detail":   f"Python declares {sorted(python_only)} as valid but db/schema.sql does NOT. Upserts using these values will be rejected by the CHECK constraint. Apply a migration that ADDs these to the CHECK IN clause.",
            })

        if sql_only:
            findings.append({
                "severity": "INFO",
                "kind":     "sql-has-legacy",
                "column":   column,
                "detail":   f"SQL CHECK accepts {sorted(sql_only)} but Python doesn't declare them — likely legacy values kept around for in-flight migration. Drop from SQL once safe.",
            })

    return findings


# ── Step 3: live Supabase probe (optional, slow) ─────────────────────────────


def _headers() -> dict:
    return {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "return=minimal",
    }


def _canary_row(source_page: str, priority: str, data_quality: str) -> dict:
    return {
        "id":             f"drift-canary-{uuid.uuid4().hex[:12]}",
        "source_page":    source_page,
        "source_run_at":  datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "title":          "[drift canary] safe to delete",
        "description":   "Auto-generated by scripts/check_supabase_schema_drift.py — should be deleted within seconds of insert.",
        "owner":          "drift-canary",
        "owner_role":     "system",
        "priority":       priority,
        "effort_hours":   0.1,
        "category":       source_page,
        "data_quality":   data_quality,
        "projected_kpis": [],
    }


def _live_probe_column(column: str, values: set[str]) -> list[dict]:
    """For each declared-valid value in `values`, attempt to upsert + delete
    a canary row using that value. Report Supabase rejections as drift.

    Only meaningful for columns where we can construct a minimal valid
    canary row. Currently: source_page, priority, data_quality.
    """
    findings: list[dict] = []
    url = f"{SUPABASE_URL}/rest/v1/work_queue_actions"
    cleanup_ids: list[str] = []

    fixed_source_page  = "seo-organic"
    fixed_priority     = "P3"
    fixed_data_quality = "low"

    for v in sorted(values):
        if column == "source_page":
            row = _canary_row(v, fixed_priority, fixed_data_quality)
        elif column == "priority":
            row = _canary_row(fixed_source_page, v, fixed_data_quality)
        elif column == "data_quality":
            row = _canary_row(fixed_source_page, fixed_priority, v)
        else:
            continue   # overall_verdict is nullable; harder to probe

        try:
            r = requests.post(url, headers=_headers(), data=json.dumps([row]), timeout=20)
        except requests.RequestException as e:
            findings.append({
                "severity": "ERROR",
                "kind":     "live-probe-network",
                "column":   column,
                "value":    v,
                "detail":   f"Network error during live probe: {e}",
            })
            continue

        if 200 <= r.status_code < 300:
            cleanup_ids.append(row["id"])
            continue   # value accepted — no drift

        # 4xx → Supabase rejected. Likely a CHECK constraint mismatch.
        findings.append({
            "severity": "ERROR",
            "kind":     "live-rejected",
            "column":   column,
            "value":    v,
            "status":   r.status_code,
            "detail":   f"Live Supabase REJECTED value '{v}' for column '{column}' (HTTP {r.status_code}). Code declares it valid; live DB disagrees. Apply migration to align CHECK constraint. Server: {r.text[:200]}",
        })

    # Clean up any canaries we managed to insert
    if cleanup_ids:
        in_clause = "(" + ",".join(f'"{cid}"' for cid in cleanup_ids) + ")"
        try:
            requests.delete(
                f"{url}?id=in.{in_clause}",
                headers=_headers(),
                timeout=20,
            )
        except requests.RequestException:
            pass   # best-effort cleanup; the canaries are tagged for human delete too

    return findings


def check_live_drift() -> list[dict]:
    findings: list[dict] = []
    for col, values in (
        ("source_page",  VALID_SOURCE_PAGES),
        ("priority",     VALID_PRIORITY),
        ("data_quality", VALID_DATA_QUALITY),
    ):
        findings.extend(_live_probe_column(col, values))
    return findings


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> int:
    p = argparse.ArgumentParser(description="Supabase schema drift detector")
    p.add_argument("--live", action="store_true",
                   help="Also probe the live Supabase DB with canary upserts (slower; needs network)")
    p.add_argument("--strict", action="store_true",
                   help="Exit 1 if any ERROR-severity findings (default: warn only)")
    p.add_argument("--log", action="store_true",
                   help="Also write findings to logs/schema-drift-<date>.json")
    args = p.parse_args()

    print(f"[schema-drift] Comparing Python schema vs db/schema.sql...")
    findings = check_python_vs_sql()

    if args.live:
        print(f"[schema-drift] Probing live Supabase ({SUPABASE_URL}) with canary upserts...")
        findings.extend(check_live_drift())

    errors = [f for f in findings if f["severity"] == "ERROR"]
    warns  = [f for f in findings if f["severity"] == "WARN"]
    infos  = [f for f in findings if f["severity"] == "INFO"]

    if not findings:
        print(f"[schema-drift] ✅ No drift detected.")
        return 0

    print()
    print(f"[schema-drift] Findings: {len(errors)} ERROR · {len(warns)} WARN · {len(infos)} INFO")
    print()
    for f in findings:
        prefix = {"ERROR": "❌", "WARN": "⚠️ ", "INFO": "ℹ️ "}[f["severity"]]
        print(f"{prefix} [{f['severity']}] {f['kind']}  column={f.get('column', '?')}")
        print(f"   {f['detail']}")
        print()

    if args.log:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOG_DIR / f"schema-drift-{datetime.now().strftime('%Y-%m-%d')}.json"
        log_path.write_text(json.dumps({
            "ran_at":   datetime.utcnow().isoformat() + "Z",
            "live":     args.live,
            "findings": findings,
        }, indent=2))
        print(f"[schema-drift] Findings written to {log_path.relative_to(BASE_DIR)}")

    if args.strict and errors:
        print(f"[schema-drift] ❌ --strict set and {len(errors)} ERROR finding(s) — exit 1.")
        return 1

    if errors:
        print(f"[schema-drift] ⚠️  Errors found but warn-only mode — exit 0. Promote to blocking with --strict.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[schema-drift] ERROR: {e}", file=sys.stderr)
        sys.exit(2)
