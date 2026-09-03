# Plan — RAC DA40 Checkride Trainer (Python quiz app)

## Goal
Build a self-contained, stdlib-only Python app per the user's `SPEC.md`:
tkinter GUI + `--cli` fallback, quiz engine (MCQ / numeric / sequence / self-check),
procedure trainer, persistent progress, unittest suite. Question content is derived
**exclusively** from the uploaded `RAC_QRC_v1.1.pdf` (no external aviation data).

## Constraints (from user + SPEC)
- Python 3.10+, standard library only, no network, no build step.
- Keep it simple, but the question bank must cover ALL QRC exercises:
  6, 7, 8, 9, 10A, 10B, 11, 12, 13, 12/13E, 15, 16, 17.
- Data under `data/` as JSON; progress at `~/.rac_checkride_trainer/progress.json`.
- SPEC references a "Comprehensive Knowledge Test" that was NOT uploaded —
  substitute with equivalent QRC-derived questions (flag this to the user).

## Source material
- `/mnt/agents/output/rac_checkride_trainer/qrc_reference.txt` — clean text extraction of the QRC (pypdf).
- `/mnt/agents/upload/SPEC.md` — the app specification.

## Stages

### Stage 1 — Content creation (parallel, independent)
Three data agents, each given the QRC reference text path + the SPEC schema sections:
- **Data Agent A**: `data/question_bank.json` part 1 — Exercises 6, 7, 8, 9, 10A
  (MCQ + numeric + sequence questions, with explanations and source refs).
- **Data Agent B**: question bank part 2 — Exercises 10B, 11, 12/13E (stalling, spin
  avoidance, circuit emergencies) incl. self-check items.
- **Data Agent C**: question bank part 3 — Exercises 12, 13, 15, 16, 17
  PLUS `data/procedures.json` (walkthroughs for ALL exercises 6–17).
Each writes a partial JSON file; orchestrator merges into `question_bank.json`.

### Stage 2 — App code (parallel with Stage 1; depends only on SPEC schema, not data)
- **Coder Agent**: `core.py`, `app.py` (GUI + CLI), `tests/test_core.py`, `README.md`,
  copy of `SPEC.md`, per SPEC sections 3–11.

### Stage 3 — Integration & verification
- Merge question parts, validate schema + ID uniqueness.
- **Verifier Agent**: run `python -m unittest discover -s tests -v`, CLI smoke test
  (piped input), GUI import check, coverage check that every exercise 6–17 has
  questions and a procedure entry. Fix-forward until green.

### Stage 4 — Deliver
- Final summary + how to run. Deliverable: `/mnt/agents/output/rac_checkride_trainer/`
  (zip for download).
