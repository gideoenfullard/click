# ClickAI Gunicorn Configuration for Fly.io
# Place this file next to clickai.py

import os

# Bind to Fly.io port
bind = f"0.0.0.0:{os.environ.get('PORT', '8080')}"

# Workers: 2-4 for Fly.io (256MB-1GB RAM)
# Each worker handles requests independently
# So if Sonnet takes 30s for one user, others still work
workers = int(os.environ.get("WEB_CONCURRENCY", "3"))

# Threads per worker (good for I/O-bound work like API calls)
threads = 2

# Timeout: 300s to handle PDF bank imports + Claude API calls
timeout = 300

# Graceful timeout for shutdown
graceful_timeout = 30

# Keep-alive connections
keepalive = 5

# Preload off - each worker imports app independently
# (NightlyScheduler runs in each worker but that's harmless)
preload_app = False

# Access logging (shows request timing in Fly.io logs)
accesslog = "-"
access_log_format = '[%(h)s] %(r)s %(s)s %(b)s %(D)sμs'

# Error logging
errorlog = "-"
loglevel = "info"

# Worker class - gthread for threading support
worker_class = "gthread"
