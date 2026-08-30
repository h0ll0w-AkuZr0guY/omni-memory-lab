from pydantic import SecretStr

from omni_memory.config.settings import Settings
from omni_memory.llm.client import build_chat_model


def test_build_chat_model_uses_generic_openai_compatible_config():
    settings = Settings(
        api_key=SecretStr("test-key-not-real"),
        base_url="https://example.com/v1",
        model="test-model",
     )

    model = build_chat_model(settings)

    assert model.model_name == "test-model"
    assert model.openai_api_base == "https://example.com/v1"
    assert model.openai_api_key.get_secret_value() == "test-key-not-real"

