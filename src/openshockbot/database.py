from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .models import AccessDecision, AccessMode, ControlRequest, Target


class Database:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._connection: sqlite3.Connection | None = None

    async def connect(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self._path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS targets (
                discord_user_id TEXT PRIMARY KEY,
                shocker_id TEXT NOT NULL,
                display_name TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                paused INTEGER NOT NULL DEFAULT 0,
                reaction_enabled INTEGER NOT NULL DEFAULT 1,
                access_mode TEXT NOT NULL DEFAULT 'everyone',
                max_intensity INTEGER NOT NULL DEFAULT 25,
                max_duration_ms INTEGER NOT NULL DEFAULT 3000,
                default_intensity INTEGER NOT NULL DEFAULT 10,
                default_duration_ms INTEGER NOT NULL DEFAULT 1000,
                cooldown_seconds REAL NOT NULL DEFAULT 5
            );

            CREATE TABLE IF NOT EXISTS access_rules (
                target_discord_user_id TEXT NOT NULL,
                actor_discord_user_id TEXT NOT NULL,
                decision TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (target_discord_user_id, actor_discord_user_id),
                FOREIGN KEY (target_discord_user_id)
                    REFERENCES targets(discord_user_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                occurred_at TEXT NOT NULL,
                actor_discord_user_id TEXT NOT NULL,
                target_discord_user_id TEXT NOT NULL,
                guild_id TEXT,
                message_id TEXT,
                source TEXT NOT NULL,
                action TEXT NOT NULL,
                requested_intensity INTEGER NOT NULL,
                requested_duration_ms INTEGER NOT NULL,
                effective_intensity INTEGER,
                effective_duration_ms INTEGER,
                outcome TEXT NOT NULL,
                detail TEXT
            );
            """
        )
        self._connection.commit()

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError("Database is not connected")
        return self._connection

    async def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    async def upsert_target(
        self,
        discord_user_id: int,
        shocker_id: str,
        *,
        display_name: str | None = None,
        max_intensity: int = 25,
        max_duration_ms: int = 3000,
        default_intensity: int = 10,
        default_duration_ms: int = 1000,
        cooldown_seconds: float = 5,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO targets (
                discord_user_id, shocker_id, display_name, max_intensity,
                max_duration_ms, default_intensity, default_duration_ms, cooldown_seconds
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(discord_user_id) DO UPDATE SET
                shocker_id = excluded.shocker_id,
                display_name = COALESCE(excluded.display_name, targets.display_name)
            """,
            (
                str(discord_user_id),
                shocker_id,
                display_name,
                max_intensity,
                max_duration_ms,
                default_intensity,
                default_duration_ms,
                cooldown_seconds,
            ),
        )
        self.connection.commit()

    async def get_target(self, discord_user_id: int) -> Target | None:
        cursor = self.connection.execute(
            "SELECT * FROM targets WHERE discord_user_id = ?",
            (str(discord_user_id),),
        )
        row = cursor.fetchone()
        cursor.close()
        if row is None:
            return None
        return Target(
            discord_user_id=int(row["discord_user_id"]),
            shocker_id=str(row["shocker_id"]),
            display_name=row["display_name"],
            enabled=bool(row["enabled"]),
            paused=bool(row["paused"]),
            reaction_enabled=bool(row["reaction_enabled"]),
            access_mode=AccessMode(row["access_mode"]),
            max_intensity=int(row["max_intensity"]),
            max_duration_ms=int(row["max_duration_ms"]),
            default_intensity=int(row["default_intensity"]),
            default_duration_ms=int(row["default_duration_ms"]),
            cooldown_seconds=float(row["cooldown_seconds"]),
        )

    async def set_paused(self, discord_user_id: int, paused: bool) -> bool:
        cursor = self.connection.execute(
            "UPDATE targets SET paused = ? WHERE discord_user_id = ?",
            (int(paused), str(discord_user_id)),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    async def set_access_mode(self, discord_user_id: int, mode: AccessMode) -> bool:
        cursor = self.connection.execute(
            "UPDATE targets SET access_mode = ? WHERE discord_user_id = ?",
            (mode.value, str(discord_user_id)),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    async def configure_target(
        self,
        discord_user_id: int,
        *,
        max_intensity: int,
        max_duration_ms: int,
        default_intensity: int,
        default_duration_ms: int,
        cooldown_seconds: float,
        reaction_enabled: bool,
    ) -> bool:
        cursor = self.connection.execute(
            """
            UPDATE targets SET
                max_intensity = ?,
                max_duration_ms = ?,
                default_intensity = ?,
                default_duration_ms = ?,
                cooldown_seconds = ?,
                reaction_enabled = ?
            WHERE discord_user_id = ?
            """,
            (
                max_intensity,
                max_duration_ms,
                default_intensity,
                default_duration_ms,
                cooldown_seconds,
                int(reaction_enabled),
                str(discord_user_id),
            ),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    async def set_access_rule(
        self,
        target_id: int,
        actor_id: int,
        decision: AccessDecision,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO access_rules (
                target_discord_user_id, actor_discord_user_id, decision, created_at
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(target_discord_user_id, actor_discord_user_id)
            DO UPDATE SET decision = excluded.decision, created_at = excluded.created_at
            """,
            (
                str(target_id),
                str(actor_id),
                decision.value,
                datetime.now(UTC).isoformat(),
            ),
        )
        self.connection.commit()

    async def remove_access_rule(self, target_id: int, actor_id: int) -> None:
        self.connection.execute(
            """
            DELETE FROM access_rules
            WHERE target_discord_user_id = ? AND actor_discord_user_id = ?
            """,
            (str(target_id), str(actor_id)),
        )
        self.connection.commit()

    async def get_access_decision(self, target_id: int, actor_id: int) -> AccessDecision | None:
        cursor = self.connection.execute(
            """
            SELECT decision FROM access_rules
            WHERE target_discord_user_id = ? AND actor_discord_user_id = ?
            """,
            (str(target_id), str(actor_id)),
        )
        row = cursor.fetchone()
        cursor.close()
        return AccessDecision(row["decision"]) if row else None

    async def log_control(
        self,
        request: ControlRequest,
        *,
        outcome: str,
        detail: str | None = None,
        effective_intensity: int | None = None,
        effective_duration_ms: int | None = None,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO audit_log (
                occurred_at, actor_discord_user_id, target_discord_user_id,
                guild_id, message_id, source, action, requested_intensity,
                requested_duration_ms, effective_intensity, effective_duration_ms,
                outcome, detail
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(UTC).isoformat(),
                str(request.actor_id),
                str(request.target_id),
                str(request.guild_id) if request.guild_id is not None else None,
                str(request.message_id) if request.message_id is not None else None,
                request.source.value,
                request.action.value,
                request.intensity,
                request.duration_ms,
                effective_intensity,
                effective_duration_ms,
                outcome,
                detail,
            ),
        )
        self.connection.commit()

    async def recent_audit(self, target_id: int, *, limit: int = 10) -> list[sqlite3.Row]:
        cursor = self.connection.execute(
            """
            SELECT occurred_at, actor_discord_user_id, source, action,
                   effective_intensity, effective_duration_ms, outcome
            FROM audit_log
            WHERE target_discord_user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (str(target_id), min(max(limit, 1), 25)),
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows
