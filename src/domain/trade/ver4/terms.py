from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# === CORE
@dataclass(frozen=True)
class ProductIdentity:
    family: str
    type_name: str
    version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "type_name": self.type_name,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProductIdentity":
        return cls(
            family=data["family"],
            type_name=data["type_name"],
            version=data.get("version", "1.0"),
        )


# === CORE
@dataclass(frozen=True)
class UnderlyingRef:
    name: str
    asset_class: str = "FX"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "asset_class": self.asset_class,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UnderlyingRef":
        return cls(
            name=data["name"],
            asset_class=data.get("asset_class", "FX"),
        )