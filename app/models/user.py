from datetime import datetime

from flask_login import UserMixin

from app.extensions import db

ROLES = ("student", "teacher", "admin")
ACCOUNT_STATUSES = ("pending", "active", "rejected", "suspended")


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    register_number = db.Column(db.String(32), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    department = db.Column(db.String(80))
    section = db.Column(db.String(16))
    role = db.Column(db.String(16), nullable=False, default="student")
    account_status = db.Column(db.String(16), nullable=False, default="pending")
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    failed_logins = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    approved_at = db.Column(db.DateTime)
    last_login_at = db.Column(db.DateTime)

    def is_teacher(self):
        return self.role in ("teacher", "admin")

    def __repr__(self):
        return f"<User {self.register_number} {self.role}>"


class EligibleStudent(db.Model):
    """Roster imported by a teacher. Registration is only allowed against a row here."""
    __tablename__ = "eligible_students"

    id = db.Column(db.Integer, primary_key=True)
    register_number = db.Column(db.String(32), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), nullable=False, index=True)
    department = db.Column(db.String(80))
    section = db.Column(db.String(16))
    claimed = db.Column(db.Boolean, default=False, nullable=False)
    imported_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
