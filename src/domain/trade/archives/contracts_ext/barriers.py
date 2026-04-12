from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Protocol

from .identity import UnderlyingRef
from .schedules import ObservationWindowSpec
from .terms import AnyTerm, term_from_dict


class LegBarrierSpec(Protocol):
    kind: ClassVar[str]

    def to_dict(self) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class NoLegBarrier:
    kind: ClassVar[str] = "none"

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NoLegBarrier":
        return cls()


@dataclass(frozen=True)
class EuropeanKnockInLegBarrier:
    kind: ClassVar[str] = "european_knock_in"
    trigger_level: AnyTerm
    observation_window: ObservationWindowSpec
    breach_condition: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "trigger_level": self.trigger_level.to_dict(),
            "observation_window": self.observation_window.to_dict(),
            "breach_condition": self.breach_condition,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EuropeanKnockInLegBarrier":
        return cls(
            trigger_level=term_from_dict(data["trigger_level"]),
            observation_window=ObservationWindowSpec.from_dict(data["observation_window"]),
            breach_condition=data["breach_condition"],
        )


LegBarrier = NoLegBarrier | EuropeanKnockInLegBarrier


def leg_barrier_from_dict(data: dict[str, Any]) -> LegBarrier:
    kind = data["kind"]
    if kind == "none":
        return NoLegBarrier.from_dict(data)
    if kind == "european_knock_in":
        return EuropeanKnockInLegBarrier.from_dict(data)
    raise ValueError(f"unknown leg barrier kind: {kind}")


class BarrierComponent(Protocol):
    component_type: ClassVar[str]
    kind: ClassVar[str]

    def to_dict(self) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class NoBarrier:
    component_type: ClassVar[str] = "barrier"
    kind: ClassVar[str] = "none"

    def to_dict(self) -> dict[str, Any]:
        return {"component_type": self.component_type, "kind": self.kind}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NoBarrier":
        return cls()


@dataclass(frozen=True)
class EuropeanKnockInBarrier:
    component_type: ClassVar[str] = "barrier"
    kind: ClassVar[str] = "european_knock_in"

    underlying: UnderlyingRef
    trigger_level: AnyTerm
    observation_window: ObservationWindowSpec
    breach_condition: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_type": self.component_type,
            "kind": self.kind,
            "underlying": self.underlying.to_dict(),
            "trigger_level": self.trigger_level.to_dict(),
            "observation_window": self.observation_window.to_dict(),
            "breach_condition": self.breach_condition,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EuropeanKnockInBarrier":
        return cls(
            underlying=UnderlyingRef.from_dict(data["underlying"]),
            trigger_level=term_from_dict(data["trigger_level"]),
            observation_window=ObservationWindowSpec.from_dict(data["observation_window"]),
            breach_condition=data["breach_condition"],
        )


@dataclass(frozen=True)
class AKOBarrier:
    component_type: ClassVar[str] = "barrier"
    kind: ClassVar[str] = "ako"

    underlying: UnderlyingRef
    trigger_level: AnyTerm
    observation_window: ObservationWindowSpec
    breach_condition: str
    action_on_breach: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_type": self.component_type,
            "kind": self.kind,
            "underlying": self.underlying.to_dict(),
            "trigger_level": self.trigger_level.to_dict(),
            "observation_window": self.observation_window.to_dict(),
            "breach_condition": self.breach_condition,
            "action_on_breach": self.action_on_breach,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AKOBarrier":
        return cls(
            underlying=UnderlyingRef.from_dict(data["underlying"]),
            trigger_level=term_from_dict(data["trigger_level"]),
            observation_window=ObservationWindowSpec.from_dict(data["observation_window"]),
            breach_condition=data["breach_condition"],
            action_on_breach=data["action_on_breach"],
        )


Barrier = NoBarrier | EuropeanKnockInBarrier | AKOBarrier


def barrier_from_dict(data: dict[str, Any]) -> Barrier:
    kind = data["kind"]
    if kind == "none":
        return NoBarrier.from_dict(data)
    if kind == "european_knock_in":
        return EuropeanKnockInBarrier.from_dict(data)
    if kind == "ako":
        return AKOBarrier.from_dict(data)
    raise ValueError(f"unknown barrier kind: {kind}")
