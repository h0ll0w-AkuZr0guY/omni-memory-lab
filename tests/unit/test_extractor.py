from datetime import UTC, datetime
from typing import Any

from omni_memory.llm.extractor import extract_fact_candidates
from omni_memory.schemas.extraction import FactExtraction
from omni_memory.schemas.memory import Episode, FactCandidate


class StubStructuredModel:
    def __init__(self) -> None:
        self.messages: list[Any] | None = None

    def invoke(self, messages: list[Any]) -> FactExtraction:
        self.messages = messages
        return FactExtraction(
            facts=[
                FactCandidate(
                    statement="沈砚关掉了灯",
                    evidence_quote="沈砚在凌晨三点关掉了灯。",
                    confidence=0.96,
                )
            ]
        )


class StubChatModel:
    def __init__(self) -> None:
        self.structured = StubStructuredModel()
        self.schema: type[FactExtraction] | None = None
        self.method: str | None = None

    def with_structured_output(
        self,
        schema: type[FactExtraction],
        *,
        method: str,
    ) -> StubStructuredModel:
        self.schema = schema
        self.method = method
        return self.structured


def test_extractor_uses_injected_structured_model():
    episode = Episode(
        episode_id="ep-1",
        text="沈砚在凌晨三点关掉了灯。",
        ingested_at=datetime.now(UTC),
        source="novel-test",
    )
    model = StubChatModel()

    extraction = extract_fact_candidates(episode, model=model)

    assert model.schema is FactExtraction
    assert model.method == "json_mode"
    assert len(extraction.facts) == 1
    assert extraction.facts[0].evidence_quote in episode.text
    assert "沈砚在凌晨三点关掉了灯。" in str(model.structured.messages)
