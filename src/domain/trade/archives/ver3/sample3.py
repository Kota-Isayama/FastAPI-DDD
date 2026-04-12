from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, ClassVar, Generic, Protocol, TypeVar, runtime_checkable


T = TypeVar("T")


# ============================================================
# Shared serialization protocol
# ============================================================

@runtime_checkable
class Serializable(Protocol):
    def to_dict(self) -> dict[str, Any]:
        ...


# ============================================================
# Identity / references
# ============================================================

@dataclass(frozen=True)
class ProductIdentity:
    family: str
    type_name: str
    version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "type_name": self.type_name,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProductIdentity":
        return cls(
            family=data["family"],
            type_name=data["type_name"],
            version=data.get("version", "1.0"),
        )


@dataclass(frozen=True)
class UnderlyingRef:
    name: str
    asset_class: str = "FX"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "asset_class": self.asset_class,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UnderlyingRef":
        return cls(
            name=data["name"],
            asset_class=data.get("asset_class", "FX"),
        )


# ============================================================
# Terms: time-varying values
# ============================================================

class Term(Protocol, Generic[T]):
    def to_dict(self) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class ConstantTerm(Generic[T]):
    kind: ClassVar[str] = "constant"
    value: T

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "value": self.value}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConstantTerm[Any]":
        return cls(value=data["value"])


@dataclass(frozen=True)
class StepByIndexTerm(Generic[T]):
    """
    例:
      [(0, 145.0), (6, 147.0)]
      -> event_index 0..5 では 145.0, 6以降では 147.0
    """
    kind: ClassVar[str] = "step_by_index"
    steps: tuple[tuple[int, T], ...]

    def __post_init__(self) -> None:
        if not self.steps:
            raise ValueError("steps must not be empty")
        starts = [x for x, _ in self.steps]
        if starts != sorted(starts):
            raise ValueError("steps must be sorted ascending by start index")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "steps": [[i, v] for i, v in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StepByIndexTerm[Any]":
        return cls(steps=tuple((int(i), v) for i, v in data["steps"]))


@dataclass(frozen=True)
class DateRangeTerm(Generic[T]):
    kind: ClassVar[str] = "date_range"
    ranges: tuple[tuple[date, date, T], ...]

    def __post_init__(self) -> None:
        if not self.ranges:
            raise ValueError("ranges must not be empty")
        for start, end, _ in self.ranges:
            if start > end:
                raise ValueError("range start must be <= end")

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
                    date.fromisoformat(item["start"]),
                    date.fromisoformat(item["end"]),
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


# ============================================================
# Schedules
# ============================================================

@dataclass(frozen=True)
class IndexedSchedule:
    """
    fixing / observation / coupon determination date と settlement date の列。
    変則 schedule を素直に持つため、ペア列で表現する。
    """
    items: tuple[tuple[date, date], ...]
    role: str = "generic"

    def __post_init__(self) -> None:
        if not self.items:
            raise ValueError("schedule items must not be empty")
        fixing_dates = [fix for fix, _ in self.items]
        if fixing_dates != sorted(fixing_dates):
            raise ValueError("schedule dates must be sorted ascending")

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
                    date.fromisoformat(item["event_date"]),
                    date.fromisoformat(item["settlement_date"]),
                )
                for item in data["items"]
            ),
            role=data.get("role", "generic"),
        )


@dataclass(frozen=True)
class ObservationSchedule:
    dates: tuple[date, ...]
    role: str = "observation"

    def __post_init__(self) -> None:
        if not self.dates:
            raise ValueError("observation schedule dates must not be empty")
        if tuple(sorted(self.dates)) != self.dates:
            raise ValueError("observation schedule dates must be sorted ascending")

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "dates": [d.isoformat() for d in self.dates],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ObservationSchedule":
        return cls(
            dates=tuple(date.fromisoformat(x) for x in data["dates"]),
            role=data.get("role", "observation"),
        )


# ============================================================
# Component base classes
# ============================================================

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


# ============================================================
# Payoff components
# ============================================================

@dataclass(frozen=True)
class FXForwardDiffPayoff:
    """
    FX の TARF 系でよくある「spot と strike の差」に基づく payoff の骨格。
    sign rule 自体はここでは計算しない。
    何を payoff の本質として採用するかだけを記述する。
    """
    component_type: ClassVar[str] = "payoff"
    kind: ClassVar[str] = "fx_forward_diff"

    underlying: UnderlyingRef
    direction: str  # exporter / importer / buy_base / sell_base など
    strike: Term[float]
    notional: Term[float]
    leverage_multiplier: Term[float]
    schedule: IndexedSchedule
    settlement_currency: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_type": self.component_type,
            "kind": self.kind,
            "underlying": self.underlying.to_dict(),
            "direction": self.direction,
            "strike": self.strike.to_dict(),
            "notional": self.notional.to_dict(),
            "leverage_multiplier": self.leverage_multiplier.to_dict(),
            "schedule": self.schedule.to_dict(),
            "settlement_currency": self.settlement_currency,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FXForwardDiffPayoff":
        return cls(
            underlying=UnderlyingRef.from_dict(data["underlying"]),
            direction=data["direction"],
            strike=term_from_dict(data["strike"]),
            notional=term_from_dict(data["notional"]),
            leverage_multiplier=term_from_dict(data["leverage_multiplier"]),
            schedule=IndexedSchedule.from_dict(data["schedule"]),
            settlement_currency=data["settlement_currency"],
        )


@dataclass(frozen=True)
class RangeCouponPayoff:
    """
    AKO 付き coupon swap 向けの coupon payoff 骨格。
    実際の算式評価はしないが、rate をどう決める契約かを記述する。
    """
    component_type: ClassVar[str] = "payoff"
    kind: ClassVar[str] = "range_coupon"

    underlying: UnderlyingRef
    pay_receive: str
    notional: Term[float]
    coupon_schedule: IndexedSchedule
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
            "coupon_schedule": self.coupon_schedule.to_dict(),
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
        lower = data.get("lower_bound")
        upper = data.get("upper_bound")
        accrual_factor = data.get("accrual_factor_term")
        return cls(
            underlying=UnderlyingRef.from_dict(data["underlying"]),
            pay_receive=data["pay_receive"],
            notional=term_from_dict(data["notional"]),
            coupon_schedule=IndexedSchedule.from_dict(data["coupon_schedule"]),
            coupon_currency=data["coupon_currency"],
            base_rate=term_from_dict(data["base_rate"]),
            spread=term_from_dict(data["spread"]),
            leverage=term_from_dict(data["leverage"]),
            lower_bound=None if lower is None else term_from_dict(lower),
            upper_bound=None if upper is None else term_from_dict(upper),
            day_count=data.get("day_count", "ACT/365"),
            accrual_factor_term=None if accrual_factor is None else term_from_dict(accrual_factor),
        )


# ============================================================
# Barrier components
# ============================================================

@dataclass(frozen=True)
class NoBarrier:
    component_type: ClassVar[str] = "barrier"
    kind: ClassVar[str] = "none"

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_type": self.component_type,
            "kind": self.kind,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NoBarrier":
        return cls()


@dataclass(frozen=True)
class EuropeanKnockInBarrier:
    component_type: ClassVar[str] = "barrier"
    kind: ClassVar[str] = "european_knock_in"

    underlying: UnderlyingRef
    trigger_level: Term[float]
    observation_schedule: ObservationSchedule
    breach_condition: str  # spot_lte_level / spot_gte_level など

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_type": self.component_type,
            "kind": self.kind,
            "underlying": self.underlying.to_dict(),
            "trigger_level": self.trigger_level.to_dict(),
            "observation_schedule": self.observation_schedule.to_dict(),
            "breach_condition": self.breach_condition,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EuropeanKnockInBarrier":
        return cls(
            underlying=UnderlyingRef.from_dict(data["underlying"]),
            trigger_level=term_from_dict(data["trigger_level"]),
            observation_schedule=ObservationSchedule.from_dict(data["observation_schedule"]),
            breach_condition=data["breach_condition"],
        )


@dataclass(frozen=True)
class AKOBarrier:
    component_type: ClassVar[str] = "barrier"
    kind: ClassVar[str] = "ako"

    underlying: UnderlyingRef
    trigger_level: Term[float]
    observation_schedule: ObservationSchedule
    breach_condition: str
    action_on_breach: str  # cancel_remaining / cancel_next_coupon

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_type": self.component_type,
            "kind": self.kind,
            "underlying": self.underlying.to_dict(),
            "trigger_level": self.trigger_level.to_dict(),
            "observation_schedule": self.observation_schedule.to_dict(),
            "breach_condition": self.breach_condition,
            "action_on_breach": self.action_on_breach,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AKOBarrier":
        return cls(
            underlying=UnderlyingRef.from_dict(data["underlying"]),
            trigger_level=term_from_dict(data["trigger_level"]),
            observation_schedule=ObservationSchedule.from_dict(data["observation_schedule"]),
            breach_condition=data["breach_condition"],
            action_on_breach=data["action_on_breach"],
        )


# ============================================================
# Accrual components
# ============================================================

@dataclass(frozen=True)
class NoAccrual:
    component_type: ClassVar[str] = "accrual"
    kind: ClassVar[str] = "none"

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_type": self.component_type,
            "kind": self.kind,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NoAccrual":
        return cls()


@dataclass(frozen=True)
class PositivePnLAccrual:
    """
    TARF で target に対して何を積み上げるか。
    """
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
    """
    coupon swap で coupon を生む accrual の記述。
    """
    component_type: ClassVar[str] = "accrual"
    kind: ClassVar[str] = "coupon"

    observation_basis: str  # in_range_days / fixing_based / formula_based
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


# ============================================================
# Redemption components
# ============================================================

@dataclass(frozen=True)
class NoRedemption:
    component_type: ClassVar[str] = "redemption"
    kind: ClassVar[str] = "none"

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_type": self.component_type,
            "kind": self.kind,
        }

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

    action_on_barrier: str  # terminate / cancel_remaining / disable_payoff_leg

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_type": self.component_type,
            "kind": self.kind,
            "action_on_barrier": self.action_on_barrier,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BarrierTriggeredRedemption":
        return cls(action_on_barrier=data["action_on_barrier"])


# ============================================================
# Settlement components
# ============================================================

@dataclass(frozen=True)
class StandardSettlement:
    component_type: ClassVar[str] = "settlement"
    kind: ClassVar[str] = "standard"

    settlement_mode: str  # cash / physical
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
    final_fixing_treatment: str  # full / partial / none
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


# ============================================================
# Component deserializers
# ============================================================

def payoff_component_from_dict(data: dict[str, Any]) -> PayoffComponent:
    kind = data["kind"]
    if kind == "fx_forward_diff":
        return FXForwardDiffPayoff.from_dict(data)
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


# ============================================================
# Contract spec composed from components
# ============================================================

@dataclass(frozen=True)
class ProductSpec:
    """
    ここが composition の中心。
    商品は components の組として表す。
    """
    identity: ProductIdentity
    payoff: PayoffComponent
    barrier: BarrierComponent
    accrual: AccrualComponent
    redemption: RedemptionComponent
    settlement: SettlementComponent
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        """
        pricing ではなく、契約記述としての整合性だけを見る。
        """
        family = self.identity.family

        if family == "TARF":
            if not isinstance(self.payoff, FXForwardDiffPayoff):
                raise ValueError("TARF payoff must be FXForwardDiffPayoff")
            if not isinstance(self.accrual, PositivePnLAccrual):
                raise ValueError("TARF accrual must be PositivePnLAccrual")
            if not isinstance(self.redemption, TargetHitRedemption):
                raise ValueError("TARF redemption must be TargetHitRedemption")
            if not isinstance(self.settlement, (StandardSettlement, FinalFixingSettlement)):
                raise ValueError("TARF settlement must be settlement component")
            if isinstance(self.barrier, AKOBarrier):
                raise ValueError("AKOBarrier is not valid for TARF family")

        elif family == "AKO_COUPON_SWAP":
            if not isinstance(self.payoff, RangeCouponPayoff):
                raise ValueError("AKO_COUPON_SWAP payoff must be RangeCouponPayoff")
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
        spec = cls(
            identity=ProductIdentity.from_dict(data["identity"]),
            payoff=payoff_component_from_dict(components["payoff"]),
            barrier=barrier_component_from_dict(components["barrier"]),
            accrual=accrual_component_from_dict(components["accrual"]),
            redemption=redemption_component_from_dict(components["redemption"]),
            settlement=settlement_component_from_dict(components["settlement"]),
            tags=tuple(data.get("tags", [])),
            metadata=dict(data.get("metadata", {})),
        )
        spec.validate()
        return spec


# ============================================================
# Typed facades
# ============================================================

@dataclass(frozen=True)
class TARFSpec:
    """
    利用者向けには TARF として扱える。
    内部では ProductSpec へ落とす。
    """
    identity: ProductIdentity
    underlying: UnderlyingRef
    direction: str
    fixing_schedule: IndexedSchedule

    strike: Term[float]
    target: Term[float]
    notional: Term[float]
    leverage_multiplier: Term[float]

    settlement_currency: str
    final_fixing_treatment: str = "full"  # full / partial / none
    barrier: BarrierComponent = field(default_factory=NoBarrier)

    def __post_init__(self) -> None:
        if self.identity.family != "TARF":
            raise ValueError("TARFSpec.identity.family must be 'TARF'")
        if self.fixing_schedule.role != "tarf_fixing":
            object.__setattr__(self, "fixing_schedule", IndexedSchedule(
                items=self.fixing_schedule.items,
                role="tarf_fixing"
            ))

    def to_product_spec(self) -> ProductSpec:
        spec = ProductSpec(
            identity=self.identity,
            payoff=FXForwardDiffPayoff(
                underlying=self.underlying,
                direction=self.direction,
                strike=self.strike,
                notional=self.notional,
                leverage_multiplier=self.leverage_multiplier,
                schedule=self.fixing_schedule,
                settlement_currency=self.settlement_currency,
            ),
            barrier=self.barrier,
            accrual=PositivePnLAccrual(
                accrual_currency=self.settlement_currency,
                metric="positive_pnl_only",
            ),
            redemption=TargetHitRedemption(
                target=self.target,
                comparison="accrued_gte_target",
                action_on_hit="terminate",
            ),
            settlement=FinalFixingSettlement(
                settlement_mode="cash",
                final_fixing_treatment=self.final_fixing_treatment,
                settlement_currency=self.settlement_currency,
            ),
            tags=("fx", "target_redemption", "tarf"),
            metadata={},
        )
        spec.validate()
        return spec

    def to_dict(self) -> dict[str, Any]:
        return self.to_product_spec().to_dict()

    @classmethod
    def from_product_spec(cls, spec: ProductSpec) -> "TARFSpec":
        spec.validate()
        if spec.identity.family != "TARF":
            raise ValueError("product spec is not TARF")
        if not isinstance(spec.payoff, FXForwardDiffPayoff):
            raise ValueError("unexpected payoff for TARF")
        if not isinstance(spec.redemption, TargetHitRedemption):
            raise ValueError("unexpected redemption for TARF")
        if not isinstance(spec.settlement, FinalFixingSettlement):
            raise ValueError("unexpected settlement for TARF")

        return cls(
            identity=spec.identity,
            underlying=spec.payoff.underlying,
            direction=spec.payoff.direction,
            fixing_schedule=spec.payoff.schedule,
            strike=spec.payoff.strike,
            target=spec.redemption.target,
            notional=spec.payoff.notional,
            leverage_multiplier=spec.payoff.leverage_multiplier,
            settlement_currency=spec.payoff.settlement_currency,
            final_fixing_treatment=spec.settlement.final_fixing_treatment,
            barrier=spec.barrier,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TARFSpec":
        return cls.from_product_spec(ProductSpec.from_dict(data))


@dataclass(frozen=True)
class AKOCouponSwapSpec:
    identity: ProductIdentity
    underlying: UnderlyingRef
    pay_receive: str
    coupon_schedule: IndexedSchedule
    notional: Term[float]
    coupon_currency: str

    base_rate: Term[float]
    spread: Term[float]
    leverage: Term[float]
    lower_bound: Term[float] | None
    upper_bound: Term[float] | None

    ako_trigger_level: Term[float]
    ako_observation_schedule: ObservationSchedule
    ako_breach_condition: str = "spot_lte_level"
    ako_action_on_breach: str = "cancel_remaining"

    day_count: str = "ACT/365"
    accrual_factor_term: Term[float] | None = None

    def __post_init__(self) -> None:
        if self.identity.family != "AKO_COUPON_SWAP":
            raise ValueError("AKOCouponSwapSpec.identity.family must be 'AKO_COUPON_SWAP'")

    def to_product_spec(self) -> ProductSpec:
        spec = ProductSpec(
            identity=self.identity,
            payoff=RangeCouponPayoff(
                underlying=self.underlying,
                pay_receive=self.pay_receive,
                notional=self.notional,
                coupon_schedule=self.coupon_schedule,
                coupon_currency=self.coupon_currency,
                base_rate=self.base_rate,
                spread=self.spread,
                leverage=self.leverage,
                lower_bound=self.lower_bound,
                upper_bound=self.upper_bound,
                day_count=self.day_count,
                accrual_factor_term=self.accrual_factor_term,
            ),
            barrier=AKOBarrier(
                underlying=self.underlying,
                trigger_level=self.ako_trigger_level,
                observation_schedule=self.ako_observation_schedule,
                breach_condition=self.ako_breach_condition,
                action_on_breach=self.ako_action_on_breach,
            ),
            accrual=CouponAccrual(
                observation_basis="formula_based",
                accrual_factor_term=self.accrual_factor_term,
            ),
            redemption=BarrierTriggeredRedemption(
                action_on_barrier=self.ako_action_on_breach,
            ),
            settlement=StandardSettlement(
                settlement_mode="cash",
                settlement_currency=self.coupon_currency,
            ),
            tags=("fx", "coupon_swap", "ako"),
            metadata={},
        )
        spec.validate()
        return spec

    def to_dict(self) -> dict[str, Any]:
        return self.to_product_spec().to_dict()

    @classmethod
    def from_product_spec(cls, spec: ProductSpec) -> "AKOCouponSwapSpec":
        spec.validate()
        if spec.identity.family != "AKO_COUPON_SWAP":
            raise ValueError("product spec is not AKO_COUPON_SWAP")
        if not isinstance(spec.payoff, RangeCouponPayoff):
            raise ValueError("unexpected payoff for AKO_COUPON_SWAP")
        if not isinstance(spec.barrier, AKOBarrier):
            raise ValueError("unexpected barrier for AKO_COUPON_SWAP")
        if not isinstance(spec.redemption, BarrierTriggeredRedemption):
            raise ValueError("unexpected redemption for AKO_COUPON_SWAP")

        return cls(
            identity=spec.identity,
            underlying=spec.payoff.underlying,
            pay_receive=spec.payoff.pay_receive,
            coupon_schedule=spec.payoff.coupon_schedule,
            notional=spec.payoff.notional,
            coupon_currency=spec.payoff.coupon_currency,
            base_rate=spec.payoff.base_rate,
            spread=spec.payoff.spread,
            leverage=spec.payoff.leverage,
            lower_bound=spec.payoff.lower_bound,
            upper_bound=spec.payoff.upper_bound,
            ako_trigger_level=spec.barrier.trigger_level,
            ako_observation_schedule=spec.barrier.observation_schedule,
            ako_breach_condition=spec.barrier.breach_condition,
            ako_action_on_breach=spec.barrier.action_on_breach,
            day_count=spec.payoff.day_count,
            accrual_factor_term=spec.payoff.accrual_factor_term,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AKOCouponSwapSpec":
        return cls.from_product_spec(ProductSpec.from_dict(data))


# ============================================================
# Example usage
# ============================================================

def example_tarf() -> TARFSpec:
    return TARFSpec(
        identity=ProductIdentity(
            family="TARF",
            type_name="TargetRedemptionForward",
            version="1.0",
        ),
        underlying=UnderlyingRef("USDJPY", "FX"),
        direction="exporter",
        fixing_schedule=IndexedSchedule(
            items=(
                (date(2026, 1, 10), date(2026, 1, 12)),
                (date(2026, 2, 10), date(2026, 2, 12)),
                (date(2026, 3, 10), date(2026, 3, 12)),
                (date(2026, 4, 10), date(2026, 4, 14)),  # irregular settlement
                (date(2026, 5, 10), date(2026, 5, 12)),
                (date(2026, 6, 10), date(2026, 6, 12)),
                (date(2026, 7, 10), date(2026, 7, 14)),
            ),
            role="tarf_fixing",
        ),
        strike=StepByIndexTerm(
            steps=(
                (0, 145.0),
                (4, 147.0),  # strike changes mid-life
            )
        ),
        target=ConstantTerm(5_000_000.0),
        notional=ConstantTerm(1_000_000.0),
        leverage_multiplier=DateRangeTerm(
            ranges=(
                (date(2026, 1, 1), date(2026, 4, 30), 1.0),
                (date(2026, 5, 1), date(2026, 12, 31), 2.0),
            )
        ),
        settlement_currency="JPY",
        final_fixing_treatment="full",
        barrier=NoBarrier(),
    )


def example_ako_coupon_swap() -> AKOCouponSwapSpec:
    return AKOCouponSwapSpec(
        identity=ProductIdentity(
            family="AKO_COUPON_SWAP",
            type_name="RangeCouponSwapWithAKO",
            version="1.0",
        ),
        underlying=UnderlyingRef("USDJPY", "FX"),
        pay_receive="receive",
        coupon_schedule=IndexedSchedule(
            items=(
                (date(2026, 1, 15), date(2026, 1, 20)),
                (date(2026, 4, 15), date(2026, 4, 20)),
                (date(2026, 7, 15), date(2026, 7, 21)),  # irregular settlement
                (date(2026, 10, 15), date(2026, 10, 20)),
            ),
            role="coupon_fixing",
        ),
        notional=StepByIndexTerm(
            steps=(
                (0, 10_000_000.0),
                (2, 8_000_000.0),  # notional changes later
            )
        ),
        coupon_currency="JPY",
        base_rate=ConstantTerm(0.015),
        spread=StepByIndexTerm(
            steps=(
                (0, 0.0020),
                (2, 0.0035),  # coupon spread changes later
            )
        ),
        leverage=ConstantTerm(1.0),
        lower_bound=ConstantTerm(130.0),
        upper_bound=ConstantTerm(155.0),
        ako_trigger_level=ConstantTerm(128.0),
        ako_observation_schedule=ObservationSchedule(
            dates=(
                date(2026, 1, 15),
                date(2026, 4, 15),
                date(2026, 7, 15),
                date(2026, 10, 15),
            ),
            role="ako_observation",
        ),
        ako_breach_condition="spot_lte_level",
        ako_action_on_breach="cancel_remaining",
        day_count="ACT/365",
        accrual_factor_term=ConstantTerm(0.25),
    )


if __name__ == "__main__":
    tarf = example_tarf()
    tarf_spec = tarf.to_product_spec()
    tarf_dict = tarf_spec.to_dict()
    tarf_restored = ProductSpec.from_dict(tarf_dict)

    print("=== TARF ProductSpec ===")
    print(tarf_dict)
    print("\n=== TARF restored family ===")
    print(tarf_restored.identity.family)

    swap = example_ako_coupon_swap()
    swap_spec = swap.to_product_spec()
    swap_dict = swap_spec.to_dict()
    swap_restored = ProductSpec.from_dict(swap_dict)

    print("\n=== AKO Coupon Swap ProductSpec ===")
    print(swap_dict)
    print("\n=== AKO restored family ===")
    print(swap_restored.identity.family)