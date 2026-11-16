#!/usr/bin/env python3
"""Write the feed: one all-day, yearly-repeating event per active day.

This is the other half of the product. The printed sheet is a *dated* year: the
mark falls on a real 2027 date. A calendar subscription is a *recurrence*: the
mark falls on month-day every year, forever, and the year something happened is
carried in the description rather than in the date.

Only `status: active` days are written. The file is parsed back before it is
written to disk, so a broken feed fails here instead of in somebody's calendar.

Usage:
    build_ics.py out/days.json [--year 2027] [--out out]
"""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import json
import pathlib

import icalendar

UID_DOMAIN = "redletter.local"


def load(path):
    data = json.loads(pathlib.Path(path).read_text())
    return data["topic"], data["days"]


def build(topic, days, year):
    cal = icalendar.Calendar()
    cal.add("prodid", "-//Redletter//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("x-wr-calname", f"{topic['title']} — red-letter days")
    cal.add(
        "x-wr-caldesc",
        "Days a field marks in red. Each day was checked against its sources "
        f"before it was added; verified {dt.date.today().isoformat()}.",
    )

    written, skipped = [], []
    for d in days:
        if d["status"] != "active":
            skipped.append((d["id"], d["status"]))
            continue
        month, day = (int(x) for x in d["month_day"].split("-"))
        if month == 2 and day == 29 and not calendar.isleap(year):
            skipped.append((d["id"], "29 February is not on the {year} sheet".format(year=year)))
            continue

        start = dt.date(year, month, day)
        ev = icalendar.Event()
        ev.add("uid", f"{d['id']}@{UID_DOMAIN}")
        ev.add("dtstamp", dt.datetime.now(dt.timezone.utc))
        ev.add("summary", d["title"])
        ev.add("dtstart", start)                       # DATE value: an all-day event
        ev.add("dtend", start + dt.timedelta(days=1)) # DTEND is exclusive for all-day
        ev.add("rrule", {"freq": "YEARLY"})
        ev.add("transp", "TRANSPARENT")               # it does not make you busy
        ev.add("categories", ["Redletter", d["kind"]])
        ev.add(
            "description",
            f"{d['blurb']}\n\n"
            f"Happened: {d['date']['gregorian']}"
            f" ({d['date']['calendar']} calendar, {d['date']['precision']} precision)\n"
            f"Checked against {len(d['sources'])} sources, {d['agreement']} supporting the day.\n"
            + "\n".join(f"· {s['citation']} — {s['url']}" for s in d["sources"]),
        )
        # An event carries one URL property, so the first source goes there and the
        # whole list lives in the description where a reader will actually see it.
        ev.add("url", d["sources"][0]["url"])
        cal.add_component(ev)
        written.append(d)

    return cal, written, skipped


def validate(cal, written, year):
    """Read the file back the way a calendar client would, and check what came out."""
    raw = cal.to_ical()
    back = icalendar.Calendar.from_ical(raw)
    events = [c for c in back.walk() if isinstance(c, icalendar.Event)]

    problems = []
    if len(events) != len(written):
        problems.append(f"{len(events)} events parsed, {len(written)} written")

    for ev, d in zip(sorted(events, key=lambda e: e["summary"].to_ical()), sorted(
            written, key=lambda d: d["title"])):
        start = ev["dtstart"].dt
        if isinstance(start, dt.datetime):
            problems.append(f"{d['id']}: DTSTART is a datetime, not a date — not all-day")
        if start.year != year:
            problems.append(f"{d['id']}: DTSTART year {start.year}, expected {year}")
        if f"{start.month:02d}-{start.day:02d}" != d["month_day"]:
            problems.append(f"{d['id']}: DTSTART {start} does not match month_day {d['month_day']}")
        rrule = ev.get("RRULE")
        freq = rrule.get("FREQ") if rrule is not None else None
        if isinstance(freq, list):
            freq = freq[0] if freq else None
        if freq != "YEARLY":
            problems.append(f"{d['id']}: no YEARLY recurrence (FREQ={freq!r})")
        if not ev.get("UID"):
            problems.append(f"{d['id']}: no UID")
    return raw, problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("days")
    ap.add_argument("--year", type=int, default=None)
    ap.add_argument("--out", default="out")
    args = ap.parse_args()

    topic, days = load(args.days)
    year = args.year or topic.get("print_year") or dt.date.today().year + 1
    cal, written, skipped = build(topic, days, year)
    raw, problems = validate(cal, written, year)

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"redletter-{topic['id']}-{year}.ics"
    path.write_bytes(raw)

    print(f"{path}: {len(written)} all-day events, yearly, starting {year}")
    for d in written:
        print(f"  {d['month_day'][0:2]}-{d['month_day'][3:5]}  {d['year']}  {d['title']}")
    for ident, why in skipped:
        print(f"  not written: {ident} ({why})")
    if problems:
        print("\nVALIDATION FAILED:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\nread back clean: every event is an all-day date with a YEARLY rule and a UID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
