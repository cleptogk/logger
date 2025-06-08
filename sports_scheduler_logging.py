"""
Enhanced logging configuration for sports-scheduler application.
Sends structured logs to centralized logging system.
"""

import logging
import logging.handlers
import json
import os
import sys
from datetime import datetime
from pathlib import Path

class CentralizedLogHandler(logging.Handler):
    """Custom logging handler that writes to centralized log files with structured format."""
    
    def __init__(self, log_dir='/var/log/centralized/ssdev/sports-scheduler', component='general'):
        super().__init__()
        self.log_dir = Path(log_dir)
        self.component = component
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create component-specific log file
        self.log_file = self.log_dir / f"{component}.log"
        
        # Set up file handler with rotation
        self.file_handler = logging.handlers.RotatingFileHandler(
            self.log_file,
            maxBytes=50*1024*1024,  # 50MB
            backupCount=5,
            encoding='utf-8'
        )
        
        # Set format for structured logging
        formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d-07:00 %(levelname)s [%(name)s:%(funcName)s:%(lineno)d] %(message)s',
            datefmt='%Y-%m-%dT%H:%M:%S'
        )
        self.file_handler.setFormatter(formatter)
    
    def emit(self, record):
        """Emit a log record to the centralized log file."""
        try:
            # Add component information to the record
            record.component = self.component
            
            # Write to file
            self.file_handler.emit(record)
            
        except Exception:
            self.handleError(record)

class IPTVOrchestratorLogger:
    """Enhanced logger for IPTV Orchestrator with step-by-step tracking."""
    
    def __init__(self, refresh_id=None):
        self.refresh_id = refresh_id
        self.logger = logging.getLogger('sports_scheduler.iptv_orchestrator')
        
        # Add centralized log handler if not already added
        if not any(isinstance(h, CentralizedLogHandler) for h in self.logger.handlers):
            handler = CentralizedLogHandler(component='iptv-orchestrator')
            handler.setLevel(logging.INFO)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def log_step_start(self, step_num, step_name, details=None):
        """Log the start of an IPTV orchestrator step."""
        message = f"Step {step_num}/8: {step_name}"
        if details:
            message += f" - {details}"
        
        if self.refresh_id:
            message = f"[Refresh-{self.refresh_id}] {message}"
        
        self.logger.info(message)
    
    def log_step_progress(self, step_num, progress_message, details=None):
        """Log progress within a step."""
        message = f"Step {step_num} Progress: {progress_message}"
        if details:
            message += f" - {details}"
        
        if self.refresh_id:
            message = f"[Refresh-{self.refresh_id}] {message}"
        
        self.logger.info(message)
    
    def log_step_complete(self, step_num, step_name, duration=None, results=None):
        """Log the completion of an IPTV orchestrator step."""
        message = f"Step {step_num}/8: {step_name} completed successfully"
        
        if duration:
            message += f" in {duration:.2f} seconds"
        
        if results:
            if isinstance(results, dict):
                # Add key metrics from results
                if 'channels_processed' in results:
                    message += f" - {results['channels_processed']} channels processed"
                if 'events_processed' in results:
                    message += f" - {results['events_processed']} events processed"
                if 'recordings_scheduled' in results:
                    message += f" - {results['recordings_scheduled']} recordings scheduled"
            else:
                message += f" - {results}"
        
        if self.refresh_id:
            message = f"[Refresh-{self.refresh_id}] {message}"
        
        self.logger.info(message)
    
    def log_step_error(self, step_num, step_name, error, details=None):
        """Log an error in an IPTV orchestrator step."""
        message = f"Step {step_num}/8: {step_name} failed - {error}"
        if details:
            message += f" - {details}"
        
        if self.refresh_id:
            message = f"[Refresh-{self.refresh_id}] {message}"
        
        self.logger.error(message)
    
    def log_workflow_start(self, trigger_source, total_steps=8):
        """Log the start of the IPTV refresh workflow."""
        message = f"Starting IPTV refresh workflow (trigger: {trigger_source}, steps: {total_steps})"
        if self.refresh_id:
            message = f"[Refresh-{self.refresh_id}] {message}"
        
        self.logger.info(message)
    
    def log_workflow_complete(self, duration, total_steps=8, results=None):
        """Log the completion of the IPTV refresh workflow."""
        message = f"IPTV refresh workflow completed successfully in {duration:.2f} seconds ({total_steps} steps)"
        
        if results and isinstance(results, dict):
            # Add summary metrics
            summary_parts = []
            if 'total_channels' in results:
                summary_parts.append(f"{results['total_channels']} channels")
            if 'total_events' in results:
                summary_parts.append(f"{results['total_events']} events")
            if 'total_recordings' in results:
                summary_parts.append(f"{results['total_recordings']} recordings")
            
            if summary_parts:
                message += f" - {', '.join(summary_parts)}"
        
        if self.refresh_id:
            message = f"[Refresh-{self.refresh_id}] {message}"
        
        self.logger.info(message)
    
    def log_workflow_error(self, error, duration=None, step_failed=None):
        """Log an error in the IPTV refresh workflow."""
        message = f"IPTV refresh workflow failed - {error}"
        
        if step_failed:
            message += f" (failed at step {step_failed})"
        
        if duration:
            message += f" after {duration:.2f} seconds"
        
        if self.refresh_id:
            message = f"[Refresh-{self.refresh_id}] {message}"
        
        self.logger.error(message)

def setup_sports_scheduler_logging():
    """Set up enhanced logging for the sports-scheduler application."""
    
    # Create centralized log handlers for different components
    components = [
        'iptv-orchestrator',
        'epg-processor', 
        'channel-scanner',
        'playlist-generator',
        'scheduler',
        'api',
        'database'
    ]
    
    for component in components:
        logger_name = f'sports_scheduler.{component.replace("-", "_")}'
        logger = logging.getLogger(logger_name)
        
        # Add centralized handler if not already present
        if not any(isinstance(h, CentralizedLogHandler) for h in logger.handlers):
            handler = CentralizedLogHandler(component=component)
            handler.setLevel(logging.INFO)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
    
    # Set up main application logger
    main_logger = logging.getLogger('sports_scheduler')
    if not any(isinstance(h, CentralizedLogHandler) for h in main_logger.handlers):
        handler = CentralizedLogHandler(component='application')
        handler.setLevel(logging.INFO)
        main_logger.addHandler(handler)
        main_logger.setLevel(logging.INFO)
    
    print("✅ Sports-scheduler centralized logging configured")

def get_component_logger(component_name):
    """Get a logger for a specific component."""
    logger_name = f'sports_scheduler.{component_name.replace("-", "_")}'
    return logging.getLogger(logger_name)

# Auto-configure logging when module is imported
if __name__ != '__main__':
    setup_sports_scheduler_logging()
