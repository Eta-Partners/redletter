# Decisions

One entry per choice that a reader could reasonably have made differently. The
date is when the choice was made; the source says who made it or what forced it.

## 2026-11-16 · The fame line, births only, and the death that has a cause

TJ, on Slack at 17:10Z: *"Can we include why people are famous? What they are
famous (known) for? And is it possible to only have the births and not the
deaths. (Unless it is significant 'They died due to their experiments/work
on…')"*. Three decisions, and the ruling on each is the operator's, relayed by
`orch-lead` on `qitem-20261116171455-bc2ff06b`.

**The fame line is the record's own blurb minus the name the title prints.** A
person's cell printed `Marie Curie is born` and then a blurb opening `Marie
Curie, …`: the name twice, and never the reason. `fame_line(title, blurb)` strips
a leading `<title subject>, ` — the subject is the title without its ` is born` /
` dies` — and the cell prints the rest, capped at two lines. Every character it
draws is a substring of the approved sentence, which is the property the tests
assert over every person record in all three datasets: `fame in blurb`. A title
that is not a person's day gets None, so `first`, `discovery`, `milestone` and
`launch` cells are unchanged.

*Which records take each path, parsed rather than assumed.* Chemistry: 43 of 43
person records open with their subject and take the strip (42 births and Curie's
death). Laureates: 0 of 72 take it — every laureate blurb opens `Nobel Prize in
Chemistry <year> in <country>: …`, not with the name — so all 72 print unchanged,
which is the rule for a blurb that does not open with its subject. The
expectation was 42 of 42 and 72 of 72 stripped; the laureate figure is the one
that was wrong. Spaceflight has no person records. The unstripped path is not a
fallback that happened to fire: it is the whole laureate calendar, and a name
this code trimmed at a guess would be a word it invented.

**The cap is two lines, and the table says what it costs.** The cell draws the
fame line in the blurb's grey at 0.86x the title's size, always — the 1.5 pt rule
below decides whether a *blurb* is worth its cost and does not decide this, which
is the operator's ruling: TJ asked for the detail. `blurb_is_worth_it` still has a
caller (non-person cells) and still fires: spaceflight at A4 portrait, January and
July, is chosen at 9 pt with the blurb. Measured across all twelve books, A4
landscape (the default book shape, 13 pages, 12 month pages):

| Book | cap | person cells | fame drawn | fame ending in … | pages whose size changed | pages down >1 step |
| --- | --- | --- | --- | --- | --- | --- |
| chemistry, 92 records | 2 lines | 43 | 43 | 41 | 0 | 0 |
| chemistry, 92 records | 1 line | 43 | 43 | 43 | 0 | 0 |
| laureates, 72 records | 2 lines | 64 | 61 | 61 | 9 | 3 (Jan 9→6.5, May 9.5→8, Aug 9.5→8) |
| laureates, 72 records | 1 line | 64 | 60 | 60 | 3 (Jan 9→7, May/Aug 9.5→9) | 1 (Jan) |
| spaceflight, 10 records | either | 0 | 0 | 0 | 0 | 0 |

The other shapes: at A4 portrait the laureate book moves only its January page,
9.5 to 9 pt at either cap; at Letter portrait January goes 9.5 to 7.5 with two
lines and 9.5 to 9 with one; at Letter landscape the laureate book loses more
(two lines: March 8.5→7, May and August 9.5→7; one line: March 8.5→7.5, May and
August 9.5→8.5, November 9.5→9). Spaceflight is identical at every shape and cap,
having no person cells. So two lines cost more than a step of type on three of
twelve pages at the default shape, not on most pages, and the ruling's two lines
stand.
What the numbers also say, plainly: on the default chemistry book 41 of 43 fame
lines end in an ellipsis, because a 48–119 character sentence in a ~20-character
cell is cut at two lines. The one-line cap cuts all 43. Two lines therefore buys
roughly twice the sentence for type the chemistry book does not pay at all, and
the laureate book pays in January, May and August.

**The cell's truncation budget is a height, not a line count.** `truncate_blocks`
took a count of lines computed at the title's size, so a cell whose fame lines are
set smaller lost lines it had room for: 7 cells on the laureate book at A4
landscape and 2 on the spaceflight book at A4 portrait were cut by a budget that
said they did not fit while the chooser had just found that they did. It now takes
the cell's room in points and keeps the blocks whose height fits. One mechanism,
and the fame line is what made the mismatch visible on every person cell.

**Births only, with one exception, and the exception is a criterion the gate
applies.** The 24 `kind: loss` records in `chemistry.yaml` were 24 deaths with a
date and no reason; the book keeps a death only when a source states the death was
caused by the person's work. Such a record carries:

```yaml
work_caused:
  statement: "<the causal sentence, which must also appear in the blurb>"
  evidence: "<a short phrase that must appear in the cited page>"
  source_url: "<a URL whose host is on data/sources-allowlist.yaml>"
```

`verify_days.py` refuses every other death: `is_person_death` (a `kind: loss`
whose title ends ` dies`), `work_caused_gap` (the block is present, `evidence` is
inside `statement`, `statement` is inside the blurb, the host is allowlisted), and
`cause_stated` (the evidence phrase is in the visible text of the page when it is
read). The last two are pure functions over the record, the allowlist and the
page text, so the offline suite feeds a page that states the cause and one that
does not. A refused record gets the status `refused`, a fifth rung beside
`active`/`provisional`/`contested`/`quarantined`: the date may be perfect and the
claim still not allowed, and a record that vanished from the ladder would be a
silent deletion. Nothing renders `refused`; the renderer already draws only
`active` and names what it skips.

The scope is a person's death and not the word `loss`, because crewed spaceflight
uses `kind: loss` for a mission whose crew were killed (`Challenger is lost`) and
that calendar is not a people calendar; the rule must not delete its days. The
gate and the renderer read the same title form, and a test over all three
datasets asserts they agree on which records are people.

*The one record that passes, and what it costs to be honest about it.* Marie
Curie survives. Her cited page is
`periodic-table.rsc.org/element/88/radium` — `rsc.org` on the allowlist, HTTP 200,
23,966 visible characters — and it says: *"Although Marie Curie lived until 1934,
her death from aplastic anaemia is almost certainly due to her exposure to
radioactive materials, particularly radium."* Her blurb now reads *"Marie Curie,
discoverer of polonium and radium and twice a Nobel laureate, died of aplastic
anaemia almost certainly due to her exposure to radioactive materials."* Three
things are deliberate. **The hedge prints**: the page says *almost certainly*, so
the blurb says it too, rather than flatly stating a cause the source hedges.
**"died in Savoy, France" leaves the blurb**, and it was sourced — the Nobel
biography that carries the 4 July 1934 date still states it and is still in
`sources:`; the place was dropped to print the cause, not because it was
unsupported. **The block's `source_url` need not state the date**: the date is the
`sources:` ladder's job, and the operator ruled that the cause page answers only
for the cause. The 23 other deaths had no such source and are not in the file;
`chemistry.yaml` goes from 115 records to 92 — 42 birth, 1 loss, 9 first, 20
discovery, 20 milestone — and six to ten days in every month. `topic.kinds` keeps
`loss`, because one survives.

**What the criterion proves, and what it does not.** It proves the evidence phrase
is on the page that was cited, in the words a reader sees. It does not prove the
phrase is the right fact about that death: choosing the phrase, and judging it the
cause, is an editorial act made once in one record, the same kind of judgement
`data/sources-allowlist.yaml` already records. It also extends what that file
means. It was written to vouch for a *date*; the death rule uses it to vouch for a
*causal statement about a death*, which is a wider claim than a body of record
makes when it prints a day. That extension is visible here beside the rule and in
the one record it reaches.

## 2026-11-16 · The fame line drops its citation label and prints at the cell's size

The entry above set the fame line in the blurb's grey at 0.86x the title and let it
carry whatever the record's own sentence opened with. Reviewing the render,
`orch-lead` amended `qitem-20261116173409-5fc50da5dcfd761e` on three measured
points, and the measurements below are mine; where they differ from the row's or
from `dev-qa`'s, this says so and uses mine.

**The label goes.** A laureate blurb opens `Nobel Prize in Chemistry 1945 in Russian
Empire: for his research and inventions in agricultural and nutrition chemistry,
…`. The label alone is 45–60 characters in a ~20-character line, so the cell spent
its two lines naming a prize, a year and a country and never reached the reason.
`after_label(text)` drops the text from the start up to and including the first
`": "` when that text contains no sentence-ending punctuation and something
non-empty follows. It is not keyed on the word `for`: of the 72 laureate records, 57
open `for …` and 15 open `in recognition of …`, and a rule keyed on `for` would
leave the 15 untouched. It is not a cap change: a third line buys one more word of
the same label, at a type cost on every dense laureate page, which the review
measured as worse than the strip on both counts. A colon that arrives after a full
stop is inside a sentence and is not a label; a colon with nothing after it is
punctuation, not a citation. The rule only chooses where the substring starts, so
the property asserted over every person record in all three datasets — every drawn
line is a substring of the approved blurb, `fame in blurb` — is still true and its
test unchanged.

*The token trap.* "Nobel Prize in Chemistry" contains `chemistry`, and most
laureate reasons contain it too, so a matcher that credits a cell for any drawn
word in common with the reason scores cells that never reached it; the operator's
first matcher did exactly that, 11 cells on the label's own word. The 57/15 split
is the answer as a test: the two counts sum to all 72, and no fame line contains
`Nobel Prize`, so after the strip there is no label drawn and a matcher has
nothing to subtract. If a matcher ever has to subtract label words again, the
strip has failed.

**The fame line prints at the cell's own size, not at 0.86x it.** The entry above
applied `BLURB_SCALE` to the detail the person cell exists to show: 5.59 pt on the
laureate book under a 6.5 pt title, 5.16–6.88 pt across chemistry. A footnote to a
thing is not the thing. The fame line now uses the page's cell size, and
`BLURB_SCALE` stays where it was written, on `with_blurb` cells, where a blurb is
optional detail beside a title and is still worth less type than the title. There
is no floor constant either: the rule is "drawn at the size the cell was chosen
at", written as one assignment, because a `max(0.86x, something)` needs the
something named and 0.86 of the smallest cell is worse than the size it started
from. Measured minimum chosen cell size after the change, over the three shipped
books and the four shapes: A4 landscape 6.0 chemistry, 6.0 laureates, 9.0
spaceflight; A4 portrait 6.5 / 8.5 / 9.0; Letter landscape 5.5 / 6.5 / 8.0;
Letter portrait 6.0 / 7.0 / 9.5. The laureate figures are one step below the
pre-change book's on each shape (6.5 / 9.0 / 7.0 / 7.5), which is where the label
strip and the cell size are paid for; chemistry and spaceflight minima do not move.

**`BLURB_MIN_PT` (7.5) is not applied to the fame line.** The floor exists so an
optional blurb cannot push a title below readable; a fame line is not optional, it
is what the cell is for. Measured: all twelve chemistry pages sit below 7.5 pt
(sizes 6 to 8), so the floor would delete the fame line from the one book that ships
by default. That is not a trade the floor was written to make. The 1.5 pt rule still
decides whether a *blurb* is chosen, as it always did.

**The table, with the population named in every column.** Two right numbers about
different things read as a disagreement in review, so: *person records* is records
whose title is a person-day form; *person cells* is cells holding at least one of
them (the laureate book packs 72 records into 64 cells); *cells drawing a fame line*
is cells whose drawn page still shows a grey line after the page's own height
budget; *positional reach* is records, counted positionally (below), each rendered
alone in a cell of the page's geometry. A4 landscape, twelve month pages:

Two reach measures sit side by side because they answer opposite questions about the
same sentence, and neither is a summary of the other:

- *positional reach*, the renderer's instrument: with the record drawn alone in a
  cell of the page's geometry, does the fame text START — is at least one complete
  word of the reason clause drawn? *whole* means the reason's last word is drawn,
  positionally.
- *content reach*, `dev-qa`'s instrument: on the printed page, does the drawn text
  reach the fame's LAST word — does the reason FINISH? Its population is the same
  records on the shipped pages, and its number is theirs to state.

| Book / version | person records | person cells | cells drawing a fame line | positional reach (records, renderer) | content reach (records, dev-qa) | page sizes |
| --- | --- | --- | --- | --- | --- | --- |
| laureates, before `4f0143b` | 72 | 64 | 61 of 64 | 2 of 72 | not measured | 6.5, 9.5, 8.5, 9, 8, 9, 9.5, 8, 9, 9, 9, 9.5 |
| laureates, this change | 72 | 64 | 63 of 64 | 71 of 72 | not measured | 6, 9.5, 8, 9, 7.5, 9, 9.5, 7.5, 9, 9, 9, 9.5 |
| chemistry, before | 43 | 43 | 43 of 43 | 43 of 43 | not measured | 7, 7, 7, 7, 7.5, 7, 7, 6, 8, 7, 7, 7 |
| chemistry, this change | 43 | 43 | 43 of 43 | 43 of 43 | not measured | unchanged |
| laureates, at `1424186` | 72 | 64 | 62 of 64 | 71 of 72 (4 whole) | 3 of 72 whole | 6, 9.5, 8, 9, 7.5, 9, 9.5, 6, 9, 9, 9, 7 |
| chemistry, at `1424186` | 43 | 43 | 43 of 43 | 43 of 43 | not measured | 7, 7, 7, 7, 7.5, 7, 7, 6, 8, 7, 7, 7 |

The two laureate reach numbers at `1424186` — 4 whole positionally and 3 whole on the
page — are the same 72 records measured at opposite ends of the same sentence: a
record can start its reason and stop before its last word. They are not merged into
one figure, and neither is the audit's cell-level count below: that instrument
counts cells, these count records.

The operator's audit — `tools/redletter-fame-audit.py`, A4 landscape only, no
other shape has been measured; it freezes the sha into a scratch dir before
measuring and asserts its per-month pairing — counts qualifying complete words on
the cell as printed: of the 64 laureate cells, 58 show at least one answer word and
1 prints the answer whole (Urey), and 6 show none, against 3 with none at
`4f0143b`; chemistry is unchanged at that sha at 50% drawn, 67% answer, and 10
whole of 43 cells (the re-run at the tip of this work is in the next entry). The
two criteria are allowed to disagree: positional reach renders one record alone in
a cell, and the seven days that carry two or more laureates can lose one or both
lines when the cell is packed, so 71 of 72 records reach in isolation while 58 of
64 cells show a complete answer word on the page. The cells column is the one that
describes the printed book, and the audit is the instrument that measures it.

Six cells draw no complete answer word at all at this sha against three at
`4f0143b`: the fame line now prints at the cell's size, and on the densest pages
that costs whole cells their grey text. A change the printed book will show is
stated rather than footnoted; whether the trade is right is the density question,
which is separate from this one.

Chemistry is unchanged because no chemistry blurb opens with a label. Svedberg's
clause (`for his work on disperse systems`) reaches its last word positionally; the
one cell the audit counts whole is Urey's (`for his discovery of heavy hydrogen`).
The one record that still draws no fame line in the positional measure is von
Baeyer's, whose label and reason together exceed two lines at 9 pt.

*Why "fame drawn" is 64 in one report and 61 in another.* `dev-qa`'s 64 of 64
counts whether the two-line cap leaves at least one line, measured before the
page's height budget; the 61 of 64 above counts cells on the drawn page, after it.
Both are right about their own population: three cells had a fame line the cap
allowed and the page could not fit. This change gives two of those three back.

**Positional reach, defined.** The cell draws a prefix of the fame text in word
order — the wrapper keeps the order, the cap cuts the tail — so matching the drawn
words against the fame words from the start measures how far in the cell got. The
reason begins where the label ends, and `reached` is at least one complete word of
the reason clause. Any-word matching would be fooled by
the `in` that appears in both `Nobel Prize in Chemistry` and most reasons, which is
why the first measurement reported 69 of 72 before the fix: it was reading the
label as part of the reason.

*Where my before-numbers differ from the row's.* The row said 4 of 72 reached
before; `dev-qa` measured 0. Mine is 2, and the two are Prigogine and Langmuir,
whose labels are short enough that the connective prints whole — `Nobel Prize in
Chemistry 1977 in Russia: for hi…`. So the most generous reading of "any complete
word of the reason" still finds only the word `for`, and no cell showed a content
word of the reason before this change, which is the fact all three numbers are
reaching for. After it, 71 of 72 records reach positionally; the cell-level count
is the audit's column quoted above.

*The type cost, against the right baseline.* Relative to `4f0143b` four laureate
pages move, each by half a step: January 6.5 to 6, March 8.5 to 8, May 8 to 7.5,
August 8 to 7.5. Chemistry moves no page. The row's "the same 9 pages move" is true
against the pre-fame book (`ebb3b01`), where nine pages moved to make room for the
fame line at all; it is not the cost of this change.

**One predicate, two callers, and its known limit.** `verify_days.person_suffix` is
now the only definition of "this record is about a person". The gate
(`is_person_death`) and the renderer (`fame_line`) both call it, and a test asserts
the renderer's name is the gate's function, not a copy. It lives in `verify_days`
because that module has no drawing dependency, and the renderer imports it rather
than the other way round so the gate stays runnable without Pillow. Its limit is
that the unit is the title, and review found one break in each direction, neither
live: a spaceflight record titled `Vladimir Komarov dies` would be read as a
person's death and refused for want of a `work_caused` block, though that book is
not a people calendar; and `Marie Curie dies of aplastic anaemia` would not be read
as a person's death at all, so a title that carried its own cause would escape the
gate. Both are pinned by tests in `tests/test_verify_days.py` so a future change
either keeps them or has to delete a named expectation. The shipped data has
`Challenger is lost` as its only `kind: loss` that is not a person, and Curie's
title is the bare `Marie Curie dies`.

## 2026-11-16 · The fame line drops the birth clause the title already says

The operator's coverage work, relayed as the third amendment to
`qitem-20261116173409-5fc50da5dcfd761e`. The chemistry blurbs end "..., was born."
on 41 of 43 records and ", was born in Warsaw." on one; the title already says "X is
born", so the cell said it twice, exactly as it used to say the name twice.

**The rule, and its two guards.** A trailing ", was born." / ", died." clause comes
off, with its comma, so the drawn line ends on its last word rather than on a
dangling comma, and stays a substring of the approved blurb. The place goes with
the clause: Curie's birth ends ", was born in Warsaw." and lands on "the first
person awarded two Nobel Prizes". The strip is about the clause, not about
wrapping: a drawn line may end on a comma where the next line continues the same
sentence — 63 such lines across the twelve books at four shapes (13 at A4
landscape), every one continued on the very next line of that cell — and no cell's
final drawn line ends on one. That last is a narrow claim: most cells are cut by
the height budget and end on the truncation marker instead, 90 of 165 at A4
landscape after the legibility fix below, so it is the 75 remaining cells the
comma test actually covers. Two guards, both of them the same reasoning the
name strip already uses:

- It applies only to the sentence that leads with the person — the one the name
  strip produced. On a sentence that does not ("That inventor of the electrostatic
  precipitator, Cottrell, was born in Ohio.") the same words are the sentence's own
  predicate, and dropping them would leave a subject with nothing said about it,
  which is the failure the no-silent-stripping rule exists to prevent.
- The tail after the predicate is a place (`in`, then at most three words), not
  any words. An unbounded tail reads Curie's death sentence — "died of aplastic
  anaemia almost certainly due to her exposure to radioactive materials" — as a
  repetition and deletes the cause, which is the one thing that record is for. She
  is the guard's real case: her death is unchanged, her birth changes normally.

It is a no-op on all 72 laureate records and on any blurb that merely contains
"was born" mid-sentence; all three are pinned by tests.

**What it buys, measured.** Positional, per record, A4 landscape, twelve month
pages, with each record rendered alone in a cell of the page's geometry (the
criterion is the table's above, not the audit's cell columns):

| chemistry | answer median | cells missing answer text | whole answer | drawn median |
| --- | --- | --- | --- | --- |
| before this commit | 70.0% | 34 of 43 | 9 | 55.6% |
| with the clause dropped | 70.0% | 29 of 43 | 14 | 70.0% |

The whole-answer count moved and the median did not. Five records gained their
whole answer, each by exactly one word — Beilstein 6 of 7 to 7 of 7, Brønsted 7 of
8 to 8 of 8, Lecoq de Boisbaudran 5 of 6 to 6 of 6, Smalley 6 of 7 to 7 of 7,
Mulliken 5 of 6 to 6 of 6 — which is what eleven characters do at 6 pt: one small
word. The drawn median rises because the clause left the denominator, not because
text arrived where there was none. The laureate book does not move in any column.

The operator pre-registered the bound at "whole 10 to at most 14, median 67% to a
modest rise", with 33 cells missing answer text at `4f0143b`. My instrument reads
one cell differently at the start (9 whole, 34 missing) and lands on the same
ceiling: 14. So: the change completes five answers and does not raise the median at
all. It is kept for legibility — the cell stops repeating the title's own clause —
and because it costs no page a step of type; it is not kept for room it did not buy.

**The audit's re-run at the tip, and the invariant it closes on.** At `21b905e` the
audit reads: laureates drawn median 17%, whole 1, any 58, zero 6 of 64 cells;
chemistry drawn median 67%, whole 14, any 43, zero 0 of 43 cells; both books 0
labelled, pairing OK. Chemistry moved from 50/67/10 at `1097ed8` to 67/67/14 here,
and its 14 is my 14 on the same population: chemistry holds 43 person cells and 43
person records, the only shared day (10-07) carrying two events and neither of
them a person's.

The fact worth keeping is not either coverage number but this: **the drawn column
and the answer column are now identical in both books.** After the label rule and
the birth-clause rule, the drawn fame line *is* the answer — there is no chrome
left in the text to draw, so "how much of the line is drawn" and "how much of the
answer is drawn" are one measurement. The audit reproduces the identity in both
books at this sha, and that is the closing statement of the pair of rules: the
cell's grey text is the reason, all of it, however much of it fits.

## 2026-11-16 · A person's title is never cut, and a cell that cannot hold its records says so

`qitem-20261116174704-da27cf7c3ad0bf8c`, after the delta re-check of `21b905e`.
The month page drew a cell's records as one stream and cut it at a line boundary
when it ran past the cell's height. A cut inside a person's title prints half a
name; a cut before a later record prints no name for it at all.

**What the old renderer did, measured at `b703983`.** Read through `cell_blocks`
and the cell's one `truncate_blocks` call — the page's own path at that sha — at A4
landscape the laureate book drew 7 of its 72 person records incompletely:

- three with the surname not legible: two drawn as a fragment (03-19 `1900 Frédéric
  Jolio…`, 09-02 `1877 Frederick Sodd…`) and one cut before it (06-25 `1911 William H…`);
- three absent: 08-30 drew only van 't Hoff's record and lost Rutherford and
  Svedberg, and 12-25 drew only Windaus and lost Herzberg;
- one title cut with the surname still visible: 10-31 `1835 … von Baeyer is bor…`.

The classes move with the shape, so those bullets describe A4 landscape. The 12-25
cell is the one to read for the pattern, and the fill of its last line is what says
whose line it is: at A4 landscape and Letter landscape it draws no Herzberg line at
all and ends on Windaus's grey fame line (`for the service…`, `for th…`); at A4
portrait Herzberg's own ink title ends `1904` / `Gerhar…`; at Letter portrait it
ends `190…`, the ellipsis falling inside the year token, so the cell shows neither a
year nor a person. The name-not-legible counts by shape are 6 at A4 landscape, 4 at
A4 portrait, 5 at Letter landscape and 6 at Letter portrait.

Across the twelve books (three datasets at four paper shapes) the old path lost 25
person record-drawings, all of them in the laureate book: 7 at A4 landscape and 6
at each of the other three shapes. Chemistry drew all 43 person records whole at
every shape under this section's cut criterion (its cells are sparse), and
spaceflight has no person records; the word criterion the next section installs
finds one of them split — Vauquelin at A4 portrait.

Of those 25, 21 lost the name itself; the other four are names that stood whole
while the title text around them was cut — von Baeyer at both landscape shapes, and
Joliot and Soddy at A4 portrait. The two figures are one population under two
criteria, not a disagreement.

**The rule.** A person's title — the year and the whole name, continuation lines
included — is atomic. A cell lays every record's title down first and gives each
record's detail (its fame line, or a blurb) only what height is left, in record
order. Detail may still be cut with the ellipsis the cell already uses; a title may
not. A cell whose titles do not all fit draws the ones that do and a final
`and N more` line, charged the cell's own type and reserved by laying the records
out one line shorter: a visible count, because a record that vanishes without a
word is the defect this fixes. The page's type choice now refuses a size at which
any cell's records cannot all *start* — a person title whole, a prose title one
line — so the count is the fallback of last resort. A title that is not a person's
is ordinary prose (chemistry's day titles are whole sentences) and keeps the old
behaviour: cut like detail, and a cell holding none of them is byte-for-byte the
stream it had.

**The type cost, measured over the twelve books at the four shapes.** Only the
laureate book moves; chemistry's and spaceflight's chosen type is unchanged at every
shape. The months whose page type dropped, old to new:

| shape | months moved | pages |
| --- | --- | --- |
| A4 landscape | 2 of 12 | August 7.5 → 6.0, December 9.5 → 7.0 |
| A4 portrait | 1 of 12 | August 9.5 → 6.5 |
| Letter landscape | 4 of 12 | June 9.0 → 7.0, August 7.0 → 5.5, October 9.0 → 8.5, December 9.5 → 7.0 |
| Letter portrait | 3 of 12 | June 9.5 → 9.0, August 9.0 → 6.0, December 9.5 → 9.0 |

Every moved page is one whose day cells carry two or three person records — the
days this row is about. The alternative was to keep the type and let those cells
print `and 1 more`, which hides one of the six records this row names, so the type
went instead. The price is heaviest at Letter landscape August (5.5 pt, four drawn
cells on that page); the page is still readable and its three records are whole.

**After the fix**, at A4 landscape: all 72 laureate records, all 43 chemistry person
records and the spaceflight book's zero person records are drawn whole, surname
included, with no title ending on an ellipsis; the same holds at all four shapes.
A pinned test iterates the three datasets at the four shapes and asserts exactly
that, and a literal fixture (fixed width, size and block list) pins the fallback
count. The chosen laureate type per month at A4 landscape is now
`[6, 9.5, 8, 9, 7.5, 9, 9.5, 6, 9, 9, 9, 7]`.

**What the fix did at each shape, 25 December, read from the drawn blocks.** The
strings, because they are the measurement. Before is `b703983` through its own
`cell_blocks` and one `truncate_blocks`; after is `6a96a15` through the cell layout.

| shape | `b703983` | `6a96a15` |
| --- | --- | --- |
| A4 landscape | Windaus `1876 Adolf Otto` / `Reinhold` / `Windaus is` / `born`, grey `for the service…`; Herzberg absent | `1876 Adolf Otto Reinhold` / `Windaus is born`, grey `for the services rendered` / `through his research int…`; `1904 Gerhard Herzberg is` / `born`, grey `for his contributions t…` |
| Letter landscape | Windaus `1876 Adolf Otto` / `Reinhold` / `Windaus` / `is born`, grey `for th…`; Herzberg absent | `1876 Adolf Otto` / `Reinhold Windaus` / `is born`, grey `for the services` / `rendered through hi…`; `1904 Gerhard Herzberg` / `is born`, no grey |
| A4 portrait | Windaus `1876 Adolf` / `Otto` / `Reinhold` / `Windaus is` / `born`, grey `for the` / `service…`, then Herzberg `1904` / `Gerhar…` | both names in full; no grey at all — the cell's only fame line is spent |
| Letter portrait | the same Windaus, then Herzberg `190…` | Windaus grey `for th…`, then `1904 Gerhard` / `Herzberg` / `is born` |

At `b703983` Herzberg's title drew `Gerhar…` at A4 portrait and `190…` at Letter
portrait — at the second the ellipsis falls inside the year, so the cell showed
neither a year nor a person. At the tip the whole name draws at every shape, at A4
portrait by spending the cell's only fame line and at Letter portrait by cutting
Windaus's to `for th…` so Herzberg's three title lines fit. At both landscape shapes
the whole name and both reason lines are drawn together.

One line of the table is no longer the tip: at Letter landscape the density rule
("Every person in a cell gets a reason line before anyone gets a second") shares the
one line the cell can afford, so on the current tip Windaus draws `for the service…`
and Herzberg `for his contribution…`, one each, where the atomicity fix alone gave
Windaus two and Herzberg none. The after column is stated at `6a96a15`, the tip that
fix left, so the two changes can be read apart.

**What moves as a side effect** is the positional reach measurement: the laureate
book's whole-answer count goes 2 → 4 and drawn/reached stay 71 of 72, because the
two packed months are laid at smaller type and their fame lines fit whole. Nothing
in the data or the fame-line rules changed.

**Not fixed here.** At A4 landscape 56 of the 64 laureate cells still end on the
truncation marker — 63 before this change — so most cells are cut mid-sentence by
the height budget, as they were. That is the density question, not this row.

## 2026-11-16 · A name word is never split across a line

**What the page did, measured at `1424186`.** The cell's wrapper leaves a word
longer than its line whole until nothing else fits, then breaks it at a character
boundary (`fit_to_width` slices with `ln[i:i + chars]`). At 9.5 pt and 11 characters
— the portrait shapes' width — that drew two shipped records as a fragment plus a
stranded word:

- laureate 02-15: `1873 Hans / Karl August / Simon von / Euler-Chelp / in / is born`
  at A4 portrait and Letter portrait;
- chemistry 05-16: `1763 / Nicolas-Lou / is / Vauquelin / is born` at A4 portrait.

Nothing was cut, so the atomic-title test above passed at every shape: a split word
is drawn text and expected text at once when a test compares the cell to the
wrapper's own output. The measurement that sees it takes the reader's unit — every
word of the year and the name appears as a whole token on one drawn line.

**The rule.** The page's type choice refuses any size at which a word of a person's
title — the year included — cannot sit on one line: `len(word) <=
cell_chars(inner_w, size)` for every such word in every cell. The unit is characters
and not points because the splitter counts characters, and the width is the cell's
full width rather than the hung width because `fit_to_width` moves a continuation
line to indent 0 whenever the word fits there, so a word that fits the full width is
never broken. A size that cannot give a word its line is not a size for that page —
the same shape of refusal `cell_min_height` already applies to a title that cannot
start.

**Why a split is worse than a cut.** A cut announces itself: the cell's last line
ends `…`, every word still printed is a word the record contains, and the reader
knows a piece is missing. A split invents a boundary. `Euler-Chelp` / `in` is two
tokens where the record has one surname, and `1763 Nicolas-Lou is Vauquelin is born`
is a grammatical sentence asserting that Nicolas-Lou is Vauquelin — a false claim
drawn from a true record, with nothing on the page to signal it.

**The type cost, this change alone**, measured against `1424186` so it is not
confused with the title cost in the entry above. Three month-pages move, each by
half a step, and every one of them is a page that was splitting a word:

| shape | months moved | pages |
| --- | --- | --- |
| A4 landscape | 0 of 12 | — |
| A4 portrait | 2 of 12, one per book | laureates February 9.5 → 9.0, chemistry May 9.5 → 9.0 |
| Letter landscape | 0 of 12 | — |
| Letter portrait | 1 of 12 | laureates February 9.5 → 9.0 |

No other month moves at any shape, and the spaceflight book's chosen type is
unchanged everywhere.

**After the fix**, at all four shapes: zero split words across the three datasets. A
test iterates them and requires every word of every person's title to be a whole
token on one drawn line; it fails at `1424186` at exactly the three shape-cells
above. On the page, laureate 02-15 now draws its title `Euler-Chelpin` / `is born`
at A4 and Letter portrait (9 pt, 13 and 14 characters), and chemistry 05-16 draws
`Nicolas-Louis` / `Vauquelin is` / `born` at A4 portrait.

## 2026-11-16 · Every person in a cell gets a reason line before anyone gets a second

**Whose choice.** TJ's, at 18:52Z on 2026-11-16, relayed by the operator with two
constraints. `qitem-20261116185319-f262ff0764ab2ae8`. This is the density question
answered; the cell's grey text is the reason, and a cell about two people should be
about two people.

**The rule.** In a cell holding two or more people, every person takes one line of
their reason before any person takes a second, in record order. A cell holding one
person is unchanged: they keep the two-line fame they have. A cell holding no
person is unchanged. The line is one line's worth of the reason, not the whole
reason: at these cell sizes the complete text cannot fit without the type drop TJ
forbade, and the rest is what the cell's ellipsis hides.

**What it replaced.** Record order gave each person as many lines as fitted before
moving to the next. Measured on the shipped books through the drawn blocks, that
allocation was already ordered — an earlier person never had fewer lines than a
later one — but it was not fair: at Letter landscape 25 December Windaus drew two
fame lines and Herzberg none, and at Letter portrait 25 June Nernst drew two and
Stein none. A cell that names two people said something about one of them.

**After the fix**, those two cells draw one line each: Letter landscape
25 December `for the service…` / `for his contribution…`, Letter portrait
25 June `in recognitio…` / `for thei…`. No other multi-person cell changes at any
shape: A4 landscape's seven (01-23, 01-31, 03-19, 06-25, 08-30, 09-02, 12-25) are
2/2, 2/2, 1/0, 1/0, 0/0/0, 1/0 and 2/1 before and after, and nobody moves to an
`and N more` line anywhere. Those cells hold room for one reason line, so the rule
cannot give a second person a first line that does not fit.

**The constraint that was not spent.** A4 landscape's chosen type per month is
`[6, 9.5, 8, 9, 7.5, 9, 9.5, 6, 9, 9, 9, 7]` before and after, and all twelve
dataset-shape arrays are identical. The type chooser measures a cell's need through
`cell_blocks`, which this change does not touch; sharing detail differently cannot
move it.

**The audit delta.** At A4 landscape the four columns are unchanged: laureates
median 17%, whole 3, any 57, zero 7; chemistry 67% / 14 / 43 / 0. The rule is a
no-op at that shape, and that is the honest report, not a target met. The change
buys fairness where the cell affords two or more reason lines; where it affords one,
the first person still has it and the second is counted by nothing, because both
their names are drawn.

**Why the no-op is the constraint and not the rule.** At 8 pt in the 19 March cell
the box has 64.70 pt of height and the five title lines take 52.80 pt, so the detail
pool is 11.90 pt — 1.127 lines of 10.56 pt. A second reason line needs the pool to
reach 21.12 pt (2.0 lines), which is 9.22 pt more than the cell has. The round robin
hands the one line it can afford to the record that comes first, and Joliot is
named and dated instead. Reaching 2.0 lines would mean either more height
than A4 landscape gives that cell or a smaller type than TJ allowed, so nothing
moves there and nothing can.

**The criterion, in the form this rule can meet.** Not "every person draws a reason
line or is named on the count line" — at A4 landscape six of the fifteen
multi-person records draw no reason line and appear on no count line: the second
person at 03-19, 06-25 and 09-02, and all three at 08-30. They are visible because
their titles are drawn whole. The checkable form is **no person is invisible: every
person's title is drawn whole, and no person takes a second detail line before every
person has had a first.** The commit passes that at all four shapes; the first
wording it could never pass.

**What this makes deliberate.** The audit has been reporting seven laureate cells
with a zero-coverage fame line as a defect. Under this rule that is a choice: a
person whose cell cannot afford a second reason line is named and dated, not
described. The truncation counts and the zero seven stay as they are; this
entry is where the decision to leave them is recorded.

**The test.** The assertion is the gap, not the ordering: no earlier person draws
more than one line more than a later one, checked over the three datasets at the
four shapes. The ordering alone ("an earlier person has at least as many lines as a
later one") is satisfied by the old allocation as well, so it would have been a test
that could not fail; the gap has two violations at `6a96a15` and none here. Two
literal fixtures pin the ends: six lines of room is one reason line and it goes to
the first person, with no `and N more`; seven lines is one each, where record order
drew two and none.

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
