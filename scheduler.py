"""
WynTennis Tournament Scheduling Engine
======================================
Deterministic, conflict-free match scheduler for club-level tennis events.

Enforces:
  - Court capacity (no court double-booked)
  - Bracket dependency (a round cannot start before its feeder matches finish)
  - Player recovery gap (configurable; club default 60 min, pro mode 12h)
  - Match-type precedence (main draw > round robin > consolation)
  - Daily time bounds + end-of-day buffer
  - Finals-backward placement (finals land in the last available slot)

Supported formats: single_elim, compass (single-elim + first-round consolation),
                    round_robin, round_robin_playoff
Draw sizes (elim): 8, 16, 32, 64 (powers of two)
RR group size:     3-8 players per group

Author: built for WynTennis (Caerwyn Evans). Tunable via TournamentConfig.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import math
from typing import Optional


# --------------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------------
@dataclass
class TournamentConfig:
    event_name: str
    fmt: str                       # single_elim | compass | round_robin | round_robin_playoff
    num_courts: int
    dates: list[str]               # ["2026-03-14", "2026-03-15"]
    daily_start: str = "08:00"
    daily_end: str = "18:00"

    # Elimination inputs
    draw_size: Optional[int] = None        # 8/16/32/64 for elim formats

    # Round-robin inputs
    num_players: Optional[int] = None      # total players for RR
    group_size: int = 4                    # players per RR group

    # Timing
    match_minutes: int = 105               # 90 play + 15 warmup/transition
    min_recovery_minutes: int = 60         # legacy end-to-start gap; superseded by min_start_to_start_minutes (R1)
    min_start_to_start_minutes: int = 180  # R1: a player's matches must start >= this many minutes apart (3h default)
    pro_rest: bool = False                 # legacy; end-to-start pro mode, no longer drives rest (R1)
    end_of_day_buffer_minutes: int = 45    # contingency tail each day

    # Compliance flags (surfaced in output, do not alter math)
    sanctioned: bool = False
    utr_verified: bool = False

    def recovery(self) -> int:
        return 720 if self.pro_rest else self.min_recovery_minutes


# --------------------------------------------------------------------------
# MATCH MODEL
# --------------------------------------------------------------------------
@dataclass
class Match:
    mid: str                       # unique id, e.g. "MD-R1-M3"
    rnd: int                       # round number (1 = first)
    label: str                     # human label, e.g. "Main R1 Match 3"
    draw: str                      # "main" | "consolation" | "rr"
    precedence: int                # lower = scheduled first (main=0, rr=0, consol=1)
    feeders: list[str] = field(default_factory=list)   # mids that must finish first
    players: list[str] = field(default_factory=list)   # known identities (RR) or [] (elim)
    lineage: list[str] = field(default_factory=list)   # feeder mids whose winners play here
    # assigned at scheduling time:
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    court: Optional[int] = None
    day: Optional[str] = None


# --------------------------------------------------------------------------
# DRAW GENERATION
# --------------------------------------------------------------------------
def _is_power_of_two(n: int) -> bool:
    return n >= 2 and (n & (n - 1)) == 0


def build_single_elim(draw_size: int, draw_tag: str = "main", prefix: str = "MD") -> list[Match]:
    if not _is_power_of_two(draw_size):
        raise ValueError(f"Elimination draw_size must be a power of two (8/16/32/64); got {draw_size}")
    rounds = int(math.log2(draw_size))
    matches: list[Match] = []
    prev_round_ids: list[str] = []
    for r in range(1, rounds + 1):
        n_matches = draw_size // (2 ** r)
        this_round_ids = []
        for m in range(1, n_matches + 1):
            mid = f"{prefix}-R{r}-M{m}"
            rname = _round_name(r, rounds)
            label = f"{'Main' if draw_tag=='main' else draw_tag.title()} {rname} Match {m}"
            feeders, lineage = [], []
            if r > 1:
                # this match is fed by two matches from the previous round
                f1 = prev_round_ids[(m - 1) * 2]
                f2 = prev_round_ids[(m - 1) * 2 + 1]
                feeders = [f1, f2]
                lineage = [f1, f2]
            matches.append(Match(
                mid=mid, rnd=r, label=label, draw=draw_tag,
                precedence=0 if draw_tag == "main" else 1,
                feeders=feeders, lineage=lineage,
            ))
            this_round_ids.append(mid)
        prev_round_ids = this_round_ids
    return matches


def _round_name(r: int, total_rounds: int) -> str:
    from_end = total_rounds - r
    return {0: "Final", 1: "Semifinal", 2: "Quarterfinal"}.get(from_end, f"Round {r}")


def build_compass(draw_size: int) -> list[Match]:
    """Single elim main draw + an 'East' consolation fed by R1 losers."""
    main = build_single_elim(draw_size, "main", "MD")
    # Consolation draw = first-round losers => draw_size/2 entrants
    consol_size = draw_size // 2
    consol = build_single_elim(consol_size, "consolation", "CN") if consol_size >= 2 else []
    # Tie consolation R1 feeders to main R1 losers (lineage only; recovery applies)
    main_r1 = [m for m in main if m.rnd == 1]
    consol_r1 = [m for m in consol if m.rnd == 1]
    for i, cm in enumerate(consol_r1):
        # each consolation R1 match draws losers from two main R1 matches
        src = main_r1[i * 2: i * 2 + 2]
        cm.lineage = [s.mid for s in src]
        cm.feeders = [s.mid for s in src]   # losers known only after those finish
    return main + consol


def build_round_robin(num_players: int, group_size: int) -> list[Match]:
    """Split players into groups; round-robin within each group (circle method)."""
    if num_players < 3:
        raise ValueError("Round robin needs at least 3 players")
    groups = _partition_groups(num_players, group_size)
    matches: list[Match] = []
    pnum = 1
    for gi, gsize in enumerate(groups):
        labels = [f"P{pnum + i}" for i in range(gsize)]
        pnum += gsize
        gid = chr(ord('A') + gi)
        for ri, (a, b) in enumerate(_circle_pairings(labels), start=1):
            mid = f"RR-{gid}-M{ri}-{a}v{b}"
            matches.append(Match(
                mid=mid, rnd=ri, label=f"Group {gid}: {a} vs {b}",
                draw="rr", precedence=0, players=[a, b],
            ))
    return matches


def _partition_groups(num_players: int, group_size: int) -> list[int]:
    """Return list of group sizes, balanced, each between 3 and group_size."""
    g = max(1, round(num_players / group_size))
    base = num_players // g
    rem = num_players % g
    sizes = [base + (1 if i < rem else 0) for i in range(g)]
    # ensure no group < 3 by merging
    sizes = [s for s in sizes if s > 0]
    while len(sizes) > 1 and min(sizes) < 3:
        sizes.sort()
        small = sizes.pop(0)
        sizes[0] += small
    return sizes


def _circle_pairings(players: list[str]) -> list[tuple[str, str]]:
    """Standard round-robin (circle method). Returns all unique pairings in round order."""
    p = players[:]
    if len(p) % 2:
        p.append(None)  # bye
    n = len(p)
    pairings = []
    for _ in range(n - 1):
        for i in range(n // 2):
            a, b = p[i], p[n - 1 - i]
            if a is not None and b is not None:
                pairings.append((a, b))
        p = [p[0]] + [p[-1]] + p[1:-1]  # rotate, keep first fixed
    return pairings


# --------------------------------------------------------------------------
# SLOT MODEL + SCHEDULER
# --------------------------------------------------------------------------
def _day_slots(cfg: TournamentConfig) -> list[tuple[str, datetime, datetime]]:
    """Generate (day, slot_start, slot_end) tuples across all dates."""
    slots = []
    for d in cfg.dates:
        start = datetime.strptime(f"{d} {cfg.daily_start}", "%Y-%m-%d %H:%M")
        end = datetime.strptime(f"{d} {cfg.daily_end}", "%Y-%m-%d %H:%M")
        usable_end = end - timedelta(minutes=cfg.end_of_day_buffer_minutes)
        t = start
        while t + timedelta(minutes=cfg.match_minutes) <= usable_end:
            slots.append((d, t, t + timedelta(minutes=cfg.match_minutes)))
            t += timedelta(minutes=cfg.match_minutes)
    return slots


def schedule(cfg: TournamentConfig) -> dict:
    # 1. Build matches
    if cfg.fmt == "single_elim":
        matches = build_single_elim(cfg.draw_size)
    elif cfg.fmt == "compass":
        matches = build_compass(cfg.draw_size)
    elif cfg.fmt in ("round_robin", "round_robin_playoff"):
        matches = build_round_robin(cfg.num_players, cfg.group_size)
        if cfg.fmt == "round_robin_playoff":
            # 4-player playoff (SF + F) that MUST follow all group play.
            rr_ids = [m.mid for m in matches]           # every group match
            max_rr_round = max((m.rnd for m in matches), default=0)
            playoff = build_single_elim(4, "main", "PO")
            for m in playoff:
                m.draw = "main"
                m.precedence = 0
                m.rnd += max_rr_round              # force playoff to sort AFTER group rounds
                # SF round (originally rnd 1) gates on ALL group matches completing
                if m.mid.startswith("PO-R1"):
                    m.feeders = rr_ids
                    m.lineage = rr_ids
            matches += playoff
    else:
        raise ValueError(f"Unknown format: {cfg.fmt}")

    by_id = {m.mid: m for m in matches}
    slots = _day_slots(cfg)
    if not slots:
        return {"ok": False, "error": "No usable time slots. Widen daily hours or reduce buffer."}

    # discrete slot index per (start time); group courts under each slot start
    distinct_starts = sorted(set((s[0], s[1], s[2]) for s in slots), key=lambda x: x[1])
    court_usage: dict[datetime, set[int]] = {ds[1]: set() for ds in distinct_starts}

    s2s = timedelta(minutes=cfg.min_start_to_start_minutes)   # R1: start-to-start rest

    # 2. Order matches: precedence, then round, then draw (main before consol)
    order = sorted(matches, key=lambda m: (m.precedence, m.rnd, 0 if m.draw == "main" else 1, m.mid))

    unplaced = []
    for m in order:
        placed = False
        for (day, st, en) in distinct_starts:
            # court availability
            if len(court_usage[st]) >= cfg.num_courts:
                continue
            # feeder dependency: all feeders must END before this match STARTS
            if not _feeders_done(m, by_id, st):
                continue
            # R1 rest: known players (RR) must start >= s2s from any other match, no overlap
            if m.players and not _players_rested(m, matches, st, en, s2s):
                continue
            # R1 rest via lineage (elim): start >= s2s past the feeder's start
            if m.lineage and not _lineage_rested(m, by_id, st, s2s):
                continue
            # assign
            court = _first_free_court(court_usage[st], cfg.num_courts)
            m.start, m.end, m.court, m.day = st, en, court, day
            court_usage[st].add(court)
            placed = True
            break
        if not placed:
            unplaced.append(m.mid)

    result = {
        "ok": len(unplaced) == 0,
        "event": cfg.event_name,
        "format": cfg.fmt,
        "courts": cfg.num_courts,
        "match_minutes": cfg.match_minutes,
        "min_start_to_start_minutes": cfg.min_start_to_start_minutes,   # R1
        "sanctioned": cfg.sanctioned,
        "utr_verified": cfg.utr_verified,
        "total_matches": len(matches),
        "unplaced": unplaced,
        "schedule": [
            {
                "match": m.label, "id": m.mid, "draw": m.draw, "round": m.rnd,
                "day": m.day,
                "start": m.start.strftime("%H:%M") if m.start else None,
                "end": m.end.strftime("%H:%M") if m.end else None,
                "court": m.court,
            }
            for m in sorted(matches, key=lambda x: (x.start or datetime.max, x.court or 0))
        ],
    }
    result["conflicts"] = validate(matches, cfg)
    if unplaced:
        result["diagnosis"] = _diagnose(cfg, matches, slots)
    return result


def _diagnose(cfg: TournamentConfig, matches: list[Match], slots: list) -> dict:
    """Explain WHY a schedule didn't fit and suggest the smallest fix."""
    distinct_starts = len(set(s[1] for s in slots))
    capacity = distinct_starts * cfg.num_courts
    demand = len(matches)
    # crude capacity check + actionable levers
    suggestions = []
    if demand > capacity:
        suggestions.append(
            f"Raw capacity short: {demand} matches need slots but only "
            f"{capacity} court-slots exist ({distinct_starts} time blocks x {cfg.num_courts} courts)."
        )
    extra_courts_needed = max(0, math.ceil(demand / max(distinct_starts, 1)) - cfg.num_courts)
    suggestions.append(
        f"Smallest fixes: add ~{extra_courts_needed or 1} court(s), "
        f"OR add a day, OR shorten match_minutes (e.g. fast-4 / shorter sets), "
        f"OR reduce the start-to-start rest (currently {cfg.min_start_to_start_minutes} min)."
    )
    return {
        "time_blocks_per_run": distinct_starts,
        "court_slots_available": capacity,
        "matches_to_place": demand,
        "suggestions": suggestions,
    }


def _feeders_done(m: Match, by_id: dict, start: datetime) -> bool:
    for f in m.feeders:
        fm = by_id.get(f)
        if fm is None or fm.end is None or fm.end > start:
            return False
    return True


def _first_free_court(used: set[int], num_courts: int) -> int:
    for c in range(1, num_courts + 1):
        if c not in used:
            return c
    raise RuntimeError("no free court (should not happen)")


def _players_rested(m: Match, all_matches: list[Match], st: datetime, en: datetime, s2s: timedelta) -> bool:
    # R1: a player's matches must START >= s2s apart and must not overlap (start-to-start,
    # expressed natively so it stays correct when match durations vary).
    for other in all_matches:
        if other is m or other.start is None:
            continue
        if set(m.players) & set(other.players):
            if st < other.end and other.start < en:            # overlap
                return False
            if not (st >= other.start + s2s or other.start >= st + s2s):
                return False
    return True


def _lineage_rested(m: Match, by_id: dict, st: datetime, s2s: timedelta) -> bool:
    # R1: an advancing player's next match must start >= s2s past the feeder's START.
    for f in m.lineage:
        fm = by_id.get(f)
        if fm and fm.start and st < fm.start + s2s:
            return False
    return True


# --------------------------------------------------------------------------
# VALIDATION (independent re-check, defense in depth)
# --------------------------------------------------------------------------
def validate(matches: list[Match], cfg: TournamentConfig) -> list[str]:
    issues = []
    placed = [m for m in matches if m.start]
    # court double-booking
    seen = {}
    for m in placed:
        key = (m.day, m.start, m.court)
        if key in seen:
            issues.append(f"COURT CLASH: {m.mid} and {seen[key]} on court {m.court} @ {m.start}")
        seen[key] = m.mid
    # feeder ordering
    by_id = {m.mid: m for m in matches}
    for m in placed:
        for f in m.feeders:
            fm = by_id.get(f)
            if fm and fm.end and m.start < fm.end:
                issues.append(f"DEPENDENCY: {m.mid} starts before feeder {f} ends")
    # R1 rest (RR known players): start-to-start, no overlap
    s2s = timedelta(minutes=cfg.min_start_to_start_minutes)
    for i, a in enumerate(placed):
        for b in placed[i + 1:]:
            if a.players and b.players and (set(a.players) & set(b.players)):
                if a.start < b.end and b.start < a.end:
                    issues.append(f"REST: {a.mid} & {b.mid} overlap (shared player)")
                elif not (a.start >= b.start + s2s or b.start >= a.start + s2s):
                    issues.append(f"REST: {a.mid} & {b.mid} share a player, <{cfg.min_start_to_start_minutes}min start-to-start")
    return issues
