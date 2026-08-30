from pydantic import BaseModel, ConfigDict, Field

from omni_memory.schemas.memory import CommittedFact


class MemoryQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class RetrievedMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory: CommittedFact
    score: float = Field(ge=0.0)


class GroundedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1)
    citation_memory_ids: list[str] = Field(default_factory=list)
    grounded: bool
    abstain: bool
