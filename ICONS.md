# Adding Custom Icons (Optional)

If you want to add custom icons to your application, follow these steps:

## Creating Icons

You need **3 different icon formats** for the 3 platforms:

### 1. Windows Icon (`.ico`)
- **Size**: 256x256 pixels (multi-resolution: 16, 32, 48, 256)
- **Format**: ICO file
- **Location**: `app/icon.ico`

**Create from PNG:**
```bash
# Using ImageMagick
magick convert icon.png -define icon:auto-resize=256,128,64,48,32,16 app/icon.ico

# Or use online tool: https://convertico.com/
```

### 2. macOS Icon (`.icns`)
- **Size**: 512x512 pixels (multi-resolution)
- **Format**: ICNS file
- **Location**: `app/icon.icns`

**Create from PNG:**
```bash
# On macOS
mkdir icon.iconset
sips -z 16 16     icon.png --out icon.iconset/icon_16x16.png
sips -z 32 32     icon.png --out icon.iconset/icon_16x16@2x.png
sips -z 32 32     icon.png --out icon.iconset/icon_32x32.png
sips -z 64 64     icon.png --out icon.iconset/icon_32x32@2x.png
sips -z 128 128   icon.png --out icon.iconset/icon_128x128.png
sips -z 256 256   icon.png --out icon.iconset/icon_128x128@2x.png
sips -z 256 256   icon.png --out icon.iconset/icon_256x256.png
sips -z 512 512   icon.png --out icon.iconset/icon_256x256@2x.png
sips -z 512 512   icon.png --out icon.iconset/icon_512x512.png
sips -z 1024 1024 icon.png --out icon.iconset/icon_512x512@2x.png
iconutil -c icns icon.iconset -o app/icon.icns
rm -rf icon.iconset
```

### 3. Linux Icon (`.png`)
- **Size**: 512x512 pixels
- **Format**: PNG file
- **Location**: `app/icon.png`

**Just use your original PNG:**
```bash
cp icon.png app/icon.png
```

---

## Updating Build Scripts

Once you have the icon files, update the build scripts:

### Windows (`build_windows.bat`)
Add back the icon line:
```batch
pyinstaller --name="ArgoLogViewer" ^
    --onefile ^
    --windowed ^
    --icon=app/icon.ico ^    <-- Add this line back
    --add-data="app;app" ^
    ...
```

### macOS (`build_macos.sh`)
Add back the icon line:
```bash
pyinstaller --name="ArgoLogViewer" \
    --windowed \
    --onefile \
    --icon=app/icon.icns \    # Add this line back
    --add-data="app:app" \
    ...
```

### Windows Installer (`installer_windows.iss`)
Add back the icon line:
```ini
SetupIconFile=app\icon.ico
```

---

## Icon Design Tips

### Professional Icon Checklist:
- ✅ Simple, recognizable design
- ✅ Works well at small sizes (16x16)
- ✅ High contrast colors
- ✅ Transparent background
- ✅ Matches your app's purpose

### Good Icon Ideas for Argo Log Viewer:
1. **Logs symbol** (📋 document with lines)
2. **Terminal icon** (⌨️ console window)
3. **Kubernetes logo** (☸️ helm/ship wheel)
4. **Combination** (terminal + cloud + logs)

### Free Icon Resources:
- **Icons8**: https://icons8.com/
- **Flaticon**: https://www.flaticon.com/
- **IconFinder**: https://www.iconfinder.com/
- **Material Icons**: https://fonts.google.com/icons

---

## Quick Icon Creation (Online Tools)

If you don't want to use command line:

1. **Create/Find a 512x512 PNG** of your icon
2. **Windows ICO**: https://convertico.com/
3. **macOS ICNS**: https://cloudconvert.com/png-to-icns
4. **Linux PNG**: Just use the 512x512 PNG directly

---

## Current Status

**Right now, the app builds WITHOUT icons** - it will use the default application icon for each platform. This is perfectly fine for:
- Internal tools
- Development versions
- Quick distribution

**Add icons when you want:**
- Professional distribution
- App Store submission
- Commercial release
- Branding requirements

---

## Testing Icons

After adding icons:

1. **Build the app** with the updated build script
2. **Check the executable** - should show your custom icon
3. **Install the app** - shortcuts should have your icon
4. **Test on target OS** - verify icon appears correctly

**Note:** Sometimes you need to rebuild the icon cache:
- **Windows**: Log out/in or restart Explorer
- **macOS**: Restart Finder or reboot
- **Linux**: Varies by desktop environment
