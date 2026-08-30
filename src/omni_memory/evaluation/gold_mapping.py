from dataclasses import dataclass

from omni_memory.evaluation.chunking import TextChunk
from omni_memory.schemas.evaluation import SourceSpan


@dataclass(frozen=True)
class GoldSpanMapping:
    source_span: SourceSpan
    chunk_ids: tuple[str, ...]
    episode_ids: tuple[str, ...]


def map_source_span_to_chunks(
    span: SourceSpan,
    chunks: tuple[TextChunk, ...],
) -> GoldSpanMapping:
    """将 gold span 映射到重叠的 chunk；跨 chunk 的 span 会返回多个结果。"""

    matched: list[TextChunk] = []
    for chunk in chunks:
        if chunk.document_id != span.document_id:
            continue
        if chunk.chapter_index != span.chapter_index:
            continue
        overlaps = chunk.start_char < span.end_char and span.start_char < chunk.end_char
        if overlaps:
            matched.append(chunk)

    if not matched:
        raise ValueError(
            f"source span 未匹配到 chunk: {span.document_id}:{span.start_char}-{span.end_char}"
        )

    matched.sort(key=lambda chunk: (chunk.start_char, chunk.chunk_id))
    return GoldSpanMapping(
        source_span=span,
        chunk_ids=tuple(chunk.chunk_id for chunk in matched),
        episode_ids=tuple(f"episode:{chunk.chunk_id}" for chunk in matched),
    )
