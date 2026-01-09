#!/bin/bash
echo "Stopping any running backend processes..."
pkill -f "python main.py" 2>/dev/null || pkill -f "uvicorn main:app" 2>/dev/null || true
echo "Waiting 2 seconds..."
sleep 2
echo "Starting backend..."
python main.py
