from collections import Counter

from app.extensions import db
from app.models.integrity_event import IntegrityEvent

LABELS = {
    "rapid_response": "Very fast MCQ response (answered almost instantly)",
    "repeated_wrong_fast_answer": "Repeated rapid wrong responses",
    "unusual_response_time": "Response time unusual for this student's own pace",
    "tab_hidden": "Switched away from the exam tab",
    "window_blurred": "Exam window lost focus",
    "copy_event": "Copy action on the exam page",
    "paste_event": "Paste action on the exam page",
}


def summarize_attempt(attempt_id):
    events = db.session.query(IntegrityEvent).filter_by(attempt_id=attempt_id).all()
    counts = Counter(e.event_type for e in events)
    return {
        "total": len(events),
        "reasons": {LABELS.get(k, k): v for k, v in counts.items()},
    }
