from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MemoryType = Literal[
    "semantic",
    "episodic",
    "procedural",
    "preference",
    "entity_fact",
    "relationship",
    "event",
    "observation",
]
MemoryLifecycle = Literal["active", "superseded", "deleted", "review"]
MutationKind = Literal["created", "updated", "deleted", "restored", "linked"]
RunStatus = Literal["queued", "running", "succeeded", "failed", "needs_review"]


class MemoryInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    tenant_id: str = Field(min_length=1)
    namespace: str = Field(min_length=1)
    content: str | None = None
    memory_type: MemoryType = "semantic"
    source_ref: str = Field(min_length=1)
    idempotency_key: str | None = None
    subject_refs: list[str] = Field(default_factory=list)
    valid_at: datetime | None = None
    observed_at: datetime | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    app_payload: dict[str, Any] = Field(default_factory=dict)
    asset_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any, /) -> None:
        if not self.content and not self.asset_refs:
            raise ValueError("content 和 asset_refs 至少提供一个")


class MemoryRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    memory_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    namespace: str = Field(min_length=1)
    version: int = Field(ge=1)
    memory_type: MemoryType = "semantic"
    content: str | None = None
    source_ref: str = Field(min_length=1)
    lifecycle: MemoryLifecycle = "active"
    subject_refs: list[str] = Field(default_factory=list)
    valid_at: datetime | None = None
    observed_at: datetime | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    app_payload: dict[str, Any] = Field(default_factory=dict)
    asset_refs: list[str] = Field(default_factory=list)
    supersedes: str | None = None
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryMutation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["create", "update", "delete", "restore"]
    memory_id: str
    record: MemoryRecord | None = None
    idempotent: bool = False
    audit_event_id: str


class MemorySearchRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    namespace: str = Field(min_length=1)
    query: str = Field(min_length=1)
    top_k: int = Field(default=10, ge=1, le=100)
    memory_types: list[MemoryType] = Field(default_factory=list)
    include_deleted: bool = False


class MemorySearchHit(BaseModel):
    record: MemoryRecord
    score: float
    matched_terms: list[str] = Field(default_factory=list)


class MemorySearchResponse(BaseModel):
    hits: list[MemorySearchHit]
    query: str
    total_candidates: int


class AssetInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    tenant_id: str = Field(min_length=1)
    namespace: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64)
    storage_uri: str = Field(min_length=1)
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    app_payload: dict[str, Any] = Field(default_factory=dict)


class AssetRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    asset_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    namespace: str = Field(min_length=1)
    filename: str
    media_type: str
    source_ref: str
    size_bytes: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64)
    storage_uri: str
    status: Literal["active", "deleted"] = "active"
    width: int | None = None
    height: int | None = None
    app_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class AuditEvent(BaseModel):
    event_id: str
    tenant_id: str
    namespace: str
    subject_id: str
    action: MutationKind | Literal["model_call", "run_started", "run_finished"]
    occurred_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class ModelCallRecord(BaseModel):
    call_id: str
    run_id: str | None = None
    operation: str
    model: str
    provider_host: str
    started_at: datetime
    finished_at: datetime
    success: bool
    retry_count: int = 0
    input_chars: int = 0
    output_chars: int = 0
    usage_available: bool = False
    usage: dict[str, Any] = Field(default_factory=dict)
    provider_request_id: str | None = None
    error_type: str | None = None
    error_message: str | None = None


class RunRecord(BaseModel):
    run_id: str
    tenant_id: str
    namespace: str
    operation: str
    status: RunStatus
    started_at: datetime
    finished_at: datetime | None = None
    error_type: str | None = None
    error_message: str | None = None
    counters: dict[str, int] = Field(default_factory=dict)
