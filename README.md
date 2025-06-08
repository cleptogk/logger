# Enhanced Logging API Server

A production-ready centralized logging solution with advanced search, analytics, and real-time monitoring capabilities for multi-application environments.

## Features

- **Enhanced Logging Integration**: Full support for sports-scheduler and auto-scraper structured logging
- **Advanced Search & Analytics**: Full-text search, regex patterns, metadata extraction, and distribution analysis
- **Real-time Processing**: Timezone-aware log parsing with step-by-step workflow tracking
- **Production-Ready API**: RESTful endpoints with pagination, filtering, and advanced query capabilities
- **Multi-Application Support**: Automatic application and component detection across ssdev, ssdvr, ssmcp, ssrun
- **Workflow Correlation**: Refresh ID tracking and step completion analysis for complex workflows

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

## Enhanced API Endpoints

### Core Endpoints
- `GET /health` - Service health check and status
- `GET /logger/files` - List all available log files and hosts

### Host-Based Queries
- `GET /logger/host=<host>` - Get logs for specific host with advanced filtering
- `GET /logger/search/<host>` - Advanced search with full-text, regex, and metadata filtering
- `GET /logger/troubleshoot/<host>/<application>` - Application-specific troubleshooting

### Application-Specific
- `GET /logger/iptv-orchestrator/<host>` - IPTV workflow step analysis
- `GET /logger/components/<host>/<application>` - Component discovery and statistics

### Advanced Filtering Parameters
- `?search=<query>` - Full-text search across log content
- `?pattern=<regex>` - Regex pattern matching
- `?level=ERROR,WARN,INFO` - Log level filtering
- `?refresh_id=Refresh-14` - Workflow correlation by refresh ID
- `?time=yesterday around 7am` - Natural language time filtering
- `?step=6` - Filter by specific workflow step
- `?limit=100&offset=200` - Pagination support

## Development

### Running the Enhanced Logging API
```bash
# Production mode
python log_api.py

# Development mode with debug
export FLASK_ENV=development
python log_api.py
```

### Testing API Endpoints
```bash
# Health check
curl http://localhost:8080/health

# Search logs with enhanced filtering
curl "http://localhost:8080/logger/search/ssdev?search=Refresh&time=today&limit=5"

# Get IPTV orchestrator workflow logs
curl "http://localhost:8080/logger/iptv-orchestrator/ssdev?step=6&time=yesterday around 7am"
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
