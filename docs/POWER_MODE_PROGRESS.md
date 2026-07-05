# Power Mode Progress Tracker

## Status: Foundational Implementation Complete

### 1. Implemented Features
- [x] **Investigation-Scoped Sessions**: Persistent session identity in SQLite.
- [x] **Typed Action System**: `ActionRequest` models with `triggered_by` field.
- [x] **Structured Event Log**: Captures action payloads, result summaries, and raw shell commands.
- [x] **Action Gateway (Option B)**: 
    - Full validation for registered tools.
    - Raw shell command passthrough for `USER` source only.
    - Rejection of unregistered tools for non-human sources.
- [x] **Universal Variable Substitution**: `$TARGET`, `$PORT`, `$SERVICE` resolution in the Facade layer.
- [x] **Entity Browser (Tree)**: Hierarchical view of findings (Hosts, Web, etc.).
- [x] **Tabbed Job Workbench**: Parallel tool execution with independent log tabs.
- [x] **Job Control**: Implementation of `ctrl+k` (Kill Job) to terminate background processes.
- [x] **Tab Navigation**: `ctrl+pageup` and `ctrl+pagedown` to cycle between active job outputs. (`Tab` reserved for TUI navigation).
- [x] **Smart Command Palette**: 
    - Visual mode indicators: `[tool]` vs `[shell]`.
    - Live context resolution line.
    - Forced shell mode with `!` prefix and `ctrl+l` toggle.
- [x] **Shell Adapter**: Fallback for arbitrary terminal command execution.

### 2. Remaining Tasks
- [ ] **Workbench Persistence**: Logic to restore tab logs from the event log upon re-entering a session.
- [ ] **Advanced Entity Grouping**: Refining the Tree logic to handle complex parent-child relations (e.g. Services under specific Hosts).
- [ ] **Tab Lifecycle Management**: UI for closing finished tabs.
- [ ] **AI Suggestions Pane**: Integration of the `proposed` finding status into the UI.
- [ ] **Export Feature**: Markdown report generation from the event log.
- [ ] **Note Taking**: Implementation of the `ctrl+n` Scratchpad overlay.
