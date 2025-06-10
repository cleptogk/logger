#!/usr/bin/env python3
"""
Gunicorn configuration for logging services.
"""

import multiprocessing
import os

# Server socket
bind = f"0.0.0.0:{os.environ.get('PORT', 8080)}"
backlog = 2048

# Worker processes
workers = min(4, multiprocessing.cpu_count())  # Scale with CPU cores
worker_class = "sync"
worker_connections = 1000  # Increased connections per worker
max_requests = 2000  # Restart workers after more requests
max_requests_jitter = 200  # Add jitter to prevent all workers restarting at once
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

# Preload app for performance
preload_app = True

# Worker lifecycle hooks
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
