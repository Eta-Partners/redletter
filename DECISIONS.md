# Decisions

One entry per choice that a reader could reasonably have made differently. The
date is when the choice was made; the source says who made it or what forced it.

## 2026-11-16 · The book form: cover, twelve months, the detail inside the cell

**Change.** `render_grid.py` gains a third emitter. `--pdf` lays the same drawing
out in PostScript points and writes thirteen pages — a cover, then one page per
month with each day's year and title inside its date cell — through the same
`draw()` the PNG uses, at 300 dpi. The wall sheet is unchanged and is still what
`--year` and `--month` produce.

**The two provisional defaults, decided.**
- *A4 landscape.* A week is wider than it is tall, and landscape is where the
  shipped datasets were measured. `--paper letter` and `--orientation portrait`
  reach the other three combinations; portrait is legible (the July page was read
  at 120 dpi) but its cells are narrow, and that is where the wrap guard earns
  its keep.
- *The blurb is preferred only while it costs less than 1.5 pt of type.* Kept, and
  made strict: the code tested `blurb_size >= title_size - 1.5`, which accepts a
  cost of exactly 1.5 pt, and the rule as decided says *less than*. Type steps by
  0.5 pt, so the boundary is reachable, not theoretical, and it was reached: the
  ten-day spaceflight dataset at Letter portrait has January and July at a blurb
  of 8 pt against a title of 9.5, and those two pages now keep the larger title.
  Built all three datasets at all four paper shapes: 156 pages, and those two are
  the only ones that differ by raster comparison. Measured on the active days in
  each dataset's `out*/days.json` at A4 landscape, the blurb is never chosen: 115
  chemistry days, 72 laureate days and 10 spaceflight days all choose
  year-and-title, because a 130-character blurb in a 20-character cell needs the
  type two or more points smaller. It fires only where a page is sparse enough to
  afford it (in A4 portrait, two months, January and July, of the ten-day dataset).
  That is the rule working as written, not a bug.

**A word wider than the cell.** `wrap_to` leaves a word longer than its line whole,
because a hyphen it inserted would be a word it invented. That is a rule about a
line, and it said nothing about the *cell*: an unbroken word ran into the next
column, which silently gives a day's detail to another day. Found at `337331b`
while checking the blurb boundary, as 104 lines over the twelve books — 101 of
them printed, the other three dropped by truncation — in 69 cells, six of them
across the three default A4 landscape books, the worst 12.6 pt past. The fix is
in `fit_to_width`, applied in `cell_blocks`: a line that fits the cell's full
width moves to indent 0, and a word wider than the whole cell is broken at the
character boundary that fits with no hyphen inserted. Flushing first recovers
almost all of it without inventing anything; the break is the last resort, and a
visibly broken word is the better error, since a word in the cell beside it
attributes a day to the wrong day. Flush is per line, so a page that already fit
keeps its layout. The second-order cost is real and measured: a break adds a line,
so a page's chosen type can step down — chemistry at A4 portrait, March, goes 9.5
to 9 pt, and at Letter portrait January and March go 8 to 7 pt, where January then
stops truncating. Rendered on all three datasets at all four paper shapes, 37 of
156 pages change and 119 are pixel-identical; the default A4 landscape books change
only on the pages that had the defect, and no default page's type size or
truncation moves.

**Why a page sizes on nine cells in ten.** Sizing on the worst cell lets one
132-character Nobel citation set a whole month to 5 pt. So a page is accepted when
at most one cell in ten may truncate. The allowance is rounded *up* to whole
cells: nine in ten rounded down would leave a page of nine cells with no allowance
at all, and the page would shrink to fit the one rare entry the rule exists to
forgive (July would go from 7 pt to 5 pt for a single long line). Truncation
drops the lines past the cell's budget and ends the last kept line with an
ellipsis; it is deterministic, and the test builds the same cell twice.

**The wrap edge, and the shared hang.** `wrap_to` clamps inside to
`max(4, int(chars))`, so a cell too narrow for the continuation hang did not
raise — it wrapped at four characters and the indent pushed the line past the cell
edge. At the size each page actually chooses, chemistry's tightest `chars - hang`
is 14 at A4 landscape, 17 at Letter landscape, 8 at Letter portrait and 5 at A4
portrait, so the default was never broken and portrait is where it would have
been. (The operator measured 12 at Letter landscape; I did not reproduce their
basis, and either reading leaves the default safe.) The hang is now dropped when
it would leave fewer than `MIN_HANG_CHARS` (8) for the continuation; the text
keeps the width instead of the alignment.

Title continuation still hangs under its title. The blurb no longer does: it
prints at the cell's left edge, already distinguished by grey and 0.86x type. The
hang costs a step of type on the path that decides whether a blurb appears at
all — measured on a 70 by 45 pt cell holding one event and a 22-character blurb,
the hung page keeps 9.5 pt and drops the blurb, while the blurb at the cell's
edge is chosen at 9 pt. It was suppressing the detail it was meant to organise.
The probe is not a page: the shipped blurbs run 34 to 150 characters (chemistry
34 to 133, laureates 73 to 150, spaceflight 92 to 143), so no shipped blurb is
short enough for that trade. Its inputs are pinned in `tests/test_render_grid.py`,
so the justification is a test that fails if the numbers stop holding. Checked page by page over all three datasets at all
four paper shapes, the split changes no month page's choice: the same type size
and the same blurb-or-not on every one of the 144 month pages. The blurb is drawn
only at A4 portrait, spaceflight January and July, and on those two the change is
the blurb's placement, not the type; at A4 landscape no blurb is drawn, so nothing
there moves.

**Cost.** The book is raster at 300 dpi, not vector: a chemistry book is about
5.5 MB and scales without banding only up to its raster resolution. Pillow also
stamps `CreationDate` into the PDF, so the file digest changes every run — the
pages, not the bytes, are what a change is verified against.

## 2026-11-15 · The four answers from the owner

Recorded from the answered decision row `qitem-20261116011417-70116e8fb82bff4b`:
`{"old_style":"gregorian","contested":"off","scope":"real_only","start":"slice"}`.

| Question | Answer | What it means here |
| --- | --- | --- |
| Which style for the printed dates? | Gregorian | The sheet is a Gregorian year. A day kept in another calendar on the day carries the calendar it was kept in in `date.calendar` and its Gregorian equivalent in `date.gregorian`; the grid uses the latter. |
| What happens to a contested day? | Off | Not drawn, not marked, not footnoted. The status is still computed and stored, so a future renderer can decide otherwise; nothing renders it today. |
| Real days only, or legendary and fictional too? | Real only | Every day must be a dated event with sources. No saints invented by hagiography, no fictional anniversaries. It is also why this repository names no fandom in its own identity. |
| Where to start? | The slice | One topic, carried end to end, before the research skills that would fill it. |

## 2026-11-15 · Independence means publishers, not pages

**Choice.** A day reaches `active` only when the agreeing sources come from at
least two different publishers. `scripts/verify_days.py` reduces each URL to the
last two labels of its host and requires two distinct values.

**Why.** The first run of the verifier passed four days on two Wikipedia articles
each. Those are two documents, but they are one publisher, and on a well-watched
article they are frequently the same editors. The design's third question is
whether *independent* sources agree; counting pages let the dataset agree with
itself and call it corroboration.

**Cost.** It is coarse: two different NASA pages are also one publisher. That is
the correct direction to be wrong in — it under-counts independence rather than
inventing it.

**Evidence.** With the rule, those four days fell to `provisional` and were given
real second publishers (NASA, the National Women's History Museum, the China
Manned Space Agency) before they printed.

## 2026-11-15 · "Mono" keeps the red

The sheet is monochrome in everything except the mark. The rubric red is the
information, not decoration, so a mono sheet that also greys the red would be a
blank calendar. A genuinely two-ink-free variant is a `--rubric` flag away.

## 2026-11-15 · Weeks start on Monday

Monday-first, which is what `calendar.Calendar(firstweekday=0)` gives and what most
of the world prints. Nothing in the data depends on it; a Sunday-first sheet is a
layout argument, not a data one.

## 2026-11-15 · The feed starts at the print year

Each event's `DTSTART` is the print year (2027) with `RRULE:FREQ=YEARLY`, and the
year the thing happened goes in the description. The alternative — starting the
series in 1961 — would fill a subscriber's calendar with decades of past events
the first time they imported it, which is not what a wall calendar is for.

## 2026-11-15 · 29 February

A day recorded on 29 February prints only in a leap year; the renderer and the
feed writer both skip it with a printed reason in a non-leap year rather than
silently moving it to 28 February or 1 March. No day in the seed dataset is on 29
February, so this rule is written and untested against real data.

## 2026-11-16 · A body of record is enough on its own

**Choice.** One agreeing source from a publisher on `data/sources-allowlist.yaml` is
enough for `active`. Everything else still needs two publishers.

**Why.** The owner asked for it, for chemistry: "if the source is from a reputable
source like ACS, Royal Society of Chemistry, Angewandte… you don't need a second."
He is right that a second website repeating the ACS adds nothing. The two-publisher
rule exists to stop a claim being copied; it is the wrong cost where the claim comes
from the body that keeps the record.

**Cost, stated.** The list is an editorial judgement and it can be wrong: a body of
record can still misprint a date, and the allowlist cannot tell. It is a short
visible file rather than a flag scattered through records, and every day it vouches
for carries `basis: authority: <name>`, so a reader can see which days never had a
second opinion.

## 2026-11-16 · The key is measured, not assumed

**Change.** The sheet's list of days now measures its own text and picks a column
count, type size and line height that fit the band it has. Before this it assumed
about ten entries; at seventy-two the list ran off the page and printed over itself
and over the footer.

**Why.** The defect only appears at density, which is exactly the state the product
is aiming for, so it would have arrived with the first real calendar.

## 2026-11-16 · The date matcher reads shapes, not strings

**Change.** `supports()` now builds a pattern from the record's date instead of
looking for one of seven pre-written phrases. It covers a full or three-letter
month name, a plain or zero-padded day, either order, and the ISO form.

**Why.** A research file arrived citing 96 Royal Society of Chemistry pages. Thirty
of them came back `contested`: the gate had fetched the page, the page stated the
date, and the gate could not see it, because the RSC titles its pages
`On This Day – Mar 06` — abbreviated month, zero-padded day — and none of the
seven phrases (`March 6, 1869`, `6 March 1869`, `Mar 6, 1869`, …) matched `Mar 06`.

**What that cost.** A third of a researched calendar was reported as sources
disagreeing about a date when the sources agreed and the reader was blind. It is
the failure mode the status ladder is supposed to prevent, arriving through the
instrument rather than the material. `contested` is a claim about the sources; it
is not a safe default for "my pattern did not match".

**Evidence.** After the fix, the same 96 pages, unchanged, on the same day. Tests
now pin both directions: `Mar 06` and `March 06` match 6 March; `March 2026`,
`March 60`, `Mar 16` and `March 1869` do not.

## 2026-11-16 · A bot wall is unread, not disagreement

**Change.** A page with fewer than 400 characters of visible text is treated as
unreadable, with the byte and character counts in its `error`, instead of being
read and found not to match.

**Why.** acs.org answers a non-browser client with HTTP 200 and 212 bytes of
Incapsula challenge script. The gate marked that source read and unsupporting,
which turns "we could not open the door" into "we looked and the date is not
there". For an allowlisted publisher that difference decides whether a day is
`contested` or `quarantined`, and it is the difference between a report a person
can act on and one that sends them to check a date that is fine.

**Cost.** A genuinely tiny page is unread too. That is the safe direction: it
under-claims, and no real article is under a paragraph.

## 2026-11-16 · Research arrives as lines and is judged, not trusted

**Format.** `MM-DD | YYYY | one sentence | source URL | publisher`, one per line.
`scripts/from_lines.py` parses it, refuses malformed lines, and cross-checks the
date against the source's own URL where the URL carries one — the RSC pages do
(`on-this-day-feb-22--…`), so a line whose date and link disagree is caught before
any request is made.

**Why this shape.** The owner offered research from other assistants. Their output
is *candidates*: the same gate judges it, unchanged, and nothing they produce can
reach a sheet without passing the same test as a hand-curated day. Two assistants
agreeing is not two publishers; the allowlist decides, not consensus.

**What it changed.** `data/chemistry.yaml` is now built from such a file rather
than from one API. The 72 laureate births it used to hold moved to
`data/chemistry-laureates.yaml` unchanged: they are the people calendar, still
true, still verified, just not the same calendar as the field's days.

## 2026-11-16 · Two research files, two id spaces

**Change.** `from_lines.py` numbers its records `D-CHE-<prefix><nnn>`, and the
prefix is an argument (`C` for one researcher's file, `G` for another's).

**Why.** The first fold gave both files `E001…`, so the ids collided. The id is the
join key between a verification result and the words printed beside it, and the
join silently matched one researcher's `E001` to the other's: a record ended up
dated 10 January and titled "Harold Clayton Urey dies". The dates and the sentences
had come out of different files.

**How it was caught.** Not by the gate — the gate judges a URL against a date and
never reads the id. It was caught by printing the folded file's first five lines
and looking at them. The fold now asserts its ids are unique before it writes.

**Lesson.** A join on a generated key is only safe if the key is unique across the
things being joined, and the gate cannot see this class of error at all.

## 2026-11-16 · Which researched days were left out, and why

Two assistants returned 137 candidate lines. The gate passed 131 of them — the
other six were ACS pages it could not open — and 115 are on the chemistry
calendar. The difference is editorial, and it is recorded here because nothing in
the output shows what is missing:

| Left out | Why |
| --- | --- |
| 8 NIST institutional anniversaries — a Boulder campus, a proving ring, two buildings burned in a fire test | Anniversaries of an agency, not days chemistry marks as a field. All eight also rested on one index page rather than a page about the event. |
| 6 ACS pages — the society's founding (proposed twice, by both researchers), its first president, its first paper, helium in natural gas | `acs.org` answers a non-browser client with a bot wall, so the gate could not read them. Excluded by fact, not judgement: no source, no mark. |
| 3 Nobel announcements and 3 IUPAC notices naming elements 113–118 | The same recurring event told on several dates. One entry per event: 7 October for the chemistry prize, 30 November for the names. |
| 1 Edison electric-lamp patent | Not chemistry, and the page the line cited does not state the date. |

The 17 laureate death dates were kept: a field's days include the days its people
die. `data/chemistry-laureates.yaml` keeps the birth calendar unchanged.

## 2026-11-16 · At density the key's column count is the lever

**Change.** When the key cannot fit every line on one row, it no longer defaults
to four columns. It keeps the largest type that fits the band at all and, at that
size, takes the column count that shows the most characters of each line.

**Why.** At 115 days and four columns, each line had about 33 characters: enough
for "The first commercial atomic clock…" and nothing else. Three columns at 12 px
give about 50, because a third of the width had been sitting unused either side of
the text. The lines are still trimmed where they land, but the trim now falls past
the point where a reader knows what the day is.

**Cost.** A three-column key reads down and then across, so the columns no longer
line up with the month blocks above them. It is a denser page; a two-sheet year is
the honest answer if the calendar grows much past this.

## 2026-11-15 · The icon is cut on the paper, not on the white

**Choice.** `tools/icon.py` finds the sheet by flooding its own cream colour from
the middle, fills the holes the printed grid leaves, and uses that silhouette as
the alpha channel. It does not key "near white" out.

**Why.** A white key leaves the thin shadow the artwork draws along the sheet's
edge. At 1024 px that reads as a soft edge; at 128 px it reads as dirt, and the
smallest size is the one that ships in a tab. Cutting on the paper removes the
shadow with the field, and a 0.8 px blur on the mask keeps the cut from aliasing.

**Cost.** It assumes the artwork's sheet is a solid colour on a plain field, which
is what was asked for. A textured or multi-colour sheet would need a different cut.

## 2026-11-15 · "2 of 2" counts cited sources, not readable ones

**Change.** `agreement` now reads `agreeing of cited`. A separate `readable` field
carries how many actually loaded.

**Why.** The old string counted readable sources, so a day with one working source
and one dead link printed `1 of 1` — which reads as "everything agrees" when in
fact half the evidence never arrived. A test caught it. The status was always right;
the number was flattering.

## 2026-11-15 · Tests: the network is faked, not avoided

**Choice.** The unit tests replace `fetch` with a mapping from URL to page, so every
branch of the status ladder is exercised exactly. The integration tests run the
real scripts against a real HTTP server this repository starts on localhost, and
only one test — the one that reads the shipped dataset from the live web — is
opt-in behind `--run-network`.

**Why.** The rules most likely to break are in the status ladder and the date
matcher, and those can be pinned in milliseconds with no network. The pipeline can
be proven end to end without the internet by serving it pages. Only the claim "the
sources still say this" depends on the web, and that claim belongs to the web.

## 2026-11-15 · No status or verification fields in the dataset

`data/*.yaml` holds what a person wrote: the day, the words, the sources. Status,
agreement and the checked-on date are written by the verifier into `out/`. Two
places to write the same fact is one place too many, and the hand-written copy is
the one that goes stale.
