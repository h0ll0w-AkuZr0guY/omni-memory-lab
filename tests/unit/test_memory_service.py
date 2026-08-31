from datetime import UTC, datetime

import pytest

from omni_memory.schemas.platform import AssetInput, MemoryInput
from omni_memory.services.memory_service import MemoryService
from omni_memory.stores.platform_store import PlatformStore


@pytest.fixture
def service(tmp_path):
    with PlatformStore(tmp_path / "platform.sqlite3") as store:
        yield MemoryService(store)


def input_data(**overrides):
    payload = {
        "tenant_id": "tenant-a",
        "namespace": "novel",
        "content": "沈砚在雨夜返回故乡。",
        "memory_type": "episodic",
        "source_ref": "book:chapter-1:span-10-20",
        "idempotency_key": "event-1",
        "subject_refs": ["character:shen-yan"],
        "valid_at": datetime(2026, 1, 1, tzinfo=UTC),
        "confidence": 0.95,
    }
    payload.update(overrides)
    return MemoryInput(**payload)


def test_create_is_idempotent(service):
    first = service.create(input_data())
    replay = service.create(input_data())

    assert first.record is not None
    assert replay.idempotent is True
    assert replay.memory_id == first.memory_id
    assert len(service.audit("tenant-a", "novel")) == 1


def test_update_creates_version_and_preserves_history(service):
    created = service.create(input_data())
    updated = service.update(
        created.memory_id,
        input_data(
            idempotency_key="event-2",
            content="沈砚在雨夜回到故乡，并带着蓝色笔记本。",
        ),
    )

    assert updated.record is not None
    assert updated.record.version == 2
    assert updated.record.supersedes == created.memory_id
    versions = service.versions(created.memory_id, "tenant-a", "novel")
    assert [item.version for item in versions] == [1, 2]
    assert [event.action for event in service.audit("tenant-a", "novel")] == [
        "created",
        "updated",
    ]


def test_delete_and_restore_are_soft_lifecycle_transitions(service):
    created = service.create(input_data())
    deleted = service.delete(created.memory_id, "tenant-a", "novel")
    assert deleted.record is not None
    assert deleted.record.lifecycle == "deleted"
    assert service.search("tenant-a", "novel", "沈砚").hits == []
    assert service.search("tenant-a", "novel", "沈砚", include_deleted=True).hits

    restored = service.restore(created.memory_id, "tenant-a", "novel")
    assert restored.record is not None
    assert restored.record.lifecycle == "active"
    assert service.search("tenant-a", "novel", "沈砚").hits


def test_tenant_and_namespace_are_isolated(service):
    service.create(input_data())
    service.create(input_data(tenant_id="tenant-b", idempotency_key="other"))

    assert len(service.search("tenant-a", "novel", "沈砚").hits) == 1
    assert len(service.search("tenant-b", "novel", "沈砚").hits) == 1
    assert service.get("unknown", "tenant-a", "novel") is None


def test_assets_are_deduplicated_by_sha256(service):
    payload = {
        "tenant_id": "tenant-a",
        "namespace": "novel",
        "filename": "portrait.png",
        "media_type": "image/png",
        "source_ref": "neuro-book:character:shen-yan",
        "size_bytes": 123,
        "sha256": "a" * 64,
        "storage_uri": "file:///assets/portrait.png",
    }
    first = service.register_asset(AssetInput(**payload))
    second_payload = {**payload, "filename": "copy.png"}
    second = service.register_asset(AssetInput(**second_payload))

    assert first.asset_id == second.asset_id
