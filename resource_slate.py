"""Resource-slate intake (SCH-01a).

Defines the `td-resource-slate/v1` config-intake contract and maps a slate into the
existing `MultiConfig`. The slate is a self-contained, re-suppliable resource object
(identical schema pre-tournament and at replan) that later embeds unchanged as the
"current resource slate" field of the step-4 tournament-state model.

1a is additive and carries **location** through the engine but leaves it **inert**:
- Per-day courts are summed across all locations open that day into a flat pool
  (`courts_by_day`), so a single-location slate schedules byte-identical to today.
- A court->location layout is derived for labeling only (`MultiConfig.court_locations`);
  it does not affect placement.
- Per-location per-date hours in the slate were carried but inert through 1a-1c; as of OI-23
  they are load-bearing: `config_from_slate` fills `MultiConfig.location_hours` and the engine
  gates court/slot admissibility on them (`_court_open`). A location/date with no explicit
  window falls back to the tournament-wide `daily_start`/`daily_end` (byte-identical).
- `transit_minutes` is validated in 1a; as of 1b it is forwarded to the engine, which
  enforces it as inter-location transit gap in `_humans_ok` / `validate_multi`.
- **SLATE-1 (2026-07-30):** a location MAY carry `lit_courts` + `lights_on` ("HH:MM",
  both-or-neither). These are **validated here and carried no further** — they are not mapped
  into `MultiConfig`, so no placement decision can read them. Their consumer is the
  pre-publication reporter's late-day ceiling check (`RPT-1`/`CAP-SLATE`); lights are
  deliberately not a scheduling feature (the 2026-07-29 recut moved them out of the engine).

This module wraps the engine (like scheduler_flow.py); it does not live inside it.
"""

import re
from datetime import date

from scheduler_multi import MultiConfig

RESOURCE_SLATE_SCHEMA = "td-resource-slate/v1"

# Strict zero-padded 24-hour HH:MM (00:00-23:59). Deliberately stricter than strptime, which
# tolerates unpadded values like "9:5" — the exact string _court_open then fails to parse.
_HHMM_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _parse_hhmm(value):
    """Return minutes-since-midnight for a strict zero-padded 24-hour HH:MM string, or None
    if `value` is not exactly that format."""
    if not isinstance(value, str):
        return None
    m = _HHMM_RE.match(value)
    if not m:
        return None
    return int(m.group(1)) * 60 + int(m.group(2))

# Config defaults mirror MultiConfig so an omitted optional maps to today's behavior.
_DEFAULT_DAILY_START = "08:00"
_DEFAULT_DAILY_END = "18:00"
_DEFAULT_EOD_BUFFER = 45
_DEFAULT_MIN_REST = 60
_DEFAULT_S2S = 180   # R1: default start-to-start rest = 3h (TD's Wilson Classic rule)

_REQUIRED_TOP = ("schema", "tournament", "dates", "locations")

# Strict ISO calendar date, zero-padded. Same discipline as _HHMM_RE: the engine keys occupancy and
# every lookup on the exact date string, so a near-miss ("2026-1-3", "") is not a date, it is a key
# that silently matches nothing. The regex fixes the SHAPE; _is_date then checks the date is real,
# so "2026-02-30" is refused as a date rather than surviving to a confusing downstream message.
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _is_date(value) -> bool:
    """True iff `value` is a zero-padded YYYY-MM-DD string naming a real calendar date."""
    if not isinstance(value, str) or not _DATE_RE.match(value):
        return False
    try:
        date(int(value[0:4]), int(value[5:7]), int(value[8:10]))
    except ValueError:
        return False
    return True


def validate_slate(slate) -> None:
    """Raise ValueError on a malformed slate; return None if it is well-formed.

    Loud failure is the project principle: fail, do not silently drop. Checks:
      - it is a dict with schema == td-resource-slate/v1 and all required top-level keys;
      - dates is a non-empty list; locations is a non-empty list of {id, available};
      - location ids are unique; each available entry has a positive int court count;
      - every listed date has at least one open location;
      - every transit_minutes key is a sorted "A|B" pair of KNOWN location ids;
      - (OI-24) every non-empty per-location per-date start/end is valid zero-padded 24-hour
        HH:MM and, when both are present and well-formed, start < end. An empty/absent start
        or end stays valid (tournament-wide fallback). All hours offenders are itemized;
      - (SLATE-1) a location's optional `lit_courts` / `lights_on` pair is both-or-neither,
        with a positive-int count and a valid HH:MM time. Reject-only: neither reaches the engine;
      - (SLATE-1) every `available` key is a well-formed YYYY-MM-DD date AND is listed in `dates`.
        Both `courts_by_day` and `_court_layout` iterate `dates`, so a malformed or unlisted key is
        read by nothing and the day would disappear from the tournament silently.
    """
    if not isinstance(slate, dict):
        raise ValueError(f"resource slate must be a dict, got {type(slate).__name__}")
    if slate.get("schema") != RESOURCE_SLATE_SCHEMA:
        raise ValueError(
            f"resource slate schema must be {RESOURCE_SLATE_SCHEMA!r}, got {slate.get('schema')!r}")
    missing = [k for k in _REQUIRED_TOP if k not in slate]
    if missing:
        raise ValueError(f"resource slate missing required keys: {', '.join(missing)}")

    dates = slate["dates"]
    if not isinstance(dates, list) or not dates:
        raise ValueError("resource slate 'dates' must be a non-empty list")

    locations = slate["locations"]
    if not isinstance(locations, list) or not locations:
        raise ValueError("resource slate 'locations' must be a non-empty list")

    ids = []
    for loc in locations:
        if not isinstance(loc, dict) or "id" not in loc or "available" not in loc:
            raise ValueError("each location must be a dict with 'id' and 'available'")
        lid = loc["id"]
        if lid in ids:
            raise ValueError(f"duplicate location id: {lid!r}")
        ids.append(lid)
        avail = loc["available"]
        if not isinstance(avail, dict):
            raise ValueError(f"location {lid!r} 'available' must be a dict")
        for d, cell in avail.items():
            courts = (cell or {}).get("courts") if isinstance(cell, dict) else None
            if not isinstance(courts, int) or isinstance(courts, bool) or courts <= 0:
                raise ValueError(
                    f"location {lid!r} date {d}: 'courts' must be a positive integer, got {courts!r}")
            # R7-3 (V-5): optional intra-day step-up — both fields or neither.
            mcourts, muntil = cell.get("morning_courts"), cell.get("morning_until")
            if (mcourts is None) != (muntil is None):
                raise ValueError(
                    f"location {lid!r} date {d}: morning_courts and morning_until must be "
                    "supplied together (or both omitted)")
            if mcourts is not None:
                if not isinstance(mcourts, int) or isinstance(mcourts, bool) or mcourts <= 0:
                    raise ValueError(
                        f"location {lid!r} date {d}: 'morning_courts' must be a positive "
                        f"integer, got {mcourts!r}")
                import re as _re
                if not isinstance(muntil, str) or not _re.match(r"^\d{2}:\d{2}$", muntil):
                    raise ValueError(
                        f"location {lid!r} date {d}: 'morning_until' must be 'HH:MM', "
                        f"got {muntil!r}")

    # SLATE-1: per-venue lit-court figures. Optional (blank until the TD supplies them per venue),
    # both-or-neither, and deliberately NOT forwarded to MultiConfig — the engine must not gain a
    # lights behaviour by the back door. Same loud-at-ingest discipline as OI-24's hours guard.
    for loc in locations:
        lid = loc["id"]
        lit, lights_on = loc.get("lit_courts"), loc.get("lights_on")
        if (lit is None) != (lights_on is None):
            raise ValueError(
                f"location {lid!r}: lit_courts and lights_on must be supplied together "
                "(or both omitted)")
        if lit is not None:
            if not isinstance(lit, int) or isinstance(lit, bool) or lit <= 0:
                raise ValueError(
                    f"location {lid!r}: 'lit_courts' must be a positive integer, got {lit!r}")
            if _parse_hhmm(lights_on) is None:
                raise ValueError(
                    f"location {lid!r}: 'lights_on' must be valid 24-hour 'HH:MM', "
                    f"got {lights_on!r}")

    # SLATE-1 (2026-07-30 review): close the silent-drop hole. `courts_by_day` and `_court_layout`
    # both iterate `dates`, so an `available` key that is not a well-formed date, or is a date absent
    # from `dates`, is read by NOTHING — the day just vanishes from the tournament with no error.
    # Reproduced from the console: clearing a day's date emitted an "" key, every check passed, and a
    # 10-day tournament silently became 9. Reject-only, and no already-valid slate is newly refused
    # (the console emits `dates` as exactly the union of these keys).
    date_errors = []
    for loc in locations:
        lid = loc["id"]
        avail = loc["available"]
        if not isinstance(avail, dict):
            continue
        for d in avail:
            if not _is_date(d):
                date_errors.append(
                    f"location {lid!r}: {d!r} is not a valid YYYY-MM-DD date")
            elif d not in dates:
                date_errors.append(
                    f"location {lid!r}: date {d} is open but is not listed in 'dates', so nothing "
                    "would schedule on it")
    if date_errors:
        raise ValueError("resource slate has unusable dates:\n  " + "\n  ".join(date_errors))

    id_set = set(ids)
    for d in dates:
        if not any(d in loc["available"] for loc in locations):
            raise ValueError(f"listed date {d} has no open location")

    for key in slate.get("transit_minutes", {}):
        parts = key.split("|")
        if len(parts) != 2 or any(p not in id_set for p in parts):
            raise ValueError(f"transit_minutes key {key!r} references an unknown location id")

    # R1: start-to-start rest minutes, when present, must be a positive integer.
    s2s = slate.get("min_start_to_start_minutes")
    if s2s is not None and (not isinstance(s2s, int) or isinstance(s2s, bool) or s2s <= 0):
        raise ValueError(
            f"min_start_to_start_minutes must be a positive integer, got {s2s!r}")

    # OI-24: hours-format crash-guard. OI-23 made per-location per-date hours load-bearing
    # (_court_open parses each window with strptime at placement time), so a malformed HH:MM now
    # raises mid-schedule. Reject it loudly at ingest instead. Reject-only and additive: a blank
    # (empty/absent) start or end stays valid and falls through to the tournament-wide window, and
    # no already-valid window is newly rejected. Collect every offender rather than raising on the
    # first (itemizing location id + date + field), matching the loud multi-error style.
    time_errors = []
    for loc in locations:
        lid = loc["id"]
        avail = loc["available"]
        if not isinstance(avail, dict):
            continue
        for d, cell in avail.items():
            if not isinstance(cell, dict):
                continue
            start, end = cell.get("start"), cell.get("end")
            smin = emin = None
            for field, val in (("start", start), ("end", end)):
                if val is None or val == "":
                    continue                      # blank window -> tournament-wide fallback
                parsed = _parse_hhmm(val)
                if parsed is None:
                    time_errors.append(
                        f"location {lid!r} date {d}: {field} {val!r} is not valid 24-hour HH:MM")
                elif field == "start":
                    smin = parsed
                else:
                    emin = parsed
            if smin is not None and emin is not None and smin >= emin:
                time_errors.append(
                    f"location {lid!r} date {d}: start {start!r} must be before end {end!r}")
    if time_errors:
        raise ValueError("resource slate has invalid hours:\n  " + "\n  ".join(time_errors))


def _court_layout(slate) -> dict:
    """Deterministic court->location layout: for each date, assign contiguous 1-based
    court ranges to the open locations in the slate's `locations` order.
    Returns date -> [(lo_court, hi_court, location_id)]. Labeling only (inert in 1a)."""
    layout = {}
    for d in slate["dates"]:
        ranges = []
        cursor = 1
        for loc in slate["locations"]:
            cell = loc["available"].get(d)
            if not cell:
                continue
            n = cell["courts"]
            ranges.append((cursor, cursor + n - 1, loc["id"]))
            cursor += n
        layout[d] = ranges
    return layout


def ceilings_from_slate(slate) -> dict:
    """BUDGET-1 §3.3 (R5): each club's PHYSICAL court ceiling — `{location id: courts}` — read off
    the optional `locations[].physical_courts` the Setup console's **Max Courts** control emits.

    THE READER HALF ONLY. SETUP-3 shipped the input (2026-08-21) and `setup_console_golden` part S
    already asserts the emit on both console lanes; this is the side that gives the number a
    consumer. `court_budget` is that consumer and the only one: PLACEMENT NEVER SEES THIS. The
    number is what a club physically owns, not what the director has booked — `available[d]
    ["courts"]` is what is booked and is the only figure the engine schedules against — so
    `config_from_slate` deliberately does not carry it onto the config at all.

    Why it exists: "you're out of room here" and "book more courts here" are different answers and
    the director acts on them differently (R5). Without a ceiling the search can only ever say the
    second, and would happily recommend a 30th court at a 24-court club.

    Absent ⇒ `{}`, which is what makes the field additive: a slate with no ceilings produces no
    ceilings, and every downstream reader sees exactly what it saw before the field existed.
    Locations are read in slate order; a non-integer or non-positive value is skipped rather than
    raised on, because `validate_slate` owns the shape and this is a projection, not a gate."""
    out = {}
    for loc in (slate or {}).get("locations", []) or []:
        n = loc.get("physical_courts")
        if isinstance(n, int) and not isinstance(n, bool) and n > 0:
            out[loc["id"]] = n
    return out


def config_from_slate(slate, events) -> MultiConfig:
    """Map a validated td-resource-slate/v1 into a MultiConfig, joining the slate's
    resources with an `events` list (e.g. from serve_tennis_intake.load_export).

    Does not mutate the slate (so it can embed unchanged in the step-4 state model).
    Per-day courts are summed across open locations into a flat pool; num_courts is the
    minimum daily total (reproduces today's global fallback for the byte-identical gate).
    """
    validate_slate(slate)

    dates = list(slate["dates"])
    courts_by_day = {}
    for d in dates:
        courts_by_day[d] = sum(
            loc["available"][d]["courts"] for loc in slate["locations"] if d in loc["available"])

    # OI-23: make the already-collected per-location per-date hours load-bearing. Key by
    # location id and the SAME date string the engine schedules on (cfg.dates / the slot's
    # `day`), so _court_open's cfg.location_hours[loc][day] lookup matches. Populate only when
    # BOTH start and end are present & non-empty; an omitted/blank window falls through to the
    # tournament-wide daily_start/daily_end (byte-identical). Does not mutate the slate.
    location_hours: dict = {}
    for loc in slate["locations"]:
        for d, cell in loc["available"].items():
            if not isinstance(cell, dict):
                continue
            start, end = cell.get("start"), cell.get("end")
            if start and end:
                location_hours.setdefault(loc["id"], {})[d] = (start, end)

    # R7-3 (V-5): intra-day court step-up — (loc, date) -> (switch "HH:MM", morning courts).
    # Absent fields => empty dict => the engine's flat caps (byte-identical).
    morning_caps: dict = {}
    for loc in slate["locations"]:
        for d, cell in loc["available"].items():
            if isinstance(cell, dict) and cell.get("morning_courts") is not None:
                morning_caps[(loc["id"], d)] = (cell["morning_until"], cell["morning_courts"])

    # VENUE-1 (2026-08-05): the director's display names, id -> name. Optional, and carried only
    # when he has typed one. REPORTED, NEVER SCHEDULED — nothing in placement keys on a name; the
    # id stays the load-bearing venue identity everywhere (D-49 corrected the NAMES, not the ids).
    venue_names = {loc["id"]: loc["name"] for loc in slate["locations"]
                   if isinstance(loc.get("name"), str) and loc["name"].strip()}

    # VENUE-1 / rule 43: THE FILL ORDER IS THE `locations` ARRAY ORDER, and always has been —
    # `_court_layout` above lays each date's court ranges out in exactly this order, and the
    # engine's `_scan_locations` filters that order without ever re-sorting it. The contract
    # question the brief left open (§7.2) is therefore settled by measurement rather than by a
    # new key: ranking a venue IS moving it up this array, and NO `rank` field is added. The
    # rank-1 venue — `locations[0]` — is the "main site" rules 38/39/40 are written against, so
    # "main site" is a position in the director's own list and never the literal string `MHCC`.
    venue_order = [loc["id"] for loc in slate["locations"]]

    # VENUE-1 / rule 31: the venue's LIGHTS-ON HOUR. Rule 31 wants only this — the time after
    # which a Level-1 Mixed match would be finishing under lights, which is a CUTOFF, not a
    # resource — and it still reads nothing else.
    #
    # LIGHTS-1 (2026-08-08) / rule 48 RETIRES THE OTHER HALF OF THIS BOUNDARY. SLATE-1's 2026-07-29
    # recut said the COUNT would never be mapped, so that no run could book more matches into a
    # venue because it happens to have floodlights. That reasoning held only in the direction it
    # was written: `lit_courts` is a CEILING, and mapping it can only ever take capacity away.
    # Unmapped, it did the harm the recut meant to prevent, in reverse — the engine built evening
    # boards with more concurrent matches than the venue has lighted courts, the report condemned
    # them on every run, and the director had no lever short of mis-stating his own lit count.
    # The count is now mapped, and it is a REDUCTION only: after `lights_on` a venue-day's usable
    # courts are `min(courts, lit_courts)`, the mirror image of the `morning_caps` step-up. It
    # adds capacity nowhere, which is the sentence the old comment was really protecting.
    venue_lights_on = {loc["id"]: loc["lights_on"] for loc in slate["locations"]
                       if isinstance(loc.get("lights_on"), str) and loc["lights_on"].strip()}
    # Both-or-neither is already enforced at ingest (`validate_slate` above), so a count is
    # carried only when its hour is carried too — a count with no hour would be a ceiling with
    # no time to start at, and inventing an hour would take courts away on the director's word
    # for something he never said.
    venue_lit_courts = {loc["id"]: loc["lit_courts"] for loc in slate["locations"]
                        if isinstance(loc.get("lit_courts"), int)
                        and not isinstance(loc.get("lit_courts"), bool)
                        and loc["id"] in venue_lights_on}

    return MultiConfig(
        tournament_name=slate["tournament"],
        num_courts=min(courts_by_day.values()),
        dates=dates,
        events=events,
        daily_start=slate.get("daily_start", _DEFAULT_DAILY_START),
        daily_end=slate.get("daily_end", _DEFAULT_DAILY_END),
        end_of_day_buffer_minutes=slate.get("end_of_day_buffer_minutes", _DEFAULT_EOD_BUFFER),
        global_recovery_minutes=slate.get("min_rest_minutes", _DEFAULT_MIN_REST),
        min_start_to_start_minutes=slate.get("min_start_to_start_minutes", _DEFAULT_S2S),   # R1
        courts_by_day=courts_by_day,
        court_locations=_court_layout(slate),
        transit_minutes=dict(slate.get("transit_minutes", {})),   # SCH-01b: now enforced by _humans_ok
        location_hours=location_hours,   # OI-23: now enforced by _location_open in _scan_locations
        morning_caps=morning_caps,       # R7-3: time-of-day-aware capacity (V-5 step-up)
        venue_names=venue_names,         # VENUE-1: id -> the TD's display name; reported, never scheduled
        venue_order=venue_order,         # VENUE-1 / rule 43: the fill order, == the slate's array order
        venue_lights_on=venue_lights_on,  # VENUE-1 / rule 31: the hour after which lights are on
        venue_lit_courts=venue_lit_courts,  # LIGHTS-1 / rule 48: the COUNT, a ceiling from that hour
    )
