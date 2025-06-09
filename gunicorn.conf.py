#!/usr/bin/env python3
"""
Gunicorn configuration for memory-optimized logging services.
"""

import multiprocessing
import os

# Server socket
bind = f"0.0.0.0:{os.environ.get('PORT', 8080)}"
backlog = 2048

# Worker processes - limit to reduce memory usage
workers = min(2, multiprocessing.cpu_count())  # Max 2 workers
worker_class = "sync"  # Use sync workers instead of async to reduce memory
worker_connections = 100  # Limit connections per worker
max_requests = 500  # Restart workers after 500 requests to prevent memory leaks
max_requests_jitter = 50  # Add jitter to prevent all workers restarting at once

# Memory limits
worker_memory_limit = 512 * 1024 * 1024  # 512MB per worker
worker_tmp_dir = "/tmp"

# Timeouts - reduce to prevent hanging requests
timeout = 30  # 30 seconds
keepalive = 2  # 2 seconds
graceful_timeout = 30

# Logging
loglevel = "info"
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stderr
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "enhanced-logging-api"

# Security
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8192

# Preload app to save memory
preload_app = True

# Worker lifecycle hooks for memory management
def when_ready(server):
    """Called just after the server is started."""
    server.log.info("Enhanced Logging API server is ready. PID: %s", os.getpid())

def worker_int(worker):
    """Called just after a worker exited on SIGINT or SIGQUIT."""
    worker.log.info("Worker received INT or QUIT signal")

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)
    
def worker_abort(worker):
    """Called when a worker received the SIGABRT signal."""
    worker.log.info("Worker received SIGABRT signal")
