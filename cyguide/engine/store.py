# PROTECTED FILE — See CONTRIBUTING.md before modifying.
# Changes to this file require team agreement.
"""SQLite-based graph store for workspaces and sessions."""

import json
import os
import re
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import aiosqlite

from cyguide.schemas.base import BaseFinding
from cyguide.schemas.power import ActionRequest


class GraphStore:
    """Manages workspaces, sessions, and stateful entity graphs."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._on_upsert_callbacks = []
        self._conn: Optional[aiosqlite.Connection] = None
        self._closed: bool = False

    def on_upsert(self, callback):
        """Register an async callback to fire when any finding is upserted."""
        self._on_upsert_callbacks.append(callback)

    @asynccontextmanager
    async def _get_conn(self):
        """Helper to get a connection, supporting persistent connection for all paths."""
        if self._closed:
            raise ValueError("Cannot operate on a closed database.")
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
            # 1. Workspaces
            await db.execute("""
                CREATE TABLE IF NOT EXISTS workspaces (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    status TEXT DEFAULT 'ACTIVE',
                    closed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 2. Sessions (Power Sessions)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    status TEXT DEFAULT 'ACTIVE',
                    closed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
                )
            """)

            # 3. Nodes (Per-session graph nodes)
            await db.execute("""
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
                )
            """)

            # 4. Edges (Per-session graph edges)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS edges (
                    session_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    PRIMARY KEY (session_id, source_id, target_id, relation_type),
                    FOREIGN KEY (session_id, source_id) REFERENCES nodes(session_id, id) ON DELETE CASCADE,
                    FOREIGN KEY (session_id, target_id) REFERENCES nodes(session_id, id) ON DELETE CASCADE
                )
            """)

            # 5. Event Log (Audit trail per session)
            await db.execute("""
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
                )
            """)

            # 6. High-Performance Graph & Event Log Indexes
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_nodes_session_schema ON nodes(session_id, schema_type)"
            )
            await db.execute("CREATE INDEX IF NOT EXISTS idx_edges_session ON edges(session_id)")
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(session_id, source_id)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(session_id, target_id)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_event_log_session_time ON event_log(session_id, timestamp DESC)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_ws_status ON sessions(workspace_id, status)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_workspaces_status ON workspaces(status)"
            )

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
            await db.execute("DELETE FROM workspaces WHERE id = ?", (workspace_id,))
            await db.commit()

    async def delete_session(self, session_id: str):
        """Delete a single session and its graph data."""
        async with self._get_conn() as db:
            await db.execute("PRAGMA foreign_keys = ON")
            await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
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
        import hashlib

        pik_str = json.dumps(pik, sort_keys=True)
        return hashlib.sha256(f"{schema_type}:{pik_str}".encode()).hexdigest()

    def _generate_node_id(self, schema_type: str, pik: Dict[str, Any]) -> str:
        return self.generate_node_id(schema_type, pik)

    async def upsert_findings_batch(
        self, session_id: str, findings: List[BaseFinding]
    ) -> List[str]:
        """Atomically upsert a batch of findings in a single SQLite transaction."""
        if not findings:
            return []

        node_ids: List[str] = []
        async with self._get_conn() as db:
            for finding in findings:
                node_id = self._generate_node_id(finding.schema_type, finding.pik)
                node_ids.append(node_id)

                # 1. Log the event
                await db.execute(
                    """INSERT INTO event_log (session_id, schema_type, finding_json, human_readable, action_payload, result_payload)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        session_id,
                        finding.schema_type,
                        finding.model_dump_json(),
                        f"Discovered {finding.schema_type}",
                        "{}",
                        "{}",
                    ),
                )

                # 2. Upsert the node
                cursor = await db.execute(
                    "SELECT data_json FROM nodes WHERE session_id = ? AND id = ?",
                    (session_id, node_id),
                )
                row = await cursor.fetchone()

                if row:
                    existing_data = json.loads(row[0])
                    existing_data.update(finding.data)
                    await db.execute(
                        "UPDATE nodes SET data_json = ?, status = ?, updated_at = CURRENT_TIMESTAMP WHERE session_id = ? AND id = ?",
                        (json.dumps(existing_data), finding.status, session_id, node_id),
                    )
                else:
                    await db.execute(
                        "INSERT INTO nodes (session_id, id, schema_type, pik_json, data_json, status) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            session_id,
                            node_id,
                            finding.schema_type,
                            json.dumps(finding.pik),
                            json.dumps(finding.data),
                            finding.status,
                        ),
                    )

                # 3. Handle Parent Relation (Auto-wiring)
                if finding.parent:
                    p = finding.parent
                    parent_id = self._generate_node_id(p.target_type, p.target_pik)
                    await db.execute(
                        "INSERT OR IGNORE INTO nodes (session_id, id, schema_type, pik_json, data_json) VALUES (?, ?, ?, ?, ?)",
                        (session_id, parent_id, p.target_type, json.dumps(p.target_pik), "{}"),
                    )
                    await db.execute(
                        "INSERT OR IGNORE INTO edges (session_id, source_id, target_id, relation_type) VALUES (?, ?, ?, ?)",
                        (session_id, parent_id, node_id, p.via),
                    )

                # 4. Handle Associations
                for assoc in finding.associations:
                    assoc_id = self._generate_node_id(assoc.target_type, assoc.target_pik)
                    await db.execute(
                        "INSERT OR IGNORE INTO nodes (session_id, id, schema_type, pik_json, data_json) VALUES (?, ?, ?, ?, ?)",
                        (
                            session_id,
                            assoc_id,
                            assoc.target_type,
                            json.dumps(assoc.target_pik),
                            "{}",
                        ),
                    )
                    await db.execute(
                        "INSERT OR IGNORE INTO edges (session_id, source_id, target_id, relation_type) VALUES (?, ?, ?, ?)",
                        (session_id, node_id, assoc_id, assoc.via),
                    )

            await db.commit()

        # Trigger reactive callbacks
        import logging

        for finding in findings:
            for cb in self._on_upsert_callbacks:
                try:
                    await cb(session_id, finding)
                except Exception as e:
                    logging.getLogger(__name__).error(
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
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM event_log WHERE session_id = ? AND (closed IS NULL OR closed = 0) ORDER BY timestamp ASC",
                (session_id,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def mark_event_closed(self, action_id: str, session_id: Optional[str] = None) -> None:
        """Mark an event log entry as closed/deleted."""
        async with self._get_conn() as db:
            if session_id:
                await db.execute(
                    "UPDATE event_log SET closed = 1 WHERE session_id = ? AND action_payload LIKE ?",
                    (session_id, f'%"{action_id}"%'),
                )
            else:
                await db.execute(
                    "UPDATE event_log SET closed = 1 WHERE action_payload LIKE ?",
                    (f'%"{action_id}"%',),
                )
            await db.commit()

    async def get_closed_events_count(self, session_id: str) -> int:
        """Get the count of closed events/tabs for a session."""
        async with self._get_conn() as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM event_log WHERE session_id = ? AND closed = 1", (session_id,)
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

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
        async with self._get_conn() as db:
            await db.execute(
                """INSERT INTO event_log (session_id, action_payload, result_payload, human_readable, schema_type, finding_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    action.model_dump_json(),
                    json.dumps(result),
                    message,
                    "system.event",
                    "{}",
                ),
            )
            await db.commit()

    async def log_audit_event(
        self, session_id: str, action_name: str, message: str, status: str
    ) -> None:
        """Append an audit lifecycle event (e.g. session closed/reopened) to event_log."""
        async with self._get_conn() as db:
            await db.execute(
                """INSERT INTO event_log (session_id, action_payload, result_payload, human_readable, schema_type, finding_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    json.dumps({"action": action_name}),
                    json.dumps({"status": status}),
                    message,
                    f"system.{action_name}",
                    "{}",
                ),
            )
            await db.commit()

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
                await db.execute("DETACH DATABASE dest")

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

                    await db.execute(
                        "INSERT INTO nodes (session_id, id, schema_type, pik_json, data_json, status, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            src_session_id,
                            n["id"],
                            schema_type,
                            json.dumps(pik_val),
                            json.dumps(data_val),
                            n["status"],
                            n["updated_at"],
                        ),
                    )

                cursor_edges = await db.execute(
                    "SELECT * FROM src.edges WHERE session_id = ?", (src_session_id,)
                )
                edges = await cursor_edges.fetchall()
                for e in edges:
                    await db.execute(
                        "INSERT INTO edges (session_id, source_id, target_id, relation_type) VALUES (?, ?, ?, ?)",
                        (src_session_id, e["source_id"], e["target_id"], e["relation_type"]),
                    )

                cursor_events = await db.execute(
                    "SELECT * FROM src.event_log WHERE session_id = ?", (src_session_id,)
                )
                events = await cursor_events.fetchall()
                for ev in events:
                    await db.execute(
                        "INSERT INTO event_log (session_id, timestamp, action_payload, result_payload, human_readable, schema_type, finding_json, closed) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            src_session_id,
                            ev["timestamp"],
                            ev["action_payload"],
                            ev["result_payload"],
                            ev["human_readable"],
                            ev["schema_type"],
                            ev["finding_json"],
                            ev["closed"],
                        ),
                    )

                await db.commit()
                return src_session_id
            except Exception:
                await db.rollback()
                raise
            finally:
                await db.execute("DETACH DATABASE src")
