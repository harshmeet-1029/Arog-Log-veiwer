#!/bin/bash
# Professional Build Script for Linux
# Argo Log Viewer - Copyright (c) 2024-2026 Harshmeet Singh
# For Linux x86_64 (Debian, Ubuntu, Fedora, RHEL, Arch, etc.)

set -e

echo "============================================================"
echo "  Argo Log Viewer - Professional Linux Builder"
echo "============================================================"
echo ""
echo "Platform: Linux (x86_64)"
echo "Build Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Verify we're on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "ERROR: This script must be run on Linux!"
    exit 1
fi

# Check architecture
ARCH=$(uname -m)
echo "Architecture: $ARCH"
if [ "$ARCH" != "x86_64" ]; then
    echo "WARNING: This script is optimized for x86_64"
    echo "Build may not work on other architectures"
fi

# Check Python version
echo ""
echo "[1/7] Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found!"
    echo ""
    echo "Install Python 3:"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
    echo "  Fedora/RHEL:   sudo dnf install python3 python3-pip"
    echo "  Arch:          sudo pacman -S python python-pip"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "✓ Python $PYTHON_VERSION"

# Setup virtual environment
echo ""
echo "[2/7] Setting up virtual environment..."
if [ ! -d "venv" ]; then
    echo "Creating new virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Using existing virtual environment"
fi

# Activate
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo ""
echo "[3/7] Installing dependencies..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
pip install pyinstaller --quiet
echo "✓ All dependencies installed"

# Clean previous builds
echo ""
echo "[4/7] Cleaning previous builds..."
rm -rf build dist *.tar.gz
echo "✓ Clean complete"

# Build application
echo ""
echo "[5/7] Building Linux application..."
echo "This may take 3-5 minutes..."
echo ""

pyinstaller ArgoLogViewer.spec --clean

# Verify build
echo ""
echo "[6/7] Verifying build..."
if [ ! -f "dist/ArgoLogViewer" ] && [ ! -d "dist/ArgoLogViewer.app" ]; then
    echo "ERROR: Build failed! Binary not created."
    exit 1
fi

# Handle both possible outputs
if [ -f "dist/ArgoLogViewer" ]; then
    chmod +x dist/ArgoLogViewer
    APP_SIZE=$(du -sh dist/ArgoLogViewer | cut -f1)
    APP_TYPE="Binary"
    echo "✓ Executable created: dist/ArgoLogViewer"
    echo "  Size: $APP_SIZE"
elif [ -d "dist/ArgoLogViewer.app" ]; then
    APP_SIZE=$(du -sh dist/ArgoLogViewer.app | cut -f1)
    APP_TYPE="Application Bundle"
    echo "✓ Application created: dist/ArgoLogViewer.app"
    echo "  Size: $APP_SIZE"
fi

# Create portable archive
echo ""
echo "[7/7] Creating portable archive..."

if [ -f "dist/ArgoLogViewer" ]; then
    tar -czf ArgoLogViewer-Linux-x86_64.tar.gz -C dist ArgoLogViewer
    ARCHIVE_SIZE=$(du -sh ArgoLogViewer-Linux-x86_64.tar.gz | cut -f1)
    echo "✓ Archive created: ArgoLogViewer-Linux-x86_64.tar.gz"
    echo "  Size: $ARCHIVE_SIZE"
fi

# Deactivate venv
deactivate

# Final summary
echo ""
echo "============================================================"
echo "  BUILD SUCCESSFUL! ✓"
echo "============================================================"
echo ""
echo "Output Files:"
if [ -f "dist/ArgoLogViewer" ]; then
    echo "  1. dist/ArgoLogViewer (Executable)"
    echo "     Size: $APP_SIZE"
    echo "     Test: ./dist/ArgoLogViewer"
    echo ""
    echo "  2. ArgoLogViewer-Linux-x86_64.tar.gz (Portable Archive)"
    echo "     Size: $ARCHIVE_SIZE"
    echo "     Extract: tar -xzf ArgoLogViewer-Linux-x86_64.tar.gz"
elif [ -d "dist/ArgoLogViewer.app" ]; then
    echo "  1. dist/ArgoLogViewer.app (Application Bundle)"
    echo "     Size: $APP_SIZE"
fi
echo ""
echo "Architecture: x86_64"
echo "Compatible with: Most Linux distributions (64-bit)"
echo ""
echo "Installation:"
echo "  1. Extract the archive: tar -xzf ArgoLogViewer-Linux-x86_64.tar.gz"
echo "  2. Run: ./ArgoLogViewer"
echo "  or move to: sudo mv ArgoLogViewer /usr/local/bin/"
echo ""
echo "Build Complete: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
