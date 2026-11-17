# Redletter — specification

## Intent

A Redletter is a calendar of the days a field marks in red. You name a topic; the
days are researched, each one sourced and checked; you get a printed year where
those days are the only things in colour, and a calendar feed that repeats them
every year.

The point is not the list. A list of interesting dates is cheap and worthless. The
point is that **every red mark earned its place**: its sources were read, they
agreed on the day, and they were not the same source twice. A day that cannot
prove itself stays out of the picture instead of appearing with an asterisk.

## Mini-requirements

The vertical slice proves these, on three calendars:

1. **A record schema for a day.** Month-day, the year it happened, a title, a
   short blurb, the date as recorded and in Gregorian, precision, sources, and a
   derived status. A person's death carries one field more, `work_caused`, with
   the causal sentence, its evidence phrase and the page that states it (item 4c).
   A day is a record, not a sentence.
2. **Three verification questions** asked of every record by script:
   - does each source exist and say what the record claims about it;
   - does each source support the date;
   - do *independent* sources agree — where independent means more than one
     publisher, not more than one page.
3. **Derived status, never hand-written.** `active` (two publishers agree on the
   day), `provisional` (one publisher, or one agreeing page), `contested` (sources
   read and disagreed), `quarantined` (nothing could be read), `refused` (the date
   stands but the claim is not allowed — item 4c). A page that returns a bot wall
   is `quarantined`, not `contested`: unread is not disagreement.
4. **A print sheet**: a dated year, mono except for a single rubric red, twelve
   month grids, and a key at the foot naming every marked day with the year it
   happened. Only `active` days are drawn.
4b. **A book form** beside the sheet, not instead of it: thirteen pages — a cover
   carrying the topic, the year and the count, then one page per month with each
   day's year and title printed inside its date cell. A person's cell also says
   what they are known for: the record's own blurb with the name the title has
   already printed taken off the front, capped at two lines. A4 landscape by
   default; `--paper` and `--orientation` reach the other three combinations. A
   page too small for all its text truncates the rare cell that does not fit,
   marked with an ellipsis, rather than shrinking the whole page; the room a cell
   has is measured in height, because its lines are not all one size.
4c. **A death prints only when the work is its stated cause.** A person's death —
   a `kind: loss` whose title is `"<subject> dies"` — is `refused` unless its
   record carries a `work_caused` block whose evidence phrase sits inside its
   statement, whose statement sits inside the blurb, whose `source_url` is on the
   source allowlist, and whose evidence phrase is in the visible text of that page
   once fetched. The check is a pure function over the record, the allowlist and
   the page text; the page only has to carry the cause, not the date. What it
   proves is that the phrase is on the cited page — not that the phrase is the
   right fact about the death, which is an editorial judgement recorded once, in
   the record. `kind: loss` on a mission ("Challenger is lost") is not a person's
   death and the rule does not touch it.
5. **A feed**: one all-day event per active day, repeating yearly, carrying the
   original date and the sources in the event body.
6. **A print/feed split that is honoured.** The printed sheet is a *dated* year —
   the mark falls on a real 2027 date. The feed is a *recurrence* — the mark falls
   on month-day every year, and the year it happened lives in the description.

## Proof contract

What counts as done, and how each is checked by effect rather than by assertion:

| Claim | How it is checked |
| --- | --- |
| The sources support the day | `verify_days.py` fetches each URL and looks for the date in the page text; the status follows from what came back |
| Agreement is real | the agreeing sources are grouped by publisher; one publisher cannot agree with itself |
| The fame line is the record's own words | a test over every person record in all three datasets asserts the printed fame line is a substring of that record's approved blurb — nothing is added, nothing is trimmed at a guess |
| A death without a stated cause is refused | `verify_days.py` refuses any record whose title ends ` dies` without a `work_caused` block that nests and cites an allowlisted page carrying the evidence phrase; an offline test runs the same rule over the shipped `chemistry.yaml` |
| The sheet shows only verified days | the renderer reads `out/days.json` and skips anything not `active`, printing what it skipped and why |
| The book is thirteen pages | `build_book` returns a cover plus twelve month pages, and the page size in points is checked against the paper's own dimensions |
| Text stays in its cell | every drawn line's rendered width is measured against its cell's inner width at every paper shape, one-word lines included; the room a cell keeps is a measured height, so it is truncated only when its text truly does not fit; a page is accepted when one cell in ten, rounded up, may truncate (the arithmetic is in `DECISIONS.md`). Width is metered in one rounded advance per character, measured and drawn from the same number, so the same page is laid out on the macOS and manylinux Pillow wheels; that is exact for the 0.600-0.602 em monospace class at the sizes the layout meters, not for every monospace at any size (the 74 pt cover year is the one size the deck sets where the class splits; see `DECISIONS.md`, 2026-11-17) |
| The feed imports | the `.ics` is parsed back with `icalendar` before it is written: dates are DATE values, every event carries a YEARLY rule and a UID, and the month-day matches the record |
| The feed is portable | CRLF line endings, no line over 75 octets, UTF-8 |

## Out of scope for the slice

- **Finding the days.** The slice curates by hand, or takes a researcher's file and
  judges it. The skills that *discover* days for a named topic unaided are still
  the next slice, and they are the hard one. What exists is the intake: a line
  format, a parser that refuses malformed lines and catches a date contradicting
  its own URL, and the unchanged gate behind it (see `DECISIONS.md`).
- **Contested days.** The owner chose to leave them out entirely rather than draw
  them differently. The status still exists; nothing renders it yet.
- **Colour paths, and paper sizes other than A4 and Letter.** The book reaches
  either paper in either orientation; nothing else is drawn.
- **A real client import.** The feed parses cleanly; nobody has yet subscribed to
  it from Apple Calendar or Google Calendar and looked at the result.
