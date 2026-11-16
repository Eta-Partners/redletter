#!/usr/bin/env python3
"""Report how many days a topic marks in each month, against a target density.

A calendar with three days in one month and none in seven others is not a
calendar, it is a list. This measures that directly so "make it denser" has a
number attached instead of a feeling.

Usage:
    coverage.py out/days.json [--target 6]
"""

from __future__ import annotations

import argparse
import calendar
import json
import pathlib


def counts(days, year):
    """Active days per month, in the given print year."""
    per_month = {m: 0 for m in range(1, 13)}
    skipped = []
    for d in days:
        if d["status"] != "active":
            skipped.append((d["id"], d["status"]))
            continue
        month, day = (int(x) for x in d["month_day"].split("-"))
        if month == 2 and day == 29 and not calendar.isleap(year):
            skipped.append((d["id"], "no 29 February in {}".format(year)))
            continue
        per_month[month] += 1
    return per_month, skipped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("days", help="out/days.json written by verify_days.py --write")
    ap.add_argument("--target", type=int, default=6, help="days a month should carry")
    ap.add_argument("--year", type=int, default=None)
    args = ap.parse_args()

    data = json.loads(pathlib.Path(args.days).read_text())
    year = args.year or data["topic"].get("print_year") or 2027
    per_month, skipped = counts(data["days"], year)

    width = max(per_month.values()) or 1
    print(f"{data['topic']['title']} — {year}, target {args.target}/month\n")
    for m in range(1, 13):
        n = per_month[m]
        bar = "█" * n
        flag = "  under" if n < args.target else ""
        print(f"{calendar.month_abbr[m].upper()} {n:>3}  {bar:<{max(args.target, width)}}{flag}")

    total = sum(per_month.values())
    short = [calendar.month_abbr[m] for m in range(1, 13) if per_month[m] < args.target]
    print(f"\n{total} active days, {total / 12:.1f} a month on average")
    if short:
        print(f"under target in {len(short)}: {', '.join(short)}")
    for ident, why in skipped:
        print(f"  not counted: {ident} ({why})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
