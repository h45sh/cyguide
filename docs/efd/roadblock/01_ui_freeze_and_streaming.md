# Roadblock 01: UI Freezing & Output Streaming Delay

## 1. The Symptoms
*   **Total UI Freeze**: During tool execution, the TUI became unresponsive. Buttons could not be clicked, and the screen did not refresh.
*   **Queued Events**: Mouse clicks made during the freeze would "fire" all at once after the tool finished.
*   **Batch Output**: Instead of streaming line-by-line, the entire tool output was "pushed" to the screen only after execution was complete.
*   **Termination Failure**: The **STOP** button was useless because the event loop was too busy to process the click.

---

## 2. Root Cause Analysis (The "Triple Threat")

### A. Quadratic Markup Parsing ($O(N^2)$)
*   **Cause**: Textual's `Static` widget parses Rich Markup (e.g., `[bold]`) by default.
*   **Problem**: On every line of output, we were calling `update()` with the *entire accumulated log*. Textual re-parsed the whole string every time. As the log grew, the time spent parsing increased quadratically, eventually taking longer than the time between lines.
*   **Result**: The UI thread was 100% occupied by string parsing.

### B. Event Loop Starvation
*   **Cause**: The `Executor` and UI callbacks were running in a tight loop without yielding.
*   **Problem**: `asyncio` requires explicit `await` points to switch tasks. Because the parsing/updating was so heavy, the loop never had a chance to process the UI "Paint" or "Input" events.
*   **Result**: The application was technically "running" but logically "frozen."

### C. Process Block-Buffering
*   **Cause**: OS-level pipe behavior.
*   **Problem**: When a tool like `nmap` detects its output is redirected to a pipe (not a TTY), it switches from line-buffering to block-buffering (usually 4KB chunks).
*   **Result**: Python's `readline()` would hang until a full 4KB block was filled, leading to "bursty" output.

---

## 3. The Solution Path

### Step 1: Efficient Buffering
*   **Method**: Switched `log_buffer` from a `str` to a `list`.
*   **Reason**: Appending to a list is $O(1)$, while string concatenation (`+=`) is $O(N)$ because it recreates the string in memory every time.

### Step 2: UI Throttling & Disabling Markup
*   **Method**: 
    1. Set `markup=False` on the raw output widget.
    2. Implemented a `UPDATE_INTERVAL` (0.05s) to cap UI refreshes at 20 FPS.
*   **Reason**: Stripping the parsing overhead and reducing the frequency of `update()` calls freed up the CPU for other tasks.

### Step 3: Textual Workers (`@work`)
*   **Method**: Wrapped `run_scan` in the `@work(exclusive=True)` decorator.
*   **Reason**: This moves the execution logic into a managed background task.
*   **Note**: This introduced a `TypeError: 'Worker' object can't be awaited`. Workers are managed by the framework and should be called without `await`.

### Step 4: Cooperative Multitasking
*   **Method**: Added `await asyncio.sleep(0)` in the UI update logic and `await asyncio.sleep(0.01)` in the `Executor` loops.
*   **Reason**: This forces the code to "pause" and let the Textual event loop process its message queue (handling mouse clicks and screen paints).

### Step 5: Persistent DB Connections
*   **Method**: Refactored `GraphStore` to use a persistent `aiosqlite` connection.
*   **Reason**: Opening/closing the database file for every single port found by a scanner was causing massive Disk I/O wait times, further slowing the event loop.

### Step 6: Safe Process Termination
*   **Method**: Used `pop(session_id, None)` instead of `del self._active_processes[session_id]`.
*   **Reason**: Prevented a `KeyError` when the user clicked **STOP** on a scan that had just finished. In an async environment, race conditions between the tool finishing naturally and the user manually stopping it are common.

---

## 4. Final Verdict
The fix required a multi-layered approach: **Infrastructure** (Persistent DB), **Logic** (Async yielding), **Data Structures** (List buffering), and **UI Optimization** (Throttling + Markup disabling). The system now maintains 60fps responsiveness even while processing high-volume scanner output.
