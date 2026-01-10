#!/bin/bash
# Complete Production Build for macOS
# This creates:
# 1. Standalone .app bundle
# 2. Professional .dmg installer with drag-to-Applications

echo "============================================"
echo "Argo Log Viewer - Production Builder (macOS)"
echo "============================================"
echo

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "ERROR: Virtual environment not found!"
    echo "Please run setup first:"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
echo "[1/6] Activating virtual environment..."
source venv/bin/activate

# Install PyInstaller and dmgbuild if not already installed
echo
echo "[2/6] Installing build tools..."
pip install pyinstaller --quiet
pip install dmgbuild --quiet 2>/dev/null || pip install create-dmg --quiet

# Clean previous build
echo
echo "[3/6] Cleaning previous build..."
rm -rf dist build installers

# Create necessary directories
mkdir -p installers/macos

# Build the standalone .app bundle
echo
echo "[4/6] Building standalone .app bundle..."
echo "This may take a few minutes..."
echo

pyinstaller --name="ArgoLogViewer" \
    --windowed \
    --onefile \
    --add-data="app:app" \
    --hidden-import=PySide6 \
    --hidden-import=paramiko \
    --hidden-import=cryptography \
    --clean \
    --osx-bundle-identifier=com.harshmeetsingh.argologviewer \
    app/main.py

# Check if build was successful
if [ ! -d "dist/ArgoLogViewer.app" ] && [ ! -f "dist/ArgoLogViewer" ]; then
    echo
    echo "========================================"
    echo "BUILD FAILED!"
    echo "========================================"
    echo
    echo "Application bundle creation failed. Check errors above."
    exit 1
fi

echo
echo "[5/6] Standalone application created successfully!"
if [ -d "dist/ArgoLogViewer.app" ]; then
    echo "Location: dist/ArgoLogViewer.app"
    echo "Size: $(du -sh dist/ArgoLogViewer.app | cut -f1)"
else
    echo "Location: dist/ArgoLogViewer"
    echo "Size: $(du -sh dist/ArgoLogViewer | cut -f1)"
fi
echo

# Code signing (if certificate available)
echo "[6/6] Code signing and creating DMG installer..."
echo

if command -v codesign &> /dev/null; then
    echo "Attempting to code sign..."
    codesign --force --deep --sign - dist/ArgoLogViewer.app 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "✓ Code signed successfully"
    else
        echo "⚠ Code signing skipped (no certificate)"
    fi
else
    echo "⚠ codesign not available, skipping"
fi

# Create DMG installer
if [ -d "dist/ArgoLogViewer.app" ]; then
    echo
    echo "Creating professional DMG installer..."
    
    # Method 1: Using create-dmg (if available)
    if command -v create-dmg &> /dev/null; then
        create-dmg \
            --volname "Argo Log Viewer" \
            --window-pos 200 120 \
            --window-size 800 400 \
            --icon-size 100 \
            --icon "ArgoLogViewer.app" 200 190 \
            --hide-extension "ArgoLogViewer.app" \
            --app-drop-link 600 185 \
            "installers/macos/ArgoLogViewer-1.0.0-macOS.dmg" \
            "dist/ArgoLogViewer.app" 2>/dev/null
        
        if [ -f "installers/macos/ArgoLogViewer-1.0.0-macOS.dmg" ]; then
            echo "✓ DMG created successfully"
        fi
    else
        # Method 2: Simple DMG creation with hdiutil
        echo "Using hdiutil to create DMG..."
        
        # Create temporary folder
        mkdir -p dist/dmg
        cp -r dist/ArgoLogViewer.app dist/dmg/
        ln -s /Applications dist/dmg/Applications
        
        # Create DMG
        hdiutil create -volname "Argo Log Viewer" \
            -srcfolder dist/dmg \
            -ov -format UDZO \
            installers/macos/ArgoLogViewer-1.0.0-macOS.dmg
        
        # Cleanup
        rm -rf dist/dmg
        
        if [ -f "installers/macos/ArgoLogViewer-1.0.0-macOS.dmg" ]; then
            echo "✓ DMG created successfully"
        fi
    fi
fi

echo
echo "========================================"
echo "PRODUCTION BUILD COMPLETE!"
echo "========================================"
echo

if [ -d "dist/ArgoLogViewer.app" ]; then
    echo "Standalone Application:"
    echo "  dist/ArgoLogViewer.app"
    echo "  Size: $(du -sh dist/ArgoLogViewer.app | cut -f1)"
    echo
fi

if [ -f "installers/macos/ArgoLogViewer-1.0.0-macOS.dmg" ]; then
    echo "Professional DMG Installer:"
    echo "  installers/macos/ArgoLogViewer-1.0.0-macOS.dmg"
    echo "  Size: $(du -sh installers/macos/ArgoLogViewer-1.0.0-macOS.dmg | cut -f1)"
    echo
    echo "The DMG includes:"
    echo "  - Drag-to-Applications interface"
    echo "  - Professional presentation"
    echo "  - Code signed (if certificate available)"
    echo
else
    echo "⚠ DMG creation skipped or failed"
    echo
    echo "To create DMG manually:"
    echo "  brew install create-dmg"
    echo "  Then run this script again"
    echo
fi

echo "========================================"
echo "DISTRIBUTION READY!"
echo "========================================"
echo
echo "You can now distribute:"
if [ -d "dist/ArgoLogViewer.app" ]; then
    echo "  1. dist/ArgoLogViewer.app - Standalone (zip it first)"
fi
if [ -f "installers/macos/ArgoLogViewer-1.0.0-macOS.dmg" ]; then
    echo "  2. installers/macos/*.dmg - Professional installer"
fi
echo

deactivate
