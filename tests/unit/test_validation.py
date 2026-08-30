from datetime import UTC, datetime

from omni_memory.graphs.validation import validate_candidates
from omni_memory.schemas.memory import Episode, FactCandidate

NOW = datetime.now(UTC)


def make_episode() -> Episode:
    return Episode(
        episode_id="ep-1",
        text="林舟在冬至回到故乡，并把旧相机放在窗台上。",
        ingested_at=NOW,
        source="neuro-book-test",
    )


def test_validate_candidates_keeps_exact_evidence():
    candidates = [
        FactCandidate(
            statement="林舟在冬至回到故乡",
            evidence_quote="林舟在冬至回到故乡",
            confidence=0.95,
        )
    ]

    valid, issues = validate_candidates(make_episode(), candidates)

    assert len(valid) == 1
    assert issues == []


def test_validate_candidates_rejects_hallucinated_evidence():
    candidates = [
        FactCandidate(
            statement="林舟在冬至回到上海",
            evidence_quote="林舟在冬至回到上海",
            confidence=0.90,
        )
    ]

    valid, issues = validate_candidates(make_episode(), candidates)

    assert valid == []
    assert len(issues) == 1
    assert issues[0].code == "quote_not_found"
    assert issues[0].candidate_index == 0


def test_validate_candidates_handles_mixed_results():
    candidates = [
        FactCandidate(
            statement="旧相机在窗台上",
            evidence_quote="旧相机放在窗台上",
            confidence=0.88,
        ),
        FactCandidate(
            statement="林舟去了国外",
            evidence_quote="林舟去了国外",
            confidence=0.70,
        ),
    ]

    valid, issues = validate_candidates(make_episode(), candidates)

    assert len(valid) == 1
    assert valid[0].statement == "旧相机在窗台上"
    assert len(issues) == 1
    assert issues[0].code == "quote_not_found"
