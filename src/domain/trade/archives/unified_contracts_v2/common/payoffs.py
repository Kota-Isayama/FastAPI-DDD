from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .schedules import ObservationWindow
from .terms import Term, term_from_dict

PayoffSchemeName = Literal["normal", "gap", "range_gap", "collar", "two_stage", "mixed"]


@dataclass(frozen=True)
class EuropeanKnockInBarrier:
    trigger_level: Term[float]
    observation_window: ObservationWindow
    breach_condition: str = "spot_lte_level"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "european_knock_in",
            "trigger_level": self.trigger_level.to_dict(),
            "observation_window": self.observation_window.to_dict(),
            "breach_condition": self.breach_condition,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EuropeanKnockInBarrier":
        return cls(
            trigger_level=term_from_dict(data["trigger_level"]),
            observation_window=ObservationWindow.from_dict(data["observation_window"]),
            breach_condition=data.get("breach_condition", "spot_lte_level"),
        )


@dataclass(frozen=True)
class ForwardPayoffLeg:
    kind: Literal["forward"] = "forward"
    position: str = "sell_base"
    strike: Term[float] | None = None
    ratio: Term[float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "position": self.position,
            "strike": None if self.strike is None else self.strike.to_dict(),
            "ratio": None if self.ratio is None else self.ratio.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ForwardPayoffLeg":
        s = data.get("strike")
        r = data.get("ratio")
        return cls(
            position=data.get("position", "sell_base"),
            strike=None if s is None else term_from_dict(s),
            ratio=None if r is None else term_from_dict(r),
        )


@dataclass(frozen=True)
class OptionPayoffLeg:
    kind: Literal["option"] = "option"
    option_type: str = "call"
    position: str = "buy"
    strike: Term[float] | None = None
    ratio: Term[float] | None = None
    barrier: EuropeanKnockInBarrier | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "option_type": self.option_type,
            "position": self.position,
            "strike": None if self.strike is None else self.strike.to_dict(),
            "ratio": None if self.ratio is None else self.ratio.to_dict(),
            "barrier": None if self.barrier is None else self.barrier.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OptionPayoffLeg":
        s = data.get("strike")
        r = data.get("ratio")
        b = data.get("barrier")
        return cls(
            option_type=data.get("option_type", "call"),
            position=data.get("position", "buy"),
            strike=None if s is None else term_from_dict(s),
            ratio=None if r is None else term_from_dict(r),
            barrier=None if b is None else EuropeanKnockInBarrier.from_dict(b),
        )


PayoffLeg = ForwardPayoffLeg | OptionPayoffLeg


def payoff_leg_from_dict(data: dict[str, Any]) -> PayoffLeg:
    if data["kind"] == "forward":
        return ForwardPayoffLeg.from_dict(data)
    if data["kind"] == "option":
        return OptionPayoffLeg.from_dict(data)
    raise ValueError(f"unknown payoff leg kind: {data['kind']}")


@dataclass(frozen=True)
class EventPayoffSpec:
    scheme_name: str
    legs: tuple[PayoffLeg, ...]

    def validate(self) -> None:
        if self.scheme_name == "normal":
            if len(self.legs) != 1 or not isinstance(self.legs[0], ForwardPayoffLeg):
                raise ValueError("normal payoff must have exactly one forward leg")
        elif self.scheme_name in {"gap", "range_gap", "collar"}:
            if len(self.legs) != 2:
                raise ValueError(f"{self.scheme_name} must have exactly two legs")
            call_legs = [x for x in self.legs if isinstance(x, OptionPayoffLeg) and x.option_type == "call"]
            put_legs = [x for x in self.legs if isinstance(x, OptionPayoffLeg) and x.option_type == "put"]
            if len(call_legs) != 1 or len(put_legs) != 1:
                raise ValueError(f"{self.scheme_name} requires one call and one put")
            call_leg = call_legs[0]
            put_leg = put_legs[0]
            if call_leg.position != "buy" or put_leg.position != "sell":
                raise ValueError(f"{self.scheme_name} requires buy call and sell put")
            if self.scheme_name in {"gap", "range_gap"} and put_leg.barrier is None:
                raise ValueError(f"{self.scheme_name} requires KI on put leg")
            if self.scheme_name == "collar" and (call_leg.barrier is not None or put_leg.barrier is not None):
                raise ValueError("collar must not have barriers")
        elif self.scheme_name == "two_stage":
            if len(self.legs) != 1 or not isinstance(self.legs[0], ForwardPayoffLeg):
                raise ValueError("two_stage event payoff must be a single forward leg")
        elif self.scheme_name == "mixed":
            pass
        else:
            raise ValueError(f"unsupported scheme_name: {self.scheme_name}")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {"scheme_name": self.scheme_name, "legs": [x.to_dict() for x in self.legs]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventPayoffSpec":
        obj = cls(scheme_name=data["scheme_name"], legs=tuple(payoff_leg_from_dict(x) for x in data["legs"]))
        obj.validate()
        return obj


@dataclass(frozen=True)
class PayoffProgram:
    default_event_payoff: EventPayoffSpec
    event_overrides: dict[int, EventPayoffSpec] | None = None

    def event_payoff_at(self, event_index: int) -> EventPayoffSpec:
        if self.event_overrides and event_index in self.event_overrides:
            return self.event_overrides[event_index]
        return self.default_event_payoff

    def classify_trade_scheme(self) -> str:
        names = {self.default_event_payoff.scheme_name}
        if self.event_overrides:
            names |= {v.scheme_name for v in self.event_overrides.values()}
        if len(names) == 1:
            only = next(iter(names))
            return only
        return "mixed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "default_event_payoff": self.default_event_payoff.to_dict(),
            "event_overrides": None if self.event_overrides is None else {str(k): v.to_dict() for k, v in self.event_overrides.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PayoffProgram":
        raw = data.get("event_overrides")
        overrides = None if raw is None else {int(k): EventPayoffSpec.from_dict(v) for k, v in raw.items()}
        return cls(default_event_payoff=EventPayoffSpec.from_dict(data["default_event_payoff"]), event_overrides=overrides)


def classify_trade_payoff(program: PayoffProgram) -> str:
    return program.classify_trade_scheme()
