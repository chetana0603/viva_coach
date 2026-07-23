"""Server-side exam access decision. Never trust the browser for this."""
from app.utils.datetime_utils import utc_now

MESSAGES = {
    "ACCOUNT_INACTIVE": "Your account is not active yet.",
    "NOT_REGISTERED": "You are not registered for this exam.",
    "REGISTRATION_NOT_APPROVED": "Your registration is waiting for teacher approval.",
    "EXAM_NOT_STARTED": "This exam has not started yet.",
    "EXAM_CLOSED": "This exam is closed.",
    "ALREADY_SUBMITTED": "You have already submitted this exam.",
    "ATTEMPT_INVALIDATED": "This attempt was invalidated. Contact your teacher.",
    "TOO_LATE_TO_START": "It is too late to start — not enough time remains for the full duration.",
    "RESUME_ATTEMPT": "Resuming your attempt.",
    "CAN_START": "You can start this exam.",
}


def determine_exam_access(user, exam, registration, attempt, current_time=None):
    now = current_time or utc_now()

    if user.account_status != "active":
        return "ACCOUNT_INACTIVE"
    if not registration:
        return "NOT_REGISTERED"
    if registration.status != "approved":
        return "REGISTRATION_NOT_APPROVED"
    if now < exam.exam_start:
        return "EXAM_NOT_STARTED"
    if now >= exam.exam_end:
        return "EXAM_CLOSED"
    if attempt and attempt.status == "invalidated":
        return "ATTEMPT_INVALIDATED"
    if attempt and attempt.status in ("submitted", "expired"):
        return "ALREADY_SUBMITTED"
    if attempt and attempt.status == "active":
        return "RESUME_ATTEMPT"
    if not exam.allow_late_start:
        latest_start = exam.exam_end - _duration(exam)
        if now > latest_start:
            return "TOO_LATE_TO_START"
    return "CAN_START"


def _duration(exam):
    from datetime import timedelta
    return timedelta(minutes=exam.duration_minutes)
