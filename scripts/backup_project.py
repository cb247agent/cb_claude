"""
backup_project.py — Comprehensive project snapshot before major changes.

Creates a timestamped backup directory containing:
  - All state/*.json files (live data snapshots — gitignored, this is the only backup)
  - docs/index.html (the dashboard file most often touched)
  - scripts/work_queue/ entire directory (schema + emitters + sync)
  - All scripts/inject-*.py + parse_*.py + bake_*.py
  - context/ entire directory (system configs)
  - Supabase work_queue_actions table snapshot (if accessible)
  - Git tag + commit hash recorded
  - README.md with rollback instructions

Output: backups/{YYYY-MM-DD-HHMM}-{tag}/

Run before risky operations (kanban migration, schema changes, render
function rewrites, etc.).

Usage:
    python scripts/backup_project.py              # auto-tag = pre-migration
    python scripts/backup_project.py --tag custom # custom tag suffix
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BACKUPS_DIR = BASE_DIR / "backups"


def _load_dotenv():
    env = BASE_DIR / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def _copy_tree(src: Path, dst: Path, exclude_patterns=()) -> int:
    """Copy a directory tree, return count of files copied."""
    count = 0
    if not src.exists():
        return 0
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if any(p in item.name for p in exclude_patterns):
            continue
        if item.is_dir():
            count += _copy_tree(item, dst / item.name, exclude_patterns)
        else:
            shutil.copy2(item, dst / item.name)
            count += 1
    return count


def _copy_glob(src_dir: Path, pattern: str, dst_dir: Path) -> int:
    """Copy all files matching pattern from src_dir to dst_dir."""
    count = 0
    if not src_dir.exists():
        return 0
    dst_dir.mkdir(parents=True, exist_ok=True)
    for f in src_dir.glob(pattern):
        if f.is_file():
            shutil.copy2(f, dst_dir / f.name)
            count += 1
    return count


def _git_info():
    """Capture current commit hash + branch + uncommitted-files count."""
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=BASE_DIR).decode().strip()
        branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=BASE_DIR).decode().strip()
        status = subprocess.check_output(["git", "status", "--short"], cwd=BASE_DIR).decode().strip()
        return {
            "commit": commit,
            "short_commit": commit[:7],
            "branch": branch,
            "uncommitted_files": len(status.splitlines()) if status else 0,
            "status_summary": status[:500] if status else "(clean)",
        }
    except Exception as e:
        return {"error": str(e)}


def _supabase_snapshot(out_dir: Path) -> dict:
    """Dump the work_queue_actions table from Supabase (if accessible).

    Uses SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY (read-only is fine).
    Falls back gracefully if unreachable.
    """
    # Match sync_to_supabase.py — publishable key is safe to embed (designed
    # for client-side use; already in docs/index.html + sync_to_supabase.py).
    url = os.getenv("SUPABASE_URL", "https://ckjwzwktuiavyfuolbgx.supabase.co").rstrip("/")
    key = os.getenv(
        "SUPABASE_PUBLISHABLE_KEY",
        "sb_publishable_3giOfPJ92JW7DN8w9jPvoQ_cFo4rd0s",
    )
    result = {"attempted": bool(url and key), "tables": {}}
    if not url or not key:
        result["error"] = "SUPABASE_URL or KEY missing in .env — skipping Supabase snapshot"
        return result
    try:
        import urllib.request
    except ImportError:
        result["error"] = "urllib not available"
        return result

    out_dir.mkdir(parents=True, exist_ok=True)
    tables = ["work_queue_actions", "mwcc_work_queue_actions"]
    for table in tables:
        try:
            req = urllib.request.Request(
                f"{url}/rest/v1/{table}?select=*",
                headers={
                    "apikey": key,
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
            out_file = out_dir / f"supabase-{table}.json"
            out_file.write_text(json.dumps(data, indent=2, default=str))
            result["tables"][table] = {"rows": len(data), "file": str(out_file.name)}
        except Exception as e:
            result["tables"][table] = {"error": str(e)[:200]}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="pre-action-workflow", help="Tag suffix for backup dir")
    parser.add_argument("--git-tag", action="store_true", help="Also create a git tag")
    args = parser.parse_args()

    _load_dotenv()

    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    backup_name = f"{timestamp}-{args.tag}"
    out_dir = BACKUPS_DIR / backup_name
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[backup] Creating: {out_dir.relative_to(BASE_DIR)}")
    print()

    summary = {
        "created_at": datetime.now().isoformat(),
        "tag": args.tag,
        "base_dir": str(BASE_DIR),
        "git": _git_info(),
    }

    # ── 1. State files (live data snapshots — NOT in git, critical) ────────
    print("[backup] 1. state/ files (live data)")
    n_state = _copy_tree(BASE_DIR / "state", out_dir / "state", exclude_patterns=["__pycache__"])
    summary["state_files_copied"] = n_state
    print(f"        → {n_state} files")

    # ── 2. Dashboard HTML (the most-touched file) ─────────────────────────
    print("[backup] 2. docs/index.html")
    src = BASE_DIR / "docs" / "index.html"
    if src.exists():
        dst = out_dir / "docs" / "index.html"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        summary["index_html_bytes"] = src.stat().st_size
        print(f"        → {src.stat().st_size:,} bytes")
    else:
        summary["index_html_bytes"] = 0
        print(f"        → NOT FOUND")

    # ── 3. Work Queue scripts (schema + emitters + sync) ───────────────────
    print("[backup] 3. scripts/work_queue/")
    n_wq = _copy_tree(BASE_DIR / "scripts" / "work_queue", out_dir / "scripts" / "work_queue",
                      exclude_patterns=["__pycache__"])
    summary["work_queue_scripts_copied"] = n_wq
    print(f"        → {n_wq} files")

    # ── 4. Inject + parse + bake scripts (dashboard pipeline) ──────────────
    print("[backup] 4. scripts/ (inject + parse + bake)")
    scripts_dir = out_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    n_inject = _copy_glob(BASE_DIR / "scripts", "inject-*.py", scripts_dir)
    n_parse  = _copy_glob(BASE_DIR / "scripts", "parse_*.py", scripts_dir)
    n_parse_dash = _copy_glob(BASE_DIR / "scripts", "parse-*.py", scripts_dir)
    n_bake   = _copy_glob(BASE_DIR / "scripts", "bake_*.py", scripts_dir)
    n_bake_dash = _copy_glob(BASE_DIR / "scripts", "bake-*.py", scripts_dir)
    n_send   = _copy_glob(BASE_DIR / "scripts", "send_*.py", scripts_dir)
    summary["pipeline_scripts_copied"] = {
        "inject": n_inject, "parse": n_parse + n_parse_dash,
        "bake": n_bake + n_bake_dash, "send": n_send,
    }
    print(f"        → inject:{n_inject} · parse:{n_parse+n_parse_dash} · bake:{n_bake+n_bake_dash} · send:{n_send}")

    # ── 5. Context (system configs — brand, design, business rules) ────────
    print("[backup] 5. context/")
    n_ctx = _copy_tree(BASE_DIR / "context", out_dir / "context", exclude_patterns=["__pycache__"])
    summary["context_files_copied"] = n_ctx
    print(f"        → {n_ctx} files")

    # ── 6. Engineering docs ────────────────────────────────────────────────
    print("[backup] 6. ENGINEERING.md + HANDOFF.md + CLAUDE.md")
    docs_copied = 0
    for doc in ("ENGINEERING.md", "HANDOFF.md", "CLAUDE.md", "README.md"):
        src = BASE_DIR / doc
        if src.exists():
            shutil.copy2(src, out_dir / doc)
            docs_copied += 1
    summary["root_docs_copied"] = docs_copied
    print(f"        → {docs_copied} files")

    # ── 7. Supabase tables snapshot ────────────────────────────────────────
    print("[backup] 7. Supabase snapshot")
    sb = _supabase_snapshot(out_dir / "supabase")
    summary["supabase"] = sb
    if sb.get("attempted"):
        for tbl, info in sb["tables"].items():
            if "rows" in info:
                print(f"        → {tbl}: {info['rows']} rows")
            else:
                print(f"        → {tbl}: ERROR {info.get('error','?')[:80]}")
    else:
        print(f"        → SKIPPED ({sb.get('error','?')})")

    # ── 8. Git tag (optional) ──────────────────────────────────────────────
    if args.git_tag:
        tag_name = f"backup-{timestamp}-{args.tag}"
        try:
            subprocess.check_call(["git", "tag", tag_name], cwd=BASE_DIR)
            summary["git_tag"] = tag_name
            print(f"[backup] 8. git tag created: {tag_name}")
        except Exception as e:
            summary["git_tag_error"] = str(e)
            print(f"[backup] 8. git tag FAILED: {e}")
    else:
        print(f"[backup] 8. git tag SKIPPED (use --git-tag to enable)")

    # ── 9. README.md with rollback instructions ────────────────────────────
    readme = out_dir / "README.md"
    readme.write_text(_build_readme(summary, backup_name, args.tag))
    print(f"[backup] 9. README.md → rollback instructions written")

    # ── Final summary ──────────────────────────────────────────────────────
    summary_file = out_dir / "_backup-summary.json"
    summary_file.write_text(json.dumps(summary, indent=2, default=str))

    # Total size
    total_bytes = sum(f.stat().st_size for f in out_dir.rglob("*") if f.is_file())
    print()
    print(f"[backup] ✅ Complete")
    print(f"         Location: {out_dir.relative_to(BASE_DIR)}")
    print(f"         Size: {total_bytes / 1024 / 1024:.2f} MB")
    print(f"         Git commit: {summary['git'].get('short_commit', '?')} on {summary['git'].get('branch', '?')}")
    if summary.get("git", {}).get("uncommitted_files", 0) > 0:
        print(f"         ⚠️  {summary['git']['uncommitted_files']} uncommitted file(s) — backup captured working tree, not just HEAD")

    return 0


def _build_readme(summary: dict, backup_name: str, tag: str) -> str:
    git = summary.get("git", {})
    sb = summary.get("supabase", {})
    return f"""# Backup · {backup_name}

Created: {summary['created_at']}
Tag: `{tag}`

## What's in here

| Path | Contents |
|---|---|
| `state/` | All live JSON snapshots ({summary.get('state_files_copied', 0)} files) — gitignored, this IS the backup |
| `docs/index.html` | Dashboard ({summary.get('index_html_bytes', 0):,} bytes) |
| `scripts/work_queue/` | Schema + emitters + sync ({summary.get('work_queue_scripts_copied', 0)} files) |
| `scripts/inject-*.py` | Dashboard inject scripts |
| `scripts/parse_*.py`, `parse-*.py` | Data parsers |
| `scripts/bake_*.py`, `bake-*.py` | HTML report bakers |
| `scripts/send_*.py` | Email senders |
| `context/` | System configs ({summary.get('context_files_copied', 0)} files) |
| `supabase/` | Supabase table dumps (if accessible) |
| `ENGINEERING.md`, `HANDOFF.md`, `CLAUDE.md` | Architecture docs |
| `_backup-summary.json` | Machine-readable manifest |

## Git state at backup

- **Commit:** `{git.get('commit', '?')}`
- **Short:** `{git.get('short_commit', '?')}`
- **Branch:** `{git.get('branch', '?')}`
- **Uncommitted files:** {git.get('uncommitted_files', 0)}
- **Git tag:** `{summary.get('git_tag', '(not created)')}`

## Supabase snapshot

{_format_supabase_summary(sb)}

## Rollback instructions

### Full rollback (revert ALL changes after this backup)

```bash
cd CB_Marketing

# 1. Revert code to pre-backup commit
git reset --hard {git.get('commit', 'HEAD')}

# 2. Restore state/ files from backup
cp -r backups/{backup_name}/state/* state/

# 3. (Optional) Restore Supabase work_queue_actions table
#    Use the SQL editor in Supabase dashboard to:
#    DELETE FROM work_queue_actions;
#    -- Then INSERT rows from backups/{backup_name}/supabase/supabase-work_queue_actions.json

# 4. Re-run inject scripts to refresh dashboard from restored state
python scripts/inject-membership-data.py
python scripts/inject-social-block.py
python scripts/inject-google-ads.py
python scripts/inject-meta-ads.py
python scripts/inject-seo-extras.py
```

### Partial rollback (restore ONE file)

```bash
# Restore dashboard HTML only
cp backups/{backup_name}/docs/index.html docs/index.html

# Restore work queue state only
cp backups/{backup_name}/state/work-queue.json state/work-queue.json

# Restore schema only
cp backups/{backup_name}/scripts/work_queue/schema.py scripts/work_queue/schema.py
```

### Browser-side state (localStorage)

The dashboard caches some state in browser localStorage (kanban statuses,
approval pills). This backup does NOT capture browser state.

If a team member's browser shows the OLD stages after rollback:
1. Open browser DevTools → Application → Local Storage → `cb247agent.github.io`
2. Look for keys `cb247-planner-status`, `cb247-planner-approval`, `mwcc-planner-status`, `mwcc-planner-approval`
3. Either delete them (forces re-sync from Supabase) or restore from a personal export

## Safety notes

- This backup is **read-only by convention** — do not modify files in here
- `state/*.json` is gitignored in the main repo BUT included in this backup
- Supabase snapshot is point-in-time — actions taken AFTER the backup time won't appear
"""


def _format_supabase_summary(sb: dict) -> str:
    if not sb.get("attempted"):
        return f"⚠️  Not captured: {sb.get('error', 'unknown')}"
    lines = []
    for tbl, info in sb.get("tables", {}).items():
        if "rows" in info:
            lines.append(f"- `{tbl}`: **{info['rows']} rows** → `supabase/{info['file']}`")
        else:
            lines.append(f"- `{tbl}`: ⚠️ ERROR — {info.get('error', '?')[:120]}")
    return "\n".join(lines) if lines else "(no tables captured)"


if __name__ == "__main__":
    sys.exit(main())
