# CyGuide Architecture & Design Context

Welcome to the internal developer guide for CyGuide. This document consolidates our core design philosophies, domain vocabularies, database models, layered execution pipelines, and governance rules into a single authoritative reference.

---

## 1. Core Philosophy: The Smart-Adapter Platform

CyGuide is a modular cybersecurity investigation platform designed for both learning and rapid power-use. The fundamental problem it solves is **tool fragmentation**: security tools produce wildly different outputs (XML, JSON, raw text) that are difficult to correlate.

CyGuide solves this through a **"Smart Adapter / Stupid Framework"** architecture:
*   **The Framework** knows nothing about specific tools (like `nmap`, `whois`, or `gobuster`). It only understands standardized schemas (like `network.host` or `web.endpoint`).
*   **The Adapter** contains the intelligence. It is responsible for running the tool, parsing its stdout/stderr streams, and yielding structured findings that conform to standard schemas.
*   **Benefits**: Adding a new tool is purely additive. It requires writing a single folder in `tools/` with zero changes to the core engine, UI, or database logic.

---

## 2. Domain Context & Terminology

*   **Finding**: The primary unit of data in CyGuide. A finding is a structured piece of information (inheriting from [`BaseFinding`](../../cyguide/schemas/base.py)) emitted by a tool adapter or manually entered.
*   **Schema**: A formal definition of a finding type. It defines the required fields, Primary Identity Keys, and structural relationships (Parent or Association relations) used by the engine to build the graph.
*   **Primary Identity Key (PIK)**: A set of fields in a schema that uniquely identifies an entity (e.g., `ip` for `network.host`). The engine uses PIKs to perform **upserts**—updating existing nodes instead of creating duplicates.
*   **Workspace**: A high-level container representing a project or engagement (e.g. "Internal Audit 2024"). It contains multiple sessions and project-level configurations.
*   **Session**: A specific thread of activity within a workspace.
    *   *Power Session*: A persistent, SQLite-backed investigation context (stored in SQLite) featuring strict tool suggestions, parallel workbenches, and action logs.
    *   *Learning Session*: An ephemeral, guided experience focused on learning a specific tool without persistent graph stores.
*   **Entity Graph**: A stateful, unified map of the target environment for a specific session. It represents the "current truth" of that session, built by linking findings together.
*   **Event Log**: An append-only, immutable record of every finding and action. It serves as our **reproducibility foundation**; a session's entity graph can be fully reconstructed by replaying its event log.
*   **Entity Alias**: A first-class finding (`entity.alias`) that maps two semantically identical but syntactically different identifiers (e.g. hostname to IP). This prevents the engine from making semantic guesses.
*   **Tool Plugin**: A folder in `tools/` containing a metadata `manifest.toml` and an execution `adapter.py` script.
*   **Canonicalization**: The process of normalizing raw inputs (lowercasing domains, stripping whitespace) before they enter the database. This is strictly **syntactic**; semantic merging is handled via aliases.

---

## 3. Layered Execution Flow (Power Mode)

To enable future autonomous AI agents without sacrificing safety, Power Mode implements a strict layered execution pipeline. This separates user intent from process management:

```text
[ TUI (Textual UI) ]
       │ calls
[ PowerWorkspaceFacade ]  <─── Future Agent Layer plugs in here
       │ delegates
[ ActionGateway ]         <─── Policy, validation, and approval gates
       │ passes to
[ Executor ]              <─── Tool adapters and process management
       │ spawns
[ Shell / Tool ]          <─── Raw nmap, gobuster, etc.
```

### Component Roles
1.  **Textual TUI**: Handles rendering, keyboard input, and user selection. It is completely decoupled from tool execution logic.
2.  **PowerWorkspaceFacade**: The single programmatic boundary for the system. It coordinates the data flow between the UI/Agents and the engine.
3.  **ActionGateway**: Validates that the requested action is safe and allowed (e.g., checks target CIDR scopes or blocks blacklisted flags).
4.  **Executor**: Handles process spawning, streaming stdout/stderr line-by-line, and passing output lines to the corresponding adapter parser.

### Architectural Decisions
*   **Universal Variable Substitution**: Variable resolution (e.g., resolving `$TARGET`, `$PORT` inside commands like `nmap -sV $TARGET`) is implemented in the `PowerWorkspaceFacade` rather than the TUI. This ensures identical behavior whether a command is triggered by a human via the Command Palette or programmatically by an AI agent.
*   **ShellAdapter Fallback**: Arbitrary commands (prefixed with `!`) are routed through a generic `ShellAdapter` so they are assigned a job ID, logged in the event log, and displayed in the tabbed workbench like standard tools.
*   **Restricted Commands**: Arbitrary shell commands are restricted to the `USER` source to ensure future autonomous agents only operate within the safe boundaries of registered tools.

---

## 4. SQLite Database Schema

CyGuide uses **SQLite** for three reasons: portability (a session is a single `.db` file), performance at engagement scale (thousands of entities), and zero dependencies. The schema consists of five core tables:

### 1. `workspaces`
Tracks project-level metadata.
*   `id` (TEXT PRIMARY KEY): Unique UUID.
*   `name` (TEXT NOT NULL): Unique project name.
*   `status` (TEXT): `ACTIVE` or `SYSTEM` (for the Learning sandbox).

### 2. `sessions`
Tracks specific sessions under a workspace.
*   `id` (TEXT PRIMARY KEY): Unique UUID.
*   `workspace_id` (TEXT): Foreign key referencing `workspaces(id)` on delete cascade.
*   `name` (TEXT NOT NULL): Name of the session.
*   `status` (TEXT): `ACTIVE` or `CLOSED`.

### 5. `nodes` (The Entity Graph)
Stores the stateful, de-duplicated findings.
*   `session_id` (TEXT): Foreign key referencing `sessions(id)` on delete cascade.
*   `id` (TEXT): Unique entity ID generated from the schema type and PIK.
*   `schema_type` (TEXT NOT NULL): E.g., `network.service`.
*   `pik_json` (TEXT NOT NULL): Serialized Primary Identity Key fields.
*   `data_json` (TEXT NOT NULL): Serialized payload fields.
*   `status` (TEXT): `confirmed` or `proposed` (for recommendations).

### 6. `edges` (The Relationships)
Stores structural and association links between nodes.
*   `session_id` (TEXT): Foreign key referencing `sessions(id)` on delete cascade.
*   `source_id` (TEXT): Node ID originating the link.
*   `target_id` (TEXT): Node ID receiving the link.
*   `relation_type` (TEXT NOT NULL): Edge type (e.g. `parent`, `resolves_to`).

### 7. `event_log` (The Audit Trail)
An append-only log storing every executed command and finding history.
*   `id` (INTEGER PRIMARY KEY AUTOINCREMENT).
*   `session_id` (TEXT): Foreign key referencing `sessions(id)` on delete cascade.
*   `action_payload` (TEXT): Full JSON representation of the `ActionRequest`.
*   `result_payload` (TEXT): Full JSON representation of execution output.
*   `human_readable` (TEXT): Summary string displayed in the UI history.
*   `schema_type` (TEXT): Schema type of findings generated by this event.
*   `finding_json` (TEXT): The findings payload.
*   `closed` (INTEGER): `0` or `1` (tracks if a workbench tab was closed).

---

## 5. Reactivity & Suggestion Engine

To keep the UI responsive and decoupled from the engine, CyGuide implements a store-watching reactivity model:
1.  **Upsert Event**: When findings are upserted, `GraphStore` fires an `on_upsert` callback.
2.  **UI Updates**: The TUI listens to these events and dynamically updates labels, stats, and lists.
3.  **Suggestion Generation**: The `RecommendationEngine` listens to these upsert events and applies declarative rule filters. For example, if a `network.service` is discovered on port `80/443`, the engine inserts a `proposed` finding recommending `gobuster`.
4.  **Deduplication**: Suggestions are given a `status = 'proposed'` in the `nodes` table, preventing infinite suggestion loops while keeping recommendations isolated from the verified target tree.

---

## 6. Project Governance & Tiered Protection

To maintain codebase stability for university submission and professional deployment, we enforce a strict tiered file protection policy:

*   **Tier 1 — Frozen**: Core infrastructure. Changes require deep review and team agreement:
    *   [`cyguide/schemas/base.py`](file:///home/harsh/Documents/cyguide/cyguide/schemas/base.py) (Base schema models and relations).
    *   [`cyguide/engine/store.py`](file:///home/harsh/Documents/cyguide/cyguide/engine/store.py) (SQLite schema, upsert logic, PIK generation).
    *   [`cyguide/engine/canonicalize.py`](file:///home/harsh/Documents/cyguide/cyguide/engine/canonicalize.py) (Normalization logic).
    *   [`cyguide/engine/registry.py`](file:///home/harsh/Documents/cyguide/cyguide/engine/registry.py) (Tool plugin discovery).
*   **Tier 2 — Review Required**: Logical and architectural components:
    *   All plugin `adapter.py` scripts.
    *   [`cyguide/engine/executor.py`](file:///home/harsh/Documents/cyguide/cyguide/engine/executor.py) (Async timeout and process reading).
    *   Database migrations.
    *   New schema models in `cyguide/schemas/`.
*   **Tier 3 — Free to Change**: UI layouts, styles, utility scripts, and documentation:
    *   [`cyguide/ui/`](file:///home/harsh/Documents/cyguide/cyguide/ui) (Screens, widgets, CSS).
    *   [`cyguide/modes/`](file:///home/harsh/Documents/cyguide/cyguide/modes) (Dashboard and screen state machines).
    *   `docs/` and `scripts/` directories.
