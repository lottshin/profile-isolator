"""
iOS-style app icon for Profile Isolator.
Minimal rounded square + soft system-blue gradient + stacked profile cards.
No vertical bar (too easy to misread).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


def render_master(size: int = 1024) -> Image.Image:
    s = size
    scale = 4
    b = s * scale
    # iOS continuous corner ~22.37%
    r = int(b * 0.2237)

    # Soft blue → indigo gradient
    base = Image.new("RGBA", (b, b), (0, 0, 0, 0))
    px = base.load()
    top = (96, 172, 255, 255)
    bot = (52, 98, 224, 255)
    for y in range(b):
        t = y / max(b - 1, 1)
        t = t * t * (3 - 2 * t)
        col = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(4))
        for x in range(b):
            dx = x / max(b - 1, 1)
            lift = int(7 * max(0.0, 1 - abs(dx - 0.38) * 1.8))
            c = (
                min(255, col[0] + lift),
                min(255, col[1] + lift),
                min(255, col[2] + max(0, lift // 2)),
                255,
            )
            px[x, y] = c

    # Soft top specular
    hi = Image.new("RGBA", (b, b), (0, 0, 0, 0))
    hpx = hi.load()
    band = int(b * 0.42)
    for y in range(band):
        ty = y / max(band - 1, 1)
        a = int((1 - ty) ** 2.4 * 34)
        for x in range(b):
            cx = abs(x / b - 0.5) * 2
            aa = int(a * max(0.0, 1 - cx * 0.65))
            if aa:
                hpx[x, y] = (255, 255, 255, aa)
    base = Image.alpha_composite(base, hi)

    tile = Image.new("RGBA", (b, b), (0, 0, 0, 0))
    mask = Image.new("L", (b, b), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, b - 1, b - 1], radius=r, fill=255)
    tile.paste(base, (0, 0), mask)

    # Glyph: two offset rounded cards = profiles / isolation (clean, no vertical bar)
    g = Image.new("RGBA", (b, b), (0, 0, 0, 0))
    d = ImageDraw.Draw(g)
    cx, cy = b // 2, int(b * 0.50)

    # Back card (smaller, offset up-left, lower opacity)
    def card(cx_, cy_, wf, hf, rf, fill_a, outline_a, dx=0, dy=0):
        w, h = int(b * wf), int(b * hf)
        x0 = cx_ - w // 2 + int(b * dx)
        y0 = cy_ - h // 2 + int(b * dy)
        rr = int(b * rf)
        d.rounded_rectangle(
            [x0, y0, x0 + w, y0 + h],
            radius=rr,
            fill=(255, 255, 255, fill_a),
        )
        d.rounded_rectangle(
            [x0, y0, x0 + w, y0 + h],
            radius=rr,
            outline=(255, 255, 255, outline_a),
            width=max(2, b // 160),
        )
        return x0, y0, w, h

    # Layered profile sheets
    card(cx, cy, 0.42, 0.34, 0.09, 70, 100, dx=-0.05, dy=-0.06)
    card(cx, cy, 0.48, 0.38, 0.10, 120, 150, dx=0.00, dy=-0.01)
    x0, y0, w, h = card(cx, cy, 0.52, 0.40, 0.105, 235, 255, dx=0.04, dy=0.05)

    # Front-card content: three soft horizontal lines (list / profiles)
    # Reads as UI list, not a bar
    line_left = x0 + int(w * 0.18)
    line_right = x0 + int(w * 0.82)
    line_h = max(3, b // 90)
    gap = int(h * 0.16)
    start_y = y0 + int(h * 0.34)
    for i in range(3):
        yy = start_y + i * gap
        # shorter last line for list rhythm
        rr = line_right if i < 2 else x0 + int(w * 0.62)
        d.rounded_rectangle(
            [line_left, yy, rr, yy + line_h],
            radius=line_h,
            fill=(52, 98, 224, 150 if i == 0 else 110),
        )

    g = g.filter(ImageFilter.GaussianBlur(radius=max(0.35, b / 1000)))
    tile = Image.alpha_composite(tile, g)

    # Hairline rim
    d2 = ImageDraw.Draw(tile)
    d2.rounded_rectangle(
        [0, 0, b - 1, b - 1],
        radius=r,
        outline=(255, 255, 255, 42),
        width=max(2, b // 200),
    )

    return tile.resize((s, s), Image.Resampling.LANCZOS)


def main() -> None:
    root = Path(__file__).resolve().parent
    icons = root / "src-tauri" / "icons"
    icons.mkdir(parents=True, exist_ok=True)

    master = render_master(1024)
    master.save(icons / "icon.png")
    master.resize((32, 32), Image.Resampling.LANCZOS).save(icons / "32x32.png")
    master.resize((128, 128), Image.Resampling.LANCZOS).save(icons / "128x128.png")
    master.resize((256, 256), Image.Resampling.LANCZOS).save(icons / "128x128@2x.png")

    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    imgs = [master.resize(sz, Image.Resampling.LANCZOS) for sz in sizes]
    imgs[-1].save(icons / "icon.ico", format="ICO", sizes=sizes, append_images=imgs[:-1])
    master.resize((512, 512), Image.Resampling.LANCZOS).save(icons / "icon.icns")

    assets = root.parent / "app" / "assets"
    if assets.is_dir():
        master.save(assets / "app.png")
        imgs[-1].save(assets / "app.ico", format="ICO", sizes=sizes, append_images=imgs[:-1])

    print("icons written:", icons)
    print("preview:", icons / "icon.png")


if __name__ == "__main__":
    main()
