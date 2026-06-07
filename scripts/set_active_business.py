"""
set_active_business.py — Switch the active business for skills (Layer 2).

Skills follow the Brand Contract (skills/SKILLS_BRAND_CONTRACT.md):
  When a skill runs, it reads context/_active_business.txt to know which
  brand-specific context files to load.

Usage:
    python scripts/set_active_business.py cb247    # switch to CB247 mode
    python scripts/set_active_business.py mwcc     # switch to MWCC mode
    python scripts/set_active_business.py          # print current

Effect:
    Writes the brand code to context/_active_business.txt.
    All skills run after this read the brand-specific context files.

Important:
    This is a SESSION-level switch. Each Claude session targeting a different
    business should run this once before invoking skills. For automation
    (cron pipelines), the weekly-report-{biz}.sh scripts should set this
    themselves at the start of the run.
"""

from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR    = Path(__file__).resolve().parent.parent
CONTEXT_DIR = BASE_DIR / "context"
ACTIVE_FILE = CONTEXT_DIR / "_active_business.txt"

VALID = {"cb247", "mwcc", "kb", "sp"}

# Resolution table — what each brand sees for the canonical context names
RESOLUTION = {
    "cb247": {
        "brand-voice":         "context/brand-voice.md",
        "marketing-strategy":  "context/marketing-strategy.md",
        "seo-targets":         "context/seo-targets-cb247.md",
        "seo-priorities":      "context/seo-priorities-cb247.md",
        "design-standards":    "context/design-standards.md",
        "research-competitors":"context/research-competitors.md",
        "team-roster":         "context/team-roster.md",
        "session-start":       "context/session-start.md",
        "seasonal-calendar":   "context/seasonal-calendar.md",
    },
    "mwcc": {
        "brand-voice":         "context/mwcc-brand-voice.md",
        "marketing-strategy":  "context/mwcc-marketing-strategy.md",
        "seo-targets":         "context/mwcc-seo-targets.md",
        "seo-priorities":      "context/mwcc-seo-priorities.md",
        "design-standards":    "context/mwcc-design-standards.md (todo)",
        "research-competitors":"context/mwcc-competitors.md",
        "team-roster":         "context/mwcc-team-roster.md",
        "session-start":       "context/mwcc-session-start.md",
        "seasonal-calendar":   "context/mwcc-seasonal-calendar.md",
    },
    "kb": {
        "brand-voice":         "context/kb-brand-voice.md (todo — placeholder)",
        "marketing-strategy":  "context/kb-marketing-strategy.md (todo — placeholder)",
    },
    "sp": {
        "brand-voice":         "context/sp-brand-voice.md (todo — placeholder)",
        "marketing-strategy":  "context/sp-marketing-strategy.md (todo — placeholder)",
    },
}


def current() -> str:
    if not ACTIVE_FILE.exists():
        return "cb247 (default — file not present)"
    return ACTIVE_FILE.read_text().strip() or "cb247 (file empty)"


def set_active(brand: str) -> int:
    if brand not in VALID:
        print(f"[set-active-biz] ERROR: '{brand}' not in {sorted(VALID)}")
        return 2
    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    ACTIVE_FILE.write_text(brand + "\n")
    print(f"[set-active-biz] ✅ Active business: {brand}")
    print(f"[set-active-biz] Persisted to: {ACTIVE_FILE.relative_to(BASE_DIR)}")
    print()
    print("Skills will now resolve generic context names to these files:")
    for canon, path in RESOLUTION.get(brand, {}).items():
        print(f"  {canon:<22}→ {path}")
    print()
    print(f"To switch back: python scripts/set_active_business.py cb247")
    return 0


def main() -> int:
    if len(sys.argv) == 1:
        active = current()
        print(f"[set-active-biz] Current: {active}")
        print(f"[set-active-biz] Valid options: {', '.join(sorted(VALID))}")
        print(f"[set-active-biz] Usage: python scripts/set_active_business.py <brand>")
        return 0
    return set_active(sys.argv[1].strip().lower())


if __name__ == "__main__":
    sys.exit(main())
