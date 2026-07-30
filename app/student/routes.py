from flask import (Blueprint, abort, flash, jsonify, redirect, render_template,
                   request, url_for)
from flask_login import current_user, login_required

from app.auth.decorators import student_required
from app.exam_engine import attempt_service
from app.exam_engine.access_service import MESSAGES, determine_exam_access
from app.exam_engine.scoring_service import score_attempt
from app.extensions import db
from app.integrity_svc.rules import CLIENT_EVENT_TYPES, record_event
from app.integrity_svc.summary_service import summarize_attempt
from app.models.exam import Exam, ExamRegistration
from app.models.attempt import Attempt
from app.utils.datetime_utils import utc_now
from app.utils.security import audit

student_bp = Blueprint("student", __name__, url_prefix="/student")


def _own_attempt_or_404(attempt_id):
    attempt = db.session.get(Attempt, attempt_id)
    if attempt is None or attempt.user_id != current_user.id:
        abort(404)   # 404, not 403 — do not confirm that another student's ID exists
    return attempt


@student_bp.route("/dashboard")
@login_required
@student_required
def dashboard():
    exams = Exam.query.filter(Exam.status != "draft").order_by(Exam.exam_start.desc()).all()
    rows = []
    for exam in exams:
        reg = ExamRegistration.query.filter_by(exam_id=exam.id, user_id=current_user.id).first()
        attempt = attempt_service.get_attempt(current_user.id, exam.id)
        rows.append({"exam": exam, "registration": reg, "attempt": attempt,
                     "access": determine_exam_access(current_user, exam, reg, attempt)})
    return render_template("student/dashboard.html", rows=rows, now=utc_now())


@student_bp.route("/exams/<int:exam_id>/register", methods=["POST"])
@login_required
@student_required
def register_for_exam(exam_id):
    exam = db.session.get(Exam, exam_id) or abort(404)
    now = utc_now()
    if not (exam.registration_start <= now <= exam.registration_end):
        flash("Registration for this exam is not open.", "error")
        return redirect(url_for("student.dashboard"))
    if ExamRegistration.query.filter_by(exam_id=exam.id, user_id=current_user.id).first():
        flash("You are already registered.", "info")
        return redirect(url_for("student.dashboard"))

    db.session.add(ExamRegistration(exam_id=exam.id, user_id=current_user.id, status="pending"))
    audit("exam_registered", "exam", exam.id)
    db.session.commit()
    flash("Registered. Your teacher will approve it.", "success")
    return redirect(url_for("student.dashboard"))


@student_bp.route("/exams/<int:exam_id>")
@login_required
@student_required
def exam_detail(exam_id):
    exam = db.session.get(Exam, exam_id) or abort(404)
    reg = ExamRegistration.query.filter_by(exam_id=exam.id, user_id=current_user.id).first()
    attempt = attempt_service.get_attempt(current_user.id, exam.id)
    if attempt:
        attempt_service.expire_if_due(attempt)
    access = determine_exam_access(current_user, exam, reg, attempt)

    project_ready = True
    if exam.is_project():
        from app.models.project import ProjectSubmission
        sub = ProjectSubmission.query.filter_by(
            user_id=current_user.id, exam_id=exam.id).first()
        project_ready = bool(sub and sub.ready_for_test())

    return render_template("student/exam_waiting.html", exam=exam, registration=reg,
                           attempt=attempt, access=access, message=MESSAGES.get(access, ""),
                           project_ready=project_ready, now=utc_now())


@student_bp.route("/exams/<int:exam_id>/start", methods=["POST"])
@login_required
@student_required
def start_exam(exam_id):
    exam = db.session.get(Exam, exam_id) or abort(404)
    reg = ExamRegistration.query.filter_by(exam_id=exam.id, user_id=current_user.id).first()
    attempt = attempt_service.get_attempt(current_user.id, exam.id)
    access = determine_exam_access(current_user, exam, reg, attempt)

    if access == "RESUME_ATTEMPT":
        return redirect(url_for("student.exam_page", attempt_id=attempt.id))
    if access != "CAN_START":
        flash(MESSAGES.get(access, "You cannot start this exam."), "error")
        return redirect(url_for("student.exam_detail", exam_id=exam.id))

    if exam.is_project():
        from app.models.project import ProjectSubmission
        sub = ProjectSubmission.query.filter_by(
            user_id=current_user.id, exam_id=exam.id).first()
        if not (sub and sub.ready_for_test()):
            flash("Finish your project submission and generate your questions first.", "error")
            return redirect(url_for("project.overview", exam_id=exam.id))

    try:
        attempt = attempt_service.start_attempt(current_user, exam)
    except attempt_service.AttemptError as e:
        flash(str(e), "error")
        return redirect(url_for("student.exam_detail", exam_id=exam.id))
    return redirect(url_for("student.exam_page", attempt_id=attempt.id))


@student_bp.route("/attempts/<int:attempt_id>")
@login_required
@student_required
def exam_page(attempt_id):
    attempt = _own_attempt_or_404(attempt_id)
    attempt_service.expire_if_due(attempt)
    if attempt.status != "active":
        return redirect(url_for("student.submitted", attempt_id=attempt.id))

    aq = attempt_service.current_question(attempt)
    if aq is None:
        attempt_service.submit_manually(attempt)
        return redirect(url_for("student.submitted", attempt_id=attempt.id))

    seconds_left = max(0, int((attempt.expires_at - utc_now()).total_seconds()))
    return render_template("student/exam.html", attempt=attempt, exam=attempt.exam,
                           aq=aq, options=aq.displayed_options(),
                           seconds_left=seconds_left)


@student_bp.route("/attempts/<int:attempt_id>/answer", methods=["POST"])
@login_required
@student_required
def answer(attempt_id):
    attempt = _own_attempt_or_404(attempt_id)
    answered_id = request.form.get("assigned_question_id")
    try:
        attempt_service.submit_answer(
            attempt, attempt.exam, answered_id,
            request.form.get("selected_option"),
            request.form.get("client_response_time"),
        )
    except attempt_service.AttemptError as e:
        flash(str(e), "error")
        return redirect(url_for("student.exam_page", attempt_id=attempt.id))

    # In a teaching exam the explanation is the point, so it is shown before the
    # next question rather than saved for the end.
    if attempt.exam.show_inline_feedback and answered_id:
        return redirect(url_for("student.feedback", attempt_id=attempt.id,
                                assigned_question_id=answered_id))
    return redirect(url_for("student.exam_page", attempt_id=attempt.id))


@student_bp.route("/attempts/<int:attempt_id>/feedback/<int:assigned_question_id>")
@login_required
@student_required
def feedback(attempt_id, assigned_question_id):
    """The learning screen: what the right answer was, and why each option was wrong."""
    attempt = _own_attempt_or_404(attempt_id)
    if not attempt.exam.show_inline_feedback:
        return redirect(url_for("student.exam_page", attempt_id=attempt.id))

    from app.models.attempt import AssignedQuestion
    aq = db.session.get(AssignedQuestion, assigned_question_id)
    if aq is None or aq.attempt_id != attempt.id or aq.response is None:
        abort(404)

    options = aq.displayed_options()
    breakdowns = aq.displayed_breakdowns()
    correct_index = aq.displayed_correct_index()

    next_aq = attempt_service.current_question(attempt)
    seconds_left = max(0, int((attempt.expires_at - utc_now()).total_seconds()))

    return render_template(
        "student/feedback.html", attempt=attempt, exam=attempt.exam, aq=aq,
        response=aq.response, options=options, breakdowns=breakdowns,
        correct_index=correct_index, has_next=next_aq is not None,
        seconds_left=seconds_left,
    )


@student_bp.route("/attempts/<int:attempt_id>/submit", methods=["POST"])
@login_required
@student_required
def submit(attempt_id):
    attempt = _own_attempt_or_404(attempt_id)
    if attempt.status == "active":
        attempt_service.submit_manually(attempt)
    return redirect(url_for("student.submitted", attempt_id=attempt.id))


@student_bp.route("/attempts/<int:attempt_id>/submitted")
@login_required
@student_required
def submitted(attempt_id):
    attempt = _own_attempt_or_404(attempt_id)
    return render_template("student/submitted.html", attempt=attempt, exam=attempt.exam)


@student_bp.route("/results/<int:attempt_id>")
@login_required
@student_required
def result(attempt_id):
    attempt = _own_attempt_or_404(attempt_id)
    if attempt.status == "active":
        return redirect(url_for("student.exam_page", attempt_id=attempt.id))
    if not attempt.exam.show_result_immediately and attempt.exam.exam_end > utc_now():
        flash("Results open after the exam window closes.", "info")
        return redirect(url_for("student.dashboard"))

    report = score_attempt(attempt)
    return render_template("student/result.html", attempt=attempt, exam=attempt.exam,
                           report=report, integrity=summarize_attempt(attempt.id),
                           show_answers=True)


@student_bp.route("/study/<subject>")
@login_required
@student_required
def study_cards(subject):
    """
    Subject study cards — the teaching material between pre-test and post-test.
    Generated once per concept from the subject notes and shared by everyone;
    per-student copies would spend API quota on identical content.
    """
    from app.models.project import StudyCard
    cards = StudyCard.query.filter(
        StudyCard.submission_id.is_(None),
        StudyCard.subject == subject.upper(),
    ).order_by(StudyCard.concept_name).all()
    return render_template("student/subject_cards.html", subject=subject.upper(),
                           cards=cards)


# ------------------------------------------------------------------ API
@student_bp.route("/api/attempts/<int:attempt_id>/state")
@login_required
@student_required
def attempt_state(attempt_id):
    attempt = _own_attempt_or_404(attempt_id)
    attempt_service.expire_if_due(attempt)
    return jsonify({
        "status": attempt.status,
        "seconds_left": max(0, int((attempt.expires_at - utc_now()).total_seconds())),
        "answered": attempt.total_answered,
        "total": attempt.exam.question_count,
    })


@student_bp.route("/api/attempts/<int:attempt_id>/events", methods=["POST"])
@login_required
@student_required
def log_event(attempt_id):
    attempt = _own_attempt_or_404(attempt_id)
    payload = request.get_json(silent=True) or {}
    event_type = payload.get("event_type")
    if event_type not in CLIENT_EVENT_TYPES:
        return jsonify({"error": "unknown event"}), 400
    record_event(attempt.id, event_type, str(payload.get("value") or "")[:255])
    db.session.commit()
    return jsonify({"recorded": True})
