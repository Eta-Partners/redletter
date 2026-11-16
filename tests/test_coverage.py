"""Unit tests for the density report."""

from __future__ import annotations

import json
import subprocess
import sys

import coverage as cov

from conftest import make_day, write_days_file

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent


def test_counts_only_active_days_per_month(tmp_path):
    path = write_days_file(tmp_path / "days.json", [
        make_day("D-1", "04-12"),
        make_day("D-2", "04-13"),
        make_day("D-3", "11-20"),
        make_day("D-4", "06-16", status="provisional"),
    ])
    data = json.loads(path.read_text())
    per_month, skipped = cov.counts(data["days"], 2027)
    assert per_month[4] == 2 and per_month[11] == 1
    assert sum(per_month.values()) == 3
    assert skipped == [("D-4", "provisional")]


def test_a_29_february_day_is_counted_only_in_a_leap_year():
    days = [make_day("D-LEAP", "02-29", year=1504)]
    assert cov.counts(days, 2028)[0][2] == 1
    per_month, skipped = cov.counts(days, 2027)
    assert per_month[2] == 0
    assert "29 February" in skipped[0][1]


def test_the_report_names_the_months_that_are_short(tmp_path):
    path = write_days_file(tmp_path / "days.json", [make_day("D-1", "04-12")])
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "coverage.py"), str(path), "--target", "2"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert "under target in 12" in proc.stdout, "one day in April leaves eleven months empty"
    assert "APR   1" in proc.stdout
