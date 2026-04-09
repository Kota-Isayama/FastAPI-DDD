from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..common.cashflows import CashflowOverride, CashflowRecord, ScheduleArchive
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


@dataclass
class TradeDraft:
    draft_id: str
    contract: Contract
    representation: TradeRepresentation
    indication_snapshot: IndicationSnapshot
    schedule_archives: list[ScheduleArchive]
    cashflows: list[CashflowRecord]
    status: str = "DRAFT"
    revision_no: int = 1
    comments: list[str] = field(default_factory=list)

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

    def apply_cashflow_override(self, cashflow_id: str, override: CashflowOverride) -> None:
        for cf in self.cashflows:
            if cf.cashflow_id == cashflow_id:
                cf.apply_override(override)
                self.revision_no += 1
                return
        raise KeyError(f"cashflow not found: {cashflow_id}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "draft_id": self.draft_id,
            "contract": self.contract.to_dict(),
            "representation": self.representation.to_dict(),
            "indication_snapshot": self.indication_snapshot.to_dict(),
            "schedule_archives": [x.to_dict() for x in self.schedule_archives],
            "cashflows": [x.to_dict() for x in self.cashflows],
            "status": self.status,
            "revision_no": self.revision_no,
            "comments": list(self.comments),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TradeDraft":
        return cls(
            draft_id=data["draft_id"],
            contract=contract_from_dict(data["contract"]),
            representation=representation_from_dict(data["representation"]),
            indication_snapshot=IndicationSnapshot.from_dict(data["indication_snapshot"]),
            schedule_archives=[ScheduleArchive.from_dict(x) for x in data["schedule_archives"]],
            cashflows=[CashflowRecord.from_dict(x) for x in data["cashflows"]],
            status=data.get("status", "DRAFT"),
            revision_no=int(data.get("revision_no", 1)),
            comments=list(data.get("comments", [])),
        )
