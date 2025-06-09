# Memory Optimizations for Logging Container

## Problem
The logging container was using excessive memory (2.8GB+ for the API process alone), causing performance issues and high IO latency. The goal is to reduce memory usage to under 2GB total.

## Root Causes Identified
1. **Unlimited log file reading** - Reading entire large log files into memory
2. **No cache limits** - In-memory caches growing indefinitely
3. **Complex regex processing** - Heavy regex patterns on every log line
4. **No pagination limits** - API could return unlimited results
5. **Inefficient Gunicorn configuration** - Too many workers, no memory limits

## Optimizations Applied

### 1. Application-Level Optimizations (`log_api.py`)
- **File size limits**: Skip files larger than 50MB
- **Line limits**: Read max 10,000 lines per file
- **Result limits**: Hard cap at 500 results per request
- **Cache limits**: 
  - `log_files_cache`: Max 1,000 entries
  - `logs_storage`: Max 5,000 entries
- **Memory cleanup**: Automatic cache clearing + garbage collection
- **Early breaking**: Stop processing when enough results found

### 2. Flask Configuration
- **Request size limit**: 16MB max
- **Cache settings**: 5-minute file cache
- **JSON optimization**: Disable key sorting

### 3. Dashboard Optimizations (`dashboard_app.py`)
- **Reduced API calls**: Limit to 50 logs instead of 100
- **SocketIO limits**: 1MB buffer, shorter timeouts
- **Processing limits**: Only process first 50 logs for stats

### 4. Gunicorn Configuration

#### API Server (`gunicorn.conf.py`)
- **Workers**: Max 2 workers (was unlimited)
- **Worker class**: `sync` (more memory efficient)
- **Connections**: 100 per worker (was unlimited)
- **Request limits**: 500 requests before worker restart
- **Memory limit**: 512MB per worker
- **Timeouts**: 30 seconds (was unlimited)

#### Dashboard (`gunicorn-dashboard.conf.py`)
- **Workers**: 1 worker only
- **Worker class**: `eventlet` (for SocketIO)
- **Connections**: 50 per worker
- **Request limits**: 200 requests before restart
- **Memory limit**: 256MB per worker

### 5. Systemd Service Limits

#### Enhanced Logging API
```ini
MemoryMax=512M
MemoryHigh=400M
CPUQuota=100%
TasksMax=256
LimitNPROC=512
```

#### Logging Dashboard
```ini
MemoryMax=256M
MemoryHigh=200M
CPUQuota=50%
TasksMax=128
LimitNPROC=256
```

### 6. Memory Monitoring (`memory_monitor.py`)
- **Real-time monitoring**: Check every minute
- **Automatic restarts**: If memory limits exceeded
- **Restart protection**: Max 3 restarts per hour
- **System alerts**: Warning at 80%, critical at 90%

## Expected Memory Usage After Optimizations

| Service | Before | After | Limit |
|---------|--------|-------|-------|
| Enhanced Logging API | 2.8GB | ~400MB | 512MB |
| Logging Dashboard | 640MB | ~200MB | 256MB |
| **Total** | **3.4GB** | **~600MB** | **768MB** |

## Deployment Instructions

1. **Deploy optimizations**:
   ```bash
   cd /opt/logging/logger
   sudo ./scripts/deploy_memory_optimizations.sh
   ```

2. **Monitor deployment**:
   ```bash
   # Check service status
   sudo systemctl status enhanced-logging-api logging-dashboard memory-monitor
   
   # Monitor memory usage
   sudo journalctl -f -u memory-monitor
   
   # Check current memory
   ps aux | grep -E "(enhanced-logging-api|logging-dashboard)" | grep -v grep
   ```

3. **Manual memory cleanup** (if needed):
   ```bash
   curl -X POST http://localhost:8080/api/cleanup
   ```

## Monitoring Commands

```bash
# Real-time memory monitoring
watch 'ps aux | grep -E "(enhanced-logging-api|logging-dashboard)" | grep -v grep'

# System memory status
free -h

# Service logs
sudo journalctl -f -u enhanced-logging-api -u logging-dashboard

# Memory monitor logs
sudo journalctl -f -u memory-monitor
```

## Rollback Instructions

If issues occur, rollback using:
```bash
# Stop new services
sudo systemctl stop enhanced-logging-api logging-dashboard memory-monitor

# Restore from backup (check /opt/logging/backups/ for latest)
BACKUP_DIR="/opt/logging/backups/YYYYMMDD_HHMMSS"
sudo cp "$BACKUP_DIR"/*.service /etc/systemd/system/

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl start enhanced-logging-api logging-dashboard
```

## Additional Recommendations

1. **Log rotation**: Ensure log files don't grow too large
2. **Disk cleanup**: Regular cleanup of old log files
3. **Database optimization**: Consider SQLite for structured logs
4. **Caching strategy**: Implement Redis with memory limits if needed
5. **Load balancing**: Consider multiple smaller containers vs one large container
