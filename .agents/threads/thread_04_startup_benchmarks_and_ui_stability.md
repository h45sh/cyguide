# Thread Insight: Startup Latency Optimization, Automated Benchmark Limits, and Modal Idempotency

- **Branch / PR**: `perf/benchmarks-and-startup-optimization` (PR #27) & `fix/ci-flaky-tests-and-runner-variance` (PR #28)
- **Primary Domain**: `[Benchmarks | Engine | Storage | UI | CI / Tooling]`
- **Author / Contributor**: `@h45sh`

---

## 1. Key Principles & Architectural Techniques Introduced

### 1.1. On-Demand Screen Loading & Dynamic PEP 562 Symbol Re-Exporting
- **The Problem**: Eagerly importing all secondary UI screens (`ToolBrowserScreen`, `LearningModeScreen`, `PowerModeScreen`, `ConfigModal`) in `cyguide/ui/screens/__init__.py` dragged the entire engine, widget trees, Markdown formatters, and network modules into the cold startup path.
- **The Seam**:
  - Implemented dynamic lazy screen factories in [`cyguide/ui/screens/lazy.py`](file:///home/harsh/Documents/cyguide/cyguide/ui/screens/lazy.py) using callable loaders registered in `CyGuideApp.SCREENS`.
  - Re-implemented [`cyguide/ui/screens/__init__.py`](file:///home/harsh/Documents/cyguide/cyguide/ui/screens/__init__.py) with PEP 562 `__getattr__` module-level dynamic resolution. This preserves 100% backward compatibility for imports (`from cyguide.ui.screens import PowerModeScreen`) while ensuring zero import penalty during CLI execution or Dashboard cold launch.
  - **Latency Impact**: Cut application cold start latency from ~950ms down to ~540ms (~43% reduction).

### 1.2. Decoupling Network/HTTP Stacks from Startup Paths
- **The Pitfall**: Basic utilities like `is_placeholder_key` were co-located in [`cyguide/engine/explainer.py`](file:///home/harsh/Documents/cyguide/cyguide/engine/explainer.py), pulling in `httpx`, `dotenv`, and heavy LLM client structures just to check an environment variable or display CLI version info.
- **The Seam**: Extracted lightweight primitives into [`cyguide/common/keys.py`](file:///home/harsh/Documents/cyguide/cyguide/common/keys.py), establishing a clean architectural boundary between credential syntax inspection and execution clients.

### 1.3. Atomic Micro-Batching in Graph Storage
- **The Technique**: Migrated session import and mass ingestion routines in [`cyguide/engine/store.py`](file:///home/harsh/Documents/cyguide/cyguide/engine/store.py) from sequential per-row `await db.execute()` loops to batched `await db.executemany()` operations inside isolated transactions.
- **Throughput**: 10,000 nodes, edges, and audit event logs ingest 2.7x faster (~2,400 entities/sec vs ~900 entities/sec).

### 1.4. Automated Limits Benchmarking & Regression Guard (`--check`)
- **The Architecture**: Created a comprehensive, self-contained performance suite:
  - [`scripts/benchmark_limits.py`](file:///home/harsh/Documents/cyguide/scripts/benchmark_limits.py): Standalone stress harness simulating real-world saturation (500k stream lines, 10k entities, 25k DOM nodes).
  - [`scripts/generate_benchmark_report.py`](file:///home/harsh/Documents/cyguide/scripts/generate_benchmark_report.py): Automated benchmark reporter rendering Markdown ([`docs/benchmarks/README.md`](file:///home/harsh/Documents/cyguide/docs/benchmarks/README.md)) and standalone HTML visualizations.
  - **Regression Gate**: Added `--check` mode to fail CI if cold launch, stream throughput, database writes, or DOM builds drop below specified guard bounds. Incorporated as Step 4 in [`scripts/release-check.sh`](file:///home/harsh/Documents/cyguide/scripts/release-check.sh).

### 1.5. CI Runner Cost Reduction & Concurrency Protection
- **Concurrency Control**: Added `concurrency: { group: "${{ github.workflow }}-${{ github.ref }}", cancel-in-progress: true }` to [`.github/workflows/ci.yml`](file:///home/harsh/Documents/cyguide/.github/workflows/ci.yml), automatically terminating obsolete matrix builds when rapid commits are pushed.
- **Path Filtering**: Added `paths-ignore` for `docs/**`, `*.md`, and `.gitignore` to eliminate unnecessary runner hours on documentation changes.
- **Isolated Benchmark Job**: Ran stress benchmarks on a single deterministic Ubuntu runner rather than redundantly spawning heavy stress benchmarks across every platform matrix node.

---

## 2. Non-Obvious Insights & Codebase Realities

### 2.1. Rapid Key Repeats & Modal `ScreenStackError`
- **The Reality**: When users hold down `F1`, `Escape`, or `Q`, modern OS keyboard repeat rates blast 20–30 key events per second into the TUI event queue.
- **The Bug**: In Textual, `Screen.dismiss()` and `App.pop_screen()` schedule screen removal asynchronously. If multiple repeat events are queued before the screen unmounts, subsequent dismiss calls execute on the newly exposed underlying screen (e.g., `DashboardScreen`). When the last screen is popped, Textual crashes with:
  `ScreenStackError: Can not pop screen; there is only one screen on the stack.`
- **The Fix**:
  - Implemented monkeypatched idempotency protection in [`cyguide/ui/compat.py`](file:///home/harsh/Documents/cyguide/cyguide/ui/compat.py):
    - `safe_screen_dismiss`: Verifies `self is stack[-1]`, sets a `_screen_dismissed` flag, and traps `ScreenStackError`.
    - `safe_app_pop_screen`: Verifies `len(stack) > 1` prior to popping.
  - Centralized shortcut actions across screens (`home.py`, `power.py`, `learning.py`, `tool_browser.py`) to delegate to `app.action_show_hotkeys()`, ensuring a single source of truth with `any(isinstance(s, ShortcutsDialog) for s in self._screen_stack)` deduplication.

### 2.2. Shared CI Runner Virtualization vs Microsecond Assertions
- **The Reality**: Operations running in 20–40ms on bare-metal NVMe machines regularly spike to 200–260ms on shared GitHub Actions runners (e.g. macOS arm64 and Ubuntu runners) due to hyperthreaded CPU contention and virtualized disk I/O scheduling.
- **The Fix**:
  - Hard assertions in test suites (e.g. [`tests/unit/test_benchmarks.py`](file:///home/harsh/Documents/cyguide/tests/unit/test_benchmarks.py)) must not set razor-thin limits like `< 100ms` for 5,000-entity operations.
  - Set CI guard limits to `< 500ms`. This prevents false-positive test flakes while maintaining a razor-sharp trap for actual $O(N^2)$ algorithmic regressions.

### 2.3. Asynchronous Debounce Synchronization in Pilot Unit Tests
- **The Reality**: Fixed calls like `await pilot.pause(0.05)` fail non-deterministically under slower test environments because debounce timers (`_ws_debounce_task`, `_sess_debounce_task`) are still in flight.
- **The Pattern**: In tests interacting with debounced list views, use a polling loop that explicitly checks `task.done()` and verifies DOM element presence before asserting:
  ```python
  async def settle():
      await pilot.pause(0.05)
      for _ in range(30):
          if dashboard._ws_debounce_task and not dashboard._ws_debounce_task.done():
              try: await dashboard._ws_debounce_task
              except asyncio.CancelledError: pass
          await pilot.pause(0.05)
          tasks_done = (dashboard._ws_debounce_task is None or dashboard._ws_debounce_task.done())
          if tasks_done and len(sess_list.children) > 0:
              break
  ```

---

## 3. Anti-Patterns & Outdated Techniques (What NOT to do)

1. **NEVER Eagerly Import Secondary Screens at Module Root**:
   - Importing screens directly in `app.py` or `screens/__init__.py` drags all dependent widgets, parsers, and charts into startup. Always use `cyguide/ui/screens/lazy.py` callables in `SCREENS`.
2. **NEVER Push Modal Dialogs Without Stack Deduplication**:
   - Never call `self.app.push_screen(ShortcutsDialog())` without verifying `if not any(isinstance(s, ShortcutsDialog) for s in self.app._screen_stack)`.
3. **NEVER Bind Keys Directly to `app.pop_screen` in Dialogs**:
   - Directly invoking `app.pop_screen` bypasses modal dismissal result callbacks and risks double-popping underlying application screens. Always route through `self.dismiss()`.
4. **NEVER Loop Over Row Inserts in SQLite Transactions**:
   - Executing individual `INSERT` statements inside a loop induces massive per-statement overhead. Always construct record parameter lists and call `db.executemany()`.
5. **NEVER Mutate Documentation in Automated `--check` Release Gates**:
   - Verification modes like `generate_benchmark_report.py --check` or `generate_schema_registry.py --check` must be strictly read-only and idempotent. Mutating markdown during preflight creates dirty working trees in CI and git hooks.
6. **NEVER Run Stress Benchmarks Across the Entire CI Matrix**:
   - Stress testing 500,000 stream lines across 4 matrix jobs burns CI quota and slows PR turnaround. Keep matrix runs focused on unit/integration correctness, and isolate stress limits to a single runner.

---

## 4. Invariants & Performance Contracts to Preserve

| Component | Target Contract | Hard Invariant / Boundary |
| :--- | :--- | :--- |
| **Cold App Launch** | `< 600 ms` | Must never exceed **`950 ms`** (`python -c "import cyguide.app"`). |
| **Terminal Stream Buffer** | `> 90,000 lines/sec` | Floor threshold is **`50,000 lines/sec`**; memory strictly capped at **`max_lines=5000`** ($O(1)$ ring buffer). |
| **GraphStore Ingestion** | `> 2,000 entities/sec` | Batch insertion floor is **`1,200 entities/sec`**; single-row transaction commits prohibited for bulk imports. |
| **DOM Virtualization** | `< 60 ms` rebuild (10k items) | Maximum allowable rebuild time is **`160 ms`**; category roots capped at **`MAX_DISPLAY_PER_CATEGORY = 200`**. |
| **Modal Screen Dismiss** | Strictly idempotent | `Screen.dismiss()` must never raise `ScreenStackError` regardless of repeat key burst volume. |
| **Release Check Preflight** | 6-Stage Gate | All 6 stages in `./scripts/release-check.sh` (Lint, Pytest, Schema Sync, Performance Guard, Build, Asset Check) must pass with zero warnings before release. |
