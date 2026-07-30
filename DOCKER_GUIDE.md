# Running with Docker

For anyone cloning the repo who doesn't want to install Python, dependencies, or
Postgres — Docker builds all of that into a container. Clone, set two values, one
command, running.

This is also *exactly* how Render runs it in production, so "works in Docker" means
"works deployed".

---

## What you need installed

Just **Docker Desktop** — docker.com/products/docker-desktop. On Windows it needs WSL2;
the installer sets that up (one reboot). Nothing else: no Python, no pip, no Postgres.

Verify:

```powershell
docker --version
docker compose version
```

---

## Option A — full local stack (app + its own Postgres)

Completely self-contained. Nothing shared, nothing external — right for a collaborator
poking at the code without touching the real study database.

```powershell
git clone https://github.com/chetana0603/viva_coach.git
cd viva_coach
copy .env.example .env
```

Edit `.env` — for the local stack you set a **local** database, not Supabase:

```
SECRET_KEY=any-long-random-string-for-dev
DATABASE_URL=postgresql+psycopg://viva_user:localdev123@db:5432/viva
POSTGRES_DB=viva
POSTGRES_USER=viva_user
POSTGRES_PASSWORD=localdev123
GROQ_API_KEY=gsk_your_key_or_blank
GROQ_MODEL=llama-3.1-8b-instant
```

> Here `@db:5432` is **correct** — `db` is the Postgres container's name on Docker's
> internal network. (Outside Docker it's wrong, which is why local Windows setup uses
> `localhost` or Supabase. Same key, two contexts.)

Build and start:

```powershell
docker compose up -d --build
```

First build takes a few minutes. Then, one-time setup **inside the container**:

```powershell
docker compose exec web flask db init
docker compose exec web flask db migrate -m "Initial schema"
docker compose exec web flask db upgrade
docker compose exec web python scripts/seed_questions.py
docker compose exec web python scripts/create_admin.py
docker compose exec web python scripts/create_students.py --count 50 --password Study2026ok
```

Open **http://localhost** (nginx serves on port 80).

Daily driving:

```powershell
docker compose up -d        # start
docker compose logs -f web  # watch logs
docker compose down         # stop (data survives in the postgres_data volume)
docker compose down -v      # stop AND wipe the database — careful
```

Code changes need a rebuild: `docker compose up -d --build`.

---

## Option B — container app, shared Supabase database

For a collaborator who should see the *same data* as the deployed site (same accounts,
same question bank). One line different: `DATABASE_URL` in `.env` points at the Supabase
pooler string instead of `db`:

```
DATABASE_URL=postgresql+psycopg://postgres.xxxx:[email protected]:6543/postgres
```

Then:

```powershell
docker compose up -d --build web
```

(Just `web` — no local `db` container needed.) Skip the migration/seed commands; the
shared database already has everything.

> Anyone with this string has full access to the study data. Share it accordingly, and
> rotate the password if a collaborator rolls off.

---

## What each file does

| File | Role |
|---|---|
| `Dockerfile` | Builds the app image: Python 3.12, dependencies, gunicorn, non-root user, healthcheck |
| `docker-compose.yml` | Orchestrates three containers: `web` (the app), `db` (Postgres 18), `nginx` (reverse proxy on port 80) |
| `deployment/gunicorn.conf.py` | Server tuning; `WEB_WORKERS`/`WEB_THREADS` env vars |
| `deployment/nginx.conf` | Proxy config, security headers, static caching |
| `.env` | All secrets and config. **Never committed** — each machine has its own |

## Troubleshooting

| Symptom | Fix |
|---|---|
| `docker: command not found` | Docker Desktop not installed or not started |
| Port 80 already in use | Change nginx's mapping in `docker-compose.yml` to `"8080:80"`, use http://localhost:8080 |
| `db` unhealthy | `POSTGRES_PASSWORD` missing in `.env`; `docker compose logs db` |
| Web container restarts repeatedly | `docker compose logs web` — usually a bad `DATABASE_URL` |
| Changes don't appear | You edited code but didn't rebuild: `docker compose up -d --build` |
| `permission denied` on scripts | Run the `docker compose exec ...` form, not bare `python` |
