"""
run_screaming_frog.py — Run Screaming Frog SEO Spider via CLI + parse output.
Saves parsed results to state/screaming-frog-data.json.

Requires:
- Screaming Frog installed at /Applications/Screaming Frog SEO Spider.app
- Or set SCREAMING_FROG_PATH in .env
"""

import json
import os
import subprocess
import sys
import csv
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
OUTPUT_DIR = BASE_DIR / "outputs" / "seo" / "audits" / "screaming-frog"
SITE = "https://chasingbetter247.com.au"

load_dotenv(BASE_DIR / ".env")


def find_sf():
    """Find Screaming Frog binary."""
    sf_path = os.getenv(
        "SCREAMING_FROG_PATH",
        "/Applications/Screaming Frog SEO Spider.app/Contents/MacOS/ScreamingFrogSEOSpiderLauncher"
    )
    if Path(sf_path).exists():
        return sf_path
    # Fallback locations
    candidates = [
        Path("/Applications/Screaming Frog SEO Spider.app/Contents/MacOS/ScreamingFrogSEOSpiderLauncher"),
        Path("/Applications/Screaming Frog SEO Spider.app/Contents/MacOS/Screaming Frog SEO Spider"),
        str(Path.home() / "Applications/Screaming Frog SEO Spider.app/Contents/MacOS/ScreamingFrogSEOSpiderLauncher"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def run_spider():
    """Run Screaming Frog crawl."""
    sf_bin = find_sf()
    if not sf_bin:
        print("Screaming Frog not found — skipping.")
        print("Install from: https://www.screamingfrog.co.uk/seo-spider/")
        return None

    today = datetime.now().strftime("%Y-%m-%d")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_issues = OUTPUT_DIR / f"live-crawl-{today}-issues.csv"
    out_pages = OUTPUT_DIR / f"live-crawl-{today}-pages.csv"

    cmd = [
        sf_bin,
        "--output-folder", str(OUTPUT_DIR),
        "--export-format", "csv",
        "--timestamped-output",
        "--crawl", SITE,
        "--headless",
        "--no-outlinks",
        "--no-subdomains",
        "--spider",
        "--min-save", "200",
    ]
    print(f"Running Screaming Frog on {SITE}...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode not in (0, -15):
            print(f"stderr: {result.stderr[:300]}")
        print(f"Crawl complete.")
        return str(out_issues), str(out_pages)
    except subprocess.TimeoutExpired:
        print("Timed out after 5 minutes.")
        return None, None
    except Exception as e:
        print(f"Error: {e}")
        return None, None


def parse_issues(csv_path):
    """Parse issues CSV."""
    if not csv_path or not Path(csv_path).exists():
        return []
    issues = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            count = int(row.get("URLs", 0))
            if count == 0:
                continue
            issues.append({
                "name": row.get("Issue Name", ""),
                "type": row.get("Issue Type", ""),
                "priority": row.get("Issue Priority", ""),
                "count": count,
                "description": row.get("Description", "")[:200],
            })
    return issues


def parse_pages(csv_path):
    """Parse pages CSV."""
    if not csv_path or not Path(csv_path).exists():
        return []
    pages = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("Status Code", "") == "200":
                pages.append({
                    "url": row.get("Address", ""),
                    "title": row.get("Title", "")[:100],
                    "h1": row.get("H1", "")[:100],
                    "word_count": row.get("Word Count", ""),
                    "status": row.get("Status Code", ""),
                    "size_kb": row.get("Content Size", ""),
                })
    return pages[:50]


def main():
    print("Running Screaming Frog SEO Spider...")
    result = {
        "date_crawled": datetime.now().isoformat(),
        "site": SITE,
    }

    issues_path, pages_path = run_spider()
    if issues_path:
        result["issues"] = parse_issues(issues_path)
        result["top_pages"] = parse_pages(pages_path)
        result["raw_issues_csv"] = issues_path
        result["raw_pages_csv"] = pages_path
    else:
        # Fall back to existing data
        existing = sorted(OUTPUT_DIR.glob("cb247-screaming-frog-issues.csv"))
        if existing:
            result["fallback"] = f"Using existing: {existing[-1]}"
            result["issues"] = parse_issues(str(existing[-1]))

    out_path = STATE_DIR / "screaming-frog-data.json"
    out_path.write_text(json.dumps(result, indent=2))
    print(f"Saved to {out_path}")
    return result


if __name__ == "__main__":
    main()