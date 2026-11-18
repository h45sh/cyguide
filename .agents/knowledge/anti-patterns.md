# Repository Anti-Patterns & Prohibited Techniques (Tier 2)

## 1. Security & Process Execution Anti-Patterns
1. **NEVER use `shell=True` or Concatenate Command Strings**:
   - *Failure Mode*: Arbitrary string interpolation invites command injection and breaks on spaces/special characters.
   - *Replacement*: Construct argument vectors (`List[str]`) passed to `asyncio.create_subprocess_exec` in `cyguide/engine/executor.py:L17`.
   - *Verification*: `.venv/bin/pytest tests/unit/test_engine_executor.py -k test_run_tool_command_args`
2. **NEVER Pass Host Secrets to Child Subprocesses**:
   - *Failure Mode*: Subprocesses inherit `os.environ` by default, leaking API tokens (`CYGUIDE_*`, `OPENAI_*`, `AWS_*`, `GITHUB_*`, `VAULT_TOKEN`) to untrusted scripts.
   - *Replacement*: Filter environment dictionaries through `sanitize_subprocess_env()` in `cyguide/engine/executor.py:L17`.
   - *Verification*: `.venv/bin/pytest tests/unit/test_engine_executor.py -k test_sanitize_subprocess_env`
3. **NEVER Trust Untrusted Scanner Output in LLM Prompts or Expose Raw Tokens**:
   - *Failure Mode*: Scanner output can contain prompt injection payloads or leaked session bearer tokens that compromise LLM reasoning and data privacy.
   - *Replacement*: Sanitize tokens and private keys with `ExplainerBackend.redact_sensitive_artifacts()` and isolate output in dynamic `<UNTRUSTED_SCAN_OUTPUT_{uuid}>` boundary tags (`cyguide/engine/explainer.py:L850`).
   - *Verification*: `.venv/bin/pytest tests/unit/test_explanation_tutor.py -k test_redact_sensitive_artifacts`
4. **NEVER Weaken SSRF Filters in `ActionGateway` or Allow Arbitrary Non-User Shell Execution**:
   - *Failure Mode*: Bypassing link-local, cloud metadata filters (`169.254.0.0/16`, IMDSv2, octal/hex IP notations), or allowing autonomous AI agents to execute raw shell commands allows host compromise and cloud credential theft.
   - *Replacement*: Strictly validate destinations via `is_blocked_destination()` in `cyguide/engine/gateway.py:L73` and restrict `use_shell=True` exclusively to explicit `ActionSource.USER` actions (`cyguide/engine/gateway.py:L179`).
   - *Verification*: `.venv/bin/pytest tests/unit/test_gateway.py -k test_blocked_destinations`

## 2. UI & Textual Presentation Anti-Patterns
1. **NEVER Call `timer.cancel()` on Textual Timers**:
   - *Failure Mode*: Textual `Timer` objects are not asyncio tasks; `.cancel()` raises `AttributeError` and crashes workers.
   - *Replacement*: Always call `timer.stop()`.
2. **NEVER Push Modal Dialogs Without Stack Deduplication**:
   - *Failure Mode*: Rapid key repeats push identical screens concurrently, breaking the screen stack with `ScreenStackError`.
   - *Replacement*: Check `if not any(isinstance(s, DialogClass) for s in self.app._screen_stack)` before pushing.
3. **NEVER Bind Keys Directly to `app.pop_screen` in Dialogs**:
   - *Failure Mode*: Bypasses dismissal result callbacks and risks double-popping underlying application screens.
   - *Replacement*: Always route through `self.dismiss()`.
4. **NEVER Rely on Static Sleeps for Asynchronous UI State Assertions**:
   - *Failure Mode*: `await pilot.pause(0.05)` or `sleep(0.1)` fails intermittently on loaded virtualized CI runners.
   - *Replacement*: Use an active settle loop awaiting `_ws_debounce_task` and `_sess_debounce_task` while checking DOM readiness.
5. **NEVER Mix Rich Markup with Raw ANSI Escape Sequences**:
   - *Failure Mode*: Mixing Rich BBCode with raw ANSI in the same buffer corrupts Rich's internal parser state.
   - *Replacement*: Use 100% ANSI escapes parsed via `Text.from_ansi()` or 100% pure Rich markup.
6. **NEVER Repeat Hardcoded Characters for Terminal Separators**:
   - *Failure Mode*: Character multiplying (`"=" * 80`) triggers horizontal line wrapping on terminal pane resize.
   - *Replacement*: Yield dynamic `rich.rule.Rule` instances inside custom Markdown elements.
7. **NEVER Emit Raw Unformatted Debug Logs into Explanations**:
   - *Failure Mode*: Direct bracketed logs degrade UI presentation quality.
   - *Replacement*: Wrap notices in Markdown blockquotes: `> 💡 Notice: Local Ollama unavailable...`.

## 3. Storage & Engine Anti-Patterns
1. **NEVER Execute Direct SQLite Calls from UI Widgets**:
   - *Failure Mode*: Tight coupling, missing transaction safety, and UI event-loop freezes.
   - *Replacement*: Route all data access through `PowerWorkspaceFacade` (`cyguide/engine/power_facade.py:L16`) or `LearningSession`.
2. **NEVER Loop Over Single-Row Inserts in SQLite Transactions**:
   - *Failure Mode*: Massive per-transaction disk write overhead ($O(N)$ commit cost).
   - *Replacement*: Prepare parameter batches and use `db.executemany()` or `upsert_findings_batch()`.
3. **NEVER Accumulate Streaming Logs in Unbounded Lists or Strings**:
   - *Failure Mode*: `+=` string concatenation on high-speed stdout streams causes severe memory fragmentation.
   - *Replacement*: Use bounded `collections.deque(maxlen=5000)` and stream logs directly to disk.
4. **NEVER Eagerly Import Secondary Screens or HTTP Stacks at Root**:
   - *Failure Mode*: Drags heavy dependencies into cold launch, inflating startup latency to $> 950\text{ms}$.
   - *Replacement*: Use `cyguide/ui/screens/lazy.py:L1` callables and extract lightweight utilities to `cyguide/common/keys.py:L1`.

## 4. Packaging & Release Engineering Anti-Patterns
1. **NEVER Use `pip install -e .` in CI Verification**:
   - *Failure Mode*: Editable installs hide missing package assets, uncommitted manifests, and broken entry points.
   - *Replacement*: Build wheel (`python -m build --wheel`) and install the `.whl` package in an isolated test environment.
2. **NEVER Invoke PyPI Publishing from a `workflow_call`**:
   - *Failure Mode*: PyPI OIDC token verification fails with HTTP 400 because caller workflow reference mismatches.
   - *Replacement*: Trigger publishing directly from top-level `release: [published]` or `workflow_dispatch` events.
3. **NEVER Mutate Documentation in Automated `--check` Release Gates**:
   - *Failure Mode*: Verification scripts mutating files dirty the git working tree in CI preflight.
   - *Replacement*: Ensure `--check` verification modes in `scripts/generate_benchmark_report.py:L1` are strictly read-only.
4. **NEVER Run Heavy Stress Benchmarks Across Entire CI Matrix**:
   - *Failure Mode*: Burns excessive CI minutes across multi-platform matrix nodes.
   - *Replacement*: Isolate high-load benchmarks to a single dedicated Ubuntu runner.
## 5. Testing & Architecture Anti-Patterns
1. **NEVER Test Pure Domain Validation Logic via Full Textual DOM Mounts**:
   - *Failure Mode*: Mounting full apps and calling `await pilot.pause(0.2)` repeatedly to test in-memory business logic bloats test suites with multi-second execution times and flaky timeouts.
   - *Replacement*: Extract state invariants into pure controllers (`KeyProfileManager` in `cyguide/ui/screens/config_modal.py:L22`) and verify with sub-second property tests (`tests/unit/test_config_state.py:L10`).
2. **NEVER Spawn Subprocesses in UI Widgets to Inspect Git Metadata**:
   - *Failure Mode*: Violates Presentation Layer DAG, creates test flakiness, leaks process handles on fast widget unmount, and fails in git-less minimal containers.
   - *Replacement*: Pure filesystem inspection via `get_git_branch` in `cyguide/paths.py:L105`.
3. **NEVER Penetrate Application Private State Across Modules**:
   - *Failure Mode*: Breaks encapsulation and triggers `PRIVATE_STATE_LEAK` warnings during Code Guard audits.
   - *Replacement*: Expose a clean, public method on the owning class (`record_shortcuts_toggle()` in `cyguide/app.py:L872`).
