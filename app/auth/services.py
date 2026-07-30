"""Registration and login rules kept out of the route layer."""
from datetime import datetime, timedelta

from flask import current_app

from app.extensions import db
from app.models.user import EligibleStudent, User
from app.utils.security import hash_password, password_problems, verify_password

LOCKOUT_THRESHOLD = 5
LOCKOUT_MINUTES = 10


def register_student(register_number, email, password):
    """Return (user, error). Registration is only allowed against the roster."""
    register_number = (register_number or "").strip().upper()
    email = (email or "").strip().lower()

    domain = current_app.config.get("ALLOWED_EMAIL_DOMAIN")
    if domain and not email.endswith("@" + domain):
        return None, f"Use your college email address ending in @{domain}."

    problems = password_problems(password)
    if problems:
        return None, " ".join(problems)

    eligible = EligibleStudent.query.filter_by(register_number=register_number).first()
    if not eligible:
        return None, "That register number is not on the eligible list. Ask your teacher to add it."
    if eligible.email.strip().lower() != email:
        return None, "The email does not match the record for that register number."
    if eligible.claimed or User.query.filter_by(register_number=register_number).first():
        return None, "An account already exists for that register number."
    if User.query.filter_by(email=email).first():
        return None, "An account already exists for that email."

    user = User(
        register_number=register_number,
        full_name=eligible.full_name,
        email=email,
        password_hash=hash_password(password),
        department=eligible.department,
        section=eligible.section,
        role="student",
        account_status="pending",
    )
    eligible.claimed = True
    db.session.add(user)
    return user, None


def authenticate(email, password):
    """Return (user, error). Errors stay generic on purpose."""
    generic = "Email or password is incorrect."
    user = User.query.filter_by(email=(email or "").strip().lower()).first()
    if not user:
        return None, generic

    if user.locked_until and user.locked_until > datetime.utcnow():
        return None, "Too many attempts. Try again in a few minutes."

    if not verify_password(user.password_hash, password):
        user.failed_logins += 1
        if user.failed_logins >= LOCKOUT_THRESHOLD:
            user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
            user.failed_logins = 0
        db.session.commit()
        return None, generic

    if user.account_status == "pending":
        return None, "Your account is waiting for teacher approval."
    if user.account_status != "active":
        return None, "This account is not active. Contact your teacher."

    user.failed_logins = 0
    user.locked_until = None
    user.last_login_at = datetime.utcnow()
    return user, None
