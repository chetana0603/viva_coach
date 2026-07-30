"""Cross-bank duplicate detection using the prototype's Jaccard check."""
from app.core.utils import is_duplicate_question
from app.models.question import Question


def find_near_duplicates(question_text, concept_id, threshold=0.7):
    existing = Question.query.filter(
        Question.concept_id == concept_id,
        Question.review_status.in_(("approved", "generated", "draft")),
    ).all()
    return [q for q in existing
            if is_duplicate_question(question_text, [q.question_text], threshold)]
