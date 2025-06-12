"""
Metrics Exporter Module
Handles Prometheus metrics collection and export for the logging server.
"""

import time
import psutil
from datetime import datetime
from typing import Dict, Any, Optional
from loguru import logger
from prometheus_client import Counter, Histogram, Gauge, Info, CollectorRegistry, REGISTRY

class MetricsExporter:
    """Prometheus metrics exporter for logging server with historical data preservation."""

    def __init__(self, redis_client=None):
        """Initialize metrics collectors and historical storage."""
        self.redis_client = redis_client
        self.historical_metrics = None

        # Initialize historical metrics if Redis is available
        if redis_client:
            from .historical_metrics import HistoricalMetrics
            self.historical_metrics = HistoricalMetrics(redis_client)

        # Track last snapshot time for hourly recording
        self._last_snapshot_hour = None

        try:
            # Log ingestion metrics
            self.logs_ingested_total = Counter(
                'logs_ingested_total',
                'Total number of logs ingested',
                ['host', 'application', 'component', 'level']
            )
        except ValueError:
            # Metric already exists, get existing one
            for collector in REGISTRY._collector_to_names:
                if hasattr(collector, '_name') and collector._name == 'logs_ingested_total':
                    self.logs_ingested_total = collector
                    break
        
        # Processing metrics
        self.log_processing_duration = Histogram(
            'log_processing_duration_seconds',
            'Time spent processing logs',
            ['operation']
        )
        
        # System metrics
        self.system_cpu_usage = Gauge('system_cpu_usage_percent', 'CPU usage percentage')
        self.system_memory_usage = Gauge('system_memory_usage_percent', 'Memory usage percentage')
        self.system_disk_usage = Gauge('system_disk_usage_percent', 'Disk usage percentage')
        
        # Application metrics
        self.active_connections = Gauge('active_connections', 'Number of active connections')
        self.log_files_monitored = Gauge('log_files_monitored', 'Number of log files being monitored')
        self.redis_connection_status = Gauge('redis_connection_status', 'Redis connection status (1=connected, 0=disconnected)')
        
        # Error metrics
        self.errors_total = Counter('errors_total', 'Total number of errors', ['component', 'error_type'])
        
        # Performance metrics
        self.ingestion_rate = Gauge('ingestion_rate_logs_per_second', 'Log ingestion rate')
        self.processing_latency = Gauge('processing_latency_seconds', 'Average processing latency')
        self.error_rate = Gauge('error_rate_percent', 'Error rate percentage')
        
        # Application info
        self.app_info = Info('logging_server_info', 'Logging server information')
        self.app_info.info({
            'version': '1.0.0',
            'component': 'centralized-logging-server'
        })
        
        # Internal tracking
        self._start_time = time.time()
        self._last_ingestion_count = 0
        self._last_ingestion_time = time.time()
        self._processing_times = []
        self._error_count = 0
        self._total_logs = 0
        
        logger.info("✅ Metrics exporter initialized")
    
    def record_log_ingestion(self, host: str, application: str, component: str, level: str, count: int = 1):
        """Record log ingestion metrics."""
        try:
            self.logs_ingested_total.labels(
                host=host,
                application=application, 
                component=component,
                level=level
            ).inc(count)
            
            self._total_logs += count
            self._update_ingestion_rate()
            
        except Exception as e:
            logger.error(f"Failed to record log ingestion: {e}")
    
    def record_processing_time(self, operation: str, duration: float):
        """Record processing time metrics."""
        try:
            self.log_processing_duration.labels(operation=operation).observe(duration)
            
            # Track for average calculation
            self._processing_times.append(duration)
            if len(self._processing_times) > 1000:  # Keep last 1000 measurements
                self._processing_times = self._processing_times[-1000:]
            
            self._update_processing_latency()
            
        except Exception as e:
            logger.error(f"Failed to record processing time: {e}")
    
    def record_error(self, component: str, error_type: str):
        """Record error metrics."""
        try:
            self.errors_total.labels(component=component, error_type=error_type).inc()
            self._error_count += 1
            self._update_error_rate()
            
        except Exception as e:
            logger.error(f"Failed to record error: {e}")
    
    def update_system_metrics(self):
        """Update system resource metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.system_cpu_usage.set(cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.system_memory_usage.set(memory.percent)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            self.system_disk_usage.set(disk_percent)
            
        except Exception as e:
            logger.error(f"Failed to update system metrics: {e}")
    
    def set_active_connections(self, count: int):
        """Set the number of active connections."""
        try:
            self.active_connections.set(count)
        except Exception as e:
            logger.error(f"Failed to set active connections: {e}")
    
    def set_monitored_files(self, count: int):
        """Set the number of monitored log files."""
        try:
            self.log_files_monitored.set(count)
        except Exception as e:
            logger.error(f"Failed to set monitored files: {e}")
    
    def set_redis_status(self, connected: bool):
        """Set Redis connection status."""
        try:
            self.redis_connection_status.set(1 if connected else 0)
        except Exception as e:
            logger.error(f"Failed to set Redis status: {e}")
    
    def get_ingestion_rate(self) -> float:
        """Get current ingestion rate (logs per second)."""
        return self.ingestion_rate._value._value if hasattr(self.ingestion_rate, '_value') else 0.0
    
    def get_processing_latency(self) -> float:
        """Get average processing latency."""
        return self.processing_latency._value._value if hasattr(self.processing_latency, '_value') else 0.0
    
    def get_error_rate(self) -> float:
        """Get current error rate percentage."""
        return self.error_rate._value._value if hasattr(self.error_rate, '_value') else 0.0
    
    def get_disk_usage(self) -> float:
        """Get current disk usage percentage."""
        return self.system_disk_usage._value._value if hasattr(self.system_disk_usage, '_value') else 0.0
    
    def get_uptime(self) -> float:
        """Get server uptime in seconds."""
        return time.time() - self._start_time
    
    def _update_ingestion_rate(self):
        """Update ingestion rate calculation."""
        try:
            current_time = time.time()
            time_diff = current_time - self._last_ingestion_time
            
            if time_diff >= 1.0:  # Update every second
                logs_diff = self._total_logs - self._last_ingestion_count
                rate = logs_diff / time_diff if time_diff > 0 else 0
                
                self.ingestion_rate.set(rate)
                
                self._last_ingestion_count = self._total_logs
                self._last_ingestion_time = current_time
                
        except Exception as e:
            logger.error(f"Failed to update ingestion rate: {e}")
    
    def _update_processing_latency(self):
        """Update average processing latency."""
        try:
            if self._processing_times:
                avg_latency = sum(self._processing_times) / len(self._processing_times)
                self.processing_latency.set(avg_latency)
        except Exception as e:
            logger.error(f"Failed to update processing latency: {e}")
    
    def _update_error_rate(self):
        """Update error rate percentage."""
        try:
            if self._total_logs > 0:
                error_rate = (self._error_count / self._total_logs) * 100
                self.error_rate.set(error_rate)
        except Exception as e:
            logger.error(f"Failed to update error rate: {e}")
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics."""
        stats = {
            'uptime_seconds': self.get_uptime(),
            'total_logs_processed': self._total_logs,
            'ingestion_rate': self.get_ingestion_rate(),
            'processing_latency': self.get_processing_latency(),
            'error_rate': self.get_error_rate(),
            'error_count': self._error_count,
            'disk_usage': self.get_disk_usage()
        }

        # Record hourly snapshot if needed
        self._maybe_record_hourly_snapshot(stats)

        return stats

    def _maybe_record_hourly_snapshot(self, stats: Dict[str, Any]):
        """Record hourly snapshot if we've crossed into a new hour."""
        try:
            if not self.historical_metrics:
                return

            current_hour = datetime.now().strftime('%Y-%m-%d %H')

            if self._last_snapshot_hour != current_hour:
                # Add additional metrics for historical tracking
                enhanced_stats = stats.copy()
                enhanced_stats.update({
                    'total_logs_today': self._total_logs,
                    'active_sources': [],  # Will be populated by log processor
                    'timestamp': datetime.now().isoformat()
                })

                self.historical_metrics.record_hourly_snapshot(enhanced_stats)
                self._last_snapshot_hour = current_hour

        except Exception as e:
            logger.error(f"Failed to record hourly snapshot: {e}")

    def get_historical_data(self) -> Dict[str, Any]:
        """Get historical metrics data for dashboard."""
        try:
            if not self.historical_metrics:
                return {'error': 'Historical metrics not available'}

            return self.historical_metrics.get_dashboard_historical_data()

        except Exception as e:
            logger.error(f"Failed to get historical data: {e}")
            return {'error': str(e)}

    def record_daily_summary(self, date: str = None):
        """Record daily summary (typically called by scheduler)."""
        try:
            if not self.historical_metrics:
                return False

            if not date:
                date = datetime.now().strftime('%Y-%m-%d')

            summary = self.historical_metrics.calculate_daily_summary(date)
            if summary:
                return self.historical_metrics.record_daily_summary(date, summary)

            return False

        except Exception as e:
            logger.error(f"Failed to record daily summary: {e}")
            return False
