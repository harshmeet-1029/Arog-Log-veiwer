# Intel Mac Build Instructions

This document explains how to build and release Intel (x86_64) binaries from your local Intel Mac.

## Why This Script?

GitHub Actions charges for Intel Mac runners (`macos-15-intel`). To avoid costs, the CI/CD workflow only builds **ARM64** binaries automatically. Intel builds are done manually from your local Intel Mac using this script.

## Prerequisites

1. **Intel Mac** running macOS 14 or later
2. **Python 3.11** installed
3. **Git** with repository cloned
4. **GitHub Personal Access Token** (optional - for auto-upload)

## Two Modes

### Mode 1: Build + Manual Upload (No Token Required)
Just build the files, then drag-and-drop to GitHub UI:

```bash
./build-intel-and-release.sh 1.0.0
```

Then manually upload the generated DMG and ZIP files through GitHub's web interface.

### Mode 2: Build + Auto Upload (Token Required)
Automatically upload to release using GitHub API:

```bash
./build-intel-and-release.sh 1.0.0 ghp_yourtoken
```

## Getting a GitHub Token

1. Go to https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. Give it a name like "ArgoLogViewer Intel Build"
4. Select scope: `repo` (Full control of private repositories)
5. Click "Generate token"
6. **Copy the token** (starts with `ghp_`)

## Usage

### Step 1: Run GitHub Actions First

Before running the local script, **create the ARM64 release** via GitHub Actions:

1. Go to your repository → Actions → "Build macOS Application"
2. Click "Run workflow"
3. Enter version number (e.g., `1.0.0`)
4. Select "Create GitHub Release: true"
5. Wait for it to complete

This creates the release with ARM64 binaries.

### Step 2: Build Intel Binaries

On your **Intel Mac**:

#### Option A: Build Only (No Token - Easiest)

```bash
# Make script executable (first time only)
chmod +x build-intel-and-release.sh

# Build Intel binaries
./build-intel-and-release.sh 1.0.0
```

Then manually upload:
1. Go to: https://github.com/yourusername/argo-log-viewer/releases/edit/v1.0.0
2. Scroll to "Attach binaries" section
3. Drag and drop the generated DMG and ZIP files
4. Click "Update release"

#### Option B: Build + Auto Upload (With Token)

```bash
# Get token from: https://github.com/settings/tokens (needs 'public_repo' permission)
./build-intel-and-release.sh 1.0.0 ghp_yourtoken
```

Or use environment variable:

```bash
export GITHUB_TOKEN=ghp_yourtoken
./build-intel-and-release.sh 1.0.0
```

### What the Script Does

1. ✅ Verifies you're on an Intel Mac
2. ✅ Installs Python dependencies
3. ✅ Creates macOS icon (.icns)
4. ✅ Builds Intel x86_64 binary with PyInstaller
5. ✅ Verifies the binary architecture
6. ✅ Creates DMG installer
7. ✅ Creates ZIP archive
8. ✅ Generates SHA-256 checksums
9. ✅ Uploads to GitHub release (if token provided) OR shows manual upload instructions

## Output

The script produces:

- `ArgoLogViewer-v{VERSION}-macOS-Intel.dmg` - DMG installer
- `ArgoLogViewer-v{VERSION}-macOS-Intel.zip` - ZIP archive
- `checksums-intel.txt` - SHA-256 checksums

All files are automatically uploaded to the GitHub release.

## Troubleshooting

### Error: "Release does not exist"

**Solution:** Run the GitHub Actions workflow first to create the release with ARM64 binaries.

### Error: "Could not detect GitHub repository"

**Solution:** Make sure you're in the git repository directory:
```bash
cd /path/to/argo-log-viewer
./build-intel-and-release.sh 1.0.0
```

### Error: "Binary is not x86_64"

**Solution:** You might be on an ARM Mac. This script requires an Intel Mac. If you only have ARM, you'll need to:
- Use GitHub Actions with `macos-15-intel` (paid)
- Or only provide ARM64 builds (Intel users use Rosetta 2)

### Permission Denied

**Solution:** Make the script executable:
```bash
chmod +x build-intel-and-release.sh
```

## Cleanup

After successful upload, clean up build artifacts:

```bash
rm -rf build dist *.dmg *.zip *.txt app/icon.icns
```

## Security Notes

- **Never commit** your GitHub token to git
- Store tokens securely (password manager or keychain)
- For public repos, you only need `public_repo` permission (not full `repo`)
- Token is only needed for auto-upload - manual upload through GitHub UI doesn't need a token
- Tokens in bash history: Clear with `history -c` after use

## Alternative: Environment Variable

For better security, use environment variables:

```bash
# Add to ~/.zshrc or ~/.bash_profile
export GITHUB_TOKEN=ghp_yourtoken

# Then just run:
./build-intel-and-release.sh 1.0.0
```

## Questions?

Open an issue at: https://github.com/yourusername/argo-log-viewer/issues
