#!/bin/bash
# Convert PNG to ICNS for macOS

echo "Converting ICON.png to icon.icns for macOS..."

# Check if ICON.png exists
if [ ! -f "app/ICON.png" ]; then
    echo "Error: app/ICON.png not found!"
    exit 1
fi

# Create temporary iconset directory
mkdir -p app/icon.iconset

# Generate different sizes (macOS requires multiple sizes)
sips -z 16 16     app/ICON.png --out app/icon.iconset/icon_16x16.png
sips -z 32 32     app/ICON.png --out app/icon.iconset/icon_16x16@2x.png
sips -z 32 32     app/ICON.png --out app/icon.iconset/icon_32x32.png
sips -z 64 64     app/ICON.png --out app/icon.iconset/icon_32x32@2x.png
sips -z 128 128   app/ICON.png --out app/icon.iconset/icon_128x128.png
sips -z 256 256   app/ICON.png --out app/icon.iconset/icon_128x128@2x.png
sips -z 256 256   app/ICON.png --out app/icon.iconset/icon_256x256.png
sips -z 512 512   app/ICON.png --out app/icon.iconset/icon_256x256@2x.png
sips -z 512 512   app/ICON.png --out app/icon.iconset/icon_512x512.png
sips -z 1024 1024 app/ICON.png --out app/icon.iconset/icon_512x512@2x.png

# Convert to icns
iconutil -c icns app/icon.iconset -o app/icon.icns

# Cleanup
rm -rf app/icon.iconset

echo "✓ Created app/icon.icns"
echo "Now you can run: pyinstaller ArgoLogViewer.spec"
