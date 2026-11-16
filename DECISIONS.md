# Decisions

One entry per choice that a reader could reasonably have made differently. The
date is when the choice was made; the source says who made it or what forced it.

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
