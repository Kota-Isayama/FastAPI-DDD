from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .schedules import ScheduleLike, schedule_from_dict


@dataclass(frozen=True)
class ScheduleArchive:
    schedule_id: str
    original_schedule: ScheduleLike

    def to_dict(self) -> dict[str, Any]:
        return {"schedule_id": self.schedule_id, "original_schedule": self.original_schedule.to_dict()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScheduleArchive":
        return cls(schedule_id=data["schedule_id"], original_schedule=schedule_from_dict(data["original_schedule"]))


@dataclass(frozen=True)
class CashflowRecord:
    cashflow_id: str
    source_schedule_id: str
    source_event_index: int
    view_kind: str
    leg_label: str
    currency: str
    amount_description: str
    payment_date: str
    active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cashflow_id": self.cashflow_id,
            "source_schedule_id": self.source_schedule_id,
            "source_event_index": self.source_event_index,
            "view_kind": self.view_kind,
            "leg_label": self.leg_label,
            "currency": self.currency,
            "amount_description": self.amount_description,
            "payment_date": self.payment_date,
            "active": self.active,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CashflowRecord":
        return cls(
            cashflow_id=data["cashflow_id"],
            source_schedule_id=data["source_schedule_id"],
            source_event_index=int(data["source_event_index"]),
            view_kind=data["view_kind"],
            leg_label=data["leg_label"],
            currency=data["currency"],
            amount_description=data["amount_description"],
            payment_date=data["payment_date"],
            active=bool(data.get("active", True)),
            metadata=dict(data.get("metadata", {})),
        )
