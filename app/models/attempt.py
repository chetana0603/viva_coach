from datetime import datetime

from app.extensions import db

ATTEMPT_STATUSES = ("created", "active", "expired", "submitted", "cancelled", "invalidated")
SUBMISSION_REASONS = ("manual", "time_expired", "teacher_closed", "administrative",
                      # Ended early because no unused approved question matched any
                      # remaining concept/level — a bank problem, not a student one.
                      "bank_exhausted")


class Attempt(db.Model):
    __tablename__ = "attempts"

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    submitted_at = db.Column(db.DateTime)
    status = db.Column(db.String(16), nullable=False, default="created")

    current_level = db.Column(db.Integer, nullable=False, default=0)
    current_sequence = db.Column(db.Integer, nullable=False, default=0)
    correct_count = db.Column(db.Integer, nullable=False, default=0)
    total_answered = db.Column(db.Integer, nullable=False, default=0)
    score = db.Column(db.Float)              # primary-only %, comparable pre vs post
    credited_score = db.Column(db.Float)     # includes 0.25 remedial recovery credit
    readiness_score = db.Column(db.Integer)
    submission_reason = db.Column(db.String(24))
    last_activity_at = db.Column(db.DateTime, default=datetime.utcnow)
    version = db.Column(db.Integer, nullable=False, default=1)

    exam = db.relationship("Exam")
    user = db.relationship("User")
    assigned = db.relationship("AssignedQuestion", backref="attempt",
                               cascade="all, delete-orphan", lazy="selectin",
                               order_by="AssignedQuestion.sequence_number")

    __table_args__ = (
        db.UniqueConstraint("exam_id", "user_id", name="uq_attempt_exam_user"),
    )

    __mapper_args__ = {"version_id_col": version}


class AssignedQuestion(db.Model):
    """A question locked to an attempt. Refresh must never change this."""
    __tablename__ = "assigned_questions"

    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey("attempts.id"), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    sequence_number = db.Column(db.Integer, nullable=False)
    displayed_option_order = db.Column(db.String(16), nullable=False, default="0,1,2,3")
    assigned_level = db.Column(db.Integer, nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    answered = db.Column(db.Boolean, default=False, nullable=False)

    # A remedial question is a second chance after a wrong answer on the same
    # concept. It is worth partial credit and is excluded from the primary
    # denominator, so it can never inflate the score above a clean run.
    is_remedial = db.Column(db.Boolean, default=False, nullable=False)
    remedial_for_id = db.Column(db.Integer, db.ForeignKey("assigned_questions.id"))

    question = db.relationship("Question")

    __table_args__ = (
        db.UniqueConstraint("attempt_id", "sequence_number", name="uq_assigned_sequence"),
        db.UniqueConstraint("attempt_id", "question_id", name="uq_assigned_once"),
    )

    def order(self):
        return [int(i) for i in self.displayed_option_order.split(",") if i != ""]

    def displayed_options(self):
        opts = self.question.options_list()
        return [opts[i] for i in self.order() if i < len(opts)]

    def displayed_breakdowns(self):
        bl = self.question.breakdown_list()
        return [bl[i] if i < len(bl) else None for i in self.order()]

    def displayed_correct_index(self):
        return self.order().index(self.question.correct_index())
