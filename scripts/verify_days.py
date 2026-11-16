#!/usr/bin/env python3
"""Ask three questions of every day in a dataset and write what the answers were.

1. Does the source exist and match what the record claims about it?
2. Does the source support the date?
3. Do independent sources agree on the day, and in which calendar?

The third question is why this script exists. A record that was typed from memory
and never fetched cannot tell you whether its sources agree, so it cannot earn a
place on a wall. Nothing here invents a verdict: a source that would not load is
reported as unread, not as disagreement, and the day's status follows from what
was actually read.

Usage:
    verify_days.py data/spaceflight.yaml [--write] [--timeout 20] [--out out]

Writes out/verification.json always. With --write, also writes out/days.json:
the canonical records the renderer and the .ics writer consume, with status,
source agreement and an approval hash computed from the printable content.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

import yaml

UA = "redletter-verify/0.1 (+https://github.com/tjmustard/redletter)"
MONTHS = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]

# A page with less visible text than this is a bot wall or an error stub, not a
# document. acs.org answers a non-browser client with HTTP 200 and 212 bytes of
# challenge script; without this floor the gate calls that "read, no match",
# which reports a blocked door as a source that disagrees.
MIN_TEXT = 400


def visible_text(page: str) -> str:
    page = re.sub(r"<(script|style)\b.*?</\1>", " ", page, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", page)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def fetch(url: str, timeout: int) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        charset = r.headers.get_content_charset() or "utf-8"
        return r.status, raw.decode(charset, "replace")


def date_pattern(iso: str) -> re.Pattern:
    """One pattern covering the ways a page writes a date.

    The RSC titles its pages "On This Day – Mar 06", with the month abbreviated
    and the day zero-padded; other pages write "6 March 1869" or "March 6, 1869".
    An enumerated list of strings missed the first form entirely and reported 30
    real days as contested, so this matches the shapes rather than the strings.
    """
    d = dt.date.fromisoformat(str(iso))
    month = MONTHS[d.month - 1]
    names = rf"(?:{month}|{month[:3]})"
    day = rf"(?<![0-9])0?{d.day}(?![0-9])"     # "6" and "06" are both printed
    return re.compile(
        rf"{names}\s+{day}|{day}\s+{names}|{d.year}-{d.month:02d}-{d.day:02d}",
        re.IGNORECASE,
    )


def supports(page: str, iso: str) -> bool:
    return date_pattern(iso).search(page) is not None


def publisher(url: str) -> str:
    """A coarse publisher key: the last two labels of the host.

    Two articles on en.wikipedia.org are two documents but one publisher. The
    design's third question is whether *independent* sources agree, so a day that
    only ever agrees with itself does not clear the bar, however many pages it
    cites. Coarse on purpose: it under-counts publishers rather than over-counts.
    """
    host = urllib.parse.urlsplit(url).hostname or url
    return ".".join(host.split(".")[-2:])


def load_allowlist(path) -> dict[str, str]:
    """Domains whose word alone carries a date, mapped to the publisher's name."""
    if not path:
        return {}
    data = yaml.safe_load(pathlib.Path(path).read_text())
    out = {}
    for entry in data.get("publishers", []):
        for domain in entry["domains"]:
            out[domain] = entry["name"]
    return out


def authority_for(url: str, allowlist: dict[str, str]):
    """The allowlisted publisher that vouches for this URL, or None."""
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    for domain, name in allowlist.items():
        if host == domain or host.endswith("." + domain):
            return name
    return None


def approval_hash(day: dict) -> str:
    """Hash the printable content: what a person is approving when they approve a day.

    The blurb, title, kind and the month-day that reaches the grid. Not the sources,
    which can change without changing what is printed, and not the status, which is
    derived.
    """
    payload = {
        "title": day["title"],
        "blurb": " ".join(day["blurb"].split()),
        "kind": day["kind"],
        "month_day": day["month_day"],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def verify_day(day: dict, timeout: int, allowlist: dict[str, str] | None = None) -> dict:
    iso = day["date"]["gregorian"]
    checked = dt.date.today().isoformat()
    allowlist = allowlist or {}
    results = []
    for src in day.get("sources", []):
        entry = {"citation": src.get("citation"), "url": src.get("url"), "type": src.get("type")}
        authority = authority_for(src["url"], allowlist)
        if authority:
            entry["authority"] = authority
        try:
            status, page = fetch(src["url"], timeout)
            entry["http"] = status
            body = visible_text(page)
            entry["bytes"] = len(page)
            entry["text"] = len(body)
            if len(body) < MIN_TEXT:
                # A challenge page is a door, not a document. Calling it read would
                # turn "we could not look" into "we looked and it is not there".
                entry["read"] = False
                entry["supports"] = None
                entry["error"] = f"blocked or empty: {len(page)} bytes, {len(body)} chars of text"
            else:
                entry["read"] = True
                # The date is looked for in the raw page, not the visible text: the
                # RSC writes "On This Day – March 6 … in 1869" inside an HTML comment,
                # which a tag strip would delete along with the evidence.
                entry["supports"] = supports(page, iso)
        except (OSError, ValueError) as exc:
            # URLError, HTTPError and TimeoutError are all OSError; a connection
            # dropped mid-read is an OSError too. Any of them means "could not read
            # this source", which is a fact about the check, not about the day.
            entry["http"] = None
            entry["read"] = False
            entry["supports"] = None
            entry["error"] = f"{type(exc).__name__}: {exc}"
        results.append(entry)

    read = [r for r in results if r["read"]]
    agreeing = [r for r in read if r["supports"]]
    n_agree, n_read = len(agreeing), len(read)
    agreeing_publishers = sorted({publisher(r["url"]) for r in agreeing})
    authorities = sorted({r["authority"] for r in agreeing if r.get("authority")})

    basis = ""
    if n_read == 0:
        status = "quarantined"
    elif n_agree >= 2 and len(agreeing_publishers) >= 2:
        status, basis = "active", "two publishers"
    elif authorities:
        # One source is enough when it is a body of record. See data/sources-allowlist.yaml.
        status, basis = "active", f"authority: {authorities[0]}"
    elif n_agree >= 2:
        status = "provisional"       # they agree, but they are the same publisher
    elif n_agree == 1:
        status = "provisional"
    else:
        status = "contested"

    return {
        "id": day["id"],
        "month_day": day["month_day"],
        "title": day["title"],
        "kind": day["kind"],
        "blurb": " ".join(day["blurb"].split()),
        "year": day["year"],
        "date": day["date"],
        "status": status,
        "basis": basis,
        # Agreeing of *all* cited sources, not of the readable ones: "1 of 1" would
        # read as agreement when the other source never loaded. How many loaded is
        # a separate number, so a page that has rotted is visible in the output.
        "agreement": f"{n_agree} of {len(results)}",
        "readable": n_read,
        "publishers": agreeing_publishers,
        "authorities": authorities,
        "checked_on": checked,
        "sources": results,
        "approved_hash": approval_hash(day),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--write", action="store_true", help="also write out/days.json")
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--out", default=None, help="directory to write into; defaults to <repo>/out")
    ap.add_argument("--allowlist", default="data/sources-allowlist.yaml",
                    help="publishers whose word alone carries a date; '' to disable")
    args = ap.parse_args()

    root = pathlib.Path(__file__).resolve().parent.parent
    data = yaml.safe_load(pathlib.Path(args.dataset).read_text())
    allowlist_path = pathlib.Path(args.allowlist) if args.allowlist else None
    if allowlist_path and not allowlist_path.exists() and not allowlist_path.is_absolute():
        allowlist_path = root / args.allowlist
    allowlist = load_allowlist(allowlist_path) if allowlist_path and allowlist_path.exists() else {}
    out_dir = pathlib.Path(args.out) if args.out else root / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    verified = [verify_day(d, args.timeout, allowlist) for d in data["days"]]
    report = {
        "topic": data["topic"],
        "generated_on": dt.date.today().isoformat(),
        "allowlist": sorted(set(allowlist.values())),
        "days": verified,
        "summary": {
            s: sum(1 for d in verified if d["status"] == s)
            for s in ("active", "provisional", "contested", "quarantined")
        },
    }
    (out_dir / "verification.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    if args.write:
        (out_dir / "days.json").write_text(
            json.dumps({k: v for k, v in report.items() if k != "summary"}, indent=2, default=str) + "\n"
        )

    for d in verified:
        mark = {"active": "OK  ", "provisional": "PROV", "contested": "CONT", "quarantined": "QUAR"}[d["status"]]
        why = f" [{d['basis']}]" if d.get("basis") else ""
        print(f"{mark} {d['id']} {d['month_day']} {d['agreement']:>7}  {d['title']}{why}")
        for s in d["sources"]:
            state = "supports" if s["supports"] else ("no match" if s["read"] else f"unread ({s.get('error','')[:60]})")
            print(f"        - {state}: {s['url']}")
    print(f"\nactive {report['summary']['active']} · provisional {report['summary']['provisional']} · "
          f"contested {report['summary']['contested']} · quarantined {report['summary']['quarantined']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
