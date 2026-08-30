from omni_memory.schemas.memory import Episode, FactCandidate, ValidationIssue


def validate_candidates(
    episode: Episode,
    candidates: list[FactCandidate],
) -> tuple[list[FactCandidate], list[ValidationIssue]]:
    """只保留能回指当前原文的候选记忆。"""

    valid: list[FactCandidate] = []
    issues: list[ValidationIssue] = []

    for index, candidate in enumerate(candidates):
        if not candidate.evidence_quote:
            issues.append(
                ValidationIssue(
                    code="empty_quote",
                    message="候选记忆缺少证据引用。",
                    candidate_index=index,
                )
            )
            continue

        if candidate.evidence_quote not in episode.text:
            issues.append(
                ValidationIssue(
                    code="quote_not_found",
                    message="证据引用不是当前 Episode 原文的精确子串。",
                    candidate_index=index,
                )
            )
            continue

        valid.append(candidate)

    return valid, issues
