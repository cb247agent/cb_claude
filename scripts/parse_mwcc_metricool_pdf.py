"""
parse_mwcc_metricool_pdf.py — Extract organic social metrics from the weekly
Metricool PDF export for My World Childcare.

Input:  mwcc-inbox/metricool.pdf  (Jordan drops this every Monday before cron)
Output: state/mwcc-social.json

PDF structure (55 pages, observed 07 Jun 2026):
  Page 1       : Cover (Meta Ad Insights title + report period + account names)
  Pages 2–5    : Account-level KPI summary (followers, impressions, interactions, posts)
  Pages 6–7    : Top posts ranking (account-wide)
  Pages 8–13   : Google Ads paid summary (already covered by pull_mwcc_ads.py API)
  Pages 14–29  : Facebook detail (community growth, content, demographics, top posts)
  Pages 30–45  : Instagram detail (community growth, reach, posts/reels/stories, hashtags)
  Pages 46–47  : Google Business Profile per centre (currently Seville Grove only)
  Pages 48–55  : Google Ads detail (covered by API — kept for reference)

The parser uses pdfplumber for text extraction. It looks for fixed keyword
landmarks ("Followers", "Impressions", "Community growth", etc.) and parses
the numeric values that follow on the same or next line.

Run:
  python scripts/parse_mwcc_metricool_pdf.py
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DIR    = Path(__file__).resolve().parent.parent
INBOX_DIR   = BASE_DIR / "mwcc-inbox"
STATE_DIR   = BASE_DIR / "state"
OUTPUT_FILE = STATE_DIR / "mwcc-social.json"


def _find_pdf() -> Path | None:
    """Find a metricool*.pdf in mwcc-inbox/."""
    if not INBOX_DIR.exists():
        return None
    candidates = sorted(INBOX_DIR.glob("metricool*.pdf"))
    return candidates[0] if candidates else None


def _to_num(s: str) -> float | int | None:
    """Parse a Metricool number — handles 'K' (thousands), commas, percentages."""
    if s is None:
        return None
    s = s.strip().replace(",", "").replace("$", "")
    if not s or s in ("-", "—"):
        return None
    pct = s.endswith("%")
    if pct:
        s = s[:-1].strip()
    k = s.endswith("K") or s.endswith("k")
    if k:
        s = s[:-1].strip()
    try:
        val = float(s)
        if k:
            val *= 1000
        return val
    except ValueError:
        return None


def _to_pct(s: str) -> float | None:
    """Parse a +0.14% / -36.76% WoW token."""
    if not s:
        return None
    s = s.strip().replace("+", "").replace("%", "")
    try:
        return float(s)
    except ValueError:
        return None


def parse_metricool(pdf_path: Path) -> dict:
    """Extract MWCC organic social metrics from the Metricool PDF."""
    try:
        import pdfplumber
    except ImportError:
        print("[metricool-mwcc] pdfplumber not installed. Run: pip install pdfplumber")
        sys.exit(1)

    out: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "brand":        "mwcc",
        "available":    True,
        "source_pdf":   str(pdf_path.relative_to(BASE_DIR)),
        "date_range":   {},
        "summary":      {},
        "facebook":     {},
        "instagram":    {},
        "gbp":          {"centres": {}},
        "notes":        [],
    }

    with pdfplumber.open(pdf_path) as pdf:
        pages = [(p.extract_text() or "") for p in pdf.pages]

    # ── Date range — appears on every page, "30 May 26 - 05 Jun 26" ──────────
    date_re = re.compile(r"(\d{1,2}\s+\w+\s+\d{2})\s*-\s*(\d{1,2}\s+\w+\s+\d{2})")
    for txt in pages:
        m = date_re.search(txt)
        if m:
            start_s, end_s = m.group(1), m.group(2)
            try:
                start_dt = datetime.strptime(start_s, "%d %b %y")
                end_dt   = datetime.strptime(end_s,   "%d %b %y")
                out["date_range"] = {
                    "start":     start_dt.strftime("%Y-%m-%d"),
                    "end":       end_dt.strftime("%Y-%m-%d"),
                    "raw":       f"{start_s} - {end_s}",
                    "label":     f"{start_dt.strftime('%d %b')}–{end_dt.strftime('%d %b %Y')}",
                }
            except ValueError:
                out["date_range"] = {"raw": f"{start_s} - {end_s}"}
            break

    # ── Account summary (pages 2–5) ──────────────────────────────────────────
    # Pattern (each page):
    #   <total_value>
    #   <metric_name>
    #   <total_wow_pct>
    #   My World Child Care
    #   <fb_val> <ig_val> [<gbp_val>]
    #   <fb_wow> <ig_wow> [<gbp_wow>]
    #   Facebook  Instagram  [Google Business Profile]
    def _parse_kpi_page(text: str) -> dict:
        if not text:
            return {}
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if len(lines) < 6:
            return {}
        # First line: total value
        total = _to_num(lines[0])
        if total is None:
            return {}
        result = {"total": total}
        # Find WoW after metric name
        # Lines pattern: [val, metric, +x.xx%, "My World Child Care", "fb ig gbp", "+wow +wow +wow", "Facebook Instagram GBP"]
        wow_total = None
        for line in lines[1:5]:
            if "%" in line and not "My" in line:
                wow_total = _to_pct(line)
                break
        if wow_total is not None:
            result["wow_pct"] = wow_total
        # Now find the per-platform breakdown — line with several space-separated numbers
        for i, line in enumerate(lines):
            if "My World Child Care" in line and i + 1 < len(lines):
                # Next line: "3698 602" or "120.83K 48.55K 31"
                nums_line = lines[i + 1]
                wow_line  = lines[i + 2] if i + 2 < len(lines) else ""
                lbl_line  = lines[i + 3] if i + 3 < len(lines) else ""
                # Split into tokens
                num_tokens = nums_line.split()
                wow_tokens = re.findall(r"[+\-]?\d+(?:\.\d+)?%", wow_line)
                # Labels can be on multiple lines depending on wrap — collect from i+3 to i+5
                lbl_tokens_raw = " ".join(lines[i+3:i+6])
                # Identify platforms by keyword
                platforms = []
                if "Google Business" in lbl_tokens_raw or "GBP" in lbl_tokens_raw:
                    platforms = ["fb", "ig", "gbp"] if len(num_tokens) == 3 else ["gbp"]
                elif "Facebook" in lbl_tokens_raw and "Instagram" in lbl_tokens_raw:
                    platforms = ["fb", "ig"]
                # Build per-platform dict
                # Order in PDF appears to be: Facebook, Instagram, [Google Business Profile]
                # but page 3 had "Google Business / Profile" + "Facebook Instagram" so reorder by label position
                # Simplest: trust the position-order = FB, IG, GBP
                for plat, val_token, wow_token in zip(platforms, num_tokens, wow_tokens + [""] * len(platforms)):
                    result[plat] = _to_num(val_token)
                    p = _to_pct(wow_token)
                    if p is not None:
                        result[f"{plat}_wow_pct"] = p
                break
        return result

    # The KPI pages have these metric names (page 2 = Followers, 3 = Impressions, etc.)
    kpi_metric_pages = {
        "followers":    2,
        "impressions":  3,
        "interactions": 4,
        "posts":        5,
    }
    for metric, page_idx in kpi_metric_pages.items():
        if page_idx <= len(pages):
            parsed = _parse_kpi_page(pages[page_idx - 1])
            if parsed:
                out["summary"][metric] = parsed

    # ── Facebook detail (page 17: Community growth) ─────────────────────────
    # "3698 4 4 1" = Followers, Total content, Acquired, Lost
    # "+0.08% +100.00% +100.00%" — these correspond to a subset
    if len(pages) >= 17:
        fb_growth = pages[16]  # page 17 = index 16
        lines = [l.strip() for l in fb_growth.split("\n") if l.strip()]
        for line in lines:
            nums = re.findall(r"\d+(?:\.\d+)?", line)
            if len(nums) >= 4 and "Followers" not in line and "growth" not in line:
                # First number matches followers; subsequent are content, acquired, lost
                try:
                    out["facebook"].update({
                        "followers":     int(float(nums[0])),
                        "total_content": int(float(nums[1])),
                        "acquired":      int(float(nums[2])),
                        "lost":          int(float(nums[3])),
                        "balance":       int(float(nums[2])) - int(float(nums[3])),
                    })
                except (ValueError, IndexError):
                    pass
                break
        # WoW from same page
        for line in lines:
            if "%" in line and "+" in line or "-" in line:
                pcts = re.findall(r"([+\-]\d+(?:\.\d+)?)%", line)
                if pcts:
                    out["facebook"]["followers_wow_pct"] = _to_pct(pcts[0])
                    break

    # ── Pull FB posts published from summary ─────────────────────────────────
    if "posts" in out["summary"]:
        out["facebook"]["posts_published"] = int(out["summary"]["posts"].get("fb", 0) or 0)
        out["facebook"]["impressions"]     = int(out["summary"]["impressions"].get("fb", 0) or 0)
        out["facebook"]["interactions"]    = int(out["summary"]["interactions"].get("fb", 0) or 0)

    # ── Instagram detail (page 30: Community growth, page 33: Average reach) ─
    if len(pages) >= 30:
        ig_growth = pages[29]  # page 30 = index 29
        lines = [l.strip() for l in ig_growth.split("\n") if l.strip()]
        for line in lines:
            nums = re.findall(r"\d+(?:\.\d+)?", line)
            if len(nums) >= 3 and "Followers" not in line:
                try:
                    out["instagram"].update({
                        "followers":          int(float(nums[0])),
                        "followers_balance":  int(float(nums[1])),
                        "total_content":      int(float(nums[2])),
                    })
                except (ValueError, IndexError):
                    pass
                break

    if len(pages) >= 33:
        ig_reach = pages[32]
        lines = [l.strip() for l in ig_reach.split("\n") if l.strip()]
        for line in lines:
            # Look for "48.55K 8241.86 4" pattern
            if "K" in line and "." in line:
                nums = re.findall(r"\d+(?:\.\d+)?K?", line)
                if len(nums) >= 2:
                    out["instagram"]["avg_reach_per_day"] = int(_to_num(nums[0]) or 0)
                    if len(nums) >= 2:
                        v = _to_num(nums[1])
                        if v: out["instagram"]["views"] = v
                    break

    # Pull IG posts/reels counts from summary too
    if "posts" in out["summary"]:
        out["instagram"]["content_published"] = int(out["summary"]["posts"].get("ig", 0) or 0)
        out["instagram"]["impressions"]       = int(out["summary"]["impressions"].get("ig", 0) or 0)
        out["instagram"]["interactions"]      = int(out["summary"]["interactions"].get("ig", 0) or 0)

    # ── Ranking of posts (Facebook page 24, Instagram page 37) ──────────────
    def _parse_ranking_table(text: str, kind: str) -> list[dict]:
        """Extract top posts from a ranking page. Returns a list of dicts."""
        if not text:
            return []
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        results = []
        # Look for date lines like "Jun 4, 2026" — those mark the start of a row
        date_re_local = re.compile(r"(\w{3}\s+\d{1,2},\s+\d{4})")
        for i, line in enumerate(lines):
            if date_re_local.match(line):
                # Collect this and the next 1-2 lines as the post body
                body = " ".join(lines[i:i+3])
                # Extract numbers — last few are metrics
                nums = re.findall(r"\d+(?:\.\d+)?", body)
                # Text snippet — everything between date and first number
                text_match = re.search(
                    rf"{re.escape(line)}\s+(?:\d+:\d+\s*[AP]M\s+)?(?:Go\s+)?(.+?)(?:\s+\d+\s+\d+|\s*$)",
                    body
                )
                text_snippet = (text_match.group(1).strip() if text_match else "").replace("\n", " ")[:120]
                if kind == "fb_post":
                    # Reactions, Comments, Shares, Clicks, Link clicks, Views, Reach, Video views, Engagement
                    if len(nums) >= 5:
                        results.append({
                            "published":  line,
                            "text":       text_snippet,
                            "views":      _to_num(nums[-4]) if len(nums) >= 4 else None,
                            "reach":      _to_num(nums[-3]) if len(nums) >= 3 else None,
                            "engagement": _to_num(nums[-1]) if nums else None,
                        })
                elif kind == "fb_reel":
                    if len(nums) >= 3:
                        results.append({
                            "published":  line,
                            "text":       text_snippet,
                            "views":      _to_num(nums[0]),
                            "reach":      _to_num(nums[1]),
                            "likes":      _to_num(nums[2]) if len(nums) > 2 else 0,
                        })
                elif kind == "ig_post":
                    # Views, Reach, Likes, Comments, Saved, Engagement
                    if len(nums) >= 5:
                        results.append({
                            "published":  line,
                            "text":       text_snippet,
                            "views":      _to_num(nums[-6]) if len(nums) >= 6 else None,
                            "reach":      _to_num(nums[-5]) if len(nums) >= 5 else None,
                            "likes":      _to_num(nums[-4]) if len(nums) >= 4 else 0,
                            "engagement": _to_num(nums[-1]),
                        })
                elif kind == "ig_reel":
                    if len(nums) >= 4:
                        results.append({
                            "published":  line,
                            "text":       text_snippet,
                            "views":      _to_num(nums[0]),
                            "reach":      _to_num(nums[1]),
                            "likes":      _to_num(nums[2]),
                        })
        return results[:10]  # keep top 10

    # ── Top posts / reels / hashtags / demographics (08 Jun 2026) ────────────
    # Pages discovered in Metricool PDF (55-page report):
    #   FB Ranking of posts     : page 24
    #   FB Demographics: countries+cities : page 19
    #   IG Ranking of posts     : page 37
    #   IG Demographics: countries+cities : page 32
    #   IG Demographics: gender+ages : page 31
    #   IG Ranking of hashtags  : pages 38-39
    #   IG Ranking of reels     : page 43
    def _parse_ranking_v2(text: str, kind: str) -> list[dict]:
        """Parse Metricool's multi-line ranking tables.

        Each row spans 3 lines on the rendered PDF:
            Line A: "Jun 4, 2026  <caption start>"
            Line B: "Go  N1 N2 N3 ... NK"   ← numbers anchored by "Go " button
            Line C: "5:03 PM <caption continuation>"

        Strategy: scan for lines starting with "Go " followed by ≥3 numbers,
        then look back/forward 1 line for the date + caption.
        """
        if not text:
            return []
        results = []
        lines = text.split("\n")
        date_re = re.compile(r"^([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})\s*(.*)$")
        time_re = re.compile(r"^(\d{1,2}:\d{2}\s*[AP]M)\s*(.*)$")
        # Match "Go <nums>" anywhere on the line — for reels the caption text
        # sometimes wraps onto the "Go ..." line ("Acting level: Room for Go 461 316 9...")
        go_re   = re.compile(r"(?:^|\s)Go\s+((?:-?\d+(?:\.\d+)?\s+){2,}-?\d+(?:\.\d+)?)\s*$")
        for i, line in enumerate(lines):
            m_go = go_re.search(line.strip())
            if not m_go:
                continue
            nums = [_to_num(n) for n in m_go.group(1).split()]
            # Pre-Go caption text on the same line (for reels: "Acting level: Room for Go 461 316 ...")
            pre_go = line.strip()[:m_go.start()].strip()
            # Look back for date line (within 3 lines — reels have pre-date caption)
            date_str = None
            caption_parts = []
            date_j = None
            for j in range(max(0, i-3), i):
                m_d = date_re.match(lines[j].strip())
                if m_d:
                    date_str = m_d.group(1)
                    date_j = j
                    if m_d.group(2):
                        caption_parts.append(m_d.group(2).strip())
                    break
            if not date_str:
                continue
            # Pre-date caption line (reels — "Directing level: Expert." sits above date)
            if date_j is not None and date_j > 0:
                pre_date = lines[date_j - 1].strip()
                # Skip header row + previous Go line residue + dates + time continuations
                header_words = ("Published", "Views", "Reach", "Likes", "Reactions", "Comments", "Shares", "Engagement", "Showing", "Ranking")
                looks_like_header = any(pre_date.startswith(w) for w in header_words)
                looks_like_time   = bool(time_re.match(pre_date))
                if pre_date and not go_re.search(pre_date) and not date_re.match(pre_date) and not looks_like_header and not looks_like_time:
                    caption_parts.insert(0, pre_date)
            # Pre-Go caption on the same line ("Acting level: Room for")
            if pre_go and not date_re.match(pre_go):
                caption_parts.append(pre_go)
            # Look forward for time + caption continuation (within 2 lines)
            time_str = ""
            for j in range(i+1, min(len(lines), i+3)):
                m_t = time_re.match(lines[j].strip())
                if m_t:
                    time_str = m_t.group(1)
                    if m_t.group(2):
                        caption_parts.append(m_t.group(2).strip())
                    break
            caption = " ".join(caption_parts)[:120].replace("...", "…").strip()
            row = {
                "published": f"{date_str}{(' ' + time_str) if time_str else ''}",
                "text": caption,
            }
            if kind == "fb_post":
                # Columns: Reactions, Comments, Shares, Clicks, Link clicks, Views, Reach, Video views, Engagement
                # PDF row example: "Go 2 0 0 11 0 185 105 0 12.38"
                if len(nums) >= 9:
                    row.update({
                        "reactions": nums[0], "comments": nums[1], "shares": nums[2],
                        "clicks": nums[3] + nums[4], "views": nums[5], "reach": nums[6],
                        "engagement": nums[-1],
                    })
                elif len(nums) >= 6:
                    row.update({
                        "reactions": nums[0], "comments": nums[1], "shares": nums[2],
                        "views": nums[-3], "reach": nums[-2], "engagement": nums[-1],
                    })
                else:
                    continue
            elif kind == "ig_post":
                # Columns: Views, Reach, Likes, Comments, Saved, Engagement
                # PDF row example: "Go 89 44 5 0 0 13.64"
                if len(nums) >= 6:
                    row.update({
                        "views": nums[0], "reach": nums[1], "likes": nums[2],
                        "comments": nums[3], "saved": nums[4], "engagement": nums[-1],
                    })
                else:
                    continue
            elif kind == "ig_reel":
                # Columns: Views, Reach, Likes, Saved, Comments, Shares, Engagement
                # PDF row example: "Go 461 316 9 0 1 1 3.48"
                if len(nums) >= 7:
                    row.update({
                        "views": nums[0], "reach": nums[1], "likes": nums[2],
                        "saved": nums[3], "comments": nums[4], "shares": nums[5],
                        "engagement": nums[-1],
                    })
                else:
                    continue
            results.append(row)
        return results[:10]

    # FB top posts (page 24)
    if len(pages) >= 24:
        out["facebook"]["top_posts"] = _parse_ranking_v2(pages[23], "fb_post")
    out["facebook"]["top_reels"] = []  # FB reels page doesn't have a clean ranking
    # IG top posts (page 37) + IG top reels (page 43)
    if len(pages) >= 37:
        out["instagram"]["top_posts"] = _parse_ranking_v2(pages[36], "ig_post")
    if len(pages) >= 43:
        out["instagram"]["top_reels"] = _parse_ranking_v2(pages[42], "ig_reel")

    # ── IG Hashtag Ranking (pages 38-39) ─────────────────────────────────────
    def _parse_hashtags(*texts) -> list[dict]:
        hashtags = []
        seen = set()
        for text in texts:
            if not text:
                continue
            # Pattern: "#hashtag <posts> <views> <likes> <comments>"
            for m in re.finditer(r"(#\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", text):
                tag = m.group(1).strip()
                if tag in seen:
                    continue
                seen.add(tag)
                hashtags.append({
                    "hashtag": tag,
                    "posts":    int(m.group(2)),
                    "views":    int(m.group(3)),
                    "likes":    int(m.group(4)),
                    "comments": int(m.group(5)),
                })
        # Sort by views desc
        hashtags.sort(key=lambda h: h["views"], reverse=True)
        return hashtags

    ig_hashtag_texts = []
    if len(pages) >= 38: ig_hashtag_texts.append(pages[37])
    if len(pages) >= 39: ig_hashtag_texts.append(pages[38])
    out["instagram"]["hashtags"] = _parse_hashtags(*ig_hashtag_texts)

    # ── Demographics — geo (FB page 19, IG page 32) + IG age/gender (page 31) ─
    def _parse_geo(text: str) -> dict:
        """Parse 'Top 10 countries' + 'Top 10 cities/regions' from a page."""
        if not text:
            return {}
        countries = []
        cities = []
        # Lines like "Australia 98.65%" or "Australia 1308 93.50%"
        line_re = re.compile(r"^([A-Za-z][A-Za-z\s,\.\-']+?)\s+(?:\d+\s+)?(\d+(?:\.\d+)?)%\s*$")
        in_left_col = True  # countries (left) vs cities/regions (right)
        for raw in text.split("\n"):
            line = raw.strip()
            if not line:
                continue
            if "Top 10 countries" in line or "Demographics" in line or "30 May" in line or line == "My World Child Care" or line.startswith("www.") or line in ("myworldchildcare", "Top 10 cities", "Top 10 regions"):
                continue
            # Lines often have two columns concatenated:
            # "Australia 98.65% Perth, WA, Australia 48.54%"
            twocol = re.match(r"^([A-Za-z][A-Za-z\s,\.\-']+?)\s+(?:\d+\s+)?(\d+(?:\.\d+)?)%\s+([A-Za-z][A-Za-z\s,\.\-']+?)\s+(?:\d+\s+)?(\d+(?:\.\d+)?)%\s*$", line)
            if twocol:
                countries.append({"name": twocol.group(1).strip(), "pct": float(twocol.group(2))})
                cities.append({"name": twocol.group(3).strip(), "pct": float(twocol.group(4))})
                continue
            m = line_re.match(line)
            if m:
                entry = {"name": m.group(1).strip(), "pct": float(m.group(2))}
                # Heuristic — country names are short, city names often have commas
                if "," in entry["name"] or len(entry["name"]) > 18:
                    cities.append(entry)
                else:
                    countries.append(entry)
        return {
            "countries": countries[:10],
            "cities":    cities[:10],
        }

    if len(pages) >= 19:
        out["facebook"]["demographics"] = _parse_geo(pages[18])
    if len(pages) >= 32:
        out["instagram"]["demographics"] = _parse_geo(pages[31])
    # IG page 31 has gender+ages but chart-rendered (no extractable text in our sample) —
    # leave a placeholder so the dashboard can show "—" gracefully.
    if "demographics" in out["instagram"]:
        out["instagram"]["demographics"]["age_gender_available"] = False

    # ── GBP per centre (page 46) ────────────────────────────────────────────
    # Page header pattern: "My World Child Care & Before & After School Care <Centre Name>"
    if len(pages) >= 46:
        gbp_text = pages[45]
        lines = [l.strip() for l in gbp_text.split("\n") if l.strip()]
        # Find centre name from header
        centre_name = None
        for line in lines:
            m = re.search(r"My World Child Care.*?Care\s+(.+)$", line)
            if m:
                centre_name = m.group(1).strip()
                break
            m2 = re.search(r"(Armadale|Midvale|Rockingham|Seville Grove|Waikiki)", line)
            if m2:
                centre_name = m2.group(1).strip()
                break
        if not centre_name:
            centre_name = "Unknown Centre"
        # Find the data row — pure-integer line like "22 9 31" (maps · search · total).
        # The next line will be three WoW percentages. Skip percentage lines and
        # any line containing %, +, -, ., or labels.
        pure_int_line_re = re.compile(r"^\s*(\d+)\s+(\d+)\s+(\d+)\s*$")
        for idx, line in enumerate(lines):
            if any(skip in line for skip in ("Google", "Reach", "30 May", "%", "Care")):
                continue
            m = pure_int_line_re.match(line)
            if m:
                out["gbp"]["centres"][centre_name] = {
                    "google_maps_actions":   int(m.group(1)),
                    "google_search_actions": int(m.group(2)),
                    "total_actions":         int(m.group(3)),
                }
                # WoW row should be the next line
                if idx + 1 < len(lines):
                    pcts = re.findall(r"([+\-]\d+(?:\.\d+)?)%", lines[idx + 1])
                    if len(pcts) >= 3:
                        out["gbp"]["centres"][centre_name].update({
                            "google_maps_wow_pct":   _to_pct(pcts[0]),
                            "google_search_wow_pct": _to_pct(pcts[1]),
                            "total_wow_pct":         _to_pct(pcts[2]),
                        })
                break

    # ── GBP top keywords (page 47) ──────────────────────────────────────────
    if len(pages) >= 47:
        kw_text = pages[46]
        lines = [l.strip() for l in kw_text.split("\n") if l.strip()]
        keywords = []
        # Pattern: "<keyword phrase> <impressions>"
        for line in lines:
            if line in ("Keywords", "Impressions", "Reach distribution by source") or "Care" in line or "30 May" in line:
                continue
            m = re.match(r"^(.+?)\s+(\d+)$", line)
            if m:
                kw, impr = m.group(1).strip(), int(m.group(2))
                if impr > 0:
                    keywords.append({"keyword": kw, "impressions": impr})
        if keywords and out["gbp"]["centres"]:
            # Attach to the first centre
            first_centre = list(out["gbp"]["centres"].keys())[0]
            out["gbp"]["centres"][first_centre]["top_keywords"] = keywords[:10]

    # ── Coverage notes ──────────────────────────────────────────────────────
    if len(out["gbp"]["centres"]) < 5:
        out["notes"].append(
            f"Only {len(out['gbp']['centres'])} of 5 centres tracked in GBP — "
            f"connect remaining centres in Metricool for full coverage."
        )

    # ── Save ────────────────────────────────────────────────────────────────
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(out, indent=2, default=str))

    # Summary
    print(f"\n[metricool-mwcc] ✅ Saved → {OUTPUT_FILE.relative_to(BASE_DIR)}")
    if "summary" in out and out["summary"]:
        s = out["summary"]
        print(f"[metricool-mwcc] Period       : {out['date_range'].get('label', '–')}")
        if "followers" in s:
            print(f"[metricool-mwcc] Followers    : {s['followers'].get('total','–')} ({s['followers'].get('wow_pct','–')}% WoW)")
        if "impressions" in s:
            print(f"[metricool-mwcc] Impressions  : {s['impressions'].get('total','–')} ({s['impressions'].get('wow_pct','–')}% WoW)")
        if "interactions" in s:
            print(f"[metricool-mwcc] Interactions : {s['interactions'].get('total','–')} ({s['interactions'].get('wow_pct','–')}% WoW)")
        if "posts" in s:
            print(f"[metricool-mwcc] Posts        : {s['posts'].get('total','–')} ({s['posts'].get('wow_pct','–')}% WoW)")
    if out["gbp"]["centres"]:
        print(f"[metricool-mwcc] GBP centres  : {list(out['gbp']['centres'].keys())}")
    for note in out["notes"]:
        print(f"[metricool-mwcc] NOTE: {note}")

    return out


def main() -> int:
    pdf = _find_pdf()
    if not pdf:
        print(f"[metricool-mwcc] No metricool*.pdf found in {INBOX_DIR.relative_to(BASE_DIR)}/")
        print(f"[metricool-mwcc] Drop the Metricool PDF and re-run.")
        # Write an unavailable placeholder so the dashboard knows
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text(json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "brand": "mwcc",
            "available": False,
            "note": "No Metricool PDF in mwcc-inbox/. Drop one and re-run scripts/parse_mwcc_metricool_pdf.py",
        }, indent=2))
        return 0

    parse_metricool(pdf)
    return 0


if __name__ == "__main__":
    sys.exit(main())
