"""Attempt lifecycle: start, assign, answer, resume, submit. All server-authoritative."""
import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.exam_engine.adaptive_service import calculate_next_level
from app.exam_engine.question_selector import select_question
from app.extensions import db
from app.models.attempt import AssignedQuestion, Attempt
from app.models.response import Response
from app.utils.datetime_utils import utc_now
from app.utils.security import audit


class AttemptError(Exception):
    pass


# ---------------------------------------------------------------- start
def start_attempt(user, exam):
    """Create the attempt and lock in question #1. Safe against double-clicks."""
    existing = get_attempt(user.id, exam.id)
    if existing:
        return existing

    now = utc_now()
    if now < exam.exam_start or now >= exam.exam_end:
        raise AttemptError("This exam is not open right now.")

    expires_at = min(now + timedelta(minutes=exam.duration_minutes), exam.exam_end)
    attempt = Attempt(
        exam_id=exam.id, user_id=user.id, started_at=now, expires_at=expires_at,
        status="active", current_level=exam.starting_level, current_sequence=0,
        last_activity_at=now,
    )
    db.session.add(attempt)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        return get_attempt(user.id, exam.id)

    assign_next_question(attempt, exam, exam.starting_level)
    audit("attempt_started", "attempt", attempt.id, exam_id=exam.id)
    db.session.commit()
    return attempt


def get_attempt(user_id, exam_id):
    return db.session.execute(
        select(Attempt).where(Attempt.user_id == user_id, Attempt.exam_id == exam_id)
    ).scalar_one_or_none()


# ------------------------------------------------------------- assignment
def assign_next_question(attempt, exam, target_level, remedial_for=None,
                         concept_id=None):
    """
    Assign the next question. `remedial_for` marks this as a second chance after
    a wrong answer, which changes only its credit weight — it is still a real
    question drawn from the pool, not a repeat of the one they missed.

    Remedial questions do NOT consume the exam's question_count budget, so a
    student who needs remediation is not punished with a shorter test.
    """
    is_remedial = remedial_for is not None
    if not is_remedial and attempt.current_sequence >= exam.question_count:
        return None
    question = select_question(exam, attempt, target_level, concept_id=concept_id)
    if question is None:
        return None

    order = list(range(len(question.options_list())))
    for i in range(len(order) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        order[i], order[j] = order[j], order[i]

    aq = AssignedQuestion(
        attempt_id=attempt.id, question_id=question.id,
        sequence_number=attempt.current_sequence + 1,
        displayed_option_order=",".join(str(i) for i in order),
        assigned_level=question.level,
        is_remedial=is_remedial,
        remedial_for_id=(remedial_for.id if remedial_for is not None else None),
    )
    db.session.add(aq)
    if not is_remedial:
        attempt.current_sequence += 1
    db.session.flush()
    audit("question_assigned", "assigned_question", aq.id, attempt_id=attempt.id)
    return aq


def current_question(attempt):
    """The oldest assigned-but-unanswered question. Refresh-stable."""
    for aq in attempt.assigned:
        if not aq.answered:
            return aq
    return None


# ------------------------------------------------------------- answering
def submit_answer(attempt, exam, assigned_question_id, selected_option, client_response_time=None):
    """Score one answer and assign the next question, in a single transaction."""
    if attempt.status != "active":
        raise AttemptError("This attempt is no longer active.")
    if expire_if_due(attempt):
        raise AttemptError("Time is up. Your attempt was submitted automatically.")

    aq = db.session.get(AssignedQuestion, int(assigned_question_id))
    if aq is None or aq.attempt_id != attempt.id:
        raise AttemptError("That question does not belong to this attempt.")
    if aq.answered or aq.response is not None:
        raise AttemptError("That question is already answered.")

    displayed = aq.displayed_options()
    try:
        selected = int(selected_option)
    except (TypeError, ValueError):
        selected = -1
    if not 0 <= selected < len(displayed):
        raise AttemptError("Choose one of the given options.")

    is_correct = selected == aq.displayed_correct_index()

    elapsed = (utc_now() - aq.assigned_at).total_seconds()
    rt = float(client_response_time) if client_response_time else elapsed
    rt = max(0.1, min(rt, elapsed + 2))  # trust the server clock as the ceiling

    from app.exam_engine.scoring_service import award_points
    points = award_points(is_correct, aq.is_remedial)

    response = Response(
        attempt_id=attempt.id, assigned_question_id=aq.id,
        selected_option=selected, is_correct=is_correct, points=points,
        response_time_seconds=round(rt, 2), finalised=True,
    )
    aq.answered = True
    attempt.total_answered += 1
    attempt.correct_count += 1 if is_correct else 0
    attempt.current_level = calculate_next_level(aq.assigned_level, is_correct, exam.max_level)
    attempt.last_activity_at = utc_now()
    db.session.add(response)

    from app.integrity_svc.rules import evaluate_response
    evaluate_response(attempt, aq, response)

    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        raise AttemptError("That answer was already recorded.")

    # Remediation: only in the adaptive post-test, only after a wrong answer on a
    # primary question, and never twice in a row (a remedial is not itself
    # remediated — that would let one weak concept dominate the whole test).
    next_aq = None
    wants_remedial = (
        exam.teaches()
        and not is_correct
        and not aq.is_remedial
    )
    if wants_remedial:
        easier = max(0, aq.assigned_level - 1)
        next_aq = assign_next_question(attempt, exam, easier, remedial_for=aq,
                                       concept_id=aq.question.concept_id)

    if next_aq is None and attempt.current_sequence < exam.question_count:
        next_aq = assign_next_question(attempt, exam, attempt.current_level)
    if next_aq is None and attempt.current_sequence <= attempt.total_answered:
        finalise_attempt(attempt, reason="manual" if attempt.current_sequence >= exam.question_count
                         else "administrative")

    audit("answer_saved", "response", response.id, attempt_id=attempt.id, correct=is_correct)
    db.session.commit()
    return response, next_aq


# -------------------------------------------------------------- lifecycle
def expire_if_due(attempt):
    if attempt.status == "active" and utc_now() >= attempt.expires_at:
        finalise_attempt(attempt, reason="time_expired", status="expired")
        db.session.commit()
        return True
    return False


def finalise_attempt(attempt, reason="manual", status="submitted"):
    if attempt.status not in ("active", "created"):
        return attempt
    attempt.status = status
    attempt.submitted_at = utc_now()
    attempt.submission_reason = reason

    from app.exam_engine.scoring_service import score_attempt
    result = score_attempt(attempt)
    attempt.score = result["score_percent"]          # primary-only, comparable pre/post
    attempt.credited_score = result["credited_percent"]
    attempt.readiness_score = result["readiness"]["score"]
    audit("attempt_submitted", "attempt", attempt.id, reason=reason)
    return attempt


def submit_manually(attempt):
    finalise_attempt(attempt, reason="manual")
    db.session.commit()
    return attempt
