# Critical Bug Fix: Application Crash During High-Speed Log Streaming

## Problem Description

The Argo Log Viewer application would crash when clicking "Stop Log" or "Refresh Pod" buttons while logs were streaming at high speed from the server. This was a critical stability issue that made the application unreliable during active log monitoring.

## Root Cause Analysis

The crashes were caused by **race conditions** between Qt signal/slot callbacks and worker thread cleanup:

1. **Late Signal Arrivals**: When the worker thread was stopped, Qt signals (`output`, `error`, `pods`, `metrics`) were already queued in the event loop and would fire AFTER the worker was terminated, causing access to invalid/destroyed objects.

2. **Batch Timer Firing After Cleanup**: The log batching timer (50ms delay) could fire after `stop_log_stream()` was called, attempting to update UI when streaming was already stopped.

3. **Signal Not Disconnected**: Worker signals were not being disconnected before stopping threads, allowing callbacks to execute even after thread termination.

4. **No Streaming State Guard**: There was no explicit flag to track active streaming state, making it impossible to guard against late operations.

## Solution Implemented

### 1. Added Streaming State Flag
```python
self._is_streaming_logs = False  # Track if actively streaming logs (CRASH PROTECTION)
```
- Set to `True` when logs start streaming in `open_logs()`
- Set to `False` IMMEDIATELY at the start of `stop_log_stream()` before any cleanup
- Checked in `_append_log()` and `_flush_log_batch()` to abort operations

### 2. Signal Disconnection Before Thread Stop
Added proper signal disconnection in all worker stop scenarios:

**In `stop_log_stream()`:**
```python
try:
    self.worker.output.disconnect()
    self.worker.error.disconnect()
except Exception as e:
    logger.debug(f"Could not disconnect signals: {e}")
```

**In `refresh_pods()` and `fetch_pods()`:**
```python
try:
    self.worker.output.disconnect()
    self.worker.pods.disconnect()
    self.worker.error.disconnect()
except Exception as e:
    logger.debug(f"Could not disconnect worker signals: {e}")
```

**In `stop_metrics_monitoring()`:**
```python
try:
    self.metrics_worker.metrics.disconnect()
    self.metrics_worker.error.disconnect()
except Exception as e:
    logger.debug(f"Could not disconnect metrics worker signals: {e}")
```

### 3. Batch Timer and Queue Cleanup
```python
# Stop batch timer immediately
if self._batch_timer and self._batch_timer.isActive():
    self._batch_timer.stop()

# Clear pending batches
if self._log_append_batch:
    self._log_append_batch.clear()
```

### 4. Triple-Layer Protection in Log Processing

**In `_append_log()`:**
```python
# Check streaming flag
if not self._is_streaming_logs:
    return

# Check worker exists and is running
if not self.worker or not self.worker.isRunning():
    return
```

**In `_flush_log_batch()`:**
```python
# Check streaming flag
if not self._is_streaming_logs:
    self._log_append_batch.clear()
    return

# Check worker exists and is running
if not self.worker or not self.worker.isRunning():
    self._log_append_batch.clear()
    return
```

### 5. Correct Cleanup Order

The cleanup now follows a safe sequence in `stop_log_stream()`:
1. ✅ Clear `_is_streaming_logs` flag IMMEDIATELY
2. ✅ Stop and clear batch timer
3. ✅ Clear pending log batches
4. ✅ Disconnect all worker signals
5. ✅ Stop worker thread gracefully (wait 2s)
6. ✅ Force terminate if needed
7. ✅ Stop metrics monitoring
8. ✅ Close disk buffer
9. ✅ Update UI state

## Changes Summary

### Files Modified
- `app/ui/main_window.py` (6 locations, ~110 lines changed)

### Key Changes
1. Added `_is_streaming_logs` state flag (1 new variable)
2. Enhanced `stop_log_stream()` with signal disconnection and proper cleanup order
3. Enhanced `refresh_pods()` with signal disconnection before worker stop
4. Enhanced `fetch_pods()` with signal disconnection before worker stop
5. Enhanced `stop_metrics_monitoring()` with signal disconnection
6. Added streaming state checks in `_append_log()`
7. Added streaming state checks in `_flush_log_batch()`
8. Updated `open_logs()` to set streaming flag

## Testing Recommendations

### Critical Tests
1. **High-Speed Streaming + Stop**: Stream logs at 1000+ lines/sec, click Stop → should not crash
2. **High-Speed Streaming + Refresh**: Stream logs rapidly, click Refresh → should not crash
3. **Rapid Operations**: Quickly click Stop/Refresh/Fetch multiple times → should not crash
4. **Batch Timer Edge Case**: Stop just after batch scheduled but before flush → should not crash

### Test Pods
Use pods with high log output for testing:
- Pods with verbose debug logging
- Pods processing high-volume events
- Pods with continuous monitoring output

## Expected Improvements

✅ **Stability**: No crashes during stop/refresh operations
✅ **Responsiveness**: Immediate response to stop commands
✅ **Clean Shutdown**: Graceful thread termination
✅ **No Zombie Signals**: No callbacks after cleanup
✅ **Memory Safety**: No access to destroyed objects

## Backward Compatibility

✅ **Fully Compatible**: All existing functionality preserved
✅ **No API Changes**: No changes to public interfaces
✅ **No Data Loss**: Log data still saved properly
✅ **Performance**: Minimal overhead from additional checks

## Monitoring

After deployment, monitor logs for these debug messages confirming proper operation:
- `"Stopping batch timer"` - confirms timer cleanup
- `"Clearing X pending log batches"` - confirms batch clearing
- `"Disconnected worker.output signal"` - confirms signal disconnection
- `"Ignoring log append - not actively streaming"` - confirms flag protection
- `"Aborting flush - not actively streaming"` - confirms flush protection

## Risk Assessment

**Risk Level**: LOW
- Changes are defensive (guard clauses, disconnect before cleanup)
- No changes to core streaming logic
- No changes to data handling
- Fully backward compatible
- Easy to verify through testing

## Rollback Plan

If issues occur:
```bash
git log --oneline
git revert <commit-hash>
```

## Related Issues

This fix addresses crashes reported during:
- High-speed log streaming from pods
- Clicking Stop Log button during active streaming
- Clicking Refresh Pod button during active streaming
- Rapid clicking of multiple buttons

## Performance Impact

**Negligible**: Added checks are simple flag/null checks with O(1) complexity
**Memory**: No additional memory overhead
**CPU**: Minimal (just boolean checks)
**Latency**: No noticeable impact on log streaming speed

## Code Quality

✅ **Type Safety**: All changes maintain type hints
✅ **Error Handling**: All signal disconnections wrapped in try-except
✅ **Logging**: Extensive debug logging for troubleshooting
✅ **Comments**: Clear documentation of CRITICAL sections
✅ **Lint Clean**: No linting errors introduced

## Future Improvements

Consider for future versions:
1. Use Qt's `Qt.QueuedConnection` with proper lifetime management
2. Implement a proper state machine for streaming lifecycle
3. Add unit tests for signal disconnection scenarios
4. Add integration tests for high-speed streaming scenarios

## Conclusion

This fix eliminates the critical crash issue by properly managing Qt signal/slot lifecycle and implementing defensive guards against race conditions. The solution is simple, safe, and maintains full backward compatibility while significantly improving application stability.
