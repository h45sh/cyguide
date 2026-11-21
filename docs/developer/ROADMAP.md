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
| **v1.10.0: Learning Mode Mega-Course, Schema 2.0 & Tools** | **Completed (Remaining on hold for v1.11+)** | 32 | 28 | 4 | 88% |
| **v1.11.0: Advanced Terminal Capabilities, IPC & Security** | **Active Next Phase** | 22 | 11 | 11 | 50% |
| **v2.0.0: Mature Flagship Release & Public Launch** | **Planned (Spec Ready)** | 12 | 0 | 12 | 0% |
| **Phase 4: Tactical Research Co-Pilot & Offensive Engine** | **Planned (Future)** | 15 | 1 | 14 | 7% |
| **Phase 5: Multi-Agent Swarms & Collaborative Intel** | **Planned (Future)** | 6 | 0 | 6 | 0% |
| **Total Project Tasks** | **In Progress** | **176** | **125** | **51** | **71%** |

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

### Delivered Platform Architecture & Core Foundations (Completed)

All baseline architectural foundations across the engine, dataflow, security, and UI have been delivered and verified:

* **Smart-Adapter Architecture**: Implemented decoupled "Smart Adapter / Stupid Framework" isolating security CLI tools from engine logic ([`cyguide/engine/adapter.py`](../../cyguide/engine/adapter.py)).
* **Reactive SQLite Graph Store**: Relational `GraphStore` with deterministic SHA-256 Primary Identity Key (PIK) upserting, edge auto-wiring, and WAL mode ([`cyguide/engine/store.py`](../../cyguide/engine/store.py)).
* **Asynchronous Process Execution Engine**: Pure subprocess execution engine with real-time stream draining, output ring-buffering, and zero memory leaks ([`cyguide/engine/execution_session.py`](../../cyguide/engine/execution_session.py)).
* **Dual-Mode Textual TUI**: Advanced Operator Workbench (Power Mode) and Guided Curriculum (Learning Mode) with 60 FPS fluid edge resizing and split panes ([`cyguide/ui/`](../../cyguide/ui)).
* **Security Tool Ecosystem**: 11 production adapters with typed finding parsers, structured manifests, and curriculum recipes: `nmap`, `gobuster`, `nikto`, `whois`, `subfinder`, `nuclei`, `ffuf`, `searchsploit`, `sqlmap`, `netexec`, and `dnspython` ([`tools/`](../../tools)).
* **Unified Headless CLI 2.0**: Decoupled POSIX command architecture with domain modules (`cyg workspace`, `cyg session`, `cyg tool`, `cyg lab`, `cyg doctor`) and universal `--json` serialization ([`cyguide/cli/`](../../cyguide/cli)).
* **Algorithmic Deep Module**: Bitwise Patricia Radix Trie (`IPRadixTrie`), Disjoint-Set Union (`DisjointSet`), MinHash similarity, 0/1 Knapsack token optimizer (`knapsack_01`), and counting Bloom filter (`BloomFilter`) consolidated in [`cyguide/common/algorithms.py`](../../cyguide/common/algorithms.py).
* **Graph Intelligence Engine**: In-memory `GraphAnalyticsEngine` providing Brandes betweenness centrality, Tarjan strongly connected components (SCC), shortest attack paths, and blast radius calculation ([`cyguide/engine/graph_analytics.py`](../../cyguide/engine/graph_analytics.py)).
* **Preflight Verification**: Pure validation engine with one-click remediation cards for missing packages, unseeded wordlists, or syntax issues ([`cyguide/engine/preflight.py`](../../cyguide/engine/preflight.py)).
* **Defense-in-Depth Security**: Subprocess environment scrubbing stripping cloud and API credentials, strict link-local and cloud metadata IP/DNS blocking, and declarative CIDR scope enforcement ([`cyguide/engine/gateway.py`](../../cyguide/engine/gateway.py)).
* **Session Portability & Universal Checkpoints**: Atomic zero-copy session export/import via SQLite `ATTACH DATABASE`, standalone `.cyglab` archives, and automated Markdown report generation ([`cyguide/engine/reporter.py`](../../cyguide/engine/reporter.py)).
* **Multi-Provider AI Fallback Engine**: Local offline Ollama integration alongside cloud AI providers (OpenAI, Anthropic, Gemini, DeepSeek, Groq) with prompt boundary sanitization and token budget caps ([`cyguide/engine/explainer.py`](../../cyguide/engine/explainer.py)).

---

### Milestone: v1.11.0 — Advanced Terminal Capabilities, IPC & Security/Encryption (Planned)

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
- [x] **Attack Path & Blast-Radius Engine (`networkx`)**:
  - *Priority*: **P1** | *Complexity*: Low | *Track*: Graph Analytics
  - Built an in-memory directed graph intelligence engine (`GraphAnalyticsEngine`) over SQLite nodes and edges to compute shortest attack paths (`find_shortest_attack_path`) from perimeter entrypoints to critical assets, calculate compromise blast radiuses (`calculate_blast_radius`), and integrate seamlessly with `PowerWorkspaceFacade` and optional `networkx` ([`cyguide/engine/graph_analytics.py`](../../cyguide/engine/graph_analytics.py), [`tests/unit/test_graph_analytics.py`](../../tests/unit/test_graph_analytics.py)).
- [x] **Graph Centrality, Choke Points & Strongly Connected Components**:
  - *Priority*: **P1** | *Complexity*: Low | *Track*: Graph Analytics
  - Implemented Brandes' $O(V \cdot E)$ betweenness centrality (`calculate_betweenness_centrality`), Tarjan's $O(V + E)$ strongly connected components (`find_strongly_connected_components`), and transitive reachability closure matrix in [`cyguide/engine/graph_analytics.py`](../../cyguide/engine/graph_analytics.py) to detect dual-homed pivot hosts, bridge nodes, and circular vulnerability dependencies.
- [x] **Bitwise Patricia Radix Trie (`IPRadixTrie`) & Fast SSRF/CIDR Gating**:
  - *Priority*: **P1** | *Complexity*: Low | *Track*: Security / Performance
  - Implemented binary Patricia Radix Trie in [`cyguide/common/algorithms.py`](../../cyguide/common/algorithms.py) yielding sub-microsecond $O(W)$ longest-prefix matching for IPv4 (32-bit) and IPv6 (128-bit) addresses and CIDRs, elevating SSRF and metadata defense checks to 2.6M - 6.7M ops/sec.
- [x] **Table-Driven DFA ANSI Stream Parser (`dfa_strip_ansi`)**:
  - *Priority*: **P1** | *Complexity*: Low | *Track*: Terminal / Performance
  - Replaced regex ANSI cleaning with table-driven ECMA-48 state machine in [`cyguide/common/__init__.py`](../../cyguide/common/__init__.py), eliminating regex engine invocation and rendering terminal stream ingestion 100% immune to catastrophic backtracking.
- [x] **0/1 Knapsack Context Window Token Optimizer (`knapsack_01`)**:
  - *Priority*: **P1** | *Complexity*: Low | *Track*: AI / Performance
  - Dynamic programming 0/1 Knapsack solver in [`cyguide/common/algorithms.py`](../../cyguide/common/algorithms.py) and [`cyguide/engine/context_builder.py`](../../cyguide/engine/context_builder.py) providing optimal finding utility subset selection within LLM token constraints.
- [x] **Probabilistic GraphStore Query Filter (`BloomFilter`)**:
  - *Priority*: **P1** | *Complexity*: Low | *Track*: Database / Performance
  - Implemented optimal counting & standard Bloom filter in [`cyguide/common/algorithms.py`](../../cyguide/common/algorithms.py) and integrated into `GraphStore.upsert_findings_batch` ([`cyguide/engine/store.py`](../../cyguide/engine/store.py)), skipping SQLite node lookups for novel finding IDs with 0% false negatives.
- [x] **Fluid Sidebar Geometry, Debounced Persistence & Layout Containment**:
  - *Priority*: **P1** | *Complexity*: Medium | *Track*: UI/UX / Performance
  - Implemented 400ms trailing write-behind settings debounce in [`cyguide/app.py`](../../cyguide/app.py), deadband column filtering in [`cyguide/ui/widgets/resizer.py`](../../cyguide/ui/widgets/resizer.py), transition decoupling (`-resizing`, `-fast-stepping`), and breakpoint tier memoization in [`cyguide/ui/screens/learning.py`](../../cyguide/ui/screens/learning.py) and [`cyguide/ui/screens/power.py`](../../cyguide/ui/screens/power.py) achieving 60 FPS buttery-smooth pane transitions.
- [ ] **Native TLS/SSL Certificate Inspector (`cryptography`)**:
  - *Priority*: **P2** | *Complexity*: Low | *Track*: Zero-Binary Probes
  - Pure-Python TLS certificate inspection for HTTPS services extracting Subject Alternative Names (SANs), issuer information, and validity periods without external CLI dependencies.
- [ ] **Decoupled Asynchronous IPC & Daemon Architecture**:
  - *Priority*: **P1** | *Complexity*: High | *Track*: Architecture
  - Decouple background command execution from the Textual UI loop via an internal event bus and optional Unix domain socket (`~/.cyguide/run/cyguide.sock`).
  - Allows background scans to continue across UI reloads and enables headless external triggers.
- [x] **Unify Split Workspace & Session Management (Deepening Candidate 4)**:
  - *Priority*: **P2** | *Complexity*: Medium | *Track*: Architecture / IPC
  - Consolidate parallel entity operations currently split across `GraphStore` and `PowerWorkspaceFacade` in dashboard views into a single deep Workspace/Session repository seam, designed to serve both the local TUI and the Unix domain socket IPC daemon ([`cyguide/engine/workspace_repository.py`](../../cyguide/engine/workspace_repository.py), [`tests/unit/test_workspace_repository.py`](../../tests/unit/test_workspace_repository.py)).
- [ ] **Encrypted Session Archives (`cyg session export --encrypt` via `cryptography`)**:
  - *Priority*: **P1** | *Complexity*: Medium | *Track*: Security
  - Add AES-256-GCM authenticated encryption for exported session databases with Argon2id passphrase key derivation using Python's `cryptography` package.
- [ ] **Zero-Leakage In-Memory Credential Scrubbing**:
  - *Priority*: **P2** | *Complexity*: Low | *Track*: Security
  - Scrub transient credentials, secret tokens, and API keys from memory upon task completion.
- [x] **Declarative CIDR Scope Enforcement**:
  - *Priority*: **P1** | *Complexity*: Medium | *Track*: Security
  - Added explicit CIDR boundary validation in `ActionGateway` (`allowed_cidrs: ["10.0.0.0/8"]`) rejecting out-of-scope targets and entity IPs before subprocess dispatch ([`cyguide/engine/gateway.py`](../../cyguide/engine/gateway.py), [`tests/unit/test_gateway.py`](../../tests/unit/test_gateway.py)).
- [x] **LLM Prompt Boundary Sandboxing**:
  - *Priority*: **P1** | *Complexity*: Medium | *Track*: AI Safety
  - Enclose untrusted terminal output in ephemeral cryptographically randomized tokens (`<<<UNTRUSTED_SCAN_OUTPUT_{UUID}>>>`) with XML escaping to neutralize prompt injections.
- [ ] **Cross-Session Approval Context Swapping**:
  - *Priority*: **P2** | *Complexity*: Low | *Track*: UI/UX
  - Automatically swap the active TUI session context when approving suggestions originated from another session in the global graph.
- [ ] **Encrypted Archive Integrity & Tamper Fuzzing**:
  - *Priority*: **P2** | *Complexity*: Medium | *Track*: Security / Reliability
  - Automated test suite verifying cryptographic rejection of truncated, bit-flipped, or maliciously crafted session archives (Argon2id + AES-256-GCM auth tag failures).
- [x] **Automated CI Performance Regression Gate (`scripts/generate_benchmark_report.py --check`)**:
  - *Priority*: **P1** | *Complexity*: Low | *Track*: Benchmarking / Quality Gate
  - Integrate benchmark checks into GitHub Actions PR workflow to automatically block merges on critical regressions across cold start, streaming ingestion, or SQLite batching ([`scripts/generate_benchmark_report.py`](../../scripts/generate_benchmark_report.py), [`.github/workflows/ci.yml:109`](../../.github/workflows/ci.yml#L109)).
- [ ] **Continuous Memory RSS & Heap Profiling**:
  - *Priority*: **P2** | *Complexity*: Medium | *Track*: Performance / Reliability
  - Profile sustained resident memory (RSS) and Python heap allocation over 50,000+ line scanner runs, verifying zero leak accumulation under long-running daemon workloads.
- [ ] **Multi-Session Concurrent Background Benchmark**:
  - *Priority*: **P2** | *Complexity*: Medium | *Track*: Concurrency / Performance
  - Benchmark SQLite WAL lock contention and CPU utilization when executing 5+ parallel tool adapters simultaneously across multiple tabs.

---

### Milestone: v2.0.0 — The Mature Flagship Platform & Public Launch (Planned)

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
- [x] **Declarative CIDR Scope Enforcement**:
  - *Priority*: **P1** | *Complexity*: Medium
  - Implemented explicit CIDR whitelist boundary validation in `ActionGateway` ([`cyguide/engine/gateway.py`](../../cyguide/engine/gateway.py)).
  - Automatically rejects actions targeting IP addresses outside authorized engagement bounds before subprocess execution.

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
- [x] **Session Export & Import**: Atomic SQLite `.db` archive portability (`cyg session export`, `cyg session import`, and `Ctrl+E`).
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
* **[Database Architecture & Relational Contracts](DATABASE.md)**
* **[Standard Schema Registry](SCHEMA_REGISTRY.md)**
