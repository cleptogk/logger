#!/usr/bin/env python3
"""
Simple test API server for MVP logging functionality.
This bypasses the complex metrics setup for initial testing.
"""

import os
import sys
import json
import time
import re
import pytz
from pathlib import Path
from datetime import datetime, timedelta
from flask import Flask, jsonify, request

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

app = Flask(__name__)

# Simple in-memory storage for testing
logs_storage = []
log_files_cache = {}

# Enhanced component patterns for detailed tracking
COMPONENT_PATTERNS = {
    'sports-scheduler': {
        'iptv-orchestrator': {
            'patterns': [r'iptv.?refresh', r'orchestrator', r'workflow', r'sports_scheduler\.iptv_orchestrator', r'\[Refresh-\d+\]'],
            'steps': {
                'step-1': [r'step\s*1/8', r'step\s*1\s*:', r'purge.*xtream', r'purging.*xtream.*provider.*data'],
                'step-2': [r'step\s*2/8', r'step\s*2\s*:', r'refresh.*xtream.*channels', r'refreshing.*xtream.*channels'],
                'step-3': [r'step\s*3/8', r'step\s*3\s*:', r'refresh.*xtream.*epg', r'refreshing.*xtream.*epg.*data'],
                'step-4': [r'step\s*4/8', r'step\s*4\s*:', r'purge.*epg.*database', r'purging.*epg.*database'],
                'step-5': [r'step\s*5/8', r'step\s*5\s*:', r'refresh.*epg.*database', r'refreshing.*epg.*database'],
                'step-6': [r'step\s*6/8', r'step\s*6\s*:', r'generat.*sports.*playlist', r'generating.*sports.*playlist'],
                'step-7': [r'step\s*7/8', r'step\s*7\s*:', r'refresh.*channels.*dvr', r'refreshing.*channels.*dvr'],
                'step-8': [r'step\s*8/8', r'step\s*8\s*:', r'process.*automated.*record', r'automated.*record.*rules']
            }
        },
        'epg-processor': {
            'patterns': [r'epg.?processor', r'epg.?refresh', r'xmltv'],
            'steps': {
                'fetch': [r'fetch.*epg', r'downloading.*epg', r'getting.*epg'],
                'parse': [r'parse.*epg', r'parsing.*xmltv', r'processing.*epg'],
                'store': [r'store.*epg', r'saving.*epg', r'database.*insert']
            }
        },
        'channel-scanner': {
            'patterns': [r'channel.?scanner', r'scan.*channels', r'channel.?refresh'],
            'steps': {
                'scan': [r'scanning.*channels', r'channel.*scan', r'discovering.*channels'],
                'filter': [r'filter.*channels', r'filtering.*channels', r'channel.*filter'],
                'update': [r'update.*channels', r'updating.*channels', r'channel.*update']
            }
        },
        'playlist-generator': {
            'patterns': [r'playlist.?generator', r'generate.*playlist', r'm3u.*generation'],
            'steps': {
                'filter': [r'filter.*channels', r'filtering.*sports', r'channel.*filtering'],
                'generate': [r'generate.*m3u', r'creating.*playlist', r'playlist.*generation'],
                'upload': [r'upload.*playlist', r'deploying.*playlist', r'playlist.*upload']
            }
        },
        'scheduler': {
            'patterns': [r'scheduler', r'cron', r'schedule.*task'],
            'steps': {
                'trigger': [r'trigger.*job', r'starting.*job', r'job.*triggered'],
                'execute': [r'execute.*job', r'running.*job', r'job.*execution'],
                'complete': [r'complete.*job', r'job.*completed', r'job.*finished']
            }
        }
    },
    'auto-scraper': {
        'list-creator': {
            'patterns': [r'list.?creator', r'list.?creation', r'create.*list'],
            'steps': {
                'init': [r'init.*list', r'starting.*list.*creation', r'list.*job.*start'],
                'fetch': [r'fetch.*items', r'getting.*items', r'retrieving.*items'],
                'filter': [r'filter.*items', r'filtering.*items', r'item.*filter'],
                'process': [r'process.*items', r'processing.*items', r'item.*processing'],
                'create': [r'create.*list', r'creating.*list', r'list.*creation'],
                'publish': [r'publish.*list', r'publishing.*trakt', r'trakt.*publish']
            }
        },
        'scraper': {
            'patterns': [r'scraper', r'scrape.*job', r'scraping'],
            'steps': {
                'init': [r'init.*scrape', r'starting.*scrape', r'scrape.*job.*start'],
                'fetch': [r'fetch.*media', r'getting.*media', r'retrieving.*media'],
                'parse': [r'parse.*media', r'parsing.*media', r'media.*parsing'],
                'store': [r'store.*media', r'saving.*media', r'media.*storage']
            }
        },
        'trakt-sync': {
            'patterns': [r'trakt.?sync', r'trakt.?service', r'sync.*trakt'],
            'steps': {
                'auth': [r'trakt.*auth', r'authenticate.*trakt', r'trakt.*login'],
                'fetch': [r'fetch.*trakt', r'getting.*trakt', r'trakt.*fetch'],
                'sync': [r'sync.*trakt', r'syncing.*trakt', r'trakt.*sync'],
                'update': [r'update.*trakt', r'updating.*trakt', r'trakt.*update']
            }
        },
        'scheduler': {
            'patterns': [r'scheduler', r'cron', r'schedule.*job'],
            'steps': {
                'trigger': [r'trigger.*job', r'starting.*job', r'job.*triggered'],
                'execute': [r'execute.*job', r'running.*job', r'job.*execution'],
                'complete': [r'complete.*job', r'job.*completed', r'job.*finished']
            }
        }
    }
}

def parse_time_filter(time_str):
    """Parse time filter string into datetime objects with Pacific timezone support."""
    if not time_str:
        return None, None

    try:
        # Use Pacific timezone (PDT/PST)
        pacific_tz = pytz.timezone('America/Los_Angeles')

        # Handle different time formats
        if 'yesterday' in time_str.lower():
            # Get yesterday in Pacific timezone
            now_pacific = datetime.now(pacific_tz)
            yesterday_pacific = now_pacific - timedelta(days=1)

            if 'around' in time_str.lower() and ('am' in time_str.lower() or 'pm' in time_str.lower()):
                # Extract time like "yesterday around 7am"
                time_match = re.search(r'(\d{1,2})\s*(am|pm)', time_str.lower())
                if time_match:
                    hour = int(time_match.group(1))
                    if time_match.group(2) == 'pm' and hour != 12:
                        hour += 12
                    elif time_match.group(2) == 'am' and hour == 12:
                        hour = 0

                    start_time = yesterday_pacific.replace(hour=hour, minute=0, second=0, microsecond=0)
                    end_time = start_time + timedelta(hours=2)  # 2-hour window
                    return start_time, end_time
            else:
                # Whole day yesterday
                start_time = yesterday_pacific.replace(hour=0, minute=0, second=0, microsecond=0)
                end_time = yesterday_pacific.replace(hour=23, minute=59, second=59, microsecond=999999)
                return start_time, end_time

        elif 'today' in time_str.lower():
            # Get today in Pacific timezone
            now_pacific = datetime.now(pacific_tz)

            if 'around' in time_str.lower() and ('am' in time_str.lower() or 'pm' in time_str.lower()):
                # Extract time like "today around 2pm"
                time_match = re.search(r'(\d{1,2})\s*(am|pm)', time_str.lower())
                if time_match:
                    hour = int(time_match.group(1))
                    if time_match.group(2) == 'pm' and hour != 12:
                        hour += 12
                    elif time_match.group(2) == 'am' and hour == 12:
                        hour = 0

                    start_time = now_pacific.replace(hour=hour, minute=0, second=0, microsecond=0)
                    end_time = start_time + timedelta(hours=2)  # 2-hour window
                    return start_time, end_time
            else:
                # Whole day today
                start_time = now_pacific.replace(hour=0, minute=0, second=0, microsecond=0)
                end_time = now_pacific.replace(hour=23, minute=59, second=59, microsecond=999999)
                return start_time, end_time

        elif 'last' in time_str.lower() and 'hour' in time_str.lower():
            end_time = datetime.now(pacific_tz)
            start_time = end_time - timedelta(hours=1)
            return start_time, end_time

        elif 'last' in time_str.lower() and 'minutes' in time_str.lower():
            # Extract number like "last 30 minutes"
            minutes_match = re.search(r'(\d+)\s*minutes', time_str.lower())
            if minutes_match:
                minutes = int(minutes_match.group(1))
                end_time = datetime.now(pacific_tz)
                start_time = end_time - timedelta(minutes=minutes)
                return start_time, end_time

        # Try to parse ISO format
        elif 'T' in time_str:
            parsed_time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            start_time = parsed_time - timedelta(minutes=30)
            end_time = parsed_time + timedelta(minutes=30)
            return start_time, end_time

    except Exception as e:
        print(f"Error parsing time filter '{time_str}': {e}")

    return None, None

def identify_component_and_step(application, message):
    """Identify component and step from log message."""
    if application not in COMPONENT_PATTERNS:
        return 'general', None

    message_lower = message.lower()

    # Check each component
    for component, config in COMPONENT_PATTERNS[application].items():
        # Check if message matches component patterns
        for pattern in config['patterns']:
            if re.search(pattern, message_lower):
                # Found component, now check for specific steps
                if 'steps' in config:
                    for step, step_patterns in config['steps'].items():
                        for step_pattern in step_patterns:
                            if re.search(step_pattern, message_lower):
                                return component, step
                return component, None

    return 'general', None

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

def extract_timestamp_from_log_line(line):
    """Extract timestamp from log line with timezone awareness."""
    pacific_tz = pytz.timezone('America/Los_Angeles')

    # Try different timestamp formats
    timestamp_patterns = [
        r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+[+-]\d{2}:\d{2})',  # ISO format with timezone
        r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})',  # Standard format
        r'(\w{3} \d{2} \d{2}:\d{2}:\d{2})',  # Syslog format
    ]

    for pattern in timestamp_patterns:
        match = re.search(pattern, line)
        if match:
            timestamp_str = match.group(1)
            try:
                if 'T' in timestamp_str and ('+' in timestamp_str or '-' in timestamp_str[-6:]):
                    # ISO format with timezone (like 2025-06-06T07:18:31.234567-07:00)
                    parsed_time = datetime.fromisoformat(timestamp_str)
                    # Convert to Pacific timezone if not already
                    if parsed_time.tzinfo is None:
                        parsed_time = pacific_tz.localize(parsed_time)
                    return parsed_time
                elif 'T' in timestamp_str:
                    # ISO format without timezone
                    parsed_time = datetime.fromisoformat(timestamp_str.replace('Z', ''))
                    return pacific_tz.localize(parsed_time)
                elif '-' in timestamp_str:
                    # Standard format - assume Pacific timezone
                    parsed_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    return pacific_tz.localize(parsed_time)
                else:
                    # Syslog format - assume current year and Pacific timezone
                    current_year = datetime.now().year
                    parsed_time = datetime.strptime(f"{current_year} {timestamp_str}", '%Y %b %d %H:%M:%S')
                    return pacific_tz.localize(parsed_time)
            except Exception as e:
                print(f"Error parsing timestamp '{timestamp_str}': {e}")
                continue

    # Fallback to current time in Pacific timezone
    return datetime.now(pacific_tz)

def read_logs_with_filters(host, application=None, component=None, step=None,
                          start_time=None, end_time=None, limit=1000,
                          search_query=None, pattern=None, level_filter=None,
                          refresh_id=None, offset=0):
    """Read logs from host log files with advanced filtering.

    Args:
        host: Target host name
        application: Application filter
        component: Component filter
        step: Step filter
        start_time: Start time filter
        end_time: End time filter
        limit: Maximum number of results
        search_query: Full-text search query
        pattern: Regex pattern for matching
        level_filter: Comma-separated log levels (ERROR,WARN,INFO)
        refresh_id: Specific refresh ID to filter by
        offset: Pagination offset
    """
    log_dir = Path(f'/var/log/centralized/{host}')
    logs = []

    if not log_dir.exists():
        return logs

    # Determine which application to look for
    app_filter = application.lower() if application and application != 'all' else None

    for log_file in log_dir.rglob('*.log'):
        if log_file.is_file():
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()

                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    # Extract timestamp
                    log_timestamp = extract_timestamp_from_log_line(line)

                    # Apply time filtering
                    if start_time and log_timestamp < start_time:
                        continue
                    if end_time and log_timestamp > end_time:
                        continue

                    # Determine application from message content
                    detected_app = 'unknown'
                    if app_filter:
                        # Check if application filter matches anywhere in the line
                        if app_filter.lower() in line.lower() or app_filter.replace('-', '_') in line:
                            detected_app = app_filter
                        else:
                            continue  # Skip if application filter doesn't match
                    else:
                        # Try to detect application from enhanced logging patterns
                        if ('sports_scheduler.' in line or 'sports-scheduler' in line.lower() or
                            'iptv' in line.lower() or 'orchestrator' in line.lower() or
                            'Step' in line or '[Refresh-' in line or
                            'refresh workflow' in line.lower()):
                            detected_app = 'sports-scheduler'
                        elif ('auto_scraper.' in line or 'auto-scraper' in line.lower() or
                              'scraper' in line.lower() or 'list creator' in line.lower()):
                            detected_app = 'auto-scraper'
                        elif 'nginx' in line.lower():
                            detected_app = 'nginx'
                        elif 'gunicorn' in line.lower():
                            detected_app = 'gunicorn'

                    # Identify component and step
                    detected_component, detected_step = identify_component_and_step(detected_app, line)

                    # Apply component filtering
                    if component and component != 'all' and component != detected_component:
                        continue

                    # Apply step filtering
                    if step and step != 'all' and step != detected_step:
                        continue

                    # Determine log level
                    level = 'INFO'
                    line_lower = line.lower()
                    if any(word in line_lower for word in ['error', 'exception', 'failed', 'critical']):
                        level = 'ERROR'
                    elif any(word in line_lower for word in ['warn', 'warning']):
                        level = 'WARNING'
                    elif any(word in line_lower for word in ['debug', 'trace']):
                        level = 'DEBUG'

                    # Advanced filtering
                    # 1. Full-text search
                    if search_query and search_query.lower() not in line.lower():
                        continue

                    # 2. Regex pattern matching
                    if pattern:
                        try:
                            if not re.search(pattern, line, re.IGNORECASE):
                                continue
                        except re.error:
                            # Invalid regex pattern, skip this filter
                            pass

                    # 3. Log level filtering
                    if level_filter:
                        allowed_levels = [l.strip().upper() for l in level_filter.split(',')]
                        if level not in allowed_levels:
                            continue

                    # 4. Refresh ID filtering
                    if refresh_id:
                        # Support both old and new refresh ID formats
                        if (f'[{refresh_id}]' not in line and
                            f'[Refresh-{refresh_id.replace("Refresh-", "")}]' not in line):
                            continue

                    # Extract enhanced metadata from new logging format
                    metadata = {}

                    # Extract step information (enhanced format: Step X/8)
                    step_match = re.search(r'step\s*(\d+)(?:/8)?', line, re.IGNORECASE)
                    if step_match:
                        metadata['step_number'] = int(step_match.group(1))

                    # Extract refresh ID (enhanced format: [Refresh-XX])
                    refresh_match = re.search(r'\[Refresh-(\d+)\]', line)
                    if refresh_match:
                        metadata['refresh_id'] = f"Refresh-{refresh_match.group(1)}"

                    # Extract timing information (enhanced format: "in X.XX seconds")
                    timing_match = re.search(r'(?:in\s+)?(\d+\.?\d*)\s*seconds?', line, re.IGNORECASE)
                    if timing_match:
                        metadata['duration_seconds'] = float(timing_match.group(1))

                    # Detect step status
                    if 'completed successfully' in line.lower():
                        metadata['step_status'] = 'completed'
                    elif 'failed' in line.lower():
                        metadata['step_status'] = 'failed'
                    elif re.search(r'step\s*\d+/8:', line, re.IGNORECASE) and 'completed' not in line.lower():
                        metadata['step_status'] = 'started'
                    elif 'starting.*workflow' in line.lower():
                        metadata['step_status'] = 'workflow_started'

                    log_entry = {
                        'timestamp': log_timestamp.isoformat(),
                        'host': host,
                        'application': detected_app,
                        'component': detected_component,
                        'step': detected_step,
                        'level': level,
                        'message': line,
                        'file_path': str(log_file),
                        'metadata': metadata
                    }

                    logs.append(log_entry)

                    if len(logs) >= limit:
                        break

            except Exception as e:
                print(f"Error reading {log_file}: {e}")

    # Sort by timestamp (newest first)
    logs.sort(key=lambda x: x['timestamp'], reverse=True)

    # Apply pagination
    if offset > 0:
        logs = logs[offset:]

    return logs[:limit]

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
    """Get logs for a specific host with advanced filtering. Format: /logger/host=ssdev"""
    try:
        # Basic filtering parameters
        application = request.args.get('application', 'all')
        component = request.args.get('component', 'all')
        step = request.args.get('step', 'all')
        log_type = request.args.get('log', 'recent')
        time_filter = request.args.get('time', None)
        limit = int(request.args.get('limit', 100))

        # Advanced filtering parameters
        search_query = request.args.get('search')      # Full-text search
        pattern = request.args.get('pattern')          # Regex pattern matching
        level_filter = request.args.get('level')       # Log level filtering (ERROR,WARN,INFO)
        refresh_id = request.args.get('refresh_id')    # Specific refresh ID filtering
        offset = int(request.args.get('offset', 0))    # Pagination offset

        # Parse time filter
        start_time, end_time = parse_time_filter(time_filter)

        # Read logs with enhanced filtering
        logs = read_logs_with_filters(
            host=host,
            application=application,
            component=component,
            step=step,
            start_time=start_time,
            end_time=end_time,
            limit=limit + offset,  # Get extra logs for pagination
            search_query=search_query,
            pattern=pattern,
            level_filter=level_filter,
            refresh_id=refresh_id,
            offset=offset
        )

        # Additional filtering by log type
        if log_type == 'errors':
            logs = [log for log in logs if log.get('level') == 'ERROR']
        elif log_type == 'lastrun':
            logs = [log for log in logs if any(keyword in log.get('message', '').lower()
                   for keyword in ['started', 'completed', 'finished', 'run', 'execution'])]

        response = {
            'host': host,
            'application': application,
            'component': component,
            'step': step,
            'log_type': log_type,
            'time_filter': time_filter,
            'time_range': {
                'start': start_time.isoformat() if start_time else None,
                'end': end_time.isoformat() if end_time else None
            },
            'advanced_filters': {
                'search_query': search_query,
                'pattern': pattern,
                'level_filter': level_filter,
                'refresh_id': refresh_id
            },
            'pagination': {
                'limit': limit,
                'offset': offset,
                'returned_count': len(logs)
            },
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
        time_filter = request.args.get('time', 'last 1 hour')

        # Parse time filter
        start_time, end_time = parse_time_filter(time_filter)

        # Get recent logs with filtering
        app_logs = read_logs_with_filters(
            host=host,
            application=application,
            component=component,
            start_time=start_time,
            end_time=end_time,
            limit=200
        )

        # Get error logs
        error_logs = [log for log in app_logs if log.get('level') == 'ERROR']

        # Analyze components and steps
        components_found = set()
        steps_found = set()
        for log in app_logs:
            if log.get('component'):
                components_found.add(log['component'])
            if log.get('step'):
                steps_found.add(log['step'])

        # Simple analysis
        analysis = {
            'total_logs': len(app_logs),
            'error_count': len(error_logs),
            'components_active': list(components_found),
            'steps_detected': list(steps_found),
            'last_activity': app_logs[0]['timestamp'] if app_logs else 'No recent activity',
            'status': 'healthy' if len(error_logs) == 0 else 'issues_detected',
            'time_range': {
                'start': start_time.isoformat() if start_time else None,
                'end': end_time.isoformat() if end_time else None
            }
        }

        response = {
            'host': host,
            'application': application,
            'component': component,
            'time_filter': time_filter,
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
        time_filter = request.args.get('time', 'last 1 hour')

        # Parse time filter
        start_time, end_time = parse_time_filter(time_filter)

        # Get recent logs with filtering
        app_logs = read_logs_with_filters(
            host=host,
            application=application,
            start_time=start_time,
            end_time=end_time,
            limit=500
        )

        # Extract components and steps
        components = set()
        component_stats = {}
        step_stats = {}

        for log in app_logs:
            component = log.get('component', 'general')
            step = log.get('step')

            components.add(component)

            # Component stats
            if component not in component_stats:
                component_stats[component] = {
                    'log_count': 0,
                    'error_count': 0,
                    'steps': set(),
                    'last_activity': None
                }

            component_stats[component]['log_count'] += 1
            if log.get('level') == 'ERROR':
                component_stats[component]['error_count'] += 1

            if step:
                component_stats[component]['steps'].add(step)

            if not component_stats[component]['last_activity']:
                component_stats[component]['last_activity'] = log.get('timestamp')

            # Step stats
            if step:
                step_key = f"{component}:{step}"
                if step_key not in step_stats:
                    step_stats[step_key] = {
                        'log_count': 0,
                        'error_count': 0,
                        'last_activity': None
                    }

                step_stats[step_key]['log_count'] += 1
                if log.get('level') == 'ERROR':
                    step_stats[step_key]['error_count'] += 1

                if not step_stats[step_key]['last_activity']:
                    step_stats[step_key]['last_activity'] = log.get('timestamp')

        # Convert sets to lists for JSON serialization
        for comp_stat in component_stats.values():
            comp_stat['steps'] = list(comp_stat['steps'])

        response = {
            'host': host,
            'application': application,
            'time_filter': time_filter,
            'time_range': {
                'start': start_time.isoformat() if start_time else None,
                'end': end_time.isoformat() if end_time else None
            },
            'components': list(components),
            'component_stats': component_stats,
            'step_stats': step_stats,
            'total_components': len(components),
            'total_logs': len(app_logs),
            'query_time': datetime.now().isoformat()
        }

        return jsonify(response)

    except Exception as e:
        return jsonify({'error': str(e), 'host': host, 'application': application}), 500

@app.route('/logger/iptv-orchestrator/<host>')
def get_iptv_orchestrator_logs(host):
    """Get IPTV orchestrator step logs. Format: /logger/iptv-orchestrator/ssdev?step=6&time=yesterday around 7am"""
    try:
        step = request.args.get('step', 'all')
        time_filter = request.args.get('time', 'last 1 hour')

        # Parse time filter
        start_time, end_time = parse_time_filter(time_filter)

        # Get IPTV orchestrator logs
        logs = read_logs_with_filters(
            host=host,
            application='sports-scheduler',
            component='iptv-orchestrator',
            step=f'step-{step}' if step != 'all' else 'all',
            start_time=start_time,
            end_time=end_time,
            limit=200
        )

        # Organize by steps
        steps_data = {}
        for log in logs:
            step_key = log.get('step', 'unknown')
            if step_key not in steps_data:
                steps_data[step_key] = {
                    'logs': [],
                    'error_count': 0,
                    'total_count': 0
                }

            steps_data[step_key]['logs'].append(log)
            steps_data[step_key]['total_count'] += 1
            if log.get('level') == 'ERROR':
                steps_data[step_key]['error_count'] += 1

        # Sort logs within each step by timestamp
        for step_data in steps_data.values():
            step_data['logs'].sort(key=lambda x: x['timestamp'], reverse=True)

        response = {
            'host': host,
            'component': 'iptv-orchestrator',
            'step_filter': step,
            'time_filter': time_filter,
            'time_range': {
                'start': start_time.isoformat() if start_time else None,
                'end': end_time.isoformat() if end_time else None
            },
            'steps': steps_data,
            'total_logs': len(logs),
            'query_time': datetime.now().isoformat()
        }

        return jsonify(response)

    except Exception as e:
        return jsonify({'error': str(e), 'host': host}), 500

@app.route('/logger/search/<host>')
def advanced_search(host):
    """Advanced search endpoint with full filtering capabilities.
    Format: /logger/search/ssdev?search=database locked&pattern=Step [1-3]/8&level=ERROR&refresh_id=Refresh-14"""
    try:
        # All filtering parameters
        application = request.args.get('application', 'all')
        component = request.args.get('component', 'all')
        step = request.args.get('step', 'all')
        time_filter = request.args.get('time', 'last 1 hour')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))

        # Advanced search parameters
        search_query = request.args.get('search')
        pattern = request.args.get('pattern')
        level_filter = request.args.get('level')
        refresh_id = request.args.get('refresh_id')

        # Parse time filter
        start_time, end_time = parse_time_filter(time_filter)

        # Perform advanced search
        logs = read_logs_with_filters(
            host=host,
            application=application,
            component=component,
            step=step,
            start_time=start_time,
            end_time=end_time,
            limit=limit + offset,
            search_query=search_query,
            pattern=pattern,
            level_filter=level_filter,
            refresh_id=refresh_id,
            offset=offset
        )

        # Search analytics
        total_before_filters = len(logs) + offset if offset > 0 else len(logs)

        # Group results by different criteria for analysis
        level_counts = {}
        component_counts = {}
        refresh_counts = {}

        for log in logs:
            # Level distribution
            level = log.get('level', 'UNKNOWN')
            level_counts[level] = level_counts.get(level, 0) + 1

            # Component distribution
            comp = log.get('component', 'unknown')
            component_counts[comp] = component_counts.get(comp, 0) + 1

            # Refresh ID distribution
            message = log.get('message', '')
            refresh_match = re.search(r'\[Refresh-(\d+)\]', message)
            if refresh_match:
                refresh_id_found = f"Refresh-{refresh_match.group(1)}"
                refresh_counts[refresh_id_found] = refresh_counts.get(refresh_id_found, 0) + 1

        response = {
            'host': host,
            'search_parameters': {
                'application': application,
                'component': component,
                'step': step,
                'time_filter': time_filter,
                'search_query': search_query,
                'pattern': pattern,
                'level_filter': level_filter,
                'refresh_id': refresh_id
            },
            'pagination': {
                'limit': limit,
                'offset': offset,
                'returned_count': len(logs),
                'estimated_total': total_before_filters
            },
            'analytics': {
                'level_distribution': level_counts,
                'component_distribution': component_counts,
                'refresh_distribution': refresh_counts
            },
            'time_range': {
                'start': start_time.isoformat() if start_time else None,
                'end': end_time.isoformat() if end_time else None
            },
            'results': logs,
            'query_time': datetime.now().isoformat()
        }

        return jsonify(response)

    except Exception as e:
        return jsonify({'error': str(e), 'host': host}), 500

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

# Enhanced API Endpoints for Dashboard Compatibility
@app.route('/api/stats')
def get_stats():
    """Get logging statistics for dashboard."""
    try:
        # Get file information
        files = scan_log_files()

        # Calculate basic stats
        total_files = sum(len(host_files) for host_files in files.values())
        active_hosts = [host for host, host_files in files.items() if host_files]

        # Get recent logs for rate calculation
        recent_logs = get_logs_for_host('ssdev', limit=100)

        # Calculate basic metrics
        stats = {
            'ingestion_rate': len(recent_logs) / 60 if recent_logs else 0,  # logs per minute
            'processing_latency': 0.1,  # seconds
            'error_rate': calculate_error_rate(recent_logs),
            'disk_usage': get_total_disk_usage(files),
            'active_sources': active_hosts,
            'total_logs_today': len(recent_logs),
            'total_files': total_files,
            'timestamp': datetime.now().isoformat()
        }

        return jsonify(stats)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs')
def get_logs_api():
    """Get logs with filtering options for dashboard compatibility."""
    try:
        # Parse query parameters
        source = request.args.get('source', 'ssdev')
        level = request.args.get('level', 'all')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))

        # Get logs from the specified source
        logs = get_logs_for_host(source, limit=limit + offset)

        # Apply level filtering
        if level != 'all':
            logs = [log for log in logs if log.get('level') == level.upper()]

        # Apply pagination
        if offset > 0:
            logs = logs[offset:]
        logs = logs[:limit]

        return jsonify({
            'logs': logs,
            'total': len(logs),
            'source': source,
            'level': level,
            'limit': limit,
            'offset': offset,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs/search')
def search_logs_api():
    """Search logs by pattern for dashboard compatibility."""
    try:
        query = request.args.get('q', '')
        source = request.args.get('source', 'ssdev')
        limit = int(request.args.get('limit', 100))

        if not query:
            return jsonify({'error': 'Query parameter "q" is required'}), 400

        # Get logs and search
        all_logs = get_logs_for_host(source, limit=1000)
        results = []

        for log in all_logs:
            if query.lower() in log.get('message', '').lower():
                results.append(log)
                if len(results) >= limit:
                    break

        return jsonify({
            'results': results,
            'query': query,
            'source': source,
            'total': len(results),
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Helper functions for enhanced API endpoints
def get_logs_for_host(host, limit=100):
    """Get logs for a specific host using existing functionality."""
    try:
        # Use the existing read_logs_with_filters function
        logs = read_logs_with_filters(
            host=host,
            application=None,
            component=None,
            step=None,
            start_time=None,
            end_time=None,
            limit=limit,
            offset=0
        )
        return logs
    except Exception as e:
        print(f"Error getting logs for host {host}: {e}")
        return []

def calculate_error_rate(logs):
    """Calculate error rate from logs."""
    if not logs:
        return 0

    error_count = sum(1 for log in logs if log.get('level') in ['ERROR', 'WARN'])
    return (error_count / len(logs)) * 100

def get_total_disk_usage(files):
    """Calculate total disk usage from file information."""
    try:
        total_size = 0
        for host_files in files.values():
            for file_info in host_files:
                total_size += file_info.get('size', 0)

        # Convert to MB
        return total_size / (1024 * 1024)
    except:
        return 0

if __name__ == '__main__':
    print("🚀 Starting MVP Logging API Server")
    print("=" * 50)
    
    host = os.environ.get('BIND_ADDRESS', '0.0.0.0')
    port = int(os.environ.get('LOGGING_SERVER_PORT', 8080))
    
    print(f"🌐 Starting Flask server on {host}:{port}")
    print("📋 Available endpoints:")
    print("  - /health")
    print("  - /logger/host=<host>?application=<app>&component=<comp>&log=<type>")
    print("  - /logger/search/<host>?search=<query>&pattern=<regex>&level=<levels>")
    print("  - /logger/troubleshoot/<host>/<application>")
    print("  - /logger/components/<host>/<application>")
    print("  - /logger/iptv-orchestrator/<host>?step=<step>&time=<time>")
    print("  - /logger/files")
    print("=" * 50)
    
    app.run(host=host, port=port, debug=False)
