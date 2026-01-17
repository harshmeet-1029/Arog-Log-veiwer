#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 GitHub Release Upload Script (FAST & FIXED)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

VERSION="$1"
GITHUB_TOKEN="${2:-$GITHUB_TOKEN}"

if [[ -z "$VERSION" || -z "$GITHUB_TOKEN" ]]; then
  echo -e "${RED}❌ Version and GitHub token required${NC}"
  exit 1
fi

REPO_OWNER=$(git config --get remote.origin.url | sed -n 's/.*github.com[:/]\(.*\)\/\(.*\)\.git/\1/p')
REPO_NAME=$(git config --get remote.origin.url | sed -n 's/.*github.com[:/]\(.*\)\/\(.*\)\.git/\2/p')

echo -e "${BLUE}Repo:${NC} $REPO_OWNER/$REPO_NAME"
echo -e "${BLUE}Version:${NC} v$VERSION"
echo ""

shift 2 || true
FILES=("$@")

if [ ${#FILES[@]} -eq 0 ]; then
  FILES=( *.zip dist/*.zip )
fi

FILES=( $(printf "%s\n" "${FILES[@]}" | sort -u) )

echo -e "${GREEN}Files to upload:${NC}"
for f in "${FILES[@]}"; do
  [[ -f "$f" ]] && echo "  - $f"
done
echo ""

RELEASE_ID=$(curl -s \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/releases/tags/v$VERSION" \
  | grep '"id":' | head -1 | sed 's/[^0-9]*//g')

if [ -z "$RELEASE_ID" ]; then
  echo -e "${RED}❌ Release v$VERSION not found${NC}"
  exit 1
fi

echo -e "${GREEN}Release ID:${NC} $RELEASE_ID"
echo ""

upload_file() {
  local file="$1"
  local name=$(basename "$file")

  FILE_BYTES=$(stat -f%z "$file")
  CONTENT_TYPE="application/zip"

  echo -e "${CYAN}📤 Uploading $name ($(numfmt --to=iec $FILE_BYTES))${NC}"

  EXISTING_ID=$(curl -s \
    -H "Authorization: Bearer $GITHUB_TOKEN" \
    "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/releases/$RELEASE_ID/assets" \
    | grep -A3 "\"name\": \"$name\"" | grep '"id":' | sed 's/[^0-9]*//g')

  if [ -n "$EXISTING_ID" ]; then
    echo "   Deleting existing asset..."
    curl -s -X DELETE \
      -H "Authorization: Bearer $GITHUB_TOKEN" \
      "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/releases/assets/$EXISTING_ID" \
      >/dev/null
  fi

  HTTP_CODE=$(curl -L --http1.1 \
    --connect-timeout 60 \
    --max-time 0 \
    --progress-bar \
    --write-out "%{http_code}" \
    -o /tmp/upload.json \
    -X POST \
    -H "Authorization: Bearer $GITHUB_TOKEN" \
    -H "Content-Type: $CONTENT_TYPE" \
    -H "Content-Length: $FILE_BYTES" \
    --data-binary @"$file" \
    "https://uploads.github.com/repos/$REPO_OWNER/$REPO_NAME/releases/$RELEASE_ID/assets?name=$name")

  if [ "$HTTP_CODE" -ne 201 ]; then
    echo -e "${RED}❌ Upload failed (HTTP $HTTP_CODE)${NC}"
    cat /tmp/upload.json
    exit 1
  fi

  echo -e "${GREEN}✅ Uploaded $name${NC}"
}

for f in "${FILES[@]}"; do
  [[ -f "$f" ]] && upload_file "$f"
done

echo ""
echo -e "${GREEN}🎉 All uploads completed successfully${NC}"
echo "https://github.com/$REPO_OWNER/$REPO_NAME/releases/tag/v$VERSION"
