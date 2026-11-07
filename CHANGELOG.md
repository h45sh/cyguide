# Changelog

All notable changes to the CyGuide project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.6.0] - 2026-11-08

### Added
- **Multi-Arch OCI Container Publishing**: Added `Dockerfile` and GitHub Actions workflow (`.github/workflows/docker.yml`) for multi-architecture (`linux/amd64`, `linux/arm64`) publishing to GitHub Container Registry (GHCR).
- **Universal Multi-Distribution Dependency Installer**: Enriched [`scripts/install_deps.sh`](scripts/install_deps.sh) supporting apt, pacman, dnf, zypper, apk, xbps, and homebrew with `--check` and `--user` non-root flags.
- **Codebase Quality & CI/CD Gates**:
  - Added [Ruff](https://github.com/astral-sh/ruff) linting configuration in `pyproject.toml` and `.github/workflows/ci.yml`.
  - Added schema documentation drift verification via `python3 scripts/generate_schema_registry.py --check`.
  - Added `macos-latest` cross-platform runner to the CI test matrix.
  - Added GitHub CodeQL Static Application Security Testing (`.github/workflows/codeql.yml`).
  - Added automated weekly dependency management via [`.github/dependabot.yml`](.github/dependabot.yml).
  - Added automated categorized release notes configuration via [`.github/release.yml`](.github/release.yml).
- **Repository Governance & Community Standards**:
  - Established responsible vulnerability disclosure policy in [`.github/SECURITY.md`](.github/SECURITY.md).
  - Added standardized Pull Request template with architectural tier checklists ([`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md)).
  - Added structured YAML issue forms for bugs, tool adapter requests, and feature proposals in `.github/ISSUE_TEMPLATE/`.
  - Updated [`.github/CODEOWNERS`](.github/CODEOWNERS) covering Tier 1 core architecture, security gateways, and CI/CD workflows.
- **Developer Ergonomics & UI Improvements**:
  - Added [`.pre-commit-config.yaml`](.pre-commit-config.yaml) for Ruff linting and schema registry drift checks.
  - Added `--version` / `-V` CLI flag to `cyg` entrypoint.
  - Fixed active and archived session overview alignment on the Home screen.
  - Real-time Command Palette tool health update reactivity upon custom tool filesystem changes.

### Changed
- **Documentation Overhaul (Diátaxis Framework)**: Restructured complete documentation portal (`docs/README.md`) into Tutorials, How-To Guides, Reference, and Explanation quadrants.
- **Decorative Emoji Purge**: Removed decorative emojis across all documentation, templates, and scripts in favor of clean text and standard labels.
- **Repository Hygiene & Directory Restructuring**:
  - Removed orphaned and redundant files: `VERSION`, `cyguide/modes/power.py`, and sample outputs.
  - Hardened and categorized [`.gitignore`](.gitignore) and [`.dockerignore`](.dockerignore).
  - Expanded test suite to **179 passing tests**.

---

## [1.5.0] - 2026-11-06


### Overview
CyGuide v1.5.0 is a **major milestone release** introducing an overhauled operator user interface, interactive workspace resizing, centralized cross-platform XDG path management, defense-in-depth security hardening, multi-provider AI integration, and an expanded test suite of 166 passing unit and integration tests.

---

### Major UI/UX Overhaul
- **Interactive Split-Pane Resizer (`cyguide.ui.widgets.resizer`)**:
  - Implemented `VerticalResizer` and `ResizeHandle` providing real-time mouse drag resizing between the command execution terminal and the findings graph pane.
  - Added keyboard accessibility for resizing (`+` / `-` adjustments), snap points, and panel collapse toggles.
- **Dynamic Configuration & Provider Key Modal (`cyguide.ui.screens.config_modal`)**:
  - Dedicated configuration screen supporting multi-provider LLM API keys: Ollama, DeepSeek, OpenAI, Anthropic, Gemini, Groq, and OpenRouter.
  - Live toggles for animation/transition speed, execution timeout limits, and maximum AI recommendations.
- **Environment & Tool Health Inspector (`cyguide.ui.screens.tool_health_modal`)**:
  - Diagnostic modal inspecting external binary installations (`nmap`, `whois`, `gobuster`, `nikto`, `subfinder`).
  - Real-time path resolution, binary validation badges, and direct install recommendations (`./scripts/install_deps.sh`).
- **Interactive Tool Catalog Screen (`cyguide.ui.screens.tool_browser`)**:
  - Dedicated tool browsing interface displaying adapter capabilities, supported targets, recipes, and customizable parameter flags.
- **Operator Workbench Power Mode (`cyguide.ui.screens.power`)**:
  - Dual split-view featuring interactive graph entity navigation and streaming command terminal.
  - Integrated Scratchpad drawer with auto-save and atomic 0600 file permissions.
  - Live session switching with persistent graph state and action history.
- **Guided Learning Mode (`cyguide.ui.screens.learning`)**:
  - Step-by-step curriculum with guided flag explanations, raw execution stream, and AI explanation drawer.
- **Performance Theme & Animations Toggle (`cyguide/ui/style.css`, `cyguide/app.py`)**:
  - Added `.no-animations` style rules for instant, zero-latency rendering on constrained or remote SSH terminal sessions.

---

### Defense-in-Depth Security Hardening
- **[CYG-SEC-01] Atomic File Creation**:
  - Replaced standard file `open()` with `os.open(..., os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)` across `app.py` and `power.py` to eliminate TOCTOU permission race conditions on `settings.json` and `scratchpad.md`.
- **[CYG-SEC-02] Link-Local & Cloud Metadata SSRF Protection**:
  - Enhanced `ActionGateway` in `cyguide/engine/gateway.py` to block entire IPv4 Link-Local subnet (`169.254.0.0/16`), AWS IMDSv2 IPv6 (`fd00:ec2::254`), Alibaba Cloud metadata (`100.100.100.200`), and hex/decimal IP variants (`2852039166`, `0xa9fea9fe`).
- **[CYG-SEC-03] AI Delimiter Neutralization**:
  - Sanitized untrusted scan logs to strip closing `</untrusted_scan_output>` tags, mitigating prompt injection breakouts in AI analysis.
- **[CYG-SEC-04] Subprocess Secret Scrubbing**:
  - Expanded `sanitize_subprocess_env()` in `cyguide/engine/executor.py` to scrub sensitive API keys (`DEEPSEEK_`, `PERPLEXITY_`, `PPLX_`, `HUGGINGFACE_`, `HF_`), `VAULT_TOKEN`, and `SSH_PRIVATE_KEY` from child execution processes.
- **[CYG-SEC-05] Markdown Command Escaping**:
  - Escaped backticks in executed commands within `cyguide/engine/reporter.py` to prevent markdown injection in generated security reports.

---

### Core Engine & Architecture Refinements
- **Centralized Path Resolution (`cyguide/paths.py`)**:
  - Introduced unified XDG-compliant path resolver for application data, configuration, cache, and scratchpad files.
- **Stateful SQLite Graph Store (`cyguide/engine/store.py`)**:
  - Enhanced session lifecycle: creation, active session tracking, deletion cascades, and database migration.
  - Deterministic Primary Identity Keys (PIKs) using SHA-256 for finding deduplication.
- **Multi-Provider AI Explainer (`cyguide/engine/explainer.py`)**:
  - Unified explainer layer supporting Ollama, DeepSeek, OpenAI, Claude, Gemini, Groq, and offline heuristic rules.
- **Smart-Adapter Subsystem (`cyguide/engine/adapter.py`, `tools/`)**:
  - Complete decoupling between engine orchestration and tool adapters (`nmap`, `whois`, `gobuster`, `nikto`, `subfinder`).
- **Schema Pruning & Verification (`scripts/generate_schema_registry.py`)**:
  - Validated 15 core schemas across entity, network, DNS, TLS, vulnerability, and power domain.
  - Removed orphaned and unreferenced schema prototypes.

---

### Test Suite & Continuous Integration
- **Expanded Test Coverage**:
  - Test suite grew to **166 passing unit and integration tests** (100% pass rate in 81s).
  - Added dedicated test modules:
    - `tests/unit/test_config.py`: Settings serialization, default values, and validation.
    - `tests/unit/test_multi_api_keys.py`: API key encryption and persistence.
    - `tests/unit/test_paths.py`: XDG directory resolution and fallback handling.
    - `tests/unit/test_session_lifecycle.py`: Multi-session switching and cascading cleanup.
    - `tests/unit/test_ui_resizer_and_power.py`: Resizer drag events, snap boundaries, and split pane behavior.
    - `tests/unit/test_security_fixes.py`: Comprehensive test coverage for all 5 security fixes.
- **Automated Verification Pipeline**:
  - `./scripts/verify.sh` executes all 166 pytest cases, validates the schema registry, and confirms documentation synchronization.

---

### Codebase Cleanup & Modernization
- **Orphaned Code Removal**:
  - Deleted legacy unreferenced files: `cyguide/ui/widgets/home.py`, `scripts/test_enrichment.py`, and `scripts/test_runner.py`.
- **Packaging Standardization**:
  - Updated `pyproject.toml` to modern SPDX string `license = "MIT"`.
  - Rebuilt sdist and wheel packages with 0 warnings.
- **Documentation Re-alignment**:
  - Updated `ARCHITECTURE.md`, `ROADMAP.md`, `DATABASE.md`, `USER_MANUAL.md`, and `CONTRIBUTING.md`.
  - 0 broken markdown links across the documentation suite.
