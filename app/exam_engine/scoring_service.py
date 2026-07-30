"""Bridges saved DB rows into the prototype's scoring module unchanged."""
from app.core import scoring
from app.core.utils import clamp_level
from app.extensions import db
from app.models.integrity_event import IntegrityEvent

# Credit model
POINTS_CORRECT = 1.0        # right first time
POINTS_REMEDIAL = 0.25      # right on the second-chance question after a miss
POINTS_WRONG = 0.0


def award_points(is_correct: bool, is_remedial: bool) -> float:
    if not is_correct:
        return POINTS_WRONG
    return POINTS_REMEDIAL if is_remedial else POINTS_CORRECT


def attempt_records(attempt):
    """Rebuild the prototype's record dicts from the database."""
    records = []
    events = db.session.query(IntegrityEvent).filter_by(attempt_id=attempt.id).all()
    flags_by_seq = {}
    for e in events:
        try:
            seq = int((e.event_value or "").split("#")[-1])
        except ValueError:
            seq = 0
        flags_by_seq.setdefault(seq, []).append(e.event_type)

    for aq in attempt.assigned:
        r = aq.response
        if r is None:
            continue
        displayed = aq.displayed_options()
        records.append({
            "type": "mcq",
            "concept": aq.question.concept.name if aq.question.concept else "Unknown",
            "level": clamp_level(aq.assigned_level),
            "question": aq.question.question_text,
            "options": displayed,
            "selected": r.selected_option,
            "selected_text": displayed[r.selected_option] if r.selected_option is not None
                             and r.selected_option < len(displayed) else "",
            "answer": aq.displayed_correct_index(),
            "correct_text": displayed[aq.displayed_correct_index()],
            "is_correct": bool(r.is_correct),
            "is_remedial": bool(aq.is_remedial),
            "points": r.points if r.points is not None else award_points(r.is_correct, aq.is_remedial),
            "explanation": aq.question.explanation or "",
            "options_breakdown": {i: (b or "") for i, b in enumerate(aq.displayed_breakdowns())},
            "response_time": r.response_time_seconds,
            "next_level": clamp_level(aq.assigned_level + (1 if r.is_correct else -1)),
            "integrity_flags": flags_by_seq.get(aq.sequence_number, []),
        })
    return records


def points_summary(records):
    """
    Two scores, deliberately.

    `primary_percent` counts only first-attempt questions. It is the score to use
    when comparing a pre-test against a post-test, because the pre-test has no
    remediation and so cannot earn recovery credit — scoring the post-test with a
    mechanic the pre-test never offered would inflate the apparent gain.

    `credited_percent` adds the 0.25 recovery credit. It measures how much a
    student recovered *during* the test after seeing an explanation, which is a
    real signal about the teaching — just not the one to run the comparison on.
    """
    primary = [r for r in records if not r.get("is_remedial")]
    remedial = [r for r in records if r.get("is_remedial")]

    denominator = len(primary)
    primary_points = sum(POINTS_CORRECT for r in primary if r["is_correct"])
    recovery_points = sum(POINTS_REMEDIAL for r in remedial if r["is_correct"])

    return {
        "primary_total": denominator,
        "primary_correct": sum(1 for r in primary if r["is_correct"]),
        "remedial_total": len(remedial),
        "remedial_correct": sum(1 for r in remedial if r["is_correct"]),
        "primary_percent": round(primary_points / denominator * 100, 1) if denominator else 0.0,
        "credited_points": round(primary_points + recovery_points, 2),
        "credited_percent": round((primary_points + recovery_points) / denominator * 100, 1)
                            if denominator else 0.0,
        "recovery_points": round(recovery_points, 2),
    }


def score_attempt(attempt):
    records = attempt_records(attempt)
    # Readiness (level-weighted) is computed on primary questions only, so a
    # student cannot climb the readiness score by failing and recovering.
    primary_records = [r for r in records if not r.get("is_remedial")]
    report = scoring.full_report(primary_records)

    pts = points_summary(records)
    report["points"] = pts
    report["score_percent"] = pts["primary_percent"]
    report["credited_percent"] = pts["credited_percent"]
    report["records"] = records
    return report
