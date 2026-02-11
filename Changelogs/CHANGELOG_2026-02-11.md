# Changelog - February 11, 2026

Detailed log of updates, fixes, and improvements made to the Argo Log Viewer application.

## 🛠️ Stability & Crash Reporting

### 1. Crash Reporting System (Local Only)
- **Problem:** The application was crashing silently without leaving logs, making debugging impossible.
- **Solution:** 
  - Implemented a global `exception_hook` in `app/main.py` to catch all unhandled exceptions.
  - Configured the logging system to **force file logging** even when running as a compiled `.exe` (previously it only logged to console, which disappears on crash).
  - Updated `logging_config.py` to robustly determine the correct log directory (`logs/` in project root for dev, user home for installed app).
  - Added a "Critical Error" popup dialog to inform the user when a crash is caught.

### 2. Stability Fixes (Feature Rollback)
- **Problem:** Frequent crashes were traced to multi-threaded operations and resource contention.
- **Solution:**
  - **Re-enabled Metrics Monitoring:** The secondary SSH connection used for fetching real-time CPU/RAM usage has been re-enabled.
    - **CRASH PROOFING:** Metrics no longer auto-start. Users must click the refresh button (🔄) to initiate monitoring.
    - **Optimization:** Once started, metrics update every 10 seconds to minimize resource usage.
  - **Re-enabled OTA Updates:** Automatic update checking on startup has been re-enabled and verified to run in a background thread to prevent UI hangs.

### 3. Settings Reset Protection
- **Problem:** Resetting settings forced an immediate app closure, disrupting user workflow.
- **Solution:** 
  - Updated the "Reset to Defaults" dialog to offer two options: **"Restart Now"** (immediate) and **"Restart Later"** (keep working, changes apply on next launch).
  - Fixed a crash where the reset function tried to access a non-existent method `AppConfig.set_theme`.

## 🎨 UI/UX Improvements

### 1. "Find" Bar Enhancements
- **Problem:** The search bar was cramped, with small buttons that were hard to click.
- **Solution:**
  - Increased search input width from 200px to **300px**.
  - Increased button size (Prev/Next/Close) to **80x28px** for better usability.
  - Improved layout spacing and alignment.
  - Made the search logic smarter: clearer messages when text is not found (only suggests "Load Older Logs" if that button is actually visible).

### 2. "Limited Mode" Warnings
- **Problem:** Users might accidentally use "Limited Mode" and lose important log history without realizing it.
- **Solution:**
  - Added a **bright orange warning** in "Advanced Settings" when "Limited Mode" is selected.
  - Added a console warning message whenever logs are opened in Limited Mode.
  - Added a warning to the **Save Logs** file export (both HTML and TXT) stating that the saved log is incomplete due to Limited Mode.

### 3. SpinBox Styling Fix
- **Problem:** The number input in settings had broken/invisible up/down arrows and a "dead zone" on the left side.
- **Solution:**
  - Created custom arrow icons (`_get_arrow_icon_path` in `themes.py`) that adapt to the active theme color.
  - Increased button click area to **25px**.
  - Fixed CSS alignment so buttons sit flush against the right edge with proper borders.

### 4. Light Mode Fixes
- **Problem:** The "About" dialog had invisible white text on a white background in Light Mode.
- **Solution:** 
  - Updated `_show_about_dialog` to explicitly set text colors (`#212121` for Light Mode, `#e0e0e0` for Dark Mode) ensuring readability in all themes.

### 5. Crash Fix (Theme System)
- **Problem:** Crash when entering Fullscreen mode due to a method name mismatch.
- **Solution:** Renamed `get_main_stylesheet` to `get_stylesheet` in `app/themes.py` and updated all references in `main_window.py` to match.

## 📝 Documentation

- Created this changelog to track all modifications.
- Verified that "Load Older Logs" button logic is correct (only appears in Unlimited Mode when buffer > 50k lines).

---
**Status:** The application is now stable, with critical crash reporting active and all reported UI/UX issues resolved.
