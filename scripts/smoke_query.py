import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from omni_memory.graphs.query_graph import build_query_graph
from omni_memory.schemas.memory import CommittedFact
from omni_memory.schemas.query import MemoryQuery
from omni_memory.stores.sqlite_store import SQLiteMemoryStore


DB = Path("artifacts") / "smoke-query.sqlite3"


def main() -> None:
    DB.parent.mkdir(parents=True, exist_ok=True)
    with SQLiteMemoryStore(DB) as store:
        store.put_many(
            [
                CommittedFact(
                    memory_id="smoke-memory-1",
                    source_episode_id="smoke-episode-1",
                    statement="沈砚在凌晨三点关掉了灯",
                    evidence_quote="沈砚在凌晨三点关掉了灯",
                    ingested_at=datetime.now(UTC),
                    confidence=0.98,
                ),
                CommittedFact(
                    memory_id="smoke-memory-2",
                    source_episode_id="smoke-episode-1",
                    statement="蓝色笔记本被放回抽屉",
                    evidence_quote="他把写满批注的蓝色笔记本放回抽屉",
                    ingested_at=datetime.now(UTC),
                    confidence=0.96,
                ),
            ]
        )
        started = perf_counter()
        result = build_query_graph(store).invoke(
            {"query": MemoryQuery(query="沈砚什么时候关掉了灯？", top_k=3)}
        )
        elapsed = perf_counter() - started

    answer = result["answer"]
    print("query_call=ok")
    print(f"elapsed_seconds={elapsed:.2f}")
    print(f"status={result['status']}")
    print("answer=" + json.dumps(answer.model_dump(mode="json"), ensure_ascii=False))
    print(
        "retrieved_ids="
        + json.dumps(
            [item.memory.memory_id for item in result.get("retrieved", [])],
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
