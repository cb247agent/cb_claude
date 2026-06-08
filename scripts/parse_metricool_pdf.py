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


if __name__ == "__main__":
    result = parse()
    sys.exit(0 if result and result.get("available") else 1)
