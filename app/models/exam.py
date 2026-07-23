from datetime import datetime

from app.extensions import db

EXAM_STATUSES = ("draft", "registration_open", "scheduled", "active", "closed", "cancelled")
REGISTRATION_STATUSES = ("pending", "approved", "rejected", "cancelled")


class Concept(db.Model):
    __tablename__ = "concepts"

    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(32), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True, nullable=False)

    __table_args__ = (db.UniqueConstraint("subject", "name", name="uq_concept_subject_name"),)

    def __repr__(self):
        return f"<Concept {self.subject}:{self.name}>"


class Exam(db.Model):
    __tablename__ = "exams"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(32), nullable=False)
    description = db.Column(db.Text)
    instructions = db.Column(db.Text)

    registration_start = db.Column(db.DateTime, nullable=False)
    registration_end = db.Column(db.DateTime, nullable=False)
    exam_start = db.Column(db.DateTime, nullable=False)
    exam_end = db.Column(db.DateTime, nullable=False)

    duration_minutes = db.Column(db.Integer, nullable=False, default=30)
    question_count = db.Column(db.Integer, nullable=False, default=20)
    starting_level = db.Column(db.Integer, nullable=False, default=0)
    max_level = db.Column(db.Integer, nullable=False, default=3)
    allow_late_start = db.Column(db.Boolean, default=True, nullable=False)
    show_result_immediately = db.Column(db.Boolean, default=False, nullable=False)

    # pre_test     = Subject viva, approved bank, adaptive, NO feedback (baseline)
    # post_test    = Subject viva, approved bank, adaptive, WITH explanations and
    #                remediation (the core system). Evaluated against pre_test.
    # project_viva = Project viva, questions generated from the student's own
    #                report. A working feature, not part of the evaluation.
    exam_kind = db.Column(db.String(16), nullable=False, default="pre_test", index=True)

    # Show the explanation and per-option breakdown immediately after each answer.
    # This is the teaching step, so it must stay off for the baseline.
    show_inline_feedback = db.Column(db.Boolean, default=False, nullable=False)

    status = db.Column(db.String(24), nullable=False, default="draft")
    # Exams sharing a study_group never reuse a question for the same student across
    # attempts — so a pre-test (Test 1) and post-test (Test 2) with the same tag draw
    # from disjoint questions. Leave blank for a normal standalone exam.
    study_group = db.Column(db.String(64), index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def is_project(self):
        """Draws questions from the student's own submission, not the shared bank."""
        return self.exam_kind == "project_viva"

    def teaches(self):
        """Gives the student explanations and second chances as they go."""
        return self.exam_kind in ("post_test", "project_viva")

    blueprints = db.relationship("ExamBlueprint", backref="exam",
                                 cascade="all, delete-orphan", lazy="selectin")
    exam_concepts = db.relationship("ExamConcept", backref="exam",
                                    cascade="all, delete-orphan", lazy="selectin")
    registrations = db.relationship("ExamRegistration", backref="exam",
                                    cascade="all, delete-orphan", lazy="selectin")


class ExamRegistration(db.Model):
    __tablename__ = "exam_registrations"

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(16), nullable=False, default="pending")
    registered_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    approved_at = db.Column(db.DateTime)
    approved_by = db.Column(db.Integer, db.ForeignKey("users.id"))

    user = db.relationship("User", foreign_keys=[user_id])

    __table_args__ = (db.UniqueConstraint("exam_id", "user_id", name="uq_registration_exam_user"),)


class ExamBlueprint(db.Model):
    """How many questions this exam draws from each concept/level."""
    __tablename__ = "exam_blueprints"

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"), nullable=False)
    concept_id = db.Column(db.Integer, db.ForeignKey("concepts.id"), nullable=False)
    level = db.Column(db.Integer, nullable=False)
    required_count = db.Column(db.Integer, nullable=False, default=1)

    concept = db.relationship("Concept")

    __table_args__ = (
        db.UniqueConstraint("exam_id", "concept_id", "level", name="uq_blueprint_cell"),
    )


class ExamConcept(db.Model):
    """
    Which concepts an exam draws from.

    Replaces the per-level blueprint grid for adaptive exams: the teacher picks
    concepts, the adaptive engine picks the level. Specifying counts per level by
    hand fights the engine, because the level a student sees is decided by how
    they are answering, not in advance.
    """
    __tablename__ = "exam_concepts"

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"), nullable=False, index=True)
    concept_id = db.Column(db.Integer, db.ForeignKey("concepts.id"), nullable=False)

    concept = db.relationship("Concept")

    __table_args__ = (
        db.UniqueConstraint("exam_id", "concept_id", name="uq_exam_concept"),
    )
