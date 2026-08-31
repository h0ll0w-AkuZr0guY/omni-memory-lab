import json
import sys
from pathlib import Path

from omni_memory.evaluation.cutoff import NovelChapter
from omni_memory.evaluation.runner import EvaluationRunner
from omni_memory.llm.client import get_chat_model
from omni_memory.schemas.evaluation import CutoffPolicy, DatasetManifest, EvaluationCase


def load_chapters(path: Path) -> list[NovelChapter]:
    text = path.read_text(encoding="utf-8")
    sections = [section.strip() for section in text.split("\n\n") if section.strip()]
    return [NovelChapter(f"chapter-{index}", index, section) for index, section in enumerate(sections, 1)]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("用法：python scripts/run_evaluation.py data/raw/your_novel.txt")

    path = Path(sys.argv[1])
    chapters = load_chapters(path)
    if len(chapters) < 5:
        raise SystemExit("至少需要 5 个章节，才能执行 80/20 cutoff")

    manifest = DatasetManifest(
        dataset_id=path.stem,
        version="local-v1",
        source_uri=f"local://{path.name}",
        license_note="user-authorized-local-only",
        content_sha256="fill-with-real-sha256-before-reporting",
        language="zh-CN",
        split="test",
    )
    policy = CutoffPolicy(mask_strategy="suffix", visible_ratio=0.8)
    raise SystemExit(
        "请先在评估 cases 中填写 gold_answer 与 gold_source_spans，"
        "再调用 EvaluationRunner；本脚本故意不自动从 holdout 生成答案，避免 gold 泄漏。"
    )


if __name__ == "__main__":
    main()
