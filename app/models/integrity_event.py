from datetime import datetime

from app.extensions import db

EVENT_TYPES = (
    "tab_hidden", "window_blurred", "rapid_response", "copy_event", "paste_event",
    "repeated_wrong_fast_answer", "unusual_response_time",
)


class IntegrityEvent(db.Model):
    __tablename__ = "integrity_events"

    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey("attempts.id"), nullable=False, index=True)
    event_type = db.Column(db.String(48), nullable=False)
    event_value = db.Column(db.String(255))
    severity = db.Column(db.String(16), default="info", nullable=False)
    occurred_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    meta = db.Column(db.Text)
