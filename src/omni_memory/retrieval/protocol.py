from typing import Protocol

from omni_memory.schemas.query import RetrievedMemory


class MemoryRetriever(Protocol):
    def search(self, query: str, top_k: int = 5) -> list[RetrievedMemory]:
        """根据 query 返回最多 top_k 条排序后的记忆。"""
        ...
