"""PUB-1 — the publish stamp: who wrote the announced calendar, and when.

Brief `PUB1_publish_stamp_brief.md` (Operator-approved 2026-08-23). Closes FG-2 and FG-9's
September half. Harness: `tests/pub1_publish_stamp.py`.

WHAT THIS IS FOR. In September the TD approves a finals calendar and tells his players about
it. Until this module the document he approved was indistinguishable from any other copy of
it — four months later nothing could say which file was the one the players were told about.
This writes that fact onto the document: the date it was announced, the name it was announced
under, and a digest over the solved map.

WHY IT LIVES HERE AND NOT IN `finals_plan.py` (decision 1, Operator 2026-08-23, option 2).
`td-finals-map/v1` has two emitters and one validator, and the console's emit AND the validator
are both inside the D-3 frozen file with all four narrow waivers spent. Three candidate writers
were measured for this build and all three work; none needs a fifth waiver. The stamp is
written on the PYTHON side, after the courier hands the document back, because that touches no
frozen file at all and adds no coupling to one — and because publishing happens after the
director has approved the days, not at the moment a screen was generated.

  · NOT `finals_plan.py` — frozen (D-3).
  · NOT `finals_guidance.py` — its stated contract is that with `engine_check` absent the layer
    does not run AT ALL, and `tests/fmap2_proposal.py` part D asserts byte-identity against the
    frozen renderer. Nothing here may weaken that.

DETERMINISM IS A HARD INVARIANT (`CLAUDE.md`). `published_on` is an ARGUMENT and this module
reads no clock. A stamp whose date depends on whose laptop pressed the button is not a record.

⚠ THE DIGEST IS AN INTEGRITY CHECK, NEVER A SIGNATURE (decision 3's binding condition). It
catches a file that drifted — an old copy, a hand edit, the wrong one of two saves. It is never
proof of who produced it: whoever can edit the map can recompute the digest. It is also blind to
an edit of the stamp's own date and to a rewrite of `pins`. Those blind spots are asserted AS
blind spots in part F so that no later build, and no sentence said to a director, can quietly
read this as proof of authenticity.

⚠ THE STAMP IS DISCARDED AT THE GATE, AND THAT IS THE WHOLE COMPATIBILITY GUARANTEE.
`finals_plan.finals_map_from_doc` ends `return dict(fmap)` — it returns the finals map and
nothing else. So no module downstream of the validator can see this key, and none can change
behaviour because of it. The same fact is a constraint the January family must inherit: a
reader of the stamp (GATE-1, RECON-1, BADGE-1) must read the couriered DOCUMENT, never the
validator's return value. Documented at `mvp_era1_contracts.md` §14 for exactly that reason.
"""
import hashlib
import json

import finals_plan as FP

KEY = "announced"


def map_digest(finals_map):
    """A digest over the SOLVED MAP ALONE, canonicalised.

    `pins` are deliberately outside it: pins are provenance, and a re-keyed pin does not change
    what the players were told. `sort_keys=True` so key order cannot move it, and compact
    separators so whitespace cannot either — a document that was pretty-printed on its way to
    the shelf and back must still check out.
    """
    if not isinstance(finals_map, dict) or not finals_map:
        raise ValueError(f"{FP.FINALS_MAP_SCHEMA}: finals_map is missing or empty")
    blob = json.dumps(finals_map, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def stamp_finals_map(doc, published_on, label=None, digest=True, replace=False):
    """Return a NEW `td-finals-map/v1` carrying `announced`. The input is never mutated.

    `published_on` — the ISO date the calendar was announced, supplied by the run. No clock is
                     read here (determinism, `CLAUDE.md`).
    `label`        — the TD's own name for what was announced. Blank derives one from the
                     tournament name and the date (open item c): a blank label makes the stamp
                     half a record.
    `digest`       — include the integrity check over the solved map (decision 3, ruled on).
    `replace`      — re-stamp a document that already carries one. Announcing twice is a
                     decision, never a silent overwrite (open item d), so the default refuses
                     and names the date that would be overwritten.
    """
    if not isinstance(doc, dict) or doc.get("schema") != FP.FINALS_MAP_SCHEMA:
        got = doc.get("schema") if isinstance(doc, dict) else type(doc).__name__
        raise ValueError(f"expected a {FP.FINALS_MAP_SCHEMA} doc, got: {got}")
    fmap = doc.get("finals_map")
    if not isinstance(fmap, dict) or not fmap:
        raise ValueError(f"{FP.FINALS_MAP_SCHEMA}: finals_map is missing or empty")
    if not published_on or not isinstance(published_on, str):
        raise ValueError(f"{KEY}: published_on is required and is supplied by the run, never a "
                         f"machine clock — got: {published_on!r}")

    prior = doc.get(KEY)
    if prior is not None and not replace:
        was = prior.get("published_on") if isinstance(prior, dict) else prior
        raise ValueError(
            f"{FP.FINALS_MAP_SCHEMA} is already announced, dated {was}. Announcing it again "
            f"would overwrite that date with {published_on}. Pass replace=True to do it "
            f"deliberately.")

    if not label:
        tournament = (doc.get("tournament") or "").strip()
        label = f"{tournament} — announced {published_on}" if tournament \
            else f"announced {published_on}"

    announced = {"published_on": published_on, "label": label}
    if digest:
        announced["map_digest"] = map_digest(fmap)

    out = dict(doc)
    out[KEY] = announced
    return out


def announced_of(doc):
    """The stamp on a couriered DOCUMENT, or None.

    ⚠ For January's readers (GATE-1 / RECON-1 / BADGE-1). Read the DOCUMENT — the validator
    `finals_plan.finals_map_from_doc` returns `dict(fmap)` and drops this key at the gate, so a
    reader that reaches for the validator's output finds the stamp gone and will not know why.
    """
    if not isinstance(doc, dict):
        return None
    got = doc.get(KEY)
    return got if isinstance(got, dict) else None


def digest_matches(doc):
    """Does the stamp's digest still agree with the map beside it?

    ⚠ WHAT THIS ANSWERS, AND WHAT IT DOES NOT. True means the solved map has not drifted since
    it was stamped. It catches a file that drifted — an old copy, a hand edit, the wrong one of
    two saves. It is never proof of who produced it, because whoever can edit the map can
    recompute the digest, and it is blind to an edit of the stamp's own date and to `pins`.
    Returns None when the document carries no digest to check.
    """
    ann = announced_of(doc)
    if not ann or "map_digest" not in ann:
        return None
    return ann["map_digest"] == map_digest(doc.get("finals_map") or {})
