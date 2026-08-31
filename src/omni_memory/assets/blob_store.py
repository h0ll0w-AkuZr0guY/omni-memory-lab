import hashlib
from pathlib import Path
from typing import BinaryIO


class LocalBlobStore:
    """本地内容寻址 blob store；数据库只保存 manifest，不保存二进制本体。"""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put_stream(self, stream: BinaryIO, filename: str) -> tuple[str, str, int]:
        digest = hashlib.sha256()
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            chunks.append(chunk)
            total += len(chunk)
        sha256 = digest.hexdigest()
        suffix = Path(filename).suffix.lower()
        target = self.root / sha256[:2] / f"{sha256}{suffix}"
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            with target.open("wb") as file:
                for chunk in chunks:
                    file.write(chunk)
        return sha256, target.as_uri(), total

    def path_for(self, sha256: str, suffix: str = "") -> Path:
        matches = list((self.root / sha256[:2]).glob(f"{sha256}*"))
        if matches:
            return matches[0]
        return self.root / sha256[:2] / f"{sha256}{suffix}"
