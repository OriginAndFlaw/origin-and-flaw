"""Pillow graphics: chapter title overlays and a thumbnail."""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

AMBER = (232, 168, 72)
CREAM = (238, 228, 210)


def _font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    names = (["georgiab.ttf", "DejaVuSerif-Bold.ttf", "NotoSerif-Bold.ttf"] if bold
             else ["georgiai.ttf", "DejaVuSerif-Italic.ttf", "NotoSerif-Italic.ttf"])
    dirs = [r"C:\Windows\Fonts", "/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/noto",
            os.path.join(os.path.dirname(__file__), "..", "assets", "fonts")]
    for d in dirs:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def chapter_overlay(number: int, title: str, dst: Path, w: int = 1920, h: int = 1080) -> Path:
    """Transparent PNG: small 'CHAPTER N' and the title, lower-left, with a soft dark band behind."""
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    band = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    # Top-left: the bottom of the frame belongs to the viewer's closed captions, which must never collide.
    ImageDraw.Draw(band).rectangle((0, int(h * 0.06), int(w * 0.62), int(h * 0.24)), fill=(0, 0, 0, 150))
    im = Image.alpha_composite(im, band.filter(ImageFilter.GaussianBlur(30)))
    d = ImageDraw.Draw(im)
    x = int(w * 0.06)
    d.text((x, int(h * 0.085)), f"CHAPTER {number}", font=_font(True, int(h * 0.028)), fill=AMBER)
    d.line((x, int(h * 0.13), x + int(w * 0.08), int(h * 0.13)), fill=AMBER, width=3)
    d.text((x, int(h * 0.145)), title, font=_font(True, int(h * 0.058)), fill=CREAM)
    im.save(dst)
    return dst


def callout(text: str, dst: Path, w: int = 1920, h: int = 1080) -> Path:
    """Transparent PNG: one big number or very short fact (e.g. "114", "60% -> 30%") in amber, upper right,
    away from the chapter card (upper left) and the viewer's captions (bottom). Numbers read in any language."""
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((int(w * 0.56), int(h * 0.04), int(w * 0.98), int(h * 0.46)), fill=(0, 0, 0, 120))
    im = Image.alpha_composite(im, glow.filter(ImageFilter.GaussianBlur(60)))
    d = ImageDraw.Draw(im)
    size = int(h * (0.16 if len(text) <= 6 else 0.10))
    font = _font(True, size)
    tw = d.textlength(text, font=font)
    x, y = int(w * 0.94 - tw), int(h * 0.12)
    d.text((x + 3, y + 4), text, font=font, fill=(0, 0, 0, 160))
    d.text((x, y), text, font=font, fill=AMBER)
    d.line((x, y + size + int(h * 0.025), x + min(tw, w * 0.2), y + size + int(h * 0.025)), fill=CREAM, width=4)
    im.save(dst)
    return dst


def thumbnail(still: Path, words: str, dst: Path) -> Path:
    """1280x720: the chosen still, darkened at the edges, 2-4 bold amber words on the left."""
    base = Image.open(still).convert("RGB").resize((1280, 720))
    base = ImageEnhance.Contrast(base).enhance(1.25)
    shade = Image.new("L", (1280, 720), 0)
    ImageDraw.Draw(shade).rectangle((0, 0, 700, 720), fill=170)
    base = Image.composite(Image.new("RGB", (1280, 720), (0, 0, 0)), base, shade.filter(ImageFilter.GaussianBlur(120)))
    d = ImageDraw.Draw(base)
    lines = words.upper().split()
    size = 150 if len(lines) <= 2 else 112
    y = 360 - len(lines) * size // 2
    for ln in lines:
        d.text((60, y), ln, font=_font(True, size), fill=AMBER, stroke_width=6, stroke_fill=(0, 0, 0))
        y += int(size * 1.05)
    base.save(dst, quality=92)
    return dst
