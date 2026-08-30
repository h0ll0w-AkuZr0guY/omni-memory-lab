from datetime import UTC, datetime

from omni_memory.schemas.memory import Episode, FactCandidate
from omni_memory.stores.commit import commit_candidates

NOW = datetime.now(UTC)


def make_episode() -> Episode:
    return Episode(
        episode_id="ep-commit-1",
        text="沈砚把蓝色笔记本放回抽屉。",
        ingested_at=NOW,
        source="commit-test",
    )


def test_commit_adds_traceability_fields():
    candidate = FactCandidate(
        statement="沈砚收起了笔记本",
        evidence_quote="沈砚把蓝色笔记本放回抽屉",
        confidence=0.93,
    )

    committed, issues = commit_candidates(make_episode(), [candidate])

    assert issues == []
    assert len(committed) == 1
    assert committed[0].memory_id == "ep-commit-1:fact:0000"
    assert committed[0].source_episode_id == "ep-commit-1"
    assert committed[0].evidence_quote in make_episode().text
    assert committed[0].status == "committed"


def test_commit_is_atomic_when_any_candidate_is_invalid():
    candidates = [
        FactCandidate(
            statement="沈砚收起了笔记本",
            evidence_quote="沈砚把蓝色笔记本放回抽屉",
            confidence=0.93,
        ),
        FactCandidate(
            statement="沈砚去了北京",
            evidence_quote="沈砚去了北京",
            confidence=0.99,
        ),
    ]

    committed, issues = commit_candidates(make_episode(), candidates)

    assert committed == []
    assert len(issues) == 1
    assert issues[0].code == "quote_not_found"


def test_commit_empty_candidates_is_valid_noop():
    committed, issues = commit_candidates(make_episode(), [])

    assert committed == []
    assert issues == []
