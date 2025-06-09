#!/usr/bin/env python3
"""
Memory monitoring script for logging services.
Monitors memory usage and restarts services if they exceed limits.
"""

import os
import sys
import time
import psutil
import subprocess
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/memory_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Memory limits (in MB)
MEMORY_LIMITS = {
    'enhanced-logging-api': 512,  # 512MB
    'logging-dashboard': 256,     # 256MB
}

# Warning thresholds (80% of limit)
WARNING_THRESHOLDS = {
    name: limit * 0.8 for name, limit in MEMORY_LIMITS.items()
}

def get_process_memory(process_name):
    """Get memory usage for a process by name."""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cmdline']):
            try:
                # Check if process name matches or is in command line
                if (process_name in proc.info['name'] or 
                    any(process_name in arg for arg in proc.info['cmdline'] or [])):
                    
                    memory_mb = proc.info['memory_info'].rss / 1024 / 1024
                    return proc.info['pid'], memory_mb
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        logger.error(f"Error getting process memory for {process_name}: {e}")
    
    return None, 0

def restart_service(service_name):
    """Restart a systemd service."""
    try:
        logger.warning(f"Restarting service: {service_name}")
        result = subprocess.run(
            ['sudo', 'systemctl', 'restart', service_name],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            logger.info(f"Successfully restarted {service_name}")
            return True
        else:
            logger.error(f"Failed to restart {service_name}: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout restarting {service_name}")
        return False
    except Exception as e:
        logger.error(f"Error restarting {service_name}: {e}")
        return False

def check_system_memory():
    """Check overall system memory usage."""
    try:
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        memory_percent = memory.percent
        swap_percent = swap.percent if swap.total > 0 else 0
        
        logger.info(f"System Memory: {memory_percent:.1f}% used, Swap: {swap_percent:.1f}% used")
        
        # Alert if system memory is critically high
        if memory_percent > 90:
            logger.critical(f"CRITICAL: System memory usage at {memory_percent:.1f}%")
        elif memory_percent > 80:
            logger.warning(f"WARNING: System memory usage at {memory_percent:.1f}%")
            
        return memory_percent, swap_percent
        
    except Exception as e:
        logger.error(f"Error checking system memory: {e}")
        return 0, 0

def monitor_services():
    """Monitor memory usage of logging services."""
    logger.info("Starting memory monitoring...")
    
    restart_counts = {service: 0 for service in MEMORY_LIMITS.keys()}
    last_restart = {service: 0 for service in MEMORY_LIMITS.keys()}
    
    while True:
        try:
            # Check system memory first
            sys_memory, sys_swap = check_system_memory()
            
            # Check each service
            for service_name, memory_limit in MEMORY_LIMITS.items():
                pid, memory_usage = get_process_memory(service_name)
                
                if pid:
                    logger.info(f"{service_name} (PID {pid}): {memory_usage:.1f}MB / {memory_limit}MB")
                    
                    # Check if memory usage exceeds limit
                    if memory_usage > memory_limit:
                        logger.critical(f"MEMORY LIMIT EXCEEDED: {service_name} using {memory_usage:.1f}MB (limit: {memory_limit}MB)")
                        
                        # Prevent restart loops (max 3 restarts per hour)
                        current_time = time.time()
                        if (current_time - last_restart[service_name] > 1200 and  # 20 minutes
                            restart_counts[service_name] < 3):
                            
                            if restart_service(service_name):
                                restart_counts[service_name] += 1
                                last_restart[service_name] = current_time
                            
                        else:
                            logger.error(f"Service {service_name} restart limit reached or too recent")
                    
                    # Warning threshold
                    elif memory_usage > WARNING_THRESHOLDS[service_name]:
                        logger.warning(f"WARNING: {service_name} using {memory_usage:.1f}MB (threshold: {WARNING_THRESHOLDS[service_name]:.1f}MB)")
                
                else:
                    logger.warning(f"Service {service_name} not found or not running")
            
            # Reset restart counts every hour
            current_time = time.time()
            for service in restart_counts:
                if current_time - last_restart[service] > 3600:  # 1 hour
                    restart_counts[service] = 0
            
            # Wait before next check
            time.sleep(60)  # Check every minute
            
        except KeyboardInterrupt:
            logger.info("Memory monitoring stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
            time.sleep(60)

if __name__ == "__main__":
    monitor_services()
