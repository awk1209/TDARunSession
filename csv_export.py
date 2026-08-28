"""csv_export.py — R5b (OUT / brief): the per-player CSV output.

One row per **player per division entered**, carrying **all fields from the original TD export**
(the player's `raw_td` record) plus that division's **first on-court match** — day, time, LOCATION
(no court number — Era-1), and opponent. "First match" = the player's earliest scheduled match in
that division (so a bye/walkover round-1 correctly rolls forward to their first played match).

Read-only over the pipeline result; no engine coupling. Consumes what `wwtc_pipeline.build()` returns.
"""
from __future__ import annotations

import csv
import os

import division_order as DO       # DIV-1: rule 44's one display order
import wwtc_ingest
import wwtc_pipeline

# Appended schedule columns (after the original TD export columns).
SCHED_COLS = ["Division", "First Match Day", "First Match Time", "First Match Location",
              "First Match Opponent"]

# HOLDVIS-1 (ruling 1, 2026-08-07): what the day column says for a match the TD held off the
# schedule. WORDS IN THE DAY COLUMN, and deliberately NOT a new column — a tournament with no
# hold exports byte-identical bytes, and the column set every desk reader knows keeps its shape.
HELD_DAY = "held — not scheduled"


def first_round_rows(build_result):
    """Return (fieldnames, rows) — one row per (player, division) with the player's original TD
    export fields + that division's first scheduled match (day/time/location/opponent)."""
    players = build_result["players"]                       # {usta_id: Player}
    result = build_result["result"]
    by_name = {p.name: p for p in players.values()}

    firsts = {}                                             # (name, division) -> earliest match info
    for row in result["schedule"]:
        div = row["event"]
        ta, tb = row.get("team_a") or [], row.get("team_b") or []
        for name in row.get("players", []):
            key = (name, div)
            cur = firsts.get(key)
            if cur is None or (row["day"], row["start"]) < (cur["day"], cur["start"]):
                opp = tb if name in ta else ta
                firsts[key] = {"day": row["day"], "start": row["start"], "end": row["end"],
                               "location": row.get("location") or "",
                               "opp": "/".join(opp) if opp else "TBD"}

    # column order: the original TD export header (from any player's raw_td) + the schedule columns
    td_cols = []
    for p in players.values():
        if p.raw_td:
            td_cols = list(p.raw_td.keys())
            break
    fieldnames = td_cols + [c for c in SCHED_COLS if c not in td_cols]

    def _base_row(name, div):
        """The player's own export fields for one division — every roster column as usual."""
        p = by_name.get(name)
        # ROSTER-1: a player entered at BOTH levels has two TD rows with two different `Draw
        # status` cells. The union keeps one Player, so the row is taken per DIVISION — before
        # this, every Mixed row printed the player's Level-2 status.
        raw = (p.raw_td_by_division.get(wwtc_ingest.division_parent(div)) or p.raw_td) if p \
            else None
        base = dict(raw) if raw else {}
        base.setdefault("Name", name)
        base["Division"] = div
        return base

    rows = []
    for (name, div), info in firsts.items():
        base = _base_row(name, div)
        base["First Match Day"] = info["day"]
        base["First Match Time"] = f'{info["start"]}-{info["end"]}'
        base["First Match Location"] = info["location"]
        base["First Match Opponent"] = info["opp"]
        rows.append(base)

    # HOLDVIS-1 (ruling 1): the held matches keep their rows. A match the TD holds off the
    # schedule used to delete its players from this file entirely — measured on run 2 as 6 of
    # 1,066 rows gone, with 4 of the 6 men appearing NOWHERE in it — so the one document that
    # answers "when do I play?" answered it with silence. The row is added only where the player
    # has no scheduled match in that division: a real first match always wins the cell.
    seen_held = set()
    for h in (result.get("held") or ()):
        div = h.get("event")
        for name in (h.get("players") or ()):
            if (name, div) in firsts or (name, div) in seen_held:
                continue
            seen_held.add((name, div))
            base = _base_row(name, div)
            base["First Match Day"] = HELD_DAY
            # Ruling 1: the other three First-Match cells are EMPTY. A held match has no time, no
            # location and no opponent to print, and inventing one is how a desk re-keys a match
            # that is not happening.
            base["First Match Time"] = ""
            base["First Match Location"] = ""
            base["First Match Opponent"] = ""
            rows.append(base)
    # Deterministic order: by division, then first-match day/time, then player name.
    # DIV-1 (rule 44): the division term is the TD's DISPLAY RANK, not the raw name — so the
    # 1,066 player rows come out in division blocks he reads in one order, the same order every
    # other surface uses. The day / time / name terms are unchanged, so within a division block
    # nothing moves. Measured before this build: 50 of 51 blocks sat outside that order.
    #
    # HOLDVIS-1: the held rows ride the SAME key and need no term of their own — the day cell
    # reads "held — not scheduled", and "h" sorts after every "2026-…", so a held row lands at
    # the end of its division block and cannot ripple the dated rows above it (measured).
    mixed_l1 = list(getattr(build_result.get("cfg"), "mixed_level_1_resolved", None) or ())
    rows.sort(key=lambda r: (DO.display_key(r.get("Division", ""), mixed_l1),
                             r.get("First Match Day", ""),
                             r.get("First Match Time", ""), r.get("Name", "")))
    return fieldnames, rows


# ROSTER-1: the exceptions list — entered, but not playing.
EXCEPTION_COLS = ["Player", "USTA ID", "Division", "Why not playing", "Draw status (desk)",
                  "Needs a look"]


def exception_rows(build_result):
    """(fieldnames, rows) for the exceptions list: every person-division entry that is NOT in a
    printed draw, with the reason and **the desk's exact words**.

    This is the other half of the per-player CSV. That file answers "when do I play?" for the
    1,066 entries that are in a draw; this one answers "why am I not on it?" for the 121 that are
    not — the question the tool could not answer at all before ROSTER-1, because 0 unplaced only
    ever meant every match it BUILT, it placed. Same lane on purpose: the TD works here when
    re-keying into Tournament Desk.

    Rows come straight off `build_result["reconciliation"]` — the same buckets the edit console's
    panel renders — so the list and the console can never disagree. Deterministic: division, then
    player. "Needs a look" marks the rows that are not self-explanatory: an unresolved status, or
    a `Selected` player in no bracket at all (**exactly 1 on the 2026 field** — the sharpest case
    this list exists to surface)."""
    rec = build_result["reconciliation"]
    rows = [{"Player": r["name"], "USTA ID": r["usta_id"], "Division": r["division"],
             "Why not playing": r["reason"], "Draw status (desk)": r["desk_status"],
             "Needs a look": "yes" if r["review"] else ""}
            for r in rec["exceptions"]]
    return list(EXCEPTION_COLS), rows


def write_exceptions_csv(build_result, out):
    """Write the exceptions list to `out`. Returns (path, n_rows)."""
    fieldnames, rows = exception_rows(build_result)
    d = os.path.dirname(os.path.abspath(out))
    if d:
        os.makedirs(d, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8-sig") as f:     # DESK-1: see write_csv
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: _clean(v) for k, v in r.items()})
    return out, len(rows)


def _clean(v):
    """Whole-number floats from the .numbers reader (e.g. USTA ID 2020284936.0) render as ints;
    genuine decimals (WTN 28.74) are untouched."""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return v


def write_csv(build_result, out):
    """Write the per-player first-round CSV to `out`. Returns (path, n_rows)."""
    fieldnames, rows = first_round_rows(build_result)
    d = os.path.dirname(os.path.abspath(out))   # F7-5: portable — create the target dir
    if d:
        os.makedirs(d, exist_ok=True)
    # DESK-1 (8/7 note 9, 2026-08-09): `utf-8-sig`, not `utf-8`. Excel on Windows reads a
    # BOM-less file as Windows-1252 whatever the bytes say, so every em dash the tool writes
    # arrived as `â€”` — confirmed from the Operator's own paste. The BOM is three bytes Excel
    # reads as "this is UTF-8"; every other reader (Numbers, Sheets, `csv` itself) skips it.
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: _clean(v) for k, v in r.items()})
    return out, len(rows)


def _selftest():
    import tempfile
    import os
    b = wwtc_pipeline.build(level="2")
    out = os.path.join(tempfile.gettempdir(), "wwtc_first_round.csv")
    path, n = write_csv(b, out)
    fieldnames, rows = first_round_rows(b)
    print(f"CSV: {n} rows -> {os.path.basename(path)}; {len(fieldnames)} columns")
    print("columns:", fieldnames)
    # every row has a real time+location and no court field
    assert n > 0
    assert all(r.get("First Match Location") and r.get("First Match Time") for r in rows), "missing time/location"
    assert not any("court" in c.lower() for c in fieldnames), "a court column leaked in"
    # header carries the original TD export fields
    assert "USTA ID" in fieldnames and "Events" in fieldnames, "TD export columns missing"
    print("sample row:", {k: rows[0].get(k) for k in ("Name", "USTA ID", "Division",
          "First Match Day", "First Match Time", "First Match Location", "First Match Opponent")})
    # ROSTER-1: the exceptions list, on the whole tournament (both levels — it is a roster
    # question, and 84 people cross the two).
    bc = wwtc_pipeline.build_combined()
    xout = os.path.join(tempfile.gettempdir(), "wwtc_exceptions.csv")
    xpath, xn = write_exceptions_csv(bc, xout)
    xf, xrows = exception_rows(bc)
    c = bc["reconciliation"]["counts"]
    assert xn == c["exceptions"], "exceptions list does not match the reconciliation"
    assert c["entries"] == c["scheduled"] + c["exceptions"], "accounting is not closed"
    print(f"exceptions: {xn} rows -> {os.path.basename(xpath)}; columns {xf}")
    print(f"closed accounting: {c['entries']} entries = {c['scheduled']} scheduled "
          f"+ {c['exceptions']} not playing")
    print("sample exception:", xrows[0])
    print("csv_export self-test OK")


if __name__ == "__main__":
    _selftest()
