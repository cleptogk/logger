# Centralized Logging Server

A comprehensive centralized logging solution built with Python, featuring real-time log ingestion, processing, and visualization.

## Features

- **Real-time Log Ingestion**: Receives logs from multiple sources via rsyslog
- **Advanced Processing**: Uses Loguru, Watchdog, and PyParsing for intelligent log handling
- **Interactive Dashboard**: Web-based interface with Chart.js visualizations
- **Automated Management**: APScheduler for maintenance, rotation, and cleanup
- **Metrics & Monitoring**: Prometheus integration for system health monitoring
- **Multi-VM Support**: Centralized logging for ssdev, ssdvr, ssmcp, ssrun

## Technology Stack

### Backend
- **Python 3.11+** - Core application runtime
- **Loguru** - Advanced logging with structured output and rotation
- **Watchdog** - Real-time file system monitoring
- **PyParsing** - Log parsing and pattern matching
- **APScheduler** - Scheduled maintenance and cleanup tasks
- **Prometheus Client** - Metrics collection and export
- **Flask** - Web framework for API and dashboard
- **Gunicorn** - WSGI server for production deployment
- **Redis** - Caching and real-time data storage

### Frontend
- **Chart.js 4.4.0** - Interactive data visualizations
- **Bootstrap 5.3** - Responsive UI framework
- **jQuery 3.7** - DOM manipulation and AJAX
- **WebSockets** - Real-time log streaming

### Infrastructure
- **rsyslog** - Log ingestion and forwarding
- **nginx** - Reverse proxy and static file serving
- **systemd** - Service management and monitoring

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Remote VMs    │    │  Logging Server │    │   Dashboard     │
│                 │    │                 │    │                 │
│ ssdev, ssdvr,   │───▶│   rsyslog:514   │───▶│  Chart.js UI    │
│ ssmcp, ssrun    │    │                 │    │                 │
└─────────────────┘    │ ┌─────────────┐ │    └─────────────────┘
                       │ │   Loguru    │ │
                       │ │  Watchdog   │ │    ┌─────────────────┐
                       │ │ PyParsing   │ │    │   Prometheus    │
                       │ │APScheduler  │ │───▶│    Metrics      │
                       │ └─────────────┘ │    │                 │
                       └─────────────────┘    └─────────────────┘
```

## Directory Structure

```
/opt/logging/
├── server/           # Core logging server application
├── dashboard/        # Web dashboard application
├── config/          # Configuration files
├── scripts/         # Maintenance and utility scripts
├── web/             # Static web assets
└── venv/            # Python virtual environment

/var/log/centralized/
├── ssdev/           # Development server logs
├── ssdvr/           # DVR server logs
├── ssmcp/           # Management server logs
├── ssrun/           # Runner server logs
├── processed/       # Processed log archives
└── alerts/          # Alert and notification logs
```

## Installation

### Prerequisites
- Debian 12+ or Ubuntu 20.04+
- Python 3.11+
- Redis server
- nginx
- rsyslog

### Automated Deployment
Deploy using Ansible from OrchestrixMCP:

```bash
ansible-playbook playbooks/deploy-sslog.yml
```

### Manual Installation
1. Clone the repository:
```bash
git clone https://github.com/cleptogk/logger.git
cd logger
```

2. Create virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure services:
```bash
sudo cp config/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable logging-server logging-dashboard
```

## Configuration

### Environment Variables
Key configuration options in `/opt/logging/config/environment`:

- `LOG_LEVEL` - Logging verbosity (DEBUG, INFO, WARNING, ERROR)
- `LOG_RETENTION_DAYS` - How long to keep logs (default: 90)
- `MAX_WORKERS` - Processing worker threads (default: 4)
- `WEB_DASHBOARD_PORT` - Dashboard port (default: 8081)
- `METRICS_PORT` - Prometheus metrics port (default: 9090)

### Log Sources
Configure remote VMs to forward logs to the centralized server:

```bash
# On remote VMs, add to /etc/rsyslog.conf:
*.* @@logger.johnsons.lcl:514
```

## Usage

### Starting Services
```bash
sudo systemctl start logging-server
sudo systemctl start logging-dashboard
```

### Accessing Dashboard
- Web Dashboard: http://logger.johnsons.lcl:8081
- API Endpoint: http://logger.johnsons.lcl:8080
- Metrics: http://logger.johnsons.lcl:9090/metrics

### Monitoring Logs
```bash
# Real-time log monitoring
tail -f /var/log/centralized/*/system.log

# Service status
systemctl status logging-server logging-dashboard

# Application logs
journalctl -u logging-server -f
```

## API Endpoints

### Log Management
- `GET /api/logs` - Retrieve logs with filtering
- `GET /api/logs/search` - Search logs by pattern
- `GET /api/logs/stats` - Log statistics and metrics

### System Health
- `GET /health` - Service health check
- `GET /metrics` - Prometheus metrics
- `GET /api/status` - Detailed system status

### Real-time Streaming
- `WebSocket /ws/logs` - Real-time log streaming
- `WebSocket /ws/metrics` - Real-time metrics updates

## Development

### Running in Development Mode
```bash
export FLASK_ENV=development
export DEBUG_ENABLED=true
python server/log-server.py
```

### Testing
```bash
python scripts/test-logging.py
```

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Monitoring & Alerting

### Prometheus Metrics
- `log_ingestion_rate` - Logs received per second
- `log_processing_latency` - Processing time metrics
- `error_rate_by_application` - Error rates by source
- `disk_usage_logs` - Log storage utilization

### Health Checks
- Service availability monitoring
- Disk space alerts
- Memory usage tracking
- Log ingestion rate monitoring

## Troubleshooting

### Common Issues
1. **Logs not appearing**: Check rsyslog configuration and firewall
2. **High memory usage**: Adjust batch size and worker count
3. **Dashboard not loading**: Verify nginx and Flask services
4. **Missing metrics**: Check Prometheus client configuration

### Log Files
- Application logs: `/var/log/centralized/sslog/system.log`
- Service logs: `journalctl -u logging-server`
- Error logs: `/var/log/centralized/alerts/`

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
- GitHub Issues: https://github.com/cleptogk/logger/issues
- Related Project: https://github.com/cleptogk/sports-scheduler/issues/40
