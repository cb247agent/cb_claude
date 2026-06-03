#!/usr/bin/env python3
"""
CB247 Adjustment Server
=======================
Listens on localhost:5055 for adjustment requests from the Content Planner.
When an adjustment is received, it reads the target blog draft, applies
the changes using Claude AI, saves the file, and pushes to GitHub.

Run with:
    python scripts/adjustment-server.py

Leave it running in a terminal while using the Content Planner dashboard.
"""

import re
import subprocess
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS
import anthropic

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE     = Path(__file__).resolve().parent.parent
BLOG_DIR = BASE / "docs" / "blog-drafts"

app = Flask(__name__)
CORS(app)  # Allow requests from GitHub Pages + localhost


# ── Helpers ────────────────────────────────────────────────────────────────────

def url_to_path(draft_url: str) -> Path | None:
    """Map a GitHub Pages URL to the local blog draft HTML file."""
    # https://cb247agent.github.io/cb_claude/blog-drafts/best-gym-malaga.html
    # → docs/blog-drafts/best-gym-malaga.html
    m = re.search(r"/blog-drafts/([^?#]+\.html)", draft_url or "")
    if not m:
        return None
    return BLOG_DIR / m.group(1)


def strip_fences(text: str) -> str:
    """Remove markdown code fences if Claude wraps the response in them."""
    text = re.sub(r"^```html?\s*\n?", "", text.strip())
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "CB247 Adjustment Server"})


@app.post("/apply-adjustment")
def apply_adjustment():
    data  = request.get_json(force=True) or {}
    notes = (data.get("notes") or "").strip()
    url   = (data.get("draftLink") or "").strip()
    title = (data.get("title") or "item").strip()

    if not notes:
        return jsonify({"error": "No adjustment notes provided"}), 400

    local_path = url_to_path(url)
    if not local_path:
        return jsonify({"error": f"Could not resolve draft URL: {url}"}), 400
    if not local_path.exists():
        return jsonify({"error": f"Draft file not found locally: {local_path.name}"}), 404

    # ── Read current draft ─────────────────────────────────────────────────────
    original_html = local_path.read_text(encoding="utf-8")

    # ── Call Claude to apply the adjustment ───────────────────────────────────
    client = anthropic.Anthropic()   # reads ANTHROPIC_API_KEY from environment

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=8096,
        messages=[{
            "role": "user",
            "content": (
                "You are editing a blog draft HTML file for CB247 (ChasingBetter247) "
                "gym in Perth, WA. The content team has requested the following adjustment:\n\n"
                f"ADJUSTMENT REQUESTED:\n{notes}\n\n"
                "Instructions:\n"
                "- Apply ONLY what the adjustment asks for. Do not rewrite anything else.\n"
                "- Keep all HTML structure, CSS styles, JavaScript, metadata, images, "
                "and internal links exactly as they are.\n"
                "- Preserve the doctor disclaimer, compliance flags, and source citations.\n"
                "- Return the complete updated HTML file — nothing else. No explanation, "
                "no markdown code fences, just the raw HTML.\n\n"
                f"CURRENT HTML FILE:\n{original_html}"
            )
        }]
    )

    updated_html = strip_fences(message.content[0].text)

    # ── Save updated file ──────────────────────────────────────────────────────
    local_path.write_text(updated_html, encoding="utf-8")

    # ── Commit + push to GitHub ────────────────────────────────────────────────
    short_note = notes[:80].replace('"', "'")
    short_title = title[:50]

    subprocess.run(["git", "add", str(local_path)], cwd=BASE, check=True)
    subprocess.run(
        ["git", "commit", "-m", f"Auto-adjustment: {short_title} — {short_note}"],
        cwd=BASE, check=True
    )
    subprocess.run(["git", "push", "origin", "main"], cwd=BASE, check=True)

    return jsonify({
        "ok": True,
        "file": local_path.name,
        "message": f"Applied and pushed: {local_path.name}"
    })


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print()
    print("  CB247 Adjustment Server")
    print("  ─────────────────────────────────────────────")
    print("  Listening on  http://localhost:5055")
    print("  Health check: http://localhost:5055/health")
    print()
    print("  Leave this running while using the Content Planner.")
    print("  Adjustments saved in the modal will be auto-applied.")
    print()
    app.run(host="127.0.0.1", port=5055, debug=False)
