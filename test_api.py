#!/usr/bin/env python3
"""
Simple test API server for MVP logging functionality.
This bypasses the complex metrics setup for initial testing.
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from flask import Flask, jsonify, request

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

app = Flask(__name__)

# Simple in-memory storage for testing
logs_storage = []
log_files_cache = {}

def scan_log_files():
    """Scan centralized log directory for log files."""
    log_dir = Path('/var/log/centralized')
    files_found = {}
    
    if not log_dir.exists():
        return files_found
    
    for host_dir in log_dir.iterdir():
        if host_dir.is_dir():
            host = host_dir.name
            files_found[host] = []
            
            for log_file in host_dir.rglob('*.log'):
                if log_file.is_file():
                    files_found[host].append({
                        'path': str(log_file),
                        'size': log_file.stat().st_size,
                        'modified': log_file.stat().st_mtime
                    })
    
    return files_found

def read_recent_logs(host, limit=50):
    """Read recent logs from host log files."""
    log_dir = Path(f'/var/log/centralized/{host}')
    logs = []
    
    if not log_dir.exists():
        return logs
    
    for log_file in log_dir.rglob('*.log'):
        if log_file.is_file():
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    
                for line in lines[-limit:]:
                    line = line.strip()
                    if line:
                        logs.append({
                            'timestamp': datetime.now().isoformat(),
                            'host': host,
                            'application': 'unknown',
                            'component': 'general',
                            'level': 'INFO',
                            'message': line,
                            'file_path': str(log_file)
                        })
            except Exception as e:
                print(f"Error reading {log_file}: {e}")
    
    return logs[-limit:]

@app.route('/health')
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0-mvp'
    })

@app.route('/logger/host=<host>')
def get_host_logs(host):
    """Get logs for a specific host. Format: /logger/host=ssdev"""
    try:
        application = request.args.get('application', 'all')
        component = request.args.get('component', 'all')
        log_type = request.args.get('log', 'recent')
        limit = int(request.args.get('limit', 50))
        
        # Read logs from files
        logs = read_recent_logs(host, limit)
        
        # Filter by application if specified
        if application != 'all':
            logs = [log for log in logs if application.lower() in log.get('message', '').lower()]
        
        # Filter by component if specified
        if component != 'all':
            logs = [log for log in logs if component.lower() in log.get('message', '').lower()]
        
        # Filter by log type
        if log_type == 'errors':
            logs = [log for log in logs if any(keyword in log.get('message', '').lower() 
                   for keyword in ['error', 'exception', 'failed', 'critical'])]
        elif log_type == 'lastrun':
            logs = [log for log in logs if any(keyword in log.get('message', '').lower() 
                   for keyword in ['started', 'completed', 'finished', 'run', 'execution'])]
        
        response = {
            'host': host,
            'application': application,
            'component': component,
            'log_type': log_type,
            'count': len(logs),
            'logs': logs,
            'query_time': datetime.now().isoformat()
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': str(e), 'host': host}), 500

@app.route('/logger/troubleshoot/<host>/<application>')
def troubleshoot_application(host, application):
    """Troubleshoot specific application. Format: /logger/troubleshoot/ssdev/auto-scraper"""
    try:
        component = request.args.get('component', 'all')
        
        # Get recent logs
        recent_logs = read_recent_logs(host, 100)
        
        # Filter by application
        app_logs = [log for log in recent_logs if application.lower() in log.get('message', '').lower()]
        
        # Filter by component if specified
        if component != 'all':
            app_logs = [log for log in app_logs if component.lower() in log.get('message', '').lower()]
        
        # Get error logs
        error_logs = [log for log in app_logs if any(keyword in log.get('message', '').lower() 
                     for keyword in ['error', 'exception', 'failed', 'critical'])]
        
        # Simple analysis
        analysis = {
            'total_logs': len(app_logs),
            'error_count': len(error_logs),
            'last_activity': app_logs[0]['timestamp'] if app_logs else 'No recent activity',
            'status': 'healthy' if len(error_logs) == 0 else 'issues_detected'
        }
        
        response = {
            'host': host,
            'application': application,
            'component': component,
            'analysis': analysis,
            'recent_logs': app_logs[:10],
            'error_logs': error_logs[:5],
            'query_time': datetime.now().isoformat()
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': str(e), 'host': host, 'application': application}), 500

@app.route('/logger/components/<host>/<application>')
def list_components(host, application):
    """List all components for an application. Format: /logger/components/ssdev/auto-scraper"""
    try:
        # Get recent logs
        logs = read_recent_logs(host, 200)
        
        # Filter by application
        app_logs = [log for log in logs if application.lower() in log.get('message', '').lower()]
        
        # Extract potential components from messages
        components = set()
        component_patterns = {
            'list-creator': ['list.creator', 'list_creator', 'list creator'],
            'epg-processor': ['epg.processor', 'epg_processor', 'epg processor'],
            'channel-scanner': ['channel.scanner', 'channel_scanner', 'channel scanner'],
            'scheduler': ['scheduler', 'cron', 'schedule'],
            'api': ['api', 'route', 'endpoint', 'flask'],
            'database': ['database', 'db', 'sql', 'sqlite']
        }
        
        component_stats = {}
        
        for log in app_logs:
            message = log.get('message', '').lower()
            found_component = 'general'
            
            for comp, patterns in component_patterns.items():
                if any(pattern in message for pattern in patterns):
                    found_component = comp
                    break
            
            components.add(found_component)
            
            if found_component not in component_stats:
                component_stats[found_component] = {
                    'log_count': 0,
                    'error_count': 0,
                    'last_activity': None
                }
            
            component_stats[found_component]['log_count'] += 1
            if any(keyword in message for keyword in ['error', 'exception', 'failed']):
                component_stats[found_component]['error_count'] += 1
            
            if not component_stats[found_component]['last_activity']:
                component_stats[found_component]['last_activity'] = log.get('timestamp')
        
        response = {
            'host': host,
            'application': application,
            'components': list(components),
            'component_stats': component_stats,
            'total_components': len(components),
            'query_time': datetime.now().isoformat()
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': str(e), 'host': host, 'application': application}), 500

@app.route('/logger/files')
def list_log_files():
    """List all available log files."""
    try:
        files = scan_log_files()
        return jsonify({
            'log_files': files,
            'total_hosts': len(files),
            'query_time': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting MVP Logging API Server")
    print("=" * 50)
    
    host = os.environ.get('BIND_ADDRESS', '0.0.0.0')
    port = int(os.environ.get('LOGGING_SERVER_PORT', 8080))
    
    print(f"🌐 Starting Flask server on {host}:{port}")
    print("📋 Available endpoints:")
    print("  - /health")
    print("  - /logger/host=<host>?application=<app>&component=<comp>&log=<type>")
    print("  - /logger/troubleshoot/<host>/<application>")
    print("  - /logger/components/<host>/<application>")
    print("  - /logger/files")
    print("=" * 50)
    
    app.run(host=host, port=port, debug=False)
