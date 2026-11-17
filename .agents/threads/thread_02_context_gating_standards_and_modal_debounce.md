# Thread Insight: Context Gating, Standards Formalization & Modal Event-Loop Debounce

- **Branch / PR**: `feat/api-guardrails-and-tool-intelligence` (Commit `7c4e0b3`)
- **Primary Domain**: `[UI | Engine | Tooling | Security]`
- **Author / Contributor**: `@h45sh`

---

## 1. Key Principles & Architectural Techniques Introduced

### 1.1. Deterministic Context Gating (`t3-gate`) & AST Architecture Caching
- **The Context Bloat Crisis**: Prior to gating, repetitive inspection of deep UI files (`learning.py` read 517 times, `home.py` read 406 times) bled thousands of dollars in LLM context windows during iterative development.
- **AST Skeleton Condensation (`t3-gate .`)**: Leverages Python's native `ast` parser to strip function bodies and summarize complex files into pure typed interfaces, docstrings, and class signatures. In CyGuide, this reduces **32,000+ raw lines to ~1,800 interface lines (~94.4% token reduction)** in [`.t3-architecture-cache.md`](file:///home/harsh/Documents/cyguide/.t3-architecture-cache.md) at $0.00 cost and < 50ms runtime.
- **Background Self-Updating Git Hook**: Configured `.git/hooks/post-commit` to execute `t3-gate . > /dev/null 2>&1 &`, ensuring the architecture index stays synchronized without manual operator intervention.
- **Hermetic Pre-flight (`t3-gate --tier0`)**: Runs AST compilation (`py_compile`) and git diff stats locally before dispatching heavyweight reasoning chains.

### 1.2. Deep Module Governance & Unidirectional Layer DAG Formalization
- **Ousterhout Philosophy Enforcement in `AGENTS.md`**: Mandates deep modules (small, stable interface hiding broad implementation complexity) and explicitly outlaws shallow 1:1 pass-through wrappers or single-method helper shims.
- **Unidirectional Layer DAG**:
  ```
  Presentation Layer (cyguide/ui/, cyguide/main.py)
    ↓
  Coordination & Intelligence Layer (power_facade.py, learning.py, gateway.py, context_builder.py, explainer.py, reporter.py)
    ↓
  Core Engine (execution_session.py, store.py, registry.py, timeline.py)
    ↓
  Pluggable Tools (tools/*/manifest.toml & adapter.py)
  ```
- **Information Hiding Invariant**: Eliminates backward-compatibility forwarder properties and bans private attribute access (e.g., no external code accessing `_active_processes` or raw SQLite connection handles).

---

## 2. Non-Obvious Insights & Codebase Realities

### 2.1. Textual `Timer` Cancellation Pitfall (`stop()` vs. `cancel()`)
- **The Trap**: Standard Python `asyncio.TimerHandle` uses `.cancel()`. Calling `timer.cancel()` on a Textual `Timer` instance raises:
  ```python
  AttributeError: 'Timer' object has no attribute 'cancel'
  ```
- **The Reality**: Textual's `Timer` class implements `.stop()` to deactivate and unschedule active timers. Always use `timer.stop()` when tearing down pending modal or debounce tasks.

### 2.2. Modal Toggle Bursts & Hardware Key-Repeat Debouncing
- **The Symptoms**: Holding down `F1` or pressing it rapidly caused `ScreenStackError`, duplicate modal pushes, or instant dismissals when the modal mounted mid-press.
- **The Solution in `ShortcutsDialog` & `CyGuideApp`**:
  1. **Holding Detection**: In `ShortcutsDialog.on_key`, if successive `F1` key events arrive with $\Delta t < 100\text{ms}$, mark `_is_holding_f1 = True` and unschedule any pending dismiss timers.
  2. **Initial Mount Guard**: Guard the first 200ms of dialog life (`(now - self._opened_at) < 0.20`), preventing the initial key-down event from instantly closing the newly opened dialog.
  3. **Tap vs. Hold Confirmation**: Delay intentional tap dismissal with a 60ms timer (`self.set_timer(0.06, self._do_f1_dismiss)`). If a subsequent repeat fires within that window, the timer is stopped via `.stop()`.
  4. **App-Level Cooldown**: `CyGuideApp.action_show_hotkeys` enforces a 250ms threshold (`_last_shortcuts_toggle_time`) before allowing another modal push.

### 2.3. Theme Palette Consistency & Test Assertions
- Markdown themes rendered on Textual's console must align with the unified Gruvbox/Warm Gold palette (`#c89b3c`, `#b4832e`, `#d5c4a1`). Tests verifying heading styles must test against the exact canonical hex tokens rather than legacy Tailwind amber shades (`#fbbf24`).

---

## 3. Anti-Patterns & Outdated Techniques (What NOT to do)

1. **NEVER Read Raw Full Files for Architectural Discovery**:
   - Do not invoke `view_file` on 1,000-line engine files just to check method names or imports. Always query `.t3-architecture-cache.md` first.
2. **NEVER Use `timer.cancel()` on Textual Timer Objects**:
   - Textual timers are not asyncio tasks; calling `.cancel()` will crash the UI worker. Always invoke `timer.stop()`.
3. **NEVER Bypass Facade Layers from UI Widgets**:
   - UI widgets must never touch `GraphStore` or dispatch shell commands directly. All operations must route through `PowerWorkspaceFacade` or `LearningSession`.
4. **NEVER Build Shell Commands via String Formatting**:
   - `shell=True` and string interpolation (`f"nmap {flags} {target}"`) are strictly forbidden. All CLI executions require argument vectors (`List[str]`) passed through `asyncio.create_subprocess_exec` with `sanitize_subprocess_env()`.

---

## 4. Invariants & Performance Contracts to Preserve

1. **AST Cache Compactness**:
   - `.t3-architecture-cache.md` must maintain $\ge 90\%$ token reduction relative to raw codebase line count (currently 94.4%, condensing ~32,000 lines into ~1,800 interface lines).
2. **Deterministic Security Boundaries**:
   - `ActionGateway.BLOCKED_TARGETS` must never weaken SSRF filters against IPv4 link-local (`169.254.0.0/16`), AWS IMDSv2 (`fd00:ec2::254`), Alibaba (`100.100.100.200`), hex/decimal encodings, and cloud metadata DNS.
3. **Atomic Private File Permissions**:
   - Any sensitive file (`settings.json`, `scratchpad.md`) must be created atomically with mode `0o600` via `os.open` with `O_CREAT | O_WRONLY | O_TRUNC` to prevent TOCTOU permission leakage.
4. **Hermetic Test Isolation**:
   - All tests must rely on canonical autouse fixtures (`isolate_cyguide_data_dir`, `in_memory_store`, `fake_command_runner`, `mock_explainer`) and never access `~/.cyguide` or make real network/LLM requests.
