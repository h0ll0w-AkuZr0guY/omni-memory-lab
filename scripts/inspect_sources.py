import hashlib
import json
import re
import zipfile
from pathlib import Path

RAW_DIR = Path("data/raw")
TXT_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "big5")
CHAPTER_PATTERN = re.compile(
    r"(?m)^(?:第[一二三四五六七八九十百千万0-9]+[章节卷部]|序章|终章|尾声|后记|Prologue|Epilogue)"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_txt(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    decoded = None
    used_encoding = None
    for encoding in TXT_ENCODINGS:
        try:
            decoded = raw.decode(encoding)
            used_encoding = encoding
            break
        except UnicodeDecodeError:
            continue
    if decoded is None:
        return {"error": "无法使用候选编码解码"}

    headings = CHAPTER_PATTERN.findall(decoded)
    paragraphs = [item for item in re.split(r"\n\s*\n", decoded) if item.strip()]
    return {
        "format": "txt",
        "encoding": used_encoding,
        "characters": len(decoded),
        "chapter_heading_candidates": len(headings),
        "paragraph_candidates": len(paragraphs),
        "first_headings": headings[:10],
    }


def inspect_epub(path: Path) -> dict[str, object]:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        image_names = [
            name
            for name in names
            if name.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"))
        ]
        document_names = [
            name
            for name in names
            if name.lower().endswith((".xhtml", ".html", ".htm"))
        ]
        opf_names = [name for name in names if name.lower().endswith(".opf")]
        return {
            "format": "epub",
            "zip_entries": len(names),
            "document_entries": len(document_names),
            "image_entries": len(image_names),
            "opf_entries": len(opf_names),
            "first_documents": document_names[:10],
            "first_images": image_names[:10],
        }


def inspect(path: Path) -> dict[str, object]:
    result: dict[str, object] = {
        "filename": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }
    if path.suffix.lower() == ".txt":
        result.update(inspect_txt(path))
    elif path.suffix.lower() == ".epub":
        result.update(inspect_epub(path))
    else:
        result["format"] = "unsupported"
    return result


def main() -> None:
    if not RAW_DIR.exists():
        raise SystemExit(f"目录不存在：{RAW_DIR.resolve()}")
    paths = sorted(
        path for path in RAW_DIR.iterdir() if path.suffix.lower() in {".txt", ".epub"}
    )
    if not paths:
        raise SystemExit(f"未找到 TXT/EPUB：{RAW_DIR.resolve()}")
    report = {"raw_dir": str(RAW_DIR.resolve()), "files": [inspect(path) for path in paths]}
    output = Path("artifacts/source-inventory.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nmetadata_report={output}")


if __name__ == "__main__":
    main()
