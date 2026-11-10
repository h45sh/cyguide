# CyGuide Master Project Roadmap & Unified Task Tracker

This document is the **single authoritative source of truth** for all completed, active, and future tasks across the CyGuide project. It consolidates architectural milestones, operator workbench features, autonomous agent roadmap, tool ecosystem expansion, and codebase maintenance items into one unified tracker.

---

## Master Task Statistics & Progress

| Phase / Category | Status | Total Tasks | Completed `[x]` | Pending `[ ]` | Progress |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Phase 1: Core Foundation** | **Completed** | 8 | 8 | 0 | 100% |
| **Phase 2: Intelligence & Expansion** | **Completed** | 8 | 8 | 0 | 100% |
| **Phase 3: Polish, Portability & Delivery** | **Completed** | 15 | 15 | 0 | 100% |
| **Power Mode Operator Workbench** | **Completed** | 30 | 30 | 0 | 100% |
| **v1.8.0 (Phase 3.5): Engine, Dataflow & Concurrency** | **In Progress** | 23 | 1 | 22 | 4% |
| **v1.9.0: Terminal Capabilities, IPC & Security/Encryption** | **Planned (Spec Ready)** | 9 | 0 | 9 | 0% |
| **v1.9.5: Tool Ecosystem & Contributor Scaffolding** | **Planned (Spec Ready)** | 6 | 0 | 6 | 0% |
| **v2.0.0: Mature Flagship Release & Public Launch** | **Planned (Spec Ready)** | 6 | 0 | 6 | 0% |
| **Phase 4: Autonomous Agent Runtime & Co-Pilot HUD** | **Planned (Future)** | 10 | 0 | 10 | 0% |
| **Phase 5: Multi-Agent Swarms & Collaborative Intel** | **Planned (Future)** | 6 | 0 | 6 | 0% |
| **Total Project Tasks** | **In Progress** | **121** | **62** | **59** | **51%** |

> [!NOTE]
> For complete technical specifications, architectural diagrams, and engineering contracts for the road to v2.0.0, consult [`docs/developer/V2_PLATFORM_SPECIFICATION.md`](V2_PLATFORM_SPECIFICATION.md).

---

## Chronological Phase Progression

```text
[ Phase 1: Core Foundation ] ────── Smart-Adapter Model, SQLite GraphStore, PIKs, TUI Shell
              │
[ Phase 2: Intelligence ] ──────── Ollama/Cloud Explainer, 5 Security Tools, Recommendation Rules
              │
[ Phase 3: Polish & Delivery ] ──── Diagnostics CLI & Modal, Portability (Export/Import), Hardening
              │
[ v1.8.0 / Phase 3.5: Engine ] ─── Stream Throttling, Disk Spooling, Tab/Queue Sync, Tree Usability
              │
[ v1.9.0: Terminal & Security ] ── Interactive PTY Shell, Decoupled IPC, AES Vault, CIDR Scope
              │
[ v1.9.5: Ecosystem & Showcase ] ─ cyg create-adapter, Nuclei, FFUF, SQLMap, VHS Recording
              │
[ v2.0.0: Flagship Launch ] ────── Standalone Binaries, Show HN, Reddit, Awesome-Lists, Kali/BlackArch
              │
[ Phase 4: Autonomous Agent ] ──── ReAct Loop, ActionGateway CIDR Policies, Agentic HUD
              │
[ Phase 5: Multi-Agent Swarm ] ─── Specialized Subagents (Recon, Web, Reporter, Critic)
```

---

### Phase 1: Core Foundation (Completed)
- [x] **Smart-Adapter Architecture**: Implemented decoupled "Smart Adapter / Stupid Framework" model isolating security CLI tools from engine logic ([`cyguide/engine/adapter.py`](../../cyguide/engine/adapter.py)).
- [x] **Reactive Graph Store**: Built SQLite-backed `GraphStore` with deterministic SHA-256 Primary Identity Key (PIK) upserting and graph edge modeling ([`cyguide/engine/store.py`](../../cyguide/engine/store.py)).
- [x] **Asynchronous Subprocess Executor**: Created non-blocking async executor with real-time stream draining and error recovery ([`cyguide/engine/executor.py`](../../cyguide/engine/executor.py)).
- [x] **Textual TUI Shell**: Implemented the base Textual application with screen management, reactive layouts, and custom theme styling ([`cyguide/app.py`](../../cyguide/app.py), [`cyguide/ui/style.css`](../../cyguide/ui/style.css)).
- [x] **Dashboard Engagement Hub**: Built workspace and session navigation with inline renaming and deletion cascades ([`cyguide/ui/screens/home.py`](../../cyguide/ui/screens/home.py)).
- [x] **Learning Mode Framework**: Developed guided curriculum screen with recipe selection, flag editor, and raw output panes ([`cyguide/ui/screens/learning.py`](../../cyguide/ui/screens/learning.py)).
- [x] **Standard 15-Schema Finding Library**: Created standard Pydantic models for cybersecurity entities ([`cyguide/schemas/`](../../cyguide/schemas)).
- [x] **Project Governance & Packaging**: Established tiered protection rules, `pyproject.toml` packaging, and CI verification ([`docs/user/CONTRIBUTING.md`](../user/CONTRIBUTING.md)).

---

### Phase 2: Intelligence & Expansion (Completed)
- [x] **Ollama Local LLM Backend**: Implemented streaming inference from local Ollama endpoints with `--ollama` and `--ollama-model` CLI flags ([`cyguide/engine/explainer.py:20`](../../cyguide/engine/explainer.py#L20)).
- [x] **Cloud LLM API Backend**: Implemented unified OpenAI, Anthropic, OpenRouter, Grok, and Groq streaming client via `CYGUIDE_API_KEY` ([`cyguide/engine/explainer.py:61`](../../cyguide/engine/explainer.py#L61)).
- [x] **Network Port Scanner Adapter (`nmap`)**: Host and service discovery yielding `network.host` and `network.service` findings ([`tools/nmap/`](../../tools/nmap)).
- [x] **Web Directory Fuzzer Adapter (`gobuster`)**: Endpoint discovery yielding `web.endpoint` findings ([`tools/gobuster/`](../../tools/gobuster)).
- [x] **Web Vulnerability Scanner Adapter (`nikto`)**: Flaw profiling yielding `web.vulnerability` findings ([`tools/nikto/`](../../tools/nikto)).
- [x] **Passive Subdomain Discovery Adapter (`subfinder`)**: Attack surface mapping yielding `dns.record` findings ([`tools/subfinder/`](../../tools/subfinder)).
- [x] **OSINT & Domain Registration Adapter (`whois`)**: Netblock and registrar extraction yielding `network.netblock` and `domain.info` findings ([`tools/whois/`](../../tools/whois)).
- [x] **Reactive Recommendation Engine**: Declarative suggestion rules proposing tools based on graph upsert events ([`cyguide/engine/recommendation.py`](../../cyguide/engine/recommendation.py)).

---

### Phase 3: Operator Polish, Diagnostics & Hardening (Completed)
- [x] **Diagnostic CLI Suite (`cyg check`)**: Automated verification of Python runtime, writable storage permissions, installed security tools, and AI backends ([`cyguide/engine/diagnostics.py`](../../cyguide/engine/diagnostics.py)).
- [x] **In-App Tool Health Modal (`Ctrl+P`)**: Surfaced real-time tool discovery badges, exact binary filesystem paths, and OS package manager installation hints directly in the TUI ([`cyguide/ui/screens/tool_health_modal.py`](../../cyguide/ui/screens/tool_health_modal.py)).
- [x] **Portable Session Export (`cyg export`)**: Zero-overhead atomic SQLite `ATTACH DATABASE` export of session graph, edges, and execution logs ([`cyguide/engine/store.py:529`](../../cyguide/engine/store.py#L529)).
- [x] **Session Import (`cyg import`)**: Seamless restoration of session archives into local workspaces ([`cyguide/engine/store.py:586`](../../cyguide/engine/store.py#L586)).
- [x] **Automated Markdown Reporting**: Executive and technical finding summary report generator ([`cyguide/engine/reporter.py`](../../cyguide/engine/reporter.py)).
- [x] **High-Performance Database Indexes**: Added 5 composite indexes (`idx_nodes_session_schema`, `idx_edges_session`, `idx_edges_source`, `idx_edges_target`, `idx_event_log_session_time`) to eliminate table scans ([`cyguide/engine/store.py:118`](../../cyguide/engine/store.py#L118)).
- [x] **Subprocess Execution Timeout Safeguards**: Wired configurable `timeout_seconds` with graceful `SIGTERM` cleanup across executor and actions ([`cyguide/engine/executor.py`](../../cyguide/engine/executor.py)).
- [x] **Comprehensive User Manual & Contributing Guides**: Master shortcut tables, CLI manuals, and tiered protection documentation ([`docs/user/USER_MANUAL.md`](../user/USER_MANUAL.md), [`docs/user/CONTRIBUTING.md`](../user/CONTRIBUTING.md)).
- [x] **166-Test Automated Hermetic Suite**: Fully automated test coverage across unit, integration, and UI flows with zero warnings or external network dependencies ([`tests/`](../../tests)).
- [x] **Defense-in-Depth Security Hardening**: Remediated link-local cloud metadata SSRF vectors, enforced atomic `0o600` private permissions on settings/notes, expanded subprocess secret scrubbing, and neutralized LLM prompt tag breakouts ([`docs/developer/ARCHITECTURE.md:520`](ARCHITECTURE.md#L520), [`tests/unit/test_security_fixes.py`](../../tests/unit/test_security_fixes.py)).
- [x] **Centralized Data Directory Architecture (`cyguide/paths.py`)**: Unified cross-platform application directory under `~/.cyguide` (or `$CYGUIDE_DATA_DIR`) preventing directory pollution ([`cyguide/paths.py`](../../cyguide/paths.py)).
- [x] **In-App Configuration Modal & Command Palette Providers (`ConfigModal`)**: Live tabbed settings editor for Ollama, Cloud AI, Database, and Custom Tools with Command Palette sub-palettes ([`cyguide/ui/screens/config_modal.py`](../../cyguide/ui/screens/config_modal.py)).
- [x] **Resilient Multi-Key Cloud AI Fallback & Cooldown Engine**: Automatic failover across multi-provider API keys and local Ollama fallback on rate-limiting (429) ([`cyguide/engine/explainer.py:208`](../../cyguide/engine/explainer.py#L208)).
- [x] **Interactive Split-Pane Edge Resizer (`ResizeHandle`)**: Draggable edge splitter dynamically resizing Entity Browser and Suggestions panes with width persistence ([`cyguide/ui/widgets/resizer.py`](../../cyguide/ui/widgets/resizer.py)).
- [x] **Forensic Session Archiving & Reopening Lifecycle**: Forensic read-only protection, status filters, and immutable audit event logging for closed sessions ([`cyguide/engine/store.py`](../../cyguide/engine/store.py), [`cyguide/engine/power_facade.py`](../../cyguide/engine/power_facade.py)).

---

### Phase 3.5: Performance Optimization, Streaming Resilience & UI Polish (Next Up / In Progress)

This critical hardening phase eliminates UI bottlenecks, decouples stream draining from terminal rendering, prevents RAM bloat during multi-hour/multi-day tasks, fixes tab lifecycle synchronization, and elevates the graph tree into a high-utility operator HUD:

#### Track 1: High-Volume Output & Streaming Resilience
- [ ] **Throttled Log Ingestion (20–30 FPS Micro-Batching)**:
  - *Priority*: **P1** | *Complexity*: Medium
  - Batch incoming stdout chunks in a rolling queue flushed at max 20–30 FPS (every 33–50ms) instead of calling `RichLog.write()` on every 1KB chunk.
  - Prevents UI freezing when tools (like `ffuf`, `gobuster`, or aggressive port scans) emit tens of thousands of lines per second.
- [ ] **Spill-to-Disk Log Streaming (`data/logs/{action_id}.log`)**:
  - *Priority*: **P1** | *Complexity*: Medium
  - Stream subprocess stdout directly to append-only disk files in real time.
  - Maintains $O(1)$ memory consumption so scans running for hours or days never cause RAM bloat or OOM crashes.
- [ ] **Decouple Database Ingestion from Subprocess Executor (Deepening Candidate 1)**:
  - *Priority*: **P1** | *Complexity*: Medium
  - Remove direct SQLite `GraphStore.upsert_finding()` calls from `Executor._drain_stream` / `run_tool()`.
  - Turns `Executor` into a pure subprocess lifecycle engine yielding `BaseFinding` streams, eliminating connection teardown race conditions and enabling atomic micro-batched ingestion at the coordination seam.
- [ ] **Capped UI Ring Buffer**:
  - *Priority*: **P1** | *Complexity*: Low
  - Keep a rolling window of the last 5,000 lines in the interactive UI terminal tab for instant rendering and smooth scrolling.
- [ ] **Safe Event Log Archiving**:
  - *Priority*: **P2** | *Complexity*: Low
  - Cap the string payload stored in SQLite's `event_log` table (saving the tail + summary in the DB and linking the full disk log).

#### Track 2: Job Queue & Tab Lifecycle Synchronization
- [ ] **Fix Tab Title Updating**:
  - *Priority*: **P1** | *Complexity*: Low
  - Replace the broken `#tab-{id}` query in `power.py` with Textual's native tab title API so workbench tabs update immediately whenever a new command is executed.
- [ ] **Live Job Queue Tracking & Elapsed Runtime Counter**:
  - *Priority*: **P1** | *Complexity*: Medium
  - Sync the Job Queue to show active tab association, current tool command snippet, live elapsed time counter (`01h:24m:10s`), and status (`◯ RUNNING`, `● DONE`, `× FAILED`).
  - Automatically update the queue item when subsequent tasks execute in the same tab.

#### Track 3: Graph Tree Optimization & Usability
- [x] **Refined Widget Exception Boundaries (NoMatches Enforced)**:
  - *Priority*: **P1** | *Complexity*: Low
  - Replaced bare `except Exception: pass` across `DashboardScreen` and `PowerModeScreen` with specific `except NoMatches: pass` to eliminate silent DOM query masking without breaking on unmounted widgets.
- [ ] **Zero-Rebuild Navigation**:
  - *Priority*: **P1** | *Complexity*: Low
  - Make `on_tree_node_highlighted` purely update the context bar variables (`$TARGET`, `$PORT`, `$SERVICE`).
  - Eliminate tree clearing (`self.root.clear()`) and tree rebuilding on arrow navigation, and prevent focus theft to `#command_input`.
- [ ] **Dynamic Category Entity Counts**:
  - *Priority*: **P2** | *Complexity*: Low
  - Display live count badges on tree headers: `Targets (3)`, `Services (12)`, `Web (22)`, `Vulnerabilities (5)`.
- [ ] **Tree Branch State Preservation**:
  - *Priority*: **P2** | *Complexity*: Medium
  - Retain user collapsed/expanded branch states across background finding updates.
- [ ] **Inline Target Search / Filter**:
  - *Priority*: **P2** | *Complexity*: Medium
  - Add an inline search bar at the top of the Entity Browser to quickly search and filter discovered hosts, services, and endpoints.

#### Track 4: Event Debouncing, Batched Upserts & Database Concurrency
- [ ] **Dashboard Highlight Debouncing**:
  - *Priority*: **P1** | *Complexity*: Low
  - Add 100ms debounce timer on workspace and session list highlight events so holding down arrow keys is silky smooth without flooding the event loop.
- [ ] **Batched Finding Ingestion & UI Notification Coalescing**:
  - *Priority*: **P1** | *Complexity*: Medium
  - Buffer rapid tool finding streams into atomic micro-batches (e.g. flush every 250ms or 50 items) instead of executing individual SQLite transactions per finding.
  - Coalesce reactive UI refresh events to prevent rendering storms.
- [ ] **Single-Query SQL Aggregates**:
  - *Priority*: **P2** | *Complexity*: Low
  - Replace per-session $N+1$ query loops in `show_workspace_details` with single `GROUP BY` aggregate queries in `GraphStore`.
- [ ] **SQLite WAL Mode & Pragma Tuning**:
  - *Priority*: **P2** | *Complexity*: Low
  - Enable `PRAGMA journal_mode = WAL;`, `PRAGMA synchronous = NORMAL;`, and `PRAGMA busy_timeout = 5000;` in `GraphStore.initialize()` to prevent read/write database locks during concurrent tasks.

#### Track 5: Learning Mode Optimization, Targeted Explanations & Boundary Isolation
- [ ] **Clean Text Rendering & Markdown Buffer Decoupling**:
  - *Priority*: **P1** | *Complexity*: Medium
  - Auto-clear or cleanly isolate previous explanation buffers upon new scan execution instead of infinitely concatenating text into an ever-expanding markdown string.
  - Eliminates $O(N^2)$ re-parsing of historical markdown tables and headings during streaming, preventing UI lag and screen jitter.
  - Cleanly erase intermediate status indicators (`*[Analyzing...]*`) when LLM tokens start streaming.
- [ ] **Selective & Targeted Explanations ("Explain Certain Text, Not All")**:
  - *Priority*: **P1** | *Complexity*: Medium
  - Feed *structured findings* (open ports, discovered vulnerabilities, HTTP status anomalies) to the LLM rather than blindly slicing the last 80 lines of raw output.
  - Contextual snippet / line explanation: allow the student to highlight or select a specific finding, error, or flag output and request an explanation for just that item.
  - Automated noise stripping: filter out repetitive scanner banner headers, ASCII art, and progress bars before LLM prompting to save token costs and reduce latency.
- [ ] **Robust Prompt Boundary Isolation & Input Sandboxing**:
  - *Priority*: **P1** | *Complexity*: Medium
  - Implement cryptographically randomized boundary tokens (e.g. `<<<UNTRUSTED_SCAN_OUTPUT_{UUID}>>>`) and XML/HTML escaping to ensure untrusted scan payloads cannot execute prompt injection attacks or break prompt boundaries.
  - Strict semantic demarcation separating System Directives, User Inquiries, and Untrusted Scanner Output.
- [ ] **Collapse Shallow LearningModeEngine into Unified Action Gateway (Deepening Candidate 2)**:
  - *Priority*: **P1** | *Complexity*: Low
  - Eliminate redundant 49-line `LearningModeEngine` pass-through module; route Learning Mode tool executions through `ActionGateway` / `PowerWorkspaceFacade.submit_action()` to inherit SSRF policy validation, live job buffers, and unified logging.
- [ ] **Eliminate Shallow LearningExplainer Wrapper (Deepening Candidate 3)**:
  - *Priority*: **P1** | *Complexity*: Low
  - Delete 10-line `LearningExplainer` indirection wrapper in `cyguide/engine/explainer.py` and unify callers directly against `MultiKeyCloudBackend.explain()` / `OllamaBackend.explain()`.
- [ ] **UI Structural Boundaries & Visual Cards**:
  - *Priority*: **P2** | *Complexity*: Low
  - Refactor the right workbench pane into distinct visual containers with explicit border separations:
    1. Active Command Execution Context Header
    2. Structured Discovered Findings Summary
    3. AI Educational Breakdown & Flags Analysis
    4. Docked Interactive Tutor Chat.

---

### Milestone: v1.9.0 — Terminal Capabilities, IPC & Security/Encryption (Planned)

> [!NOTE]
> Detailed technical specifications, data models, and sequence flows are documented in [`docs/developer/V2_PLATFORM_SPECIFICATION.md:36-160`](V2_PLATFORM_SPECIFICATION.md#L36-L160).

- [ ] **Dual-Path Interactive PTY Architecture**:
  - *Priority*: **P1** | *Complexity*: High | *Track*: Terminal
  - Implement OS pseudo-terminal pair (`master_fd`/`slave_fd`) via `os.openpty()` in `Executor` for interactive commands, replacing `stdin=DEVNULL`.
  - Enables handling interactive prompts (`sudo`, `ssh`, `[y/N]` confirmations, and live bash shells) inside workbench tabs.
- [ ] **Terminal Window Resize Signals (`SIGWINCH`)**:
  - *Priority*: **P1** | *Complexity*: Medium | *Track*: Terminal
  - Forward terminal geometry adjustments to the active PTY via `fcntl.ioctl` with `termios.TIOCSWINSZ` on UI pane resize.
- [ ] **Decoupled Asynchronous IPC & Daemon Architecture**:
  - *Priority*: **P1** | *Complexity*: High | *Track*: Architecture
  - Decouple background command execution from the Textual UI loop via an internal event bus and optional Unix domain socket (`~/.cyguide/run/cyguide.sock`).
  - Allows background scans to continue across UI reloads and enables headless external triggers.
- [ ] **Unify Split Workspace & Session Management (Deepening Candidate 4)**:
  - *Priority*: **P2** | *Complexity*: Medium | *Track*: Architecture / IPC
  - Consolidate parallel entity operations currently split across `GraphStore` and `PowerWorkspaceFacade` in dashboard views into a single deep Workspace/Session repository seam, designed to serve both the local TUI and the Unix domain socket IPC daemon.
- [ ] **Encrypted Session Archives (`cyg export --encrypt`)**:
  - *Priority*: **P1** | *Complexity*: Medium | *Track*: Security
  - Add AES-256-GCM authenticated encryption for exported session databases with Argon2id passphrase key derivation.
- [ ] **Zero-Leakage In-Memory Credential Scrubbing**:
  - *Priority*: **P2** | *Complexity*: Low | *Track*: Security
  - Scrub transient credentials, secret tokens, and API keys from memory upon task completion.
- [ ] **Declarative CIDR Scope Enforcement**:
  - *Priority*: **P1** | *Complexity*: Medium | *Track*: Security
  - Add explicit CIDR whitelist boundary validation in `ActionGateway` (e.g. `allowed_cidrs: ["10.0.0.0/24"]`) to reject out-of-scope targets.
- [ ] **LLM Prompt Boundary Sandboxing**:
  - *Priority*: **P1** | *Complexity*: Medium | *Track*: AI Safety
  - Enclose untrusted terminal output in ephemeral cryptographically randomized tokens (`<<<UNTRUSTED_SCAN_OUTPUT_{UUID}>>>`) with XML escaping to neutralize prompt injections.
- [ ] **Cross-Session Approval Context Swapping**:
  - *Priority*: **P2** | *Complexity*: Low | *Track*: UI/UX
  - Automatically swap the active TUI session context when approving suggestions originated from another session in the global graph.

---

### Milestone: v1.9.5 — Tool Ecosystem Expansion & Contributor Scaffolding (Planned)

> [!NOTE]
> Detailed adapter generator templates and schema contracts are documented in [`docs/developer/V2_PLATFORM_SPECIFICATION.md:162-192`](V2_PLATFORM_SPECIFICATION.md#L162-L192).

- [ ] **CLI Adapter Generator (`cyg create-adapter <name>`)**:
  - *Priority*: **P1** | *Complexity*: Low | *Track*: Developer Experience
  - Scaffolding generator creating `tools/<name>/manifest.toml`, `adapter.py`, typed finding models, and hermetic pytest tests in one step.
- [ ] **Nuclei Tool Adapter (`tools/nuclei/`)**:
  - *Priority*: **P1** | *Complexity*: Medium | *Track*: Tool Plugins
  - Fast, template-based vulnerability scanning using community YAML signatures. Emits `vulnerability.found` and `web.vulnerability`.
- [ ] **FFUF Tool Adapter (`tools/ffuf/`)**:
  - *Priority*: **P2** | *Complexity*: Low | *Track*: Tool Plugins
  - High-performance Go web fuzzer alternative to `gobuster`, leveraging v1.8.0 log batching. Emits `web.endpoint`.
- [ ] **SQLMap Tool Adapter (`tools/sqlmap/`)**:
  - *Priority*: **P2** | *Complexity*: High | *Track*: Tool Plugins
  - Automated SQL injection detection and database takeover. Emits `vulnerability.found` (SQLi) and `credential.found`.
- [ ] **External User Plugin Loading**:
  - *Priority*: **P3** | *Complexity*: Medium | *Track*: Extensibility
  - Support dynamic runtime discovery of custom user-defined adapters from `~/.config/cyguide/tools/` and `$CYGUIDE_PLUGIN_PATH`.
- [x] **Visual Terminal Showcase Script (`demo.tape` via VHS)**:
  - *Priority*: **P1** | *Complexity*: Low | *Track*: Showcase
  - Script a repeatable Charm VHS tape recording CyGuide launching, selecting a target, running a recipe, and exploring the graph ([`demo.tape`](../../demo.tape), [`assets/demo.gif`](../../assets/demo.gif), [`assets/`](../../assets/)).

---

### Milestone: v2.0.0 — The Mature Flagship Platform & Public Launch (Planned)

> [!NOTE]
> Detailed packaging specifications and launch playbooks are documented in [`docs/developer/V2_PLATFORM_SPECIFICATION.md:194-245`](V2_PLATFORM_SPECIFICATION.md#L194-L245).

- [ ] **Standalone Linux Binary Distribution (`cyguide-linux-x86_64`)**:
  - *Priority*: **P1** | *Complexity*: Medium | *Track*: Distribution
  - Configure GitHub Actions workflow building portable single-file binary releases via PyInstaller/Shiv with zero Python dependency requirements.
- [ ] **Target Delta / Diff View**:
  - *Priority*: **P2** | *Complexity*: Medium | *Track*: Operator Features
  - Visually highlight newly opened ports, services, or endpoints discovered across assessment sessions in diff colors.
- [ ] **Headless CLI Scripting Execution (`cyg run`)**:
  - *Priority*: **P2** | *Complexity*: Medium | *Track*: Automation
  - Support non-interactive CLI execution storing findings directly into the SQLite graph without launching the TUI.
- [ ] **GitHub Social Preview Card & Out-of-the-Box Badges**:
  - *Priority*: **P1** | *Complexity*: Low | *Track*: Branding
  - Deploy 1280×640 Open Graph banner and adapter badges (`Nmap`, `Gobuster`, `Nikto`, `Nuclei`, `FFUF`, `SQLMap`) to `README.md`.
- [ ] **Public Community Launch Sequence**:
  - *Priority*: **P1** | *Complexity*: Low | *Track*: Community
  - Execute coordinated releases across Hacker News (Show HN), Reddit (`r/commandline`, `r/Python`, `r/cybersecurity`), and PRs to `awesome-python`, `awesome-tui`, and `awesome-pentest`.
- [ ] **Security Distribution Packaging Requests**:
  - *Priority*: **P3** | *Complexity*: Low | *Track*: Distribution
  - Submit Intent-to-Package (ITP) issues to Kali Linux and BlackArch package repositories.

---

### Phase 4: Autonomous Agent Runtime & Co-Pilot Cockpit (Post-v2.0.0)

Evolves CyGuide from a manual terminal operator into an **AI Mission-Control Cockpit** engineered for hypothesis-driven, supervised autonomous cyber operations:

#### Track 1: Autonomous ReAct Decision Loop & Orchestrator
- [ ] **Autonomous ReAct Investigation Loop (`AgentOrchestrator`)**:
  - *Priority*: **P1** | *Complexity*: High
  - Iterative `Observe → Reason → Plan → Execute → Synthesize` loop that queries `WorkspaceContext` and calls `submit_action()`.
  - Driven by local Ollama or cloud models using structured tool calling schemas.
  - Reference: [`docs/developer/FUTURE_POWER_MODE.md:123-154`](FUTURE_POWER_MODE.md#L123-L154).
- [ ] **Declarative CIDR Scope Enforcement**:
  - *Priority*: **P1** | *Complexity*: Medium
  - Add explicit CIDR whitelist boundary validation in `ActionGateway` (e.g. `allowed_cidrs: ["10.0.0.0/24"]`).
  - Automatically reject agent actions targeting IP addresses outside authorized engagement bounds.
  - Reference: [`docs/developer/FUTURE_POWER_MODE.md:107-109`](FUTURE_POWER_MODE.md#L107-L109).

#### Track 2: The Agentic Cockpit UI (Power Mode Evolution)
- [ ] **Dual-Mode Workspace Layout (Operator vs Agentic Cockpit)**:
  - *Priority*: **P1** | *Complexity*: High
  - Toggle between classic **Manual Operator Workbench** (tabbed terminals) and **Agentic Co-Pilot Cockpit** (Live Reasoning Stream + Collapsible Tool Log Drawers).
  - Eliminates tab explosion when autonomous swarms run dozens of background tools simultaneously.
- [ ] **Agent Reasoning & Hypothesis Stream**:
  - *Priority*: **P1** | *Complexity*: Medium
  - Live structured feed exposing agent cognitive states: `Objective`, `Hypothesis`, `Decision Rationale`, and `Next Planned Moves`.
- [ ] **Attack Path Visualization & Root Cause Lineage**:
  - *Priority*: **P2** | *Complexity*: High
  - Transform the hierarchical entity tree into an **Attack Chain Visualizer** (`Host ❯ Port ❯ Endpoint ❯ Vulnerability ❯ Credential ❯ Pivot Target`).
  - Highlight the full discovery lineage for any compromised entity with a single click.

#### Track 3: Security Governance & Risk-Tiered HITL
- [ ] **Risk-Tiered Action Matrix & Approval Gate**:
  - *Priority*: **P1** | *Complexity*: Medium
  - Replace binary USER/AGENT checks with a 4-tier risk policy:
    - *Tier 1 (Passive Recon)*: Auto-approved (WHOIS, DNS, passive subdomains).
    - *Tier 2 (Active Non-Intrusive)*: Auto-approved with rate limits (SYN port scans, HTTP HEAD/GET).
    - *Tier 3 (Active Intrusive / Fuzzing)*: Requires policy rule or operator approval (directory fuzzing, vulnerability scanners).
    - *Tier 4 (Exploitation / Credential Probing)*: Strictly gated; interactive one-click authorization with payload inspection.
- [ ] **Real-Time Agent Steering & Life-Cycle Controls**:
  - *Priority*: **P1** | *Complexity*: Medium
  - Add Global Agent Pause (`Space` / `F5`) and **Natural Language Steering**: allows the operator to inject directional guidance (`"Avoid internal subnet 192.168.1.0/24, focus on port 8080"`) without terminating the agent session.
- [ ] **Execution Governor & Rate-Limiter**:
  - *Priority*: **P2** | *Complexity*: Medium
  - Configurable concurrency quotas per target host, request-per-second throttling, and target backoff on connection resets to prevent WAF bans or accidental denial-of-service.

#### Track 4: Multi-Session Recommendations & Workspace Scaling
- [ ] **Remove Recommendation Engine Store Seam Leakage (Deepening Candidate 5)**:
  - *Priority*: **P2** | *Complexity*: Low | *Track*: Architecture / Recommendations
  - Make recommendation rules pure finding transformers: stop reaching into `GraphStore._generate_node_id` and remove unused `store` references from rule APIs.
  - Keep identity generation behind a public schema or store interface so recommendation logic no longer depends on a private persistence implementation detail.
- [ ] **Workspace-Scoped Suggestion Toggling in Global View**:
  - *Priority*: **P2** | *Complexity*: Low
  - When Global Graph view (`Ctrl+G`) is active, query and display proposed findings across *all* sessions in the workspace.
- [ ] **Cross-Session Approval Context Swapping**:
  - *Priority*: **P2** | *Complexity*: Low
  - Automatically switch active TUI session when approving a suggestion originated from another session to maintain variable resolution integrity.

---

### Phase 5: Multi-Agent Swarms & Collaborative Intel (Planned)
- [ ] **Reconnaissance Subagent (`ReconAgent`)**:
  - *Priority*: **P2** | *Complexity*: Medium | *Track*: Multi-Agent
  - Specializes in attack surface enumeration (`nmap`, `whois`, `subfinder`), feeding confirmed host entities into the graph.
- [ ] **Web Application Subagent (`WebAgent`)**:
  - *Priority*: **P2** | *Complexity*: Medium | *Track*: Multi-Agent
  - Specializes in HTTP/HTTPS service fuzzing (`gobuster`) and vulnerability profiling (`nikto`).
- [ ] **Critic & Safety Audit Subagent (`CriticAgent`)**:
  - *Priority*: **P2** | *Complexity*: Medium | *Track*: Multi-Agent
  - Continuously audits proposed action batches against engagement scope boundaries, rate limits, and scan budgets.
- [ ] **Executive Reporter Subagent (`ReporterAgent`)**:
  - *Priority*: **P3** | *Complexity*: Low | *Track*: Multi-Agent
  - Reads append-only `event_log` upon engagement completion and synthesizes structured risk matrices and executive summaries.
- [ ] **Persistent Agent Cognitive Journal**:
  - *Priority*: **P2** | *Complexity*: Medium | *Track*: Memory
  - SQLite-backed memory preserving agent hypotheses, ruled-out vectors, and high-level milestones across session disconnects.
- [ ] **Cross-Session Knowledge Sharing & Workspace Graph Rollups**:
  - *Priority*: **P3** | *Complexity*: Medium | *Track*: Intelligence
  - Correlate discoveries across multiple engagements to detect shared infrastructure, identical SSL certificates, and enterprise-wide vulnerabilities.

---

## Power Mode Functional Progress Checklist

The Power Mode operator workbench is fully implemented as an advanced operator workspace:

- [x] **Investigation-Scoped Sessions**: Persistent session identity and state in SQLite.
- [x] **Typed Action System**: `ActionRequest` models with `triggered_by` field tracking execution origin.
- [x] **Structured Event Log**: Captures action payloads, result summaries, and raw shell commands.
- [x] **Action Gateway Security Policy**:
  - [x] Full validation for registered tools against input schemas.
  - [x] Raw shell command passthrough restricted strictly to `USER` source.
  - [x] Automatic rejection of unregistered tools for automated/agent sources.
  - [x] Blocked cloud metadata destination validation (`169.254.169.254`, `metadata.google.internal`).
- [x] **Universal Variable Substitution**: Contextual resolution of `$TARGET`, `$PORT`, `$SERVICE`, and `$PROTOCOL` in the Facade layer.
- [x] **Entity Browser (Tree)**: Hierarchical physical view of findings (Hosts -> Services -> Endpoints -> Vulnerabilities).
- [x] **Tabbed Job Workbench**: Parallel tool execution with independent log tabs and rolling output buffers.
- [x] **Job Control**: Implementation of `Ctrl+K` (Kill Job) to safely terminate active background processes (`SIGTERM`).
- [x] **Tab Navigation**: `Ctrl+PageUp` / `Ctrl+PageDown` horizontal workbench navigation.
- [x] **Smart Command Palette & Prompt**:
  - [x] Visual mode indicator badge: `[tool]` vs `[shell]`.
  - [x] Live context resolution status bar.
  - [x] Forced shell mode with `!` prefix and `Ctrl+L` prompt lock.
  - [x] Quick mode switching (`> !` and `! !`).
  - [x] CWD filename autocompletion via `Tab` in shell mode.
  - [x] Command execution history via `Up` / `Down` arrows.
- [x] **Workbench Persistence**: Replays tab logs and status from `event_log` upon re-entering a session.
- [x] **Advanced Entity Grouping**: Resolves graph parent-child edges to correctly nest services strictly under their host.
- [x] **Operator Scratchpad**: Docked markdown editor (`Ctrl+N`) auto-saving to `~/.cyguide/scratchpad.md`.
- [x] **Raw Shell Adapter**: Fallback adapter executing arbitrary OS terminal commands.
- [x] **Global Entity Graph (`Ctrl+G`)**: Deduplicates and merges entities across all sessions in a workspace.
- [x] **Global Job Queue**: Multi-session background task monitor grouping jobs by session.
- [x] **Cross-Session Jump**: Clicking a job in the queue seamlessly swaps active session context.
- [x] **Inline Renaming (`F2`)**: Universal inline renaming on Dashboard with case-insensitive collision validation.
- [x] **Safe Session Lifecycle Handling**: Graceful processing of deleted or moved sessions without ghost entities.
- [x] **Tab Lifecycle Management (`Ctrl+W`)**: UI for closing finished workbench tabs.
- [x] **Tab Closure Persistence**: Closed tabs are marked closed in SQLite (`closed_job_ids`) and do not reappear.
- [x] **Active/Closed Job Counters**: Real-time background job counts and persisted closed tab counts on dashboard.
- [x] **Unified Workspace Mutations in Facade**: Validates name uniqueness and kills active background processes on deletion.
- [x] **High-Density Recent Activity Log**: Compact dashboard event feed extracting IPs, ports, and domains while omitting closed tabs.
- [x] **AI Suggestions Pane**: Interactive sidebar displaying proposed findings with Approve (`Enter`) and Dismiss (`d`/`x`).
- [x] **Session Export & Import**: Atomic SQLite `.db` archive portability (`cyg export`, `cyg import`, and `Ctrl+E`).
- [x] **Forensic Session Archiving**: Mark sessions closed with immutable audit event logging and read-only protection against unintended mutations.
- [x] **Dynamic Split-Pane Edge Resizing**: Interactive drag handles for resizing Entity Browser and Suggestions sidebars with persistent widths.
- [x] **Unified Persistent Scratchpad**: Note-taking editor bound to `~/.cyguide/scratchpad.md` with mode `0o600`.

---

## Codebase Inline TODOs & Legacy Tech Debt Audit

| File | Line | Code / Comment | Audit Status & Resolution |
| :--- | :---: | :--- | :--- |
| [`cyguide/modes/power.py`](../../cyguide/modes/power.py#L48-L52) | 48-52 | `# Advanced: Complex graph-reactive suggestions...` | **Resolved**: Legacy stub cleaned up and formally documented as delegating reactive suggestion rules to `RecommendationEngine` in [`cyguide/engine/recommendation.py`](../../cyguide/engine/recommendation.py). |

---

## Historical Walkthrough References

For detailed implementation narratives, architectural decisions, and testing histories of completed features:
* **[Session Export & Markdown Reporting (Aug 2026)](history/walkthrough_export_reporting.md)**
* **[AI Suggestions & Recommendation Engine (Aug 2026)](history/walkthrough_suggestions_recommendations.md)**
* **[Codebase Refinement & Performance Optimization (Nov 2026)](#walkthrough.md)**
* **[Comprehensive Security Audit & Defense Hardening (Nov 2026)](#security_audit.md)**
