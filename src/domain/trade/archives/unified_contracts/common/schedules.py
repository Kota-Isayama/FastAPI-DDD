from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class Event:
    index: int
    fixing_date: date
    settlement_date: date

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "fixing_date": self.fixing_date.isoformat(),
            "settlement_date": self.settlement_date.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        return cls(
            index=int(data["index"]),
            fixing_date=date.fromisoformat(data["fixing_date"]),
            settlement_date=date.fromisoformat(data["settlement_date"]),
        )


@dataclass(frozen=True)
class EventSchedule:
    events: tuple[Event, ...]
    role: str = "generic"

    def __post_init__(self) -> None:
        if not self.events:
            raise ValueError("events must not be empty")
        indexes = [e.index for e in self.events]
        if indexes != list(range(len(indexes))):
            raise ValueError("event indexes must be contiguous starting from 0")

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "event_schedule", "role": self.role, "events": [e.to_dict() for e in self.events]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventSchedule":
        return cls(
            events=tuple(Event.from_dict(x) for x in data["events"]),
            role=data.get("role", "generic"),
        )


@dataclass(frozen=True)
class PeriodicScheduleSpec:
    start_date: date
    end_date: date
    frequency: str
    settlement_lag_days: int = 0
    business_day_adjustment: str = "following"
    holiday_calendar: str | None = None
    role: str = "generic"

    def __post_init__(self) -> None:
        if self.start_date > self.end_date:
            raise ValueError("start_date must be <= end_date")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "periodic_schedule",
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "frequency": self.frequency,
            "settlement_lag_days": self.settlement_lag_days,
            "business_day_adjustment": self.business_day_adjustment,
            "holiday_calendar": self.holiday_calendar,
            "role": self.role,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PeriodicScheduleSpec":
        return cls(
            start_date=date.fromisoformat(data["start_date"]),
            end_date=date.fromisoformat(data["end_date"]),
            frequency=data["frequency"],
            settlement_lag_days=int(data.get("settlement_lag_days", 0)),
            business_day_adjustment=data.get("business_day_adjustment", "following"),
            holiday_calendar=data.get("holiday_calendar"),
            role=data.get("role", "generic"),
        )


@dataclass(frozen=True)
class ObservationWindow:
    observation_dates: tuple[date, ...]
    start_payoff_index: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    role: str = "observation"

    def __post_init__(self) -> None:
        if not self.observation_dates:
            raise ValueError("observation_dates must not be empty")
        if self.start_payoff_index is not None and self.start_date is not None:
            raise ValueError("use either start_payoff_index or start_date")

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_dates": [d.isoformat() for d in self.observation_dates],
            "start_payoff_index": self.start_payoff_index,
            "start_date": None if self.start_date is None else self.start_date.isoformat(),
            "end_date": None if self.end_date is None else self.end_date.isoformat(),
            "role": self.role,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ObservationWindow":
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        return cls(
            observation_dates=tuple(date.fromisoformat(x) for x in data["observation_dates"]),
            start_payoff_index=data.get("start_payoff_index"),
            start_date=None if start_date is None else date.fromisoformat(start_date),
            end_date=None if end_date is None else date.fromisoformat(end_date),
            role=data.get("role", "observation"),
        )


ScheduleLike = EventSchedule | PeriodicScheduleSpec


def schedule_from_dict(data: dict[str, Any]) -> ScheduleLike:
    kind = data["kind"]
    if kind == "event_schedule":
        return EventSchedule.from_dict(data)
    if kind == "periodic_schedule":
        return PeriodicScheduleSpec.from_dict(data)
    raise ValueError(f"unknown schedule kind: {kind}")
