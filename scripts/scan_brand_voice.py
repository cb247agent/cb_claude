"""
scan_brand_voice.py — Wave A.1 (dev cycle) — brand voice + compliance scanner.

Walks agent markdown outputs, dashboard JS, and emitter Python files looking
for stale vocabulary, banned ACL phrases, TGA therapeutic claims, and the
CB_Brain "DON'Ts" list. Each finding is printed with file:line so the
operator can jump straight to the offending text.

WHY THIS EXISTS
    Bugs that escaped to the live dashboard this session that this scanner
    would have caught BEFORE commit:
      - Stale "Angela QC → Denver sign-off → Mark publishes" vocab in
        seo_emitter.py descriptions (shipped to live, Tia spotted it)
      - Same stale vocab in PLANNER_ITEMS templates in docs/index.html
      - Generic "best gyms perth" hand-coded action title
    Pattern source of truth is scripts/work_queue/compliance.py — this
    scanner reuses RULES_BY_BUSINESS so we don't duplicate the rule list.

EXIT CODES
    0 = scan clean OR warnings only (default behaviour — never blocks)
    1 = scan found findings AND --strict was passed (promote to blocking)
    2 = scanner itself errored

USAGE
    .venv/bin/python3.13 scripts/scan_brand_voice.py                      # warn
    .venv/bin/python3.13 scripts/scan_brand_voice.py --strict             # block
    .venv/bin/python3.13 scripts/scan_brand_voice.py --paths outputs/seo  # narrow scope
    .venv/bin/python3.13 scripts/scan_brand_voice.py --business mwcc      # MWCC rules

CALLED BY
    - scripts/dev-cycle.sh --pre-commit  (light, fast — just the new agent outputs)
    - scripts/dev-cycle.sh --pre-flight  (everything, before Monday's data pull)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))   # so we can import work_queue.compliance

from work_queue.compliance import RULES_BY_BUSINESS  # noqa: E402

BASE_DIR = _HERE.parent
LOG_DIR = BASE_DIR / "logs"

# Default scan paths — narrow + relevant. Add as new asset types appear.
DEFAULT_PATHS_CB247 = [
    "outputs/seo",
    "outputs/content",
    "outputs/blueprints",
    "outputs/research",
    "outputs/creatives",
    "docs/blog-drafts",
    "scripts/work_queue",    # catches stale vocab in emitter descriptions
    "context",               # catches stale vocab in brand voice files
    "agents",                # catches stale vocab in agent prompts
]
DEFAULT_PATHS_MWCC = [
    "outputs/mwcc",
    "context",
    "agents/mwcc",
]

# Files we never scan (binary, huge, generated)
SKIP_FILE_GLOBS = {
    ".final.md", "-final.md",  # auto-generated McKinsey-style reports
}
SKIP_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".zip", ".xlsx"}

# Files that DEFINE the banned patterns — would always self-match.
# Maintain by basename to avoid path coupling.
SELF_REFERENTIAL_FILES = {
    "compliance.py",          # defines RULES_BY_BUSINESS
    "scan_brand_voice.py",    # this script — describes the rules in its docstring
}


def _iter_scan_files(paths: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        if not p.exists():
            continue
        if p.is_file():
            files.append(p)
            continue
        # rglob — pick text-like files
        for f in p.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix.lower() in SKIP_EXTENSIONS:
                continue
            if any(g in f.name for g in SKIP_FILE_GLOBS):
                continue
            if f.name in SELF_REFERENTIAL_FILES:
                continue
            # Cap individual file size — protect against accidentally
            # scanning a multi-MB minified blob.
            try:
                if f.stat().st_size > 2_000_000:
                    continue
            except OSError:
                continue
            files.append(f)
    return files


def _scan_file(path: Path, patterns: list[tuple[str, str]]) -> list[dict]:
    """Return list of findings: {file, line, col, snippet, rule, reason}."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    findings: list[dict] = []
    for regex_str, reason in patterns:
        try:
            regex = re.compile(regex_str, re.IGNORECASE)
        except re.error:
            continue
        for match in regex.finditer(text):
            # Locate line + column from match position
            start = match.start()
            line_no = text.count("\n", 0, start) + 1
            last_newline = text.rfind("\n", 0, start)
            col = start - last_newline if last_newline != -1 else start + 1
            line_text = text.split("\n")[line_no - 1].strip()
            # Truncate long lines so terminal output stays readable
            if len(line_text) > 140:
                line_text = line_text[:137] + "..."
            findings.append({
                "file":    str(path.relative_to(BASE_DIR)),
                "line":    line_no,
                "col":     col,
                "snippet": line_text,
                "rule":    regex_str,
                "reason":  reason,
                "match":   match.group(0),
            })
    return findings


def main() -> int:
    p = argparse.ArgumentParser(description="Brand voice + compliance scanner")
    p.add_argument("--business", default="cb247", choices=["cb247", "mwcc"],
                   help="Which compliance rule set to apply")
    p.add_argument("--paths", nargs="*",
                   help="Specific paths to scan (default: per-business safe list)")
    p.add_argument("--strict", action="store_true",
                   help="Exit 1 if any findings (default: warn only, exit 0)")
    p.add_argument("--log", action="store_true",
                   help="Also write findings to logs/scan-brand-voice-<date>.json")
    args = p.parse_args()

    patterns = RULES_BY_BUSINESS.get(args.business) or []
    if not patterns:
        print(f"[scan-brand-voice] No banned patterns configured for business='{args.business}' — nothing to scan.")
        return 0

    if args.paths:
        scan_paths = [BASE_DIR / p for p in args.paths]
    else:
        defaults = DEFAULT_PATHS_CB247 if args.business == "cb247" else DEFAULT_PATHS_MWCC
        scan_paths = [BASE_DIR / p for p in defaults]

    files = _iter_scan_files(scan_paths)
    print(f"[scan-brand-voice] {args.business.upper()} · {len(patterns)} rules · scanning {len(files)} files in {len(scan_paths)} paths")

    all_findings: list[dict] = []
    for f in files:
        all_findings.extend(_scan_file(f, patterns))

    if not all_findings:
        print(f"[scan-brand-voice] ✅ Scan clean — 0 findings.")
        return 0

    # Group findings by file for readable output
    by_file: dict[str, list[dict]] = {}
    for f in all_findings:
        by_file.setdefault(f["file"], []).append(f)

    print()
    print(f"[scan-brand-voice] ⚠️  {len(all_findings)} finding(s) across {len(by_file)} file(s):")
    print()
    for file_path, hits in sorted(by_file.items()):
        print(f"  {file_path}  ({len(hits)} hit{'s' if len(hits) != 1 else ''})")
        for h in hits[:5]:   # cap per file so output stays scannable
            print(f"    L{h['line']}:{h['col']}  {h['match']!r}")
            print(f"      ↳ {h['reason']}")
            print(f"      ↳ context: {h['snippet']}")
        if len(hits) > 5:
            print(f"    ... and {len(hits) - 5} more in this file")
        print()

    if args.log:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOG_DIR / f"scan-brand-voice-{datetime.now().strftime('%Y-%m-%d')}.json"
        log_path.write_text(json.dumps({
            "business":   args.business,
            "ran_at":     datetime.utcnow().isoformat() + "Z",
            "files_scanned": len(files),
            "findings":   all_findings,
        }, indent=2))
        print(f"[scan-brand-voice] Findings written to {log_path.relative_to(BASE_DIR)}")

    if args.strict:
        print()
        print(f"[scan-brand-voice] ❌ --strict set, exiting 1 (blocking).")
        return 1

    print()
    print(f"[scan-brand-voice] Warn-only mode — exit 0. Promote to blocking with --strict.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[scan-brand-voice] ERROR: {e}", file=sys.stderr)
        sys.exit(2)
