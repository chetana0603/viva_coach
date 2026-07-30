from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.auth.forms import LoginForm, RegisterForm
from app.auth.services import authenticate, register_student
from app.extensions import db
from app.utils.security import audit

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("public.home"))
    form = RegisterForm()
    if form.validate_on_submit():
        user, error = register_student(form.register_number.data, form.email.data,
                                       form.password.data)
        if error:
            flash(error, "error")
        else:
            db.session.commit()
            flash("Account created. Your teacher will approve it before you can log in.",
                  "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("public.home"))
    form = LoginForm()
    if form.validate_on_submit():
        user, error = authenticate(form.email.data, form.password.data)
        if error:
            flash(error, "error")
        else:
            login_user(user)
            audit("user_login", "user", user.id)
            db.session.commit()
            nxt = request.args.get("next")
            if nxt and nxt.startswith("/") and not nxt.startswith("//"):
                return redirect(nxt)
            return redirect(url_for("public.home"))
    return render_template("auth/login.html", form=form)


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    from app.utils.security import hash_password, password_problems, verify_password
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")

        if not verify_password(current_user.password_hash, current):
            flash("Your current password is incorrect.", "error")
        elif new != confirm:
            flash("The new passwords do not match.", "error")
        elif password_problems(new):
            flash(" ".join(password_problems(new)), "error")
        else:
            current_user.password_hash = hash_password(new)
            audit("password_changed", "user", current_user.id)
            db.session.commit()
            flash("Password changed.", "success")
            return redirect(url_for("public.home"))
    return render_template("auth/change_password.html")


@auth_bp.route("/logout")
@login_required
def logout():
    audit("user_logout", "user", current_user.id)
    db.session.commit()
    logout_user()
    flash("You are logged out.", "info")
    return redirect(url_for("auth.login"))
