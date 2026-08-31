"""td-editor-plan/v1 — the self-contained snapshot the Edit console loads (Phase 5).

Read-only projection (like verify.py / schedule_views.py — no engine coupling, nothing here
changes placement). Bundles into ONE couriered doc everything the editor needs so it can render
without ever calling the engine (B-1):

  - placements  : the engine's least-conflict schedule (day / start / location / duration /
                  players / division / round / label / fmt). Court is deferred (never emitted).
  - divisions   : per-division bracket structure (elim rounds / RR teams) for the bracket panel.
  - resources   : locations with per-day capacity (concurrent matches) + hours + the lit-court
                  ceiling — from the slate, the deferred-court capacity model (no court numbers).
  - constraints : the applied td-constraints/v1 echoed, so the editor's live advisories use the
                  TD's real rest / staging rules instead of hardcoded constants.
  - unplaced    : ids the engine could not place (empty on the 815/294/0/0 field).

The editor emits schedule-edits/v1 back; scheduler_flow.apply_schedule_edits consumes it.
"""

import re

import division_order as DO       # DIV-1: rule 44's one display order. Display only — this
                                 # module is read-only over engine output and imports nothing
                                 # from the placement path.

EDITOR_PLAN_SCHEMA = "td-editor-plan/v1"

_FMT_UI = {"round_robin": "rr"}   # engine fmt -> editor fmt; everything else is an elim tree


def _fmt_ui(fmt):
    return _FMT_UI.get(fmt, "elim")


def _is_doubles(division):
    """CARD-1: the same one-line test as `wwtc_ingest._is_doubles` and the console's
    `divIsDoubles` — "mixed" counts. Restated here rather than imported so this module keeps
    importing nothing from the ingest path; the three copies are asserted equal in
    `tests/card1_teams.py`."""
    return "doubles" in division.lower() or "mixed" in division.lower()


def _teams(item):
    """CARD-1 (additive, optional): the two sides of a doubles card as `[[side A], [side B]]`.

    Returned only when at least one side is known and the division is doubles, so a plan built
    from a run where nothing is decided is byte-identical to a pre-CARD-1 plan. A side that is
    still undecided rides as `[]` — the console renders "winner to be decided" for it, which is
    the honest answer. Singles cards never carry the key: their "sides" are single players and
    every render site already prints them correctly."""
    if not _is_doubles(item.get("event", "")):
        return None
    ta, tb = item.get("team_a") or [], item.get("team_b") or []
    if not ta and not tb:
        return None
    return [list(ta), list(tb)]


def _round_name(rnd, max_rnd):
    """Human round label for the bracket panel (Final / Semifinals / … / Round N)."""
    back = max_rnd - rnd
    return {0: "Final", 1: "Semifinals", 2: "Quarterfinals"}.get(back, f"Round {rnd}")


def _duration(item):
    """Match length in minutes from the schedule item's start/end (HH:MM)."""
    def m(hhmm):
        h, mm = hhmm.split(":")
        return int(h) * 60 + int(mm)
    if item.get("start") and item.get("end"):
        return m(item["end"]) - m(item["start"])
    return None


def _lights(cfg, loc, rec):
    """COURTS-1 (rule 48, additive + optional): the venue's lit-court ceiling, mirrored ONE-FOR-ONE
    from `MultiConfig` so the console receives what the engine holds and nothing invented.

    `lit_courts` (int) + `lights_on` ("HH:MM"), PER LOCATION because that is the only shape the
    engine can express — `venue_lit_courts` is keyed by location alone, with no per-day term
    (D2 option 1, ruled 8/17). A per-day key beside `morning_by_day` would advertise a
    flexibility the engine does not have.

    ⚠ BOTH-OR-NEITHER, matching `validate_multi` (`:1929-1932`) exactly: the mirror reads the
    hour only when a count exists, so an hour carried alone (rule 31 uses one — Level 1 Mixed
    never under lights — with no ceiling attached) must not be read as a ceiling. Emitting each
    key only where `cfg` carries it keeps the console's `litGate` and the mirror's `gate` the
    same test. Absent keys => the console behaves exactly as it did before this build,
    byte-identical; that is `td-editor-plan/v1`'s compatibility guarantee."""
    lit = cfg.venue_lit_courts.get(loc) if cfg.venue_lit_courts else None
    if lit is not None:
        rec["lit_courts"] = lit
    on = cfg.venue_lights_on.get(loc) if cfg.venue_lights_on else None
    if on:
        rec["lights_on"] = on


def _resources(cfg):
    """Per-location capacity + hours for every day, from the deferred-court capacity model.
    Capacity = the location's court count (range width) in cfg.court_locations; hours from
    cfg.location_hours with the tournament-wide fallback. No court numbers are surfaced."""
    daily_start = cfg.daily_start
    daily_end = cfg.daily_end
    # gather every (day, location, capacity) from the layout; fall back to a single pool.
    locs = {}
    for day in cfg.dates:
        layout = cfg.court_locations.get(day)
        if layout:
            for lo, hi, loc in layout:
                locs.setdefault(loc, {"id": loc, "name": loc, "capacity_by_day": {},
                                      "hours_by_day": {}, "morning_by_day": {}})
                locs[loc]["capacity_by_day"][day] = hi - lo + 1
                window = (cfg.location_hours.get(loc, {}) or {}).get(day)
                locs[loc]["hours_by_day"][day] = list(window) if window else [daily_start, daily_end]
                mc = cfg.morning_caps.get((loc, day)) if cfg.morning_caps else None
                if mc:   # R7-3 (additive): ["HH:MM" switch, morning courts] — absent = flat
                    locs[loc]["morning_by_day"][day] = [mc[0], mc[1]]
                _lights(cfg, loc, locs[loc])
        else:
            loc = "POOL"
            locs.setdefault(loc, {"id": loc, "name": "All courts", "capacity_by_day": {}, "hours_by_day": {}})
            locs[loc]["capacity_by_day"][day] = cfg.courts_by_day.get(day, cfg.num_courts)
            locs[loc]["hours_by_day"][day] = [daily_start, daily_end]
    return {
        "locations": [locs[k] for k in locs],
        "daily_start": daily_start, "daily_end": daily_end,
        "end_of_day_buffer_minutes": cfg.end_of_day_buffer_minutes,
        # DRAW-1 (OI-37 a6-ii, additive): the inter-venue transit map, mirrored ONE-FOR-ONE from
        # MultiConfig.transit_minutes (sorted "A|B" -> minutes) so the editor's read is a rename
        # and nothing more. {} = no transit rule (advisories stay blind to it, today's behaviour).
        "transit_minutes": dict(cfg.transit_minutes or {}),
    }


_RR_GROUP = re.compile(r"\s+[—-]\s*Group\s*\d+\s*$")

# BRACKET-1: the engine's own elimination id. It mints every one as `{prefix}-R{r}-M{m+1}` over
# 0-based `m` in DRAW order (`scheduler_multi.py:167`/`:191` in `_build_elim_positional`,
# `:245`/`:272` in `build_elim_teams`), so the match number IS the draw position — Match 1 is the
# top pairing of the round on every division. Round-robin ids carry no `-R` segment and never
# match, which is how ruling 71's carve-out holds without a round-robin branch.
_ELIM_ID = re.compile(r"^(.+)-R(\d+)-M(\d+)$")


def _draw_pos(match_id):
    """The draw position an elimination id names, for sorting a round into draw order.

    An id that does not parse sorts LAST and keeps its incoming order — a round is re-ordered,
    never re-shaped, so nothing may be dropped or duplicated by a sort key it does not fit."""
    g = _ELIM_ID.match(str(match_id or ""))
    return (0, int(g.group(3))) if g else (1, 0)


def _finals_day_of(division, finals_map):
    """EVAL-1 §5.2: the TD's CONFIRMED finals-map day for a division, or None.

    Round-robin divisions run as `<parent> — Group N` in the engine while a finals map is keyed by
    the parent, so the parent is the fallback — the same unwrapping `division_floors` and
    `daily_caps` already need on the console side. Resolved HERE, upstream of the browser, so the
    console reads a day and never re-derives which division a group belongs to (F11).

    This is the TD's confirmed map and NOT FMAP-2's `graded_map`, which records what a verdict
    graded rather than what he chose (EVAL-1 §8 risk 4). Absent map ⇒ None ⇒ the key is omitted."""
    if not finals_map:
        return None
    day = finals_map.get(division)
    if day is None:
        day = finals_map.get(_RR_GROUP.sub("", str(division or "")).strip())
    return day or None


def _divisions(placements, events, mixed_level_1=(), finals_map=None):
    """Bracket structure per division for the editor's bracket panel. Elim divisions get
    ordered rounds (each with its match ids); RR divisions get their team labels.

    DIV-1 (rule 44): the array comes out in the TD's ONE division order — men's singles,
    women's singles, men's doubles, women's doubles, Mixed, youngest to oldest inside each —
    not the dict-insertion order the engine happened to place matches in. Same entries, same
    fields; only the order moves, and no shipped reader asserted it (the editor's picker walks
    the array, `tests/r4_editor.py` reads by name). Measured before that build: 49 of 51 rows
    sat outside that order, the worst travelling 41 places.

    DIV-2 (2026-08-30): the Mixed clause is ONE age-ordered block, not Level 1 then Level 2.
    Re-ordered again, never re-shaped — six rows move on the 2026 field and the emitted digest
    moves with them (`tests/holdvis1_visibility.py` ZERO_EDIT_PLAN / EDITED_PLAN).
    """
    ev_fmt = {e.name: e.fmt for e in (events or [])}
    ev_teams = {e.name: [t.label() for t in e.teams] for e in (events or [])}
    by_div = {}
    for p in placements:
        by_div.setdefault(p["div"], []).append(p)
    out = []
    for div in DO.sort_divisions(by_div, mixed_level_1):
        ps = by_div[div]
        fmt = ev_fmt.get(div)
        if fmt is None:                       # infer when events not supplied
            fmt = "round_robin" if all(p["fmt"] == "rr" for p in ps) else "single_elim"
        d = {"name": div, "fmt": _fmt_ui(fmt)}
        # EVAL-1 §5.2 (additive, optional): the day the TD's finals map promised this division.
        # Omitted — never null — when there is no map or no entry, so a plan built without one is
        # byte-identical to a pre-EVAL-1 plan and the console falls back to the card's own day.
        fday = _finals_day_of(div, finals_map)
        if fday:
            d["finals_day"] = fday
        if _fmt_ui(fmt) == "rr":
            teams = ev_teams.get(div)
            if not teams:                     # derive team labels from the placed players
                seen = []
                for p in ps:
                    for who in p["players"]:
                        if who not in seen:
                            seen.append(who)
                teams = seen
            d["teams"] = teams
        else:
            rnds = sorted({p["round"] for p in ps})
            max_rnd = max(rnds) if rnds else 0
            # BRACKET-1 (decision 1 option A, Operator 8/17): each round's ids come out in DRAW
            # order — match-number order — not the placement order `result["schedule"]` happens
            # to carry. DIV-1's exact shape one level down: re-ordered, never re-shaped, same
            # ids and same fields, and measured at build against every reader of the block
            # (console `:1389` membership and `:3228` length; `console2_batch`, `eval1_preview`
            # by membership; `editvo1_viewonly` by length) — no shipped reader asserted the
            # order. Fixed HERE rather than at the render so every present and future reader of
            # `td-editor-plan/v1` gets the draw for free instead of re-sorting for itself.
            d["rounds"] = [{"round": r, "name": _round_name(r, max_rnd),
                            "ids": sorted((p["id"] for p in ps if p["round"] == r),
                                          key=_draw_pos)} for r in rnds]
        out.append(d)
    return out


def _opening_ids(placements):
    """F3 (EDITOR-V2): the ids of placements that are the OPENING match for at least one of their
    players within their division — each player's earliest scheduled match (round 1 for most,
    round 2 for a first-round bye, since a bye walkover is never in `schedule`). Mirrors
    `csv_export.first_round_rows`; NOT literal `round == 1`. Deterministic (sorted).

    Additive: the editor scopes its default surface to these so it publishes each player's opening
    match across all days rather than a single calendar day. Absent → older day-scoped behavior."""
    earliest = {}                                       # (player, division) -> ((day, start), id)
    for p in placements:
        stamp = (p.get("day") or "", p.get("start") or "")
        for who in p.get("players", []):
            key = (who, p["div"])
            cur = earliest.get(key)
            if cur is None or stamp < cur[0]:
                earliest[key] = (stamp, p["id"])
    return sorted({v[1] for v in earliest.values()})


def _seeds_by_player(seeds):
    """{event: {"A/B": n}} -> {event: {"A": n, "B": n}}.

    The ingest seeds a TEAM; the console flags a PLAYER, so each doubles pair's seed is
    carried by both of its members. Deterministic: events and names sorted."""
    out = {}
    for event, by_team in sorted((seeds or {}).items()):
        per = {}
        for label, n in sorted(by_team.items()):
            for who in str(label).split("/"):
                who = who.strip()
                if who:
                    per[who] = n
        if per:
            out[event] = dict(sorted(per.items()))
    return out


def _division_floors(events):
    """CUI-3: {division: "HH:MM"} — the engine's RESOLVED earliest-start floor per division.

    `constraints.apply_constraints` already walked the age rules onto `ev.earliest_start`
    (`constraints.py:288-295`, highest matching `age_min` wins), so this reads that result and
    never re-derives the age from the division name. The editor reads the floor; it must not own
    a second copy of the age→floor mapping (the D-32 precedent, and ruling 21's "emit it, do not
    derive it"). Divisions with no floor are simply absent; `{}` = no floors anywhere."""
    return {ev.name: ev.earliest_start
            for ev in sorted(events or [], key=lambda e: e.name)
            if getattr(ev, "earliest_start", None)}


def _players_meta(roster, constraints_doc, present):
    """CUI-3: {name: {events, rating, locality}} — the per-player card facts, display-only.

    Keyed by the same `"First Last"` form as `placements[].players`, `locals` and `seeds`, so the
    console looks a player up exactly as it already does. Absent key = no badges.

      events   : the count of divisions entered, EMITTED not derived (ruling 21). Real range on the
                 2026 field is 1–6, not the "(1/2/3)" the register recorded — never a 3-value enum.
      rating   : {"singles": float, "doubles": float} — WTN, whichever the ingest carries. Both are
                 real numbers, so the choice of WHICH to show is a render rule (the card shows the
                 one matching its own format), not a contract decision. Absent when neither exists.
      locality : "L" (home cluster) | "C" (commuter) | absent. RESOLVED HERE, upstream of the
                 browser — the console never holds a city list. Both tiers run through the SAME
                 shipped matcher, `constraints.local_players_from_locality` (city test at `:239`,
                 `_norm`-folded); a second matcher would be a build failure.
      gender   : "M" | "F" | absent — GENDER-1 (2026-08-08), the entry list's own `Gender`
                 column (`wwtc_ingest.Player.gender`), FORWARDED, never inferred. It exists so
                 the console can test a Mixed team's composition against a FACT: before this the
                 browser derived gender from the divisions a person entered, which is blind on
                 27.8% of the pairings it exists for (1,947 of 6,996 replaced x candidate pairs
                 on Mixed cards, measured 8/8) — and the 2027 mock run put two men on a Mixed
                 court with nothing on any surface saying a word.
                 ABSENT when the entry list has no value, and absent — deliberately — when two
                 roster records share a name and disagree, because a name is not unique and the
                 console keys by name. An absent key is the ruling-88 line: the tool greys the
                 row with the reason and never blocks. Measured on the committed field: 759 of
                 759 records carry a value (559 M / 200 F) and 0 names are ambiguous.

    `roster` is the pipeline's `{usta_id: Player}`. Omitted → `{}` (inert; additive)."""
    if not roster:
        return {}
    import constraints as C

    people = list(roster.values())
    meta = {p.name: {"city": getattr(p, "city", ""), "section": getattr(p, "section", ""),
                     "zip": ""} for p in people}
    locality = (constraints_doc or {}).get("locality") or {}
    # The SAME function for both tiers — only the city list differs. `home_section`/`home_zips` are
    # deliberately not passed for the commuter tier: the C badge is a city-list fact and nothing else.
    local_set = C.local_players_from_locality(meta, home_cities=locality.get("home_cities"),
                                              home_section=locality.get("home_section"),
                                              home_zips=locality.get("home_zips"))
    commuter_set = C.local_players_from_locality(meta,
                                                 home_cities=locality.get("commuter_cities"))
    # GENDER-1: name -> "M" | "F", or None where the fact is unusable. Built as its OWN pass
    # because the map below is keyed by NAME while the roster is keyed by USTA id: two records
    # sharing a name would otherwise let the last one written decide a gender for both. A
    # disagreement collapses to None — the tool never blocks on an ambiguous fact.
    sex = {}
    for p in people:
        g = (getattr(p, "gender", "") or "").strip().upper()[:1]
        g = g if g in ("M", "F") else None
        if p.name in sex and sex[p.name] != g:
            sex[p.name] = None
        else:
            sex.setdefault(p.name, g)
    out = {}
    for p in people:
        if p.name not in present:
            continue
        # DRAW-1: `usta_id` rides the card facts so a substitution can emit the OUTGOING
        # player's id (§7's `sub.out`) — the roster is keyed by USTA id and a name is not
        # unique, so the emit must carry the id, not just the name. Additive.
        rec = {"events": len(getattr(p, "events", []) or []),
               "usta_id": getattr(p, "usta_id", None)}
        # GENDER-1 (additive, optional — `td-editor-plan/v1`): the entry list's answer, not a
        # guess. Omitted (never null, never "") when there is none, so an older console is inert
        # to it and the console's own fallback — ELIG-1's inference — still runs for that person.
        if sex.get(p.name):
            rec["gender"] = sex[p.name]
        rating = {}
        if getattr(p, "wtn_singles", None) is not None:
            rating["singles"] = p.wtn_singles
        if getattr(p, "wtn_doubles", None) is not None:
            rating["doubles"] = p.wtn_doubles
        if rating:
            rec["rating"] = rating
        # The validator forbids a city in both lists, so this is never ambiguous in practice;
        # L wins if a hand-edited doc ever slips one through.
        if p.name in local_set:
            rec["locality"] = "L"
        elif p.name in commuter_set:
            rec["locality"] = "C"
        out[p.name] = rec
    return dict(sorted(out.items()))


def editor_plan(result, cfg, events=None, constraints_doc=None, local_players=None,
                non_drawn=None, master_warnings=None, seeds=None, roster=None,
                plan_id=None, finals_map=None) -> dict:
    """Project a scheduled result + its cfg (+ optional events / constraints) into a
    td-editor-plan/v1 doc. Pure projection: reads the engine's outputs, never re-derives
    placement. Court is intentionally omitted (deferred to day-of ops).

    local_players (optional): the constraints-layer local-player name set
    (`local_players_from_zips(...)`). When supplied, the projection emits `locals` — the sorted
    subset of those names that actually appear in a placement — so the editor can flag locals
    (display-only, advisory). Names match placement `players` exactly (same "First Last" form),
    so no normalization is needed. Omitted → `locals: []` (inert).

    non_drawn (optional, F6): `wwtc_ingest.non_drawn_entrants(...)` output. When supplied, the
    projection emits `non_drawn` (per-event alternate/unpaired/no-draw cards — surface + flag
    only, never placed) and `withdrawn` (the read-only withdrawn list). Omitted → both empty
    (inert; additive, pre-F6 consumers unaffected).

    master_warnings (optional, CUI-2): the Pass-1 master's advisory warnings, as returned
    alongside the build (`result["master_warnings"]` on the pipeline's dicts). Emitted with
    `spills` (read straight off `result["assigned_day_spills"]` — the R7-2 Option-A fallback
    report) so the edit console can show both in its warning bar instead of leaving them in
    the run report. Both are advisory notices ABOUT the schedule, never inputs to it; the
    spill list is whatever the run produced and varies with the pins in play, so nothing here
    treats its length as a fixed number. Omitted → both empty (additive, inert).

    cadence_conflicts (FIX-1 item 2): divisions with more than one round on a single day, read
    off `result["cadence_conflicts"]` the same way `spills` is. Each entry carries the rounds
    involved and a plain-language note; the console shows them in the warning bar. Advisory —
    a description of the schedule, never an input to it. `[]` when the schedule is clean.

    roster (optional, CUI-3): the pipeline's `{usta_id: Player}` — the roster the pipeline has
    always held and always dropped here. When supplied, the projection emits `players` (per-player
    events entered / WTN rating / resolved L|C locality; see `_players_meta`). Omitted → `{}`
    (inert). `division_floors` rides on `events` and needs no argument.

    seeds (optional, EC-F2): the ingest's per-division seed map, `{event: {team_label: n}}`
    as returned on the pipeline's `seeds` key. Team labels are slash-joined for doubles, so
    they are flattened here to `{event: {player_name: n}}` — the console flags a seeded player
    by plain name lookup, exactly as it does for locals. Display-only; seeding is the
    registration platform's decision and nothing here changes it. Omitted → `{}` (inert).

    plan_id (optional, EDITBASE-1 2026-08-08): the build this plan is a picture of, as
    `scheduler_flow._default_plan_id(cfg)` computes it. RECEIVED, never imported: this module is
    a read-only projection over engine output and imports nothing from the placement path
    (DIV-1's guard, stated at the `division_order` import above), and re-deriving the slug here
    would put a SECOND definition of an identifier whose entire job is that the two sides agree.
    It is normally not passed at all — `apply_schedule_edits` stamps `result["plan_id"]` on every
    edited result and the build lane stamps it on a base build, so the id rides the same object
    the board came from and cannot describe a different schedule than the placements do. An
    explicit argument wins over the result's own key; neither ⇒ the key is OMITTED, and a console
    generated from such a plan emits `plan_id: null`, which the engine now refuses. That is the
    intended reading: an unstamped console is one whose provenance nobody can check.

    finals_map (optional, EVAL-1 2026-08-16): the TD's CONFIRMED finals map, `{division: date}` —
    the same validated map `build_from_setup` hands the cascade (`wwtc_pipeline._finals_pins`).
    When supplied, each division carries `finals_day` (§5.2), riding for one reason only: so the
    console's hold-on-a-final message can name the day the map promised rather than describing a
    day the TD never chose. Read-only projection, additive and optional in the same lane as
    GENDER-1's key — omitted ⇒ the console is byte-identical and its message names the card's own
    delivered day instead (degraded wording, never a missing message). NOT `graded_map`: FMAP-2's
    verdict records what was graded, this records what he confirmed, and the message reads the
    confirmed map only.

    `applied_edits` rides `result` the same way (`apply_schedule_edits` writes it) and is emitted
    VERBATIM — the console seeds its own edit list from it, so a console regenerated after a
    change starts with the run's changes instead of forgetting them (run report D2). Absent on a
    base build, which is exactly the plan that has no earlier changes to carry."""
    placements = []
    for item in result.get("schedule", []):
        p = {
            "id": item["id"],
            "div": item["event"],
            "fmt": _fmt_ui("round_robin" if item.get("draw") == "rr" else "single_elim"),
            "round": item.get("round"),
            "label": item.get("match"),
            "players": item.get("players", []),
            "day": item.get("day"),
            "start": item.get("start"),
            "duration": _duration(item),
            "location": item.get("location"),   # may be None on a no-layout run
        }
        # CARD-1 (additive, optional — `td-editor-plan/v1`): who partners whom. Emitted only on
        # doubles cards with at least one side known, and omitted (not None) otherwise, so every
        # shipped reader is inert to it and an older plan still renders. The console prefers this
        # key, falling back to the label parse and then the two-names inference.
        teams = _teams(item)
        if teams is not None:
            p["teams"] = teams
        placements.append(p)
    local_set = set(local_players or ())
    present = {who for p in placements for who in p["players"]}
    locals_here = sorted(local_set & present)
    # GENDER-1 (2026-08-08): the card-facts map is widened by the SUBSTITUTE POOL, and by nothing
    # else. `present` is the board's population, and a pool candidate is by definition not on the
    # board — measured, 11 of the 53 pool people had no record at all, so a gender read off this
    # map would have been blind on exactly the people a substitution brings IN. `locals_here`
    # above keeps the unwidened `present`, deliberately: the L badge is a board fact.
    # The WITHDRAWN list is NOT added — `subCandidates` reads the pool only, so a withdrawn
    # person is never a candidate and a record for them would be emit weight nothing reads.
    named = present | {c.get("name") for cards in (non_drawn or {}).get("by_event", {}).values()
                       for c in cards if c.get("name")}
    # DIV-1 / rule 45: the RESOLVED Level-1 Mixed list, parked on the config by
    # `wwtc_pipeline._mixed_level_1`. The consoles are self-contained and surface-ignorant (F11),
    # so the editor's JS cannot re-derive which Mixed ages are Level 1 — that fact lives in the
    # TD's setup answer or in which PDF a division came from, and neither reaches the browser.
    # Without it the JS mirror would have to hardcode one year's split, which rule 45 forbids.
    mixed_l1 = list(getattr(cfg, "mixed_level_1_resolved", None) or ())
    # EDITBASE-1: both keys are OPTIONAL and both are omitted rather than emitted null when there
    # is nothing to say — DIV-1's `mixed_level_1` precedent. A reader shipped before this build
    # ignores them; a console shipped before this build ignores them too, which is the
    # old-plan/new-console and new-plan/old-console pair the acceptance names.
    pid = plan_id if plan_id is not None else result.get("plan_id")
    prior = result.get("applied_edits")
    return {
        "schema": EDITOR_PLAN_SCHEMA,
        "tournament": result.get("tournament"),
        # The build this plan is a picture of. The console echoes it into every block it emits,
        # and `apply_schedule_edits` refuses a block whose id is not this build's.
        **({"plan_id": pid} if pid else {}),
        # The changes that produced the board above, verbatim from the engine's own record. The
        # console SEEDS its emit list from these, so the next block it emits is the FULL set of
        # changes relative to the base build rather than only the newest one. This is the half
        # that kills run report D2 — refusal alone cannot, because a console regenerated from the
        # base build emits a block that is stale and looks perfectly legitimate.
        **({"applied_edits": prior} if prior else {}),
        "days": list(cfg.dates),
        "resources": _resources(cfg),
        "constraints": constraints_doc or {},
        # DRAW-1 (OI-37 a6-ii, additive): each division's per-player daily match cap, from
        # ev.max_matches_per_day — the value the engine actually enforces (ENG-1 routed
        # td-constraints `match_caps` there) — NEVER the inert `constraints` echo above, whose
        # `match_caps` block is the console's input, not the engine's resolved answer. Advisory
        # in the editor; {} when no events supplied or no division carries a cap.
        "daily_caps": {ev.name: ev.max_matches_per_day
                       for ev in sorted(events or [], key=lambda e: e.name)
                       if getattr(ev, "max_matches_per_day", None) is not None},
        "divisions": _divisions(placements, events, mixed_l1, finals_map),
        # DIV-1 (additive, optional): the resolved list the browser-side sort reads. [] means no
        # Mixed division is Level 1 this year, which is a legal answer.
        "mixed_level_1": mixed_l1,
        "placements": placements,
        "opening_ids": _opening_ids(placements),   # F3: each player's opening match (all days)
        "locals": locals_here,
        "non_drawn": (non_drawn or {}).get("by_event", {}),         # F6: per-event cards
        "withdrawn": (non_drawn or {}).get("withdrawn", []),        # F6: read-only list
        # CUI-2: advisory engine notices, surfaced in the console's warning bar.
        "spills": list(result.get("assigned_day_spills", [])),
        # FIX-1 item 2: divisions with two rounds on one day. Read off the result like `spills`,
        # so no caller changes. Separate from `spills` because a collision can exist with none of
        # them (two rounds pinned to the same day never spill). Additive; [] when clean.
        "cadence_conflicts": list(result.get("cadence_conflicts", [])),
        # ENG-1 (ruling 73): matches the engine had to place outside the TD's singles -> mixed ->
        # doubles order, and matches only the relaxed ladder could seat. Read off the result like
        # `spills`, so no caller changes; [] when clean. Without this projection the escapes reach
        # no rendered surface at all, and the console's own baked-rules box promises the TD that
        # "the exception is listed for you".
        "day_shape_exceptions": list(result.get("day_shape_exceptions", [])),
        "rule_escapes": list(result.get("rule_escapes", [])),
        "master_warnings": list(master_warnings or []),
        "seeds": _seeds_by_player(seeds),          # EC-F2: {event: {player: seed}}
        # CUI-3: per-player card facts and the resolved per-division floor. Both additive and
        # display-only; `locals`/`seeds` keep their names and shapes so no shipped reader changes.
        "players": _players_meta(roster, constraints_doc, named),
        "division_floors": _division_floors(events),
        "unplaced": [{"id": mid} for mid in result.get("unplaced", [])],
    }


def render_editor_console(plan, template_path=None) -> str:
    """CUI-1: the Edit console as a GENERATED artifact — a self-contained interactive HTML
    string preloaded with `plan`, for the run surface to write to a file and hand to the
    operator (the render_finals_console / F7-2 precedent). The operator never handles
    td-editor-plan/v1; only the emitted schedule-edits/v1 travels back (B-1: no fetch/XHR/
    file/engine at runtime; data embedded at generation).

    `schedule_editor.html` (next to this module) is the template: its single embedded
    `var SAMPLE = …;` line — the generation slot — is replaced with the supplied plan.
    Deterministic: same plan, same template -> same HTML."""
    import json
    import os
    import re

    if not isinstance(plan, dict) or plan.get("schema") != EDITOR_PLAN_SCHEMA:
        got = plan.get("schema") if isinstance(plan, dict) else type(plan).__name__
        raise ValueError(f"expected a {EDITOR_PLAN_SCHEMA} doc, got: {got}")
    path = template_path or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "schedule_editor.html")
    with open(path, encoding="utf-8") as fh:
        template = fh.read()
    # </script>-safe: keep the payload from terminating the inline script block early.
    payload = json.dumps(plan).replace("</", "<\\/")
    html, n = re.subn(r"^(\s*var SAMPLE = ).*;$",
                      lambda m: m.group(1) + payload + ";",
                      template, flags=re.MULTILINE)
    if n != 1:
        raise ValueError(f"template {os.path.basename(path)}: expected exactly one "
                         f"'var SAMPLE = …;' generation slot, found {n}")
    return html


def editor_plan_text(plan) -> str:
    r = plan["resources"]
    lines = [f"td-editor-plan/v1 — {plan.get('tournament')}",
             f"  days: {len(plan['days'])}  divisions: {len(plan['divisions'])}  "
             f"placements: {len(plan['placements'])}  unplaced: {len(plan['unplaced'])}",
             f"  locations: {', '.join(l['id'] for l in r['locations'])}"]
    return "\n".join(lines)


def _selftest():
    from scheduler_multi import schedule_multi, MultiConfig, EventSpec, Team

    # A tiny two-division field with a shared player (cross-division), one elim + one RR.
    evs = [
        EventSpec(name="Men's 65 Singles", fmt="single_elim",
                  teams=[Team("1", ["Al Ace"]), Team("2", ["Bo Bell"]),
                         Team("3", ["Cy Cole"]), Team("4", ["De Dunn"])]),
        EventSpec(name="Men's 70 Singles", fmt="round_robin",
                  teams=[Team("5", ["Al Ace"]), Team("6", ["Ed East"]), Team("7", ["Fi Fox"])]),
    ]
    cfg = MultiConfig(tournament_name="edit-smoke", num_courts=3,
                      dates=["2026-01-31", "2026-02-01"], events=evs,
                      courts_by_day={"2026-01-31": 3, "2026-02-01": 3},
                      court_locations={"2026-01-31": [(1, 2, "MHCC"), (3, 3, "ORLP")],
                                       "2026-02-01": [(1, 2, "MHCC"), (3, 3, "ORLP")]})
    res = schedule_multi(cfg)
    con = {"schema": "td-constraints/v1", "min_start_to_start_minutes": 180}
    plan = editor_plan(res, cfg, events=evs, constraints_doc=con,
                       local_players={"Al Ace", "Zzz Nobody"})

    assert plan["schema"] == EDITOR_PLAN_SCHEMA
    assert len(plan["placements"]) == len(res["schedule"]) > 0
    # locals: only names that both are local AND appear in a placement (Al Ace plays; Zzz Nobody does not)
    assert plan["locals"] == ["Al Ace"], plan["locals"]
    # omitting local_players leaves the field inert (empty)
    assert editor_plan(res, cfg, events=evs)["locals"] == []
    # court never surfaced
    assert all("court" not in p for p in plan["placements"])
    # every placement carries location + duration + division
    assert all(p["location"] in ("MHCC", "ORLP") for p in plan["placements"])
    assert all(p["duration"] and p["div"] for p in plan["placements"])
    # resources: two locations, capacity from the layout (MHCC 2, ORLP 1), hours present
    rl = {l["id"]: l for l in plan["resources"]["locations"]}
    assert set(rl) == {"MHCC", "ORLP"}
    assert rl["MHCC"]["capacity_by_day"]["2026-01-31"] == 2 and rl["ORLP"]["capacity_by_day"]["2026-01-31"] == 1
    assert rl["MHCC"]["hours_by_day"]["2026-01-31"] == ["08:00", "18:00"]
    # divisions: one elim (with rounds) + one rr (with teams)
    dv = {d["name"]: d for d in plan["divisions"]}
    assert dv["Men's 65 Singles"]["fmt"] == "elim" and dv["Men's 65 Singles"]["rounds"]
    assert dv["Men's 70 Singles"]["fmt"] == "rr" and "Al Ace" in dv["Men's 70 Singles"]["teams"]
    # constraints echoed, unchanged
    assert plan["constraints"]["min_start_to_start_minutes"] == 180
    # F3: opening_ids = each player's earliest scheduled match per division (mirrors first_round_rows),
    # never scoped to a single day and not literal round==1.
    oid = set(plan["opening_ids"])
    assert oid, "opening_ids empty"
    by_id = {p["id"]: p for p in plan["placements"]}
    earliest = {}
    for p in plan["placements"]:
        for who in p["players"]:
            k = (who, p["div"])
            stamp = (p["day"] or "", p["start"] or "")
            if k not in earliest or stamp < earliest[k][0]:
                earliest[k] = (stamp, p["id"])
    assert oid == {v[1] for v in earliest.values()}, "opening_ids != per-player earliest set"
    assert all(by_id[i]["round"] is not None for i in oid)
    assert "opening_ids" not in editor_plan(res, cfg) or isinstance(
        editor_plan(res, cfg)["opening_ids"], list)   # additive field always a list
    # final round labelled "Final"
    last = dv["Men's 65 Singles"]["rounds"][-1]
    assert last["name"] == "Final"

    # CUI-1: the generated preloaded console — self-contained, embeds THIS plan, deterministic
    html = render_editor_console(plan)
    assert html == render_editor_console(plan), "render must be deterministic"
    import json as _json
    assert _json.dumps(plan).replace("</", "<\\/") in html, "plan not embedded verbatim"
    for needle in ("schedule-edits/v1", "emitBtn", "Edit Console"):
        assert needle in html, f"generated console missing {needle!r}"
    for banned in ("fetch(", "XMLHttpRequest", "WebSocket", "<script src", 'id="paste"'):
        assert banned not in html, f"generated console must be offline/preloaded: found {banned!r}"
    try:
        render_editor_console({"schema": "nope"})
        raise AssertionError("renderer accepted a non-plan doc")
    except ValueError:
        pass
    print(f"render_editor_console: {len(html)//1024} KB, offline, preloaded, deterministic")

    print("editor_plan self-test OK")
    print(editor_plan_text(plan))


if __name__ == "__main__":
    _selftest()
