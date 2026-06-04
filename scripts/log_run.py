"""
scripts/log_run.py — Structured run logger for the CB247 pipeline.

Reads _meta.is_fresh from all context/*.json files (written by build_context.py Fix 2)
and writes a structured JSON log after each pipeline execution.

Usage (called at end of weekly-report.sh):
    python scripts/log_run.py \\
        --business cb247 \\
        --status "success|partial|failed" \\
        --failed-agents "seo-agent,performance" \\
        --duration-seconds 1842

Output files:
    logs/run-YYYYMMDD-HHMMSS.json  — timestamped archive
    logs/last-run.json             — always the most recent run (overwritten)
"""

import json
import argparse
from pathlib import Path
from datetime import datetime, timezone


BASE_DIR = Path(__file__).resolve().parent.parent


def log_run(business_id: str, status: str, failed_agents: str, duration_seconds: int):
    # ── Read freshness from all context files built by Fix 2 ──
    context_freshness = {}
    for ctx_file in sorted((BASE_DIR / "context").glob("*-context.json")):
        try:
            raw = json.loads(ctx_file.read_text())
            meta = raw.get("_meta", {})
            context_freshness[ctx_file.stem] = {
                "is_fresh":  meta.get("is_fresh", "unknown"),
                "built_at":  meta.get("built_at"),
                "warnings":  meta.get("staleness_warnings", []),
            }
        except Exception:
            context_freshness[ctx_file.stem] = {
                "is_fresh": False,
                "error":    "unreadable",
            }

    failed_list = [a.strip() for a in failed_agents.split(",") if a.strip()] if failed_agents else []

    run_log = {
        "run_id":           datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"),
        "business_id":      business_id,
        "run_date":         datetime.now(timezone.utc).isoformat(),
        "status":           status,
        "duration_seconds": duration_seconds,
        "failed_agents":    failed_list,
        "context_freshness": context_freshness,
    }

    log_dir = BASE_DIR / "logs"
    log_dir.mkdir(exist_ok=True)

    # Timestamped archive copy
    archive_path = log_dir / f"run-{run_log['run_id']}.json"
    archive_path.write_text(json.dumps(run_log, indent=2))

    # Overwrite last-run for quick status checks
    (log_dir / "last-run.json").write_text(json.dumps(run_log, indent=2))

    # ── Console summary ──
    print(f"\n[log_run] {status.upper()} | {duration_seconds}s | "
          f"Failed agents: {failed_list or 'none'}")
    print("Context freshness:")
    for name, info in context_freshness.items():
        fresh = info.get("is_fresh")
        icon = "✅" if fresh is True else ("⚠️ " if fresh is False else "❓")
        built = info.get("built_at", "unknown")
        print(f"  {icon} {name}: {built}")
        for w in info.get("warnings", []):
            print(f"       ↳ {w}")

    print(f"\n[log_run] Saved → logs/run-{run_log['run_id']}.json + logs/last-run.json")
    return run_log


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Log a CB247 pipeline run.")
    parser.add_argument("--business",         default="cb247")
    parser.add_argument("--status",           required=True,
                        choices=["success", "partial", "failed"],
                        help="Overall run status")
    parser.add_argument("--failed-agents",    default="",
                        help="Comma-separated list of failed agent names")
    parser.add_argument("--duration-seconds", type=int, default=0,
                        help="Total pipeline duration in seconds")
    args = parser.parse_args()

    log_run(args.business, args.status, args.failed_agents, args.duration_seconds)
