from omni_memory.schemas.query import GroundedAnswer, RetrievedMemory


def validate_grounded_answer(
    answer: GroundedAnswer,
    retrieved: list[RetrievedMemory],
) -> GroundedAnswer:
    """确保引用 ID 来自本次召回；不负责判断自然语言是否完全正确。"""

    retrieved_ids = {item.memory.memory_id for item in retrieved}
    cited_ids = set(answer.citation_memory_ids)
    unknown_ids = cited_ids - retrieved_ids

    if unknown_ids or not answer.citation_memory_ids:
        return answer.model_copy(
            update={
                "answer": "当前召回的记忆不足以支持可靠回答。",
                "citation_memory_ids": [],
                "grounded": False,
                "abstain": True,
            }
        )

    return answer.model_copy(update={"grounded": True, "abstain": False})
