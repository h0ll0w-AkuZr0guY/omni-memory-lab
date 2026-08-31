from omni_memory.adapters.neurobook import NeuroBookAdapter


def test_neurobook_event_maps_to_generic_memory_input():
    result = NeuroBookAdapter().to_memory_input(
        {
            "project_id": "project-1",
            "event_id": "event-1",
            "event_type": "character_fact",
            "chapter_id": "chapter-3",
            "character_id": "char-yan",
            "statement": "沈砚畏惧深海。",
            "subject_refs": ["character:yan"],
            "confidence": 0.88,
        }
    )

    assert result.tenant_id == "project-1"
    assert result.namespace == "novel"
    assert result.memory_type == "entity_fact"
    assert result.content == "沈砚畏惧深海。"
    assert result.idempotency_key == "event-1"
    assert result.app_payload["chapter_id"] == "chapter-3"


def test_neurobook_generated_asset_keeps_generation_provenance():
    result = NeuroBookAdapter().to_asset_input(
        {
            "project_id": "project-1",
            "filename": "yan.png",
            "media_type": "image/png",
            "size_bytes": 1024,
            "sha256": "a" * 64,
            "storage_uri": "file:///assets/yan.png",
            "character_id": "char-yan",
            "generation": {"model": "image-model", "prompt_hash": "p" * 64},
        }
    )

    assert result.tenant_id == "project-1"
    assert result.app_payload["generation"]["model"] == "image-model"
    assert result.app_payload["character_id"] == "char-yan"
