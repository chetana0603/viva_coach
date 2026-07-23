from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log in")


class RegisterForm(FlaskForm):
    register_number = StringField("Register number", validators=[DataRequired(), Length(max=32)])
    email = StringField("College email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    confirm = PasswordField("Confirm password",
                            validators=[DataRequired(), EqualTo("password", "Passwords must match.")])
    submit = SubmitField("Create account")
