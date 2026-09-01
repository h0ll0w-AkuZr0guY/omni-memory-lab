import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from omni_memory.evaluation.chunking import split_chapters
from omni_memory.evaluation.ingest import chunks_to_episodes
from omni_memory.evaluation.source_bridge import (
    assets_to_records,
    parsed_chapters_to_novel_chapters,
)
from omni_memory.evaluation.source_parser import parse_source
from omni_memory.llm.batch_extractor import extract_batch
from omni_memory.llm.client import get_chat_model
from omni_memory.schemas.memory import Episode
from omni_memory.services.run_context import RunContext
from omni_memory.stores.commit import commit_candidates
from omni_memory.stores.platform_store import PlatformStore
from omni_memory.stores.sqlite_store import SQLiteMemoryStore

FRONT_MATTER_MARKERS = ("目录", "关键词", "作者：", "插画：", "录入：", "校对：")


def log(message: str) -> None:
    print(message, flush=True)


def is_content_chapter(chapter) -> bool:
    preview = chapter.text[:500]
    return len(chapter.text) >= 500 and not any(
        marker in preview for marker in FRONT_MATTER_MARKERS
    )


def load_completed(path: Path) -> set[str]:
    if not path.exists():
        return set()
    completed: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("status") in {"committed", "empty", "needs_review"}:
            values = record.get("episode_ids", [record.get("episode_id", "")])
            completed.update(item for item in values if item)
    return completed


def write_record(progress, record: dict) -> None:
    progress.write(json.dumps(record, ensure_ascii=False) + "\n")
    progress.flush()
    log("episode: " + json.dumps(record, ensure_ascii=False))


def process_batch(
    episodes: list[Episode],
    *,
    model,
    store: SQLiteMemoryStore,
    call_store: PlatformStore,
    run_id: str,
    max_attempts: int,
    retry_backoff_s: float,
    progress,
) -> tuple[int, bool]:
    started = perf_counter()
    try:
        grouped = extract_batch(
            episodes,
            model=model,
            call_store=call_store,
            run_id=run_id,
            max_attempts=max_attempts,
            retry_backoff_s=retry_backoff_s,
        )
    except Exception as error:  # noqa: BLE001 - provider SDK 异常类型跨版本不稳定
        for episode in episodes:
            write_record(
                progress,
                {
                    "episode_id": episode.episode_id,
                    "status": "provider_error",
                    "candidate_count": 0,
                    "committed_count": 0,
                    "issue_count": 0,
                    "error_type": type(error).__name__,
                    "error": str(error)[:1000],
                    "batch_elapsed_seconds": round(perf_counter() - started, 2),
                },
            )
        return 0, False

    committed_count = 0
    for episode in episodes:
        candidates = grouped.get(episode.episode_id, [])
        if not candidates:
            record = {
                "episode_id": episode.episode_id,
                "status": "empty",
                "candidate_count": 0,
                "committed_count": 0,
                "issue_count": 0,
            }
        else:
            committed, issues = commit_candidates(episode, candidates)
            if issues:
                record = {
                    "episode_id": episode.episode_id,
                    "status": "needs_review",
                    "candidate_count": len(candidates),
                    "committed_count": 0,
                    "issue_count": len(issues),
                    "issue_codes": [issue.code for issue in issues],
                    "issue_messages": [issue.message for issue in issues],
                }
            else:
                store.put_many(committed)
                committed_count += len(committed)
                record = {
                    "episode_id": episode.episode_id,
                    "status": "committed",
                    "candidate_count": len(candidates),
                    "committed_count": len(committed),
                    "issue_count": 0,
                }
        record["batch_elapsed_seconds"] = round(perf_counter() - started, 2)
        write_record(progress, record)
    return committed_count, True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--max-chapters", type=int, default=2)
    parser.add_argument("--max-episodes", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--retry-backoff-s", type=float, default=1.0)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--progress", type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    if (
        args.max_chapters <= 0
        or args.max_episodes <= 0
        or args.batch_size <= 0
        or args.max_attempts <= 0
        or args.retry_backoff_s < 0
    ):
        raise SystemExit(
            "max-chapters、max-episodes、batch-size、max-attempts 必须大于 0，"
            "retry-backoff-s 不能小于 0"
        )

    parsed = parse_source(args.source)
    content_chapters = tuple(
        chapter for chapter in parsed.chapters if is_content_chapter(chapter)
    )
    chapters = parsed_chapters_to_novel_chapters(
        content_chapters[: args.max_chapters]
    )
    chunks = split_chapters(tuple(chapters), max_chars=800)[: args.max_episodes]
    episodes = list(
        chunks_to_episodes(
            chunks,
            ingested_at=datetime.now(UTC),
            source=f"authorized-local:{args.source.name}",
        )
    )

    database = args.database or Path("artifacts") / f"{args.source.stem}-content-batch.sqlite3"
    progress_path = args.progress or Path("artifacts") / f"{args.source.stem}-content-progress.jsonl"
    completed = load_completed(progress_path) if args.resume else set()
    pending = [episode for episode in episodes if episode.episode_id not in completed]

    log(
        f"content_chapters={len(content_chapters)} selected_chapters={len(chapters)} "
        f"input_episodes={len(episodes)} pending_episodes={len(pending)} "
        f"batch_size={args.batch_size} max_attempts={args.max_attempts}"
    )

    database.parent.mkdir(parents=True, exist_ok=True)
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    with SQLiteMemoryStore(database) as store, PlatformStore(database) as call_store:
        store.put_assets(assets_to_records(parsed.assets))
        model = get_chat_model()
        with RunContext(
            call_store,
            tenant_id=args.source.stem,
            namespace="novel-ingestion",
            operation="batch_ingest_epub",
        ) as run, progress_path.open("a", encoding="utf-8") as progress:
            total_committed = 0
            failed_batches = 0
            for start in range(0, len(pending), args.batch_size):
                batch = pending[start : start + args.batch_size]
                log(f"batch:start index={start // args.batch_size + 1} size={len(batch)}")
                committed, succeeded = process_batch(
                    batch,
                    model=model,
                    store=store,
                    call_store=call_store,
                    run_id=run.run.run_id,
                    max_attempts=args.max_attempts,
                    retry_backoff_s=args.retry_backoff_s,
                    progress=progress,
                )
                total_committed += committed
                failed_batches += int(not succeeded)
            final_run = run.succeed(
                {
                    "input_episodes": len(pending),
                    "committed_memories": total_committed,
                    "model_calls": len(call_store.list_model_calls(run.run.run_id)),
                    "failed_batches": failed_batches,
                }
            )
        log(
            f"complete database={database} run_id={final_run.run_id} "
            f"run_status={final_run.status} committed_memory_count={store.count()} "
            f"asset_count={len(store.list_assets())} "
            f"model_call_count={len(call_store.list_model_calls(final_run.run_id))} "
            f"failed_batches={failed_batches} progress={progress_path}"
        )


if __name__ == "__main__":
    main()
