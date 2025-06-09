#!/usr/bin/env python3
"""
Test script to run the dashboard for debugging
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_dashboard():
    """Test the dashboard functionality"""
    print("🧪 Testing Dashboard Components")
    print("=" * 50)
    
    try:
        # Test 1: Import dashboard app
        print("1. Testing dashboard app import...")
        from dashboard.dashboard_app import app, initialize_dashboard
        print("   ✅ Dashboard app imported successfully")
        
        # Test 2: Initialize dashboard
        print("2. Testing dashboard initialization...")
        success = initialize_dashboard()
        if success:
            print("   ✅ Dashboard initialized successfully")
        else:
            print("   ⚠️ Dashboard initialization had issues")
        
        # Test 3: Test basic routes
        print("3. Testing basic routes...")
        with app.test_client() as client:
            # Test dashboard route
            response = client.get('/')
            print(f"   Dashboard route: {response.status_code}")
            
            # Test IPTV orchestrator route
            response = client.get('/iptv-orchestrator')
            print(f"   IPTV orchestrator route: {response.status_code}")
            
            # Test health route
            response = client.get('/api/dashboard/health')
            print(f"   Health route: {response.status_code}")
        
        print("\n🎉 Dashboard test completed!")
        return True
        
    except Exception as e:
        print(f"❌ Dashboard test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_dashboard():
    """Run the dashboard server"""
    print("🚀 Starting Dashboard Server")
    print("=" * 50)
    
    try:
        from dashboard.dashboard_app import app, initialize_dashboard, main
        
        # Initialize dashboard
        if not initialize_dashboard():
            print("❌ Failed to initialize dashboard")
            return
        
        # Run the app
        host = os.environ.get('DASHBOARD_HOST', '0.0.0.0')
        port = int(os.environ.get('DASHBOARD_PORT', 8081))
        
        print(f"🌐 Starting dashboard on {host}:{port}")
        print(f"📱 Access dashboard at: http://localhost:{port}")
        print("🔗 IPTV Orchestrator: http://localhost:{port}/iptv-orchestrator")
        print("=" * 50)
        
        app.run(host=host, port=port, debug=True)
        
    except Exception as e:
        print(f"❌ Failed to start dashboard: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Test and run the logging dashboard')
    parser.add_argument('--test', action='store_true', help='Run tests only')
    parser.add_argument('--run', action='store_true', help='Run the dashboard server')
    
    args = parser.parse_args()
    
    if args.test:
        test_dashboard()
    elif args.run:
        run_dashboard()
    else:
        # Default: run tests then start server
        if test_dashboard():
            print("\n" + "=" * 50)
            run_dashboard()
