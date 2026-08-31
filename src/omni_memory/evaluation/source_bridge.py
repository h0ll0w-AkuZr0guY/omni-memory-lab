from omni_memory.evaluation.cutoff import NovelChapter
from omni_memory.evaluation.sources import ParsedChapter, SourceAsset
from omni_memory.schemas.asset import AssetRecord


def parsed_chapters_to_novel_chapters(
    chapters: tuple[ParsedChapter, ...],
    *,
    max_chapters: int | None = None,
) -> list[NovelChapter]:
    selected = chapters if max_chapters is None else chapters[:max_chapters]
    return [
        NovelChapter(
            document_id=chapter.document_id,
            chapter_index=chapter.chapter_index,
            text=chapter.text,
        )
        for chapter in selected
        if chapter.text.strip()
    ]


def assets_to_records(assets: tuple[SourceAsset, ...]) -> list[AssetRecord]:
    records: list[AssetRecord] = []
    for asset in assets:
        kind = "image" if asset.media_type.startswith("image/") else "document"
        records.append(
            AssetRecord(
                asset_id=asset.asset_id,
                source_path=asset.source_path,
                media_type=asset.media_type,
                kind=kind,
                size_bytes=asset.size_bytes,
            )
        )
    return records
