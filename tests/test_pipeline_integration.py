"""Integration tests: the three scripts run as a person runs them.

The local test drives the whole pipeline against a web server this test starts, so
it exercises real HTTP, real YAML, real files on disk and the real command-line
entry points — and it runs offline, in CI, on every push.

The network test runs the same pipeline against the shipped dataset and the real
sources. It is opt-in (`pytest --run-network`) because it fails when a publisher
moves a page, which is a fact about the web rather than about this code.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap

import pytest

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
PY = sys.executable


def run(*args, check=True):
    proc = subprocess.run([PY, *map(str, args)], capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise AssertionError(
            f"{' '.join(map(str, args))} exited {proc.returncode}\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc


def dataset(tmp_path, days):
    path = tmp_path / "data" / "topic.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent("""
        topic:
          id: integration
          title: Integration Topic
          print_year: 2027
          kinds: [first]
        days:
        """) + textwrap.indent(days, "  "))
    return path


def one_day(ident, month_day, year, urls):
    sources = "\n".join(
        f"      - type: archive\n        citation: source {i}\n        url: {u}"
        for i, u in enumerate(urls)
    )
    return f"""- id: {ident}
  month_day: "{month_day}"
  year: {year}
  kind: first
  title: Day {ident}
  blurb: A line about {ident}.
  date:
    as_recorded: {year}-{month_day}
    calendar: gregorian
    gregorian: {year}-{month_day}
    precision: day
  sources:
{sources}
"""


def test_the_whole_pipeline_runs_on_a_local_web(tmp_path, site):
    server, base = site
    port = server.server_port
    # Two spellings of this host resolve to different publisher keys, which is how
    # one machine here stands in for two independent publishers there.
    other = f"http://localhost:{port}"

    server.pages["/good-a"] = "<p>Launched on April 12, 1961.</p>"
    server.pages["/good-b"] = "<p>12 April 1961: the first flight.</p>"
    server.pages["/half"] = "<p>May 30, 2020.</p>"

    data = dataset(tmp_path, "".join([
        one_day("D-OK", "04-12", 1961, [f"{base}/good-a", f"{other}/good-b"]),
        one_day("D-HALF", "05-30", 2020, [f"{base}/half", f"{base}/missing"]),
        one_day("D-DEAD", "07-17", 1975, [f"{base}/missing", f"{base}/gone"]),
    ]))

    out = tmp_path / "out"
    run(ROOT / "scripts" / "verify_days.py", data, "--write", "--out", out, "--timeout", "5")

    report = json.loads((out / "verification.json").read_text())
    status = {d["id"]: d for d in report["days"]}
    assert status["D-OK"]["status"] == "active"
    assert status["D-OK"]["publishers"] == ["0.1", "localhost"]
    assert status["D-HALF"]["status"] == "provisional"
    assert status["D-HALF"]["agreement"] == "1 of 2"
    assert status["D-DEAD"]["status"] == "quarantined"
    assert report["summary"] == {"active": 1, "provisional": 1, "contested": 0, "quarantined": 1}

    days = out / "days.json"
    assert days.exists()
    assert {d["id"] for d in json.loads(days.read_text())["days"]} == {"D-OK", "D-HALF", "D-DEAD"}

    run(ROOT / "scripts" / "render_grid.py", days, "--out", out)
    assert (out / "redletter-integration-2027.png").exists()
    assert (out / "redletter-integration-2027.svg").exists()

    run(ROOT / "scripts" / "build_ics.py", days, "--out", out)
    ics = (out / "redletter-integration-2027.ics").read_bytes()
    assert ics.count(b"BEGIN:VEVENT") == 1, "only the active day reaches the feed"
    assert b"DTSTART;VALUE=DATE:20270412" in ics
    assert b"RRULE:FREQ=YEARLY" in ics


def test_a_failed_fetch_does_not_stop_the_run(tmp_path, site):
    server, base = site
    server.pages["/ok"] = "<p>April 12, 1961.</p>"
    data = dataset(tmp_path, "".join([
        one_day("D-OK", "04-12", 1961, [f"{base}/ok", "http://127.0.0.1:1/refused"]),
    ]))
    out = tmp_path / "out"
    proc = run(ROOT / "scripts" / "verify_days.py", data, "--write", "--out", out, "--timeout", "2")
    assert "PROV" in proc.stdout
    report = json.loads((out / "verification.json").read_text())
    source = report["days"][0]["sources"][1]
    assert source["read"] is False and source["supports"] is None


def test_the_ics_fails_loudly_when_the_contract_is_broken(tmp_path, site):
    """A day with no sources cannot be written; the writer must not invent one."""
    server, base = site
    data = dataset(tmp_path, """- id: D-EMPTY
  month_day: "04-12"
  year: 1961
  kind: first
  title: No sources
  blurb: Nothing to check.
  date:
    as_recorded: 1961-04-12
    calendar: gregorian
    gregorian: 1961-04-12
    precision: day
  sources: []
""")
    out = tmp_path / "out"
    run(ROOT / "scripts" / "verify_days.py", data, "--write", "--out", out, "--timeout", "2")
    report = json.loads((out / "verification.json").read_text())
    assert report["days"][0]["status"] == "quarantined"

    proc = run(ROOT / "scripts" / "build_ics.py", out / "days.json", "--out", out, check=False)
    assert proc.returncode == 0
    assert (out / "redletter-integration-2027.ics").read_bytes().count(b"BEGIN:VEVENT") == 0


@pytest.mark.network
def test_the_shipped_dataset_verifies_against_the_real_sources(tmp_path):
    out = tmp_path / "out"
    run(ROOT / "scripts" / "verify_days.py", ROOT / "data" / "spaceflight.yaml",
        "--write", "--out", out, "--timeout", "30")
    report = json.loads((out / "verification.json").read_text())
    assert len(report["days"]) == 10
    for day in report["days"]:
        assert day["sources"], f"{day['id']} has no sources"
        for source in day["sources"]:
            assert source["read"] or source.get("error"), "an unread source must say why"
    assert report["summary"]["active"] >= 8, "most of the shipped days should still hold"

    run(ROOT / "scripts" / "render_grid.py", out / "days.json", "--out", out)
    run(ROOT / "scripts" / "build_ics.py", out / "days.json", "--out", out)
    assert (out / "redletter-crewed-spaceflight-2027.ics").exists()
