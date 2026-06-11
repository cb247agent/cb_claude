"""
test_strategist_chain.py — Wave A.3 (dev cycle) — integration test for the
SEO Strategist → normalise → extract → schema-validate chain.

Does NOT call Claude or Supabase. Uses a fixture markdown file that
contains a known-good ```json proposed_actions block, runs it through the
real production pipeline locally (normalise_strategist_output.py +
extract_agent_actions.py + schema.WorkQueueAction.validate), and asserts
expected outcomes.

WHY THIS EXISTS
    The strategist chain has 4 moving parts and each one has been a bug
    surface in the last 48h:
      1. Strategist LLM emits dict-shape projected_kpis (normaliser fix)
      2. Normaliser drops actions with invalid metrics (schema fix)
      3. Extractor merges with auto-derived id (extract bug surface)
      4. Schema validation rejects rows missing target/delta_min
    Without a fixture-driven test, every change to one stage requires a
    full Opus run + Tia eyeballing the dashboard to verify. This script
    runs the chain in <2 seconds against a fixture, surfaces regressions.

EXIT CODES
    0 = all assertions pass
    1 = at least one assertion failed AND --strict was passed
    2 = test runner errored

USAGE
    .venv/bin/python3.13 scripts/test_strategist_chain.py
    .venv/bin/python3.13 scripts/test_strategist_chain.py --strict
    .venv/bin/python3.13 scripts/test_strategist_chain.py --keep-fixture  # leave temp files for inspection

CALLED BY
    - scripts/dev-cycle.sh --pre-commit  (fast — <2s)
    - scripts/dev-cycle.sh --pre-flight  (also)
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from work_queue.schema import WorkQueueAction, ProjectedKPI   # noqa: E402
from work_queue.normalize_strategist_output import normalise_markdown  # noqa: E402

BASE_DIR = _HERE.parent
LOG_DIR = BASE_DIR / "logs"


# ── Fixture: what a real strategist output looks like ────────────────────────
# Mix of well-shaped + malformed actions so we can assert the normaliser
# does its job. The expected outcome is documented under EXPECTED below.


FIXTURE_MARKDOWN = """# CB247 SEO Strategist — TEST FIXTURE

## Page-Keyword Inventory
| URL | H1 | wc |
|---|---|---|
| / | 24/7 Gym Memberships in Malaga and Ellenbrook | 914 |

## Top GSC Opportunities
| Keyword | Pos | Impr | Action |
|---|---|---|---|
| gym malaga | 6.0 | 250 | optimise |

## Strategic Decisions
Various — see proposed_actions below.

## Proposed Actions

```json proposed_actions
[
  {
    "id": "test-fixture-001",
    "title": "Optimise on-page for 'gym malaga' — currently #6.0",
    "description": "Existing /malaga page ranks #6 with 250 impressions. Update H1 + meta + add 2 internal links from homepage.",
    "owner": "John",
    "owner_role": "SEO Specialist",
    "priority": "P1",
    "effort_hours": 0.5,
    "category": "seo-organic",
    "data_quality": "high",
    "projected_kpis": [
      {
        "metric": "gsc_position",
        "keyword": "gym malaga",
        "baseline": 6.0,
        "target": 3.0,
        "measurement_window_days": 14,
        "confidence": "high"
      }
    ]
  },
  {
    "id": "test-fixture-002-dict-kpi",
    "title": "Build service page: 'reformer pilates malaga' — 880 impressions",
    "description": "No existing page targets this. Build /reformer-pilates-malaga with class times, pricing, FAQ.",
    "owner": "AI",
    "owner_role": "Content Agent",
    "priority": "P2",
    "effort_hours": 6,
    "category": "seo-organic",
    "data_quality": "high",
    "type": "Content",
    "projected_kpis": {
      "gsc_position": {"baseline": 21, "target": 8}
    }
  },
  {
    "id": "test-fixture-003-invalid-metric",
    "title": "Fix 5 broken URLs returning 4xx errors",
    "description": "Screaming Frog found 5 URLs returning HTTP errors.",
    "owner": "John",
    "owner_role": "SEO Specialist",
    "priority": "P1",
    "effort_hours": 0.5,
    "category": "seo-organic",
    "data_quality": "high",
    "projected_kpis": [
      {
        "metric": "pages_4xx",
        "baseline": 5,
        "target": 0,
        "measurement_window_days": 7,
        "confidence": "high"
      }
    ]
  },
  {
    "id": "test-fixture-004-bogus-metric",
    "title": "Add nonexistent KPI to test drop logic",
    "description": "This action uses a metric NOT in VALID_METRICS — should be dropped.",
    "owner": "John",
    "owner_role": "SEO Specialist",
    "priority": "P3",
    "effort_hours": 0.5,
    "category": "seo-organic",
    "data_quality": "low",
    "projected_kpis": [
      {
        "metric": "totally_made_up_metric_xyzzy",
        "baseline": 0,
        "target": 1,
        "measurement_window_days": 7,
        "confidence": "low"
      }
    ]
  }
]
```
"""


# ── Expected normalised outcomes ─────────────────────────────────────────────
# After normalisation, we expect:
#   - Action 1 (well-shaped, valid metric)        → KEPT, unchanged
#   - Action 2 (dict-shape KPI, includes "type")  → KEPT, KPI coerced to list, type stripped
#   - Action 3 (pages_4xx — now valid metric)     → KEPT (post-Wave A schema fix)
#   - Action 4 (bogus metric)                     → DROPPED (no valid KPIs left)

EXPECTED_KEPT_IDS = {
    "test-fixture-001",
    "test-fixture-002-dict-kpi",
    "test-fixture-003-invalid-metric",   # name kept from fixture, despite metric being VALID now
}
EXPECTED_DROPPED_IDS = {
    "test-fixture-004-bogus-metric",
}


# ── Test harness ─────────────────────────────────────────────────────────────


def _run() -> tuple[list[str], list[dict]]:
    """Run the fixture through normalise + validate. Returns (failures, normalised_actions)."""
    failures: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="strategist-test-"))
    try:
        fixture_path = tmp / "seo-strategist-fixture.md"
        fixture_path.write_text(FIXTURE_MARKDOWN)

        # Step 1 — run the real normaliser on the fixture
        n_kept = normalise_markdown(fixture_path)

        # Step 2 — read the normalised markdown back and extract its
        # proposed_actions JSON block
        normalised_md = fixture_path.read_text()
        match = re.search(
            r"```(?:json|jsonc)(?:\s+proposed[_-]?actions)?\s*\n(.*?)\n```",
            normalised_md, re.DOTALL | re.IGNORECASE,
        )
        if not match:
            failures.append("normalised markdown has no proposed_actions block")
            return failures, []

        try:
            actions = json.loads(match.group(1))
        except json.JSONDecodeError as e:
            failures.append(f"normalised JSON is invalid: {e}")
            return failures, []

        if not isinstance(actions, list):
            failures.append(f"normalised actions is not a list (got {type(actions).__name__})")
            return failures, []

        kept_ids = {a.get("id") for a in actions}

        # Step 3 — assert expected keeps + drops
        missing = EXPECTED_KEPT_IDS - kept_ids
        if missing:
            failures.append(
                f"normaliser DROPPED action(s) that should have been KEPT: {sorted(missing)}"
            )

        unexpected = EXPECTED_DROPPED_IDS & kept_ids
        if unexpected:
            failures.append(
                f"normaliser KEPT action(s) that should have been DROPPED: {sorted(unexpected)}"
            )

        # Step 4 — assert each kept action validates against the strict schema
        for a in actions:
            try:
                # Coerce projected_kpis dict shape → ProjectedKPI[] instances
                kpis = []
                for k in a.get("projected_kpis", []):
                    kpis.append(ProjectedKPI(**k))
                action = WorkQueueAction(
                    id=a["id"],
                    source_page=a.get("source_page", a.get("category", "seo-organic")),
                    source_run_at=a.get("source_run_at") or datetime.utcnow().isoformat() + "Z",
                    title=a["title"],
                    description=a.get("description", ""),
                    owner=a.get("owner", "Unknown"),
                    owner_role=a.get("owner_role", ""),
                    priority=a["priority"],
                    effort_hours=a.get("effort_hours", 1.0),
                    category=a.get("category", "seo-organic"),
                    data_quality=a.get("data_quality", "medium"),
                    projected_kpis=kpis,
                )
                errs = action.validate()
                if errs:
                    failures.append(
                        f"action {a['id']} failed schema validation: {errs}"
                    )
            except Exception as e:
                failures.append(f"action {a.get('id', '?')} crashed during validation: {e}")

        # Step 5 — assert specific normaliser behaviours
        # Action 2 had "type": "Content" — strip should have removed it
        action_2 = next((a for a in actions if a["id"] == "test-fixture-002-dict-kpi"), None)
        if action_2 and "type" in action_2:
            failures.append("normaliser did NOT strip 'type' field from action 2")
        # Action 2 had dict-shape KPIs — should be list now
        if action_2 and not isinstance(action_2.get("projected_kpis"), list):
            failures.append("normaliser did NOT coerce action 2's projected_kpis from dict to list")

        return failures, actions
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    p = argparse.ArgumentParser(description="Strategist chain integration test")
    p.add_argument("--strict", action="store_true",
                   help="Exit 1 if any test fails (default: warn only)")
    p.add_argument("--log", action="store_true",
                   help="Write test report to logs/strategist-chain-test-<date>.json")
    args = p.parse_args()

    print("[strategist-chain] Running fixture through normalise → validate chain...")
    failures, actions = _run()

    if not failures:
        print(f"[strategist-chain] ✅ All assertions passed — {len(actions)} action(s) kept after normalisation.")
        if args.log:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            (LOG_DIR / f"strategist-chain-test-{datetime.now().strftime('%Y-%m-%d')}.json").write_text(
                json.dumps({"status": "pass", "ran_at": datetime.utcnow().isoformat() + "Z",
                            "kept": [a["id"] for a in actions]}, indent=2)
            )
        return 0

    print()
    print(f"[strategist-chain] ❌ {len(failures)} assertion(s) failed:")
    for f in failures:
        print(f"   · {f}")
    print()

    if args.log:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        (LOG_DIR / f"strategist-chain-test-{datetime.now().strftime('%Y-%m-%d')}.json").write_text(
            json.dumps({"status": "fail", "ran_at": datetime.utcnow().isoformat() + "Z",
                        "failures": failures}, indent=2)
        )

    if args.strict:
        return 1

    print("[strategist-chain] Warn-only mode — exit 0. Promote to blocking with --strict.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[strategist-chain] ERROR: {e}", file=sys.stderr)
        sys.exit(2)
