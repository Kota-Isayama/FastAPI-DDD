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
        return {
            "source_payload": self.source_payload,
            "captured_at": self.captured_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IndicationSnapshot":
        return cls(
            source_payload=dict(data["source_payload"]),
            captured_at=datetime.fromisoformat(data["captured_at"]),
        )


@dataclass(frozen=True)
class TradeSnapshot:
    revision_no: int
    created_at: datetime
    created_by: str
    reason: str
    contract: Contract
    representation: TradeRepresentation
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

    @property
    def current_snapshot(self) -> TradeSnapshot:
        if not self.snapshots:
            raise ValueError("trade draft has no snapshots")
        return self.snapshots[-1]

    @property
    def contract(self) -> Contract:
        return self.current_snapshot.contract

    @property
    def representation(self) -> TradeRepresentation:
        return self.current_snapshot.representation

    @property
    def schedule_archives(self) -> tuple[ScheduleArchive, ...]:
        return self.current_snapshot.schedule_archives

    @property
    def cashflows(self) -> tuple[CashflowRecord, ...]:
        return self.current_snapshot.cashflows

    @property
    def revision_no(self) -> int:
        return self.current_snapshot.revision_no

    def add_snapshot(
        self,
        *,
        created_by: str,
        reason: str,
        created_at: datetime,
        contract: Contract | None = None,
        representation: TradeRepresentation | None = None,
        schedule_archives: list[ScheduleArchive] | tuple[ScheduleArchive, ...] | None = None,
        cashflows: list[CashflowRecord] | tuple[CashflowRecord, ...] | None = None,
        comments: list[str] | tuple[str, ...] | None = None,
    ) -> TradeSnapshot:
        base = self.current_snapshot
        snapshot = TradeSnapshot(
            revision_no=base.revision_no + 1,
            created_at=created_at,
            created_by=created_by,
            reason=reason,
            contract=base.contract if contract is None else contract,
            representation=base.representation if representation is None else representation,
            schedule_archives=base.schedule_archives if schedule_archives is None else tuple(schedule_archives),
            cashflows=base.cashflows if cashflows is None else tuple(cashflows),
            comments=base.comments if comments is None else tuple(comments),
        )
        self.snapshots.append(snapshot)
        return snapshot

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "draft_id": self.draft_id,
            "indication_snapshot": self.indication_snapshot.to_dict(),
            "snapshots": [x.to_dict() for x in self.snapshots],
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TradeDraft":
        return cls(
            draft_id=data["draft_id"],
            indication_snapshot=IndicationSnapshot.from_dict(data["indication_snapshot"]),
            snapshots=[TradeSnapshot.from_dict(x) for x in data["snapshots"]],
            status=data.get("status", "DRAFT"),
        )
