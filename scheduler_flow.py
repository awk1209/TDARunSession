"""
WynTennis Scheduling Flow Layer (chat-mediated three-step)
==========================================================
Adds a decision/answer round-trip on top of the deterministic engine in
scheduler_multi.py, without changing the engine's scheduling math:

  Step 1  plan_multi(cfg)              -> {"plan": <result>, "decisions_doc": <td-decisions/v1>}
  Step 2  (human resolves decisions in the console; emits <td-answers/v1>)
  Step 3  finalize_multi(cfg, answers) -> final result with the answers applied

The trick that keeps the console light: the engine is deterministic, so
finalize_multi re-runs _build_and_place(cfg) to reconstruct the *identical*
match state, re-derives the same decision IDs, then applies the answers on top.
The console therefore only ever carries the decisions and answers — never the
whole schedule.

Decision IDs are stable across plan_multi and finalize_multi for the same cfg:
  unplaced -> U1, U2, ...   overlaps -> O1, O2, ...   staggers -> S1, S2, ...
"""

from __future__ import annotations
from datetime import datetime, timedelta

from scheduler_multi import (
    MultiConfig,
    _same_day_finish_pairs,
    busy_map,
    cadence_conflicts_of,
    _build_and_place,
    _assemble_result,
    _potential_later_round_overlaps,
    _move_to_next_slot,
    _free_location,
    _humans_ok,
    _location_open,
    _scan_locations,
    _mark_slot,
    _loc_usage,
    _day_locations,
    # EVAL-1: the refusal names its match the way the conflicts sheet names one — division, round
    # and players, never an internal id (LANG-1 ruling 3). IMPORTED rather than restated: this
    # string can end up beside the engine's own conflict lines on the same page, and two spellings
    # of one match on one page is exactly what ruling 3 exists to stop.
    _c_match,
    _FULL,
)

DECISIONS_SCHEMA = "td-decisions/v1"
ANSWERS_SCHEMA = "td-answers/v1"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _hhmm(dt) -> str | None:
    return dt.strftime("%H:%M") if dt else None


def _slug(s: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in s).strip("-")


def _default_plan_id(cfg: MultiConfig) -> str:
    return f"{_slug(cfg.tournament_name)}-{'_'.join(cfg.dates)}"


def _location_has_room(occ: dict, day: str, st: datetime, en: datetime,
                       loc, cap: int) -> bool:
    """Deferred-court: is location `loc` below its concurrent capacity for [st, en)?"""
    return _loc_usage(occ, day, loc, st, en) < cap


# --------------------------------------------------------------------------
# decision emission (shared by plan_multi and finalize_multi)
# --------------------------------------------------------------------------
def _emit_decisions(all_matches, unplaced, overlap_records, stagger_records) -> list[dict]:
    by_id = {m.mid: m for m in all_matches}
    decisions: list[dict] = []

    for n, mid in enumerate(unplaced, start=1):
        m = by_id.get(mid)
        decisions.append({
            "id": f"U{n}",
            "type": "unplaced_match",
            "prompt": "No feasible slot was found for this match in the given courts and dates.",
            "context": {
                "match_id": mid,
                "event": m.event if m else None,
                "round": m.rnd if m else None,
                "label": m.label if m else mid,
                "players": sorted(m.humans) if (m and m.humans) else [],
                "reason": "All in-bounds slots full or blocked by recovery/feeder constraints.",
            },
            "options": [
                {"value": "pin", "label": "Pin to a specific slot", "payload": ["day", "start", "location"]},
                {"value": "leave", "label": "Leave unplaced (handle manually)"},
                {"value": "rerun_add_resource", "label": "Add a day or court and re-run"},
            ],
        })

    for n, r in enumerate(overlap_records, start=1):
        a, b = by_id.get(r["mid_a"]), by_id.get(r["mid_b"])
        decisions.append({
            "id": f"O{n}",
            "type": "potential_overlap",
            "prompt": "If these players advance, they could be double-booked in this time block.",
            "context": {
                "day": r["day"],
                "time_block": r["time_block"],
                "match_a": {"id": r["mid_a"], "label": r["label_a"], "day": r["day"], "start": _hhmm(a.start) if a else None},
                "match_b": {"id": r["mid_b"], "label": r["label_b"], "day": r["day"], "start": _hhmm(b.start) if b else None},
                "shared_players": r["shared"],
            },
            "options": [
                {"value": "move_a", "label": f"Move {r['label_a']} to next free slot"},
                {"value": "move_b", "label": f"Move {r['label_b']} to next free slot"},
                {"value": "accept_rerun", "label": "Accept now, re-run after results"},
                {"value": "accept", "label": "Accept as-is"},
            ],
        })

    for n, r in enumerate(stagger_records, start=1):
        decisions.append({
            "id": f"S{n}",
            "type": "stagger_review",
            "prompt": "The engine staggered this final to avoid a guaranteed clash. Keep it?",
            "context": {
                "match_id": r["match_id"],
                "event": r["event"],
                "day": r["day"],
                "from": r["from"],
                "to": r["to"],
                # FIX-1 item 4: this read `r["court"]` and raised KeyError on every staggered
                # final, because the deferred-court migration made court numbers a day-of
                # decision (`m.court` is always None) and `_stagger_finals` emits `location`
                # instead. It crashed the whole courier lane: `plan_multi` on the reference
                # field staggers 6 finals, so step 1 could not complete at all.
                "location": r["location"],
                "reason": f"Shared a slot with the {r['shared_with']} final; the fields share players.",
            },
            "options": [
                {"value": "keep", "label": "Keep the stagger"},
                {"value": "revert", "label": "Revert to the original slot"},
            ],
        })

    return decisions


# --------------------------------------------------------------------------
# STEP 1
# --------------------------------------------------------------------------
def plan_multi(cfg: MultiConfig, plan_id: str | None = None) -> dict:
    # FIX-1: `out=` must be passed. Without it the engine's spill and cadence reports were
    # built and then dropped on the floor, so the courier lane — the product path — showed the
    # Operator neither which matches missed their assigned day nor any cadence collision.
    info = {}
    all_matches, occ, unplaced, stagger_records = _build_and_place(cfg, out=info)
    overlap_records = _potential_later_round_overlaps(all_matches)
    decisions = _emit_decisions(all_matches, unplaced, overlap_records, stagger_records)
    plan = _assemble_result(cfg, all_matches, unplaced, stagger_records,
                            day_shape_exceptions=info.get("day_shape_exceptions"),
                            rule_escapes=info.get("rule_escapes"),
                            spills=info.get("spills"),
                            cadence_conflicts=info.get("cadence_conflicts"))
    return {
        "plan": plan,
        "decisions_doc": {
            "schema": DECISIONS_SCHEMA,
            "tournament": cfg.tournament_name,
            "plan_id": plan_id or _default_plan_id(cfg),
            "summary": {
                "matches_needing_court": plan["total_matches_needing_court"],
                "placed": len([m for m in all_matches if m.start]),
                "unplaced": len(unplaced),
                "overlaps": len(overlap_records),
                "staggers": len(stagger_records),
            },
            "decisions": decisions,
        },
    }


# --------------------------------------------------------------------------
# STEP 3 — apply answers
# --------------------------------------------------------------------------
def _apply_pin(m, payload, occ, cfg, did) -> dict:
    if m is None:
        return {"id": did, "result": "skipped", "detail": "match not found"}
    try:
        day = payload["day"]
        start = payload["start"]
    except (KeyError, TypeError):
        return {"id": did, "result": "skipped", "detail": "pin needs day, start, location"}
    # Deferred-court: a pin targets a LOCATION, not a court number. DRAW-1 (2026-08-06)
    # retired the legacy court-number fallback with the advertised payload — the contract's
    # §6 checklist had marked this migration SHIPPED while both still spoke `court`.
    loc = payload.get("location")
    st = datetime.strptime(f"{day} {start}", "%Y-%m-%d %H:%M")
    en = st + timedelta(minutes=m.match_minutes)
    day_end = datetime.strptime(f"{day} {cfg.daily_end}", "%Y-%m-%d %H:%M") - timedelta(
        minutes=cfg.end_of_day_buffer_minutes)
    if en > day_end:
        return {"id": did, "result": "rejected", "match": m.mid, "detail": "runs past end-of-day buffer"}
    caps = dict(_day_locations(cfg, day))
    if loc not in caps:
        return {"id": did, "result": "rejected", "match": m.mid, "detail": f"unknown location {loc!r} on {day}"}
    if not _location_has_room(occ, day, st, en, loc, caps[loc]):
        return {"id": did, "result": "rejected", "match": m.mid, "detail": f"location {loc or 'pool'} at capacity at requested time"}
    m.start, m.end, m.day = st, en, day
    m.court = None
    m.location = loc
    _mark_slot(occ, day, st, en, loc)
    return {"id": did, "result": "pinned", "match": m.mid, "day": day, "start": start, "location": loc}


def _apply_revert(ctx, by_id, occ, cfg, did) -> dict:
    m = by_id.get(ctx["match_id"])
    if m is None or m.start is None:
        return {"id": did, "result": "skipped", "detail": "final not placed"}
    day = ctx["day"]
    orig = datetime.strptime(f"{day} {ctx['from']}", "%Y-%m-%d %H:%M")
    en = orig + timedelta(minutes=m.match_minutes)
    # free the current slot
    cur = occ.get((m.day, m.start), [])
    if (m.location, m.end) in cur:
        cur.remove((m.location, m.end))
    # FIX-1a (Operator-signed-off 2026-07-30). Two changes, and the second is why the first
    # matters. (a) Try every open location at the original slot, not just `_free_location`'s head.
    # (b) Check that reverting leaves this match's players conflict-free — which this never did.
    #
    # A stagger exists precisely because two finals shared a slot and their fields share players;
    # reverting put the match back into that slot with a capacity test alone, so it could restore
    # the double-booking the stagger was created to prevent. `_move_to_next_slot` has taken a
    # `busy` map since 2026-07-25 for exactly this reason; the revert that undoes it did not, and
    # a move that is checked paired with a revert that is not is not a coherent pair. Without (b)
    # there is nothing for (a) to fail over, so a location loop alone would have been decorative.
    busy = busy_map(by_id.values(), m.mid)
    chosen = _FULL
    # ENG-1 / ruling 72: the exception has to reach here too, or a revert that is legal at the TD's
    # 150-minute gap is refused with "reverting would double-book or under-rest a player" — the
    # engine's own placement reported back as illegal.
    sdf_exempt = _same_day_finish_pairs(list(by_id.values()), cfg)
    for cand in _scan_locations(occ, day, orig, en, cfg):
        if _humans_ok(m, busy, orig, en, cfg.min_start_to_start_minutes, cand,
                      cfg.transit_minutes, cfg, sdf_exempt):
            chosen = cand
            break
    if chosen is _FULL:                     # can't revert; restore current slot
        _mark_slot(occ, m.day, m.start, m.end, m.location)
        # OI-38 (closed at DRAW-1, 2026-08-06): name the TRUE cause. `_scan_locations` returns
        # empty both for a capacity exhaustion and for a venue closed at that hour, so the old
        # two-string branch reported an hours refusal as a booking clash. Distinguish before
        # composing: candidates that passed capacity+hours but failed the player check ->
        # double-book/under-rest; no location OPEN at that time -> the hours cause, naming it;
        # locations open but full -> occupied.
        if _scan_locations(occ, day, orig, en, cfg):
            detail = "reverting would double-book or under-rest a player in this match"
        else:
            open_locs = [loc for loc, _cap in _day_locations(cfg, day)
                         if _location_open(cfg, day, loc, orig, en)]
            if open_locs:
                detail = "original slot now occupied"
            else:
                detail = (f"no venue is open at {ctx['from']} on {day} — "
                          "the original slot is outside every venue's hours")
        return {"id": did, "result": "not_reverted", "match": m.mid, "detail": detail}
    m.start, m.end, m.day = orig, en, day
    m.court = None
    m.location = chosen
    _mark_slot(occ, day, orig, en, chosen)
    return {"id": did, "result": "reverted", "match": m.mid, "to": ctx["from"], "location": chosen}


def _apply_answer(d, ans, by_id, occ, cfg) -> dict:
    t = d["type"]
    choice = ans.get("choice")
    ctx = d["context"]
    did = d["id"]

    if t == "unplaced_match":
        if choice == "leave":
            return {"id": did, "result": "left_unplaced", "match": ctx["match_id"]}
        if choice == "rerun_add_resource":
            return {"id": did, "result": "pending_rerun", "match": ctx["match_id"],
                    "detail": "TD wants more courts/days; adjust cfg and re-run plan_multi."}
        if choice == "pin":
            return _apply_pin(by_id.get(ctx["match_id"]), ans.get("payload") or {}, occ, cfg, did)
        return {"id": did, "result": "skipped", "detail": f"unknown choice {choice!r}"}

    if t == "potential_overlap":
        if choice in ("accept", "accept_rerun"):
            return {"id": did, "result": "accepted", "detail": choice}
        if choice == "move_a":
            mid = ctx["match_a"]["id"]
        elif choice == "move_b":
            mid = ctx["match_b"]["id"]
        else:
            return {"id": did, "result": "skipped", "detail": f"unknown choice {choice!r}"}
        # FIX-1 item 4: guard the same way the two sibling handlers already do (`_apply_pin`
        # returns "match not found"; `_apply_revert` checks None and unplaced). This call was
        # the only unguarded one, so a match that is missing or unplaced reached
        # `_move_to_next_slot` and raised on `m.day` / `m.start + gap`. Unreachable from a
        # self-consistent decisions doc — the ids are re-derived from this build — so this
        # changes no reachable behavior; it removes a crash where a skip belongs.
        target = by_id.get(mid)
        if target is None or target.start is None:
            return {"id": did, "result": "skipped", "match": mid,
                    "detail": "match not found or not placed"}
        moved = _move_to_next_slot(target, cfg, occ)
        if moved:
            return {"id": did, "result": "moved", "match": mid, "from": moved["from"], "to": moved["to"]}
        return {"id": did, "result": "not_moved", "match": mid, "detail": "no later slot available that day"}

    if t == "stagger_review":
        if choice == "keep":
            return {"id": did, "result": "kept", "event": ctx["event"]}
        if choice == "revert":
            return _apply_revert(ctx, by_id, occ, cfg, did)
        return {"id": did, "result": "skipped", "detail": f"unknown choice {choice!r}"}

    return {"id": did, "result": "skipped", "detail": f"unknown type {t!r}"}


def finalize_multi(cfg: MultiConfig, answers_doc: dict, plan_id: str | None = None) -> dict:
    # rebuild the identical deterministic state, then re-derive the same decisions
    info = {}
    all_matches, occ, unplaced, stagger_records = _build_and_place(cfg, out=info)
    overlap_records = _potential_later_round_overlaps(all_matches)
    decisions = _emit_decisions(all_matches, unplaced, overlap_records, stagger_records)
    dec_by_id = {d["id"]: d for d in decisions}
    by_id = {m.mid: m for m in all_matches}

    pid = plan_id or _default_plan_id(cfg)
    warn = None
    if answers_doc.get("plan_id") and answers_doc["plan_id"] != pid:
        warn = f"answers plan_id {answers_doc['plan_id']!r} != current {pid!r}; cfg may have changed since planning."

    applied = []
    for ans in answers_doc.get("answers", []):
        d = dec_by_id.get(ans.get("id"))
        if not d:
            applied.append({"id": ans.get("id"), "result": "skipped", "detail": "unknown decision id"})
            continue
        applied.append(_apply_answer(d, ans, by_id, occ, cfg))

    # recompute open state AFTER edits (pins may have placed matches; moves/reverts shifted them)
    remaining_unplaced = [m.mid for m in all_matches if m.scheduled_needed and m.start is None]
    # FIX-1: carry the engine's spill + cadence reports (see plan_multi). The answers may have
    # moved matches, so these describe the base build the Operator was answering about.
    result = _assemble_result(cfg, all_matches, remaining_unplaced, [],  # staggers already applied / possibly reverted
                              spills=info.get("spills"),
                              day_shape_exceptions=info.get("day_shape_exceptions"),
                              rule_escapes=info.get("rule_escapes"),
                              cadence_conflicts=info.get("cadence_conflicts"))
    result["applied_answers"] = applied
    result["plan_id"] = pid
    if warn:
        result["plan_id_warning"] = warn
    return result


# --------------------------------------------------------------------------
# STEP 3' — apply Edit-console edits (schedule-edits/v1)  [Phase 5, ADJ-1]
# --------------------------------------------------------------------------
EDITS_SCHEMA = "schedule-edits/v1"


def _free_current(m, occ) -> None:
    """Remove m's current occupancy and clear its placement (used by move/hold)."""
    if m.start is None:
        return
    cell = occ.get((m.day, m.start), [])
    if (m.location, m.end) in cell:
        cell.remove((m.location, m.end))
    m.start = m.end = m.day = m.location = None
    m.court = None


def _place_at(m, day, start, location, occ, cfg) -> dict:
    """Place m at (day, start, location) — the deferred-court identity. Rejects only
    STRUCTURAL invalidity (missing fields, unknown location, past end-of-day). A placement
    that merely conflicts (over capacity / double-book) is APPLIED and left for validate_multi
    to flag — the editor is WYSIWYG, so the emitted edit is honoured and the re-check tells the
    truth. Court is never assigned."""
    if not (day and start and location):
        return {"result": "rejected", "match": m.mid, "detail": "move needs day, start, location"}
    st = datetime.strptime(f"{day} {start}", "%Y-%m-%d %H:%M")
    en = st + timedelta(minutes=m.match_minutes)
    day_end = datetime.strptime(f"{day} {cfg.daily_end}", "%Y-%m-%d %H:%M") - timedelta(
        minutes=cfg.end_of_day_buffer_minutes)
    if en > day_end:
        return {"result": "rejected", "match": m.mid, "detail": "runs past end-of-day buffer"}
    if location not in dict(_day_locations(cfg, day)):
        return {"result": "rejected", "match": m.mid, "detail": f"unknown location {location!r} on {day}"}
    m.start, m.end, m.day, m.location, m.court = st, en, day, location, None
    _mark_slot(occ, day, st, en, location)
    return {"result": "placed", "match": m.mid, "day": day, "start": start, "location": location}


# --------------------------------------------------------------------------
# GENDER-1 (2026-08-08) — a Mixed team stays one man and one woman, on THIS side of the courier
# lane too. The console's block (`schedule_editor.html::mixedBlockWhy`) guards the surface the TD
# uses; this guards the document. A `schedule-edits/v1` block is hand-buildable and reaches the
# engine without a browser ever running, which is exactly how the 2027 mock put two men on a
# Mixed court with nothing refusing it.
#
# ONE WORDING, written once and stated identically by both surfaces — `tests/gender1_guard.py`
# asserts the two byte-for-byte. Two descriptions of the same refusal is support noise on a lane
# whose whole design is a human carrying JSON between two programs.
_MIXED_BLOCK = ("Blocked · {inn} in for {out} would leave {inn} and {partner} — two {many} — as "
                "a team in {div}. A Mixed team is one man and one woman, and {partner} is "
                "already a {one} on it. Pick a {need}.")


def _is_mixed(event: str) -> bool:
    """Mixed is read off the division name, the same test `schedule_report.event_kind` makes and
    the console's `divParse` makes — asserted equal across all three in `tests/gender1_guard.py`.
    The reporter's copy is not imported: that module states, at its own top, that it imports no
    engine and no engine imports it, and GENDER-1 does not spend that decoupling on one predicate.
    """
    return str(event or "").strip().lower().startswith("mixed")


def _gender_by_name(roster) -> dict:
    """{name: "M" | "F"} off the entry list's own `Gender` column, for the names the roster knows.

    A name two records disagree about collapses to absent, not to a guess — the roster is keyed
    by USTA id and a `substitute` edit names people, so an ambiguous name must never decide a
    refusal. Measured on the committed field: 759 of 759 records carry a value (559 M / 200 F)
    and 0 names are ambiguous. Omitted roster => `{}` => no test runs at all, which is today's
    behaviour exactly.
    """
    out: dict = {}
    for p in (roster or {}).values():
        g = (getattr(p, "gender", "") or "").strip().upper()[:1]
        g = g if g in ("M", "F") else None
        if p.name in out and out[p.name] != g:
            out[p.name] = None
        else:
            out.setdefault(p.name, g)
    return {n: g for n, g in out.items() if g}


def _mixed_gender_block(m, out_name, in_name, sex) -> str | None:
    """The refusal text, or None when this substitution may proceed.

    Tested on the team the substitution LEAVES BEHIND — the incoming player beside the partner
    who stays — never on the outgoing player. On a legal Mixed team the two readings are one test;
    they part only on a team that is already wrong, where reading the outgoing player would refuse
    the substitution that FIXES it. Measured on the committed field: 0 Mixed teams are already
    wrong, so the readings agree on every one of them.

    BOTH genders must be entry-list facts. Either absent and nothing is refused — ruling 88 is
    narrowed, never overturned: the tool blocks on a fact and never on a guess.
    """
    if not sex or not _is_mixed(m.event):
        return None
    side = (m.team_a if out_name in (m.team_a or ())
            else (m.team_b if out_name in (m.team_b or ()) else None))
    if not side:
        return None
    after = [in_name if p == out_name else p for p in side]
    after = [p for p in after if p in m.humans or p == in_name]
    if len(after) != 2:
        return None                       # one name is not a team; there is nothing to test
    partner = next((p for p in after if p != in_name), None)
    gi, gp = sex.get(in_name), sex.get(partner)
    if not gi or not gp or gi != gp:
        return None
    return _MIXED_BLOCK.format(
        inn=in_name, out=out_name, partner=partner, div=m.event,
        many="women" if gi == "F" else "men", one="woman" if gi == "F" else "man",
        need="man" if gi == "F" else "woman")


def _apply_substitute(m, e, mid, sex=None) -> dict:
    """DRAW-1: replace the outgoing player with the incoming one on match `m` — humans,
    team lists and label. Structural invalidity is REJECTED (missing names, a `kept` seed with
    no recorded reason — NQ-3's override must never apply silently); a substitution that merely
    creates a conflict is APPLIED and left for validate_multi to flag, the same WYSIWYG rule
    `_place_at` follows. Placement is untouched — this op changes who, never where."""
    sub = e.get("sub") or {}
    out_name, in_name = sub.get("out_name"), sub.get("in_name")
    if not out_name or not in_name:
        return {"id": mid, "op": "substitute", "result": "rejected",
                "detail": "substitute needs sub.out_name and sub.in_name"}
    if e.get("seed_effect") == "kept" and not (e.get("seed_kept_reason") or "").strip():
        return {"id": mid, "op": "substitute", "result": "rejected",
                "detail": "seed_effect 'kept' with no seed_kept_reason — a kept seed "
                          "must record why (NQ-3, D-48)"}
    if out_name not in m.humans:
        return {"id": mid, "op": "substitute", "result": "rejected",
                "detail": f"{out_name!r} is not in this match"}
    # GENDER-1: refused BEFORE anything is mutated, and per-edit — every other edit in the same
    # block still applies, which is the existing `applied_edits` contract and not a new shape.
    # This is a REFUSAL, not the WYSIWYG "apply and let validate_multi flag it" rule the rest of
    # this function follows, and the difference is deliberate: a capacity clash is a schedule the
    # TD can look at and accept, while two men on a Mixed court is not a schedule at all.
    blocked = _mixed_gender_block(m, out_name, in_name, sex)
    if blocked:
        return {"id": mid, "op": "substitute", "result": "rejected", "detail": blocked}
    m.humans.discard(out_name)
    m.humans.add(in_name)
    m.team_a = [in_name if p == out_name else p for p in m.team_a]
    m.team_b = [in_name if p == out_name else p for p in m.team_b]
    m.label = m.label.replace(out_name, in_name)
    rec = {"id": mid, "op": "substitute", "result": "substituted",
           "out": sub.get("out"), "in": sub.get("in"),
           "out_name": out_name, "in_name": in_name}
    if e.get("seed_effect") is not None:
        rec["seed_effect"] = e["seed_effect"]
        if e.get("seed_kept_reason"):
            rec["seed_kept_reason"] = e["seed_kept_reason"]
    if e.get("note"):
        rec["note"] = e["note"]
    return rec


# EDITBASE-1 (2026-08-08) — the whole-block refusal, written once so the two halves of the
# reason cannot drift apart. BOTH ids are named and the REMEDY is named: a message that says only
# what is wrong leaves the courier holding a document and no next step, which on a lane whose
# only actor is a human carrying JSON is the same as saying nothing.
_STALE_BLOCK = (
    "Refused · this block of changes was made in a console built from a different schedule "
    "({theirs}), and this schedule is {ours}. NOTHING in it was applied — all {n} change(s) were "
    "left out, so the schedule is exactly as it was. What to do: open a freshly generated Edit "
    "console for this schedule and make the changes there. A regenerated console already carries "
    "every change made so far, so nothing that was already done is lost.")
_UNSTAMPED_BLOCK = (
    "Refused · this block of changes does not say which schedule it was made against, so there "
    "is no way to tell whether it belongs to this one ({ours}). NOTHING in it was applied — all "
    "{n} change(s) were left out, so the schedule is exactly as it was. What to do: open a "
    "freshly generated Edit console for this schedule and make the changes there; that console "
    "stamps every block it produces. A hand-written block cannot be applied.")


# EVAL-1 (2026-08-16) — half (b), the back door closes. A `move`/`pin` whose target day is not the
# match's DELIVERED day is refused, PER EDIT (`_MIXED_BLOCK`'s shape, never `_STALE_BLOCK`'s
# whole-block one): a cross-day move is one bad instruction inside a document whose other
# instructions are fine, while a stale block is a document about a different schedule.
#
# ⚠ THE IDENTITY IS THE BASE BUILD'S DAY FOR THAT ID, captured before the edit loop runs — never
# `m.day`. `_free_current` sets `m.day = None` on a `hold` (`:371`), so a refusal reading the
# object's own day would compare against `None` on the legal hold-then-replace cycle (the
# console's own replace path) and wave through the cross-day re-place it exists to stop. This is
# the same capture the console's `mustDay` makes at load (`schedule_editor.html:775`).
#
# WHY A REFUSAL AND NOT THE WYSIWYG "apply and let validate_multi flag it" rule the rest of this
# module follows (`_place_at`'s own comment): a capacity clash is a schedule the TD can look at
# and accept; a match on a day his finals map never promised is not a schedule he was ever shown.
# No console gesture can emit one (measured across the whole six-edit replay), so this path is
# reachable only from a hand-built document — exactly the lane it exists to close.
_CROSS_DAY_BLOCK = (
    "Refused · {who} plays {delivered}, and this change asks for {target}. A match keeps its day "
    "— times and courts change on the Edit console, days do not. Nothing else in this block is "
    "affected. What to do: to move a division's rounds to another day, change the finals map and "
    "build again.")

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _fmt_day(iso: str) -> str:
    """`2026-01-26` -> `Jan 26`, the short form every TD-facing surface already uses (the
    console's own `fmtDay`, approved 8/8). An ISO date is a machine's way of saying it."""
    try:
        _year, mo, day = str(iso).split("-")
        return f"{_MONTHS[int(mo) - 1]} {int(day)}"
    except (ValueError, IndexError, TypeError):
        return str(iso)


class StaleEditBlock(ValueError):
    """EDITBASE-1: a `schedule-edits/v1` block that is not stamped for THIS build. Raised before
    a single edit is applied, so the refusal cannot be half-honoured.

    Why it raises rather than returning a result with a reason on it: the run lane's Step 5 reads
    `r["applied_edits"]` and moves on. A returned base result with an empty edit list reads, on
    that surface, as "the TD made no changes" — which is the *exact* silent-loss failure this
    build exists to end (run report D2). F7's finals-map validation set the precedent: a courier
    document that cannot be trusted is rejected loudly, never absorbed."""


def apply_schedule_edits(cfg: MultiConfig, edits_doc: dict, plan_id: str | None = None,
                         roster: dict | None = None, allow_unstamped: bool = False) -> dict:
    """Apply an Edit-console schedule-edits/v1 doc onto the deterministic base schedule and
    re-validate. Ops: `move`/`pin` -> _place_at{day,start,location}; `hold` -> unplace;
    `substitute` (DRAW-1) -> _apply_substitute, who-not-where. The engine re-runs validate_multi
    in _assemble_result, so any conflict the TD's edits introduce (capacity / double-book /
    rest / the incoming player's other divisions) is surfaced, not hidden. B-1: the console
    couriers this doc; the engine never reads the console directly.

    EVAL-1 half (b) (2026-08-16, engine sign-off given with the brief): a `move`/`pin` whose
    `to.day` differs from the match's DELIVERED day — the base build's day for that id, captured
    before the edit loop — is REJECTED, per edit, with the reason named (`_CROSS_DAY_BLOCK`).
    `schedule-edits/v1` gains no field: an advertised surface starts refusing, EDITBASE-1's own
    shape. Hold-then-replace on the SAME day stays legal — it is the console's own replace path.

    `roster` (GENDER-1, 2026-08-08, additive keyword-with-default): the pipeline's
    `{usta_id: Player}` — the entry list. Supplied, a `substitute` that would leave a Mixed team
    two men or two women is REFUSED, per edit, naming both players and the division; every other
    edit in the block still applies. Omitted => no gender test runs and this function behaves
    exactly as it did before, which is also why the runbook's Step 5 call has to pass it: a
    keyword nobody passes ships the guard inert on the one lane a real run uses (the ENG-1/D-41
    lesson, and REKEY-1's own precedent). `schedule-edits/v1` gains no field — the fact comes
    from the entry list, never from the couriered document, or a hand-built block could assert
    its way past the guard it is there to trip.

    `allow_unstamped` (EDITBASE-1, 2026-08-08): the COMPAT PATH, named at the call site rather
    than hidden in here. A block whose `plan_id` is absent or null is REFUSED by default —
    that is this build's ruling — but a function-level caller that is replaying a document
    written before the console stamped anything (the two committed run archives, and the
    harnesses that hand-build a block to exercise one op) opts out explicitly. The run lane
    never passes it, and the exemption is therefore visible in the file that takes it: a caller
    reading `allow_unstamped=True` knows it is replaying history, not editing a tournament.
    A MISMATCHED id is refused either way — that is a document about a different schedule, and
    no caller may wave it through."""
    info = {}
    all_matches, occ, unplaced, _stagger = _build_and_place(cfg, out=info)
    by_id = {m.mid: m for m in all_matches}
    # EVAL-1 half (b): THE DELIVERED DAY, captured HERE — from the base build, before a single
    # edit runs — for the reason `_CROSS_DAY_BLOCK` states at length. A match the base build left
    # unplaced has no delivered day and nothing to compare against, so it carries none and the
    # refusal never fires on it (measured on the committed field: 0 such matches).
    delivered = {m.mid: m.day for m in all_matches if m.day}
    pid = plan_id or _default_plan_id(cfg)

    # EDITBASE-1 — the whole-block gate, AHEAD of the per-edit loop and ahead of GENDER-1's
    # per-edit refusal inside `_apply_substitute`. The order is load-bearing: a block that is
    # both stale AND carries an illegal Mixed substitution is refused whole, by plan id, before
    # the gender test ever runs. Nothing is placed, nothing is substituted, nothing is held.
    theirs, n = edits_doc.get("plan_id"), len(edits_doc.get("edits") or ())
    if theirs and theirs != pid:
        raise StaleEditBlock(_STALE_BLOCK.format(theirs=theirs, ours=pid, n=n))
    if not theirs and not allow_unstamped:
        raise StaleEditBlock(_UNSTAMPED_BLOCK.format(ours=pid, n=n))

    sex = _gender_by_name(roster)          # GENDER-1: {} when no roster => no test, as before
    applied = []
    for e in edits_doc.get("edits", []):
        # DRAW-1 §15 decision 2 (2026-08-06): `id` is the settled spelling; `match_id` is
        # accepted during transition so a document written before the correction is not dropped.
        mid, op = e.get("id", e.get("match_id")), e.get("op")
        m = by_id.get(mid)
        if m is None:
            applied.append({"id": mid, "op": op, "result": "skipped", "detail": "unknown match id"})
            continue
        if op == "hold":
            # HOLDVIS-1 (§3.1): record WHO was in the match and WHAT slot it vacates. The record
            # used to be `{id, op, result}` and nothing else, so every printed surface lost the
            # match AND the players in it: run 2 measured 6 of 1,066 rows gone from the
            # per-player file and 4 of 6 men with no handout page at all. RECORDING ONLY — no
            # placement decision, no ordering, no gate is touched; the `move` branch below
            # already captures the same thing (REKEY-1's landed precedent).
            #
            # Captured HERE, before `_free_current`, for the reason that branch states at length:
            # `_free_current` sets day/start/location to None, so a capture one line later yields
            # `None` for every field and every "Was" cell renders empty on a page that still
            # looks right. `tests/holdvis1_visibility.py` Part E asserts these values BY VALUE.
            frm = ({"day": m.day, "start": m.start.strftime("%H:%M"), "location": m.location}
                   if m.start is not None else None)
            _free_current(m, occ)
            applied.append({"id": mid, "op": op, "result": "held", "from": frm,
                            "event": m.event, "round": m.rnd, "label": m.label,
                            "players": sorted(m.humans)})
        elif op in ("move", "pin"):
            to = e.get("to") or {}
            # EVAL-1 half (b) — refused BEFORE anything is freed or placed, so a rejected edit
            # leaves the match exactly where the base build put it. Per edit: the loop continues
            # and every other instruction in the block still applies.
            home = delivered.get(mid)
            if home and to.get("day") and to["day"] != home:
                applied.append({"id": mid, "op": op, "result": "rejected",
                                "detail": _CROSS_DAY_BLOCK.format(
                                    who=_c_match(m, all_matches, cfg),
                                    delivered=_fmt_day(home),
                                    target=_fmt_day(to["day"]))})
                continue
            # REKEY-1 (A7a): record the slot the match is LEAVING, so the re-enter page can show
            # the desk what it currently holds beside what it should become without needing the
            # base build alongside the edited result. RECORDING ONLY — no placement decision, no
            # ordering, no gate is touched, and the record itself already existed.
            #
            # Captured HERE, before `_free_current`, and not inside `_place_at`: `_free_current`
            # sets day/start/location to None, so a capture one line later yields `None` for every
            # field and every "Was" cell on the page renders empty. That failure is silent — the
            # page still renders and its structure checks still pass — which is why
            # `tests/rekey1_changes.py` Part D asserts all five Was values BY NAME.
            frm = ({"day": m.day, "start": m.start.strftime("%H:%M"), "location": m.location}
                   if m.start is not None else None)
            _free_current(m, occ)   # free the old slot first (no-op if it was unplaced)
            r = _place_at(m, to.get("day"), to.get("start"), to.get("location"), occ, cfg)
            # `from` is null when the match had no slot to leave (a `hold` earlier in the same
            # document, or a match that was never placed). The page prints "not scheduled" there.
            r.update({"id": mid, "op": op, "from": frm})
            applied.append(r)
        elif op == "substitute":
            # DRAW-1 (2026-08-06, ruling 84): changes WHO is in the match, never where it sits.
            # The match keeps its slot; the re-validation below sees the new player in every
            # rest / cap / transit check, so any ripple — including the incoming player's other
            # divisions — is reported, not hidden.
            applied.append(_apply_substitute(m, e, mid, sex))
        else:
            applied.append({"id": mid, "op": op, "result": "skipped", "detail": f"unknown op {op!r}"})

    remaining_unplaced = [m.mid for m in all_matches if m.scheduled_needed and m.start is None]
    # FIX-1: recompute the cadence report over the EDITED schedule rather than carrying the base
    # build's copy. An edit can create a two-rounds-on-one-day collision the base build did not
    # have, and a stale report would call the edited schedule clean. No spill attribution here:
    # the engine's ladder is not what put these rounds together, the TD's edit is.
    result = _assemble_result(cfg, all_matches, remaining_unplaced, [],
                              spills=info.get("spills"),
                              day_shape_exceptions=info.get("day_shape_exceptions"),
                              rule_escapes=info.get("rule_escapes"),
                              cadence_conflicts=cadence_conflicts_of(all_matches, cfg))
    result["applied_edits"] = applied
    # HOLDVIS-1 (§3.1): the held model — ONE descriptor per match the TD held and never placed
    # back, joined from the hold records above and read by all five printed surfaces, so a sheet
    # can never say "held" about a match the player file omits. Derived from the ids still
    # unplaced after the WHOLE document, so a hold RE-PLACED by a later `move` yields no
    # descriptor and no phantom row on a printed page. When the same match is held twice, the
    # first non-null `from` is kept — the slot the desk actually saw published. Consumers read
    # `result.get("held")` and treat absent as empty; a base build carries no key at all.
    still, seen, held = set(remaining_unplaced), {}, []
    for a in applied:
        if a.get("op") != "hold" or a.get("id") not in still:
            continue
        d = seen.get(a["id"])
        if d is None:
            seen[a["id"]] = d = {"id": a["id"], "event": a.get("event"), "round": a.get("round"),
                                 "players": list(a.get("players") or ()),
                                 "label": a.get("label"), "from": a.get("from")}
            held.append(d)
        elif d["from"] is None:
            d["from"] = a.get("from")
    result["held"] = held
    # EDITBASE-1: the edited result carries the id of the build it was made against AND the edits
    # that made it, so `editor_plan` can stamp a regenerated console off the result alone — the
    # projection never has to reach back into the placement path for either fact (DIV-1's guard).
    result["plan_id"] = pid
    return result
