# CyGuide – TUI-Based Guided Cybersecurity Learning Platform

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
- `nmap` (installed on your system)
- (Optional) `Ollama` for local LLM explanations.

### Installation

```bash
# Clone and install in editable mode
pip install -e .
```

### Launching

```bash
# Launch with default database (data/cyguide.db)
cyg

# Launch with a custom SQLite database
cyg --db my_project.db
```

## ✅ Testing & Verification

To ensure the codebase is stable and the documentation is in sync with the schemas, run the verification script:

```bash
./scripts/verify.sh
```

This script executes:
1. **Logic Tests**: A `pytest` suite (27 tests) covering the core executor, graph store, and finding schemas.
2. **Schema Linting**: Verifies that all 15 schemas are documented and have valid PIK declarations.
3. **Integration Verification**: Runs a real end-to-end execution loop using a mock adapter.

## 🛠️ Adding a Tool

CyGuide is built for extensibility. See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) to learn how to write a new adapter.

## 📚 Documentation

- **[Architecture](docs/ARCHITECTURE.md)**: Technical breakdown of the Smart-Adapter model and Graph Store.
- **[Schema Registry](docs/SCHEMA_REGISTRY.md)**: The current 15-schema vocabulary for security findings.
- **[Contributors](docs/CONTRIBUTORS.md)**: Project leadership and architectural ownership.

## 📂 Project Structure

- `cyguide/`: The core application package.
- `tools/`: The directory for tool plugins.
- `docs/`: Technical and architectural documentation.
- `data/`: Default directory for SQLite databases.

---

**Note:** This project has completed **Stage 1: Core Implementation** and is currently in **Stage 2: Advanced Feature Implementation**.
