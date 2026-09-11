"""Optional property-address card. Never burn an AI watermark."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from photomotion.constants import FONT_SANS, MASTER_H, MASTER_W


def _font(path: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def write_address_card(dest: Path, address: str, city: str) -> Path:
    """Reel-E-style open: address + city, left lower-third, no product lockup."""
    img = Image.new("RGBA", (MASTER_W, MASTER_H), (0, 0, 0, 0))
    grad_h = 240
    grad = Image.new("RGBA", (MASTER_W, grad_h), (0, 0, 0, 0))
    pixels = grad.load()
    for y in range(grad_h):
        alpha = int(150 * ((y / max(1, grad_h - 1)) ** 1.35))
        for x in range(MASTER_W):
            pixels[x, y] = (11, 14, 16, alpha)
    img.paste(grad, (0, MASTER_H - grad_h), grad)
    draw = ImageDraw.Draw(img)
    sans = _font(FONT_SANS, 48)
    small = _font(FONT_SANS, 22)
    x, y = 72, MASTER_H - 168
    draw.rectangle((x, y, x + 56, y + 3), fill=(153, 204, 255, 240))
    draw.text((x, y + 18), address.strip(), font=sans, fill=(247, 248, 250, 255))
    if city.strip():
        draw.text((x, y + 80), city.strip(), font=small, fill=(201, 194, 178, 230))
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest)
    return dest
