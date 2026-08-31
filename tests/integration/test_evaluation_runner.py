
from omni_memory.evaluation.cutoff import NovelChapter
from omni_memory.evaluation.runner import EvaluationRunner
from omni_memory.schemas.evaluation import (
    CutoffPolicy,
    DatasetManifest,
    EvaluationCase,
    SourceSpan,
)
from omni_memory.schemas.extraction import FactExtraction
from omni_memory.schemas.memory import FactCandidate
from omni_memory.schemas.query import GroundedAnswer


class ExtractionStructured:
    def invoke(self, messages):
        text = str(messages)
        if "蓝色笔记本" in text:
            fact = FactCandidate(
                statement="沈砚把笔记本放回抽屉",
                evidence_quote="沈砚把蓝色笔记本放回抽屉",
                confidence=0.95,
            )
        else:
            fact = FactCandidate(
                statement="沈砚在凌晨三点关掉了灯",
                evidence_quote="沈砚在凌晨三点关掉了灯",
                confidence=0.98,
            )
        return FactExtraction(facts=[fact])


class ExtractionModel:
    def with_structured_output(self, schema, *, method):
        return ExtractionStructured()


class AnswerStructured:
    def invoke(self, messages):
        return GroundedAnswer(
            answer="沈砚在凌晨三点关掉了灯。",
            citation_memory_ids=["episode:chapter-1:chunk:0000:fact:0000"],
            grounded=True,
            abstain=False,
        )


class AnswerModel:
    def with_structured_output(self, schema, *, method):
        return AnswerStructured()


def manifest():
    return DatasetManifest(
        dataset_id="novel-e2e",
        version="v1",
        source_uri="local://authorized",
        license_note="test-owned",
        content_sha256="test-hash",
        language="zh-CN",
        split="test",
    )


def test_runner_never_indexes_holdout_chapter():
    chapters = [
        NovelChapter("chapter-1", 1, "沈砚在凌晨三点关掉了灯。"),
        NovelChapter("chapter-2", 2, "沈砚发现了蓝色笔记本。"),
        NovelChapter("chapter-3", 3, "后文揭示了一个秘密。"),
        NovelChapter("chapter-4", 4, "后文发生了新的事件。"),
        NovelChapter("chapter-5", 5, "后文最终收束。"),
    ]
    case = EvaluationCase(
        case_id="case-1",
        dataset_id="novel-e2e",
        split="test",
        query="沈砚什么时候关掉了灯？",
        query_type="event_order",
        gold_answer="凌晨三点",
        answerable=True,
        gold_source_spans=[
            SourceSpan(
                document_id="chapter-1",
                chapter_index=1,
                start_char=0,
                end_char=12,
            )
        ],
        cutoff=CutoffPolicy(mask_strategy="suffix", visible_ratio=0.8),
    )

    report = EvaluationRunner(ExtractionModel(), AnswerModel()).run(
        manifest(),
        chapters,
        [case],
        case.cutoff,
        top_k=3,
    )

    assert report.case_count == 1
    assert report.mean_recall_at_k == 1.0
    assert report.mean_mrr == 1.0
    assert report.temporal_leakage_rate == 0.0
    assert report.case_results[0].status == "answered"


def test_runner_does_not_turn_future_gold_into_retrievable_memory():
    chapters = [
        NovelChapter("chapter-1", 1, "沈砚在凌晨三点关掉了灯。"),
        NovelChapter("chapter-2", 2, "前文内容。"),
        NovelChapter("chapter-3", 3, "未来答案在这里。"),
        NovelChapter("chapter-4", 4, "未来内容。"),
        NovelChapter("chapter-5", 5, "未来收束。"),
    ]
    case = EvaluationCase(
        case_id="future-case",
        dataset_id="novel-e2e",
        split="test",
        query="未来章节发生了什么？",
        query_type="unanswerable",
        answerable=False,
        cutoff=CutoffPolicy(mask_strategy="suffix", visible_ratio=0.8),
    )

    report = EvaluationRunner(ExtractionModel(), AnswerModel()).run(
        manifest(),
        chapters,
        [case],
        case.cutoff,
    )

    assert report.case_results[0].abstention_correct is True
    assert report.case_results[0].temporal_leakage_rate == 0.0
