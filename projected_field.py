"""S-2 — the projected field: last season's draws stand in, only the NEW divisions are built.

WHAT THIS IS FOR. The September publish run prices and announces a tournament that has not
happened yet. It needs a field. Until this module, the only thing producing one was
`reference/product/budget1_projected_field_20260822.py` — committed scaffolding whose header
said "when that product piece exists, DELETE THIS", which fabricated all 56 divisions from
scratch, monkey-patched five call sites at runtime, and needed a source edit at six constants
for every new year. This is that product piece. The point is not a better 2026 field; the
point is that 2027 arrives with no answer key and the run still works.

THE SHAPE (Operator, 2026-08-23 — not open):
  1. Last season's draws stand in UNCHANGED for every returning division. Not regenerated,
     not re-drawn, not re-membered. They are the real thing, so their distribution is correct
     by definition and free.
  2. Only NEW divisions are fabricated, at the director's estimated sizes.
  3. The new set is found BY DIFFERENCE against last season's draws, never by a hardcoded
     list. The list this replaced named five and the true set is six — `Men's 45 & over
     doubles` is a Level 2 addition it never flagged. A measured remainder cannot go stale.
  4. The step emits a matched player-list-AND-draws pair, so the accounting surfaces answer
     honestly instead of being stubbed quiet.

THE DRAFT RULE IS LEAST-ENTERED-FIRST, AND IT WAS SETTLED BY MEASUREMENT, NOT TASTE
(brief §7.3's properties; risk 3). Three rules were simulated against last season's committed
field at this build's HEAD. The discriminator is whether the three-event bucket is a TAIL or a
SHOULDER — the 3-event-to-2-event ratio, which reads 0.14 on the real field and 0.94 on the
scaffolding whose defect it catches:

    rule                  people   per person   3-event   3/2 ratio
    real draws (target)      721        1.479     5.13%     0.14
    least-entered first      741        1.563     4.99%     0.11   <-- this one
    rotating cursor          729        1.588     9.47%     0.25
    cap at 3 entries         729        1.588    10.43%     0.27   <-- ruled out

Cap-at-3 is ruled out by the bar itself: an entry ceiling that enough of the field can reach
piles up against it, which is the scaffolding's own defect in miniature. Least-entered-first
never creates a third entry while any eligible person still has fewer, so the three-event
bucket stays a tail BY CONSTRUCTION rather than by luck.

⚠ EVENTS PER DRAWN PERSON IS REPORTED, NEVER TARGETED (Operator ruling, 2026-08-24). Adding
92 member slots to a fixed roster bounds it to [1.424, 1.606] and last season's own 1.479 sits
INSIDE that band, so the mean cannot detect a defect and no player is ever invented to make an
average come out right.

⚠ INVENTED NAMES APPEAR ONLY WHERE THE ROSTER IS GENUINELY EXHAUSTED. On last season's bench
that is exactly six slots: Mixed 85 needs five women and the roster holds two, Mixed 90 needs
three and holds none. When the director adds a division older than his field currently reaches,
last season's roster cannot supply it — that is a fact about his tournament, not a defect, and
the report says it out loud per division.

R18 and R-B2 still bind: a fabricated bracket serves the planning run only and never reaches a
deliverable.
"""
import collections
import contextlib
import copy
import dataclasses
import re

import constraints
import draws_pdf
import field_source
import wwtc_ingest

# The new optional top-level key on `td-setup/v1` (contract decision 7.2, Operator 2026-08-24).
# The added divisions ride the ONE couriered block the setup console already emits — the
# director copies once and pastes once, exactly as in every run he has done.
ADDED_KEY = "added_divisions"

# The unit trap, carried in the field name itself. The director's numbers are TEAMS and bracket
# capacity, NEVER players: "Mixed 55 & over doubles: 14" is 14 teams = 28 people. Reading 14 as
# players sizes that division at half, and sizes the whole exercise at half.
_REQUIRED = ("name", "teams")
_OPTIONAL = ("level", "bracket", "format")
_FORMATS = ("single_elim", "round_robin")

_INVENTED_PREFIX = "Projected Entrant"


class ProjectedFieldError(ValueError):
    """A September run that cannot be built from what the director actually sent.

    ⚠ THIS EXISTS BECAUSE THE COURIERED BUNDLE TOLERATES UNKNOWN KEYS SILENTLY. `_check_setup`
    accepts any top-level key it does not recognise, which is what makes the additive contract
    cheap — and is also what would make a misspelled key invisible. If this module defaulted to
    "no added divisions" when the key was missing, a typo would price the director's tournament
    without the very divisions this module exists to carry, and nothing would object. That is
    the same silent-wrong-answer class as the four defects the scaffolding took to find. So an
    absent or unreadable key is REFUSED, loudly, and never assumed empty.
    """


def read_added_divisions(setup):
    """The director's added-division answers, off the one couriered `td-setup/v1` block.

    Returns a list of normalised dicts, possibly empty — an EMPTY LIST IS A VALID ANSWER and
    means "I am adding nothing this year". An ABSENT key is not: it is refused, because the
    module cannot tell "he added nothing" from "the key was misspelled or dropped in transit".
    """
    if not isinstance(setup, dict):
        raise ProjectedFieldError(
            f"a September projected field needs the couriered td-setup/v1 bundle, "
            f"got {type(setup).__name__}")
    if ADDED_KEY not in setup:
        near = [k for k in setup if isinstance(k, str) and _looks_like(k)]
        raise ProjectedFieldError(
            f"the couriered setup carries no {ADDED_KEY!r} key, so this run cannot tell "
            f"whether the director is adding no divisions or whether the answer was lost. "
            f"Answer the added-divisions section on the setup console and re-courier; if he "
            f"is adding none, that section still emits {ADDED_KEY!r} as an empty list."
            + (f" Did you mean {near[0]!r}?" if near else ""))
    raw = setup[ADDED_KEY]
    if not isinstance(raw, list):
        raise ProjectedFieldError(
            f"{ADDED_KEY!r} must be a list of added divisions, got {type(raw).__name__}")
    out = []
    for i, item in enumerate(raw):
        out.append(_normalise(item, i))
    names = [d["name"] for d in out]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise ProjectedFieldError(
            f"{ADDED_KEY!r} names the same division twice: {', '.join(dupes)}")
    return out


def _looks_like(key):
    k = key.lower().replace("-", "_").replace(" ", "_")
    return k != ADDED_KEY and ("division" in k or "added" in k or "projected" in k)


def _normalise(item, i):
    where = f"{ADDED_KEY}[{i}]"
    if not isinstance(item, dict):
        raise ProjectedFieldError(f"{where} must be an object, got {type(item).__name__}")
    for k in _REQUIRED:
        if k not in item:
            raise ProjectedFieldError(f"{where} is missing {k!r}")
    name = str(item["name"]).strip()
    if not name:
        raise ProjectedFieldError(f"{where} has an empty 'name'")
    teams = item["teams"]
    if isinstance(teams, bool) or not isinstance(teams, (int, float)) or int(teams) != teams:
        raise ProjectedFieldError(
            f"{where} 'teams' must be a whole number of TEAMS (a doubles pair is one team), "
            f"got {teams!r}")
    teams = int(teams)
    if teams < 2:
        raise ProjectedFieldError(f"{where} 'teams' must be at least 2, got {teams}")
    bracket = item.get("bracket")
    if bracket is not None:
        if isinstance(bracket, bool) or not isinstance(bracket, (int, float)) \
                or int(bracket) != bracket or bracket < 2:
            raise ProjectedFieldError(
                f"{where} 'bracket' must be a whole number of at least 2, got {bracket!r}")
        bracket = int(bracket)
    fmt = item.get("format")
    if fmt is not None:
        fmt = str(fmt).strip()
        if fmt not in _FORMATS:
            raise ProjectedFieldError(
                f"{where} 'format' must be one of {'/'.join(_FORMATS)}, got {fmt!r}")
    level = item.get("level")
    if level is not None:
        level = str(level).strip()
        if level not in ("1", "2"):
            raise ProjectedFieldError(f"{where} 'level' must be '1' or '2', got {level!r}")
    if not constraints._age(name):
        raise ProjectedFieldError(
            f"{where} name {name!r} carries no age bracket — the engine's division vocabulary "
            f"is \"Men's 45 & over doubles\" / \"Mixed 55 & over doubles\"")
    # A level the director did not state falls back to Level 2 — the general draw, where all
    # but the Mixed ladder lives. RECORDED in the report rather than assumed silently, so a
    # division that landed on the wrong side of the split is visible instead of inferred.
    return {"name": name, "teams": teams, "bracket": bracket, "format": fmt,
            "level": level or "2", "level_stated": level is not None}


# ---------------------------------------------------------------- the field, built

class ProjectedField:
    """The matched pair the September run is built from, plus its own accounting.

    `draws`   — {level: [DivisionDraw]}. Returning divisions are last season's, UNCHANGED;
                added divisions are fabricated at the director's stated sizes.
    `players` — {usta_id: Player}, last season's roster PLUS one record per invented name, so
                every name printed in the draws resolves. This is what makes the pair MATCHED,
                and it is why the accounting surfaces stop needing to be stubbed.
    `added` / `returning` — the two sets, the added one found by DIFFERENCE.
    `report`  — measured accounting, computed rather than asserted (ruling 12).

    `draws_for` / `players_for` are what the seam serves at the ingest boundary. They are
    PER LEVEL, deliberately: last season's level-1 roster is 118 people and level-2's is 725,
    and handing a level-1 read the whole union would reconcile 725 people against four
    divisions and report hundreds of them as entered-but-not-drawn.
    """

    def __init__(self, draws, players, by_level, invented, invented_level, added, returning,
                 report):
        self.draws = draws
        self.players = players
        self.invented = invented
        self.added = added
        self.returning = returning
        self.report = report
        self._by_level = by_level
        self._invented_level = invented_level

    def all_draws(self):
        return [d for lvl in sorted(self.draws) for d in self.draws[lvl]]

    def levels(self):
        return sorted(self.draws)

    def draws_for(self, level):
        """This level's projected draws. Deep-copied: consumers annotate what they are handed,
        and last season's returning divisions must survive a build unmarked."""
        return copy.deepcopy(self.draws.get(str(level), []))

    def players_for(self, level):
        """This level's served roster: its real people, everyone drafted into one of its added
        divisions, and the placeholders invented for them — each carrying the added division on
        their own entry record so the resolver has a candidate pool. See `_served_rosters`."""
        return dict(self._by_level.get(str(level), {}))


def build_projected_field(setup, levels=("1", "2"), td_path=None, st_path=None,
                          draws_path=None, season_year=None):
    """Build the projected field from the director's couriered answers.

    NOTHING HERE IS YEAR-SPECIFIC. Last season's draws and roster resolve through the same
    data-directory scan every other consumer uses (`draws_pdf.resolve_draws_pdf`,
    `wwtc_ingest.resolve_player_lists`, both env-overridable), and every fact about the coming
    season arrives in `setup`. A new year drops its files in and re-couriers; no source edit.
    """
    added = read_added_divisions(setup)
    year = season_year or season_year_of(setup)
    levels = tuple(str(l) for l in levels)

    last_draws = {lvl: draws_pdf.parse_draws(draws_path, level=lvl) for lvl in levels}
    returning = {d.event for lvl in levels for d in last_draws[lvl]}

    # ⚠ THE ADDED SET IS THE DIFFERENCE, NEVER THE DIRECTOR'S LABEL. If he names a division
    # that last season actually drew, last season's real draw stands in and his estimate is
    # ignored — that is rule 1 of the shape. Reported, never silent.
    ignored = [d for d in added if d["name"] in returning]
    to_build = [d for d in added if d["name"] not in returning]

    # Both shapes are needed and neither is derivable from the other: the DRAFT works off the
    # union (a person eligible for an added division is eligible whichever level they entered
    # at last season), while the SEAM serves per level, because that is the shape every
    # consumer of the boundary already expects.
    by_level = {lvl: wwtc_ingest.load_players(level=lvl) for lvl in levels}
    players = _union(by_level, levels)
    roster_size = len(players)

    # Last season's entry counts per person, from last season's own draws — resolved per level
    # against that level's own roster, exactly as the ingest does. This is the state
    # least-entered-first drafts against, so a person who already plays three divisions is the
    # last one the tool reaches for.
    entries, counted = collections.Counter(), set()
    for lvl in levels:
        by_div, _stats = wwtc_ingest.resolve_draws(last_draws[lvl], by_level[lvl])
        for div, res in by_div.items():
            for r in res:
                for pid in r.player_ids:
                    if pid in players and (pid, div) not in counted:
                        counted.add((pid, div))
                        entries[pid] += 1

    men, women = [], []
    for pid in sorted(players):
        p = players[pid]
        if not p.yob:
            continue
        g = (p.gender or "").upper()
        if g.startswith("M"):
            men.append(pid)
        elif g.startswith("F"):
            women.append(pid)

    built, invented_total, shortfall = [], 0, []
    invented, invented_level, drafted = {}, {}, {}
    for spec in sorted(to_build, key=lambda d: (-constraints._age(d["name"]), d["name"])):
        before = set(players)
        draw, n_inv, short, took = _fabricate(spec, players, entries, men, women, year,
                                              invented_total)
        for pid in set(players) - before:
            invented[pid] = players[pid]
            invented_level[pid] = spec["level"]
        drafted[spec["name"]] = (spec["level"], took)
        invented_total += n_inv
        if short:
            shortfall.append(short)
        built.append((spec, draw))

    out = {lvl: list(last_draws[lvl]) for lvl in levels}
    for spec, draw in built:
        out.setdefault(spec["level"], []).append(draw)

    served = _served_rosters(by_level, players, invented, invented_level, drafted, levels)
    report = _report(out, served, ignored, to_build, returning, roster_size,
                     invented_total, shortfall, levels, year)
    return ProjectedField(out, players, served, invented, invented_level, to_build,
                          sorted(returning), report)


def _union(by_level, levels):
    """One record per human across the levels — `wwtc_ingest.load_players_combined`'s merge,
    run over rosters already in hand.

    Not a second call to that function: it re-reads all four spreadsheets, which costs about a
    second on every build and produces exactly what the per-level loads above already hold. The
    semantics are its docstring's and must stay so — `events`, `entry_status` and
    `raw_td_by_division` UNION across levels (each level holds a real, non-overlapping part of
    them, and 84 people are entered at both); every scalar keeps the LAST level's value.
    """
    out = {}
    for lvl in levels:
        for uid, p in by_level.get(lvl, {}).items():
            prior = out.get(uid)
            if prior is not None:
                p = dataclasses.replace(
                    p,
                    events=wwtc_ingest._dedup(list(prior.events) + list(p.events)),
                    entry_status={**prior.entry_status, **p.entry_status},
                    raw_td_by_division={**prior.raw_td_by_division, **p.raw_td_by_division})
            out[uid] = p
    return out


def _served_rosters(by_level, union, invented, invented_level, drafted, levels):
    """The per-level player lists the seam serves — THE OTHER HALF OF THE MATCHED PAIR.

    ⚠ TWO THINGS HAVE TO BE TRUE HERE OR THE ADDED DIVISIONS QUIETLY BECOME BYES, and both were
    found by driving a real build rather than by reading the code:

    1. **The people have to be ON the level's list.** The draft works off the union, because
       someone eligible for a new division is eligible whichever level they entered at last
       season — but a level-1 read is served the level-1 list, which holds 118 of the roster's
       759 people. A person drafted into a level-1 added division out of the level-2 list would
       be a name in a draw with nobody on the list to be.
    2. **Their entry record has to SAY they entered the new division.** The resolver builds its
       candidate pool per division out of what each person entered; for a division nobody has
       ever entered that pool does not exist, and resolution falls back to scanning the whole
       roster by surname. Measured on a real build, that fallback resolved 54 of 97 entrants —
       the rest became byes, and a division of byes costs no courts. A projected entry is a real
       entry as far as the field is concerned, so it is written onto the person's record.

    Records are COPIED before the division is added. Mutating the shared roster would leak a
    projected entry into the union and across levels, and last season's returning divisions must
    resolve exactly as they do today.
    """
    served = {lvl: dict(by_level.get(lvl, {})) for lvl in levels}
    for division, (level, pids) in sorted(drafted.items()):
        roster = served.setdefault(level, {})
        for pid in pids:
            base = roster.get(pid) or union.get(pid)
            if base is None:
                continue
            roster[pid] = dataclasses.replace(
                base,
                events=_dedup_append(base.events, division),
                entry_status={**base.entry_status, division: None},
                raw_td_by_division=dict(base.raw_td_by_division))
    for pid, p in invented.items():
        served.setdefault(invented_level[pid], {})[pid] = p
    return served


def _dedup_append(events, division):
    out = list(events or [])
    if division not in out:
        out.append(division)
    return out


@contextlib.contextmanager
def serving(field):
    """Serve `field` from the ingest boundary for the span of the block — THE SEAM.

    Use this whenever the span fits in one piece of code:

        field = projected_field.build_projected_field(setup)
        with projected_field.serving(field):
            budget = wwtc_pipeline.court_budget(...)      # sees the projected field
            plan   = wwtc_pipeline.finals_plan(setup)     # sees it too

    ⚠ THE SPAN MATTERS. A September run ends at the announcement; nothing after it belongs
    inside, and no January run should ever enter one. The previous value is restored on the way
    out even when the body raises, which is why this is preferred wherever it fits.
    """
    prior = install(field)
    try:
        yield field
    finally:
        uninstall(prior)


def install(field):
    """Serve `field` from the ingest boundary until `uninstall` — for a GUIDED RUN, where the
    span is the run itself and cannot be a block.

    A guided September run is a sequence of turns with the Operator couriering between them, so
    Steps 2 through 3.6 are not one piece of code and no `with` can hold them. That is the case
    this exists for, and the runbook's Step 1.5 is its caller. Returns the previous value.

    ⚠ EVERYTHING AFTER THE ANNOUNCEMENT IS OUTSIDE IT. A September run ends at Step 3.6; a
    January run must never have it on, because January has the real field and reading estimated
    players there would be silent and wrong.
    """
    return field_source.install(field)


def uninstall(prior=None):
    """Stop serving the projected field, or restore what `install` returned."""
    field_source.uninstall(prior)


def season_year_of(setup):
    """The year the COMING tournament is played in, read off the couriered slate's own dates.

    Age eligibility is `>=` against a reference year, and that reference is the season being
    planned — a player born in 1937 is 89 at a January 2026 tournament and 90 at a January
    2027 one, which is the difference between eligible for the division the director is adding
    and not. The scaffolding this replaced carried the window as a source constant (`WINDOW`,
    `:36`) and so needed editing every year; the slate already carries the real dates, so the
    year is DERIVED and nothing here needs to know what year it is.

    ⚠ REFUSES rather than guessing. A September run always carries the coming January's real
    slate — that is the entire point of the run — so an unreadable one is a broken bundle, not
    a year to assume. Guessing here would quietly draft the wrong people into his new
    divisions, which is precisely the silent-wrong-answer class this module exists to end.
    """
    slate = (setup or {}).get("slate") if isinstance(setup, dict) else None
    dates = (slate or {}).get("dates") if isinstance(slate, dict) else None
    years = sorted({int(m.group(1)) for d in (dates or [])
                    for m in [re.match(r"\s*(\d{4})-\d{2}-\d{2}", str(d))] if m})
    if not years:
        raise ProjectedFieldError(
            "the couriered setup carries no readable slate dates, so the season being planned "
            "cannot be derived and age eligibility for the added divisions would be a guess. "
            "Courier the setup with its slate, or pass season_year= explicitly.")
    # A tournament that straddles New Year takes the year most of it falls in.
    counts = collections.Counter(int(str(d)[:4]) for d in dates if re.match(r"\s*\d{4}-", str(d)))
    return counts.most_common(1)[0][0]


def _fabricate(spec, players, entries, men, women, year, invented_so_far):
    """One added division, drafted least-entered-first off last season's roster."""
    name = spec["name"]
    age = constraints._age(name)
    doubles = wwtc_ingest._is_doubles(name)
    lower = name.lower()
    mixed = "mixed" in lower
    womens = lower.startswith("women")
    n_teams = spec["teams"]
    if spec["bracket"]:
        # OI-B7 (Operator, 2026-08-22): plan against the ENTRY COUNT, the stated draw size as
        # the CEILING. A bracket protects the runway and describes the field at once, and
        # reading it only the second way builds a tournament that does not exist.
        n_teams = min(n_teams, spec["bracket"])
    fmt = spec["format"] or ("round_robin" if n_teams <= 5 else "single_elim")
    if fmt == "round_robin":
        n_teams = max(3, n_teams)

    used, invented, dry = set(), [invented_so_far], collections.Counter()
    took = []

    def take(pool, tag):
        """Least-entered-first: the eligible person with the fewest entries so far, ties broken
        by usta_id so the draft is deterministic. A third entry is never created while any
        eligible person still has fewer, which is what keeps the three-event bucket a tail.

        Returns (full name, surname) — the printed draws write a doubles pair as SURNAMES
        joined by a bare slash ('Orta/Thu') and a singles entrant as a full name, so both are
        needed to build a draw the existing resolver can read.
        """
        best = None
        for pid in pool:
            if pid in used:
                continue
            if year - players[pid].yob < age:
                continue
            key = (entries[pid], pid)
            if best is None or key < best[0]:
                best = (key, pid)
        if best is None:
            # ⚠ THE ROSTER IS GENUINELY EXHAUSTED — the only place a name is ever invented.
            dry[tag] += 1
            invented[0] += 1
            return _invent(players, tag, invented[0], age, year, name)
        pid = best[1]
        used.add(pid)
        took.append(pid)
        entries[pid] += 1
        return players[pid].name, (players[pid].last or players[pid].name.split()[-1])

    teams = []
    for _ in range(n_teams):
        if mixed:
            team = [take(men, "M"), take(women, "W")]
        elif not doubles:
            team = [take(women if womens else men, "W" if womens else "M")]
        else:
            pool, tag = (women, "W") if womens else (men, "M")
            team = [take(pool, tag), take(pool, tag)]
        teams.append(team)

    draw = _draw_for(name, fmt, teams, doubles)
    short = None
    if dry:
        short = {"division": name, "invented": sum(dry.values()),
                 "men": dry.get("M", 0), "women": dry.get("W", 0)}
    return draw, invented[0] - invented_so_far, short, took


def _invent(players, tag, n, age, year, division):
    """A placeholder entrant, added to the player list so the pair stays MATCHED.

    The name is deliberately unmistakable on a printed page. R18 and R-B2 already confine a
    fabricated bracket to the planning run, and this is the belt to that brace: if one of these
    ever reaches a deliverable, it reads as what it is rather than as a person. It carries the
    division on its own entry record for the same reason a drafted person does — without that,
    the resolver has no candidate pool and the slot silently becomes a bye.
    """
    surname = f"Projected{tag}{n}"
    label = f"{_INVENTED_PREFIX} {tag}{n}"
    pid = f"PROJ-{tag}{n}"
    players[pid] = wwtc_ingest.Player(
        usta_id=pid, name=label, first=_INVENTED_PREFIX, last=surname,
        gender="M" if tag == "M" else "F", yob=(year - age) if year else None,
        events=[division], entry_status={division: None})
    return label, surname


def _display(team, doubles):
    """The printed form. Doubles print SURNAMES joined by a bare slash ('Orta/Thu'); a singles
    entrant prints a full name. Matching the printed form exactly is what lets the existing
    resolver read a fabricated draw with no special case."""
    return "/".join(t[1] for t in team) if doubles else team[0][0]


def _draw_for(name, fmt, teams, doubles):
    """A DivisionDraw in exactly the shape `draws_pdf.parse_draws` returns for a printed one."""
    def parts(team):
        return [t[1] for t in team] if doubles else [team[0][0]]

    if fmt == "round_robin":
        members = [draws_pdf.RRMember(display=_display(t, doubles), is_doubles=doubles,
                                      partners=parts(t))
                   for t in teams]
        return draws_pdf.DivisionDraw(event=name, fmt="round_robin",
                                      groups=[draws_pdf.Group(name="Group 1", members=members)])
    size = 1
    while size < max(len(teams), 2):
        size *= 2
    n_byes = size - len(teams)
    bye_at = set()
    if n_byes:
        step = size / n_byes
        bye_at = {int(i * step) for i in range(n_byes)}
        k = 0
        while len(bye_at) < n_byes:
            if k not in bye_at:
                bye_at.add(k)
            k += 1
    slots, ti = [], 0
    for k in range(size):
        if k in bye_at:
            slots.append(draws_pdf.Slot(pos=k + 1, display="BYE", is_bye=True,
                                        is_doubles=doubles))
        else:
            t = teams[ti]
            ti += 1
            slots.append(draws_pdf.Slot(pos=k + 1, display=_display(t, doubles),
                                        is_doubles=doubles, partners=parts(t)))
    return draws_pdf.DivisionDraw(event=name, fmt="single_elim", slots=slots)


def _report(draws, served, ignored, to_build, returning, roster_size, invented,
            shortfall, levels, year):
    """Measured accounting over the pair. Every figure computed here, never quoted forward.

    ⚠ IDENTITY IS RESOLVED, NEVER READ OFF THE PRINTED TEXT. A doubles slot prints 'Orta/Thu'
    and a singles slot prints a full name, so counting display strings would count printed
    blobs rather than people and would report a field of strangers each playing one event. The
    count goes through the same resolver every other consumer uses — and against exactly the
    roster the seam will serve for that level, so the report measures the field the run gets.
    """
    seen, per_person, unresolved = set(), collections.Counter(), 0
    for lvl in sorted(draws):
        players = served.get(lvl, {})
        by_div, stats = wwtc_ingest.resolve_draws(draws[lvl], players)
        unresolved += stats.get("unresolved", 0)
        for div, res in by_div.items():
            for r in res:
                for pid in r.player_ids:
                    if pid in players and (pid, div) not in seen:
                        seen.add((pid, div))
                        per_person[pid] += 1
    n = len(per_person) or 1
    buckets = collections.Counter(per_person.values())
    added_names = {a["name"] for a in to_build}
    added_slots = sum(len(_members(d)) for lvl in draws for d in draws[lvl]
                      if d.event in added_names)
    return {
        "divisions": sum(len(v) for v in draws.values()),
        "returning": len(returning),
        "added": len(to_build),
        "added_names": sorted(added_names),
        "ignored_because_returning": [a["name"] for a in ignored],
        "level_not_stated": sorted(a["name"] for a in to_build if not a["level_stated"]),
        "season_year": year,
        "roster": roster_size,
        "people": len(per_person),
        "entries": sum(per_person.values()),
        "events_per_drawn_person": sum(per_person.values()) / n,
        "buckets": {k: buckets.get(k, 0) for k in sorted(buckets)},
        "three_to_two_ratio": (buckets.get(3, 0) / buckets[2]) if buckets.get(2) else None,
        "added_slots": added_slots,
        "invented": invented,
        "real_share_of_added_slots": ((added_slots - invented) / added_slots)
                                     if added_slots else None,
        "roster_exhausted": shortfall,
        # ⚠ AN UNRESOLVED ENTRANT BECOMES A BYE, AND A DIVISION OF BYES COSTS NO COURTS. Carried
        # as a figure rather than a warning because that is the shape of the failure: never an
        # error, always a tournament that looks cheaper than it is.
        "unresolved_entrants": unresolved,
        "levels": list(levels),
    }


def _members(d):
    """Every non-bye member slot in a division, counted as PEOPLE — a doubles team is two."""
    if d.fmt == "single_elim":
        entries = [s for s in d.slots if not s.is_bye]
    else:
        entries = [m for g in d.groups for m in g.members]
    return [w for e in entries for w in (e.partners or [e.display])]
