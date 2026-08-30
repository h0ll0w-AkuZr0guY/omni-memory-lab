from omni_memory.graphs.validation import validate_candidates
from omni_memory.schemas.memory import CommittedFact, Episode, FactCandidate, ValidationIssue


def commit_candidates(
    episode: Episode,
    candidates: list[FactCandidate],
) -> tuple[list[CommittedFact], list[ValidationIssue]]:
    """重新执行证据校验后提交；任何问题都会阻止本批次提交。"""

    valid, issues = validate_candidates(episode, candidates)
    if issues:
        return [], issues

    committed = [
        CommittedFact(
            memory_id=f"{episode.episode_id}:fact:{index:04d}",
            source_episode_id=episode.episode_id,
            kind=candidate.kind,
            statement=candidate.statement,
            evidence_quote=candidate.evidence_quote,
            ingested_at=episode.ingested_at,
            valid_at=candidate.valid_at,
            confidence=candidate.confidence,
            metadata=episode.metadata,
        )
        for index, candidate in enumerate(valid)
    ]
    return committed, []
