from pydantic import BaseModel, ConfigDict, Field


class QuestionGeneration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    citation_memory_ids: list[str] = Field(min_length=1)
