#!/bin/bash

################################################################################
# Intel macOS Build & Release Script
# Run this on your Intel Mac to build and upload Intel binaries
#
# Usage:
#   ./build-intel-and-release.sh <version> [github-token]
#
# Examples:
#   ./build-intel-and-release.sh 1.0.2
#   ./build-intel-and-release.sh 1.0.2 ghp_yourtoken
################################################################################

set -e  # Exit on error

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Intel macOS Build & Release Script"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Version argument check ─────────────────────────────────────────────────────
if [ -z "$1" ]; then
    echo -e "${RED}ERROR: Version number required!${NC}"
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
    echo -e "${BLUE}Configuration:${NC}"
    echo "   Version: $VERSION"
    echo "   Mode: Build + Auto-upload"
    echo "   GitHub Token: ${GITHUB_TOKEN:0:10}..."
    echo ""
else
    echo -e "${BLUE}Configuration:${NC}"
    echo "   Version: $VERSION"
    echo "   Mode: Build only (manual upload)"
    echo ""
    echo -e "${YELLOW}TIP: Provide GitHub token to auto-upload:${NC}"
    echo "   ./build-intel-and-release.sh 1.0.0 ghp_yourtoken"
    echo ""
fi

# ── Architecture check ─────────────────────────────────────────────────────────
ARCH=$(uname -m)
echo -e "${BLUE}Checking system architecture...${NC}"
echo "   Detected: $ARCH"

if [ "$ARCH" != "x86_64" ]; then
    echo -e "${YELLOW}WARNING: This script is designed for Intel Macs (x86_64)${NC}"
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

# ── Repo info ─────────────────────────────────────────────────────────────────
REPO_OWNER=$(git config --get remote.origin.url | sed -n 's/.*github.com[:/]\(.*\)\/\(.*\)\.git/\1/p')
REPO_NAME=$(git config --get remote.origin.url | sed -n 's/.*github.com[:/]\(.*\)\/\(.*\)\.git/\2/p')

if [ -z "$REPO_OWNER" ] || [ -z "$REPO_NAME" ]; then
    echo -e "${RED}ERROR: Could not detect GitHub repository!${NC}"
    echo "   Make sure you're in a git repository with a GitHub remote"
    exit 1
fi

echo -e "${BLUE}Repository:${NC}"
echo "   Owner: $REPO_OWNER"
echo "   Repo:  $REPO_NAME"
echo ""

# ── Clean previous builds ─────────────────────────────────────────────────────
echo -e "${BLUE}Cleaning previous builds...${NC}"
rm -rf build dist *.dmg *.zip checksums-*.txt app/icon.icns app/icon.iconset app/build_metadata.py
echo -e "${GREEN}   Cleaned${NC}"
echo ""

# ── Virtual env + dependencies ────────────────────────────────────────────────
echo -e "${BLUE}Setting up virtual environment...${NC}"
if [ ! -d "venv" ] || [ ! -f "venv/bin/activate" ]; then
    echo "   Creating new venv..."
    python3 -m venv venv
else
    echo "   Using existing venv..."
fi
source venv/bin/activate
echo "   Installing dependencies..."
pip install --quiet -r requirements.txt
pip install --quiet pyinstaller
echo -e "${GREEN}   Venv activated and dependencies installed${NC}"
echo ""

# ── macOS icon (.icns) ────────────────────────────────────────────────────────
echo -e "${BLUE}Creating macOS icon (.icns)...${NC}"
mkdir -p app/icon.iconset
sips -z 16   16   app/ICON.png --out app/icon.iconset/icon_16x16.png
sips -z 32   32   app/ICON.png --out app/icon.iconset/icon_16x16@2x.png
sips -z 32   32   app/ICON.png --out app/icon.iconset/icon_32x32.png
sips -z 64   64   app/ICON.png --out app/icon.iconset/icon_32x32@2x.png
sips -z 128  128  app/ICON.png --out app/icon.iconset/icon_128x128.png
sips -z 256  256  app/ICON.png --out app/icon.iconset/icon_128x128@2x.png
sips -z 256  256  app/ICON.png --out app/icon.iconset/icon_256x256.png
sips -z 512  512  app/ICON.png --out app/icon.iconset/icon_256x256@2x.png
sips -z 512  512  app/ICON.png --out app/icon.iconset/icon_512x512.png
sips -z 1024 1024 app/ICON.png --out app/icon.iconset/icon_512x512@2x.png
iconutil -c icns app/icon.iconset -o app/icon.icns
rm -rf app/icon.iconset
echo -e "${GREEN}   Icon created: app/icon.icns${NC}"
echo ""

export MACOSX_DEPLOYMENT_TARGET=11.0

# ══════════════════════════════════════════════════════════════════════════════
# BUILD 1 - DMG variant  (executable: ArgoLogViewer-Installer, bundle: ArgoLogViewer.app)
# Matches the Apple Silicon CI job exactly.
# ══════════════════════════════════════════════════════════════════════════════
echo -e "${BLUE}[1/2] Generating build metadata for DMG variant...${NC}"
cat > app/build_metadata.py << EOF
"""Build metadata - Auto-generated during build. DO NOT EDIT."""
PLATFORM = "macos"
PACKAGE_TYPE = "dmg"
ARCHITECTURE = "amd64"
BUILD_DATE = "$VERSION"
VERSION = "$VERSION"
EOF
echo -e "${GREEN}   build_metadata.py written (VERSION=$VERSION, PACKAGE_TYPE=dmg)${NC}"

echo -e "${BLUE}[1/2] Building Intel DMG variant with PyInstaller...${NC}"
python3 -m PyInstaller --name="ArgoLogViewer-Installer" \
  --windowed \
  --onedir \
  --icon="app/icon.icns" \
  --add-data="app:app" \
  --hidden-import=PySide6 \
  --hidden-import=paramiko \
  --hidden-import=cryptography \
  --hidden-import=app.build_metadata \
  --clean \
  --osx-bundle-identifier=com.harshmeetsingh.argologviewer \
  --target-arch x86_64 \
  --codesign-identity - \
  app/main.py

# Rename to standard bundle name (matches CI)
mv dist/ArgoLogViewer-Installer.app dist/ArgoLogViewer.app

echo -e "${BLUE}   Fixing code signatures...${NC}"
sudo codesign --remove-signature "dist/ArgoLogViewer.app/Contents/MacOS/ArgoLogViewer-Installer" 2>/dev/null || true
sudo codesign -s - --deep --force dist/ArgoLogViewer.app

# Verify
EXEC_DMG="dist/ArgoLogViewer.app/Contents/MacOS/ArgoLogViewer-Installer"
if [ ! -f "$EXEC_DMG" ]; then
    echo -e "${RED}ERROR: DMG executable not found at $EXEC_DMG${NC}"
    exit 1
fi
if lipo -info "$EXEC_DMG" | grep -q "x86_64"; then
    echo -e "${GREEN}   DMG binary is x86_64${NC}"
else
    echo -e "${RED}   ERROR: DMG binary is not x86_64!${NC}"
    exit 1
fi

echo -e "${BLUE}   Creating DMG...${NC}"
mkdir -p dist/dmg
cp -r dist/ArgoLogViewer.app dist/dmg/
ln -s /Applications dist/dmg/Applications
hdiutil create -volname "Argo Log Viewer (Intel)" \
  -srcfolder dist/dmg \
  -ov -format UDZO \
  "ArgoLogViewer-v${VERSION}-macOS-Intel.dmg"
rm -rf dist/dmg dist/ArgoLogViewer.app
echo -e "${GREEN}   DMG created: ArgoLogViewer-v${VERSION}-macOS-Intel.dmg${NC}"
echo ""

# ══════════════════════════════════════════════════════════════════════════════
# BUILD 2 - ZIP variant  (executable: ArgoLogViewer-Portable, bundle: ArgoLogViewer-ZIP.app)
# Matches the Apple Silicon CI job exactly.
# ══════════════════════════════════════════════════════════════════════════════
echo -e "${BLUE}[2/2] Regenerating build metadata for ZIP variant...${NC}"
cat > app/build_metadata.py << EOF
"""Build metadata - Auto-generated during build. DO NOT EDIT."""
PLATFORM = "macos"
PACKAGE_TYPE = "zip"
ARCHITECTURE = "amd64"
BUILD_DATE = "$VERSION"
VERSION = "$VERSION"
EOF
echo -e "${GREEN}   build_metadata.py updated (VERSION=$VERSION, PACKAGE_TYPE=zip)${NC}"

echo -e "${BLUE}[2/2] Building Intel ZIP variant with PyInstaller...${NC}"
python3 -m PyInstaller --name="ArgoLogViewer-Portable" \
  --windowed \
  --onedir \
  --icon="app/icon.icns" \
  --add-data="app:app" \
  --hidden-import=PySide6 \
  --hidden-import=paramiko \
  --hidden-import=cryptography \
  --hidden-import=app.build_metadata \
  --clean \
  --osx-bundle-identifier=com.harshmeetsingh.argologviewer \
  --target-arch x86_64 \
  --codesign-identity - \
  app/main.py

mv dist/ArgoLogViewer-Portable.app dist/ArgoLogViewer-ZIP.app

echo -e "${BLUE}   Fixing code signatures...${NC}"
sudo codesign --remove-signature "dist/ArgoLogViewer-ZIP.app/Contents/MacOS/ArgoLogViewer-Portable" 2>/dev/null || true
sudo codesign -s - --deep --force dist/ArgoLogViewer-ZIP.app

echo -e "${BLUE}   Creating ZIP...${NC}"
cd dist
zip -r -q "../ArgoLogViewer-v${VERSION}-macOS-Intel.zip" ArgoLogViewer-ZIP.app
cd ..
echo -e "${GREEN}   ZIP created: ArgoLogViewer-v${VERSION}-macOS-Intel.zip${NC}"
echo ""

# ── Checksums ─────────────────────────────────────────────────────────────────
echo -e "${BLUE}Generating checksums...${NC}"
shasum -a 256 "ArgoLogViewer-v${VERSION}-macOS-Intel.dmg" >  checksums-intel.txt
shasum -a 256 "ArgoLogViewer-v${VERSION}-macOS-Intel.zip" >> checksums-intel.txt
cat checksums-intel.txt
echo -e "${GREEN}   Checksums saved to checksums-intel.txt${NC}"
echo ""

# ── Cleanup build_metadata so it is not accidentally committed ────────────────
rm -f app/build_metadata.py
echo -e "${GREEN}   Cleaned up app/build_metadata.py${NC}"
echo ""

# ── Upload helper ─────────────────────────────────────────────────────────────
upload_asset() {
    local file="$1"
    local content_type="$2"
    local filename
    filename=$(basename "$file")

    FILE_BYTES=$(stat -f%z "$file")

    if   [ "$FILE_BYTES" -ge 1073741824 ]; then
        FILE_SIZE=$(echo "scale=1; $FILE_BYTES/1073741824" | bc)"G"
    elif [ "$FILE_BYTES" -ge 1048576 ]; then
        FILE_SIZE=$(echo "scale=1; $FILE_BYTES/1048576" | bc)"M"
    elif [ "$FILE_BYTES" -ge 1024 ]; then
        FILE_SIZE=$(echo "scale=1; $FILE_BYTES/1024" | bc)"K"
    else
        FILE_SIZE="${FILE_BYTES}B"
    fi

    echo -e "${CYAN}Uploading: $filename ($FILE_SIZE)${NC}"

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
        echo -e "${RED}Upload failed (HTTP $HTTP_CODE)${NC}"
        cat /tmp/upload_response.json
        exit 1
    fi

    echo -e "${GREEN}   Uploaded successfully${NC}"
}

# ── GitHub upload ──────────────────────────────────────────────────────────────
if [ "$AUTO_UPLOAD" = true ]; then
    echo -e "${BLUE}Uploading to GitHub Release v${VERSION}...${NC}"
    echo ""

    RELEASE_ID=$(curl -s \
      -H "Authorization: token $GITHUB_TOKEN" \
      "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/releases/tags/v${VERSION}" \
      | grep '"id":' | head -1 | sed 's/[^0-9]*//g')

    if [ -z "$RELEASE_ID" ]; then
        echo -e "${RED}ERROR: Release v${VERSION} does not exist!${NC}"
        echo ""
        echo "Create the release first:"
        echo "  1. Run the GitHub Actions workflow to create the ARM64 build"
        echo "  2. Or manually create it at:"
        echo "     https://github.com/$REPO_OWNER/$REPO_NAME/releases/new?tag=v${VERSION}"
        echo ""
        exit 1
    fi

    echo -e "${GREEN}   Found release: ID=$RELEASE_ID${NC}"
    echo ""

    DMG_FILE="ArgoLogViewer-v${VERSION}-macOS-Intel.dmg"
    ZIP_FILE="ArgoLogViewer-v${VERSION}-macOS-Intel.zip"

    [ -f "$DMG_FILE" ] || { echo -e "${RED}Missing $DMG_FILE${NC}"; exit 1; }
    [ -f "$ZIP_FILE" ] || { echo -e "${RED}Missing $ZIP_FILE${NC}"; exit 1; }

    upload_asset "$DMG_FILE" "application/x-apple-diskimage"
    upload_asset "$ZIP_FILE" "application/zip"

    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}SUCCESS! Intel build uploaded to release v${VERSION}${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${BLUE}Files uploaded:${NC}"
    echo "   - ArgoLogViewer-v${VERSION}-macOS-Intel.dmg"
    echo "   - ArgoLogViewer-v${VERSION}-macOS-Intel.zip"
    echo ""
    echo -e "${BLUE}View release at:${NC}"
    echo "   https://github.com/$REPO_OWNER/$REPO_NAME/releases/tag/v${VERSION}"
else
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}SUCCESS! Intel build complete${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${BLUE}Files created:${NC}"
    echo "   - ArgoLogViewer-v${VERSION}-macOS-Intel.dmg"
    echo "   - ArgoLogViewer-v${VERSION}-macOS-Intel.zip"
    echo "   - checksums-intel.txt"
    echo ""
    echo -e "${YELLOW}MANUAL UPLOAD REQUIRED${NC}"
    echo ""
    echo "   Upload the files to:"
    echo "   https://github.com/$REPO_OWNER/$REPO_NAME/releases/edit/v${VERSION}"
    echo ""
    echo "   Steps:"
    echo "   1. Click the link above"
    echo "   2. Scroll to 'Attach binaries'"
    echo "   3. Drag and drop the DMG and ZIP files"
    echo "   4. Click 'Update release'"
fi

echo ""
echo -e "${BLUE}Checksums:${NC}"
cat checksums-intel.txt
echo ""
echo -e "${YELLOW}TIP: Clean up build files with:${NC}"
echo "   rm -rf build dist *.dmg *.zip *.txt app/icon.icns"
echo ""
