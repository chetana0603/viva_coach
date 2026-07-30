from datetime import timedelta

from tests.conftest import PASSWORD, login

from app.exam_engine import attempt_service
from app.models.attempt import Attempt
from app.models.response import Response
from app.utils.datetime_utils import utc_now


def _start(client, exam):
    return client.post(f"/student/exams/{exam.id}/start", follow_redirects=True)


def test_student_can_start_and_answer(client, db, exam, student, registered):
    login(client, student.email)
    _start(client, exam)

    attempt = Attempt.query.filter_by(user_id=student.id, exam_id=exam.id).one()
    assert attempt.status == "active"
    assert len(attempt.assigned) == 1

    aq = attempt.assigned[0]
    client.post(f"/student/attempts/{attempt.id}/answer", data={
        "assigned_question_id": aq.id,
        "selected_option": aq.displayed_correct_index(),
        "client_response_time": "8.0",
    }, follow_redirects=True)

    db.session.refresh(attempt)
    assert attempt.total_answered == 1
    assert attempt.correct_count == 1
    assert attempt.current_level == 1          # correct answer steps up
    assert len(attempt.assigned) == 2          # next question already locked in


def test_second_attempt_is_blocked(client, db, exam, student, registered):
    login(client, student.email)
    _start(client, exam)
    _start(client, exam)   # double click
    assert Attempt.query.filter_by(user_id=student.id, exam_id=exam.id).count() == 1


def test_refresh_returns_the_same_question(client, db, exam, student, registered):
    login(client, student.email)
    _start(client, exam)
    attempt = Attempt.query.filter_by(user_id=student.id).one()

    first = client.get(f"/student/attempts/{attempt.id}").data
    second = client.get(f"/student/attempts/{attempt.id}").data
    marker = f'name="assigned_question_id" value="{attempt.assigned[0].id}"'.encode()
    assert marker in first and marker in second


def test_refresh_does_not_reset_the_timer(client, db, exam, student, registered):
    login(client, student.email)
    _start(client, exam)
    attempt = Attempt.query.filter_by(user_id=student.id).one()
    expiry = attempt.expires_at

    client.get(f"/student/attempts/{attempt.id}")
    db.session.refresh(attempt)
    assert attempt.expires_at == expiry


def test_answering_twice_is_rejected(client, db, exam, student, registered):
    login(client, student.email)
    _start(client, exam)
    attempt = Attempt.query.filter_by(user_id=student.id).one()
    aq = attempt.assigned[0]

    payload = {"assigned_question_id": aq.id, "selected_option": 0, "client_response_time": "5"}
    client.post(f"/student/attempts/{attempt.id}/answer", data=payload, follow_redirects=True)
    client.post(f"/student/attempts/{attempt.id}/answer", data=payload, follow_redirects=True)

    assert Response.query.filter_by(assigned_question_id=aq.id).count() == 1


def test_expired_attempt_rejects_answers(client, db, exam, student, registered):
    login(client, student.email)
    _start(client, exam)
    attempt = Attempt.query.filter_by(user_id=student.id).one()
    aq = attempt.assigned[0]

    attempt.expires_at = utc_now() - timedelta(seconds=1)
    db.session.commit()

    client.post(f"/student/attempts/{attempt.id}/answer", data={
        "assigned_question_id": aq.id, "selected_option": 0, "client_response_time": "5",
    }, follow_redirects=True)

    db.session.refresh(attempt)
    assert attempt.status == "expired"
    assert attempt.submission_reason == "time_expired"
    assert Response.query.filter_by(attempt_id=attempt.id).count() == 0


def test_attempt_ends_after_question_count(client, db, exam, student, registered):
    login(client, student.email)
    _start(client, exam)
    attempt = Attempt.query.filter_by(user_id=student.id).one()

    for _ in range(exam.question_count):
        aq = attempt_service.current_question(attempt)
        if aq is None:
            break
        client.post(f"/student/attempts/{attempt.id}/answer", data={
            "assigned_question_id": aq.id,
            "selected_option": aq.displayed_correct_index(),
            "client_response_time": "6",
        }, follow_redirects=True)
        db.session.refresh(attempt)

    assert attempt.total_answered == exam.question_count
    assert attempt.status == "submitted"
    assert attempt.score == 100.0


def test_answers_survive_logout_and_login(client, db, exam, student, registered):
    login(client, student.email)
    _start(client, exam)
    attempt = Attempt.query.filter_by(user_id=student.id).one()
    aq = attempt.assigned[0]
    client.post(f"/student/attempts/{attempt.id}/answer", data={
        "assigned_question_id": aq.id, "selected_option": aq.displayed_correct_index(),
        "client_response_time": "5"}, follow_redirects=True)

    client.get("/logout", follow_redirects=True)
    login(client, student.email)

    db.session.refresh(attempt)
    assert attempt.total_answered == 1
    assert Response.query.filter_by(attempt_id=attempt.id).count() == 1
