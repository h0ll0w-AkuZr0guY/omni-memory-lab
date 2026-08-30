from pydantic import BaseModel, ConfigDict, Field

from omni_memory.schemas.memory import FactCandidate


class FactExtraction(BaseModel):
    """模型一次抽取的候选事实集合；它们尚未提交到长期记忆。"""

    model_config = ConfigDict(extra="forbid")

    facts: list[FactCandidate] = Field(default_factory=list)
