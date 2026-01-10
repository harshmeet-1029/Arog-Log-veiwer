#!/bin/bash

echo "======================================="
echo " Argo Log Viewer - Production Grade"
echo "======================================="
echo

# Check if virtual environment exists
if [ ! -f "venv/bin/python" ]; then
    echo "ERROR: Virtual environment not found!"
    echo
    echo "Please run setup first:"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    echo
    exit 1
fi

# Activate virtual environment and run application
echo "Starting application..."
echo

source venv/bin/activate
python -m app.main

# Deactivate on exit
deactivate

echo
echo "Application closed."
