import os
import sys
from datetime import timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db as _db
from app.models.exam import Concept, Exam, ExamRegistration
from app.models.question import Question
from app.models.user import User
from app.utils.datetime_utils import utc_now
from app.utils.security import hash_password

PASSWORD = "TestPass123"


@pytest.fixture
def app():
    application = create_app("app.config.TestingConfig")
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def db(app):
    return _db


@pytest.fixture
def client(app):
    return app.test_client()


def make_user(reg, email, role="student", status="active"):
    user = User(register_number=reg, full_name=f"Test {reg}", email=email,
                password_hash=hash_password(PASSWORD), role=role, account_status=status)
    _db.session.add(user)
    _db.session.flush()
    return user


@pytest.fixture
def student(db):
    u = make_user("S001", "s001@college.edu")
    db.session.commit()
    return u


@pytest.fixture
def other_student(db):
    u = make_user("S002", "s002@college.edu")
    db.session.commit()
    return u


@pytest.fixture
def teacher(db):
    u = make_user("T001", "t001@college.edu", role="teacher")
    db.session.commit()
    return u


@pytest.fixture
def exam(db, teacher):
    concept = Concept(subject="DBMS", name="Normalization and Functional Dependencies")
    db.session.add(concept)
    db.session.flush()

    for level in range(4):
        for i in range(6):
            db.session.add(Question(
                subject="DBMS", concept_id=concept.id, level=level, question_type="mcq",
                question_text=f"Level {level} question number {i} about normalization?",
                option_a="Correct answer", option_b="Wrong one", option_c="Wrong two",
                option_d="Wrong three", correct_option="A",
                explanation="Because normalization reduces redundancy.",
                review_status="approved", generation_method="existing_bank",
                fingerprint=f"fp-{level}-{i}",
            ))

    now = utc_now()
    e = Exam(title="DBMS Viva 1", subject="DBMS", created_by=teacher.id,
             registration_start=now - timedelta(days=2), registration_end=now + timedelta(days=1),
             exam_start=now - timedelta(minutes=5), exam_end=now + timedelta(hours=2),
             duration_minutes=30, question_count=5, starting_level=0, max_level=3,
             status="active", show_result_immediately=True)
    db.session.add(e)
    db.session.commit()
    return e


@pytest.fixture
def registered(db, exam, student):
    db.session.add(ExamRegistration(exam_id=exam.id, user_id=student.id, status="approved"))
    db.session.commit()


def login(client, email, password=PASSWORD):
    return client.post("/login", data={"email": email, "password": password},
                       follow_redirects=True)
