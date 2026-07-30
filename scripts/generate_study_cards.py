"""
Generate the shared DBMS (or OS) study cards — one per concept, from the subject
notes. These are the teaching material students read between the pre-test and
the post-test.

    python scripts/generate_study_cards.py DBMS

Idempotent: concepts that already have a card are skipped, so a rate-limit
interruption can be resumed by just running it again.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()

from app import create_app                    # noqa: E402
from app.core import core_engine as engine    # noqa: E402
from app.core.subject_loader import load_subject_notes  # noqa: E402
from app.extensions import db                 # noqa: E402
from app.models.exam import Concept           # noqa: E402
from app.models.project import StudyCard      # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("subject")
    args = parser.parse_args()
    subject = args.subject.upper()

    app = create_app(os.environ.get("CONFIG", "app.config.DevelopmentConfig"))
    with app.app_context():
        api_key = app.config.get("GROQ_API_KEY")
        material = load_subject_notes(subject)
        if not material.strip():
            print(f"No notes found for {subject} in subject_materials/.")
            return

        concepts = Concept.query.filter_by(subject=subject, active=True).all()
        made = skipped = 0
        for concept in concepts:
            if StudyCard.query.filter_by(subject=subject, submission_id=None,
                                         concept_name=concept.name).first():
                skipped += 1
                continue
            card = engine.generate_study_card(concept.name, material, api_key=api_key)
            row = StudyCard(
                submission_id=None, subject=subject, concept_name=concept.name,
                definition=card.get("definition", ""),
                purpose=card.get("purpose", ""),
                where_used=card.get("where_used", ""),
                recommended_answer=card.get("recommended_answer", ""),
                misconception=card.get("misconception", ""),
                retrieved_context=card.get("retrieved_context", ""),
                source=card.get("source", "Offline"),
            )
            db.session.add(row)
            db.session.flush()
            row.revision_points = card.get("revision_points", [])
            db.session.commit()
            made += 1
            print(f"  [{subject}] {concept.name}: card {'(AI)' if 'AI' in row.source else '(offline)'}")

        print(f"\n{made} cards created, {skipped} already existed.")
        print(f"Students see them at /student/study/{subject}")


if __name__ == "__main__":
    main()
