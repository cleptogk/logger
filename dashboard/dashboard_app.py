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
        
        # Set enhanced logging API URL
        logging_server_url = f"http://127.0.0.1:{os.environ.get('LOGGING_API_PORT', 8080)}"
        logger.info(f"✅ Enhanced Logging API URL: {logging_server_url}")
        
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

@app.route('/iptv-orchestrator')
def iptv_orchestrator_page():
    """IPTV Orchestrator monitoring page."""
    return render_template('iptv_orchestrator.html')

@app.route('/workflow-analysis')
def workflow_analysis_page():
    """Workflow analysis page."""
    return render_template('workflow_analysis.html')

# API Routes
@app.route('/api/dashboard/stats')
def get_dashboard_stats():
    """Get dashboard statistics from enhanced logging API."""
    try:
        # Get health status from enhanced logging API
        health_response = requests.get(f"{logging_server_url}/health", timeout=5)
        health_data = health_response.json() if health_response.status_code == 200 else {}

        # Get file information
        files_response = requests.get(f"{logging_server_url}/logger/files", timeout=5)
        files_data = files_response.json() if files_response.status_code == 200 else {}

        # Get recent logs for stats calculation
        recent_logs_response = requests.get(f"{logging_server_url}/logger/search/ssdev?time=today&limit=1000", timeout=10)
        recent_logs = recent_logs_response.json() if recent_logs_response.status_code == 200 else {}

        # Calculate stats from recent logs
        total_logs_today = recent_logs.get('pagination', {}).get('total_count', 0)
        analytics = recent_logs.get('analytics', {})
        level_distribution = analytics.get('level_distribution', {})

        # Calculate error rate
        error_count = level_distribution.get('ERROR', 0) + level_distribution.get('WARN', 0)
        error_rate = (error_count / total_logs_today * 100) if total_logs_today > 0 else 0

        # Build comprehensive stats
        stats = {
            'total_logs_today': total_logs_today,
            'ingestion_rate': calculate_ingestion_rate(recent_logs),
            'error_rate': error_rate,
            'disk_usage': get_disk_usage(),
            'health_data': health_data,
            'files_info': files_data,
            'analytics': analytics,
            'dashboard': {
                'active_connections': len(socketio.server.manager.rooms.get('/', {})),
                'uptime': get_dashboard_uptime(),
                'version': '2.0.0'
            }
        }

        return jsonify(stats)

    except Exception as e:
        logger.error(f"Failed to get dashboard stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/dashboard/logs')
def get_dashboard_logs():
    """Get logs for dashboard display using enhanced logging API."""
    try:
        # Build enhanced API request
        host = request.args.get('host', 'ssdev')
        application = request.args.get('application', '')
        component = request.args.get('component', '')
        level = request.args.get('level', '')
        search = request.args.get('search', '')
        time_filter = request.args.get('time', 'last 1 hour')
        limit = request.args.get('limit', 50)

        # Build API endpoint URL
        if component:
            endpoint = f"/logger/{component}/{host}"
        elif application:
            endpoint = f"/logger/host={host}"
        else:
            endpoint = f"/logger/search/{host}"

        # Build parameters
        params = {
            'limit': limit,
            'time': time_filter
        }

        if application:
            params['application'] = application
        if level:
            params['level'] = level
        if search:
            params['search'] = search

        response = requests.get(f"{logging_server_url}{endpoint}", params=params, timeout=10)

        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': 'Failed to fetch logs'}), response.status_code

    except Exception as e:
        logger.error(f"Failed to get logs: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/dashboard/search')
def search_dashboard_logs():
    """Search logs using enhanced logging API."""
    try:
        # Get search parameters
        query = request.args.get('q', '')
        host = request.args.get('host', 'ssdev')
        pattern = request.args.get('pattern', '')
        level = request.args.get('level', '')
        refresh_id = request.args.get('refresh_id', '')
        time_filter = request.args.get('time', 'last 1 hour')
        limit = request.args.get('limit', 100)

        if not query and not pattern and not refresh_id:
            return jsonify({'error': 'At least one search parameter (q, pattern, or refresh_id) is required'}), 400

        # Build enhanced search request
        params = {
            'limit': limit,
            'time': time_filter
        }

        if query:
            params['search'] = query
        if pattern:
            params['pattern'] = pattern
        if level:
            params['level'] = level
        if refresh_id:
            params['refresh_id'] = refresh_id

        response = requests.get(f"{logging_server_url}/logger/search/{host}", params=params, timeout=10)

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

@app.route('/api/dashboard/iptv-orchestrator')
def get_iptv_orchestrator_data():
    """Get IPTV orchestrator workflow data."""
    try:
        # Get IPTV orchestrator logs
        response = requests.get(f"{logging_server_url}/logger/iptv-orchestrator/ssdev",
                              params={'time': 'today', 'limit': 500}, timeout=10)

        if response.status_code == 200:
            data = response.json()

            # Process workflow data
            workflows = process_workflow_data(data.get('results', []))
            analytics = data.get('analytics', {})

            return jsonify({
                'workflows': workflows,
                'analytics': analytics,
                'total_workflows': len(workflows),
                'success_rate': calculate_success_rate(workflows)
            })
        else:
            return jsonify({'error': 'Failed to fetch IPTV orchestrator data'}), response.status_code

    except Exception as e:
        logger.error(f"Failed to get IPTV orchestrator data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/dashboard/workflow/<refresh_id>')
def get_workflow_details(refresh_id):
    """Get detailed workflow information for a specific refresh ID."""
    try:
        response = requests.get(f"{logging_server_url}/logger/search/ssdev",
                              params={'refresh_id': refresh_id, 'limit': 100}, timeout=10)

        if response.status_code == 200:
            data = response.json()
            workflow_steps = process_workflow_steps(data.get('results', []))

            return jsonify({
                'refresh_id': refresh_id,
                'steps': workflow_steps,
                'total_duration': calculate_total_duration(workflow_steps),
                'status': determine_workflow_status(workflow_steps)
            })
        else:
            return jsonify({'error': 'Failed to fetch workflow details'}), response.status_code

    except Exception as e:
        logger.error(f"Failed to get workflow details: {e}")
        return jsonify({'error': str(e)}), 500

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

def calculate_ingestion_rate(recent_logs):
    """Calculate log ingestion rate from recent logs."""
    try:
        results = recent_logs.get('results', [])
        if not results:
            return 0

        # Calculate logs per minute based on recent activity
        # This is a simplified calculation
        return len(results) / 60  # Assuming results are from last hour
    except:
        return 0

def get_disk_usage():
    """Get disk usage percentage."""
    try:
        import shutil
        total, used, free = shutil.disk_usage('/var/log/centralized')
        return (used / total) * 100
    except:
        return 0

def process_workflow_data(log_results):
    """Process log results to extract workflow information."""
    workflows = {}

    for log_entry in log_results:
        metadata = log_entry.get('metadata', {})
        refresh_id = metadata.get('refresh_id')

        if refresh_id:
            if refresh_id not in workflows:
                workflows[refresh_id] = {
                    'refresh_id': refresh_id,
                    'steps': [],
                    'start_time': log_entry.get('timestamp'),
                    'status': 'in_progress'
                }

            step_number = metadata.get('step_number')
            step_status = metadata.get('step_status')
            duration = metadata.get('duration_seconds')

            if step_number:
                workflows[refresh_id]['steps'].append({
                    'step': step_number,
                    'status': step_status,
                    'duration': duration,
                    'timestamp': log_entry.get('timestamp'),
                    'message': log_entry.get('message')
                })

    return list(workflows.values())

def calculate_success_rate(workflows):
    """Calculate workflow success rate."""
    if not workflows:
        return 0

    successful = sum(1 for w in workflows if w.get('status') == 'completed')
    return (successful / len(workflows)) * 100

def process_workflow_steps(log_results):
    """Process log results to extract detailed step information."""
    steps = []

    for log_entry in log_results:
        metadata = log_entry.get('metadata', {})
        step_number = metadata.get('step_number')

        if step_number:
            steps.append({
                'step': step_number,
                'status': metadata.get('step_status', 'unknown'),
                'duration': metadata.get('duration_seconds'),
                'timestamp': log_entry.get('timestamp'),
                'message': log_entry.get('message'),
                'level': log_entry.get('level')
            })

    return sorted(steps, key=lambda x: x['step'])

def calculate_total_duration(workflow_steps):
    """Calculate total workflow duration."""
    durations = [step.get('duration', 0) for step in workflow_steps if step.get('duration')]
    return sum(durations) if durations else 0

def determine_workflow_status(workflow_steps):
    """Determine overall workflow status from steps."""
    if not workflow_steps:
        return 'unknown'

    failed_steps = [step for step in workflow_steps if step.get('status') == 'failed']
    if failed_steps:
        return 'failed'

    completed_steps = [step for step in workflow_steps if step.get('status') == 'completed']
    if len(completed_steps) >= 8:  # All 8 steps completed
        return 'completed'

    return 'in_progress'

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
