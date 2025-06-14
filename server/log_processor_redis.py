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
        self.max_lines_per_file = int(os.environ.get('MAX_LINES_PER_FILE', 5000))  # 0 = unlimited
        self.max_file_size = int(os.environ.get('MAX_FILE_SIZE_MB', 50)) * 1024 * 1024
        
        # Redis key patterns
        self.keys = {
            'logs': 'logs:{host}:{app}:{component}',
            'index': 'logs:index:{host}',
            'metadata': 'logs:meta:{host}:{file_hash}',
            'stats': 'logs:stats:{host}:{app}',
            'search': 'logs:search:{query_hash}'
        }
        
        max_lines_display = "unlimited" if self.max_lines_per_file == 0 else str(self.max_lines_per_file)
        logger.info(f"Redis Log Processor initialized - TTL: {self.log_ttl}s, Max lines: {max_lines_display}")

    def start_workers(self, num_workers=4):
        """Start background worker threads."""
        for i in range(num_workers):
            worker = threading.Thread(target=self._worker_loop, args=(i,))
            worker.daemon = True
            worker.start()
            self.worker_threads.append(worker)

        # Start Redis queue processor
        redis_worker = threading.Thread(target=self._redis_queue_processor)
        redis_worker.daemon = True
        redis_worker.start()
        self.worker_threads.append(redis_worker)

        logger.info(f"Started {num_workers} worker threads + 1 Redis queue processor")

    def _redis_queue_processor(self):
        """Process files from Redis queue and add to Python queue."""
        logger.info("Redis queue processor started")
        while self.running:
            try:
                # Block for up to 1 second waiting for a file from Redis queue
                result = self.redis_client.brpop('log_files_queue', timeout=1)
                if result:
                    queue_name, file_path = result

                    # Extract host from path
                    path_parts = Path(file_path).parts
                    host = 'unknown'
                    for part in path_parts:
                        if part in ['ssdev', 'ssdvr', 'ssmcp', 'ssrun', 'sslog']:
                            host = part
                            break

                    # Create task and add to processing queue
                    task = {
                        'file_path': file_path,
                        'host': host,
                        'event_type': 'queued'
                    }

                    try:
                        self.processing_queue.put_nowait(task)
                        logger.info(f"Queued file for processing: {file_path} (host: {host})")
                    except queue.Full:
                        logger.warning(f"Processing queue full, re-queuing {file_path}")
                        self.redis_client.lpush('log_files_queue', file_path)

            except Exception as e:
                logger.error(f"Redis queue processor error: {e}")
                time.sleep(1)

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

                # Limit lines processed (0 = unlimited)
                if self.max_lines_per_file > 0 and len(lines) > self.max_lines_per_file:
                    lines = lines[-self.max_lines_per_file:]
                    logger.warning(f"Worker {worker_id}: Truncated {file_path} to {self.max_lines_per_file} lines")
                else:
                    logger.info(f"Worker {worker_id}: Processing all {len(lines)} lines from {file_path}")

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

        # Extract refresh ID
        refresh_match = re.search(r'\[Refresh-(\d+)\]', line)
        refresh_id = refresh_match.group(1) if refresh_match else None

        # Extract step information
        step_match = re.search(r'step\s*(\d+)(?:/8)?', line, re.IGNORECASE)
        step = step_match.group(1) if step_match else None

        return {
            'timestamp': timestamp.isoformat(),
            'level': level,
            'message': line.strip(),
            'file_path': str(file_path),
            'line_number': line_num,
            'refresh_id': refresh_id,
            'step': step,
            'indexed_at': datetime.now().isoformat()
        }

    def _store_log_entry(self, log_entry: Dict, host: str, app: str, component: str):
        """Store log entry in Redis with proper indexing."""
        # Clean log entry - remove None values
        clean_entry = {}
        for key, value in log_entry.items():
            if value is not None:
                clean_entry[key] = str(value)  # Convert all values to strings for Redis

        # Generate unique key for this log entry
        entry_key = f"log:{host}:{app}:{component}:{clean_entry['timestamp']}:{clean_entry['line_number']}"

        # Store the log entry
        self.redis_client.hset(entry_key, mapping=clean_entry)
        self.redis_client.expire(entry_key, self.log_ttl)

        # Add to sorted sets for efficient querying
        timestamp_score = int(datetime.fromisoformat(clean_entry['timestamp']).timestamp())

        # Index by host:app:component
        index_key = self.keys['logs'].format(host=host, app=app, component=component)
        self.redis_client.zadd(index_key, {entry_key: timestamp_score})
        self.redis_client.expire(index_key, self.log_ttl)

        # Index by level for filtering
        level_key = f"{index_key}:level:{clean_entry['level']}"
        self.redis_client.zadd(level_key, {entry_key: timestamp_score})
        self.redis_client.expire(level_key, self.log_ttl)

        # Index by refresh_id if present
        if clean_entry.get('refresh_id'):
            refresh_key = f"{index_key}:refresh:{clean_entry['refresh_id']}"
            self.redis_client.zadd(refresh_key, {entry_key: timestamp_score})
            self.redis_client.expire(refresh_key, self.log_ttl)

        # Index by step if present
        if clean_entry.get('step'):
            step_key = f"{index_key}:step:{clean_entry['step']}"
            self.redis_client.zadd(step_key, {entry_key: timestamp_score})
            self.redis_client.expire(step_key, self.log_ttl)

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
