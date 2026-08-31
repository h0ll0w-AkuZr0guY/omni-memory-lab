import hashlib
import json
import sys
from pathlib import Path

from omni_memory.evaluation.source_parser import parse_source


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("用法：python scripts/parse_sources.py data/raw/文件名")
    path = Path(sys.argv[1])
    parsed = parse_source(path)
    report = {
        "filename": path.name,
        "sha256": sha256(path),
        "format": parsed.source_format,
        "encoding": parsed.encoding,
        "chapter_count": len(parsed.chapters),
        "chapters": [
            {
                "document_id": chapter.document_id,
                "chapter_index": chapter.chapter_index,
                "title": chapter.title,
                "characters": len(chapter.text),
            }
            for chapter in parsed.chapters
        ],
        "asset_count": len(parsed.assets),
        "assets": [
            {
                "asset_id": asset.asset_id,
                "source_path": asset.source_path,
                "media_type": asset.media_type,
                "size_bytes": asset.size_bytes,
            }
            for asset in parsed.assets
        ],
    }
    output = Path("artifacts") / f"{path.stem}-source-manifest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"manifest={output}")


if __name__ == "__main__":
    main()
