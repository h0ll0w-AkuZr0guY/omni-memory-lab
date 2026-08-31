
import pytest
from langchain_core.messages import AIMessage

from omni_memory.llm.observability import invoke_with_observation
from omni_memory.stores.platform_store import PlatformStore


class SuccessfulInvoker:
    def invoke(self, payload):
        return AIMessage(
            content="模型连接成功",
            response_metadata={
                "token_usage": {"prompt_tokens": 10, "completion_tokens": 3},
                "request_id": "provider-123",
            },
        )


class FailedInvoker:
    def invoke(self, payload):
        raise TimeoutError("provider timeout")


def test_successful_call_is_recorded_without_prompt_text(tmp_path, monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.setenv("BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("MODEL", "test-model")
    from omni_memory.config.settings import get_settings

    get_settings.cache_clear()
    with PlatformStore(tmp_path / "calls.sqlite3") as store:
        result = invoke_with_observation(
            SuccessfulInvoker(),
            "secret novel text that must not be persisted",
            operation="unit_test",
            store=store,
            run_id="run-1",
        )
        calls = store.list_model_calls("run-1")

    assert result.content == "模型连接成功"
    assert len(calls) == 1
    assert calls[0].success is True
    assert calls[0].usage_available is True
    assert calls[0].provider_request_id == "provider-123"
    assert calls[0].provider_host == "example.com"
    assert "secret novel" not in calls[0].model_dump_json()


def test_failed_call_is_recorded_and_reraised(tmp_path):
    with PlatformStore(tmp_path / "calls.sqlite3") as store:
        with pytest.raises(TimeoutError, match="provider timeout"):
            invoke_with_observation(
                FailedInvoker(),
                "payload",
                operation="unit_failure",
                store=store,
            )
        calls = store.list_model_calls()

    assert len(calls) == 1
    assert calls[0].success is False
    assert calls[0].error_type == "TimeoutError"
