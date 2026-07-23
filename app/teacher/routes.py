import csv
import io

from flask import (Blueprint, Response as FlaskResponse, abort, flash, redirect,
                   render_template, request, url_for)
from flask_login import current_user, login_required

from app.auth.decorators import teacher_required
from app.exam_engine.scoring_service import score_attempt
from app.extensions import db
from app.integrity_svc.summary_service import summarize_attempt
from app.models.attempt import Attempt
from app.models.exam import Concept, Exam, ExamBlueprint, ExamConcept, ExamRegistration
from app.models.question import Question
from app.models.user import EligibleStudent, User
from app.teacher.forms import ExamForm
from app.utils.datetime_utils import to_local_input, utc_now
from app.utils.security import audit

teacher_bp = Blueprint("teacher", __name__, url_prefix="/teacher")


@teacher_bp.before_request
@login_required
@teacher_required
def guard():
    pass


@teacher_bp.route("/dashboard")
def dashboard():
    stats = {
        "students": User.query.filter_by(role="student").count(),
        "pending_accounts": User.query.filter_by(role="student", account_status="pending").count(),
        "exams": Exam.query.count(),
        "approved_questions": Question.query.filter_by(review_status="approved").count(),
        "pending_questions": Question.query.filter_by(review_status="generated").count(),
        "attempts": Attempt.query.count(),
    }
    exams = Exam.query.order_by(Exam.exam_start.desc()).limit(10).all()
    return render_template("teacher/dashboard.html", stats=stats, exams=exams)


# ----------------------------------------------------------- accounts
@teacher_bp.route("/students")
def students():
    pending = User.query.filter_by(role="student", account_status="pending").all()
    active = User.query.filter_by(role="student", account_status="active").all()
    roster = EligibleStudent.query.order_by(EligibleStudent.register_number).all()
    return render_template("teacher/students.html", pending=pending, active=active,
                           roster=roster)


@teacher_bp.route("/students/<int:user_id>/<action>", methods=["POST"])
def student_account_action(user_id, action):
    user = db.session.get(User, user_id) or abort(404)
    mapping = {"approve": "active", "reject": "rejected", "suspend": "suspended"}
    if action not in mapping:
        abort(400)
    user.account_status = mapping[action]
    if action == "approve":
        user.approved_at = utc_now()
    audit(f"account_{action}", "user", user.id)
    db.session.commit()
    flash(f"{user.full_name}: account {mapping[action]}.", "success")
    return redirect(url_for("teacher.students"))


@teacher_bp.route("/students/import", methods=["POST"])
def import_students():
    file = request.files.get("roster")
    if not file:
        flash("Choose a CSV file first.", "error")
        return redirect(url_for("teacher.students"))
    reader = csv.DictReader(io.StringIO(file.read().decode("utf-8", errors="ignore")))
    added = 0
    for row in reader:
        reg = (row.get("register_number") or "").strip().upper()
        if not reg or EligibleStudent.query.filter_by(register_number=reg).first():
            continue
        db.session.add(EligibleStudent(
            register_number=reg,
            full_name=(row.get("full_name") or "").strip(),
            email=(row.get("email") or "").strip().lower(),
            department=(row.get("department") or "").strip(),
            section=(row.get("section") or "").strip(),
        ))
        added += 1
    audit("roster_imported", meta_count=added)
    db.session.commit()
    flash(f"Imported {added} eligible students.", "success")
    return redirect(url_for("teacher.students"))


# -------------------------------------------------------------- exams
@teacher_bp.route("/exams")
def exams():
    return render_template("teacher/exams.html",
                           exams=Exam.query.order_by(Exam.exam_start.desc()).all())


@teacher_bp.route("/exams/create", methods=["GET", "POST"])
@teacher_bp.route("/exams/<int:exam_id>/edit", methods=["GET", "POST"])
def edit_exam(exam_id=None):
    exam = db.session.get(Exam, exam_id) if exam_id else None
    form = ExamForm(obj=exam)
    if form.validate_on_submit():
        if exam is None:
            exam = Exam(created_by=current_user.id)
            db.session.add(exam)
        form.populate_obj(exam)

        # A baseline that teaches is not a baseline: if the pre-test showed
        # explanations, the gain would include what that test itself taught.
        if exam.exam_kind == "pre_test" and exam.show_inline_feedback:
            exam.show_inline_feedback = False
            flash("Inline explanations were turned off — a pre-test must not teach, "
                  "or it contaminates the baseline it exists to measure.", "warning")
        if exam.teaches() and not exam.show_inline_feedback:
            flash("This test type usually shows explanations after each answer. "
                  "Turn that on unless you meant otherwise.", "info")

        if exam.exam_end <= exam.exam_start:
            flash("The exam window must end after it starts.", "error")
        elif exam.duration_minutes * 60 > (exam.exam_end - exam.exam_start).total_seconds():
            flash("Duration is longer than the exam window.", "error")
        else:
            db.session.flush()
            audit("exam_saved", "exam", exam.id)
            db.session.commit()
            flash("Exam saved.", "success")
            return redirect(url_for("teacher.exam_blueprint", exam_id=exam.id))
    return render_template("teacher/create_exam.html", form=form, exam=exam,
                           to_local_input=to_local_input)


@teacher_bp.route("/exams/<int:exam_id>/blueprint", methods=["GET", "POST"])
def exam_blueprint(exam_id):
    """
    Concept selection, not a level grid.

    The adaptive engine decides which level a student sees from how they are
    answering, so fixing counts per level in advance would only fight it. The
    teacher chooses which concepts are in scope and how many questions to ask.
    """
    exam = db.session.get(Exam, exam_id) or abort(404)
    concepts = Concept.query.filter_by(subject=exam.subject, active=True).order_by(
        Concept.name).all()

    if request.method == "POST":
        chosen = {int(c) for c in request.form.getlist("concept_ids") if c.isdigit()}
        ExamConcept.query.filter_by(exam_id=exam.id).delete()
        for cid in chosen:
            db.session.add(ExamConcept(exam_id=exam.id, concept_id=cid))

        count = request.form.get("question_count", "")
        if count.isdigit() and 1 <= int(count) <= 60:
            exam.question_count = int(count)

        audit("exam_concepts_saved", "exam", exam.id, concepts=len(chosen))
        db.session.commit()
        flash(f"{len(chosen)} concept(s) selected for this exam.", "success")
        return redirect(url_for("teacher.exam_blueprint", exam_id=exam.id))

    selected = {ec.concept_id for ec in ExamConcept.query.filter_by(exam_id=exam.id).all()}

    # Approved stock per concept, broken down by level, so a thin level is visible
    stock = {}
    for c in concepts:
        by_level = {}
        for q in Question.query.filter_by(concept_id=c.id, review_status="approved",
                                          submission_id=None).all():
            by_level[q.level] = by_level.get(q.level, 0) + 1
        stock[c.id] = {"total": sum(by_level.values()), "by_level": by_level}

    selected_stock = sum(stock[c.id]["total"] for c in concepts if c.id in selected)
    return render_template("teacher/blueprint.html", exam=exam, concepts=concepts,
                           selected=selected, stock=stock,
                           selected_stock=selected_stock,
                           levels=list(range(exam.max_level + 1)))


@teacher_bp.route("/registrations")
def registrations():
    pending = ExamRegistration.query.filter_by(status="pending").all()
    return render_template("teacher/registrations.html", pending=pending)


@teacher_bp.route("/registrations/<int:reg_id>/<action>", methods=["POST"])
def registration_action(reg_id, action):
    reg = db.session.get(ExamRegistration, reg_id) or abort(404)
    if action not in ("approve", "reject"):
        abort(400)
    reg.status = "approved" if action == "approve" else "rejected"
    reg.approved_at = utc_now()
    reg.approved_by = current_user.id
    audit(f"registration_{action}", "exam_registration", reg.id)
    db.session.commit()
    flash("Registration updated.", "success")
    return redirect(url_for("teacher.registrations"))


# ---------------------------------------------------------- questions
@teacher_bp.route("/questions")
def questions():
    status = request.args.get("status", "approved")
    subject = request.args.get("subject", "")
    q = Question.query
    if status:
        q = q.filter_by(review_status=status)
    if subject:
        q = q.filter_by(subject=subject)
    items = q.order_by(Question.concept_id, Question.level).limit(400).all()
    counts = {s: Question.query.filter_by(review_status=s).count()
              for s in ("draft", "generated", "approved", "rejected", "archived")}
    return render_template("teacher/questions.html", items=items, counts=counts,
                           status=status, subject=subject)


@teacher_bp.route("/questions/<int:question_id>/<action>", methods=["POST"])
def question_action(question_id, action):
    question = db.session.get(Question, question_id) or abort(404)
    mapping = {"approve": "approved", "reject": "rejected", "archive": "archived"}
    if action not in mapping:
        abort(400)
    question.review_status = mapping[action]
    question.reviewed_by = current_user.id
    audit(f"question_{action}", "question", question.id)
    db.session.commit()
    flash(f"Question {mapping[action]}.", "success")
    return redirect(request.referrer or url_for("teacher.questions"))


# ------------------------------------------------------------ results
@teacher_bp.route("/exams/<int:exam_id>/attempts")
def exam_attempts(exam_id):
    exam = db.session.get(Exam, exam_id) or abort(404)
    attempts = Attempt.query.filter_by(exam_id=exam.id).all()
    rows = []
    for a in attempts:
        rows.append({"attempt": a, "integrity": summarize_attempt(a.id)})
    return render_template("teacher/results.html", exam=exam, rows=rows)


@teacher_bp.route("/attempts/<int:attempt_id>")
def attempt_detail(attempt_id):
    attempt = db.session.get(Attempt, attempt_id) or abort(404)
    report = score_attempt(attempt)
    return render_template("student/result.html", attempt=attempt, exam=attempt.exam,
                           report=report, integrity=summarize_attempt(attempt.id),
                           show_answers=True, teacher_view=True)


@teacher_bp.route("/attempts/<int:attempt_id>/<action>", methods=["POST"])
def attempt_action(attempt_id, action):
    attempt = db.session.get(Attempt, attempt_id) or abort(404)
    if action == "invalidate":
        attempt.status = "invalidated"
    elif action == "close":
        from app.exam_engine.attempt_service import finalise_attempt
        finalise_attempt(attempt, reason="teacher_closed")
    elif action == "reopen":
        attempt.status = "active"
        attempt.submitted_at = None
    else:
        abort(400)
    audit(f"attempt_{action}", "attempt", attempt.id)
    db.session.commit()
    flash(f"Attempt {action}d.", "success")
    return redirect(url_for("teacher.exam_attempts", exam_id=attempt.exam_id))


@teacher_bp.route("/evaluation")
def evaluation():
    """Pre-test vs post-test — does the system actually improve readiness?"""
    from app.reports.comparison import build_comparison, study_groups
    groups = study_groups()
    group = request.args.get("group") or (groups[0] if groups else None)
    data = build_comparison(group) if group else None
    return render_template("teacher/evaluation.html", groups=groups, group=group, data=data)


@teacher_bp.route("/evaluation.csv")
def evaluation_csv():
    from app.reports.comparison import build_comparison
    group = request.args.get("group", "")
    data = build_comparison(group)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["register_number", "full_name",
                "pre_score_primary", "pre_readiness", "pre_highest_level",
                "post_score_primary", "post_credited_score", "post_readiness",
                "post_highest_level", "recovery_points",
                "score_gain", "readiness_gain", "level_gain",
                "cards_read", "cards_total"])
    for r in data["rows"]:
        pre, post = r["pre"], r["post"]
        w.writerow([
            r["user"].register_number, r["user"].full_name,
            pre["score_percent"] if pre else "",
            pre["readiness"]["score"] if pre else "",
            pre["readiness"]["highest_level"] if pre else "",
            post["score_percent"] if post else "",
            post["credited_percent"] if post else "",
            post["readiness"]["score"] if post else "",
            post["readiness"]["highest_level"] if post else "",
            r.get("recovery", ""),
            r.get("score_gain", ""), r.get("readiness_gain", ""), r.get("level_gain", ""),
            r["cards_read"], r["cards_total"],
        ])
    audit("evaluation_exported", meta_group=group)
    db.session.commit()
    return FlaskResponse(buf.getvalue(), mimetype="text/csv", headers={
        "Content-Disposition": f"attachment; filename=evaluation_{group or 'all'}.csv"})


@teacher_bp.route("/exams/<int:exam_id>/results.csv")
def export_csv(exam_id):
    exam = db.session.get(Exam, exam_id) or abort(404)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["register_number", "full_name", "status", "answered", "correct",
                     "score_percent", "readiness", "highest_level", "avg_response_time",
                     "integrity_flags", "submitted_at_utc"])
    for a in Attempt.query.filter_by(exam_id=exam.id).all():
        report = score_attempt(a)
        rd = report["readiness"]
        writer.writerow([a.user.register_number, a.user.full_name, a.status,
                         a.total_answered, a.correct_count, report["score_percent"],
                         rd["score"], rd["highest_level"], rd["avg_response_time"],
                         summarize_attempt(a.id)["total"],
                         a.submitted_at.isoformat() if a.submitted_at else ""])
    audit("results_exported", "exam", exam.id)
    db.session.commit()
    return FlaskResponse(
        buf.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=exam_{exam.id}_results.csv"},
    )
