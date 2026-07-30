from datetime import timedelta
from types import SimpleNamespace

from app.exam_engine.access_service import determine_exam_access
from app.utils.datetime_utils import utc_now

NOW = utc_now()


def _exam(**kw):
    base = dict(exam_start=NOW - timedelta(minutes=10), exam_end=NOW + timedelta(hours=1),
                duration_minutes=30, allow_late_start=True)
    base.update(kw)
    return SimpleNamespace(**base)


def _user(status="active"):
    return SimpleNamespace(account_status=status)


def _reg(status="approved"):
    return SimpleNamespace(status=status)


def test_inactive_account_blocked():
    assert determine_exam_access(_user("pending"), _exam(), _reg(), None, NOW) == "ACCOUNT_INACTIVE"


def test_unregistered_blocked():
    assert determine_exam_access(_user(), _exam(), None, None, NOW) == "NOT_REGISTERED"


def test_unapproved_registration_blocked():
    assert determine_exam_access(_user(), _exam(), _reg("pending"), None, NOW) == "REGISTRATION_NOT_APPROVED"


def test_before_window_blocked():
    exam = _exam(exam_start=NOW + timedelta(hours=1), exam_end=NOW + timedelta(hours=2))
    assert determine_exam_access(_user(), exam, _reg(), None, NOW) == "EXAM_NOT_STARTED"


def test_after_window_blocked():
    exam = _exam(exam_start=NOW - timedelta(hours=3), exam_end=NOW - timedelta(hours=1))
    assert determine_exam_access(_user(), exam, _reg(), None, NOW) == "EXAM_CLOSED"


def test_submitted_attempt_blocked():
    attempt = SimpleNamespace(status="submitted")
    assert determine_exam_access(_user(), _exam(), _reg(), attempt, NOW) == "ALREADY_SUBMITTED"


def test_active_attempt_resumes():
    attempt = SimpleNamespace(status="active")
    assert determine_exam_access(_user(), _exam(), _reg(), attempt, NOW) == "RESUME_ATTEMPT"


def test_late_start_rejected_when_disallowed():
    exam = _exam(exam_end=NOW + timedelta(minutes=10), allow_late_start=False)
    assert determine_exam_access(_user(), exam, _reg(), None, NOW) == "TOO_LATE_TO_START"


def test_can_start():
    assert determine_exam_access(_user(), _exam(), _reg(), None, NOW) == "CAN_START"
