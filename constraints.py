"""Constraints & rules intake (Phase 2).

Defines the `td-constraints/v1` rules contract and layers it onto a `MultiConfig`
already built from the resource slate (`resource_slate.config_from_slate`). The slate
carries *resources* (dates, per-location capacity, hours, transit); this contract carries
the *rules* (rest, placement policy, locality). Mirrors `resource_slate.py`: loud
validation, then a pure mapper.

Phase 2 consumes, from the doc:
  - `min_start_to_start_minutes` — rest override (optional; else the slate/engine default).
  - `placement_policy` — morning/later staging: stage_multidivision_early, locals_early
    (LOCALS-EARLY, CEO 2026-07-25: locals front of their tier; travelers get morning travel
    time). Enables the engine's `_staging_rank`. local_late / local_multidiv_tiebreak RETIRED.
  - `locality` — deterministic home-city / home-section membership → the local names the engine
    parks later (absent city and section => no locals => the local rule is inert, not wrong).
    The legacy exact-zip allowlist was DELETED by ENG-1 (OI-37 b2): the real WWTC export carries
    no zip, so the branch was twice proven dead before it was removed.

  - `match_minutes` — the engine's block length (WIRE-1, 2026-08-02). CONSUMED, not merely
    carried: it is stamped onto every `EventSpec` in `cfg.events`, so a 60 here produces
    60-minute placements. Omitted => the ingest's own 90 stands (an omitted field maps to
    today's behavior). Enum-capped to 60/75/90 — see `_DURATIONS`.
  - `matches_per_day_target` / `finals_per_day` — pacing thresholds (WIRE-1, D-32). Validated
    and carried ONLY; the finals map (FMAP-1) is what reads them. Nothing here consumes them.

`match_caps` also rides in the contract (for the console to show/emit) but stays applied at the
intake layer today (`serve_tennis_intake`), unchanged — routing it through here is ENG-1's.
Five keys were REMOVED from this contract by WIRE-1 and now raise: `tournament` (the resource
slate carries it), `min_rest_minutes`, `rr_threshold`, `singles_before_doubles` and
`singles_day_ahead` — see `_RETIRED`. This module wraps the engine; it does not live inside it.
"""

import re

from scheduler_multi import MultiConfig

CONSTRAINTS_SCHEMA = "td-constraints/v1"

_AGE_RE = re.compile(r"(\d+)\s*&\s*over")
# Range-checked, not just shaped: "25:99" matched the old `^\d{1,2}:\d{2}$` and was handed
# straight to datetime.strptime, which raised out of `_band_setup` — inside `validate_multi`, a
# function every caller relies on returning a list rather than raising. The contract gate is where
# a bad clock time has to stop.
_HHMM_RE = re.compile(r"^(?:[01]?\d|2[0-3]):[0-5]\d$")

# BUDGET-1 (R19, Operator 2026-08-22): the hour Level 1 Mixed should not start after. Used ONLY
# to migrate a document still carrying the retired `l1_mixed_lights_off`; a doc that names
# `l1_mixed_latest_start` for itself is never overridden by it.
_L1_MIXED_LATEST_DEFAULT = "14:00"

# WIRE-1 / D-1 (ruled 2026-07-31, option 1). The offerable match blocks. Capped at 90 because the
# rest rule is start-to-start: at a 180-minute gap, a block over 90 leaves a 60-and-over player
# less than USTA FAC Table 11's 90 minutes of real rest, silently. The hazard is closed by
# SUBTRACTION — the layered end-to-start rest floor that would re-admit 105/120 is deferred (OI-37).
_DURATIONS = (60, 75, 90)

# ENG-1 (2026-08-02). FAC Table 9's age ladder, kept as the DOCUMENTED SANCTIONING CEILING now
# that the operating value is the TD's flat 1 (ruling 75). Reproduces serve_tennis_intake._cap_for
# exactly — USTA's adult brackets step 55->60 and 80->85, so the 56-59 / 81-84 gaps never occur and
# a division with no parseable age reads 0 and lands in the le55 tier.
_KINDS = ("singles", "mixed", "doubles")
_CAP_BANDS = ("le55", "60to80", "ge85")
_CAP_LADDER = {"le55": 6, "60to80": 4, "ge85": 3}


def _caps_mode(caps: dict) -> str:
    """`match_caps.mode`, defaulted from what the block actually carries.

    A blanket "flat" default turned a doc that spells out ONLY the FAC ladder into a flat cap of
    1 — the strictest possible reading of a block whose author wrote 6/4/3. An explicit `mode`
    always wins; otherwise the block is read as whichever of the two it supplies, and as `flat`
    (the ruled default, value 1) when it supplies neither.
    """
    mode = caps.get("mode")
    if mode is not None:
        return mode
    if "flat" not in caps and "age_based" in caps:
        return "age_based"
    return "flat"


def _cap_band(age: int) -> str:
    if age >= 85:
        return "ge85"
    if age >= 60:
        return "60to80"
    return "le55"

# WIRE-1 (2026-08-02). Keys this contract no longer carries. A doc presenting one RAISES rather
# than being quietly ignored — the LOCALS-EARLY precedent below. The Setup console migrates a
# legacy doc silently (it simply stops reading these); this is the gate for a doc that bypasses it.
_RETIRED = {
    "locality.home_zips":
        "locality.home_zips was DELETED from td-constraints/v1 by ENG-1 (2026-08-02, OI-37 b2): "
        "the real export carries no zip column, so the exact-zip branch never ran on a real "
        "field. Locality is home_cities / home_section only. Remove the key",
    "locality.home_prefixes":
        "locality.home_prefixes was DELETED from td-constraints/v1 by ENG-1 (2026-08-02, OI-37 "
        "b2) with home_zips, the legacy alias it aliased. Use locality.home_cities",
    "tournament":
        "tournament was REMOVED from td-constraints/v1 by WIRE-1 (2026-08-02): the resource "
        "slate (td-resource-slate/v1) carries the tournament name, and holding it in two "
        "contracts meant two answers to one question — put it on the slate only",
    "min_rest_minutes":
        "min_rest_minutes was RETIRED by WIRE-1 (2026-08-02, D-2): nothing anywhere read it — "
        "rest is start-to-start only. Use min_start_to_start_minutes. (The slate-side "
        "min_rest_minutes read by resource_slate is a DIFFERENT key and is unaffected.)",
    "rr_threshold":
        "rr_threshold was RETIRED by WIRE-1 (2026-08-02, D-2): a division's format comes from "
        "the printed draws, and the advisory divergence flag it fed was never built",
    "singles_before_doubles":
        "singles_before_doubles was RETIRED by WIRE-1 (2026-08-02, D-2): singles-before-doubles "
        "is the engine's fixed behavior (singles carry precedence 0, doubles 1) and was never "
        "switchable — the checkbox promised a choice that did not exist",
    "singles_day_ahead":
        "singles_day_ahead was CUT by WIRE-1 (2026-08-02, ruling 5): wiring it would have been "
        "building spec rule T-4 in some strength, and the Operator ruled the control out "
        "instead. T-4 itself stays on the orphaned-rules list, UNDELIVERED — removing this key "
        "closes nothing and promises nothing",
}


def _pos_int(v):
    return isinstance(v, int) and not isinstance(v, bool) and v > 0


def _age(name):
    """Age bracket parsed from a division name ('Men's 80 & over singles' -> 80); 0 if none.
    Matches the 'N & over' form the real TD/draws names use (RR-group names carry it too)."""
    m = _AGE_RE.search(name or "")
    return int(m.group(1)) if m else 0


def validate_constraints(doc) -> None:
    """Raise ValueError on a malformed constraints doc; return None if well-formed.

    Loud failure is the project principle. Checks (all rule fields are optional — an
    omitted field maps to today's behavior — but a PRESENT field must be well-typed):
      - dict with schema == td-constraints/v1;
      - no RETIRED key is present (WIRE-1) — each raises with the ruling that removed it;
      - min_start_to_start_minutes, when present, is a positive int;
      - match_minutes, when present, is one of 60/75/90 (WIRE-1 — it now binds placement);
      - matches_per_day_target, when present, is a positive int (WIRE-1/D-32, carried for FMAP-1);
      - finals_per_day, when present, is a dict of positive ints under singles/doubles (ditto);
      - placement_policy, when present, is a dict; its flags are bools; its tiebreak,
        when present, is one of multidivision|local;
      - locality, when present, is a dict; home_cities / commuter_cities, when present, are
        lists of non-empty strings and share no city.
    """
    if not isinstance(doc, dict):
        raise ValueError(f"constraints doc must be a dict, got {type(doc).__name__}")
    if doc.get("schema") != CONSTRAINTS_SCHEMA:
        raise ValueError(
            f"constraints schema must be {CONSTRAINTS_SCHEMA!r}, got {doc.get('schema')!r}")

    # WIRE-1: loud on a retired key, never silent. A doc built against the old contract is a
    # doc whose author believed a field did something; dropping it quietly repeats the defect.
    for key, why in _RETIRED.items():
        if "." not in key and key in doc:      # dotted entries are checked at their own nesting
            raise ValueError(why)

    # WIRE-1: match_minutes BINDS placement now, so an out-of-range value is a hard error rather
    # than a carried curiosity. The console keeps a loaded non-standard value on screen (labelled)
    # so a prefill never silently rewrites a block length — this is where it stops.
    mm = doc.get("match_minutes")
    if mm is not None and (not _pos_int(mm) or mm not in _DURATIONS):
        raise ValueError(
            f"match_minutes must be one of {list(_DURATIONS)}, got {mm!r}. Blocks over 90 minutes "
            "were removed by D-1 (2026-07-31): under the start-to-start rest rule they cut a "
            "60-and-over player's real rest below USTA FAC Table 11's 90-minute minimum")

    # WIRE-1/D-32: pacing thresholds. Validated here, consumed by the finals map (FMAP-1) from the
    # couriered doc — never hardcoded there, and not read by anything in this module.
    mpd = doc.get("matches_per_day_target")
    if mpd is not None and not _pos_int(mpd):
        raise ValueError(f"matches_per_day_target must be a positive integer, got {mpd!r}")

    fpd = doc.get("finals_per_day")
    if fpd is not None:
        if not isinstance(fpd, dict):
            raise ValueError("finals_per_day must be a dict of {singles, doubles}")
        for side in ("singles", "doubles"):
            v = fpd.get(side)
            if v is not None and not _pos_int(v):
                raise ValueError(f"finals_per_day.{side} must be a positive integer, got {v!r}")

    # ENG-1 (2026-08-02, ruling 75): match_caps stops being carried and becomes CONSUMED — the
    # number on screen is the number the engine obeys. `mode` defaults to "flat" and `flat` to 1
    # (the TD's own rule: one match per division per player per day); the FAC Table 9 age ladder
    # is retained under `age_based` as the documented sanctioning ceiling. An OMITTED match_caps
    # leaves the intake's own 6/4/3 in place — the contract's "omitted maps to today's behavior".
    caps = doc.get("match_caps")
    if caps is not None:
        if not isinstance(caps, dict):
            raise ValueError("match_caps must be a dict")
        mode = _caps_mode(caps)
        if mode not in ("flat", "age_based"):
            raise ValueError(f"match_caps.mode must be 'flat' or 'age_based', got {mode!r}")
        flat = caps.get("flat")
        # `null` is rejected rather than defaulted. `.get("flat", 1)` returns None for a key that
        # is PRESENT and null, so a null silently produced max_matches_per_day=None — no cap at
        # all, the opposite of the rule — and a null `gap_minutes` reached `min(int, None)` and
        # killed the run with a TypeError the engine does not catch.
        if "flat" in caps and flat is None:
            raise ValueError(
                "match_caps.flat must be a positive integer, got null — omit the key to take the "
                "default of 1 rather than nulling it, which would remove the cap entirely")
        if flat is not None and not _pos_int(flat):
            raise ValueError(f"match_caps.flat must be a positive integer, got {flat!r}")
        ab = caps.get("age_based")
        if ab is not None:
            if not isinstance(ab, dict):
                raise ValueError("match_caps.age_based must be a dict of {le55, 60to80, ge85}")
            for band in _CAP_BANDS:
                v = ab.get(band)
                if v is not None and not _pos_int(v):
                    raise ValueError(
                        f"match_caps.age_based.{band} must be a positive integer, got {v!r}")

    # ENG-1 (2026-08-02) — the three remaining rule blocks. All additive and all defaulted OFF, so
    # a doc omitting them produces today's schedule (the contract's own rule, §8 invariant 12).
    fe = doc.get("finals_earliest")
    if fe is not None and not (isinstance(fe, str) and _HHMM_RE.match(fe)):
        raise ValueError(f"finals_earliest must be an 'HH:MM' string, got {fe!r}")

    shape = doc.get("day_shape")
    if shape is not None:
        if not isinstance(shape, dict):
            raise ValueError("day_shape must be a dict")
        order = shape.get("order")
        if order is not None:
            if not isinstance(order, list) or any(k not in _KINDS for k in order):
                raise ValueError(
                    f"day_shape.order must be a list drawn from {list(_KINDS)}, got {order!r}")
            if len(set(order)) != len(order):
                raise ValueError(f"day_shape.order must not repeat a kind, got {order!r}")
        ons = shape.get("on_no_slot")
        if ons is not None and ons != "place_and_record":
            raise ValueError(
                f"day_shape.on_no_slot is 'place_and_record' and has no second value — "
                f"0-unplaced is never traded away (ruling 73); got {ons!r}")

    bands = doc.get("day_bands")
    if bands is not None:
        if not isinstance(bands, dict):
            raise ValueError("day_bands must be a dict")
        for key in ("singles_by", "mixed_at", "doubles_from"):
            v = bands.get(key)
            if v is not None and not (isinstance(v, str) and _HHMM_RE.match(v)):
                raise ValueError(f"day_bands.{key} must be an 'HH:MM' string, got {v!r}")
        scope = bands.get("scope")
        if scope is not None and scope not in ("triple_days", "all_days"):
            raise ValueError(
                f"day_bands.scope must be 'triple_days' or 'all_days', got {scope!r}")

    # VENUE-1 (2026-08-05) — the venue rules block. Every key optional; a present key must be
    # well-typed. Loud failure, because a mistyped rule here is a rule that silently does nothing.
    venue = doc.get("venue_rules")
    if venue is not None:
        if not isinstance(venue, dict):
            raise ValueError("venue_rules must be a dict")
        ages = venue.get("main_site_ages")
        if ages is not None:
            if not isinstance(ages, list) or not ages or not all(_pos_int(a) for a in ages):
                raise ValueError(
                    f"venue_rules.main_site_ages must be a non-empty list of age brackets "
                    f"(e.g. [80, 85, 90]), got {ages!r}")
        # BUDGET-1 (R19, Operator 2026-08-22, OI-B1): rule 31's `l1_mixed_lights_off` was
        # REPLACED by `l1_mixed_latest_start`, not joined by it — 14:00 is stricter than any
        # venue's lights-on hour, so the old test could never fire on a match the new one had not
        # already caught.
        #
        # IT IS MIGRATED, NOT REFUSED, AND THAT WAS A CORRECTION. The first cut raised on the
        # retired key, on this block's own principle that a rule silently doing nothing is worse
        # than a loud failure. That principle is right and it earned its keep immediately — it
        # caught the Setup console still EMITTING the retired key on both lanes, which would have
        # meant the console producing documents the engine rejects.
        #
        # But it went too far. The courier workflow's whole shape is that the director KEEPS the
        # JSON he couriered and replays it; the repo commits real examples of exactly that
        # (`reference/product/WWTC_2026_courier_blocks_20260807.md` and its run-2 sibling, which
        # six harnesses replay). Refusing the old key made every document this product has ever
        # emitted unbuildable, which is a compatibility break no ruling asked for, and the only
        # ways to a green suite were to rewrite committed records of real runs — falsifying
        # history — or to leave the director's saved work broken.
        #
        # So the key is ACCEPTED and TRANSLATED to the rule that replaced it, and the migration is
        # RECORDED on the config rather than performed in silence. Nothing does nothing: an old
        # doc gets the new rule, and it can say so. A doc carrying BOTH keys keeps the new one —
        # it was written after the change and the explicit value is the author's intent.
        if "l1_mixed_lights_off" in venue:
            v = venue["l1_mixed_lights_off"]
            if v is not None and not isinstance(v, bool):
                raise ValueError(
                    f"venue_rules.l1_mixed_lights_off must be true or false, got {v!r}")
        for flag in ("main_site_finals", "main_site_l1_mixed", "rank_order"):
            v = venue.get(flag)
            if v is not None and not isinstance(v, bool):
                raise ValueError(f"venue_rules.{flag} must be true or false, got {v!r}")
        latest = venue.get("l1_mixed_latest_start")
        if latest is not None and not (isinstance(latest, str) and _HHMM_RE.match(latest)):
            raise ValueError(
                f"venue_rules.l1_mixed_latest_start must be an 'HH:MM' string (e.g. '14:00'), "
                f"got {latest!r}")
        pw = venue.get("peak_window")
        if pw is not None:
            if not isinstance(pw, dict):
                raise ValueError("venue_rules.peak_window must be a dict")
            for key in ("start", "end"):
                v = pw.get(key)
                if v is not None and not (isinstance(v, str) and _HHMM_RE.match(v)):
                    raise ValueError(
                        f"venue_rules.peak_window.{key} must be an 'HH:MM' string, got {v!r}")
            if pw.get("start") and pw.get("end") and pw["start"] >= pw["end"]:
                raise ValueError(
                    f"venue_rules.peak_window must start before it ends, got "
                    f"{pw['start']}-{pw['end']}")
            mx = pw.get("max_starts")
            if mx is not None and not _pos_int(mx):
                raise ValueError(
                    f"venue_rules.peak_window.max_starts must be a positive integer, got {mx!r}")

    sdf = doc.get("same_day_finish")
    if sdf is not None:
        if not isinstance(sdf, dict):
            raise ValueError("same_day_finish must be a dict")
        divs = sdf.get("divisions")
        if divs is not None:
            if not isinstance(divs, list):
                raise ValueError("same_day_finish.divisions must be a list of division names")
            for d in divs:
                if not isinstance(d, str) or not d.strip():
                    raise ValueError(
                        f"same_day_finish.divisions entries must be non-empty division "
                        f"names — the TD names them, they are never inferred; got {d!r}")
        gap = sdf.get("gap_minutes")
        if "gap_minutes" in sdf and gap is None:
            raise ValueError(
                "same_day_finish.gap_minutes must be a positive integer, got null — omit the key "
                "to take the default of 150 rather than nulling it")
        if gap is not None and not _pos_int(gap):
            raise ValueError(f"same_day_finish.gap_minutes must be a positive integer, got {gap!r}")

    # DIV-1 / rule 45: which Mixed ages the TD sanctioned at Level 1. Reg IV.C draws Level 2
    # from the SAME division list as Level 1, so this is a property of HIS sanction that year
    # and is never hardcodable. Same shape as `same_day_finish` above, for the same reason: the
    # Setup console runs BEFORE the draws are read, so it cannot offer a list and the TD names
    # divisions in free text. Omitted or blank = the pipeline derives the split from which
    # draws file each division was printed in, and says so (`_resolve_mixed_level_1`).
    # Validated rather than merely tolerated — an unvalidated key is how a typo becomes a
    # silent mis-sort. DISPLAY ONLY: nothing here reaches placement.
    mx = doc.get("mixed_level_1")
    if mx is not None:
        if not isinstance(mx, dict):
            raise ValueError("mixed_level_1 must be a dict")
        divs = mx.get("divisions")
        if divs is not None:
            if not isinstance(divs, list):
                raise ValueError("mixed_level_1.divisions must be a list of division names")
            for d in divs:
                if not isinstance(d, str) or not d.strip():
                    raise ValueError(
                        f"mixed_level_1.divisions entries must be non-empty division names — "
                        f"the TD names them, they are never inferred; got {d!r}")

    s2s = doc.get("min_start_to_start_minutes")
    if s2s is not None and (not isinstance(s2s, int) or isinstance(s2s, bool) or s2s <= 0):
        raise ValueError(f"min_start_to_start_minutes must be a positive integer, got {s2s!r}")

    policy = doc.get("placement_policy")
    if policy is not None:
        if not isinstance(policy, dict):
            raise ValueError("placement_policy must be a dict")
        for retired in ("local_late", "local_multidiv_tiebreak"):
            if retired in policy:
                raise ValueError(
                    f"placement_policy.{retired} was RETIRED by LOCALS-EARLY (2026-07-25): "
                    "locals now stage EARLY within their tier (travel time goes to non-locals) and "
                    "the local-vs-multidivision tiebreak is moot — use locals_early: true")
        for flag in ("stage_multidivision_early", "locals_early"):
            if flag in policy and not isinstance(policy[flag], bool):
                raise ValueError(f"placement_policy.{flag} must be a boolean, got {policy[flag]!r}")

    age_rules = doc.get("earliest_start_by_age")
    if age_rules is not None:
        if not isinstance(age_rules, list):
            raise ValueError("earliest_start_by_age must be a list")
        for r in age_rules:
            if not isinstance(r, dict):
                raise ValueError("earliest_start_by_age entries must be dicts")
            am = r.get("age_min")
            if not isinstance(am, int) or isinstance(am, bool) or am <= 0:
                raise ValueError(f"earliest_start_by_age.age_min must be a positive int, got {am!r}")
            e = r.get("earliest")
            if not isinstance(e, str) or not _HHMM_RE.match(e):
                raise ValueError(f"earliest_start_by_age.earliest must be 'HH:MM', got {e!r}")

    locality = doc.get("locality")
    if locality is not None:
        if not isinstance(locality, dict):
            raise ValueError("locality must be a dict")
        # Real-export basis: home_cities (list of names) + home_section (a section name).
        # CUI-3: `commuter_cities` mirrors `home_cities` one-for-one — same shape, same validation.
        # The asymmetry is deliberate: home_cities reaches the engine (LOCALS-EARLY staging),
        # commuter_cities is DISPLAY-ONLY and no engine path reads it.
        for key in ("home_cities", "commuter_cities"):
            cities = locality.get(key)
            if cities is None:
                continue
            if not isinstance(cities, list):
                raise ValueError(f"locality.{key} must be a list")
            for c in cities:
                if not isinstance(c, str) or c.strip() == "":
                    raise ValueError(f"locality.{key} entries must be non-empty strings, got {c!r}")
        # A city in BOTH tiers is ambiguous — it cannot be both local and commuting. Compared
        # through the same `_norm` the matcher uses, so "palm  desert" and "Palm Desert" collide.
        home_norm = {_norm(c): c for c in (locality.get("home_cities") or [])}
        both = sorted({home_norm[_norm(c)] for c in (locality.get("commuter_cities") or [])
                       if _norm(c) in home_norm})
        if both:
            # Reported as the TD spelled it in home_cities, not as the folded key — a message
            # naming "indio" would send the reader looking for a city they never typed.
            raise ValueError(
                f"locality: {len(both)} city/cities appear in BOTH home_cities and "
                f"commuter_cities, which is ambiguous — {', '.join(both)}")
        section = locality.get("home_section")
        if section is not None and not isinstance(section, str):
            raise ValueError(f"locality.home_section must be a string, got {section!r}")  # "" = off
        # Loud on a deleted key, never silent — the LOCALS-EARLY precedent. A doc whose locality is
        # expressed ONLY as home_zips would otherwise validate clean, derive an empty local set,
        # and switch LOCALS-EARLY off for the whole field with no error anywhere.
        for dead in ("home_zips", "home_prefixes"):
            if dead in locality:
                raise ValueError(_RETIRED[f"locality.{dead}"])
        # ENG-1 (OI-37 b2): the legacy exact-zip allowlist — `home_zips` / `home_prefixes`, their
        # validation, `local_players_from_zips` and the `apply_constraints(roster_zips=...)` path —
        # was DELETED here, not deprecated. The real WWTC export carries no zip column, so the
        # branch never ran on a real field; `local_players_from_locality` is the one shipped matcher.


def _norm(s):
    """Casefold + collapse whitespace, for city/section membership (deterministic)."""
    return " ".join(str(s or "").split()).casefold()


def local_players_from_locality(roster_meta: dict, home_cities=None, home_section=None,
                                home_zips=None) -> set:
    """Deterministic locality for the **real export** (which carries no zip): a player is local if
    their **city is in the home-city set** OR their **section equals the home section** OR (legacy)
    their zip is in `home_zips`. `roster_meta` maps name -> {"city","section","zip"}. Any provided
    basis contributes (OR); an absent basis is simply inert. Pure function -> determinism preserved.

    City is the recommended basis (the venue's Coachella Valley cluster); section is offered because
    AVOID-2 speaks of "same city and/or section", but section alone is coarse (one section can be
    ~half the field), so it is opt-in, not the default."""
    hc = {_norm(c) for c in (home_cities or []) if str(c).strip()}
    hs = _norm(home_section) if home_section else None
    hz = {str(z).strip()[:5] for z in (home_zips or []) if str(z).strip()}
    local = set()
    for name, meta in (roster_meta or {}).items():
        meta = meta or {}
        city = _norm(meta.get("city"))
        section = _norm(meta.get("section"))
        zc = str(meta.get("zip") or "").strip()[:5]
        if (city and city in hc) or (hs and section and section == hs) or (zc and zc in hz):
            local.add(name)
    return local


def apply_constraints(cfg: MultiConfig, doc, roster_meta=None) -> MultiConfig:
    """Layer a validated td-constraints/v1 onto an existing MultiConfig (built from the
    slate). Sets the rest override (if given), **the match block length (if given)**,
    **the per-(division, player, day) match cap**, **the four ENG-1 rule fields**, the
    placement policy, and the local-player set. Returns the same cfg (mutated) for chaining.
    An empty/default doc leaves placement off => byte-identical.

    Locality: when `roster_meta` (name -> {city,section,zip}) is supplied — the real-export path —
    the local set is derived from `home_cities`/`home_section`. Otherwise there is no basis to
    derive locality from and the local set is empty (the local rule is inert, not wrong).
    ENG-1 (OI-37 b2) removed the `roster_zips` parameter with the exact-zip branch it fed; no
    caller in the repo supplied it, and a parameter that is accepted and ignored is the
    presented-and-inactive defect class WIRE-1 spent a build removing."""
    validate_constraints(doc)

    if doc.get("min_start_to_start_minutes") is not None:
        cfg.min_start_to_start_minutes = doc["min_start_to_start_minutes"]

    # WIRE-1 (§15 decision 1, route i) — THE wiring point. `match_minutes` stops being a value the
    # bundle carries and becomes the engine's block length: every downstream figure (slot windows,
    # the capacity sweep, the end-of-day buffer, draw-sheet times, the CSV) already derives from
    # match END times, so stamping the spec here is the whole change.
    # OMITTED => untouched, which leaves wwtc_ingest's uniform 90 (:808) exactly as it was. That is
    # the contract's "an omitted field maps to today's behavior" rule, and it is what keeps a bare
    # or legacy doc byte-identical.
    if doc.get("match_minutes") is not None:
        for ev in cfg.events:
            ev.match_minutes = doc["match_minutes"]

    # ENG-1 (ruling 75) — the cap's wiring point, on WIRE-1's `match_minutes` pattern above.
    # `match_caps` stops being a value the bundle carries for the console to show and becomes the
    # per-(division, player, day) ceiling `scheduler_multi._scan` gates on (`caps`, :467) and
    # `validate_multi` mirrors (the MATCH CAP block, which already existed and was inert only
    # because the value was 6/4/3). OMITTED => untouched, so the intake's own `_cap_for` ladder
    # stands and a bare or legacy doc is byte-identical.
    caps = doc.get("match_caps")
    if caps is not None:
        mode = _caps_mode(caps)
        if mode == "flat":
            flat = caps.get("flat", 1)
            for ev in cfg.events:
                ev.max_matches_per_day = flat
        else:
            ladder = {**_CAP_LADDER, **{k: v for k, v in (caps.get("age_based") or {}).items()
                                        if v is not None}}
            for ev in cfg.events:
                ev.max_matches_per_day = ladder[_cap_band(_age(ev.name))]

    # ENG-1 — the three remaining rule blocks reach the engine here. Each maps an OMITTED field to
    # today's behavior: no finals floor, no day shape, no bands, the switch off everywhere.
    fe = doc.get("finals_earliest")
    if fe is not None:
        for ev in cfg.events:
            ev.finals_earliest = fe
    cfg.day_shape = dict(doc.get("day_shape") or {})
    cfg.day_bands = dict(doc.get("day_bands") or {})
    cfg.same_day_finish = dict(doc.get("same_day_finish") or {})
    # DIV-1 / rule 45: the RAW tick-box block, carried the way `same_day_finish` is. The
    # pipeline resolves it against the printed division list and parks the answer on
    # `cfg.mixed_level_1_resolved`; nothing in placement reads either one.
    cfg.mixed_level_1 = dict(doc.get("mixed_level_1") or {})

    # VENUE-1 (2026-08-05) — the venue rules (6/31/38/39/40/43) reach the engine here, on the same
    # omitted-field-means-today's-behavior contract as ENG-1's blocks above: no key, no rule.
    # Every one of them is a PREFERENCE with a recorded escape (rule 41) — none can refuse a
    # placement, so none can cost the 0-unplaced guarantee.
    cfg.venue_rules = dict(doc.get("venue_rules") or {})
    # BUDGET-1 (R19) — THE RETIRED-KEY MIGRATION, applied at the one place venue rules reach the
    # engine, so every caller gets it and no lane can miss it. See the long note in
    # `validate_constraints`. Performed on the CONFIG and never on the caller's document: the doc
    # may be a committed record of a real run, and a validator that edits its input would rewrite
    # the evidence it was handed.
    if "l1_mixed_lights_off" in cfg.venue_rules:
        was = cfg.venue_rules.pop("l1_mixed_lights_off")
        if was and "l1_mixed_latest_start" not in cfg.venue_rules:
            cfg.venue_rules["l1_mixed_latest_start"] = _L1_MIXED_LATEST_DEFAULT
            cfg.venue_rules_migrated = [
                f"venue_rules.l1_mixed_lights_off was retired at BUDGET-1 and this document "
                f"still carries it. Level 1 Mixed is now held to a clock time instead of the "
                f"venue's lights hour, so the rule has been read as "
                f"l1_mixed_latest_start={_L1_MIXED_LATEST_DEFAULT!r} — stricter than the test it "
                f"replaces, and venue-independent."]

    cfg.placement_policy = dict(doc.get("placement_policy") or {})

    # AVOID-3: per-division earliest-start floor by age bracket (e.g. 80+ -> 09:30). The highest
    # matching age_min wins; no matching rule -> None (no floor). Deterministic (static on names).
    age_rules = doc.get("earliest_start_by_age") or []
    for ev in cfg.events:
        a = _age(ev.name)
        best = None
        for r in age_rules:
            if a >= r["age_min"] and (best is None or r["age_min"] > best["age_min"]):
                best = r
        ev.earliest_start = best["earliest"] if best else None

    locality = doc.get("locality") or {}
    if roster_meta is not None:
        cfg.local_players = local_players_from_locality(
            roster_meta, locality.get("home_cities"), locality.get("home_section"))
    else:
        cfg.local_players = set()      # no roster metadata => no basis => the local rule is inert
    return cfg


if __name__ == "__main__":
    # Function-level smoke test (B-2: no runtime, no engine coupling beyond MultiConfig).
    from scheduler_multi import (EventSpec, Team, schedule_multi, _multidivision_players,
                                 _player_event_counts, _staging_rank)

    # validate: schema + type guards
    for bad in ({}, {"schema": "x"},
                {"schema": CONSTRAINTS_SCHEMA, "min_start_to_start_minutes": 0},
                {"schema": CONSTRAINTS_SCHEMA, "placement_policy": {"local_late": True}},       # retired
                {"schema": CONSTRAINTS_SCHEMA, "placement_policy": {"local_multidiv_tiebreak": "multidivision"}},  # retired
                {"schema": CONSTRAINTS_SCHEMA, "placement_policy": {"locals_early": "yes"}},    # type
                {"schema": CONSTRAINTS_SCHEMA, "locality": {"home_cities": [""]}}):
        try:
            validate_constraints(bad); raise AssertionError(f"expected reject: {bad}")
        except ValueError:
            pass
    validate_constraints({"schema": CONSTRAINTS_SCHEMA})  # empty is valid
    validate_constraints({"schema": CONSTRAINTS_SCHEMA, "locality": {"home_cities": ["Palm Desert"]}})

    # WIRE-1: every retired key raises, and the message names the ruling that removed it.
    for retired, cite in (("tournament", "WIRE-1"), ("min_rest_minutes", "D-2"),
                          ("rr_threshold", "D-2"), ("singles_before_doubles", "D-2"),
                          ("singles_day_ahead", "T-4")):
        try:
            validate_constraints({"schema": CONSTRAINTS_SCHEMA, retired: 1})
            raise AssertionError(f"retired key accepted: {retired}")
        except ValueError as ex:
            assert cite in str(ex), f"{retired} rejection must cite {cite}: {ex}"

    # WIRE-1: match_minutes is enum-capped (D-1) now that it binds placement.
    for good in _DURATIONS:
        validate_constraints({"schema": CONSTRAINTS_SCHEMA, "match_minutes": good})
    for bad in (105, 120, 45, 0, "90", True):
        try:
            validate_constraints({"schema": CONSTRAINTS_SCHEMA, "match_minutes": bad})
            raise AssertionError(f"match_minutes accepted out of range: {bad!r}")
        except ValueError:
            pass

    # WIRE-1/D-32: the pacing thresholds are type-checked here and consumed by FMAP-1, not here.
    validate_constraints({"schema": CONSTRAINTS_SCHEMA, "matches_per_day_target": 125,
                          "finals_per_day": {"singles": 9, "doubles": 4}})
    for bad in ({"matches_per_day_target": 0}, {"matches_per_day_target": "125"},
                {"finals_per_day": []}, {"finals_per_day": {"singles": 0}},
                {"finals_per_day": {"doubles": "4"}}):
        try:
            validate_constraints({"schema": CONSTRAINTS_SCHEMA, **bad})
            raise AssertionError(f"threshold accepted: {bad}")
        except ValueError:
            pass

    # ENG-1 (OI-37 b2): the exact-zip selftest block was deleted WITH its fixture. Deleting only
    # the assertion lines would have left an orphaned `zips` dict behind — the deletion unit is
    # fixture + calls + assertions together.

    # BP-2 staging tiers + LOCALS-EARLY. Al Ace is in THREE divisions and also local.
    evs = [EventSpec(name="Men's 65 Singles", fmt="round_robin",
                     teams=[Team("1", ["Al Ace"]), Team("2", ["Bo Bell"]), Team("3", ["Cy Cole"])]),
           EventSpec(name="Men's 65 Doubles", fmt="round_robin",
                     teams=[Team("A", ["Al Ace", "De Dunn"]), Team("B", ["Bo Bell", "Ed East"]),
                            Team("C", ["Cy Cole", "Fi Fox"])]),
           EventSpec(name="Mixed 65 Doubles", fmt="round_robin",
                     teams=[Team("M", ["Al Ace", "Gi Grey"]), Team("N", ["Bo Bell", "Ho Hall"]),
                            Team("O", ["Ky King", "Li Lott"])])]
    counts = _player_event_counts(evs)
    assert counts["Al Ace"] == 3 and counts["Cy Cole"] == 2, counts
    assert _multidivision_players(evs) == {"Al Ace", "Bo Bell", "Cy Cole"}, _multidivision_players(evs)
    cfg = MultiConfig(tournament_name="t", num_courts=2, dates=["2026-01-01"], events=evs,
                      placement_policy={"stage_multidivision_early": True, "locals_early": True},
                      local_players={"Al Ace", "Ky King"})   # Al Ace = 3-event AND local; Ky King = singles-only + local
    from scheduler_multi import Match
    m_al = Match(mid="x", event="Men's 65 Singles", rnd=1, label="", draw="rr",
                 precedence=0, match_minutes=90, recovery_minutes=60, humans={"Al Ace"})
    m_ky = Match(mid="y", event="Mixed 65 Doubles", rnd=1, label="", draw="rr",
                 precedence=0, match_minutes=90, recovery_minutes=60, humans={"Ky King", "Li Lott"})
    r_al, r_ky = _staging_rank(m_al, cfg, counts), _staging_rank(m_ky, cfg, counts)
    assert r_al == (0, 0), r_al   # 3-event -> earliest tier (0); all-local -> FRONT of the tier
    assert r_ky == (2, 1), r_ky   # singles-only tier (2); Li Lott travels -> team staged BACK of it
    assert r_al < r_ky            # the tier always wins: multi-division before singles-only
    assert _staging_rank(m_al, MultiConfig(tournament_name="t", num_courts=2, dates=["2026-01-01"],
                                           events=evs), counts) == (1, 0)   # no policy -> uniform

    # WIRE-1: apply_constraints STAMPS the block length onto every event — the wiring point.
    # Omitted => untouched, which is what keeps a bare or legacy doc byte-identical.
    cfg2 = MultiConfig(tournament_name="t", num_courts=2, dates=["2026-01-01"],
                       events=[EventSpec(name="Men's 65 Singles", fmt="round_robin",
                                         teams=[Team("1", ["Al Ace"]), Team("2", ["Bo Bell"])],
                                         match_minutes=90)])
    apply_constraints(cfg2, {"schema": CONSTRAINTS_SCHEMA, "match_minutes": 60})
    assert [e.match_minutes for e in cfg2.events] == [60], "match_minutes did not reach the events"
    apply_constraints(cfg2, {"schema": CONSTRAINTS_SCHEMA})          # omitted => leave it alone
    assert [e.match_minutes for e in cfg2.events] == [60], "an omitted match_minutes overwrote the event"

    print("constraints self-test OK")
