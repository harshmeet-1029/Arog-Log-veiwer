# macOS Build Instructions

## Quick Start (Intel Mac)

```bash
# 1. Make scripts executable
chmod +x create_macos_icon.sh
chmod +x build_macos_intel.sh

# 2. Run build script
./build_macos_intel.sh

# 3. Test the app
open dist/ArgoLogViewer.app

# Done! Your app is in: dist/ArgoLogViewer.app
```

---

## Step-by-Step (If Script Fails)

### Step 1: Create Icon

```bash
# Make script executable
chmod +x create_macos_icon.sh

# Run it
./create_macos_icon.sh

# This creates: app/icon.icns
```

### Step 2: Setup Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install pyinstaller
```

### Step 3: Build

```bash
# Clean old builds
rm -rf build dist

# Build
pyinstaller ArgoLogViewer.spec

# Output: dist/ArgoLogViewer.app
```

### Step 4: Test

```bash
# Run the app
open dist/ArgoLogViewer.app

# Or from terminal
dist/ArgoLogViewer.app/Contents/MacOS/ArgoLogViewer
```

---

## Troubleshooting

### "No icon showing"

**Problem:** Icon not appearing in app

**Solution:**
```bash
# Verify icon file exists
ls -la app/icon.icns

# If missing, create it:
./create_macos_icon.sh

# Rebuild
pyinstaller ArgoLogViewer.spec --clean
```

### "sips: command not found"

**Problem:** `create_macos_icon.sh` fails

**Solution:** Install Xcode Command Line Tools
```bash
xcode-select --install
```

### "App won't open" or "Damaged" error

**Problem:** macOS blocking unsigned app

**Solution:**
```bash
# Remove quarantine flag
xattr -cr dist/ArgoLogViewer.app

# Or allow in System Preferences:
# System Preferences → Security & Privacy → Allow
```

### "Permission denied"

**Problem:** Scripts not executable

**Solution:**
```bash
chmod +x create_macos_icon.sh
chmod +x build_macos_intel.sh
```

---

## Distribution

### Create DMG (Optional)

```bash
# Install create-dmg
brew install create-dmg

# Create DMG
create-dmg \
  --volname "Argo Log Viewer" \
  --window-pos 200 120 \
  --window-size 800 400 \
  --icon-size 100 \
  --icon "ArgoLogViewer.app" 200 190 \
  --hide-extension "ArgoLogViewer.app" \
  --app-drop-link 600 185 \
  "ArgoLogViewer.dmg" \
  "dist/ArgoLogViewer.app"
```

### Code Signing (For Distribution)

```bash
# List available certificates
security find-identity -v -p codesigning

# Sign the app
codesign --deep --force --verify --verbose \
  --sign "Developer ID Application: Your Name" \
  dist/ArgoLogViewer.app

# Verify signature
codesign --verify --verbose dist/ArgoLogViewer.app
spctl --assess --verbose dist/ArgoLogViewer.app
```

---

## Quick Reference

```bash
# Full build process
chmod +x *.sh
./create_macos_icon.sh
./build_macos_intel.sh
open dist/ArgoLogViewer.app

# Clean rebuild
rm -rf build dist
pyinstaller ArgoLogViewer.spec --clean

# Check icon
ls -la app/icon.icns

# Test app
open dist/ArgoLogViewer.app
```

---

## What Gets Created

```
dist/
└── ArgoLogViewer.app/
    ├── Contents/
    │   ├── MacOS/
    │   │   └── ArgoLogViewer     # Executable
    │   ├── Resources/
    │   │   └── icon.icns         # App icon
    │   ├── Frameworks/           # Python & dependencies
    │   └── Info.plist           # App metadata
```

---

## Notes

- **Intel Mac:** Use `build_macos_intel.sh`
- **M1/M2 Mac:** Same script works (creates universal binary)
- **Icon format:** macOS requires `.icns` (not `.ico` or `.png`)
- **Code signing:** Required for distribution outside App Store
- **Notarization:** Required for Catalina+ if distributing online

---

## For GitHub Actions (Automated macOS Build)

Will be added in next update. For now, build manually on your Mac.

---

**That's it! Your app should have an icon now! 🎉**
