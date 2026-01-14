#!/bin/bash

################################################################################
# macOS Universal2 Build Script
# Builds a universal2 binary (Intel + Apple Silicon) of ArgoLogViewer
# Compatible with macOS 11.0 Big Sur and later
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="ArgoLogViewer"
PYTHON_VERSION="3.11"
PYTHON_PATH="/Library/Frameworks/Python.framework/Versions/${PYTHON_VERSION}/bin/python${PYTHON_VERSION}"
MIN_MACOS_VERSION="11.0"

################################################################################
# Helper Functions
################################################################################

print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

################################################################################
# Check Prerequisites
################################################################################

check_prerequisites() {
    print_header "CHECKING PREREQUISITES"
    
    # Check if running on macOS
    if [[ "$OSTYPE" != "darwin"* ]]; then
        print_error "This script must be run on macOS"
        exit 1
    fi
    print_success "Running on macOS"
    
    # Check for Python.org Python
    if [ ! -f "$PYTHON_PATH" ]; then
        print_error "Python.org Python ${PYTHON_VERSION} not found at $PYTHON_PATH"
        echo ""
        print_info "Please install Python from: https://www.python.org/downloads/"
        print_info "Download the macOS 64-bit universal2 installer"
        echo ""
        print_info "Alternatively, install with Homebrew:"
        echo "  brew install python@${PYTHON_VERSION}"
        exit 1
    fi
    print_success "Python ${PYTHON_VERSION} found"
    
    # Verify Python is universal2
    PYTHON_FRAMEWORK="/Library/Frameworks/Python.framework/Versions/${PYTHON_VERSION}/Python"
    if [ -f "$PYTHON_FRAMEWORK" ]; then
        PYTHON_ARCHS=$(lipo -info "$PYTHON_FRAMEWORK" 2>/dev/null || echo "")
        if echo "$PYTHON_ARCHS" | grep -q "x86_64" && echo "$PYTHON_ARCHS" | grep -q "arm64"; then
            print_success "Python is universal2 (x86_64 + arm64)"
        else
            print_warning "Python may not be universal2"
            print_info "Architecture: $PYTHON_ARCHS"
        fi
    fi
    
    # Check for required tools
    if ! command -v hdiutil &> /dev/null; then
        print_error "hdiutil not found (required for DMG creation)"
        exit 1
    fi
    print_success "hdiutil available"
    
    if ! command -v zip &> /dev/null; then
        print_error "zip not found"
        exit 1
    fi
    print_success "zip available"
}

################################################################################
# Install Dependencies
################################################################################

install_dependencies() {
    print_header "INSTALLING DEPENDENCIES"
    
    print_info "Installing Python packages..."
    "$PYTHON_PATH" -m pip install --upgrade pip --quiet
    "$PYTHON_PATH" -m pip install -r requirements.txt --quiet
    "$PYTHON_PATH" -m pip install pyinstaller --quiet
    
    print_success "Dependencies installed"
}

################################################################################
# Build Universal2 App
################################################################################

build_app() {
    print_header "BUILDING UNIVERSAL2 APP"
    
    # Set deployment target
    export MACOSX_DEPLOYMENT_TARGET="$MIN_MACOS_VERSION"
    
    print_info "Building with PyInstaller..."
    print_info "Deployment target: macOS ${MIN_MACOS_VERSION} and later"
    print_info "Architecture: universal2 (Intel + Apple Silicon)"
    echo ""
    
    # Clean previous builds
    if [ -d "build" ]; then
        print_info "Cleaning previous build artifacts..."
        rm -rf build
    fi
    if [ -d "dist" ]; then
        rm -rf dist
    fi
    if [ -f "${APP_NAME}.spec" ]; then
        rm -f "${APP_NAME}.spec"
    fi
    
    # Build with PyInstaller
    "$PYTHON_PATH" -m PyInstaller \
        --name="${APP_NAME}" \
        --windowed \
        --onefile \
        --add-data="app:app" \
        --hidden-import=PySide6 \
        --hidden-import=paramiko \
        --hidden-import=cryptography \
        --clean \
        --osx-bundle-identifier=com.harshmeetsingh.argologviewer \
        --target-arch universal2 \
        --codesign-identity - \
        app/main.py
    
    echo ""
    print_success "Build complete"
}

################################################################################
# Verify Universal2 Binary
################################################################################

verify_binary() {
    print_header "VERIFYING UNIVERSAL2 BINARY"
    
    EXECUTABLE="dist/${APP_NAME}.app/Contents/MacOS/${APP_NAME}"
    
    if [ ! -f "$EXECUTABLE" ]; then
        print_error "Executable not found at: $EXECUTABLE"
        exit 1
    fi
    
    print_info "Checking architectures..."
    ARCHS=$(lipo -info "$EXECUTABLE")
    echo "$ARCHS"
    echo ""
    
    # Verify both architectures are present
    if echo "$ARCHS" | grep -q "x86_64" && echo "$ARCHS" | grep -q "arm64"; then
        print_success "Binary is universal2!"
        echo "  ✓ Contains x86_64 (Intel)"
        echo "  ✓ Contains arm64 (Apple Silicon)"
        echo ""
        print_success "Will run natively on both Intel and Apple Silicon Macs"
        print_success "NO Rosetta 2 required!"
    else
        print_error "Binary is not universal2!"
        print_error "Expected: x86_64 and arm64"
        print_error "Got: $ARCHS"
        exit 1
    fi
    
    # Show file info
    echo ""
    print_info "Executable info:"
    ls -lh "$EXECUTABLE"
    
    # Show app info
    echo ""
    print_info "App bundle info:"
    if [ -f "dist/${APP_NAME}.app/Contents/Info.plist" ]; then
        BUNDLE_ID=$(defaults read "$(pwd)/dist/${APP_NAME}.app/Contents/Info.plist" CFBundleIdentifier 2>/dev/null || echo "N/A")
        BUNDLE_VERSION=$(defaults read "$(pwd)/dist/${APP_NAME}.app/Contents/Info.plist" CFBundleShortVersionString 2>/dev/null || echo "N/A")
        echo "  Bundle Identifier: $BUNDLE_ID"
        echo "  Version: $BUNDLE_VERSION"
    fi
}

################################################################################
# Create DMG Installer
################################################################################

create_dmg() {
    print_header "CREATING DMG INSTALLER"
    
    DMG_NAME="${APP_NAME}-universal2.dmg"
    
    print_info "Creating DMG..."
    
    # Create temporary DMG directory
    mkdir -p dist/dmg
    cp -r "dist/${APP_NAME}.app" dist/dmg/
    ln -s /Applications dist/dmg/Applications
    
    # Remove old DMG if exists
    if [ -f "$DMG_NAME" ]; then
        rm -f "$DMG_NAME"
    fi
    
    # Create DMG
    hdiutil create -volname "$APP_NAME" \
        -srcfolder dist/dmg \
        -ov -format UDZO \
        "$DMG_NAME" > /dev/null 2>&1
    
    # Cleanup
    rm -rf dist/dmg
    
    print_success "DMG created: $DMG_NAME"
    DMG_SIZE=$(du -sh "$DMG_NAME" | cut -f1)
    print_info "Size: $DMG_SIZE"
}

################################################################################
# Create ZIP Archive
################################################################################

create_zip() {
    print_header "CREATING ZIP ARCHIVE"
    
    ZIP_NAME="${APP_NAME}-universal2.zip"
    
    print_info "Creating ZIP..."
    
    # Remove old ZIP if exists
    if [ -f "$ZIP_NAME" ]; then
        rm -f "$ZIP_NAME"
    fi
    
    # Create ZIP
    cd dist
    zip -r -q "../$ZIP_NAME" "${APP_NAME}.app"
    cd ..
    
    print_success "ZIP created: $ZIP_NAME"
    ZIP_SIZE=$(du -sh "$ZIP_NAME" | cut -f1)
    print_info "Size: $ZIP_SIZE"
}

################################################################################
# Generate Checksums
################################################################################

generate_checksums() {
    print_header "GENERATING CHECKSUMS"
    
    print_info "Calculating SHA-256 checksums..."
    
    CHECKSUM_FILE="CHECKSUMS.txt"
    
    # Remove old checksum file
    if [ -f "$CHECKSUM_FILE" ]; then
        rm -f "$CHECKSUM_FILE"
    fi
    
    # Generate checksums
    if [ -f "${APP_NAME}-universal2.dmg" ]; then
        shasum -a 256 "${APP_NAME}-universal2.dmg" >> "$CHECKSUM_FILE"
    fi
    
    if [ -f "${APP_NAME}-universal2.zip" ]; then
        shasum -a 256 "${APP_NAME}-universal2.zip" >> "$CHECKSUM_FILE"
    fi
    
    print_success "Checksums saved to: $CHECKSUM_FILE"
    echo ""
    cat "$CHECKSUM_FILE"
}

################################################################################
# Final Summary
################################################################################

show_summary() {
    print_header "BUILD SUMMARY"
    
    print_success "BUILD COMPLETE!"
    echo ""
    
    print_info "Output files:"
    if [ -f "${APP_NAME}-universal2.dmg" ]; then
        echo "  📦 ${APP_NAME}-universal2.dmg ($(du -sh ${APP_NAME}-universal2.dmg | cut -f1))"
    fi
    if [ -f "${APP_NAME}-universal2.zip" ]; then
        echo "  📦 ${APP_NAME}-universal2.zip ($(du -sh ${APP_NAME}-universal2.zip | cut -f1))"
    fi
    if [ -f "CHECKSUMS.txt" ]; then
        echo "  📄 CHECKSUMS.txt"
    fi
    echo ""
    
    print_info "App location:"
    echo "  📁 dist/${APP_NAME}.app"
    echo ""
    
    print_success "Installation instructions:"
    echo ""
    echo "  DMG Method (Recommended):"
    echo "    1. Open ${APP_NAME}-universal2.dmg"
    echo "    2. Drag ${APP_NAME}.app to Applications folder"
    echo "    3. Right-click app → Open (first time only)"
    echo ""
    echo "  ZIP Method:"
    echo "    1. Unzip ${APP_NAME}-universal2.zip"
    echo "    2. Move ${APP_NAME}.app to Applications"
    echo "    3. Right-click app → Open (first time only)"
    echo ""
    
    print_success "Compatible with:"
    echo "  ✓ macOS ${MIN_MACOS_VERSION} Big Sur and later"
    echo "  ✓ Intel Macs (x86_64) - Native"
    echo "  ✓ Apple Silicon Macs (arm64) - Native"
    echo "  ✓ NO Rosetta 2 required!"
    echo ""
    
    print_header "✅ ALL DONE!"
}

################################################################################
# Main Script
################################################################################

main() {
    clear
    
    print_header "🍎 MACOS UNIVERSAL2 BUILD SCRIPT"
    print_info "App: ${APP_NAME}"
    print_info "Target: universal2 (Intel + Apple Silicon)"
    print_info "Min macOS: ${MIN_MACOS_VERSION}"
    
    check_prerequisites
    install_dependencies
    build_app
    verify_binary
    create_dmg
    create_zip
    generate_checksums
    show_summary
}

# Run main function
main
