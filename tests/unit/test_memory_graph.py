from datetime import UTC, datetime

from omni_memory.graphs.memory_graph import build_validation_graph
from omni_memory.schemas.memory import Episode, FactCandidate

NOW = datetime.now(UTC)


def episode() -> Episode:
    return Episode(
        episode_id="ep-graph-1",
        text="顾言在雨夜修好了收音机。",
        ingested_at=NOW,
        source="graph-test",
    )


def candidate(statement: str, quote: str) -> FactCandidate:
    return FactCandidate(
        statement=statement,
        evidence_quote=quote,
        confidence=0.9,
    )


def test_graph_routes_valid_candidates_to_ready():
    graph = build_validation_graph()
    result = graph.invoke(
        {
            "episode": episode(),
            "candidates": [candidate("顾言修好了收音机", "顾言在雨夜修好了收音机")],
        }
    )

    assert result["status"] == "ready_for_persistence"
    assert len(result["valid_candidates"]) == 1
    assert result["issues"] == []


def test_graph_routes_invalid_evidence_to_review():
    graph = build_validation_graph()
    result = graph.invoke(
        {
            "episode": episode(),
            "candidates": [candidate("顾言去了北京", "顾言去了北京")],
        }
    )

    assert result["status"] == "needs_review"
    assert result["valid_candidates"] == []
    assert result["issues"][0].code == "quote_not_found"


def test_graph_keeps_valid_candidates_when_some_need_review():
    graph = build_validation_graph()
    result = graph.invoke(
        {
            "episode": episode(),
            "candidates": [
                candidate("顾言修好了收音机", "顾言在雨夜修好了收音机"),
                candidate("顾言去了北京", "顾言去了北京"),
            ],
        }
    )

    assert result["status"] == "needs_review"
    assert len(result["valid_candidates"]) == 1
    assert len(result["issues"]) == 1

class GraphStubStructuredModel:
    def invoke(self, messages):
        from omni_memory.schemas.extraction import FactExtraction

        return FactExtraction(
            facts=[
                FactCandidate(
                    statement="顾言修好了收音机",
                    evidence_quote="顾言在雨夜修好了收音机。",
                    confidence=0.95,
                )
            ]
        )


class GraphStubChatModel:
    def __init__(self):
        self.structured = GraphStubStructuredModel()

    def with_structured_output(self, schema, *, method):
        assert method == "json_mode"
        return self.structured


def test_full_memory_graph_extracts_then_validates():
    from omni_memory.graphs.memory_graph import build_memory_graph

    graph = build_memory_graph(model=GraphStubChatModel())
    result = graph.invoke(
        {
            "episode": Episode(
                episode_id="ep-full-1",
                text="顾言在雨夜修好了收音机。",
                ingested_at=NOW,
                source="graph-test",
            )
        }
    )

    assert result["status"] == "ready_for_persistence"
    assert len(result["candidates"]) == 1
    assert len(result["valid_candidates"]) == 1
    assert result["issues"] == []


def test_full_memory_graph_sends_hallucinated_candidate_to_review():
    class HallucinatingStructuredModel:
        def invoke(self, messages):
            from omni_memory.schemas.extraction import FactExtraction

            return FactExtraction(
                facts=[
                    FactCandidate(
                        statement="顾言去了北京",
                        evidence_quote="顾言去了北京",
                        confidence=0.99,
                    )
                ]
            )

    class HallucinatingChatModel(GraphStubChatModel):
        def __init__(self):
            self.structured = HallucinatingStructuredModel()

    from omni_memory.graphs.memory_graph import build_memory_graph

    graph = build_memory_graph(model=HallucinatingChatModel())
    result = graph.invoke(
        {
            "episode": Episode(
                episode_id="ep-full-2",
                text="顾言在雨夜修好了收音机。",
                ingested_at=NOW,
                source="graph-test",
            )
        }
    )

    assert result["status"] == "needs_review"
    assert result["valid_candidates"] == []
    assert result["issues"][0].code == "quote_not_found"

def test_full_memory_graph_persists_only_validated_memories(tmp_path):
    from omni_memory.graphs.memory_graph import build_memory_graph
    from omni_memory.stores.sqlite_store import SQLiteMemoryStore

    database = tmp_path / "graph-memory.sqlite3"
    episode = Episode(
        episode_id="ep-persist-1",
        text="顾言在雨夜修好了收音机。",
        ingested_at=NOW,
        source="graph-test",
    )

    with SQLiteMemoryStore(database) as store:
        graph = build_memory_graph(model=GraphStubChatModel(), store=store)
        result = graph.invoke({"episode": episode})

        assert result["status"] == "committed"
        assert len(result["committed"]) == 1
        assert store.count() == 1
        assert store.get("ep-persist-1:fact:0000") is not None


def test_full_memory_graph_does_not_persist_invalid_candidates(tmp_path):
    from omni_memory.graphs.memory_graph import build_memory_graph
    from omni_memory.stores.sqlite_store import SQLiteMemoryStore

    class InvalidStructuredModel:
        def invoke(self, messages):
            from omni_memory.schemas.extraction import FactExtraction

            return FactExtraction(
                facts=[
                    FactCandidate(
                        statement="顾言去了北京",
                        evidence_quote="顾言去了北京",
                        confidence=0.99,
                    )
                ]
            )

    class InvalidChatModel(GraphStubChatModel):
        def __init__(self):
            self.structured = InvalidStructuredModel()

    database = tmp_path / "graph-invalid.sqlite3"
    episode = Episode(
        episode_id="ep-persist-2",
        text="顾言在雨夜修好了收音机。",
        ingested_at=NOW,
        source="graph-test",
    )

    with SQLiteMemoryStore(database) as store:
        graph = build_memory_graph(model=InvalidChatModel(), store=store)
        result = graph.invoke({"episode": episode})

        assert result["status"] == "needs_review"
        assert result["committed"] == []
        assert store.count() == 0
