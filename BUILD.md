# Production-Grade Build Instructions

This guide shows how to create **professional installers** for macOS, Linux, and Windows - just like real commercial applications.

## What You'll Get

| Platform | Output Files | Features |
|----------|-------------|----------|
| **Windows** | `.exe` + Setup installer | Start Menu, Desktop icon, Uninstaller, System integration |
| **macOS** | `.app` + `.dmg` installer | Drag-to-Applications, Code signed, Professional presentation |
| **Linux** | Binary + `.deb` + `.rpm` | System integration, Package manager support |

---

## 🔧 Prerequisites

### All Platforms
```bash
# Create virtual environment
python3 -m venv venv

# Activate (macOS/Linux)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Windows Additional Tools
- **Inno Setup 6**: Download from https://jrsoftware.org/isdl.php
  - Free, professional installer creator
  - Used by many commercial applications

### macOS Additional Tools
```bash
# For DMG creation (optional but recommended)
brew install create-dmg

# Or use built-in hdiutil (less pretty)
```

### Linux Additional Tools
```bash
# For .deb packages (Debian/Ubuntu)
sudo apt-get install dpkg-dev

# For .rpm packages (Fedora/RHEL)
sudo apt-get install rpm  # On Debian/Ubuntu
# OR
sudo dnf install rpm-build  # On Fedora
```

---

## 🪟 Windows Production Build

### Quick Start
```cmd
build_windows.bat
```

### What It Creates

1. **Standalone Executable**
   - Location: `dist\ArgoLogViewer.exe`
   - Size: ~40-60 MB
   - No installation needed
   - Portable, can run from USB drive

2. **Professional Installer**
   - Location: `installers\windows\ArgoLogViewer-1.0.0-Windows-Setup.exe`
   - Size: ~40-60 MB
   - Features:
     - ✅ Modern wizard-style installer
     - ✅ Start Menu shortcuts
     - ✅ Desktop icon (optional)
     - ✅ Quick Launch icon (optional)
     - ✅ Professional uninstaller in Control Panel
     - ✅ System integration (Add/Remove Programs)
     - ✅ Checks for Visual C++ Redistributable
     - ✅ Custom icon and branding

### Manual Build Steps

```cmd
REM 1. Build executable
venv\Scripts\activate
pyinstaller --name="ArgoLogViewer" --onefile --windowed app/main.py

REM 2. Install Inno Setup from https://jrsoftware.org/isdl.php

REM 3. Compile installer
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer_windows.iss
```

### Distribution

**For Users:**
```
ArgoLogViewer-1.0.0-Windows-Setup.exe  (Recommended)
  OR
ArgoLogViewer.exe  (Portable version)
```

**Installation:** Double-click the Setup.exe, follow wizard

**Uninstallation:** Control Panel → Programs → Uninstall

---

## 🍎 macOS Production Build

### Quick Start
```bash
chmod +x build_macos.sh
./build_macos.sh
```

### What It Creates

1. **Standalone Application Bundle**
   - Location: `dist/ArgoLogViewer.app`
   - Size: ~60-80 MB
   - Double-click to run
   - Can be copied to /Applications

2. **Professional DMG Installer**
   - Location: `installers/macos/ArgoLogViewer-1.0.0-macOS.dmg`
   - Size: ~60-80 MB
   - Features:
     - ✅ Beautiful drag-to-Applications interface
     - ✅ Custom background and icons
     - ✅ Code signed (if certificate available)
     - ✅ Automatically opens when mounted
     - ✅ Professional presentation
     - ✅ Compressed and optimized

### Manual Build Steps

```bash
# 1. Build .app bundle
source venv/bin/activate
pyinstaller --name="ArgoLogViewer" --windowed --onefile app/main.py

# 2. Code sign (optional, requires certificate)
codesign --force --deep --sign "Developer ID Application: Your Name" dist/ArgoLogViewer.app

# 3. Create DMG
brew install create-dmg
create-dmg \
  --volname "Argo Log Viewer" \
  --window-pos 200 120 \
  --window-size 800 400 \
  --icon-size 100 \
  --icon "ArgoLogViewer.app" 200 190 \
  --app-drop-link 600 185 \
  "ArgoLogViewer.dmg" \
  "dist/ArgoLogViewer.app"
```

### Distribution

**For Users:**
```
ArgoLogViewer-1.0.0-macOS.dmg  (Recommended)
  OR
ArgoLogViewer.app  (Zip it first: zip -r ArgoLogViewer.zip ArgoLogViewer.app)
```

**Installation:**
1. Double-click the `.dmg`
2. Drag app to Applications folder
3. Eject the DMG

**Uninstallation:** Drag app to Trash from Applications

### Removing "Unidentified Developer" Warning

If users see "cannot be opened because it is from an unidentified developer":

```bash
# Users can run:
xattr -cr /Applications/ArgoLogViewer.app

# OR right-click → Open → Open (first time only)
```

**For production:** Get an Apple Developer account ($99/year) for proper code signing

---

## 🐧 Linux Production Build

### Quick Start
```bash
chmod +x build_linux.sh
./build_linux.sh
```

### What It Creates

1. **Standalone Binary**
   - Location: `dist/ArgoLogViewer`
   - Size: ~50-70 MB
   - No installation needed
   - Portable, can run from anywhere

2. **DEB Package (Debian/Ubuntu)**
   - Location: `installers/linux/argologviewer_1.0.0_amd64.deb`
   - Size: ~50-70 MB
   - Features:
     - ✅ System integration
     - ✅ Application menu entry
     - ✅ Desktop file for launchers
     - ✅ Dependency management
     - ✅ Clean uninstallation
     - ✅ Package manager support

3. **RPM Package (Fedora/RHEL/CentOS)**
   - Location: `installers/linux/argologviewer-1.0.0-1.x86_64.rpm`
   - Size: ~50-70 MB
   - Same features as DEB

### Manual Build Steps

```bash
# 1. Build binary
source venv/bin/activate
pyinstaller --name="ArgoLogViewer" --onefile app/main.py

# 2. Create .deb package
mkdir -p package/DEBIAN
mkdir -p package/usr/bin
cp dist/ArgoLogViewer package/usr/bin/argologviewer
# Create control file (see build_linux.sh for template)
dpkg-deb --build package argologviewer_1.0.0_amd64.deb

# 3. Create .rpm package
rpmbuild -ba argologviewer.spec
```

### Distribution

**For Debian/Ubuntu Users:**
```bash
sudo dpkg -i argologviewer_1.0.0_amd64.deb
# OR
sudo apt install ./argologviewer_1.0.0_amd64.deb
```

**For Fedora/RHEL Users:**
```bash
sudo rpm -i argologviewer-1.0.0-1.x86_64.rpm
# OR
sudo dnf install argologviewer-1.0.0-1.x86_64.rpm
```

**Portable Binary:**
```bash
chmod +x ArgoLogViewer
./ArgoLogViewer
```

### Uninstallation

```bash
# Debian/Ubuntu
sudo apt remove argologviewer

# Fedora/RHEL
sudo dnf remove argologviewer

# Portable
rm ArgoLogViewer
```

---

## 📦 Build Output Structure

After successful build:

```
argo-log-viewer/
├── dist/
│   ├── ArgoLogViewer.exe        # Windows standalone
│   ├── ArgoLogViewer.app/       # macOS app bundle
│   └── ArgoLogViewer            # Linux binary
│
└── installers/
    ├── windows/
    │   └── ArgoLogViewer-1.0.0-Windows-Setup.exe
    ├── macos/
    │   └── ArgoLogViewer-1.0.0-macOS.dmg
    └── linux/
        ├── argologviewer_1.0.0_amd64.deb
        └── argologviewer-1.0.0-1.x86_64.rpm
```

---

## 🎨 Customization

### Change App Name/Version

Edit these files before building:

**Windows:** `installer_windows.iss`
```innosetup
#define MyAppName "Your App Name"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Your Company"
```

**Linux:** `build_linux.sh`
```bash
Version: 1.0.0
Package: yourappname
```

### Add Custom Icon

1. **Windows:** Place `app/icon.ico` (256x256)
2. **macOS:** Place `app/icon.icns` (512x512)
3. **Linux:** Place `app/icon.png` (512x512)

Convert icons:
```bash
# PNG to ICO (Windows)
convert icon.png -define icon:auto-resize=256,128,64,48,32,16 icon.ico

# PNG to ICNS (macOS)
mkdir icon.iconset
sips -z 512 512   icon.png --out icon.iconset/icon_512x512.png
iconutil -c icns icon.iconset
```

---

## 🔒 Code Signing (Advanced)

### Windows
```powershell
# Get a code signing certificate from DigiCert, Sectigo, etc.
signtool sign /f certificate.pfx /p password /t http://timestamp.digicert.com dist\ArgoLogViewer.exe
```

### macOS
```bash
# Requires Apple Developer account ($99/year)
codesign --deep --force --verify --verbose --sign "Developer ID Application: Your Name" dist/ArgoLogViewer.app

# Notarize for Gatekeeper
xcrun notarytool submit ArgoLogViewer.dmg --wait
```

### Linux
```bash
# Use GPG signing for packages
gpg --armor --sign argologviewer_1.0.0_amd64.deb
```

---

## 🚀 Distribution Checklist

Before releasing:

- [ ] Test on clean machine (without Python installed)
- [ ] Verify all features work in built version
- [ ] Check file size is reasonable
- [ ] Test installation process
- [ ] Test uninstallation process
- [ ] Verify shortcuts and icons work
- [ ] Create SHA256 checksums
- [ ] Write release notes
- [ ] Tag version in git
- [ ] Upload to distribution platform

### Generate Checksums
```bash
# Windows
certutil -hashfile installers\windows\*.exe SHA256 > checksums.txt

# macOS/Linux
sha256sum installers/*/* > checksums.txt
```

---

## 🐛 Troubleshooting

### Windows: "Windows Defender SmartScreen prevented"
- Normal for unsigned executables
- Users can click "More info" → "Run anyway"
- Solution: Get a code signing certificate

### macOS: "damaged and can't be opened"
```bash
xattr -cr /Applications/ArgoLogViewer.app
```

### Linux: "error while loading shared libraries"
```bash
# Check dependencies
ldd dist/ArgoLogViewer

# Install missing libs
sudo apt-get install libxcb-xinerama0
```

### Build Fails: "Module not found"
Add to build script:
```bash
--hidden-import=missing_module
```

---

## 📊 Comparison: Simple vs Professional

| Aspect | Simple Build | Professional Build |
|--------|-------------|-------------------|
| **Windows** | Single .exe | Setup.exe with installer |
| **macOS** | .app bundle | .dmg with drag-to-install |
| **Linux** | Binary only | .deb + .rpm packages |
| **Installation** | Manual copy | Proper system integration |
| **Uninstall** | Delete file | Proper uninstaller |
| **Shortcuts** | None | Start Menu, Desktop, etc. |
| **Updates** | Manual | Can add auto-update |
| **Professional** | No | Yes ✓ |

---

## 🌟 What Makes This Production-Grade

✅ **Professional installers** for all platforms  
✅ **System integration** (Start Menu, Applications folder)  
✅ **Proper uninstallers**  
✅ **Code signing support** (with certificates)  
✅ **Package manager support** (.deb, .rpm)  
✅ **Custom branding** (icons, names, descriptions)  
✅ **Dependency checking** (Visual C++ Redistributable, etc.)  
✅ **Compressed and optimized** packages  
✅ **Professional presentation** (DMG backgrounds, wizard UI)  
✅ **Distribution ready** (checksums, release packages)  

---

## 📚 Additional Resources

- **Inno Setup**: https://jrsoftware.org/isinfo.php
- **create-dmg**: https://github.com/create-dmg/create-dmg
- **PyInstaller**: https://pyinstaller.org/en/stable/
- **Debian Packaging**: https://www.debian.org/doc/manuals/maint-guide/
- **RPM Packaging**: https://rpm-packaging-guide.github.io/
- **Code Signing**: https://codesign.guide/

---

## 🎯 Quick Commands Reference

```bash
# Windows
build_windows.bat

# macOS
chmod +x build_macos.sh && ./build_macos.sh

# Linux
chmod +x build_linux.sh && ./build_linux.sh
```

That's it! You now have production-grade installers ready for distribution! 🚀
