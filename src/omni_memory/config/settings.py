from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """通用 OpenAI-compatible 模型配置；敏感值只从环境变量或本地 .env 读取。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    api_key: SecretStr
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    request_timeout_s: float = 60.0

    langchain_tracing_v2: bool = False
    langchain_api_key: SecretStr | None = None
    langchain_project: str = "omni-memory-lab"


@lru_cache(maxsize=1 )
def get_settings() -> Settings:
    return Settings()
