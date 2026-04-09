from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..common.identity import ProductIdentity
from ..common.schedules import ObservationWindow, ScheduleLike, schedule_from_dict
from ..common.terms import Term, term_from_dict


@dataclass(frozen=True)
class TARFLeg:
    strike: Term[float]
    ratio: Term[float]
    position: str  # sell_base / buy_base

    def to_dict(self) -> dict[str, Any]:
        return {
            "strike": self.strike.to_dict(),
            "ratio": self.ratio.to_dict(),
            "position": self.position,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TARFLeg":
        return cls(
            strike=term_from_dict(data["strike"]),
            ratio=term_from_dict(data["ratio"]),
            position=data["position"],
        )


@dataclass(frozen=True)
class TARFSpec:
    identity: ProductIdentity
    underlying: str
    settlement_currency: str
    base_notional: Term[float]
    payoff_style: str  # normal / gap / two_stage / collar
    payoff_schedule: ScheduleLike
    main_leg: TARFLeg
    target: Term[float]
    final_fixing_treatment: str = "full"
    barrier_type: str = "none"
    barrier_level: Term[float] | None = None
    barrier_window: ObservationWindow | None = None
    barrier_condition: str | None = None

    def validate(self) -> None:
        if self.identity.family != "TARF":
            raise ValueError("family must be TARF")
        if self.barrier_type == "none" and (self.barrier_level is not None or self.barrier_window is not None):
            raise ValueError("barrier fields must be empty when barrier_type is none")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "kind": "tarf",
            "identity": self.identity.to_dict(),
            "underlying": self.underlying,
            "settlement_currency": self.settlement_currency,
            "base_notional": self.base_notional.to_dict(),
            "payoff_style": self.payoff_style,
            "payoff_schedule": self.payoff_schedule.to_dict(),
            "main_leg": self.main_leg.to_dict(),
            "target": self.target.to_dict(),
            "final_fixing_treatment": self.final_fixing_treatment,
            "barrier_type": self.barrier_type,
            "barrier_level": None if self.barrier_level is None else self.barrier_level.to_dict(),
            "barrier_window": None if self.barrier_window is None else self.barrier_window.to_dict(),
            "barrier_condition": self.barrier_condition,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TARFSpec":
        barrier_level = data.get("barrier_level")
        barrier_window = data.get("barrier_window")
        return cls(
            identity=ProductIdentity.from_dict(data["identity"]),
            underlying=data["underlying"],
            settlement_currency=data["settlement_currency"],
            base_notional=term_from_dict(data["base_notional"]),
            payoff_style=data["payoff_style"],
            payoff_schedule=schedule_from_dict(data["payoff_schedule"]),
            main_leg=TARFLeg.from_dict(data["main_leg"]),
            target=term_from_dict(data["target"]),
            final_fixing_treatment=data.get("final_fixing_treatment", "full"),
            barrier_type=data.get("barrier_type", "none"),
            barrier_level=None if barrier_level is None else term_from_dict(barrier_level),
            barrier_window=None if barrier_window is None else ObservationWindow.from_dict(barrier_window),
            barrier_condition=data.get("barrier_condition"),
        )
