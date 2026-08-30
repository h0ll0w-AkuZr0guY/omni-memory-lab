from dataclasses import dataclass

from omni_memory.evaluation.cutoff import NovelChapter


@dataclass(frozen=True)
class TextChunk:
    """保留原文字符 offset 的可检索文本块；区间为 [start_char, end_char)。"""

    chunk_id: str
    document_id: str
    chapter_index: int
    start_char: int
    end_char: int
    text: str


def split_chapter(chapter: NovelChapter, max_chars: int = 800) -> tuple[TextChunk, ...]:
    """以确定性定长方式切分章节，并保留原始字符 offset。"""

    if max_chars <= 0:
        raise ValueError("max_chars 必须大于 0")
    if not chapter.text:
        return ()

    chunks: list[TextChunk] = []
    for index, start in enumerate(range(0, len(chapter.text), max_chars)):
        end = min(start + max_chars, len(chapter.text))
        chunks.append(
            TextChunk(
                chunk_id=f"{chapter.document_id}:chunk:{index:04d}",
                document_id=chapter.document_id,
                chapter_index=chapter.chapter_index,
                start_char=start,
                end_char=end,
                text=chapter.text[start:end],
            )
        )
    return tuple(chunks)


def split_chapters(
    chapters: tuple[NovelChapter, ...],
    max_chars: int = 800,
) -> tuple[TextChunk, ...]:
    """按输入顺序切分多个章节；每章独立编号。"""

    chunks: list[TextChunk] = []
    for chapter in chapters:
        chunks.extend(split_chapter(chapter, max_chars=max_chars))
    return tuple(chunks)
