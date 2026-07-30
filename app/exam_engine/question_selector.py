"""Pick the next question for an attempt from the approved bank."""
import secrets

from sqlalchemy import select

from app.exam_engine.adaptive_service import nearest_available_level
from app.extensions import db
from app.models.attempt import AssignedQuestion
from app.models.exam import ExamBlueprint
from app.models.question import Question


def _used_question_ids(attempt_id):
    rows = db.session.execute(
        select(AssignedQuestion.question_id).where(AssignedQuestion.attempt_id == attempt_id)
    ).scalars().all()
    return set(rows)


def _study_group_seen_ids(exam, user_id):
    """
    Questions this student was already assigned in OTHER exams of the same study group.

    For a pre/post study (Test 1 then Test 2 sharing a study_group tag), this guarantees
    Test 2 never reuses a Test 1 question — so an improvement measures learning, not memory
    of a specific item. Returns an empty set when the exam has no study_group.
    """
    from app.models.attempt import Attempt
    from app.models.exam import Exam

    group = getattr(exam, "study_group", None)
    if not group:
        return set()

    rows = db.session.execute(
        select(AssignedQuestion.question_id)
        .join(Attempt, AssignedQuestion.attempt_id == Attempt.id)
        .join(Exam, Attempt.exam_id == Exam.id)
        .where(Exam.study_group == group, Attempt.user_id == user_id, Exam.id != exam.id)
    ).scalars().all()
    return set(rows)


def _blueprint_cells(exam_id):
    return db.session.execute(
        select(ExamBlueprint).where(ExamBlueprint.exam_id == exam_id)
    ).scalars().all()


def _concept_quota_state(attempt, cells):
    """How many questions each concept still owes, based on what's assigned so far."""
    assigned_by_concept = {}
    for aq in attempt.assigned:
        cid = aq.question.concept_id
        assigned_by_concept[cid] = assigned_by_concept.get(cid, 0) + 1

    required = {}
    for c in cells:
        required[c.concept_id] = required.get(c.concept_id, 0) + c.required_count
    return assigned_by_concept, required


def choose_concept(attempt, cells):
    """Concept with the largest remaining quota; ties broken randomly."""
    assigned, required = _concept_quota_state(attempt, cells)
    remaining = [(cid, required[cid] - assigned.get(cid, 0)) for cid in required]
    remaining = [r for r in remaining if r[1] > 0] or [(cid, 0) for cid in required]
    if not remaining:
        return None
    top = max(r[1] for r in remaining)
    pool = [cid for cid, r in remaining if r == top]
    return pool[secrets.randbelow(len(pool))]


def approved_unused_questions(exam, attempt_id, concept_id, level, used_ids=None,
                              submission_id=None):
    """
    Candidate questions for one concept/level.

    `submission_id` scopes the pool to a single student's project questions. A
    project pool is private: without this filter one student's generated
    questions could be served to another, which would leak their project.
    """
    used_ids = used_ids if used_ids is not None else _used_question_ids(attempt_id)
    stmt = select(Question).where(
        Question.subject == exam.subject,
        Question.concept_id == concept_id,
        Question.level == level,
        Question.question_type == "mcq",
        Question.review_status == "approved",
    )
    if submission_id is not None:
        stmt = stmt.where(Question.submission_id == submission_id)
    else:
        stmt = stmt.where(Question.submission_id.is_(None))
    return [q for q in db.session.execute(stmt).scalars().all() if q.id not in used_ids]


def _submission_for(exam, user_id):
    """The student's project submission — only project vivas draw on their own pool."""
    if not exam.is_project():
        return None
    from app.models.project import ProjectSubmission
    return ProjectSubmission.query.filter_by(user_id=user_id, exam_id=exam.id).first()


def _exam_concept_ids(exam):
    from app.models.exam import ExamConcept
    return db.session.execute(
        select(ExamConcept.concept_id).where(ExamConcept.exam_id == exam.id)
    ).scalars().all()


def select_question(exam, attempt, target_level, concept_id=None):
    """Return a Question or None if the pool is exhausted for this attempt."""
    submission = _submission_for(exam, attempt.user_id)
    submission_id = submission.id if submission else None

    used = _used_question_ids(attempt.id)
    if submission_id is None:
        used |= _study_group_seen_ids(exam, attempt.user_id)

    # A remedial asks for the same concept the student just missed.
    if concept_id is not None:
        concept_order = [concept_id]
    elif submission_id is not None:
        from app.models.exam import Concept
        concept_order = db.session.execute(
            select(Question.concept_id).where(
                Question.submission_id == submission_id).distinct()
        ).scalars().all()
        concept_order = _least_used_first(attempt, concept_order)
    else:
        cells = _blueprint_cells(exam.id)
        concept_order = _exam_concept_ids(exam)
        if concept_order:
            concept_order = _least_used_first(attempt, concept_order)
        else:
            primary = choose_concept(attempt, cells) if cells else None
            concept_order = [primary] if primary else []
            concept_order += [c.concept_id for c in cells if c.concept_id not in concept_order]

    if not concept_order:  # nothing selected: fall back to every concept in the subject
        from app.models.exam import Concept
        concept_order = db.session.execute(
            select(Concept.id).where(Concept.subject == exam.subject)
        ).scalars().all()

    for cid in concept_order:
        candidates = approved_unused_questions(exam, attempt.id, cid, target_level,
                                               used, submission_id)
        if not candidates:
            level_stmt = select(Question.level).where(
                Question.subject == exam.subject,
                Question.concept_id == cid,
                Question.review_status == "approved",
                Question.level <= exam.max_level,
            )
            if submission_id is not None:
                level_stmt = level_stmt.where(Question.submission_id == submission_id)
            else:
                level_stmt = level_stmt.where(Question.submission_id.is_(None))
            levels = db.session.execute(level_stmt.distinct()).scalars().all()
            fallback = nearest_available_level(target_level, levels)
            if fallback is None:
                continue
            candidates = approved_unused_questions(exam, attempt.id, cid, fallback,
                                                   used, submission_id)
        if candidates:
            return candidates[secrets.randbelow(len(candidates))]
    return None


def _least_used_first(attempt, concept_ids):
    """Spread questions across concepts instead of exhausting one at a time."""
    counts = {}
    for aq in attempt.assigned:
        counts[aq.question.concept_id] = counts.get(aq.question.concept_id, 0) + 1
    return sorted(concept_ids, key=lambda cid: (counts.get(cid, 0), secrets.randbelow(1000)))
