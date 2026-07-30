# Viva Platform

The platform version of the Streamlit Adaptive Viva Preparation Engine. Same academic
logic, same visual language — but with PostgreSQL persistence, real accounts, server-held
timers, and an assessment mode that survives a refresh.

The Streamlit prototype is **not** replaced. Keep it running, tagged `prototype-v1`, for
Practice/Learn mode and for comparison.

---

## What this version is

Two modes, deliberately separated:

| | Practice mode (still Streamlit) | Assessment mode (this repo) |
|---|---|---|
| Questions | Generated live by Groq | Pre-generated, teacher-approved, from the DB |
| Uploads | Project files allowed | None |
| Timing | None | Server-held `expires_at` |
| Storage | Session state | PostgreSQL, written on every answer |
| Failure impact | Inconvenient | Examination-critical |

Assessment mode makes **zero LLM calls**. Question generation happens days earlier, via
`scripts/generate_questions.py`, and every candidate passes automatic validation plus a
teacher's approval before a student can ever see it.

---

## Running it locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # for local dev you can leave DATABASE_URL unset (SQLite)
export FLASK_APP=wsgi.py

flask db init                 # first time only
flask db migrate -m "Initial schema"
flask db upgrade

python scripts/seed_questions.py     # concepts + your existing offline bank
python scripts/create_admin.py       # your teacher account

flask run
```

Open http://localhost:5000 and log in with the teacher account.

### First run as a teacher

1. **Students → Import roster** — CSV with `register_number, full_name, email, department, section`.
   Only these register numbers can create an account.
2. **Exams → Create exam** — set the registration window, exam window, duration, question count.
3. **Blueprint** — how many questions come from each concept and level. The page shows how many
   approved questions actually exist for each cell.
4. Students register → you approve under **Exam registrations**.
5. After the window: **Results → Export CSV**.

---

## ⚠️ Read this before scheduling a real exam

Your offline bank is smaller than the project report claims. Measured directly from
`subject_bank.OFFLINE_MCQS`:

```
Covered:   Normalization and Functional Dependencies (7)
           Relational Model and Keys (6)
           CPU Scheduling (6)
           Virtual Memory and Paging (6)
           ---------------------------------------------
           25 questions across 4 of 12 concepts

No questions at all:
  DBMS  →  SQL Queries and Joins, Transactions and ACID Properties,
           Indexing and Query Performance, ER Model and Schema Design
  OS    →  Processes and Threads, Deadlocks, Process Synchronization, File Systems
```

The report says "100+ questions." It is 25. For DBMS specifically, `seed_questions.py`
will give you **13 approved questions across 2 concepts** — and a 20-question adaptive
exam needs far more than that, because each question is assigned to an attempt only once.

The pilot target is **192 approved questions** (6 concepts × 4 levels × 8). Closing that
gap is the critical-path task, not the Flask code. Two routes:

```bash
# Draft candidates with Groq, then approve them at /teacher/questions?status=generated
export GROQ_API_KEY=...
python scripts/generate_questions.py DBMS --levels 0 1 2 3 --per-level 8
```

or author them by hand. Either way a teacher approves every one. Budget real time for
this — reviewing ~200 questions is several hours of a teacher's attention, and the
blueprint page will keep warning you until the numbers line up.

---

## Deployment

```bash
git clone <repository> && cd viva_platform
cp .env.example .env            # fill in SECRET_KEY, POSTGRES_PASSWORD, DATABASE_URL

docker compose build
docker compose up -d
docker compose exec web flask db upgrade
docker compose exec web python scripts/create_admin.py
docker compose exec web python scripts/seed_questions.py
docker compose logs -f web
```

TLS certificates go in `deployment/certs/` as `fullchain.pem` and `privkey.pem`.

Backups (`deployment/backup.sh`): nightly, plus immediately before and after every exam.
Restore one at least once before you trust it.

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `DuplicatePreparedStatement: "_pg3_0" already exists` | Supabase **transaction** pooler recycles backend connections | Already handled in `app/config.py` (`prepare_threshold=None`). Pull the latest code. |
| `Path doesn't exist: '...\migrations'` | Fresh copy of the repo — `migrations/` isn't committed | `flask db init`, then `migrate` + `upgrade` |
| `.venv\Scripts\Activate.ps1 not recognized` | No virtualenv in this folder yet | `python -m venv .venv` then activate |
| `No module named 'app'` | `flask` resolving from the parent folder | Use `python -m flask run` |
| `no such table: users` | App fell back to SQLite — `DATABASE_URL` not set for this shell | `$env:DATABASE_URL = "..."` or rely on `.env` |

## Testing

```bash
pytest                       # unit + integration + security
pytest tests/security -v     # the ones that matter most

locust -f tests/load/locustfile.py --host https://staging.example.edu
```

Load stages from the plan: 5 → 10 → 25 → 50 → 75 users. Run them against staging with
seeded load-test accounts, never against real student data.

The security suite covers the things that end a pilot badly:

- a student opening another student's attempt URL (`/attempt/101`) → 404
- answering with another attempt's `assigned_question_id` → rejected
- the correct answer never reaching the browser before submission
- expired attempts refusing answers
- pending accounts unable to log in
- students hitting teacher routes → 403

---

## How the prototype maps onto this

**Reused unchanged**, in `app/core/` — only the imports were rewritten to package paths:

```
scoring.py  integrity.py  retriever.py  text_processing.py
utils.py    subject_bank.py  subject_loader.py  prompts.py  core_engine.py
```

`scoring.full_report()` still produces the Report Mode payload. `scoring_service.py`
rebuilds the prototype's record dicts from database rows and hands them to it unchanged,
so the readiness formula, level-wise accuracy, concept mastery, adaptive trace, and
teacher follow-ups are byte-for-byte the same logic students already saw.

**Rewritten**: `app.py` split into routes (receive) → services (decide) → models (persist)
→ templates (display). Session state is gone.

**One bug fixed on the way over.** `core_engine.generate_teacher_report()` called
`normalize_mcq(parsed, level)` — `level` was undefined there, and the function checked for
a `"question"` key that a teacher report never has. It could only ever return `None` or
raise `NameError`. It now parses the report fields the prompt actually asks for.

---

## Keeping the Streamlit look

`app/static/css/app.css` reproduces the Streamlit light theme from its own tokens:
Source Sans Pro, `#FF4B4B` primary, `#31333F` text, `#F0F2F6` sidebar, `0.5rem` radii,
and Streamlit's exact alert colours (`rgba(28,131,225,0.1)` info, `rgba(33,195,84,0.1)`
success, and so on). `st.metric`, `st.progress`, `st.tabs`, `st.expander`, `st.radio`,
`st.dataframe`, and `st.bar_chart` each have a CSS equivalent, so the Report Mode page
and the question card read the same as the prototype.

The one deliberate difference: **explanations and the option breakdown are withheld until
submission.** In Practice mode showing them immediately is the whole point. In an exam it
hands the answer to a student who can then tell a friend, so `result.html` carries the
"Comprehensive Learning Breakdown" instead of the question page.

---

## Layout

```
app/
├── config.py, extensions.py, __init__.py    application factory
├── core/                                    prototype logic, unchanged
├── models/                                  users, exams, questions, attempts, responses
├── auth/                                    roster-gated registration, argon2, lockout
├── student/                                 dashboard, exam page, answer, result, API
├── teacher/                                 accounts, exams, blueprint, review, results
├── exam_engine/                             access, attempt, selection, adaptive, scoring
├── question_authoring/                      validation, duplicate detection
├── integrity_svc/                           soft signals → integrity_events
├── templates/, static/                      Streamlit-look UI
scripts/                                     admin, seeding, roster, generation
tests/                                       unit, integration, security, load
deployment/                                  nginx, gunicorn, backup
```

---

## Integrity, stated plainly

Every signal here is a **review indicator, never a verdict**. Tab-hidden, window-blur,
copy, and paste events are reported by the browser and are trivially defeatable — treat a
missing signal as meaning nothing at all. Response-time flags come from the prototype's
own heuristics, compared against each student's own baseline. Nothing is ever
auto-penalised; a teacher reads the flags and decides.

Say this to students before the exam rather than after. An exam that silently watches
people is a different thing from one that tells them what it records.
