"""Server-side integrity signals. Review indicators only — never a cheating verdict."""
from app.core import integrity as core_integrity
from app.extensions import db
from app.models.integrity_event import IntegrityEvent

SEVERITY = {
    "rapid_response": "low",
    "repeated_wrong_fast_answer": "medium",
    "unusual_response_time": "low",
    "tab_hidden": "medium",
    "window_blurred": "low",
    "copy_event": "medium",
    "paste_event": "medium",
}

CLIENT_EVENT_TYPES = {"tab_hidden", "window_blurred", "copy_event", "paste_event"}


def record_event(attempt_id, event_type, value=None, severity=None):
    event = IntegrityEvent(
        attempt_id=attempt_id, event_type=event_type, event_value=value,
        severity=severity or SEVERITY.get(event_type, "info"),
    )
    db.session.add(event)
    return event


def evaluate_response(attempt, assigned_question, response):
    """Run the prototype's heuristics against a freshly saved response."""
    rt = response.response_time_seconds
    tag = f"q#{assigned_question.sequence_number}"

    if core_integrity.check_mcq_response(rt, response.is_correct, assigned_question.assigned_level):
        record_event(attempt.id, "rapid_response", tag)

    previous = [
        aq.response.response_time_seconds for aq in attempt.assigned
        if aq.response is not None and aq.id != assigned_question.id
    ]
    if core_integrity.check_response_time_anomaly(rt, previous):
        record_event(attempt.id, "unusual_response_time", tag)

    recent = [
        {"type": "mcq", "is_correct": aq.response.is_correct,
         "response_time": aq.response.response_time_seconds}
        for aq in attempt.assigned if aq.response is not None
    ]
    if core_integrity.check_rapid_wrong_streak(recent):
        record_event(attempt.id, "repeated_wrong_fast_answer", tag)
