"""
Automatic checks run on every candidate question before a teacher ever sees it.
Returns a list of problems; an empty list means the question is worth reviewing.
"""
from app.core.text_processing import tokenize
from app.core.utils import is_duplicate_question

BANNED_PHRASES = (
    "according to the above passage", "according to the passage",
    "in the text above", "as mentioned above", "based on the context above",
)


def validate_mcq(mcq, material=None, previous_questions=None, min_grounding=0.10):
    problems = []
    question = (mcq.get("question") or "").strip()
    options = [o for o in (mcq.get("options") or []) if str(o).strip()]

    if len(options) < 4:
        problems.append("Fewer than four options.")

    if len(set(o.strip().lower() for o in options)) != len(options):
        problems.append("Duplicate options.")

    answer = mcq.get("answer")
    if not isinstance(answer, int) or not 0 <= answer < len(options):
        problems.append("Correct answer is not one of the options.")

    if len(question.split()) < 4:
        problems.append("Question is too short to be meaningful.")

    lower_q = question.lower()
    for phrase in BANNED_PHRASES:
        if phrase in lower_q:
            problems.append(f"Refers to a passage the student will not see ('{phrase}').")
            break

    # Question reveals its own answer
    if isinstance(answer, int) and 0 <= answer < len(options):
        correct_tokens = set(tokenize(options[answer])) - {"the", "a", "of", "to", "is"}
        q_tokens = set(tokenize(question))
        if correct_tokens and len(correct_tokens & q_tokens) / len(correct_tokens) > 0.8:
            problems.append("The question text gives away the correct answer.")

    if previous_questions and is_duplicate_question(question, previous_questions):
        problems.append("Near-duplicate of an existing question.")

    # Grounding: does the question share vocabulary with the source material?
    if material:
        m_tokens = {t for t in tokenize(material) if len(t) > 3}
        q_tokens = {t for t in tokenize(question) if len(t) > 3}
        if q_tokens and m_tokens:
            overlap = len(q_tokens & m_tokens) / len(q_tokens)
            if overlap < min_grounding:
                problems.append("Question is not clearly grounded in the source material.")

    return problems
