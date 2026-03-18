"""
Indaba Launcher
---------------
Run this file to start Indaba:

    python launch.py

The browser will open automatically. If it doesn't, go to:
    http://localhost:5050
"""

import sys
import os
import time
import threading
import webbrowser

# Ensure we're running from the right directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

PORT = 5050
URL  = f'http://localhost:{PORT}'

def open_browser():
    """Wait a moment for Flask to start, then open the browser."""
    time.sleep(1.2)
    webbrowser.open(URL)

if __name__ == '__main__':
    # Load plugins before starting
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    # Import and boot app
    from app import app, load_plugins
    load_plugins()

    print()
    print('  ┌──────────────────────────────────────┐')
    print('  │                                      │')
    print('  │   INDABA — Morning Briefing System   │')
    print('  │                                      │')
    print(f'  │   Opening at: {URL:<23}│')
    print('  │   Press Ctrl+C to stop               │')
    print('  │                                      │')
    print('  └──────────────────────────────────────┘')
    print()

    # Open browser in background thread
    t = threading.Thread(target=open_browser, daemon=True)
    t.start()

    # Start Flask (suppresses default startup messages)
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.WARNING)

    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
