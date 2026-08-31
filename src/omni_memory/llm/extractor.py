from typing import Any, Protocol

from langchain_core.messages import HumanMessage, SystemMessage

from omni_memory.llm.client import get_chat_model
from omni_memory.llm.observability import invoke_with_observation
from omni_memory.llm.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    build_extraction_user_prompt,
)
from omni_memory.schemas.extraction import FactExtraction
from omni_memory.schemas.memory import Episode
from omni_memory.stores.platform_store import PlatformStore


class StructuredInvoker(Protocol):
    def invoke(self, messages: list[Any]) -> Any: ...


class ModelWithStructuredOutput(Protocol):
    def with_structured_output(
        self,
        schema: type[FactExtraction],
        *,
        method: str,
    ) -> StructuredInvoker: ...


def extract_fact_candidates(
    episode: Episode,
    model: ModelWithStructuredOutput | None = None,
    call_store: PlatformStore | None = None,
    run_id: str | None = None,
) -> FactExtraction:
    """从一个 Episode 提出候选事实；不执行证据校验和持久化。"""

    chat_model = model or get_chat_model()
    structured_model = chat_model.with_structured_output(
        FactExtraction,
        method="json_mode",
    )
    result = invoke_with_observation(
        structured_model,
        [
            SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
            HumanMessage(content=build_extraction_user_prompt(episode)),
        ],
        operation="fact_extraction",
        store=call_store,
        run_id=run_id,
    )

    if isinstance(result, FactExtraction):
        return result
    return FactExtraction.model_validate(result)
