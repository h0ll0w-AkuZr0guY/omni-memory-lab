import json
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from omni_memory.config.settings import get_settings
from omni_memory.schemas.platform import ModelCallRecord
from omni_memory.stores.platform_store import PlatformStore


def _text_size(value: Any) -> int:
    if isinstance(value, str):
        return len(value)
    try:
        return len(json.dumps(value, ensure_ascii=False, default=str))
    except TypeError:
        return len(str(value))


def _response_text(result: Any) -> str:
    content = getattr(result, "content", None)
    if isinstance(content, str):
        return content
    if content is not None:
        return str(content)
    return str(result)


def _response_metadata(result: Any) -> dict[str, Any]:
    metadata = getattr(result, "response_metadata", None)
    if isinstance(metadata, dict):
        return metadata
    return {}


def invoke_with_observation(
    invoker: Any,
    payload: Any,
    *,
    operation: str,
    store: PlatformStore | None = None,
    run_id: str | None = None,
) -> Any:
    """调用 LangChain Runnable 并可选写入脱敏 model-call 记录。"""
    settings = get_settings()
    call_id = f"call_{uuid4().hex}"
    started_at = datetime.now(UTC)
    try:
        result = invoker.invoke(payload)
        finished_at = datetime.now(UTC)
        metadata = _response_metadata(result)
        usage = metadata.get("token_usage") or metadata.get("usage_metadata") or {}
        provider_request_id = metadata.get("id") or metadata.get("request_id")
        record = ModelCallRecord(
            call_id=call_id,
            run_id=run_id,
            operation=operation,
            model=settings.model,
            provider_host=urlparse(settings.base_url).netloc,
            started_at=started_at,
            finished_at=finished_at,
            success=True,
            input_chars=_text_size(payload),
            output_chars=len(_response_text(result)),
            usage_available=bool(usage),
            usage=usage if isinstance(usage, dict) else {"raw": str(usage)},
            provider_request_id=str(provider_request_id) if provider_request_id else None,
        )
        if store is not None:
            store.save_model_call(record)
        return result
    except Exception as error:
        finished_at = datetime.now(UTC)
        record = ModelCallRecord(
            call_id=call_id,
            run_id=run_id,
            operation=operation,
            model=settings.model,
            provider_host=urlparse(settings.base_url).netloc,
            started_at=started_at,
            finished_at=finished_at,
            success=False,
            input_chars=_text_size(payload),
            error_type=type(error).__name__,
            error_message=str(error)[:1000],
        )
        if store is not None:
            store.save_model_call(record)
        raise
