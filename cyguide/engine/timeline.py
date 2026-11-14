"""Deep module managing session action timeline, execution audit trails, and event lifecycle."""

import json
from typing import Any, Dict, List, Optional

import aiosqlite

from cyguide.schemas.power import ActionRequest


class ActionTimelineRepository:
    """The deep module managing persistent event logging, audit trails,

    and active/closed tab status for investigation sessions.
    """

    def __init__(self, store: Any):
        self.store = store

    async def append_event(
        self,
        session_id: str,
        action: ActionRequest,
        result: Dict[str, Any],
        message: str,
    ) -> None:
        """Append a structured action/result event to the session event log."""
        async with self.store._get_conn() as db:
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
        async with self.store._get_conn() as db:
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

    async def get_event_log(self, session_id: str) -> List[Dict[str, Any]]:
        """Fetch all non-closed events for a session in chronological order."""
        async with self.store._get_conn() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM event_log WHERE session_id = ? AND (closed IS NULL OR closed = 0) ORDER BY timestamp ASC, id ASC",
                (session_id,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def mark_event_closed(self, action_id: str, session_id: Optional[str] = None) -> None:
        """Mark an event log entry as closed/deleted from the active view."""
        async with self.store._get_conn() as db:
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
        async with self.store._get_conn() as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM event_log WHERE session_id = ? AND closed = 1",
                (session_id,),
            )
            row = await cursor.fetchone()
            return row[0] if row else 0
