import pytest

from omni_memory.evaluation.chunking import split_chapter, split_chapters
from omni_memory.evaluation.cutoff import NovelChapter


def test_chunking_preserves_exact_text_and_offsets():
    chapter = NovelChapter("ch-1", 1, "0123456789")

    chunks = split_chapter(chapter, max_chars=4)

    assert [chunk.text for chunk in chunks] == ["0123", "4567", "89"]
    assert [(chunk.start_char, chunk.end_char) for chunk in chunks] == [
        (0, 4),
        (4, 8),
        (8, 10),
    ]
    assert all(
        chapter.text[chunk.start_char : chunk.end_char] == chunk.text
        for chunk in chunks
    )


def test_chunk_ids_are_stable_and_restart_per_chapter():
    chunks = split_chapters(
        (
            NovelChapter("ch-a", 1, "abcdef"),
            NovelChapter("ch-b", 2, "ghijkl"),
        ),
        max_chars=3,
    )

    assert [chunk.chunk_id for chunk in chunks] == [
        "ch-a:chunk:0000",
        "ch-a:chunk:0001",
        "ch-b:chunk:0000",
        "ch-b:chunk:0001",
    ]


def test_empty_chapter_produces_no_chunks():
    assert split_chapter(NovelChapter("empty", 0, "")) == ()


def test_chunking_rejects_non_positive_size():
    with pytest.raises(ValueError, match="max_chars 必须大于 0"):
        split_chapter(NovelChapter("ch-1", 1, "text"), max_chars=0)
