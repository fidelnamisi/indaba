#!/bin/zsh
# Indaba — Morning Briefing System Toggle
# Double-click this file to Start/Stop Indaba.

cd "$(dirname "$0")"

# ALWAYS source your shell profile so your FAL_KEY / DEEPSEEK_API_KEY are loaded
[ -f "$HOME/.zshrc" ] && source "$HOME/.zshrc"

# Check if Indaba is already running on port 5050 or 5051
PID=$(lsof -ti:5050,5051 | head -n 1)

echo ""
echo "  ┌──────────────────────────────────────┐"
echo "  │   INDABA — Morning Briefing System   │"
echo "  └──────────────────────────────────────┘"
echo ""

if [ -n "$PID" ]; then
    PORT=$(lsof -a -p "$PID" -iTCP -sTCP:LISTEN -P -n | awk 'NR>1 {print $9}' | awk -F':' '{print $NF}' | head -n 1)
    [ -z "$PORT" ] && PORT="unknown"
    echo "  [●] Indaba is currently RUNNING on port $PORT (PID $PID)"
    echo "  [➔] Action: STOPPING server..."
    
    # Kill the process
    kill -9 $PID
    sleep 1.5
    
    # Confirm it's gone
    NEW_PID=$(lsof -ti:5050,5051 | head -n 1)
    if [ -z "$NEW_PID" ]; then
        echo "  [✓] Indaba Stopped Successfully."
    else
        echo "  [✗] Failed to stop process $PID. You may need to manual kill."
    fi
else
    echo "  [○] Indaba is currently STOPPED"
    echo "  [➔] Action: STARTING server..."
    
    # Start the server (using nohup so it stays alive if you close this window)
    nohup python3 app.py > app_run.log 2>&1 &
    
    # Wait for the server to bind (up to 10 seconds)
    for i in {1..10}; do
        NEW_PID=$(lsof -ti:5050,5051 | head -n 1)
        if [ -n "$NEW_PID" ]; then
            break
        fi
        sleep 1
    done
    
    if [ -n "$NEW_PID" ]; then
        PORT=$(lsof -a -p "$NEW_PID" -iTCP -sTCP:LISTEN -P -n | awk 'NR>1 {print $9}' | awk -F':' '{print $NF}' | head -n 1)
        [ -z "$PORT" ] && PORT="unknown"
        echo "  [✓] Indaba Started running on port $PORT"
        echo "  [➔] The browser sequence has triggered automatically."
    else
        echo "  [✗] Start FAILED. Check app_run.log for errors."
    fi
fi

# Keep the window open for a moment so you can read the status
echo ""
echo "  Closing window in 3 seconds..."
sleep 3

exit
