# Changelog

All notable changes to the CyGuide project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.9.0](https://github.com/h45sh/cyguide/compare/v1.8.0...v1.9.0) (2026-11-12)


### Features

* **cli:** enhance argument parser with rich boxed styling and flexible option ordering ([76a55f6](https://github.com/h45sh/cyguide/commit/76a55f6cada0f0cb122b8db1b6d373248b6aa469))


### Documentation

* record v1.8.0 release and shift future roadmap milestones ([251d8bd](https://github.com/h45sh/cyguide/commit/251d8bda8b2d8f0f013bd4f731a5e405adefc4ca))

## [1.8.0](https://github.com/h45sh/cyguide/compare/v1.7.0...v1.8.0) (2026-11-11)


### Features

* add demo mode dummy IP support and enrich documentation showcase ([1d45844](https://github.com/h45sh/cyguide/commit/1d458442d796f051f872ff41930e75dfb2ac7ea8))
* **docs:** embed terminal demo video and revert recording dummy IP logic ([a61d0d3](https://github.com/h45sh/cyguide/commit/a61d0d3674f81dd10eef88977e20f5f80ecf3d00))


### Bug Fixes

* **ci:** upgrade setuptools to resolve runner vulnerability in pip audit ([b7fa94c](https://github.com/h45sh/cyguide/commit/b7fa94cb1db0e1a99e27cbbdd91c683c263082d2))
* **ui:** protect against Textual NoneType region crash and throttle Markdown updates ([2124980](https://github.com/h45sh/cyguide/commit/212498067e11f7d9de3f71426e39b98ac5643ee5))
* **ui:** stabilize Textual updates and automate releases ([3b002be](https://github.com/h45sh/cyguide/commit/3b002becdf0539356b6dec17e54b04a305f4e4ab))


### Documentation

* add official project webpage to README ([c964f65](https://github.com/h45sh/cyguide/commit/c964f651dd120eab8d58beb5e6c5ab7c3637af20))
* add official project webpage to README ([aea0f49](https://github.com/h45sh/cyguide/commit/aea0f491fe34985e2394dc4c512c6257521e9484))
* add recommendation cleanup to roadmap ([4ce4840](https://github.com/h45sh/cyguide/commit/4ce4840ce4934efd1525e824155a09515a06c035))
* formalize v1.8.0 through v2.0.0 progression ([701a97e](https://github.com/h45sh/cyguide/commit/701a97ea996b79bc2ea6b9f281d7f010df6c4eb9))
* formalize v1.8.0 through v2.0.0 progression and platform specification ([5418587](https://github.com/h45sh/cyguide/commit/5418587a28237c85212a27e05810ccb40272f7ee))
* integrate authentic UI screenshots and set Power Mode as hero preview ([e0b0cad](https://github.com/h45sh/cyguide/commit/e0b0cad2716bc0f7d1a6bc11ff3fac3d234e78e8))
* **security:** update contact email and supported versions ([5129090](https://github.com/h45sh/cyguide/commit/5129090b2378787da701bbc1005dc530dff4b7d5))
* showcase visual workstation interface, embed demo video, and enrich user manual ([68f8fd2](https://github.com/h45sh/cyguide/commit/68f8fd2750d8eab3f66bef401c6e4d8f987ded85))
* **ui:** document technical debt and upstream decommissioning criteria for Textual compat ([b9a5eb4](https://github.com/h45sh/cyguide/commit/b9a5eb42010ba01d0a0e9724b9bc7542913f28a3))

## [1.7.0] - 2026-11-08

### Power Mode & Concurrency
* **Persistent Background Task Execution**: Background investigation jobs (e.g. `nmap`, `subfinder`, `whois`) now maintain continuous execution and ring-buffer history across tab changes, session switches, and dashboard navigation.
* **Pub/Sub Observability Engine**: Real-time event subscription model decouples UI presentation from active execution tasks, enabling responsive live stream rendering without UI freezes.
* **Graceful Teardown & Task Draining**: Coordinated async shutdown sequence prevents connection race conditions (`Cannot operate on a closed database`) when exiting the application during active runs.

### Operator Networking & Usability
* **Automated LHOST & Network Interface Detection**: Intelligent discovery of active local IP addresses, automatically prioritizing VPN interfaces (`tun0`, `tap0`) followed by local adapters and binding `$LHOST` directly into the execution prompt.
* **Real-Time CTF Flag Detection**: Automated stream detection for security flag formats (`flag{...}`, `HTB{...}`, `THM{...}`) with native desktop notifications (`notify-send`) and one-key clipboard yank (`Ctrl+Y`).
* **Modern TUI Visual Standards**: Enforced 34-column sidebar standards, anti-flicker surgical DOM updates, and standardized operational status glyphs (`●`, `◌`, `▪`, `×`, `⊘`).

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
* **Multi-Tab Terminal Execution**: Asynchronous job runner supporting concurrent tool execution and live output streaming.
