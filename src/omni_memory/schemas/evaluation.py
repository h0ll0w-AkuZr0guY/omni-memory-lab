from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

QueryType = Literal[
    "entity_attribute",
    "event_order",
    "multi_hop",
    "state_change",
    "foreshadowing",
    "unanswerable",
    "citation",
]

MaskStrategy = Literal["suffix", "random_span"]


class DatasetManifest(BaseModel):
    """数据集身份与可复现信息，不包含完整原文。"""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    source_uri: str = Field(min_length=1)
    license_note: str = Field(min_length=1)
    content_sha256: str = Field(min_length=1)
    language: str = Field(min_length=1)
    split: Literal["train", "dev", "test"]


class CutoffPolicy(BaseModel):
    """规定被测系统的可见边界和遮蔽方式。"""

    model_config = ConfigDict(extra="forbid")

    mask_strategy: MaskStrategy
    visible_until_chapter: int | None = Field(default=None, ge=0)
    visible_ratio: float | None = Field(default=None, gt=0.0, lt=1.0)
    random_seed: int | None = None
    mask_fraction: float = Field(default=0.2, gt=0.0, lt=1.0)

    @model_validator(mode="after")
    def require_one_cutoff(self) -> "CutoffPolicy":
        if (self.visible_until_chapter is None) == (self.visible_ratio is None):
            raise ValueError("必须且只能设置 visible_until_chapter 或 visible_ratio")
        if self.mask_strategy == "random_span" and self.random_seed is None:
            raise ValueError("random_span 必须提供 random_seed")
        return self


class SourceSpan(BaseModel):
    """gold 证据在原始文档中的位置；offset 使用半开区间。"""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    chapter_index: int = Field(ge=0)
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_range(self) -> "SourceSpan":
        if self.end_char <= self.start_char:
            raise ValueError("end_char 必须大于 start_char")
        return self


class EvaluationCase(BaseModel):
    """单个离线评估问题、答案和 gold 证据。"""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    split: Literal["train", "dev", "test"]
    query: str = Field(min_length=1)
    query_type: QueryType
    gold_answer: str | None = None
    answerable: bool
    gold_source_spans: list[SourceSpan] = Field(default_factory=list)
    cutoff: CutoffPolicy

    @model_validator(mode="after")
    def validate_gold_consistency(self) -> "EvaluationCase":
        if self.answerable and not self.gold_answer:
            raise ValueError("answerable case 必须有 gold_answer")
        if self.answerable and not self.gold_source_spans:
            raise ValueError("answerable case 必须有 gold_source_spans")
        if not self.answerable and self.gold_source_spans:
            raise ValueError("unanswerable case 不应携带 gold_source_spans")
        return self
