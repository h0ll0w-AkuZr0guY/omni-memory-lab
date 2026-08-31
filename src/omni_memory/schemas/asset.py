from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AssetKind = Literal["image", "audio", "video", "document"]


class AssetRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    kind: AssetKind
    size_bytes: int = Field(ge=0)
    source_document_id: str | None = None
    sha256: str | None = None
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)
