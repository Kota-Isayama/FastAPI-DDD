from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .schedules import ScheduleLike, schedule_from_dict


@dataclass(frozen=True)
class ScheduleArchive:
    schedule_id: str
    original_schedule: ScheduleLike

    def to_dict(self) -> dict[str, Any]:
        return {
            "schedule_id": self.schedule_id,
            "original_schedule": self.original_schedule.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScheduleArchive":
        return cls(
            schedule_id=data["schedule_id"],
            original_schedule=schedule_from_dict(data["original_schedule"]),
        )


@dataclass(frozen=True)
class CashflowOverride:
    edited_by: str
    edited_at: datetime
    reason: str
    new_amount_description: str | None = None
    new_payment_date: str | None = None
    new_active: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "edited_by": self.edited_by,
            "edited_at": self.edited_at.isoformat(),
            "reason": self.reason,
            "new_amount_description": self.new_amount_description,
            "new_payment_date": self.new_payment_date,
            "new_active": self.new_active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CashflowOverride":
        return cls(
            edited_by=data["edited_by"],
            edited_at=datetime.fromisoformat(data["edited_at"]),
            reason=data["reason"],
            new_amount_description=data.get("new_amount_description"),
            new_payment_date=data.get("new_payment_date"),
            new_active=data.get("new_active"),
        )


@dataclass
class CashflowRecord:
    cashflow_id: str
    source_schedule_id: str
    source_event_index: int
    view_kind: str
    leg_label: str
    currency: str
    original_amount_description: str
    current_amount_description: str
    original_payment_date: str
    current_payment_date: str
    active: bool = True
    overrides: list[CashflowOverride] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def apply_override(self, override: CashflowOverride) -> None:
        if override.new_amount_description is not None:
            self.current_amount_description = override.new_amount_description
        if override.new_payment_date is not None:
            self.current_payment_date = override.new_payment_date
        if override.new_active is not None:
            self.active = override.new_active
        self.overrides.append(override)

    @property
    def is_edited(self) -> bool:
        return bool(self.overrides)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cashflow_id": self.cashflow_id,
            "source_schedule_id": self.source_schedule_id,
            "source_event_index": self.source_event_index,
            "view_kind": self.view_kind,
            "leg_label": self.leg_label,
            "currency": self.currency,
            "original_amount_description": self.original_amount_description,
            "current_amount_description": self.current_amount_description,
            "original_payment_date": self.original_payment_date,
            "current_payment_date": self.current_payment_date,
            "active": self.active,
            "overrides": [x.to_dict() for x in self.overrides],
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
            original_amount_description=data["original_amount_description"],
            current_amount_description=data["current_amount_description"],
            original_payment_date=data["original_payment_date"],
            current_payment_date=data["current_payment_date"],
            active=bool(data.get("active", True)),
            overrides=[CashflowOverride.from_dict(x) for x in data.get("overrides", [])],
            metadata=dict(data.get("metadata", {})),
        )
