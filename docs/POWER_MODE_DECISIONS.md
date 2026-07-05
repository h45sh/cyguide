# Power Mode: Implementation & Architectural Decisions

This document records the specific technical decisions and architectural choices made during the implementation of Power Mode.

## 1. Action Gateway Policy (Option B)
**Decision**: Restrict arbitrary shell commands to the `USER` source.
**Rationale**: To ensure future autonomous agents operate within a deterministic and safe sandbox. While human users have full shell access, agents are restricted to registered tools with defined input/output contracts.

## 2. Universal Variable Substitution
**Decision**: Implement `$VARIABLE` resolution in the `PowerWorkspaceFacade` rather than the TUI or individual adapters.
**Rationale**: Centralizing resolution ensures consistent behavior across both registered tools (e.g., `nmap $TARGET`) and raw shell commands (e.g., `ping $TARGET`). It also keeps the UI layer thin and focused on rendering.

## 3. The Professional Workspace UI Pattern
**Decision**: Utilize a split-pane layout with a persistent Entity Browser (Context) and a Tabbed Workbench (Execution).
**Rationale**: Security experts require simultaneous access to structured data (the graph) and raw tool output. Tabs allow for parallel task management without losing the scrollback of long-running scans.

## 4. ShellAdapter Fallback
**Decision**: Create a dedicated `ToolAdapter` for unregistered commands.
**Rationale**: By routing arbitrary commands through a `ShellAdapter`, they remain integrated into the standard pipeline: they are logged in the event log, assigned a job ID, and displayed in the tabbed workbench, despite having no predefined output parser.

## 5. Event Log Structure
**Decision**: Store full JSON `ActionRequest` and `Result` payloads alongside human-readable strings.
**Rationale**: The human-readable string is optimized for the UI history view, while the JSON payloads provide a structured observation feed for future AI agents to reason about past actions and their outcomes.

## 6. Context-Aware Palette
**Decision**: Implement a live `on_input_changed` callback to update the `[tool]` vs `[shell]` indicator.
**Rationale**: Provides immediate feedback to the user regarding how CyGuide will interpret and process their command (i.e., whether graph findings will be automatically generated).
