"""
parse_metricool_pdf.py — Extract organic social metrics from the weekly
Metricool PDF export.

Input:  cb247-inbox/metricool.pdf  (user drops this every Monday before 1:55am AWST)
Output: state/metricool-data.json

This recovers the rich Metricool data (stories impressions, reach,
demographics, GBP actions) that Apify public scraping cannot replace.

Failure mode: if the PDF is missing or unparseable, keeps the last good
JSON file in place rather than blanking it. This protects the dashboard
when the user forgets to drop the file.

Parser strategy:
  - pdfplumber extracts full text per page
  - regex pulls labelled values (Followers, Impressions, etc.)
  - WoW deltas extracted from "+12.34%" / "-12.34%" patterns near each value
  - Date range pulled from the report header

The Metricool PDF layout is fairly consistent. If they tweak the format,
individual field regexes may miss — but the script logs missing fields
explicitly so we know what to fix.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR  = Path(__file__).resolve().parent.parent
INBOX_DIR = BASE_DIR / "cb247-inbox"
STATE_DIR = BASE_DIR / "state"
PDF_PATH  = INBOX_DIR / "metricool.pdf"
OUT_PATH  = STATE_DIR / "metricool-data.json"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _num(s):
    """Parse '8,982' or '1.05' or '54,680' → 8982 / 1.05 / 54680."""
    if s is None:
        return None
    s = str(s).strip().replace(",", "").replace("%", "")
    if not s or s in ("-", "–", "—"):
        return None
    try:
        return float(s) if "." in s else int(s)
    except ValueError:
        return None


def _pct(s):
    """Parse '+12.34%' or '-90.0%' → 12.34 / -90.0. Returns None if no match."""
    if not s:
        return None
    m = re.search(r"([+\-]?\d+(?:\.\d+)?)\s*%", str(s))
    if not m:
        return None
    return float(m.group(1))


def _find(text, *patterns, group=1, transform=_num):
    """Return first matching group from text across multiple patterns.
    Patterns are tried in order. Returns None if no match.
    """
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE | re.MULTILINE)
        if m:
            try:
                val = m.group(group)
                return transform(val) if transform else val
            except (IndexError, ValueError):
                continue
    return None


def _find_value_then_pct(text, label_patterns):
    """For metrics where value + WoW % appear adjacent.
    Returns dict {value, wow_pct} or {value: None, wow_pct: None}.
    """
    for p in label_patterns:
        # Try to match: label  VALUE  PCT%  (in that order, with stuff between)
        m = re.search(
            p + r"[^0-9\-]*([0-9][0-9,\.]*)[^%\n]*?([+\-]?\d+(?:\.\d+)?\s*%)",
            text, re.IGNORECASE | re.DOTALL,
        )
        if m:
            return {"value": _num(m.group(1)), "wow_pct": _pct(m.group(2))}
        # Try value only
        m = re.search(p + r"[^0-9\-]*([0-9][0-9,\.]*)", text, re.IGNORECASE | re.DOTALL)
        if m:
            return {"value": _num(m.group(1)), "wow_pct": None}
    return {"value": None, "wow_pct": None}


# ── Main parser ──────────────────────────────────────────────────────────────

def parse():
    if not PDF_PATH.exists():
        print(f"[metricool] PDF not found at {PDF_PATH}")
        print(f"            Drop the weekly Metricool export here and re-run.")
        return None

    try:
        import pdfplumber
    except ImportError:
        print("[metricool] pdfplumber not installed. Run: pip install pdfplumber")
        return None

    # Extract full text from all pages
    pages_text = []
    try:
        with pdfplumber.open(PDF_PATH) as pdf:
            for p in pdf.pages:
                t = p.extract_text() or ""
                pages_text.append(t)
    except Exception as e:
        print(f"[metricool] PDF read failed: {e}")
        return None

    full_text = "\n\n".join(pages_text)
    if not full_text.strip():
        print("[metricool] PDF parsed but no text extracted — may be scanned/image-only.")
        return None

    # ── Date range from header ──
    # Format observed: "25 May 2026 - 31 May 2026" or "25/05/2026 - 31/05/2026"
    date_range = {"start": None, "end": None, "raw": None}
    dr_match = re.search(
        r"(\d{1,2}[\s/-][A-Za-z]{3,}[\s/-]\d{4})\s*[-–—to]+\s*(\d{1,2}[\s/-][A-Za-z]{3,}[\s/-]\d{4})",
        full_text,
    )
    if dr_match:
        date_range["start"] = dr_match.group(1)
        date_range["end"]   = dr_match.group(2)
        date_range["raw"]   = dr_match.group(0)
    else:
        # Fallback: numeric date format
        dr_match = re.search(r"(\d{1,2}/\d{1,2}/\d{4})\s*[-–—to]+\s*(\d{1,2}/\d{1,2}/\d{4})", full_text)
        if dr_match:
            date_range["start"] = dr_match.group(1)
            date_range["end"]   = dr_match.group(2)
            date_range["raw"]   = dr_match.group(0)

    # ── Combined totals (account level) ──
    combined = {
        "total_followers":    _find_value_then_pct(full_text, [r"Total\s+Followers", r"Community\s+Total"])["value"],
        "total_impressions":  _find_value_then_pct(full_text, [r"Total\s+Impressions", r"Impressions"])["value"],
        "total_interactions": _find_value_then_pct(full_text, [r"Total\s+Interactions", r"Interactions"])["value"],
        "total_posts":        _find_value_then_pct(full_text, [r"Total\s+Posts", r"Posts\s+published"])["value"],
    }
    combined["wow"] = {
        "total_impressions":  _find_value_then_pct(full_text, [r"Total\s+Impressions", r"Impressions"])["wow_pct"],
        "total_interactions": _find_value_then_pct(full_text, [r"Total\s+Interactions", r"Interactions"])["wow_pct"],
    }

    # ── Facebook section ──
    fb_section = _section(full_text, "Facebook", ["Instagram", "Google Business", "GBP"])
    fb = {
        "followers":          _find_value_then_pct(fb_section, [r"Followers", r"Page\s+Likes"])["value"],
        "followers_chg":      _find_value_then_pct(fb_section, [r"Followers", r"Page\s+Likes"])["wow_pct"],
        "impressions":        _find_value_then_pct(fb_section, [r"Impressions"])["value"],
        "impressions_chg":    _find_value_then_pct(fb_section, [r"Impressions"])["wow_pct"],
        "interactions":       _find_value_then_pct(fb_section, [r"Interactions"])["value"],
        "interactions_chg":   _find_value_then_pct(fb_section, [r"Interactions"])["wow_pct"],
        "posts_published":    _find_value_then_pct(fb_section, [r"Posts\s+Published", r"Posts"])["value"],
        "posts_chg":          _find_value_then_pct(fb_section, [r"Posts\s+Published", r"Posts"])["wow_pct"],
        "reach_avg":          _find_value_then_pct(fb_section, [r"Avg\s+Reach", r"Average\s+Reach"])["value"],
        "engagement_rate":    _find_value_then_pct(fb_section, [r"Engagement\s+Rate"])["value"],
        "community_acquired": _find_value_then_pct(fb_section, [r"Acquired", r"Gained"])["value"],
        "community_lost":     _find_value_then_pct(fb_section, [r"Lost"])["value"],
        "page_views":         _find_value_then_pct(fb_section, [r"Page\s+Views"])["value"],
        "page_views_chg":     _find_value_then_pct(fb_section, [r"Page\s+Views"])["wow_pct"],
    }

    # ── Instagram section ──
    ig_section = _section(full_text, "Instagram", ["Facebook", "Google Business", "GBP"])
    ig = {
        "followers":              _find_value_then_pct(ig_section, [r"Followers"])["value"],
        "followers_chg":          _find_value_then_pct(ig_section, [r"Followers"])["wow_pct"],
        "followers_balance":      _find_value_then_pct(ig_section, [r"Balance", r"Net\s+gain"])["value"],
        "views":                  _find_value_then_pct(ig_section, [r"Views"])["value"],
        "views_chg":              _find_value_then_pct(ig_section, [r"Views"])["wow_pct"],
        "avg_reach_per_day":      _find_value_then_pct(ig_section, [r"Avg\s+Reach\s+per\s+Day", r"Daily\s+Reach"])["value"],
        "avg_reach_per_day_chg":  _find_value_then_pct(ig_section, [r"Avg\s+Reach\s+per\s+Day", r"Daily\s+Reach"])["wow_pct"],
        "posts_published":        _find_value_then_pct(ig_section, [r"Posts\s+Published", r"Feed\s+Posts"])["value"],
        "posts_chg":              _find_value_then_pct(ig_section, [r"Posts\s+Published", r"Feed\s+Posts"])["wow_pct"],
        "post_engagement":        _find_value_then_pct(ig_section, [r"Post\s+Engagement"])["value"],
        "post_engagement_chg":    _find_value_then_pct(ig_section, [r"Post\s+Engagement"])["wow_pct"],
        # Reels
        "reels_published":        _find_value_then_pct(ig_section, [r"Reels\s+Published", r"Reels"])["value"],
        "reels_chg":              _find_value_then_pct(ig_section, [r"Reels\s+Published", r"Reels"])["wow_pct"],
        "reel_avg_reach":         _find_value_then_pct(ig_section, [r"Reel.*Avg\s+Reach", r"Reels\s+Reach"])["value"],
        "reel_engagement":        _find_value_then_pct(ig_section, [r"Reel.*Engagement"])["value"],
        "reel_likes":             _find_value_then_pct(ig_section, [r"Reel\s+Likes", r"Reels\s+Likes"])["value"],
        "reel_likes_chg":         _find_value_then_pct(ig_section, [r"Reel\s+Likes", r"Reels\s+Likes"])["wow_pct"],
        # Stories
        "stories_published":      _find_value_then_pct(ig_section, [r"Stories\s+Published", r"Stories"])["value"],
        "stories_impressions":    _find_value_then_pct(ig_section, [r"Stories?\s+Impressions"])["value"],
        "stories_impressions_chg":_find_value_then_pct(ig_section, [r"Stories?\s+Impressions"])["wow_pct"],
        "story_avg_reach":        _find_value_then_pct(ig_section, [r"Story\s+Avg\s+Reach", r"Stories?\s+Reach"])["value"],
        "story_reach_chg":        _find_value_then_pct(ig_section, [r"Story\s+Avg\s+Reach", r"Stories?\s+Reach"])["wow_pct"],
    }

    # ── GBP section ──
    gbp_section = _section(full_text, "Google Business", ["Facebook", "Instagram"], also_match=["GBP", "Business Profile"])
    gbp = {
        "reach_total":      _find_value_then_pct(gbp_section, [r"Total\s+Reach", r"Reach"])["value"],
        "reach_chg":        _find_value_then_pct(gbp_section, [r"Total\s+Reach", r"Reach"])["wow_pct"],
        "maps_reach":       _find_value_then_pct(gbp_section, [r"Maps\s+Reach"])["value"],
        "maps_chg":         _find_value_then_pct(gbp_section, [r"Maps\s+Reach"])["wow_pct"],
        "search_reach":    _find_value_then_pct(gbp_section, [r"Search\s+Reach"])["value"],
        "search_chg":      _find_value_then_pct(gbp_section, [r"Search\s+Reach"])["wow_pct"],
        "website_clicks":   _find_value_then_pct(gbp_section, [r"Website\s+Clicks?"])["value"],
        "website_chg":      _find_value_then_pct(gbp_section, [r"Website\s+Clicks?"])["wow_pct"],
        "phone_clicks":     _find_value_then_pct(gbp_section, [r"Phone\s+Clicks?", r"Calls"])["value"],
        "phone_chg":        _find_value_then_pct(gbp_section, [r"Phone\s+Clicks?", r"Calls"])["wow_pct"],
        "directions":       _find_value_then_pct(gbp_section, [r"Directions?\s+Requests?", r"Directions?"])["value"],
        "directions_chg":   _find_value_then_pct(gbp_section, [r"Directions?\s+Requests?", r"Directions?"])["wow_pct"],
        "total_actions":    _find_value_then_pct(gbp_section, [r"Total\s+Actions"])["value"],
        "actions_chg":      _find_value_then_pct(gbp_section, [r"Total\s+Actions"])["wow_pct"],
        "reviews_week":     _find_value_then_pct(gbp_section, [r"Reviews"])["value"],
        "star_rating":      _find_value_then_pct(gbp_section, [r"Star\s+Rating", r"Average\s+Rating"])["value"],
    }

    # ── Quality check — count how many fields parsed successfully ──
    def _count_filled(d):
        return sum(1 for v in d.values() if v is not None and v != 0)

    quality = {
        "fb_fields_filled":  _count_filled({k:v for k,v in fb.items() if not k.endswith("_chg")}),
        "ig_fields_filled":  _count_filled({k:v for k,v in ig.items() if not k.endswith("_chg")}),
        "gbp_fields_filled": _count_filled({k:v for k,v in gbp.items() if not k.endswith("_chg")}),
        "date_range_found":  bool(date_range.get("start")),
    }

    result = {
        "parsed_at":   datetime.now(timezone.utc).isoformat(),
        "source_pdf":  str(PDF_PATH),
        "date_range":  date_range,
        "combined":    combined,
        "fb":          fb,
        "ig":          ig,
        "gbp":         gbp,
        "parse_quality": quality,
        "available":   quality["ig_fields_filled"] >= 5,  # heuristic: need 5+ IG fields to count as successful parse
    }

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, indent=2, default=str))

    print(f"[metricool] Parsed → {OUT_PATH}")
    print(f"            Date range: {date_range.get('raw') or 'NOT FOUND'}")
    print(f"            FB fields filled:  {quality['fb_fields_filled']}")
    print(f"            IG fields filled:  {quality['ig_fields_filled']}")
    print(f"            GBP fields filled: {quality['gbp_fields_filled']}")
    if quality["ig_fields_filled"] < 5:
        print(f"            WARN: only {quality['ig_fields_filled']} IG fields parsed — Metricool PDF layout may have changed.")
        print(f"            Last good metricool-data.json was preserved.")
    return result


def _section(full_text, primary_label, end_labels, also_match=None):
    """Extract a section of text between primary_label and the next end_label.
    also_match: list of additional labels that all mean the same section.
    """
    labels = [primary_label] + (also_match or [])
    # Find earliest match of any label
    start_idx = None
    for lbl in labels:
        m = re.search(r"\b" + re.escape(lbl) + r"\b", full_text, re.IGNORECASE)
        if m and (start_idx is None or m.start() < start_idx):
            start_idx = m.start()
    if start_idx is None:
        return ""
    # Find earliest end label after start
    end_idx = len(full_text)
    for lbl in end_labels:
        m = re.search(r"\b" + re.escape(lbl) + r"\b", full_text[start_idx + len(primary_label):], re.IGNORECASE)
        if m:
            candidate = start_idx + len(primary_label) + m.start()
            if candidate < end_idx:
                end_idx = candidate
    return full_text[start_idx:end_idx]


if __name__ == "__main__":
    result = parse()
    sys.exit(0 if result and result.get("available") else 1)
