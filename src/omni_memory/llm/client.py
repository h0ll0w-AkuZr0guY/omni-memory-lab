from langchain_openai import ChatOpenAI

from omni_memory.config.settings import Settings, get_settings


def build_chat_model(settings: Settings | None = None) -> ChatOpenAI:
    """构造 OpenAI-compatible ChatModel；调用 invoke/ainvoke 时才产生网络请求。"""

    config = settings or get_settings()
    return ChatOpenAI(
        api_key=config.api_key.get_secret_value(),
        base_url=config.base_url,
        model=config.model,
        temperature=0,
        timeout=config.request_timeout_s,
        max_retries=2,
    )


def get_chat_model() -> ChatOpenAI:
    """使用当前环境配置构造默认聊天模型。"""

    return build_chat_model()
