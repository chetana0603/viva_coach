"""Create a teacher/admin account. Run once after the first migration."""
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Read .env exactly like the `flask` command does, so DATABASE_URL and
# GROQ_API_KEY work without setting them in the shell first.
from dotenv import load_dotenv  # noqa: E402
load_dotenv()

from app import create_app
from app.extensions import db
from app.models.user import User
from app.utils.security import hash_password, password_problems


def main():
    app = create_app(os.environ.get("CONFIG", "app.config.DevelopmentConfig"))
    with app.app_context():
        email = input("Email: ").strip().lower()
        if User.query.filter_by(email=email).first():
            print("That email already exists.")
            return
        name = input("Full name: ").strip()
        reg = input("Staff ID / register number: ").strip().upper()
        password = getpass.getpass("Password: ")
        problems = password_problems(password)
        if problems:
            print(" ".join(problems))
            return

        db.session.add(User(
            register_number=reg, full_name=name, email=email,
            password_hash=hash_password(password), role="teacher",
            account_status="active", email_verified=True,
        ))
        db.session.commit()
        print(f"Teacher account created: {email}")


if __name__ == "__main__":
    main()
