from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProductIdentity:
    family: str
    type_name: str
    version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {"family": self.family, "type_name": self.type_name, "version": self.version}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProductIdentity":
        return cls(
            family=data["family"],
            type_name=data["type_name"],
            version=data.get("version", "1.0"),
        )
