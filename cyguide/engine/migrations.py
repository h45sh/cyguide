# codeguard: disable-file[UNTRACKED_SCHEMA_MUTATION]
"""Database schema migrations and compatibility helpers for CyGuide.

Provides versioned, forward-only migrations for standalone checkpoint databases
and workspace graph stores.
"""

from __future__ import annotations

import aiosqlite


async def migrate_checkpoint_schema(db: aiosqlite.Connection) -> None:
    """Ensure learning checkpoint SQLite database schema is up-to-date with forward-only migrations."""
    cursor = await db.execute("PRAGMA user_version")
    row = await cursor.fetchone()
    current_version = row[0] if row else 0

    # Ensure base learning_state table exists
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS learning_state (
            session_id TEXT PRIMARY KEY,
            primary_target TEXT,
            active_tool TEXT,
            tools_used TEXT,
            tool_configs TEXT,
            stdout_log TEXT,
            explanation_buffer TEXT,
            notes TEXT,
            model_name TEXT,
            saved_at TEXT
        )
        """
    )

    # Forward migration: Version 1 -> Version 2 (multi-tool metadata attributes)
    if current_version < 2:
        cursor = await db.execute("PRAGMA table_info(learning_state)")
        existing_cols = {r[1] for r in await cursor.fetchall()}
        alter_statements = {
            "primary_target": "ALTER TABLE learning_state ADD COLUMN primary_target TEXT",
            "active_tool": "ALTER TABLE learning_state ADD COLUMN active_tool TEXT",
            "tools_used": "ALTER TABLE learning_state ADD COLUMN tools_used TEXT",
            "tool_configs": "ALTER TABLE learning_state ADD COLUMN tool_configs TEXT",
        }
        for col_name, stmt in alter_statements.items():
            if col_name not in existing_cols:
                await db.execute(stmt)
        await db.execute("PRAGMA user_version = 2")
