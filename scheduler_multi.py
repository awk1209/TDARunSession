"""
WynTennis Multi-Event Scheduling Engine (Doubles / Mixed / Singles together)
============================================================================
Superset of scheduler.py. Adds:
  - TEAMS as entries (1 player = singles, 2 players = doubles/mixed)
  - MULTIPLE events sharing ONE court pool and date range
    (e.g. Men's Doubles + Women's Doubles + Mixed running the same weekend)
  - Cross-event conflict tracking at the INDIVIDUAL HUMAN level:
      * a person is never scheduled in two matches at once, across ALL events
      * a person gets the recovery gap between any two of their matches,
        across ALL events (uses the larger of the two events' recovery values)
  - BYES for non-power-of-two draws (common in doubles); a bye is a walkover
    that takes no court/time and propagates the advancing team's identity
  - Per-event match length (doubles often runs a shorter format)

WHAT IT CAN AND CANNOT DECONFLICT BY PERSON (be honest about this):
  - Round-robin matches: ALL identities known -> fully deconflicted by person.
  - Elimination Round 1 + any bye-advanced team: identities known -> deconflicted.
  - Elimination Round 2+: winners not yet known -> per-person conflicts cannot be
    pre-resolved across events. Handled by within-event court/feeder/recovery logic;
    re-run once the draw resolves to deconflict later rounds by person.

The single-event scheduler.py remains the engine for one simple event; this
module is what the assistant uses whenever 2+ draws share courts OR entries are
doubles/mixed teams with overlapping players.
"""

from __future__ import annotations
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
import math
import re
from typing import Optional

from scheduler import _is_power_of_two, _round_name, _circle_pairings  # reuse proven helpers


BYE = "__BYE__"


# --------------------------------------------------------------------------
# MODELS
# --------------------------------------------------------------------------
@dataclass
class Team:
    tid: str                       # unique within its event, e.g. "MD-T1"
    members: list[str]             # human names: 1 (singles) or 2 (doubles/mixed)

    def label(self) -> str:
        return "/".join(self.members)


@dataclass
class EventSpec:
    name: str                      # "Men's Doubles", "Mixed Doubles", ...
    fmt: str                       # single_elim | compass | round_robin
    teams: list[Team]
    group_size: int = 4            # RR only
    match_minutes: int = 75        # doubles often shorter (8-game pro set / no-ad)
    # OI-37 b1 — PRESERVE, discharged 2026-08-02 (ENG-1). This chain (`EventSpec.recovery_minutes`
    # -> `Match.recovery_minutes` -> the third slot of every `human_busy` entry) is carried but not
    # read by any gate: rest is start-to-start (R1). OI-37 proposed deleting it; the Operator ruled
    # PRESERVE, because it is the substrate the DEFERRED layered end-to-start rest floor reuses —
    # the same floor whose absence is why D-1 caps match blocks at 90. ENG-1 reopened this file
    # under a lifted freeze and deliberately LEFT IT ALONE. The disposition is recorded here and in
    # `brief.md` because a preserve ruling that leaves no trace is indistinguishable from an
    # oversight at the next visit — which is exactly how it came to be proposed for deletion twice.
    recovery_minutes: int = 60     # within-event recovery for this event's players
    precedence: int = 0            # lower schedules earlier (use to order finals days)
    sanctioned: bool = False
    utr_verified: bool = False
    max_matches_per_day: Optional[int] = None   # per-(player, day) cap for this division; ENG-1 routes td-constraints match_caps here (was FAC Table 9 at intake)
    earliest_start: Optional[str] = None         # per-division earliest slot "HH:MM" (AVOID-3: 80+ -> 09:30); None = no floor
    finals_earliest: Optional[str] = None        # ENG-1/F-4/M6: earliest slot for this division's FINAL ROUND ONLY "HH:MM"; None = no finals floor. The ROUND-AWARE sibling of earliest_start — see _final_rounds


@dataclass
class MultiConfig:
    tournament_name: str
    num_courts: int
    dates: list[str]
    events: list[EventSpec]
    daily_start: str = "08:00"
    daily_end: str = "18:00"
    end_of_day_buffer_minutes: int = 45
    global_recovery_minutes: int = 60   # legacy end-to-start floor; superseded by min_start_to_start_minutes (R1), retained for back-compat
    min_start_to_start_minutes: int = 180   # R1: a player's matches must start >= this many minutes apart (TD-set; 3h default)
    courts_by_day: dict = field(default_factory=dict)   # date -> concurrent courts; falls back to num_courts
    court_locations: dict = field(default_factory=dict)  # date -> [(lo_court, hi_court, location_id)]; inert labeling only (SCH-01a)
    transit_minutes: dict = field(default_factory=dict)  # sorted "A|B" -> minutes; empty = no transit (SCH-01b)
    location_hours: dict = field(default_factory=dict)   # location_id -> {date: (start, end)}; empty = tournament-wide hours (OI-23)
    placement_policy: dict = field(default_factory=dict)  # td-constraints/v1 placement policy (Phase 2); empty = no staging (byte-identical)
    local_players: set = field(default_factory=set)      # names within the TD home region (zip-prefix); empty = no local rule (Phase 2)
    assigned_days: dict = field(default_factory=dict)    # R7-2: (event, rnd) -> "YYYY-MM-DD" master-assigned day; empty = off (byte-identical)
    morning_caps: dict = field(default_factory=dict)     # R7-3: (location_id, date) -> ("HH:MM", morning_courts) — fewer courts before the switch time (member play); empty = flat caps (byte-identical)
    # ENG-1 (2026-08-02) — the director's rules, all four defaulted OFF so a bare doc is byte-identical.
    day_shape: dict = field(default_factory=dict)        # {"order": ["singles","mixed","doubles"], "on_no_slot": "place_and_record"}; empty = off. A GATE WITH A RECORDED ESCAPE (ruling 73)
    day_bands: dict = field(default_factory=dict)        # {"singles_by","mixed_at","doubles_from","scope"} — three-event players' head start, read "at or earlier" (D-40); empty = off
    same_day_finish: dict = field(default_factory=dict)  # {"divisions": [...], "gap_minutes": 150} — per division, TD-flipped, NEVER automatic (D-41); [] = off everywhere
    day_shape_exceptions: set = field(default_factory=set)  # (mid, day, start) the day shape could not seat in shape; RECORDED like a spill and TOLERATED by the mirror (ruling 73). Keyed on the SLOT, so moving the match revokes the pass
    rule_escapes: set = field(default_factory=set)       # (mid, day, start) only the relaxed ladder could seat — band / finals floor; same tolerate-and-revoke rule
    # VENUE-1 (2026-08-05) — the venue axis, rules 6/31/38/39/40/41/43. All four default empty so
    # a bare doc is byte-identical: with `venue_rules` empty no predicate is consulted at all.
    venue_rules: dict = field(default_factory=dict)      # per-rule switches, {} = every venue rule OFF. Keys: main_site_ages (38), main_site_finals (39), main_site_l1_mixed (40), l1_mixed_latest_start (31, re-cut at BUDGET-1 — was l1_mixed_lights_off), rank_order (43), peak_window (6)
    venue_rules_migrated: list = field(default_factory=list)  # BUDGET-1 (R19): plain-English notes for a doc written against a RETIRED rule key, translated to its replacement rather than refused. Empty on every doc written after the change. Reported, never scheduled
    venue_names: dict = field(default_factory=dict)      # location id -> the TD's display name (D-49). REPORTED, never scheduled; venue ids stay the load-bearing identity
    venue_order: list = field(default_factory=list)      # rule 43: the TD's fill order, == the slate's `locations` array order. venue_order[0] is the MAIN SITE rules 38/39/40 are written against — a position in his list, never the literal string "MHCC". Empty = no slate (the self-test path)
    venue_l1_mixed: set = field(default_factory=set)     # division names this run treats as Level-1 Mixed — rule 45's ALREADY-RESOLVED answer, handed in as DATA. `division_order` is never imported here; the import direction is DIV-1's guard
    venue_final_rnd: dict = field(default_factory=dict)  # event -> the round that IS its final (rule 39 needs semis AND finals). Built once per run from `_final_rounds`; empty = elimination rounds unknown, so rule 39 stands down
    venue_lights_on: dict = field(default_factory=dict)  # rule 31: location id -> "HH:MM" the venue's lights come on. A CUTOFF for rule 31, and from LIGHTS-1 also the hour rule 48's ceiling starts
    venue_lit_courts: dict = field(default_factory=dict)  # LIGHTS-1 / rule 48: location id -> lighted-court count. A CEILING from `venue_lights_on` onward — usable courts become min(courts, lit_courts) — so it can only ever take capacity away. Empty = off (byte-identical), and a count is carried only with its hour
    venue_escapes: set = field(default_factory=set)      # (mid, day, start, location) no venue the rules prefer could hold this match, so it was PLACED ANYWAY and recorded (rule 41). Keyed on the SLOT + location, so moving the match revokes the pass — the day_shape_exceptions pattern (ruling 73)
    day_shape_no_precedent: set = field(default_factory=set)  # NEAR-1 A1 (2026-08-06): mids the cross-day fallback placed (the spills). They set NO day-shape precedent — excluded from the kind windows and judged symmetrically by `day_shape_violations`. Stamped by `_build_and_place`, read by the `validate_multi` mirror, so record and mirror share ONE input. Empty (the default, and every no-map run) = pre-A1 behaviour exactly. Engine-internal; never emitted, no contract carries it


@dataclass
class Match:
    mid: str
    event: str
    rnd: int
    label: str
    draw: str                      # main | consolation | rr
    precedence: int
    match_minutes: int
    recovery_minutes: int
    feeders: list[str] = field(default_factory=list)   # must finish first (same event)
    lineage: list[str] = field(default_factory=list)   # feeder mids for recovery
    humans: set[str] = field(default_factory=set)      # KNOWN human names in this match
    team_a: list[str] = field(default_factory=list)    # one side's members (when known)
    team_b: list[str] = field(default_factory=list)    # other side's members (when known)
    scheduled_needed: bool = True                      # False for bye walkovers
    decided_team: Optional[str] = None                 # bye: who advances
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    court: Optional[int] = None
    day: Optional[str] = None
    location: Optional[str] = None                      # venue id of the assigned court; inert label (SCH-01a)


# --------------------------------------------------------------------------
# DRAW BUILDERS (team-aware)
# --------------------------------------------------------------------------
def _next_pow2(n: int) -> int:
    p = 1
    while p < n:
        p *= 2
    return p


def _is_bye_team(t) -> bool:
    return getattr(t, "tid", None) == BYE or not t.members


def _build_elim_positional(ev: EventSpec, prefix: str) -> list[Match]:
    """Honor an explicit bracket: entrants given in slot order, BYE entries
    occupying real bracket positions (as the registration platform placed them)."""
    slots = ev.teams[:]
    size = len(slots)
    if size < 2 or (size & (size - 1)) != 0:
        raise ValueError(f"{ev.name}: explicit draw needs a power-of-two slot count "
                         f"(fill with BYE entries); got {size}")
    rounds = int(math.log2(size))
    members = {t.tid: set(t.members) for t in slots if not _is_bye_team(t)}
    matches, known_after, prev_ids = [], {}, []
    for m in range(size // 2):
        a, b = slots[2 * m], slots[2 * m + 1]
        a_bye, b_bye = _is_bye_team(a), _is_bye_team(b)
        mid = f"{prefix}-R1-M{m+1}"
        if a_bye and b_bye:
            raise ValueError(f"{ev.name}: BYE vs BYE at slots {2*m+1}-{2*m+2}")
        if a_bye or b_bye:
            real = b if a_bye else a
            mt = Match(mid=mid, event=ev.name, rnd=1,
                       label=f"{ev.name} R1 M{m+1}: {real.label()} (BYE)",
                       draw="main", precedence=ev.precedence,
                       match_minutes=ev.match_minutes, recovery_minutes=ev.recovery_minutes,
                       humans=set(real.members), scheduled_needed=False, decided_team=real.tid)
            known_after[mid] = real.tid
        else:
            mt = Match(mid=mid, event=ev.name, rnd=1,
                       label=f"{ev.name} R1 M{m+1}: {a.label()} vs {b.label()}",
                       draw="main", precedence=ev.precedence,
                       match_minutes=ev.match_minutes, recovery_minutes=ev.recovery_minutes,
                       humans=set(a.members) | set(b.members),
                       team_a=sorted(a.members), team_b=sorted(b.members))
            known_after[mid] = None
        matches.append(mt); prev_ids.append(mid)
    for r in range(2, rounds + 1):
        this_ids = []
        for m in range(size // (2 ** r)):
            f1, f2 = prev_ids[2 * m], prev_ids[2 * m + 1]
            mid = f"{prefix}-R{r}-M{m+1}"
            # CARD-1 (metadata only, ruling 86): keep the SIDE structure, not just the flat
            # union. This is the builder the WWTC lane actually uses — printed draws carry BYE
            # sentinels, so `build_elim_teams` hands off here (`:207`) and its own rounds-2+ loop
            # never runs on this field. Both loops are filled so the two cannot drift.
            kt1, kt2 = known_after.get(f1), known_after.get(f2)
            known_h = set()
            for kt in (kt1, kt2):
                if kt:
                    known_h |= members.get(kt, set())
            mt = Match(mid=mid, event=ev.name, rnd=r,
                       label=f"{ev.name} {_round_name(r, rounds)} M{m+1}", draw="main",
                       precedence=ev.precedence, match_minutes=ev.match_minutes,
                       recovery_minutes=ev.recovery_minutes,
                       feeders=[f1, f2], lineage=[f1, f2], humans=known_h,
                       team_a=sorted(members.get(kt1, set())) if kt1 else [],
                       team_b=sorted(members.get(kt2, set())) if kt2 else [])
            known_after[mid] = None
            matches.append(mt); this_ids.append(mid)
        prev_ids = this_ids
    return matches


def build_elim_teams(ev: EventSpec, prefix: str) -> list[Match]:
    if any(_is_bye_team(t) for t in ev.teams):
        return _build_elim_positional(ev, prefix)
    teams = ev.teams[:]
    n = len(teams)
    if n < 2:
        raise ValueError(f"{ev.name}: need at least 2 teams")
    size = _next_pow2(n)
    rounds = int(math.log2(size))
    members = {t.tid: set(t.members) for t in teams}

    # Distribute byes correctly: never pair BYE vs BYE.
    #   num_bye teams get a walkover; the rest play R1.
    #   (Final seed-aware bye placement is done in the registration platform;
    #    here we guarantee structural correctness — each bye advances one real team.)
    num_bye = size - n                 # teams receiving a bye
    num_play = n - num_bye             # teams that actually play R1 (always even)
    playing = [t.tid for t in teams[:num_play]]
    bying = [t.tid for t in teams[num_play:]]   # exactly num_bye teams

    # Build R1 pairings: real-vs-real matches first, then real-vs-BYE walkovers.
    r1_pairs: list[tuple] = []
    for k in range(0, len(playing), 2):
        r1_pairs.append((playing[k], playing[k + 1]))
    for tid in bying:
        r1_pairs.append((tid, BYE))

    matches: list[Match] = []
    known_after: dict[str, Optional[str]] = {}
    prev_ids = []
    for m, (a, b) in enumerate(r1_pairs):
        mid = f"{prefix}-R1-M{m+1}"
        if b == BYE:
            mt = Match(mid=mid, event=ev.name, rnd=1,
                       label=f"{ev.name} R1 M{m+1}: {teams_lbl(a, members, teams)} (BYE)",
                       draw="main", precedence=ev.precedence,
                       match_minutes=ev.match_minutes, recovery_minutes=ev.recovery_minutes,
                       humans=members.get(a, set()),
                       scheduled_needed=False, decided_team=a)
            known_after[mid] = a
        else:
            mt = Match(mid=mid, event=ev.name, rnd=1,
                       label=f"{ev.name} R1 M{m+1}: {teams_lbl(a, members, teams)} vs {teams_lbl(b, members, teams)}",
                       draw="main", precedence=ev.precedence,
                       match_minutes=ev.match_minutes, recovery_minutes=ev.recovery_minutes,
                       humans=members.get(a, set()) | members.get(b, set()),
                       team_a=sorted(members.get(a, set())),
                       team_b=sorted(members.get(b, set())))
            known_after[mid] = None
        matches.append(mt)
        prev_ids.append(mid)

    # Rounds 2..final
    for r in range(2, rounds + 1):
        n_matches = size // (2 ** r)
        this_ids = []
        for m in range(n_matches):
            f1, f2 = prev_ids[2 * m], prev_ids[2 * m + 1]
            mid = f"{prefix}-R{r}-M{m+1}"
            rname = _round_name(r, rounds)
            # identity may be partially known if a feeder was decided by a bye
            known_h = set()
            kt1, kt2 = known_after.get(f1), known_after.get(f2)
            if kt1:
                known_h |= members.get(kt1, set())
            if kt2:
                known_h |= members.get(kt2, set())
            # CARD-1 (metadata only, ruling 86): keep the SIDE structure this loop already
            # computes. `known_h` unions both feeders' advancing teams into one flat set, which
            # is all placement needs — but it is also the only record of who partners whom, and
            # dropping it is why a bye pair renders as two opponents (OI-45/OI-46). Filling
            # team_a/team_b costs nothing on the placement path: no scheduling math, invariant,
            # `_humans_ok` or court-identity check reads either field. Empty stays empty when a
            # feeder is undecided, exactly as before.
            mt = Match(mid=mid, event=ev.name, rnd=r,
                       label=f"{ev.name} {rname} M{m+1}", draw="main",
                       precedence=ev.precedence, match_minutes=ev.match_minutes,
                       recovery_minutes=ev.recovery_minutes,
                       feeders=[x for x in (f1, f2)], lineage=[x for x in (f1, f2)],
                       humans=known_h,
                       team_a=sorted(members.get(kt1, set())) if kt1 else [],
                       team_b=sorted(members.get(kt2, set())) if kt2 else [])
            # this match's winner is known only if BOTH feeders were decided byes
            known_after[mid] = None
            matches.append(mt)
            this_ids.append(mid)
        prev_ids = this_ids

    # bye walkovers don't gate on feeders needing a court; downstream feeders that
    # point at a bye match are fine because bye matches have end=None handled below
    return matches


def teams_lbl(tid, members, teams) -> str:
    for t in teams:
        if t.tid == tid:
            return t.label()
    return tid


def build_rr_teams(ev: EventSpec, prefix: str) -> list[Match]:
    teams = ev.teams
    if len(teams) < 3:
        raise ValueError(f"{ev.name}: round robin needs >=3 teams")
    members = {t.tid: set(t.members) for t in teams}
    labels = {t.tid: t.label() for t in teams}
    ids = [t.tid for t in teams]
    matches = []
    for ri, (a, b) in enumerate(_circle_pairings(ids), start=1):
        mid = f"{prefix}-M{ri}-{a}v{b}"
        matches.append(Match(
            mid=mid, event=ev.name, rnd=ri,
            label=f"{ev.name}: {labels[a]} vs {labels[b]}", draw="rr",
            precedence=ev.precedence, match_minutes=ev.match_minutes,
            recovery_minutes=ev.recovery_minutes,
            humans=members[a] | members[b],
            team_a=sorted(members[a]),
            team_b=sorted(members[b]),
        ))
    return matches


# --------------------------------------------------------------------------
# SCHEDULER
# --------------------------------------------------------------------------
def _courts_on(cfg: MultiConfig, day: str) -> int:
    """Concurrent courts available on `day` (per-day override, else num_courts)."""
    return cfg.courts_by_day.get(day, cfg.num_courts)


def _location_for(cfg: MultiConfig, day: str, court: Optional[int]) -> Optional[str]:
    """Derived label only (SCH-01a): map a placed (day, court) to its venue id via the
    inert court_locations layout. Returns None when no layout is supplied (today's cfg),
    so placement is unaffected and readers that ignore location are unchanged."""
    if court is None:
        return None
    for lo, hi, loc in cfg.court_locations.get(day, []):
        if lo <= court <= hi:
            return loc
    return None


def _slots(cfg: MultiConfig):
    starts = []
    for d in cfg.dates:
        s = datetime.strptime(f"{d} {cfg.daily_start}", "%Y-%m-%d %H:%M")
        e = datetime.strptime(f"{d} {cfg.daily_end}", "%Y-%m-%d %H:%M") - timedelta(
            minutes=cfg.end_of_day_buffer_minutes)
        t = s
        while t < e:
            starts.append((d, t))
            t += timedelta(minutes=15)   # 15-min granularity; matches vary in length
    return sorted(starts, key=lambda x: x[1])


def _player_event_counts(events: list) -> dict:
    """name -> number of distinct divisions (events) the player is entered in. A static roster
    property (schedule-independent -> deterministic). Drives the BP-2 staging tier in
    _staging_rank ONLY — and note the earliest tier is 3+ events, not 2+.
    NOT a rest input: _humans_ok applies the start-to-start minimum identically to every
    player, whatever this count says. (Corrected 2026-07-27 — the prior text claimed this was
    "the multi-division identity the 3h rest rule protects"; _humans_ok does not support it,
    and badge copy written from that sentence would be wrong. See brief.md ruling 21.)"""
    seen: dict = {}
    for ev in events:
        names = {h for t in ev.teams for h in t.members}
        for h in names:
            seen[h] = seen.get(h, 0) + 1
    return seen


def _multidivision_players(events: list) -> set:
    """Names entered in >=2 distinct divisions (events) — same identity as B3's roster report,
    derived from the event counts."""
    return {h for h, n in _player_event_counts(events).items() if n >= 2}


def _staging_rank(m: "Match", cfg: MultiConfig, evcounts: dict):
    """BP-2 placement priority (lower = earlier slots), a soft secondary sort key. The event tier
    comes from the match's **max player event-count**: 3+ events -> earliest (0), 2 events -> mid (1),
    singles-only (1 event) -> latest (2). `locals_early` (LOCALS-EARLY, CEO 2026-07-25 — resolves
    DISC-4, reversing the old local-late rule) is a finer *within-tier* nudge: an all-local match
    takes the FRONT of its tier, a match with any traveling player the back — non-locals keep their
    mornings for travel. The tier always wins (rest feasibility over locality, CEO).
    Off (uniform) when no placement_policy is set, so the order is byte-identical to pre-Phase-2.
    Pure function of the policy, the match's humans, and the static counts/local sets -> deterministic."""
    policy = cfg.placement_policy
    if not policy:
        return (1, 0)
    humans = m.humans
    maxev = max((evcounts.get(h, 1) for h in humans), default=1)
    if policy.get("stage_multidivision_early"):
        etier = 0 if maxev >= 3 else (1 if maxev == 2 else 2)   # BP-2: 3ev early, 2ev mid, singles late
    else:
        etier = 1
    # A team is "local" only if EVERY player is local — one traveling partner needs travel time.
    # Flag off, no humans, or no configured locals -> uniform (inert, not wrong).
    ltier = 1 if (policy.get("locals_early") and humans
                  and not all(h in cfg.local_players for h in humans)) else 0
    return (etier, ltier)


def _true_round_of(cfg: MultiConfig, event: str, rnd: int) -> int:
    """The real round number for a match's `rnd`.

    For a round-robin GROUP `rnd` is a FLAT match index in circle-method order (see
    wwtc_pipeline._expand_rr_groups), so several matches of the SAME round legitimately share a
    day. Comparing flat indices would read every group as a cadence violation — which is why a
    naive count of the real field says 23 where the true figure is 6.
    """
    for ev in cfg.events:
        if ev.name == event:
            if ev.fmt == "round_robin":
                return (rnd - 1) // max(len(ev.teams) // 2, 1) + 1
            break
    return rnd


# --------------------------------------------------------------------------
# ENG-1 (2026-08-02) — the director's rules. Each helper below is written ONCE and read by BOTH
# the placement loop (`_scan`) and the `validate_multi` mirror, so the two can never drift into
# disagreeing. A schedule the engine builds and then reports as conflicted breaks 0-conflicts,
# which is the invariant that never bends (§8 invariant 9).
# --------------------------------------------------------------------------

# M5 / brief §8A row 30: the TD's day shape. Day-LEVEL order already exists as
# master_schedule._TYPE_ORDER; this is the same three-way split applied at the CLOCK. Deliberately
# NOT wwtc_ingest._is_doubles — that predicate is a division-KIND test consumed at :517 and :807
# for draw building and recovery minutes, and widening it there would move things ENG-1 has not
# measured (brief §15 decision 2's closing note).
_KIND_ORDER = {"singles": 0, "mixed": 1, "doubles": 2}


def _event_kind(event: str) -> str:
    """singles | mixed | doubles for the day shape. Mirrors master_schedule._etype exactly."""
    low = event.lower()
    if "mixed" in low:
        return "mixed"
    if "doubles" in low:
        return "doubles"
    return "singles"


def kind_order_of(cfg: MultiConfig) -> dict:
    """kind -> rank, FROM the TD's configured `day_shape.order`.

    The contract validates `order` as a real permutation, so it has to be a real permutation —
    reading it for truthiness alone and then enforcing a module constant would make it the
    presented-and-inactive class WIRE-1 spent a build removing, and would enforce the OPPOSITE of a
    reversed order with no error anywhere. A kind the TD leaves out of the list is unranked and the
    shape rule simply does not bind it, which is why a partial list cannot silently switch the full
    three-way gate on. Empty/omitted => `{}` => the rule is off.
    """
    order = (cfg.day_shape or {}).get("order") or []
    return {k: i for i, k in enumerate(order)}


def _kind_rank(event: str, order: dict = None) -> int:
    """This match's rank in the configured order, or None when the order does not bind its kind."""
    if order is None:
        order = _KIND_ORDER
    return order.get(_event_kind(event))


def _final_rounds(all_matches: list, cfg: MultiConfig) -> dict:
    """event -> the round number that IS that division's final.

    ENG-1/F-4/M6, ruling 74: the 09:00 floor is FINALS ONLY, so the gate has to know which round
    is the final. `earliest_start` cannot express this — it is event-keyed and ROUND-BLIND, and
    flooring whole divisions at 09:00 (the naive path) moves 536 of 760 placements where the rule
    asks for 8. This is the round-aware sibling G4 names.

    Elimination formats only. A round-robin group's last round is not a championship match, and
    ruling 74's measured scope is the 8 elimination finals; RR sits inside the ruling-71 carve-out
    and is built as specified, not extended here.
    """
    fmt = {ev.name: ev.fmt for ev in cfg.events}
    finals: dict = {}
    for m in all_matches:
        if fmt.get(m.event) not in ("single_elim", "compass"):
            continue
        if m.rnd > finals.get(m.event, 0):
            finals[m.event] = m.rnd
    return finals


def _band_setup(cfg: MultiConfig, all_matches: list):
    """(bands, band_days) for the TD's 9:00 / 12:00 / 15:00 head start — D-40 / ruling 67.

    `bands` maps kind -> the latest time a match of that kind may START, read **"at or earlier"**:
    his own words are *"all three-event players start at 9:00, 12:00, and 3:00 … this ensures they
    get on court before other matches scheduled 30 minutes later"*, and his real week starts 103
    matches before 9:00, 21 of them his own hand-built head starts for exactly these players. An
    exact-9:00 reading would move his own head starts LATER, which is the opposite of the rule.

    `band_days` is the set of (player, day) the rule binds. Scope is NARROW by default — triple
    days only, pending NQ-1 — and the day comes from the MASTER-ASSIGNED map, not from where a
    match finally landed, so placement and the `validate_multi` mirror read one identical answer
    even where a match spilled. `scope: "all_days"` is the broad reading.
    """
    spec = cfg.day_bands or {}
    if not spec:
        return {}, set()
    bands = {}
    for kind, key in (("singles", "singles_by"), ("mixed", "mixed_at"), ("doubles", "doubles_from")):
        v = spec.get(key)
        if v:
            bands[kind] = datetime.strptime(v, "%H:%M").time()
    if not bands:
        return {}, set()
    if spec.get("scope", "triple_days") == "all_days":
        return bands, None                      # None == "every player-day", no membership test
    seen: dict = {}
    for m in all_matches:
        if not m.scheduled_needed or not m.humans:
            continue
        # The MASTER-ASSIGNED day only — never `m.day`. `_build_and_place` calls this BEFORE
        # placement, where every `m.day` is None, and `validate_multi` calls it AFTER, where they
        # are real dates; an `or m.day` fallback therefore gave the gate one answer and the mirror
        # another, and the engine built schedules it then reported as DAY BAND conflicts (0
        # conflicts is the invariant that never bends). With no day map the narrow scope cannot
        # know which day a match will land on, so it binds nothing — inert on BOTH sides, which is
        # the honest reading. `scope: "all_days"` needs no map and is unaffected.
        day = (cfg.assigned_days or {}).get((m.event, m.rnd))
        if day is None:
            continue
        for h in m.humans:
            seen.setdefault((h, day), set()).add(m.event)
    return bands, {k for k, evs in seen.items() if len(evs) >= 3}


def _in_band(m, day, st, bands, band_days) -> bool:
    """Whether starting `m` on `day` at `st` honours the day bands. Read by BOTH sites."""
    if not bands or not m.humans:
        return True
    lim = bands.get(_event_kind(m.event))
    if lim is None or st.time() <= lim:
        return True
    return not (band_days is None or any((h, day) in band_days for h in m.humans))


def _same_day_finish_pairs(all_matches: list, cfg: MultiConfig) -> dict:
    """`mid -> (division, is_final)` for the matches the same-day-finish exception can reach.

    D-41 ships a per-division switch the TD flips so a division can finish on ONE day because its
    players asked to leave early. The ruled gap is 150 minutes; the engine's rest floor is 180.
    The TD's own 2026 instance therefore breaches his own stated 3-hour rule by 30 minutes, and
    ruling 72 resolved it as a NAMED EXCEPTION rather than by moving either number.

    THE EXCEPTION IS EXACTLY THIS WIDE and no wider:
      * only a division the TD has NAMED in `same_day_finish.divisions` (never inferred);
      * only between that division's FINAL and its PENULTIMATE round — the two matches the switch
        actually joins, NOT any two matches drawn from those two rounds. Two penultimate-round
        matches of the same division on the same day keep the full 180-minute floor, which is why
        this records `is_final` per match rather than a flat set of ids;
      * everything else in that division, on that day, keeps the full 180-minute floor.

    Read by all FOUR enforcement sites — `_humans_ok`, `_lineage_rested` and both `validate_multi`
    mirrors — through `_s2s_for`. Written once, read four times: if placement and the validator
    disagreed here the engine would build a schedule and then report it broken.
    """
    named = {e for e in (cfg.same_day_finish or {}).get("divisions", []) or []}
    if not named:
        return {}
    finals = _final_rounds(all_matches, cfg)
    out = {}
    for m in all_matches:
        f = finals.get(m.event)
        if m.event in named and f is not None and f >= 2 and m.rnd in (f, f - 1):
            out[m.mid] = (m.event, m.rnd == f)
    return out


def _s2s_for(a_mid, b_mid, cfg: MultiConfig, exempt: dict) -> int:
    """The start-to-start floor binding a PAIR of matches, in minutes.

    The full `min_start_to_start_minutes` everywhere, EXCEPT between a named division's FINAL and
    its PENULTIMATE-round match, where the TD's `gap_minutes` binds instead. `gap_minutes` is
    load-bearing twice — it sets the spacing AND it defines the exception's width — so a TD who
    raises it to 180 gets a same-day finish with no exception in play at all, and one who lowers
    it widens the exception knowingly. This is the ONLY place the 180-minute floor ever yields.
    """
    if exempt:
        a, b = exempt.get(a_mid), exempt.get(b_mid)
        if a and b and a[0] == b[0] and a[1] != b[1]:      # same division, final + penultimate
            gap = (cfg.same_day_finish or {}).get("gap_minutes", 150)
            return min(cfg.min_start_to_start_minutes, gap)
    return cfg.min_start_to_start_minutes


def day_shape_violations(all_matches: list, order: dict = None,
                         no_precedent: frozenset = frozenset()) -> list:
    """Every placed match that sits OUT of the TD's day shape, from the FINISHED schedule.

    Out of shape == a later-kind match starting before an earlier-kind match of that same day
    starts (§5(b): "before an earlier-kind match of that day is under way"). Measured this way the
    committed 2026 field carries 150 of 760, per day 0·21·20·38·4·18·23·18·0·8.

    Computed from the finished schedule rather than flagged at placement time, and that is
    deliberate — the same reasoning FIX-1 recorded for cadence. A placement-time flag cannot see
    the whole truth: a doubles match that is perfectly in shape when it lands can be put out of
    shape later, when a mixed match of a subsequent round arrives on that day behind it. The
    recorded escape set and the validator mirror therefore read THIS one function, so the mirror
    can never report the engine's own legal fallbacks as conflicts.

    `no_precedent` (NEAR-1 A1, 2026-08-06): mids the cross-day fallback placed — spills. They
    are EXCLUDED from the per-day kind windows, so one exception cannot indict the
    normally-placed matches around it, and each is judged SYMMETRICALLY against those clean
    windows — both directions, the placement gate's own symmetry, because the one-sided default
    cannot see an earlier-kind match arriving late. An empty set is byte-identical to the pre-A1
    reading. Callers must pass the SAME set the recorder used (`cfg.day_shape_no_precedent`) or
    the record and the mirror read two different schedules.
    """
    by_day: dict = {}
    for m in all_matches:
        if m.start is not None:
            by_day.setdefault(m.day, []).append((_kind_rank(m.event, order), m))
    out = []
    for day in sorted(by_day):
        ranked = [(r, m) for r, m in by_day[day] if r is not None]   # unranked kinds do not bind
        latest: dict = {}                       # kind rank -> latest start of that kind, this day
        earliest: dict = {}                     # A1: the spills' symmetric reading needs it
        for r, m in ranked:
            if m.mid in no_precedent:
                continue                        # A1: a spill sets no precedent, either direction
            if r not in latest or m.start > latest[r]:
                latest[r] = m.start
            if r not in earliest or m.start < earliest[r]:
                earliest[r] = m.start
        hits = []
        for r, m in ranked:
            if any(er < r and m.start < ls for er, ls in latest.items()):
                hits.append(m)                  # the ruled §5(b) reading, unchanged
            elif m.mid in no_precedent and \
                    any(lr > r and es < m.start for lr, es in earliest.items()):
                hits.append(m)                  # A1: the spill itself, judged both ways
        out.extend(sorted(hits, key=lambda x: (x.start, x.mid)))
    return out


def _same_day_finish_cells(all_matches: list, cfg: MultiConfig) -> set:
    """(event, day) cells a TD-configured same-day finish legitimately puts two rounds on.

    Without this the cadence report tells the Operator to "review the day layout" for exactly the
    division the TD asked to finish in one day — a permanent false advisory on the plan and in the
    Edit console's warning bar, attributing his own instruction to "the planned day layout".
    """
    exempt = _same_day_finish_pairs(all_matches, cfg)
    return {(m.event, m.day) for m in all_matches if m.start is not None and m.mid in exempt}


def cadence_cells(all_matches: list, cfg: MultiConfig) -> dict:
    """{(event, day): [rounds]} for every day holding MORE THAN ONE true round of one division.

    FIX-1 item 2. Computed from placed matches only, so it is valid for any schedule — the
    engine's own build, or one the TD has edited through the courier. Read-only.
    """
    cells: dict[tuple, set] = {}
    for m in all_matches:
        if m.start is not None:
            cells.setdefault((m.event, m.day), set()).add(_true_round_of(cfg, m.event, m.rnd))
    asked_for = _same_day_finish_cells(all_matches, cfg)
    return {k: sorted(v) for k, v in sorted(cells.items(), key=lambda kv: (kv[0][0], kv[0][1] or ""))
            if len(v) > 1 and k not in asked_for}


def cadence_conflicts_of(all_matches: list, cfg: MultiConfig, spills=None,
                         no_clean_day=None) -> list:
    """`cadence_cells` rendered as reportable records, each with a plain-language note.

    `spills` / `no_clean_day` let a record name its true cause. Without them the note states the
    fact without attributing it — which is right for a TD-edited schedule, where the engine's
    ladder is not what put the rounds together.
    """
    spills = spills or []
    no_clean_day = no_clean_day or set()
    out = []
    for (event, day), rounds in cadence_cells(all_matches, cfg).items():
        here = [r for r in spills if r["event"] == event and r["placed_day"] == day]
        forced = any(r["id"] in no_clean_day for r in here)
        if forced:
            cause = ("no other day could seat it, so it was placed here rather than left "
                     "unplaced — the 0-unplaced invariant wins")
        elif here:
            cause = ("a match that could not sit on its assigned day moved here while this day "
                     "was still clear, and another round landed here afterwards")
        else:
            cause = "the planned day layout puts these rounds on the same day"
        out.append({"event": event, "day": day, "rounds": rounds,
                    "spilled_ids": [r["id"] for r in here], "forced": forced,
                    "note": (f"{event} has more than one round on {day} "
                             f"(rounds {', '.join(str(x) for x in rounds)}): {cause}. "
                             f"Review the day layout for this division.")})
    return out


def _build_and_place(cfg: MultiConfig, out=None):
    """Core engine: build draws, greedily place matches, auto-stagger finals.
    Returns (all_matches, occ, unplaced, stagger_records) so callers can either
    assemble a result dict (schedule_multi) or apply post-hoc decisions
    (scheduler_flow.finalize_multi). Raises ValueError on an unsupported format.

    out (optional dict): if given, `out["spills"]` is filled with the R7-2 assigned-day
    fallback report (matches that couldn't sit on their pinned day). Omitted by default so
    existing callers (scheduler_flow) keep the 4-tuple contract unchanged."""
    # VENUE-1: the escape record belongs to THIS placement run. Clearing it here is what keeps
    # the engine deterministic when one config is placed twice — the determinism check does
    # exactly that, and a set carried over from the previous run would make the second result
    # differ from the first for no reason but bookkeeping.
    cfg.venue_escapes = set()
    all_matches: list[Match] = []
    for i, ev in enumerate(cfg.events):
        prefix = f"E{i+1}"
        if ev.fmt in ("single_elim", "compass"):
            all_matches += build_elim_teams(ev, prefix)
        elif ev.fmt == "round_robin":
            all_matches += build_rr_teams(ev, prefix)
        else:
            raise ValueError(f"Unsupported fmt for {ev.name}: {ev.fmt}")

    by_id = {m.mid: m for m in all_matches}
    grid = _slots(cfg)
    _near_cache: dict = {}

    def _near_grid(ref):
        """NEAR-1 (2026-08-06): `grid`, re-ordered so its DAYS run outward from `ref` instead of
        chronologically. Nothing is added or removed — this is the same slot list in a different
        order, so the set of feasible (day, slot) pairs the caller sees is identical and every
        gate inside `_scan` still decides it.

        The sort key is a TOTAL order, and it has to be: two days at equal distance sorting
        unstably would make the engine non-deterministic, which is the invariant that never bends.
          1. `abs(delta)`  — nearest first, the whole point of the build
          2. `delta`       — signed, so an equal-distance tie takes the EARLIER day (ruling 53 /
                             D-28; re-affirmed 2026-08-06 on refreshed committed-field evidence)
          3. the date str  — a final tiebreak that cannot collide, so sort stability is never
                             load-bearing

        Each day keeps its own chronological slot order inside the group, so time-of-day
        preference within a day is untouched. Memoised per reference day — at most one entry per
        tournament day — so the reorder is paid once per day, not once per match."""
        got = _near_cache.get(ref)
        if got is None:
            byday: dict = {}
            for pair in grid:
                byday.setdefault(pair[0], []).append(pair)
            r0 = datetime.strptime(ref, "%Y-%m-%d")

            def _key(d):
                delta = (datetime.strptime(d, "%Y-%m-%d") - r0).days
                return (abs(delta), delta, d)

            got = [pair for d in sorted(byday, key=_key) for pair in byday[d]]
            _near_cache[ref] = got
        return got

    occ: dict[tuple, list[tuple[int, datetime]]] = {}
    human_busy: dict[str, list[tuple[datetime, datetime, int]]] = {}

    # BP-2 morning/later staging. evcounts = per-player division count. The staging rank is a
    # secondary key placed AFTER (precedence, round, draw) so round/feeder ordering is untouched —
    # it only reorders matches that are already simultaneously placeable: 3-event players grab the
    # earliest slots of their round, singles-only take the latest, with locals-early a within-tier
    # nudge (locals front, travelers back). Empty placement_policy => rank uniform => byte-identical.
    evcounts = _player_event_counts(cfg.events)
    # ENG-1 (ruling 73): the day shape at the clock. `shape_on` gates; the escape is RECORDED after
    # placement from the finished schedule, so the mirror and the record can never disagree.
    kind_order = kind_order_of(cfg)
    shape_on = bool(kind_order)
    # ENG-1 (ruling 73): the day shape binds HERE as well as in the gate. `precedence` already puts
    # singles (0) ahead of mixed and gender doubles (both 1), but those two separated only on an
    # ALPHABETICAL tiebreak — "Men's ..." sorts before "Mixed ...", so gender doubles claimed a
    # day's slots before the mixed matches that belong ahead of them. The gate alone cannot repair
    # that: it refuses the out-of-shape slot, the mixed match spills to another day, and the shape
    # is bought with a day change nobody asked for. Measured: gate only => 39 spills, 32 of them
    # beyond +/-1 day and EVERY ONE a Mixed division. With the kind key in the sort the same gate
    # yields the figures in `brief.md` Update 14. `_kind_rank` sits ABOVE the round so a day holding
    # several rounds still fills singles -> mixed -> doubles; within one division it is constant, so
    # round order — and every feeder dependency that rides on it — is untouched.
    order = sorted(all_matches,
                   key=lambda m: (m.precedence,
                                  (_kind_rank(m.event, kind_order) if shape_on else None) or 0,
                                  m.rnd, 0 if m.draw != "consolation" else 1,
                                  _staging_rank(m, cfg, evcounts), m.event, m.mid))

    caps = {ev.name: ev.max_matches_per_day for ev in cfg.events}   # ENG-1: routed from td-constraints match_caps
    # AVOID-3: per-division earliest-start floor (e.g. 80-and-over -> 09:30). Time-of-day only.
    floors = {ev.name: datetime.strptime(ev.earliest_start, "%H:%M").time()
              for ev in cfg.events if ev.earliest_start}
    # ENG-1/F-4/M6 (ruling 74): the ROUND-AWARE floor. Same shape as `floors`, but it binds only
    # on each division's FINAL round — `final_rnd` is what makes "the final, but not round one"
    # expressible. The 80+ AVOID-3 floor above still applies on top, so a 09:30 division keeps
    # 09:30 for its final (NQ-2's ruled 9:30-wins default, and it falls out rather than being coded).
    fin_floors = {ev.name: datetime.strptime(ev.finals_earliest, "%H:%M").time()
                  for ev in cfg.events if ev.finals_earliest}
    # VENUE-1 (rule 39) needs the same round-aware map, so it is now built whenever EITHER rule
    # wants it. With both off it stays `{}` and everything downstream is byte-identical.
    venue_on = bool(cfg.venue_rules) and bool(cfg.venue_order)
    final_rnd = _final_rounds(all_matches, cfg) if (fin_floors or venue_on) else {}
    cfg.venue_final_rnd = final_rnd   # VENUE-1: read by `_venue_demerit` for semis + finals
    # ENG-1 (D-40 / ruling 67): the TD's 9:00 / 12:00 / 15:00 head start for three-event players,
    # read "at or EARLIER", narrow scope (triple days only) pending NQ-1.
    bands, band_days = _band_setup(cfg, all_matches)
    kinds_on_day: dict = {}      # day -> {kind rank: (earliest start, latest start)}
    # ENG-1 (ruling 72): the same-day-finish rest-floor exception, resolved ONCE here and read by
    # every site that enforces rest. Empty set => the full 180-minute floor everywhere, as today.
    sdf_exempt = _same_day_finish_pairs(all_matches, cfg)
    assigned_days = cfg.assigned_days   # R7-2: (event, rnd) -> day; empty => gate inert (byte-identical)
    day_count: dict[tuple, int] = {}                                 # (event, human, day) -> matches that day

    spills = []          # R7-2 (Option A): matches that couldn't sit on their assigned day (report)
    rule_escapes = []    # ENG-1: matches only the relaxed ladder could seat (band / finals floor)
    unplaced = []
    # CAD-1 (ruling R1): `no_clean_day` — the mids the ladder placed on its cadence-breaking last
    # rung — is retired with that rung. It stays as an empty set passed to `cadence_conflicts_of`
    # because that helper also grades COURIER-EDITED schedules, where "the ladder was forced here"
    # is a cause it must be able to decline to claim.
    no_clean_day: set = set()

    # FIX-1 item 2: round cadence — which TRUE rounds of a division already sit on a day.
    rounds_on_day: dict[tuple, set] = {}          # (event, day) -> {true round, ...}

    def _true_round(m):
        return _true_round_of(cfg, m.event, m.rnd)

    # CAD-1 patch 1 (Operator ruling R1, 2026-08-18) — THE RESERVATION-AWARE CADENCE GUARD.
    # A reservation-aware variant was built at FIX-1, measured, and dropped: skipping a reserved
    # day pushes the spilled match LATER, which cascaded into further spills (26 against 24) and
    # turned a mild round-2/round-3 collision into a final-on-its-own-semifinal's-day one. It is
    # BACK, and what changed is not the guard — it is what happens when the guard bites. Under
    # the spill-first ladder it had nowhere to send the match but further down the calendar; under
    # the yield-first ladder (patch 4) the match bends a recorded clock rule and STAYS on its
    # planned day, which is the cure the engine was already using in one place and now uses first.
    # Measured on the committed field: the two cadence cells go to 0 and the spills go 5 -> 2.
    #
    # `cad_reserved` is the map's own claim on a day; `cad_round_day` and `cad_placed` are
    # patches 3/3b's forward-only inputs — the day the map ASSIGNED an earlier round, and the day
    # that round actually LANDED on. All three are built ONLY when an assigned-day map exists:
    # the no-map diagnostic hatch (D-3) is legacy by ruling and every one of these structures
    # stays empty there, which is what makes `tests/cad1_invariant.py` part F byte-identical.
    cad_reserved: dict = {}      # (event, day) -> {true rounds the day map reserves}
    cad_round_day: dict = {}     # (event, true round) -> latest day the map assigned that round
    cad_placed: dict = {}        # (event, true round) -> latest day that round actually landed on
    if assigned_days:
        for (_ev, _rnd), _d in assigned_days.items():
            _tr = _true_round_of(cfg, _ev, _rnd)
            cad_reserved.setdefault((_ev, _d), set()).add(_tr)
            if _d > cad_round_day.get((_ev, _tr), ""):
                cad_round_day[(_ev, _tr)] = _d

    def _cad_placed_max(ev, tr):
        """The latest day ANY earlier true round of this division actually landed on.

        Patch 3b (dynamic + transitive). Patch 3 alone compares against the previous round's
        ASSIGNED day, so when that round itself spills forward the next round can still land
        BEFORE it — measured 3 division-round pairs printing backwards at 80% courts, 8 at 50%.
        Taking the max over every earlier round rather than only the immediately previous one is
        what makes it transitive, and that is not tidiness: a chain whose middle round is
        unplaced otherwise breaks the comparison and lets the later round march back past both
        (measured, 1 residual at 50%). Dormant on the committed field — byte-identical at full
        capacity — and load-bearing the moment courts get tight."""
        best = None
        for (e2, t2), d in cad_placed.items():
            if e2 == ev and t2 < tr and (best is None or d > best):
                best = d
        return best

    def _scan(m, restrict_day, cadence_clean=False, keep_rules=True, venue_gate=None,
              near_to=None, relax_bands=False, relax_shape=False, main_site_only=False):
        """Greedy slot scan for one match. `restrict_day` (a date str) pins the search to that day —
        the R7-2 HARD assigned-day gate; None searches every day (today's earliest-feasible). Commits
        the placement and returns True on the first feasible slot; False if none fits. Every
        feasibility gate below is unchanged from the pre-R7-2 loop; the day pin is one added filter,
        the same shape as AVOID-3's earliest-start floor.

        `cadence_clean` (FIX-1 item 2) refuses any day that already holds a DIFFERENT true round
        of this match's own division. Only the Option-A fallback passes it, so a run with no
        assigned-day map never reaches it and stays byte-identical.

        `keep_shape` (ENG-1, ruling 73) refuses a slot that would break the TD's day shape. It is
        TRUE on every rung except the last: where no in-shape slot exists ANYWHERE, the match is
        placed out of shape and the exception recorded, exactly as an assigned-day spill is.
        0-unplaced is never traded away.

        `near_to` (NEAR-1, 2026-08-06) names the day to measure distance FROM, and changes only
        the ORDER days are visited in — never which of them are feasible. Absent (every caller but
        the two cross-day rungs) the sweep is the shipped chronological `grid` object itself, not
        a copy of it, so the untouched path is untouched in the strongest sense available. Only
        meaningful with `restrict_day` None: a one-day scan has no day order to change.

        `relax_bands` / `relax_shape` (CAD-1, ruling R2) are the graded yield ladder's two levers.
        They lift ONE named gate each and nothing else — in particular `keep_rules` stays True
        through every rung, so the finals floor and the rest floor never yield again. Every scan
        that used one is recorded in `rule_escapes` with the gate named."""
        tr = _true_round(m)
        krank = _kind_rank(m.event, kind_order)
        if venue_gate is None:
            venue_gate = keep_rules and venue_on
        # CAD-1 patches 3/3b — THE FORWARD-ONLY LIMIT, computed once per scan rather than per
        # slot. Plan-relative part: the day the map assigned this division's PREVIOUS true round.
        # Dynamic part: also the latest day any earlier round of it actually landed on. Both are
        # conditioned on an assigned-day map existing, which is the whole guard keeping this off
        # the no-map diagnostic hatch (D-3) — the hatch has no plan to be forward of.
        cad_floor = None
        cad_sdf_final = False
        if assigned_days:
            cad_floor = cad_round_day.get((m.event, tr - 1))
            dyn = _cad_placed_max(m.event, tr)
            if dyn is not None and (cad_floor is None or dyn > cad_floor):
                cad_floor = dyn
            # Ruling 72's same-day finish is the ONE exception, and it is one-directional: a
            # TD-named division's FINAL may SHARE its penultimate round's day, never precede it.
            cad_sdf_final = bool(sdf_exempt) and sdf_exempt.get(m.mid, (None, False))[1]
        for (day, st) in (_near_grid(near_to) if near_to is not None else grid):
            if restrict_day is not None and day != restrict_day:
                continue
            # CAD-1 patches 3/3b: a round never plays before — or on — a day an earlier round of
            # its own division already holds. The sdf final is the named exception to the "or on".
            if cad_floor is not None and (day < cad_floor or
                                          (day == cad_floor and not cad_sdf_final)):
                continue
            if cadence_clean:
                held = rounds_on_day.get((m.event, day))
                if held and held != {tr}:
                    continue
                # CAD-1 patch 1: also refuse a day the assigned-day map RESERVES for a different
                # true round of this division. Without it a spilling match takes a day that is
                # clean at the moment it lands and is collided into later, when the round the map
                # planned for that day arrives by the primary gate — which is exactly how both
                # committed cadence cells were minted.
                resv = cad_reserved.get((m.event, day))
                if resv and resv != {tr}:
                    continue
            en = st + timedelta(minutes=m.match_minutes)
            day_end = datetime.strptime(f"{day} {cfg.daily_end}", "%Y-%m-%d %H:%M") - timedelta(
                minutes=cfg.end_of_day_buffer_minutes)
            if en > day_end:
                continue
            floor = floors.get(m.event)          # AVOID-3: don't start this division before its floor
            if floor is not None and st.time() < floor:
                continue
            # ENG-1/F-4/M6 (ruling 74): the finals floor — this division's FINAL round only. A
            # semifinal at 08:00 passes here untouched; flooring it would be scope not granted.
            ffloor = fin_floors.get(m.event)
            if keep_rules and ffloor is not None and m.rnd == final_rnd.get(m.event) \
                    and st.time() < ffloor:
                continue
            # ENG-1 (D-40): the three-event head start, "at or earlier", triple days only.
            if keep_rules and not relax_bands and not _in_band(m, day, st, bands, band_days):
                continue
            # ENG-1 (ruling 73): the day shape at the clock. The test is SYMMETRIC — a later-kind
            # match may not start before an earlier-kind match already on this day, AND an
            # earlier-kind match may not start after a later-kind one already there. One-sided,
            # the second case would place a mixed match behind a doubles match already down and
            # silently put THAT match out of shape after the fact.
            # Refuse if any earlier-kind match on this day starts AFTER me (`hi > st`), or any
            # later-kind match on it starts BEFORE me (`st > lo`).
            if keep_rules and not relax_shape and shape_on and krank is not None:
                seen = kinds_on_day.get(day)
                if seen and any((r < krank and st < hi) or (r > krank and st > lo)
                                for r, (lo, hi) in seen.items()):
                    continue
            # FIX-1 item 1: the full candidate list, not just its head. Capacity and hours are
            # location-independent of the match, so they filter here; transit is not, so it is
            # tested per candidate below.
            # VENUE-1: `m` rides along so the venue rules can order the list. It changes the
            # ORDER only — the same locations come back — so a venue rule never costs a placement.
            cands = _scan_locations(occ, day, st, en, cfg, m)
            if not cands:
                continue
            # VENUE-1 (rules 6/31/38/39/40/43) — THE VENUE GATE, built to ruling 73's shape.
            # Ordering the candidates is not enough on its own and measuring proved it: the main
            # site is already rank 1, so it is already tried first, and the 30 eighty-and-over
            # matches sitting off-site were off-site because the main site had no room AT THAT
            # MOMENT — not because some other venue was preferred. Re-ordering a list the main
            # site is already at the head of moves nothing.
            #
            # So the rule has to bind on the SLOT, exactly as the day shape does: on a rules-
            # respecting rung this slot is acceptable only if a venue the rules actually want has
            # room in it, and otherwise the scan walks on to the next slot and tries there. The
            # match is not refused — it is placed at a different TIME, at the venue his rules ask
            # for. Where no such slot exists anywhere, the ladder's last rung runs with
            # `keep_rules=False`, this gate lifts, and the placement is recorded as an escape
            # (rule 41). 0-unplaced is never traded away.
            # BUDGET-1 §3.2 (R13, Operator option 3, 2026-08-22) — THE NARROW GATE.
            # `main_site_only` asks ONE question: is this slot at the main site? It is not the
            # venue gate with a different name, and the difference is the whole of option 3.
            #
            # `venue_gate` above consults EVERY enabled venue rule at once — the 80-and-over
            # rule, the semifinal rule, the fill order, AND rule 6's cap on how many matches may
            # start at the main site between 15:00 and 16:00. So a slot AT the main site scores a
            # demerit when rule 6's window is full, and the gate rejects it. Reading that
            # rejection as "the main site has no room" is exactly the error that made the first
            # two cuts of this build move matches for no reason: on the same-day-finish week the
            # Mixed 70 & over doubles final was pushed a whole day off its planned date when the
            # ordinary ladder would have seated it at 15:00 at the main site, rule 6 bending by
            # one and nothing else wrong. Measured: 16 recorded day-shape yields traded for a
            # moved final nobody asked to move.
            #
            # This gate therefore ignores the other venue rules entirely and lets them bend and
            # record as rule 41 has always allowed. It restricts the CLUB and nothing else.
            if main_site_only:
                main = _venue_main_site(cfg)
                cands = [loc for loc in cands if loc == main]
                if not cands:
                    continue
            elif venue_gate:
                want = [loc for loc in cands
                        if not _venue_demerit(m, loc, day, st, cfg, occ)]
                if not want:
                    continue
                cands = want
            if not _feeders_done(m, by_id, st):
                continue
            if m.lineage and not _lineage_rested(m, by_id, st, cfg.min_start_to_start_minutes,
                                                 cfg, sdf_exempt, m.mid):
                continue
            cap = caps.get(m.event)   # ENG-1: per division, per player, per day — the TD's 1
            if cap is not None and m.humans and \
                    any(day_count.get((m.event, h, day), 0) + 1 > cap for h in m.humans):
                continue
            # FIX-1 item 1: try every open location before abandoning the slot. Pre-fix this
            # tested `cands[0]` alone and gave the whole (day, start) up on failure, so a match
            # that only a second location could seat landed later than it needed to — or not at
            # all. No gate is weakened: each candidate faces the identical `_humans_ok` test,
            # and the first that clears wins, so the lowest-order preference is intact.
            # `_FULL` is the sentinel, NOT None: with no court_locations layout the pool's
            # location id IS None (a legitimate placement), so None cannot mean "not found".
            cand_loc = _FULL
            for loc in cands:
                if _humans_ok(m, human_busy, st, en, cfg.min_start_to_start_minutes,
                              loc, cfg.transit_minutes, cfg, sdf_exempt):
                    cand_loc = loc
                    break
            if cand_loc is _FULL:
                continue
            m.start, m.end, m.day = st, en, day
            m.court = None            # court is a day-of operational decision (Era-2); never assigned here
            m.location = cand_loc     # placement identity is (day, start, location)
            _record_venue_escape(m, cand_loc, day, st, cfg, occ)   # VENUE-1 / rule 41
            _mark_slot(occ, day, st, en, cand_loc)
            rounds_on_day.setdefault((m.event, day), set()).add(tr)
            # CAD-1 patch 3b: the OUTCOME-relative half of the forward-only limit. Recorded here,
            # at the moment of placement, because the plan-relative half alone cannot see a round
            # that spilled forward and must not be marched past.
            if assigned_days and day > cad_placed.get((m.event, tr), ""):
                cad_placed[(m.event, tr)] = day
            # NEAR-1 A1 (2026-08-06): `near_to is None` — only NORMALLY-placed matches widen the
            # day-shape windows. A cross-day (spilled) placement is already a recorded exception;
            # letting it set precedent here dragged 23 later-placed doubles into one 15:30 slot
            # and put 15 starts in rule 6's capped hour against the TD's 9. The spill still obeys
            # the shape gate above when it lands; it just cannot make law for matches placed
            # after it. Its residual out-of-shape-ness is judged and recorded by
            # `day_shape_violations`' symmetric no-precedent path, so record and mirror agree.
            if shape_on and krank is not None and near_to is None:   # ENG-1: widen this day's window for this kind
                lohi = kinds_on_day.setdefault(day, {}).get(krank)
                kinds_on_day[day][krank] = ((min(lohi[0], st), max(lohi[1], st)) if lohi
                                            else (st, st))
            for h in m.humans:
                human_busy.setdefault(h, []).append((st, en, m.recovery_minutes, cand_loc, m.mid))
                day_count[(m.event, h, day)] = day_count.get((m.event, h, day), 0) + 1
            return True
        return False

    # CAD-1 patch 4 (Operator ruling R2, 2026-08-18) — THE GRADED YIELD LADDER, YIELD-FIRST.
    # Each rung lifts ONE named clock rule and records which one. The order inside the ladder
    # (bands, then shape, then both) was measured immaterial — swapped at every capacity down to
    # 50% the schedules are identical, because the two rescue disjoint match sets — so the ruled
    # order stands at zero measured cost. The shape rung first fires at 55% capacity.
    _YIELD_GATES = (("day_bands", {"relax_bands": True}),
                    ("day_shape", {"relax_shape": True}),
                    ("day_bands+day_shape", {"relax_bands": True, "relax_shape": True}))

    def _record_yield(m, gate):
        """A recorded clock-rule yield. The `gate` field is CAD-1 patch 5 — additive inside the
        existing `rule_escapes` rows, so no contract gains a field and every consumer that reads
        the list today keeps reading it unchanged. It names which rule bent, which is what the
        editor's TD-facing sentence needs to stop guessing."""
        rule_escapes.append({"id": m.mid, "event": m.event, "round": m.rnd,
                             "day": m.day, "start": m.start.strftime("%H:%M"),
                             "gate": gate})

    def _record_spill(m, aday):
        spills.append({"id": m.mid, "event": m.event, "round": m.rnd,
                       "assigned_day": aday, "placed_day": m.day})

    def _day_ladder(m, aday):
        """The R7-2 assigned-day ladder, re-ordered by CAD-1's ruling R2 and shortened by R1.

        NEAR-1 (2026-08-06) ANSWERED ENG-1's SIGNPOST on day-choice semantics and its answer
        stands: the cross-day rungs search NEAREST-feasible from the assigned day, equal
        distances breaking to the EARLIER day (ruling 53 / D-28), and the venue gate does not
        follow the match off its day (`venue_gate=False`, VENUE-1's ruling — re-gating those
        rungs was measured at 84 spills and 1 UNPLACED).

        WHAT CAD-1 CHANGED, and why each piece is here:

        * THE LAST-RESORT RUNG IS GONE (patch 2). It was the one scan with no cadence guard, and
          it is what minted the two cells on the committed field. No rung may break cadence now;
          where nothing seats the match the WEEK is refused (feasibility rung 2), which is a
          decision the Operator ruled explicitly rather than a placement the engine improvises.
        * `keep_rules=False` IS GONE WITH IT (patch 4). The old escape lifted the finals floor,
          the bands, the day shape and the venue gate in one move and recorded a single
          undifferentiated line. The finals floor and the rest floor now never yield — measured
          free, they yielded in no configuration down to 50% capacity — and what does yield says
          so by name.
        * YIELD BEFORE SPILL (ruling R2). A match bends a recorded clock rule ON its planned day
          before it is allowed to leave that day. Measured dominant on every robustness axis:
          it fixes the same-day-finish week that spill-first loses 6 matches on, keeps 2 matches
          off their planned day instead of 6, and places everyone deeper into court shortage
          (unplaced at 62% courts: 21 against 10). Its cost is preference-shaped, not
          correctness-shaped — 10 recorded band yields against 2, more clock bends and fewer day
          moves. The E8 (Men's 45) case is the engine's own precedent: where every spill day was
          blocked it already bent the 09:30 band rather than move the match, and the 4 players
          affected finish EARLIER than under the shipped engine, which "protected" their 09:00
          deadline by pushing their singles to the next morning at 08:00 — minting the cadence
          cell and giving 2 of the 4 a double day.

        The cross-day rung keeps its own graded yields as ITS last resort, so a match that can
        neither sit its day nor bend a rule there is still placed rather than dropped.
        `tests/cad1_invariant.py` parts A and C measure both halves on real boards; part B holds
        the cell count at 0 down to the capacity where the week is refused instead."""
        # R7-2 HARD gate: try the master-assigned day FIRST, with every rule kept. No map =>
        # aday is None => a single unrestricted scan => byte-identical to the pre-R7-2 engine,
        # which is also what keeps the no-map diagnostic hatch (D-3) legacy.
        if _scan(m, aday):
            return True
        # BUDGET-1 §3.2 (R13) — FOR THE TWO HARD RULES, THE VENUE BEATS THE DAY.
        # (Operator option 1, 2026-08-22, a second sign-off taken after the first implementation
        # was measured.)
        #
        # Rung 1 has just failed with the venue gate on, so this match cannot have both its
        # assigned day and the venue the rules want. For every ordinary match the next rung keeps
        # the DAY and yields the venue, which is VENUE-1's ruling and stays exactly as it was.
        # But a rule that "yields to nothing" cannot be the thing that yields there: keeping the
        # day is a PREFERENCE, and a preference must not outrank an absolute.
        #
        # So a final, or a Level 1 Mixed match, gets two more chances FIRST, in the order that
        # costs the director least:
        #
        #   (a) BEND A CLOCK RULE, STAY ON THE DAY, STAY AT THE MAIN SITE. Rung 1 keeps every
        #       rule AND the venue gate, so it fails for clock reasons as often as venue ones —
        #       a gender-doubles final wanting a late slot the main site has already filled, say.
        #       Running the ladder's own graded yields WITH THE VENUE GATE STILL ON resolves
        #       exactly those without anything moving at all. This is ruling R2's own order
        #       (yield before spill) applied inside the hard rule.
        #   (b) Only then MOVE A DAY to stay at the main site — the same cross-day search the
        #       ladder already runs, venue gate still on. It moves a DAY rather than moving CLUB.
        #
        # (a) BEFORE (b) IS LOAD-BEARING AND WAS MEASURED. With (b) alone this rung fired on
        # every rung-1 failure whatever its cause, and spilled matches a day that had no venue
        # problem at all: the committed field moved 17 rows and its spill anchor went 2 -> 1 for
        # no reason a director would recognise. With (a) ahead of it, the clock-shaped failures
        # are absorbed on the day where they belong.
        #
        # THE 0-UNPLACED QUESTION, ANSWERED BY MEASUREMENT AND NOT BY ARGUMENT. Both rungs are
        # additive in the sense that they are inserted ahead of the old ladder and remove
        # nothing: if neither finds a home, the ladder proceeds exactly as before, through
        # day-beats-venue, the graded yields, the spill and the graded cross-day rungs.
        #
        # THAT ARGUMENT IS NOT SUFFICIENT AND MUST NOT BE MISTAKEN FOR A PROOF. Placement is
        # greedy and sequential, so a match that takes a different slot here changes what is
        # left for every match placed after it — per-match additivity does not give field-level
        # safety. VENUE-1 measured re-gating the cross-day rungs for the whole field at 84 spills
        # and 1 UNPLACED, which is exactly this effect. The claim that these rungs cost no
        # placement rests on the regression suite and on the committed field being byte-identical
        # across the change, not on the shape of the code. If a future edit widens
        # `_hard_venue_match`, that measurement has to be retaken.
        #
        # AND WHY IT IS RESTRICTED TO THESE MATCHES. VENUE-1 measured re-gating the cross-day
        # rungs FOR EVERYTHING at 84 spills and 1 UNPLACED, which is why those rungs run with the
        # gate off. That measurement is not overturned here and must not be: these rungs are
        # gated on `_hard_venue_match`, so the set they apply to is the finals and the Level 1
        # Mixed ladder, not the field.
        if aday is not None and venue_on and _hard_venue_match(m, cfg):
            # (a) THE PLANNED DAY, AT THE MAIN SITE, letting the other venue rules bend.
            #     This is the rung that does nearly all the work and the one both earlier cuts
            #     lacked. It keeps the day, keeps the club, and costs nothing but a rule-41
            #     record on whichever lesser venue rule gave way.
            if _scan(m, aday, venue_gate=False, main_site_only=True):
                return True
            # (b) the same, bending ONE named clock rule — ruling R2's yield-before-spill order,
            #     applied inside the hard rule.
            for gate, kw in _YIELD_GATES:
                if _scan(m, aday, venue_gate=False, main_site_only=True, **kw):
                    _record_yield(m, gate)
                    return True
            # (c) THERE IS NO RUNG (c). A VENUE RULE NEVER MOVES A MATCH'S DAY.
            #     Two cuts of this build had one — a cross-day search at the main site, so a match
            #     could move a DAY rather than move CLUB — and BOTH were wrong, in two different
            #     ways, each caught by measurement rather than by review:
            #
            #       * It moved matches nobody needed to move. On the same-day-finish week it
            #         pushed the Mixed 70 & over doubles FINAL a whole day off its planned date,
            #         when the ordinary ladder seated it at 15:00 at the main site with nothing
            #         wrong. A published finals day is a promise to players and R6 is explicit
            #         that this tool prices the director's calendar and never reshapes it.
            #       * Restricted to non-finals it STILL BROKE 0-UNPLACED. On the adversarial
            #         WEST-first ordering (a 4-court main site open 2 days of 10) it took one of
            #         those scarce slots on another day and left a match with nowhere to play —
            #         VENUE-1's own 84-spills-and-1-unplaced measurement, reproduced in miniature.
            #         0-unplaced is never traded, so that ends the argument.
            #
            #     And it bought nothing: rungs (a) and (b) alone fix every case this rung was
            #     added for, including the PDF-derived day map that first exposed the problem —
            #     0 unplaced, 0 breaches, no refusal, and no day moved. Measured both ways.
            #
            #     So a hard-rule match that cannot reach the main site ON ITS OWN DAY falls
            #     through to the ordinary ladder. If it then lands off-site the week is REFUSED
            #     by name, which is R13's whole point: the tool says so rather than moving
            #     somebody's day behind the director's back to avoid saying it.
        # VENUE-1 — THE DAY BEATS THE VENUE. Rung 1 has just failed with the venue gate on, so
        # the match cannot have both the day the director assigned it AND the venue his rules
        # prefer. Given that choice it keeps the DAY. Unmoved by CAD-1: it costs no recorded
        # rule, so it sits ahead of every rung that does. Unmoved by BUDGET-1 either — the rung
        # above takes the two hard-rule classes out ahead of it and leaves this one alone.
        if aday is not None and venue_on and _scan(m, aday, venue_gate=False):
            return True
        if aday is None:
            # The no-map path has no planned day to yield ON and no cadence to keep, so the
            # graded rungs are all it has. On the committed field it never reaches them — the
            # hatch places all 760 on rung 1 — and `tests/cad1_invariant.py` part F pins that.
            for gate, kw in _YIELD_GATES:
                if _scan(m, None, venue_gate=False, **kw):
                    _record_yield(m, gate)
                    return True
            return False
        for gate, kw in _YIELD_GATES:          # ruling R2: yields ON the planned day come first
            if _scan(m, aday, venue_gate=False, **kw):
                _record_yield(m, gate)
                return True
        if _scan(m, None, cadence_clean=True, venue_gate=False, near_to=aday):
            _record_spill(m, aday)
            return True
        for gate, kw in _YIELD_GATES:          # cross-day AND graded — the deepest rung there is
            if _scan(m, None, cadence_clean=True, venue_gate=False, near_to=aday, **kw):
                _record_spill(m, aday)
                _record_yield(m, gate)
                return True
        return False

    for m in order:
        if not m.scheduled_needed:
            continue
        aday = assigned_days.get((m.event, m.rnd)) if assigned_days else None
        # CAD-1 (rulings R1/R2): ONE ladder, one pass. ENG-1's ruling-73 rule escape — the second
        # run of the whole ladder with `keep_rules=False` — is gone: what it existed to prevent
        # (a preference quietly beating 0-unplaced, measured at 4 of 6 matches dropped by the band
        # gate alone on a six-match single-court day) is now prevented rung by rung inside the
        # ladder, with the yielded rule named instead of four of them lifted together.
        if not _day_ladder(m, aday):
            unplaced.append(m.mid)

    # FIX-1 item 2, second half: report whatever cadence collision survives, from the FINISHED
    # schedule rather than at placement time. A placement-time flag cannot see the whole truth —
    # a spilled round-2 match can take a day that is genuinely clean when it lands and only
    # collide later, when round 3 arrives there via its own assigned-day scan.
    #
    # Keyed on the CELL, not on spills: a collision can exist with NO spill at all, because two
    # rounds of a division pinned to the same day are placed there by the primary gate, which
    # honours the master map and never spills. Reporting only annotated spills left that silent.
    cadence_conflicts = cadence_conflicts_of(all_matches, cfg, spills=spills,
                                             no_clean_day=no_clean_day)
    by_cell = {(c["event"], c["day"]): c for c in cadence_conflicts}
    for rec in spills:                 # keep the per-spill flag for consumers reading spills
        c = by_cell.get((rec["event"], rec["placed_day"]))
        if c:
            rec["cadence_conflict"] = True
            rec["note"] = c["note"]

    stagger_records = _stagger_finals(all_matches, cfg, occ)

    # ENG-1 (ruling 73) — RECORD the day-shape escapes, from the FINISHED schedule.
    #
    # Two kinds land here and both are legal: a match no rung could seat in shape (the escape rung
    # above), and a match that WAS in shape when it landed and was put out of shape afterwards, by
    # an earlier-kind match of a later round arriving on that day behind it. `_stagger_finals` can
    # also move a match after the fact. A placement-time flag would miss the second and third —
    # the same reason FIX-1 computes cadence from the finished schedule — so the record and the
    # `validate_multi` mirror read ONE function, and the mirror therefore cannot report the
    # engine's own legal fallbacks as conflicts. That is what keeps 0-conflicts true.
    shape_escapes = []
    if shape_on:
        for m in day_shape_violations(all_matches, kind_order,
                                      no_precedent=frozenset(s["id"] for s in spills)):
            shape_escapes.append({"id": m.mid, "event": m.event, "round": m.rnd, "day": m.day,
                                  "start": m.start.strftime("%H:%M"),
                                  "kind": _event_kind(m.event)})
    # Keyed on (mid, day, start), NOT on the mid alone. A bare-mid pass is permanent and
    # position-blind: the 38 escapes on the committed field could then be dragged anywhere, on any
    # day, and the mirror would stay silent forever — which is the exact couriered-edit case the
    # mirror exists for. Tying the pass to the slot it was granted for means moving the match
    # revokes it.
    cfg.day_shape_exceptions = {(r["id"], r["day"], r["start"]) for r in shape_escapes}
    # NEAR-1 A1: the mirror must read the SAME no-precedent set the recorder just used — the
    # day_shape_exceptions pattern. Stamped unconditionally: empty when there are no spills.
    cfg.day_shape_no_precedent = {s["id"] for s in spills}
    cfg.rule_escapes = {(r["id"], r["day"], r["start"]) for r in rule_escapes}

    if out is not None:
        out["spills"] = spills
        out["cadence_conflicts"] = cadence_conflicts
        out["day_shape_exceptions"] = shape_escapes
        out["rule_escapes"] = rule_escapes
    return all_matches, occ, unplaced, stagger_records


def _assemble_result(cfg: MultiConfig, all_matches: list, unplaced: list,
                     stagger_records: list, spills=None, cadence_conflicts=None,
                     day_shape_exceptions=None, rule_escapes=None) -> dict:
    """Render the public result dict from engine state. String outputs match
    the original schedule_multi (auto_adjustments / potential_overlaps).

    spills (optional, R7-2): the assigned-day fallback report; when non-empty it is surfaced as
    result["assigned_day_spills"] so the operator sees which matches couldn't honor their pin.
    cadence_conflicts (optional, FIX-1 item 2): (event, day) cells holding more than one round of
    that division, each with the rounds involved, whether the ladder was forced there, and a
    plain-language note. Reported separately from `spills` because a collision can exist with NO
    spill — two rounds pinned to the same day are placed there by the primary gate. Advisory: it
    describes the schedule, never constrains it.

    Omitted/empty => the key is absent (output byte-identical to a run with no assigned-day map)."""
    placed_matches = [m for m in all_matches if m.start]
    result = {
        "ok": len(unplaced) == 0,
        "tournament": cfg.tournament_name,
        "courts": cfg.num_courts,
        "courts_by_day": (cfg.courts_by_day or None),
        "events": [e.name for e in cfg.events],
        "total_matches_needing_court": sum(1 for m in all_matches if m.scheduled_needed),
        "byes": sum(1 for m in all_matches if not m.scheduled_needed),
        "unplaced": unplaced,
        "schedule": [
            {"event": m.event, "match": m.label, "id": m.mid, "draw": m.draw,
             "round": m.rnd, "day": m.day,
             "start": m.start.strftime("%H:%M") if m.start else None,
             "end": m.end.strftime("%H:%M") if m.end else None,
             "court": m.court,
             # location: additive, present only on slate-driven runs; omitted (not None)
             # when no layout is supplied so today's output is byte-identical (SCH-01a)
             **({"location": m.location} if m.location is not None else {}),
             "players": sorted(m.humans) if m.humans else [],
             "team_a": m.team_a, "team_b": m.team_b}
            for m in sorted(placed_matches, key=lambda x: (x.day, x.start, x.location or "", x.mid))
        ],
        "conflicts": validate_multi(all_matches, cfg),
        "potential_overlaps": [_overlap_text(r) for r in _potential_later_round_overlaps(all_matches)],
    }
    if stagger_records:
        result["auto_adjustments"] = [_stagger_text(r) for r in stagger_records]
    if spills:
        result["assigned_day_spills"] = spills   # R7-2: pinned matches that fell back to a feasible day
    if day_shape_exceptions:
        # ENG-1 (ruling 73): matches sitting outside the TD's singles -> mixed -> doubles order.
        # Surfaced exactly as spills are — reported, never asserted. Absent when empty, so a run
        # with the shape rule off is byte-identical.
        result["day_shape_exceptions"] = day_shape_exceptions
    if rule_escapes:
        # ENG-1: matches only the relaxed ladder could seat — the band or the finals floor had to
        # yield so the match was placed rather than dropped. Same treatment as a spill.
        result["rule_escapes"] = rule_escapes
    if cfg.venue_escapes:
        # VENUE-1 (rule 41): matches no venue the director's rules prefer could hold at the time
        # they needed, PLACED ANYWAY and recorded. Same treatment as a spill — reported, never
        # asserted — and absent when empty, so a run with the venue rules off is byte-identical.
        # Sorted for determinism: the set's own iteration order is not stable across runs.
        result["venue_escapes"] = sorted(cfg.venue_escapes,
                                         key=lambda e: tuple("" if x is None else str(x)
                                                             for x in e))
    hard = _hard_venue_breaches(placed_matches, cfg)
    if hard:
        # BUDGET-1 §3.2 (R13, Operator sign-off 2026-08-22): the two rules that yield to nothing —
        # Level 1 Mixed at the main site, and every division's FINAL at the main site.
        #
        # PLACEMENT IS UNCHANGED, and that is the design. 0-unplaced is never traded away, so the
        # match is still placed and still recorded under rule 41 exactly as before; what changes
        # is that the rung-2 gate now REFUSES a week carrying one of these, instead of publishing
        # it with a line in the report. Refusing inside placement would mean a match with nowhere
        # to go, which is the very failure `_record_venue_escape` exists to prevent.
        #
        # Derived from the FINISHED schedule rather than from the placement path, for the same
        # reason `validate_multi` rebuilds `venue_final_rnd` rather than reading it: a breach is a
        # property of where matches ended up, and a check that rides the placement path can only
        # see the placements that took that path.
        #
        # ADDITIVE and absent when empty, so every run that holds both rules — the committed
        # field, and every configuration at or above the 32-court floor — is byte-identical.
        # `venue_escapes` above is deliberately NOT reshaped: its 4-tuple is read by the report,
        # the `validate_multi` mirrors and the editor, and R13 is not a reason to move them all.
        result["hard_venue_breaches"] = hard
    if cadence_conflicts:
        # FIX-1 item 2: divisions with two rounds on one day. Separate from spills because a
        # collision can exist with none (two rounds pinned to the same day never spill).
        result["cadence_conflicts"] = cadence_conflicts
    if unplaced:
        result["note"] = ("Some matches could not be placed in the time/courts given. "
                          "Add a day, add courts, shorten match length, or split events across days.")
    return result


def schedule_multi(cfg: MultiConfig) -> dict:
    try:
        info = {}
        all_matches, occ, unplaced, stagger_records = _build_and_place(cfg, out=info)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    return _assemble_result(cfg, all_matches, unplaced, stagger_records,
                            spills=info.get("spills"),
                            cadence_conflicts=info.get("cadence_conflicts"),
                            day_shape_exceptions=info.get("day_shape_exceptions"),
                            rule_escapes=info.get("rule_escapes"))

def _event_players(matches: list, event: str) -> set:
    """Every human known anywhere in an event's field (R1 + bye-advanced + RR)."""
    out = set()
    for m in matches:
        if m.event == event:
            out |= m.humans
    return out


def _stagger_finals(all_matches: list, cfg: MultiConfig, occ: dict) -> list:
    """If two events' finals share a day+start time AND the events share any
    players, move the later one to the next free slot on its day. Returns a list
    of human-readable notes describing what was moved (empty if nothing moved)."""
    notes = []
    # final = the max-round match of each event (single_elim/compass have one)
    finals_by_event = {}
    for ev in cfg.events:
        ev_matches = [m for m in all_matches if m.event == ev.name and m.start]
        if not ev_matches:
            continue
        max_rnd = max(m.rnd for m in ev_matches)
        finals = [m for m in ev_matches if m.rnd == max_rnd]
        if len(finals) == 1:               # a single championship match
            finals_by_event[ev.name] = finals[0]

    finals = list(finals_by_event.items())
    for i in range(len(finals)):
        for j in range(i + 1, len(finals)):
            ev_a, fa = finals[i]
            ev_b, fb = finals[j]
            if fa.day != fb.day or fa.start != fb.start:
                continue
            # only stagger if the two fields actually share a person
            if not (_event_players(all_matches, ev_a) & _event_players(all_matches, ev_b)):
                continue
            # move the later-listed event's final (fb) to the next free slot — one that also leaves
            # fb's players conflict-free, so staggering never drops fb onto another of its players'
            # matches (a latent bug that tight packing, e.g. an R7-2 assigned-day pin, can trigger).
            moved = _move_to_next_slot(fb, cfg, occ, busy=busy_map(all_matches, fb.mid),
                                       exempt=_same_day_finish_pairs(all_matches, cfg))
            if moved:
                notes.append({
                    "event": ev_b, "match_id": fb.mid, "day": fb.day,
                    "from": moved["from"], "to": moved["to"], "location": fb.location,
                    "shared_with": ev_a,
                })
    return notes


def _stagger_text(rec: dict) -> str:
    return (f"Staggered the {rec['event']} final: moved from "
            f"{rec['day']} {rec['from']} to {rec['to']} (location {rec['location']}). "
            f"It shared a slot with the {rec['shared_with']} final and the two fields share "
            f"players, so anyone reaching both finals would have been double-booked.")


def busy_map(matches, exclude_mid=None) -> dict:
    """{human -> [(start, end, recovery, location, mid)]} over every PLACED match except `exclude_mid`.

    The `busy` argument `_move_to_next_slot` takes, in the shape `_humans_ok` reads. Factored out
    (FIX-1a) so the stagger path and the courier's revert path build it identically instead of one
    of them going without — a move that is checked and a revert that is not are not consistent.
    """
    busy: dict = {}
    for om in matches:
        if om.start is None or om.mid == exclude_mid:
            continue
        for h in om.humans:
            # The mid is the 5th slot because `_s2s_for` needs BOTH ids to decide whether the
            # same-day-finish exception covers a pair. A 4-tuple here made `busy_mid` None and the
            # exception structurally unreachable from the two movers below, so a stagger or a
            # revert silently applied the full 180 to a pair the engine had seated at 150.
            busy.setdefault(h, []).append((om.start, om.end, om.recovery_minutes, om.location,
                                           om.mid))
    return busy


def _move_to_next_slot(m: Match, cfg: MultiConfig, occ: dict, busy=None,
                       exempt=None) -> Optional[dict]:
    """Push match m far enough that a player reaching both finals could actually
    play both: at least the recovery gap past the original start, then the next
    capacity-available, in-bounds slot. Updates occupancy + the match. Returns
    {from,to} or None if no suitable slot exists on the day.

    busy (optional): {human -> [(start, end, recovery, loc)]} of the OTHER placed matches. When
    given, a candidate slot is taken only if it also leaves m's players conflict-free (the same
    overlap + start-to-start rest + transit check validate_multi enforces), so a stagger move can
    never create a new same-player conflict. None => today's location-only check (caller behavior
    unchanged; the baseline has no conflicts, so passing busy is byte-identical there)."""
    day = m.day
    old_start, old_end, old_loc = m.start, m.end, m.location
    day_end = datetime.strptime(f"{day} {cfg.daily_end}", "%Y-%m-%d %H:%M") - timedelta(
        minutes=cfg.end_of_day_buffer_minutes)
    step = timedelta(minutes=15)
    # R1: earliest acceptable new start = old start + the start-to-start gap, so the two
    # finals are genuinely playable by one person under the 3h rule.
    gap = timedelta(minutes=cfg.min_start_to_start_minutes)
    venue_on = bool(cfg.venue_rules) and bool(cfg.venue_order)

    def _sweep(respect_venue):
        """One pass over the day's remaining slots. `respect_venue` is VENUE-1's gate in the
        same two-rung shape the placement ladder uses: the first sweep will only move a match to
        a venue its rules actually want, and the second — run only if the first found nothing —
        takes the best available and lets the caller record the escape."""
        t = m.start + gap
        while t + timedelta(minutes=m.match_minutes) <= day_end:
            en = t + timedelta(minutes=m.match_minutes)
            # FIX-1a (Operator-signed-off 2026-07-30): the same defect item 1 fixed in `_scan`
            # lived here too. This took `_free_location`'s head, tested it, and on failure
            # abandoned the whole time `t` — stepping 15 minutes on even when another open
            # location at the SAME time would have cleared. A stagger could therefore land later
            # than necessary, or be abandoned outright, purely because the lowest-order venue was
            # the wrong one.
            # `_FULL` is the sentinel, NOT None: the pool's location id is legitimately None.
            # VENUE-1: this is the path measured relocating 6 finals and 16 semifinals off the
            # main site — the stagger would push a final to a later slot and, finding the main
            # site full there, quietly move it to another club. Rule 39 stops exactly that.
            for loc in _scan_locations(occ, day, t, en, cfg, m):
                if respect_venue and _venue_demerit(m, loc, day, t, cfg, occ):
                    continue
                if busy is None or _humans_ok(m, busy, t, en, cfg.min_start_to_start_minutes,
                                              loc, cfg.transit_minutes, cfg, exempt):
                    return t, en, loc
            t += step
        return None

    found = _sweep(True) if venue_on else None
    if found is None:
        found = _sweep(False)
    if found is None:
        return None   # no suitable later slot; leave it (overlap flag remains)
    t, en, chosen = found
    cell = occ.get((day, old_start), [])
    if (old_loc, old_end) in cell:
        cell.remove((old_loc, old_end))
    m.start, m.end = t, en
    m.court = None            # court stays deferred (Era-2)
    m.location = chosen       # keep placement identity consistent after move
    _record_venue_escape(m, chosen, day, t, cfg, occ)      # VENUE-1 / rule 41
    _mark_slot(occ, day, t, en, chosen)
    return {"from": old_start.strftime("%H:%M"), "to": t.strftime("%H:%M")}


def _reachable_humans(m: "Match", by_id: dict) -> set:
    """All humans who COULD end up playing in match m, by tracing its feeder tree
    back to matches whose participants are known (R1 / bye-advanced / RR)."""
    if m.humans:
        return set(m.humans)
    found = set()
    for f in m.feeders:
        fm = by_id.get(f)
        if fm:
            found |= _reachable_humans(fm, by_id)
    return found


def _potential_later_round_overlaps(matches: list) -> list[str]:
    """Flag the trap a confident 'no conflicts' would hide: a later-round match
    placed in the same day/time block as another match, where a person who COULD
    advance into the later-round match is already committed in that block. These
    are not certain clashes — they depend on results — but they must be surfaced."""
    by_id = {m.mid: m for m in matches}
    placed = [m for m in matches if m.start]
    warnings = []
    seen = set()
    for a in placed:
        a_people = _reachable_humans(a, by_id)
        a_known = bool(a.humans)
        for b in placed:
            if a is b or a.day != b.day:
                continue
            # overlapping time block?
            if not (a.start < b.end and b.start < a.end):
                continue
            # only care when at least one side has UNKNOWN (potential) participants
            if a_known and b.humans:
                continue   # both known -> validate_multi already handles it
            b_people = _reachable_humans(b, by_id)
            shared = a_people & b_people
            if not shared:
                continue
            key = tuple(sorted([a.mid, b.mid]))
            if key in seen:
                continue
            seen.add(key)
            warnings.append({
                "mid_a": a.mid, "mid_b": b.mid,
                "event_a": a.event, "label_a": a.label,
                "event_b": b.event, "label_b": b.label,
                "day": a.day, "time_block": a.start.strftime("%H:%M"),
                "shared": sorted(shared),
            })
    return warnings


def _overlap_text(rec: dict) -> str:
    who = ", ".join(rec["shared"])
    return (f"POSSIBLE later-round clash: {rec['event_a']} '{rec['label_a']}' and "
            f"{rec['event_b']} '{rec['label_b']}' share the same time block "
            f"({rec['day']} {rec['time_block']}); if {who} advance(s), they could be "
            f"double-booked. Re-run once results are in, or move one match.")


# Sentinel: no location has spare concurrent capacity for the requested slot.
_FULL = object()


def _day_locations(cfg: MultiConfig, day: str) -> list[tuple[Optional[str], int]]:
    """Ordered [(location_id, capacity)] open on `day` under the deferred-court model.
    Capacity is a location's concurrent-match count, read from the court_locations
    layout (range width = number of courts = concurrent capacity). With no layout
    (today's no-slate cfg / small self-tests) a single pool (None, _courts_on) is
    returned, preserving the pooled path. Layout order == the slate's location order,
    which reproduces the old 'fill lowest court number first' fill order."""
    layout = cfg.court_locations.get(day)
    if layout:
        return [(loc, hi - lo + 1) for (lo, hi, loc) in layout]
    return [(None, _courts_on(cfg, day))]


def _location_open(cfg: MultiConfig, day: str, loc: Optional[str],
                   st: datetime, en: datetime) -> bool:
    """OI-23 in deferred-court form: is `loc` within its hours window for [st, en) on
    `day`? Empty location_hours, the pool (loc is None), or no window for this
    location/date all fall back to the tournament-wide window (admissible). Boundary:
    a slot ending exactly at close is admitted; one minute past is rejected."""
    if not cfg.location_hours or loc is None:
        return True
    window = cfg.location_hours.get(loc, {}).get(day)
    if window is None:
        return True
    w_start = datetime.strptime(f"{day} {window[0]}", "%Y-%m-%d %H:%M")
    w_end = datetime.strptime(f"{day} {window[1]}", "%Y-%m-%d %H:%M")
    return w_start <= st and en <= w_end


def _loc_usage(occ: dict, day: str, loc: Optional[str],
               st: datetime, en: datetime) -> int:
    """Number of placed matches at (day, loc) whose interval overlaps [st, en)."""
    n = 0
    for (d, s), entries in occ.items():
        if d != day:
            continue
        for (eloc, e_end) in entries:
            if eloc == loc and s < en and st < e_end:
                n += 1
    return n


def _cap_for_slot(cfg: MultiConfig, day: str, loc, base_cap: int, st: datetime) -> int:
    """R7-3 intra-day court step-up (V-5): a slot STARTING before the location's switch
    time sees the (smaller) morning court count; from the switch onward the full count.
    Conservative at the boundary (a match crossing the switch is held to the morning
    cap it starts under). Empty morning_caps => base_cap (byte-identical)."""
    mc = cfg.morning_caps.get((loc, day)) if cfg.morning_caps else None
    if mc and st.strftime("%H:%M") < mc[0]:
        return mc[1]
    return base_cap


def _lit_gate(cfg: MultiConfig, day: str, loc, en: datetime):
    """LIGHTS-1 / rule 48: the instant `loc`'s lit ceiling starts binding on `day`, or None
    when it does not bind on a slot ending at `en` (no lit figures, the pool, or a match that
    is off court before the lights come on). Empty `venue_lit_courts` => None everywhere,
    which is the pre-LIGHTS-1 engine exactly."""
    if not cfg.venue_lit_courts or loc is None:
        return None
    on = cfg.venue_lights_on.get(loc)
    if cfg.venue_lit_courts.get(loc) is None or not on:
        return None
    gate = datetime.strptime(f"{day} {on}", "%Y-%m-%d %H:%M")
    return gate if en > gate else None


def _lit_room(occ: dict, cfg: MultiConfig, day: str, loc, st: datetime, en: datetime,
              base_cap: int) -> bool:
    """RULE 48: after lights-on a venue-day's usable courts are min(courts, lit_courts) —
    matches cannot play in the dark. True when [st, en) still fits under that ceiling.

    MEASURED AT BUILD, and it decides the shape of this function: the whole rule turns on
    OCCUPANCY, never on start time. MHCC's latest start on the committed field is 15:30 and a
    block is 90 minutes, so NOT ONE of the 13 matches on court after 16:00 STARTS after 16:00.
    Graded on the start instant — the literal mirror image of `_cap_for_slot`'s morning
    step-up — rule 48 would be inert on this field and unreachable on any field whose last
    start precedes the lights hour, while the mirror below and the reporter (which both grade
    concurrency at instants past the gate) would go on condemning boards the engine had just
    built. That is the one failure this engine never permits: build a schedule, then declare it
    broken. So placement measures what they measure — how many matches are ON COURT in the lit
    window — and start points are clamped to the gate so only the lit window itself is graded.

    A true peak sweep, not `_loc_usage`'s overlap count, for the same reason `validate_multi`
    sweeps: with 90-minute blocks on a 30-minute grid, matches overlapping a slot outnumber
    matches sharing any one instant with it, and against a ceiling of 7 that gap is the
    difference between a legal board and a refused placement. Under a ceiling of 24 it was
    slack nobody could see."""
    gate = _lit_gate(cfg, day, loc, en)
    if gate is None:
        return True
    limit = min(base_cap, cfg.venue_lit_courts[loc])
    pts = [(max(st, gate), 1), (en, -1)]
    for (d, s), entries in occ.items():
        if d != day:
            continue
        for (eloc, e_end) in entries:
            if eloc == loc and e_end > gate:
                pts.append((max(s, gate), 1))
                pts.append((e_end, -1))
    # An end (-1) is processed before a start (+1) at a shared instant, so touching windows
    # [., end)|[end, .) do not overlap — placement's half-open [st, en) model, and the same
    # convention `validate_multi` and `check_cap_slate` sweep under.
    cur = 0
    for _t, delta in sorted(pts, key=lambda x: (x[0], x[1])):
        cur += delta
        if cur > limit:
            return False
    return True


_VENUE_AGE_RE = re.compile(r"(\d+)\s*&\s*over")


def _venue_age(name: str) -> int:
    """Age bracket parsed from a division name ("Men's 80 & over singles" -> 80); 0 if none.
    A local copy of `constraints._age` on purpose: the placement path imports neither
    `constraints` nor `division_order`, and one three-line regex is a cheaper price than a new
    import edge into the engine."""
    mt = _VENUE_AGE_RE.search(name or "")
    return int(mt.group(1)) if mt else 0


def _venue_main_site(cfg: MultiConfig) -> Optional[str]:
    """The MAIN SITE: the TD's rank-1 venue — `locations[0]` of the slate he built, carried
    through as `cfg.venue_order[0]`. NEVER the literal string "MHCC". A director who moves a
    different club to the top of his venue list has moved the main site, and rules 38/39/40
    follow it there."""
    return cfg.venue_order[0] if cfg.venue_order else None


def _venue_demerit(m: "Match", loc: Optional[str], day: str, st: datetime,
                   cfg: MultiConfig, occ: Optional[dict] = None) -> int:
    """VENUE-1: 0 if every enabled venue rule is content to see `m` at `loc`, 1 if at least one
    would rather it went elsewhere. A DEMERIT, never a veto — the caller uses it to order the
    candidate list, so a 1 still gets played when nothing better has room (rule 41).

    Each rule is consulted only when the TD has switched it on; `cfg.venue_rules` empty means
    this function is never called at all. The pool location (`loc is None`, the no-slate
    self-test path) has no venue identity to judge, so it is always content."""
    if loc is None:
        return 0
    vr = cfg.venue_rules
    main = _venue_main_site(cfg)
    if main is None:
        return 0
    off_main = (loc != main)

    # ---- rule 38: every event at 80 and over plays at the main site ----
    # His field: 95 of 95, across 8 events, no exception. The engine was putting 30 of 93
    # off-site, every one of them at ORLP. Expressed as the list of age brackets the director
    # named rather than a bare threshold, so a future field that adds a 95s division does not
    # silently inherit the rule.
    ages = vr.get("main_site_ages")
    if ages and off_main and _venue_age(m.event) in ages:
        return 1

    # ---- rule 39: semifinals AND finals at the main site ----
    # His field: finals 49 of 49, semifinals 87 of 88 — the one exception a Men's 50 & over
    # doubles semifinal at the Westin. The engine was relocating 6 finals and 16 semifinals off
    # it. Elimination draws only: `_final_rounds` deliberately excludes round-robin, where the
    # last group round is not a championship match (ruling 71's carve-out), so a division whose
    # final round is unknown leaves this rule standing down rather than guessing.
    if vr.get("main_site_finals") and off_main:
        f = cfg.venue_final_rnd.get(m.event)
        if f is not None and f >= 2 and m.rnd in (f, f - 1):
            return 1

    # ---- rule 40: Level-1 Mixed plays at the main site ----
    # His field: 61 of 62. The single exception was a WALKOVER, so excluding walkovers no
    # Level-1 Mixed match was ever CONTESTED away from the main site — 54 of 54. The engine was
    # holding 13 of 49 off it. Which Mixed divisions are Level 1 is the director's tick-box
    # (rule 45), resolved once per run and handed in on `cfg.venue_l1_mixed`; an unresolved list
    # leaves the rule standing down rather than guessing from the division name.
    l1 = cfg.venue_l1_mixed
    if l1 and vr.get("main_site_l1_mixed") and off_main and m.event in l1:
        return 1

    # ---- rule 31, RE-CUT AT BUDGET-1 (R19, Operator 2026-08-22, OI-B1): Level-1 Mixed does
    # ---- not START after 14:00 ----
    # WHAT THIS REPLACES. Until this build the test read the VENUE's lights-on hour and demerited
    # a Level-1 Mixed match starting at or after it. That test fired on NOTHING: the committed
    # field puts 0 of 49 Level-1 Mixed matches at or after 16:00, and on the 2027 five-club plan
    # it catches none of the late starts either, because they all land at 15:30 — half an hour
    # inside the lights hour. What actually happens is a 3:30 start finishing at 5, with the
    # January light going, and it is not spread evenly: every late start measured on the 2027
    # mock was in the 65-and-over half of the ladder. The oldest players were the ones being sent
    # out last, and the rule written to protect them could not see it.
    #
    # REPLACEMENT, NOT A SECOND RULE. 14:00 is strictly earlier than any venue's lights-on hour
    # in the committed slate or the 2027 plan (both 16:00), so the old test could never fire on a
    # match this one had not already caught. Two rules where one fires is one line too many in
    # the director's report, so the old key is RETIRED rather than left standing — and
    # `constraints.py` REFUSES it, because a rule that silently does nothing is the failure that
    # block was written loud to prevent.
    #
    # STILL A DEMERIT, NEVER A VETO (R19 is explicit, and rule 41 is unchanged). Measured at
    # 2 of 136 Level-1 Mixed matches at plan fill on the planned five-club slate, 14 of 182 at
    # full brackets. Two matches is nowhere near a week worth refusing, and a rule that fires on
    # normal behaviour teaches a director to stop reading refusals — the reason the early-start
    # ceiling was re-ruled from 15 to 25 four days ago.
    #
    # Venue-independent BY DESIGN: unlike the rule it replaces it does not consult
    # `venue_lights_on`, so a satellite club with no lights at all is held to the same clock.
    if l1 and vr.get("l1_mixed_latest_start") and m.event in l1:
        if st.strftime("%H:%M") > vr["l1_mixed_latest_start"]:
            return 1

    # ---- rule 6: a hard ceiling on how many matches start at the main site in one window ----
    # The director's own words are a hard limit — at most 9 starts between 15:00 and 16:00 at the
    # main site, because that is what his desk can physically send out at once. Measured against
    # HIS field on the comparison that matches what this tool produces (each player's first match
    # only, which is what an up-front schedule is): 35 starts in the window, peak 11, over the
    # limit on 1 of 8 days. So his own week breaks his own limit exactly once, by two matches —
    # this is NOT a rule that flags normal behaviour. The engine's own peak today is 3 of 9, so
    # enforcing it costs nothing on this field; it is a guardrail against a field that would.
    # It ships WITH the recorded escape (D-48): a day that genuinely cannot seat a match inside
    # the ceiling places it anyway and records the exception, because refusing a Saturday he
    # would have run is worse than exceeding a number by one.
    pw = vr.get("peak_window")
    if pw and occ is not None and not off_main:
        lo, hi = pw.get("start", "15:00"), pw.get("end", "16:00")
        if lo <= st.strftime("%H:%M") < hi:
            n = 0
            for (d, s_at), entries in occ.items():
                if d != day or not (lo <= s_at.strftime("%H:%M") < hi):
                    continue
                n += sum(1 for (eloc, _end) in entries if eloc == loc)
            if n >= pw.get("max_starts", 9):
                return 1
    return 0


def _is_division_final(m: "Match", cfg: MultiConfig) -> bool:
    """Is this match its division's FINAL? Elimination only — a round-robin group has no
    championship match (ruling 71's carve-out) and `venue_final_rnd` holds no entry for one.

    Its own function because it is asked for two different reasons that must never drift apart:
    R13 pins a final to the main site, and BUDGET-1's option-3 ladder refuses to move a final off
    its published day. One is about WHERE, the other about WHEN, and both mean the same match."""
    f = cfg.venue_final_rnd.get(m.event)
    return f is not None and f >= 2 and m.rnd == f


def _hard_venue_match(m: "Match", cfg: MultiConfig) -> bool:
    """BUDGET-1 §3.2 / R13: is this match one of the two classes that yield to nothing — a
    division's FINAL, or a Level 1 Mixed match?

    ONE definition, read by both halves of R13: the placement rung that keeps such a match at the
    main site, and `_hard_venue_breaches` which refuses the week when one of them ended up
    elsewhere anyway. A second copy of this test is a way for the two to disagree, and they would
    disagree silently — the engine would fight to hold a match the gate did not care about, or
    refuse over one it never tried to hold."""
    vr = cfg.venue_rules
    if not vr:
        return False
    if vr.get("main_site_finals") and _is_division_final(m, cfg):
        return True
    return bool(cfg.venue_l1_mixed and vr.get("main_site_l1_mixed")
                and m.event in cfg.venue_l1_mixed)


def _hard_venue_breaches(placed: list, cfg: MultiConfig) -> list:
    """BUDGET-1 §3.2 / R13: every placed match that breaks one of the two rules that yield to
    nothing — a division's FINAL, or any Level 1 Mixed match, away from the main site.

    FINALS ONLY, not semifinals. Rule 39 (the preference this hardens half of) covers `m.rnd in
    (f, f-1)` because the director's own field puts semifinals at the main site 87 times in 88;
    R13 hardened the FINAL and said nothing about the semifinal, so this reads `m.rnd == f`
    alone. Hardening a rule further than it was ruled is how a sign-off's measured blast radius
    stops being the blast radius.

    Round-robin is excluded twice over, and deliberately: `_final_rounds` already stands down on
    a division whose last round is not a championship match (ruling 71's carve-out), and the
    engine's RR events are named `<parent> — Group <i>`, so `venue_final_rnd` holds no entry for
    them. The brief's §0.8 records that counting an RR tail as a final is an error a first pass
    actually made — an RR match's round parses to nothing, and nothing-equals-nothing matched
    every RR row.

    Returns rows, sorted for determinism, each naming the rule so the refusal can say which one
    broke and on which matches. Empty list when both rules hold — which is the committed field
    and every configuration at or above the 32-court floor, so the key never appears there."""
    vr = cfg.venue_rules
    if not vr or not cfg.venue_order:
        return []
    main = _venue_main_site(cfg)
    if main is None:
        return []
    l1 = cfg.venue_l1_mixed
    out = []
    for m in placed:
        if m.location is None or m.location == main:
            continue
        if not _hard_venue_match(m, cfg):      # ONE definition, shared with the placement rung
            continue
        rules = []
        if vr.get("main_site_finals"):
            f = cfg.venue_final_rnd.get(m.event)
            if f is not None and f >= 2 and m.rnd == f:
                rules.append("main_site_finals")
        if l1 and vr.get("main_site_l1_mixed") and m.event in l1:
            rules.append("main_site_l1_mixed")
        for rule in rules:
            out.append({"rule": rule, "event": m.event, "id": m.mid, "round": m.rnd,
                        "day": m.day,
                        "start": m.start.strftime("%H:%M") if m.start else None,
                        "location": m.location, "main_site": main,
                        # D-49 / VENUE-1: the refusal reaches a DIRECTOR, so it names his club
                        # the way he does. The ID stays beside it as the load-bearing identity —
                        # `venue_names` is reported, never scheduled — so a reader that needs to
                        # match on the venue still can, and one that prints gets the real name.
                        "location_name": cfg.venue_names.get(m.location, m.location),
                        "main_site_name": cfg.venue_names.get(main, main)})
    return sorted(out, key=lambda r: (r["rule"], r["day"], str(r["start"]), r["id"]))


def _occ_of(placed: list) -> dict:
    """Rebuild placement's occupancy map from a finished schedule: (day, start) -> [(loc, end)].
    VENUE-1's mirror needs it because rule 6 counts what else already starts in the window, and
    the mirror is handed matches rather than the map placement built. Same shape `_mark_slot`
    writes, so `_venue_demerit` cannot tell the two apart."""
    occ: dict = {}
    for m in placed:
        occ.setdefault((m.day, m.start), []).append((m.location, m.end))
    return occ


def _record_venue_escape(m: "Match", loc: Optional[str], day: str, st: datetime,
                         cfg: MultiConfig, occ: Optional[dict] = None) -> None:
    """RULE 41, the standing disposition for the whole venue axis: this match is going to a venue
    at least one enabled rule would rather not use, because nothing the rules prefer had room for
    it at this slot. PLACE IT AND RECORD THE EXCEPTION — never refuse. A hard refusal with
    nowhere left to go is exactly how the 0-unplaced guarantee breaks, and 0-unplaced is never
    traded away.

    Keyed on (mid, day, start, location) — the SLOT and the venue — so moving the match revokes
    the pass rather than carrying it along, which is the same tolerate-and-revoke shape ruling 73
    gave `day_shape_exceptions`. The `validate_multi` mirrors read this set and tolerate exactly
    these placements, so the tool never builds a schedule and then declares it broken."""
    if cfg.venue_rules and _venue_demerit(m, loc, day, st, cfg, occ):
        cfg.venue_escapes.add((m.mid, day, st.strftime("%H:%M"), loc))


def _scan_locations(occ: dict, day: str, st: datetime, en: datetime, cfg: MultiConfig,
                    m: Optional["Match"] = None) -> list:
    """EVERY location that could hold [st, en) on `day` — spare concurrent capacity (time-of-day
    aware under R7-3 morning caps) and inside its hours window — in layout order.

    FIX-1 item 1: `_free_location` returns only the head of this list, which is all a pure
    capacity question needs. Transit is not a pure capacity question: whether a location works
    depends on where that match's players already are, so the scan needs the whole list to avoid
    abandoning a slot that one of the other open locations would have served.

    VENUE-1 (2026-08-05): `m` is the match being placed, and it is what makes venue eligibility
    expressible at all — "80-and-over at the main site" cannot be asked of a bare (day, slot).
    THIS is the signature change the build turns on; `m=None` is exactly today's behaviour, and
    so is any `m` when `cfg.venue_rules` is empty. **The venue rules re-ORDER this list and never
    shorten it** (rule 41): a venue the rules dislike stays a candidate, just behind the ones
    they like, so no venue predicate can ever be the reason a match goes unplaced. The caller
    records an escape when the venue it actually lands on is one the rules would rather not use.

    Deterministic: layout order, filtered, then STABLY partitioned — `list.sort` on a 0/1 key
    preserves layout order within each group, so the TD's rank (rule 43) survives untouched and
    location choice stays a pure function of the inputs."""
    out = []
    for loc, cap in _day_locations(cfg, day):
        if _loc_usage(occ, day, loc, st, en) >= _cap_for_slot(cfg, day, loc, cap, st):
            continue
        # LIGHTS-1 / rule 48: the lit ceiling is PHYSICAL capacity (Operator, 2026-08-08) — a
        # court with no light on it cannot hold a match, so there is no per-match escape here,
        # exactly as there is none from a venue's court count. Rule 41's place-and-record
        # character lives ONE LEVEL UP: a match the evening can no longer hold takes an earlier
        # slot or another day through the fallback ladder every other capacity refusal uses, and
        # a lost assigned day is recorded as a spill. `_scan_locations` returning a shorter list
        # is never on its own a reason a match goes unplaced.
        if not _lit_room(occ, cfg, day, loc, st, en, cap):
            continue
        if not _location_open(cfg, day, loc, st, en):
            continue
        out.append(loc)
    if m is not None and cfg.venue_rules and len(out) > 1:
        out.sort(key=lambda loc: _venue_demerit(m, loc, day, st, cfg, occ))
    return out


def _free_location(occ: dict, day: str, st: datetime, en: datetime, cfg: MultiConfig,
                   m: Optional["Match"] = None):
    """Deferred-court capacity model (replaces _free_court). Return the lowest-order
    location with spare concurrent capacity for [st, en) on `day` that is also within
    its hours window. Court NUMBERS are never assigned — a location simply holds up to
    `capacity` concurrent matches (time-of-day-aware under R7-3 morning caps). Returns
    the location id (may be None for the pool) or _FULL when nothing has room.
    Deterministic: pure function of (occ, day, slot, cfg), same location order every call.

    NOT ON THE PLACEMENT PATH since FIX-1 item 1 (2026-07-30) replaced both of its call sites
    with `_scan_locations` — measured at VENUE-1 (2026-08-05): this function is referenced by
    nothing. It is kept as the single-candidate reader of the scan and carries VENUE-1's `m` so
    the two cannot drift apart; a future caller gets the venue rules automatically."""
    cands = _scan_locations(occ, day, st, en, cfg, m)
    return cands[0] if cands else _FULL


def _mark_slot(occ: dict, day: str, st: datetime, en: datetime, loc: Optional[str]):
    """Record a placed match's occupancy at (day, loc) ending at `en`."""
    occ.setdefault((day, st), []).append((loc, en))


def _feeders_done(m: Match, by_id, st) -> bool:
    for f in m.feeders:
        fm = by_id.get(f)
        if fm is None:
            continue
        if not fm.scheduled_needed:
            continue   # bye walkover: considered done immediately
        if fm.end is None or fm.end > st:
            return False
    return True


def _lineage_rested(m: Match, by_id, st, s2s_minutes, cfg=None, exempt=None, mid=None) -> bool:
    """R1: an advancing player's next match must start >= s2s past the feeder's START.

    ENG-1 (ruling 72): `cfg`/`exempt` carry the same-day-finish exception — one of the FOUR sites
    that must honour it, and the one a same-day final hits first (its own semifinal is its feeder).
    Omitted => the full floor, so every existing caller is unchanged."""
    for f in m.lineage:
        fm = by_id.get(f)
        if fm and fm.scheduled_needed and fm.start:
            floor = (_s2s_for(mid or m.mid, f, cfg, exempt) if cfg is not None and exempt
                     else s2s_minutes)
            if st < fm.start + timedelta(minutes=floor):
                return False
    return True


def _humans_ok(m: Match, human_busy, st, en, s2s_minutes, cand_loc=None, transit=None,
               cfg=None, exempt=None) -> bool:
    """R1: two of a player's matches must START >= s2s_minutes apart (start-to-start),
    must not overlap, and — across DIFFERENT locations — must also clear inter-location
    transit (end-to-start). Start-to-start is expressed natively so it stays correct when
    match durations vary (OI-19); transit is layered on top, never dropped (SCH-01b).

    ENG-1 (ruling 72): `cfg`/`exempt` carry the same-day-finish exception. The OVERLAP and TRANSIT
    tests are never relaxed by it — only the rest floor yields, and only between two matches that
    are both inside one named division's last-two-round pair. Omitted => the full floor."""
    for h in m.humans:
        for entry in human_busy.get(h, []):
            bs, be = entry[0], entry[1]
            busy_loc = entry[3] if len(entry) > 3 else None
            busy_mid = entry[4] if len(entry) > 4 else None
            # no overlap (robust to variable durations)
            if st < be and bs < en:
                return False
            # R1 start-to-start rest — at the pair's own floor (the exception, where it applies)
            s2s = timedelta(minutes=(_s2s_for(m.mid, busy_mid, cfg, exempt)
                                     if cfg is not None and exempt else s2s_minutes))
            if not (st >= bs + s2s or bs >= st + s2s):
                return False
            # SCH-01b: consecutive matches at DIFFERENT locations must also clear transit.
            if transit and cand_loc is not None and busy_loc is not None and cand_loc != busy_loc:
                tmin = timedelta(minutes=transit.get("|".join(sorted((cand_loc, busy_loc))), 0))
                if not (en + tmin <= bs or be + tmin <= st):
                    return False
    return True


# --------------------------------------------------------------------------
# CONFLICT WORDING (LANG-1 / A7c, glossary ruling 3)
# --------------------------------------------------------------------------
# The RULE CONFLICTS sheet leads the printed draw sheets, and it is the ONLY TD-facing surface
# that ever printed the internal match id (`E36-R1-M14`). Measured at LANG-1 drafting: that id
# appears on no other output the director holds — the draw sheets use it as a lookup key and
# never draw it, the run-of-play and player handouts never carry it, and the Edit console holds
# it in a `div.mid` that computes to `display:none`. So the one page that told him two matches
# were wrong gave him no way to find them.
#
# These helpers name a match the way his paperwork names it: division, round, players. They are
# module-level ON PURPOSE — `validate_multi` is engine-adjacent and LANG-1's sign-off is wording
# only, so every edit inside that function is confined to a string literal. Each helper is pure
# and self-sufficient (it derives what it needs from `matches`/`cfg`), which is what lets it be
# called from inside an f-string without adding a setup line to the function.
def _c_day(day: str) -> str:
    """`Sat 24 Jan` — a date a director reads off a wall sheet, not `2026-01-24`."""
    if not day:
        return ""
    try:
        d = datetime.strptime(day, "%Y-%m-%d")
    except (TypeError, ValueError):
        return str(day)
    return f"{d.strftime('%a')} {d.day} {d.strftime('%b')}"


def _c_when(m: "Match") -> str:
    """`11:00 Sat 24 Jan` — the slot as it reads on paper."""
    if not m.start:
        return _c_day(m.day)
    return f"{m.start.strftime('%H:%M')} {_c_day(m.day)}"


def _c_side(names, shared) -> str:
    """`Dunnett/Wilkins`. Surnames, because that is how a draw sheet reads — but a surname that
    is NOT unique inside its own match keeps its first name. Measured on the committed field:
    **12 of 1035 matches** pair two players who share a surname (mixed-doubles couples), and
    `Stanley/Stanley` names nobody, which is the exact defect ruling 3 exists to remove."""
    out = []
    for n in names:
        sur = n.split()[-1] if n.split() else n
        out.append(n if sur in shared else sur)
    return "/".join(out)


def _c_winner_of(mid: str) -> str:
    """The Edit console's own fallback for a round whose players are not decided yet."""
    g = re.search(r"-R(\d+)-M(\d+)$", mid or "")
    return f"winner of R{g.group(1)} M{g.group(2)}" if g else (mid or "an earlier match")


def _c_players(m: "Match") -> str:
    """`Dunnett/Wilkins v Grant/Ruffin`, falling back to `winner of R1 M2 v winner of R1 M4`
    for a round nobody has qualified for yet (glossary ruling 3's stated fallback)."""
    a, b = list(m.team_a or []), list(m.team_b or [])
    named = a + b
    surs = [n.split()[-1] for n in named if n.split()]
    shared = {s for s in surs if surs.count(s) > 1}
    if a and b:
        return f"{_c_side(a, shared)} v {_c_side(b, shared)}"
    waits = [_c_winner_of(f) for f in (m.feeders or [])]
    if a or b:
        return f"{_c_side(a or b, shared)} v {waits[0] if waits else 'an opponent'}"
    if waits:
        return " v ".join(waits)
    return _c_winner_of(m.mid)


def _c_match(m: "Match", matches: list, cfg: "MultiConfig") -> str:
    """`Men's 70 & over doubles, Round 1 — Dunnett/Wilkins v Grant/Ruffin` — division, round and
    players, never the internal id (glossary ruling 3).

    A ROUND ROBIN has no final: its round 6 is round 6, not "the final". Same carve-out
    `schedule_views._round_label` makes, for the same reason — a wrong word on a posted sheet
    cannot be taken back.
    """
    if m.draw == "rr" or m.rnd is None:
        rnd = f"Round {m.rnd}" if m.rnd is not None else ""
    else:
        fin = _final_rounds(matches, cfg).get(m.event)
        rnd = _round_name(m.rnd, fin) if fin else f"Round {m.rnd}"
    head = f"{m.event}, {rnd}" if rnd else f"{m.event}"
    return f"{head} — {_c_players(m)}"


def _c_earlier_kinds(kind: str, order: dict) -> str:
    """`singles and mixed` — the kinds this day runs BEFORE this one, named outright. "earlier-kind"
    is banned from every TD-facing surface (glossary §2), so the sentence says which kinds."""
    rank = order.get(kind)
    if rank is None:
        return "earlier matches"
    earlier = [k for k, i in sorted(order.items(), key=lambda kv: kv[1]) if i < rank]
    if not earlier:
        return "earlier matches"
    if len(earlier) == 1:
        return earlier[0]
    return ", ".join(earlier[:-1]) + " and " + earlier[-1]


# --------------------------------------------------------------------------
# VALIDATION (independent re-check)
# --------------------------------------------------------------------------
def validate_multi(matches: list[Match], cfg: MultiConfig) -> list[str]:
    issues = []
    placed = [m for m in matches if m.start]
    # capacity clashes (deferred-court model): court numbers are never assigned, so a
    # clash is an over-capacity LOCATION — more concurrent matches at a (day, location)
    # than that location's capacity — not two matches sharing a numbered court.
    cap_groups: dict = {}
    for m in placed:
        cap_groups.setdefault((m.day, m.location), []).append(m)
    for (day, loc), ms in cap_groups.items():
        cap = dict(_day_locations(cfg, day)).get(loc)
        if cap is None:                       # location not in the layout (e.g. pool without cfg) — cannot bound
            continue
        # True peak concurrency via a sweep over endpoints. At a shared instant an end (-1)
        # is processed before a start (+1), so touching windows [.,end)|[end,.) don't overlap —
        # matching placement's half-open [st, en) capacity model. (The prior "count matches
        # overlapping a, take the max" over-reported when 30-min-offset matches bridged two
        # 90-min blocks, e.g. under the AVOID-3 09:30 floor.)
        pts = []
        for m in ms:
            pts.append((m.start, 1))
            pts.append((m.end, -1))
        # R7-3: the cap is time-of-day-aware — before the switch the morning count binds.
        # A zero-delta point at the switch splits the sweep so each segment is audited
        # against the cap in force at its own start instant.
        mc = cfg.morning_caps.get((loc, day)) if cfg.morning_caps else None
        if mc:
            switch = datetime.strptime(f"{day} {mc[0]}", "%Y-%m-%d %H:%M")
            pts.append((switch, 0))
        # LIGHTS-1 / rule 48: the same trick for the step-DOWN. It is graded per DAY, like rule
        # 6's window mirror, because a lit ceiling is a COUNT and not a property of one match —
        # graded per match it would report every evening match on a legal board. The zero-delta
        # point goes in AT the lights hour so the evening segment is audited under the ceiling in
        # force at its own start instant instead of the daytime court count; without it a board
        # that steps 24 -> 7 at 16:00 is graded against 24 all evening and the mirror reports
        # nothing it was built to catch.
        lit = cfg.venue_lit_courts.get(loc) if cfg.venue_lit_courts else None
        on = cfg.venue_lights_on.get(loc) if lit is not None else None
        gate = datetime.strptime(f"{day} {on}", "%Y-%m-%d %H:%M") if on else None
        if gate:
            pts.append((gate, 0))
        pts.sort(key=lambda x: (x[0], x[1]))
        cur = 0
        worst = worst_cap = None
        worst_lit = False
        # EVERY delta at one instant is applied BEFORE that instant is graded, and LIGHTS-1 is
        # what forced it. Grading each point as it was applied read the transient values inside
        # a single timestamp: at MHCC's lights hour on a forced 12:00 fixture, three matches
        # ENDING at 12:00 were still in the running count while the first of them was graded, so
        # the mirror reported "8 matches at once, 6 lighted courts" against a board whose true
        # concurrency at 12:00 was 6 — a breach placement had correctly refused to build. The
        # morning step-UP could never expose it, because a rising limit grades those same
        # transients under the LARGER number and they vanish. A step-DOWN grades them under the
        # smaller one. Nothing about the pre-LIGHTS-1 grades changes: with one limit across the
        # whole sweep, the running maximum only ever occurs at a timestamp's final value, which
        # is exactly what this loop now tests.
        i = 0
        while i < len(pts):
            t = pts[i][0]
            while i < len(pts) and pts[i][0] == t:
                cur += pts[i][1]
                i += 1
            limit = mc[1] if (mc and t < switch) else cap
            after_lights = gate is not None and t >= gate
            if after_lights:
                limit = min(limit, lit)
            if cur > limit and (worst is None or cur - limit > worst - worst_cap):
                worst, worst_cap, worst_lit = cur, limit, after_lights and limit == lit
        if worst is not None:
            # "7 courts" at a venue the director knows has 24 is a true number that reads as a
            # mistake. When the ceiling that broke is the lit one, the sentence says so — it is
            # the difference between a board he thinks is miscounted and a board he can fix by
            # moving one match out of the dark.
            courts = "lighted courts, after the lights come on" if worst_lit else "courts"
            issues.append(
                f"{loc or 'the pool'}, {_c_day(day)}: {worst} matches at once, "
                f"{worst_cap} {courts}.")
    # human conflicts + rest across ALL events (R1: start-to-start, plus transit)
    # ENG-1 (ruling 72): the same-day-finish exception is resolved ONCE, by the same helper the
    # placement loop calls, and read by both rest mirrors below. Placement and the validator
    # cannot disagree about it — if they did, the engine would build a schedule and then report it
    # broken, and 0 conflicts is the invariant that never bends.
    sdf_exempt = _same_day_finish_pairs(matches, cfg)
    for i, a in enumerate(placed):
        for b in placed[i + 1:]:
            shared = a.humans & b.humans
            if not shared:
                continue
            if a.day != b.day:
                continue
            who = ", ".join(sorted(shared))
            # overlap — NEVER relaxed by the exception
            if a.start < b.end and b.start < a.end:
                issues.append(
                    f"{who}: two matches at once — {_c_match(a, matches, cfg)} at "
                    f"{_c_when(a)}, and {_c_match(b, matches, cfg)} at {_c_when(b)}.")
                continue
            # R1 start-to-start rest, at this PAIR's own floor
            s2s = timedelta(minutes=_s2s_for(a.mid, b.mid, cfg, sdf_exempt))
            if not (a.start >= b.start + s2s or b.start >= a.start + s2s):
                issues.append(
                    f"{who}: under {int(s2s.total_seconds() // 60)} minutes between starts — "
                    f"{_c_match(a, matches, cfg)} at {_c_when(a)}, and "
                    f"{_c_match(b, matches, cfg)} at {_c_when(b)}.")
            # SCH-01b mirror (defense-in-depth): cross-location must also clear transit.
            if a.location is not None and b.location is not None and a.location != b.location:
                tmin = timedelta(minutes=cfg.transit_minutes.get(
                    "|".join(sorted((a.location, b.location))), 0))
                if not (a.end + tmin <= b.start or b.end + tmin <= a.start):
                    issues.append(
                        f"{who}: not enough time to travel between venues "
                        f"({int(tmin.total_seconds() // 60)} min needed) — "
                        f"{_c_match(a, matches, cfg)} at {_c_when(a)} {a.location}, and "
                        f"{_c_match(b, matches, cfg)} at {_c_when(b)} {b.location}.")
    # feeder ordering
    by_id = {m.mid: m for m in matches}
    for m in placed:
        for f in m.feeders:
            fm = by_id.get(f)
            if fm and fm.scheduled_needed and fm.end and m.start < fm.end:
                issues.append(
                    f"Out of draw order — {_c_match(m, matches, cfg)}: {_c_when(m)}, before "
                    f"{_c_match(fm, matches, cfg)} finishes at {fm.end.strftime('%H:%M')}.")

    # ---------------------------------------------------------------- RPT-1 validator mirrors
    # Of the gates `_scan` applies at placement, five were enforced at generation and re-checked
    # nowhere, so a couriered edit could breach any of them and the engine still returned
    # `conflicts: []`. Each block below mirrors one gate, reading the SAME helper the placement
    # loop reads so the two can never drift into disagreeing.
    #
    # Traced at build start (RPT-1 §6 requires it). The brief's §6 list named four; the trace found
    # a fifth — per-location hours — which the `brief.md` *Gates & validation* register did name.
    # All five are here. Assigned-day deviation and round CADENCE are deliberately NOT here: both
    # are preferences, not invariants (§8A row 37), and are reported as info via `spills` /
    # `result["cadence_conflicts"]`. Mirroring cadence as an ISSUE would fire on the committed
    # baseline's one structural Women's-50-doubles collision, which FIX-1 established is reported
    # rather than repaired.

    # AVOID-3 — the per-division earliest-start floor (e.g. 80-and-over -> 09:30).
    floors = {ev.name: datetime.strptime(ev.earliest_start, "%H:%M").time()
              for ev in cfg.events if ev.earliest_start}
    for m in placed:
        floor = floors.get(m.event)
        if floor is not None and m.start.time() < floor:
            issues.append(
                f"{_c_match(m, matches, cfg)}: {_c_when(m)}, before this division's "
                f"{floor.strftime('%H:%M')} earliest start.")

    # Daily window — BOTH ends, plus the day itself. `_scan` never sees an out-of-bounds slot
    # because it iterates the `_slots` grid, which is built only over `cfg.dates` and only from
    # `daily_start`; `daily_end` is a COMPLETION deadline (ruling 27), so the late test is on the
    # match's end less the buffer, exactly as `_scan` computes it. The first cut of this mirror
    # checked the late end alone, which left a couriered edit to an early start — or to a day the
    # tournament does not run — coming back `conflicts: []`, the very hole the block closes.
    # NOT mirrored, deliberately: the grid's 15-minute grain. An off-grid start is a granularity
    # convention, not a feasibility gate, and rejecting one would refuse edits that are playable.
    for m in placed:
        if cfg.dates and m.day not in cfg.dates:
            issues.append(
                f"{_c_match(m, matches, cfg)}: {_c_day(m.day)} is not a tournament day.")
            continue
        day_start = datetime.strptime(f"{m.day} {cfg.daily_start}", "%Y-%m-%d %H:%M")
        day_end = datetime.strptime(f"{m.day} {cfg.daily_end}", "%Y-%m-%d %H:%M") - timedelta(
            minutes=cfg.end_of_day_buffer_minutes)
        if m.start < day_start:
            issues.append(
                f"{_c_match(m, matches, cfg)}: {_c_when(m)}, before play opens at "
                f"{cfg.daily_start}.")
        if m.end > day_end:
            issues.append(
                f"{_c_match(m, matches, cfg)}: {_c_when(m)}, ending "
                f"{m.end.strftime('%H:%M')} — past the {day_end.strftime('%H:%M')} cutoff.")

    # OI-23 — per-location hours. The pool (location None) and an unwindowed location fall back
    # to the tournament-wide window inside `_location_open`, so this never fires on a cfg with no
    # `location_hours` and stays byte-identical for the small self-tests.
    for m in placed:
        if not _location_open(cfg, m.day, m.location, m.start, m.end):
            issues.append(
                f"{_c_match(m, matches, cfg)}: {_c_when(m)}–{m.end.strftime('%H:%M')} at "
                f"{m.location or 'the pool'}, outside that venue's hours.")

    # VENUE-1 (rules 6/31/38/39/40) — THE VENUE MIRROR, one pass covering every enabled rule.
    #
    # Every mirror TOLERATES A RECORDED ESCAPE, and that is the whole point of writing it in the
    # same build as the rules: without it the tool builds a schedule, legally places a match at
    # the only venue that had room, and then turns round and reports its own legal fallback as a
    # conflict. `venue_escapes` is keyed on (mid, day, start, location) — the slot AND the venue —
    # so an escape granted for one placement does not follow the match somewhere else. Move the
    # match and the pass is revoked, exactly as ruling 73 shaped `day_shape_exceptions`.
    #
    # `venue_final_rnd` is rebuilt here rather than read off the config: the mirror is called on
    # couriered edits by consumers that never ran placement, and a stale map would mirror a rule
    # against the wrong round.
    # THE TWO KINDS OF RULE MIRROR DIFFERENTLY, and conflating them is a real defect this build
    # hit and fixed. Rules 38/39/40/31 are about ONE match — "is this match allowed to be here" —
    # and mirror per match. Rule 6 is a COUNT over a window, and a count cannot be mirrored per
    # match: at placement each match is tested against the day AS IT STOOD WHEN IT LANDED, but
    # the mirror sees the finished day, so on a day that ends up over the ceiling EVERY match in
    # the window looks like the offender while only the one that actually crossed the line
    # carries an escape. Measured: a single-venue 20-court slate reported 9 conflicts that way,
    # against a schedule the engine had built entirely legally — 0 conflicts is the invariant
    # that never bends, so the counting rule is graded per DAY below instead.
    if cfg.venue_rules and cfg.venue_order:
        mirror_cfg = replace(cfg, venue_final_rnd=_final_rounds(matches, cfg))
        main = _venue_main_site(cfg)
        # `occ` is deliberately NOT passed: without it `_venue_demerit` skips the counting rule
        # and answers only the per-match question this loop is entitled to ask.
        for m in placed:
            if not _venue_demerit(m, m.location, m.day, m.start, mirror_cfg):
                continue
            if (m.mid, m.day, m.start.strftime("%H:%M"), m.location) in cfg.venue_escapes:
                continue                       # rule 41: placed and recorded, and therefore legal
            issues.append(
                f"{_c_match(m, matches, cfg)}: {_c_when(m)} at {m.location or 'the pool'} — "
                f"your venue rules do not allow it and no exception was recorded "
                f"(main site {main or 'unset'}).")

        # Rule 6, graded per (day, main site): a day may sit over the ceiling exactly as far as
        # its recorded exceptions carry it, and no further.
        pw = cfg.venue_rules.get("peak_window")
        if pw and main is not None:
            lo, hi = pw.get("start", "15:00"), pw.get("end", "16:00")
            mx = pw.get("max_starts", 9)
            per_day: dict = {}
            for m in placed:
                if m.location == main and lo <= m.start.strftime("%H:%M") < hi:
                    per_day.setdefault(m.day, []).append(m)
            for day in sorted(per_day):
                ms = per_day[day]
                excused = sum(
                    1 for m in ms
                    if (m.mid, m.day, m.start.strftime("%H:%M"), m.location) in cfg.venue_escapes)
                if len(ms) - excused <= mx:
                    continue
                issues.append(
                    f"{main}, {_c_day(day)}: {len(ms)} matches start between {lo} and {hi}, "
                    f"above your limit of {mx}. {excused} recorded as exceptions.")

    # FAC Table 9 — the per-(division, player, day) match cap.
    caps = {ev.name: ev.max_matches_per_day for ev in cfg.events}
    day_count: dict = {}
    for m in placed:
        for h in m.humans:
            day_count[(m.event, h, m.day)] = day_count.get((m.event, h, m.day), 0) + 1
    for (event, human, day) in sorted(day_count):
        cap = caps.get(event)
        n = day_count[(event, human, day)]
        if cap is not None and n > cap:
            issues.append(
                f"{human}: {n} {event} matches on {_c_day(day)}, limit {cap}.")

    # R1 lineage rest — an advancing player's next match must start >= s2s past the feeder's
    # START. Distinct from the person-rest check above, which can only see matches whose players
    # are already known; lineage binds the undecided rounds too.
    for m in placed:
        if m.lineage and not _lineage_rested(m, by_id, m.start, cfg.min_start_to_start_minutes,
                                             cfg, sdf_exempt, m.mid):
            issues.append(
                f"{_c_match(m, matches, cfg)}: {_c_when(m)}, under "
                f"{cfg.min_start_to_start_minutes} minutes' rest after the last round started.")

    # ---------------------------------------------------------------- ENG-1 mirrors (2026-08-02)
    # Each reads the SAME helper the placement loop reads. The 15:00-16:00 start ceiling gets NO
    # mirror here, and that is a DECISION, not an omission: it is a reporter warning about
    # operational slack (D-37 / ruling 65), not a feasibility rule, and mirroring it would make a
    # warning the TD chose not to enforce into a blocking conflict.

    # F-4 / M6 (ruling 74) — the finals floor. ROUND-AWARE and FINALS ONLY: a semifinal at 08:00
    # must NOT raise an issue here, which is exactly what the event-keyed `earliest_start` mirror
    # above cannot express.
    # Both gates below can be RELAXED by the escape rung when nothing else would seat the match
    # (0-unplaced is the harder invariant), so both mirrors tolerate the recorded escapes on the
    # exact slot they were granted for — otherwise the engine reports its own legal fallbacks.
    def _slot(m):
        return (m.mid, m.day, m.start.strftime("%H:%M"))
    escaped = cfg.rule_escapes or set()

    fin_floors = {ev.name: datetime.strptime(ev.finals_earliest, "%H:%M").time()
                  for ev in cfg.events if ev.finals_earliest}
    if fin_floors:
        final_rnd = _final_rounds(matches, cfg)
        for m in placed:
            fl = fin_floors.get(m.event)
            if fl is not None and m.rnd == final_rnd.get(m.event) and m.start.time() < fl \
                    and _slot(m) not in escaped:
                issues.append(
                    f"{_c_match(m, matches, cfg)}: {_c_when(m)}, before the "
                    f"{fl.strftime('%H:%M')} earliest start for a final.")

    # D-40 / ruling 67 — the three-event head start, "at or earlier", triple days only.
    bands, band_days = _band_setup(cfg, matches)
    if bands:
        for m in placed:
            if not _in_band(m, m.day, m.start, bands, band_days) and _slot(m) not in escaped:
                lim = bands[_event_kind(m.event)]
                issues.append(
                    f"{_c_match(m, matches, cfg)}: {_c_when(m)} — a player is in 3 divisions "
                    f"that day, and {_event_kind(m.event)} must start by "
                    f"{lim.strftime('%H:%M')}.")

    # Ruling 73 — the day shape, singles -> mixed -> doubles at the clock. THE MIRROR MUST TOLERATE
    # THE RECORDED ESCAPES. Without that it would report the engine's own legal fallbacks as
    # conflicts, on precisely the days the escape exists for, and break 0-conflicts. What it still
    # catches is the case it is for: a COURIERED EDIT that puts a match out of shape where no
    # escape was recorded.
    kind_order = kind_order_of(cfg)
    if kind_order:
        recorded = cfg.day_shape_exceptions or set()
        for m in day_shape_violations(matches, kind_order,
                                      no_precedent=frozenset(cfg.day_shape_no_precedent or ())):
            if _slot(m) in recorded:
                continue
            issues.append(
                f"{_c_match(m, matches, cfg)}: {_c_when(m)}, ahead of that day's "
                f"{_c_earlier_kinds(_event_kind(m.event), kind_order)}.")

    # CAD-1 (ruling R1, 2026-08-18) — THE CADENCE MIRROR. Rule 16 is INVARIABLE for the engine's
    # own output: no rung of the ladder can now put two rounds of one division on one day, and no
    # rung can print a round before one of its own earlier rounds. That is exactly why this rung
    # exists. A rule the engine cannot break is a rule whose only remaining source is the OTHER
    # side of the courier — a TD edit, or a supplied day map — and the mirror is the last line
    # there. On the engine's own build it is silent by construction, which is what part A of
    # `tests/cad1_invariant.py` measures; part G is the courier case it is actually for.
    #
    # It grades from the FINISHED schedule, through the same `_true_round_of` that placement used,
    # so a round-robin group's flat match index cannot be read as a cadence breach (a naive count
    # of the real field says 23 where the true figure is 2).
    #
    # THE ONE EXCUSE IS `_same_day_finish_cells` AND NOTHING ELSE (ruling R5's shape, applied
    # here): a division the TD NAMED in his same-day-finish switch is his own instruction, and
    # reporting it back at him is what the reporter's wider closing-day allowance used to do.
    #
    # CONDITIONED ON A DAY MAP EXISTING, exactly as placement's own guard is (patches 1/3/3b).
    # This is not a convenience — it is the mirror rule. Cadence is PLAN-relative: "one round a
    # day" is a statement about a schedule built from a day map, and the no-map diagnostic hatch
    # (D-3) has no plan to be one round a day against. It carries 67 cells by construction and
    # always has. A mirror that graded them would report 67 conflicts on a board placement
    # deliberately built that way — the engine building a schedule and then calling it broken,
    # which is the one thing the write-once-read-twice discipline exists to prevent. The edit
    # lane keeps the build's own cfg, so every courier-edited PRODUCT schedule is still graded.
    if cfg.assigned_days:
        _cadence_mirror(issues, placed, matches, cfg)
    return issues


def _cadence_mirror(issues, placed, matches, cfg: MultiConfig) -> None:
    """CAD-1's cadence rung, factored out so the one condition above reads as the rule it is."""
    sdf_cells = _same_day_finish_cells(matches, cfg)
    by_cell: dict = {}
    span: dict = {}          # (event, true round) -> [earliest day, latest day]
    for m in placed:
        tr = _true_round_of(cfg, m.event, m.rnd)
        by_cell.setdefault((m.event, m.day), {}).setdefault(tr, []).append(m)
        lohi = span.get((m.event, tr))
        span[(m.event, tr)] = [min(lohi[0], m.day), max(lohi[1], m.day)] if lohi \
            else [m.day, m.day]
    for (event, day), rounds in sorted(by_cell.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")):
        if len(rounds) < 2 or (event, day) in sdf_cells:
            continue
        # ONE sentence per cell — count and name, not one per match. Named to a match all the
        # same, like every other sentence here, so the printed conflicts sheet carries division,
        # round and players on the row rather than a bare day. The match named is the LATER
        # round's earliest, which is the one a director would move.
        late = sorted(rounds)[-1]
        m = sorted(rounds[late], key=lambda x: (x.start, x.mid))[0]
        issues.append(
            f"{_c_match(m, matches, cfg)}: {_c_when(m)} — this division has more than one round "
            f"on {day} (rounds {', '.join(str(x) for x in sorted(rounds))}), and it plays one "
            f"round a day.")

    # The day-level half of the same rule: a later round may not sit on an EARLIER day than one
    # its own earlier round already holds. Same-day is the cell above; this is the BACKWARDS case,
    # which is what the forward-only limit (patches 3/3b) prevents in placement — and which,
    # measured, is what a plan-relative check alone lets through the moment courts get tight
    # (3 division-round pairs printing backwards at 80% courts, 8 at 50%). Graded strictly (`<`),
    # so a same-day pairing is reported once, as a cell, and never twice.
    for event in sorted({ev for (ev, _tr) in span}):
        trs = sorted(tr for (ev, tr) in span if ev == event)
        for i, tr in enumerate(trs):
            back = [t for t in trs[i + 1:] if span[(event, t)][0] < span[(event, tr)][1]]
            if not back:
                continue
            day = span[(event, back[0])][0]
            m = sorted(by_cell[(event, day)][back[0]], key=lambda x: (x.start, x.mid))[0]
            issues.append(
                f"{_c_match(m, matches, cfg)}: {_c_when(m)} — an earlier round of this division "
                f"plays as late as {span[(event, tr)][1]}, and a round never plays before one of "
                f"its own earlier rounds.")
            break
