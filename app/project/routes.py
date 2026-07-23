"""
Student-facing core-system flow:

    submit report -> analyse -> study cards -> generate pool -> adaptive post-test

Each step is a separate request so a slow LLM call never blocks a page load, and
so a failure at one step leaves the earlier work intact.
"""
from flask import (Blueprint, abort, flash, redirect, render_template,
                   request, url_for)
from flask_login import current_user, login_required

from app.auth.decorators import student_required
from app.extensions import db
from app.models.exam import Exam
from app.models.project import ProjectSubmission
from app.project import services
from app.utils.datetime_utils import utc_now
from app.utils.security import audit

project_bp = Blueprint("project", __name__, url_prefix="/student/project")

ALLOWED_EXTS = {".pdf", ".docx", ".txt", ".md", ".py", ".java", ".sql",
                ".c", ".cpp", ".html", ".css", ".js"}


def _own_submission(exam_id):
    exam = db.session.get(Exam, exam_id) or abort(404)
    if not exam.is_project():
        abort(404)
    return exam, services.get_or_create_submission(current_user, exam)


@project_bp.route("/<int:exam_id>")
@login_required
@student_required
def overview(exam_id):
    exam, sub = _own_submission(exam_id)
    return render_template("student/project_overview.html", exam=exam, submission=sub,
                           coverage=services.pool_coverage(sub) if sub.id else {},
                           now=utc_now())


@project_bp.route("/<int:exam_id>/upload", methods=["POST"])
@login_required
@student_required
def upload(exam_id):
    exam, sub = _own_submission(exam_id)
    if sub.status == "questions_ready":
        flash("Your project is already analysed. Re-uploading would change your test.", "warning")
        return redirect(url_for("project.overview", exam_id=exam.id))

    files = [f for f in request.files.getlist("report") if f and f.filename]
    typed = (request.form.get("typed_material") or "").strip()

    if not files and not typed:
        flash("Upload your report or paste its text.", "error")
        return redirect(url_for("project.overview", exam_id=exam.id))

    chunks, names = [], []
    for f in files:
        import os
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in ALLOWED_EXTS:
            flash(f"{f.filename}: unsupported file type — skipped.", "warning")
            continue
        text = services.extract_text(f.filename, f.read())
        if text.strip():
            chunks.append(f"### FILE: {f.filename}\n{text}")
            names.append(f.filename)
    if typed:
        chunks.append(typed)
        names.append("pasted text")

    if not chunks:
        flash("Nothing readable was found in what you submitted.", "error")
        return redirect(url_for("project.overview", exam_id=exam.id))

    sub.title = request.form.get("title") or sub.title
    services.attach_material(sub, names, "\n\n".join(chunks))
    audit("project_submitted", "project_submission", sub.id)
    db.session.commit()
    flash("Report received. Now analyse it to pull out your concepts.", "success")
    return redirect(url_for("project.overview", exam_id=exam.id))


@project_bp.route("/<int:exam_id>/analyse", methods=["POST"])
@login_required
@student_required
def analyse(exam_id):
    exam, sub = _own_submission(exam_id)
    if not (sub.material or "").strip():
        flash("Submit your report first.", "error")
        return redirect(url_for("project.overview", exam_id=exam.id))

    services.analyse_submission(sub)
    if sub.status == "failed":
        flash(sub.error_message or "Analysis failed.", "error")
    else:
        flash(f"Found {len(sub.concepts)} concepts in your project.", "success")
    audit("project_analysed", "project_submission", sub.id)
    db.session.commit()
    return redirect(url_for("project.overview", exam_id=exam.id))


@project_bp.route("/<int:exam_id>/cards", methods=["POST"])
@login_required
@student_required
def build_cards(exam_id):
    exam, sub = _own_submission(exam_id)
    if sub.status not in ("analysed", "cards_ready", "questions_ready"):
        flash("Analyse your report first.", "error")
        return redirect(url_for("project.overview", exam_id=exam.id))

    services.generate_study_cards(sub)
    audit("study_cards_generated", "project_submission", sub.id)
    db.session.commit()
    flash("Study cards ready. Read them before you take the test.", "success")
    return redirect(url_for("project.cards", exam_id=exam.id))


@project_bp.route("/<int:exam_id>/cards")
@login_required
@student_required
def cards(exam_id):
    exam, sub = _own_submission(exam_id)
    if not sub.cards:
        flash("No study cards yet.", "info")
        return redirect(url_for("project.overview", exam_id=exam.id))
    return render_template("student/project_cards.html", exam=exam, submission=sub)


@project_bp.route("/<int:exam_id>/cards/<int:card_id>/viewed", methods=["POST"])
@login_required
@student_required
def mark_viewed(exam_id, card_id):
    exam, sub = _own_submission(exam_id)
    from app.models.project import StudyCard
    card = db.session.get(StudyCard, card_id)
    if card is None or card.submission_id != sub.id:
        abort(404)
    card.viewed_at = utc_now()
    db.session.commit()
    return redirect(url_for("project.cards", exam_id=exam.id))


@project_bp.route("/<int:exam_id>/generate", methods=["POST"])
@login_required
@student_required
def generate_pool(exam_id):
    exam, sub = _own_submission(exam_id)
    if sub.status not in ("cards_ready", "questions_ready"):
        flash("Generate your study cards first.", "error")
        return redirect(url_for("project.overview", exam_id=exam.id))

    _, stats = services.generate_question_pool(sub)
    audit("project_pool_generated", "project_submission", sub.id, **stats)
    db.session.commit()
    flash(f"{stats['created']} questions generated for your project "
          f"({stats['rejected']} rejected by validation). You can start the test.",
          "success")
    return redirect(url_for("project.overview", exam_id=exam.id))
