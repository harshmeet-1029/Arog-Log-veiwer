# Disk Buffering — How It Works

> **Applies to:** Unlimited log mode only.  
> In Limited mode `setMaximumBlockCount` is used instead — no temp file, no disk buffering.

---

## What It Does (User View)

When you stream pod logs in **Unlimited mode**, every line is automatically saved to a
temporary file on disk. This gives you three things:

| Capability | How |
|---|---|
| **Scroll back to older logs** | "Load Older" bar appears at the top of the log view |
| **Save the full session** | "Save All Logs" saves from disk, not just what's visible |
| **Load everything at once** | "Load All" button pulls every line from disk into the viewer |

The temp file is deleted automatically when you switch pods or close the app.

---

## Architecture

### 1. Temp File

| Property | Value |
|---|---|
| Location | `{system temp dir}/argo_log_viewer_buffers/logs_{pod}_{pid}.txt` |
| Max size | **500 MB** — writes stop automatically above this; streaming continues |
| Encoding | UTF-8 |
| Write buffer | 8 KB (OS-level buffering) |

### 2. RAM Cache — SSD Wear Protection

Lines are **not** written to disk one at a time. They accumulate in
`_disk_buffer_ram_cache` (a Python list) and are flushed every **100 batches**.
This dramatically reduces write syscalls.

```
Incoming log batch
    → _disk_buffer_ram_cache.append(text)
    → if len(cache) >= 100:
          write entire cache to disk in one call
          cache.clear()
```

`_disk_buffer_cache_size = 100` (fixed, not user-configurable).

### 3. UI Trim — Configurable Threshold

The visible `QTextEdit` is kept to at most **`ui_trim_threshold`** lines
(default **100,000**, user-configurable, hard cap **100,000**).

When `doc.blockCount() > ui_trim_threshold`:

1. The oldest `max(1000, threshold // 10)` lines are removed from the QTextEdit.
2. `_ui_start_line` advances by the same amount.
3. The **"Load Older"** bar appears at the top of the log view.
4. The pod label updates: e.g. `my-pod │ 120,000 lines on disk (showing 10,001–120,000)`.

The disk file is **never affected** — all lines remain there.

### 4. Load Older Bar

Appears automatically when `_ui_start_line > 0`.

| Button | Behaviour |
|---|---|
| `Load 10,000 Older Lines` | Prepends the previous chunk from disk into the viewer |
| `Load All` | Reads every line from disk and inserts into the viewer |

**Load All warning:** if `total_lines_on_disk > ui_trim_threshold` the user sees a
confirmation dialog showing line count, file size, and estimated RAM usage before
proceeding. This is intentional — loading hundreds of thousands of lines on the main
thread can freeze the UI for several seconds.

### 5. Line Counter Variables

| Variable | Meaning |
|---|---|
| `_disk_log_lines_count` | Total lines written to disk in this session |
| `_ui_start_line` | Disk index of the first line currently shown in the viewer |
| `_ui_end_line` | Disk index of the last line currently shown |
| `_ui_lines_count` | Current `doc.blockCount()` |

### 6. Cleanup

| Event | Action |
|---|---|
| User switches pod | `_close_disk_buffer()` — flushes RAM cache, closes file |
| App exits normally | `_close_disk_buffer()` + deletes temp files older than 1 hour |
| App crashes | Temp files remain; cleaned up automatically on next launch |

---

## Data Flow (Unlimited Mode)

```
Kubernetes log line arrives
        │
        ▼
_process_log_output_batch()
        │
        ├─► STEP 1 — disk write (SSD-friendly batching)
        │       RAM cache.append(line)
        │       if len(cache) >= 100:
        │           write cache to disk file
        │           cache.clear()
        │
        ├─► STEP 2 — append to QTextEdit
        │
        └─► STEP 3 — UI trim check
                threshold = AppConfig.get_ui_trim_threshold()
                if QTextEdit.blockCount() > threshold:
                    trim = max(1000, threshold // 10)
                    remove oldest `trim` lines from QTextEdit
                    _ui_start_line += trim
                    show "Load Older" bar
```

---

## User-Configurable Setting — `ui_trim_threshold`

### What it controls

1. **When the viewer starts trimming** — older lines are pushed out of view and onto disk.
2. **When "Load All" shows its warning dialog** — if total disk lines exceed the threshold,
   the user is warned before loading everything into memory.

### Trade-off

| Lower value (e.g. 10,000) | Higher value (e.g. 100,000) |
|---|---|
| Less RAM used | More RAM used |
| "Load Older" appears more often | Longer scroll history without clicking "Load Older" |
| Lower risk of UI freeze on "Load All" | Higher risk of freeze on "Load All" |

### Limits

| | Value | Reason |
|---|---|---|
| **Default** | 100,000 | Matches the original hardcoded value; works well for most systems |
| **Min** | 100 | Practical floor — below this the viewer would trim every few lines |
| **Max** | 100,000 (hard cap) | Above this, RAM usage and "Load All" freeze risk become unacceptable |

### Where to change it

**Settings → Advanced Settings → Scroll-back && Full Save**

- **Default — 100,000 lines (recommended):** uses the hard cap; no config written.
- **Custom:** enter any value between 100 and 100,000. Saved as `ui_trim_threshold`
  in `~/.argo-log-viewer/config.json`.

Config key: `ui_trim_threshold`  
Config class: `AppConfig.get_ui_trim_threshold()` / `AppConfig.set_ui_trim_threshold(n)`

---

## What Is NOT Configurable (By Design)

| Thing | Why fixed |
|---|---|
| 500 MB max file size | Safety cap — prevents runaway disk usage |
| RAM cache flush interval (100 batches) | SSD protection — changing it offers no user benefit |
| Disk buffering on/off | Always on in Unlimited mode; no temp file in Limited mode |
| Temp file location | OS temp dir is correct; cleaned up automatically |
| Trim chunk size | Always `max(1000, threshold // 10)` — 10 % of threshold |

---

## Known Limitation

`_load_all_logs()` reads the disk file in 50,000-line chunks and calls
`cursor.insertText()` in a loop on the **main GUI thread**. For very large sessions
(500k+ lines) this can freeze the window for several seconds. The warning dialog before
"Load All" exists precisely to set that expectation.
