from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Protocol

from .barriers import (
    AKOBarrier,
    EuropeanKnockInBarrier,
    NoBarrier,
)
from .identity import ProductIdentity, UnderlyingRef
from .payoff_legs import FXForwardLegSpec, FXLegSpec, FXOptionLegSpec, fx_leg_from_dict
from .schedules import EventSchedule
from .terms import ConstantTerm, StepByIndexTerm, Term, term_from_dict


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


# === UPDATED
@dataclass(frozen=True)
class FXStructuredPayoff:
    component_type: ClassVar[str] = "payoff"
    kind: ClassVar[str] = "fx_structured"

    underlying: UnderlyingRef
    payoff_style: str  # normal / gap / range_gap / collar / two_stage / custom
    schedule_spec: Any  # ScheduleSpec
    settlement_currency: str
    base_notional: Term[float]
    legs: tuple[FXLegSpec, ...]
    netting_method: str = "per_event"

    def validate(self) -> None:
        if not self.legs:
            raise ValueError("FXStructuredPayoff.legs must not be empty")

        for leg in self.legs:
            if isinstance(leg, FXOptionLegSpec):
                if leg.option_type not in {"call", "put"}:
                    raise ValueError("option_type must be call or put")
                if leg.position not in {"buy", "sell"}:
                    raise ValueError("option position must be buy or sell")
            elif isinstance(leg, FXForwardLegSpec):
                if leg.position not in {"buy_base", "sell_base", "long", "short"}:
                    raise ValueError("forward position must be buy_base/sell_base/long/short")
            else:
                raise ValueError(f"unsupported leg type: {type(leg)!r}")

        if self.payoff_style == "normal":
            if len(self.legs) != 1 or not isinstance(self.legs[0], FXForwardLegSpec):
                raise ValueError("normal payoff must have exactly one FXForwardLegSpec")

        elif self.payoff_style == "two_stage":
            if len(self.legs) != 1 or not isinstance(self.legs[0], FXForwardLegSpec):
                raise ValueError("two_stage payoff must have exactly one FXForwardLegSpec")
            if not isinstance(self.legs[0].strike, StepByIndexTerm):
                raise ValueError("two_stage payoff requires StepByIndexTerm strike")

        elif self.payoff_style in {"gap", "range_gap", "collar"}:
            if len(self.legs) != 2:
                raise ValueError(f"{self.payoff_style} payoff must have exactly two legs")

            call_legs = [
                leg for leg in self.legs
                if isinstance(leg, FXOptionLegSpec) and leg.option_type == "call"
            ]
            put_legs = [
                leg for leg in self.legs
                if isinstance(leg, FXOptionLegSpec) and leg.option_type == "put"
            ]
            if len(call_legs) != 1 or len(put_legs) != 1:
                raise ValueError(f"{self.payoff_style} must have one call leg and one put leg")

            call_leg = call_legs[0]
            put_leg = put_legs[0]

            if self.payoff_style in {"gap", "range_gap"}:
                from .barriers import EuropeanKnockInLegBarrier, NoLegBarrier

                if call_leg.position != "buy":
                    raise ValueError(f"{self.payoff_style} call leg must be buy")
                if put_leg.position != "sell":
                    raise ValueError(f"{self.payoff_style} put leg must be sell")
                if not isinstance(put_leg.barrier, EuropeanKnockInLegBarrier):
                    raise ValueError(f"{self.payoff_style} put leg must have European KI")
                if not isinstance(call_leg.barrier, NoLegBarrier):
                    raise ValueError(f"{self.payoff_style} call leg must not have barrier")

            if self.payoff_style == "collar":
                from .barriers import NoLegBarrier

                if call_leg.position != "buy":
                    raise ValueError("collar call leg must be buy")
                if put_leg.position != "sell":
                    raise ValueError("collar put leg must be sell")
                if not isinstance(call_leg.barrier, NoLegBarrier):
                    raise ValueError("collar call leg must not have barrier")
                if not isinstance(put_leg.barrier, NoLegBarrier):
                    raise ValueError("collar put leg must not have barrier")

            if isinstance(call_leg.strike, ConstantTerm) and isinstance(put_leg.strike, ConstantTerm):
                call_k = call_leg.strike.value
                put_k = put_leg.strike.value

                if self.payoff_style == "gap" and not (call_k < put_k):
                    raise ValueError("gap requires call strike < put strike")
                if self.payoff_style == "range_gap" and not (call_k == put_k):
                    raise ValueError("range_gap requires call strike == put strike")
                if self.payoff_style == "collar" and not (call_k > put_k):
                    raise ValueError("collar requires call strike > put strike")

        elif self.payoff_style == "custom":
            pass
        else:
            raise ValueError(f"unsupported payoff_style: {self.payoff_style}")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "component_type": self.component_type,
            "kind": self.kind,
            "underlying": self.underlying.to_dict(),
            "payoff_style": self.payoff_style,
            "schedule_spec": self.schedule_spec.to_dict(),
            "settlement_currency": self.settlement_currency,
            "base_notional": self.base_notional.to_dict(),
            "legs": [leg.to_dict() for leg in self.legs],
            "netting_method": self.netting_method,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FXStructuredPayoff":
        from .schedules import schedule_spec_from_dict
        obj = cls(
            underlying=UnderlyingRef.from_dict(data["underlying"]),
            payoff_style=data["payoff_style"],
            schedule_spec=schedule_spec_from_dict(data["schedule_spec"]),
            settlement_currency=data["settlement_currency"],
            base_notional=term_from_dict(data["base_notional"]),
            legs=tuple(fx_leg_from_dict(leg) for leg in data["legs"]),
            netting_method=data.get("netting_method", "per_event"),
        )
        obj.validate()
        return obj


@dataclass(frozen=True)
class RangeCouponPayoff:
    component_type: ClassVar[str] = "payoff"
    kind: ClassVar[str] = "range_coupon"

    underlying: UnderlyingRef
    pay_receive: str
    notional: Term[float]
    coupon_schedule_spec: Any
    coupon_currency: str

    base_rate: Term[float]
    spread: Term[float]
    leverage: Term[float]
    lower_bound: Term[float] | None = None
    upper_bound: Term[float] | None = None
    day_count: str = "ACT/365"
    accrual_factor_term: Term[float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_type": self.component_type,
            "kind": self.kind,
            "underlying": self.underlying.to_dict(),
            "pay_receive": self.pay_receive,
            "notional": self.notional.to_dict(),
            "coupon_schedule_spec": self.coupon_schedule_spec.to_dict(),
            "coupon_currency": self.coupon_currency,
            "base_rate": self.base_rate.to_dict(),
            "spread": self.spread.to_dict(),
            "leverage": self.leverage.to_dict(),
            "lower_bound": None if self.lower_bound is None else self.lower_bound.to_dict(),
            "upper_bound": None if self.upper_bound is None else self.upper_bound.to_dict(),
            "day_count": self.day_count,
            "accrual_factor_term": (
                None if self.accrual_factor_term is None else self.accrual_factor_term.to_dict()
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RangeCouponPayoff":
        from .schedules import schedule_spec_from_dict
        lower = data.get("lower_bound")
        upper = data.get("upper_bound")
        aft = data.get("accrual_factor_term")
        return cls(
            underlying=UnderlyingRef.from_dict(data["underlying"]),
            pay_receive=data["pay_receive"],
            notional=term_from_dict(data["notional"]),
            coupon_schedule_spec=schedule_spec_from_dict(data["coupon_schedule_spec"]),
            coupon_currency=data["coupon_currency"],
            base_rate=term_from_dict(data["base_rate"]),
            spread=term_from_dict(data["spread"]),
            leverage=term_from_dict(data["leverage"]),
            lower_bound=None if lower is None else term_from_dict(lower),
            upper_bound=None if upper is None else term_from_dict(upper),
            day_count=data.get("day_count", "ACT/365"),
            accrual_factor_term=None if aft is None else term_from_dict(aft),
        )


@dataclass(frozen=True)
class NoAccrual:
    component_type: ClassVar[str] = "accrual"
    kind: ClassVar[str] = "none"

    def to_dict(self) -> dict[str, Any]:
        return {"component_type": self.component_type, "kind": self.kind}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NoAccrual":
        return cls()


@dataclass(frozen=True)
class PositivePnLAccrual:
    component_type: ClassVar[str] = "accrual"
    kind: ClassVar[str] = "positive_pnl"

    accrual_currency: str
    metric: str = "positive_pnl_only"

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_type": self.component_type,
            "kind": self.kind,
            "accrual_currency": self.accrual_currency,
            "metric": self.metric,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PositivePnLAccrual":
        return cls(
            accrual_currency=data["accrual_currency"],
            metric=data.get("metric", "positive_pnl_only"),
        )


@dataclass(frozen=True)
class CouponAccrual:
    component_type: ClassVar[str] = "accrual"
    kind: ClassVar[str] = "coupon"

    observation_basis: str
    accrual_factor_term: Term[float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_type": self.component_type,
            "kind": self.kind,
            "observation_basis": self.observation_basis,
            "accrual_factor_term": (
                None if self.accrual_factor_term is None else self.accrual_factor_term.to_dict()
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CouponAccrual":
        aft = data.get("accrual_factor_term")
        return cls(
            observation_basis=data["observation_basis"],
            accrual_factor_term=None if aft is None else term_from_dict(aft),
        )


@dataclass(frozen=True)
class NoRedemption:
    component_type: ClassVar[str] = "redemption"
    kind: ClassVar[str] = "none"

    def to_dict(self) -> dict[str, Any]:
        return {"component_type": self.component_type, "kind": self.kind}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NoRedemption":
        return cls()


@dataclass(frozen=True)
class TargetHitRedemption:
    component_type: ClassVar[str] = "redemption"
    kind: ClassVar[str] = "target_hit"

    target: Term[float]
    comparison: str = "accrued_gte_target"
    action_on_hit: str = "terminate"

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_type": self.component_type,
            "kind": self.kind,
            "target": self.target.to_dict(),
            "comparison": self.comparison,
            "action_on_hit": self.action_on_hit,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TargetHitRedemption":
        return cls(
            target=term_from_dict(data["target"]),
            comparison=data.get("comparison", "accrued_gte_target"),
            action_on_hit=data.get("action_on_hit", "terminate"),
        )


@dataclass(frozen=True)
class BarrierTriggeredRedemption:
    component_type: ClassVar[str] = "redemption"
    kind: ClassVar[str] = "barrier_triggered"

    action_on_barrier: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_type": self.component_type,
            "kind": self.kind,
            "action_on_barrier": self.action_on_barrier,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BarrierTriggeredRedemption":
        return cls(action_on_barrier=data["action_on_barrier"])


@dataclass(frozen=True)
class StandardSettlement:
    component_type: ClassVar[str] = "settlement"
    kind: ClassVar[str] = "standard"

    settlement_mode: str
    settlement_currency: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_type": self.component_type,
            "kind": self.kind,
            "settlement_mode": self.settlement_mode,
            "settlement_currency": self.settlement_currency,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StandardSettlement":
        return cls(
            settlement_mode=data["settlement_mode"],
            settlement_currency=data.get("settlement_currency"),
        )


@dataclass(frozen=True)
class FinalFixingSettlement:
    component_type: ClassVar[str] = "settlement"
    kind: ClassVar[str] = "final_fixing"

    settlement_mode: str
    final_fixing_treatment: str
    settlement_currency: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_type": self.component_type,
            "kind": self.kind,
            "settlement_mode": self.settlement_mode,
            "final_fixing_treatment": self.final_fixing_treatment,
            "settlement_currency": self.settlement_currency,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FinalFixingSettlement":
        return cls(
            settlement_mode=data["settlement_mode"],
            final_fixing_treatment=data["final_fixing_treatment"],
            settlement_currency=data.get("settlement_currency"),
        )


def payoff_component_from_dict(data: dict[str, Any]) -> PayoffComponent:
    kind = data["kind"]
    if kind == "fx_structured":
        return FXStructuredPayoff.from_dict(data)
    if kind == "range_coupon":
        return RangeCouponPayoff.from_dict(data)
    raise ValueError(f"unknown payoff component kind: {kind}")


def barrier_component_from_dict(data: dict[str, Any]) -> BarrierComponent:
    kind = data["kind"]
    if kind == "none":
        return NoBarrier.from_dict(data)
    if kind == "european_knock_in":
        return EuropeanKnockInBarrier.from_dict(data)
    if kind == "ako":
        return AKOBarrier.from_dict(data)
    raise ValueError(f"unknown barrier component kind: {kind}")


def accrual_component_from_dict(data: dict[str, Any]) -> AccrualComponent:
    kind = data["kind"]
    if kind == "none":
        return NoAccrual.from_dict(data)
    if kind == "positive_pnl":
        return PositivePnLAccrual.from_dict(data)
    if kind == "coupon":
        return CouponAccrual.from_dict(data)
    raise ValueError(f"unknown accrual component kind: {kind}")


def redemption_component_from_dict(data: dict[str, Any]) -> RedemptionComponent:
    kind = data["kind"]
    if kind == "none":
        return NoRedemption.from_dict(data)
    if kind == "target_hit":
        return TargetHitRedemption.from_dict(data)
    if kind == "barrier_triggered":
        return BarrierTriggeredRedemption.from_dict(data)
    raise ValueError(f"unknown redemption component kind: {kind}")


def settlement_component_from_dict(data: dict[str, Any]) -> SettlementComponent:
    kind = data["kind"]
    if kind == "standard":
        return StandardSettlement.from_dict(data)
    if kind == "final_fixing":
        return FinalFixingSettlement.from_dict(data)
    raise ValueError(f"unknown settlement component kind: {kind}")


@dataclass(frozen=True)
class ProductSpec:
    identity: ProductIdentity
    payoff: PayoffComponent
    barrier: BarrierComponent
    accrual: AccrualComponent
    redemption: RedemptionComponent
    settlement: SettlementComponent
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        family = self.identity.family

        if family == "TARF":
            if not isinstance(self.payoff, FXStructuredPayoff):
                raise ValueError("TARF payoff must be FXStructuredPayoff")
            self.payoff.validate()
            if not isinstance(self.accrual, PositivePnLAccrual):
                raise ValueError("TARF accrual must be PositivePnLAccrual")
            if not isinstance(self.redemption, TargetHitRedemption):
                raise ValueError("TARF redemption must be TargetHitRedemption")
            if not isinstance(self.settlement, (StandardSettlement, FinalFixingSettlement)):
                raise ValueError("TARF settlement must be settlement component")
            if isinstance(self.barrier, AKOBarrier):
                raise ValueError("AKOBarrier is not valid for TARF")

        elif family == "AKO_COUPON_SWAP":
            if not isinstance(self.payoff, (FXStructuredPayoff, RangeCouponPayoff)):
                raise ValueError("AKO_COUPON_SWAP payoff must be FXStructuredPayoff or RangeCouponPayoff")
            if isinstance(self.payoff, FXStructuredPayoff):
                self.payoff.validate()
            if not isinstance(self.barrier, AKOBarrier):
                raise ValueError("AKO_COUPON_SWAP barrier must be AKOBarrier")
            if not isinstance(self.accrual, CouponAccrual):
                raise ValueError("AKO_COUPON_SWAP accrual must be CouponAccrual")
            if not isinstance(self.redemption, (NoRedemption, BarrierTriggeredRedemption)):
                raise ValueError("AKO_COUPON_SWAP redemption must match AKO usage")
            if not isinstance(self.settlement, StandardSettlement):
                raise ValueError("AKO_COUPON_SWAP settlement must be StandardSettlement")
        else:
            raise ValueError(f"unsupported family: {family}")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "identity": self.identity.to_dict(),
            "components": {
                "payoff": self.payoff.to_dict(),
                "barrier": self.barrier.to_dict(),
                "accrual": self.accrual.to_dict(),
                "redemption": self.redemption.to_dict(),
                "settlement": self.settlement.to_dict(),
            },
            "tags": list(self.tags),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProductSpec":
        components = data["components"]
        obj = cls(
            identity=ProductIdentity.from_dict(data["identity"]),
            payoff=payoff_component_from_dict(components["payoff"]),
            barrier=barrier_component_from_dict(components["barrier"]),
            accrual=accrual_component_from_dict(components["accrual"]),
            redemption=redemption_component_from_dict(components["redemption"]),
            settlement=settlement_component_from_dict(components["settlement"]),
            tags=tuple(data.get("tags", [])),
            metadata=dict(data.get("metadata", {})),
        )
        obj.validate()
        return obj