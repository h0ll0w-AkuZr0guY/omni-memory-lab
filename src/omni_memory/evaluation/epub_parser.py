import posixpath
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser
from pathlib import Path

from omni_memory.evaluation.sources import ParsedChapter, ParsedSource, SourceAsset

FRONT_MATTER_STEMS = {"coverpage", "cover", "title", "message", "summary", "toc", "copyright"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.image_hrefs: list[str] = []

    def handle_data(self, data: str) -> None:
        value = data.strip()
        if value:
            self.parts.append(value)

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() == "img":
            attributes = dict(attrs)
            if href := attributes.get("src"):
                self.image_hrefs.append(href)

    def text(self) -> str:
        return "\n".join(self.parts)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _resolve_zip_path(base: str, href: str) -> str:
    return posixpath.normpath(posixpath.join(posixpath.dirname(base), href.split("#", 1)[0]))


def parse_epub(path: str | Path) -> ParsedSource:
    source = Path(path)
    with zipfile.ZipFile(source) as archive:
        names = set(archive.namelist())
        container = ET.fromstring(archive.read("META-INF/container.xml"))
        rootfile = next(
            element for element in container.iter() if _local_name(element.tag) == "rootfile"
        )
        opf_path = rootfile.attrib["full-path"]
        opf = ET.fromstring(archive.read(opf_path))

        manifest: dict[str, str] = {}
        media_types: dict[str, str] = {}
        for element in opf.iter():
            if _local_name(element.tag) == "item":
                item_id = element.attrib["id"]
                href = _resolve_zip_path(opf_path, element.attrib["href"])
                manifest[item_id] = href
                media_types[href] = element.attrib.get("media-type", "")

        spine_ids = [
            element.attrib["idref"]
            for element in opf.iter()
            if _local_name(element.tag) == "itemref"
        ]
        document_paths = [manifest[item_id] for item_id in spine_ids if item_id in manifest]
        chapters: list[ParsedChapter] = []
        assets: list[SourceAsset] = []
        seen_asset_paths: set[str] = set()
        content_documents = [
            document_path
            for document_path in document_paths
            if Path(document_path).stem.lower() not in FRONT_MATTER_STEMS
        ]
        for index, document_path in enumerate(content_documents, start=1):
            if document_path not in names:
                continue
            extractor = _TextExtractor()
            extractor.feed(archive.read(document_path).decode("utf-8", errors="replace"))
            text = extractor.text()
            if text:
                chapters.append(
                    ParsedChapter(
                        document_id=f"{source.stem}:chapter:{index:04d}",
                        chapter_index=index,
                        title=f"chapter-{index}",
                        text=text,
                        source_format="epub",
                        source_path=str(source),
                    )
                )
            for href in extractor.image_hrefs:
                image_path = _resolve_zip_path(document_path, href)
                if image_path in names:
                    media_type = media_types.get(image_path, "application/octet-stream")
                    assets.append(
                        SourceAsset(
                            asset_id=f"{source.stem}:asset:{image_path}",
                            source_path=image_path,
                            media_type=media_type,
                            size_bytes=archive.getinfo(image_path).file_size,
                        )
                    )
                    if image_path in seen_asset_paths:
                        continue
                    seen_asset_paths.add(image_path)

        # 记录 archive 中所有图片，而不仅是正文中已被 img 标签引用的图片，
        # 因为封面/插图可能由 CSS 或 metadata 引用。
        referenced = {asset.source_path for asset in assets}
        for name in sorted(names):
            media_type = media_types.get(name, "")
            if name in referenced or not media_type.startswith("image/"):
                continue
            seen_asset_paths.add(name)
            assets.append(
                SourceAsset(
                    asset_id=f"{source.stem}:asset:{name}",
                    source_path=name,
                    media_type=media_type,
                    size_bytes=archive.getinfo(name).file_size,
                )
            )

    return ParsedSource(
        source_path=str(source),
        source_format="epub",
        encoding="utf-8",
        chapters=tuple(chapters),
        assets=tuple(assets),
    )
