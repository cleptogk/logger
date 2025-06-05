"""
Loguru Configuration Module
Centralized logging configuration using Loguru.
"""

import os
import sys
from pathlib import Path
from loguru import logger

def setup_logging():
    """Configure Loguru logging for the centralized logging server."""
    
    # Remove default handler
    logger.remove()
    
    # Get configuration from environment
    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    log_dir = Path(os.environ.get('LOG_BASE_DIR', '/var/log/centralized'))
    app_name = 'logging-server'
    
    # Ensure log directory exists
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Console handler with colors
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>",
        colorize=True,
        backtrace=True,
        diagnose=True
    )
    
    # File handler for application logs
    logger.add(
        log_dir / "sslog" / f"{app_name}.log",
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        rotation="100 MB",
        retention="90 days",
        compression="gz",
        backtrace=True,
        diagnose=True,
        enqueue=True  # Thread-safe logging
    )
    
    # Error-only file handler
    logger.add(
        log_dir / "sslog" / f"{app_name}-errors.log",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        rotation="50 MB",
        retention="180 days",
        compression="gz",
        backtrace=True,
        diagnose=True,
        enqueue=True
    )
    
    # JSON handler for structured logging (optional)
    if os.environ.get('STRUCTURED_LOGGING', 'false').lower() == 'true':
        logger.add(
            log_dir / "sslog" / f"{app_name}-structured.json",
            level=log_level,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} | {message}",
            serialize=True,  # JSON format
            rotation="100 MB",
            retention="90 days",
            compression="gz",
            enqueue=True
        )
    
    # Performance logging (DEBUG level only)
    if log_level == 'DEBUG':
        logger.add(
            log_dir / "sslog" / f"{app_name}-performance.log",
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | PERF | {name}:{function}:{line} | {message}",
            filter=lambda record: "PERF" in record["message"],
            rotation="50 MB",
            retention="7 days",
            compression="gz",
            enqueue=True
        )
    
    logger.info(f"Loguru logging configured - Level: {log_level}, Directory: {log_dir}")
    return logger

def get_logger(name: str):
    """Get a logger instance with the specified name."""
    return logger.bind(name=name)

def log_performance(func_name: str, duration: float, details: str = ""):
    """Log performance metrics."""
    logger.debug(f"PERF | {func_name} | {duration:.4f}s | {details}")

def log_ingestion(source: str, level: str, count: int):
    """Log ingestion metrics."""
    logger.info(f"INGESTION | Source: {source} | Level: {level} | Count: {count}")

def log_processing(operation: str, duration: float, records_processed: int):
    """Log processing metrics."""
    logger.info(f"PROCESSING | {operation} | {duration:.4f}s | Records: {records_processed}")

def log_error_with_context(error: Exception, context: dict = None):
    """Log errors with additional context."""
    context_str = f" | Context: {context}" if context else ""
    logger.error(f"ERROR | {type(error).__name__}: {error}{context_str}")

def log_health_check(component: str, status: str, details: str = ""):
    """Log health check results."""
    level = "info" if status == "ok" else "warning" if status == "degraded" else "error"
    getattr(logger, level)(f"HEALTH | {component} | {status.upper()} | {details}")

# Custom log levels for specific use cases
logger.level("INGESTION", no=25, color="<blue>")
logger.level("PROCESSING", no=25, color="<magenta>")
logger.level("HEALTH", no=25, color="<yellow>")
logger.level("PERF", no=15, color="<cyan>")
