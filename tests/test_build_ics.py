"""Unit tests for the feed: what becomes an event, and what the file looks like.

The point of these is that the `.ics` is checked the way a calendar client reads
it — parsed back, not asserted on the string the writer produced.
"""

from __future__ import annotations

import datetime as dt

import icalendar
import pytest

import build_ics as bi

from conftest import make_day, write_days_file


def build(days, year=2027):
    topic = {"id": "test-topic", "title": "Test Topic", "print_year": year}
    return bi.build(topic, days, year)


def events(cal):
    return [c for c in cal.walk() if isinstance(c, icalendar.Event)]


# --------------------------------------------------------------- what is written


def test_one_event_per_active_day():
    cal, written, skipped = build([make_day("D-1"), make_day("D-2", "05-30")])
    assert len(written) == 2
    assert len(events(cal)) == 2
    assert skipped == []


def test_days_that_did_not_pass_the_gate_are_left_out():
    cal, written, skipped = build([
        make_day("D-1", status="provisional"),
        make_day("D-2", status="contested"),
        make_day("D-3", status="quarantined"),
    ])
    assert written == []
    assert {w for _, w in skipped} == {"provisional", "contested", "quarantined"}


def test_a_29_february_day_is_skipped_in_a_common_year():
    cal, written, skipped = build([make_day("D-LEAP", "02-29", year=1504)], year=2027)
    assert written == []
    assert "29 February" in skipped[0][1]


def test_a_29_february_day_is_written_in_a_leap_year():
    cal, written, _ = build([make_day("D-LEAP", "02-29", year=1504)], year=2028)
    assert len(written) == 1
    assert events(cal)[0]["dtstart"].dt == dt.date(2028, 2, 29)


# ------------------------------------------------------------- how it is read


def test_every_event_is_an_all_day_yearly_event_with_a_uid():
    cal, _, _ = build([make_day("D-1", "04-12", year=1961)])
    ev = events(cal)[0]
    assert isinstance(ev["dtstart"].dt, dt.date)
    assert not isinstance(ev["dtstart"].dt, dt.datetime)
    assert ev["dtstart"].dt == dt.date(2027, 4, 12)
    assert ev["dtend"].dt == dt.date(2027, 4, 13)      # DTEND is exclusive
    freq = ev["rrule"]["FREQ"]
    assert (freq[0] if isinstance(freq, list) else freq) == "YEARLY"
    assert ev["uid"].endswith("@redletter.local")


def test_the_event_body_carries_the_original_date_and_the_sources():
    cal, _, _ = build([make_day("D-1", "04-12", year=1961)])
    body = events(cal)[0]["description"]
    assert "1961-04-12" in body
    assert "example.org" in body and "example.net" in body


def test_validate_accepts_what_the_writer_produced():
    cal, written, _ = build([make_day("D-1")])
    _, problems = bi.validate(cal, written, 2027)
    assert problems == []


def test_validate_catches_a_date_that_does_not_match_the_record():
    cal, written, _ = build([make_day("D-1", "04-12")])
    tampered = [dict(written[0], month_day="04-13")]
    _, problems = bi.validate(cal, tampered, 2027)
    assert any("does not match" in p for p in problems)


def test_validate_catches_a_missing_recurrence():
    cal, written, _ = build([make_day("D-1")])
    ev = events(cal)[0]
    del ev["rrule"]
    _, problems = bi.validate(cal, written, 2027)
    assert any("YEARLY" in p for p in problems)


# ---------------------------------------------------------------- the raw file


def test_the_written_file_is_crlf_utf8_and_folded(tmp_path):
    from conftest import write_days_file

    path = write_days_file(tmp_path / "days.json", [make_day("D-1")])
    topic, days = bi.load(path)
    cal, written, _ = bi.build(topic, days, 2027)
    raw, _ = bi.validate(cal, written, 2027)

    assert raw.count(b"\r\n") > 0
    assert raw.count(b"\n") - raw.count(b"\r\n") == 0, "bare LF would break some clients"
    assert raw.decode("utf-8")
    assert all(len(line) <= 75 for line in raw.split(b"\r\n")), "lines must fold at 75 octets"


def test_a_long_description_still_folds_within_75_octets():
    day = make_day("D-1")
    day["blurb"] = "A very long blurb. " * 30
    cal, written, _ = build([day])
    raw, _ = bi.validate(cal, written, 2027)
    assert all(len(line) <= 75 for line in raw.split(b"\r\n"))
