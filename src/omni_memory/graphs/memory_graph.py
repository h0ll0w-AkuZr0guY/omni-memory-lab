from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from omni_memory.graphs.validation import validate_candidates
from omni_memory.llm.extractor import (
    ModelWithStructuredOutput,
    extract_fact_candidates,
)
from omni_memory.schemas.memory import CommittedFact, Episode, FactCandidate, ValidationIssue
from omni_memory.stores.commit import commit_candidates
from omni_memory.stores.platform_store import PlatformStore
from omni_memory.stores.sqlite_store import SQLiteMemoryStore


class MemoryGraphState(TypedDict, total=False):
    episode: Episode
    candidates: list[FactCandidate]
    valid_candidates: list[FactCandidate]
    issues: list[ValidationIssue]
    committed: list[CommittedFact]
    status: Literal["needs_review", "ready_for_persistence", "committed"]


def extract_node(
    state: MemoryGraphState,
    model: ModelWithStructuredOutput | None = None,
    call_store: PlatformStore | None = None,
    run_id: str | None = None,
) -> dict[str, list[FactCandidate]]:
    extraction = extract_fact_candidates(
        state["episode"],
        model=model,
        call_store=call_store,
        run_id=run_id,
    )
    return {"candidates": extraction.facts}


def validate_node(state: MemoryGraphState) -> dict[str, object]:
    valid, issues = validate_candidates(
        episode=state["episode"],
        candidates=state.get("candidates", []),
    )
    return {"valid_candidates": valid, "issues": issues}


def route_after_validation(
    state: MemoryGraphState,
) -> Literal["review", "ready"]:
    if state.get("issues"):
        return "review"
    return "ready"


def mark_for_review(_: MemoryGraphState) -> dict[str, object]:
    return {"status": "needs_review", "committed": []}


def mark_ready(_: MemoryGraphState) -> dict[str, str]:
    return {"status": "ready_for_persistence"}


def persist_node(
    state: MemoryGraphState,
    store: SQLiteMemoryStore,
) -> dict[str, object]:
    committed, issues = commit_candidates(
        episode=state["episode"],
        candidates=state.get("candidates", []),
    )
    if issues:
        return {"committed": [], "issues": issues, "status": "needs_review"}
    store.put_many(committed)
    return {"committed": committed, "status": "committed"}


def build_memory_graph(
    model: ModelWithStructuredOutput | None = None,
    store: SQLiteMemoryStore | None = None,
    call_store: PlatformStore | None = None,
    run_id: str | None = None,
):
    """构造 Episode  抽取  校验  可选持久化的记忆图。"""

    def extract_with_config(state: MemoryGraphState) -> dict[str, list[FactCandidate]]:
        return extract_node(
            state,
            model=model,
            call_store=call_store,
            run_id=run_id,
        )

    builder = StateGraph(MemoryGraphState)
    builder.add_node("extract_candidates", extract_with_config)
    builder.add_node("validate_candidates", validate_node)
    builder.add_node("mark_for_review", mark_for_review)
    builder.add_node("mark_ready", mark_ready)

    builder.add_edge(START, "extract_candidates")
    builder.add_edge("extract_candidates", "validate_candidates")
    builder.add_conditional_edges(
        "validate_candidates",
        route_after_validation,
        {"review": "mark_for_review", "ready": "mark_ready"},
    )
    builder.add_edge("mark_for_review", END)

    if store is None:
        builder.add_edge("mark_ready", END)
    else:
        def persist_with_store(state: MemoryGraphState) -> dict[str, object]:
            return persist_node(state, store)

        builder.add_node("persist_committed_memories", persist_with_store)
        builder.add_edge("mark_ready", "persist_committed_memories")
        builder.add_edge("persist_committed_memories", END)

    return builder.compile()


def build_validation_graph():
    """保留只做校验的图，便于单独测试校验路由。"""

    builder = StateGraph(MemoryGraphState)
    builder.add_node("validate_candidates", validate_node)
    builder.add_node("mark_for_review", mark_for_review)
    builder.add_node("mark_ready", mark_ready)
    builder.add_edge(START, "validate_candidates")
    builder.add_conditional_edges(
        "validate_candidates",
        route_after_validation,
        {"review": "mark_for_review", "ready": "mark_ready"},
    )
    builder.add_edge("mark_for_review", END)
    builder.add_edge("mark_ready", END)
    return builder.compile()

