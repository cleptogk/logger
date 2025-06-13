#!/usr/bin/env python3
"""
Trigger initial scan of existing log files for Redis log processor.
This script touches all log files to trigger the file watcher.
"""

import os
import time
from pathlib import Path

def trigger_initial_scan():
    """Touch all log files to trigger file watcher processing."""
    log_dir = Path('/var/log/centralized')
    
    if not log_dir.exists():
        print(f"❌ Log directory {log_dir} does not exist")
        return
    
    print(f"🔍 Scanning {log_dir} for log files...")
    
    log_files = list(log_dir.rglob('*.log'))
    print(f"📁 Found {len(log_files)} log files")
    
    for log_file in log_files:
        try:
            # Touch the file to trigger file watcher
            log_file.touch()
            print(f"✅ Triggered: {log_file}")
            time.sleep(0.1)  # Small delay to avoid overwhelming the processor
        except Exception as e:
            print(f"❌ Failed to trigger {log_file}: {e}")
    
    print(f"🎉 Triggered processing for {len(log_files)} log files")
    print("⏳ Wait 30-60 seconds for background processing to complete")

if __name__ == '__main__':
    trigger_initial_scan()
