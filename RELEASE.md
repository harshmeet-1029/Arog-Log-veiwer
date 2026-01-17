# How to Release a New Version

## Simple: Use GitHub UI

1. **Go to:** GitHub → Actions → "Build All Platforms"
2. **Click:** "Run workflow" button
3. **Enter:** Version number (e.g., `1.0.1`)
4. **Check:** ✅ "Create GitHub Release?"
5. **Click:** "Run workflow"
6. **Wait:** ~15 minutes
7. **Done!** 🎉

## What Happens Automatically

- ✅ Updates `pyproject.toml` with your version
- ✅ Builds Windows, macOS (Apple Silicon), Linux
- ✅ Commits version to main branch
- ✅ Creates git tag `v1.0.1`
- ✅ Creates GitHub Release
- ✅ Uploads all binaries
- ✅ Users get update notifications

## That's It!

No files to edit, no builds to run. Just enter the version in the UI and go!
