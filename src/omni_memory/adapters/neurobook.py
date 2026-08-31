from datetime import UTC, datetime
from typing import Any

from omni_memory.schemas.platform import AssetInput, MemoryInput


class NeuroBookAdapter:
    """参考适配器：核心平台不依赖 neuro-book，本类只负责字段映射。"""

    application_name = "neuro-book"

    def to_memory_input(self, event: dict[str, Any]) -> MemoryInput:
        event_type = event.get("event_type", "chapter_fact")
        source_ref = str(event.get("source_ref") or event.get("chapter_id") or "neuro-book:event")
        content = event.get("content") or event.get("statement")
        if not content:
            raise ValueError("neuro-book event requires content or statement")
        return MemoryInput(
            tenant_id=str(event.get("project_id", "default-project")),
            namespace=str(event.get("namespace", "novel")),
            content=str(content),
            memory_type={
                "character_fact": "entity_fact",
                "relationship": "relationship",
                "timeline_event": "event",
                "chapter_fact": "semantic",
            }.get(event_type, "semantic"),
            source_ref=source_ref,
            idempotency_key=str(event.get("event_id")) if event.get("event_id") else None,
            subject_refs=[str(item) for item in event.get("subject_refs", [])],
            observed_at=datetime.now(UTC),
            confidence=event.get("confidence"),
            tags=[str(item) for item in event.get("tags", [])],
            app_payload={
                "application": self.application_name,
                "event_type": event_type,
                "chapter_id": event.get("chapter_id"),
                "scene_id": event.get("scene_id"),
                "raw_fields": {
                    key: value
                    for key, value in event.items()
                    if key not in {"content", "statement"}
                },
            },
        )

    def to_asset_input(self, asset: dict[str, Any]) -> AssetInput:
        return AssetInput(
            tenant_id=str(asset.get("project_id", "default-project")),
            namespace=str(asset.get("namespace", "novel")),
            filename=str(asset["filename"]),
            media_type=str(asset["media_type"]),
            source_ref=str(asset.get("source_ref", "neuro-book:asset")),
            size_bytes=int(asset["size_bytes"]),
            sha256=str(asset["sha256"]),
            storage_uri=str(asset["storage_uri"]),
            width=asset.get("width"),
            height=asset.get("height"),
            app_payload={
                "application": self.application_name,
                "character_id": asset.get("character_id"),
                "chapter_id": asset.get("chapter_id"),
                "generation": asset.get("generation", {}),
            },
        )
