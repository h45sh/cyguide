# Domain Knowledge: Storage & Graph Persistence (Tier 2)

## 1. Persistence Seams & Facades
- **Unified Graph Store**: Graph database interactions are encapsulated inside `GraphStore` (`cyguide/engine/store.py:L1`) and `WorkspaceRepository` (`cyguide/engine/workspace_repository.py:L1`).
- **No Direct UI SQLite Calls**: UI widgets (`cyguide/ui/`) must never import or invoke `db.execute()`. All mutations must route through `PowerWorkspaceFacade` (`cyguide/engine/power_facade.py:L16`) or `LearningSession`.
- **Async Execution**: Never run synchronous, blocking SQLite calls directly on the Textual main thread or asyncio event loop. Disk queries and mutations run within dedicated threadpools or background workers.

## 2. Ingestion Performance & Atomic Micro-Batching
- **Batch Insertion Mandate**: Executing individual `INSERT` statements inside loops is strictly prohibited ($O(N)$ transaction overhead). Bulk imports must use `db.executemany()` or `upsert_findings_batch()`.
- **Throughput Contract**: GraphStore ingestion must maintain $\ge 2,000\text{ entities/sec}$ (hard floor $\ge 1,200\text{ entities/sec}$ under shared virtualized CI). 10,000 nodes/edges ingest 2.7x faster using atomic batching.
- **Bulk Query Scale Limits**: 5,000 nodes and 2,500 edges must be queried in $\le 500\text{ms}$ in SQLite via parameter-bound queries and indexed foreign keys.
- **WAL Journaling**: SQLite connections use write-ahead logging (`PRAGMA journal_mode=WAL;`) and synchronous normal mode for high-concurrency readers.

## 3. Lab Checkpointing Architecture (`.cyglab`)
- **Quicksave / Load Checkpoint Pattern**: Educational exploration (Learning Mode) avoids continuous auto-save to prevent polluting databases with broken student states.
- **Zero-Copy Serialization**: Uses zero-copy SQLite attachments (`ATTACH DATABASE`) to snapshot discovered graph nodes, terminal log buffers, Socratic tutor history, and reflection notes into `.cyglab` checkpoint bundles.
- **Atomic Private File Permissions**: Checkpoint files and export archives must be created with explicit atomic private permissions (`0o600` for files, `0o700` for directories) via `os.open` with `O_CREAT | O_WRONLY | O_TRUNC` to prevent TOCTOU permission leakage.
