from datetime import UTC, datetime

from omni_memory.graphs.query_graph import build_query_graph
from omni_memory.schemas.memory import CommittedFact
from omni_memory.schemas.query import GroundedAnswer, MemoryQuery
from omni_memory.stores.sqlite_store import SQLiteMemoryStore


class QueryStubStructured:
    def __init__(self, answer: GroundedAnswer):
        self.answer = answer

    def invoke(self, messages):
        return self.answer


class QueryStubModel:
    def __init__(self, answer: GroundedAnswer):
        self.answer = answer

    def with_structured_output(self, schema, *, method):
        assert method == "json_mode"
        return QueryStubStructured(self.answer)


def make_memory(memory_id: str, statement: str, quote: str) -> CommittedFact:
    return CommittedFact(
        memory_id=memory_id,
        source_episode_id="ep-query-1",
        statement=statement,
        evidence_quote=quote,
        ingested_at=datetime.now(UTC),
        confidence=0.95,
    )


def test_query_graph_answers_with_valid_citation(tmp_path):
    database = tmp_path / "query.sqlite3"
    memory = make_memory("m-query-1", "沈砚关掉了灯", "沈砚在凌晨三点关掉了灯")
    model = QueryStubModel(
        GroundedAnswer(
            answer="沈砚在凌晨三点关掉了灯。",
            citation_memory_ids=["m-query-1"],
            grounded=True,
            abstain=False,
        )
    )

    with SQLiteMemoryStore(database) as store:
        store.put_many([memory])
        result = build_query_graph(store, model=model).invoke(
            {"query": MemoryQuery(query="沈砚什么时候关灯？")}
        )

    assert result["status"] == "answered"
    assert result["answer"].citation_memory_ids == ["m-query-1"]
    assert result["answer"].grounded is True


def test_query_graph_abstains_without_retrieval(tmp_path):
    database = tmp_path / "query-empty.sqlite3"
    model = QueryStubModel(
        GroundedAnswer(
            answer="不应调用模型",
            citation_memory_ids=[],
            grounded=False,
            abstain=True,
        )
    )

    with SQLiteMemoryStore(database) as store:
        result = build_query_graph(store, model=model).invoke(
            {"query": MemoryQuery(query="完全不存在的内容")}
        )

    assert result["status"] == "abstained"
    assert result["answer"].abstain is True
    assert result["retrieved"] == []


def test_query_graph_rejects_unknown_citation(tmp_path):
    database = tmp_path / "query-unknown-citation.sqlite3"
    memory = make_memory("m-query-2", "沈砚关掉了灯", "沈砚在凌晨三点关掉了灯")
    model = QueryStubModel(
        GroundedAnswer(
            answer="沈砚去了北京。",
            citation_memory_ids=["not-retrieved"],
            grounded=True,
            abstain=False,
        )
    )

    with SQLiteMemoryStore(database) as store:
        store.put_many([memory])
        result = build_query_graph(store, model=model).invoke(
            {"query": MemoryQuery(query="沈砚什么时候关灯？")}
        )

    assert result["status"] == "abstained"
    assert result["answer"].grounded is False
    assert result["answer"].citation_memory_ids == []
