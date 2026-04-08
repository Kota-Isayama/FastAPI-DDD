from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, ClassVar, Protocol


@dataclass(frozen=True)
class EventSchedule:
    items: tuple[tuple[int, date, date], ...]
    role: str = "generic"

    def __post_init__(self) -> None:
        if not self.items:
            raise ValueError("schedule items must not be empty")
        indexes = [x[0] for x in self.items]
        if indexes != list(range(len(indexes))):
            raise ValueError("payoff indexes must be contiguous from 0")
        event_dates = [x[1] for x in self.items]
        if event_dates != sorted(event_dates):
            raise ValueError("event dates must be sorted")

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "items": [
                {
                    "payoff_index": i,
                    "event_date": event_date.isoformat(),
                    "settlement_date": settlement_date.isoformat(),
                }
                for i, event_date, settlement_date in self.items
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventSchedule":
        return cls(
            items=tuple(
                (
                    int(item["payoff_index"]),
                    date.fromisoformat(item["event_date"]),
                    date.fromisoformat(item["settlement_date"]),
                )
                for item in data["items"]
            ),
            role=data.get("role", "generic"),
        )


@dataclass(frozen=True)
class ObservationDates:
    dates: tuple[date, ...]
    role: str = "observation"

    def __post_init__(self) -> None:
        if not self.dates:
            raise ValueError("observation dates must not be empty")
        if self.dates != tuple(sorted(self.dates)):
            raise ValueError("observation dates must be sorted")

    def to_dict(self) -> dict[str, Any]:
        return {"role": self.role, "dates": [x.isoformat() for x in self.dates]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ObservationDates":
        return cls(
            dates=tuple(date.fromisoformat(x) for x in data["dates"]),
            role=data.get("role", "observation"),
        )


class ScheduleSpec(Protocol):
    kind: ClassVar[str]

    def to_dict(self) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class ExplicitEventScheduleSpec:
    kind: ClassVar[str] = "explicit_event_schedule"
    schedule: EventSchedule

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "schedule": self.schedule.to_dict()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExplicitEventScheduleSpec":
        return cls(schedule=EventSchedule.from_dict(data["schedule"]))


@dataclass(frozen=True)
class PeriodicScheduleSpec:
    kind: ClassVar[str] = "periodic_schedule"

    start_date: date
    end_date: date
    frequency: str
    settlement_lag_days: int = 0
    roll_convention: str = "none"
    business_day_adjustment: str = "following"
    holiday_calendar: str | None = None
    role: str = "generic"

    def __post_init__(self) -> None:
        if self.start_date > self.end_date:
            raise ValueError("start_date must be <= end_date")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "frequency": self.frequency,
            "settlement_lag_days": self.settlement_lag_days,
            "roll_convention": self.roll_convention,
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
            settlement_lag_days=data.get("settlement_lag_days", 0),
            roll_convention=data.get("roll_convention", "none"),
            business_day_adjustment=data.get("business_day_adjustment", "following"),
            holiday_calendar=data.get("holiday_calendar"),
            role=data.get("role", "generic"),
        )


@dataclass(frozen=True)
class RelativeStartSpec:
    kind: ClassVar[str] = "relative_start"
    mode: str
    payoff_index: int | None = None
    start_date: date | None = None

    def __post_init__(self) -> None:
        if self.mode == "by_payoff_index":
            if self.payoff_index is None or self.start_date is not None:
                raise ValueError("by_payoff_index requires payoff_index and forbids start_date")
        elif self.mode == "by_date":
            if self.start_date is None or self.payoff_index is not None:
                raise ValueError("by_date requires start_date and forbids payoff_index")
        else:
            raise ValueError("mode must be by_payoff_index or by_date")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "mode": self.mode,
            "payoff_index": self.payoff_index,
            "start_date": None if self.start_date is None else self.start_date.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RelativeStartSpec":
        raw = data.get("start_date")
        return cls(
            mode=data["mode"],
            payoff_index=data.get("payoff_index"),
            start_date=None if raw is None else date.fromisoformat(raw),
        )


@dataclass(frozen=True)
class ObservationWindowSpec:
    kind: ClassVar[str] = "observation_window"

    observation_dates: ObservationDates | None = None
    observation_schedule_spec: ScheduleSpec | None = None
    start_spec: RelativeStartSpec | None = None
    end_date: date | None = None
    role: str = "observation_window"

    def __post_init__(self) -> None:
        if self.observation_dates is None and self.observation_schedule_spec is None:
            raise ValueError("either observation_dates or observation_schedule_spec is required")
        if self.observation_dates is not None and self.observation_schedule_spec is not None:
            raise ValueError("only one of observation_dates or observation_schedule_spec may be set")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "observation_dates": None if self.observation_dates is None else self.observation_dates.to_dict(),
            "observation_schedule_spec": (
                None if self.observation_schedule_spec is None else self.observation_schedule_spec.to_dict()
            ),
            "start_spec": None if self.start_spec is None else self.start_spec.to_dict(),
            "end_date": None if self.end_date is None else self.end_date.isoformat(),
            "role": self.role,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ObservationWindowSpec":
        raw_end = data.get("end_date")
        raw_dates = data.get("observation_dates")
        raw_sched = data.get("observation_schedule_spec")
        raw_start = data.get("start_spec")
        return cls(
            observation_dates=None if raw_dates is None else ObservationDates.from_dict(raw_dates),
            observation_schedule_spec=None if raw_sched is None else schedule_spec_from_dict(raw_sched),
            start_spec=None if raw_start is None else RelativeStartSpec.from_dict(raw_start),
            end_date=None if raw_end is None else date.fromisoformat(raw_end),
            role=data.get("role", "observation_window"),
        )


def schedule_spec_from_dict(data: dict[str, Any]) -> ScheduleSpec:
    kind = data["kind"]
    if kind == "explicit_event_schedule":
        return ExplicitEventScheduleSpec.from_dict(data)
    if kind == "periodic_schedule":
        return PeriodicScheduleSpec.from_dict(data)
    raise ValueError(f"unknown schedule spec kind: {kind}")
