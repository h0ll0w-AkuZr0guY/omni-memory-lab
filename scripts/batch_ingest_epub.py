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
        if record.get("status") in {"committed", "empty"}:
            completed.update(record.get("episode_ids", [record.get("episode_id", "")]))
    return {item for item in completed if item}


def process_batch(
    episodes: list[Episode],
    *,
    model,
    store: SQLiteMemoryStore,
    call_store: PlatformStore,
    progress,
) -> None:
    started = perf_counter()
    try:
        grouped = extract_batch(
            episodes,
            model=model,
            call_store=call_store,
        )
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
                    record = {
                        "episode_id": episode.episode_id,
                        "status": "committed",
                        "candidate_count": len(candidates),
                        "committed_count": len(committed),
                        "issue_count": 0,
                    }
            record["batch_elapsed_seconds"] = round(perf_counter() - started, 2)
            progress.write(json.dumps(record, ensure_ascii=False) + "\n")
            progress.flush()
            log("episode: " + json.dumps(record, ensure_ascii=False))
    except Exception as error:
        record = {
            "episode_ids": [episode.episode_id for episode in episodes],
            "status": "error",
            "error_type": type(error).__name__,
            "error": str(error),
            "batch_elapsed_seconds": round(perf_counter() - started, 2),
        }
        progress.write(json.dumps(record, ensure_ascii=False) + "\n")
        progress.flush()
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--max-chapters", type=int, default=2)
    parser.add_argument("--max-episodes", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--progress", type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    if args.max_chapters <= 0 or args.max_episodes <= 0 or args.batch_size <= 0:
        raise SystemExit("max-chapters、max-episodes 和 batch-size 必须大于 0")

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
        f"batch_size={args.batch_size}"
    )

    database.parent.mkdir(parents=True, exist_ok=True)
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    with SQLiteMemoryStore(database) as store, PlatformStore(database) as call_store:
        store.put_assets(assets_to_records(parsed.assets))
        model = get_chat_model()
        with progress_path.open("a", encoding="utf-8") as progress:
            for start in range(0, len(pending), args.batch_size):
                batch = pending[start : start + args.batch_size]
                log(f"batch:start index={start // args.batch_size + 1} size={len(batch)}")
                process_batch(
                    batch,
                    model=model,
                    store=store,
                    call_store=call_store,
                    progress=progress,
                )
        log(
            f"complete database={database} committed_memory_count={store.count()} "
            f"asset_count={len(store.list_assets())} progress={progress_path}"
        )


if __name__ == "__main__":
    main()
