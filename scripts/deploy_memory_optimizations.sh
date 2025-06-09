#!/bin/bash
"""
Deploy memory optimizations for logging services.
This script applies all memory optimization changes.
"""

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
LOGGER_DIR="/opt/logging/logger"
SYSTEMD_DIR="/etc/systemd/system"
BACKUP_DIR="/opt/logging/backups/$(date +%Y%m%d_%H%M%S)"

echo -e "${GREEN}=== Deploying Memory Optimizations for Logging Services ===${NC}"

# Create backup directory
echo -e "${YELLOW}Creating backup directory...${NC}"
sudo mkdir -p "$BACKUP_DIR"

# Backup existing configurations
echo -e "${YELLOW}Backing up existing configurations...${NC}"
if [ -f "$SYSTEMD_DIR/enhanced-logging-api.service" ]; then
    sudo cp "$SYSTEMD_DIR/enhanced-logging-api.service" "$BACKUP_DIR/"
fi
if [ -f "$SYSTEMD_DIR/logging-dashboard.service" ]; then
    sudo cp "$SYSTEMD_DIR/logging-dashboard.service" "$BACKUP_DIR/"
fi

# Stop existing services
echo -e "${YELLOW}Stopping existing services...${NC}"
sudo systemctl stop enhanced-logging-api.service 2>/dev/null || true
sudo systemctl stop logging-dashboard.service 2>/dev/null || true

# Copy new systemd service files
echo -e "${YELLOW}Installing optimized systemd service files...${NC}"
sudo cp "$LOGGER_DIR/systemd/enhanced-logging-api.service" "$SYSTEMD_DIR/"
sudo cp "$LOGGER_DIR/systemd/logging-dashboard.service" "$SYSTEMD_DIR/"

# Set proper permissions
sudo chmod 644 "$SYSTEMD_DIR/enhanced-logging-api.service"
sudo chmod 644 "$SYSTEMD_DIR/logging-dashboard.service"

# Copy Gunicorn configuration files
echo -e "${YELLOW}Installing Gunicorn configuration files...${NC}"
sudo cp "$LOGGER_DIR/gunicorn.conf.py" "$LOGGER_DIR/"
sudo cp "$LOGGER_DIR/gunicorn-dashboard.conf.py" "$LOGGER_DIR/"
sudo chown logserver:logserver "$LOGGER_DIR/gunicorn*.conf.py"

# Install memory monitor script
echo -e "${YELLOW}Installing memory monitor script...${NC}"
sudo cp "$LOGGER_DIR/scripts/memory_monitor.py" "/usr/local/bin/"
sudo chmod +x "/usr/local/bin/memory_monitor.py"

# Create memory monitor systemd service
echo -e "${YELLOW}Creating memory monitor service...${NC}"
sudo tee "$SYSTEMD_DIR/memory-monitor.service" > /dev/null << 'EOF'
[Unit]
Description=Memory Monitor for Logging Services
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 /usr/local/bin/memory_monitor.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd daemon
echo -e "${YELLOW}Reloading systemd daemon...${NC}"
sudo systemctl daemon-reload

# Enable services
echo -e "${YELLOW}Enabling services...${NC}"
sudo systemctl enable enhanced-logging-api.service
sudo systemctl enable logging-dashboard.service
sudo systemctl enable memory-monitor.service

# Start services
echo -e "${YELLOW}Starting optimized services...${NC}"
sudo systemctl start enhanced-logging-api.service
sudo systemctl start logging-dashboard.service
sudo systemctl start memory-monitor.service

# Wait a moment for services to start
sleep 5

# Check service status
echo -e "${YELLOW}Checking service status...${NC}"
echo "Enhanced Logging API:"
sudo systemctl status enhanced-logging-api.service --no-pager -l

echo -e "\nLogging Dashboard:"
sudo systemctl status logging-dashboard.service --no-pager -l

echo -e "\nMemory Monitor:"
sudo systemctl status memory-monitor.service --no-pager -l

# Show memory usage
echo -e "${YELLOW}Current memory usage:${NC}"
ps aux | grep -E "(enhanced-logging-api|logging-dashboard)" | grep -v grep

echo -e "${GREEN}=== Memory Optimization Deployment Complete ===${NC}"
echo -e "${YELLOW}Backup created at: $BACKUP_DIR${NC}"
echo -e "${YELLOW}Monitor logs with: sudo journalctl -f -u enhanced-logging-api -u logging-dashboard -u memory-monitor${NC}"
