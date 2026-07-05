# Power Mode: Advanced Operator Workspace

┌─────────────────────────┬────────────────────────────────────────────────────┐
│ SESSION: 04:43:44       │ [nmap#1 ✓] [gobuster ●] [+]                        │
│ DEFAULT PROJECT         │────────────────────────────────────────────────────│
│─────────────────────────│                                                    │
│ ENTITY BROWSER          │ > nmap -sV 10.10.10.5                              │
│                         │ Starting Nmap 7.93...                              │
│ ▼ Hosts                 │ PORT   STATE SERVICE VERSION                       │
│   ▼ 10.10.10.5          │ 22/tcp open  ssh     OpenSSH 8.2p1                 │
│     ├─ 22/tcp  ssh      │ 80/tcp open  http    Apache 2.4.49                 │
│     └─ 80/tcp  http     │                                                    │
│   ▷ 10.10.10.6          │ [12:05] Done. 2 entities added.                    │
│                         │                                                    │
│ ▼ Web                   │                                                    │
│   └─ /admin (403)       │                                                    │
│                         │                                                    │
│ ▼ Credentials           │                                                    │
│   └─ admin:admin123     │                                                    │
│─────────────────────────│                                                    │
│ JOB QUEUE               │                                                    │
│                         │                                                    │
│ ✓ nmap#1   0:45  DONE   │────────────────────────────────────────────────────│
│ ● gobuster 1:23  RUN    │ cyguide ❯ _                                        │
│ ○ nikto    --    QUEUE  │ ctx: 10.10.10.5 | p:80 | svc:http                  │
└[Esc]Dashboard─[^b]Sidebar─[^k]Kill─[Tab]Jobs─[^n]Notes─[^e]Export────────────┘

## 1. Core Philosophy
Power Mode transforms CyGuide from a learning tool into a professional cybersecurity workstation. It is designed as an **Advanced Operator Workspace** for experienced practitioners—providing the raw power of the command line with the structured context of a graph database.

### Design Mandates:
1.  **Keyboard-First**: Optimized for rapid entry and navigation without a mouse.
2.  **Raw Transparency**: Never hide the raw output of a tool; experts trust the source.
3.  **Contextual Memory**: Automatically resolve variables (IPs, ports) based on the current selection.
4.  **Deterministic Harness**: The UI and future AI agents use the exact same API, ensuring safety and auditability.

## 2. Layered Architecture
Power Mode implements a strict five-layer execution flow to decouple intent from execution and prepare for future autonomy.

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

### Component Responsibilities:
-   **TUI**: Handles rendering, keyboard input, and user selection. It knows nothing about tool execution logic.
-   **PowerWorkspaceFacade**: The single entry point for the system. It coordinates the data flow between the UI/Agents and the engine.
-   **ActionGateway**: Validates that the requested action is safe and allowed (e.g., checks CIDR scopes or blocked flags).
-   **Executor**: Standardized execution of tool adapters.

## 3. Data & State Models

### 3.1 Investigation-Scoped Sessions
Unlike "scans" which are often one-offs, Power Mode operates on **Sessions**. A session is a persistent investigation context (stored in SQLite) that groups all findings, actions, and events for a specific engagement.

### 3.2 Typed Actions (`ActionRequest`)
Every tool execution is represented as a structured object:
- `session_id`: The investigation context.
- `tool_name`: The adapter to invoke.
- `target_entity_id`: The specific graph node being targeted.
- `params`: Raw flags or configuration.
- `triggered_by`: Source of the action (`USER`, `SUGGESTION`, `AGENT`).

### 3.3 The Event Log
Every action and its resulting findings are appended to an **Event Log**. This serves two purposes:
1.  **Human History**: A scrollable log of "What happened and when."
2.  **Agent Observation**: A structured feed for future AI planners to understand the current state of the investigation.

## 4. Contextual Intelligence

### 4.1 Variable Resolution
Power Mode eliminates copy-pasting via a context-aware Command Palette.
- Selecting a **Host** node in the Entity Browser resolves `$TARGET`.
- Selecting a **Service** node resolves `$TARGET`, `$PORT`, and `$SERVICE`.
The Command Palette automatically translates `nmap -sV $TARGET` into a concrete execution using these resolved values.

### 4.2 WorkspaceContext
The Facade exposes a `get_context()` method that provides a "point-in-time" snapshot of the investigation, including:
- Resolved variables for the currently selected entity.
- Active and queued job statuses.
- Entity counts and summary statistics.

## 5. UI Layout Specification

| Panel | Component | Responsibility |
| :--- | :--- | :--- |
| **Entity Browser** (Left) | `Tree` | Hierarchical view of the GraphStore (Hosts > Services > Web). |
| **Job Queue** (Bottom Left) | `ListView` | Real-time status of running and queued tasks. |
| **Workbench** (Center) | `Tabs` | Parallel output views. Each tool run (`tool#N`) gets its own terminal tab. |
| **Command Palette** (Bottom) | `Input` | Autocomplete-enabled prompt with a dedicated context-resolution line. |

## 6. Path to Autonomy (Stage C & D)
This architecture is designed to support future agentic features without structural changes:
1.  **Suggestions**: The Facade can return `proposed` findings (flagged in the schema) which appear in the UI for user approval.
2.  **Autonomous Loops**: An agent can read the `WorkspaceContext` and `EventLog`, propose an `ActionRequest`, and submit it through the `PowerWorkspaceFacade`.
3.  **Policy Enforcement**: The `ActionGateway` remains the final arbiter of what is allowed to run on the network, regardless of whether a human or an AI initiated it.

## 7. Implementation Resources
- [Power Mode Progress Tracker](POWER_MODE_PROGRESS.md)
- [Implementation & Architectural Decisions](POWER_MODE_DECISIONS.md)

