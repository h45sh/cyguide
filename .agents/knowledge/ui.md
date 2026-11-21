# Domain Knowledge: UI & Terminal Presentation (Tier 2)

## 1. Architectural Seams & Invariants
- **Unidirectional Layer DAG**: Presentation layer (`cyguide/ui/compat.py:L1`) must never spawn subprocesses, query SQLite directly, perform disk I/O, or execute LLM prompt loops.
- **Pure Filesystem Metadata**: UI widgets like `PowerPrompt` resolve git branches via standard library file parsing in `get_git_branch` (`cyguide/paths.py:L105`) reading `.git/HEAD` or worktree pointers ($< 0.1\text{ms}$), completely avoiding `subprocess.check_output` overhead and container binary requirements.
- **Clean Seam Encapsulation**: Dialogs (`ShortcutsDialog`) must never penetrate application private state (e.g. `_last_shortcuts_toggle_time`). State interactions must use explicit public methods on `CyGuideApp` (`record_shortcuts_toggle()`).
- **Facade Delegation**: UI interactions must route strictly through high-level facades: `PowerWorkspaceFacade` (`cyguide/engine/power_facade.py:L16`) or `LearningSession`.
- **Markdown Explanation Rendering**: Render streaming tutor explanations as a single `Static` container via `render_markdown()`; never mount nested per-paragraph DOM widgets ($O(1)$ widget allocation).
- **Theme Palette Consistency**: Markdown themes and syntax highlighting must adhere to the Gruvbox/Warm Gold palette (`#c89b3c`, `#b4832e`, `#d5c4a1`), avoiding hardcoded legacy Tailwind amber tokens (`#fbbf24`).

## 2. Textual Lifecycles & Async Event Timing
- **Active Settle Protocol**: Never rely on static sleeps (`sleep(0.1)`) for UI state assertions in tests. Virtualized CI runners can stretch a 50ms debounce into 150ms+. Always run an active settle loop awaiting in-flight tasks (`_ws_debounce_task`, `_sess_debounce_task`) catching `asyncio.CancelledError` and verifying `sess_list.index is not None`.
- **Timer Cancellation Invariant**: Textual `Timer` instances are event-loop callbacks, not `asyncio.Task` handles. Always invoke `timer.stop()`; invoking `timer.cancel()` crashes workers with `AttributeError`.
- **Modal Event-Loop Debounce & Idempotency**:
  - Guard the first 200ms of dialog lifecycle (`(now - self._opened_at) < 0.20`) to prevent immediate dismissal on keydown.
  - Successive key repeats with $\Delta t < 100\text{ms}$ mark `_is_holding_f1 = True` and cancel pending dismissal timers.
  - `CyGuideApp.action_show_hotkeys` enforces a 250ms cooldown before allowing subsequent modal pushes.
  - Stack deduplication: check `if not any(isinstance(s, ShortcutsDialog) for s in self.app._screen_stack)` before `push_screen()`.
  - Dismissal idempotency: `safe_screen_dismiss` in `cyguide/ui/compat.py:L1` verifies `self is stack[-1]`, setting a `_screen_dismissed` flag and trapping `ScreenStackError`. Never bind dismissal keys directly to `app.pop_screen()`.

## 3. Terminal & Formatting Standards
- **Authentic ANSI Prompt Stream**: Emits raw 8-bit ANSI SGR sequences (`┌─[run #N]─[timestamp]` and `└─> <command>`) parsed via `rich.text.Text.from_ansi()`. Eliminates square-bracket Rich markup escaping hazards.
- **ANSI & Markdown Hygiene**: Never mix Rich BBCode markup (`[bold]`) with raw ANSI escapes (`\x1b[32m`) in the same stream, which corrupts Rich's internal parser state.
- **Adaptive Separators**: Rules and dividers must dynamically inherit from `rich.rule.Rule` or `RichHorizontalRule`. Never repeat hardcoded characters (`"═" * 80`) which break on terminal pane resize. Major session breaks use electric blue double rules (`═`); minor section dividers use subtle hairlines (`─`).
- **Operational Notices**: Wrap fallback logs in clean Markdown blockquotes: `> 💡 Notice: Local Ollama unavailable. Falling back to Cloud AI...` instead of raw bracketed logs.

## 4. Key Failure Modes & Mandated Replacements
- **Streaming Markdown Crash**: Raw token chunks directly fed to Markdown renderers crash with `NoneType` region calculation exceptions. Buffer incoming tokens with a 50ms coalesce debounce.
- **Table Event Forwarding**: Handled via monkeypatch in `cyguide/ui/compat.py:L1` setting `MarkdownTableContent.ALLOW_SELECT = False`.
- **LLM Heading Normalization**: Pre-process LLM text with `re.sub(r"^\s*\*\*(#{1,6}\s+.*?)\*\*\s*$", r"\1", text, flags=re.MULTILINE)` so CommonMark detects `#` at column 0 instead of degrading to plain text.
- **Shielded DOM Reconciliation**: When switching tool inspectors or re-rendering child rows during rapid item highlights, shield the DOM reconciliation task via `asyncio.shield(...)` in `cyguide/ui/screens/tool_browser.py:L1` and patch `MessagePump._flush_next_callbacks` to safely handle `asyncio.CancelledError` (`cyguide/ui/compat.py:L140`).
