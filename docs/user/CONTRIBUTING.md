# Contributing to CyGuide: The Tool Plugin Contract

CyGuide follows a **"Smart Adapter / Stupid Framework"** model. The framework handles the UI, database, and concurrency; the **Tool Adapters** handle all security domain logic.

---

## 1. Tool Structure
Every plugin lives in `tools/<name>/` and requires two files:
- `manifest.toml`: Declarative metadata and UI constraints.
- `adapter.py`: Python logic to build commands and parse output.

---

## 2. Implementation Patterns

### A. The Scanner Pattern (e.g., Nmap)
Used for discovering child entities (like services) from a parent (like a host).
- **Input**: `network.host`
- **Output**: `network.service` (engine automatically wires the parent-child relationship).

### B. The Enrichment Pattern (e.g., Whois)
Used for adding new properties to an existing entity.
- **Input**: `network.host`
- **Output**: `network.host` (engine performs a semantic merge based on the IP address PIK).

---

## 3. Standard Schemas
Always use schemas from `cyguide/schemas/` to ensure tool chaining works. Every finding must have a **Primary Identity Key (PIK)** that uniquely identifies it.

- `network.host`: PIK is `{"ip": "..."}`.
- `network.service`: PIK is `{"host_ip": "...", "port": ..., "protocol": "..."}`.
- `dns.record`: PIK is `{"domain": "...", "type": "...", "value": "..."}`.

---

## 4. Headless-First Development (Mandatory)
Before touching the TUI, verify your adapter using a standalone script to ensure the **Executor → Adapter → Store** pipeline works in isolation.

Example `scripts/test_mytool.py`:
```python
import asyncio
from cyguide.engine.store import GraphStore
from cyguide.engine.executor import Executor
from tools.mytool.adapter import MyToolAdapter

async def main():
    store = GraphStore(":memory:")
    await store.initialize()
    executor = Executor(store)
    
    # ... run tool and assert graph state ...
    
    await store.close()
```

---

## 5. UI Boundaries
Adapters **must never** import from `cyguide.ui`. They should only depend on `cyguide.engine` and `cyguide.schemas`.

---

## 6. Protected Files
To ensure project stability during Phase 3/4 and university submission, we follow a tiered protection policy.

### Tier 1 — Frozen (Team Agreement Required)
These files are critical infrastructure. A wrong change can silently break the entire graph or adapter ecosystem. Do not modify without a team meeting and written agreement.
- `cyguide/schemas/base.py`: The `BaseFinding` and `Relation` models.
- `cyguide/engine/store.py`: Upsert logic and PIK resolution.
- `cyguide/engine/canonicalize.py`: Normalization rules.
- `cyguide/engine/registry.py`: Discovery and loading logic.
- **Existing `manifest.toml` sections**: `[meta]`, `[input]`, and `[output]` of already committed tools.

### Tier 2 — Review Required
Changes are expected but require at least one other team member to review the diff before merging.
- Any `adapter.py`: Vulnerability and async contract check.
- `cyguide/engine/executor.py`: Async timeout and process logic.
- SQLite schema in `store.py`: Database migrations.
- New schema files in `cyguide/schemas/`: Vocabulary check.

### Tier 3 — Free to Change
No formal review needed, though common sense applies.
- Anything in `cyguide/ui/`: CSS, layout, widgets.
- `cyguide/modes/`: Orchestration logic.
- `tools/*/manifest.toml` learning section: Content and descriptions.
- `docs/` and `efd/`: Documentation and examples.
- `scripts/`: Utility scripts.

