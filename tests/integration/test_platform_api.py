import hashlib

from fastapi.testclient import TestClient

from omni_memory.server import create_app


def body(**overrides):
    payload = {
        "tenant_id": "tenant-api",
        "namespace": "default",
        "content": "林默收藏了一张旧照片。",
        "memory_type": "episodic",
        "source_ref": "app:message:1",
        "idempotency_key": "message-1",
        "tags": ["photo"],
    }
    payload.update(overrides)
    return payload


def test_platform_api_lifecycle(tmp_path):
    client = TestClient(create_app(tmp_path / "api.sqlite3"))

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    created = client.post("/v1/memories", json=body())
    assert created.status_code == 201
    record = created.json()["record"]
    memory_id = record["memory_id"]

    replay = client.post("/v1/memories", json=body())
    assert replay.status_code == 201
    assert replay.json()["idempotent"] is True

    search = client.post(
        "/v1/memories/search",
        json={"tenant_id": "tenant-api", "namespace": "default", "query": "旧照片"},
    )
    assert search.status_code == 200
    assert search.json()["hits"][0]["record"]["memory_id"] == memory_id

    updated = client.put(
        f"/v1/memories/{memory_id}",
        json=body(
            idempotency_key="message-2",
            content="林默收藏了一张旧照片，并把它放进书里。",
            source_ref="app:message:2",
        ),
    )
    assert updated.status_code == 200
    assert updated.json()["record"]["version"] == 2

    versions = client.get(
        f"/v1/memories/{memory_id}/versions",
        params={"tenant_id": "tenant-api", "namespace": "default"},
    )
    assert [item["version"] for item in versions.json()] == [1, 2]

    deleted = client.delete(
        f"/v1/memories/{memory_id}",
        params={"tenant_id": "tenant-api", "namespace": "default"},
    )
    assert deleted.status_code == 200
    assert deleted.json()["record"]["lifecycle"] == "deleted"

    restored = client.post(
        f"/v1/memories/{memory_id}/restore",
        params={"tenant_id": "tenant-api", "namespace": "default"},
    )
    assert restored.status_code == 200
    assert restored.json()["record"]["lifecycle"] == "active"

    asset = client.post(
        "/v1/assets",
        json={
            "tenant_id": "tenant-api",
            "namespace": "default",
            "filename": "old-photo.png",
            "media_type": "image/png",
            "source_ref": "app:image:1",
            "size_bytes": 10,
            "sha256": "b" * 64,
            "storage_uri": "file:///tmp/old-photo.png",
        },
    )
    assert asset.status_code == 201
    assert asset.json()["sha256"] == "b" * 64

    content = b"fake image bytes"
    uploaded = client.post(
        "/v1/assets/upload",
        data={
            "tenant_id": "tenant-api",
            "namespace": "default",
            "source_ref": "app:image:upload",
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": str(len(content)),
        },
        files={"file": ("portrait.png", content, "image/png")},
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["storage_uri"].startswith("file:")

    audit = client.get(
        "/v1/audit",
        params={"tenant_id": "tenant-api", "namespace": "default", "subject_id": memory_id},
    )
    assert audit.status_code == 200
    assert [item["action"] for item in audit.json()] == [
        "created",
        "updated",
        "deleted",
        "restored",
    ]
