"""draws_pdf.py — parse a Tournament Desk "raw draws" PDF into per-division bracket structure.

Part of the R1 real-data ingest (MVP rescope). Ingests the **finalized** draw — pairings, seeds,
byes, and doubles partnerships — as the tournament desk exported it. The PDF's auto-created
day/time/location schedule is **retained** (ING-1, ruling D5, 2026-07-29): the earlier premise
that the TD rejects the autoschedule was disproven by the nine-file analysis — measured on 2026 he
keeps **95.2% of first matches verbatim** and the desk's day in **130 of 133** groups (see
`reference/product/ninefile_analysis_2026-07-29/`). Stamps are carried as data on `DivisionDraw`
(`r1_stamps` / `later_stamps` / `Group.stamps`, verbatim PDF tokens; `schedule_of()` looks one up).
The ENGINE still ignores them — seeding `assigned_days` from these stamps is D4's build, and the
pre-publication checks over them are RPT-1. This module is now the single stamp-aware parser: the
analysis package's `extract.py` forked this tokenizer to get the stamps and stays as the frozen
2026 record; future analysis work consumes this module, not `extract.py`.

Read-only; no engine coupling (R1c turns these structures into `scheduler_multi` EventSpecs; R1b
resolves the PDF's display names to full players via the player-list join). Text is extracted with
`pypdfium2` — `pdfminer`/`pdfplumber` are blocked by a broken `cryptography` binding in this env.

Per division we emit a `DivisionDraw`:
  - elimination → `fmt="single_elim"`, `slots` = the ordered bracket (power-of-two length) with each
    slot carrying seed / bye / doubles-partner info, exactly as positioned. Multi-page draws
    (a 64-draw prints as two 1..32 / 33..64 half-pages plus later-round continuation pages) are
    stitched; continuation pages are ignored *structurally* — the engine rebuilds later rounds from
    round 1 — but their schedule stamps are harvested (ING-1).
  - round-robin → `fmt="round_robin"`, one `Group` per printed "Group N" table.

Elim parsing is exact (verified: every division reconstructs to a power-of-two, names verbatim).
RR grids wrap unpredictably, so RR member identity is captured best-effort (cleaned display blob +
seed) and finalized by the R1b roster join; `Group.stamps` carries the same best-effort caveat.
"""
from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass, field
from typing import Optional

import pypdfium2 as pdfium

import field_source

# Bracket round labels → draw size. Round 1 of a division is its largest label.
LABEL_SIZE = {"R256": 256, "R128": 128, "R64": 64, "R32": 32, "R16": 16,
              "Quarterfinals": 8, "Semifinals": 4, "Final": 2}
_WEEKDAY = re.compile(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun),")
_WEEKDAY_IN = re.compile(r"\s+(Mon|Tue|Wed|Thu|Fri|Sat|Sun),")   # embedded schedule start
_SLOT = re.compile(r"^(\d+)\s+(.*\S)\s*$")          # "12 Some Name [3]" / "2 BYE"
_SEED = re.compile(r"\s*\[(\d+)\]\s*$")             # trailing seed marker
_INT = re.compile(r"^\d+$")
_GROUP = re.compile(r"^Group\s+(\d+)\b")
# ING-1 schedule stamps. Elim pages always print the full form on one line (verified: 0
# unparseable weekday lines across the four committed PDFs' elim pages); RR grids wrap, so the
# RR harvest uses the tail form + a next-line venue continuation.
_STAMP = re.compile(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s*"
                    r"(\w{3} \d{1,2}),\s*(\d{1,2}:\d{2} [AP]M)\s+at\s+(\S+)\s*$")
_STAMP_TAIL = re.compile(r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s*"
                         r"(\w{3} \d{1,2}),\s*(\d{1,2}:\d{2} [AP]M)"
                         r"(?:\s+at(?:\s+(\S+))?)?\s*$")
_AT_LINE = re.compile(r"^at\s+(\S+)\s*$")           # RR wrap: '9:30 AM' / 'at MHCC'
_NOT_SCHEDULED = "Not scheduled"


@dataclass
class Slot:
    """One position in an elimination bracket, in draw order."""
    pos: int
    display: str                       # raw entrant text (seed stripped), or "BYE"
    is_bye: bool = False
    seed: Optional[int] = None
    is_doubles: bool = False
    partners: list = field(default_factory=list)   # surname tokens (["Auld","Smith"] / ["Rovner"])


@dataclass
class RRMember:
    display: str                       # cleaned blob (schedule removed), for R1b name matching
    seed: Optional[int] = None
    is_doubles: bool = False
    partners: list = field(default_factory=list)


@dataclass
class Group:
    name: str                          # "Group 1"
    members: list = field(default_factory=list)     # list[RRMember]
    # ING-1: schedule stamps in printed order (dict per stamp, None per 'Not scheduled').
    # Best-effort, same caveat as RR member identity; the cross-table prints each pairing's
    # stamp once per row, so pairings typically appear twice.
    stamps: list = field(default_factory=list)
    # Which member row each stamp printed under: {member index (0-based) -> [stamp|None, ...]}.
    # ADDITIVE — `stamps` above is unchanged. Without this the flat list is unusable: a stamp
    # names neither of its players, so a reader has a date and nobody to attach it to. The row IS
    # a player (row order == `members` order, both driven by the same bare-integer line), which is
    # all a rest or day-band check needs; and because the grid prints a match's stamp once in each
    # of its two players' rows, an identical stamp under exactly two rows also recovers the
    # pairing. See `schedule_report.rr_matches`.
    row_stamps: dict = field(default_factory=dict)


@dataclass
class DivisionDraw:
    event: str
    fmt: str                           # "single_elim" | "round_robin"
    pages: list = field(default_factory=list)
    slots: list = field(default_factory=list)       # elim: list[Slot], draw order
    groups: list = field(default_factory=list)      # rr: list[Group]
    warnings: list = field(default_factory=list)
    # ING-1 (ruling D5): the desk autoschedule, retained as data. A stamp is
    # {"date","time","venue"} — verbatim PDF tokens (e.g. {"date": "Jan 24", "time": "9:30 AM",
    # "venue": "MHCC"}); normalisation is the consumer's job. None = the PDF printed
    # 'Not scheduled'; a missing key = the PDF carried no stamp line for that match.
    r1_stamps: dict = field(default_factory=dict)      # round-1 match index (1-based) -> stamp
    later_stamps: dict = field(default_factory=dict)   # round label -> match index -> stamp

    @property
    def draw_size(self) -> int:
        return len(self.slots)

    @property
    def n_real(self) -> int:
        return sum(1 for s in self.slots if not s.is_bye)

    @property
    def n_byes(self) -> int:
        return sum(1 for s in self.slots if s.is_bye)


_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "wwtc-2026")
_ROOTS = (_DATA_DIR, "/mnt/user-data/uploads", "/root/.claude/uploads")


def resolve_draws_pdf(name_hint="Raw_Draws", level=None):
    """Locate a raw-draws PDF across the data dir + ephemeral upload dirs. When `level` is given,
    pick the PDF whose filename carries that level token (`L1`/`L2`) — the six-file set ships one
    raw-draws PDF per level. Case-insensitive (real files vary: `RAW_DRAWS` vs `Raw_Draws`).
    Env overrides: $WWTC_DRAWS_PDF_L<level> (per level) or $WWTC_DRAWS_PDF (single)."""
    override = (os.environ.get(f"WWTC_DRAWS_PDF_L{level}") if level else None) \
        or os.environ.get("WWTC_DRAWS_PDF")
    if override and os.path.exists(override):
        return override
    hint = name_hint.lower()
    for root in _ROOTS:
        hits = sorted(glob.glob(os.path.join(root, "**", "*.pdf"), recursive=True))
        cand = [h for h in hits if hint in os.path.basename(h).lower()]
        if level is not None:
            cand = [h for h in cand if f"l{level}" in os.path.basename(h).lower()]
        if cand:
            return cand[0]
    raise FileNotFoundError(
        f"No raw-draws PDF for level={level} (hint {name_hint!r}). "
        f"Set $WWTC_DRAWS_PDF_L{level} / $WWTC_DRAWS_PDF or drop the PDF into a data/upload dir.")


def _split_seed(text):
    m = _SEED.search(text)
    if m:
        return text[:m.start()].strip(), int(m.group(1))
    return text.strip(), None


def _partners(name):
    """Doubles display 'Auld/Smith' → (['Auld','Smith'], True); singles → ([name], False)."""
    if "/" in name:
        return [p.strip() for p in name.split("/") if p.strip()], True
    return [name], False


def _event_of(txt):
    m = re.search(r"Event:\s*(.+)", txt)
    return m.group(1).strip() if m else None


def _first_label(txt):
    for ln in txt.splitlines():
        s = ln.strip()
        if s in LABEL_SIZE:
            return s
    return None


def _page_texts(pdf):
    return [pdf[i].get_textpage().get_text_range() for i in range(len(pdf))]


def _elim_slots_on_page(txt):
    """{pos: entrant_text} for numbered round-1 slot lines (schedule/label lines excluded)."""
    out = {}
    for ln in txt.splitlines():
        s = ln.strip()
        if not s or _WEEKDAY.match(s):
            continue
        m = _SLOT.match(s)
        if not m:
            continue
        ent = m.group(2).strip()
        if ent in LABEL_SIZE:
            continue
        out[int(m.group(1))] = ent
    return out


# ---- ING-1: schedule-stamp harvest (structure parsing above/below is untouched) -------------

def _stamp_sections(txt):
    """[(round_label, items)] for one elim page; items = ('slot', pos) | ('stamp', dict|None).

    A stamp line (full form) or 'Not scheduled' attaches to the section it prints under; every
    other line (names, scores, footers) is ignored. Slot positions are the PDF's original draw
    coordinates on every page — continuation pages re-print advancing players at their round-1
    line numbers.
    """
    sections, label, items = [], None, []
    for ln in txt.splitlines():
        s = ln.strip()
        if not s:
            continue
        if s in LABEL_SIZE:
            if label is not None:
                sections.append((label, items))
            label, items = s, []
            continue
        if label is None:
            continue
        m = _STAMP.match(s)
        if m:
            items.append(("stamp", {"date": m.group(2), "time": m.group(3), "venue": m.group(4)}))
            continue
        if s == _NOT_SCHEDULED:
            items.append(("stamp", None))
            continue
        m = _SLOT.match(s)
        if m and m.group(2).strip() not in LABEL_SIZE and not _WEEKDAY.match(s):
            items.append(("slot", int(m.group(1))))
    if label is not None:
        sections.append((label, items))
    return sections


def _record_stamp(dd, target, label, idx, stamp):
    """First stamp wins; a CONFLICTING duplicate is a warning (consistent duplicates are the
    norm — a later round prints both on the round-1 pages, split by subtree, and again on the
    continuation page)."""
    if idx in target:
        if target[idx] != stamp:
            dd.warnings.append(f"stamp conflict {label} match {idx}: "
                               f"{target[idx]!r} vs {stamp!r}")
        return
    target[idx] = stamp


def _harvest_elim_stamps(dd, texts):
    """Attach the desk's schedule stamps to an elim DivisionDraw (r1_stamps / later_stamps).

    Round-1 sections print every slot line, and a match's stamp sits vertically between its two
    side rows — so a stamp attaches to the match of the *preceding* slot line. Later-round
    sections print a stamp per match in bracket order (interleaved bye-advancer lines carry no
    stamp of their own), so the k-th stamp of a section maps to match `sub_lo + k` of that label
    within the page's subtree: `per = 2 * draw_size / LABEL_SIZE[label]`,
    `sub_lo = (first_slot_on_page - 1) // per + 1`. A continuation page (first label smaller
    than round 1's) is all later-round sections; one with no slot lines covers the whole tail
    (`sub_lo = 1`).
    """
    maxsz = dd.draw_size
    if not maxsz or (maxsz & (maxsz - 1)) != 0:
        return
    for i in dd.pages:
        secs = _stamp_sections(texts[i])
        if not secs:
            continue
        slots_on_page = [it[1] for _lbl, its in secs[:1] for it in its if it[0] == "slot"]
        base = min(slots_on_page) if slots_on_page else 1
        r1_first = LABEL_SIZE[secs[0][0]] == maxsz
        for si, (lbl, items) in enumerate(secs):
            if si == 0 and r1_first:
                pending = None
                for it in items:
                    if it[0] == "slot":
                        pending = it[1]
                    elif pending is not None:
                        _record_stamp(dd, dd.r1_stamps, lbl, (pending + 1) // 2, it[1])
                continue
            per = 2 * maxsz // LABEL_SIZE[lbl]
            sub_lo = (base - 1) // per + 1
            target = dd.later_stamps.setdefault(lbl, {})
            k = 0
            for it in items:
                if it[0] == "stamp":
                    _record_stamp(dd, target, lbl, sub_lo + k, it[1])
                    k += 1


def _file_row_stamp(dd, gi, row, stamp):
    """File one stamp under the member row it printed against, loudly refusing a row that has no
    member. A stamp attached to the wrong player is worse than one that is missing: the first
    produces a confident false finding, the second is visible in the coverage counts."""
    g = dd.groups[gi]
    if row < 0 or row >= len(g.members):
        dd.warnings.append(f"{g.name}: schedule stamp at member row {row + 1} of "
                           f"{len(g.members)} — dropped, no member to attach it to")
        return
    g.row_stamps.setdefault(row, []).append(stamp)


def _harvest_rr_stamps(dd, texts):
    """Attach schedule stamps to each RR Group, in printed order (best-effort — the caveat of
    the RR member parse applies). RR grids wrap a stamp across lines two ways, both recovered:
    '… 2:30 PM at' + venue on the next line, and '… 11:00 AM' + 'at VEN' on the next line; a
    stamp may also sit embedded at the end of a member/city line.

    Each stamp is also filed under the member ROW it printed under (`Group.row_stamps`). The row
    is detected exactly as `_build_rr` detects a member — a bare-integer line inside a group — so
    the two walks cannot disagree about how many rows a group has: a stray integer that fooled
    this one would already have fooled `_build_rr` into minting a spurious member. A row index
    past the parsed member list is dropped with a warning rather than filed against the wrong
    player."""
    gi = -1
    row = -1
    for i in dd.pages:
        lines = [ln.strip() for ln in texts[i].splitlines()]
        for j, s in enumerate(lines):
            if not s:
                continue
            if _GROUP.match(s):
                gi += 1
                row = -1
                continue
            if gi < 0 or gi >= len(dd.groups):
                continue
            if _INT.fullmatch(s):
                row += 1
                continue
            if s == _NOT_SCHEDULED:
                dd.groups[gi].stamps.append(None)
                _file_row_stamp(dd, gi, row, None)
                continue
            m = _STAMP_TAIL.search(s)
            if not m:
                continue
            venue = m.group(4)
            if venue is None:
                nxt = lines[j + 1] if j + 1 < len(lines) else ""
                m2 = _AT_LINE.match(nxt)
                if m2:
                    venue = m2.group(1)
                elif m.group(0).rstrip().endswith(" at") and re.fullmatch(r"\S+", nxt) \
                        and re.search(r"[A-Za-z]", nxt):
                    venue = nxt
            stamp = {"date": m.group(2), "time": m.group(3), "venue": venue}
            dd.groups[gi].stamps.append(stamp)
            _file_row_stamp(dd, gi, row, stamp)


def schedule_of(draw, round_label, match_index):
    """The desk's schedule stamp for one match of an elim DivisionDraw, or None (either the PDF
    printed 'Not scheduled' or it carried no stamp line for that match). Round 1 is the label
    whose size equals the draw size; every other label reads from later_stamps."""
    if LABEL_SIZE.get(round_label) == draw.draw_size:
        return draw.r1_stamps.get(match_index)
    return draw.later_stamps.get(round_label, {}).get(match_index)


def _build_elim(event, pages, texts):
    """Stitch a division's round-1 pages into an ordered Slot list."""
    maxsz = max(LABEL_SIZE.get(_first_label(texts[i]), 0) for i in pages)
    r1pages = [i for i in pages if LABEL_SIZE.get(_first_label(texts[i]), 0) == maxsz]
    dd = DivisionDraw(event=event, fmt="single_elim", pages=sorted(pages))
    raw = {}
    for i in r1pages:
        for pos, ent in _elim_slots_on_page(texts[i]).items():
            if pos in raw and raw[pos] != ent:
                dd.warnings.append(f"dup slot {pos}: {raw[pos]!r} vs {ent!r}")
            raw[pos] = ent
    for pos in sorted(raw):
        ent = raw[pos]
        if ent.upper() == "BYE":
            dd.slots.append(Slot(pos=pos, display="BYE", is_bye=True))
            continue
        name, seed = _split_seed(ent)
        parts, is_dbl = _partners(name)
        dd.slots.append(Slot(pos=pos, display=name, seed=seed, is_doubles=is_dbl, partners=parts))
    n = dd.draw_size
    if n == 0 or (n & (n - 1)) != 0:
        dd.warnings.append(f"draw size {n} is not a power of two")
    # positions should be a contiguous 1..n
    if sorted(raw) != list(range(1, n + 1)):
        dd.warnings.append("slot positions are not contiguous 1..N")
    _harvest_elim_stamps(dd, texts)                 # ING-1: structure above is untouched
    return dd


def _build_rr(event, pages, texts):
    """Best-effort RR: one Group per 'Group N' table; members = cleaned blob + seed (R1b resolves)."""
    dd = DivisionDraw(event=event, fmt="round_robin", pages=sorted(pages))
    for i in pages:
        lines = [ln.rstrip() for ln in texts[i].splitlines()]
        cur = None
        j = 0
        while j < len(lines):
            s = lines[j].strip()
            gm = _GROUP.match(s)
            if gm:
                cur = Group(name=f"Group {gm.group(1)}")
                dd.groups.append(cur)
                j += 1
                continue
            if cur is not None and _INT.fullmatch(s):
                # a member row: accumulate following lines until a schedule/next-int/footer line
                blob = []
                j += 1
                while j < len(lines):
                    t = lines[j].strip()
                    if not t or _INT.fullmatch(t) or _WEEKDAY.match(t) \
                       or t.startswith("USTA ") or t.startswith("Dates:") or _GROUP.match(t) \
                       or t.startswith("at "):
                        break
                    sm = _WEEKDAY_IN.search(t)      # schedule bled onto this line — keep the head, stop
                    if sm:
                        head = t[:sm.start()].strip()
                        if head:
                            blob.append(head)
                        j += 1
                        break
                    blob.append(t)
                    j += 1
                text = " ".join(blob).strip()
                name, seed = _split_seed(text) if _SEED.search(text) else (text, None)
                # seed can sit mid-blob ("Name [1] City"): pull it out too
                if seed is None:
                    ms = re.search(r"\[(\d+)\]", text)
                    if ms:
                        seed = int(ms.group(1))
                        name = text[:ms.start()].strip()
                lead = name.split(",")[0].strip()          # drop city tail for partner detection
                parts, is_dbl = _partners(lead)
                cur.members.append(RRMember(display=name, seed=seed,
                                            is_doubles=is_dbl, partners=parts))
                continue
            j += 1
    if not dd.groups:
        dd.warnings.append("no groups parsed")
    else:
        _harvest_rr_stamps(dd, texts)               # ING-1: member parse above is untouched
    return dd


def parse_draws(path=None, level=None):
    """Parse a raw-draws PDF → list[DivisionDraw] (one per printed division). When `path` is None,
    resolve the PDF for `level` (level-aware selection across the six-file set).

    S-2 SEAM (Operator ruling, 2026-08-24 — option 1). A September run works from a field that
    has not been played, so there is no PDF to read. When a projected field is installed
    (`field_source`), this serves that field's draws for the level instead of parsing. With
    nothing installed — every January run, and every other consumer — the body below runs
    exactly as it did before the seam existed, byte for byte.
    """
    projected = field_source.installed()
    if projected is not None:
        return projected.draws_for(level)
    path = path or resolve_draws_pdf(level=level)
    pdf = pdfium.PdfDocument(path)
    texts = _page_texts(pdf)
    # group page indices by division event, preserving first-seen order
    order, bydiv = [], {}
    for i, txt in enumerate(texts):
        ev = _event_of(txt) or f"__page{i}"
        if ev not in bydiv:
            bydiv[ev] = []
            order.append(ev)
        bydiv[ev].append(i)
    out = []
    for ev in order:
        pages = bydiv[ev]
        is_rr = any(("Group" in texts[i] and "Draw Stage" not in texts[i]) for i in pages)
        out.append(_build_rr(ev, pages, texts) if is_rr else _build_elim(ev, pages, texts))
    return out


def _selftest():
    path = resolve_draws_pdf()
    print(f"draws PDF: {path}")
    draws = parse_draws(path)
    elim = [d for d in draws if d.fmt == "single_elim"]
    rr = [d for d in draws if d.fmt == "round_robin"]
    print(f"divisions={len(draws)}  elim={len(elim)}  rr={len(rr)}")
    bad = [d for d in draws if d.warnings]
    tot_real = 0
    for d in draws:
        if d.fmt == "single_elim":
            tot_real += d.n_real
            print(f"  [ELM] {d.event[:38]:38s} size={d.draw_size:3d} real={d.n_real:3d} "
                  f"byes={d.n_byes:3d} seeds={sum(1 for s in d.slots if s.seed)}"
                  f"{'  WARN:'+';'.join(d.warnings) if d.warnings else ''}")
        else:
            m = sum(len(g.members) for g in d.groups)
            tot_real += m
            print(f"  [RR ] {d.event[:38]:38s} groups={len(d.groups)} members={m}"
                  f"{'  WARN:'+';'.join(d.warnings) if d.warnings else ''}")
    print(f"total real entrants ~= {tot_real}")
    # ING-1: schedule-stamp harvest summary
    r1 = sum(1 for d in elim for v in d.r1_stamps.values() if v)
    r1_ns = sum(1 for d in elim for v in d.r1_stamps.values() if v is None)
    later = sum(1 for d in elim for lbl in d.later_stamps for v in d.later_stamps[lbl].values() if v)
    rr_st = sum(1 for d in rr for g in d.groups for v in g.stamps if v)
    # Every RR stamp must also be filed under a member row, or the reporter cannot attach it to a
    # player. The two counts drifting apart means row detection lost a stamp the flat list kept.
    rr_rows = sum(1 for d in rr for g in d.groups for v in g.row_stamps.values() for s in v if s)
    assert rr_rows == rr_st, \
        f"{rr_st} RR stamps but {rr_rows} filed to member rows — row attribution dropped some"
    fin = [schedule_of(d, "Final", 1) for d in elim]
    print(f"stamps: r1={r1} (+{r1_ns} not-scheduled) later={later} rr={rr_st} "
          f"(all filed to member rows)  "
          f"finals stamped={sum(1 for f in fin if f)}/{len(elim)}")
    assert not bad, f"{len(bad)} divisions have warnings"
    assert all((d.draw_size & (d.draw_size - 1)) == 0 for d in elim), "a draw is not power-of-two"
    print("SELF-TEST OK")


if __name__ == "__main__":
    _selftest()
