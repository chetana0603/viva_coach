from datetime import datetime

from app.extensions import db


class Response(db.Model):
    __tablename__ = "responses"

    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey("attempts.id"), nullable=False, index=True)
    assigned_question_id = db.Column(db.Integer, db.ForeignKey("assigned_questions.id"),
                                     nullable=False)
    selected_option = db.Column(db.Integer)          # index into displayed options
    descriptive_answer = db.Column(db.Text)
    is_correct = db.Column(db.Boolean)
    # 1.0 correct on a primary question, 0.25 correct on a remedial, 0 wrong.
    points = db.Column(db.Float, default=0.0, nullable=False)
    response_time_seconds = db.Column(db.Float)
    answered_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    saved_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    finalised = db.Column(db.Boolean, default=True, nullable=False)

    assigned_question = db.relationship("AssignedQuestion", backref=db.backref("response", uselist=False))

    __table_args__ = (
        db.UniqueConstraint("assigned_question_id", name="uq_response_per_assigned_question"),
    )
