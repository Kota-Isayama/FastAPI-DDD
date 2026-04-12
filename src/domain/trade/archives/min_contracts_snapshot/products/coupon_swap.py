from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..common.identity import ProductIdentity
from ..common.schedules import ObservationWindow, ScheduleLike, schedule_from_dict
from ..common.terms import Term, term_from_dict


@dataclass(frozen=True)
class CouponFormula:
    payoff_style: str
    strike: Term[float]
    ratio: Term[float]
    option_side: str | None = None
    lower_bound: Term[float] | None = None
    upper_bound: Term[float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "payoff_style": self.payoff_style,
            "strike": self.strike.to_dict(),
            "ratio": self.ratio.to_dict(),
            "option_side": self.option_side,
            "lower_bound": None if self.lower_bound is None else self.lower_bound.to_dict(),
            "upper_bound": None if self.upper_bound is None else self.upper_bound.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CouponFormula":
        lower = data.get("lower_bound")
        upper = data.get("upper_bound")
        return cls(
            payoff_style=data["payoff_style"],
            strike=term_from_dict(data["strike"]),
            ratio=term_from_dict(data["ratio"]),
            option_side=data.get("option_side"),
            lower_bound=None if lower is None else term_from_dict(lower),
            upper_bound=None if upper is None else term_from_dict(upper),
        )


@dataclass(frozen=True)
class CouponSwapSpec:
    identity: ProductIdentity
    underlying: str
    coupon_currency: str
    notional: Term[float]
    coupon_schedule: ScheduleLike
    coupon_formula: CouponFormula
    pay_receive: str = "receive"

    def validate(self) -> None:
        if self.identity.family != "COUPON_SWAP":
            raise ValueError("family must be COUPON_SWAP")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "kind": "coupon_swap",
            "identity": self.identity.to_dict(),
            "underlying": self.underlying,
            "coupon_currency": self.coupon_currency,
            "notional": self.notional.to_dict(),
            "coupon_schedule": self.coupon_schedule.to_dict(),
            "coupon_formula": self.coupon_formula.to_dict(),
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
            coupon_formula=CouponFormula.from_dict(data["coupon_formula"]),
            pay_receive=data.get("pay_receive", "receive"),
        )


@dataclass(frozen=True)
class AKOCouponSwapSpec:
    identity: ProductIdentity
    underlying: str
    coupon_currency: str
    notional: Term[float]
    coupon_schedule: ScheduleLike
    coupon_formula: CouponFormula
    ako_level: Term[float]
    ako_window: ObservationWindow
    ako_condition: str = "spot_lte_level"
    action_on_breach: str = "cancel_remaining"
    pay_receive: str = "receive"

    def validate(self) -> None:
        if self.identity.family != "AKO_COUPON_SWAP":
            raise ValueError("family must be AKO_COUPON_SWAP")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "kind": "ako_coupon_swap",
            "identity": self.identity.to_dict(),
            "underlying": self.underlying,
            "coupon_currency": self.coupon_currency,
            "notional": self.notional.to_dict(),
            "coupon_schedule": self.coupon_schedule.to_dict(),
            "coupon_formula": self.coupon_formula.to_dict(),
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
            coupon_formula=CouponFormula.from_dict(data["coupon_formula"]),
            ako_level=term_from_dict(data["ako_level"]),
            ako_window=ObservationWindow.from_dict(data["ako_window"]),
            ako_condition=data.get("ako_condition", "spot_lte_level"),
            action_on_breach=data.get("action_on_breach", "cancel_remaining"),
            pay_receive=data.get("pay_receive", "receive"),
        )
