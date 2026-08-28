"""ANN-1 — the announced start days: the day the final is played and the day play begins.

Brief `ANN1_announced_days_brief.md` (Operator-approved 2026-08-23, all four decisions settled
the same day). Closes FG-1's detection half and FG-3. Harness: `tests/ann1_announced_days.py`.

WHAT THIS IS FOR. In September the TD approves a finals calendar and announces it. The finals
day travels on the map, so January can look it up. The day first matches BEGIN does not — and
it cannot be worked out again in January, because it is a function of what September estimated
the draws would be, and January has the real draws instead. Re-deriving it in January computes
the day the tool is about to use and compares it against itself, which always agrees. So unless
September writes the start days down, nobody can ever tell whether the promise held. This
writes them down.

S-9 (Operator-approved 2026-08-27, `S9_growth_and_tested_days_brief.md`, both decisions ruled the
same day) added the half that was missing: EVERY division's growth is now tested against the week
being announced, not just the round robins'. Before it, a bracket division's file printed R7's
trigger count and said nothing about whether the day past that trigger exists — and on the 2027
seed one of them does not exist, on the 2026 calibration field seven do not. See
`_bracket_growth_branch`.

S-9 also added the RECORD (decision 2 — the calendar says what it was computed from: the field it
priced, the rules in force, and per division whether its announced day was graded and held, was
flagged, was moved AFTER grading, or was never checked). See `_computed_from`. ⚠ Its three
evidence arguments are all CALLER-SUPPLIED, which is what keeps trap 2 below shut: the plan
carries `engine_check` and is sitting in the same run surface, and by Step 3.6 it describes a
board the TD has already changed. The writer never reads it.

⚠ NO PLAYER-FACING OUTPUT (Operator, 8/20). This module writes arithmetic onto a file. There is
no announcement page, no PDF and no HTML — the director writes his own announcement off the
file. Nothing here is a deliverable a fabricated entrant could reach (BUDGET-1 R-B2).

⚠ NOTHING READS THIS YET, AND THAT IS THE DESIGN. Every reader is January's (GATE-1, RECON-1,
BADGE-1), and every one is deliberately outside this build. What this module leaves them is a
record, not a route.

WHERE IT LIVES, AND WHY IT IS A THIRD FILE.
  · NOT `finals_plan.py` — FROZEN (D-3), four narrow waivers spent, and none is asked for here.
  · NOT `finals_guidance.py` — its stated contract is that with `engine_check` absent the layer
    does not run AT ALL, and `tests/fmap2_proposal.py` part D asserts byte-identity against the
    frozen renderer. Nothing here may weaken that.
  · NOT `finals_publish.py` — that module is the publish STAMP (who announced it, and when).
    This one is what was announced. They nest (decision 3) but they are not the same fact, and
    a September run can legitimately stamp without announcing days.

DETERMINISM IS A HARD INVARIANT (`CLAUDE.md`). `announced_days` reads no clock and no file:
same inputs, same bytes. The one function here that touches the disk is `watchlist_rows`, which
is where R7's arithmetic is CALLED — it is deliberately a separate, explicit call so the writer
itself stays pure.

⚠ TWO TRAPS THIS MODULE EXISTS ON THE RIGHT SIDE OF.

  1. `finals day − (rounds − 1)` IS THE WRONG ARITHMETIC, and it agrees with the cascade on 50
     of 50 divisions on every field committed to this repo. It is wrong on every division the
     TD names in `same_day_finish`: `master_schedule._lay_out` joins a named division's last
     two rounds, so its cascade spans one fewer day than it has rounds, and the formula
     announces it a DAY EARLY. `wwtc_pipeline._finals_pins` is the one other site in the
     product that compensates (REVIEW-1/M10 found it producing a FALSE refusal there). NOTHING
     HERE COMPUTES THAT FORMULA. Every day this module emits comes out of the shipped cascade —
     `master_schedule.build_master_schedule` — including the hypothetical branches, which are
     derived by re-running that same cascade over a hypothetical round count rather than by
     adding or subtracting days. `tests/ann1_announced_days.py` part B asserts the DIFFERENCE,
     so a later "simplification" back to the formula fails loudly.

  2. THE CONVENIENT SOURCE IS THE STALE ONE. At runbook Step 3 the run surface holds two
     things: Step 2's `td-finals-plan/v1`, which already carries `round_day`, and the
     `td-finals-map/v1` block the TD has just pasted back after dragging finals around. Reading
     the plan announces 8 of 50 divisions wrong on the real committed record
     `reference/runs/2026-08-15/finals_map.json`, one of them by two days. THIS MODULE TAKES
     THE COURIERED DOCUMENT AND RE-DERIVES THE CASCADE UNDER ITS PINS. Part C drives that file.

⚠ THE VALIDATOR DROPS THIS KEY AT THE GATE, exactly as it drops PUB-1's stamp.
`finals_plan.finals_map_from_doc` ends `return dict(fmap)` — it returns the finals map and
nothing else. So no module downstream of the courier gate can see this key and none can change
behaviour because of it, which is the whole compatibility guarantee. It is also the constraint
the January family inherits: a reader of the announced days must read the couriered DOCUMENT,
never the validator's return value. `start_days_of(doc)` is the accessor, and it reads the
document through `finals_publish.announced_of` rather than by key.
"""
import master_schedule as MS

KEY = "start_days"

# S-9 decision 2 (Operator, 2026-08-27, option 1 — THE FULL RECORD). The key, beside `start_days`
# and inside PUB-1's `announced`: what the announced calendar was COMPUTED FROM. Nothing
# TD-facing ever speaks this name.
RECORD_KEY = "computed_from"

# What the last full check had to say about each division's announced finals day. The four are
# exhaustive by construction and every division gets exactly one.
HELD = "held"                                  # graded by the full check, and it held as mapped
FLAGGED = "flagged"                            # graded, and the check had something to say
MOVED_AFTER_GRADING = "moved_after_grading"    # graded on one day, announced on another
NOT_GRADED = "not_graded"                      # no check ever covered this division's day
DAY_STATUS = (HELD, FLAGGED, MOVED_AFTER_GRADING, NOT_GRADED)

# Decision 1 (Operator, 2026-08-23, option 1). A division announces a SECOND date — the day it
# starts if the draw comes in smaller — only where the smaller bracket is still an elimination
# draw. Below 32 it is not: at 16 the smaller draw is 5–8 entrants and at 8 it is 3–4, and rule
# 22 turns those into round robins, which run MORE rounds than the small bracket they replaced,
# not fewer. So the naive second date there points the WRONG WAY — it promises a later start to
# a division that will begin the same day or two days EARLIER. Those divisions carry one date
# and a recorded threshold instead of a second date and a wrong one.
SOUND_BRACKET_FLOOR = 32

# `master_schedule._lay_out`'s own words when a division's rounds run off the front of the
# window. ⚠ PIN THE STRING, NEVER THE LINE NUMBER (the OI-19 lesson) — this is how the module
# tells "one step up the ladder starts earlier" from "one step up the ladder does not fit at
# all", which is the difference between a date and a sentence in what a director is told.
_PRE_WINDOW = "do not fit before finals"

# Decision 2 as amended (Operator, 2026-08-23). The sentence a flagged round robin carries in
# place of a date it cannot honestly be given. Plain English, because the runbook reads it back
# to the director verbatim and it is the one September finding he can still act on.
NO_ROOM_NOTE = ("if this division runs as one group next January, the week as planned has no "
                "room for it")
NO_COUNT_NOTE = ("this division's entry count was not supplied, so the earliest it could begin "
                 "was not worked out")

# S-9 decision 1 (Operator, 2026-08-27, option 1 — CONVERGE). The elimination division's own
# no-room sentence, approved with the S-9 brief exactly as `NO_ROOM_NOTE` was approved with
# ANN-1's. It is a DIFFERENT sentence from the round robins' because the trigger is a different
# event: a round robin grows when one more person enters, a bracket grows when enough enter to
# push it up a rung. The two are never interchangeable in what a director is being told.
NO_ROOM_BRACKET_NOTE = ("if this division outgrows its bracket next January, the week as planned "
                        "has no room for the extra round it would need")


def watchlist_rows(levels=("1", "2"), fill=1.0):
    """R7's threshold arithmetic, CALLED — never re-implemented (brief open item b, part H).

    `wwtc_pipeline._cb_watchlist` is BUDGET-1's and is used here exactly as it ships: it is the
    one place in the product that knows the registration count at which a division stops
    costing a court and starts costing a whole PLAYING DAY. The director can buy a court; he
    cannot buy a day once the calendar is announced.

    ⚠ THIS IS THE ONE IMPURE FUNCTION IN THIS MODULE — `_cb_watchlist` reads the printed draws.
    It is separate from `announced_days` on purpose, so the writer itself reads no file and the
    caller can hand the rows in from anywhere (a September run, a harness, a projected field).

    `fill` is R7's assumed registration fraction; at 1.0 every division is read at its printed
    bracket, which is what September assumes when it announces on last year's shape.
    """
    import wwtc_pipeline as W
    out = {"watchlist": [], "not_tried": []}
    W._cb_watchlist(levels, (), fill, out)
    return out["watchlist"]


def rules_record_from_setup(setup):
    """S-9 · the RULES half of the record — the pipeline's own resolver, CALLED.

    `wwtc_pipeline._paired_rules` is S-7's and is used here exactly as it ships, so there is one
    implementation of "whose rules produced this" in the product and never a second. It returns
    `{source, digest, keys}`: `caller` where the director's own rules were handed over, `defaults`
    where the tool's rulebook was legitimately meant.

    ⚠ IT REFUSES A SLATE WITH NO RULES BESIDE IT, AND THAT REFUSAL IS THE POINT — it must
    propagate. A September run holding the director's dates but not his rules would otherwise
    stamp the ENGINE's rulebook onto the calendar and label it his. S-7 measured that exact case
    on the committed 2027 seed: 0 of his 15 rule keys reached the search.

    Called by the RUN, like `same_day_finish_from_setup`, so this module's writer keeps reading
    no file and no global state.
    """
    import wwtc_pipeline as W
    _doc, record = W._paired_rules(setup.get("constraints"), setup.get("slate"))
    return record


def rr_entrants_from_draws(draws):
    """{event: entrants} for the round-robin divisions, off an already-parsed draws list.

    Pure — it reads no file; the caller has already parsed. The entrant count is what decision
    2's earliest-possible date steps up from, and it cannot be recovered from a `Division`: a
    round robin carries `draw_size: 0`, and a round count of 3 could be a group of 3 or a group
    of 4. Rule 22 stands throughout — the format and the grouping are READ off the printed
    draw, never chosen.
    """
    return {d.event: sum(len(g.members) for g in d.groups)
            for d in draws if getattr(d, "fmt", None) == "round_robin"}


def same_day_finish_from_setup(setup, divisions):
    """The resolved `same_day_finish` division names for a couriered `td-setup/v1`.

    ⚠ THE ONE ARGUMENT A CALLER MUST NOT FORGET. Omit it and every division the TD has named
    is announced a DAY EARLY (trap 1 in this module's header). This is the shipped resolver
    (`wwtc_pipeline._resolve_same_day_finish`), called the way the build and plan lanes call it,
    so there is one obvious right way to obtain the names and no second implementation of the
    name matching. Resolution warnings are dropped here on purpose, exactly as `_finals_pins`
    drops them: the build and plan lanes resolve the same names and report them, and a name that
    does not resolve does not join the cascade either — so the announcement still matches the day
    the tool will play.
    """
    import wwtc_pipeline as W
    con = setup.get("constraints") or W.default_constraints()
    return list(W._resolve_same_day_finish(
        (con.get("same_day_finish") or {}).get("divisions"), divisions, []))


def _cascade(divisions, dates, finals_map, same_day_finish):
    """The shipped cascade, re-run under the couriered map's pins. Read-only projection."""
    return MS.build_master_schedule(divisions, dates, finals_map=dict(finals_map),
                                    same_day_finish=same_day_finish)


def _first_day(round_day, event, dates):
    """The day first matches begin — the earliest day the cascade gives this division.

    Read off `round_day`, which is the cascade's own record of which day each round is on. Never
    `finals − (rounds − 1)`: see trap 1.
    """
    return min(round_day[event].values(), key=lambda dt: dates.index(dt))


def _hypothetical_start(div, rounds, final, dates, joined):
    """Re-run the SHIPPED cascade for one division at a hypothetical round count.

    Returns the day it would begin, or None where the week as planned cannot hold it. This is
    how both branches are derived — the smaller-draw date and the round robins' earliest
    possible start — so neither is a day added to or subtracted from another date, and both
    honour the same-day-finish collapse without this module knowing anything about it.
    """
    if rounds < 1:
        return None
    hypo = MS.Division(event=div.event, fmt=div.fmt, draw_size=div.draw_size,
                       rounds=rounds, age=div.age, etype=div.etype)
    try:
        ms = _cascade([hypo], dates, {div.event: final},
                      [div.event] if joined else None)
    except ValueError:
        # `build_master_schedule`'s OI-43 guard: the window has fewer days than the division
        # has rounds, so it cannot be laid out at all. That is "the week has no room", loudly.
        return None
    if any(w.startswith(div.event + ":") and _PRE_WINDOW in w for w in ms.warnings):
        return None
    return _first_day(ms.round_day, div.event, dates)


def announced_days(doc, divisions, dates, same_day_finish=None, watchlist=None,
                   rr_entrants=None, strict=True):
    """Per division, what September announces: the finals day and the day play begins.

    doc              : the COURIERED `td-finals-map/v1` — the block the TD pasted back, not
                       Step 2's plan (trap 2). Its `finals_map` drives the cascade.
    divisions        : the `master_schedule.Division` list for the field being announced —
                       January's, or September's projection of it.
    dates            : the slate's tournament days, in order.
    same_day_finish  : the RESOLVED division names the TD has flipped the switch on. ⚠ Omit it
                       and every named division is announced a day EARLY (trap 1).
                       `same_day_finish_from_setup` is the one obvious way to get them.
    watchlist        : R7's rows from `watchlist_rows()`. Absent, the threshold figures are
                       null — this module never re-implements that arithmetic to fill them in.
    rr_entrants      : {event: entrants} from `rr_entrants_from_draws`. Absent, a round robin
                       is still flagged but its earliest-possible day says why it is missing.
    strict           : refuse a map naming a division that is not in `divisions`, or pinned
                       outside the slate window. False skips those instead — for replaying an
                       archived record against a field it was not written for.

    Returns {event: record}. Reads no clock and no file: same inputs, same bytes.
    """
    fmap = _finals_map_of(doc)
    known = {d.event: d for d in divisions}
    joined = {str(e) for e in (same_day_finish or ())}
    r7 = {row["division"]: row for row in (watchlist or ())}
    ent = dict(rr_entrants or {})

    events, skipped = [], []
    for ev in sorted(fmap):
        if ev not in known:
            skipped.append(f"{ev}: not a division of this field")
        elif fmap[ev] not in dates:
            skipped.append(f"{ev}: announced {fmap[ev]}, which is not a day of this tournament")
        else:
            events.append(ev)
    if skipped and strict:
        raise ValueError("cannot announce this map — " + "; ".join(skipped))
    if not events:
        raise ValueError("cannot announce this map — none of its divisions is in this field")

    ms = _cascade([known[ev] for ev in events], dates, {ev: fmap[ev] for ev in events},
                  sorted(joined))
    out = {}
    for ev in events:
        div = known[ev]
        final = fmap[ev]
        out[ev] = _record(div, final, _first_day(ms.round_day, ev, dates), dates,
                          ev in joined, r7.get(ev), ent.get(ev))
    return out


def _record(div, final, first_match, dates, joined, row, entrants):
    """One division's announced line."""
    rr = div.fmt == "round_robin"
    rec = {
        "final": final,
        "first_match": first_match,
        "first_match_if_smaller": None,
        # R7's own figures, verbatim from `_cb_watchlist`'s row. A round robin has no bracket
        # for that ladder to speak about, so these stay null rather than being invented — its
        # uncertainty is `format_assumed` and the earliest-possible day, which is a different
        # and larger question than one more entrant.
        #
        # ⚠ S-4 (2026-08-25, OPERATOR-RULED — the one waiver this build asked for). This block
        # was written when R7 SKIPPED round robins outright, so "no bracket" and "no row" were
        # the same condition and `if row` tested both at once. S-4 §3.6 was ruled to end that
        # silence: a round robin now HAS a row, carrying its group shape and the entrant count
        # at which one more adds a round, with `bracket` and `next_bracket` null because it
        # genuinely has neither. The guards therefore test the FIGURE rather than the row's
        # existence, which is what the paragraph above always meant.
        #
        # ⚠ NOTHING THIS FILE EMITS MOVES, and that was measured before the waiver was asked
        # for: with the guards on the figures, every part of `tests/ann1_announced_days.py` that
        # grades this module's OUTPUT reproduces, including part F's round-robin ladder — 5 of 8
        # starting two days earlier, 1 unchanged, 2 the week cannot hold. The alternative was to
        # take round robins back off the warning list, which would have restored exactly the
        # silence S-4 was ruled to end, on the one page whose job is to say what is close to
        # costing a playing day. Options put to the Operator, option 1 taken.
        "assumed_draw": row["bracket"] if row else None,
        # The same ladder read DOWNWARD. R7's `next_bracket` is the rung above the printed
        # bracket, so a quarter of it is the rung below — the entry count at or under which the
        # smaller draw applies. One ladder, read both ways; never a second implementation.
        "smaller_branch_applies_at": ((row["next_bracket"] // 4)
                                      if row and row["next_bracket"] else None),
        "bigger_draw_costs_a_day_at": row["costs_a_day_at"] if row and row["bracket"] else None,
        "format": div.fmt,
        # Decision 2: a round robin's shape — how many groups, and how big — is a desk decision
        # made in January off the printed draw, so September is assuming last year's. An
        # elimination division's format is read off a printed bracket and is not in question.
        "format_assumed": rr,
        # ⚠ S-9 decision 1 (Operator, 2026-08-27, option 1 — CONVERGE). EVERY division's growth
        # answer lives in this ONE pair of fields: the earliest day it could begin if it grows,
        # or `null` and a sentence where the week as planned cannot hold it. Until S-9 only the
        # round robins filled them in and every bracket division left them blank — so a reader
        # had to know what kind of division it was looking at before it could find the answer,
        # and for a bracket division there was no answer to find. What GROWS is different per
        # family (a round robin takes one more entrant, a bracket takes a whole extra round) and
        # `format` beside it says which; WHETHER HIS WEEK CAN HOLD IT is the same question for
        # all 56, asked once and answered in one place.
        "earliest_possible_start": None,
        "earliest_possible_note": None,
    }
    if rr:
        _round_robin_branch(rec, div, final, dates, joined, entrants)
    elif row and row["bracket"] >= SOUND_BRACKET_FLOOR:
        # Decision 1: the smaller draw is 16 or more here and is always an elimination draw, so
        # it is one round shallower and starts one day LATER. Derived by re-running the shipped
        # cascade at that round count, never by adding a day to anything.
        smaller = _hypothetical_start(div, div.rounds - 1, final, dates, joined)
        # Open item (d): two identical dates read as a mistake, so a branch that lands on the
        # announced day prints as one date, not two.
        rec["first_match_if_smaller"] = smaller if smaller != first_match else None
    if not rr:
        _bracket_growth_branch(rec, div, final, dates, joined)
    return rec


def _round_robin_branch(rec, div, final, dates, joined, entrants):
    """Decision 2 AS AMENDED — the flag carries the earliest possible start day.

    Reading C, the ruled one (brief §0.9a): ONE group, one more entrant than last year. That is
    the smallest change in entries the ladder can take, and it is where the surprise lives —
    a round robin's rounds step 3 → 5 → 7 as the largest group goes 4 → 5 or 6 → 7 or 8, so one
    extra person can pull a division's start TWO DAYS earlier than the day it was announced on.
    The two readings that were rejected are worth recording: one group at last year's own count
    merely repeats the announced day, and "the earliest the week could possibly hold" is the
    first day of the tournament dressed up as arithmetic.

    ⚠ WHERE THAT STEP WILL NOT FIT, THE FIELD IS `null` AND THE NOTE SAYS SO IN WORDS. Printing
    a date the week cannot hold would be a fabrication, and the fact is the more serious of the
    two warnings: for those divisions the next step up the ladder does not start early, it
    refuses the week outright — in January, after the announcement has gone out.
    """
    if not entrants:
        rec["earliest_possible_note"] = NO_COUNT_NOTE
        return
    # `_rr_rounds` is `master_schedule`'s own ladder, called rather than restated: m − 1 rounds
    # for an even group and m for an odd one.
    start = _hypothetical_start(div, MS._rr_rounds(entrants + 1), final, dates, joined)
    if start is None:
        rec["earliest_possible_note"] = NO_ROOM_NOTE
    else:
        rec["earliest_possible_start"] = start


def _bracket_growth_branch(rec, div, final, dates, joined):
    """S-9 — an elimination division's growth answer, TESTED against the week he is announcing.

    The asymmetry this closes. A round robin's growth has been tested against the window since
    ANN-1: `_round_robin_branch` re-runs the shipped cascade one step up the ladder and writes a
    sentence where it does not fit. A bracket division's growth was never tested at all — the
    file printed `bigger_draw_costs_a_day_at`, R7's TRIGGER figure, and left the reader to assume
    the day past that trigger exists. On the 2027 seed one of them does not (`Mixed 85 & over
    doubles`, whose bracket fills the week in front of its final); on the 2026 calibration field
    seven do not, every one of them starting on day 1 with its rounds exactly filling the space.
    Each of those printed a threshold as if the extra day were there for the taking.

    ⚠ `bigger_draw_costs_a_day_at` IS NOT WRONG AND IS NOT TOUCHED. It is right about the trigger
    on every division: that IS the entry count at which the draw costs a playing day. What was
    never checked is whether the week HAS the day to spend. The figure gains a companion here; it
    is never deleted and never re-implemented (S-9 §2.1, R7 stays the one implementation).

    Decision 1 (Operator, 2026-08-27, option 1 — CONVERGE): the answer rides the SAME two fields
    the round robins already use, so a reader asks one question for all 56 divisions and never
    has to know what kind of division it is looking at before finding the answer. The format is
    on the record beside it (`format`) where a reader who needs to know WHICH growth trigger this
    is can see it.

    ⚠ ONE MORE ROUND, NOT ONE MORE ENTRANT. The step is `div.rounds + 1` — the next rung of the
    bracket ladder — because that is what a bracket division's growth costs: a whole round. It is
    re-run through the SHIPPED cascade like every other day this module emits, never
    `first_match − 1` (trap 1 in the header: the formula agrees until the day it does not).

    ⚠ AND WHERE THERE IS NO ROOM, THE FIELD IS `null` AND THE NOTE SAYS SO IN WORDS — the same
    discipline `_round_robin_branch` ships on. A fabricated date here would be the one number in
    the whole announcement step a director would act on and be wrong about.

    This runs for EVERY elimination division, including one R7 gave no usable threshold for
    (measured exposure: zero on both benches, guarded anyway). Whether the week can hold another
    round is a fact about HIS WEEK and is independent of the trigger count that would set it off,
    so the day is carried either way and the threshold stays `null` exactly as it does today.
    """
    start = _hypothetical_start(div, div.rounds + 1, final, dates, joined)
    if start is None:
        rec["earliest_possible_note"] = NO_ROOM_BRACKET_NOTE
    else:
        rec["earliest_possible_start"] = start


def _computed_from(days, field_source, rules, engine_check):
    """S-9 · what the announced calendar was computed from, or None where nothing was supplied.

    Three blocks, every one derived from something that already exists — this is a RECORD, never
    new machinery (the queue's own words). Absent every evidence argument it returns None and the
    emitted document is byte-identical to what ANN-1 shipped.

    ⚠ TRAP 2, REOPENED BY THIS FUNCTION AND CLOSED HERE. The convenient source is the stale one.
    Step 2's plan is sitting right there in the run surface carrying `engine_check`, and reaching
    into it from inside this writer is exactly the mistake ANN-1's header names: by Step 3.6 the
    TD has dragged finals around and the plan describes a board he has already changed. So THE
    CALLER HANDS THE BLOCK OVER, explicitly, and this function never sees a plan. A future edit
    that reaches for `plan` in here re-opens a measured defect.

    ⚠ AND THE FIELD'S SOURCE IS AN ARGUMENT, never `projected_field.installed()`. Reading global
    state would make the same call produce different bytes depending on what a previous step left
    installed, which breaks the module's determinism invariant outright.

    The per-division verdict is the one thing here that is derived rather than copied, and it is a
    dict comparison: the day the check GRADED against the day being ANNOUNCED. That is what makes
    a declined recheck legible — the days the director moved after grading go out MARKED instead
    of going out silently. The decline is RECORDED, never refused (§11.3 q2: refusing was S-6's
    and S-7's half of the chain, and both shipped; a director is entitled to decline, and the
    8/25 run is the measured case of him doing it — six of fifty finals days moved after grading,
    with nothing on the calendar able to say which six).
    """
    if field_source is None and rules is None and engine_check is None:
        return None

    ec = engine_check if isinstance(engine_check, dict) else {}
    # A REFUSED week carries `{"refused": ...}` and no `graded_map` — it graded nothing, so every
    # division reads `not_graded`, which is the honest answer and not a special case.
    graded = ec.get("graded_map") or {}
    flagged_evs = {n.get("event") for n in (ec.get("notes") or []) if isinstance(n, dict)}

    finals_days = {}
    for ev in sorted(days):
        if ev not in graded:
            finals_days[ev] = NOT_GRADED
        elif graded[ev] != days[ev]["final"]:
            finals_days[ev] = MOVED_AFTER_GRADING
        elif ev in flagged_evs:
            finals_days[ev] = FLAGGED
        else:
            finals_days[ev] = HELD

    record = {"finals_days": finals_days}
    if field_source is not None:
        record["field"] = {"divisions": len(days), "source": field_source}
    if rules is not None:
        record["rules"] = dict(rules)
    return record


def computed_from_of(doc):
    """S-9's record on a couriered DOCUMENT, or None.

    ⚠ WHAT THIS IS AND WHAT IT IS NOT — say both halves, the way the publish digest's two halves
    are always said together. It is an honest record of what produced the calendar: the field it
    priced, the rules in force, and which announced days a full check had actually covered. It is
    NOT a signature. It is written by whoever runs the announce step and proves nothing about
    who; a hand edit of the record itself is caught by nothing, because PUB-1's digest is taken
    over the solved map and not over this. A run that oversells it teaches a director to trust a
    record that cannot carry the weight.

    ⚠ Read the DOCUMENT — `finals_plan.finals_map_from_doc` drops the whole `announced` block at
    the gate, this key with it (the constraint January's readers inherit).
    """
    import finals_publish as PUB
    ann = PUB.announced_of(doc)
    if not ann:
        return None
    got = ann.get(RECORD_KEY)
    return got if isinstance(got, dict) else None


def announce_finals_map(doc, divisions, dates, same_day_finish=None, watchlist=None,
                        rr_entrants=None, strict=True, replace=False,
                        field_source=None, rules=None, engine_check=None):
    """Return a NEW `td-finals-map/v1` carrying the announced days. The input is never mutated.

    Decision 3 (Operator, 2026-08-23, option 1): `start_days` nests INSIDE PUB-1's `announced`.
    One promise, one object — a file cannot end up carrying the date it was announced without
    the days that were announced, or the other way round. So a document that has not been
    stamped is REFUSED here, naming the step that comes first: announcing days on an unstamped
    map would write half a promise.

    `replace` — re-announce a document that already carries days. Announcing twice is a
    decision, never a silent overwrite, so the default refuses and names the days at stake — and
    names the record beside them where the file carries one, because that is at stake too.

    S-9's three EVIDENCE arguments, all optional and all supplied by the caller (decision 2,
    Operator 2026-08-27). Absent every one of them the emitted document is byte-identical to what
    ANN-1 shipped; supplied, the file also says what the calendar was computed from:

    field_source : `"projected"` (September's estimate of the field) or `"drawn"` (real printed
                   draws). ⚠ An ARGUMENT — never read from `projected_field.installed()`, whose
                   value depends on what an earlier step left behind.
    rules        : S-7's `{source, digest, keys}` block. `rules_record_from_setup(setup)` is the
                   one obvious way to get it.
    engine_check : the plan's `engine_check` block, handed over BY THE CALLER. ⚠ Never read from
                   the plan in here — by this step the TD has dragged finals and the plan
                   describes a board he has already changed (trap 2).

    ⚠ THE RECORD ALWAYS DESCRIBES *THIS* CALL. On a deliberate `replace` it is rewritten from the
    arguments given, and REMOVED where none are — a file never keeps a record of a call that no
    longer produced it. A stale record is worse than none: it is the only thing on the file a
    reader would trust to say which days were checked.
    """
    _finals_map_of(doc)                                  # schema first, loudly
    import finals_publish as PUB
    prior_stamp = PUB.announced_of(doc)
    if prior_stamp is None:
        raise ValueError(
            f"this {_SCHEMA()} has not been announced yet, so there is nothing for the start "
            f"days to ride on. Stamp it first with finals_publish.stamp_finals_map(doc, "
            f"published_on=...), then announce the days.")
    prior = prior_stamp.get(KEY)
    if prior is not None and not replace:
        also = (" It also carries a record of what produced them, which would go with them."
                if prior_stamp.get(RECORD_KEY) is not None else "")
        raise ValueError(
            f"this {_SCHEMA()} already carries announced start days for {len(prior)} "
            f"division{'' if len(prior) == 1 else 's'}. Announcing again would overwrite them."
            f"{also} Pass replace=True to do it deliberately.")

    days = announced_days(doc, divisions, dates, same_day_finish=same_day_finish,
                          watchlist=watchlist, rr_entrants=rr_entrants, strict=strict)
    out = dict(doc)
    stamp = dict(prior_stamp)
    stamp[KEY] = days
    record = _computed_from(days, field_source, rules, engine_check)
    if record is None:
        stamp.pop(RECORD_KEY, None)
    else:
        stamp[RECORD_KEY] = record
    out[PUB.KEY] = stamp
    return out


def start_days_of(doc):
    """The announced start days on a couriered DOCUMENT, or None.

    ⚠ For January's readers (GATE-1 / RECON-1 / BADGE-1). Read the DOCUMENT — the validator
    `finals_plan.finals_map_from_doc` returns `dict(fmap)` and drops the whole `announced`
    block at the gate, so a reader that reaches for the validator's output finds the days gone
    and will not know why. This goes through `finals_publish.announced_of` rather than indexing
    by key, so the two builds' records stay one object with one accessor path.
    """
    import finals_publish as PUB
    ann = PUB.announced_of(doc)
    if not ann:
        return None
    got = ann.get(KEY)
    return got if isinstance(got, dict) else None


def _SCHEMA():
    import finals_plan as FP
    return FP.FINALS_MAP_SCHEMA


def _finals_map_of(doc):
    """The couriered map, validated in the shipped loud style."""
    import finals_plan as FP
    if not isinstance(doc, dict) or doc.get("schema") != FP.FINALS_MAP_SCHEMA:
        got = doc.get("schema") if isinstance(doc, dict) else type(doc).__name__
        raise ValueError(f"expected a {FP.FINALS_MAP_SCHEMA} doc, got: {got}")
    fmap = doc.get("finals_map")
    if not isinstance(fmap, dict) or not fmap:
        raise ValueError(f"{FP.FINALS_MAP_SCHEMA}: finals_map is missing or empty")
    return fmap
