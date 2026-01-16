#!/bin/bash
# Build script for macOS (Intel)

set -e  # Exit on error

echo "=================================="
echo "Building Argo Log Viewer for macOS"
echo "=================================="

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "Error: This script must be run on macOS"
    exit 1
fi

# Check Python version
echo "Checking Python version..."
python3 --version

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

# Create icon if it doesn't exist
if [ ! -f "app/icon.icns" ]; then
    echo "Creating macOS icon..."
    bash create_macos_icon.sh
fi

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build dist

# Build with PyInstaller
echo "Building application..."
pyinstaller ArgoLogViewer.spec

# Check if build was successful
if [ -f "dist/ArgoLogViewer.app/Contents/MacOS/ArgoLogViewer" ]; then
    echo "=================================="
    echo "✓ Build successful!"
    echo "=================================="
    echo ""
    echo "Application created at:"
    echo "  dist/ArgoLogViewer.app"
    echo ""
    echo "To test:"
    echo "  open dist/ArgoLogViewer.app"
    echo ""
    echo "To create DMG for distribution:"
    echo "  bash create_dmg.sh"
else
    echo "=================================="
    echo "✗ Build failed!"
    echo "=================================="
    exit 1
fi
