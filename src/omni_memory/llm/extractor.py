from typing import Any, Protocol

from langchain_core.messages import HumanMessage, SystemMessage

from omni_memory.llm.client import get_chat_model
from omni_memory.llm.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    build_extraction_user_prompt,
)
from omni_memory.schemas.extraction import FactExtraction
from omni_memory.schemas.memory import Episode


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
) -> FactExtraction:
    """从一个 Episode 提出候选事实；不执行证据校验和持久化。"""

    chat_model = model or get_chat_model()
    structured_model = chat_model.with_structured_output(
        FactExtraction,
        method="json_mode",
    )
    result = structured_model.invoke(
        [
            SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
            HumanMessage(content=build_extraction_user_prompt(episode)),
        ]
    )

    if isinstance(result, FactExtraction):
        return result
    return FactExtraction.model_validate(result)
