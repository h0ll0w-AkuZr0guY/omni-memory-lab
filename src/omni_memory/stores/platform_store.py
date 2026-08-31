import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

from omni_memory.schemas.platform import (
    AssetRecord,
    AuditEvent,
    MemoryInput,
    MemoryRecord,
    ModelCallRecord,
    RunRecord,
)


class PlatformStore:
    """通用长期记忆的本地持久化实现。

    当前使用 SQLite 作为本地单节点实现；公共 service 不依赖 SQL 细节，
    后续可将本类替换为 Postgres/对象存储适配器。
    """

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(
            self.database_path,
            timeout=30,
            check_same_thread=False,
        )
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS platform_memories (
                memory_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                tenant_id TEXT NOT NULL,
                namespace TEXT NOT NULL,
                lifecycle TEXT NOT NULL,
                idempotency_key TEXT,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (memory_id, version)
            );
            CREATE INDEX IF NOT EXISTS idx_platform_memory_scope
                ON platform_memories (tenant_id, namespace, lifecycle);
            CREATE INDEX IF NOT EXISTS idx_platform_memory_idempotency
                ON platform_memories (tenant_id, namespace, idempotency_key);
            CREATE TABLE IF NOT EXISTS platform_current_memory (
                memory_id TEXT PRIMARY KEY,
                version INTEGER NOT NULL,
                tenant_id TEXT NOT NULL,
                namespace TEXT NOT NULL,
                idempotency_key TEXT,
                FOREIGN KEY (memory_id, version)
                    REFERENCES platform_memories(memory_id, version)
            );
            CREATE TABLE IF NOT EXISTS platform_assets (
                asset_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                namespace TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (tenant_id, namespace, sha256)
            );
            CREATE TABLE IF NOT EXISTS platform_audit_events (
                event_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                namespace TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                action TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS platform_runs (
                run_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                namespace TEXT NOT NULL,
                operation TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT
            );
            CREATE TABLE IF NOT EXISTS platform_model_calls (
                call_id TEXT PRIMARY KEY,
                run_id TEXT,
                operation TEXT NOT NULL,
                model TEXT NOT NULL,
                provider_host TEXT NOT NULL,
                success INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    @staticmethod
    def stable_memory_id(input_data: MemoryInput) -> str:
        raw = "|".join(
            [
                input_data.tenant_id,
                input_data.namespace,
                input_data.idempotency_key or "",
                input_data.source_ref,
                input_data.content or "",
                ",".join(input_data.asset_refs),
            ]
        )
        return f"mem_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]}"

    def find_idempotent(self, tenant_id: str, namespace: str, key: str) -> MemoryRecord | None:
        row = self.connection.execute(
            """
            SELECT m.payload_json FROM platform_memories m
            JOIN platform_current_memory c
              ON c.memory_id = m.memory_id AND c.version = m.version
            WHERE c.tenant_id = ? AND c.namespace = ? AND c.idempotency_key = ?
            """,
            (tenant_id, namespace, key),
        ).fetchone()
        return self._record(row["payload_json"]) if row else None

    def get_current(self, memory_id: str) -> MemoryRecord | None:
        row = self.connection.execute(
            """
            SELECT m.payload_json FROM platform_memories m
            JOIN platform_current_memory c
              ON c.memory_id = m.memory_id AND c.version = m.version
            WHERE c.memory_id = ?
            """,
            (memory_id,),
        ).fetchone()
        return self._record(row["payload_json"]) if row else None

    def list_current(
        self,
        tenant_id: str,
        namespace: str,
        include_deleted: bool = False,
    ) -> list[MemoryRecord]:
        sql = """
            SELECT m.payload_json FROM platform_memories m
            JOIN platform_current_memory c
              ON c.memory_id = m.memory_id AND c.version = m.version
            WHERE c.tenant_id = ? AND c.namespace = ?
        """
        params: list[Any] = [tenant_id, namespace]
        if not include_deleted:
            sql += " AND json_extract(m.payload_json, '$.lifecycle') != 'deleted'"
        sql += " ORDER BY m.updated_at, m.memory_id"
        rows = self.connection.execute(sql, params).fetchall()
        return [self._record(row["payload_json"]) for row in rows]

    def save_memory(self, record: MemoryRecord, idempotency_key: str | None) -> None:
        payload = json.dumps(record.model_dump(mode="json"), ensure_ascii=False)
        self.connection.execute(
            """
            INSERT INTO platform_memories
                (memory_id, version, tenant_id, namespace, lifecycle,
                 idempotency_key, payload_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.memory_id,
                record.version,
                record.tenant_id,
                record.namespace,
                record.lifecycle,
                idempotency_key,
                payload,
                record.created_at.isoformat(),
                record.updated_at.isoformat(),
            ),
        )
        self.connection.execute(
            """
            INSERT OR REPLACE INTO platform_current_memory
                (memory_id, version, tenant_id, namespace, idempotency_key)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                record.memory_id,
                record.version,
                record.tenant_id,
                record.namespace,
                idempotency_key,
            ),
        )
        self.connection.commit()

    def list_versions(self, memory_id: str) -> list[MemoryRecord]:
        rows = self.connection.execute(
            "SELECT payload_json FROM platform_memories WHERE memory_id = ? ORDER BY version",
            (memory_id,),
        ).fetchall()
        return [self._record(row["payload_json"]) for row in rows]

    def save_asset(self, asset: AssetRecord) -> AssetRecord:
        now = datetime.now(UTC)
        existing = self.connection.execute(
            "SELECT payload_json FROM platform_assets WHERE tenant_id=? AND namespace=? AND sha256=?",
            (asset.tenant_id, asset.namespace, asset.sha256),
        ).fetchone()
        if existing:
            return AssetRecord.model_validate(json.loads(existing["payload_json"]))
        self.connection.execute(
            """
            INSERT INTO platform_assets
                (asset_id, tenant_id, namespace, sha256, payload_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                asset.asset_id,
                asset.tenant_id,
                asset.namespace,
                asset.sha256,
                json.dumps(asset.model_dump(mode="json"), ensure_ascii=False),
                now.isoformat(),
                now.isoformat(),
            ),
        )
        self.connection.commit()
        return asset

    def list_assets(self, tenant_id: str, namespace: str) -> list[AssetRecord]:
        rows = self.connection.execute(
            "SELECT payload_json FROM platform_assets WHERE tenant_id=? AND namespace=? ORDER BY created_at",
            (tenant_id, namespace),
        ).fetchall()
        return [AssetRecord.model_validate(json.loads(row["payload_json"])) for row in rows]

    def add_audit(self, event: AuditEvent) -> None:
        self.connection.execute(
            "INSERT INTO platform_audit_events VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                event.event_id,
                event.tenant_id,
                event.namespace,
                event.subject_id,
                event.action,
                event.occurred_at.isoformat(),
                json.dumps(event.payload, ensure_ascii=False),
            ),
        )
        self.connection.commit()

    def list_audit(self, tenant_id: str, namespace: str, subject_id: str | None = None) -> list[AuditEvent]:
        sql = "SELECT * FROM platform_audit_events WHERE tenant_id=? AND namespace=?"
        params: list[Any] = [tenant_id, namespace]
        if subject_id:
            sql += " AND subject_id=?"
            params.append(subject_id)
        sql += " ORDER BY occurred_at, event_id"
        rows = self.connection.execute(sql, params).fetchall()
        return [
            AuditEvent(
                event_id=row["event_id"],
                tenant_id=row["tenant_id"],
                namespace=row["namespace"],
                subject_id=row["subject_id"],
                action=row["action"],
                occurred_at=datetime.fromisoformat(row["occurred_at"]),
                payload=json.loads(row["payload_json"]),
            )
            for row in rows
        ]

    def save_run(self, run: RunRecord) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO platform_runs
                (run_id, tenant_id, namespace, operation, status, payload_json, started_at, finished_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.run_id,
                run.tenant_id,
                run.namespace,
                run.operation,
                run.status,
                json.dumps(run.model_dump(mode="json"), ensure_ascii=False),
                run.started_at.isoformat(),
                run.finished_at.isoformat() if run.finished_at else None,
            ),
        )
        self.connection.commit()

    def get_run(self, run_id: str) -> RunRecord | None:
        row = self.connection.execute(
            "SELECT payload_json FROM platform_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        return RunRecord.model_validate(json.loads(row["payload_json"])) if row else None

    def save_model_call(self, record: ModelCallRecord) -> None:
        self.connection.execute(
            "INSERT INTO platform_model_calls VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.call_id,
                record.run_id,
                record.operation,
                record.model,
                record.provider_host,
                int(record.success),
                json.dumps(record.model_dump(mode="json"), ensure_ascii=False),
                record.started_at.isoformat(),
                record.finished_at.isoformat(),
            ),
        )
        self.connection.commit()

    def list_model_calls(self, run_id: str | None = None) -> list[ModelCallRecord]:
        if run_id:
            rows = self.connection.execute(
                "SELECT payload_json FROM platform_model_calls WHERE run_id=? ORDER BY started_at",
                (run_id,),
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT payload_json FROM platform_model_calls ORDER BY started_at"
            ).fetchall()
        return [ModelCallRecord.model_validate(json.loads(row["payload_json"])) for row in rows]

    @staticmethod
    def _record(payload: str) -> MemoryRecord:
        return MemoryRecord.model_validate(json.loads(payload))

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
