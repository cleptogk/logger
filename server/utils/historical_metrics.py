"""
Historical Metrics Storage Module
Preserves metrics data even when logs are aggressively rotated.
"""

import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from loguru import logger


class HistoricalMetrics:
    """Stores and retrieves historical metrics data using Redis."""
    
    def __init__(self, redis_client):
        """Initialize historical metrics storage."""
        self.redis = redis_client
        self.metrics_key_prefix = "historical_metrics"
        self.retention_days = 30  # Keep 30 days of historical data
        
        # Metric collection intervals
        self.hourly_key = f"{self.metrics_key_prefix}:hourly"
        self.daily_key = f"{self.metrics_key_prefix}:daily"
        
        logger.info("✅ Historical metrics storage initialized")
    
    def record_hourly_snapshot(self, metrics: Dict[str, Any]) -> bool:
        """Record an hourly metrics snapshot."""
        try:
            timestamp = datetime.now().isoformat()
            snapshot = {
                'timestamp': timestamp,
                'hour': datetime.now().strftime('%Y-%m-%d %H:00'),
                'metrics': metrics
            }
            
            # Add to hourly list (keep last 24*30 = 720 hours = 30 days)
            self.redis.lpush(self.hourly_key, snapshot)
            self.redis.ltrim(self.hourly_key, 0, 719)  # Keep last 720 entries
            
            logger.debug(f"Recorded hourly metrics snapshot: {timestamp}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to record hourly snapshot: {e}")
            return False
    
    def record_daily_summary(self, date: str, summary: Dict[str, Any]) -> bool:
        """Record a daily metrics summary."""
        try:
            daily_summary = {
                'date': date,
                'timestamp': datetime.now().isoformat(),
                'summary': summary
            }
            
            # Add to daily list (keep last 30 days)
            self.redis.lpush(self.daily_key, daily_summary)
            self.redis.ltrim(self.daily_key, 0, 29)  # Keep last 30 entries
            
            logger.info(f"Recorded daily summary for {date}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to record daily summary: {e}")
            return False
    
    def get_hourly_metrics(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get hourly metrics for the last N hours."""
        try:
            # Get the last N hours of data
            snapshots = self.redis.lrange(self.hourly_key, 0, hours - 1)
            return snapshots
            
        except Exception as e:
            logger.error(f"Failed to get hourly metrics: {e}")
            return []
    
    def get_daily_summaries(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get daily summaries for the last N days."""
        try:
            summaries = self.redis.lrange(self.daily_key, 0, days - 1)
            return summaries
            
        except Exception as e:
            logger.error(f"Failed to get daily summaries: {e}")
            return []
    
    def get_metrics_for_timerange(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get metrics for a specific time range."""
        try:
            all_hourly = self.redis.lrange(self.hourly_key, 0, -1)
            
            filtered_metrics = []
            for snapshot in all_hourly:
                snapshot_time = datetime.fromisoformat(snapshot['timestamp'])
                if start_time <= snapshot_time <= end_time:
                    filtered_metrics.append(snapshot)
            
            # Sort by timestamp (newest first)
            filtered_metrics.sort(key=lambda x: x['timestamp'], reverse=True)
            return filtered_metrics
            
        except Exception as e:
            logger.error(f"Failed to get metrics for timerange: {e}")
            return []
    
    def calculate_daily_summary(self, date: str) -> Dict[str, Any]:
        """Calculate daily summary from hourly data."""
        try:
            # Get all hourly data for the specified date
            start_time = datetime.strptime(date, '%Y-%m-%d')
            end_time = start_time + timedelta(days=1)
            
            hourly_data = self.get_metrics_for_timerange(start_time, end_time)
            
            if not hourly_data:
                return {}
            
            # Calculate aggregated metrics
            total_logs = sum(h['metrics'].get('total_logs_today', 0) for h in hourly_data)
            avg_ingestion_rate = sum(h['metrics'].get('ingestion_rate', 0) for h in hourly_data) / len(hourly_data)
            avg_error_rate = sum(h['metrics'].get('error_rate', 0) for h in hourly_data) / len(hourly_data)
            max_disk_usage = max(h['metrics'].get('disk_usage', 0) for h in hourly_data)
            
            # Count unique active sources
            all_sources = set()
            for h in hourly_data:
                sources = h['metrics'].get('active_sources', [])
                if isinstance(sources, list):
                    all_sources.update(sources)
            
            summary = {
                'date': date,
                'total_logs_processed': total_logs,
                'avg_ingestion_rate': round(avg_ingestion_rate, 2),
                'avg_error_rate': round(avg_error_rate, 2),
                'max_disk_usage': round(max_disk_usage, 2),
                'unique_active_sources': len(all_sources),
                'active_sources': list(all_sources),
                'data_points': len(hourly_data),
                'calculated_at': datetime.now().isoformat()
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to calculate daily summary: {e}")
            return {}
    
    def get_trend_data(self, metric_name: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get trend data for a specific metric."""
        try:
            hourly_data = self.get_hourly_metrics(hours)
            
            trend_data = []
            for snapshot in reversed(hourly_data):  # Oldest first for trend
                if metric_name in snapshot['metrics']:
                    trend_data.append({
                        'timestamp': snapshot['timestamp'],
                        'hour': snapshot['hour'],
                        'value': snapshot['metrics'][metric_name]
                    })
            
            return trend_data
            
        except Exception as e:
            logger.error(f"Failed to get trend data for {metric_name}: {e}")
            return []
    
    def get_dashboard_historical_data(self) -> Dict[str, Any]:
        """Get comprehensive historical data for dashboard display."""
        try:
            # Get recent hourly data (last 24 hours)
            hourly_data = self.get_hourly_metrics(24)
            
            # Get recent daily summaries (last 7 days)
            daily_summaries = self.get_daily_summaries(7)
            
            # Calculate trends
            ingestion_trend = self.get_trend_data('ingestion_rate', 24)
            error_trend = self.get_trend_data('error_rate', 24)
            disk_trend = self.get_trend_data('disk_usage', 24)
            
            # Calculate current vs historical averages
            current_metrics = hourly_data[0]['metrics'] if hourly_data else {}
            
            # 24-hour averages
            if hourly_data:
                avg_24h_ingestion = sum(h['metrics'].get('ingestion_rate', 0) for h in hourly_data) / len(hourly_data)
                avg_24h_error_rate = sum(h['metrics'].get('error_rate', 0) for h in hourly_data) / len(hourly_data)
            else:
                avg_24h_ingestion = 0
                avg_24h_error_rate = 0
            
            return {
                'current_metrics': current_metrics,
                'hourly_snapshots': hourly_data[:12],  # Last 12 hours for display
                'daily_summaries': daily_summaries,
                'trends': {
                    'ingestion_rate': ingestion_trend,
                    'error_rate': error_trend,
                    'disk_usage': disk_trend
                },
                'averages_24h': {
                    'ingestion_rate': round(avg_24h_ingestion, 2),
                    'error_rate': round(avg_24h_error_rate, 2)
                },
                'data_availability': {
                    'hourly_points': len(hourly_data),
                    'daily_summaries': len(daily_summaries),
                    'oldest_hourly': hourly_data[-1]['timestamp'] if hourly_data else None,
                    'newest_hourly': hourly_data[0]['timestamp'] if hourly_data else None
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get dashboard historical data: {e}")
            return {}
    
    def cleanup_old_data(self) -> bool:
        """Clean up data older than retention period."""
        try:
            # Redis LTRIM already handles this automatically
            # This method is for any additional cleanup if needed
            logger.info("Historical metrics cleanup completed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            return False
