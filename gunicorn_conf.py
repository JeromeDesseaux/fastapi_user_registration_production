"""
Gunicorn configuration for production FastAPI deployment.

This configuration uses Gunicorn as a process manager with Uvicorn workers
for optimal ASGI/async performance. Gunicorn provides:
- Multiple worker processes (parallelism)
- Graceful reloads (zero-downtime deployments)
- Worker health monitoring and auto-restart
- Load balancing across workers

Decision: Gunicorn + Uvicorn workers is the industry standard for production
FastAPI deployments, providing mature process management with full async support.
"""

import multiprocessing
import os

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
# Formula: (2 x CPU cores) + 1 for I/O-bound async applications
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "uvicorn.workers.UvicornWorker"  # ASGI-compatible async workers
worker_connections = 1000
max_requests = 1000  # Restart workers after N requests (prevents memory leaks)
max_requests_jitter = 50  # Add randomness to prevent all workers restarting simultaneously

# Timeouts
timeout = 30  # Workers silent for >30s are killed
keepalive = 5  # Keep-alive connections
graceful_timeout = 30  # Time to finish in-flight requests during graceful reload

# Logging
accesslog = "-"  # Log to stdout (Docker-friendly)
errorlog = "-"  # Log to stderr (Docker-friendly)
loglevel = os.getenv("LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "fastapi-user-registration"

# Server mechanics
daemon = False  # Run in foreground (required for Docker)
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (disabled, handled by reverse proxy)
keyfile = None
certfile = None
