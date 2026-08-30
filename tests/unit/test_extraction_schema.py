from datetime import UTC, datetime

from omni_memory.llm.prompts import build_extraction_user_prompt
from omni_memory.schemas.extraction import FactExtraction
from omni_memory.schemas.memory import Episode


def test_fact_extraction_defaults_to_empty_collection():
    extraction = FactExtraction(facts=[])

    assert extraction.facts == []


def test_extraction_prompt_contains_only_episode_context():
    episode = Episode(
        episode_id="ep-1",
        text="沈砚在凌晨三点关掉了灯。",
        ingested_at=datetime.now(UTC),
        source="novel-test",
    )

    prompt = build_extraction_user_prompt(episode)

    assert "ep-1" in prompt
    assert "沈砚在凌晨三点关掉了灯。" in prompt
    assert "episode_text:" in prompt
