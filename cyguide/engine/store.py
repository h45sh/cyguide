# PROTECTED FILE — See CONTRIBUTING.md before modifying.
# Changes to this file require team agreement.
"""SQLite-based graph store for workspaces and sessions."""

import json
import uuid
import aiosqlite
from datetime import datetime, UTC
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
from cyguide.schemas.base import BaseFinding, Relation
from cyguide.schemas.power import ActionRequest


class GraphStore:
    """Manages workspaces, sessions, and stateful entity graphs."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._on_upsert_callbacks = []
        self._conn: Optional[aiosqlite.Connection] = None

    def on_upsert(self, callback):
        """Register an async callback to fire when any finding is upserted."""
        self._on_upsert_callbacks.append(callback)

    @asynccontextmanager
    async def _get_conn(self):
        """Helper to get a connection, supporting persistent connection for all paths."""
        if self._conn is None:
            self._conn = await aiosqlite.connect(self.db_path)
            await self._conn.execute("PRAGMA foreign_keys = ON")
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
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
            """)
            
            # 6. Schema Migrations (for backward compatibility with older cyguide.db)
            try:
                await db.execute("ALTER TABLE event_log ADD COLUMN action_payload TEXT")
                await db.execute("ALTER TABLE event_log ADD COLUMN result_payload TEXT")
                await db.execute("ALTER TABLE event_log ADD COLUMN human_readable TEXT")
            except Exception:
                pass # Columns already exist

            try:
                await db.execute("ALTER TABLE nodes ADD COLUMN status TEXT DEFAULT 'confirmed'")
            except Exception:
                pass # Column already exists
                
            await db.commit()

    async def close(self):
        """Close the persistent connection if it exists."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def get_or_create_learning_sandbox(self) -> tuple[str, str]:
        """Ensure the singleton Learning Sandbox and its session exist and return their IDs."""
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            # 1. Check for existing Learning Sandbox
            cursor = await db.execute("SELECT id FROM workspaces WHERE name = 'Learning Sandbox' LIMIT 1")
            row = await cursor.fetchone()
            if row:
                ws_id = row["id"]
            else:
                ws_id = str(uuid.uuid4())
                await db.execute("INSERT INTO workspaces (id, name, status) VALUES (?, ?, ?)", (ws_id, "Learning Sandbox", "SYSTEM"))
            
            # 2. Check for existing Guided Session
            cursor = await db.execute("SELECT id FROM sessions WHERE workspace_id = ? AND name = 'Guided Session' LIMIT 1", (ws_id,))
            row = await cursor.fetchone()
            if row:
                sess_id = row["id"]
            else:
                sess_id = str(uuid.uuid4())
                await db.execute("INSERT INTO sessions (id, workspace_id, name, status) VALUES (?, ?, ?, ?)", (sess_id, ws_id, "Guided Session", "SYSTEM"))
            
            await db.commit()
            return ws_id, sess_id

    # --- Workspace Management ---

    async def create_workspace(self, name: str) -> str:
        workspace_id = str(uuid.uuid4())
        async with self._get_conn() as db:
            await db.execute("INSERT INTO workspaces (id, name) VALUES (?, ?)", (workspace_id, name))
            await db.commit()
        return workspace_id

    async def list_workspaces(self) -> List[Dict]:
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
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

    # --- Session Management ---

    async def create_session(self, workspace_id: str, name: str) -> str:
        session_id = str(uuid.uuid4())
        async with self._get_conn() as db:
            await db.execute(
                "INSERT INTO sessions (id, workspace_id, name) VALUES (?, ?, ?)",
                (session_id, workspace_id, name)
            )
            await db.commit()
        return session_id

    async def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session metadata."""
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def list_sessions(self, workspace_id: str) -> List[Dict]:
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM sessions WHERE workspace_id = ? ORDER BY created_at DESC", 
                (workspace_id,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

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
                (target_workspace_id, session_id)
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
                WHERE s.workspace_id = ? 
                ORDER BY e.timestamp DESC LIMIT ?
            """
            cursor = await db.execute(query, (workspace_id, limit))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # --- Graph Data Persistence (Session Aware) ---

    def _generate_node_id(self, schema_type: str, pik: Dict[str, Any]) -> str:
        import hashlib
        pik_str = json.dumps(pik, sort_keys=True)
        return hashlib.sha256(f"{schema_type}:{pik_str}".encode()).hexdigest()

    async def upsert_finding(self, session_id: str, finding: BaseFinding):
        node_id = self._generate_node_id(finding.schema_type, finding.pik)
        
        async with self._get_conn() as db:
            # 1. Log the event
            await db.execute(
                """INSERT INTO event_log (session_id, schema_type, finding_json, human_readable, action_payload, result_payload) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, finding.schema_type, finding.model_dump_json(), f"Discovered {finding.schema_type}", "{}", "{}")
            )

            # 2. Upsert the node
            cursor = await db.execute(
                "SELECT data_json FROM nodes WHERE session_id = ? AND id = ?", 
                (session_id, node_id)
            )
            row = await cursor.fetchone()
            
            if row:
                existing_data = json.loads(row[0])
                existing_data.update(finding.data)
                await db.execute(
                    "UPDATE nodes SET data_json = ?, status = ?, updated_at = CURRENT_TIMESTAMP WHERE session_id = ? AND id = ?",
                    (json.dumps(existing_data), finding.status, session_id, node_id)
                )
            else:
                await db.execute(
                    "INSERT INTO nodes (session_id, id, schema_type, pik_json, data_json, status) VALUES (?, ?, ?, ?, ?, ?)",
                    (session_id, node_id, finding.schema_type, json.dumps(finding.pik), json.dumps(finding.data), finding.status)
                )

            # 3. Handle Parent Relation (Auto-wiring)
            if finding.parent:
                p = finding.parent
                parent_id = self._generate_node_id(p.target_type, p.target_pik)
                await db.execute(
                    "INSERT OR IGNORE INTO nodes (session_id, id, schema_type, pik_json, data_json) VALUES (?, ?, ?, ?, ?)",
                    (session_id, parent_id, p.target_type, json.dumps(p.target_pik), "{}")
                )
                await db.execute(
                    "INSERT OR IGNORE INTO edges (session_id, source_id, target_id, relation_type) VALUES (?, ?, ?, ?)",
                    (session_id, parent_id, node_id, p.via)
                )

            # 4. Handle Associations
            for assoc in finding.associations:
                assoc_id = self._generate_node_id(assoc.target_type, assoc.target_pik)
                await db.execute(
                    "INSERT OR IGNORE INTO nodes (session_id, id, schema_type, pik_json, data_json) VALUES (?, ?, ?, ?, ?)",
                    (session_id, assoc_id, assoc.target_type, json.dumps(assoc.target_pik), "{}")
                )
                await db.execute(
                    "INSERT OR IGNORE INTO edges (session_id, source_id, target_id, relation_type) VALUES (?, ?, ?, ?)",
                    (session_id, node_id, assoc_id, assoc.via)
                )

            await db.commit()

        # Trigger reactive callbacks
        for cb in self._on_upsert_callbacks:
            try:
                await cb(session_id, finding)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Error in reactive callback {cb.__name__}: {e}")

        return node_id

    async def query(self, schema_type: str, session_id: Optional[str] = None) -> List[Dict]:
        """Fetch all nodes of a specific schema type."""
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            if session_id:
                cursor = await db.execute(
                    "SELECT * FROM nodes WHERE session_id = ? AND schema_type = ?",
                    (session_id, schema_type)
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM nodes WHERE schema_type = ?",
                    (schema_type,)
                )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_event_log(self, session_id: str) -> List[Dict]:
        """Fetch all events for a session."""
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM event_log WHERE session_id = ? ORDER BY timestamp ASC",
                (session_id,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_all_nodes(self, session_id: str) -> List[Dict]:
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM nodes WHERE session_id = ? ORDER BY updated_at DESC", 
                (session_id,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_node(self, session_id: str, node_id: str) -> Optional[Dict]:
        """Fetch a specific node by ID."""
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM nodes WHERE session_id = ? AND id = ?",
                (session_id, node_id)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_stats(self, session_id: Optional[str] = None) -> Dict[str, int]:
        async with self._get_conn() as db:
            if session_id:
                cursor = await db.execute(
                    "SELECT schema_type, COUNT(*) FROM nodes WHERE session_id = ? GROUP BY schema_type",
                    (session_id,)
                )
            else:
                cursor = await db.execute("SELECT schema_type, COUNT(*) FROM nodes GROUP BY schema_type")
            
            rows = await cursor.fetchall()
            stats = {"total": 0}
            for schema_type, count in rows:
                stats[schema_type] = count
                stats["total"] += count
            return stats

    async def append_event(self, session_id: str, action: ActionRequest, result: Dict[str, Any], message: str):
        """Append a structured action/result event to the log."""
        async with self._get_conn() as db:
            await db.execute(
                """INSERT INTO event_log (session_id, action_payload, result_payload, human_readable, schema_type, finding_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, action.model_dump_json(), json.dumps(result), message, "system.event", "{}")
            )
            await db.commit()
