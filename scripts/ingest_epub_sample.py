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
from omni_memory.graphs.memory_graph import build_memory_graph
from omni_memory.llm.client import get_chat_model
from omni_memory.stores.sqlite_store import SQLiteMemoryStore


def log(message: str) -> None:
    print(message, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--max-chapters", type=int, default=1)
    parser.add_argument("--max-chunks", type=int, default=1)
    args = parser.parse_args()

    log("[1/6] parse:start")
    parsed = parse_source(args.source)
    log(f"[1/6] parse:ok chapters={len(parsed.chapters)} assets={len(parsed.assets)}")

    chapters = parsed_chapters_to_novel_chapters(
        parsed.chapters,
        max_chapters=args.max_chapters,
    )
    chunks = split_chapters(tuple(chapters), max_chars=800)[: args.max_chunks]
    episodes = chunks_to_episodes(
        chunks,
        ingested_at=datetime.now(UTC),
        source=f"authorized-local:{args.source.name}",
    )
    log(f"[2/6] select:ok chapters={len(chapters)} chunks={len(chunks)}")

    log("[3/6] model:init:start")
    model = get_chat_model()
    log("[3/6] model:init:ok")

    database = Path("artifacts") / f"{args.source.stem}-sample.sqlite3"
    result_path = Path("artifacts") / f"{args.source.stem}-ingest-progress.jsonl"
    database.parent.mkdir(parents=True, exist_ok=True)

    with SQLiteMemoryStore(database) as store:
        store.put_assets(assets_to_records(parsed.assets))
        graph = build_memory_graph(model=model, store=store)
        log(f"[4/6] graph:init:ok db={database}")

        with result_path.open("a", encoding="utf-8") as progress:
            for index, episode in enumerate(episodes, start=1):
                started = perf_counter()
                log(
                    f"[5/6] episode:start index={index}/{len(episodes)} "
                    f"id={episode.episode_id} chars={len(episode.text)}"
                )
                try:
                    result = graph.invoke({"episode": episode})
                    record = {
                        "episode_id": episode.episode_id,
                        "status": result["status"],
                        "candidate_count": len(result.get("candidates", [])),
                        "valid_count": len(result.get("valid_candidates", [])),
                        "committed_count": len(result.get("committed", [])),
                        "issue_count": len(result.get("issues", [])),
                        "elapsed_seconds": round(perf_counter() - started, 2),
                    }
                    log("[5/6] episode:ok " + json.dumps(record, ensure_ascii=False))
                except Exception as error:
                    record = {
                        "episode_id": episode.episode_id,
                        "status": "error",
                        "error_type": type(error).__name__,
                        "error": str(error),
                        "elapsed_seconds": round(perf_counter() - started, 2),
                    }
                    log("[5/6] episode:error " + json.dumps(record, ensure_ascii=False))
                    progress.write(json.dumps(record, ensure_ascii=False) + "\n")
                    progress.flush()
                    raise
                progress.write(json.dumps(record, ensure_ascii=False) + "\n")
                progress.flush()

        report = {
            "source": args.source.name,
            "processed_chunks": len(episodes),
            "asset_count": len(store.list_assets()),
            "committed_memory_count": store.count(),
            "progress_file": str(result_path),
        }

    log("[6/6] complete " + json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
