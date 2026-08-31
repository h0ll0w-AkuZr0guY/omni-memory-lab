import argparse
import json
from pathlib import Path

from omni_memory.evaluation.source_parser import parse_source
from omni_memory.llm.client import get_chat_model
from omni_memory.schemas.memory import CommittedFact
from omni_memory.schemas.question_generation import QuestionGeneration
from omni_memory.stores.sqlite_store import SQLiteMemoryStore

FRONT_MATTER_MARKERS = ("目录", "关键词", "作者：", "插画：", "录入：", "校对：")


def is_content_chapter(chapter) -> bool:
    preview = chapter.text[:500]
    return len(chapter.text) >= 500 and not any(
        marker in preview for marker in FRONT_MATTER_MARKERS
    )


def find_database(source: Path, explicit: Path | None) -> Path:
    if explicit is not None:
        if not explicit.exists():
            raise SystemExit(f"指定数据库不存在：{explicit}")
        return explicit

    expected = Path("artifacts") / f"{source.stem}-content-batch.sqlite3"
    candidates = [expected] + [
        path for path in sorted(Path("artifacts").glob("*-content-batch.sqlite3"))
        if path != expected
    ]
    for candidate in candidates:
        if candidate.exists():
            with SQLiteMemoryStore(candidate) as store:
                if store.count() > 0:
                    return candidate
    raise SystemExit("找不到正文专用 batch SQLite，请先运行 batch_ingest_epub.py")


def locate_memory(
    memory: CommittedFact,
    chapters: tuple,
) -> tuple[str, int, int, int]:
    for chapter in chapters:
        start = chapter.text.find(memory.evidence_quote)
        if start >= 0:
            return (
                chapter.document_id,
                chapter.chapter_index,
                start,
                start + len(memory.evidence_quote),
            )
    raise ValueError(f"无法在正文中定位 evidence_quote: {memory.memory_id}")


def build_question_prompt(memory: CommittedFact) -> str:
    return (
        "根据下面已经通过 evidence 校验的事实，生成一个自然的中文问题。"
        "问题必须能由该事实直接回答，不得加入事实之外的信息。"
        "只输出 JSON，question 是问题，answer 是简短答案，"
        "citation_memory_ids 必须只包含给定 memory_id。\n\n"
        f"memory_id={memory.memory_id}\n"
        f"statement={memory.statement}\n"
        f"evidence={memory.evidence_quote}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--limit", type=int, default=2)
    args = parser.parse_args()
    if args.limit <= 0:
        raise SystemExit("--limit 必须大于 0")

    parsed = parse_source(args.source)
    content_chapters = tuple(
        chapter for chapter in parsed.chapters if is_content_chapter(chapter)
    )
    if not content_chapters:
        raise SystemExit("没有识别到正文内容章节")

    database = find_database(args.source, args.database)
    with SQLiteMemoryStore(database) as store:
        all_memories: list[CommittedFact] = store.list_all()

    content_document_ids = {chapter.document_id for chapter in content_chapters}
    memories = [
        memory
        for memory in all_memories
        if memory.metadata.get("document_id") in content_document_ids
    ][: args.limit]
    if not memories:
        raise SystemExit(f"数据库 {database} 中没有能映射到正文的已提交记忆")

    print(f"using_database={database}")
    print(f"content_chapters={len(content_chapters)}")
    print(f"eligible_memories={len(memories)}")

    model = get_chat_model()
    structured = model.with_structured_output(QuestionGeneration, method="json_mode")
    output = Path("artifacts") / f"{args.source.stem}-case-candidates.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with output.open("w", encoding="utf-8") as file:
        for memory in memories:
            try:
                document_id, chapter_index, start, end = locate_memory(
                    memory, content_chapters
                )
            except ValueError as error:
                print(f"skip_unlocatable={memory.memory_id}: {error}")
                continue

            result = structured.invoke(build_question_prompt(memory))
            question = (
                result
                if isinstance(result, QuestionGeneration)
                else QuestionGeneration.model_validate(result)
            )
            case = {
                "case_id": f"{args.source.stem}:candidate:{written + 1:04d}",
                "dataset_id": args.source.stem,
                "query": question.question,
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
            written += 1
            print(f"candidate_written={written} chapter={chapter_index}")

    print(f"candidate_count={written}")
    print(f"candidate_file={output}")


if __name__ == "__main__":
    main()
