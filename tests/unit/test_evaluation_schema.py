import pytest
from pydantic import ValidationError

from omni_memory.schemas.evaluation import (
    CutoffPolicy,
    EvaluationCase,
    SourceSpan,
)


def suffix_cutoff() -> CutoffPolicy:
    return CutoffPolicy(
        mask_strategy="suffix",
        visible_ratio=0.8,
    )


def test_answerable_case_requires_gold_answer_and_span():
    case = EvaluationCase(
        case_id="novel-dev-001",
        dataset_id="novel-demo",
        split="dev",
        query="顾言什么时候修好了收音机？",
        query_type="event_order",
        gold_answer="雨夜",
        answerable=True,
        gold_source_spans=[
            SourceSpan(
                document_id="chapter-03",
                chapter_index=3,
                start_char=10,
                end_char=18,
            )
        ],
        cutoff=suffix_cutoff(),
    )

    assert case.cutoff.visible_ratio == 0.8


def test_cutoff_requires_exactly_one_boundary():
    with pytest.raises(ValidationError):
        CutoffPolicy(mask_strategy="suffix")

    with pytest.raises(ValidationError):
        CutoffPolicy(
            mask_strategy="suffix",
            visible_ratio=0.8,
            visible_until_chapter=3,
        )


def test_random_span_requires_seed():
    with pytest.raises(ValidationError):
        CutoffPolicy(mask_strategy="random_span", visible_ratio=0.8)


def test_unanswerable_case_cannot_have_gold_span():
    with pytest.raises(ValidationError):
        EvaluationCase(
            case_id="novel-dev-002",
            dataset_id="novel-demo",
            split="dev",
            query="顾言最喜欢哪家餐馆？",
            query_type="unanswerable",
            answerable=False,
            gold_source_spans=[
                SourceSpan(
                    document_id="chapter-01",
                    chapter_index=1,
                    start_char=0,
                    end_char=5,
                )
            ],
            cutoff=suffix_cutoff(),
        )
