"""Core logic for the RAC DA40 Checkride Trainer.

Responsibilities:
- Load and validate the JSON data files (question bank and procedures).
- Quiz engine helpers: filtering, shuffling (with index mapping so grading
  stays correct after shuffling) and grading for all four question types.
- Persistent progress storage (per-question and per-procedure), with an
  injectable path so tests can use a temporary directory.

Standard library only.  No tkinter is imported here.
"""

from __future__ import annotations

import json
import os
import random
import re
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APP_TITLE = "RAC DA40 Checkride Trainer"
DEFAULT_DISCLAIMER = (
    "Training aid only; AFM/POH and current controlled RAC SOP take precedence."
)

QUESTION_TYPES = ("mcq", "numeric", "sequence", "self_check")
PROCEDURE_KINDS = ("procedure", "checklist", "memory", "emergency")

CATEGORIES = [
    "Numbers & Limits",
    "Procedures",
    "Emergencies",
    "Circuit & Landing",
    "Stall & Spin",
]

EXERCISES = [
    "6 Straight and Level",
    "7 Climbing",
    "8 Descending",
    "9 Turning",
    "10A Slow Flight",
    "10B Stalling",
    "11 Spin Avoidance",
    "12 Take-off and Climb",
    "13 Circuit, Approach and Landing",
    "12/13E Circuit Emergencies",
    "15 Advanced Turning",
    "16 Forced Landing",
    "17 Precautionary Landing",
]

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = PACKAGE_DIR / "data"
QUESTION_BANK_PATH = DEFAULT_DATA_DIR / "question_bank.json"
PROCEDURES_PATH = DEFAULT_DATA_DIR / "procedures.json"

ENV_HOME = "RAC_TRAINER_HOME"
PROGRESS_DIRNAME = ".rac_checkride_trainer"
PROGRESS_FILENAME = "progress.json"


# ---------------------------------------------------------------------------
# JSON loading and validation
# ---------------------------------------------------------------------------

def _read_json(path):
    """Return (data, error).  Never raises; error is a string or None."""
    path = Path(path)
    if not path.is_file():
        return None, "file not found: %s" % path
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh), None
    except (OSError, ValueError) as exc:  # ValueError covers JSONDecodeError
        return None, "could not parse %s: %s" % (path, exc)


def mcq_answer_index(question):
    """Return the zero-based correct choice index for an MCQ.

    Accepts an int index (canonical) or a letter ("A"/"b" -> 0/1) mapped
    deterministically.  Returns None if the answer is unusable.
    """
    answer = question.get("answer")
    if isinstance(answer, bool):  # bool is an int subclass; reject it
        return None
    if isinstance(answer, int):
        return answer
    if isinstance(answer, str):
        text = answer.strip()
        if len(text) == 1 and text.isalpha():
            return ord(text.upper()) - ord("A")
        try:
            return int(text)
        except ValueError:
            return None
    return None


def validate_question(question, index=0):
    """Return a list of schema problems for one question (empty == valid)."""
    errors = []
    label = None
    if isinstance(question, dict):
        label = question.get("id")
    label = label or "question #%d" % index

    if not isinstance(question, dict):
        return ["%s: not a JSON object" % label]

    qid = question.get("id")
    if not isinstance(qid, str) or not qid.strip():
        errors.append("%s: missing or invalid 'id'" % label)
    if not isinstance(question.get("prompt"), str) or not question["prompt"].strip():
        errors.append("%s: missing 'prompt'" % label)
    if not isinstance(question.get("category"), str) or not question["category"].strip():
        errors.append("%s: missing 'category'" % label)

    qtype = question.get("type")
    if qtype not in QUESTION_TYPES:
        errors.append("%s: invalid 'type' %r" % (label, qtype))
        return errors  # further checks are type-specific

    if qtype == "mcq":
        choices = question.get("choices")
        if not isinstance(choices, list) or not 3 <= len(choices) <= 5:
            errors.append("%s: mcq requires 3-5 'choices'" % label)
        elif not all(isinstance(c, str) and c.strip() for c in choices):
            errors.append("%s: mcq choices must be non-empty strings" % label)
        else:
            idx = mcq_answer_index(question)
            if idx is None or not 0 <= idx < len(choices):
                errors.append("%s: mcq 'answer' %r out of range" % (label, question.get("answer")))
    elif qtype == "numeric":
        parts = question.get("parts")
        if not isinstance(parts, list) or not parts:
            errors.append("%s: numeric requires non-empty 'parts'" % label)
        else:
            for i, part in enumerate(parts):
                plabel = "%s part %d" % (label, i + 1)
                if not isinstance(part, dict):
                    errors.append("%s: not a JSON object" % plabel)
                    continue
                answer = part.get("answer")
                if isinstance(answer, bool) or not isinstance(answer, (int, float)):
                    errors.append("%s: 'answer' must be numeric" % plabel)
                tol = part.get("tolerance", 0)
                if isinstance(tol, bool) or not isinstance(tol, (int, float)) or tol < 0:
                    errors.append("%s: 'tolerance' must be a number >= 0" % plabel)
    elif qtype == "sequence":
        steps = question.get("steps")
        if not isinstance(steps, list) or len(steps) < 2:
            errors.append("%s: sequence requires at least 2 'steps'" % label)
        elif not all(isinstance(s, str) and s.strip() for s in steps):
            errors.append("%s: sequence steps must be non-empty strings" % label)
    elif qtype == "self_check":
        if not isinstance(question.get("model_answer"), str) or not question["model_answer"].strip():
            errors.append("%s: self_check requires a 'model_answer'" % label)

    return errors


def validate_procedure(procedure, index=0):
    """Return a list of schema problems for one procedure (empty == valid)."""
    if not isinstance(procedure, dict):
        return ["procedure #%d: not a JSON object" % index]
    errors = []
    label = procedure.get("id") or "procedure #%d" % index
    if not isinstance(procedure.get("id"), str) or not procedure["id"].strip():
        errors.append("%s: missing or invalid 'id'" % label)
    if not isinstance(procedure.get("title"), str) or not procedure["title"].strip():
        errors.append("%s: missing 'title'" % label)
    if not isinstance(procedure.get("exercise"), str) or not procedure["exercise"].strip():
        errors.append("%s: missing 'exercise'" % label)
    kind = procedure.get("kind")
    if kind is not None and kind not in PROCEDURE_KINDS:
        errors.append("%s: invalid 'kind' %r" % (label, kind))
    steps = procedure.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("%s: requires non-empty 'steps'" % label)
    elif not all(isinstance(s, str) and s.strip() for s in steps):
        errors.append("%s: steps must be non-empty strings" % label)
    return errors


@dataclass
class QuestionBank:
    """Loaded question bank plus metadata and any load/validation errors."""

    questions: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    path: Path = QUESTION_BANK_PATH

    @property
    def disclaimer(self):
        return self.metadata.get("disclaimer") or DEFAULT_DISCLAIMER

    @property
    def title(self):
        return self.metadata.get("title") or APP_TITLE

    def categories(self):
        seen = {q.get("category") for q in self.questions if q.get("category")}
        ordered = [c for c in CATEGORIES if c in seen]
        ordered += sorted(seen - set(ordered))
        return ordered

    def exercises(self):
        seen = {q.get("exercise") for q in self.questions if q.get("exercise")}
        ordered = [e for e in EXERCISES if e in seen]
        ordered += sorted(seen - set(ordered))
        return ordered


def load_question_bank(path=None):
    """Load and validate question_bank.json.

    Never raises: a missing or corrupt file yields an empty bank with the
    problem recorded in ``errors``.
    """
    path = Path(path) if path else QUESTION_BANK_PATH
    metadata = {
        "title": APP_TITLE,
        "source_documents": [],
        "disclaimer": DEFAULT_DISCLAIMER,
    }
    errors = []
    questions = []

    data, err = _read_json(path)
    if err:
        errors.append(err)
    elif not isinstance(data, dict) or not isinstance(data.get("questions"), list):
        errors.append("%s: top-level object with a 'questions' list is required" % path)
    else:
        raw_meta = data.get("metadata")
        if isinstance(raw_meta, dict):
            for key in ("title", "disclaimer"):
                if isinstance(raw_meta.get(key), str) and raw_meta[key].strip():
                    metadata[key] = raw_meta[key]
            docs = raw_meta.get("source_documents")
            if isinstance(docs, list):
                metadata["source_documents"] = [str(d) for d in docs]
        seen_ids = set()
        for i, question in enumerate(data["questions"]):
            qerrs = validate_question(question, i)
            qid = question.get("id") if isinstance(question, dict) else None
            if isinstance(qid, str) and qid:
                if qid in seen_ids:
                    qerrs.append("%s: duplicate question id" % qid)
                seen_ids.add(qid)
            if qerrs:
                errors.extend(qerrs)
            else:
                questions.append(question)

    return QuestionBank(questions=questions, metadata=metadata, errors=errors, path=path)


def load_procedures(path=None):
    """Load and validate procedures.json -> (procedures, errors).

    Never raises on a missing or corrupt file.
    """
    path = Path(path) if path else PROCEDURES_PATH
    errors = []
    procedures = []

    data, err = _read_json(path)
    if err:
        errors.append(err)
    elif not isinstance(data, dict) or not isinstance(data.get("procedures"), list):
        errors.append("%s: top-level object with a 'procedures' list is required" % path)
    else:
        seen_ids = set()
        for i, proc in enumerate(data["procedures"]):
            perrs = validate_procedure(proc, i)
            pid = proc.get("id") if isinstance(proc, dict) else None
            if isinstance(pid, str) and pid:
                if pid in seen_ids:
                    perrs.append("%s: duplicate procedure id" % pid)
                seen_ids.add(pid)
            if perrs:
                errors.extend(perrs)
            else:
                procedures.append(proc)

    return procedures, errors


def procedures_by_exercise(procedures):
    """Group procedures by exercise, exercises in canonical order first."""
    groups = {}
    for proc in procedures:
        groups.setdefault(proc.get("exercise", "(no exercise)"), []).append(proc)
    ordered = [(e, groups[e]) for e in EXERCISES if e in groups]
    ordered += [(e, groups[e]) for e in sorted(groups) if e not in set(EXERCISES)]
    return ordered


# ---------------------------------------------------------------------------
# Quiz engine: filtering, shuffling, grading
# ---------------------------------------------------------------------------

def filter_questions(questions, category=None, exercise=None, qtype=None, ids=None):
    """Return questions matching all given filters (None means no filter)."""
    id_set = set(ids) if ids is not None else None
    result = []
    for q in questions:
        if category and q.get("category") != category:
            continue
        if exercise and q.get("exercise") != exercise:
            continue
        if qtype and q.get("type") != qtype:
            continue
        if id_set is not None and q.get("id") not in id_set:
            continue
        result.append(q)
    return result


def shuffle_mcq_choices(question, rng=None):
    """Shuffle MCQ choices.

    Returns (displayed, correct_pos) where ``displayed`` is a list of
    ``(original_index, choice_text)`` tuples in display order and
    ``correct_pos`` is the position within ``displayed`` of the correct
    answer (None if the answer index is unusable).
    """
    rng = rng or random
    choices = list(question.get("choices") or [])
    order = list(range(len(choices)))
    rng.shuffle(order)
    displayed = [(orig, choices[orig]) for orig in order]
    correct = mcq_answer_index(question)
    correct_pos = None
    if correct is not None:
        for pos, (orig, _text) in enumerate(displayed):
            if orig == correct:
                correct_pos = pos
                break
    return displayed, correct_pos


def shuffle_sequence_steps(question, rng=None):
    """Shuffle sequence steps.

    Returns a list of ``(letter, original_index, step_text)`` tuples in
    display order; the letter is the label shown to the user (A, B, C, ...).
    """
    rng = rng or random
    steps = list(question.get("steps") or [])
    order = list(range(len(steps)))
    rng.shuffle(order)
    return [(chr(ord("A") + pos), orig, steps[orig]) for pos, orig in enumerate(order)]


def grade_mcq(question, original_index):
    """Grade an MCQ answer given as an index into the *original* choices."""
    correct = mcq_answer_index(question)
    return correct is not None and original_index == correct


def grade_numeric_value(part, user_input):
    """Grade one numeric part: abs(user - answer) <= tolerance.

    Blank or non-numeric input is incorrect.
    """
    if user_input is None:
        return False
    text = str(user_input).strip()
    if not text:
        return False
    try:
        value = float(text)
    except ValueError:
        return False
    try:
        answer = float(part.get("answer"))
        tolerance = float(part.get("tolerance", 0) or 0)
    except (TypeError, ValueError):
        return False
    return abs(value - answer) <= tolerance


def grade_numeric(question, user_inputs):
    """Grade a (possibly multi-part) numeric question; all parts must pass."""
    parts = question.get("parts") or []
    if user_inputs is None or len(user_inputs) != len(parts):
        return False
    return all(grade_numeric_value(part, raw) for part, raw in zip(parts, user_inputs))


def grade_sequence(question, original_order):
    """Grade a sequence answer given as original step indices in user order."""
    steps = question.get("steps") or []
    if original_order is None:
        return False
    return list(original_order) == list(range(len(steps)))


def parse_sequence_letters(text, displayed):
    """Convert a letter answer like 'BADC' into original step indices.

    ``displayed`` comes from :func:`shuffle_sequence_steps`.  Returns None
    if the letters do not form a permutation of the displayed steps.
    """
    if text is None:
        return None
    letters = re.sub(r"[^A-Za-z]", "", text).upper()
    if len(letters) != len(displayed):
        return None
    by_letter = {letter: orig for letter, orig, _step in displayed}
    order = []
    for ch in letters:
        if ch not in by_letter:
            return None
        order.append(by_letter[ch])
    if len(set(order)) != len(order):
        return None
    return order


def grade_self_check(_question, recalled):
    """Self-check items are graded by the user's own marking."""
    return bool(recalled)


def correct_answer_text(question):
    """Human-readable correct answer for feedback screens."""
    qtype = question.get("type")
    if qtype == "mcq":
        idx = mcq_answer_index(question)
        choices = question.get("choices") or []
        if idx is not None and 0 <= idx < len(choices):
            return choices[idx]
        return "(answer unavailable)"
    if qtype == "numeric":
        bits = []
        for part in question.get("parts") or []:
            label = part.get("label") or "Value"
            unit = (" " + part["unit"]) if part.get("unit") else ""
            bits.append("%s: %s%s" % (label, part.get("answer"), unit))
        return "; ".join(bits)
    if qtype == "sequence":
        steps = question.get("steps") or []
        return " -> ".join("%d. %s" % (i + 1, s) for i, s in enumerate(steps))
    if qtype == "self_check":
        return question.get("model_answer", "")
    return ""


@dataclass
class QuestionResult:
    question_id: str
    category: str
    prompt: str
    correct: bool
    needs_review: bool = False


class QuizSession:
    """A shuffled run of questions plus collected results."""

    def __init__(self, questions, rng=None):
        self.rng = rng or random.Random()
        self.questions = list(questions)
        self.rng.shuffle(self.questions)
        self.results = []

    def limit(self, count):
        """Trim the session to at most ``count`` questions."""
        if count is not None and count >= 0:
            self.questions = self.questions[:count]
        return self

    def record(self, question, correct, needs_review=False):
        self.results.append(
            QuestionResult(
                question_id=question.get("id", "?"),
                category=question.get("category", "(uncategorised)"),
                prompt=question.get("prompt", ""),
                correct=bool(correct),
                needs_review=bool(needs_review),
            )
        )

    @property
    def total(self):
        return len(self.results)

    @property
    def score(self):
        return sum(1 for r in self.results if r.correct)

    def per_category(self):
        """Return {category: [correct, total]} preserving first-seen order."""
        agg = {}
        for r in self.results:
            slot = agg.setdefault(r.category, [0, 0])
            slot[1] += 1
            if r.correct:
                slot[0] += 1
        return agg

    def missed(self):
        """Results that were incorrect or flagged for review."""
        return [r for r in self.results if not r.correct or r.needs_review]


# ---------------------------------------------------------------------------
# Progress persistence
# ---------------------------------------------------------------------------

class ProgressStore:
    """Persistent per-question and per-procedure progress.

    The storage path is injectable: pass ``path`` explicitly, or set the
    RAC_TRAINER_HOME environment variable; otherwise the SPEC default
    ``~/.rac_checkride_trainer/progress.json`` is used.
    """

    VERSION = 1

    def __init__(self, path=None):
        if path is None:
            env_home = os.environ.get(ENV_HOME)
            base = Path(env_home).expanduser() if env_home else Path.home() / PROGRESS_DIRNAME
            path = base / PROGRESS_FILENAME
        self.path = Path(path)
        self._data = self._empty()
        self.load()

    @classmethod
    def _empty(cls):
        return {"version": cls.VERSION, "questions": {}, "procedures": {}}

    # -- file handling -----------------------------------------------------

    def load(self):
        """(Re)load from disk; a missing/corrupt file starts fresh."""
        if self.path.is_file():
            try:
                with self.path.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except (OSError, ValueError):
                data = None
            if isinstance(data, dict):
                merged = self._empty()
                for key in merged:
                    if key in data:
                        merged[key] = data[key]
                if not isinstance(merged["questions"], dict):
                    merged["questions"] = {}
                if not isinstance(merged["procedures"], dict):
                    merged["procedures"] = {}
                self._data = merged
        return self._data

    def save(self):
        """Persist atomically (write temp file, then rename)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_name(self.path.name + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2, sort_keys=True)
        os.replace(tmp_path, self.path)

    # -- questions ----------------------------------------------------------

    def record_question(self, question_id, correct, needs_review=False):
        """Record one attempt.  A correct, unflagged answer clears the
        needs-review flag ("queue until answered correctly")."""
        entry = self._data["questions"].setdefault(
            question_id,
            {"attempts": 0, "correct": 0, "last_result": None, "needs_review": False},
        )
        entry["attempts"] = int(entry.get("attempts", 0)) + 1
        if correct:
            entry["correct"] = int(entry.get("correct", 0)) + 1
            entry["needs_review"] = bool(needs_review)
        else:
            entry["needs_review"] = bool(entry.get("needs_review")) or bool(needs_review)
        entry["last_result"] = "correct" if correct else "incorrect"
        self.save()

    def question_stats(self, question_id):
        return dict(self._data["questions"].get(question_id, {}))

    def review_ids(self):
        """Question IDs queued for review: last attempt wrong, or flagged."""
        return sorted(
            qid
            for qid, entry in self._data["questions"].items()
            if entry.get("last_result") == "incorrect" or entry.get("needs_review")
        )

    # -- procedures ----------------------------------------------------------

    def record_procedure(self, procedure_id, recalled):
        """Record a procedure completion with self-rating."""
        entry = self._data["procedures"].setdefault(
            procedure_id, {"completions": 0, "self_rating": None}
        )
        entry["completions"] = int(entry.get("completions", 0)) + 1
        entry["self_rating"] = "recalled" if recalled else "needs_review"
        self.save()

    def procedure_stats(self, procedure_id):
        return dict(self._data["procedures"].get(procedure_id, {}))

    # -- summary / reset -----------------------------------------------------

    def summary(self):
        entries = list(self._data["questions"].values())
        attempts = sum(int(e.get("attempts", 0)) for e in entries)
        correct = sum(int(e.get("correct", 0)) for e in entries)
        procs = list(self._data["procedures"].values())
        return {
            "questions_seen": len(entries),
            "attempts": attempts,
            "correct": correct,
            "accuracy": (correct / attempts) if attempts else None,
            "review_queue": len(self.review_ids()),
            "procedures_touched": sum(1 for e in procs if int(e.get("completions", 0)) > 0),
            "procedures_recalled": sum(
                1 for e in procs if e.get("self_rating") == "recalled"
            ),
        }

    def reset(self, confirm=False):
        """Erase all progress.  Requires confirm=True (confirmation gate)."""
        if not confirm:
            return False
        self._data = self._empty()
        self.save()
        return True
