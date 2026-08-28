"""Multi-division renderer: one draw sheet per event (brackets + byes + RR grids).
Reconstructs each division's draw from the engine's own build functions
(deterministic) and overlays the scheduled slots from a schedule_multi result.

Two outputs, same SVGs:
  render_all(...)      -> screen/print HTML (one sheet per division; @media print
                          targets 36x24" landscape plotter paper).
  render_all_pdf(...)  -> 36x24" landscape PDF, one division per page, for the
                          large-format printout. Colors are dereferenced from the
                          shared PALETTE because the SVG var() refs live in the
                          HTML <style>, which a standalone SVG->PDF pass can't see.
"""
import math, re, datetime as _dt
import division_order as DO       # DIV-1: rule 44's one display order (display only)
from scheduler_multi import (Team, EventSpec, MultiConfig, BYE,
                             build_elim_teams, build_rr_teams, _is_bye_team,
                             # REKEY-1 (N9): LANG-1's own match-naming helpers, REUSED rather
                             # than re-minted — division, round and players, never an internal
                             # id, with the shared-surname carve-out already measured there.
                             _c_players, _c_day, _final_rounds, _round_name)

# Single source of truth for colors. The HTML :root mirrors these; the PDF path
# substitutes them literally (cairosvg does not resolve CSS var()).
PALETTE = {
    "--paper":  "#F3F1EA", "--ink":     "#15201b", "--muted":   "#7c7f78",
    "--line":   "#c9cdc4", "--line-2":  "#d8dcd2",
    "--court":  "#1f6e55", "--court-d": "#16523d", "--red":     "#a8323f",
    # REKEY-1 (N8): the three amber values `schedule_editor.html:12` already uses, so the print
    # set and the console carry ONE amber rather than two. They live here AND in PAGE's :root
    # below — a var added to only one of the two palettes renders black on the plotter PDF and
    # correct on screen, which fails only on the surface this build exists to fix.
    "--amber":  "#9C5F0E", "--amber-bg": "#F7F0E3", "--amber-line": "#E6D6B6",
    "--font-mono": "ui-monospace,'SF Mono',Menlo,Consolas,monospace",
}

def _deref(svg, palette=PALETTE):
    """Replace every var(--x) with its literal value. Unknown vars -> black,
    so a missing color is visible rather than silently transparent."""
    return re.sub(r"var\((--[a-z0-9-]+)\)",
                  lambda m: palette.get(m.group(1), "black"), svg)

def _xml_safe(svg):
    """Escape bare '&' that aren't already part of an entity. Browsers tolerate
    raw '&' (e.g. in '30 & over'); cairosvg's strict XML parser does not.
    HTML output keeps the raw form; only the PDF pass needs this."""
    return re.sub(r"&(?!#?\w+;)", "&amp;", svg)

DOW = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
def _slot(row):
    if not row or not row.get("day"): return None
    d = _dt.datetime.strptime(row["day"], "%Y-%m-%d")
    # Era-1: placement is (day, time, LOCATION) — court numbers are a day-of ops decision (deferred).
    return f"{DOW[d.weekday()]} {d.strftime('%b %-d')} · {row['start']}–{row['end']} · {row.get('location') or '—'}"

def _slot_compact(row):
    """Compact slot for the sheets: 'M/D HH:MM LOC' (e.g. '1/25 12:30 ORLP') — ~60%
    narrower than _slot(). Drops the weekday, the end-time and the heavy separators so
    the label fits its own lane under a name instead of spilling into the inter-column
    gap. _slot() stays verbose for the RR 'Next match' column, which has its own wide
    lane; still time + LOCATION, still no court number (Era-1)."""
    if not row or not row.get("day"): return None
    d = _dt.datetime.strptime(row["day"], "%Y-%m-%d")
    return f"{d.month}/{d.day} {row['start']} {row.get('location') or '—'}"

# Deterministic text-width estimate (px) for the content-sizing pass. No font metrics
# are available offline, so approximate per-glyph advance; erring generous is safe
# because the sheets render at natural size and scroll rather than being squashed.
def _text_w(s, size, mono=False):
    return len(s) * size * (0.62 if mono else 0.60)

def _prefix_for(cfg, ev):
    return f"E{cfg.events.index(ev)+1}"


# ------------------------------------------------- REKEY-1: the change model (A7a, §3.1)
# ONE model, three consumers: the brackets (N7 names + seeds), the amber marks (N8) and the
# re-enter page (N9). Built here so a sheet can never mark a match the page omits, and vice
# versa — `tests/rekey1_changes.py` Part C asserts that as set equality in both directions.
#
# The tags are minted under the glossary's ultra-concise house rule (1-3 words) in the ruled
# vocabulary: "locked day", never "pin". Amber is NEVER the only carrier of meaning — these
# sheets print to 36x24" plotter paper and may come off a monochrome plotter — so every amber
# element also carries its tag as TEXT, and the legend names the tags the sheet uses.
TAG_MOVED = "moved"
TAG_LOCKED_DAY = "locked day"
TAG_SUB = "substituted"
TAGS = (TAG_MOVED, TAG_LOCKED_DAY, TAG_SUB)
# Decision 2's ONE meaning, stated on every sheet that carries a mark. The mark does NOT mean
# "someone typed this": on the 2026 run 20 of the 25 marks sit in two divisions the TD never
# hand-edited, and without this line an unedited-but-marked division is unexplained.
LEGEND_LEAD = "Amber = not as first scheduled."

# ------------------------------------------------- HOLDVIS-1: the held stamp (ruling 2, 8/7)
# What the slot lane prints for a match the TD held off the schedule. TEXT ONLY, and the colour
# stays RED: amber has ONE ruled meaning on these sheets — "not where the schedule first put it"
# (REKEY-1 decision 2) — and a hold is the TD's own decision, not a move. The change model that
# deliberately excludes holds is not widened, and "held" reaches no tag and no legend.
#
# Measured before this build: the lane printed a bare `not scheduled` in red on exactly the 3
# held matches, which reads as an ENGINE failure rather than a recorded decision. The word is
# what changes; the ink does not.
HELD_TEXT = "held — not scheduled"


def held_matches(result):
    """`{match id}` — every match the TD held and never placed back (`result["held"]`).

    Absent on a base build and on any result the edit lane never touched, so a tournament with no
    hold reads an empty set here and every sheet renders exactly the bytes it rendered before.
    """
    return {h.get("id") for h in (result.get("held") or ())}


def _no_slot_text(mid, held):
    """The stamp for a match with no slot: the TD's own hold says so in words, or the bare
    fallback for a match the schedule genuinely never placed."""
    return HELD_TEXT if mid in (held or ()) else "not scheduled"


def _event_matches(ev, prefix):
    """The event's own match list, by format — the same call `render_event` dispatches on."""
    return build_rr_teams(ev, prefix) if ev.fmt == "round_robin" else build_elim_teams(ev, prefix)


def changed_matches(result, locked_day_shifts=None):
    """`{match id: tag}` — every match that is not where the schedule first put it.

    Two sources, one convention (decision 2, Operator 2026-08-07): the TD's own hand edits, and
    the rounds a locked final dragged onto another day. Measured on the 2026 run that is
    **25 of 760** — 5 hand-edited + 20 inside the 6 shifted rounds, with an empty intersection.

    `locked_day_shifts` is the structure `wwtc_pipeline` emits beside `master_warnings`; it is
    NOT in `result` and cannot be derived from it (`cfg.assigned_days` holds only the final day
    per round, with no was-days). Omitted -> hand edits only.

    A `hold` is deliberately NOT marked: the brief's model carries three change kinds — moves,
    the substitution and locked-day shifts — and a held match has no recorded old slot to show
    in a "Was" column. Flagged rather than silently half-built.
    """
    marks = {}
    want = set()
    for s in (locked_day_shifts or ()):
        for rnd in (s.get("match_rounds") or ([s.get("round")] if s.get("round") else [])):
            want.add((s.get("event"), rnd))
    if want:
        for row in (result.get("schedule") or ()):
            if (row.get("event"), row.get("round")) in want:
                marks[row["id"]] = TAG_LOCKED_DAY
    # A hand edit is the more specific fact, so it wins on a match that is also in a shifted
    # round; later records win over earlier ones on the same match, as the document applied them.
    for e in (result.get("applied_edits") or ()):
        if e.get("op") in ("move", "pin") and e.get("result") == "placed":
            marks[e["id"]] = TAG_MOVED
    return marks


def substitutions(cfg, result):
    """`{(event name, tid): record}` — the substituted TEAM on its OWN draw.

    Keyed by `(event, tid)` and NEVER by player name. Measured on the 2026 run: the outgoing
    player prints 3 times across the printed set and only the doubles line is wrong — he
    legitimately still plays singles — so a name-level scrub would break two correct sheets.
    `tests/rekey1_changes.py` Part A asserts exactly 2 surviving prints and fails at 0.
    """
    out = {}
    cache = {}
    for e in (result.get("applied_edits") or ()):
        if e.get("op") != "substitute" or e.get("result") != "substituted":
            continue
        mid, out_name, in_name = e.get("id") or "", e.get("out_name"), e.get("in_name")
        g = re.match(r"^E(\d+)-", mid)
        if not (g and out_name and in_name):
            continue
        i = int(g.group(1)) - 1
        if not 0 <= i < len(cfg.events):
            continue
        ev, prefix = cfg.events[i], f"E{int(g.group(1))}"
        if prefix not in cache:
            cache[prefix] = ({m.mid: m for m in _event_matches(ev, prefix)},
                             {frozenset(t.members): t for t in ev.teams if not _is_bye_team(t)})
        by_mid, by_members = cache[prefix]
        m = by_mid.get(mid)
        if m is None:
            continue
        team = next((t for t in (by_members.get(frozenset(m.team_a or [])),
                                 by_members.get(frozenset(m.team_b or [])))
                     if t is not None and out_name in t.members), None)
        if team is None:
            continue
        members = [in_name if p == out_name else p for p in team.members]
        out[(ev.name, team.tid)] = {
            "event": ev.name, "tid": team.tid, "id": mid,
            "label": "/".join(members), "members": members,
            "old_label": team.label(), "old_members": list(team.members),
            "out_name": out_name, "in_name": in_name,
            "seed_effect": e.get("seed_effect"), "seed_kept_reason": e.get("seed_kept_reason"),
        }
    return out


def _subs_for(ev, subs):
    """The substitution map narrowed to one draw: `{tid: record}`."""
    return {tid: v for (name, tid), v in (subs or {}).items() if name == ev.name}


def _rekey_seeds(seeds, subs_by_tid):
    """Re-key the seed map onto the substituted label, following the RECORDED `seed_effect`.

    `seeds` is keyed by the OLD label string, so renaming a team without re-keying silently
    drops its `[3]` — the exact opposite of a recorded `seed_effect: "kept"`. `seed_effect` is
    authoritative: the sheet never invents a seed decision. An absent `seed_effect` drops the
    seed, which is the Edit console's own stated default.
    """
    if not subs_by_tid:
        return seeds
    out = dict(seeds or {})
    for s in subs_by_tid.values():
        sd = out.pop(s["old_label"], None)
        if s.get("seed_effect") == "kept" and sd is not None:
            out[s["label"]] = sd
    return out


# ------------------------------------------------- REKEY-1: N6b, ratings beside the names
def _roster_by_name(roster):
    """`{full name: player}`. The roster is keyed by USTA ID; the draws carry names. Measured on
    the 2026 field: 759 names, 759 distinct, and 721 of 721 players on a draw match exactly."""
    if not roster:
        return {}
    src = roster.values() if isinstance(roster, dict) else roster
    return {p.name: p for p in src if getattr(p, "name", None)}


def _is_doubles_division(name):
    """The division name carries the format — the same test the console's card renderer uses."""
    d = (name or "").lower()
    return "doubles" in d or "mixed" in d


def _rated(members, ridx, doubles):
    """`Frank Zebot 15.8/David Hochwald 12.3` — the name line with each member's format-matched
    WTN. A doubles line carries two names, therefore two ratings. A missing rating prints an em
    dash, never a blank (decision 4): 46 of the 2026 field's 1,066 name-slots have no rating of
    the right kind. One decimal, matching the Edit console's own card."""
    parts = []
    for nm in members:
        p = ridx.get(nm)
        v = getattr(p, "wtn_doubles" if doubles else "wtn_singles", None) if p is not None else None
        parts.append(f"{nm} {v:.1f}" if isinstance(v, (int, float)) else f"{nm} —")
    return "/".join(parts)


def _team_text(team, subs_by_tid, ridx, doubles):
    """`(printed name text, seed key, tag)` for one team cell — the substituted label if this
    team was substituted, plus its ratings. `tag` is the N8 tag or None.

    ONE function, called by BOTH the content-sizing pass and the cell renderer, so the lane can
    never be sized from a shorter string than the one that gets drawn. A slot stamp plus
    `· locked day` measures ~226 px against the lane's 180 px floor, so an unsized tag overruns
    the box into the connector channel on a short-name draw.

    The tag is returned separately, not glued on, because it renders AFTER the seed marker —
    `Frank Zebot/David Hochwald [3] · substituted` reads; the seed wedged behind the tag does not.
    """
    if team is None:
        return "BYE", None, None
    s = (subs_by_tid or {}).get(team.tid)
    members = s["members"] if s else list(team.members)
    key = s["label"] if s else team.label()
    txt = _rated(members, ridx, doubles) if (ridx and members) else key
    return txt, key, (TAG_SUB if s else None)


def _tagged(txt, tag, seed=None):
    """The full drawn width of a name cell: text, seed marker, tag. The sizing pass measures
    THIS, never the bare text."""
    return f"{txt}{f' [{seed}]' if seed else ''}{f' · {tag}' if tag else ''}"


def _slot_text(sched_row, mid, marks):
    """`(printed slot text, amber)`. The tag joins the string here so the sizing pass sees it."""
    s = _slot_compact(sched_row)
    tag = (marks or {}).get(mid)
    if s and tag:
        return f"{s} · {tag}", True
    return s, False


def _legend_svg(x, y, tags, size=13):
    """The legend, once per sheet and only when the sheet carries a mark (never once per mark).

    It states decision 2's ONE ruled meaning, because the mark no longer means "someone typed
    this" — two divisions the TD never touched carry 20 of the 2026 run's 25 marks, and the
    sheet has to explain itself. Returns `(svg, width)`.
    """
    present = [t for t in TAGS if t in tags]
    if not present:
        return "", 0
    txt = f"{LEGEND_LEAD}  " + " · ".join(present)
    w = int(_text_w(txt, size)) + 44
    return (f'<rect x="{x}" y="{y - size}" width="{w}" height="{size + 8}" rx="3" '
            f'fill="var(--amber-bg)" stroke="var(--amber-line)"/>'
            f'<rect x="{x + 8}" y="{y - size + 3}" width="{size - 3}" height="{size - 3}" rx="2" '
            f'fill="var(--amber)"/>'
            f'<text x="{x + size + 16}" y="{y - 1}" font-size="{size}" '
            f'fill="var(--amber)">{txt}</text>'), w

# ---------------------------------------------------------------- conflicts sheet
def _wrap_words(s, width):
    words, lines, cur = s.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur); cur = w
        else:
            cur = f"{cur} {w}" if cur else w
    if cur:
        lines.append(cur)
    return lines or [""]

# RPT-2 (8/7 note 8): THE CLASSIFIER. The red page used to be one flat bulleted list — on the
# 2026 run-2 replay that is 55 sentences of which 53 break the same rule, and a director reading
# it has to notice that himself. Grouping says the thing the list never said: this is three
# problems, not fifty-five.
#
# ⚠ RENDERER-SIDE ONLY. These patterns READ `validate_multi`'s sentences; they never change one,
# and `validate_multi`'s return shape is untouched. A conflict is still recorded, couriered and
# reported as the full sentence the engine wrote — the grouping exists on this page and nowhere
# else. Re-deriving which rule a match broke would be a second copy of the rule.
#
# ⚠ SEVENTEEN `issues.append` SITES, EIGHTEEN SENTENCE SHAPES. LIGHTS-1 (8/8) made the capacity
# site emit two wordings from one append — "… 7 courts." and "… 7 lighted courts, after the
# lights come on." — selected by a ternary at `scheduler_multi.py:1966`. They are the SAME rule
# broken and must land in the same group, which is why that pattern makes the lighting clause
# optional instead of keying on the literal trailing "courts.".
#
# Anything that matches nothing prints VERBATIM under "Other" — ugly, never lost (invariant 2).
_C_DAY = (r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) \d{1,2} "
          r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)")
_C_WHEN = re.compile(r"(\d{1,2}:\d{2}) (" + _C_DAY + r")")
_C_DAY_RE = re.compile(_C_DAY)

# (group heading, axis, detector). `axis` picks the second half of the sub-header, and it is the
# ruling's own split: person-level kinds group BY PLAYER, everything else by the thing the rule
# is about — the division for a match rule, the venue for a count over a venue-day.
_CONFLICT_KINDS = (
    ("Two matches at once", "person",
     re.compile(r"^(?P<label>[^:]+): two matches at once — ")),
    ("Not enough rest between matches", "person",
     re.compile(r"^(?P<label>[^:]+): under \d+ minutes between starts — ")),
    ("Not enough time to travel between venues", "person",
     re.compile(r"^(?P<label>[^:]+): not enough time to travel between venues \(")),
    ("More matches in one day than the limit", "person",
     re.compile(r"^(?P<label>[^:]+): \d+ .+ matches on .+, limit \d+\.$")),
    ("More matches at once than there are courts", "venue",
     re.compile(r"^(?P<label>.+?), (?P<day>" + _C_DAY + r"): \d+ matches at once, "
                r"\d+ (?:lighted )?courts")),
    ("Too many matches starting late afternoon", "venue",
     re.compile(r"^(?P<label>.+?), (?P<day>" + _C_DAY + r"): \d+ matches start between ")),
    ("Out of draw order", "match", re.compile(r"^Out of draw order — ")),
    # CAD-1 (2026-08-18) — the cadence mirror's two sentences. `tests/rpt2_conflicts.py` part C
    # asserts that every `issues.append` site in `validate_multi` has a row here, and it is right
    # to: without one the sentence prints under "Other", which is the graceful degradation this
    # module guarantees but not the printed page a director should get for the rule the whole
    # CAD-1 build is about. The heading is LANG-1 §42's ruled wording ("Two rounds in one day"),
    # not the engine's code word.
    ("Two rounds in one day", "match",
     re.compile(r" — this division has more than one round on ")),
    ("A round plays before an earlier round", "match",
     re.compile(r" — an earlier round of this division plays as late as ")),
    ("Out of the day's running order", "match", re.compile(r", ahead of that day's ")),
    ("Not enough rest after the last round", "match",
     re.compile(r", under \d+ minutes' rest after the last round started\.$")),
    ("A player in three divisions must start earlier", "match",
     re.compile(r" — a player is in 3 divisions that day, and ")),
    ("Before the earliest start for a final", "match",
     re.compile(r", before the \d{1,2}:\d{2} earliest start for a final\.$")),
    ("Before the division's earliest start", "match",
     re.compile(r", before this division's \d{1,2}:\d{2} earliest start\.$")),
    ("Before play opens", "match", re.compile(r", before play opens at \d{1,2}:\d{2}\.$")),
    ("Ends after the day's cutoff", "match", re.compile(r" — past the \d{1,2}:\d{2} cutoff\.$")),
    ("Outside the venue's hours", "match", re.compile(r", outside that venue's hours\.$")),
    ("Against your venue rules", "match", re.compile(r"your venue rules do not allow it")),
    ("Not a tournament day", "match", re.compile(r" is not a tournament day\.$")),
)
OTHER_GROUP = "Other"


def _conflict_divisions(result):
    """The division names on this board, longest first — the only reliable way to read the
    division off a sentence, because a round label is one of eight spellings and a division name
    can hold a comma of its own. Data off the schedule, never a rule."""
    return sorted({str(m.get("event")) for m in ((result or {}).get("schedule") or [])
                   if m.get("event")}, key=len, reverse=True)


def _conflict_division(s, divisions):
    """The division a match-level sentence opens with. Matched against the board's own division
    names, longest first — never parsed out of the punctuation, because `_c_match` puts a comma
    between the division and the round and a division name may carry one."""
    head = s[len("Out of draw order — "):] if s.startswith("Out of draw order — ") else s
    for d in divisions:
        if head.startswith(d):
            return d
    return head.split(",")[0].strip()


def _condense(s, axis, day, label):
    """The row as it prints under its own sub-header: whatever the sub-header already says is
    taken out of the row, and NOTHING else is.

    The day is dropped from `_c_when` alone — the `HH:MM {day}` pair — so the one sentence whose
    day IS the finding ("… Tue 3 Feb is not a tournament day.") keeps it."""
    if axis is None:
        return s
    out = s
    if axis == "person" and label:
        if out.startswith(label + ": "):
            out = out[len(label) + 2:]
    elif axis == "venue" and label and day:
        head = f"{label}, {day}: "
        if out.startswith(head):
            out = out[len(head):]
    elif axis == "match" and label:
        if out.startswith("Out of draw order — "):
            out = out[len("Out of draw order — "):]
        if out.startswith(label + ", "):
            out = out[len(label) + 2:]
        elif out.startswith(label):
            out = out[len(label):].lstrip(" ,")
    if day and axis in ("person", "match"):
        out = _C_WHEN.sub(lambda m: m.group(1) if m.group(2) == day else m.group(0), out)
    return out.strip()


def classify_conflicts(conflicts, divisions=()):
    """Group `result["conflicts"]` for the printed page. Pure, deterministic, side-effect free.

    Returns `[{"title", "axis", "n", "groups": [{"day", "label", "rows": [(condensed, raw)]}]}]`
    in the fixed `_CONFLICT_KINDS` order, with the unmatched sentences last under "Other" —
    where `condensed == raw`, because an unrecognised sentence is printed exactly as written.

    THE FOUR INVARIANTS THIS PAGE IS HELD TO (harness `tests/rpt2_conflicts.py`) all read off
    this structure: the group counts sum to `len(conflicts)`; an unknown sentence prints verbatim
    under "Other"; a sub-header plus its row still names division, round and players; and the
    couriered record — `result["conflicts"]` itself — is untouched full sentences.
    """
    divisions = list(divisions)
    buckets, order = {}, []
    for raw in conflicts:
        s = str(raw)
        title, axis, day, label = OTHER_GROUP, None, "", ""
        for t, a, pat in _CONFLICT_KINDS:
            m = pat.search(s)
            if not m:
                continue
            title, axis = t, a
            gd = m.groupdict()
            label = (gd.get("label") or "").strip()
            day = (gd.get("day") or "").strip()
            break
        if axis and not day:
            d = _C_DAY_RE.search(s)
            day = d.group(0) if d else ""
        if axis == "match":
            label = _conflict_division(s, divisions)
        key = (title, day, label)
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append((_condense(s, axis, day, label), s))

    titles = [t for t, _a, _p in _CONFLICT_KINDS] + [OTHER_GROUP]
    axes = {t: a for t, a, _p in _CONFLICT_KINDS}
    out = []
    for title in titles:
        keys = [k for k in order if k[0] == title]      # first-appearance order, deterministic
        if not keys:
            continue
        groups = [{"day": k[1], "label": k[2], "rows": buckets[k]} for k in keys]
        out.append({"title": title, "axis": axes.get(title),
                    "n": sum(len(g["rows"]) for g in groups), "groups": groups})
    return out


def render_conflicts(result):
    """The engine's conflict list as its own sheet — (svg, w, h) like render_event, or None
    when the list is empty. REVIEW-1 (D2): a couriered edit can breach a rule the engine
    enforces; the engine records the breach in result["conflicts"] in plain English, and
    before this sheet that sentence reached no printed surface. Rendered by BOTH output
    paths (screen HTML and 36x24 PDF) through the same call, first in the set, so a bad
    slot is caught before paper. Absent on a clean run — the sheet count only moves when
    there is something to say.

    RPT-2 (8/7 note 8) did two things to it. **The heading dropped " — resolve before anything
    prints"**: it threatened a gate that does not exist. An accepted conflict publishes (Operator
    ruling 8/7 — recorded, never a failure), the sub-line beneath it has always said "Fix each
    one or accept it", and the heading was contradicting the sentence under it on the page that
    leads the printed pack. **And the flat list became a grouped one** — see `classify_conflicts`.
    """
    conflicts = [str(c) for c in ((result or {}).get("conflicts") or [])]
    if not conflicts:
        return None
    esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    W, LH, SIZE, X = 1500, 24, 15, 48
    grouped = classify_conflicts(conflicts, _conflict_divisions(result))

    # Lay the page out as (indent, space-before, space-after, size, weight, fill, text) lines
    # first, so the height is the MEASURED one rather than an estimate — the same content-sizing
    # discipline the brackets use. A `text` of None is a spacer.
    lines = []
    for grp in grouped:
        lines.append((0, 26, 0, 17, "700", "var(--ink)", f'{grp["title"]}  ({grp["n"]})'))
        for sub in grp["groups"]:
            head = " · ".join([p for p in (sub["day"], sub["label"]) if p])
            if head:
                lines.append((20, 8, 2, 14, "400", "var(--muted)", head))
            for row, _raw in sub["rows"]:
                for i, ln in enumerate(_wrap_words(row, 138 if head else 146)):
                    lines.append((36 if head else 12, 0, 0, SIZE, "400", "var(--ink)",
                                  ("•  " if i == 0 else "   ") + ln))
        lines.append((0, 0, 6, SIZE, "400", "var(--ink)", None))

    H = 128 + sum((LH if t is not None else 0) + pre + post
                  for _x, pre, post, _s, _w, _f, t in lines) + 36
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
         f'<rect x="0" y="0" width="{W}" height="{H}" fill="var(--paper)"/>',
         f'<rect x="0" y="0" width="{W}" height="6" fill="var(--red)"/>',
         f'<text x="{X}" y="52" font-size="26" font-weight="700" fill="var(--red)">'
         f'RULE CONFLICTS</text>',
         f'<text x="{X}" y="80" font-size="14" fill="var(--muted)">'
         f'{len(conflicts)} rule break{"s" if len(conflicts) != 1 else ""} after your edits. '
         f'Fix each one or accept it. This page prints only while the list is not '
         f'empty.</text>']
    y = 118
    for indent, pre, post, size, weight, fill, text in lines:
        y += pre
        if text is not None:
            p.append(f'<text x="{X + indent}" y="{y}" font-size="{size}" '
                     f'font-weight="{weight}" fill="{fill}">{esc(text)}</text>')
            y += LH
        y += post
    p.append("</svg>")
    return "".join(p), W, H

# ---------------------------------------------------------------- elimination
def render_elim(ev, prefix, sched, seeds, subs=None, marks=None, ridx=None, held=None):
    ms = build_elim_teams(ev, prefix)
    by_members = {frozenset(t.members): t for t in ev.teams if not _is_bye_team(t)}
    by_tid = {t.tid: t for t in ev.teams if not _is_bye_team(t)}
    r1 = [m for m in ms if m.rnd == 1]
    size = len(r1) * 2
    rounds = int(math.log2(size))
    rt = lambda r: {0:"Final",1:"Semifinals",2:"Quarterfinals",3:"Round of 16",
                    4:"Round of 32",5:"Round of 64",6:"Round of 128"}.get(rounds-r, f"Round {r}")
    # REKEY-1 (N7/N8/N6b): the printed name comes from the CHANGE MODEL, not from the parsed
    # draw alone. `_team_text` resolves the substituted label, the ratings and the tag together;
    # `seeds` arrives already re-keyed onto the substituted label by `render_event`.
    dbl = _is_doubles_division(ev.name)

    # leaf TEAMS (col 0), top-to-bottom — teams, not label strings, so the substitution map can
    # be applied by tid and the seed looked up on the (possibly re-keyed) label.
    leaves = []
    for m in r1:
        if not m.scheduled_needed:                    # bye walkover
            leaves += [(by_tid[m.decided_team], True), (None, False)]
        else:
            leaves += [(by_members[frozenset(m.team_a)], True),
                       (by_members[frozenset(m.team_b)], True)]

    # Content-sizing pass (③): size the name/slot lane to the longest actual label in
    # this draw so a long name or slot can never overflow its box. Deterministic.
    # REKEY-1: sized from the TAGGED, RATED strings — the ones that actually get drawn. Sizing
    # from the bare label would leave an amber tag or a rating hanging over the connector channel.
    _names = [_tagged(*_team_text(t, subs, ridx, dbl)[::2]) for (t, real) in leaves if real]
    _names += [_tagged(*_team_text(t, subs, ridx, dbl)[::2]) for t in by_tid.values()]
    _names.append("Champion — TBD")
    _slots = [s for s in (_slot_text(sched.get(m.mid), m.mid, marks)[0]
                          for m in ms if m.rnd >= 1) if s]
    # HOLDVIS-1: the held stamp joins the sizing pass like every tag (REKEY-1 §3.3's overflow
    # rule) — it is longer than a slot, and a lane sized without it would let the words run into
    # the connector channel. Only ACTUAL holds are added, so a draw with none sizes to exactly
    # the box it always did.
    _slots += [HELD_TEXT for m in ms if m.rnd >= 1 and m.mid in (held or ())]
    _name_w = max((_text_w(n + " [99]", 17) for n in _names), default=0)
    _slot_w = max((_text_w(s, 13, mono=True) for s in _slots), default=0)
    boxW = max(180, int(_name_w), int(_slot_w)) + 24
    leaf, top, x0, colW = 72, 168, 50, boxW + 40   # keep colW-boxW=40: preserves the connector elbow
    N = size
    H = top + N*leaf + 64
    # REKEY-1: which tags this sheet will draw, resolved BEFORE the page width is fixed — the
    # legend is a full-width line and a narrow draw must not have it run off the paper.
    tags_used = {marks[m.mid] for m in ms
                 if marks and m.mid in marks and _slot_compact(sched.get(m.mid))}
    if subs:
        tags_used.add(TAG_SUB)
    _legend, _legend_w = _legend_svg(x0, H - 26, tags_used)
    W = max(x0 + (rounds+1)*colW + 60, (x0 + _legend_w + 30) if _legend else 0)
    ey = [top + i*leaf + 28 for i in range(N)]
    ys = {0: ey}
    for r in range(1, rounds+1):
        ys[r] = [(ys[r-1][2*m]+ys[r-1][2*m+1])/2 for m in range(len(ys[r-1])//2)]
    colx = [x0 + c*colW for c in range(rounds+1)]
    known_after = {m.mid: (m.decided_team if not m.scheduled_needed else None) for m in ms}
    mid_by = {m.mid: m for m in ms}

    S = [f'<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">']
    S.append(f'<rect width="{W}" height="{H}" fill="var(--paper)"/>')
    S.append(f'<text x="{x0}" y="50" font-size="28" font-weight="700" fill="var(--ink)">{ev.name}</text>')
    S.append(f'<text x="{x0}" y="80" font-size="16" fill="var(--muted)">USTA Wilson World Tennis Classic · Main draw · single elimination, {N}-draw</text>')
    S.append(f'<line x1="{x0}" y1="98" x2="{W-30}" y2="98" stroke="var(--court)" stroke-width="2.5"/>')
    S.append(f'<text x="{colx[0]}" y="128" font-size="14" font-weight="700" letter-spacing="1.2" fill="var(--court-d)">DRAW</text>')
    for r in range(1, rounds+1):
        S.append(f'<text x="{colx[r]}" y="128" font-size="14" font-weight="700" letter-spacing="1.2" fill="var(--court-d)">{rt(r).upper()}</text>')

    def cell(x,y,txt,seed=None,muted=False,strong=False,tag=None):
        f = "var(--amber)" if tag else ("var(--muted)" if muted else "var(--ink)")
        w = "700" if (seed or strong) else "500"
        t = f'<text x="{x}" y="{y-5}" font-size="17" font-weight="{w}" fill="{f}">{txt}'
        if seed: t += f' <tspan fill="var(--court-d)">[{seed}]</tspan>'
        if tag: t += f' · {tag}'          # never colour alone (ruled): the mark is TEXT too
        t += '</text>'
        ln = "var(--amber-line)" if tag else "var(--line)"
        t += f'<line x1="{x}" y1="{y}" x2="{x+boxW}" y2="{y}" stroke="{ln}" stroke-width="1.2"/>'
        return t

    for i,(t_,real) in enumerate(leaves):
        txt, key, tag = _team_text(t_, subs, ridx, dbl)
        S.append(cell(colx[0], ey[i], txt, seed=seeds.get(key) if real else None,
                      muted=not real, tag=tag))

    for r in range(1, rounds+1):
        for m in range(size // (2**r)):
            ymid = ys[r][m]; y1,y2 = ys[r-1][2*m], ys[r-1][2*m+1]
            cx = colx[r]-30; xp = colx[r-1]+boxW
            S.append(f'<path d="M{xp} {y1} H{cx} V{y2} H{xp}" fill="none" stroke="var(--line-2)" stroke-width="1.6"/>')
            S.append(f'<path d="M{cx} {ymid} H{colx[r]}" fill="none" stroke="var(--line-2)" stroke-width="1.6"/>')
            mid = f"{prefix}-R{r}-M{m+1}"; mm = mid_by.get(mid)
            if mm is not None and not mm.scheduled_needed:
                lab, col = "BYE — walkover", "var(--muted)"
            else:
                s, amber = _slot_text(sched.get(mid), mid, marks)
                lab = s or _no_slot_text(mid, held)      # HOLDVIS-1: words, not amber
                col = "var(--court-d)" if s else "var(--red)"
                if amber:
                    col = "var(--amber)"
            # slot gets its own lane (②): left-aligned under the winner cell, below its
            # underline — never centered in the inter-column channel, so it cannot touch
            # a name or a bracket line.
            S.append(f'<text x="{colx[r]}" y="{ymid+16}" font-size="13" font-family="var(--font-mono)" fill="{col}">{lab}</text>')
            # winner placeholder; show a known bye-advancer if this is that match
            if r < rounds:
                adv = known_after.get(mid)
                if adv:
                    ntxt, _k, ntag = _team_text(by_tid[adv], subs, ridx, dbl)
                    S.append(cell(colx[r], ymid, ntxt, tag=ntag))
                else:
                    S.append(cell(colx[r], ymid, "—", muted=True))
            else:
                S.append(cell(colx[r], ymid, "Champion — TBD", muted=True, strong=True))
    if _legend:
        S.append(_legend)
    S.append('</svg>')
    return "\n".join(S), W, H

# ---------------------------------------------------------------- round robin
def _rr_next(i, ms, idx, teams, sched):
    """E3: the RR player at row i's *next* match — the earliest-scheduled pairing
    that player is in. Tie-break: location ascending, then match mid ascending, so
    the render is deterministic across runs. Returns the sentinel 'Next: —' when
    the player has no scheduled pairing (no crash). Stateless by design: 'next'
    is earliest-*scheduled*, not next-*unplayed* (v1 has no results/state model)."""
    cands = []
    for m in ms:
        ia, ib = idx[frozenset(m.team_a)], idx[frozenset(m.team_b)]
        if i not in (ia, ib):
            continue
        row = sched.get(m.mid)
        if not row or not row.get("day"):
            continue
        start = _dt.datetime.strptime(f"{row['day']} {row['start']}", "%Y-%m-%d %H:%M")
        opp = ib if i == ia else ia
        cands.append((start, row.get("location") or "", m.mid, opp))
    if not cands:
        return "Next: —"
    _s, _c, mid, opp = min(cands, key=lambda c: (c[0], c[1], c[2]))
    return f"Next: vs {teams[opp].label()} · {_slot(sched.get(mid))}"

def render_rr(ev, prefix, sched, seeds, subs=None, marks=None, ridx=None, held=None):
    ms = build_rr_teams(ev, prefix)
    teams = ev.teams
    idx = {frozenset(t.members): i for i,t in enumerate(teams)}
    n = len(teams)
    dbl = _is_doubles_division(ev.name)
    cell_h, x0, y0 = 74, 460, 168
    cellslot, cellamber, cellheld = {}, {}, {}
    for m in ms:
        ia, ib = idx[frozenset(m.team_a)], idx[frozenset(m.team_b)]
        # REKEY-1 (N8): the cross-table cell is this format's slot stamp, so it is where a
        # locked-day shift or a hand edit reads on a round-robin sheet. `_slot` is the verbose
        # form here (its own wide lane), and the tag rides on its second stacked line.
        cellslot[(ia,ib)] = cellslot[(ib,ia)] = _slot(sched.get(m.mid))
        tag = (marks or {}).get(m.mid)
        if tag and cellslot[(ia, ib)]:
            cellamber[(ia,ib)] = cellamber[(ib,ia)] = tag
        # HOLDVIS-1: this format's own stamp lane. A held match leaves `_slot` returning None,
        # and the cell then printed a bare em dash — indistinguishable from a pairing the grid
        # simply has no row for. The 2026 field cannot exercise this (all 3 of the run's holds
        # are elimination-lane), so it is proven on a crafted fixture instead.
        if cellslot[(ia, ib)] is None and m.mid in (held or ()):
            cellheld[(ia,ib)] = cellheld[(ib,ia)] = True
    _next = [_rr_next(i, ms, idx, teams, sched) for i in range(n)]
    # content-size the cross-table cell and the Next column (③) so the two-line cell
    # slot and the verbose Next string can never bleed past their lanes. Deterministic.
    _lines, _hdrs = [], [(t.members[0].split()[-1].upper() if t.members else "") for t in teams]
    for k, s in cellslot.items():
        if s:
            # REKEY-1: sized from the TAGGED second line, the one that is actually drawn.
            p = s.split(" · ")
            tail = " · ".join(p[1:])
            if cellamber.get(k):
                tail = f"{tail} · {cellamber[k]}"
            _lines += [p[0], tail]
    if cellheld:
        _lines.append(HELD_TEXT)      # HOLDVIS-1: sized from what is actually drawn
    cell_w = max(230,
                 int(max((_text_w(x, 12.5, mono=True) for x in _lines), default=0)) + 28,
                 int(max((_text_w(h, 14) for h in _hdrs), default=0)) + 20)
    nameW = x0 - 60
    grid_r = x0 + n*cell_w           # right edge of the cross-table
    next_x = grid_r + 24             # left edge of the E3 "Next match" column
    next_w = max(480, int(max((_text_w(x, 14, mono=True) for x in _next), default=0)) + 24)
    H = y0 + n*cell_h + 70
    tags_used = set(cellamber.values())
    if subs:
        tags_used.add(TAG_SUB)
    _legend, _legend_w = _legend_svg(50, H - 28, tags_used)
    W = max(next_x + next_w + 30, (50 + _legend_w + 30) if _legend else 0)

    S = [f'<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">']
    S.append(f'<rect width="{W}" height="{H}" fill="var(--paper)"/>')
    S.append(f'<text x="50" y="50" font-size="28" font-weight="700" fill="var(--ink)">{ev.name}</text>')
    S.append(f'<text x="50" y="80" font-size="16" fill="var(--muted)">USTA Wilson World Tennis Classic · Main draw · round robin, Group 1</text>')
    S.append(f'<line x1="50" y1="98" x2="{W-30}" y2="98" stroke="var(--court)" stroke-width="2.5"/>')
    # column headers (opponents)
    for j,t in enumerate(teams):
        cx = x0 + j*cell_w + cell_w/2
        S.append(f'<text x="{cx}" y="{y0-14}" font-size="14" font-weight="700" text-anchor="middle" fill="var(--court-d)">{t.members[0].split()[-1].upper() if t.members else ""}</text>')
    # E3: "Next match" column header (right of the cross-table)
    S.append(f'<text x="{next_x}" y="{y0-14}" font-size="14" font-weight="700" fill="var(--court-d)">NEXT MATCH</text>')
    for i,t in enumerate(teams):
        ry = y0 + i*cell_h
        # REKEY-1 (N7/N6b): the substituted label, its ratings and its tag; the seed follows the
        # ruled `seed_effect` because `seeds` arrives re-keyed onto the new label.
        ttxt, tkey, ttag = _team_text(t, subs, ridx, dbl)
        sd = seeds.get(tkey)
        nm = _tagged(ttxt, ttag, sd)          # never colour alone: the tag is TEXT
        tf = "var(--amber)" if ttag else "var(--ink)"
        S.append(f'<text x="50" y="{ry+cell_h/2+5}" font-size="17" font-weight="{ "700" if sd else "500"}" fill="{tf}">{i+1}. {nm}</text>')
        for j in range(n):
            cx = x0 + j*cell_w
            if i == j:
                S.append(f'<rect x="{cx}" y="{ry}" width="{cell_w}" height="{cell_h}" fill="#e7e4dc" stroke="var(--line)"/>')
            else:
                S.append(f'<rect x="{cx}" y="{ry}" width="{cell_w}" height="{cell_h}" fill="#fff" stroke="var(--line)"/>')
                s = cellslot.get((i,j))
                if s:
                    # split "Mon Jan 26 · 13:30–15:00 · MHCC" into two stacked lines
                    parts = s.split(" · ")
                    line1 = parts[0]                              # day + date
                    line2 = " · ".join(parts[1:]) if len(parts) > 1 else ""
                    ctag = cellamber.get((i,j))
                    ccol = "var(--amber)" if ctag else "var(--court-d)"
                    if ctag:
                        line2 = f"{line2} · {ctag}"               # never colour alone
                    cy = ry + cell_h/2
                    S.append(f'<text x="{cx+cell_w/2}" y="{cy-4}" font-size="12.5" font-family="var(--font-mono)" text-anchor="middle" fill="{ccol}">{line1}</text>')
                    S.append(f'<text x="{cx+cell_w/2}" y="{cy+14}" font-size="12.5" font-family="var(--font-mono)" text-anchor="middle" fill="{ccol}">{line2}</text>')
                elif cellheld.get((i,j)):
                    # HOLDVIS-1 (ruling 2): words, red, no amber — the same treatment the
                    # elimination stamp lane gets, in this format's own cell.
                    S.append(f'<text x="{cx+cell_w/2}" y="{ry+cell_h/2+5}" font-size="12.5" font-family="var(--font-mono)" text-anchor="middle" fill="var(--red)">{HELD_TEXT}</text>')
                else:
                    S.append(f'<text x="{cx+cell_w/2}" y="{ry+cell_h/2+5}" font-size="12.5" font-family="var(--font-mono)" text-anchor="middle" fill="var(--muted)">—</text>')
        # E3: per-player next-match annotation (earliest-scheduled; see _rr_next)
        S.append(f'<text x="{next_x}" y="{ry+cell_h/2+5}" font-size="14" '
                 f'font-family="var(--font-mono)" fill="var(--court-d)">'
                 f'{_next[i]}</text>')
    if _legend:
        S.append(_legend)
    S.append('</svg>')
    return "\n".join(S), W, H

# ----------------------------------------------- elimination (wide / facing)
def render_elim_wide(ev, prefix, sched, seeds, subs=None, marks=None, ridx=None, held=None):
    """Facing-bracket layout for large draws (>=64). The bracket is split into a
    top half drawn left->center and a bottom half drawn right->center, meeting at
    the final in the middle. This halves the height and uses the full page width,
    turning a tall 1:3 draw into a landscape-native sheet that fits one 36x24 page
    at a readable font. Geometry differs from render_elim; match/slot semantics
    are identical."""
    ms = build_elim_teams(ev, prefix)
    by_members = {frozenset(t.members): t for t in ev.teams if not _is_bye_team(t)}
    by_tid = {t.tid: t for t in ev.teams if not _is_bye_team(t)}
    r1 = [m for m in ms if m.rnd == 1]
    size = len(r1) * 2
    rounds = int(math.log2(size))
    rt = lambda r: {0:"Final",1:"Semifinals",2:"Quarterfinals",3:"Round of 16",
                    4:"Round of 32",5:"Round of 64",6:"Round of 128"}.get(rounds-r, f"Round {r}")
    mid_by = {m.mid: m for m in ms}
    known_after = {m.mid: (m.decided_team if not m.scheduled_needed else None) for m in ms}
    dbl = _is_doubles_division(ev.name)          # REKEY-1: same model as render_elim

    # leaf TEAMS for round 1, top-to-bottom (same as render_elim)
    leaves = []
    for m in r1:
        if not m.scheduled_needed:
            leaves += [(by_tid[m.decided_team], True), (None, False)]
        else:
            leaves += [(by_members[frozenset(m.team_a)], True),
                       (by_members[frozenset(m.team_b)], True)]

    # Content-sizing pass (③): size the name/slot lane to the longest actual label.
    # REKEY-1: from the TAGGED, RATED strings — the ones that are drawn.
    _names = [_tagged(*_team_text(t, subs, ridx, dbl)[::2]) for (t, real) in leaves if real]
    _names += [_tagged(*_team_text(t, subs, ridx, dbl)[::2]) for t in by_tid.values()]
    _names.append("Champion — TBD")
    _slots = [s for s in (_slot_text(sched.get(m.mid), m.mid, marks)[0]
                          for m in ms if m.rnd >= 1) if s]
    _slots += [HELD_TEXT for m in ms if m.rnd >= 1 and m.mid in (held or ())]   # HOLDVIS-1
    _name_w = max((_text_w(n + " [99]", 15.5) for n in _names), default=0)
    _slot_w = max((_text_w(s, 12, mono=True) for s in _slots), default=0)
    boxW = max(160, int(_name_w), int(_slot_w)) + 20
    leaf, top, x0, colW = 56, 168, 50, boxW + 52   # keep colW-boxW=52: preserves the facing connectors
    side_rounds = rounds - 1                      # columns each side, before the center final
    half_leaves = size // 2
    H = top + half_leaves*leaf + 64
    centerW = colW                               # width reserved for the center final column
    tags_used = {marks[m.mid] for m in ms
                 if marks and m.mid in marks and _slot_compact(sched.get(m.mid))}
    if subs:
        tags_used.add(TAG_SUB)
    _legend, _legend_w = _legend_svg(x0, H - 26, tags_used)
    W = max(x0 + side_rounds*colW + centerW + side_rounds*colW + colW + 50,
            (x0 + _legend_w + 30) if _legend else 0)

    # leaf y-centers for ONE side (half the draw)
    ey = [top + i*leaf + 24 for i in range(half_leaves)]
    # y positions per round, per side: ys_side[r] holds centers for that side's round r
    ys_side = {0: ey}
    for r in range(1, side_rounds+1):
        ys_side[r] = [(ys_side[r-1][2*m]+ys_side[r-1][2*m+1])/2 for m in range(len(ys_side[r-1])//2)]

    # left columns march right; right columns march left (mirrored)
    left_x  = [x0 + c*colW for c in range(side_rounds+1)]
    right_x = [W - 50 - boxW - c*colW for c in range(side_rounds+1)]
    center_x = x0 + side_rounds*colW + (centerW - boxW)//2 + 20

    S = [f'<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">']
    S.append(f'<rect width="{W}" height="{H}" fill="var(--paper)"/>')
    S.append(f'<text x="{x0}" y="50" font-size="28" font-weight="700" fill="var(--ink)">{ev.name}</text>')
    S.append(f'<text x="{x0}" y="80" font-size="16" fill="var(--muted)">USTA Wilson World Tennis Classic · Main draw · single elimination, {size}-draw (facing bracket)</text>')
    S.append(f'<line x1="{x0}" y1="98" x2="{W-30}" y2="98" stroke="var(--court)" stroke-width="2.5"/>')

    def cell(x,y,txt,seed=None,muted=False,strong=False,anchor_end=False,tag=None):
        f = "var(--amber)" if tag else ("var(--muted)" if muted else "var(--ink)")
        w = "700" if (seed or strong) else "500"
        a = ' text-anchor="end"' if anchor_end else ''
        tx = x+boxW if anchor_end else x
        t = f'<text x="{tx}" y="{y-5}" font-size="15.5" font-weight="{w}" fill="{f}"{a}>{txt}'
        if seed: t += f' <tspan fill="var(--court-d)">[{seed}]</tspan>'
        if tag: t += f' · {tag}'          # never colour alone (ruled): the mark is TEXT too
        t += '</text>'
        ln = "var(--amber-line)" if tag else "var(--line)"
        t += f'<line x1="{x}" y1="{y}" x2="{x+boxW}" y2="{y}" stroke="{ln}" stroke-width="1.2"/>'
        return t

    def slot_label(mid, x, y, anchor_end=False):
        # Compact slot in its own lane (② ③): under the winner cell, aligned to the
        # same edge (start for the left side, end for the mirrored right side), below
        # the cell's underline — never in the inter-column channel.
        mm = mid_by.get(mid)
        if mm is not None and not mm.scheduled_needed:
            lab, col = "BYE — walkover", "var(--muted)"
        else:
            s, amber = _slot_text(sched.get(mid), mid, marks)
            lab = s or _no_slot_text(mid, held)          # HOLDVIS-1: words, not amber
            col = "var(--amber)" if amber else ("var(--court-d)" if s else "var(--red)")
        a = ' text-anchor="end"' if anchor_end else ''
        return f'<text x="{x}" y="{y}" font-size="12" font-family="var(--font-mono)"{a} fill="{col}">{lab}</text>'

    # round labels across the top: left side then center then right side
    for c in range(side_rounds+1):
        S.append(f'<text x="{left_x[c]}" y="128" font-size="13" font-weight="700" letter-spacing="1.1" fill="var(--court-d)">{(rt(c) if c else "DRAW").upper()}</text>')
    S.append(f'<text x="{center_x+boxW/2}" y="128" font-size="13" font-weight="700" letter-spacing="1.1" text-anchor="middle" fill="var(--court-d)">FINAL</text>')
    for c in range(1, side_rounds+1):
        S.append(f'<text x="{right_x[c]+boxW}" y="128" font-size="13" font-weight="700" letter-spacing="1.1" text-anchor="end" fill="var(--court-d)">{rt(c).upper()}</text>')

    # how many round-1 matches per side
    half_r1 = len(r1) // 2

    def side(matches_filter, xcols, mirror):
        # leaf cells (round 0)
        for li in range(half_leaves):
            gi = li if not mirror else half_leaves + li
            t_, real = leaves[gi]
            txt, key, tag = _team_text(t_, subs, ridx, dbl)
            x = xcols[0]
            S.append(cell(x, ey[li], txt,
                          seed=seeds.get(key) if real else None, muted=not real,
                          anchor_end=mirror, tag=tag))
        # inner rounds 1..side_rounds, drawing connectors + winner cells + slots
        for r in range(1, side_rounds+1):
            for m in range(half_leaves // (2**r)):
                ymid = ys_side[r][m]; y1,y2 = ys_side[r-1][2*m], ys_side[r-1][2*m+1]
                if not mirror:
                    cx = xcols[r]-30; xp = xcols[r-1]+boxW
                    S.append(f'<path d="M{xp} {y1} H{cx} V{y2} H{xp}" fill="none" stroke="var(--line-2)" stroke-width="1.6"/>')
                    S.append(f'<path d="M{cx} {ymid} H{xcols[r]}" fill="none" stroke="var(--line-2)" stroke-width="1.6"/>')
                else:
                    cx = xcols[r]+boxW+30; xp = xcols[r-1]
                    S.append(f'<path d="M{xp} {y1} H{cx} V{y2} H{xp}" fill="none" stroke="var(--line-2)" stroke-width="1.6"/>')
                    S.append(f'<path d="M{cx} {ymid} H{xcols[r]+boxW}" fill="none" stroke="var(--line-2)" stroke-width="1.6"/>')
                # match id for this side's round r, node m
                gm = m if not mirror else (half_leaves // (2**r)) + m
                mid = f"{prefix}-R{r}-M{gm+1}"
                slot_x = (xcols[r]+boxW) if mirror else xcols[r]
                S.append(slot_label(mid, slot_x, ymid+15, anchor_end=mirror))
                adv = known_after.get(mid)
                if adv:
                    ntxt, _k, ntag = _team_text(by_tid[adv], subs, ridx, dbl)
                    S.append(cell(xcols[r], ymid, ntxt, anchor_end=mirror, tag=ntag))
                else:
                    S.append(cell(xcols[r], ymid, "—", muted=True, anchor_end=mirror))

    side(None, left_x, mirror=False)
    side(None, right_x, mirror=True)

    # center final: both sides' semifinal nodes sit at the same y (mirrored layout),
    # so the final box sits just below that shared line, fed from left and right.
    semi_y = ys_side[side_rounds][0]
    lsemi_x = left_x[side_rounds] + boxW
    rsemi_x = right_x[side_rounds]
    cfx = center_x
    final_y = semi_y + leaf            # drop the final box one leaf-row below the semis
    # elbow connectors from each semifinal into the centered final line
    S.append(f'<path d="M{lsemi_x} {semi_y} H{cfx-30} V{final_y} H{cfx}" fill="none" stroke="var(--line-2)" stroke-width="1.8"/>')
    S.append(f'<path d="M{rsemi_x} {semi_y} H{cfx+boxW+30} V{final_y} H{cfx+boxW}" fill="none" stroke="var(--line-2)" stroke-width="1.8"/>')
    final_mid = f"{prefix}-R{rounds}-M1"
    S.append(cell(cfx, final_y+30, "Champion — TBD", muted=True, strong=True))
    S.append(slot_label(final_mid, cfx, final_y+30+15))

    if _legend:
        S.append(_legend)
    S.append('</svg>')
    return "\n".join(S), W, H


def render_event(cfg, ev, result, seeds_by_event, locked_day_shifts=None, roster=None):
    """Return (svg_string, width, height). Width/height let the PDF path fit each
    sheet to the 36x24 page while preserving aspect.

    REKEY-1 (A7a): the change model is derived HERE, not in `render_all`. `render_all_pdf`
    calls this function DIRECTLY, never through `render_all`, so a map built one level up
    would fix the screen HTML and leave the 36x24" plotter PDF printing the substituted-out
    player with his kept seed — the same defect on the surface that actually goes on the wall.
    Deriving it here fixes both output paths and leaves every existing call site unchanged.
    """
    prefix = _prefix_for(cfg, ev)
    sched = {r["id"]: r for r in result["schedule"]}
    subs = _subs_for(ev, substitutions(cfg, result))
    seeds = _rekey_seeds(seeds_by_event.get(ev.name, {}), subs)
    marks = changed_matches(result, locked_day_shifts)
    # HOLDVIS-1 (§3.4): the held set is derived HERE for the same reason the change model is —
    # `render_all_pdf` calls this function DIRECTLY, never through `render_all`, so a set built
    # one level up would put the words on the screen sheets and leave the 36x24" plotter PDF
    # printing a bare "not scheduled" on the sheet that actually goes on the wall.
    held = held_matches(result)
    ridx = _roster_by_name(roster)
    if ev.fmt in ("single_elim","compass"):
        # large draws (>=64) reshape to a landscape-native facing bracket so they
        # fill a 36x24 page at readable size; <=32 keep the validated tall layout.
        size = 1
        while size < len(ev.teams):
            size *= 2
        if size >= 64:
            return render_elim_wide(ev, prefix, sched, seeds, subs=subs, marks=marks, ridx=ridx,
                                    held=held)
        return render_elim(ev, prefix, sched, seeds, subs=subs, marks=marks, ridx=ridx, held=held)
    if ev.fmt == "round_robin":
        return render_rr(ev, prefix, sched, seeds, subs=subs, marks=marks, ridx=ridx, held=held)
    raise ValueError(f"no renderer for fmt {ev.fmt}")

PAGE = """<!doctype html>
<meta charset="utf-8"><style>
:root{{--paper:#F3F1EA;--ink:#15201b;--muted:#7c7f78;--line:#c9cdc4;--line-2:#d8dcd2;
--court:#1f6e55;--court-d:#16523d;--red:#a8323f;
--amber:#9C5F0E;--amber-bg:#F7F0E3;--amber-line:#E6D6B6;
--font-mono:ui-monospace,'SF Mono',Menlo,Consolas,monospace;}}
body{{margin:0;background:#e7e4dc;font-family:system-ui,-apple-system,'Segoe UI',Helvetica,Arial,sans-serif}}
.nav{{position:sticky;top:0;background:#16523d;color:#fff;padding:10px 18px;font-size:13px;z-index:9;
box-shadow:0 1px 6px rgba(0,0,0,.2)}}
.nav b{{font-weight:700}} .nav a{{color:#cdebd9;text-decoration:none;margin-right:14px}}
.nav a:hover{{text-decoration:underline}}
.sheet{{background:var(--paper);margin:20px auto;max-width:1600px;box-shadow:0 1px 6px rgba(0,0,0,.12);
border-radius:6px;overflow-x:auto;overflow-y:hidden}}
/* On screen, render each SVG at its designed (natural) size so slot labels keep
   legible proportions; each sheet scrolls inside its own container (overflow-x)
   rather than being squashed to page width. The page body never scrolls sideways. */
svg{{display:block;max-width:none}}

/* Print: 36x24" landscape plotter sheets, one division per page. */
@media print{{
  @page{{size:36in 24in landscape;margin:0.5in;}}
  body{{background:#fff;}}
  .nav{{display:none !important;}}
  .sheet{{margin:0;max-width:none;box-shadow:none;border-radius:0;overflow:visible;
    break-after:page;page-break-after:always;}}
  .sheet:last-child{{break-after:auto;page-break-after:auto;}}
  /* fit each sheet's SVG within one landscape page, aspect preserved */
  svg{{width:100%;height:auto;max-height:23in;}}
}}
</style>
<div class="nav"><b>WWTC draw sheets</b> &nbsp; {links}</div>
{sheets}"""

def sheet_order(cfg):
    """DIV-1 (rule 44): the divisions in the TD's ONE display order — the order BOTH sheet paths
    print in.

    Written once and called by `render_all` and `render_all_pdf` together, so the screen set and
    the printed set can never come out in different orders. Measured before DIV-1: 49 of 51
    sheets sat outside the TD's order, the worst travelling 45 places.

    `cfg.events` is the ENGINE's list and is never re-ordered in place — this returns a sorted
    copy. `tests/div1_order.py` asserts the result against the expected order, which is how the
    PDF path's ordering is covered: it needs `cairosvg` + `pypdf` to run at all, so its own
    output is not exercised by the suite.
    """
    return DO.sorted_by(cfg.events, lambda e: e.name,
                        getattr(cfg, "mixed_level_1_resolved", None) or ())


def render_all(cfg, result, seeds_by_event, out="/mnt/user-data/outputs/wwtc_draw_sheets.html",
               locked_day_shifts=None, roster=None):
    """REKEY-1 (A7a) adds two KEYWORD-WITH-DEFAULT parameters, so all nine existing call sites
    keep working untouched:
      locked_day_shifts — the structure `wwtc_pipeline` emits beside `master_warnings`. It is
                          NOT in `result` and cannot be derived from it. Omitted -> no
                          locked-day marks.
      roster            — `build["players"]`, for the WTN beside each name (N6b). Omitted -> no
                          ratings.
    The runbook's Step-6 call passes BOTH: a keyword-with-default the product lane never passes
    is a feature that ships inert, which is exactly what ENG-1/D-41 recorded on same-day finish.
    """
    # DIV-1 (rule 44): the sheets print in the TD's ONE division order, not the order the engine
    # happened to place matches in. Anchors stay tied to the EVENT's position in `cfg.events`
    # (not to the loop index), so a sheet's `#evN` link is the same before and after this change
    # and any bookmark into the printed set still resolves.
    links, sheets = [], []
    # REVIEW-1 (D2): the engine's conflict list leads the set — the wall document is the one
    # deliverable that always gets printed, so a breach recorded after a hand edit is caught
    # by the person about to print it. No conflicts, no sheet, no link.
    con = render_conflicts(result)
    if con:
        links.append('<a href="#conflicts" style="color:#ffd7dc;font-weight:700">&#9888; Conflicts</a>')
        sheets.append(f'<div class="sheet" id="conflicts">{con[0]}</div>')
    for ev in sheet_order(cfg):
        anchor = "ev" + str(cfg.events.index(ev)+1)
        links.append(f'<a href="#{anchor}">{ev.name}</a>')
        svg, _w, _h = render_event(cfg, ev, result, seeds_by_event,
                                   locked_day_shifts=locked_day_shifts, roster=roster)
        sheets.append(f'<div class="sheet" id="{anchor}">{svg}</div>')
    html = PAGE.format(links=" ".join(links), sheets="\n".join(sheets))
    _ensure_dir(out)   # F7-5: portable across surfaces — create the target dir, don't assume it
    open(out,"w").write(html)
    return out


def _ensure_dir(path):
    import os
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)


# ------------------------------------------------- REKEY-1: N9, the re-enter page
REKEY_PAGE = """<!doctype html>
<meta charset="utf-8"><title>Re-enter at the desk</title><style>
:root{{--paper:#F3F1EA;--ink:#15201b;--muted:#7c7f78;--line:#c9cdc4;--line-2:#d8dcd2;
--court:#1f6e55;--court-d:#16523d;--amber:#9C5F0E;--amber-bg:#F7F0E3;--amber-line:#E6D6B6;
--font-mono:ui-monospace,'SF Mono',Menlo,Consolas,monospace;}}
body{{margin:0;background:#e7e4dc;color:var(--ink);
font-family:system-ui,-apple-system,'Segoe UI',Helvetica,Arial,sans-serif}}
.page{{background:var(--paper);max-width:1000px;margin:20px auto;padding:32px 40px 40px;
box-shadow:0 1px 6px rgba(0,0,0,.12);border-radius:6px}}
h1{{margin:0;font-size:28px}}
.sub{{margin:6px 0 0;color:var(--muted);font-size:15px}}
.rule{{height:2.5px;background:var(--court);margin:14px 0 26px}}
h2{{font-size:19px;margin:30px 0 8px;color:var(--court-d)}}
table{{width:100%;border-collapse:collapse;font-size:15px}}
th{{text-align:left;font-size:12px;letter-spacing:1.1px;text-transform:uppercase;
color:var(--court-d);border-bottom:1.5px solid var(--line);padding:4px 10px 4px 0}}
td{{padding:8px 10px 8px 0;border-bottom:1px solid var(--line-2);vertical-align:top}}
td.was{{color:var(--muted);font-family:var(--font-mono);font-size:13.5px;white-space:nowrap}}
td.now{{color:var(--amber);font-family:var(--font-mono);font-size:13.5px;font-weight:700;
white-space:nowrap}}
.note{{display:block;color:var(--muted);font-size:13px;font-weight:400;font-family:inherit;
white-space:normal;margin-top:3px}}
.empty{{color:var(--muted);font-size:16px}}
@media print{{@page{{size:letter portrait;margin:0.5in}}body{{background:#fff}}
.page{{margin:0;max-width:none;box-shadow:none;border-radius:0;padding:0}}
section{{break-inside:avoid;page-break-inside:avoid}}}}
</style>
<div class="page"><h1>Re-enter at the desk</h1>
<p class="sub">{sub}</p><div class="rule"></div>
{body}</div>"""


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _when(day, start=None, location=None):
    """`Sun 25 Jan · 12:30 · MHCC` — the slot as the desk holds it. `_c_day` is LANG-1's."""
    if not day:
        return "not scheduled"
    return " · ".join(x for x in (_c_day(day), start, location) if x)


def _expand_winner_of(s):
    """`winner of R1 M15` -> `winner of Round 1 match 15`. The conflicts sheet's compact form is
    right for a crowded red page; this page is a keying checklist read one line at a time, so it
    spells the round out the way the Edit console's own card does."""
    return re.sub(r"winner of R(\d+) M(\d+)", r"winner of Round \1 match \2", s)


def _rekey_rows(cfg, result, locked_day_shifts=None):
    """`[(division, [row, ...]), ...]` — the run's complete change list, grouped ONE DRAW AT A
    TIME (workbook rule N5) in the TD's own division order.

    Three change kinds, all named by division, round and players and never by internal id: the
    hand-edited slots (with the slot they are LEAVING, from the `from` the engine now records),
    the substitutions, and the rounds a locked final dragged onto another day.
    """
    subs = substitutions(cfg, result)
    by_event: dict = {}
    cache: dict = {}

    def matches_of(ev):
        if ev.name not in cache:
            cache[ev.name] = _event_matches(ev, _prefix_for(cfg, ev))
        return cache[ev.name]

    def event_of(mid):
        g = re.match(r"^E(\d+)-", mid or "")
        if not g:
            return None
        i = int(g.group(1)) - 1
        return cfg.events[i] if 0 <= i < len(cfg.events) else None

    def add(ev, row):
        by_event.setdefault(ev.name, []).append(row)

    def named(ev, mid):
        m = next((x for x in matches_of(ev) if x.mid == mid), None)
        if m is None:
            return ""
        return _expand_winner_of(f"{_round_of(ev, m.rnd)} — {_c_players(m)}")

    def _round_of(ev, rnd):
        ms = matches_of(ev)
        m = next((x for x in ms if x.rnd == rnd), None)
        if m is None or m.draw == "rr" or rnd is None:
            return f"Round {rnd}"
        fin = _final_rounds(ms, cfg).get(ev.name)
        return _round_name(rnd, fin) if fin else f"Round {rnd}"

    for e in (result.get("applied_edits") or ()):
        ev = event_of(e.get("id"))
        if ev is None:
            continue
        if e.get("op") in ("move", "pin") and e.get("result") == "placed":
            frm = e.get("from") or {}
            add(ev, {"what": named(ev, e["id"]),
                     "was": _when(frm.get("day"), frm.get("start"), frm.get("location")),
                     "now": _when(e.get("day"), e.get("start"), e.get("location")),
                     "note": ""})
        elif e.get("op") == "substitute" and e.get("result") == "substituted":
            s = next((v for k, v in subs.items()
                      if k[0] == ev.name and v["id"] == e.get("id")), None)
            eff = (e.get("seed_effect") or "").strip()
            note = ""
            if eff == "kept":
                # The recorded reason prints VERBATIM — no rewording, no redaction
                # (Operator ruling, 2026-08-07).
                note = "Seed stays with the team"
                note += (f" — {e['seed_kept_reason']}" if e.get("seed_kept_reason") else ".")
            elif eff:
                note = "Seed dropped."
            add(ev, {"what": named(ev, e["id"]),
                     "was": e.get("out_name") or "",
                     "now": (s["in_name"] if s else e.get("in_name")) or "",
                     "note": note})

    # HOLDVIS-1 (ruling 3): a held match is a DESK INSTRUCTION — Tournament Desk is still holding
    # a slot that should now be empty, and nothing else on the printed set tells the desk to take
    # it out. Read from `result["held"]`, which is derived from the ids still unplaced after the
    # whole document, so a hold the TD re-placed with a later move produces no row here (the
    # phantom-row risk). REKEY-1 recorded "a hold records no old slot" as a stated limitation;
    # the engine now records it, so the Was column is real.
    for h in (result.get("held") or ()):
        ev = event_of(h.get("id"))
        if ev is None:
            continue
        frm = h.get("from") or {}
        add(ev, {"what": named(ev, h["id"]),
                 "was": _when(frm.get("day"), frm.get("start"), frm.get("location")),
                 "now": HELD_TEXT, "note": ""})

    for sh in (locked_day_shifts or ()):
        ev = next((x for x in cfg.events if x.name == sh.get("event")), None)
        if ev is None:
            continue
        # A whole round moved, so the row names the round and says how many rows that is to
        # key — the desk worker's actual question. Counted off the schedule, never guessed.
        want = set(sh.get("match_rounds") or ([sh.get("round")] if sh.get("round") else []))
        n = sum(1 for row in (result.get("schedule") or ())
                if row.get("event") == ev.name and row.get("round") in want)
        add(ev, {"what": f"{_round_of(ev, sh.get('round'))} — {n} match"
                         f"{'es' if n != 1 else ''}",
                 "was": _when(sh.get("was")), "now": _when(sh.get("now")),
                 "note": "The final is held to a locked day, so this round moved with it."})

    return [(ev.name, by_event[ev.name]) for ev in sheet_order(cfg) if ev.name in by_event]


def render_rekey(cfg, result, locked_day_shifts=None,
                 out="/mnt/user-data/outputs/wwtc_re_enter.html"):
    """N9 — "Re-enter at the desk": the run's complete change list, on one printed page.

    A RENDERED ARTIFACT (decision 3, Operator 2026-08-07): no schema, no contract row, no
    machine-import format — no `td-*` document gains, loses or renames anything for it.

    "WAS AND NOW" (decision 1): every row shows what Tournament Desk should currently hold beside
    what it should become. The Was column is the whole point — the page is often worked by
    someone who was not present when the changes were made, and it is the only layout that lets
    them tell an already-entered change from a pending one. Re-keying a move twice is exactly the
    error that puts two players on one court.

    Grouped ONE DRAW AT A TIME (workbook rule N5). Empty state matches the Edit console's rail
    word for word rather than minting a second phrasing.
    """
    groups = _rekey_rows(cfg, result, locked_day_shifts)
    n = sum(len(rows) for _name, rows in groups)
    tour = getattr(cfg, "tournament_name", None) or "USTA Wilson World Tennis Classic"
    if not n:
        sub, body = _esc(tour), '<p class="empty">Nothing to re-enter.</p>'
    else:
        sub = (f"{_esc(tour)} · {n} change{'s' if n != 1 else ''} across "
               f"{len(groups)} draw{'s' if len(groups) != 1 else ''}")
        parts = []
        for name, rows in groups:
            parts.append(f"<section><h2>{_esc(name)}</h2><table>"
                         f"<thead><tr><th>Match</th><th>Was</th><th>Now</th></tr></thead><tbody>")
            for row in rows:
                note = (f'<span class="note">{_esc(row["note"])}</span>' if row["note"] else "")
                parts.append(f'<tr><td>{_esc(row["what"])}</td>'
                             f'<td class="was">{_esc(row["was"])}</td>'
                             f'<td class="now">{_esc(row["now"])}{note}</td></tr>')
            parts.append("</tbody></table></section>")
        body = "\n".join(parts)
    html = REKEY_PAGE.format(sub=sub, body=body)
    _ensure_dir(out)
    open(out, "w").write(html)
    return out


# ---------------------------------------------------------------- PDF (36x24 landscape)
# 36x24 inches at 72 pt/in. Each division is fit onto one page, aspect preserved.
_PAGE_W_PT, _PAGE_H_PT = 36*72, 24*72        # 2592 x 1728
_PAGE_MARGIN_PT = 0.5*72                       # 36 pt

def render_all_pdf(cfg, result, seeds_by_event,
                   out="/mnt/user-data/outputs/wwtc_draw_sheets.pdf",
                   locked_day_shifts=None, roster=None):
    """One 36x24" landscape page per division. Reuses the exact SVGs from the
    HTML path; dereferences PALETTE colors (cairosvg can't resolve var()), then
    scales each sheet to fit the printable area with its aspect preserved.

    REKEY-1: takes the same two keyword-with-default parameters as `render_all`, because this
    path calls `render_event` directly — the two output paths must never disagree about who is
    on the draw."""
    import io
    import cairosvg
    from pypdf import PdfReader, PdfWriter, Transformation
    from pypdf.generic import RectangleObject

    avail_w = _PAGE_W_PT - 2*_PAGE_MARGIN_PT
    avail_h = _PAGE_H_PT - 2*_PAGE_MARGIN_PT
    writer = PdfWriter()

    # DIV-1 follow-up (2026-08-05): the PDF pages print in the SAME order as the HTML sheets —
    # one call, one order. The screen set and the printed set coming out differently is the
    # inconsistency rule 44 exists to end. REVIEW-1 (D2): the conflicts sheet leads the PDF
    # exactly as it leads the HTML — same renderer, same condition, so the two paths cannot
    # disagree about whether there is something to warn about.
    con = render_conflicts(result)
    pages = [con] if con else []
    pages += [render_event(cfg, ev, result, seeds_by_event,
                           locked_day_shifts=locked_day_shifts, roster=roster)
              for ev in sheet_order(cfg)]
    for svg, w, h in pages:
        svg = _xml_safe(_deref(svg))
        # Render the SVG to a PDF at its natural point size (1 svg unit -> 1 pt),
        # then place+scale that page onto a fixed 36x24 landscape sheet.
        src_bytes = cairosvg.svg2pdf(bytestring=svg.encode("utf-8"),
                                     output_width=w, output_height=h)
        src_page = PdfReader(io.BytesIO(src_bytes)).pages[0]

        scale = min(avail_w / w, avail_h / h)          # fit, preserve aspect
        draw_w, draw_h = w*scale, h*scale
        tx = (_PAGE_W_PT - draw_w) / 2                  # center horizontally
        ty = (_PAGE_H_PT - draw_h) / 2                  # center vertically

        page = writer.add_blank_page(width=_PAGE_W_PT, height=_PAGE_H_PT)
        page.merge_transformed_page(
            src_page, Transformation().scale(scale, scale).translate(tx, ty))

    _ensure_dir(out)   # F7-5: portable across surfaces
    with open(out, "wb") as f:
        writer.write(f)
    return out
