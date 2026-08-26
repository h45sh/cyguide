# CyGuide System Architecture & Engineering Blueprint

Welcome to the system architecture specification for CyGuide.

> [!NOTE]
> The primary authoritative architecture document is maintained in [`docs/developer/ARCHITECTURE.md`](docs/developer/ARCHITECTURE.md).

For the complete in-depth blueprint covering the Smart-Adapter platform, layered execution pipeline, universal variable substitution, dynamic plugin discovery, reactive recommendation engine, AI explainer, and Architectural Decision Records (ADRs), please see:

👉 **[Complete Architecture Documentation (`docs/developer/ARCHITECTURE.md`)](docs/developer/ARCHITECTURE.md)**

---

## Quick Reference Summary

### Core Execution Flow
```text
[ TUI (Textual) / AI Agents ]
             │
   [ PowerWorkspaceFacade ]   <── Universal Variable Resolution ($TARGET, $PORT)
             │
     [ ActionGateway ]        <── Policy & Source Validation (USER vs AGENT)
             │
      [ Async Executor ]      <── Subprocess Spawning & Non-blocking Stream Draining
             │
     [ Tool Adapters ]        <── Emits standardized BaseFinding streams to GraphStore
```

### Architectural Highlights
* **Smart Adapter / Stupid Framework**: Zero engine changes needed to add new tools under `tools/`.
* **Universal Variable Resolution**: Unified `$TARGET`, `$PORT`, `$SERVICE` evaluation in the facade layer for both operators and autonomous agents.
* **Reactive Suggestion Engine**: Event-driven recommendations (`status = 'proposed'`) triggered on finding ingestion.
* **Portability Subsystem**: Transactional export/import using SQLite `ATTACH DATABASE`.

For full details, diagrams, sequence charts, and ADRs, refer to [docs/developer/ARCHITECTURE.md](docs/developer/ARCHITECTURE.md).
