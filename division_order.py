"""division_order.py — DIV-1: the ONE division display order (rule 44) and the division
universe (rule 45).

The tournament director reads the same list of divisions in six places — the editor's picker,
the finals console, the order-of-play sheet, the CSV he hands out, the draw sheets he prints,
and the pre-publication report. He gave us one order for all six:

    Men's Singles -> Women's Singles -> Men's Doubles -> Women's Doubles
      -> Mixed Level 1 -> Mixed Level 2,   youngest to oldest inside each group.

That order is written HERE, once. No surface re-implements it; every surface imports
`sort_divisions` or `display_key`. (`schedule_editor.html` carries the one unavoidable second
implementation — a JS mirror, because the browser cannot import Python — and
`tests/div1_order.py` asserts the two agree on every emitted name.)

###########################################################################################
#  THE HARD GUARD — THIS MODULE IS DISPLAY ORDER ONLY.                                    #
#                                                                                          #
#  `master_schedule._TYPE_ORDER = {"singles": 0, "mixed": 1, "doubles": 2}` is the CLOCK   #
#  order (register rule 30): singles early, mixed midday, gender doubles late. It is a     #
#  DIFFERENT ORDER from the one in this file, and the two disagree about Mixed ON PURPOSE  #
#  — display puts Mixed LAST (ranks 4 and 5), the clock puts it in the MIDDLE (rank 1).    #
#  Both are correct. They answer different questions: *what order do I read the divisions  #
#  in* and *what time of day does this kind of match play*.                                #
#                                                                                          #
#  Measured cost of wiring one into the other: 6 of 50 divisions and 60 of 760 placed      #
#  matches get re-timed — 78 of 777 rows on the TD's own played record. `_TYPE_ORDER`      #
#  MUST NOT MOVE.                                                                          #
#                                                                                          #
#  The import direction is the guard. This module is imported BY the display surfaces and  #
#  INTO nothing in the placement path (`master_schedule`, `scheduler_multi`,               #
#  `scheduler_flow`, `draws_pdf`), and it imports none of them — it imports nothing from   #
#  this repo at all. `tests/div1_order.py` asserts both directions by source inspection,   #
#  so it fails loudly the first time someone reaches across.                               #
###########################################################################################

Rule 45 — the universe. All 80 USTA divisions ingest, at either sanction level, present or
absent. The 80 are enumerated once, below, straight off the regulation text:

  * Reg **IV.A.1**      — Men's and Women's Open
  * Reg **IV.A.2**      — Men's and Women's 30..100 in fives (15 age bands)
  * Rankings **A.1.a/b** — Mixed doubles at the SAME 16 ages
                           (Mixed is ABSENT from IV.A.2's list — a reader checking IV.A alone
                            will not find it; it is established in the rankings section.)

  5 groups x 16 ages = 80. 2026 ran 50 of them, so 30 must ingest EMPTY and break nothing.
  The universe is the sort's VOCABULARY and the ingest's tolerance — it is never a row
  source. A division with no entries adds no rows to any surface.

**NTRP and Family divisions are excluded, deliberately (D-50).** The WWTC runs neither, and
rule 44's order has no slot for them: they are not a gender/type/age triple, so there is no
honest place to sort them. A build that needs them needs a new rank, not a fallback.

**Mixed Level 1 vs Level 2 is the only input the key cannot derive from a division's name.**
Reg IV.C draws Level 2 from the SAME division list as Level 1, so the split is a property of
the TD's sanction that year, never of the division. It is passed in as `mixed_level_1` — a
list of division names, from the TD's setup tick-box or derived from which draws file the
division was printed in. This module never reads a global, never guesses, and never hardcodes
any year's split.
"""
from __future__ import annotations

import re

# The six display blocks, in the TD's order (2026-08-03). `display_key`'s first term is an
# index into this tuple.
DISPLAY_ORDER = ("men_singles", "women_singles",
                 "men_doubles", "women_doubles",
                 "mixed_l1", "mixed_l2")

_GROUP_RANK = {("men", "singles"): 0, ("women", "singles"): 1,
               ("men", "doubles"): 2, ("women", "doubles"): 3}
_MIXED_L1_RANK = 4
_MIXED_L2_RANK = 5

# Round-robin group draws are minted as `f"{division} — {group}"` by
# `wwtc_ingest.load_from_finalized_draws` — one EventSpec per printed group. Measured on the
# 2026 field: 9 of 51 emitted names carry the suffix and 0 of their 8 parents are emitted
# separately, so the group name REPLACES the parent rather than nesting under it. The suffix
# is therefore stripped before ranking and the group number is the last tie-break: a group
# sorts where its parent sorts, and sibling groups stay in group order. Alphabetically they
# scatter from #1 to #51.
_GROUP_SUFFIX = re.compile(r"\s*—\s*Group\s*(\d+)\s*$")

# The age is anchored to `& over` and NEVER guessed. `master_schedule._age` falls back to a
# bare `\b(\d{2})\b` when the anchor is absent, which would read a `Group 1`-style token as an
# age on a name shaped differently; that fallback is right for the clock and wrong here. A
# name with no `& over` token yields age 0 and sorts in the Open slot — see `age_is_stated`,
# which is how a surface tells a real Open division from a name it could not read.
_AGE = re.compile(r"(\d+)\s*&\s*over")

# Rule 45's universe: 5 groups x 16 ages. Age 0 == Open, and Open sorts FIRST (0 < 30).
AGES = (0, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100)
GROUPS = (("men", "singles"), ("women", "singles"),
          ("men", "doubles"), ("women", "doubles"), ("mixed", "doubles"))

_WHO = {"men": "Men's", "women": "Women's", "mixed": "Mixed"}


def division_name(gender: str, etype: str, age: int) -> str:
    """The canonical division name for a (gender, type, age) triple — the naming the printed
    draws use. `age=0` is Open. Round-trips through `parse_division`."""
    return f"{_WHO[gender]} {'Open' if not age else f'{age} & over'} {etype}"


# The 80, enumerated once, in the regulation's own order (group, then age). This is the
# vocabulary, not a row source — `sort_divisions` is what puts any SUBSET into display order,
# because the Mixed block's L1/L2 split is not knowable until the sanction is.
ALL_DIVISIONS = tuple(division_name(g, t, a) for (g, t) in GROUPS for a in AGES)


def parse_division(name):
    """`(gender, etype, age, group_no, parent)` for a division name.

    gender   : "men" | "women" | "mixed"
    etype    : "singles" | "doubles"
    age      : the `& over` age, or **0 for Open** (and for any name with no age token —
               see `age_is_stated`)
    group_no : the `— Group N` number, or 0 when the name carries no suffix
    parent   : the name with the group suffix stripped

    Total and never raises: a name outside the 80 still yields a key, which is what lets a
    never-before-seen division sort correctly on first sight with no code change (rule 45).
    """
    parent = _GROUP_SUFFIX.sub("", str(name))
    hit = _GROUP_SUFFIX.search(str(name))
    group_no = int(hit.group(1)) if hit else 0
    low = parent.lower()
    # "women" is tested before "men" on purpose — "Women's" contains "men".
    gender = "mixed" if "mixed" in low else ("women" if "women" in low else "men")
    etype = "doubles" if "doubles" in low else "singles"
    age = _AGE.search(low)
    return gender, etype, (int(age.group(1)) if age else 0), group_no, parent


def age_is_stated(name) -> bool:
    """True when the name carries an explicit `<n> & over` age token.

    False for the Open divisions, which have no token by design, and false for any name whose
    age could not be read. `display_key` sorts both at age 0 rather than guessing at one; this
    is how a surface tells the two apart and reports the second.
    """
    return bool(_AGE.search(str(name).lower()))


def is_mixed(name) -> bool:
    """True for a Mixed division — the only block whose rank depends on the sanction level."""
    return parse_division(name)[0] == "mixed"


def _l1_parents(mixed_level_1):
    """The Level-1 Mixed list as a set of PARENT names, so a group-suffixed Mixed division
    resolves against a parent-named tick-box (the TD only ever names parents)."""
    return {_GROUP_SUFFIX.sub("", str(n)) for n in (mixed_level_1 or ())}


def display_key(name, mixed_level_1=()):
    """Rule 44's sort key: `(block, age, parent, group_no)`.

    `mixed_level_1` is the resolved list of division names the TD sanctioned at Level 1 — from
    his setup tick-box, or derived from which draws file the division was printed in. An empty
    list is a legal answer and puts every Mixed division in the L2 block; a year with no
    Level-1 Mixed is a real year.

    `parent` is the third term so sibling groups of one division stay together and are then
    ordered by `group_no`; on the 2026 field no two distinct divisions share a (block, age).
    """
    gender, etype, age, group_no, parent = parse_division(name)
    if gender == "mixed":
        block = _MIXED_L1_RANK if parent in _l1_parents(mixed_level_1) else _MIXED_L2_RANK
    else:
        block = _GROUP_RANK[(gender, etype)]
    return block, age, parent, group_no


def sort_divisions(names, mixed_level_1=()):
    """`names` in rule 44's display order. Stable, deterministic, and total — any name sorts,
    including one outside 2026's 50 and one outside the 80."""
    l1 = _l1_parents(mixed_level_1)
    return sorted(names, key=lambda n: display_key(n, l1))


def sorted_by(names, key, mixed_level_1=()):
    """`names` in display order when each entry is a record rather than a bare string: `key`
    maps an entry to its division name. The one helper the surfaces that sort objects need,
    so none of them re-implements the lambda."""
    l1 = _l1_parents(mixed_level_1)
    return sorted(names, key=lambda n: display_key(key(n), l1))
