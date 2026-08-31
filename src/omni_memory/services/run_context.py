from datetime import UTC, datetime
from typing import Self
from uuid import uuid4

from omni_memory.schemas.platform import RunRecord
from omni_memory.stores.platform_store import PlatformStore


class RunContext:
    """一个应用操作的可审计生命周期；异常时自动记录 failed。"""

    def __init__(self, store: PlatformStore, tenant_id: str, namespace: str, operation: str):
        self.store = store
        self.run = RunRecord(
            run_id=f"run_{uuid4().hex}",
            tenant_id=tenant_id,
            namespace=namespace,
            operation=operation,
            status="running",
            started_at=datetime.now(UTC),
        )

    def __enter__(self) -> Self:
        self.store.save_run(self.run)
        return self

    def succeed(self, counters: dict[str, int] | None = None) -> RunRecord:
        self.run = self.run.model_copy(
            update={
                "status": "succeeded",
                "finished_at": datetime.now(UTC),
                "counters": counters or {},
            }
        )
        self.store.save_run(self.run)
        return self.run

    def fail(self, error: Exception) -> RunRecord:
        self.run = self.run.model_copy(
            update={
                "status": "failed",
                "finished_at": datetime.now(UTC),
                "error_type": type(error).__name__,
                "error_message": str(error)[:1000],
            }
        )
        self.store.save_run(self.run)
        return self.run

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if exc_value is not None:
            self.fail(exc_value)
        elif self.run.status == "running":
            self.succeed()
