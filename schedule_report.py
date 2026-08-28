"""RPT-1 — the pre-publication schedule reporter.

The tool's ruled posture is **reporter first** (D2a): before anything is published, audit the
schedule the desk produced — and the TD's couriered edits to it — against the measured rule set,
and say precisely what breaks and for whom. 2026's shipped schedule contained sub-3-hour
turnarounds it took a nine-file retrospective to find, and no instrument existed to catch any of
it before print. This module is that instrument.

Read-only, and deliberately decoupled: nothing here imports the engine, and the engine imports
nothing here. Input is an ingested schedule (`draws_pdf.DivisionDraw` + the ING-1 stamps) plus the
level player lists; output is a `td-report/v1` document and a text render of it. The courier moves
the file — the reporter never talks to a console (B-1).

WHAT THE REPORTER CAN SEE, AND WHY IT MATTERS
---------------------------------------------
A published elimination draw names its round-1 entrants. It does not name the player who will
appear in a quarterfinal, because that depends on who wins. So a *pre-publication* audit can only
speak about commitments that are certain at publication time:

  * every round-1 match (both entrants named), and
  * any later-round match a side reaches by BYE — formally, a side is certain exactly when its
    feeding sub-bracket holds a single non-bye slot (`_certain_side`).

That is the "first match" plane BENCH-1 measured (276 of 756 entrants first play via a bye) and a
little more. It is strictly smaller than the retrospective plane the 2026 nine-file analysis used,
which knew every round's players *because the tournament had already been played*. The gap is
structural, not a coverage bug: the retrospective figures are not reachable from a pre-publication
input, and `check_*` therefore reports what the TD can actually be warned about before print.

`report()` takes a schedule, not files, so a caller holding a fully-resolved schedule (a bench
fixture reproducing a historical finding, a future results-aware surface) can hand one over and
get the same checks applied. Provenance travels in `source`.

DETERMINISM
-----------
Same input, same bytes — **across processes, not just within one**. Every finding is sorted
`(code, day, division, players)`; every count derives from the sorted finding list; and every sort
key that can reach the output is TOTAL. That last clause is the one that bit: a set of round labels
sorted on draw size alone ties for every label outside `LABEL_SIZE` (consolation, round-robin), and
a tie over a set resolves in hash order, so the document's bytes tracked `PYTHONHASHSEED`. Sorting
a set is fine; sorting it on a non-total key is not. `tests/rpt1_report.py` guards this with a
multi-seed subprocess run, because a same-process comparison cannot detect it.
"""
from __future__ import annotations

import dataclasses
import itertools
import json
import os
import re
from dataclasses import dataclass, field
from typing import Optional

import constraints as C
import division_order as DO       # DIV-1: rule 44's one display order (display only)
import draws_pdf
import wwtc_ingest as WI

SCHEMA = "td-report/v1"

SEVERITIES = ("breach", "warn", "info")

# The check set (RPT-1 §9). Order here is the report's presentation order.
# HOLDVIS-1 (ruling 4, 2026-08-07): `HELD` is APPENDED, so the ten existing sections come out in
# exactly the order they always did and the new one reads last.
# GENDER-1 (2026-08-08): `MIXED-GENDER` is APPENDED for the same reason — the eleven existing
# sections come out in exactly the order they always did. It is a must-fix, and the printed page
# leads with the severity counts, so appending costs it no prominence.
# RPT-2 (A5c, 2026-08-09): `CONFLICTS` is APPENDED, third time, same reason. It is the only rung
# here that GRADES NOTHING — it carries the engine's own `result["conflicts"]` record verbatim,
# and it reads last because it is a record of decisions already taken rather than a check.
CODES = ("REST-XLEVEL", "BAND-3EV", "FLOOR-80", "CADENCE", "VENUE-LATE",
         "FINALS-UNSET", "CAP-SLATE", "START-WINDOW", "SAMETYPE-WATCH", "SEED-COUNT",
         "HELD", "MIXED-GENDER", "CONFLICTS")

_HHMM = re.compile(r"^(\d{1,2}):(\d{2})$")


def _hhmm_minutes(v):
    """'HH:MM' -> minutes from midnight, or None. The couriered docs speak 'HH:MM'; this config
    counts minutes. D-22 reads every threshold through here so one parse rule serves them all."""
    if not isinstance(v, str):
        return None
    m = _HHMM.match(v.strip())
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None

_MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
           "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
_TIME = re.compile(r"^(\d{1,2}):(\d{2})\s*([AP]M)$")

# Round labels reach the reporter in two spellings: `draws_pdf`'s long form ("Semifinals") and the
# short form the match report prints ("SF"). Any check that reasons about WHICH round a match is
# must canonicalise first, or it silently answers "no" for one of the two callers — which is how
# the closing-day cadence exception and the semifinal/final venue rule both went dead on the bench
# plane while the product plane scored them correctly. Consolation ("V-QF", "PL-F") and
# round-robin ("Round 1") labels have no canonical form and pass through unchanged, which is
# correct: neither is a main-draw round.
_ROUND_ALIAS = {"F": "Final", "SF": "Semifinals", "QF": "Quarterfinals"}
_LATE_ROUNDS = ("Semifinals", "Final")
# Round-robin group play carries no round label in the source grid, so it gets one of its own
# rather than borrowing a bracket label it would then be scored against.
RR_ROUND = "RR"


def canonical_round(label: str) -> str:
    return _ROUND_ALIAS.get(label, label)


def _round_rank(label: str) -> tuple:
    """Sort key for a round label: biggest draw first, then the label itself.

    The label tiebreak is load-bearing, not cosmetic. `LABEL_SIZE` knows only the eight main-draw
    labels, so every consolation and round-robin label scored 0 and tied — and a tie over a SET
    resolves in hash order, which changes between processes. That put a hash-seed-dependent list
    into `measured["rounds"]` and broke the module's determinism guarantee in the one place a
    same-process comparison could never catch.
    """
    return (-draws_pdf.LABEL_SIZE.get(canonical_round(label), 0), label)


# --------------------------------------------------------------------------
# INPUT MODEL
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ScheduledMatch:
    """One stamped match on the schedule under audit.

    `sides` holds two entries, one per side of the draw: a sorted list of USTA IDs when that side
    is certain at publication time, or None when it is not (an undecided feeder). A match with one
    certain side is still a real commitment for that side's players and is audited as such.

    `courts` is how many courts this record occupies — 1 for a normal match. It exists for the one
    case where the source names everybody on court at a moment but not who is playing whom: a
    round-robin group whose whole membership shares a slot (see `rr_matches`). Rather than invent
    a pairing to make the record look ordinary, that slot is one record holding every player, with
    `courts` set to the number of matches actually running. Every per-player check is exact
    because each player still has exactly one commitment at that time; venue load is exact because
    it counts `courts`; and no finding claims two people are opponents when the source never said
    so.
    """
    event: str
    level: str                       # "1" | "2"
    round_label: str
    match_index: int
    day: str                         # "YYYY-MM-DD"
    start: int                       # minutes from midnight
    venue: Optional[str]
    sides: tuple = ((), ())          # (tuple[str] | None, tuple[str] | None)
    courts: int = 1

    @property
    def mid(self) -> str:
        return f"{self.event}|{self.round_label}|{self.match_index}"

    @property
    def players(self) -> tuple:
        out = []
        for s in self.sides:
            if s:
                out.extend(s)
        return tuple(sorted(set(out)))

    @property
    def fully_known(self) -> bool:
        return all(s is not None for s in self.sides)


@dataclass
class ReportConfig:
    """Check parameters, at the ruled defaults.

    Every value here is either a ruling or a measurement, cited at its field. TD packet answers
    Q2 (cadence wording), Q6 (rest-vs-floor precedence) and Q7 (per-venue lit counts) re-
    parameterise three of them when they land; per §13 the checks ship with the defaults now.
    """
    # R1 / §8A row 1 — TD's 3h start-to-start, the measured rule.
    min_start_to_start: int = 180
    # D-40 / ruling 67 — the TD's OWN band times, replacing D1a/D1b's sent recommendation:
    # three-event players at 9:00 / 12:00 / 15:00, and every one read "at or EARLIER". The
    # slide-early variant DIES with the recommendation it came from — nothing watches the 15:00
    # window fill, so there was never anything to slide against. `band_slide_offsets` is retained
    # at (0,) so the scoring loop keeps its shape; it is no longer a variant, it is the identity.
    band_singles_by: int = 9 * 60
    band_mixed_at: int = 12 * 60
    band_doubles_from: int = 15 * 60
    band_slide_offsets: tuple = (0,)
    # AVOID-3 — the per-division earliest-start floor the engine enforces at placement.
    floor_age_min: int = 80
    floor_before: int = 9 * 60 + 30
    # V-2 / V-3 / F-1 / DM-2 — the main host site. VENUE-1 (2026-08-05): when a slate is
    # couriered this is DERIVED from it — the director's rank-1 venue, `locations[0]` — because
    # "main site" is a position in his own venue list, not the string "MHCC". The literal
    # survives only as the no-slate fallback.
    main_site: str = "MHCC"
    # VENUE-1 / rule 41 — the placements the engine could not seat inside a venue rule and so
    # PLACED AND RECORDED. (mid, day, "HH:MM", venue). The reporter tolerates exactly these, so a
    # legal recorded fallback is never graded as a breach; it is surfaced as an `info` instead.
    # Passed in beside the schedule like `mixed_level_1` is — `td-report/v1` gains no field.
    venue_escapes: frozenset = frozenset()
    # D8 — the MEASURED slate peaks (20/12/4), not the configured 24/20/4.
    slate_capacity: dict = field(default_factory=lambda: {"MHCC": 20, "ORLP": 12, "WEST": 4})
    # (venue, date) -> courts, when the couriered slate names them per day. Falls back to
    # `slate_capacity` for a day the slate does not cover; empty => venue-wide only, as before.
    slate_capacity_by_day: dict = field(default_factory=dict)
    # SLATE-1 / D-10 — the per-venue lit-court ceiling. ORLP/WEST blank pending TD Q7.
    #
    # D-10 was recorded as "move 15:30 to 16:00", and it is NOT a one-number swap. The reporter
    # carried ONE GLOBAL hour while the console models lights PER VENUE (`lights_on` per location,
    # SLATE-1, `setup_console.html:1236`). Swapping the constant would have left the two models
    # still disagreeing — the next venue with its own lights-on hour would re-open the same gap.
    # `lights_from` is therefore a DICT keyed the same way `lit_courts` is, so a venue's ceiling
    # and the hour it starts travel together, exactly as they do on the slate the TD couriers.
    lit_courts: dict = field(default_factory=lambda: {"MHCC": 7})
    lights_from: dict = field(default_factory=lambda: {"MHCC": 16 * 60})
    # ENG-1 / ruling 72 — the same-day-finish exception, so the reporter does not grade a pair the
    # engine placed BY RULE as the highest-severity breach it can emit. `{division: gap_minutes}`;
    # empty => the flat floor everywhere, as before. Read from `same_day_finish` by
    # `from_constraints`, because a reporter re-pointed at the TD's numbers has to read all of
    # them — a rule and its one named exception are the same number.
    same_day_finish: dict = field(default_factory=dict)
    # D-37 / ruling 65 — the late-afternoon catch-up window. Counts STARTS in [15:00, 16:00)
    # against 9. A DIFFERENT quantity from the lit-court check above, which counts matches ON
    # COURT after the lights go on. WARNS, never enforces.
    start_window: tuple = (15 * 60, 16 * 60)
    start_window_max: int = 9
    # §8 — uniform 90-minute block; concurrency is measured over it.
    match_minutes: int = 90
    # Compressed (opening / closing) days are gap-checked directly instead of band-checked —
    # the named exception in D1a. Empty => derived as the first and last day on the schedule.
    compressed_days: tuple = ()
    # DIV-1 / rule 45 — the RESOLVED Level-1 Mixed divisions for this run, which is the one
    # input rule 44's display order cannot derive from a division's name. Not a threshold and
    # nothing is graded against it: it only sets where the Mixed divisions sit in the division
    # lists this report prints. Empty => every Mixed division sorts into the Level-2 block.
    mixed_level_1: tuple = ()

    @classmethod
    def from_constraints(cls, doc, slate=None, **overrides):
        """A ReportConfig that grades against the TD's numbers instead of its own — D-22.

        WIRE-1 opened this seam for `match_minutes` alone and said the other four private
        thresholds were ENG-1's. This is ENG-1 closing it. Every threshold the report checks or
        prints now comes from the couriered docs:

          `min_start_to_start_minutes`  -> min_start_to_start   (was a private 180)
          `day_bands`                   -> the three band times (was a private 9:30/12:30/15:30)
          `earliest_start_by_age`       -> floor_age_min / floor_before   (was a private 80 / 9:30)
          slate `locations[].available` -> slate_capacity       (was a private 20/12/4)
          slate `locations[].lit_courts`/`lights_on` -> lit_courts / lights_from  (D-10)

        Why it mattered, precisely: on the fixture lane the engine may place up to the slate's
        configured MHCC 24 while the reporter judged against its private 20, so 12 of 15
        venue-days carried a CAP-SLATE finding. Neither file was wrong — ruling 28 holds the
        fixture at 24/20/4 by design and the reporter's 20/12/4 mirrored the console prefill — but
        a reporter with private copies grades whatever it is given against numbers it was not
        given. After this re-point the reporter follows the slate it is handed.

        Every read is defaulted, so a doc (or slate) that omits a field keeps the ruled default,
        and `from_constraints(None)` is exactly `ReportConfig()`. Explicit `overrides` always win.
        """
        doc = doc or {}
        mm = doc.get("match_minutes")
        if mm is not None:
            overrides.setdefault("match_minutes", mm)
        s2s = doc.get("min_start_to_start_minutes")
        if s2s is not None:
            overrides.setdefault("min_start_to_start", s2s)
        bands = doc.get("day_bands") or {}
        for key, fieldname in (("singles_by", "band_singles_by"), ("mixed_at", "band_mixed_at"),
                               ("doubles_from", "band_doubles_from")):
            v = _hhmm_minutes(bands.get(key))
            if v is not None:
                overrides.setdefault(fieldname, v)
        # AVOID-3's ladder is a list of {age_min, earliest}; the report checks ONE floor, so the
        # oldest rule wins — the same "highest matching age_min" precedence apply_constraints uses.
        # The LOWEST rung, not the highest: `check_floor_80` tests `age >= floor_age_min`, so
        # taking the oldest rule would stop reporting every division between the youngest rung and
        # it — the engine still floors those. `age_min` is validated here rather than indexed,
        # because `report(constraints=...)` never runs `validate_constraints` and a rule without
        # it used to raise KeyError out of report generation.
        rules = [r for r in (doc.get("earliest_start_by_age") or [])
                 if isinstance(r, dict) and _hhmm_minutes(r.get("earliest")) is not None
                 and isinstance(r.get("age_min"), int) and not isinstance(r["age_min"], bool)]
        if rules:
            low = min(rules, key=lambda r: r["age_min"])
            overrides.setdefault("floor_age_min", low["age_min"])
            overrides.setdefault("floor_before", _hhmm_minutes(low["earliest"]))
        sdf = doc.get("same_day_finish") or {}
        divs = [d for d in (sdf.get("divisions") or []) if isinstance(d, str) and d.strip()]
        if divs:
            gap = sdf.get("gap_minutes")
            gap = gap if isinstance(gap, int) and not isinstance(gap, bool) and gap > 0 else 150
            overrides.setdefault("same_day_finish", {d: gap for d in divs})
        if slate:
            capacity, lit, lights, per_day = {}, {}, {}, {}
            for loc in slate.get("locations") or []:
                lid = loc.get("id")
                if not lid:
                    continue
                courts = []
                for date, d in (loc.get("available") or {}).items():
                    if not isinstance(d, dict) or d.get("courts") is None:
                        continue          # a malformed cell is skipped, never crashed on
                    courts.append(d["courts"])
                    per_day[(lid, date)] = d["courts"]
                if courts:
                    # `max` is the venue-wide fallback for a day the slate does not name; the
                    # per-(venue, day) map below is what `check_cap_slate` actually grades against,
                    # because a venue that steps down from 24 courts to 8 on the closing day would
                    # otherwise have that day judged against 24 — blind to the one day most likely
                    # to be over.
                    capacity[lid] = max(courts)
                lc, lo = loc.get("lit_courts"), _hhmm_minutes(loc.get("lights_on"))
                if lc is not None and lo is not None:      # SLATE-1: both-or-neither
                    lit[lid] = lc
                    lights[lid] = lo
            # VENUE-1 / rule 43: the director's rank-1 venue IS the main site, and the slate's
            # `locations` order is his ranking. Taken from the first location that has an id, so a
            # half-typed row cannot silently promote the second venue.
            for loc in slate.get("locations") or []:
                if loc.get("id"):
                    overrides.setdefault("main_site", loc["id"])
                    break
            if capacity:
                overrides.setdefault("slate_capacity", capacity)
                overrides.setdefault("slate_capacity_by_day", per_day)
            if lit:
                overrides.setdefault("lit_courts", lit)
                overrides.setdefault("lights_from", lights)
        return cls(**overrides)


def parse_stamp(stamp: dict, year: int = 2026) -> tuple:
    """An ING-1 stamp's verbatim tokens -> ("YYYY-MM-DD", minutes-from-midnight, venue).

    `draws_pdf` deliberately leaves normalisation to the consumer, so it happens here — once.
    Raises ValueError on a token shape the parser never produces, rather than guessing: a stamp
    that cannot be normalised must not become a silently-dropped match.
    """
    mon, day = str(stamp["date"]).split()
    m = _TIME.match(str(stamp["time"]).strip())
    if mon not in _MONTHS or not m:
        raise ValueError(f"unparseable schedule stamp: {stamp!r}")
    hh = int(m.group(1)) % 12 + (12 if m.group(3) == "PM" else 0)
    return f"{year}-{_MONTHS[mon]:02d}-{int(day):02d}", hh * 60 + int(m.group(2)), stamp["venue"]


def hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


# --------------------------------------------------------------------------
# ROSTER — identity is ALWAYS the roster join, never a surname match
# --------------------------------------------------------------------------
def full_roster(levels=("1", "2")) -> dict:
    """Union of the levels' player records, keyed by USTA ID — one record per human.

    `events` is MERGED across levels. A plain `dict.update()` (what `wwtc_pipeline.build_combined`
    did) replaces the L1 record with the L2 one for the 84 people entered at both levels and takes
    their L1 events with it, which blinds `resolve_draws` in exactly the four L1 Mixed divisions.

    **ROSTER-1 (2026-07-31) fixed the root cause and this now delegates to it** — as this
    docstring asked it to. `wwtc_ingest.load_players_combined` is the one union; the local repair
    that stood here and in `avoidance.full_roster` is gone rather than left standing beside it.
    """
    return WI.load_players_combined(levels)


def _name_of(roster: dict, pid: str) -> str:
    """Full name for a USTA ID via the roster join. An unresolved ID surfaces as itself rather
    than being dropped — a finding must never lose the person it is about."""
    p = roster.get(pid)
    return p.name if p is not None else str(pid)


def _names(roster: dict, pids) -> list:
    return sorted(_name_of(roster, p) for p in pids)


# --------------------------------------------------------------------------
# THE ENGINE-RESULT -> REPORTER ADAPTER  (CUI-5, §15 D4 option 1)
# --------------------------------------------------------------------------
# ONE adapter, shipped here, so the guided run's pre-publication step and the harness that
# grades it project the engine's result the same way. Two adapters drifting apart is CARD-1's
# two-loops failure shape, and before this the only adapter in the tree was harness-local
# (`tests/eng1_rules.py:_report_inputs`).
#
# It closes the two gaps that copy carries, both measured at drafting:
#   · LEVEL — schedule rows carry no `level` key (measured: {None} across 760 rows), so the
#     harness-local copy hardcoded "2" and reported every Level-1 Mixed match as Level 2.
#     Level is DERIVED here from the build's own per-level division lists.
#   · ROUND LABEL — that copy passed the raw round NUMBER ("2", "3"). This module's round
#     vocabulary is `draws_pdf.LABEL_SIZE` ("R32" … "Quarterfinals", "Semifinals", "Final")
#     plus `RR_ROUND`, and two checks read it: CADENCE's closing-day exception and VENUE-LATE,
#     which asks `canonical_round(m.round_label) in _LATE_ROUNDS`. Fed a bare number, BOTH are
#     structurally blind — VENUE-LATE cannot fire at all. A number is not this module's
#     vocabulary, so the adapter speaks the vocabulary.
#
# It is a PROJECTION, not a new field: `td-report/v1` gains nothing, no contract is opened, and
# the engine is not read for anything it did not already emit.
_GROUP_SUFFIX = re.compile(r"\s+—\s+Group\s+\d+$")


def _base_division(name: str) -> str:
    """A round-robin division is scheduled under its group name (`… — Group 1`) while the build's
    per-level lists key on the base division. Strip the suffix to join them."""
    return _GROUP_SUFFIX.sub("", name or "")


def _levels_by_division(built: dict) -> dict:
    """{division name as scheduled: "1" | "2"} from the build's own per-level draw inventory.

    `built["meta"][lvl]["drawn_by_division"]` is what `wwtc_ingest` recorded per level, so this
    reads the build rather than guessing. Measured on the committed field: 4 divisions / 49 rows
    resolve to Level 1 and 47 divisions / 711 rows to Level 2 — the baseline's own per-level
    placed counts, which is the cross-check that this derivation is right.
    """
    per_level = {}
    for lvl in built.get("levels", ()):
        for div in (built.get("meta", {}).get(lvl, {}).get("drawn_by_division") or {}):
            per_level[div] = str(lvl)
    out = {}
    for e in built.get("result", {}).get("schedule", []):
        name = e.get("event")
        if name in out:
            continue
        lvl = per_level.get(_base_division(name))
        if lvl is None:
            # Named, not swallowed: a division the build cannot place at a level would be
            # silently audited as Level 2 otherwise, which is the gap this function exists to
            # close. The run's step reports it; it does not stop the report.
            lvl = "2"
        out[name] = lvl
    return out


def _adapter_round_label(rnd, draw, max_round) -> str:
    """The engine's round NUMBER in this module's round vocabulary.

    Round robin has no bracket round, so it gets `RR_ROUND` — the label this module already
    reserves for exactly that, rather than a bracket label it would then be scored against.
    """
    if str(draw) == "rr":
        return RR_ROUND
    if rnd is None or max_round is None:
        return str(rnd)
    back = max_round - rnd
    names = {v: k for k, v in draws_pdf.LABEL_SIZE.items()}
    size = 2 ** (back + 1)
    return names.get(size, str(rnd))


def scheduled_from_result(built: dict, roster: Optional[dict] = None) -> tuple:
    """(matches, roster) — the shipped projection of a `wwtc_pipeline.build_combined` result
    into `ScheduledMatch` records, ready for `report()`.

    Sides are the certain ones only: an undecided feeder carries no commitment, so a row with
    neither side resolved is skipped exactly as the harness-local copy skipped it. Deterministic
    — the record order is a total sort, so the same build projects the same records every time.
    """
    roster = full_roster() if roster is None else roster
    by_name = {p.name: pid for pid, p in roster.items()}
    rows = built.get("result", {}).get("schedule", [])
    levels = _levels_by_division(built)
    max_round: dict = {}
    for e in rows:
        ev, r = e.get("event"), e.get("round")
        if r is not None and (ev not in max_round or r > max_round[ev]):
            max_round[ev] = r
    out = []
    for i, m in enumerate(rows):
        a = tuple(sorted(by_name[n] for n in (m.get("team_a") or []) if n in by_name))
        b = tuple(sorted(by_name[n] for n in (m.get("team_b") or []) if n in by_name))
        # A row whose sides are BOTH undecided still carries the record: it is a real match, on
        # a real day, at a real time, in a real division. The harness-local copy dropped those
        # 272 of 760 rows, and dropping them made the report structurally blind to every check
        # that is about the MATCH rather than the people in it — CADENCE above all, whose two
        # collisions on the committed field are round-2/round-3 pairs with no named players yet,
        # so not one of them reached the report. `sides=(None, None)` reads through the record
        # model unchanged: `players` is empty, `fully_known` is False, and every per-player
        # check no-ops on it exactly as it does on a half-known feeder today.
        start = m.get("start") or "00:00"
        out.append(ScheduledMatch(
            event=m["event"], level=levels.get(m.get("event"), "2"),
            round_label=_adapter_round_label(m.get("round"), m.get("draw"),
                                             max_round.get(m.get("event"))),
            match_index=i, day=m["day"],
            start=int(start[:2]) * 60 + int(start[3:]),
            venue=m.get("location"), sides=(a or None, b or None)))
    out.sort(key=lambda x: (x.day, x.start, x.event, x.round_label, x.match_index))
    return out, roster


# --------------------------------------------------------------------------
# SCHEDULE CONSTRUCTION from ingested draws + ING-1 stamps
# --------------------------------------------------------------------------
def _round_labels(size: int) -> list:
    names = {v: k for k, v in draws_pdf.LABEL_SIZE.items()}
    out, s = [], size
    while s >= 2:
        out.append(names[s])
        s //= 2
    return out


def _certain_side(real_positions: set, ids_by_pos: dict, lo: int, hi: int):
    """The players certainly appearing on the side fed by draw slots [lo, hi], or None.

    Certain exactly when the sub-bracket holds ONE non-bye slot AND that entrant resolved to at
    least one player: they reach this match without playing anyone, so no result is needed to name
    them. Two or more real slots means a match must be won first, and the side is undecided; zero
    means the side is pure bye.

    An entrant the roster join could not resolve returns None, not an empty tuple. The distinction
    matters: `()` is a side that is "certain with nobody on it", which reads as fully known, audits
    as zero people, and cannot be caught by any check that inspects names — there are none to
    inspect. Those entrants are counted into `source["coverage"]["unresolved_entrants"]` instead,
    so an identity failure is visible rather than absorbed.
    """
    real = [p for p in range(lo, hi + 1) if p in real_positions]
    if len(real) != 1:
        return None
    return ids_by_pos.get(real[0]) or None


def rr_matches(draw, resolved, level: str, year: int = 2026):
    """(matches, stats) for one round-robin DivisionDraw, from the ING-1 row-attributed stamps.

    A round-robin grid prints a match's stamp twice — once in each of its two players' rows — so a
    stamp under exactly two rows names its pairing outright. That recovers most of them. What is
    left is the whole-group slot: every row carries the same stamp because the entire group is on
    court at once, two matches running side by side, and the grid never says which pair is which.
    Round-robin structure does not settle it either — on the committed 2026 field, eliminating
    pairings already seen at other times leaves 2 to 3 possible matchings for every such slot, so
    there is nothing to deduce.

    Those slots are emitted as ONE record carrying every player on court, with `courts` set to the
    number of matches. Nothing is invented and nothing is lost that any check reads: rest, floor
    and band checks are per player and each player's commitment is exact; venue load counts
    `courts`. Only the pairing is unavailable, and no check reads a pairing.

    Round cadence is out of reach for round-robin regardless of any of this — the grid prints no
    round labels at all, so a match cannot be attributed to a round.
    """
    ids_by_row = {}
    for r in resolved:
        if r.kind != "rr" or not r.player_ids or "#" not in r.ref:
            continue
        group, _, idx = r.ref.rpartition("#")
        if idx.isdigit():
            ids_by_row[(group, int(idx))] = tuple(sorted(r.player_ids))

    out = []
    stats = {"pairings_recovered": 0, "group_slots": 0, "matches": 0, "rows_unresolved": 0}
    for g in draw.groups:
        slots: dict = {}
        for row, stamps in sorted(g.row_stamps.items()):
            if (g.name, row) not in ids_by_row:
                stats["rows_unresolved"] += sum(1 for s in stamps if s)
                continue
            for s in stamps:
                if s:
                    slots.setdefault(parse_stamp(s, year), []).append(row)
        for (day, start, venue), rows in sorted(slots.items()):
            rows = sorted(set(rows))
            ids = [ids_by_row[(g.name, r)] for r in rows]
            if len(rows) == 2:
                sides, courts = (ids[0], ids[1]), 1
                stats["pairings_recovered"] += 1
            else:
                sides = (tuple(sorted(p for side in ids for p in side)), None)
                courts = max(1, len(rows) // 2)
                stats["group_slots"] += 1
            stats["matches"] += courts
            out.append(ScheduledMatch(
                event=draw.event, level=level, round_label=RR_ROUND, match_index=len(out) + 1,
                day=day, start=start, venue=venue, sides=sides, courts=courts))
    return out, stats


def schedule_from_draws(draws_by_level: dict, players_by_level: dict, year: int = 2026,
                        mixed_level_1=()):
    """(matches, unscheduled) for the ingested draws.

    `matches` is every STAMPED elimination match, with each side resolved to certain players where
    publication-time certainty allows (see the module docstring). `unscheduled` is every
    elimination match the PDF left without a stamp — the FINALS-UNSET feed.

    Round-robin groups ARE ingested, via `rr_matches` and the ING-1 row-attributed stamps. The
    coverage block still reports them in numbers, because how much of a round-robin the source
    scheduled varies: the 2026 APPROVED set carries no RR schedule at all (its grids print scores
    where the raw set prints stamps), so those divisions have nothing to audit, and that must not
    read as "audited and clean".
    """
    matches, unscheduled = [], []
    coverage = {"rr_groups": 0, "rr_groups_with_stamps": 0, "rr_stamps_present": 0,
                "rr_matches_ingested": 0, "rr_pairings_recovered": 0, "rr_group_slots": 0,
                "rr_rows_unresolved": 0, "unresolved_entrants": 0}
    for lvl in sorted(draws_by_level):
        draws = draws_by_level[lvl]
        by_div, _ = WI.resolve_draws(draws, players_by_level[lvl])
        # DIV-1 (rule 44): the ingest-coverage walk reads the divisions in the TD's order.
        for d in DO.sorted_by(draws, lambda x: x.event, mixed_level_1):
            coverage["unresolved_entrants"] += sum(
                1 for r in by_div[d.event] if not r.is_bye and not r.player_ids)
            if d.fmt != "single_elim":
                coverage["rr_groups"] += len(d.groups)
                for g in d.groups:
                    stamps = sum(1 for s in g.stamps if s)
                    coverage["rr_stamps_present"] += stamps
                    coverage["rr_groups_with_stamps"] += 1 if stamps else 0
                rr, st = rr_matches(d, by_div[d.event], lvl, year)
                matches += rr
                coverage["rr_matches_ingested"] += st["matches"]
                coverage["rr_pairings_recovered"] += st["pairings_recovered"]
                coverage["rr_group_slots"] += st["group_slots"]
                coverage["rr_rows_unresolved"] += st["rows_unresolved"]
                continue
            ids_by_pos = {r.pos: tuple(sorted(r.player_ids))
                          for r in by_div[d.event] if r.pos and not r.is_bye and r.player_ids}
            real = {s.pos for s in d.slots if not s.is_bye}
            for ri, label in enumerate(_round_labels(d.draw_size), start=1):
                span = 2 ** ri
                for k in range(1, d.draw_size // span + 1):
                    stamp = draws_pdf.schedule_of(d, label, k)
                    if not stamp:
                        unscheduled.append({"event": d.event, "level": lvl,
                                            "round": label, "match_index": k})
                        continue
                    day, start, venue = parse_stamp(stamp, year)
                    lo = (k - 1) * span + 1
                    matches.append(ScheduledMatch(
                        event=d.event, level=lvl, round_label=label, match_index=k,
                        day=day, start=start, venue=venue,
                        sides=(_certain_side(real, ids_by_pos, lo, lo + span // 2 - 1),
                               _certain_side(real, ids_by_pos, lo + span // 2, lo + span - 1))))
    matches.sort(key=lambda m: (m.day, m.start, m.event, m.round_label, m.match_index))
    unscheduled.sort(key=lambda u: (u["event"], u["round"], u["match_index"]))
    return matches, unscheduled, coverage


def load_2026(which: str = "app", levels=("1", "2")):
    """The committed 2026 file set as (matches, unscheduled, roster, source).

    `which` is "app" (the TD's approved draws) or "raw" (the desk's autoschedule). The approved
    PDFs are the ANSWER KEY plane — the product flow ingests raw draws (ING-1 §5); this loader
    reaches the approved set so the harness can score the reporter against a known schedule.
    """
    names = {("raw", "1"): "26_WWTC_L1_Raw_Draws.pdf", ("raw", "2"): "26_WWTC_L2_Raw_Draws.pdf",
             ("app", "1"): "26_WWTC_L1_Approved_Draws.pdf",
             ("app", "2"): "26_WWTC_Approved_Draws.pdf"}
    data = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "wwtc-2026")
    draws_by_level, players_by_level, files = {}, {}, []
    for lvl in levels:
        fn = names[(which, lvl)]
        files.append(fn)
        draws_by_level[lvl] = draws_pdf.parse_draws(os.path.join(data, fn))
        players_by_level[lvl] = WI.load_players(level=lvl)
    matches, unscheduled, coverage = schedule_from_draws(draws_by_level, players_by_level)
    source = {"files": sorted(files), "levels": sorted(levels), "set": which,
              "coverage": coverage}
    return matches, unscheduled, full_roster(levels), source


# --------------------------------------------------------------------------
# CLASSIFIERS
# --------------------------------------------------------------------------
def event_kind(event: str) -> str:
    """"singles" | "mixed" | "doubles" — the day-shape kinds of §8A row 30.

    Mixed is split out from gender doubles on purpose: `wwtc_ingest._is_doubles` answers True for
    both (they share `precedence=1`), which is exactly the collapse that made the row-30 day shape
    unverifiable in the engine. The band model needs the three-way split.
    """
    low = event.lower()
    if "singles" in low:
        return "singles"
    return "mixed" if low.startswith("mixed") else "doubles"


def _levels_differ(a: ScheduledMatch, b: ScheduledMatch) -> bool:
    return a.level != b.level


def _player_days(matches: list) -> dict:
    """{(usta_id, day): [ScheduledMatch]} over every CERTAIN commitment, each list time-sorted."""
    out: dict = {}
    for m in matches:
        for pid in m.players:
            out.setdefault((pid, m.day), []).append(m)
    for k in out:
        out[k].sort(key=lambda m: (m.start, m.event, m.round_label, m.match_index))
    return out


# --------------------------------------------------------------------------
# CHECKS (RPT-1 §9)
# --------------------------------------------------------------------------
def check_rest(matches, roster, cfg):
    """REST-XLEVEL — same-day commitments closer than the start-to-start floor.

    One finding per MATCH PAIR, not per player: two doubles partners sharing the same two matches
    are one scheduling fact with two people on it, and the finding names both. Cross-level pairs
    are tagged — the 2026 retrospective found the floor breaks almost only where the two levels
    cannot see each other, which is the whole reason this check exists.
    """
    found: dict = {}
    for (pid, day), ms in _player_days(matches).items():
        for a, b in itertools.combinations(ms, 2):
            gap = abs(b.start - a.start)
            if gap >= cfg.min_start_to_start:
                continue
            key = tuple(sorted((a.mid, b.mid)))
            rec = found.setdefault(key, {"a": a, "b": b, "gap": gap, "day": day, "pids": set()})
            rec["pids"].add(pid)
    out = []
    for rec in found.values():
        a, b, gap = rec["a"], rec["b"], rec["gap"]
        cross = _levels_differ(a, b)
        who = _names(roster, rec["pids"])
        overlap = gap < cfg.match_minutes
        # Ruling 72's named exception. The TD flipped the switch on this division BECAUSE its
        # players asked to finish the same day; the engine placed the pair at his gap on purpose,
        # and calling that a `breach` would have the tool's own instrument contradict its own
        # ruling. Reported as `info` so the shorter turnaround is still visible and attributed.
        exc = cfg.same_day_finish.get(a.event) if a.event == b.event else None
        if exc is not None and gap >= exc and not overlap:
            out.append(_finding(
                "REST-XLEVEL", "info", [a.event], who, rec["day"],
                f"{a.event} {a.round_label} ({hhmm(a.start)}) and {b.round_label} "
                f"({hhmm(b.start)}) on {rec['day']} are {gap} minutes apart for "
                f"{', '.join(who)} — inside the {cfg.min_start_to_start}-minute rest floor, and "
                f"deliberately so: this division is set to finish the same day at a {exc}-minute "
                f"gap because its players asked to. It is the one exception to the rest rule.",
                {"gap_minutes": gap, "floor_minutes": cfg.min_start_to_start,
                 "same_day_finish_gap": exc, "cross_level": cross, "overlapping": overlap,
                 "matches": [a.mid, b.mid], "starts": [hhmm(a.start), hhmm(b.start)]}))
            continue
        lead = "DOUBLE-BOOKED" if gap == 0 else f"Only {gap} minutes start-to-start"
        tail = (" The two divisions sit at different levels, so neither scheduling system "
                "sees the other." if cross else "")
        detail = (f"{lead} between {a.event} {a.round_label} ({hhmm(a.start)}) and "
                  f"{b.event} {b.round_label} ({hhmm(b.start)}) on {rec['day']} for "
                  f"{', '.join(who)} — the floor is {cfg.min_start_to_start} minutes.{tail}")
        out.append(_finding(
            "REST-XLEVEL", "breach", [a.event, b.event], who, rec["day"], detail,
            {"gap_minutes": gap, "floor_minutes": cfg.min_start_to_start, "cross_level": cross,
             "overlapping": overlap, "matches": [a.mid, b.mid],
             "starts": [hhmm(a.start), hhmm(b.start)]}))
    return out


def _band_target(kind, cfg, offset):
    """The band this kind must start AT OR BEFORE.

    D-40 / ruling 67 read all three of the TD's times as **"at or earlier"** — his own week starts
    103 matches before 9:00, 21 of them exactly these head starts, so an exact-9:00 reading would
    move his own practice LATER. The pre-ENG-1 D1a model read `mixed_at` as exact equality and
    `doubles_from` as a lower bound, and leaving those in place while `from_constraints` re-pointed
    the NUMBERS at the TD's doc made the reporter grade the engine's own output backwards: measured
    on the shipped field, 8 BAND-3EV findings telling the TD to move matches to slots
    `scheduler_multi._in_band` would refuse. One rule, one direction, both surfaces.
    """
    at = {"singles": cfg.band_singles_by, "mixed": cfg.band_mixed_at}.get(
        kind, cfg.band_doubles_from)
    return ("at or before", at + offset)


def _band_ok(kind, start, cfg, offset):
    _rel, t = _band_target(kind, cfg, offset)
    return start <= t


# CAD-1: the advice this check gives, keyed on whether the engine RECORDED the late start as a
# yield it chose. "Move it" was the only sentence before, and against a recorded yield it is bad
# advice: the engine tried every slot on that day, then every other day, and bent this promise
# because that was the least-bad thing left. Telling the director to move a match the tool has
# already proven has nowhere better to go sends him hunting for a slot that does not exist.
# Where the late start is NOT a recorded yield — a couriered edit put it there — "move it" is
# still exactly right, and that sentence is unchanged.
_BAND_ADVICE = {
    False: "Move it to keep the three-event day inside the band model.",
    True: ("The tool put it there deliberately: no slot anywhere kept both this player's early "
           "start and the rest of the week's rules, so it gave up the early start rather than "
           "move the match off its planned day. Nothing to fix unless you would rather it "
           "moved days."),
}


def _is_recorded_yield(m, recorded):
    """Did the ENGINE record this late start as a yield it chose? See `report`'s own note on why
    the key is (division, day, clock) and not the match id."""
    return bool(recorded) and (m.event, m.day, hhmm(m.start)) in recorded


def check_bands(matches, roster, cfg, compressed, recorded=None):
    """BAND-3EV — D1a/D1b compliance for three-event player-days, with the move-list.

    A three-event day is a player-day carrying all three kinds (singles, mixed, gender doubles) —
    the day the band model exists to make survivable. The day is scored against the band triple and
    against the accepted slide-early variant, and the variant that costs fewer moves wins, so a
    triple the TD deliberately slid is not reported as three breaches.

    Compressed (opening / closing) days are SKIPPED: D1a's named exception gap-checks them
    directly instead, which REST-XLEVEL already does over the same commitments.
    """
    out = []
    for (pid, day), ms in sorted(_player_days(matches).items()):
        if day in compressed:
            continue
        kinds = {event_kind(m.event) for m in ms}
        if kinds != {"singles", "mixed", "doubles"}:
            continue
        best = None
        for off in cfg.band_slide_offsets:
            bad = [m for m in ms if not _band_ok(event_kind(m.event), m.start, cfg, off)]
            if best is None or len(bad) < len(best[1]):
                best = (off, bad)
        off, bad = best
        who = _names(roster, [pid])
        for m in bad:
            kind = event_kind(m.event)
            rel, target = _band_target(kind, cfg, off)
            out.append(_finding(
                "BAND-3EV", "warn", [m.event], who, day,
                f"{who[0]} plays three events on {day}; the {kind} match "
                f"({m.event} {m.round_label}) starts {hhmm(m.start)} but the "
                f"{'slide-early ' if off else ''}band wants it {rel} {hhmm(target)}. "
                f"{_BAND_ADVICE[_is_recorded_yield(m, recorded)]}",
                {"kind": kind, "start": hhmm(m.start), "band": f"{rel} {hhmm(target)}",
                 "slide_early": bool(off), "match": m.mid,
                 "recorded_engine_yield": _is_recorded_yield(m, recorded),
                 "day_starts": [hhmm(x.start) for x in ms]}))
    return out


def check_floor_80(matches, roster, cfg, three_event_days):
    """FLOOR-80 — an 80-and-over division starting before its AVOID-3 floor.

    Annotated, not escalated, when the early start is what buys a three-event day its rest: the
    rest-wins precedence is TD packet Q6 and is not ours to rule, so the report states which of
    the two rules the start is serving and leaves the call with the TD.
    """
    out = []
    for m in matches:
        if C._age(m.event) < cfg.floor_age_min or m.start >= cfg.floor_before:
            continue
        who = _names(roster, m.players)
        buys_rest = any((pid, m.day) in three_event_days for pid in m.players)
        tail = (" — but the player is on a three-event day, and the early start is what buys the "
                "later matches their rest (rest-vs-floor precedence is TD Q6)."
                if buys_rest else ".")
        detail = (f"{m.event} {m.round_label} starts {hhmm(m.start)} on {m.day}, before the "
                  f"{hhmm(cfg.floor_before)} floor for {cfg.floor_age_min}-and-over play{tail}")
        out.append(_finding("FLOOR-80", "warn", [m.event], who, m.day, detail,
                            {"start": hhmm(m.start), "floor": hhmm(cfg.floor_before),
                             "age_min": C._age(m.event), "buys_three_event_rest": buys_rest,
                             "match": m.mid}))
    return out


def check_cadence(matches, roster, cfg):
    """CADENCE — more than one round of a division on one day (§8A row 16).

    THE EXCEPTION IS NARROWED (CAD-1 ruling R5, Operator 2026-08-18). It used to excuse a
    semifinal-and-final pairing on ANY division's own closing day, on no evidence that the TD had
    asked for it — wider than the invariant itself, and wider than `_same_day_finish_cells`, the
    engine's own definition of a legitimate two-round day. It now requires the division to be
    NAMED in the TD's same-day-finish switch, which is the same test the engine and the
    `validate_multi` mirror apply. What that changes in practice: with rule 16 invariable, a
    closing-day pairing the TD did not ask for can now only reach this reporter through a
    COURIER-EDITED schedule, and on that board it is a finding, not "how the event finishes".

    TD PACKET Q2 NEEDS NO RECONCILING — the narrowing brings this check into line with the answer
    the packet already gave. Q2 asked whether a division may double up its semifinal and final on
    its closing day, and ruling 68 answered that it is "a player request, not a calendar rule":
    a per-division switch the TD flips, NEVER AUTOMATIC. This check was applying it automatically
    to every division's closing day, which is the opposite of what Q2 ruled. The TD's own single
    2026 instance — Mixed 60 & over doubles on 01-30, two of its four players asking to finish
    and leave — is exactly the case the switch exists for, and it now reads as a breach until he
    flips the switch, with the breach sentence naming the switch. That is Q2's answer working.

    The `closing_day` measured key keeps its name and meaning (this WAS the division's last day);
    `td_named_same_day_finish` records the half that is new, so a reader of the JSON can see which
    test the exception turned on.
    """
    cells: dict = {}
    # CUI-5 (Part D): the earliest start each round takes on a day, so the finding can say what
    # the collision does to a PERSON rather than only that it happened. `check_cadence` already
    # iterates matches carrying starts — no new input, no contract field.
    starts: dict = {}
    for m in matches:
        cells.setdefault(m.event, {}).setdefault(m.day, set()).add(m.round_label)
        k = (m.event, m.day, m.round_label)
        if k not in starts or m.start < starts[k]:
            starts[k] = m.start
    out = []
    for event in DO.sort_divisions(cells, cfg.mixed_level_1):   # DIV-1: rule 44's order
        days = cells[event]
        closing = max(days)
        for day in sorted(days):
            rounds = sorted(days[day], key=_round_rank)
            if len(rounds) < 2:
                continue
            # CAD-1 ruling R5: the TD's own named list is now half the test — the same
            # `same_day_finish.divisions` the engine reads through `_same_day_finish_cells`.
            td_named = event in (cfg.same_day_finish or {})
            closing_pair = td_named and day == closing \
                and {canonical_round(r) for r in rounds} == set(_LATE_ROUNDS)
            # CUI-5 (Part D, ruled 8/5): the console's twin of this sentence said only that a
            # division plays two rounds on a day. It named no person and no clock, so the one
            # thing the TD actually has to weigh — that a winner is back on court the same day,
            # and how many hours later — was nowhere in it. Every person-level check is blind
            # here by construction (a later elimination round has no named players yet), so
            # this sentence IS the coverage. Same wording both surfaces.
            human = ""
            turnaround = None
            if not closing_pair:
                clocks = [(r, starts.get((event, day, r))) for r in rounds]
                clocks = [(r, s) for r, s in clocks if s is not None]
                if len(clocks) >= 2:
                    (r0, s0), (r1, s1) = clocks[0], clocks[-1]
                    turnaround = s1 - s0
                    if turnaround == 0:
                        # RPT-2 (copy item 1). THE SAME-CLOCK SPECIAL CASE. Both rounds are
                        # posted at the same time, so "back on court at 14:00" after a match
                        # that also starts 14:00 is not a turnaround, it is nonsense — and it
                        # degraded exactly that way on 3 of the 2027 mock's 8 must-fix findings.
                        # What the sentence has to say instead is what the TD actually has to do:
                        # nobody can play both, so the desk sequences them by hand.
                        human = (f" — both rounds are scheduled to start at {hhmm(s0)}; the desk "
                                 f"will have to sequence them")
                    else:
                        human = (f" — whoever wins the {hhmm(s0)} {r0} match is back on court at "
                                 f"{hhmm(s1)} for the {r1}")
            measured = {"rounds": rounds, "closing_day": closing_pair,
                        "division_last_day": closing, "td_named_same_day_finish": td_named}
            if turnaround is not None:
                measured["turnaround_minutes"] = turnaround
            # RPT-2 (copy item 2). AGE WEIGHTING. The mock's two 80-and-over 90-minute
            # turnarounds sat undifferentiated in a bucket of nine, and an 84-year-old back on
            # court inside one match block is not the same finding as a 45-year-old with four
            # hours. It outranks the bucket rather than changing severity: the rule broken is
            # identical, the person it lands on is not. `priority` is read by `_sort_key`, so
            # these lead their own section and nothing else in the report moves.
            old_tight = (not closing_pair and turnaround is not None
                         and turnaround <= cfg.match_minutes
                         and C._age(event) >= cfg.floor_age_min)
            if old_tight:
                measured["priority"] = 1
                human += (f" — and this is {C._age(event)}-and-over play on a "
                          f"{turnaround}-minute turnaround" if turnaround else
                          f" — and this is {C._age(event)}-and-over play")
            out.append(_finding(
                "CADENCE", "info" if closing_pair else "breach", [event], [], day,
                f"{event} plays {len(rounds)} rounds on {day} ({', '.join(rounds)})"
                + (" — you asked this division to finish in one day, so semifinal and final "
                   "together on its closing day is how you told the tool to end it."
                   if closing_pair else
                   human + ". The division should play one round per day. Review the day "
                   "layout."
                   # CAD-1 R5: the narrowed exception opened a gap this closes. A director whose
                   # last two rounds sit together ON PURPOSE now gets a breach where he used to
                   # get an informational line, and nothing on the page told him the setting
                   # that makes it his choice again. A rule that flags a deliberate decision
                   # without naming the way to declare it is how a report trains its reader to
                   # ignore it.
                   + (" If you want this division to finish in one day, set it as a "
                      "same-day-finish division and this stops being a breach."
                      if day == closing and
                      {canonical_round(r) for r in rounds} == set(_LATE_ROUNDS) else "")),
                measured))
    return out


def check_venue_late(matches, roster, cfg):
    """VENUE-LATE — semifinals/finals, and 80-and-over play, away from the main host site.

    V-3 / F-1 / DM-2 put every semifinal and final at the host site and V-2 puts 80-and-over there;
    all four are HARD in the spec and none is enforced anywhere in the engine, so the report is
    the only place they are currently checked at all.
    """
    out, excepted = [], []
    for m in matches:
        if m.venue is None or m.venue == cfg.main_site:
            continue
        late = canonical_round(m.round_label) in _LATE_ROUNDS
        old = C._age(m.event) >= cfg.floor_age_min
        if not (late or old):
            continue
        why = " and ".join(([f"a {m.round_label.lower().rstrip('s')}"] if late else [])
                           + ([f"{C._age(m.event)}-and-over play"] if old else []))
        # VENUE-1 / rule 41 — TOLERATE A RECORDED ESCAPE. Rules 38 and 39 are enforced at
        # placement now, so a match still off the main site is one the engine could not seat
        # there and PLACED AND RECORDED rather than refusing. Grading that as a warning would be
        # the tool reporting its own legal fallback as a fault. It is surfaced below instead, as
        # an `info`, so the exception is visible without being an accusation.
        if (m.mid, m.day, hhmm(m.start), m.venue) in cfg.venue_escapes:
            excepted.append(m)
            continue
        out.append(_finding(
            "VENUE-LATE", "warn", [m.event], _names(roster, m.players), m.day,
            f"{m.event} {m.round_label} is at {m.venue} on {m.day}, not the host site "
            f"{cfg.main_site} — the rules keep {why} on the main site.",
            {"venue": m.venue, "main_site": cfg.main_site, "round": m.round_label,
             "age_min": C._age(m.event), "match": m.mid}))
    if excepted:
        out.append(_finding(
            "VENUE-LATE", "info", sorted({m.event for m in excepted}), [], None,
            f"{len(excepted)} match(es) the venue rules would have kept at {cfg.main_site} are "
            f"elsewhere because it had no room at the time they needed — each was placed and "
            f"recorded rather than left unscheduled.",
            {"escapes": len(excepted), "main_site": cfg.main_site,
             "matches": sorted(m.mid for m in excepted)}))
    return out


def check_finals_unset(unscheduled, roster, cfg):
    """FINALS-UNSET — a final the desk left without a stamp. Info: it feeds the F7 finals lane
    rather than blocking anything. The desk leaves most of them unscheduled by habit."""
    return [_finding("FINALS-UNSET", "info", [u["event"]], [], None,
                     f"{u['event']} has no scheduled final — the draw prints no day, time or "
                     f"venue for it. Set it in the finals map before publishing.",
                     {"round": u["round"], "match_index": u["match_index"], "level": u["level"]})
            for u in unscheduled if canonical_round(u["round"]) == "Final"]


def check_cap_slate(matches, roster, cfg):
    """CAP-SLATE — concurrency against the MEASURED slate (D8: 20/12/4), and the lit-court
    ceiling from 15:30 (SLATE-1: MHCC 7; ORLP/WEST blank pending TD Q7).

    Concurrency is a sweep over the uniform 90-minute block, so a peak is the true simultaneous
    count rather than a per-start-time tally. A venue with no measured capacity is skipped rather
    than assumed — inventing a ceiling would manufacture findings.
    """
    out = []
    by_venue_day: dict = {}
    for m in matches:
        if m.venue is None:
            continue
        by_venue_day.setdefault((m.venue, m.day), []).append(m)
    for (venue, day) in sorted(by_venue_day):
        ms = by_venue_day[(venue, day)]
        # D-10: the lights hour is per venue now, so a venue's lit ceiling and the hour it starts
        # come from the same row of the slate. A venue with a lit count but no hour is skipped —
        # SLATE-1 makes the pair both-or-neither, and inventing an hour would manufacture findings.
        day_cap = cfg.slate_capacity_by_day.get((venue, day), cfg.slate_capacity.get(venue))
        for limit, name, gate in ((day_cap, "measured court capacity", 0),
                                  (cfg.lit_courts.get(venue), "lit-court capacity",
                                   cfg.lights_from.get(venue))):
            if limit is None or gate is None:
                continue
            # A court is occupied for the whole block, so the lit-court question is "how many
            # matches are ON COURT after the lights go on", not "how many START after". Filtering
            # on the start time alone let a match beginning at 15:00 hold a lit court at 15:30
            # while going uncounted — on the committed 2026 field that under-read MHCC's peak by
            # as much as 6 courts and suppressed findings entirely on the lighter days. Start
            # points are clamped to the gate so the sweep measures the lit window itself.
            pool = [m for m in ms if m.start + cfg.match_minutes > gate] if gate else list(ms)
            # `m.courts`, not 1: a round-robin whole-group slot is one record standing for two
            # matches on two courts (see `rr_matches`). Counting records would under-read the load
            # by exactly the courts the unrecoverable pairings occupy.
            pts = sorted([(max(m.start, gate), m.courts) for m in pool]
                         + [(m.start + cfg.match_minutes, -m.courts) for m in pool],
                         key=lambda x: (x[0], x[1]))
            cur = peak = 0
            peak_at = None
            for t, delta in pts:
                cur += delta
                if cur > peak:
                    peak, peak_at = cur, t
            if peak <= limit:
                continue
            tail = (f" — the {hhmm(gate)} ceiling, which is what the late doubles band has to fit "
                    f"inside." if gate else ".")
            # VENUE-1 / rule 41 — an escape is NAMED here but never excuses the finding. Court
            # capacity is physical: a venue holding more matches than it has courts is wrong
            # however it got there, and suppressing that would be the one place a recorded
            # exception could hide a real fault. What the count buys the reader is the CAUSE —
            # a peak the venue rules pushed here reads differently from one the slate caused.
            escaped = sum(1 for m in pool
                          if (m.mid, m.day, hhmm(m.start), m.venue) in cfg.venue_escapes)
            why = (f" {escaped} of those matches are recorded venue-rule exceptions."
                   if escaped else "")
            out.append(_finding(
                "CAP-SLATE", "warn", sorted({m.event for m in pool}), [], day,
                f"{venue} runs up to {peak} matches at once on {day} from {hhmm(peak_at)}, above "
                f"its {name} of {limit}{tail}{why}",
                {"venue": venue, "peak": peak, "limit": limit, "limit_kind": name,
                 "from": hhmm(gate), "peak_at": hhmm(peak_at),
                 "recorded_exceptions": escaped}))
    return out


def check_start_window(matches, roster, cfg):
    """START-WINDOW — more matches STARTING in the 15:00-16:00 block than the TD's catch-up
    slack allows (D-37 / ruling 65).

    His reason, given for the first time in the 8/1 packet, is what fixes the shape of this check:
    the limit is about **catch-up slack**, not lighting — *"no more than 9 at that 3-4 p.m.
    timeframe"* — because the day will inevitably be running behind by then. So this counts
    STARTS inside the window against 9. That is a DIFFERENT quantity from `check_cap_slate`'s
    lit-court rung, which counts matches ON COURT after the lights go on against the lit count:
    same file, second rung, not an edit to the first.

    Ruling 65 shipped it WARN-ONLY with no `validate_multi` mirror, recorded as a decision. D-48
    (2026-08-05) then ruled the ceiling ENFORCED, and VENUE-1 enforces it — at the MAIN SITE,
    which is the scope the director stated it in. This check keeps its own wider scope on
    purpose: it counts starts across EVERY venue, so it still answers "is the whole afternoon
    over-committed" rather than duplicating the engine's rule. Where the engine could not hold a
    day inside the ceiling it places the match and records the exception (rule 41), and those are
    tolerated here for the same reason the mirror tolerates them — a legal recorded fallback is
    not a fault.
    """
    out = []
    lo, hi = cfg.start_window
    by_day: dict = {}
    for m in matches:
        if lo <= m.start < hi:
            by_day.setdefault(m.day, []).append(m)
    for day in sorted(by_day):
        ms = by_day[day]
        n = sum(m.courts for m in ms)
        if n <= cfg.start_window_max:
            continue
        escaped = [m for m in ms
                   if (m.mid, m.day, hhmm(m.start), m.venue) in cfg.venue_escapes]
        # Every start over the line is one the engine recorded as an exception: report it, but as
        # information rather than a warning. The day is over the ceiling because it could not be
        # under it, which the director already accepted when the escape was ruled in.
        excused = n - sum(m.courts for m in escaped)
        sev = "info" if escaped and excused <= cfg.start_window_max else "warn"
        tail = (f" {len(escaped)} of them could not be held inside the ceiling and were placed "
                f"and recorded as exceptions." if escaped else "")
        out.append(_finding(
            "START-WINDOW", sev, sorted({m.event for m in ms}), [], day,
            f"{n} matches start between {hhmm(lo)} and {hhmm(hi)} on {day}, above the "
            f"{cfg.start_window_max} the TD keeps free for catch-up — by mid-afternoon the day "
            f"is usually running behind, and that block is the slack that absorbs it.{tail}",
            {"starts": n, "limit": cfg.start_window_max,
             "window": [hhmm(lo), hhmm(hi)], "recorded_exceptions": len(escaped),
             "by_venue": {v: sum(m.courts for m in ms if m.venue == v)
                          for v in sorted({m.venue for m in ms if m.venue is not None})}}))
    return out


def _seed_block(v: int) -> int:
    """Seed value -> seeding block ordinal (1, 2, 3-4, 5-8, 9-16, 17-32)."""
    for i, lo in enumerate((1, 2, 3, 5, 9, 17), start=1):
        hi = (1, 2, 4, 8, 16, 32)[i - 1]
        if lo <= v <= hi:
            return i
    return 7


def _table3_max_seeds(entrants: int) -> int:
    """Adult Regulations Table 3 — max seeds by DRAW SIZE (the next power of two above the
    entrant count). This is the reading rule 47's measurement used (8/6): graded per player
    count, Mixed 70 doubles' 4 seeds on 10 teams would read over-ladder, but the measured
    over-ladder count is 0 of 42 on both sides — the desk seeds to the printed draw's size."""
    size = 1
    while size < max(entrants, 2):
        size *= 2
    return {4: 2, 8: 2, 16: 4, 32: 8, 64: 16}.get(max(size, 4), 32)


def check_seed_count(seeds, entrants_by_division, cfg, recorded_seed_drops=None):
    """SEED-COUNT — register rule 47 (ruled 8/5 option 3; tier ruled 8/6 option 2, ruling 84).

    WARN-ONLY, never blocks. Two WARN conditions (a count no rule allows): not a power of two,
    or over Table 3's ladder. INFO: over the strict 1-in-3 ratio (his desk exceeds it
    deliberately on sparse draws — flagging normal behaviour is the rule-42 mistake) and a
    skipped seed block (a withdrawal print artifact).

    OPTION 2 (ruling 84): a non-power-of-two count this tool itself produced by dropping a
    seed on a RECORDED substitution is EXPLAINED — the drop rides the change into the rekey
    delta — and stays SILENT. `recorded_seed_drops` = {division: n dropped-seed substitutions
    recorded this run}; absent = none. An odd count no recorded drop explains still warns.

    SILENT where a division prints no seed at all: `seeds` simply has no entry (measured 8/6:
    0 of 8 RR divisions print one — nothing to check, no empty finding). Ladder and ratio are
    graded only where the entrant count is known; inventing one would manufacture findings.
    """
    out = []
    drops = dict(recorded_seed_drops or {})
    for div in sorted(seeds or {}):
        # SILENT on round-robin divisions (ruled). RR groups run as "<parent> — Group N";
        # a stray seed marker parsed off an RR grid must not produce a finding — 0 of 8 RR
        # divisions print a real seed (measured 8/6), and the rung has nothing to check there.
        if re.search(r"\s+[—-]\s*Group\s*\d+\s*$", div):
            continue
        per = seeds[div] or {}
        if not per:
            continue
        # n = SEEDED TEAMS (one entry per seeded slot). The printed VALUES are block heads —
        # seeds 5-8 all print "5", 9-16 all print "9" (Table 3's alphabetical groups) — so
        # counting distinct values under-counts: Men's 50 singles prints [1,2,3,4,5,5,5,5],
        # eight seeds, a legal power of two.
        n = len(per)
        nums = sorted({int(v) for v in per.values()})
        entrants = (entrants_by_division or {}).get(div)
        if n & (n - 1):                                   # not a power of two
            explained = drops.get(div, 0)
            if not ((n + explained) & (n + explained - 1)) and explained:
                pass                                      # option 2: explained -> silent
            else:
                out.append(_finding(
                    "SEED-COUNT", "warn", [div], [], None,
                    f"{n} seeds is not a standard count (1, 2, 4, 8, 16, 32) and no recorded "
                    f"substitution explains it.",
                    {"seeds": n, "seed_numbers": nums}))
        if entrants and n > _table3_max_seeds(entrants):
            out.append(_finding(
                "SEED-COUNT", "warn", [div], [], None,
                f"{n} seeds is above Table 3's ceiling of {_table3_max_seeds(entrants)} "
                f"for {entrants} entrants.",
                {"seeds": n, "entrants": entrants, "ceiling": _table3_max_seeds(entrants)}))
        if entrants and n * 3 > entrants:
            out.append(_finding(
                "SEED-COUNT", "info", [div], [], None,
                f"{n} seeds across {entrants} entrants is above the strict 1-in-3 ratio — "
                f"common on a sparse draw, not an error.",
                {"seeds": n, "entrants": entrants}))
        # A skipped seed BLOCK ([2] with no [1]) — blocks are 1 · 2 · 3-4 · 5-8 · 9-16 · 17-32,
        # so a draw printing 1,2,3,4,5,9 has every block and is clean; one printing only [2]
        # skipped block 1. The blocks present must be a contiguous prefix.
        blocks = sorted({_seed_block(v) for v in nums})
        if blocks != list(range(1, len(blocks) + 1)):
            out.append(_finding(
                "SEED-COUNT", "info", [div], [], None,
                f"A seed number is missing (seeds run {', '.join(map(str, nums))}). "
                f"Usually a withdrawal, not an error.",
                {"seed_numbers": nums}))
    return out


def check_sametype_watch(matches, draw_entries, roster, cfg):
    """SAMETYPE-WATCH — players entered in more than one division of the SAME kind.

    Two singles draws, or two gender-doubles draws, is a standing double-duty risk the desk has no
    reason to notice: the divisions are age-separated and look unrelated. Roster-joined, so the
    same-surname couples that inflated this population to 48 in the first pass stay two people.
    Info, unless one of their same-day pairs actually breaches the rest floor.
    """
    out = []
    for pid in sorted(draw_entries):
        by_kind: dict = {}
        for event in draw_entries[pid]:
            by_kind.setdefault(event_kind(event), set()).add(event)
        for kind in sorted(by_kind):
            evs = sorted(by_kind[kind])
            if len(evs) < 2:
                continue
            who = _names(roster, [pid])
            days = sorted({m.day for m in matches
                           if m.event in evs and pid in m.players})
            out.append(_finding(
                "SAMETYPE-WATCH", "info", evs, who, None,
                f"{who[0]} is entered in {len(evs)} {kind} divisions ({', '.join(evs)}). "
                f"They are age-separated draws that look unrelated on the desk, so a same-day "
                f"double-duty is easy to schedule by accident. "
                + (f"Scheduled commitments fall on {', '.join(days)}." if days else
                   "No commitments are certain at publication time yet."),
                {"kind": kind, "divisions": evs, "days": days}))
    return out


def entries_by_player(draws_by_level: dict, players_by_level: dict, mixed_level_1=()) -> dict:
    """{usta_id: [division, ...]} over every drawn entrant, via the roster join.

    DIV-1 (rule 44): each player's division list comes out in the TD's reading order."""
    out: dict = {}
    for lvl in sorted(draws_by_level):
        by_div, _ = WI.resolve_draws(draws_by_level[lvl], players_by_level[lvl])
        for event in DO.sort_divisions(by_div, mixed_level_1):
            for r in by_div[event]:
                if r.is_bye:
                    continue
                for pid in r.player_ids:
                    out.setdefault(pid, set()).add(event)
    # The emitted per-player list is the one a human reads, so it takes the key too — sorting
    # the walk above and then alphabetising here would have undone it.
    return {k: DO.sort_divisions(v, mixed_level_1) for k, v in sorted(out.items())}


# --------------------------------------------------------------------------
# REPORT
# --------------------------------------------------------------------------
def _finding(code, severity, divisions, players, day, detail, measured):
    # DIV-1 (rule 44): EVERY finding's division list comes out in the TD's reading order. The
    # re-sort happens once, in `report()` (`_display_order_findings`), rather than here — this
    # helper has no `cfg` and so no way to know which Mixed divisions are Level 1, and doing it
    # in one place means a check added later is covered without remembering to pass anything.
    # The alphabetical sort stays as the deterministic construction-time order.
    return {"code": code, "severity": severity, "divisions": sorted(divisions),
            "players": list(players), "day": day, "detail": detail, "measured": measured}


def check_held(held):
    """HELD — the matches the TD took off the schedule and never placed back (HOLDVIS-1, ruling 4).

    REPORTING ONLY, and severity `warn` (printed "Check"): a hold is the TD's own recorded
    decision — a withdrawal pending confirmation, a match awaiting a ruling — not a rule break,
    and this rung never argues with it. What it says is what the hold COSTS: the players in a held
    match have no day, time or venue anywhere, so without this the one mandatory page before print
    was silent about 3 matches and 6 people on the 2026 run.

    `held` is `result["held"]` — one descriptor per held match, carrying the division, the round
    and the players by name. Omitted or empty ⇒ no finding and no section, so the rung cannot fire
    on a report that should not carry it.
    """
    out = []
    for h in (held or ()):
        div = h.get("event") or ""
        who = list(h.get("players") or ())
        rnd = h.get("round")
        where = f"{div} Round {rnd}" if rnd is not None else div
        # The internal match reference (`label` carries "R1 M2") never reaches the prose — the
        # match is named the way a person names it: the division, the round and who is in it.
        out.append(_finding(
            "HELD", "warn", [div] if div else [], who, None,
            f"{where} — {' v '.join(who) if who else 'both sides undecided'} — is held off the "
            f"schedule. It has no day, time or venue, and it prints as held on the draw, in the "
            f"player file and on the handouts. Place it before publishing, or publish it held.",
            {"round": rnd, "players": len(who)}))
    return out


def check_conflicts(conflicts):
    """CONFLICTS — the rule breaks the TD's own edits put on the board (RPT-2 / A5c).

    THE ONE RUNG HERE THAT GRADES NOTHING, and that is the design, not a shortcut. The engine
    already recorded each of these in plain English in `result["conflicts"]`; this rung carries
    that sentence to the one mandatory page **verbatim, character for character**. Re-deriving
    day order — or any of the other sixteen rules `validate_multi` mirrors — inside the reporter
    would put a second copy of each rule in the tree, which is the mirror hazard this codebase
    refuses (PLAN §2's standing gate, and the reason `check_cadence` is advisory).

    WHY IT WAS BLIND WITHOUT IT. The reporter's twelve other rungs re-read the SCHEDULE; none of
    them reads the engine's record. Measured at build on this repo's own field: one TD move
    (`E2-R1-M15`, 11:00 → 14:00 on 2026-01-26) puts **36 conflicts** on the board — 35 day-order
    and 1 double-book — and the report went from 15 findings to 16. **35 of the 36, every
    day-order one, produced ZERO findings**, and the 36th surfaced only as a rest breach that
    never said "day order". The 2027 mock published a board carrying 25 of them under a report
    that called it clean.

    Severity `warn` — printed "Check", the `HELD` shape and for the same reason. A conflict on
    this list is a rule break the TD introduced and **knowingly accepted**, and an accepted
    conflict publishes (Operator ruling 8/7: recorded, never a failure). Grading it "Must fix"
    would have the one mandatory page contradict the ruling — and contradict the conflicts sheet
    beside it, whose heading RPT-2 stops threatening a gate that does not exist.

    `conflicts` is `result["conflicts"]`. Omitted or empty ⇒ no finding and no section, which is
    every build the engine makes on its own: 0 conflicts is the invariant that never bends, so
    this section only ever carries what a TD accepted.
    """
    out = []
    for i, c in enumerate(conflicts or ()):
        # `day=None` and no divisions or players ON PURPOSE. `render_text` prefixes the day to a
        # finding's line, and the engine's sentence already carries its own date in the
        # director's own form (`Mon 26 Jan`) — a prefix would put a second date in front of a
        # sentence this rung promises to reproduce exactly. `measured` records the position in
        # the engine's list so a reader can line the report up against the record row for row.
        out.append(_finding("CONFLICTS", "warn", [], [], None, str(c), {"recorded": i}))
    return out


def check_mixed_gender(matches, roster, cfg):
    """MIXED-GENDER — a Mixed doubles team that is not one man and one woman (GENDER-1).

    THE BACKSTOP, and the only rung here that catches a bad pairing the tool did not make: the
    console block and the engine refusal both guard the `substitute` op, so neither of them sees
    a Mixed team that arrived wrong in the printed draw. This one reads the schedule itself.

    Severity `breach` — must-fix. A Mixed division is Mixed by its rules, and two men on a Mixed
    court is not a schedule the TD can accept and publish; it is one he has to fix before print.
    The 2027 mock run's pairing reached the printed draw sheets with no surface saying a word.

    Identity is the USTA id off `sides`, so the roster join is exact and no name is matched. The
    rung is SILENT wherever the entry list has no gender for a member — ruling 88's line, held
    here too: an absent fact reports nothing rather than guessing at a breach. It is also silent
    on a side that is not exactly two people, which is what keeps it off the round-robin group
    slots that carry a whole group in one record (`ScheduledMatch.courts` > 1) — those name
    everybody on court and never who partners whom, so there is no team there to grade.
    """
    out = []
    for m in matches:
        if event_kind(m.event) != "mixed":
            continue
        for side in m.sides:
            if not side or len(side) != 2:
                continue
            gs = []
            for pid in side:
                p = roster.get(pid)
                g = (getattr(p, "gender", "") or "").strip().upper()[:1] if p is not None else ""
                gs.append(g if g in ("M", "F") else None)
            if None in gs or gs[0] != gs[1]:
                continue
            who = _names(roster, side)
            many = "women" if gs[0] == "F" else "men"
            out.append(_finding(
                "MIXED-GENDER", "breach", [m.event], who, m.day,
                f"{m.event} {canonical_round(m.round_label)} — {' and '.join(who)} are down as a "
                f"team, and both are {many}. A Mixed team is one man and one woman. Fix the pair "
                f"before this draw is printed.",
                {"gender": gs[0], "start": m.start}))
    return out


def _display_order_findings(findings, mixed_level_1):
    """Re-sort every finding's `divisions` list into rule 44's order, in place. Runs BEFORE
    `_sort_key` orders the findings themselves, because that key joins the division list — so
    the findings' own order is computed from the display order too, not from the alphabetical
    one they were built with."""
    for f in findings:
        f["divisions"] = DO.sort_divisions(f["divisions"], mixed_level_1)
    return findings


def _sort_key(f):
    # RPT-2 (copy item 2): a check may rank one of its own findings ABOVE the rest of its
    # section. `measured["priority"]` is per-check data — every code's `measured` already
    # carries its own keys — so this is an ordering hook, not a `td-report/v1` field, and a
    # finding that does not set it sorts exactly where it always did.
    priority = -int((f.get("measured") or {}).get("priority", 0))
    return (CODES.index(f["code"]), priority, f["day"] or "", ",".join(f["divisions"]),
            ",".join(f["players"]), json.dumps(f["measured"], sort_keys=True))


def _cross_reference_evening(findings):
    """RPT-2 (copy item 3) — the lit-court finding and the late-afternoon finding stop reading
    as two separate problems when they are one crowded evening.

    Measured on the 2027 mock: both fired on the same two days, and the report said nothing to
    connect them, so a TD reading down the page counted the evening twice. Neither sentence is
    replaced — each gains one clause naming the other, so a reader who fixes the evening knows
    both lines go away together.

    Reads only what the two rungs already recorded (`measured`): the lit finding names its
    venue, the late-afternoon finding names its per-venue start counts. Nothing is re-derived
    and no finding is added, removed or re-graded.
    """
    lit = [f for f in findings if f["code"] == "CAP-SLATE"
           and (f.get("measured") or {}).get("limit_kind") == "lit-court capacity"]
    late = [f for f in findings if f["code"] == "START-WINDOW"]
    if not lit or not late:
        return
    for lf in lit:
        venue = (lf.get("measured") or {}).get("venue")
        mates = [f for f in late
                 if f["day"] == lf["day"] and venue in ((f.get("measured") or {}).get("by_venue")
                                                        or {})]
        if not mates:
            continue
        lf["detail"] += (" The late-afternoon start count for this day is over its limit too — "
                         "one crowded evening, counted a second way.")
        lf["measured"]["also_reported_as"] = "START-WINDOW"
    for f in late:
        venues = sorted({(lf.get("measured") or {}).get("venue") for lf in lit
                         if lf["day"] == f["day"]
                         and (lf.get("measured") or {}).get("venue")
                         in ((f.get("measured") or {}).get("by_venue") or {})})
        if not venues:
            continue
        who = venues[0] if len(venues) == 1 else \
            ", ".join(venues[:-1]) + " and " + venues[-1]
        f["detail"] += (f" {who} is over its lit-court ceiling the same evening — "
                        f"one crowded evening, counted a second way.")
        f["measured"]["also_reported_as"] = "CAP-SLATE"


def report(matches, roster, unscheduled=(), source=None, cfg=None, draw_entries=None,
           ingest_warnings=None, constraints=None, slate=None, mixed_level_1=None,
           venue_escapes=None, seeds=None, recorded_seed_drops=None, held=None,
           conflicts=None, rule_escapes=None) -> dict:
    """The `td-report/v1` document for one schedule. Deterministic: same input, same bytes.

    `ingest_warnings` (PREP-1, additive): the tool's own ingest warnings — `meta["warnings"]`
    from `wwtc_ingest.load_from_finalized_draws` — carried verbatim and rendered as their own
    section. Before this the sole consumer of that list was a test asserting it empty: a division
    the ingest could not build was reported nowhere a human looks. Empty/omitted ⇒ the field is
    `[]` and the render has no section.

    `constraints` / `slate` (D-22, additive): the couriered `td-constraints/v1` and
    `td-resource-slate/v1` docs the RUN was built from. Supplied, the report grades against the
    TD's own numbers; omitted, it falls back to the ruled defaults exactly as before, so an
    existing caller — including `tests/rpt1_report.py`'s argument-bearing `ReportConfig` — stays
    valid. An explicit `cfg` still wins over both.

    `mixed_level_1` (DIV-1, additive): the RESOLVED Level-1 Mixed list for this run
    (`build["mixed_level_1"]`). It only sets where the Mixed divisions sit in the division lists
    this report prints — rule 44's order — and grades nothing. Omitted, a `cfg.mixed_level_1`
    is used if one is set, and otherwise every Mixed division sorts into the Level-2 block.

    `held` (HOLDVIS-1, additive, keyword-with-default): the run's held matches
    (`result["held"]`). Omitted ⇒ no held section, exactly as before — which is also why the
    runbook's Step 5.5 call has to pass it: a keyword nobody passes ships the rung inert on the
    one lane the TD actually sees (the ENG-1/D-41 lesson). `td-report/v1` gains no input field.

    `conflicts` (RPT-2 / A5c, additive, keyword-with-default): the engine's own conflict record
    (`result["conflicts"]`), carried into the report VERBATIM — see `check_conflicts`. Omitted or
    empty ⇒ no section, exactly as before, and the engine's own builds are always empty. Like
    `held`, the runbook's Step 5.5 call has to pass it or the rung ships inert on the one lane
    the TD sees. `td-report/v1` gains no input field.

    `rule_escapes` (CAD-1, additive, same shape as `venue_escapes`): the engine's own recorded
    clock-rule yields (`result["rule_escapes"]`). It changes NO verdict — a late start is still
    reported at exactly the same severity — and only decides which ADVICE the BAND-3EV finding
    gives, because "move it" is wrong against a match the engine has already proven has nowhere
    better to go. Omitted ⇒ every finding keeps the pre-CAD-1 sentence, so an existing caller is
    unmoved. `td-report/v1` gains no input field."""
    cfg = cfg or ReportConfig.from_constraints(constraints, slate=slate)
    # DIV-1: the explicit argument wins, then the config's own value. `replace` copies rather
    # than mutating — a caller's ReportConfig is theirs, and this must not reach back into it.
    if mixed_level_1 is not None:
        cfg = dataclasses.replace(cfg, mixed_level_1=tuple(mixed_level_1))
    # VENUE-1 (additive, same shape as `mixed_level_1`): the run's recorded venue-rule escapes
    # (`build["result"]["venue_escapes"]`). Omitted, nothing is tolerated and every check grades
    # exactly as it did before the venue rules existed. `td-report/v1` gains no field.
    if venue_escapes is not None:
        cfg = dataclasses.replace(
            cfg, venue_escapes=frozenset(tuple(e) for e in venue_escapes))
    matches = sorted(matches, key=lambda m: (m.day, m.start, m.event,
                                             m.round_label, m.match_index))
    days = sorted({m.day for m in matches})
    compressed = set(cfg.compressed_days) or ({days[0], days[-1]} if days else set())
    pdays = _player_days(matches)
    three_event_days = {k for k, ms in pdays.items()
                        if {event_kind(m.event) for m in ms} == {"singles", "mixed", "doubles"}}

    findings = []
    findings += check_rest(matches, roster, cfg)
    # CAD-1: the recorded early-start yields, keyed (division, day, clock) — NOT by match id.
    # The reporter's own id is a composite of its division, round label and row index; the
    # engine's is a draw position. They are different namespaces and `scheduled_from_result`
    # carries neither across, which is by design (the adapter is a projection, not a join).
    # (division, day, clock) is the same shape the day-shape mirror's pass is keyed on, and it
    # is deliberately COARSER than a match: two matches of one division at one clock on one day
    # share the key, so if one is a recorded yield both read as recorded. That is acceptable
    # here and only here — this key decides which SENTENCE a finding carries, never whether the
    # finding exists or how severe it is.
    recorded_yields = {(r.get("event"), r.get("day"), r.get("start"))
                       for r in (rule_escapes or [])
                       if "day_bands" in (r.get("gate") or "day_bands")}
    findings += check_bands(matches, roster, cfg, compressed, recorded=recorded_yields)
    findings += check_floor_80(matches, roster, cfg, three_event_days)
    findings += check_cadence(matches, roster, cfg)
    findings += check_venue_late(matches, roster, cfg)
    findings += check_finals_unset(unscheduled, roster, cfg)
    findings += check_cap_slate(matches, roster, cfg)
    findings += check_start_window(matches, roster, cfg)      # D-37 / ruling 65 — warns only
    if draw_entries:
        findings += check_sametype_watch(matches, draw_entries, roster, cfg)
    # DRAW-1 (register rule 47, additive like `venue_escapes` — td-report/v1 gains no input
    # field, `seeds` and `recorded_seed_drops` arrive as arguments): warn-only seed-count
    # sanity over draw metadata. Omitted `seeds` ⇒ nothing to grade, exactly as before.
    if seeds:
        entrants_by_division: dict = {}
        for pid, events in (draw_entries or {}).items():
            for ev in events:
                entrants_by_division[ev] = entrants_by_division.get(ev, 0) + 1
        for ev in list(entrants_by_division):
            if event_kind(ev) != "singles":               # two players make a doubles team
                entrants_by_division[ev] = entrants_by_division[ev] // 2
        findings += check_seed_count(seeds, entrants_by_division, cfg,
                                     recorded_seed_drops=recorded_seed_drops)
    findings += check_held(held)          # HOLDVIS-1 (ruling 4) — empty/omitted ⇒ no section
    # GENDER-1 (2026-08-08): no new argument — `roster` is already the reporter's entry-list join
    # and `Player.gender` was already on it. The rung ships live on every existing caller, which
    # is the one place in this build nothing has to be threaded to avoid shipping inert.
    findings += check_mixed_gender(matches, roster, cfg)
    _cross_reference_evening(findings)    # RPT-2 copy item 3 — after both rungs, before sorting
    _display_order_findings(findings, cfg.mixed_level_1)      # DIV-1: rule 44, every finding
    findings.sort(key=_sort_key)
    # RPT-2 (A5c): APPENDED AFTER THE SORT, deliberately. The conflict record is the ENGINE's
    # order and this rung promises to reproduce it — sorting it would re-order a list the
    # reporter did not derive, and `_sort_key`'s last component (the JSON of `measured`) sorts
    # `{"recorded": 10}` before `{"recorded": 2}` anyway. `CONFLICTS` is last in `CODES`, so the
    # printed section and the JSON's own order agree without the sort's help.
    findings += check_conflicts(conflicts)

    by_code = {c: sum(1 for f in findings if f["code"] == c) for c in CODES}
    by_sev = {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITIES}
    return {
        "schema": SCHEMA,
        "source": dict(source or {}),
        "ingest_warnings": [str(w) for w in (ingest_warnings or ())],
        "findings": findings,
        "summary": {
            "counts_by_code": by_code,
            "counts_by_severity": by_sev,
            "total": len(findings),
            "matches_audited": len(matches),
            "player_commitments": sum(len(m.players) for m in matches),
            "days": days,
            "compressed_days": sorted(compressed),
            "three_event_player_days": len(three_event_days),
            "band_moves": by_code["BAND-3EV"],
        },
    }


# LANG-1 (A7c, glossary ruling 4): the section headings the PRINTED report shows. The internal
# code is no longer printed beside them — it stays in `CODES` and in every `td-report/v1`
# finding, which is the whole point of the ruling: the page loses a log-file word, the JSON
# loses nothing. Wording is the glossary's, under its ultra-concise house rule.
_HEADINGS = {
    "REST-XLEVEL": "Matches too close together",
    "BAND-3EV": "Too late for a player in 3 divisions",
    "FLOOR-80": "Too early for 80 and over",
    "CADENCE": "Two rounds in one day",
    "VENUE-LATE": "Semifinals, finals and 80+ away from the main site",
    "FINALS-UNSET": "Finals not scheduled",
    "CAP-SLATE": "More matches than courts",
    "START-WINDOW": "Late-afternoon starts",
    "SAMETYPE-WATCH": "Players in two draws of the same kind",
    "SEED-COUNT": "Seed counts against FAC II.A and Table 3",
    "HELD": "Held off the schedule",
    "MIXED-GENDER": "A Mixed team that is not one man and one woman",
    "CONFLICTS": "Rule breaks after your edits",
}

# Ruling 4's other half: severity RENDERS in plain words. `SEVERITIES` and every finding's
# `severity` value keep their `breach`/`warn`/`info` spelling in the JSON, untouched.
_SEVERITY_WORDS = {"breach": "Must fix", "warn": "Check", "info": "Info"}


def render_text(doc: dict) -> str:
    """The human-readable render. Same ordering as the JSON, so the two never disagree."""
    s = doc["summary"]
    src = doc["source"]
    out = ["SCHEDULE CHECK", "=" * 78,
           f"checked  : {', '.join(src.get('files', [])) or 'current schedule'}"
           + (f"  [{src['set']}]" if src.get("set") else ""),
           f"matches  : {s['matches_audited']:,} · "
           f"named entries {s['player_commitments']:,} · {len(s['days'])} days",
           f"found    : {s['total']}  ("
           + " · ".join(f"{n} {_SEVERITY_WORDS.get(k, k).lower()}"
                       for k, n in s["counts_by_severity"].items() if n) + ")",
           ""]
    if s.get("three_event_player_days"):
        out.append(f"in 3 divisions in a day: {s['three_event_player_days']} · "
                   f"moved for an early start: {s['band_moves']}")
        out.append("")
    # What was NOT audited, stated up front. A reader who does not know the reporter skipped every
    # round-robin match would read a clean report as a clean schedule.
    cov = src.get("coverage") or {}
    gaps = []
    if cov.get("rr_groups") and not cov.get("rr_stamps_present"):
        gaps.append(f"{cov['rr_groups']} round-robin group(s) carry no schedule in this source — "
                    f"the grids print scores where a raw draw prints day, time and venue. Those "
                    f"divisions are unaudited, not clean.")
    if cov.get("rr_group_slots"):
        gaps.append(f"{cov['rr_group_slots']} round-robin slot(s) put a whole group on court at "
                    f"once, so the source does not say who played whom. Every player's commitment "
                    f"and the court count are exact; only the pairings are unknown.")
    if cov.get("rr_rows_unresolved"):
        gaps.append(f"{cov['rr_rows_unresolved']} round-robin stamp(s) sit under a member the "
                    f"roster join could not resolve — excluded rather than guessed.")
    if cov.get("unresolved_entrants"):
        gaps.append(f"{cov['unresolved_entrants']} drawn entrant(s) the roster join could not "
                    f"resolve — excluded from every check rather than audited as nobody.")
    if cov.get("rr_matches_ingested"):
        out.append(f"round-robin: {cov['rr_matches_ingested']} matches audited "
                   f"({cov['rr_pairings_recovered']} with their pairing recovered) — round cadence "
                   f"is not checkable for these, the grid prints no round labels")
        out.append("")
    if gaps:
        out.append("NOT AUDITED")
        out.append("-" * 78)
        out += [f"  · {g}" for g in gaps]
        out.append("")
    # PREP-1: the ingest's own warnings, verbatim. A division the tool could not build has no
    # matches to audit, so without this section a clean report over a degraded ingest reads as a
    # clean tournament.
    if doc.get("ingest_warnings"):
        out.append("INGEST WARNINGS — what the tool could not build from this source")
        out.append("-" * 78)
        out += [f"  · {w}" for w in doc["ingest_warnings"]]
        out.append("")
    for code in CODES:
        rows = [f for f in doc["findings"] if f["code"] == code]
        if not rows:
            continue
        out.append(f"{_HEADINGS[code]}  ({len(rows)})")
        out.append("-" * 78)
        for f in rows:
            head = f"  {_SEVERITY_WORDS.get(f['severity'], f['severity'])}" \
                   + (f" {f['day']}" if f["day"] else "")
            out.append(f"{head}  {f['detail']}")
        out.append("")
    if s["total"] == 0:
        out.append("No findings. The schedule clears every check at its ruled defaults.")
    return "\n".join(out).rstrip() + "\n"


def _selftest():
    """Function-level smoke test (B-2): the checks fire on a hand-built schedule and the
    document is deterministic."""
    roster = {}

    class _P:
        def __init__(self, n):
            self.name = n
    for i, n in enumerate(("Alex Sample", "Robin Sample", "Chris Example"), start=1):
        roster[f"P{i}"] = _P(n)

    def M(event, lvl, rnd, k, day, start, venue, a, b):
        return ScheduledMatch(event, lvl, rnd, k, day, start, venue, (a, b))

    ms = [
        M("Men's 50 & over singles", "2", "R16", 1, "2026-01-26", 9 * 60, "MHCC", ("P1",), ("P3",)),
        M("Mixed 50 & over doubles", "1", "R16", 1, "2026-01-26", 10 * 60, "MHCC",
          ("P1", "P2"), None),
        M("Men's 80 & over doubles", "2", "Final", 1, "2026-01-27", 8 * 60, "ORLP", ("P3",), None),
    ]
    doc = report(ms, roster, unscheduled=[{"event": "Men's 50 & over singles", "level": "2",
                                           "round": "Final", "match_index": 1}],
                 source={"files": ["selftest"]},
                 draw_entries={"P1": ["Men's 50 & over singles", "Men's 60 & over singles"]})
    codes = doc["summary"]["counts_by_code"]
    assert codes["REST-XLEVEL"] == 1, codes
    assert codes["FLOOR-80"] == 1, codes
    assert codes["VENUE-LATE"] == 1, codes
    assert codes["FINALS-UNSET"] == 1, codes
    assert codes["SAMETYPE-WATCH"] == 1, codes
    rest = [f for f in doc["findings"] if f["code"] == "REST-XLEVEL"][0]
    assert rest["measured"]["cross_level"] is True and rest["measured"]["gap_minutes"] == 60
    assert rest["players"] == ["Alex Sample"], rest["players"]

    # Round-label aliasing: the closing-day cadence exception and the semifinal/final venue rule
    # must fire on BOTH spellings. Asserted on the short form, because the long form is the one
    # the product path happens to use — so only this direction can regress unnoticed.
    # RE-DERIVED AT CAD-1 (2026-08-18) for ruling R5, and the fixture now carries BOTH halves of
    # the narrowed exception, because the half that was missing is the one that shipped wrong:
    # the pair is graded once WITHOUT the same-day-finish switch (a breach — the TD never asked
    # for it) and once WITH the division named in it (info — his own instruction).
    div = "Women's 60 & over doubles"
    named = ReportConfig.from_constraints(
        {"schema": "td-constraints/v1",
         "same_day_finish": {"divisions": [div], "gap_minutes": 150}})
    for sf, fin in (("Semifinals", "Final"), ("SF", "F")):
        pair = [M(div, "2", sf, 1, "2026-02-01", 9 * 60, "ORLP", ("P1",), ("P3",)),
                M(div, "2", fin, 1, "2026-02-01", 13 * 60, "ORLP", ("P1",), ("P3",))]
        cad = [f for f in report(pair, roster)["findings"] if f["code"] == "CADENCE"]
        assert len(cad) == 1 and cad[0]["severity"] == "breach", \
            (f"an unasked-for closing-day pair must be a breach since R5 narrowed the exception "
             f"to TD-named same-day-finish divisions ({sf!r}/{fin!r}): {cad}")
        cad = [f for f in report(pair, roster, cfg=named)["findings"] if f["code"] == "CADENCE"]
        assert len(cad) == 1 and cad[0]["severity"] == "info", \
            f"closing-day exception did not fire for {sf!r}/{fin!r} on a NAMED division: {cad}"
        assert cad[0]["measured"]["td_named_same_day_finish"] is True, cad[0]["measured"]
        vl = [f for f in report(pair, roster)["findings"] if f["code"] == "VENUE-LATE"]
        assert len(vl) == 2, f"off-site semifinal/final not flagged for {sf!r}/{fin!r}: {vl}"
    assert json.dumps(doc, sort_keys=True) == json.dumps(
        report(ms, roster, unscheduled=[{"event": "Men's 50 & over singles", "level": "2",
                                         "round": "Final", "match_index": 1}],
               source={"files": ["selftest"]},
               draw_entries={"P1": ["Men's 50 & over singles", "Men's 60 & over singles"]}),
        sort_keys=True), "report is not deterministic"
    # LANG-1 (A7c, glossary ruling 4): the printed page carries no code word and no
    # [BREACH]/[WARN]/[INFO]; the DOCUMENT still carries both. Asserted as a pair here, on the
    # same doc, because either half alone would let the separation rot unnoticed.
    txt = render_text(doc)
    assert txt.startswith("SCHEDULE CHECK")
    assert not any(c in txt for c in CODES), "an internal code word reached the printed report"
    assert not any(s in txt for s in ("[BREACH]", "[WARN]", "[INFO]")), \
        "a bracketed severity reached the printed report"
    assert {f["code"] for f in doc["findings"]} <= set(CODES), "the JSON lost its codes"
    assert {f["severity"] for f in doc["findings"]} <= set(SEVERITIES), \
        "the JSON's severity values moved — ruling 4 keeps them exactly as they were"
    print("schedule_report selftest OK")
    return True


if __name__ == "__main__":
    _selftest()
