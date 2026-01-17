#!/bin/bash

################################################################################
# GitHub Release Upload Script - DMG Only
# Upload pre-built DMG binaries to an existing GitHub release
# No building - just uploading DMG files!
################################################################################

set -e  # Exit on error

# Color codes for pretty output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🍎 GitHub Release Upload Script - DMG Files Only"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if version is provided
if [ -z "$1" ]; then
    echo -e "${RED}❌ ERROR: Version number required!${NC}"
    echo ""
    echo "Usage: ./release-dmg-only.sh <version> [github-token] [file1] [file2] ..."
    echo ""
    echo "Examples:"
    echo "  # Upload specific DMG files"
    echo "  ./release-dmg-only.sh 1.0.0 ghp_token file1.dmg file2.dmg"
    echo ""
    echo "  # Auto-detect DMG files based on version"
    echo "  ./release-dmg-only.sh 1.0.0 ghp_token"
    echo ""
    echo "  # Use GITHUB_TOKEN env var"
    echo "  export GITHUB_TOKEN=ghp_yourtoken"
    echo "  ./release-dmg-only.sh 1.0.0"
    echo ""
    exit 1
fi

VERSION="$1"
GITHUB_TOKEN="${2:-$GITHUB_TOKEN}"

if [ -z "$GITHUB_TOKEN" ]; then
    echo -e "${RED}❌ ERROR: GitHub token required!${NC}"
    echo ""
    echo "Provide token as argument or set GITHUB_TOKEN environment variable:"
    echo "  ./release-dmg-only.sh $VERSION ghp_yourtoken"
    echo "OR"
    echo "  export GITHUB_TOKEN=ghp_yourtoken"
    echo "  ./release-dmg-only.sh $VERSION"
    echo ""
    exit 1
fi

# Get repository info
REPO_OWNER=$(git config --get remote.origin.url | sed -n 's/.*github.com[:/]\(.*\)\/\(.*\)\.git/\1/p')
REPO_NAME=$(git config --get remote.origin.url | sed -n 's/.*github.com[:/]\(.*\)\/\(.*\)\.git/\2/p')

if [ -z "$REPO_OWNER" ] || [ -z "$REPO_NAME" ]; then
    echo -e "${RED}❌ ERROR: Could not detect GitHub repository!${NC}"
    echo "   Make sure you're in a git repository with a GitHub remote"
    exit 1
fi

echo -e "${BLUE}📋 Configuration:${NC}"
echo "   Repository: $REPO_OWNER/$REPO_NAME"
echo "   Version: v$VERSION"
echo "   GitHub Token: ${GITHUB_TOKEN:0:10}..."
echo ""

# Determine files to upload
shift 2 2>/dev/null || shift 1  # Remove version and token from args
FILES_TO_UPLOAD=("$@")

if [ ${#FILES_TO_UPLOAD[@]} -eq 0 ]; then
    echo -e "${CYAN}🔍 Auto-detecting DMG files...${NC}"
    
    # Look for DMG patterns only
    PATTERNS=(
        "ArgoLogViewer-v${VERSION}-macOS-Intel.dmg"
        "ArgoLogViewer-v${VERSION}-macOS-ARM64.dmg"
        "ArgoLogViewer-macOS-Intel.dmg"
        "ArgoLogViewer-macOS-ARM64.dmg"
        "*.dmg"
    )
    
    for pattern in "${PATTERNS[@]}"; do
        for file in $pattern; do
            if [ -f "$file" ]; then
                FILES_TO_UPLOAD+=("$file")
            fi
        done
    done
    
    # Also check dist folder for DMG files only
    if [ -d "dist" ]; then
        for file in dist/*.dmg; do
            if [ -f "$file" ]; then
                FILES_TO_UPLOAD+=("$file")
            fi
        done
    fi
    
    # Remove duplicates
    FILES_TO_UPLOAD=($(echo "${FILES_TO_UPLOAD[@]}" | tr ' ' '\n' | sort -u | tr '\n' ' '))
fi

if [ ${#FILES_TO_UPLOAD[@]} -eq 0 ]; then
    echo -e "${RED}❌ ERROR: No DMG files found to upload!${NC}"
    echo ""
    echo "Specify DMG files manually:"
    echo "  ./release-dmg-only.sh $VERSION $GITHUB_TOKEN file1.dmg file2.dmg"
    echo ""
    echo "Or make sure DMG files exist in current directory with naming pattern:"
    echo "  ArgoLogViewer-v${VERSION}-macOS-Intel.dmg"
    echo "  ArgoLogViewer-v${VERSION}-macOS-ARM64.dmg"
    echo ""
    exit 1
fi

echo -e "${GREEN}   ✅ Found ${#FILES_TO_UPLOAD[@]} DMG file(s) to upload:${NC}"

# Filter to only .dmg files
FILTERED_FILES=()
for file in "${FILES_TO_UPLOAD[@]}"; do
    filename=$(basename "$file")
    extension="${filename##*.}"
    
    if [[ "$extension" == "dmg" ]]; then
        FILTERED_FILES+=("$file")
        if [ -f "$file" ]; then
            SIZE=$(du -h "$file" | cut -f1)
            echo "      - $file ($SIZE)"
        else
            echo -e "${YELLOW}      ⚠️  $file (not found - will skip)${NC}"
        fi
    else
        echo -e "${YELLOW}      ⚠️  Skipping $file (not a DMG file)${NC}"
    fi
done

FILES_TO_UPLOAD=("${FILTERED_FILES[@]}")
echo ""

# Check if release exists
echo -e "${CYAN}🔍 Checking release v${VERSION}...${NC}"

# Validate that we have files to upload after filtering
if [ ${#FILES_TO_UPLOAD[@]} -eq 0 ]; then
    echo -e "${RED}❌ ERROR: No valid DMG files to upload after filtering!${NC}"
    echo ""
    exit 1
fi

RELEASE_ID=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/releases/tags/v${VERSION}" \
  | grep '"id":' | head -1 | sed 's/[^0-9]*//g')

if [ -z "$RELEASE_ID" ]; then
    echo -e "${RED}❌ ERROR: Release v${VERSION} does not exist!${NC}"
    echo ""
    echo "Create the release first at:"
    echo "  https://github.com/$REPO_OWNER/$REPO_NAME/releases/new?tag=v${VERSION}"
    echo ""
    echo "Or run GitHub Actions workflow to create it automatically"
    echo ""
    exit 1
fi

echo -e "${GREEN}   ✅ Release found: ID=$RELEASE_ID${NC}"
echo ""

# Upload function with retry logic
upload_file() {
    local file="$1"
    local filename=$(basename "$file")

    if [ ! -f "$file" ]; then
        echo -e "${YELLOW}   ⚠️  Skipping $filename (file not found)${NC}"
        return 0
    fi

    echo -e "${CYAN}📤 Uploading: $filename${NC}"

    CONTENT_TYPE="application/x-apple-diskimage"

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
    
    echo "   Size: $FILE_SIZE"
    echo "   Type: $CONTENT_TYPE"

    echo "   Checking for existing asset..."
    EXISTING_ASSET_ID=$(curl -s \
      -H "Authorization: Bearer $GITHUB_TOKEN" \
      "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/releases/$RELEASE_ID/assets" \
      | grep -A3 "\"name\": \"$filename\"" | grep '"id":' | sed 's/[^0-9]*//g')

    if [ -n "$EXISTING_ASSET_ID" ]; then
        echo "   Deleting existing asset..."
        curl -s -X DELETE \
          -H "Authorization: Bearer $GITHUB_TOKEN" \
          "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/releases/assets/$EXISTING_ASSET_ID" \
          >/dev/null
    fi

    HTTP_CODE=$(curl -L --http1.1 \
      --connect-timeout 60 \
      --max-time 0 \
      --progress-bar \
      --write-out "%{http_code}" \
      -o /tmp/upload_response.json \
      -X POST \
      -H "Authorization: Bearer $GITHUB_TOKEN" \
      -H "Content-Type: $CONTENT_TYPE" \
      -H "Content-Length: $FILE_BYTES" \
      --data-binary @"$file" \
      "https://uploads.github.com/repos/$REPO_OWNER/$REPO_NAME/releases/$RELEASE_ID/assets?name=$filename")

    if [ "$HTTP_CODE" -ne 201 ]; then
        echo -e "${RED}❌ Upload failed (HTTP $HTTP_CODE)${NC}"
        cat /tmp/upload_response.json
        return 1
    fi

    echo -e "${GREEN}✅ Uploaded successfully${NC}"
}


# Upload all files
echo -e "${CYAN}🚀 Starting DMG uploads...${NC}"
echo ""

UPLOAD_COUNT=0
FAILED_COUNT=0

for file in "${FILES_TO_UPLOAD[@]}"; do
    if upload_file "$file"; then
        ((UPLOAD_COUNT++))
    else
        ((FAILED_COUNT++))
    fi
    echo ""
done

# Final summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $FAILED_COUNT -eq 0 ]; then
    echo -e "${GREEN}✅ SUCCESS! All DMG files uploaded${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${BLUE}📊 Summary:${NC}"
    echo "   Uploaded: $UPLOAD_COUNT file(s)"
    echo "   Failed: $FAILED_COUNT"
else
    echo -e "${YELLOW}⚠️  Upload completed with errors${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${BLUE}📊 Summary:${NC}"
    echo "   Uploaded: $UPLOAD_COUNT file(s)"
    echo -e "   ${RED}Failed: $FAILED_COUNT${NC}"
fi
echo ""
echo -e "${BLUE}🌐 View release at:${NC}"
echo "   https://github.com/$REPO_OWNER/$REPO_NAME/releases/tag/v${VERSION}"
echo ""

if [ $FAILED_COUNT -gt 0 ]; then
    exit 1
fi
