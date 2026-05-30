#!/bin/bash

# Start the streaming telemetry server locally
echo "Starting Streaming Telemetry Server locally..."
cd streaming-telemetry-server

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install requirements
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Run the modern ingester server
echo "Launching ingester.py on port 8080..."
export PORT=8080
export MOCK_MODE=true
python3 ingester.py
