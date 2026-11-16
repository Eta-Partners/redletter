"""Unit tests for the research handoff format.

The interesting parts are the refusals: a line is cheap to write wrong, and the
only defence before any network call is that a malformed one does not become a
record. The date/URL cross-check is the one check here that catches a *plausible*
mistake rather than a typo.
"""

from __future__ import annotations

import pytest

import from_lines as fl


GOOD = ("05-10 | 1860 | Robert Bunsen and Gustav Kirchhoff discovered caesium in "
        "spring water. | https://edu.rsc.org/resources/on-this-day-may-10--caesium-"
        "was-discovered/10510.article | Royal Society of Chemistry")


# ------------------------------------------------------------------- parsing


def test_a_line_in_the_briefed_format_parses():
    p = fl.parse_line(GOOD)
    assert p["month_day"] == "05-10"
    assert p["year"] == 1860
    assert p["url"].startswith("https://edu.rsc.org/")
    assert p["publisher"] == "Royal Society of Chemistry"


@pytest.mark.parametrize("line", [
    "05-10 | 1860 | only three fields | https://example.org",
    "5-10 | 1860 | short month | https://example.org | Someone",
    "13-01 | 1860 | month thirteen | https://example.org | Someone",
    "02-30 | 1860 | february thirtieth | https://example.org | Someone",
    "05-10 | 60 | short year | https://example.org | Someone",
    "05-10 | 1860 | not https | http://example.org | Someone",
    "05-10 | 1860 |    | https://example.org | Someone",
])
def test_a_malformed_line_is_refused(line):
    with pytest.raises(ValueError):
        fl.parse_line(line)


def test_a_url_wrapped_with_a_space_is_repaired():
    p = fl.parse_line("06-08 | 2016 | x | https://iupac.org/things-and- oganesson/ | IUPAC")
    assert p["url"] == "https://iupac.org/things-and-oganesson/"


# ------------------------------------------------------------ the date check


@pytest.mark.parametrize("url,expected", [
    ("https://edu.rsc.org/resources/on-this-day-may-10--caesium-was-discovered/10510.article",
     "05-10"),
    ("https://edu.rsc.org/resources/on-this-day-feb-06-discovery-of-germanium/10206.article",
     "02-06"),
    ("https://edu.rsc.org/lcredir/learn-chemistry/collections/chemistry-calendar/august-3",
     "08-03"),
    ("https://edu.rsc.org/resources/on-this-day-jan-10--cottrell-was-born/10110.article",
     "01-10"),
])
def test_a_url_states_the_day_it_is_about(url, expected):
    assert fl.slug_date(url) == expected


def test_a_url_without_a_date_claims_nothing():
    assert fl.slug_date("https://www.nobelprize.org/prizes/chemistry/1911/marie-curie/biographical/") is None


def test_a_date_that_contradicts_its_url_is_refused(tmp_path):
    path = tmp_path / "lines.txt"
    path.write_text(
        "05-11 | 1860 | Bunsen and Kirchhoff discover caesium. | "
        "https://edu.rsc.org/resources/on-this-day-may-10--caesium/10510.article | RSC\n"
    )
    parsed, problems = fl.read_lines(path)
    assert parsed == []
    assert "says 05-10" in problems[0]


def test_a_file_keeps_the_lines_it_can_use(tmp_path):
    path = tmp_path / "lines.txt"
    path.write_text(GOOD + "\nnot a line at all\n")
    parsed, problems = fl.read_lines(path)
    assert len(parsed) == 1
    assert len(problems) == 1


def test_blank_lines_and_comments_are_skipped(tmp_path):
    path = tmp_path / "lines.txt"
    path.write_text("\n# a heading\n\n" + GOOD + "\n\n")
    parsed, problems = fl.read_lines(path)
    assert len(parsed) == 1 and problems == []


# ------------------------------------------------------- what gets printed


@pytest.mark.parametrize("sentence,kind", [
    ("Robert Boyle, author of Boyle's law, was born.", "birth"),
    ("Otto Wallach, who studied terpenes, died.", "loss"),
    ("Willard Libby performed the first carbon dating experiment.", "first"),
    ("Clemens Winkler discovered the element germanium.", "discovery"),
    ("The Chemical Society of London held its first meeting.", "first"),
    ("Aldrich Chemical Company was established.", "milestone"),
])
def test_kind_follows_the_sentence(sentence, kind):
    assert fl.kind_of(sentence) == kind


def test_a_birth_title_is_the_name_and_the_event():
    assert fl.title_of("Frederick Gardner Cottrell, inventor of the electrostatic "
                       "precipitator, was born.", "birth") == "Frederick Gardner Cottrell is born"


def test_a_death_title_is_the_name_and_the_event():
    assert fl.title_of("French chemist Paul Vieille, inventor of smokeless powder, "
                       "died.", "loss") == "French chemist Paul Vieille dies"


def test_a_title_that_is_already_short_is_left_alone():
    s = "Clemens Winkler discovered the element germanium."
    assert fl.title_of(s, "discovery") == "Clemens Winkler discovered the element germanium"


def test_a_long_title_is_cut_at_a_word_boundary():
    s = ("A very long sentence about a discovery that keeps going and going well past "
         "any reasonable printed line length for a wall calendar.")
    title = fl.title_of(s, "discovery", limit=40)
    assert len(title) <= 41 and title.endswith("…") and not title.endswith(" …")


# ---------------------------------------------------------------- the dataset


def test_records_are_ordered_by_month_day_not_by_input_order():
    data = fl.build([
        {"month_day": "12-26", "year": 1898, "sentence": "Radium was discovered.",
         "url": "https://edu.rsc.org/x", "publisher": "RSC"},
        {"month_day": "01-15", "year": 1784, "sentence": "Water was announced.",
         "url": "https://edu.rsc.org/y", "publisher": "RSC"},
    ])
    assert [d["month_day"] for d in data["days"]] == ["01-15", "12-26"]
    assert [d["id"] for d in data["days"]] == ["D-CHE-E001", "D-CHE-E002"]


def test_a_record_carries_no_status_of_its_own():
    data = fl.build([{"month_day": "01-15", "year": 1784, "sentence": "Water was announced.",
                      "url": "https://edu.rsc.org/y", "publisher": "RSC"}])
    day = data["days"][0]
    assert "status" not in day
    assert day["date"]["gregorian"] == "1784-01-15"
    assert day["sources"][0]["url"] == "https://edu.rsc.org/y"


def test_two_research_files_do_not_share_an_id_space():
    """Ids are the join key when two files are folded together; E001 twice is a clash."""
    one = fl.build([{"month_day": "01-15", "year": 1784, "sentence": "Water.",
                     "url": "https://a.org/x", "publisher": "A"}], "C")
    two = fl.build([{"month_day": "01-16", "year": 1905, "sentence": "Standards.",
                     "url": "https://b.org/y", "publisher": "B"}], "G")
    assert one["days"][0]["id"] == "D-CHE-C001"
    assert two["days"][0]["id"] == "D-CHE-G001"


def test_a_citation_names_the_publisher_and_the_day_not_half_a_sentence():
    data = fl.build([{"month_day": "01-10", "year": 1877,
                      "sentence": "Frederick Gardner Cottrell, inventor of the "
                                  "electrostatic precipitator, was born.",
                      "url": "https://edu.rsc.org/x", "publisher": "RSC"}])
    citation = data["days"][0]["sources"][0]["citation"]
    assert citation == "RSC — Frederick Gardner Cottrell is born"
    assert not citation.endswith((" ", "electros"))
