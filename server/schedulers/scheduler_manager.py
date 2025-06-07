"""
Scheduler Manager Module
Manages scheduled tasks for the logging server.
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Callable, Any
from loguru import logger

class SchedulerManager:
    """Manages scheduled tasks for the logging server."""
    
    def __init__(self, redis_client, metrics_exporter):
        """Initialize scheduler manager."""
        self.redis = redis_client
        self.metrics = metrics_exporter
        self.running = False
        self.scheduler_thread = None
        self.tasks = {}
        
        # Register default tasks
        self._register_default_tasks()
        
        logger.info("Scheduler manager initialized")
    
    def start(self):
        """Start the scheduler."""
        try:
            if self.running:
                logger.warning("Scheduler is already running")
                return
            
            self.running = True
            self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
            self.scheduler_thread.start()
            
            logger.info("✅ Scheduler started")
            
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            self.running = False
    
    def stop(self):
        """Stop the scheduler."""
        try:
            if not self.running:
                return
            
            self.running = False
            
            if self.scheduler_thread and self.scheduler_thread.is_alive():
                self.scheduler_thread.join(timeout=5)
            
            logger.info("✅ Scheduler stopped")
            
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")
    
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self.running and (self.scheduler_thread and self.scheduler_thread.is_alive())
    
    def add_task(self, name: str, func: Callable, interval: int, description: str = ""):
        """Add a scheduled task."""
        try:
            self.tasks[name] = {
                'function': func,
                'interval': interval,
                'description': description,
                'last_run': 0,
                'run_count': 0,
                'error_count': 0
            }
            
            logger.info(f"Added scheduled task: {name} (every {interval}s)")
            
        except Exception as e:
            logger.error(f"Failed to add task {name}: {e}")
    
    def remove_task(self, name: str):
        """Remove a scheduled task."""
        try:
            if name in self.tasks:
                del self.tasks[name]
                logger.info(f"Removed scheduled task: {name}")
            else:
                logger.warning(f"Task not found: {name}")
                
        except Exception as e:
            logger.error(f"Failed to remove task {name}: {e}")
    
    def get_tasks(self) -> Dict[str, Any]:
        """Get information about all tasks."""
        try:
            task_info = {}
            for name, task in self.tasks.items():
                task_info[name] = {
                    'description': task['description'],
                    'interval': task['interval'],
                    'last_run': task['last_run'],
                    'run_count': task['run_count'],
                    'error_count': task['error_count'],
                    'next_run': task['last_run'] + task['interval'] if task['last_run'] > 0 else 'pending'
                }
            return task_info
            
        except Exception as e:
            logger.error(f"Failed to get task info: {e}")
            return {}
    
    def _scheduler_loop(self):
        """Main scheduler loop."""
        logger.info("Scheduler loop started")
        
        while self.running:
            try:
                current_time = time.time()
                
                for name, task in self.tasks.items():
                    try:
                        # Check if task should run
                        if current_time - task['last_run'] >= task['interval']:
                            logger.debug(f"Running scheduled task: {name}")
                            
                            # Run the task
                            start_time = time.time()
                            task['function']()
                            duration = time.time() - start_time
                            
                            # Update task info
                            task['last_run'] = current_time
                            task['run_count'] += 1
                            
                            # Record metrics
                            self.metrics.record_processing_time(f"scheduled_task_{name}", duration)
                            
                            logger.debug(f"Completed task {name} in {duration:.2f}s")
                            
                    except Exception as e:
                        logger.error(f"Error running scheduled task {name}: {e}")
                        task['error_count'] += 1
                        self.metrics.record_error('scheduler', f"task_{name}_error")
                
                # Sleep for a short interval
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                time.sleep(5)  # Wait longer on error
        
        logger.info("Scheduler loop stopped")
    
    def _register_default_tasks(self):
        """Register default scheduled tasks."""
        try:
            # System metrics update task
            self.add_task(
                name="update_system_metrics",
                func=self._update_system_metrics,
                interval=30,  # Every 30 seconds
                description="Update system resource metrics"
            )
            
            # Redis health check task
            self.add_task(
                name="redis_health_check",
                func=self._redis_health_check,
                interval=60,  # Every minute
                description="Check Redis connection health"
            )
            
            # Log cleanup task
            self.add_task(
                name="cleanup_old_logs",
                func=self._cleanup_old_logs,
                interval=3600,  # Every hour
                description="Clean up old log entries from Redis"
            )
            
            # Metrics summary task
            self.add_task(
                name="metrics_summary",
                func=self._generate_metrics_summary,
                interval=300,  # Every 5 minutes
                description="Generate and store metrics summary"
            )
            
        except Exception as e:
            logger.error(f"Failed to register default tasks: {e}")
    
    def _update_system_metrics(self):
        """Update system resource metrics."""
        try:
            self.metrics.update_system_metrics()
        except Exception as e:
            logger.error(f"Failed to update system metrics: {e}")
    
    def _redis_health_check(self):
        """Check Redis connection health."""
        try:
            is_connected = self.redis.ping() if self.redis else False
            self.metrics.set_redis_status(is_connected)
            
            if not is_connected:
                logger.warning("Redis health check failed")
            
        except Exception as e:
            logger.error(f"Redis health check error: {e}")
            self.metrics.set_redis_status(False)
    
    def _cleanup_old_logs(self):
        """Clean up old log entries from Redis."""
        try:
            if not self.redis:
                return
            
            # Get current date
            current_date = datetime.now()
            
            # Clean up daily logs older than 7 days
            for i in range(8, 15):  # Check 8-14 days ago
                old_date = current_date - timedelta(days=i)
                old_key = f"logs:daily:{old_date.strftime('%Y%m%d')}"
                
                if self.redis.exists(old_key):
                    self.redis.delete(old_key)
                    logger.debug(f"Cleaned up old daily logs: {old_key}")
            
            logger.debug("Log cleanup completed")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old logs: {e}")
    
    def _generate_metrics_summary(self):
        """Generate and store metrics summary."""
        try:
            if not self.redis:
                return
            
            # Get current metrics summary
            summary = self.metrics.get_summary_stats()
            
            # Store in Redis with timestamp
            timestamp = datetime.now().isoformat()
            summary['timestamp'] = timestamp
            
            # Store in metrics history
            metrics_key = "metrics:history"
            self.redis.lpush(metrics_key, summary)
            self.redis.ltrim(metrics_key, 0, 287)  # Keep last 288 entries (24 hours at 5-min intervals)
            
            # Store current metrics
            self.redis.set("metrics:current", summary, expire=600)  # Expire after 10 minutes
            
            logger.debug("Metrics summary generated and stored")
            
        except Exception as e:
            logger.error(f"Failed to generate metrics summary: {e}")
    
    def force_run_task(self, name: str) -> bool:
        """Force run a specific task immediately."""
        try:
            if name not in self.tasks:
                logger.warning(f"Task not found: {name}")
                return False
            
            task = self.tasks[name]
            
            logger.info(f"Force running task: {name}")
            start_time = time.time()
            task['function']()
            duration = time.time() - start_time
            
            # Update task info
            task['last_run'] = time.time()
            task['run_count'] += 1
            
            # Record metrics
            self.metrics.record_processing_time(f"scheduled_task_{name}", duration)
            
            logger.info(f"Force completed task {name} in {duration:.2f}s")
            return True
            
        except Exception as e:
            logger.error(f"Error force running task {name}: {e}")
            if name in self.tasks:
                self.tasks[name]['error_count'] += 1
            return False
