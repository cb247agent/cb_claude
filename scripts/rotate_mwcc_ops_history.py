"""
rotate_mwcc_ops_history.py — append current mwcc-ops.json to mwcc-ops-history.json
so the dashboard can render week-on-week deltas.

Runs AFTER parse_mwcc_ops.py (Step 4 of weekly-report-mwcc.sh) — so the freshest
weekly snapshot is what gets appended.

History file shape:
    [
      { "period": {...}, "generated_at": "...", "centres": {...}, "network_summary": {...} },
      ...   # one entry per week, oldest first
    ]

Keeps last N weeks (default 12). Idempotent: if a snapshot for the same period.end
already exists, it's overwritten — running this twice in the same week is safe.

Run:
    .venv/bin/python3.13 scripts/rotate_mwcc_ops_history.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR     = Path(__file__).resolve().parent.parent
STATE_DIR    = BASE_DIR / "state"
CURRENT_FILE = STATE_DIR / "mwcc-ops.json"
HISTORY_FILE = STATE_DIR / "mwcc-ops-history.json"
KEEP_WEEKS   = 12


def _load_current() -> Dict[str, Any] | None:
    if not CURRENT_FILE.exists():
        return None
    try:
        return json.loads(CURRENT_FILE.read_text())
    except Exception as e:
        print(f"[rotate] could not parse {CURRENT_FILE}: {e}")
        return None


def _load_history() -> List[Dict[str, Any]]:
    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text())
        if isinstance(data, list):
            return data
    except Exception as e:
        print(f"[rotate] could not parse {HISTORY_FILE}: {e}")
    return []


def _snapshot_from(current: Dict[str, Any]) -> Dict[str, Any]:
    """Trim the snapshot to only the fields the dashboard needs for deltas."""
    return {
        "period":          current.get("period", {}),
        "generated_at":    current.get("generated_at"),
        "brand":           current.get("brand", "mwcc"),
        "network_summary": current.get("network_summary", {}),
        "centres":         current.get("centres", {}),
    }


def main() -> int:
    current = _load_current()
    if not current:
        print(f"[rotate] no {CURRENT_FILE} found — nothing to rotate (graceful skip)")
        return 0

    snapshot = _snapshot_from(current)
    snap_period_end = (snapshot.get("period") or {}).get("end")
    if not snap_period_end:
        print("[rotate] current snapshot has no period.end — skipping (won't rotate without a key)")
        return 0

    history = _load_history()

    # Remove any existing snapshot for the same period.end (idempotent)
    history = [h for h in history if (h.get("period") or {}).get("end") != snap_period_end]

    history.append(snapshot)

    # Sort by period.end ascending so history[-1] is the most recent
    history.sort(key=lambda h: (h.get("period") or {}).get("end") or "")

    # Keep last KEEP_WEEKS
    if len(history) > KEEP_WEEKS:
        history = history[-KEEP_WEEKS:]

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(history, indent=2, default=str))

    print(f"[rotate] {HISTORY_FILE.name}: {len(history)} week(s), latest period.end = {snap_period_end}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
