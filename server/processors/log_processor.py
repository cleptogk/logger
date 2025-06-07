"""
Log Processor Module
Processes and analyzes log entries from various sources.
"""

import re
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from loguru import logger

class LogProcessor:
    """Processes and analyzes log entries."""
    
    def __init__(self, redis_client, metrics_exporter):
        """Initialize log processor."""
        self.redis = redis_client
        self.metrics = metrics_exporter
        
        # Log parsing patterns
        self.patterns = {
            'rsyslog': re.compile(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+[+-]\d{2}:\d{2})\s+(.+)$'),
            'application': re.compile(r'^\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]\s+(\w+)\s+(.+)$'),
            'generic': re.compile(r'^(.+)$')
        }
        
        # Host/application mapping based on file paths
        self.path_mappings = {
            '/var/log/centralized/ssdev/': {'host': 'ssdev', 'applications': ['sports-scheduler', 'auto-scraper', 'nginx', 'gunicorn']},
            '/var/log/centralized/ssdvr/': {'host': 'ssdvr', 'applications': ['ssdvr', 'channels-dvr', 'nginx']},
            '/var/log/centralized/ssmcp/': {'host': 'ssmcp', 'applications': ['ansible', 'git', 'nginx']},
            '/var/log/centralized/ssrun/': {'host': 'ssrun', 'applications': ['github-runner', 'docker', 'nginx']},
            '/var/log/centralized/sslog/': {'host': 'sslog', 'applications': ['logging-server', 'nginx', 'redis']}
        }
        
        # Component patterns for applications
        self.component_patterns = {
            'sports-scheduler': {
                'list-creator': re.compile(r'(list.creator|list_creator)', re.IGNORECASE),
                'epg-processor': re.compile(r'(epg.processor|epg_processor)', re.IGNORECASE),
                'channel-scanner': re.compile(r'(channel.scanner|channel_scanner)', re.IGNORECASE),
                'scheduler': re.compile(r'(scheduler|cron)', re.IGNORECASE),
                'api': re.compile(r'(api|route|endpoint)', re.IGNORECASE),
                'database': re.compile(r'(database|db|sql)', re.IGNORECASE)
            },
            'auto-scraper': {
                'list-creator': re.compile(r'(list.creator|list_creator)', re.IGNORECASE),
                'trakt-sync': re.compile(r'(trakt|sync)', re.IGNORECASE),
                'torrentio': re.compile(r'(torrentio|torrent)', re.IGNORECASE),
                'scheduler': re.compile(r'(scheduler|cron)', re.IGNORECASE),
                'api': re.compile(r'(api|route|endpoint)', re.IGNORECASE),
                'database': re.compile(r'(database|db|sql)', re.IGNORECASE)
            }
        }
        
        logger.info("Log processor initialized")
    
    def process_log_line(self, file_path: str, line: str):
        """Process a single log line."""
        try:
            # Parse the log entry
            parsed_entry = self._parse_log_line(file_path, line)
            
            if parsed_entry:
                # Store in Redis
                self._store_log_entry(parsed_entry)
                
                # Update metrics
                self.metrics.record_log_ingestion(
                    host=parsed_entry['host'],
                    application=parsed_entry['application'],
                    component=parsed_entry['component'],
                    level=parsed_entry['level']
                )
                
                # Check for errors or important events
                self._analyze_log_entry(parsed_entry)
                
        except Exception as e:
            logger.error(f"Failed to process log line from {file_path}: {e}")
            self.metrics.record_error('log_processor', 'processing_error')
    
    def _parse_log_line(self, file_path: str, line: str) -> Optional[Dict[str, Any]]:
        """Parse a log line into structured data."""
        try:
            # Determine host and application from file path
            host, application = self._get_host_application(file_path)
            
            # Parse timestamp and message
            timestamp, message, level = self._extract_log_components(line)
            
            # Determine component
            component = self._identify_component(application, message)
            
            # Create structured entry
            entry = {
                'timestamp': timestamp,
                'host': host,
                'application': application,
                'component': component,
                'level': level,
                'message': message,
                'file_path': file_path,
                'raw_line': line
            }
            
            return entry
            
        except Exception as e:
            logger.error(f"Failed to parse log line: {e}")
            return None
    
    def _get_host_application(self, file_path: str) -> Tuple[str, str]:
        """Determine host and application from file path."""
        try:
            for path_prefix, mapping in self.path_mappings.items():
                if file_path.startswith(path_prefix):
                    host = mapping['host']
                    
                    # Try to determine specific application from filename or content
                    file_name = Path(file_path).name
                    for app in mapping['applications']:
                        if app in file_name.lower():
                            return host, app
                    
                    # Default to first application for the host
                    return host, mapping['applications'][0]
            
            # Fallback
            return 'unknown', 'unknown'
            
        except Exception as e:
            logger.error(f"Failed to determine host/application for {file_path}: {e}")
            return 'unknown', 'unknown'
    
    def _extract_log_components(self, line: str) -> Tuple[str, str, str]:
        """Extract timestamp, message, and level from log line."""
        try:
            # Try rsyslog format first
            match = self.patterns['rsyslog'].match(line)
            if match:
                timestamp_str, message = match.groups()
                level = self._extract_log_level(message)
                return timestamp_str, message, level
            
            # Try application format
            match = self.patterns['application'].match(line)
            if match:
                timestamp_str, level, message = match.groups()
                return timestamp_str, message, level.upper()
            
            # Generic format
            timestamp_str = datetime.now().isoformat()
            level = self._extract_log_level(line)
            return timestamp_str, line, level
            
        except Exception as e:
            logger.error(f"Failed to extract log components: {e}")
            return datetime.now().isoformat(), line, 'INFO'
    
    def _extract_log_level(self, message: str) -> str:
        """Extract log level from message."""
        message_upper = message.upper()
        
        if any(word in message_upper for word in ['ERROR', 'FAIL', 'EXCEPTION', 'CRITICAL']):
            return 'ERROR'
        elif any(word in message_upper for word in ['WARN', 'WARNING']):
            return 'WARNING'
        elif any(word in message_upper for word in ['DEBUG', 'TRACE']):
            return 'DEBUG'
        else:
            return 'INFO'
    
    def _identify_component(self, application: str, message: str) -> str:
        """Identify component based on application and message content."""
        try:
            if application in self.component_patterns:
                for component, pattern in self.component_patterns[application].items():
                    if pattern.search(message):
                        return component
            
            # Default component
            return 'general'
            
        except Exception as e:
            logger.error(f"Failed to identify component: {e}")
            return 'general'
    
    def _store_log_entry(self, entry: Dict[str, Any]):
        """Store log entry in Redis."""
        try:
            # Create Redis keys
            timestamp_key = datetime.now().strftime('%Y%m%d')
            
            # Store in multiple structures for different query patterns
            
            # 1. Recent logs (last 1000 entries)
            recent_key = 'logs:recent'
            self.redis.lpush(recent_key, entry)
            self.redis.ltrim(recent_key, 0, 999)  # Keep last 1000
            
            # 2. Host-specific logs
            host_key = f"logs:host:{entry['host']}"
            self.redis.lpush(host_key, entry)
            self.redis.ltrim(host_key, 0, 499)  # Keep last 500 per host
            
            # 3. Application-specific logs
            app_key = f"logs:app:{entry['host']}:{entry['application']}"
            self.redis.lpush(app_key, entry)
            self.redis.ltrim(app_key, 0, 199)  # Keep last 200 per app
            
            # 4. Component-specific logs
            comp_key = f"logs:comp:{entry['host']}:{entry['application']}:{entry['component']}"
            self.redis.lpush(comp_key, entry)
            self.redis.ltrim(comp_key, 0, 99)  # Keep last 100 per component
            
            # 5. Daily logs for historical queries
            daily_key = f"logs:daily:{timestamp_key}"
            self.redis.lpush(daily_key, entry)
            self.redis.expire(daily_key, 86400 * 7)  # Keep for 7 days
            
        except Exception as e:
            logger.error(f"Failed to store log entry: {e}")
            self.metrics.record_error('log_processor', 'storage_error')
    
    def _analyze_log_entry(self, entry: Dict[str, Any]):
        """Analyze log entry for important events."""
        try:
            message = entry['message'].lower()
            level = entry['level']
            
            # Check for critical errors
            if level == 'ERROR' or any(word in message for word in ['exception', 'failed', 'error', 'critical']):
                self._handle_error_event(entry)
            
            # Check for application-specific events
            if entry['application'] == 'auto-scraper':
                self._analyze_auto_scraper_event(entry)
            elif entry['application'] == 'sports-scheduler':
                self._analyze_sports_scheduler_event(entry)
                
        except Exception as e:
            logger.error(f"Failed to analyze log entry: {e}")
    
    def _handle_error_event(self, entry: Dict[str, Any]):
        """Handle error events."""
        try:
            # Store in error-specific key
            error_key = f"logs:errors:{entry['host']}:{entry['application']}"
            self.redis.lpush(error_key, entry)
            self.redis.ltrim(error_key, 0, 49)  # Keep last 50 errors
            self.redis.expire(error_key, 86400)  # Expire after 1 day
            
            # Update error metrics
            self.metrics.record_error(entry['application'], entry['level'])
            
        except Exception as e:
            logger.error(f"Failed to handle error event: {e}")
    
    def _analyze_auto_scraper_event(self, entry: Dict[str, Any]):
        """Analyze auto-scraper specific events."""
        message = entry['message'].lower()
        
        if 'list creator' in message or 'list_creator' in message:
            # Store list creator events
            key = f"logs:auto-scraper:list-creator"
            self.redis.lpush(key, entry)
            self.redis.ltrim(key, 0, 49)
            self.redis.expire(key, 86400)
    
    def _analyze_sports_scheduler_event(self, entry: Dict[str, Any]):
        """Analyze sports-scheduler specific events."""
        message = entry['message'].lower()
        
        if 'list creator' in message or 'list_creator' in message:
            # Store list creator events
            key = f"logs:sports-scheduler:list-creator"
            self.redis.lpush(key, entry)
            self.redis.ltrim(key, 0, 49)
            self.redis.expire(key, 86400)
    
    def get_logs(self, host: str = 'all', application: str = 'all', component: str = 'all', 
                 level: str = 'all', limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get logs with filtering options."""
        try:
            # Determine Redis key based on filters
            if host != 'all' and application != 'all' and component != 'all':
                key = f"logs:comp:{host}:{application}:{component}"
            elif host != 'all' and application != 'all':
                key = f"logs:app:{host}:{application}"
            elif host != 'all':
                key = f"logs:host:{host}"
            else:
                key = 'logs:recent'
            
            # Get logs from Redis
            logs = self.redis.lrange(key, offset, offset + limit - 1)
            
            # Filter by level if specified
            if level != 'all':
                logs = [log for log in logs if log.get('level', '').upper() == level.upper()]
            
            return logs
            
        except Exception as e:
            logger.error(f"Failed to get logs: {e}")
            return []
    
    def search_logs(self, query: str, host: str = 'all', application: str = 'all', 
                   limit: int = 100) -> List[Dict[str, Any]]:
        """Search logs by query string."""
        try:
            # Get logs to search through
            logs = self.get_logs(host=host, application=application, limit=limit * 2)
            
            # Search through messages
            results = []
            query_lower = query.lower()
            
            for log in logs:
                if query_lower in log.get('message', '').lower():
                    results.append(log)
                    if len(results) >= limit:
                        break
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to search logs: {e}")
            return []
    
    def get_active_sources(self) -> List[str]:
        """Get list of active log sources."""
        try:
            sources = []
            for path_prefix, mapping in self.path_mappings.items():
                host = mapping['host']
                for app in mapping['applications']:
                    sources.append(f"{host}:{app}")
            return sources
        except Exception as e:
            logger.error(f"Failed to get active sources: {e}")
            return []
    
    def get_logs_count_today(self) -> int:
        """Get total logs processed today."""
        try:
            today_key = f"logs:daily:{datetime.now().strftime('%Y%m%d')}"
            return self.redis.client.llen(today_key) if self.redis.client else 0
        except Exception as e:
            logger.error(f"Failed to get logs count: {e}")
            return 0
