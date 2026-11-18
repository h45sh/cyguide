# Agent Directives, Engineering Standards & Architecture Rules

This authoritative specification governs all AI agents and contributors working in the **CyGuide** repository. Adherence to these standards is mandatory to preserve architectural integrity, security guarantees, performance, and token efficiency.

---

## 1. Context Gate & Token Optimization Policy

1. **Architecture Discovery via Cache**:
   - **Never read raw full files for architectural discovery.**
   - Consult `.t3-architecture-cache.md` first to locate classes, signatures, data structures, and module contracts.
2. **Slice Reads**:
   - When inspecting implementations, use line-bounded ranges (`view_file` with `StartLine` and `EndLine`) targeting only the relevant function or block. Never dump 1,000-line files into context.
3. **Diff-Bounded Audits**:
   - Inspect and audit only `git diff` hunks or staged changes, not entire directory trees.
4. **Tier 0 Local Pre-flight**:
   - Run zero-cost local checks (`t3-gate --tier0`, `.venv/bin/ruff check`, `.venv/bin/pytest`) in 50ms before invoking heavy multi-step agent reasoning loops.
5. **High-Density Communication**:
   - Omit conversational filler, repeating user prompts, boilerplate summaries, and pleasantries. Focus strictly on concrete technical findings, diffs, and verification commands.

---

## 2. Architectural Principles: Deep Modules vs. Shallow Modules

CyGuide strictly adheres to John Ousterhout’s philosophy of software design (**Deep Modules** over Shallow Modules):

1. **Deep Modules (Small Interface, Big Implementation)**:
   - Every module must provide a concise, high-leverage interface that hides significant internal complexity.
   - **Never create shallow classes or functions**: Avoid creating wrappers that simply pass arguments through 1:1, thin helper classes with an interface as complex as their implementation, or single-method shims.
   - Modules like `ExecutionSession`, `ActionGateway`, `WorkspaceRepository`, `WorkspaceContextBuilder`, `ExplanationTutor`, and `SessionReportService` are deep; do not split them into trivial micro-files.
2. **Information Hiding & Strict Encapsulation**:
   - Encapsulate private state, helper functions, and internal data structures.
   - **Never leak private attributes** across architectural boundaries (e.g. no caller should access `_active_processes`, `_sessions`, or internal connection objects).
   - Do not create backward-compatibility forwarder properties or shims; write clean, direct contracts.
3. **Pure Core vs. Imperative Shell (Unidirectional Layer DAG)**:
   - Dependencies must flow strictly downwards in one direction:
     ```
     Presentation Layer (TUI / CLI: cyguide/ui/, cyguide/main.py)
       ↓
     Coordination & Intelligence Layer (cyguide/engine/power_facade.py, learning.py, gateway.py, context_builder.py, explainer.py, reporter.py)
       ↓
     Core Engine (cyguide/engine/execution_session.py, store.py, registry.py, timeline.py)
       ↓
     Pluggable Tools (tools/*/manifest.toml & adapter.py)
     ```
   - **Presentation Layer Rules**:
     - UI screens and widgets (`cyguide/ui/`) must **NEVER**:
       - Spawn subprocesses directly (`asyncio.create_subprocess_exec` or `subprocess.run`).
       - Query or mutate SQLite tables directly (no direct SQL or `store` mutations from widgets).
       - Perform disk file I/O or raw network calls.
       - Implement LLM prompt construction or polling loops.
     - All user and agent actions MUST flow through high-level facades (`PowerWorkspaceFacade`, `LearningSession`).
4. **The "Smart Adapter / Stupid Framework" Invariant**:
   - The core framework is completely tool-agnostic: it understands only normalized Pydantic `BaseFinding` schemas, SQLite graph storage, process lifecycles, and pub/sub streams.
   - Pluggable tool adapters (`tools/<name>/adapter.py`) encapsulate all CLI argument construction, binary discovery, and line-by-line stdout/stderr parsing.
   - Adding or modifying a security tool is **strictly additive**: create or edit `tools/<name>/manifest.toml` and `adapter.py`. Never edit core engine, database, or UI code to support a new tool.
   - **DevKit & Adapter Authoring Skill**: When authoring, scaffolding, or validating tool plugins, consult the official standalone toolkit and skill at [`h45sh/cyguide-devkit`](https://github.com/h45sh/cyguide-devkit). It provides automated scaffolding (`cyguide-devkit new`), AST validation (`cyguide-devkit validate`), and curriculum recipe schemas.
5. **Polymorphic Seam Encapsulation**:
   - Adhere to established seams:
     - `InvestigationSession` (`cyguide/engine/session.py`): Unifies runtime lifecycle requirements across Power Mode (`PowerWorkspaceFacade`) and Learning Mode (`LearningSession`).
     - `ToolAdapter` (`cyguide/engine/adapter.py`): Contract for all CLI tools (`validate_install`, `build_command`, `parse_output`).
     - `CommandRunner` (`cyguide/engine/execution_session.py`): Pluggable execution seam allowing fast in-memory test fakes without subprocesses.
     - `ExplainerBackend` (`cyguide/engine/explainer.py`): Seam for streaming AI responses across local Ollama and cloud providers.

---

## 3. Security Principles & Defense-in-Depth

Security is an absolute invariant. CyGuide is a cybersecurity operator tool and must be immune to command injection, SSRF, prompt injection, and credential exposure.

1. **Subprocess Isolation & No Shell Injection**:
   - **NEVER use `shell=True`**, `os.system()`, or string concatenation/interpolation to build shell commands.
   - Always spawn binaries via argument vectors (`List[str]`) using `asyncio.create_subprocess_exec(cmd[0], *cmd[1:], ...)`.
   - Always scrub child process environments with `sanitize_subprocess_env()`: strip `CYGUIDE_*`, `OPENAI_*`, `ANTHROPIC_*`, `GROQ_*`, `DEEPSEEK_*`, `AWS_*`, `GITHUB_*`, `VAULT_TOKEN`, and SSH keys so child tools never inherit operator secrets.
2. **Gated Policy & Source Segregation**:
   - Explicit arbitrary shell commands (`!` prefix / `is_explicit_shell=True`) are strictly restricted to `ActionSource.USER` inside `ActionGateway`.
   - Autonomous AI agents are restricted to registered tools conforming to validated schemas.
   - Tool targets must strictly validate against manifest `accepts` schema contracts.
3. **SSRF & Cloud Metadata Defense**:
   - `ActionGateway.BLOCKED_TARGETS` enforces strict blocking against:
     - IPv4 Link-Local subnet: `169.254.0.0/16` (AWS, Azure `169.254.169.250`, GCP, DigitalOcean, Oracle).
     - AWS IMDSv2 IPv6 Link-Local: `fd00:ec2::254`.
     - Alibaba Cloud metadata: `100.100.100.200`.
     - Alternate numeric encodings: decimal `2852039166`, hex `0xa9fea9fe`.
     - Cloud DNS hostnames: `metadata.google.internal`, `metadata.internal`, `instance-data`.
4. **Atomic Private File Permissions (TOCTOU Prevention)**:
   - Any file storing credentials, API keys, or operator notes (`settings.json`, `scratchpad.md`) must be created atomically with permission mode `0o600` (`-rw-------`, user read/write only) via `os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)`.
   - Never create a file with default umask and `chmod` afterwards, as this leaves a Time-of-Check to Time-of-Use window. Application directories must use `0o700`.
5. **AI Prompt Injection Neutralization**:
   - Untrusted target scanner outputs passed to AI tutor prompts must be strictly wrapped inside `<untrusted_scan_output>...</untrusted_scan_output>` XML boundary tags.
   - Neutralize closing tag breakouts: replace any occurrence of `</untrusted_scan_output>` in untrusted logs with `<\\/untrusted_scan_output>` prior to prompt interpolation.
6. **Database Hardening**:
   - 100% of SQL statements must use parameterized queries (e.g. `ATTACH DATABASE ? AS src`). Never concatenate or format raw strings into SQL queries.
   - Enforce `PRAGMA trusted_schema = OFF;` and `PRAGMA foreign_keys = ON;` on every connection.
   - Enforce forensic read-only locking on `CLOSED` workspaces/sessions (`PermissionError` on mutation attempts).

---

## 4. Real-Time Streaming & UI Performance (Textual & Asyncio)

Follow these lessons learned to ensure terminal rendering remains responsive at 60 FPS:

1. **Virtualization & Bounded Buffers**:
   - Never accumulate streaming terminal logs via unbounded string concatenation (`+=`) or unbounded lists.
   - Use bounded ring buffers (`collections.deque(maxlen=5000)`) in terminal stream widgets to keep UI heap consumption under 3 MB.
   - Stream uncapped complete raw output directly to disk (`data/logs/{action_id}.log`).
   - Virtualize viewports: `render_line(y)` renders only lines currently in the visible terminal viewport; never build DOM elements for off-screen rows.
2. **Quadratic Markup Suppression**:
   - Set `markup=False` on raw stdout terminal output widgets to avoid quadratic $O(N^2)$ Textual Rich markup parsing on incoming stream chunks.
3. **Throttled Micro-Batching**:
   - Batch high-frequency output updates at 30 FPS (~33ms) or 20 FPS (~50ms) using a timer. Never trigger a UI repaint on every individual stdout line.
4. **Event Loop Starvation Defense**:
   - Explicitly yield control to the asyncio event loop in tight loops:
     - `await asyncio.sleep(0)` inside UI update loops.
     - `await asyncio.sleep(0.01)` inside process stream reader loops.
5. **Textual Workers (`@work`)**:
   - Run long-running tasks in background workers using `@work(exclusive=True)`.
   - Call worker methods directly without `await` (`self.run_worker()` not `await self.run_worker()`).
6. **Defensive System Imports**:
   - Secondary dependencies (e.g. `pyperclip` for clipboard) must be wrapped in `try/except ImportError` blocks so headless Linux or SSH sessions do not crash.
7. **CSS Dialects**:
   - Use Textual-native CSS rules (e.g., `text-style: italic`, not web CSS `font-style: italic`).

---

## 5. Data Modeling, Identity & Storage (GraphStore & SQLite)

1. **Primary Identity Keys (PIK)**:
   - Findings must inherit from `BaseFinding` in `cyguide/schemas/base.py`.
   - Every finding schema defines a deterministic Primary Identity Key (PIK) (e.g. `{"ip": "..."}` for `network.host`, `{"host_ip": "...", "port": ..., "protocol": "..."}` for `network.service`).
   - Node IDs are deterministic SHA-256 hashes of `(schema_type + sorted_pik)`.
2. **Idempotent Upsert & Non-Destructive Merging**:
   - Upserts must merge finding payload attributes rather than duplicating nodes.
   - Hierarchical parent-child links (`parent_id`) and semantic association links (`associations`) must be auto-wired deterministically.
3. **Pydantic Declarative Canonicalization**:
   - Canonicalize data in Pydantic field validators: trim whitespace, lowercase domains, normalize IP addresses and URLs.
4. **Dual Graph & Event-Log Persistence**:
   - Stateful `nodes` and `edges` tables provide sub-millisecond graph queries for UI trees.
   - Immutable append-only `event_log` table records every tool execution, shell command, and finding for forensic replayability and session tab restoration.
5. **Persistent Connection Pool**:
   - Never open and close SQLite connections per finding or row. Encapsulate connections via `GraphStore.connection()` using a shared `aiosqlite` connection pool with `busy_timeout=5000` and `journal_mode=WAL`.
6. **Zero-Copy Session Portability**:
   - Use SQLite native `ATTACH DATABASE` and `INSERT INTO dest.* SELECT ... FROM src.*` for atomic, zero-memory session export and import.

---

## 6. Code Quality, Linters & Checks

1. **Python Environment & Baseline**:
   - Python $\ge 3.11$ (`requires-python = ">=3.11"`).
   - Target version in linters: `py311`.
2. **Ruff Rules & Formatting**:
   - Run check: `.venv/bin/ruff check .`
   - Run format: `.venv/bin/ruff format .`
   - Line length: 100 characters.
   - Enforced rule sets:
     - `E9`, `F7`: Syntax errors
     - `F63`: Assertions and test syntax
     - `F82`: Undefined names
     - `F401`: Unused imports (remove dead imports)
     - `I`: isort clean import ordering (`known-first-party = ["cyguide", "tools"]`)
     - `ASYNC`: flake8-async pitfalls
     - `B`: flake8-bugbear design gotchas
3. **Schema Registry Synchronization**:
   - Whenever any schema in `cyguide/schemas/` is created or modified, you MUST re-generate the schema registry documentation:
     ```bash
     python3 scripts/generate_schema_registry.py
     ```
   - Pre-commit hook enforces `python3 scripts/generate_schema_registry.py --check`.

---

## 7. Testing Standards, Proofs & The Trust Pyramid

CyGuide adheres to Lauren Tan’s **Trust Pyramid** and **"Review Proof, Not Code"** engineering model:

1. **The Trust Pyramid (Mechanical Gates over Prose Prompts)**:
   - **Translate Mistakes to AST Linters & Tests, Not Prompts**: Prose instructions degrade over time and cause prompt fatigue. Whenever an agent violates an architectural invariant, security boundary, or layer rule, convert it into an automated AST check in `tests/unit/test_architecture.py` rather than adding more negative prose rules to `AGENTS.md`. Structural and mechanical constraints are permanent, deterministic, and zero-cost.
   - **Mathematical Properties over Point Examples**: Core logic (PIK generation, canonicalization idempotence, SSRF IP/DNS blocking, GraphStore commutativity/idempotence) must be verified via property-based testing with **Hypothesis** (`tests/unit/test_properties.py`).
2. **Review Proof, Not Code (Headless User Flow Proofs)**:
   - Builds and isolated unit tests do not prove that an operator flow works.
   - When modifying TUI screens (`cyguide/ui/`), widget layouts, event streams, or command lifecycles, you must provide empirical execution proofs using Textual's headless pilot (`tests/integration/test_tui_workflow_proof.py`).
   - Verify full screen transitions, event handling, and graph rendering rather than relying on manual human inspection of raw diffs.
3. **Universal Adapter Fuzzing & Auto-Registration**:
   - Every tool adapter implementing `ToolAdapter` is automatically tested via `tests/unit/test_parsers/test_fuzz_all_adapters.py`.
   - Adapters are subjected to 4 adversarial streams (broken ANSI codes, 20,000-token strings, truncated JSON, and null bytes) and installation checks without requiring boilerplate unit tests per adapter.
   - Do NOT write repetitive `test_validate_install` or shallow wrapper tests for individual adapters.
4. **The Codebase Is Memory (Zero Tolerance for Slop & Layered Mess)**:
   - LLMs imitate whatever is in the repository. Maintain zero tolerance for dead code, unused parameters, temporary backward-compatibility shims, or shallow wrapper slop. Reference adapters (`tools/nmap/`) and core engines must remain immaculate templates.
   - **Prune Superseded Tests**: When introducing universal property tests, AST architectural checks, or workflow proofs, actively prune redundant point-value legacy tests to prevent "layered mess" and keep test execution lean.
5. **Tiered Test Execution Matrix**:
   - `pytest -m tier0`: AST architectural rules & mathematical invariants (<3s, zero external dependencies, run before every push).
   - `pytest -m fast`: Fast unit logic, state machines, and bounded stream stress tests (`tests/unit/test_engine_stress.py`).
   - `pytest -m fuzz`: Universal security tool adapter fuzzing suite (`tests/unit/test_parsers/test_fuzz_all_adapters.py`).
   - `pytest -m proof`: Headless TUI pilot workflows (`tests/integration/test_tui_workflow_proof.py`).
   - `pytest -m slow`: Long-running multi-stage benchmarks or soak tests.
6. **Hermetic Test Isolation**:
   - `isolate_cyguide_data_dir` autouse fixture isolates `CYGUIDE_DATA_DIR` to a temporary directory. Never read or write to `~/.cyguide` during test execution.
   - `in_memory_store`: Use `GraphStore(":memory:")` for fast in-memory SQLite testing. Always ensure stores are closed in test teardown (`await store.close()`).
   - `fake_command_runner`: Use `FakeCommandRunner` or `HighVolumeStressRunner` subclass of `CommandRunner` for execution testing; never spawn real network tools (`nmap`, `gobuster`, etc.) in automated unit tests.
   - `mock_explainer`: Use `FastMockExplainer` subclass of `ExplainerBackend` for AI testing; never make live network calls to Ollama or cloud LLMs during testing.

---

## 8. Codebase Tiered File Protection Policy

Adhere to the file modification governance policy:

| Tier | Category | Files | Policy |
| :--- | :--- | :--- | :--- |
| **Tier 1** | **Frozen Core** | `cyguide/schemas/base.py`<br>`cyguide/engine/store.py`<br>`cyguide/common/canonicalize.py`<br>`cyguide/engine/registry.py`<br>`cyguide/paths.py` | Core infrastructure. Must not be modified or refactored casually. Zero breaking contract changes. |
| **Tier 2** | **Review Required** | `tools/*/adapter.py`<br>`cyguide/schemas/*.py`<br>`cyguide/engine/executor.py`<br>`cyguide/engine/power_facade.py`<br>`cyguide/engine/explainer.py`<br>`cyguide/engine/gateway.py` | Architectural components. Any modifications require comprehensive unit tests verifying backward compatibility. |
| **Tier 3** | **Free to Change** | `cyguide/ui/` (Screens, Widgets, Styles)<br>`docs/`<br>`scripts/`<br>`tests/` | Layouts, UI widgets, styles, tests, documentation, and tooling. |

---

## 9. Domain Vocabulary & Ubiquitous Language

Maintain strict adherence to the project glossary:
- **Workspace**: Top-level container grouping related sessions for an engagement. (_Avoid_: Folder, project, target group).
- **Session**: Immutable persistent investigation timeline in SQLite with graph nodes and event log. (_Avoid_: Engagement, project, run, tab).
- **ExecutionSession**: Runtime manager for process lifecycles, output streaming, and session eviction. (_Avoid_: Job manager, runner, terminal instance).
- **ActionGateway**: Deep security module managing policy, SSRF defense, input validation, and variable resolution. (_Avoid_: Validator, firewall, auth check).
- **Finding**: Structured canonicalized unit of security intelligence inheriting `BaseFinding`. (_Avoid_: Result, discovery, raw output).
- **Action**: Explicit recorded invocation of a security tool or shell command. (_Avoid_: Job, task, subprocess).
- **ExplanationTutor**: AI guidance subsystem providing contextual mentorship and vulnerability explication. (_Avoid_: Chatbot, LLM client, assistant).
