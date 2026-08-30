from omni_memory.evaluation.chunking import split_chapter
from omni_memory.evaluation.cutoff import NovelChapter, apply_cutoff
from omni_memory.evaluation.gold_mapping import map_source_span_to_chunks
from omni_memory.evaluation.ingest import chunks_to_episodes
from omni_memory.schemas.evaluation import CutoffPolicy, SourceSpan
from datetime import UTC, datetime

chapters = tuple(
    NovelChapter(f"chapter-{index}", index, f"第{index}章：人物在这一章发生了事件。")
    for index in range(1, 6)
)
cutoff = apply_cutoff(
    list(chapters),
    CutoffPolicy(mask_strategy="suffix", visible_ratio=0.8),
)
visible_chunks = tuple(
    chunk
    for chapter in cutoff.visible_chapters
    for chunk in split_chapter(chapter, max_chars=12)
)
episodes = chunks_to_episodes(
    visible_chunks,
    ingested_at=datetime.now(UTC),
    source="local-authorized-novel",
)
span = SourceSpan(
    document_id="chapter-2",
    chapter_index=2,
    start_char=0,
    end_char=8,
)
mapping = map_source_span_to_chunks(span, visible_chunks)
print("visible_chapters=", [chapter.chapter_index for chapter in cutoff.visible_chapters])
print("heldout_chapters=", cutoff.heldout_chapter_indices)
print("episode_count=", len(episodes))
print("gold_chunk_ids=", mapping.chunk_ids)
print("gold_episode_ids=", mapping.episode_ids)
