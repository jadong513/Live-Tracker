#!/usr/bin/env python3
"""
Quick launcher for the Live Tracker Web Dashboard.

Run this file to start the web interface.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from live_tracker.web.app import run_server

if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("📈 LIVE TRACKER - Professional Trading Dashboard")
    print("=" * 50)

    port = 5000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass

    run_server(host="127.0.0.1", port=port, debug=True)
