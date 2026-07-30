from tests.conftest import login

from app.models.attempt import Attempt


def test_student_cannot_open_teacher_pages(client, exam, student, registered):
    login(client, student.email)
    for path in ("/teacher/dashboard", "/teacher/questions", "/teacher/students",
                 f"/teacher/exams/{exam.id}/attempts"):
        assert client.get(path).status_code == 403


def test_student_cannot_open_another_students_attempt(client, db, exam, student,
                                                      other_student, registered):
    from app.models.exam import ExamRegistration
    db.session.add(ExamRegistration(exam_id=exam.id, user_id=other_student.id, status="approved"))
    db.session.commit()

    login(client, other_student.email)
    client.post(f"/student/exams/{exam.id}/start", follow_redirects=True)
    victim_attempt = Attempt.query.filter_by(user_id=other_student.id).one()
    client.get("/logout", follow_redirects=True)

    login(client, student.email)
    assert client.get(f"/student/attempts/{victim_attempt.id}").status_code == 404
    assert client.get(f"/student/results/{victim_attempt.id}").status_code == 404
    assert client.get(f"/student/api/attempts/{victim_attempt.id}/state").status_code == 404


def test_answer_for_another_attempts_question_is_rejected(client, db, exam, student,
                                                          other_student, registered):
    from app.models.exam import ExamRegistration
    from app.models.response import Response
    db.session.add(ExamRegistration(exam_id=exam.id, user_id=other_student.id, status="approved"))
    db.session.commit()

    login(client, other_student.email)
    client.post(f"/student/exams/{exam.id}/start", follow_redirects=True)
    victim = Attempt.query.filter_by(user_id=other_student.id).one()
    victim_aq_id = victim.assigned[0].id
    client.get("/logout", follow_redirects=True)

    login(client, student.email)
    client.post(f"/student/exams/{exam.id}/start", follow_redirects=True)
    mine = Attempt.query.filter_by(user_id=student.id).one()

    client.post(f"/student/attempts/{mine.id}/answer", data={
        "assigned_question_id": victim_aq_id, "selected_option": 0,
        "client_response_time": "5"}, follow_redirects=True)

    assert Response.query.filter_by(assigned_question_id=victim_aq_id).count() == 0


def test_anonymous_is_redirected_to_login(client, exam):
    resp = client.get("/student/dashboard")
    assert resp.status_code == 302 and "/login" in resp.headers["Location"]


def test_pending_account_cannot_log_in(client, db):
    from tests.conftest import PASSWORD, make_user
    make_user("S900", "pending@college.edu", status="pending")
    db.session.commit()
    resp = client.post("/login", data={"email": "pending@college.edu", "password": PASSWORD},
                       follow_redirects=True)
    assert b"waiting for teacher approval" in resp.data


def test_correct_answer_is_not_sent_to_the_browser(client, db, exam, student, registered):
    login(client, student.email)
    client.post(f"/student/exams/{exam.id}/start", follow_redirects=True)
    attempt = Attempt.query.filter_by(user_id=student.id).one()
    page = client.get(f"/student/attempts/{attempt.id}").data.decode()

    assert "correct_option" not in page
    assert "displayed_correct_index" not in page
    assert attempt.assigned[0].question.explanation not in page


def test_login_error_is_generic(client, student):
    resp = client.post("/login", data={"email": student.email, "password": "wrong-password"},
                       follow_redirects=True)
    assert b"Email or password is incorrect." in resp.data
