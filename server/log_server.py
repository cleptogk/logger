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
