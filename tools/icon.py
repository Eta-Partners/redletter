#!/usr/bin/env python3
"""Turn a supplied artwork image into the icon size set.

The artwork arrives as a flat picture on a plain white field: a cream sheet with
a printed grid and one rubric-red cell. This finds the sheet, cuts around its true
silhouette, re-centres it on a transparent square and emits every size the
repository needs, in both PNG and WebP.

It cuts on the *paper*, not on the white. A white-key leaves the thin shadow the
artwork draws along the sheet's edge, which reads as dirt at 128 px.

It does not draw anything. The mark is the owner's artwork; this is only the
conversion, so the icon in the README and the icon in `media/icons/` are the same
file at different sizes rather than three drifting copies.

Usage:
    icon.py <source.png> [--out media/icons] [--margin 0.04]
"""

from __future__ import annotations

import argparse
import pathlib
from collections import deque

from PIL import Image, ImageFilter

SIZES = [1024, 512, 256, 192, 128]
PAPER = (250, 239, 214)   # the sheet's own colour
COLOR_TOLERANCE = 16      # how close to PAPER still counts as sheet
SOFTEN = 0.8              # px of blur on the mask, so the cut is not aliased


def px_close(c, tol=COLOR_TOLERANCE) -> bool:
    return max(abs(c[i] - PAPER[i]) for i in range(3)) <= tol


def sheet_mask(img: Image.Image) -> Image.Image:
    """A mask of the sheet: flood the paper colour, then fill the holes it left.

    Flooding the paper colour stops at the printed grid, so the holes (cells, ink,
    the red mark) are filled back in afterwards. That gives the sheet's true
    silhouette, and everything outside it — white field and printed shadow alike —
    is left out of the cut.
    """
    w, h = img.size
    px = img.load()
    inside = bytearray(w * h)

    seeds = [(w // 2, h // 2), (w // 2, h // 4), (w // 4, h // 2), (3 * w // 4, 3 * h // 4)]
    q = deque()
    for sx, sy in seeds:
        # Walk outward from each seed until we are standing on paper.
        for r in range(0, min(w, h) // 2):
            found = False
            for x, y in ((sx + r, sy), (sx - r, sy), (sx, sy + r), (sx, sy - r)):
                if 0 <= x < w and 0 <= y < h and px_close(px[x, y][:3]):
                    q.append((x, y))
                    inside[y * w + x] = 1
                    found = True
                    break
            if found:
                break

    while q:
        x, y = q.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h:
                j = ny * w + nx
                if not inside[j] and px_close(px[nx, ny][:3]):
                    inside[j] = 1
                    q.append((nx, ny))

    # Fill holes: flood the outside from the border over everything not yet inside.
    outside = bytearray(w * h)
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            j = y * w + x
            if not inside[j] and not outside[j]:
                outside[j] = 1
                q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            j = y * w + x
            if not inside[j] and not outside[j]:
                outside[j] = 1
                q.append((x, y))
    while q:
        x, y = q.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h:
                j = ny * w + nx
                if not inside[j] and not outside[j]:
                    outside[j] = 1
                    q.append((nx, ny))

    mask = Image.new("L", (w, h), 0)
    mp = mask.load()
    for y in range(h):
        for x in range(w):
            if inside[y * w + x] or not outside[y * w + x]:
                mp[x, y] = 255
    return mask.filter(ImageFilter.GaussianBlur(SOFTEN))


def cut_sheet(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    img.putalpha(sheet_mask(img))
    return img


def square_on_transparent(img: Image.Image, margin: float) -> Image.Image:
    """Trim to the artwork, then centre it on a transparent square with a margin."""
    box = img.getbbox()
    if not box:
        raise SystemExit("nothing left after cutting the background — is the image all white?")
    art = img.crop(box)
    side = max(art.size)
    canvas_side = int(round(side * (1 + 2 * margin)))
    canvas = Image.new("RGBA", (canvas_side, canvas_side), (0, 0, 0, 0))
    canvas.paste(art, ((canvas_side - art.width) // 2, (canvas_side - art.height) // 2), art)
    return canvas


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--out", default="media/icons")
    ap.add_argument("--margin", type=float, default=0.04)
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    (out / "web").mkdir(parents=True, exist_ok=True)

    src = Image.open(args.source)
    master = square_on_transparent(cut_sheet(src), args.margin)

    for size in SIZES:
        img = master.resize((size, size), Image.LANCZOS)
        img.save(out / f"icon-{size}.png", optimize=True)
        img.save(out / "web" / f"icon-{size}.webp", lossless=False, quality=92, method=6)

    for f in sorted(out.rglob("*")):
        if f.is_file():
            print(f"{f}  {f.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
