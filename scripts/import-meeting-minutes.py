"""
import-meeting-minutes.py — CB247 Marketing OS

Takes a meeting-minutes-YYYY-MM-DD.json (exported from docs/meeting-minutes.html)
and pushes decisions + context into state/action-tracker.json.

Usage:
  python scripts/import-meeting-minutes.py                          # auto-finds latest
  python scripts/import-meeting-minutes.py state/meeting-minutes-2026-06-02.json

What it does:
  1. Reads meeting minutes JSON
  2. Updates action-tracker.json with decisions (approved/adjusted/rejected)
  3. Sets due dates + status to in_progress for approved actions
  4. Logs meeting minutes into tracker history
  5. Prints summary of what changed
"""

import json
import sys
import glob
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR  = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
TRACKER   = STATE_DIR / "action-tracker.json"


def load_json(path):
    return json.loads(Path(path).read_text())


def save_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2))


def find_latest_minutes():
    files = sorted(glob.glob(str(STATE_DIR / "meeting-minutes-*.json")), reverse=True)
    return files[0] if files else None


def main():
    # ── Find minutes file ──────────────────────────────────────────────
    if len(sys.argv) > 1:
        minutes_path = sys.argv[1]
    else:
        minutes_path = find_latest_minutes()

    if not minutes_path or not Path(minutes_path).exists():
        print("❌ No meeting minutes file found.")
        print("   Drop file at: state/meeting-minutes-YYYY-MM-DD.json")
        print("   Or generate from: https://cb247agent.github.io/cb_claude/meeting-minutes.html")
        sys.exit(1)

    print(f"\n📋 Importing: {Path(minutes_path).name}")
    minutes = load_json(minutes_path)

    if not TRACKER.exists():
        print("❌ state/action-tracker.json not found.")
        sys.exit(1)

    tracker = load_json(TRACKER)
    actions_map = {a["id"]: a for a in tracker.get("actions", [])}

    meeting_date = minutes.get("meeting_date", datetime.now().strftime("%Y-%m-%d"))
    now_str      = datetime.now().strftime("%Y-%m-%d")

    counts = {"approved": 0, "adjusted": 0, "rejected": 0, "pending": 0}

    # ── Apply decisions ────────────────────────────────────────────────
    for dec in minutes.get("decisions", []):
        action_id = dec.get("id")
        decision  = dec.get("decision", "pending")

        if action_id not in actions_map:
            print(f"  ⚠️  Action {action_id} not found in tracker — skipping")
            continue

        action = actions_map[action_id]
        action["decision"]       = decision
        action["decision_date"]  = meeting_date
        action["decision_notes"] = dec.get("notes", "")

        if decision == "adjusted":
            action["adjusted_brief"] = dec.get("adjusted_brief", "")

        # Auto-progress status based on decision
        if decision == "approved":
            action["status"] = "in_progress"
            action["started_date"] = now_str
        elif decision == "rejected":
            action["status"] = "cancelled"
        # adjusted stays pending until brief is confirmed

        counts[decision] = counts.get(decision, 0) + 1
        print(f"  {'✅' if decision == 'approved' else '🔄' if decision == 'adjusted' else '❌' if decision == 'rejected' else '⏸'} "
              f"{action_id}: {decision.upper()} — {action['recommendation'][:60]}…")

    # ── Add any custom decisions as new tracker items ──────────────────
    custom = minutes.get("custom_decisions", [])
    if custom:
        counter = tracker.get("action_counter", len(tracker.get("actions", [])))
        for text in custom:
            if not text.strip():
                continue
            counter += 1
            new_id = f"ACT-{counter:03d}"
            tracker["actions"].append({
                "id": new_id,
                "week": meeting_date,
                "source": "meeting-minutes",
                "recommendation": text,
                "category": "operations",
                "owner": "Tia",
                "ownerRole": "Director",
                "priority": "P2",
                "context": f"Added in meeting: {meeting_date}",
                "decision": "approved",
                "decision_date": meeting_date,
                "decision_notes": "",
                "adjusted_brief": "",
                "status": "in_progress",
                "due_date": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
                "started_date": now_str,
                "completed_date": None,
                "execution_notes": "",
                "review_date": (datetime.now() + timedelta(days=21)).strftime("%Y-%m-%d"),
                "outcome_assessed": False,
                "kpis": [],
                "projected_impact": {},
                "actual_impact": {},
                "outcome_notes": "",
                "outcome_verdict": None
            })
            print(f"  ➕ {new_id}: Added from meeting — {text[:60]}…")
        tracker["action_counter"] = counter

    # ── Store meeting minutes in tracker history ───────────────────────
    if "meeting_minutes" not in tracker:
        tracker["meeting_minutes"] = []

    tracker["meeting_minutes"].append({
        "date": meeting_date,
        "attendees": minutes.get("attendees", []),
        "narrative": minutes.get("weekly_narrative", ""),
        "active_promos": minutes.get("active_promos", []),
        "promo_details": minutes.get("promo_details", ""),
        "campaign_brief": minutes.get("campaign_brief", ""),
        "decisions_summary": counts,
        "imported_at": datetime.now().isoformat()
    })

    tracker["last_updated"] = now_str
    save_json(TRACKER, tracker)

    # ── Summary ────────────────────────────────────────────────────────
    print(f"\n✅ Import complete.")
    print(f"   Meeting: {meeting_date} | Attendees: {', '.join(minutes.get('attendees', []))}")
    print(f"   Decisions: {counts['approved']} approved · {counts['adjusted']} adjusted · {counts['rejected']} rejected · {counts.get('pending', 0)} pending")
    if custom:
        print(f"   Custom actions added: {len(custom)}")
    if minutes.get("active_promos"):
        print(f"   Active promos: {', '.join(minutes['active_promos'])}")
    print(f"\n   Tracker updated: {TRACKER}")
    print(f"   Rebuild dashboard: python scripts/bake-public-dashboard.py")
    print(f"   Deploy: bash scripts/deploy-dashboard.sh")


if __name__ == "__main__":
    main()
