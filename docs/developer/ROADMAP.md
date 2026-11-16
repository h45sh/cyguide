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
| **v1.8.0: Showcase, Textual Resilience & Automated Release** | **Completed** | 4 | 4 | 0 | 100% |
| **v1.9.0 (Phase 3.5): Engine, Dataflow & Concurrency** | **Completed** | 22 | 22 | 0 | 100% |
| **v1.9.1: Finding Stream Debouncing & Tree Node Caps** | **Completed** | 2 | 2 | 0 | 100% |
| **v1.10.0: Learning Mode Mega-Course, Schema 2.0 & Tools** | **In Progress (Active dev)** | 23 | 14 | 9 | 61% |
| **v1.11.0: Advanced Terminal Capabilities, IPC & Security** | **Planned (Spec Ready)** | 13 | 1 | 12 | 8% |
| **v2.0.0: Mature Flagship Release & Public Launch** | **Planned (Spec Ready)** | 12 | 0 | 12 | 0% |
| **Phase 4: Tactical Research Co-Pilot & Offensive Engine** | **Planned (Future)** | 15 | 1 | 14 | 7% |
| **Phase 5: Multi-Agent Swarms & Collaborative Intel** | **Planned (Future)** | 6 | 0 | 6 | 0% |
| **Job-First Engineering & Market Mastery Track** | **Active Focus** | 9 | 3 | 6 | 33% |
| **Total Project Tasks** | **In Progress** | **167** | **108** | **59** | **65%** |

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
[ v1.8.0: Showcase & Resilience ] ─ VHS Demo, Textual 0.89+ Crash Resilience, Release Please Automation
              │
[ v1.9.0 / Phase 3.5: Engine ] ─── Stream Throttling, Disk Spooling, Tab/Queue Sync, Tree Usability
              │
[ v1.10.0: Mega-Course & Tools ] ── 6+ Adapters (dnspython, searchsploit, ffuf, nuclei), Schema 2.0, Theory Tabs, Wordlists, Local Lab
              │
[ v1.11.0: Terminal & Security ] ── Interactive PTY (pyte), AES Vault (cryptography), IPC Daemon, Graph (networkx)
              │
[ v2.0.0: Flagship Launch ] ────── Standalone Binaries, Jinja2/WeasyPrint Reports, Dulwich Git Diffs, DuckDB, Playwright
              │
[ Phase 4: Tactical Co-Pilot ] ─── sqlite-vec (Offline RAG), Scapy Packet Engine, Impacket AD Suite, Metasploit PTY
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
- [x] **Standard Finding Schema Library**: Created standard Pydantic models for cybersecurity entities ([`cyguide/schemas/`](../../cyguide/schemas)).
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
- [x] **Reactive Recommendation Engine (Historical - Decommissioned in Phase 3.5)**: Declarative suggestion rules proposing tools based on graph upsert events (superseded by Phase 4 on-demand `TargetAdvisor`).

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
- [x] **Comprehensive Automated Hermetic Suite**: Fully automated test coverage across unit, integration, and UI flows with zero warnings or external network dependencies ([`tests/`](../../tests)).
- [x] **Defense-in-Depth Security Hardening**: Remediated link-local cloud metadata SSRF vectors, enforced atomic `0o600` private permissions on settings/notes, expanded subprocess secret scrubbing, and neutralized LLM prompt tag breakouts ([`docs/developer/ARCHITECTURE.md:520`](ARCHITECTURE.md#L520), [`tests/unit/test_engine_executor.py`](../../tests/unit/test_engine_executor.py), [`tests/unit/test_gateway.py`](../../tests/unit/test_gateway.py)).

- [x] **Centralized Data Directory Architecture (`cyguide/paths.py`)**: Unified cross-platform application directory under `~/.cyguide` (or `$CYGUIDE_DATA_DIR`) preventing directory pollution ([`cyguide/paths.py`](../../cyguide/paths.py)).
- [x] **In-App Configuration Modal & Command Palette Providers (`ConfigModal`)**: Live tabbed settings editor for Ollama, Cloud AI, Database, and Custom Tools with Command Palette sub-palettes ([`cyguide/ui/screens/config_modal.py`](../../cyguide/ui/screens/config_modal.py)).
- [x] **Resilient Multi-Key Cloud AI Fallback & Cooldown Engine**: Automatic failover across multi-provider API keys and local Ollama fallback on rate-limiting (429) ([`cyguide/engine/explainer.py:208`](../../cyguide/engine/explainer.py#L208)).
- [x] **Interactive Split-Pane Edge Resizer (`ResizeHandle`)**: Draggable edge splitter dynamically resizing Entity Browser and Suggestions panes with width persistence ([`cyguide/ui/widgets/resizer.py`](../../cyguide/ui/widgets/resizer.py)).
- [x] **Forensic Session Archiving & Reopening Lifecycle**: Forensic read-only protection, status filters, and immutable audit event logging for closed sessions ([`cyguide/engine/store.py`](../../cyguide/engine/store.py), [`cyguide/engine/power_facade.py`](../../cyguide/engine/power_facade.py)).

---

### Release: v1.8.0 — Terminal Showcase, Textual Resilience & Automated Release (Completed)
- [x] **Visual Terminal Showcase Script (`demo.tape` via VHS)**: Scripted a repeatable Charm VHS recording capturing CyGuide startup, target selection, recipe execution, and graph exploration ([`demo.tape`](../../demo.tape), [`assets/demo.mp4`](../../assets/demo.mp4), [`assets/demo.gif`](../../assets/demo.gif), [`README.md`](../../README.md)).
- [x] **Upstream Textual 0.89+ Runtime Resilience & Event Guard**: Guarded against fatal `AttributeError: 'NoneType' object has no attribute 'region'` inside Textual's `Screen._forward_event` during Markdown table click interactions and AI streaming by disabling table selection (`MarkdownTableContent.ALLOW_SELECT = False`) and applying safe event forwarding fallback monkeypatch ([`cyguide/ui/compat.py`](../../cyguide/ui/compat.py), [`docs/developer/DEVELOPER_NOTES.md`](DEVELOPER_NOTES.md)).
- [x] **Learning Mode UI Stream Decoupling & Async Safety**: Throttled explainer Markdown pane rendering to 250ms micro-batches and properly awaited `explainer_pane.update()`, neutralizing race conditions and unhandled `asyncio.CancelledError` task crashes ([`cyguide/ui/screens/learning.py`](../../cyguide/ui/screens/learning.py), [`tests/unit/test_textual_compat.py`](../../tests/unit/test_textual_compat.py)).
- [x] **Automated Release Please Pipeline & Changelog Generation**: Integrated Google's Release Please action for automated semantic version bumping, CHANGELOG generation, and GitHub release tagging via Conventional Commits ([`.github/workflows/release.yml`](../../.github/workflows/release.yml)).

---

### Milestone: v1.9.0 (Phase 3.5) — Engine, Dataflow & Concurrency (Completed)

This critical hardening phase eliminates UI bottlenecks, decouples stream draining from terminal rendering, prevents RAM bloat during multi-hour/multi-day tasks, fixes tab lifecycle synchronization, and elevates the graph tree into a high-utility operator HUD:

#### Track 1: High-Volume Output & Streaming Resilience
- [x] **Throttled Log Ingestion (20–30 FPS Micro-Batching)**:
  - *Priority*: **P1** | *Complexity*: Medium
  - Batch incoming stdout chunks in a rolling queue flushed at max 20–30 FPS (every 33–50ms) instead of calling `RichLog.write()` on every 1KB chunk.
  - Prevents UI freezing when tools (like `ffuf`, `gobuster`, or aggressive port scans) emit tens of thousands of lines per second.
- [x] **Spill-to-Disk Log Streaming (`data/logs/{action_id}.log`)**:
  - *Priority*: **P1** | *Complexity*: Medium
  - Stream subprocess stdout directly to append-only disk files in real time.
  - Maintains $O(1)$ memory consumption so scans running for hours or days never cause RAM bloat or OOM crashes.
- [x] **Decouple Database Ingestion from Subprocess Executor (Deepening Candidate 1)**:
  - *Priority*: **P1** | *Complexity*: Medium
  - Remove direct SQLite `GraphStore.upsert_finding()` calls from `Executor._drain_stream` / `run_tool()`.
  - Turns `Executor` into a pure subprocess lifecycle engine yielding `BaseFinding` streams, eliminating connection teardown race conditions and enabling atomic micro-batched ingestion at the coordination seam.
- [x] **Capped UI Ring Buffer**:
  - *Priority*: **P1** | *Complexity*: Low
  - Keep a rolling window of the last 5,000 lines in the interactive UI terminal tab for instant rendering and smooth scrolling.
- [x] **Safe Event Log Archiving**:
  - *Priority*: **P2** | *Complexity*: Low
  - Cap the string payload stored in SQLite's `event_log` table (saving the tail + summary in the DB and linking the full disk log).

#### Track 2: Job Queue & Tab Lifecycle Synchronization
- [x] **Fix Tab Title Updating**:
  - *Priority*: **P1** | *Complexity*: Low
  - Replace the broken `#tab-{id}` query in `power.py` with Textual's native tab title API so workbench tabs update immediately whenever a new command is executed.
- [x] **Live Job Queue Tracking & Elapsed Runtime Counter**:
  - *Priority*: **P1** | *Complexity*: Medium
  - Sync the Job Queue to show active tab association, current tool command snippet, live elapsed time counter (`01h:24m:10s`), and status (`◯ RUNNING`, `● DONE`, `× FAILED`).
  - Automatically update the queue item when subsequent tasks execute in the same tab.

#### Track 3: Graph Tree Optimization & Usability
- [x] **Refined Widget Exception Boundaries (NoMatches Enforced)**:
  - *Priority*: **P1** | *Complexity*: Low
  - Replaced bare `except Exception: pass` across `DashboardScreen` and `PowerModeScreen` with specific `except NoMatches: pass` to eliminate silent DOM query masking without breaking on unmounted widgets.
- [x] **Zero-Rebuild Navigation**:
  - *Priority*: **P1** | *Complexity*: Low
  - Make `on_tree_node_highlighted` purely update the context bar variables (`$TARGET`, `$PORT`, `$SERVICE`).
  - Eliminate tree clearing (`self.root.clear()`) and tree rebuilding on arrow navigation, and prevent focus theft to `#command_input`.
- [x] **Dynamic Category Entity Counts**:
  - *Priority*: **P2** | *Complexity*: Low
  - Display live count badges on tree headers: `Targets (3)`, `Services (12)`, `Web (22)`, `Vulnerabilities (5)`.
- [x] **Tree Branch State Preservation**:
  - *Priority*: **P2** | *Complexity*: Medium
  - Retain user collapsed/expanded branch states across background finding updates.
- [x] **Inline Target Search / Filter**:
  - *Priority*: **P2** | *Complexity*: Medium
  - Add an inline search bar at the top of the Entity Browser to quickly search and filter discovered hosts, services, and endpoints.

#### Track 4: Event Debouncing, Batched Upserts & Database Concurrency
- [x] **Dashboard Highlight Debouncing**:
  - *Priority*: **P1** | *Complexity*: Low
  - Add 100ms debounce timer on workspace and session list highlight events so holding down arrow keys is silky smooth without flooding the event loop.
- [x] **Batched Finding Ingestion & UI Notification Coalescing**:
  - *Priority*: **P1** | *Complexity*: Medium
  - Buffer rapid tool finding streams into atomic micro-batches (e.g. flush every 250ms or 50 items) instead of executing individual SQLite transactions per finding.
  - Coalesce reactive UI refresh events to prevent rendering storms.
- [x] **Single-Query SQL Aggregates**:
  - *Priority*: **P2** | *Complexity*: Low
  - Replace per-session $N+1$ query loops in `show_workspace_details` with single `GROUP BY` aggregate queries in `GraphStore`.
- [x] **SQLite WAL Mode & Pragma Tuning**:
  - *Priority*: **P2** | *Complexity*: Low
  - Enable `PRAGMA journal_mode = WAL;`, `PRAGMA synchronous = NORMAL;`, and `PRAGMA busy_timeout = 5000;` in `GraphStore.initialize()` to prevent read/write database locks during concurrent tasks.

#### Track 5: Learning Mode Optimization, Targeted Explanations & Boundary Isolation
- [x] **Clean Text Rendering & Markdown Buffer Decoupling**:
  - *Priority*: **P1** | *Complexity*: Medium
  - Auto-clear or cleanly isolate previous explanation buffers upon new scan execution instead of infinitely concatenating text into an ever-expanding markdown string.
  - Eliminates $O(N^2)$ re-parsing of historical markdown tables and headings during streaming, preventing UI lag and screen jitter.
  - Cleanly erase intermediate status indicators (`*[Analyzing...]*`) when LLM tokens start streaming.
- [x] **Selective & Targeted Explanations ("Explain Certain Text, Not All")**:
  - *Priority*: **P1** | *Complexity*: Medium
  - Feed *structured findings* (open ports, discovered vulnerabilities, HTTP status anomalies) to the LLM rather than blindly slicing the last 80 lines of raw output.
  - Contextual snippet / line explanation: allow the student to highlight or select a specific finding, error, or flag output and request an explanation for just that item.
  - Automated noise stripping: filter out repetitive scanner banner headers, ASCII art, and progress bars before LLM prompting to save token costs and reduce latency.
- [x] **Robust Prompt Boundary Isolation & Input Sandboxing**:
  - *Priority*: **P1** | *Complexity*: Medium
  - Implement cryptographically randomized boundary tokens (e.g. `<<<UNTRUSTED_SCAN_OUTPUT_{UUID}>>>`) and XML/HTML escaping to ensure untrusted scan payloads cannot execute prompt injection attacks or break prompt boundaries.
  - Strict semantic demarcation separating System Directives, User Inquiries, and Untrusted Scanner Output.
- [x] **Collapse Shallow LearningModeEngine into Unified Action Gateway (Deepening Candidate 2)**:
  - *Priority*: **P1** | *Complexity*: Low
  - Eliminate redundant 49-line `LearningModeEngine` pass-through module; route Learning Mode tool executions through `ActionGateway` / `PowerWorkspaceFacade.submit_action()` to inherit SSRF policy validation, live job buffers, and unified logging.
- [x] **Eliminate Shallow LearningExplainer Wrapper (Deepening Candidate 3)**:
  - *Priority*: **P1** | *Complexity*: Low
  - Delete 10-line `LearningExplainer` indirection wrapper in `cyguide/engine/explainer.py` and unify callers directly against `MultiKeyCloudBackend.explain()` / `OllamaBackend.explain()`.
- [x] **UI Structural Boundaries & Visual Cards**:
  - *Priority*: **P2** | *Complexity*: Low
  - Refactor the right workbench pane into distinct visual containers with explicit border separations:
    1. Active Command Execution Context Header
    2. Structured Discovered Findings Summary
    3. AI Educational Breakdown & Flags Analysis
    4. Docked Interactive Tutor Chat.

---

### Milestone: v1.10.0 — Learning Mode Mega-Course, Schema 2.0 & Tool Ecosystem (Fast-Tracked)
*(14/23 tasks complete — 61%)*

> [!NOTE]
> Fast-tracked ahead of terminal PTY/IPC to prioritize pedagogical mastery, tool richness, and curriculum-grade cybersecurity instruction.
> Combines schema registry evolution, centralized wordlists, curriculum recipes, interactive theory briefings, offline local labs, and 6+ high-demand tool adapters.

#### Track 1: Schema Registry Evolution & Finding Expansion
- [x] **`exploit.reference` Schema Model**:
  - *Priority*: **P1** | *Complexity*: Low | *Track*: Schemas
  - Create Pydantic model for exploit intelligence capturing Exploit-DB ID, CVE cross-references, PoC code availability, platform (`linux`/`windows`/`webapps`), and verification status ([`cyguide/schemas/vulnerability.py:39`](../../cyguide/schemas/vulnerability.py#L39)).
- [x] **`web.technology` / `software.banner` Schema Model**:
  - *Priority*: **P1** | *Complexity*: Low | *Track*: Schemas
  - Create typed finding schema for web framework, CMS, application server, and runtime version detection with confidence scoring and CPE identifiers ([`cyguide/schemas/web.py:65`](../../cyguide/schemas/web.py#L65)).
- [x] **`audit.misconfig` Schema Model**:
  - *Priority*: **P1** | *Complexity*: Low | *Track*: Schemas
  - Create finding schema for policy violations, exposed `.git`/`.env` files, open directory listings, and cloud metadata exposures emitted by `nuclei` and `nikto` ([`cyguide/schemas/vulnerability.py:118`](../../cyguide/schemas/vulnerability.py#L118)).
- [x] **Schema Versioning & Flexible Key Anchoring (`schema_version = "1.0"`)**:
  - *Priority*: **P1** | *Complexity*: Medium | *Track*: Schemas
  - Add explicit `schema_version` to `BaseFinding` and support URL-anchored or target-flexible Primary Identity Keys (PIKs) for web-native findings. Update `scripts/generate_schema_registry.py` to auto-validate and regenerate documentation ([`cyguide/schemas/base.py:32`](../../cyguide/schemas/base.py#L32), [`docs/developer/SCHEMA_REGISTRY.md`](SCHEMA_REGISTRY.md)).

#### Track 2: Centralized Wordlist & Asset Subsystem
- [x] **Unified Wordlist Directory Architecture (`paths.get_default_wordlists_dir()`)**:
  - *Priority*: **P1** | *Complexity*: Low | *Track*: Assets
  - Centralize wordlists under `~/.cyguide/wordlists/` (or `$CYGUIDE_DATA_DIR/wordlists`) with `0o700` permissions, eliminating missing file errors in fuzzing tools ([`cyguide/paths.py:87`](../../cyguide/paths.py#L87)).
- [x] **Bundled High-Signal Starter Micro-Wordlists**:
  - *Priority*: **P1** | *Complexity*: Low | *Track*: Assets
  - Package minimal, high-utility dictionaries inside the CyGuide wheel (`common_dirs.txt`, `subdomains_500.txt`, `common_params.txt`, `common_passwords.txt`, `common_usernames.txt`) and auto-extract on initial launch or `cyg init` ([`cyguide/assets/wordlists/`](../../cyguide/assets/wordlists), [`cyguide/engine/wordlists.py:22`](../../cyguide/engine/wordlists.py#L22)).
- [x] **Dynamic Macro Wordlist Substitution in Recipes**:
  - *Priority*: **P1** | *Complexity*: Medium | *Track*: Engine / Recipes
  - Support named wordlist macros in recipe flags (e.g. `{wordlist:common_dirs}` → `~/.cyguide/wordlists/common_dirs.txt`) with automatic fallback to bundled lists and UI input overrides ([`cyguide/engine/wordlists.py:91`](../../cyguide/engine/wordlists.py#L91), [`cyguide/ui/screens/learning.py:102`](../../cyguide/ui/screens/learning.py#L102)).

#### Track 3: Tool Ecosystem Expansion & Contributor Scaffolding
- [x] **AI Adapter Authoring Skill (`adapter-authoring`)**:
  - *Priority*: **P1** | *Complexity*: Low | *Track*: Developer & Agent Experience
  - Dedicated agent skill and standalone authoring toolkit guiding the AI and developers to inspect target tool binaries/help/man-pages, map findings to CyGuide schemas, author deep `manifest.toml` files with curriculum-grade recipes & wire theory, implement `adapter.py` with streaming JSON or regex parsing, and generate hermetic pytest fixtures. Maintained in the independent [`cyguide-adapter-authoring`](https://github.com/h45sh/cyguide-adapter-authoring) project.
- [x] **Pure-Python DNS Recon Probe (`tools/dnspython/`)**:
  - *Priority*: **P1** | *Complexity*: Low | *Track*: Zero-Binary Probes
  - Built-in, zero-external-binary passive DNS resolver, reverse-lookup, and zone-transfer (AXFR) engine emitting `dns.record` findings directly into the entity graph ([`tools/dnspython/`](../../tools/dnspython)).
- [x] **SearchSploit Tool Adapter (`tools/searchsploit/`)**:
  - *Priority*: **P1** | *Complexity*: Low | *Track*: Tool Plugins
  - Command-line Exploit-DB integration querying local exploit archives for discovered `network.service` software versions via `--json`, directly emitting `exploit.reference` findings ([`tools/searchsploit/`](../../tools/searchsploit)).
- [x] **FFUF Tool Adapter (`tools/ffuf/`)**:
  - *Priority*: **P1** | *Complexity*: Low | *Track*: Tool Plugins
  - High-performance Go web fuzzer alternative to `gobuster`, leveraging v1.9.0 log batching and named wordlists. Emits `web.endpoint` and `audit.misconfig` ([`tools/ffuf/`](../../tools/ffuf)).
- [x] **Nuclei Vulnerability Scanner (`tools/nuclei/`)**:
  - *Priority*: **P1** | *Complexity*: Medium | *Track*: Tool Plugins
  - Fast, template-based vulnerability scanning using community YAML signatures. Emits `vulnerability.found`, `web.technology`, and `audit.misconfig` ([`tools/nuclei/`](../../tools/nuclei)).
- [ ] **SQLMap Tool Adapter (`tools/sqlmap/`)**:
  - *Priority*: **P2** | *Complexity*: High | *Track*: Tool Plugins
  - Automated SQL injection detection and database takeover with `--batch` non-interactive execution. Emits `vulnerability.found` (SQLi) and `credential.found`.
- [ ] **NetExec (`nxc`) Network Spraying Adapter (`tools/netexec/`)**:
  - *Priority*: **P2** | *Complexity*: Medium | *Track*: Tool Plugins
  - High-performance multi-protocol credential spraying and Active Directory enumeration across SMB, SSH, WinRM, and LDAP, emitting `credential.found` and `host.internal` models.
- [x] **Hermetic Mock Scanner Testbed (`tests/fixtures/mock_tools/`)**:
  - *Priority*: **P1** | *Complexity*: Medium | *Track*: Testing / Reliability
  - Pre-recorded CLI output dumps and mock runner fixtures across `nmap`, `gobuster`, `nikto`, `subfinder`, `whois`, `nuclei`, `searchsploit`, `ffuf`, and `dnspython` to run full end-to-end adapter tests in CI without requiring live binaries or internet connectivity ([`tests/fixtures/mock_tools/`](../../tests/fixtures/mock_tools), [`tests/unit/test_parsers/`](../../tests/unit/test_parsers)).

#### Track 4: Learning Mode Mega-Course, Theory Primer & Socratic AI
- [x] **Curriculum-Grade Recipe Taxonomy & Theory Metadata**:
  - *Priority*: **P1** | *Complexity*: Medium | *Track*: Learning Mode
  - Upgrade `manifest.toml` recipe specifications with `difficulty`, `track`, `concepts`, `wire_summary`, RFC standards references, and blue-team `remediation_guide`. Expand each tool to 4–6 progressive educational recipes ([`cyguide/engine/manifest.py:17`](../../cyguide/engine/manifest.py#L17), [`tools/`](../../tools)).
- [ ] **Interactive Theory & Protocol Deep Dive Tab**:
  - *Priority*: **P1** | *Complexity*: Medium | *Track*: Learning Mode
  - Add a dedicated third tab in Learning Mode (`Theory & Deep Dive`) displaying OSI layer packet flows, protocol state machines (TCP 3-way handshake vs SYN teardown, DNS recursion vs AXFR, HTTP header injection), and RFC briefings before execution.
- [ ] **Socratic AI Tutor & Guided Exploration**:
  - *Priority*: **P1** | *Complexity*: Medium | *Track*: Learning Mode / AI
  - Implement toggleable "Socratic Tutor" persona in the AI Explainer pane that prompts students with analytical questions about findings (e.g., assessing version risk, HTTP redirect chains) and guides next steps rather than just dumping static summaries.
- [ ] **Dual-Lens Perspective: Offense vs Blue-Team Defense**:
  - *Priority*: **P2** | *Complexity*: Low | *Track*: Learning Mode
  - Provide a toggleable "Defender's Lens" detailing how the scan appears in SIEM/IDS telemetry (Snort, Suricata, Zeek) and exact configuration hardening steps to remediate discovered risks.
- [ ] **Curriculum Syllabus & Mastery Progress Tracking**:
  - *Priority*: **P2** | *Complexity*: Medium | *Track*: Learning Mode
  - Group recipes into sequential learning tracks (Network Discovery, DNS Mapping, Web Fuzzing, Vuln Auditing, Exploit Research) with progress tracking saved in `~/.cyguide/settings.json`, displaying mastery badges and completion percentages.
- [ ] **Pre-flight Dependency & Parameter Verification**:
  - *Priority*: **P1** | *Complexity*: Low | *Track*: Learning Mode
  - Validate required binaries, wordlists, and target variables before execution, offering one-click remediation or guidance if an asset is missing.

#### Track 5: Hermetic Local Lab & Target Sandboxes
- [ ] **Built-in Mock Target Lab Server (`cyg lab start`)**:
  - *Priority*: **P1** | *Complexity*: Medium | *Track*: Local Lab
  - Lightweight embedded asyncio loopback server running on `127.0.0.1:8888` simulating realistic web endpoints, HTTP headers, `/robots.txt`, and sample vulnerabilities for 100% legal, offline student practice.
- [ ] **Interactive Concept Challenges / Flag Verification**:
  - *Priority*: **P2** | *Complexity*: Low | *Track*: Local Lab
  - Embedded scenario checks verifying students understand why a scan returned specific responses (e.g., distinguishing 403 Forbidden from 404 Not Found, identifying stealth scan packet resets).

---

### Milestone: v1.11.0 — Advanced Terminal Capabilities, IPC & Security/Encryption (Planned)

> [!NOTE]
> Detailed technical specifications, data models, and sequence flows are documented in [`docs/developer/V2_PLATFORM_SPECIFICATION.md:36-160`](V2_PLATFORM_SPECIFICATION.md#L36-L160).

- [ ] **Dual-Path Interactive PTY Architecture (`pyte` + `ptyprocess`)**:
  - *Priority*: **P1** | *Complexity*: High | *Track*: Terminal
  - Implement OS pseudo-terminal pair (`master_fd`/`slave_fd`) via `os.openpty()` / `ptyprocess` in `Executor` for interactive commands, replacing `stdin=DEVNULL`.
  - Use `pyte` in-memory VT102/xterm screen emulator to maintain ANSI escape codes, cursor positions, and color buffers for interactive prompts (`sudo`, `ssh`, `[y/N]` confirmations, and live bash shells) inside workbench tabs.
- [ ] **Terminal Window Resize Signals (`SIGWINCH`)**:
  - *Priority*: **P1** | *Complexity*: Medium | *Track*: Terminal
  - Forward terminal geometry adjustments to the active PTY via `fcntl.ioctl` with `termios.TIOCSWINSZ` on UI pane resize.
- [ ] **In-TUI Syntax Highlighting for Loot & Exploits (`pygments`)**:
  - *Priority*: **P2** | *Complexity*: Low | *Track*: UI / Detail Dock
  - Integrate `pygments` lexers to provide rich syntax highlighting for captured credentials, extracted `.env`/config files, and exploit code snippets within the TUI detail and scratchpad views.
- [ ] **Attack Path & Blast-Radius Engine (`networkx`)**:
  - *Priority*: **P1** | *Complexity*: Low | *Track*: Graph Analytics
  - Build an in-memory directed graph wrapper (`networkx.DiGraph`) over SQLite nodes and edges to compute shortest attack paths (`nx.shortest_path`) from entrypoints to critical assets, and calculate compromise blast radiuses (`nx.descendants`).
- [ ] **Native TLS/SSL Certificate Inspector (`cryptography`)**:
  - *Priority*: **P2** | *Complexity*: Low | *Track*: Zero-Binary Probes
  - Pure-Python TLS certificate inspection for HTTPS services extracting Subject Alternative Names (SANs), issuer information, and validity periods without external CLI dependencies.
- [ ] **Decoupled Asynchronous IPC & Daemon Architecture**:
  - *Priority*: **P1** | *Complexity*: High | *Track*: Architecture
  - Decouple background command execution from the Textual UI loop via an internal event bus and optional Unix domain socket (`~/.cyguide/run/cyguide.sock`).
  - Allows background scans to continue across UI reloads and enables headless external triggers.
- [ ] **Unify Split Workspace & Session Management (Deepening Candidate 4)**:
  - *Priority*: **P2** | *Complexity*: Medium | *Track*: Architecture / IPC
  - Consolidate parallel entity operations currently split across `GraphStore` and `PowerWorkspaceFacade` in dashboard views into a single deep Workspace/Session repository seam, designed to serve both the local TUI and the Unix domain socket IPC daemon.
- [ ] **Encrypted Session Archives (`cyg export --encrypt` via `cryptography`)**:
  - *Priority*: **P1** | *Complexity*: Medium | *Track*: Security
  - Add AES-256-GCM authenticated encryption for exported session databases with Argon2id passphrase key derivation using Python's `cryptography` package.
- [ ] **Zero-Leakage In-Memory Credential Scrubbing**:
  - *Priority*: **P2** | *Complexity*: Low | *Track*: Security
  - Scrub transient credentials, secret tokens, and API keys from memory upon task completion.
- [ ] **Declarative CIDR Scope Enforcement**:
  - *Priority*: **P1** | *Complexity*: Medium | *Track*: Security
  - Add explicit CIDR whitelist boundary validation in `ActionGateway` (e.g. `allowed_cidrs: ["10.0.0.0/24"]`) to reject out-of-scope targets.
- [x] **LLM Prompt Boundary Sandboxing**:
  - *Priority*: **P1** | *Complexity*: Medium | *Track*: AI Safety
  - Enclose untrusted terminal output in ephemeral cryptographically randomized tokens (`<<<UNTRUSTED_SCAN_OUTPUT_{UUID}>>>`) with XML escaping to neutralize prompt injections.
- [ ] **Cross-Session Approval Context Swapping**:
  - *Priority*: **P2** | *Complexity*: Low | *Track*: UI/UX
  - Automatically swap the active TUI session context when approving suggestions originated from another session in the global graph.
- [ ] **Encrypted Archive Integrity & Tamper Fuzzing**:
  - *Priority*: **P2** | *Complexity*: Medium | *Track*: Security / Reliability
  - Automated test suite verifying cryptographic rejection of truncated, bit-flipped, or maliciously crafted session archives (Argon2id + AES-256-GCM auth tag failures).

---

### Milestone: v2.0.0 — The Mature Flagship Platform & Public Launch (Planned)

> [!NOTE]
> Detailed packaging specifications and launch playbooks are documented in [`docs/developer/V2_PLATFORM_SPECIFICATION.md:194-245`](V2_PLATFORM_SPECIFICATION.md#L194-L245).

- [ ] **Standalone Linux Binary Distribution (`cyguide-linux-x86_64`)**:
  - *Priority*: **P1** | *Complexity*: Medium | *Track*: Distribution
  - Configure GitHub Actions workflow building portable single-file binary releases via PyInstaller/Shiv with zero Python dependency requirements.
- [ ] **Executive & Technical Pentest Reporting (`jinja2` + `weasyprint` / `typst-py`)**:
  - *Priority*: **P1** | *Complexity*: Medium | *Track*: Reporting
  - Template-driven HTML and PDF report generator producing formal client-ready pentest deliverables with CVSS scorecards, attack path charts, and finding evidence tables.
- [ ] **Pure-Python Git Engagement Versioning (`dulwich`)**:
  - *Priority*: **P2** | *Complexity*: Low | *Track*: Versioning / Diffing
  - Automatic silent Git versioning of target graphs under `~/.cyguide/workspaces/<ws_id>/.git`, enabling time-travel delta comparisons (`cyg diff`) across sessions.
- [ ] **Analytical Log & Wordlist Search Engine (`duckdb`)**:
  - *Priority*: **P2** | *Complexity*: Medium | *Track*: Scale / Analytics
  - In-process analytical database engine enabling sub-millisecond queries across 500k+ wordlists, fuzzing logs, and large-scale subnet sweeps.
- [ ] **Headless DOM & Screenshot Extractor (`playwright`)**:
  - *Priority*: **P3** | *Complexity*: Medium | *Track*: Deep Web Recon
  - Optional deep web reconnaissance worker extracting form fields, auth tokens, client-side frameworks, and page captures.
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
- [ ] **Architectural Boundary Linting & Import Isolation**:
  - *Priority*: **P2** | *Complexity*: Low | *Track*: Codebase Integrity
  - Automated CI check enforcing import isolation: `tools/` adapters cannot import UI or SQLite layers, and `cyguide.schemas` cannot depend on external execution logic.
- [ ] **LLM Anti-Injection & Golden Dataset Evaluation**:
  - *Priority*: **P2** | *Complexity*: Medium | *Track*: AI Safety & Reliability
  - Automated evaluation harness testing LLM Explainer and future ReAct agents against golden benchmark scan outputs to ensure prompt boundaries (`<<<UNTRUSTED_SCAN_OUTPUT>>>`) neutralize injection payloads and maintain schema compliance.

---

### Phase 4: Tactical Security Research Co-Pilot & Offensive Engine (Post-v2.0.0)

Evolves CyGuide into an **Augmented Security Research Cockpit** engineered for hypothesis-driven investigation, offline intelligence, and tactical offensive workflows:

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

#### Track 4: Target Intelligence & On-Demand Advisor Architecture
- [x] **Decommission Legacy Heuristic Recommendation Engine**:
  - *Priority*: **P1** | *Complexity*: Low | *Track*: Architecture / Engine
  - Disconnect `store.on_upsert(self.recommendation_engine.handle_upsert)` from `cyguide/app.py` and retire static 4-rule background execution.
  - Eliminates silent SQLite writes of unviewed `proposed` nodes during high-volume tool execution.
- [ ] **On-Demand Neuro-Symbolic Target Advisor (`TargetAdvisor`)**:
  - *Priority*: **P1** | *Complexity*: Medium | *Track*: Architecture / Intelligence
  - Operator-triggered target advice (via Command Palette or shortcut on selected Entity Browser node) rather than noisy background spam.
  - Assembles structured entity briefs (ports, technology banners, OS signatures, existing findings) and feeds them to the Explainer/ReAct agent for contextual next steps.
  - All recommended actions must pass through `ActionGateway` for deterministic CIDR boundary enforcement, SSRF prevention, and parameter validation before execution.
- [ ] **Cross-Session Approval Context Swapping**:
  - *Priority*: **P2** | *Complexity*: Low | *Track*: UI / Workbench
  - Automatically switch active TUI session when approving a suggested action originating from another session to maintain variable resolution integrity.

#### Track 5: Offline Knowledge & Advanced Offensive Probes
- [ ] **Embedded Offline Security Knowledge Base & RAG (`sqlite-vec`)**:
  - *Priority*: **P1** | *Complexity*: Medium | *Track*: Offline Knowledge
  - Integrate `sqlite-vec` vector embeddings directly in SQLite to store offline MITRE ATT&CK techniques, Exploit-DB titles, and HackTricks checklists for instant local semantic search on discovered services without internet access.
- [ ] **Native Packet Crafting & Stealth Network Engine (`scapy`)**:
  - *Priority*: **P2** | *Complexity*: Medium | *Track*: Offensive Engine
  - Pure-Python stealth TCP SYN scanning, custom port-knocking sequences, and local ARP network sniffing with zero external binary dependencies.
- [ ] **Enterprise Active Directory Protocol Suite (`impacket`)**:
  - *Priority*: **P2** | *Complexity*: High | *Track*: Enterprise Offensive
  - Python-native Active Directory assessment engine providing Kerberoasting, AS-REP roasting, and SMB/RPC interaction commands within the CyGuide workbench.
- [ ] **Metasploit Interactive Session Integration (`msfconsole` via PTY)**:
  - *Priority*: **P2** | *Complexity*: Medium | *Track*: Exploit Console
  - Dedicated PTY tab integration for managing active Metasploit shells, meterpreter sessions, and payload handlers directly from the CyGuide workbench.

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

## Job-First Engineering & Market Mastery Track

An applied, portfolio-anchored curriculum translating CyGuide's real production architecture into interview-ready software engineering, DevSecOps, and backend systems competencies.

```text
Track 1: Async Storage & DB Architecture  ➜  Track 2: CI/CD & DevSecOps Pipeline  ➜  Track 3: System Design & APIs
 (aiosqlite, Pydantic, Transactions)           (GitHub Actions, Docker, Security)      (httpx, Caching, Rate Limiting)
                                                ▲
                           [ Ongoing: Target DSA (NeetCode 75 Core) ]
```

### Track 1: Database & Storage Architecture (In `cyguide`)
*Job Skills:* **SQL, Schema Design, Concurrency, Async I/O, Pydantic Data Modeling**
- [x] **Relational Graph Modeling & Canonical Identity Hashing**: Implemented deterministic SHA-256 Primary Identity Key (PIK) algorithms preventing duplication across independent tool sources ([`cyguide/engine/store.py`](../../cyguide/engine/store.py)).
- [ ] **Async I/O Concurrency & Connection Pooling**: Master non-blocking event-loop I/O with `aiosqlite`, write-ahead logging (WAL), and evaluate async connection pool lifecycles under heavy concurrent load.
  - *Interview Competency:* Explaining how asynchronous event loops schedule file/socket I/O without blocking worker threads, and preventing SQLite `busy` locks under concurrency.
- [ ] **Schema Migrations & Transactional Integrity**: Implement declarative schema versioning and transactional rollback semantics for multi-table graph mutations.
  - *Interview Competency:* Designing normalized schemas, foreign-key cascades, atomic transactions, and handling schema migrations without downtime.

### Track 2: DevSecOps, CI/CD & Packaging (In `cyguide`)
*Job Skills:* **GitHub Actions, Docker, Static Analysis (SAST), Supply Chain Security**
- [x] **Hermetic CI/CD & Security Pipelines**: Configured end-to-end multi-platform test matrices, CodeQL SAST scanning, and Release Please semantic changelog tagging ([`.github/workflows/`](../../.github/workflows)).
- [ ] **Container Hardening & Multi-Stage Builds**: Review and optimize [`Dockerfile`](../../Dockerfile) for minimal image footprint (`python:3.11-slim`), non-root execution permissions, and layer cache reuse.
  - *Interview Competency:* Explaining container isolation, Linux namespaces/cgroups, non-root runtime defense, and attack surface reduction.
- [ ] **Automated Supply Chain & Dependency CVE Gate**: Enforce strict pre-merge gates using `pip-audit` to block vulnerabilities in upstream dependencies and lockfiles.
  - *Interview Competency:* Explaining software supply chain security, SBOM generation, and automated vulnerability triage in modern CI pipelines.

### Track 3: System Design & Network Integrations (In `cyguide`)
*Job Skills:* **API Design, HTTP/REST, Caching, Resilience & Error Handling**
- [x] **Unified Multi-Provider Async Client**: Streamed completions from Ollama and cloud providers with fallback cooldowns ([`cyguide/engine/explainer.py`](../../cyguide/engine/explainer.py)).
- [ ] **Network Resilience, Retries & Exponential Backoff**: Implement jittered exponential backoff and circuit-breaker patterns for external LLM API endpoints and web fetchers using `httpx`.
  - *Interview Competency:* Designing distributed systems for graceful degradation under third-party outages, rate limits (HTTP 429), and network partitions.
- [ ] **Analytical In-Memory Caching & Telemetry**: Integrate structured contextual logging and query response caching to minimize latency across repeated graph lookups.
  - *Interview Competency:* Demonstrating end-to-end observability, distributed tracing concepts, and latency optimization via caching layers.

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
| `cyguide/modes/` | N/A | Legacy mode engine stubs (`power.py`, `learning.py`) | **Resolved**: Completely removed redundant `cyguide/modes/` package; execution routes through `ActionGateway` and `PowerWorkspaceFacade`. |

---

## Architectural & Specification References

For detailed architecture specifications, system contracts, and execution pipelines:
* **[System Architecture Blueprint](ARCHITECTURE.md)**
* **[Platform Specification & Dataflow Engine](V2_PLATFORM_SPECIFICATION.md)**
* **[Database Architecture & Relational Contracts](DATABASE.md)**
* **[Standard Schema Registry](SCHEMA_REGISTRY.md)**
