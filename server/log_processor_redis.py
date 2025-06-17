#!/usr/bin/env python3
"""
Redis-based log processor for high-performance log parsing.
Runs as background service, continuously processes log files into Redis.
"""

import os
import sys
import json
import time
import redis
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from loguru import logger
import threading
import queue
from typing import Dict, List, Optional

class RedisLogProcessor:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=os.environ.get('REDIS_HOST', '127.0.0.1'),
            port=int(os.environ.get('REDIS_PORT', 6379)),
            db=int(os.environ.get('REDIS_DB', 0)),
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        
        # Processing queue
        self.processing_queue = queue.Queue(maxsize=1000)
        self.worker_threads = []
        self.running = True
        
        # Cache settings
        self.log_ttl = int(os.environ.get('LOG_TTL_HOURS', 24)) * 3600  # 24 hours
        self.max_lines_per_file = int(os.environ.get('MAX_LINES_PER_FILE', 5000))
        self.max_file_size = int(os.environ.get('MAX_FILE_SIZE_MB', 50)) * 1024 * 1024
        
        # Redis key patterns - updated to match file structure
        self.keys = {
            'logs': 'logs:{host}:{app}:{component}',
            'step_logs': 'logs:{host}:{app}:{component}:{refresh_id}:{step_name}',
            'refresh_logs': 'logs:{host}:{app}:{component}:{refresh_id}:all',
            'index': 'logs:index:{host}',
            'metadata': 'logs:meta:{host}:{file_hash}',
            'stats': 'logs:stats:{host}:{app}',
            'search': 'logs:search:{query_hash}'
        }

        # Step name mapping for IPTV orchestrator
        self.step_names = {
            '1': 'step1-purge_xtream',
            '2': 'step2-refresh_channels',
            '3': 'step3-refresh_xtream_epg',
            '4': 'step4-purge_epg_db',
            '5': 'step5-refresh_epg_db',
            '6': 'step6-generate_playlist',
            '7': 'step7-refresh_channels_dvr',
            '8': 'step8-automated_recordings',
            '9': 'step9-create_collections'
        }
        
        logger.info(f"Redis Log Processor initialized - TTL: {self.log_ttl}s, Max lines: {self.max_lines_per_file}")

    def start_workers(self, num_workers=4):
        """Start background worker threads."""
        for i in range(num_workers):
            worker = threading.Thread(target=self._worker_loop, args=(i,))
            worker.daemon = True
            worker.start()
            self.worker_threads.append(worker)
        logger.info(f"Started {num_workers} worker threads")

    def _worker_loop(self, worker_id):
        """Worker thread loop for processing files."""
        while self.running:
            try:
                task = self.processing_queue.get(timeout=1)
                if task is None:  # Shutdown signal
                    break
                    
                self._process_file_task(task, worker_id)
                self.processing_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")

    def _process_file_task(self, task, worker_id):
        """Process a single file task."""
        file_path = Path(task['file_path'])
        host = task['host']
        
        try:
            # Check if file needs processing
            file_hash = self._get_file_hash(file_path)
            meta_key = self.keys['metadata'].format(host=host, file_hash=file_hash)
            
            cached_meta = self.redis_client.hgetall(meta_key)
            if cached_meta and cached_meta.get('processed_at'):
                # Check if file was modified since last processing
                last_processed = datetime.fromisoformat(cached_meta['processed_at'])
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                
                if file_mtime <= last_processed:
                    logger.debug(f"Worker {worker_id}: File {file_path} already processed")
                    return
            
            # Process the file
            logs_processed = self._parse_and_store_file(file_path, host, worker_id)
            
            # Update metadata
            self.redis_client.hset(meta_key, mapping={
                'file_path': str(file_path),
                'file_size': file_path.stat().st_size,
                'processed_at': datetime.now().isoformat(),
                'logs_count': logs_processed,
                'worker_id': worker_id
            })
            self.redis_client.expire(meta_key, self.log_ttl)
            
            logger.info(f"Worker {worker_id}: Processed {logs_processed} logs from {file_path}")
            
        except Exception as e:
            logger.error(f"Worker {worker_id}: Failed to process {file_path}: {e}")

    def _get_file_hash(self, file_path: Path) -> str:
        """Generate hash for file based on path and mtime."""
        stat = file_path.stat()
        content = f"{file_path}:{stat.st_size}:{stat.st_mtime}"
        return hashlib.md5(content.encode()).hexdigest()

    def _parse_and_store_file(self, file_path: Path, host: str, worker_id: int) -> int:
        """Parse log file and store in Redis."""
        if file_path.stat().st_size > self.max_file_size:
            logger.warning(f"Worker {worker_id}: Skipping large file {file_path} ({file_path.stat().st_size} bytes)")
            return 0
        
        logs_processed = 0
        app_name = self._extract_app_name(file_path)
        component = self._extract_component_name(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Read file in reverse to get most recent logs first
                lines = f.readlines()
                
                # Limit lines processed
                if len(lines) > self.max_lines_per_file:
                    lines = lines[-self.max_lines_per_file:]
                    logger.warning(f"Worker {worker_id}: Truncated {file_path} to {self.max_lines_per_file} lines")
                
                # Process lines in reverse (newest first)
                for line_num, line in enumerate(reversed(lines)):
                    if not line.strip():
                        continue
                        
                    log_entry = self._parse_log_line(line, file_path, line_num)
                    if log_entry:
                        self._store_log_entry(log_entry, host, app_name, component)
                        logs_processed += 1
                        
        except Exception as e:
            logger.error(f"Worker {worker_id}: Error reading {file_path}: {e}")
            
        return logs_processed

    def _extract_app_name(self, file_path: Path) -> str:
        """Extract application name from file path."""
        path_parts = file_path.parts
        if 'sports-scheduler' in path_parts:
            return 'sports-scheduler'
        elif 'auto-scraper' in path_parts:
            return 'auto-scraper'
        elif 'system' in str(file_path):
            return 'system'
        return 'unknown'

    def _extract_component_name(self, file_path: Path) -> str:
        """Extract component name from file path."""
        path_parts = file_path.parts

        # For new structured IPTV orchestrator logs: /var/log/centralized/ssdev/sports-scheduler/iptv-orchestrator/123/step1-purge_xtream.log
        if 'iptv-orchestrator' in path_parts:
            return 'iptv-orchestrator'

        # For legacy flat structure, check filename
        filename = file_path.name
        if 'iptv-orchestrator' in filename:
            return 'iptv-orchestrator'
        elif 'epg-processor' in filename:
            return 'epg-processor'
        elif 'automated-recording' in filename:
            return 'automated-recording'
        elif 'application' in filename:
            return 'application'
        elif 'api' in filename:
            return 'api'
        return 'general'

    def _extract_refresh_id_and_step(self, file_path: Path) -> tuple:
        """Extract refresh_id and step_name from file path for structured IPTV orchestrator logs."""
        path_parts = file_path.parts

        # Check if this is a structured IPTV orchestrator log
        # Path format: /var/log/centralized/ssdev/sports-scheduler/iptv-orchestrator/123/step1-purge_xtream.log
        try:
            if 'iptv-orchestrator' in path_parts:
                iptv_index = path_parts.index('iptv-orchestrator')
                if iptv_index + 2 < len(path_parts):
                    refresh_id = path_parts[iptv_index + 1]
                    step_filename = path_parts[iptv_index + 2]
                    step_name = step_filename.replace('.log', '')
                    return refresh_id, step_name
        except (ValueError, IndexError):
            pass

        return None, None

    def _parse_log_line(self, line: str, file_path: Path, line_num: int) -> Optional[Dict]:
        """Parse a single log line into structured data."""
        import re
        from datetime import datetime

        # Extract timestamp
        timestamp_patterns = [
            r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?[+-]\d{2}:\d{2})',
            r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)',
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})',
        ]

        timestamp = None
        for pattern in timestamp_patterns:
            match = re.search(pattern, line)
            if match:
                try:
                    timestamp_str = match.group(1)
                    if 'T' in timestamp_str and ('+' in timestamp_str or '-' in timestamp_str[-6:]):
                        timestamp = datetime.fromisoformat(timestamp_str)
                    else:
                        timestamp = datetime.fromisoformat(timestamp_str.replace('T', ' '))
                    break
                except:
                    continue

        if not timestamp:
            timestamp = datetime.now()

        # Extract log level
        level_match = re.search(r'\b(DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)\b', line, re.IGNORECASE)
        level = level_match.group(1).upper() if level_match else 'INFO'

        # Extract refresh_id and step_name from file path (for structured logs)
        refresh_id, step_name = self._extract_refresh_id_and_step(file_path)

        # Fallback: Extract refresh ID from message (for legacy logs)
        if not refresh_id:
            refresh_match = re.search(r'\[Refresh-(\d+)\]', line)
            refresh_id = refresh_match.group(1) if refresh_match else None

        # Fallback: Extract step information from message (for legacy logs)
        step = None
        if not step_name:
            step_match = re.search(r'step\s*(\d+)(?:/[89])?', line, re.IGNORECASE)
            step = step_match.group(1) if step_match else None

        return {
            'timestamp': timestamp.isoformat(),
            'level': level,
            'message': line.strip(),
            'file_path': str(file_path),
            'line_number': line_num,
            'refresh_id': refresh_id,
            'step': step,
            'step_name': step_name,
            'indexed_at': datetime.now().isoformat()
        }

    def _store_log_entry(self, log_entry: Dict, host: str, app: str, component: str):
        """Store log entry in Redis using new structured key format."""
        # Clean log entry - remove None values
        clean_entry = {}
        for key, value in log_entry.items():
            if value is not None:
                clean_entry[key] = str(value)  # Convert all values to strings for Redis

        # Create JSON string of the log entry for storage in sorted set
        log_json = json.dumps(clean_entry)
        timestamp_score = int(datetime.fromisoformat(clean_entry['timestamp']).timestamp())

        # Check if this is a structured IPTV orchestrator log
        is_structured_iptv = (component == 'iptv-orchestrator' and
                             clean_entry.get('refresh_id') and
                             clean_entry.get('step_name'))

        if is_structured_iptv:
            # Use new structured key format for IPTV orchestrator step logs
            refresh_id = clean_entry['refresh_id']
            step_name = clean_entry['step_name']

            # Step-specific key: logs:host:app:component:refresh_id:step_name
            step_key = self.keys['step_logs'].format(
                host=host, app=app, component=component,
                refresh_id=refresh_id, step_name=step_name
            )
            self.redis_client.zadd(step_key, {log_json: timestamp_score})
            self.redis_client.expire(step_key, self.log_ttl)
            self.redis_client.zremrangebyrank(step_key, 0, -1001)  # Keep last 1,000 per step

            # Refresh-wide aggregation: logs:host:app:component:refresh_id:all
            refresh_key = self.keys['refresh_logs'].format(
                host=host, app=app, component=component, refresh_id=refresh_id
            )
            self.redis_client.zadd(refresh_key, {log_json: timestamp_score})
            self.redis_client.expire(refresh_key, self.log_ttl)
            self.redis_client.zremrangebyrank(refresh_key, 0, -5001)  # Keep last 5,000 per refresh

            # Level-based filtering within step
            step_level_key = f"{step_key}:level:{clean_entry['level']}"
            self.redis_client.zadd(step_level_key, {log_json: timestamp_score})
            self.redis_client.expire(step_level_key, self.log_ttl)
            self.redis_client.zremrangebyrank(step_level_key, 0, -501)  # Keep last 500 per step/level

        # Always store in legacy format for backward compatibility
        index_key = self.keys['logs'].format(host=host, app=app, component=component)
        self.redis_client.zadd(index_key, {log_json: timestamp_score})
        self.redis_client.expire(index_key, self.log_ttl)
        self.redis_client.zremrangebyrank(index_key, 0, -10001)  # Keep last 10,000 entries

        # Legacy level indexing
        level_key = f"{index_key}:level:{clean_entry['level']}"
        self.redis_client.zadd(level_key, {log_json: timestamp_score})
        self.redis_client.expire(level_key, self.log_ttl)
        self.redis_client.zremrangebyrank(level_key, 0, -1001)  # Keep last 1,000 per level

        # Legacy refresh_id indexing (for backward compatibility)
        if clean_entry.get('refresh_id'):
            legacy_refresh_key = f"{index_key}:refresh:{clean_entry['refresh_id']}"
            self.redis_client.zadd(legacy_refresh_key, {log_json: timestamp_score})
            self.redis_client.expire(legacy_refresh_key, self.log_ttl)

        # Legacy step indexing (for backward compatibility)
        if clean_entry.get('step'):
            legacy_step_key = f"{index_key}:step:{clean_entry['step']}"
            self.redis_client.zadd(legacy_step_key, {log_json: timestamp_score})
            self.redis_client.expire(legacy_step_key, self.log_ttl)

        # Update statistics
        stats_key = self.keys['stats'].format(host=host, app=app)
        self.redis_client.hincrby(stats_key, 'total_logs', 1)
        self.redis_client.hincrby(stats_key, f'level_{clean_entry["level"]}', 1)
        self.redis_client.expire(stats_key, self.log_ttl)

class LogFileWatcher(FileSystemEventHandler):
    """File system watcher for real-time log processing."""
    
    def __init__(self, processor: RedisLogProcessor):
        self.processor = processor
        
    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith('.log'):
            return
            
        # Extract host from path
        path_parts = Path(event.src_path).parts
        host = 'unknown'
        for part in path_parts:
            if part in ['ssdev', 'ssdvr', 'ssmcp', 'ssrun']:
                host = part
                break
                
        # Queue for processing
        task = {
            'file_path': event.src_path,
            'host': host,
            'event_type': 'modified'
        }
        
        try:
            self.processor.processing_queue.put_nowait(task)
        except queue.Full:
            logger.warning(f"Processing queue full, dropping task for {event.src_path}")

def main():
    """Main entry point for Redis log processor service."""
    processor = RedisLogProcessor()
    
    # Start worker threads
    processor.start_workers(num_workers=4)
    
    # Set up file system watcher
    event_handler = LogFileWatcher(processor)
    observer = Observer()
    observer.schedule(event_handler, '/var/log/centralized', recursive=True)
    observer.start()
    
    logger.info("Redis Log Processor started - watching /var/log/centralized")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down Redis Log Processor...")
        processor.running = False
        observer.stop()
        observer.join()
        
        # Signal workers to stop
        for _ in processor.worker_threads:
            processor.processing_queue.put(None)
            
        # Wait for workers to finish
        for worker in processor.worker_threads:
            worker.join(timeout=5)

if __name__ == '__main__':
    main()
