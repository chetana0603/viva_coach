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

    # Models sometimes copy the prompt's example shape literally and emit
    # ["A","B","C","D"] as the answers themselves. Those are unusable.
    placeholder = {"a", "b", "c", "d", "option a", "option b", "option c", "option d",
                   "true", "false", "none", "all of the above", "none of the above"}
    letterish = [o for o in options if o.strip().lower() in placeholder]
    if len(letterish) >= 2:
        problems.append("Options are placeholders or labels, not real answers.")

    if any(len(o.strip()) <= 2 for o in options):
        problems.append("An option is too short to be a real answer.")


    answer = mcq.get("answer")
    if not isinstance(answer, int) or not 0 <= answer < len(options):
        problems.append("Correct answer is not one of the options.")

    # --- Distractor quality -------------------------------------------------
    # A question with one real answer and three throwaways is a giveaway, and a
    # bank full of giveaways flattens the difficulty levels the study depends on.
    if isinstance(answer, int) and 0 <= answer < len(options):
        distractors = [o for i, o in enumerate(options) if i != answer]
        correct = options[answer]

        # Length giveaway: the correct answer being much longer than every
        # distractor is the classic test-taking tell.
        if distractors:
            avg_d = sum(len(d) for d in distractors) / len(distractors)
            if len(correct) > 2.5 * avg_d and len(correct) > 40:
                problems.append("Correct answer is far longer than the distractors "
                                "(length gives it away).")

        # Off-topic distractors: an option sharing no vocabulary with the
        # question or the material is filler, not a distractor.
        q_tokens = {t for t in tokenize(question) if len(t) > 3}
        m_tokens = {t for t in tokenize(material or "") if len(t) > 3}
        topical = q_tokens | m_tokens
        if topical:
            off_topic = 0
            for d in distractors:
                d_tokens = {t for t in tokenize(d) if len(t) > 3}
                if d_tokens and not (d_tokens & topical):
                    off_topic += 1
            if off_topic >= 2:
                problems.append(f"{off_topic} distractors share no vocabulary with the "
                                "topic — they read as filler.")

        # Near-identical distractors collapse four options into three (or two).
        stop = {"the", "a", "an", "of", "to", "in", "for", "is", "are"}
        lowered = [set(d.strip().lower().split()) - stop for d in distractors]
        for i in range(len(lowered)):
            for j in range(i + 1, len(lowered)):
                a_t, b_t = lowered[i], lowered[j]
                if a_t and b_t and len(a_t & b_t) / len(a_t | b_t) >= 0.8:
                    problems.append("Two distractors are near-identical.")
                    break
            else:
                continue
            break

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
