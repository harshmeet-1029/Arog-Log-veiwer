#!/bin/bash

################################################################################
# Intel macOS Build & Release Script
# Run this on your Intel Mac (macOS 14) to build and upload Intel binaries
################################################################################

set -e  # Exit on error

# Color codes for pretty output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🍎 Intel macOS Build & Release Script"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if version is provided
if [ -z "$1" ]; then
    echo -e "${RED}❌ ERROR: Version number required!${NC}"
    echo ""
    echo "Usage: ./build-intel-and-release.sh <version> [github-token]"
    echo "Example: ./build-intel-and-release.sh 1.0.0"
    echo "Example: ./build-intel-and-release.sh 1.0.0 ghp_yourtoken"
    echo ""
    echo "If no GitHub token provided, will use GITHUB_TOKEN env var"
    exit 1
fi

VERSION="$1"
GITHUB_TOKEN="${2:-$GITHUB_TOKEN}"
AUTO_UPLOAD=false

if [ -n "$GITHUB_TOKEN" ]; then
    AUTO_UPLOAD=true
    echo -e "${BLUE}📋 Configuration:${NC}"
    echo "   Version: $VERSION"
    echo "   Mode: Build + Auto-upload"
    echo "   GitHub Token: ${GITHUB_TOKEN:0:10}..."
    echo ""
else
    echo -e "${BLUE}📋 Configuration:${NC}"
    echo "   Version: $VERSION"
    echo "   Mode: Build only (manual upload)"
    echo ""
    echo -e "${YELLOW}💡 TIP: Provide GitHub token to auto-upload:${NC}"
    echo "   ./build-intel-and-release.sh 1.0.0 ghp_yourtoken"
    echo ""
fi

# Verify we're on Intel Mac
ARCH=$(uname -m)
echo -e "${BLUE}🔍 Checking system architecture...${NC}"
echo "   Detected: $ARCH"

if [ "$ARCH" != "x86_64" ]; then
    echo -e "${YELLOW}⚠️  WARNING: This script is designed for Intel Macs (x86_64)${NC}"
    echo "   You're running on: $ARCH"
    echo -e "${YELLOW}   The build might not work correctly!${NC}"
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi
echo ""

# Get repository info
REPO_OWNER=$(git config --get remote.origin.url | sed -n 's/.*github.com[:/]\(.*\)\/\(.*\)\.git/\1/p')
REPO_NAME=$(git config --get remote.origin.url | sed -n 's/.*github.com[:/]\(.*\)\/\(.*\)\.git/\2/p')

if [ -z "$REPO_OWNER" ] || [ -z "$REPO_NAME" ]; then
    echo -e "${RED}❌ ERROR: Could not detect GitHub repository!${NC}"
    echo "   Make sure you're in a git repository with a GitHub remote"
    exit 1
fi

echo -e "${BLUE}📦 Repository:${NC}"
echo "   Owner: $REPO_OWNER"
echo "   Repo: $REPO_NAME"
echo ""

# Clean previous builds
echo -e "${BLUE}🧹 Cleaning previous builds...${NC}"
rm -rf build dist *.dmg *.zip checksums-*.txt app/icon.icns app/icon.iconset
echo -e "${GREEN}   ✅ Cleaned${NC}"
echo ""

# Setup venv and install dependencies
echo -e "${BLUE}📦 Setting up virtual environment...${NC}"
if [ ! -d "venv" ] || [ ! -f "venv/bin/activate" ]; then
    echo "   Creating new venv..."
    python3 -m venv venv
else
    echo "   Using existing venv..."
fi
source venv/bin/activate
echo "   Installing dependencies..."
pip install -r requirements.txt
echo -e "${GREEN}   ✅ Venv activated and dependencies installed${NC}"
echo ""

# Create macOS icon
echo -e "${BLUE}🎨 Creating macOS icon (.icns)...${NC}"
mkdir -p app/icon.iconset
sips -z 16 16 app/ICON.png --out app/icon.iconset/icon_16x16.png
sips -z 32 32 app/ICON.png --out app/icon.iconset/icon_16x16@2x.png
sips -z 32 32 app/ICON.png --out app/icon.iconset/icon_32x32.png
sips -z 64 64 app/ICON.png --out app/icon.iconset/icon_32x32@2x.png
sips -z 128 128 app/ICON.png --out app/icon.iconset/icon_128x128.png
sips -z 256 256 app/ICON.png --out app/icon.iconset/icon_128x128@2x.png
sips -z 256 256 app/ICON.png --out app/icon.iconset/icon_256x256.png
sips -z 512 512 app/ICON.png --out app/icon.iconset/icon_256x256@2x.png
sips -z 512 512 app/ICON.png --out app/icon.iconset/icon_512x512.png
sips -z 1024 1024 app/ICON.png --out app/icon.iconset/icon_512x512@2x.png
iconutil -c icns app/icon.iconset -o app/icon.icns
rm -rf app/icon.iconset
echo -e "${GREEN}   ✅ Icon created: app/icon.icns${NC}"
echo ""

# Build Intel app
echo -e "${BLUE}🔨 Building Intel (x86_64) app with PyInstaller...${NC}"
export MACOSX_DEPLOYMENT_TARGET=11.0
echo "   Deployment target: macOS 11.0 Big Sur and later"
echo ""

python3 -m PyInstaller --name="ArgoLogViewer" \
  --windowed \
  --onefile \
  --icon="app/icon.icns" \
  --add-data="app:app" \
  --hidden-import=PySide6 \
  --hidden-import=paramiko \
  --hidden-import=cryptography \
  --clean \
  --osx-bundle-identifier=com.harshmeetsingh.argologviewer \
  --target-arch x86_64 \
  --codesign-identity - \
  app/main.py

echo ""
echo -e "${BLUE}🔧 Fixing code signatures for distribution...${NC}"

# Remove all code signatures to prevent Team ID mismatches
sudo codesign --remove-signature dist/ArgoLogViewer.app/Contents/MacOS/ArgoLogViewer 2>/dev/null || true

# Re-sign with consistent ad-hoc signature (deep sign everything)
sudo codesign -s - --deep --force dist/ArgoLogViewer.app

echo -e "${GREEN}   ✅ Code signatures fixed${NC}"

echo ""
echo -e "${YELLOW}⚠️  IMPORTANT SECURITY NOTICE:${NC}"
echo -e "${YELLOW}   This build is NOT code-signed or notarized by Apple${NC}"
echo -e "${YELLOW}   Users will see a Gatekeeper warning on first launch${NC}"
echo -e "${YELLOW}   See MACOS_INSTALLATION.md for user instructions${NC}"

echo ""
echo -e "${GREEN}   ✅ Build complete!${NC}"
echo ""

# Verify Intel binary
echo -e "${BLUE}🔍 Verifying Intel binary...${NC}"
EXECUTABLE="dist/ArgoLogViewer.app/Contents/MacOS/ArgoLogViewer"

if [ ! -f "$EXECUTABLE" ]; then
    echo -e "${RED}❌ ERROR: Executable not found at $EXECUTABLE${NC}"
    exit 1
fi

lipo -info "$EXECUTABLE"
file "$EXECUTABLE"

if lipo -info "$EXECUTABLE" | grep -q "x86_64"; then
    echo -e "${GREEN}   ✅ SUCCESS: Binary is Intel x86_64!${NC}"
else
    echo -e "${RED}   ❌ ERROR: Binary is not x86_64!${NC}"
    exit 1
fi
echo ""

# Create DMG installer
echo -e "${BLUE}📀 Creating Intel DMG installer...${NC}"
mkdir -p dist/dmg
cp -r dist/ArgoLogViewer.app dist/dmg/
ln -s /Applications dist/dmg/Applications
hdiutil create -volname "Argo Log Viewer (Intel)" \
  -srcfolder dist/dmg \
  -ov -format UDZO \
  "ArgoLogViewer-v${VERSION}-macOS-Intel.dmg"
rm -rf dist/dmg
echo -e "${GREEN}   ✅ DMG created${NC}"
echo ""

# Create ZIP
echo -e "${BLUE}📦 Creating Intel ZIP archive...${NC}"
cd dist
zip -r -q "../ArgoLogViewer-v${VERSION}-macOS-Intel.zip" ArgoLogViewer.app
cd ..
echo -e "${GREEN}   ✅ ZIP created${NC}"
echo ""

# Generate checksums
echo -e "${BLUE}🔐 Generating checksums...${NC}"
shasum -a 256 "ArgoLogViewer-v${VERSION}-macOS-Intel.dmg" > checksums-intel.txt
shasum -a 256 "ArgoLogViewer-v${VERSION}-macOS-Intel.zip" >> checksums-intel.txt
cat checksums-intel.txt
echo -e "${GREEN}   ✅ Checksums generated${NC}"
echo ""

# ---------------------------------------------
# Fast GitHub upload helper (GUI-like speed)
# ---------------------------------------------
upload_asset() {
    local file="$1"
    local content_type="$2"
    local filename
    filename=$(basename "$file")

    FILE_BYTES=$(stat -f%z "$file")
    
    # Convert bytes to human-readable format (macOS compatible)
    if [ $FILE_BYTES -ge 1073741824 ]; then
        FILE_SIZE=$(echo "scale=1; $FILE_BYTES/1073741824" | bc)"G"
    elif [ $FILE_BYTES -ge 1048576 ]; then
        FILE_SIZE=$(echo "scale=1; $FILE_BYTES/1048576" | bc)"M"
    elif [ $FILE_BYTES -ge 1024 ]; then
        FILE_SIZE=$(echo "scale=1; $FILE_BYTES/1024" | bc)"K"
    else
        FILE_SIZE="${FILE_BYTES}B"
    fi

    echo -e "${CYAN}📤 Uploading: $filename ($FILE_SIZE)${NC}"

    HTTP_CODE=$(curl -L --http1.1 \
      --connect-timeout 60 \
      --max-time 0 \
      --progress-bar \
      --write-out "%{http_code}" \
      -o /tmp/upload_response.json \
      -X POST \
      -H "Authorization: Bearer $GITHUB_TOKEN" \
      -H "Content-Type: $content_type" \
      -H "Content-Length: $FILE_BYTES" \
      --data-binary @"$file" \
      "https://uploads.github.com/repos/$REPO_OWNER/$REPO_NAME/releases/$RELEASE_ID/assets?name=$filename")

    if [ "$HTTP_CODE" -ne 201 ]; then
        echo -e "${RED}❌ Upload failed (HTTP $HTTP_CODE)${NC}"
        cat /tmp/upload_response.json
        exit 1
    fi

    echo -e "${GREEN}✅ Uploaded successfully${NC}"
}

# Upload to GitHub Release (if token provided)
if [ "$AUTO_UPLOAD" = true ]; then
    echo -e "${BLUE}🚀 Uploading to GitHub Release...${NC}"
    echo "   Tag: v${VERSION}"
    echo ""

    # Check if release exists
    RELEASE_ID=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
      "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/releases/tags/v${VERSION}" \
      | grep '"id":' | head -1 | sed 's/[^0-9]*//g')

    if [ -z "$RELEASE_ID" ]; then
        echo -e "${RED}❌ ERROR: Release v${VERSION} does not exist!${NC}"
        echo ""
        echo "Please create the release first by:"
        echo "  1. Running the GitHub Actions workflow to create ARM64 build"
        echo "  2. Or manually create the release at:"
        echo "     https://github.com/$REPO_OWNER/$REPO_NAME/releases/new?tag=v${VERSION}"
        echo ""
        exit 1
    fi

    echo -e "${GREEN}   ✅ Found release: ID=$RELEASE_ID${NC}"
    echo ""

    # Upload DMG
    DMG_FILE="ArgoLogViewer-v${VERSION}-macOS-Intel.dmg"
    ZIP_FILE="ArgoLogViewer-v${VERSION}-macOS-Intel.zip"

    [ -f "$DMG_FILE" ] || { echo -e "${RED}❌ Missing $DMG_FILE${NC}"; exit 1; }
    [ -f "$ZIP_FILE" ] || { echo -e "${RED}❌ Missing $ZIP_FILE${NC}"; exit 1; }

    upload_asset "$DMG_FILE" "application/x-apple-diskimage"
    upload_asset "$ZIP_FILE" "application/zip"

    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✅ SUCCESS! Intel build uploaded to release v${VERSION}${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${BLUE}📋 Files uploaded:${NC}"
    echo "   - ArgoLogViewer-v${VERSION}-macOS-Intel.dmg"
    echo "   - ArgoLogViewer-v${VERSION}-macOS-Intel.zip"
    echo ""
    echo -e "${YELLOW}⚠️  REMINDER: Add macOS installation instructions to release notes${NC}"
    echo -e "${YELLOW}   Copy from: MACOS_INSTALLATION.md${NC}"
    echo ""
    echo -e "${BLUE}🌐 View release at:${NC}"
    echo "   https://github.com/$REPO_OWNER/$REPO_NAME/releases/tag/v${VERSION}"
else
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✅ SUCCESS! Intel build complete${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${BLUE}📋 Files created:${NC}"
    echo "   - ArgoLogViewer-v${VERSION}-macOS-Intel.dmg"
    echo "   - ArgoLogViewer-v${VERSION}-macOS-Intel.zip"
    echo "   - checksums-intel.txt"
    echo ""
    echo -e "${YELLOW}📤 MANUAL UPLOAD REQUIRED${NC}"
    echo ""
    echo "   Upload these files to the release at:"
    echo "   https://github.com/$REPO_OWNER/$REPO_NAME/releases/edit/v${VERSION}"
    echo ""
    echo "   Steps:"
    echo "   1. Click the link above"
    echo "   2. Scroll to 'Attach binaries' section"
    echo "   3. Drag and drop the DMG and ZIP files"
    echo "   4. Add macOS installation instructions (see MACOS_INSTALLATION.md)"
    echo "   5. Click 'Update release'"
    echo ""
    echo -e "${YELLOW}⚠️  IMPORTANT: Include Gatekeeper bypass instructions in release notes${NC}"
fi

echo ""
echo -e "${BLUE}📝 Checksums:${NC}"
cat checksums-intel.txt
echo ""
echo -e "${YELLOW}💡 TIP: You can clean up build files with: rm -rf build dist *.dmg *.zip *.txt app/icon.icns${NC}"
echo ""
