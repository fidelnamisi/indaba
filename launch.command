#!/bin/bash
# Indaba — Morning Briefing System
# Double-click this file to launch.
# First time only: chmod +x launch.command (in Terminal, once)

cd "$(dirname "$0")"

# Install Flask if not already present (instant if already installed)
pip3 install flask -q

echo ""
echo "  ┌──────────────────────────────────────┐"
echo "  │   INDABA — Morning Briefing System   │"
echo "  │   Starting at http://localhost:5050  │"
echo "  └──────────────────────────────────────┘"
echo ""

# Start the server in the background
python3 app.py &
SERVER_PID=$!

# Give Flask a moment to start
sleep 1.5

# Open in default browser
open http://localhost:5050

# Keep terminal alive — Ctrl+C or close the window to stop Indaba
wait $SERVER_PID
