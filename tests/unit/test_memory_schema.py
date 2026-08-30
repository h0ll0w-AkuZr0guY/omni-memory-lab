from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from omni_memory.schemas.memory import Episode, FactCandidate


def test_episode_requires_non_empty_source_text():
    episode = Episode(
        episode_id="ep-1",
        text="主角在冬至回到故乡。",
        ingested_at=datetime.now(UTC),
        source="test",
    )

    assert episode.episode_id == "ep-1"
    assert episode.valid_at is None


def test_fact_candidate_rejects_invalid_confidence():
    with pytest.raises(ValidationError):
        FactCandidate(
            statement="一个事实",
            evidence_quote="一个事实",
            confidence=1.5,
        )


def test_schema_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        Episode(
            episode_id="ep-1",
            text="原文",
            ingested_at=datetime.now(UTC),
            source="test",
            accidental_field="should-fail",
        )
