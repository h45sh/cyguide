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

### 7. Upstream Textual Text-Selection Race & Markdown Tables (Technical Debt)
* **The Roadblock**: Clicking inside rapidly streaming Markdown documents (such as during AI tutor explanations with tables in Learning Mode) triggered `AttributeError: 'NoneType' object has no attribute 'region'` inside Textual's `Screen._forward_event`.
* **Root Cause**: Textual assumes `content_widget.parent` is always non-None when calculating container text-selection bounds. When clicking on unmounting nodes or grid containers (`MarkdownTableContent`), `parent` evaluates to `None`, terminating the application. Additionally, calling `Markdown.update()` unawaited at 50ms intervals caused overlapping tasks to contend on `Markdown.lock`, dumping unretrieved `CancelledError` warnings to the terminal.
* **The Workaround (`cyguide/ui/compat.py`)**:
  1. Disabled `ALLOW_SELECT` on `MarkdownTableContent` so container grids do not trigger container offset calculations (cell contents remain selectable).
  2. Wrapped `Screen._forward_event` to safely catch `AttributeError` on `NoneType.region`, clearing `_select_state` and passing raw events directly.
  3. Throttled explanation streaming to 250ms and explicitly awaited `explainer_pane.update()` in `LearningModeScreen`.
* **Decommissioning Criteria**: This technical debt can be retired once upstream Textual implements defensive null checks (`if container is not None:`) before evaluating `container.region` in `_forward_event`. Tracked and verified via `tests/unit/test_textual_compat.py`.

### 8. High-Velocity Terminal Virtualization (`TerminalStreamPane`)
* **The Roadblock**: Standard `RichLog` widgets store rendered output lines as full Rich `Strip` objects. High-frequency scanners (such as `ffuf` or `nuclei` emitting 10,000+ lines per second) flooded Textual's async message queue and caused catastrophic RAM bloat (exceeding 800 MB on long scans) and main thread starvation.
* **The Architecture (`cyguide/ui/widgets/terminal_stream.py`)**:
  1. **$O(1)$ Staging Queue**: Raw subprocess stdout chunks append directly to an in-memory list without Rich parsing on arrival.
  2. **30 FPS Micro-Batch Cadence**: A 30 Hz timer flushes accumulated chunks in atomic batches, preserving terminal responsiveness at a stable 60 FPS.
  3. **Bounded Ring Buffer**: A `collections.deque(maxlen=5000)` strictly clamps in-memory lines, keeping steady-state UI heap consumption under 3 MB.
  4. **Viewport Virtualization**: `render_line(y)` renders only the visible rows on the terminal viewport rather than building DOM elements for off-screen lines.
  5. **Direct Disk Spooling**: The async executor streams complete, uncapped output directly to `data/logs/{action_id}.log` for forensic completeness.

### 9. Tree DOM Virtualization & In-Place Identity Caching (`EntityBrowser`)
* **The Roadblock**: Under high finding influx (e.g. multi-subnet port sweeps yielding 1,000+ hosts and services), calling `self.clear()` on Textual's `Tree` widget on every finding destroyed and rebuilt thousands of `TreeNode` widgets, freezing the interface for 500ms+ per update.
* **The Optimization (`cyguide/ui/widgets/power.py`)**:
  1. **Identity Cache Fast-Path**: If the graph snapshot data and active search query are unchanged, `refresh_entities()` immediately returns in sub-1ms, skipping DOM reconstruction entirely.
  2. **Category Capping**: Capped maximum visible child nodes per category (`Targets`, `Services`, `Web`) to 200 items, appending a summary overflow leaf (`… X more (filter with search)`).
  3. **State Preservation**: Persisted user expanded/collapsed branch keys across background store updates.

### 10. Micro-Wordlist Compression & Vendoring Strategy
* **The Roadblock**: Bundled micro-wordlists (`subdomains_500.txt`, `common_params.txt`, etc.) contributed 6,318 lines of raw text, inflating Git lines-of-code statistics and cluttering pull request review diffs.
* **The Solution (`cyguide/engine/wordlists.py`)**:
  1. **`.gitattributes` Vendoring**: Added `linguist-vendored=true` and `-diff` to suppress wordlist assets from GitHub language analytics and git diff calculations.
  2. **Gzip Compressed Archives**: Wordlists are packaged as `.txt.gz` inside the Python wheel (~78% size reduction).
  3. **Transparent Runtime Extraction**: `seed_bundled_wordlists()` stream-decompresses `.txt.gz` archives into the user's `~/.cyguide/wordlists/*.txt` directory on initial run with `0o600` permissions.

---

## 3. General Developer Lessons

*   **Defensive Imports**: Libraries like `pyperclip` (for copying text to clipboard) can fail to import on headless Linux machines or systems without X11. Always wrap clipboard commands in `try/except ImportError` blocks so that missing secondary features do not crash the primary application.
*   **CSS Dialects**: Terminals do not support web-based fonts or normal layouts. Standard CSS rules like `font-family` or `font-style: italic` fail or raise errors in Textual. Use framework-specific rules like `text-style: italic`.
