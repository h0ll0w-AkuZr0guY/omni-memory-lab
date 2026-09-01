from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile

from omni_memory.assets.blob_store import LocalBlobStore
from omni_memory.schemas.platform import (
    AssetInput,
    AssetRecord,
    MemoryInput,
    MemoryMutation,
    MemoryRecord,
    MemorySearchRequest,
    MemorySearchResponse,
    ModelCallRecord,
    RunRecord,
)
from omni_memory.services.memory_service import MemoryService
from omni_memory.stores.platform_store import PlatformStore


def create_app(
    database_path: str | Path = "artifacts/platform.sqlite3",
    blob_root: str | Path | None = None,
) -> FastAPI:
    store = PlatformStore(database_path)
    resolved_blob_root = blob_root or Path(database_path).with_suffix("").with_name(
        f"{Path(database_path).stem}-blobs"
    )
    service = MemoryService(store, LocalBlobStore(resolved_blob_root))
    app = FastAPI(title="Omni Memory Platform", version="0.2.0")
    app.state.memory_store = store
    app.state.memory_service = service

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "omni-memory-platform"}

    @app.post("/v1/memories", response_model=MemoryMutation, status_code=201)
    def create_memory(data: MemoryInput) -> MemoryMutation:
        return service.create(data)

    @app.get("/v1/memories/{memory_id}", response_model=MemoryRecord)
    def get_memory(memory_id: str, tenant_id: str, namespace: str) -> MemoryRecord:
        record = service.get(memory_id, tenant_id, namespace)
        if record is None:
            raise HTTPException(status_code=404, detail="memory not found")
        return record

    @app.get("/v1/memories/{memory_id}/versions", response_model=list[MemoryRecord])
    def get_versions(memory_id: str, tenant_id: str, namespace: str) -> list[MemoryRecord]:
        versions = service.versions(memory_id, tenant_id, namespace)
        if not versions:
            raise HTTPException(status_code=404, detail="memory not found")
        return versions

    @app.put("/v1/memories/{memory_id}", response_model=MemoryMutation)
    def update_memory(memory_id: str, data: MemoryInput) -> MemoryMutation:
        try:
            return service.update(memory_id, data)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.delete("/v1/memories/{memory_id}", response_model=MemoryMutation)
    def delete_memory(memory_id: str, tenant_id: str, namespace: str) -> MemoryMutation:
        try:
            return service.delete(memory_id, tenant_id, namespace)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post("/v1/memories/{memory_id}/restore", response_model=MemoryMutation)
    def restore_memory(memory_id: str, tenant_id: str, namespace: str) -> MemoryMutation:
        try:
            return service.restore(memory_id, tenant_id, namespace)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post("/v1/memories/search", response_model=MemorySearchResponse)
    def search_memory(data: MemorySearchRequest) -> MemorySearchResponse:
        return service.search(
            tenant_id=data.tenant_id,
            namespace=data.namespace,
            query=data.query,
            top_k=data.top_k,
            include_deleted=data.include_deleted,
        )

    @app.post("/v1/assets", response_model=AssetRecord, status_code=201)
    def register_asset(data: AssetInput) -> AssetRecord:
        return service.register_asset(data)

    @app.post("/v1/assets/upload", response_model=AssetRecord, status_code=201)
    def upload_asset(
        file: Annotated[UploadFile, File()],
        tenant_id: str = Form(...),
        namespace: str = Form(...),
        source_ref: str = Form(...),
        sha256: str = Form(...),
        size_bytes: int = Form(...),
    ) -> AssetRecord:
        data = AssetInput(
            tenant_id=tenant_id,
            namespace=namespace,
            filename=file.filename or "upload.bin",
            media_type=file.content_type or "application/octet-stream",
            source_ref=source_ref,
            size_bytes=size_bytes,
            sha256=sha256,
            storage_uri="pending://upload",
        )
        try:
            return service.register_asset_bytes(data, file.file)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/v1/audit")
    def list_audit(tenant_id: str, namespace: str, subject_id: str | None = None):
        return service.audit(tenant_id, namespace, subject_id)

    @app.get("/v1/runs", response_model=list[RunRecord])
    def list_runs(
        tenant_id: str | None = Query(default=None),
        namespace: str | None = Query(default=None),
    ) -> list[RunRecord]:
        return service.list_runs(tenant_id, namespace)

    @app.get("/v1/runs/{run_id}", response_model=RunRecord)
    def get_run(run_id: str) -> RunRecord:
        run = service.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        return run

    @app.get("/v1/model-calls", response_model=list[ModelCallRecord])
    def list_model_calls(run_id: str | None = Query(default=None)) -> list[ModelCallRecord]:
        return service.list_model_calls(run_id)

    return app


app = create_app()
