from pathlib import Path

from omni_memory.evaluation.epub_parser import parse_epub
from omni_memory.evaluation.sources import ParsedSource
from omni_memory.evaluation.txt_parser import parse_txt


def parse_source(path: str | Path) -> ParsedSource:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".txt":
        return parse_txt(source)
    if suffix == ".epub":
        return parse_epub(source)
    raise ValueError(f"不支持的文件类型：{source.suffix}")
