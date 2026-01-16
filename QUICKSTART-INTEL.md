# 🚀 Quick Start: Build Intel Binary (No Token!)

## Easiest Way - No GitHub Token Needed

Since this is a public repo, you can build and upload without any authentication setup:

### Step 1: Run GitHub Actions (Creates ARM64 Release)
1. Go to **Actions** tab
2. Run **Build macOS Application** workflow
3. Wait for completion

### Step 2: Build Intel on Your Mac (No Token!)
```bash
./build-intel-and-release.sh 1.0.0
```

### Step 3: Upload Files (Drag & Drop)
1. Script shows you the release URL
2. Click it (opens GitHub)
3. Scroll to "Attach binaries"
4. Drag and drop the DMG and ZIP files
5. Click "Update release"

**That's it!** No tokens, no API keys, no authentication hassles! 🎉

---

## Advanced: Auto-Upload (Optional)

If you want the script to upload automatically:

```bash
# Get token: https://github.com/settings/tokens
# Permission needed: public_repo
./build-intel-and-release.sh 1.0.0 ghp_yourtoken
```

But honestly? The manual drag-and-drop is easier for occasional releases.

---

**Full docs:** See [BUILD-INTEL.md](BUILD-INTEL.md)
