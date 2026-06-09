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


# ── NEW (08 Jun 2026): Metricool layout v2 helpers ──
# Metricool restructured their PDF in mid-2026. Numbers now appear
# ABOVE labels (e.g. "14.28K\nFollowers\n+0.21%") instead of after.
# Per-channel breakdowns follow as:
#   <val1> <val2> [<val3>]
#   <pct1> <pct2> [<pct3>]
#   <channel1_label> <channel2_label> [<channel3_label>]
# where channel order is GBP / Facebook / Instagram for impression-type
# metrics, and Facebook / Instagram for follower-type metrics.

def _num_with_suffix(s):
    """Parse '14.28K' / '143.07K' / '4.5M' / '688' / '92' → int.
    K = thousand, M = million, B = billion.
    """
    if s is None:
        return None
    s = str(s).strip().replace(",", "")
    if not s or s in ("-", "–", "—"):
        return None
    m = re.match(r"^([\d.]+)\s*([KMB]?)$", s, re.IGNORECASE)
    if not m:
        try:
            return float(s) if "." in s else int(s)
        except ValueError:
            return None
    val = float(m.group(1))
    mult = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}.get(m.group(2).lower(), 1)
    out = val * mult
    return int(out) if out.is_integer() else out


def _parse_metric_page_v2(page_text):
    """Parse a v2 Metricool 'metric headline' page.

    Layout:
        14.28K            ← total value
        Followers         ← metric label
        +0.21%            ← total % change
        ChasingBetter247  ← brand name (skipped)
        5284 8997         ← per-channel values (space-separated)
        +0.09% +0.28%     ← per-channel % changes
        Facebook Instagram ← channel labels (in same order as values)
        30 May 26 - 05 Jun 26  ← date footer (skipped)

    Returns dict:
        {
          "metric_label": str,
          "total_value":  int|float,
          "total_pct":    float,
          "by_channel":   {channel_name: {"value": ..., "pct": ...}},
        }
    Returns None if the page doesn't match the v2 layout.
    """
    lines = [ln.strip() for ln in (page_text or "").splitlines() if ln.strip()]
    if len(lines) < 6:
        return None

    # Line 0: total value (e.g. "14.28K")
    total_value = _num_with_suffix(lines[0])
    if total_value is None:
        return None

    # Line 1: metric label (e.g. "Followers")
    metric_label = lines[1]
    if not re.match(r"^[A-Z][A-Za-z ]+$", metric_label):
        return None  # Not a metric page

    # Line 2: total %
    total_pct = _pct(lines[2])

    # Find the per-channel value line: a row of 2-3 numbers (no %, no label)
    val_line_idx = None
    for i in range(3, len(lines)):
        # Skip the "ChasingBetter247" brand line
        if "ChasingBetter247" in lines[i]:
            continue
        # Look for a line of 2-3 numbers
        tokens = lines[i].split()
        if 2 <= len(tokens) <= 3 and all(re.match(r"^[\d.]+[KMB]?$", t) for t in tokens):
            val_line_idx = i
            break

    if val_line_idx is None:
        return None

    values = [_num_with_suffix(t) for t in lines[val_line_idx].split()]

    # Next line: per-channel percents (may have one missing slot if channel value is 0)
    pcts = []
    if val_line_idx + 1 < len(lines):
        pct_tokens = re.findall(r"[+\-]?\d+(?:\.\d+)?\s*%", lines[val_line_idx + 1])
        pcts = [_pct(t) for t in pct_tokens]

    # Find the channel-label line (after the percents). It may span 1-2 lines
    # because "Google Business Profile" can wrap.
    channel_text = ""
    for i in range(val_line_idx + 2, min(val_line_idx + 5, len(lines))):
        ln = lines[i]
        # Skip date footer lines
        if re.search(r"\d{1,2}\s+[A-Za-z]+\s+\d{2,4}", ln) and "-" in ln:
            break
        channel_text += " " + ln

    # Identify channels in order
    channels = []
    if re.search(r"Google\s+Business", channel_text, re.IGNORECASE):
        channels.append("gbp")
    if re.search(r"Facebook", channel_text, re.IGNORECASE):
        channels.append("fb")
    if re.search(r"Instagram", channel_text, re.IGNORECASE):
        channels.append("ig")

    # Map values to channels (best-effort positional match)
    by_channel = {}
    for idx, ch in enumerate(channels):
        if idx < len(values):
            by_channel[ch] = {
                "value": values[idx],
                "pct":   pcts[idx] if idx < len(pcts) else None,
            }

    return {
        "metric_label": metric_label,
        "total_value":  total_value,
        "total_pct":    total_pct,
        "by_channel":   by_channel,
    }


def _parse_v2_pages(pdf_path):
    """Iterate through Metricool v2 PDF pages and extract all metric pages.

    Returns:
        {
          "Followers":    {parse_metric_page_v2 output},
          "Impressions":  {...},
          "Interactions": {...},
          "Posts":        {...},
        }
    """
    try:
        import pdfplumber
    except ImportError:
        return {}
    out = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            parsed = _parse_metric_page_v2(text)
            if parsed and parsed["metric_label"] not in out:
                out[parsed["metric_label"]] = parsed
    return out


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
    # Format observed (older Metricool):  "25 May 2026 - 31 May 2026" or "25/05/2026 - 31/05/2026"
    # Format observed (newer Metricool 08 Jun 2026): "30 May 26 - 05 Jun 26" (2-digit year)
    # and on cover page sometimes "30 May 26 05 Jun 26" (newline between dates).
    date_range = {"start": None, "end": None, "raw": None}
    # Pattern 1: dd Mon yyyy/yy with optional dash/em-dash/to between
    dr_match = re.search(
        r"(\d{1,2}[\s/-][A-Za-z]{3,}[\s/-]\d{2,4})\s*[-–—to]+\s*(\d{1,2}[\s/-][A-Za-z]{3,}[\s/-]\d{2,4})",
        full_text,
    )
    if dr_match:
        date_range["start"] = dr_match.group(1)
        date_range["end"]   = dr_match.group(2)
        date_range["raw"]   = dr_match.group(0)
    else:
        # Pattern 2: Same but without an explicit separator (newline between dates — cover page layout)
        dr_match = re.search(
            r"(\d{1,2}[\s/-][A-Za-z]{3,}[\s/-]\d{2,4})\s+(\d{1,2}[\s/-][A-Za-z]{3,}[\s/-]\d{2,4})",
            full_text,
        )
        if dr_match:
            date_range["start"] = dr_match.group(1)
            date_range["end"]   = dr_match.group(2)
            date_range["raw"]   = dr_match.group(0)
        else:
            # Pattern 3: numeric date format (legacy fallback)
            dr_match = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})\s*[-–—to]+\s*(\d{1,2}/\d{1,2}/\d{2,4})", full_text)
            if dr_match:
                date_range["start"] = dr_match.group(1)
                date_range["end"]   = dr_match.group(2)
                date_range["raw"]   = dr_match.group(0)

    # ── v2 layout parse (Metricool reformatted 08 Jun 2026) ──
    # The new PDF has 4 "headline metric" pages near the top — Followers,
    # Impressions, Interactions, Posts — each with total + per-channel
    # breakdown for FB/IG/GBP. Parse those directly.
    v2 = _parse_v2_pages(PDF_PATH)

    def _v2_chan(metric_name, channel):
        d = v2.get(metric_name) or {}
        return (d.get("by_channel") or {}).get(channel) or {}

    # ── Combined totals (account level) ──
    combined = {
        "total_followers":    (v2.get("Followers")    or {}).get("total_value"),
        "total_impressions":  (v2.get("Impressions")  or {}).get("total_value"),
        "total_interactions": (v2.get("Interactions") or {}).get("total_value"),
        "total_posts":        (v2.get("Posts")        or {}).get("total_value"),
    }
    combined["wow"] = {
        "total_followers":    (v2.get("Followers")    or {}).get("total_pct"),
        "total_impressions":  (v2.get("Impressions")  or {}).get("total_pct"),
        "total_interactions": (v2.get("Interactions") or {}).get("total_pct"),
        "total_posts":        (v2.get("Posts")        or {}).get("total_pct"),
    }
    # Dashboard reads `combined.reach` — alias to total_impressions
    combined["reach"] = combined["total_impressions"]

    # Legacy full-text fallback (only used if v2 parse failed completely)
    if combined["total_followers"] is None:
        combined["total_followers"] = _find_value_then_pct(full_text, [r"Total\s+Followers", r"Community\s+Total"])["value"]
    if combined["total_impressions"] is None:
        combined["total_impressions"] = _find_value_then_pct(full_text, [r"Total\s+Impressions", r"Impressions"])["value"]
    if combined["total_interactions"] is None:
        combined["total_interactions"] = _find_value_then_pct(full_text, [r"Total\s+Interactions", r"Interactions"])["value"]
    if combined["total_posts"] is None:
        combined["total_posts"] = _find_value_then_pct(full_text, [r"Total\s+Posts", r"Posts\s+published"])["value"]

    # ── Facebook section ──
    # v2: prefer the per-channel breakdowns from the headline metric pages.
    # Legacy: fall back to in-section regex if v2 didn't find the metric.
    fb_section = _section(full_text, "Facebook", ["Instagram", "Google Business", "GBP"])
    fb = {
        "followers":          _v2_chan("Followers",    "fb").get("value")  or _find_value_then_pct(fb_section, [r"Followers", r"Page\s+Likes"])["value"],
        "followers_chg":      _v2_chan("Followers",    "fb").get("pct")    or _find_value_then_pct(fb_section, [r"Followers", r"Page\s+Likes"])["wow_pct"],
        "impressions":        _v2_chan("Impressions",  "fb").get("value")  or _find_value_then_pct(fb_section, [r"Impressions"])["value"],
        "impressions_chg":    _v2_chan("Impressions",  "fb").get("pct")    or _find_value_then_pct(fb_section, [r"Impressions"])["wow_pct"],
        "interactions":       _v2_chan("Interactions", "fb").get("value")  or _find_value_then_pct(fb_section, [r"Interactions"])["value"],
        "interactions_chg":   _v2_chan("Interactions", "fb").get("pct")    or _find_value_then_pct(fb_section, [r"Interactions"])["wow_pct"],
        "posts_published":    _v2_chan("Posts",        "fb").get("value")  or _find_value_then_pct(fb_section, [r"Posts\s+Published", r"Posts"])["value"],
        "posts_chg":          _v2_chan("Posts",        "fb").get("pct")    or _find_value_then_pct(fb_section, [r"Posts\s+Published", r"Posts"])["wow_pct"],
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
        "followers":              _v2_chan("Followers",    "ig").get("value") or _find_value_then_pct(ig_section, [r"Followers"])["value"],
        "followers_chg":          _v2_chan("Followers",    "ig").get("pct")   or _find_value_then_pct(ig_section, [r"Followers"])["wow_pct"],
        "followers_balance":      _find_value_then_pct(ig_section, [r"Balance", r"Net\s+gain"])["value"],
        "views":                  _find_value_then_pct(ig_section, [r"Views"])["value"],
        "views_chg":              _find_value_then_pct(ig_section, [r"Views"])["wow_pct"],
        "impressions":            _v2_chan("Impressions",  "ig").get("value"),
        "impressions_chg":        _v2_chan("Impressions",  "ig").get("pct"),
        "interactions":           _v2_chan("Interactions", "ig").get("value"),
        "interactions_chg":       _v2_chan("Interactions", "ig").get("pct"),
        "posts_published_new":    _v2_chan("Posts",        "ig").get("value"),
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

    # ── v3 page-router — extract rich detail pages ────────────────────────────
    # The headline regex pass above only catches summary fields. The new
    # Metricool layout (08 Jun 2026+) puts detail metrics on dedicated pages
    # using a "title → brand → values → percentages → labels" pattern.
    # This router walks each page, classifies it by title, and extracts the
    # structured fields into ig/fb/gbp dicts. Only OVERWRITES None values
    # so the regex pass remains authoritative for what it already filled.
    v3 = _parse_v3_pages(pages_text)

    def _fill(target, source):
        """Copy source[k] into target[k] only if target[k] is None or 0."""
        for k, v in source.items():
            if v is None or v == 0:
                continue
            if target.get(k) in (None, 0):
                target[k] = v

    _fill(ig, v3.get("ig") or {})
    _fill(fb, v3.get("fb") or {})

    # Top-level enrichment fields (lists + dicts the dashboard uses)
    enrichment = {
        "top_reels":     v3.get("top_reels")     or [],
        "top_posts":     v3.get("top_posts")     or [],
        "top_stories":   v3.get("top_stories")   or [],
        "geo_top_cities": v3.get("geo_top_cities") or [],
        "ig_competitors": v3.get("ig_competitors") or [],
        "fb_competitors": v3.get("fb_competitors") or [],
        "hashtags":      v3.get("hashtags")      or [],
    }
    # Move enriched lists onto ig/fb where the render expects them
    if enrichment["top_reels"]:    ig["top_reels"]     = enrichment["top_reels"]
    if enrichment["top_posts"]:    ig["top_posts"]     = enrichment["top_posts"]
    if enrichment["top_stories"]:  ig["top_stories"]   = enrichment["top_stories"]
    if enrichment["geo_top_cities"]: ig["geo_top_cities"] = enrichment["geo_top_cities"]
    if enrichment["ig_competitors"]: ig["competitors"] = enrichment["ig_competitors"]
    if enrichment["fb_competitors"]: fb["competitors"] = enrichment["fb_competitors"]
    if enrichment["hashtags"]:     ig["hashtags"]      = enrichment["hashtags"]

    # GBP per-location detail from page-router (Malaga from main PDF,
    # Ellenbrook from sidecar PDF if present)
    gbp_v3 = v3.get("gbp") or {}
    _fill(gbp, gbp_v3.get("malaga") or {})   # populate top-level with Malaga as default
    # Also expose per-location blocks for the dashboard's 2-location section
    gbp["malaga_perf"]     = gbp_v3.get("malaga") or {}
    gbp["ellenbrook_perf"] = gbp_v3.get("ellenbrook") or {}

    # ── Quality check — count how many fields parsed successfully ──
    def _count_filled(d):
        return sum(1 for v in d.values() if v is not None and v != 0)

    quality = {
        "fb_fields_filled":  _count_filled({k:v for k,v in fb.items() if not k.endswith("_chg")}),
        "ig_fields_filled":  _count_filled({k:v for k,v in ig.items() if not k.endswith("_chg")}),
        "gbp_fields_filled": _count_filled({k:v for k,v in gbp.items() if not k.endswith("_chg")}),
        "combined_fields_filled": _count_filled({k:v for k,v in combined.items() if k != "wow" and not isinstance(v, dict)}),
        "date_range_found":  bool(date_range.get("start")),
    }

    # ── Success heuristic (v2 layout aware) ──
    # The new Metricool v2 layout populates ONLY the headline metrics
    # (4 combined + 4 fb + 4 ig + 3 gbp = 15 essentials). Deep-section
    # fields stay None until we parse Stories/Reels/GBP detail pages.
    # So "successful parse" now means: date_range parsed AND combined
    # totals populated AND ≥3 essential IG fields (followers + impressions
    # + interactions).
    success = (
        quality["date_range_found"]
        and quality["combined_fields_filled"] >= 3
        and quality["ig_fields_filled"] >= 3
    )

    result = {
        "parsed_at":   datetime.now(timezone.utc).isoformat(),
        "source_pdf":  str(PDF_PATH),
        "date_range":  date_range,
        "combined":    combined,
        "fb":          fb,
        "ig":          ig,
        "gbp":         gbp,
        "parse_quality": quality,
        "available":   success,
    }

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, indent=2, default=str))

    print(f"[metricool] Parsed → {OUT_PATH}")
    print(f"            Date range: {date_range.get('raw') or 'NOT FOUND'}")
    print(f"            Combined fields:  {quality['combined_fields_filled']}/4")
    print(f"            FB fields filled:  {quality['fb_fields_filled']}")
    print(f"            IG fields filled:  {quality['ig_fields_filled']}")
    print(f"            GBP fields filled: {quality['gbp_fields_filled']}")
    if not success:
        print(f"            WARN: parse below threshold — date_range={quality['date_range_found']}, combined={quality['combined_fields_filled']}, ig={quality['ig_fields_filled']}")
        print(f"            Output written, but exit=1 so shell wrapper preserves fallback behaviour.")
    else:
        print(f"            ✅ Parse successful (v2 layout)")
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


# ── v3 page-router — extract rich detail pages ──────────────────────────────
# The new Metricool layout (08 Jun 2026+) puts detail metrics on
# dedicated pages with title → brand → values → percentages → labels
# layout. Page-routing is more robust than full-text regex.

def _v3_value_pct_pairs(text):
    """Walk page text and find consecutive (value_line, pct_line) pairs.

    A page like:
        Reels published in period
        chasingbetter247
        1.81 4
        +29.30% -33.33%
        Engagement Reels
        30 May 26 - 05 Jun 26

    Returns: [([1.81, 4], [29.30, -33.33])]

    Multi-pair example (Interactions of published reels):
        Interactions of published reels
        chasingbetter247
        102 2 1 113
        -19.05% +0.00% -75.00% -19.86%
        Likes Comments Saved Interactions
        8 4
        -11.11% -33.33%
        Shares Reels
    Returns: [
        ([102, 2, 1, 113], [-19.05, 0, -75, -19.86]),
        ([8, 4], [-11.11, -33.33]),
    ]
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    pairs = []

    def _to_num(s):
        s = s.replace(",", "").replace("+", "").strip()
        mult = 1.0
        if s.endswith("K") or s.endswith("k"):
            s = s[:-1]; mult = 1_000
        elif s.endswith("M") or s.endswith("m"):
            s = s[:-1]; mult = 1_000_000
        try:
            f = float(s) * mult
            return int(f) if f == int(f) else f
        except ValueError:
            return None

    def _to_pct(s):
        try:
            return float(s.replace("%", "").replace("+", "").strip())
        except ValueError:
            return None

    # Numeric line: contains only numbers + separators (no letters except K/M)
    NUM_RE = re.compile(r"^[\d.,KMkm+\-\s]+$")
    PCT_RE = re.compile(r"^[+\-\d.%\s]+%[+\-\d.%\s]*$")

    i = 0
    while i < len(lines) - 1:
        if NUM_RE.match(lines[i]) and PCT_RE.match(lines[i + 1]):
            nums = re.findall(r"[\d.,]+[KMk]?", lines[i])
            pcts = re.findall(r"[+\-]?[\d.]+%", lines[i + 1])
            vals = [_to_num(n) for n in nums]
            ps   = [_to_pct(p) for p in pcts]
            # Drop trailing Nones
            vals = [v for v in vals if v is not None]
            ps   = [p for p in ps if p is not None]
            # Allow pcts to be SHORTER than values (PDF sometimes omits some
            # pcts when no comparable prior period exists). Pad with None
            # at the END so positional indexing still works.
            if vals and ps:
                while len(ps) < len(vals):
                    ps.append(None)
                # Cap pcts list at len(values)
                ps = ps[:len(vals)]
                pairs.append((vals, ps))
            i += 2   # skip both consumed lines
        else:
            i += 1
    return pairs


def _v3_extract_value_label(text):
    """Layout pattern: title / brand / value(s) / pcts(s) / labels(s).

    Returns dict {label_lower: {value, pct}} for as many labels as we can
    align numerically. Handles "K" / "M" suffix in values.
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    # Find the run of: numeric-line → percent-line → label-line
    out = {}
    for i in range(len(lines) - 2):
        nums = re.findall(r"[+\-]?[\d.,]+[KMk]?", lines[i])
        pcts = re.findall(r"[+\-]?[\d.]+%", lines[i + 1])
        # labels often on the line AFTER pcts; sometimes 2 lines (when
        # there's a sub-block with its own value/pct/label below)
        # Find label line: must contain at least one alpha word, no digits
        label_line = None
        for j in (i + 2, i + 3):
            if j < len(lines):
                ll = lines[j]
                if ll and re.search(r"[A-Za-z]", ll) and not re.search(r"\d", ll):
                    label_line = ll
                    break
        if not label_line:
            continue
        labels = re.split(r"\s{2,}|\t+", label_line)
        if len(labels) == 1:
            # Single label OR a multi-word label like "Avg reach per day"
            labels = [label_line]
        if not labels:
            continue

        # Strip K/M suffix in values, parse to int/float
        def _val(s):
            s = s.replace(",", "").replace("+", "").strip()
            mult = 1.0
            if s.endswith("K") or s.endswith("k"):
                s = s[:-1]; mult = 1_000
            elif s.endswith("M") or s.endswith("m"):
                s = s[:-1]; mult = 1_000_000
            try:
                v = float(s) * mult
                return int(v) if v == int(v) else v
            except ValueError:
                return None

        def _pct_val(s):
            s = s.replace("%", "").replace("+", "").strip()
            try:
                return float(s)
            except ValueError:
                return None

        values = [_val(n) for n in nums]
        pcts_n = [_pct_val(p) for p in pcts]

        # Align: shortest of (len(values), len(pcts_n), len(labels))
        n = min(len(values), len(pcts_n) if pcts_n else len(values), len(labels))
        for k in range(n):
            lbl = labels[k].lower().strip().rstrip(".")
            out[lbl] = {"value": values[k], "pct": pcts_n[k] if pcts_n else None}
    return out


def _v3_extract_value_only(text):
    """Same as above but for single-value pages (e.g. 'Stories 23 -34.29%'
    layout where labels are below the single value)."""
    return _v3_extract_value_label(text)


def _v3_parse_table_rows(text, header_keywords):
    """Generic table-row extractor for the 'Ranking of …' pages.
    Splits on lines that start with a date, captures the row as a list.
    """
    rows = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    capturing = False
    for line in lines:
        # Detect date prefix — "Jun 4, 2026" or similar
        if re.match(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d+,\s+\d{4}", line):
            rows.append(line)
            capturing = True
        elif capturing and line and not re.match(r"^(Showing|\d{1,2}:\d{2})", line):
            # continuation of previous row's text
            if rows:
                rows[-1] += " " + line
    return rows


def _parse_v3_pages(pages_text):
    """Walk pages and route by title to specific extractors.

    Returns dict with keys:
      ig, fb              — partial dicts to merge into ig/fb sections
      top_reels, top_posts, top_stories, hashtags
      geo_top_cities, ig_competitors, fb_competitors
      gbp = {malaga: {...}, ellenbrook: {...}}
    """
    ig = {}
    fb = {}
    top_reels = []
    top_posts = []
    top_stories = []
    hashtags = []
    geo_top_cities = []
    ig_competitors = []
    fb_competitors = []
    gbp = {"malaga": {}, "ellenbrook": {}}

    # Identify pages by their first 2-3 lines (title + brand)
    # Brand disambiguation: the SECOND line is the brand block.
    #   "chasingbetter247"  (all-lowercase)        → Instagram handle
    #   "ChasingBetter247"  (camelcase)            → Facebook page name (general)
    #   "ChasingBetter247 Health & Fitness Gym ..." → GBP listing
    # We preserve the raw second line (NOT lowercased) for disambiguation.
    for idx, text in enumerate(pages_text):
        if not text:
            continue
        raw_lines = text.split("\n")
        title = (raw_lines[0] or "").strip().lower()
        brand_raw = (raw_lines[1] or "").strip() if len(raw_lines) > 1 else ""
        head = "\n".join(raw_lines[:3]).lower()

        # Strict brand routing
        is_ig_page = brand_raw == "chasingbetter247" or brand_raw.lower() == "chasingbetter247" and brand_raw[0:1].islower()
        is_fb_page = brand_raw == "ChasingBetter247"
        # GBP page header is the location name
        is_gbp_malaga = "chasingbetter247 health & fitness gym" in brand_raw.lower() and "ellenbrook" not in brand_raw.lower()
        is_gbp_ellenbrook = "ellenbrook" in brand_raw.lower() and "chasingbetter247" in brand_raw.lower()

        # ── IG: Posts/Reels/Stories — published in period (lowercase = IG handle) ──
        # Direct positional extraction: find consecutive (values, pcts) pairs
        # then map by position based on the known page layout.
        pairs = _v3_value_pct_pairs(text)

        if "reels published in period" in title and is_ig_page:
            # Layout: "<engagement> <reels>" + "<eng%> <reels%>"
            if pairs and len(pairs[0][0]) >= 2:
                v, p = pairs[0]
                ig["reel_engagement"] = v[0]
                ig["reel_engagement_chg"] = p[0]
                ig["reels_published"] = v[1]
                ig["reels_chg"] = p[1]
        elif "reach of published reels" in title and is_ig_page:
            # Layout: "<avg_reach> <reels>" + "<reach%> <reels%>"
            if pairs and len(pairs[0][0]) >= 2:
                v, p = pairs[0]
                ig["reel_avg_reach"] = v[0]
                ig["reel_avg_reach_chg"] = p[0]
                if not ig.get("reels_published"):
                    ig["reels_published"] = v[1]
                    ig["reels_chg"] = p[1]
        elif "interactions of published reels" in title and is_ig_page:
            # Layout: 2 pairs.
            # Pair 1: "<likes> <comments> <saved> <interactions>" + pcts (4 values)
            # Pair 2: "<shares> <reels>" + pcts (2 values)
            if pairs:
                v, p = pairs[0]
                if len(v) >= 4:
                    ig["reel_likes"] = v[0]; ig["reel_likes_chg"] = p[0]
                    ig["reel_comments"] = v[1]
                    ig["reel_saved"]  = v[2]
                    ig["reel_interactions_total"] = v[3]
                if len(pairs) >= 2:
                    v2, p2 = pairs[1]
                    if len(v2) >= 2:
                        ig["reel_shares"] = v2[0]
        elif "stories published in period" in title and is_ig_page:
            if pairs:
                v, p = pairs[0]
                # Multiple layouts seen:
                #   Layout A (single value): "<stories>" + "<stories%>" → 1 value
                #   Layout B (multi): "<impressions> <avg_reach> <stories>" + pcts
                if len(v) == 1:
                    ig["stories_published"] = v[0]
                    ig["stories_chg"] = p[0]
                elif len(v) >= 3:
                    ig["stories_impressions"] = v[0]; ig["stories_impressions_chg"] = p[0]
                    ig["story_avg_reach"] = v[1];     ig["story_reach_chg"] = p[1]
                    ig["stories_published"] = v[2];   ig["stories_chg"] = p[2]
        elif "posts published in period" in title and is_ig_page:
            # Layout: "<engagement> <posts>" + pcts
            if pairs and len(pairs[0][0]) >= 2:
                v, p = pairs[0]
                ig["post_engagement"] = v[0]; ig["post_engagement_chg"] = p[0]
                ig["posts_published"] = v[1]; ig["posts_chg"] = p[1]
        elif "reach of published posts" in title and is_ig_page:
            # Layout: "<avg_reach> <posts>" + pcts
            if pairs and len(pairs[0][0]) >= 2:
                v, p = pairs[0]
                ig["post_avg_reach"] = v[0]; ig["post_avg_reach_chg"] = p[0]
        elif "interactions of published posts" in title and is_ig_page:
            # Layout: 2 pairs.
            # Pair 1: "<likes> <comments> <saved> <shares>" + pcts (4 values)
            # Pair 2: "<interactions>" + "<interactions%>" (single value)
            if pairs:
                v, p = pairs[0]
                if len(v) >= 4:
                    ig["post_likes"]    = v[0]; ig["post_likes_chg"] = p[0]
                    ig["post_comments"] = v[1]
                    ig["post_saved"]    = v[2]
                    ig["post_shares"]   = v[3]
                if len(pairs) >= 2:
                    v2, p2 = pairs[1]
                    if v2: ig["post_interactions"] = v2[0]
        elif "community growth" in title and is_ig_page:
            # Layout: "<followers> <balance> <total_content>" + pcts (3 values)
            if pairs and len(pairs[0][0]) >= 1:
                v, p = pairs[0]
                ig["followers"] = v[0]
                if len(v) >= 2: ig["followers_balance"] = v[1]
        elif "average reach per day" in title and is_ig_page:
            # Layout: "<views> <avg_reach> <total_content>" + pcts
            if pairs:
                v, p = pairs[0]
                if len(v) >= 2:
                    ig["views"] = v[0]; ig["views_chg"] = p[0]
                    ig["avg_reach_per_day"] = v[1]; ig["avg_reach_per_day_chg"] = p[1]

        # ── IG: Top reels / Top posts / Top stories / Hashtags ──
        elif "ranking of reels" in title and is_ig_page:
            # Each row has format: "<text> Go <views> <reach> <likes> <saved> <comments> <shares> <engagement>"
            # — the "Go" is the Metricool "Go to post" link inline. Capture the
            # 7 numbers following "Go ". Date + time are on separate lines.
            for line in text.split("\n"):
                m = re.search(
                    r"Go\s+(\d[\d,]*)\s+(\d[\d,]*)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)\b",
                    line,
                )
                if m:
                    top_reels.append({
                        "text":      line[:80].rsplit(" Go ", 1)[0][:80],
                        "views":     int(m.group(1).replace(",", "")),
                        "reach":     int(m.group(2).replace(",", "")),
                        "likes":     int(m.group(3)),
                        "saves":     int(m.group(4)),
                        "comments":  int(m.group(5)),
                        "shares":    int(m.group(6)),
                        "engagement": float(m.group(7)),
                        "avg_watch": "—",   # not in this layout (separate stat earlier)
                    })
            top_reels = top_reels[:5]
        elif "ranking of posts" in title and is_ig_page:
            # Format: "<text> Go <views> <reach> <likes> <comments> <saved> <engagement>" (6 numbers)
            for line in text.split("\n"):
                m = re.search(
                    r"Go\s+(\d[\d,]*)\s+(\d[\d,]*)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)\b",
                    line,
                )
                if m:
                    top_posts.append({
                        "text":     line[:80].rsplit(" Go ", 1)[0][:80],
                        "views":    int(m.group(1).replace(",", "")),
                        "reach":    int(m.group(2).replace(",", "")),
                        "likes":    int(m.group(3)),
                        "comments": int(m.group(4)),
                        "saved":    int(m.group(5)),
                        "engagement": float(m.group(6)),
                    })
            top_posts = top_posts[:5]
        elif "ranking of stories" in title:
            for line in text.split("\n"):
                # Format: "date / text / impressions reach replies tap-back tap-forward exits"
                m = re.search(r"(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$", line.strip())
                if m and "Jun" not in line and "May" not in line:
                    top_stories.append({
                        "impressions": int(m.group(1)),
                        "reach":       int(m.group(2)),
                        "replies":     int(m.group(3)),
                        "tap_back":    int(m.group(4)),
                        "tap_forward": int(m.group(5)),
                        "exits":       int(m.group(6)),
                    })
        elif "ranking of hashtags" in title:
            for line in text.split("\n"):
                m = re.match(r"#([a-zA-Z0-9_]+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", line.strip())
                if m:
                    hashtags.append({
                        "hashtag":  m.group(1),
                        "posts":    int(m.group(2)),
                        "views":    int(m.group(3)),
                        "likes":    int(m.group(4)),
                        "comments": int(m.group(5)),
                    })

        # ── IG: Demographics / countries+cities ──
        elif "demographics: countries and cities" in title and is_ig_page:
            # Each PDF line has BOTH columns: "Country X% City, Region Y%".
            # findall all (name, pct) matches on each line, then keep the LAST
            # match which is the CITY column. Reset list — this is the IG page
            # we want (Facebook has its own demographics page with different format).
            geo_top_cities = []
            for line in text.split("\n"):
                line = line.strip()
                # Match "Name [, Region [, Subregion]] N.NN%" — supports up to 3 comma segments
                matches = re.findall(
                    r"([A-Z][A-Za-z\s]+(?:,\s+[A-Z][A-Za-z\s,]*)?)\s+([\d.]+)%",
                    line,
                )
                if len(matches) >= 2:
                    # Last match = city column (first = country)
                    name = matches[-1][0].strip().rstrip(",")
                    pct = float(matches[-1][1])
                    geo_top_cities.append({"city": name, "pct": pct})
            geo_top_cities = geo_top_cities[:8]

        # ── IG/FB competitors ──
        elif "competitors" in title and (is_ig_page or is_fb_page):
            # IG competitor page has "Reels" column, FB has "Likes on page"
            is_ig_competitors = is_ig_page and "reels" in text.lower()
            for line in text.split("\n"):
                # "Revo Fitness Gym / 107.79k 5 3 882.13 1440.13 2.15" — IG layout
                # "World Gym Australia / 51.6k 51.6k 5 2.8 0.2 0 0.01" — FB layout (Followers + Likes)
                m = re.match(r"^\s*([\d.]+[Kk]?)\s+(\d+)\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*$", line)
                if m:
                    # The line above this line is the competitor name
                    pass   # we'll handle table-row pairing differently
            # Alternative: walk lines, pair name + numbers
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            for i, line in enumerate(lines):
                # IG: "107.79k 5 3 882.13 1440.13 2.15"
                m_ig = re.match(r"^([\d.]+[Kk]?)\s+(\d+)\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)$", line)
                # FB: "51.6k 51.6k 5 2.8 0.2 0 0.01"
                m_fb = re.match(r"^([\d.]+[Kk]?)\s+([\d.]+[Kk]?)\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)$", line)
                # Find preceding name (1 line up = name, 2 lines down = handle for IG)
                name = lines[i-1] if i > 0 else ""
                if name.replace(" ", "").isdigit() or name.startswith("Showing"):
                    continue
                def _kv(s):
                    s = s.replace(",", "").replace("k", "000").replace("K", "000")
                    try: return int(float(s))
                    except: return 0
                if m_ig and is_ig_competitors:
                    handle = lines[i+1] if (i+1) < len(lines) else name
                    ig_competitors.append({
                        "name":       name,
                        "handle":     handle,
                        "followers":  _kv(m_ig.group(1)),
                        "posts":      int(m_ig.group(2)),
                        "reels":      int(m_ig.group(3)),
                        "likes":      float(m_ig.group(4)),
                        "comments":   float(m_ig.group(5)),
                        "engagement": float(m_ig.group(6)),
                    })
                elif m_fb and not is_ig_competitors:
                    fb_competitors.append({
                        "name":       name,
                        "followers":  _kv(m_fb.group(1)),
                        "likes_page": _kv(m_fb.group(2)),
                        "posts":      int(m_fb.group(3)),
                        "reactions":  float(m_fb.group(4)),
                        "comments":   float(m_fb.group(5)),
                        "shares":     float(m_fb.group(6)),
                        "engagement": float(m_fb.group(7)),
                    })

        # ── GBP Malaga (in main PDF) ──
        elif title == "reach" and is_gbp_malaga:
            # Layout: "<maps> <search> <total>" + "<maps%> <search%> <total%>"
            if pairs and len(pairs[0][0]) >= 3:
                v, p = pairs[0]
                gbp["malaga"]["maps_reach"]   = v[0]; gbp["malaga"]["maps_chg"]   = p[0]
                gbp["malaga"]["search_reach"] = v[1]; gbp["malaga"]["search_chg"] = p[1]
                gbp["malaga"]["reach_total"]  = v[2]; gbp["malaga"]["reach_chg"]  = p[2]
        elif title == "clicks" and is_gbp_malaga:
            # Layout: "<website> <phone> <directions> <total>" + pcts
            if pairs and len(pairs[0][0]) >= 4:
                v, p = pairs[0]
                gbp["malaga"]["website_clicks"] = v[0]; gbp["malaga"]["website_chg"]    = p[0]
                gbp["malaga"]["phone_clicks"]   = v[1]; gbp["malaga"]["phone_chg"]      = p[1]
                gbp["malaga"]["directions"]     = v[2]; gbp["malaga"]["directions_chg"] = p[2]
                gbp["malaga"]["total_actions"]  = v[3]; gbp["malaga"]["actions_chg"]    = p[3]

    # ── Ellenbrook GBP — sidecar PDF ──
    ell_pdf = BASE_DIR / "cb247-inbox" / "metricool_GBP_Ellenbrook.pdf"
    if ell_pdf.exists():
        try:
            import pdfplumber
            with pdfplumber.open(ell_pdf) as pdf:
                ell_pages = [p.extract_text() or "" for p in pdf.pages]
            for text in ell_pages:
                if not text: continue
                title = (text.split("\n")[0] or "").strip().lower()
                e_pairs = _v3_value_pct_pairs(text)
                if title == "reach" and e_pairs and len(e_pairs[0][0]) >= 3:
                    v, p = e_pairs[0]
                    gbp["ellenbrook"]["maps_reach"]   = v[0]; gbp["ellenbrook"]["maps_chg"]   = p[0]
                    gbp["ellenbrook"]["search_reach"] = v[1]; gbp["ellenbrook"]["search_chg"] = p[1]
                    gbp["ellenbrook"]["reach_total"]  = v[2]; gbp["ellenbrook"]["reach_chg"]  = p[2]
                elif title == "clicks" and e_pairs and len(e_pairs[0][0]) >= 4:
                    v, p = e_pairs[0]
                    gbp["ellenbrook"]["website_clicks"] = v[0]; gbp["ellenbrook"]["website_chg"]    = p[0]
                    gbp["ellenbrook"]["phone_clicks"]   = v[1]; gbp["ellenbrook"]["phone_chg"]      = p[1]
                    gbp["ellenbrook"]["directions"]     = v[2]; gbp["ellenbrook"]["directions_chg"] = p[2]
                    gbp["ellenbrook"]["total_actions"]  = v[3]; gbp["ellenbrook"]["actions_chg"]    = p[3]
                elif title == "reviews" and e_pairs and len(e_pairs[0][0]) >= 2:
                    v, p = e_pairs[0]
                    gbp["ellenbrook"]["star_rating"]    = v[0]; gbp["ellenbrook"]["star_rating_chg"]    = p[0]
                    gbp["ellenbrook"]["reviews_total"]  = v[1]; gbp["ellenbrook"]["reviews_total_chg"]  = p[1]
        except Exception as e:
            print(f"[metricool] Ellenbrook GBP PDF parse warning: {e}")

    return {
        "ig": ig,
        "fb": fb,
        "top_reels": top_reels,
        "top_posts": top_posts,
        "top_stories": top_stories,
        "hashtags": hashtags,
        "geo_top_cities": geo_top_cities,
        "ig_competitors": ig_competitors,
        "fb_competitors": fb_competitors,
        "gbp": gbp,
    }


if __name__ == "__main__":
    result = parse()
    sys.exit(0 if result and result.get("available") else 1)
