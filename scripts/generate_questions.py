"""
Pre-generate candidate questions with Groq, before the exam. Nothing here runs
during an assessment. Output lands in review_status='generated' for teacher review.

Usage:
    python scripts/generate_questions.py DBMS --levels 0 1 2 3 --per-level 8
"""
import argparse
import hashlib
import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Read .env exactly like the `flask` command does, so DATABASE_URL and
# GROQ_API_KEY work without setting them in the shell first.
from dotenv import load_dotenv  # noqa: E402
load_dotenv()

from app import create_app
from app.core import core_engine as engine
from app.core.subject_loader import load_subject_notes
from app.extensions import db
from app.models.exam import Concept
from app.models.question import Question
from app.question_authoring.validator import validate_mcq

LETTERS = ("A", "B", "C", "D")


def fingerprint(text):
    return hashlib.sha256(" ".join(text.lower().split()).encode()).hexdigest()[:64]


def existing_questions(concept_id):
    return [q.question_text for q in Question.query.filter_by(concept_id=concept_id).all()]


def _finish(total_saved, total_rejected, calls_made):
    print(f"\n{total_saved} candidates saved, {total_rejected} rejected by validation.")
    print(f"API calls made: {calls_made}")
    print("Review them at /teacher/questions?status=generated")
    return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("subject")
    parser.add_argument("--levels", nargs="+", type=int, default=[0, 1, 2, 3])
    parser.add_argument("--per-level", type=int, default=8)
    parser.add_argument("--budget", type=int, default=None,
                        help="Stop after this many API calls in total. Useful when the "
                             "daily token quota is tight — spend it where you need it.")
    parser.add_argument("--concepts", nargs="+", default=None,
                        help="Only these concepts (substring match, case-insensitive). "
                             "Generating for concepts you will not test just creates "
                             "review work you do not need.")
    parser.add_argument("--list-concepts", action="store_true",
                        help="Print the concept names for this subject and exit.")
    args = parser.parse_args()

    app = create_app(os.environ.get("CONFIG", "app.config.DevelopmentConfig"))
    with app.app_context():
        api_key = app.config.get("GROQ_API_KEY")
        if not engine.llm_available(api_key):
            print("No GROQ_API_KEY configured. Set it in .env before generating.")
            return

        # Prove the API works before spending several minutes on it.
        ok, detail = engine.check_llm(api_key)
        if not ok:
            print(f"Groq API is not usable right now: {detail}")
            print()
            if "rate_limited" in (detail or ""):
                print("You are rate limited. Free-tier quotas reset on a rolling window —")
                print("wait a while and run again. Questions already saved are unaffected.")
            elif "auth_failed" in (detail or ""):
                print("Check GROQ_API_KEY in .env — it is missing, wrong, or revoked.")
            elif "model_not_found" in (detail or ""):
                print(f"The model '{engine.DEFAULT_MODEL}' was rejected. Models get")
                print("decommissioned; pick a current one at console.groq.com/docs/models")
                print("and set it in app/core/core_engine.py (DEFAULT_MODEL).")
            return
        print(f"Groq API reachable (model: {engine.DEFAULT_MODEL})")
        if args.budget:
            print(f"Call budget: {args.budget}")
        print()
        calls_made = 0
        waits = 0

        material = load_subject_notes(args.subject)
        if not material.strip():
            print(f"No backend notes found for {args.subject}.")
            return

        concepts = Concept.query.filter_by(subject=args.subject, active=True).all()

        if args.list_concepts:
            print(f"Concepts for {args.subject}:")
            for c in concepts:
                print(f"  {c.name}")
            return

        if args.concepts:
            wanted = [w.lower() for w in args.concepts]
            concepts = [c for c in concepts
                        if any(w in c.name.lower() for w in wanted)]
            if not concepts:
                print(f"No concepts matched {args.concepts}. "
                      f"Run with --list-concepts to see the names.")
                return
        print(f"Generating for {len(concepts)} concept(s): "
              f"{', '.join(c.name for c in concepts)}\n")
        total_saved = total_rejected = 0

        for concept in concepts:
            previous = existing_questions(concept.id)
            for level in args.levels:
                saved = 0
                # Why candidates were dropped, so a low yield is never a mystery.
                drops = {"duplicate": 0, "invalid": 0, "seen": 0, "api_error": 0}
                api_error_detail = None
                # 3x, not 6x. A larger budget just spends the daily token quota on
                # attempts that are mostly duplicates anyway.
                budget = args.per_level * 3

                for _ in range(budget):
                    if saved >= args.per_level:
                        break
                    if args.budget and calls_made >= args.budget:
                        break
                    calls_made += 1
                    mcq = engine.generate_mcq(concept.name, level, material,
                                              previous_questions=previous, api_key=api_key)
                    if not mcq or mcq.get("source") != "AI":
                        # generate_mcq fell back. LAST_ERROR says why — an API
                        # failure and a duplicate question are very different
                        # problems and must not be reported as the same thing.
                        reason = engine.LAST_ERROR or "duplicate_question"

                        if reason == "duplicate_question":
                            drops["duplicate"] += 1
                            continue

                        # A per-minute limit clears on its own, so wait it out rather
                        # than throwing away the rest of the run.
                        if reason == "rate_limited_minute":
                            wait = max(engine.LAST_RETRY_AFTER, 20.0) + 2
                            waits += 1
                            if waits > 40:
                                print("\n  Too many rate-limit pauses — stopping.")
                                db.session.commit()
                                return _finish(total_saved, total_rejected, calls_made)
                            print(f"    per-minute limit reached, waiting {wait:.0f}s…",
                                  flush=True)
                            db.session.commit()
                            time.sleep(wait)
                            continue

                        drops["api_error"] += 1
                        api_error_detail = reason

                        if reason == "rate_limited_day":
                            print("\n  Daily token quota exhausted. It resets tomorrow.")
                            db.session.commit()
                            return _finish(total_saved, total_rejected, calls_made)
                        if "auth_failed" in reason or "model_not_found" in reason:
                            print(f"\n  Stopping: {reason}")
                            db.session.commit()
                            return _finish(total_saved, total_rejected, calls_made)
                        continue

                    problems = validate_mcq(mcq, material, previous)
                    if problems:
                        drops["invalid"] += 1
                        total_rejected += 1
                        continue

                    fp = fingerprint(mcq["question"])
                    if Question.query.filter_by(fingerprint=fp).first():
                        drops["seen"] += 1
                        continue

                    opts = list(mcq["options"])[:4]
                    breakdown = mcq.get("options_breakdown", {})
                    while len(opts) < 4:
                        opts.append(None)

                    db.session.add(Question(
                        subject=args.subject, concept_id=concept.id, level=level,
                        question_type="mcq", question_text=mcq["question"],
                        option_a=opts[0], option_b=opts[1], option_c=opts[2], option_d=opts[3],
                        correct_option=LETTERS[mcq["answer"]],
                        explanation=mcq.get("explanation", ""),
                        breakdown_a=str(breakdown.get(0, "") or ""),
                        breakdown_b=str(breakdown.get(1, "") or ""),
                        breakdown_c=str(breakdown.get(2, "") or ""),
                        breakdown_d=str(breakdown.get(3, "") or ""),
                        source_document=f"{args.subject} backend notes",
                        generation_method="llm", review_status="generated",
                        fingerprint=fp,
                    ))
                    previous.append(mcq["question"])
                    saved += 1
                    total_saved += 1

                db.session.commit()
                detail = ", ".join(f"{k}:{v}" for k, v in drops.items() if v)
                if api_error_detail:
                    detail += f"  [{api_error_detail[:60]}]"
                status = "ok " if saved >= args.per_level else "LOW"
                print(f"  [{status}] {concept.name[:38]:38} L{level}: {saved}/{args.per_level} saved"
                      + (f"   (dropped — {detail})" if detail else ""))

        print(f"\n{total_saved} candidates saved, {total_rejected} rejected by validation.")
        print(f"API calls made: {calls_made}")
        print("Review them at /teacher/questions?status=generated")
        print()
        print("Reading the drop counts:")
        print("  duplicate  — the model keeps asking the same things. Your notes for that")
        print("               concept may not hold many more distinct questions.")
        print("  api_error  — the call failed. The reason is shown in brackets.")
        print("  invalid    — structurally broken; the validator did its job.")
        print("  seen       — already in the database from an earlier run.")


if __name__ == "__main__":
    main()
