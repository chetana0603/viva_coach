"""
Project Viva models.

The core system's flow, persisted: a student submits their project report, the
engine extracts concepts and technologies, builds study cards from the material,
and pre-generates an adaptive question pool grounded in that same material.

Questions generated here are scoped to ONE submission and never appear in another
student's test.
"""
import json
from datetime import datetime

from app.extensions import db

SUBMISSION_STATUSES = (
    "draft",          # created, no material yet
    "submitted",      # material uploaded, not yet analysed
    "analysed",       # concepts + technologies extracted
    "cards_ready",    # study cards generated — student can study
    "questions_ready",  # adaptive pool generated — student can take the test
    "failed",
)


class ProjectSubmission(db.Model):
    __tablename__ = "project_submissions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"), index=True)

    title = db.Column(db.String(200))
    subject = db.Column(db.String(32), nullable=False, default="DBMS")
    source_filenames = db.Column(db.Text)      # newline-joined
    material = db.Column(db.Text)              # extracted plain text of the report

    concepts_json = db.Column(db.Text)         # ["Login Module", ...]
    technologies_json = db.Column(db.Text)     # ["Python", "SQLite", ...]

    status = db.Column(db.String(24), nullable=False, default="draft")
    error_message = db.Column(db.Text)
    generation_source = db.Column(db.String(24))   # "AI" or "Offline"

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    analysed_at = db.Column(db.DateTime)
    questions_generated_at = db.Column(db.DateTime)

    user = db.relationship("User")
    exam = db.relationship("Exam")
    cards = db.relationship("StudyCard", backref="submission",
                            cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (
        db.UniqueConstraint("user_id", "exam_id", name="uq_submission_user_exam"),
    )

    # --- convenience -------------------------------------------------
    @property
    def concepts(self):
        try:
            return json.loads(self.concepts_json or "[]")
        except ValueError:
            return []

    @concepts.setter
    def concepts(self, value):
        self.concepts_json = json.dumps(list(value or []))

    @property
    def technologies(self):
        try:
            return json.loads(self.technologies_json or "[]")
        except ValueError:
            return []

    @technologies.setter
    def technologies(self, value):
        self.technologies_json = json.dumps(list(value or []))

    def ready_for_test(self):
        return self.status == "questions_ready"


class StudyCard(db.Model):
    """
    One Learn-Mode card per concept.

    Two flavours share this table:
      - submission_id set  -> private card built from one student's project
      - submission_id NULL -> shared subject card (e.g. DBMS), built once from
        the subject notes and shown to every student between pre- and post-test
    """
    __tablename__ = "study_cards"

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("project_submissions.id"),
                              nullable=True, index=True)
    subject = db.Column(db.String(32), index=True)   # set for shared subject cards
    concept_name = db.Column(db.String(200), nullable=False)

    definition = db.Column(db.Text)
    purpose = db.Column(db.Text)
    where_used = db.Column(db.Text)
    recommended_answer = db.Column(db.Text)
    misconception = db.Column(db.Text)
    revision_points_json = db.Column(db.Text)
    retrieved_context = db.Column(db.Text)
    source = db.Column(db.String(32))          # "AI (grounded)" / "Offline (context-grounded)"

    viewed_at = db.Column(db.DateTime)         # did the student actually open it?
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("submission_id", "concept_name", name="uq_card_submission_concept"),
        db.Index("ix_card_subject_concept", "subject", "concept_name"),
    )

    @property
    def revision_points(self):
        try:
            return json.loads(self.revision_points_json or "[]")
        except ValueError:
            return []

    @revision_points.setter
    def revision_points(self, value):
        self.revision_points_json = json.dumps(list(value or []))
