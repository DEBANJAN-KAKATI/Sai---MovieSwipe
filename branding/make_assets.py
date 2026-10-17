"""Generate every sai icon/logo asset from branding/sai-logo-source.png.

    .venv/Scripts/python branding/make_assets.py

The source is a mockup (wordmark on a dark rounded tile with a soft shadow), so the wordmark is cut out onto a
transparent background first and every asset is rebuilt from that — no mockup shadow in any icon.

Outputs
  frontend/public/   sai-wordmark.png, favicon.png, favicon-32.png, apple-touch-icon.png, icon-192.png,
                     icon-512.png, icon-maskable-512.png
  frontend/android/app/src/main/res/
                     mipmap-*/ic_launcher.png, ic_launcher_round.png, ic_launcher_foreground.png
                     drawable*/splash.png
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "branding" / "sai-logo-source.png"
PUBLIC = ROOT / "frontend" / "public"
RES = ROOT / "frontend" / "android" / "app" / "src" / "main" / "res"

TILE = (10, 10, 10, 255)  # icon background (matches the logo's tile)
APP_BG = (11, 11, 18, 255)  # app background, used for splash screens


def wordmark() -> Image.Image:
    """The cream/red 'sai' mark on a transparent background, tightly cropped."""
    src = Image.open(SOURCE).convert("RGB")
    lum = src.convert("L").point(lambda v: 255 if v > 90 else 0)
    left, top, right, bottom = lum.getbbox()
    pad = 6
    crop = src.crop((left - pad, top - pad, right + pad, bottom + pad))
    # Alpha from brightness: the tile is ~8-14, the mark is 235-255. Then un-premultiply so edges keep their colour.
    r, g, b = crop.split()
    brightest = ImageChops.lighter(ImageChops.lighter(r, g), b)
    alpha = brightest.point(lambda v: 0 if v <= 22 else 255 if v >= 200 else int((v - 22) * 255 / 178))
    px = crop.load()
    ap = alpha.load()
    out = Image.new("RGBA", crop.size)
    op = out.load()
    for y in range(crop.height):
        for x in range(crop.width):
            a = ap[x, y]
            if a == 0:
                op[x, y] = (0, 0, 0, 0)
                continue
            cr, cg, cb = px[x, y]
            k = 255 / a
            op[x, y] = (min(255, int(cr * k)), min(255, int(cg * k)), min(255, int(cb * k)), a)
    return out


def place(canvas: Image.Image, mark: Image.Image, width_frac: float, dy_frac: float = 0.0) -> Image.Image:
    w = round(canvas.width * width_frac)
    h = round(mark.height * w / mark.width)
    m = mark.resize((w, h), Image.LANCZOS)
    x = (canvas.width - w) // 2
    y = (canvas.height - h) // 2 + round(canvas.height * dy_frac)
    canvas.alpha_composite(m, (x, y))
    return canvas


def rounded_mask(size: int, radius_frac: float) -> Image.Image:
    scale = 4
    big = Image.new("L", (size * scale, size * scale), 0)
    ImageDraw.Draw(big).rounded_rectangle(
        (0, 0, size * scale - 1, size * scale - 1), radius=int(size * scale * radius_frac), fill=255
    )
    return big.resize((size, size), Image.LANCZOS)


def circle_mask(size: int) -> Image.Image:
    scale = 4
    big = Image.new("L", (size * scale, size * scale), 0)
    ImageDraw.Draw(big).ellipse((0, 0, size * scale - 1, size * scale - 1), fill=255)
    return big.resize((size, size), Image.LANCZOS)


def tile_icon(size: int, mark: Image.Image, width_frac: float, shape: str = "square", radius: float = 0.22) -> Image.Image:
    canvas = place(Image.new("RGBA", (size, size), TILE), mark, width_frac)
    if shape == "square":
        return canvas
    mask = circle_mask(size) if shape == "circle" else rounded_mask(size, radius)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(canvas, (0, 0), mask)
    return out


def main() -> None:
    mark = wordmark()
    PUBLIC.mkdir(parents=True, exist_ok=True)

    # ---- web
    wm = mark.copy()
    wm.thumbnail((360, 360), Image.LANCZOS)
    wm.save(PUBLIC / "sai-wordmark.png", optimize=True)
    tile_icon(64, mark, 0.80, "rounded", 0.24).save(PUBLIC / "favicon.png", optimize=True)
    tile_icon(32, mark, 0.86, "rounded", 0.24).save(PUBLIC / "favicon-32.png", optimize=True)
    tile_icon(180, mark, 0.64).convert("RGB").save(PUBLIC / "apple-touch-icon.png", optimize=True)
    tile_icon(192, mark, 0.64, "rounded", 0.22).save(PUBLIC / "icon-192.png", optimize=True)
    tile_icon(512, mark, 0.64, "rounded", 0.22).save(PUBLIC / "icon-512.png", optimize=True)
    tile_icon(512, mark, 0.50).convert("RGB").save(PUBLIC / "icon-maskable-512.png", optimize=True)

    # ---- android launcher icons
    densities = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}
    for name, k in densities.items():
        folder = RES / f"mipmap-{name}"
        folder.mkdir(parents=True, exist_ok=True)
        legacy = round(48 * k)
        tile_icon(legacy, mark, 0.66, "rounded", 0.2).save(folder / "ic_launcher.png", optimize=True)
        tile_icon(legacy, mark, 0.60, "circle").save(folder / "ic_launcher_round.png", optimize=True)
        # Adaptive foreground: 108dp canvas, mark kept inside the 66dp safe zone.
        fg_size = round(108 * k)
        place(Image.new("RGBA", (fg_size, fg_size), (0, 0, 0, 0)), mark, 0.58).save(
            folder / "ic_launcher_foreground.png", optimize=True
        )

    # ---- android splash screens (same sizes as the Capacitor template)
    for splash in RES.glob("drawable*/splash.png"):
        w, h = Image.open(splash).size
        canvas = Image.new("RGBA", (w, h), APP_BG)
        side = min(w, h)
        mw = round(side * 0.42)
        m = mark.resize((mw, round(mark.height * mw / mark.width)), Image.LANCZOS)
        canvas.alpha_composite(m, ((w - m.width) // 2, (h - m.height) // 2))
        canvas.convert("RGB").save(splash, optimize=True)

    print(f"wordmark {mark.size}; web icons in {PUBLIC}; Android icons + splash screens in {RES}")


if __name__ == "__main__":
    main()
