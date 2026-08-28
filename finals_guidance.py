"""finals_guidance.py — FMAP-2's guidance layer over the FROZEN finals console.

`finals_plan.py` is frozen (D-3) and its four narrow waivers are spent. FMAP-2 needs tens of
lines of CSS and JS on that surface, which a fifth waiver would be a freeze exception in name
only — so the additions ride HERE instead (Operator ruling, 8/15, decision 3 option 1):
`render_finals_console` is called untouched and its output is decorated on the way past.
`finals_plan.py` and `finals_map_from_pdf.py` are not opened by this build.

What gets added, all of it fed by the plan doc's `engine_check` block (contracts §13):

  · an engine-check chip in the existing chip row — "47 of 50 hold as mapped · 3 need a look"
  · on a flagged row: a banded gold ring and a `!` on the day the division is mapped to, a DASHED
    GHOST F on the day the engine actually finishes it, and graded tints on its other days
  · a note card per flagged division in a rail right of the board, under a "Needs a look · N"
    header, carrying the cause in plain English, an Adopt button and a keep link (plus adopt-all
    when more than one is flagged)
  · a mini-tag on the division label where there is no day to propose
  · a three-line legend strip pinned in the sticky band over the board, its swatches real cells
    carrying the board's real classes
  · OI-42's fix (§6): when both clipboard paths fail, the Copy button's OWN LABEL carries the
    shortcut, so a sighted TD finally gets a visible cue

SKIN-FIN-1 (2026-08-27) re-cut this layer onto the BRAND-1 design lock with the surface it
decorates, and carried the Operator's three rulings of that day: all THREE verdicts paint on the
board, not only `blocked`; the legend is exactly three lines and is pinned over the grid rather
than folded into the paper beside it; the cards stay cards, in a rail. The graded grid's data,
the cards' content and every behaviour here are unchanged.

⚠ AMENDED 2026-08-28 (Operator, option 1) AFTER THE BOARD WAS DRIVEN ON TWO REAL FIELDS: green
means "no OTHER division moves", not "not one match moves". As first shipped the green could
NEVER reach the screen — 0 green squares of 180 inked on the 2027 projected field and 0 of 211
on the 2026 bench — because the strict reading is only ever true of the day a division already
sits on, which carries the F and takes no ink. What the director got was a wall of yellow, 210
against one pink on the bench. The split is the CONSOLE's: `_grade` and `data-fm2` are
untouched, so the plan doc, the emit and the harness's cell-for-cell grading are exactly as
they were.

THE TWO RULES THIS MODULE LIVES BY

1. **Absent `engine_check` => nothing happens.** The frozen renderer's output is returned
   byte-for-byte. A TD who never asked for the verdict gets the console that shipped.
2. **Every addition is read-only until Adopt.** Adopt calls the console's own `moveFinal` — the
   shipped drag, no new operation — so `td-finals-map/v1` (§14) is untouched and a zero-drag
   emit still means exactly what it meant. A decoration that writes state is a defect here.

Offline like the surface it decorates (B-1): no fetch, no XHR, no external script, data embedded
at generation. Deterministic: the injected payload is built in sorted order, like the plan.
"""
from __future__ import annotations

import json

import finals_plan as FP

# ---------------------------------------------------------------- the injection anchors
# The layer keys off three points in the frozen file's output. They are PINNED here and asserted
# to appear exactly once, so drift in the frozen file is a loud failure at generation rather than
# a silent half-injection on the TD's screen. If a future waiver legitimately moves one of these,
# it is re-pinned in that same commit (decision 3's stated wrong-case).
ANCHOR_CSS = "</style>"
ANCHOR_CHIP = '<span class="chip" id="chipWarn">0 warnings</span></p>'
# SKIN-FIN-1: a FOURTH anchor, and it exists because the legend and the note panel no longer
# belong in the same place. The Operator's 8/27 ruling pins the legend INSIDE the sticky band,
# immediately under the chip row — which is exactly where ANCHOR_CHIP lands it. The note panel
# must NOT go there: it is fixed at wide widths but drops into normal flow under 1100px, and a
# column of cards flowing inside the sticky band would push the board off the screen. It is
# injected in front of the board instead, so its narrow-width fallback is the same one it has
# always had — normal flow, immediately above the board.
ANCHOR_BOARD = '<div class="wrap">'
ANCHOR_JS = "</script>"

_GRADES = ("hold", "moves", "blocked", "infeasible")


def _check_anchor(html, anchor, what):
    n = html.count(anchor)
    if n != 1:
        raise ValueError(
            f"finals_guidance: the {what} anchor appears {n} times in the generated console, "
            f"expected exactly 1 — the frozen renderer's structure moved and this layer's "
            f"injection points must be re-pinned: {anchor!r}")


CSS = """
    /* ---- FMAP-2 guidance layer (finals_guidance.py) ------------------------------------
       Additions only. Nothing here restyles a shipped element: every selector is `.fm2-*` or
       an fm2 attribute, so a console generated without a verdict is untouched.
       SKIN-FIN-1: re-cut onto the BRAND-1 lock with the surface it decorates. Every value below
       is read through `var()` off the tokens the frozen renderer declares — this block injects
       INTO that stylesheet — except the three the Operator ruled on 8/27, which are declared
       here because they are this layer's own and are named in `DESIGN_RECORD.md` §2. */
    :root{
      --w-grade-hold:#e6f2e6; --w-grade-block:#f2d7da; --w-grade-block-heavy:#ebcdd1;
    }
    /* THE "WILL NOT HOLD" RING IS DELIBERATELY NOT THE SHIPPED LOCKED-DAY RING (Operator
       review, 8/16). Both were amber 3px inset and computed PIXEL-IDENTICAL
       (`rgb(156,95,14) 0 0 0 3px inset`), so a board carrying nine locked days and three broken
       ones showed twelve identical rings telling two unrelated stories, separated only by a `!`.
       This one is a banded ring — a panel-coloured gap inside an amber band — which reads as a
       different mark at a glance and cannot be mistaken for `moved-f`. The shipped ring is NOT
       touched: it is the frozen console's and means "you locked this day". */
    td.fcell.fm2-ring{box-shadow:inset 0 0 0 2px var(--w-bg), inset 0 0 0 5px var(--w-avoid);
      position:relative}
    /* the `!` is a filled badge, not a bare character: it has to survive a scan of a 50-row
       board on which only 19 rows fit at once.
       ⚠ SKIN-FIN-1: the glyph is INK ON GOLD, not white on gold. Measured: white on the record's
       `--w-avoid` is **2.65:1**, far under the 4.5:1 floor for text this small, where white on
       the CUI-2 amber it replaced was **5.18:1** — so carrying the white glyph across would have
       quietly made a warning badge harder to read than the one it succeeded. Ink on the same
       gold is **6.94:1**. */
    td.fcell.fm2-ring .fm2-bang{position:absolute;top:1px;right:1px;width:15px;height:15px;
      border-radius:50%;background:var(--w-avoid);color:var(--w-ink);font-size:11px;
      line-height:15px;font-weight:700;text-align:center;margin:0}
    /* the engine's day is a GHOST, never a solid F — the map does not change until the TD
       adopts, and a solid F would say it already had. */
    td.fcell.fm2-ghost{color:var(--w-notice-ink);font-weight:700;
      box-shadow:inset 0 0 0 2px var(--w-notice-line);background:var(--w-notice-bg)}
    td.fcell.fm2-ghost .fm2-ghostf{opacity:.75;border-bottom:2px dashed var(--w-notice-ink)}
    /* ---- the graded grid: ALL THREE VERDICTS PAINT (Operator ruling, 2026-08-27) ------------
       ⚠ THIS SUPERSEDES THE 8/16 "PAINT ONLY WHERE IT IS NEWS" RULING, and the history is kept
       because it is the argument, not a changelog. The FIRST cut painted every graded cell in
       one cream: 275 cells saying "moving the final here shuffles matches", true of nearly every
       move, with the 26 days that actually cost a court sitting inside that wash. 8/16 answered
       by painting only `blocked`. 8/27 answers differently and better: three grades, three
       different colours, so the wash cannot come back — a green cell and a yellow cell no longer
       look alike, and "nothing else moves" is a fact the TD could not previously see anywhere.
       The three paints, ruled: pale green = the final can move here and NO OTHER DIVISION
       moves · pale yellow = other divisions reshuffle but the week still fits · pink = a day is
       overloaded.
       ⚠ THE GREEN'S MEANING WAS AMENDED 2026-08-28 (Operator, option 1) — see `GRADE_INK` in the
       script, which carries the measurement. Read strictly, as it shipped on 8/27, green could
       not reach a real board at all: 0 squares of 180 inked on the 2027 field, 0 of 211 on the
       bench. The paint rule below is unchanged; what moved is which grade reaches it.
       ⚠ WHAT DID NOT CHANGE, and must not: ink goes only on a cell where the frozen renderer
       drew nothing, so the shipped `td.F` / `td.SF` / `td.QF` / `td.R` shading is never
       overwritten (these selectors outrank it, which is how the first build silently flattened
       90 cells); `data-fm2` still rides on EVERY cell as the data the harness grades against the
       doc; and the per-cell hover numbers are untouched — the shade is the glance, the number is
       the answer.
       ⚠ TWO SHADES OF PINK, not one (Operator ruling, 8/16, RETAINED 8/27). One shade flattened
       a 28-fold range: on the committed field the marked days run from +1 problem touching one
       other division to +28 across eleven, and a TD avoiding both equally is being told a
       nuisance and a bad idea are the same thing. `HEAVY_COST` in the script is the line.
       The three new values entered `DESIGN_RECORD.md` §2 at this build (§4 of the brief); the
       yellow is the record's existing `--w-cell-2`, and nothing else was minted. */
    /* ⚠ THESE FOUR DROP THE `td` QUALIFIER THE REST OF THIS SHEET KEEPS, and it is deliberate:
       the legend's swatches are the SAME classes on <span>s, so one declaration paints both the
       board and the key to it and they cannot drift a value at a time. Two classes still outrank
       the shipped one-class round shading, so the ranking the note above depends on is intact —
       and what actually keeps ink off a labelled cell is the `!td.textContent` guard in the
       script, never specificity. */
    .fcell.fm2-hold{background:var(--w-grade-hold)}
    .fcell.fm2-moves{background:var(--w-cell-2)}
    .fcell.fm2-mark{background:var(--w-grade-block)}
    .fcell.fm2-mark-heavy{background:var(--w-grade-block-heavy)}
    /* ⚠ FLAT FILLS, NO INSET RINGS — measured off the approved mock, where all four graded
       squares are one colour edge to edge. The 8/16 shades carried a 1px inset each and the
       heavy one carried it in the BRAND RED, which on a board of 500 cells read as an alarm
       rather than as the harder half of a scale. The two-shade split the 8/27 ruling retained
       lives in the fill, which is where the mock puts it.
       ⚠ THE DAY A DIVISION'S ROUNDS CANNOT REACH STILL HAS NO RULE, and that is a decision
       rather than an omission: it is not a choice at all. The mock greys those squares in a
       near-white the record does not name, and this build mints no colour (brief §4). The
       nearest free grey, `--w-off`, sits ONE unit from `--w-rule-2` — the semifinal ground — so
       painting it would have made an unreachable day and a semifinal day look identical.
       Reported to the Operator rather than solved here (§5, §7 rule 5). Nothing is lost: the
       drag affordance already refuses to highlight those days (ruling 60), and the one hard
       refusal names the earliest day that works. */
    /* ---- the day the WEEK refuses (Operator ruling, 2026-08-28, option 1) -------------------
       ⚠ `infeasible` IS TWO FACTS WEARING ONE NAME, and this is the other one — see `GRADE_INK`
       in the script, which carries the measurement and the reason the console can tell them
       apart. This square is a day where the tool built the WHOLE tournament with that final and
       could not schedule the week at all.
       It is struck, not coloured: a fine diagonal in the board's own rule grey. Deliberately NOT
       a fourth tint — this square is not a point on the cost scale the three colours carry, it
       is the ABSENCE of a schedule, and giving it a colour would enter it into a conversation it
       is not part of. Drawn in a token the record already names, so nothing is minted.
       ⚠ IT IS THE WORST OUTCOME ON THE BOARD AND IT WAS THE MOST INVISIBLE: 63 squares on the
       2027 projected field, across 35 of 56 divisions, rendered as blank paper and captioned
       with the OTHER reason — and the drop was ACCEPTED on every one of them, because the rounds
       fit. Found by the Operator driving the board. */
    td.fcell.fm2-refused{background-image:linear-gradient(to top right,
      transparent calc(50% - 0.5px), var(--w-rule) calc(50% - 0.5px),
      var(--w-rule) calc(50% + 0.5px), transparent calc(50% + 0.5px))}
    /* ...and the ghost keeps its gold over any grade, being the more specific fact. */
    td.fcell.fm2-ghost{background:var(--w-notice-bg)}
    .fm2-tag{display:inline-block;font-family:var(--w-body);font-size:var(--fs-xs);font-weight:700;
      padding:1px 6px;margin-left:8px;border-radius:var(--radius);background:var(--w-notice-bg);
      border:1px solid var(--w-notice-line);color:var(--w-notice-ink);vertical-align:1px}
    /* The note panel sits IMMEDIATELY RIGHT OF THE GRID (Operator review, 8/16). It used to
       pin to the window's right edge (`right:18px`), which parked it on top of the scroll
       region's own scrollbar and left a moat of blank paper between the board and the cards
       that annotate it. It is still FIXED so it stays with the TD while the 50-row board
       scrolls under it — but its left edge now follows the table's right edge, measured in
       layout() (CSS cannot see the table's width). Below the width where the free space runs
       out it drops into normal flow above the board instead, unchanged. */
    /* SKIN-FIN-1 (Operator ruling 5, 8/27): THE CARDS STAY CARDS, IN A RAIL. What changed is
       paint and width — 300px, the approved mock's, which is what stops a plain-English cause
       from breaking into one word a line. Card CONTENT and the Adopt / keep / stale BEHAVIOUR
       are FMAP-2's and are untouched. The rail wears the notice gold end to end, because every
       card in it is the same one level of message: something here wants a look. */
    .fm2-panel{position:fixed;width:300px;z-index:25;
      max-height:calc(100vh - var(--stickyH, 200px) - 40px);overflow:auto}
    /* the rail's own title, ruled at 8/27 ("Needs a look · N") with the adopt-all beside it.
       The adopt-all is still a <button> and still carries `fm2-adopt-all` — it is the same
       control, wearing the keep link's shape because the mock puts it on the title's line. */
    .fm2-panelhead{display:flex;align-items:baseline;justify-content:space-between;gap:8px;
      flex-wrap:wrap;margin:0 0 8px}
    .fm2-panelhead h2{font-family:var(--w-display);font-size:var(--fs-md);font-weight:500;
      margin:0;color:var(--w-ink)}
    .fm2-card{background:var(--w-notice-bg);border:1px solid var(--w-notice-line);
      border-left:4px solid var(--w-avoid);border-radius:var(--radius);padding:12px;margin:0 0 8px}
    .fm2-card h3{font-size:var(--fs-sm);margin:0 0 4px;color:var(--w-ink);font-weight:700}
    .fm2-cause{font-size:var(--fs-sm);margin:0 0 8px;color:var(--w-notice-ink);line-height:1.45}
    .fm2-card button.fm2-adopt{font-size:var(--fs-sm);height:28px;padding:0 12px;
      background:var(--w-red);color:var(--w-bg);border-color:var(--w-red)}
    .fm2-card button.fm2-adopt:hover{background:var(--w-red-h);border-color:var(--w-red-h);
      color:var(--w-bg)}
    .fm2-keep{font-size:var(--fs-sm);margin-left:8px;color:var(--w-muted);
      background:none;border:0;padding:0;height:auto;text-decoration:underline;cursor:pointer}
    .fm2-keep:hover{color:var(--w-red)}
    .fm2-panelhead button.fm2-adopt-all{font-size:var(--fs-sm);color:var(--w-muted);
      background:none;border:0;padding:0;height:auto;text-decoration:underline;cursor:pointer}
    .fm2-panelhead button.fm2-adopt-all:hover{color:var(--w-red)}
    /* ---- the STALE state (Operator ruling, 8/16) --------------------------------------------
       The check is 302 full builds of the whole tournament; it cannot re-run in a browser, and
       the console never talks to the engine (B-1). So the moment the board moves off the map the
       verdict was run against, everything here describes a board that no longer exists — and
       before this it went on asserting "47 of 50 hold as mapped" anyway, with the same
       confidence it had when that was true. Worse, a moved division's card USED TO VANISH, which
       reads as "fixed" when it means "no longer checked". Now the chip drops its amber and says
       what it is, the panel names the route to a fresh answer, and a moved card stays and marks
       itself. Nothing here claims to know whether the new day is better. */
    .chip.fm2-stale{background:var(--w-hair);border-color:var(--w-rule);color:var(--w-muted)}
    /* SKIN-FIN-1: the banner loses CUI-2's blue with the rest of that family. The record has two
       message levels and this is the softer one — it does not say anything is wrong with the
       tournament, only that the reading on screen is older than the board. BEHAVIOUR UNTOUCHED
       (brief §3.5): when it shows, what it says and what it offers are all FMAP-2's. */
    .fm2-banner{background:var(--w-notice-bg);border:1px solid var(--w-notice-line);
      border-left:4px solid var(--w-avoid);border-radius:var(--radius);padding:12px;margin:0 0 8px;
      font-size:var(--fs-sm);color:var(--w-ink);line-height:1.45}
    .fm2-card.fm2-was-moved{opacity:.72;border-left-color:var(--w-rule)}
    .fm2-movedline{font-size:var(--fs-sm);color:var(--w-muted);margin:0 0 8px}
    .fm2-none{font-size:var(--fs-sm);color:var(--w-muted);margin:0}
    /* ---- the legend: THREE LINES, PINNED (Operator ruling, 2026-08-27) ----------------------
       ⚠ THIS REPLACES THE 8/16 LEGEND, AND THE CUT IS THE POINT: 13 entries down to 3. That
       legend answered "I don't know how to read this map" by naming every mark on the board —
       the F ladder, moved-F, the ghost, the flag ring, the drag outline, the tag, both chips —
       and a 13-row key parked in the right-hand paper is a second thing to read while deciding.
       Every one of those marks now explains itself where it is drawn, on the board or on its
       card. What is left is the ONE thing a coloured square cannot say by itself: what the
       colour means. The three lines are the Operator's own words, verbatim, and are not
       paraphrasable — "Costs a court" was rejected as language to put in front of a director,
       and "Many matches shift" was rejected as factually wrong for pink, which is a difference
       in kind rather than of volume.
       It is a slim horizontal STRIP now, not a panel: it rides the sticky band between the chip
       row and the board, so it is on screen at every scroll position of a 50-row board — which
       is what the fixed lane and its fold were both working around. The fold, the caret, the
       `<details>` element and the fixed-lane geometry all retire with it.
       ⚠ The swatches are still REAL cells carrying the REAL classes (`td.fcell fm2-hold` and its
       two mates) inside the strip, so a re-ruled shade repaints here for free and the legend
       cannot drift from the board a value at a time. */
    .fm2-legend{display:flex;align-items:center;flex-wrap:wrap;gap:8px 16px;margin:0 0 12px;
      padding:8px 12px;background:var(--w-bg);border:1px solid var(--w-hair);
      border-radius:var(--radius)}
    .fm2-lgd-row{display:flex;align-items:center;gap:8px}
    /* the swatch takes the surface's ONE radius, not a smaller one of its own: `DESIGN_RECORD.md`
       §5's Working column names 7px and this build's acceptance is one value on the page. */
    .fm2-legend .fcell{display:block;width:28px;min-width:28px;height:18px;padding:0;
      border:1px solid var(--w-rule);border-radius:var(--radius)}
    .fm2-legend .fm2-lgd-t{font-family:var(--w-body);font-size:var(--fs-sm);line-height:1.35;
      color:var(--w-ink)}
    @media (max-width:1099px){
      .fm2-panel{position:static;width:auto;max-height:none;margin:0 0 12px}
    }
"""

JS = """
    // ---- FMAP-2 guidance layer (finals_guidance.py) -----------------------------------------
    // Runs AFTER the frozen script, in the same scope, so it reads that script's own state
    // (`fday`, `moved`, `DATES`) and calls its own `moveFinal`. Nothing here is a second copy of
    // the console's rules: Adopt IS the drag.
    var FM2 = __FM2__;
    (function(){
      "use strict";
      var byEvent = {}, dismissed = {};
      FM2.notes.forEach(function(n){ byEvent[n.event] = n; });

      function esc(s){ return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;")
                                       .replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }

      // ---- what a candidate day COSTS, in the TD's own terms --------------------------------
      // HEAVY_COST is the line between the two marked shades: at or above it the day is shaded
      // harder. FIVE, and the reason is the TD's own rhythm rather than this field's histogram —
      // a division plays about one round a day, so five matches knocked off their planned day is
      // roughly a round's worth of play disturbed. Below that it is a nuisance; at or above it he
      // is re-cutting the week. ⚠ It is ONE NUMBER IN ONE PLACE on purpose: it is a judgement,
      // the Operator owns it, and moving it must never mean hunting through the file.
      var HEAVY_COST = 5;
      // The ONE place a grade becomes ink (Operator ruling, 8/27: all three verdicts paint). It
      // is a function rather than a lookup because two of the three grades SPLIT, and it is
      // named once so the legend's swatches and the board's cells cannot be given two different
      // answers — `legendHTML()` below reads the same class names.
      //
      // ⚠ GREEN IS "NO OTHER DIVISION MOVES", NOT "NOT ONE MATCH MOVES" (Operator ruling,
      // 2026-08-28, option 1). AS FIRST SHIPPED THE GREEN COULD NOT REACH THE BOARD AT ALL, and
      // it was measured on two whole fields before this changed: `hold` requires that NOT ONE
      // match anywhere changes day, and sliding a final always drags its own division's ladder
      // with it — so the only cell that can ever grade `hold` is the day the division already
      // sits on, and that cell carries the red F, which ink never overpaints. Measured: 0 green
      // squares of 180 inked on the 2027 projected field, 0 of 211 on the 2026 bench. What the
      // director got instead was a wall of yellow — 210 yellow against ONE pink on the bench —
      // which is the same wall the 8/16 ruling existed to break up.
      // The `moves` grade carries the number that actually separates a free day from an
      // expensive one: how many OTHER divisions the move disturbs. Splitting on it is the
      // Operator's own sentence working — "nothing ELSE moves" reads as "no other division",
      // which is what this now paints. Measured after: 149 green / 13 yellow / 18 pink on the
      // 2027 field, 191 / 19 / 1 on the bench.
      // ⚠ THE SPLIT IS THE CONSOLE'S, NOT THE ENGINE'S. `data-fm2` still carries the engine's
      // four grades verbatim and `_grade` is untouched, so the doc, the emit and the harness's
      // cell-for-cell grading are all exactly as they were. Only ink moved.
      //
      // ⚠ `infeasible` IS TWO DIFFERENT FACTS WEARING ONE NAME, and the second one is the most
      // expensive thing on this board (Operator ruling, 2026-08-28, option 1 — found by driving
      // the board, not by reading the code). `_engine_check` writes `{"grade":"infeasible"}` from
      // TWO places: the cheap one, where the division's rounds cannot reach the day and no build
      // is spent; and the catch around the candidate build, where the WHOLE WEEK could not be
      // scheduled with that final moved there. Measured on the 2027 projected field: 161 of the
      // 224 are the first, 63 are the second, spread across 35 of 56 divisions — and Wed 1/27
      // alone refuses 19 divisions. The doc cannot tell them apart (both cells carry `grade`
      // alone), and until this ruling the board showed both as empty white and told the TD the
      // FIRST reason for both. Worse, the drop was ACCEPTED on all 63: the rounds fit, so the
      // console let him choose a day it had already proved has no schedule behind it.
      // The console separates them with what it already knows — `canLand` is the same rounds
      // test the engine's cheap branch uses.
      // ⚠ WHY THE SPLIT CANNOT RAISE A FALSE ALARM: the engine's threshold is `need - 1`, where
      // `need` is the division's rounds MINUS ONE for a same-day-finish division. `need <=
      // rounds`, so every cell the engine calls structurally infeasible also fails `canLand`,
      // and a good day can never be struck. The reverse is a MISS, not a false alarm: on a field
      // that sets same-day-finish, a joined division's week-refusing day at exactly one column
      // before its earliest can read as the quiet case and stay blank. Named rather than solved
      // — the plan doc carries no constraints block, so the console cannot see that list.
      function GRADE_INK(g, reachable){
        if (g.grade === "hold") return " fm2-hold";          // reachable only on the mapped day
        if (g.grade === "moves") return g.divisions ? " fm2-moves" : " fm2-hold";
        if (g.grade === "blocked")
          return g.cost >= HEAVY_COST ? " fm2-mark fm2-mark-heavy" : " fm2-mark";
        // infeasible: struck when the WEEK refused it, blank when the rounds cannot reach it —
        // the second is not a choice at all and has nothing to say.
        return reachable ? " fm2-refused" : "";
      }
      function plural(n, one, many){ return n + " " + (n === 1 ? one : many); }
      function costLine(g, isHere, reachable){
        // ⚠ the day the division ALREADY sits on is not a candidate, and every "moving here"
        // sentence is nonsense on it — it would read "leaves 0 more matches on a day it was not
        // planned for". Its grade still reports the division's own standing, which is what the
        // ring and the card are about.
        if (isHere)
          return g.grade === "hold"
            ? "This division finishes here, and the check found nothing wrong with that."
            : "This is the day this division is mapped to finish — see the note on the right.";
        if (g.grade === "infeasible")
          // ⚠ TWO FACTS, TWO SENTENCES (Operator ruling, 8/28). Until this ruling BOTH cells
          // carried the first line, so 63 squares on the 2027 field named a reason that was not
          // theirs — the rounds fit those days perfectly well; the week does not.
          return reachable
            ? "Moving the Final here leaves the week with no schedule at all. The tool built "
              + "the whole tournament with this day and it did not hold."
            : "This division's rounds cannot finish by this day.";
        if (g.grade === "hold") return "Moving the Final here changes nothing else.";
        // the shade is the glance and the number is the answer, so the number the shade SPLITS
        // on has to be in the line (Operator ruling, 8/28): a green cell says who is untouched,
        // a yellow one says how many divisions are not.
        if (g.grade === "moves")
          return g.divisions
            ? "Moving the Final here shifts " + plural(g.matches, "match", "matches")
              + " to a different day, across "
              + plural(g.divisions, "other division", "other divisions")
              + ", and every one still plays when it was planned to."
            // the green line ENDS on the fact the colour is about, so a reader who stops after
            // the first clause has still been told the thing the shade promised
            : "Moving the Final here shifts " + plural(g.matches, "match", "matches")
              + " to a different day, and every one still plays when it was planned to. "
              + "No other division changes.";
        return "Moving the Final here leaves " + plural(g.cost, "more match", "more matches")
             + " on a day it was not planned for"
             + (g.divisions ? ", across " + plural(g.divisions, "other division", "other divisions")
                            : "")
             + ". It is still a legal schedule.";
      }

      // Which divisions the board has moved off the map the verdict was run against. Any drift
      // at all makes the whole verdict historical: the check grades a WHOLE map, so moving one
      // division can change what courts are free for another. That is the same reason the check
      // runs the full build in the first place.
      function movedSince(){
        var out = [];
        Object.keys(FM2.graded_map).forEach(function(ev){
          if (fday[ev] !== FM2.graded_map[ev]) out.push(ev); });
        return out;
      }

      // The chip is a SIXTH member of the shipped strip, styled by the same `.chip.warn` rule
      // the warnings chip uses — one vocabulary of "this needs attention" on the row. Once the
      // board drifts it goes NEUTRAL, not amber: a stale reading is not a warning about the
      // tournament, it is a statement about the reading.
      function chip(){
        var c = document.getElementById("chipCheck");
        if (!c) return;
        var n = movedSince().length;
        if (n){
          c.textContent = "checked against the days as generated \\u00b7 " + n
                        + (n === 1 ? " division moved since" : " divisions moved since");
          c.className = "chip fm2-stale";
          return;
        }
        c.textContent = FM2.flagged
          ? FM2.held + " of " + (FM2.held + FM2.flagged) + " hold as mapped \\u00b7 "
            + FM2.flagged + " need a look"
          : FM2.held + " of " + FM2.held + " hold as mapped";
        c.className = "chip" + (FM2.flagged ? " warn" : "");
      }

      // Decorations are re-applied after EVERY render, because the frozen render() rebuilds the
      // whole tbody. They are painted from the doc, never from the DOM, so they cannot drift.
      function decorate(){
        var rows = document.querySelectorAll("#fboard tbody tr.card");
        Array.prototype.forEach.call(rows, function(tr){
          var ev = tr.getAttribute("data-ev"), note = byEvent[ev];
          var grid = FM2.day_grid[ev];
          Array.prototype.forEach.call(tr.querySelectorAll("td.fcell"), function(td){
            var dt = DATES[parseInt(td.getAttribute("data-di"), 10)];
            var g = grid && grid[dt];
            if (g){
              // the grade rides on every cell as DATA; ink goes on ALL THREE verdicts (Operator
              // ruling, 8/27 — see the stylesheet) but still ONLY where the frozen renderer drew
              // nothing, so the shipped round shading is never overpainted. Tested BEFORE the
              // ring and ghost below add content of their own.
              // `reachable` is the rounds test, and it is what splits `infeasible` into its two
              // real meanings for both the ink and the sentence (see GRADE_INK).
              var reachable = canLand(ev, parseInt(td.getAttribute("data-di"), 10));
              td.setAttribute("data-fm2", g.grade);
              td.title = costLine(g, fday[ev] === dt, reachable);
              // ⚠ INK IS A FILL AND GOES ONLY WHERE THE BOARD DREW NOTHING — that is what keeps
              // the shipped round shading intact. THE STRIKE IS AN OVERLAY, NOT A FILL: it is a
              // `background-image` riding on top of whatever ground the cell already has, so a
              // day the week refuses is marked even under a round label. Measured on the 2027
              // field: 14 of the 63 refused days sit on a labelled cell, and marking only the
              // blank ones would have left the same invisibility on those fourteen. The cell
              // still reads "QF" and still computes its shipped background colour, which is what
              // `fmap2_proposal`'s shading check grades.
              if (!td.textContent) td.className += GRADE_INK(g, reachable);
              else if (g.grade === "infeasible" && reachable) td.className += " fm2-refused";
            }
            if (!note) return;
            // The ring marks the day the division is MAPPED to and does not hold. Painted only
            // while the map still says so — once the TD moves the division the flag is stale,
            // and a decoration that outlived its fact would be worse than none.
            if (fday[ev] === note.mapped && dt === note.mapped){
              td.className += " fm2-ring";
              td.innerHTML = td.innerHTML + '<span class="fm2-bang">!</span>';
            }
            if (note.landed && fday[ev] !== note.landed && dt === note.landed){
              td.className += " fm2-ghost";
              // APPEND, never overwrite: the landed day is normally past the division's last
              // round and empty, but it is not guaranteed to be, and a decoration that erased a
              // real round label would be hiding the board to annotate it.
              td.innerHTML = (td.textContent ? td.innerHTML + " " : "")
                           + '<span class="fm2-ghostf">F</span>';
            }
          });
          if (note && !note.landed && fday[ev] === note.mapped){
            var lbl = tr.querySelector("td.div");
            if (lbl) lbl.innerHTML = lbl.innerHTML
              + '<span class="fm2-tag" title="' + esc(note.cause) + '">see note</span>';
          }
        });
        // the chip is repainted with the board, not once at load — it carries the drift count,
        // and a chip that only ever ran on arrival is precisely how it went on asserting
        // "47 of 50 hold as mapped" two drags later.
        chip();
        cards();
      }

      // ⚠ A moved division's card STAYS. It used to be filtered out, so dragging the flagged
      // division made its warning disappear — which reads as "you fixed it" when what happened
      // is "nobody has checked the new day" (Operator review, 8/16). It stays, marked.
      function live(){
        return FM2.notes.filter(function(n){ return !dismissed[n.event]; });
      }
      function cards(){
        var panel = document.getElementById("fm2panel");
        if (!panel) return;
        var open = live(), h = [], drift = movedSince().length;
        // ⚠ the bar counts the cards that HAVE a day to propose AND still sit where they were
        // graded, not the flagged ones. Gating on the flagged count printed "… for all 1" on the
        // committed field, where three divisions are flagged and only one has a day to move to
        // (Operator review, 8/16). The label then read "Use the engine's days for all N" and was
        // reworded at BRAND-1 for sentence rule 3; the counting defect this note records is
        // unrelated to that rewording and is still fixed.
        var adoptable = open.filter(function(n){
          return n.landed && fday[n.event] === n.mapped; });
        // SKIN-FIN-1 (Operator ruling 5, 8/27): the rail says what it is and carries the
        // adopt-all on the same line. Rendered only when there is something in it — a rail
        // headed "Needs a look · 0" is a heading for an empty room.
        if (open.length)
          h.push('<div class="fm2-panelhead"><h2>Needs a look \\u00b7 ' + open.length + '</h2>'
                 + (adoptable.length > 1
                    ? '<button type="button" class="fm2-adopt-all">Use the proposed days for all '
                      + adoptable.length + '</button>'
                    : '')
                 + '</div>');
        if (drift)
          h.push('<div class="fm2-banner">These notes and the marks on the board describe the '
                 + 'days this board was built with. You have moved ' + drift
                 + (drift === 1 ? ' division' : ' divisions') + ' since, so nothing here has '
                 + 'been checked against what is on screen now. Press <b>Save my finals days</b>, '
                 + 'paste the block back, and the check runs again on the days you chose.</div>');
        open.forEach(function(n){
          // a card whose own division has moved keeps its facts and loses its buttons: the
          // proposal was computed for a board this one is no longer on.
          var wasMoved = fday[n.event] !== n.mapped;
          h.push('<div class="fm2-card' + (wasMoved ? ' fm2-was-moved' : '')
                 + '" data-ev="' + esc(n.event) + '">'
                 + '<h3>' + esc(n.event) + '</h3>'
                 + (wasMoved
                    ? '<p class="fm2-movedline">You moved this to ' + shortDate(fday[n.event])
                      + '. That day has not been checked.</p>'
                    : '')
                 + '<p class="fm2-cause">' + esc(n.cause) + '</p>'
                 + (n.landed && !wasMoved
                    ? '<button type="button" class="fm2-adopt" data-ev="' + esc(n.event)
                      + '" data-day="' + esc(n.landed) + '">Move it to '
                      + shortDate(n.landed) + '</button>'
                    : '')
                 + (wasMoved ? ''
                    : '<button type="button" class="fm2-keep" data-ev="' + esc(n.event) + '">'
                      + (n.landed ? 'Keep ' + shortDate(n.mapped) : 'Got it') + '</button>')
                 + '</div>');
        });
        panel.innerHTML = h.join("");
        layout();
        Array.prototype.forEach.call(panel.querySelectorAll("button.fm2-adopt"), function(b){
          b.addEventListener("click", function(){
            // the SHIPPED mechanic and nothing else — same call the click-to-place path makes
            moveFinal(b.getAttribute("data-ev"), DATES.indexOf(b.getAttribute("data-day")));
          });
        });
        Array.prototype.forEach.call(panel.querySelectorAll("button.fm2-keep"), function(b){
          b.addEventListener("click", function(){
            // keeping is legal — the map is untouched and the TD's day stands (report, never refuse)
            dismissed[b.getAttribute("data-ev")] = true; cards();
            announce("Keeping the day you mapped.");
          });
        });
        var all = panel.querySelector("button.fm2-adopt-all");
        if (all) all.addEventListener("click", function(){
          // the same set the bar counted — never a division the TD has already placed himself
          adoptable.forEach(function(n){ moveFinal(n.event, DATES.indexOf(n.landed)); });
        });
      }

      // ---- the fixed lane's geometry (Operator ruling, 8/16) --------------------------------
      // CSS cannot see the table's width, so the card rail is seated here: it hugs the grid's
      // right edge. Re-run on every render and resize (both already route through cards()).
      // ⚠ SKIN-FIN-1: THE LEGEND IS NO LONGER IN THIS LANE. It is a strip in the sticky band
      // (8/27 ruling 3), so the whole fold/measure/re-seat branch this function used to carry —
      // the 150px paper floor, the `fm2-lgd-flow` mode swap, the re-sync on a mode change — is
      // gone with it. What is left is the one panel that was always fixed.
      function layout(){
        var panel = document.getElementById("fm2panel"),
            board = document.getElementById("fboard");
        if (!panel || !board) return;
        // clear the chip strip as well as the band: the strip is INSIDE the band now, so the
        // band's own bottom already covers it — the max() is kept because it costs nothing and
        // is what stopped the verdict chip being born clipped under the first card.
        var strip = document.querySelector("p.strip");
        var top = Math.round(Math.max(
              document.querySelector(".stickytop").getBoundingClientRect().bottom,
              strip ? strip.getBoundingClientRect().bottom : 0)) + 10;
        panel.style.top = top + "px";
        if (!window.matchMedia("(max-width:1099px)").matches)
          panel.style.left = (Math.round(board.getBoundingClientRect().right) + 12) + "px";
      }

      // ---- the legend: the three ruled lines (Operator ruling, 8/27) ------------------------
      // Built once: it describes the classes, not the data. The swatches carry the REAL classes
      // `GRADE_INK` puts on the board, so a re-ruled shade repaints here for free and the two
      // can never disagree.
      // ⚠ THE THREE SENTENCES ARE VERBATIM AND ARE NOT PARAPHRASABLE. "Overloads a day" was
      // ruled against "Costs a court" (not language to put in front of a director) and against
      // "Many matches shift" (wrong: pink is a difference in kind, not of volume). Nothing else
      // goes in this strip — the 8/16 legend's other ten entries were deleted on the same
      // ruling, and every mark they named explains itself on the board or on its card.
      // ⚠ THE GREEN LINE MOVED ON 2026-08-28 (Operator, option 1), and it moved because the
      // colour under it did. It read "Nothing else moves", which is true of no square any board
      // can produce; green now means the move touches no OTHER division, so the line says that
      // and cannot be read as "not one match anywhere". The other two are the 8/27 words,
      // untouched.
      function legendHTML(){
        var rows = [
          ["fm2-hold",    "Only this division moves"],
          ["fm2-moves",   "Reshuffles, still fits"],
          ["fm2-mark",    "Overloads a day"],
          // THE FOURTH LINE (Operator ruling, 8/28, option 1). The 8/27 cut deleted ten marks
          // that explain themselves where they are drawn; a struck square has nothing on it to
          // explain itself, and it is the one square on the board that says the choice has no
          // schedule behind it. Its swatch carries the REAL class, like the other three.
          ["fm2-refused", "No schedule at all"]
        ];
        return rows.map(function(r){
          return '<span class="fm2-lgd-row"><span class="fcell ' + r[0] + '"></span>'
               + '<span class="fm2-lgd-t">' + r[1] + "</span></span>"; }).join("");
      }

      // Wrap the frozen render() rather than editing it: every drag, click-to-place, adopt and
      // reset repaints the board, and the decorations have to survive all four.
      var baseRender = render;
      render = function(){ baseRender(); decorate(); };

      // "Start over" means start over: a card the TD waved away comes back with the days it
      // described. Registered after the frozen handler, which has already reset the map by the
      // time this runs.
      document.getElementById("resetBtn").addEventListener("click", function(){
        dismissed = {}; cards();
      });
      // The locked band wraps at narrow widths, so the panel's offset moves with the window even
      // when nothing re-renders — the same reason the frozen file re-syncs on resize.
      window.addEventListener("resize", cards);

      // The legend has NO behaviour now (8/27 ruling 3): it is a strip inside the sticky band,
      // always on screen, nothing to open or close. It is filled once — but the band it joined
      // is the one the frozen file measures `--stickyH` from, so the board's scroll region has
      // to be re-sized after the strip has a height, or the board is sized against a band that
      // was 3 lines shorter when it was measured.
      var lgdEl = document.getElementById("fm2legend");
      if (lgdEl){
        lgdEl.innerHTML = legendHTML();
        syncStickyHeight();
      }

      // ---- OI-42 (ruling 79's accepted defect, folded in here) -------------------------------
      // When both clipboard paths fail, the instruction used to go ONLY to the aria-live region,
      // which sits at left:-9999px — so a sighted TD whose clipboard is blocked got no visible
      // cue at all. The fix ruling 79 offered and did not take: the button's own label carries
      // the shortcut, in `copyKey()`'s platform form (never a second hardcoded twin), reverting
      // on the same 1.6s timer the success path uses. The aria-live message is unchanged.
      var copyBtn = document.getElementById("copyBtn");
      copyBtn.addEventListener("click", function(){
        setTimeout(function(){
          if (copyBtn.textContent === "Copy" &&
              document.getElementById("out").classList.contains("selected")){
            copyBtn.textContent = "Press " + copyKey();
            setTimeout(function(){ copyBtn.textContent = "Copy"; }, 1600);
          }
        }, 0);
      });

      chip();
      decorate();
    })();
"""


def render_guided_finals_console(plan) -> str:
    """The finals console the run surface writes at Step 2: the frozen renderer's output with
    the verdict drawn on it.

    With no `engine_check` in the plan doc this returns `render_finals_console(plan)` unchanged,
    byte for byte — the layer is not "mostly inert", it does not run at all.
    """
    html = FP.render_finals_console(plan)
    ec = plan.get("engine_check")
    if not ec:
        return html

    for anchor, what in ((ANCHOR_CSS, "stylesheet"), (ANCHOR_CHIP, "chip row"),
                         (ANCHOR_BOARD, "board"), (ANCHOR_JS, "script")):
        _check_anchor(html, anchor, what)

    notes = sorted((n for n in ec.get("notes") or []), key=lambda n: n["event"])
    grid = ec.get("day_grid") or {}
    for ev, row in grid.items():
        bad = sorted({(c or {}).get("grade") for c in row.values()
                      if (c or {}).get("grade") not in _GRADES})
        if bad:
            raise ValueError(f"finals_guidance: unknown day grade(s) for {ev!r}: {bad}")
    # `graded_map` rides into the page so the layer can tell when the board has drifted off the
    # map the verdict was actually run against. Deliberately NOT inferred from `PLAN.finals_day`,
    # which merely happens to equal it today: the verdict's own record of what it graded is the
    # authority, and a future build that grades something else stays honest for free.
    payload = json.dumps({"held": ec["held"], "flagged": ec["flagged"],
                          "graded_map": {ev: ec["graded_map"][ev]
                                         for ev in sorted(ec.get("graded_map") or {})},
                          "notes": notes,
                          "day_grid": {ev: {dt: grid[ev][dt] for dt in sorted(grid[ev])}
                                       for ev in sorted(grid)}},
                         sort_keys=False)

    # The chip joins the EXISTING strip (inside its <p>), and the legend strip follows it —
    # both inside the frozen file's sticky band, which is what pins the legend over the board
    # (8/27 ruling 3). No shipped element is moved or re-parented. The note panel goes in front
    # of the BOARD instead, on its own anchor: it is fixed at wide widths but flows at narrow
    # ones, and a column of cards flowing inside the sticky band would push the board off the
    # screen. The legend's body is filled by legendHTML() at runtime, and the panel is seated
    # by layout().
    chip = ('<span class="chip" id="chipCheck"></span></p>'
            '<div class="fm2-legend" id="fm2legend"></div>')
    html = html.replace(ANCHOR_CSS, CSS + ANCHOR_CSS)
    html = html.replace(ANCHOR_CHIP, ANCHOR_CHIP.replace("</p>", chip))
    html = html.replace(ANCHOR_BOARD, '<aside class="fm2-panel" id="fm2panel"></aside>'
                        + ANCHOR_BOARD)
    html = html.replace(ANCHOR_JS, JS.replace("__FM2__", payload) + ANCHOR_JS)
    return html


def _selftest():
    import wwtc_pipeline as W

    setup = {"schema": "td-setup/v1"}
    plain = W.finals_plan(setup)
    assert "engine_check" not in plain, "the verdict must be opt-in"
    assert render_guided_finals_console(plain) == FP.render_finals_console(plain), \
        "with no verdict the layer must return the frozen renderer's output byte for byte"

    plan = W.finals_plan(setup, engine_check=True, grid_events=["Mixed 80 & over doubles"],
                         progress=False)
    ec = plan["engine_check"]
    html = render_guided_finals_console(plan)
    assert html == render_guided_finals_console(plan), "the guided console must be deterministic"
    for needle in ('id="chipCheck"', 'id="fm2panel"', "fm2-ring", "fm2-ghost", "fm2-adopt",
                   "moveFinal", "copyKey()", 'id="fm2legend"',
                   # SKIN-FIN-1: the three paints and the three ruled legend lines. `fm2-lgd-drop`
                   # went with the 8/16 legend that named the drag affordance.
                   "fm2-hold", "fm2-moves", "fm2-mark", "Only this division moves",
                   "Reshuffles, still fits", "Overloads a day", "Needs a look",
                   "fm2-refused", "No schedule at all"):
        assert needle in html, f"guided console missing {needle!r}"
    # B-1: the layer is as offline as the surface it decorates
    for banned in ("fetch(", "XMLHttpRequest", "WebSocket", "<script src"):
        assert banned not in html, f"guided console must be offline: found {banned!r}"
    # the golden's HDR-1 absence tripwires must survive the injection
    for removed in ('id="confirm"', 'id="warnbox"', 'id="gate"', 'el("gate")'):
        assert removed not in html, f"the layer reinstated {removed!r}"
    # a moved anchor is a loud failure, not a silent half-injection
    try:
        _check_anchor("no anchors here", ANCHOR_CSS, "stylesheet")
        raise AssertionError("a missing anchor must raise")
    except ValueError as e:
        assert "must be re-pinned" in str(e), str(e)
    print(f"finals_guidance: {len(html)//1024} KB, offline, deterministic; "
          f"{ec['held']} held / {ec['flagged']} flagged, {len(ec['notes'])} note(s), "
          f"grid over {len(ec['day_grid'])} division(s); "
          f"no-verdict path byte-identical to the frozen renderer")
    print("finals_guidance self-test OK")


if __name__ == "__main__":
    _selftest()
