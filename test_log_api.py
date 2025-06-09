#!/usr/bin/env python3
"""
Test script to run and test the log API
"""

import os
import sys
import requests
import time
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_api_endpoints():
    """Test the log API endpoints"""
    print("🧪 Testing Log API Endpoints")
    print("=" * 50)
    
    base_url = "http://localhost:8080"
    
    endpoints_to_test = [
        "/health",
        "/logger/files",
        "/api/stats",
        "/logger/host=ssdev?application=sports-scheduler&limit=10",
        "/logger/iptv-orchestrator/ssdev?time=last 1 hour",
        "/logger/search/ssdev?search=IPTV&limit=5",
    ]
    
    for endpoint in endpoints_to_test:
        try:
            print(f"Testing: {endpoint}")
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict):
                    print(f"  Keys: {list(data.keys())}")
                elif isinstance(data, list):
                    print(f"  Items: {len(data)}")
                print("  ✅ Success")
            else:
                print(f"  ❌ Failed: {response.text[:100]}")
                
        except requests.exceptions.ConnectionError:
            print(f"  ❌ Connection failed - API server not running?")
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        print()

def run_log_api():
    """Run the log API server"""
    print("🚀 Starting Log API Server")
    print("=" * 50)
    
    try:
        from log_api import app
        
        host = os.environ.get('BIND_ADDRESS', '0.0.0.0')
        port = int(os.environ.get('LOGGING_SERVER_PORT', 8080))
        
        print(f"🌐 Starting log API on {host}:{port}")
        print(f"📋 Available endpoints:")
        print("  - /health")
        print("  - /logger/host=<host>?application=<app>&component=<comp>")
        print("  - /logger/search/<host>?search=<query>&pattern=<regex>")
        print("  - /logger/iptv-orchestrator/<host>?step=<step>&time=<time>")
        print("  - /logger/files")
        print("  - /api/stats")
        print("=" * 50)
        
        app.run(host=host, port=port, debug=True)
        
    except Exception as e:
        print(f"❌ Failed to start log API: {e}")
        import traceback
        traceback.print_exc()

def check_log_files():
    """Check if log files exist"""
    print("📁 Checking Log Files")
    print("=" * 50)
    
    log_dir = Path('/var/log/centralized')
    
    if not log_dir.exists():
        print(f"❌ Log directory does not exist: {log_dir}")
        print("   Creating test directory structure...")
        
        # Create test structure
        test_dir = Path('./test_logs/ssdev/sports-scheduler')
        test_dir.mkdir(parents=True, exist_ok=True)
        
        # Create test log file
        test_log = test_dir / 'iptv-orchestrator.log'
        with open(test_log, 'w') as f:
            f.write("2025-01-15 14:30:00.123-07:00 DEBUG [sports_scheduler.iptv_orchestrator:refresh:45] [Refresh-15] Step 1/8: Starting IPTV refresh workflow\n")
            f.write("2025-01-15 14:30:05.456-07:00 INFO [sports_scheduler.iptv_orchestrator:refresh:67] [Refresh-15] Step 2/8: Purging Xtream provider data completed successfully in 4.23 seconds\n")
            f.write("2025-01-15 14:30:10.789-07:00 DEBUG [sports_scheduler.iptv_orchestrator:refresh:89] [Refresh-15] Step 3/8: Refreshing Xtream channels\n")
        
        print(f"   ✅ Created test log file: {test_log}")
        return str(test_dir.parent.parent)
    else:
        print(f"✅ Log directory exists: {log_dir}")
        
        # List available hosts
        hosts = [d.name for d in log_dir.iterdir() if d.is_dir()]
        print(f"   Available hosts: {hosts}")
        
        for host in hosts:
            host_dir = log_dir / host
            log_files = list(host_dir.rglob('*.log'))
            print(f"   {host}: {len(log_files)} log files")
        
        return str(log_dir)

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Test and run the log API')
    parser.add_argument('--test', action='store_true', help='Test API endpoints')
    parser.add_argument('--run', action='store_true', help='Run the API server')
    parser.add_argument('--check', action='store_true', help='Check log files')
    
    args = parser.parse_args()
    
    if args.test:
        test_api_endpoints()
    elif args.run:
        run_log_api()
    elif args.check:
        check_log_files()
    else:
        # Default: check files, then run server
        check_log_files()
        print("\n" + "=" * 50)
        run_log_api()
