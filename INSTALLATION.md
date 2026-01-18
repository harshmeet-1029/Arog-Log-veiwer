# Installation Guide

This guide covers installation options for all platforms.

## 📦 Installation Options

### Windows

You have **two options** for Windows:

#### Option 1: Installer (Recommended) ✅

**File:** `ArgoLogViewer-vX.X.X-Windows-Installer.exe`

**Features:**
- ✅ Full installation wizard
- ✅ Start Menu shortcuts
- ✅ Desktop icon (optional)
- ✅ Automatic updates support
- ✅ Clean uninstaller via Control Panel

**Installation Steps:**
1. Download the installer
2. Double-click to run
3. Follow the installation wizard
4. If Windows Defender shows a warning:
   - Click "More info"
   - Click "Run anyway"
5. App will be installed to `C:\Program Files\Argo Log Viewer\`

**To Uninstall:**
```
Settings → Apps → Argo Log Viewer → Uninstall
```
or
```
Control Panel → Programs → Uninstall a program → Argo Log Viewer
```

#### Option 2: Portable

**File:** `ArgoLogViewer-vX.X.X-Windows-Portable.exe`

**Features:**
- ✅ Single executable
- ✅ No installation required
- ✅ Run from USB drive
- ✅ No registry entries
- ❌ No Start Menu shortcuts
- ❌ No automatic updates

**Usage:**
1. Download the portable exe
2. Move it anywhere you want
3. Double-click to run
4. No uninstallation needed - just delete the file

---

### Linux

You have **two options** for Linux:

#### Option 1: DEB Package (Debian/Ubuntu/Mint - Recommended) ✅

**File:** `ArgoLogViewer-vX.X.X-Linux-Installer.deb`

**Features:**
- ✅ System-wide installation
- ✅ Desktop menu entry
- ✅ Icon integration
- ✅ Run from anywhere: `argologviewer`
- ✅ Clean uninstaller via package manager

**Supported Distributions:**
- Ubuntu (18.04+)
- Debian (10+)
- Linux Mint
- Pop!_OS
- Elementary OS
- Any Debian-based distro

**Installation Steps:**

```bash
# Download the DEB file, then:
sudo dpkg -i ArgoLogViewer-vX.X.X-Linux-Installer.deb

# If you get dependency errors:
sudo apt-get install -f
```

**After Installation:**
- Run from terminal: `argologviewer`
- Or find it in your Applications menu under "Utilities"

**To Uninstall:**
```bash
sudo apt remove argologviewer
```

or use your package manager (Software Center, Synaptic, etc.)

#### Option 2: Portable (All Linux Distributions)

**File:** `ArgoLogViewer-vX.X.X-Linux-Portable`

**Features:**
- ✅ Single binary
- ✅ Works on ANY Linux distribution
- ✅ No root/sudo required
- ✅ Run from anywhere
- ❌ No desktop menu entry
- ❌ No system integration

**Supported Distributions:**
- Fedora, RHEL, CentOS
- Arch Linux, Manjaro
- openSUSE
- Any other Linux distribution

**Usage:**

```bash
# Download and make executable:
chmod +x ArgoLogViewer-vX.X.X-Linux-Portable

# Run from current directory:
./ArgoLogViewer-vX.X.X-Linux-Portable

# Optional: Install system-wide (requires sudo):
sudo mv ArgoLogViewer-vX.X.X-Linux-Portable /usr/local/bin/argologviewer
# Then run from anywhere:
argologviewer
```

**To Uninstall (if moved to system):**
```bash
sudo rm /usr/local/bin/argologviewer
```

---

### macOS

**Files:** 
- `ArgoLogViewer-vX.X.X-macOS-AppleSilicon.dmg` (M1/M2/M3/M4)
- `ArgoLogViewer-vX.X.X-macOS-Intel.dmg` (Intel Macs)

**Features:**
- ✅ Standard macOS .app bundle
- ✅ Drag and drop installation
- ✅ Native macOS integration
- ✅ Works from Applications folder

**Installation (DMG - Recommended):**
1. Download the correct DMG for your Mac type
2. Double-click the DMG file
3. Drag "ArgoLogViewer" to Applications folder
4. **Important:** Right-click the app → "Open" (first time only)
5. Click "Open" again to bypass Gatekeeper

**Installation (ZIP):**
1. Download and unzip
2. Move to Applications folder
3. Run in Terminal: `xattr -cr /Applications/ArgoLogViewer.app`
4. Open normally

**To Uninstall:**
Just drag the app from Applications to Trash

**For detailed macOS instructions, see:** [MACOS_INSTALLATION.md](MACOS_INSTALLATION.md)

---

## 🔍 Which Version Should I Choose?

### Windows Users

| Scenario | Recommended |
|----------|-------------|
| Regular use, want easy updates | **Installer** |
| Using on work computer without admin rights | **Portable** |
| Testing before installing | **Portable** |
| Want Start Menu shortcuts | **Installer** |
| Run from USB drive | **Portable** |

### Linux Users

| Scenario | Recommended |
|----------|-------------|
| Using Ubuntu/Debian/Mint | **DEB Package** |
| Using Fedora/Arch/other distros | **Portable** |
| No sudo/root access | **Portable** |
| Want system integration | **DEB Package** |
| Want desktop menu entry | **DEB Package** |

---

## ✅ Verify Your Download

All releases include `CHECKSUMS.txt` with SHA-256 hashes.

**Windows:**
```powershell
Get-FileHash -Algorithm SHA256 ArgoLogViewer-vX.X.X-Windows-*.exe
```

**Linux/macOS:**
```bash
sha256sum ArgoLogViewer-vX.X.X-*
```

Compare the output with `CHECKSUMS.txt`.

---

## 🐛 Troubleshooting

### Windows: "Windows protected your PC"
This is normal for unsigned applications.
- Click "More info"
- Click "Run anyway"

### Linux: "Permission denied"
```bash
chmod +x ArgoLogViewer-vX.X.X-Linux-Portable
```

### macOS: "App is damaged and can't be opened"
```bash
xattr -cr /Applications/ArgoLogViewer.app
```

### DEB Package: Dependency errors
```bash
sudo apt-get install -f
```

---

## 📖 Additional Resources

- [Main README](README.md)
- [macOS Installation Guide](MACOS_INSTALLATION.md)
- [Build Instructions](BUILD.md)

---

## 🆘 Need Help?

Report issues at: https://github.com/harshmeetsingh/argo-log-viewer/issues
