"""Unit tests for the sheet: which days reach the grid, and what comes out.

The renderer is checked structurally — how many marks land on the page, which days
are refused, and that the SVG and the PNG agree on the page size — rather than by
comparing pixels, which would fail on any font change without telling anyone
anything useful.
"""

from __future__ import annotations

import calendar
import json

import pytest

import render_grid as rg

from conftest import make_day, write_days_file


requires_font = pytest.mark.skipif(
    rg.font_path("regular") is None, reason="no monospace font installed"
)


# ------------------------------------------------------------------ calendars


def test_january_2027_starts_on_a_friday():
    # `calendar` pads with 0, not None, for the days before the 1st.
    weeks = rg.month_days(2027, 1)
    assert weeks[0] == [0, 0, 0, 0, 1, 2, 3]


def test_february_2028_has_a_29th():
    flat = [d for week in rg.month_days(2028, 2) for d in week if d]
    assert flat[-1] == 29
    assert len(flat) == 29


def test_february_2027_has_no_29th():
    flat = [d for week in rg.month_days(2027, 2) for d in week if d]
    assert max(flat) == 28


# --------------------------------------------------------------- which days


def test_only_active_days_are_marked(tmp_path):
    path = write_days_file(tmp_path / "days.json", [
        make_day("D-1", "04-12", status="active"),
        make_day("D-2", "05-30", status="provisional"),
        make_day("D-3", "07-17", status="contested"),
        make_day("D-4", "11-20", status="quarantined"),
    ])
    topic, marks, skipped = rg.load_marks(path, 2027)
    assert list(marks) == [4]
    assert marks[4][12]
    assert {ident for ident, _ in skipped} == {"D-2", "D-3", "D-4"}


def test_a_29_february_day_is_skipped_in_a_common_year(tmp_path):
    path = write_days_file(tmp_path / "days.json", [
        make_day("D-LEAP", "02-29", year=1504, status="active"),
    ])
    _, marks, skipped = rg.load_marks(path, 2027)
    assert marks == {}
    assert skipped and "29 February" in skipped[0][1]


def test_a_29_february_day_is_kept_in_a_leap_year(tmp_path):
    path = write_days_file(tmp_path / "days.json", [
        make_day("D-LEAP", "02-29", year=1504, status="active"),
    ])
    _, marks, _ = rg.load_marks(path, 2028)
    assert marks[2][29]


# -------------------------------------------------------------- the page


def test_year_sheet_marks_exactly_the_active_days(tmp_path):
    path = write_days_file(tmp_path / "days.json", [
        make_day("D-1", "04-12"),
        make_day("D-2", "05-30"),
        make_day("D-3", "07-17", status="provisional"),
    ])
    topic, marks, _ = rg.load_marks(path, 2027)
    prims, size = rg.build_year(topic, marks, 2027, rg.RUBRIC)
    red_cells = [p for p in prims if p["kind"] == "rect" and p["fill"] == rg.RUBRIC]
    assert len(red_cells) == 2
    assert size == (1800, 2400)


def test_month_sheet_is_smaller_and_marks_the_same_day(tmp_path):
    path = write_days_file(tmp_path / "days.json", [make_day("D-1", "04-12")])
    topic, marks, _ = rg.load_marks(path, 2027)
    prims, size = rg.build_month(topic, marks, 2027, 4, rg.RUBRIC)
    assert size == (900, 1000)
    assert len([p for p in prims if p["kind"] == "rect" and p["fill"] == rg.RUBRIC]) == 1


def test_the_key_names_every_marked_day(tmp_path):
    path = write_days_file(tmp_path / "days.json", [make_day("D-1", "04-12", year=1961)])
    topic, marks, _ = rg.load_marks(path, 2027)
    prims, _ = rg.build_year(topic, marks, 2027, rg.RUBRIC)
    lines = [p["s"] for p in prims if p["kind"] == "text"]
    assert any("1961" in s for s in lines), "the year a day happened belongs in the key"
    assert any(s.startswith("APR") for s in lines)


# ------------------------------------------------------------------ emitters


def test_svg_and_png_cover_the_same_page(tmp_path, days_file):
    topic, marks, _ = rg.load_marks(days_file, 2027)
    prims, size = rg.build_year(topic, marks, 2027, rg.RUBRIC)
    svg = tmp_path / "sheet.svg"
    rg.emit_svg(prims, size, svg)
    text = svg.read_text()
    assert text.startswith("<svg")
    assert f'viewBox="0 0 {size[0]} {size[1]}"' in text
    assert text.rstrip().endswith("</svg>")


@requires_font
def test_png_is_written_at_the_supersampled_size(tmp_path, days_file):
    from PIL import Image

    topic, marks, _ = rg.load_marks(days_file, 2027)
    prims, size = rg.build_year(topic, marks, 2027, rg.RUBRIC)
    png = tmp_path / "sheet.png"
    rg.emit_png(prims, size, png)
    with Image.open(png) as im:
        assert im.size == (size[0] * rg.SS, size[1] * rg.SS)


def test_svg_escapes_markup_in_a_title(tmp_path):
    day = make_day("D-1", "04-12")
    day["title"] = "Apollo & Soyuz <dock>"
    path = write_days_file(tmp_path / "days.json", [day])
    topic, marks, _ = rg.load_marks(path, 2027)
    prims, size = rg.build_year(topic, marks, 2027, rg.RUBRIC)
    svg = tmp_path / "sheet.svg"
    rg.emit_svg(prims, size, svg)
    text = svg.read_text()
    assert "Apollo &amp; Soyuz &lt;dock&gt;" in text
    assert "<dock>" not in text


# ------------------------------------------------------------- the key's layout


def test_key_lines_puts_the_date_only_on_the_first_of_two():
    marks = {1: {23: [(1876, "Otto Diels is born"), (1929, "John Polanyi is born")]}}
    lines = rg.key_lines(marks)
    assert lines[0] == ("JAN 23", "1876  Otto Diels is born")
    assert lines[1] == ("", "1929  John Polanyi is born")


def test_the_key_fits_the_page_when_it_is_crowded():
    """Eighty days must not overlap; that is why the layout is measured."""
    lines = [("JAN 01", f"{1800 + i}  A reasonably long chemist's name is born")
             for i in range(80)]
    cols, size, line_h, rows = rg.key_columns(lines, 1800, 120)
    assert rows * cols >= 80, "every line gets a slot"
    assert 46 + rows * line_h <= rg.KEY_BAND + 1, "and the slots fit the band"
    if size >= 13:
        # A chosen (non-fallback) layout must fit its text; the fallback truncates.
        col_w = (1800 - 2 * 120) / cols
        widest = max(rg.text_width(label, size, "bold") + rg.KEY_INDENT
                     + rg.text_width(entry, size) for label, entry in lines)
        assert widest <= col_w


def test_a_small_key_gets_room_to_breathe():
    lines = [("JAN 01", "1900  Someone is born")] * 10
    cols, size, line_h, _ = rg.key_columns(lines, 1800, 120)
    assert cols == 2 and size >= 15 and line_h >= 30


def test_a_dense_key_uses_the_width_it_has():
    """At 115 entries four columns showed about 33 characters of a line; three shows 50."""
    lines = [("JAN 01", f"{1800 + i}  A reasonably long chemist's name is born")
             for i in range(115)]
    cols, size, line_h, rows = rg.key_columns(lines, 1800, 120)
    assert cols == 3, "the key's column count is the lever on how much of a line survives"
    assert 46 + rows * line_h <= rg.KEY_BAND + 1


# ------------------------------------------------------------------- the book


def book_for(path, year=2027, paper="a4", orientation="landscape"):
    """The book as emitted: pages of primitives, the page size in points, the skips."""
    topic, marks, skipped = rg.load_marks(path, year, with_blurb=True)
    size = rg.page_size_pt(paper, orientation)
    return rg.build_book(topic, marks, year, size, "2026-11-15", rg.TAGLINE), size, skipped


def text_of(page):
    return [p["s"] for p in page if p["kind"] == "text"]


@requires_font
def test_the_book_is_a_cover_and_one_page_per_month(days_file):
    pages, _, _ = book_for(days_file)
    assert len(pages) == 13, "a cover and twelve months, as asked"
    assert "REDLETTER" in text_of(pages[0])
    for month in range(1, 13):
        head = calendar.month_name[month].upper()
        assert any(s.startswith(head) for s in text_of(pages[month])), head


def test_the_page_is_measured_in_postscript_points():
    # 210 x 297 mm at 72 points to the inch; landscape turns the sheet over.
    assert rg.page_size_pt("a4", "landscape") == pytest.approx((841.89, 595.28), abs=0.01)
    assert rg.page_size_pt("a4", "portrait") == pytest.approx((595.28, 841.89), abs=0.01)
    assert rg.page_size_pt("letter", "landscape") == pytest.approx((792.0, 612.0), abs=0.01)


@requires_font
def test_the_cover_carries_the_title_the_year_and_the_count(days_file):
    days = [make_day("D-1", "04-12"), make_day("D-2", "05-30")]
    path = write_days_file(days_file.parent.parent / "two.json", days)
    pages, _, _ = book_for(path)
    lines = text_of(pages[0])
    assert "Test Topic" in lines
    assert "2027" in lines
    assert "2 days" in lines


@requires_font
def test_a_one_day_book_says_day_not_days(tmp_path):
    path = write_days_file(tmp_path / "days.json", [make_day("D-1", "04-12")])
    pages, _, _ = book_for(path)
    assert "1 day" in text_of(pages[0])


@requires_font
def test_only_active_days_are_drawn_in_the_book(tmp_path):
    path = write_days_file(tmp_path / "days.json", [
        make_day("D-1", "04-12", status="active"),
        make_day("D-2", "04-13", status="provisional"),
    ])
    pages, _, _ = book_for(path)
    whole_book = " ".join(s for page in pages for s in text_of(page))
    assert "Something happened on 04-12" in whole_book
    assert "04-13" not in whole_book


@requires_font
def test_a_day_prints_inside_the_cell_for_its_weekday(tmp_path):
    path = write_days_file(tmp_path / "days.json", [make_day("D-1", "04-12")])
    pages, size, _ = book_for(path)
    page = pages[4]  # April
    title = [p for p in page if p["kind"] == "text" and p["s"].startswith("1961")]
    assert len(title) == 1, "the year and title print inside the cell"
    assert " ".join(text_of(page)).find("1961 Something happened on 04-12") >= 0
    weeks = rg.month_days(2027, 4)
    row, col = next((r, c) for r, week in enumerate(weeks)
                    for c, day in enumerate(week) if day == 12)
    W, H = size
    M = W * 0.045
    cell_w = (W - 2 * M) / 7
    left, top = M + cell_w * col, M + 86 + (H - M - 30 - (M + 86)) / len(weeks) * row
    assert left <= title[0]["x"] < left + cell_w
    assert top <= title[0]["y"] < top + (H - M - 30 - (M + 86)) / len(weeks)


@requires_font
def test_the_book_is_the_same_document_every_time(days_file):
    first, _, _ = book_for(days_file)
    second, _, _ = book_for(days_file)
    assert first == second


def test_truncation_keeps_the_budget_and_marks_what_it_lost():
    blocks, _ = rg.cell_blocks([(1961, "A title " * 30, "")], 18, 8, False)
    first = rg.truncate_blocks(blocks, 5)
    second = rg.truncate_blocks(blocks, 5)
    assert first == second, "same cell, same lines: truncation is deterministic"
    assert len(first) == 5
    assert first[-1][0].endswith("…")
    assert first[-2][0] != first[-1][0]


@requires_font
def test_a_29_february_day_is_skipped_in_the_book(tmp_path):
    path = write_days_file(tmp_path / "days.json", [
        make_day("D-LEAP", "02-29", year=1504, status="active"),
    ])
    common, _, skipped = book_for(path, year=2027)
    assert skipped and "29 February" in skipped[0][1]
    assert not any("02-29" in s for page in common for s in text_of(page))
    leap, _, skipped = book_for(path, year=2028)
    assert not skipped
    assert any("02-29" in s for s in text_of(leap[2]))


def test_no_line_is_wider_than_the_cell_it_was_wrapped_for():
    """Every line fits, one-word lines included: that is the case the old check skipped.

    It read `if " " in s` and let the single-word lines though, which is exactly
    where a cell's text left the cell: 104 of them across the twelve books at
    337331b, six at the default A4 landscape.
    """
    entries = [
        (1784, "Henry Cavendish announced to the Royal Society that water is a compound", ""),
        (1898, "hexafluoroplatinate, the first noble-gas compound, is reported", ""),
        (1900, "pneumonoultramicroscopicsilicovolcanoconiosis in a date cell", ""),
    ]
    for chars in range(4, 25):
        for entry in entries:
            blocks, _ = rg.cell_blocks([entry], chars, 8, False)
            for s, _, _, indent in blocks:
                assert indent + len(s) <= chars, (chars, indent, s)


def test_a_word_that_fits_the_cell_moves_left_rather_than_breaking():
    """`International` is 13 characters where the hang leaves 8, and that is 6 short.

    It takes the cell's full 14 at indent 0; breaking it would be inventing a split
    for a word the cell has room for.
    """
    entry = (1998, "Zarya opens the International Space Station", "")
    blocks, _ = rg.cell_blocks([entry], 14, 8, False)
    texts = [(s, indent) for s, _, _, indent in blocks]
    assert ("International", 0) in texts, texts
    assert ("Space", 6) in texts, "the next line keeps the hang"
    assert all("-" not in s for s, _ in texts)


def test_a_word_wider_than_the_whole_cell_is_broken_with_no_hyphen():
    """20 characters leaves a 6-character hang and 14 for the word, which is 45.

    So the word is broken at the full width, and nothing is added to it: the pieces
    join back to the word itself.
    """
    word = "pneumonoultramicroscopicsilicovolcanoconiosis"
    blocks, _ = rg.cell_blocks([(1900, word, "")], 20, 8, False)
    lines = [s for s, _, _, indent in blocks]
    assert all(len(s) <= 20 for s in lines), lines
    assert all(indent == 0 for _, _, _, indent in blocks), blocks
    assert "".join(lines[1:]) == word, lines
    assert all("-" not in s for s in lines)


@requires_font
def test_every_line_measures_inside_the_cells_inner_width():
    """The promise in points, not in characters: the font is monospace, so they agree."""
    entry = (1898, "hexafluoroplatinate, the first noble-gas compound, is reported", "")
    for size in (5.0, 7.5, 9.5, 14.0):
        for chars in (4, 8, 13, 20, 40):
            inner = chars * rg.text_width("M", size)
            blocks, _ = rg.cell_blocks([entry], chars, size, False)
            for s, ssize, _, indent in blocks:
                drawn = indent * rg.text_width("M", ssize) + rg.text_width(s, ssize)
                assert drawn <= inner + 0.01, (size, chars, s)


@requires_font
def test_no_line_prints_past_its_cells_right_edge(tmp_path):
    """On the page itself: a day's text stays in its own cell at every paper shape."""
    days = [
        make_day("D-1", "11-20", year=1998),
        make_day("D-2", "03-06", year=1898),
        make_day("D-3", "05-08", year=1900),
    ]
    days[0]["title"] = "Zarya opens the International Space Station"
    days[1]["title"] = "hexafluoroplatinate, the first noble-gas compound, is reported"
    days[2]["title"] = "pneumonoultramicroscopicsilicovolcanoconiosis is reported"
    path = write_days_file(tmp_path / "days.json", days)
    for paper in ("a4", "letter"):
        for orientation in ("landscape", "portrait"):
            pages, size, _ = book_for(path, paper=paper, orientation=orientation)
            W, H = size
            margin = W * 0.045
            cell_w = (W - 2 * margin) / 7
            grid_top, grid_bottom = margin + 86, H - margin - 30
            for page in pages[1:]:
                for p in page:
                    if p["kind"] != "text" or not grid_top <= p["y"] <= grid_bottom:
                        continue
                    w = rg.text_width(p["s"], p["size"], p["weight"])
                    if p["anchor"] == "end":
                        left = p["x"] - w
                    elif p["anchor"] == "middle":
                        left = p["x"] - w / 2
                    else:
                        left = p["x"]
                    col = int((left - margin) // cell_w)
                    assert left >= margin + col * cell_w + 4 - 0.01, (paper, orientation, p["s"])
                    assert left + w <= margin + cell_w * (col + 1) - 4 + 0.01, \
                        (paper, orientation, p["s"])


def test_the_hang_is_dropped_when_the_cell_cannot_afford_it():
    """The threshold is eight characters of room: 8 hangs, 7 keeps the width.

    The widths are literals on purpose. A year of 1961 hangs six characters, so a
    14-character cell leaves 8 and a 13-character cell leaves 7. Written as
    `6 + MIN_HANG_CHARS ...` the test would pass with the constant at 0 too: it
    would show the branch is wired, not that 8 is the number.
    """
    entry = (1961, "A fairly long title that will need to wrap around the cell", "")
    wide, _ = rg.cell_blocks([entry], 14, 8, False)
    assert any(indent == 6 for _, _, _, indent in wide), "8 characters of room: it hangs"
    narrow, _ = rg.cell_blocks([entry], 13, 8, False)
    assert all(indent == 0 for _, _, _, indent in narrow), "7 characters: it keeps the width"


def test_a_blurb_that_costs_exactly_one_and_a_half_points_is_not_preferred():
    """The rule is *less than* 1.5 pt, and type steps by 0.5, so the boundary is real."""
    assert rg.blurb_is_worth_it(8.5, 9.5) is True, "one point below the title"
    assert rg.blurb_is_worth_it(8, 9.5) is False, "exactly 1.5 pt is not less than 1.5"
    assert rg.blurb_is_worth_it(8, 9.0) is True
    assert rg.blurb_is_worth_it(7.5, 8.5) is True, "BLURB_MIN_PT itself is allowed"
    assert rg.blurb_is_worth_it(7, 9.5) is False, "below BLURB_MIN_PT, however cheap"


@requires_font
def test_no_month_page_prints_wide_of_its_paper():
    entry = (1784, "Henry Cavendish announced to the Royal Society that water is a "
                   "compound of hydrogen and oxygen", "")
    marks = {month: {day: [entry] for day in range(1, 29)} for month in range(1, 13)}
    for paper in ("a4", "letter"):
        for orientation in ("landscape", "portrait"):
            size = rg.page_size_pt(paper, orientation)
            page = rg.build_month_page({"title": "Test Topic"}, marks, 2027, 1, size, "2026-11-15")
            W, _ = size
            for p in page:
                if p["kind"] != "text":
                    continue
                w = rg.text_width(p["s"], p["size"], p["weight"])
                if p["anchor"] == "end":
                    left = p["x"] - w
                elif p["anchor"] == "middle":
                    left = p["x"] - w / 2
                else:
                    left = p["x"]
                assert left >= -0.5, (paper, orientation, p["s"])
                assert left + w <= W + 0.5, (paper, orientation, p["s"])


@requires_font
def test_one_long_entry_does_not_set_the_page_type():
    short = [(1970, "A short title", "")]
    long = [(1970, "A very long title that will wrap over many lines and not fit "
                   "the cell at all, however small the type gets", "")]
    short_only, _ = rg.choose_cell_type([short] * 9, 100.0, 60.0)
    mixed, _ = rg.choose_cell_type([short] * 9 + [long], 100.0, 60.0)
    assert mixed == short_only, "one cell in ten may truncate; it may not shrink the page"
    worst, _ = rg.choose_cell_type([long] * 10, 100.0, 60.0)
    assert worst < short_only, "when every cell is long there is nothing to forgive"
