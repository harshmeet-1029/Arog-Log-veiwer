# macOS Icon Creation

To create `app/icon.icns` for macOS builds:

## Option 1: On macOS (Recommended)

```bash
# Create iconset folder
mkdir -p icon.iconset

# Convert PNG to different sizes
sips -z 16 16     app/ICON.png --out icon.iconset/icon_16x16.png
sips -z 32 32     app/ICON.png --out icon.iconset/icon_16x16@2x.png
sips -z 32 32     app/ICON.png --out icon.iconset/icon_32x32.png
sips -z 64 64     app/ICON.png --out icon.iconset/icon_32x32@2x.png
sips -z 128 128   app/ICON.png --out icon.iconset/icon_128x128.png
sips -z 256 256   app/ICON.png --out icon.iconset/icon_128x128@2x.png
sips -z 256 256   app/ICON.png --out icon.iconset/icon_256x256.png
sips -z 512 512   app/ICON.png --out icon.iconset/icon_256x256@2x.png
sips -z 512 512   app/ICON.png --out icon.iconset/icon_512x512.png
sips -z 1024 1024 app/ICON.png --out icon.iconset/icon_512x512@2x.png

# Create .icns file
iconutil -c icns icon.iconset -o app/icon.icns

# Cleanup
rm -rf icon.iconset

echo "Created app/icon.icns"
```

## Option 2: Online Converter

1. Go to https://cloudconvert.com/png-to-icns
2. Upload `app/ICON.png`
3. Download the converted `icon.icns`
4. Save it as `app/icon.icns`

## Option 3: Use PNG2ICNS Tool

```bash
# Install npm tool
npm install -g png2icons

# Convert
png2icons app/ICON.png app/icon.icns -icns
```

---

Once you have `app/icon.icns`, the macOS build script will automatically use it!

**Note:** For now, macOS builds will work without the .icns file (using default icon).
