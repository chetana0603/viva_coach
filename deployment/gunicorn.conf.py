"""
Gunicorn config, sized by environment.

Render's free tier has 512 MB RAM and a fraction of a CPU. Multiple sync workers
there don't add capacity — they add memory pressure and OOM restarts, which users
experience as "the website stopped working". One worker with threads handles a
20-user classroom load comfortably, because this app's requests are short
DB-bound operations, not CPU work.

On a real VM, raise WEB_WORKERS via environment (2 x cores is the usual start).
"""
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = int(os.environ.get("WEB_WORKERS", "1"))
threads = int(os.environ.get("WEB_THREADS", "8"))
worker_class = "gthread"
timeout = 60
graceful_timeout = 30
keepalive = 5
max_requests = 500            # recycle workers to keep memory flat on 512 MB
max_requests_jitter = 50
accesslog = "-"
errorlog = "-"
loglevel = "info"
capture_output = True
