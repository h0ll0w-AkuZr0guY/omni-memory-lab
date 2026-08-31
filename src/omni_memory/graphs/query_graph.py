from typing import Literal, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from omni_memory.llm.client import get_chat_model
from omni_memory.llm.observability import invoke_with_observation
from omni_memory.retrieval.grounding import validate_grounded_answer
from omni_memory.retrieval.sqlite_retriever import SQLiteMemoryRetriever
from omni_memory.schemas.query import GroundedAnswer, MemoryQuery, RetrievedMemory
from omni_memory.stores.platform_store import PlatformStore
from omni_memory.stores.sqlite_store import SQLiteMemoryStore

ANSWER_SYSTEM_PROMPT = """
你是一个证据约束的小说记忆问答 Agent。
只能使用提供的 retrieved_memories 回答，不能使用外部知识或常识补全。
回答中的每个事实性判断都必须引用 retrieved_memories 中实际存在的 memory_id。
如果证据不足，返回 abstain=true、grounded=false、citation_memory_ids=[]。
只输出符合 JSON schema 的对象。
""".strip()


class QueryGraphState(TypedDict, total=False):
    query: MemoryQuery
    retrieved: list[RetrievedMemory]
    draft_answer: GroundedAnswer
    answer: GroundedAnswer
    status: Literal["answered", "abstained"]


def retrieve_node(
    state: QueryGraphState,
    retriever: SQLiteMemoryRetriever,
) -> dict[str, list[RetrievedMemory]]:
    query = state["query"]
    return {"retrieved": retriever.search(query.query, query.top_k)}


def answer_node(
    state: QueryGraphState,
    model=None,
    call_store: PlatformStore | None = None,
    run_id: str | None = None,
) -> dict[str, GroundedAnswer]:
    retrieved = state.get("retrieved", [])
    if not retrieved:
        return {
            "draft_answer": GroundedAnswer(
                answer="当前记忆中没有足够证据回答这个问题。",
                citation_memory_ids=[],
                grounded=False,
                abstain=True,
            )
        }

    evidence = "\n".join(
        f"memory_id={item.memory.memory_id}; score={item.score:.4f}; "
        f"statement={item.memory.statement}; evidence={item.memory.evidence_quote}"
        for item in retrieved
    )
    prompt = f"问题：{state['query'].query}\n\n可用证据：\n{evidence}"
    chat_model = model or get_chat_model()
    structured_model = chat_model.with_structured_output(
        GroundedAnswer,
        method="json_mode",
    )
    result = invoke_with_observation(
        structured_model,
        [
            SystemMessage(content=ANSWER_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ],
        operation="grounded_query_answer",
        store=call_store,
        run_id=run_id,
    )
    if isinstance(result, GroundedAnswer):
        return {"draft_answer": result}
    return {"draft_answer": GroundedAnswer.model_validate(result)}


def validate_answer_node(state: QueryGraphState) -> dict[str, GroundedAnswer]:
    answer = validate_grounded_answer(
        state["draft_answer"],
        state.get("retrieved", []),
    )
    return {"answer": answer}


def route_answer(state: QueryGraphState) -> Literal["answered", "abstained"]:
    if state["answer"].abstain or not state["answer"].grounded:
        return "abstained"
    return "answered"


def mark_answered(state: QueryGraphState) -> dict[str, object]:
    return {"status": "answered", "answer": state["answer"]}


def mark_abstained(state: QueryGraphState) -> dict[str, object]:
    return {"status": "abstained", "answer": state["answer"]}


def build_query_graph(
    store: SQLiteMemoryStore,
    model=None,
    call_store: PlatformStore | None = None,
    run_id: str | None = None,
):
    retriever = SQLiteMemoryRetriever(store)

    def retrieve_with_store(state: QueryGraphState):
        return retrieve_node(state, retriever)

    def answer_with_model(state: QueryGraphState):
        return answer_node(
            state,
            model=model,
            call_store=call_store,
            run_id=run_id,
        )

    builder = StateGraph(QueryGraphState)
    builder.add_node("retrieve", retrieve_with_store)
    builder.add_node("answer", answer_with_model)
    builder.add_node("validate_answer", validate_answer_node)
    builder.add_node("mark_answered", mark_answered)
    builder.add_node("mark_abstained", mark_abstained)
    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "answer")
    builder.add_edge("answer", "validate_answer")
    builder.add_conditional_edges(
        "validate_answer",
        route_answer,
        {"answered": "mark_answered", "abstained": "mark_abstained"},
    )
    builder.add_edge("mark_answered", END)
    builder.add_edge("mark_abstained", END)
    return builder.compile()
