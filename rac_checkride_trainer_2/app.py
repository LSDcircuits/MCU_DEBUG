#!/usr/bin/env python3
"""RAC DA40 Checkride Trainer - GUI entry point and CLI fallback.

Usage:
    python app.py          launch the tkinter GUI
    python app.py --cli    run the text-mode CLI (no tkinter required)

Standard library only.  tkinter is imported lazily inside run_gui() so this
module imports fine on systems without Tk.
"""

from __future__ import annotations

import argparse
import random
import sys

import core

# ===========================================================================
# CLI
# ===========================================================================

CLI_MENU = """\
==================  RAC DA40 Checkride Trainer (CLI)  ==================
Training aid only; AFM/POH and current controlled RAC SOP take precedence.

  1) Practice Exam      - randomized questions from all categories
  2) Category Drill     - filter by category / exercise / type
  3) Numeric Drill      - numbers & limits practice
  4) Procedure Trainer  - exercise walkthroughs and checklists
  5) Review Missed      - questions queued for review
  6) Progress           - lifetime stats and reset
  q) Quit
"""


class Cli:
    """Menu-driven command-line interface.  Safe with piped/EOF stdin."""

    def __init__(self, bank, procedures, proc_errors, progress):
        self.bank = bank
        self.procedures = procedures
        self.proc_errors = proc_errors
        self.progress = progress
        self.rng = random.Random()

    # -- input helpers ------------------------------------------------------

    @staticmethod
    def _ask(prompt=""):
        """input() that returns None on EOF instead of raising."""
        try:
            return input(prompt)
        except EOFError:
            print()
            return None

    def _pick_from_list(self, title, options, allow_all=False):
        """Show a numbered list; return the chosen option, 'ALL', or None."""
        print("\n" + title)
        for i, opt in enumerate(options, 1):
            print("  %d) %s" % (i, opt))
        if allow_all:
            print("  a) All")
        print("  q) Back")
        raw = self._ask("Select: ")
        if raw is None:
            return None
        text = raw.strip().lower()
        if text in ("q", "quit", "back"):
            return None
        if allow_all and text in ("a", "all"):
            return "ALL"
        if text.isdigit() and 1 <= int(text) <= len(options):
            return options[int(text) - 1]
        print("  Invalid selection.")
        return None

    def _ask_count(self, available):
        """Question count selection; returns an int, or None to go back."""
        raw = self._ask(
            "\nHow many questions? (1-%d, 'all', or 'q' to go back) [10]: "
            % available
        )
        if raw is None:
            return None
        text = raw.strip().lower()
        if text in ("q", "quit", "back"):
            return None
        if text in ("", "all", "a"):
            return available if text else min(10, available)
        if text.isdigit() and int(text) >= 1:
            return min(int(text), available)
        print("  Invalid count.")
        return None

    # -- top-level menu -----------------------------------------------------

    def main_menu(self):
        self._show_data_status()
        while True:
            print(CLI_MENU)
            choice = self._ask("Select: ")
            if choice is None:
                print("Goodbye.")
                return 0
            choice = choice.strip().lower()
            if choice in ("q", "quit", "exit"):
                print("Goodbye.")
                return 0
            elif choice == "1":
                self.practice_exam()
            elif choice == "2":
                self.category_drill()
            elif choice == "3":
                self.numeric_drill()
            elif choice == "4":
                self.procedure_trainer()
            elif choice == "5":
                self.review_missed()
            elif choice == "6":
                self.show_progress()
            else:
                print("  Unknown selection - please try again.")

    def _show_data_status(self):
        if self.bank.errors:
            print("Question bank status:")
            for err in self.bank.errors[:5]:
                print("  - %s" % err)
            if len(self.bank.errors) > 5:
                print("  - ... and %d more" % (len(self.bank.errors) - 5))
        if self.proc_errors:
            print("Procedures status:")
            for err in self.proc_errors[:5]:
                print("  - %s" % err)
        if not self.bank.questions and not self.procedures:
            print(
                "\nNo study data found yet.  Add data/question_bank.json and\n"
                "data/procedures.json (see README.md), then restart."
            )

    # -- quiz modes -----------------------------------------------------------

    def practice_exam(self):
        self._run_quiz(self.bank.questions, "Practice Exam")

    def category_drill(self):
        category = self._pick_from_list(
            "Category:", self.bank.categories(), allow_all=True
        )
        if category is None:
            return
        category = None if category == "ALL" else category

        pool = core.filter_questions(self.bank.questions, category=category)
        exercises = sorted({q.get("exercise") for q in pool if q.get("exercise")})
        exercise = None
        if exercises:
            pick = self._pick_from_list("Exercise:", exercises, allow_all=True)
            if pick is None:
                return
            exercise = None if pick == "ALL" else pick

        types = ["mcq", "numeric", "sequence", "self_check"]
        pick = self._pick_from_list("Question type:", types, allow_all=True)
        if pick is None:
            return
        qtype = None if pick == "ALL" else pick

        pool = core.filter_questions(
            self.bank.questions, category=category, exercise=exercise, qtype=qtype
        )
        self._run_quiz(pool, "Category Drill")

    def numeric_drill(self):
        pool = core.filter_questions(self.bank.questions, qtype="numeric")
        self._run_quiz(pool, "Numeric Drill")

    def review_missed(self):
        ids = self.progress.review_ids()
        pool = core.filter_questions(self.bank.questions, ids=ids)
        if not pool:
            print("\nReview queue is empty - nothing flagged or missed.")
            return
        self._run_quiz(pool, "Review Missed")

    # -- quiz engine front-end -----------------------------------------------

    def _run_quiz(self, questions, title):
        if not questions:
            print("\nNo questions available for this selection.")
            if self.bank.errors:
                print("(Check the data files: %s)" % "; ".join(self.bank.errors[:2]))
            return
        count = self._ask_count(len(questions))
        if count is None:
            return
        session = core.QuizSession(questions, rng=self.rng).limit(count)
        print("\n=== %s: %d question(s) ===" % (title, len(session.questions)))
        for number, question in enumerate(session.questions, 1):
            outcome = self._ask_question(question, number, len(session.questions))
            if outcome is None:
                print("\nQuiz ended early.")
                break
            correct, needs_review = outcome
            session.record(question, correct, needs_review)
            if question.get("id"):
                self.progress.record_question(question["id"], correct, needs_review)
        self._show_end_screen(session, title)

    def _ask_question(self, q, number, total):
        """Ask one question.  Returns (correct, needs_review) or None to quit."""
        print(
            "\n--- Question %d/%d  [%s]  %s | %s ---"
            % (
                number,
                total,
                q.get("id", "?"),
                q.get("category", "?"),
                q.get("exercise", "-"),
            )
        )
        print(q.get("prompt", "(no prompt)"))
        qtype = q.get("type")
        if qtype == "mcq":
            result = self._ask_mcq(q)
        elif qtype == "numeric":
            result = self._ask_numeric(q)
        elif qtype == "sequence":
            result = self._ask_sequence(q)
        elif qtype == "self_check":
            result = self._ask_self_check(q)
        else:
            print("(Unsupported question type %r - skipped.)" % (qtype,))
            return (False, True)
        if result is None:
            return None
        self._show_feedback(q, result)
        needs_review = self._ask_needs_review()
        if needs_review:
            print("  Flagged for review.")
        return (result, needs_review)

    def _ask_mcq(self, q):
        displayed, correct_pos = core.shuffle_mcq_choices(q, self.rng)
        for pos, (_orig, text) in enumerate(displayed, 1):
            print("  %d) %s" % (pos, text))
        while True:
            raw = self._ask("Your answer (1-%d, or 'q' to end quiz): " % len(displayed))
            if raw is None or raw.strip().lower() == "q":
                return None
            text = raw.strip()
            pos = None
            if text.isdigit() and 1 <= int(text) <= len(displayed):
                pos = int(text) - 1
            elif len(text) == 1 and text.isalpha():
                letter_pos = ord(text.upper()) - ord("A")
                if 0 <= letter_pos < len(displayed):
                    pos = letter_pos
            if pos is None:
                print("  Please enter a choice number.")
                continue
            original_index = displayed[pos][0]
            return core.grade_mcq(q, original_index)

    def _ask_numeric(self, q):
        parts = q.get("parts") or []
        answers = []
        for part in parts:
            unit = " (%s)" % part["unit"] if part.get("unit") else ""
            raw = self._ask("  %s%s: " % (part.get("label", "Value"), unit))
            if raw is None:
                return None  # EOF ends the quiz gracefully
            answers.append(raw)  # blank stays blank -> graded incorrect
        return core.grade_numeric(q, answers)

    def _ask_sequence(self, q):
        displayed = core.shuffle_sequence_steps(q, self.rng)
        print("  Steps (shuffled):")
        for letter, _orig, text in displayed:
            print("    %s) %s" % (letter, text))
        raw = self._ask("Enter the correct order (e.g. BADC), or 'q' to end quiz: ")
        if raw is None or raw.strip().lower() == "q":
            return None
        order = core.parse_sequence_letters(raw, displayed)
        if order is None:
            print("  Could not parse that as an ordering - marked incorrect.")
            return False
        return core.grade_sequence(q, order)

    def _ask_self_check(self, q):
        key = q.get("key_elements") or []
        if key:
            print("  Key elements to cover:")
            for item in key:
                print("    - %s" % item)
        if self._ask("Press Enter to reveal the model answer (or 'q' to end quiz): ") is None:
            return None
        print("\n  Model answer:")
        print("  " + (q.get("model_answer", "(none)") or "(none)"))
        while True:
            raw = self._ask("Did you recall it correctly? (y/n, 'q' to end quiz): ")
            if raw is None or raw.strip().lower() == "q":
                return None
            text = raw.strip().lower()
            if text.startswith("y"):
                return True
            if text.startswith("n") or text == "":
                return False
            print("  Please answer y or n.")

    def _ask_needs_review(self):
        raw = self._ask("Press Enter to continue, or 'r' to flag 'Needs review': ")
        return bool(raw and raw.strip().lower().startswith("r"))

    def _show_feedback(self, q, correct):
        print("\n  %s" % ("CORRECT" if correct else "INCORRECT"))
        if not correct:
            print("  Correct answer: %s" % core.correct_answer_text(q))
        if q.get("explanation"):
            print("  Explanation: %s" % q["explanation"])
        if q.get("source"):
            print("  Source: %s" % q["source"])

    def _show_end_screen(self, session, title):
        print("\n=== %s - Results ===" % title)
        if session.total == 0:
            print("No questions were answered.")
            return
        pct = 100.0 * session.score / session.total
        print("Score: %d/%d (%.0f%%)" % (session.score, session.total, pct))
        print("\nPer category:")
        for category, (good, total) in session.per_category().items():
            print("  %-22s %d/%d" % (category, good, total))
        missed = session.missed()
        if missed:
            print("\nMissed / flagged for review:")
            for r in missed:
                flag = " [needs review]" if r.needs_review else ""
                print("  %s  %s%s" % (r.question_id, r.prompt[:70], flag))
        else:
            print("\nNo missed questions - well done.")

    # -- procedure trainer -----------------------------------------------------

    def procedure_trainer(self):
        if not self.procedures:
            print("\nNo procedures available.")
            if self.proc_errors:
                print("(Check the data file: %s)" % "; ".join(self.proc_errors[:2]))
            return
        groups = core.procedures_by_exercise(self.procedures)
        names = ["%s (%d)" % (name, len(procs)) for name, procs in groups]
        pick = self._pick_from_list("Exercise:", names)
        if pick is None:
            return
        exercise = groups[names.index(pick)][0]
        procs = dict(groups)[exercise]

        titles = ["%s [%s]" % (p.get("title", p.get("id")), p.get("kind", "procedure")) for p in procs]
        pick = self._pick_from_list("Procedure in %s:" % exercise, titles)
        if pick is None:
            return
        proc = procs[titles.index(pick)]
        self._run_procedure(proc)

    def _run_procedure(self, proc):
        print("\n=== %s ===" % proc.get("title", proc.get("id")))
        if proc.get("exercise"):
            print("Exercise: %s" % proc["exercise"])
        if proc.get("briefing"):
            print("Briefing: %s" % proc["briefing"])
        steps = proc.get("steps") or []
        raw = self._ask(
            "\nPress Enter to step through one at a time, or type 'all' "
            "for the full checklist: "
        )
        if raw is not None and raw.strip().lower() == "all":
            print("\nFull checklist:")
            for i, step in enumerate(steps, 1):
                print("  %2d. %s" % (i, step))
        else:
            print("\nStep-through (Enter = reveal next step):")
            for i, step in enumerate(steps, 1):
                print("  Step %d/%d: %s" % (i, len(steps), step))
                if i < len(steps):
                    if self._ask("  ... ") is None:
                        break
        if proc.get("callouts"):
            print("\nCallouts:")
            for c in proc["callouts"]:
                print("  * %s" % c)
        if proc.get("completion_standards"):
            print("\nCompletion standards:")
            for c in proc["completion_standards"]:
                print("  * %s" % c)
        if proc.get("source"):
            print("\nSource: %s" % proc["source"])
        while True:
            raw = self._ask("\nCould you recall it? (y = recalled / n = needs review): ")
            if raw is None:
                return
            text = raw.strip().lower()
            if text.startswith("y"):
                recalled = True
                break
            if text.startswith("n"):
                recalled = False
                break
            print("  Please answer y or n.")
        self.progress.record_procedure(proc["id"], recalled)
        print("  Recorded: %s." % ("recalled" if recalled else "needs review"))

    # -- progress --------------------------------------------------------------

    def show_progress(self):
        summary = self.progress.summary()
        print("\n=== Progress (lifetime) ===")
        print("  Questions seen:        %d" % summary["questions_seen"])
        print("  Attempts:              %d" % summary["attempts"])
        print("  Correct:               %d" % summary["correct"])
        if summary["accuracy"] is not None:
            print("  Accuracy:              %.0f%%" % (100.0 * summary["accuracy"]))
        print("  In review queue:       %d" % summary["review_queue"])
        print("  Procedures completed:  %d" % summary["procedures_touched"])
        print("  Procedures 'recalled': %d" % summary["procedures_recalled"])
        raw = self._ask("\nType 'reset' to erase all progress, or Enter to go back: ")
        if raw is None or raw.strip().lower() != "reset":
            return
        confirm = self._ask("Really erase ALL progress? Type 'yes' to confirm: ")
        if confirm is not None and confirm.strip().lower() == "yes":
            self.progress.reset(confirm=True)
            print("  Progress erased.")
        else:
            print("  Reset cancelled.")


def run_cli():
    bank = core.load_question_bank()
    procedures, proc_errors = core.load_procedures()
    progress = core.ProgressStore()
    return Cli(bank, procedures, proc_errors, progress).main_menu()


# ===========================================================================
# GUI (tkinter imported lazily - only when the GUI is actually launched)
# ===========================================================================

def run_gui():
    import tkinter as tk
    from tkinter import messagebox, ttk

    bank = core.load_question_bank()
    procedures, proc_errors = core.load_procedures()
    progress = core.ProgressStore()
    rng = random.Random()

    class TrainerApp:
        FONT = ("TkDefaultFont", 11)
        FONT_BOLD = ("TkDefaultFont", 11, "bold")
        FONT_TITLE = ("TkDefaultFont", 16, "bold")
        FONT_SMALL = ("TkDefaultFont", 10)

        def __init__(self, root):
            self.root = root
            root.title(core.APP_TITLE)
            root.geometry("1000x700")
            root.minsize(900, 620)

            style = ttk.Style(root)
            style.configure("TButton", font=self.FONT, padding=6)
            style.configure("TLabel", font=self.FONT)
            style.configure("Title.TLabel", font=self.FONT_TITLE)
            style.configure("Small.TLabel", font=self.FONT_SMALL, foreground="#555")
            style.configure("Good.TLabel", font=self.FONT_BOLD, foreground="#1a7a1a")
            style.configure("Bad.TLabel", font=self.FONT_BOLD, foreground="#b02020")

            self.container = ttk.Frame(root, padding=14)
            self.container.pack(fill="both", expand=True)

            # quiz state
            self.session = None
            self.quiz_index = 0
            self.mcq_displayed = None
            self.seq_displayed = None
            self.needs_review_var = None
            self.answered_correct = None

            self.show_dashboard()

        # -- frame helpers ---------------------------------------------------

        def _clear(self):
            for child in self.container.winfo_children():
                child.destroy()

        def _header(self, title, subtitle=None):
            ttk.Label(self.container, text=title, style="Title.TLabel").pack(anchor="w")
            if subtitle:
                ttk.Label(self.container, text=subtitle, style="Small.TLabel",
                          wraplength=940, justify="left").pack(anchor="w", pady=(2, 8))

        def _data_warning_text(self):
            notes = []
            if bank.errors:
                notes.append("Question bank: " + "; ".join(bank.errors[:2]))
            if proc_errors:
                notes.append("Procedures: " + "; ".join(proc_errors[:2]))
            return "\n".join(notes)

        # -- dashboard ----------------------------------------------------------

        def show_dashboard(self):
            self._clear()
            self._header(core.APP_TITLE)
            ttk.Label(
                self.container, text=bank.disclaimer, style="Small.TLabel",
                wraplength=940, justify="left",
            ).pack(anchor="w", pady=(0, 12))

            warning = self._data_warning_text()
            if warning:
                ttk.Label(self.container, text=warning, style="Bad.TLabel",
                          wraplength=940, justify="left").pack(anchor="w", pady=(0, 12))
            if not bank.questions:
                ttk.Label(
                    self.container,
                    text="No questions loaded yet. Add data/question_bank.json "
                         "(see README.md) and restart.",
                    style="Small.TLabel", wraplength=940, justify="left",
                ).pack(anchor="w", pady=(0, 12))

            buttons = ttk.Frame(self.container)
            buttons.pack(anchor="w", pady=8)
            entries = [
                ("Practice Exam", self.start_practice_exam),
                ("Category Drill", self.start_category_drill),
                ("Numeric Drill", lambda: self.start_quiz_setup("numeric")),
                ("Procedure Trainer", self.show_procedure_list),
                ("Review Missed", self.start_review_missed),
                ("Progress", self.show_progress),
                ("Exit", self.root.destroy),
            ]
            for row, (label, command) in enumerate(entries):
                ttk.Button(buttons, text=label, command=command, width=28).grid(
                    row=row, column=0, sticky="w", pady=4
                )

            summary = progress.summary()
            stats = "Lifetime: %d attempt(s), %d correct, %d in review queue." % (
                summary["attempts"], summary["correct"], summary["review_queue"])
            ttk.Label(self.container, text=stats, style="Small.TLabel").pack(
                anchor="w", pady=(16, 0))

        # -- quiz setup ----------------------------------------------------------

        def start_practice_exam(self):
            self.start_quiz_setup(None)

        def start_review_missed(self):
            ids = progress.review_ids()
            pool = core.filter_questions(bank.questions, ids=ids)
            if not pool:
                messagebox.showinfo(
                    "Review Missed",
                    "Review queue is empty - nothing flagged or missed.",
                    parent=self.root)
                return
            self.begin_quiz(pool, "Review Missed", count=None)

        def start_quiz_setup(self, fixed_type):
            """Setup screen for Practice Exam (fixed_type=None) or one type."""
            self._clear()
            title = "Practice Exam" if fixed_type is None else "%s Drill" % fixed_type.title()
            self._header(title)

            if fixed_type is None:
                pool = list(bank.questions)
            else:
                pool = core.filter_questions(bank.questions, qtype=fixed_type)
            if not pool:
                ttk.Label(self.container,
                          text="No questions available for this mode yet.",
                          style="Bad.TLabel").pack(anchor="w", pady=8)
                ttk.Button(self.container, text="Back",
                           command=self.show_dashboard).pack(anchor="w", pady=8)
                return

            ttk.Label(self.container, text="%d question(s) in the pool." % len(pool)
                      ).pack(anchor="w", pady=4)
            row = ttk.Frame(self.container)
            row.pack(anchor="w", pady=4)
            ttk.Label(row, text="Number of questions (blank = all):").pack(side="left")
            count_var = tk.StringVar(value=str(min(10, len(pool))))
            entry = ttk.Entry(row, textvariable=count_var, width=6)
            entry.pack(side="left", padx=6)
            entry.focus_set()

            def go(_event=None):
                text = count_var.get().strip()
                count = None
                if text:
                    if not text.isdigit() or int(text) < 1:
                        messagebox.showerror(title, "Enter a positive number.",
                                             parent=self.root)
                        return
                    count = int(text)
                self.begin_quiz(pool, title, count)

            entry.bind("<Return>", go)
            ttk.Button(self.container, text="Start", command=go).pack(anchor="w", pady=8)
            ttk.Button(self.container, text="Back",
                       command=self.show_dashboard).pack(anchor="w")

        def start_category_drill(self):
            self._clear()
            self._header("Category Drill")
            if not bank.questions:
                ttk.Label(self.container, text="No questions loaded yet.",
                          style="Bad.TLabel").pack(anchor="w", pady=8)
                ttk.Button(self.container, text="Back",
                           command=self.show_dashboard).pack(anchor="w")
                return

            form = ttk.Frame(self.container)
            form.pack(anchor="w", pady=8)

            ttk.Label(form, text="Category:").grid(row=0, column=0, sticky="w", pady=3)
            cat_values = ["(all)"] + bank.categories()
            cat_var = tk.StringVar(value="(all)")
            ttk.Combobox(form, textvariable=cat_var, values=cat_values,
                         state="readonly", width=34).grid(row=0, column=1, sticky="w")

            ttk.Label(form, text="Exercise:").grid(row=1, column=0, sticky="w", pady=3)
            ex_values = ["(all)"] + bank.exercises()
            ex_var = tk.StringVar(value="(all)")
            ttk.Combobox(form, textvariable=ex_var, values=ex_values,
                         state="readonly", width=34).grid(row=1, column=1, sticky="w")

            ttk.Label(form, text="Type:").grid(row=2, column=0, sticky="w", pady=3)
            type_values = ["(all)"] + list(core.QUESTION_TYPES)
            type_var = tk.StringVar(value="(all)")
            ttk.Combobox(form, textvariable=type_var, values=type_values,
                         state="readonly", width=34).grid(row=2, column=1, sticky="w")

            ttk.Label(form, text="Questions (blank = all):").grid(
                row=3, column=0, sticky="w", pady=3)
            count_var = tk.StringVar(value="10")
            ttk.Entry(form, textvariable=count_var, width=6).grid(
                row=3, column=1, sticky="w")

            def go():
                text = count_var.get().strip()
                count = None
                if text:
                    if not text.isdigit() or int(text) < 1:
                        messagebox.showerror("Category Drill",
                                             "Enter a positive number.",
                                             parent=self.root)
                        return
                    count = int(text)
                pool = core.filter_questions(
                    bank.questions,
                    category=None if cat_var.get() == "(all)" else cat_var.get(),
                    exercise=None if ex_var.get() == "(all)" else ex_var.get(),
                    qtype=None if type_var.get() == "(all)" else type_var.get(),
                )
                if not pool:
                    messagebox.showinfo("Category Drill",
                                        "No questions match that filter.",
                                        parent=self.root)
                    return
                self.begin_quiz(pool, "Category Drill", count)

            ttk.Button(self.container, text="Start", command=go).pack(anchor="w", pady=8)
            ttk.Button(self.container, text="Back",
                       command=self.show_dashboard).pack(anchor="w")

        # -- quiz screen ----------------------------------------------------------

        def begin_quiz(self, pool, title, count):
            self.session = core.QuizSession(pool, rng=rng).limit(count)
            self.quiz_index = 0
            self.quiz_title = title
            self.show_question()

        def show_question(self):
            self._clear()
            session = self.session
            if self.quiz_index >= len(session.questions):
                self.show_end_screen()
                return
            q = session.questions[self.quiz_index]
            self.answered_correct = None
            self.needs_review_var = tk.BooleanVar(value=False)

            self._header(
                self.quiz_title,
                "Question %d/%d   [%s]   %s | %s" % (
                    self.quiz_index + 1, len(session.questions), q.get("id", "?"),
                    q.get("category", "?"), q.get("exercise", "-")))

            ttk.Label(self.container, text=q.get("prompt", "(no prompt)"),
                      font=self.FONT_BOLD, wraplength=940,
                      justify="left").pack(anchor="w", pady=(0, 8))

            self.answer_area = ttk.Frame(self.container)
            self.answer_area.pack(anchor="w", fill="x", pady=4)

            qtype = q.get("type")
            if qtype == "mcq":
                self._build_mcq(q)
            elif qtype == "numeric":
                self._build_numeric(q)
            elif qtype == "sequence":
                self._build_sequence(q)
            elif qtype == "self_check":
                self._build_self_check(q)
            else:
                ttk.Label(self.answer_area,
                          text="Unsupported question type %r" % (qtype,),
                          style="Bad.TLabel").pack(anchor="w")
                self._grade_and_show(False)

        # answer builders; each calls _grade_and_show(correct) on submit -----

        def _build_mcq(self, q):
            self.mcq_displayed, _pos = core.shuffle_mcq_choices(q, rng)
            self.mcq_var = tk.IntVar(value=-1)
            for pos, (_orig, text) in enumerate(self.mcq_displayed):
                ttk.Radiobutton(self.answer_area, text=text, value=pos,
                                variable=self.mcq_var).pack(anchor="w", pady=2)

            def submit():
                pos = self.mcq_var.get()
                if pos < 0:
                    messagebox.showinfo("Answer", "Pick a choice first.",
                                        parent=self.root)
                    return
                self._grade_and_show(
                    core.grade_mcq(q, self.mcq_displayed[pos][0]))

            self._build_submit(submit)

        def _build_numeric(self, q):
            self.numeric_entries = []
            for part in q.get("parts") or []:
                row = ttk.Frame(self.answer_area)
                row.pack(anchor="w", pady=2)
                unit = " (%s)" % part["unit"] if part.get("unit") else ""
                ttk.Label(row, text="%s%s:" % (part.get("label", "Value"), unit),
                          width=28).pack(side="left")
                var = tk.StringVar()
                entry = ttk.Entry(row, textvariable=var, width=12)
                entry.pack(side="left")
                entry.bind("<Return>", lambda _e: (submit(), "break")[1])
                self.numeric_entries.append(var)
            if self.numeric_entries:
                self.answer_area.winfo_children()[0].winfo_children()[1].focus_set()

            def submit():
                self._grade_and_show(core.grade_numeric(
                    q, [v.get() for v in self.numeric_entries]))

            self._build_submit(submit)

        def _build_sequence(self, q):
            self.seq_displayed = core.shuffle_sequence_steps(q, rng)
            for letter, _orig, text in self.seq_displayed:
                ttk.Label(self.answer_area, text="%s)  %s" % (letter, text),
                          wraplength=900, justify="left").pack(anchor="w", pady=1)
            row = ttk.Frame(self.answer_area)
            row.pack(anchor="w", pady=6)
            ttk.Label(row, text="Correct order (e.g. BADC):").pack(side="left")
            self.seq_var = tk.StringVar()
            entry = ttk.Entry(row, textvariable=self.seq_var, width=12)
            entry.pack(side="left", padx=6)
            entry.focus_set()
            entry.bind("<Return>", lambda _e: (submit(), "break")[1])

            def submit():
                order = core.parse_sequence_letters(
                    self.seq_var.get(), self.seq_displayed)
                if order is None:
                    self._grade_and_show(False)
                else:
                    self._grade_and_show(core.grade_sequence(q, order))

            self._build_submit(submit)

        def _build_self_check(self, q):
            key = q.get("key_elements") or []
            if key:
                ttk.Label(self.answer_area, text="Key elements to cover:",
                          font=self.FONT_BOLD).pack(anchor="w")
                for item in key:
                    ttk.Label(self.answer_area, text="- %s" % item,
                              wraplength=900, justify="left").pack(anchor="w")
            model = tk.Text(self.answer_area, height=6, wrap="word",
                            font=self.FONT)
            model.insert("1.0", q.get("model_answer", "(no model answer)"))
            model.configure(state="disabled")

            def reveal():
                model.pack(anchor="w", fill="x", pady=6)
                reveal_btn.state(["disabled"])
                yes_btn.state(["!disabled"])
                no_btn.state(["!disabled"])

            def mark(recalled):
                self._grade_and_show(core.grade_self_check(q, recalled))

            reveal_btn = ttk.Button(self.answer_area, text="Reveal model answer",
                                    command=reveal)
            reveal_btn.pack(anchor="w", pady=6)
            marks = ttk.Frame(self.answer_area)
            marks.pack(anchor="w")
            yes_btn = ttk.Button(marks, text="I recalled it",
                                 command=lambda: mark(True))
            no_btn = ttk.Button(marks, text="Needs work",
                                command=lambda: mark(False))
            yes_btn.pack(side="left", padx=(0, 6))
            no_btn.pack(side="left")
            yes_btn.state(["disabled"])
            no_btn.state(["disabled"])
            self.submit_frame = None

        def _build_submit(self, submit):
            self.submit_frame = ttk.Frame(self.container)
            self.submit_frame.pack(anchor="w", pady=8)
            ttk.Button(self.submit_frame, text="Submit answer",
                       command=submit).pack(side="left")
            ttk.Button(self.submit_frame, text="End quiz",
                       command=self.show_end_screen).pack(side="left", padx=8)

        # feedback / navigation ------------------------------------------------

        def _grade_and_show(self, correct):
            if self.answered_correct is not None:
                return  # already graded (e.g. duplicate <Return> event)
            q = self.session.questions[self.quiz_index]
            self.answered_correct = bool(correct)
            if self.submit_frame is not None:
                self.submit_frame.destroy()
                self.submit_frame = None

            fb = ttk.Frame(self.container)
            fb.pack(anchor="w", fill="x", pady=8)
            ttk.Label(fb, text="CORRECT" if correct else "INCORRECT",
                      style="Good.TLabel" if correct else "Bad.TLabel"
                      ).pack(anchor="w")
            if not correct:
                ttk.Label(fb, text="Correct answer: %s"
                          % core.correct_answer_text(q),
                          wraplength=940, justify="left").pack(anchor="w")
            if q.get("explanation"):
                ttk.Label(fb, text="Explanation: %s" % q["explanation"],
                          wraplength=940, justify="left").pack(anchor="w", pady=2)
            if q.get("source"):
                ttk.Label(fb, text="Source: %s" % q["source"],
                          style="Small.TLabel", wraplength=940,
                          justify="left").pack(anchor="w")

            ttk.Checkbutton(
                fb, text="Needs review (queue this question even if correct)",
                variable=self.needs_review_var).pack(anchor="w", pady=4)

            nav = ttk.Frame(fb)
            nav.pack(anchor="w", pady=6)
            ttk.Button(nav, text="Next", command=self._next_question,
                       ).pack(side="left")
            ttk.Button(nav, text="End quiz",
                       command=self._record_and_end).pack(side="left", padx=8)
            self.root.bind("<Return>", lambda _e: self._next_question())

        def _record_current(self):
            q = self.session.questions[self.quiz_index]
            needs_review = bool(self.needs_review_var.get())
            self.session.record(q, self.answered_correct, needs_review)
            if q.get("id"):
                progress.record_question(q["id"], self.answered_correct,
                                         needs_review)

        def _next_question(self):
            if self.answered_correct is None:
                return
            self.root.unbind("<Return>")
            self._record_current()
            self.quiz_index += 1
            self.show_question()

        def _record_and_end(self):
            self.root.unbind("<Return>")
            self._record_current()
            self.quiz_index = len(self.session.questions)
            self.show_end_screen()

        def show_end_screen(self):
            self.root.unbind("<Return>")
            self._clear()
            session = self.session
            self._header("%s - Results" % self.quiz_title)
            if session.total == 0:
                ttk.Label(self.container, text="No questions were answered."
                          ).pack(anchor="w", pady=8)
            else:
                pct = 100.0 * session.score / session.total
                ttk.Label(self.container,
                          text="Score: %d/%d (%.0f%%)"
                          % (session.score, session.total, pct),
                          font=self.FONT_TITLE).pack(anchor="w", pady=4)
                ttk.Label(self.container, text="Per category:",
                          font=self.FONT_BOLD).pack(anchor="w", pady=(10, 2))
                for category, (good, total) in session.per_category().items():
                    ttk.Label(self.container, text="  %-24s %d/%d"
                              % (category, good, total)).pack(anchor="w")
                missed = session.missed()
                ttk.Label(self.container,
                          text="Missed / flagged for review:" if missed
                          else "No missed questions - well done.",
                          font=self.FONT_BOLD).pack(anchor="w", pady=(10, 2))
                if missed:
                    box = tk.Text(self.container, height=8, wrap="word",
                                  font=self.FONT)
                    for r in missed:
                        flag = " [needs review]" if r.needs_review else ""
                        box.insert("end", "%s  %s%s\n"
                                   % (r.question_id, r.prompt, flag))
                    box.configure(state="disabled")
                    box.pack(anchor="w", fill="both", expand=True)
            ttk.Button(self.container, text="Back to dashboard",
                       command=self.show_dashboard).pack(anchor="w", pady=10)

        # -- procedure trainer --------------------------------------------------

        def show_procedure_list(self):
            self._clear()
            self._header("Procedure Trainer")
            if not procedures:
                ttk.Label(self.container,
                          text="No procedures loaded yet. Add "
                               "data/procedures.json and restart.",
                          style="Bad.TLabel").pack(anchor="w", pady=8)
                ttk.Button(self.container, text="Back",
                           command=self.show_dashboard).pack(anchor="w")
                return
            groups = core.procedures_by_exercise(procedures)
            for exercise, procs in groups:
                ttk.Label(self.container, text=exercise,
                          font=self.FONT_BOLD).pack(anchor="w", pady=(8, 2))
                for proc in procs:
                    stats = progress.procedure_stats(proc["id"])
                    suffix = ""
                    if stats.get("completions"):
                        suffix = "  (%dx, %s)" % (
                            stats["completions"],
                            stats.get("self_rating") or "done")
                    ttk.Button(
                        self.container,
                        text="%s [%s]%s" % (proc.get("title", proc["id"]),
                                            proc.get("kind", "procedure"),
                                            suffix),
                        command=lambda p=proc: self.show_procedure(p),
                    ).pack(anchor="w", pady=1)
            ttk.Button(self.container, text="Back",
                       command=self.show_dashboard).pack(anchor="w", pady=12)

        def show_procedure(self, proc):
            self._clear()
            self._header(proc.get("title", proc.get("id")),
                         "%s | %s" % (proc.get("exercise", ""),
                                      proc.get("kind", "procedure")))
            if proc.get("briefing"):
                ttk.Label(self.container, text="Briefing: %s" % proc["briefing"],
                          wraplength=940, justify="left").pack(anchor="w",
                                                               pady=(0, 8))

            steps = proc.get("steps") or []
            state = {"index": 0, "all_shown": False}

            body = ttk.Frame(self.container)
            body.pack(anchor="w", fill="both", expand=True)

            step_label = ttk.Label(body, text="", wraplength=940, justify="left",
                                   font=self.FONT)
            step_box = tk.Text(body, height=12, wrap="word", font=self.FONT)
            check_vars = []

            def render_step():
                step_box.pack_forget()
                step_label.pack(anchor="w", pady=4)
                i = state["index"]
                step_label.configure(
                    text="Step %d/%d: %s" % (i + 1, len(steps), steps[i]))
                if i < len(steps) - 1:
                    next_btn.configure(text="Reveal next step")
                    next_btn.state(["!disabled"])
                else:
                    next_btn.configure(text="All steps shown")
                    next_btn.state(["disabled"])

            def render_all():
                step_label.pack_forget()
                step_box.configure(state="normal")
                step_box.delete("1.0", "end")
                step_box.pack(anchor="w", fill="both", expand=True, pady=4)
                for i, step in enumerate(steps, 1):
                    var = tk.BooleanVar(value=False)
                    check_vars.append(var)
                    step_box.insert("end", "[ ] %d. %s\n" % (i, step))
                step_box.configure(state="disabled")
                next_btn.state(["disabled"])

            def advance():
                if state["index"] < len(steps) - 1:
                    state["index"] += 1
                    render_step()

            controls = ttk.Frame(self.container)
            controls.pack(anchor="w", pady=6)
            next_btn = ttk.Button(controls, text="Reveal next step",
                                  command=advance)
            next_btn.pack(side="left")
            ttk.Button(controls, text="Show full checklist",
                       command=render_all).pack(side="left", padx=6)
            render_step()

            if proc.get("callouts"):
                ttk.Label(self.container, text="Callouts: "
                          + "; ".join(proc["callouts"]),
                          wraplength=940, justify="left").pack(anchor="w", pady=2)
            if proc.get("completion_standards"):
                ttk.Label(self.container, text="Completion standards: "
                          + "; ".join(proc["completion_standards"]),
                          wraplength=940, justify="left").pack(anchor="w", pady=2)
            if proc.get("source"):
                ttk.Label(self.container, text="Source: %s" % proc["source"],
                          style="Small.TLabel").pack(anchor="w", pady=2)

            rating_var = tk.StringVar(value="")
            rating = ttk.Frame(self.container)
            rating.pack(anchor="w", pady=10)

            def mark(recalled):
                progress.record_procedure(proc["id"], recalled)
                rating_var.set("Recorded: %s."
                               % ("I could recall it" if recalled
                                  else "Needs review"))

            ttk.Button(rating, text="I could recall it",
                       command=lambda: mark(True)).pack(side="left")
            ttk.Button(rating, text="Needs review",
                       command=lambda: mark(False)).pack(side="left", padx=6)
            ttk.Button(rating, text="Back to procedures",
                       command=self.show_procedure_list).pack(side="left", padx=6)
            ttk.Label(self.container, textvariable=rating_var,
                      style="Good.TLabel").pack(anchor="w")

        # -- progress --------------------------------------------------------------

        def show_progress(self):
            self._clear()
            self._header("Progress", "Stored at %s" % progress.path)
            summary = progress.summary()
            lines = [
                ("Questions seen", str(summary["questions_seen"])),
                ("Attempts", str(summary["attempts"])),
                ("Correct", str(summary["correct"])),
                ("Accuracy", ("%.0f%%" % (100.0 * summary["accuracy"]))
                 if summary["accuracy"] is not None else "-"),
                ("In review queue", str(summary["review_queue"])),
                ("Procedures completed", str(summary["procedures_touched"])),
                ("Procedures 'recalled'", str(summary["procedures_recalled"])),
            ]
            for label, value in lines:
                ttk.Label(self.container, text="%-24s %s" % (label + ":", value)
                          ).pack(anchor="w", pady=1)

            def do_reset():
                if messagebox.askyesno(
                        "Reset progress",
                        "Erase ALL saved progress? This cannot be undone.",
                        parent=self.root):
                    progress.reset(confirm=True)
                    self.show_progress()

            buttons = ttk.Frame(self.container)
            buttons.pack(anchor="w", pady=14)
            ttk.Button(buttons, text="Reset progress...",
                       command=do_reset).pack(side="left")
            ttk.Button(buttons, text="Back",
                       command=self.show_dashboard).pack(side="left", padx=8)

    root = tk.Tk()
    TrainerApp(root)
    root.mainloop()
    return 0


# ===========================================================================
# Entry point
# ===========================================================================

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="RAC DA40 Checkride Trainer - study aid only; "
                    "AFM/POH and current controlled RAC SOP take precedence.")
    parser.add_argument("--cli", action="store_true",
                        help="run the text-mode CLI instead of the GUI")
    args = parser.parse_args(argv)
    if args.cli:
        return run_cli()
    try:
        return run_gui()
    except ImportError as exc:  # tkinter unavailable
        print("Could not start the GUI (%s)." % exc, file=sys.stderr)
        print("Falling back to the CLI. Use 'python app.py --cli' directly.",
              file=sys.stderr)
        return run_cli()


if __name__ == "__main__":
    sys.exit(main())
