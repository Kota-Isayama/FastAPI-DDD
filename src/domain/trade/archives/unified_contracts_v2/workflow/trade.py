from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..common.cashflows import CashflowRecord, ScheduleArchive
from ..common.representations import TradeRepresentation, representation_from_dict
from ..products import Contract, contract_from_dict


@dataclass(frozen=True)
class IndicationSnapshot:
    source_payload: dict[str, Any]
    captured_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {"source_payload": self.source_payload, "captured_at": self.captured_at.isoformat()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IndicationSnapshot":
        return cls(source_payload=dict(data["source_payload"]), captured_at=datetime.fromisoformat(data["captured_at"]))


@dataclass(frozen=True)
class ExternalTradeRef:
    system_name: str
    external_trade_id: str
    target_revision_no: int
    issued_at: datetime
    status: str = "issued"

    def to_dict(self) -> dict[str, Any]:
        return {
            "system_name": self.system_name,
            "external_trade_id": self.external_trade_id,
            "target_revision_no": self.target_revision_no,
            "issued_at": self.issued_at.isoformat(),
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExternalTradeRef":
        return cls(
            system_name=data["system_name"],
            external_trade_id=data["external_trade_id"],
            target_revision_no=int(data["target_revision_no"]),
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
    issued_at: datetime
    status: str = "issued"

    def to_dict(self) -> dict[str, Any]:
        return {
            "system_name": self.system_name,
            "component_kind": self.component_kind,
            "component_key": self.component_key,
            "external_component_id": self.external_component_id,
            "parent_external_trade_id": self.parent_external_trade_id,
            "target_revision_no": self.target_revision_no,
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
            issued_at=datetime.fromisoformat(data["issued_at"]),
            status=data.get("status", "issued"),
        )


@dataclass(frozen=True)
class TradeSnapshot:
    revision_no: int
    created_at: datetime
    created_by: str
    reason: str
    contract: Contract
    representation: TradeRepresentation
    trade_payoff_scheme: str
    schedule_archives: tuple[ScheduleArchive, ...]
    cashflows: tuple[CashflowRecord, ...]
    comments: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision_no": self.revision_no,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "reason": self.reason,
            "contract": self.contract.to_dict(),
            "representation": self.representation.to_dict(),
            "trade_payoff_scheme": self.trade_payoff_scheme,
            "schedule_archives": [x.to_dict() for x in self.schedule_archives],
            "cashflows": [x.to_dict() for x in self.cashflows],
            "comments": list(self.comments),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TradeSnapshot":
        return cls(
            revision_no=int(data["revision_no"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            created_by=data["created_by"],
            reason=data["reason"],
            contract=contract_from_dict(data["contract"]),
            representation=representation_from_dict(data["representation"]),
            trade_payoff_scheme=data["trade_payoff_scheme"],
            schedule_archives=tuple(ScheduleArchive.from_dict(x) for x in data["schedule_archives"]),
            cashflows=tuple(CashflowRecord.from_dict(x) for x in data["cashflows"]),
            comments=tuple(data.get("comments", [])),
        )


@dataclass
class TradeDraft:
    draft_id: str
    indication_snapshot: IndicationSnapshot
    snapshots: list[TradeSnapshot]
    status: str = "DRAFT"
    external_trade_refs: list[ExternalTradeRef] = field(default_factory=list)
    external_component_refs: list[ExternalComponentRef] = field(default_factory=list)

    @property
    def current_snapshot(self) -> TradeSnapshot:
        if not self.snapshots:
            raise ValueError("trade draft has no snapshots")
        return self.snapshots[-1]

    @property
    def revision_no(self) -> int:
        return self.current_snapshot.revision_no

    @property
    def contract(self) -> Contract:
        return self.current_snapshot.contract

    @property
    def cashflows(self) -> tuple[CashflowRecord, ...]:
        return self.current_snapshot.cashflows

    def add_snapshot(self, *, created_by: str, reason: str, created_at: datetime, contract: Contract | None = None,
                     representation: TradeRepresentation | None = None, trade_payoff_scheme: str | None = None,
                     schedule_archives: tuple[ScheduleArchive, ...] | list[ScheduleArchive] | None = None,
                     cashflows: tuple[CashflowRecord, ...] | list[CashflowRecord] | None = None,
                     comments: tuple[str, ...] | list[str] | None = None) -> TradeSnapshot:
        base = self.current_snapshot
        snap = TradeSnapshot(
            revision_no=base.revision_no + 1,
            created_at=created_at,
            created_by=created_by,
            reason=reason,
            contract=base.contract if contract is None else contract,
            representation=base.representation if representation is None else representation,
            trade_payoff_scheme=base.trade_payoff_scheme if trade_payoff_scheme is None else trade_payoff_scheme,
            schedule_archives=base.schedule_archives if schedule_archives is None else tuple(schedule_archives),
            cashflows=base.cashflows if cashflows is None else tuple(cashflows),
            comments=base.comments if comments is None else tuple(comments),
        )
        self.snapshots.append(snap)
        return snap

    def submit_for_approval(self) -> None:
        if self.status != "DRAFT":
            raise ValueError("only DRAFT can be submitted")
        self.status = "PENDING_APPROVAL"

    def approve(self) -> None:
        if self.status != "PENDING_APPROVAL":
            raise ValueError("only PENDING_APPROVAL can be approved")
        self.status = "APPROVED"

    def confirm(self) -> None:
        if self.status != "APPROVED":
            raise ValueError("only APPROVED can be confirmed")
        self.status = "CONFIRMED"

    def register_external_trade_ref(self, ref: ExternalTradeRef) -> None:
        self.external_trade_refs.append(ref)

    def register_external_component_ref(self, ref: ExternalComponentRef) -> None:
        self.external_component_refs.append(ref)

    def to_dict(self) -> dict[str, Any]:
        return {
            "draft_id": self.draft_id,
            "indication_snapshot": self.indication_snapshot.to_dict(),
            "snapshots": [x.to_dict() for x in self.snapshots],
            "status": self.status,
            "external_trade_refs": [x.to_dict() for x in self.external_trade_refs],
            "external_component_refs": [x.to_dict() for x in self.external_component_refs],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TradeDraft":
        return cls(
            draft_id=data["draft_id"],
            indication_snapshot=IndicationSnapshot.from_dict(data["indication_snapshot"]),
            snapshots=[TradeSnapshot.from_dict(x) for x in data["snapshots"]],
            status=data.get("status", "DRAFT"),
            external_trade_refs=[ExternalTradeRef.from_dict(x) for x in data.get("external_trade_refs", [])],
            external_component_refs=[ExternalComponentRef.from_dict(x) for x in data.get("external_component_refs", [])],
        )
