from datetime import UTC, datetime

from omni_memory.schemas.memory import CommittedFact
from omni_memory.stores.sqlite_store import SQLiteMemoryStore

NOW = datetime.now(UTC)


def memory(memory_id: str) -> CommittedFact:
    return CommittedFact(
        memory_id=memory_id,
        source_episode_id="ep-1",
        statement="沈砚关掉了灯",
        evidence_quote="沈砚在凌晨三点关掉了灯",
        ingested_at=NOW,
        confidence=0.95,
    )


def test_sqlite_store_round_trips_committed_memory(tmp_path):
    database = tmp_path / "memory.sqlite3"

    with SQLiteMemoryStore(database) as store:
        store.put_many([memory("m-1")])
        loaded = store.get("m-1")

        assert loaded is not None
        assert loaded.memory_id == "m-1"
        assert loaded.evidence_quote == "沈砚在凌晨三点关掉了灯"
        assert store.count() == 1


def test_sqlite_store_survives_reopen(tmp_path):
    database = tmp_path / "memory.sqlite3"

    with SQLiteMemoryStore(database) as store:
        store.put_many([memory("m-1"), memory("m-2")])

    with SQLiteMemoryStore(database) as store:
        assert [item.memory_id for item in store.list_all()] == ["m-1", "m-2"]


def test_sqlite_store_replaces_same_memory_id(tmp_path):
    database = tmp_path / "memory.sqlite3"
    updated = memory("m-1").model_copy(update={"statement": "沈砚熄灭了灯"})

    with SQLiteMemoryStore(database) as store:
        store.put_many([memory("m-1")])
        store.put_many([updated])

        assert store.count() == 1
        assert store.get("m-1").statement == "沈砚熄灭了灯"

def test_sqlite_store_records_audit_events(tmp_path):
    database = tmp_path / "memory.sqlite3"

    with SQLiteMemoryStore(database) as store:
        store.put_many([memory("m-1")])
        updated = memory("m-1").model_copy(update={"statement": "沈砚熄灭了灯"})
        store.put_many([updated])

        events = store.list_audit_events("m-1")

        assert len(events) == 2
        assert [event.action for event in events] == ["created", "replaced"]
        assert all(event.memory_id == "m-1" for event in events)


def test_sqlite_store_lists_memories_by_episode(tmp_path):
    database = tmp_path / "memory.sqlite3"
    first = memory("m-1")
    second = memory("m-2").model_copy(update={"source_episode_id": "ep-2"})

    with SQLiteMemoryStore(database) as store:
        store.put_many([first, second])

        result = store.list_by_episode("ep-1")

        assert [item.memory_id for item in result] == ["m-1"]
