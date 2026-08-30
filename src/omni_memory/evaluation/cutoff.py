import random
from dataclasses import dataclass

from omni_memory.schemas.evaluation import CutoffPolicy


@dataclass(frozen=True)
class NovelChapter:
    """小说章节的最小输入协议；原文只应来自本地或获授权数据。"""

    document_id: str
    chapter_index: int
    text: str


@dataclass(frozen=True)
class CutoffResult:
    """cutoff 后交给被测系统的内容和不泄漏原文的 holdout 元数据。"""

    visible_chapters: tuple[NovelChapter, ...]
    heldout_document_ids: tuple[str, ...]
    heldout_chapter_indices: tuple[int, ...]


def apply_cutoff(
    chapters: list[NovelChapter],
    policy: CutoffPolicy,
) -> CutoffResult:
    """按固定策略切分章节；隐藏内容不会出现在返回值中。"""

    if not chapters:
        raise ValueError("chapters 不能为空")

    ordered = sorted(chapters, key=lambda chapter: chapter.chapter_index)
    indices = [chapter.chapter_index for chapter in ordered]
    if len(set(indices)) != len(indices):
        raise ValueError("chapter_index 必须唯一")

    if policy.visible_until_chapter is not None:
        visible = [
            chapter
            for chapter in ordered
            if chapter.chapter_index <= policy.visible_until_chapter
        ]
    elif policy.visible_ratio is not None:
        visible_count = max(1, int(len(ordered) * policy.visible_ratio))
        visible = ordered[:visible_count]
    else:
        raise ValueError("policy 缺少可见边界")

    if policy.mask_strategy == "random_span":
        rng = random.Random(policy.random_seed)
        holdout_count = max(1, int(len(ordered) * policy.mask_fraction))
        holdout = set(rng.sample(indices, k=min(holdout_count, len(indices))))
        visible = [chapter for chapter in ordered if chapter.chapter_index not in holdout]
    else:
        visible_ids = {chapter.document_id for chapter in visible}
        holdout = {
            chapter.chapter_index
            for chapter in ordered
            if chapter.document_id not in visible_ids
        }

    visible_ids = {chapter.document_id for chapter in visible}
    heldout = [chapter for chapter in ordered if chapter.document_id not in visible_ids]

    return CutoffResult(
        visible_chapters=tuple(visible),
        heldout_document_ids=tuple(chapter.document_id for chapter in heldout),
        heldout_chapter_indices=tuple(chapter.chapter_index for chapter in heldout),
    )
