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

from PIL import Image, ImageDraw, ImageFont

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
            f = FONTS.get(p["size"], p["weight"], ss=ss)
            anchor = {"start": "ls", "middle": "ms", "end": "rs"}[p["anchor"]]
            if p["spacing"]:
                x = p["x"]
                for ch in p["s"]:
                    d.text((x * ss, p["y"] * ss), ch, font=f, fill=p["fill"], anchor=anchor)
                    x += f.getlength(ch) / ss + p["spacing"]
            else:
                d.text((p["x"] * ss, p["y"] * ss), p["s"], font=f, fill=p["fill"], anchor=anchor)
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


def cell_blocks(events, chars, size, with_blurb):
    """One cell's lines and the height they need, as (text, size, ink, indent).

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
    title by grey and 0.86x type, and sharing the hang costs a step of type on the
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
    blocks, height = [], 0.0
    for year, title, blurb in events:
        head = str(year)
        hang = len(head) + 2
        if chars - hang < MIN_HANG_CHARS:
            hang = 0
        wrapped = wrap_to(f"{head}  {title}", chars)
        lines = fit_to_width([wrapped[0]], chars, 0)
        rest = " ".join(wrapped[1:])
        if rest:
            lines += fit_to_width(wrap_to(rest, chars - hang), chars, hang)
        for ln, indent in lines:
            blocks.append((ln, size, INK, indent))
            height += size * CELL_LEADING
        if with_blurb and blurb:
            bsize = size * BLURB_SCALE
            for ln, _ in fit_to_width(wrap_to(blurb, chars), chars, 0):
                blocks.append((ln, bsize, GRAY, 0))
                height += bsize * CELL_LEADING
    return blocks, height


def cell_line_budget(inner_h_pt, size_pt):
    """How many lines a cell can hold at this size before it runs into the next row."""
    return max(1, int(inner_h_pt // (size_pt * CELL_LEADING)))


def truncate_blocks(blocks, budget):
    """Keep a cell inside its box, and say so with an ellipsis.

    One 132-character entry — a Nobel citation quoted whole — would otherwise set
    the type size for every cell on the page. The sheet already truncates its key
    the same way; a short line that ends in … is honest about being short.
    """
    if len(blocks) <= budget:
        return blocks
    kept = blocks[:budget]
    s, size, ink, indent = kept[-1]
    if len(s) > 1:
        kept[-1] = (s[:-1].rstrip() + "…", size, ink, indent)
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
    """The type size that fits the page, allowing a rare cell to truncate.

    Sizing on the *worst* cell lets one long entry shrink a whole month, which is
    the wrong trade: nine cells set too small to teach a whole page to fit one.
    A page is accepted when nine cells in ten hold their text, and the tenth
    truncates. Detail is preferred over size only while it costs less than a point
    and a half of type.
    """
    nonempty = [c for c in cells if c]
    if not nonempty:
        return CELL_PT[0], False

    def best_size(with_blurb):
        # One cell in ten may truncate, the allowance rounded up to whole cells:
        # nine in ten rounded down would let a page of nine cells truncate none,
        # and the page would shrink to fit the one rare long entry this rule
        # exists to forgive.
        allowed = math.ceil(len(nonempty) / 10)
        need = max(1, len(nonempty) - allowed)
        for size in sizes:
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


def build_month_page(topic, marks, year, month, size, verified=""):
    """One month, with the day's detail inside its own cell."""
    W, H = size
    M = W * 0.045
    cell_title = 15
    prims = [rect(0, 0, W, H, PAPER)]

    prims.append(text(M, M + 8, "REDLETTER", 9, RUBRIC, weight="bold", spacing=3))
    prims.append(text(M, M + 44, f"{calendar.month_name[month].upper()}  {year}",
                      cell_title * 1.5, INK, weight="bold"))
    prims.append(text(W - M, M + 40, topic["title"], 10, GRAY, anchor="end"))
    prims.append(line(M, M + 58, W - M, M + 58, INK, 1))

    weeks = month_days(year, month)
    head_y = M + 78
    cell_w = (W - 2 * M) / 7
    prims.append(line(M, head_y, W - M, head_y, INK, 0.75))
    for i, wd in enumerate("MTWTFSS"):
        prims.append(text(M + cell_w * (i + 0.5), head_y - 5, wd, 8, GRAY, anchor="middle"))

    grid_top = head_y + 8
    grid_bottom = H - M - 30
    # The rows a month actually uses, not a fixed six: February 2027 needs four,
    # and spending two empty rows on it would set the whole page's type smaller.
    rows = len(weeks)
    row_h = (grid_bottom - grid_top) / rows
    by_month = marks.get(month, {})

    inner_w = cell_w - 8
    inner_h = row_h - 16
    cells = [by_month.get(day, []) for week in weeks for day in week]
    cell_pt, with_blurb = choose_cell_type(cells, inner_w, inner_h)
    budget = cell_line_budget(inner_h, cell_pt)

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
            blocks, _ = cell_blocks(events, cell_chars(inner_w, cell_pt),
                                    cell_pt, with_blurb)
            y = cy + 16 + cell_pt
            for s, ssize, ink, indent in truncate_blocks(blocks, budget):
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
