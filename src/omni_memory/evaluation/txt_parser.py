import re
from pathlib import Path

from omni_memory.evaluation.sources import ParsedChapter, ParsedSource

DEFAULT_TXT_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "big5")
DEFAULT_HEADING_PATTERN = re.compile(
    r"^\s*(?:(?:第[一二三四五六七八九十百千万0-9]+[章节卷部].{0,100})|"
    r"(?:序章|终章|尾声|后记|序言|前言).{0,100}|"
    r"(?:[0-9]{1,3})[ \t]+[^。！？!?]{1,80})\s*$"
)


def decode_text(path: Path, encodings=DEFAULT_TXT_ENCODINGS) -> tuple[str, str]:
    raw = path.read_bytes()
    for encoding in encodings:
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeError(f"无法解码文本文件：{path}")


def parse_txt(
    path: str | Path,
    *,
    heading_pattern: re.Pattern[str] = DEFAULT_HEADING_PATTERN,
) -> ParsedSource:
    source = Path(path)
    text, encoding = decode_text(source)
    lines = text.splitlines()
    headings: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        cleaned = line.strip()
        if cleaned and heading_pattern.match(cleaned):
            headings.append((index, cleaned))

    if not headings:
        # 没有可靠章节标题时保留整本书为一个可审计单元；后续可注入专用规则。
        chapters = (
            ParsedChapter(
                document_id=f"{source.stem}:chapter:0001",
                chapter_index=1,
                title=source.stem,
                text=text,
                source_format="txt",
                source_path=str(source),
            ),
        )
    else:
        chapters_list: list[ParsedChapter] = []
        preface_end = headings[0][0]
        if text_before := "\n".join(lines[:preface_end]).strip():
            chapters_list.append(
                ParsedChapter(
                    document_id=f"{source.stem}:preface:0000",
                    chapter_index=0,
                    title="preface",
                    text=text_before,
                    source_format="txt",
                    source_path=str(source),
                )
            )
        for ordinal, (line_index, title) in enumerate(headings, start=1):
            next_line = headings[ordinal][0] if ordinal < len(headings) else len(lines)
            chapter_text = "\n".join(lines[line_index:next_line]).strip()
            chapters_list.append(
                ParsedChapter(
                    document_id=f"{source.stem}:chapter:{ordinal:04d}",
                    chapter_index=ordinal,
                    title=title,
                    text=chapter_text,
                    source_format="txt",
                    source_path=str(source),
                )
            )
        chapters = tuple(chapters_list)

    return ParsedSource(
        source_path=str(source),
        source_format="txt",
        encoding=encoding,
        chapters=tuple(chapters),
        assets=(),
    )
