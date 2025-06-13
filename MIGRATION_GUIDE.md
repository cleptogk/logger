# Migration Guide: File-Based → Redis-Based Log Processing

## 🎯 **QUICK MIGRATION (Recommended)**

### **1. Deploy Redis Architecture**
```bash
cd /Users/clepto/Downloads/apps/logger
./scripts/deploy_redis_architecture.sh ssdev
```

### **2. Verify Deployment**
```bash
# Check services
ssh ssdev "sudo systemctl status redis-log-processor redis-log-api"

# Test API
curl "http://ssdev:8080/health"
curl "http://ssdev:8080/logger/redis/ssdev?limit=10"
```

### **3. Update Frontend (if applicable)**
```javascript
// Change API endpoints from:
fetch('/logger/ssdev?limit=100')

// To:
fetch('/logger/redis/ssdev?limit=100')
```

---

## 🔄 **GRADUAL MIGRATION (Conservative)**

### **Phase 1: Deploy Redis Services (No Disruption)**
```bash
# Deploy Redis services alongside existing ones
./scripts/deploy_redis_architecture.sh ssdev

# Both systems run in parallel:
# - Old: http://ssdev:8080/logger/ssdev (file-based)
# - New: http://ssdev:8080/logger/redis/ssdev (Redis-based)
```

### **Phase 2: Performance Testing**
```bash
# Compare performance
time curl "http://ssdev:8080/logger/ssdev?limit=100"        # Old
time curl "http://ssdev:8080/logger/redis/ssdev?limit=100"  # New

# Monitor resources
ssh ssdev "watch 'ps aux | grep -E \"(redis|gunicorn)\" | head -10'"
```

### **Phase 3: Switch Traffic**
```bash
# Update nginx/load balancer to route to Redis endpoints
# OR update application code to use new endpoints
```

### **Phase 4: Remove Old Services**
```bash
ssh ssdev "
    sudo systemctl stop enhanced-logging-api logging-dashboard
    sudo systemctl disable enhanced-logging-api logging-dashboard
"
```

---

## 📋 **ENDPOINT MAPPING**

| Old Endpoint | New Endpoint | Notes |
|--------------|--------------|-------|
| `/logger/{host}` | `/logger/redis/{host}` | Same parameters |
| `/logger/search/{host}` | `/logger/search/redis/{host}` | Faster search |
| `/logger/stats/{host}` | `/logger/stats/redis/{host}` | Real-time stats |
| `/health` | `/health` | Enhanced with Redis status |

### **Parameter Compatibility**
All existing query parameters work with Redis endpoints:
- `?app=sports-scheduler`
- `?component=iptv-orchestrator`
- `?level=ERROR`
- `?refresh_id=Refresh-47`
- `?step=6`
- `?time=yesterday around 7am`
- `?search=workflow`
- `?limit=100&offset=200`

---

## 🔧 **CONFIGURATION CHANGES**

### **Environment Variables**
```bash
# Add to /etc/environment or service files
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0
LOG_TTL_HOURS=24
MAX_LINES_PER_FILE=5000
MAX_FILE_SIZE_MB=50
```

### **Redis Configuration**
```bash
# /etc/redis/redis-logging.conf
port 6379
bind 127.0.0.1
maxmemory 512mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

---

## 🚨 **ROLLBACK PLAN**

### **If Issues Occur**
```bash
# Stop Redis services
ssh ssdev "sudo systemctl stop redis-log-processor redis-log-api"

# Restart old services (if still installed)
ssh ssdev "sudo systemctl start enhanced-logging-api logging-dashboard"

# Or deploy old architecture
cd /Users/clepto/Downloads/apps/logger
./scripts/deploy_memory_optimizations.sh
```

### **Data Recovery**
```bash
# Redis data is cached, original log files unchanged
# No data loss possible - Redis only caches parsed data
# Original files remain in /var/log/centralized/
```

---

## 📊 **MONITORING MIGRATION**

### **Key Metrics During Migration**
```bash
# Memory usage comparison
ssh ssdev "
    echo 'OLD SERVICES:'
    ps aux | grep enhanced-logging-api | grep -v grep
    echo 'NEW SERVICES:'
    ps aux | grep redis-log | grep -v grep
"

# Response time comparison
echo 'OLD API:' && time curl -s "http://ssdev:8080/logger/ssdev?limit=10" > /dev/null
echo 'NEW API:' && time curl -s "http://ssdev:8080/logger/redis/ssdev?limit=10" > /dev/null

# Redis statistics
ssh ssdev "redis-cli info memory | grep used_memory_human"
```

### **Success Criteria**
- ✅ Redis API responds in <200ms
- ✅ Memory usage <500MB total
- ✅ CPU usage <20% during queries
- ✅ All log data accessible via Redis API
- ✅ Real-time updates working

---

## 🎯 **POST-MIGRATION TASKS**

### **1. Update Documentation**
```bash
# Update API documentation to reference Redis endpoints
# Update monitoring dashboards
# Update alerting rules
```

### **2. Performance Optimization**
```bash
# Monitor Redis memory usage
redis-cli info memory

# Adjust TTL if needed
# Tune worker count based on load
# Configure Redis persistence if required
```

### **3. Cleanup**
```bash
# Remove old service files after successful migration
ssh ssdev "
    sudo rm /etc/systemd/system/enhanced-logging-api.service
    sudo rm /etc/systemd/system/logging-dashboard.service
    sudo systemctl daemon-reload
"
```

---

## 🔍 **TROUBLESHOOTING**

### **Common Migration Issues**

| Issue | Symptom | Solution |
|-------|---------|----------|
| **Redis not starting** | Connection refused | Check Redis installation: `sudo systemctl status redis-server` |
| **No data in Redis** | Empty responses | Check processor: `sudo journalctl -u redis-log-processor` |
| **Old API still used** | High memory usage | Update application endpoints |
| **Permission errors** | Service won't start | Check logserver user permissions |

### **Validation Commands**
```bash
# Test Redis connection
ssh ssdev "redis-cli ping"

# Check log processing
ssh ssdev "redis-cli keys 'logs:*' | head -5"

# Verify API health
curl "http://ssdev:8080/health" | jq .

# Check service logs
ssh ssdev "sudo journalctl -u redis-log-processor --since '5 minutes ago'"
```

---

## ✅ **MIGRATION CHECKLIST**

- [ ] Redis server installed and running
- [ ] Redis log processor service deployed
- [ ] Redis log API service deployed
- [ ] Health check endpoint responding
- [ ] Sample queries returning data
- [ ] Performance meets expectations
- [ ] Monitoring configured
- [ ] Documentation updated
- [ ] Old services stopped (if desired)
- [ ] Team notified of new endpoints

**Estimated Migration Time: 15-30 minutes**
**Downtime Required: 0 minutes (parallel deployment)**
