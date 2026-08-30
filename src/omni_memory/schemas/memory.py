from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MemoryKind = Literal["semantic", "episodic", "procedural"]
MemoryStatus = Literal["candidate", "committed", "retracted"]


class Episode(BaseModel):
    """原始输入单元，是所有派生记忆的证据根。"""

    model_config = ConfigDict(extra="forbid")

    episode_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    ingested_at: datetime
    valid_at: datetime | None = None
    source: str = Field(min_length=1)
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)


class FactCandidate(BaseModel):
    """模型从 Episode 中提出的候选记忆，尚未获得提交资格。"""

    model_config = ConfigDict(extra="forbid")

    kind: MemoryKind = "semantic"
    statement: str = Field(min_length=1)
    evidence_quote: str = Field(min_length=1)
    valid_at: datetime | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    status: Literal["candidate"] = "candidate"


class CommittedFact(BaseModel):
    """通过证据校验后进入长期记忆的事实。"""

    model_config = ConfigDict(extra="forbid")

    memory_id: str = Field(min_length=1)
    source_episode_id: str = Field(min_length=1)
    kind: MemoryKind = "semantic"
    statement: str = Field(min_length=1)
    evidence_quote: str = Field(min_length=1)
    ingested_at: datetime
    valid_at: datetime | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    status: Literal["committed", "retracted"] = "committed"
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)


class ValidationIssue(BaseModel):
    """可机器处理、可展示给用户的校验问题。"""

    model_config = ConfigDict(extra="forbid")

    code: Literal["empty_quote", "quote_not_found", "invalid_candidate"]
    message: str = Field(min_length=1)
    candidate_index: int = Field(ge=0)


class MemoryAuditEvent(BaseModel):
    """记忆写入/替换等不可变审计事件。"""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1)
    memory_id: str = Field(min_length=1)
    action: Literal["created", "replaced"]
    occurred_at: datetime
