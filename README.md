# CyGuide – TUI-Based Guided Cybersecurity Learning and Terminal Tool Orchestration Platform

CyGuide is a Terminal User Interface (TUI) platform for cybersecurity education, designed as a pluggable ecosystem for security tools.

## 🏗️ New Plugin Architecture

CyGuide has been restructured into a "Smart Adapter / Stupid Framework" model:

- **Core Engine (`cyguide/engine`)**: Manages a stateful entity graph and event log using SQLite.
- **Unified Schemas (`cyguide/schemas`)**: Defines a shared language for security findings (Hosts, Services, Endpoints, etc.).
- **Plugin System (`tools/`)**: Allows adding new tools (nmap, gobuster, etc.) without touching the core codebase.
- **Textual TUI (`cyguide/ui`)**: A modern, async terminal interface.

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- (Optional) `Ollama` for local LLM explanations.

To automatically install all required security tools (`nmap`, `gobuster`, `nikto`, `whois`, `subfinder`) and their system dependencies on Linux/macOS, run:

```bash
./scripts/install_deps.sh
```

### Installation

```bash
# Clone and install in editable mode
pip install -e .
```

### Launching

```bash
# Launch with unified default application database (~/.cyguide/cyguide.db)
cyg

# Launch with a custom data directory
cyg --data-dir ~/.my_cyguide

# Launch with a custom SQLite database
cyg --db my_project.db
```

### LLM Configuration

CyGuide supports both local and cloud-based LLMs for generating explanations:

#### Local (Ollama)
Launch with the `--ollama` flag and optionally specify a model (defaults to `gemma`):
```bash
cyg --ollama --ollama-model llama3
```

#### Cloud APIs (OpenAI, Anthropic, OpenRouter, Grok, etc.)
CyGuide uses environment variables to configure cloud LLM providers. You can set these in your shell or copy `.env.example` to `.env`.

```bash
# Required
export CYGUIDE_API_KEY="your_api_key_here"

# Optional overrides (defaults to OpenAI / gpt-4o)
export CYGUIDE_API_TYPE="openai"       # Options: openai, anthropic
export CYGUIDE_API_BASE="https://api.openai.com/v1" # E.g., https://openrouter.ai/api/v1
export CYGUIDE_API_MODEL="gpt-4o"      # E.g., claude-3-5-sonnet-20240620
```

### 🩺 Diagnostic Health Check
Verify your environment, database permissions, installed security tools, and AI backends:
```bash
cyg check
```
*(Use `cyg check --json` for scriptable JSON output in CI/CD pipelines).*

### 💾 Session Portability & Reporting
CyGuide provides built-in mechanisms to export, import, and generate reports from your investigations:

#### 1. Machine-Readable Database Exports (`exports/`)
Export a standalone, self-contained SQLite archive of a specific session containing its full entity graph, relationships, and raw command execution logs:
```bash
cyg export <session_id> exports/my_session.db
```
Import a previously exported session `.db` into your local workspace on any machine:
```bash
cyg import exports/my_session.db
```
* **Who are Exports for?**
  * **Instructors & Graders**: Students can export their lab/CTF session into an archive and submit it. Instructors can run `cyg import` to review findings, topology, and execution timelines in the TUI.
  * **Security Teams**: Analysts can share specific engagement graphs with team members for peer review or shift handoffs without exposing the entire global database.
  * **Archiving**: Lightweight, standalone backups of completed pentest engagements or CTF challenges.

#### 2. Human-Readable Markdown Reports (`reports/`)
Generate a formatted executive and technical Markdown report summarizing all discovered hosts, services, vulnerabilities, and executed commands:
```bash
cyg export <session_id> exports/my_session.db --report reports/my_session_report.md
```
*(You can also trigger automatic export and reporting directly inside Power Mode by pressing `Ctrl+E`).*

## 📜 Utility Scripts

CyGuide includes dedicated helper scripts under `scripts/`:

| Script | Purpose |
| :--- | :--- |
| [`./scripts/install_deps.sh`](scripts/install_deps.sh) | Automatically installs required system tools (`nmap`, `gobuster`, `nikto`, `whois`, `subfinder`) and Perl XML dependencies across Debian/Ubuntu, Arch, Fedora/RHEL, and macOS (Homebrew). |
| [`./scripts/verify.sh`](scripts/verify.sh) | Runs the comprehensive verification pipeline: executes the 166-test pytest suite, validates and regenerates the 15-schema documentation, and checks integration pipelines. |
| [`./scripts/generate_schema_registry.py`](scripts/generate_schema_registry.py) | Introspects the `cyguide.schemas` module and dynamically updates `docs/developer/SCHEMA_REGISTRY.md` with active finding schemas and Primary Identity Keys (PIKs). |

## ✅ Testing & Verification

To verify the codebase stability and ensure documentation is in sync with the schemas, run:

```bash
./scripts/verify.sh
```

## 🛠️ Adding a Tool

CyGuide is built for extensibility. See [docs/user/CONTRIBUTING.md](docs/user/CONTRIBUTING.md) to learn how to write a new adapter.

## 📚 Documentation

*   **[User Manual](docs/user/USER_MANUAL.md)**: Operating guide, keyboard shortcuts, UI panel descriptions, and export/import usage.
*   **[Architecture & Domain Context](docs/developer/ARCHITECTURE.md)**: System design details, database schemas, and facade layers.
*   **[Database Architecture & Specification](docs/developer/DATABASE.md)**: Exhaustive database models, PIK hashing, ER diagrams, and portability.
*   **[Schema Registry](docs/developer/SCHEMA_REGISTRY.md)**: Standard 15-schema vocabulary and Primary Identity Key (PIK) rules.
*   **[Roadmap & Progress Tracker](docs/developer/ROADMAP.md)**: Unified project phases, task checklists, and historical walkthroughs.
*   **[Autonomous Agent Harness Vision](docs/developer/FUTURE_POWER_MODE.md)**: Architecture for autonomous AI agents, HITL safety gates, and multi-agent roles.
*   **[Developer Performance Notes](docs/developer/DEVELOPER_NOTES.md)**: Real-time streaming, event loops, and CPU load roadblocks.
*   **[Changelog](CHANGELOG.md)**: Full release history and detailed changelog for v1.5.0.
*   **[Contributing](docs/user/CONTRIBUTING.md)**: Developer guide for creating tool plugins and contributing to CyGuide.

## 📂 Project Structure & Data Isolation

- `cyguide/`: The core application package (engine, schemas, modes, TUI).
- `tools/`: Tool plugin adapters and manifests (`nmap`, `gobuster`, `nikto`, `whois`, `subfinder`).
- `scripts/`: Development and system installation scripts.
- `docs/`: Technical and user documentation.
- `~/.cyguide/`: Default unified application data directory storing runtime database (`cyguide.db`), scratchpad notes (`scratchpad.md`), persistent settings (`settings.json`), exported archives (`exports/`), and generated investigation reports (`reports/`) across any launch directory.

---
