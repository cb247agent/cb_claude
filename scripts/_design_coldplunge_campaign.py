"""
_design_coldplunge_campaign.py — one-off campaign-poster overlay matching
the "Your 7-Day Upgrade Is Still Waiting" layout style: sticker-logo top-
left, massive white Impact headline, smaller sub-line, teal CTA bar at
bottom. Applied to the v7 ice bath background.

OUTPUTS
    docs/Image/social-posts/coldplunge-campaign-v1-feed.jpg   (1080x1350)
    docs/Image/social-posts/coldplunge-campaign-v1-story.jpg  (1080x1920)
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE_DIR = Path(__file__).resolve().parent.parent
BG_PATH    = BASE_DIR / "docs" / "Image" / "social-posts" / "coldplunge-i2i-v7-real-ice-opaque-tub.jpg"
LOGO_PATH  = BASE_DIR / "Image" / "ChasingBetterGym_small_logo.jpeg"
OUT_DIR    = BASE_DIR / "docs" / "Image" / "social-posts"

# Brand palette (teal-only per design-standards.md — no pink)
TEAL       = (63, 166, 154)
TEAL_DEEP  = (45, 125, 114)
WHITE      = (255, 255, 255)
BLACK      = (26, 26, 26)

FONT_HEAVY   = "/System/Library/Fonts/Supplemental/Impact.ttf"
FONT_BOLD    = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_ITALIC  = "/System/Library/Fonts/Supplemental/Arial Italic.ttf"


def _f(p, s):
    try: return ImageFont.truetype(p, s)
    except OSError: return ImageFont.load_default()


def _cover(img, w, h):
    sw, sh = img.size
    sr, tr = sw/sh, w/h
    if sr > tr:
        nh, nw = h, round(sw * (h/sh))
    else:
        nw, nh = w, round(sh * (w/sw))
    img = img.resize((nw, nh), Image.LANCZOS)
    return img.crop(((nw-w)//2, (nh-h)//2, (nw-w)//2 + w, (nh-h)//2 + h))


def _shadow_text(draw, xy, text, font, fill=WHITE, blur=6):
    """Headline with a soft drop shadow so it reads on any background."""
    x, y = xy
    shadow_layer = Image.new("RGBA", draw.im.size if hasattr(draw, "im") else (0,0), (0,0,0,0))
    # Simpler: draw multiple offset blacks then white on top
    for ox, oy in [(4,4), (3,3), (2,2)]:
        draw.text((x+ox, y+oy), text, font=font, fill=(0,0,0,220))
    draw.text(xy, text, font=font, fill=fill)


def _paste_logo(canvas, x, y, max_w=200):
    if not LOGO_PATH.exists():
        return
    logo = Image.open(LOGO_PATH).convert("RGBA")
    r = max_w / logo.width
    logo = logo.resize((max_w, round(logo.height * r)), Image.LANCZOS)
    # White rounded "sticker" backing card (like the reference)
    pad = 12
    card = Image.new("RGBA", (logo.width + pad*2, logo.height + pad*2), (255,255,255,255))
    # Slight rotation to feel sticker-like (-2 deg)
    card_canvas = Image.new("RGBA", card.size, (0,0,0,0))
    card_canvas.paste(card, (0,0), card)
    card_canvas.paste(logo, (pad, pad), logo)
    card_canvas = card_canvas.rotate(-3, resample=Image.BICUBIC, expand=True)
    canvas.paste(card_canvas, (x, y), card_canvas)


def _gradient_overlay_full(width, height, top_a=80, bottom_a=200):
    """Vertical dark gradient over the whole image for text contrast."""
    o = Image.new("RGBA", (width, height), (0,0,0,0))
    d = ImageDraw.Draw(o)
    for y in range(height):
        a = round(top_a + (bottom_a - top_a) * (y / height))
        d.rectangle([(0,y),(width,y+1)], fill=(0,0,0,a))
    return o


def _wrap(text, font, max_w):
    words, lines, cur = text.split(), [], []
    for w in words:
        t = (" ".join(cur + [w])).strip()
        bb = font.getbbox(t)
        if bb[2]-bb[0] <= max_w: cur.append(w)
        else:
            if cur: lines.append(" ".join(cur))
            cur = [w]
    if cur: lines.append(" ".join(cur))
    return lines


def _render(width, height, headline, sub, cta_main, cta_sub, story=False):
    bg = Image.open(BG_PATH).convert("RGB")
    bg = _cover(bg, width, height)
    canvas = bg.convert("RGBA")

    # Heavy gradient overlay so the white headline pops
    canvas.alpha_composite(_gradient_overlay_full(width, height, top_a=70, bottom_a=190))

    draw = ImageDraw.Draw(canvas)

    # Logo top-left (sticker style)
    _paste_logo(canvas, x=44, y=44, max_w=190 if not story else 230)

    # Headline — massive Impact, white, slightly italicised feel via Impact
    head_size = 160 if not story else 200
    head_font = _f(FONT_HEAVY, head_size)
    head_lines = _wrap(headline.upper(), head_font, width - 96)
    # Start headline at ~28% from top so the logo sits clear above
    y = round(height * (0.24 if not story else 0.20))
    for line in head_lines:
        bb = head_font.getbbox(line)
        x = 48
        # re-create draw to ensure shadows work on alpha canvas
        d2 = ImageDraw.Draw(canvas)
        for ox, oy in [(5,5),(3,3)]:
            d2.text((x+ox, y+oy), line, font=head_font, fill=(0,0,0,200))
        d2.text((x, y), line, font=head_font, fill=WHITE)
        y += (bb[3]-bb[1]) + 14

    # Sub-line (smaller, white, bold)
    sub_font = _f(FONT_BOLD, 52 if not story else 60)
    sub_lines = _wrap(sub, sub_font, width - 96)
    y += 18
    d2 = ImageDraw.Draw(canvas)
    for line in sub_lines:
        bb = sub_font.getbbox(line)
        for ox, oy in [(3,3)]:
            d2.text((48+ox, y+oy), line, font=sub_font, fill=(0,0,0,200))
        d2.text((48, y), line, font=sub_font, fill=WHITE)
        y += (bb[3]-bb[1]) + 10

    # CTA bar near bottom — teal
    bar_h = 170 if not story else 200
    bar_y = height - bar_h - (50 if not story else 130)
    pad_x = 60
    draw.rectangle([(pad_x, bar_y), (width-pad_x, bar_y+bar_h)], fill=TEAL)
    # CTA main
    cta_font = _f(FONT_HEAVY, 60 if not story else 72)
    bb = cta_font.getbbox(cta_main.upper())
    cx = (width - (bb[2]-bb[0]))//2
    cy = bar_y + (bar_h - (bb[3]-bb[1]))//2 - 16
    draw.text((cx, cy), cta_main.upper(), font=cta_font, fill=WHITE)
    # CTA sub
    cta_sub_font = _f(FONT_ITALIC, 28 if not story else 34)
    bb = cta_sub_font.getbbox(cta_sub)
    cx = (width - (bb[2]-bb[0]))//2
    cy = bar_y + bar_h - (bb[3]-bb[1]) - 22
    draw.text((cx, cy), cta_sub, font=cta_sub_font, fill=(255,255,255,230))

    return canvas.convert("RGB")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    headline = "3 MIN ICE BATH"
    sub      = "> 30 min scrolling"
    cta_main = "Visit Malaga + Ellenbrook"
    cta_sub  = "Sauna + ice bath in your membership"

    feed = _render(1080, 1350, headline, sub, cta_main, cta_sub, story=False)
    feed_p = OUT_DIR / "coldplunge-campaign-v1-feed.jpg"
    feed.save(feed_p, "JPEG", quality=90, optimize=True)
    print(f"  → {feed_p.relative_to(BASE_DIR)} ({feed_p.stat().st_size // 1024} KB)")

    story = _render(1080, 1920, headline, sub, cta_main, cta_sub, story=True)
    story_p = OUT_DIR / "coldplunge-campaign-v1-story.jpg"
    story.save(story_p, "JPEG", quality=90, optimize=True)
    print(f"  → {story_p.relative_to(BASE_DIR)} ({story_p.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
