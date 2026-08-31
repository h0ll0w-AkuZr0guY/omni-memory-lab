from collections import defaultdict
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from omni_memory.llm.client import get_chat_model
from omni_memory.llm.observability import invoke_with_observation
from omni_memory.schemas.batch_extraction import BatchFactExtraction
from omni_memory.schemas.memory import Episode, FactCandidate
from omni_memory.stores.platform_store import PlatformStore

BATCH_SYSTEM_PROMPT = """
你是证据优先的小说记忆抽取器。输入包含多个彼此独立的 episode。
请只从每个 episode 自身的原文中抽取明确事实，并把事实绑定到正确的 episode_id。

严格规则：
1. evidence_quote 必须是对应 episode 原文中的连续精确子串。
2. statement 可以规范化代词，但不得增加原文没有的信息。
3. 不确定、推测和常识不要抽取。
4. episode_id 必须来自输入，禁止新造或混用 episode_id。
5. 没有事实时可以返回空 facts。
6. 只输出 JSON：{"facts": [{"episode_id": "...", "kind": "episodic", "statement": "...", "evidence_quote": "...", "confidence": 0.0}]}。
""".strip()


def build_batch_prompt(episodes: list[Episode]) -> str:
    blocks = []
    for episode in episodes:
        blocks.append(
            f"<episode id=\"{episode.episode_id}\">\n"
            f"{episode.text}\n"
            "</episode>"
        )
    return "请处理以下 episode，不能使用 episode 之外的信息：\n\n" + "\n\n".join(blocks)


def extract_batch(
    episodes: list[Episode],
    model: Any | None = None,
    call_store: PlatformStore | None = None,
    run_id: str | None = None,
) -> dict[str, list[FactCandidate]]:
    if not episodes:
        return {}

    chat_model = model or get_chat_model()
    structured_model = chat_model.with_structured_output(
        BatchFactExtraction,
        method="json_mode",
    )
    result = invoke_with_observation(
        structured_model,
        [
            SystemMessage(content=BATCH_SYSTEM_PROMPT),
            HumanMessage(content=build_batch_prompt(episodes)),
        ],
        operation="batch_fact_extraction",
        store=call_store,
        run_id=run_id,
    )
    extraction = (
        result
        if isinstance(result, BatchFactExtraction)
        else BatchFactExtraction.model_validate(result)
    )

    known_ids = {episode.episode_id for episode in episodes}
    grouped: dict[str, list[FactCandidate]] = defaultdict(list)
    for fact in extraction.facts:
        if fact.episode_id not in known_ids:
            continue
        grouped[fact.episode_id].append(
            FactCandidate(
                kind=fact.kind,
                statement=fact.statement,
                evidence_quote=fact.evidence_quote,
                confidence=fact.confidence,
            )
        )
    return dict(grouped)
