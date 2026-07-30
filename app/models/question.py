from datetime import datetime

from app.extensions import db

QUESTION_TYPES = ("mcq", "descriptive")
GENERATION_METHODS = ("manual", "llm", "imported", "existing_bank")
REVIEW_STATUSES = ("draft", "generated", "approved", "rejected", "archived")


class Question(db.Model):
    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(32), nullable=False, index=True)
    concept_id = db.Column(db.Integer, db.ForeignKey("concepts.id"), nullable=False, index=True)
    level = db.Column(db.Integer, nullable=False, index=True)
    question_type = db.Column(db.String(16), nullable=False, default="mcq")

    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.Text)
    option_b = db.Column(db.Text)
    option_c = db.Column(db.Text)
    option_d = db.Column(db.Text)
    correct_option = db.Column(db.String(1))  # "A".."D"
    explanation = db.Column(db.Text)
    breakdown_a = db.Column(db.Text)
    breakdown_b = db.Column(db.Text)
    breakdown_c = db.Column(db.Text)
    breakdown_d = db.Column(db.Text)

    source_text = db.Column(db.Text)
    source_document = db.Column(db.String(255))
    generation_method = db.Column(db.String(24), nullable=False, default="manual")
    review_status = db.Column(db.String(16), nullable=False, default="draft", index=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    fingerprint = db.Column(db.String(64), index=True)

    # Set for questions generated from ONE student's project report. These are
    # private to that submission and must never be served to another student.
    submission_id = db.Column(db.Integer, db.ForeignKey("project_submissions.id"),
                              index=True)

    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    concept = db.relationship("Concept")

    # --- helpers -------------------------------------------------------
    LETTERS = ("A", "B", "C", "D")

    def options_list(self):
        return [o for o in (self.option_a, self.option_b, self.option_c, self.option_d) if o]

    def breakdown_list(self):
        return [self.breakdown_a, self.breakdown_b, self.breakdown_c, self.breakdown_d][
            : len(self.options_list())
        ]

    def correct_index(self):
        try:
            return self.LETTERS.index((self.correct_option or "A").upper())
        except ValueError:
            return 0
