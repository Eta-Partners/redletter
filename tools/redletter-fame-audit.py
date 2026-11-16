#!/usr/bin/env python3
"""One command: audit what the books' fame lines actually show.

  python3 fame_audit.py <git-sha|dir> [repo]

Freezes the sha into a scratch dir and measures both person books at A4 landscape
through the renderer's own path. Prints, per book: records, cells, person cells,
whether a fame line still draws its award label, and both coverage denominators.

Guards, all of which must hold or the measurement is void:
  * one cell-level truncate_blocks call per processed day, every month;
  * laureates must show 0 trailing birth clauses (the suffix drop is a no-op there);
  * chemistry's two Curie records are reported separately, because one of them
    legitimately changes under the suffix drop and one must not.

Measured quantities:
  drawn  - qualifying words of the drawn fame line that survive truncation. A token
           ending in the truncation marker counts when its stem is a whole word in
           the fame line, and is dropped when it is a fragment; see qual_drawn.
  answer - qualifying words of the *answer* that appear in the drawn text, where
           the answer is the fame line minus its award label (and minus every word
           the label prints, or "chemistry" scores every laureate cell) and minus a
           trailing birth clause (or "born" scores every chemistry cell).
"""
import calendar, pathlib, re, statistics, subprocess, sys, tarfile, tempfile
import yaml

def _git(*args, cwd):
    """Run git by argument list. No shell, so a sha from a queue message is data."""
    return subprocess.run(["git", *args], cwd=cwd, check=True,
                          capture_output=True, text=True).stdout.strip()

TARGET = sys.argv[1]
REPO_ARG = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--repo=")), None)
if REPO_ARG:
    REPO = pathlib.Path(REPO_ARG).resolve()
else:
    try:                                        # no absolute default path: discover it
        REPO = pathlib.Path(_git("rev-parse", "--show-toplevel", cwd=pathlib.Path.cwd()))
    except subprocess.CalledProcessError:
        sys.exit("fame_audit: not inside a git repository; pass --repo=<path>")

if (REPO / TARGET).exists() and (REPO / TARGET / "scripts").exists():
    root, label = REPO / TARGET, f"dir:{TARGET}"
else:
    # Resolve to a commit first, so an argument beginning with "-" cannot become a
    # git option and a branch name cannot drift under the measurement.
    try:
        SHA = _git("rev-parse", "--verify", f"{TARGET}^{{commit}}", cwd=REPO)
    except subprocess.CalledProcessError:
        sys.exit(f"fame_audit: {TARGET!r} does not resolve to a commit in {REPO}")
    root = pathlib.Path(tempfile.mkdtemp(prefix="rl-audit-"))
    tar = root / "src.tar"
    _git("archive", "--format=tar", f"--output={tar}", SHA, cwd=REPO)
    with tarfile.open(tar) as tf:               # extracted, not piped through a shell
        tf.extractall(root)
    tar.unlink()
    label = f"sha:{SHA[:12]}"

sys.path.insert(0, str(root / "scripts"))
import render_grid as R

BORN = re.compile(r",?\s*(was born|is born)(\s+in\s+[^.,]*)?\.?\s*$", re.I)
LABEL = re.compile(r"^Nobel Prize", re.I)
STOP = {"that","with","from","their","which","this","were","been","into","over",
        "after","before","than","them","they","when","where"}
toks = lambda s: re.findall(r"[A-Za-z][A-Za-z'\-…]*", s)
def qual(s):
    return [w.lower() for w in toks(s) if len(w) >= 4 and w.lower() not in STOP
            and not w.endswith("…")]
def qual_drawn(s, src):
    """`qual` on drawn text, where a marker means whatever the layout put it after.

    The blank rule "drop any token ending in …" was calibrated on the renderer that
    amputates a complete word's last letter: there `'studies o…'` still shows
    `studies`, and `'outstandin…'` is a fragment it is right to drop. A re-wrap that
    ends on a word boundary instead gives `'studies…'` — a whole word carrying the
    cut signal — and the blank rule throws that word away, scoring the better
    rendering worse. So credit a marked token whose stem is a whole word in the
    fame line, and keep dropping one whose stem is not. On the shipped renderer
    the zero column does not move at A4 landscape, the shape the audit reports
    (7 of 64); at the portrait shapes it falls by one cell each, 53 -> 52 and
    44 -> 43, both at 09-01. The laureates' median does move, 16.7% -> 18.3%, and
    >=50% goes 9 -> 10, because two lines end with a whole word followed by the
    marker ('pioneering work…', 'plant pigments…') and the blank rule was
    discounting both. It matters most when comparing two ways of rendering a cut.
    """
    out = []
    for w in toks(s):
        low = w.lower()
        if len(w) < 4 or low in STOP:
            continue
        if w.endswith("…"):
            if w[:-1].lower() in src:
                out.append(w[:-1].lower())
        else:
            out.append(low)
    return out

def source_words(f):
    return {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'\-]*", f)}

def drawn_words(f):
    return qual(f)
def answer_words(f):
    head, sep, tail = f.partition(": ")
    body = BORN.sub("", tail if sep else f)
    if not sep:
        return qual(body)
    lab = {w.lower() for w in toks(head)}
    return [w for w in qual(body) if w not in lab]

def marks_of(path, year):
    d = yaml.safe_load(path.read_text()); m = {}
    for r in d["days"]:
        if r.get("status", "active") != "active":
            continue
        mo, dy = (int(x) for x in r["month_day"].split("-"))
        if mo == 2 and dy == 29 and not calendar.isleap(year):
            continue
        m.setdefault(mo, {}).setdefault(dy, []).append(
            (r["year"], r["title"], r.get("blurb") or ""))
    return d["topic"], m

def audit(name, path):
    topic, marks = marks_of(root / path, 2027)
    size = R.page_size_pt("a4", "landscape")
    orig, outer, bad = R.truncate_blocks, [], 0
    def spy(blocks, h, _o=orig):
        kept = _o(blocks, h)
        if not blocks or any(b[2] == R.INK for b in blocks):
            outer.append(kept)
        return kept
    R.truncate_blocks = spy
    drawn, ans, persons, cells, labelled = [], [], 0, 0, 0
    curie = []
    try:
        for mo in range(1, 13):
            outer.clear()
            R.build_month_page(topic, marks, 2027, mo, size)
            days = [d for w in R.month_days(2027, mo) for d in w if d]
            if len(days) != len(outer):
                bad += 1; continue
            for dy, kept in zip(days, outer):
                ev = marks.get(mo, {}).get(dy, [])
                if not ev:
                    continue
                cells += 1
                fames = [f for f in (R.fame_line(t, b) for (y, t, b) in ev) if f]
                if not fames:
                    continue
                persons += 1
                f = fames[0]
                if LABEL.match(f):
                    labelled += 1
                got = qual_drawn(" ".join(x[0] for x in kept if x[2] == R.GRAY),
                                 source_words(f))
                dw, aw = drawn_words(f), answer_words(f)
                drawn.append(sum(w in got for w in dw) / len(dw) if dw else 1.0)
                ans.append(sum(w in got for w in aw) / len(aw) if aw else 1.0)
                if "Curie" in f or any("Curie" in e[1] for e in ev):
                    curie.append((" ".join(x[0] for x in kept if x[2] == R.GRAY),
                                  BORN.sub("", f.partition(": ")[2] or f)))
    finally:
        R.truncate_blocks = orig
    recs = sum(len(e) for mo in marks.values() for e in mo.values())
    return dict(name=name, recs=recs, cells=cells, persons=persons, bad=bad,
                labelled=labelled, drawn=drawn, ans=ans, curie=curie)

def row(a, which):
    c = a[which]
    print(f"  {a['name']:<10} {which:<6} median {statistics.median(c):>4.0%}  "
          f"whole {sum(x == 1 for x in c):>2}  >=50% {sum(x >= .5 for x in c):>2}  "
          f"any {sum(x > 0 for x in c):>2}  zero {sum(x == 0 for x in c):>2}")

print(f"fame audit — {label} — A4 landscape, 2027\n")
for name, p in (("laureates", "data/chemistry-laureates.yaml"),
                ("chemistry", "data/chemistry.yaml")):
    try:
        a = audit(name, p)
    except Exception as e:
        print(f"  {name}: FAILED — {e}")
        continue
    pairing = "OK" if a["bad"] == 0 else f'BROKEN in {a["bad"]} months'
    print(f"{a['name']}: {a['recs']} records, {a['cells']} cells, "
          f"{a['persons']} person cells, {a['labelled']} fame lines still draw an "
          f"award label; pairing {pairing}")
    row(a, "drawn"); row(a, "ans")
    for g, want in a["curie"]:
        print(f"    curie: drawn={g[:70]!r}")
        print(f"           answer={want[:70]!r}")
    print()
