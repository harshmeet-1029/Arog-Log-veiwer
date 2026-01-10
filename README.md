# Argo Log Viewer - Production Grade

A production-grade Python desktop GUI application for viewing Argo Workflow logs through SSH.

## Features

- **Stateful SSH Connection Chain**: Maintains proper SSH session through jump host → internal server → sudo context
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

### Using the Application

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

## Safety Features

### Read-Only Operations

Only these kubectl commands are allowed:
- `kubectl get pods`
- `kubectl logs`
- `kubectl describe`

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

[Your License Here]

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
