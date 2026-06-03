"""
import_site_audit.py — Convert Ahrefs Site Audit CSV export to screaming-frog-data.json

Usage:
    python3 scripts/import_site_audit.py
    python3 scripts/import_site_audit.py --folder state/my_export_folder

Looks for the most recent Ahrefs export folder in state/ (folders matching
the pattern chasingbetter247_*_all-issues_*) and converts all issue CSVs
to state/screaming-frog-data.json for use by the SEO agent.

Skip *-links.csv files — those are supplementary backlink lists, not the
issue pages themselves.
"""

import csv
import glob
import io
import json
import os
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR  = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"


# ── Priority order for display ──
PRIORITY_ORDER = {"Error": 0, "Warning": 1, "Notice": 2}

# ── Human-readable names for common filename patterns ──
ISSUE_LABELS = {
    "404_page":                                          "404 pages",
    "4XX_page":                                          "4XX client errors",
    "indexable-Orphan_page_(has_no_incoming_internal_links)": "Orphan pages (no internal links)",
    "indexable-Page_has_links_to_broken_page":           "Pages linking to broken URLs",
    "indexable-Page_has_no_outgoing_links":              "Pages with no outgoing links",
    "HTTP_to_HTTPS_redirect":                            "HTTP→HTTPS redirects",
    "Indexable_page_became_non-indexable":               "Pages that became non-indexable",
    "Open_Graph_tags_missing":                           "Missing Open Graph tags",
    "Organic_traffic_dropped":                           "Pages with dropped organic traffic",
    "Pages_added_to_sitemaps":                           "Pages added to sitemap",
    "Pages_to_submit_to_IndexNow":                       "Pages to submit via IndexNow",
    "Redirect_chain":                                    "Redirect chains",
    "Structured_data_has_Google_rich_results_validation_error": "Rich results validation errors",
    "Structured_data_has_schema.org_validation_error":   "Schema.org validation errors",
    "X_(Twitter)_card_missing":                         "Missing Twitter/X card",
    "indexable-Multiple_H1_tags":                        "Multiple H1 tags",
    "indexable-Page_and_SERP_titles_do_not_match":       "Page title vs SERP title mismatch",
    "indexable-Page_has_only_one_dofollow_incoming_internal_link": "Pages with only 1 internal link",
    "indexable-Pages_have_high_AI_content_levels":       "High AI content levels (flagged)",
    "indexable-Word_count_changed":                      "Word count changed significantly",
    "3XX_redirect":                                      "3XX redirects",
    "Missing_alt_text":                                  "Images missing alt text",
    "Open_Graph_URL_not_matching_canonical":             "OG URL ≠ canonical",
    "Open_Graph_tags_incomplete":                        "Incomplete Open Graph tags",
    "X_(Twitter)_card_incomplete":                       "Incomplete Twitter/X card",
    "indexable-Meta_description_tag_missing_or_empty":   "Missing or empty meta description",
    "indexable-Meta_description_too_long":               "Meta description too long",
    "indexable-Title_too_short":                         "Title tag too short",
}


def find_export_folder(override=None):
    """Find most recent Ahrefs site audit export folder in state/."""
    if override:
        p = Path(override)
        if not p.is_absolute():
            p = BASE_DIR / p
        if p.exists():
            return p
        raise FileNotFoundError(f"Export folder not found: {p}")

    # Auto-detect: look for folders named chasingbetter247_*_all-issues_*
    pattern = str(STATE_DIR / "chasingbetter247_*_all-issues_*")
    folders = sorted(glob.glob(pattern), reverse=True)  # newest first
    if not folders:
        raise FileNotFoundError(
            f"No Ahrefs export folder found in {STATE_DIR}.\n"
            "Expected folder name pattern: chasingbetter247_*_all-issues_*\n"
            "Export from: ahrefs.com → Site Audit → Issues → Export all"
        )
    return Path(folders[0])


def read_csv_utf16(filepath):
    """Read a UTF-16 tab-separated CSV from Ahrefs export."""
    try:
        raw = Path(filepath).read_bytes()
        # Try UTF-16 first (Ahrefs default), fall back to UTF-8
        for enc in ("utf-16", "utf-8-sig", "utf-8"):
            try:
                text = raw.decode(enc)
                break
            except (UnicodeDecodeError, LookupError):
                continue
        else:
            return [], []

        reader = csv.DictReader(io.StringIO(text), delimiter="\t")
        rows = list(reader)
        headers = reader.fieldnames or []
        return headers, rows
    except Exception as e:
        print(f"  WARN: could not read {filepath.name}: {e}")
        return [], []


def parse_filename(filename):
    """
    Parse issue filename into priority + issue key.
    Examples:
      Error-404_page.csv           → priority=Error, key=404_page
      Warning-Missing_alt_text.csv → priority=Warning, key=Missing_alt_text
      Notice-indexable-Multiple_H1_tags.csv → priority=Notice, key=indexable-Multiple_H1_tags
    """
    stem = Path(filename).stem   # remove .csv
    parts = stem.split("-", 1)   # split on first dash only
    if len(parts) == 2 and parts[0] in PRIORITY_ORDER:
        return parts[0], parts[1]
    return "Notice", stem


def url_column(headers):
    """Find the URL column name (Ahrefs uses 'URL' with possible BOM/whitespace)."""
    for h in (headers or []):
        if h and h.strip().strip("﻿").strip('"').upper() == "URL":
            return h
    # Fallback: second column is usually URL
    if headers and len(headers) > 1:
        return headers[1]
    return None


def convert(folder_path):
    folder = Path(folder_path)
    crawl_date = "2026-06-01"  # from folder name; can be parsed if needed

    # Try to parse date from folder name
    folder_name = folder.name
    # Pattern: chasingbetter247_01-jun-2026_all-issues_...
    try:
        date_part = folder_name.split("_")[1]  # e.g. "01-jun-2026"
        crawl_date = datetime.strptime(date_part, "%d-%b-%Y").strftime("%Y-%m-%d")
    except Exception:
        pass

    print(f"\nAhrefs Site Audit Import")
    print(f"  Folder : {folder.name}")
    print(f"  Date   : {crawl_date}")
    print()

    issues = []
    csv_files = sorted(folder.glob("*.csv"))

    for csv_file in csv_files:
        # Skip -links.csv (supplementary backlink lists)
        if csv_file.name.endswith("-links.csv"):
            continue

        priority, key = parse_filename(csv_file.name)
        label = ISSUE_LABELS.get(key, key.replace("_", " ").replace("-", " — "))

        headers, rows = read_csv_utf16(csv_file)
        if not rows:
            continue

        count = len(rows)

        # Extract affected URLs (up to 10)
        url_col = url_column(headers)
        affected_urls = []
        for row in rows[:10]:
            url = ""
            if url_col and url_col in row:
                url = (row[url_col] or "").strip().strip('"')
            if url and url.startswith("http"):
                affected_urls.append(url)

        # Extract organic traffic info if available
        traffic_col = next((h for h in (headers or []) if "traffic" in (h or "").lower()), None)
        total_traffic_lost = 0
        if traffic_col:
            for row in rows:
                try:
                    total_traffic_lost += int(row.get(traffic_col, "0") or 0)
                except (ValueError, TypeError):
                    pass

        issue = {
            "name":          label,
            "priority":      priority.lower(),
            "count":         count,
            "description":   _describe(priority, key, count),
            "affected_urls": affected_urls[:5],
        }
        if total_traffic_lost:
            issue["organic_traffic_affected"] = total_traffic_lost

        issues.append(issue)
        traffic_note = f" | {total_traffic_lost} traffic" if total_traffic_lost else ""
        print(f"  [{priority:7s}] {count:3d} pages — {label}{traffic_note}")

    # Sort: Errors first, then Warnings, then Notices; largest count first within each
    issues.sort(key=lambda i: (PRIORITY_ORDER.get(i["priority"].capitalize(), 9), -i["count"]))

    # Summary counts
    error_count   = sum(1 for i in issues if i["priority"] == "error")
    warning_count = sum(1 for i in issues if i["priority"] == "warning")
    notice_count  = sum(1 for i in issues if i["priority"] == "notice")

    result = {
        "source":       "ahrefs_site_audit",
        "date_crawled": crawl_date,
        "export_folder": folder.name,
        "summary": {
            "total_issue_types": len(issues),
            "errors":   error_count,
            "warnings": warning_count,
            "notices":  notice_count,
        },
        "issues": issues,
    }

    out_path = STATE_DIR / "screaming-frog-data.json"
    out_path.write_text(json.dumps(result, indent=2))

    print(f"\n  Summary: {error_count} errors | {warning_count} warnings | {notice_count} notices")
    print(f"  Saved → state/screaming-frog-data.json")
    print()

    return result


def _describe(priority, key, count):
    """Short actionable description for each issue type."""
    desc_map = {
        "404_page":              f"{count} page(s) returning 404 — remove from sitemap and fix internal links",
        "4XX_page":              f"{count} page(s) with 4XX errors — review and fix or redirect",
        "indexable-Orphan_page_(has_no_incoming_internal_links)": f"{count} page(s) with no internal links — add links from relevant pages",
        "indexable-Page_has_links_to_broken_page": f"{count} page(s) linking to broken URLs — update or remove broken links",
        "indexable-Page_has_no_outgoing_links": f"{count} page(s) with no outgoing links — add relevant internal/external links",
        "HTTP_to_HTTPS_redirect": f"{count} URL(s) redirecting HTTP→HTTPS — expected, monitor for chains",
        "Open_Graph_tags_missing": f"{count} page(s) missing OG tags — add for better social sharing",
        "Organic_traffic_dropped": f"{count} page(s) with dropped organic traffic — investigate ranking changes",
        "Redirect_chain":         f"{count} redirect chain(s) — simplify to single redirects",
        "Structured_data_has_Google_rich_results_validation_error": f"{count} page(s) with rich results errors — fix schema markup",
        "Structured_data_has_schema.org_validation_error": f"{count} page(s) with schema.org errors — validate and fix structured data",
        "indexable-Multiple_H1_tags": f"{count} page(s) with multiple H1 tags — keep one H1 per page",
        "indexable-Page_and_SERP_titles_do_not_match": f"{count} page(s) where Google rewrites title — optimise title tags",
        "indexable-Pages_have_high_AI_content_levels": f"{count} page(s) flagged for high AI content — review for quality/originality",
        "indexable-Word_count_changed": f"{count} page(s) with significant word count changes — check for accidental content removal",
        "3XX_redirect":           f"{count} URL(s) with 3XX redirects — review and consolidate",
        "Missing_alt_text":       f"{count} image(s) missing alt text — add descriptive alt attributes",
        "Open_Graph_URL_not_matching_canonical": f"{count} page(s) where OG URL ≠ canonical — align OG URL with canonical",
        "indexable-Meta_description_tag_missing_or_empty": f"{count} page(s) missing meta description — write unique descriptions",
        "indexable-Meta_description_too_long":   f"{count} page(s) with meta description > 160 chars — trim to 150–160 chars",
        "indexable-Title_too_short": f"{count} page(s) with title < 30 chars — expand title tags",
    }
    return desc_map.get(key, f"{count} page(s) affected")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Import Ahrefs Site Audit CSV export")
    parser.add_argument("--folder", default=None,
                        help="Path to export folder (default: auto-detect newest in state/)")
    args = parser.parse_args()

    try:
        folder = find_export_folder(args.folder)
        convert(folder)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
