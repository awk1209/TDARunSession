"""wwtc_pipeline.py — the real-data end-to-end pipeline, tying R1 ingest + R2 slate + R3 rules
into one entry point for the consoles and outputs (R4/R5/R6).

  finalized draw + player lists  (R1: wwtc_ingest.load_from_finalized_draws)
    -> authoritative WWTC slate  (R2a: §8 — MHCC all days; ORLP Jan 24-26; WEST Jan 27 & 30)
    -> TD constraints + rules     (R2b locality + R3 AVOID-3/BP-2)
    -> zero-conflict schedule      (scheduler_multi)

`build(level, ...)` returns everything downstream needs; `editor_plan_for` projects the
`td-editor-plan/v1` the Edit console loads (optionally scoped to one day — the "first-day board").
Read-only over the engine; deterministic.
"""
from __future__ import annotations

import collections
import copy
import datetime
import hashlib
import json
import math
import re

import constraints as C
import division_order as DO
import draws_pdf
import editor_plan as EP
# S-4 §3.6: the watchlist has to know which of its rows are the director's own estimates, and the
# S-2 seam is the one named place that answers. It imports nothing of anyone's, so consulting it
# here makes no cycle (`field_source`'s own docstring is why it is a module of its own).
import field_source
import finals_plan as FP
import master_schedule as MS
import wwtc_ingest
import resource_slate as RS                      # BUDGET-1 §3.3: the club-ceiling reader
from resource_slate import config_from_slate
from scheduler_flow import _default_plan_id   # EDITBASE-1: ONE definition of the build's id
from scheduler_multi import schedule_multi, _true_round_of as SM_true_round

# WWTC dates (from the draws PDF footer: Jan 23 – Feb 1, 2026).
DATES = ["2026-01-23", "2026-01-24", "2026-01-25", "2026-01-26", "2026-01-27",
         "2026-01-28", "2026-01-29", "2026-01-30", "2026-01-31", "2026-02-01"]
ORLP_DAYS = ["2026-01-24", "2026-01-25", "2026-01-26"]
WEST_DAYS = ["2026-01-27", "2026-01-30"]

# Coachella Valley home-city cluster for the local-player-late rule (R2b default).
# CUI-3 (Operator locality addendum, 2026-08-02): 11 -> 13, purely additive — Mecca and Thermal in,
# none dropped. This list REACHES THE ENGINE (LOCALS-EARLY, scheduler_multi.py:368-369), so it can
# move the schedule. Measured schedule-neutral on the 2026 field ONLY because no 2026 entrant lives
# in Mecca or Thermal — never inherit that zero; re-measure whenever this list changes (DOC-03).
# Supersedes ruling 16's 11-city LOCAL membership. Kept in step with `setup_console.html`'s
# PRESET_CITIES and the build spec's `locality-cluster`, or prefill and default silently diverge.
HOME_CITIES = ["Rancho Mirage", "Palm Desert", "Palm Springs", "Cathedral City", "Indian Wells",
               "La Quinta", "Indio", "Coachella", "Mecca", "Desert Hot Springs", "Thousand Palms",
               "Bermuda Dunes", "Thermal"]

# CUI-3: the COMMUTER tier — the reviewer's revised 75 (supersedes ruling 16's 49-city prose list).
# DISPLAY-ONLY. It reaches NOTHING: no engine path reads it, and none may be added without its own
# Operator sign-off. It exists so the editor's cards can badge a commuting player (C, red).
COMMUTER_CITIES = [
    "Twentynine Palms", "Yucca Valley", "Joshua Tree", "Beaumont", "Hemet", "San Jacinto",
    "Idyllwild", "Temecula", "Murrieta", "Perris", "Moreno Valley", "Riverside", "Corona",
    "Menifee", "Wildomar", "Lake Elsinore", "Norco", "San Bernardino", "Redlands", "Yucaipa",
    "Big Bear Lake", "Fontana", "Rancho Cucamonga", "Ontario", "Chino", "Chino Hills", "Pomona",
    "Claremont", "Diamond Bar", "Walnut", "Anaheim", "Santa Ana", "Irvine", "Orange", "Fullerton",
    "Mission Viejo", "Lake Forest", "Tustin", "Costa Mesa", "Huntington Beach", "Newport Beach",
    "Laguna Beach", "Escondido", "Fallbrook", "San Marcos", "Vista", "Victorville", "Apple Valley",
    "Hesperia", "Barstow", "El Centro", "Brawley", "Calipatria", "Blythe", "Palmdale", "Lancaster",
    "San Diego", "Carlsbad", "Oceanside", "Encinitas", "Poway", "Long Beach", "Los Angeles",
    "Pasadena", "Glendale", "Burbank", "Torrance", "Compton", "Downey", "Whittier", "Santa Monica",
    "Culver City", "El Segundo", "Norwalk", "La Habra"]


def wwtc_slate():
    """The authoritative §8 WWTC resource slate (matches Console 1's default)."""
    def avail(courts, days, morning=None):
        cell = lambda: {"courts": courts, "start": "08:00", "end": "18:00"}
        out = {}
        for d in days:
            c = cell()
            if morning:   # R7-3 (V-5): fewer courts before the switch (member play)
                c["morning_courts"], c["morning_until"] = morning
            out[d] = c
        return out
    return {
        "schema": "td-resource-slate/v1", "tournament": "USTA Wilson World Tennis Classic",
        "dates": DATES, "daily_start": "08:00", "daily_end": "18:00",
        "end_of_day_buffer_minutes": 45, "min_rest_minutes": 30, "min_start_to_start_minutes": 180,
        "locations": [
            # MHCC morning step-up 9->15@11:00: the sourced O1 example, prefilled as a
            # TD-EDITABLE default (CEO 2026-07-25) — the real numbers replace it via the console.
            # VENUE-1 (2026-08-05): the display names are D-49's — the corrections the tournament
            # director gave for his own clubs. `name` became load-bearing at VENUE-1 (it rides the
            # console emit again and reaches the reporter), so the placeholder names it shipped
            # with would now be printed at him. The IDS are untouched and never change.
            # Venue ORDER is the fill order (rule 43); MHCC first == the main site.
            # LIGHTS-1 (2026-08-08) / rule 48: the lit-court COUNT and the hour it starts, the
            # TD's own figures as recorded in PLAN rule 6 (MHCC 7 · ORLP 8 · WEST 4, all 16:00).
            # SLATE-1 makes the pair both-or-neither, so each venue carries both or neither. Until
            # this build the repo's own slate carried NEITHER on any venue, which is why the
            # engine could never see a lit ceiling it was meant to respect: the schema accepted
            # the pair, the console emitted MHCC's, the reporter graded against a hard-coded
            # default, and the one document placement actually reads said nothing at all.
            {"id": "MHCC", "name": "Mission Hills Country Club", "available": avail(24, DATES, morning=(9, "11:00")),
             "lit_courts": 7, "lights_on": "16:00"},
            {"id": "ORLP", "name": "Omni Rancho Las Palmas", "available": avail(20, ORLP_DAYS),
             "lit_courts": 8, "lights_on": "16:00"},
            {"id": "WEST", "name": "The Westin", "available": avail(4, WEST_DAYS),
             "lit_courts": 4, "lights_on": "16:00"}],
        "transit_minutes": {"MHCC|ORLP": 20, "MHCC|WEST": 35, "ORLP|WEST": 25},
    }


def default_constraints():
    """The TD rules doc: R3 AVOID-3 (80+ 09:30) + BP-2 staging + R2b Coachella locality.

    WIRE-1 (2026-08-02) adds the three keys the Setup console now emits, so this default doc and
    the console's bare emit agree field-for-field:
      · `match_minutes` 90 — the engine's block length, now CONSUMED. 90 is exactly what
        wwtc_ingest stamps on every EventSpec (:808), so naming it here changes no placement.
      · `matches_per_day_target` / `finals_per_day` — the D-32 pacing thresholds, at the TD's own
        measured practice. Carried for the finals map (FMAP-1) to read; inert until it ships.
    Deliberately carries NO retired key, so the product's own default never trips the loud
    rejection in constraints.validate_constraints.
    """
    return {
        "schema": "td-constraints/v1",
        "min_start_to_start_minutes": 180,
        "match_minutes": 90,
        # ENG-1 (ruling 75): CONSUMED since 2026-08-02. `flat: 1` is the TD's own rule — one match
        # per division per player per day — and it is the number the console shows and the engine
        # obeys. The FAC Table 9 ladder stays under `age_based` as the documented sanctioning
        # ceiling, unreachable while mode is "flat". Measured in two steps so the wiring was proven
        # before the value moved: routed at 6/4/3 => 0 of 760 placements moved; flipped to 1 => 0
        # again (the desk-seeded day map already achieves one-per-division-per-day, so the cap is a
        # guard for the first field that does not).
        "match_caps": {"mode": "flat", "flat": 1,
                       "age_based": {"le55": 6, "60to80": 4, "ge85": 3}},
        # ENG-1 (F-4 / M6, ruling 74): no FINAL before 9am. Finals only — the nine 08:00
        # semifinals are reported, never floored; flooring them would be scope not granted.
        "finals_earliest": "09:00",
        # ENG-1 (ruling 73): the TD's day, at the clock — singles early, mixed midday, gender
        # doubles late. A GATE: `_scan` refuses an out-of-shape slot, and where no in-shape slot
        # exists anywhere the match is placed and the exception RECORDED, exactly as an
        # assigned-day spill is. 0-unplaced is never traded away, which is why `on_no_slot` has
        # one value and is not a knob the TD is offered.
        "day_shape": {"order": ["singles", "mixed", "doubles"],
                      "on_no_slot": "place_and_record"},
        # ENG-1 (D-40 / ruling 67): the TD's own head start for three-event players, read
        # "at or EARLIER" — his real week starts 103 matches before 9:00, 21 of them these very
        # head starts, so an exact-9:00 reading would move his own practice LATER. Narrow scope
        # (triple days only) pending NQ-1; "all_days" is the broad reading.
        "day_bands": {"singles_by": "09:00", "mixed_at": "12:00", "doubles_from": "15:00",
                      "scope": "triple_days"},
        # ENG-1 (D-41 / ruling 72): SHIPS OFF. The TD names a division when its players ask to
        # finish the same day; nothing is ever inferred. `gap_minutes` is load-bearing TWICE — it
        # sets the spacing between the last two matches AND it defines the width of the only
        # exception the 180-minute rest floor ever yields to. Raise it to 180 and the exception
        # stops existing; lower it and the exception widens.
        "same_day_finish": {"divisions": [], "gap_minutes": 150},
        # DIV-1 (rule 45): which Mixed ages the TD sanctioned at LEVEL 1. Ships BLANK, and blank
        # is not "none" — it means "derive it from which draws file each division was printed
        # in, and say so" (`_resolve_mixed_level_1`, Operator ruling 2026-08-05). Reg IV.C draws
        # Level 2 from the SAME division list, so this is his sanction that year and can never
        # be hardcoded. His tick-box always wins over the derivation. DISPLAY ONLY.
        "mixed_level_1": {"divisions": []},
        # VENUE-1 (2026-08-05) — the venue rules the director has stated, switched ON. Each is a
        # PREFERENCE with a recorded escape (rule 41): where nothing the rule wants has room, the
        # match is placed anyway and the exception recorded, so none of them can cost a placement.
        # Measured on the 2026 field with all six on: 760/275/0/0, determinism PASS, and the gaps
        # closed — 80-and-over 63 of 93 -> 92 of 93 (the 1 residual carries a recorded escape),
        # finals 36 of 42 -> 42 of 42, semifinals 68 of 84 -> 84 of 84, Level-1 Mixed 36 of 49 ->
        # 49 of 49, window peak 7 of 9. Scored against the director's own approved week the venue
        # axis goes 67.8% -> 72.1%, and matches with BOTH time and venue right go 48 of 745 -> 67.
        # Cost: 381 of 760 matches sit in different slots, 2 matches of day agreement (736 -> 734
        # of 745), and the assigned-day spill anchor moves 3 -> 5.
        # "Main site" is the rank-1 venue of the director's own list, never the string "MHCC".
        "venue_rules": {
            "main_site_ages": [80, 85, 90],   # 38 — his field: 95 of 95, across 8 events
            "main_site_finals": True,         # 39 — his field: finals 49 of 49, semis 87 of 88
            "main_site_l1_mixed": True,       # 40 — his field: 61 of 62; the 1 exception a walkover
            # 31, RE-CUT AT BUDGET-1 (R19, Operator 2026-08-22, OI-B1). Was
            # `l1_mixed_lights_off: True`, a test against the venue's lights hour that fired on
            # 0 of 49 on the committed field and on none of the 2027 late starts either — they
            # land at 15:30, inside the lights hour. This is the stricter, venue-independent
            # test that catches them. SOFT: a demerit that bends and records under rule 41.
            "l1_mixed_latest_start": "14:00",
            "rank_order": True,               # 43 — venues fill in his list order, dropping to the next when full
            # 6 — his hard ceiling. His own week breaks it once, by two matches (Sat 01-24, 11 of
            # 9, on the each-player's-first-match comparison); the engine's peak is 3 of 9.
            "peak_window": {"start": "15:00", "end": "16:00", "max_starts": 9},
        },
        # S-3 §4.4a (Operator, 2026-08-24): 130, was 125 — the SAME figure the setup console's two
        # defaults blocks carry. This is the canonical-defaults path a run takes when it does NOT
        # go through the console (`wwtc_2026_defaults()` returns this function's block), so
        # changing the screen alone would leave the tool with two answers to one question and
        # nothing on any surface saying which one the run used.
        # It is a THRESHOLD THE FINALS MAP EDITOR COLOURS A DAY PAST, never a scheduling limit:
        # no placement path reads it, and 760/275/0/0 is unmoved by this line.
        "matches_per_day_target": 130,
        "finals_per_day": {"singles": 9, "doubles": 4},
        "placement_policy": {"stage_multidivision_early": True, "locals_early": True},
        "earliest_start_by_age": [{"age_min": 80, "earliest": "09:30"}],
        # CUI-3: `commuter_cities` rides beside `home_cities` — same block, same validation shape,
        # same chips control. `home_cities` reaches the engine; `commuter_cities` reaches nothing.
        "locality": {"home_cities": HOME_CITIES, "commuter_cities": COMMUTER_CITIES,
                     "home_section": ""},
    }


def _paired_rules(constraints_doc, slate):
    """Resolve the (slate, rules) PAIR one lane was handed, and REFUSE the silent half.

    `td-setup/v1` is a pair — slate plus constraints — and every lane that takes the document
    whole (`build_from_setup`) gets both. The lanes that take the pair already split used to
    write `doc = constraints_doc or default_constraints()`, which means a caller who passes the
    director's slate and forgets his rules gets the ENGINE'S rulebook, silently, and no surface
    says so. Measured on the committed 2027 seed (S-7 §0): 0 of his 15 rule keys reached the
    Step 3.5 search, and the run's court figures matched his only because the single rule he had
    changed (`matches_per_day_target`) is the single rule that changes nothing.

    Three cases, and the third is the whole point:
      · `constraints_doc` given            -> use it, source `"caller"`
      · neither doc nor slate              -> `default_constraints()`, source `"defaults"`
        (the legitimate 2026-fixture lane — `wwtc_2026_defaults()` and every bench caller)
      · a slate WITHOUT a doc              -> `ValueError`, naming both remedies

    ⚠ "GIVEN" IS TRUTHINESS, NOT `is not None`, and both halves are deliberate. It keeps the
    defaults branch byte-identical to the `or` expression this replaced, and it means an EMPTY
    constraints block — a console emit that lost its rules — is the MISSING half rather than a
    document with no rules in it. Read the other way, a malformed setup would buy a court answer
    computed under no rules at all and LABELLED as the director's, which is the same family of
    silent fault this function exists to close. `build_from_setup` already normalises the same
    way (`setup.get("constraints") or None`); this is that precedent, applied where the pair
    arrives already split.

    Returns `(doc, record)`. The record is the provenance the answer carries so a reader can
    ask "whose rules produced this figure?" without trusting the call site.
    """
    if not constraints_doc and slate:
        raise ValueError(
            "a slate was given without the rules that go with it, and this call will not "
            "substitute the tool's own rulebook for the director's: the court answer would be "
            "computed against rules he does not use. Pass `constraints_doc=setup[\"constraints\"]` "
            "alongside the slate, or pass `constraints_doc=default_constraints()` explicitly if "
            "the tool's defaults are genuinely what you mean.")
    doc = constraints_doc or default_constraints()
    return doc, _rules_record(doc, "caller" if constraints_doc else "defaults")


def _rules_record(doc, source, edited=None):
    """The `rules` provenance block a court answer carries (S-7, the R-6 half for M8).

    `digest` is over the canonical-JSON rules doc, so two answers computed under the same rules
    carry the same digest whatever route the doc took to get there. `edited` is `try_change`'s
    addition — the keys his what-if actually moved — and the digest beside it is taken on the doc
    AS EDITED, because the record must describe the rules the build RAN under, not the ones it
    was handed."""
    blob = json.dumps(doc, sort_keys=True, default=str)
    record = {"source": source,
              "digest": hashlib.sha256(blob.encode()).hexdigest(),
              "keys": len(doc)}
    if edited is not None:
        record["edited"] = sorted(edited)
    return record


def wwtc_2026_defaults():
    """The 2026 WWTC fixture (CANON-2 D-2A): the committed dataset's slate + TD rules doc.
    The ONLY sanctioned path to the 2026 defaults — a 2027 run passes the Setup console's
    slate/constraints instead (nothing 2026 is reachable without naming this fixture)."""
    return wwtc_slate(), default_constraints()


def _level_draws(levels):
    """The finalized-draws PDFs for `levels`, parsed once. `parse_draws` is uncached, and the
    day-map lane now has two readers of the same draws (divisions + the ASSIGN-1 desk seed);
    sharing one parse keeps a build at one pass over the PDFs per lane."""
    draws = []
    for lvl in levels:
        draws.extend(draws_pdf.parse_draws(level=lvl))
    return draws


def _divisions(levels):
    """Division records from the finalized-draws PDFs (shared by Pass 1 and the finals plan).
    Overrides never alter draw structure/size — only entrant identity — so the division list
    is override-independent (same as Pass 1 has always assumed)."""
    return MS.divisions_from_draws(_level_draws(levels))


def _expand_rr_groups(base, ms, divisions, events):
    """F7-4: bind RR GROUP draws to their parent division's master days (CEO sign-off
    2026-07-25). The R7-2 gate joins on the engine's `(event, rnd)`; RR engine events are
    named `<parent> — Group <i>` (wwtc_ingest) with `rnd` a FLAT match index in circle-method
    round order (scheduler._circle_pairings), so true round = (rnd-1) // (m//2) + 1 for a
    group of m teams. Rounds are END-ALIGNED to the parent's cascade (offset =
    parent_rounds - group_rounds) so every group's last round lands on the division's
    draggable finals day — the semantic the TD's finals-map drag expresses. Uses the real
    EventSpecs (post-ingest team counts), never a draws-side re-derivation."""
    rounds_by = {d.event: d.rounds for d in divisions}
    out = dict(base)
    for ev in events:
        if ev.fmt != "round_robin" or " — Group" not in ev.name:
            continue
        parent = ev.name.split(" — Group")[0]
        total, rd = rounds_by.get(parent), ms.round_day.get(parent)
        m = len(ev.teams)
        if not total or not rd or m < 3:
            continue
        per, g_rounds = m // 2, MS._rr_rounds(m)
        offset = total - g_rounds
        for ri in range(1, m * (m - 1) // 2 + 1):
            tr = (ri - 1) // per + 1                       # true circle round of this match
            lbl = MS._round_label(min(max(tr + offset, 1), total), total)
            dt = rd.get(lbl)
            if dt is not None:
                out[(ev.name, ri)] = dt
    return out


def _short_day(day):
    """`2026-01-25` -> `Jan 25`. LANG-1 (A7c): the warning bar speaks the desk's own register —
    the desk prints its stamps as "Jan 28" tokens, so a warning about a desk day says it the
    same way. Unparseable input is returned verbatim rather than swallowed."""
    try:
        return datetime.datetime.strptime(day, "%Y-%m-%d").strftime("%b %-d")
    except (TypeError, ValueError):
        return str(day)


_WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _weekday_translation(source_dates, dates):
    """KEY-1: `{source ISO -> (slate ISO or None, "Friday #2")}` — the desk seed's key.

    A desk stamp names a day in the DRAWS' season; the seed has to name the same day in the
    SLATE's. Matching the two by calendar date assumes next season occupies last season's dates,
    which is true in January (the draws and the slate are the same season) and false on every
    September publish run: measured on the committed field seeded against the 2027 window, all
    135 elimination desk cells land one weekday late, silently. The desk's shape is a WEEKDAY
    shape — "quarterfinals on the first Saturday" — so the key is (weekday, occurrence-within-
    window), counted chronologically: 2026-01-24 is Saturday #1, 2026-01-31 is Saturday #2.

    A source day whose (weekday, occurrence) has no partner in the slate maps to `None`, carrying
    its label so the caller's warning can name it. That is the VISIBLE fallback — the cell drops
    to the computed cascade with a warning, never silently and never fatally (ruling 47's shape).

    The identity property is what makes January safe, and it is structural rather than a branch:
    with `source_dates == dates` every day's own (weekday, occurrence) resolves back to itself,
    so the translation is the identity map and the seed is byte-for-byte the shipped one."""
    slots: dict = {}
    for iso in dates:
        slots.setdefault(datetime.date.fromisoformat(iso).weekday(), []).append(iso)
    seen, out = {}, {}
    for iso in source_dates:
        wd = datetime.date.fromisoformat(iso).weekday()
        occ = seen[wd] = seen.get(wd, 0) + 1
        days = slots.get(wd, ())
        out[iso] = (days[occ - 1] if occ <= len(days) else None,
                    f"{_WEEKDAY_NAMES[wd]} #{occ}")
    return out


def _draws_window(levels, warn=None):
    """KEY-1: the SOURCE window — the days the DRAWS were printed against, read off their own
    `Dates:` page header with SETUP-2's shipped parser (`_window_from_texts`). Measured on the
    committed field: one distinct header on 72 of 72 pages, and the window it yields equals the
    committed slate exactly.

    This is the only place a desk stamp's YEAR can come from — the desk prints "Jan 30" and
    nothing else — and therefore the only place its WEEKDAY can come from. Without it the seed
    has no way to tell last season's dates from next season's and simply assumes they are the
    same, which is the defect KEY-1 removes.

    A header that cannot be read is a VISIBLE fallback, never a raise: `None` comes back (the
    shipped date-key resolution) and `warn`, when given, carries one line saying the desk days
    were matched by calendar date instead. Read-only over the same PDFs the lane already parses;
    deterministic, and measured at seconds."""
    try:
        import pypdfium2 as pdfium
        texts = []
        for lvl in levels:
            path = draws_pdf.resolve_draws_pdf(level=lvl)
            texts += draws_pdf._page_texts(pdfium.PdfDocument(path))
    except Exception as exc:            # a PDF-layer failure the seed can survive without
        if warn is not None:
            warn.append(f"the draws' own date window could not be read "
                        f"({exc.__class__.__name__}) — desk days were matched to the slate by "
                        f"calendar date, not by weekday")
        return None
    window, _headers = _window_from_texts(texts)
    if not window:
        if warn is not None:
            warn.append("the draws carry no readable 'Dates:' header — desk days were matched "
                        "to the slate by calendar date, not by weekday")
        return None
    return window


def _desk_date(token, by_md, warn, where, xlate=None):
    """ASSIGN-1 item 1: a desk stamp's verbatim date token ("Jan 28") -> the slate's
    "YYYY-MM-DD". The desk prints no year, so the year comes from the date list the token is
    looked up in, which is year-correct even for a window that straddles New Year. Unparseable
    tokens RAISE (ruling 3's crash-guard discipline — a stamp we cannot read is a parser
    regression, not a cell to drop); a token that parses but names a day outside that window is
    WARNED and left unseeded, never silently dropped. Measured on the committed field: 0 of 674
    stamped elim matches hit either path.

    KEY-1 splits the two windows the shipped code conflated. `by_md` is the DRAWS' own season —
    the window the stamps were printed against — and `xlate` (`_weekday_translation`) carries
    that day on to the SLATE by (weekday, occurrence). `xlate=None` means the stamps are the
    slate's own season, and is byte-for-byte the shipped date-key resolution: every direct
    caller and every injected-draws harness keeps today's behaviour. A stamp whose weekday
    occurrence has no partner in the slate is warned by name and left unseeded, the same shape
    the outside-window path already has — the cell falls back to the computed cascade rather
    than moving silently to a day the desk never chose.

    The token carries no year, so it is parsed against a LEAP year: `strptime` defaults to 1900,
    which is not a leap year, and would reject a perfectly readable "Feb 29" as unparseable —
    crashing a leap-year tournament on a real stamp. The parsed year is discarded; only
    (month, day) is used, and the real year comes from `by_md`."""
    d = None
    for fmt in ("%b %d", "%B %d"):
        try:
            d = datetime.datetime.strptime(f"{token} 2024", f"{fmt} %Y")   # leap year, see above
            break
        except ValueError:
            continue
    if d is None:
        raise ValueError(f"{where}: unparseable desk schedule date {token!r} "
                         f"(expected '%b %d' / '%B %d', e.g. 'Jan 28')")
    iso = by_md.get((d.month, d.day))
    if iso is None:
        warn.append(f"{where}: desk day {token!r} is outside the draws' own printed window "
                    f"— not seeded")
        return None
    if xlate is None:                  # the stamps are the slate's own season: shipped behaviour
        return iso
    day, occurrence = xlate.get(iso, (None, ""))
    if day is None:
        warn.append(f"{where}: desk day {token!r} ({occurrence}) has no matching weekday in the "
                    f"new window — falling back to computed")
    return day


def _desk_seed(levels, dates, draws=None, source_dates=None):
    """ASSIGN-1 (ruling 32): the day map's SEED — the desk's own published elimination layout,
    read off the raw draws' ING-1 stamps as `(event, rnd) -> "YYYY-MM-DD"`, plus advisory
    warnings. Not a new parse: `draws_pdf` already retains the stamps; this is the join the
    engine never had.

    Item 2, the round-label join: the desk labels rounds by PLAYERS REMAINING (R64 / R32 /
    Quarterfinals / Final) and the master labels them by ORDINAL (`Round n` / Semifinal /
    Final), so the two match on nothing but `Final`. The join is arithmetic — a label naming N
    remaining is round `total - log2(N) + 1` — which also makes round 1 self-consistent, since a
    64-draw prints it as both `R1` and `R64`. Measured: all 135 desk cells join, 0 unjoinable.

    `MultiConfig.assigned_days` is keyed per ROUND, the desk stamps per MATCH, so a round's
    stamps are collapsed to one day. Measured lossless: 0 of 135 cells span more than one date.
    A cell that ever did would take the earliest and say so rather than pick silently.
    `draws` (optional): an already-parsed `_level_draws(levels)`, to avoid a second pass over
    the PDFs when the caller has one. Deterministic; read-only over the draws.

    KEY-1: `source_dates` (optional) is the DRAWS' own window — the days the stamps were printed
    against, which in September is last season's, not the slate's. Given it, stamps resolve by
    (weekday, occurrence) instead of calendar date (`_weekday_translation`). `None` means the
    stamps are the slate's own season and is byte-for-byte the shipped resolution."""
    src = list(source_dates) if source_dates else list(dates)
    by_md = {(int(dt[5:7]), int(dt[8:10])): dt for dt in src}
    xlate = _weekday_translation(src, dates) if source_dates else None
    cells, warn = {}, []
    for d in (_level_draws(levels) if draws is None else draws):
        if d.fmt != "single_elim" or d.draw_size < 2:
            continue
        total = int(math.log2(d.draw_size))
        r1_label = next((l for l, s in draws_pdf.LABEL_SIZE.items() if s == d.draw_size), None)
        sections = [(r1_label, d.r1_stamps)] + sorted(d.later_stamps.items())
        for label, stamps in sections:
            size = draws_pdf.LABEL_SIZE.get(label)
            rnd = total - int(math.log2(size)) + 1 if size else None
            if rnd is None or not 1 <= rnd <= total:
                if any(stamps.values()):
                    warn.append(f"{d.event}: desk round label {label!r} does not join to a "
                                f"round of a {d.draw_size} draw — {len(stamps)} stamps unseeded")
                continue
            for idx, stamp in sorted(stamps.items()):
                if not stamp:                      # 'Not scheduled', or no stamp line
                    continue
                iso = _desk_date(stamp["date"], by_md, warn,
                                 f"{d.event} {label} match {idx}", xlate)
                if iso is None:
                    continue
                prev = cells.setdefault((d.event, rnd), iso)
                if prev != iso:
                    cells[(d.event, rnd)] = min(prev, iso)
                    warn.append(f"{d.event} round {rnd}: desk stamps span {prev} and {iso} "
                                f"— seeded the earlier ({min(prev, iso)})")
    return cells, warn


def _desk_finals(seed, divisions, dates, skip=(), warn=None):
    """ASSIGN-1 item 3 (ruling 30): every elimination division's DESK-DERIVED finals day — the
    day the desk stamped the final itself (3 divisions), else its own desk semifinal + 1 (the
    other 39, the "anchored" ones).

    Anchoring is deliberately a ONE-ROUND problem, not a re-cascade: the desk supplies every
    non-final elimination round (135 of 174 elim keys; the 39 uncovered are exactly the 39
    unstamped finals), so the only seam where a computed cell can meet a desk cell is the final.
    Splicing a computed final onto a desk semifinal instead produces 19 round-order inversions —
    every one a final on or before the semifinal that feeds it. Anchoring reproduces the TD's
    own finals calendar in 41 of 42 divisions.

    Both kinds go to `MS.build_master_schedule(finals_anchors=...)` together so the master
    artifact the TD reviews — the chart, and the finals-map editor's draft — names the same
    finals day the engine will actually schedule. `skip` names divisions whose final is already
    fixed by the TD's console pin, which outranks anything derived here.

    **The one case the +1 cannot honour: a desk semifinal stamped on the LAST slate day.** There
    is no day left to add, so an anchor there would put the final on its own semifinal's day —
    the exact round-order inversion anchoring exists to remove. That division is therefore given
    **no anchor at all** and falls back to the computed finals day (Operator sign-off 2026-07-30);
    the fallback costs it the desk's accuracy, which is why `warn` names it rather than letting
    it pass quietly. A warning is the right tool for something ambiguous, not for a day we can
    already tell is wrong. 0 of 42 divisions hit this on the committed field.

    `warn` (optional): the advisory list for that fallback. Pass None when deriving the
    provenance answer key, so the same fallback is applied without warning about it twice."""
    out = {}
    last = len(dates) - 1
    for div in divisions:
        if div.fmt != "single_elim" or div.rounds < 1 or div.event in skip:
            continue
        stamped = seed.get((div.event, div.rounds))
        if stamped in dates:
            out[div.event] = stamped
            continue
        sf = seed.get((div.event, div.rounds - 1)) if div.rounds >= 2 else None
        if sf in dates:
            i = dates.index(sf)
            if i >= last:
                if warn is not None:
                    warn.append(f"{div.event}: desk semifinal {sf} is the last slate day, so its "
                                f"final cannot be anchored a day after it — falling back to the "
                                f"computed finals day for this division")
                continue                               # no anchor: Pass B's computed day stands
            out[div.event] = dates[i + 1]
    return out


def _rr_desk_seed(levels, dates, draws=None, source_dates=None):
    """ASSIGN-2 (ruling 40): the ROUND-ROBIN half of the desk seed — `(group event, true round)
    -> day`, split into the rounds the desk stamped and the tail rounds derived from them.
    Returns `(stamped, anchored, warnings)`.

    **The round join is exact, not best-effort**, which the ING-1 caveat on `Group.stamps`
    invites one to assume it is not. Within a group the stamps' DISTINCT dates appear in round
    order, and each date repeats `2 * (m // 2)` times for a group of m members — twice the
    matches in one round, because a match's stamp prints once in each of its two players' rows.
    So the k-th distinct date IS round k. Measured across all 9 committed groups: 0 violations
    of the repeat rule, 0 ambiguous groups. A group that ever broke the rule is warned about and
    left unseeded rather than joined on a guess.

    **"k-th distinct date" is read CHRONOLOGICALLY, never in printed order.** `Group.stamps` is
    filed row-major — member row, then column (`draws_pdf._harvest_rr_stamps`) — so its dates are
    in a player's opponent order, not the desk's day order: measured on the committed field, rows
    2 and 3 of every 4-member group print their dates DESCENDING, and first-appearance order only
    lands on the right answer because member row 0 happens to run ascending. Sorting is a no-op
    there and the difference between a seed and a round-order inversion anywhere else, since
    `order[-1]` is also what ruling 41's tail anchors off.

    **The desk stamps every round but the last** — the same shape as its elimination pages, and
    the reason ASSIGN-1's design transfers. Measured: 21 of 27 (group, round) cells covered, the
    6 uncovered being exactly the last round of 6 groups. Those tails are anchored at
    `last stamped + 1 day` (ruling 41, mirroring ruling 30), and **ruling 38's guard applies
    unchanged**: a tail with no day left in the window takes no anchor and stays computed.

    **RRGAP-1 (rulings 45–48) — ruling 40 now carries a PRECONDITION: the stamped days must be
    CONTIGUOUS.** "k-th distinct date = round k" is sound only while the blank rounds are
    trailing. A blank *middle* round cannot be seen by the join itself — it relabels the dates, so
    the hole always presents as trailing and `tests/…::check_anchor_is_the_last_round` passes by
    construction (that check verifies the ANCHOR rule; it never could detect a middle gap).
    Measured on the committed field, the desk runs a division's rounds on consecutive days:
    **9 of 9 RR groups with zero gaps**, and **129 of 131 elimination round transitions at +1
    day**. So a gap in a group's stamped days means the round numbers cannot be trusted, and the
    group is refused rather than guessed at (ruling 45 — the desk *does* rest a division a day,
    1 of those 131 transitions, so auto-correcting the ordinals would trade a silent middle-gap
    error for a silent rest-day one). Refusal is per-group, never a raise (ruling 47).
    **NOT covered, deliberately (ruling 46): a LEADING gap** — rounds 2..n stamped with round 1
    blank yields contiguous days and passes. Judged remote (every RR pairing is known up front,
    so nothing forces the desk to schedule a later round first) and the only test for it needs
    the parent's own day map, reintroducing the circularity this guard removes.

    Round-robin group SIZES come from the draws here because that is what the stamps were
    printed against; the engine's own post-ingest team counts drive the expansion onto flat
    match indices (`_rr_group_days`), exactly as `_expand_rr_groups` has always insisted.

    KEY-1: `source_dates` is the DRAWS' own window, exactly as in `_desk_seed` — stamps resolve
    by (weekday, occurrence) rather than calendar date, and `None` is the shipped resolution.
    The read-each-token-once dedup below is untouched, so warning granularity is unchanged."""
    src = list(source_dates) if source_dates else list(dates)
    by_md = {(int(dt[5:7]), int(dt[8:10])): dt for dt in src}
    xlate = _weekday_translation(src, dates) if source_dates else None
    stamped, anchored, warn = {}, {}, []
    last = len(dates) - 1
    for d in (_level_draws(levels) if draws is None else draws):
        if d.fmt != "round_robin":
            continue
        for g in d.groups:
            name = f"{d.event} — {g.name}"              # the engine's own RR event name
            m = len(g.members)
            if m < 3:
                continue
            tokens = [s["date"] for s in g.stamps if s]        # skip 'Not scheduled'
            iso_of = {tok: _desk_date(tok, by_md, warn, f"{name} schedule stamp", xlate)
                      for tok in dict.fromkeys(tokens)}        # each token read (and warned) once
            order = sorted({iso for iso in iso_of.values() if iso is not None})
            if not order:
                continue
            per_round = 2 * (m // 2)                   # stamp instances one round should print
            counts = collections.Counter(iso_of[tok] for tok in tokens)
            odd = {k: v for k, v in counts.items() if v != per_round}
            if odd:
                warn.append(f"{name}: desk stamps do not repeat {per_round} times per day "
                            f"({odd}) — the date order cannot be trusted to name rounds, "
                            f"so this group is left on the computed expansion")
                continue
            # RRGAP-1 (ruling 45): the date-order join is only sound while the UNSTAMPED rounds
            # are trailing, and a blank middle round is invisible to it — the join relabels the
            # dates, so the hole always presents as trailing. Require the stamped days to occupy
            # CONSECUTIVE PLAYING-DAY POSITIONS (indices into `dates`, never calendar arithmetic,
            # so a year with a dark day still reads correctly). Refuse the group otherwise.
            idx = [dates.index(d) for d in order if d in dates]
            if len(idx) != len(order) or idx != list(range(idx[0], idx[0] + len(idx))):
                skipped = ([dates[i] for i in range(idx[0], idx[-1] + 1) if i not in set(idx)]
                           if idx else [])
                warn.append(f"{name}: the desk's stamped days {', '.join(order)} skip "
                            f"{', '.join(skipped) or 'a day outside the tournament window'}. "
                            f"A blank MIDDLE round and a blank LAST round are indistinguishable "
                            f"in the source, so the round numbers cannot be named from date "
                            f"order — this group is left on the computed expansion (RRGAP-1)")
                continue
            rounds = MS._rr_rounds(m)
            for r, day in enumerate(order[:rounds], 1):
                stamped[(name, r)] = day
            i = dates.index(order[-1]) if order[-1] in dates else None
            for r in range(len(order) + 1, rounds + 1):
                nxt = None if i is None else i + (r - len(order))
                if nxt is None or nxt > last:
                    warn.append(f"{name}: round {r} is unstamped and its last stamped round "
                                f"{order[-1]} leaves no day after it — falling back to the "
                                f"computed day for this round")
                    continue
                anchored[(name, r)] = dates[nxt]
    return stamped, anchored, warn


def _rr_group_days(rr_days, events):
    """Expand the per-ROUND round-robin seed onto the engine's FLAT rr match index. RR engine
    events carry `rnd` as a flat index in circle-method round order, so true round =
    (rnd - 1) // (m // 2) + 1 for a group of m teams — the same arithmetic `_expand_rr_groups`
    uses, and read off the real EventSpecs (post-ingest team counts) for the same reason."""
    out = {}
    for ev in events or ():
        if ev.fmt != "round_robin" or " — Group" not in ev.name:
            continue
        m = len(ev.teams)
        if m < 3:
            continue
        per = m // 2
        for ri in range(1, m * (m - 1) // 2 + 1):
            day = rr_days.get((ev.name, (ri - 1) // per + 1))
            if day is not None:
                out[(ev.name, ri)] = day
    return out


def _rr_group_rounds(draws):
    """`group event -> its own circle-round count`, off the draws the stamps were printed
    against. This is the DENOMINATOR of `_rr_parent_days`' end-alignment, and it has to be the
    group's real round count rather than its highest SEEDED round: ruling 38's guard can leave a
    tail unanchored, and inferring the count from the seed would then shorten the group by a
    round and slide the whole parent division one round late."""
    return {f"{d.event} — {g.name}": MS._rr_rounds(len(g.members))
            for d in draws if d.fmt == "round_robin"
            for g in d.groups if len(g.members) >= 3}


def _rr_parent_days(rr_days, divisions, stamped=(), warn=None, group_rounds=None):
    """The RR PARENT division's own `(event, round) -> day`, projected from its groups' seeded
    days by the SAME end-alignment `_expand_rr_groups` uses (parent round = group round +
    parent_rounds - group_rounds), so the two cannot drift apart.

    The parent's cells gate nothing — every RR match is a `— Group` event — but they are what
    the master chart and the finals-map editor's draft are drawn from, and what the provenance
    record reports. Leaving them computed while the groups moved is the disagreement Update 6
    had to fix on the elimination side. A division whose groups disagree about a round takes the
    LATER day and says so rather than choosing silently; measured, the one division that prints
    two groups (Women's 75 & over doubles) has identical dates in both.

    `group_rounds` (`_rr_group_rounds`): each group's real round count. Pass it — the highest
    seeded round is only the same number while every round is seeded, and `_expand_rr_groups`
    end-aligns on the real one regardless."""
    grouped = collections.defaultdict(lambda: collections.defaultdict(set))
    from_stamp = collections.defaultdict(lambda: collections.defaultdict(list))
    rounds_by = {d.event: d.rounds for d in divisions if d.fmt == "round_robin"}
    g_rounds = collections.defaultdict(int)
    for (name, rnd), _day in rr_days.items():          # fallback: the highest seeded round
        g_rounds[name] = max(g_rounds[name], rnd)
    for name, total in (group_rounds or {}).items():
        if name in g_rounds:
            g_rounds[name] = total
    for (name, rnd), day in rr_days.items():
        parent = name.split(" — Group")[0]
        total = rounds_by.get(parent)
        if not total:
            continue
        pr = min(max(rnd + total - g_rounds[name], 1), total)
        grouped[parent][pr].add(day)
        from_stamp[parent][pr].append((name, rnd) in stamped)
    out, stamped_keys = {}, set()
    for parent, rounds in grouped.items():
        for pr, days in rounds.items():
            if len(days) > 1 and warn is not None:
                warn.append(f"{parent} round {pr}: its groups sit on different days "
                            f"({sorted(days)}) — the division's master day takes the later")
            out[(parent, pr)] = max(days)
            if all(from_stamp[parent][pr]):     # every contributing group round was published
                stamped_keys.add((parent, pr))
    return out, stamped_keys


def _rr_parent_finals(parent_days, divisions, skip=()):
    """`event -> date` for each RR division's last round, for `finals_anchors`. The parent's
    cascade then runs one round per day backward from it; measured, every committed RR
    division's desk days are contiguous, so it reproduces them exactly."""
    out = {}
    for div in divisions:
        if div.fmt != "round_robin" or div.event in skip:
            continue
        days = [d for (ev, r), d in parent_days.items() if ev == div.event]
        if days:
            out[div.event] = max(days)
    return out


def _normalise_division(name):
    """Lower-case, `and` -> `&`, whitespace collapsed. OI-54's whole matching rule.

    `and` is replaced on a WORD boundary, never as a substring — otherwise `Sanders` normalises
    to `S&ers` and the comparison starts inventing matches of its own.
    """
    s = re.sub(r"\band\b", "&", str(name or "").lower())
    return re.sub(r"\s+", " ", s).strip()


def _suggest_division(typed, candidates):
    """OI-54 (LANG-1 A7c) — the real division name a mistyped one almost certainly meant, or
    `None`. **IT SUGGESTS. IT DOES NOT RESOLVE.**

    The caller's `by_name.get(name)` lookup is untouched and a normalised match is NEVER accepted
    as a hit. That is a behavior boundary, not a style choice: auto-resolving the 2026 run's own
    typo would make Mixed 70 & over doubles actually join its last two rounds — the same-day
    finish would fire, OI-39's 150-minute exception would apply, and THE SCHEDULE WOULD MOVE.
    Anyone proposing that is proposing a new build.

    **Fuzzy matching is refused, and the measurement is recorded here so it is not re-proposed.**
    Measured 2026-08-07 against the committed field's 51 division names: normalisation resolves
    the run's real typo and 255 of 255 punctuation/case/spacing variants with **0 of 61** wrong
    suggestions; `difflib` at cutoff 0.6 picks a **different division in 31 of 61** age-mutated
    names (`"Men's 45 & over doubles"` -> suggests `"Men's 75 & over doubles"`). A director who
    accepted that would join the WRONG age group's last two rounds. A suggestion he can act on
    must never be a guess.

    `candidates` is walked in its own order, which is the printed-draw order at both call sites —
    deterministic, same input same output.
    """
    target = _normalise_division(typed)
    if not target:
        return None
    for real in candidates:
        if _normalise_division(real) == target:
            return real
    return None


def _did_you_mean(typed, candidates):
    """The suggestion clause, or an empty string. Never an empty `Did you mean ''?`."""
    hit = _suggest_division(typed, candidates)
    return f" Did you mean {hit!r}?" if hit else ""


def _resolve_same_day_finish(named, divisions, warn):
    """The TD's named divisions, resolved against the real division list (ENG-1 / D-41).

    Returns the subset that can actually be honoured, and appends a loud warning for every name
    that cannot. Two ways a name silently did nothing before: a spelling that matches no division,
    and a ROUND-ROBIN division — `master_schedule._lay_out` would happily join its last two rounds
    and announce it, while `scheduler_multi._same_day_finish_pairs` is elimination-only, so the
    rest-floor exception never existed and the pair either spilled or was refused. A feature that
    reports itself on and is off is worse than one that is plainly unavailable.
    """
    if not named:
        return []
    by_name = {d.event: d for d in divisions}
    out = []
    for name in named:
        div = by_name.get(name)
        if div is None:
            warn.append(f"same-day finish: no division named {name!r}."
                        f"{_did_you_mean(name, by_name)} Nothing was changed.")
        elif div.fmt not in ("single_elim", "compass"):
            warn.append(f"same-day finish: {name} is a {div.fmt} division, and the same-day "
                        f"finish covers elimination draws only — its last two rounds were NOT "
                        f"joined. Raise it as its own question if the group needs it")
        elif div.rounds < 2:
            warn.append(f"same-day finish: {name} has only {div.rounds} round, so there is no "
                        f"previous round for its final to join")
        else:
            out.append(name)
    return out


def _resolve_mixed_level_1(named, names_by_level, warn):
    """DIV-1 / rule 45 — which Mixed divisions this run treats as LEVEL 1, and where that came
    from. Returns `(resolved_division_names, one_informational_line)`.

    Reg IV.C draws Level 2 from the SAME division list as Level 1, so the split is a property of
    the TD's sanction that year and is never hardcodable. Two sources, in strict priority:

      1. **His tick-box** (`td-constraints/v1` `mixed_level_1.divisions`) — always wins. Resolved
         against the real printed division list exactly the way `_resolve_same_day_finish`
         resolves its own, and for the same reason: the Setup console runs BEFORE the draws are
         read, so the field is free text and a typo would otherwise be a silent mis-sort. Two
         ways a name does nothing get a loud warning — a spelling that matches no printed
         division, and a division that is not Mixed (the tick-box is a Mixed-level control, and
         silently accepting `Men's 50 & over singles` would be a feature reporting itself on
         while off).
      2. **Blank -> derive from the source files** (Operator ruling, 2026-08-05, option 1): the
         Mixed divisions printed in the LEVEL-1 draws file are the Level-1 Mixed divisions.
         Measured at drafting on the only field we have: the L1 PDF holds exactly Mixed
         50/60/70/80, the L2 PDF holds the other 46, overlap 0 — matching his recorded split
         exactly. **It is never silent**: the line this returns names what was read and where it
         came from, and the resolved list rides on `td-editor-plan/v1` so the browser sort reads
         the same answer rather than re-deriving it.

    A cold year (2024/2025) may file differently. That is a FINDING to report, never a quiet
    patch (D-19 / open item A-1) — the tick-box is how it gets corrected.

    DISPLAY ONLY. Nothing here reaches placement; `master_schedule._TYPE_ORDER` is untouched.
    """
    # {parent division name: the level of the draws file it was printed in}. RR groups join
    # through `division_parent` — the TD only ever names parents.
    printed = {}
    for lvl in sorted(names_by_level):
        for name in names_by_level[lvl]:
            printed.setdefault(wwtc_ingest.division_parent(name), str(lvl))

    if named:
        out = []
        for name in named:
            parent = wwtc_ingest.division_parent(name)
            if parent not in printed:
                warn.append(f"Level-1 Mixed: no division named {name!r}."
                            f"{_did_you_mean(name, printed)} Nothing was changed.")
            elif not DO.is_mixed(parent):
                warn.append(f"Level-1 Mixed: {name} is not a Mixed division, and the Level-1 "
                            f"tick-box covers Mixed only — the division order was NOT changed "
                            f"for it. Every non-Mixed division sorts by gender and type, which "
                            f"the sanction level does not affect")
            else:
                out.append(parent)
        resolved = DO.sort_divisions(set(out), out)
        return resolved, (
            f"Level-1 Mixed: {', '.join(resolved) if resolved else '(none)'} — from the "
            f"tournament director's Setup console answer.")

    derived = [p for p, lvl in printed.items() if lvl == "1" and DO.is_mixed(p)]
    resolved = DO.sort_divisions(derived, derived)
    return resolved, (
        f"Level-1 Mixed: {', '.join(resolved) if resolved else '(none)'} — derived, not set. "
        f"These are the Mixed divisions printed in the LEVEL-1 draws file. No Level-1 Mixed "
        f"list was named in the Setup console; naming one there wins over this.")


def _mixed_level_1(cfg, names_by_level):
    """Resolve rule 45's tick-box ONCE per build and park the answer where the display surfaces
    can read it: `cfg.mixed_level_1_resolved` (the list the sort key takes),
    `cfg.mixed_level_1_note` (the one informational line) and `cfg.mixed_level_1_warnings`.
    Returns the same three, for the build dict. Display only — placement never reads any of
    them, and this runs AFTER the gate precisely so it cannot be mistaken for one of its
    inputs."""
    warn: list = []
    resolved, note = _resolve_mixed_level_1(
        (getattr(cfg, "mixed_level_1", None) or {}).get("divisions"), names_by_level, warn)
    cfg.mixed_level_1_resolved = resolved
    cfg.mixed_level_1_note = note
    cfg.mixed_level_1_warnings = warn
    return resolved, note, warn


def _master_assigned_days(levels, dates, finals_map=None, events=None, desk_seed=True,
                          same_day_finish=None):
    """Pass 1 (CANON-2 default): finalized draws -> master schedule -> (event, rnd) -> day map
    + the master's advisory warnings (F7-6: previously discarded — the hole that let an
    infeasible pin slide silently) + ASSIGN-1's provenance record. Dates come from the SLATE
    (not module constants); finals_map (td-finals-map/v1, validated upstream) pins the TD's
    finals days, computed layout otherwise. F7-4: when the engine's events are supplied, RR
    group draws are bound to their parent's days (see _expand_rr_groups).

    ASSIGN-1 (ruling 32) changes the map's CONTENT, not its plumbing: the elimination rounds
    the desk published are seeded from the desk and each unstamped final is anchored to its own
    desk semifinal (ruling 30). **ASSIGN-2 (ruling 40) extends the same seed to round-robin** —
    the rounds the desk stamped, plus each group's unstamped tail at last-stamped + 1 (ruling
    41) — so the only cells still on the computed cascade are those the desk never published.
    *(Ruling 31 deferred RR seeding on the ground that no answer key existed to score it; the
    committed match report carries all 45 RR matches dated and timed, so ruling 39 reopened it.
    The match report SCORES and never seeds — see `tests/`, and ruling 42.)*
    Provenance is `{(event, rnd): "desk"|"anchored"|"pinned"|"computed"}` — an anchored cell is
    derived from a desk stamp but is not itself one, and a `pinned` day is the TD's own console
    choice overriding the desk, neither of which any neighbouring label states truthfully.
    `desk_seed=False` rebuilds the pre-ASSIGN-1/2 computed map (diagnostics and the A/B
    harness). Deterministic; read-only."""
    draws = _level_draws(levels)                       # parsed once, shared by every reader
    divs = MS.divisions_from_draws(draws)
    pinned = set(finals_map or ())
    # REKEY-1 (A7a): the locked-day shifts, emitted STRUCTURALLY beside the prose sentence the
    # warning list already carries. The sentence's wording is LANG-1's and is untouched; this is
    # the same fact in a shape a renderer can read. Both displacement sites below fill it — a
    # half-wired model would silently under-report — and each record names the schedule rows it
    # covers, because a round-robin group's DISPLAY round and its rows' flat match index are not
    # the same number. Nothing is recomputed and no day moves.
    shifts: list = []
    # KEY-1: the desk stamps are read against the DRAWS' own printed window, not the slate's.
    # In January the two are the same window and the seed is unmoved; in September the draws are
    # last season's and the slate is next January's, and matching them by calendar date rotates
    # every desk-stamped day one weekday without saying so. Derived once per build, no lane flag
    # and no mode — January's safety is the translation's identity property, not a branch.
    window_warn: list = []
    source_dates = _draws_window(levels, window_warn) if desk_seed else None
    seed, warnings = (_desk_seed(levels, dates, draws, source_dates) if desk_seed else ({}, []))
    rr_stamped, rr_anchored, rr_warn = (_rr_desk_seed(levels, dates, draws, source_dates)
                                        if desk_seed else ({}, {}, []))
    warnings[:0] = window_warn
    warnings.extend(rr_warn)
    rr_days = {**rr_stamped, **rr_anchored}
    rr_parent, rr_parent_stamped = _rr_parent_days(rr_days, divs, stamped=rr_stamped,
                                                   warn=warnings,
                                                   group_rounds=_rr_group_rounds(draws))
    finals = _desk_finals(seed, divs, dates, skip=pinned, warn=warnings)
    finals.update(_rr_parent_finals(rr_parent, divs, skip=pinned))
    # ENG-1 / D-41: resolve the TD's named divisions against the REAL division list once, here,
    # and warn on a name that matches nothing. The console emits free text and the two consumers
    # key off different name spaces (the master uses draw-parent names, the engine uses the
    # engine's, which for round-robin carry a "— Group N" suffix), so an unresolvable name used to
    # be a completely silent no-op — a typo, or a round-robin division, simply did nothing while
    # the warning said the feature was on.
    joined = _resolve_same_day_finish(same_day_finish, divs, warnings)
    ms = MS.build_master_schedule(divs, dates, finals_map=finals_map or None,
                                  finals_anchors=finals or None,
                                  same_day_finish=joined)
    warnings.extend(ms.warnings)
    base = MS.assigned_day_map(ms, divs)
    rounds_by = {d.event: d.rounds for d in divs}
    # The desk's own days win over the computed cascade (ruling 32) — except a division whose
    # final the TD pinned through the finals-map editor. A pin outranks the desk for the WHOLE
    # division, not just its last cell: the pinned cascade rides backward from the pinned day
    # (the semantic the editor draws), so seeding that division's earlier rounds from the desk
    # would leave rounds landing AFTER the final they feed. Loud where it actually displaces a
    # desk day, silent on a zero-drag round trip where the pin reproduces the desk layout.
    for (ev, rnd), day in seed.items():
        if (ev, rnd) not in base:
            continue
        if ev in pinned:
            if base[(ev, rnd)] != day:
                # The elimination lane — measured on the 2026 field, the site that produces ALL 6
                # of that run's shifts (both pinned divisions are single_elim). An elim round's
                # display round IS its schedule rows' `round`, so it covers itself.
                shifts.append({"event": ev, "round": rnd, "was": day, "now": base[(ev, rnd)],
                               "match_rounds": [rnd]})
                warnings.append(
                    f"{ev} final locked to "
                    f"{'a later' if base[(ev, rnd)] > day else 'an earlier'} day. Round {rnd}: "
                    f"{_short_day(day)} → {_short_day(base[(ev, rnd)])}.")
            continue
        if ev in joined:
            # ENG-1 / D-41: a same-day-finish division is the TD's own instruction, given AFTER
            # the desk published its layout, so it outranks the desk exactly as a finals pin does.
            # Without this the desk seed wrote every published day straight back over the join and
            # the feature was completely inert on the product lane — while the master still told
            # the Operator "SAME-DAY FINISH is on". The tool said it had done what he asked and
            # had not.
            if base[(ev, rnd)] != day:
                # LANG-1: restated in item 25's shape. This warning is not one of the brief's
                # two enumerated pin templates, but it lands on the SAME warning bar in the same
                # sentence pattern — leaving it would put two conventions on one surface, the
                # half-swept failure §3.4 names. Flagged at ship as one item beyond the list.
                warnings.append(
                    f"{ev} set to finish in one day. Round {rnd}: "
                    f"{_short_day(day)} → {_short_day(base[(ev, rnd)])}.")
            continue
        base[(ev, rnd)] = day

    # Provenance is classified from the FINISHED map against the desk's own layout, not from
    # which branch above happened to write a cell. The difference only shows on the pinned lane,
    # and it matters there: a zero-drag courier round trip pins every division, so a
    # branch-based record would have labelled all 243 cells `computed` while the map was
    # byte-identical to the desk's.
    #
    # FOUR values (Operator sign-off 2026-07-30, amending §7/ruling 30's three). The fourth is
    # `pinned` — a day the TD chose in the finals-map console that MOVED his division off the day
    # it would otherwise have had. Without it those cells read `computed`, filing the most
    # deliberate day in the map as the one nobody chose. §7's "three values, not two" was an
    # argument against collapsing `anchored` into its neighbours; a `pinned` label was not a
    # question at the time.
    #
    # `pinned` means the pin MOVED something, not merely that a pin exists — the same test the
    # desk labels get. A zero-drag courier round trip pins all 50 divisions while changing
    # nothing, so labelling on the existence of a pin would report 69 round-robin cells as the
    # TD's choices when he accepted the draft untouched. Measuring the move needs the finals day
    # the division would have had with no pins at all, which is one extra master build (pure
    # computation over the divisions — no second pass over the PDFs) and only when pins exist.
    desk_days = dict(seed)
    desk_days.update(rr_parent)                                    # every RR parent round
    ref_finals = _desk_finals(seed, divs, dates)                   # unskipped: the answer key
    ref_finals.update(_rr_parent_finals(rr_parent, divs))
    for ev, day in ref_finals.items():
        desk_days.setdefault((ev, rounds_by[ev]), day)
    moved = set()
    if pinned:
        ref = MS.build_master_schedule(divs, dates, finals_anchors=ref_finals or None)
        moved = {ev for ev in pinned if ref.finals_day.get(ev) != ms.finals_day.get(ev)}
    published = set(seed) | rr_parent_stamped          # cells the desk itself printed a day for
    src = {}
    for key in base:
        day = desk_days.get(key)
        if day is not None and base[key] == day:
            src[key] = "desk" if key in published else "anchored"
        else:
            src[key] = "pinned" if key[0] in moved else "computed"
    amap = _expand_rr_groups(base, ms, divs, events) if events else base
    # The true circle round behind an RR group event's FLAT match index, read off the real
    # EventSpecs once (the same arithmetic `_expand_rr_groups` and `_rr_group_days` use).
    rr_teams = {ev.name: len(ev.teams) for ev in (events or ())
                if ev.fmt == "round_robin" and " — Group" in ev.name and len(ev.teams) >= 3}

    def _true_round(k):
        m = rr_teams.get(k[0])
        return None if m is None else (k[1] - 1) // (m // 2) + 1

    # ASSIGN-2: the desk's own RR group days win over that end-aligned expansion, the same way
    # the desk's elimination days win over the cascade — but only where the TD has not pinned the
    # division, whose pin outranks the desk for the whole division exactly as on the elim side.
    # Including the elim side's loudness: a pin that actually displaces a desk-published group day
    # is named, once per (group, round), rather than dropping the desk's layout in silence.
    rr_group = _rr_group_days(rr_days, events)
    displaced = {}
    displaced_rows: dict = {}          # REKEY-1: the FLAT match indices each display round covers
    for key, day in rr_group.items():
        if key not in amap:
            continue
        if key[0].split(" — Group")[0] in pinned:
            if amap[key] != day:
                displaced.setdefault((key[0], _true_round(key)), (day, amap[key]))
                displaced_rows.setdefault((key[0], _true_round(key)), []).append(key[1])
            continue
        amap[key] = day
    for (name, r), (day, placed) in sorted(displaced.items()):
        # REKEY-1: the round-robin lane, wired to the same model. Measured on the 2026 field this
        # site fires 0 times — no pinned division is round-robin there — so a green 2026 run is
        # NOT evidence it works; `tests/rekey1_changes.py` Part C carries a crafted fixture.
        # A group's schedule rows carry the FLAT match index, not this display round, so the
        # record names both rather than leaving a consumer to re-derive the arithmetic.
        shifts.append({"event": name, "round": r, "was": day, "now": placed,
                       "match_rounds": sorted(displaced_rows.get((name, r), []))})
        warnings.append(
            f"{name} final locked to {'a later' if placed > day else 'an earlier'} day. "
            f"Round {r}: {_short_day(day)} → {_short_day(placed)}.")
    for k in amap:                                     # anything the desk never published stays
        if k in src:                                   # computed; a moved pin owns its groups
            continue
        if k[0].split(" — Group")[0] in moved:
            src[k] = "pinned"
            continue
        tr = _true_round(k)                            # classified from the FINISHED map, as above
        if tr is not None and amap[k] == rr_days.get((k[0], tr)):
            src[k] = "desk" if (k[0], tr) in rr_stamped else "anchored"
        else:
            src[k] = "computed"
    # Sorted so the page is stable run to run; `warnings` keeps its own emission order verbatim.
    return amap, warnings, src, sorted(shifts, key=lambda s: (s["event"], s["round"] or 0))


def _gate(cfg, levels, slate_doc, assigned_days, finals_map, events=None):
    """CANON-2 default resolution for the R7-2 assigned-day gate. Returns the master's advisory
    warnings, ASSIGN-1's provenance record and REKEY-1's locked-day shifts ([] / {} / [] on the
    supplied-map and OFF paths — no master was computed here, so there is nothing to report).
    None (default) -> compute the master day-map (two-pass lane, the product).
    dict           -> caller-supplied map (e.g. a courier split already ran Pass 1).
    False          -> gate OFF: the legacy earliest-feasible packing. DIAGNOSTIC ONLY (D-3) —
                      exists for old-vs-new forensics; not a documented mode, not in the runbook."""
    if assigned_days is False:
        return [], {}, []
    if assigned_days:
        cfg.assigned_days = assigned_days
        _check_day_map(cfg)                 # CAD-1 rung 0 — loud, before any placement
        return [], {}, []
    # ENG-1 / D-41: the TD's named same-day-finish divisions reach Pass 1 here. The switch is a
    # DAY-MAP act first (the final joins its penultimate round's day) and a placement act second
    # (the 150-minute gap), so the same list has to be visible to both halves.
    cfg.assigned_days, warnings, sources, shifts = _master_assigned_days(
        levels, slate_doc["dates"], finals_map, events=events,
        same_day_finish=(cfg.same_day_finish or {}).get("divisions"))
    # RUNG 0 IS NOT APPLIED TO THE COMPUTED MAP, and that is a decision measured rather than an
    # oversight. On a short window the master's own two-pass lay-out has to double-book a
    # division-day — the real nine-day console-derived slate does exactly that for a round-robin
    # group — and rung 0 firing there would pre-empt rung 2 with the WRONG answer: it names one
    # division and tells the director to give it a separate day for each round, when the true
    # finding is that the week is too short and the fix is more venue-days. Rung 2 says that,
    # with remedies it has re-run for real. Rung 0 exists for a map the tool did NOT compute,
    # where an unexplained unplaced match is the only alternative.
    return warnings, sources, shifts


# ---------------------------------------------------------------------------------------------
# CAD-1 (Operator rulings R3/R4, 2026-08-18) — THE FEASIBILITY GATE.
#
# The tool has never told the director "no". Every rung of the old engine ended in a placement,
# because 0-unplaced was held by letting some other rule bend — and the last rule left to bend
# was one round a division a day. With rule 16 ruled INVARIABLE (R1) that escape is gone, so
# there is now a week the engine genuinely cannot seat, and something has to decide what happens
# then. This is that decision, and it is the Operator's: the WEEK IS REFUSED. No deliverable is
# emitted, and the refusal arrives carrying remedies that have each been re-run for real.
#
# THE BOUNDARY AGAINST D-52's APPENDIX W.7, drawn in the brief and repeated here because the
# words collide: W.7 governs a PUBLISHED DAY the field cannot hold — that day's overflow moves to
# the nearest day and is recorded, and 0-unplaced is guarded by reporting, never by refusing to
# place. This gate governs an INFEASIBLE WEEK — a week no placement can seat at 0 not-scheduled.
# The scopes do not overlap and neither yields to the other. D-52's outcome-4 decision screen
# reuses `probe_remedies` below rather than growing a second copy of it.
#
# TWO RUNGS, NOT THREE. An arithmetic pre-screen was designed, measured, and DROPPED: it has zero
# false positives by construction, but it is provably insufficient alone — its first refusal
# comes at 50% courts while real placement fails from 70%, and it PASSES the real nine-day
# console-derived slate that loses 24 matches. Aggregate arithmetic cannot see player-level
# constraints or the greedy engine's own suboptimality. The real build IS the verdict, at ~2.2 s,
# deterministic; precedent for build-as-verdict is FMAP-2's `engine_check`.

BAND_YIELD_CEILING = 25
"""Ruling R4 as first set (15) and RE-RULED at ship (25, Operator 2026-08-18).

R4 put the ceiling at the committed field's footprint of 10 recorded early-start yields plus 5 of
headroom. Measured at ship across every single finals-day move the finals editor allows — 72 of
them, one division's final one day earlier or later — 15 refused TWO: Men's 50 & over singles
01-31 -> 02-01 at 16 yields, and Mixed 70 & over doubles 01-27 -> 01-26 at 17. BOTH PLACED EVERY
MATCH. Nothing was unschedulable; the week was refused on a count of given-up courtesies alone,
and one of the two is the first card on the board.

A refusal that fires on an ordinary edit with nothing actually wrong teaches a director to stop
reading refusals, so the Operator raised it to 25: clear of the worst ordinary edit measured (17)
with room to spare, still a hard stop on a week that genuinely comes apart. Re-measured over the
same 72 moves after the re-ruling: 0 refused, 55 of them at 10 yields, the worst still 17 — eight
of clearance over anything ordinary editing produces. The footprint on the
committed field is unmoved at 10, and every yield is still recorded and still printed in the
pre-publication report whether or not the ceiling is near — the ceiling decides whether the week
is REFUSED, never whether the director is told.

BAND YIELDS ONLY — day-shape records stay report-only exactly as today (38 on the committed
field, long-ruled advisory), because this ceiling is ruled for the early-start courtesy and the
same-day-finish week's 16 day-shape records must not trip a limit that was never about them."""

_BAND_GATES = ("day_bands", "day_bands+day_shape")


class DayMapRefused(ValueError):
    """Rung 0: the day map itself puts two rounds of one division on one day.

    Loud and pre-placement. Not strictly needed for safety — a doctored map cannot mint a cadence
    cell past the forward-only limit; it turns into a recorded move or a match with nowhere to
    play — but that residual is a match the director is told has no place, with no reason given.
    This names the division and the day instead."""


class WeekRefused(RuntimeError):
    """Rung 2: no legal schedule exists for this week, so no schedule is published.

    Carries `reasons` (plain English, one per failed test), `result` (the build that failed, for
    the engineer and the report — it is not a deliverable), and `remedies` (each re-run for real).
    """

    def __init__(self, reasons, result, remedies=None, shortfall=None):
        self.reasons = list(reasons)
        self.result = result
        self.remedies = list(remedies or [])
        # OI-56: what to ADD, in courts · club · days · hours, every number confirmed by a real
        # build. Rides beside `remedies` because it answers a different question: the remedies
        # rearrange supply the club already has, this one buys courts. Empty when the refusal was
        # raised while probing, exactly as `remedies` is.
        self.shortfall = shortfall or {"reasons": [], "builds": {"used": 0, "budget": 0},
                                       "not_tried": [], "partial": False}
        super().__init__(" ".join(self.reasons))


def band_yields_of(result):
    """The recorded early-start yields in a result — the rows the ceiling counts.

    CAD-1 patch 5 puts a `gate` field on every `rule_escapes` row naming which rule bent. The
    field is additive inside an existing list, so no contract gained anything; a row written
    before this build carries no `gate` and is counted, because the pre-CAD-1 escape lifted the
    early-start band among others."""
    return [r for r in ((result or {}).get("rule_escapes") or [])
            if r.get("gate", _BAND_GATES[0]) in _BAND_GATES]


def _name_some(divisions):
    """`a`, `a, b`, `a, b, c`, `a, b, c and N more` — the refusal's one way of naming divisions.

    Lifted out of `check_week`'s finals sentence, which has always read this way, so ANSWER-1's
    three new naming sites cannot drift from it. Byte-for-byte what that sentence built inline."""
    divisions = list(divisions)
    return ", ".join(divisions[:3]) + (f" and {len(divisions) - 3} more"
                                       if len(divisions) > 3 else "")


def _divisions_of(mids, events):
    """The divisions behind a list of match ids, read off the result's own event list.

    ANSWER-1 §0.3. `E{n}-R{r}-M{m}` indexes `cfg.events`, and `result["events"]` is that same
    list of names (`scheduler_multi:1343`), so a refusal can name what is stuck WITHOUT the
    config — which is what lets every caller of `check_week` say the same sentence. A round-robin
    id is `{prefix}-M{ri}-{a}v{b}` and its `E{n}` prefix reads the same way.

    An id that cannot be read is skipped rather than guessed at: the count of stuck matches is
    the figure that must never be wrong, and it is taken from the list itself."""
    names, events = [], list(events or [])
    for mid in mids:
        try:
            idx = int(str(mid).split("-")[0][1:]) - 1
        except (ValueError, IndexError):
            continue
        if 0 <= idx < len(events) and events[idx] not in names:
            names.append(events[idx])
    return sorted(names)


def check_week(result):
    """The rung-2 tests, in plain English. An empty list means the week can be published."""
    reasons = []
    unplaced = (result or {}).get("unplaced") or []
    if unplaced:
        # ANSWER-1 A2 — THE UNPLACED SENTENCE NAMES ITS DIVISIONS, the shape the finals sentence
        # below has always used. The two halves of a refusal were asymmetric by construction: the
        # finals half named its divisions and this one named a bare count, so a director told
        # "24 matches have no place to play" had no way to know WHICH tournament was stuck. The
        # names are read off the result, never off a config, so `try_change`, the remedy probes
        # and the refusal itself all say the same sentence.
        divisions = _divisions_of(unplaced, (result or {}).get("events"))
        named = f" ({_name_some(divisions)})" if divisions else ""
        reasons.append(
            f"{len(unplaced)} match{'es have' if len(unplaced) != 1 else ' has'} no place to "
            f"play{named}. Every match has to fit for the week to work.")
    n = len(band_yields_of(result))
    if n > BAND_YIELD_CEILING:
        reasons.append(
            f"{n} matches would start later than the early start promised to a player who is in "
            f"three divisions that day. The most this week can absorb is {BAND_YIELD_CEILING}.")
    # BUDGET-1 §3.2 (R13, Operator sign-off 2026-08-22). The two rules that yield to nothing.
    # THIS is where they become hard — a rung-2 test in the existing list, in the existing plain
    # English, reaching the director through the existing `format_refusal`. No new refusal
    # surface is invented, which was the brief's condition.
    #
    # Placement still places and still records (rule 41 unchanged): 0-unplaced is never traded,
    # and a hard refusal inside placement is exactly how that guarantee breaks. The week is
    # refused here, whole, after the schedule exists — the same shape the unplaced test above has.
    #
    # One reason per rule, not one per match, and each names its own count: a director told
    # "11 things are wrong" acts differently from one told which rule broke and how widely.
    breaches = (result or {}).get("hard_venue_breaches") or []
    if breaches:
        main = (breaches[0].get("main_site_name")
                or breaches[0].get("main_site") or "the main site")
        for rule, one, many in (("main_site_finals", "final", "finals"),
                                ("main_site_l1_mixed",
                                 "Level 1 Mixed match", "Level 1 Mixed matches")):
            rows = [b for b in breaches if b["rule"] == rule]
            if not rows:
                continue
            divisions = sorted({b["event"] for b in rows})
            named = _name_some(divisions)
            reasons.append(
                f"{len(rows)} {one if len(rows) == 1 else many} would play away from {main} "
                f"({named}). Every {one} plays at {main} — that rule does not bend, so this week "
                f"cannot be published as planned.")
    return reasons


def _check_day_map(cfg):
    """Rung 0. Refuses a day map that asks one division to play two rounds on one day.

    The TD's same-day-finish switch is the one legitimate case and it is EXCUSED here, read off
    his own named division list — the two rounds it joins are his instruction, not a collision.
    """
    amap = cfg.assigned_days or {}
    if not amap:
        return
    named = {e for e in (cfg.same_day_finish or {}).get("divisions", []) or []}
    seen: dict = {}
    for (event, rnd), day in sorted(amap.items()):
        if event in named:
            continue
        tr = SM_true_round(cfg, event, rnd)
        held = seen.setdefault((event, day), set())
        if held and tr not in held:
            raise DayMapRefused(
                f"The planned days ask {event} to play two rounds on {day} "
                f"(rounds {', '.join(str(x) for x in sorted(held | {tr}))}). A division plays one "
                f"round a day, so this week cannot be built as planned. Give {event} a separate "
                f"day for each round.")
        held.add(tr)


def _remedy_slate(base, *, morning_full=False, satellites_all_days=False, extra_days=0):
    """One remedy applied to a copy of the courts & days document."""
    slate = copy.deepcopy(base)
    dates = list(slate["dates"])
    if extra_days:
        last = datetime.datetime.strptime(dates[-1], "%Y-%m-%d")
        dates += [(last + datetime.timedelta(days=i + 1)).strftime("%Y-%m-%d")
                  for i in range(extra_days)]
        slate["dates"] = dates
    for i, loc in enumerate(slate["locations"]):
        avail = loc["available"]
        if morning_full:
            for cell in avail.values():
                cell.pop("morning_courts", None)
                cell.pop("morning_until", None)
        if satellites_all_days and i > 0 and avail:
            sample = copy.deepcopy(next(iter(avail.values())))
            loc["available"] = {d: copy.deepcopy(sample) for d in dates}
        elif extra_days and avail:
            sample = copy.deepcopy(next(iter(avail.values())))
            for d in dates:
                avail.setdefault(d, copy.deepcopy(sample))
    return slate


def _stepup_clubs(slate):
    """Every club whose day cells carry a mid-morning step-up, in the director's own fill order.

    S-4 §3.3. `_remedy_slate(morning_full=True)` strips the step-up at EVERY club that carries
    one, while the shipped label said "the main site's" — bench-tuned wording on an edit that was
    already slate-agnostic. The label now names the clubs the edit actually touches."""
    return [loc["id"] for loc in (slate or {}).get("locations") or []
            if any(isinstance(c, dict) and c.get("morning_courts")
                   for c in (loc.get("available") or {}).values())]


def _closed_club_days(slate):
    """`(club, day)` for every day a NON-FIRST club is closed on, cheapest club first.

    R7's raw material, and the fence is in the word CLOSED: these are days the director already
    has the club for and has not booked it on. Nothing here proposes a club he does not have or
    a day the week does not run on — R2 forbids both and is untouched."""
    dates = list((slate or {}).get("dates") or [])
    out = []
    for loc in ((slate or {}).get("locations") or [])[1:]:
        avail = loc.get("available") or {}
        for day in dates:
            if day not in avail:
                out.append((loc["id"], day))
    return out


def _open_club_days(slate, pairs):
    """`slate` with each named club-day opened, in that club's OWN booked shape.

    The shape is copied from a day the club is already booked on, so an opened day is the club
    as he books it — not a day invented at some other club's court count."""
    s = copy.deepcopy(slate)
    want: dict = {}
    for club, day in pairs:
        want.setdefault(club, []).append(day)
    for loc in s["locations"]:
        days = want.get(loc["id"])
        if not days or not loc.get("available"):
            continue
        sample = copy.deepcopy(next(iter(loc["available"].values())))
        for day in days:
            loc["available"].setdefault(day, copy.deepcopy(sample))
    return s


# ⚠ BOTH BOUNDS ARE REPORTED, NEVER SILENT (R18). A search that stops somewhere and does not say
# where reads as "we checked everything" when it did not, which is the one thing this row must
# never do — the director acts on it by phoning a club.
_SAT_GREEDY_ROUNDS = 3


def _satellite_search(base_slate, run, refused=None):
    """R7 + R18: WHICH club, WHICH days, the fewest that change anything — never "open
    everything".

    ⚠ WHAT THIS REPLACED WAS UNUSABLE ADVICE. The shipped probe opened every non-first club on
    every date of the week at once. Measured on the invented five-club week: it took the booking
    from 326 court-days to 528 — four clubs opened on 28 days they were not booked for — to say
    one word about whether it helped. A director cannot act on that; he phones clubs.

    THREE STAGES, EACH PRUNE REPORTED:
      1 · one build per satellite club, that club opened on every day it is closed. A club whose
          FULL opening changes nothing has nothing worth searching day by day, and saying so
          costs one build instead of ten.
      2 · for the clubs that changed something, one build per closed day of theirs, cheapest
          first — so the answer is "this club, these days" and not "this club, the week".
      3 · when no single day clears it, GREEDY-ACCUMULATE (R18): fix in the most helpful day,
          re-test the rest, repeat. Bounded, and the bound is on the row.

    ⚠ THE FINAL SET IS RE-BUILT WHOLE BEFORE IT IS REPORTED. More courts can place FEWER matches
    (R-2, three measured instances), so a set assembled one day at a time is not a set that was
    ever built — and every number printed here is confirmed at exactly the configuration
    printed."""
    closed = _closed_club_days(base_slate)
    names = {loc["id"]: (loc.get("name") or loc["id"])
             for loc in base_slate["locations"]}
    row = {"remedy": "satellite_days", "clears": False, "unscheduled": None,
           "early_start_yields": None, "builds": 0, "club_days": [], "days": [],
           "clubs": [], "single_day_bound": 0, "greedy_bound": 0, "note": "",
           "not_tried": []}
    if not closed:
        row["clears"] = None
        row["note"] = ("not tried — every club you have is already open on every day of the "
                       "week, so there is no closed day to open")
        return _finish_sat(row, names)

    def score(pairs):
        row["builds"] += 1
        r = run(_open_club_days(base_slate, pairs))
        return (len(r["unplaced"]), len(r.get("hard_venue_breaches") or []),
                not check_week(r), r)

    # ---- stage 1 · one build per club, that club opened on every day it is closed.
    by_club: dict = {}
    for club, day in closed:
        by_club.setdefault(club, []).append(day)
    if refused is None:
        # The week as it stands is what "changed something" is measured against. Normally it
        # arrives with the refusal; without it, one build buys the comparison rather than
        # letting every club silently read as "changed nothing".
        base_u, base_h, _clear, _r = score([])
    else:
        base_u = len(refused.get("unplaced") or [])
        base_h = len(refused.get("hard_venue_breaches") or [])
    live, whole_club = [], {}
    for club, days in by_club.items():
        u, h, clear, _r = score([(club, d) for d in days])
        if clear or (u, h) < (base_u, base_h):
            live.append(club)
            whole_club[club] = clear
        else:
            row["not_tried"].append(
                f"{names[club]} was not tried day by day: opening it on all "
                f"{len(days)} days it is closed changed nothing about this week")
    if not live:
        row["note"] = ("no club you already have makes a difference on the days it is closed, "
                       "however many of them are opened")
        return _finish_sat(row, names)

    # ---- stage 2 · one build per closed day of the clubs that changed something. THE FEWEST
    # ---- THAT CHANGE ANYTHING (R7): a whole club opened is not an answer while one of its days
    # ---- might be, and "open this club all week" is the advice this search exists to replace.
    row["single_day_bound"] = sum(len(by_club[c]) for c in live)
    ranked = []
    for club in live:
        for day in by_club[club]:
            u, h, clear, _r = score([(club, day)])
            if clear:
                row.update(clears=True, unscheduled=u, club_days=[(club, day)],
                           days=[day], clubs=[club])
                row["note"] = f"{names[club]} opened on {_diag_day_label(day)} clears the week."
                return _finish_sat(row, names)
            ranked.append(((u, h), club, day))
    ranked.sort(key=lambda x: (x[0], list(by_club).index(x[1]), x[2]))

    # ---- stage 3 · greedy accumulation (R18, decision 7).
    chosen: list = []
    best = (base_u, base_h)
    for _round in range(_SAT_GREEDY_ROUNDS):
        row["greedy_bound"] = _round + 1
        pick = next(((s, c, d) for s, c, d in ranked if (c, d) not in chosen), None)
        if pick is None:
            break
        chosen.append((pick[1], pick[2]))
        u, h, clear, _r = score(chosen)
        if clear:
            break
        if (u, h) >= best:
            chosen.pop()                       # that day bought nothing on top of the others
            break
        best = (u, h)
        ranked = sorted(
            [((u2, h2), c, d) for (u2, h2), c, d in ranked if (c, d) not in chosen],
            key=lambda x: (x[0], list(by_club).index(x[1]), x[2]))
    # ⚠ THE WHOLE-CLUB OPENING IS THE FALLBACK, NEVER THE HEADLINE. Where stage 1 found that a
    # club opened on every closed day clears the week but no smaller set does, that IS the answer
    # and it is reported as what it is — the largest of the answers searched, not the first one
    # found.
    if not chosen:
        for club, cleared in whole_club.items():
            if cleared:
                chosen = [(club, d) for d in by_club[club]]
                row["note"] = (f"No single day at {names[club]}, and no accumulation of them, "
                               f"clears this week; opening it on all {len(by_club[club])} of the "
                               f"days it is closed does.")
                break
    if chosen:
        # RE-BUILT WHOLE. The set was assembled a day at a time and has never been built as a
        # set; non-monotonicity means the assembly is not evidence about the assembled thing.
        u, h, clear, r = score(chosen)
        row.update(clears=clear, unscheduled=u, club_days=list(chosen),
                   days=sorted({d for _c, d in chosen}),
                   clubs=sorted({c for c, _d in chosen}, key=lambda c: list(by_club).index(c)))
        row["early_start_yields"] = len(band_yields_of(r))
        if not clear:
            row["note"] = (f"{len(chosen)} closed club-day(s) opened together still leaves "
                           f"{u} match{'es' if u != 1 else ''} with nowhere to play.")
    else:
        row["note"] = "No closed club-day, alone or with the others, clears this week."
    return _finish_sat(row, names)


def _and_list(items):
    """`a`, `a and b`, `a, b and c` — the director's own register, never `a and b and c`."""
    items = list(items)
    if len(items) <= 2:
        return " and ".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _finish_sat(row, names):
    """The row's own sentence, its bounds, and R18's may-not-be-smallest caveat."""
    if row["club_days"]:
        by_club: dict = {}
        for club, day in sorted(row["club_days"], key=lambda cd: (cd[0], cd[1])):
            by_club.setdefault(club, []).append(day)
        row["label"] = "Open " + "; ".join(
            f"{names.get(c, c)} on {_and_list(_diag_day_label(d) for d in days)}"
            for c, days in by_club.items()) + "."
    else:
        row["label"] = ("Open a club you already have on a day it is closed — searched, and "
                        "named where one is found.")
    if len(row["club_days"]) > 1:
        row["note"] = ((row["note"] + " ") if row["note"] else "") + (
            "These were found one at a time and then built together, so a smaller combination "
            "may exist and was not searched for.")
    # ANSWER-1 A5 — THE BOUNDS ARE SAID ONLY WHERE THERE WAS A SEARCH TO BOUND. Measured on the
    # committed 2027 seed, where every club is open on every one of the ten days: the row said
    # "there is no closed day to open" and then "Bounds: 0 single club-day(s) tried, 0
    # accumulated round(s)" — a limit quoted on a search that had nothing to look at. Zero bounds
    # AND zero builds is the one shape that means the search space was empty; a stage-1 sweep that
    # found nothing worth opening has builds behind it and still reports its zeros, because there
    # the zeros say stage 2 never ran and that IS information.
    if row["single_day_bound"] or row["greedy_bound"] or row["builds"]:
        row["note"] = ((row["note"] + " ") if row["note"] else "") + (
            f"Bounds: {row['single_day_bound']} single club-day(s) tried, "
            f"{row['greedy_bound']} accumulated round(s).")
    if row["not_tried"]:
        row["note"] += " " + " ".join(n[0].upper() + n[1:] + "." for n in row["not_tried"])
    return row


def probe_remedies(levels=("1", "2"), constraints_doc=None, slate=None, overrides=None,
                   finals_map=None, combined=True, refused_result=None):
    """Re-run the REAL build once per remedy and report which of them clear the week.

    ⚠ S-4 §3.3 CUT THIS LIST FROM SIX TO TWO, AND IT CHANGES WHAT IS TRIED, NOT ONLY WHAT IS
    SHOWN — the prober stops at the first remedy that clears, so removing one moves what the
    others are asked. This is a deliberate behaviour change to an artifact frozen twice (OI-56
    §4, CAD-1's ruled order), on two Operator rulings:

      · R2 (2026-08-24) — adding a venue and adding days are NOT options. "Consider those not
        possible, define as NOT an option." The three day-adds are gone from this surface.
      · R5 (2026-08-25) — match length is INVARIABLE at 90 for this advice, on EVERY surface and
        in BOTH seasons (decision 2, option 2). `shorter_matches` is gone — AND IT WAS THE ONLY
        ONE THAT CLEARED the week measured. The cost was put to the Operator in those words and
        accepted: a director told in September that match length is fixed and in January that
        shortening it is the fix learns the advice depends on which screen he is on, and from
        then on trusts neither answer.

    `format_refusal` renders this list for September's booking step and January's build lanes
    alike. There is no season flag and no caller-dependent wording here, by ruling.

    Never recursive: each probe calls the build with the gate's own refusal caught, so a remedy
    that does not clear the week reports its residue instead of raising."""
    base_slate = slate or wwtc_slate()
    doc = constraints_doc or default_constraints()

    # ⚠ THE MORNING PROBE IS SKIPPED WITH A REASON WHERE THERE IS NO STEP-UP TO OPEN. On a slate
    # where no club steps up mid-morning the edit is a no-op and the build is byte-identical to
    # one already run, so reporting it "not enough" would be a verdict on work never done.
    stepup = _stepup_clubs(base_slate)
    names = {loc["id"]: (loc.get("name") or loc["id"]) for loc in base_slate["locations"]}

    # OI-56 §3.5 — THE HONESTY FIX. Satellite courts are worth nothing against a main-site rule:
    # rules 38/39/40 put every final and every Level 1 Mixed match at the main site regardless of
    # how many courts the other clubs open, and R13 made that yield to nothing. Measured at this
    # HEAD: against a refusal raised ONLY by those rules, opening the other two venues on every
    # day of the week clears nothing at 2 courts and nothing at 4.
    #
    # So when every reason raised is a main-site rule, this probe's NOTE says it cannot address
    # one, instead of "a cheaper change already fixes the week" — which reads as though it might
    # have. NO PROBE IS ADDED, DELETED OR REORDERED, and the probe is still listed and still run
    # in its ruled place: only the sentence changes.
    main_site_only = False
    if refused_result is not None:
        main_site_only = (bool((refused_result.get("hard_venue_breaches") or []))
                          and not (refused_result.get("unplaced") or [])
                          and len(band_yields_of(refused_result)) <= BAND_YIELD_CEILING)

    def run(edited_slate, edited_doc=None):
        """One real build on THE LANE THAT REFUSED — never a near neighbour of it, because a
        remedy measured on a different lane is not a measurement of this week."""
        kw = {"slate": edited_slate, "constraints_doc": edited_doc or doc}
        try:
            return (build_combined(levels=levels, overrides=overrides, finals_map=finals_map,
                                   _probing=True, **kw) if combined
                    else build(level=levels[0], overrides=overrides, finals_map=finals_map,
                               _probing=True, **kw))["result"]
        except WeekRefused as e:            # S-4 §3.7: this DOES happen under `_probing` —
            return e.result                 # `_refuse_if_infeasible` raises regardless

    # ---- PROBE 1 · the mid-morning step-up, unchanged except for its label and its skip.
    if not stepup:
        morning = {
            "remedy": "morning_courts", "clears": None, "builds": 0, "unscheduled": None,
            "early_start_yields": None,
            "label": "Open the full court count from the start of the day.",
            "note": ("not tried — no club steps up mid-morning on this booking, so there is "
                     "nothing to open earlier")}
    else:
        label = (f"Open the full court count at {' and '.join(names[c] for c in stepup)} from "
                 f"the start of the day, instead of stepping up mid-morning.")
        try:
            r = run(_remedy_slate(base_slate, morning_full=True))
            reasons = check_week(r)
            morning = {"remedy": "morning_courts", "label": label, "clears": not reasons,
                       "builds": 1, "unscheduled": len(r["unplaced"]),
                       "early_start_yields": len(band_yields_of(r)),
                       "note": "" if not reasons else " ".join(reasons)}
        except (DayMapRefused, ValueError, AssertionError) as e:
            morning = {"remedy": "morning_courts", "label": label, "clears": False, "builds": 1,
                       "unscheduled": None, "early_start_yields": None,
                       "note": f"could not be tried: {e}"}

    # ---- PROBE 2 · which club, which days (R7), accumulated when no single day is enough (R18).
    # THE ORDER IS THE ANSWER, so this is not searched when the cheaper lever already worked.
    # ⚠ THE MAIN-SITE NOTE WINS OVER "a cheaper change already fixes the week" — OI-56 §3.5's
    # precedence, kept exactly. When every reason raised is a main-site rule, saying only that
    # something cheaper worked reads as though this MIGHT have; saying it cannot address a
    # main-site rule is the fact the director needs, and he needs it whether or not the cheaper
    # lever happened to clear.
    skip = None
    if main_site_only:
        skip = ("not tried — it cannot address a main-site rule: every final and every Level 1 "
                "Mixed match plays at the main site however many courts the other clubs open")
    elif morning["clears"]:
        skip = "not tried — a cheaper change already fixes the week"
    if skip:
        sat = {"remedy": "satellite_days", "clears": None, "builds": 0, "unscheduled": None,
               "early_start_yields": None, "club_days": [], "days": [], "clubs": [],
               "single_day_bound": 0, "greedy_bound": 0, "not_tried": [],
               "label": "Open a club you already have on a day it is closed.", "note": skip}
    else:
        sat = _satellite_search(base_slate, run, refused=refused_result)
    return [morning, sat]


# =============================================================================================
# S-4 §3.4 — ANSWER 2: THE BENDABLE RULES. R3's ruled order is courts FIRST, then these.
#
# THE SET IS NINE, IT IS CLOSED, AND EVERY EXCLUSION IS A RULING (decision 1, 2026-08-25, as
# amended by decision 3 the same day). A build session that finds a tenth candidate does not add
# it — it stops and returns to the Operator, and `tests/s4_court_answer.py` part F is written so
# an addition FAILS rather than passing quietly.
#
# ⚠ THE COUNT CONVENTION, PINNED: NINE RULES · EIGHT LEVERS · SEVEN BUILDS. Locals-first and
# multi-division-first are two rules the director states separately and one key the engine reads,
# so they are one build; and the mid-morning step-up is CITED from the remedies row rather than
# re-built, because the one lever that appears in both lists must appear ONCE.
#
# WHAT IS LOCKED, AND WHY EACH ONE IS:
#   · governing-body rules — rest between matches, singles before doubles, a Mixed team is one
#     man and one woman, age eligibility, the draw format, the pre-publication conflict check.
#   · the Operator's own rulings — every final and every Level 1 Mixed match at the main site
#     (BUDGET-1 R13), one round per division per day (CAD-1), no day changes on the edit console
#     (rule 51), and MATCH LENGTH (R5).
#   · locked by the machinery — 80-and-over at the main site cannot be emptied (`ValueError`,
#     measured), and match length above 90 is already refused on screen.
#
# ⚠ THREE CONTROLS ARE EXCLUDED FOR MOVING NOTHING, and the reason is the Operator's own standing
# test: a tool that suggests a change measured to move nothing is worse than one that says
# nothing — he acts on it, waits, sees no difference, and reads every later suggestion as a
# guess. `matches_per_day_target` moves nothing by contract; `match_caps` moved 0 of 760 at
# either setting; and `finals_per_day` is inert BY CONSTRUCTION — `apply_constraints` maps
# nothing from it onto the config and placement cannot read it, so varying it re-runs a
# byte-identical build on ANY field, forever. All three keep working exactly as they do today and
# ride every document; this governs only what the tool PROPOSES.
# =============================================================================================

BENDABLE_RULES = (
    # (rule as the director says it, lever, edit) — the BENT FORM OF EACH RULE IS PINNED so the
    # advice is reproducible and the harness can assert it.
    ("The mid-morning court step-up", "morning_courts", None),
    ("The earliest a final may start", "finals_earliest",
     lambda d: d.pop("finals_earliest", None)),
    ("The earliest start for 80-and-over", "earliest_start_by_age",
     lambda d: d.pop("earliest_start_by_age", None)),
    ("Singles, then mixed, then doubles through the day", "day_shape",
     lambda d: d.pop("day_shape", None)),
    ("Locals first", "placement_policy", lambda d: d.update(placement_policy={})),
    ("Players in several divisions first", "placement_policy", lambda d: d.update(
        placement_policy={})),
    ("The order your clubs fill in", "venue_rules.rank_order",
     lambda d: d.setdefault("venue_rules", {}).update(rank_order=False)),
    ("The 2pm avoid for Level 1 Mixed", "venue_rules.l1_mixed_latest_start",
     lambda d: d.setdefault("venue_rules", {}).pop("l1_mixed_latest_start", None)),
    ("The peak-hour cap", "venue_rules.peak_window",
     lambda d: d.setdefault("venue_rules", {}).pop("peak_window", None)),
)


def bendable_pass(levels=("1", "2"), constraints_doc=None, slate=None, overrides=None,
                  finals_map=None, combined=True, refused_result=None, morning_row=None):
    """Answer 2 (R3): every rule in the signed-off set, re-run ONCE at his booked configuration.

    One real build per LEVER, graded on the WHOLE refusal — never on the one reason it was picked
    to address, because a change that places every stuck match and pushes a third final off the
    main site is not a fix (R-2's second consequence, and at this HEAD that is a real
    configuration rather than a hypothetical).

    Each row reports what was re-run and what it did: whether it cleared, what was left, and its
    delta against the refusal as it stands. The set and the counts are §3.4's and they are
    CLOSED — see the block above.

    `morning_row` is the remedies row for the mid-morning step-up. The one lever that appears in
    both answers is CITED from there rather than re-built: two builds of the same slate edit
    would be two chances to disagree about one number."""
    base_slate = slate or wwtc_slate()
    doc = constraints_doc or default_constraints()
    before = (len((refused_result or {}).get("unplaced") or []),
              len((refused_result or {}).get("hard_venue_breaches") or []))

    def run(edited_doc):
        try:
            return (build_combined(levels=levels, constraints_doc=edited_doc, slate=base_slate,
                                   overrides=overrides, finals_map=finals_map,
                                   _probing=True) if combined
                    else build(level=levels[0], constraints_doc=edited_doc, slate=base_slate,
                               overrides=overrides, finals_map=finals_map,
                               _probing=True))["result"]
        except WeekRefused as e:
            return e.result

    rows, built_by_lever = [], {}
    for rule, lever, edit in BENDABLE_RULES:
        if edit is None:
            # CITED, NEVER RE-BUILT.
            row = {"rule": rule, "lever": lever, "built": False,
                   "cited_from": "morning_courts",
                   "clears": (morning_row or {}).get("clears"),
                   "unplaced": (morning_row or {}).get("unscheduled"),
                   "hard_breaches": None, "delta": None,
                   "note": ("read off the courts answer above, where this change was already "
                            "tried for real on this week")}
            rows.append(row)
            continue
        if lever in built_by_lever:
            # TWO RULES, ONE LEVER — the director states them separately and the engine reads one
            # key, so they share a build and both rows say so rather than one being dropped.
            twin = built_by_lever[lever]
            rows.append(dict(twin, rule=rule, built=False, cited_from=lever,
                             note=("this and the rule above are one setting, so they were "
                                   "re-run together")))
            continue
        d = copy.deepcopy(doc)
        edit(d)
        try:
            r = run(d)
        except (DayMapRefused, ValueError, AssertionError) as e:
            rows.append({"rule": rule, "lever": lever, "built": True, "cited_from": None,
                         "clears": False, "unplaced": None, "hard_breaches": None,
                         "delta": None, "note": f"could not be tried: {e}"})
            continue
        u, h = len(r.get("unplaced") or []), len(r.get("hard_venue_breaches") or [])
        reasons = check_week(r)
        row = {"rule": rule, "lever": lever, "built": True, "cited_from": None,
               "clears": not reasons, "unplaced": u, "hard_breaches": h,
               "delta": {"unplaced": u - before[0], "hard_breaches": h - before[1]},
               "note": ("every match fits and every rule stands" if not reasons
                        else " ".join(reasons))}
        built_by_lever[lever] = row
        rows.append(row)
    return rows


# =============================================================================================
# OI-56 (brief approved 2026-08-23) — THE SHORTFALL ANSWER IN COURTS · CLUB · HOURS.
#
# When the week is refused, the refusal names how many courts, at which club, on which days, in
# which of the day's three bands — every number confirmed by a real build — and where it cannot
# find an answer, what it tried and what it did not. Before this, a refusal named a club for the
# whole tournament and offered six fixes, not one of which buys a court.
#
# ⚠ IT IS ITS OWN SECTION AND NEVER A SEVENTH PROBE. `probe_remedies` STOPS at the first remedy
# that clears — a ruled, measured-correct order — and at every shortfall measured for this build
# the FIRST probe clears, so a court lever appended to that list would print "not tried" exactly
# when the director most needs it. "Open your full court count from 08:00" and "add one court at
# Mission Hills on Thursday before 11:00" are different purchases and he needs both.
#
# ⚠ SHORTFALL IS NOT A SYNONYM FOR "MATCHES UNPLACED". Measured at this HEAD: at 72% and 70% of
# the booked courts EVERY MATCH IS PLACED and the week is refused on the finals rule alone. That
# is the FIRST refusal a September run now meets — R13 shipped after the 8/18 research and moved
# the cliff. The two halves of a refusal also carry OPPOSITE evidence: `hard_venue_breaches`
# already knows the club, the day, the hour and the division; `unplaced` is bare match ids.
#
# ⚠ NON-MONOTONE IN SUPPLY, PROVED (§0.8, three instances at this HEAD). More courts can place
# FEWER matches, and a court that fixes one reason can create another. Two consequences, and the
# whole design leans on them:
#     1. Every number printed is confirmed by a real build AT EXACTLY THAT NUMBER. No
#        interpolation between measured points, no "at least N", no arithmetic on top of a build.
#     2. A configuration is graded on the WHOLE refusal, never on the one reason it was chosen to
#        fix. A remedy that clears the unplaced list and displaces a third final is not a remedy.
# =============================================================================================

# The order the ladder walks, and its bound. Stated here rather than buried in the loop because
# the COST is part of the design: bounded by the calendar, not by a search space, so there is no
# chain to unlock and nothing to stall on — which is exactly what the 8/18 upward greedy (71
# builds, no answer) did not have.
_DIAG_DOSES = (1, 2, 3)
_DIAG_BANDS = ("early", "main")
# ⚠ THE PER-DAY SWEEP IS BOUNDED AT ONE COURT PER DAY, and that bound is REPORTED, never silent.
# Measured on a lumpy fixture at this HEAD: three courts on one searched day clear a week that
# the sweep at one court does not, and the week-wide answer that IS found costs 20 court-days
# where the day-local one costs 3. Deepening the sweep would take the ladder from 29 builds to
# 69, which is a scope decision and not this build's to take — so the director is TOLD.
_DIAG_SWEEP_DOSE = 1


def _diag_day_label(day):
    """`2026-01-27` -> `Tue Jan 27`. The draw sheets' own register (`draw_sheets._slot`), built on
    this module's shipped `_short_day`, so a refusal names a day the way every other page the
    director holds names it."""
    try:
        dt = datetime.datetime.strptime(day, "%Y-%m-%d")
    except (TypeError, ValueError):
        return str(day)
    return f"{('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')[dt.weekday()]} {_short_day(day)}"


def _diag_band_words(band):
    """The hour in the director's own words, and never finer than the contract can express.

    ⚠ THE VOCABULARY IS BOUND (§0.12). Capacity is three bands per venue-day and nothing finer
    exists in `td-resource-slate/v1`. "One more at Mission Hills BEFORE 11:00 on Tuesday" is
    expressible AND re-runnable; "three more between 11:00 and 14:00" — the OI-56 row's own
    example — is neither, and saying it would be a promise the tool cannot keep or re-check. A
    finer window is a contract change and an engine capacity change, and it is out of this build.
    """
    return {"early": "before the courts open up",
            "main": "once the courts open up",
            "lit": "after the lights come on"}[band]


def _diag_when(band, hour):
    """The band as the director hears it — HIS boundary hour where the day cells agree on one,
    the band's own words where they do not.

    ANSWER-1 decision 2 as ruled: "at what time(s)" ships as the day's bands with his own
    boundary hours, which is the finest unit the capacity vocabulary can express AND re-run.
    Lifted out of the answer sentence, which has always read this way, so the out-of-room
    sentence cannot drift from it."""
    if not hour:
        return _diag_band_words(band)
    return (f"before {hour}" if band == "early"
            else f"from {hour}" if band == "main"
            else f"after {hour}")


def _diag_band_hour(slate, club, band, days=None):
    """The band boundary in the DIRECTOR'S OWN NUMBERS, read off his slate — never the tool's.

    Returns None when the day cells disagree, in which case the answer falls back to the band's
    words alone rather than quoting an hour that is only true of some days."""
    hours = set()
    for loc in slate.get("locations") or []:
        if loc["id"] != club:
            continue
        if band == "lit":
            return loc.get("lights_on")
        for day, cell in (loc.get("available") or {}).items():
            if days is not None and day not in days:
                continue
            if band == "early":
                hours.add(cell.get("morning_until"))
            else:
                hours.add(cell.get("morning_until") or cell.get("start"))
    hours.discard(None)
    return hours.pop() if len(hours) == 1 else None


def _diag_main_site(slate):
    """The main site is a POSITION in the director's own list — `locations[0]` — and never the
    literal string `MHCC` (VENUE-1 / rule 43: rank IS the array order, no key)."""
    locs = slate.get("locations") or []
    if not locs:
        return None, None
    return locs[0]["id"], (locs[0].get("name") or locs[0]["id"])


def _diag_stage1(result, slate, cfg):
    """STAGE 1 — read off the failure what is genuinely there, per reason raised.

    ⚠ THE TWO HALVES HAVE OPPOSITE DATA SITUATIONS, and pretending they are one problem is how
    this goes wrong:

    · FINALS / L1 MIXED. `hard_venue_breaches` already carries `rule` · `event` · `id` · `round` ·
      `day` · `start` · `location` · `main_site` and both display names. The club, the days, the
      hour and the divisions are all READ OFF the failure. The sentence today throws all of it
      away and prints a count.

    · UNPLACED. Bare match ids. Division and round are recovered from the id (`E{n}-R{r}-M{m}`
      indexes `cfg.events`, minted at `scheduler_multi:727`) and the planned day from
      `cfg.assigned_days` — and that day is then treated as EVIDENCE, NEVER AS THE ANSWER.

      ⚠ Measured at this HEAD, and it contradicts the locked approach's own 8/18 wording: on a
      lumpy fixture the stuck matches are planned for Jan 30 and Jan 31, every dose on those two
      days fails, and the day that clears is Jan 29 — a day no failing match sits on. The greedy
      engine re-flows: a court given on Thursday frees Friday indirectly, by moving what was
      occupying Friday. So for this half the day is SEARCHED, one build per open day, bounded.

    ⚠ `unplaced` is appended at `scheduler_multi.py:1266` as a bare `m.mid`, at a site that holds
    `m.event`, `m.rnd` and the planned day. Widening that row is the obvious temptation and it is
    DELIBERATELY NOT TAKEN: the recovery above needs nothing new, and a placement-loop record is
    engine surface this build has no reason to touch.
    """
    site, site_name = _diag_main_site(slate)
    reasons = []
    sentences = check_week(result)

    breaches = (result or {}).get("hard_venue_breaches") or []
    for rule, one, many in (("main_site_finals", "final", "finals"),
                            ("main_site_l1_mixed", "Level 1 Mixed match", "Level 1 Mixed matches")):
        rows = [b for b in breaches if b["rule"] == rule]
        if not rows:
            continue
        pushed_to = sorted({b.get("location_name") or b.get("location") for b in rows})
        reasons.append({
            "kind": rule,
            "sentence": next((s for s in sentences if f" {many} " in s or f" {one} " in s), ""),
            "club": rows[0].get("main_site") or site,
            "club_name": rows[0].get("main_site_name") or site_name,
            "evidence_days": sorted({b["day"] for b in rows}),
            "divisions": sorted({b["event"] for b in rows}),
            # OI-B12 (decision 1, ruled IN): the count and the venue are ALREADY in the payload.
            # The refusal NAMES both sides of the trade and never takes it — R13 is untouched.
            "alternative": {"count": len(rows), "noun": one if len(rows) == 1 else many,
                            "venues": pushed_to},
            "answer": None, "tried": [], "not_tried": [], "out_of_room": None,
            "beyond_owned": None})

    unplaced = (result or {}).get("unplaced") or []
    if unplaced:
        events = list(getattr(cfg, "events", []) or [])
        amap = getattr(cfg, "assigned_days", None) or {}
        divisions, days = set(), set()
        unreadable = 0
        for mid in unplaced:
            try:
                idx = int(str(mid).split("-")[0][1:]) - 1
                name = events[idx].name
            except (ValueError, IndexError):
                unreadable += 1
                continue
            divisions.add(name)
            # A round-robin id is `{prefix}-M{ri}-{a}v{b}` and carries no round, so it has no
            # planned day to recover. The division still counts as evidence.
            if "-R" in str(mid):
                try:
                    rnd = int(str(mid).split("-R")[1].split("-M")[0])
                except ValueError:
                    continue
                day = amap.get((name, rnd))
                if day:
                    days.add(day)
        reasons.append({
            "kind": "unplaced",
            "sentence": next((s for s in sentences if "no place to play" in s), ""),
            # The candidate club is the one the venue rules point at — in practice the main site
            # whenever a venue rule is what stuck them. Every other club is recorded as untried
            # rather than silently ruled out.
            "club": site, "club_name": site_name,
            "evidence_days": sorted(days),
            "divisions": sorted(divisions),
            "alternative": None,
            "answer": None, "tried": [], "not_tried": [], "out_of_room": None,
            "beyond_owned": None,
            "_unreadable": unreadable})

    yields = len(band_yields_of(result))
    if yields > BAND_YIELD_CEILING:
        # The early-start ceiling is a CLOCK rule, not a court shortage: the matches are placed
        # and the courts exist. Naming a court number against it would be inventing an answer, so
        # it is diagnosed as having none and says why.
        reasons.append({
            "kind": "band_yields",
            "sentence": next((s for s in sentences if "early start promised" in s), ""),
            "club": None, "club_name": None, "evidence_days": [], "divisions": [],
            "alternative": None, "answer": None, "tried": [],
            "not_tried": ["more courts were not tried against the early-start promise: those "
                          "matches already have a court, so this is a clock question and not a "
                          "court one"],
            "out_of_room": None, "beyond_owned": None})
    return reasons


# S-4 §3.1.4 — EVERY SENTENCE NAMES ITS FRAME, and the two frames are opposite claims about the
# same week. A diagnosis taken at the clubs' ceilings describes a booking the director has not
# made; one taken at his booked counts describes the week he is holding. A figure wearing the
# wrong frame is a booking he never made, printed at him.
_FRAME_WORDS = {"as-booked": "As you booked it",
                "at-ceilings": "At everything your clubs own"}


def _diag_bottleneck(result, slate, reasons, frame="as-booked"):
    """STAGE 1.5 — WHERE THE WEEK BROKE. Counts and configurations, and ZERO extra builds.

    S-4 §3.2. The refusal already says what failed; it has never said WHERE. This reads the
    failed build's own schedule — arithmetic, 0.01 s — and, for the club and day each reason
    names, reports per band what is open, the peak simultaneous use, and the contiguous window
    where the two are equal, in the day's own three bands with the DIRECTOR'S boundary hours.

    ⚠ IT IS EVIDENCE AND NEVER A PRESCRIPTION, and that is a measured position rather than a
    cautious one. The one move the jam most obviously suggests was driven on the refusing week
    and does nothing: the full court count from 08:00 on the jam day alone changes nothing, the
    morning step-up raised on that day changes nothing, and the full count from 08:00 on EVERY
    day places every match and leaves the refusal standing. The greedy engine re-flows — a court
    given on Thursday frees Friday by moving what was occupying Friday — so the day the week
    broke on is not the day to buy courts on. The words here say where it broke. What to buy is
    the ladder's answer, one rung at a time, each confirmed by a real build.

    ⚠ ITS HOME IS HERE, INSIDE THE DIAGNOSTIC, and that is what puts ONE bottleneck voice on
    every refusal surface in both seasons: September's booking step and January's refusal report
    render the same record, because both read `shortfall`.

    LANG-1 §7 binds every sentence: the division, the club, the day and the hour are named and a
    match id never is (rule 2); every number carries its denominator (rule 5); the tool never
    names its own parts (rule 3) nor speaks as "we" (rule 7)."""
    bands = _cb_bands(slate or {})
    names = {loc["id"]: (loc.get("name") or loc["id"])
             for loc in (slate or {}).get("locations") or []}
    blocks: dict = {}
    for m in result.get("schedule") or []:
        club, day = m.get("location"), m.get("day")
        s, e = _hhmm_min(m.get("start")), _hhmm_min(m.get("end"))
        if club and day and s is not None:
            blocks.setdefault((club, day), []).append((s, e if e is not None else s + 90))

    sites, not_shown, seen = [], [], set()
    for reason in reasons or []:
        club = reason.get("club")
        if not club:
            continue
        days = list(reason.get("evidence_days") or [])
        if not days:
            not_shown.append(
                "the matches with nowhere to play carry no planned day here, so no day is "
                "named for them" if reason.get("kind") == "unplaced" else
                "this reason names no day, so none is shown for it")
            continue
        for day in days:
            if (club, day) in seen:
                continue
            seen.add((club, day))
            rows = []
            for band, lo, hi, cap in bands.get((club, day), []):
                peak, full = _cb_occupancy(blocks.get((club, day)) or [], lo, hi)
                # THE LONGEST CONTIGUOUS FULL STRETCH, never the envelope from the first to the
                # last. A club full 08:00-09:00 and again 13:00-14:00 was not full for six hours,
                # and printing it as though it were would be the wrong kind of wrong on the one
                # page a director reads under pressure.
                run = max(full, key=lambda ab: ab[1] - ab[0]) if full and peak >= cap else None
                rows.append({
                    "band": band, "band_words": _diag_band_words(band),
                    "hour": _diag_band_hour(slate, club, band, [day]),
                    "open": cap, "peak": peak,
                    "full_from": _min_hhmm(run[0]) if run else None,
                    "full_until": _min_hhmm(run[1]) if run else None,
                    "full_minutes": (run[1] - run[0]) if run else 0})
            if not rows:
                continue
            sites.append({"club": club, "club_name": names.get(club, club), "day": day,
                          "day_label": _diag_day_label(day), "reason": reason.get("kind"),
                          "divisions": list(reason.get("divisions") or []), "bands": rows})

    lead = _FRAME_WORDS.get(frame, _FRAME_WORDS["as-booked"])
    lines = []
    for site in sites:
        tight = [b for b in site["bands"] if b["open"] and b["peak"] >= b["open"]]
        if tight:
            where = "; ".join(
                f"{b['peak']} of its {b['open']} courts are in use from {b['full_from']} to "
                f"{b['full_until']} {b['band_words']}" for b in tight)
        else:
            worst = max(site["bands"], key=lambda b: (b["peak"], -b["open"]))
            where = (f"{worst['peak']} of its {worst['open']} courts are in use at the busiest "
                     f"point {worst['band_words']}")
        divs = site["divisions"][:3]
        tail = ""
        if divs:
            more = len(site["divisions"]) - len(divs)
            tail = (f" What is held up there: {', '.join(divs)}"
                    + (f" and {more} more" if more > 0 else "") + ".")
        lines.append(f"  · {lead}, {site['day_label']} at {site['club_name']} is where this "
                     f"week runs short: {where}.{tail}")
    return {"frame": frame, "frame_words": lead, "sites": sites, "not_shown": not_shown,
            "sentences": lines}


def _diag_rungs(reason, slate, sweep_days):
    """STAGE 2's ladder for one reason, cheapest first. Each rung is a configuration to BUILD.

    The order is the director's own money, ascending: the days the failure already names, in the
    hour that is cheapest, before anything week-wide is proposed. Measured at this HEAD: naming
    the hour halves the courts (one court before 11:00 clears a week that needs two after it),
    and naming the days saves twenty court-days for the same result.
    """
    club = reason["club"]
    named = reason["evidence_days"]
    rungs = []
    if named:
        for band in _DIAG_BANDS:
            for n in _DIAG_DOSES:
                rungs.append({"club": club, "days": list(named), "band": band, "courts": n,
                              "scope": "named"})
    # THE SEARCH. One build per open day — necessary for the unplaced half, because the day the
    # failure names is not the day that needs courts.
    for day in sweep_days:
        for band in _DIAG_BANDS:
            rungs.append({"club": club, "days": [day], "band": band,
                          "courts": _DIAG_SWEEP_DOSE, "scope": "searched"})
    # The week-wide answer, which at depth is sometimes the only honest one.
    for n in _DIAG_DOSES:
        rungs.append({"club": club, "days": None, "band": "main", "courts": n, "scope": "week"})
    return rungs


# ANSWER-1 decision 1 (Operator, 2026-08-28, option 1) — HOW FAR PAST ITS OWN COURTS THE LADDER
# GOES once every in-bounds configuration is exhausted. Four, and the bound is REPORTED exactly
# as the day sweep's one-court bound is: a director told "not within four courts of what this
# club owns" knows the answer is a different club or a different week, and one told nothing at
# all knows only that the tool stopped.
_DIAG_BEYOND_MAX = 4


def _diag_beyond_edits(base, club, band, days, target):
    """The per-day edits that put exactly `target` courts in `band` on each of `days`.

    ⚠ PER DAY, NEVER ONE UNIFORM DELTA. `_court_slate` adds a delta to what a cell already
    carries, and the days in scope do not carry the same counts — one delta across them would
    leave the quieter days BELOW the figure being reported, which is the interpolation OI-56
    forbids. Every day is raised to the figure itself, so the configuration built is the
    configuration named.

    ⚠ A CLUB THAT OWNS `target` COURTS HAS THEM ALL DAY. So an early-band figure raises the main
    band with it wherever the main band sits below it: a morning count above the day's own court
    count is not a booking anyone could make, and building one would price a week that cannot
    exist."""
    edits = []
    for loc in base["locations"]:
        if loc["id"] != club:
            continue
        for day, cell in (loc.get("available") or {}).items():
            if day not in days:
                continue
            if band == "early":
                # A day with no morning step-up has no early band to widen — the same skip
                # `_court_slate` makes, made here so the edit list says what will happen.
                if "morning_courts" in cell:
                    edits.append((club, day, "early",
                                  target - (cell.get("morning_courts") or 0)))
                if (cell.get("courts") or 0) < target:
                    edits.append((club, day, "main", target - (cell.get("courts") or 0)))
            else:
                edits.append((club, day, "main", target - (cell.get("courts") or 0)))
    return edits


def _diag_beyond_owned(reason, probe, base, club, owns, rung, out, budget_builds):
    """ANSWER-1 A3 — the ladder that continues PAST what the club owns, and the ONE new
    computation in this build.

    Today's search stops at the ceiling, and the director is told he is out of room with no
    figure at all: not how many courts, not on which day, not at what time, not for which
    division. He cannot buy a court his club does not have — but the SIZE of the gap is what
    decides whether the answer is a neighbouring club or a different week, and that is a figure
    only a build can give him.

    ⚠ IT IS A HYPOTHETICAL AND THE SENTENCE SAYS SO. Nothing here is a booking to make; the
    report says "you cannot book that" in the same breath as the number.

    ⚠ OI-56'S PROPERTIES CARRY OVER VERBATIM, because the supply is the same non-monotone supply:
    every figure is BUILT at exactly that figure — no interpolation, no "at least N" — and graded
    on the WHOLE refusal (`holds`, which is `check_week` empty AND no hard breach), never on the
    one reason the ladder was entered for.

    Returns the answer, or None with the bound recorded on the reason's `not_tried`.
    """
    band = rung["band"]
    open_days = sorted({day for loc in base["locations"] if loc["id"] == club
                        for day in (loc.get("available") or {})})
    if not open_days:
        return None
    named = [d for d in (rung["days"] or []) if d in open_days]

    # ⚠ THE IN-BOUNDS LADDER'S OWN SCOPE ORDER, CONTINUED — and it is NOT optional. Measured on
    # the flat-at-ceiling bench at 0.52: the days this reason names carry no answer at any of the
    # four figures, and ONE court beyond what the club owns, on every day of the week, clears
    # the whole refusal. A ladder that stopped at the broken rung's own days would have reported
    # "no number of courts" over an answer that exists — which is the defect this build is
    # closing, rebuilt one level down. Named days first at every figure, then the week, exactly
    # as `_diag_rungs` exhausts its named rungs before it proposes a week-wide booking.
    #
    # ⚠ `days: None` MEANS THE WHOLE WEEK, the same way the in-bounds `answer` says it. No new
    # vocabulary, and the renderer's existing "on every day of the week" reads it already.
    # ⚠ `builds` IS REAL BUILDS, NEVER RUNGS CLIMBED. `court_probe` caches, and the reasons of one
    # refusal share a club — so the three reasons of the flat-at-ceiling bench each climb five
    # rungs and the week-wide rung is built ONCE for all three. Reporting five apiece would
    # inflate this build's own cost by more than half, on the one figure that exists to state it.
    spent = probe.used
    for scope_days in ([named] if named else []) + [None]:
        for k in range(1, _DIAG_BEYOND_MAX + 1):
            edits = _diag_beyond_edits(base, club, band, scope_days or open_days, owns + k)
            if not edits:
                continue
            try:
                r = probe.at(edits)
            except _CBExhausted:
                out["partial"] = True
                reason["not_tried"].append(
                    f"the search stopped at its build budget of {budget_builds} before it could "
                    f"say how many courts beyond the {owns} {reason['club_name']} owns this "
                    f"week needs")
                return None
            if r.get("holds"):
                if scope_days is None:
                    _diag_beyond_sweep_note(reason, club_name=reason["club_name"], owns=owns)
                return {"courts": k, "days": list(scope_days) if scope_days else None,
                        "band": band, "hour": _diag_band_hour(base, club, band, scope_days),
                        "divisions": list(reason["divisions"]),
                        "builds": probe.used - spent}
    # NOTHING WITHIN FOUR. `null`, and the BOUND is reported — the day sweep's one-court bound
    # verbatim ("a silent cap reads as 'we checked everything' when we did not").
    #
    # ⚠ WHAT GOES IN `not_tried` IS THE CAP, NEVER "nothing was found". OI-56's own rule, kept:
    # the sentence already says the week did not fit at any of them, and saying it twice is the
    # padding LANG-1 rule 6 deletes rather than shortens. What ADDS information is that the
    # ladder stopped at four and a fifth court was never built.
    reason["not_tried"].append(
        f"more than {_DIAG_BEYOND_MAX} courts beyond the {owns} {reason['club_name']} owns was "
        f"not tried")
    _diag_beyond_sweep_note(reason, club_name=reason["club_name"], owns=owns)
    return None


def _diag_beyond_sweep_note(reason, *, club_name, owns):
    """The day sweep is NOT run above the ceiling, and the director is told so.

    The in-bounds ladder searches one day at a time because the day a failure names is not the
    day that needs courts. Above the ceiling that sweep would cost four builds per open day per
    reason for a booking he cannot make anyway, so it is not run — and, exactly as the sweep's
    own one-court bound is reported rather than left silent, that is said. The note is worth
    saying only where a day-local answer was NOT found; where one was, no cheaper scope exists."""
    reason["not_tried"].append(
        f"one day at a time was not tried above the {owns} courts {club_name} owns")


def diagnose_shortfall(result, slate=None, *, cfg=None, constraints_doc=None, levels=("1", "2"),
                       overrides=None, finals_map=None, ceilings=None, budget_builds=200,
                       probe=None, frame="as-booked"):
    """What to add, in courts · club · days · hours — every number confirmed by a real build.

    Input: the refused `result` and the slate that produced it. Output: COUNTS AND CONFIGURATIONS
    ONLY — never a schedule (BUDGET-1 §3.4's context rule).

    Returns `{"reasons": [...], "builds": {...}, "not_tried": [...], "partial": bool}`. Each
    reason carries what was read off the failure, the answer if one was found and confirmed, what
    was tried, and what was not.

    ⚠ GRADING IS ON THE WHOLE REFUSAL — `check_week` empty — never on the one reason the rung was
    chosen to fix. A court that clears every stuck match and takes a third final off the main
    site is not an answer, and at this HEAD that is a real configuration and not a hypothetical.
    """
    base = slate if slate is not None else wwtc_slate()
    doc = constraints_doc or default_constraints()
    ceilings = dict(ceilings if ceilings is not None else RS.ceilings_from_slate(base))
    out = {"reasons": [], "builds": {"used": 0, "budget": budget_builds},
           "not_tried": [], "partial": False, "bottleneck": None}

    reasons = _diag_stage1(result, base, cfg) if check_week(result) else []
    out["reasons"] = reasons
    if not reasons:
        return out

    # ---- STAGE 1.5 · WHERE IT BROKE (S-4 §3.2). Arithmetic over the failed build's own
    # ---- schedule, before a single rung is priced, so it survives a spent build budget: the
    # ---- one thing a director whose search ran out of room still gets is the jam itself.
    out["bottleneck"] = _diag_bottleneck(result, base, reasons, frame=frame)

    # ONE machine across every reason, so the two halves of a refusal share a cache instead of
    # paying twice for the same tournament — which they do, because they probe the same club.
    probe = probe or court_probe(base, doc, levels=levels, budget=budget_builds,
                                 overrides=overrides, finals_map=finals_map)
    sweep_days = list(base.get("dates") or [])

    for reason in reasons:
        if not reason["club"]:
            continue
        club, owns = reason["club"], ceilings.get(reason["club"])

        def _booked(band, days):
            """What the club already has open, in this band, on the days the rung edits.

            0 when the club is not open on any of them — a venue with no cell for a day has no
            capacity there to raise, so there is nothing to weigh against its ceiling."""
            key = "morning_courts" if band == "early" else "courts"
            return max((cell.get(key) or 0
                        for loc in base["locations"] if loc["id"] == club
                        for day, cell in loc["available"].items()
                        if days is None or day in days), default=0)

        # A club that is not open on a day cannot be given courts on it: the edit would apply to
        # nothing and the build would be a byte-identical copy of one already run. Measured on
        # the committed slate, where Omni is closed on two of the ten days — the sweep spent two
        # builds proving that a slate it had not changed still refused.
        open_days = {day for loc in base["locations"] if loc["id"] == club
                     for day in (loc.get("available") or {})}
        club_sweep = [d for d in sweep_days if d in open_days]
        if len(club_sweep) < len(sweep_days):
            reason["not_tried"].append(
                f"{reason['club_name']} is not open on "
                f"{len(sweep_days) - len(club_sweep)} of the week's {len(sweep_days)} days, so "
                f"courts there were not tried on those days")

        for rung in _diag_rungs(reason, base, club_sweep):
            # R5, FROM THE OTHER DIRECTION. A prescription the club cannot supply is NOT a court
            # number — it is "you're out of room here", and the director acts on the two
            # differently. Checked BEFORE the build, so a number he cannot buy is never probed
            # and never printed.
            #
            # ⚠ BOTH per-day bands are checked against what the club OWNS, because neither can
            # exceed it — but they are checked SEPARATELY and that distinction is real money:
            # opening a court earlier in the day is not buying a court. A club with 17 courts and
            # only 9 open before 11:00 is not out of room for an early-band answer; it is out of
            # room only when the answer asks for an 18th court to exist.
            here = _booked(rung["band"], rung["days"])
            if owns is not None and here + rung["courts"] > owns:
                reason["out_of_room"] = {"club": club, "club_name": reason["club_name"],
                                         "owns": owns, "booked": here, "band": rung["band"]}
                reason["not_tried"].append(
                    f"{club} already has {here} of the {owns} courts it owns in use, so more "
                    f"courts there were not tried")
                # ANSWER-1 A3 — AND THE LADDER CARRIES ON PAST THE CEILING, so the one case the
                # shipped report answered in no figures at all now answers in four. The in-bounds
                # search still stops exactly where it stopped before: this adds a bounded
                # hypothetical after it and changes nothing it had already tried.
                reason["beyond_owned"] = _diag_beyond_owned(
                    reason, probe, base, club, owns, rung, out, budget_builds)
                break
            try:
                r = probe.at([(club, d, rung["band"], rung["courts"])
                              for d in (rung["days"] or [None])])
            except _CBExhausted:
                out["partial"] = True
                reason["not_tried"].append(
                    f"the search stopped at its build budget of {budget_builds}; everything "
                    f"below this point is untried")
                break
            row = dict(rung)
            row["unplaced"] = r.get("unplaced")
            row["hard_breaches"] = r.get("hard_breaches")
            reason["tried"].append(row)
            # THE WHOLE REFUSAL IS THE GRADE.
            if r.get("holds"):
                reason["answer"] = dict(rung)
                reason["answer"]["club_name"] = reason["club_name"]
                reason["answer"]["hour"] = _diag_band_hour(base, club, rung["band"], rung["days"])
                break

        # STAGE 3 — SAY WHAT WAS NOT TRIED. `court_budget`'s discipline verbatim: a silent cap
        # reads as "we checked everything" when we did not.
        # ⚠ "Nothing was found" is NOT recorded here as a `not_tried` line: it is what the
        # sentence itself says, and repeating it in the same breath is the padding LANG-1 rule 6
        # deletes rather than shortens. What belongs here is only what ADDS information — the
        # bounds the search stopped at, and the clubs it never probed.
        # The sweep's dose bound is only worth saying when it MATTERS — when the search came back
        # with nothing, or with a week-wide answer that more courts on one day might have beaten.
        # If a single day already answered at one court, no cheaper answer exists and repeating
        # the bound would be noise on a page the director is reading under pressure.
        if (any(t["scope"] == "searched" for t in reason["tried"])
                and (reason["answer"] is None or reason["answer"]["scope"] == "week")):
            reason["not_tried"].append(
                f"one day at a time was tried at {_DIAG_SWEEP_DOSE} extra court only — more "
                f"courts on a single day may fix this week and were not tried")
        others = [loc.get("name") or loc["id"] for loc in base["locations"]
                  if loc["id"] != reason["club"]]
        if others:
            reason["not_tried"].append(
                f"courts at {' and '.join(others)} were not tried against this")

    out["builds"]["used"] = probe.used
    if out["partial"]:
        out["not_tried"].append(
            f"the search stopped at its build budget of {budget_builds}")
    return out


def _diag_out_of_room(reason, oor):
    """ANSWER-1 A3 — the out-of-room answer, in the four figures the September run owes him.

    The requirement (Operator, 2026-08-28): where there is a court deficit the run says HOW MANY
    courts, on WHAT DAYS, at WHAT TIMES, for WHAT DIVISIONS. Every other branch of this report
    already carried three of the four; this one carried none, and it is the branch a director
    whose clubs are all at their Max Courts figure lands in.

    ⚠ THE FIGURES HERE ARE A HYPOTHETICAL AND THE SENTENCE SAYS SO IN THE SAME BREATH. The club
    does not own those courts. What the number buys him is the SIZE of the gap: one court short
    is a phone call to a neighbouring club, four is a different week.

    ⚠ AND THERE IS NO "another club" CLAUSE ON A MAIN-SITE-BOUND REASON. Rules 38/39/40 put every
    final and every Level 1 Mixed match at the main site and R13 made that yield to nothing, so
    telling a director that the answer might be at another club is FALSE for exactly the match
    that is blocking him.

    Ordered by LANG-1 rule 4 — what happened, what it costs, the way forward — and the two ways
    forward are named, never ranked and never chosen for him.
    """
    club = oor["club_name"]
    beyond = reason.get("beyond_owned")
    main_site_bound = str(reason.get("kind") or "").startswith("main_site")
    said = [f"You are out of room at {club}: {oor['booked']} of its {oor['owns']} courts are "
            f"already in use {_diag_band_words(oor['band'])}."]

    # ⚠ THE FIGURE'S DAYS ARE THE FIGURE'S OWN, AND `None` MEANS THE WHOLE WEEK. Falling back to
    # the reason's evidence days when the ladder answered week-wide would print a booking that
    # was never built — three named days in place of ten.
    days = beyond["days"] if beyond else (reason["evidence_days"] or None)
    when = _diag_when((beyond or {}).get("band") or oor["band"], (beyond or {}).get("hour"))
    where = (f"on {_and_list([_diag_day_label(d) for d in days])}" if days
             else "on every day of the week")
    divisions = _name_some(reason["divisions"])
    # ⚠ THE DIVISION LIST IS COMMA-SEPARATED, so the clause carrying it is bracketed by dashes.
    # Run on with a comma and "for Men's 60 & over singles, Women's 65 & over doubles, and the
    # week did not fit" reads as a third division.
    for_whom = f", for {divisions}" if divisions else ""
    if beyond:
        n = beyond["courts"]
        said.append(
            f"It would take {n} more court{'s' if n != 1 else ''} than {club} owns — {when}, "
            f"{where}{for_whom} — and you cannot book courts a club does not have.")
    else:
        said.append(
            f"Even {_DIAG_BEYOND_MAX} more courts than the {oor['owns']} it owns — {when}, "
            f"{where}{for_whom} — did not make this week fit.")

    # THE DAY LEVER HE ACTUALLY HAS is the finals map: a division's finals day sets its whole
    # ladder, so it is the finals day that is named whichever reason was raised — but a reason
    # holding one division names THAT division, and a reason holding several never pretends the
    # tool knows which of them to move.
    # ⚠ AND THE MOVE IS AGAINST THE DAYS THE FAILURE NAMES, NEVER THE DAYS THE COURTS WOULD GO
    # ON. OI-56 measured those apart and they stay apart here: a court given on Thursday frees
    # Friday by re-flowing what sat on Friday, but the final he can move is the one that is ON
    # the day that broke.
    only = reason["divisions"][0] if len(reason["divisions"]) == 1 else None
    hit = reason["evidence_days"] or (days or [])
    off = _and_list([_diag_day_label(d) for d in hit]) if hit else "the day it breaks on"
    move = (f"move the {only} final off {off}" if only
            else f"move one of those divisions' finals off {off}")
    gives = "that day" if len(hit) <= 1 else "on those days"
    said.append(f"Two ways forward: {move} and check the week again, or change what {club} "
                f"gives you {gives}.")
    if not main_site_bound:
        said.append("Those matches can also play at another club, or in another week.")
    return said


def _diag_sentences(diag):
    """STAGE 2's answers as the director's own sentences — one line per reason diagnosed.

    LANG-1 §7 binds every line here: the day is named the way the draw sheets name it, the hour
    in the day's own three bands with HIS boundary numbers, the club by its full name, and the
    tool never names its own parts (rule 3) nor speaks as "we" (rule 7).
    """
    # ONE LINE PER REASON DIAGNOSED — but two reasons that reach the SAME answer say it once.
    # Both halves of a refusal probe the same club, so they routinely land on the same sentence,
    # and printing "you are out of room at Mission Hills" twice tells the director nothing the
    # first line did not (LANG-1 rule 6: a fact and a consequence, nothing else). Order is the
    # order the reasons were raised; only exact repeats collapse.
    lines, seen = [], set()

    def _say(line):
        if line not in seen:
            seen.add(line)
            lines.append(line)

    for reason in diag.get("reasons") or []:
        ans, oor = reason["answer"], reason["out_of_room"]
        if oor:
            # R5's answer, and it is a DIFFERENT answer from a bigger number: the director books
            # courts against one of these and renegotiates the week against the other.
            #
            # ⚠ ANSWER-1 A3 REWRITES THIS LINE, and it is the case the whole build exists for. It
            # used to carry NONE of the four figures the September run owes him — no number, no
            # day, no time, no division — on the one refusal the shipped report could not answer.
            # It now says, in order (LANG-1 rule 4): what happened · what it would take and that
            # he cannot buy it · the two ways forward.
            _say("  · " + " ".join(_diag_out_of_room(reason, oor)))
            continue
        if ans is None:
            tried = len(reason["tried"])
            where = f" at {reason['club_name']}" if reason["club_name"] else ""
            _say(
                f"  · No number of courts{where} fixed this week"
                + (f", across {tried} bookings tried for real." if tried else ".")
                + " " + " ".join(n[0].upper() + n[1:] + "." for n in reason["not_tried"][:2]))
            continue
        courts = f"{ans['courts']} more court" + ("s" if ans["courts"] != 1 else "")
        when = _diag_when(ans["band"], ans["hour"])
        where = (f"on {' and '.join(_diag_day_label(d) for d in ans['days'])}"
                 if ans["days"] else "on every day of the week")
        # ANSWER-1 A1 — THE FOURTH FIGURE. The payload has always carried `divisions` and this
        # sentence has always thrown them away, so a director reading "1 more court at Mission
        # Hills before 11:00 on Tuesday" was never told which tournament the court was for.
        # Rendering only: nothing is computed here that the reason row did not already hold.
        divisions = _name_some(reason["divisions"])
        line = f"  · {courts} at {ans['club_name']} {when}, {where}"
        if divisions:
            line += f", for {divisions}"
        alt = reason["alternative"]
        if alt:
            # OI-B12 — THE TRADE IS NAMED, IT IS NEVER TAKEN. R13 still refuses to publish a
            # week with a final off the main site; this clause only says what the courts buy.
            line += (f" — or {'those ' + str(alt['count']) if alt['count'] != 1 else 'that'} "
                     f"{alt['noun']} play at {' and '.join(alt['venues'])}.")
        else:
            line += " — every match fits."
        _say(line)
    return lines


def format_refusal(exc):
    """The refusal as a REPORT SECTION — plain English, the TD's own vocabulary.

    Engineer recommendation carried at the brief's §6 and taken: a report section first, no
    console change in this build. The console never has to learn a new state to show this."""
    lines = ["This week cannot be scheduled as planned.", ""]
    lines += [f"  · {r}" for r in exc.reasons]
    # S-4 §3.2 — WHERE IT BROKE, first, because it is the only section that costs nothing and
    # the only one that is true whatever the search then finds. ONE VOICE ON BOTH SEASONS'
    # SURFACES: this renderer serves September's booking step and January's build lanes alike,
    # and neither gets a different account of the same jam.
    jam = ((getattr(exc, "shortfall", None) or {}).get("bottleneck") or {}).get("sentences") or []
    if jam:
        lines += ["", "Where the week runs short — read off the week that was just built:"]
        lines += jam
    if exc.remedies:
        lines += ["", "What would fix it — each one tried for real on this week's entries:"]
        for r in exc.remedies:
            if r["clears"]:
                mark, tail = "THIS FIXES IT", "every match fits."
            elif r["clears"] is None:
                mark, tail = "not tried", r["note"].split("— ", 1)[-1]
            elif r["unscheduled"] is None:
                mark, tail = "could not try", r["note"]
            else:
                mark = "not enough"
                tail = (f"still leaves {r['unscheduled']} match"
                        f"{'es' if r['unscheduled'] != 1 else ''} with nowhere to play."
                        if r["unscheduled"] else r["note"])
            lines.append(f"  [{mark}] {r['label']} — {tail}")
        # ANSWER-1 A4 — "TWO OF THEM TOGETHER" NEEDS TWO OF THEM. The sentence printed whenever
        # nothing cleared, however short the list of things actually tried; on the committed 2027
        # seed that is ONE row tried and found not enough beside ONE row that could not be tried
        # at all, and the director was invited to combine a pair that does not exist. It now needs
        # two rows that were built and came back short — below that the single row already says
        # what it says.
        tried_short = [r for r in exc.remedies if r["clears"] is False]
        if not any(r["clears"] for r in exc.remedies) and len(tried_short) >= 2:
            lines += ["", "None of these is enough on their own. Two of them together may be — "
                             "or the entry list is larger than this week of courts can hold."]
    # OI-56 §3.4 — ITS OWN SECTION, under the remedies and never inside them. The list above
    # rearranges supply the club already has; this one says what to BUY, and the director needs
    # both. It runs regardless of whether anything above cleared, because the list above stops at
    # its first success and would otherwise mark this "not tried" exactly when it matters most.
    diag = getattr(exc, "shortfall", None) or {}
    said = _diag_sentences(diag)
    if said:
        lines += ["", "What it would take — each one tried for real on this week's entries:"]
        lines += said
        if diag.get("partial"):
            lines += ["", "This did not finish, so there may be a smaller answer it did not "
                          "reach."]
    return "\n".join(lines)


def _refuse_if_infeasible(result, *, probing, levels, constraints_doc, slate, overrides,
                          finals_map, combined=True, cfg=None):
    """Rung 2, at the one place both build lanes pass through after placement and BEFORE any
    deliverable work. Ahead of `_reconcile` on purpose: a match with nowhere to play makes its
    entrant unreconciled, and being told the reconciliation invariant broke is a worse answer to
    an over-subscribed week than being told the week is over-subscribed."""
    reasons = check_week(result)
    if not reasons:
        return
    # BOTH answers are gated on `probing`, and for the same reason: a probe's own refusal is
    # discarded by its caller, so the builds behind these would be seconds spent to learn
    # nothing. NOMAP-1's grid leans on exactly this — every candidate-day cell builds
    # `_probing=True`, so an infeasible cell still costs ONE build and the diagnostic below never
    # runs inside it. Only the baseline, whose answers ARE the deliverable, pays for them.
    remedies = [] if probing else probe_remedies(
        levels=levels, constraints_doc=constraints_doc, slate=slate, overrides=overrides,
        finals_map=finals_map, combined=combined, refused_result=result)
    shortfall = None if probing else diagnose_shortfall(
        result, slate=slate or wwtc_slate(), cfg=cfg, constraints_doc=constraints_doc,
        levels=levels, overrides=overrides, finals_map=finals_map)
    raise WeekRefused(reasons, result, remedies, shortfall)


def _reconcile(players, events, result, draws=None, ingest_warnings=None):
    """ROSTER-1: reconcile the entry lists against the finished schedule and enforce the one
    invariant this build delivers — **drawn and not scheduled must never happen**.

    A person in a printed draw with no match on the schedule is a hard failure, raised here on
    every run rather than left to be noticed. Its mirror — *entered and not drawn* — is
    information, not a failure: it is the exceptions list, and it is expected to be non-empty
    (121 entries for 106 people on the 2026 field). Today the failure case holds at 0; this makes
    it checkable rather than incidental.

    PREP-1 (2026-08-01) sharpens the rule to **warned-or-fatal, never silent**: `draws` (the
    parsed-draw truth, `wwtc_ingest.draw_truth`) lets the reconciliation see entrants the ingest
    itself dropped. A drop an ingest warning covers becomes the `not_buildable` exceptions bucket
    — degraded input degrades the run loudly instead of killing it (FIX-1 precedent) — while a
    drop NO warning covers joins `drawn_not_scheduled` and raises here, exactly like an engine
    loss."""
    recon = wwtc_ingest.reconcile_entries(players, events, schedule=result.get("schedule"),
                                          draws=draws, ingest_warnings=ingest_warnings)
    missing = recon["drawn_not_scheduled"]
    if missing:
        shown = ", ".join(f"{r['name']} / {r['division']}" for r in missing[:5])
        raise AssertionError(
            f"INVARIANT BROKEN — {len(missing)} entrant(s) are in a printed draw but have no "
            f"match on the schedule: {shown}{' …' if len(missing) > 5 else ''}")
    return recon


def build(level="2", constraints_doc=None, slate=None, overrides=None, assigned_days=None,
          finals_map=None, _probing=False):
    """Run the full pipeline. Returns a dict with players, events, seeds, doc, cfg, result.

    CANON-2: the two-pass lane is the DEFAULT — Pass 1 (master schedule, finals-anchored,
    `finals_map` pins honored) gates placement via R7-2. See `_gate` for the
    `assigned_days` semantics (None=computed / dict=supplied / False=diagnostic legacy)."""
    players = wwtc_ingest.load_players(level=level)
    events, seeds, meta = wwtc_ingest.load_from_finalized_draws(level, overrides=overrides)
    doc = constraints_doc or default_constraints()
    slate_doc = slate or wwtc_slate()
    cfg = C.apply_constraints(config_from_slate(slate_doc, events), doc,
                              roster_meta=wwtc_ingest.roster_meta(players))
    mw, dsrc, lds = _gate(cfg, (level,), slate_doc, assigned_days, finals_map, events=events)
    ml1, ml1_note, ml1_warn = _mixed_level_1(cfg, {level: [e.name for e in events]})   # DIV-1
    result = schedule_multi(cfg)
    _refuse_if_infeasible(result, probing=_probing, levels=(level,),   # CAD-1 rung 2
                          constraints_doc=constraints_doc, slate=slate, overrides=overrides,
                          finals_map=finals_map, combined=False, cfg=cfg)
    result["plan_id"] = _default_plan_id(cfg)                     # EDITBASE-1: see build_combined
    truth, iw = wwtc_ingest.draw_truth([meta])                    # PREP-1: parsed-draw truth
    recon = _reconcile(players, events, result,
                       draws=truth, ingest_warnings=iw)           # ROSTER-1: closed accounting
    non_drawn = wwtc_ingest.non_drawn_entrants(players, events, draws=truth,
                                               ingest_warnings=iw)  # F6: surface, never place
    return {"players": players, "events": events, "seeds": seeds, "doc": doc,
            "cfg": cfg, "result": result, "meta": meta, "non_drawn": non_drawn,
            "reconciliation": recon,
            # DIV-1 / rule 45: the resolved Level-1 Mixed list, the one informational line
            # naming where it came from, and any tick-box resolution warnings. Their own
            # channel on purpose — `master_warnings` is the Pass-1 master's advisory list and
            # a display-control warning is not one of those.
            "mixed_level_1": ml1, "mixed_level_1_note": ml1_note,
            "mixed_level_1_warnings": ml1_warn,
            # REKEY-1: the locked-day shifts, structurally. It rides BESIDE `master_warnings`
            # rather than inside `result` on purpose — it cannot be derived from the result at
            # all (`cfg.assigned_days` holds only the final day per round, no was-days), and no
            # `td-*` schema moves for it (decision 3).
            "master_warnings": mw, "assigned_day_sources": dsrc, "locked_day_shifts": lds}


def build_combined(levels=("1", "2"), constraints_doc=None, slate=None, overrides=None,
                   assigned_days=None, finals_map=None, _probing=False):
    """One-tournament build: L1 (mixed doubles) + L2 (singles/gender doubles) share the SAME courts,
    so their events are merged and scheduled in a SINGLE engine pass against one capacity pool.

    Player identity is the canonical `First Last` name (built from the same TD USTA-ID row in either
    level), so a player entered in both levels is one human to the engine — cross-level rest
    (3h start-to-start) and one-match-per-day-per-event fall out of the existing name-keyed rules.
    No division namespacing: L1's four Mixed divisions never collide with L2's names.
    """
    ov = overrides or {}
    events, seeds, metas = [], {}, {}
    # DIV-1 / rule 45: which draws FILE each division was printed in, recorded here as the loop
    # reads them. This is the whole input the blank-tick-box derivation needs, and taking it
    # here costs nothing — re-deriving it later would mean a second pass over the PDFs.
    names_by_level: dict = {}
    # ROSTER-1: a real union — `dict.update()` replaced the L1 record with the L2 one for the 84
    # people entered at both levels and erased their L1 entries with it. Scalars still resolve
    # last-level-wins, so `roster_meta` (and therefore locality and placement) is unmoved.
    players = wwtc_ingest.load_players_combined(levels)
    for lvl in levels:
        ev, sd, meta = wwtc_ingest.load_from_finalized_draws(lvl, overrides=ov.get(lvl))
        events.extend(ev)
        seeds.update(sd)
        metas[lvl] = meta
        names_by_level[lvl] = [e.name for e in ev]
    names = [e.name for e in events]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise ValueError(f"division-name collision across levels: {dupes}")
    doc = constraints_doc or default_constraints()
    slate_doc = slate or wwtc_slate()
    cfg = C.apply_constraints(config_from_slate(slate_doc, events), doc,
                              roster_meta=wwtc_ingest.roster_meta(players))
    mw, dsrc, lds = _gate(cfg, levels, slate_doc, assigned_days, finals_map,
                          events=events)                          # CANON-2 two-pass
    ml1, ml1_note, ml1_warn = _mixed_level_1(cfg, names_by_level)   # DIV-1 / rule 45
    # VENUE-1 (2026-08-05): rules 40 and 31 are written about LEVEL-1 MIXED, so the answer rule 45
    # already resolves above is handed to placement — as DATA, a plain list of division names on
    # the config. `scheduler_multi` still imports neither `division_order` nor this module, so
    # DIV-1's hard guard (the import direction, asserted in `tests/div1_order.py` part A) is
    # untouched. It is set AFTER `_gate` for the same reason DIV-1 resolves it there: the day map
    # must not be able to read it.
    cfg.venue_l1_mixed = set(ml1)
    result = schedule_multi(cfg)
    # S-4 §3.7 — THE RESOLVED LEVEL 1 MIXED LIST RIDES THE RESULT, STAMPED BEFORE THE REFUSAL
    # GATE, and the position is the whole fix. `CourtProbe.at` catches `WeekRefused` and emptied
    # the list under a comment saying the catch "cannot happen under `_probing`" — FALSE, and
    # measured: `_refuse_if_infeasible` raises regardless of `probing`, so every refused probe
    # reported `late_l1_mixed: 0` where the true count on that same schedule was not 0 (§0.18 —
    # driven at 65% on the committed slate, the probe said 0 against a true 1).
    #
    # `WeekRefused` carries the result, so a list stamped BEFORE the gate rides the exception and
    # the refused path can read the real answer instead of inventing an empty one. Stamped after
    # the gate it would be invisible to exactly the path that needs it. Which divisions are Level
    # 1 Mixed is rule 45's answer about the FIELD — it has nothing to do with court supply, so
    # there is no case in which a refusal makes it unknowable.
    #
    # An engine-result key and internal: no `td-*` contract moves (§3.10).
    result["mixed_level_1"] = list(ml1)
    _refuse_if_infeasible(result, probing=_probing, levels=tuple(levels),   # CAD-1 rung 2
                          constraints_doc=constraints_doc, slate=slate, overrides=overrides,
                          finals_map=finals_map, cfg=cfg)
    # EDITBASE-1 (2026-08-08): the BUILD LANE stamps the base result with the id of the build
    # that produced it, so `editor_plan` can read the id off the same object the board comes
    # from and never has to be told it. `apply_schedule_edits` already stamps every EDITED
    # result the same way, which closes the other half: whichever result a console is generated
    # from, it is stamped, and an unstamped console is therefore a real signal rather than an
    # oversight. Computed by the ONE definition (`scheduler_flow._default_plan_id`) that the
    # engine itself checks against — a second derivation of an id whose whole job is that two
    # sides agree would be a way for them to disagree.
    result["plan_id"] = _default_plan_id(cfg)
    truth, iw = wwtc_ingest.draw_truth([metas[lvl] for lvl in levels])  # PREP-1
    recon = _reconcile(players, events, result,
                       draws=truth, ingest_warnings=iw)           # ROSTER-1: closed accounting
    non_drawn = wwtc_ingest.non_drawn_entrants(players, events, draws=truth,
                                               ingest_warnings=iw)  # F6: surface, never place
    return {"players": players, "events": events, "seeds": seeds, "doc": doc,
            "cfg": cfg, "result": result, "meta": metas, "levels": list(levels),
            "non_drawn": non_drawn, "reconciliation": recon,
            "mixed_level_1": ml1, "mixed_level_1_note": ml1_note,   # DIV-1 / rule 45
            "mixed_level_1_warnings": ml1_warn,
            # REKEY-1: see `build` — structural locked-day shifts, beside the warning list.
            "master_warnings": mw, "assigned_day_sources": dsrc, "locked_day_shifts": lds}


# =============================================================================================
# BUDGET-1 (Operator rulings R1-R19, 2026-08-22) — THE COURT BUDGET.
#
# September's question is not "can this week be played?" — the tool has answered that since
# CAD-1. It is "WHAT DO I NEED TO BOOK?", and until this build the tool had no answer at all.
#
# WHY THIS SEARCH TERMINATES AND `probe_remedies` DOES NOT SCALE. `probe_remedies` searches
# UPWARD from a week that is already broken: every step is a guess at what might unlock a chain,
# and the 8/18 research spent 71 builds that way without reaching an answer. This search runs
# DOWNWARD and NEVER LEAVES WORKING TERRITORY. It starts from a slate that plays the week, then
# asks one local question at a time — *is this court load-bearing?* — with the week feasible at
# every step. There is no chain to unlock and nothing to stall on, and the worst case is bounded
# by the courts on the slate rather than by the size of a search space.
#
# CONTEXT, NOT CLOCK, IS THE BINDING COST (§3.4, risk R-B5). Wall-clock in September is nothing —
# a build is about two seconds. The run session's context window is the constraint, so this is
# ONE CALL THAT LOOPS INTERNALLY AND RETURNS NUMBERS. It returns counts and configurations and
# never schedules: a table of clubs and courts is small, forty full tournaments is not. A search
# driven step-by-step from the conversation would fill the window and fall over partway, which is
# a stronger reason for this to be code than reproducibility is.
#
# THE ANSWER IS DEFENSIBLE, NOT OPTIMAL (risk R-B3). Greedy descent finds a working booking,
# possibly a court or two above the true minimum. That is the safe direction against a number
# that becomes a court contract, and it is SAID OUT LOUD in the result rather than implied away.
# =============================================================================================

# The three counters the descent grades a configuration on, plus the courtesy. Read against the
# FIELD'S OWN FLOOR RESIDUE and never against zero — see `_cb_reading`.
_CB_COUNTERS = ("moved_day", "out_of_order", "venue_bends", "late_l1_mixed")


class _CBExhausted(Exception):
    """The build budget ran out. Carries nothing: the caller already holds everything found so
    far, and returning that beats dying with nothing (§3.4 — a four-minute run that crashes at
    minute three must not cost the whole afternoon)."""


def _hhmm_min(value):
    """`'HH:MM'` -> minutes from midnight, or None. The couriered documents speak `HH:MM` and so
    does every schedule row, so the arithmetic is done in one place rather than in five."""
    try:
        h, m = str(value).split(":")
        return int(h) * 60 + int(m)
    except (AttributeError, TypeError, ValueError):
        return None


def _min_hhmm(mins):
    return None if mins is None else f"{int(mins) // 60:02d}:{int(mins) % 60:02d}"


def _cb_bands(slate):
    """Each open club-day's bands as `(band, from, until, courts)` in minutes.

    ⚠ THE VOCABULARY IS THE CONTRACT'S AND NOTHING FINER (OI-56 §0.12). `td-resource-slate/v1`
    expresses three bands per venue-day — before the courts open up, once they do, and after the
    lights come on — and a finer window is a contract change. The three do not share a grain:
    the early and main counts are per venue AND day, the lit count is per VENUE only.

    The lit band is carved out of the main one rather than laid over it, because after
    `lights_on` the usable count IS `min(courts, lit_courts)` — `config_from_slate` maps it as a
    reduction and placement honours it, so treating them as overlapping would report a club as
    having more capacity in the evening than the engine will ever use."""
    out = {}
    for loc in (slate or {}).get("locations") or []:
        lit_n, lit_at = loc.get("lit_courts"), _hhmm_min(loc.get("lights_on"))
        for day, cell in (loc.get("available") or {}).items():
            if not isinstance(cell, dict):
                continue
            start = _hhmm_min(cell.get("start")) or _hhmm_min(slate.get("daily_start")) or 0
            end = _hhmm_min(cell.get("end")) or _hhmm_min(slate.get("daily_end")) or 24 * 60
            courts = cell.get("courts") or 0
            bands, main_from = [], start
            morning_until = _hhmm_min(cell.get("morning_until"))
            if cell.get("morning_courts") and morning_until and morning_until > start:
                bands.append(("early", start, morning_until, cell["morning_courts"]))
                main_from = morning_until
            main_to = end
            if lit_n and lit_at is not None and main_from < end:
                gate = max(lit_at, main_from)
                if gate < end:
                    main_to = gate
                    bands.append(("lit", gate, end, min(courts, lit_n)))
            if main_to > main_from:
                bands.append(("main", main_from, main_to, courts))
            out[(loc["id"], day)] = bands
    return out


def _cb_occupancy(blocks, lo, hi):
    """Peak simultaneous use inside `[lo, hi)`, and the contiguous segments at that peak.

    The sweep is `schedule_report.check_cap_slate`'s convention verbatim — a court is held for
    the WHOLE block, ends process before starts at the same instant, and start points are clamped
    to the window — because a peak read per start-time rather than per instant under-reads a
    club by as much as the blocks that began before the window opened."""
    pts = []
    for s, e in blocks:
        s2, e2 = max(s, lo), min(e, hi)
        if e2 <= s2:
            continue
        pts.append((s2, 1))
        pts.append((e2, -1))
    if not pts:
        return 0, []
    pts.sort(key=lambda x: (x[0], x[1]))
    cur, peak, prev, spans = 0, 0, None, []
    for t, delta in pts:
        if prev is not None and t > prev:
            spans.append((prev, t, cur))
        cur += delta
        peak = max(peak, cur)
        prev = t
    # The segments AT the peak, adjacent ones merged. Merged rather than listed because the
    # question a full window answers is "for how long was there nowhere to put anything", and
    # two touching segments are one such stretch.
    full = []
    for a, b, level in spans:
        if peak <= 0 or level < peak:
            continue
        if full and full[-1][1] == a:
            full[-1] = (full[-1][0], b)
        else:
            full.append((a, b))
    return peak, full


def _cb_axis_counts(result, slate):
    """S-4 §3.11: the per-axis COUNTS off the build `_cb_reading` already reduces.

    ⚠ COUNTS AND CONFIGURATIONS, NEVER A SCHEDULE. One small dict per build — a handful of
    integers per club per band, a first and last hour per club, a list of idle DAYS, and two
    integers for transit. BUDGET-1 §3.4's context rule binds this exactly as it binds the rest
    of the reading, and this is the widening most likely to be tempted past it.

    Taken here rather than at the one configuration that reports it, for `_cb_reading`'s own
    reason: `probe` caches the READING and discards the result, so a later pass has nothing left
    to count. Measured cost: 0.03 s on the bench, 0.06 s on a five-club slate."""
    bands = _cb_bands(slate)
    blocks: dict = {}
    people: dict = {}
    for m in result.get("schedule") or []:
        club, day = m.get("location"), m.get("day")
        s, e = _hhmm_min(m.get("start")), _hhmm_min(m.get("end"))
        if not club or not day or s is None:
            continue
        blocks.setdefault((club, day), []).append((s, e if e is not None else s + 90))
        for who in m.get("players") or []:
            people.setdefault(who, set()).add((day, club))

    courts: dict = {}
    hours: dict = {}
    club_days: dict = {}
    lights: dict = {}
    for loc in (slate or {}).get("locations") or []:
        club = loc["id"]
        open_days = sorted((loc.get("available") or {}))
        used = sorted(d for d in open_days if blocks.get((club, d)))
        club_days[club] = {"booked": len(open_days), "used": len(used),
                           "idle": [d for d in open_days if d not in set(used)]}
        first = last = None
        booked_start = booked_end = None
        for day in open_days:
            cell = loc["available"][day]
            bs, be = _hhmm_min(cell.get("start")), _hhmm_min(cell.get("end"))
            booked_start = bs if booked_start is None else min(booked_start, bs or booked_start)
            booked_end = be if booked_end is None else max(booked_end, be or booked_end)
            for s, e in blocks.get((club, day)) or []:
                first = s if first is None else min(first, s)
                last = e if last is None else max(last, e)
            for band, lo, hi, cap in bands.get((club, day), []):
                peak, full = _cb_occupancy(blocks.get((club, day)) or [], lo, hi)
                row = courts.setdefault(club, {}).setdefault(
                    band, {"open": cap, "peak": 0, "days": 0, "full_days": 0, "window": None})
                row["open"] = max(row["open"], cap)
                row["days"] += 1
                if peak >= cap and cap:
                    row["full_days"] += 1
                if peak > row["peak"]:
                    row["peak"] = peak
                    row["window"] = ({"day": day, "from": _min_hhmm(full[0][0]),
                                      "until": _min_hhmm(full[-1][1])} if full else None)
                if band == "lit" and cap:
                    lit = lights.setdefault(
                        club, {"lit": cap, "peak": 0, "nights_booked": 0, "nights_used": 0})
                    lit["nights_booked"] += 1
                    lit["peak"] = max(lit["peak"], peak)
                    if peak:
                        lit["nights_used"] += 1
        hours[club] = {"booked_start": _min_hhmm(booked_start), "booked_end": _min_hhmm(booked_end),
                       "first": _min_hhmm(first), "last": _min_hhmm(last)}

    moves = sum(1 for who, seen in people.items()
                for day in {d for d, _c in seen}
                if len({c for d2, c in seen if d2 == day}) > 1)
    return {"courts": courts, "hours": hours, "club_days": club_days, "lights": lights,
            "transit": {"moves": moves, "people": len(people)},
            "buffer_minutes": (slate or {}).get("end_of_day_buffer_minutes") or 0}


def court_axes(reading, slate, doc=None):
    """RESOURCES AGAINST CONSTRAINTS — the six axes, graded BINDING or SLACK off ONE build (R9).

    This is the analysis the booking step owes and did not have: what the tournament actually
    needs, set against what the director booked, on every axis his own resource document can
    express. Zero extra builds — the counts ride the reading the descent's first probe already
    produced.

    ⚠ IT REPORTS ON WHATEVER AXES THE SLATE HAS, and that is what makes it slate-agnostic rather
    than tuned to one director's five clubs: a one-club slate has no transit axis and an unlit
    club has no lights axis, and neither is reported as slack. No axis is skipped because some
    other slate lacked it.

    ⚠ THE TWO MEASURED SLATES DISAGREE ABOUT WHICH AXIS IS LOOSE, WHICH IS THE WHOLE POINT. On
    the bench the courts have slack under lights and every club-day is used; on the Operator's
    own 2027 answers no court is spare anywhere and 18 of 50 club-days are booked and never
    touched. A step that reported only courts would be blind on the second; one that reported
    only club-days would be blind on the first.

    ⚠ TRANSIT IS A COUNT AND NEVER A VERDICT. Nothing the director booked states a limit on how
    many people may cross town in a day, so grading it would be enforcing a rule nobody set."""
    counts = (reading or {}).get("axes") or {}
    if not counts:
        return {}
    clubs = [loc["id"] for loc in (slate or {}).get("locations") or []]
    names = {loc["id"]: (loc.get("name") or loc["id"])
             for loc in (slate or {}).get("locations") or []}
    out: dict = {}

    # 1 · COURTS — peak simultaneous use against what is open, per club per band.
    rows, binding = [], False
    for club in clubs:
        for band, row in sorted((counts.get("courts") or {}).get(club, {}).items()):
            full = row["full_days"] > 0
            binding = binding or full
            rows.append({"club": club, "club_name": names.get(club, club), "band": band,
                         "band_words": _diag_band_words(band), "open": row["open"],
                         "peak": row["peak"], "spare": max(0, row["open"] - row["peak"]),
                         "full_on_days": row["full_days"], "of_days": row["days"],
                         "full_window": row["window"] if full else None})
    out["courts"] = {"verdict": "BINDING" if binding else "SLACK", "clubs": rows}

    # 2 · HOURS — first and last play against the hours he booked, per club.
    buffer_min = counts.get("buffer_minutes") or 0
    rows, binding = [], False
    for club in clubs:
        row = (counts.get("hours") or {}).get(club)
        if not row:
            continue
        booked_end, last = _hhmm_min(row["booked_end"]), _hhmm_min(row["last"])
        tight = last is not None and booked_end is not None and last >= booked_end - buffer_min
        binding = binding or tight
        rows.append({"club": club, "club_name": names.get(club, club),
                     "booked": [row["booked_start"], row["booked_end"]],
                     "played": [row["first"], row["last"]],
                     "unused_minutes": (max(0, booked_end - last)
                                        if last is not None and booked_end is not None else None),
                     "tight": tight})
    out["hours"] = {"verdict": "BINDING" if binding else "SLACK", "clubs": rows}

    # 3 · CLUB-DAYS — days booked against days a match landed on.
    rows, idle = [], 0
    for club in clubs:
        row = (counts.get("club_days") or {}).get(club)
        if not row:
            continue
        idle += len(row["idle"])
        rows.append({"club": club, "club_name": names.get(club, club), "booked": row["booked"],
                     "used": row["used"], "idle": list(row["idle"])})
    out["club_days"] = {"verdict": "BINDING" if not idle else "SLACK", "clubs": rows,
                        "idle_total": idle}

    # 4 · LIGHTS — only where a club has any. Stated as LIGHTING and never converted to a court
    # number (scope L): floodlights are a club's evening, not two more courts.
    if counts.get("lights"):
        rows, binding = [], False
        for club in clubs:
            row = (counts.get("lights") or {}).get(club)
            if not row:
                continue
            full = row["peak"] >= row["lit"] > 0
            binding = binding or full
            rows.append({"club": club, "club_name": names.get(club, club), "lit": row["lit"],
                         "peak": row["peak"], "nights_booked": row["nights_booked"],
                         "nights_used": row["nights_used"],
                         "nights_unused": row["nights_booked"] - row["nights_used"]})
        out["lights"] = {"verdict": "BINDING" if binding else "SLACK", "clubs": rows}

    # 5 · THE CLOCK — the busiest day against HIS OWN matches-per-day figure.
    target = ((doc or {}).get("matches_per_day_target")
              if isinstance(doc, dict) else None)
    day_counts = (reading or {}).get("day_counts") or {}
    if target and day_counts:
        over = sorted(((d, n) for d, n in day_counts.items() if n > target),
                      key=lambda x: (-x[1], x[0]))
        busiest = max(day_counts.items(), key=lambda x: (x[1], x[0]))
        out["clock"] = {"verdict": "BINDING" if over else "SLACK", "target": target,
                        "busiest": {"day": busiest[0], "matches": busiest[1]},
                        "days_over": [{"day": d, "matches": n, "over_by": n - target}
                                      for d, n in over],
                        "headroom": max(0, target - busiest[1])}

    # 6 · TRANSIT — a COUNT, with its denominator, and no verdict.
    if len(clubs) > 1:
        t = counts.get("transit") or {}
        out["transit"] = {"verdict": None, "moves": t.get("moves", 0),
                          "people": t.get("people", 0)}
    return out


def _cb_reading(result, ml1, latest_start, slate=None):
    """One build reduced to the handful of numbers the search compares. NEVER a schedule.

    `late_l1_mixed` is counted here rather than read off a result key because the 14:00 courtesy
    (R19) is a demerit: a bent one is recorded in `venue_escapes` alongside every other bent venue
    rule, and the search needs this rule's own count, not the pooled one.

    R20 adds the DAY LOAD — matches per day, and per day the largest division whose first
    scheduled match falls on it. Both are counts, never a schedule (§3.4): one integer per day
    and one (name, count) pair per day, which is what the cap report needs and no more. It is
    taken here rather than at the two configurations that report it because `probe` caches the
    READING and discards the result, so a later pass has nothing left to count.

    S-4 §3.11 adds the SIX AXES' counts, for the same reason and on the same terms — `slate` is
    taken because half of them are a comparison against what the director booked, and a peak
    with nothing to be a peak OF is not an axis. Absent, the axis counts are simply not taken and
    every existing caller reads exactly what it read before."""
    late = 0
    if latest_start:
        for m in result.get("schedule") or []:
            ev = (m.get("event") or "").split(" — Group")[0]
            if ev in ml1 and (m.get("start") or "") > latest_start:
                late += 1
    day_counts: dict = {}
    per_div: dict = {}                    # (division, day) -> matches
    opens_on: dict = {}                   # division -> its first scheduled day
    for m in result.get("schedule") or []:
        day = m.get("day")
        if not day:
            continue
        day_counts[day] = day_counts.get(day, 0) + 1
        # The GROUP suffix is stripped so a round-robin division counts as ONE division, the
        # same way it does everywhere else the director reads a division name.
        ev = (m.get("event") or "").split(" — Group")[0]
        per_div[(ev, day)] = per_div.get((ev, day), 0) + 1
        if ev not in opens_on or day < opens_on[ev]:
            opens_on[ev] = day
    openers: dict = {}
    for (ev, day), n in per_div.items():
        if opens_on.get(ev) != day:
            continue                      # the division was already playing before this day
        best = openers.get(day)
        # Ties break on the division name, so the answer is deterministic and never depends on
        # the order the schedule happens to be in.
        if best is None or (n, ev) > (best[1], best[0]):
            openers[day] = (ev, n)
    return {
        "ok": not (result.get("unplaced") or []),
        "unplaced": len(result.get("unplaced") or []),
        "moved_day": len(result.get("assigned_day_spills") or []),
        "out_of_order": len(result.get("day_shape_exceptions") or []),
        "venue_bends": len(result.get("venue_escapes") or []),
        "late_l1_mixed": late,
        "hard_breaches": len(result.get("hard_venue_breaches") or []),
        "day_counts": day_counts,
        "day_openers": openers,
        "axes": _cb_axis_counts(result, slate) if slate else None,
    }


def _court_slate(base, edits):
    """`base` with its court supply rewritten. OI-56 §3.1 — the generalisation of BUDGET-1's
    `_cb_slate`, which this replaces and whose whole-slate behaviour it keeps exactly.

    Two kinds of edit, because the two customers of the shared machine ask different questions:

    · A MAPPING `{club: count}` — the WHOLE-SLATE form. Every club under consideration is
      enumerated, each club's booked count is REPLACED, and a club absent from the mapping is one
      the caller has trimmed away. This is `court_budget`'s downward descent, byte-identical.

    · A SEQUENCE of `(club, day_or_None, band, delta)` — the PER-DAY, PER-BAND form. `delta` is
      added to what the slate already carries, on one named day or on every open day, in one of
      the day's three bands. This is the grain OI-56 §0.12 measures the contract as already
      supporting, and it is what lets a refusal say "one more court at Mission Hills before 11:00
      on Tuesday" instead of naming a club for the whole tournament.

    ⚠ THE THREE BANDS DO NOT SHARE A GRAIN, and the difference is load-bearing:
        early · `available[day].morning_courts` — per venue AND day
        main  · `available[day].courts`         — per venue AND day
        lit   · `lit_courts`                    — per VENUE ONLY, so `day` is INEXPRESSIBLE
    A caller that asks for floodlit courts on a named day is asking for something
    `td-resource-slate/v1` cannot say, and it is refused here rather than silently applied to the
    whole week — a prescription the director cannot re-run is worse than none.

    Days and hours are never touched by either form: this varies SUPPLY, and a change that
    quietly shortened or lengthened the week too would be answering a question nobody asked."""
    if not isinstance(edits, dict):
        s = copy.deepcopy(base)
        for club, day, band, delta in edits:
            for loc in s["locations"]:
                if loc["id"] != club:
                    continue
                if band == "lit":
                    if day is not None:
                        raise ValueError(
                            f"floodlit courts are a per-venue count on this contract, not a "
                            f"per-day one, so {club} on {day} cannot be expressed")
                    if loc.get("lit_courts"):
                        loc["lit_courts"] = max(1, loc["lit_courts"] + delta)
                    continue
                if band not in ("early", "main"):
                    raise ValueError(f"unknown court band {band!r}")
                for d, cell in loc["available"].items():
                    if day is not None and d != day:
                        continue
                    if band == "early":
                        # A day with no morning step-up has no early band to widen. Skipped, and
                        # the caller records it — never silently promoted to the main band.
                        if "morning_courts" in cell:
                            cell["morning_courts"] = max(1, cell["morning_courts"] + delta)
                    else:
                        # `lit_courts` is left alone deliberately and needs no clamp: floodlit
                        # capacity is read as `min(courts, lit_courts)`, so raising the main band
                        # cannot raise it. Buying daytime courts does not buy floodlights, which
                        # is true of the club as well as of the arithmetic.
                        cell["courts"] = max(1, cell["courts"] + delta)
        return s

    counts = edits
    s = copy.deepcopy(base)
    keep = []
    for loc in s["locations"]:
        # ABSENT MEANS DROPPED, NOT UNCHANGED. `counts` enumerates every club under
        # consideration — `_cb_counts` seeds it from the slate itself — so a club missing from it
        # is one the descent has trimmed away. Treating absent as "leave this club alone" made
        # the reported floor a fiction: a floor of {MHCC: 14} was built and graded on a slate
        # still carrying ORLP's 20 courts and WEST's 4, so the search reported 14 courts for a
        # week that was actually played on 38. Caught by part B, which rebuilds every reported
        # configuration instead of trusting the search's own bookkeeping.
        n = counts.get(loc["id"])
        if n is None or n <= 0:
            continue
        if n is not None:
            for cell in loc["available"].values():
                cell["courts"] = n
                if "morning_courts" in cell:
                    cell["morning_courts"] = min(cell["morning_courts"], n)
            if loc.get("lit_courts"):
                loc["lit_courts"] = min(loc["lit_courts"], n)
        keep.append(loc)
    s["locations"] = keep
    ids = {loc["id"] for loc in keep}
    s["transit_minutes"] = {k: v for k, v in (s.get("transit_minutes") or {}).items()
                            if all(part in ids for part in k.split("|"))}
    return s


def _cb_counts(slate):
    """`{club: booked courts}` off a slate. The minimum across the club's open days, because a
    club that opens 15 courts on nine days and 8 on the tenth is an 8-court club to a descent
    that trims uniformly — claiming 15 would report a booking the week does not actually stand on.
    """
    out = {}
    for loc in slate["locations"]:
        vals = [cell["courts"] for cell in loc["available"].values() if isinstance(cell, dict)]
        if vals:
            out[loc["id"]] = min(vals)
    return out


class CourtProbe:
    """ONE COURT MACHINE, THREE CUSTOMERS — the "built once" debt, discharged (Y.3).

    BUDGET-1 shipped this machine inside `court_budget` and did not name it: a cached,
    budget-bounded closure that runs one REAL build at a given court supply and reduces it to a
    handful of counts. `court_budget` (shipped), OI-56's `diagnose_shortfall` (this build) and
    M9's STOP-1 all need it, and before this only the first could reach it.

    `.at(edits)` runs one real build at `edits` — either whole-slate `{club: count}` or a sequence
    of `(club, day_or_None, band, delta)`; see `_court_slate` — and returns `_cb_reading`'s
    counts.

    ⚠ IT RETURNS COUNTS AND CONFIGURATIONS AND NEVER A SCHEDULE. BUDGET-1 §3.4's context rule
    binds this build identically and for the same reason: wall-clock in September is nothing, but
    the run session's CONTEXT WINDOW is the real constraint, and forty full tournaments handed
    back through it would fill it and fall over partway. A table of clubs and courts is small.

    ⚠ THE CACHE KEY INCLUDES THE FINALS MAP. Two runs at the same courts and different finals
    days are two different tournaments, and letting them share a cached answer would make every
    finals-day saving in R6 a copy of the floor's own reading.

    ⚠ EXHAUSTION RAISES `_CBExhausted` RATHER THAN RETURNING A GUESS. The caller already holds
    everything found so far, and returning that beats dying with nothing — the partial-result
    discipline both customers reuse.
    """

    def __init__(self, base_slate, doc, levels=("1", "2"), budget=200, overrides=None,
                 finals_map=None):
        self.base = base_slate
        self.doc = doc
        self.levels = levels
        self.budget = budget
        self.overrides = overrides
        self.finals_map = finals_map
        self.latest_start = (doc.get("venue_rules") or {}).get("l1_mixed_latest_start")
        self.used = 0
        self._cache: dict = {}

    @staticmethod
    def _key(edits, fmap):
        spec = (tuple(sorted(edits.items())) if isinstance(edits, dict)
                else tuple(sorted(tuple(e) for e in edits)))
        return (spec, tuple(sorted((fmap or {}).items())))

    def at(self, edits, finals_map=None):
        """One real build at `edits`, cached and budget-bounded. Never a schedule."""
        fmap = finals_map if finals_map is not None else self.finals_map
        key = self._key(edits, fmap)
        if key in self._cache:
            return self._cache[key]
        if self.used >= self.budget:
            raise _CBExhausted()
        self.used += 1
        edited = _court_slate(self.base, edits)
        try:
            b = build_combined(levels=self.levels, constraints_doc=self.doc,
                               slate=edited, overrides=self.overrides,
                               finals_map=fmap, _probing=True)
            res, ml1 = b["result"], set(b["mixed_level_1"])
        except WeekRefused as e:
            # S-4 §3.7. This catch DOES happen under `_probing` — `_refuse_if_infeasible` raises
            # regardless of the flag — and emptying the list here made `late_l1_mixed` a
            # structural 0 on every refused reading (§0.18). `build_combined` stamps the resolved
            # list onto the result before the refusal gate, so it rides the exception; an absent
            # key is a result from before that change and falls back to empty rather than
            # guessing.
            res, ml1 = e.result, set(e.result.get("mixed_level_1") or ())
        except (DayMapRefused, ValueError, AssertionError) as e:
            out = {"ok": False, "error": f"{type(e).__name__}: {e}", "unplaced": None,
                   "hard_breaches": None}
            self._cache[key] = out
            return out
        # S-4 §3.11: the reading is taken against the EDITED slate, never the base one — the
        # axes are a comparison with what is open at this configuration, and grading a trimmed
        # slate's peak against the booking it was trimmed from would report slack that the
        # configuration under test does not have.
        r = _cb_reading(res, ml1, self.latest_start, slate=edited)
        # A configuration "holds" only if every match is placed AND both hard rules stand. The
        # second half is what R13 added: before it a slate that quietly relocated a final looked
        # identical to one that did not, and the search would have reported it as a floor.
        #
        # OI-56 reads the SAME field for the same reason from the other direction: a remedy is
        # graded on the WHOLE refusal, never on the one reason it was chosen to fix.
        r["holds"] = r["ok"] and not r["hard_breaches"] and not check_week(res)
        r["refusal"] = check_week(res)
        if isinstance(edits, dict):
            r["counts"] = dict(edits)
            r["total"] = sum(edits.values())
        self._cache[key] = r
        return r


# THE NAME Y.3 OWED. `court_probe` is the machine's name in every brief, register row and
# handoff from here on — `CourtProbe` is only the class it is spelled with, and STOP-1's brief
# points at this line.
court_probe = CourtProbe


def _cb_diag_slate(base, counts, ceilings):
    """The slate the not-fitting answer is diagnosed on: `counts` for the booking, and THE
    DESCENT'S OWN CEILINGS stamped on so the diagnosis cannot recommend a court the search
    already knows the club does not own.

    ⚠ WITHOUT THIS THE TWO HALVES DISAGREE ABOUT THE SAME CLUB. `court_budget` takes `ceilings`
    as an argument and `diagnose_shortfall` reads them off `locations[].physical_courts`, so a
    caller who passed ceilings the slate does not carry got a descent that stopped at eight
    courts and a ladder that cheerfully priced a twelfth — the "out of room here" answer R5
    reserves for a club that has genuinely run out, contradicted two paragraphs later on the same
    page. Measured cost of the disagreement on the bench squeezed to 65%: the ladder ran the full
    per-day sweep at every club instead of refusing pre-build, which is minutes spent to reach
    numbers the descent had already ruled out."""
    slate = _court_slate(base, counts)
    for loc in slate["locations"]:
        if loc["id"] in (ceilings or {}):
            loc["physical_courts"] = ceilings[loc["id"]]
    return slate


def _cb_does_not_fit(base, doc, levels, overrides, finals_map, counts, case, frame, state,
                     ceilings=None):
    """S-4 §3.1 — THE REACH. The whole answer for a week that does NOT fit, from ONE call.

    ⚠ THE ONE SEPTEMBER STEP WHOSE QUESTION IS "WHAT DO I NEED TO BOOK?" COULD NOT REACH EITHER
    ANSWER BUILT FOR IT. `diagnose_shortfall` — the courts · club · days · band answer shipped at
    OI-56 — has exactly one call site in product code, and both it and `probe_remedies` are gated
    `None if probing else …`, while `CourtProbe.at` builds `_probing=True` on EVERY build the
    court budget runs. So the step that asks the question and the machinery that answers it were
    in the same file and could not see each other.

    ⚠ WHY ONE NON-PROBING BUILD RATHER THAN A CALL INTO THE DIAGNOSTIC. The machinery behind the
    refusal has `cfg` in scope — which the jam and the unplaced half's day recovery both need —
    while `CourtProbe.at` discards results by design (BUDGET-1 §3.4's context rule). Re-raising
    the refusal is the one way to obtain the refused week's FULL diagnosis without widening the
    probe's contract.

    ⚠ THE TRUE COST IS THE MACHINERY THE RAISE TRIGGERS, NOT THE BUILD. Half a second to two
    seconds for the build itself, plus the remedies (the morning probe and the club-day search),
    plus the shortfall ladder, plus the nine-rule pass — bounded, tens of builds, tens of
    seconds. At an exhaustion configuration most ladder rungs refuse before building at all, on
    the ceiling check, which is the honest answer arriving cheap.

    ⚠ BOTH CASES, ONE SHAPE (R17, decision 6). A week that refuses at his booking but HOLDS
    within the clubs' ceilings gets the same menu as one that exhausts them: the jam, the
    cheapest holding booking, the named club-day alternative and the nine-rule rows. The
    Operator declined the bigger-number-alone draft in those words — the tool knew cheaper doors
    existed and kept them shut. The director asks one question and reads one answer shape
    whichever way his week is pointing.

    ⚠ EVERY SENTENCE NAMES ITS FRAME (§3.1.4). An exhaustion diagnosis describes the week at
    everything the clubs own — a booking he has not made — and the middle case describes the week
    as he booked it. A figure wearing the wrong frame is a booking he never made, printed at
    him."""
    slate = _cb_diag_slate(base, counts, ceilings)
    try:
        build_combined(levels=levels, constraints_doc=doc, slate=slate, overrides=overrides,
                       finals_map=finals_map, _probing=False)
        return None                       # it holds here; there is nothing not to fit
    except WeekRefused as e:
        result, shortfall, remedies = e.result, (e.shortfall or {}), list(e.remedies or [])
    except (DayMapRefused, ValueError, AssertionError) as e:
        return {"case": case, "frame": frame, "frame_words": _FRAME_WORDS.get(frame, ""),
                "shortfall": None, "remedies": [], "bendable": [],
                "builds": {"one_build": 1, "diagnosis": None, "remedies": 0, "bendable": 0},
                "note": f"the week at this configuration could not be diagnosed: {e}"}

    # THE FRAME IS RE-RENDERED RATHER THAN THREADED THROUGH THE ENGINE. `_diag_bottleneck` is
    # pure and costs 0.01 s, so the branch that knows which frame it is standing in re-states it
    # here — no `frame` argument is pushed down through `build_combined` and the refusal gate to
    # reach the one function that needs it.
    if shortfall.get("reasons") and (shortfall.get("bottleneck") or {}).get("frame") != frame:
        shortfall = dict(shortfall)
        shortfall["bottleneck"] = _diag_bottleneck(result, slate, shortfall["reasons"],
                                                   frame=frame)
    morning = next((r for r in remedies if r.get("remedy") == "morning_courts"), None)
    bend = bendable_pass(levels=levels, constraints_doc=doc, slate=slate, overrides=overrides,
                         finals_map=finals_map, refused_result=result, morning_row=morning)

    # ⚠ THE ACCOUNTING IS EXPLICIT, AND BOTH BUDGETS ARE REPORTED (§3.1.3, acceptance 20). The
    # descent's budget and the diagnostic's own are separate numbers and neither hides inside the
    # other: a director told "24 builds" when 60 tournaments were built is being told a number
    # that is not about anything.
    inner = {"one_build": 1,
             "diagnosis": dict(shortfall.get("builds") or {}),
             "remedies": sum(int(r.get("builds") or 0) for r in remedies),
             "bendable": sum(1 for r in bend if r.get("built"))}
    state["extra_builds"] += (inner["one_build"] + int((inner["diagnosis"] or {}).get("used", 0))
                              + inner["remedies"] + inner["bendable"])
    return {"case": case, "frame": frame, "frame_words": _FRAME_WORDS.get(frame, ""),
            "shortfall": shortfall, "remedies": remedies, "bendable": bend,
            "builds": inner, "note": ""}


def court_budget(levels=("1", "2"), constraints_doc=None, slate=None, ceilings=None,
                 finals_map=None, added_divisions=None, fill=0.75, budget_builds=200,
                 overrides=None):
    """What to book: the floor, the clean line, the finals-day savings, the cushions, the
    watchlist — as data, from one call (R1-R12).

    `ceilings` is `{club: physical courts}` (R5) — what each club OWNS, as distinct from what the
    director has booked. Read from the slate's own `physical_courts` when not passed. It is what
    lets the answer be "you're out of room here" instead of a bigger number the club cannot
    supply, and those are different answers the director acts on differently.

    Returns a dict of COUNTS AND CONFIGURATIONS. Never schedules (§3.4). Always carries
    `builds`, `not_tried` and `notes`; `partial` is True when the budget stopped it early."""
    base = copy.deepcopy(slate or wwtc_slate())
    # S-7: the pair is resolved by name, and a slate handed over without his rules is REFUSED
    # rather than quietly answered against the engine's rulebook. `court_budget()` bare still
    # runs on the defaults — only the SILENT half-pair substitution went.
    doc, rules_record = _paired_rules(constraints_doc, slate)
    ceilings = dict(ceilings if ceilings is not None else RS.ceilings_from_slate(base))
    start_counts = _cb_counts(base)
    state = {"used": 0, "cache": {}, "not_tried": [], "notes": [], "partial": False,
             # S-4 §3.1.3: builds the BRANCH triggered, outside the descent's own probe. Kept
             # apart so `builds.used` can account for every build without the descent's number
             # silently absorbing tens of tournaments it did not run.
             "extra_builds": 0,
             "args": {"levels": levels, "overrides": overrides, "finals_map": finals_map}}

    # OI-56 §3.1 — RE-POINTED ONTO THE NAMED MACHINE, NOT REWRITTEN. The descent below, its
    # ordering, its floor, clean line, cushions, watchlist and daily cap are untouched; only the
    # thing that runs one build moved out of this function and got a name, so OI-56 and STOP-1
    # can reach it. `tests/oi56_shortfall_diagnostic.py` part F pins this function's WHOLE result
    # byte-identical on the committed field, and that pin was taken and green before the lift was
    # written (R-6's mitigation, and the reason §9 ordered the build this way).
    _probe = court_probe(base, doc, levels=levels, budget=budget_builds, overrides=overrides,
                         finals_map=finals_map)

    def probe(counts, fmap=None):
        """One real build at `counts` — the whole-slate form, this search's only form."""
        r = _probe.at(counts, finals_map=fmap)
        state["used"] = _probe.used
        return r

    result = {"start": {"courts": dict(start_counts), "total": sum(start_counts.values())},
              "ceilings": dict(ceilings), "floor": {}, "clean_line": None,
              "floor_residue": None, "out_of_room": [], "finals_savings": [],
              "cushions": {}, "watchlist": [], "daily_cap": None,
              "builds": {"used": 0, "budget": budget_builds},
              # S-4: the step answers in BOTH directions from one call (R9). `does_not_fit` is
              # what he reads when the week does not fit — at his booking or at everything his
              # clubs own — and `surplus` is what he reads when it holds. Exactly one of them is
              # ever populated, and `out_of_room_source` says which of the two OPPOSITE
              # situations the phrase "out of room" is reporting (§0.7).
              "does_not_fit": None, "surplus": None, "axes": None,
              "out_of_room_source": None,
              # S-7: WHOSE RULES produced these figures — source, the rules doc's digest, and
              # its key count. The September readback says it out loud, and a reader of the
              # artifact can answer the question without trusting the call site.
              "rules": rules_record,
              "not_tried": state["not_tried"], "notes": state["notes"], "partial": False}
    try:
        _cb_search(probe, base, doc, levels, start_counts, ceilings, finals_map,
                   added_divisions, fill, state, result)
    except _CBExhausted:
        state["partial"] = True
        state["not_tried"].append(
            f"the search stopped at its build budget of {budget_builds}; everything below this "
            f"point in the descent is untried and the floor reported may be higher than the true "
            f"one")
        # THE PARTIAL-RESULT DISCIPLINE, EXTENDED TO THE TWO ANSWERS THAT COST NOTHING (S-4). The
        # watchlist is pure arithmetic over the draw ladder and the axes ride a reading the first
        # probe already produced, so a spent budget must not cost either of them: a director
        # whose search ran out three rungs down still gets the divisions closest to needing a
        # bigger draw, and the analysis of the booking he is actually holding.
        if not result["watchlist"]:
            try:
                _cb_watchlist(levels, added_divisions, fill, result)
            except Exception as e:                          # noqa: BLE001 — never lose the rest
                state["not_tried"].append(
                    f"the watchlist was not built: {type(e).__name__}: {e}")
    # Read off the machine itself rather than the last synced copy: exhaustion raises out of
    # `probe` before the sync line, so `state["used"]` can be one build stale exactly in the case
    # where the count is being reported as a limit. S-4 §3.1.3 adds the builds the not-fitting
    # branch triggered OUTSIDE the descent's own probe — the one non-probing build, the
    # diagnostic's ladder, the remedies and the nine-rule pass — so the number accounts for every
    # tournament this call built. The inner budgets are reported beside it, never inside it.
    result["builds"]["used"] = _probe.used + state["extra_builds"]
    result["builds"]["descent"] = _probe.used
    if state["extra_builds"]:
        result["builds"]["branch"] = state["extra_builds"]
        result["builds"]["inner"] = (result.get("does_not_fit") or {}).get("builds")
    result["partial"] = state["partial"]
    result["not_tried"] = state["not_tried"]
    result["notes"] = state["notes"]
    return result


def _cb_search(probe, base, doc, levels, start_counts, ceilings, finals_map,
               added_divisions, fill, state, out):
    """Steps 1-6 of §3.1, in order. Split out so `court_budget` can catch the budget exhaustion
    at ONE place and still return everything found before it — the partial-result discipline."""
    order = [loc["id"] for loc in base["locations"]]

    # ---- step 1 · establish feasibility. Raise uniformly until the week holds, or run out of
    # ---- room. "Out of room" is R9's answer and it is a DIFFERENT answer from a bigger number.
    counts = dict(start_counts)
    first = probe(counts)
    as_booked = first
    # ---- S-4 §3.11 · THE SIX AXES, taken HERE rather than at the end. Zero extra builds — this
    # ---- probe is the as-booked reading — and taken early on the partial-result discipline: a
    # ---- search that runs out of budget three rungs down still owes the director the analysis
    # ---- of the booking he actually holds, which cost nothing to produce.
    out["axes"] = court_axes(as_booked, base, doc)
    if not first.get("holds"):
        while True:
            # A club with NO ceiling is unbounded, not stuck. Defaulting an absent ceiling to the
            # club's current count made "out of room" the answer to every infeasible slate that
            # arrived without ceilings — which is the one answer R5 reserves for a club that has
            # genuinely run out, and the most misleading thing this search could say.
            headroom = [c for c in order
                        if c in counts and (c not in ceilings or counts[c] < ceilings[c])]
            if not headroom:
                out["out_of_room"] = sorted(
                    c for c in counts if c in ceilings and counts[c] >= ceilings[c])
                # ⚠ THE TWO SOURCES OF "OUT OF ROOM" ARE OPPOSITE SITUATIONS (§0.7). THIS one is
                # a week that CANNOT BE SCHEDULED at what the clubs own. The other — a cushion
                # that cannot be grown on a week that HOLDS — is set in `_cb_cushions`, and on
                # the Operator's own 2027 answers it is the one that fires, on a week that plays
                # with 0 unplaced and 0 broken rules. Telling him he is out of room at all five
                # clubs when his week is fine is the misreading this key exists to end.
                out["out_of_room_source"] = "exhaustion"
                out["notes"].append(
                    "Every club is at the courts it physically owns and the week still does not "
                    "hold. More courts is not the answer here — the levers left are a longer "
                    "week, fewer divisions, or another club.")
                out["floor"] = {"courts": dict(counts), "total": sum(counts.values()),
                                "verdict": "out of room",
                                "degradation": {k: first.get(k) for k in _CB_COUNTERS}}
                # THE OUT-OF-ROOM PATH STILL OWES AN ACCOUNT OF WHAT IT SKIPPED. Returning here
                # silently left `clean_line`, `cushions`, `finals_savings` and the watchlist all
                # empty with nothing in `not_tried` to say why — which reads as "we looked and
                # found nothing", the exact misreading §3.4's rule exists to prevent. The
                # watchlist is pure arithmetic and costs no build, so it is still produced; the
                # three that need a feasible week to descend from are reported as untried.
                out["not_tried"].append(
                    "the clean line, the three cushions and the finals-day savings were not "
                    "priced: all of them are measured DOWNWARD from a week that works, and this "
                    "field has no working week to start from at the courts these clubs own")
                # S-4 §3.1 — THE REACH. Before this the branch wrote two sentences and returned:
                # zero dates in the whole serialised answer, no day, no hour, no band, and every
                # club named rather than the binding one.
                out["does_not_fit"] = _cb_does_not_fit(
                    base, doc, levels, state["args"]["overrides"], finals_map, counts,
                    "exhaustion", "at-ceilings", state, ceilings=ceilings)
                _cb_watchlist(levels, added_divisions, fill, out)
                return
            for c in headroom:
                counts[c] += 1
            r = probe(counts)
            if r.get("holds"):
                break
    out["notes"].append(
        "The number is a defensible booking, not the theoretical minimum — a greedy descent can "
        "sit a court or two high. That is the safe direction against a booking you have promised.")

    # ---- the FLOOR RESIDUE: what this field degrades by even when courts are not the problem.
    # §0.7 measured 1 moved day, 11 out of order and 3 venue bends at 59 courts on the 2027 mock,
    # driven by the drawn players' own cross-division schedules. A clean line defined as ZERO
    # does not exist on a real field, and a search that chased one would never stop.
    top = probe(counts)
    residue = {k: top[k] for k in _CB_COUNTERS}
    out["floor_residue"] = dict(residue)
    out["notes"].append(
        "The clean line is read against this field's own floor residue, not against zero: even "
        "with courts to spare, players entered in several divisions force some movement.")

    # ---- step 2 · trim. One court off one club at a time, in REVERSE fill order — the last club
    # ---- to fill is the first to give a court back, because rule 43 fills the main site first
    # ---- and a court trimmed there is load-bearing far sooner. Never reorders the fill (R8).
    clean = dict(counts) if all(top[k] <= residue[k] for k in _CB_COUNTERS) else None
    for club in reversed(order):
        if club not in counts:
            continue
        while counts[club] > 0:
            trial = dict(counts)
            trial[club] -= 1
            if trial[club] == 0:
                trial.pop(club)
            r = probe(trial)
            if not r.get("holds"):
                break                      # that court was load-bearing; put it back and move on
            counts = trial
            # ---- step 3 · the clean line, PASSED THROUGH on the way down so it costs no extra
            # ---- builds. The lowest supply at which nothing has degraded past the residue.
            if all(r[k] <= residue[k] for k in _CB_COUNTERS):
                clean = dict(counts)
            if club not in counts:
                break
    floor_r = probe(counts)
    out["floor"] = {"courts": dict(counts), "total": sum(counts.values()), "verdict": "ok",
                    "degradation": {k: floor_r[k] for k in _CB_COUNTERS}}
    if clean is not None:
        cr = probe(clean)
        out["clean_line"] = {"courts": dict(clean), "total": sum(clean.values()),
                             "degradation": {k: cr[k] for k in _CB_COUNTERS}}
    else:
        out["not_tried"].append(
            "no clean line was found on the descent — every configuration tested degrades past "
            "this field's own floor residue")

    # ---- step 3b · the daily match cap (R20, Operator 2026-08-22 — OI-B9 option 1). REPORTS
    # ---- ONLY. Nothing here moves a match, a round or a day; the tool names the day and the
    # ---- director decides. Costs NO extra builds — both configurations it reads are already
    # ---- in the probe cache.
    _cb_daily_cap(probe, doc, counts, clean, out)

    # `out_of_room` is NOT "the floor happens to sit at a club's ceiling". It is R5's distinct
    # ANSWER — the search wanted more courts somewhere and the club did not own them. A floor
    # that lands on a ceiling while the week holds comfortably is not a shortage, and reporting
    # it as one would tell the director he has a problem he does not have. It is set in step 1's
    # exhaustion branch and by a cushion that cannot be built; nothing else may add to it.

    # ---- step 4 · finals-day savings (R6). Priced at the FIRST CONFIGURATION BELOW THE FLOOR —
    # ---- the one court the week could not give up — because "would this move lower the bill?"
    # ---- is exactly the question of whether that court stops being load-bearing. One build per
    # ---- move. The tool NEVER reshapes the calendar; it names the moves and their price.
    _cb_finals_savings(probe, base, doc, levels, counts, finals_map, state, out)

    # ---- step 5 · cushions (R12), and S-4 §3.9 BUILDS every level it reports.
    _cb_cushions(probe, counts, clean, ceilings, order, out)

    # ---- step 6 · watchlist (R7). Pure arithmetic off the draw ladder — no builds at all.
    _cb_watchlist(levels, added_divisions, fill, out)

    # ---- step 7 · S-4 §3.8 · THE SURPLUS (R9-R16), when the week holds as he booked it. The
    # ---- step answers in BOTH directions from one call: what he needs to book, and what he has
    # ---- booked beyond what the tournament needs.
    if as_booked.get("holds"):
        out["surplus"] = _cb_surplus(probe, base, doc, ceilings, order, as_booked, out,
                                     levels=levels, finals_map=finals_map,
                                     overrides=state["args"]["overrides"])
    else:
        # ---- S-4 §3.1 + R17 · THE MIDDLE CASE. The week refuses at HIS BOOKING and holds
        # ---- within the clubs' ceilings. The climbed floor is the courts answer, and the jam,
        # ---- the named club-day alternative and the nine-rule rows arrive beside it — computed
        # ---- off one non-probing build at his BOOKED counts, so the diagnosis is about the week
        # ---- he is holding rather than the one the search climbed to.
        out["does_not_fit"] = _cb_does_not_fit(
            base, doc, levels, state["args"]["overrides"], finals_map, start_counts,
            "middle", "as-booked", state, ceilings=ceilings)


def _slate_close_days(slate, idle):
    """`slate` with the named club-days closed. `idle` is `{club: [days]}`."""
    s = copy.deepcopy(slate)
    for loc in s["locations"]:
        for day in idle.get(loc["id"], []):
            loc["available"].pop(day, None)
    s["locations"] = [loc for loc in s["locations"] if loc["available"]]
    ids = {loc["id"] for loc in s["locations"]}
    s["dates"] = [d for d in s["dates"] if any(d in loc["available"] for loc in s["locations"])]
    s["transit_minutes"] = {k: v for k, v in (s.get("transit_minutes") or {}).items()
                            if all(part in ids for part in k.split("|"))}
    return s


def _slate_narrow_hours(slate, ends):
    """`slate` with each named club closing earlier. `ends` is `{club: 'HH:MM'}`."""
    s = copy.deepcopy(slate)
    for loc in s["locations"]:
        end = ends.get(loc["id"])
        if not end:
            continue
        for cell in loc["available"].values():
            if _hhmm_min(cell.get("start")) is not None and _hhmm_min(end) > _hhmm_min(
                    cell.get("start")):
                cell["end"] = end
    return s


def _cb_cost(after, before):
    """R16: what a release COSTS, as deltas off the SAME build that verified it.

    Savings without a price is half an answer, and the half that is missing is the one that
    stings in January: a release that quietly nudges the busiest day past the director's own
    figure is discovered by a player who planned around Thursday and finds out they play Friday.

    ⚠ A ZERO-COST RELEASE SAYS SO OUT LOUD. Silence and not-checked must never read the same.

    Free by construction — the verification build already computes every counter."""
    b_days, a_days = before.get("day_counts") or {}, after.get("day_counts") or {}
    b_peak = max(b_days.values(), default=0)
    a_peak = max(a_days.values(), default=0)
    busiest = max(a_days.items(), key=lambda x: (x[1], x[0]), default=(None, 0))
    cost = {"moved_day": after.get("moved_day", 0) - before.get("moved_day", 0),
            "out_of_order": after.get("out_of_order", 0) - before.get("out_of_order", 0),
            "busiest_day": {"day": busiest[0], "matches": busiest[1],
                            "was": b_peak, "change": a_peak - b_peak}}
    moved = cost["moved_day"] or cost["out_of_order"] or cost["busiest_day"]["change"]
    if not moved:
        cost["says"] = "Nothing else moves."
    else:
        bits = []
        if cost["moved_day"]:
            bits.append(f"{abs(cost['moved_day'])} more match(es) play on a different day from "
                        f"the one planned" if cost["moved_day"] > 0 else
                        f"{abs(cost['moved_day'])} fewer match(es) move off their planned day")
        if cost["out_of_order"]:
            bits.append(f"{abs(cost['out_of_order'])} more match(es) sit outside the order you "
                        f"run your day in" if cost["out_of_order"] > 0 else
                        f"{abs(cost['out_of_order'])} fewer match(es) sit outside that order")
        if cost["busiest_day"]["change"]:
            bits.append(f"your busiest day goes from {b_peak} matches to {a_peak}")
        cost["says"] = _and_list(bits).capitalize() + "."
    return cost


def _cb_surplus(probe, base, doc, ceilings, order, as_booked, out, levels=("1", "2"),
                finals_map=None, overrides=None):
    """R9's other half: WHEN HE HAS BOOKED TOO MANY, in the units he books in.

    ⚠ THE STEP IS AN OPTIMISATION IN BOTH DIRECTIONS, not a shortfall tool with a surplus
    footnote. It has to tell him when he has booked more than the tournament needs, and it has to
    do it in COURTS, CLUB-DAYS AND OPENING HOURS — because he does not book "courts", he books a
    club, for certain days, for certain hours, and because the axes disagree about which of the
    three is loose. Measured: on the Operator's own 2027 answers the court-count search reports
    ZERO surplus while a third of his booking sits on days and hours nothing ever uses.

    ⚠ MEASURED AGAINST THE VERIFIED SAFE LEVEL, NEVER THE CHEAPEST WEEK THAT PLAYS (R10). A
    slightly generous booking costs money; a falsely comfortable one costs a tournament. And the
    asymmetry is the whole reason this is the careful direction: a shortfall shows up while he is
    still at the screen, while A RELEASED COURT IS A DECISION HE DISCOVERS IN JANUARY WITH
    ENTRIES CLOSED.

    ⚠ WHEN NO SAFE LEVEL CAN BE BUILT, THE ANSWER DROPS FROM ADVICE TO FACT (R15, decision 4).
    On a slate where every club is booked at its ceiling the two-court margin behind safe cannot
    exist, and a release recommended there would stand on nothing. The idle days and hours are
    still stated, with their consequences and with the reason no release is recommended — the
    call is the director's alone. Nothing is recommended without a verified margin behind it.

    ⚠ READ, THEN BUILT — never read alone (R-13). Idle club-days and unused hours are READ off a
    schedule the engine produced under its own fill order; close them and it re-flows. Every
    released unit is re-built before it is reported, and about two builds is the whole cost.

    ⚠ NEITHER NAIVE MEASURE IS EVER PRINTED (§0.5, R-10). Not idle court-hours — on the bench
    that says release half the week, and it would release courts he needs. Not spare-at-peak —
    that says release nothing, and it hides a whole club. They are the two things a later session
    reaches for first, and both are wrong in opposite directions."""
    axes = out.get("axes") or {}
    cush = out.get("cushions") or {}
    safe = cush.get("safe") or {}
    verified = safe.get("built") is True
    start = out["start"]["courts"]
    names = {loc["id"]: (loc.get("name") or loc["id"]) for loc in base["locations"]}

    surplus = {
        "register": "advice" if verified else "facts",
        "against": ({"level": "safe", "verified": True, "courts": dict(safe.get("courts") or {}),
                     "total": safe.get("total")} if verified else None),
        "why_no_release": None, "courts": None, "club_days": None, "hours": None,
        "club_not_needed": None, "lighting": None, "assumes": [], "at_risk": [],
        "sentences": [], "builds": 0}
    if not verified:
        surplus["why_no_release"] = (
            "This booking carries no spare courts above the comfortable level, so no release is "
            "recommended; if you release days yourself, there is no cushion behind the week.")

    # ---- COURTS. What he booked above the level that was BUILT, per club.
    if verified and safe.get("courts"):
        per_club = {c: start.get(c, 0) - safe["courts"].get(c, 0) for c in start}
        release = {c: n for c, n in per_club.items() if n > 0}
        try:
            # Cached — the safe level was just built by `_cb_cushions`, so this is a cache read
            # rather than a build. Guarded anyway: a spent budget must cost the surplus its cost
            # line, never the whole answer (the partial-result discipline).
            cost = _cb_cost(probe(dict(safe["courts"])), as_booked) if release else None
        except _CBExhausted:
            cost = None
        surplus["courts"] = {
            "release": release, "total": sum(release.values()), "built": True,
            "recommend": bool(release), "cost": cost,
            "note": ("measured against the safe level, which is a week that was built — never "
                     "the cheapest week that plays")}
    else:
        surplus["courts"] = {"release": {}, "total": 0, "built": False, "recommend": False,
                             "cost": None,
                             "note": "no verified safe level exists to measure a court release "
                                     "against, so none is reported"}

    # ---- CLUB-DAYS. Days booked that no match landed on — READ, then BUILT.
    idle = {row["club"]: list(row["idle"]) for row in ((axes.get("club_days") or {}).get("clubs")
                                                       or []) if row["idle"]}
    if idle:
        try:
            closed = _slate_close_days(base, idle)
            r = _cb_reading(_probe_build(doc, closed, levels, finals_map, overrides), set(),
                            (doc.get("venue_rules") or {}).get("l1_mixed_latest_start"),
                            slate=closed)
        except (DayMapRefused, ValueError, AssertionError) as e:
            r = None
            surplus["club_days"] = {"release": [], "total": 0, "built": False,
                                    "recommend": False, "cost": None,
                                    "note": f"could not be re-built: {e}"}
        surplus["builds"] += 1
        if r is not None:
            holds = r["ok"] and not r["hard_breaches"]
            surplus["club_days"] = {
                "release": [{"club": c, "club_name": names.get(c, c), "days": d}
                            for c, d in sorted(idle.items())],
                "total": sum(len(d) for d in idle.values()), "built": holds,
                "recommend": bool(holds and verified),
                "cost": _cb_cost(r, as_booked) if holds else None,
                "note": ("" if holds else
                         "closing every day nothing landed on does not re-build, so no club-day "
                         "release is reported: the engine re-flows when a day is taken away")}
            if not holds:
                surplus["club_days"]["total"] = 0

    # ---- OPENING HOURS. The gap between the hours he booked and the hours play reached.
    ends = {}
    for row in (axes.get("hours") or {}).get("clubs") or []:
        if row["played"][1] and row["booked"][1] and not row["tight"]:
            ends[row["club"]] = row["played"][1]
    if ends:
        try:
            narrowed = _slate_narrow_hours(base, ends)
            r = _cb_reading(_probe_build(doc, narrowed, levels, finals_map, overrides), set(),
                            (doc.get("venue_rules") or {}).get("l1_mixed_latest_start"),
                            slate=narrowed)
        except (DayMapRefused, ValueError, AssertionError) as e:
            r = None
            surplus["hours"] = {"release": [], "total": 0, "built": False, "recommend": False,
                                "cost": None, "note": f"could not be re-built: {e}"}
        surplus["builds"] += 1
        if r is not None:
            holds = r["ok"] and not r["hard_breaches"]
            rows, minutes = [], 0
            for row in (axes.get("hours") or {}).get("clubs") or []:
                if row["club"] not in ends:
                    continue
                mins = row["unused_minutes"] or 0
                minutes += mins
                rows.append({"club": row["club"], "club_name": names.get(row["club"], row["club"]),
                             "booked_until": row["booked"][1], "play_ends": row["played"][1],
                             "hours": round(mins / 60, 1)})
            surplus["hours"] = {
                "release": rows, "total": round(minutes / 60, 1) if holds else 0,
                "built": holds, "recommend": bool(holds and verified),
                "cost": _cb_cost(r, as_booked) if holds else None,
                "note": ("" if holds else
                         "closing earlier does not re-build, so no hours release is reported")}

    # ---- A CLUB THAT APPEARS IN NO LEVEL — A FACT WITH ITS CONSEQUENCE, NEVER ADVICE (R11).
    # ---- BUDGET-1 R9's precedent and the same reason: the tool knows the arithmetic and nothing
    # ---- about the relationship. A club is more than its courts.
    levels_seen = (safe.get("courts") if verified else (out.get("floor") or {}).get("courts")) or {}
    gone = [c for c in order if c in start and not levels_seen.get(c)]
    if gone and levels_seen:
        club = gone[0]
        surplus["club_not_needed"] = {
            "club": club, "club_name": names.get(club, club), "recommend": False,
            "consequence": (f"the week builds with nothing at {names.get(club, club)} — the "
                            f"matches that play there now move to your other clubs"),
            "note": "stated as a fact about the arithmetic, never as a recommendation"}

    # ---- THE LIGHTING LINE (scope L). Stated as LIGHTING and never converted into a court
    # ---- number: floodlights are a club's evening, not two more courts.
    unused = [row for row in (axes.get("lights") or {}).get("clubs") or []
              if row["nights_unused"]]
    if unused:
        surplus["lighting"] = [
            f"{names.get(row['club'], row['club'])} has floodlights on "
            f"{row['nights_unused']} of the {row['nights_booked']} nights you have it, with "
            f"nothing on court after the lights come on"
            for row in unused]

    # ---- WHAT IT ASSUMES, SAID OUT LOUD (R12).
    surplus["assumes"] = [
        "the draws come in at the sizes you estimated",
        "this holds no room for a division that grows past its bracket"]
    at_risk = [r for r in (out.get("watchlist") or [])
               if r.get("room_left") is not None and r["room_left"] <= 0]
    surplus["at_risk"] = [{"division": r["division"], "basis": r["basis"],
                           "entered": r["entered"], "bracket": r["bracket"]}
                          for r in at_risk[:10]]
    if at_risk:
        surplus["assumes"].append(
            f"{len(at_risk)} of the divisions on your field were already at or over their "
            f"bracket last season")
    return surplus


def _probe_build(doc, slate, levels=("1", "2"), finals_map=None, overrides=None):
    """One real build at a slate, refusal caught — the surplus's own verification build.

    Not `CourtProbe`: the probe varies COURT SUPPLY on the base slate, and the club-day and hours
    releases vary days and hours, which `_court_slate` deliberately never touches (varying supply
    and quietly shortening the week would be answering a question nobody asked).

    ⚠ IT RUNS THE LANE THAT PRODUCED THE READING — the same levels, the same calendar, the same
    overrides. Measured the hard way: with the finals map dropped, closing days nothing landed on
    made the week refuse on the Operator's own answers, and the release was correctly but wrongly
    reported as one that does not re-build. A verification build on a different tournament
    verifies nothing."""
    try:
        return build_combined(levels=levels, constraints_doc=doc, slate=slate,
                              overrides=overrides, finals_map=finals_map,
                              _probing=True)["result"]
    except WeekRefused as e:
        return e.result


def _cb_daily_cap(probe, doc, floor, clean, out):
    """R20 (Operator, 2026-08-22 — OI-B9 option 1): does a configuration the search RECOMMENDS
    run a day past the director's own matches-per-day figure? Name the day, the count, how far
    over, and the biggest division that opens that day. **Report only — never move anything.**

    The figure is `matches_per_day_target` from `td-constraints/v1` (§2), which the Setup console
    already emits and the finals-map editor already flags days against. This reads the SAME key
    on purpose: two surfaces disagreeing about the director's own limit is worse than one of them
    being silent, which is what this was.

    Both configurations are already in `probe`'s cache, so this costs NO builds. It reads the
    two the search actually BUILT — the floor (which the cushions call `tight`) and the clean
    line (`comfortable`). The `safe` cushion is arithmetic on top of the clean line, never a
    build, so nothing is claimed about it rather than a figure being invented for it.

    The day shape MOVES with the court count, so it is re-read per configuration rather than taken
    once — and THE DIRECTION IS NOT FIXED, which is why neither configuration may stand in for the
    other. Measured both ways: on the 2027 field the floor peaks HIGHER than the clean line
    (135 at 52 courts against 134 at 54), while on the committed 2026 field it peaks LOWER
    (115 at 27 courts against 132 at 38, harness part H). Squeezing courts can flatten a week by
    spilling work onto other days, or concentrate it; which one happens is a property of the field,
    not a rule, and nothing here may assume either."""
    tgt = doc.get("matches_per_day_target")
    if not tgt:
        # §3.4: a step that finds nothing and a step that never ran read identically to the
        # director unless one of them says so.
        out["not_tried"].append(
            "the daily match cap was not checked: this run's rules carry no matches-per-day "
            "figure, so there is no limit to measure the busiest day against")
        return
    report = {}
    for name, cfg in (("floor", floor), ("clean_line", clean)):
        if not cfg:
            continue
        # No dedup when the two configurations coincide: `probe` is cached, so re-reading the
        # same courts costs nothing and both entries stay independently true.
        r = probe(dict(cfg))
        counts = r.get("day_counts") or {}
        openers = r.get("day_openers") or {}
        if not counts:
            continue
        peak_day = max(sorted(counts), key=lambda d: counts[d])
        over = []
        for day in sorted(counts):
            if counts[day] <= tgt:
                continue
            ev, n = openers.get(day, (None, 0))
            over.append({"day": day, "matches": counts[day], "over_by": counts[day] - tgt,
                         "biggest_division_opening_that_day": ev,
                         "its_matches_that_day": n})
        report[name] = {"courts": dict(cfg), "total": sum(cfg.values()),
                        "peak_day": peak_day, "peak": counts[peak_day],
                        "days_over": over}
    if not report:
        return
    out["daily_cap"] = {"target": tgt, "source": "matches_per_day_target", "by_configuration": report}
    worst = max((c for c in report.values()), key=lambda c: c["peak"])
    if any(c["days_over"] for c in report.values()):
        out["notes"].append(
            f"A day in the week this search recommends runs past the {tgt} matches a day these "
            f"rules carry — busiest {worst['peak']} on {worst['peak_day']}. The tool reports it "
            f"and changes nothing: which matches move, if any, is the director's call.")
    else:
        out["notes"].append(
            f"Every day of the recommended week sits inside the {tgt} matches a day these rules "
            f"carry — busiest {worst['peak']} on {worst['peak_day']}.")


def _cb_finals_savings(probe, base, doc, levels, floor, finals_map, state, out):
    """R6: which finals-day moves would lower the bill, each re-run for real.

    Bounded on purpose (§3.4). Without a finals calendar to price there is nothing to move, and
    that is REPORTED rather than passed over in silence — a search that quietly skips a whole
    step reads to the director as a step that found nothing."""
    if not finals_map:
        out["not_tried"].append(
            "finals-day savings were not priced — no finals calendar was supplied, so there is "
            "no calendar to move")
        return
    dates = list(base["dates"])
    cheaper = None
    for club in reversed([loc["id"] for loc in base["locations"]]):
        if floor.get(club):
            cheaper = dict(floor)
            cheaper[club] -= 1
            if cheaper[club] == 0:
                cheaper.pop(club)
            break
    if cheaper is None:
        return
    for division, day in sorted(finals_map.items()):
        if day not in dates:
            continue
        i = dates.index(day)
        for delta in (-1, 1):
            j = i + delta
            if not (0 <= j < len(dates)):
                continue
            try:
                r = probe(cheaper, {**finals_map, division: dates[j]})
            except _CBExhausted:
                out["not_tried"].append(
                    f"finals-day moves from {division} onward were not priced — the build budget "
                    f"ran out first")
                return
            if r.get("holds"):
                out["finals_savings"].append(
                    {"division": division, "from": day, "to": dates[j],
                     "courts_after": dict(cheaper), "total_after": sum(cheaper.values()),
                     "saves_courts": sum(floor.values()) - sum(cheaper.values())})
    if not out["finals_savings"]:
        out["notes"].append(
            "No single finals-day move makes a cheaper booking work. The calendar is not what is "
            "costing you courts here.")


def _cb_add_courts(counts, n, order, ceilings):
    """`n` more courts, laid on in the director's own fill order and never past what a club owns.

    Fill order, not "at the main site", and the difference is measured: on the 2027 mock five more
    courts at a satellite moved the late-start count by EXACTLY ZERO, because the rules that make
    a court worth having there are main-site rules. Adding blindly at the main site is wrong the
    other way — once that club is at its ceiling the cushion silently stops growing, which is how
    `safe` and `comfortable` collapsed onto the same answer the first time this ran.

    Returns `(counts, short)` — `short` is how many courts could not be placed anywhere, which is
    an out-of-room finding and is reported as one rather than rounded away."""
    out_counts = dict(counts)
    added = 0
    while added < n:
        for club in order:
            if added >= n:
                break
            have = out_counts.get(club, 0)
            if club in ceilings and have >= ceilings[club]:
                continue
            out_counts[club] = have + 1
            added += 1
        else:
            if all(club in ceilings and out_counts.get(club, 0) >= ceilings[club]
                   for club in order):
                break                       # every club is at the courts it physically owns
            continue
        if added >= n:
            break
    return out_counts, n - added


# ⚠ THE STEP-UP IS A PATH, NOT A SEARCH, AND IT IS BOUNDED. Four steps past `comfortable + 2`;
# beyond that the level is reported UNVERIFIED rather than printed as a recommendation, and R15
# then governs the surplus. Bounded because every step is a real build and because a search that
# climbs indefinitely on a slate with headroom would spend a minute to reach a number the
# director could not book anyway.
_CB_STEPUP_BOUND = 4


def _cb_verify_level(probe, counts, ceilings, order):
    """Build a cushion level, stepping UP THE FILL-ORDER PATH until the week holds.

    S-4 §3.9. Returns `(counts, built, steps)` — `built` True when a configuration on the path
    holds, False when the bound or the clubs' ceilings are reached first, None when the build
    budget ran out before an answer.

    ⚠ THE PATH IS THE RULE, AND IT MAY LAND A COURT ABOVE THE CHEAPEST HOLDING TOTAL. Measured on
    the September field: at 47 courts the fill-order point `{MHCC 26, ORLP 21}` FAILS while
    `{MHCC 25, ORLP 22}` HOLDS. Reporting the cheapest holding TOTAL would mean searching the
    configurations at a total rather than walking the director's own fill order, and the descent's
    doctrine is defensible-not-optimal: a number he can re-derive beats a number that is one court
    smaller. The answer says out loud that it may sit a court high."""
    cfg = dict(counts)
    for step in range(_CB_STEPUP_BOUND + 1):
        try:
            r = probe(cfg)
        except _CBExhausted:
            return dict(counts), None, step
        if r.get("holds"):
            return cfg, True, step
        nxt, short = _cb_add_courts(cfg, 1, order, ceilings)
        if short:
            return dict(counts), False, step
        cfg = nxt
    return dict(counts), False, _CB_STEPUP_BOUND


def _cb_cushions(probe, floor, clean, ceilings, order, out):
    """R12: tight / comfortable / safe — and S-4 §3.9 makes every one of them a level that was
    BUILT.

    Tight is the floor — the cheapest week that plays at all. Comfortable is the clean line when
    the descent found one, because that is the measured supply at which the week stops degrading;
    falling back to "floor plus two" only when it did not. Safe is comfortable plus two more.

    ⚠ WHAT S-4 CHANGED, AND IT MOVED A NUMBER THE DIRECTOR ACTS ON. `safe` was arithmetic — two
    courts laid on top of a configuration the search stood on — and nothing ever built it. The
    docstring deferred the guarantee to "part B of the harness", and part B grades every reported
    configuration ONLY on the committed 2026 field. On the SEPTEMBER field the derived safe is 46
    courts and 46 DOES NOT HOLD: it relocates the Men's 90 & over singles final, while 44 holds
    and 48 holds. One isolated hole, and the tool's own headline recommendation sat in it. The
    level now steps up the fill-order path to the first configuration that holds — 48 on that
    field — or is reported UNVERIFIED and recommended to nobody.

    ⚠ COMFORTABLE'S NO-CLEAN-LINE FALLBACK IS THE SAME DEFECT ONE LEVEL DOWN and is built under
    the same rule. With no clean line, "floor plus two" is arithmetic the probe never stood on.

    Cost: ONE extra build in the ordinary case, about half a second."""
    if not floor or not order:
        return
    tight = dict(floor)
    steps = {}
    if clean:
        comfortable, c_built, c_steps = dict(clean), True, 0
    else:
        derived, short = _cb_add_courts(floor, 2, order, ceilings)
        if short:
            out["notes"].append(
                "There was no room to build a comfortable cushion above the cheapest week — "
                "every club is already at the courts it owns.")
        comfortable, c_built, c_steps = _cb_verify_level(probe, derived, ceilings, order)
    derived_safe, short_safe = _cb_add_courts(comfortable, 2, order, ceilings)
    if short_safe:
        out["out_of_room"] = sorted(set(out["out_of_room"]) |
                                    {c for c in order
                                     if c in ceilings and derived_safe.get(c, 0) >= ceilings[c]})
        out["out_of_room_source"] = out.get("out_of_room_source") or "cushion"
        out["notes"].append(
            f"The safe cushion is {short_safe} court(s) short of what it asks for — the clubs are "
            f"out of room, so a bigger cushion has to come from a longer week or another club. "
            f"The week itself holds; this is about the margin behind it, not about whether it "
            f"can be played.")
    safe, s_built, s_steps = _cb_verify_level(probe, derived_safe, ceilings, order)
    if short_safe:
        # ⚠ A LEVEL THAT COULD NOT GROW IS NOT A LEVEL THAT WAS VERIFIED, and this is the case
        # R15 was ruled on. When every club is at the courts it owns, `_cb_add_courts` returns
        # the level below unchanged — so `safe` becomes `comfortable` wearing safe's name, holds
        # trivially, and would report itself BUILT. It is a margin that does not exist, and a
        # surplus recommended against it would stand on nothing.
        s_built = False
    if not clean and short:
        comfortable, c_built = dict(comfortable), False
    steps = {"comfortable": c_steps, "safe": s_steps}
    levels = (("tight", tight, True, 0), ("comfortable", comfortable, c_built, c_steps),
              ("safe", safe, s_built, s_steps))
    for name, cfg, built, step in levels:
        out["cushions"][name] = {"courts": dict(cfg), "total": sum(cfg.values()),
                                 "built": built, "steps_up": step}
    if s_built is True and s_steps:
        out["notes"].append(
            f"The safe level was raised {s_steps} court(s) above the arithmetic one because the "
            f"arithmetic one does not actually play — every level here is a week that was built. "
            f"It follows the order your clubs fill in, so it can sit a court above the cheapest "
            f"booking that would have worked.")
    if s_built is False and short_safe:
        out["not_tried"].append(
            "the safe level is the comfortable one under another name — there was no room above "
            "it to build a margin — so it is not a recommendation and nothing is measured "
            "against it")
    elif s_built is False:
        out["not_tried"].append(
            "no safe level could be built inside four courts of the comfortable one, so the "
            "figure shown for it is arithmetic and is not a recommendation")
    if s_built is None:
        out["not_tried"].append(
            "the build budget ran out before the safe level could be built, so the figure shown "
            "for it is arithmetic and is not a recommendation")
    if c_built is False:
        out["not_tried"].append(
            "no comfortable level could be built above the cheapest week, so the figure shown "
            "for it is arithmetic and is not a recommendation")
    out["notes"].append(
        "Comfortable is the level to book to: tight is the cheapest week that plays at all and "
        "leaves nothing for a draw that comes in bigger than estimated.")


def _cb_drawn_counts(levels):
    """The REAL drawn team count per division, and a round robin's printed group shape.

    S-4 §3.6. Read THROUGH THE S-2 SEAM — `load_from_finalized_draws` consults the ingest
    boundary, so September (a projected field), January (the real one) and the bench all answer
    the same way, and none of them needs to know which it is.

    ⚠ THE EVENTS ARE THE SOURCE, NOT A WIDENED PARSER. The division records `_divisions` returns
    carry no entrants — measured: `age`, `draw_size`, `etype`, `event`, `fmt`, `rounds` and
    nothing else — and widening that derivation to carry them would put an entrant count on a
    record three other callers read for its shape alone.

    An elim division's `teams` is the ordered bracket WITH bye sentinels, so the drawn count is
    the non-bye slots; a round robin arrives as one event per printed group, so the division's
    count is the groups summed and the shape is the groups themselves."""
    from scheduler_multi import BYE
    drawn, groups = {}, {}
    for lvl in levels:
        events, _seeds, _meta = wwtc_ingest.load_from_finalized_draws(lvl)
        for ev in events:
            base = ev.name.split(" — Group")[0]
            n = sum(1 for t in ev.teams if t.tid != BYE)
            drawn[base] = drawn.get(base, 0) + n
            if ev.fmt == "round_robin":
                groups.setdefault(base, []).append(n)
    return drawn, {k: sorted(v, reverse=True) for k, v in groups.items()}


def _cb_watchlist(levels, added_divisions, fill, out):
    """R7 + S-4 §3.6: the divisions closest to needing a bigger draw, ON THE REAL DRAWN COUNT,
    and the registration count at which each one costs a PLAYING DAY rather than a court.

    No builds. The distinction is the whole point: one more entrant inside the bracket costs a
    court somewhere, while the entrant that pushes a division past its bracket adds a WHOLE
    ROUND, and a round is a day. The director can buy a court; he cannot buy a day once the
    calendar is published.

    ⚠ WHAT S-4 CHANGED, AND WHY IT WAS WRONG. Every row was `round(draw_size x 0.75)` — including
    the 42 divisions whose entry count is a FACT sitting in the committed draws. Measured on the
    bench: 38 of 42 rows carried the wrong `room_left`, the assumed total was 774 against a real
    757, the worst row overstated by 21 (a 128 bracket assumed at 96, drawn at 75) and the worst
    understated by 13 (a 64 bracket assumed at 48, drawn at 61 — reported room 16, true room 3).
    SEVEN divisions were AT OR OVER their bracket on last season's own draws and were shown with
    two to four places still open, which errs in the falsely-comfortable direction on the one
    surface whose job is to say what is close to costing a day.

    ⚠ AND IT COULD NOT SEE A ROUND ROBIN AT ALL. A round robin's `draw_size` is 0, so `size < 2`
    skipped every one of them — 8 of 50 on the bench, 9 of 56 projected, and no others. ANN-1
    measured that of those 8, five move two days one step up the ladder and two the week cannot
    hold at all, so they were exactly the wrong rows to be silent about.

    ⚠ EVERY ROW SAYS WHICH KIND OF NUMBER IT IS. `basis` is `fact` for a division whose draw was
    printed and `estimate` for one the director is adding — because through the S-2 seam an added
    division's draw EXISTS and is fabricated at his stated count, so "the real count where a draw
    exists" yields his own estimate, which is the right number and better than three quarters of
    a bracket, but it is not a fact and must not read as one.

    `fill` survives on the legacy `added_divisions=` parameter path only — unreached (S-2 §4),
    not retired, and this build does not change that."""
    try:
        divisions = _divisions(levels)
    except Exception as e:                     # a projected-only field has no printed draws
        out["not_tried"].append(f"the watchlist was not built: {type(e).__name__}: {e}")
        return
    try:
        drawn, groups = _cb_drawn_counts(levels)
    except Exception as e:
        drawn, groups = {}, {}
        out["not_tried"].append(
            f"the drawn counts could not be read, so every row falls back to an estimate of "
            f"{int(round(fill * 100))}% of its bracket: {type(e).__name__}: {e}")

    # WHICH DIVISIONS ARE THE DIRECTOR'S OWN ESTIMATES. Read off the field the ingest boundary is
    # serving; with nothing serving, every printed draw is a fact and the set is empty.
    field = field_source.installed()
    added = {str(d.get("name")) for d in (getattr(field, "added", None) or [])
             if isinstance(d, dict) and d.get("name")}
    added |= {str(d.get("name")) for d in (added_divisions or [])
              if isinstance(d, dict) and d.get("name")}

    rows = []
    for d in divisions:
        size = getattr(d, "draw_size", 0) or 0
        real = drawn.get(d.event)
        basis = "estimate" if d.event in added else "fact"
        if getattr(d, "fmt", "") == "round_robin":
            shape = groups.get(d.event)
            if not shape:
                continue
            entrants = sum(shape)
            # ANN-1's reading C, re-derived and NOT re-decided here: one more entrant, and on the
            # reading that puts the division in ONE group. The grouping itself is a desk decision
            # January makes — ANN-1 records it as READ, never chosen — so the row states the step
            # the ladder takes at that reading rather than predicting a shape nobody has set.
            rows.append({
                "division": d.event, "format": "round_robin", "basis": basis,
                "bracket": None, "entered": entrants, "room_left": None, "next_bracket": None,
                "groups": list(shape), "rounds": MS._rr_rounds(max(shape)),
                "costs_a_day_at": entrants + 1,
                "rounds_at": MS._rr_rounds(entrants + 1),
                "note": ("a round robin has no bracket to fill, so nothing here is places left: "
                         "one more entrant is a decision about groups, and taken as one group "
                         "it runs the division over more days than the printed groups do")})
            continue
        if size < 2:
            continue
        if real is None:
            entered, basis = max(1, int(round(size * fill))), "estimate"
        else:
            entered = real
        rows.append({"division": d.event, "format": "single_elim", "basis": basis,
                     "bracket": size, "entered": entered,
                     "room_left": size - entered, "next_bracket": size * 2,
                     "costs_a_day_at": size + 1})
    # The fullest divisions lead. A round robin has no `room_left` to sort on and rides the tail
    # rather than being given an invented one.
    for row in sorted(rows, key=lambda r: (r["room_left"] is None,
                                           r["room_left"] if r["room_left"] is not None else 0,
                                           r["division"])):
        out["watchlist"].append(row)


def try_change(*, base_slate=None, slate=None, rules=None, levels=("1", "2"),
               constraints_doc=None, overrides=None, finals_map=None, schedule=False):
    """THE PROBLEM-SOLVING LOOP'S ONE TOOL (S-4 §3.5): test the director's own idea, for real.

    The run session presents the jam and the two answers; he proposes a change; THE SESSION
    BUILDS IT. One real build, about half a second on a September field, counts back.

    ⚠ IT TAKES SLATE EDITS AND RULE EDITS, and both halves are load-bearing. His idea may be
    courts — `slate=[(club, day_or_None, band, delta)]` or `slate={club: count}`, `_court_slate`'s
    two forms — or it may be one of the rules answer 2 varies, and a loop that tests only courts
    sends every rule idea back to the hand-rolling this exists to end. `rules` is merged onto the
    constraints document; a value of `None` DELETES that key, which is how a rule is switched off.

    ⚠ THE SESSION NEVER REASONS ABOUT CAPACITY INSTEAD OF BUILDING IT. A court figure derived in
    chat is exactly how a wrong booking reaches a club.

    ⚠ COUNTS AND CONFIGURATIONS ONLY, NEVER A SCHEDULE. BUDGET-1 §3.4's context rule binds this
    identically to everything else on this path, and an interactive loop is the surface most
    likely to break it: forty tournaments handed back through a chat window fill it and fall over
    partway through his afternoon. Asking for the schedule is REFUSED rather than quietly
    honoured, because the refusal is the only thing that keeps the rule from being a convention.
    """
    if schedule:
        raise ValueError(
            "this returns counts and configurations, never a schedule — a full board handed back "
            "through the run session fills its context and the run falls over partway. Build the "
            "idea here, keep what works, and make the schedule from the console.")
    base = base_slate or wwtc_slate()
    # S-7: same pairing rule as `court_budget`, and it matters MORE here — his `rules=` edits are
    # merged onto this doc, so a substituted default turned "switch off this rule and tell me what
    # it saves" into switching it off on top of fourteen rules that are not his. ⚠ THE
    # `schedule=True` REFUSAL STAYS AHEAD OF THIS ONE: `make_run_bundle.py`'s trap drives a bare
    # `schedule=True` call and must keep proving the guard it names, not this pairing refusal.
    _paired, _paired_record = _paired_rules(constraints_doc, base_slate)
    doc = copy.deepcopy(_paired)
    for key, value in (rules or {}).items():
        if "." in str(key):
            head, tail = str(key).split(".", 1)
            block = doc.setdefault(head, {})
            block.pop(tail, None) if value is None else block.update({tail: value})
        elif value is None:
            doc.pop(key, None)
        else:
            doc[key] = value
    # ⚠ TAKEN AFTER THE MERGE, DELIBERATELY. The record describes the rules this build actually
    # RAN under, so the digest is of the doc AS EDITED; `edited` names the keys his what-if moved.
    # Taken before the merge it would claim his rules while the build ran his rules-as-modified.
    rules_record = _rules_record(doc, _paired_record["source"], list((rules or {}).keys()))
    edited = _court_slate(base, slate) if slate is not None else base
    try:
        result = build_combined(levels=levels, constraints_doc=doc, slate=edited,
                                overrides=overrides, finals_map=finals_map,
                                _probing=True)["result"]
    except WeekRefused as e:
        result = e.result
    reading = _cb_reading(result, set(result.get("mixed_level_1") or ()),
                          (doc.get("venue_rules") or {}).get("l1_mixed_latest_start"),
                          slate=edited)
    days = reading["day_counts"]
    busiest = max(days.items(), key=lambda x: (x[1], x[0]), default=(None, 0))
    return {"builds": 1, "holds": bool(reading["ok"] and not reading["hard_breaches"]
                                       and not check_week(result)),
            "unplaced": reading["unplaced"], "hard_breaches": reading["hard_breaches"],
            "moved_day": reading["moved_day"], "out_of_order": reading["out_of_order"],
            "venue_bends": reading["venue_bends"], "late_l1_mixed": reading["late_l1_mixed"],
            "busiest_day": {"day": busiest[0], "matches": busiest[1]},
            "refusal": check_week(result),
            # S-7: whose rules this what-if ran under, and which of them his idea moved.
            "rules": rules_record,
            "courts": {loc["id"]: max((c["courts"] for c in loc["available"].values()),
                                      default=0)
                       for loc in edited["locations"]}}


def _check_setup(setup):
    """Validate a couriered td-setup/v1 bundle (shared by finals_plan + build_from_setup).
    F7: the bundle no longer carries finals — a truthy embedded `finals_map` is REJECTED
    (CEO ruling, 2026-07-25) so the retired pre-engine console approximation can never bind
    placement again. An empty {} (old bare emits in the wild) is tolerated."""
    if not isinstance(setup, dict) or setup.get("schema") != "td-setup/v1":
        raise ValueError(f"expected a td-setup/v1 bundle, got: {setup.get('schema') if isinstance(setup, dict) else type(setup).__name__}")
    if setup.get("finals_map"):
        raise ValueError("td-setup/v1 no longer carries finals_map — courier the finals-map "
                         "editor loop instead (td-finals-plan/v1 -> td-finals-map/v1)")


def _finals_pins(setup, levels, finals):
    """Resolve an optional td-finals-map/v1 doc into validated {event: date} pins ({} = none).
    F7-6: validation includes structural feasibility — a pin earlier than the division's
    rounds allow is REJECTED loudly (the cascade would otherwise slide it silently)."""
    if not finals:
        return {}
    dates = (setup.get("slate") or wwtc_slate())["dates"]
    divs = _divisions(levels)
    # REVIEW-1 (M10): the feasibility floor honours the same-day-finish collapse.
    # master_schedule._lay_out joins a switched division's last two rounds (`joined = div.event
    # in same_day and need >= 2`), so its cascade spans one fewer day — raw d.rounds refused a
    # pin on a day the engine could in fact honour ("7 rounds cannot finish by ..." naming a
    # feasible day's successor: a FALSE refusal). Resolution warnings are dropped here on
    # purpose — the build and plan lanes resolve the same names and report them.
    con = setup.get("constraints") or default_constraints()
    joined = set(_resolve_same_day_finish(
        (con.get("same_day_finish") or {}).get("divisions"), divs, []))
    return FP.finals_map_from_doc(finals, dates=dates,
                                  known_events={d.event for d in divs},
                                  rounds_by={d.event: d.rounds - (1 if d.event in joined else 0)
                                             for d in divs})


def _round_matches(draws, divs):
    """FMAP-1 (ruling 58): PLANNED matches per division per round, off the APPROVED DRAWS.

    The finals map's Matches row has to answer "what does this drag cost that day?", and the
    only honest source is the draws themselves. `td-finals-plan/v1` carries `draw_size` (the
    BRACKET size, not the entrant count) and no bye data, and the 8 round-robin divisions carry
    `draw_size: 0` — so a doc-side guess reads 990 against a real 760 and, at a 125 threshold,
    fires on the wrong day in 3 of 10 cases (opening day would read 156 against a true 54).

    Method:
      elimination  — round 1 is the count of adjacent slot pairs where NEITHER slot is a bye
                     (byes are the whole reason the bracket size overstates the work); rounds
                     >= 2 are `draw_size / 2**r`, every bye having been consumed by then.
      round robin  — each group of m >= 3 plays `m//2` matches in each of its `m-1` (m even)
                     or `m` (m odd) circle rounds, i.e. C(m,2) matches in total.

    Keys mirror `master_schedule._round_label`, which is what `round_day` is keyed by, so the
    console joins the two maps directly. Read-only: nothing here touches placement.
    """
    by_ev = {d.event: d for d in divs}
    out = {}
    for dr in draws:
        div = by_ev.get(dr.event)
        if div is None:
            continue
        total, per = div.rounds, {}
        if dr.fmt == "single_elim" and dr.draw_size > 0:
            slots = list(dr.slots)
            per[MS._round_label(1, total)] = sum(
                1 for i in range(0, len(slots) - 1, 2)
                if not slots[i].is_bye and not slots[i + 1].is_bye)
            for r in range(2, total + 1):
                per[MS._round_label(r, total)] = dr.draw_size // (2 ** r)
        elif dr.fmt == "round_robin":
            for g in dr.groups:
                m = len(g.members)
                if m < 3:
                    continue
                for r in range(1, min(m - 1 if m % 2 == 0 else m, total) + 1):
                    lbl = MS._round_label(r, total)
                    per[lbl] = per.get(lbl, 0) + m // 2
        out[dr.event] = per
    return out


# ---------------------------------------------------------------- FMAP-2: the feasibility verdict
#
# The finals map used to ECHO the desk's days and say nothing about whether they survive a real
# board. Everything below computes what it now says: a full-build verdict over the map the console
# opens on, plus a per-division day grid. Read-only projection throughout — the same
# `build_combined` lane run with a map, nothing on the placement path changes (the engine gate's
# stated grounds). All of it is OPT-IN: `finals_plan(..., engine_check=True)`. Absent, the plan doc
# is byte-for-byte what it was and the console with it.

# The schedule's event key carries the round-robin group suffix ("Women's 80 & over singles —
# Group 1") while the finals map is keyed by DIVISION. Joining the two by exact name silently
# drops all 8 RR divisions and the verdict then reports clean on 8 of 50 rows it never looked at.
_GROUP_SUFFIX = re.compile(r"\s+—\s+Group\s+\d+$")


def _division_last_day(schedule):
    """{division: the day its LAST match plays}, group draws folded into their division.

    D2 (Operator ruling, 8/15): a round-robin division's finals date means the group FINISHES BY
    that day. That is graded here and displayed on the surface — placement is untouched, and
    ruling 71's carve-out otherwise stands.
    """
    last = {}
    for m in schedule:
        ev = _GROUP_SUFFIX.sub("", m["event"])
        if ev not in last or m["day"] > last[ev]:
            last[ev] = m["day"]
    return last


def _console_day(day):
    """`2026-01-25` -> `Sun 1/25` — the finals console's OWN date form (FMAP-1, ruling 63).

    Deliberately not `_short_day` ("Jan 25"): that is the desk's register, for warnings about a
    desk stamp. These sentences are read on the finals board, whose column headers and refusal
    message both say "Sun 1/25", so they say it the same way.
    """
    try:
        d = datetime.datetime.strptime(day, "%Y-%m-%d")
    except (TypeError, ValueError):
        return str(day)
    return f"{d.strftime('%a')} {d.month}/{d.day}"


def _verdict_notices(result):
    """The build's own notices, attributed to DIVISIONS: {division: {kind: [detail, ...]}}.

    A division "needs a look" when the build attributes any notice to it — the chip's second
    number is exactly the size of this map (§0.2's attribution).
    """
    by_id = {m["id"]: m for m in result["schedule"]}
    out = {}

    def add(ev, kind, detail):
        if not ev:
            return
        out.setdefault(_GROUP_SUFFIX.sub("", ev), {}).setdefault(kind, []).append(detail)

    for s in result.get("assigned_day_spills") or []:
        ev = s.get("event") or by_id.get(s.get("id"), {}).get("event")
        add(ev, "moved_day", s)
    for c in result.get("cadence_conflicts") or []:
        add(c.get("event"), "two_rounds", c)
    for e in result.get("venue_escapes") or []:
        mid = e[0] if isinstance(e, (list, tuple)) else e.get("id")
        add(by_id.get(mid, {}).get("event"), "other_venue",
            {"id": mid, "day": e[1], "start": e[2], "venue": e[3]}
            if isinstance(e, (list, tuple)) and len(e) >= 4 else {"id": mid})
    return out


def _verdict_note(ev, mapped, kinds, last_day, main_site=None):
    """One flagged division -> the note the card renders: cause in TD vocabulary, and the day to
    propose when there IS one.

    `landed` is present ONLY for the finishes-by miss — the single shape where re-mapping the
    division to the engine's day is a real proposal. A division that finishes on time but plays
    two rounds in one day, or reaches another venue, has no day to offer: it carries a mini-tag
    and the card explains, which is report-never-refuse rather than a suggestion we cannot stand
    behind. Wording routes through `LANG-1_glossary.md` — "moved to another day" for a match that
    could not sit where it was assigned, "two rounds in one day" for the cadence shape, and no
    retired term ("spill", "cadence", "escape") reaches the screen.
    """
    venue = (kinds.get("other_venue") or [{}])[0]
    if last_day and last_day > mapped:
        where = f" at {venue['venue']}" if venue.get("venue") and venue.get("day") == last_day else ""
        return {"event": ev, "mapped": mapped, "landed": last_day, "kind": "spill",
                "cause": (f"Mapped to {_console_day(mapped)}, but that day has no free court for "
                          f"this division's last match — it plays {_console_day(last_day)}"
                          f"{where} instead.")}
    if kinds.get("moved_day"):
        s = kinds["moved_day"][0]
        placed, assigned = s.get("placed_day"), s.get("assigned_day")
        if placed and assigned and placed < assigned:
            return {"event": ev, "mapped": mapped, "landed": None, "kind": "spill_early",
                    "cause": (f"This division finishes on {_console_day(mapped)} as mapped, but "
                              f"one of its matches plays earlier than planned, on "
                              f"{_console_day(placed)}.")}
    if kinds.get("two_rounds"):
        c = kinds["two_rounds"][0]
        day = c.get("day")
        # When the doubled-up day IS the mapped day, saying both halves names the same date twice
        # ("finishes on Mon 1/26 … but two rounds land on Mon 1/26") and reads as a non-sequitur.
        # Measured on the committed 8/15 map, which is exactly that case.
        return {"event": ev, "mapped": mapped, "landed": None, "kind": "cadence",
                "cause": (f"Two of this division's rounds land on {_console_day(day)}, the day it "
                          f"is mapped to finish."
                          if day == mapped else
                          f"This division finishes on {_console_day(mapped)} as mapped, but two "
                          f"of its rounds land on {_console_day(day)}.")}
    # A recorded venue exception does NOT imply the match left the main site, and writing it as
    # though it did produced a self-contradicting sentence: "one match plays at MHCC — the main
    # site had no free court at that hour." Rule 6 (the cap on main-site starts between 15:00 and
    # 16:00) and rule 38 record their exceptions ON the main site, so the escape and the venue
    # can name the same club. Latent since VENUE-1; BUDGET-1 made it common by design, because
    # §3.2's rungs deliberately let a lesser venue rule bend in order to KEEP a final or a Level 1
    # Mixed match at the main site — which is the good outcome, and read as the bad one.
    where = venue.get("venue")
    if where and main_site and where == main_site:
        return {"event": ev, "mapped": mapped, "landed": None, "kind": "venue",
                "cause": (f"This division finishes on {_console_day(mapped)} as mapped and stays "
                          f"at {where}, but one match had to give up a court preference there to "
                          f"do it.")}
    return {"event": ev, "mapped": mapped, "landed": None, "kind": "venue",
            "cause": (f"This division finishes on {_console_day(mapped)} as mapped, but one match "
                      f"plays at {where or 'another venue'} — the main site had no "
                      f"free court at that hour.")}


def _cell_state(result):
    """(notice total, {match id: day}, {match id: division}) — what a graded cell is compared on.

    ⚠ `cadence_conflicts` is ABSENT, not empty, on a result that has none — `.get(...) or []` is
    load-bearing, not defensive habit.
    """
    return (len(result.get("assigned_day_spills") or [])
            + len(result.get("cadence_conflicts") or []),
            {m["id"]: m["day"] for m in result["schedule"]},
            {m["id"]: _GROUP_SUFFIX.sub("", m["event"]) for m in result["schedule"]})


def _grade(base, cell, moved_event=None):
    """DELTA vs the as-mapped board, never an absolute count (§0.4) — grade AND what it costs.

    The board the TD is looking at already carries notices of its own, so a cell that reads the
    SAME total as the baseline is *no worse than today* — grading it absolutely would paint most
    of the grid red and train the reader to ignore it. Three grades, the approved mock's:
      hold    — no new notice and not one match moves
      moves   — no new notice, but matches shift day to make room
      blocked — a notice the current map does not have: this day costs a court somewhere

    ⚠ The COST is carried out with the grade (Operator ruling, 8/16). Grading alone flattened a
    28-fold range into one colour: on the committed field the pink cells run from +1 problem
    touching one other division to +28 across eleven, and a TD avoiding both equally is being
    told a nuisance and a bad idea are the same thing. These three numbers are what the console
    shows on hover and shades on:

      cost      — how many MORE matches land on a day they were not planned for (plus days where
                  a division ends up playing two rounds). The delta, never the absolute.
      divisions — how many OTHER divisions are disturbed. This is usually the number that matters:
                  the cost of moving a division is almost never paid by the division you moved.
      matches   — how many matches change day at all. Deliberately NOT the cost signal: 83 matches
                  shifting a day is cheap if every one of them still plays when it was planned to,
                  and the committed field has exactly that case.
    """
    moved = [k for k, v in base[1].items() if cell[1].get(k) != v]
    divisions = {cell[2].get(k) for k in moved} - {moved_event, None}
    grade = ("blocked" if cell[0] > base[0] else "moves" if moved else "hold")
    return {"grade": grade, "cost": max(cell[0] - base[0], 0),
            "divisions": len(divisions), "matches": len(moved)}


def _engine_check(setup, levels, plan, grid_events=None, progress=True):
    """The td-finals-plan/v1 `engine_check` block (contracts §13) — additive and optional.

    Runs the FULL build over the map the console opens on (pre-ruled 8/15: the 8/15 field's
    moved-day records were court-level facts a quick check cannot see), attributes its notices to
    divisions, and grades every structurally-feasible day of every division one board deep.

    `grid_events` grades only the named divisions instead of all of them — the harness's lever, so
    a test can exercise real full-build grading without spending the runbook's whole wait. None =
    the shipped depth: every gradable cell (D4 option 2).

    NOMAP-1: when the BASELINE build refuses the week this returns `{"refused": {...}}` instead of
    a verdict — the refusal's reasons, its remedies and the printable report, for `finals_plan` to
    route onto the plan document. Nothing is graded past that point: a week no legal schedule can
    hold has no day worth grading (measured at 65% courts — seven of the probe division's nine
    non-mapped cells refuse and none is feasible, minutes of builds to learn nothing).
    """
    dates, mapped = plan["dates"], plan["finals_day"]
    tour = plan.get("tournament") or ""

    def _doc(m, pins=None):
        return {"schema": FP.FINALS_MAP_SCHEMA, "tournament": tour, "confirmed": True,
                "finals_map": dict(m), "pins": dict(pins or {})}

    def _say(msg):
        if progress:
            print(msg, flush=True)

    _say("Checking the finals map against a full build …")
    _t0 = datetime.datetime.now()
    try:
        _base_build = build_from_setup(setup, levels=levels, finals=_doc(mapped))
        base_result = _base_build["result"]
    except WeekRefused as e:
        # NOMAP-1 / FG-11's first half. The baseline runs NON-probing, exactly as it always has,
        # so by the time the exception arrives its remedies have already been re-run for real on
        # this week's own entries — the answers exist, and before this they died in flight and the
        # director got a Python exception four months out instead of a calendar.
        #
        # Nothing is graded from here. A grid over a week that cannot be built is all refusals,
        # and the caller gets the refusal itself: reasons, the prober's rows verbatim, and
        # `format_refusal`'s rendering ready to print. This grades nothing and invents nothing —
        # no probe, no search, no court lever, no new sentence (FG-12 stays open).
        _say("  the week as supplied cannot be scheduled, so there is nothing to check against — "
             "the reasons and what would fix them are on the plan")
        # OI-56: `shortfall` rides INSIDE the existing `week_refusal` key beside `remedies` —
        # no contract key moves at the top level (§3.8). It carries what to ADD, and its own
        # BUILD COST, so the cost of an answer is on the answer rather than in a harness's
        # constant (acceptance 5: context and clock are both the diagnostic's price).
        return {"refused": {"reasons": e.reasons, "remedies": e.remedies,
                            "shortfall": e.shortfall, "report": format_refusal(e)}}
    # what one full build costs on THIS machine — the estimate below is derived from it rather
    # than printed as a constant. Timing never reaches the returned doc, so determinism holds.
    per_build = max((datetime.datetime.now() - _t0).total_seconds(), 0.1)
    base = _cell_state(base_result)
    last_day = _division_last_day(base_result["schedule"])
    notices = _verdict_notices(base_result)

    # The main site is the rank-1 venue of the director's own list (rule 43), never the string
    # "MHCC". The note needs it to tell "stayed at the main site" from "went to another club".
    _order = getattr(_base_build.get("cfg"), "venue_order", None)
    _main = _order[0] if _order else None
    notes = [_verdict_note(ev, mapped[ev], kinds, last_day.get(ev), _main)
             for ev, kinds in sorted(notices.items()) if ev in mapped]
    notes.sort(key=lambda n: n["event"])
    flagged = len(notes)
    _say(f"  {len(mapped) - flagged} of {len(mapped)} hold as mapped · {flagged} need a look")

    # ---- the per-division day grid ----------------------------------------------------------
    # Structural feasibility first (a final cannot land before its rounds fit, the same-day-finish
    # collapse honoured exactly as `_finals_pins` honours it), so infeasible cells cost no build.
    divs = _divisions(levels)
    con = setup.get("constraints") or default_constraints()
    joined = set(_resolve_same_day_finish(
        (con.get("same_day_finish") or {}).get("divisions"), divs, []))
    need = {d.event: d.rounds - (1 if d.event in joined else 0) for d in divs}
    flagged_evs = {n["event"] for n in notes}

    wanted = sorted(mapped) if grid_events is None else sorted(grid_events)
    todo = [(ev, dt) for ev in wanted for i, dt in enumerate(dates)
            if i >= need.get(ev, 1) - 1 and dt != mapped.get(ev)]
    # D4's ruling: generation says what it is doing WHILE it runs. The estimate is derived from
    # the baseline build just timed above — one graded cell is one build of the same work — and
    # never printed as a constant: a quoted figure goes stale across machines and fields, and
    # trains the reader to read ordinary variance as a fault (D-16's lesson).
    _say(f"  grading {len(todo)} candidate day(s) across {len(wanted)} divisions at full build "
         f"depth — roughly {max(1, round(len(todo) * per_build / 60))} minute(s)")

    day_grid, done = {}, 0
    for ev in wanted:
        row = {}
        for i, dt in enumerate(dates):
            if i < need.get(ev, 1) - 1:
                # no build is spent on a day the division's rounds cannot reach, so there is no
                # cost to report — the cell is not a choice at all.
                row[dt] = {"grade": "infeasible"}
            elif dt == mapped.get(ev):
                # the currently-mapped day is graded from the baseline build, not a re-run of it,
                # and costs nothing by definition: it IS the board.
                row[dt] = {"grade": ("hold" if ev not in flagged_evs else
                                     "blocked" if any(n["event"] == ev and n.get("landed")
                                                      for n in notes) else "moves"),
                           "cost": 0, "divisions": 0, "matches": 0}
            else:
                m = dict(mapped)
                m[ev] = dt
                try:
                    r = build_from_setup(setup, levels=levels, finals=_doc(m, {ev: dt}),
                                         _probing=True)["result"]
                    row[dt] = _grade(base, _cell_state(r), moved_event=ev)
                except (ValueError, WeekRefused):
                    # the courier gate refused this map, or the week itself cannot be built with
                    # the division moved here — either way that IS the infeasible answer, and the
                    # contract's own words hold: a day that refuses the week "is not a choice at
                    # all", so the cell carries `grade` alone.
                    #
                    # NOMAP-1: `WeekRefused` is a RuntimeError, so before this it escaped the
                    # `except ValueError` and took the WHOLE grid down with it — measured at 70%
                    # courts, a board where 37 of 50 divisions held as mapped lost its entire
                    # verdict to one refusing candidate day. The build above runs `_probing=True`
                    # for the same reason the catch is here: the grid discards the exception, so
                    # the ~6 remedy builds behind it are seconds spent to learn nothing. The
                    # refused BASELINE is the opposite case — its remedies ARE the deliverable,
                    # so it runs non-probing and pays for them.
                    row[dt] = {"grade": "infeasible"}
                done += 1
                if done % 25 == 0 or done == len(todo):
                    _say(f"  … {done} of {len(todo)} days graded")
        day_grid[ev] = row

    return {"graded_map": {ev: mapped[ev] for ev in sorted(mapped)},
            "held": len(mapped) - flagged, "flagged": flagged,
            "notes": notes,
            "day_grid": {ev: day_grid[ev] for ev in sorted(day_grid)}}


# =============================================================================================
# BEST-1 (2026-08-29) — STEP 2's FIRST MAP IS THE OPTIMIZED CALENDAR. LANE: September (M8).
#
# Today Step 2 hands the director ONE candidate, produced by a four-level precedence — pinned,
# then the desk's own stamp, then an anchor off his desk semifinal, then a computed cascade. It
# is a defensible map, and since KEY-1 it is the desk's real weekday shape. IT IS NOT A CHOSEN
# MAP, BECAUSE NOTHING CHOOSES: offering a best needs a score, more than one candidate, and a
# comparison, and OI-62 measured that none of the three existed. This block supplies all three,
# OPT-IN, and leaves the shipped draft exactly where it is.
#
# THE SCORE IS D-54's, IN D-54's ORDER, OVER LEGAL ARRANGEMENTS ONLY — quietest busiest day,
# then fewest courts to book, then fewest matches out of the daily order. An arrangement that
# leaves a match unplaced, bends something hard, or fails `check_week` is not ranked, not shown
# and cannot win: it is not a calendar at all. Everything else a build reports — venue bends,
# matches moved to another day, late Level-1 Mixed — is REPORTED AND NEVER SCORED. And MATCHING
# LAST SEASON'S DATES IS WORTH NOTHING (D-54): no term below expresses it, directly or by proxy.
# KEY-1's desk-derived draft is where the search STARTS, never what it aims at.
#
# ⚠ LEG 2 IS PRICED ON THE FINALISTS, NOT ON EVERY CANDIDATE (brief §2.3 option A, Operator-
# approved 8/29), and every clause of that is measured rather than reasoned. `court_budget` costs
# ~70 s and ~105 builds per evaluation, so pricing courts per candidate is 343 x 70 s ~ 6.6 HOURS
# against a ruled 10-12 minute allowance. The free proxy was DRIVEN AND FAILS: `_cb_axis_counts`'
# peak court occupancy saturates at what the director already booked (54 against a real floor of
# 48) and so cannot tell two finals maps apart. The hill-climb therefore steers on legs 1 and 3,
# the best arrangements it SAW get a real court bill, and leg 2 decides among them in D-54's
# order. The measured pilot is the argument for that shape as much as the warning: the map that
# won on legs 1 and 3 was NOT the cheapest to book (48 -> 49), so a design that never re-read
# courts would have shipped the +1 blind.
#
# ⚠ AND THE TOOL DOES NOT TAKE THAT TRADE FOR HIM (Operator ruling 8/29, brief §5a). It neither
# decides nor refuses: it puts BOTH calendars in front of him with all three numbers each and he
# picks. That is why this returns two of them, and why the DRAFT IS NEVER A FINALIST — ranking it
# against the searched arrangements would quietly re-impose "refuse any calendar dearer to book
# than the free draft", which is one of the two options the ruling explicitly DECLINED.
#
# ⚠ THE CHOICE IS ELICITED IN THE RUN CONVERSATION, NOT ON A CONSOLE SCREEN. Both calendars are
# recorded here as plain maps precisely so the chosen one re-enters through the EXISTING re-edit
# loop (`finals_plan(setup, finals=<td-finals-map/v1>)`, the same pins path a zero-drag courier
# round trip already uses). No console code is written and `finals_plan.py` is not opened, so the
# D-3 freeze stays sealed at five waivers granted and five spent.
#
# THE RESULT IS DEFENSIBLE, NOT OPTIMAL, and says so in `court_budget`'s own words (:3612): a
# greedy hill-climb can sit above the true optimum, and a calendar he can re-derive beats one
# that is one better and unexplainable.
# =============================================================================================

# The RULED allowance, taken mid-band of the Operator's 10-12 minutes. It bounds the WHOLE
# optimization — the draft's own court bill, the hill-climb, and the finalists' court bills —
# because those are one wait as far as the director is concerned, and §2.3's finalists are what
# "the remaining allowance buys".
_BEST_ALLOWANCE = 660
# §2.3 option A's N: how many of the arrangements the search saw get a REAL court bill.
_BEST_FINALISTS = 5


def _best_need(setup, levels, divs=None):
    """{event: days its rounds need} — the structural-feasibility rule, REUSED not re-derived.

    Identical to `_engine_check`'s own (`:4755-4759`), same-day-finish collapse honoured exactly
    as `_finals_pins` honours it. `divs` is passed in by `finals_plan`, which has already made
    the one pass over the draw PDFs; absent, it is resolved here for a standalone caller.
    """
    divs = _divisions(levels) if divs is None else divs
    con = setup.get("constraints") or default_constraints()
    joined = set(_resolve_same_day_finish(
        (con.get("same_day_finish") or {}).get("divisions"), divs, []))
    return {d.event: d.rounds - (1 if d.event in joined else 0) for d in divs}


def _best_candidates(need, mapped, dates):
    """Every structurally-legal single-division finals move off `mapped`, in a FIXED order.

    ⚠ SORTED BY (division, date), and that is not tidiness: determinism is a hard invariant, so
    the order candidates are read in must never be what decides a tie. Structurally infeasible
    cells cost no build, exactly as they cost none in the day grid.

    Measured on the committed 2027 seed over the full 56-division stand-in field: 343 moves
    against a naive ceiling of 504 — per division min 3, max 9, median 6, and 0 divisions with
    no move at all.
    """
    return [(ev, dt) for ev in sorted(mapped) for i, dt in enumerate(dates)
            if i >= need.get(ev, 1) - 1 and dt != mapped[ev]]


def _best_legal(reading):
    """LEGAL, and nothing below ranks anything that is not: every match placed, nothing hard
    bent, and the week itself holds. An illegal arrangement is not a worse calendar — it is not
    a calendar. Roughly one candidate in ten refuses the week on this field (35 of 343 on the
    pilot's first round), so this filter is load-bearing rather than defensive habit."""
    return (not reading["unplaced"] and not reading["hard_breaches"]
            and not reading["refusal"])


def _best_pair(reading):
    """Legs 1 and 3 — what the hill-climb steers on. Leg 2 is priced on the finalists (§2.3)."""
    return (reading["busiest_day"]["matches"], reading["out_of_order"])


def _best_calendar(which, fmap, reading, courts):
    """One of the two calendars Step 2 hands over, with ALL THREE of D-54's numbers on it.

    `courts` is `court_budget`'s floor total — the real one, built, never estimated. Both
    calendars carry the same shape so a reader comparing them is comparing like with like, which
    is the whole point of showing two.
    """
    return {"which": which, "finals_day": {ev: fmap[ev] for ev in sorted(fmap)},
            "busiest_day": dict(reading["busiest_day"]), "courts_to_book": courts,
            "out_of_order": reading["out_of_order"],
            # REPORTED, NEVER SCORED (§2.1) — the gravy, so he can see what else moved.
            "venue_bends": reading["venue_bends"], "moved_day": reading["moved_day"],
            "late_l1_mixed": reading["late_l1_mixed"]}


def _best_trio(cal):
    """D-54's three numbers off a calendar, in D-54's order. THE comparable, lexicographic."""
    return (cal["busiest_day"]["matches"], cal["courts_to_book"], cal["out_of_order"])


def _best_sentences(draft, best, search):
    """What Step 2 says out loud, in the director's language. A RECORD, NEVER ADVICE — the tool
    prices and proposes and never tells him his own calendar is wrong (§2.5)."""
    lines = [f"The tool tried {search['search_builds']} versions of the week in "
             f"{max(1, round(search['seconds'] / 60))} minute(s) and kept the best it found."]
    if best is None:
        lines.append("It found nothing better than the calendar it already had, so there is one "
                     "calendar here, not two.")
        return lines
    lines.append("Two calendars, and the choice is yours — the one the tool derives on its own, "
                 "and the one the search found:")
    for cal in (draft, best):
        lines.append(
            f"  · {'the calendar as derived' if cal is draft else 'the searched calendar'}: "
            f"busiest day {cal['busiest_day']['matches']} matches "
            f"({_console_day(cal['busiest_day']['day'])}) · "
            f"{cal['courts_to_book']} courts to book · "
            f"{cal['out_of_order']} matches outside the daily order")
    # ⚠ SAID ONLY AS STRONGLY AS IT IS TRUE. The first smoke run printed "better on all three
    # counts" for a calendar that was better on ONE and level on the other two — an overclaim
    # about the exact numbers he is being asked to choose between. Winning every leg means
    # STRICTLY better on every leg; anything weaker gets the weaker sentence, with its count.
    d, b = _best_trio(draft), _best_trio(best)
    for name, x, y in (("The searched calendar", b, d), ("The calendar as derived", d, b)):
        if all(i < j for i, j in zip(x, y)):
            lines.append(f"{name} is better on all three counts.")
            break
        if all(i <= j for i, j in zip(x, y)) and x != y:
            n = sum(1 for i, j in zip(x, y) if i < j)
            lines.append(f"{name} is no worse on any of the three counts, and better on "
                         f"{n} of them.")
            break
    if search["still_improving"]:
        # RULED 8/29: it stops, it SAYS it was still improving, and whether to keep going is his.
        lines.append("The search was still finding better weeks when its time ran out. It can "
                     "keep going if you want it to — that is your call, not the tool's.")
    # `court_budget`'s own register (:3612), inherited rather than restated stronger.
    lines.append("This is a defensible calendar, not the theoretical best — a search like this "
                 "can stop a little short of the very best arrangement. That is the safe "
                 "direction against a calendar you are about to announce.")
    return lines


def _best_search(setup, levels, plan, *, allowance=_BEST_ALLOWANCE,
                 finalists=_BEST_FINALISTS, max_builds=None, progress=True, divs=None):
    """The `td-finals-plan/v1` `optimized_map` block (contracts §13) — additive and optional.

    Greedy hill-climb over single-division finals moves, EVERY CANDIDATE A REAL BUILD. No
    surrogate score and no estimated capacity: `try_change` at ~0.7 s is the verdict, exactly the
    way the court budget's own descent works. A round evaluates every remaining candidate and
    takes the single best improving move; it stops on the first of a local optimum, the
    allowance, or `max_builds`.

    Returns BOTH calendars — the free draft and the search's winner — each with all three of
    D-54's numbers, plus every finalist's trio, the moves taken, what was spent, and whether the
    allowance stopped it while it was still improving (§5a, §2.5).

      allowance  : seconds for the WHOLE optimization, draft pricing and finalist pricing
                   included. Default 660 — the Operator's ruled 10-12 minutes, mid-band.
      finalists  : how many of the arrangements seen get a real `court_budget`. Bends DOWN, never
                   below 1, when a shortened allowance cannot buy that many bills.
      max_builds : THE HARNESS'S DETERMINISTIC LEVER, and the reason it exists is worth stating.
                   A wall-clock bound makes the number of builds a property of the machine, so a
                   test that must prove "same input, same map, twice" bounds the search by BUILDS
                   instead, which is deterministic. Same precedent as `court_budget`'s
                   `budget_builds` and `_engine_check`'s `grid_events`. None = the clock alone.
      progress   : D4's ruling — the wait is named UPFRONT and the search says what it is doing
                   while it runs, never a silent eleven-minute stall at Step 2. False silences it.

    ⚠ TIES BREAK ON A FIXED KEY — the score, then the division name, then the date — never on
    iteration order. Determinism is a hard invariant and this is where it would be lost.
    """
    t0 = datetime.datetime.now()
    slate_doc, con = setup.get("slate"), setup.get("constraints")
    ov = setup.get("overrides") or None
    dates = list(plan["dates"])
    draft_map = dict(plan["finals_day"])
    # ⚠ TWO COUNTERS, AND THE SPLIT IS LOAD-BEARING. `total` is every build this call spends, so
    # the cost of the answer rides on the answer (OI-56's discipline). `search` is the hill-climb's
    # own, and it is what `max_builds` bounds — measured the other way round on the first smoke
    # run: the draft's court bill alone is ~106 builds, so a `max_builds` counting both spent the
    # whole bound before a single candidate calendar was built and the search silently did nothing.
    spent = {"total": 0, "search": 0}

    def _say(msg):
        if progress:
            print(msg, flush=True)

    def _elapsed():
        return (datetime.datetime.now() - t0).total_seconds()

    def _read(fmap):
        """One real build over `fmap`. The S-7 pair travels WHOLE — his slate with his rules —
        or `_paired_rules` refuses it; a court figure computed under the engine's rulebook and
        labelled as the director's is the fault that guard exists to close."""
        spent["total"] += 1
        return try_change(base_slate=slate_doc, constraints_doc=con, levels=levels,
                          overrides=ov, finals_map=dict(fmap))

    def _courts(fmap):
        """Leg 2, BUILT — `court_budget`'s floor total over this calendar. ~70 s, ~105 builds."""
        cb = court_budget(levels=levels, constraints_doc=con, slate=slate_doc,
                          finals_map=dict(fmap), overrides=ov)
        spent["total"] += cb["builds"]["used"]
        return cb["floor"].get("total"), cb

    # D4's ruling, and §2.4 item 1: THE WAIT IS NAMED BEFORE IT IS SPENT, never after.
    _say(f"Looking for a quieter week — up to about {max(1, round(allowance / 60))} minute(s). "
         f"You will be shown both calendars at the end and the choice will be yours.")

    # ---- the free draft, priced in full ---------------------------------------------------
    # It is one of the two calendars he is shown, so its court bill is not optional. Timing it
    # is also how the finalists' reserve below gets a MEASURED size instead of a constant.
    draft_read = _read(draft_map)
    if not _best_legal(draft_read):
        # ⚠ A WEEK THAT DOES NOT HOLD IS NOT SEARCHED, and the guard is here rather than at the
        # call site so it stands however this is reached. NOMAP-1's rule holds identically: a week
        # no legal schedule can hold has no calendar worth optimizing, every candidate would fail
        # `_best_legal`, and the search would spend the director's eleven minutes proving it. He
        # gets his draft map and the reasons — which is what that path already hands him. The one
        # `court_budget` call below is skipped too: on a refusing week it answers a different
        # question (`does_not_fit`) and reports no floor to put on a calendar.
        return {"calendars": [], "choice_required": False, "wins_every_leg": None,
                "finalists": [], "not_searched": "the week as supplied cannot be scheduled, so "
                                                 "there is no calendar to improve",
                "search": {"builds": spent["total"], "search_builds": 0,
                           "seconds": round(_elapsed(), 1),
                           "rounds": 0, "candidates": 0, "refused": 0,
                           "allowance_seconds": allowance, "max_builds": max_builds,
                           "stopped": "week refused", "still_improving": False,
                           "finalists_priced": 0},
                "sentences": ["The week as supplied cannot be scheduled, so there is no calendar "
                              "to improve — the reasons and what would fix them are on the plan."]}
    _cb_t0 = datetime.datetime.now()
    draft_courts, _draft_cb = _courts(draft_map)
    cb_cost = max((datetime.datetime.now() - _cb_t0).total_seconds(), 0.1)
    draft_cal = _best_calendar("draft", draft_map, draft_read, draft_courts)
    _say(f"  the calendar as derived: busiest day {draft_cal['busiest_day']['matches']} · "
         f"{draft_courts} courts to book · {draft_cal['out_of_order']} out of the daily order")

    # ⚠ THE PRICING RESERVE IS MEASURED, NEVER QUOTED (D-16's lesson, `_engine_check`'s
    # precedent). The finalists' court bills come OUT of the allowance — they are the same wait —
    # so the hill-climb's deadline is what is left after the bills just measured are set aside.
    # A shortened allowance buys FEWER bills rather than none: the winner is priced or there is
    # no second calendar to offer at all.
    room = max(allowance - _elapsed(), 0.0)
    n_final = max(1, min(finalists, int(room // cb_cost)))
    search_deadline = _elapsed() + max(room - n_final * cb_cost, 0.0)

    # ---- the hill-climb --------------------------------------------------------------------
    need = _best_need(setup, levels, divs=divs)
    current, cur_pair = dict(draft_map), _best_pair(draft_read)
    draft_pair = cur_pair
    pool: dict = {}          # arrangement -> (pair, reading). THE DRAFT IS NEVER IN IT (§5a).
    rounds, refused, stopped = 0, 0, "local optimum"

    while True:
        best_here = None
        for ev, dt in _best_candidates(need, current, dates):
            if max_builds is not None and spent["search"] >= max_builds:
                stopped = "build bound"
                break
            if _elapsed() >= search_deadline:
                stopped = "allowance"
                break
            trial = dict(current)
            trial[ev] = dt
            spent["search"] += 1
            # ⚠ BEFORE THE LEGALITY FILTER, NOT AFTER. Sited after the `continue` below it, a
            # candidate that refused the week on exactly the 200th build swallowed that whole
            # progress line — seen on the first full-allowance run, which reported 150 and then
            # 250. D4's ruling is that generation says what it is doing WHILE it runs, and a
            # silence of that length at Step 2 is what it exists to prevent.
            if spent["search"] % 50 == 0:
                _say(f"  … {spent['search']} versions of the week tried, best so far "
                     f"{cur_pair[0]} on the busiest day · {cur_pair[1]} out of the daily order")
            r = _read(trial)
            if not _best_legal(r):
                # not a worse calendar — not a calendar. Measured at 35 of 343 on round 1.
                refused += 1
                continue
            pair = _best_pair(r)
            if pair < draft_pair:
                # Only arrangements that BEAT the draft on legs 1 and 3 are eligible to be the
                # optimized calendar. Offering him a second calendar that is worse on the two
                # legs the search steers on is noise, and §5a's one-calendar case is the answer.
                pool[tuple(sorted(trial.items()))] = (pair, r)
            # TIES: score, then division name, then date. Never iteration order.
            if best_here is None or (pair, ev, dt) < best_here[0]:
                best_here = ((pair, ev, dt), r)
        if stopped != "local optimum":
            break
        if best_here is None or best_here[0][0] >= cur_pair:
            break                                   # no improving move: a local optimum
        (pair, ev, dt), _r = best_here
        current[ev], cur_pair = dt, pair
        rounds += 1
        _say(f"  round {rounds}: moved {ev} to {_console_day(dt)} — busiest day {pair[0]} · "
             f"{pair[1]} out of the daily order")

    # ⚠ WHAT "STILL IMPROVING" MEANS HERE, stated because the looser reading OVERCLAIMS and the
    # first smoke run produced exactly that: a search cut off before it had found anything at all
    # reported itself as still improving, which would put a sentence in front of the director
    # inviting him to spend more time on a search that had shown nothing. Both halves are
    # required — the search was cut short by the allowance or the build bound RATHER THAN by
    # running out of improving moves, AND it had actually found a better arrangement by then.
    # Measured on the pilot: all three rounds found an improving move, so this fires on his own
    # committed seed rather than being hypothetical.
    still_improving = stopped != "local optimum" and bool(pool)

    # ---- §2.3 option A: price leg 2 on the finalists, and let it decide among them ----------
    ranked = sorted(pool.items(), key=lambda kv: (kv[1][0], kv[0]))[:n_final]
    if ranked:
        _say(f"  pricing the courts on the best {len(ranked)} of them …")
    finalist_rows, priced = [], []
    for key, (_pair, reading) in ranked:
        # ⚠ THE ALLOWANCE IS THE OUTER BOUND, AND THE PRICING RESPECTS IT TOO. The reserve above
        # is an ESTIMATE off one measured court bill, and an estimate can undershoot: the first
        # full-allowance run measured 77 s a bill against the 70 s it had set aside and finished
        # at 11.6 minutes — inside the ruled 10-12, but by drift rather than by design. So the
        # last bills are dropped rather than allowed to run past the wait he was promised, and
        # `finalists_priced` records how many were actually bought. ALWAYS AT LEAST ONE: without
        # a priced arrangement there is no second calendar to put in front of him at all.
        if priced and _elapsed() + cb_cost > allowance:
            break
        fmap = dict(key)
        courts, _cb = _courts(fmap)
        cal = _best_calendar("optimized", fmap, reading, courts)
        finalist_rows.append({"busiest_day": dict(cal["busiest_day"]),
                              "courts_to_book": courts,
                              "out_of_order": cal["out_of_order"],
                              "finals_day": cal["finals_day"]})
        priced.append(cal)
    # D-54's order decides the winner among them; the map itself breaks a three-way tie so the
    # answer cannot depend on which finalist was priced first.
    priced.sort(key=lambda c: (_best_trio(c), tuple(sorted(c["finals_day"].items()))))
    best_cal = priced[0] if priced else None
    if best_cal is not None:
        best_cal = dict(best_cal)
        # ⚠ THE MOVES ARE READ OFF THE TWO CALENDARS, NOT OFF THE ROUNDS THE HILL-CLIMB TOOK, and
        # the smoke run is why: the winner can come out of the pool of arrangements SEEN during a
        # round that was cut off before its move was applied, and then `rounds` is 0 while the
        # calendar plainly differs — which reported "moves: []" beside a calendar that had moved a
        # division. The diff against the draft is the fact the director is owed either way.
        best_cal["moves"] = [{"event": ev, "from": draft_map[ev],
                              "to": best_cal["finals_day"][ev]}
                             for ev in sorted(draft_map)
                             if best_cal["finals_day"].get(ev) != draft_map[ev]]
        best_cal["still_improving"] = still_improving

    search = {"builds": spent["total"], "search_builds": spent["search"],
              "seconds": round(_elapsed(), 1),
              "rounds": rounds, "candidates": len(_best_candidates(need, draft_map, dates)),
              "refused": refused, "allowance_seconds": allowance,
              "max_builds": max_builds, "stopped": stopped,
              "still_improving": still_improving, "finalists_priced": len(finalist_rows)}
    calendars = [draft_cal] + ([best_cal] if best_cal is not None else [])
    out = {"calendars": calendars,
           # ⚠ ONE CALENDAR, NOT TWO, WHEN THERE IS NOTHING TO CHOOSE (§5a). Asking him to pick
           # between two identical calendars teaches him to stop reading the question.
           "choice_required": best_cal is not None,
           "wins_every_leg": None,
           "finalists": finalist_rows, "search": search,
           "sentences": _best_sentences(draft_cal, best_cal, search)}
    if best_cal is not None:
        # Said plainly when it is true — the ruling is that HE chooses, not that the tool
        # withholds what it knows. STRICTLY better on every leg, matching the sentence: a
        # calendar level on two legs has not won them, and `sentences` says the weaker thing.
        d, b = _best_trio(draft_cal), _best_trio(best_cal)
        if all(x < y for x, y in zip(b, d)):
            out["wins_every_leg"] = "optimized"
        elif all(x < y for x, y in zip(d, b)):
            out["wins_every_leg"] = "draft"
    for line in out["sentences"]:
        _say(line)
    return out


def finals_plan(setup, levels=("1", "2"), finals=None, engine_check=False, grid_events=None,
                progress=True, optimize=False, allowance=_BEST_ALLOWANCE,
                finalists=_BEST_FINALISTS, max_builds=None):
    """F7 step 2: derive the ENGINE's finals map for the TD to confirm — td-setup/v1 ->
    ingest the draws -> Pass-1 master draft -> the td-finals-plan/v1 doc the finals-map
    editor is generated from. `finals` (an earlier td-finals-map/v1) seeds pins for a
    re-edit loop; absent, the draft is the pure computed layout. Read-only; deterministic.

    FMAP-2 adds the feasibility verdict, OPT-IN and additive:

      engine_check : run the full build over the draft and attach the §13 `engine_check` block
                     (verdict + per-division day grid). DEFAULT FALSE, and the default is
                     load-bearing — with the key absent the doc is byte-for-byte what it was and
                     the generated console with it, which is what `tests/fmap2_proposal.py`
                     part D pins. It also keeps the ~9 minutes of grid grading out of every
                     caller that only wants the draft (the whole suite, among them).
      grid_events  : grade only these divisions (the harness's lever). None = the shipped depth.
      progress     : the grid states what it is doing while it runs (D4's ruling — never a
                     silent stall at runbook Step 2). False silences it.

    BEST-1 adds the September search, on exactly the same terms — OPT-IN and additive:

      optimize     : search for a better finals calendar and attach the §13 `optimized_map`
                     block — BOTH calendars (the free draft and the search's winner) with all
                     three of D-54's numbers each, so Step 2 can put them in front of the
                     director and take his choice (§5a, ruled 8/29). DEFAULT FALSE, AND THE
                     DEFAULT IS THE JANUARY PROTECTION: it is a property, not a branch — there
                     is no lane flag and no September mode, a January run simply never asks, so
                     January's bytes cannot move. With the key absent the doc and the generated
                     console are byte-for-byte what they are today, which is the same guarantee
                     `engine_check` carries and what `tests/fmap2_proposal.py` part D pins.
      allowance    : seconds for the whole search, default 660 (the ruled 10-12 minutes).
      finalists    : how many arrangements get a real court bill (§2.3 option A).
      max_builds   : bound the search by builds instead of the clock — the deterministic lever
                     a harness needs to prove the same input returns the same map twice.

    NOMAP-1 adds the other half of `engine_check=True`: if the full build REFUSES the week, this
    still returns a plan doc — the draft is desk-derived and survives — carrying `week_refusal`
    (§13) and NO `engine_check` block. The refusal never propagates out of here.

    The verdict is a read-only projection like everything else here: it runs the same
    `build_combined` lane with a map and reads the notices out. Nothing on the placement path
    changes, and the draft the console renders is not derived from it."""
    _check_setup(setup)
    slate_doc = setup.get("slate") or wwtc_slate()
    pins = _finals_pins(setup, levels, finals)          # full validated map — drives the cascade
    # DIV-1: parsed per level and then flattened — the same single pass over the PDFs
    # `_level_draws` makes, keeping which FILE each division was printed in, which is the
    # blank-tick-box derivation's whole input (rule 45).
    draws_by_level = {lvl: draws_pdf.parse_draws(level=lvl) for lvl in levels}
    draws = [d for lvl in levels for d in draws_by_level[lvl]]
    divs = MS.divisions_from_draws(draws)
    # ASSIGN-1: the draft must name the day the engine will actually schedule, or a zero-drag
    # round-trip through the editor would silently CHANGE the schedule. Same desk-derived finals
    # the default lane uses (`_master_assigned_days`); the TD's pins still outrank them.
    # ASSIGN-2 adds the round-robin half for exactly the same reason: with the RR parents left
    # off this draft, pinning it sent all 8 RR divisions back to their computed days.
    dates = slate_doc["dates"]
    # KEY-1: the same source window the build lane derives, for the same reason — a draft naming
    # days the build lane would not use is exactly what ASSIGN-1 fixed here in the first place.
    window_warn: list = []
    source_dates = _draws_window(levels, window_warn)
    anchors = _desk_finals(_desk_seed(levels, dates, draws, source_dates)[0], divs, dates,
                           skip=set(pins))
    rr_st, rr_an, _w = _rr_desk_seed(levels, dates, draws, source_dates)
    rr_parent, _stamped = _rr_parent_days({**rr_st, **rr_an}, divs,
                                          group_rounds=_rr_group_rounds(draws))
    anchors.update(_rr_parent_finals(rr_parent, divs, skip=set(pins)))
    # REVIEW-1 (D6): the finals lane resolves the same-day-finish switch exactly the way the
    # build lane does (:699-702) — before this, the board's round_day was byte-identical with
    # the switch on or off (198 cells) while the engine moved 17 (event, round) day cells, so
    # the board drew days the engine would not use. Resolution warnings ride ms.warnings into
    # plan["warnings"], which used to stay [] on a bad name.
    con = setup.get("constraints") or default_constraints()
    sdf_warn = []
    joined = _resolve_same_day_finish((con.get("same_day_finish") or {}).get("divisions"),
                                      divs, sdf_warn)
    ms = MS.build_master_schedule(divs, dates, finals_map=pins or None,
                                  finals_anchors=anchors or None,
                                  same_day_finish=joined)
    ms.warnings.extend(window_warn + sdf_warn)
    # §13: the plan's `pins` field is the TD's MOVED subset when the couriered doc carries one
    # (consistent entries only); otherwise the full applied map (an older/hand-built doc).
    sub = (finals or {}).get("pins")
    echo = ({k: v for k, v in sub.items() if pins.get(k) == v}
            if isinstance(sub, dict) and sub else pins)
    # FMAP-1 / D-32: the TD's own pacing thresholds ride into the doc so the finals map reads
    # them instead of hardcoding a twin. Before this, no cap was passed at all and `finals_plan`'s
    # 6/6 signature default stood through an entire guided run — the master chart and the finals
    # map would both have contradicted a TD who set 9 singles / 4 doubles in the Setup console.
    # (`con` resolved above, where the same-day-finish switch reads it.)
    fpd = con.get("finals_per_day") or {}
    # DIV-1 / rule 44: the finals console's division rows come out in the TD's one display
    # order, like every other surface. `finals_plan.py` is FROZEN under D-3 and the waiver
    # granted 2026-08-05 is ONE LINE wide — its sort line — so the resolved Level-1 Mixed list
    # is handed over on the master-schedule object rather than through a new parameter, which
    # would have cost a second line in the frozen file. `master_schedule` never reads it; this
    # is display only.
    ms.mixed_level_1 = _resolve_mixed_level_1(
        (con.get("mixed_level_1") or {}).get("divisions"),
        {lvl: [d.event for d in draws_by_level[lvl]] for lvl in levels}, ms.warnings)[0]
    plan = FP.finals_plan(ms, divs, tournament=slate_doc.get("tournament", ""), pins=echo,
                          cap_singles=fpd.get("singles", 6), cap_doubles=fpd.get("doubles", 6),
                          round_matches=_round_matches(draws, divs),
                          matches_per_day_target=con.get("matches_per_day_target"))
    # FMAP-2: the verdict is attached LAST and only when asked for, so `finals_plan.py` (FROZEN,
    # D-3) is not opened and the doc it builds is untouched. The key's absence is the contract's
    # compatibility guarantee (§13) — every existing consumer reads the same document it did.
    if engine_check:
        checked = _engine_check(setup, levels, plan, grid_events=grid_events, progress=progress)
        # NOMAP-1: a week the full build REFUSES has no verdict, so none is attached — the doc
        # carries `week_refusal` instead and no `engine_check` block at all. Two reasons for that
        # shape, both load-bearing:
        #   · with `engine_check` absent, `finals_guidance.render_guided_finals_console` returns
        #     the frozen plain renderer's output byte for byte, so the refused week still hands the
        #     TD his draft map editor with zero console code — the console never learns what a
        #     refused week is (CAD-1's ruled shape: the refusal is a report section, never a
        #     console state);
        #   · it cannot hand the guided renderer `held`/`day_grid` keys that honestly cannot exist.
        # The draft itself is desk-derived, not build-derived, so it survives the refusal whole:
        # a court-short September still gets its map, plus the reason the week will not hold and
        # the six remedies each already tried for real.
        if "refused" in checked:
            plan["week_refusal"] = checked["refused"]
        else:
            plan["engine_check"] = checked
    # BEST-1: the search is attached LAST and only when asked for, for the same two reasons the
    # verdict is — `finals_plan.py` (FROZEN, D-3) is not opened, and the key's ABSENCE is the
    # contract's compatibility guarantee (§13). `divs` is handed over so the search reuses the
    # one pass this function already made over the draw PDFs rather than parsing them again.
    #
    # ⚠ A REFUSED WEEK IS NOT SEARCHED. NOMAP-1's rule holds identically here: a week no legal
    # schedule can hold has no calendar worth optimizing, and every candidate would be illegal by
    # `_best_legal`, so the search would spend the director's eleven minutes proving it. He gets
    # his draft map, the reasons and the remedies — which is what that path already hands him.
    if optimize and "week_refusal" not in plan:
        plan["optimized_map"] = _best_search(setup, levels, plan, allowance=allowance,
                                             finalists=finalists, max_builds=max_builds,
                                             progress=progress, divs=divs)
    return plan


def build_from_setup(setup, levels=("1", "2"), finals=None, _probing=False):
    """CANON-2/F7: the `td-setup/v1` consumer — the function the courier hands the Setup
    console's bundle to (B-1 intact: a human still carries the JSON; nothing here reads the
    console). Splits the bundle: per-level `overrides` -> ingest · `slate` -> capacity/dates ·
    `constraints` -> TD rules. `finals` is the finals-map editor's couriered td-finals-map/v1
    (validated loudly) -> Pass-1 pins -> the R7-2 assigned-day gate; absent -> the computed
    finals-anchored layout (the TD skipped or zero-dragged the finals editor).

    NOMAP-1: `_probing` is private and additive, threaded straight to `build_combined` — default
    False, so every existing caller is byte-identical. It exists for the day grid, which needs a
    refused week to refuse CHEAPLY: the grid discards the exception, and probing six remedies to
    build one that is thrown away costs about twelve seconds per refused candidate day."""
    _check_setup(setup)
    return build_combined(levels=levels,
                          constraints_doc=setup.get("constraints") or None,
                          slate=setup.get("slate") or None,
                          overrides=setup.get("overrides") or None,
                          finals_map=_finals_pins(setup, levels, finals) or None,
                          _probing=_probing)


SETUP_DRAWS_SCHEMA = "td-setup-draws/v0-internal"

# SETUP-2 (D4). The `Dates:` header the draws print on every page — the ONE line in the whole
# export that carries a YEAR. `draws_pdf` reads these page texts already and skips this line as
# noise (`:412`); `tests/dataset_inventory.py:79` is the working prototype this is lifted from.
# Read HERE rather than in `draws_pdf`, which is brief §7's stated alternative and leaves the
# ingest untouched.
_DATES_HEADER = re.compile(r"Dates:\s*([A-Za-z]{3,9}\.? \d{1,2}, \d{4})\s*-\s*"
                           r"([A-Za-z]{3,9}\.? \d{1,2}, \d{4})")


def _header_date(token):
    """'Jan 23, 2026' / 'January 23, 2026' / 'Jan. 23, 2026' -> datetime.date. None if unreadable."""
    t = token.replace(".", "").strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    return None


def _window_from_texts(texts):
    """The tournament window from the `Dates:` header lines on a set of PAGE TEXTS.

    Split out from `dates_from_draws` on purpose: it is the only piece that touches PDF text, so
    a crafted fixture for another year is a list of strings rather than a manufactured PDF.

    Returns `(days, headers)` — `days` every ISO date from the first to the last inclusive,
    `headers` the distinct header strings seen, in first-seen order. TWO OR MORE DISTINCT HEADERS
    ARE WIDENED TO THEIR UNION AND ALL OF THEM ARE RETURNED, never silently reconciled: two draws
    files disagreeing about the tournament's own dates is a fact the director has to see.
    """
    seen, lo, hi = [], None, None
    for txt in texts or []:
        m = _DATES_HEADER.search(txt or "")
        if not m:
            continue
        raw = f"{m.group(1)} - {m.group(2)}"
        a, b = _header_date(m.group(1)), _header_date(m.group(2))
        if a is None or b is None or b < a:
            continue
        if raw not in seen:
            seen.append(raw)
        lo = a if lo is None or a < lo else lo
        hi = b if hi is None or b > hi else hi
    if lo is None:
        return [], seen
    days, one = [], datetime.timedelta(days=1)
    d = lo
    while d <= hi:
        days.append(d.isoformat())
        d += one
    return days, seen


def _venue_days_from_stamps(draws, window):
    """{venue -> [ISO day, ...]} from the desk's own schedule stamps, plus what did not resolve.

    A stamp is `{"date": "Jan 24", "time": …, "venue": "MHCC"}` — VERBATIM PDF tokens carrying NO
    YEAR (`draws_pdf.DivisionDraw`), which is why the window has to come from the header line and
    the year is then read off it: a stamp resolves to the one day in the window with that month
    and day. A token matching no window day is RECORDED, never guessed at.
    """
    bymd = {}
    for iso in window:
        d = datetime.date.fromisoformat(iso)
        bymd.setdefault((d.month, d.day), iso)
    out, unmatched, dated, blank = {}, [], 0, 0
    for dd in draws or []:
        stamps = list(dd.r1_stamps.values())
        for mm in dd.later_stamps.values():
            stamps += list(mm.values())
        for g in dd.groups:
            stamps += list(g.stamps)
        for st in stamps:
            if st is None:                       # the page printed 'Not scheduled'
                blank += 1
                continue
            date, venue = st.get("date"), st.get("venue")
            if not date or not venue:
                continue
            key = _header_date(f"{date}, 2000")  # year is a throwaway; only (month, day) is read
            iso = bymd.get((key.month, key.day)) if key else None
            if iso is None:
                if date not in unmatched:
                    unmatched.append(date)
                continue
            dated += 1
            out.setdefault(venue, set()).add(iso)
    return ({v: sorted(d) for v, d in sorted(out.items())}, unmatched,
            {"dated": dated, "not_scheduled": blank})


def dates_from_draws(draws=None, texts=None, levels=(1, 2), main_site=None) -> dict:
    """SETUP-2 (run report D4): the tournament window and the per-venue days, DERIVED from the
    director's own draws — the tool has read them before the Setup console renders.

    THIS IS A PREFILL HE CONFIRMS, NEVER A FIGURE THE TOOL ASSERTS (rule 8's precedent), and the
    2026 field is the standing proof it must stay one: measured 2026-08-09, the derivation and the
    committed slate DISAGREE ON TWO OF THREE VENUES, in both directions.
      · MHCC — NO match is stamped on Feb 1, so the stamps alone can never yield the slate's 10th
        day. A day nobody plays on is invisible to this derivation.
      · WEST — the desk's own autoschedule stamps 2 matches at WEST on Jan 31 (both L2 Mixed 30 &
        over doubles semifinals, 3:30 PM), a venue-day the committed slate does not open. The
        derivation is not wrong about the draws; the desk and the slate disagree.
    The WINDOW identity holds exactly (via the header line, `Jan 23, 2026 - Feb 1, 2026` on 72 of
    72 pages ≡ the slate's 10 days). The per-venue identity holds on 1 of 3 venues (ORLP).

    WHAT `venues` CARRIES, and why it is not `derived` (Operator ruling, 2026-08-09 — option 2).
    `derived` is the pure stamp derivation, reported unretouched. `venues` is the PREFILL, and it
    adds one repair: **a day inside the printed window that no venue is stamped open on is opened
    at the main site** (`window_only_days` names every such day, and `main_site` names where they
    went). Measured why this is not cosmetic: the console builds the tournament window out of the
    union of the venue days (`setup_console.html:511`), so prefilling the raw 9/3/3 hands back a
    NINE-day tournament, and on the 2026 field that leaves **2 matches unplaced — the Men's 35 &
    over doubles final and the Women's 50 & over doubles final, both scheduled Feb 1** (760 -> 758
    placed, spills 5 -> 30). With the repair: 760 placed, 0 unplaced, 0 conflicts, spill anchor
    still 5, and 7 of 760 rows shift — 2 of them onto the WEST Jan-31 the desk itself used.

    `main_site` defaults to the venue with the MOST stamped days (ties by venue id, so it is
    deterministic); pass it to override. On the 2026 field that is MHCC at 9 days, which is also
    the slate's rank-1 venue — rule 43's main site — but this derives it rather than assuming it.

    Reads the PARSED draws for the stamps and the page texts for the header only; `draws_pdf` is
    untouched. `texts`/`draws` are injectable so a fixture for another year is pure python.
    """
    if draws is None or texts is None:
        import pypdfium2 as pdfium
        pdraws, ptexts = [], []
        for lvl in levels:
            path = draws_pdf.resolve_draws_pdf(level=lvl)
            if texts is None:
                ptexts += draws_pdf._page_texts(pdfium.PdfDocument(path))
            if draws is None:
                pdraws += draws_pdf.parse_draws(path)
        draws = pdraws if draws is None else draws
        texts = ptexts if texts is None else texts

    window, headers = _window_from_texts(texts)
    derived, unmatched, counts = _venue_days_from_stamps(draws, window)

    site = main_site
    if site is None and derived:
        site = sorted(derived, key=lambda v: (-len(derived[v]), v))[0]
    covered = {d for days in derived.values() for d in days}
    gaps = [d for d in window if d not in covered]

    venues = {v: list(days) for v, days in derived.items()}
    if gaps and site:
        venues[site] = sorted(set(venues.get(site, [])) | set(gaps))

    return {"window": window, "headers": headers, "venues": venues, "derived": derived,
            "main_site": site, "window_only_days": gaps, "unmatched_stamp_dates": unmatched,
            "counts": counts}


def render_setup_console(template_path=None, divisions=None, mixed_level_1=None,
                         dates=None, venues=None, setup=None) -> str:
    """CONS-1 (A7b): the Setup console as a GENERATED artifact — runbook Step 1 becomes
    generate-then-publish, the shape Steps 2 and 5 already have.

    Why the order could change at all: reading the draws needs NOTHING from setup
    (`parse_draws(level=n)` resolves its own PDF) and costs 0.143s for both levels. So the run
    can read the director's own printed draws BEFORE he sees the console, and the two division
    questions stop being "type a name" — a field asking him to type a division name one step
    before the tool has read any — and become "pick from your own draws".

    RENDERER ONLY. It reads the draws and substitutes a template slot; it computes nothing the
    engine reads and moves no contract. The emitted `td-setup/v1` document is byte-identical
    whether the console was generated or opened raw (setup_console_golden part K).

    `setup_console.html` (next to this module) is the template: its single embedded
    `var DRAWS = …;` line — the generation slot — is replaced with the parsed division names.
    THE SHIPPED FILE IS THE TEMPLATE, edited in place and never regenerated from an older copy:
    it carries LANG-1/A7c's 19 ruled strings, and regenerating would silently undo them.
    Deterministic: same draws, same template -> same HTML. The `render_editor_console` precedent
    (editor_plan.py), including the `</`-escape and the exactly-one-slot guard — which matters
    more here, because the template declares `var SAMPLE` twice and a copied SAMPLE regex would
    match both.

    `divisions`/`mixed_level_1` are for tests and for a caller that has already parsed; the
    default reads both levels.

    SETUP-2 (D4): `dates` is a SECOND generation slot, `var DATES = …;`, carrying what
    `dates_from_draws()` derived — the tournament window and the per-venue days. The console's day
    model was three hardcoded 2026 literals, and the 2027 mock run honoured "set the venue days to
    2027" only by PATCHING THE GENERATED HTML at run time: three string replacements on the run
    surface, exactly the edit CONS-1's contract tells a run not to make. Filling this slot retires
    that patch.

    **NO `dates` ARGUMENT -> TODAY'S SAMPLE BLOCK, VERBATIM.** The slot stays `null` and the SAMPLE
    IIFE falls through to its own literals, character for character, so the console behaves exactly
    as it did before this build. (The rendered HTML is NOT byte-identical to the pre-SETUP-2 file —
    it carries the new slot and the three edited strings; what is byte-identical is the EMITTED
    `td-setup/v1`.) That is the fallback lane the byte-identity rides — stated
    here because brief §4 leaves the choice to the build: `setup_console_golden` part K drives
    BOTH lanes bare (`_console_path("generated")` calls this with no `dates`), so the pinned emit
    is unmoved by construction rather than by re-pinning, and `tests/venue1_rules.py`'s
    field-for-field transcription of the SAMPLE keeps agreeing with the file.

    S-1 §1-C: `venues` is a THIRD generation slot, `var VENUES = …;`, carrying next January's
    clubs — `{"locations": [...], "transit_minutes": {...}}`, where each location has the shape
    the console's own SAMPLE already uses (`id`, `name`, `available` per day with `courts`/
    `start`/`end`, and optionally `lit_courts`/`lights_on`/`physical_courts`), so the console's
    loader needs no new model. In September the only draws in existence are last January's and
    the workbook carries divisions rather than venues, so without this the director retypes five
    clubs' courts, hours and lights by hand — 40 editable inputs on the shipped three-club
    prefill, and a five-club slate scales it directly.

    ⚠ THE SEED'S SOURCE IS THE RUN'S OWN ELICITATION, NEVER A FILE. The run asks him in plain
    words and passes the answer here. **Patching the generated HTML is the forbidden door** — the
    same one the 2027 mock took with its three string replacements, named above. And it is a
    PREFILL HE CONFIRMS, never a figure the tool asserts (rule 8): Step 1's readback says read
    and check, exactly as it does for the dates.

    **NO `venues` ARGUMENT -> TODAY'S SAMPLE BLOCK, VERBATIM**, on the `dates` lane's terms: the
    slot stays `null` and the SAMPLE falls through to its own literals character for character,
    so the emitted `td-setup/v1` is unmoved. `setup_console_golden` part K drives both lanes bare,
    so that holds by construction rather than by re-pinning, and `tests/venue1_rules.py`'s
    field-for-field transcription of the SAMPLE keeps agreeing with the file.

    S-6 §1-B: `setup` is a FOURTH generation slot, `var SETUP = …;`, and it is the only one that
    carries a WHOLE DOCUMENT — a complete `td-setup/v1` with `slate`, `constraints` and
    `added_divisions`. The console opens on it: the boot block at the end of its script hands a
    non-null slot to `loadDocument()`, the same function the paste-back panel calls, which is why
    this needs no new model on either side.

    WHY A FOURTH SLOT RATHER THAN A FOURTH FIELD. `venues=` carries the clubs, `dates=` the days;
    the Operator's own committed 2027 answers carry his RULES and the six divisions he is adding
    next year as well, and there was no slot for either. Measured on the seed as committed before
    this build: a bare venues-shaped file that reached the run through `venues=`, so his rules and
    his six divisions never arrived at all — the 2026-08-25 run planned 50 divisions against a
    real 56 and reported `0 added`.

    **`venues=` STAYS.** It is not superseded: `tests/venue1_rules.py` transcribes the SAMPLE
    field for field through it and S-1 §1-C's lane still uses it. A caller that has only clubs
    passes `venues=`; a caller holding the whole answer passes `setup=`.

    **NO `setup` ARGUMENT -> THE SLOT STAYS `null` AND THE BOOT BLOCK DOES NOTHING**, on the two
    lanes above's exact terms, so the console behaves as it did before this build and the emitted
    `td-setup/v1` is byte-identical. `setup_console_golden` part K drives both lanes bare.

    ⚠ AND IT IS STILL A PREFILL HE CONFIRMS, NEVER A FIGURE THE TOOL ASSERTS (rule 8). Everything
    the seed carries is on screen and overwritable, and Step 1's readback still says read and
    check. Patching the generated HTML remains the forbidden door.

    THE BACKSTOP (ruling 8.2 / brief §3.7). A scan-like PDF errors nowhere: `_page_texts` returns
    `['']`, `_event_of` returns None, and every page becomes a `__page{i}` pseudo-division
    (draws_pdf.py:454). Unchecked, `__page0` would reach the picker as a division name. This
    refuses a pseudo-name or an empty list and names the materials check, so garbage cannot reach
    the director even on a run that skipped it — two independent doors, either one stops it.
    """
    import json
    import os
    import re

    if divisions is None:
        l1 = [d.event for d in draws_pdf.parse_draws(level=1)]
        l2 = [d.event for d in draws_pdf.parse_draws(level=2)]
        divisions = l1 + l2
        if mixed_level_1 is None:
            mixed_level_1 = l1
    divisions = list(divisions)
    mixed_level_1 = list(mixed_level_1 or [])

    bad = [n for n in divisions if not n or str(n).startswith("__page")]
    if bad or not divisions:
        raise ValueError(
            f"refusing to build a Setup console from an unusable division list "
            f"({'no divisions were parsed' if not divisions else f'pseudo-names {bad[:4]}'}). "
            f"A PDF with no text layer parses 'successfully' into __page pseudo-divisions — run "
            f"the materials check (preflight.materials_check) and re-export the draws from "
            f"Tournament Desk as a PDF rather than a scan.")

    path = template_path or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "setup_console.html")
    with open(path, encoding="utf-8") as fh:
        template = fh.read()
    payload = json.dumps({"schema": SETUP_DRAWS_SCHEMA,
                          "divisions": divisions,
                          "mixed_level_1": mixed_level_1}).replace("</", "<\\/")
    html, n = re.subn(r"^(\s*var DRAWS = ).*;$",
                      lambda m: m.group(1) + payload + ";",
                      template, flags=re.MULTILINE)
    if n != 1:
        raise ValueError(f"template {os.path.basename(path)}: expected exactly one "
                         f"'var DRAWS = …;' generation slot, found {n}")

    # SETUP-2: the dates slot. Untouched when no `dates` is supplied — see the fallback-lane note
    # in the docstring. The exactly-one-slot guard is the DRAWS one, for the same reason.
    if dates:
        dpayload = json.dumps(dates, sort_keys=True).replace("</", "<\\/")
        html, n = re.subn(r"^(\s*var DATES = ).*;$",
                          lambda m: m.group(1) + dpayload + ";",
                          html, flags=re.MULTILINE)
        if n != 1:
            raise ValueError(f"template {os.path.basename(path)}: expected exactly one "
                             f"'var DATES = …;' generation slot, found {n}")

    # S-1 §1-C: the venues slot. Untouched when no `venues` is supplied — the SAMPLE's own
    # literals stand. Same exactly-one-slot guard and same `</` escape, for the same reasons.
    if venues:
        vpayload = json.dumps(venues, sort_keys=True).replace("</", "<\\/")
        html, n = re.subn(r"^(\s*var VENUES = ).*;$",
                          lambda m: m.group(1) + vpayload + ";",
                          html, flags=re.MULTILINE)
        if n != 1:
            raise ValueError(f"template {os.path.basename(path)}: expected exactly one "
                             f"'var VENUES = …;' generation slot, found {n}")

    # S-6 §1-B: the setup slot — a whole `td-setup/v1`. Untouched when no `setup` is supplied, so
    # the console falls through to the SAMPLE exactly as it does for the three above. Same `</`
    # escape and same exactly-one-slot guard, for the same reasons.
    # `sort_keys` is NOT used here, unlike `dates` and `venues`: this document is the director's
    # own answer and `added_divisions` is an ordered list whose ROW order he set. Sorting keys
    # would not touch that order, but the document is handed back to him to read, and a block
    # whose keys have been rearranged reads as a block the tool rewrote.
    if setup:
        spayload = json.dumps(setup).replace("</", "<\\/")
        html, n = re.subn(r"^(\s*var SETUP = ).*;$",
                          lambda m: m.group(1) + spayload + ";",
                          html, flags=re.MULTILINE)
        if n != 1:
            raise ValueError(f"template {os.path.basename(path)}: expected exactly one "
                             f"'var SETUP = …;' generation slot, found {n}")
    return html


def editor_plan_for(level="2", day=None, **kw):
    """`td-editor-plan/v1` for the Edit console. day=None -> whole schedule; day="first" -> the
    first scheduled day (the first-day board); day="2026-01-23" -> that day."""
    b = build(level, **kw)
    plan = EP.editor_plan(b["result"], b["cfg"], events=b["events"],
                          constraints_doc=b["doc"], local_players=b["cfg"].local_players,
                          non_drawn=b["non_drawn"],
                          master_warnings=b.get("master_warnings"),   # CUI-2: into the warning bar
                          seeds=b.get("seeds"),                       # EC-F2: seed flags on cards
                          roster=b["players"])                        # CUI-3: per-player card facts
    if day in (None, "all"):
        return plan
    target = plan["days"][0] if day == "first" else day
    keep = [p for p in plan["placements"] if p["day"] == target]
    names = {n for p in keep for n in p["players"]}
    return dict(plan, days=[target], placements=keep,
                divisions=[d for d in plan["divisions"]
                           if any(p["div"] == d["name"] for p in keep)],
                locals=sorted(n for n in plan.get("locals", []) if n in names),
                # CUI-3: `players` narrows with `locals` — the board only ever looks up a name it
                # is showing, and the day board should not carry the whole field's facts.
                players={n: v for n, v in (plan.get("players") or {}).items() if n in names})


def _selftest():
    plan = editor_plan_for(level="2", day="first")
    d1 = plan["days"][0]
    from collections import Counter
    ven = Counter(p["location"] for p in plan["placements"])
    print(f"first-day board {d1}: {len(plan['placements'])} matches, "
          f"{len(plan['divisions'])} divisions, venues {dict(ven)}, {len(plan['locals'])} locals")
    assert plan["schema"] == "td-editor-plan/v1" and plan["placements"], "bad plan"
    full = build(level="2")["result"]
    assert len(full["unplaced"]) == 0 and len(full["conflicts"]) == 0, "pipeline not 0/0"
    print("wwtc_pipeline self-test OK")


if __name__ == "__main__":
    _selftest()
