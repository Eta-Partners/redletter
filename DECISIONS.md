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

## 2026-11-15 · No status or verification fields in the dataset

`data/*.yaml` holds what a person wrote: the day, the words, the sources. Status,
agreement and the checked-on date are written by the verifier into `out/`. Two
places to write the same fact is one place too many, and the hand-written copy is
the one that goes stale.
