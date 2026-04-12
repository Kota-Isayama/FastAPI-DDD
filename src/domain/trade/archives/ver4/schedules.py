from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, ClassVar, Protocol


# === NEW
# 未展開 schedule spec と展開済み schedule を分ける。


# =========================
# Expanded / concrete forms
# =========================

@dataclass(frozen=True)
class EventSchedule:
    """
    展開済みの payoff event schedule。
    payoff index を持つので StepByIndexTerm と対応しやすい。
    """
    items: tuple[tuple[int, date, date], ...]  # (payoff_index, event_date, settlement_date)
    role: str = "generic"

    def __post_init__(self) -> None:
        if not self.items:
            raise ValueError("event schedule items must not be empty")

        indexes = [x[0] for x in self.items]
        if indexes != list(range(len(indexes))):
            raise ValueError("payoff indexes must be contiguous starting from 0")

        event_dates = [x[1] for x in self.items]
        if event_dates != sorted(event_dates):
            raise ValueError("event dates must be sorted ascending")

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "items": [
                {
                    "payoff_index": payoff_index,
                    "event_date": event_date.isoformat(),
                    "settlement_date": settlement_date.isoformat(),
                }
                for payoff_index, event_date, settlement_date in self.items
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
        if tuple(sorted(self.dates)) != self.dates:
            raise ValueError("observation dates must be sorted ascending")

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "dates": [d.isoformat() for d in self.dates],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ObservationDates":
        return cls(
            dates=tuple(date.fromisoformat(x) for x in data["dates"]),
            role=data.get("role", "observation"),
        )


# =========================
# Unexpanded schedule specs
# =========================

class ScheduleSpec(Protocol):
    kind: ClassVar[str]

    def to_dict(self) -> dict[str, Any]:
        ...


# === NEW
@dataclass(frozen=True)
class ExplicitEventScheduleSpec:
    """
    すでに展開済みの日付列を spec として保持したい場合。
    """
    kind: ClassVar[str] = "explicit_event_schedule"
    schedule: EventSchedule

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "schedule": self.schedule.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExplicitEventScheduleSpec":
        return cls(schedule=EventSchedule.from_dict(data["schedule"]))


# === NEW
@dataclass(frozen=True)
class PeriodicScheduleSpec:
    """
    未展開の schedule を保持するための spec。
    business day adjustment や holiday calendar もここに自然に乗る。
    """
    kind: ClassVar[str] = "periodic_schedule"

    start_date: date
    end_date: date
    frequency: str  # monthly / quarterly / weekly ...
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


# === NEW
@dataclass(frozen=True)
class RelativeStartSpec:
    """
    観測開始を契約開始から相対指定したい場合。
    by_payoff_index / by_date を両方サポート。
    """
    kind: ClassVar[str] = "relative_start"

    mode: str  # by_payoff_index / by_date
    payoff_index: int | None = None
    start_date: date | None = None

    def __post_init__(self) -> None:
        if self.mode == "by_payoff_index":
            if self.payoff_index is None:
                raise ValueError("payoff_index is required for by_payoff_index")
            if self.start_date is not None:
                raise ValueError("start_date must be None for by_payoff_index")
        elif self.mode == "by_date":
            if self.start_date is None:
                raise ValueError("start_date is required for by_date")
            if self.payoff_index is not None:
                raise ValueError("payoff_index must be None for by_date")
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
        start_date = data.get("start_date")
        return cls(
            mode=data["mode"],
            payoff_index=data.get("payoff_index"),
            start_date=None if start_date is None else date.fromisoformat(start_date),
        )


# === NEW
@dataclass(frozen=True)
class ObservationWindowSpec:
    """
    AKO や KI の観測窓。
    payoff スケジュールと一致しなくてもよい。
    観測開始を payoff index または日付で指定できる。
    """
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
            "observation_dates": (
                None if self.observation_dates is None else self.observation_dates.to_dict()
            ),
            "observation_schedule_spec": (
                None if self.observation_schedule_spec is None else self.observation_schedule_spec.to_dict()
            ),
            "start_spec": None if self.start_spec is None else self.start_spec.to_dict(),
            "end_date": None if self.end_date is None else self.end_date.isoformat(),
            "role": self.role,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ObservationWindowSpec":
        obs_dates = data.get("observation_dates")
        obs_sched = data.get("observation_schedule_spec")
        start_spec = data.get("start_spec")
        end_date = data.get("end_date")
        return cls(
            observation_dates=None if obs_dates is None else ObservationDates.from_dict(obs_dates),
            observation_schedule_spec=None if obs_sched is None else schedule_spec_from_dict(obs_sched),
            start_spec=None if start_spec is None else RelativeStartSpec.from_dict(start_spec),
            end_date=None if end_date is None else date.fromisoformat(end_date),
            role=data.get("role", "observation_window"),
        )


def schedule_spec_from_dict(data: dict[str, Any]) -> ScheduleSpec:
    kind = data["kind"]
    if kind == "explicit_event_schedule":
        return ExplicitEventScheduleSpec.from_dict(data)
    if kind == "periodic_schedule":
        return PeriodicScheduleSpec.from_dict(data)
    raise ValueError(f"unknown schedule spec kind: {kind}")