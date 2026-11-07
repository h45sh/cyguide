# CyGuide Documentation Hub

Welcome to the CyGuide documentation portal. CyGuide is an open-source Terminal User Interface (TUI) platform for cybersecurity education, tool orchestration, and stateful reconnaissance analysis.

Our documentation is structured according to the **[Diátaxis Framework](https://diataxis.fr/)**, dividing technical information into four distinct modes: **Tutorials**, **How-To Guides**, **Reference**, and **Explanation**.

---

## Documentation Navigation

```text
                                  PRACTICAL
                                     ▲
                                     │
           Tutorials                 │             How-To Guides
     (Learning-Oriented)             │          (Problem-Oriented)
  "Show me how to get started"       │      "Show me how to solve a task"
                                     │
 ────────────────────────────────────┼────────────────────────────────────
                                     │
             Explanation             │               Reference
     (Understanding-Oriented)        │         (Information-Oriented)
   "Help me understand how it works" │     "Give me the technical specs"
                                     │
                                     ▼
                                THEORETICAL
```

---

### 1. Tutorials (Learning-Oriented)
Step-by-step lessons designed to take you through your first successful investigation:

* **[Quickstart & First Reconnaissance](user/USER_MANUAL.md#1-getting-started--the-dashboard)**: Launch CyGuide, initialize a workspace, and discover your first target host and open services.
* **[Guided Learning Mode](user/USER_MANUAL.md#3-learning-mode-guided-cybersecurity-curriculum)**: Work through curated security tool recipes, inspect flag breakdowns, and receive real-time AI tutor explanations.

---

### 2. How-To Guides (Task-Oriented)
Practical recipes for accomplishing specific operational goals:

* **[Multi-Distribution Installation](README.md#installing-security-tools--dependencies)**: Automated and native package manager installation across Debian/Ubuntu, Kali, Arch, Fedora/RHEL, openSUSE, Alpine, Void, and macOS.
* **[Configuring Local AI with Ollama](user/USER_MANUAL.md#the-command-palette-ctrlp--in-app-configuration)**: Connect CyGuide to local, privacy-preserving LLMs (e.g., Llama 3, Gemma, Mistral).
* **[Multi-Provider Cloud AI Setup](user/USER_MANUAL.md#the-command-palette-ctrlp--in-app-configuration)**: Configure OpenAI, Anthropic, Gemini, DeepSeek, or Groq with automatic failover.
* **[Exporting & Importing Investigations](user/USER_MANUAL.md#session-portability--reporting)**: Archive standalone `.db` graphs for CTF assignment submissions or peer reviews.
* **[Writing a Custom Security Tool Adapter](user/CONTRIBUTING.md#1-tool-structure)**: Create a new pluggable adapter using the Smart Adapter / Stupid Framework pattern.
* **[Developer Standards & Pre-Commit Setup](user/CONTRIBUTING.md#7-code-standards--developer-ergonomics)**: Ruff linting, pre-commit git hooks, and Conventional Commits workflow.

---

### 3. Reference (Information-Oriented)
Authoritative technical specifications and catalogues:

* **[Master Keyboard Shortcuts & Hotkeys](user/USER_MANUAL.md#master-keyboard-shortcuts--hotkeys-quick-reference)**: Comprehensive lookup table for all global, dashboard, learning mode, and operator hotkeys.
* **[CLI Commands & Diagnostics](user/USER_MANUAL.md#4-cli-subcommands--diagnostics)**: Complete reference for `cyg check`, `cyg export`, and `cyg import`.
* **[Standard Schema Registry](developer/SCHEMA_REGISTRY.md)**: Specifications for the 15 standardized finding schemas (hosts, services, endpoints, credentials, vulnerabilities) and Primary Identity Keys (PIKs).
* **[Database Architecture & Relational DDL](developer/DATABASE.md)**: Full SQLite schema, index specifications, ER diagrams, and portability mechanisms.
* **[Security Vulnerability Policy](../.github/SECURITY.md)**: Supported versions, private reporting channels, response SLAs, and threat model boundaries.



---

### 4. Explanation (Understanding-Oriented)
In-depth discussions of system architecture, design decisions, and threat models:

* **[System Architecture Blueprint](developer/ARCHITECTURE.md)**: Architectural Decision Records (ADRs), decoupled subsystem design, and dataflow pipelines.
* **[Autonomous Agent Harness Vision](developer/FUTURE_POWER_MODE.md)**: Architecture for autonomous ReAct agents, CIDR scope policies, and Human-in-the-Loop (HITL) safety gates.
* **[Developer Performance & Real-Time Streaming](developer/DEVELOPER_NOTES.md)**: Technical post-mortems on event loop starvation, micro-batching, and subprocess streaming.
* **[Master Project Roadmap](developer/ROADMAP.md)**: Chronological phase progression, completed milestones, and engineering task tracker.

---

## Reading Paths by Role

### For Students & CTF Competitors
1. Read the **[User Manual](user/USER_MANUAL.md)** to learn how to navigate the TUI.
2. Launch `cyg` and practice in **Learning Mode** to understand command flags and scan outputs.
3. Switch to **Power Mode** during live CTFs to track network discovery live in the entity graph without messy terminal tabs.
4. Export your session using `cyg export <session_id> session.db --report report.md` to submit your challenge writeup.

### For Instructors & Evaluators
1. Install CyGuide via Docker or package manager ([Installation Guide](README.md#installing-security-tools--dependencies)).
2. Have students submit standalone `.db` archives generated via `cyg export`.
3. Use `cyg import <archive.db>` to import student submissions into your local CyGuide instance.
4. Review the student's exact chronological execution timeline, discovered findings, and command history in the TUI.

### For Security Analysts & Penetration Testers
1. Deploy CyGuide via Docker (`docker run -it --rm --net=host -v ~/.cyguide:/root/.cyguide ghcr.io/h45sh/cyguide`).
2. Utilize **Power Mode** (`Enter`) for parallel scanning with universal variable substitution (`$TARGET`, `$PORT`).
3. Use `Ctrl+G` to merge findings across multiple subnets and targets into a unified workspace-wide attack graph.
4. Press `Ctrl+E` to generate instant technical and executive Markdown reports.

### For Tool Developers & Core Contributors
1. Read **[Contributing Guide](user/CONTRIBUTING.md)** and understand the Smart Adapter contract.
2. Inspect the **[Schema Registry](developer/SCHEMA_REGISTRY.md)** to select the right finding models for your tool.
3. Review **[System Architecture](developer/ARCHITECTURE.md)** and **[Database Specification](developer/DATABASE.md)**.
4. Verify changes locally by running `./scripts/verify.sh`.
