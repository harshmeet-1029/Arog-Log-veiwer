#!/bin/bash
# Professional Build Script for macOS Apple Silicon
# Argo Log Viewer - Copyright (c) 2024-2026 Harshmeet Singh
# For Apple Silicon Macs (ARM64 / M1, M2, M3)

set -e

echo "============================================================"
echo "  Argo Log Viewer - Professional macOS Builder (ARM64)"
echo "============================================================"
echo ""
echo "Platform: macOS Apple Silicon (ARM64)"
echo "Build Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Verify we're on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "ERROR: This script must be run on macOS!"
    exit 1
fi

# Verify architecture
ARCH=$(uname -m)
if [ "$ARCH" != "arm64" ]; then
    echo "WARNING: Detected architecture: $ARCH"
    echo "This script is optimized for Apple Silicon (arm64)"
    echo "For Intel Macs, use: build_macos_intel.sh"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check Python version
echo "[1/8] Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found!"
    echo "Install: brew install python3"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "✓ Python $PYTHON_VERSION"

# Setup virtual environment
echo ""
echo "[2/8] Setting up virtual environment..."
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
echo "[3/8] Installing dependencies..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
pip install pyinstaller --quiet
echo "✓ All dependencies installed"

# Create macOS icon
echo ""
echo "[4/8] Creating macOS icon..."
if [ ! -f "app/ICON.png" ]; then
    echo "ERROR: app/ICON.png not found!"
    exit 1
fi

# Create iconset
mkdir -p app/icon.iconset

echo "Generating icon sizes..."
sips -z 16 16     app/ICON.png --out app/icon.iconset/icon_16x16.png 2>/dev/null
sips -z 32 32     app/ICON.png --out app/icon.iconset/icon_16x16@2x.png 2>/dev/null
sips -z 32 32     app/ICON.png --out app/icon.iconset/icon_32x32.png 2>/dev/null
sips -z 64 64     app/ICON.png --out app/icon.iconset/icon_32x32@2x.png 2>/dev/null
sips -z 128 128   app/ICON.png --out app/icon.iconset/icon_128x128.png 2>/dev/null
sips -z 256 256   app/ICON.png --out app/icon.iconset/icon_128x128@2x.png 2>/dev/null
sips -z 256 256   app/ICON.png --out app/icon.iconset/icon_256x256.png 2>/dev/null
sips -z 512 512   app/ICON.png --out app/icon.iconset/icon_256x256@2x.png 2>/dev/null
sips -z 512 512   app/ICON.png --out app/icon.iconset/icon_512x512.png 2>/dev/null
sips -z 1024 1024 app/ICON.png --out app/icon.iconset/icon_512x512@2x.png 2>/dev/null

# Convert to icns
iconutil -c icns app/icon.iconset -o app/icon.icns 2>/dev/null
rm -rf app/icon.iconset
echo "✓ Icon created: app/icon.icns"

# Clean previous builds
echo ""
echo "[5/8] Cleaning previous builds..."
rm -rf build dist *.dmg
echo "✓ Clean complete"

# Build application
echo ""
echo "[6/8] Building macOS application..."
echo "This may take 3-5 minutes..."
echo ""

# Build specifically for ARM64
pyinstaller ArgoLogViewer.spec --clean --target-arch arm64

echo ""
echo "[6.5/8] Fixing code signatures..."

# Remove all code signatures to prevent Team ID mismatches
sudo codesign --remove-signature dist/ArgoLogViewer.app/Contents/MacOS/ArgoLogViewer 2>/dev/null || true

# Re-sign with consistent ad-hoc signature (deep sign everything)
sudo codesign -s - --deep --force dist/ArgoLogViewer.app

echo "✓ Code signatures fixed"
echo ""
echo "⚠️  NOTE: This build is NOT code-signed or notarized"
echo "   Users will need to bypass macOS Gatekeeper"
echo "   See: MACOS_INSTALLATION.md for instructions"

# Verify build
echo ""
echo "[7/8] Verifying build..."
if [ ! -d "dist/ArgoLogViewer.app" ]; then
    echo "ERROR: Build failed! Application bundle not created."
    exit 1
fi

APP_SIZE=$(du -sh dist/ArgoLogViewer.app | cut -f1)
echo "✓ Application bundle created"
echo "  Size: $APP_SIZE"

# Create DMG
echo ""
echo "[8/8] Creating DMG installer..."

# Create temporary DMG folder
mkdir -p dist/dmg
cp -r dist/ArgoLogViewer.app dist/dmg/
ln -s /Applications dist/dmg/Applications

# Create DMG
hdiutil create -volname "Argo Log Viewer" \
    -srcfolder dist/dmg \
    -ov -format UDZO \
    ArgoLogViewer-macOS-ARM64.dmg

rm -rf dist/dmg

if [ -f "ArgoLogViewer-macOS-ARM64.dmg" ]; then
    DMG_SIZE=$(du -sh ArgoLogViewer-macOS-ARM64.dmg | cut -f1)
    echo "✓ DMG created: ArgoLogViewer-macOS-ARM64.dmg"
    echo "  Size: $DMG_SIZE"
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
echo "  1. dist/ArgoLogViewer.app (Application Bundle)"
echo "     Size: $APP_SIZE"
echo "     Test: open dist/ArgoLogViewer.app"
echo ""
if [ -f "ArgoLogViewer-macOS-ARM64.dmg" ]; then
    echo "  2. ArgoLogViewer-macOS-ARM64.dmg (Installer)"
    echo "     Size: $DMG_SIZE"
    echo "     For distribution to Apple Silicon Mac users"
    echo ""
    echo "⚠️  IMPORTANT: This DMG is NOT code-signed"
    echo "   Users must bypass Gatekeeper to open"
    echo "   Include MACOS_INSTALLATION.md with distribution"
fi
echo ""
echo "Architecture: ARM64 (Apple Silicon)"
echo "Compatible with: M1, M2, M3 Macs"
echo ""
echo "Build Complete: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
