#!/usr/bin/env python3
"""Draw the month grid, or a year of them, from the days that passed verification.

Only `status: active` days are marked. A day that did not clear the gate is not
drawn at all — that is the whole difference between a calendar and a list of
things somebody believes.

The layout is built once as a list of drawing primitives, then emitted twice: a
PNG to look at, and an SVG to print. Both come from the same geometry, so the
picture on screen and the picture on paper do not drift.

Usage:
    render_grid.py out/days.json [--year 2027] [--month 4] [--out out]
                   [--rubric '#C0392B'] [--png-only | --svg-only]
"""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import json
import pathlib

from PIL import Image, ImageDraw, ImageFont

# Ink and paper. Mono except for the rubric: the red is information, not decoration.
PAPER = "#FBF3E2"
INK = "#221E1C"
FAINT = "#B9AE99"
GRID = "#E6DDC8"
RUBRIC = "#C0392B"
GRAY = "#8C8375"

FONT_DIR = pathlib.Path.home() / "Library" / "Fonts"
FONT_CANDIDATES = {
    "regular": ["JetBrainsMonoNerdFontMono-Regular.ttf", "JetBrainsMonoNerdFont-Regular.ttf"],
    "bold": ["JetBrainsMonoNerdFontMono-Bold.ttf", "JetBrainsMonoNerdFont-Bold.ttf"],
}
# Any monospace that is actually installed will do; the sheet is set in whatever
# of these is found first, so the renderer runs on Linux and in CI as well as here.
SYSTEM_FALLBACK = {
    "regular": [
        "/System/Library/Fonts/Menlo.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/dejavu/DejaVuSansMono.ttf",
    ],
    "bold": [
        "/System/Library/Fonts/Menlo.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSansMono-Bold.ttf",
    ],
}
SVG_FAMILY = "JetBrainsMonoNFM, Menlo, monospace"
SS = 2  # supersample factor for the PNG


# ---------------------------------------------------------------- primitives


def rect(x, y, w, h, fill, radius=0, stroke=None, sw=0):
    return {"kind": "rect", "x": x, "y": y, "w": w, "h": h,
            "fill": fill, "radius": radius, "stroke": stroke, "sw": sw}


def text(x, y, s, size, fill, anchor="start", weight="regular", spacing=0):
    return {"kind": "text", "x": x, "y": y, "s": s, "size": size,
            "fill": fill, "anchor": anchor, "weight": weight, "spacing": spacing}


def line(x1, y1, x2, y2, color, w=1):
    return {"kind": "line", "x1": x1, "y1": y1, "x2": x2, "y2": y2, "color": color, "w": w}


# -------------------------------------------------------------------- fonts


def font_path(weight: str):
    """The first font that exists here, or None when none of them do."""
    for name in FONT_CANDIDATES[weight]:
        p = FONT_DIR / name
        if p.exists():
            return str(p)
    for p in SYSTEM_FALLBACK[weight]:
        if pathlib.Path(p).exists():
            return p
    return None


class Fonts:
    def __init__(self):
        self._cache = {}

    def get(self, size: int, weight: str = "regular", ss: int = SS):
        key = (round(size * ss), weight)
        if key not in self._cache:
            path = font_path(weight)
            if path is None:
                raise SystemExit(
                    "no monospace font found: put a JetBrains Mono file in ~/Library/Fonts, "
                    "or install DejaVu Sans Mono, or render with --svg-only"
                )
            self._cache[key] = ImageFont.truetype(path, key[0])
        return self._cache[key]


FONTS = Fonts()


def text_width(s: str, size: float, weight: str = "regular") -> float:
    f = FONTS.get(size, weight, ss=1)
    return f.getlength(s)


# ------------------------------------------------------------------ layout


def month_days(year: int, month: int):
    """The weeks of a month, Monday first; 0 marks the days before the 1st."""
    cal = calendar.Calendar(firstweekday=0)
    return [week for week in cal.monthdayscalendar(year, month)]


def month_block(x, y, w, h, year, month, marks, title_size, day_size, header_size, rubric):
    """One month: name, weekday rule, and a cell per day. Marked days take the rubric."""
    prims = []
    pad = w * 0.02
    prims.append(text(x + pad, y + title_size, calendar.month_name[month].upper(),
                      title_size, INK, weight="bold", spacing=title_size * 0.12))

    weeks = month_days(year, month)
    top = y + title_size * 1.9
    rule_y = top + header_size * 1.3
    cell_w = (w - 2 * pad) / 7

    prims.append(line(x + pad, rule_y, x + w - pad, rule_y, INK, 1))
    for i, wd in enumerate("MTWTFSS"):
        prims.append(text(x + pad + cell_w * (i + 0.5), rule_y - header_size * 0.55,
                          wd, header_size, GRAY, anchor="middle"))

    grid_top = rule_y + header_size * 0.55
    row_h = (y + h - grid_top) / 6

    # A faint rule per cell keeps the numbers on a grid instead of floating on paper.
    for c in range(1, 7):
        gx = x + pad + cell_w * c
        prims.append(line(gx, grid_top + row_h * 0.16, gx, y + h - row_h * 0.1, GRID, 1))
    for r in range(6):
        gy = grid_top + row_h * r
        prims.append(line(x + pad, gy, x + w - pad, gy, GRID, 1))

    for r, week in enumerate(weeks):
        for c, day in enumerate(week):
            if not day:
                continue
            cy = grid_top + row_h * r
            cx = x + pad + cell_w * c
            marked = day in marks
            if marked:
                prims.append(rect(cx + cell_w * 0.08, cy + row_h * 0.1,
                                  cell_w * 0.84, row_h * 0.8, rubric, radius=cell_w * 0.1))
            prims.append(text(cx + cell_w * 0.5, cy + row_h * 0.5 + day_size * 0.36, str(day),
                              day_size, PAPER if marked else INK,
                              anchor="middle", weight="bold" if marked else "regular"))
    return prims


def key_lines(marks):
    """One line per printed entry, in date order, with the date on the first line.

    A date with two people on it is two lines: the second indents under the first.
    Counting *lines* rather than dates is what lets a crowded calendar lay its key
    out without running off the page.
    """
    lines = []
    for (month, day), vals in sorted(((m, d), v) for m in marks for d, v in marks[m].items()):
        label = f"{calendar.month_abbr[month].upper()} {day:02d}"
        for i, (hist_year, title) in enumerate(vals):
            lines.append((label if i == 0 else "", f"{hist_year}  {title}"))
    return lines


def key_columns(n_lines):
    """How many columns the key needs to fit a sheet, and how tall each line is."""
    if n_lines <= 16:
        return 2, 56
    if n_lines <= 40:
        return 3, 38
    return 4, 28


KEY_BAND = 640          # the height the key gets, whatever it holds
KEY_INDENT = 92         # where an entry's text starts, right of its date label


def key_columns(lines, W, M):
    """Pick the column count, type size and row height that fit the key band.

    Measured, not guessed: a key that overlaps itself is worse than no key, and a
    calendar with eighty days needs a different key from one with ten.
    """
    best = None
    for size in (17, 16, 15, 14, 13, 12):
        for cols in (2, 3, 4, 5):
            col_w = (W - 2 * M) / cols
            rows = max(1, -(-len(lines) // cols))
            line_h = (KEY_BAND - 46) / rows
            widest = max(
                text_width(label, size, "bold") + KEY_INDENT + text_width(entry, size)
                for label, entry in lines
            ) if lines else 0
            if line_h >= size * 1.3 and widest <= col_w - 16:
                best = (cols, size, min(40, line_h), rows)
                break
        if best:
            break
    if best:
        return best

    # Nothing fits: four columns, the smallest type that reads, and the text is
    # trimmed where it lands rather than allowed to run over its neighbour.
    cols = 4
    rows = max(1, -(-len(lines) // cols))
    return cols, 12, max(14, (KEY_BAND - 46) / rows), rows


def build_year(topic, marks, year, rubric, verified=""):
    W, H, M = 1800, 2400, 120
    lines = key_lines(marks)
    cols, body, line_h, rows = key_columns(lines, W, M)
    col_w = (W - 2 * M) / cols
    room = col_w - KEY_INDENT - 12
    prims = [rect(0, 0, W, H, PAPER)]

    prims.append(text(M, M + 34, "REDLETTER", 22, RUBRIC, weight="bold", spacing=4))
    prims.append(text(M, M + 108, topic["title"], 58, INK, weight="bold"))
    prims.append(text(M, M + 152, f"{year}", 26, INK))
    n_days = sum(len(v) for m in marks.values() for v in m.values())
    prims.append(text(W - M, M + 108, f"{n_days} days", 22, INK, anchor="end"))
    prims.append(text(W - M, M + 140, f"verified {verified}", 17, FAINT, anchor="end"))
    prims.append(line(M, M + 200, W - M, M + 200, INK, 2))

    gap, rows_of_months, cols_of_months = 44, 4, 3
    top = M + 240
    bw = (W - 2 * M - gap * (cols_of_months - 1)) / cols_of_months
    bottom = H - M - KEY_BAND
    bh = (bottom - top - gap * (rows_of_months - 1)) / rows_of_months
    for i in range(12):
        r, c = divmod(i, cols_of_months)
        bx, by = M + c * (bw + gap), top + r * (bh + gap)
        prims += month_block(bx, by, bw, bh, year, i + 1, marks.get(i + 1, {}),
                             26, 19, 15, rubric)

    # The key: every marked day, spelled out. A red square with no name is a decoration.
    ly = bottom + 40
    prims.append(line(M, ly - 34, W - M, ly - 34, INK, 1))
    prims.append(text(M, ly, "THE DAYS", 18, RUBRIC, weight="bold", spacing=3))
    for i, (label, entry) in enumerate(lines):
        c, r = divmod(i, rows)
        ex = M + c * col_w
        ey = ly + 40 + r * line_h
        while room > 0 and text_width(entry, body) > room:
            entry = entry[:-2].rstrip() + "…"
        if label:
            prims.append(text(ex, ey, label, body, RUBRIC, weight="bold"))
        prims.append(text(ex + KEY_INDENT, ey, entry, body, INK))

    prims.append(text(M, H - 60,
                      "Marked days are those whose sources were read and supported the day: "
                      "either two publishers agreed, or a body of record says so.",
                      14, FAINT))
    return prims, (W, H)


def build_month(topic, marks, year, month, rubric):
    W, H, M = 900, 1000, 70
    prims = [rect(0, 0, W, H, PAPER)]
    prims.append(text(M, M + 20, "REDLETTER", 16, RUBRIC, weight="bold", spacing=3))
    prims.append(text(M, M + 72, topic["title"], 32, INK, weight="bold"))
    prims.append(text(M, M + 108, f"{year}", 18, INK))
    prims.append(line(M, M + 140, W - M, M + 140, INK, 2))
    prims += month_block(M, M + 170, W - 2 * M, 470, year, month,
                         marks.get(month, {}), 34, 26, 17, rubric)
    ey = M + 690
    prims.append(line(M, ey - 24, W - M, ey - 24, INK, 1))
    for i, (d, vals) in enumerate(sorted(marks.get(month, {}).items())):
        prims.append(text(M, ey + 14 + i * 46, f"{calendar.month_abbr[month].upper()} {d:02d}",
                          16, RUBRIC, weight="bold"))
        for j, (hist_year, title) in enumerate(vals):
            prims.append(text(M + 92, ey + 14 + i * 46 + j * 22, f"{hist_year}  {title}",
                              16, INK))
    return prims, (W, H)


# ------------------------------------------------------------------ emitters


def emit_png(prims, size, path):
    W, H = size
    img = Image.new("RGB", (W * SS, H * SS), PAPER)
    d = ImageDraw.Draw(img)
    for p in prims:
        if p["kind"] == "rect":
            box = [p["x"] * SS, p["y"] * SS, (p["x"] + p["w"]) * SS, (p["y"] + p["h"]) * SS]
            kw = {}
            if p["stroke"]:
                kw = {"outline": p["stroke"], "width": max(1, int(p["sw"] * SS))}
            if p["radius"]:
                d.rounded_rectangle(box, radius=p["radius"] * SS, fill=p["fill"], **kw)
            else:
                d.rectangle(box, fill=p["fill"], **kw)
        elif p["kind"] == "line":
            d.line([p["x1"] * SS, p["y1"] * SS, p["x2"] * SS, p["y2"] * SS],
                   fill=p["color"], width=max(1, int(p["w"] * SS)))
        elif p["kind"] == "text":
            f = FONTS.get(p["size"], p["weight"], ss=SS)
            anchor = {"start": "ls", "middle": "ms", "end": "rs"}[p["anchor"]]
            if p["spacing"]:
                x = p["x"]
                for ch in p["s"]:
                    d.text((x * SS, p["y"] * SS), ch, font=f, fill=p["fill"], anchor=anchor)
                    x += f.getlength(ch) / SS + p["spacing"]
            else:
                d.text((p["x"] * SS, p["y"] * SS), p["s"], font=f, fill=p["fill"], anchor=anchor)
    img.save(path)


def emit_svg(prims, size, path):
    W, H = size
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
           f'viewBox="0 0 {W} {H}">',
           f'<rect width="{W}" height="{H}" fill="{PAPER}"/>']
    for p in prims:
        if p["kind"] == "rect":
            if p["fill"] == PAPER:
                continue
            stroke = f' stroke="{p["stroke"]}" stroke-width="{p["sw"]}"' if p["stroke"] else ""
            r = f' rx="{p["radius"]}"' if p["radius"] else ""
            out.append(f'<rect x="{p["x"]:.2f}" y="{p["y"]:.2f}" width="{p["w"]:.2f}" '
                       f'height="{p["h"]:.2f}"{r} fill="{p["fill"]}"{stroke}/>')
        elif p["kind"] == "line":
            out.append(f'<line x1="{p["x1"]:.2f}" y1="{p["y1"]:.2f}" x2="{p["x2"]:.2f}" '
                       f'y2="{p["y2"]:.2f}" stroke="{p["color"]}" stroke-width="{p["w"]}"/>')
        elif p["kind"] == "text":
            anchor = {"start": "start", "middle": "middle", "end": "end"}[p["anchor"]]
            weight = ' font-weight="700"' if p["weight"] == "bold" else ""
            spacing = f' letter-spacing="{p["spacing"]}"' if p["spacing"] else ""
            s = (p["s"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
            out.append(f'<text x="{p["x"]:.2f}" y="{p["y"]:.2f}" font-family="{SVG_FAMILY}" '
                       f'font-size="{p["size"]}" fill="{p["fill"]}" text-anchor="{anchor}"'
                       f'{weight}{spacing}>{s}</text>')
    out.append("</svg>")
    pathlib.Path(path).write_text("\n".join(out) + "\n")


# -------------------------------------------------------------------- main


def topic_of(path) -> dict:
    return json.loads(pathlib.Path(path).read_text())["topic"]


def load_marks(path, year):
    data = json.loads(pathlib.Path(path).read_text())
    marks, skipped = {}, []
    for d in data["days"]:
        if d["status"] != "active":
            skipped.append((d["id"], d["status"]))
            continue
        month, day = (int(x) for x in d["month_day"].split("-"))
        if month == 2 and day == 29 and not calendar.isleap(year):
            skipped.append((d["id"], "no 29 February in {}".format(year)))
            continue
        marks.setdefault(month, {}).setdefault(day, []).append((d["year"], d["title"]))
    return data["topic"], marks, skipped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("days", help="out/days.json written by verify_days.py --write")
    ap.add_argument("--year", type=int, default=None)
    ap.add_argument("--month", type=int, default=None, choices=range(1, 13))
    ap.add_argument("--out", default="out")
    ap.add_argument("--rubric", default=RUBRIC)
    ap.add_argument("--png-only", action="store_true")
    ap.add_argument("--svg-only", action="store_true")
    args = ap.parse_args()

    topic = topic_of(args.days)
    year = args.year or topic.get("print_year") or dt.date.today().year + 1
    marks_meta, marks, skipped = load_marks(args.days, year)
    topic = marks_meta
    verified = json.loads(pathlib.Path(args.days).read_text()).get("generated_on", "")

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"redletter-{topic['id']}-{year}" + (f"-{year}{args.month:02d}" if args.month else "")
    if args.month:
        prims, size = build_month(topic, marks, year, args.month, args.rubric)
    else:
        prims, size = build_year(topic, marks, year, args.rubric, verified)

    if not args.svg_only:
        emit_png(prims, size, out / f"{stem}.png")
    if not args.png_only:
        emit_svg(prims, size, out / f"{stem}.svg")

    n_marked = sum(len(v) for m in marks.values() for v in m.values())
    print(f"{stem}: {n_marked} marked days on a {size[0]}x{size[1]} sheet")
    for ident, why in skipped:
        print(f"  not drawn: {ident} ({why})")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
