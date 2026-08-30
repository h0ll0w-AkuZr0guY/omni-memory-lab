from datetime import UTC, datetime

import pytest

from omni_memory.evaluation.chunking import split_chapter
from omni_memory.evaluation.cutoff import NovelChapter
from omni_memory.evaluation.ingest import chunks_to_episodes

NOW = datetime.now(UTC)


def test_chunks_convert_to_traceable_episodes():
    chunks = split_chapter(
        NovelChapter("chapter-07", 7, "顾言推开门。雨停了。"),
        max_chars=5,
    )

    episodes = chunks_to_episodes(
        chunks,
        ingested_at=NOW,
        source="novel-test",
    )

    assert len(episodes) == 2
    assert episodes[0].episode_id == "episode:chapter-07:chunk:0000"
    assert episodes[0].text == "顾言推开门"
    assert episodes[0].metadata["chapter_index"] == 7
    assert episodes[0].metadata["start_char"] == 0
    assert episodes[0].metadata["end_char"] == 5
    assert episodes[1].metadata["start_char"] == 5


def test_ingest_preserves_timestamp_and_source():
    chunks = split_chapter(NovelChapter("ch-1", 1, "原文"))

    episodes = chunks_to_episodes(
        chunks,
        ingested_at=NOW,
        source="licensed-novel-v1",
    )

    assert episodes[0].ingested_at == NOW
    assert episodes[0].source == "licensed-novel-v1"


def test_ingest_rejects_empty_source():
    chunks = split_chapter(NovelChapter("ch-1", 1, "原文"))

    with pytest.raises(ValueError, match="source 不能为空"):
        chunks_to_episodes(chunks, ingested_at=NOW, source="")

