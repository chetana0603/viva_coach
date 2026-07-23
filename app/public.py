from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def home():
    if current_user.is_authenticated:
        if current_user.is_teacher():
            return redirect(url_for("teacher.dashboard"))
        return redirect(url_for("student.dashboard"))
    return render_template("home.html")


@public_bp.route("/healthz")
def healthz():
    return {"status": "ok"}
