"""Password hashing (argon2) and audit logging."""
import json

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from flask import request
from flask_login import current_user

from app.extensions import db

_ph = PasswordHasher()

PASSWORD_MIN_LENGTH = 10


def hash_password(raw: str) -> str:
    return _ph.hash(raw)


def verify_password(stored_hash: str, raw: str) -> bool:
    try:
        return _ph.verify(stored_hash, raw)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_problems(raw: str):
    problems = []
    if len(raw or "") < PASSWORD_MIN_LENGTH:
        problems.append(f"Use at least {PASSWORD_MIN_LENGTH} characters.")
    if not any(c.isalpha() for c in raw or ""):
        problems.append("Include at least one letter.")
    if not any(c.isdigit() for c in raw or ""):
        problems.append("Include at least one number.")
    return problems


def audit(action, entity_type=None, entity_id=None, **meta):
    from app.models.audit import AuditLog
    log = AuditLog(
        actor_user_id=getattr(current_user, "id", None) if current_user else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        ip_address=(request.remote_addr if request else None),
        user_agent=(request.headers.get("User-Agent", "")[:255] if request else None),
        meta=json.dumps(meta) if meta else None,
    )
    db.session.add(log)
    return log
