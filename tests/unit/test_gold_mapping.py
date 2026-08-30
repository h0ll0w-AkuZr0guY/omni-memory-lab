from datetime import UTC, datetime

import pytest

from omni_memory.evaluation.chunking import split_chapter
from omni_memory.evaluation.cutoff import NovelChapter
from omni_memory.evaluation.gold_mapping import map_source_span_to_chunks
from omni_memory.evaluation.metrics import temporal_leakage_rate
from omni_memory.schemas.evaluation import SourceSpan
from omni_memory.schemas.memory import CommittedFact
from omni_memory.schemas.query import RetrievedMemory

NOW = datetime.now(UTC)


def test_gold_span_maps_to_one_chunk():
    chapter = NovelChapter("ch-1", 1, "0123456789")
    chunks = split_chapter(chapter, max_chars=5)
    span = SourceSpan(
        document_id="ch-1",
        chapter_index=1,
        start_char=1,
        end_char=4,
    )

    mapping = map_source_span_to_chunks(span, chunks)

    assert mapping.chunk_ids == ("ch-1:chunk:0000",)
    assert mapping.episode_ids == ("episode:ch-1:chunk:0000",)


def test_gold_span_can_cross_chunk_boundary():
    chapter = NovelChapter("ch-1", 1, "0123456789")
    chunks = split_chapter(chapter, max_chars=5)
    span = SourceSpan(
        document_id="ch-1",
        chapter_index=1,
        start_char=3,
        end_char=8,
    )

    mapping = map_source_span_to_chunks(span, chunks)

    assert mapping.chunk_ids == (
        "ch-1:chunk:0000",
        "ch-1:chunk:0001",
    )


def test_gold_span_rejects_unmatched_document():
    chunks = split_chapter(NovelChapter("ch-1", 1, "原文"))
    span = SourceSpan(
        document_id="other",
        chapter_index=1,
        start_char=0,
        end_char=1,
    )

    with pytest.raises(ValueError, match="未匹配到 chunk"):
        map_source_span_to_chunks(span, chunks)


def test_temporal_leakage_rate_detects_future_chapter():
    def retrieved(memory_id: str, chapter_index: int) -> RetrievedMemory:
        return RetrievedMemory(
            memory=CommittedFact(
                memory_id=memory_id,
                source_episode_id="ep-1",
                statement="事实",
                evidence_quote="证据",
                ingested_at=NOW,
                confidence=0.9,
                metadata={"chapter_index": chapter_index},
            ),
            score=1.0,
        )

    result = temporal_leakage_rate(
        [retrieved("m-1", 2), retrieved("m-2", 5)],
        visible_until_chapter=3,
    )

    assert result == 0.5


def test_temporal_leakage_is_zero_for_empty_or_safe_results():
    assert temporal_leakage_rate([], visible_until_chapter=3) == 0.0
    assert (
        temporal_leakage_rate(
            [
                RetrievedMemory(
                    memory=CommittedFact(
                        memory_id="m-1",
                        source_episode_id="ep-1",
                        statement="事实",
                        evidence_quote="证据",
                        ingested_at=NOW,
                        confidence=0.9,
                        metadata={"chapter_index": 3},
                    ),
                    score=1.0,
                )
            ],
            visible_until_chapter=3,
        )
        == 0.0
    )
