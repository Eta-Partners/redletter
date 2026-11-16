"""Shared fixtures for the Redletter tests.

The scripts are not a package — they are three files a person runs — so the test
suite imports them by path rather than asking the project to grow a module layout
it does not need.
"""

from __future__ import annotations

import json
import pathlib
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tools"))


def pytest_addoption(parser):
    parser.addoption(
        "--run-network",
        action="store_true",
        default=False,
        help="also run tests that fetch the real sources over the internet",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-network"):
        return
    skip = pytest.mark.skip(reason="needs the internet; run with --run-network")
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip)


def make_day(ident="D-0001", month_day="04-12", year=1961, status="active", sources=None):
    """A day record shaped like the verifier's output, which is what both writers read."""
    return {
        "id": ident,
        "month_day": month_day,
        "title": f"Something happened on {month_day}",
        "kind": "first",
        "blurb": "A short line about it.",
        "year": year,
        "date": {
            "as_recorded": f"{year}-{month_day}",
            "calendar": "gregorian",
            "gregorian": f"{year}-{month_day}",
            "precision": "day",
        },
        "status": status,
        "agreement": "2 of 2",
        "publishers": ["example.org", "example.net"],
        "checked_on": "2026-11-15",
        "sources": sources
        or [
            {"citation": "One", "url": "https://example.org/a", "type": "archive",
             "http": 200, "read": True, "supports": True},
            {"citation": "Two", "url": "https://example.net/b", "type": "reference-data",
             "http": 200, "read": True, "supports": True},
        ],
        "approved_hash": "0" * 64,
    }


def write_days_file(path, days, topic=None):
    payload = {
        "topic": topic or {"id": "test-topic", "title": "Test Topic", "print_year": 2027},
        "generated_on": "2026-11-15",
        "days": days,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    return path


@pytest.fixture
def days_file(tmp_path):
    return write_days_file(tmp_path / "out" / "days.json", [make_day()])


# ------------------------------------------------------------------ local web


class _Handler(BaseHTTPRequestHandler):
    pages: dict = {}

    def do_GET(self):  # noqa: N802 - http.server's spelling
        body = self.pages.get(self.path)
        if body is None:
            self.send_response(404)
            self.end_headers()
            return
        raw = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass


@pytest.fixture
def site():
    """A local web server; point it at pages, and it serves them for the test."""
    handler = type("H", (_Handler,), {"pages": {}})
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    server.pages = handler.pages
    yield server, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join(timeout=5)
