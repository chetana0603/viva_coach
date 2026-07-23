"""Cross-test question exclusion for pre/post studies."""
from datetime import timedelta

import pytest

from tests.conftest import PASSWORD, login, make_user

from app.exam_engine import attempt_service
from app.extensions import db as _db
from app.models.attempt import Attempt
from app.models.exam import Concept, Exam, ExamRegistration
from app.models.question import Question
from app.utils.datetime_utils import utc_now


def _make_study_exam(title, study_group, concept_id, subject="DBMS"):
    now = utc_now()
    e = Exam(title=title, subject=subject, created_by=1,
             registration_start=now - timedelta(days=2), registration_end=now + timedelta(days=5),
             exam_start=now - timedelta(minutes=5), exam_end=now + timedelta(days=3),
             duration_minutes=30, question_count=6, starting_level=0, max_level=3,
             status="active", show_result_immediately=True, study_group=study_group)
    _db.session.add(e)
    _db.session.commit()
    return e


def _answer_all(client, attempt, always_correct=False):
    while True:
        _db.session.refresh(attempt)
        aq = attempt_service.current_question(attempt)
        if aq is None:
            break
        opt = aq.displayed_correct_index() if always_correct else 0
        client.post(f"/student/attempts/{attempt.id}/answer", data={
            "assigned_question_id": aq.id, "selected_option": opt,
            "client_response_time": "6"}, follow_redirects=True)


def test_test2_never_reuses_a_test1_question(client, db, teacher, student):
    # A concept with plenty of questions at every level so both tests can fill up
    concept = Concept(subject="DBMS", name="Big Concept")
    db.session.add(concept)
    db.session.flush()
    for level in range(4):
        for i in range(10):
            db.session.add(Question(
                subject="DBMS", concept_id=concept.id, level=level, question_type="mcq",
                question_text=f"L{level} Q{i} big concept?",
                option_a="Right", option_b="W1", option_c="W2", option_d="W3",
                correct_option="A", explanation="x", review_status="approved",
                generation_method="existing_bank", fingerprint=f"big-{level}-{i}"))
    db.session.commit()

    test1 = _make_study_exam("Test 1", "study-alpha", concept.id)
    test2 = _make_study_exam("Test 2", "study-alpha", concept.id)
    for exam in (test1, test2):
        db.session.add(ExamRegistration(exam_id=exam.id, user_id=student.id, status="approved"))
    db.session.commit()

    login(client, student.email)

    # Take Test 1 fully
    client.post(f"/student/exams/{test1.id}/start", follow_redirects=True)
    a1 = Attempt.query.filter_by(user_id=student.id, exam_id=test1.id).one()
    _answer_all(client, a1)
    test1_qids = {aq.question_id for aq in a1.assigned}

    # Take Test 2 fully
    client.post(f"/student/exams/{test2.id}/start", follow_redirects=True)
    a2 = Attempt.query.filter_by(user_id=student.id, exam_id=test2.id).one()
    _answer_all(client, a2)
    test2_qids = {aq.question_id for aq in a2.assigned}

    assert test1_qids, "Test 1 assigned no questions"
    assert test2_qids, "Test 2 assigned no questions"
    assert test1_qids.isdisjoint(test2_qids), (
        f"Test 2 reused questions from Test 1: {test1_qids & test2_qids}")


def test_no_study_group_allows_reuse_across_exams(client, db, teacher, student):
    concept = Concept(subject="DBMS", name="Small Concept")
    db.session.add(concept)
    db.session.flush()
    # Only 6 questions total, so without exclusion the second exam must reuse some
    for level in range(2):
        for i in range(3):
            db.session.add(Question(
                subject="DBMS", concept_id=concept.id, level=level, question_type="mcq",
                question_text=f"L{level} Q{i} small?",
                option_a="Right", option_b="W1", option_c="W2", option_d="W3",
                correct_option="A", explanation="x", review_status="approved",
                generation_method="existing_bank", fingerprint=f"small-{level}-{i}"))
    db.session.commit()

    e1 = _make_study_exam("Plain 1", None, concept.id)
    e2 = _make_study_exam("Plain 2", None, concept.id)
    for exam in (e1, e2):
        db.session.add(ExamRegistration(exam_id=exam.id, user_id=student.id, status="approved"))
    db.session.commit()

    login(client, student.email)
    client.post(f"/student/exams/{e1.id}/start", follow_redirects=True)
    a1 = Attempt.query.filter_by(user_id=student.id, exam_id=e1.id).one()
    _answer_all(client, a1)
    client.post(f"/student/exams/{e2.id}/start", follow_redirects=True)
    a2 = Attempt.query.filter_by(user_id=student.id, exam_id=e2.id).one()
    _answer_all(client, a2)

    q1 = {aq.question_id for aq in a1.assigned}
    q2 = {aq.question_id for aq in a2.assigned}
    # With no study_group and a tiny bank, reuse is allowed (and expected)
    assert q1 and q2
