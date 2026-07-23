from functools import wraps

from flask import abort
from flask_login import current_user


def teacher_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_teacher():
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def student_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "student":
            abort(403)
        if current_user.account_status != "active":
            abort(403)
        return view(*args, **kwargs)
    return wrapped
