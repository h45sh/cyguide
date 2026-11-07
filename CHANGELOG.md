# Changelog

All notable changes to the CyGuide project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.6.1] - 2026-11-08

### Operator Experience & Runtime
* **Instantaneous CLI Startup (`cyg --version`)**: Optimized startup runtime to sub-100ms (~8.5x faster) by lazy-loading interactive TUI components only when launching visual mode.
* **Pre-Configured Web Scanning in Docker**: Fixed containerized Nikto execution by embedding Perl SSL engines and XML libraries directly in the official multi-architecture container.
* **PyPI Distribution Integrity**: Streamlined distribution via PyPI (`pip install cyguide`) with isolated binary execution and clean uninstallation.

---

## [1.6.0] - 2026-11-08

### Engagement Management & Dashboard
* **Actionable Engagement Cards**: Active and archived engagement cards on the Home Screen feature clear target counts, metadata tags, and one-click actions:
  * `› VIEW AUDIT LOG`: Opens timeline logs, executed command histories, and discovered findings.
  * `↺ REOPEN ENGAGEMENT`: Re-activates past engagements while preserving all graph nodes and findings.
* **Streamlined Card Layout**: Repositioned quick-action shortcuts and status indicators for clean alignment and visual hierarchy.

### Reactive Command Palette (Ctrl+P)
* **Real-Time Tool Health Diagnostics**: Added a live tool health badge (`● Healthy (5/5)` / `▲ Issues Detected`) that dynamically probes installed security tools (`nmap`, `whois`, `gobuster`, `nikto`, `subfinder`) and reflects changes live.
* **Structured Command Categorization**: Grouped actions logically into View Toggles, Tool Diagnostics, Configuration, Themes, Hotkeys, and Session Management.
* **Live Theme Switcher**: Dedicated theme selection palette with instant preview and arrow key navigation.
* **F1 Hotkeys Reference**: Fast-reference shortcuts dialog detailing all workbench, navigation, and resizing keys.

### Command-Line Diagnostics & Reporting
* **Terminal System Diagnostics (`cyg check`)**: Inspect installed tools, database integrity, and environment health from the terminal, with optional JSON output (`cyg check --json`).
* **Session Export & Markdown Reports (`cyg export`)**: Export engagement databases and generate formatted Markdown assessment reports with atomic file security.
* **Direct Version Check (`cyg --version`)**: Added `--version` / `-V` flag for immediate version checks.

### Tooling Setup & Deployment
* **Universal One-Command Installer (`scripts/install_deps.sh`)**: Automated dependency installer supporting Debian/Ubuntu, Kali, Arch Linux, Fedora/RHEL, openSUSE, Alpine, Void Linux, and macOS (Homebrew).
* **Safe Audit & Non-Root Modes**: Added `--check` mode to preview missing tools without system changes, and `--user` mode for non-root environments.
* **Official Multi-Architecture Container (`ghcr.io/h45sh/cyguide`)**: Pre-built container images for `linux/amd64` and `linux/arm64` bundling all security tools with zero local host configuration.

### UI Polish & Terminal Ergonomics
* **Thin Scrollbar Rendering**: Replaced bulky scrollbars with a custom thin scrollbar with mouse grab support.
* **Terminal Crash Protection**: Escaped raw terminal markup and tool stderr to prevent crashes from noisy scans or ANSI escape sequences.
* **Modern Minimalist Aesthetics**: Polished typography, consistent card padding, and clean border styling across all screens.
* **Diátaxis Documentation Hub**: Reorganized documentation portal (`docs/README.md`) into practical Tutorials, How-To Guides, Reference specs, and Architecture Explanations.

---

## [1.5.0] - 2026-11-06

### Operator Workbench (Power Mode)
* **Interactive Split-Pane Resizing**: Smooth mouse-drag and keyboard resizing (`+`/`-`) between the live terminal stream and findings graph.
* **Integrated Engagement Scratchpad (`Ctrl+N`)**: Built-in side drawer for operator notes with atomic file security (`0600`).
* **Interactive Entity Browser**: Live graph hierarchy displaying targets, ports, web endpoints, and detected vulnerabilities with local vs. global scope toggle (`Ctrl+G`).

### Multi-Provider AI Intelligence
* **Pluggable LLM Backends**: Support for local Ollama models (offline privacy) and cloud providers (OpenAI, Claude, Gemini, DeepSeek, Groq, OpenRouter).
* **Contextual Suggestions**: Real-time AI explanations of tool outputs with recommended follow-up commands.

### Navigation & Diagnostics
* **Tool Health Inspector**: Graphical dialog auditing missing tool binaries with direct installation recommendations.
* **Tool Catalog Screen**: Visual catalog of tools, parameters, scan modes, and target scopes.
* **Guided Learning Mode**: Step-by-step penetration testing curriculum with flag breakdowns and AI coaching.
* **Low-Latency Theme**: Zero-animation mode (`.no-animations`) for fast rendering over remote SSH connections.

### Defense-in-Depth Safeguards
* **SSRF & Metadata Protection**: Gateway blocking unauthorized tool calls to cloud metadata endpoints (`169.254.169.254`, AWS IMDSv2 IPv6).
* **Environment Sanitization**: Automatic redaction of sensitive API keys, tokens, and SSH credentials from spawned tool subprocesses.

---

## [1.0.0] - 2026-11-04

### Initial Release
* **Terminal User Interface**: Interactive TUI built on Textual and Rich for penetration testing and reconnaissance.
* **Core Security Tool Adapters**: Integrated workflows for `nmap`, `whois`, `gobuster`, `nikto`, and `subfinder`.
* **Stateful SQLite Findings Graph**: Relational entity store tracking domains, IPs, network services, endpoints, and vulnerabilities.
* **Heuristic Recommendation Engine**: Automated analysis turning raw tool outputs into actionable next-step suggestions.
