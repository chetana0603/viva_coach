# Deploying online — Render (app) + Supabase (database)

No Docker, no local Postgres, no laptop staying on. Your Flask app runs on Render; your data
lives on Supabase. Both free. Your friends get an `https://…onrender.com` link.

Roughly 45 minutes end to end.

---

## Why this split

- **Supabase = the database.** Managed Postgres, free, and — unlike a free Render database —
  it does **not** expire after 30 days. It only pauses after a week of no activity, which a
  keep-alive pinger (Step 6) prevents.
- **Render = the app.** Runs Linux, so Gunicorn works there natively — the `fcntl` /
  `No module named 'fcntl'` error only happens on Windows. You never run Gunicorn locally.

---

## Step 1 — Supabase database (10 min)

1. Sign up at **supabase.com** → **New project**.
2. Name it, set a strong **database password** (save it), pick the region closest to your
   friends (Mumbai/Singapore for India).
3. Wait ~2 minutes for it to provision.
4. Find the connection string. Supabase moved this — it's **no longer** under Project
   Settings. Click the **"Connect"** button at the **top of the dashboard** (top bar, next to
   the project name). A panel opens with several connection strings.
5. In that panel, find the **"Transaction pooler"** section (host contains
   `pooler.supabase.com`, port `6543`) and copy its string. Avoid the **"Direct connection"**
   one.

   > **Why the pooler, not direct.** The direct string is IPv6-only unless you buy the IPv4
   > add-on, and most home/college/Windows networks can't do IPv6 — the direct string just
   > hangs. The pooler (Supavisor) is IPv4-friendly and works everywhere. This is the single
   > most common Supabase setup failure.
   >
   > If you only see the panel by project reference, the same page is at
   > `https://supabase.com/dashboard/project/_?showConnect=true`.

   It looks like:

   ```
   postgresql://postgres.abcdxyz:[YOUR-PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
   ```

6. Change **two things** for this app:
   - `postgresql://` → `postgresql+psycopg://`
   - replace `[YOUR-PASSWORD]` with the real password from step 2

   Final form:

   ```
   postgresql+psycopg://postgres.abcdxyz:realpassword@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
   ```

   Keep this handy — it's your `DATABASE_URL` in two places below.

---

## Step 2 — Create the tables on Supabase (5 min)

Do this **from your laptop**, pointing at Supabase, before deploying. It's the one time you
run migrations.

`.env` on your machine (temporarily) with the Supabase URL:

```bash
FLASK_ENV=development
SECRET_KEY=anything-for-local-migration
DATABASE_URL=postgresql+psycopg://postgres.abcdxyz:realpassword@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
GROQ_API_KEY=gsk_your_key
ALLOWED_EMAIL_DOMAIN=
```

Then:

```powershell
.\.venv\Scripts\Activate.ps1
$env:FLASK_APP = "wsgi.py"

flask db migrate -m "Initial schema"
flask db upgrade
python scripts/seed_questions.py
python scripts/create_admin.py
```

✅ Supabase dashboard → **Table Editor** shows `users`, `exams`, `questions`, `attempts`, etc.

> **Read the migration first.** Open the new file in `migrations\versions\` and confirm these
> three constraints are in it: `uq_attempt_exam_user`, `uq_response_per_assigned_question`,
> `uq_assigned_once`. They stop duplicate attempts and double-submitted answers. If they're
> missing, they're not in the database.

---

## Step 3 — Push to GitHub (5 min)

Render deploys from a Git repo.

```powershell
git check-ignore .env
```

✅ This must print `.env`. If it prints nothing, **stop** — your secrets are about to go
public. Confirm `.gitignore` contains `.env`.

```powershell
git add .
git commit -m "Platform ready for deploy"
git remote add origin https://github.com/YOURNAME/viva_platform.git
git push -u origin main
```

Make the GitHub repo **private** — the code is fine to share, but no reason to make your study
setup public.

---

## Step 4 — Deploy on Render (10 min)

1. Sign up at **render.com** with your GitHub account.
2. **New → Blueprint** → pick your repo. Render reads `render.yaml` and sets up the web
   service automatically. (If it doesn't detect the blueprint, use **New → Web Service**,
   build command `pip install -r requirements.txt`, start command
   `gunicorn --config deployment/gunicorn.conf.py wsgi:app`.)
3. In the service's **Environment** tab, set the values `render.yaml` left blank:
   - `DATABASE_URL` → your Supabase pooler string from Step 1
   - `GROQ_API_KEY` → your key
   - `SECRET_KEY` → Render generated one; leave it
4. **Create Web Service.** First build takes a few minutes; watch the log.

✅ `https://viva-platform-xxxx.onrender.com/healthz` returns `{"status": "ok"}`.

You already created the admin and seeded questions against Supabase in Step 2, and Render
uses the same database, so your teacher login already works. Nothing to re-run.

---

## Step 5 — The free-tier sleep, and why it barely matters (2 min)

Render's free web service **spins down after 15 minutes of no traffic**; the next request
takes ~60 seconds to wake it. On the *first page*, before anyone starts a test — so it never
eats exam time.

Two ways to handle it:

- **Just warn people:** "first load may take a minute." Fine for 20 friends.
- **Keep it awake (Step 6).** Better if your test window is open for days.

---

## Step 6 — Keep-alive pinger (5 min) — do this for a multi-day window

A free uptime monitor hitting `/healthz` every 10 minutes keeps **both** Render awake and
Supabase active (Supabase pauses after a week idle; this resets that clock).

1. Sign up at **uptimerobot.com** (free) or **cron-job.org** (free).
2. New monitor → HTTP(s) → URL `https://viva-platform-xxxx.onrender.com/healthz` →
   interval **10 minutes**.
3. Save.

That's it — no more cold starts during your study, and Supabase won't pause between Test 1
and Test 2.

---

## Step 7 — Back up your data (the study is irreplaceable)

There are **no automatic backups** on either free tier, and you can't re-run someone's
baseline test. After **each** test session:

- Teacher dashboard → the exam → **Results → Export CSV.** That's your real deliverable —
  save it somewhere safe (not just on your laptop).
- Optionally, Supabase dashboard → Database → you can dump the whole database from Settings.

Export **immediately after Test 1** and **immediately after Test 2**. Don't wait.

---

## Updating the app later

Change code → `git push` → Render redeploys automatically. If you changed models, run
`flask db migrate` + `flask db upgrade` from your laptop against Supabase (as in Step 2) —
Render doesn't run migrations for you.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Connection hangs, then times out | Using the **direct** Supabase string (IPv6) | Use the **pooler** string (Step 1.4) |
| `password authentication failed` | `[YOUR-PASSWORD]` placeholder left in, or wrong password | Re-copy, replace the bracket with the real password |
| `No module named 'fcntl'` | Ran Gunicorn on Windows | You don't — Gunicorn runs on Render. Locally use `flask run` or Waitress |
| First visit takes 60s | Render free spin-down | Step 6 pinger, or just warn people |
| Project offline after a quiet week | Supabase paused | Dashboard → Restore (one click). Step 6 prevents it |
| Render build fails on `pip install` | A package won't build | Check the build log; usually a version pin — tell me what it says |
| Tables missing on Supabase | Step 2 not run, or run against the wrong URL | Re-run `flask db upgrade` with the Supabase URL in `.env` |

---

## The whole thing, in order

1. Supabase project → copy **pooler** string, fix the two edits
2. `.env` with that string → `flask db upgrade` → seed → create admin (from your laptop)
3. Read the migration; confirm the three unique constraints
4. `git push` to a private GitHub repo (check `.env` is ignored)
5. Render → Blueprint → set `DATABASE_URL` + `GROQ_API_KEY`
6. UptimeRobot pinger on `/healthz`
7. Export CSV after every test session

Then build your question bank and set up the two tests — see `STUDY_SETUP.md`.
