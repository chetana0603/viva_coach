"""
The core system's pipeline, persisted.

    project report  ->  concepts + technologies  ->  study cards  ->  question pool

The question pool is PRE-GENERATED, not built live during the test. Adaptivity is
about which question comes next, not when it was written — so generating upfront
keeps the test fully adaptive while removing the failure modes of calling an LLM
mid-exam (latency between questions, an API error stranding a student halfway,
rate limits when several students test at once, and no auditable record of what
was asked).
"""
import hashlib
from datetime import datetime

from flask import current_app

from app.core import core_engine as engine
from app.extensions import db
from app.models.exam import Concept
from app.models.project import ProjectSubmission, StudyCard
from app.models.question import Question
from app.question_authoring.validator import validate_mcq

LETTERS = ("A", "B", "C", "D")

# Levels the project test can reach. Kept at 0-5 so the adaptive climb is the
# full range the prototype defined.
POOL_LEVELS = (0, 1, 2, 3, 4, 5)
# Per concept, per level. Enough that a climb never dead-ends on a level.
POOL_PER_LEVEL = 3
MAX_CONCEPTS = 6


def _fingerprint(text):
    return hashlib.sha256(" ".join((text or "").lower().split()).encode()).hexdigest()[:64]


def _api_key():
    return current_app.config.get("GROQ_API_KEY") or None


# ---------------------------------------------------------------- ingest
def attach_material(submission, filenames, material):
    submission.source_filenames = "\n".join(filenames or [])
    submission.material = material or ""
    submission.status = "submitted"
    db.session.commit()
    return submission


def extract_text(filename, file_bytes):
    """PDF / DOCX / code / plain text -> text, via the prototype's extractor."""
    return engine.extract_text_from_file(filename, file_bytes)


# -------------------------------------------------------------- analyse
def analyse_submission(submission):
    """Extract concepts and technologies from the report."""
    if not (submission.material or "").strip():
        submission.status = "failed"
        submission.error_message = "No readable text was found in the uploaded files."
        db.session.commit()
        return submission

    result = engine.extract_concepts(submission.material, api_key=_api_key())
    concepts = [c for c in (result.get("concepts") or []) if c.strip()][:MAX_CONCEPTS]

    if not concepts:
        submission.status = "failed"
        submission.error_message = "No concepts could be extracted from this material."
        db.session.commit()
        return submission

    submission.concepts = concepts
    submission.technologies = result.get("technologies") or []
    submission.generation_source = "AI" if engine.llm_available(_api_key()) else "Offline"
    submission.status = "analysed"
    submission.analysed_at = datetime.utcnow()
    db.session.commit()
    return submission


# ----------------------------------------------------------- study cards
def generate_study_cards(submission):
    """Build one Learn-Mode card per concept. This is the teaching step."""
    if submission.status not in ("analysed", "cards_ready", "questions_ready"):
        return submission

    existing = {c.concept_name for c in submission.cards}
    for concept in submission.concepts:
        if concept in existing:
            continue
        card = engine.generate_study_card(concept, submission.material, api_key=_api_key())
        db.session.add(StudyCard(
            submission_id=submission.id,
            concept_name=concept,
            definition=card.get("definition", ""),
            purpose=card.get("purpose", ""),
            where_used=card.get("where_used", ""),
            recommended_answer=card.get("recommended_answer", ""),
            misconception=card.get("misconception", ""),
            revision_points_json=None,
            retrieved_context=card.get("retrieved_context", ""),
            source=card.get("source", "Offline"),
        ))
        db.session.flush()
        StudyCard.query.filter_by(
            submission_id=submission.id, concept_name=concept
        ).first().revision_points = card.get("revision_points", [])

    if submission.status == "analysed":
        submission.status = "cards_ready"
    db.session.commit()
    return submission


# --------------------------------------------------- adaptive question pool
def _concept_row(subject, name):
    """Concepts extracted from a report are per-student, so create on demand."""
    concept = Concept.query.filter_by(subject=subject, name=name).first()
    if concept is None:
        concept = Concept(subject=subject, name=name, active=False,
                          description="Extracted from a project submission.")
        db.session.add(concept)
        db.session.flush()
    return concept


def generate_question_pool(submission, per_level=POOL_PER_LEVEL, levels=POOL_LEVELS):
    """
    Pre-generate the adaptive pool for this submission, grounded in the student's
    own material. Questions are auto-approved because they are private to this
    student's test and there is no teacher in the loop for a project viva.
    """
    if submission.status not in ("cards_ready", "questions_ready"):
        return submission, {"created": 0, "rejected": 0}

    api_key = _api_key()
    created = rejected = 0

    for concept_name in submission.concepts:
        concept = _concept_row(submission.subject, concept_name)
        previous = [
            q.question_text for q in
            Question.query.filter_by(submission_id=submission.id,
                                     concept_id=concept.id).all()
        ]
        for level in levels:
            have = Question.query.filter_by(
                submission_id=submission.id, concept_id=concept.id, level=level
            ).count()
            attempts = 0
            while have < per_level and attempts < per_level * 3:
                attempts += 1
                mcq = engine.generate_mcq(
                    concept_name, level, submission.material,
                    previous_questions=previous, api_key=api_key,
                )
                if not mcq:
                    break

                problems = validate_mcq(mcq, submission.material, previous)
                if problems:
                    rejected += 1
                    continue

                fp = _fingerprint(mcq["question"])
                if Question.query.filter_by(fingerprint=fp,
                                            submission_id=submission.id).first():
                    continue

                opts = list(mcq["options"])[:4]
                breakdown = mcq.get("options_breakdown", {}) or {}
                while len(opts) < 4:
                    opts.append(None)

                db.session.add(Question(
                    subject=submission.subject,
                    concept_id=concept.id,
                    level=level,
                    question_type="mcq",
                    question_text=mcq["question"],
                    option_a=opts[0], option_b=opts[1], option_c=opts[2], option_d=opts[3],
                    correct_option=LETTERS[mcq["answer"]],
                    explanation=mcq.get("explanation", ""),
                    breakdown_a=str(breakdown.get(0, "") or ""),
                    breakdown_b=str(breakdown.get(1, "") or ""),
                    breakdown_c=str(breakdown.get(2, "") or ""),
                    breakdown_d=str(breakdown.get(3, "") or ""),
                    source_document="Project report",
                    generation_method="llm" if api_key else "existing_bank",
                    review_status="approved",
                    fingerprint=fp,
                    submission_id=submission.id,
                    created_by=submission.user_id,
                ))
                previous.append(mcq["question"])
                have += 1
                created += 1
            db.session.commit()

    submission.status = "questions_ready"
    submission.questions_generated_at = datetime.utcnow()
    db.session.commit()
    return submission, {"created": created, "rejected": rejected}


def pool_coverage(submission):
    """{concept: {level: count}} so the student/teacher can see the pool's depth."""
    coverage = {}
    rows = Question.query.filter_by(submission_id=submission.id).all()
    by_id = {c.id: c.name for c in Concept.query.filter(
        Concept.id.in_({r.concept_id for r in rows} or {0})).all()}
    for r in rows:
        name = by_id.get(r.concept_id, "?")
        coverage.setdefault(name, {})
        coverage[name][r.level] = coverage[name].get(r.level, 0) + 1
    return coverage


def get_or_create_submission(user, exam):
    sub = ProjectSubmission.query.filter_by(user_id=user.id, exam_id=exam.id).first()
    if sub is None:
        sub = ProjectSubmission(user_id=user.id, exam_id=exam.id,
                                subject=exam.subject, status="draft")
        db.session.add(sub)
        db.session.commit()
    return sub
