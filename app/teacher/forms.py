from flask_wtf import FlaskForm
from wtforms import (BooleanField, DateTimeLocalField, IntegerField, SelectField,
                     StringField, SubmitField, TextAreaField)
from wtforms.validators import DataRequired, NumberRange


class ExamForm(FlaskForm):
    title = StringField("Exam title", validators=[DataRequired()])
    exam_kind = SelectField("Test type", choices=[
        ("pre_test", "Pre-test — Subject viva, no feedback (baseline)"),
        ("post_test", "Post-test — Subject viva, with explanations + remediation"),
        ("project_viva", "Project viva — questions from the student's own report"),
    ], default="pre_test")
    show_inline_feedback = BooleanField(
        "Show explanations after each answer",
        description="The teaching step. Leave OFF for a pre-test or the baseline "
                    "will teach the student and you cannot separate the effect.")
    subject = SelectField("Subject", choices=[("DBMS", "DBMS"), ("OS", "Operating Systems")])
    description = TextAreaField("Description")
    instructions = TextAreaField("Instructions shown to students")
    registration_start = DateTimeLocalField("Registration opens (IST)", format="%Y-%m-%dT%H:%M")
    registration_end = DateTimeLocalField("Registration closes (IST)", format="%Y-%m-%dT%H:%M")
    exam_start = DateTimeLocalField("Exam window opens (IST)", format="%Y-%m-%dT%H:%M")
    exam_end = DateTimeLocalField("Exam window closes (IST)", format="%Y-%m-%dT%H:%M")
    duration_minutes = IntegerField("Duration per student (minutes)",
                                    validators=[NumberRange(min=5, max=180)], default=30)
    question_count = IntegerField("Questions per attempt",
                                  validators=[NumberRange(min=1, max=60)], default=20)
    starting_level = SelectField("Starting level", coerce=int,
                                 choices=[(i, f"Level {i}") for i in range(6)], default=0)
    max_level = SelectField("Highest level used", coerce=int,
                            choices=[(i, f"Level {i}") for i in range(6)], default=3)
    allow_late_start = BooleanField("Allow late start", default=True)
    show_result_immediately = BooleanField("Show result immediately after submit")
    study_group = StringField(
        "Study group tag (optional)",
        description="Give Test 1 and Test 2 the same tag so a student never sees the same "
                    "question twice across them. Leave blank for a normal exam.",
    )
    status = SelectField("Status", choices=[
        ("draft", "draft"), ("registration_open", "registration_open"),
        ("scheduled", "scheduled"), ("active", "active"),
        ("closed", "closed"), ("cancelled", "cancelled")])
    submit = SubmitField("Save exam")
