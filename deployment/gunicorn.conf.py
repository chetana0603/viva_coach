"""
Gunicorn config. Worker/thread/port counts read from the environment so the same
file works on a tiny Render free instance and a bigger college VM.

Render sets $PORT and has ~512 MB on the free tier — keep it to 2 workers there.
On a 4-core VM, start with WEB_WORKERS=4 and tune after the 25/50-user load tests.
"""
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = int(os.environ.get("WEB_WORKERS", "2"))
threads = int(os.environ.get("WEB_THREADS", "2"))
timeout = 60
graceful_timeout = 30
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = "info"
capture_output = True
