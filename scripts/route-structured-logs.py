#!/usr/bin/env python3
"""
Structured Log Router for rsyslog
Parses ROUTE| prefixed messages and writes them to appropriate step-specific files.
"""

import sys
import os
import re
from pathlib import Path
from datetime import datetime

# Base log directory
LOG_BASE_DIR = Path('/var/log/centralized')

def parse_structured_message(log_line):
    """
    Parse a structured log message.
    Expected format: TIMESTAMP HOSTNAME TAG ROUTE|host|app|component|refresh_id|step_name|actual_message
    """
    # Extract the message part (everything after the syslog header)
    # Format: "2025-06-17T14:30:45-07:00 ssdev sports_scheduler: ROUTE|ssdev|sports-scheduler|iptv-orchestrator|123|step1-purge_xtream|[Refresh-123] Step 1/9: ..."
    
    # Find the ROUTE| prefix in the message
    route_match = re.search(r'ROUTE\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|(.*)', log_line)
    if not route_match:
        return None
    
    host = route_match.group(1)
    app = route_match.group(2)
    component = route_match.group(3)
    refresh_id = route_match.group(4)
    step_name = route_match.group(5)
    actual_message = route_match.group(6)
    
    # Extract timestamp and hostname from the beginning of the log line
    timestamp_match = re.match(r'^(\S+)\s+(\S+)\s+(\S+)\s+', log_line)
    if timestamp_match:
        timestamp = timestamp_match.group(1)
        hostname = timestamp_match.group(2)
        tag = timestamp_match.group(3)
    else:
        timestamp = datetime.now().isoformat()
        hostname = 'unknown'
        tag = 'unknown'
    
    return {
        'timestamp': timestamp,
        'hostname': hostname,
        'tag': tag,
        'host': host,
        'app': app,
        'component': component,
        'refresh_id': refresh_id,
        'step_name': step_name,
        'message': actual_message
    }

def write_to_step_file(parsed_log):
    """Write the log entry to the appropriate step-specific file."""
    # Build the file path: /var/log/centralized/host/app/component/refresh_id/step_name.log
    log_dir = LOG_BASE_DIR / parsed_log['host'] / parsed_log['app'] / parsed_log['component'] / parsed_log['refresh_id']
    log_file = log_dir / f"{parsed_log['step_name']}.log"
    
    # Create directory if it doesn't exist
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Format the log entry (without the ROUTE| prefix)
    formatted_log = f"{parsed_log['timestamp']} {parsed_log['hostname']} {parsed_log['tag']} {parsed_log['message']}\n"
    
    # Write to file
    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(formatted_log)
        return True
    except Exception as e:
        # Log error to stderr (rsyslog will capture this)
        print(f"ERROR: Failed to write to {log_file}: {e}", file=sys.stderr)
        return False

def main():
    """Main processing loop - read from stdin and route messages."""
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            
            # Only process lines with ROUTE| prefix
            if 'ROUTE|' not in line:
                continue
            
            # Parse the structured message
            parsed_log = parse_structured_message(line)
            if not parsed_log:
                print(f"WARNING: Failed to parse structured message: {line}", file=sys.stderr)
                continue
            
            # Write to appropriate file
            success = write_to_step_file(parsed_log)
            if not success:
                print(f"ERROR: Failed to route message: {line}", file=sys.stderr)
    
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"FATAL: Structured log router error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
