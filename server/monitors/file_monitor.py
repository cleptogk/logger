"""
File Monitor Module
Monitors log files for changes and processes new log entries.
"""

import os
import time
import threading
from pathlib import Path
from typing import Dict, Set, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent
from loguru import logger

class LogFileHandler(FileSystemEventHandler):
    """Handler for log file system events."""
    
    def __init__(self, processor):
        """Initialize with log processor."""
        self.processor = processor
        self.file_positions = {}  # Track file read positions
        
    def on_modified(self, event):
        """Handle file modification events."""
        if isinstance(event, FileModifiedEvent) and not event.is_directory:
            if event.src_path.endswith('.log'):
                self._process_log_file(event.src_path)
    
    def _process_log_file(self, file_path: str):
        """Process new lines in a log file."""
        try:
            # Get current position or start from end for new files
            current_pos = self.file_positions.get(file_path, 0)
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Seek to last known position
                f.seek(current_pos)
                
                # Read new lines
                new_lines = f.readlines()
                
                if new_lines:
                    # Update position
                    self.file_positions[file_path] = f.tell()
                    
                    # Process each line
                    for line in new_lines:
                        line = line.strip()
                        if line:
                            self.processor.process_log_line(file_path, line)
                            
        except Exception as e:
            logger.error(f"Error processing log file {file_path}: {e}")

class LogFileMonitor:
    """Monitors log files for changes and processes new entries."""
    
    def __init__(self, processor):
        """Initialize file monitor with log processor."""
        self.processor = processor
        self.observer = Observer()
        self.handler = LogFileHandler(processor)
        self.monitored_paths = set()
        self.running = False
        
        # Default paths to monitor
        self.log_base_dir = Path('/var/log/centralized')
        
        logger.info("File monitor initialized")
    
    def start(self):
        """Start monitoring log files."""
        try:
            if self.running:
                logger.warning("File monitor is already running")
                return
            
            # Ensure log directory exists
            self.log_base_dir.mkdir(parents=True, exist_ok=True)
            
            # Start monitoring the centralized log directory
            self._add_watch_path(str(self.log_base_dir))
            
            # Start the observer
            self.observer.start()
            self.running = True
            
            logger.info(f"✅ File monitor started, watching: {self.log_base_dir}")
            
            # Initialize file positions for existing files
            self._initialize_existing_files()
            
        except Exception as e:
            logger.error(f"Failed to start file monitor: {e}")
            self.running = False
    
    def stop(self):
        """Stop monitoring log files."""
        try:
            if not self.running:
                return
            
            self.observer.stop()
            self.observer.join(timeout=5)
            self.running = False
            
            logger.info("✅ File monitor stopped")
            
        except Exception as e:
            logger.error(f"Error stopping file monitor: {e}")
    
    def is_running(self) -> bool:
        """Check if monitor is running."""
        return self.running and self.observer.is_alive()
    
    def add_path(self, path: str):
        """Add a path to monitor."""
        try:
            path_obj = Path(path)
            if path_obj.exists():
                self._add_watch_path(str(path_obj))
                logger.info(f"Added monitoring path: {path}")
            else:
                logger.warning(f"Path does not exist: {path}")
        except Exception as e:
            logger.error(f"Failed to add monitoring path {path}: {e}")
    
    def remove_path(self, path: str):
        """Remove a path from monitoring."""
        try:
            if path in self.monitored_paths:
                # Note: watchdog doesn't have a direct way to remove specific paths
                # This would require restarting the observer with updated paths
                self.monitored_paths.discard(path)
                logger.info(f"Removed monitoring path: {path}")
        except Exception as e:
            logger.error(f"Failed to remove monitoring path {path}: {e}")
    
    def get_monitored_paths(self) -> Set[str]:
        """Get currently monitored paths."""
        return self.monitored_paths.copy()
    
    def get_file_count(self) -> int:
        """Get number of log files being monitored."""
        try:
            count = 0
            for path in self.monitored_paths:
                path_obj = Path(path)
                if path_obj.is_dir():
                    count += len(list(path_obj.rglob('*.log')))
                elif path_obj.is_file() and path_obj.suffix == '.log':
                    count += 1
            return count
        except Exception as e:
            logger.error(f"Failed to count monitored files: {e}")
            return 0
    
    def _add_watch_path(self, path: str):
        """Add a watch path to the observer."""
        try:
            self.observer.schedule(self.handler, path, recursive=True)
            self.monitored_paths.add(path)
        except Exception as e:
            logger.error(f"Failed to add watch path {path}: {e}")
    
    def _initialize_existing_files(self):
        """Initialize file positions for existing log files."""
        try:
            for path in self.monitored_paths:
                path_obj = Path(path)
                if path_obj.is_dir():
                    # Find all .log files in the directory
                    for log_file in path_obj.rglob('*.log'):
                        if log_file.is_file():
                            # Set position to end of file (only process new entries)
                            try:
                                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                                    f.seek(0, 2)  # Seek to end
                                    self.handler.file_positions[str(log_file)] = f.tell()
                            except Exception as e:
                                logger.warning(f"Could not initialize position for {log_file}: {e}")
                                
        except Exception as e:
            logger.error(f"Failed to initialize existing files: {e}")
    
    def force_scan(self):
        """Force scan all monitored files for new content."""
        try:
            for path in self.monitored_paths:
                path_obj = Path(path)
                if path_obj.is_dir():
                    for log_file in path_obj.rglob('*.log'):
                        if log_file.is_file():
                            self.handler._process_log_file(str(log_file))
                            
            logger.info("Force scan completed")
            
        except Exception as e:
            logger.error(f"Force scan failed: {e}")
    
    def get_status(self) -> Dict[str, any]:
        """Get monitor status information."""
        return {
            'running': self.is_running(),
            'monitored_paths': list(self.monitored_paths),
            'file_count': self.get_file_count(),
            'observer_alive': self.observer.is_alive() if self.observer else False,
            'tracked_files': len(self.handler.file_positions)
        }
