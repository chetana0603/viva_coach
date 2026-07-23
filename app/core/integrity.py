"""
integrity.py
------------
Non-video integrity telemetry.

IMPORTANT: This does NOT claim to detect cheating. It produces soft signals for
teacher review only. All thresholds are heuristic and explained in plain language.

Implemented (Python-only, no camera/mic):
  - fast MCQ response (fixed threshold)
  - response-time anomaly vs the student's own baseline (statistical)
  - repeated rapid wrong responses
  - descriptive: repeats-question, timing-inferred paste, too-short
  - answer consistency (hard-correct / easy-wrong inversion)
  - project explanation consistency (answer grounded in uploaded material)

Future work (needs browser JS, documented not implemented):
  - true copy-paste event logging, tab-switch monitoring, face/voice presence.
"""

import statistics

from app.core.text_processing import tokenize, split_sentences

# Heuristic thresholds
FAST_MCQ_SECONDS = 1.5            # answering an MCQ faster than this looks suspicious
FAST_DESCRIPTIVE_CHARS_PER_SEC = 25  # typing speed above this for a long answer looks pasted
MIN_PASTE_LENGTH = 120           # only flag "pasted" on reasonably long answers
ANOMALY_MIN_SAMPLES = 4          # need this many prior answers before a baseline is meaningful
ANOMALY_Z_FAST = 1.8             # z-score below the student's mean => unusually fast
ANOMALY_Z_SLOW = 3.0             # z-score above the student's mean => unusually slow


def check_mcq_response(response_time: float, is_correct: bool, level: int):
    """Return integrity flags for a single MCQ response."""
    flags = []
    if response_time is not None and response_time < FAST_MCQ_SECONDS:
        flags.append("Very fast MCQ response (answered almost instantly)")
    return flags


def check_rapid_wrong_streak(recent_records, window: int = 3):
    """Flag repeated rapid wrong answers across recent MCQ records."""
    flags = []
    recent = [r for r in recent_records if r.get("type", "mcq") == "mcq"][-window:]
    if len(recent) >= window:
        rapid_wrong = [
            r for r in recent
            if not r.get("is_correct", True)
            and (r.get("response_time") or 999) < FAST_MCQ_SECONDS
        ]
        if len(rapid_wrong) >= window:
            flags.append(f"Repeated rapid wrong responses ({len(rapid_wrong)} in a row)")
    return flags


def check_descriptive_answer(question: str, answer: str, response_time: float):
    """
    Analyze a short descriptive answer for integrity signals:
      - answer repeats the question instead of explaining
      - long answer submitted implausibly fast (possible paste)
      - answer far too short to be an explanation
    """
    flags = []
    answer = (answer or "").strip()
    question = (question or "").strip()

    if not answer:
        return ["Empty answer submitted"]

    q_tokens = set(tokenize(question))
    a_tokens = set(tokenize(answer))

    # 1) Repeats the question
    if q_tokens and a_tokens:
        overlap = len(q_tokens & a_tokens) / max(len(a_tokens), 1)
        # remove the instruction words to focus on content overlap
        if overlap > 0.75 and len(a_tokens) <= len(q_tokens) + 3:
            flags.append("Answer repeats the question instead of explaining")

    # 2) Possible pasted response (long answer, very fast)
    if response_time and response_time > 0 and len(answer) >= MIN_PASTE_LENGTH:
        chars_per_sec = len(answer) / response_time
        if chars_per_sec > FAST_DESCRIPTIVE_CHARS_PER_SEC:
            flags.append(
                f"Possible pasted response (long answer typed in {response_time:.1f}s)"
            )

    # 3) Too short to be an explanation
    sentences = split_sentences(answer)
    if len(a_tokens) < 6 or (len(sentences) < 1 and len(a_tokens) < 10):
        flags.append("Answer too short to be a real explanation")

    return flags


def check_response_time_anomaly(response_time, previous_times):
    """
    Compare this response time to the STUDENT'S OWN baseline, not a fixed cutoff.

    A z-score well below the student's mean flags an unusually fast answer for
    this particular student; a very high z-score flags an unusually slow answer
    (possible external lookup). Needs a few prior answers before it activates.
    """
    flags = []
    times = [t for t in (previous_times or []) if t]
    if not response_time or len(times) < ANOMALY_MIN_SAMPLES:
        return flags
    mean = statistics.mean(times)
    stdev = statistics.pstdev(times)
    if stdev <= 0:
        return flags
    z = (response_time - mean) / stdev
    if z < -ANOMALY_Z_FAST:
        flags.append("Response-time anomaly: much faster than this student's usual pace")
    elif z > ANOMALY_Z_SLOW:
        flags.append("Response-time anomaly: much slower than usual (possible external lookup)")
    return flags


def consistency_flags(records):
    """
    Answer consistency check (session-level).

    Flags a concept where the student answered a HARDER question correctly but an
    EASIER question on the same concept incorrectly (a level inversion of >= 2).
    Getting Level 4 right while missing Level 0/1 on the same topic is an
    inconsistency worth a teacher's attention (e.g. selective lookup or guessing).
    """
    flags = []
    mcqs = [r for r in records if r.get("type", "mcq") == "mcq"]
    by_concept = {}
    for r in mcqs:
        by_concept.setdefault(r.get("concept", "Unknown"), []).append(r)

    for concept, rs in by_concept.items():
        correct_levels = [r.get("level", 0) for r in rs if r.get("is_correct")]
        wrong_levels = [r.get("level", 0) for r in rs if not r.get("is_correct")]
        if correct_levels and wrong_levels:
            if max(correct_levels) - min(wrong_levels) >= 2:
                flags.append(
                    f"Inconsistent performance on '{concept}': correct at Level "
                    f"{max(correct_levels)} but wrong at Level {min(wrong_levels)}"
                )
    return flags


def check_project_explanation(answer, material, min_words: int = 15, min_overlap: float = 0.08):
    """
    Project-specific explanation consistency.

    For Project Viva descriptive answers: checks whether the student's explanation
    actually uses vocabulary from THEIR uploaded material. A substantive answer that
    shares almost no terms with the project suggests a generic or copied answer that
    is not grounded in the student's own work.
    """
    flags = []
    answer = (answer or "").strip()
    a_tokens = [t for t in tokenize(answer) if len(t) > 3]
    if len(a_tokens) < min_words:
        return flags  # too short to judge here; other checks cover short answers

    m_tokens = {t for t in tokenize(material or "") if len(t) > 3}
    if not m_tokens:
        return flags

    unique_a = set(a_tokens)
    overlap = len(unique_a & m_tokens) / len(unique_a)
    if overlap < min_overlap:
        flags.append("Explanation not clearly grounded in the uploaded project material")
    return flags


def summarize_flags(records):
    """Aggregate all integrity flags across a session for the teacher console."""
    total = 0
    reasons = {}
    for r in records:
        for f in r.get("integrity_flags", []) or []:
            total += 1
            reasons[f] = reasons.get(f, 0) + 1
    return {"total": total, "reasons": reasons}