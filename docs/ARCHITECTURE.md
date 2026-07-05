# CyGuide Architecture: The Smart-Adapter Platform

## 1. Introduction
CyGuide is a modular cybersecurity investigation platform designed for both learning and rapid power-use. The fundamental problem it solves is **tool fragmentation**: security tools produce wildly different outputs (XML, JSON, raw text) that are difficult to correlate into a single "source of truth."

CyGuide solves this through a **"Smart Adapter / Stupid Framework"** architecture.

## 2. Core Architectural Principles

### 2.1 Smart Adapters, Stupid Framework
Most security frameworks try to understand the tools they wrap. This creates a maintenance bottleneck. CyGuide moves the intelligence into the **Adapters**:
- The **Framework** knows nothing about `nmap` or `whois`. It only understands **Schemas** (e.g., `network.host`).
- The **Adapter** is responsible for taking tool-specific raw output and transforming it into standardized findings.
- This enables **purely additive contributions**: adding a new tool requires zero changes to the core engine.

### 2.2 The Entity Graph & PIK Upsert
Instead of a flat log of findings, CyGuide maintains a **Stateful Entity Graph**.
- **PIK (Primary Identity Key)**: Every schema defines a PIK (e.g., `host_ip` for a host).
- **De-duplication**: When a tool reports a finding, the `GraphStore` uses the PIK to perform an `upsert`. If the entity already exists, it is updated; if not, it is created.
- **Wiring**: Findings define a `parent` relation. The engine automatically wires these in the database (e.g., a `network.service` finding automatically links to its parent `network.host`).

### 2.3 Store-Watching Reactivity
To maintain a high-performance UI without tight coupling, CyGuide uses a **Reactivity Model**:
1. The `Executor` runs a tool and writes findings to the `GraphStore`.
2. The `GraphStore` triggers an `on_upsert` callback.
3. The **UI** (Textual) listens to these callbacks and surgically updates labels or graphs.
This ensures the Engine never imports from the UI, preserving a strict architectural boundary.

## 3. Data Persistence: Why SQLite?
CyGuide uses SQLite with adjacency tables rather than a dedicated Graph Database (like Neo4j) for three reasons:
1. **Portability**: A session is a single `.db` file that can be shared or audited.
2. **Performance**: At the scale of a single investigation (thousands of entities), SQLite is faster and has zero memory overhead.
3. **Zero Dependency**: Simplifies deployment for students and professional penetration testers alike.

## 4. Learning Mode: Milestone-to-Prompt
The Learning Mode isn't just a wrapper; it's a curriculum engine.
- Tools define **Milestones** in their `manifest.toml` (e.g., `first_service`).
- When the `Executor` detects a milestone, it triggers the `LearningExplainer`.
- The Explainer resolves a templated prompt and streams it through an **ExplainerBackend**.
- **Current State**: Implements a zero-dependency `TemplateBackend` for offline use and an `OllamaBackend` for local LLM integration (Stage 2, defaults to `gemma`).
- This creates a real-time "mentor" experience that reacts to actual scan results.

## 5. Plugin Loading & Diagnostics
To ensure system reliability, the `ToolRegistry` performs validation during the loading phase:
- **Error Capture**: Exceptions during manifest parsing or adapter instantiation are captured and stored in `load_errors`.
- **TUI Visibility**: These diagnostics are surfaced in the Dashboard under **TOOL HEALTH**, providing immediate feedback on the status of the tool ecosystem.

## 6. CLI & Storage Flexibility
CyGuide is designed for professional use-cases:
- **`cyg` Command**: Exposed via the `cyg` command (renamed from `cyguide` to avoid shell directory collisions).
- **Configurable Persistence**: Users can specify custom SQLite database paths via the `--db` flag, enabling per-project workspace isolation.

### 7. Security & Governance: The Tiered Policy
To ensure long-term stability, the codebase implements a three-tier protection policy:
- **Tier 1 (Frozen)**: Core engine logic (`store.py`, `executor.py`). Changes require deep architectural review.
- **Tier 2 (Review Required)**: Schema definitions and TUI screens.
- **Tier 3 (Free)**: Tool adapters and documentation.

## 8. Future Direction: Power Mode & Agent Harness
Power Mode is designed to evolve CyGuide from a deterministic platform into a controlled cybersecurity agent harness. By utilizing a strict **Facade/Gateway/Executor** layering, the system allows for future AI integration while maintaining a "Deterministic Core."

Detailed documentation for this mode can be found in [docs/POWER_MODE.md](POWER_MODE.md).

## 9. Conclusion
CyGuide's architecture prioritizes **extensibility** through standardization. By enforcing a strict schema vocabulary and a declarative tool contract, it transforms a collection of disparate scripts into a unified, reactive investigation platform. This architectural foundation, completed in **Stage 1: Core Implementation**, provides the necessary stability for the upcoming **Stage 2: Advanced Feature Implementation**.

