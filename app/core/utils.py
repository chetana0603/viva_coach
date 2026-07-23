"""
utils.py
--------
Helper functions: robust JSON extraction from LLM output, duplicate-question
detection, and small formatting helpers.
"""

import json
import random
import re

from app.core.text_processing import tokenize

LEVEL_NAMES = {
    0: "Very Easy",
    1: "Easy",
    2: "Moderate",
    3: "Challenging",
    4: "Hard",
    5: "Expert",
}


def level_name(level: int) -> str:
    return LEVEL_NAMES.get(int(level), f"Level {level}")


def clamp_level(level: int) -> int:
    return max(0, min(5, int(level)))


def extract_json(text: str):
    """
    Extract a JSON object/array from possibly-messy LLM text.

    Handles ```json fences, leading prose, and trailing commentary.
    Returns the parsed object, or None on failure.
    """
    if not text:
        return None

    # Strip code fences
    cleaned = re.sub(r"```(?:json)?", "", text).strip()

    # Direct parse first
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        pass

    # Find the first balanced { } or [ ] block
    for open_c, close_c in (("{", "}"), ("[", "]")):
        start = cleaned.find(open_c)
        if start == -1:
            continue
        depth = 0
        for i in range(start, len(cleaned)):
            if cleaned[i] == open_c:
                depth += 1
            elif cleaned[i] == close_c:
                depth -= 1
                if depth == 0:
                    candidate = cleaned[start:i + 1]
                    try:
                        return json.loads(candidate)
                    except (json.JSONDecodeError, ValueError):
                        break
    return None


def is_duplicate_question(new_q: str, previous_qs, threshold: float = 0.7) -> bool:
    """Jaccard token overlap to avoid asking near-identical questions."""
    if not new_q:
        return False
    new_tokens = set(tokenize(new_q))
    if not new_tokens:
        return False
    for prev in previous_qs or []:
        prev_tokens = set(tokenize(prev))
        if not prev_tokens:
            continue
        overlap = len(new_tokens & prev_tokens)
        union = len(new_tokens | prev_tokens)
        if union and overlap / union >= threshold:
            return True
    return False


def safe_get(d, key, default=None):
    try:
        return d.get(key, default)
    except AttributeError:
        return default


def normalize_mcq(mcq: dict, target_level: int = 0) -> dict:
    """Safely validate, format, and shuffle MCQ payloads including option breakdowns."""
    if not isinstance(mcq, dict):
        return None

    question = str(mcq.get("question", "")).strip()
    if not question:
        return None

    options = mcq.get("options")
    if not isinstance(options, list) or len(options) < 2:
        return None

    options = [str(o).strip() for o in options if str(o).strip()]
    if len(options) < 2:
        return None
    options = options[:4]

    answer = mcq.get("answer")
    if isinstance(answer, str):
        answer_clean = answer.strip()
        idx = None
        if len(answer_clean) == 1 and answer_clean.upper() in "ABCD":
            idx = "ABCD".index(answer_clean.upper())
        else:
            for i, opt in enumerate(options):
                if opt.lower() == answer_clean.lower():
                    idx = i
                    break
        answer = idx
    try:
        answer = int(answer)
    except (TypeError, ValueError):
        answer = 0
    if answer < 0 or answer >= len(options):
        answer = 0

    # Capture the raw option breakdowns before shuffling
    raw_breakdown = mcq.get("options_breakdown", {})

    # Shuffle positions keeping options and their respective individual explanations tied
    order = list(range(len(options)))
    random.shuffle(order)
    
    shuffled_options = [options[i] for i in order]
    shuffled_answer = order.index(answer)
    
    # Remap explanation strings to their new position indices
    shuffled_breakdown = {}
    for new_idx, old_idx in enumerate(order):
        # Handle string or integer keys from LLM output formats
        msg = raw_breakdown.get(str(old_idx)) or raw_breakdown.get(old_idx) or ""
        shuffled_breakdown[new_idx] = str(msg).strip()

    return {
        "question": question,
        "options": shuffled_options,
        "answer": shuffled_answer,
        "explanation": str(mcq.get("explanation", "")).strip() or "Review the concept and try the next question.",
        "options_breakdown": shuffled_breakdown,
        "level": clamp_level(mcq.get("level", target_level)),
    }