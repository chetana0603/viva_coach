"""
Create N pre-approved student accounts in one shot:

    student1 / student1@gmail.com ... studentN / studentN@gmail.com

All share one starting password and are active immediately — no registration, no
approval queue. Students can change their password after logging in.

    python scripts/create_students.py --count 50 --password Study@2026

Idempotent: existing register numbers are skipped, so re-running is safe.

The shared password is a deliberate trade-off: it removes the registration
bottleneck for a supervised classroom study, at the cost that anyone who knows
the pattern can enter as any student until that student changes their password.
Acceptable for a study you supervise; not for anything real. Don't reuse a
password that matters anywhere else.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()

from app import create_app                     # noqa: E402
from app.extensions import db                  # noqa: E402
from app.models.user import EligibleStudent, User  # noqa: E402
from app.utils.security import hash_password, password_problems  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--start", type=int, default=1,
                        help="First number, so --start 51 extends an existing set.")
    parser.add_argument("--password", required=True)
    parser.add_argument("--domain", default="gmail.com")
    parser.add_argument("--prefix", default="student")
    args = parser.parse_args()

    problems = password_problems(args.password)
    if problems:
        print("Password rejected:", " ".join(problems))
        return

    app = create_app(os.environ.get("CONFIG", "app.config.DevelopmentConfig"))
    with app.app_context():
        pw_hash = hash_password(args.password)   # hash once, reuse: argon2 is slow on purpose
        created = skipped = 0

        for i in range(args.start, args.start + args.count):
            reg = f"{args.prefix.upper()}{i:02d}"
            email = f"{args.prefix}{i}@{args.domain}".lower()

            if User.query.filter_by(register_number=reg).first() or \
               User.query.filter_by(email=email).first():
                skipped += 1
                continue

            db.session.add(User(
                register_number=reg,
                full_name=f"Student {i}",
                email=email,
                password_hash=pw_hash,
                role="student",
                account_status="active",       # pre-approved: no queue
                email_verified=True,
            ))
            # Mirror onto the roster so the eligible list reflects reality.
            if not EligibleStudent.query.filter_by(register_number=reg).first():
                db.session.add(EligibleStudent(
                    register_number=reg, full_name=f"Student {i}",
                    email=email, claimed=True,
                ))
            created += 1

        db.session.commit()
        print(f"{created} accounts created, {skipped} already existed.")
        print(f"Logins: {args.prefix}{args.start}@{args.domain} ... "
              f"{args.prefix}{args.start + args.count - 1}@{args.domain}")
        print("All share the password you provided, and all are active immediately.")
        print("Tell students they can change it after logging in (sidebar link).")


if __name__ == "__main__":
    main()
