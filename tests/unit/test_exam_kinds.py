"""The three exam kinds and what each one does."""
from types import SimpleNamespace

from app.models.exam import Exam


def _exam(kind, feedback=False):
    e = Exam(title="t", subject="DBMS", exam_kind=kind, show_inline_feedback=feedback)
    return e


def test_pre_test_does_not_teach():
    e = _exam("pre_test")
    assert not e.teaches()
    assert not e.is_project()


def test_post_test_teaches_from_shared_bank():
    e = _exam("post_test", True)
    assert e.teaches()
    assert not e.is_project(), "post-test must use the shared bank, not a project pool"


def test_project_viva_uses_own_pool():
    e = _exam("project_viva", True)
    assert e.teaches()
    assert e.is_project()


def test_only_project_viva_requires_a_submission():
    assert not _exam("pre_test").is_project()
    assert not _exam("post_test").is_project()
    assert _exam("project_viva").is_project()


def test_evaluation_pair_shares_a_question_source():
    """The comparison is only meaningful if both tests draw the same bank."""
    pre, post = _exam("pre_test"), _exam("post_test", True)
    assert pre.is_project() == post.is_project() is False
    assert pre.subject == post.subject
