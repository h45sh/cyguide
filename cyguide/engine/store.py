# PROTECTED FILE — See CONTRIBUTING.md before modifying.
# Changes to this file require team agreement.
"""SQLite-based graph store for workspaces and sessions."""

import asyncio
import functools
import hashlib
import json
import logging
import os
import re
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Set

import aiosqlite

from cyguide.engine.timeline import ActionTimelineRepository
from cyguide.schemas.base import BaseFinding
from cyguide.schemas.power import ActionRequest

logger = logging.getLogger(__name__)

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT DEFAULT 'ACTIVE',
    closed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT DEFAULT 'ACTIVE',
    closed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS nodes (
    session_id TEXT NOT NULL,
    id TEXT NOT NULL,
    schema_type TEXT NOT NULL,
    pik_json TEXT NOT NULL,
    data_json TEXT NOT NULL,
    status TEXT DEFAULT 'confirmed',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (session_id, id),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS edges (
    session_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    PRIMARY KEY (session_id, source_id, target_id, relation_type),
    FOREIGN KEY (session_id, source_id) REFERENCES nodes(session_id, id) ON DELETE CASCADE,
    FOREIGN KEY (session_id, target_id) REFERENCES nodes(session_id, id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS event_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    action_payload TEXT,
    result_payload TEXT,
    human_readable TEXT,
    schema_type TEXT,
    finding_json TEXT,
    closed INTEGER DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS notes (
    scope_type TEXT NOT NULL,
    scope_id TEXT NOT NULL,
    content TEXT DEFAULT '',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (scope_type, scope_id)
);
CREATE INDEX IF NOT EXISTS idx_nodes_session_schema ON nodes(session_id, schema_type);
CREATE INDEX IF NOT EXISTS idx_edges_session ON edges(session_id);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(session_id, source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(session_id, target_id);
CREATE INDEX IF NOT EXISTS idx_event_log_session_time ON event_log(session_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_ws_status ON sessions(workspace_id, status);
CREATE INDEX IF NOT EXISTS idx_workspaces_status ON workspaces(status);
CREATE INDEX IF NOT EXISTS idx_notes_scope ON notes(scope_type, scope_id);
CREATE INDEX IF NOT EXISTS idx_nodes_session_updated ON nodes(session_id, updated_at DESC);
"""


@functools.lru_cache(maxsize=4096)
def _cached_node_id(schema_type: str, pik_items: tuple) -> str:
    """Compute and cache deterministic SHA-256 node ID from sorted PIK items."""
    pik_str = json.dumps(dict(pik_items), sort_keys=True)
    return hashlib.sha256(f"{schema_type}:{pik_str}".encode()).hexdigest()


class GraphStore:
    """Manages workspaces, sessions, and stateful entity graphs."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._on_upsert_callbacks = []
        self._on_batch_callbacks = []
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock: Optional[asyncio.Lock] = None
        self._closed: bool = False
        self._session_bloom: Dict[str, Any] = {}
        self._warmed_sessions: Set[str] = set()
        self.timeline = ActionTimelineRepository(self)

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _get_bloom(self, session_id: str):
        """Get or initialize in-memory Bloom filter for fast node ID pre-filtering."""
        from cyguide.common.algorithms import BloomFilter

        if session_id not in self._session_bloom:
            self._session_bloom[session_id] = BloomFilter(capacity=25000, error_rate=0.01)
        return self._session_bloom[session_id]

    def on_upsert(self, callback):
        """Register an async callback to fire when any finding is upserted."""
        self._on_upsert_callbacks.append(callback)

    def on_findings_batch(self, callback):
        """Register an async callback to fire when a batch of findings is upserted."""
        self._on_batch_callbacks.append(callback)

    @asynccontextmanager
    async def connection(self):
        """Public context manager for acquiring a database connection."""
        async with self._get_conn() as conn:
            yield conn

    @asynccontextmanager
    async def _get_conn(self):
        """Helper to get a connection, supporting persistent connection for all paths."""
        if self._closed:
            raise ValueError("Cannot operate on a closed database.")
        async with self._get_lock():
            if self._conn is None:
                if self.db_path != ":memory:":
                    db_dir = os.path.dirname(os.path.abspath(self.db_path))
                    if db_dir:
                        os.makedirs(db_dir, exist_ok=True)
                self._conn = await aiosqlite.connect(self.db_path)
                await self._conn.execute("PRAGMA foreign_keys = ON")
                await self._conn.execute("PRAGMA trusted_schema = OFF")
                await self._conn.execute("PRAGMA busy_timeout = 5000")
                if self.db_path != ":memory:":
                    await self._conn.execute("PRAGMA journal_mode = WAL")
                    await self._conn.execute("PRAGMA synchronous = NORMAL")
                if self.db_path != ":memory:" and os.path.exists(self.db_path):
                    try:
                        os.chmod(self.db_path, 0o600)
                    except OSError:
                        pass
            yield self._conn

    async def initialize(self):
        """Create tables if they don't exist."""
        async with self._get_conn() as db:
            await db.executescript(SCHEMA_DDL)
            await db.commit()

    async def check_integrity(self) -> tuple[str, list[str]]:
        """Run an SQLite integrity check and return status and table list."""
        async with self._get_conn() as db:
            cursor = await db.execute("PRAGMA integrity_check")
            row = await cursor.fetchone()
            integrity_status = row[0] if row else "unknown"

            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in await cursor.fetchall()]
            return integrity_status, tables

    async def close(self):
        """Close the persistent connection if it exists."""
        self._closed = True
        if self._conn:
            try:
                await self._conn.close()
            except Exception:
                pass
            self._conn = None

    async def get_or_create_learning_sandbox(self) -> tuple[str, str]:
        """Ensure the singleton Learning Sandbox and its session exist and return their IDs."""
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            # 1. Check for existing Learning Sandbox
            cursor = await db.execute(
                "SELECT id FROM workspaces WHERE name = 'Learning Sandbox' LIMIT 1"
            )
            row = await cursor.fetchone()
            if row:
                ws_id = row["id"]
            else:
                ws_id = str(uuid.uuid4())
                await db.execute(
                    "INSERT INTO workspaces (id, name, status) VALUES (?, ?, ?)",
                    (ws_id, "Learning Sandbox", "SYSTEM"),
                )

            # 2. Check for existing Guided Session
            cursor = await db.execute(
                "SELECT id FROM sessions WHERE workspace_id = ? AND name = 'Guided Session' LIMIT 1",
                (ws_id,),
            )
            row = await cursor.fetchone()
            if row:
                sess_id = row["id"]
            else:
                sess_id = str(uuid.uuid4())
                await db.execute(
                    "INSERT INTO sessions (id, workspace_id, name, status) VALUES (?, ?, ?, ?)",
                    (sess_id, ws_id, "Guided Session", "SYSTEM"),
                )

            await db.commit()
            return ws_id, sess_id

    # --- Workspace Management ---

    async def create_workspace(self, name: str) -> str:
        workspace_id = str(uuid.uuid4())
        async with self._get_conn() as db:
            await db.execute(
                "INSERT INTO workspaces (id, name) VALUES (?, ?)", (workspace_id, name)
            )
            await db.commit()
        return workspace_id

    async def rename_workspace(self, workspace_id: str, new_name: str) -> None:
        async with self._get_conn() as db:
            await db.execute(
                "UPDATE workspaces SET name = ? WHERE id = ?", (new_name, workspace_id)
            )
            await db.commit()

    async def list_workspaces(self, status_filter: Optional[str] = None) -> List[Dict]:
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            if status_filter:
                cursor = await db.execute(
                    "SELECT * FROM workspaces WHERE status = ? ORDER BY created_at DESC",
                    (status_filter,),
                )
            else:
                cursor = await db.execute("SELECT * FROM workspaces ORDER BY created_at DESC")
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_workspace(self, workspace_id: str) -> Optional[Dict]:
        """Get workspace metadata."""
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def close_workspace(self, workspace_id: str) -> None:
        """Mark workspace as closed/archived."""
        async with self._get_conn() as db:
            await db.execute(
                "UPDATE workspaces SET status = 'CLOSED', closed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (workspace_id,),
            )
            await db.commit()

    async def reopen_workspace(self, workspace_id: str) -> None:
        """Reopen a closed workspace."""
        async with self._get_conn() as db:
            await db.execute(
                "UPDATE workspaces SET status = 'ACTIVE', closed_at = NULL WHERE id = ?",
                (workspace_id,),
            )
            await db.commit()

    # --- Session Management ---

    async def create_session(self, workspace_id: str, name: str) -> str:
        session_id = str(uuid.uuid4())
        async with self._get_conn() as db:
            await db.execute(
                "INSERT INTO sessions (id, workspace_id, name) VALUES (?, ?, ?)",
                (session_id, workspace_id, name),
            )
            await db.commit()
        return session_id

    async def rename_session(self, session_id: str, new_name: str) -> None:
        async with self._get_conn() as db:
            await db.execute("UPDATE sessions SET name = ? WHERE id = ?", (new_name, session_id))
            await db.commit()

    async def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session metadata."""
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def list_sessions(
        self, workspace_id: str, status_filter: Optional[str] = None
    ) -> List[Dict]:
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            if status_filter:
                cursor = await db.execute(
                    "SELECT * FROM sessions WHERE workspace_id = ? AND status = ? ORDER BY created_at DESC",
                    (workspace_id, status_filter),
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM sessions WHERE workspace_id = ? ORDER BY created_at DESC",
                    (workspace_id,),
                )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def close_session(self, session_id: str) -> None:
        """Mark session as closed/archived."""
        async with self._get_conn() as db:
            await db.execute(
                "UPDATE sessions SET status = 'CLOSED', closed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,),
            )
            await db.commit()

    async def reopen_session(self, session_id: str) -> None:
        """Reopen an archived session back to ACTIVE."""
        async with self._get_conn() as db:
            await db.execute(
                "UPDATE sessions SET status = 'ACTIVE', closed_at = NULL WHERE id = ?",
                (session_id,),
            )
            await db.commit()

    async def delete_workspace(self, workspace_id: str):
        """Delete a workspace and all its sessions/graphs (cascade)."""
        async with self._get_conn() as db:
            await db.execute("PRAGMA foreign_keys = ON")
            await db.execute(
                """
                DELETE FROM notes
                WHERE scope_type IN ('session', 'learning')
                  AND scope_id IN (SELECT id FROM sessions WHERE workspace_id = ?)
                """,
                (workspace_id,),
            )
            await db.execute(
                "DELETE FROM notes WHERE scope_type = 'workspace' AND scope_id = ?",
                (workspace_id,),
            )
            await db.execute("DELETE FROM workspaces WHERE id = ?", (workspace_id,))
            await db.commit()

    async def delete_session(self, session_id: str):
        """Delete a single session, its graph data, and its notes."""
        async with self._get_conn() as db:
            await db.execute("PRAGMA foreign_keys = ON")
            await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            await db.execute(
                "DELETE FROM notes WHERE (scope_type = 'session' AND scope_id = ?) OR (scope_type = 'learning' AND scope_id = ?)",
                (session_id, session_id),
            )
            await db.commit()

    # --- Notes Management ---

    async def get_notes(self, scope_type: str, scope_id: str) -> str:
        """Fetch persistent notes for a specific scope (e.g. 'session' or 'learning')."""
        async with self._get_conn() as db:
            cursor = await db.execute(
                "SELECT content FROM notes WHERE scope_type = ? AND scope_id = ?",
                (scope_type, str(scope_id)),
            )
            row = await cursor.fetchone()
            return row[0] if row and row[0] is not None else ""

    async def save_notes(self, scope_type: str, scope_id: str, content: str) -> None:
        """Atomically persist notes for a specific scope in SQLite."""
        async with self._get_conn() as db:
            await db.execute(
                """
                INSERT INTO notes (scope_type, scope_id, content, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(scope_type, scope_id) DO UPDATE SET
                    content = excluded.content,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (scope_type, str(scope_id), content),
            )
            await db.commit()

    async def move_session(self, session_id: str, target_workspace_id: str):
        """Move a session to a different workspace."""
        async with self._get_conn() as db:
            await db.execute(
                "UPDATE sessions SET workspace_id = ? WHERE id = ?",
                (target_workspace_id, session_id),
            )
            await db.commit()

    async def get_recent_activity(self, workspace_id: str, limit: int = 5) -> List[Dict]:
        """Fetch latest events across all sessions in a workspace."""
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            query = """
                SELECT e.*, s.name as session_name
                FROM event_log e
                JOIN sessions s ON e.session_id = s.id
                WHERE s.workspace_id = ? AND (e.closed IS NULL OR e.closed = 0)
                ORDER BY e.timestamp DESC LIMIT ?
            """
            cursor = await db.execute(query, (workspace_id, limit))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # --- Graph Data Persistence (Session Aware) ---

    def generate_node_id(self, schema_type: str, pik: Dict[str, Any]) -> str:
        """Deterministically compute entity node ID from schema type and primary identity keys."""
        try:
            items = tuple(sorted(pik.items()))
            return _cached_node_id(schema_type, items)
        except TypeError:
            pik_str = json.dumps(pik, sort_keys=True)
            return hashlib.sha256(f"{schema_type}:{pik_str}".encode()).hexdigest()

    async def upsert_findings_batch(
        self, session_id: str, findings: List[BaseFinding]
    ) -> List[str]:
        """Atomically upsert a batch of findings in a single SQLite transaction."""
        if not findings:
            return []

        node_ids: List[str] = []
        event_log_params = []
        unique_node_ids: List[str] = []
        seen = set()
        node_metadata: Dict[str, Dict[str, Any]] = {}

        parent_nodes: Dict[str, tuple] = {}
        parent_edges: set = set()
        assoc_nodes: Dict[str, tuple] = {}
        assoc_edges: set = set()

        for finding in findings:
            node_id = self.generate_node_id(finding.schema_type, finding.pik)
            node_ids.append(node_id)

            event_log_params.append(
                (
                    session_id,
                    finding.schema_type,
                    finding.model_dump_json(),
                    f"Discovered {finding.schema_type}",
                    "{}",
                    "{}",
                )
            )

            if node_id not in seen:
                seen.add(node_id)
                unique_node_ids.append(node_id)
                node_metadata[node_id] = {
                    "schema_type": finding.schema_type,
                    "pik": finding.pik,
                    "data": dict(finding.data),
                    "status": finding.status,
                }
            else:
                node_metadata[node_id]["data"].update(finding.data)
                node_metadata[node_id]["status"] = finding.status

            if finding.parent:
                p = finding.parent
                parent_id = self.generate_node_id(p.target_type, p.target_pik)
                parent_nodes[parent_id] = (
                    session_id,
                    parent_id,
                    p.target_type,
                    json.dumps(p.target_pik),
                    "{}",
                )
                parent_edges.add((session_id, parent_id, node_id, p.via))

            for assoc in finding.associations:
                assoc_id = self.generate_node_id(assoc.target_type, assoc.target_pik)
                assoc_nodes[assoc_id] = (
                    session_id,
                    assoc_id,
                    assoc.target_type,
                    json.dumps(assoc.target_pik),
                    "{}",
                )
                assoc_edges.add((session_id, node_id, assoc_id, assoc.via))

        bloom = self._get_bloom(session_id)

        async with self._get_conn() as db:
            # Warm up bloom filter for this session if newly accessed
            if session_id not in self._warmed_sessions:
                cursor = await db.execute(
                    "SELECT id FROM nodes WHERE session_id = ?", (session_id,)
                )
                rows = await cursor.fetchall()
                for (nid,) in rows:
                    bloom.add(nid)
                self._warmed_sessions.add(session_id)

            # 1. Log the events in a single batch
            await db.executemany(
                """INSERT INTO event_log (session_id, schema_type, finding_json, human_readable, action_payload, result_payload)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                event_log_params,
            )

            # 2. Fetch existing data only for candidate node IDs that might exist in this session (via Bloom filter)
            candidate_ids = [nid for nid in unique_node_ids if nid in bloom]
            if candidate_ids:
                for i in range(0, len(candidate_ids), 500):
                    chunk = candidate_ids[i : i + 500]
                    placeholders = ",".join("?" for _ in chunk)
                    query_parts = (
                        "SELECT id, data_json FROM nodes WHERE session_id = ? AND id IN (",
                        placeholders,
                        ")",
                    )
                    select_sql = "".join(query_parts)
                    cursor = await db.execute(select_sql, [session_id, *chunk])
                    rows = await cursor.fetchall()
                    for r_id, r_data in rows:
                        if r_data:
                            merged = json.loads(r_data)
                            merged.update(node_metadata[r_id]["data"])
                            node_metadata[r_id]["data"] = merged

            # 3. Batch upsert the nodes
            nodes_params = [
                (
                    session_id,
                    nid,
                    meta["schema_type"],
                    json.dumps(meta["pik"]),
                    json.dumps(meta["data"]),
                    meta["status"],
                )
                for nid, meta in node_metadata.items()
            ]
            await db.executemany(
                """INSERT INTO nodes (session_id, id, schema_type, pik_json, data_json, status)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(session_id, id) DO UPDATE SET
                       data_json = excluded.data_json,
                       status = excluded.status,
                       updated_at = CURRENT_TIMESTAMP""",
                nodes_params,
            )

            # 4. Handle Parent and Association Relations (Auto-wiring in consolidated batches)
            rel_nodes = list(parent_nodes.values())
            if assoc_nodes:
                rel_nodes.extend(assoc_nodes.values())
            if rel_nodes:
                await db.executemany(
                    "INSERT OR IGNORE INTO nodes (session_id, id, schema_type, pik_json, data_json) VALUES (?, ?, ?, ?, ?)",
                    rel_nodes,
                )

            rel_edges = list(parent_edges | assoc_edges)
            if rel_edges:
                await db.executemany(
                    "INSERT OR IGNORE INTO edges (session_id, source_id, target_id, relation_type) VALUES (?, ?, ?, ?)",
                    rel_edges,
                )

            await db.commit()

        # Update Bloom filter with all newly upserted node IDs and relationship nodes
        for nid in unique_node_ids:
            bloom.add(nid)
        for p_nid in parent_nodes:
            bloom.add(p_nid)
        for a_nid in assoc_nodes:
            bloom.add(a_nid)

        # Trigger reactive callbacks
        if self._on_batch_callbacks and findings:
            for cb in self._on_batch_callbacks:
                try:
                    await cb(session_id, findings)
                except Exception as e:
                    logger.error(
                        f"Error in reactive batch callback {getattr(cb, '__name__', 'callback')}: {e}"
                    )

        if self._on_upsert_callbacks and findings:
            for finding in findings:
                for cb in self._on_upsert_callbacks:
                    try:
                        await cb(session_id, finding)
                    except Exception as e:
                        logger.error(
                            f"Error in reactive callback {getattr(cb, '__name__', 'callback')}: {e}"
                        )

        return node_ids

    async def upsert_finding(self, session_id: str, finding: BaseFinding) -> str:
        """Upsert a single finding (delegates to upsert_findings_batch)."""
        node_ids = await self.upsert_findings_batch(session_id, [finding])
        return node_ids[0] if node_ids else ""

    async def query(self, schema_type: str, session_id: Optional[str] = None) -> List[Dict]:
        """Fetch all nodes of a specific schema type."""
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            if session_id:
                cursor = await db.execute(
                    "SELECT * FROM nodes WHERE session_id = ? AND schema_type = ?",
                    (session_id, schema_type),
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM nodes WHERE schema_type = ?", (schema_type,)
                )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_event_log(self, session_id: str) -> List[Dict]:
        """Fetch all events for a session."""
        return await self.timeline.get_event_log(session_id)

    async def mark_event_closed(self, action_id: str, session_id: Optional[str] = None) -> None:
        """Mark an event log entry as closed/deleted."""
        await self.timeline.mark_event_closed(action_id, session_id)

    async def get_closed_events_count(self, session_id: str) -> int:
        """Get the count of closed events/tabs for a session."""
        return await self.timeline.get_closed_events_count(session_id)

    async def get_all_nodes(self, session_id: str) -> List[Dict]:
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM nodes WHERE session_id = ? ORDER BY updated_at DESC", (session_id,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_all_edges(self, session_id: str) -> List[Dict]:
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM edges WHERE session_id = ?", (session_id,))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_workspace_nodes(self, workspace_id: str) -> List[Dict]:
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT n.* FROM nodes n
                   JOIN sessions s ON n.session_id = s.id
                   WHERE s.workspace_id = ? ORDER BY n.updated_at DESC""",
                (workspace_id,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_workspace_edges(self, workspace_id: str) -> List[Dict]:
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT e.* FROM edges e
                   JOIN sessions s ON e.session_id = s.id
                   WHERE s.workspace_id = ?""",
                (workspace_id,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_node(self, session_id: str, node_id: str) -> Optional[Dict]:
        """Fetch a specific node by ID."""
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM nodes WHERE session_id = ? AND id = ?", (session_id, node_id)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_node_data(
        self, session_id: str, node_id: str, updates: Dict[str, Any]
    ) -> None:
        """Update fields inside a node's data_json (such as custom alias, name, or notes)."""
        async with self._get_conn() as db:
            cursor = await db.execute(
                "SELECT data_json FROM nodes WHERE session_id = ? AND id = ?", (session_id, node_id)
            )
            row = await cursor.fetchone()
            if not row:
                return
            current_data = json.loads(row[0] or "{}")
            current_data.update(updates)
            await db.execute(
                "UPDATE nodes SET data_json = ? WHERE session_id = ? AND id = ?",
                (json.dumps(current_data), session_id, node_id),
            )
            await db.commit()

    async def get_stats(
        self, session_id: Optional[str] = None, workspace_id: Optional[str] = None
    ) -> Dict[str, int]:
        async with self._get_conn() as db:
            if session_id:
                cursor = await db.execute(
                    "SELECT schema_type, COUNT(*) FROM nodes WHERE session_id = ? GROUP BY schema_type",
                    (session_id,),
                )
            elif workspace_id:
                cursor = await db.execute(
                    """SELECT n.schema_type, COUNT(*)
                       FROM nodes n
                       JOIN sessions s ON n.session_id = s.id
                       WHERE s.workspace_id = ?
                       GROUP BY n.schema_type""",
                    (workspace_id,),
                )
            else:
                cursor = await db.execute(
                    "SELECT schema_type, COUNT(*) FROM nodes GROUP BY schema_type"
                )

            rows = await cursor.fetchall()
            stats = {"total": 0}
            for schema_type, count in rows:
                stats[schema_type] = count
                stats["total"] += count
            return stats

    async def append_event(
        self, session_id: str, action: ActionRequest, result: Dict[str, Any], message: str
    ):
        """Append a structured action/result event to the log."""
        await self.timeline.append_event(session_id, action, result, message)

    async def log_audit_event(
        self, session_id: str, action_name: str, message: str, status: str
    ) -> None:
        """Append an audit lifecycle event (e.g. session closed/reopened) to event_log."""
        await self.timeline.log_audit_event(session_id, action_name, message, status)

    async def export_session(self, session_id: str, dest_db_path: str) -> None:
        """Export session metadata, nodes, edges, and event_log rows to a new SQLite database."""
        dest_store = GraphStore(dest_db_path)
        await dest_store.initialize()
        await dest_store.close()

        async with self._get_conn() as db:
            await db.execute("ATTACH DATABASE ? AS dest", (dest_db_path,))
            try:
                # 1. Copy workspace row
                await db.execute(
                    """
                    INSERT OR IGNORE INTO dest.workspaces (id, name, status, created_at)
                    SELECT w.id, w.name, w.status, w.created_at
                    FROM workspaces w
                    JOIN sessions s ON s.workspace_id = w.id
                    WHERE s.id = ?
                """,
                    (session_id,),
                )

                # 2. Copy session row
                await db.execute(
                    """
                    INSERT OR IGNORE INTO dest.sessions (id, workspace_id, name, status, created_at)
                    SELECT id, workspace_id, name, status, created_at
                    FROM sessions
                    WHERE id = ?
                """,
                    (session_id,),
                )

                # 3. Copy nodes
                await db.execute(
                    """
                    INSERT OR IGNORE INTO dest.nodes (session_id, id, schema_type, pik_json, data_json, status, updated_at)
                    SELECT session_id, id, schema_type, pik_json, data_json, status, updated_at
                    FROM nodes
                    WHERE session_id = ?
                """,
                    (session_id,),
                )

                # 4. Copy edges
                await db.execute(
                    """
                    INSERT OR IGNORE INTO dest.edges (session_id, source_id, target_id, relation_type)
                    SELECT session_id, source_id, target_id, relation_type
                    FROM edges
                    WHERE session_id = ?
                """,
                    (session_id,),
                )

                # 5. Copy event_log
                await db.execute(
                    """
                    INSERT OR IGNORE INTO dest.event_log (id, session_id, timestamp, action_payload, result_payload, human_readable, schema_type, finding_json, closed)
                    SELECT id, session_id, timestamp, action_payload, result_payload, human_readable, schema_type, finding_json, closed
                    FROM event_log
                    WHERE session_id = ?
                """,
                    (session_id,),
                )

                # 6. Copy notes
                await db.execute(
                    """
                    INSERT OR IGNORE INTO dest.notes (scope_type, scope_id, content, updated_at)
                    SELECT scope_type, scope_id, content, updated_at
                    FROM notes
                    WHERE (scope_type = 'session' AND scope_id = ?)
                       OR (scope_type = 'learning' AND scope_id = ?)
                """,
                    (session_id, session_id),
                )

                await db.commit()
                if os.path.exists(dest_db_path):
                    try:
                        os.chmod(dest_db_path, 0o600)
                    except OSError:
                        pass
            except Exception:
                await db.rollback()
                raise
            finally:
                try:
                    await db.execute("DETACH DATABASE dest")
                except Exception:
                    pass

    async def import_session(
        self, src_db_path: str, target_workspace_id: Optional[str] = None
    ) -> str:
        """Import a session from an exported SQLite database into this store.

        If the session already exists, it is overwritten (restored).
        Returns the imported session ID.
        """
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            await db.execute("ATTACH DATABASE ? AS src", (src_db_path,))
            try:
                cursor = await db.execute("SELECT * FROM src.sessions LIMIT 1")
                src_session = await cursor.fetchone()
                if not src_session:
                    raise ValueError("No session found in the source database.")

                src_session_id = src_session["id"]
                src_session_name = src_session["name"]
                src_session_status = src_session["status"]
                src_session_created = src_session["created_at"]

                cursor_ws = await db.execute(
                    "SELECT name FROM src.workspaces WHERE id = ?", (src_session["workspace_id"],)
                )
                ws_row = await cursor_ws.fetchone()
                src_workspace_name = ws_row["name"] if ws_row else "Imported Workspace"

                if target_workspace_id:
                    cursor_target_ws = await db.execute(
                        "SELECT id FROM workspaces WHERE id = ?", (target_workspace_id,)
                    )
                    t_ws = await cursor_target_ws.fetchone()
                    if not t_ws:
                        raise ValueError(f"Target workspace ID '{target_workspace_id}' not found.")
                    final_workspace_id = target_workspace_id
                else:
                    if src_workspace_name.lower() == "learning sandbox":
                        cursor_target_ws = await db.execute(
                            "SELECT id FROM workspaces WHERE LOWER(name) = 'learning sandbox' LIMIT 1"
                        )
                    else:
                        cursor_target_ws = await db.execute(
                            "SELECT id FROM workspaces WHERE LOWER(name) = ? AND status != 'SYSTEM' LIMIT 1",
                            (src_workspace_name.lower(),),
                        )
                    t_ws = await cursor_target_ws.fetchone()
                    if t_ws:
                        final_workspace_id = t_ws["id"]
                    else:
                        import uuid

                        final_workspace_id = str(uuid.uuid4())
                        await db.execute(
                            "INSERT INTO workspaces (id, name, status) VALUES (?, ?, 'ACTIVE')",
                            (final_workspace_id, src_workspace_name),
                        )

                # Check if the session already exists by ID in our database
                cursor_existing_sess = await db.execute(
                    "SELECT id, name, workspace_id FROM sessions WHERE id = ?", (src_session_id,)
                )
                existing_sess = await cursor_existing_sess.fetchone()

                if existing_sess:
                    # Clean up existing session data first to overwrite/restore it
                    await db.execute("DELETE FROM sessions WHERE id = ?", (src_session_id,))
                    # Explicit cleanup (cascades should handle this, but just to be sure)
                    await db.execute("DELETE FROM nodes WHERE session_id = ?", (src_session_id,))
                    await db.execute("DELETE FROM edges WHERE session_id = ?", (src_session_id,))
                    await db.execute(
                        "DELETE FROM event_log WHERE session_id = ?", (src_session_id,)
                    )

                # Handle name collision with a DIFFERENT session in the target workspace
                final_session_name = src_session_name
                collision_idx = 1
                while True:
                    cursor_sess = await db.execute(
                        "SELECT id FROM sessions WHERE workspace_id = ? AND LOWER(name) = ? AND id != ? LIMIT 1",
                        (final_workspace_id, final_session_name.lower(), src_session_id),
                    )
                    s_row = await cursor_sess.fetchone()
                    if not s_row:
                        break
                    final_session_name = f"{src_session_name} (Imported {collision_idx})"
                    collision_idx += 1

                await db.execute(
                    "INSERT INTO sessions (id, workspace_id, name, status, created_at) VALUES (?, ?, ?, ?, ?)",
                    (
                        src_session_id,
                        final_workspace_id,
                        final_session_name,
                        src_session_status,
                        src_session_created,
                    ),
                )

                cursor_nodes = await db.execute(
                    "SELECT * FROM src.nodes WHERE session_id = ?", (src_session_id,)
                )
                nodes = await cursor_nodes.fetchall()
                nodes_to_insert = []
                for n in nodes:
                    schema_type = n["schema_type"]
                    if (
                        not schema_type
                        or not re.match(r"^[a-zA-Z0-9_.]+$", schema_type)
                        or len(schema_type) > 64
                    ):
                        raise ValueError(f"Invalid schema_type '{schema_type}' in imported node.")
                    try:
                        pik_val = json.loads(n["pik_json"])
                        data_val = json.loads(n["data_json"])
                        if not isinstance(pik_val, dict) or not isinstance(data_val, dict):
                            raise ValueError
                    except Exception:
                        raise ValueError(
                            f"Corrupt JSON payload in imported node {n['id']}."
                        ) from None

                    nodes_to_insert.append(
                        (
                            src_session_id,
                            n["id"],
                            schema_type,
                            json.dumps(pik_val),
                            json.dumps(data_val),
                            n["status"],
                            n["updated_at"],
                        )
                    )

                if nodes_to_insert:
                    await db.executemany(
                        "INSERT INTO nodes (session_id, id, schema_type, pik_json, data_json, status, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        nodes_to_insert,
                    )

                cursor_edges = await db.execute(
                    "SELECT * FROM src.edges WHERE session_id = ?", (src_session_id,)
                )
                edges = await cursor_edges.fetchall()
                if edges:
                    edges_to_insert = [
                        (src_session_id, e["source_id"], e["target_id"], e["relation_type"])
                        for e in edges
                    ]
                    await db.executemany(
                        "INSERT INTO edges (session_id, source_id, target_id, relation_type) VALUES (?, ?, ?, ?)",
                        edges_to_insert,
                    )

                cursor_events = await db.execute(
                    "SELECT * FROM src.event_log WHERE session_id = ?", (src_session_id,)
                )
                events = await cursor_events.fetchall()
                if events:
                    events_to_insert = [
                        (
                            src_session_id,
                            ev["timestamp"],
                            ev["action_payload"],
                            ev["result_payload"],
                            ev["human_readable"],
                            ev["schema_type"],
                            ev["finding_json"],
                            ev["closed"],
                        )
                        for ev in events
                    ]
                    await db.executemany(
                        "INSERT INTO event_log (session_id, timestamp, action_payload, result_payload, human_readable, schema_type, finding_json, closed) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        events_to_insert,
                    )

                # Import notes if present in src
                try:
                    cursor_notes = await db.execute(
                        "SELECT * FROM src.notes WHERE scope_id = ?", (src_session_id,)
                    )
                    notes_rows = await cursor_notes.fetchall()
                    if notes_rows:
                        notes_to_insert = [
                            (n["scope_type"], src_session_id, n["content"]) for n in notes_rows
                        ]
                        await db.executemany(
                            "INSERT OR REPLACE INTO notes (scope_type, scope_id, content) VALUES (?, ?, ?)",
                            notes_to_insert,
                        )
                except Exception:
                    pass

                await db.commit()
                return src_session_id
            except Exception:
                await db.rollback()
                raise
            finally:
                try:
                    await db.execute("DETACH DATABASE src")
                except Exception:
                    pass
