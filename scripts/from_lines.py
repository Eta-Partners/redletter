#!/usr/bin/env python3
"""Turn a file of `MM-DD | YYYY | sentence | URL | publisher` lines into candidates.

This is the format the repository asks a researcher — human or assistant — to
send. Nothing here decides whether a day is true: it parses the lines, refuses
the ones that are malformed, cross-checks the date against the source's own URL
where the URL carries one, and writes a dataset for `verify_days.py` to judge.

The URL check is the reason this is a script rather than a spreadsheet paste: the
RSC's "on this day" pages carry their date in the slug (`on-this-day-feb-22--…`),
so a line whose date and URL disagree is caught before any network call. It is a
typo check, not a truth check.

Usage:
    from_lines.py research.md --out data/_candidates.yaml [--publisher-name]
"""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import re
import sys

import yaml

MON3 = ["jan", "feb", "mar", "apr", "may", "jun",
        "jul", "aug", "sep", "oct", "nov", "dec"]
MONTHS = ["january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"]

# The RSC writes its article URLs two ways, and both carry the date.
SLUG_DATE = [
    re.compile(r"on-this-day-(?P<mon>[a-z]{3})-(?P<day>\d{2})(?![0-9])"),
    re.compile(r"chemistry-calendar/(?P<mon_word>[a-z]+)-(?P<day>\d{1,2})(?![0-9])"),
]


def parse_line(line: str) -> dict:
    """Split one line into fields, or raise ValueError saying what is wrong."""
    fields = [f.strip() for f in line.split("|")]
    if len(fields) != 5:
        raise ValueError(f"expected 5 fields, found {len(fields)}")
    month_day, year, sentence, url, publisher = fields
    if not re.fullmatch(r"\d{2}-\d{2}", month_day):
        raise ValueError(f"month_day {month_day!r} is not MM-DD")
    month, day = (int(x) for x in month_day.split("-"))
    if not dt.date(2000, month, day):  # 2000 is a leap year: 02-29 parses
        raise ValueError(f"month_day {month_day!r} is not a real date")
    if not re.fullmatch(r"\d{4}", year):
        raise ValueError(f"year {year!r} is not four digits")
    # A PDF or a chat window wraps a long URL with a space in the middle. No URL
    # contains a space, so removing them is safe and recovers the real target.
    url = re.sub(r"\s+", "", url)
    if not url.startswith("https://"):
        raise ValueError(f"url {url!r} is not https")
    if not sentence:
        raise ValueError("sentence is empty")
    return {
        "month_day": month_day,
        "year": int(year),
        "sentence": sentence,
        "url": url,
        "publisher": publisher,
    }


def slug_date(url: str):
    """The month-day a URL claims for itself, or None if it does not claim one."""
    for pattern in SLUG_DATE:
        m = pattern.search(url.lower())
        if not m:
            continue
        if "mon" in m.groupdict():
            name = m.group("mon")
        else:
            name = m.group("mon_word")[:3]
        if name not in MON3:
            return None
        return f"{MON3.index(name) + 1:02d}-{int(m.group('day')):02d}"
    return None


def kind_of(sentence: str) -> str:
    s = sentence.lower()
    if "was born" in s or "is born" in s:
        return "birth"
    if " died" in s or s.endswith("died."):
        return "loss"
    # Where the verb governs the sentence, it is near the front. Looking at the
    # whole string made "Alfred Nobel signed his final will … including an award
    # for the top chemical discovery" a discovery, because the noun appears late.
    head = s[:60]
    if "first" in head:
        return "first"
    if any(w in head for w in ("discover", "isolat", "announc", "prepared",
                               "detected", "identif")):
        return "discovery"
    return "milestone"


def title_of(sentence: str, kind: str, limit: int = 140) -> str:
    """The one line the sheet prints. A compression of the sentence, not a rewrite.

    The limit matches the length the research brief asks for, so a title is never
    the sentence cut in half: the printed sheet does its own measuring and trimming
    (`render_grid.key_columns`), and a title ellipsized here would arrive there
    already damaged.
    """
    if kind in ("birth", "loss"):
        head = sentence.split(",")[0]
        if kind == "birth":
            head = re.split(r"\s+was born", head)[0]
            head = re.sub(r"\s+in\s+[\w\s]+$", "", head)   # "…, born in Warsaw"
        else:
            head = re.split(r"\s+died", head)[0]
        head = head.strip()
        if head and len(head) <= limit:
            return f"{head} is born" if kind == "birth" else f"{head} dies"
    text = sentence.rstrip(".").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def to_record(index: int, parsed: dict, prefix: str = "E") -> dict:
    iso = f"{parsed['year']:04d}-{parsed['month_day']}"
    kind = kind_of(parsed["sentence"])
    title = title_of(parsed["sentence"], kind)
    return {
        "id": f"D-CHE-{prefix}{index:03d}",
        "month_day": parsed["month_day"],
        "year": parsed["year"],
        "kind": kind,
        "title": title,
        "blurb": " ".join(parsed["sentence"].split()),
        "date": {
            "as_recorded": iso,
            "calendar": "gregorian",
            "gregorian": iso,
            "precision": "day",
        },
        "sources": [{
            "type": "reference-data",
            # The publisher and the day's own title, not the first sixty characters
            # of the sentence: a citation cut mid-word ships in the calendar feed.
            "citation": f"{parsed['publisher']} — {title}",
            "url": parsed["url"],
        }],
    }


def read_lines(path) -> tuple[list[dict], list[str]]:
    """Parse a file, returning the good records and one message per rejected line."""
    parsed, problems = [], []
    for n, raw in enumerate(pathlib.Path(path).read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            p = parse_line(line)
        except ValueError as exc:
            problems.append(f"line {n}: {exc}")
            continue
        claimed = slug_date(p["url"])
        if claimed and claimed != p["month_day"]:
            problems.append(
                f"line {n}: date {p['month_day']} but the URL says {claimed}")
            continue
        parsed.append(p)
    return parsed, problems


def build(parsed: list[dict], prefix: str = "E") -> dict:
    ordered = sorted(parsed, key=lambda p: (p["month_day"], p["year"]))
    return {
        "topic": {
            "id": "chemistry",
            "title": "Chemistry",
            "scope": "The days chemistry marks: the discoveries that changed what "
                     "the field could do, and the people who made them.",
            "print_year": 2027,
            "kinds": ["birth", "discovery", "milestone", "first", "loss"],
        },
        "days": [to_record(i, p, prefix) for i, p in enumerate(ordered, 1)],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("lines")
    ap.add_argument("--out", default="data/_candidates.yaml")
    ap.add_argument("--id-prefix", default="E",
                    help="letter for this file's record ids; two research files "
                         "folded together must not share one, or their ids collide")
    args = ap.parse_args()

    parsed, problems = read_lines(args.lines)
    data = build(parsed, args.id_prefix)
    pathlib.Path(args.out).write_text(yaml.safe_dump(data, sort_keys=False,
                                                     width=100, allow_unicode=True))
    for p in problems:
        print(f"REJECT {p}", file=sys.stderr)
    print(f"{len(data['days'])} records → {args.out}; {len(problems)} rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
