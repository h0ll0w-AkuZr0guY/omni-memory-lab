from typing import Any, Protocol

from omni_memory.schemas.platform import AssetInput, MemoryInput


class MemoryAdapter(Protocol):
    """应用适配器只负责把应用数据映射到通用平台协议。"""

    application_name: str

    def to_memory_input(self, event: Any) -> MemoryInput: ...

    def to_asset_input(self, asset: Any) -> AssetInput: ...


class DictMemoryAdapter:
    """面向 JSON/dict 事件的通用适配器，适合 HTTP webhook 和简单集成。"""

    application_name = "generic-dict"

    def to_memory_input(self, event: dict[str, Any]) -> MemoryInput:
        return MemoryInput.model_validate(event)

    def to_asset_input(self, asset: dict[str, Any]) -> AssetInput:
        return AssetInput.model_validate(asset)
