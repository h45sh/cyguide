# Changelog

All notable changes to the CyGuide project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.6.1] - 2026-11-08

### Operator Performance & Container Reliability
- **Instantaneous CLI Startup**: Optimized CLI runtime so `cyg --version` and command-line flags execute sub-100ms (~8.5x faster) by lazy-loading the interactive TUI only when entering visual mode.
- **Pre-Configured Nikto & Web Scanning in Docker**: Fully functional containerized web vulnerability scanning with Nikto, Perl SSL engines, and XML libraries pre-installed in the official container image.
- **Seamless PyPI Distribution**: Official package distribution on PyPI (`pip install cyguide`) with clean installation, environment isolation, and executable uninstallation.

---

## [1.6.0] - 2026-11-08

### Overview
CyGuide v1.6.0 delivers a major release focused on operator ergonomics, real-time workspace reactivity, streamlined engagement management, universal cross-platform deployment, and a polished terminal interface.

---

### Home Screen & Engagement Management
- **Redesigned Overview Cards**: Active and archived engagement overviews feature high-contrast target counts, metadata badges, and dedicated quick-action controls:
  - **› VIEW AUDIT LOG**: Instantly view the timeline log, executed commands, and historical findings.
  - **↺ REOPEN ENGAGEMENT**: Seamlessly reopen past sessions with full graph state and findings history preserved.
- **Polished Visual Alignment**: Repositioned quick-action controls and status indicators for intuitive navigation.

---

### Real-Time Reactive Command Palette (Ctrl+P)
- **Live Tool Health Diagnostics**: The command palette features a real-time tool health badge (`● Healthy (5/5)` or `▲ Issues Detected`) that dynamically monitors installed security tools (`nmap`, `whois`, `gobuster`, `nikto`, `subfinder`) and updates live as tools are installed or removed.
- **Organized Command Hierarchy**: Re-architected command palette menu with clear categorization: Animation Toggles, Tool Diagnostics, Configuration, Theme Picker, and Help.
- **Interactive Theme Switcher**: Dedicated theme selection palette with live preview and arrow key navigation.
- **F1 Hotkeys & Shortcuts Reference**: Fast-reference modal mapping keyboard shortcuts for terminal resizing, tab navigation, global graph view, and scratchpad toggles.

---

### Instant CLI Operations & Reporting
- **Direct System Diagnostics (`cyg check`)**: Inspect installed tools, database connectivity, and environment health directly from the terminal without launching the TUI, with JSON output (`cyg check --json`) for automated workflows.
- **Engagement Export & Markdown Reporting (`cyg export`)**: Export engagement databases and generate formatted Markdown assessment reports with atomic file security.
- **Instant Version Flag**: Added `--version` / `-V` for immediate version verification.

---

### Universal Security Tooling Setup
- **Universal Multi-Distribution Installer**: One-command dependency installation script (`./scripts/install_deps.sh`) supporting Debian/Ubuntu, Arch Linux, Fedora/RHEL, openSUSE, Alpine, Void Linux, and macOS (Homebrew).
- **Non-Root & Verification Modes**: Run `./scripts/install_deps.sh --check` to audit missing tools without modifying the system, or `--user` to configure without root privileges.

---

### Official Multi-Architecture Container (Docker / GHCR)
- **Ready-to-Run Security Container**: Official container images published to GitHub Container Registry (`ghcr.io/h45sh/cyguide`) for `linux/amd64` and `linux/arm64`, bundling all security tools and dependencies with zero host setup required.

---

### UI Polish & Visual Refinements
- **Thin Scrollbar Rendering**: Replaced bulky default terminal scrollbars with a custom thin scrollbar featuring full mouse-drag grab support.
- **Terminal Crash Safeguards**: Hardened terminal log rendering to prevent crashes from noisy tool output, escape sequences, or unexpected markup tags during intense scans.
- **Modern Text-First Aesthetic**: Streamlined typography, consistent card padding, and clean border styling across all screens.
- **Comprehensive Documentation**: Redesigned documentation portal following the Diátaxis framework, offering complete Tutorials, Operator How-To guides, interactive Schema Reference, and deep Architecture Explanations.

---

## [1.5.0] - 2026-11-06

### Overview
CyGuide v1.5.0 introduced the operator workbench, interactive split-pane resizing, multi-provider AI model integration, and defense-in-depth security controls.

---

### Operator Workbench (Power Mode)
- **Interactive Split-Pane Resizing**: Smooth mouse-drag and keyboard adjustment (`+`/`-`) between the live terminal output and the entity graph pane.
- **Integrated Engagement Scratchpad**: Built-in side drawer for operator notes, automatically saved and secured with private file permissions (`0600`).
- **Interactive Entity Graph**: Real-time visualization of discovered targets, ports, web endpoints, and detected vulnerabilities with filterable scopes (Session vs. Global Workspace).

---

### Multi-Provider AI Intelligence
- **Flexible LLM Integrations**: Support for both local Ollama models (for offline privacy) and cloud providers (OpenAI, Claude, Gemini, DeepSeek, Groq, OpenRouter).
- **Contextual Next-Step Recommendations**: Real-time AI explanations of tool outputs with suggested follow-up reconnaissance commands.

---

### Diagnostic Modals & Navigation
- **Tool Health Inspector**: Graphical dialog auditing missing binary dependencies with direct remediation guidance.
- **Tool Catalog & Recipes**: Interactive reference screen showing tool capabilities, supported targets, and parameter flags.
- **Guided Learning Mode**: Step-by-step penetration testing curriculum with flag breakdowns and AI coaching.
- **Performance Theme**: Zero-animation mode (`.no-animations`) for lightning-fast rendering over remote SSH connections.

---

### Operator Security Hardening
- **SSRF & Cloud Metadata Safeguards**: Built-in gateway blocking unintended access to link-local cloud metadata services (`169.254.169.254`, AWS IMDSv2 IPv6, etc.).
- **Subprocess Environment Sanitization**: Automatic redaction of sensitive API keys, tokens, and SSH credentials from spawned tool subprocesses.

---

## [1.0.0] - 2026-11-04

### Initial Release
- **Cybersecurity Reconnaissance TUI**: Interactive Terminal User Interface built with Textual and Rich for penetration testers and security analysts.
- **Core Security Tool Adapters**: Integrated workflows for `nmap` (network scanning), `whois` (domain/IP lookups), `gobuster` (directory brute-forcing), `nikto` (web misconfiguration scanning), and `subfinder` (subdomain enumeration).
- **SQLite Findings Graph**: Centralized relational store tracking domains, IPs, network services, web endpoints, and discovered vulnerabilities.
- **AI Recommendation Engine**: Automated analysis transforming raw security tool outputs into structured findings and logical next steps.
