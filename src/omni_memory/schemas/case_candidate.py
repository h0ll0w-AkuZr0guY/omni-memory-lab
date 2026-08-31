from pydantic import BaseModel, ConfigDict, Field


class CaseCandidate(BaseModel):
    """候选评估案例；默认未批准，需人工审核后才能成为 gold case。"""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    query_type: str = Field(min_length=1)
    gold_answer: str = Field(min_length=1)
    source_memory_id: str = Field(min_length=1)
    source_episode_id: str = Field(min_length=1)
    evidence_quote: str = Field(min_length=1)
    source_document_id: str = Field(min_length=1)
    chapter_index: int = Field(ge=1)
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    approved: bool = False
    reviewer_note: str = ""
