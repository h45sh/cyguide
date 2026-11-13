# Contributing to CyGuide: Developer & Plugin Guide

Thank you for your interest in contributing to CyGuide! This guide covers our architectural model, the plugin specification for adding new security tools, our headless-first testing workflow, and code governance policies.

---

## 1. Architectural Philosophy: Smart Adapter / Stupid Framework

CyGuide decouples terminal orchestration from cybersecurity tooling:

* **The Core Framework (`cyguide/engine`)**: Manages the asynchronous subprocess lifecycle, deterministic SQLite entity graph, event logs, and the Textual user interface. It has zero tool-specific logic.
* **The Tool Adapters (`tools/<tool_name>/`)**: Self-contained plugins that translate between external CLI commands (`nmap`, `gobuster`, etc.) and CyGuide's unified finding schemas.

> [!NOTE]
> Adapters must never import from `cyguide.ui`. They should only interact with `cyguide.engine` abstractions and `cyguide.schemas` finding models.

---

## 2. Anatomy of a Tool Plugin

Every security tool plugin lives in its own subdirectory under `tools/<tool_name>/` and requires two files:

```text
tools/<tool_name>/
├── __init__.py
├── manifest.toml    # Metadata, execution constraints, and learning recipes
└── adapter.py       # Command generation and stdout parsing logic
```

### A. The Declarative Manifest (`manifest.toml`)

The manifest informs CyGuide's registry about tool capabilities, inputs, and outputs:

```toml
[meta]
name = "mytool"
description = "Fast web directory and virtual host scanner"
one_line_summary = "Enumerate endpoints and paths on web targets"
category = "Web Reconnaissance"
categories = ["web", "enumeration"]
binary = "mytool"

[modes]
learning = true
power = true

[input]
accepts = ["network.service", "web.endpoint"]

[output]
produces = ["web.endpoint", "web.vulnerability"]

[learning]
enabled = true

[[learning.recipes]]
name = "Quick Path Discovery"
description = "Scan standard paths on target web server"
flags = ["-u", "$TARGET", "-w", "/usr/share/wordlists/dirb/common.txt"]
```

### B. The Tool Adapter (`adapter.py`)

Adapters inherit from `ToolAdapter` in `cyguide.engine.adapter` and implement three core methods:

```python
from typing import List, AsyncGenerator
from cyguide.engine.adapter import ToolAdapter
from cyguide.schemas.base import BaseFinding
from cyguide.schemas.web import WebEndpointFinding

class MyToolAdapter(ToolAdapter):
    @property
    def name(self) -> str:
        return "mytool"

    def validate_install(self) -> bool:
        """Check if the external CLI binary is available on PATH."""
        return self._binary_exists("mytool")

    def build_command(self, target: str, flags: List[str]) -> List[str]:
        """Construct the CLI arguments safely as an argument list (preventing shell injection)."""
        return ["mytool", "-u", target] + flags

    async def parse_output(self, stream: AsyncGenerator[str, None]) -> AsyncGenerator[BaseFinding, None]:
        """Parse streaming line-by-line stdout into validated BaseFinding schemas."""
        async for line in stream:
            cleaned = line.strip()
            if "200 OK" in cleaned:
                path = cleaned.split()[0]
                yield WebEndpointFinding(
                    url=path,
                    status_code=200,
                    source_tool="mytool"
                )
```

---

## 3. Standard Finding Schemas & Primary Identity Keys (PIKs)

To enable tool chaining (e.g. `nmap` discovering a port, triggering `gobuster` on that port), all findings inherit from `BaseFinding` and declare a deterministic **Primary Identity Key (PIK)**.

| Schema Type | Finding Class | PIK Identifying Fields |
| :--- | :--- | :--- |
| `network.host` | `HostFinding` | `{"ip": "<ip_address>"}` |
| `network.service` | `ServiceFinding` | `{"host_ip": "<ip>", "port": <port>, "protocol": "<proto>"}` |
| `web.endpoint` | `WebEndpointFinding` | `{"url": "<url>", "method": "<method>"}` |
| `dns.record` | `DNSRecordFinding` | `{"domain": "<domain>", "record_type": "<type>", "value": "<val>"}` |
| `vulnerability.found` | `VulnerabilityFinding` | `{"target": "<target>", "vuln_id": "<cve_or_id>"}` |

> [!TIP]
> Consult [`docs/developer/SCHEMA_REGISTRY.md`](../developer/SCHEMA_REGISTRY.md) for the complete reference of all 15 active schemas.

---

## 4. Headless-First Development Workflow

Before testing your adapter inside the Textual TUI, verify the **Executor → Adapter → GraphStore** pipeline in headless isolation using an in-memory SQLite database:

```python
# scripts/test_mytool_headless.py
import asyncio
from cyguide.engine.store import GraphStore
from cyguide.engine.executor import SubprocessExecutor
from tools.mytool.adapter import MyToolAdapter

async def test_run():
    store = GraphStore(":memory:")
    await store.initialize()
    
    adapter = MyToolAdapter()
    executor = SubprocessExecutor(store)
    
    # Run against a mock target or local test server
    cmd = adapter.build_command("http://127.0.0.1:8000", [])
    print(f"Executing: {' '.join(cmd)}")
    
    await store.close()

if __name__ == "__main__":
    asyncio.run(test_run())
```

---

## 5. Code Governance & Tiered Protection Policy

To protect system determinism and database stability, CyGuide follows a three-tiered change governance model:

### Tier 1: Core Foundation (Strict Review Required)
> [!IMPORTANT]
> These files define core engine contracts. Breaking changes here can silently corrupt the entity graph or break all registered adapters. Modifications require full test validation and consensus.
* `cyguide/schemas/base.py`: The `BaseFinding` and `Relation` models.
* `cyguide/engine/store.py`: Upsert logic, PIK SHA-256 calculation, and database schemas.
* `cyguide/common/canonicalize.py`: Value and schema normalization rules.
* `cyguide/engine/registry.py`: Dynamic tool discovery and manifest loader.
* `cyguide/paths.py`: Centralized application data path resolution.

### Tier 2: Adapter & Executor Pipeline (Review Recommended)
* `cyguide/engine/executor.py`: Subprocess streams, timeouts, and process group management.
* `cyguide/engine/gateway.py`: Action validation and CIDR scope policies.
* Individual tool adapters under `tools/*/adapter.py`.
* Database migration routines in `store.py`.

### Tier 3: Presentation, Content & Documentation (Fast Track)
* `cyguide/ui/`: Textual CSS styling (`style.css`), layouts, screens, and widgets.
* `docs/`: User and developer documentation.
* `scripts/`: Development and maintenance helper scripts.
* Learning mode recipes in `tools/*/manifest.toml`.

---

## 6. Running Verification & Continuous Integration

Before submitting a Pull Request, run the automated verification pipeline:

```bash
# Execute the full verification suite (170+ tests, schema doc sync, and code style)
./scripts/verify.sh

# Run fast unit tests directly with pytest
pytest tests/unit/ -v

# Run integration flow tests
pytest tests/integration/ -v

# Verify finding schema documentation is in sync without modifying files
python3 scripts/generate_schema_registry.py --check
```

> [!NOTE]
> If you create or modify finding schemas in `cyguide/schemas/`, `./scripts/verify.sh` automatically updates and validates [`docs/developer/SCHEMA_REGISTRY.md`](../developer/SCHEMA_REGISTRY.md). Ensure any generated documentation diffs are committed with your PR.

---

## 7. Code Standards & Developer Ergonomics

### A. Linting and Formatting (Ruff)

CyGuide uses [Ruff](https://github.com/astral-sh/ruff) as its single authoritative linter and code formatter. All pull requests must pass automated lint and format checks in CI:

```bash
# Check code for lint issues and import order
ruff check .

# Automatically apply safe lint fixes
ruff check . --fix

# Verify code formatting (100 character line length)
ruff format --check .

# Automatically reformat all code
ruff format .
```

### B. Pre-Commit Git Hooks

To catch style and schema discrepancies locally before committing, install our pre-commit hooks:

```bash
# Install pre-commit into your development virtualenv
pip install -r requirements-dev.txt

# Install the git hook scripts
pre-commit install

# Manually trigger all hooks against all files
pre-commit run --all-files
```

Pre-commit runs Ruff linting, Ruff formatting, YAML/TOML syntax checks, and verifies that `docs/developer/SCHEMA_REGISTRY.md` matches your schema models.

### C. Type Annotations & Static Safety

* **Engine & Schemas (`cyguide/engine/`, `cyguide/schemas/`)**: Strict type annotations are expected for all function signatures and data models.
* **Subprocess Arguments**: Never invoke subshells (`shell=True`). Always construct commands as structured argument lists (`List[str]`).

---

## 8. Pull Request & Commit Standards

### A. Conventional Commits

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification for commit messages and PR titles. This enables automated release notes generation:

| Prefix | Description | Example |
| :--- | :--- | :--- |
| `feat:` | A new user-facing capability or command | `feat: add workspace export encryption` |
| `tool:` | A new or updated security tool adapter | `tool: add ffuf web fuzzer adapter` |
| `fix:` | A bug fix | `fix: resolve aiosqlite race in event bus` |
| `docs:` | Documentation changes only | `docs: add Diataxis how-to guide for AI setup` |
| `refactor:` | Code restructuring without behavior changes | `refactor: extract subnet parsing into utils` |
| `test:` | Adding or improving tests | `test: add unit tests for nmap parser` |
| `ci:` | Changes to CI workflows or build scripts | `ci: add CodeQL security analysis workflow` |

### B. Pull Request Guidelines

1. **Use the PR Template**: Fill out all sections of [`.github/PULL_REQUEST_TEMPLATE.md`](../../.github/PULL_REQUEST_TEMPLATE.md), noting the architectural tier of your changes.
2. **One Feature per PR**: Keep changes focused and atomic to simplify review and rollbacks.
3. **No Decorative Emojis**: Documentation and code comments must remain clean and readable in standard terminal displays without decorative emojis.
4. **Code Ownership Approval**: Any modifications touching Tier 1 files (`cyguide/engine/store.py`, `cyguide/schemas/base.py`) automatically assign `@h45sh` as a required reviewer via [`.github/CODEOWNERS`](../../.github/CODEOWNERS).

