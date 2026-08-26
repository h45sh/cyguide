# Developer Notes: Real-time Streaming, UI Performance & Roadblocks

This document compiles the lessons learned, roadblocks, and architectural workarounds encountered during the development of CyGuide's async execution and TUI.

---

## 1. Async Streaming vs UI Freezing

### The Symptoms
Initially, when the executor ran a long scan (like an `nmap` execution taking 30 seconds), the Textual TUI would freeze completely. The screen did not repaint, mouse clicks were queued and fired in a burst after the tool finished, and the **STOP** button was unresponsive.

### Root Cause Analysis (The "Triple Threat")
1.  **Quadratic Markup Parsing ($O(N^2)$)**: Textual's `Static` widget parses Rich Markup (like `[bold]`) by default. Appending each line and calling `update()` with the *entire accumulated log* caused Textual to re-parse the whole text again. As logs grew, parsing time increased quadratically.
2.  **Event Loop Starvation**: Asyncio requires cooperative yielding. Running the process stdout reader loop and heavy UI updates in a tight synchronous loop starved the asyncio event loop, preventing it from handling UI paints or mouse clicks.
3.  **Process Block-Buffering**: When security tools detect their stdout is redirected to an OS pipe rather than a pseudo-terminal (TTY), they switch from line-buffering to block-buffering (typically 4KB). This caused Python's `readline()` to hang until a 4KB chunk was filled, leading to "bursty" output.

---

## 2. Performance Optimizations & Workarounds

### 1. Efficient Buffering
Switched the log accumulator from a string concatenation (`log += line`) to a list of lines (`log_list.append(line)`). String concatenation is $O(N)$ since it recreates the string in memory each time. Appending to a list is $O(1)$.

### 2. Throttling updates & Disabling Markup
1.  Set `markup=False` on the terminal logs output widget to disable Textual's Rich parsing.
2.  Throttled UI refreshes by capping them at 20 FPS (every 0.05 seconds) instead of repainting on every single stdout line.

### 3. Cooperative Multitasking (`asyncio.sleep`)
To prevent event loop starvation, we explicitly yield control to the loop using:
*   `await asyncio.sleep(0)` inside the UI update loops.
*   `await asyncio.sleep(0.01)` inside the process reader loops.
This allows Textual to process its message queue and repaint the terminal.

### 4. Textual Workers (`@work`)
Moved the tool adapter process runner into background tasks using Textual's `@work(exclusive=True)` decorator.
*   *Note*: When launching workers, call them directly without `await` to avoid `TypeError: 'Worker' object can't be awaited`. Textual handles worker scheduling internally.

### 5. Persistent DB Connections
Initially, opening and closing the SQLite file for every single port or vulnerability found caused heavy Disk I/O waits, blocking the async event loop. We refactored `GraphStore` to use a persistent, long-running connection (`aiosqlite` connection pool) which is initialized on mount and closed on unmount.

### 6. Safe Process Termination
When a user terminates a scan, race conditions can occur if the process completes naturally at the exact same moment. We replaced direct dict deletions (`del self._active_processes[session_id]`) with safe pops (`self._active_processes.pop(session_id, None)`) to prevent unhandled `KeyErrors` during termination.

---

## 3. General Developer Lessons

*   **Defensive Imports**: Libraries like `pyperclip` (for copying text to clipboard) can fail to import on headless Linux machines or systems without X11. Always wrap clipboard commands in `try/except ImportError` blocks so that missing secondary features do not crash the primary application.
*   **CSS Dialects**: Terminals do not support web-based fonts or normal layouts. Standard CSS rules like `font-family` or `font-style: italic` fail or raise errors in Textual. Use framework-specific rules like `text-style: italic`.
