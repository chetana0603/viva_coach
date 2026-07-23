from datetime import datetime

from app.extensions import db


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(64), nullable=False, index=True)
    entity_type = db.Column(db.String(48))
    entity_id = db.Column(db.Integer)
    ip_address = db.Column(db.String(64))
    user_agent = db.Column(db.String(255))
    occurred_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    meta = db.Column(db.Text)
