# Crash Fix Verification Test Plan

## Issue Fixed
Application crashed when clicking "Stop Log" or "Refresh Pod" while logs were streaming at high speed.

## Root Cause
Race conditions between Qt signal callbacks and thread cleanup, causing UI updates after worker threads were terminated.

## Changes Made

### 1. Added Streaming State Flag
- New flag `_is_streaming_logs` tracks active streaming state
- Set to `True` when logs start
- Set to `False` IMMEDIATELY when stopping (before any cleanup)

### 2. Signal Disconnection
Added proper signal disconnection in:
- `stop_log_stream()` - disconnects output and error signals
- `refresh_pods()` - disconnects output, pods, and error signals
- `fetch_pods()` - disconnects output, pods, and error signals  
- `stop_metrics_monitoring()` - disconnects metrics and error signals

### 3. Batch Processing Protection
- Batch timer stopped immediately when stopping stream
- Pending batches cleared to prevent late UI updates
- `_append_log()` checks streaming flag before processing
- `_flush_log_batch()` checks streaming flag before flushing

### 4. Order of Operations
Cleanup now follows safe sequence:
1. Clear `_is_streaming_logs` flag
2. Stop and clear batch timer
3. Clear pending batches
4. Disconnect all signals
5. Stop worker thread
6. Wait for graceful shutdown (or terminate if needed)
7. Cleanup UI elements

## Test Scenarios

### Test 1: High-Speed Log Streaming + Stop
**Steps:**
1. Connect to server
2. Open logs for a pod with VERY high log output (1000+ lines/sec)
3. Wait for logs to stream for 5-10 seconds
4. Click "Stop Log" button while logs are actively streaming
5. Verify no crash occurs
6. Verify logs stop cleanly
7. Verify UI remains responsive

**Expected Result:** ✅ No crash, clean stop, UI responsive

### Test 2: High-Speed Log Streaming + Refresh
**Steps:**
1. Connect to server
2. Open logs for a pod with high log output
3. Wait for logs to stream for 5-10 seconds
4. Click "Refresh" button while logs are actively streaming
5. Verify no crash occurs
6. Verify pod list refreshes successfully
7. Verify UI remains responsive

**Expected Result:** ✅ No crash, pod list refreshes, UI responsive

### Test 3: High-Speed Log Streaming + Pod Search
**Steps:**
1. Connect to server
2. Open logs for a pod with high log output
3. Wait for logs to stream
4. Enter search term and click "Fetch" while logs are streaming
5. Verify no crash occurs
6. Verify search completes successfully

**Expected Result:** ✅ No crash, search works, UI responsive

### Test 4: Rapid Operations
**Steps:**
1. Connect to server
2. Open logs for a pod with high output
3. Rapidly click: Stop → Refresh → Stop → Fetch → Stop
4. Verify no crashes during rapid operations

**Expected Result:** ✅ No crashes, operations complete cleanly

### Test 5: Log Streaming + Metrics Monitoring
**Steps:**
1. Connect to server
2. Open logs for a pod with high output
3. Start metrics monitoring
4. While both are active, click Stop
5. Verify both stop cleanly without crash

**Expected Result:** ✅ Both stop cleanly, no crash

### Test 6: Batch Timer Edge Case
**Steps:**
1. Connect to server
2. Open logs for a pod with moderate output (triggers batch timer)
3. Wait for batch timer to be scheduled (50ms delay)
4. Click Stop just after batch scheduled but before flush
5. Verify no crash when timer fires

**Expected Result:** ✅ Timer aborts cleanly, no crash

## Debug Verification

Check logs for these debug messages confirming proper operation:
- "Stopping batch timer" - confirms timer cleanup
- "Clearing X pending log batches" - confirms batch clearing
- "Disconnected worker.output signal" - confirms signal disconnection
- "Ignoring log append - not actively streaming" - confirms flag protection
- "Aborting flush - not actively streaming" - confirms flush protection

## Performance Impact

Expected improvements:
- ✅ No crashes during high-speed streaming
- ✅ Cleaner thread shutdown
- ✅ No zombie signals/callbacks
- ✅ Immediate response to stop commands
- ✅ No memory leaks from orphaned signals

## Files Modified

- `app/ui/main_window.py`:
  - Added `_is_streaming_logs` flag
  - Enhanced `stop_log_stream()` with signal disconnection
  - Enhanced `refresh_pods()` with signal disconnection
  - Enhanced `fetch_pods()` with signal disconnection
  - Enhanced `stop_metrics_monitoring()` with signal disconnection
  - Added protection checks in `_append_log()`
  - Added protection checks in `_flush_log_batch()`
  - Updated `open_logs()` to set streaming flag

## Rollback Plan

If issues occur, revert commit using:
```bash
git log --oneline  # Find commit hash
git revert <commit-hash>
```

## Post-Deployment Monitoring

Monitor for:
- Application crashes during log operations
- Thread cleanup warnings in logs
- UI freeze/hang during stop operations
- Memory leaks during extended streaming sessions
