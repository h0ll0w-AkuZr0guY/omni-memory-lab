import pytest

from omni_memory.evaluation.cutoff import NovelChapter, apply_cutoff
from omni_memory.schemas.evaluation import CutoffPolicy

CHAPTERS = [
    NovelChapter("ch-1", 1, "第一章原文"),
    NovelChapter("ch-2", 2, "第二章原文"),
    NovelChapter("ch-3", 3, "第三章原文"),
    NovelChapter("ch-4", 4, "第四章原文"),
    NovelChapter("ch-5", 5, "第五章原文"),
]


def test_suffix_cutoff_returns_only_visible_prefix():
    result = apply_cutoff(
        CHAPTERS,
        CutoffPolicy(mask_strategy="suffix", visible_ratio=0.8),
    )

    assert [chapter.document_id for chapter in result.visible_chapters] == [
        "ch-1",
        "ch-2",
        "ch-3",
        "ch-4",
    ]
    assert result.heldout_document_ids == ("ch-5",)
    assert result.heldout_chapter_indices == (5,)
    assert not hasattr(result, "heldout_chapters")


def test_cutoff_is_order_independent():
    result = apply_cutoff(
        list(reversed(CHAPTERS)),
        CutoffPolicy(mask_strategy="suffix", visible_until_chapter=3),
    )

    assert [chapter.chapter_index for chapter in result.visible_chapters] == [1, 2, 3]
    assert result.heldout_chapter_indices == (4, 5)


def test_random_cutoff_is_reproducible_with_seed():
    policy = CutoffPolicy(
        mask_strategy="random_span",
        visible_ratio=0.8,
        mask_fraction=0.4,
        random_seed=42,
    )

    first = apply_cutoff(CHAPTERS, policy)
    second = apply_cutoff(CHAPTERS, policy)

    assert first == second
    assert len(first.heldout_chapter_indices) == 2
    assert set(first.heldout_chapter_indices).isdisjoint(
        chapter.chapter_index for chapter in first.visible_chapters
    )


def test_cutoff_rejects_duplicate_chapter_indices():
    duplicate = [*CHAPTERS, NovelChapter("ch-other", 3, "重复章节")]

    with pytest.raises(ValueError, match="chapter_index 必须唯一"):
        apply_cutoff(
            duplicate,
            CutoffPolicy(mask_strategy="suffix", visible_ratio=0.8),
        )
