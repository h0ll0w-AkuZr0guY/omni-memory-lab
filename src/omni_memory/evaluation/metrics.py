from dataclasses import dataclass

from omni_memory.schemas.query import GroundedAnswer, RetrievedMemory


@dataclass(frozen=True)
class RetrievalMetrics:
    recall_at_k: float
    precision_at_k: float
    mrr: float


@dataclass(frozen=True)
class AnswerMetrics:
    citation_precision: float
    citation_recall: float
    abstention_correct: bool


def retrieval_metrics(
    retrieved: list[RetrievedMemory],
    gold_memory_ids: set[str],
    *,
    k: int,
) -> RetrievalMetrics:
    """计算单个 query 的 Recall@k、Precision@k 和 MRR。"""

    if k < 1:
        raise ValueError("k 必须大于 0")
    top = retrieved[:k]
    retrieved_ids = [item.memory.memory_id for item in top]
    hits = sum(memory_id in gold_memory_ids for memory_id in retrieved_ids)

    recall = hits / len(gold_memory_ids) if gold_memory_ids else 0.0
    precision = hits / len(retrieved_ids) if retrieved_ids else 0.0
    reciprocal_rank = 0.0
    for rank, memory_id in enumerate(retrieved_ids, start=1):
        if memory_id in gold_memory_ids:
            reciprocal_rank = 1.0 / rank
            break

    return RetrievalMetrics(
        recall_at_k=recall,
        precision_at_k=precision,
        mrr=reciprocal_rank,
    )


def answer_metrics(
    answer: GroundedAnswer,
    gold_memory_ids: set[str],
    *,
    gold_answerable: bool,
) -> AnswerMetrics:
    """计算引用精度/召回和 abstention 是否正确。"""

    cited = set(answer.citation_memory_ids)
    correct_citations = cited & gold_memory_ids
    citation_precision = len(correct_citations) / len(cited) if cited else 0.0
    citation_recall = (
        len(correct_citations) / len(gold_memory_ids) if gold_memory_ids else 0.0
    )
    abstention_correct = answer.abstain is (not gold_answerable)

    return AnswerMetrics(
        citation_precision=citation_precision,
        citation_recall=citation_recall,
        abstention_correct=abstention_correct,
    )

from omni_memory.schemas.query import RetrievedMemory


def temporal_leakage_rate(
    retrieved: list[RetrievedMemory],
    *,
    visible_until_chapter: int,
) -> float:
    """计算检索结果中来自 cutoff 之后章节的比例。"""

    if not retrieved:
        return 0.0

    leaked = 0
    for item in retrieved:
        chapter_index = item.memory.metadata.get("chapter_index")
        if isinstance(chapter_index, int) and chapter_index > visible_until_chapter:
            leaked += 1

    return leaked / len(retrieved)
