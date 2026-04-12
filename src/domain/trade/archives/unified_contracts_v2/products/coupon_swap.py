from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..common.identity import ProductIdentity
from ..common.payoffs import PayoffProgram
from ..common.schedules import ObservationWindow, ScheduleLike, schedule_from_dict
from ..common.terms import Term, term_from_dict


@dataclass(frozen=True)
class CouponSwapSpec:
    identity: ProductIdentity
    underlying: str
    coupon_currency: str
    notional: Term[float]
    coupon_schedule: ScheduleLike
    payoff_program: PayoffProgram
    pay_receive: str = "receive"

    def validate(self) -> None:
        if self.identity.family != "COUPON_SWAP":
            raise ValueError("family must be COUPON_SWAP")

    @property
    def trade_payoff_scheme(self) -> str:
        return self.payoff_program.classify_trade_scheme()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "kind": "coupon_swap",
            "identity": self.identity.to_dict(),
            "underlying": self.underlying,
            "coupon_currency": self.coupon_currency,
            "notional": self.notional.to_dict(),
            "coupon_schedule": self.coupon_schedule.to_dict(),
            "payoff_program": self.payoff_program.to_dict(),
            "pay_receive": self.pay_receive,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CouponSwapSpec":
        return cls(
            identity=ProductIdentity.from_dict(data["identity"]),
            underlying=data["underlying"],
            coupon_currency=data["coupon_currency"],
            notional=term_from_dict(data["notional"]),
            coupon_schedule=schedule_from_dict(data["coupon_schedule"]),
            payoff_program=PayoffProgram.from_dict(data["payoff_program"]),
            pay_receive=data.get("pay_receive", "receive"),
        )


@dataclass(frozen=True)
class AKOCouponSwapSpec:
    identity: ProductIdentity
    underlying: str
    coupon_currency: str
    notional: Term[float]
    coupon_schedule: ScheduleLike
    payoff_program: PayoffProgram
    ako_level: Term[float]
    ako_window: ObservationWindow
    ako_condition: str = "spot_lte_level"
    action_on_breach: str = "cancel_remaining"
    pay_receive: str = "receive"

    def validate(self) -> None:
        if self.identity.family != "AKO_COUPON_SWAP":
            raise ValueError("family must be AKO_COUPON_SWAP")

    @property
    def trade_payoff_scheme(self) -> str:
        return self.payoff_program.classify_trade_scheme()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "kind": "ako_coupon_swap",
            "identity": self.identity.to_dict(),
            "underlying": self.underlying,
            "coupon_currency": self.coupon_currency,
            "notional": self.notional.to_dict(),
            "coupon_schedule": self.coupon_schedule.to_dict(),
            "payoff_program": self.payoff_program.to_dict(),
            "ako_level": self.ako_level.to_dict(),
            "ako_window": self.ako_window.to_dict(),
            "ako_condition": self.ako_condition,
            "action_on_breach": self.action_on_breach,
            "pay_receive": self.pay_receive,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AKOCouponSwapSpec":
        return cls(
            identity=ProductIdentity.from_dict(data["identity"]),
            underlying=data["underlying"],
            coupon_currency=data["coupon_currency"],
            notional=term_from_dict(data["notional"]),
            coupon_schedule=schedule_from_dict(data["coupon_schedule"]),
            payoff_program=PayoffProgram.from_dict(data["payoff_program"]),
            ako_level=term_from_dict(data["ako_level"]),
            ako_window=ObservationWindow.from_dict(data["ako_window"]),
            ako_condition=data.get("ako_condition", "spot_lte_level"),
            action_on_breach=data.get("action_on_breach", "cancel_remaining"),
            pay_receive=data.get("pay_receive", "receive"),
        )
