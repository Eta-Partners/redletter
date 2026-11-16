"""Unit tests for the gate: date matching, publisher grouping, and the status rule.

These never touch the network. `fetch` is replaced with a function that returns
whatever page the test says a URL would return, so every branch of the status
rule can be exercised exactly.
"""

from __future__ import annotations

import datetime as dt

import pytest

import verify_days as vd

from conftest import source_page


def page(*phrases):
    """A readable page — see `conftest.source_page` for why size matters here."""
    return source_page(*phrases)


class FakeWeb:
    """A stand-in for the internet: a mapping from URL to page, or to an exception."""

    def __init__(self, pages):
        self.pages = pages

    def __call__(self, url, timeout):
        value = self.pages[url]
        if isinstance(value, Exception):
            raise value
        return 200, value


def day_with(urls, iso="1961-04-12"):
    return {
        "id": "D-TEST",
        "month_day": iso[5:],
        "title": "A day",
        "kind": "first",
        "blurb": "A line about it.",
        "year": int(iso[:4]),
        "date": {"as_recorded": iso, "calendar": "gregorian", "gregorian": iso, "precision": "day"},
        "sources": [{"citation": f"source {i}", "url": u, "type": "archive"}
                    for i, u in enumerate(urls)],
    }


# --------------------------------------------------------------- date matching


@pytest.mark.parametrize("value", ["1961-04-12", dt.date(1961, 4, 12)])
def test_a_iso_string_and_a_yaml_date_are_both_accepted(value):
    # YAML hands an unquoted 1961-04-12 back as a date, so a dataset does not have
    # to quote every date for the matcher's sake.
    assert vd.supports("<p>April 12</p>", value)


@pytest.mark.parametrize("phrase", [
    "April 12, 1961", "12 April 1961", "Apr 12, 1961", "12 Apr 1961",
    "1961-04-12", "12 april", "april 12",
])
def test_supports_finds_every_written_form(phrase):
    assert vd.supports(f"<p>{phrase}</p>", "1961-04-12")


@pytest.mark.parametrize("phrase", [
    # The RSC titles its pages "On This Day - Mar 06": month abbreviated, day
    # zero-padded, year further down the page. An enumerated list of written
    # forms missed this one and reported 30 real days as contested.
    "On This Day – Mar 06 : Mendeleev's Periodic Table",
    "Mar 06", "06 Mar", "March 06", "6 March", "March 6, 1869",
])
def test_supports_reads_the_form_the_rsc_prints(phrase):
    assert vd.supports(f"<p>{phrase}</p>", "1869-03-06")


@pytest.mark.parametrize("phrase", ["Mar 16", "March 2026", "March 60",
                                    "March 1869", "Apr 06"])
def test_a_zero_padded_day_does_not_match_its_neighbours(phrase):
    assert not vd.supports(f"<p>{phrase}</p>", "1869-03-06")


@pytest.mark.parametrize("phrase", [
    "April 13, 1961", "April 1961", "April 120", "March 12, 1961", "12 March",
])
def test_supports_does_not_reach_for_a_neighbouring_date(phrase):
    assert not vd.supports(f"<p>{phrase}</p>", "1961-04-12")


def test_supports_collapses_whitespace_and_ignores_case():
    page_text = "<p>on   12\n\n   APRIL    1961 he flew</p>"
    assert vd.supports(page_text, "1961-04-12")


def test_supports_does_not_match_a_different_day():
    assert not vd.supports("<p>April 13, 1961</p>", "1961-04-12")


# ------------------------------------------------------------------ publishers


@pytest.mark.parametrize("url,expected", [
    ("https://en.wikipedia.org/wiki/Vostok_1", "wikipedia.org"),
    ("https://www.nasa.gov/history/thing/", "nasa.gov"),
    ("https://en.cmse.gov.cn/a/b.html", "gov.cn"),
    ("http://127.0.0.1:8000/x", "0.1"),
    ("https://example.org", "example.org"),
])
def test_publisher_reduces_a_url_to_two_labels(url, expected):
    assert vd.publisher(url) == expected


def test_two_wikipedia_articles_are_one_publisher():
    assert vd.publisher("https://en.wikipedia.org/wiki/Zarya") == \
        vd.publisher("https://en.wikipedia.org/wiki/International_Space_station")


# ---------------------------------------------------------------- status rule


def run_day(monkeypatch, pages, iso="1961-04-12"):
    day = day_with(list(pages), iso)
    monkeypatch.setattr(vd, "fetch", FakeWeb(pages))
    return vd.verify_day(day, timeout=1)


def test_active_needs_two_agreeing_publishers(monkeypatch):
    out = run_day(monkeypatch, {
        "https://a.org/x": page("April 12, 1961"),
        "https://b.org/y": page("12 April 1961"),
    })
    assert out["status"] == "active"
    assert out["agreement"] == "2 of 2"
    assert out["publishers"] == ["a.org", "b.org"]


def test_same_publisher_twice_is_only_provisional(monkeypatch):
    out = run_day(monkeypatch, {
        "https://a.org/x": page("April 12, 1961"),
        "https://a.org/y": page("12 April 1961"),
    })
    assert out["status"] == "provisional"
    assert out["agreement"] == "2 of 2"
    assert out["publishers"] == ["a.org"]


def test_one_agreeing_source_is_provisional(monkeypatch):
    out = run_day(monkeypatch, {
        "https://a.org/x": page("April 12, 1961"),
        "https://b.org/y": page("nothing to see"),
    })
    assert out["status"] == "provisional"
    assert out["agreement"] == "1 of 2"


def test_read_but_disagreeing_is_contested(monkeypatch):
    out = run_day(monkeypatch, {
        "https://a.org/x": page("April 13, 1961"),
        "https://b.org/y": page("12 May 1961"),
    })
    assert out["status"] == "contested"
    assert out["agreement"] == "0 of 2"


def test_nothing_readable_is_quarantined(monkeypatch):
    out = run_day(monkeypatch, {
        "https://a.org/x": OSError("connection refused"),
        "https://b.org/y": TimeoutError("too slow"),
    })
    assert out["status"] == "quarantined"
    assert out["agreement"] == "0 of 2", "cited sources, not readable ones"
    assert out["readable"] == 0
    assert all(s["read"] is False for s in out["sources"])


def test_an_unreadable_source_is_not_treated_as_disagreement(monkeypatch):
    """The distinction the script exists for: unread is not the same as wrong."""
    out = run_day(monkeypatch, {
        "https://a.org/x": page("April 12, 1961"),
        "https://b.org/y": OSError("connection refused"),
    })
    assert out["status"] == "provisional"     # not "contested"
    assert out["agreement"] == "1 of 2", "the unread source still counts in the total"
    assert out["readable"] == 1
    assert out["sources"][1]["supports"] is None


# -------------------------------------------------------------- approval hash


def test_approval_hash_is_stable_across_whitespace():
    a = day_with(["https://a.org/x"])
    b = dict(a, blurb="A line\n   about it.")
    assert vd.approval_hash(a) == vd.approval_hash(b)


@pytest.mark.parametrize("field,value", [
    ("title", "A different title"),
    ("blurb", "A different line."),
    ("kind", "loss"),
    ("month_day", "04-13"),
])
def test_approval_hash_changes_when_the_printable_content_changes(field, value):
    a = day_with(["https://a.org/x"])
    assert vd.approval_hash(a) != vd.approval_hash(dict(a, **{field: value}))


def test_approval_hash_ignores_sources_and_status():
    a = day_with(["https://a.org/x"])
    b = dict(a, sources=[], status="contested")
    assert vd.approval_hash(a) == vd.approval_hash(b)


# ---------------------------------------------------------------- authorities


ALLOWLIST = {"acs.org": "American Chemical Society", "rsc.org": "Royal Society of Chemistry"}


def test_one_allowlisted_source_is_enough(monkeypatch):
    day = day_with(["https://pubs.acs.org/doi/10.1021/xyz"])
    monkeypatch.setattr(vd, "fetch", FakeWeb({"https://pubs.acs.org/doi/10.1021/xyz":
                                              page("April 12, 1961")}))
    out = vd.verify_day(day, timeout=1, allowlist=ALLOWLIST)
    assert out["status"] == "active"
    assert out["basis"] == "authority: American Chemical Society"
    assert out["authorities"] == ["American Chemical Society"]


def test_one_source_outside_the_allowlist_is_not_enough(monkeypatch):
    day = day_with(["https://en.wikipedia.org/wiki/Thing"])
    monkeypatch.setattr(vd, "fetch", FakeWeb({"https://en.wikipedia.org/wiki/Thing":
                                              page("April 12, 1961")}))
    out = vd.verify_day(day, timeout=1, allowlist=ALLOWLIST)
    assert out["status"] == "provisional"
    assert out["basis"] == ""


def test_an_authority_that_does_not_support_the_date_changes_nothing(monkeypatch):
    day = day_with(["https://pubs.acs.org/doi/10.1021/xyz"])
    monkeypatch.setattr(vd, "fetch", FakeWeb({"https://pubs.acs.org/doi/10.1021/xyz":
                                              page("a page about something else")}))
    out = vd.verify_day(day, timeout=1, allowlist=ALLOWLIST)
    assert out["status"] == "contested"


def test_an_unreadable_authority_is_still_quarantined(monkeypatch):
    day = day_with(["https://pubs.acs.org/doi/10.1021/xyz"])
    monkeypatch.setattr(vd, "fetch", FakeWeb({"https://pubs.acs.org/doi/10.1021/xyz":
                                              OSError("gone")}))
    out = vd.verify_day(day, timeout=1, allowlist=ALLOWLIST)
    assert out["status"] == "quarantined"


def test_two_publishers_still_win_over_the_allowlist(monkeypatch):
    day = day_with(["https://a.org/x", "https://b.org/y"])
    monkeypatch.setattr(vd, "fetch", FakeWeb({
        "https://a.org/x": page("April 12, 1961"),
        "https://b.org/y": page("12 April 1961"),
    }))
    out = vd.verify_day(day, timeout=1, allowlist=ALLOWLIST)
    assert out["status"] == "active"
    assert out["basis"] == "two publishers"


@pytest.mark.parametrize("host,vouched", [
    ("pubs.acs.org", True),
    ("www.acs.org", True),
    ("acs.org", True),
    ("notacs.org", False),
    ("acs.org.example.com", False),
])
def test_authority_matching_is_on_the_host_boundary(host, vouched):
    assert bool(vd.authority_for(f"https://{host}/x", ALLOWLIST)) is vouched


# ------------------------------------------------------------ the block floor
#
# acs.org answers a non-browser client with HTTP 200 and 212 bytes of challenge
# script. Before the floor, the gate called that "read, no match" — reporting a
# blocked door as a source that disagrees about the date. It is a door.

BOT_WALL = ('<html><head><META NAME="robots" CONTENT="noindex,nofollow">'
            '<script src="/_Incapsula_Resource?SWJIYLWA=1"></script>'
            '</head><body></body></html>')


def test_a_bot_wall_is_unread_rather_than_disagreeing(monkeypatch):
    out = run_day(monkeypatch, {"https://www.acs.org/x": BOT_WALL})
    assert out["status"] == "quarantined"
    assert out["sources"][0]["read"] is False
    assert "blocked or empty" in out["sources"][0]["error"]


def test_a_bot_wall_does_not_turn_a_day_contested(monkeypatch):
    """One readable source that agrees, one wall: still provisional, not contested."""
    out = run_day(monkeypatch, {
        "https://a.org/x": page("April 12, 1961"),
        "https://www.acs.org/x": BOT_WALL,
    })
    assert out["status"] == "provisional"
    assert out["agreement"] == "1 of 2"
    assert out["readable"] == 1


def test_the_floor_counts_visible_text_not_markup():
    page_markup = "<div>" + "<span class='x'></span>" * 400 + "April 12, 1961</div>"
    assert len(vd.visible_text(page_markup)) < vd.MIN_TEXT


def test_visible_text_drops_script_bodies():
    assert "alert" not in vd.visible_text('<script>alert(1)</script><p>April 12</p>')
