"""
Export the raw, per-answer data for a pre/post study group, for re-analysis.

Writes two CSV files into ./study_export/ :
  responses_<group>.csv  one row per answered question (primary AND remedial)
  attempts_<group>.csv   one row per attempt (exam config + stored scores)

No names or e-mails are exported: participants are identified only by their
roster register number (e.g. STUDY07), which is already a pseudonym.

Usage (from the viva_platform folder, with the same .env the app uses):
    python scripts/export_study_data.py                    # lists study groups
    python scripts/export_study_data.py dbms-study-2026    # exports that group
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.attempt import Attempt  # noqa: E402
from app.models.exam import Exam  # noqa: E402

OUT_DIR = "study_export"


def list_groups():
    rows = db.session.query(Exam.study_group, Exam.exam_kind, Exam.id, Exam.title) \
        .filter(Exam.study_group.isnot(None)).order_by(Exam.study_group).all()
    if not rows:
        print("No exams have a study_group tag.")
    for g, kind, eid, title in rows:
        n = Attempt.query.filter_by(exam_id=eid).count()
        print(f"{g:30s} {kind:12s} exam_id={eid:<4d} attempts={n:<4d} {title}")


def cards_read_for(user_id, exam_id):
    try:
        from app.models.project import ProjectSubmission
    except ImportError:
        return ""
    sub = ProjectSubmission.query.filter_by(user_id=user_id, exam_id=exam_id).first()
    if not sub:
        return ""
    return sum(1 for c in sub.cards if c.viewed_at)


def export(group):
    exams = Exam.query.filter_by(study_group=group).all()
    if not exams:
        print(f"No exams found for study group '{group}'.")
        return
    os.makedirs(OUT_DIR, exist_ok=True)
    resp_path = os.path.join(OUT_DIR, f"responses_{group}.csv")
    att_path = os.path.join(OUT_DIR, f"attempts_{group}.csv")

    n_resp = n_att = 0
    with open(resp_path, "w", newline="", encoding="utf-8") as fr, \
            open(att_path, "w", newline="", encoding="utf-8") as fa:
        wr, wa = csv.writer(fr), csv.writer(fa)
        wr.writerow([
            "participant", "exam_id", "exam_kind", "attempt_id", "sequence",
            "question_id", "concept", "question_level", "assigned_level",
            "is_remedial", "remedial_for_sequence", "is_correct", "points",
            "response_time_s", "assigned_at", "answered_at",
        ])
        wa.writerow([
            "participant", "exam_id", "exam_kind", "attempt_id", "status",
            "submission_reason", "started_at", "submitted_at",
            "starting_level", "max_level", "question_count", "show_inline_feedback",
            "stored_primary_score", "stored_credited_score", "stored_readiness",
            "n_primary_answered", "n_remedial_answered", "cards_read",
        ])

        for exam in exams:
            for att in Attempt.query.filter_by(exam_id=exam.id).all():
                pid = att.user.register_number
                seq_of = {aq.id: aq.sequence_number for aq in att.assigned}
                n_primary = n_remedial = 0
                for aq in sorted(att.assigned, key=lambda a: a.sequence_number):
                    r = aq.response
                    if r is None:
                        continue
                    if aq.is_remedial:
                        n_remedial += 1
                    else:
                        n_primary += 1
                    q = aq.question
                    wr.writerow([
                        pid, exam.id, exam.exam_kind, att.id, aq.sequence_number,
                        q.id, q.concept.name if q.concept else "", q.level,
                        aq.assigned_level, int(bool(aq.is_remedial)),
                        seq_of.get(aq.remedial_for_id, ""),
                        int(bool(r.is_correct)), r.points, r.response_time_seconds,
                        aq.assigned_at.isoformat() if aq.assigned_at else "",
                        r.answered_at.isoformat() if r.answered_at else "",
                    ])
                    n_resp += 1
                wa.writerow([
                    pid, exam.id, exam.exam_kind, att.id, att.status,
                    att.submission_reason,
                    att.started_at.isoformat() if att.started_at else "",
                    att.submitted_at.isoformat() if att.submitted_at else "",
                    exam.starting_level, exam.max_level, exam.question_count,
                    int(bool(exam.show_inline_feedback)),
                    att.score, att.credited_score, att.readiness_score,
                    n_primary, n_remedial, cards_read_for(att.user_id, exam.id),
                ])
                n_att += 1

    print(f"Wrote {n_att} attempts  -> {att_path}")
    print(f"Wrote {n_resp} responses -> {resp_path}")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        if len(sys.argv) < 2:
            list_groups()
        else:
            export(sys.argv[1])
