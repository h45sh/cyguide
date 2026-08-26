# CyGuide Project Roadmap & Progress Tracker

This document maintains a unified view of the project phases, current and planned features, and historical progress.

---

## 📅 Project Phases & High-Level Roadmap

### ✅ Phase 1: Core Foundation (Completed)
- **Engine Architecture**: Implemented Smart-Adapter model, Reactive Graph Store (PIK-Upsert), and Async Executor.
- **TUI Framework**: Built the Textual shell with Dashboard, Learning Mode, and the **Power Mode Advanced Operator Workspace Foundations**.
- **Schema Vocabulary**: Developed a 15-schema Pydantic library with auto-generated registry and linter.
- **Project Governance**: Established tiered protection policy, MIT License, and 86-test verification suite.
- **Production Hardening**: Implemented configurable storage (`data/` isolation), plugin diagnostics (UI-surfaced), absolute tool discovery (fixing `cyg` execution from any directory), and modernized packaging (`pyproject.toml`).

### 🚀 Phase 2: Intelligence & Expansion (Current)
*   **Priority 1: The "Intelligence" (Explainer Backends)**:
    *   [x] **Ollama Integration**: Implemented `OllamaBackend` and wired it to the CLI/TUI via `--ollama` (default: gemma).
    *   [x] **Cloud LLM Integration**: Implemented cloud-based explanations via `CloudAPIBackend` supporting OpenAI, Anthropic, OpenRouter, Grok, and others (Opt-in).
*   **Priority 2: The "Curriculum" (Tool Expansion)**:
    *   [x] **Web Discovery**: Implement `gobuster` adapter for directory brute-forcing.
    *   [x] **Vuln Scanning**: Implement `nikto` adapter for standard web vulnerability detection.
    *   [x] **DNS Analysis**: Implement `subfinder` adapter for attack surface mapping.
*   **Priority 3: Strategic Logic (Guided Mentorship)**:
    *   [x] **Recommendation Engine**: Implement declarative filters to suggest tools based on findings (e.g., if port 80/443 found -> suggest gobuster).

### 🛠️ Phase 3: Polish & Delivery (Completed)
*   **System Diagnostics**:
    *   [x] **Diagnostic CLI**: Added `cyg check` command to verify local environment dependencies, storage health, and AI backends.
*   **Session Portability**:
    *   [x] **Export/Import**: Mechanism to export and import sessions (`.db` + logs) for collaborative review or grading.
    *   [x] **Markdown Reporting**: Automatically generate professional summary of findings in Markdown format.
*   **Final Polish & Performance**:
    *   [x] **User Manual**: Comprehensive guide for adding new adapters, navigation, and using the TUI.
    *   [x] **UI Responsiveness & Streaming**: Hardened terminal resizing, non-blocking high-volume output streaming, rolling render buffers, and fine-grained LLM connection timeouts.

### 🧠Future => Advanced Intelligence, Autonomy & Ecosystem (Post-Release/Future)

*   **Automation, Code Quality & CI/CD**:
    *   [ ] **GitHub Actions CI**: Automated schema linting and multi-platform test execution on push/PR (Python 3.11, 3.12, 3.13).
    *   [ ] **Static Analysis & Formatting**: Pre-commit hooks with `ruff` and `black` to enforce codebase quality and prevent regression.
*   **Database & Execution Concurrency**:
    *   [ ] **SQLite WAL Mode**: Enable Write-Ahead Logging (`PRAGMA journal_mode = WAL;`) and connection pooling in `GraphStore` for high-throughput concurrent jobs.
*   **Tool Ecosystem Expansion**:
    *   [ ] **Nuclei Adapter**: Community YAML template vulnerability scanner yielding `vulnerability.generic` findings.
    *   [ ] **SQLMap Adapter**: Automated SQL injection exploitation and database enumeration adapter yielding `vulnerability.sqli` and `credential.dump` findings.
    *   [ ] **FFUF Adapter**: High-speed web fuzzing alternative to `gobuster`.
*   **Autonomous AI Agent Mode**:
    *   [ ] **Autonomous Investigation Loop**: Agent runtime built on `PowerWorkspaceFacade` and `ActionGateway` capable of reading entity graphs, querying recommendations, and submitting verified tool actions without human intervention.
*   **Multi-Session Recommendations & Workspace Scaling**:
    *   [ ] **Workspace-Scoped Suggestion Toggling**: Support querying and displaying proposed findings across all sessions in the active workspace when Global Graph view (`ctrl+g`) is active.
    *   [ ] **Cross-Session Approval Navigation**: Swapping TUI context to another session when approving a workspace-scoped suggestion to ensure variable resolution integrity.
*   **Distribution & Community Ecosystem**:
    *   [ ] **External Plugin Discovery**: Support loading custom user-defined adapters from `~/.config/cyguide/tools/` or `$CYGUIDE_PLUGIN_PATH`.
    *   [ ] **Containerized Distribution**: Official Kali Linux / Alpine Docker image with all security tools pre-installed for zero-setup execution.
    *   [ ] **PyPI Release**: Build and publish `cyguide` as an official package on PyPI (`pip install cyguide`).

---

## 🛠️ Power Mode Functional Progress Checklist

Power Mode has been successfully implemented as an advanced operator workspace:

*   [x] **Investigation-Scoped Sessions**: Persistent session identity in SQLite.
*   [x] **Typed Action System**: `ActionRequest` models with `triggered_by` field.
*   [x] **Structured Event Log**: Captures action payloads, result summaries, and raw shell commands.
*   [x] **Action Gateway (Option B)**:
    *   Full validation for registered tools.
    *   Raw shell command passthrough for `USER` source only.
    *   Rejection of unregistered tools for non-human sources.
*   [x] **Universal Variable Substitution**: `$TARGET`, `$PORT`, `$SERVICE` resolution in the Facade layer.
*   [x] **Entity Browser (Tree)**: Hierarchical view of findings (Hosts, Web, etc.).
*   [x] **Tabbed Job Workbench**: Parallel tool execution with independent log tabs.
*   [x] **Job Control**: Implementation of `ctrl+k` (Kill Job) to terminate background processes.
*   [x] **Tab Navigation**: `ctrl+pageup` and `ctrl+pagedown` to cycle between active job outputs.
*   [x] **Smart Command Palette**:
    *   Visual mode indicators: `[tool]` vs `[shell]`.
    *   Live context resolution line.
    *   Forced shell mode with `!` prefix and `ctrl+l` toggle.
*   [x] **Workbench Persistence**: Logic to restore tab logs from the event log upon re-entering a session.
*   [x] **Advanced Entity Grouping**: Tree logic handles complex parent-child relations using graph edges (e.g. Services strictly under specific Hosts).
*   [x] **Note Taking**: Implementation of the `ctrl+n` Scratchpad as a docked side pane that auto-saves to `data/.cyguide_scratchpad.md`.
*   [x] **Shell Adapter**: Fallback for arbitrary terminal command execution.
*   [x] **Global Entity Graph**: Toggled via `ctrl+g` to merge and deduplicate graph nodes across all sessions in a workspace into a unified tree.
*   [x] **Global Job Queue**: Groups jobs by session ID, displaying all background tasks active across the entire workspace in one unified view.
*   [x] **Cross-Session Navigation**: Clicking a job in the Job Queue from a different session automatically swaps the active environment to that session.
*   [x] **Inline Renaming**: `F2` universally bound on the Dashboard to instantly rename Workspaces and Sessions without leaving the flow.
*   [x] **Session Lifecycle Edge Cases**: Robust event handling in the Dashboard and Power Mode to safely process deleted or moved sessions and workspaces natively without crashing or displaying ghost entities.
*   [x] **Tab Lifecycle Management**: UI for closing finished tabs via `ctrl+w`.
*   [x] **Tab Closure Persistence**: Closed tabs are marked as closed in the SQLite database and do not reappear upon re-entering the session.
*   [x] **Active/Closed Job Counters**: Session details in the dashboard display live background job counts and persistent closed tab counts.
*   [x] **Unified Workspace/Session Mutations**: Route mutations through `PowerWorkspaceFacade` to validate name uniqueness (case-insensitively) and terminate active background tasks on deletion to prevent resource leaks.
*   [x] **High-Density Recent Activity Log**: Sidebar displays compact formatting (truncating session name and extracting target IPs/ports/domains/vulnerabilities) and hides closed tab events.
*   [x] **AI Suggestions Pane**: Integration of the `proposed` finding status into the UI.
*   [x] **Session Export & Import**: Handled via `export` / `import` CLI commands and TUI `Ctrl+E` shortcuts.

---

## 📜 Historical Walkthrough References
For detailed information on the design, coding decisions, and test outputs of completed features, refer to the archived logs:
*   [Session Export & Markdown Reporting (Aug 2026)](history/walkthrough_export_reporting.md)
*   [AI Suggestions & Recommendation Engine (Aug 2026)](history/walkthrough_suggestions_recommendations.md)
