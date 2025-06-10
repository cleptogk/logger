#!/usr/bin/env python3
"""
Gunicorn configuration for logging dashboard.
"""

import multiprocessing
import os

# Server socket
bind = f"0.0.0.0:{os.environ.get('DASHBOARD_PORT', 8081)}"
backlog = 1024

# Worker processes
workers = 2  # Multiple workers for better performance
worker_class = "eventlet"  # Use eventlet for SocketIO support
worker_connections = 200  # Increased connections
max_requests = 1000  # Restart worker after more requests
max_requests_jitter = 100
worker_tmp_dir = "/tmp"

# Timeouts
timeout = 60  # Longer timeout for dashboard
keepalive = 2
graceful_timeout = 30

# Logging
loglevel = "info"
accesslog = "-"
errorlog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "logging-dashboard"

# Security
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8192

# Preload app for performance
preload_app = True

# Worker lifecycle hooks
def when_ready(server):
    """Called just after the server is started."""
    server.log.info("Logging Dashboard server is ready. PID: %s", os.getpid())

def worker_int(worker):
    """Called just after a worker exited on SIGINT or SIGQUIT."""
    worker.log.info("Dashboard worker received INT or QUIT signal")

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    server.log.info("Dashboard worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.info("Dashboard worker spawned (pid: %s)", worker.pid)
    
def worker_abort(worker):
    """Called when a worker received the SIGABRT signal."""
    worker.log.info("Dashboard worker received SIGABRT signal")
