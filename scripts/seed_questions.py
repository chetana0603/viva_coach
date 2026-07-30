"""
Import the prototype's offline MCQ bank (subject_bank.OFFLINE_MCQS) into the
database as approved questions, and create the Concept rows for every subject.

Idempotent: re-running will not duplicate questions (matched on fingerprint).
"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Read .env exactly like the `flask` command does, so DATABASE_URL and
# GROQ_API_KEY work without setting them in the shell first.
from dotenv import load_dotenv  # noqa: E402
load_dotenv()

from app import create_app
from app.core.subject_bank import OFFLINE_MCQS, SUBJECTS, get_concepts
from app.extensions import db
from app.models.exam import Concept
from app.models.question import Question

LETTERS = ("A", "B", "C", "D")


def fingerprint(text):
    return hashlib.sha256(" ".join(text.lower().split()).encode()).hexdigest()[:64]


def subject_for_concept(name):
    for code in SUBJECTS:
        if name in get_concepts(code):
            return code
    return None


def seed_concepts():
    created = 0
    for code in SUBJECTS:
        for name in get_concepts(code):
            if not Concept.query.filter_by(subject=code, name=name).first():
                db.session.add(Concept(subject=code, name=name, active=True))
                created += 1
    db.session.commit()
    return created


def seed_questions():
    created = skipped = orphan = bad_level = 0
    for concept_name, items in OFFLINE_MCQS.items():
        subject = subject_for_concept(concept_name)
        if subject is None:
            orphan += 1
            print(f"  ! '{concept_name}' is not in any subject's concept list — skipped")
            continue
        concept = Concept.query.filter_by(subject=subject, name=concept_name).first()

        for item in items:
            level = item.get("level")
            if not isinstance(level, int) or not 0 <= level <= 5:
                bad_level += 1
                print(f"  ! bad level {level!r} in '{concept_name}' — skipped")
                continue
            fp = fingerprint(item["question"])
            if Question.query.filter_by(fingerprint=fp).first():
                skipped += 1
                continue
            opts = list(item["options"])[:4]
            while len(opts) < 4:
                opts.append(None)
            db.session.add(Question(
                subject=subject,
                concept_id=concept.id,
                level=level,
                question_type="mcq",
                question_text=item["question"],
                option_a=opts[0], option_b=opts[1], option_c=opts[2], option_d=opts[3],
                correct_option=LETTERS[item["answer"]],
                explanation=item.get("explanation", ""),
                generation_method="existing_bank",
                review_status="approved",
                fingerprint=fp,
            ))
            created += 1
    db.session.commit()
    return created, skipped, orphan, bad_level


def repair_existing_bad_levels():
    """Fix any question already in the DB with a NULL/out-of-range level.

    These render as 'none' in the stock summary and confuse the adaptive engine.
    We archive them rather than guess a level — a teacher can re-level and re-approve.
    """
    from sqlalchemy import or_
    bad = Question.query.filter(
        or_(Question.level.is_(None), Question.level < 0, Question.level > 5)
    ).all()
    for q in bad:
        q.review_status = "archived"
    if bad:
        db.session.commit()
    return len(bad)


def main():
    app = create_app(os.environ.get("CONFIG", "app.config.DevelopmentConfig"))
    with app.app_context():
        print("Seeding concepts...")
        print(f"  {seed_concepts()} concepts created")

        repaired = repair_existing_bad_levels()
        if repaired:
            print(f"Archived {repaired} existing question(s) with an invalid level "
                  f"(they showed as 'none'). Re-level and re-approve them if you want them back.")

        print("Seeding questions from subject_bank.OFFLINE_MCQS...")
        created, skipped, orphan, bad_level = seed_questions()
        print(f"  {created} created, {skipped} already present, "
              f"{orphan} unmatched concepts, {bad_level} skipped for bad level")

        print("\nApproved question stock by concept and level:")
        for c in Concept.query.order_by(Concept.subject, Concept.name).all():
            counts = {}
            for q in Question.query.filter_by(concept_id=c.id, review_status="approved").all():
                counts[q.level] = counts.get(q.level, 0) + 1
            summary = ", ".join(f"L{l}:{n}" for l, n in sorted(counts.items())) or "none"
            print(f"  [{c.subject}] {c.name:48} {summary}")


if __name__ == "__main__":
    main()
