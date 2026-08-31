import json
import sys
from pathlib import Path

from omni_memory.evaluation.source_parser import parse_source
from omni_memory.llm.client import get_chat_model
from omni_memory.schemas.memory import CommittedFact
from omni_memory.schemas.question_generation import QuestionGeneration
from omni_memory.stores.sqlite_store import SQLiteMemoryStore


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "用法：python scripts/generate_case_candidates.py "
            "data/raw/01我想成为影之强者！.epub"
        )

    source = Path(sys.argv[1])
    parsed = parse_source(source)
    content_chapters = tuple(
        chapter
        for chapter in parsed.chapters
        if len(chapter.text) >= 500
        and not any(
            marker in chapter.text[:500]
            for marker in ("目录", "关键词", "作者：", "插画：", "录入：", "校对：")
        )
    )
    database = Path("artifacts") / f"{source.stem}-batch.sqlite3"
    output = Path("artifacts") / f"{source.stem}-case-candidates.jsonl"
    memories: list[CommittedFact]
    with SQLiteMemoryStore(database) as store:
        memories = store.list_all()
    content_document_ids = {chapter.document_id for chapter in content_chapters}
    memories = [
        memory
        for memory in memories
        if memory.metadata.get("document_id") in content_document_ids
    ]

    if not memories:
        raise SystemExit("SQLite 中没有已提交记忆，请先运行批量摄入")

    # 首轮最多取 10 条事实，避免一次生成过多候选。
    memories = memories[:10]
    model = get_chat_model()
    structured = model.with_structured_output(QuestionGeneration, method="json_mode")
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", encoding="utf-8") as file:
        for index, memory in enumerate(memories, start=1):
            prompt = (
                "根据下面已经通过 evidence 校验的事实，生成一个自然的中文问题。"
                "问题必须能由该事实直接回答，不要加入事实之外的信息。"
                "只输出 JSON，question 是问题，answer 是该事实的简短答案，citation_memory_ids 必须填入给定 memory_id。"
                f"memory_id={memory.memory_id}\n"
                f"statement={memory.statement}\n"
                f"evidence={memory.evidence_quote}"
            )
            result = structured.invoke(prompt)
            answer = (
                result
                if isinstance(result, QuestionGeneration)
		else QuestionGeneration.model_validate(result)
            )
            try:
                document_id, chapter_index, start, end = _locate_memory(memory, content_chapters)
            except ValueError:
                print(f"skip_unlocatable_memory={memory.memory_id}")
                continue

            case = {
                "case_id": f"{source.stem}:candidate:{index:04d}",
                "dataset_id": source.stem,
                "query": answer.question,
                "query_type": "citation",
                "gold_answer": memory.statement,
                "source_memory_id": memory.memory_id,
                "source_episode_id": memory.source_episode_id,
                "evidence_quote": memory.evidence_quote,
                "source_document_id": document_id,
                "chapter_index": chapter_index,
                "start_char": start,
                "end_char": end,
                "approved": False,
                "reviewer_note": "",
            }
            file.write(json.dumps(case, ensure_ascii=False) + "\n")
            file.flush()
            print(json.dumps(case, ensure_ascii=False))

    print(f"candidate_file={output}")


def _locate_memory(memory, chapters):
    for chapter in chapters:
        start = chapter.text.find(memory.evidence_quote)
        if start >= 0:
            return chapter.document_id, chapter.chapter_index, start, start + len(memory.evidence_quote)
    raise ValueError(f"无法定位 evidence_quote: {memory.memory_id}")


if __name__ == "__main__":
    main()
