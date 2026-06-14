"""
generate_social_image.py — Call Replicate (Flux Schnell) to generate a
polished social-media image from a text prompt. Downloads the result to
docs/Image/social-posts/{slug}.jpg.

WHY THIS EXISTS (14 Jun 2026)
    Tia tried Path B (auto-design with Pillow over the existing photo)
    and didn't like the polish. Path A — generate a fully AI image from
    a prompt — is the alternative. Costs ~$0.003 per image via
    Replicate's Flux Schnell.

    Trade-off: the result is a CONCEPT / lifestyle visual, not the
    actual CB247 facility. Use only when authenticity is less important
    than polish (e.g., teaser posts, ambient content, story backgrounds).

INPUT
    .env  → REPLICATE_API_TOKEN (must be set)
    CLI   → --prompt, --slug, optional --aspect

OUTPUT
    docs/Image/social-posts/{slug}.jpg

CLI
    python scripts/generate_social_image.py \\
        --prompt "Cinematic close-up of an ice bath at a modern gym..." \\
        --slug coldplunge-ai-2026-06-14 \\
        --aspect 4:5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "docs" / "Image" / "social-posts"

# Default text-to-image: Flux Schnell — fast + cheap (~$0.003/image)
MODEL_T2I = "black-forest-labs/flux-schnell"
# Image-to-image (edits an existing photo per a prompt) — flux-kontext-pro,
# ~$0.04/image. Keeps structure + identity of the source, applies prompt
# as a stylistic / atmospheric edit. Use when authenticity matters.
MODEL_I2I = "black-forest-labs/flux-kontext-pro"
API_URL = "https://api.replicate.com/v1/models/{model}/predictions"

ASPECT_MAP = {
    "1:1":  "1:1",
    "4:5":  "4:5",   # IG feed portrait
    "9:16": "9:16",  # IG story / Reel
    "16:9": "16:9",  # YouTube / cinematic
    "match_input_image": "match_input_image",  # Kontext: preserve source ratio
}


def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return env
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def _post(url: str, body: dict, token: str) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
            "Prefer":        "wait=60",   # block server-side up to 60s
        },
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def _get(url: str, token: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def _download(url: str, dest: Path) -> int:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    dest.write_bytes(data)
    return len(data)


def _data_uri(path: Path) -> str:
    """Base64-encode an image file as a data: URI for Replicate input."""
    import base64
    ext = path.suffix.lower().lstrip(".")
    if ext in ("jpg", "jpeg"):
        mime = "image/jpeg"
    elif ext == "png":
        mime = "image/png"
    elif ext == "webp":
        mime = "image/webp"
    else:
        mime = "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def generate(prompt: str, slug: str, aspect: str = "4:5", source_image: str | None = None) -> Path:
    """Generate a social image. If source_image is given, runs image-to-image
    (flux-kontext-pro) over that source. Otherwise runs text-to-image (flux-schnell)."""
    env = _load_env()
    token = env.get("REPLICATE_API_TOKEN") or os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        raise RuntimeError("REPLICATE_API_TOKEN not set in .env")
    if aspect not in ASPECT_MAP:
        raise ValueError(f"aspect must be one of {list(ASPECT_MAP)}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUT_DIR / f"{slug}.jpg"

    if source_image:
        src_path = BASE_DIR / source_image
        if not src_path.exists():
            raise RuntimeError(f"source_image not found: {src_path}")
        # flux-kontext-pro input shape — preserves source structure
        body = {
            "input": {
                "prompt":             prompt,
                "input_image":        _data_uri(src_path),
                "aspect_ratio":       ASPECT_MAP[aspect],
                "output_format":      "jpg",
                "safety_tolerance":   2,
            }
        }
        model = MODEL_I2I
    else:
        # Pure text-to-image
        body = {
            "input": {
                "prompt":         prompt,
                "aspect_ratio":   ASPECT_MAP[aspect],
                "num_outputs":    1,
                "output_format":  "jpg",
                "output_quality": 90,
                "go_fast":        True,
            }
        }
        model = MODEL_T2I

    url = API_URL.format(model=model)
    print(f"  → {model} (aspect={aspect}{' · img2img' if source_image else ''})", file=sys.stderr)
    print(f"  → prompt: {prompt[:120]}{'…' if len(prompt) > 120 else ''}", file=sys.stderr)
    resp = _post(url, body, token)

    # Poll until completed (the Prefer:wait=60 header usually lands a
    # finished response on first call for Flux Schnell, but we handle
    # the longer path too)
    pred_id = resp.get("id", "?")
    status = resp.get("status")
    deadline = time.time() + 120
    while status in ("starting", "processing") and time.time() < deadline:
        time.sleep(2)
        resp = _get(f"https://api.replicate.com/v1/predictions/{pred_id}", token)
        status = resp.get("status")

    if status != "succeeded":
        raise RuntimeError(f"Replicate prediction {pred_id} failed: status={status} err={resp.get('error')!r}")

    output = resp.get("output")
    img_url = output[0] if isinstance(output, list) else output
    if not img_url:
        raise RuntimeError(f"No output URL in response: {resp}")

    size = _download(img_url, dest)
    metrics = resp.get("metrics", {})
    elapsed = metrics.get("predict_time", "?")
    print(f"  ✓ saved {dest.relative_to(BASE_DIR)} ({size // 1024} KB · {elapsed}s predict)", file=sys.stderr)
    return dest


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--prompt", required=True, help="Image generation prompt")
    p.add_argument("--slug", required=True, help="Output filename slug (no extension)")
    p.add_argument("--aspect", default="4:5", choices=list(ASPECT_MAP), help="Aspect ratio")
    p.add_argument("--source-image", default=None, help="Path to source image (relative to repo root). If given, runs img2img via flux-kontext-pro.")
    args = p.parse_args()
    try:
        generate(args.prompt, args.slug, args.aspect, args.source_image)
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
