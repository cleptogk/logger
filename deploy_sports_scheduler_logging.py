#!/usr/bin/env python3
"""
Deploy enhanced logging configuration to sports-scheduler application.
"""

import os
import sys
import shutil
from pathlib import Path

def deploy_logging_to_sports_scheduler():
    """Deploy the enhanced logging configuration to sports-scheduler."""
    
    # Source and destination paths
    source_file = Path(__file__).parent / 'sports_scheduler_logging.py'
    sports_scheduler_dir = Path('/opt/apps/sports-scheduler')
    dest_file = sports_scheduler_dir / 'sports_scheduler_logging.py'
    
    print("🚀 Deploying enhanced logging to sports-scheduler...")
    
    # Check if sports-scheduler directory exists
    if not sports_scheduler_dir.exists():
        print(f"❌ Sports-scheduler directory not found: {sports_scheduler_dir}")
        return False
    
    try:
        # Copy the logging configuration file
        shutil.copy2(source_file, dest_file)
        print(f"✅ Copied logging configuration to {dest_file}")
        
        # Create log directories
        log_dirs = [
            '/var/log/centralized/ssdev/sports-scheduler',
            '/var/log/centralized/ssdev/auto-scraper'
        ]
        
        for log_dir in log_dirs:
            Path(log_dir).mkdir(parents=True, exist_ok=True)
            print(f"✅ Created log directory: {log_dir}")
        
        # Set proper permissions
        os.system(f"chown -R logserver:logserver /var/log/centralized/ssdev/")
        print("✅ Set proper permissions on log directories")
        
        print("\n📋 Next steps:")
        print("1. Update sports-scheduler app.py to import the new logging")
        print("2. Update IPTV orchestrator to use enhanced logging")
        print("3. Restart sports-scheduler service")
        print("4. Test the logging API endpoints")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to deploy logging configuration: {e}")
        return False

if __name__ == '__main__':
    success = deploy_logging_to_sports_scheduler()
    sys.exit(0 if success else 1)
