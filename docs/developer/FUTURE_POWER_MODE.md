# CyGuide Future: Power Mode as an Agent Harness

This folder sketches a future-proof direction for CyGuide where **Power Mode** evolves from a context-aware terminal into a controlled cybersecurity agent harness.

The core principle:

> Keep CyGuide deterministic. Let AI sit above it as an optional planner/operator, never inside the trusted core.

## 1. High-Level Architecture

```text
┌─────────────────────────────────────────────────────────────────────┐
│                            Power Mode UI                            │
│                                                                     │
│  Context terminal │ Graph browser │ Suggestions │ Run history       │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Power Workspace API                         │
│                                                                     │
│  get_context()  run_action()  list_tools()  read_graph()  export()  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
┌─────────────────┐   ┌─────────────────┐   ┌────────────────────────┐
│ Context Builder │   │ Action Gateway  │   │ Policy / Approval Layer │
│                 │   │                 │   │                        │
│ target/session  │   │ validates and   │   │ scope, rate limits,     │
│ findings/tools  │   │ executes typed  │   │ user approval, safety   │
│ history/notes   │   │ actions         │   │ boundaries              │
└────────┬────────┘   └────────┬────────┘   └───────────┬────────────┘
         │                     │                        │
         ▼                     ▼                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Deterministic Core                          │
│                                                                     │
│  GraphStore │ ToolRegistry │ Executor │ EventLog │ Schemas │ Modes  │
└─────────────────────────────────────────────────────────────────────┘
                                ▲
                                │ observations/results
                                │
┌───────────────────────────────┴─────────────────────────────────────┐
│                         Optional Agent Layer                         │
│                                                                     │
│  planner │ critic │ reporter │ multi-agent coordinator │ evaluator  │
└─────────────────────────────────────────────────────────────────────┘
```

## 2. The Five Future Modules

### Module 1: `PowerWorkspaceAPI`

The stable boundary between UI, deterministic engine, and future AI agents.

It should expose typed operations such as:

```python
get_context(session_id) -> WorkspaceContext
list_available_tools(context) -> list[ToolDescriptor]
run_action(session_id, action) -> ActionResult
read_graph(session_id, filters=None) -> GraphSnapshot
export_report(session_id, format="markdown") -> ExportResult
```

This prevents agents from directly touching internals like SQLite, Textual widgets, or adapter instances.

---

### Module 2: `WorkspaceContextBuilder`

Builds a compact, structured representation of the current investigation.

Example context fields:

```python
WorkspaceContext:
  workspace_id
  session_id
  active_target
  selected_entity
  known_hosts
  known_services
  known_web_endpoints
  available_tools
  recent_events
  notes
  constraints
```

This is what a human sees in Power Mode and what an AI agent would receive later.

Important rule:

> Context should be generated from trusted state, not from model memory.

---

### Module 3: `ActionGateway`

The only path for executing meaningful operations.

Actions should be typed and auditable:

```python
RunToolAction:
  tool_name: "nmap"
  target_entity_id: "..."
  params:
    raw_flags: "-sV -Pn"

AddNoteAction:
  text: "Port 80 looks like a web target."

ExportReportAction:
  format: "markdown"
```

The gateway validates:

- does the tool exist?
- does the selected entity match the tool input contract?
- are required params present?
- does policy allow this action?
- should the user approve it first?

This makes AI safe because it can only request actions, not execute arbitrary behavior.

---

### Module 4: `PolicyAndApprovalLayer`

Cybersecurity agents need hard boundaries.

This module controls:

- allowed target scopes
- blocked commands/flags
- rate limits
- dangerous scan modes
- user approval requirements
- environment restrictions
- logging/audit requirements

Example policy:

```yaml
scope:
  allowed_targets:
    - 127.0.0.1
    - 10.10.10.0/24

actions:
  run_tool:
    require_approval: true
  destructive_actions:
    allowed: false

tools:
  nmap:
    blocked_flags:
      - --script vuln
      - -A
```

Early CyGuide can keep this simple. Future agent mode will need it badly.

---

### Module 5: `AgentOrchestrator` optional, later

This is added after Power Mode is mature.

The orchestrator does not own the system. It only loops over context and actions:

```text
1. Read context
2. Propose next step
3. Ask policy/approval
4. Run action through ActionGateway
5. Observe result
6. Update notes/report
7. Repeat or stop
```

Possible future agent roles:

- **Recon Agent**: chooses enumeration steps
- **Web Agent**: follows HTTP findings
- **Explainer Agent**: teaches the user what happened
- **Reporter Agent**: turns event log into a report
- **Critic Agent**: checks if the plan is safe and reasonable

The important design rule:

> Agents are replaceable operators. The harness is the product.

## 3. Recommended Development Path

### Stage A: Current Project

Finish deterministic core and human-first Power Mode.

Focus on:

- target selection
- real session graph
- tool execution from selected entities
- persisted run history
- context-aware tool suggestions
- Markdown report export

### Stage B: Harness-Ready Power Mode

Add the stable API and typed actions.

Deliverables:

- `WorkspaceContext`
- `Action` models
- `ActionGateway`
- policy checks
- approval prompts
- full event logging

At this point, Power Mode becomes a harness even without AI.

### Stage C: AI-Lite

Add non-autonomous AI features:

- explain selected finding
- summarize session
- suggest next commands
- draft report

AI can advise, but the user clicks/runs.

### Stage D: Agent Mode

Add controlled autonomy:

- bounded tasks
- explicit scope
- approval gates
- budget/rate limits
- stop conditions
- replayable audit trail

Example command:

```text
/agent recon --target 10.10.10.5 --max-actions 5 --approval each-step
```

## 4. Design Decisions to Make Now

These choices avoid a future overhaul:

1. Power Mode should operate on **session state**, not hardcoded targets.
2. Tool runs should be represented as **typed actions**.
3. Every action/result should be written to the **event log**.
4. UI should call a **PowerWorkspaceAPI**, not low-level executor methods directly.
5. AI output should be stored as **notes/proposals**, not trusted findings unless validated.
6. Policy should exist before autonomy, even if simple.

## 5. Short Verdict

Yes: CyGuide can become a strong cybersecurity agent harness later.

No: it does not require a major overhaul if Power Mode is designed around context, typed actions, policy, and event logs now.

The best near-term architecture is:

> Human-first contextual terminal today. Agent-ready action harness tomorrow. Controlled multi-agent cybersecurity platform later.
