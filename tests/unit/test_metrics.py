from datetime import UTC, datetime

import pytest

from omni_memory.evaluation.metrics import answer_metrics, retrieval_metrics
from omni_memory.schemas.memory import CommittedFact
from omni_memory.schemas.query import GroundedAnswer, RetrievedMemory

NOW = datetime.now(UTC)


def retrieved(memory_id: str, score: float) -> RetrievedMemory:
    return RetrievedMemory(
        memory=CommittedFact(
            memory_id=memory_id,
            source_episode_id="ep-metric",
            statement=f"事实 {memory_id}",
            evidence_quote=f"证据 {memory_id}",
            ingested_at=NOW,
            confidence=0.9,
        ),
        score=score,
    )


def test_retrieval_metrics_calculate_recall_precision_and_mrr():
    result = retrieval_metrics(
        [retrieved("m-1", 2.0), retrieved("noise", 1.0), retrieved("m-2", 0.5)],
        {"m-1", "m-2"},
        k=3,
    )

    assert result.recall_at_k == 1.0
    assert result.precision_at_k == pytest.approx(2 / 3)
    assert result.mrr == 1.0


def test_retrieval_metrics_respects_k():
    result = retrieval_metrics(
        [retrieved("noise", 2.0), retrieved("m-1", 1.0)],
        {"m-1"},
        k=1,
    )

    assert result.recall_at_k == 0.0
    assert result.precision_at_k == 0.0
    assert result.mrr == 0.0


def test_answer_metrics_calculate_citation_quality():
    result = answer_metrics(
        GroundedAnswer(
            answer="回答",
            citation_memory_ids=["m-1", "noise"],
            grounded=True,
            abstain=False,
        ),
        {"m-1"},
        gold_answerable=True,
    )

    assert result.citation_precision == 0.5
    assert result.citation_recall == 1.0
    assert result.abstention_correct is True


def test_answer_metrics_evaluates_unanswerable_case():
    result = answer_metrics(
        GroundedAnswer(
            answer="没有足够证据",
            citation_memory_ids=[],
            grounded=False,
            abstain=True,
        ),
        set(),
        gold_answerable=False,
    )

    assert result.citation_precision == 0.0
    assert result.citation_recall == 0.0
    assert result.abstention_correct is True


def test_metrics_reject_invalid_k():
    with pytest.raises(ValueError, match="k 必须大于 0"):
        retrieval_metrics([], {"m-1"}, k=0)
