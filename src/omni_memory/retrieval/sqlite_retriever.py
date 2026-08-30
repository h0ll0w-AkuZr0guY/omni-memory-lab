import re

from omni_memory.retrieval.protocol import MemoryRetriever
from omni_memory.schemas.query import RetrievedMemory
from omni_memory.stores.sqlite_store import SQLiteMemoryStore


def _terms(query: str) -> list[str]:
    normalized = query.strip()
    if not normalized:
        return []
    whitespace_terms = [term for term in re.split(r"\s+", normalized) if term]
    if len(whitespace_terms) > 1:
        return list(dict.fromkeys(whitespace_terms))
    if len(normalized) <= 2:
        return [normalized]
    bigrams = [normalized[index : index + 2] for index in range(len(normalized) - 1)]
    return list(dict.fromkeys([normalized, *bigrams]))


class SQLiteMemoryRetriever(MemoryRetriever):
    """第一版确定性检索基线；后续可替换为 BM25、向量或混合时序实现。"""

    def __init__(self, store: SQLiteMemoryStore):
        self.store = store

    def search(self, query: str, top_k: int = 5) -> list[RetrievedMemory]:
        if not query.strip():
            return []
        if top_k < 1:
            raise ValueError("top_k 必须大于 0")

        terms = _terms(query)
        results: list[RetrievedMemory] = []
        for memory in self.store.list_all():
            searchable = f"{memory.statement} {memory.evidence_quote}"
            matched = sum(term in searchable for term in terms)
            if matched == 0:
                continue
            exact_bonus = 1.0 if query.strip() in searchable else 0.0
            score = (matched / len(terms)) + exact_bonus
            results.append(RetrievedMemory(memory=memory, score=score))

        results.sort(key=lambda item: (-item.score, item.memory.memory_id))
        return results[:top_k]
