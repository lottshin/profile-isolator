"""
Premium icon for Codex Profile Isolator.
Direction: Linear / Raycast / Arc — dark, precise, restrained.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


def render_master(size: int = 1024) -> Image.Image:
    s = size
    out = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    # Supersample tile
    scale = 4
    pad = int(s * 0.06)
    ts = s - pad * 2
    b = ts * scale
    r = int(s * 0.22 * scale)

    # ---- Deep void tile ----
    tile = Image.new("RGBA", (b, b), (0, 0, 0, 0))
    base = Image.new("RGBA", (b, b), (0, 0, 0, 0))
    px = base.load()
    # charcoal-navy gradient: rich but not muddy
    top = (24, 28, 42, 255)
    bot = (10, 12, 20, 255)
    for y in range(b):
        t = y / max(b - 1, 1)
        t = t * t * (3 - 2 * t)
        col = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(4))
        for x in range(b):
            px[x, y] = col

    # single soft highlight — top edge only, very controlled
    hi = Image.new("RGBA", (b, b), (0, 0, 0, 0))
    hpx = hi.load()
    band = int(b * 0.38)
    for y in range(band):
        ty = y / max(band - 1, 1)
        a = int((1 - ty) ** 2.2 * 22)
        for x in range(b):
            # horizontal falloff from center-top
            cx = abs(x / b - 0.5) * 2
            aa = int(a * max(0, 1 - cx * 0.55))
            if aa:
                hpx[x, y] = (160, 185, 255, aa)
    base = Image.alpha_composite(base, hi)

    mask = Image.new("L", (b, b), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, b - 1, b - 1], radius=r, fill=255)
    tile.paste(base, (0, 0), mask)

    d = ImageDraw.Draw(tile)
    # ultra-thin luminous rim
    d.rounded_rectangle(
        [0, 0, b - 1, b - 1],
        radius=r,
        outline=(170, 190, 255, 32),
        width=max(2, b // 160),
    )

    # ---- Symbol: concentric rounded frames = isolated profiles ----
    # Large negative space = expensive look
    cx, cy = b // 2, int(b * 0.50)
    # outer frame
    w1, h1 = int(b * 0.48), int(b * 0.36)
    # middle
    w2, h2 = int(b * 0.36), int(b * 0.26)
    # inner solid
    w3, h3 = int(b * 0.22), int(b * 0.16)
    rr1 = int(b * 0.08)
    rr2 = int(b * 0.065)
    rr3 = int(b * 0.05)
    sw = max(3, b // 48)  # stroke weight

    def frame(w, h, rad, outline, width, fill=None):
        x0, y0 = cx - w // 2, cy - h // 2
        d.rounded_rectangle(
            [x0, y0, x0 + w, y0 + h],
            radius=rad,
            outline=outline,
            width=width,
            fill=fill,
        )
        return x0, y0, x0 + w, y0 + h

    # Outer ice ring
    frame(w1, h1, rr1, (120, 160, 230, 160), sw)
    # Middle ring — slightly offset down-right for depth (isolation stack)
    ox, oy = int(b * 0.018), int(b * 0.018)
    x0 = cx - w2 // 2 + ox
    y0 = cy - h2 // 2 + oy
    d.rounded_rectangle(
        [x0, y0, x0 + w2, y0 + h2],
        radius=rr2,
        outline=(150, 185, 255, 200),
        width=sw,
    )
    # Inner filled plate
    x0 = cx - w3 // 2 + ox * 2
    y0 = cy - h3 // 2 + oy * 2
    d.rounded_rectangle(
        [x0, y0, x0 + w3, y0 + h3],
        radius=rr3,
        fill=(36, 48, 78, 255),
        outline=(186, 210, 255, 220),
        width=max(2, sw - 1),
    )

    # Accent: single vertical mint tick (active profile) — jewelry-like
    tick_w = max(3, b // 55)
    tick_h = int(h3 * 0.45)
    tx = x0 + int(w3 * 0.22)
    ty = y0 + (h3 - tick_h) // 2
    d.rounded_rectangle(
        [tx, ty, tx + tick_w, ty + tick_h],
        radius=tick_w // 2,
        fill=(52, 211, 153, 255),
    )

    # Micro diamond / node on the right of inner plate
    rr = max(3, b // 70)
    nx = x0 + int(w3 * 0.72)
    ny = y0 + h3 // 2
    d.ellipse([nx - rr, ny - rr, nx + rr, ny + rr], fill=(125, 211, 252, 255))

    tile_s = tile.resize((ts, ts), Image.Resampling.LANCZOS)
    out.paste(tile_s, (pad, pad), tile_s)
    return out


def render_small(size: int) -> Image.Image:
    scale = 4
    b = size * scale
    img = Image.new("RGBA", (b, b), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = max(2, b // 11)
    rad = max(3, b // 4)
    # solid dark
    d.rounded_rectangle([pad, pad, b - pad - 1, b - pad - 1], radius=rad, fill=(16, 18, 30, 255))
    d.rounded_rectangle(
        [pad, pad, b - pad - 1, b - pad - 1],
        radius=rad,
        outline=(140, 170, 230, 60),
        width=max(1, b // 42),
    )

    cx, cy = b // 2, b // 2
    sw = max(2, b // 22)

    # two nested frames only
    for i, (wf, hf, off, col) in enumerate(
        [
            (0.50, 0.38, 0, (130, 170, 230, 180)),
            (0.34, 0.26, b // 28, (180, 210, 255, 230)),
        ]
    ):
        w, h = int(b * wf), int(b * hf)
        x0 = cx - w // 2 + (off if i else 0)
        y0 = cy - h // 2 + (off if i else 0)
        d.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=max(2, b // 12), outline=col, width=sw)

    # mint tick
    tw = max(2, b // 16)
    th = max(4, b // 8)
    d.rounded_rectangle(
        [cx - b // 14, cy - th // 2 + b // 30, cx - b // 14 + tw, cy + th // 2 + b // 30],
        radius=1,
        fill=(52, 211, 153, 255),
    )
    # cyan dot
    rr = max(2, b // 18)
    d.ellipse([cx + b // 16, cy - rr + b // 30, cx + b // 16 + rr * 2, cy + rr + b // 30], fill=(125, 211, 252, 255))

    return img.resize((size, size), Image.Resampling.LANCZOS)


def make_icon(path: Path) -> None:
    master = render_master(1024)
    path.parent.mkdir(parents=True, exist_ok=True)
    preview = path.with_suffix(".png")
    master.resize((512, 512), Image.Resampling.LANCZOS).save(preview, format="PNG")

    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    images = []
    for s in sizes:
        if s < 48:
            images.append(render_small(s))
        else:
            images.append(master.resize((s, s), Image.Resampling.LANCZOS))

    ordered = sorted(images, key=lambda im: im.width, reverse=True)
    ordered[0].save(
        path,
        format="ICO",
        sizes=[(im.width, im.height) for im in ordered],
        append_images=ordered[1:],
    )
    print(f"Wrote {path}")
    print(f"Preview {preview}")


if __name__ == "__main__":
    make_icon(Path(__file__).resolve().parent / "assets" / "app.ico")
