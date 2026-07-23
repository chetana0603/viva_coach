"""Import an eligible-student roster from CSV (same format as the teacher UI)."""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Read .env exactly like the `flask` command does, so DATABASE_URL and
# GROQ_API_KEY work without setting them in the shell first.
from dotenv import load_dotenv  # noqa: E402
load_dotenv()

from app import create_app
from app.extensions import db
from app.models.user import EligibleStudent


def main(path):
    app = create_app(os.environ.get("CONFIG", "app.config.DevelopmentConfig"))
    with app.app_context():
        added = 0
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                reg = (row.get("register_number") or "").strip().upper()
                if not reg or EligibleStudent.query.filter_by(register_number=reg).first():
                    continue
                db.session.add(EligibleStudent(
                    register_number=reg,
                    full_name=(row.get("full_name") or "").strip(),
                    email=(row.get("email") or "").strip().lower(),
                    department=(row.get("department") or "").strip(),
                    section=(row.get("section") or "").strip(),
                ))
                added += 1
        db.session.commit()
        print(f"Imported {added} eligible students.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/import_students.py roster.csv")
        sys.exit(1)
    main(sys.argv[1])
