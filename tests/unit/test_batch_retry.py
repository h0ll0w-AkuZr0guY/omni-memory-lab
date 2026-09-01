from datetime import UTC, datetime

from omni_memory.llm.batch_extractor import extract_batch
from omni_memory.schemas.batch_extraction import BatchFactCandidate, BatchFactExtraction
from omni_memory.schemas.memory import Episode
from omni_memory.stores.platform_store import PlatformStore


class RetryStructuredModel:
    def __init__(self):
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        if self.calls == 1:
            raise TimeoutError("temporary timeout")
        return BatchFactExtraction(
            facts=[
                BatchFactCandidate(
                    episode_id="ep-1",
                    statement="顾言修好了收音机",
                    evidence_quote="顾言在雨夜修好了收音机。",
                    confidence=0.95,
                )
            ]
        )


class RetryChatModel:
    def __init__(self):
        self.structured = RetryStructuredModel()
        self.model_name = "test-model"
        self.openai_api_base = "https://example.com/v1"

    def with_structured_output(self, schema, *, method):
        return self.structured


def test_batch_retry_records_each_attempt(tmp_path):
    episode = Episode(
        episode_id="ep-1",
        text="顾言在雨夜修好了收音机。",
        ingested_at=datetime.now(UTC),
        source="test",
    )
    database = tmp_path / "retry.sqlite3"
    model = RetryChatModel()

    with PlatformStore(database) as store:
        grouped = extract_batch(
            [episode],
            model=model,
            call_store=store,
            run_id="run-retry-1",
            max_attempts=2,
            retry_backoff_s=0,
        )
        calls = store.list_model_calls("run-retry-1")

    assert len(grouped["ep-1"]) == 1
    assert model.structured.calls == 2
    assert len(calls) == 2
    assert [call.success for call in calls] == [False, True]
    assert calls[0].error_type == "TimeoutError"
    assert calls[1].model == "test-model"
    assert calls[1].provider_host == "example.com"
