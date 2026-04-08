from __future__ import annotations

import dataclasses
import datetime
from multiprocessing import Value
from typing import Any, ClassVar, Generic, Protocol, Self, TypeVar, runtime_checkable


T = TypeVar("T")

# ----------------------------
# 共有シリアライゼーションプロトコル
# ----------------------------

@runtime_checkable  # なんか非推奨らしい isinstanceが使えるようになるらしいが、メソッドの名前だけ（シグネチャを見ない）で判定するから。
class Serializable(Protocol):
    def to_dict(self) -> dict[str, Any]
        ...

    
# ----------------------------
# Identity / reference
# ----------------------------

@dataclasses.dataclass(frozen=True)
class ProductIdentity:
    family: str
    type_name: str
    version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "type_name": self.type_name,
            "version": self.version,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            family=data["family"],
            type_name=data["type_name"],
            version=data.get("version", "1.0")
        )
    

@dataclasses.dataclass(frozen=True)
class UnderlyingRef:
    name: str
    asset_class: str = "FX"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "asset_class": self.asset_class,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            name=data["name"],
            asset_class=data.get("asset_class", "FX")
        )
    

# ---------------------------
# Terms: time-varying values
# ---------------------------

class Term(Protocol, Generic[T]):
    def to_dict(self) -> dict[str, Any]:
        ...


@dataclasses.dataclass(frozen=True)
class ConstantTerm(Generic[T]):
    kind: ClassVar[str] = "constant"
    value: T

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "value": self.value}
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(value=data["value"])
    

@dataclasses.dataclass(frozen=True)
class StepByIndexTerm(Generic[T]):
    """
    例:
        [(0, 145.0), (6, 147.0)]
        -> event_index 0..5では145.0、6以降では147.0
    """
    kind: ClassVar[str] = "step_by_index"
    steps: tuple[tuple[int, T], ...]

    def __post_init__(self) -> None:
        if not self.steps:
            raise ValueError("steps must not be empty.")
        starts = [x for x, _ in self.steps]
        if starts != sorted(starts):
            raise ValueError("steps must be sorted ascending by start index.")  # これは必要か？
        
    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "steps": [[i, v] for i, v in self.steps],
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StepByIndexTerm[Any]":
        return cls(steps=tuple((int(i), v) for i, v in data["steps"]))
    

@dataclasses.dataclass(frozen=True)
class DateRangeTerm(Generic[T]):
    kind: ClassVar[str] = "data_range"
    ranges: tuple[tuple[datetime.date, datetime.date, T], ...]

    def __post_init__(self) -> None:
        if not self.ranges:
            raise ValueError("ranges must not be empty.")
        for start, end, _ in self.ranges:
            if start > end:
                raise ValueError("range start must be <= end.")
            
    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "ranges": [
                {
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "value": value,
                }
                for start, end, value in self.ranges
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DateRangeTerm[Any]":
        return cls(
            ranges=tuple(
                (
                    datetime.date.fromisoformat(item["start"]),
                    datetime.date.fromisoformat(item["end"]),
                    item["value"],
                )
                for item in data["ranges"]
            )
        )
    

def term_from_dict(data: dict[str, Any]) -> Term[Any]:
    kind = data["kind"]
    if kind == "constant":
        return ConstantTerm.from_dict(data)
    if kind == "step_by_index":
        return StepByIndexTerm.from_dict(data)
    if kind == "date_range":
        return DateRangeTerm.from_dict(data)
    raise ValueError(f"unknown term kind: {kind}")


# ---------------------------
# スケジュール
# ---------------------------

@dataclasses.dataclass(frozen=True)
class IndexedSchedule:
    """
    fixing / observation / coupon determination date と settlement dateの列。
    変則 scheduleを素直に持つため、ペア列で表現する。
    """
    items: tuple[tuple[datetime.date, datetime.date], ...]
    role: str = "generic"

    def __post_init__(self) -> None:
        if not self.items:
            raise ValueError("schedule items must not be empty.")
        fixing_dates = [fix for fix, _ in self.items]
        if fixing_dates != sorted(fixing_dates):
            raise ValueError("schedule dates must be sorted ascending.")
        
    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "items": [
                {
                    "event_date": event_date.isoformat(),
                    "settlement_date": settlement_date.isoformat(),
                }
                for event_date, settlement_date in self.items
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IndexedSchedule":
        return cls(
            items=tuple(
                (
                    datetime.date.fromisoformat(item["event_date"]),
                    datetime.date.fromisoformat(item["settlement_date"]),
                )
                for item in data["items"]
            ),
            role=data.get("role", "generic"),
        )
    

@dataclasses.dataclass(frozen=True)
class ObservationSchedule:
    dates: tuple[datetime.date, ...]
    role: str = "observation"

    def __post_init__(self) -> None:
        if not self.dates:
            raise ValueError("observation schedule dates must not be empty.")
        if tuple(sorted(self.dates)) != self.dates:
            raise ValueError("observation schedule dates must be sorted ascending.")
        
    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "dates": [d.isoformat() for d in self.dates],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ObservationSchedule":
        return cls(
            dates=tuple(datetime.date.fromisoformat(x) for x in data["dates"]),
            role=data.get("role", "observation"),
        )
    

# ------------------------
# コンポーネントベースクラス
# ------------------------

class ProductComponent(Protocol):
    component_type: ClassVar[str]

    def to_dict(self) -> dict[str, Any]:
        ...

class PayoffComponent(ProductComponent, Protocol):
    component_type: ClassVar[str]


class BarrierComponent(ProductComponent, Protocol):
    component_type: ClassVar[str]


class AccrualComponent(ProductComponent, Protocol):
    component_type: ClassVar[str]


class RedemptionComponent(ProductComponent, Protocol):
    component_type: ClassVar[str]


class SettlementComponent(ProductComponent, Protocol):
    component_type: ClassVar[str]


# ----------------------
# leg level barrier
# ----------------------

class LegBarrierSpec(Protocol):
    kind: ClassVar[str]

    def to_dict(self) -> dict[str, Any]:
        ...


@dataclasses.dataclass(frozen=True)
class NoLegBarrier:
    kind: ClassVar[str] = "none"

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind}
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls()
    

@dataclasses.dataclass(frozen=True)
class EuropeanKnockInLegBarrier:
    kind: ClassVar[str] = "european_knock_in"

    trigger_level: Term[float]
    observation_schedule: ObservationSchedule
    breach_condition: str  # spot_lte_level / spot_gte_level  # なんだろう


    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "trigger_level": self.trigger_level.to_dict(),
            "observation_schedule": self.observation_schedule.to_dict(),
            "breach_condition": self.breach_condition,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EuropeanKnockInLegBarrier":
        return cls(
            trigger_level=term_from_dict(data["trigger_level"]),
            observation_schedule=ObservationSchedule.from_dict(data["observation_schedule"]),
            breach_condition=data["breach_condition"],
        )


def leg_barrier_from_dict(data: dict[str, Any]) -> LegBarrierSpec:
    kind = data["kind"]
    if kind == "none":
        return NoLegBarrier.from_dict(data)
    if kind == "european_knock_in":
        return EuropeanKnockInLegBarrier.from_dict(data)
    raise ValueError(f"unknown leg barrier kind: {kind}")

# -----------------------------------
# Leg specs for structured FX payoff
# -----------------------------------

class FXLegSpec(Protocol):
    kind: ClassVar[str]

    def to_dict(self) -> dict[str, Any]:
        ...


@dataclasses.dataclass(frozen=True)
class FxForwardLegSpec:
    """
    レシオフォワード等のfoward-like payoff leg
    """
    kind: ClassVar[str] = "fx_forward_leg"

    position: str  # buy_base / sell_base / long / short
    strike: Term[float]
    quantity_multiplier: Term[float]  # なんだろう？

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "position": self.position,
            "strike": self.strike.to_dict(),
            "quantity_multiplier": self.quantity_multiplier.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FXForwardLegSpec":
        return cls(
            position=data["position"],
            strike=term_from_dict(data["strike"]),
            quantity_multiplier=term_from_dict(data["quantity_multiplier"]),
        )

