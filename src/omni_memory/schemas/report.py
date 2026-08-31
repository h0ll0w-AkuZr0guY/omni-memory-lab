from pydantic import BaseModel, ConfigDict, Field


class CaseEvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    recall_at_k: float = Field(ge=0.0, le=1.0)
    precision_at_k: float = Field(ge=0.0, le=1.0)
    mrr: float = Field(ge=0.0, le=1.0)
    citation_precision: float = Field(ge=0.0, le=1.0)
    citation_recall: float = Field(ge=0.0, le=1.0)
    abstention_correct: bool
    temporal_leakage_rate: float = Field(ge=0.0, le=1.0)
    status: str = Field(min_length=1)


class EvaluationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    case_count: int = Field(ge=0)
    mean_recall_at_k: float = Field(ge=0.0, le=1.0)
    mean_precision_at_k: float = Field(ge=0.0, le=1.0)
    mean_mrr: float = Field(ge=0.0, le=1.0)
    mean_citation_precision: float = Field(ge=0.0, le=1.0)
    mean_citation_recall: float = Field(ge=0.0, le=1.0)
    abstention_accuracy: float = Field(ge=0.0, le=1.0)
    temporal_leakage_rate: float = Field(ge=0.0, le=1.0)
    case_results: list[CaseEvaluationResult]
