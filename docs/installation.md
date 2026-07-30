# Installation Guide

## Prerequisites
- Python 3.10 or newer
- PostgreSQL-compatible database (Supabase is supported)
- Git
- PowerShell or a similar terminal

## 1. Create a Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks the activation script:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 2. Install Dependencies
```powershell
pip install -r requirements.txt
```

## 3. Configure Environment Variables
Create a `.env` file from the example file if present:
```powershell
copy .env.example .env
```

Set at least:
- `SECRET_KEY`
- `DATABASE_URL`
- `GROQ_API_KEY` (optional for generation workflows)

## 4. Initialize the Database
```powershell
$env:FLASK_APP = "wsgi.py"
flask db init
flask db migrate -m "Initial schema"
flask db upgrade
```

## 5. Seed Initial Data
```powershell
python scripts/seed_questions.py
python scripts/create_admin.py
python scripts/create_students.py --count 50 --password Study2026ok
```

## 6. Run the Application
```powershell
python -m flask run
```

Open http://localhost:5000 in your browser.

## Troubleshooting
- If Flask cannot find the app, use `python -m flask run` instead of `flask run`.
- If the database tables are missing, run the migration steps again.
- If the app uses the wrong database, verify `.env` and `DATABASE_URL`.
