# Version Management & OTA Updates

## Quick Release Guide

**Easy way:** Use GitHub Actions workflow at `.github/workflows/build-all-platforms.yml`

1. Go to Actions → "Build All Platforms"
2. Click "Run workflow"
3. Enter version (e.g., `1.0.1`)
4. Click "Run workflow"
5. Done! See [RELEASE.md](../RELEASE.md)

## How It Works

The app automatically reads version from `pyproject.toml`. The GitHub Actions workflow updates it for you when you release.

## Version Detection

The app reads version from `pyproject.toml`:

```python
# app/config.py - automatically reads from pyproject.toml
version = UpdateConfig.get_current_version()
```

Falls back to `1.0.0` if file not found (for bundled apps).

## Configuration

### Update Server URL
Default: GitHub Releases API for your repository

Override via environment variable:
```bash
export ARGO_UPDATE_SERVER_URL="https://api.github.com/repos/YOUR_USER/YOUR_REPO/releases/latest"
```

### Check on Startup
Default: `true`

Disable via environment variable:
```bash
export ARGO_CHECK_UPDATES_ON_STARTUP=false
```

### Check Interval
Default: `24 hours` (86400 seconds)

Change via environment variable:
```bash
export ARGO_UPDATE_CHECK_INTERVAL=43200  # 12 hours
```

## GitHub Release Tag Format

The updater supports both formats:
- `v1.0.1` (with 'v' prefix) → Automatically stripped to `1.0.1`
- `1.0.1` (without 'v' prefix) → Used as-is

## Example: Version Update Scenario

### Scenario: Releasing v1.0.1

**Current version:** `1.0.0` (in `pyproject.toml`)

1. **Developer updates `pyproject.toml`:**
   ```toml
   version = "1.0.1"
   ```

2. **Developer builds the app:**
   ```bash
   ./build_windows.bat
   # Or: ./build_linux.sh
   # Or: ./build_macos_arm.sh
   ```
   → Built app contains version `1.0.1`

3. **Developer creates GitHub release:**
   - Tag: `v1.0.1`
   - Upload: `ArgoLogViewer-1.0.1-windows.exe`

4. **User with v1.0.0 opens the app:**
   - App reads its version: `1.0.0` (from `pyproject.toml` or fallback)
   - App queries GitHub API: Latest release is `v1.0.1`
   - App compares: `1.0.1 > 1.0.0` → **Update available!**
   - User sees update notification with download link

5. **User with v1.0.1 opens the app:**
   - App reads its version: `1.0.1`
   - App queries GitHub API: Latest release is `v1.0.1`
   - App compares: `1.0.1 == 1.0.1` → **Up to date!**
   - No notification shown

## Troubleshooting

### Version not detected during build
**Problem:** Build shows fallback version `1.0.0`

**Solution:** Ensure `pyproject.toml` is in the project root and contains:
```toml
[project]
version = "x.y.z"
```

### Update check always fails
**Problem:** Users don't see updates

**Solutions:**
1. Check GitHub release is **published** (not draft)
2. Verify repository is **public** or set `ARGO_UPDATE_SERVER_URL` with auth token
3. Check internet connectivity
4. Check logs: `logs/argo_log_viewer_*.log`

### Version comparison issues
**Problem:** App thinks `1.0.10` < `1.0.9`

**Solution:** The `packaging` library handles this correctly. If you see this, check that versions are being parsed correctly (not as strings).

## Benefits

✅ **No more forgetting to update versions** → Automatic from `pyproject.toml`  
✅ **No more pushing multiple times** → Single source of truth  
✅ **No more manual sync** → Build process reads version automatically  
✅ **Proper semantic versioning** → Uses `packaging` library  
✅ **GitHub integration** → Works seamlessly with GitHub Releases  

## Technical Details

### Version Detection Flow

```
┌─────────────────────────────────────────┐
│  UpdateConfig.get_current_version()     │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  Try: Read from pyproject.toml          │
│  - Look for 'version = "x.y.z"' line    │
│  - Parse and extract version string     │
└─────────────────┬───────────────────────┘
                  │
                  ├──── Found? ──────► Return version
                  │
                  └──── Not found? ───► Return fallback "1.0.0"
```

### Update Check Flow

```
┌─────────────────────────────────────────┐
│  User opens app                         │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  Should check for updates?              │
│  - Check if enabled                     │
│  - Check if interval elapsed            │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  Query GitHub API:                      │
│  /repos/USER/REPO/releases/latest       │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  Parse response:                        │
│  - Extract tag_name (e.g., "v1.0.1")   │
│  - Strip 'v' prefix                     │
│  - Extract download URLs                │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  Compare versions:                      │
│  version.parse(remote) > version.parse(current) │
└─────────────────┬───────────────────────┘
                  │
                  ├──── Newer? ────────► Show update dialog
                  │
                  └──── Same/Older? ───► Do nothing
```

## Related Files

- `app/config.py` → `UpdateConfig` class with version detection
- `app/update_checker.py` → `UpdateChecker` class with GitHub API integration
- `ArgoLogViewer.spec` → PyInstaller spec with version reading
- `pyproject.toml` → **Single source of truth for version**

---

**Last Updated:** January 2026  
**Author:** Harshmeet Singh
