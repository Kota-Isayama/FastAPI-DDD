from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal


@dataclass(frozen=True)
class ExternalTradeRef:
    system_name: str
    external_trade_id: str
    target_revision_no: int
    mode: Literal["create", "update", "cancel"] = "create"
    issued_at: datetime = datetime.min
    status: str = "issued"

    def to_dict(self) -> dict[str, Any]:
        return {
            "system_name": self.system_name,
            "external_trade_id": self.external_trade_id,
            "target_revision_no": self.target_revision_no,
            "mode": self.mode,
            "issued_at": self.issued_at.isoformat(),
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExternalTradeRef":
        return cls(
            system_name=data["system_name"],
            external_trade_id=data["external_trade_id"],
            target_revision_no=int(data["target_revision_no"]),
            mode=data.get("mode", "create"),
            issued_at=datetime.fromisoformat(data["issued_at"]),
            status=data.get("status", "issued"),
        )


@dataclass(frozen=True)
class ExternalComponentRef:
    system_name: str
    component_kind: str
    component_key: str
    external_component_id: str
    parent_external_trade_id: str
    target_revision_no: int
    mode: Literal["create", "update", "cancel"] = "create"
    issued_at: datetime = datetime.min
    status: str = "issued"

    def to_dict(self) -> dict[str, Any]:
        return {
            "system_name": self.system_name,
            "component_kind": self.component_kind,
            "component_key": self.component_key,
            "external_component_id": self.external_component_id,
            "parent_external_trade_id": self.parent_external_trade_id,
            "target_revision_no": self.target_revision_no,
            "mode": self.mode,
            "issued_at": self.issued_at.isoformat(),
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExternalComponentRef":
        return cls(
            system_name=data["system_name"],
            component_kind=data["component_kind"],
            component_key=data["component_key"],
            external_component_id=data["external_component_id"],
            parent_external_trade_id=data["parent_external_trade_id"],
            target_revision_no=int(data["target_revision_no"]),
            mode=data.get("mode", "create"),
            issued_at=datetime.fromisoformat(data["issued_at"]),
            status=data.get("status", "issued"),
        )
