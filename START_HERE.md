# START HERE

This replaces every earlier setup note. Follow it top to bottom once and you'll have a
working system. Every known problem you hit is already fixed in this version.

**Delete your old project folder** and use this fresh copy. Mixing old files with new ones is
how the confusion started.

---

## What you're setting up

Three kinds of test, all DBMS:

| Test type | Questions from | Explanations | Second chances | Part of the study |
|---|---|---|---|---|
| **Pre-test** | approved DBMS bank | no | no | yes — the baseline |
| **Post-test** | *same* DBMS bank | yes | yes (0.25 credit) | yes — the outcome |
| **Project viva** | student's own report | yes | yes (0.25 credit) | no — separate feature |

The study compares pre-test against post-test. Both draw the same bank, so the only
difference between them is the teaching — which is what makes the comparison mean anything.

---

# Part 1 — Setup (about 30 minutes)

## 1.1 Put the project somewhere and open PowerShell there

Extract the zip, then:

```powershell
cd "D:\D drive\internship\viva_platform"
```

Everything below runs from this folder. If a command fails with "not recognized" or "no such
file", check your prompt actually shows this path.

## 1.2 Virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Your prompt should now start with `(.venv)`. If PowerShell blocks the script:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 1.3 Install

```powershell
pip install -r requirements.txt
```

## 1.4 Supabase database

1. **supabase.com** → New project. Set a database password with **only letters and numbers**
   (special characters need URL-escaping — avoid the problem). Save it somewhere.
2. Wait ~2 minutes for provisioning.
3. Click **Connect** at the top of the dashboard.
4. Choose the **Transaction pooler** string. Check it has `pooler.supabase.com` and port
   `6543`. Do **not** use "Direct connection" — it's IPv6-only and will hang.

## 1.5 Create `.env`

```powershell
copy .env.example .env
notepad .env
```

Fill in exactly two things:

```
SECRET_KEY=<paste from the command below>
DATABASE_URL=postgresql+psycopg://postgres.xxxx:YOURPASSWORD@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
```

Generate the secret key:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

For `DATABASE_URL`, take the Supabase string and make **two edits**:
- `postgresql://` → `postgresql+psycopg://`
- `[YOUR-PASSWORD]` → your real password (remove the brackets too)

Add `GROQ_API_KEY=gsk_...` from console.groq.com if you have one. Save and close.

> Scripts now read `.env` automatically. You never need `$env:DATABASE_URL` again.

## 1.6 Create the database tables

```powershell
$env:FLASK_APP = "wsgi.py"
flask db init
flask db migrate -m "Initial schema"
flask db upgrade
```

**Before moving on**, open the new file in `migrations\versions\` and search it for these.
All five must be present:

```
project_submissions          study_cards
uq_attempt_exam_user         uq_response_per_assigned_question
uq_assigned_once
```

The `uq_` ones are unique constraints that stop duplicate attempts and double-submitted
answers. If they're not in the migration, they're not in the database, and that protection
doesn't exist.

✅ Check Supabase → **Table Editor**. You should see `users`, `exams`, `questions`,
`attempts`, `project_submissions`, and more.

## 1.7 Seed and create your teacher account

```powershell
python scripts/seed_questions.py
python scripts/create_admin.py
python scripts/create_students.py --count 50 --password Study2026ok
```

`create_admin.py` asks for your email, name, a staff ID, and a password (10+ characters, at
least one letter and one number).

`create_students.py` makes 50 pre-approved logins — `student1@gmail.com` through
`student50@gmail.com`, all sharing the password you pass, all active immediately. No
registration, no approval queue. Students can change their password after logging in
(sidebar → Change password). Then put everyone on a test in one click:
**teacher → Exams → Enrol → Enrol ALL active students.**

## 1.8 Run it

```powershell
python -m flask run
```

Open **http://localhost:5000** and log in.

> Use `python -m flask run`, not plain `flask run` — the bare command sometimes resolves
> from the parent folder and fails with `No module named 'app'`.

---

# Part 2 — Build your question bank

**This is the real work, and everything else waits on it.**

After seeding you have ~25 questions across 4 concepts, roughly 1 per level. That is not
enough. Both your tests draw from this bank and **never repeat a question between them**, so
each level needs enough for two separate runs.

Target: **8–10 approved questions per level, per concept**, for the concepts you'll test.

## 2.1 Add your DBMS notes

Copy `dbms_notes.txt` into `subject_materials\`. Question generation is grounded in these
notes and will refuse to run without them.

```powershell
Test-Path subject_materials\dbms_notes.txt
```

Must print `True`.

## 2.2 Generate candidates

```powershell
python scripts/generate_questions.py DBMS --levels 0 1 2 3 --per-level 10
```

Takes several minutes. It over-generates because the validator rejects weak ones
automatically.

## 2.3 Approve them — by hand

Teacher login → **Question bank** → **generated** tab. Approve or reject each one.

**Only approved questions ever appear in a test.** Read each one and check:

- Is the marked-correct answer actually correct? *(the validator cannot judge this — you can)*
- Are the wrong options plausibly wrong, not filler?
- Does the difficulty match the level? A mislevelled question corrupts your adaptive
  measurement, not just that one answer.

Do 20–30 at a sitting. Around question 50 your judgment degrades and you start rubber-stamping,
which is exactly what poisons a learning-gains study.

## 2.4 Check coverage

```powershell
python scripts/seed_questions.py
```

Reprints the per-concept, per-level counts including your newly approved ones. Repeat 2.2–2.4
until the levels you'll use show 8+.

**Decide scope from these numbers.** Two concepts done properly beats six done thinly. If
Levels 4–5 won't reach quality, set `max_level = 3` on both exams and cap the climb there.

---

# Part 3 — Set up the study

## 3.1 Accounts — the fast way

If you ran `create_students.py` in step 1.7, you already have 50 active logins and can
skip the roster entirely. Hand each friend a login (`student7@gmail.com` + the shared
password), enrol everyone on the exam from **Exams → Enrol**, done.
The roster flow below still works and remains right for a real class where students
register with their own details.

## 3.1b Roster (optional now)

Create `roster.csv` in the project folder — your friends, with IDs you assign:

```csv
register_number,full_name,email,department,section
STUDY01,Aditya R,aditya@gmail.com,CSE,A
STUDY02,Priya S,priya@gmail.com,CSE,A
```

Use their **real emails** — the address must match exactly at registration.

```powershell
python scripts/import_students.py roster.csv
```

Send each friend their ID, the exact email you used, and the link. They register, then you
approve them under **Students & accounts**.

## 3.2 Create the two tests

**Teacher → Exams → Create exam.** Make two, identical except where marked:

| Field | Test 1 | Test 2 |
|---|---|---|
| Title | `Pre-test — Baseline` | `Post-test` |
| **Test type** | **pre_test** | **post_test** |
| **Show explanations after each answer** | **OFF** | **ON** |
| Show result immediately | OFF | ON |
| **Study group tag** | `dbms-study` | `dbms-study` (identical) |
| Exam window | e.g. Mon–Wed | Thu–Sat (**after** Test 1 closes) |
| Subject / questions / levels | same | same |
| Status | active | active |

Two settings are load-bearing:

- **Identical study group tag** — this is what stops Test 2 reusing a Test 1 question.
- **Explanations OFF for the pre-test** — a baseline that teaches isn't a baseline. The app
  enforces this and will switch it off with a warning if you try.

After saving each, open **Concepts** and tick which concepts are in scope, plus the question
count. There's no per-level grid — the adaptive engine picks the level from how the student
answers.

## 3.3 Approve exam registrations

Students register for each exam from their dashboard; you approve under **Exam
registrations**. This is separate from approving their account.

---

# Part 4 — Test it yourself first

Do not skip this. It costs 15 minutes and catches a thin-bank stall while it's still cheap.

1. Add yourself to the roster as `TEST01` with a spare email, import it.
2. Open an **incognito window**, register as TEST01. Approve from your normal (teacher)
   window. Two windows, because a browser holds one login at a time.
3. Register for the pre-test, approve it, take it.

Watch for:

- **Does the level move?** Correct → harder, wrong → easier.
- **Does it reach the full question count**, or stall early? Stalling means a level ran dry —
  go back to Part 2.
- **Refresh mid-question** → same question, timer unchanged.
- **URL fiddling**: change `/student/attempts/5` to `/6` → must be a 404.

Then do the same for the post-test and confirm the explanation screen appears after each
answer, with the per-option breakdown.

---

# Part 5 — Deploy (only when Parts 2–4 are done)

Full detail in `DEPLOY_RENDER_SUPABASE.md`. Short version:

1. Confirm `.env` is ignored: `git check-ignore .env` must print `.env`
2. Push to a **private** GitHub repo
3. **render.com** → New → Blueprint → your repo (it reads `render.yaml`)
4. In Render's Environment tab, set `DATABASE_URL` (same Supabase string) and `GROQ_API_KEY`
5. Free Render services sleep after 15 minutes idle. Point a free
   **uptimerobot.com** monitor at `https://your-app.onrender.com/healthz` every 10 minutes —
   this also stops Supabase pausing between your two tests.

Your database already has everything, so there's nothing to re-seed.

---

# Part 6 — Read the results

**Teacher → System evaluation.** Pick your study group tag. It pairs each student's two
attempts and shows the gains. **Export CSV** for your report.

The numbers that matter:

- **Readiness gain** — the primary outcome; weights higher levels and rewards depth
- **Highest level gain** — how much further up they climbed
- **Score gain** — first-attempt correctness

> **Why "primary" score?** The post-test offers 0.25 recovery credit on a second chance; the
> pre-test has no such mechanic. Comparing a with-remediation score against a
> without-remediation one would credit the post-test for the scoring rule rather than for
> learning. So comparisons use first-attempt questions only. Recovery is reported separately
> — it's genuinely interesting, just not the headline.

**Export after every session.** Free tiers have no backups, and you can't re-run someone's
baseline.

---

# Troubleshooting

| Error | Fix |
|---|---|
| `Activate.ps1 not recognized` | No venv here yet → `python -m venv .venv` (step 1.2) |
| `No module named 'app'` | Use `python -m flask run`, not `flask run` |
| `Path doesn't exist: ...\migrations` | `flask db init` first (step 1.6) |
| `DuplicatePreparedStatement "_pg3_0"` | Fixed in this version's `app/config.py`. If you see it, you're on an old copy. |
| `failed to resolve host 'db'` | `.env` has `@db:5432` — use your Supabase pooler host |
| `no such table: users` | `.env` missing or `DATABASE_URL` commented out |
| `password authentication failed` | Password in `DATABASE_URL` doesn't match Supabase |
| Connection hangs forever | You used the **direct** string — switch to **transaction pooler** (6543) |
| `psycopg-binary==3.2.1` not found | Fixed — this version uses `>=3.2.2` |
| `No module named 'fcntl'` | You ran gunicorn on Windows. Use `python -m flask run` locally; gunicorn is for Render. |
| Register button missing | Exam window has passed, or status isn't `active` — edit the dates |
| "Register number not on the eligible list" | Import a roster first (step 3.1) |
| Test ends early | Bank too thin at some level — back to Part 2 |

**If Supabase already has tables and a migration fails**, the quickest reset while you have no
real data — Supabase → SQL Editor:

```sql
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO postgres;
```

Then redo step 1.6 onward. **This destroys everything** — never run it once real student data
exists.

---

# The order, one more time

1. **Setup** (Part 1) — 30 minutes, do it once
2. **Question bank** (Part 2) — days; the binding constraint on the whole study
3. **Study setup** (Part 3) — 5 minutes with pre-made accounts
4. **Dry run** (Part 4) — 15 minutes, don't skip
5. **Deploy** (Part 5) — 45 minutes
6. **Run the study, export results** (Part 6)

Everything except Part 2 is quick. Part 2 is the project.
