"""td-finals-plan/v1 — the self-contained snapshot the finals-map editor is generated from (F7).

Read-only projection over an already-built master schedule (like editor_plan.py — no engine
coupling, nothing here changes placement). Bundles into ONE doc everything the finals-map
edit surface needs so it can render without ever calling the engine (B-1):

  - dates       : the slate's tournament days, verbatim — the chart's columns.
  - divisions   : per-division structure from the parsed draws (event / fmt / draw_size /
                  rounds / age / etype) — the chart's rows. The ENGINE's round counts, not a
                  console-side re-derivation (the old Finals tab's entrant-count guess could
                  drift from the draw PDFs, worst for round-robins).
  - finals_day  : the engine-computed finals draft, per division (pins honored where supplied).
  - round_day   : the full backward cascade, per division: round label -> date.
  - pins        : the pins that were applied when deriving ({} on a first pass; the TD's moved
                  set on a re-edit loop).
  - finals_by_day / cap_singles / cap_doubles : the per-day finals cap audit inputs — the
                  editor reads the caps, never hardcodes them.
  - round_matches / matches_per_day_target : FMAP-1's pacing inputs — PLANNED matches per
                  division per round (derived from the APPROVED DRAWS upstream, never guessed
                  from draw_size) and the TD's own matches/day threshold. Keyed to mirror
                  `round_day`, so the console's day summary is a join against the live map and
                  recomputes on every drag instead of going stale on the first one.
  - warnings    : the cascade's advisory warnings (cap saturated / rounds don't fit).

The editor emits td-finals-map/v1 back: the FULL solved map exactly as displayed at emit
(every division pinned), plus the TD-moved subset for provenance / re-seeding. Emitting the
full map makes the courier round-trip exact — `build_master_schedule(finals_map=full)`
reproduces byte-for-byte what the TD saw, so any JS preview drift is display-only and can
never bind placement. `finals_map_from_doc` validates that doc loudly on the way back in.
"""
from __future__ import annotations

FINALS_PLAN_SCHEMA = "td-finals-plan/v1"
FINALS_MAP_SCHEMA = "td-finals-map/v1"


# ---------------------------------------------------------------------- the mark, embedded
# BRAND-1's `mark_684x234.png` — the cropped, knocked-out asset with alpha, the ONE the record
# says every surface uses (`DESIGN_RECORD.md` §3 rule 1; never `Wyn-Social-FC_Tennis_RED.png`,
# which no layout references). 22,175 bytes; 684 x 234; ratio 2.9231 : 1.
#
# ⚠ IT TRAVELS AS A base64 data: URI, INSIDE THE GENERATED FILE, AND A RELATIVE src IS FORBIDDEN
# — the same rule `setup_console.html` carries, for the same reason. This console is written to a
# file and couriered; a relative path breaks the moment the file moves, and it is exactly the
# fetch B-1 exists to prevent. A data: URI is not a fetch: the byte is in the file.
#
# Held here rather than read from disk at generation so the renderer stays a pure function of its
# plan doc — same input, same output, on a machine that has only this module.
_MARK_B64 = (
    "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"
)


def finals_plan(ms, divisions, tournament=None, pins=None, cap_singles=6, cap_doubles=6,
                round_matches=None, matches_per_day_target=None):
    """Project a built MasterSchedule + its Division records into td-finals-plan/v1.

    ms         : master_schedule.MasterSchedule (already built, pins honored upstream).
    divisions  : the master_schedule.Division list the master was built from.
    pins       : the finals_map that was applied when building `ms` ({} = pure computed draft).
    Deterministic: divisions sorted by event name; day/round maps echo the master verbatim.

    FMAP-1 adds the two pacing inputs the finals map needs to count while the TD decides:

      round_matches          : {event: {round label: PLANNED match count}} — derived from the
                               APPROVED DRAWS upstream (`wwtc_pipeline._round_matches`), never
                               guessed from `draw_size`. Keys mirror `round_day` exactly, so the
                               console's per-day sum is a join against the live day map rather
                               than a second key vocabulary. Per-division-per-round and never a
                               per-day total: a per-day total goes stale on the first drag.
      matches_per_day_target : the TD's own matches/day threshold from td-constraints/v1 (§2).
                               None = no threshold set, and the console flags nothing.

    Both are read-only projection inputs — nothing here changes placement. `cap_singles` /
    `cap_doubles` keep their signature defaults, but the pipeline now passes the TD's measured
    values instead of letting 6/6 stand through a whole guided run (D-32: the editor reads the
    thresholds, it never hardcodes them).
    """
    import master_schedule as MS
    import division_order as DO; divs = DO.sorted_by(divisions, lambda d: d.event, getattr(ms, "mixed_level_1", ()))
    rm = round_matches or {}
    return {
        "schema": FINALS_PLAN_SCHEMA,
        "tournament": tournament or "",
        "dates": list(ms.dates),
        "cap_singles": cap_singles,
        "cap_doubles": cap_doubles,
        "matches_per_day_target": matches_per_day_target,
        "round_matches": {ev: dict(rm[ev]) for ev in sorted(rm)},
        "divisions": [{"event": d.event, "fmt": d.fmt, "draw_size": d.draw_size,
                       "rounds": d.rounds, "age": d.age, "etype": d.etype} for d in divs],
        "finals_day": dict(ms.finals_day),
        "round_day": {ev: dict(rd) for ev, rd in ms.round_day.items()},
        "pins": dict(pins or {}),
        "finals_by_day": MS.summarize_finals_by_day(ms, divs),
        "warnings": list(ms.warnings),
    }


def finals_map_from_doc(doc, dates=None, known_events=None, rounds_by=None):
    """td-finals-map/v1 -> {event: date}, validated LOUDLY (the courier-typo guard).

    master_schedule._pinned_day silently ignores an unknown event or out-of-window date, and
    the cascade silently SLIDES a structurally infeasible pin (rounds that can't fit before
    the pinned day clamp to the window start, landing the real final days later) — a
    couriered doc could therefore partially no-op or quietly miss its pin with no error
    anywhere in the chain. This is the gate that refuses instead. `rounds_by`
    ({event: rounds}, F7-6): a pin earlier than `dates[rounds-1]` is rejected with the
    earliest feasible finals day named.
    """
    if not isinstance(doc, dict) or doc.get("schema") != FINALS_MAP_SCHEMA:
        got = doc.get("schema") if isinstance(doc, dict) else type(doc).__name__
        raise ValueError(f"expected a {FINALS_MAP_SCHEMA} doc, got: {got}")
    fmap = doc.get("finals_map")
    if not isinstance(fmap, dict) or not fmap:
        raise ValueError(f"{FINALS_MAP_SCHEMA}: finals_map is missing or empty")
    if dates is not None:
        bad = sorted(dt for dt in fmap.values() if dt not in dates)
        if bad:
            raise ValueError(f"{FINALS_MAP_SCHEMA}: dates outside the slate window: {bad}")
    if known_events is not None:
        unknown = sorted(ev for ev in fmap if ev not in known_events)
        if unknown:
            raise ValueError(f"{FINALS_MAP_SCHEMA}: unknown division names: {unknown}")
    if dates is not None and rounds_by:
        infeasible = []
        for ev, dt in sorted(fmap.items()):
            need = rounds_by.get(ev)
            if not need or dates.index(dt) >= need - 1:
                continue
            # OI-57 (SKIN-FIN-1, riding the fifth D-3 waiver): a division that needs MORE rounds
            # than the slate has playing days has no feasible day at all, so `dates[need - 1]`
            # indexes past the end and this branch used to raise a bare `IndexError` out of
            # `finals_map_from_doc` — the courier gate CRASHING instead of producing the loud
            # named refusal it exists for, on a path September can reach. The boundary is exact
            # and is asserted in `tests/finals_console_golden.py`: `need == len(dates)` names the
            # last day and is ACCEPTED; `need == len(dates) + 1` is the first case with nowhere
            # to land, and it now refuses by name and says what would fix it. The cascade one
            # layer down already refused this case cleanly — the gate is the surface that fails,
            # and it fails FIRST.
            if need > len(dates):
                infeasible.append(f"{ev}: {need} rounds cannot finish by {dt} — the slate has "
                                  f"{len(dates)} playing days, so no day in this window can hold "
                                  f"this division's final; shorten the draw or add a playing day")
            else:
                infeasible.append(f"{ev}: {need} rounds cannot finish by {dt} — "
                                  f"earliest feasible finals day is {dates[need - 1]}")
        if infeasible:
            raise ValueError(f"{FINALS_MAP_SCHEMA}: structurally infeasible pin(s) — "
                             + "; ".join(infeasible))
    return dict(fmap)


def render_finals_console(plan) -> str:
    """F7-2: the finals-map EDIT SURFACE — a self-contained interactive HTML string the run
    surface writes to a file and hands to the TD (generated artifact; precedent U3 + draw
    sheets). Look = master_schedule.render_master_html (the approved end-state): divisions x
    days chart, F/SF/QF/R# cells, per-day finals cap footer. Each division row is one CARD:
    drag it right-left (or click the division name, then a day cell) to slide its Final to a
    day — the round cascade rides along, one round per day backward, mirroring
    build_master_schedule's exact clamp math. Only the touched division moves (every division
    is treated as pinned at its displayed day). Cap overruns WARN, never block. Emits
    td-finals-map/v1 — the FULL map as displayed + the moved subset — for the human to
    courier back (B-1: no fetch/XHR/file/engine at runtime; data embedded at generation)."""
    import datetime
    import json

    if not isinstance(plan, dict) or plan.get("schema") != FINALS_PLAN_SCHEMA:
        got = plan.get("schema") if isinstance(plan, dict) else type(plan).__name__
        raise ValueError(f"expected a {FINALS_PLAN_SCHEMA} doc, got: {got}")

    def dhdr(dt):
        y, m, d = (int(x) for x in dt.split("-"))
        wd = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][datetime.date(y, m, d).weekday()]
        return f"{wd}<br>{m}/{d}"

    # SKIN-FIN-1's masthead names the TOURNAMENT, not the tool. Both strings below are derived
    # from the plan doc and nothing new is read: `tname` is the same value the <title> has always
    # carried, and `span` is the slate's own first and last day — the doc holds no venues, so the
    # approved mock's venue line is not reproduced rather than invented (§5: a conflict with the
    # record or the doc is a decision, never a quiet fill-in).
    tname = plan.get("tournament") or "Tournament"
    title = tname + " — Finals Map (TD edit)"
    # the name reaches an ELEMENT now, not only the <title>, so it is escaped on the way in —
    # the same two replacements the division labels already make in the script below
    tname = tname.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def dlong(dt):
        y, m, d = (int(x) for x in dt.split("-"))
        wd = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][datetime.date(y, m, d).weekday()]
        mon = ["January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December"][m - 1]
        return f"{wd} {d} {mon}"

    dts = plan["dates"]
    span = (f"{dlong(dts[0])} – {dlong(dts[-1])}" if len(dts) > 1
            else dlong(dts[0]) if dts else "")
    heads = "".join(f"<th>{dhdr(dt)}</th>" for dt in plan["dates"])
    n_rr = sum(1 for d in plan["divisions"] if d["fmt"] == "round_robin")
    rr_chip = (f'<span class="chip" id="chipRR">{n_rr} round-robin — schedule as group draws'
               '</span>') if n_rr else ""
    payload = json.dumps(plan)   # deterministic: plan dicts are built in fixed order

    # ---- SKIN-FIN-1: the BRAND-1 design lock, on the board -----------------------------------
    # The tokens are `DESIGN_RECORD.md` §2's palette table verbatim, and the density is §5's
    # WORKING rhythm — the one this surface shares with the edit console: 16px base, ONE control
    # radius at 7px, spacing on 4 / 8 / 12 / 16. What this replaced was CUI-2's green/paper
    # family: 19 colours on this file, 18 of them values the record never named.
    #
    # NOTHING BELOW PAINTS A COLOUR DIRECTLY. Every value is declared once in `:root` and read
    # through `var()`, which is what makes the record and this surface one edit apart rather than
    # forty; it is also what `tests/brand1_design_lock.py` part C's rule depends on — a colour
    # cannot enter a surface without entering the record's table first.
    #
    # ⚠ THE RECORD HAS TWO MESSAGE LEVELS AND ONLY TWO (§2), so the CUI-2 BLUE FAMILY IS GONE
    # rather than re-toned: the semifinal shading, the round-robin badge and the stale banner all
    # move onto greys and the notice gold. A third level would teach the director a colour
    # language the other two consoles do not speak.
    # Light mode only — this page publishes as an artifact.
    css = """
    :root{
      --w-bg:#ffffff; --w-ink:#141414; --w-muted:#5f5f5f; --w-faint:#8f8f8f;
      --w-hair:#e9e6e3; --w-rule:#cfcac6; --w-rule-2:#d8d4d0; --w-off:#d9d5d1;
      --w-dim:#9a9a9a; --w-slate:#4a4a4a;
      --w-red:#ba141a; --w-red-h:#9a1116;
      --w-sun:#ffc20e; --w-avoid:#c99700; --w-cell-2:#fff3cd;
      --w-notice-bg:#fdf7e8; --w-notice-line:#efdcb0; --w-notice-ink:#8a6a08;
      --w-stop-bg:#fbf1f1; --w-stop-line:#eecdcf;
      --fs-2xl:28px; --fs-xl:23px; --fs-lg:19px; --fs-md:17px; --fs-base:16px; --fs-sm:14px; --fs-xs:12px;
      --fs-mono:15px; --fs-mono-sm:13px; --radius:7px;
      --w-display:'Trebuchet MS','Avenir',sans-serif;
      --w-body:Arial, Helvetica, sans-serif;
      --w-mono:'SF Mono',Consolas,ui-monospace,monospace;
    }
    *{box-sizing:border-box}
    body{font-family:var(--w-body);font-size:var(--fs-base);line-height:1.5;margin:0;
      padding:16px 16px 40px;color:var(--w-ink);background:var(--w-bg);-webkit-font-smoothing:antialiased}
    /* ---- the masthead (SKIN-FIN-1) ---------------------------------------------------------
       The board used to open on a lone heading reading "Finals Editor" — naming the tool rather
       than the tournament, on the one surface where the director is deciding his own week. The
       masthead is the setup console's, so the two read as one product: the mark on its own line
       BESIDE the name (`DESIGN_RECORD.md` §3 rule 3 allows either), the eyebrow saying which
       screen this is, the name itself, and the slate's own dates under it.
       ⚠ 150px IS THE RECORD'S MEASURED FLOOR (§3 rule 5) AND IS NOT NEGOTIABLE DOWNWARD — the
       mark's nine separable shapes close below 119px. The 16px gap to the name is rule 4's clear
       space (the dot's height, 9.8% of 150px = ~15px) rounded UP to a rhythm step, declared on
       the mark itself so a later edit to the parent cannot silently lose it. */
    header{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:nowrap;
      padding:0 0 12px;margin:0 0 12px;border-bottom:1px solid var(--w-hair)}
    .mast-left{display:flex;align-items:center;gap:16px;min-width:0;flex:1 1 auto}
    .mark{display:block;width:150px;height:auto;margin:0;flex:0 0 auto}
    .mast-id{min-width:0}
    .eyebrow{font-family:var(--w-body);font-size:var(--fs-xs);font-weight:700;letter-spacing:.12em;
      text-transform:uppercase;color:var(--w-faint);margin:0 0 4px}
    h1{font-family:var(--w-display);font-size:var(--fs-2xl);font-weight:500;letter-spacing:-.01em;
      line-height:1.1;margin:0;color:var(--w-ink)}
    .mast-sub{font-size:var(--fs-sm);color:var(--w-muted);margin:4px 0 0}
    .mast-right{display:flex;align-items:center;gap:8px;flex:0 0 auto}
    .strip{margin:0 0 8px} .chip{display:inline-block;font-family:var(--w-body);font-size:var(--fs-mono-sm);
      padding:4px 8px;border:1px solid var(--w-rule);border-radius:var(--radius);margin-right:4px;
      background:var(--w-bg)}
    /* ⚠ THE CHIPS TOOK THE 7px RADIUS RATHER THAN KEEPING THEIR 999px PILL. The pill is the
       LEDGER rhythm's control shape (`DESIGN_RECORD.md` §5) and belongs to the setup console and
       the printed pages; this surface is Working, and the Working column names one radius. */
    .chip.warn{background:var(--w-notice-bg);border-color:var(--w-notice-line);color:var(--w-notice-ink)}
    /* PIN-1 (A1c): the board gets its OWN scroll region. This rule was overflow-x only, and
       because one axis is auto the browser coerced the other to auto too — so .wrap was
       already a scroll container, but with no height cap its scrollHeight equalled its
       clientHeight (1900 == 1900) and it never scrolled. A sticky header inside a box that
       never scrolls sticks to a scrollport that never moves, which is why it read as static.
       Capping the height against the measured band (--stickyH, below) is what gives the
       header something to pin against. overflow:auto keeps the sideways scroll, which is
       load-bearing at narrow widths. */
    .wrap{overflow:auto;max-height:calc(100vh - var(--stickyH, 200px) - 26px)}
    table{border-collapse:collapse} th,td{border:1px solid var(--w-hair);padding:4px 8px;text-align:center}
    th.div,td.div{text-align:left;white-space:nowrap;position:sticky;left:0;background:var(--w-bg);cursor:grab}
    /* the RR badge loses CUI-2's blue with the rest of that family (see the :root note): the
       record has two message levels and this is neither — it is a fact about the draw, so it
       reads as quiet furniture rather than as a third kind of flag. */
    .rrbadge{display:inline-block;font-family:var(--w-body);font-size:var(--fs-xs);font-weight:700;
      padding:1px 6px;margin-left:8px;border-radius:var(--radius);background:var(--w-hair);
      border:1px solid var(--w-rule);color:var(--w-muted);vertical-align:1px}
    thead th{background:var(--w-hair);font-size:var(--fs-sm)}
    /* PIN-1 (A1c, ruling 77): the whole header block pins AS A UNIT inside .wrap's scroll
       region — the date row and BOTH of FMAP-1's day-summary rows, from any scroll position.
       Deliberately on <thead>, not on `thead th`: the summary rows' cells are <td>, so a
       th-only rule pins the date row and abandons both FMAP-1 rows — a third of the fix,
       looking finished. A sticky <thead> carries <td> and <th> alike, so FMAP-1's
       <td class="div"> labels stay exactly as they are and the golden's `thead th == dates+1`
       guard is untouched. The edit console's literal per-cell pattern
       (schedule_editor.html:142-143) is the named fallback if a target browser disagrees. */
    #fboard thead{position:sticky;top:0;z-index:20}
    .cap th{font-weight:600;background:var(--w-hair)}
    /* FMAP-1: the two day-summary rows. They sit in <thead> so the whole header block stays
       together, but their row LABEL is a <td class="div">, never a <th> — the golden asserts
       `thead th == dates + 1` as a structural guard, and a <th> label here would push that to
       13 and tempt a build into re-pointing a live assertion. `.hrow .div` is styled directly,
       so the appearance is identical to a header cell either way. */
    .hrow td{background:var(--w-hair);font-size:var(--fs-mono-sm);
      font-variant-numeric:tabular-nums;font-family:var(--w-body)}
    .hrow td.div{font-weight:600;cursor:default;background:var(--w-bg)}
    /* ⚠ THE OVER-THRESHOLD NUMERAL IS `--w-notice-ink`, NOT `--w-avoid`, AND THAT IS A
       DELIBERATE STEP AWAY FROM THE APPROVED MOCK. Measured: the mock's gold-on-cream pair is
       **2.40:1**, where the CUI-2 pair it replaces was **4.57:1** — so taking the mock's exact
       tones here would have made the one number on this board that means "this day is over your
       own threshold" the hardest number on it to read. `--w-notice-ink` on the same cream is
       **4.57:1**, identical to what shipped, and it is the record's own notice text colour, so
       the level the cell is speaking at is the level it is painted at. */
    .hrow td.over{background:var(--w-cell-2);color:var(--w-notice-ink);font-weight:700}
    /* ---- the round ramp, on the record's own greys -----------------------------------------
       Four steps toward the Final, light to dark: earlier rounds carry no ground at all and a
       faint numeral, the quarterfinal takes the hairline grey, the semifinal the step above it,
       and the Final the brand red. The record names no light-grey RAMP — it names five greys, of
       which these are three — so the depth is built from what §2 has rather than from a fourth
       tint minted here (§7 rule 1). */
    td.F{background:var(--w-red);color:var(--w-bg);font-weight:700} td.SF{background:var(--w-rule-2)}
    /* the earlier rounds' numeral is `--w-muted`, again above the mock's own tone: the mock's
       `--w-dim` on this ground measures **2.81:1** against the **4.45:1** the shipped pair held,
       and these labels sit on ~100 cells of a 500-cell board. `--w-muted` is **6.39:1** and still
       reads as the quiet end of the ramp, because the GROUND is doing that work. */
    td.QF{background:var(--w-hair)} td.R{background:var(--w-bg);color:var(--w-muted)}
    .cap td{font-variant-numeric:tabular-nums;font-family:var(--w-body);font-size:var(--fs-mono-sm)}
    .over{background:var(--w-cell-2);color:var(--w-notice-ink);font-weight:700}
    tr.card[draggable=true]{cursor:grab} tr.card.dragging{opacity:.45}
    tr.card.sel td.div{outline:3px solid var(--w-red);outline-offset:-3px}
    td.drop-ok{outline:3px dashed var(--w-red);outline-offset:-3px}
    /* the day the TD locked himself, in the mark's own yellow — one glance apart from the
       guidance layer's BANDED gold ring, which means something else entirely. */
    td.moved-f{box-shadow:inset 0 0 0 3px var(--w-sun)}
    /* CUI-2: one warning bar at the top. .stop is the hard refusal (a final that
       cannot physically fit); everything else warns and never blocks. */
    .warnbox{display:none;margin:0 0 12px;padding:12px 16px;border-radius:var(--radius);
      background:var(--w-notice-bg);border:1px solid var(--w-notice-line);color:var(--w-notice-ink);
      font-size:var(--fs-md);white-space:pre-line;max-height:22vh;overflow:auto}
    .warnbox.show{display:block}
    .warnbox.stop{background:var(--w-stop-bg);border-color:var(--w-stop-line);color:var(--w-red);
      font-weight:600}
    /* CUI-2 patch (Operator review): the action row stays put while the board scrolls. The
       two alert boxes ride with it — a refused drop must be visible when you are scrolled
       down a 50-row table, otherwise the one hard refusal in the product fires off-screen. */
    /* SKIN-FIN-1: the band now carries the CHIP ROW, the guidance legend (injected between the
       two by `finals_guidance.py`) and the refusal — the three things that have to stay on
       screen while a 50-row board scrolls under them. The action row LEFT it for the masthead,
       where the approved mock puts it; the refusal, which is the load-bearing half of CUI-2's
       original patch, stays. */
    .stickytop{position:sticky;top:0;z-index:30;background:var(--w-bg);padding-top:8px}
    /* the Working rhythm's button: 32px tall, 12px sides, 7px radius (`DESIGN_RECORD.md` §5) */
    button{font-family:var(--w-body);font-size:var(--fs-sm);font-weight:600;height:32px;padding:0 12px;
      border:1px solid var(--w-rule);border-radius:var(--radius);background:var(--w-bg);
      color:var(--w-ink);cursor:pointer}
    button:hover{border-color:var(--w-red);color:var(--w-red)}
    button.primary{background:var(--w-red);color:var(--w-bg);border-color:var(--w-red)}
    button.primary:hover{background:var(--w-red-h);border-color:var(--w-red-h);color:var(--w-bg)}
    button:focus-visible{outline:2px solid var(--w-red);outline-offset:2px}
    /* HDR-1 (ruling 79): `label.cf` (the approval tick box) and `.gate-note` (the header
       status line) were removed here with the elements they styled — this build is what made
       them unreachable, so they go with it rather than being left as debris. */
    /* ---- the emit block, under the board (SKIN-FIN-1, approved mock) ------------------------
       It used to sit ABOVE the chip row and the board, so the one thing the TD produces at the
       END of the task was the first thing between him and the thing he was doing. It is the last
       panel on the page now, and it says what it is — the block only appears once there is one. */
    .emitwrap{margin:12px 0 0}
    .emithead{display:flex;align-items:center;gap:16px;margin:0 0 8px}
    .emitcap{font-family:var(--w-body);font-size:var(--fs-xs);font-weight:700;letter-spacing:.12em;
      text-transform:uppercase;color:var(--w-faint)}
    pre#out{display:none;max-height:300px;overflow:auto;background:var(--w-bg);color:var(--w-ink);
      border:1px solid var(--w-rule);padding:12px;border-radius:var(--radius);font-family:var(--w-mono);
      font-size:var(--fs-mono);white-space:pre-wrap;word-break:break-word;user-select:all;margin:0}
    pre#out.show{display:block}
    pre#out.selected{outline:2px solid var(--w-red);outline-offset:1px}
    """

    js = """
    "use strict";
    var PLAN = __PLAN__;
    var DATES = PLAN.dates, N = DATES.length;
    var CAP_BUCKET = {singles:"singles", mixed:"doubles", doubles:"doubles"};
    // SKIN-FIN-1: `TYPE_ORDER` and `typeRank` RETIRE HERE, with the fifth D-3 waiver open. They
    // were FMAP-1's fix for a falsy-zero read in the console's own client-side row sort; DIV-1's
    // fourth waiver then retired that sort entirely — the line below takes the emit's order,
    // which already carries rule 44's — and the pair has been unreachable debris ever since,
    // kept only because the file was frozen. `master_schedule._TYPE_ORDER` is a DIFFERENT
    // constant, is the engine's clock order, and is untouched (`tests/div1_order.py` part A
    // guards it).
    var DIVS = PLAN.divisions.slice();   // DIV-1: the emit already carries rule 44's one order
    var BY_EV = {}; DIVS.forEach(function(d){ BY_EV[d.event]=d; });
    var fday = {}, moved = {}, selected = null, dragEv = null;
    function resetState(){
      fday = {}; Object.keys(PLAN.finals_day).forEach(function(k){ fday[k]=PLAN.finals_day[k]; });
      moved = {}; Object.keys(PLAN.pins||{}).forEach(function(k){ moved[k]=PLAN.pins[k]; });
      selected = null;
    }
    function roundLabel(r,total){var b=total-r;return b===0?"Final":b===1?"Semifinal":b===2?"Quarterfinal":"Round "+r;}
    function abbr(l){return l==="Final"?"F":l==="Semifinal"?"SF":l==="Quarterfinal"?"QF":l.replace("Round ","R");}
    // FMAP-1 (ruling 63): the TD-facing date form — "Sat 1/24", matching the column headers and
    // the ruled warning form. UTC throughout, so the label can never slide a day on a machine
    // west of Greenwich. `finals_map_from_doc` keeps ISO: it raises to an engineer, not the TD.
    var WEEKDAY = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];
    function shortDate(dt){
      var p = dt.split("-");
      return WEEKDAY[new Date(Date.UTC(+p[0], +p[1]-1, +p[2])).getUTCDay()] +
             " " + (+p[1]) + "/" + (+p[2]);
    }
    // the EXACT build_master_schedule cascade clamp: start<0 -> 0, cells capped at the last day
    function cascade(ev){
      var d = BY_EV[ev], fi = DATES.indexOf(fday[ev]), out = {}, warn = null;
      if (fi < 0) fi = N-1;
      var start = fi - (d.rounds-1);
      if (start < 0){ warn = ev+": "+d.rounds+" rounds do not fit before finals "+fday[ev]; start = 0; }
      for (var r=1; r<=d.rounds; r++) out[roundLabel(r,d.rounds)] = DATES[Math.min(start+(r-1), N-1)];
      return {days:out, warn:warn};
    }
    function capAudit(){
      var per = {}; DATES.forEach(function(dt){ per[dt]={singles:0,doubles:0}; });
      DIVS.forEach(function(d){ var dt=fday[d.event]; if(per[dt]) per[dt][CAP_BUCKET[d.etype]]++; });
      return per;
    }
    // FMAP-1: PLANNED matches per day, re-summed against the LIVE cascade. `round_matches` is
    // keyed per division per round precisely so this is a join against the current day map
    // rather than a stored per-day total — a stored total is stale the instant the TD drags.
    // The counts came off the approved draws upstream; nothing here guesses from draw_size.
    function dayMatches(){
      var per = {}, RM = PLAN.round_matches || {};
      DATES.forEach(function(dt){ per[dt]=0; });
      DIVS.forEach(function(d){
        var rm = RM[d.event]; if (!rm) return;
        var days = cascade(d.event).days;
        Object.keys(days).forEach(function(lbl){
          var n = rm[lbl];
          if (n && per[days[lbl]] != null) per[days[lbl]] += n;
        });
      });
      return per;
    }
    function warnings(){
      var w = [];
      DIVS.forEach(function(d){ var c=cascade(d.event); if(c.warn) w.push(c.warn); });
      // FMAP-1 (ruled form): "Sun 2/1 \\u00b7 10s" / "Sat 1/24 \\u00b7 128 matches". Compact,
      // because the TD now reads the same fact off the day-summary rows while dragging; the bar
      // is the running tally, not the explanation. Every one of these WARNS and never blocks —
      // the sole hard refusal on this surface stays the structurally impossible pin.
      var per = capAudit(), mpd = dayMatches(), tgt = PLAN.matches_per_day_target;
      DATES.forEach(function(dt){
        if (per[dt].singles > PLAN.cap_singles) w.push(shortDate(dt)+" \\u00b7 "+per[dt].singles+"s");
        if (per[dt].doubles > PLAN.cap_doubles) w.push(shortDate(dt)+" \\u00b7 "+per[dt].doubles+"d");
        if (tgt && mpd[dt] > tgt) w.push(shortDate(dt)+" \\u00b7 "+mpd[dt]+" matches");
      });
      return w;
    }
    function el(id){ return document.getElementById(id); }
    function render(){
      var tb = el("tbody"), h = [];
      DIVS.forEach(function(d){
        var c = cascade(d.event).days, cell = {};
        Object.keys(c).forEach(function(lbl){ cell[c[lbl]] = abbr(lbl); });
        var tds = [];
        DATES.forEach(function(dt, i){
          var v = cell[dt] || "";
          var cls = v==="F"?"F":v==="SF"?"SF":v==="QF"?"QF":(v?"R":"");
          if (v==="F" && moved[d.event]) cls += " moved-f";
          tds.push('<td class="fcell '+cls+'" data-di="'+i+'">'+v+'</td>');
        });
        var rr = (d.fmt === "round_robin");   // F7-4: RR groups bind too — drags fully apply
        h.push('<tr class="card'+(selected===d.event?" sel":"")+'" draggable="true" data-ev="'+
               d.event.replace(/&/g,"&amp;").replace(/"/g,"&quot;")+'">'+
               '<td class="div"'+(rr?' title="round-robin — all group draws follow this division\\'s day map"':'')+'>'+
               d.event.replace(/&/g,"&amp;")+(rr?'<span class="rrbadge">RR</span>':'')+'</td>'+
               tds.join("")+'</tr>');
      });
      var per = capAudit(), caps = [];
      DATES.forEach(function(dt){
        var s = per[dt].singles, d2 = per[dt].doubles;
        var over = (s > PLAN.cap_singles || d2 > PLAN.cap_doubles);
        caps.push('<td class="'+(over?"over":"")+'">'+((s||d2)?(s+"s/"+d2+"d"):"")+'</td>');
      });
      h.push('<tr class="cap"><th class="div">Finals / day</th>'+caps.join("")+'</tr>');
      tb.innerHTML = h.join("");
      // FMAP-1: the two day-summary rows, rebuilt on EVERY render — which is every drag, every
      // click-to-place and every reset. That is the whole point: the two facts the TD needs
      // while deciding used to live 1,803px below the decision. Labels are <td class="div">,
      // never <th> (see the .hrow note in the stylesheet). Both rows are PLANNED figures.
      var mpd = dayMatches(), tgt = PLAN.matches_per_day_target, mcells = [], fcells = [];
      DATES.forEach(function(dt){
        var n = mpd[dt];
        mcells.push('<td class="'+(tgt && n > tgt ? "over" : "")+'">'+(n || "")+'</td>');
        var s = per[dt].singles, d2 = per[dt].doubles;
        var over = (s > PLAN.cap_singles || d2 > PLAN.cap_doubles);
        fcells.push('<td class="'+(over?"over":"")+'">'+((s||d2)?(s+"s/"+d2+"d"):"")+'</td>');
      });
      el("rowMatches").innerHTML = '<td class="div">Matches</td>'+mcells.join("");
      el("rowFinals").innerHTML = '<td class="div">Finals s/d</td>'+fcells.join("");
      // HDR-1 (ruling 79): the amber warnings BOX is gone from the header. warnings() still
      // runs — the count rides on the amber "n warnings" chip, and the per-day figures are
      // still on the board itself (the Matches row and Finals s/d row go amber past
      // threshold). Nothing about what counts as a warning changed; only where it is shown.
      var w = warnings();
      el("chipMoved").textContent = Object.keys(moved).length + " moved";
      el("chipWarn").textContent = w.length + " warnings";
      el("chipWarn").className = "chip" + (w.length ? " warn" : "");
      wire();
      syncStickyHeight();
    }
    // PIN-1 (A1c, ruling 78): the board's scroll region is sized against the locked band, so
    // the pinned header sits exactly under it at any window size. Same pattern, same name, as
    // schedule_editor.html:1527-1530 — the two surfaces read as one product. The band has FOUR
    // heights, not three, and the one the TD always sees on arrival (214px, four warning lines
    // on the committed field) is not one a hard-coded number would have guessed.
    function syncStickyHeight(){
      var b = document.querySelector(".stickytop"); if (!b) return;
      document.documentElement.style.setProperty("--stickyH", b.offsetHeight+"px");
    }
    // F7-6 guard: a final can't land before its rounds fit — the courier gate would reject
    // this map, so the drop is refused here (edit-console conflict-guard precedent).
    //
    // FMAP-1 / ruling 60: this is now the ONE place the need-1 test lives on this surface, and
    // both callers — the drop (moveFinal) and the dragover affordance — go through it. It is
    // deliberately NOT copied into the highlight: need-1 already has exactly three homes
    // (master_schedule.py:130/:153/:180, the engine's authority; finals_plan.py:87, the courier
    // gate; and here, the console), one rule across two languages. A fourth mirror is how the
    // console starts accepting a map the gate refuses.
    function canLand(ev, di){
      var d = BY_EV[ev];
      if (!d || di==null || di<0 || di>=N) return false;
      return di >= d.rounds - 1;
    }
    function moveFinal(ev, di){
      if (!BY_EV[ev] || di==null || di<0 || di>=N) return;
      if (fday[ev] === DATES[di]) return;
      var need = BY_EV[ev].rounds;
      if (!canLand(ev, di)){
        // The one hard refusal (Hybrid ruling): this final physically cannot fit.
        // Every other flag on this page warns and lets the choice stand.
        block(ev+" needs "+need+" days of play, so its final cannot land on "+shortDate(DATES[di])+
              ". The earliest it can finish is "+shortDate(DATES[need-1])+".");
        return;
      }
      hideBlock();
      fday[ev] = DATES[di]; moved[ev] = DATES[di];
      selected = null; render(); announce(ev+" final -> "+DATES[di]);
    }
    // PIN-1: these two show and hide the refusal box WITHOUT going through render(), so they
    // change the locked band's height with nothing else re-measuring it. Syncing only in
    // render() leaves the board mis-sized (by 62px) for exactly as long as a refusal is on
    // screen — the worst possible moment, since the refusal is the one thing the TD is
    // reading. Both call sites are required; two of the three is the trap.
    function block(msg){
      var b = el("blockmsg");
      b.textContent = msg; b.className = "warnbox stop show"; announce(msg); syncStickyHeight();
    }
    function hideBlock(){ el("blockmsg").className = "warnbox stop"; syncStickyHeight(); }
    function clearHints(){
      document.querySelectorAll("td.drop-ok").forEach(function(t){ t.classList.remove("drop-ok"); });
    }
    function wire(){
      document.querySelectorAll("tr.card").forEach(function(tr){
        var ev = tr.getAttribute("data-ev");
        tr.addEventListener("dragstart", function(e){
          dragEv = ev; tr.classList.add("dragging");
          try{ e.dataTransfer.setData("text/plain", ev); }catch(_){}
        });
        tr.addEventListener("dragend", function(){ dragEv=null; tr.classList.remove("dragging"); clearHints(); });
        tr.querySelector("td.div").addEventListener("click", function(){
          selected = (selected===ev ? null : ev); render();
        });
        tr.querySelectorAll("td.fcell").forEach(function(td){
          // FMAP-1 (ruling 60): the affordance stops lying. It used to paint "you may drop
          // here" on every cell with no feasibility test, so the board invited the one move it
          // would then hard-refuse. Only the HIGHLIGHT is gated — preventDefault still runs, so
          // a TD who drops anyway still gets the refusal that EXPLAINS itself rather than a
          // dead cell. moveFinal's outcome is untouched and stays outside D-3's waiver.
          td.addEventListener("dragover", function(e){
            if(!dragEv) return;
            e.preventDefault(); clearHints();
            if (canLand(dragEv, parseInt(td.getAttribute("data-di"), 10))) td.classList.add("drop-ok");
          });
          td.addEventListener("dragleave", function(){ td.classList.remove("drop-ok"); });
          td.addEventListener("drop", function(e){
            e.preventDefault(); clearHints();
            var src = dragEv || (e.dataTransfer ? e.dataTransfer.getData("text/plain") : null);
            if (src) moveFinal(src, parseInt(td.getAttribute("data-di"), 10));
          });
          td.addEventListener("click", function(){
            if (selected) moveFinal(selected, parseInt(td.getAttribute("data-di"), 10));
          });
        });
      });
    }
    function announce(msg){ el("ariaLive").textContent = msg; }
    function emitDoc(){
      var fm = {};
      Object.keys(fday).sort().forEach(function(k){ fm[k]=fday[k]; });
      var mv = {};
      Object.keys(moved).sort().forEach(function(k){ mv[k]=moved[k]; });
      // HDR-1 (ruling 79): the approval tick box is gone from the header, so `confirmed` is
      // no longer a thing the TD sets separately — pressing "Save my finals days" IS the
      // approval. The FIELD stays in td-finals-map/v1 (§14) and stays a boolean, so the wire
      // format and every Python consumer are unchanged; only what fills it changed.
      return { schema:"td-finals-map/v1", tournament:PLAN.tournament,
               confirmed: true, finals_map: fm, pins: mv };
    }
    el("emitBtn").addEventListener("click", function(){
      var o = el("out");
      o.textContent = JSON.stringify(emitDoc(), null, 2);
      o.classList.add("show"); o.scrollIntoView({behavior:"smooth", block:"nearest"});
      showToggle(true);
      announce(Object.keys(moved).length + " change(s) ready.");
    });
    // CUI-2 patch: the block folds away once copied. Opens EXPANDED - you emit in order to
    // copy, and hiding it at that moment fights the task.
    // SKIN-FIN-1: the caption and the toggle are ONE element now (`#outCap`), because the block
    // moved under the board and a standing caption over an empty panel would announce something
    // that does not exist yet. Everywhere the toggle used to be shown or hidden, the head is.
    function showToggle(open){
      var t = el("outToggle"); if (!t) return;
      el("outCap").hidden = false;
      t.textContent = open ? "Hide this block" : "Show the block";
      t.setAttribute("aria-expanded", open ? "true" : "false");
    }
    el("outToggle").addEventListener("click", function(){
      var open = el("out").classList.toggle("show");
      showToggle(open);
      announce(open ? "Block shown." : "Block hidden.");
    });
    // ---------------------------------------------------------------------
    // CUI-2 - copy that tells the truth. The old handler announced "Copied"
    // from the failure path and swallowed execCommand's exception, so in a
    // sandboxed artifact frame (clipboard API unavailable, execCommand
    // blocked) it claimed success while the clipboard stayed empty. Both
    // programmatic paths are now checked, and when they fail the text is
    // selected on the page so the reader can copy it with the keyboard.
    // ---------------------------------------------------------------------
    function legacyCopy(t){
      var ta = document.createElement("textarea");
      ta.value = t; ta.setAttribute("readonly","");
      ta.style.position="fixed"; ta.style.top="-1000px"; ta.style.opacity="0";
      document.body.appendChild(ta); ta.select();
      var ok = false;
      try{ ok = document.execCommand("copy"); }catch(_){ ok = false; }
      document.body.removeChild(ta);
      return ok === true;
    }
    function copyKey(){ return (navigator.platform||"").indexOf("Mac")>-1 ? "\\u2318 C" : "Ctrl + C"; }
    el("copyBtn").addEventListener("click", function(){
      var o = el("out");
      if (!o.textContent){ o.textContent = JSON.stringify(emitDoc(), null, 2); o.classList.add("show"); }
      el("outCap").hidden = false;
      var t = o.textContent, btn = this;
      function done(){
        btn.textContent = "Copied";
        announce("Copied to the clipboard.");
        setTimeout(function(){ btn.textContent = "Copy"; }, 1600);
      }
      function manual(){
        var msg;
        try{
          var r = document.createRange(); r.selectNodeContents(o);
          var sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(r);
          o.classList.add("selected");
          msg = "Press " + copyKey() + " to copy \\u2014 your finals days are selected above.";
        }catch(_){ msg = "Select the block above and copy it."; }
        // HDR-1 (ruling 79): the header carries no text at all, so this instruction no longer
        // appears ON SCREEN — the text is still selected on the page and the message still
        // goes to the aria-live region, but a sighted TD whose clipboard is blocked now gets
        // no visible cue. KNOWN AND ACCEPTED at the Operator's instruction ("just the
        // buttons"); the offered fix — putting the shortcut on the Copy button's own label —
        // was NOT taken, and is recorded as OI-42 rather than applied here.
        announce(msg);
      }
      if (navigator.clipboard && navigator.clipboard.writeText){
        navigator.clipboard.writeText(t).then(done, function(){ if (legacyCopy(t)) done(); else manual(); });
      } else if (legacyCopy(t)){ done(); } else { manual(); }
    });
    el("resetBtn").addEventListener("click", function(){
      resetState(); el("out").classList.remove("show"); el("outCap").hidden = true; render();
      announce("Back to the suggested days.");
    });
    // PIN-1: the band wraps at narrow widths, so its height changes with the window even
    // though nothing re-renders (schedule_editor.html:1531).
    window.addEventListener("resize", syncStickyHeight);
    resetState(); render();
    """

    return f"""<!doctype html><meta charset=utf-8><title>{title}</title><style>{css}</style>
<header><div class="mast-left"><img class="mark" alt="WYN Tennis Academy"
src="data:image/png;base64,{_MARK_B64}"><div class="mast-id"><p
class="eyebrow">Finals map — TD edit</p><h1>{tname}</h1><p class="mast-sub">{span}</p></div></div>
<div class="mast-right"><button id="resetBtn">Start over</button><button
id="copyBtn">Copy</button><button class="primary" id="emitBtn">Save my finals days</button></div>
</header>
<div class="stickytop">
<p class="strip"><span class="chip">{len(plan["divisions"])} divisions</span><span
class="chip">{len(plan["dates"])} days</span>{rr_chip}<span class="chip" id="chipMoved">0
moved</span><span class="chip" id="chipWarn">0 warnings</span></p>
<div class="warnbox stop" id="blockmsg" role="alert"></div>
</div>
<div class="wrap"><table id="fboard"><thead><tr><th class="div">Division
({len(plan["divisions"])})</th>{heads}</tr><tr class="hrow" id="rowMatches"></tr><tr
class="hrow" id="rowFinals"></tr></thead><tbody id="tbody"></tbody></table></div>
<section class="emitwrap"><div class="emithead" id="outCap" hidden><span class="emitcap">After
&quot;Save my finals days&quot; — the block you copy and paste back to the run</span><button
id="outToggle" aria-expanded="true" aria-controls="out">Hide this block</button></div>
<pre id="out"></pre></section>
<div id="ariaLive" aria-live="polite" style="position:absolute;left:-9999px"></div>
<script>{js.replace("__PLAN__", payload)}</script>
"""


def _selftest():
    import draws_pdf
    import master_schedule as MS
    draws = draws_pdf.parse_draws(level="1") + draws_pdf.parse_draws(level="2")
    divs = MS.divisions_from_draws(draws)
    dates = ["2026-01-23", "2026-01-24", "2026-01-25", "2026-01-26", "2026-01-27",
             "2026-01-28", "2026-01-29", "2026-01-30", "2026-01-31", "2026-02-01"]
    import wwtc_pipeline as W          # deferred: W imports this module at load
    ms = MS.build_master_schedule(divs, dates)
    rm = W._round_matches(draws, divs)
    plan = finals_plan(ms, divs, tournament="WWTC 2026", round_matches=rm,
                       matches_per_day_target=125)
    assert plan["schema"] == FINALS_PLAN_SCHEMA
    assert plan["dates"] == dates and len(plan["divisions"]) == len(divs)
    assert set(plan["finals_day"]) == {d.event for d in divs}, "finals_day must cover every division"
    cells = sum(len(rd) for rd in plan["round_day"].values())
    # FMAP-1: round_matches must join round_day with no leftover key on either side, or the
    # console's day summary would silently drop (or invent) a round's worth of matches.
    assert set(plan["round_matches"]) == set(plan["round_day"]), "round_matches must cover every division"
    for ev, rd in plan["round_day"].items():
        assert set(plan["round_matches"][ev]) == set(rd), f"{ev}: round_matches keys must mirror round_day"
    derived = sum(sum(v.values()) for v in plan["round_matches"].values())
    print(f"finals_plan: {len(plan['divisions'])} divisions, {cells} round-day cells, "
          f"{derived} planned matches, {len(plan['warnings'])} warnings")
    # determinism
    assert plan == finals_plan(MS.build_master_schedule(divs, dates), divs, tournament="WWTC 2026",
                               round_matches=W._round_matches(draws, divs),
                               matches_per_day_target=125)
    # fixed point: pinning EVERY division at its computed day reproduces the cascade exactly
    ms2 = MS.build_master_schedule(divs, dates, finals_map=plan["finals_day"])
    assert ms2.round_day == ms.round_day and ms2.finals_day == ms.finals_day, \
        "full-map pin must be a fixed point of the cascade"
    # the return trip validates loudly
    doc = {"schema": FINALS_MAP_SCHEMA, "finals_map": dict(plan["finals_day"])}
    assert finals_map_from_doc(doc, dates, set(plan["finals_day"])) == plan["finals_day"]
    for bad, err in [({"schema": "nope"}, "expected"),
                     ({"schema": FINALS_MAP_SCHEMA, "finals_map": {}}, "missing or empty"),
                     ({"schema": FINALS_MAP_SCHEMA, "finals_map": {"X": dates[0]}}, "unknown"),
                     ({"schema": FINALS_MAP_SCHEMA,
                       "finals_map": {divs[0].event: "1999-01-01"}}, "outside")]:
        try:
            finals_map_from_doc(bad, dates, {d.event for d in divs})
            raise AssertionError(f"should have rejected: {bad}")
        except ValueError as e:
            assert err in str(e), (err, str(e))
    # F7-6: a structurally infeasible pin (final before its rounds fit) is rejected
    need3 = next(d for d in divs if d.rounds >= 3)
    try:
        finals_map_from_doc({"schema": FINALS_MAP_SCHEMA, "finals_map": {need3.event: dates[0]}},
                            dates, {d.event for d in divs},
                            rounds_by={d.event: d.rounds for d in divs})
        raise AssertionError("infeasible pin accepted")
    except ValueError as e:
        assert "cannot finish" in str(e) and dates[need3.rounds - 1] in str(e), str(e)
    # renderer: generated artifact is self-contained, embeds the plan, deterministic
    html = render_finals_console(plan)
    assert html == render_finals_console(plan), "render must be deterministic"
    for needle in ("td-finals-map/v1", "emitBtn", "resetBtn", "Finals / day", plan["dates"][0],
                   "rowMatches", "rowFinals", "Finals s/d",    # FMAP-1: the two summary rows
                   "#fboard thead{position:sticky"):   # PIN-1: a tripwire, NOT the proof —
        # it shows the rule shipped, not that the header pins. The proof is the golden's
        # browser assertion (tests/finals_console_golden.py), which fails against pre-PIN-1
        # code with {'date': False, 'matches': False, 'finals': False}.
        assert needle in html, f"generated console missing {needle!r}"
    # FMAP-1 / ruling 60: need-1 is SHARED between the drop and the dragover affordance, never
    # copied. Three occurrences = one definition + exactly two callers; a fourth would be the
    # copy this build exists to avoid.
    assert html.count("canLand") == 3, f"canLand must be shared, not copied: {html.count('canLand')}"
    # HDR-1 (ruling 79): the header is the three buttons and nothing else. These are tripwires
    # against a later build quietly reinstating any of it; `el("gate")` is checked too, because
    # the element and the four handlers that wrote into it had to go together — leaving one
    # write behind would throw on a null element the moment that button was pressed.
    for removed in ('id="confirm"', 'id="warnbox"', 'id="gate"', 'el("gate")',
                    "Nothing needs changing", "Back to the days we suggested"):
        assert removed not in html, f"HDR-1 removed this from the header, it is back: {removed!r}"
    assert 'id="blockmsg"' in html, "the hard-refusal box is NOT what HDR-1 removed"
    for banned in ("fetch(", "XMLHttpRequest", "WebSocket", "<script src"):
        assert banned not in html, f"generated console must be offline: found {banned!r}"
    try:
        render_finals_console({"schema": "nope"})
        raise AssertionError("renderer accepted a non-plan doc")
    except ValueError:
        pass
    print(f"render_finals_console: {len(html)//1024} KB, offline, deterministic")
    print("finals_plan self-test OK")


if __name__ == "__main__":
    _selftest()
