# SPEC — RAC Checkride Trainer

## 1. Purpose
A self-contained local Python desktop app for practicing the RAC DA40-TDI QRC/SOP checkride material uploaded by the user.

The app is a study aid only. It must clearly state that the AFM/POH and current controlled RAC SOP take precedence.

## 2. User experience
Target user: a student pilot preparing for an RAC checkride. The app must run locally without a server or third-party Python packages.

Primary workflows:
1. **Practice Exam**: randomized questions from all categories, with a selectable question count.
2. **Category Drill**: filter by category (Numbers & Limits, Procedures, Emergencies, Circuit & Landing, etc.) and/or question type.
3. **Numeric Drill**: numeric fill-in questions, including multi-part answers.
4. **Procedure Trainer**: exercise procedures grouped by training exercise; step-through, reveal model answer, and self-mark completion.
5. **Review Missed**: automatically queue missed/unsure questions until answered correctly.
6. **Progress**: show session score and persistent lifetime stats.

## 3. Technical stack and constraints
- Python 3.10+.
- Standard library only.
- GUI: `tkinter`/`ttk`.
- CLI fallback: `python app.py --cli` for environments without Tkinter.
- Data: JSON files under `data/`.
- Persistence: local JSON progress file at `~/.rac_checkride_trainer/progress.json`.
- No network calls.
- No build step required.

## 4. File structure
```text
rac_checkride_trainer/
├── app.py                  # GUI entry point and CLI fallback
├── core.py                 # data loading, grading, quiz engine, progress persistence
├── data/
│   ├── question_bank.json  # MCQ, numeric, sequence, and scenario/self-check items
│   └── procedures.json     # exercise walkthroughs/checklists
├── tests/
│   └── test_core.py        # standard-library unittest coverage
├── README.md               # run instructions and study workflow
└── SPEC.md                 # this specification
```

## 5. Data schemas

### 5.1 Question bank
`question_bank.json` must be an object:
```json
{
  "metadata": {
    "title": "RAC DA40 Checkride Trainer",
    "source_documents": ["RAC QRC v1.1", "RAC SOP v1.1", "RAC QRC Comprehensive Knowledge Test"],
    "disclaimer": "Training aid only; AFM/POH and current controlled RAC SOP take precedence."
  },
  "questions": []
}
```

Each question object:
```json
{
  "id": "NUM-001",
  "category": "Numbers & Limits",
  "exercise": "6 Straight and Level",
  "type": "numeric|mcq|sequence|self_check",
  "prompt": "Straight-and-level cruise speed and power",
  "parts": [
    {"label": "Speed", "answer": 110, "tolerance": 0, "unit": "KIAS"},
    {"label": "Power", "answer": 65, "tolerance": 0, "unit": "%"}
  ],
  "choices": ["..."],
  "answer": "B",
  "steps": ["..."],
  "model_answer": "...",
  "explanation": "...",
  "source": "RAC QRC v1.1, Exercise 6",
  "tags": ["speed", "power"]
}
```

Type-specific requirements:
- `numeric`: non-empty `parts`; each part has numeric `answer` and `tolerance`.
- `mcq`: 3–5 `choices`; `answer` is the correct zero-based index or a letter mapped deterministically.
- `sequence`: ordered `steps`; user arranges shuffled steps.
- `self_check`: model answer and key elements; user compares and marks correct/needs review.

### 5.2 Procedures
`procedures.json` must be an object:
```json
{
  "procedures": [
    {
      "id": "PROC-06-SL",
      "exercise": "6 Straight and Level",
      "title": "Straight-and-level flight",
      "kind": "procedure|checklist|memory|emergency",
      "briefing": "When/why to use it",
      "steps": ["..."],
      "callouts": ["..."],
      "completion_standards": ["..."],
      "source": "RAC QRC v1.1"
    }
  ]
}
```

## 6. Seed content requirements
Seed at least:
- All numeric limits from the provided comprehensive test Section 1, split into individual or multi-part questions.
- All 10 MCQs from Section 3 (questions 28–37) with explanations.
- All 5 sequence questions from Section 2.
- Scenario/critical-memory questions from Sections 4–5 as self-check items with model answers.
- Procedure entries for QRC exercises 6, 7, 8, 9, 10A, 10B, 11, 12, 13, 12/13E, 15, 16, and 17, using the uploaded QRC/SOP as source.

## 7. Functional requirements

### 7.1 Quiz engine
- Shuffle question order and MCQ choices.
- Support filtering by category, exercise, and type.
- Grade:
  - MCQ by selected choice.
  - Numeric by `abs(user - answer) <= tolerance`; blank/non-numeric is incorrect.
  - Sequence by exact order.
  - Self-check by user marking.
- Show immediate correct/incorrect feedback, correct answer, explanation, and source.
- Allow marking a question “Needs review” even if correct.
- End screen: score, per-category score, and missed-question list.

### 7.2 Procedure trainer
- Category/exercise selector.
- Step-at-a-time mode with hide/reveal.
- Full checklist mode with checkboxes.
- “I could recall it” / “Needs review” controls.
- Completion persisted per procedure.

### 7.3 Progress
- Store attempts, correct count, last result, and needs-review flags by question ID.
- Store procedure completion/self-rating by procedure ID.
- Provide a Reset Progress action with confirmation.

## 8. GUI requirements
- Main window title: `RAC DA40 Checkride Trainer`.
- Startup dashboard with buttons for Practice Exam, Category Drill, Numeric Drill, Procedure Trainer, Review Missed, Progress, and Exit.
- Use readable fonts, keyboard-friendly controls, and a clear disclaimer.
- Handle invalid/empty question sets gracefully.
- Window should be usable at 1000×700.

## 9. CLI requirements
`python app.py --cli` must provide:
- Question count selection.
- MCQ, numeric, sequence, and self-check interaction.
- Final score and missed list.
No GUI dependency when `--cli` is used.

## 10. Testing
Use `unittest` and validate:
- JSON loads and schema invariants hold.
- Every question ID/procedure ID is unique.
- Numeric grading honors tolerance.
- MCQ grading works after shuffling.
- Sequence grading works.
- Progress round-trip works in a temporary directory.
- Seeded content meets minimum counts.

## 11. Acceptance criteria
- `python -m unittest discover -s tests -v` passes.
- `python app.py --cli` starts and can complete a short noninteractive smoke path when input is piped.
- GUI code imports without syntax errors.
- App runs from the project root with no third-party dependencies.
- README explains setup, use, data editing, and safety disclaimer.
