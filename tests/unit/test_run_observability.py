from datetime import UTC, datetime

from omni_memory.llm.observability import invoke_with_observation
from omni_memory.schemas.platform import RunRecord
from omni_memory.stores.platform_store import PlatformStore


class FakeInvoker:
    def invoke(self, payload):
        return "ok"


class FakeModel:
    model_name = "glm-5.3-flash"
    openai_api_base = "https://open.bigmodel.cn/api/paas/v4"


def test_list_runs_filters_and_orders_by_start_time(tmp_path):
    database = tmp_path / "runs.sqlite3"
    with PlatformStore(database) as store:
        for run_id, tenant_id in [("run-2", "tenant-a"), ("run-1", "tenant-a"), ("run-3", "tenant-b")]:
            store.save_run(
                RunRecord(
                    run_id=run_id,
                    tenant_id=tenant_id,
                    namespace="novel",
                    operation="test",
                    status="succeeded",
                    started_at=datetime(2026, 1, int(run_id[-1]), tzinfo=UTC),
                )
            )
        runs = store.list_runs("tenant-a", "novel")

    assert [run.run_id for run in runs] == ["run-1", "run-2"]


def test_observer_uses_explicit_chat_model_metadata(tmp_path):
    database = tmp_path / "calls.sqlite3"
    with PlatformStore(database) as store:
        invoke_with_observation(
            FakeInvoker(),
            "safe payload",
            operation="test",
            store=store,
            run_id="run-1",
            model_source=FakeModel(),
        )
        calls = store.list_model_calls("run-1")

    assert len(calls) == 1
    assert calls[0].model == "glm-5.3-flash"
    assert calls[0].provider_host == "open.bigmodel.cn"
