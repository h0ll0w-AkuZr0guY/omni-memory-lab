import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Self
from uuid import uuid4

from omni_memory.schemas.asset import AssetRecord
from omni_memory.schemas.memory import CommittedFact, MemoryAuditEvent


class SQLiteMemoryStore:
    """本地领域记忆 Store：保存当前记忆投影和 append-only 审计事件。"""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.database_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS committed_memories (
                memory_id TEXT PRIMARY KEY,
                source_episode_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id TEXT PRIMARY KEY,
                memory_id TEXT NOT NULL,
                action TEXT NOT NULL,
                occurred_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS assets (
                asset_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def put_many(self, memories: list[CommittedFact]) -> None:
        audit_events: list[MemoryAuditEvent] = []
        for memory in memories:
            exists = self.connection.execute(
                "SELECT 1 FROM committed_memories WHERE memory_id = ?",
                (memory.memory_id,),
            ).fetchone()
            action = "replaced" if exists else "created"
            self.connection.execute(
                """
                INSERT OR REPLACE INTO committed_memories
                    (memory_id, source_episode_id, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    memory.memory_id,
                    memory.source_episode_id,
                    json.dumps(memory.model_dump(mode="json"), ensure_ascii=False),
                    memory.ingested_at.isoformat(),
                ),
            )
            audit_events.append(
                MemoryAuditEvent(
                    event_id=str(uuid4()),
                    memory_id=memory.memory_id,
                    action=action,
                    occurred_at=memory.ingested_at,
                )
            )

        self.connection.executemany(
            """
            INSERT INTO audit_events (event_id, memory_id, action, occurred_at)
            VALUES (?, ?, ?, ?)
            """,
            [
                (event.event_id, event.memory_id, event.action, event.occurred_at.isoformat())
                for event in audit_events
            ],
        )
        self.connection.commit()

    def get(self, memory_id: str) -> CommittedFact | None:
        row = self.connection.execute(
            "SELECT payload_json FROM committed_memories WHERE memory_id = ?",
            (memory_id,),
        ).fetchone()
        if row is None:
            return None
        return CommittedFact.model_validate(json.loads(row["payload_json"]))

    def list_all(self) -> list[CommittedFact]:
        rows = self.connection.execute(
            "SELECT payload_json FROM committed_memories ORDER BY created_at, memory_id"
        ).fetchall()
        return [
            CommittedFact.model_validate(json.loads(row["payload_json"]))
            for row in rows
        ]

    def list_by_episode(self, source_episode_id: str) -> list[CommittedFact]:
        rows = self.connection.execute(
            """
            SELECT payload_json FROM committed_memories
            WHERE source_episode_id = ?
            ORDER BY created_at, memory_id
            """,
            (source_episode_id,),
        ).fetchall()
        return [
            CommittedFact.model_validate(json.loads(row["payload_json"]))
            for row in rows
        ]

    def list_audit_events(self, memory_id: str | None = None) -> list[MemoryAuditEvent]:
        if memory_id is None:
            rows = self.connection.execute(
                "SELECT * FROM audit_events ORDER BY rowid"
            ).fetchall()
        else:
            rows = self.connection.execute(
                """
                SELECT * FROM audit_events
                WHERE memory_id = ?
                ORDER BY rowid
                """,
                (memory_id,),
            ).fetchall()
        return [MemoryAuditEvent.model_validate(dict(row)) for row in rows]

    def count(self) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) AS total FROM committed_memories"
        ).fetchone()
        return int(row["total"])

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def put_assets(self, assets: list[AssetRecord]) -> None:
        now = datetime.now(UTC).isoformat()
        self.connection.executemany(
            """
            INSERT OR REPLACE INTO assets (asset_id, payload_json, created_at)
            VALUES (?, ?, ?)
            """,
            [
                (
                    asset.asset_id,
                    json.dumps(asset.model_dump(mode="json"), ensure_ascii=False),
                    now,
                )
                for asset in assets
            ],
        )
        self.connection.commit()

    def list_assets(self) -> list[AssetRecord]:
        rows = self.connection.execute(
            "SELECT payload_json FROM assets ORDER BY created_at, asset_id"
        ).fetchall()
        return [
            AssetRecord.model_validate(json.loads(row["payload_json"]))
            for row in rows
        ]

