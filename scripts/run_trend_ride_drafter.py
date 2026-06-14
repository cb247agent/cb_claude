"""
run_trend_ride_drafter.py — Fires the trend-ride-drafter agent for each
pending org-social trend/adapt action.

DESIGN DECISION (14 Jun 2026)
    Originally shipped as scripts/run_trend_rides_only.sh which had the
    agent read state/work-queue.json directly via Read tool. Result: all
    3 drafts came out empty (0 bytes). Root cause: in --print mode, the
    agent printed nothing to stdout because its workflow expected to
    "Write" via tool — but stdout WAS the output channel, so files were
    blank.

    This rewrite embeds the action + trend data INLINE in the prompt, so
    the agent doesn't need to read state/. It only needs context/* and
    the CB_Brain knowledge base. The agent's output to stdout becomes
    the draft content directly.

INPUT
    state/work-queue.json    → action rows
    state/social-trends.json → hashtag scrape + top posts

OUTPUT
    outputs/trend-rides/{slug}.md → one full draft per pending action

INVOCATION
    python3 scripts/run_trend_ride_drafter.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CLAUDE_BIN = "/Users/tiachasingbetter/.local/bin/claude"
MODEL = os.environ.get("ANTHROPIC_DEFAULT_SONNET_MODEL", "claude-sonnet-4-5")

WORK_QUEUE = BASE_DIR / "state" / "work-queue.json"
SOCIAL_TRENDS = BASE_DIR / "state" / "social-trends.json"
OUT_DIR = BASE_DIR / "outputs" / "trend-rides"

TREND_VERB_RE = re.compile(r"^(Trend-ride|Adapt\s+high-engagement)", re.IGNORECASE)


def slugify(text: str, max_len: int = 60) -> str:
    s = (text or "").lower()
    s = re.sub(r"[^a-z0-9\s\-]", "", s)
    s = re.sub(r"\s+", "-", s.strip())
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:max_len].rstrip("-")


def load_actions() -> list[dict]:
    data = json.loads(WORK_QUEUE.read_text())
    items = data.get("items", data) if isinstance(data, dict) else data
    if isinstance(items, dict):
        items = list(items.values())
    return [i for i in items if isinstance(i, dict)]


def load_trends() -> dict:
    if not SOCIAL_TRENDS.exists():
        return {}
    return json.loads(SOCIAL_TRENDS.read_text())


def find_trend_context(action: dict, trends: dict) -> str:
    """Build a text snippet of the relevant trend data for this action."""
    title = action.get("title", "")
    is_adapt = title.lower().startswith("adapt")

    if is_adapt:
        # Try to match by engagement count in title
        m = re.search(r"(\d{2,})\s+engagement", title)
        target_eng = int(m.group(1)) if m else None
        top_posts = trends.get("top_posts", [])
        match = None
        if target_eng:
            for p in top_posts:
                if p.get("engagement") == target_eng:
                    match = p
                    break
        if match:
            return (
                f"Source post (TikTok) we're adapting:\n"
                f"  text: {match.get('text','')}\n"
                f"  likes: {match.get('likes')}  comments: {match.get('comments')}  "
                f"shares: {match.get('shares')}  plays: {match.get('plays')}\n"
                f"  source hashtags used: {', '.join(match.get('hashtags', []))}\n"
                f"  url: {match.get('url','')}\n"
            )
        return "Source post not found in social-trends.json (use title alone)."

    # Trend-ride — match by hashtag
    m = re.search(r"#(\w+)", title)
    tag = m.group(1).lower() if m else ""
    trending = trends.get("trending_hashtags", [])
    hit = next((t for t in trending if t.get("hashtag", "").lower() == tag), None)
    if hit:
        return (
            f"Trending hashtag: #{hit['hashtag']} — {hit.get('count')} hits "
            f"in this week's CB247 socials scrape ({trends.get('scraped','')[:10]}).\n"
        )
    return f"Hashtag #{tag} (no scrape detail found)."


def build_prompt(action: dict, trend_ctx: str, date_str: str) -> str:
    """Embed all the action+trend data into a self-contained prompt."""
    return f"""You are the CB247 Trend-Ride Drafter. Today is {date_str}.

YOUR JOB
Draft the FULL trend-ride for one org-social action so Joanne can schedule
+ post without writing copy from scratch. Output MUST include:
  1. Three caption variations (each ≤ 220 chars, distinct angles)
  2. A six-tag hashtag stack (mix of local + niche + trending, NO banned tags)
  3. A Shauna shot brief (only if no matching CB247 asset is likely; otherwise note "use existing asset")
  4. Best posting time + day (AWST)
  5. One sentence on which CB247 differentiator the post lands

ACTION
  id:          {action.get('id','')}
  title:       {action.get('title','')}
  source_page: {action.get('source_page','')}
  owner:       {action.get('owner','')}
  priority:    {action.get('priority','')}
  effort:      {action.get('effort','')}
  metric:      {action.get('metric','qualitative_assessment')}

TREND CONTEXT
{trend_ctx}

CB247 BRAND FACTS (MANDATORY)
- Price anchor: $11.95/wk, no lock-in
- Locations: Malaga + Ellenbrook (Perth, WA)
- Differentiators (use 1-2 per caption, never all): 24/7 access, Kids Hub,
  Traditional Sauna + Ice Bath, FIFO-friendly membership freeze, Reformer
  Pilates / ChasingRX / Recovery (PAID add-ons — NEVER bundle into $11.95)
- Tagline: AlwaysBetter

BANNED LANGUAGE (NEVER USE)
- "only gym with", "best gym", "burns fat", "detox", "heals", "cures",
  "guaranteed"
- Competitor names: Revo, Anytime, Snap, Ryderwear, Fitstop
- Bundling Recovery/Reformer/ChasingRX into $11.95

OUTPUT FORMAT
Output a single markdown document. Use this exact structure:

---
title: <action title>
action_id: {action.get('id','')}
source_page: organic-social
owner: Joanne (Organic Social)
drafted_at: {date_str}
format: trend-ride
---

# <Hook headline — 1 line, ≤80 chars>

## Caption Variations

### Variation A — <angle name>
<caption text ≤220 chars>

### Variation B — <angle name>
<caption text ≤220 chars>

### Variation C — <angle name>
<caption text ≤220 chars>

## Hashtag Stack
#tag1 #tag2 #tag3 #tag4 #tag5 #tag6

## Shot Brief (Shauna)
<3-5 sentence shot direction OR "Use existing asset: <description>">

## Posting Schedule
- Best day: <day>
- Best time: <HH:MM AWST>
- Platform: <Instagram/TikTok/both>

## Differentiator Landing
<1 sentence: which CB247 differentiator + why it fits this trend>

## Compliance Check
- [ ] No banned phrases
- [ ] No competitor names
- [ ] Recovery/Reformer/ChasingRX not bundled in $11.95
- [ ] Each caption ≤220 chars

BEGIN THE DRAFT NOW. Output ONLY the markdown document above — no preamble,
no explanation, no "Here is the draft:" intro.
"""


def run_one(action: dict, trends: dict, date_str: str) -> bool:
    slug = slugify(action.get("title", ""))
    if not slug:
        print(f"  skip — no slug for {action.get('id')}", file=sys.stderr)
        return False
    out_path = OUT_DIR / f"{slug}.md"
    if out_path.exists() and out_path.stat().st_size > 200:
        print(f"  skip — draft already exists: {out_path.name}", file=sys.stderr)
        return False

    trend_ctx = find_trend_context(action, trends)
    prompt = build_prompt(action, trend_ctx, date_str)

    print(f"  → {action['id']} ({slug[:50]}…) firing trend-ride-drafter [{MODEL}]", file=sys.stderr)
    proc = subprocess.run(
        [
            CLAUDE_BIN,
            "--allowedTools",
            "Read(context/**),Read(/Users/tiachasingbetter/Documents/ChasingBetter/CB_Brain/wiki/**)",
            "--model",
            MODEL,
            "--print",
            "--output-format",
            "text",
            prompt,
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    output = proc.stdout.strip()
    if proc.returncode != 0:
        print(f"  ✗ FAILED — exit={proc.returncode} stderr={proc.stderr[:200]}", file=sys.stderr)
        return False
    if len(output) < 200:
        print(f"  ✗ EMPTY/SHORT output — {len(output)} bytes. Preview: {output[:120]!r}", file=sys.stderr)
        return False
    out_path.write_text(output + "\n")
    print(f"  ✓ wrote {out_path.name} ({len(output)} chars)", file=sys.stderr)
    return True


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    actions = load_actions()
    trends = load_trends()
    date_str = datetime.now().strftime("%Y-%m-%d")

    pending = [
        a for a in actions
        if a.get("source_page") == "organic-social"
        and TREND_VERB_RE.match(str(a.get("title", "")).strip())
    ]
    print(f"[trend-ride-drafter] {len(pending)} pending action(s)", file=sys.stderr)

    ok = 0
    for action in pending:
        if run_one(action, trends, date_str):
            ok += 1

    print(f"[trend-ride-drafter] {ok}/{len(pending)} draft(s) written", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
