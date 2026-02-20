# Save Logs Fix - Double Line Breaks Issue

## Problem Description

When saving logs using the "Save Logs" button, the saved file contained **double line breaks** (blank lines) between each log entry. This made the saved logs harder to read and doubled the file size unnecessarily.

### Example:
**Before Fix** (saved .txt file):
```
kubectl logs pod-name -n argo -f

[INFO] Streaming logs...

time="2026-02-20T13:36:58.462Z" level=info msg="capturing logs"

{"asctime": "2026-02-20 13:36:58,710", "levelname": "DEBUG"}
```

**Expected** (manual copy-paste):
```
kubectl logs pod-name -n argo -f
[INFO] Streaming logs...
time="2026-02-20T13:36:58.462Z" level=info msg="capturing logs"
{"asctime": "2026-02-20 13:36:58,710", "levelname": "DEBUG"}
```

## Root Cause

Qt's `toPlainText()` method treats each text block in the QTextEdit document as a **paragraph**. When converting to plain text, it adds an extra newline between paragraphs, resulting in double line breaks.

The issue occurred in two places:
1. `save_logs_to_file()` - when saving logs from UI (line 1582)
2. `_copy_all_logs()` - when copying all logs to clipboard (line 1845)

## Solution

Instead of using `toPlainText()`, we now **manually iterate through the text document blocks** and join them with single newlines:

```python
# OLD (WRONG):
log_content = self.log_output.toPlainText()

# NEW (CORRECT):
document = self.log_output.document()
blocks = []
block = document.begin()
while block.isValid():
    blocks.append(block.text())
    block = block.next()
log_content = "\n".join(blocks)
```

This ensures that each text block is joined with exactly **one newline**, preserving the original log formatting.

## Changes Made

### 1. Fixed `save_logs_to_file()` method
**File**: `app/ui/main_window.py`, lines ~1576-1595

- Replaced `toPlainText()` with manual block iteration
- Applies when saving logs from UI (when disk buffer is not available)
- Preserves original log formatting without extra line breaks

### 2. Fixed `_copy_all_logs()` method
**File**: `app/ui/main_window.py`, lines ~1841-1857

- Replaced `toPlainText()` with manual block iteration
- Applies when copying all logs to clipboard
- Ensures clipboard content matches the visual log display

## Impact

### ✅ Benefits:
- **Correct Formatting**: Saved logs now match the original format exactly
- **Smaller File Size**: Eliminates unnecessary blank lines (roughly 50% reduction)
- **Consistency**: Saved files now identical to manually copy-pasted logs
- **Better Readability**: No confusing blank lines between log entries

### 🔍 Scope:
- Affects only UI-based log saving (when disk buffer not used)
- Disk buffer saves were already correct (direct file copy)
- No changes to log streaming or display functionality

## Testing Recommendations

1. **Save from UI** (limited logs mode):
   - Connect to server
   - View pod logs
   - Click "Save Logs" button
   - Verify no blank lines between log entries

2. **Save from Disk Buffer** (unlimited logs mode):
   - Enable unlimited logs in Settings → Advanced
   - Stream logs for extended period
   - Click "Save Logs" button
   - Verify complete logs with correct formatting

3. **Copy to Clipboard**:
   - View pod logs
   - Right-click → "Copy All Logs"
   - Paste into text editor
   - Verify no blank lines between entries

## Related Issues

This fix complements the recent crash fix (commit 70dc0bb) which resolved:
- Application crashes during high-speed log streaming
- Signal/slot race conditions when stopping streams

## Notes

- The disk buffer save functionality was already working correctly (uses direct file copy)
- This fix only affects saves from the Qt UI widget
- Search functionality was not affected (uses `document.find()` not `toPlainText()`)
- No performance impact (block iteration is O(n) same as `toPlainText()`)
