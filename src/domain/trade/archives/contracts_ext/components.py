from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Protocol

from .barriers import AKOBarrier, Barrier, EuropeanKnockInBarrier, NoBarrier, barrier_from_dict
from .identity import ProductIdentity, UnderlyingRef
from .legs import (
    FixedRateLegSpec,
    FloatingRateLegSpec,
    FormulaLegSpec,
    FXForwardLegSpec,
    FXOptionLegSpec,
    KnownLeg,
    leg_from_dict,
)
from .schedules import ScheduleSpec, schedule_spec_from_dict
from .terms import AnyTerm, ConstantTerm, StepByIndexTerm, term_from_dict


class ProductComponent(Protocol):
    component_type: ClassVar[str]

    def to_dict(self) -> dict[str, Any]:
        ...


class PayoffComponent(ProductComponent, Protocol):
    component_type: ClassVar[str]


class AccrualComponent(ProductComponent, Protocol):
    component_type: ClassVar[str]


class RedemptionComponent(ProductComponent, Protocol):
    component_type: ClassVar[str]


class SettlementComponent(ProductComponent, Protocol):
    component_type: ClassVar[str]


@dataclass(frozen=True)
class FXStructuredPayoff:
    component_type: ClassVar[str] = "payoff"
    kind: ClassVar[str] = "fx_structured"

    underlying: UnderlyingRef
    payoff_style: str
    schedule_spec: ScheduleSpec
    settlement_currency: str
    base_notional: AnyTerm
    legs: tuple[KnownLeg, ...]
    netting_method: str = "per_event"

    def validate(self) -> None:
        if self.underlying.asset_class != "FX":
            raise ValueError("FXStructuredPayoff requires FX underlying")
        if not self.legs:
            raise ValueError("legs must not be empty")
        for leg in self.legs:
            if not isinstance(leg, (FXForwardLegSpec, FXOptionLegSpec)):
                raise ValueError("FXStructuredPayoff accepts only FX legs")

        if self.payoff_style == "normal":
            if len(self.legs) != 1 or not isinstance(self.legs[0], FXForwardLegSpec):
                raise ValueError("normal payoff requires one FXForwardLegSpec")
        elif self.payoff_style == "two_stage":
            if len(self.legs) != 1 or not isinstance(self.legs[0], FXForwardLegSpec):
                raise ValueError("two_stage payoff requires one FXForwardLegSpec")
            if not isinstance(self.legs[0].strike, StepByIndexTerm):
                raise ValueError("two_stage payoff requires StepByIndexTerm strike")
        elif self.payoff_style in {"gap", "range_gap", "collar"}:
            if len(self.legs) != 2:
                raise ValueError(f"{self.payoff_style} payoff requires two legs")
        elif self.payoff_style != "custom":
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
        obj = cls(
            underlying=UnderlyingRef.from_dict(data["underlying"]),
            payoff_style=data["payoff_style"],
            schedule_spec=schedule_spec_from_dict(data["schedule_spec"]),
            settlement_currency=data["settlement_currency"],
            base_notional=term_from_dict(data["base_notional"]),
            legs=tuple(leg_from_dict(item) for item in data["legs"]),
            netting_method=data.get("netting_method", "per_event"),
        )
        obj.validate()
        return obj


@dataclass(frozen=True)
class GenericMultiLegPayoff:
    component_type: ClassVar[str] = "payoff"
    kind: ClassVar[str] = "generic_multileg"

    payoff_style: str
    schedule_spec: ScheduleSpec
    legs: tuple[KnownLeg, ...]
    principal_exchange: str = "none"
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.legs:
            raise ValueError("GenericMultiLegPayoff.legs must not be empty")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "component_type": self.component_type,
            "kind": self.kind,
            "payoff_style": self.payoff_style,
            "schedule_spec": self.schedule_spec.to_dict(),
            "legs": [leg.to_dict() for leg in self.legs],
            "principal_exchange": self.principal_exchange,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GenericMultiLegPayoff":
        obj = cls(
            payoff_style=data["payoff_style"],
            schedule_spec=schedule_spec_from_dict(data["schedule_spec"]),
            legs=tuple(leg_from_dict(item) for item in data["legs"]),
            principal_exchange=data.get("principal_exchange", "none"),
            metadata=dict(data.get("metadata", {})),
        )
        obj.validate()
        return obj


@dataclass(frozen=True)
class RangeCouponPayoff:
    component_type: ClassVar[str] = "payoff"
    kind: ClassVar[str] = "range_coupon"

    underlying: UnderlyingRef
    pay_receive: str
    notional: AnyTerm
    coupon_schedule_spec: ScheduleSpec
    coupon_currency: str
    base_rate: AnyTerm
    spread: AnyTerm
    leverage: AnyTerm
    lower_bound: AnyTerm | None = None
    upper_bound: AnyTerm | None = None
    day_count: str = "ACT/365"
    accrual_factor_term: AnyTerm | None = None

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
            "accrual_factor_term": None if self.accrual_factor_term is None else self.accrual_factor_term.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RangeCouponPayoff":
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


Payoff = FXStructuredPayoff | GenericMultiLegPayoff | RangeCouponPayoff


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
        return cls(accrual_currency=data["accrual_currency"], metric=data.get("metric", "positive_pnl_only"))


@dataclass(frozen=True)
class CouponAccrual:
    component_type: ClassVar[str] = "accrual"
    kind: ClassVar[str] = "coupon"
    observation_basis: str
    accrual_factor_term: AnyTerm | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_type": self.component_type,
            "kind": self.kind,
            "observation_basis": self.observation_basis,
            "accrual_factor_term": None if self.accrual_factor_term is None else self.accrual_factor_term.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CouponAccrual":
        raw = data.get("accrual_factor_term")
        return cls(
            observation_basis=data["observation_basis"],
            accrual_factor_term=None if raw is None else term_from_dict(raw),
        )


Accrual = NoAccrual | PositivePnLAccrual | CouponAccrual


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
    target: AnyTerm
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


Redemption = NoRedemption | TargetHitRedemption | BarrierTriggeredRedemption


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
        return cls(settlement_mode=data["settlement_mode"], settlement_currency=data.get("settlement_currency"))


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


Settlement = StandardSettlement | FinalFixingSettlement


def payoff_from_dict(data: dict[str, Any]) -> Payoff:
    kind = data["kind"]
    if kind == "fx_structured":
        return FXStructuredPayoff.from_dict(data)
    if kind == "generic_multileg":
        return GenericMultiLegPayoff.from_dict(data)
    if kind == "range_coupon":
        return RangeCouponPayoff.from_dict(data)
    raise ValueError(f"unknown payoff kind: {kind}")


def accrual_from_dict(data: dict[str, Any]) -> Accrual:
    kind = data["kind"]
    if kind == "none":
        return NoAccrual.from_dict(data)
    if kind == "positive_pnl":
        return PositivePnLAccrual.from_dict(data)
    if kind == "coupon":
        return CouponAccrual.from_dict(data)
    raise ValueError(f"unknown accrual kind: {kind}")


def redemption_from_dict(data: dict[str, Any]) -> Redemption:
    kind = data["kind"]
    if kind == "none":
        return NoRedemption.from_dict(data)
    if kind == "target_hit":
        return TargetHitRedemption.from_dict(data)
    if kind == "barrier_triggered":
        return BarrierTriggeredRedemption.from_dict(data)
    raise ValueError(f"unknown redemption kind: {kind}")


def settlement_from_dict(data: dict[str, Any]) -> Settlement:
    kind = data["kind"]
    if kind == "standard":
        return StandardSettlement.from_dict(data)
    if kind == "final_fixing":
        return FinalFixingSettlement.from_dict(data)
    raise ValueError(f"unknown settlement kind: {kind}")


@dataclass(frozen=True)
class ProductSpec:
    identity: ProductIdentity
    payoff: Payoff
    barrier: Barrier
    accrual: Accrual
    redemption: Redemption
    settlement: Settlement
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        family = self.identity.family

        if isinstance(self.payoff, FXStructuredPayoff):
            self.payoff.validate()
        elif isinstance(self.payoff, GenericMultiLegPayoff):
            self.payoff.validate()

        if family == "TARF":
            if not isinstance(self.payoff, FXStructuredPayoff):
                raise ValueError("TARF requires FXStructuredPayoff")
            if not isinstance(self.accrual, PositivePnLAccrual):
                raise ValueError("TARF requires PositivePnLAccrual")
            if not isinstance(self.redemption, TargetHitRedemption):
                raise ValueError("TARF requires TargetHitRedemption")
            if not isinstance(self.settlement, FinalFixingSettlement):
                raise ValueError("TARF requires FinalFixingSettlement")
            if isinstance(self.barrier, AKOBarrier):
                raise ValueError("AKOBarrier is not valid for TARF")

        elif family == "TARN":
            if not isinstance(self.payoff, (FXStructuredPayoff, GenericMultiLegPayoff, RangeCouponPayoff)):
                raise ValueError("TARN requires supported payoff")
            if not isinstance(self.accrual, (PositivePnLAccrual, CouponAccrual)):
                raise ValueError("TARN requires accrual component")
            if not isinstance(self.redemption, TargetHitRedemption):
                raise ValueError("TARN requires TargetHitRedemption")

        elif family == "AKO_COUPON_SWAP":
            if not isinstance(self.payoff, (FXStructuredPayoff, RangeCouponPayoff, GenericMultiLegPayoff)):
                raise ValueError("AKO_COUPON_SWAP requires coupon-like payoff")
            if not isinstance(self.barrier, AKOBarrier):
                raise ValueError("AKO_COUPON_SWAP requires AKOBarrier")
            if not isinstance(self.accrual, CouponAccrual):
                raise ValueError("AKO_COUPON_SWAP requires CouponAccrual")

        elif family == "INTEREST_RATE_SWAP":
            if not isinstance(self.payoff, GenericMultiLegPayoff):
                raise ValueError("INTEREST_RATE_SWAP requires GenericMultiLegPayoff")
            if not all(isinstance(leg, (FixedRateLegSpec, FloatingRateLegSpec)) for leg in self.payoff.legs):
                raise ValueError("IRS legs must be fixed or floating")
            if len(self.payoff.legs) < 2:
                raise ValueError("IRS requires at least two legs")
            if not isinstance(self.accrual, CouponAccrual):
                raise ValueError("IRS requires CouponAccrual")

        elif family == "PRDC":
            if not isinstance(self.payoff, GenericMultiLegPayoff):
                raise ValueError("PRDC requires GenericMultiLegPayoff")
            if not any(isinstance(leg, FormulaLegSpec) for leg in self.payoff.legs):
                raise ValueError("PRDC requires at least one FormulaLegSpec")
            if not isinstance(self.accrual, CouponAccrual):
                raise ValueError("PRDC requires CouponAccrual")

        elif family == "RANGE_ACCRUAL_NOTE":
            if not isinstance(self.payoff, RangeCouponPayoff):
                raise ValueError("RANGE_ACCRUAL_NOTE requires RangeCouponPayoff")
            if not isinstance(self.accrual, CouponAccrual):
                raise ValueError("RANGE_ACCRUAL_NOTE requires CouponAccrual")

        elif family == "FX_OPTION_STRATEGY":
            if not isinstance(self.payoff, FXStructuredPayoff):
                raise ValueError("FX_OPTION_STRATEGY requires FXStructuredPayoff")

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
            payoff=payoff_from_dict(components["payoff"]),
            barrier=barrier_from_dict(components["barrier"]),
            accrual=accrual_from_dict(components["accrual"]),
            redemption=redemption_from_dict(components["redemption"]),
            settlement=settlement_from_dict(components["settlement"]),
            tags=tuple(data.get("tags", [])),
            metadata=dict(data.get("metadata", {})),
        )
        obj.validate()
        return obj
