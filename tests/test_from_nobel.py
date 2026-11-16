"""Unit tests for the candidate generator: no network, no API.

What matters here is the shape of what lands on disk — a generator that writes a
YAML a person cannot read, or a day with no date, is worse than no generator.
"""

from __future__ import annotations

import yaml

import from_nobel as fn


def laureate(ident="160", name="Jacobus Henricus van 't Hoff", birth="1852-08-30",
             year="1901", motivation="in recognition of his services"):
    return {
        "id": ident,
        "fullName": {"en": name},
        "knownName": {"en": name},
        "birth": {"date": birth, "place": {"country": {"en": "the Netherlands"}}},
        "nobelPrizes": [{
            "awardYear": year,
            "motivation": {"en": motivation},
        }],
    }


def test_a_laureate_becomes_a_day_with_a_real_date():
    day = fn.to_day(laureate(), 1, "che")
    assert day["month_day"] == "08-30"
    assert day["year"] == 1852
    assert day["date"]["gregorian"] == "1852-08-30"
    assert day["sources"][0]["url"].endswith("/160")


def test_a_year_only_date_is_dropped():
    """The API writes 1943-00-00 when only the year is known; that is not a day."""
    assert fn.to_day(laureate(birth="1943-00-00"), 1, "che") is None


def test_a_laureate_with_no_birth_date_is_dropped():
    person = laureate()
    person["birth"] = {}
    assert fn.to_day(person, 1, "che") is None


def test_a_laureate_with_no_prize_is_dropped():
    person = laureate()
    person["nobelPrizes"] = []
    assert fn.to_day(person, 1, "che") is None


def test_the_earliest_prize_is_the_one_quoted():
    person = laureate()
    person["nobelPrizes"] = [
        {"awardYear": "1954", "motivation": {"en": "later"}},
        {"awardYear": "1922", "motivation": {"en": "earlier"}},
    ]
    day = fn.to_day(person, 1, "che")
    assert "1922" in day["blurb"]


def test_shorten_keeps_the_line_readable():
    assert fn.shorten("a  b\n c") == "a b c"
    long = "x " * 200
    assert len(fn.shorten(long, 40)) == 40
    assert fn.shorten(long, 40).endswith("…")


def test_generated_yaml_parses_back_into_the_dataset_shape():
    days = [fn.to_day(laureate(), 1, "che"), fn.to_day(laureate("161", "Emil Fischer",
                                                                "1852-10-09"), 2, "che")]
    topic = {"id": "chemistry", "title": "Chemistry", "scope": "Why not.", "print_year": 2027}
    parsed = yaml.safe_load(fn.yaml_text(topic, days))
    assert parsed["topic"]["id"] == "chemistry"
    assert len(parsed["days"]) == 2
    # YAML reads an unquoted 1852-08-30 as a date; the verifier coerces with str().
    assert str(parsed["days"][0]["date"]["gregorian"]) == "1852-08-30"
    assert parsed["days"][0]["sources"][0]["url"].startswith("https://")


def test_a_quote_in_a_blurb_does_not_break_the_yaml():
    days = [fn.to_day(laureate(name='A "quoted" name'), 1, "che")]
    topic = {"id": "t", "title": "T", "scope": "s", "print_year": 2027}
    parsed = yaml.safe_load(fn.yaml_text(topic, days))
    assert 'A "quoted" name' in parsed["days"][0]["title"]
