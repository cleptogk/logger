#!/bin/bash
set -e

# Deploy Redis-based log processing architecture
# This replaces Gunicorn file parsing with Redis-cached log processing

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEPLOY_TARGET="${1:-ssdev}"

echo "🚀 Deploying Redis-based log architecture to $DEPLOY_TARGET"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if target is accessible
if ! ssh "$DEPLOY_TARGET" "echo 'Connection test successful'" >/dev/null 2>&1; then
    log_error "Cannot connect to $DEPLOY_TARGET"
    exit 1
fi

log_info "Connected to $DEPLOY_TARGET successfully"

# Step 1: Install Redis if not present
log_info "Step 1: Installing Redis server"
ssh "$DEPLOY_TARGET" "
    if ! command -v redis-server &> /dev/null; then
        sudo apt update
        sudo apt install -y redis-server
        sudo systemctl enable redis-server
        sudo systemctl start redis-server
        echo '✅ Redis installed and started'
    else
        echo '✅ Redis already installed'
    fi
    
    # Configure Redis for log processing
    sudo tee /etc/redis/redis-logging.conf > /dev/null << 'EOF'
# Redis configuration for log processing
port 6379
bind 127.0.0.1
maxmemory 512mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
EOF
    
    sudo systemctl restart redis-server
"

# Step 2: Create logging user and directories
log_info "Step 2: Setting up logging infrastructure"
ssh "$DEPLOY_TARGET" "
    # Create logserver user if not exists
    if ! id logserver &>/dev/null; then
        sudo useradd -r -s /bin/false -d /opt/logging logserver
        echo '✅ Created logserver user'
    fi
    
    # Create directories
    sudo mkdir -p /opt/logging/logger
    sudo mkdir -p /var/log/centralized
    sudo chown -R logserver:logserver /opt/logging
    sudo chmod 755 /opt/logging
    
    echo '✅ Directories created'
"

# Step 3: Deploy application files
log_info "Step 3: Deploying application files"

# Copy server files
scp -r "$PROJECT_ROOT/server" "$DEPLOY_TARGET:/tmp/logger-server"
scp "$PROJECT_ROOT/requirements.txt" "$DEPLOY_TARGET:/tmp/logger-requirements.txt"

ssh "$DEPLOY_TARGET" "
    sudo cp -r /tmp/logger-server /opt/logging/logger/
    sudo cp /tmp/logger-requirements.txt /opt/logging/logger/
    sudo chown -R logserver:logserver /opt/logging/logger
    sudo chmod +x /opt/logging/logger/server/*.py
    
    echo '✅ Application files deployed'
"

# Step 4: Install Python dependencies
log_info "Step 4: Installing Python dependencies"
ssh "$DEPLOY_TARGET" "
    cd /opt/logging/logger
    
    # Create virtual environment
    sudo -u logserver python3 -m venv venv
    
    # Install dependencies
    sudo -u logserver ./venv/bin/pip install --upgrade pip
    sudo -u logserver ./venv/bin/pip install -r requirements.txt
    sudo -u logserver ./venv/bin/pip install redis watchdog gunicorn
    
    echo '✅ Python dependencies installed'
"

# Step 5: Deploy systemd services
log_info "Step 5: Deploying systemd services"
scp "$PROJECT_ROOT/systemd/redis-log-processor.service" "$DEPLOY_TARGET:/tmp/"
scp "$PROJECT_ROOT/systemd/redis-log-api.service" "$DEPLOY_TARGET:/tmp/"

ssh "$DEPLOY_TARGET" "
    sudo cp /tmp/redis-log-processor.service /etc/systemd/system/
    sudo cp /tmp/redis-log-api.service /etc/systemd/system/
    
    sudo systemctl daemon-reload
    sudo systemctl enable redis-log-processor redis-log-api
    
    echo '✅ Systemd services configured'
"

# Step 6: Stop old services if they exist
log_info "Step 6: Stopping old log services"
ssh "$DEPLOY_TARGET" "
    # Stop old services if they exist
    for service in enhanced-logging-api logging-dashboard; do
        if systemctl is-active --quiet \$service; then
            sudo systemctl stop \$service
            sudo systemctl disable \$service
            echo '🛑 Stopped old service: \$service'
        fi
    done
"

# Step 7: Start new Redis-based services
log_info "Step 7: Starting Redis-based services"
ssh "$DEPLOY_TARGET" "
    # Start Redis log processor first
    sudo systemctl start redis-log-processor
    sleep 5
    
    # Start Redis log API
    sudo systemctl start redis-log-api
    sleep 3
    
    # Check status
    echo '📊 Service Status:'
    sudo systemctl status redis-log-processor --no-pager -l
    echo ''
    sudo systemctl status redis-log-api --no-pager -l
"

# Step 8: Verify deployment
log_info "Step 8: Verifying deployment"
ssh "$DEPLOY_TARGET" "
    # Test Redis connection
    redis-cli ping
    
    # Test API endpoint
    sleep 5
    curl -s http://localhost:8080/health | python3 -m json.tool
    
    echo ''
    echo '✅ Redis-based log architecture deployed successfully!'
    echo ''
    echo '📋 Service URLs:'
    echo '   - Health Check: http://$DEPLOY_TARGET:8080/health'
    echo '   - Redis Logs API: http://$DEPLOY_TARGET:8080/logger/redis/ssdev'
    echo '   - Redis Search: http://$DEPLOY_TARGET:8080/logger/search/redis/ssdev'
    echo ''
    echo '🔧 Management Commands:'
    echo '   - View processor logs: sudo journalctl -f -u redis-log-processor'
    echo '   - View API logs: sudo journalctl -f -u redis-log-api'
    echo '   - Redis CLI: redis-cli'
    echo '   - Restart services: sudo systemctl restart redis-log-processor redis-log-api'
"

log_info "🎉 Redis-based log architecture deployment completed!"
log_warn "Note: The background processor will start indexing existing logs automatically"
log_info "Monitor progress with: ssh $DEPLOY_TARGET 'sudo journalctl -f -u redis-log-processor'"
