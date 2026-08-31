"""Schedule views (read-only) — E2 / OI-20 output sheets.

Reorganize a generated schedule into the operational documents a TD posts,
without touching the engine. All three consume result["schedule"] (from
scheduler_multi.schedule_multi / scheduler_flow.finalize_multi) and return
plain data; the *_text helpers render a printable summary.

  order_of_play_by_division(result)  E2     -> matches per division, in play order
  run_of_play_by_court(result)       OI-20  -> per site/day/court sequence (courtside)
  schedule_by_player(result)         OI-20  -> each player's matches (player-facing)

CUI-5 (OI-20, D-24) adds the two printable sheets the desk actually posts, in the
house draw-sheet look (`draw_sheets.PALETTE`, same paper/green/print shell):

  render_run_of_play_html(rows, ...)  -> one sheet per site-day, matches by start
  render_by_player_html(rows, ...)    -> one block per player, CARD-1 side rendering

Byes carry no start time and never appear (they are not court matches). Nothing
in the engine imports this module; it only reads engine output.
"""
from collections import defaultdict
import datetime as _dt
import html as _html

import division_order as DO       # DIV-1: rule 44's one display order. This module only ever
                                 # reads engine output; the key does the same.


def _division_sort_key(div, mixed_level_1):
    """`None`-last, then rule 44's display order. A match carrying no event name still sorts,
    and still sorts last — that guard predates DIV-1 and is kept."""
    return (1, ()) if div is None else (0, DO.display_key(div, mixed_level_1))


# HOLDVIS-1 (ruling 1-3, 2026-08-07): the one phrase, on every surface. A match the TD holds off
# the schedule has no day, no start and no site — the line says so in words rather than printing
# three blanks or dropping the player's page altogether.
HELD_TEXT = "held — not scheduled"


def _division_depth(result):
    """`{division: the deepest round it actually plays}`, read off the result's own match record.

    ROUND-1 (2026-08-08): the schedule carries EVERY round of a division whether or not its
    players are decided — an undecided round-6 match sits in it with empty sides, waiting on its
    feeders. That is the fact the player handout was missing: `schedule_by_player` groups by
    NAMED player, so the deepest round it could see was the deepest round somebody was already
    known to be in, and `_round_label` counted back from there. Measured on the committed field
    before the fix: 1,008 of 1,164 handout lines named a round the division does not have, across
    699 of 721 players and 42 of 51 divisions, 315 of them telling a man he was in the FINAL
    while he played his first or second match.

    THE HELD MATCHES COUNT TOWARDS THE DEPTH, and this is the one place the ROUND-1 brief's §4.1
    is amended rather than followed to the letter — measured, not assumed. §4.1 says "from
    `result["schedule"]`", on the reasoning that a held match cannot reach the stamp. It cannot;
    but holding a match REMOVES it from `result["schedule"]`, so a schedule-only depth drops when
    the TD holds a division's final, and every remaining match in that division steps up a name —
    a quarterfinal starts printing "Semifinal". That is precisely the relabel HOLDVIS-1 shipped an
    invariant against, and `tests/holdvis1_visibility.py` Part B catches it: built to the letter,
    holding `E14-R6-M1` moved Men's 75 & over singles' ceiling from 6 to 5. A match the TD holds
    off the schedule is still a match the division has to play, so its round still counts here —
    the held descriptor carries the round, and with it the ceiling is unmoved. This changes no
    render on a build with no hold, and none on the run's own three (all round 1, under a
    ceiling of 6).
    """
    top = {}
    for e in list(result.get("schedule", [])) + list(result.get("held") or ()):
        rnd, ev = e.get("round"), e.get("event")
        if rnd is None:
            continue
        if ev not in top or rnd > top[ev]:
            top[ev] = rnd
    return top


def _match_row(e, division_rounds=None):
    row = {"day": e.get("day"), "start": e.get("start"), "end": e.get("end"),
           "court": e.get("court"), "event": e.get("event"),
           "match": e.get("match"), "players": e.get("players", [])}
    # ROUND-1: the division's true depth, carried the same additive way `location`, `sides` and
    # `held` are — present when the caller knows it, absent otherwise. The argument DEFAULTS to
    # nothing, so the two callers that group by court and by division emit exactly the dicts they
    # always emitted and render exactly the bytes they always rendered.
    if division_rounds is not None:
        row["division_rounds"] = division_rounds
    # HOLDVIS-1: the held marker rides the row the same additive way `location` and `sides` do —
    # present when the engine recorded a hold, absent otherwise, so a base build's rows are
    # exactly the dicts they always were.
    if e.get("held"):
        row["held"] = True
    if "location" in e:
        row["location"] = e["location"]
    # CUI-5 (OI-20): the sides, carried the same additive way `location` already is — present
    # when the engine emitted them, absent otherwise. CARD-1's side model is READ here, never
    # re-derived: a doubles partner is not an opponent, and the by-player handout has to say so.
    if e.get("team_a") is not None or e.get("team_b") is not None:
        row["sides"] = (list(e.get("team_a") or []), list(e.get("team_b") or []))
    if e.get("round") is not None:
        row["round"] = e["round"]
    if e.get("draw") is not None:
        row["draw"] = e["draw"]
    return row


# ---- E2 - order of play, by division ----------------------------------------
def order_of_play_by_division(result, mixed_level_1=()):
    """[{division, matches: [row, ... by day/start/court]}, ...] in the TD's division order.

    DIV-1 (rule 44): the divisions come out in the ONE display order — men's singles, women's
    singles, men's doubles, women's doubles, Mixed, youngest to oldest inside each — rather
    than alphabetically. The `None`-last guard is kept: a match with no event still sorts, and
    still sorts last.

    DIV-2 (2026-08-30): Mixed is ONE age-ordered block across sanction levels. `mixed_level_1`
    is still accepted — callers pass `build["mixed_level_1"]` — and is now IGNORED for
    ordering; passing it, passing `[]` and omitting it all give the same order.
    """
    by_div = defaultdict(list)
    for e in result.get("schedule", []):
        by_div[e.get("event")].append(e)
    out = []
    for div in sorted(by_div, key=lambda x: _division_sort_key(x, mixed_level_1)):
        rows = sorted(by_div[div],
                      key=lambda e: (e.get("day") or "", e.get("start") or "", e.get("court") or 0))
        out.append({"division": div, "matches": [_match_row(e) for e in rows]})
    return out


# ---- OI-20 - run of play, by court ------------------------------------------
def run_of_play_by_court(result):
    """[{location, day, court, matches: [row, ... by start]}, ...] — the courtside sheet."""
    by_court = defaultdict(list)
    for e in result.get("schedule", []):
        by_court[(e.get("location"), e.get("day"), e.get("court"))].append(e)
    out = []
    for key in sorted(by_court,
                      key=lambda k: (str(k[0]), str(k[1]), k[2] if k[2] is not None else 0)):
        rows = sorted(by_court[key], key=lambda e: (e.get("start") or ""))
        out.append({"location": key[0], "day": key[1], "court": key[2],
                    "matches": [_match_row(e) for e in rows]})
    return out


# ---- OI-20 - schedule, by player --------------------------------------------
def schedule_by_player(result):
    """[{player, matches: [row, ... by day/start]}, ...] sorted by player.

    HOLDVIS-1 (§3.3): a match the TD held off the schedule still belongs on its players'
    handouts. Before this, holding three matches left 4 of the 6 men with NO block in the file at
    all — the player was handed nothing and had no way to learn why. The held entries are folded
    into the same per-player list the scheduled ones use, so both renderers get them without a
    signature change. They sort LAST within a player: a held match has no day to sort on, and the
    end of the list is where the CSV puts it too (ruling 1's own reasoning). A result with no
    hold produces exactly the rows and the order it always did.

    ROUND-1 (2026-08-08): the division's real depth is read from the SAME result this function
    already receives and stamped on every row it emits, so the handout's round word counts back
    from the round the division actually ends on rather than from the deepest round one of its
    named players happens to be in. No signature change — the runbook's Step-6 call is untouched
    and there is no keyword a caller can forget.
    """
    depth = _division_depth(result)
    by_player = defaultdict(list)
    for e in result.get("schedule", []):
        for p in e.get("players", []):
            by_player[p].append(e)
    for h in (result.get("held") or ()):
        e = {"event": h.get("event"), "players": list(h.get("players") or ()), "held": True}
        if h.get("round") is not None:
            e["round"] = h["round"]
        for p in e["players"]:
            by_player[p].append(e)
    out = []
    for p in sorted(by_player):
        rows = sorted(by_player[p], key=lambda e: (1 if e.get("held") else 0,
                                                   e.get("day") or "", e.get("start") or ""))
        out.append({"player": p,
                    "matches": [_match_row(e, depth.get(e.get("event"))) for e in rows]})
    return out


# ---- text rendering ---------------------------------------------------------
def _loc(m):
    return f" @{m['location']}" if m.get("location") else ""


def _court(m):
    """CUI-5 (Part C): the court token, printed ONLY when a court was actually assigned.

    Court is a day-of-ops decision in Era-1 — the engine emits `court: None` on every row this
    lane produces (760 of 760 on the committed field), and printing `court None` told the TD
    nothing on 760 by-division lines and 1,164 by-player lines. A row carrying a REAL court
    number still prints it, byte for byte as before: the retirement is additive, and the
    module's selftest keeps a court-carrying case to prove it.
    """
    return f"  court {m['court']}" if m.get("court") is not None else ""


def order_of_play_by_division_text(rows):
    if not rows:
        return "No scheduled matches."
    lines = []
    for r in rows:
        lines.append(f"{r['division']}  ({len(r['matches'])} matches)")
        for m in r["matches"]:
            lines.append(f"    {m['day']} {m['start']}-{m['end']}{_court(m)}{_loc(m)}  {m['match']}")
    return "\n".join(lines)


def _by_court_head(r):
    """CUI-5 (Part C): the group's own name.

    On this lane no court is assigned, so the grouping key `(location, day, court)` yields ONE
    group per site-day — and the header used to call that group `MHCC court None - 2026-01-23`,
    naming a court that does not exist for a group that is the whole site-day. It now says what
    the group is. A real court number prints exactly the header it always did.
    """
    loc, day, court = r["location"], r["day"], r["court"]
    if court is not None:
        return f"{loc + ' ' if loc else ''}court {court} - {day}"
    return f"{loc} — {day}" if loc else f"{day}"


def run_of_play_by_court_text(rows):
    if not rows:
        return "No scheduled matches."
    lines = []
    for r in rows:
        lines.append(f"{_by_court_head(r)}  ({len(r['matches'])} matches)")
        for m in r["matches"]:
            lines.append(f"    {m['start']}-{m['end']}  {m['event']}  {m['match']}")
    return "\n".join(lines)


def schedule_by_player_text(rows):
    if not rows:
        return "No scheduled matches."
    lines = []
    for r in rows:
        lines.append(f"{r['player']}  ({len(r['matches'])} matches)")
        for m in r["matches"]:
            if m.get("held"):
                # HOLDVIS-1: the words stand where day / start / site would print. The match
                # label is not used — it carries the internal round-and-match reference, which
                # never reaches a surface a person reads.
                lines.append(f"    {HELD_TEXT}  {m['event']}  "
                             f"{' v '.join(m.get('players') or ())}")
                continue
            lines.append(f"    {m['day']} {m['start']}{_court(m)}{_loc(m)}  {m['event']}  {m['match']}")
    return "\n".join(lines)


# ---- OI-20 (D-24 / CUI-5 Part E) - the printable sheets ----------------------
# The two sheets the desk posts and hands out. Same house look as `draw_sheets.py` — the paper,
# the green band, the sticky index, the print shell — so the run's output set reads as one
# document family. Deliberately NOT SVG: these are tabular, they reflow, and a TD prints them on
# letter paper at the desk rather than on the 36x24" plotter the brackets need.
#
# NO COURT COLUMN, by design and not by omission: court is a day-of-ops decision (Era-1;
# `draw_sheets._slot` says the same), so a column of blanks would invite someone to treat the
# sheet as the court assignment. Part C's text views are silent about court for the same reason.
#
# Deterministic: nothing here reads the clock, so the same result renders the same bytes.

_DOW = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

SHEET_PAGE = """<!doctype html>
<meta charset="utf-8"><title>{title}</title><style>
:root{{--paper:#F3F1EA;--ink:#15201b;--muted:#7c7f78;--line:#c9cdc4;--line-2:#d8dcd2;
--court:#1f6e55;--court-d:#16523d;--red:#a8323f;
--font-mono:ui-monospace,'SF Mono',Menlo,Consolas,monospace;}}
body{{margin:0;background:#e7e4dc;color:var(--ink);
font-family:system-ui,-apple-system,'Segoe UI',Helvetica,Arial,sans-serif}}
.nav{{position:sticky;top:0;background:#16523d;color:#fff;padding:10px 18px;font-size:13px;z-index:9;
box-shadow:0 1px 6px rgba(0,0,0,.2)}}
.nav b{{font-weight:700}} .nav a{{color:#cdebd9;text-decoration:none;margin-right:14px}}
.nav a:hover{{text-decoration:underline}}
.sheet{{background:var(--paper);margin:20px auto;max-width:1100px;padding:22px 26px 26px;
box-shadow:0 1px 6px rgba(0,0,0,.12);border-radius:6px;overflow-x:auto}}
.sheet h2{{margin:0;font-size:20px;letter-spacing:.01em;color:var(--court-d)}}
.sheet .sub{{margin:3px 0 14px;font-size:12.5px;color:var(--muted);
letter-spacing:.06em;text-transform:uppercase;font-weight:600}}
table{{border-collapse:collapse;width:100%;font-size:13.5px}}
th{{text-align:left;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);
font-weight:700;padding:0 10px 6px 0;border-bottom:1px solid var(--line)}}
td{{padding:6px 10px 6px 0;border-bottom:1px solid var(--line-2);vertical-align:top}}
tr:last-child td{{border-bottom:none}}
.t{{font-family:var(--font-mono);white-space:nowrap;color:var(--court-d);font-weight:600}}
.rnd{{white-space:nowrap;color:var(--muted)}}
.site{{white-space:nowrap}}
.vs{{color:var(--muted);padding:0 2px}}
.pt{{color:var(--muted);padding:0 1px}}
.await{{color:var(--muted);font-style:italic}}
.foot{{margin-top:14px;font-size:11.5px;color:var(--muted);line-height:1.5}}
.empty{{color:var(--muted);font-style:italic;padding:8px 0}}

/* Print: letter paper at the desk, one sheet per page. */
@media print{{
  @page{{size:letter portrait;margin:0.5in;}}
  body{{background:#fff}}
  .nav{{display:none !important}}
  .sheet{{margin:0;max-width:none;padding:0;box-shadow:none;border-radius:0;background:#fff;
    break-after:page;page-break-after:always;overflow:visible}}
  .sheet:last-child{{break-after:auto;page-break-after:auto}}
  thead{{display:table-header-group}}
  tr{{break-inside:avoid;page-break-inside:avoid}}
}}
</style>
<div class="nav"><b>{banner}</b> &nbsp; {links}</div>
{sheets}"""


def _e(s):
    """Escape for HTML. Division names carry '&' ("30 & over") on nearly every sheet."""
    return _html.escape("" if s is None else str(s))


def _long_day(day):
    """`2026-01-23` -> `Friday, Jan 23, 2026`. An unparseable day prints as-is rather than
    raising — a sheet is a report, and a malformed date is information, not a crash."""
    try:
        d = _dt.datetime.strptime(day, "%Y-%m-%d")
    except (TypeError, ValueError):
        return str(day)
    return f"{_DOW[d.weekday()]}, {_MON[d.month - 1]} {d.day}, {d.year}"


def _short_day(day):
    try:
        d = _dt.datetime.strptime(day, "%Y-%m-%d")
    except (TypeError, ValueError):
        return str(day)
    return f"{_DOW[d.weekday()][:3]} {_MON[d.month - 1]} {d.day}"


def _round_label(m, max_rnd):
    """The house round wording (`editor_plan._round_name`'s vocabulary, singular on a sheet that
    names ONE match per line). Re-stated rather than imported: this module imports engine output
    and `division_order` only, and that direction is asserted elsewhere.

    A ROUND ROBIN has no final — its round 6 is round 6, not "the final" — so the elimination
    naming is applied only to a `main` draw. The committed field carries 9 RR divisions playing
    6 rounds each; naming their last three rounds Final / Semifinal / Quarterfinal would put a
    wrong word on a posted sheet, which is the failure a printed document cannot take back.
    """
    rnd = m.get("round")
    if rnd is None:
        return ""
    if m.get("draw") == "rr" or max_rnd is None:
        return f"Round {rnd}"
    back = max_rnd - rnd
    return {0: "Final", 1: "Semifinal", 2: "Quarterfinal"}.get(back, f"Round {rnd}")


def _max_round_by_division(rows_groups):
    """Deepest round per division across the whole set, so 'Final' means the division's final.

    HOLDVIS-1: a HELD row is excluded from the max. It is not a line of its own here — the max
    feeds every OTHER line's round label, and a held match deep in a division could otherwise
    relabel matches this build has no business touching. A hold changes the held line and nothing
    else; `tests/holdvis1_visibility.py` Part B asserts that as byte-identity on 715 blocks.

    ROUND-1: a row that carries `division_rounds` already KNOWS its division's real depth — the
    caller read it off the result's own match record (`_division_depth`), where every round is
    present whether or not its players are decided — so the stamp is PREFERRED wherever a row
    carries one. The row-derived
    max stays as the fallback and is load-bearing, not vestigial: `render_run_of_play_html`
    groups by court and its rows carry no stamp, and it was already right (0 of 51 divisions
    wrong, because that grouping sees every row named or not), so it must go on computing exactly
    what it computes today and rendering the same bytes.
    """
    top, stamped = {}, {}
    for g in rows_groups:
        for m in g["matches"]:
            r, ev = m.get("round"), m.get("event")
            d = m.get("division_rounds")
            if d is not None and (ev not in stamped or d > stamped[ev]):
                stamped[ev] = d
            if r is None or m.get("held"):
                continue
            if ev not in top or r > top[ev]:
                top[ev] = r
    top.update(stamped)
    return top


def _sides_html(m):
    """CARD-1's side model, rendered: partners joined, sides separated, a side still waiting on
    a feeder said as such.

    LANG-1 item 36: when NEITHER side is decided the column reads "To be decided". It used to
    fall back to the engine's match label, which answered "who is playing?" with the division and
    round already printed in the two columns beside it, plus an internal match number
    (`Men's 85 & over singles Quarterfinal M2`) — measured on 272 of 760 run-of-play rows. The
    player handouts already answered the same question correctly ("— awaiting an opponent",
    172 uses); this brings the run-of-play sheet into line.
    """
    sides = m.get("sides")
    if not sides:
        players = [p for p in (m.get("players") or []) if p]
        if players:
            return f' <span class="vs">v</span> '.join(_e(p) for p in players)
        # LANG-1 item 36: the "who's playing" column must answer WHO. Falling back to the
        # engine's match label made it repeat the division and round already printed beside it
        # and add an internal match number — measured, 272 of 760 run-of-play rows.
        return "To be decided"
    a, b = sides
    join = ' <span class="pt">/</span> '
    if a and b:
        return (join.join(_e(p) for p in a) + ' <span class="vs">v</span> '
                + join.join(_e(p) for p in b))
    one = a or b
    if one:
        return join.join(_e(p) for p in one) + ' <span class="await">— awaiting an opponent</span>'
    # The measured site: an undecided round carries `sides` of [[], []], so it lands HERE, not on
    # the no-sides branch above. 272 of 760 run-of-play rows.
    return "To be decided"


def _nav(links, banner, sheets, title):
    return SHEET_PAGE.format(title=_e(title), banner=_e(banner),
                             links=" ".join(links), sheets="\n".join(sheets))


def _banner(tournament, what):
    """The sheet's title and banner.

    `tournament` DEFAULTS TO NOTHING, and that is the point. It shipped as the literal
    `"WWTC 2026"`, which meant a caller that did not pass a name — and the runbook's Step-6
    snippet did not — printed **2026** on every posted run-of-play sheet and all 721 player
    handouts of a 2027 run. A printed document is the one place a wrong year cannot be taken
    back, so an omitted name now claims no year at all; the run passes the real one from the
    couriered slate. Found by running a mock 2027 field end to end.
    """
    return f"{tournament} — {what}" if tournament else what[:1].upper() + what[1:]


def render_run_of_play_html(rows, tournament=None):
    """The courtside run-of-play sheet — ONE sheet per site-day, matches in start order.

    `rows` is `run_of_play_by_court(result)`. Court is not a column (day-of ops); the sheet's
    job is the ORDER of play at a site on a day, which is exactly what the desk posts.
    """
    if not rows:
        return _nav([], _banner(tournament, "run of play"), ['<div class="sheet"><h2>Run of play</h2>'
                    '<div class="empty">No scheduled matches.</div></div>'],
                    _banner(tournament, "run of play"))
    top = _max_round_by_division(rows)
    links, sheets = [], []
    for i, r in enumerate(rows, 1):
        anchor = f"rop{i}"
        site = r.get("location") or "All courts"
        head = f"{site} — {_long_day(r['day'])}" if r.get("court") is None \
            else f"{site} court {r['court']} — {_long_day(r['day'])}"
        links.append(f'<a href="#{anchor}">{_e(site)} {_e(_short_day(r["day"]))}</a>')
        body = []
        for m in r["matches"]:
            body.append(
                f'<tr><td class="t">{_e(m.get("start"))}–{_e(m.get("end"))}</td>'
                f'<td>{_e(m.get("event"))}</td>'
                f'<td class="rnd">{_e(_round_label(m, top.get(m.get("event"))))}</td>'
                f'<td>{_sides_html(m)}</td></tr>')
        sheets.append(
            f'<div class="sheet" id="{anchor}"><h2>{_e(head)}</h2>'
            f'<div class="sub">Run of play · {len(r["matches"])} '
            f'match{"" if len(r["matches"]) == 1 else "es"}</div>'
            f'<table><thead><tr><th>Time</th><th>Division</th><th>Round</th>'
            f'<th>Match</th></tr></thead><tbody>{"".join(body)}</tbody></table>'
            f'<div class="foot">Courts are assigned at the desk on the day — this sheet is the '
            f'order of play, not the court assignment.</div></div>')
    return _nav(links, _banner(tournament, "run of play"), sheets, _banner(tournament, "run of play"))


def render_by_player_html(rows, tournament=None):
    """The player handout — one block per player, every match they are in, in play order.

    `rows` is `schedule_by_player(result)`. On a doubles line the partner is named as a partner
    and the opponents as opponents (CARD-1's side model, read from the row, never re-derived).
    """
    if not rows:
        return _nav([], _banner(tournament, "player schedules"),
                    ['<div class="sheet"><h2>Player schedules</h2>'
                     '<div class="empty">No scheduled matches.</div></div>'],
                    _banner(tournament, "player schedules"))
    top = _max_round_by_division(rows)
    # The index is A–Z, not one link per player: the committed field carries 721 players, and a
    # 721-link band filled the entire first screen and buried the first sheet under it. Each
    # letter jumps to the first player under it; the sheets themselves are the document (one per
    # page in print), and the band is only how you find someone on screen.
    links, sheets, seen_initial = [], [], set()
    for i, r in enumerate(rows, 1):
        anchor = f"pl{i}"
        initial = (r["player"] or "?").strip()[:1].upper() or "?"
        if initial not in seen_initial:
            seen_initial.add(initial)
            links.append(f'<a href="#{anchor}">{_e(initial)}</a>')
        body = []
        for m in r["matches"]:
            if m.get("held"):
                # HOLDVIS-1 (§3.3): the phrase prints where day · start · site would, spanning
                # those three columns rather than leaving the player to read three blank cells.
                # The division, the round and who he is playing are all still there — the only
                # thing this match does not have is a time.
                body.append(
                    f'<tr><td class="await" colspan="3">{_e(HELD_TEXT)}</td>'
                    f'<td>{_e(m.get("event"))}</td>'
                    f'<td class="rnd">{_e(_round_label(m, top.get(m.get("event"))))}</td>'
                    f'<td><span class="vs">—</span></td>'
                    f'<td>{_sides_html(m)}</td></tr>')
                continue
            sides = m.get("sides")
            with_ = ""
            if sides:
                mine = sides[0] if r["player"] in sides[0] else (
                    sides[1] if r["player"] in sides[1] else [])
                partners = [p for p in mine if p != r["player"]]
                if partners:
                    with_ = " / ".join(partners)
            partner_cell = _e(with_) if with_ else '<span class="vs">—</span>'
            body.append(
                f'<tr><td class="site">{_e(_short_day(m.get("day")))}</td>'
                f'<td class="t">{_e(m.get("start"))}</td>'
                f'<td class="site">{_e(m.get("location") or "—")}</td>'
                f'<td>{_e(m.get("event"))}</td>'
                f'<td class="rnd">{_e(_round_label(m, top.get(m.get("event"))))}</td>'
                f'<td>{partner_cell}</td>'
                f'<td>{_sides_html(m)}</td></tr>')
        sheets.append(
            f'<div class="sheet" id="{anchor}"><h2>{_e(r["player"])}</h2>'
            f'<div class="sub">{len(r["matches"])} '
            f'match{"" if len(r["matches"]) == 1 else "es"}</div>'
            f'<table><thead><tr><th>Day</th><th>Start</th><th>Site</th><th>Division</th>'
            f'<th>Round</th><th>Partner</th><th>Match</th></tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table>'
            f'<div class="foot">Report to the desk at the site above; your court is given to you '
            f'there. Times can move — check the posted run of play on the day.</div></div>')
    return _nav(links, _banner(tournament, "player schedules"), sheets,
                _banner(tournament, "player schedules"))


# ---- self-test + demo -------------------------------------------------------
def _selftest():
    # sample data names only (per repo rule)
    #
    # CUI-5 (Part C): the PRIMARY case is the LIVE shape — court-less rows, which is what all
    # 760 rows of the committed field look like. The fixture used to hardcode courts 1/1/2 and
    # so graded a path the field never takes: `court None` printed on 1,924 lines across the
    # three views while this selftest was green. One court-carrying row is KEPT (the doubles
    # final at ORLP) to prove the additive half — a real court still prints.
    result = {"schedule": [
        {"event": "Men's 65 Singles", "match": "SF", "day": "2026-01-01", "round": 1,
         "start": "08:00", "end": "09:30", "court": None, "location": "MHCC",
         "team_a": ["Al Ace"], "team_b": ["Bo Bell"],
         "players": ["Al Ace", "Bo Bell"]},
        {"event": "Men's 65 Singles", "match": "F", "day": "2026-01-01", "round": 2,
         "start": "11:00", "end": "12:30", "court": None, "location": "MHCC",
         "team_a": ["Al Ace"], "team_b": ["Cy Cole"],
         "players": ["Al Ace", "Cy Cole"]},
        {"event": "Men's 65 Doubles", "match": "F", "day": "2026-01-02", "round": 1,
         "start": "09:30", "end": "11:00", "court": 2, "location": "ORLP",
         "team_a": ["Al Ace", "De Dunn"], "team_b": ["Bo Bell", "Ed East"],
         "players": ["Al Ace", "De Dunn", "Bo Bell", "Ed East"]},
    ]}

    div = order_of_play_by_division(result)
    # DIV-1 (rule 44): singles before doubles — the TD's reading order, not alphabetical.
    # (Was ["Men's 65 Doubles", "Men's 65 Singles"] when this sorted on the raw name.)
    assert [d["division"] for d in div] == ["Men's 65 Singles", "Men's 65 Doubles"]
    singles = next(d for d in div if d["division"] == "Men's 65 Singles")
    assert [m["start"] for m in singles["matches"]] == ["08:00", "11:00"]   # play order

    courts = run_of_play_by_court(result)
    mhcc = next(c for c in courts if c["location"] == "MHCC")
    assert mhcc["court"] is None and mhcc["day"] == "2026-01-01" and len(mhcc["matches"]) == 2
    assert [m["start"] for m in mhcc["matches"]] == ["08:00", "11:00"]
    orlp = next(c for c in courts if c["location"] == "ORLP")
    assert orlp["court"] == 2                                  # the additive half, still carried

    players = schedule_by_player(result)
    al = next(p for p in players if p["player"] == "Al Ace")
    assert len(al["matches"]) == 3
    assert [(m["day"], m["start"]) for m in al["matches"]] == [
        ("2026-01-01", "08:00"), ("2026-01-01", "11:00"), ("2026-01-02", "09:30")]

    # CUI-5 Part C: no printed line names a court the engine never assigned, and a row that
    # DOES carry one still prints it.
    div_t = order_of_play_by_division_text(div)
    court_t = run_of_play_by_court_text(courts)
    play_t = schedule_by_player_text(players)
    for name, text in (("by-division", div_t), ("by-court", court_t), ("by-player", play_t)):
        bad = [l for l in text.splitlines() if "court None" in l]
        assert not bad, f"{name} still prints a court that was never assigned: {bad[:3]}"
    assert "MHCC — 2026-01-01" in court_t, court_t      # the group finally says what it is
    assert "ORLP court 2 - 2026-01-02" in court_t, court_t          # unchanged for a real court
    assert "court 2" in div_t and "court 2" in play_t, "the additive half stopped printing"

    # CUI-5 Part E: the two printable sheets render, carry the house shell, name no court
    # column, and read CARD-1's sides on the doubles line.
    rop = render_run_of_play_html(courts)
    byp = render_by_player_html(players)
    for name, doc in (("run-of-play", rop), ("by-player", byp)):
        assert doc.startswith('<!doctype html>'), name
        assert "court None" not in doc, name
        assert "@page" in doc and "#16523d" in doc, f"{name} lost the house print shell"
    # CUI-5 follow-up: an omitted `tournament` claims NO year. It shipped defaulting to the
    # literal "WWTC 2026", so a 2027 run — whose runbook snippet passed no name — would have
    # printed 2026 on every posted sheet and all 721 handouts.
    for doc in (rop, byp):
        assert "2026" not in doc.split("<style>")[0], \
            f"the sheet's banner names a year nobody passed: {doc[:120]}"
    named = render_run_of_play_html(courts, tournament="WWTC 2027")
    assert "WWTC 2027 — run of play" in named, named[:200]
    assert "MHCC — Thursday, Jan 1, 2026" in rop, rop[:400]
    assert "Al Ace" in byp and "De Dunn" in byp
    assert "Final" in rop and "Semifinal" in rop         # round labels, not raw round numbers

    # Integration: real engine output feeds all three views consistently.
    from scheduler_multi import schedule_multi, MultiConfig, EventSpec, Team
    ev = EventSpec(name="Test RR", fmt="round_robin",
                   teams=[Team(tid="1", members=["Al Ace"]),
                          Team(tid="2", members=["Bo Bell"]),
                          Team(tid="3", members=["Cy Cole"])])
    res = schedule_multi(MultiConfig(tournament_name="views-smoke", num_courts=2,
                                     dates=["2026-01-01", "2026-01-02"], events=[ev]))
    n = len(res["schedule"])
    assert sum(len(d["matches"]) for d in order_of_play_by_division(res)) == n
    assert sum(len(c["matches"]) for c in run_of_play_by_court(res)) == n

    print("schedule_views self-test OK")
    print(order_of_play_by_division_text(div))
    print(run_of_play_by_court_text(courts))
    print(schedule_by_player_text(players))


if __name__ == "__main__":
    _selftest()
