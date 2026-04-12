from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..common.identity import ProductIdentity
from ..common.payoffs import PayoffProgram
from ..common.schedules import ObservationWindow, ScheduleLike, schedule_from_dict
from ..common.terms import Term, term_from_dict


@dataclass(frozen=True)
class TARFSpec:
    identity: ProductIdentity
    underlying: str
    settlement_currency: str
    base_notional: Term[float]
    payoff_schedule: ScheduleLike
    payoff_program: PayoffProgram
    target: Term[float]
    final_fixing_treatment: str = "full"
    product_barrier_type: str = "none"
    product_barrier_level: Term[float] | None = None
    product_barrier_window: ObservationWindow | None = None
    product_barrier_condition: str | None = None

    def validate(self) -> None:
        if self.identity.family != "TARF":
            raise ValueError("family must be TARF")

    @property
    def trade_payoff_scheme(self) -> str:
        return self.payoff_program.classify_trade_scheme()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "kind": "tarf",
            "identity": self.identity.to_dict(),
            "underlying": self.underlying,
            "settlement_currency": self.settlement_currency,
            "base_notional": self.base_notional.to_dict(),
            "payoff_schedule": self.payoff_schedule.to_dict(),
            "payoff_program": self.payoff_program.to_dict(),
            "target": self.target.to_dict(),
            "final_fixing_treatment": self.final_fixing_treatment,
            "product_barrier_type": self.product_barrier_type,
            "product_barrier_level": None if self.product_barrier_level is None else self.product_barrier_level.to_dict(),
            "product_barrier_window": None if self.product_barrier_window is None else self.product_barrier_window.to_dict(),
            "product_barrier_condition": self.product_barrier_condition,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TARFSpec":
        pbl = data.get("product_barrier_level")
        pbw = data.get("product_barrier_window")
        return cls(
            identity=ProductIdentity.from_dict(data["identity"]),
            underlying=data["underlying"],
            settlement_currency=data["settlement_currency"],
            base_notional=term_from_dict(data["base_notional"]),
            payoff_schedule=schedule_from_dict(data["payoff_schedule"]),
            payoff_program=PayoffProgram.from_dict(data["payoff_program"]),
            target=term_from_dict(data["target"]),
            final_fixing_treatment=data.get("final_fixing_treatment", "full"),
            product_barrier_type=data.get("product_barrier_type", "none"),
            product_barrier_level=None if pbl is None else term_from_dict(pbl),
            product_barrier_window=None if pbw is None else ObservationWindow.from_dict(pbw),
            product_barrier_condition=data.get("product_barrier_condition"),
        )
