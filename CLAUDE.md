# TDA v3.1 — RUN surface

**Every session in this repository is a RUN / simulation session of the TDA guided run,
governed end-to-end by `WWTC_test_run_starter.md` in this repository.** That file is the sole
authority for the run: one elicited step at a time, never batch, never auto-advance, and every
scripted move is mandatory — a skipped move is a run defect, not a style choice.

## The surface rules

- **State the runbook's version in your first turn, read off the file's own first line.** This
  file deliberately names no version — a number written here goes stale silently. If the
  Operator says the version is not current, stop before Step 0.
- **This repository is a verified bundle extract**, cut from the build repository by its bundle
  tool and proven from the extract at cut time — `START_HERE.md` names the commit it was cut
  from. It is refreshed only by re-cutting there and replacing the files here, never by hand
  edits. If an import fails, a file the runbook names is missing, or the materials check fails:
  **stop and report — never improvise a substitute, and never patch an engine module mid-run.**
- Run the engine with code execution; write everything the run produces to `outputs/`
  (gitignored). **Do not edit any bundle file. Do not commit or push anything unless the
  Operator explicitly asks to save a run record.** The build repository is out of scope from
  here entirely — the runbook is complete for a run, and build-governance documents are absent
  on purpose.
- **Engine and consoles are decoupled on purpose:** the human couriers every JSON block between
  them. Never bypass a courier stop, and never move a block the human did not paste. Consoles
  reach the Operator as published artifact links (or saved HTML files they open); the engine
  never reads a console's document except when the Operator pastes it.
- **The run's shape is the runbook's opening fork.** A September (plan & announce) run **ends
  at the announced calendar** — the edit console and schedule edits are never reached. Only a
  full schedule-build run continues past that point. Do not drive beyond the fork's own
  stopping point.
- **A refused week is a designed outcome, not an error:** follow the runbook's refusal branch
  to the letter — the report printed verbatim, the unchecked map handed over, the fixes put as
  the Operator's decision, never chosen for them. Any re-test that ends in a refusal prints the
  fresh report verbatim; summarize on top of it, never instead of it.
- `LANG-1_glossary.md` (in this repository) is the authority on the word for each concept a
  director reads or hears.
- When the run completes or stops, produce the run report in the format the Operator pastes.

## Starting a run

The run begins when the Operator pastes the opening prompt — `START_HERE.md` carries it, along
with the inventory of what this extract contains. Dependencies are `requirements.txt`
(`openpyxl` and `pypdfium2` are required; the two PDF-export packages are optional — the HTML
paths work without them).
