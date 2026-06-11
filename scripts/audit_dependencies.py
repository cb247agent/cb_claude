"""
audit_dependencies.py — Wave A.4 (dev cycle) — scan scripts/requirements.txt
for known CVEs via pip-audit. Wraps pip-audit so the dev-cycle can call it
with consistent flags, log JSON output, and emit a digest.

WHY THIS EXISTS
    The marketing OS shells out to Python packages that touch live data
    sources (requests for Supabase, google-* for GA4/GSC, anthropic SDK,
    etc.). A CVE in any of them could expose credentials or corrupt data.
    pip-audit catches the ones with public CVEs; this wrapper makes it
    easy to add to weekly + commit cycles.

EXIT CODES
    0 = no vulnerable dependencies (or warnings only — default)
    1 = vulnerable dependencies AND --strict was passed
    2 = pip-audit itself errored (e.g. not installed)

USAGE
    .venv/bin/python3.13 scripts/audit_dependencies.py            # warn
    .venv/bin/python3.13 scripts/audit_dependencies.py --strict   # block
    .venv/bin/python3.13 scripts/audit_dependencies.py --install  # install pip-audit if missing

CALLED BY
    - scripts/dev-cycle.sh --pre-flight  (once a week — too slow for pre-commit)
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_HERE = Path(__file__).resolve().parent
BASE_DIR = _HERE.parent
REQ_FILE = BASE_DIR / "scripts" / "requirements.txt"
LOG_DIR = BASE_DIR / "logs"
VENV_PIP = BASE_DIR / ".venv" / "bin" / "pip"
VENV_PYTHON = BASE_DIR / ".venv" / "bin" / "python3.13"


def _have_pip_audit() -> bool:
    """Check if pip-audit is importable in the venv."""
    try:
        result = subprocess.run(
            [str(VENV_PYTHON), "-c", "import pip_audit"],
            capture_output=True, timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _install_pip_audit() -> bool:
    print("[audit-deps] Installing pip-audit into venv...")
    try:
        result = subprocess.run(
            [str(VENV_PIP), "install", "--quiet", "pip-audit"],
            capture_output=True, timeout=120,
        )
        if result.returncode != 0:
            print(f"[audit-deps] pip install failed: {result.stderr.decode()[:500]}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print("[audit-deps] pip install timed out after 120s")
        return False
    except FileNotFoundError:
        print(f"[audit-deps] pip not found at {VENV_PIP}")
        return False


def _run_pip_audit() -> tuple[int, dict | None, str]:
    """Run pip-audit against requirements.txt, returning (exit_code, parsed_json, stderr)."""
    cmd = [
        str(VENV_PYTHON), "-m", "pip_audit",
        "--requirement", str(REQ_FILE),
        "--format", "json",
        "--progress-spinner", "off",
        # Note: removed --disable-pip because requirements.txt isn't
        # hashed; pip-audit needs to resolve transitive deps via pip.
        # Slightly slower (5-15s) but accurate.
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=180)
    except subprocess.TimeoutExpired:
        return 124, None, "pip-audit timed out after 180s"

    try:
        parsed = json.loads(result.stdout) if result.stdout.strip() else None
    except json.JSONDecodeError:
        parsed = None

    return result.returncode, parsed, result.stderr.decode()[:2000]


def _digest_findings(parsed: dict) -> list[dict]:
    """Turn pip-audit's JSON output into a flat list of vulnerable-dep dicts."""
    out: list[dict] = []
    # pip-audit format: {"dependencies": [{"name": "X", "version": "Y", "vulns": [...]}, ...]}
    for dep in (parsed or {}).get("dependencies", []):
        vulns = dep.get("vulns") or []
        if not vulns:
            continue
        for v in vulns:
            out.append({
                "package":     dep.get("name", "?"),
                "version":     dep.get("version", "?"),
                "vuln_id":     v.get("id", "?"),
                "fix_versions": v.get("fix_versions") or [],
                "description":  (v.get("description") or "")[:300],
            })
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Dependency vulnerability scanner")
    p.add_argument("--strict", action="store_true",
                   help="Exit 1 if vulnerabilities found (default: warn only)")
    p.add_argument("--install", action="store_true",
                   help="Install pip-audit into the venv if missing")
    p.add_argument("--log", action="store_true",
                   help="Write findings to logs/dep-audit-<date>.json")
    args = p.parse_args()

    if not REQ_FILE.exists():
        print(f"[audit-deps] {REQ_FILE.relative_to(BASE_DIR)} missing — nothing to scan.")
        return 0

    if not _have_pip_audit():
        if args.install:
            if not _install_pip_audit():
                print("[audit-deps] Failed to install pip-audit — skipping audit (exit 2).")
                return 2
        else:
            print("[audit-deps] pip-audit not installed in venv. Re-run with --install to add it.")
            print("[audit-deps] (No findings reported. Returning warn-only 0.)")
            return 0

    print(f"[audit-deps] Auditing {REQ_FILE.relative_to(BASE_DIR)}...")
    code, parsed, stderr = _run_pip_audit()

    findings = _digest_findings(parsed) if parsed else []

    if args.log:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        (LOG_DIR / f"dep-audit-{datetime.now().strftime('%Y-%m-%d')}.json").write_text(
            json.dumps({
                "ran_at":   datetime.utcnow().isoformat() + "Z",
                "exit":     code,
                "findings": findings,
                "stderr":   stderr if code != 0 and not findings else "",
            }, indent=2)
        )

    if code == 0 and not findings:
        print("[audit-deps] ✅ No known vulnerabilities.")
        return 0

    if findings:
        print(f"[audit-deps] ⚠️  {len(findings)} vulnerability finding(s):")
        print()
        for f in findings:
            fix = f["fix_versions"][0] if f["fix_versions"] else "(no fix available)"
            print(f"  ⚠️  {f['package']} {f['version']}  [{f['vuln_id']}]  → fix: {fix}")
            if f["description"]:
                print(f"      {f['description']}")
            print()

        if args.strict:
            print("[audit-deps] ❌ --strict + findings — exit 1.")
            return 1
        print("[audit-deps] Warn-only mode — exit 0.")
        return 0

    # pip-audit returned non-zero with no parsed findings — likely a config issue.
    print(f"[audit-deps] pip-audit exited {code} but parsed no findings. stderr (truncated):")
    print(stderr or "(empty)")
    return 2 if args.strict else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[audit-deps] ERROR: {e}", file=sys.stderr)
        sys.exit(2)
