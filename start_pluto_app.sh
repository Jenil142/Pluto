#!/bin/bash
cd /home/jenil/Pluto

# Start Uvicorn if not already running on port 8000
if ! pgrep -f "uvicorn api:app" > /dev/null; then
    .venv/bin/python3 api.py &
    sleep 2 # wait for startup
fi

# Launch Chrome as a native app
google-chrome --app=http://localhost:8000
