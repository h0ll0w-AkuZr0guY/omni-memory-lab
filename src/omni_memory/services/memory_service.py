from datetime import UTC, datetime
from typing import BinaryIO
from uuid import uuid4

from omni_memory.assets.blob_store import LocalBlobStore
from omni_memory.retrieval.sqlite_retriever import _terms
from omni_memory.schemas.platform import (
    AssetInput,
    AssetRecord,
    AuditEvent,
    MemoryInput,
    MemoryMutation,
    MemoryRecord,
    MemorySearchHit,
    MemorySearchResponse,
    ModelCallRecord,
    RunRecord,
)
from omni_memory.stores.platform_store import PlatformStore


class MemoryService:
    """应用层长期记忆服务；调用方不需要知道 SQLite 或 LangGraph 细节。"""

    def __init__(self, store: PlatformStore, blob_store: LocalBlobStore | None = None):
        self.store = store
        self.blob_store = blob_store

    def create(self, data: MemoryInput) -> MemoryMutation:
        if data.idempotency_key:
            existing = self.store.find_idempotent(
                data.tenant_id, data.namespace, data.idempotency_key
            )
            if existing:
                return MemoryMutation(
                    operation="create",
                    memory_id=existing.memory_id,
                    record=existing,
                    idempotent=True,
                    audit_event_id="idempotent-replay",
                )
        now = datetime.now(UTC)
        memory_id = self.store.stable_memory_id(data)
        existing = self.store.get_current(memory_id)
        if existing:
            return MemoryMutation(
                operation="create",
                memory_id=existing.memory_id,
                record=existing,
                idempotent=True,
                audit_event_id="stable-id-replay",
            )
        record = MemoryRecord(
            memory_id=memory_id,
            tenant_id=data.tenant_id,
            namespace=data.namespace,
            version=1,
            memory_type=data.memory_type,
            content=data.content,
            source_ref=data.source_ref,
            subject_refs=data.subject_refs,
            valid_at=data.valid_at,
            observed_at=data.observed_at,
            confidence=data.confidence,
            tags=data.tags,
            app_payload=data.app_payload,
            asset_refs=data.asset_refs,
            created_at=now,
            updated_at=now,
            metadata=data.metadata,
        )
        self.store.save_memory(record, data.idempotency_key)
        event = self._audit(data.tenant_id, data.namespace, memory_id, "created")
        return MemoryMutation(
            operation="create", memory_id=memory_id, record=record, audit_event_id=event.event_id
        )

    def update(self, memory_id: str, data: MemoryInput) -> MemoryMutation:
        current = self._require(memory_id, data.tenant_id, data.namespace)
        now = datetime.now(UTC)
        record = MemoryRecord(
            memory_id=current.memory_id,
            tenant_id=current.tenant_id,
            namespace=current.namespace,
            version=current.version + 1,
            memory_type=data.memory_type,
            content=data.content,
            source_ref=data.source_ref,
            lifecycle="active",
            subject_refs=data.subject_refs,
            valid_at=data.valid_at,
            observed_at=data.observed_at,
            confidence=data.confidence,
            tags=data.tags,
            app_payload=data.app_payload,
            asset_refs=data.asset_refs,
            supersedes=current.memory_id,
            created_at=current.created_at,
            updated_at=now,
            metadata=data.metadata,
        )
        self.store.save_memory(record, data.idempotency_key)
        event = self._audit(data.tenant_id, data.namespace, memory_id, "updated", {"version": record.version})
        return MemoryMutation(
            operation="update", memory_id=memory_id, record=record, audit_event_id=event.event_id
        )

    def delete(self, memory_id: str, tenant_id: str, namespace: str) -> MemoryMutation:
        current = self._require(memory_id, tenant_id, namespace)
        now = datetime.now(UTC)
        record = current.model_copy(update={"version": current.version + 1, "lifecycle": "deleted", "updated_at": now})
        self.store.save_memory(record, None)
        event = self._audit(tenant_id, namespace, memory_id, "deleted", {"version": record.version})
        return MemoryMutation(operation="delete", memory_id=memory_id, record=record, audit_event_id=event.event_id)

    def restore(self, memory_id: str, tenant_id: str, namespace: str) -> MemoryMutation:
        current = self._require(memory_id, tenant_id, namespace)
        now = datetime.now(UTC)
        record = current.model_copy(update={"version": current.version + 1, "lifecycle": "active", "updated_at": now})
        self.store.save_memory(record, None)
        event = self._audit(tenant_id, namespace, memory_id, "restored", {"version": record.version})
        return MemoryMutation(operation="restore", memory_id=memory_id, record=record, audit_event_id=event.event_id)

    def get(self, memory_id: str, tenant_id: str, namespace: str) -> MemoryRecord | None:
        record = self.store.get_current(memory_id)
        if record is None or record.tenant_id != tenant_id or record.namespace != namespace:
            return None
        return record

    def versions(self, memory_id: str, tenant_id: str, namespace: str) -> list[MemoryRecord]:
        current = self.get(memory_id, tenant_id, namespace)
        if current is None:
            return []
        return self.store.list_versions(memory_id)

    def search(self, tenant_id: str, namespace: str, query: str, top_k: int = 10, include_deleted: bool = False) -> MemorySearchResponse:
        records = self.store.list_current(tenant_id, namespace, include_deleted=include_deleted)
        terms = _terms(query)
        hits: list[MemorySearchHit] = []
        for record in records:
            searchable = " ".join(
                [record.content or "", " ".join(record.tags), " ".join(record.subject_refs)]
            )
            matched = [term for term in terms if term in searchable]
            if not matched:
                continue
            score = len(matched) / max(1, len(terms))
            if query.strip() in searchable:
                score += 1.0
            hits.append(MemorySearchHit(record=record, score=score, matched_terms=matched))
        hits.sort(key=lambda item: (-item.score, item.record.updated_at, item.record.memory_id))
        return MemorySearchResponse(hits=hits[:top_k], query=query, total_candidates=len(records))

    def register_asset(self, data: AssetInput) -> AssetRecord:
        now = datetime.now(UTC)
        asset = AssetRecord(
            asset_id=f"asset_{uuid4().hex}",
            tenant_id=data.tenant_id,
            namespace=data.namespace,
            filename=data.filename,
            media_type=data.media_type,
            source_ref=data.source_ref,
            size_bytes=data.size_bytes,
            sha256=data.sha256,
            storage_uri=data.storage_uri,
            width=data.width,
            height=data.height,
            app_payload=data.app_payload,
            created_at=now,
            updated_at=now,
        )
        return self.store.save_asset(asset)

    def register_asset_bytes(
        self,
        data: AssetInput,
        stream: BinaryIO,
    ) -> AssetRecord:
        if self.blob_store is None:
            raise RuntimeError("blob_store is not configured")
        sha256, storage_uri, size_bytes = self.blob_store.put_stream(stream, data.filename)
        if data.sha256 != sha256 or data.size_bytes != size_bytes:
            raise ValueError("上传内容与 sha256/size_bytes 不匹配")
        return self.register_asset(
            data.model_copy(update={"storage_uri": storage_uri})
        )

    def audit(self, tenant_id: str, namespace: str, subject_id: str | None = None) -> list[AuditEvent]:
        return self.store.list_audit(tenant_id, namespace, subject_id)

    def save_run(self, run: RunRecord) -> None:
        self.store.save_run(run)

    def get_run(self, run_id: str) -> RunRecord | None:
        return self.store.get_run(run_id)

    def save_model_call(self, call: ModelCallRecord) -> None:
        self.store.save_model_call(call)

    def list_model_calls(self, run_id: str | None = None) -> list[ModelCallRecord]:
        return self.store.list_model_calls(run_id)

    def _require(self, memory_id: str, tenant_id: str, namespace: str) -> MemoryRecord:
        current = self.get(memory_id, tenant_id, namespace)
        if current is None:
            raise KeyError(f"memory not found: {memory_id}")
        return current

    def _audit(self, tenant_id: str, namespace: str, subject_id: str, action: str, payload: dict | None = None) -> AuditEvent:
        event = AuditEvent(
            event_id=f"audit_{uuid4().hex}",
            tenant_id=tenant_id,
            namespace=namespace,
            subject_id=subject_id,
            action=action,
            occurred_at=datetime.now(UTC),
            payload=payload or {},
        )
        self.store.add_audit(event)
        return event
