"""
Pre-test vs post-test comparison — the evaluation of the system itself.

Pairs each student's baseline attempt with their post-test attempt and reports the
change. Comparison uses the PRIMARY score (first-attempt questions only), because
the pre-test has no remediation: crediting the post-test for a recovery mechanic
the pre-test never offered would manufacture a gain that isn't learning.
"""
from app.exam_engine.scoring_service import score_attempt
from app.extensions import db
from app.models.attempt import Attempt
from app.models.exam import Exam
from app.models.project import ProjectSubmission


def _finished(attempt):
    return attempt is not None and attempt.status in ("submitted", "expired")


def build_comparison(study_group):
    """Return per-student rows plus aggregate gains for one study group."""
    exams = Exam.query.filter_by(study_group=study_group).all()
    pre = next((e for e in exams if e.exam_kind == "pre_test"), None)
    post = next((e for e in exams if e.exam_kind == "post_test"), None)
    if pre is None or post is None:
        return {"pre": pre, "post": post, "rows": [], "summary": None,
                "error": "This study group needs one pre-test and one post-test."}

    pre_attempts = {a.user_id: a for a in Attempt.query.filter_by(exam_id=pre.id).all()}
    post_attempts = {a.user_id: a for a in Attempt.query.filter_by(exam_id=post.id).all()}

    rows = []
    for user_id in sorted(set(pre_attempts) | set(post_attempts)):
        a_pre, a_post = pre_attempts.get(user_id), post_attempts.get(user_id)
        user = (a_pre or a_post).user

        pre_report = score_attempt(a_pre) if _finished(a_pre) else None
        post_report = score_attempt(a_post) if _finished(a_post) else None

        submission = ProjectSubmission.query.filter_by(
            user_id=user_id, exam_id=post.id).first()
        cards_read = sum(1 for c in submission.cards if c.viewed_at) if submission else 0

        row = {
            "user": user,
            "pre": pre_report,
            "post": post_report,
            "cards_total": len(submission.cards) if submission else 0,
            "cards_read": cards_read,
            "complete": bool(pre_report and post_report),
        }
        if row["complete"]:
            row["score_gain"] = round(post_report["score_percent"] - pre_report["score_percent"], 1)
            row["readiness_gain"] = (post_report["readiness"]["score"]
                                     - pre_report["readiness"]["score"])
            row["level_gain"] = (post_report["readiness"]["highest_level"]
                                 - pre_report["readiness"]["highest_level"])
            row["recovery"] = post_report["points"]["recovery_points"]
        rows.append(row)

    done = [r for r in rows if r["complete"]]
    summary = None
    if done:
        n = len(done)
        summary = {
            "n": n,
            "n_partial": len(rows) - n,
            "mean_score_gain": round(sum(r["score_gain"] for r in done) / n, 1),
            "mean_readiness_gain": round(sum(r["readiness_gain"] for r in done) / n, 1),
            "mean_level_gain": round(sum(r["level_gain"] for r in done) / n, 2),
            "improved": sum(1 for r in done if r["score_gain"] > 0),
            "unchanged": sum(1 for r in done if r["score_gain"] == 0),
            "declined": sum(1 for r in done if r["score_gain"] < 0),
        }
    return {"pre": pre, "post": post, "rows": rows, "summary": summary, "error": None}


def study_groups():
    return sorted({e.study_group for e in Exam.query.all() if e.study_group})
