"""Pre-flight decision-support reports (read-only). No engine coupling.

B3 — multi-division players. Spotting players entered across divisions so their
slots can be staggered under the rest rule is the TD's most labor-intensive
manual step (copilot brief O12); this surfaces them automatically:

  roster_multi_division(events)      pre-generation  -> entered in >=2 divisions
  schedule_multi_match_days(result)  post-generation -> >=2 matches on one day

B1 — match-volume forecast, and B2 — capacity feasibility. Answer "how many
matches is this field?" and "does it fit these courts?" before generating,
rather than reading it off failures after:

  match_volume(events)               per-division + total played matches
  capacity_feasibility(cfg)          volume vs aggregate court-time (necessary
                                     condition, not the full scheduler)

Human identity is the canonical "First Last" name string, matching the engine
(Team.members / Match.humans) — the same key the rest rule, caps, and conflict
checks key on. Every function returns plain data; the *_text helpers render a
summary. Nothing in the engine imports this module; it only reads its outputs.
"""
import os
from collections import defaultdict


# ---- B3a - roster-level (pre-generation) ------------------------------------
def roster_multi_division(events, min_divisions=2):
    """Players entered in >= min_divisions divisions.

    events: list[EventSpec] (from serve_tennis_intake.load_export or hand-built).
            Each event has .name and .teams; each team has .members (names).
    Returns list[dict] sorted by division-count desc, then player name:
        {"player": name, "divisions": [event names, sorted], "n": int}
    """
    by_player = defaultdict(set)
    for ev in events:
        for t in ev.teams:
            for name in t.members:
                by_player[name].add(ev.name)
    out = [
        {"player": p, "divisions": sorted(divs), "n": len(divs)}
        for p, divs in by_player.items()
        if len(divs) >= min_divisions
    ]
    out.sort(key=lambda r: (-r["n"], r["player"]))
    return out


# ---- B3b - schedule-level (post-generation) ---------------------------------
def schedule_multi_match_days(result, min_matches=2):
    """Players with >= min_matches placed matches on the same day.

    result: the dict returned by scheduler_multi.schedule_multi /
            scheduler_flow.finalize_multi. Reads result["schedule"] only.
    Returns list[dict] sorted by player, then day:
        {"player", "day", "n", "cross_division": bool,
         "matches": [{event, match, start, court, location?}, ... by start]}
    Byes carry no start time and never appear here.
    """
    per = defaultdict(list)  # (player, day) -> [entry, ...]
    for e in result.get("schedule", []):
        for p in e.get("players", []):
            per[(p, e.get("day"))].append(e)
    out = []
    for (p, day), entries in per.items():
        if len(entries) < min_matches:
            continue
        ordered = sorted(entries, key=lambda x: (x.get("start") or "", x.get("court") or 0))
        matches = []
        for x in ordered:
            row = {"event": x.get("event"), "match": x.get("match"),
                   "start": x.get("start"), "court": x.get("court")}
            if "location" in x:
                row["location"] = x["location"]
            matches.append(row)
        out.append({
            "player": p, "day": day, "n": len(entries),
            "cross_division": len({x.get("event") for x in entries}) > 1,
            "matches": matches,
        })
    out.sort(key=lambda r: (r["player"], str(r["day"])))
    return out


# ---- B1 - match-volume forecast (pre-generation) ----------------------------
def _division_matches(ev):
    """Played matches for one division (byes are walkovers, not counted).
    round_robin -> C(n,2); single_elim -> n-1. Other formats (e.g. compass)
    are not forecastable by simple arithmetic -> None."""
    n = len(ev.teams)
    if n < 2:
        return 0
    if ev.fmt == "round_robin":
        return n * (n - 1) // 2
    if ev.fmt == "single_elim":
        return n - 1
    return None


def match_volume(events):
    """Expected played-match counts (pre-generation).

    Returns:
        {"divisions": [{division, teams, fmt, matches|None}, ...],
         "total": int,                       # sum over forecastable divisions
         "unforecastable": [division names]} # non-RR/elim formats
    """
    divisions, total, unforecastable = [], 0, []
    for ev in events:
        m = _division_matches(ev)
        divisions.append({"division": ev.name, "teams": len(ev.teams),
                          "fmt": ev.fmt, "matches": m})
        if m is None:
            unforecastable.append(ev.name)
        else:
            total += m
    divisions.sort(key=lambda d: (-(d["matches"] or 0), d["division"]))
    return {"divisions": divisions, "total": total, "unforecastable": unforecastable}


# ---- B2 - capacity feasibility (pre-generation) -----------------------------
def _hhmm_to_min(s):
    h, m = str(s).split(":")
    return int(h) * 60 + int(m)


def capacity_feasibility(cfg, block_minutes=90):
    """Does the field fit the courts? A necessary-condition court-time check.

    Mirrors the engine's usable window (daily hours minus end-of-day buffer,
    scheduler_multi._slots) and packs back-to-back `block_minutes` matches per
    court. NOT the scheduler: ignores rest gaps, one-round-per-day, and
    per-location hours, so `feasible=True` means "enough court-time in
    principle", while `feasible=False` is a hard "cannot fit".

    cfg: a MultiConfig (reads dates, num_courts, courts_by_day, daily_start,
         daily_end, end_of_day_buffer_minutes, events).
    """
    vol = match_volume(cfg.events)["total"]
    usable = _hhmm_to_min(cfg.daily_end) - _hhmm_to_min(cfg.daily_start) \
        - cfg.end_of_day_buffer_minutes
    slots_per_court = max(0, usable // block_minutes)
    per_day = []
    for d in cfg.dates:
        courts = cfg.courts_by_day.get(d, cfg.num_courts)
        per_day.append({"date": d, "courts": courts,
                        "capacity": courts * slots_per_court})
    total_cap = sum(p["capacity"] for p in per_day)
    return {
        "volume": vol,
        "capacity": total_cap,
        "headroom": total_cap - vol,
        "utilization": round(vol / total_cap, 3) if total_cap else None,
        "feasible": vol <= total_cap,
        "slots_per_court_per_day": slots_per_court,
        "block_minutes": block_minutes,
        "per_day": per_day,
        "note": ("Aggregate court-time check (necessary, not sufficient): uniform "
                 f"{block_minutes}-min block, tournament-wide hours; ignores rest "
                 "gaps, one-round-per-day, and per-location hours."),
    }


# ---- AVOID-1/2 first-round avoidance (pre-generation) -----------------------
def avoidance_flags(draws=None, players=None, levels=None):
    """AVOID-1/2 first-round avoidance flags, surfaced here so the report has a consumer.

    FIX-1 item 3 (2026-07-30, Operator-ruled destination): `avoidance.py` computed a correct
    report that nothing ever called — no reference in `wwtc_pipeline`, `preflight` or `verify`,
    so DISC-2's "flag-only" ruling delivered neither a flag nor a call. This is the call.
    Pre-flight is the right home: both are read-only pre-generation decision support, and the
    TD routes an avoidance finding to the USTA desk before the draw is locked, not after.

    Still flag-only: nothing here influences placement, and nothing blocks. Draws are final
    (D1), so the tool reports pairings it would not choose — it never re-pairs them.

    Returns the finding list from `avoidance.first_round_avoidance` unchanged (division, the
    two opponents, rule, reason), or `None` when the real artifacts are unavailable — an
    ingest-dependent report must not turn a pre-flight run into a crash.
    """
    try:
        import avoidance
    except ImportError:
        return None
    kwargs = {"draws": draws, "players": players}
    if levels is not None:
        kwargs["levels"] = levels
    try:
        return avoidance.first_round_avoidance(**kwargs)
    except (FileNotFoundError, OSError, ValueError):
        return None


def avoidance_flags_text(findings):
    """Render the avoidance flags for the pre-flight report."""
    if findings is None:
        return ("First-round avoidance: not checked (the draws/player-list artifacts were not "
                "available to this run).")
    import avoidance
    return avoidance.report_text(findings)


# ---- CONS-1 (A7b) materials check (pre-generation, read-only) ----------------
MATERIALS_SCHEMA = "td-materials/v0-internal"


def _materials_roots():
    """The dirs the product resolvers search — the committed data dir plus the two ephemeral
    upload dirs. Read from `draws_pdf` rather than restated, so this check can never look
    somewhere the run does not."""
    import draws_pdf
    return tuple(draws_pdf._ROOTS)


def _scan_draws_candidates(level):
    """Every PDF actually present that PARSES like a draws file, whatever it is called.

    Resolution is NAME-bound: draws need `Raw_Draws` plus an `L1`/`L2` token in the FILENAME
    (draws_pdf.py:131). So a perfectly good export saved under the wrong name reports as
    absent, and the director is told a file he is looking at is missing. This scan is what
    turns that into a NAMED candidate he can confirm.
    """
    import draws_pdf
    import glob as _glob
    import os as _os
    out = []
    for root in _materials_roots():
        for path in sorted(_glob.glob(_os.path.join(root, "**", "*.pdf"), recursive=True)):
            base = _os.path.basename(path).lower()
            if "raw_draws" in base and f"l{level}" in base:
                continue                      # this one the resolver would already have found
            try:
                names = [d.event for d in draws_pdf.parse_draws(path)]
            except Exception:
                continue                      # not a readable PDF; not a candidate
            real = [n for n in names if not n.startswith("__page")]
            if real:
                out.append({"path": path, "divisions": len(real), "sample": real[:3]})
    return out


def _check_draws(level):
    """One raw-draws PDF: ok / missing / unreadable / no-text."""
    import draws_pdf
    rec = {"kind": "draws", "level": level, "status": None, "path": None,
           "divisions": 0, "detail": "", "candidates": []}
    try:
        path = draws_pdf.resolve_draws_pdf(level=level)
    except FileNotFoundError:
        rec["status"] = "missing"
        rec["detail"] = (f"No Level-{level} draws file found. It needs 'Raw_Draws' and 'L{level}' "
                         f"in the file name.")
        rec["candidates"] = _scan_draws_candidates(level)
        return rec
    rec["path"] = path
    try:
        names = [d.event for d in draws_pdf.parse_draws(path)]
    except Exception as ex:                   # PdfiumError and friends: the file will not open
        rec["status"] = "unreadable"
        rec["detail"] = f"{type(ex).__name__}: {ex}"
        rec["candidates"] = _scan_draws_candidates(level)
        return rec
    # VALIDATE THE OUTPUT, NOT THE FACT THAT THE CALL RETURNED. A scan or photo PDF has no text
    # layer: `_page_texts` returns [''], `_event_of` returns None, and every page becomes a
    # `__page{i}` pseudo-division (draws_pdf.py:454) — parse_draws raises nothing at all. The
    # pseudo-names are counted here and NEVER repeated into the report.
    real = [n for n in names if not n.startswith("__page")]
    if not real:
        rec["status"] = "no-text"
        rec["detail"] = (f"The file opens but carries no text — {len(names)} page(s) and no "
                         f"division names. This is a picture of the draws, not a printed PDF.")
        return rec
    rec["status"] = "ok"
    rec["divisions"] = len(real)
    rec["detail"] = f"{len(real)} divisions"
    return rec


def _check_player_lists(levels):
    """The TD + ST list for each level: ok / missing / unreadable.

    THE SPLIT THAT MATTERS: `wwtc_ingest._classify` reads each candidate behind a bare `except`
    and returns `(None, None)` on failure, so a CORRUPT list is skipped exactly like an absent
    one and the resolver reports both as "missing". A director told a file is missing goes
    looking for it; a director told it will not open goes and re-exports it. Those are different
    days, so the two are separated here.
    """
    import glob as _glob
    import os as _os
    import re as _re
    import wwtc_ingest
    found, broken = {}, []
    for root in _materials_roots():
        # DESK-1 (run report D3, 2026-08-09): `.csv` joins the scan, the second of the two glob
        # sets the ingest keeps (`wwtc_ingest.resolve_player_lists` holds the other). Without it
        # `materials_check` reports a perfectly good CSV player list as "missing" with an empty
        # candidate list — the exact absence the check exists to turn into a named file.
        for pat in ("*.xlsx", "*.numbers", "*.csv"):
            for path in sorted(_glob.glob(_os.path.join(root, "**", pat), recursive=True)):
                try:
                    header, rows = wwtc_ingest.read_table(path)
                except ImportError as ex:
                    # NOT A FILE PROBLEM. A missing reader library says nothing about the
                    # director's spreadsheet, and telling him a good file "will not open" sends
                    # him off to re-export it. Named as what it is, so the fix lands on the
                    # right thing.
                    broken.append({"path": path, "tooling": True,
                                   "detail": f"{type(ex).__name__}: {ex}"})
                    continue
                except Exception as ex:
                    broken.append({"path": path, "detail": f"{type(ex).__name__}: {ex}"})
                    continue
                hset = set(header)
                kind = "st" if "Section" in hset else ("td" if "Draw status" in hset else None)
                if not kind:
                    continue
                m = (_re.search(r"\bL(\d)\b", _os.path.basename(path))
                     or _re.search(r"_L(\d)_", _os.path.basename(path)))
                lvl = m.group(1) if m else None
                found.setdefault((kind, lvl), {"path": path, "players": len(rows)})
    out = []
    for level in levels:
        for kind in ("td", "st"):
            hit = found.get((kind, str(level))) or found.get((kind, None))
            rec = {"kind": kind, "level": str(level), "status": "ok" if hit else "missing",
                   "path": hit["path"] if hit else None,
                   "players": hit["players"] if hit else 0, "detail": "", "candidates": []}
            if hit:
                rec["detail"] = f"{hit['players']} players"
            else:
                # an override pointed at a file, or a file is sitting there that will not open
                rec["detail"] = (f"No Level-{level} {kind.upper()} player list found. It needs an "
                                 f"'L{level}' token in the file name.")
                rec["candidates"] = list(broken)
                if broken:
                    rec["status"] = "unreadable"
                    tooling = [b for b in broken if b.get("tooling")]
                    rec["detail"] = (
                        f"This machine cannot read spreadsheets at all: {tooling[0]['detail']}"
                        if tooling else
                        f"A player list is present but will not open: {broken[0]['detail']}")
            out.append(rec)
    return out


def materials_check(levels=(1, 2)):
    """CONS-1 §3.7 / Operator ruling 8.2 — do the director's files actually read, BEFORE the
    Setup console is published?

    Today nothing looks: Step 0 checks module imports only, and the first read of the draws is
    Step 2, the first read of the player lists Step 4. So a bad file is discovered several steps
    into a run, in engineer language, at the point it blocks something.

    Reports one status per file — **ok** (with counts), **missing** (plus a content-scan naming
    any file actually present that parses like draws, so a MISNAMED file surfaces as a named
    candidate rather than an absence), **unreadable** (it will not open), or **no-text** (it
    opens and carries no text layer — the silent failure, made loud).

    THIS NEVER GATES AND NEVER RAISES. It returns a report for every state of the materials,
    including a completely empty directory. Whatever cannot be repaired in session falls back to
    the console's free-text lane and the run proceeds — blocking a tournament at Step 1 over two
    optional questions was 8.2's rejected option 2, and a check that "reports and repairs" drifts
    into a refusal one edit at a time unless the rule is written down where it is enforced.

    Read-only and deterministic: it resolves and parses, and writes nothing.
    """
    draws = [_check_draws(int(lv)) for lv in levels]
    lists = _check_player_lists(levels)
    problems = [f for f in draws + lists if f["status"] != "ok"]
    return {"schema": MATERIALS_SCHEMA,
            "draws": draws,
            "player_lists": lists,
            "ok": not problems,
            "problems": [{"kind": f["kind"], "level": f["level"], "status": f["status"],
                          "detail": f["detail"]} for f in problems]}


def materials_check_text(rep):
    """The check in the director's language — counts first, then anything that needs him.

    The runbook reads this back before Step 1 and troubleshoots from it; it never quotes a raw
    error first. `detail` carries the engineer-facing cause for the session's own use.
    """
    lines = []
    draws_ok = [d for d in rep["draws"] if d["status"] == "ok"]
    if draws_ok:
        per = " and ".join(f"{d['divisions']} at Level {d['level']}" for d in draws_ok)
        lines.append(f"Draws read: {sum(d['divisions'] for d in draws_ok)} divisions — {per}.")
    lists_ok = [f for f in rep["player_lists"] if f["status"] == "ok"]
    if lists_ok:
        lines.append(f"Player lists read: {len(lists_ok)} of {len(rep['player_lists'])}, "
                     f"{sum(f['players'] for f in lists_ok)} players in total.")
    trouble = {
        "missing": "not found",
        "unreadable": "will not open",
        "no-text": "opens but has no text in it — this is a picture of the draws, not a printout",
    }
    for f in rep["draws"] + rep["player_lists"]:
        if f["status"] == "ok":
            continue
        what = (f"Level-{f['level']} draws" if f["kind"] == "draws"
                else f"Level-{f['level']} {f['kind'].upper()} player list")
        lines.append(f"{what}: {trouble.get(f['status'], f['status'])}.")
        for c in f.get("candidates", [])[:3]:
            if "divisions" in c:
                lines.append(f"    There is a file here that looks like draws: "
                             f"{os.path.basename(c['path'])} ({c['divisions']} divisions). "
                             f"Is that the one?")
            elif c.get("tooling"):
                lines.append(f"    (This is the tool's own problem, not your file: "
                             f"{c['detail']}.)")
            else:
                lines.append(f"    {os.path.basename(c['path'])} is here but will not open.")
    if rep["ok"]:
        lines.append("Everything needed is here. Ready to start.")
    else:
        lines.append("Anything not sorted out here is not a blocker — the run carries on and "
                     "you type those names in instead.")
    return "\n".join(lines)


# ---- text rendering ---------------------------------------------------------
def roster_multi_division_text(rows):
    if not rows:
        return "No players entered in more than one division."
    lines = [f"Multi-division players ({len(rows)}):"]
    for r in rows:
        lines.append(f"  {r['player']}  x{r['n']}  -  {', '.join(r['divisions'])}")
    return "\n".join(lines)


def schedule_multi_match_days_text(rows):
    if not rows:
        return "No player has more than one match on any single day."
    lines = [f"Multi-match days ({len(rows)}):"]
    for r in rows:
        tag = "cross-division" if r["cross_division"] else "same-division"
        lines.append(f"  {r['player']}  {r['day']}  x{r['n']} ({tag}):")
        for m in r["matches"]:
            loc = f" @{m['location']}" if m.get("location") else ""
            lines.append(f"      {m['start']}  court {m['court']}{loc}  {m['match']}")
    return "\n".join(lines)


def match_volume_text(v):
    lines = [f"Match-volume forecast: {v['total']} played matches across "
             f"{len(v['divisions'])} divisions"]
    for d in v["divisions"]:
        m = "?" if d["matches"] is None else d["matches"]
        lines.append(f"  {m:>4}  {d['fmt']:<12} {d['teams']:>3} teams  {d['division']}")
    if v["unforecastable"]:
        lines.append(f"  (not forecastable: {', '.join(v['unforecastable'])})")
    return "\n".join(lines)


def capacity_feasibility_text(c):
    head = "FITS" if c["feasible"] else "DOES NOT FIT"
    util = f"{c['utilization']*100:.0f}%" if c["utilization"] is not None else "n/a"
    lines = [f"Capacity: {head} - {c['volume']} matches vs {c['capacity']} court-slots "
             f"({util} utilization, headroom {c['headroom']}); "
             f"{c['slots_per_court_per_day']} slots/court/day @ {c['block_minutes']}min"]
    for p in c["per_day"]:
        lines.append(f"  {p['date']}  {p['courts']} courts  -> {p['capacity']} slots")
    lines.append(f"  {c['note']}")
    return "\n".join(lines)


# ---- self-test + demo -------------------------------------------------------
def _selftest():
    from scheduler_multi import EventSpec, Team

    def ev(name, *rosters):
        return EventSpec(name=name, fmt="round_robin",
                         teams=[Team(tid=str(i), members=list(m)) for i, m in enumerate(rosters)])

    # sample data names only (per repo rule)
    events = [
        ev("Men's 65 Singles", ["Al Ace"], ["Bo Bell"], ["Cy Cole"]),
        ev("Men's 65 Doubles", ["Al Ace", "Bo Bell"], ["Cy Cole", "De Dunn"]),
        ev("Men's 70 Singles", ["Al Ace"], ["Ed East"]),
    ]
    roster = roster_multi_division(events)
    assert {r["player"]: r["n"] for r in roster} == {"Al Ace": 3, "Bo Bell": 2, "Cy Cole": 2}
    assert roster[0]["player"] == "Al Ace"
    assert roster[0]["divisions"] == ["Men's 65 Doubles", "Men's 65 Singles", "Men's 70 Singles"]

    result = {"schedule": [
        {"event": "Men's 65 Singles", "match": "S R1", "day": "Sat",
         "start": "08:00", "court": 1, "players": ["Al Ace", "Bo Bell"]},
        {"event": "Men's 70 Singles", "match": "S R1", "day": "Sat",
         "start": "12:30", "court": 3, "players": ["Al Ace", "Ed East"]},
        {"event": "Men's 65 Doubles", "match": "D R1", "day": "Sun",
         "start": "09:30", "court": 2, "players": ["Al Ace", "Bo Bell", "Cy Cole", "De Dunn"]},
    ]}
    days = schedule_multi_match_days(result)
    al = [r for r in days if r["player"] == "Al Ace"]
    assert len(al) == 1 and al[0]["day"] == "Sat" and al[0]["n"] == 2 and al[0]["cross_division"]
    assert al[0]["matches"][0]["start"] == "08:00"          # ordered by start
    assert not any(r["player"] == "Bo Bell" for r in days)  # one match each on 2 days -> excluded

    # B1 - match volume: RR(3)=3, single_elim(4)=3, single_elim(5)=4 -> 10.
    def sev(name, fmt, n):
        return EventSpec(name=name, fmt=fmt,
                         teams=[Team(tid=str(i), members=[f"P{i}"]) for i in range(n)])
    vevents = [sev("RR3", "round_robin", 3), sev("SE4", "single_elim", 4),
               sev("SE5", "single_elim", 5), sev("Comp", "compass", 8)]
    vol = match_volume(vevents)
    assert vol["total"] == 10, vol
    assert vol["unforecastable"] == ["Comp"]
    assert {d["division"]: d["matches"] for d in vol["divisions"]} == {
        "RR3": 3, "SE4": 3, "SE5": 4, "Comp": None}

    # B2 - capacity: 08:00-18:00 - 45 buffer = 555 min -> 555//90 = 6 slots/court/day.
    from scheduler_multi import MultiConfig
    fits = capacity_feasibility(MultiConfig(tournament_name="cap", num_courts=2,
                                            dates=["2026-01-01"], events=vevents[:3]))
    assert fits["slots_per_court_per_day"] == 6 and fits["capacity"] == 12
    assert fits["volume"] == 10 and fits["feasible"] and fits["headroom"] == 2
    tight = capacity_feasibility(MultiConfig(tournament_name="cap", num_courts=1,
                                             dates=["2026-01-01"], events=vevents[:3]))
    assert tight["capacity"] == 6 and not tight["feasible"] and tight["headroom"] == -4

    print("preflight self-test OK")
    print(roster_multi_division_text(roster))
    print(schedule_multi_match_days_text(days))
    print(match_volume_text(vol))
    print(capacity_feasibility_text(fits))


if __name__ == "__main__":
    import sys
    _selftest()
    if len(sys.argv) > 1:
        from serve_tennis_intake import load_export
        events, _seeds, warns = load_export(sys.argv[1])
        print()
        print(roster_multi_division_text(roster_multi_division(events)))
        for w in warns:
            print("  -", w)
