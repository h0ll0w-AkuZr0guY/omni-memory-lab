import json
from datetime import UTC, datetime
from time import perf_counter

from omni_memory.graphs.validation import validate_candidates
from omni_memory.llm.extractor import extract_fact_candidates
from omni_memory.schemas.memory import Episode


def main() -> None:
    episode = Episode(
        episode_id="smoke-episode-001",
        text=(
            "沈砚在凌晨三点关掉了灯。窗外的雨一直没有停，"
            "他把写满批注的蓝色笔记本放回抽屉。"
        ),
        ingested_at=datetime.now(UTC),
        source="local-smoke-test",
    )

    started = perf_counter()
    extraction = extract_fact_candidates(episode)
    valid, issues = validate_candidates(episode, extraction.facts)
    elapsed = perf_counter() - started

    print("extraction_call=ok")
    print(f"elapsed_seconds={elapsed:.2f}")
    print(f"candidate_count={len(extraction.facts)}")
    print(
        "candidates="
        + json.dumps(extraction.model_dump(mode="json"), ensure_ascii=False)
    )
    print(f"validated_count={len(valid)}")
    print(
        "validation_issues="
        + json.dumps(
            [issue.model_dump(mode="json") for issue in issues],
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
