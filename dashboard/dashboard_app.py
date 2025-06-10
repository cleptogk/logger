#!/usr/bin/env python3
"""
Centralized Logging Dashboard
Web-based dashboard for log visualization and monitoring.
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Use basic logging instead of missing dependencies
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from flask import Flask, render_template, jsonify, request
import requests

# Import SocketIO with graceful fallback
try:
    from flask_socketio import SocketIO, emit
    SOCKETIO_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ flask_socketio not available, real-time features disabled")
    SOCKETIO_AVAILABLE = False
    # Create mock SocketIO class for graceful degradation
    class MockSocketIO:
        def __init__(self, app, **kwargs):
            self.app = app
        def emit(self, *args, **kwargs):
            pass
        def on(self, event):
            def decorator(f):
                return f
            return decorator
    SocketIO = MockSocketIO
    def emit(*args, **kwargs):
        pass

# Initialize Flask app with memory optimizations
app = Flask(__name__,
           template_folder='../web/templates',
           static_folder='../web/static')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

# Configure Flask for memory efficiency
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max request size
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 300  # 5 minutes cache
app.config['JSON_SORT_KEYS'] = False  # Don't sort JSON keys to save CPU

# Initialize SocketIO for real-time updates with memory limits
socketio = SocketIO(app, cors_allowed_origins="*",
                   max_http_buffer_size=1024*1024,  # 1MB buffer
                   ping_timeout=30,  # 30 second timeout
                   ping_interval=10)  # 10 second ping interval

# Global components
redis_client = None
logging_server_url = None

# Initialize Redis client with graceful fallback
try:
    # Try to import Redis client utilities
    import sys
    sys.path.append("/opt/logging")
    from server.utils.redis_client import RedisClient
    redis_client = RedisClient()
    if redis_client.ping():
        logger.info("✅ Redis client connected successfully")
    else:
        redis_client = None
        logger.warning("⚠️ Redis ping failed, using file-based storage")
except ImportError as e:
    redis_client = None
    logger.warning(f"⚠️ Redis client not available, using file-based storage: {e}")
except Exception as e:
    redis_client = None
    logger.warning(f"⚠️ Redis unavailable, using file-based storage: {e}")

def validate_dependencies():
    """Validate all required dependencies and configurations."""
    issues = []

    # Check Flask
    try:
        from flask import __version__ as flask_version
        logger.info(f"✅ Flask {flask_version} available")
    except ImportError:
        issues.append("Flask not available")

    # Check requests
    try:
        import requests
        logger.info(f"✅ Requests {requests.__version__} available")
    except ImportError:
        issues.append("Requests library not available")

    # Check SocketIO (optional)
    if SOCKETIO_AVAILABLE:
        logger.info("✅ Flask-SocketIO available - real-time features enabled")
    else:
        logger.warning("⚠️ Flask-SocketIO not available - using mock implementation")

    # Check Redis (optional)
    if redis_client:
        logger.info("✅ Redis client available")
    else:
        logger.info("ℹ️ Redis client not available - using file-based storage")

    return issues

def initialize_dashboard():
    """Initialize dashboard components with comprehensive validation."""
    global redis_client, logging_server_url

    logger.info("🚀 Initializing logging dashboard...")

    try:
        # Validate dependencies first
        dependency_issues = validate_dependencies()
        if dependency_issues:
            logger.warning(f"⚠️ Dependency issues found: {', '.join(dependency_issues)}")

        # Set enhanced logging API URL with validation
        api_port = os.environ.get('LOGGING_API_PORT', '8080')
        logging_server_url = f"http://127.0.0.1:{api_port}"
        logger.info(f"🔗 Enhanced Logging API URL: {logging_server_url}")

        # Test API connectivity
        try:
            test_response = requests.get(f"{logging_server_url}/health", timeout=3)
            if test_response.status_code == 200:
                logger.info("✅ Logging API connectivity verified")
            else:
                logger.warning(f"⚠️ Logging API returned status {test_response.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ Could not verify logging API connectivity: {e}")

        # Initialize SocketIO if available
        if SOCKETIO_AVAILABLE:
            logger.info("✅ Real-time features enabled via SocketIO")
        else:
            logger.info("ℹ️ Real-time features disabled - using polling fallback")

        logger.info("🎉 Dashboard initialized successfully!")
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

        # Get stats from the new /api/stats endpoint
        stats_response = requests.get(f"{logging_server_url}/api/stats", timeout=10)
        api_stats = stats_response.json() if stats_response.status_code == 200 else {}

        # Get recent logs for additional processing - limit to reduce memory usage
        recent_logs_response = requests.get(f"{logging_server_url}/api/logs?source=ssdev&limit=50", timeout=5)
        recent_logs_data = recent_logs_response.json() if recent_logs_response.status_code == 200 else {}
        logs_list = recent_logs_data.get('logs', [])

        # Use API stats or calculate from logs
        total_logs_today = api_stats.get('total_logs_today', len(logs_list))

        # Calculate level distribution from recent logs - limit processing
        level_distribution = {}
        for log in logs_list[:50]:  # Only process first 50 logs
            level = log.get('level', 'UNKNOWN')
            level_distribution[level] = level_distribution.get(level, 0) + 1

        analytics = {
            'level_distribution': level_distribution,
            'active_sources': api_stats.get('active_sources', []),
            'ingestion_rate': api_stats.get('ingestion_rate', 0),
            'recent_logs': logs_list[:10]  # Last 10 logs for recent activity
        }

        # Calculate error rate
        error_count = level_distribution.get('ERROR', 0) + level_distribution.get('WARN', 0)
        error_rate = (error_count / total_logs_today * 100) if total_logs_today > 0 else 0

        # Build comprehensive stats
        stats = {
            'total_logs_today': total_logs_today,
            'ingestion_rate': api_stats.get('ingestion_rate', calculate_ingestion_rate(recent_logs_data)),
            'error_rate': api_stats.get('error_rate', error_rate),
            'disk_usage': api_stats.get('disk_usage', get_disk_usage()),
            'health_data': health_data,
            'files_info': files_data,
            'analytics': analytics,
            'api_stats': api_stats,  # Include raw API stats
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

        response = requests.get(f"{logging_server_url}{endpoint}", params=params, timeout=20)

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
        component = request.args.get('component', '')
        time_filter = request.args.get('time', 'last 1 hour')
        limit = request.args.get('limit', 100)

        # Allow searches with just host, component, and time parameters
        # For host-only searches, we'll search for all logs from that host
        if not query and not pattern and not refresh_id and not component:
            # If no specific search terms, search for all logs from the host
            query = '*'  # Use wildcard to get all logs

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
            params['search'] = refresh_id  # Use search parameter for refresh_id
        if component:
            params['component'] = component

        response = requests.get(f"{logging_server_url}/logger/search/{host}", params=params, timeout=20)

        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': 'Search failed'}), response.status_code

    except Exception as e:
        logger.error(f"Search failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/dashboard/health')
def dashboard_health():
    """Comprehensive dashboard health check."""
    try:
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'components': {},
            'dependencies': {},
            'api_connectivity': {},
            'system_info': {}
        }

        # Check logging server health
        try:
            if logging_server_url:
                response = requests.get(f"{logging_server_url}/health", timeout=5)
                if response.status_code == 200:
                    server_health = response.json()
                    health_status['components']['logging_server'] = 'healthy'
                    health_status['api_connectivity']['logging_api'] = server_health
                else:
                    health_status['components']['logging_server'] = 'degraded'
                    health_status['status'] = 'degraded'
            else:
                health_status['components']['logging_server'] = 'not_configured'
                health_status['status'] = 'degraded'
        except Exception as e:
            health_status['components']['logging_server'] = 'error'
            health_status['api_connectivity']['logging_api_error'] = str(e)
            health_status['status'] = 'degraded'

        # Check dependencies
        health_status['dependencies']['flask_socketio'] = 'available' if SOCKETIO_AVAILABLE else 'missing'
        health_status['dependencies']['redis_client'] = 'available' if redis_client else 'disabled'
        health_status['dependencies']['requests'] = 'available'

        # Check SocketIO status
        health_status['components']['socketio'] = 'available' if SOCKETIO_AVAILABLE else 'mock'

        # System information
        health_status['system_info']['python_path'] = sys.path[:3]  # First 3 entries
        health_status['system_info']['working_directory'] = os.getcwd()
        health_status['system_info']['logging_server_url'] = logging_server_url

        # Test IPTV orchestrator endpoint
        try:
            if logging_server_url:
                test_response = requests.get(f"{logging_server_url}/logger/search/ssdev",
                                           params={'search': 'test', 'limit': 1}, timeout=3)
                health_status['api_connectivity']['iptv_search'] = 'available' if test_response.status_code == 200 else 'error'
        except Exception as e:
            health_status['api_connectivity']['iptv_search'] = f'error: {str(e)}'

        return jsonify(health_status)

    except Exception as e:
        logger.error(f"Dashboard health check failed: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/dashboard/system-status')
def system_status():
    """Detailed system status for debugging."""
    try:
        import platform
        import psutil

        status = {
            'platform': {
                'system': platform.system(),
                'python_version': platform.python_version(),
                'architecture': platform.architecture()[0]
            },
            'memory': {
                'available_mb': psutil.virtual_memory().available // 1024 // 1024,
                'percent_used': psutil.virtual_memory().percent
            },
            'environment': {
                'logging_api_port': os.environ.get('LOGGING_API_PORT', '8080'),
                'secret_key_set': bool(os.environ.get('SECRET_KEY')),
                'flask_env': os.environ.get('FLASK_ENV', 'production')
            },
            'flask_config': {
                'max_content_length': app.config.get('MAX_CONTENT_LENGTH'),
                'send_file_max_age': app.config.get('SEND_FILE_MAX_AGE_DEFAULT'),
                'json_sort_keys': app.config.get('JSON_SORT_KEYS')
            }
        }

        return jsonify(status)

    except ImportError:
        return jsonify({'error': 'psutil not available for system monitoring'}), 503
    except Exception as e:
        logger.error(f"System status check failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/dashboard/iptv-orchestrator')
def get_iptv_orchestrator_data():
    """Get IPTV orchestrator workflow data with enhanced error handling."""
    try:
        if not logging_server_url:
            logger.error("Logging server URL not initialized")
            return jsonify({'error': 'Logging server not available'}), 503

        # Use search endpoint with multiple fallback strategies
        search_params = {
            'search': 'Refresh-',
            'component': 'iptv-orchestrator',
            'time': 'today',
            'limit': 100
        }

        logger.info(f"Fetching IPTV orchestrator data from {logging_server_url}/logger/search/ssdev")
        response = requests.get(f"{logging_server_url}/logger/search/ssdev",
                              params=search_params, timeout=15)

        if response.status_code == 200:
            data = response.json()
            logger.info(f"Successfully fetched {len(data.get('results', []))} log entries")

            # Process workflow data from search results
            workflows = process_workflow_data(data.get('results', []))
            analytics = data.get('analytics', {})

            result = {
                'workflows': workflows,
                'analytics': analytics,
                'total_workflows': len(workflows),
                'success_rate': calculate_success_rate(workflows),
                'last_updated': datetime.now().isoformat(),
                'data_source': 'enhanced_api'
            }

            logger.info(f"Processed {len(workflows)} workflows with {result['success_rate']:.1f}% success rate")
            return jsonify(result)

        elif response.status_code == 404:
            logger.warning("IPTV orchestrator endpoint not found, trying fallback")
            # Fallback to general search
            fallback_response = requests.get(f"{logging_server_url}/logger/search/ssdev",
                                           params={'search': 'iptv-orchestrator', 'time': 'today', 'limit': 50},
                                           timeout=10)
            if fallback_response.status_code == 200:
                data = fallback_response.json()
                workflows = process_workflow_data(data.get('results', []))
                return jsonify({
                    'workflows': workflows,
                    'total_workflows': len(workflows),
                    'success_rate': calculate_success_rate(workflows),
                    'analytics': {'note': 'Using fallback search'},
                    'data_source': 'fallback_search'
                })

        logger.error(f"API request failed with status {response.status_code}: {response.text}")
        return jsonify({'error': f'API request failed: {response.status_code}'}), response.status_code

    except requests.exceptions.Timeout:
        logger.error("Timeout while fetching IPTV orchestrator data")
        return jsonify({'error': 'Request timeout - logging server may be overloaded'}), 504
    except requests.exceptions.ConnectionError:
        logger.error("Connection error while fetching IPTV orchestrator data")
        return jsonify({'error': 'Cannot connect to logging server'}), 503
    except Exception as e:
        logger.error(f"Unexpected error getting IPTV orchestrator data: {e}")
        # Return empty data structure instead of error to prevent UI from breaking
        return jsonify({
            'workflows': [],
            'total_workflows': 0,
            'success_rate': 0,
            'analytics': {
                'component_distribution': {},
                'level_distribution': {},
                'refresh_distribution': {},
                'error': str(e)
            },
            'data_source': 'error_fallback'
        })

@app.route('/api/dashboard/workflow/<refresh_id>')
def get_workflow_details(refresh_id):
    """Get detailed workflow information for a specific refresh ID."""
    try:
        # Use the same search pattern as the main IPTV orchestrator endpoint
        # but filter for the specific refresh ID
        response = requests.get(f"{logging_server_url}/logger/search/ssdev",
                              params={'search': refresh_id, 'component': 'iptv-orchestrator',
                                     'time': 'today', 'limit': 100}, timeout=20)

        if response.status_code == 200:
            data = response.json()
            all_results = data.get('results', [])

            # Filter results to only include logs for this specific refresh ID
            filtered_results = []
            for log_entry in all_results:
                message = log_entry.get('message', '')
                metadata = log_entry.get('metadata', {})

                # Check if this log entry belongs to the requested refresh ID
                if (refresh_id in message or
                    metadata.get('refresh_id') == refresh_id):
                    filtered_results.append(log_entry)

            logger.info(f"Found {len(filtered_results)} log entries for {refresh_id}")
            workflow_steps = process_workflow_steps(filtered_results)

            return jsonify({
                'refresh_id': refresh_id,
                'steps': workflow_steps,
                'total_duration': calculate_total_duration(workflow_steps),
                'status': determine_workflow_status(workflow_steps)
            })
        else:
            logger.error(f"API request failed with status {response.status_code}: {response.text}")
            return jsonify({'error': 'Failed to fetch workflow details'}), response.status_code

    except Exception as e:
        logger.error(f"Failed to get workflow details for {refresh_id}: {e}")
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
        logs_list = recent_logs.get('logs', [])
        if not logs_list:
            return 0

        # Calculate logs per minute based on recent activity
        # This is a simplified calculation
        return len(logs_list) / 60  # Assuming logs are from last hour
    except:
        return 0

def get_disk_usage():
    """Get disk usage percentage."""
    try:
        import shutil
        total, used, _ = shutil.disk_usage('/var/log/centralized')
        return (used / total) * 100
    except:
        return 0

def process_workflow_data(log_results):
    """Process log results to extract workflow information."""
    workflows = {}

    for log_entry in log_results:
        metadata = log_entry.get('metadata', {})
        refresh_id = metadata.get('refresh_id')
        message = log_entry.get('message', '')

        # Extract refresh_id from message if not in metadata
        if not refresh_id and '[Refresh-' in message:
            import re
            match = re.search(r'\[Refresh-(\d+)\]', message)
            if match:
                refresh_id = f"Refresh-{match.group(1)}"

        if refresh_id:
            if refresh_id not in workflows:
                workflows[refresh_id] = {
                    'refresh_id': refresh_id,
                    'steps': {},  # Use dict to avoid duplicates
                    'start_time': log_entry.get('timestamp'),
                    'status': 'in_progress'
                }

            # Extract step information from message
            step_number = metadata.get('step_number')
            if not step_number and 'Step ' in message:
                import re
                match = re.search(r'Step (\d+)/8', message)
                if match:
                    step_number = int(match.group(1))

            if step_number:
                step_status = metadata.get('step_status')
                duration = metadata.get('duration_seconds')

                # Determine status from message if not in metadata
                if not step_status:
                    if 'completed successfully' in message:
                        step_status = 'completed'
                    elif 'failed' in message.lower():
                        step_status = 'failed'
                    elif message.strip().endswith(':'):
                        step_status = 'started'
                    else:
                        step_status = 'unknown'

                # Extract duration from message if not in metadata
                if not duration and 'in ' in message and 'seconds' in message:
                    import re
                    match = re.search(r'in ([\d.]+) seconds', message)
                    if match:
                        duration = float(match.group(1))

                # Only keep the latest status for each step
                step_key = step_number
                if step_key not in workflows[refresh_id]['steps'] or step_status == 'completed':
                    workflows[refresh_id]['steps'][step_key] = {
                        'step': step_number,
                        'status': step_status,
                        'duration': duration,
                        'timestamp': log_entry.get('timestamp'),
                        'message': message
                    }

    # Convert steps dict back to list and determine final status
    for workflow in workflows.values():
        steps_list = list(workflow['steps'].values())
        workflow['steps'] = sorted(steps_list, key=lambda x: x['step'])

        # Determine final workflow status
        completed_steps = [s for s in steps_list if s['status'] == 'completed']
        failed_steps = [s for s in steps_list if s['status'] == 'failed']

        if failed_steps:
            workflow['status'] = 'failed'
        elif len(completed_steps) >= 8:
            workflow['status'] = 'completed'
        else:
            workflow['status'] = 'in_progress'

    return list(workflows.values())

def calculate_success_rate(workflows):
    """Calculate workflow success rate."""
    if not workflows:
        return 0

    successful = sum(1 for w in workflows if w.get('status') == 'completed')
    return (successful / len(workflows)) * 100

def process_workflow_steps(log_results):
    """Process log results to extract detailed step information."""
    steps = {}  # Use dict to avoid duplicates and keep latest status

    for log_entry in log_results:
        metadata = log_entry.get('metadata', {})
        message = log_entry.get('message', '')

        # Get step number from metadata or parse from message
        step_number = metadata.get('step_number')
        if not step_number and 'Step ' in message:
            import re
            match = re.search(r'Step (\d+)/8', message)
            if match:
                step_number = int(match.group(1))

        if step_number:
            # Get step status from metadata or parse from message
            step_status = metadata.get('step_status')
            if not step_status:
                if 'completed successfully' in message:
                    step_status = 'completed'
                elif 'failed' in message.lower():
                    step_status = 'failed'
                elif message.strip().endswith(':'):
                    step_status = 'started'
                else:
                    step_status = 'unknown'

            # Get duration from metadata or parse from message
            duration = metadata.get('duration_seconds')
            if not duration and 'in ' in message and 'seconds' in message:
                import re
                match = re.search(r'in ([\d.]+) seconds', message)
                if match:
                    duration = float(match.group(1))

            # Only keep the latest status for each step (prefer completed status)
            step_key = step_number
            if step_key not in steps or step_status == 'completed':
                steps[step_key] = {
                    'step': step_number,
                    'status': step_status,
                    'duration': duration,
                    'timestamp': log_entry.get('timestamp'),
                    'message': message,
                    'level': log_entry.get('level')
                }

    # Convert to sorted list
    return sorted(steps.values(), key=lambda x: x['step'])

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
    # Basic logging already configured
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
        socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
    finally:
        logger.info("🛑 Centralized Logging Dashboard stopped")

# Initialize dashboard when module is imported (for gunicorn)
# Call initialization without app context since it doesn't need Flask request context
initialize_dashboard()

if __name__ == '__main__':
    main()
