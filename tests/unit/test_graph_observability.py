from datetime import UTC, datetime

from omni_memory.graphs.memory_graph import build_memory_graph
from omni_memory.schemas.memory import Episode
from omni_memory.stores.platform_store import PlatformStore
from tests.unit.test_memory_graph import GraphStubChatModel


def test_memory_graph_persists_model_call_with_run_id(tmp_path):
    database = tmp_path / "graph-observability.sqlite3"
    episode = Episode(
        episode_id="ep-observed-1",
        text="顾言在雨夜修好了收音机。",
        ingested_at=datetime.now(UTC),
        source="test",
    )

    with PlatformStore(database) as call_store:
        graph = build_memory_graph(
            model=GraphStubChatModel(),
            call_store=call_store,
            run_id="run-graph-1",
        )
        result = graph.invoke({"episode": episode})
        calls = call_store.list_model_calls("run-graph-1")

    assert result["status"] == "ready_for_persistence"
    assert len(calls) == 1
    assert calls[0].operation == "fact_extraction"
    assert calls[0].success is True
    assert calls[0].run_id == "run-graph-1"


def test_memory_graph_persists_failed_model_call(tmp_path):
    class FailingStructuredModel:
        def invoke(self, messages):
            raise TimeoutError("test provider timeout")

    class FailingChatModel:
        def with_structured_output(self, schema, *, method):
            return FailingStructuredModel()

    database = tmp_path / "graph-failure.sqlite3"
    episode = Episode(
        episode_id="ep-observed-2",
        text="顾言在雨夜修好了收音机。",
        ingested_at=datetime.now(UTC),
        source="test",
    )

    with PlatformStore(database) as call_store:
        graph = build_memory_graph(
            model=FailingChatModel(),
            call_store=call_store,
            run_id="run-graph-2",
        )
        try:
            graph.invoke({"episode": episode})
        except TimeoutError:
            pass
        calls = call_store.list_model_calls("run-graph-2")

    assert len(calls) == 1
    assert calls[0].success is False
    assert calls[0].error_type == "TimeoutError"
