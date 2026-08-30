from omni_memory.config.settings import get_settings


def test_settings_loads_openai_compatible_config(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("API_KEY", "test-key-not-real")
    monkeypatch.setenv("BASE_URL", "https://example.com/v1" )
    monkeypatch.setenv("MODEL", "test-model")

    settings = get_settings()

    assert settings.api_key.get_secret_value() == "test-key-not-real"
    assert settings.model == "test-model"
    assert settings.base_url == "https://example.com/v1"
