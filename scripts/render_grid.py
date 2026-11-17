#!/usr/bin/env python3
"""Draw the month grid, or a year of them, from the days that passed verification.

Only `status: active` days are marked. A day that did not clear the gate is not
drawn at all — that is the whole difference between a calendar and a list of
things somebody believes.

The layout is built once as a list of drawing primitives, then emitted three
ways: a PNG to look at, an SVG to print, and a multi-page PDF for the book form.
All three come from the same geometry, so the picture on screen and the picture
on paper do not drift.

Usage:
    render_grid.py out/days.json [--year 2027] [--month 4] [--out out]
                   [--rubric '#C0392B'] [--png-only | --svg-only]
    render_grid.py out/days.json --pdf [--paper a4|letter] [--orientation ...]
"""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import json
import math
import pathlib
import re

from PIL import Image, ImageDraw, ImageFont

# The one definition of "this record is about a person", shared with the gate so
# the death rule and the fame line cannot drift. It lives in verify_days because
# that module has no drawing dependency (Pillow is right here); importing it this
# way round is also what keeps the gate runnable without a font or an image lib.
from verify_days import person_suffix

# Ink and paper. Mono except for the rubric: the red is information, not decoration.
PAPER = "#FBF3E2"
INK = "#221E1C"
FAINT = "#B9AE99"
GRID = "#E6DDC8"
RUBRIC = "#C0392B"
GRAY = "#8C8375"

# The cover's one sentence. It is the repository's own description, kept here as a
# constant so the title page cannot drift from the README it repeats.
TAGLINE = "Calendars of the days a field marks in red: every day sourced, every source read."

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
    """Faces, cached by the size that asked for them.

    The key is the point size and the scale, not the pixel count they round to.
    Two sizes can round to the same count - 8 pt and 8.5 pt are both 8 px at
    ss=1 - and a cache that hands one size another size's face is a defect that
    stays invisible until the rounding or the scale changes underneath it. The
    face loaded is still the whole pixel grid; `advance` says why that grid.
    """

    def __init__(self):
        self._cache = {}

    def get(self, size: float, weight: str = "regular", ss: int = SS):
        key = (float(size), int(ss), weight)
        if key not in self._cache:
            path = font_path(weight)
            if path is None:
                raise SystemExit(
                    "no monospace font found: put a JetBrains Mono file in ~/Library/Fonts, "
                    "or install DejaVu Sans Mono, or render with --svg-only"
                )
            self._cache[key] = ImageFont.truetype(path, max(1, int(round(size * ss))))
        return self._cache[key]


FONTS = Fonts()


_ADVANCE = {}


def advance(size, weight="regular"):
    """One character's width in points, rounded to the whole point.

    The layout's only unit of width, and `draw` places every glyph by it as well,
    so a line is drawn at the width it was measured at. Rounding once is what
    makes the page a property of the type size instead of of the wheel: Pillow's
    macOS wheel returns a whole number of pixels for a face where the manylinux
    wheel returns the fraction - DejaVu Sans Mono 2.37, M at 9 pt, reads 5.0
    against 5.421875 - so a layout that measured the raw advance drew a
    different page on each.

    What this pins is the advance *ratio*, not the font build. Every face named
    above is 0.600-0.602 em, and at the sizes this deck uses both ends of that
    range round to the same whole point. A monospace outside the class, or a size
    where the two ends straddle a half point, is a different layout: "any
    monospace will do" still means the sheet renders and prints, it does not mean
    every face yields this exact page.

    The face is read at `ss=1`, so a size is measured on the whole pixel grid:
    8.5 pt is measured on the 8 px face, and `Fonts.get` keeps that face its own
    entry. That grid is deliberate - it is the only one the two wheels agree on.
    A fractional pixel size is snapped by the macOS wheel (37.5 px rasterises
    identically to 38 px, measured) and honoured by manylinux, so asking for 5.5
    px would read 4.0 here and 3.3 there, and `cell_chars(70, 5.5)` would be 17
    against 23: the stack dependence this function exists to remove. (The 23 is
    this function's own rounding doing the work - 3.313 rounds to 3 - and would be
    21 for a variant that divided unrounded; the number belongs to the pipeline,
    not to the face.)
    """
    key = (float(size), weight)
    if key not in _ADVANCE:
        raw = FONTS.get(size, weight, ss=1).getlength("M")
        _ADVANCE[key] = max(1, int(math.floor(raw + 0.5)))
    return _ADVANCE[key]


def text_width(s: str, size: float, weight: str = "regular") -> float:
    return advance(size, weight) * len(s)


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

    # Nothing fits on one line. The old answer was "four columns, small type", but
    # at high density the column count is the real lever on how much of a sentence
    # survives, and four columns threw away a third of the width. Keep the largest
    # type that fits the band at all, and at that size take the column count that
    # shows the most characters per line.
    for size in (12, 11, 10):
        best, best_chars = None, -1.0
        char_w = max(0.1, text_width("M", size))
        for cols in (2, 3, 4, 5):
            rows = max(1, -(-len(lines) // cols))
            line_h = (KEY_BAND - 46) / rows
            if line_h < size * 1.25:
                continue
            label_w = max((text_width(label, size, "bold") for label, _ in lines), default=0)
            room = (W - 2 * M) / cols - 16 - KEY_INDENT - label_w
            chars = room / char_w
            if chars > best_chars:
                best, best_chars = (cols, line_h, rows), chars
        if best:
            cols, line_h, rows = best
            return cols, size, min(40, line_h), rows

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


def draw(prims, size, ss=SS):
    """The page as a bitmap. Every emitter draws through here, so none can drift."""
    W, H = size
    img = Image.new("RGB", (W * ss, H * ss), PAPER)
    d = ImageDraw.Draw(img)
    for p in prims:
        if p["kind"] == "rect":
            box = [p["x"] * ss, p["y"] * ss, (p["x"] + p["w"]) * ss, (p["y"] + p["h"]) * ss]
            kw = {}
            if p["stroke"]:
                kw = {"outline": p["stroke"], "width": max(1, int(p["sw"] * ss))}
            if p["radius"]:
                d.rounded_rectangle(box, radius=p["radius"] * ss, fill=p["fill"], **kw)
            else:
                d.rectangle(box, fill=p["fill"], **kw)
        elif p["kind"] == "line":
            d.line([p["x1"] * ss, p["y1"] * ss, p["x2"] * ss, p["y2"] * ss],
                   fill=p["color"], width=max(1, int(p["w"] * ss)))
        elif p["kind"] == "text":
            if not p["s"]:
                continue
            f = FONTS.get(p["size"], p["weight"], ss=ss)
            # Glyph by glyph, at the same whole-point advance the layout measured
            # with: one number for both, so drawing cannot drift from measuring.
            step = advance(p["size"], p["weight"]) + p["spacing"]
            width = step * len(p["s"]) - p["spacing"]
            x = p["x"] - {"start": 0, "middle": width / 2, "end": width}[p["anchor"]]
            for ch in p["s"]:
                d.text((x * ss, p["y"] * ss), ch, font=f, fill=p["fill"], anchor="ls")
                x += step
    return img


def emit_png(prims, size, path):
    draw(prims, size, SS).save(path)


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


# --------------------------------------------------------------- the book form

# One month per page is a different job from the wall sheet: the cell has room to
# say what the day *is*, not only that it is marked. Everything here is laid out
# in PostScript points — the paper's own unit — and scaled to pixels only at emit
# time, so the same geometry prints at 150 dpi or 300 dpi without being re-tuned.
PAPER_MM = {"a4": (210.0, 297.0), "letter": (215.9, 279.4)}
PDF_DPI = 300
CELL_PT = [9.5, 9, 8.5, 8, 7.5, 7, 6.5, 6, 5.5, 5]
CELL_LEADING = 1.32
# A cell's height is a sum of `size * leading` terms, so a budget that is exactly
# n lines can land a few ULPs under n * size * leading. Comparing without a
# tolerance turns that into a hidden record: 37.62 - 12.54 is 25.079999999999998,
# and a two-line title measured at 25.08 stopped fitting the two lines left.
LAYOUT_EPS = 1e-6
BLURB_SCALE = 0.86
BLURB_MIN_PT = 7.5


def page_size_pt(paper="a4", orientation="landscape"):
    """The page in points. Landscape, because a week is wider than it is tall."""
    w_mm, h_mm = PAPER_MM[paper]
    w, h = w_mm / 25.4 * 72, h_mm / 25.4 * 72
    return (h, w) if orientation == "landscape" else (w, h)


def scale_prims(prims, s):
    """Points to pixels, for the emitter. The layout never sees a pixel."""
    out = []
    for p in prims:
        q = dict(p)
        if p["kind"] == "rect":
            q.update(x=p["x"] * s, y=p["y"] * s, w=p["w"] * s, h=p["h"] * s,
                     radius=p["radius"] * s, sw=p["sw"] * s)
        elif p["kind"] == "line":
            q.update(x1=p["x1"] * s, y1=p["y1"] * s, x2=p["x2"] * s, y2=p["y2"] * s,
                     w=max(1, p["w"] * s))
        else:
            q.update(x=p["x"] * s, y=p["y"] * s, size=p["size"] * s,
                     spacing=p["spacing"] * s)
        out.append(q)
    return out


def wrap_to(s, chars):
    """Break a sentence into lines of at most `chars`, on spaces, losing no word.

    A word longer than the line is left whole rather than split: these cells hold
    names and chemical terms, and a hyphen this code inserts is a word it invented.
    A line can therefore come out wider than `chars`; `fit_to_width` is what makes
    a cell keep its own width.
    """
    chars = max(4, int(chars))
    lines, cur = [], ""
    for word in s.split():
        cand = f"{cur} {word}".strip()
        if len(cand) <= chars or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = word
    return (lines + [cur]) if cur else (lines or [""])


def fit_to_width(lines, chars, indent):
    """Indents that keep every line inside `chars`, breaking what cannot fit.

    `wrap_to` leaves a word longer than its line whole, so a wrapped line can still
    be wider than the cell. Two rules, in order. First the line takes the full
    width at indent 0 if the word fits there: on a continuation line that is what
    keeps `International` in its own date cell instead of the next day's. Only a
    word wider than the whole cell is broken, at the character boundary that fits,
    and without a hyphen inserted — a hyphen would be a character this code
    invented, while a word in the cell beside it silently gives a day's detail to
    another day, which is worse than a visibly broken word.
    """
    out = []
    for ln in lines:
        if len(ln) <= chars - indent:
            out.append((ln, indent))
        elif indent and len(ln) <= chars:
            out.append((ln, 0))
        else:
            out.extend((ln[i:i + chars], 0) for i in range(0, len(ln), chars))
    return out


def cell_chars(w_pt, size_pt):
    return max(4, int(w_pt / max(0.1, text_width("M", size_pt))))


MIN_HANG_CHARS = 8


FAME_LINES = 2


# The clause the title already says: ", was born.", ", was born in Warsaw.",
# ", died." - the predicate, optionally with a place. The tail is a place and not
# any words: an unbounded tail reads Curie's death sentence ("died of aplastic
# anaemia almost certainly due to her exposure to radioactive materials") as a
# repetition and deletes the cause, which is the one thing that record is for.
BIRTH_CLAUSE = re.compile(r",\s(?:was born|died)(?:\sin\s\S+(?:\s\S+){0,2})?\.$")


def without_birth_clause(text):
    """The fame line without a trailing ", was born." / ", died." clause.

    The chemistry blurbs end "..., was born." (one ends ", was born in Warsaw.");
    the title already says "X is born", so the cell says it twice, exactly as it
    used to say the name twice before `fame_line` stripped that. Dropping the
    comma with the clause leaves the drawn line on its last word rather than on a
    dangling comma, and leaves it a substring of the approved blurb.

    The clause is matched only at the end of the string, so a blurb that merely
    contains the words mid-sentence is untouched. A sentence that states the cause
    of a death - Curie's - does not end in one of these clauses and is untouched.
    """
    return BIRTH_CLAUSE.sub("", text)


def after_label(text):
    """The reason clause when `text` opens with a citation label, else `text`.

    The laureate calendar's sentences open "Nobel Prize in Chemistry 1945 in Russian
    Empire: for his research ...". What comes before the colon is the award, which
    says what the day was; the clause after it says what the person is known for,
    and that is what the cell exists to print. Without this, two lines of grey in a
    laureate cell are spent on the label and the reason is never reached.

    A label is recognised without knowing who wrote it: it carries no sentence
    ending, and something non-empty follows the colon. A colon that arrives after a
    full stop is inside a sentence, not a label, so that text is returned whole.
    This chooses only where the substring starts; it never adds a word, so the fame
    line stays a suffix of the approved blurb.
    """
    head, sep, rest = text.partition(": ")
    if sep and rest.strip() and not any(ch in head for ch in ".!?"):
        return rest
    return text


def fame_line(title, blurb):
    """What a person is known for: the blurb, minus the name, then minus the label.

    A person's cell prints `Marie Curie is born` and then a blurb that opens
    `Marie Curie, ...`, so the name is said twice before anything is said about
    it. The fame line is the rest of the blurb. It is derived from the record's
    own words and never written here: every character it draws is a substring of
    the blurb, which is what makes it safe to print as fact.

    A title that is not a person's birthday or death day returns None, so a
    discovery, a milestone or a mission never grows one; the test is
    `verify_days.person_suffix`, the same function the gate uses. When the blurb
    does not open with the title's subject, it is returned whole rather than
    trimmed at a guess: a name this code trimmed off would be a word it invented,
    and the record would print a sentence with its subject missing. The label
    rule then applies to whatever remains (`after_label`), and the birth clause
    the title already says comes off last (`without_birth_clause`).
    """
    suffix = person_suffix(title)
    if suffix is None:
        return None
    prefix = title[: -len(suffix)] + ", "
    if not blurb.startswith(prefix):
        return after_label(blurb)
    # The clause comes off only on the sentence that leads with the person and
    # whose subject is the title. On a sentence that does not - "That inventor of
    # the electrostatic precipitator, Cottrell, was born in Ohio." - the same
    # words are the sentence's own predicate, and dropping them would leave a
    # subject with nothing said about it, which is the failure the no-silent-
    # stripping rule above exists to prevent.
    return without_birth_clause(after_label(blurb[len(prefix):]))


def record_blocks(year, title, blurb, chars, size, with_blurb):
    """One record's lines: its title, which is atomic, and its detail, which is not.

    The title block is the year and the name wrapped to the cell, continuation
    lines hung under it. It is returned as its own list because a title is the one
    thing in a cell that may not be cut: cut after its first line, "1883 Walter
    Norman Haworth is born" becomes "1883 Walter Norman", and the reader has a
    person with no surname. Everything else - a fame line, a blurb - is detail and
    may be cut. See `_record_blocks_core` for the wrapping and type rules.
    """
    return _record_blocks_core(year, title, blurb, chars, size, with_blurb)


def _record_blocks_core(year, title, blurb, chars, size, with_blurb):
    """The measure: `record_blocks` with every detail line kept. It never cuts.

    Cutting is the layout's job and happens once, in `cell_layout`: a detail line
    cut here and again there would put a second ellipsis on a line that already
    has one.

    Continuation lines hang under the title, so they are wrapped to `chars` minus
    the hang: wrapping them to the full width and then indenting them is what puts
    a cell's last words in its neighbour's column. When the hang would leave less
    than MIN_HANG_CHARS for the line, it is dropped and the continuation takes the
    full width: `wrap_to` clamps at 4, so a width that goes to nought is not an
    error, it is four-character slivers shoved right by the indent and past the
    cell edge. Measured on the shipped datasets, the tightest `chars - hang` is
    14 at A4 landscape and 5 at A4 portrait; 8 keeps the hang where it reads and
    drops it in portrait, where the cell is narrower than the year's indent.

    The blurb prints at the cell's left edge. It is already distinguished from the
    title by grey and 0.86x type (the fame line is grey at the cell's own size, so
    it shares only the grey), and sharing the hang costs a step of type on the
    path that decides whether a blurb appears at all: in a 70 by 45 pt cell with
    one event and a 24-character blurb, the hung page keeps 9.5 pt and no blurb,
    while the blurb at the cell's edge is chosen at 9 pt with it (the exact strings
    are pinned in test_the_blurb_costs_one_step_of_type_in_a_narrow_cell). The hang
    was suppressing the detail it was meant to organise. That case is a probe, not
    a page: the shipped blurbs run 34 to 150 characters, and the split changes no
    month page's choice in any of the twelve books — the blurb is drawn on two,
    spaceflight at A4 portrait January and July, and on those it is the blurb's
    own placement that moves, not the type. At A4 landscape no blurb is drawn at
    all, so nothing there changes.
    """
    head = str(year)
    hang = len(head) + 2
    if chars - hang < MIN_HANG_CHARS:
        hang = 0
    wrapped = wrap_to(f"{head}  {title}", chars)
    lines = fit_to_width([wrapped[0]], chars, 0)
    rest = " ".join(wrapped[1:])
    if rest:
        lines += fit_to_width(wrap_to(rest, chars - hang), chars, hang)
    title_blocks = [(ln, size, INK, indent) for ln, indent in lines]

    detail = []
    fame = fame_line(title, blurb)
    if fame:
        # Always drawn on a person's cell, whatever `with_blurb` says: the
        # question there is whether a page can afford detail, and a fame line
        # capped at FAME_LINES is the detail that fits. It prints at the cell's
        # own size, not at the blurb's 0.86x: at 0.86 the laureate book set it
        # at 5.59 pt under a 6.5 pt title, which is a footnote to the thing it
        # explains rather than the content TJ asked for. The cap uses the same
        # ellipsis as the cell's own truncation, so a cut line says so.
        fsize = size
        fblocks = [(ln, fsize, GRAY, 0)
                   for ln, _ in fit_to_width(wrap_to(fame, chars), chars, 0)]
        cap = FAME_LINES * fsize * CELL_LEADING
        detail = list(_cut_blocks(fblocks, cap, chars))
    elif with_blurb and blurb:
        bsize = size * BLURB_SCALE
        detail = [(ln, bsize, GRAY, 0)
                  for ln, _ in fit_to_width(wrap_to(blurb, chars), chars, 0)]
    return title_blocks, detail


def cell_blocks(events, chars, size, with_blurb):
    """One cell's lines and the height they need, as (text, size, ink, indent).

    Titles and their detail, record by record. This is the cell's *need*: what it
    would draw with room for everything, which is what the page's type choice
    measures against. What it actually draws is `cell_layout`.
    """
    blocks, height = [], 0.0
    for year, title, blurb in events:
        title_blocks, detail = record_blocks(year, title, blurb, chars, size, with_blurb)
        for block in title_blocks + detail:
            blocks.append(block)
            height += block[1] * CELL_LEADING
    return blocks, height


def cell_min_height(events, chars, size):
    """The least height that lets every record in the cell start.

    A person's title is atomic, so it needs all of its lines; any other record's
    title is ordinary prose and may be cut, so it needs one line to start. This is
    the chooser's floor: at a size where it holds, no record in the cell has to be
    counted in an "and N more" line.
    """
    line_h = size * CELL_LEADING
    total = 0.0
    for year, title, blurb in events:
        if person_suffix(title) is None:
            total += line_h
        else:
            title_blocks, _ = record_blocks(year, title, blurb, chars, size, False)
            total += len(title_blocks) * line_h
    return total


CUT_CLOSERS = ",.!?;:)]\"'"


def cut_line(s, chars=None, indent=0):
    """`s`, cut: end on a whole token, the ellipsis saying the line went on.

    The marker may take the place of punctuation that closes the last token - a
    comma, a full stop, a bracket, a quote - because that token is already whole.
    It may not take the place of a character inside one: a letter, a digit, or a
    hyphen that joins a compound. A line with a character of slack appends the
    marker to the whole word; a line without slack drops that word and ends on
    the previous one; where dropping it would leave nothing but the marker, the
    line keeps its old shape, because a bare ellipsis tells the reader nothing
    about what was lost.

    `chars` is the cell's measure in characters and `indent` the hang the line is
    drawn at, in the same units, so the text has chars - indent to fill: a line
    hung six characters into a fourteen-character cell can hold eight, not
    fourteen. Reading the measure without the hang put one drawn line past its
    cell at dadbef0 - chemistry 12-24 at Letter portrait, 'use of a…' at indent 6
    against a measure of 14 - which is why both facts are arguments here.

    A caller that has no measure - a test cutting a block list, the audit's spy on
    the page's final guard - gets the no-slack reading, which can only ever run
    short of the cell. Measured, that guard never cuts: 2920 calls, no line
    changed, both books, all four shapes.
    """
    if len(s) <= 1:
        return s
    body = s.rstrip()
    if not body:
        return s
    if body.endswith("…"):
        return body                    # already marked; appending would double it
    if body[-1] in CUT_CLOSERS:
        return body[:-1].rstrip() + "…"
    if chars is not None and len(body) + 1 + indent <= chars:
        return body + "…"
    prefix = body[:len(body) - len(body.split()[-1])].rstrip()
    if prefix:
        return prefix + "…"
    return body[:-1].rstrip() + "…"    # only the marker would be left: draw it as before


def fit_detail(blocks, height, chars=None):
    """As much of `blocks` as fits in `height`, the last kept line cut by cut_line."""
    kept, used = [], 0.0
    for block in blocks:
        line_h = block[1] * CELL_LEADING
        if used + line_h > height + LAYOUT_EPS:
            break
        kept.append(block)
        used += line_h
    if kept and len(kept) < len(blocks):
        s, size, ink, indent = kept[-1]
        kept[-1] = (cut_line(s, chars, indent), size, ink, indent)
    return kept


def _draw_records(records, size, height, chars=None):
    """Draw records into `height`; return (blocks, used, hidden_record_count).

    Titles go down first, every one of them, and detail fills the height left
    over in record order. Titles are what a cell owes its reader: allocating a
    record's detail before the next record's title is what hid "Frédéric Joliot"
    on 19 March behind 1.5 lines of Haworth's fame line. A person's title is
    drawn whole or not at all; a prose record's title may be cut with the ellipsis
    the cell already uses. The first record that cannot start ends the walk, and
    the records from there on are the count the cell owes the reader.
    """
    line_h = size * CELL_LEADING
    titles, used = [], 0.0
    for i, (title_blocks, _detail, is_person) in enumerate(records):
        if is_person:
            need = len(title_blocks) * line_h
            if used + need > height + LAYOUT_EPS:
                return _with_detail(records[:i], height, size, chars), used, len(records) - i
            drawn = title_blocks
        else:
            drawn = fit_detail(title_blocks, height - used, chars)
            if not drawn:
                return _with_detail(records[:i], height, size, chars), used, len(records) - i
        titles.append(drawn)
        used += sum(b[1] * CELL_LEADING for b in drawn)
    return _with_detail(records[:len(titles)], height, size, chars), used, 0


def _with_detail(records, height, size, chars=None):
    """The placed titles with the detail shared between them, one line each in turn.

    The detail pool is the height left after *every* title. It is shared round
    robin, in record order: every record takes its first line before any record
    takes a second. Handing each record as many lines as fitted before moving to
    the next let the first person in a cell spend the whole pool - at Letter
    landscape 25 December Windaus drew two fame lines and Herzberg none, so a cell
    about two people was about one of them. A reader should meet both before
    hearing more about either.

    A record whose next line does not fit is skipped for that round and has no
    later round that fits either, because the pool only shrinks; the pass ends
    when a whole round adds nothing. A cell holding one record allocates exactly
    as it did before: its lines in order, the last kept one carrying the ellipsis
    when the pool ran out.

    The pool is still what the titles leave: charging detail record by record
    against what the titles before it had left let one fame line push a later
    title past the cell's height, and the page's final truncate_blocks then cut
    that title - the exact defect this layout exists to stop.
    """
    title_heights = [sum(b[1] * CELL_LEADING for b in tb)
                     for tb, _detail, _is_person in records]
    pool = height - sum(title_heights)
    kept = [[] for _ in records]
    cursor = [0] * len(records)
    progressed = True
    while progressed:
        progressed = False
        for i, (_title, detail, _is_person) in enumerate(records):
            if cursor[i] >= len(detail):
                continue
            line_h = detail[cursor[i]][1] * CELL_LEADING
            if line_h > pool + LAYOUT_EPS:
                continue
            kept[i].append(detail[cursor[i]])
            cursor[i] += 1
            pool -= line_h
            progressed = True
    out = []
    for (title_blocks, detail, _is_person), lines in zip(records, kept):
        out += title_blocks
        if len(lines) < len(detail) and lines:
            s, line_size, ink, indent = lines[-1]
            lines = lines[:-1] + [(cut_line(s, chars, indent), line_size, ink, indent)]
        out += lines
    return out


def cell_layout(events, chars, size, with_blurb, height):
    """What the cell draws in `height`: person titles whole, detail with what is left.

    The rule the cell obeys is that a person's title is never cut. Cut after its
    first line, "1883 Walter Norman Haworth is born" reads "1883 Walter Norman",
    and the reader has a person with no surname. Detail - a fame line, a blurb -
    may still be cut with the ellipsis the cell already uses. A cell whose person
    records do not all fit draws the ones that do and a final "and N more" line: a
    visible count, because a record that vanishes without a word is the defect
    this fixes. The count line is charged the cell's own type.

    A title that is not a person's is ordinary prose - chemistry's day titles are
    whole sentences - and keeps the old behaviour: it is cut like detail, and a
    cell holding none of them keeps exactly the prefix-and-ellipsis it had. Making
    every title atomic would set chemistry's pages at 5 pt to fit "Niels Bohr
    proposed his model of the atom..." in a month cell, which is a different book,
    not a fix.
    """
    records = []
    for year, title, blurb in events:
        title_blocks, detail = record_blocks(year, title, blurb, chars, size, with_blurb)
        records.append((title_blocks, detail, person_suffix(title) is not None))
    if not any(is_person for *_rest, is_person in records):
        # No person in this cell: the cell is prose and nothing changes for it.
        stream = [b for title_blocks, detail, _ in records
                  for b in title_blocks + detail]
        return _cut_blocks(stream, height, chars)
    drawn, _, hidden = _draw_records(records, size, height, chars)
    if not hidden:
        return drawn
    # Reserve the count line by laying the same records out one line shorter, so
    # the cell says what it is not showing instead of running over its box.
    drawn, _, hidden = _draw_records(records, size, height - size * CELL_LEADING, chars)
    drawn.append((f"and {hidden} more", size, GRAY, 0))
    return drawn


def truncate_blocks(blocks, height):
    """Keep a cell inside its box, and say so with an ellipsis.

    `height` is the room the box has, in points. It is a height and not a count of
    lines because a cell's lines are not all one size: a blurb is set at 0.86x the
    title's, as the fame line was until it moved to the cell's own size, so
    counting lines at the title's size threw away detail the cell had room for —
    seven fame lines on the laureate book at A4 landscape and two on the
    spaceflight book at A4 portrait, every one of them a cell the chooser had just
    found fitted. One 132-character entry — a Nobel citation quoted whole — would
    otherwise set the type size for every cell on the page. The sheet already
    truncates its key the same way; a line that ends in … is honest about being
    cut.

    The page makes exactly one call to this per drawn day cell, as its final
    guard: the layout has already fitted the cell, so the call keeps nothing and
    changes nothing. The operator's audit in `tools/` pairs days to cells by this
    call, so the cell's own internal cuts go through `_cut_blocks` instead and do
    not look like a second cell. The two-argument signature is part of that
    contract: `tools/redletter-fame-audit.py` replaces this function with a spy
    that passes the same two arguments on.

    That leaves this call without the cell's measure, so a cut here would fall
    back to `_cut_blocks`'s no-slack reading. It never gets the chance: measured at
    0c63caf and again with cut_line in place, this guard cut no line on either book
    at any of the four shapes - 2920 calls, none changed - because the layout has
    already fitted the cell by height. A guard that starts cutting is a layout bug
    to fix in the layout, not a line for this function to draw differently.
    """
    return _cut_blocks(blocks, height)


def _cut_blocks(blocks, height, chars=None):
    """The cut itself: a prefix by height, the last kept line cut by cut_line."""
    if not blocks:
        return blocks
    used, kept = 0.0, []
    for block in blocks:
        used += block[1] * CELL_LEADING
        if used > height + LAYOUT_EPS and kept:
            break
        kept.append(block)
    if len(kept) == len(blocks):
        return blocks
    s, size, ink, indent = kept[-1]
    kept[-1] = (cut_line(s, chars, indent), size, ink, indent)
    return kept


def blurb_is_worth_it(blurb_size, title_size):
    """Detail is preferred over size only while it costs *less than* 1.5 pt.

    Strictly less, because the type steps by 0.5 pt, so `title_size - 1.5` is a
    reachable size rather than a limit nothing lands on. Measured, it is reached:
    the ten-day spaceflight dataset at Letter portrait has January and July at a
    blurb of 8 pt against a title of 9.5, and both now keep the larger title.
    """
    return blurb_size >= BLURB_MIN_PT and blurb_size > title_size - 1.5


def choose_cell_type(cells, w_pt, h_pt, sizes=CELL_PT):
    """The type size that fits the page, allowing a rare cell to lose detail.

    Sizing on the *worst* cell lets one long entry shrink a whole month, which is
    the wrong trade: nine cells set too small to teach a whole page to fit one.
    A page is accepted when nine cells in ten hold their text, and the tenth
    shows less detail. Detail is preferred over size only while it costs less
    than a point and a half of type.

    What the ninth cell may lose is detail, never a name. Every record's title
    block has to fit its cell at the chosen size, in every cell, or the size is
    refused: a title cut after its first line prints "1883 Walter Norman" and the
    reader has a person with no surname, which is not a smaller version of the
    record but a different one. If no size holds every title, the page takes the
    smallest size and a cell that still cannot hold a record says "and N more" —
    the count is the fallback, not the allowance, and on the shipped books every
    title fits at the chosen size.

    A size is also refused when a name word cannot sit on one line. The cell's
    wrapper leaves a long word whole until nothing else fits and then splits it at
    a character boundary (`fit_to_width` slices with `ln[i:i + chars]`), so at the
    portrait shapes "Euler-Chelpin" is drawn "Euler-Chelp" / "in" and "Nicolas-Louis"
    is drawn "Nicolas-Lou" / "is": two words where the reader had one, and a
    sentence — "1763 Nicolas-Lou is Vauquelin is born" — that asserts the wrong
    thing. The width is a character count, not points, because that is the unit the
    splitter works in, and it is the cell's full width rather than the hung width:
    `fit_to_width` moves a continuation line to indent 0 whenever it fits there, so
    a word that fits the full width is never broken.
    """
    nonempty = [c for c in cells if c]
    if not nonempty:
        return CELL_PT[0], False

    def titles_fit(size):
        chars = cell_chars(w_pt, size)
        return all(cell_min_height(ev, chars, size) <= h_pt for ev in nonempty)

    def names_fit(size):
        chars = cell_chars(w_pt, size)
        return all(len(word) <= chars
                   for ev in nonempty for year, title, _ in ev
                   if person_suffix(title) is not None
                   for word in f"{year} {title}".split())

    def best_size(with_blurb):
        # One cell in ten may lose detail, the allowance rounded up to whole
        # cells: nine in ten rounded down would let a page of nine cells lose
        # detail in none, and the page would shrink to fit the one rare long
        # entry this rule exists to forgive. That allowance never covers a title.
        allowed = math.ceil(len(nonempty) / 10)
        need = max(1, len(nonempty) - allowed)
        for size in sizes:
            if not (titles_fit(size) and names_fit(size)):
                continue
            fits = sum(
                1 for ev in nonempty
                if cell_blocks(ev, cell_chars(w_pt, size), size, with_blurb)[1] <= h_pt
            )
            if fits >= need:
                return size
        return sizes[-1]

    title_size, blurb_size = best_size(False), best_size(True)
    if blurb_is_worth_it(blurb_size, title_size):
        return blurb_size, True
    return title_size, False


def build_cover(topic, marks, year, size, verified="", tagline=""):
    """The title page: what this is, whose year it is, and how many days it holds."""
    W, H = size
    M = W * 0.09
    n_days = sum(len(v) for m in marks.values() for v in m.values())
    prims = [rect(0, 0, W, H, PAPER)]
    prims.append(text(M, M + 10, "REDLETTER", 13, RUBRIC, weight="bold", spacing=4))
    prims.append(line(M, M + 26, M + 96, M + 26, RUBRIC, 2))

    # The year is set twice the height of the title, so its baseline has to clear
    # the title's descenders rather than follow them by a fixed gap.
    prims.append(text(M, M + 118, topic["title"], 34, INK, weight="bold"))
    prims.append(text(M, M + 210, str(year), 74, INK, weight="bold"))

    parts = []
    if tagline:
        parts += wrap_to(tagline, int((W * 0.62) / max(0.1, text_width("M", 12))))
    for i, ln in enumerate(parts):
        prims.append(text(M, M + 252 + i * 17, ln, 12, GRAY))

    prims.append(line(M, H - M - 44, W - M, H - M - 44, INK, 1))
    plural = "" if n_days == 1 else "s"
    prims.append(text(M, H - M - 20, f"{n_days} day{plural}", 14, INK, weight="bold"))
    if verified:
        prims.append(text(W - M, H - M - 20, f"verified {verified}", 11, FAINT, anchor="end"))
    return prims


def month_geometry(size, year, month):
    """The month page's box, in points: the numbers every cell is laid out in.

    `build_month_page` draws from these, and the tests that measure a cell's
    content measure with them too, so a test cannot pass against geometry the page
    does not use.
    """
    W, H = size
    M = W * 0.045
    weeks = month_days(year, month)
    grid_top = M + 78 + 8
    grid_bottom = H - M - 30
    cell_w = (W - 2 * M) / 7
    row_h = (grid_bottom - grid_top) / len(weeks)
    return {"margin": M, "weeks": weeks, "cell_w": cell_w, "row_h": row_h,
            "grid_top": grid_top, "grid_bottom": grid_bottom,
            "inner_w": cell_w - 8, "inner_h": row_h - 16}


def build_month_page(topic, marks, year, month, size, verified=""):
    """One month, with the day's detail inside its own cell."""
    W, H = size
    geo = month_geometry(size, year, month)
    M = geo["margin"]
    cell_title = 15
    prims = [rect(0, 0, W, H, PAPER)]

    prims.append(text(M, M + 8, "REDLETTER", 9, RUBRIC, weight="bold", spacing=3))
    prims.append(text(M, M + 44, f"{calendar.month_name[month].upper()}  {year}",
                      cell_title * 1.5, INK, weight="bold"))
    prims.append(text(W - M, M + 40, topic["title"], 10, GRAY, anchor="end"))
    prims.append(line(M, M + 58, W - M, M + 58, INK, 1))

    weeks = geo["weeks"]
    head_y = M + 78
    cell_w = geo["cell_w"]
    prims.append(line(M, head_y, W - M, head_y, INK, 0.75))
    for i, wd in enumerate("MTWTFSS"):
        prims.append(text(M + cell_w * (i + 0.5), head_y - 5, wd, 8, GRAY, anchor="middle"))

    grid_top = geo["grid_top"]
    grid_bottom = geo["grid_bottom"]
    # The rows a month actually uses, not a fixed six: February 2027 needs four,
    # and spending two empty rows on it would set the whole page's type smaller.
    rows = len(weeks)
    row_h = geo["row_h"]
    by_month = marks.get(month, {})

    inner_w = geo["inner_w"]
    inner_h = geo["inner_h"]
    cells = [by_month.get(day, []) for week in weeks for day in week]
    cell_pt, with_blurb = choose_cell_type(cells, inner_w, inner_h)
    budget = inner_h
    for c in range(1, 7):
        gx = M + cell_w * c
        prims.append(line(gx, grid_top, gx, grid_bottom, GRID, 0.75))
    for r in range(rows + 1):
        gy = grid_top + row_h * r
        prims.append(line(M, gy, W - M, gy, GRID, 0.75))

    for r, week in enumerate(weeks):
        for c, day in enumerate(week):
            if not day:
                continue
            cx = M + cell_w * c
            cy = grid_top + row_h * r
            events = by_month.get(day, [])
            marked = bool(events)
            prims.append(text(cx + 4, cy + 12, str(day), 10 if marked else 9,
                              RUBRIC if marked else GRAY,
                              weight="bold" if marked else "regular"))
            blocks = truncate_blocks(
                cell_layout(events, cell_chars(inner_w, cell_pt),
                            cell_pt, with_blurb, budget), budget)
            y = cy + 16 + cell_pt
            for s, ssize, ink, indent in blocks:
                prims.append(text(cx + 4 + indent * text_width("M", ssize), y, s, ssize, ink))
                y += ssize * CELL_LEADING

    prims.append(text(M, H - M + 4,
                      "A red date is a day whose sources were read and supported it.",
                      7.5, FAINT))
    if verified:
        prims.append(text(W - M, H - M + 4, f"verified {verified}", 7.5, FAINT, anchor="end"))
    return prims


def build_book(topic, marks, year, size, verified="", tagline=""):
    """A cover, then twelve months. The pages are one document, so they share a size."""
    pages = [build_cover(topic, marks, year, size, verified, tagline)]
    for month in range(1, 13):
        pages.append(build_month_page(topic, marks, year, month, size, verified))
    return pages


def emit_pdf(pages, size_pt, path, dpi=PDF_DPI):
    """Write the pages as one PDF, one page per sheet.

    Pillow writes the raster form; the geometry above is what is being rasterised,
    so the PDF is the same drawing as the PNG at print resolution rather than a
    second rendering path that could disagree with it.
    """
    s = dpi / 72.0
    px = (int(round(size_pt[0] * s)), int(round(size_pt[1] * s)))
    imgs = [draw(scale_prims(p, s), px, ss=1) for p in pages]
    imgs[0].save(path, "PDF", resolution=float(dpi), save_all=True,
                 append_images=imgs[1:], quality=95)


# -------------------------------------------------------------------- main


def topic_of(path) -> dict:
    return json.loads(pathlib.Path(path).read_text())["topic"]


def load_marks(path, year, with_blurb=False):
    """The marks the sheet draws, by month and day.

    `with_blurb` changes the tuple shape: the wall sheet's key prints a date and a
    title, while a month page has room for the blurb as well. Keeping it a flag on
    one loader means the two forms cannot disagree about which days are drawn.
    """
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
        entry = (d["year"], d["title"], d.get("blurb") or "") if with_blurb \
            else (d["year"], d["title"])
        marks.setdefault(month, {}).setdefault(day, []).append(entry)
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
    ap.add_argument("--pdf", action="store_true",
                    help="write the book form: a cover, then one page per month")
    ap.add_argument("--paper", default="a4", choices=sorted(PAPER_MM))
    ap.add_argument("--orientation", default="landscape", choices=["landscape", "portrait"])
    ap.add_argument("--dpi", type=int, default=PDF_DPI)
    args = ap.parse_args()
    if args.pdf and args.month:
        ap.error("--pdf writes the whole book; --month belongs to the wall sheet")

    topic = topic_of(args.days)
    year = args.year or topic.get("print_year") or dt.date.today().year + 1
    marks_meta, marks, skipped = load_marks(args.days, year, with_blurb=args.pdf)
    topic = marks_meta
    verified = json.loads(pathlib.Path(args.days).read_text()).get("generated_on", "")

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"redletter-{topic['id']}-{year}" + (f"-{year}{args.month:02d}" if args.month else "")

    if args.pdf:
        size_pt = page_size_pt(args.paper, args.orientation)
        pages = build_book(topic, marks, year, size_pt, verified, TAGLINE)
        emit_pdf(pages, size_pt, out / f"{stem}.pdf", args.dpi)
        n_marked = sum(len(v) for m in marks.values() for v in m.values())
        print(f"{stem}.pdf: {len(pages)} pages at {args.paper} {args.orientation}, "
              f"{n_marked} marked days")
        for ident, why in skipped:
            print(f"  not drawn: {ident} ({why})")
        return 0

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
