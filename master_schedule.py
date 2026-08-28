"""master_schedule.py — R7 Pass 1: the TD's MASTER SCHEDULE generator (read-only planning layer).

Turns the finalized draws into a per-(division, round) -> DAY assignment following the TD's own
method (interview 2026-07-23, reference/wwtc/schedulingrules_TDinterview_July23.xml):

  M1  one round per division per day
  M2  finals-anchored: place each division's FINAL, then work backward by round to the start day
  M3  older divisions first (their finals land earlier; younger later)
  M4  spread the finals: <= cap_singles singles finals AND cap_doubles doubles finals per day
  M5  within a day: singles -> mixed -> doubles; try a division's MIXED final one day before its
      singles/doubles finals
  M6  finals never before 9:00 AM  (a Pass-2 time rule; recorded here, enforced in the daily chart)
  M7  the first round is its own day (falls out of one-round-per-day)

This is a **planning artifact** — no engine coupling, deterministic. It produces the day grid that
R7-2 will feed the engine as an assigned-day constraint. The finals-day layout it computes is a
rule-based FIRST DRAFT (O2): the TD confirms/adjusts it against his real master chart.

RR divisions: a group of m teams plays (m-1 | m) rounds (one per day), its last round == its "final".
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Optional

# --- event attribute parsing (shared idiom with serve_tennis_intake._age) ---

def _age(name: str) -> int:
    m = re.search(r"(\d+)\s*&\s*over", name.lower()) or re.search(r"\b(\d{2})\b", name)
    return int(m.group(1)) if m else 0


def _etype(name: str) -> str:
    low = name.lower()
    if "mixed" in low:
        return "mixed"
    if "doubles" in low:
        return "doubles"
    return "singles"


# singles first, then mixed (Gold Ball), then gender doubles — M5 within-day order
_TYPE_ORDER = {"singles": 0, "mixed": 1, "doubles": 2}
# finals cap bucket: mixed counts under the doubles cap (both are doubles play)
_CAP_BUCKET = {"singles": "singles", "mixed": "doubles", "doubles": "doubles"}


def _rr_rounds(max_group: int) -> int:
    """Round-robin rounds for the largest group: m-1 if m even else m (one match/team/round)."""
    if max_group < 2:
        return 1
    return max_group - 1 if max_group % 2 == 0 else max_group


@dataclass
class Division:
    event: str
    fmt: str                 # "single_elim" | "round_robin"
    draw_size: int
    rounds: int
    age: int
    etype: str               # "singles" | "mixed" | "doubles"


def divisions_from_draws(draws) -> list:
    """Build Division records from draws_pdf.parse_draws output."""
    out = []
    for d in draws:
        if d.fmt == "single_elim" and d.draw_size > 0:
            rounds = int(math.log2(d.draw_size))
        elif d.fmt == "round_robin":
            rounds = _rr_rounds(max((len(g.members) for g in d.groups), default=0))
        else:
            rounds = 1
        out.append(Division(event=d.event, fmt=d.fmt, draw_size=d.draw_size,
                            rounds=rounds, age=_age(d.event), etype=_etype(d.event)))
    return out


def _round_label(r: int, total: int) -> str:
    """1-indexed round r of `total` -> TD-facing label."""
    from_end = total - r
    return {0: "Final", 1: "Semifinal", 2: "Quarterfinal"}.get(from_end, f"Round {r}")


@dataclass
class MasterSchedule:
    dates: list
    finals_day: dict = field(default_factory=dict)     # event -> date (finals)
    round_day: dict = field(default_factory=dict)      # event -> {round_label: date}
    warnings: list = field(default_factory=list)


def build_master_schedule(divisions, dates, cap_singles=6, cap_doubles=6,
                          finals_map=None, finals_anchors=None,
                          same_day_finish=None) -> MasterSchedule:
    """Assign each division's rounds to days under M1-M5/M7.

    finals_map (optional, O2): event -> date to pin finals exactly (the TD's real assignment).
    When absent, finals days are COMPUTED: older divisions first, earliest feasible finals day with
    cap room, so older finish earlier and younger later (M3), finals spread under the cap (M4).
    Rounds then cascade backward one-per-day (M1/M2), first round its own day (M7).

    finals_anchors (optional, ASSIGN-1): event -> the DESK-DERIVED finals day — the day the desk
    published the final, or the one derived from that division's own desk-stamped semifinal
    (+1 day). Same authority class as a `finals_map` pin — TD-derived, placed exactly, and NOT
    filtered by M4's cap (ruling 30) — but lower precedence: an explicit pin wins. M4 still
    governs the computed backfill; see Pass C for why anchors sit outside its load count.

    same_day_finish (optional, ENG-1 / D-41): the division names the TD has flipped the same-day
    finish on. NEVER automatic and never inferred — his words are *"these players requested to be
    done the same day so they could leave earlier"*, so the switch is a request he relays, not a
    property the tool detects. For a named division the FINAL shares its penultimate round's day
    instead of taking the next one; every earlier round still cascades one per day. This is where
    the switch has to live: M1 (one round per division per day) is a DAY-MAP rule, and the R7-2
    gate pins each round to its own assigned day, so attempting it at placement alone produces a
    spill rather than a same-day finish. `scheduler_multi` owns the other half — the 150-minute
    gap and its named exception to the rest floor (ruling 72).
    """
    ms = MasterSchedule(dates=list(dates))
    n = len(dates)
    # OI-43 (adopted by VENUE-1, 2026-08-05) — REFUSE AN IMPOSSIBLE WINDOW, don't `IndexError`.
    # A division needs one day per round (M1: one round per division per day), so a window with
    # fewer days than the deepest division has rounds cannot be laid out at all. Pre-VENUE-1 that
    # ran on regardless and died several steps later on `dates[fday]` at the saturation fallback
    # below, with `IndexError: list index out of range` and no clue which division caused it.
    # Measured on the real 2026 field (50 divisions, deepest needs 7 rounds): clean at a 7-day
    # window, `IndexError` at 6 and below.
    # This is the ENGINE half of Decision 1. The console stops the director at the moment of the
    # edit, but a slate hand-edited or couriered from anywhere else still arrives here, and
    # without this guard it still reaches the old crash.
    if n and divisions:
        too_deep = [d for d in divisions if d.rounds > n]
        if too_deep:
            worst = max(too_deep, key=lambda d: (d.rounds, d.event))
            raise ValueError(
                f"the tournament window is {n} day{'' if n == 1 else 's'} "
                f"({dates[0]} to {dates[-1]}), but {worst.event} needs {worst.rounds} rounds and "
                f"a division plays at most one round a day — so it cannot finish. "
                f"{len(too_deep)} division{' does' if len(too_deep) == 1 else 's do'} not fit. "
                f"Open a venue on more days, or run fewer rounds.")
    # The tournament builds to the last weekend: finals are anchored to the END and filled backward,
    # so the youngest/marquee divisions final on the last day and OLDER divisions finish EARLIER
    # (M3). Assignment order is therefore youngest-first (claims the latest finals days first);
    # within an age, singles -> mixed -> doubles (M5); name for determinism.
    order = sorted(divisions, key=lambda d: (d.age, _TYPE_ORDER.get(d.etype, 9), d.event))
    finals_load = {d: {"singles": 0, "doubles": 0} for d in range(n)}
    # Spread, don't cap-pack: aim for a soft per-day target so finals fan across ~SPREAD_DAYS at the
    # back of the window (the TD runs ~2-4 finals/type/day over the second half, not a jammed 6+6).
    # The hard cap (M4) is still the ceiling if the soft target can't absorb everything.
    from collections import Counter
    fcount = Counter(_CAP_BUCKET[d.etype] for d in divisions)
    SPREAD_DAYS = min(n, 8)
    soft = {b: min(cap_singles if b == "singles" else cap_doubles,
                   max(1, math.ceil(fcount[b] / SPREAD_DAYS))) for b in ("singles", "doubles")}

    def _pick_finals_day(bucket, need):
        cap = cap_singles if bucket == "singles" else cap_doubles
        lo = need - 1                                          # rounds must fit before the final
        for tgt in (soft[bucket], cap):                       # try the soft target, then the hard cap
            for d in range(n - 1, lo - 1, -1):                # latest first (build to the last day)
                if finals_load[d][bucket] < tgt:
                    return d
        return None

    def _lookup(src, div):
        return dates.index(src[div.event]) if (
            src and div.event in src and src[div.event] in dates) else None

    def _pinned_day(div):
        """The TD's pinned finals day for this division (O2), or None to compute it."""
        return _lookup(finals_map, div)

    def _anchor_day(div):
        """ASSIGN-1's desk-derived finals day (finals_anchors), or None. Ranked BELOW a console
        pin: where a division carries both, the TD's explicit drag wins."""
        return _lookup(finals_anchors, div)

    same_day = {str(e) for e in (same_day_finish or ())}

    def _lay_out(div, fday):
        """Record one division's finals day and cascade its rounds backward one per day (M1/M2).

        ENG-1 / D-41: a division the TD has named for a same-day finish collapses its LAST TWO
        rounds onto one day — the final joins its penultimate round's day — so the cascade spans
        one fewer day and the earlier rounds shift a day later, not earlier. A one-round division
        has nothing to join and is left alone."""
        need = div.rounds
        joined = div.event in same_day and need >= 2
        span = need - 1 if joined else need        # distinct DAYS this division occupies
        start = fday - (span - 1)
        if start < 0:
            ms.warnings.append(
                f"{div.event}: {need} rounds do not fit before finals {dates[fday]} (starts pre-window)")
            start = 0
        ms.finals_day[div.event] = dates[fday]
        ms.round_day[div.event] = {
            _round_label(r, need): dates[min(start + min(r - 1, span - 1), n - 1)]
            for r in range(1, need + 1)}
        if joined:
            ms.warnings.append(
                f"{div.event}: SAME-DAY FINISH is on — the final shares "
                f"{ms.round_day[div.event][_round_label(need, need)]} with its previous round, at "
                f"the TD's configured gap. The players asked to finish the same day (D-41)")

    # Pass A: pinned finals are the TD's ground truth and never move — count their load FIRST so the
    # computed backfill (Pass B) sees it and routes around already-filled days (M4 pin-aware). When
    # finals_map is absent this is a no-op, so the computed-only output stays byte-identical.
    for div in order:
        pd = _pinned_day(div)
        if pd is not None:
            finals_load[pd][_CAP_BUCKET[div.etype]] += 1

    # Pass B: place every division. Pinned use their fixed day; computed pick via _pick_finals_day,
    # which (by its finals_load < tgt guard) refuses any day already at/over cap — so a computed
    # final never lands on a pinned-full day and never pushes a day past the cap.
    for div in order:
        need = div.rounds
        fday = _pinned_day(div)
        if fday is None:
            bucket = _CAP_BUCKET[div.etype]
            fday = _pick_finals_day(bucket, need)
            if fday is None:
                fday = max(need - 1, 0)
                ms.warnings.append(f"{div.event}: finals cap saturated; forced to {dates[fday]}")
            finals_load[fday][bucket] += 1
        _lay_out(div, fday)

    # Pass C (ASSIGN-1, rulings 30 + 31): an anchored final REPLACES the computed one for its own
    # division. It runs AFTER Pass B, and that ordering is the whole design:
    #   * it bypasses `_pick_finals_day` instead of being filtered by it, so M4's cap YIELDS to the
    #     anchor (ruling 30) rather than refusing the day and dropping the final at the FRONT of the
    #     window via the saturation fallback — which would re-create the round-order inversion the
    #     anchor exists to remove (a final on or before its own semifinal);
    #   * and the computed backfill above never sees the anchors at all, so it lays out exactly as
    #     it does today. That is what makes ruling 31 true: once the desk seeds every elimination
    #     round, the only finals still computed are the round-robin divisions', and they keep
    #     today's days. Measured: letting anchors participate in the cap moves all 69 RR cells and
    #     costs spills 4 -> 6, cadence 2 -> 3, past the ruled gate.
    # M4 therefore still governs the computed backfill against itself — the constraint
    # `tests/r7_finals_map.py` asserts — and only ever yields where a desk anchor exists.
    for div in order:
        if _pinned_day(div) is not None:
            continue                                   # a console pin outranks an anchor
        ad = _anchor_day(div)
        if ad is not None:
            _lay_out(div, ad)
    return ms


def assigned_day_map(ms: MasterSchedule, divisions) -> dict:
    """R7-2 join: invert `round_day` (round-label keyed) into the engine's `(event, rnd)` key ->
    "YYYY-MM-DD". Read-only projection over an already-built MasterSchedule — no behavior change,
    deterministic. `rnd` is 1-indexed to match `scheduler_multi.Match.rnd`; the label is rebuilt with
    the same `_round_label(rnd, total)` the master used, so the round join is exact. The result is
    handed to `MultiConfig.assigned_days` (empty => engine gate inert)."""
    rounds_by = {d.event: d.rounds for d in divisions}
    out = {}
    for ev, rd in ms.round_day.items():
        total = rounds_by.get(ev)
        if not total:
            continue
        for r in range(1, total + 1):
            dt = rd.get(_round_label(r, total))
            if dt is not None:
                out[(ev, r)] = dt
    return out


def summarize_finals_by_day(ms: MasterSchedule, divisions) -> dict:
    """date -> {'singles': [...], 'doubles': [...]} finals landing that day (cap audit)."""
    by_type = {d.event: _CAP_BUCKET[d.etype] for d in divisions}
    out = {dt: {"singles": [], "doubles": []} for dt in ms.dates}
    for ev, dt in ms.finals_day.items():
        out[dt][by_type.get(ev, "doubles")].append(ev)
    return out


def render_master_chart(ms: MasterSchedule, divisions) -> str:
    """Text master chart: one row per division (older first), columns = days, cells = round label."""
    order = sorted(divisions, key=lambda d: (-d.age, _TYPE_ORDER.get(d.etype, 9), d.event))
    short = [dt[5:] for dt in ms.dates]                      # MM-DD
    w = max((len(d.event) for d in divisions), default=10)
    lines = [f"{'division':<{w}} | " + " ".join(f"{s:>5}" for s in short)]
    lines.append("-" * len(lines[0]))
    abbr = {"Final": "F", "Semifinal": "SF", "Quarterfinal": "QF"}
    for div in order:
        rd = ms.round_day.get(div.event, {})
        cell = {}
        for lbl, dt in rd.items():
            cell[dt] = abbr.get(lbl, lbl.replace("Round ", "R"))
        row = " ".join(f"{cell.get(dt,''):>5}" for dt in ms.dates)
        lines.append(f"{div.event:<{w}} | {row}")
    return "\n".join(lines)


def render_master_html(ms: MasterSchedule, divisions, title="WWTC 2026 — Master Schedule (draft)",
                       cap_singles=6, cap_doubles=6) -> str:
    """Self-contained HTML master chart (divisions x days; round-label cells). Read-only R7-4 output;
    no PII (division names + round labels only). The TD reviews and marks finals-day corrections."""
    order = sorted(divisions, key=lambda d: (-d.age, _TYPE_ORDER.get(d.etype, 9), d.event))
    fin = summarize_finals_by_day(ms, divisions)
    days = ms.dates

    def dhdr(dt):
        import datetime
        y, m, d = (int(x) for x in dt.split("-"))
        wd = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][datetime.date(y, m, d).weekday()]
        return f"{wd}<br>{m}/{d}"

    abbr = {"Final": "F", "Semifinal": "SF", "Quarterfinal": "QF"}
    css = """
    body{font:13px system-ui,Arial,sans-serif;margin:18px;color:#111}
    h1{font-size:19px;margin:0 0 2px} .sub{color:#555;margin:0 0 14px;max-width:70ch}
    table{border-collapse:collapse} th,td{border:1px solid #d0d0d0;padding:3px 6px;text-align:center}
    th.div,td.div{text-align:left;white-space:nowrap;position:sticky;left:0;background:#fafafa}
    thead th{background:#f0f0f3} .cap th{font-weight:600;background:#eef}
    td.F{background:#1d4ed8;color:#fff;font-weight:700} td.SF{background:#bfdbfe}
    td.QF{background:#dbeafe} td.R{background:#eef4ff;color:#334}
    .cap td{font-variant-numeric:tabular-nums} .over{background:#fee2e2}
    """
    rows = []
    for div in order:
        cell = {}
        for lbl, dt in ms.round_day.get(div.event, {}).items():
            cell[dt] = abbr.get(lbl, lbl.replace("Round ", "R"))
        tds = []
        for dt in days:
            v = cell.get(dt, "")
            cls = "F" if v == "F" else "SF" if v == "SF" else "QF" if v == "QF" else ("R" if v else "")
            tds.append(f'<td class="{cls}">{v}</td>')
        rows.append(f'<tr><td class="div">{div.event}</td>{"".join(tds)}</tr>')
    caps = []
    for dt in days:
        s, d = len(fin[dt]["singles"]), len(fin[dt]["doubles"])
        txt = f"{s}s/{d}d" if (s or d) else ""
        # FMAP-1: the TD's own thresholds, never a literal — a hardcoded 6 here would have the
        # master chart flagging days the TD's setting says are fine the moment FMAP-1 ships.
        caps.append(f'<td class="{"over" if (s>cap_singles or d>cap_doubles) else ""}">{txt}</td>')
    head = "".join(f"<th>{dhdr(dt)}</th>" for dt in days)
    return f"""<!doctype html><meta charset=utf-8><title>{title}</title><style>{css}</style>
    <h1>{title}</h1>
    <p class="sub">One round per division per day, finals-anchored and worked backward; older
    divisions finish first; ≤6 singles + 6 doubles finals/day; builds to the final weekend.
    Finals days are a <b>rule-based draft</b> — the TD confirms/corrects (O2). Cells: F=Final,
    SF=Semi, QF=Quarter, R#=earlier round.</p>
    <table><thead><tr><th class="div">Division ({len(order)})</th>{head}</tr></thead>
    <tbody>{"".join(rows)}
    <tr class="cap"><th class="div">Finals / day</th>{"".join(caps)}</tr></tbody></table>"""


def _selftest():
    import draws_pdf
    draws = draws_pdf.parse_draws(level="2") + draws_pdf.parse_draws(level="1")
    divs = divisions_from_draws(draws)
    dates = ["2026-01-23", "2026-01-24", "2026-01-25", "2026-01-26", "2026-01-27",
             "2026-01-28", "2026-01-29", "2026-01-30", "2026-01-31", "2026-02-01"]
    ms = build_master_schedule(divs, dates)
    print(render_master_chart(ms, divs))
    cap_s, cap_d = 6, 6          # the build_master_schedule defaults this selftest builds with
    print(f"\nFinals per day (cap audit, cap {cap_s} singles / {cap_d} doubles):")
    for dt, b in summarize_finals_by_day(ms, divs).items():
        s, d = len(b["singles"]), len(b["doubles"])
        flag = "  <-- OVER" if (s > cap_s or d > cap_d) else ""
        if s or d:
            print(f"  {dt}: singles={s} doubles={d}{flag}")
    # M1 audit: each division's rounds on distinct consecutive days
    bad = 0
    for div in divs:
        days = [dates.index(dt) for dt in ms.round_day[div.event].values()]
        if len(set(days)) != len(days):
            bad += 1
    print(f"\nM1 (one round/day, distinct days per division) violations: {bad}")
    print(f"warnings: {len(ms.warnings)}")
    for w in ms.warnings[:10]:
        print("   -", w)


if __name__ == "__main__":
    _selftest()
