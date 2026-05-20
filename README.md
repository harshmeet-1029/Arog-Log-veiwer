# Argo Log Viewer - Production Grade

A production-grade Python desktop GUI application for viewing Argo Workflow logs through SSH.

## Why We Created This Tool

Working with Argo Workflows on Kubernetes clusters often requires navigating through multiple SSH jump servers and executing complex kubectl commands just to view logs. This tool was created to eliminate that friction and provide a seamless log viewing experience.

### The Problem

When working with Argo Workflows deployed on Kubernetes clusters behind SSH jump servers (like `solutions-argo-workflow`), developers face several pain points:

1. **Complex SSH Access Chain**: To view logs in real-time, you need to manually execute a tedious series of commands:
   ```
   Local Machine → ssh usejump → ssh 10.0.34.231 → sudo su - solutions01-prod-us-east-1-eks → kubectl commands
   ```
   This multi-step process is time-consuming and error-prone.

2. **"Waiting for Data" Delays**: The web-based Argo Workflow UI often displays "Waiting for data..." messages indefinitely, preventing you from seeing logs in real-time.

3. **Difficult Log Persistence**: Saving logs requires navigating to S3 buckets manually, which is cumbersome and time-consuming.

4. **Limited Search Capabilities**: Finding specific information in logs requires manual scrolling or complex grep commands through SSH.

5. **No Resource Monitoring**: Checking CPU and memory usage of pods requires logging into the SSH jump server and running multiple kubectl commands, making performance troubleshooting difficult.

6. **Line-Level Copy Restrictions**: The web UI doesn't allow copying individual log lines, forcing you to copy entire log blocks or use SSH for specific lines.

### The Solution

Argo Log Viewer automates the entire SSH chain and provides a modern desktop interface that:

- **Eliminates SSH Complexity**: Automatically handles the entire SSH jump server chain for you - no more manual logins
- **Real-Time Log Streaming**: View logs instantly with kubectl logs -f, no more "Waiting for data" messages
- **Easy Log Saving**: Save logs with one click while viewing them in real-time
- **Built-in Search**: Find what you need quickly with integrated search functionality
- **Real-Time Resource Monitoring**: View CPU and memory usage directly in the UI without SSH commands
- **Line-Level Copy**: Copy any single line or selection from the logs
- **Professional UI**: Modern, responsive interface with themes and proper layout

**Bottom Line**: This tool transforms a 5-command SSH workflow into a single click, while providing features that aren't available in the web UI.

## Features

- **Stateful SSH Connection Chain**: Maintains proper SSH session through jump host → internal server → sudo context
- **Custom SSH Folder Configuration**: Point to any SSH folder with your config and keys (NEW!)
- **OTA Updates**: Automatic update checking with one-click installation (NEW!)
- **Real-time Resource Monitoring**: Monitor CPU and memory utilization of pods in real-time (NEW!)
- **Modular Theme System**: Easy-to-extend theme system with Dark, Light, and High Contrast modes (NEW!)
- **Production-Grade Security**: 
  - Read-only operations only (no kubectl apply/delete/exec/scale)
  - Input sanitization to prevent command injection
  - Proper authentication via existing SSH config and agent
- **Real-time Log Streaming**: Live pod log viewing with kubectl logs -f
- **Search and Filter**: Find pods using grep-style keyword matching
- **Console Output**: See all SSH commands being executed in real-time
- **Modern UI**: Clean PySide6 (Qt) interface with proper layout
- **Non-blocking Operations**: All SSH operations run in background threads
- **Comprehensive Logging**: Debug logs saved to files for troubleshooting

## Architecture

### SSH Connection Flow

The application replicates your manual SSH workflow exactly:

```
Local Machine
  → ssh usejump 
    → ssh 10.0.34.231 
      → sudo su - solutions01-prod-us-east-1-eks
        → kubectl commands
```

This is achieved using:
- **Paramiko** with `invoke_shell()` for interactive sessions
- **Prompt detection** instead of fixed timeouts
- **Stateful connection** that preserves sudo context

### Project Structure

```
argo-log-viewer/
├── app/
│   ├── __init__.py
│   ├── main.py                    # Application entry point
│   ├── logging_config.py          # Centralized logging setup
│   ├── ssh/
│   │   ├── __init__.py
│   │   ├── connection_manager.py  # SSH connection management
│   │   └── argo_worker.py         # Threaded SSH operations
│   ├── kubernetes/
│   │   ├── __init__.py
│   │   └── operations.py          # Safe kubectl operations
│   └── ui/
│       ├── __init__.py
│       └── main_window.py         # Main GUI window
├── logs/                          # Application logs (auto-created)
├── requirements.txt               # Python dependencies
├── pyproject.toml                 # Project metadata
└── README.md                      # This file
```

## Requirements

- **Python 3.10+**
- **SSH Configuration**: `~/.ssh/config` with usejump host configured
- **SSH Agent**: For authentication (no hardcoded credentials)

## Installation

### Pre-built Binaries (Recommended)

Download the latest release from [GitHub Releases](../../releases).

**macOS Users - IMPORTANT:**
- macOS will **BLOCK this app on first launch** (expected security warning)
- **You MUST follow special steps to open it** - See: [macOS Installation Guide](MACOS_INSTALLATION.md)
- **Quick Fix:** System Settings → Privacy & Security → Click "Open Anyway"
- Or Terminal: `xattr -cr /Applications/ArgoLogViewer.app`

**NEW USERS: Follow these 5 steps exactly:**
1. Download DMG → Install to Applications
2. Try to open app (you'll see error) → Click "Done"
3. **System Settings** → **Privacy & Security** → Scroll to **Security** section
4. Click **"Open Anyway"** button
5. Confirm → Done! App will now open normally forever

---

**Linux Users - IMPORTANT (Portable):**

> If you double-click the Portable binary in the file manager, you will see:
> **"Could not Display - There is no app installed for Executable files"**
> This is **normal Linux security behavior**, not a bug.

You **must** launch it from a terminal:
```bash
chmod +x ArgoLogViewer-v*-Linux-Portable
./ArgoLogViewer-v*-Linux-Portable
```

Or enable it in the file manager: right-click → **Properties** → **Permissions** → check **"Allow executing as program"** → then double-click.

The **DEB package** (Installer) does not have this issue - it installs properly and appears in your Applications menu.

---

### 1. Clone or extract the project

```bash
cd /path/to/argo-log-viewer
```

### 2. Create virtual environment

```bash
python3 -m venv venv
```

### 3. Activate virtual environment

**macOS/Linux:**
```bash
source venv/bin/activate
```

**Windows:**
```cmd
venv\Scripts\activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

## Usage

### Running the Application

**macOS/Linux (quick start):**
```bash
chmod +x run.sh
./run.sh
```

**Or manually:**
```bash
source venv/bin/activate
python -m app.main
```

### New Features

#### 1. Custom SSH Folder Configuration
Point to any SSH folder with your config and keys:
- `Settings` → `Custom SSH Folder...`
- Browse to your SSH folder or leave empty for default (~/.ssh)
- Useful for project-specific SSH configs or encrypted drives

#### 2. OTA (Over-The-Air) Updates
Automatic update checking:
- Checks for updates on startup (once per 24 hours)
- Manual check: `Settings` → `Check for Updates`
- One-click download and installation
- View release notes before updating

**📖 For complete guide on all features, see: [FEATURES_GUIDE.md](FEATURES_GUIDE.md)**

### Using the Application

**⚠️ macOS First-Time Setup - REQUIRED:**
If you're on macOS and this is your first time opening the app, it will be **BLOCKED by macOS Gatekeeper**. This is normal!

**You MUST do this ONCE:**
1. Try to open the app → You'll see: *"ArgoLogViewer" can't be opened...*
2. Go to **System Settings** → **Privacy & Security**
3. Scroll to **Security** section → Click **"Open Anyway"**
4. Confirm by clicking **"Open"**

**Detailed guide with screenshots:** [macOS Installation Guide](MACOS_INSTALLATION.md)

---

**Once the app opens successfully:**

1. **Connect**: Click "Connect" button to establish SSH connection chain
   - Watch console output to see connection progress
   - Wait for "Ready for operations" message

2. **Search Pods**: 
   - Enter a keyword (e.g., "workflow-")
   - Click "Fetch Pods" or press Enter
   - Found pods will appear in the list

3. **View Logs**:
   - Double-click any pod in the list
   - Logs will stream in real-time in the bottom panel
   - **Resource metrics (CPU & Memory) automatically appear above the logs**
   - Metrics refresh every 3 seconds automatically
   - Click "Stop Log Stream" to stop streaming

4. **Disconnect**: Click "Disconnect" when done

### Console Output

The console panel shows all SSH commands being executed:
- `[INFO]` - Informational messages
- `[CMD]` - Actual commands being executed
- `[OK]` - Success messages
- `[ERROR]` - Error messages

This provides full transparency into what the application is doing.

## Configuration

### SSH Configuration

Ensure your `~/.ssh/config` has the jump host configured:

```
Host usejump
    HostName your-jump-host.example.com
    User your-username
    IdentityFile ~/.ssh/your-key
```

### Application Configuration

Key settings are in the code:
- **Namespace**: `argo` (in `app/kubernetes/operations.py`)
- **Internal Server**: `10.0.34.231` (in `app/ssh/connection_manager.py`)
- **Sudo User**: `solutions01-prod-us-east-1-eks` (in `app/ssh/connection_manager.py`)

To change these, edit the respective files.

## Logging

Application logs are saved to `logs/` directory with timestamps:
- **Format**: `argo_log_viewer_YYYYMMDD_HHMMSS.log`
- **Level**: DEBUG (all operations logged)
- **Location**: Project root `/logs/` directory

View logs for troubleshooting or auditing.

### Safety Features

### Read-Only Operations

Only these kubectl commands are allowed:
- `kubectl get pods`
- `kubectl logs`
- `kubectl describe`
- `kubectl top` (for resource metrics)

**NO WRITE OPERATIONS**: apply, delete, exec, scale, patch, etc.

### Input Sanitization

All user inputs are sanitized:
- Pod names validated against Kubernetes naming rules
- Search keywords filtered to prevent command injection
- Commands properly quoted with `shlex.quote()`

### Connection Management

- Automatic cleanup on application exit
- Graceful handling of connection failures
- Proper signal handling for Ctrl+C

## Troubleshooting

### "Metrics server not available" when monitoring resources

**Problem**: Resource monitoring fails with "Metrics server not available" error.

**Solution**: The resource monitoring feature requires metrics-server to be installed in your Kubernetes cluster.

To install metrics-server:
```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

To verify metrics-server is running:
```bash
kubectl get deployment metrics-server -n kube-system
```

Once metrics-server is installed and running, the resource monitoring feature will work.

---

### macOS: "App can't be opened because Apple cannot check it" ⚠️

**THIS IS THE #1 ISSUE FOR macOS USERS** - The app is blocked by macOS Gatekeeper on first launch.

**Solution (Choose ONE method):**

#### Method 1: System Settings (EASIEST - RECOMMENDED)
1. Try to open the app (you'll see error) → Click "Done"
2. **System Settings** → **Privacy & Security**
3. Scroll to **Security** section
4. Click **"Open Anyway"** button
5. Confirm by clicking **"Open"**
6. ✅ Done! App will open normally from now on

#### Method 2: Terminal Command
```bash
xattr -cr /Applications/ArgoLogViewer.app
```

For **macOS Sequoia (15.x)**, if the above doesn't work, also run:
```bash
sudo codesign --remove-signature /Applications/ArgoLogViewer.app/Contents/MacOS/ArgoLogViewer
sudo codesign -s - --deep --force /Applications/ArgoLogViewer.app
```

#### Method 3: Right-Click (May not work on macOS Sequoia)
Right-click the app → "Open" → "Open" again

**📖 Full guide with screenshots:** [macOS Installation Guide](MACOS_INSTALLATION.md)

---

### "Connection failed: Authentication failed"

**Solution**: Ensure SSH agent is running and has your key loaded
```bash
ssh-add -l  # List loaded keys
ssh-add ~/.ssh/your-key  # Add key if needed
```

### "Timeout waiting for shell prompt"

**Solution**: 
- Check network connectivity to jump host
- Verify jump host is accessible: `ssh usejump`
- Increase timeout in `connection_manager.py` if needed

### "No pods found"

**Solution**:
- Verify you're searching for correct pattern
- Check kubectl access: manually SSH and run `kubectl get pods -n argo`
- Ensure pods exist in the argo namespace

### Application freezes

**Solution**:
- Check `logs/` directory for error details
- Ensure operations are completing (check console output)
- Restart application and check SSH connectivity

## Development

### Creating a Release

See [RELEASE.md](RELEASE.md) - Just enter version in GitHub UI!

### Running with Debug Logging

Edit `app/main.py` and ensure:
```python
setup_logging(log_level=logging.DEBUG, log_to_file=True)
```

### Code Style

- Type hints used throughout
- Comprehensive docstrings
- Error handling at all levels
- Logging for all operations

### Testing Checklist

- [ ] SSH connection establishes successfully
- [ ] Console shows all commands being run
- [ ] Pod search works with various keywords
- [ ] Log streaming displays real-time output
- [ ] Stop button terminates streaming
- [ ] Disconnect closes connection cleanly
- [ ] Application exits without errors
- [ ] Logs written to `logs/` directory

## Security Considerations

### What This Application Does NOT Do

- ❌ Does NOT store or hardcode credentials
- ❌ Does NOT use one-liner SSH jump commands
- ❌ Does NOT skip SSH config or agent
- ❌ Does NOT allow write operations to cluster
- ❌ Does NOT bypass sudo requirements
- ❌ Does NOT execute arbitrary commands

### What This Application DOES Do

- ✅ Uses existing SSH configuration
- ✅ Authenticates via SSH agent
- ✅ Maintains proper SSH chain with sudo
- ✅ Sanitizes all user inputs
- ✅ Logs all operations for audit
- ✅ Read-only cluster access only

## Known Limitations

1. **Single Connection**: Only one SSH connection at a time
2. **Argo Namespace Only**: Hardcoded to `argo` namespace
3. **No Auto-Reconnect**: Must manually reconnect if connection drops

## License

**Restricted Use Software License**

Copyright © 2024-2026 Harshmeet Singh. All Rights Reserved.

This software is proprietary and its use is subject to license restrictions.

**Permitted:**
- Viewing source code for educational purposes
- Authorized organizational use (see LICENSE.txt for details)

**Not Permitted:**
- General use without authorization
- Modification (only author may modify)
- Redistribution or commercial use
- Creating derivative works

See [LICENSE.txt](LICENSE.txt) for complete terms and conditions.

**For licensing inquiries:**
- Harshmeet Singh
- harshmeetsingh010@gmail.com
- harshmeet.singh@netcoreunbxd.com

## Developer

**Harshmeet Singh**

📧 Contact:
- harshmeetsingh010@gmail.com
- harshmeet.singh@netcoreunbxd.com

## Support

For issues or questions:
1. Check logs in `logs/` directory
2. Review troubleshooting section above
3. Ensure SSH configuration is correct
4. Verify manual SSH workflow works

## Version History

### v1.0.0 (Current)
- Initial production release
- Full SSH chain support
- Real-time log streaming
- Console output panel
- Input sanitization
- Comprehensive logging
- **NEW:** Custom SSH folder configuration
- **NEW:** OTA update system