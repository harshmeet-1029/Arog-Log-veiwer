# Argo Log Viewer - Complete Guide

**Everything you need in ONE file!**

---

## 📑 Table of Contents

1. [Quick Start (Users)](#quick-start-users)
2. [Quick Start (Developers)](#quick-start-developers)
3. [Feature 1: Custom SSH Folder](#feature-1-custom-ssh-folder)
4. [Feature 2: OTA Updates](#feature-2-ota-updates)
5. [How to Release Updates](#how-to-release-updates)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)
8. [Configuration](#configuration)
9. [FAQ](#faq)

---

## Quick Start (Users)

### Install and Run

1. **Download:** https://github.com/harshmeet-1029/Arog-Log-veiwer/releases/latest
2. **Run:** Double-click `ArgoLogViewer.exe`
3. **Done!** Updates work automatically.

### First Time Setup

1. Launch the app
2. Click **Connect** to establish SSH connection
3. Configure SSH folder if needed: `Settings` → `Custom SSH Folder`

That's it! 🎉

---

## Quick Start (Developers)

### Clone and Run

```bash
# Clone
git clone https://github.com/harshmeet-1029/Arog-Log-veiwer.git
cd Arog-Log-veiwer

# Setup
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Run
python -m app.main
```

### Build Executable

**Windows:**
```bash
pip install pyinstaller
pyinstaller ArgoLogViewer.spec
# Output: dist\ArgoLogViewer.exe
```

**macOS:**
```bash
# First, create icon
chmod +x create_macos_icon.sh
./create_macos_icon.sh

# Then build
pip install pyinstaller
pyinstaller ArgoLogViewer.spec
# Output: dist/ArgoLogViewer.app

# Or use the all-in-one script:
chmod +x build_macos_intel.sh
./build_macos_intel.sh
```

**See [BUILD_MACOS.md](BUILD_MACOS.md) for detailed macOS instructions.**

---

## Feature 1: Custom SSH Folder

### What It Does

Point the app to any folder containing your SSH config and keys instead of using `~/.ssh`.

**Use Cases:**
- Project-specific SSH configs
- SSH files on encrypted drive
- Testing with different credentials
- Multiple SSH configurations

### How to Use

**Set Custom Folder:**
1. `Settings` → `Custom SSH Folder...`
2. Click `Browse...` and select your folder
3. Validation shows (✓ green = good, ⚠ orange = warning, ✗ red = error)
4. Click `OK`

**Remove Custom Folder:**
1. Open same dialog
2. Click `Remove Custom Folder (Use Default)`
3. Click `OK`

### Folder Requirements

```
your-ssh-folder/
├── config          # Required
├── id_rsa         # Optional
├── id_ed25519     # Optional
└── known_hosts    # Optional
```

### Example

```bash
# Create test folder
mkdir ~/my-ssh
cp ~/.ssh/config ~/my-ssh/
cp ~/.ssh/id_rsa ~/my-ssh/

# In app: Settings → Custom SSH Folder → Browse to ~/my-ssh
# Connect - uses ~/my-ssh instead of ~/.ssh
```

**Config stored at:** `~/.argo-log-viewer/config.json`

---

## Feature 2: OTA Updates

### What It Does

Automatically checks for new versions and lets you download updates with one click.

**Features:**
- Auto-check on startup (every 24 hours)
- Manual check anytime
- View release notes
- Skip non-critical updates
- One-click download

### How It Works

**Automatic (Default):**
- App checks GitHub when you launch it (once per 24 hours)
- If update available → Notification appears
- Click "Download Update" → Browser opens
- Download new .exe and replace old one

**Manual:**
1. `Settings` → `Check for Updates`
2. Wait a few seconds
3. Dialog shows result

### Configuration (Optional)

```bash
# Disable auto-checks
setx ARGO_CHECK_UPDATES_ON_STARTUP "false"

# Change interval (seconds)
setx ARGO_UPDATE_CHECK_INTERVAL "43200"  # 12 hours

# Custom server
setx ARGO_UPDATE_SERVER_URL "https://your-server.com/api/updates"
```

**Default server:** `https://api.github.com/repos/harshmeet-1029/Arog-Log-veiwer/releases/latest`

---

## How to Release Updates

### Automated (RECOMMENDED!)

```bash
# 1. Update version in app/config.py
CURRENT_VERSION = "1.1.0"  # Change this line

# 2. Commit and push
git add app/config.py
git commit -m "Bump version to 1.1.0"
git push

# 3. Create and push tag
git tag v1.1.0
git push origin v1.1.0

# 4. Done! GitHub Actions will:
#    - Build ArgoLogViewer.exe (5-10 minutes)
#    - Create release
#    - Upload file
#    Check: https://github.com/harshmeet-1029/Arog-Log-veiwer/actions
```

### Manual (If needed)

```bash
# 1. Update version
# Edit app/config.py: CURRENT_VERSION = "1.1.0"

# 2. Build
pyinstaller ArgoLogViewer.spec

# 3. Go to GitHub
# https://github.com/harshmeet-1029/Arog-Log-veiwer/releases/new

# 4. Fill in:
#    Tag: v1.1.0
#    Title: Version 1.1.0
#    Upload: dist\ArgoLogViewer.exe
#    Publish!
```

### What Users See

When you release v1.1.0:

```
User with v1.0.0 opens app
    ↓
"Update Available: v1.1.0"
    ↓
User clicks "Download Update"
    ↓
Browser opens to release page
    ↓
User downloads and installs
```

---

## Testing

### Test Custom SSH Folder

```bash
# Create test folder
mkdir ~/test-ssh
cp ~/.ssh/config ~/test-ssh/

# In app:
# 1. Settings → Custom SSH Folder
# 2. Browse to ~/test-ssh
# 3. Click OK
# 4. Connect
# 5. Check console: "Using custom SSH folder: /path/to/test-ssh"
```

### Test Update Notifications

```bash
# Method 1: Create test release
# 1. Keep code at v1.0.0
# 2. Create GitHub release v1.0.1
# 3. Run app
# 4. Should see "Update Available: v1.0.1"

# Method 2: Manual check
# 1. Run app
# 2. Settings → Check for Updates
# 3. Dialog shows result
```

### Test Build

```bash
# Build and test
pyinstaller ArgoLogViewer.spec
dist\ArgoLogViewer.exe

# Should launch without errors
```

---

## Troubleshooting

### Custom SSH Folder Issues

**Problem:** "Config file not found"
```bash
# Ensure folder has config file
ls ~/your-folder/config

# Create if missing
touch ~/your-folder/config
nano ~/your-folder/config
```

**Problem:** Connection fails
```bash
# Check SSH keys exist
ls -la ~/your-folder/

# Check permissions
chmod 600 ~/your-folder/id_rsa

# Test manually
ssh -F ~/your-folder/config your-host
```

**Problem:** Folder not used
```bash
# Verify saved
cat ~/.argo-log-viewer/config.json

# Check logs
tail logs/argo_log_viewer_*.log
# Look for: "Using custom SSH folder"
```

### Update Check Issues

**Problem:** Update check fails
```bash
# Test URL manually
curl https://api.github.com/repos/harshmeet-1029/Arog-Log-veiwer/releases/latest

# Check internet
ping github.com

# Check logs
tail logs/argo_log_viewer_*.log | grep -i update
```

**Problem:** No notification
```bash
# Check last check time
cat ~/.argo-log-viewer/config.json | grep last_update_check

# Check if skipped
cat ~/.argo-log-viewer/config.json | grep skip_update_version

# Force new check
rm ~/.argo-log-viewer/config.json
```

**Problem:** GitHub Actions failed
```bash
# Check workflow
# https://github.com/harshmeet-1029/Arog-Log-veiwer/actions

# Common issues:
# - Missing dependencies → Update requirements.txt
# - Build errors → Check pyinstaller spec file
# - Tag format wrong → Use v1.0.0 format
```

### General Issues

**Problem:** App won't start
```bash
# Check Python version
python --version  # Need 3.10+

# Reinstall dependencies
pip install -r requirements.txt

# Check logs
cat logs/argo_log_viewer_*.log
```

**Problem:** Config file not created
```bash
# Create manually
mkdir -p ~/.argo-log-viewer
touch ~/.argo-log-viewer/config.json
echo '{}' > ~/.argo-log-viewer/config.json
```

---

## Configuration

### Config File Location

`~/.argo-log-viewer/config.json`

**Permissions:** `0o600` (owner only)

**Example:**
```json
{
  "custom_ssh_folder": "/path/to/ssh",
  "last_update_check": 1705536000.0,
  "skip_update_version": "1.0.1"
}
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ARGO_UPDATE_SERVER_URL` | GitHub API | Update server endpoint |
| `ARGO_CHECK_UPDATES_ON_STARTUP` | `true` | Check on launch |
| `ARGO_UPDATE_CHECK_INTERVAL` | `86400` (24h) | Seconds between checks |
| `ARGO_JUMP_HOST` | `usejump` | SSH jump host |
| `ARGO_INTERNAL_HOST` | `10.0.34.231` | Internal server IP |
| `ARGO_SERVICE_ACCOUNT` | `solutions01-prod-us-east-1-eks` | Service account |
| `ARGO_NAMESPACE` | `argo` | Kubernetes namespace |

### Application Settings

**Version:** Edit `app/config.py` line 119
```python
CURRENT_VERSION = "1.0.0"
```

**Update URL:** Edit `app/config.py` line 123
```python
UPDATE_SERVER_URL = "https://api.github.com/repos/harshmeet-1029/Arog-Log-veiwer/releases/latest"
```

---

## FAQ

**Q: Does custom SSH folder affect my system ~/.ssh?**  
A: No! Only changes what the app uses.

**Q: Are updates installed automatically?**  
A: No! You must manually download and install.

**Q: How often does it check for updates?**  
A: Once per 24 hours (configurable).

**Q: Can I disable update checks?**  
A: Yes! `setx ARGO_CHECK_UPDATES_ON_STARTUP "false"`

**Q: Where are logs stored?**  
A: `logs/argo_log_viewer_*.log` in project folder.

**Q: Where is config stored?**  
A: `~/.argo-log-viewer/config.json`

**Q: Can I have multiple custom SSH folders?**  
A: One at a time. Change via Settings menu.

**Q: What if GitHub is down?**  
A: App logs error and continues normally.

**Q: Is my SSH config modified?**  
A: No! App only reads, never modifies.

**Q: Do I need a GitHub account to use updates?**  
A: No! Only to download releases.

**Q: Can I use a different update server?**  
A: Yes! Set `ARGO_UPDATE_SERVER_URL` environment variable.

---

## Project Structure

```
argo-log-viewer/
├── app/
│   ├── config.py              # Configuration & versions
│   ├── update_checker.py      # OTA update logic
│   ├── main.py               # Entry point
│   ├── ui/
│   │   └── main_window.py    # Main UI
│   └── ssh/
│       ├── connection_manager.py
│       └── argo_worker.py
├── .github/
│   └── workflows/
│       └── build-release.yml  # Auto-build workflow
├── ArgoLogViewer.spec        # PyInstaller config
├── requirements.txt          # Dependencies
├── README.md                 # Main docs
└── FEATURES_GUIDE.md        # This file!
```

---

## Technical Details

### Files Modified

**Code:**
- `app/config.py` - Added `AppConfig` and `UpdateConfig`
- `app/ui/main_window.py` - Added UI for both features
- `app/ssh/connection_manager.py` - Uses custom SSH folder
- `requirements.txt` - Added `packaging>=24.0`

**New:**
- `app/update_checker.py` - Update checking logic
- `.github/workflows/build-release.yml` - Auto-build

### Security Features

- Config file: `0o600` permissions
- HTTPS-only update checks
- SSL certificate validation
- No automatic code installation
- Path validation
- All operations logged

### Update Flow

```
App Launch
    ↓
Should check? (24h+ since last)
    ↓ Yes
HTTP GET → GitHub API
    ↓
Parse JSON response
    ↓
Compare versions
    ↓
Version > current?
    ↓ Yes
Show notification
    ↓
User clicks Download
    ↓
Open browser to release
```

### Custom SSH Flow

```
User sets custom folder
    ↓
Save to config.json
    ↓
User clicks Connect
    ↓
App reads: SSHConfig.get_ssh_folder()
    ↓
Returns custom folder (if set)
    ↓
Load config from: custom_folder/config
    ↓
Load keys from: custom_folder/id_rsa
    ↓
Connect using custom credentials
```

---

## Version History

**v1.0.0** - Initial Release
- SSH connection management
- Custom SSH folder configuration
- OTA update system
- Real-time log streaming
- Pod search and filtering
- Modern UI with themes

---

## Quick Reference

### Release Checklist

- [ ] Update `CURRENT_VERSION` in `app/config.py`
- [ ] Commit changes
- [ ] Push to GitHub
- [ ] Create tag: `git tag v1.X.X`
- [ ] Push tag: `git push origin v1.X.X`
- [ ] Wait for GitHub Actions (5-10 min)
- [ ] Check release page
- [ ] Test download link

### Important Links

- **Releases:** https://github.com/harshmeet-1029/Arog-Log-veiwer/releases
- **Actions:** https://github.com/harshmeet-1029/Arog-Log-veiwer/actions
- **Issues:** https://github.com/harshmeet-1029/Arog-Log-veiwer/issues

### Command Cheatsheet

```bash
# Run from source
python -m app.main

# Build executable
pyinstaller ArgoLogViewer.spec

# Release new version
git tag v1.X.X && git push origin v1.X.X

# Check logs
tail -f logs/argo_log_viewer_*.log

# View config
cat ~/.argo-log-viewer/config.json

# Test update URL
curl https://api.github.com/repos/harshmeet-1029/Arog-Log-veiwer/releases/latest
```

---

## Support

**Developer:** Harshmeet Singh

**Email:**
- harshmeetsingh010@gmail.com
- harshmeet.singh@netcoreunbxd.com

**Before contacting:**
1. Check logs: `logs/argo_log_viewer_*.log`
2. Check config: `~/.argo-log-viewer/config.json`
3. Try troubleshooting section above
4. Check GitHub Issues

**When reporting bugs:**
- Include log files
- Describe steps to reproduce
- Include OS and Python version
- Include error messages

---

## License

**Proprietary Software - All Rights Reserved**

Copyright © 2024-2026 Harshmeet Singh

This software is proprietary and confidential. Unauthorized copying, forking, 
distribution, or use without explicit written permission is **STRICTLY PROHIBITED**.

### What You CANNOT Do Without Permission:
- ❌ Fork or copy the source code
- ❌ Create derivative works
- ❌ Use for commercial purposes
- ❌ Redistribute or resell
- ❌ Reverse engineer

### What Requires Royalty Payment:
- Forking the repository
- Creating derivative works
- Commercial use
- Distribution to third parties

### Contact for Licensing:
- **Email:** harshmeetsingh010@gmail.com
- **Email:** harshmeet.singh@netcoreunbxd.com

See [LICENSE.txt](LICENSE.txt) for complete legal terms.

---

**That's everything in ONE file! 🎉**

For main project info, see [README.md](README.md)
