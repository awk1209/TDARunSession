# WWTC Scheduler — Guided Run (Runbook 8.17)

*TDA V3.1 · **Runbook 8.17 (2026-08-31) — Step 0.5 counts people, names its files, and types no
figure.** No lane change, no new module, no new courier stop, no step moves, and the only call in
this document that changes is what `materials_check` reports back. **The defect:** the materials
check announced a player total more than twice the size of the tournament. It added the four
lists' ROW counts together — which counts every player entered in more than one event once per
event, and then adds the Serve Tennis list, which is a subset of the Tournament Desk one, to its
own superset. That sentence has been read aloud on every run since 2026-08-08, including one that
completed and announced a calendar. Worse, a file whose name carries no `L1`/`L2` token answered
for **every** level at once, so two unlabelled uploads reported all four lists present with no
Level-1 list in the directory at all — and closed with *"Everything needed is here. Ready to
start."* **What changes:** the check counts distinct people by USTA ID; an unlabelled file may
stand in for one level only, and the levels it cannot cover are named instead of being reported
green; and the readback prints the file it actually read beside each count, naming any same-level
file it beat. The pick order itself is unchanged. **This step's readback goes to slots** — the
typed figures leave this document and none arrive, because a figure written here is read aloud to
a real director as though it were his (ruling 12). The check still never gates and never raises,
and the partial lane is untouched: a director with one unlabelled file walks through. Operator
ruling 2026-08-31 (PRE-2).*

*Previously — **Runbook 8.16 (2026-08-30) — September computes first and asks once.** No new module,
no new courier stop, and **the January branch is byte-identical**. **The defect, off the 8/29
September run:** to announce one calendar the director answered five scripted stops between the
search and the readback, and the tool asked before it had earned anything to show — may I check
your days, then separately what shall I price, then here is your board, then here is your booking
answer. He approved days before he had any idea what the week would cost him to book, and the
question that mattered — is this the week you want? — was never asked once with both answers on the
table. **What changes here, on the September lane only:** the check is no longer offered, it is
run, and the booking answer is worked out with it as **one silence** with one honest sentence
naming the wait; the days and the booking answer then arrive **together**, at a **priced board**
that ends in **one stop** — accept, edit a few days, or go further back — with every exit priced
off this run's own figures before he picks it; accepting **costs nothing and couriers nothing**,
and mints an **acceptance record** on the document carrying the fingerprint of the map he accepted,
the date, and whether he accepted the board as shown or after an edit; the finals-map paste now
lives **only** on the edit-a-few-days branch, which re-grades without asking again; and the court
answer's day-move savings leave the standing readback and become **ask-only**, each row now
carrying what it costs in the shape of his week and the configuration it is priced against.
**The September run's unconditional stops between the search and the announce readback go 5 → 3**
(the search offer · the two-calendars choice · the priced-board stop), counted by hand on the
shipped tree. ⚠ **The document's own elicitation markers go 14 → 15, and that is not a
contradiction** — the two numbers count different things, and a session reading one for the other
will report the opposite of what happened. The 5 → 3 is **September's own path**; the 15 is
**every marker in the document across both lanes**, and it rises by one because Step 2's check ask
and Step 3a both stay, as **January's** steps, while September's new priced-board stop is added
beside them. Counted by hand at this cut, on the same caveat STOP-1 recorded: a bare `grep -c` on
the marker also catches the two lines of the binding control rule that talk *about* stops, and
reads 16 → 17. ⚠ **The
incremental re-grade was specified, DRIVEN, and it does not ship.** Grading only the divisions he
moved and carrying the rest over was measured against a full pass on four graded edits across both
benches: **202 of 224 carried days agreed and 22 did not**, and the disagreements run the wrong
way — days a carried grade calls fine that a rebuild calls costly, and two it offers him at all
that a rebuild says cannot be played. So the re-grade is the whole pass, entered without a second
question, and the note at that step carries the measurement so nobody re-derives it. Operator
ruling 2026-08-30 (CF-1).*

*Previously — **Runbook 8.15 (2026-08-30) — the run surface speaks executive, and the standard is
countable.** No lane change, no new module, no new courier stop, no step moves, and no call in
this document changes. **The defect, off the 8/29 September run:** the "How the run speaks"
section was already BINDING and the run was still verbose and full of the tool's own vocabulary.
Two reasons, and the second is the one nobody had looked at. The rule capped which WORDS a
session may use and never capped HOW MANY, so a run could be long-winded and fully compliant at
the same time; and a judgment-word standard ("plain", "concise") is one a session grades itself
against and always passes. Then the scripts in this document were themselves the violation —
measured at this cut: **65 scripted texts, 6 of them over forty words, the longest 97, and the
fork's own ask, the first thing a director ever hears, at 59.** **What changes here:** the
binding section replaces the judgment words with **four countable caps** — an option is one line,
twelve words or fewer, action first · a readback leads with the figure and what it means in one
sentence, and your own words around a result stop at three · mechanism is spoken only when asked ·
the stranger test decides every sentence; **11 scripted texts are rewritten to them, 759 words
down to 479**, and the whole run surface's scripted speech goes 1,395 → 1,115 with the count over
forty words at 6 → 1; and `make_run_bundle.py`'s opening prompt now carries the four caps in six
lines, so they are the first thing every bundle session reads. ⚠ **The print-it-whole obligations
are untouched, and the cap says so in its own text** — a report, a refusal report and `sentences`
are data, not chat, and ruling 12 is not reopened. `LANG-1_glossary.md` is applied and never
reopened: no word added, none removed. Operator ruling 2026-08-30 (VOICE-1).*

*Previously — **Runbook 8.14 (2026-08-30) — the quieter-week search can be given more time, in
sittings.** No lane change, no new module, no new courier stop, no step moves. **The defect, off
the 8/29 September run's own report:** the search used its whole ten minutes, said it was still
finding better weeks, and offered to keep going — and there was no way to accept. This run surface
caps one step at ten minutes and backgrounding a long step is forbidden, so the longer single
search this document told the session to run could not be run at all (OI-B), and the director's
own question — what would more search time have found? — went unanswered (OI-A item 1). **What
changes here:** the two-calendars stop gains a third option, **keep searching**, offered only when
the search says it was still improving; each further sitting starts from the calendar he was just
shown, is given a named length before it is spent, and reports what THAT sitting bought in the
same three numbers; and the offer retires itself the moment a sitting runs out of improving moves.
The engine gains one opt-in parameter and there is still no run-state file — the seed is the
calendar he already has. Operator ruling 2026-08-30 (RESUME-1, "I want the resumable clock").*

*Previously — **Runbook 8.13 (2026-08-30) — the loop stops and asks, and one field can be kept
without a console trip.** No lane change, no new module, no step moves, and the three courier
stops are unchanged. **The defects, all three off the 8/29 September run's own report:** the
problem-solving loop at the end of Step 3.5 had no ⛔ stop, so a test that found a materially
better week was read out and walked past — the director had to halt the run himself to say he
wanted it (OI-2); keeping a one-number change cost a console trip plus Steps 2 and 3 in full, on
information the session was already holding (OI-3); and the first save of a couriered block was
hand-transcribed instead of copied, which dropped one added division and corrupted another,
because nothing in this document had ever said to copy rather than type (OI-C). **What changes
here:** the problem-solving loop ends in a ⛔ stop — keep this change · test another idea ·
carry on — fired after every `try_change` that returns, and it prices the keep before he chooses,
off this run's own measured timings; standing procedure 4 gains ONE inline lane, a single named
field of the last couriered setup on his explicit instruction, under six obligations that keep the
tie between his screen and his answer visible; and the same procedure gains the sentence saying a
couriered block is copied, never retyped. **The run's elicitation stops go 13 → 14** — counted by
hand at this cut, because a bare `grep -c` on the marker also catches the two lines of the binding
control rule that talk *about* stops, and reads 15 → 16. Operator ruling 2026-08-30 (STOP-1 —
OI-2's suggested shape, OI-3's proposed lane, OI-C folded in).*

*Previously — **Runbook 8.12 (2026-08-29) — five things the September run paid for by hand.** No
lane change, no new courier stop, no step moves; one new module function and one new deliverable.
**The defects, all five off the 8/29 September run's own report:** every finals console a run
published arrived in the director's gallery under one identical name, so the calendar he approved
and the proposals he discarded were indistinguishable; the announced calendar had no page at all,
so the run built a printable one by hand; the bundle cut no `.gitignore`, so the run's tree filled
with generated files; Step 3a told a director who had moved nothing that "the calendar he
announces will say those days were moved after the check", which is false in both halves on a
zero-move paste; and the booking answer said nothing about idle opening hours or unused floodlit
nights, both of which it was already carrying. **What changes here:** the guided console gains a
`doc_label` and the three publish sites pass one each; Step 3.6 writes a printable calendar page
beside the JSON, rendered off the announced record and re-deriving nothing; Step 3a branches on
whether the paste actually moved days and skips the offer where it did not; Step 3.5's readback
gains a three-line hours-and-lights slot in the ⛔ read-off-the-answer discipline. The engine's
outputs are untouched.*

*Previously — **Runbook 8.11 (2026-08-29) — the pre-flight stops asking, and holds only when
nothing at all reads.** No lane change, no new courier stop, no new module, and no step above or
below 0.5 moves. **The defect:** the run opened by asking permission twice — may I check the
imports, may I check your files — and the useful answer to both was always yes, so the two stops
bought nothing on a good run. On a bad one they cost the director his first move and then paid
him back in engineer language: a missing PDF reader reached him as a raw `ImportError`, and a
file set where NOTHING opened closed with a sentence promising the run carries on — the one state
where that is untrue. **What changes here:** both elicitations and all four of their option
labels go (2 of the run's 15 stops, and only those); Step 0 runs its imports directly and, when
they fail, stops in his language first and quotes the error second, naming the two remedy shapes
that actually occur; Step 0.5 always runs the check and goes three ways — everything read, go on;
something read, **carry on without asking**; nothing read, stop and sort it out with him. The
checker itself is unchanged in kind: `preflight.materials_check` still never gates and never
raises, and gains only a derived `nothing_usable` flag so no session has to invent the threshold.
Setup gains the two pip readers it never named. Operator ruling 2026-08-29 (OI-59, option 2, plus
the stop location and run finding 1).*

*Previously — **Runbook 8.10 (2026-08-29) — the added divisions are planned at his number, not at
three quarters of a bracket.** No lane change, no new courier stop, no new module, and no step
moves. **The defect:** Step 3.5's second elicitation told the director his added divisions are
planned at **75% of each bracket**. The engine stopped doing that at S-4, which retired
`round(draw_size x 0.75)` as a measured defect (assumed total 774 against a real 757, 38 of 42
rows carrying the wrong `room_left`), and S-2's seam draws each added division at the count he
states with his stated bracket as the ceiling — re-measured at drafting, 6 of 6 added divisions
drawn at his own number. The document also contradicted itself: Step 1.5 already said the added
divisions are built "at the sizes he stated". **What changes here:** that one sentence in Step 3.5,
and nothing else.*

*Previously — **Runbook 8.9 (2026-08-28) — the refusal answers in four figures, and the run reads it
as scripted.** No lane change, no new courier stop, no new module. **The defect:** on 2026-08-28 a
September re-run refused, and the section of the report that is supposed to say what to book
carried **none of the four figures a director needs** — not how many courts, not on which days,
not at what times, not for which divisions — while five of the six moves this step already
scripted existed only as prose and **two of them were skipped**. **What changes here:** Step 2's
refusal branch becomes a numbered ⛔ checklist of six moves, every one a MUST, with a four-figure
readback template whose every slot is read off the payload at run time and never typed; the
editor handover and the his-decision ask are held as text by a harness so a session cannot
quietly drop them again; a standing rule binds every re-test and what-if that ends in a refusal
to print the fresh report verbatim; and Step 3.5's surplus answer gains the three-slot readback
the deficit direction already had.*

*Previously — **Runbook 8.8 (2026-08-27) — the growth pass.** Step 3.6 gains the half of the growth
answer a bracket division never had: the readback now says the day play would begin once a
division outgrows its draw, or reads a sentence where his week has no room for the extra round —
and the calendar he shelves records what produced it, so a January reader can tell a day that was
checked from a day that never was. Step 3a's decline now names its own consequence.*

*Previously — **Runbook 8.7 (2026-08-27) — the truth pass.** Seven places where this document was
wrong, stale or silent, and where a session following it faithfully still produced something
untrue. **No lane change, no new courier stop, no new module**; one new elicitation, at the end
of Step 3.6. **The defect:** Step 5.5's call passed one of the build's two records under the
other's name, so on the last check before he publishes the report told the TD to move late starts
the tool had already proven had nowhere better to go — the call now passes both records, each
under its own name. **Then, in order:** Step 1 stops reading back a rule he was never given a
control for, and carries the one true sentence to use if he asks about it; Step 2's
recommendation is made on the size of his field and the days he has, never on that rule; Step 3.6
prints its own readback — one line per division, the announced days and what happens to each if
the entries come in bigger or smaller than last year — and stops for his answer before the days
go out; the matches-per-day default is corrected to the figure the tool actually defaults to;
Step 3.6 takes its date list off the setup he most recently pasted instead of a copy that can go
stale; the attach table gains the two modules Step 1.5 needs and Step 0 checks the one nothing
else would catch; the opening fork confirms the kind of run the prompt already declared instead
of asking it again; and one note records that long steps run in the foreground. Everything below
from 8.6's note down is as it shipped.*

*TDA V3.1 · **Runbook 8.6 (2026-08-25) — Step 3.5 answers in both directions.** No lane change,
no new courier stop, no new module, and no step above or below 3.5 moves. What changed is what
that step now hands back and how it is read out. When the week does NOT fit it carries the JAM —
the club, the day, the hours and how many of that club's courts were in use through them, with a
frame line saying which booking is being described — then what to buy, which club to open on
which days, and nine of the director's own rules re-run for real. **It no longer offers to
shorten matches or to add days, on any surface and in either season** (Operator rulings, 8/24 and
8/25); the section says so rather than leaving their absence to be noticed. When the week DOES
fit it carries the other half — what he has booked beyond what the tournament needs, in courts,
club-days and opening hours, with a register line that decides the verbs: on `facts` the session
recommends nothing. A six-axis reading of his resources against his tournament arrives with both.
And the step gains a LOOP: when he proposes a change, the session BUILDS it with `try_change`
rather than reasoning about it — court edits or rule edits, one build, counts only, and asking it
for a schedule is refused by design. Testing an idea needs no re-courier; keeping one does.
⚠ **The stale hidden-`pacing` paragraph is DELETED** — S-3 put that control back on screen, so the
instruction never to send him to it had become false. The principle it served is kept and its
example re-points to the one section still hidden. The reference field is unmoved. Everything
below from 8.5's note down is as it shipped.*

*TDA V3.1 · **Runbook 8.5 (2026-08-23) — the run opens with a fork.** No lane change, no new
courier stop, no new module, and nothing below Step 0 moves. One new elicitation at the very
top of the Step map (Operator ruling 8/23): before anything runs, the session asks whether
this is a **plan & announce** run (the September kind) or a **full schedule build** (the
January kind), then names the files that path needs and confirms they are attached — so a
missing file costs a sentence at the door instead of a stop mid-run. The September list needs
nothing extra attached for the divisions he is adding — they are typed on the Setup console and
ride the block he couriers back; the January list names the announced calendar from the shelf, with the
honest note that the tool does not yet read it back into a build. The mental-model note and
the Setup section now point at the fork; Steps 3.5 and 3.6 keep their own are-you-sure
checks. The reference field is unmoved. Everything below from 8.4's note down is as it
shipped.*

*TDA V3.1 · **Runbook 8.4 (2026-08-23) — the Setup list corrected, and the divisions he is
adding enter a September run.** No lane change, no new courier stop, and a January run sees
none of it. Two things move. **First:** the Setup module list gains `finals_publish.py` and
`finals_announce.py` and its count goes **18 → 20** — Step 3.6 imports both, and neither
build that shipped that step (PUB-1 · ANN-1, 8/23) added its module here. A bundle built by
reading the old list hard-blocks at Step 3.6, after the director has approved his finals
days: the fourth time this list has gone stale. The bundle is now CUT AND VERIFIED by the
repo's `make_run_bundle.py`, never assembled by reading the list. **Second:** a new
**Step 1.5**, September planning runs only (Operator ruling 8/23): the divisions the
director is adding next year — which are in no draws file, because they have never been
played — enter the field from **his own answers on the Setup console** (S-2), stated as an
estimate at every use, so the court answer at Step 3.5 and the calendar at Step 3.6 carry his whole
tournament instead of leaving the new divisions off. Steps 3.5 and 3.6 each gain one
matching caution. The reference field is unmoved. Everything below from 8.3's note down is
as it shipped.*

*TDA V3.1 · **Runbook 8.3 (2026-08-23) — the refusal now says what to BUY, and one elicitation
stops being required.** No lane change, no step change, no new courier stop, and a week that
schedules normally sees none of it. Two things move. **First:** where 8.2 had the refusal name
its reasons and offer six fixes — every one of which rearranges courts the clubs already have —
it now ends with a further section naming **how many courts, at which club, on which days, and
in which part of the day**, each figure re-run for real against these entries; and where it
cannot find an answer it says so and says what it tried. Steps 2 and 4 still print the report
**verbatim** and still stop there: nothing about who decides has changed. **Second:** Step 3's
first elicitation no longer demands each club's own court count — it is asked for, blank is
accepted, and what blank costs him is said out loud. **The reference field is unmoved**, and a
week that schedules sees nothing new at all. Everything below from 8.2's note down is as it
shipped.*

*TDA V3.1 · **Runbook 8.2 (2026-08-21) — one new branch, no lane change and no step change.**
Two steps gain what to do when **the week as supplied cannot be scheduled at all** — a week
with more matches than its courts can hold. Until now that ended a run with a Python exception
and no scripted next step. It now ends with answers: **Step 2** picks up the refusal off the
plan document and prints it, **Step 4** catches it off the build and prints it, and both stop
there and put the fixes to the director. There is nothing new to import, no new courier stop,
no new option on any elicitation, and a week that schedules normally sees none of it. The
reference field is **unmoved at 760 placed · 275 byes · 0 unplaced · 0 conflicts**. Everything
below from 8.1's note down is as it shipped.*

*TDA V3.1 · **Runbook 8.1 (2026-08-08) — one correction, no lane change and no step change.**
The Setup module list gains **`preflight.py`** and its count goes **17 → 18**. Step 0 imports
`materials_check` / `materials_check_text` from it and Step 0.5 calls them, so a run bundle
built by reading 8.0's list hard-blocks at Step 0 before the director sees anything. Nothing
else in this runbook moves — same three courier stops, same steps, same options, same words.
Everything below from here is 8.0 as it shipped.*

*TDA V3.1 · Runbook 8.0 — FINAL (CUI-5). The finishing pass. **The pre-publication report is now
part of the run** — a new **Step 5.5** between the edit loop and the deliverables that grades the
schedule you are about to print against **your own numbers** (the rest floor, the day bands, the
age floor, the court counts, the lights hour — all read from what you set in Setup) and shows you
every finding before anything is generated. It **reports and pauses; it never refuses**. The
sentence in 7.7 that said "the reporter is still not wired into the guided run" is retired: it is
wired, and this is the step. **Two new things to hand out at Step 6** — a **run-of-play sheet**
for each site and day (the order of play you post at the desk) and a **player schedule** for each
entrant (their matches, with their partner named on a doubles line). **Court numbers no longer
appear anywhere they were never assigned.** Every printed line used to say `court None`, and the
courtside sheet grouped an entire site-day under one heading called "court None"; the sheets now
say the site and the day, and courts stay what they always were — a decision you make at the desk
on the morning. **The two-rounds-on-one-day warning now says what it costs a person:** it used to
read "this division plays rounds 2 and 3 on this date", and it now reads *whoever wins the 08:00
match is back on court at 11:00*. Same words in the Edit console and in the report. **Three panels
in the Edit console fold** — "Where can this go?", "Substitute a partner", and "Entered, but not
in a draw" — each with a ▸/▾ caret and **all three open by default**; folding one gives the
right-hand column its space back. **No lane change and no courier change:** same three courier
stops, and a zero-edit emit is byte-for-byte what it was. The reference field is **unmoved at 760
placed · 275 byes · 0 unplaced · 0 conflicts**.*

---

## Running the run — the four things you can always do

*These are manners, not machinery. Nothing here writes a file the scheduler reads: the run's
state IS the blocks you have pasted, which is what makes every one of them safe.*

> ### 0 · How the run speaks — BINDING on every RUN session (A7 N4)
>
> **Everything the run says to the tournament director is plain English.** No schema names, no
> code words, no internal ids, no engineering vocabulary — in spoken readbacks, in elicitation
> prompts, in what you paraphrase off a screen.
>
> **FOUR CAPS, AND THEY ARE COUNTABLE** *(VOICE-1, Operator ruling 2026-08-30)*. They replace
> "plain" and "concise", which were judgment words a session graded itself against and always
> passed. What was capped was which WORDS you may use; how MANY was never capped at all, so a run
> could be verbose and fully compliant at the same time — which is what the 8/29 September run
> was.
>
> 1. **An option is one line, twelve words or fewer, action first.** *"Keep this change"* — never
>    a clause explaining the mechanism behind it, and never a second copy of something the question
>    above it already said. Two places name a thing rather than an action, both deliberate and both
>    counted: Step 2's two calendars are named for what each calendar IS (read off the block, never
>    typed), and Step 6's list is a list of documents.
> 2. **A readback leads with the figure and what it means, in one sentence — and your own words
>    around any result stop at three sentences.** The cap counts YOUR commentary. A step's own
>    instruction to the director — press this, copy that, paste it back — is not commentary, and
>    ⚠ **a printed document is not commentary either: a report, a refusal report and `sentences`
>    are DATA, and every step below that says to print one whole and verbatim still means it**
>    (ruling 12). This cap never shortens one of those and never excuses skipping one.
> 3. **Mechanism is spoken only when asked.** How the tool arrived at a number is not part of the
>    number. A direct question about how something works still gets a real, full answer.
> 4. **The stranger test — check every sentence against this one.** A director who has never seen
>    this tool acts on the sentence without asking what a word means. If a word would need
>    explaining, it is the wrong word.
>
> **`LANG-1_glossary.md` is the authority on the word for each concept**, and it is closed: a
> match is named by division, round and players, never `E36-R1-M14`; a final held to a date is a
> **locked day** and a match held to a court and time is a **locked slot**, never a "pin"; a
> division playing twice in a day is **two rounds in one day**, never "cadence"; matches that
> did not get on the schedule are **not scheduled**, never "unplaced"; courts and days are
> **courts & days**, never "the slate"; and the document the desk produced is the **Raw Draw**
> while anything this tool renders is a **System Draw** — say which one, every time (glossary
> §2a, ruled 2026-08-09; the phrase those two replace named both and distinguished neither).
> **It is applied here and never reopened.** The word list says which word; the four caps above
> say how many, and neither one substitutes for the other.
>
> **Real tennis vocabulary stays** — bye, walkover, seed, draw, round robin, Quarterfinals,
> WTN, FAC II.A, 16-draw. Replacing those would make the tool sound like it does not know the
> sport. So do the **load-bearing names**: file names, function names, config keys and the
> `td-` schema names keep their exact spelling *inside a block*, and are simply not spoken —
> at the courier stops you say "the setup block", "the finals map block", "the edits block".
>
> The anti-pattern, recorded verbatim from the Operator driving the 2026 run: a Step-4 readback
> that said `coverage: reconciliation counts 1066 scheduled entries; … -> MATCH`. It now says
> *"1,066 on the schedule, 1,066 in the player file. Agree."*

1. **Start a run with one message.** Say **"start a WWTC run"** — or *"let's run the scheduler"*,
   *"guided run"*, *"run the WWTC scheduler"*, *"start the guided run"*. Any of those begins at
   Step 0 and the assistant drives one step at a time from there (the binding control rule below).
   Nothing else is needed to begin.

2. **Go back a step.** Say **"go back to Step N"** at any point. The assistant returns there and
   re-runs from that step forward. What still stands and what must be regenerated, per step:

   | Going back to | Still stands | Must be regenerated |
   |---|---|---|
   | Step 1 (Setup) | nothing downstream | the finals-map editor, the schedule, the editor console, every deliverable |
   | Step 3 (Finals map) | your `td-setup/v1` block | the schedule, the editor console, every deliverable |
   | Step 4 (Schedule) | `td-setup/v1` + `td-finals-map/v1` | the editor console, every deliverable |
   | Step 5 (Edit loop) | all three blocks above | the editor console (standing procedure 2), the report, every deliverable |
   | Step 5.5 / 6 | everything above | only what you ask for again |

   **This is safe because the engine is deterministic:** replaying the same blocks reproduces the
   same schedule, byte for byte. It is never safe to keep a console you generated before the
   change — that is standing procedure 2, and going back is exactly when it bites.

3. **Name a run.** Give the run a label when it starts — *"call this run friday-draft"*. The label
   is used for the output folder (`outputs/friday-draft/…`) and in the artifact titles, so two
   runs on one day do not overwrite each other. It is a **convention, not a field**: no couriered
   document carries it, nothing validates it, and the engine never sees it.

4. **Pause and resume.** Stop whenever you like — **the couriered blocks are the state.** Keep the
   ones you have (the pasted `td-setup/v1`, the `td-finals-map/v1`, any `schedule-edits/v1`, and
   the run label) and a fresh session resumes by starting at Step 0 and **pasting them back in
   order, unedited**. Determinism does the rest: the same blocks give the same schedule. Standing
   procedure 4 governs — **never hand-edit a courier document to "catch it up"**; regenerate it
   from the console that owns it.

   *There is deliberately no run-state file. A file the run wrote and later read back would be
   state outside the courier lane — a stale one silently resuming the wrong run is a failure shape
   the lane exists to prevent.*

---

*TDA V3.1 · Runbook version 7.9 — SWAP-1 makes **"Where can this go?" answer two questions**
(Step 5). With a placed card selected, the same button now lists open slots above and, under
them, **up to four clean swaps** — another match on the same day that the selected one could
trade places with. A swap is only offered when **both** cards land cleanly, so nothing becomes
placeable without notice; the rows are ranked by least disruption (fewest people affected, then
smallest time change, same venue preferred) and no two rows are the same kind of trade.
**Hovering a row outlines its partner on the board**; clicking **Swap** performs the exchange
through the same guards a drag uses, and if any step refuses, both cards stay exactly where they
were and the console says why. When nothing survives it says **"No swaps available."**
**The all-clear is now complete:** "Nothing clashing here ✓" covers **round ordering** — a
semifinal can no longer be dropped ahead of the quarterfinal that decides who plays in it. That
one is a **hard stop**, like venue hours: the scheduler refuses to build such a board and the
checker reports it, so a drag that broke it would only be refused later, at the end of the lane.
Holding the earlier match first still lifts the rule, so there is always a legal path through.
**No lane change and no courier change:** same three stops, a swap rides the emitted block as
**two ordinary move instructions** (nothing new to key, nothing new for the reader to learn), and
a zero-edit emit is **byte-for-byte** what it was. The reference field is **unmoved at 760 placed
· 275 byes · 0 unplaced · 0 conflicts**.*

---

*TDA V3.1 · Runbook version 7.8 — DRAW-1 puts **partner substitution in the Edit console**
(Step 5). A doubles player drops out: the TD selects the match, opens the **Substitute a
partner** panel, and picks a replacement from the entered-but-not-drawn pool — every candidate
is shown, and one who is already in the Raw Draw or whose withdrawal is unclear is visible
but not selectable, with the reason on the row. **The team's seed drops by default; one click
keeps it, and keeping it requires a recorded reason** that travels with the change. **A
substitution that would make two doubles partners meet in round 1 is blocked outright** — the
message names both players and the division. Substituted cards wear an orange **SUB** tag
(hover names who came in for whom) and every change lands in the **Re-enter at the desk** panel,
grouped in the one division order — that list is what the TD keys back into Tournament Desk,
and it rides the same emitted `schedule-edits/v1` block as the moves (a new `substitute`
instruction; `apply_schedule_edits` consumes it and re-checks every consequence, including the
incoming player's other divisions). **The all-clear grew:** "Nothing clashing here ✓" now also
covers **travel time between venues** and **each division's daily match cap** — both warn,
never block. Round ordering is still not covered (SWAP-1's). A zero-edit emit is byte-for-byte
what it was; no lane change, same three courier stops.*

---

*TDA V3.1 · Runbook version 7.7 — ENG-1 makes the **schedule follow the director's day**. Four
rules the tool only knew on paper are now rules it obeys. **One match per division, per player, per
day** — the Setup console's **Matches per day** control is live and defaults to **1**; the box no
longer says "not read yet", and the number on screen is the number the scheduler uses. **The day
runs in order:** singles early, mixed doubles in the middle, gender doubles late. **No final starts
before 9:00 a.m.** — finals only; semifinals can still start at 8:00, and nine of them do. **A
player in three divisions on one day gets the 9:00 / 12:00 / 3:00 head start.** **One new control on
the Rules tab: Same-day finish** — name a division and its last two rounds run on the same day, the
gap apart, for players who asked to finish and travel home. It is **off unless you name a division**
and nothing is ever assumed. Read the gap twice: it sets how long after the semifinal the final
starts **and** it becomes the rest those two matches are held to — the one place the three-hour rest
rule gives way. **What is new on screen in Step 5:** matches the scheduler could not fit into the day's order
anywhere are listed in the Edit console's warning bar, grouped by day — placed rather than dropped,
and named so you can see where the rule could not be kept. **What you will notice in the output:** the totals are unchanged at **760 placed ·
275 byes · 0 unplaced · 0 conflicts**, but **107 of the 760 matches sit somewhere different** — 99
at a different time on the same day, 8 on a different day. That is the expected, approved
consequence of turning the four rules on, not a fault. **The pre-publication report — NOT part of this run — now grades
against your own numbers** rather than its own copies: the rest floor, the day bands, the age
floor, the court counts and the lights hour all come from what you set in Setup, and it gains one
new warning when more than nine matches start between 3:00 and 4:00. **Stated plainly so nobody
looks for it: the reporter is still not wired into the guided run.** Step 4 prints placed / byes /
not scheduled / conflicts and the engine's advisories, as it always has; `schedule_report` is reachable
only from code today, and CUI-5 is the build that puts it in the run.
*(**Superseded at 8.0** — CUI-5 wired it in. The report runs at **Step 5.5**, between the edit
loop and the deliverables. This paragraph is kept as the 7.7 record, not as current instruction.)*
**No lane
change and no courier change:** same three stops, and a zero-edit emit is byte-for-byte what it was.
The Edit console's "Nothing clashing here ✓" is unchanged in meaning — it still does not cover
travel between venues, per-division daily caps, or round ordering.*

---

*TDA V3.1 · Runbook version 7.6 — CUI-3 makes the **Edit console's cards say who is on them**.
Every real player on a card now carries their **seed**, the **number of events they entered**, their
**rating** (the WTN matching that card's own format — singles on a singles card, doubles on a
doubles or mixed card; a player without that number shows none rather than the other one) and a
**round single-letter locality badge** — **green L** for the home cluster, **red C** for a commuting
city, nothing for anyone matching neither. The badge is a fact about the **person**, not about the
match: it says where they live and nothing about when they play. **It replaces the old blue name,
the ◆ suffix and the ◆ LOCAL pill** rather than joining them, so there is one locality mark instead
of three. **Step 5's call gains one argument, `roster=b["players"]`** — without it the cards render
exactly as they did before, so the snippet below is the version to copy. **Two honesty fixes:** a
rest warning now reads **"Rest <1h 40m"** instead of `Rest <1.6666666666666667h`, and the console's
advisories learn **per-venue hours** and each division's **earliest start**, so "Nothing clashing
here ✓" now means those too — it still does **not** mean travel between venues, per-division daily
caps, or round ordering. **New: "Where can this go?"** on the selected card sweeps the visible day
and lists only slots that are **completely clean**, ranked nearest-first, with the board showing the
same numbered candidates; when nothing survives it says **"No clean slots this day."** Nothing
becomes placeable without notice — a manual drag still warns exactly as before, and accepting a
suggestion emits the **same block** a drag emits. The division picker is now **filterable** and the
bracket shows a **window of rounds** with steppers instead of the whole draw. **No lane change and no
courier change:** same three stops, and a zero-edit emit is **byte-for-byte** what it was. The
reference field is **unmoved at 760 placed · 275 byes · 0 unplaced · 0 conflicts**.*

*TDA V3.1 · Runbook version 7.5 — FMAP-1 makes the **finals map count**. The editor the TD gets at
Step 3 now carries **two summary rows under the dates** — **Matches** (how many matches that day's
plan holds) and **Finals s/d** — and **both recompute on every drag**, so the two facts that decide
a move are now beside the move instead of far below it. A day past the TD's own threshold **fills
amber**; nothing new blocks, and the one hard refusal on that surface is still the finals day a
division's rounds cannot physically reach. **The Matches row is a PLAN, not a measurement** — it is
what the approved draws put on that day, counted from the draws themselves rather than guessed from
bracket size, and it is labelled as a plan on the page. The thresholds are the TD's own: whatever
was set on the Rules tab at Step 1 is what ambers here, replacing the fixed 6-and-6 the map used
regardless. **Three smaller corrections:** dragging a division no longer offers a day the board will
then refuse (the dashed outline now appears only where the final can actually land), division rows
read **singles → mixed → doubles** within an age band instead of mixed → doubles → singles, and the
refusal names its day the way the columns do (**"Sat 1/24"**, not `2026-01-24`). **No lane change and
no courier change:** same three stops, same steps, and the emitted block is **byte-for-byte what it
was** — a zero-drag emit is still exactly the engine's draft. The reference field is **unmoved at 760
placed · 275 byes · 0 unplaced · 0 conflicts**.*

*TDA V3.1 · Runbook version 7.4 — WIRE-1 makes the **Rules tab honest**. Every field it shows now
either binds the schedule or is gone, so what the TD reads on that tab is what the run does.
**Match duration is live:** the picklist offers **60 / 75 / 90 only** (longer blocks would cut a
60-and-over player's rest below the USTA minimum, and the tab says so) and the engine now builds
the day on the pick — change it and the schedule changes. **Four dead controls are gone**
(minimum rest floor · round-robin threshold · singles before doubles · singles one day ahead), as
is the duplicate tournament name and the **decoy rest field** on Venues & days, where a floor the
TD set was silently overridden by the Rules tab's copy. The staging checkbox now reads **≥3
divisions**, which is what the code has always done. **Two new inputs** set day load — matches per
day (125) and finals per day (9 singles / 4 doubles) — which are **warnings the finals map will
show, never limits**; they reach the couriered block now and the finals map reads them from the
**next** build, so until then it still uses its own 6-and-6. **7.5:** that next build shipped —
the finals map now reads both thresholds from the couriered doc, and the 6-and-6 is gone. A **read-only box** at the bottom of
the tab lists what the tool does on its own and, deliberately, what it does not. **On Venues &
days, ORLP and WEST now close at 16:30** (MHCC unchanged at 17:45), making 15:00 the last
90-minute start offsite — the TD's own rule, previously not encoded. **No lane change and no
courier change:** same three stops, same steps. The reference field is **unmoved at 760 placed ·
275 byes · 0 unplaced · 0 conflicts** — every one of these changes was proved against that.
A legacy rules block carrying one of the removed fields is now **refused with the reason**, rather
than being quietly ignored; re-emit it from the console to migrate it.*

*Runbook version 7.3 — ROSTER-1 adds **one new deliverable at Step 6: the exceptions
list**, the entered-but-not-playing roster with the desk's own words on each row. Nothing else in
the lane moves: same courier stops, same steps, same engine. It exists because "0 unplaced" only
ever meant every match the tool BUILT, it placed — it never compared the entry lists against the
schedule, so a person entered and left out of every draw was invisible. The run now reports a
closed accounting (entries = scheduled + exceptions) and a non-empty exceptions list is the
expected result, never a fault.*

*Runbook version 7.2 — SLATE-1 reworks how the Setup console's **Venues & days** tab
asks for courts and days; the lane, the courier stops and the engine are unchanged.
**Days now live on the venues.** Each venue lists the days it is open and the tournament runs
across whatever those add up to — the separate Dates panel is gone, so a day with no venue open
can no longer be entered. **Court availability reads as plain rows:** a day shows "All day: N
courts, from–to", or, where the club releases courts later, a "Morning: N courts until HH:MM" row
above a "Rest of day" row. Those two rows are the same `morning_courts` / `morning_until` fields
the engine has used since R7-3 — the mechanism did not change, only the words. A venue can be
**duplicated and renamed** (for splitting court loading across one physical club), and the tab now
states **the latest time a match can start** on the current numbers, so the TD never has to work
back from the finish-by time. **New prefilled defaults** (ruling D8, measured from the real 2026
week): the window is **08:00 → last match finishing by 17:45** and capacity is **MHCC 20 / ORLP 12
/ WEST 4** — the observed concurrency peaks, pending club confirmation, and TD-editable as always.
**7.4:** the two offsite venues carry their own closing time — **ORLP and WEST finish by 16:30**,
so 15:00 is the last 90-minute start there, while MHCC keeps the 17:45 window.
Each venue also carries **lit-court fields** (MHCC 7 from 16:00; blank elsewhere until the TD
answers Q7): from the lights hour onward these are a **hard ceiling** (rule 48 / LIGHTS-1) — the
venue can run only as many matches at once as it has lighted courts. Blank = no ceiling.
*(Corrected 2026-08-23: this line used to say the fields changed nothing, which was true when it
was written and stopped being true at LIGHTS-1.)*
**Reference figures move with the capacity change:** the combined field still places
**760 / 275 / 0 / 0**. The moved-day count is **deliberately not quoted here** — it is
reported, never asserted, and varies with the courts and days and any locked days in play. Report what the run
returned (DOC-03, 2026-07-31).*

*Carried forward from 7.1 — CUI-2 restyled the run surfaces without changing the lane.
Every console now shares one house style (light mode, larger type, full width), carries a
**warning bar at the top** as the single place problems appear, and puts **emit · copy · the
block you copy** above the fold. **Copy is honest everywhere:** where the clipboard is blocked
(a published artifact frame blocks both the clipboard API and `execCommand`) the page selects
the block and says which keys to press, instead of reporting a copy that never happened — the
defect both CUI-1 sims hit. The **moved-day list and master warnings now reach the Edit console's
warning bar** rather than living only in the Step-4 report, and a conflict introduced by an
edit stays on screen until it is fixed rather than surfacing only in the applied-edits report.
Emitted JSON is byte-identical to 7.0 on all three surfaces (golden-diff verified).*

*Carried forward from 7.0: the Setup console is two tabs (**Venues & days · Rules** — the
Ingest review tab is retired; a bad ingest fails loudly instead), the **Edit console is
generated preloaded** with the schedule (the TD never handles `td-editor-plan/v1`), and every
console reaches the TD as a **published private artifact link**. Three courier stops, unchanged:
`td-setup/v1` → `td-finals-map/v1` → `schedule-edits/v1`. From 6.x: every ⛔ step has ≥2
options, portable output paths, RR divisions bind (F7-4), sanctioned defaults fast path,
infeasible locked finals days refused in-editor AND rejected at the gate, master warnings surface at
Step 4.*

This is a **behavioral runbook**, not a copy/paste script. The assistant drives the full
scheduling run — the finalized WWTC draws → **draw sheets + per-player CSV** — by presenting
plain-language choices as **elicitation widgets** at each step. You tap a choice; the assistant
runs the correct underlying action. **You never copy a prompt out of this file.**

> **For the assistant — binding control rule (read before running anything):**
> When the user signals a run (e.g. "start a WWTC run", "let's run the scheduler", "guided run"),
> drive the steps below **one at a time**. At every step marked **⛔ ELICIT**, you **MUST**:
> 1. call the elicitation tool with that step's options,
> 2. **end your turn and wait** for the user's tap,
> 3. only then run that step's mapped action.
>
> **Never batch steps. Never auto-advance. Never run a later step before the user has tapped the
> current one.** Running the whole flow and reporting results afterward is a failure of this runbook —
> even when the result would be correct. One ⛔ ELICIT = one tap = one action, in order.
> Keep the engine deterministic and the console/engine decoupled.
>
> **Consoles publish as artifact links (7.0 — replaces the 6.1 side-panel auto-open).** At
> every step that involves a console or edit surface, you **publish the HTML as a private
> claude.ai artifact page the moment the step begins and hand the operator the link** — one
> click opens a real browser tab where JavaScript and the clipboard both work. Never wait to
> be asked, and never drop the console as a bare HTML card or a download. Publishing is
> automatic; the paste-back remains a ⛔ courier stop.
> **Fallback:** if the surface cannot publish an artifact, write the file under `outputs/` and
> give one-line open-in-browser instructions — the consoles are self-contained and work from a
> local file identically.
> **Consoles ship publish-ready (CONS-1) — do NOT wrap anything at run time.** Every surface the
> TD is handed now carries `<!doctype html>` in the repo: both console files and the draw-sheet,
> re-enter and run-of-play/player-sheet renderers. The 2026 run's Step 1 failed because
> `setup_console.html` had no doctype and the artifact renderer refused it; that session added
> the line live. Nothing to remember now — if a publish is ever refused for a missing doctype,
> that is a defect to report, not something to patch in the run.
>
> **Every ⛔ step offers ≥2 options (6.1).** The elicitation widget requires at least two.
> Single-action steps carry the standard second option **`Hold here — not yet`** → stop and
> wait; never invent a different filler option.
>
> **What counts as doing the step right vs. wrong (the run keeps failing on this):**
> - ✅ RIGHT: at a ⛔ step, your turn contains a call to the elicitation tool and nothing that
>   advances the run. You then stop and wait for the tap to arrive as the user's next message.
> - ❌ WRONG: writing "Ready to plan? Let me know" as prose and stopping. A silent pause is **not**
>   the same as calling the tool — if there's no tool call, you skipped the step.
> - ❌ WRONG: running the step's code first and showing results, then asking. The tap comes **before**
>   the action, never after.

---

## The mental model

> **⚠ TWO KINDS OF RUNS — the fork at the top of the Step map asks which one this is, first
> thing, before Step 0.**
> The product runs twice a year (`CLAUDE.md` "The product"; the frame is Operator-locked
> 8/22). A **September planning run** uses last year's field as the stand-in with the coming
> January's real venues and dates, plus the divisions the director is adding (Step 1.5), runs
> the court budget (Step 3.5), announces the calendar (Step 3.6) and stops there — its purpose
> is a booking answer and an announced calendar, not a full schedule. A **January live run** uses the real field and runs every step through the
> deliverables and re-entry at the desk. The 2026 data in this repo is the **calibration bench**: a 2026
> replay is a validation exercise, never the product's goal — a run session polishing the
> 2026 schedule for its own sake has drifted.

- **The engine** is the scheduler `.py` files. Deterministic: same input → same output.
- **The pipeline** (`wwtc_pipeline`) ingests the finalized 2026 WWTC draws + player lists
  (L1 Mixed doubles + L2 singles/gender doubles) and schedules **both levels in one shared-court
  pass**.
- **The Setup console** (`setup_console.html`) is where a run starts: **Venues & days · Rules**
  in two tabs (7.1 labels — these were *Slate · Constraints*), both prefilled with the canonical
  WWTC defaults (no finals, no ingest review — see below). **7.2:** the Venues tab carries the
  days themselves (one list per venue, no separate Dates panel) and its prefill is the measured
  2026 envelope — 08:00 → finish by 17:45, MHCC 20 / ORLP 12 / WEST 4 (**7.4:** ORLP and WEST
  finish by 16:30). **7.4:** the Rules tab's fields all bind now — match duration is live at
  60/75/90, the dead controls are gone, and two day-load inputs are emitted for the finals map.
  It emits a **single** `td-setup/v1`
  block; the button that produces it now reads **Build my setup**. 7.0: a bare emit carries **no
  overrides** — draws ingest as printed, and a malformed file raises a clear error instead of
  asking for a human review pass.
- **The finals-map editor is GENERATED, not a repo console.** After ingest, the engine derives
  its proposed finals map (Pass 1, finals-anchored) and the run surface writes a self-contained
  interactive HTML file — divisions × days, each division one draggable card. The TD repositions
  finals and emits `td-finals-map/v1`, couriered back. A `td-setup/v1` carrying an embedded
  `finals_map` is **stale** and is rejected loudly.
- **The Edit console is GENERATED too (7.0).** After scheduling, the run surface projects the
  result (`editor_plan`) and writes the edit surface **preloaded with the schedule**
  (`editor_plan.render_editor_console`) — division-primary, opening matches across all days.
  The TD never sees or pastes `td-editor-plan/v1`; the repo's `schedule_editor.html` is the
  template. The console emits `schedule-edits/v1`, which the run surface applies via
  `scheduler_flow.apply_schedule_edits`.
- **The engine and the consoles never talk.** A human moves each JSON block between them (the
  "courier"): each edit surface *emits* JSON; you paste it into the run. Consoles never read files
  or call the engine. (Generated surfaces get their data embedded at generation — the
  courier-back is unchanged.)

What changed from 6.2 (CUI-1): the Setup console lost its Ingest review tab (the
`td-ingest-review-overrides/v1` contract is retired; loud ingest crash guards are the safety
net); the Edit console became a generated preloaded artifact (its paste path is gone); consoles
now reach the TD as published private artifact links with `outputs/` browser-open as the
fallback.

What changed in 7.2 (SLATE-1): the Venues & days tab only — days moved onto the venues (no
separate Dates panel), court availability reads as up to two plain rows per day over the
unchanged R7-3 fields, venues can be duplicated, the latest legal start is stated, and the
prefilled courts & days are now the **measured** 2026 envelope (08:00 → finish by 17:45; MHCC 20 / ORLP 12
/ WEST 4) with per-venue lit-court fields that nothing read *at 7.2* — ⚠ they became a hard
court ceiling at LIGHTS-1; see the 7.4 note above. **No lane change and no
courier change:** the three stops are as before, and `td-resource-slate/v1` gains only optional
fields. The reference field still reads **760 placed · 275 byes · 0 unplaced · 0 conflicts**.
The moved-day figure is **not quoted** — reported, never asserted (DOC-03, 2026-07-31).

What changed in 7.1 (CUI-2): appearance and wording only — one light house style across all
three surfaces, a warning bar at the top of each, emit/copy/output above the fold, copy that
reports failure honestly instead of claiming success, and the engine's moved-day list and master
warnings surfaced in the Edit console rather than only in the Step-4 report. **No lane change
and no contract change to anything emitted** — the three courier stops and every emitted block
are identical to 7.0.

---

## Setup (do this first — one time)

1. **Start a new chat inside the project.** Turn on **Code Execution and File Creation**.
2. **Install the two reader libraries the run needs:** `pip install pypdfium2 openpyxl`.
   *(PRE-1, run finding 1, 2026-08-29 — neither was named anywhere in this document, and a run
   that session hit both. `pypdfium2` reads the draws PDFs and is imported at the top of
   `draws_pdf.py`, so without it Step 0 fails on its very first import; `openpyxl` reads `.xlsx`
   player lists and is imported lazily inside `wwtc_ingest.read_table`, so without it Step 0
   passes clean and the failure surfaces at Step 0.5 instead — as the tool's own problem, not the
   director's file. Attaching every module in the table below does not supply either one: they are
   pip packages, not project files.)*
3. **Make the project modules available** (attach or rely on project knowledge). **The set is
   the table below** — `wwtc_pipeline.py` and its imports. *(The count is deliberately not
   restated here: this line read "20 modules" over a table of 21 from the 8.1 correction until
   S-1, and a director attaching by count drops one and hard-blocks at Step 0. Attach the table.
   `make_run_bundle.py` derives the count from its own list and prints it at the cut.)*

   | | | |
   |---|---|---|
   | `wwtc_pipeline.py` | `wwtc_ingest.py` | `draws_pdf.py` |
   | `scheduler.py` | `scheduler_multi.py` | `scheduler_flow.py` |
   | `resource_slate.py` | `constraints.py` | `master_schedule.py` |
   | `finals_plan.py` | `finals_guidance.py` | `serve_tennis_intake.py` |
   | `division_order.py` | `finals_publish.py` | `finals_announce.py` |
   | `draw_sheets.py` | `csv_export.py` | `editor_plan.py` |
   | `schedule_report.py` | `schedule_views.py` | `preflight.py` |
   | `projected_field.py` | `field_source.py` | |

   — **and the console template `schedule_editor.html`** (the Step-5 edit surface is generated
   from it) — plus the 2026 data under `data/wwtc-2026/`: the **six-file set** (TD + ST player
   lists and the L1/L2 finalized-draws PDFs). *(7.0 fix: the list previously omitted
   `scheduler.py` — a top-level `scheduler_multi` import — and `serve_tennis_intake.py` — the
   Step-4 ingest path's lazy import; a live run hard-blocked on the latter.)* *(REVIEW-1, 8/7:
   `finals_map_from_pdf.py` and its input `26_WWTC_Approved_Draws.pdf` are STRUCK from this
   list — the module has zero production callers (`wwtc_pipeline.py` does not import it; only
   two harnesses do), and its PDF resolver silently takes the alphabetically first match in the
   data dir, so wiring it into a run invited last year's draws in. The module itself stays in
   the repo for its tests.)* *(8.0: three more added — `division_order.py` (DIV-1's one display
   order; **missing from this list since DIV-1 shipped 8/5**, and a run attaching only what was
   listed would have hard-blocked on it), `schedule_report.py` (Step 5.5) and
   `schedule_views.py` (Step 6's two sheets).)*

   *(**8.1, 2026-08-08 — `preflight.py` ADDED and the count corrected, 17 → 18.** 8.0 declared
   this list "the computed import closure of Step 0's entry points", but the closure was
   computed from the pre-CONS-1 entry points and `preflight.py` was never added when CONS-1
   put it in Step 0 and Step 0.5 the same day. **Step 0 imports `materials_check` and
   `materials_check_text` from it and Step 0.5 calls them**, so a bundle built by reading this
   list hard-blocks at Step 0 — the third time this list has gone stale and the second time it
   would have stopped a live run. **`avoidance.py` is NOT in the set, and that is deliberate**:
   `preflight.avoidance_flags` imports it inside the function behind `try: import avoidance /
   except ImportError: return None`, and no run step calls that function — so its absence is
   silent rather than blocking. If a later build wires the avoidance report into a run, it
   joins this list in the same build, because a silent `None` on a printed report is worse than
   a stop.)*

   *(**8.4, 2026-08-23 — `finals_publish.py` and `finals_announce.py` ADDED and the count
   corrected, 18 → 20.** Step 3.6 imports both — the calendar's date-and-label call and the
   announced start days (PUB-1 · ANN-1, both shipped 8/23) — and neither build added its module
   here. A bundle built by reading this list hard-blocks at Step 3.6, after the director has
   approved his finals days: the fourth time this list has gone stale. The standing fix is the
   repo's `make_run_bundle.py` — it cuts the bundle from this list, then proves it the way the
   paragraph below says, so a missing module fails the cut instead of the run.)*

   *(**8.7, 2026-08-27 — `projected_field.py` and `field_source.py` ADDED.** Step 1.5 has been a
   product step since S-2 and both modules ride the bundle the script cuts, but neither was ever
   added here: the fifth time this list has gone stale, and the first that bites only a director
   attaching **by hand**. `field_source.py` was covered by accident — `wwtc_pipeline`,
   `draws_pdf` and `wwtc_ingest` all import it at the top, so Step 0's very first import fails
   without it — but **`projected_field` was covered by nothing.** Its first load is Step 1.5's own
   `import projected_field`, so a set missing it passes Step 0 clean and dies after the director
   has filled in the console and made a courier trip. Step 0 now imports it for that reason. The
   recurrence is closed on the tooling side as well: `make_run_bundle.py` compares this table
   against its own list at every cut and refuses one that disagrees, naming what drifted.)*

   **Verify a bundle, never assume it** — copy the files into an EMPTY directory, take the
   source tree off `sys.path`, and import every Step-0 entry point from there. That is the only
   check that catches a module the list forgot, and it is what the three stale-list incidents
   above have in common: each was found by a run, not by reading.
4. **No browser tabs to prepare.** Every console reaches you as a published artifact link
   during the run — the Setup console at Step 1, the finals-map editor at Step 3, the
   preloaded Edit console at Step 5. Attach `setup_console.html` alongside the modules so the
   run surface can publish it.
5. Say **"start a WWTC run."** The assistant takes it from here — its first question is the
   fork: which kind of run this is, and what that kind needs attached.

---

## Step map (assistant: elicitation → action)

Each step gives the **plain-language options** to show and the **action** to run for each.

### The fork — which run is this?  *(the run's FIRST elicitation, before Step 0)*
*(Operator ruling 2026-08-23 — the run opens by asking, and then says what to attach. The two
kinds of runs are defined in "The mental model" above; this step is where the question is
actually put, so a session never has to infer it. **S-8, 2026-08-27: the opening prompt may have
answered it already** — the prompt the cut script generates declares the run kind in its first
line, so every bundle run arrives with the answer in hand — and where it has, this stop
**confirms** it rather than asking again. The stop itself is never skipped: a declared kind is
still an assumption until he says so out loud.)*

**⛔ ELICIT — your action for this step IS the tool call. Call the elicitation tool with the options below, then end your turn. Do not run any code, do not write a prose question, do not pause silently — those all count as skipping the step.**

**Which words go on the widget is decided by the opening prompt, never by preference.**

**Where the opening prompt already declared the run kind** — every bundle run — read back what it
said and offer him the switch: *"This session opened as a September planning run. Confirm, or
switch."*, with the options **`Confirm — plan & announce`** and **`Switch — full schedule
build`**. Name the kind the prompt actually declared, not the one you expect.

**Where nothing declared it**, ask: *"Two kinds of run. **Plan & announce** gives you a court booking answer and the calendar you announce; **full schedule build** gives you the schedule, the edit screens and the printouts. Which is this?"*

Both forms land on the same two routes:
- **`Plan & announce (the September run)`** → the September path: Steps 0 → 3.6, with
  Step 1.5, Step 3.5 and Step 3.6 in; the run ends at the announced calendar.
- **`Full schedule build (the January run)`** → the January path: Steps 0 → 6, with
  Step 1.5, Step 3.5 and Step 3.6 skipped.

**Then name what this path needs attached, in plain words, and confirm it is all present
before Step 0.** If anything is missing, say which and wait — this is the one moment a
missing file costs a sentence at the door instead of a stop mid-run.

**Plan & announce needs:**
- **Last season's two player lists per level and both draws PDFs.** The TD always has these
  from the season just played; they are the stand-in field. In a rehearsal the bundled
  `data/wwtc-2026/` set plays this part; in a real run his own exports do — a file the
  resolver cannot bind by name is caught and confirmed at Step 0.5, never lost.
- Next season's venues, dates and rules are **typed, not attached** — they go in on the
  Setup console at Step 1. **So are the divisions he is adding**: they have their own section
  on that console (S-2), ride back in the same one couriered block, and become a field at
  Step 1.5. Nothing extra is attached for them, and there is no workbook.

**Full schedule build needs:**
- **This season's two player lists per level and both draws PDFs** — the real field, his own
  exports, never the bundle's data set.
- **The announced calendar from the shelf** — the file the plan & announce run wrote at
  Step 3.6. Ask for it by name and keep it beside the run, and **say the honest half out
  loud**: the tool does not yet read it back into the build — checking January against the
  announced days is a later build — so today it rides with the run so the announced days are
  on the table and the right file stays on the shelf.

Then go to Step 0.

### Step 0 — Confirm imports  *(PRE-1, Operator ruling 2026-08-29 — this step no longer asks)*
*(OI-59. The useful answer to "may I check the imports?" was always yes, so the question bought
nothing on the runs where everything was fine — and on the run where something was actually
wrong it spent the director's first move on permission and then handed him a raw `ImportError`.
The check runs itself now. What changed is not whether it runs, but what he hears when it fails.)*

**Run the import block directly** — straight after the fork's attach confirmation, no stop and no
question. Import `build_from_setup` and `finals_plan` from `wwtc_pipeline`,
`render_finals_console` from `finals_plan`, **`render_guided_finals_console` from
`finals_guidance`** (FMAP-2 — Step 2's editor comes from the wrapper, not the frozen renderer),
`apply_schedule_edits` from `scheduler_flow`,
`render_all` **and `render_rekey`** from `draw_sheets`, `write_csv` **and
`write_exceptions_csv`** from `csv_export`,
`editor_plan` and
`render_editor_console` from `editor_plan`, **and `import serve_tennis_intake`** (Step 4's
ingest path loads it lazily — importing it here surfaces a missing file now instead of a
mid-run hard block; a 7.0 sim hit exactly that). **8.0 adds the two the new steps need:
`scheduled_from_result`, `report` and `render_text` from `schedule_report` (Step 5.5) and
`run_of_play_by_court`, `schedule_by_player`, `render_run_of_play_html` and
`render_by_player_html` from `schedule_views` (Step 6).** Every one of these is checked HERE
for the same reason `serve_tennis_intake` is: a module that first loads at Step 5.5 turns a
missing file into a hard block after the TD has already done the editing.
**CONS-1 adds the two the materials check and the new Step 1 need: `render_setup_console` from
`wwtc_pipeline`, and `materials_check` and `materials_check_text` from `preflight`.**
**SETUP-2 adds one more: `dates_from_draws` from `wwtc_pipeline`** — Step 1 calls it before it
renders, so a missing name would block the run at its first screen.
**S-8 adds one more: `import projected_field`** — nothing else in the run loads it, and its own
first use is at Step 1.5, on the far side of the console trip. Found there, a missing file costs
the director everything he has already typed in; found here, it costs a sentence at the door.
Confirm they import cleanly.

**If they import cleanly — one sentence, and straight on to Step 0.5.** *"The pipeline modules
all load."* Nothing else: no counts, no module list read back, no question.

**If anything fails to import — ⛔ STOP, and say it in his language FIRST.** The raw
`ImportError` is the second thing he reads, never the first — the same discipline Step 0.5 has
always had for files, and 2026-08-29 is the run where its absence here cost a director his
opening move. Say what is wrong, then quote the error verbatim, then name the fix. Two shapes
cover what actually happens:

- **A module file was not attached** — the error names it (`No module named 'schedule_views'`
  and the like, for any name in the table above). Tell him which file is missing, ask him to
  attach it, and resume at Step 0. Do not carry on without it and do not work around it: the
  module list is the attach table in Setup, and a run missing one of them hard-blocks later, in
  a worse place.
- **A reader library is not installed** — this is the tool's own problem, not his files, and it
  must be said that way. **`pypdfium2`** is imported at the top of `draws_pdf.py`, so its
  absence fails Step 0's very first import: *"this machine can't read PDFs at all yet — that's
  the tool's setup, not your draws."* **`openpyxl`** is imported lazily inside
  `wwtc_ingest.read_table`, so its absence passes Step 0 clean and surfaces at Step 0.5 instead,
  as a tooling record the materials check already names as the tool's own problem — *"this
  machine can't read spreadsheets at all."* Either way the fix is the same and it is not his to
  diagnose: `pip install pypdfium2 openpyxl`, then resume.

### Step 0.5 — Check the materials  *(CONS-1 / Operator ruling 8.2; PRE-1 ruling 2026-08-29)*
*(OI-59. The option to skip this step existed because the check was optional. It is not any more —
it is read-only, it takes seconds, and it is the only thing standing between a bad file and a
console built on top of it. So the step stops asking and just runs.)*

**Run the check directly** — no stop, no question:
```python
materials = preflight.materials_check()          # read-only; never raises, never blocks
print(preflight.materials_check_text(materials))
```

**Read the result back in plain words, with the counts** — in this shape, and every figure in it
read off `materials` on the run:

> *"Draws read: `<divisions>` divisions — `<n>` at Level 1, `<n>` at Level 2. `<people>` people on
> your entry lists: `<n>` at Level 1, `<n>` at Level 2, `<n>` on both."*

⚠ **EVERY `<slot>` IS READ AT RUN TIME AND NONE OF THEM IS EVER TYPED** — the same rule Step 2's
four-figure readback carries, for the same reason (ruling 12). `materials_check_text` composes
this line from the files that run actually read, and names each one, so read its output back
rather than writing your own. Two things it says that a session must not re-word: `<people>`
counts **people, not rows** — the check joins on USTA ID, so a director entered in three events
is one person — and the sentence is about **the lists just read**, never "your field". At this
step the tool holds last year's entries and nothing else; the field is not settled until the
stand-ins are built.

**Then it goes one of three ways** (PRE-1, Operator ruling 2026-08-29):
- **Everything read** — go to Step 1, as today. Nothing else needed.
- **Some of it read, some did not** (`nothing_usable` is `False` and `ok` is `False`) — **carry
  on to Step 1 without asking.** Name what is missing and any candidates the check found, offer
  the in-session repairs below, and go. **Do not stop here.** A director whose draws are perfect
  and whose one player list is misnamed must walk through this step, not be held at it — that
  is the whole shape of ruling 8.2 and it is unchanged.
- **Nothing read at all** (`materials["nothing_usable"]` is `True`) — **⛔ STOP.** Say it plainly
  — *"none of the files I have here will open, so there is nothing to build your setup from"* —
  work the troubleshooting list below with him as the script, and wait. This is the one state
  where the old closing line ("the run carries on") was untrue, and it is now the runbook's stop.

**If something is wrong, troubleshoot it with the TD in his language. Never quote the raw error
first.** Fix what can be fixed here, in this session:
- **A file is there under the wrong name** → the check names the candidate it found. Confirm it
  with him — *"there's a file here called `scan of the draws.pdf` with 4 divisions in it; is that
  your Level-1 draws?"* — then point the run at it and re-run the check:
  ```python
  os.environ["WWTC_DRAWS_PDF_L1"] = "<the path he confirmed>"   # or _L2 / WWTC_TD_LIST / WWTC_ST_LIST
  ```
- **The file name says nothing about the level** → read a few pages, tell him which level you see,
  and assign it with the same override once he confirms.
- **The PDF asks for a password** → ask him for it and open it with that.

**What cannot be fixed here, said plainly, with the outside fix named:**
- **The file was never provided** → *"export the draws from Tournament Desk as a PDF and attach
  it."* His choice whether to pause or carry on without.
- **A scan or a photo** (`no-text`) → *"this is a picture of the draws rather than a printout —
  go back to the program and print to PDF; don't scan the paper."*
- **A corrupted upload** (`unreadable`) → ask him to attach it again.
- **A year whose layout the tool does not recognise** → this is the A6b format-drift rule: report
  it and route it to the Engineer as its own brief. **Never patch a parser live in a run.**

**THE CHECK NEVER GATES — and as of 2026-08-29 the RUN holds in exactly one state.** Two
different truths, and both are load-bearing:

- **The function never gates and never raises.** `preflight.materials_check` reports on every
  state of the materials, including a completely empty directory, and returns. It has no refusal
  in it and is not to be given one — the stop below is the runbook's action, taken by the
  session reading the report, never the checker's.
- **Whatever read cleanly is used**, and whatever did not falls back to the typing boxes in
  Step 1, with the typo-catcher (OI-54) still on guard at the door. A tournament with perfectly
  good draws must never be stuck at the first step over *optional* questions — 8.2's reason,
  intact, and a nothing-usable stop does not touch that case: there are no good draws to be
  stuck over.
- **The one hold:** when `nothing_usable` is `True` — not one draws file and not one player list
  opened — there is nothing for Step 1 to be built on, and the run waits with him instead of
  publishing a console over an empty field. Any partial state carries on.

### Step 1 — Setup console → one `td-setup/v1` block  *(courier stop 1)*
**GENERATE the console first, then publish it (CONS-1 — the shape Steps 2 and 5 already have):**
```python
dates = wwtc_pipeline.dates_from_draws()                 # SETUP-2: HIS dates, off HIS own draws
html = wwtc_pipeline.render_setup_console(dates=dates)   # embeds the names AND the days (~0.3s)
print(f"{dates['window'][0]} to {dates['window'][-1]} ({len(dates['window'])} days) · "
      + " · ".join(f"{v} {len(d)}" for v, d in dates["venues"].items())
      + (f" · no match scheduled on {', '.join(dates['window_only_days'])}, "
         f"opened at {dates['main_site']}" if dates["window_only_days"] else ""))
```
Write that HTML to a file and publish THAT as the private artifact — not the repo file. It is the
same console with the two division questions turned into pick-from-your-own-draws instead of
type-a-name, **and with the fifteen-odd venue-day rows carrying HIS tournament's dates instead of
the file's hardcoded ones** (SETUP-2). **If it raises** (a draws file with no text in it), say so
plainly, publish the repo file `setup_console.html` instead, and carry on — that is the fallback
lane, both division fields stay as typing boxes and the dates stay as the file's own. `dates=` is
safe on a bad read by construction: an empty window falls straight through to the same lane.

**⚠ THE DATES ARE A PREFILL HE CONFIRMS, NEVER A FIGURE THE TOOL ASSERTS (rule 8), and this run
must not describe them as his.** The derivation is *measured* to disagree with a real committed
courts & days on 2 of 3 venues, in both directions — a day nobody plays on is invisible to it, and the
desk stamps venue-days the courts & days do not open. Say **read** and **check**, never "your dates are".

**⚠ A NO-LIGHTS CLUB'S MUST-FINISH-BY IS ITS DUSK HOUR.** A venue with no lit courts has no
after-dark protection except its own finish-by time — nothing in the tool refuses a late match on
an unlit court. When handing over the link, say so: any club without lights should have its "last
match finishes by" set no later than dusk at that club.

**⚠ SEPTEMBER BRANCH — the derived window is LAST JANUARY'S, BY CONSTRUCTION (S-1 §1-E4).** In a
**September planning run** the only draws in existence are the season just played, so
`dates_from_draws()` can only ever return last January's window: planning January 2027 in
September 2026, it reads **2026-01-23 → 2026-02-01, 10 days**. The January path below is
unchanged; on the September path, present it as what it is and then ask for next January's:

- **Say what was read, and say plainly that it is last season's.** *"Off your draws I read
  `<window>` — that's last season's tournament, not next January's."*
- **Then say what next January's days ARE, and ask him to confirm them — do not ask him to type
  them.** The 2027 seed below already carries them (2027-01-22 → 2027-01-31, 10 days), so asking
  for something the run is holding would be theatre and would invite a second, disagreeing answer.
  ⚠ **The fork promised him these would be typed. That promise is now over-served, not broken —
  say so in one line** (*"I already have next January's dates from your own answers — check them
  rather than typing them"*), because a director braced to type and then not asked will assume
  the tool guessed. **If the seed is missing, this reverts to the typed question exactly as the
  fork promised.**
- **Then generate the console on HIS clubs and next January's days.** ⚠ **THERE IS NOW A COMMITTED
  SEED AND THIS RUN MUST USE IT** — the Operator gave his 2027 answers on 2026-08-24 and asked for
  them as the default, so the run no longer re-asks for five clubs' courts and hours every
  September:
  ```python
  import json
  seed = json.load(open("data/wwtc-2027/setup_seed_2027.json"))
  html = wwtc_pipeline.render_setup_console(setup=seed)     # clubs, days, rules, added divisions
  ```
  `setup=` is S-6 §1-B's slot and it takes the WHOLE `td-setup/v1` document. The seed carries the
  whole answer — five clubs with their courts, hours, lit courts and morning step-up; the ten days
  2027-01-22..31, both in the document's own `dates` and inside each club's `available` map; every
  venue pair's travel time; the tournament window, 08:00 → **18:00**; **his rules**; and **the six
  divisions he is adding next year**, with their team counts, draw sizes, formats and levels. No
  `dates=` and no `venues=` argument is needed or wanted here: the one document carries all of it.
  ⚠ **`venues=` IS THE WRONG SLOT FOR THIS FILE AND FAILS SILENTLY.** It still exists, for a
  caller that holds only clubs, and handing it the whole document leaves his rules and his six
  divisions off the screen entirely — which is the defect that made the 2026-08-25 run plan 50
  divisions against a real 56 while reporting `0 added`.
  ⚠ **THE `_note` POP IS GONE WITH THE `_note` KEY.** The seed is a real `td-setup/v1` now, not a
  venues-shaped file with prose in it.
  ⚠ **THIS SUPERSEDES THE OLD "NEVER A FILE" RULE FOR THE VENUES SLOT, on Operator instruction.**
  That rule existed because no file carried next year's venues and a run inventing them would be
  asserting figures nobody gave it. One does now, and it holds HIS OWN typed answers.
  ⚠ **WHAT THE RULE PROTECTED IS UNCHANGED AND STILL BINDS: it is a prefill he CONFIRMS, never a
  figure the tool asserts** (rule 8). The readback below still says **read** and **check**, and he
  can change any of it on the screen. Patching the generated HTML remains the forbidden door.
  ⚠ **IF THE SEED IS MISSING OR WILL NOT PARSE, DO NOT INVENT ONE.** Fall through to eliciting the
  clubs as before and say which lane was taken — a run that quietly makes up five clubs' court
  counts is the failure this whole step is shaped to prevent.
  ⚠ **THE SEED IS 2027's.** A later year needs its own file and its own Operator answers; do not
  re-date this one.
- **Both stay a prefill he confirms, never a figure the tool asserts** (rule 8) — the readback
  below still says **read** and **check**.

**Then hand over the link. SAY WHAT THE TOOL READ FIRST** — the readback above goes IN the
elicitation message, before he opens a screen with fifteen date boxes on it. A wrong date is
easiest to catch when he is told what to look for, hardest when he is scanning a grid.
**⛔ ELICIT — your action for this step IS the tool call. Call the elicitation tool with the options below, then end your turn. Do not run any code, do not write a prose question, do not pause silently — those all count as skipping the step.** *"I read your tournament off your own draws as `<window>`, `<the per-venue day counts>`."* — and, if there is one, *"Nothing is scheduled on `<day>`, so I've opened it at `<club>` — confirm or remove it."* — then the link: *"Your dates, courts and rules are already filled in. Check the Venues & days and Rules tabs, press Build my setup, then Copy, and paste the block back here."*
- **`Use the defaults as-is`** → the TD confirms the console's prefilled courts & days + rules and pastes
  the emitted `td-setup/v1` JSON back.
- **`I edited the setup`** → same path; the TD pastes their edited `td-setup/v1` JSON.
- **`Skip the console — run canonical defaults`** → no paste; the assistant uses
  `setup = {"schema": "td-setup/v1"}` (resolves identically to a bare emit — the canonical
  WWTC courts & days + default rules, no overrides). The stale-`finals_map` rejection stays covered
  by the goldens on this path. **⚠ THIS PATH IGNORES THE DERIVED DATES AND USES THE 2026 FIXTURE
  COURTS & DAYS — say so when you offer it, in one clause, if the readback above printed a different
  window.** It is the right path for a 2026 replay and the wrong one for any other year, and
  after the run has just read his real dates aloud, silence here would read as agreement.

> **⚠ A SECOND `td-setup/v1` INVALIDATES `plan` AND `fmap` (S-1 §1-E5).** If the director comes
> back to this step and pastes a new setup — corrected courts & days, a changed window, a club
> added or removed — then **Step 2 and Step 3 are re-run before Step 3.5 or Step 3.6 use `plan`
> or `fmap`.**
> Both were built on the setup he has just replaced. Step 3.6 announces the days off `fmap`, so
> skipping the rebuild **announces a calendar built against a superseded window** — and a calendar
> announced against the wrong window is the one mistake in this run that cannot be taken back,
> because his players have already been told. *(Step 3.6 reads its date list off `setup` rather
> than `plan`, so the window itself is always the one he last pasted; what goes stale is `fmap` —
> finals days chosen against days that have moved.)* In the 2026-08-23 rehearsal the two windows
> happened to match and nothing showed; that was luck, not a check.

> **Assistant:** on the paste paths, keep the bundle whole:
>
> ```python
> setup = json.loads(pasted)                       # td-setup/v1 — no finals_map in it (F7)
> ```

> **⚠ Assistant — READ BACK ONLY WHAT HE CAN SEE AND SET ON THE SCREEN (CAP-1, 2026-08-27).**
> The block he pastes carries more than the console shows him. **A value in the block with no
> control on the screen is the console's own default — it is never his answer, and it is never
> spoken as his.** Read back the venues, the days, the rules he was shown, and the divisions he
> is adding. Nothing else.
>
> **The one that has bitten: `match_caps`.** It emits with every block and there is no control
> for it anywhere on the screen — its control was removed on purpose. **Do not read it back, do
> not describe it, and do not reason from it** — not about how full his days are, not about
> whether to run the check at Step 2, not about anything. A run that treats it as his answer is
> telling him he set a rule he was never shown.
>
> **If he asks directly what it does, this is the whole answer:** it limits a player to one
> match a day *within a single division* — so somebody entered in three divisions can still play
> three matches that day, and usually does. It is not a limit on his day. On this field it made
> no difference at all: every one of the 760 matches lands on the same day, the same time and
> the same court at either setting (re-measured 2026-08-27).

### Step 1.5 — Put the divisions he is adding into the field  *(SEPTEMBER PLANNING RUNS ONLY — skip it in a January run)*
*(Operator ruling 2026-08-23 — the September run carries the new divisions. No courier stop:
this runs in your own session and nothing crosses a console boundary. A January run has the
real field; skip straight to Step 2.)*

**Why this step exists.** In September the only draws in existence are last January's. The
divisions the director is adding next year have never been played, so they are in no file —
and without this step the court answer at Step 3.5 prices a tournament that is missing them,
and the calendar he announces at Step 3.6 leaves them off entirely. He tells the Setup console
which ones he is adding; this step is where that becomes a field the rest of the run can plan
against.

**It comes off his own answers — there is nothing to install and no file to edit.** He typed
the divisions he is adding, and their sizes, into the **Divisions You Are Adding** section of
the Setup console at Step 1, so they are already in the block he couriered back. This step
turns that into a field: last season's draws stand in **unchanged** for every returning
division, and only the divisions he is adding are built, at the sizes he stated.

**Run it AFTER Step 1's console is generated, never before.** Step 0.5 checks his real files,
and Step 1's prefill reads his venues and dates off his real draws — and his added divisions
arrive in the block he pastes back at the end of Step 1. There is nothing to run before it.

```python
import projected_field
field = projected_field.build_projected_field(setup)   # `setup` is the block he couriered
projected_field.install(field)   # stays on for the rest of the run; a September run ends at 3.6
print(field.report["added_names"], field.report["invented"],
      field.report["roster_exhausted"])
```

From here on, every read of the draws returns the projected field. **Whenever a number
includes them, say it: the added divisions are estimates, not entries.**

**⚠ HIS SIZES ARE TEAMS AND BRACKET CAPACITY, NOT ENTRIES — say so when you read them back**
*(moved here at CF-1 from Step 3.5's retired elicitation; the protection is unchanged and it is
the half of it that was not already written down elsewhere).* The console asks for **Teams (a
doubles pair is one team)** and a **Draw size**, so reading his numbers as players sizes the
whole exercise at half. The tool plans at **the count he states, with his bracket as the
ceiling** — 14 teams in a 16 bracket are planned as 14, never as three quarters of the 16.

**⚠ If it refuses, it is telling you something true — do not work around it.** A run whose
couriered block carries no added-divisions answer is **refused**, on purpose: the block
tolerates an unknown key silently, so a misspelled or dropped answer would otherwise price his
tournament without the very divisions he is adding, and nothing would object. The fix is
always the same — go back to Step 1, answer that section, and re-courier. **If he is adding
nothing this year he ticks “I am adding no divisions next year”** (S-6: the free-text box and
its typed `none` are gone — the answer is the section's own toggle), which is a different answer
from leaving the section untouched.

**What the step tells you, and what to do with it.** `report["roster_exhausted"]` names any
division where last season's roster genuinely could not supply the players — on the 2026 field
that is the older Mixed divisions, where the tool holds too few women old enough. Those slots
are filled with obvious placeholder names. **Say it when you report that division**; it is a
fact about his field, not a fault, and R18 already keeps a fabricated bracket off every
deliverable.

### Step 2 — Derive the finals map (silent) → hand the TD the editor

#### Step 2 · FIRST, THE SEARCH — and it is a SEPTEMBER sub-step only  *(BEST-1)*

**⚠ LANE GATE, and it is the first thing to settle.** This sub-step belongs to the **September
publish run** and runs nowhere else. In a January run the calendar was published in September and
re-enters through reconciliation — there is nothing here to search, the search is never offered,
and you go straight to the elicitation below. **A January run that offers this has left its lane.**

Until now Step 2 handed him **one** calendar: worked out from the rounds each division needs, set
as late as each day allows, and defensible — but nothing *chose* it, because there was nothing to
choose between. This sub-step gives him a second one and lets him pick.

**⛔ ELICIT — your action for this sub-step IS the tool call. Call the elicitation tool with the options below, then end your turn. Do not run any code, do not write a prose question, do not pause silently — those all count as skipping the sub-step.** *"I can spend about eleven minutes looking for a quieter version of your week. You get both calendars with three numbers each, and you choose which one the editor opens on."*

- **`Look for a quieter week`** → run:
  ```python
  plan = wwtc_pipeline.finals_plan(setup, optimize=True)     # ingest -> draft -> the search
  ```
  **⏳ SAY THE WAIT BEFORE YOU START IT, NEVER AFTER** — the same rule the check below carries,
  for the same reason. **About eleven minutes**, and that is the number he plans around. It prints
  its progress while it runs, so the sub-step is never a silent stall.
  **⚠ RUN IT IN THE FOREGROUND. Never send a long step to the background on the run surface** —
  work handed off between tool calls there dies without saying so (the 2026-08-25 rehearsal).
  Then go to **the two calendars** below. ⚠ **Do not report a single number out of this call until
  you have read that section** — which calendar the numbers belong to is the whole point.
- **`Go straight to the map`** → run nothing here. The elicitation below is next, unchanged, and
  the run is exactly what it is today.

> ⚠ **THE SEARCH DOES NOT RUN ON A WEEK THAT CANNOT BE SCHEDULED.** If the week as supplied has
> more matches than its courts can hold, `optimized_map` comes back with **no calendars** and a
> `not_searched` line, and it comes back **fast** — say so for what it is and go to the refusal
> checklist below. There is no calendar to improve, and the six moves there are what he is owed.

#### The two calendars — put both in front of him, and the choice is HIS  *(BEST-1; Operator ruling 2026-08-29)*

⚠ **THE CHOICE IS ELICITED HERE, IN THIS CONVERSATION. There is no two-map console screen, and
none is to be built.** The chosen calendar re-enters through the finals-map loop this runbook
already uses, which is why this costs no console code at all. A session that finds itself
designing a screen for this has taken a road nobody asked for — stop and say so.

⚠ **ONE CALENDAR OR TWO IS DECIDED BY `plan["optimized_map"]["choice_required"]`, NEVER BY
PREFERENCE**, exactly as the three branches below are decided by `plan`.

**When `choice_required` is `false`** — the search found nothing better than the calendar the tool
already had. **Do not ask him to choose between two identical calendars**: say in one sentence
that the search found nothing better, and go straight to the elicitation below. There is nothing
here for him to decide.

**When `choice_required` is `true`** — print `plan["optimized_map"]["sentences"]` **VERBATIM**.
They carry both calendars with all three numbers each, in his own terms, and every figure in them
was measured on his field. **Do not summarise them, re-order them, or re-type a number out of
them** (ruling 12). Then elicit:

**⛔ ELICIT** *"Two calendars, and neither one is the tool's recommendation. Which should the editor open on?"*

- **`The calendar as derived`** → `pick = plan["optimized_map"]["calendars"][0]`
- **`The searched calendar`** → `pick = plan["optimized_map"]["calendars"][1]`
- **`Keep searching`** → **OFFER THIS THIRD OPTION ONLY WHEN
  `plan["optimized_map"]["search"]["still_improving"]` IS `true`**, and then go to **keep
  searching** below. When it is `false` the option is not offered at all — see that section's
  retirement rule.

⚠ **THE FIRST OPTION IS NAMED FOR WHAT THE CALENDAR ACTUALLY IS.** On the first sitting it is the
tool's own derivation and reads `The calendar as derived`. **After a sitting that kept searching
it is the calendar he already has, and it reads `The calendar you have now`** — the block itself
says which, in `plan["optimized_map"]["calendars"][0]["which"]` (`draft` or `seed`), and
`sentences` uses the same words. Read the label off that key; never type one from memory.

Then seed the map he picked into the loop that already exists — this is the ordinary re-edit
courier shape, with the paste replaced by his choice:

```python
draft = plan["finals_day"]                     # the tool's own derivation, whatever sittings ran
seed = {"schema": "td-finals-map/v1", "tournament": plan["tournament"], "confirmed": True,
        "finals_map": dict(pick["finals_day"]),
        "pins": {ev: dt for ev, dt in pick["finals_day"].items() if draft[ev] != dt}}
```

…and carry `seed` into **the silent build** below — it is what `finals_plan(setup, finals=seed,
engine_check=True)` grades and what the booking answer is priced against. His calendar is what the
board opens on, what the booking answer prices and what Step 4 builds.

⚠ **`draft` IS `plan["finals_day"]`, NOT THE FIRST CALENDAR IN THE BLOCK** — the two are the same
thing on a first sitting and are NOT the same thing after a resumed one, where the first calendar
is the seed. `pins` is the TD's moved subset against what the tool derived, so a resumed run that
read it off the seed would hand the editor a map claiming he had moved nothing.

⚠ **NEITHER CALENDAR IS THE TOOL'S RECOMMENDATION, AND YOU DO NOT MAKE ONE.** The search can buy
a much quieter week and cost more courts to book, and the tool neither takes that trade for him
nor refuses it — **it shows him both and he picks.** Where one calendar genuinely is better on all
three numbers, `sentences` says so plainly and both are still shown: the ruling is that he
chooses, not that the tool withholds what it knows. ⚠ **Which way the trade falls is a fact about
his field and is READ OFF THE NUMBERS IN FRONT OF YOU, never anticipated** — it has been measured
going both ways on the same seed, and a session that tells him what to expect before the search
has run is quoting a figure at a real director (ruling 12).

⚠ **IF THE SEARCH RAN OUT OF TIME WHILE IT WAS STILL IMPROVING, `sentences` SAYS SO — PRINT IT
AND MEAN IT.** Whether to spend more time is his call, and **keep searching** below is how he
spends it. ⚠ **Do not offer him a longer single search.** This surface caps one step at ten
minutes and backgrounding a long step is forbidden, so a longer allowance is a promise this run
cannot keep — that was measured live on 8/29 (OI-B), with the search using its whole ten minutes
and the offer to continue left unanswerable.

#### Keep searching — another sitting, and it says what it bought  *(RESUME-1; Operator ruling 2026-08-30)*

**Offered only when `plan["optimized_map"]["search"]["still_improving"]` is `true`.** The search
stopped on the clock with better weeks still in front of it; a further sitting picks up from the
calendar he was just shown and carries on from there.

**⏳ SAY THE LENGTH BEFORE YOU SPEND IT, NEVER AFTER** — the same rule the first sitting follows.
**About eight minutes** is what a resumed sitting is given, and that is the number he plans
around. Then run, in the foreground:

```python
last = plan["optimized_map"]["calendars"][1]["finals_day"]   # the winner just shown to him
plan = wwtc_pipeline.finals_plan(setup, optimize=True,
                                 resume_from=dict(last), allowance=480)
```

⚠ **THE SEED IS THE SEARCH'S WINNER — `calendars[1]` — NOT `pick`.** He chose to keep searching
instead of choosing a calendar, so there is no `pick` yet; the sitting continues from the best
week the tool has found so far. Whenever `still_improving` is `true` there are always two
calendars, so `calendars[1]` is always there to read.

⚠ **RUN IT IN THE FOREGROUND. Never send a long step to the background on the run surface** —
work handed off between tool calls there dies without saying so (the 2026-08-25 rehearsal).

⚠ **480 SECONDS, AND THE REASON IS THIS SURFACE'S CAP.** The first sitting's ruled 660 finished at
11.6 minutes on the 8/29 run — inside its band by drift, over the ten-minute cap. A resumed
sitting is given eight minutes so the drift has somewhere to go. **Read the figure from here; it
is never asserted from a brief, and never quoted to him as what the sitting will find.**

**Then come straight back to the two calendars above and work it exactly as written.** The block
has the same shape it always has: the first calendar is where the last sitting ended, the second
is where this one did, both with all three numbers, and `sentences` is printed VERBATIM. **The
difference between those two calendars is what these minutes bought** — that is the whole point of
pricing the first one in full, and it is the answer to the director's own standing question about
what more search time is worth on his field. ⚠ **Read it off the two calendars in front of you;
never estimate it, and never predict the next sitting's from the last one's** (ruling 12).

**A sitting can buy nothing, and then it says so.** `choice_required` comes back `false`, there is
one calendar, and it is the one he already had. Say that in one sentence and move on.

**⚠ THE OFFER RETIRES ITSELF, AND YOU DO NOT RE-OFFER IT.** The moment a sitting comes back with
`still_improving` `false`, say plainly: **"The search has run out of improving moves."** Then the
third option is gone from the stop above and the run carries on with the two options it always
had. A session that offers another sitting after that is selling him time the tool has already
said it cannot use.

⚠ **THERE IS STILL NO RUN-STATE FILE, AND NONE IS TO BE CREATED.** The seed is the calendar the
director was shown — it is in the block already in front of you, and it travels the ordinary
courier way like everything else here. A session writing search progress to disk has taken a road
nobody asked for; stop and say so.

⚠ **NOTHING HERE GRADES A DAY HE LATER CHOOSES.** Showing two calendars with their numbers is the
tool's own two proposals, before he has touched anything. The moment he drags a division the
existing discipline takes over unchanged: the chip goes neutral, nothing is removed, and the tool
never tells him his day is worse.

#### Step 2 · the silent build — SEPTEMBER PLANNING RUNS ONLY  *(CF-1; Operator ruling 2026-08-30)*

**⚠ LANE GATE, AND IT DECIDES WHETHER THIS STEP ASKS AT ALL.** On a **September planning run**
the check is not offered — it is run, and the booking answer is worked out with it, as one
silence. Take the two calls below. **A January run does not come here at all**: it takes *the
check ask* further down, unchanged, and nothing in this build touches its lane.

**Why it stops asking.** He has just picked his calendar out of two, each priced. Asking whether
to check it is a question with one useful answer, and it costs him a turn before the tool has
earned anything to show. So the tool earns both answers first — which days hold, and what to book
— and asks once, with both of them on the table (**Step 3 · the priced board**).

**⏳ ONE HONEST SENTENCE NAMING THE WAIT, SAID BEFORE THE FIRST CALL AND NEVER AFTER.** A silence
nobody named is just a stall. Say this, then start:

> I'm building your tournament to grade every finals day and work out what to book. About ten
> minutes, and you get the days and the booking answer together.

⚠ **TEN MINUTES IS THE CAUTIOUS PROMISE AND IT IS WHAT HE PLANS AROUND** — the same figure the
check has always carried. **Never quote a faster one**: a number said out loud becomes a promise
the next field breaks (ruling 12).
⚠ **RUN BOTH IN THE FOREGROUND. Never send a long step to the background on the run surface** —
work handed off between tool calls there dies without saying so (the 2026-08-25 rehearsal).
⚠ **SAY NOTHING BETWEEN THE TWO CALLS.** They are one wait to him. Both print their own progress
while they run, so the step is never a silent stall.

```python
plan = wwtc_pipeline.finals_plan(setup, finals=seed, engine_check=True)   # the days, graded
if "week_refusal" in plan:                       # the silence ENDS here — see the gate below
    raise SystemExit                             # (stop; do not price a week that has no schedule)
html = finals_guidance.render_guided_finals_console(                      # the board, verdict on it
    plan, doc_label="the two calendars")                                  # names THIS publish
# write html to a file and IMMEDIATELY publish it as a private artifact (7.0) — HOLD the link
# for Step 3 and do not hand it over yet; the board and the booking answer go over together.
fmap = seed                                                               # BEST-1: never None here
budget = wwtc_pipeline.court_budget(
    slate=setup["slate"],
    constraints_doc=setup["constraints"],                  # HIS RULES — the other half of the pair
    finals_map=finals_plan.finals_map_from_doc(fmap) if fmap else None,   # the DAYS, not the doc
    ceilings=None)                                         # None = read them off the slate
```

⚠ **THE `week_refusal` LINE IS A GATE, NOT A CRASH.** It is written into the block because the
two calls are one silence and a session running straight through would price a week that has no
schedule. In the run you do not raise anything — you **stop, and work the six moves below**.

⚠ **`seed` IS THE CALENDAR HE PICKED, AND ON A SEARCHED SEPTEMBER RUN IT IS NEVER `None`**
(BEST-1). On the **`Go straight to the map`** branch he never searched, so there is no `seed`:
pass `finals=None`, carry `fmap = None`, and the booking answer says the finals-day savings were
not priced — which is true and is reported rather than passed over.
⚠ **THE THREE THINGS THIS STEP USED TO ELICIT ARE ALL IN YOUR HAND ALREADY — CHECK, DO NOT
ASSUME.** The court answer used to open by asking for each club's own court count, the divisions
he is adding, and his finals calendar. On this lane Step 1 carries all three: **Max Courts** is
on the Setup console's Club Ledger and rides the block, so `ceilings=None` reads it; the divisions
he is adding went into the field at **Step 1.5**; and the calendar is the one he just picked.
**Look at the block before you skip the question** — if the setup in your hand carries no court
ceilings at all, say what blank costs him in one sentence (without it the answer can only ever be
*"book more courts here"*; with it the tool can also say *"you're out of room here"*) and carry
on. **Never guess a ceiling for him**: a guessed one can turn a real booking into a false "out of
room".
⚠ **THE PAIR IS BOTH HALVES — his courts AND his rules.** Leave `constraints_doc=` off and the
call STOPS, naming what is missing. If you see that refusal you have handed the step half his
setup: pass `setup["constraints"]` and run it again. Do **not** work around it with
`wwtc_pipeline.default_constraints()` — that is for a bench call that genuinely means the tool's
defaults, and here it re-creates the exact fault the refusal exists to stop.
⚠ **`finals_plan.finals_map_from_doc` IS THE ONE SANCTIONED UNWRAPPER. Never take the key
directly as `fmap["finals_map"]`** — it is also the loud courier-typo gate, and it is the only
thing standing between a mistyped paste and a court answer computed against the wrong calendar.
⚠ **THE SAME ARGUMENT NAME TAKES TWO SHAPES IN THIS RUN.** `finals_plan(setup, finals=…)` takes
the whole **document**; `court_budget(finals_map=…)` and `build_combined(finals_map=…)` take the
**bare** `{division: date}` map from inside it. Hand the budget the document and it stops dead —
`TypeError: unhashable type: 'dict'`, in 0.0 s, before a single tournament is built.
⚠ **Do NOT drive the court answer from the conversation.** Do not loop over court counts yourself,
do not print a line per build, and do not ask it for schedules. One call in, one compact answer
out.

**⛔ IF THE WEEK REFUSES, THE SILENCE ENDS THERE.** `plan` comes back carrying
`week_refusal` and no verdict, so there is nothing to price and no board to hand over: go to the
**six moves** below and work them exactly as written. **Do not run the court answer on a refused
week** — it would price a week that has no schedule. The refusal branch is untouched by this
build.

**Then go to Step 3 · the priced board.** Nothing is said to him between the two calls and that
step; the next thing he hears is the board and the booking answer together.

#### Step 2 · the check ask — JANUARY RUNS ONLY  *(the lane as it has always stood)*

**⚠ THIS ELICITATION IS THE JANUARY ENTRANCE. A September run does not reach it** — it took the
silent build above. January's branch is unchanged in every respect.

**⛔ ELICIT — your action for this step IS the tool call. Call the elicitation tool with the options below, then end your turn. Do not run any code, do not write a prose question, do not pause silently — those all count as skipping the step.** *"Check every division's finals day against a full build? About ten minutes, and it is what tells you which days will actually hold."*

*(Assistant: if he asks whether it is worth running, the recommendation is made on **how big his
field is and how many days he has** — nothing else. Never recommend for or against it on the
strength of a rule this run has not measured on this field; that is exactly how a misreading
became a recommendation once already.)*

- **`Derive it`** → run:
  ```python
  plan = wwtc_pipeline.finals_plan(setup, engine_check=True)   # ingest -> draft -> the check
  html = finals_guidance.render_guided_finals_console(          # the editor, with the verdict on it
      plan, doc_label="the two calendars")                      # names THIS publish in his gallery
  # write html to a file and IMMEDIATELY publish it as a private artifact (7.0) — hand over
  # the link (fallback: outputs/ + open-in-browser instructions)
  ```
  ⚠ **`doc_label` IS WHAT KEEPS HIS GALLERY LEGIBLE, AND EACH PUBLISH USES THE ONE WRITTEN AT ITS
  OWN SITE** (FIX-1, off the 8/29 run's finding 6). A September run publishes this console three
  times or more, and until this label every one of them arrived under the same name — the calendar
  he approved and the proposals he discarded, side by side in his list, indistinguishable. The
  three labels are **`"the two calendars"`** here and at the silent build, **`"for your edits"`**
  at Step 3's re-seed, and **`"re-check"`** at every re-grade — September's *after the edit* and
  January's Step 3a alike. Use them as written; you may append his own words
  after them, and **never a clock, a date or a counter** — the same rule the announced calendar's
  label follows, and for the same reason: two runs of the same inputs must produce the same file.
  **⏳ SAY THE WAIT BEFORE YOU START IT, NEVER AFTER.** `engine_check=True` builds the whole
  tournament once per candidate day — around 300 builds on the WWTC field, roughly ten minutes.
  It prints its progress while it runs, so the step is never a silent stall; the TD should be
  told the wait is expected *before* the call, not asked to sit through it and reassured after.
  **⚠ RUN IT IN THE FOREGROUND. Never send a long step to the background on the run surface** —
  work handed off between tool calls there dies without saying so: in the 2026-08-25 rehearsal a
  backgrounded check stopped mid-log with no error and no result, and the same check re-run in
  the foreground finished normally. **Ten minutes stays what you tell him** — it is the cautious
  promise and it is what he plans around. *(Measured once, 2026-08-25, on that foreground re-run:
  156.2 s. Recorded here as a measurement of one run on one field, never as a figure to quote to
  him — a faster number said out loud becomes a promise the next field breaks.)*
  Report: divisions, the finals span, cap-audit warnings if any, **and the check's two numbers as
  the chip states them — `<held>` of `<divisions>` hold as mapped · `<flagged>` need a look**
  (read them off `plan["engine_check"]["held"]` / `["flagged"]`, and the denominator off the
  field's own division count; **never quote a figure from this document — they move with the
  field**). ⚠ **THE DENOMINATOR IS A SLOT, NOT THE NUMBER 50.** This line read *"N of 50"* until
  S-1: 50 is the committed 2026 field, and a September run with Step 1.5 on carries **56** — so
  the literal was wrong for the very lane it is written in, and a run reading it aloud tells the
  director his tournament is four divisions smaller than it is. Note the master-vs-draws count
  distinction: round-robin divisions
  (RR-badged rows) schedule as `— Group N` draws, so the draw-sheet count exceeds the division
  count; **their drags bind all of the division's groups (F7-4)**, and **a round-robin division's
  finals day means the group FINISHES BY that day** — the check grades it that way and the board
  says so.
- **`Skip the check — just the map`** → same two lines with `engine_check=False` (the default)
  and `finals_plan.render_finals_console(plan)`. The TD gets today's editor, unchanged and
  immediate; nothing tells him which days hold.
- **`Hold here — not yet`** → stop and wait.

> **⛔ IF THE WEEK CANNOT BE SCHEDULED AT ALL (NOMAP-1) — THE SIX MOVES, EVERY ONE A MUST.** The
> check runs a full build first, and that build can come back saying this week has more matches
> than its courts can hold. When it does, `plan` carries **`week_refusal`** and **no
> `engine_check`** — the check never ran, so there is no verdict, and there are no chip numbers to
> report.
>
> ⚠ **THESE SIX ARE A CHECKLIST, NOT ADVICE, AND SKIPPING ONE IS SKIPPING THE STEP.** Measured on
> the 2026-08-28 run: five of these moves already existed here as prose and **two of them were
> skipped** — the draft map was never handed over and the fixes were never put as his decision.
> Prose did not hold the session to the script, so this is numbered, and moves 4 and 5 — the two
> that were dropped — are held as text by `tests/answer1_four_figures.py` part E.
>
> 1. **Say it plainly, first sentence:** the week as supplied cannot be scheduled, so the finals
>    days could not be checked against a build.
> 2. **Print `plan["week_refusal"]["report"]` VERBATIM.** Do not summarise it, re-order it, or
>    translate it. It names the reasons and then every fix that was tried — each one re-run for
>    real against these entries, before you saw it — and it says which ones clear the week.
>    **It ends with a further section, *"What it would take"*, naming how many courts, at which
>    club, on which days, in which part of the day and for which divisions** — again each figure
>    re-run for real before you saw it. Print it with the rest, verbatim, and treat it exactly as
>    the list above: it is his decision, not a recommendation to make for him. Where it says no
>    number of courts fixed the week, **that is the answer** and it is reported as plainly as any
>    other — it also says what it did not try, and those bounds are part of the answer too.
> 3. **⛔ READ THE FOUR FIGURES BACK, in his own terms, off the payload.** Printing the report is
>    not the same as telling him what to book, and on 2026-08-28 the printed report carried **none
>    of the four figures** in its instruction section. Read `plan["week_refusal"]["shortfall"]`
>    and say, once per reason it carries:
>
>    > To make this week fit you would need **`<courts>` more courts** at **`<club>`**,
>    > **`<hours>`**, on **`<days>`**, for **`<divisions>`**.
>
>    And where the club is already at everything it owns, the same four figures with what he
>    cannot do said out loud:
>
>    > **`<club>`** is at every court it owns **`<hours>`**. It would take **`<courts>` more
>    > courts than it owns**, on **`<days>`**, for **`<divisions>`** — and that is not a booking
>    > you can make. The two ways forward are to move a final off **`<days>`** and check again, or
>    > to change what **`<club>`** gives you.
>
>    ⚠ **EVERY `<slot>` IS READ AT RUN TIME AND NONE OF THEM IS EVER TYPED.** `<courts>` ·
>    `<club>` · `<hours>` · `<days>` · `<divisions>` come off `shortfall["reasons"]` — the answer
>    row where the club has room (`answer`), the beyond-what-it-owns row where it does not
>    (`beyond_owned`), and the club's own figures either way. A session that types a number here
>    reads it aloud to a real director (ruling 12). Where a row carries **no** figure, say that —
>    with what was tried and what was not — and never substitute one.
> 4. **Still hand over the editor.** The draft map does not come from the build, so it survived:
>    render it the "Skip the check" way (`finals_plan.render_finals_console(plan)`, the same line
>    that step's option already uses — with no `engine_check` on the doc that is what the guided
>    wrapper returns anyway) and give the TD the link. **Name it before the link:** *"this is the
>    map as drafted — it has not been checked, because the week as supplied cannot be scheduled."*
> 5. **Stop, and put the fixes to the TD as HIS decision.** Read out what the report lists and ask
>    which he wants. **Never pick one for him**, never rank them beyond the order they print in,
>    and never quote a figure from this document — the report's own numbers are the only ones.
>    **One ask, and then stop and wait.** A row that reads *not tried* means something cheaper
>    already fixes the week; it does not mean it failed.
> 6. **When he changes something, the answer is a fresh check.** He adjusts the venues, days or
>    match length in the Setup console, couriers a new `td-setup/v1`, and you **loop back to
>    Step 2** and run it again — the same seeded re-check the step already offers after an edit.
>    **Name the wait again before starting it.** Nothing here is re-run in the browser: the
>    console never talks to the engine.
>
> ⚠ **EVERY RE-TEST OR WHAT-IF THAT ENDS IN A REFUSAL PRINTS THE FRESH REPORT VERBATIM.** You may
> summarise on top of the report; never instead of it. This binds the loop above, the re-check
> after any edit, and every `try_change` at Step 3.5 — measured 2026-08-28, when the second
> refusal of a run was summarised freelance and the director never saw what the tool actually
> said.
>
> **Do not go on to Step 3 or Step 4 on a refused week.** The build there will refuse for the same
> reason, and every later step would be running against a week that has no schedule.

> **What the TD sees when the check runs (FMAP-2).** The board still opens on the desk's days —
> **confirming without touching anything still changes nothing**, exactly as before. On top of it:
> a chip counting the divisions that hold, an amber ring on a day that will not hold, a dashed
> **F** on the day the engine actually finishes that division, and a card on the right naming the
> cause in plain English with a button that moves the division there. **Adopting is the same
> action as dragging** — the emitted block is byte-identical either way. Keeping the day he
> mapped is legal and always available: the tool reports, it does not refuse.

#### Presenting the first finals board — the words, three branches  *(S-1 §1-E3)*

**Which branch you are in is decided by `plan`, not by preference:** an `engine_check` present
is branch 1, the check declined at the elicitation is branch 2, and `week_refusal` present with
no `engine_check` is branch 3.

⚠ **WHERE THESE WORDS ARE SAID DEPENDS ON THE LANE (CF-1).** A **January run** says them here, at
the board, exactly as it always has. A **September planning run** does not hand the board over
until the booking answer is beside it, so it says **branch 1's first paragraph** at **Step 3 · the
priced board** — as written, it is still approved verbatim — and holds branch 1's **second**
paragraph for the *edit a few days* branch, which is the only September branch where a drag and a
paste happen. Branch 2 is a January branch: September never skips the check. Branch 3 is the
refusal and is unchanged in both lanes.

**BRANCH 1 — the check ran and returned a verdict. APPROVED VERBATIM (Operator, 2026-08-23;
swept to the four caps at VOICE-1, 2026-08-30 — the say-it-as-written discipline is unchanged).
The figures are SLOTS; everything else is said as written:**

> Here's your finals map, checked against a full build of your tournament: **`<held>` of
> `<divisions>` divisions hold on the day they're on, and `<flagged>` need a look** — each of
> those has a card on the right saying why. The field behind it is last season's entries standing
> in for next year's, plus the divisions you are adding at your estimated sizes — estimates, not
> entries.
>
> Drag any final to the day you want it, then press **Save my finals days**, **Copy**, and paste
> the block back here. Say so and I'll re-check the days you choose — about ten minutes, as often
> as you like.

⚠ **`<held>`, `<divisions>` and `<flagged>` are READ AT RUN TIME** off
`plan["engine_check"]["held"]` and `["flagged"]`, with the denominator from the field's own
division count. **A session that hardcodes them reads them aloud to a real director** (ruling 12).
The brief's illustrative "52 of 56 · 4" is an EXAMPLE, not a figure to type.
⚠ **The second paragraph is only true when Step 1.5 is on.** In a January run the field is real;
drop that paragraph rather than telling him real entries are estimates.

**BRANCH 2 — the check was skipped.** There is no verdict, and the turn must not imply there is
one. Say so plainly and offer the check:

> Here's your finals map. **It has not been checked against a build**, so nothing here tells you
> which of these days will hold.
>
> Drag any final to the day you want it, then press **Save my finals days**, **Copy**, and paste
> the block back here. Say so and I'll check the days — yours or these — about ten minutes.

**BRANCH 3 — the week was refused (NOMAP-1).** The check ran and returned **no verdict at all**:
`plan` carries `week_refusal` and no `engine_check`. He gets the refusal report printed verbatim,
**the four figures read back to him**, and an **unchecked draft map**, which survives because it
is desk-derived rather than built. ⚠ **The six-move checklist in the blockquote above is what
scripts this, and it is a checklist** — the words below are move 1 and nothing more; moves 2 to 6
still all have to happen:

> The week as supplied cannot be scheduled, so I could not check the finals days against a build.
> The report below says why, and every fix in it was re-run for real before you saw it.
>
> The map itself survived, and **it has not been checked**. Once you have changed something, I can
> run the check on it.

⚠ **This branch comes back COMPARATIVELY FAST, and you must say so for what it is.** The
~300-build grid never starts; what is paid for instead is the refusal's own remedy probes (OI-56:
up to 35 builds, roughly a minute). **Never call it "the ten minutes".** A director told ten
minutes and answered in one reasonably concludes something went wrong — and here nothing did.

### Step 3 — The board, and the finals-map editor → `td-finals-map/v1`  *(courier stop 2)*

**⚠ TWO ENTRANCES, AND THE RUN'S KIND DECIDES WHICH ONE (CF-1, Operator ruling 2026-08-30).**
- **A September planning run** enters at **the priced board** below — one look, one stop. It
  reaches the paste only on that board's *edit a few days* branch.
- **A January run** enters at **the paste** below, unchanged in every respect.

#### Step 3 · the priced board — SEPTEMBER PLANNING RUNS ONLY  *(CF-1, Operator ruling 2026-08-30)*

**What he gets here is one look and one question.** His days are graded and his booking answer is
worked out, and they go over together. Until this build they arrived two steps apart with a
question in between, so he was asked to approve days before he had any idea what the week would
cost him to book.

**⚠ THE ORDER IS FIXED — the days, then the booking answer, then the stop — and nothing is
elicited before all three.**

**1 · Hand over the board and say the verdict.** Give him the link you held back at the silent
build, and say **branch 1's FIRST paragraph, as written** (it is approved verbatim; `<held>`,
`<divisions>` and `<flagged>` are slots read off `plan["engine_check"]` at run time). ⚠ **Do not
say branch 1's second paragraph here.** It tells him to drag and paste, and it belongs to the edit
branch below: said here it asks him to change days before he has seen what they cost.

**2 · Read the booking answer back — the whole discipline at Step 3.5, unchanged.** The two
numbers and the gap between them, the three hours-and-lights lines, `does_not_fit` or `surplus`,
`axes`, `daily_cap`, `watchlist`, `out_of_room`, `not_tried` and `partial`, and the three things
to say out loud every time. **That section is where those rules live and this one does not repeat
them** — read it and work it. The one thing that has moved is the finals-day savings, which are
now **ask-only**: see that bullet.

**3 · ⛔ THE ONE STOP, AND EVERY EXIT IS PRICED BEFORE HE PICKS IT.** This is the ask-once half of
the law: he has both answers in front of him, so he is asked once, about the whole of it.

**Say the three prices in one sentence first, every figure read off THIS run.** Accepting costs
nothing at all. Editing a few days costs a trip to the board and the days graded again — quote
**the silent build's own elapsed time**, the one you just spent. Going further back costs a
console trip and then the same grading, plus the quieter-week search's own elapsed time if he
wants it looked for again. ⚠ **Never quote a duration from this document** (ruling 12): timings
move with his field and with the day, and a printed expectation teaches him to read ordinary
variance as a fault.

**⛔ ELICIT — your action for this step IS the tool call. Call the elicitation tool with the options below, then end your turn. Do not run any code, do not write a prose question, do not pause silently — those all count as skipping the step.** *"Accept these days, edit a few, or go further back?"*

- **`Accept these days`** → the days stand as graded and **nothing is couriered** — a round that
  changes nothing costs nothing. Mint the acceptance record below, then go to **Step 3.5**, where
  the what-if lane is waiting if he wants to test anything about his booking, and on to **Step
  3.6** when he does not.
- **`Edit a few days`** → say branch 1's **second** paragraph now, and go to **the paste** below.
  That is courier stop 2, and this is the only September branch that reaches it.
- **`Go further back`** → the standing loop-back, priced. Ask which step he wants — **Step 1** for
  his courts, days or rules, **Step 2** for another look at the week — and say what it costs in
  the same breath, off this run's own figures. ⚠ **S-1 §1-E5 binds on the Step 1 road: a new setup
  invalidates `plan`, so Steps 2 and 3 re-run before Step 3.5 or Step 3.6 are used again.** Say
  that in one clause as he chooses it, not afterwards.

**⛔ THE ACCEPTANCE RECORD — minted the moment he accepts, and it is what January reads.** *(CF-1;
the vehicle is MARK-1's guarded pass-through, and no printed page changes.)* Accepting a board is
a decision, and until this build it left no trace at all: the file he shelved could not say
whether he had looked at those days and said yes, or whether they were simply the last thing the
tool produced. Write it onto the document he is holding:

```python
import finals_publish, finals_plan
fmap = dict(fmap, _acceptance={
    "accepted_on": "2026-09-15",              # HIS date, supplied by the run — never a clock
    "branch": "as shown",                     # or "after an edit", on the edit branch below
    "map_digest": finals_publish.map_digest(finals_plan.finals_map_from_doc(fmap)),
})
```

⚠ **`accepted_on` IS SUPPLIED, NEVER READ OFF A MACHINE CLOCK** — the same rule Step 3.6's
announce date follows, and for the same reason: a record whose date depends on whose computer
pressed the button is not a record. Say the date out loud as you write it.
⚠ **`branch` SAYS HOW HE GOT HERE AND IT IS NOT COSMETIC.** *"as shown"* means he accepted the
board the tool built; *"after an edit"* means he moved days first and accepted what came back.
Four months later those are different facts about the same file.
⚠ **THE FINGERPRINT IS THE MAP HE ACCEPTED, taken through the one sanctioned unwrapper** —
`finals_map_from_doc`, never `fmap["finals_map"]`. It is deliberately a second fingerprint beside
the announce stamp's: they agree when the calendar announced is the calendar accepted, and they
**disagree** if the days were touched in between. That disagreement is the whole point.
⚠ **THE PRINTED PAGE DOES NOT CHANGE, AND IT MUST NOT.** This is a record for January's read-back,
not a mark for players. The key rides the announced JSON through the same pass-through
`_session_edit` rides — `stamp_finals_map` and `announce_finals_map` both carry unknown top-level
keys, and `finals_map_from_doc` drops it at the gate, so nothing downstream can see it or change
because of it. A session that puts an acceptance mark on the printed calendar has taken a road
nobody asked for; stop and say so.
⚠ **AND IT IS NEVER PROOF OF WHO ACCEPTED.** Whoever can edit the map can recompute the
fingerprint, exactly as with the announce stamp. It catches a file that drifted; it says nothing
about authorship. Say both halves if he asks.

#### Step 3 · the paste  *(courier stop 2 — January's entrance, and September's edit branch)*
**⛔ ELICIT — your action for this step IS the tool call. Call the elicitation tool with the options below, then end your turn. Do not run any code, do not write a prose question, do not pause silently — those all count as skipping the step.** *"The finals map is at the link above — drag any finals you want moved. When you're done, press **Save my finals days**, then **Copy**, and paste the finals map block back here."*
- **`I edited the finals map`** (or a zero-drag emit) → the TD pastes `td-finals-map/v1`:
  ```python
  fmap = json.loads(pasted_finals)                 # validated loudly at Step 4
  ```
- **`Use the engine draft as-is`** → `fmap = None` (identical outcome to a zero-drag emit —
  the computed draft binds). ⚠ **On a September run that used the search (BEST-1), this branch is
  `fmap = seed` — the calendar he picked at Step 2 — and never `None`.** The map on the board is
  already a document, so handing `None` on down would throw away the calendar he chose and leave
  Step 3.5 unable to price the finals-day savings.

> **If the TD moved anything, the check on that board is now HISTORY (FMAP-2).** The court-level
> verdict is ~300 full builds; it cannot re-run in the browser, and the console never talks to
> the engine (B-1). So the moment a division moves, the chip goes neutral and reads *"checked
> against the days as generated · N divisions moved since"*, a note at the top of the cards says
> the same, and a moved division's card stays put marked *"You moved this to Wed 1/28. That day
> has not been checked."* — it is never removed, because a warning that vanishes reads as a
> problem solved. **Nothing on that screen claims the new days are better or worse. Do not tell
> the TD they are.**
>
> **To get a real answer for the days he chose, loop back to Step 2 with his emit seeded:**
> `plan = wwtc_pipeline.finals_plan(setup, finals=fmap, engine_check=True)` → regenerate the
> editor with `finals_guidance.render_guided_finals_console(plan, doc_label="for your edits")`
> — the board that carries the days he moved, named so it is not one more copy of Step 2's in his
> gallery. His moves arrive as locked
> days and the check runs again on them. **Name the wait again before starting it** — it is the
> same ten minutes or so. It is the only honest way to answer what his change did, and it is a
> choice, not a requirement: he can save and go to Step 4 with the check unrepeated, and the
> build will still report everything it finds at Step 4 and 5.5.

#### Step 3 · after the edit — SEPTEMBER PLANNING RUNS ONLY  *(CF-1, Operator ruling 2026-08-30)*

**⚠ SEPTEMBER DOES NOT ASK HERE ANY MORE, AND THAT IS THE ASK-ONCE HALF OF THE LAW.** He came to
the board to change days; asking him afterwards whether he wants those days graded is a second
question about the same decision. So on the September lane the re-grade is not offered — it
happens — and Step 3a below is **January's step**. Work the two branches in this order:

**FIRST, ASK THE PASTE WHETHER ANYTHING ACTUALLY MOVED** — the same one-line comparison Step 3a
uses below, and the same reason: both halves are already in your hand.

```python
moved = sorted(ev for ev, dt in ((fmap or {}).get("finals_map") or {}).items()
               if plan["finals_day"].get(ev) != dt)          # the days he actually changed
```

**If `moved` is empty — HE MOVED NOTHING, and that is an acceptance.** Nothing is re-graded,
because the calendar in his hand is the one the check already graded. Say it plainly — *"you kept
the days as they were, so there is nothing new to check"* — mint the acceptance record with
`branch` reading **`"as shown"`** (the map he accepted IS the board the tool built), and go to
**Step 3.5**. ⚠ **DO NOT SAY THE MOVED-AFTER-THE-CHECK CLAUSE HERE. IT IS FALSE ON THIS BRANCH**
(FIX-1, off the 8/29 run's finding 4): no day was moved, so the calendar he announces will record
those days as **checked**. A session that reads the moved-days wording anyway tells a real
director that his announcement will carry a mark it will not carry, about days he never touched.
What is true here is: **his days stand exactly as they were graded, and the announced calendar
will say they were checked.**

**If `moved` is not empty — HE MOVED DAYS, so grade them. No ask.**

**⏳ SAY THE WAIT BEFORE YOU START IT, NEVER AFTER** — the same honest sentence the silent build
uses, and the same ten-minute promise. Then run, in the foreground:

```python
plan = wwtc_pipeline.finals_plan(setup, finals=fmap, engine_check=True)
html = finals_guidance.render_guided_finals_console(plan, doc_label="re-check")
budget = wwtc_pipeline.court_budget(
    slate=setup["slate"], constraints_doc=setup["constraints"],
    finals_map=finals_plan.finals_map_from_doc(fmap), ceilings=None)
```

**Each re-check publishes under the `"re-check"` label**, so his gallery does not fill with
identically-named boards (FIX-1; you may append his own words, never a clock or a counter).
**Then go back to the priced board** and work it exactly as written — his moved days graded, his
booking answer re-priced beside them, one stop. On the accept branch there, `branch` reads
**`"after an edit"`**.

⚠ **THE RE-GRADE IS THE WHOLE PASS, AND THAT IS A MEASURED DECISION, NOT AN OVERSIGHT (CF-1).**
Grading only the divisions he moved and carrying every other division's days over from the
previous check was specified, driven on both benches, and **it does not agree with a full pass.**
Measured 2026-08-30, four graded edits — two on the 2026 calibration bench, two on the 2027
September field, two or three divisions moved each time: **202 of 224 carried days agreed and 22
did not.** A fifth edit refused the week outright and graded nothing. **The disagreements are in
the dangerous direction:**
- days the carried grade called *matches shift to make room* that a rebuild calls **blocked** —
  one of them at a cost of 13 across two other divisions;
- and two days the carried grade offered him at all that a rebuild says **cannot be played** —
  the week refuses with that division there.

**The cause is not a bug to fix.** A day is graded as a difference against the board's own build,
and moving one division re-flows the whole week, so every other division's days are being measured
against a board that has changed underneath them. **Do not re-introduce a partial re-grade without
driving that measurement again**, on both benches, and reading the disagreements rather than the
percentage.

⚠ **`fmap` is `None` only on a path this lane cannot reach** — the September board always carries
a real calendar (BEST-1). The guard in the comparison above is written so a session that reaches
the line anyway gets an empty `moved` and the acceptance branch, never a crash mid-step.

⚠ **This comparison is for the wording and the branch, and for nothing else.** It is not a court
answer and it is not a validation — `finals_plan.finals_map_from_doc` is still the one sanctioned
unwrapper and it still runs where it always has. A paste that is wrong in some other way is still
caught there, loudly.

#### Step 3a — Offer the recheck  *(JANUARY RUNS ONLY — after every finals-map paste)*

**⚠ THIS IS JANUARY'S STEP AND IT IS UNCHANGED.** A September run does not reach it: it took *after
the edit* above, which grades without asking. Everything below stands exactly as it has stood.

*(S-1 §1-E2. This used to be a line of advice inside the blockquote above — "offer this loop
whenever he asks what his change did" — which put the loop behind the director knowing to ask
for it. The board teaches it; the runbook did not offer it. Now it is a step, and it runs every
time a `td-finals-map/v1` comes back, including a zero-drag emit.)*

*(FIX-1, 2026-08-29 — the step still runs on every paste; what it SAYS now depends on whether the
paste moved anything. S-1's reason stands whole for every paste that moves days. On a paste that
moves none, the offer was asking him to re-grade the days it had just graded, and the decline
sentence beside it was false in both halves.)*

**⛔ FIRST, ASK THE PASTE WHETHER ANYTHING ACTUALLY MOVED — the two branches below are decided by
that answer and never by preference** (FIX-1, off the 8/29 run's finding 4). Both halves are
already in your hand: the plan the board opened on, and the block he pasted back.

```python
moved = sorted(ev for ev, dt in ((fmap or {}).get("finals_map") or {}).items()
               if plan["finals_day"].get(ev) != dt)          # the days he actually changed
```

⚠ **`fmap` is `None` on Step 3's "use the engine draft as-is" path, and that path skips this step
outright** — see the rule at the end of this step. The guard above is written so a session that
reaches the line anyway gets an empty `moved` and the skip branch, never a crash mid-step.

⚠ **This comparison is for the wording below and for nothing else.** It is not a court answer and
it is not a validation — `finals_plan.finals_map_from_doc` is still the one sanctioned unwrapper
and it still runs where it always has, at Step 3.5 and Step 4. Nothing here is loud, and a paste
that is wrong in some other way is still caught there.

---

**If `moved` is empty — HE MOVED NOTHING. Skip the offer, and say why in one sentence.** A
zero-drag emit is the same calendar the check already graded, so re-running it would build his
whole tournament for ten minutes to grade the days it just graded. Say it plainly — *"you kept the
days as they were, so there is nothing new to check"* — and go straight to **Step 3.5**. This is
the same reason the `fmap = None` path skips, and it is the same skip.

⚠ **AND DO NOT SAY THE DECLINE SENTENCE HERE. IT IS FALSE ON THIS BRANCH** — that is the whole
defect this branch fixes. On a zero-move paste no day was moved, so the calendar he announces will
record those days as **checked**, not as moved after the check. A session that reads the
moved-days wording anyway tells a real director that his announcement will carry a mark it will
not carry, about days he never touched. What is true here is: **his days stand exactly as they
were graded, and the announced calendar will say they were checked.**

---

**If `moved` is not empty — HE MOVED DAYS. Offer the re-check, and the wording below is unchanged.**

**⛔ ELICIT — your action for this step IS the tool call. Call the elicitation tool with the options below, then end your turn. Do not run any code, do not write a prose question, do not pause silently — those all count as skipping the step.** *"Check the days you chose? About ten minutes, and it builds your whole tournament to grade them."*
- **`Check these days`** → loop back to **Step 2** with his emit seeded:
  ```python
  plan = wwtc_pipeline.finals_plan(setup, finals=fmap, engine_check=True)
  html = finals_guidance.render_guided_finals_console(plan, doc_label="re-check")
  ```
  **Name the wait before you start it, never after.** Present the result with the Step 2
  presenting turn (branch 1), then come back here — the offer repeats, as many times as he wants.
  **Each re-check publishes under the `"re-check"` label**, so his gallery does not fill with
  identically-named boards (FIX-1; you may append his own words, never a clock or a counter).
- **`Carry on to the court budget`** → go to Step 3.5 with the check unrepeated. **Say what that
  means in one clause**: the days he moved have not been graded, nothing later in a September
  run will grade them, **and the calendar he announces will say those days were moved after the
  check.** He is entitled to decline — the run records the decline, it never blocks him — but he
  hears the consequence before he chooses it, not four months later.

⚠ **On the `fmap = None` path there is nothing to re-check** — he kept the draft the check
already graded, so skip this step rather than offering to re-run the same check on the same days.

### Step 3.5 — The court budget  *(SEPTEMBER PLANNING RUNS ONLY — skip it in a January run)*
*(BUDGET-1, Operator rulings R1–R12, 2026-08-22. No courier stop: this runs engine-side in your
own session and nothing crosses a console boundary.)*

**When this step applies.** Only when the run is a **September planning run** — the TD is deciding
what to BOOK for a tournament months away. A January run has the courts already; skip straight to
Step 4. If you are not certain which kind of run you are in, ask before running anything.

**What it answers.** Not "can this week be played?" — Steps 4 and 5.5 answer that. This answers
**"what do I need to book?"**, which the tool could not answer at all before this build.

**⚠ THE CALL HAS ALREADY RUN, AND THIS STEP NO LONGER ELICITS ANYTHING (CF-1, Operator ruling
2026-08-30).** `budget` was computed in the **silent build** at Step 2, beside the check, and read
back at **the priced board** at Step 3. Two things follow and both are the point of the change:

- **This step's three questions are gone.** It used to open by asking for each club's own court
  count, the divisions he is adding, and his finals calendar — all three of which Step 1 and Step
  1.5 were already carrying. The rules that governed them are kept where they are still needed:
  the **Max Courts** guidance is at the silent build, the added-divisions rule is at **Step 1.5**,
  and the calendar is the one he picked. **Check the block rather than assuming it** — that rule
  is written out at the silent build.
- **What this step IS now: the readback discipline below, and the what-if lane.** The readback is
  worked at the priced board; the what-if lane is this step's headline and it is where he
  problem-solves his booking. Everything below binds exactly as it always has.

**The call, for reference — it is made ONCE, at the silent build, and never again here:**

```python
budget = wwtc_pipeline.court_budget(
    slate=setup["slate"],
    constraints_doc=setup["constraints"],                   # HIS RULES — the other half of the pair
    finals_map=finals_plan.finals_map_from_doc(fmap) if fmap else None,   # the DAYS, not the doc
    ceilings=None)                                          # None = read them off the slate
```

⚠ **THE SETUP IS A PAIR — his courts AND his rules — and this call takes both halves. If you
leave `constraints_doc=` off, the call now STOPS** with a message naming what is missing. It used
to run: it quietly swapped in the tool's own rulebook and priced his tournament against rules he
does not use, with nothing on any surface saying so. If you see that refusal, you have handed the
step half his setup — pass `setup["constraints"]` and run it again. Do **not** work around it by
passing `wwtc_pipeline.default_constraints()`; that is for a bench call that genuinely means the
tool's defaults, and here it would re-create the exact fault the refusal exists to stop.

**Read this back to him in one sentence, out loud, before any court figure:** `budget["rules"]`
says which rules produced the answer — `source` `"caller"` means *"these numbers were computed
under the rules you typed"*, `"defaults"` means *"under the tool's own rules, not yours."* On his
run it must say `"caller"`. Saying it is the difference between a booking he can trust and one he
only assumes.

⚠ **THE SAME ARGUMENT NAME TAKES TWO DIFFERENT SHAPES IN THIS RUN. Read this before you write
the call from memory.** `finals_plan(setup, finals=…)` at Step 2 takes the whole **document** the
TD pasted back. `court_budget(finals_map=…)` here and `build_combined(finals_map=…)` at Step 4
take the **bare** `{division: date}` map from inside it. Hand this step the document and it stops
dead — `TypeError: unhashable type: 'dict'`, in 0.0 s, before a single tournament is built.

**`finals_plan.finals_map_from_doc` is the ONE sanctioned unwrapper. Never take the key directly
as `fmap["finals_map"]`** — the unwrapper is also the loud courier-typo gate, and it is the only
thing standing between a mistyped paste and a court answer computed against the wrong calendar:
it refuses a wrong schema, an unknown division name, a date outside the window, and a finals day
too early for the rounds that division needs. Taking the key directly passes a smoke test and
silently throws that check away.

⚠ **`fmap` is `None` on Step 3's "use the engine draft as-is" path**, which is why the call is
guarded rather than unconditional. `court_budget` already treats `finals_map=None` as "no calendar
supplied" and says the finals-day savings were not priced — see the `finals_savings` note below.

⚠ **ON A SEPTEMBER RUN THAT USED THE SEARCH, `fmap` IS NEVER `None` HERE** (BEST-1, run finding 3
from 2026-08-29). The calendar he picked at Step 2 is already a real `td-finals-map/v1` — the
`seed` document that step builds — so accepting the map unedited hands a concrete calendar down
the line and **the finals-day savings are priced instead of reported unpriced.** Carry `seed`
forward as `fmap` on the accept-the-draft branch rather than passing `None`. Nothing new runs; the
guard above simply stops being reachable with `None` on that path.

⚠ **Do NOT drive this from the conversation.** Do not loop over court counts yourself, do not
print a line per build, and do not ask it for schedules. It runs dozens of real tournaments
internally and hands back counts and configurations; a search steered turn-by-turn would fill the
window and fall over partway through the afternoon. One call in, one compact answer out.

**How to read it back — the two numbers and the gap between them (R4).**
- **`floor`** — the cheapest court plan that plays every match. Say what it costs him in his own terms,
  from `floor["degradation"]`: matches moved to another day, matches out of the day's order,
  venue preferences bent.
- **`clean_line`** — the cheapest court plan that plays cleanly. **Read it against `floor_residue`, never
  against zero.** A real field always carries some movement, because players entered in several
  divisions force it; a clean line described as "nothing moves" is a promise the tool cannot keep.
- **`cushions`** — tight / comfortable / safe. **Lead with comfortable** (R12). Tight is the
  cheapest week that plays at all and leaves him nothing if a draw comes in bigger than estimated.
- **⛔ THE HOURS AND THE LIGHTS — three lines, all three said, every figure read off `axes`**
  *(FIX-1, off the 8/29 run's booking findings; R11 discipline)*. He is not booking "courts". He is
  booking a club, for certain days, for certain hours — and the answer above says nothing about
  the hours or the floodlights he is paying for. The figures already exist on `budget["axes"]` and
  went unspoken — the 8/29 run worked its idle hours and its unused floodlit nights out BY HAND,
  off an answer that was already carrying both. ⚠ **No figure from that run is repeated here and
  none may be: they are facts about one field on one week** (ruling 12). Say all three lines even
  where one is empty — **an unsaid line reads as "nothing idle", which is a different answer from
  "not measured"**:

  > At **`<club>`** you have booked **`<booked_from>`–`<booked_until>`**, and the tournament
  > plays **`<played_first>`–`<played_last>`** — **`<idle_hours>`** of opening nothing uses.
  > **`<idle_days>`** club-days go unused across the week — **`<club>`** on **`<days>`**.
  > **`<club>`** has floodlights booked on **`<nights_booked>`** nights and the tournament plays
  > under them on **`<nights_used>`** — **`<nights_unused>`** unused.

  ⚠ **EVERY `<slot>` IS READ OFF `axes` AT RUN TIME AND NONE OF THEM IS EVER TYPED**, the same
  discipline the surplus and refusal readbacks carry. Hours come off `axes["hours"]["clubs"]` —
  each row's `booked` pair against its `played` pair, and its own `unused_minutes`; club-days off
  `axes["club_days"]` — `idle_total` and each row's `idle` day list; lights off
  `axes["lights"]["clubs"]` — `nights_booked`, `nights_used`, `nights_unused`. Name the club by
  its `club_name`. A session that types a figure here reads it aloud to a real director (ruling
  12).
  ⚠ **SAY THE LIGHTS AS LIGHTING AND NEVER CONVERT THEM INTO A COURT NUMBER** — the shipped
  `lighting` rule's words, and it binds here exactly as it binds in the surplus readback.
  Floodlights are a club's evening, not two more courts.
  ⚠ **WHERE AN AXIS IS NOT THERE, SAY THAT — never announce an absence as slack.** `axes` reports
  on whatever his own clubs and days can carry: **`axes["lights"]` is absent when no club he
  booked has floodlights at all**, and an `idle_total` of zero means every club-day he booked
  gets used. Both are answers; say which one you are reading.
  ⚠ **FACTS BESIDE THE BOOKING LEVER, NEVER ADVICE (R11).** State what sits idle and stop. Do not
  tell him to shorten a booking, drop a night or give a club back, and **never compute a surplus
  of your own** — the two obvious measures are both wrong in opposite directions, neither is in
  the answer, and neither may be put there in conversation (R-10 stands, unchanged). What to do
  about idle hours is his call and he is the one holding the club relationship.
- **`finals_savings` — ASK-ONLY. Say ONE line that it exists, and read the rows out only if he
  asks for them** *(CF-1, Operator ruling 1 of 2026-08-30, off the 8/29 run's OI-5)*. The standing
  readback used to list every finals-day move that would lower the bill. It no longer does. The
  line to say is one sentence — that the answer holds finals-day moves that would lower the court
  bill, and he can have them — and then stop.
  **Why it was demoted, measured on his own field:** the tool's day-move offers are the search's
  own lever and the search has already pulled it, so what arrived at this step were scraps or bad
  trades. The one the director took on 8/29 saved a court at the cheapest week and **doubled the
  matches out of the day's order there**, while at the level he is told to book to the answer was
  **identical before and after**. Offering that unasked is the tool nudging his calendar, and the
  tool prices his calendar — it never reshapes it.
  **When he asks, read each row WHOLE — the courts saved, the cost, and the level.** All three are
  on the row and none of them is ever typed:
  - `saves_courts` and `total_after` — what the move buys.
  - `degradation_delta` — what it costs in the shape of his week: matches moved to another day,
    matches out of the day's order, venue preferences bent, late Level-1 Mixed. **A row read
    without its delta is the exact gap OI-5 recorded.** Where the delta is zero on a counter, say
    *"nothing else moves"* on it — silence and not-measured must never sound the same.
  - `level` — the configuration the saving is priced against. It reads **`floor`**, which is the
    cheapest week and **not** the level R12 tells you to lead with. **Say that out loud**: the
    saving may be worth nothing at all at the level he is booking to, and on 8/29 it was worth
    exactly nothing there.
  **Name them as facts, never as advice** (R9): the tool prices his calendar, it never reshapes
  it. Do not rank them, do not pick one, and do not tell him a saving is worth taking.
- **`out_of_room`** — clubs that cannot supply what the answer needs. This is R9's "the door is
  shut here", and it is a different sentence from "book more".
- **`watchlist`** — the divisions closest to needing a bigger draw, and the entry count at which
  each stops costing a court and starts costing a **playing day**. He can buy a court; he cannot
  buy a day once the calendar is published.
- **`daily_cap`** (R20) — whether the week this search recommends runs a day past **his own**
  matches-per-day figure. It carries the target, the busiest day and its count for each
  configuration the search actually built, and for every day over: the day, the count, how far
  over, and the biggest division that OPENS that day. **Read it out whenever it is present, and
  read the busiest day out even when nothing is over** — "your busiest day is 119 against your
  limit of 130" is an answer he wants. ⚠ **This REPORTS and moves nothing** (Operator, 8/22 —
  OI-B9 option 1). Do not offer to fix it, do not suggest which matches should move, and never
  imply the tool has already spread the day: which matches move, if any, is his call.

  ⚠ **IF THE BLOCK IS ABSENT, THERE ARE TWO CASES AND THE OLD READING NAMED ONLY ONE (S-1
  §1-E7).** *"The rules carry no matches-per-day figure"* is often simply untrue — the default is
  **130 and present**. The other case is the one a September director is most likely to land in:
  **on the out-of-room path the search returns before the daily-cap step ever runs**, so the
  figure was never computed. Read the absence honestly:
  - **`out_of_room` is non-empty** → *"the search stopped before it got to your busiest-day
    figure, because it ran out of room first."* Do NOT ask him for a number — he already has one,
    and asking implies the tool lost it.
  - **otherwise** → the run's rules really do carry no figure. Ask him for it **in words**:
    *"how many matches in a day is too many, for you?"*

  ⚠ **NEVER SEND HIM TO A CONTROL HE CANNOT SEE** (S-1 §1-E7 — the principle, which stands). The
  worked example this rule used to carry was `pacing`, and **that example is now false and has
  been deleted**: S-3 restored `rest`, `sdf`, `pacing` and `earliest` to the Rules tab, so
  `matches_per_day_target` IS on screen and you may send him to it. The one section still hidden
  is `ml1`. Check before you point at a box; an instruction that cannot be followed costs his
  trust in everything else the run has told him. **The finals-map editor at Step 3 already flags
  days against this same figure** from the planned draw ladder; this is the same limit read off
  real builds, and if the two ever disagree say both numbers rather than picking.
- **`not_tried`** and **`partial`** — **read these out**. A cap that goes unmentioned reads to him
  as full coverage. If `partial` is true the search hit its build budget and the floor may be high.

**Three things to say out loud, every time.**
- **The number errs high.** It is a defensible booking, not the theoretical minimum — a greedy
  descent can sit a court or two above the true floor. That is the safe direction against a
  booking he has promised, and it is said, never implied away.
- **No dollars** (R11). Courts, days and hours only. The tool has no basis for a court rate and
  must not imply one.
- **This answer is stale by January** and is **re-run, never quoted** (ruling 12). Say so at the
  time, so a September figure never gets repeated back in January as though it still held.

---

#### The week does not fit — `does_not_fit`  *(S-4, Operator rulings R1–R3, R6, R7, R17, R18)*

**One key, one shape, whichever way the week is pointing.** `does_not_fit` is present when the
week refuses **as he booked it** — whether the search then found a holding booking under his
clubs' ceilings (`case: "middle"`) or ran out of room at them (`case: "exhaustion"`). Read all
four parts, in this order:

1. **`shortfall.bottleneck` — WHERE it broke.** Read `sentences` out verbatim. It names the club,
   the day, the band and the window in his own hours, with every number carrying its denominator.
   ⚠ **`frame_words` is not decoration — say it.** *"At everything your clubs own"* and *"as you
   booked it"* describe two different bookings, and a figure read out under the wrong one is a
   booking he never made, said to his face.
   ⚠ **IT IS EVIDENCE, NEVER A PRESCRIPTION.** Do not turn it into advice. The obvious move it
   suggests was driven on a refusing week and does nothing: the full court count from 08:00 on
   the jam day alone changes nothing, and on every day it places every match and leaves the
   refusal standing. The engine re-flows — a court given on Thursday frees Friday by moving what
   was occupying Friday — so **the day it broke on is not the day to buy courts on.**
2. **`shortfall.reasons` — what to buy.** Each carries the answer if one was found and confirmed,
   what was tried, and what was not. Read `not_tried` out.
3. **`remedies` — the two changes to what he already has.** The mid-morning step-up, and which
   club on which days. ⚠ **Read `single_day_bound` and `greedy_bound` out**: the search states
   where it stopped, and a bound left unsaid reads as "we checked everything".
4. **`bendable` — the nine rules, each re-run for real.** Nine rules on eight levers, seven
   builds. Report what each one did. ⚠ **The list is CLOSED. Never add a tenth**, and never
   propose match length, the busiest-day figure, the per-player cap or the finals-per-day figure —
   they are off this advice by ruling, on every surface and in both seasons.

**`builds` carries two numbers and they are not the same number.** `descent` is the search's own;
`branch` is what the diagnosis cost. Say both. A director told "25 builds" when sixty tournaments
were built is being told a figure that is not about anything.

---

#### The week holds — `surplus`  *(S-4, Operator rulings R9–R16)*

**The step answers in BOTH directions from one call.** When the week holds, `surplus` says what he
has booked beyond what the tournament needs — **in courts, club-days AND opening hours**, because
he does not book "courts", he books a club, for certain days, for certain hours.

⚠ **READ `register` FIRST, AND LET IT DECIDE YOUR VERBS.**
- **`advice`** — a safe level was BUILT, so there is a verified margin behind every release.
- **`facts`** — no safe level could be built at his clubs' ceilings. **Recommend nothing.** State
  what sits idle, state its consequence, and read `why_no_release` out as written. The release
  call is his alone. **This is the branch a director whose clubs are all at their Max Courts
  figure lands in, and that is a common booking, not an edge case.**

- **`courts` / `club_days` / `hours`** — each carries `built`, so you can say a release was
  re-built and held. ⚠ **Every line carries a `cost`. Read it.** A release that quietly pushes
  his busiest day past his own figure is discovered in January by a player who planned around
  Thursday and finds out they play Friday. A zero-cost release says **"nothing else moves"** —
  say that too, because silence and not-checked must never sound the same.

  **⛔ THE SURPLUS READBACK — THREE SLOTS, ALL THREE SAID, EACH WITH ITS COST.** The deficit
  direction has a scripted readback and this one did not, so it was read out however the session
  felt like reading it. Say all three lines even where one is empty — an unsaid line reads as
  nothing to release, which is a different answer from none found:

  > You have **`<courts>` courts** more than this tournament needs at **`<club>`** — releasing
  > them **`<cost>`**.
  > You have **`<club_days>` club-days** you could give back — **`<club>`** on **`<days>`** —
  > releasing them **`<cost>`**.
  > You have **`<hours>`** of opening you could give back at **`<club>`**, **`<hours_when>`** —
  > releasing them **`<cost>`**.

  ⚠ **EVERY `<slot>` IS READ OFF `surplus` AT RUN TIME AND NONE OF THEM IS EVER TYPED**, the same
  discipline the deficit readback carries. `<cost>` is the line's own `cost` — where it is zero,
  say **"nothing else moves"** in those words.
  ⚠ **WHERE `register` READS `facts`, READ `why_no_release` OUT VERBATIM IN PLACE OF ALL THREE
  LINES** and recommend nothing. No safe level was built, so there is no verified margin behind
  any release, and the three lines above would each be a recommendation the run cannot stand
  behind.
- **`club_not_needed`** — ⚠ **A FACT WITH ITS CONSEQUENCE, NEVER ADVICE** (R11). Say the
  arithmetic and stop. Never *"you don't need it"*. A club is more than its courts, and the tool
  knows the arithmetic and nothing about the relationship.
- **`lighting`** — say it as lighting. Never convert unused floodlit nights into a court number.
- **`assumes`** — read it out, every time. The draws come in at the sizes he estimated, and
  nothing here holds room for a division that grows. `at_risk` names the divisions that were
  already at or over their bracket last season.
- ⚠ **NEVER compute a surplus yourself.** Two obvious measures are both wrong in opposite
  directions — idle court-hours says release half the week and would release courts he needs;
  spare-at-peak says release nothing and hides a whole club. Neither is in the answer, and
  neither may be put there in conversation.

---

#### `axes` — his resources against his tournament  *(S-4, Operator ruling R9)*

Six axes off the same build, each graded **BINDING** or **SLACK**: courts per club per band,
opening hours, club-days, lights, the busiest day against his own figure, and same-day
club-to-club moves. ⚠ **It reports on whatever axes his own clubs and days can carry** — a
one-club week has no transit axis, an unlit club no lights axis — so read what is there and never
announce an absence as slack. **Transit is a COUNT with no verdict**: nothing he booked states a limit on it, and
grading it would be enforcing a rule nobody set.

---

#### The problem-solving loop — test his idea, never reason about it  *(S-4, Operator ruling R6)*

**The lens (R6):** the engine states the bottleneck, **he problem-solves with you in conversation**,
and when he has a change worth keeping he goes back to the Setup console and makes a new document.
Diagnostic, never optimisation.

**When he proposes something — a club opened on a day, more courts somewhere, a rule relaxed —
BUILD IT. Do not reason about it.**

```python
answer = wwtc_pipeline.try_change(
    base_slate=setup["slate"],
    constraints_doc=setup["constraints"],        # HIS RULES — his idea is tested on top of THESE
    slate=[("ORLP", "2027-01-27", "main", 2)],   # his idea, in courts…
    rules={"day_shape": None},                   # …or in rules; a value of None switches one off
    finals_map=fmap_days)
```

- ⚠ **`constraints_doc=` IS NOT OPTIONAL HERE, and this is the lane where leaving it off did the
  most damage.** His rule idea is *merged onto* the rules document, so a missing document meant
  "switch this rule off and tell me what it saves" was answered by switching it off on top of
  fourteen rules that were not his — an idea tested against a tournament he is not running, and
  possibly kept. The call now STOPS instead. If it does, pass `setup["constraints"]` and re-run.
- **Read the answer's own record back before you report what his idea did:** `answer["rules"]`
  carries `source` (`"caller"` = his rules, `"defaults"` = the tool's) and `edited` — the rules
  his idea actually moved. Say which, out loud: *"tested on your rules, with that one rule
  switched off."*
- ⚠ **EVERY RE-TEST OR WHAT-IF THAT ENDS IN A REFUSAL PRINTS THE FRESH REPORT VERBATIM.** You may
  summarise on top of the report; never instead of it. His idea gets the same treatment the first
  refusal got — the whole report, then the four figures read back — because a summary is where the
  numbers he would act on go missing. Measured 2026-08-28: the what-if re-test was summarised
  freelance and the fresh report was never printed, so the one thing that changed between the two
  runs was never on his screen.
- ⚠ **A court figure derived in chat is exactly how a wrong booking reaches a club.** One real
  build, about half a second on a September field. Never arithmetic in the conversation.
- ⚠ **It takes COURT edits and RULE edits**, and both matter — the nine bendable rules are rules,
  and a loop that only tests courts sends every rule idea back to hand-rolling.
- ⚠ **Counts only, never a schedule.** Asking it for one is refused, deliberately. Forty
  tournaments through a chat window fills it and the run falls over partway through his
  afternoon.
- ⚠ **TESTING an idea is free of the courier lane. KEEPING one is not.** Try as many as he likes
  here. The moment he wants to keep a change he needs a new setup document — from the Setup
  console, or, for a single named field on his instruction, from standing procedure 4's inline
  lane — and **S-1 §1-E5 binds either way: a new setup invalidates `plan`, so Steps 2 and 3 re-run
  before Step 3.5 or Step 3.6 are used again.** ⚠ **He is never sent down that road by a session's
  own reading of the answer** — the ⛔ stop at the end of this loop is where he chooses, and its
  price is read off this run.

**No document comes out of `try_change`** (R10). Its answer is delivered in conversation — counts,
never a schedule. What he *does* with that answer is the stop below, and that is a different
question from what the call returns.

---

**⛔ THE STOP AT THE END OF THE LOOP — FIRED AFTER EVERY `try_change` THAT RETURNS, whether it
found something or found nothing** *(STOP-1, Operator ruling 2026-08-30, off the 8/29 run's
OI-2).* Measured 2026-08-29: a `try_change` came back with a materially better week, the session
read the numbers out and went straight on to the next step, and the Operator had to halt the run
himself to say he wanted it kept. His words: *"The tool must offer the improvement, wait for user
to respond."* This step already said *"try as many as he likes here"* — as prose, and prose did
not hold a session to it, which is the same reason Step 2's refusal moves became a numbered
checklist and Step 3a became a step rather than a line of advice.

⚠ **A test that found nothing still gets the stop.** The temptation is to skip it there, and it is
the wrong instinct twice over: he is entitled to keep a change that bought him nothing measurable,
and a stop that fires only on good news teaches him that silence means bad news. Where the test
changed nothing, say so in the question's first clause and offer the same three options.

⚠ **If the call STOPPED rather than returned** — the missing rules document — there is no result
to decide about. Fix the call as the warning above says, re-run it, and the stop fires on the
answer.

**SAY THE PRICE BEFORE HE CHOOSES, AND READ IT OFF THIS RUN.** Keeping a change costs a new setup
document and then Steps 2 and 3 in full. The figure to quote is **the days check this session has
already run — its own elapsed time** — plus the quieter-week search's own, if he ran one.
⚠ **Never quote a duration from this document.** Timings move with his field and with the day; a
printed expectation teaches him to read ordinary variance as a fault.
⚠ **ON THE SEPTEMBER LANE THE RE-RUN IS ONE SILENCE, AND THAT IS WHAT YOU QUOTE (CF-1).** Steps 2
and 3 re-run as the **silent build** — the days graded and the booking answer re-priced together,
one honest sentence naming the wait, no question in the middle — and land back at **the priced
board**. Quote it as the one wait it is, not as two.

**⛔ ELICIT — your action for this step IS the tool call. Call the elicitation tool with the options below, then end your turn. Do not run any code, do not write a prose question, do not pause silently — those all count as skipping the step.** *"Keep this change? It needs a new setup and the days check run again — about `<check_time>` on your field, plus `<search_time>` if you want the quieter week looked for as well."*
- **`Keep this change`** → the keep lane. **One named field** of the setup he last pasted → the
  inline lane at **standing procedure 4**, on this instruction, under its six obligations —
  he confirms the edit in plain words before anything uses it. **Anything wider** → back to
  **Step 1**, where he emits a new setup on the console. Either way **S-1 §1-E5 binds: the new
  setup invalidates `plan`, so Steps 2 and 3 re-run before Step 3.5 or Step 3.6 are used again** —
  say that in one clause as he chooses it, not afterwards.
- **`Test another idea`** → back to the top of this loop. Build it, read the answer back, and this
  stop fires again. As many times as he likes; nothing here is couriered and nothing is spent.
- **`Carry on`** → **nothing he tested is kept** — his week stands exactly as the court budget
  above described it, under the rules and courts he pasted. Say that clause before he takes it. In
  a September run, go to **Step 3.6**; the days he accepted at the priced board are the days that
  get announced, and the acceptance record he minted there rides with them.

### Step 3.6 — Announce the calendar  *(SEPTEMBER PLANNING RUNS ONLY — skip it in a January run)*
*(PUB-1, Operator decisions 1–4, 2026-08-23. No courier stop: this runs in your own session and
nothing crosses a console boundary.)*

**When this step applies.** Only in a **September planning run**, and only once the TD has approved
his finals days at Step 3 — the same test Step 3.5 already states. A January run skips straight to
Step 4. If you are not certain which kind of run you are in, ask before running anything.

**What it answers.** *Which file is the calendar the players were told about?* Until this step
there was no way to tell it from any other copy of it, and four months later that is the whole
question — the days he announces in September are the days a player books flights around.

**Elicit two things first, in plain words, and do not guess either.**
1. **The date the calendar goes out to the players.** Type it in. It is not taken from the
   computer's clock: the date has to be the day the tournament announced its calendar, not the day
   this run happened to be executed, and the same run repeated has to produce the same file.
2. **What he wants it called** — his own name for what is going out, so months later he knows which
   one it is without opening it. If he offers none, it is named from the tournament and the date;
   it is not left blank.

**Then make ONE call.**

```python
import json, finals_publish
announced = finals_publish.stamp_finals_map(fmap, published_on="2026-09-15",
                                            label="WWTC 2027")          # his own words
with open("WWTC_2027_announced_calendar.json", "w") as f:                # the file he keeps
    json.dump(announced, f, indent=2)
```

If he has already announced a calendar and is doing it again, this refuses and tells you the date
it would have written over. That is deliberate — announcing twice is a decision he makes out loud,
not something that happens quietly. Ask him, and only then pass `replace=True`.

**⚠ THE ACCEPTANCE RECORD RIDES THROUGH BOTH CALLS AND YOU DO NOTHING TO CARRY IT (CF-1).** If
`fmap` carries `_acceptance` from the priced board, `stamp_finals_map` and `announce_finals_map`
both preserve it — unknown top-level keys pass through, the same lane `_session_edit` travels —
and `finals_map_from_doc` drops it at the gate, so nothing downstream can see it or behave
differently because of it. **Do not re-write it here, do not re-date it, and do not put it on the
printed page.** It is a record for January's read-back: the fingerprint of the map he accepted,
when he accepted it, and whether he accepted the board as shown or after an edit. **A run that
reaches Step 3.6 with no acceptance record has skipped the priced board's stop** — go back and
work it, rather than minting one here for days he never said yes to.

**⚠ Which file goes on the shelf — say this out loud, every time.** You are now holding **two**
things: the block the TD pasted back at Step 3, and `announced`. **The one he keeps is
`announced`.** Write it to a file, tell him where it is, and tell him the other one is the draft he
approved rather than the calendar his players were told about. Shelving the wrong one puts January
back exactly where it started — though the mistake is at least a visible one, because a file with
nothing written on it is plainly not the announced calendar.

**What the check on that file does, and what it does not do.** The file carries a check over the
days themselves. It **catches a file that drifted** — an old copy, a hand edit, the wrong one of
two saves. It is **never proof of who produced it**: anyone who can change the days can work the
check out again, and it cannot see an edit to the date written on the file itself. **Say both
halves.** A run that oversells this teaches the director to trust a check that cannot carry the
weight, and he will find that out in January when it matters.

**The file also says what produced it, and that is worth one clause — no more.** Alongside the
days, it records how many divisions were priced and whether they were estimates or real entries,
a fingerprint of the rules the answer was worked out under, and — division by division — whether
its day was checked and held, was checked and flagged, was moved after the check, or was never
checked at all. **Say it the same way as the paragraph above: it is an honest note of what
happened, not proof of who did it.** Anyone who can edit the file can edit that note, and nothing
would catch it. What it buys is real and narrow: in January, a person can tell a day that was
proven from a day that never was, instead of guessing.

**Then, on the same file — the days he can announce (ANN-1).** *(Operator decisions 1–4,
2026-08-23. Still Step 3.6, still no courier stop: this is the rest of the same step, not a
second procedure.)*

The file now says which calendar it is. It does not yet say **what was announced**. The finals
day travels on the map, so January can always look it up — but **the day first matches begin
cannot be worked out again in January**, because it depends on what September estimated the draws
would be, and January has the real draws instead. If September does not write it down, nobody can
ever tell whether the promise held. So write it down, in the same call, onto the same file:

```python
import finals_announce, master_schedule, draws_pdf
draws = [d for lvl in ("1", "2") for d in draws_pdf.parse_draws(level=lvl)]
divisions = master_schedule.divisions_from_draws(draws)
announced = finals_announce.announce_finals_map(
    announced,                                                 # the stamped file from above
    divisions,
    setup["slate"]["dates"],                                   # the days he most recently pasted
    same_day_finish=finals_announce.same_day_finish_from_setup(setup, divisions),
    watchlist=finals_announce.watchlist_rows(),                # R7's thresholds, called
    rr_entrants=finals_announce.rr_entrants_from_draws(draws),
    # What produced this calendar — the same one call, the same one file.
    field_source="projected",                                  # a September run; "drawn" in January
    rules=finals_announce.rules_record_from_setup(setup),      # whose rules, from his own setup
    engine_check=plan.get("engine_check"))                     # the LAST check that ran, or None
with open("WWTC_2027_announced_calendar.json", "w") as f:      # the same file, rewritten
    json.dump(announced, f, indent=2)

# FIX-1 — the page he can print, written beside the file he keeps.
with open("WWTC_2027_announced_calendar.html", "w") as f:
    f.write(finals_announce.render_announced_calendar(announced))
```

**⚠ TWO FILES NOW, AND THEY ARE NOT THE SAME KIND OF THING — say which is which.** The **JSON is
the file of record** and it is the one that goes on the shelf; nothing about that changes. The
**HTML page is the deliverable he prints and hands out** — every division's finals day, the day
play begins, what happens if the entries come in bigger or smaller, and whether each day was
checked. Before FIX-1 there was no page at all and the 8/29 run built one by hand in-session,
which means the thing the director walked away with was assembled by a session rather than
rendered off his file.

**The page is rendered off the announced document and re-derives nothing** — every date and every
sentence on it is copied out of the same record the JSON carries, so the two cannot disagree. It
carries the fingerprint too, and beside it **both halves of the honesty sentence** in the same
words you say them here: it catches a file that drifted, it is never proof of who produced it.

**⚠ It refuses a map that was never announced, by name.** If you call it on the block he pasted
back at Step 3, or on a stamped file whose days were never written, it stops and tells you which
step comes first. That refusal is the point: a printable calendar rendered off a discarded draft
is indistinguishable from the real one, and printing it is how a discarded draft becomes the thing
his players were told.

**⚠ `engine_check` comes off the plan you are holding, and you pass it — the tool never goes
looking for it.** Hand over the check that most recently ran. If he declined the recheck at Step
3a, the plan you have is the one from before he moved days, and that is exactly right: the
calendar will then say those days were moved after the check, which is the true thing to say. If
no check ever ran, pass `None` and the file records that no day was checked. **Never reach for an
older plan to make the record look better** — a record of a check that did not cover these days is
worse than a record saying none did.

**Do not drop `same_day_finish`.** If the TD has asked for any division to finish on the same day
it plays its semifinal, leaving that argument out announces every one of those divisions **a day
earlier than the tool will actually play them**. Nothing else in the run will catch it.

If he has already announced start days on this file, this refuses and says how many divisions it
would write over. Ask him, and only then pass `replace=True`.

**Read it back to him, per division, and read back only this.** The finals day, the day first
matches begin, and the second date where there is one. **Nothing about courts, nothing about how
full the days are, nothing about which matches had to move** — the announcement is a calendar,
not a report, and he is about to retype these days into an email to his players.

**⚠ Where a division is one Step 1.5 filled in, say so when you read its days.** Its days are
built from his estimated bracket sizes, with no entries behind them. The day can be announced —
that is the point of the September run — and it is announced with the estimate named, the same
sentence Step 1.5 requires everywhere: estimates, not entries.

**The tool prints this readback — you read it out, you never assemble it.** One line per
division, every date on it taken off the announced file, so there is nothing to look up and
nothing to work out. Run it, then read the lines to him. The paragraphs below say how to read
each kind of line, and the ⛔ stop at the end of this step is where he answers.

```python
for event, d in sorted(finals_announce.start_days_of(announced).items()):
    bits = []
    if d["earliest_possible_note"]:
        bits.append(d["earliest_possible_note"])    # no date exists — read these lines FIRST
    elif d["format"] == "round_robin":
        if d["earliest_possible_start"] == d["first_match"]:
            bits.append("the same day even if one more person enters")
        elif d["earliest_possible_start"]:
            bits.append(f"as early as {d['earliest_possible_start']}"
                        " if one more person enters and it runs as one group")
    elif d["bigger_draw_costs_a_day_at"]:
        bits.append(f"past {d['bigger_draw_costs_a_day_at']} entries,"
                    f" play begins {d['earliest_possible_start']}")
    elif d["earliest_possible_start"]:
        bits.append(f"if it outgrows its bracket, play begins"
                    f" {d['earliest_possible_start']} — the entry count that does it was"
                    f" not worked out")
    if d["first_match_if_smaller"]:
        bits.append(f"or {d['first_match_if_smaller']} if the draw comes in smaller")
    if not bits:
        bits.append("no second date on the file")
    print(f"{event} · final {d['final']} · play begins {d['first_match']} · "
          + " · ".join(bits))
```

**⚠ Every bracket division now says what happens if it GROWS, and that is the half he could not
hear before.** The line gives the entry count that costs a whole extra playing day and **the day
play would begin once he passes it** — *"past sixty-five entries, play begins the Monday
instead."* Read it as one fact, not two: the count on its own is a number he cannot act on, and
before this the count was all the file had. **Where a division also carries a smaller date, say
both directions and say what decides between them** — *"Play begins Tuesday the 27th if the draw
fills. If it comes in smaller, Wednesday the 28th — that is what happens at thirty-two entries or
fewer. If it comes in bigger, Monday the 26th."*

**⚠ Where a division carries no SMALLER date, say why, in plain words — never in silence.** A
missing smaller date reads as an oversight, and it is not one: *"if fewer people enter, this one
may run as a group instead of a bracket, and a group takes longer, not less. The day you announce
holds if it runs as it did last year."* **It still has a growth answer** — the direction that goes
the other way is on every bracket division, and the line carries it.

**⚠ And where the count itself was never worked out, say that, rather than reading a blank
aloud.** The line then gives the day play would begin if the division outgrows its bracket, and
says the entry count that sets it off was not worked out. That is a fact about his week either
way; only the trigger is missing.

**⚠ Where a division is a round robin, give him the two facts and stop.** Say the day it begins if
it runs as it did last year — **and** the earliest it could begin if it comes back as one group
with one more person in it, which on the canonical inputs is **two days earlier**. He cannot plan
against a flag that only says "this one is uncertain"; he can plan against a date.

**⚠ And where the file gives no earliest date, read the sentence instead — this is the finding of
the whole step.** For those divisions the next step up is not an early start, it is **no room at
all**. There are two of these sentences and they are not interchangeable, because they are set off
by different things:
- a group division that comes back with one more person in it — *"if this division runs as one
  group next January, the week as planned has no room for it."*
- a bracket division that fills up past its draw — *"if this division outgrows its bracket next
  January, the week as planned has no room for the extra round it would need."*

**The second one is new, and it is the finding that was invisible until now.** Those divisions
have been printing the entry count that costs a playing day as though the day were there for the
taking. It is not. Say it in September, when he can still do something about it — move the final
later, or accept that the division is capped. Discovering it in January means discovering it after
the announcement has gone out.

**⚠ Three things this step never says.**
- **It never promises the day will hold.** These are the days as planned. A real January field can
  move them, and the tool says so when it does — it does not guarantee them in advance.
- **It never gives a round-one date for a named player.** The announcement is per division: the day
  the division starts, never the day a person plays. That is the shape the approach was locked on,
  and it matches how the nationals, the sections and the ITF Masters announce.
- **It never prints an earliest date the week cannot hold.** Where there is no room, there is a
  sentence and no date. A fabricated date there would be the one number in this whole step a
  director would act on and be wrong about.

**⛔ ELICIT — read the days back before he sends them (R-4, Operator ruling 2026-08-27).** The
printout above is read to him **line by line** — and **any line saying the week has no room is
read first**, before the days that are fine, because it is the only one he cannot act on in
January. **Both no-room sentences count**, the group one and the bracket one alike; read them all
before anything else. Then call the elicitation tool with the options below and end your turn. Nothing has
been announced until he has heard the days he is about to send: *"That's every division's finals
day, the day play begins, and what changes if the entries come in bigger or smaller than last
year. Ready to send?"*
- **`Send it — these are the days`** → the calendar stands as written; the file you shelved above
  is the one he keeps.
- **`Hold — I want to change days first`** → go back to Step 3 and hand him the finals board
  again. When he has settled the days, re-run this step from the top on the map he comes back
  with — writing over a calendar that is already stamped is refused, exactly as above, so tell
  him what it would write over and only then pass `replace=True`.

This stop exists because the protection that came before it was a sentence a session had to
remember, and on 2026-08-25 a run announced a count instead of the days. It never re-opens a
decision he has already made; it makes sure he heard them.

**A September planning run ends here.** Steps 4 onward build the tournament itself against a real
field, and that is the January run's work. What September hands forward is this one file.

### Step 4 — Schedule (one combined pass)
**⛔ ELICIT — your action for this step IS the tool call. Call the elicitation tool with the options below, then end your turn. Do not run any code, do not write a prose question, do not pause silently — those all count as skipping the step.** *"Schedule the tournament now?"*
- **`Schedule it`** → run:
  ```python
  b = wwtc_pipeline.build_from_setup(setup, finals=fmap)   # R7-2 gate binds the TD's days
  r = b["result"]
  ```
  Print the end-of-run report: placed (`len(r["schedule"])`), byes (`r["byes"]`), unplaced
  (`len(r["unplaced"])`), conflicts (`len(r["conflicts"])`), and any master advisories
  (`b["master_warnings"]` — 6.2; empty on a clean run). On the canonical inputs this reads
  **760 placed · 275 byes · 0 unplaced · 0 conflicts**.

  **Ingest gate-and-report (REVIEW-1 / D4·D14·D19·D23·D8) — print these lines with the report
  above, every run, no exceptions:**
  ```python
  for lvl, m in sorted(b["meta"].items()):
      rate = m["resolution"]["rate"] * 100
      names = "all names matched" if rate == 100 else f"{rate:.2f}% of names matched"
      flags = "Nothing to flag." if not m["warnings"] else \
              f"{len(m['warnings'])} to flag."
      print(f"Level {lvl}: {names}. {flags}")
      for w in m["warnings"]:
          print("   ·", w)
  import csv_export
  n_csv = len(csv_export.first_round_rows(b)[1])
  n_sched = b["reconciliation"]["counts"]["scheduled"]
  print(f"{n_sched:,} on the schedule, {n_csv:,} in the player file. "
        f"{'Agree.' if n_sched == n_csv else 'They do NOT agree — stop and look.'}")
  ```
  **Any rate under 100%, any ingest warning, or any scheduled-vs-CSV mismatch is a
  stop-and-look: show the TD exactly what printed and wait for their nod before Step 5.
  REPORT, never refuse — the build stands; the numbers have to be looked at.** On the
  canonical inputs this reads *"Level 1: all names matched. Nothing to flag."*, the same for
  Level 2, and *"1,066 on the schedule, 1,066 in the player file. Agree."* Four measured
  ways silence used to lose here, all at full, professional-looking deliverables: unmatchable
  roster names (rate under 100%, warnings name each one — nothing gated on either); a
  missing `Events` column (rate 100%, 0 warnings — only the coverage check catches it);
  the wrong draws file for the level (rate ~55% — nothing said a word about the file); two
  entrants sharing a display name (rate 100%, 0 warnings — the CSV quietly writes one row
  fewer than the schedule's own count).
- **`Hold here — not yet`** → stop and wait.

> **If the build FAILS (REVIEW-1 / D18 interim cover).** `build()` on a broken input returns
> `{"ok": False, "error": "..."}` instead of a schedule — and the next call that touches
> `r["schedule"]` then dies with a bare `KeyError: 'schedule'`, which points at the wrong
> place. **The diagnosis lives in `r["error"]` (and `b["meta"]`'s warnings), not in the
> KeyError.** Check `r.get("ok", True)` right after the build; on False, quote `r["error"]`
> verbatim to the TD and stop — do not run any later step against that result.

> **If the week cannot be scheduled at all (NOMAP-1).** Distinct from the box above: nothing is
> broken and no input is bad — the week simply has more matches than its courts can hold, so the
> tool refuses to publish a schedule rather than publish one with matches that have nowhere to
> play. `build_from_setup` raises `wwtc_pipeline.WeekRefused` and there is no result to read.
> Catch it and stop:
> ```python
> try:
>     b = wwtc_pipeline.build_from_setup(setup, finals=fmap)
>     r = b["result"]
> except wwtc_pipeline.WeekRefused as e:
>     print(wwtc_pipeline.format_refusal(e))       # print it VERBATIM — then stop
> ```
> **Report it as the refusal it is: the tool worked, the week does not fit, and here is what would
> fix it — each one already tried for real on these entries.** Print `format_refusal(e)` verbatim,
> lead with the plain sentence that the week as supplied cannot be scheduled, then put the fixes to
> the TD as his decision — never pick one for him, and never quote a figure from this document.
> **The printout now ends with a further section, *"What it would take"*, naming how many courts,
> at which club, on which days and in which part of the day** — every figure re-run for real
> before you saw it, and it is his decision on exactly the same terms as the list above it. Where
> it says no number of courts fixed the week, **that is the answer**, and what it did not try is
> part of it. ⚠ **This costs real time on a refused week and it is spent before the exception
> reaches you** — measured on the reference field, up to about 35 builds and a little over a
> minute. Name the wait the way every other long step is named; do not try to shorten it, and do
> not re-run it yourself to check a number.
> **No later step runs against a refused week** (same posture as the box above): no edit loop, no
> report, no deliverables. When he changes the venues, days or match length in Setup, courier the
> new `td-setup/v1` and start again from Step 2.

> **Infeasible locked days (6.2).** A finals map carrying a locked day too early for its division's rounds
> is REJECTED here with the earliest feasible day named (the editor refuses such drops, so
> only a hand-built map can trigger it). Fix the map and re-run this step — never work around
> the error.

> **Finals days moved (Option A).** A few structurally-infeasible matches (e.g. 09:30-floored
> multi-division 80+ opening rounds) can't sit on their assigned day; they fall to a feasible day
> and are reported in `r.get("assigned_day_spills", [])`. **0 unplaced / 0 conflicts still
> holds** — surface the moved-day list. **The count is not a constant.** It varies with the courts and days
> and the locked days in play, and a locked day **can** add a day move (it is not guaranteed to — a 7-pin map in
> the 2026-07-31 run added none). **Report what the run returned; never assert a figure, and do
> not re-introduce one here** — quoted figures went stale across three builds and a run session
> then read a correct result as an anomaly (DOC-03, 2026-07-31). **7.1:** the same list and any master warnings also
> appear in the Edit console's top warning bar at Step 5, so the TD sees them on the surface
> where they'd act rather than only in this report. If the TD wants different finals days in
> response, **loop back to Step 2** with their emitted map seeded:
> `plan = wwtc_pipeline.finals_plan(setup, finals=fmap)` → regenerate the editor (their moves
> arrive with their days already locked) → new emit → re-run Step 4.

### Step 5 — Edit loop (optional) → `schedule-edits/v1`  *(courier stop 3)*
**⛔ ELICIT — your action for this step IS the tool call. Call the elicitation tool with the options below, then end your turn. Do not run any code, do not write a prose question, do not pause silently — those all count as skipping the step.** *"Hand-adjust placed matches in the Edit console, or go straight to the deliverables?"*
- **`Open the edit loop`** → run:
  ```python
  ep = editor_plan(r, b["cfg"], events=b["events"], constraints_doc=b["doc"],
                   local_players=b["cfg"].local_players, non_drawn=b["non_drawn"],
                   master_warnings=b.get("master_warnings"),   # 7.1: into the warning bar
                   seeds=b.get("seeds"),                       # 7.1: seed flags on the cards
                   roster=b["players"])                        # 7.6: events / rating / L-C badge
  html = render_editor_console(ep)      # 7.0: the edit surface, PRELOADED with the schedule
  # write html to a file and publish it as a private artifact — hand over the link
  # (fallback: outputs/ + open-in-browser instructions)
  ```
  The TD opens the link and edits directly — **no `td-editor-plan/v1` file changes hands**
  (7.0; the plan is embedded at generation). **7.1:** pass `master_warnings=` so the console's
  warning bar carries the engine's advisories alongside the moved-day list (both ride the plan);
  a conflict the TD's own edits introduce also stays in that bar until it is resolved, so it
  can't be discovered only in the applied-edits report below. **Wait** for the TD's emitted
  `schedule-edits/v1` paste, then:
  ```python
  edits = json.loads(pasted_edits)
  r = scheduler_flow.apply_schedule_edits(b["cfg"], edits,   # re-validated; conflicts surfaced
                                          roster=b["players"])   # GENDER-1: the Mixed guard
  ```
  **Pass `roster=` (GENDER-1, 8/8).** It is optional with a safe default, so leaving it out
  changes nothing visible and silently ships the Mixed-team guard dead on the one lane a real
  run uses. With it, a substitution that would leave a Mixed team two men or two women is
  refused — that edit alone; every other edit in the block still applies — and the refusal names
  both players and the division, in the same words the Edit console uses.
  Report `r["applied_edits"]` and any conflicts the edits introduced (WYSIWYG — surfaced, not
  hidden).

  **The block is applied to the ORIGINAL schedule, not on top of the last one (EDITBASE-1,
  8/8).** So the paste has to carry every change made this run, and a console regenerated from
  the current result does that by itself — see standing procedure 2. Two things follow here:
  - **`apply_schedule_edits` now REFUSES a block that is not stamped for this schedule** —
    a different id, or no id at all — by raising `scheduler_flow.StaleEditBlock`. Nothing in the
    block is applied. Read the message out: it names both ids and the fix, which is always
    *regenerate the console and make the changes there*. **Never work around it** by editing the
    JSON or passing `allow_unstamped=True`; that flag exists for the archived replays and the
    harnesses, never for a run.
  - **Going back to the console mid-run: pass the NEWEST `r`** — `editor_plan(r, …)` with the
    result the apply above just returned. Passing `b["result"]` regenerates a console that has
    forgotten the run's changes, and its next block would undo them.

  **⛔ ELICIT — held matches with nobody placed back (added 8/7, Operator ruling, run-2 audit).**
  After applying, check `r["unplaced"]`: every id in it is a match the TD held off the schedule
  and never re-placed (the emit's own `still_unplaced` list carries the same ids — the paste
  tells you itself). **If the list is non-empty, this stop is MANDATORY before Step 5.5** — call
  the elicitation tool, then end your turn. Say it in the TD's terms, with the count and the
  names: *"<n> matches are held with nobody placed — <the players>, <division>. Until they are
  placed, those players are missing from the printed schedules: no row in the player file, no
  handout page, no time on the wall sheet. Advance anyway, or go back and place them?"*
  - **`Advance anyway`** → carry on to Step 5.5 with `r` as it stands. The holds are the TD's
    recorded decision — record it, never argue it.
  - **`Back to the Edit console`** → regenerate the console from the CURRENT result —
    `editor_plan(r, …)` with the `r` this step just produced (standing procedure 2; never reuse
    a console generated before a change, and never regenerate from `b["result"]`). It opens
    holding the changes already made, so the TD places the held matches and the next block
    carries everything. Re-run this step's apply on the new paste.

  A hold can be legitimate (a withdrawal pending confirmation, a match awaiting a ruling) — this
  stop never refuses; it makes the disappearance a decision instead of a discovery.
- **`Skip to deliverables`** → keep `r` as scheduled.

### Step 5.5 — Pre-publication report  *(MANDATORY — no courier stop)*
**⛔ ELICIT — your action for this step IS the tool call. Call the elicitation tool with the option below, then end your turn. Do not run any code, do not write a prose question, do not pause silently — those all count as skipping the step.** *"Run the pre-publication report on the schedule as it now stands?"*
- **`Run the report`** → run:
  ```python
  ms, roster = schedule_report.scheduled_from_result({**b, "result": r})
  rep = schedule_report.report(ms, roster,
                               constraints=b["doc"],              # D-22: YOUR numbers, not copies
                               slate=slate_doc,                   #        the couriered slate
                               mixed_level_1=b["mixed_level_1"],
                               venue_escapes=r.get("venue_escapes"),
                               rule_escapes=r.get("rule_escapes"),
                               seeds=b.get("seeds"),
                               held=r.get("held"),            # HOLDVIS-1: the held-match rung
                               conflicts=r.get("conflicts"))  # RPT-2: the engine's own record
  print(schedule_report.render_text(rep))
  ```
  **`{**b, "result": r}` is load-bearing here for the same reason it is at Step 6's CSV line:
  `scheduled_from_result` reads `["result"]`, and passing bare `b` would grade the UNEDITED base
  build — you would be shown a clean report for a schedule you are not printing.**

  **⚠ Those two middle keyword lines are two different records. Never swap them, never merge
  them.** `r["venue_escapes"]` and `r["rule_escapes"]` are different lists with different shapes,
  each read straight off this build's own record, and each one decides something different in
  what the report prints. Pass both, spelled exactly as above. One passed under the other's name
  is a silent wrong answer — the report still runs, still finds the same things, still grades
  each at the same severity, and prints the wrong advice: on the last check before he publishes,
  it tells the TD to move late starts the tool put where they are on purpose, having already
  proven they had nowhere better to go. Corrected in 8.7; before that the call carried one name
  and not the other.

  **This step is not optional and it is not skippable.** The product goal is that every rule break
  is reported before publication; a check the TD in a hurry can step past is decoration. There is
  one option on the widget, and it is *Run the report*.

  **Report and pause — never refuse** (the Step-4 gate's shape). Read out, in this order:
  1. **how many were found, and how many of each kind** (must fix · check · info), then
  2. **every finding**, in the report's own order, in plain words.

  *(LANG-1: the printed report no longer carries the internal code beside each section — the
  section's plain heading is what you read out. The codes are still in `td-report/v1` for
  anyone diagnosing.)*

  Then **stop and wait for the TD's nod** before Step 6. A finding is information, not a failure:
  the report grades against rules the engine does not all enforce, so a warning here is the tool
  doing its job. Nothing is regenerated and nothing is blocked by what it says.

  **RPT-2 (2026-08-09) — the report now also carries the rule breaks HIS OWN EDITS made.** The
  last section, *Rule breaks after your edits*, is `result["conflicts"]` printed **word for word
  as the engine recorded it** — the same sentences on the red RULE CONFLICTS page at the front of
  the draw sheets. It is a **record, not a re-check**: nothing is re-graded, and the section is
  absent when the list is empty, which is every build the engine makes on its own. Read the count
  with the others. **An accepted rule break publishes** (ruling 8/7) — say what it is and let him
  decide; do not tell him it has to be fixed. Before this the page was blind to them: one move on
  the 2026 field puts 36 on the board and the report's finding count moved by one.

  **What the TD will most often see, and what it means:**
  - **Two rounds in one day** — one division playing two rounds on the same date. The finding says what it costs a
    person, not just that it happened: *"whoever wins the 08:00 Quarterfinals match is back on
    court at 11:00 for the Semifinals."* A division's own **closing day** is the exception and
    reports as **info** — semifinal and final together is how an event finishes. This is the one
    warning nothing else can produce: every player-level check needs to know who is playing, and
    a later elimination round does not have names yet.
  - **VENUE-LATE** — a semifinal, a final, or 80-and-over play away from the host site.

  The report is a `td-report/v1` document and it is **deterministic**: the same schedule prints
  the same report, so two runs can be diffed against each other. **It grades against the couriered
  documents** — `td-constraints/v1` and the courts & days — so the numbers it holds you to are the numbers
  you set in Setup, never the tool's own defaults.

  *One adapter, both sides: `scheduled_from_result` is the same function the harness grades with
  (`tests/cui5_views.py` part D holds them together). There is no second copy to drift.*

### Step 6 — Produce the deliverables
**⛔ ELICIT — your action for this step IS the tool call. Call the elicitation tool with the options below, then end your turn. Do not run any code, do not write a prose question, do not pause silently — those all count as skipping the step.** *"Generate the deliverables?"*
- **`Draw sheets`** → run:
  ```python
  render_all(b["cfg"], r, b["seeds"], out="outputs/wwtc_draw_sheets.html",
             locked_day_shifts=b["locked_day_shifts"], roster=b["players"])
  ```
  and publish the HTML as a private artifact, handing over the link (7.0; fallback: open the
  `outputs/` file in a browser) — one sheet per division (brackets with byes as walkovers;
  round-robin grids), each match labeled day / time / location (no court number; court is a
  day-of ops decision). **Pass `locked_day_shifts=` and `roster=` — both are optional with a
  default of "off", so a call that omits them renders sheets with no change marks and no
  ratings, silently, on the one lane the TD actually sees.** `locked_day_shifts` puts the amber
  mark on the rounds a locked final moved; `roster` puts each player's rating beside their name.
  The sheets read the schedule **as it now stands** (`r`, not `b`), so a substituted player shows
  on the draw as the incoming one. If the run also produces the 36x24" PDF
  (`render_all_pdf`), pass it the same two arguments — the two output paths must never disagree
  about who is on the draw. The TD's reference for the draw itself; **the change list is the
  re-enter page below.**
- **`Re-enter at the desk`** → run:
  ```python
  render_rekey(b["cfg"], r, locked_day_shifts=b["locked_day_shifts"],
               out="outputs/wwtc_re_enter.html")
  ```
  and publish it the same way. **The one deliverable that says exactly what to key into
  Tournament Desk** — every hand-edited slot, every substituted player and every round a locked
  final moved, grouped one draw at a time, with **what the desk currently holds beside what it
  should become**. That second column is the point: the page is often worked by someone who was
  not there when the changes were made, and it is what lets them tell a change already entered
  from one still pending. It is a printed checklist, not an import file. A run with no edits
  prints **"Nothing to re-enter."** and nothing else.
- **`Per-player CSV`** → run `write_csv({**b, "result": r}, "outputs/wwtc.csv")` — every export
  field plus each player's first scheduled match (day / time / location / opponent). **The
  `{**b, "result": r}` is load-bearing (REVIEW-1 / D3): `write_csv` reads `build_result["result"]`,
  and passing bare `b` hands it the UNEDITED base build — the wall sheet (rendered from `r`) and
  the player's handout then disagree about any hand-edited match. Never "simplify" this back to
  `write_csv(b, …)`. `write_csv` returns `(path, n_rows)` — **re-confirm coverage here**
  (REVIEW-1 / D8): compare `n_rows` against `b["reconciliation"]["counts"]["scheduled"]` and
  say in plain words whether the two counts agree ("1,066 on the schedule, 1,066 in the player
  file. Agree."); a disagreement here is the same stop-and-look as Step 4's.
- **`Run-of-play sheets`** *(8.0 / OI-20)* → run:
  ```python
  rop = schedule_views.render_run_of_play_html(schedule_views.run_of_play_by_court(r),
                                               tournament=b["cfg"].tournament_name)
  ```
  **Pass `tournament=` — it is the year on the sheet.** The name comes from the couriered
  courts & days, so the sheet carries the tournament the TD actually set up. Omitted, the sheet claims
  no year rather than guessing one.
  and publish the HTML as a private artifact, handing over the link (fallback: write it under
  `outputs/` and open it in a browser). **One sheet per site and day**, matches in start order,
  with the division, the round and who is playing — the sheet the desk posts on the morning.
  There is **no court column, and that is deliberate**: courts are assigned at the desk on the
  day, so a column of blanks would invite someone to read the sheet as the court assignment. It
  prints one site-day per page on letter paper.
- **`Player schedules`** *(8.0 / OI-20)* → run:
  ```python
  byp = schedule_views.render_by_player_html(schedule_views.schedule_by_player(r),
                                             tournament=b["cfg"].tournament_name)
  ```
  and publish it the same way. **One block per entrant** — every match they are in, in play order,
  with the day, the start, the site, the division, the round, and on a doubles line **their
  partner named as their partner** rather than mixed in with their opponents. This is the handout
  a player is given; it prints one player per page. Both sheets read the schedule **as it now
  stands** (`r`, not `b`), so hand edits from Step 5 are on them.
- **`Exceptions list`** → run `write_exceptions_csv(b, "outputs/wwtc_exceptions.csv")` — the
  entered-but-not-playing list: one row per person-division entry that is **not** in a printed
  draw, with the reason and the desk's own words. The other half of the per-player CSV: that
  file answers *"when do I play?"*, this one answers *"why am I not on it?"*. Report the closed
  accounting from `b["reconciliation"]["counts"]` — entries = scheduled + exceptions — and say
  the two numbers out loud; a non-empty exceptions list is the expected result, never a fault.
  Rows marked **Needs a look** are the ones to raise with the desk: an unresolved status string,
  or someone the desk marked `Selected` who is in no bracket at all.

> **Paths:** any writable path works — the writers create the target directory themselves. A
> session-local `outputs/` is the default suggestion (git-ignored, so run surfaces with commit
> hooks stay clean); writing outside the repo is equally fine. Adjust to the surface's download
> location if it has one.

---

## What "done" looks like

`wwtc_draw_sheets.html` you can open and print: one sheet per division. Reference run on the real
2026 field (canonical courts & days): **51 division sheets, 760 matches placed, 275 byes, 0 unplaced,
0 conflicts**, deterministic, in ~1–2 seconds. Optional: the per-player CSV and the edit loop.
*(A schedule carrying live conflicts after hand edits leads the set with a RULE CONFLICTS
sheet — REVIEW-1 / D2. That sheet on a printout is a stop, not decoration.)*

---

## Standing procedures (Operator-adopted, REVIEW-1 8/7 — they replace code; skipping one is a finding)

1. **After any finals-board editing: rebuild and READ THE UNPLACED COUNT before anything
   prints.** (Measured: all 50 finals dragged onto one day → 725 placed, 35 unplaced, ok
   False — the board lets you draw a layout the engine cannot honour.)
2. **After any setup change or any change the TD makes: regenerate the Edit console from the
   CURRENT result — `editor_plan(r, …)` with the `r` that `apply_schedule_edits` just returned,
   never `b["result"]` — and keep editing in the new one.**

   **Every block of changes is applied to the ORIGINAL schedule, never on top of the block
   before it** — so a block has to carry every change made so far, or the ones it leaves out
   quietly come undone. *(That one sentence is the whole reason this procedure exists: in the
   2027 mock run a second paste carrying one correction erased four moves and a substitution,
   and the set went to print with a player the director believed he had taken off it — D2.)*

   A console regenerated from the current result now does the carrying for you: it opens
   **already holding the earlier changes**, they are listed in *Changes to re-enter*, and the
   counter beside **Save my changes** reads *"N changes in this block"*. **Read that number
   before couriering the block: it is the total made this run, not just the new ones.** A
   console generated from the base build instead would emit a block that looks perfectly
   legitimate and is missing everything done before it.

   Every console generated by this build is stamped with the schedule's own id and stamps every
   block it emits. **A block stamped for a different schedule — or stamped for none, which is
   what a hand-written one is — is refused whole: nothing in it is applied**, and the refusal
   names both ids and says to regenerate the console. A stale editor also carries stale cards.
3. **After the build: list any finals sharing an exact date-time and check the draws for a
   player reachable in both** — about 15 minutes. (Covers the two-reachable-finals case the
   conflict guards cannot see until players are known.)
4. **Never hand-edit a courier document; shipped consoles only.**

   **AND PERSIST ONE AS AN EXACT BYTE COPY OF THE PASTE — written from the paste itself, never
   retyped, re-keyed or reconstructed — and check the saved copy against the paste before anything
   reads it.** *(STOP-1, off the 8/29 run's OI-C. Measured 2026-08-29: a session hand-transcribed
   the first `td-setup/v1` it was given instead of copying it — one added division vanished and
   another was written as 12 teams / 16 draw where he had said 5 / 8. It was caught before any
   engine call and re-saved field for field, so nothing downstream was computed on it, but that
   was luck and a careful reader, not a rule. This procedure forbade hand-EDITING a courier
   document and said nothing at all about how to SAVE one.)*

   **⚠ THE ONE INLINE LANE, AND IT IS ONE FIELD WIDE** *(STOP-1, Operator ruling 2026-08-30, off
   the 8/29 run's OI-3).* For a **single named field** of the last couriered `td-setup/v1`, and
   **only on his explicit instruction**, the session may derive the new document itself instead of
   sending him back to the console for one number. What this procedure protects was never the
   arithmetic — a session can copy a document and change one field correctly. It protects the tie
   between **what he sees on the screen and what priced his week**: edit a block silently and his
   Rules tab still reads 70 while the court answer was computed at 80, with nothing on any surface
   recording the gap. So the lane exists, and all six obligations below bind:

   1. **The couriered original is kept untouched**, written to `outputs/<run>/_session/` before
      anything is derived from it.
   2. **The new document is DERIVED from that file by changing that one field — never retyped.**
      (This is the verbatim rule above, applied to the derived copy.)
   3. **The edit is read back in plain words and he confirms it BEFORE anything uses it** — the
      field, the value it had, the value it will have, in his own terms and not in the block's.
   4. **A `_session_edit` record is written onto the document itself**, carrying: that it is
      session-derived and not couriered · the instruction that authorised it and its date · the
      document it was derived from · the field · both values. Invisible is the failure mode, and
      this record is what makes the edit visible in January.
   5. **It goes through the same reader a couriered document would, with no bypass** — `_check_setup`,
      which `finals_plan` and `build_from_setup` both call, so obligation 6's re-run IS the
      validation. (Measured 2026-08-29 on the adjacent lane: a `_session_edit`-marked
      `td-finals-map/v1` was put through `finals_plan.finals_map_from_doc`, the one sanctioned
      unwrapper, and **accepted** — 56 divisions read, the moved division at its new day. An
      unknown top-level key rides through; it disturbs no validation.)
   6. **S-1 §1-E5 stands, unchanged and unweakened.** A derived setup invalidates `plan` exactly as
      a couriered one does, so **Steps 2 and 3 re-run before Step 3.5 or Step 3.6 are used again.**
      This lane changes who types the document. It changes nothing about what a changed document
      invalidates, and the re-runs were never the part he was objecting to.

   **More than one field goes back to the console.** The lane is one field wide on purpose:
   one field is what obligation 3's readback can carry without turning into a form he has to
   proof-read.
5. **The data directory holds only the CURRENT year's PDFs.** The retired PDF resolver took
   the alphabetically first match — proved: a stray `25_…` file made it return last year's
   draws silently. The struck module keeps this rule alive for anything else that globs.
6. **Proof printed seeds against the desk's draw.**
7. **THE SHIPPED CONSOLE HTML IS THE AUTHORITY ON WHAT THE DIRECTOR CAN SEE AND DO** — not the
   Python, not the contracts, not this runbook's own prose (S-1 §1-E6). A field can exist in the
   DOM, ride the contract and be read by the engine while being **invisible on screen**; a label
   can say something quite different from what the key is called. Before telling the Operator or
   the director that a control exists, open the shipped HTML and check. Three statements made in
   one rehearsal were wrong for exactly this reason, all three verifiable in the repo:

   | what was said | what the screen actually shows |
   |---|---|
   | a Level-1 Mixed field he can fill in | the `ml1` section is `display:none` — SETUP-3 retired the tick-box; the key still rides, the field does not exist |
   | a matches-per-day **limit** | the label is **"Flag past"**, hint *"Flag a day once it passes this many matches"*, in a section titled *"Set Warnings for Finals Map Editor"* — a warning threshold, not a limit, and hidden besides |
   | an instruction to delete travel rows | a stale travel key **renders no row at all** — there is nothing on screen to delete |

---

## Gotchas

- **Three courier stops, in order:** `td-setup/v1` (Step 1) → `td-finals-map/v1` (Step 3) →
  `schedule-edits/v1` (Step 5, optional). Each is a paste from a human; no file reads, no engine
  calls from any console (B-1).
- **`td-setup/v1` no longer carries `finals_map`** — a console emitting one is stale;
  `build_from_setup` and `finals_plan` reject it loudly (F7).
- **The finals map is the ENGINE's draft first.** The TD's first contact is the computed
  finals-anchored layout — never an empty grid. A zero-drag emit ≡ the draft (a verified fixed
  point). The couriered map is validated loudly: an unknown division name, an out-of-window
  date, **or a structurally infeasible pin (a finals day too early for the division's rounds —
  6.2)** is an error, not a silent no-op or a silent slide. The editor refuses infeasible
  drops at drag time, naming the earliest feasible day.
- **Finals always bind placement — including round-robins (F7-4).** Locked days honored exactly;
  RR-badged divisions bind all of their `— Group N` draws (last round end-aligned on the
  chosen finals day); day moves (Option A) reported; 0/0 holds.
- **Byes** are read from the result's `byes` field (`_assemble_result`), not from any decisions doc.
- **Caps bind only on known players** (RR, round 1, bye-advanced).
- **Format is the draw PDF's** (elim vs round-robin per printed structure). **Ingest has no
  review step (7.0):** the draws load exactly as printed, and a malformed or unreadable file
  raises a clear error naming the problem — nothing ingests silently. If an ingest error
  surfaces, fix the source file and re-run; never work around the error.

---

## Appendix — single-level runs

- **One level only:** use `wwtc_pipeline.build(level="2", slate=…, constraints_doc=…,
  assigned_days=…, finals_map=…)` — note `build` takes a bare `{event: date}` finals_map,
  whereas the guided lane's `build_from_setup(setup, finals=…)` takes the couriered
  `td-finals-map/v1` doc.
