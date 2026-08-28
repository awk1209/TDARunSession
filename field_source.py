"""S-2 seam — the field the ingest boundary serves (Operator ruling, 2026-08-24, OPTION 1).

WHAT THIS IS. A September run has to price and announce a tournament that has not happened
yet, so the field it works from is projected rather than printed. This module is the ONE named
place that field is handed over. Nothing is installed by default: with nothing installed, every
consumer reads the printed draws and the real player lists exactly as it does today, byte for
byte.

WHY IT IS HERE AND NOT SOMEWHERE SHALLOWER. Measured by driving the code at this build's HEAD,
all four entry points on the September path reach the draws lane, and two of them go and read
it on their own account rather than through anything that receives the director's answers:

    court_budget     -> _cb_search -> probe -> at -> build_combined -> load_from_finalized_draws
    build_from_setup                              -> build_combined -> load_from_finalized_draws
    build_combined   -> _gate -> _master_assigned_days -> _level_draws -> parse_draws  (a 2nd read)
    finals_plan      -> parse_draws  DIRECTLY, bypassing build_combined

⚠ SO A SEAM AT `build_from_setup` WOULD NOT REACH THE COURT ANSWER, and one at `build_combined`
would not reach the finals map. `court_budget` takes no setup bundle at all. Handing the field
over at the boundary is the only site where one change reaches all four — and, just as
important, the only site where `build_combined`'s TWO independent reads of the draws cannot
diverge from each other.

WHY IT IS A MODULE OF ITS OWN. The two functions that must consult it —
`draws_pdf.parse_draws` and `wwtc_ingest.load_players` — sit on opposite sides of an existing
import edge (`wwtc_ingest` imports `draws_pdf`, never the reverse), and `projected_field`
imports both. A holder in any of the three makes a cycle or hides a player-list hook inside the
PDF parser. This module imports nothing of theirs, so all three can consult it freely.

WHAT IT REPLACED. `Field2027.__enter__` in the committed scaffolding monkey-patched FIVE call
sites at runtime: `draws_pdf.parse_draws`, `wwtc_pipeline.draws_pdf.parse_draws`,
`wwtc_ingest.load_from_finalized_draws`, `wwtc_pipeline._reconcile` and
`wwtc_ingest.non_drawn_entrants`. This seam replaces the first three and RETIRES the last two
outright — they existed only because the scaffolding's field had no player list to reconcile
against, so the two accounting surfaces had to be stubbed quiet. A matched pair reconciles for
real, so there is nothing left to silence.

⚠ INSTALL AROUND THE NARROWEST SPAN THAT NEEDS IT. This is process-global by design — that is
what lets one installation reach four entry points without threading an argument through the
engine — and global state that leaks is the failure mode. Use `projected_field.serving` wherever
the span fits in one block, because it restores the previous value even when the body raises.
A GUIDED RUN is the one case that cannot: Steps 2 through 3.6 are separate turns with the
Operator couriering between them, so no block can hold them, and `projected_field.install` is
what the runbook calls there. Either way, everything after the announcement is outside it — a
January run must never have a projected field installed.
"""

_INSTALLED = None


def installed():
    """The projected field currently being served, or None for today's behaviour."""
    return _INSTALLED


def install(field):
    """Serve `field` from the ingest boundary. Returns the previous value, for restoration.

    Prefer `projected_field.serving(field)` — it restores on the way out even if the body
    raises, which a bare install/uninstall pair does not.
    """
    global _INSTALLED
    if field is not None:
        for attr in ("draws_for", "players_for"):
            if not callable(getattr(field, attr, None)):
                raise TypeError(
                    f"a field served at the ingest boundary must provide {attr}(level); "
                    f"{type(field).__name__} does not")
    prior, _INSTALLED = _INSTALLED, field
    return prior


def uninstall(prior=None):
    """Stop serving, or restore whatever `install` returned."""
    global _INSTALLED
    _INSTALLED = prior
