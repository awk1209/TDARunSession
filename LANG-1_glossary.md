# LANG-1 · The glossary — for Operator sign-off

**What this is.** The one-page vocabulary ruling that opens A7c (LANG-1), and the first piece of
A7 work of any kind. It fixes the word the tool uses for each concept on every TD-facing surface.
It is a **decision, not a build** — nothing in this file is code, and no code changes until it is
signed off. The glossary precedes REKEY-1 (A7a) because REKEY-1 mints new TD-facing surfaces (the
rekey page, the amber legend) that must be born in the ruled vocabulary.

> ## ✅ RULED — Operator, 2026-08-07: options **1 · 1 · 1 · 1**
> 1. **"Cadence" becomes "two rounds in one day"** — *not* "Event Order-of-play", which collides
>    with this glossary's own day-shape wording and with the sheet a TD already calls his order of
>    play. "The day's order of play" is therefore free, and is the ruled phrase for the
>    singles → mixed → doubles rule.
> 2. **Two locked words: "locked day"** (a final held to a date) **and "locked slot"** (a match
>    held to a court and time). "Pin" is retired from every TD-facing surface.
> 3. **The conflicts sheet stops naming matches by an internal id.** Division + round + players,
>    with the console's `winner of R1 M2` fallback for undecided rounds. Carries the engine
>    sign-off flag — engine-adjacent strings, wording only.
> 4. **The report's code words leave the printed page and stay in the JSON.** Severity renders
>    **Must fix / Check this / For information**; `td-report/v1`'s `breach`/`warn`/`info` values
>    are untouched.
>
> §3 below is the record of how each was decided and is retained verbatim. §5 is the full
> screen-by-screen sweep the ruling authorised.

Owns the vocabulary half of **N4 · N5 · N6a + the general language rules** (PLAN §3, A7).
After sign-off the LANG-1 sweep is mechanical and gets its own brief.

---

## 1 · Measured — re-measured at drafting, 2026-08-07, on `18df28c`

Method: string literals only, never comments. `.py` via `ast` with docstrings excluded; `.html`
visible text plus JS/HTML string literals with `//`, `/* */` and `<style>` stripped; the runbook
line-by-line. Script: `scratchpad/lang1_prose.py` (drafting artifact, not committed).

**a · The RULE CONFLICTS sheet — the page that leads the printed deliverables in red.**
`scheduler_multi.validate_multi` carries **17 conflict-string templates**, each opening with an
internal code word: `CAPACITY EXCEEDED` · `PERSON CONFLICT` · `REST <…>` · `TRANSIT` ·
`DEPENDENCY` · `EARLIEST START` · `DAY WINDOW` (×3) · `LOCATION HOURS` · `VENUE RULE` (×2) ·
`MATCH CAP` · `LINEAGE REST` · `FINALS FLOOR` · `DAY BAND` · `DAY SHAPE`.

**14 of the 17 print an internal match id** (`E36-R1-M14` shape). Measured against every other
TD-facing output, **that id appears on none of them**: `draw_sheets.py` uses it as a lookup key
and never draws it, `schedule_views.py` and `csv_export.py` never carry it, and
`schedule_editor.html` holds it in `data-mid` (4 uses) without ever rendering it as text. So a
director reading the red page cannot find the named match anywhere in his paperwork.

On the committed 2026 run, 2 conflicts printed. Verbatim, as they reached paper:

```
RULE CONFLICTS — resolve before anything prints
2 rule breaches recorded on this schedule after hand edits. Fix the edit or accept it
knowingly — this page appears only while the list is non-empty.
  •  DAY SHAPE: E36-R1-M14 (doubles) starts 11:00 on 2026-01-24, before an earlier-kind
     match of that day is under way (singles -> mixed -> doubles)
  •  DAY SHAPE: E37-R1-M6 (doubles) starts 11:00 on 2026-01-25, before an earlier-kind
     match of that day is under way (singles -> mixed -> doubles)
```

**b · The pre-publication report** (Step 5.5, MANDATORY). **10 finding sections**, each titled
with its internal code followed by a plain heading already written for it —
`REST-XLEVEL — Rest floor — matches too close together`. Severity renders `[BREACH]` / `[WARN]` /
`[INFO]`. The summary line reads `760 stamped matches · 1066 certain player commitments`.
Committed field: 4 findings (1 breach, 1 warn, 2 info).

**c · The pin warnings (N5).** 3 templates. **All three are in `wwtc_pipeline.py`
(`:717`, `:729`, `:797`) — not `master_schedule.py`, which N5 records as the source.**
`master_schedule.py` carries "pin" in comments only and emits 0 warning strings. Cite corrected
here; N5's fix shape is unaffected.

**d · The Step-4 readback** — the Operator's recorded anti-pattern, verbatim from
`WWTC_test_run_starter.md:462-469`, as printed to the TD:

```
L2 name-match rate: 100.00%  ingest warnings: 0
coverage: reconciliation counts 1066 scheduled entries; the per-player CSV will carry
1066 rows -> MATCH
```

**e · Jargon inventory across TD-facing surfaces: 261 prose hits over 22 terms.** Of those,
**155 are runbook lines** (which instruct the assistant more often than they speak to the TD) and
**106 are code-emitted strings or console text**. The 106 is an **upper bound** on the sweep's
surface, not its work-list: it includes `constraints.py` validation messages a TD never sees on a
clean run, and one embedded sample-JSON blob in `schedule_editor.html`. The sweep's hard targets
are the enumerated ones — 17 conflict strings, 10 report codes, 3 pin warnings, the Step-4
readback. Counts outside the runbook, highest first: `slate` 23 · `unplaced` 21 · `schema names`
10 · `transit` 9 · `day shape` 7 · `stamped` 7 · `pin` 6 · `band` 5 · `feeder/lineage` 4 ·
`cadence` 3 · `escape` 2 · `seed drop` 2 · `reconciliation` 2 · `earlier-kind` 1 · `spill` 1 ·
`emit` 1 · `courier` 1.

---

## 2 · The glossary — proposed, sign off as a block

Everything in this table is proposed as-is and needs no discussion unless you disagree with a
row. The four rows that carry a genuine choice are pulled out into §3 and are **not** settled here.

### Words that change

| Today | What the TD sees now | Proposed word | Where it appears |
|---|---|---|---|
| pin · pinned · pin a final | "the TD's finals pin overrides the desk's published day" | **locked day** — see §3.2 | `wwtc_pipeline.py` ×3 · finals-map editor · runbook ×8 |
| pinned cascade | "the pinned cascade places it 2026-01-28" | **the rounds behind it** | `wwtc_pipeline.py` ×3 |
| earlier-kind · later-kind | "before an earlier-kind match of that day is under way" | **banned** — name the kinds: "ahead of that day's singles and mixed" | `scheduler_multi.py:1999` (conflicts sheet) |
| day shape | "DAY SHAPE:" leading a conflict line | **the day's order of play** | conflicts sheet · `constraints.py` ×4 |
| spill · assigned-day spill | "surface the spill list" | **moved to another day** | runbook ×9 · console ×1 |
| escape · recorded escape | "a recorded escape" | **recorded exception** | console ×2 · reporter |
| unplaced | "0 unplaced" · "Leave unplaced (handle manually)" | **not scheduled** | console ×18 · runbook ×15 · engine ×3 |
| slate | "Court capacity against the measured slate" | **courts & days** | 23 outside the runbook |
| stamped match | "760 stamped matches" | **scheduled matches** | report summary · `wwtc_pipeline.py` ×4 |
| band · day band · BAND-3EV | "after the 14:00 band" · "band move-list" | **latest start** | report ×3 · conflicts sheet · console ×2 |
| feeder | "starts before feeder E12-R1-M5" | **the earlier match** | conflicts sheet · console |
| LINEAGE REST | "LINEAGE REST: … less than 180 minutes after a feeder's start" | **rest after the last round** | conflicts sheet |
| DEPENDENCY | "DEPENDENCY: … starts before feeder …" | **out of draw order** | conflicts sheet · console |
| transit | "transit minutes" | **travel between venues** | console ×9 · runbook ×2 |
| name-match rate | "L2 name-match rate: 100.00%" | **names matched** | Step-4 readback |
| reconciliation counts · MATCH/MISMATCH | "coverage: reconciliation counts 1066 … -> MATCH" | plain sentence — see §3.4 | Step-4 readback · runbook ×3 |
| seed drops | "The seed drops (the default)." | **seed dropped** | console ×2 · runbook ×1 |
| non-drawn | already reads "Entered, but not in a draw" | **keep as is** — the console already ruled it at OI-53 | console |
| emit · couriered block | "the emit", "courier stop 1" | **the block to copy** / **paste it across** | runbook ×32 (assistant-facing; TD hears it at the three stops) |
| printed draw | "already in the printed draw" · "a person in a printed draw with no match" | **retired — say which draw:** **Raw Draw** or **System Draw**, per §2a | RPT-2 sweep, 2026-08-09 — measured below |

### 2a · Raw Draw and System Draw — added 2026-08-09 (RPT-2, 8/7 note 10)

**Why the pair exists.** "Printed draw" named two different things and the tool used it for both.
Sometimes it meant the file the Tournament Desk produced — the document this tool ingests and
never argues with. Sometimes it meant a page this tool itself rendered. When a substitute panel
says a player is "already in the printed draw" it means the first; when the report talks about a
pairing that "reached the printed draw sheets" it means the second. A director reading the two
sentences has no way to know they are about different pieces of paper, and one of them is the
authority over the other.

| Term | What it means | Where it is right |
|---|---|---|
| **Raw Draw** | The ingested Tournament Desk export — **the truth**. The tool reads it, never writes it. | Anything about who is entered, who is drawn, seeds as printed, the format a division plays |
| **System Draw** | Any draw surface **this tool renders** — the draw sheets, the bracket view, the plotter PDF. | Anything about what the tool prints or shows |
| ~~printed draw~~ | **RETIRED** — it names both and distinguishes neither. | Nowhere |

Bare **"draw"** stays, and stays kept vocabulary (§5.9): it is the right word for the abstract
concept — *a 32-draw*, *the main draw*, *single elimination*. The pair above is only for when the
sentence is about a **document**, where the reader has to know which one.

**Sequencing (note 10, satisfied by construction):** this pair lands before DESK-1 mints its
entry-status sentences, so DESK-1 is born in the ruled vocabulary rather than swept afterwards.

**Measured at RPT-2's ship, 2026-08-09 — whole-word "draw", `grep -oiw draw`, per file:** runbook
**19** · this glossary **18** (the brief's 18/12 were taken before session 1 and do not
reproduce; state the method, because the two counts are not comparable without it). **"printed
draw" outside `archive/`: 41 files.** Swept and left, both named, in RPT-2's ship commit — the
short version is that the two consoles carry **4 TD-facing occurrences** that are outside RPT-2's
file list and are recorded for CONSOLE-2 and SETUP-2 rather than changed here.

### Words that stay — real tennis vocabulary the director uses daily

**bye · walkover · seed · draw · round robin · consolation · quarterfinal · semifinal · final ·
division · court · venue · entry list · default · round.** These are not jargon; replacing them
would make the tool sound like it does not know the sport. `bye` appears 30×, `walkover` 3× —
both stay untouched.

### Load-bearing names that are never translated (CLAUDE.md standing rule)

The `td-` schema names (`td-setup/v1`, `td-editor-plan/v1`, …), the `TD`/`ST` file suffixes, file
names, function names, config keys and commands keep their exact spelling everywhere. Where one
must appear on a TD surface it is glossed on first use, never renamed. **The 10 report codes and
the 17 conflict codes are not in this class** — they are display labels the tool invented, and
§3.3 and §3.4 rule on them.

---

## 3 · The four decisions

### 3.1 · What replaces "Cadence"

**The situation.** The general language rules say "Event Order-of-play" replaces "Cadence". The
Cadence check means one specific thing, measured: a division playing two rounds on the same day
(`Men's 45 singles plays 2 rounds on 2026-01-31`). Separately, this glossary proposes calling the
singles → mixed → doubles rule **the day's order of play**. If both take the phrase, two
different rules end up with one name — and "order of play" already means something else to a
director: the daily schedule sheet he pins to the wall.

1. **"Two rounds in one day."** Names exactly what the check reports. Frees "order of play" for
   the day-shape rule where it fits. Cost: departs from the phrase you wrote. If wrong: a heading
   that is blunt but never ambiguous.
2. **"Event order of play"**, as written. Cost: collides with the day-shape wording, and with the
   sheet the TD already calls his order of play. If wrong: two unrelated warnings read as the same
   family, and he goes looking for a schedule sheet.
3. **Keep "Cadence" with a first-use gloss.** Cost: keeps a word no director uses. If wrong:
   nothing breaks; it just stays opaque.

**The trade:** your phrase reads more professional; "two rounds in one day" is unmistakable.

**Recommendation — option 1.** The check's own sentence already says "plays 2 rounds on
2026-01-31"; the heading should say the same thing rather than a second, grander name for it.

### 3.2 · One "locked" or two

**The situation.** "Pin" is two different things in this tool. The TD pins a **final to a day** in
the finals-map editor (`wwtc_pipeline.py`'s three warnings). He also pins a **match to an exact
day, time and court** in the Edit console (`scheduler_flow.py:90`, "Pin to a specific slot").
"Locked day" covers the first and not the second.

1. **Two words: "locked day" for a final's day, "locked slot" for a match held to a court and
   time.** Cost: two terms to learn. If wrong: he confuses which one he set.
2. **One word, "locked", disambiguated by the sentence.** Cost: the warning must carry the
   distinction in prose every time. If wrong: he thinks he locked a day when he locked a court.
3. **Keep "pin" with a first-use gloss.** Cost: keeps the word you flagged. If wrong: nothing
   breaks.

**The trade:** two words cost a little learning and remove an ambiguity that costs a wrong edit.

**Recommendation — option 1.** The two actions have different consequences — one moves a whole
division's rounds, the other moves one match — so they should not share a name.

### 3.3 · The conflicts sheet names matches by a code nobody can look up

**The situation.** This is the red page that leads the printed draw sheets. Measured: 14 of its 17
line types name the match by an internal id like `E36-R1-M14`, and that id prints on no other
output the TD holds — not the draw sheets, not the run-of-play, not the player handouts, not the
CSV. On your own run, both printed conflicts named matches this way. The page tells him two
matches are wrong and gives him no way to find them.

This is the one item here that is more than wording, so it is your call whether it rides in
LANG-1 or waits.

1. **Replace the id with division, round and players** — "Men's 55 & over doubles, Round 1 —
   Heine / Straley v Daly / Shea". Undecided later rounds fall back to what the console already
   says: "winner of R1 M2 v winner of R1 M4". Cost: touches `validate_multi`'s strings, which are
   engine-adjacent and pinned by tests. If wrong: a conflict line reads long on a crowded page.
2. **Keep the id and add division, round and players after it.** Cost: same work, longer lines.
   If wrong: the page looks more technical than it needs to.
3. **Wording only — leave the id.** Cost: none. If wrong: the red page stays unusable, and the
   next run repeats exactly what yours did.

**The trade:** option 1 makes the page actionable and makes the same string more useful in
diagnosis too, since division-plus-players identifies a match uniquely; option 3 is free and
leaves the defect standing.

**Recommendation — option 1.** The sheet exists for one reader and currently speaks to nobody.

### 3.4 · The report's 10 code words and the Step-4 readback

**The situation.** Every section of the mandatory pre-publication report is titled with an
internal code and then a plain heading that was already written for it —
`REST-XLEVEL — Rest floor — matches too close together`. The plain half is good; the code half is
noise on paper. Same shape at Step 4, where the readback says `-> MATCH` instead of a sentence.

1. **Drop the code from the printed render; keep the plain heading. The JSON keeps the code
   unchanged.** Step 4 says "1,066 players on the schedule, 1,066 rows in the player file — they
   agree." Cost: near zero — the plain headings exist. If wrong: an engineer reading a printed
   report loses a grep handle, and still has the JSON.
2. **Keep both.** Cost: none. If wrong: the page keeps reading like a log file.
3. **Rename the codes themselves.** Cost: touches `td-report/v1` values and every pinned test.
   If wrong: a contract change for a cosmetic gain.

**The trade:** option 1 is the cheapest real improvement on this page and changes no contract.

**Recommendation — option 1.** The severity labels change on the render only for the same reason
— `[BREACH]` / `[WARN]` / `[INFO]` become **Must fix** / **Check this** / **For information**,
while the JSON's `breach` / `warn` / `info` values stay exactly as they are.

---

## 4 · What sign-off unlocks

On your ruling, the LANG-1 brief is drafted against this glossary and the sweep is mechanical:
the runbook's binding plain-English manner at the top plus the step readbacks rewritten, the pin
warnings restated as chose-then-happened, "earlier-kind" gone from the conflict strings, and the
Cadence rename carried to every TD-facing surface. The sweep carries the engine sign-off flag —
wording only, engine-adjacent files — and the string-pinning harnesses (`fix1_guards`,
`cui5_views`, `rpt1_report`, `review1_conflict_sheet`) move with the code.

**Boundary, unchanged from PLAN A7:** OI-54 (the typo warning naming the nearest real division)
stays an ordinary open item. LANG-1 touches the neighbouring sentence; pulling it in costs about a
line. Your call at brief approval, not here.

---

## 5 · The screen sweep — every word on every surface

**Authorised by the ruling above, 2026-08-07. Method: the screens, not the code.** The three
archived courier blocks were replayed function-level (`build_from_setup` → `apply_schedule_edits`),
reproducing the run exactly — **760 placed · 275 byes · 0 unplaced · 2 conflicts**, both conflicts
byte-identical to the archived pair. Every surface was then regenerated from that result and
**driven in headless Chromium**: each page loaded, every `<details>` opened, every tab clicked,
every `<select>`'s options enumerated, a singles card and a doubles card selected so the side
panels populated, "Where can this go?" answered, and the visible-text tree walked after each
gesture so text that exists only behind a click was captured. Text still in the DOM after every
gesture is listed separately. Drafting artifacts: `scratchpad/build_surfaces*.py`,
`sweep_screens.py`, `sweep_editor2.py`; dumps under `scratchpad/screens/`.

**Surfaces swept:** Setup console · Edit console (all six views: Grid · Bracket · By day · By
player · Withdrawn · Flags, plus the four side panels) · draw sheets (52 sheets incl. the RULE
CONFLICTS page) · run-of-play sheets · player schedules · the pre-publication report · the
exceptions CSV · the per-player CSV · the runbook's spoken readbacks.

> ### ✅ HOUSE RULE — Operator, 2026-08-07: **ultra-concise**
> **Every replacement string cuts every word that is not doing work.** The register is desk
> shorthand, not prose: *"Withdrawn not SUB"*, not *"Can't be used as a substitute — their
> withdrawal isn't clear"* (the Operator's own example, and item 29 below adopts it verbatim).
> A label is 1–3 words. A warning is a fact and a consequence, nothing else. Help text that
> explains the mechanism is deleted, not shortened.
>
> **This binds the LANG-1 sweep and every TD-facing surface REKEY-1 and CONS-1 mint after it.**
> It does not bind briefs, `PLAN.md`, commit messages or code comments, which keep their full
> technical register.
>
> **Two already-ruled strings were tightened under this rule and are flagged for confirmation:**
> the §5.8 rekey label (*"Changes to re-enter at the desk"* → **"Re-enter at the desk"**) and
> ruling 4's severity labels (*"Check this" / "For information"* → **"Check" / "Info"**;
> **"Must fix"** is unchanged). Say so if either tightening goes too far.

**One finding corrected from §1a by the sweep, in the tool's favour:** the internal match id
**is** present on every Edit-console card — in a `div class="mid"` that computes to
`display: none`. It is deliberately hidden and never reaches the screen, so §1a's claim stands
and is now stronger: the id is suppressed everywhere the director looks **except** the one red
page that leads his printed deliverables.

**Also worth recording: most of these surfaces are already good.** The player handouts, the
run-of-play sheets and the Setup console's "What the tool does on its own" panel are written in
plain English throughout and need almost nothing. The problems cluster in four places — the
report, the conflicts sheet, the pin warnings, and a scatter of engineer phrases left in help
text.

### 5.1 · Setup console

| # | Now | Proposed |
|---|---|---|
| 1 | `td-setup/v1` badge beside the page title | *(delete the badge — the name stays inside the block)* |
| 2 | Load a different slate / start over | **Load another setup** |
| 3 | Section label (screen readers): Slate | **Courts & days** |
| 4 | Transit between locations | **Travel between venues** |
| 5 | "Minutes of travel between venues. Emitted as sorted "A\|B" keys so the engine matches them. Leave blank for none." | **"Minutes between venues. Blank = none."** |
| 6 | **MHCC\|ORLP** | **MHCC ⇄ ORLP** |
| 7 | ▲ tooltip: "Move this venue up — the engine fills venues in this order, and rule 38/39/40's "main site" is whichever venue sits at the top" *(1 of 2)* | **"Move up. Venues fill in this order. Top = main site."** *(also N2's fix)* |
| 8 | Venue id | **Code** |
| 9 | "A venue-day that names its own hours is held to them: the engine will not place a match outside a venue's stated window." *(1 of 3 "the engine" sentences)* | **"Nothing is placed outside a venue's hours. Blank = tournament hours."** |
| 10 | "— reported, not scheduled: the engine does not restrict late play to lit courts" | ~~**"— reference only, not enforced"**~~ — **REMOVED 2026-08-08 (Operator), and the row is kept as the record of why.** Both wordings said the lit figures change nothing. Rule 48 (LIGHTS-1) made them a hard placement ceiling, so the replacement was as untrue as the original. The filled-in hint now renders nothing; the blank-state hint ("— blank = not known. Affects nothing.") is untouched and still exactly true. `setup_console_golden` item 10 is INVERTED to `absent`, so the sentence cannot come back unnoticed. |
| 11 | Start-to-start (min) · "start-to-start rest" · "· staging on · locals-early on" | **Between starts (min)** · **rest** · **· multi-division early · locals early** |
| 12 | Match-day caps · Cap mode · Flat cap | **Matches per day** · **Count by** · **Limit** |
| 13 | Placement policy — "morning / later staging" | **Filling the day** — **"who plays early"** |
| 14 | "age-based earliest slot (AVOID-3)" | **"earliest start by age"** |
| 15 | "A player is local iff their export city is in this set (case-insensitive)." | **"Local = their entry-list city is here. Case ignored."** |
| 16 | "…marked as commuting on the edit console's cards. Display only — it changes no scheduling decision." | **"Shows as commuting on their card. Label only — changes nothing."** |
| 17 | Day load | **Busy-day warnings** |
| 18 | Browser tab: Run Setup Console | **Tournament setup** |
| 19 | "Seeding groups … are a property of the draws you print." | **"Seeding groups come from your printed draws."** |

### 5.1a · Setup console — SETUP-3 renames, new strings and retirements (2026-08-21)

The §5.1 table above is the LANG-1 record and is not rewritten; this is the delta the setup-console
upgrade shipped. Every row was ruled by the Operator on 8/20 (SETUP-3 §3.4 · §3.7 · §3.9 · §3.10)
except where noted, and each is re-pinned in `setup_console_golden` in the same commit — a rename is
graded BOTH ways there, old string absent and new string present, so neither half can drift alone.

**Renamed**

| §5.1 row | Was | Now | Ruling |
|---|---|---|---|
| 11 | Section **Rest & recovery**, descriptor `rest` | **Rest Between Matches** *(section hidden — §3.9-2)* | §3.7 B1 |
| 13 | **Filling the day**, descriptor `who plays early` | **Early Match Preferences** | §3.4-2 |
| 14 | Descriptor `earliest start by age` | **Earliest Start by Age**, now the section TITLE *(section hidden — §3.9-2)* | §3.9-2 |
| 17 | **Busy-day warnings** | **Set Warnings for Finals Map Editor** *(section hidden — §3.9-2)* | §3.4-6, Operator's exact wording |
| — | **Locality** | **Local and Commuter Cities** | §3.4-3 |
| — | Baked-rules display | **Locked Rules** *(now its own view — §3.5/§6E)* | §3.4-7 |
| — | `Courts booked` | ~~**Courts Reserved**~~ — **RETIRED 8/21**, see below | §3.7 A1, superseded |
| — | `Club ceiling` | **Max Courts** *(contract key `physical_courts` — §3.1)* | §3.7 A2 |
| — | `remove venue` · `+ Add venue` · `split` | **Delete venue** · **+ Add a venue** · **Split** | §3.9-4 / §6C |
| — | `Untitled slate` | **Untitled tournament** | *Engineer, forced:* `slate` is a RETIRED term (§2) and the string moved from `<script>`, which the sweep strips, into rendered markup. |
| — | Locked Rules row 01: "from your **printed draws**" | "from your **Raw Draws**" | *Engineer, forced:* `printed draw`/`printed draws` were retired at §2a on 2026-08-09 and this table RENDERS. §2a assigns this exact subject — who is drawn, seeds as printed, the format a division plays — to **Raw Draw**. `rpt2_conflicts` D3 pins this screen at zero occurrences. |

**Retired as screen strings** (the capability stays — SETUP-3 §3.3 · §3.4-5 · §3.9-1 · §3.9-2 · §6F)

- Section titles **Rest Between Matches** · **Same-day finish** · **Level-1 Mixed divisions** ·
  **Set Warnings for Finals Map Editor** · **Earliest Start by Age** — hidden by one CSS rule.
  Their state, loaders, validation and emitted keys are untouched, so a saved document still
  round-trips verbatim; the words leave the screen, not the file.
- **Use the usual setup** · **Start empty** · **Use the usual rules** · **Reuse rules from another
  tournament** · *"Venues & days from another tournament (optional)"* — three load surfaces on two
  views became one panel behind the masthead. The SAMPLE prefill stays as the silent initial state.
- Every light-grey descriptor under a card or section title, console-wide (§3.4-8). The eight in
  §5.1 rows 11 · 13 · 14 and their five siblings go together.
- **+ Add day** · **Closed every day — add the days this venue is available.** — the day-token row
  and the capacity matrix's dashed cells open a day BY NAME now, so there is no day left to guess
  and no venue that can look closed without showing which days it is closed on.
- **Under lights:** / **from** — the row labels became the caps label **Lit · lights on**. The
  blank-state hint **"blank = not known. Affects nothing."** STAYS, and is load-bearing: blank
  means no ceiling, and a director who leaves it blank has to know that is an answer rather than
  an omission. (LANG-1 item 10's removed filled-in hint stays removed and stays inverted.)
- **Venues fill in this order. Top = main site.** — superseded by §6C's ruled header line, **The
  order is the fill order — the top club is the main site**. The ▲/▼ `title` attributes keep
  §5.1 row 7's ruled sentence unchanged.
- **Add two or more locations with ids to set inter-location transit times.** → **Add two or more
  venues with codes to set travel times between them.** — plain English, and it now uses the
  screen's own words (**Code**, **Travel between venues**) instead of `id`/`transit`/`location`.
- The status indicator (§3.7 A5) and the venue-card footnote line (§3.7 A3). `· last resort` leaves
  the third venue's tag (§3.7 A4).
- **THE VENUE HEADLINE ROW (Operator, 8/21)** — the band of oversized numerals under each club.
  **Courts Reserved** and **Mornings** go with it and are not re-homed: both were DISPLAY of values
  owned elsewhere (the capacity matrix; the day detail), which is why they cost nothing to delete —
  and why they were two of the four surfaces that drifted out of step at the 8/21 review. The round
  day tokens stay, on instruction. **Max Courts**, **Lit** and **Lights on** stay too, as CONTROLS
  in a compact settings line: they are inputs, not display, and that line is the only home for
  `physical_courts` (§3.1), `lit_courts` and `lights_on` (rule 48) — §3.6 requires the full control
  set on every venue. The blank-state hint **"blank = not known. Affects nothing."** moves with
  them, still load-bearing.
- **`Lit · lights on`** — the one label that sat over BOTH boxes. Split into **Lit courts** and
  **Lights on** on Operator instruction (8/21, option 1) because a reader could not tell which
  number was courts and which was a clock time, and given the sentence above. The hour list is
  floored at the start of play, so an impossible hour is off the menu; one arriving by paste is
  refused in words and never silently rewritten (§5a).

**New strings** (all four views; the Locked Rules table's 31 sentences are §3.5's approved text)

| Where | String |
|---|---|
| Masthead | **Load a saved setup** · **Build my setup** |
| Tabs | **Venues & Days** · **Rules** · **Locked Rules** · **Review & Build** |
| Venues & Days | **The order is the fill order — the top club is the main site** · **Main site · fills first** · **Overflow №n** · **Lit courts** · **Lights on** · **Courts by day** · **Reserved capacity · every open instant** · **The latest a match can begin is H:MM.** · ~~*"How many of this club's courts have lights, and when they come on. From that hour the club can only run as many matches at once as it has lit courts."*~~ **REMOVED 2026-08-24** (Operator: *"remove the helper text"*); `setup_console_golden` part U's pin is INVERTED to keep it off the screen. The RULE is unchanged — rule 48 still binds — and Locked Rules still states it. |
| Rules | **N rules apply on their own with no setting here — see Locked Rules.** *(N is counted from the one source array, never typed)* |
| Locked Rules | **Every rule the tool applies on its own — no setting controls these.** · **Search rules…** · **All · N** / **Invariable · N** / **Avoid · N** / **Nice-to-have · N** · **No rule matches that.** · **N of N shown** |
| Review & Build | **What you set** · **Your setup** · **The block your schedule is built from** · **Reset and start over** · **Copy — paste it back into the chat** · **Plus the N locked rules, which always apply.** |
| Load panel | **Load a saved setup** · *"Paste a saved setup here — the whole block you copied last time, or just its venues or just its rules."* · **Use this** · **Close** |

**One collision recorded, NOT resolved here — for the Operator.** Locked Rules row 20 is named
**Day shape**, and `day shape` is on §2's retired list as a report code word. The Operator approved
this table's console text on 8/20 and SETUP-3 §3.5 transcribes it verbatim; §1 of that brief makes
this glossary the string authority. The two collide. Rewriting approved copy is a scope decision,
so the collision is PRINTED by `tests/setup3_locked_rules.py` part A on every run and routed here
rather than patched quietly. No harness is red because of it — `rpt2_conflicts` D3 sweeps only the
retired PHRASES on this screen.

### 5.2 · Edit console

| # | Now | Proposed |
|---|---|---|
| 20 | "Men's 35 & over doubles **(elim)**" · "Women's 45 & over singles — Group 1 **(RR)**" — **all 51 options** (42 / 9) | **(knockout)** · **(round robin)** |
| 21 | Over-cap | **Over limit** |
| 22 | Hold (unplace) | **Hold (off schedule)** |
| 23 | Tab: Flags / "15 flags" — the panel it opens says "Worth a look (15)" | **Worth a look** *(tab matches panel)* |
| 24 | "— awaiting winner of R1 M4" — **43 cards** | **"— awaits winner, Round 1 match 4"** |
| 25 | "Mixed 80 & over doubles round 1: the TD's finals pin overrides the desk's published day 2026-01-25 — the pinned cascade places it 2026-01-26" — **6 of the 7 warnings** *(N5)* | **"Mixed 80 & over doubles final locked to a later day. Round 1: Jan 25 → Jan 26."** |
| 26 | "This card does not carry its team lineup (a later-round card), so a substitution cannot be recorded here." | **"Later round — players not known yet. Substitute on their Round 1 match."** |
| 27 | Changes to rekey / "No changes to rekey." | **Re-enter at the desk** / **"Nothing to re-enter."** *(§5.8, tightened)* |
| 28 | "5 division(s), 8 player(s)" | **"5 divisions, 8 players"** |
| 29 | "not a substitute — withdrawal unclear" | **"Withdrawn not SUB"** *(Operator's own wording, verbatim)* |
| 30 | "No clean swaps this day." | **"No swaps available."** |
| 31 | Header trail: "· grid ·", "· flags ·", "· bracket ·", "· withdrawn (58)" | **· Grid ·** · **· Worth a look ·** · **· Draw ·** · **· Withdrawn (58)** |
| 32 | Browser tab: Edit Console — schedule editor | **Edit the schedule** |
| 33 | *(nothing — following an issue card into another division left no way back)* | **`← Back to <division>`** — the arrow, the plain word, the division named in full; announced as **"Back to <division>"**. Shown only after a jump that changed the scope, beside the division picker. ISSUES-1, ruled 8/17 (D4 placement 1) |
| 53 | "Move blocked · **MHCC is full at 08:00 (9 courts)**. Card left in place — free a court first." / "Placement blocked · … Card stays in the Unplaced dock — free a court first." — the drop's own start time and one bare court count, on **every** capacity refusal | **"Move blocked · MHCC has 9 courts before 11:00 and they're all in use at 09:30. Card left in place."** — the sentence names **the instant that actually breached and the limit in force there**, which are two different clocks and were being conflated. A venue with one court count all day says **"MHCC has 24 courts and they're all in use at 11:00"**; a venue closed that day says **"WEST has no courts at 08:00"**, because "they're all in use" is a false statement about a venue that has none. The placement half is the same sentence ending **"Card stays in the Unplaced dock."** COURTS-1, ruled 8/17 (D1 option 1) |
| 54 | *(nothing — the Edit console had no lit-court data of any kind and refused nothing for the lights)* | **"Move blocked · MHCC has 7 lighted courts, after the lights come on at 16:00, and they're all in use at 16:30. Card left in place."** — the phrase **"lighted courts, after the lights come on"** is the pre-publication report's own ruled wording (`scheduler_multi.py:1966`), reused word for word so the screen and the printed page say the same thing about the same ceiling. The hour is dropped from the clause when it IS the instant that breached, so the commonest case — a 15:30 card still on court at 16:00 — does not print 16:00 twice. COURTS-1, ruled 8/17 (D1 option 1) |
| 55 | *(nothing — the strip's five chips said what the board IS; nothing said what THIS SITTING had done to it)* | **`Rule breaks +8 (8 new, 0 cleared)`** — the running score's first component, board-wide, measured against the schedule this console opened with. **"Rule breaks"** is row 34's ratified noun, reused here for the whole family (double-book · over the court limit · short rest · out of the day's order) rather than minted again. On hover the make-up: **"New: 7 out of the day's order, 1 over the court limit. Cleared: 1 over the court limit."** — must-fix kinds named before check kinds. Quiet on an untouched board: nothing changed this sitting, nothing rendered. SCORE-1, D2 ruled 8/20 |
| 56 | *(nothing — the `Unplaced` chip is scoped to the division on screen, so a match held in one division read `Unplaced 0` in the other fifty)* | **`Off the schedule 1`** — the second component: matches the TD took off the schedule in this sitting and has not placed back, counted **board-wide**, so the number is the same from every division. Not "unplaced", which the strip already uses for a different, scoped count. Hover: **"1 match you took off the schedule is not yet placed back."** SCORE-1, D2 ruled 8/20 |
| 57 | *(nothing — nothing on the surface said how much court room a change had spent)* | **`Tightest slot 0 courts free (MHCC Jan 29 12:30)`** — the third component: the least room left at any court and hour this sitting touched, both ends of every change. The slot is named in the TD's own terms — venue, short date, time — never as an internal slot key. Hover: **"The least room left at any court and hour this sitting touched."** SCORE-1, D2 ruled 8/20 |
| 58 | *(nothing — there was no way to take a change back; moving a card to where it started left a change on the wire that named the card's own delivered slot)* | **"Take it back"** — the undo, one word for the TD's own sentence, on the match card, on the dock card and on the Change Check listing's rows. Not "Undo", which is a computer's word for it and says nothing about *what* is being undone. No confirm: redoing the change is one gesture. Hover: **"Put this match back where the schedule this console opened with had it."** A change made in an earlier round carries no control at all, and the absence is the statement. SCORE-1, D1 ruled 8/20 |
| 58a | **"MHCC has 24 courts and they're all in use at 11:00. Change taken back — the card is back where this schedule was delivered. Review before finalizing."** — shipped 8/20 and **wrong**, reported by the Operator from the surface the same day: the opening clause is the capacity **refusal** sentence (row 53) word for word, so a change that had been APPLIED read as an error | **"Change taken back — the match is back where this schedule was delivered. ⚠ That leaves 1 match over the court limit. See which in Issues."** — what happened FIRST, the consequence second, a route third (EVAL-1's own shape). Silent when the undo breaks nothing. The kinds read **double-booked** · **over the court limit** · **with too little rest** · **out of the day's order**, must-fix before check, off the same board-wide record the score card reads so the two surfaces cannot describe one board two ways. SCORE-1a, 8/20 |
| 58b | *(nothing — a swap was two changes to the tool and one gesture to the director, and taking back one half put a match back on top of its own partner)* | **"Swap taken back — both matches are back where this schedule was delivered."** One click on either half returns both, because one gesture is one undo. The pairing lasts only while both matches still sit where the swap put them: move either one again and the two stop being one gesture. SCORE-1a, Operator ruling 8/20 (option 1) |
| 59 | *(nothing — a sitting could only be given back one change at a time, and it could not be given back at all)* | **"Start over"** → armed: **"Start over · confirm"**. The whole-sitting sibling of row 58, beside the change count it clears. It asks twice, and the first click says what it is about to do with the real number: **"Start over · this takes back the 4 changes you made and returns the schedule to the version this console opened with. Click Start Over again to confirm."** Done: **"Every change removed. The schedule is back to the version this console opened with."** Greyed, never hidden, when there is nothing to take back. SCORE-1, Operator addition 8/20 |
| 59a | **"‹ earlier rounds"** · **"later rounds ›"** · **"Round 3 – Semifinals of 6 rounds"** — the Bracket tab's round stepper, and the four columns it paged through | *(nothing — all of it is **retired**)*. Every round of a draw is on the screen at once, so there is no window to step and no label to explain it. Measured at retirement: **14 of the 42 elimination draws ran deeper than four rounds** — 8 at five, 5 at six, 1 at seven — so a third of the draw sheets could not be seen whole, which is the one thing a draw sheet is for. BRACKET-2, Operator instruction 8/20 |
| 60 | *(nothing — the Change Check tab listed what was wrong with the board and never what the TD had changed)* | **"Changes you made in this sitting (6)"**, above the two warning blocks, one row per change: **"Moved · Women's 60 & over singles, Round 1 · Match 15 — Kathy Brashear v Lisa Sutherland — now ORLP 11:00 Jan 25, was ORLP 08:00 Jan 25"** and **"Taken off the schedule · … — was MHCC 12:30 Jan 29"**. Matches are named division · round · players (ruling 3); no internal id reaches the screen. Absent entirely when this sitting has changed nothing. SCORE-1, 8/20 |

### 5.3 · Draw sheets (52 sheets)

| # | Now | Proposed |
|---|---|---|
| 33 | `DAY SHAPE: E36-R1-M14 (doubles) starts 11:00 on 2026-01-24, before an earlier-kind match of that day is under way (singles -> mixed -> doubles)` — the red page, verbatim from the run *(1 of 17 templates; 14 name a match this way)* | **"Men's 55 & over doubles, Round 1 — Heine/Straley v Daly/Shea: 11:00 Sat 24 Jan, ahead of that day's singles and mixed."** *(ruling 3 + the "earlier-kind" ban)* |
| 34 | "2 rule breaches recorded on this schedule after hand edits." | **"2 rule breaks after your edits."** |
| 35 | "USTA Wilson World Tennis Classic · **Draw Stage: Main** · single elimination, 16-draw" — **51 sheets** | **"· Main draw ·"** |

### 5.4 · Run-of-play sheets and player schedules

| # | Now | Proposed |
|---|---|---|
| 36 | The **"who's playing" column** on a match whose players aren't decided yet repeats the two columns to its left and adds an internal match number — row reads `Quarterfinal │ Men's 85 & over singles Quarterfinal M2` — **272 of 760 rows** | **"To be decided"** |

**⚠ Item 36 was mis-stated in the first draft of this sweep and is corrected here.** The first
pass reported the *round* column as carrying an ` M<n>` suffix. It does not: `_round_label`
(`schedule_views.py:250-266`) returns clean values, measured — `Final · Semifinal · Quarterfinal ·
Round 1–6`, nothing else. The real site is `_sides_html`'s fallback (`schedule_views.py:291`
and `:300`), which returns `m["match"]` when a match has neither `sides` nor `players`. The
defect is worse than first written: the one column that answers *"who is playing?"* answers it
with the division and round already printed beside it.

*Available if preferred, from data already in hand:* the console solves the same problem with
`feedersOf`'s id arithmetic, so this cell could read **"Winners of Round 1 M3 & M4"** instead.
That is more informative and four words longer; **"To be decided"** is carried as the proposal
under the house rule. Operator's call at brief approval — it changes one string, not the design.

*Everything else on both sheets is already right and is untouched — including "Courts are assigned
at the desk on the day…", "Report to the desk at the site above; your court is given to you
there.", and the player handouts' **"— awaiting an opponent"** (172 uses), which is already the
right answer to the same question.*

### 5.5 · The pre-publication report (the one mandatory page)

| # | Now | Proposed |
|---|---|---|
| 37 | PRE-PUBLICATION SCHEDULE REPORT | **SCHEDULE CHECK** |
| 38 | `source   : (supplied schedule)` | `checked  : current schedule` |
| 39 | `audited  : 760 stamped matches · 1164 certain player commitments · 10 days` | `matches  : 760 · named entries 1,164 · 10 days` |
| 40 | `findings : 2  (1 breach · 1 info)` | `found    : 2  (1 must fix · 1 info)` |
| 41 | `three-event player-days: 4 · band move-list: 0 matches` | `in 3 divisions in a day: 4 · moved for an early start: 0` |
| 42 | `CADENCE — Round cadence — one round per division per day  (1)` *(1 of 10 code headings)* | **`Two rounds in one day  (1)`** *(rulings 1 + 4)* |
| 43 | `[BREACH]` · `[WARN]` · `[INFO]` | **Must fix** · **Check** · **Info** *(ruling 4, tightened)* |
| 44 | "A seed block is skipped (seeds run 2) — usually a withdrawal print artifact, not an error." | **"A seed number is missing (1, 2, then skip). Usually a withdrawal, not an error."** |
| 45 | `VENUE-LATE — Venue — semifinals, finals and 80-and-over off the host site` | **"Semifinals, finals and 80+ away from the main site"** |

### 5.6 · The exceptions list (121 rows)

| # | Now | Proposed |
|---|---|---|
| 46 | `status unclear — list says "Withdrawn, Selected" across: Women's 45 & over doubles, Women's 50 & over doubles…` — **44 of 121 rows** | **`Entry list conflicts — Withdrawn / Selected: Women's 45 & over doubles, Women's 50 & over doubles…`** |
| 47 | `Selected - ALT` | **UNCHANGED** *(Operator, 8/7)* |
| 48 | `Unpaired` | **UNCHANGED** *(Operator, 8/7)* |

*Columns `Player · USTA ID · Division · Why not playing · Draw status (desk) · Needs a look` are
already right and stay. 45 of 121 rows flagged **Needs a look** — unchanged.*

### 5.7 · What the run says out loud (the runbook)

| # | Now | Proposed |
|---|---|---|
| 49 | `L2 name-match rate: 100.00%  ingest warnings: 0` | **"Level 2: all names matched. Nothing to flag."** |
| 50 | `coverage: reconciliation counts 1066 scheduled entries; the per-player CSV will carry 1066 rows -> MATCH` *(N4's recorded anti-pattern)* | **"1,066 on the schedule, 1,066 in the player file. Agree."** |
| 51 | Step 5.5 instruction: read out "the counts by code" | **read out the findings in plain words** *(ruling 4 leaves no codes to read)* |
| 52 | Courier stops name the block `td-setup/v1` | **"the setup block"** in speech; the schema name stays inside the block |
| 53 | The September step that marks the finals calendar as the one the players were told about would naturally say *"publish the calendar"* — but **18 of the runbook's 24 publish/announce lines already use "publish" to mean *put this HTML on a link and hand over the link*** (measured, PUB-1 §0.14) | **"announce" / "the announced calendar"**, in the step, in the file the TD keeps, and in everything a September run says out loud. ✅ **RULED (Operator, 2026-08-23 — PUB-1 open item b):** the two senses cannot share a word on the one surface where both appear, and the director is the person who would be misread to. *"Publish" keeps its existing meaning everywhere it already stands.* |

### 5.8 · "Rekey" — ✅ RULED, Operator 2026-08-07: **option 1**

**The screen says "Re-enter at the desk"; "rekey" stays in our own build names.** A7a remains
REKEY-1 and the deliverable keeps its internal name — the page the desk reads is what changes.
The Edit console's two labels become **Re-enter at the desk** / **"Nothing to re-enter."**, and
REKEY-1 must name its own page in the same register when it builds it.

*(Ruled as "Changes to re-enter at the desk"; tightened to "Re-enter at the desk" under the house
rule above, flagged there for confirmation. The three options as put are retained below.)*

1. **"Re-enter at the desk."** Says what the panel is for with no term to learn.
2. **Keep "rekey", gloss it once on first use.**
3. **Keep "rekey" bare.**

**Ruled option 1.**

### 5.9 · Deliberately unchanged — real tennis vocabulary

Confirmed present and correct on the swept screens, and **not** touched: **bye · BYE — walkover ·
seed and the `[1]` `[2]` seed marks · draw · main draw · round robin · Round 1–6 · Quarterfinals ·
Semifinals · Final · Champion — TBD · division · court · venue · site · entry list · alternate ·
withdrawn · partner · WTN (World Tennis Number) · USTA FAC II.A and Table 3 · single elimination ·
16-draw / 32-draw / 64-draw / 128-draw**, plus **`Selected - ALT`** and **`Unpaired`** (Operator,
8/7). Replacing any of these would make the tool sound like it does not know the sport.

---

## 6 · Status

**The glossary is CLOSED — every decision in it is ruled.** Rulings 1–4 (§3), the "rekey" ruling
(§5.8) and the ultra-concise house rule (§5) are the complete vocabulary set; §5's 52 items are
the work-list the LANG-1 brief will be written against. **No brief is drafted yet** — held at
Operator instruction, 2026-08-07.

Three items carried into the brief when it is written, none of them a vocabulary question:
- **Item 25 is N5's fix** and its source strings are in `wwtc_pipeline.py` (`:717`, `:729`,
  `:797`), not `master_schedule.py` — see §1c.
- **Item 33 carries the engine sign-off flag** (ruling 3): it edits `validate_multi`'s conflict
  strings, which are engine-adjacent and pinned by `review1_conflict_sheet`. Wording only.
- **Two tightenings await confirmation** — the §5.8 rekey label and ruling 4's severity labels,
  both flagged in the house-rule box.

---

## 7 · The seven sentence rules — ✅ RULED, Operator 2026-08-23 ("keep all seven, they bind the working notes too")

**What this section is and why it exists.** §2 decides **which word** the tool uses for each
thing. It says nothing about **how a sentence is built**, which is why *"costs nothing"* passes
§2 cleanly and is still wrong — the Operator's own example, and the reason this section was
commissioned. These seven rules govern sentence construction on every surface. They **stack with
§2, they do not replace it**: a sentence obeying all seven while using a retired word still fails.

**Measured before ruling, 2026-08-23 at `78ed826`.** Of the glossary's ruled work-list, **55 of
64 checks hold**. Every item an automated check pins held — **100%** — and every unpinned item
drifted; the surface with no string harness at all (the runbook) was the worst, carrying four
retired screen strings and one statement that had become false. Across both consoles the
sentence rules below were already largely observed: **one** live violation of rule 3 and zero of
rules 1 and 7. The problem was never authorship. It was that nothing was watching.

### 7.1 · The rules

| # | Rule | Before → After | Held by |
|---|---|---|---|
| **1** | **Say what happens, not how hard it is.** Never call an action easy, cheap, safe, quick, simple, minor, trivial or free, and never say it "costs nothing". State the effect on the tournament. | *"costs nothing"* → **"does not change the schedule."** | machine |
| **2** | **Name the thing on the schedule, never a code.** A sentence about a match names division, round and players; a sentence about a place names venue, day and time. No internal ids, no invented code words. | *"DAY SHAPE: E36-R1-M14 starts 11:00"* → **"Men's 55 & over doubles, Round 1 — Heine/Straley v Daly/Shea: 11:00 Sat 24 Jan."** | machine |
| **3** | **The tool never names its own parts to the director.** No *engine*, *scheduler*, *mirror*, *console*, *validator*, *renderer*. Say what will or will not happen. | *"which the scheduler will refuse"* → **"and it will not build until that changes."** | machine |
| **4** | **A refusal says what happened, then what it costs, then the way forward — in that order** — and never implies the director erred. | The 8/20 undo message opened with the capacity **refusal** sentence word for word, so a change that had SUCCEEDED read as an error (§5.2 row 58a). Operator-reported off the surface the same day. | person, at review |
| **5** | **Every number carries its denominator and its unit.** A bare count implies a scale the reader cannot see. | *"38 matches out of order"* → **"38 of 760 matches out of order, 12 of them on Jan 26."** | partly machine |
| **6** | **A label is 1–3 words. A message is a fact and a consequence, nothing else.** Text explaining mechanism is deleted, not shortened. *(§5's ultra-concise house rule, 8/7, restated as global.)* | *"Can't be used as a substitute — their withdrawal isn't clear"* → **"Withdrawn not SUB"** | machine (length) |
| **7** | **The tool addresses the director as "you", never speaks as "I" or "we", and never apologises.** | *"Sorry, I couldn't place this match"* → **"Not scheduled — MHCC has 9 courts before 11:00 and they're all in use. Free a court on Tuesday morning."** | machine |

### 7.2 · Where they bind — Operator-ruled, and the one carve-out

**They bind every surface a director reads or hears** — the three consoles, the printed draw
sheets, the player schedules, the announced calendar, the pre-publication report, and everything
a RUN session says out loud — **and, by the 8/23 ruling, the working notes a session reads**:
`WWTC_test_run_starter.md`'s own prose is in scope, not merely the strings it quotes.

**The one carve-out, which is not new.** Where a rule collides with CLAUDE.md's standing rule
that **file names, function names, contract keys and commands are never translated**, the
standing rule wins and the collision is recorded rather than resolved silently. Three
consequences, each named with its count so none is mistaken for clean:

- **The four-figure anchor and the printed-figure read-backs** (*760 placed · 275 byes ·
  0 unplaced · 0 conflicts*, and the instructions that read that figure aloud) — **15 lines**.
  `unplaced` is the contract key the code prints; the runbook reads that figure back. Renaming it
  in prose alone would make the runbook disagree with the tool. **Owner: a future build that
  renames the PRINTED figure**, in the code and its harnesses together, at which point these 15
  lines follow in the same commit.
- **The ban statement itself** (the runbook's opening manner, **3 lines**) — a rule that forbids
  a word must be able to name the word it forbids. Permanently exempt.
- **Build ids, keyword arguments and dated history** — `SLATE-1` ×2, `slate=` ×1, and one quoted
  pair of retired 7.1 tab labels: **4 lines**. Permanently exempt.

**22 lines in total, and the harness asserts that number.** Appending a pattern without moving
the count fails the part.

**Rule 3's scope is TD-facing text.** A working note may name the engine, a module or a harness —
those are the load-bearing names above. What rule 3 forbids is the *director* being told about
the tool's internals.

**Briefs, `PLAN.md`, commit messages and code comments are unchanged and out of scope**, exactly
as §5's house rule already stated. They keep their full technical register.

### 7.3 · Enforcement — the whole point

The 8/23 measurement is the argument: **pinned held, unpinned drifted, 100% either way.** So
every rule above that a machine can hold is held by one, and the harness is named in the rule
table's last column.

- `tests/lang1_language.py` — the retired-term sweep over every regenerated TD-facing surface
  (unchanged; it has never gone red).
- `tests/lang1_runbook.py` — **new 8/23.** The runbook: retired screen strings graded BOTH ways
  and each replacement asserted to EXIST in the console the runbook attributes it to; the code
  words a run must never speak; the ruled plain readbacks; the working-notes sweep with the three
  carve-outs above held as NAMED, COUNTED exceptions; and the machine-checkable sentence rules
  (1, 3, 7) over the runbook and both consoles — **and, as of BRAND-1 the same day, over THE PAPER
  TOO**: `draw_sheets.py`, `schedule_views.py` and `finals_guidance.py`, 1,240 string literals.
  ⚠ **The collector needs BOTH halves and neither is optional.** `ast` drops docstrings, assert
  messages, self-test bodies and `__main__`, because a code comment can never be screen text; then
  HTML/CSS/JS comments are stripped *out of the surviving literals*, because these files BUILD
  markup and annotate it heavily — several times quoting the very wording they replaced. The naive
  sweep reports 6 hits on this set and **4 of them are annotation**. It found 2 real violations,
  both rule 3, **both on the finals console's wrap — the two paper surfaces were already clean.**
- `tests/sentence_list.py` — **new 8/23, BRAND-1, and it is not a rule check.** Rules 4 and 5 need
  a reader (§5.2 row 58a is the argument: that message broke no word rule, passed every automatic
  check, and was wrong in a way only a person looking at the screen could see). This collects every
  director-facing sentence on the five surfaces, compares against a committed snapshot, and prints
  **every string that is new or changed**, for a person to read before the build ships. **It never
  passes or fails on quality.** It fails on ONE thing: a snapshot it cannot trust — a surface
  missing, or a snapshot cut by a different collector version, which would make every sentence read
  as changed and teach the reader to skim.
  ⚠ **The flood is the real failure mode and it was measured, not guessed:** 2,665 sentences on the
  first cut, **450** after excluding one named literal — `SAMPLE`, the consoles' baked demo plan,
  359,531 bytes of it — which had made the list ~85% real players' names. **That exclusion is ONE
  identifier, its count is asserted, and each named holder is asserted to EXIST.** `LOCKED_RULES`
  is deliberately NOT excluded though it is also an ALL-CAPS array: its entries are TD-facing
  sentences, which is exactly what the file exists to show.

**Adding to an exception list is a decision, not a fix** — the same standing rule §5's `KEPT`
list carries. A failure "solved" by appending to an exception list has switched the rule off.
