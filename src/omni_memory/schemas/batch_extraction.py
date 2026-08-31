from pydantic import BaseModel, ConfigDict, Field

from omni_memory.schemas.memory import MemoryKind


class BatchFactCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    episode_id: str = Field(min_length=1)
    kind: MemoryKind = "episodic"
    statement: str = Field(min_length=1)
    evidence_quote: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class BatchFactExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facts: list[BatchFactCandidate] = Field(default_factory=list)
