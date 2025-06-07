#!/usr/bin/env python3
"""
Centralized Logging Server
Main application entry point for the logging server.
"""

import os
import sys
import signal
import threading
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from flask import Flask, jsonify, request
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

from utils.loguru_config import setup_logging
from utils.redis_client import RedisClient
from utils.metrics_exporter import MetricsExporter
from monitors.file_monitor import LogFileMonitor
from schedulers.scheduler_manager import SchedulerManager
from processors.log_processor import LogProcessor

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

# Global components
redis_client = None
metrics_exporter = None
file_monitor = None
scheduler_manager = None
log_processor = None

# Prometheus metrics
log_ingestion_counter = Counter('logs_ingested_total', 'Total number of logs ingested', ['source', 'level'])
log_processing_histogram = Histogram('log_processing_seconds', 'Time spent processing logs')
active_connections_gauge = Gauge('active_connections', 'Number of active connections')
system_health_gauge = Gauge('system_health_score', 'Overall system health score (0-100)')

def initialize_components():
    """Initialize all logging server components."""
    global redis_client, metrics_exporter, file_monitor, scheduler_manager, log_processor
    
    logger.info("Initializing centralized logging server components...")
    
    try:
        # Initialize Redis client
        redis_client = RedisClient()
        logger.info("✅ Redis client initialized")
        
        # Initialize metrics exporter
        metrics_exporter = MetricsExporter()
        logger.info("✅ Metrics exporter initialized")
        
        # Initialize log processor
        log_processor = LogProcessor(redis_client, metrics_exporter)
        logger.info("✅ Log processor initialized")
        
        # Initialize file monitor
        file_monitor = LogFileMonitor(log_processor)
        logger.info("✅ File monitor initialized")
        
        # Initialize scheduler
        scheduler_manager = SchedulerManager(redis_client, metrics_exporter)
        logger.info("✅ Scheduler manager initialized")
        
        logger.success("🎉 All components initialized successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize components: {e}")
        return False

def start_background_services():
    """Start background monitoring and processing services."""
    logger.info("Starting background services...")
    
    try:
        # Start file monitoring
        if file_monitor:
            file_monitor.start()
            logger.info("✅ File monitor started")
        
        # Start scheduler
        if scheduler_manager:
            scheduler_manager.start()
            logger.info("✅ Scheduler started")
        
        logger.success("🚀 Background services started successfully!")
        
    except Exception as e:
        logger.error(f"❌ Failed to start background services: {e}")

def stop_background_services():
    """Stop all background services gracefully."""
    logger.info("Stopping background services...")
    
    try:
        if file_monitor:
            file_monitor.stop()
            logger.info("✅ File monitor stopped")
        
        if scheduler_manager:
            scheduler_manager.stop()
            logger.info("✅ Scheduler stopped")
        
        logger.success("🛑 Background services stopped successfully!")
        
    except Exception as e:
        logger.error(f"❌ Error stopping background services: {e}")

# API Routes
@app.route('/health')
def health_check():
    """Health check endpoint."""
    try:
        # Check Redis connection
        redis_status = redis_client.ping() if redis_client else False
        
        # Check file monitor status
        monitor_status = file_monitor.is_running() if file_monitor else False
        
        # Check scheduler status
        scheduler_status = scheduler_manager.is_running() if scheduler_manager else False
        
        # Calculate health score
        health_score = 0
        if redis_status:
            health_score += 25
        if monitor_status:
            health_score += 25
        if scheduler_status:
            health_score += 25
        if log_processor:
            health_score += 25
        
        system_health_gauge.set(health_score)
        
        status = {
            'status': 'healthy' if health_score >= 75 else 'degraded' if health_score >= 50 else 'unhealthy',
            'health_score': health_score,
            'components': {
                'redis': 'ok' if redis_status else 'error',
                'file_monitor': 'ok' if monitor_status else 'error',
                'scheduler': 'ok' if scheduler_status else 'error',
                'log_processor': 'ok' if log_processor else 'error'
            },
            'timestamp': logger._core.now().isoformat()
        }
        
        return jsonify(status), 200 if health_score >= 75 else 503
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/metrics')
def metrics():
    """Prometheus metrics endpoint."""
    try:
        return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}
    except Exception as e:
        logger.error(f"Metrics generation failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs')
def get_logs():
    """Get logs with filtering options."""
    try:
        # Parse query parameters
        source = request.args.get('source', 'all')
        level = request.args.get('level', 'all')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        
        # Get logs from processor
        logs = log_processor.get_logs(source=source, level=level, limit=limit, offset=offset)
        
        return jsonify({
            'logs': logs,
            'total': len(logs),
            'source': source,
            'level': level,
            'limit': limit,
            'offset': offset
        })
        
    except Exception as e:
        logger.error(f"Failed to retrieve logs: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs/search')
def search_logs():
    """Search logs by pattern."""
    try:
        query = request.args.get('q', '')
        source = request.args.get('source', 'all')
        limit = int(request.args.get('limit', 100))
        
        if not query:
            return jsonify({'error': 'Query parameter "q" is required'}), 400
        
        # Search logs
        results = log_processor.search_logs(query=query, source=source, limit=limit)
        
        return jsonify({
            'results': results,
            'query': query,
            'source': source,
            'total': len(results)
        })
        
    except Exception as e:
        logger.error(f"Log search failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def get_stats():
    """Get logging statistics."""
    try:
        stats = {
            'ingestion_rate': metrics_exporter.get_ingestion_rate(),
            'processing_latency': metrics_exporter.get_processing_latency(),
            'error_rate': metrics_exporter.get_error_rate(),
            'disk_usage': metrics_exporter.get_disk_usage(),
            'active_sources': log_processor.get_active_sources(),
            'total_logs_today': log_processor.get_logs_count_today()
        }

        return jsonify(stats)

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return jsonify({'error': str(e)}), 500

# MVP API Endpoints for Troubleshooting
@app.route('/logger/host=<host>')
def get_host_logs(host):
    """Get logs for a specific host. Format: /logger/host=ssdev"""
    try:
        application = request.args.get('application', 'all')
        component = request.args.get('component', 'all')
        log_type = request.args.get('log', 'recent')  # recent, lastrun, errors
        limit = int(request.args.get('limit', 50))

        # Get logs based on parameters
        if log_type == 'lastrun':
            # Get recent logs that might indicate last run status
            logs = log_processor.get_logs(host=host, application=application, component=component, limit=limit)
            # Filter for run-related messages
            logs = [log for log in logs if any(keyword in log.get('message', '').lower()
                   for keyword in ['started', 'completed', 'finished', 'run', 'execution'])]
        elif log_type == 'errors':
            # Get error logs
            logs = log_processor.get_logs(host=host, application=application, component=component, level='ERROR', limit=limit)
        else:
            # Get recent logs
            logs = log_processor.get_logs(host=host, application=application, component=component, limit=limit)

        response = {
            'host': host,
            'application': application,
            'component': component,
            'log_type': log_type,
            'count': len(logs),
            'logs': logs,
            'query_time': logger._core.now().isoformat()
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Failed to get host logs for {host}: {e}")
        return jsonify({'error': str(e), 'host': host}), 500

@app.route('/logger/troubleshoot/<host>/<application>')
def troubleshoot_application(host, application):
    """Troubleshoot specific application. Format: /logger/troubleshoot/ssdev/auto-scraper"""
    try:
        component = request.args.get('component', 'all')
        hours = int(request.args.get('hours', 1))  # Look back hours

        # Get recent logs
        recent_logs = log_processor.get_logs(host=host, application=application, component=component, limit=100)

        # Get error logs
        error_logs = log_processor.get_logs(host=host, application=application, component=component, level='ERROR', limit=20)

        # Analyze for common issues
        analysis = {
            'total_logs': len(recent_logs),
            'error_count': len(error_logs),
            'last_activity': recent_logs[0]['timestamp'] if recent_logs else 'No recent activity',
            'common_errors': _analyze_common_errors(error_logs),
            'status': 'healthy' if len(error_logs) == 0 else 'issues_detected'
        }

        response = {
            'host': host,
            'application': application,
            'component': component,
            'analysis': analysis,
            'recent_logs': recent_logs[:10],  # Last 10 logs
            'error_logs': error_logs[:5],     # Last 5 errors
            'query_time': logger._core.now().isoformat()
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Failed to troubleshoot {host}/{application}: {e}")
        return jsonify({'error': str(e), 'host': host, 'application': application}), 500

@app.route('/logger/components/<host>/<application>')
def list_components(host, application):
    """List all components for an application. Format: /logger/components/ssdev/auto-scraper"""
    try:
        # Get recent logs to identify active components
        logs = log_processor.get_logs(host=host, application=application, limit=200)

        # Extract unique components
        components = set()
        component_stats = {}

        for log in logs:
            comp = log.get('component', 'general')
            components.add(comp)

            if comp not in component_stats:
                component_stats[comp] = {
                    'log_count': 0,
                    'error_count': 0,
                    'last_activity': None
                }

            component_stats[comp]['log_count'] += 1
            if log.get('level') == 'ERROR':
                component_stats[comp]['error_count'] += 1

            if not component_stats[comp]['last_activity']:
                component_stats[comp]['last_activity'] = log.get('timestamp')

        response = {
            'host': host,
            'application': application,
            'components': list(components),
            'component_stats': component_stats,
            'total_components': len(components),
            'query_time': logger._core.now().isoformat()
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Failed to list components for {host}/{application}: {e}")
        return jsonify({'error': str(e), 'host': host, 'application': application}), 500

def _analyze_common_errors(error_logs):
    """Analyze common error patterns in logs."""
    try:
        if not error_logs:
            return []

        error_patterns = {}
        for log in error_logs:
            message = log.get('message', '').lower()

            # Categorize common errors
            if 'connection' in message or 'timeout' in message:
                error_type = 'connection_issues'
            elif 'permission' in message or 'access' in message:
                error_type = 'permission_issues'
            elif 'file not found' in message or 'no such file' in message:
                error_type = 'file_issues'
            elif 'database' in message or 'sql' in message:
                error_type = 'database_issues'
            elif 'api' in message or 'http' in message:
                error_type = 'api_issues'
            else:
                error_type = 'other_errors'

            if error_type not in error_patterns:
                error_patterns[error_type] = 0
            error_patterns[error_type] += 1

        # Return sorted list of error types
        return sorted(error_patterns.items(), key=lambda x: x[1], reverse=True)

    except Exception as e:
        logger.error(f"Failed to analyze common errors: {e}")
        return []

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    stop_background_services()
    sys.exit(0)

def main():
    """Main application entry point."""
    # Setup logging
    setup_logging()
    
    logger.info("🚀 Starting Centralized Logging Server")
    logger.info("=" * 50)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize components
    if not initialize_components():
        logger.error("❌ Failed to initialize components, exiting...")
        sys.exit(1)
    
    # Start background services
    start_background_services()
    
    # Get configuration
    host = os.environ.get('BIND_ADDRESS', '0.0.0.0')
    port = int(os.environ.get('LOGGING_SERVER_PORT', 8080))
    debug = os.environ.get('DEBUG_ENABLED', 'false').lower() == 'true'
    
    logger.info(f"🌐 Starting Flask server on {host}:{port}")
    logger.info(f"🔧 Debug mode: {debug}")
    logger.info("=" * 50)
    
    try:
        # Start Flask app
        app.run(host=host, port=port, debug=debug, threaded=True)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Server error: {e}")
    finally:
        stop_background_services()
        logger.info("🛑 Centralized Logging Server stopped")

if __name__ == '__main__':
    main()
