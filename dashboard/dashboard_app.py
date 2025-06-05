#!/usr/bin/env python3
"""
Centralized Logging Dashboard
Web-based dashboard for log visualization and monitoring.
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import requests
from loguru import logger

from server.utils.loguru_config import setup_logging
from server.utils.redis_client import RedisClient

# Initialize Flask app
app = Flask(__name__, 
           template_folder='../web/templates',
           static_folder='../web/static')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

# Initialize SocketIO for real-time updates
socketio = SocketIO(app, cors_allowed_origins="*")

# Global components
redis_client = None
logging_server_url = None

def initialize_dashboard():
    """Initialize dashboard components."""
    global redis_client, logging_server_url
    
    logger.info("Initializing logging dashboard...")
    
    try:
        # Initialize Redis client
        redis_client = RedisClient()
        logger.info("✅ Redis client initialized")
        
        # Set logging server URL
        logging_server_url = f"http://127.0.0.1:{os.environ.get('LOGGING_SERVER_PORT', 8080)}"
        logger.info(f"✅ Logging server URL: {logging_server_url}")
        
        logger.success("🎉 Dashboard initialized successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize dashboard: {e}")
        return False

# Web Routes
@app.route('/')
def dashboard():
    """Main dashboard page."""
    return render_template('dashboard.html')

@app.route('/logs')
def log_viewer():
    """Log viewer page."""
    return render_template('log_viewer.html')

@app.route('/metrics')
def metrics_page():
    """Metrics and monitoring page."""
    return render_template('metrics.html')

# API Routes
@app.route('/api/dashboard/stats')
def get_dashboard_stats():
    """Get dashboard statistics."""
    try:
        # Get stats from logging server
        response = requests.get(f"{logging_server_url}/api/stats", timeout=5)
        if response.status_code == 200:
            stats = response.json()
        else:
            stats = {'error': 'Failed to fetch stats from logging server'}
        
        # Add dashboard-specific stats
        stats['dashboard'] = {
            'active_connections': len(socketio.server.manager.rooms.get('/', {})),
            'uptime': get_dashboard_uptime(),
            'version': '1.0.0'
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Failed to get dashboard stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/dashboard/logs')
def get_dashboard_logs():
    """Get logs for dashboard display."""
    try:
        # Forward request to logging server
        params = {
            'source': request.args.get('source', 'all'),
            'level': request.args.get('level', 'all'),
            'limit': request.args.get('limit', 50),
            'offset': request.args.get('offset', 0)
        }
        
        response = requests.get(f"{logging_server_url}/api/logs", params=params, timeout=10)
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': 'Failed to fetch logs'}), response.status_code
            
    except Exception as e:
        logger.error(f"Failed to get logs: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/dashboard/search')
def search_dashboard_logs():
    """Search logs from dashboard."""
    try:
        # Forward search request to logging server
        params = {
            'q': request.args.get('q', ''),
            'source': request.args.get('source', 'all'),
            'limit': request.args.get('limit', 100)
        }
        
        if not params['q']:
            return jsonify({'error': 'Query parameter "q" is required'}), 400
        
        response = requests.get(f"{logging_server_url}/api/logs/search", params=params, timeout=10)
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': 'Search failed'}), response.status_code
            
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/dashboard/health')
def dashboard_health():
    """Dashboard health check."""
    try:
        # Check logging server health
        response = requests.get(f"{logging_server_url}/health", timeout=5)
        server_health = response.json() if response.status_code == 200 else {'status': 'error'}
        
        # Check Redis connection
        redis_status = redis_client.ping() if redis_client else False
        
        dashboard_health = {
            'status': 'healthy' if redis_status and server_health.get('status') == 'healthy' else 'degraded',
            'components': {
                'redis': 'ok' if redis_status else 'error',
                'logging_server': server_health.get('status', 'error'),
                'socketio': 'ok'
            },
            'server_health': server_health,
            'timestamp': logger._core.now().isoformat()
        }
        
        return jsonify(dashboard_health)
        
    except Exception as e:
        logger.error(f"Dashboard health check failed: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# WebSocket Events
@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    logger.info(f"Client connected: {request.sid}")
    emit('status', {'message': 'Connected to logging dashboard'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    logger.info(f"Client disconnected: {request.sid}")

@socketio.on('subscribe_logs')
def handle_subscribe_logs(data):
    """Handle log subscription."""
    source = data.get('source', 'all')
    level = data.get('level', 'all')
    
    logger.info(f"Client {request.sid} subscribed to logs: source={source}, level={level}")
    
    # Join room for filtered logs
    room = f"logs_{source}_{level}"
    socketio.server.enter_room(request.sid, room)
    
    emit('subscription_confirmed', {
        'source': source,
        'level': level,
        'room': room
    })

@socketio.on('unsubscribe_logs')
def handle_unsubscribe_logs():
    """Handle log unsubscription."""
    logger.info(f"Client {request.sid} unsubscribed from logs")
    
    # Leave all log rooms
    rooms = socketio.server.manager.get_rooms(request.sid, '/')
    for room in rooms:
        if room.startswith('logs_'):
            socketio.server.leave_room(request.sid, room)
    
    emit('unsubscription_confirmed')

def broadcast_log_update(log_entry):
    """Broadcast log update to subscribed clients."""
    try:
        source = log_entry.get('source', 'unknown')
        level = log_entry.get('level', 'info')
        
        # Broadcast to specific rooms
        rooms = [
            f"logs_all_all",
            f"logs_{source}_all",
            f"logs_all_{level}",
            f"logs_{source}_{level}"
        ]
        
        for room in rooms:
            socketio.emit('log_update', log_entry, room=room)
            
    except Exception as e:
        logger.error(f"Failed to broadcast log update: {e}")

def broadcast_metrics_update(metrics):
    """Broadcast metrics update to all clients."""
    try:
        socketio.emit('metrics_update', metrics, broadcast=True)
    except Exception as e:
        logger.error(f"Failed to broadcast metrics update: {e}")

def get_dashboard_uptime():
    """Get dashboard uptime in seconds."""
    # This would be implemented with a start time tracker
    return 0

def main():
    """Main dashboard entry point."""
    # Setup logging
    setup_logging()
    
    logger.info("🚀 Starting Centralized Logging Dashboard")
    logger.info("=" * 50)
    
    # Initialize dashboard
    if not initialize_dashboard():
        logger.error("❌ Failed to initialize dashboard, exiting...")
        sys.exit(1)
    
    # Get configuration
    host = os.environ.get('BIND_ADDRESS', '0.0.0.0')
    port = int(os.environ.get('WEB_DASHBOARD_PORT', 8081))
    debug = os.environ.get('DEBUG_ENABLED', 'false').lower() == 'true'
    
    logger.info(f"🌐 Starting dashboard server on {host}:{port}")
    logger.info(f"🔧 Debug mode: {debug}")
    logger.info("=" * 50)
    
    try:
        # Start SocketIO app
        socketio.run(app, host=host, port=port, debug=debug)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
    finally:
        logger.info("🛑 Centralized Logging Dashboard stopped")

if __name__ == '__main__':
    main()
