from datetime import datetime

from omni_memory.evaluation.chunking import TextChunk
from omni_memory.schemas.memory import Episode


def chunks_to_episodes(
    chunks: tuple[TextChunk, ...],
    *,
    ingested_at: datetime,
    source: str,
) -> tuple[Episode, ...]:
    """将带 offset 的 chunk 转成记忆系统的 Episode，并保留定位元数据。"""

    if not source:
        raise ValueError("source 不能为空")

    return tuple(
        Episode(
            episode_id=f"episode:{chunk.chunk_id}",
            text=chunk.text,
            ingested_at=ingested_at,
            source=source,
            metadata={
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "chapter_index": chunk.chapter_index,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
            },
        )
        for chunk in chunks
    )
