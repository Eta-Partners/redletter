"""Unit tests for the sheet: which days reach the grid, and what comes out.

The renderer is checked structurally — how many marks land on the page, which days
are refused, and that the SVG and the PNG agree on the page size — rather than by
comparing pixels, which would fail on any font change without telling anyone
anything useful.
"""

from __future__ import annotations

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
