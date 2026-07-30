"""Project submission model behaviour (no LLM calls)."""
from app.models.project import ProjectSubmission, StudyCard


def test_concepts_roundtrip(db):
    sub = ProjectSubmission(user_id=1, subject="DBMS", status="draft")
    sub.concepts = ["Login Module", "Database Layer"]
    sub.technologies = ["Python", "SQLite"]
    assert sub.concepts == ["Login Module", "Database Layer"]
    assert sub.technologies == ["Python", "SQLite"]


def test_empty_json_fields_are_safe():
    sub = ProjectSubmission(user_id=1, subject="DBMS")
    assert sub.concepts == []
    assert sub.technologies == []


def test_ready_for_test_only_when_questions_generated():
    sub = ProjectSubmission(user_id=1, subject="DBMS")
    for status in ("draft", "submitted", "analysed", "cards_ready"):
        sub.status = status
        assert not sub.ready_for_test()
    sub.status = "questions_ready"
    assert sub.ready_for_test()


def test_revision_points_roundtrip():
    card = StudyCard(submission_id=1, concept_name="X")
    card.revision_points = ["a", "b", "c"]
    assert card.revision_points == ["a", "b", "c"]
