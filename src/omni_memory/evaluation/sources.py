from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedChapter:
    document_id: str
    chapter_index: int
    title: str
    text: str
    source_format: str
    source_path: str


@dataclass(frozen=True)
class SourceAsset:
    asset_id: str
    source_path: str
    media_type: str
    size_bytes: int


@dataclass(frozen=True)
class ParsedSource:
    source_path: str
    source_format: str
    encoding: str | None
    chapters: tuple[ParsedChapter, ...]
    assets: tuple[SourceAsset, ...]
