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
# Core shared domain objects
# ============================================================

# === CORE:
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


# === CORE:
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
# Terms (time-varying parameters)
# ============================================================

# === CORE:
class Term(Protocol, Generic[T]):
    def to_dict(self) -> dict[str, Any]:
        ...


# === CORE:
@dataclass(frozen=True)
class ConstantTerm(Generic[T]):
    kind: ClassVar[str] = "constant"
    value: T

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "value": self.value}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConstantTerm[Any]":
        return cls(value=data["value"])


# === CORE:
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


# === CORE:
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

# === CORE:
@dataclass(frozen=True)
class IndexedSchedule:
    """
    各イベント日の列。
    event_date / settlement_date をペアで持つ。
    fixing, coupon determination, settlement など変則日程をそのまま表現できる。
    """
    items: tuple[tuple[date, date], ...]
    role: str = "generic"

    def __post_init__(self) -> None:
        if not self.items:
            raise ValueError("schedule items must not be empty")
        event_dates = [event for event, _ in self.items]
        if event_dates != sorted(event_dates):
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


# === CORE:
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
# Component protocols
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
# === NEW: Leg-level barrier specs
# ============================================================

class LegBarrierSpec(Protocol):
    kind: ClassVar[str]

    def to_dict(self) -> dict[str, Any]:
        ...


# === NEW:
@dataclass(frozen=True)
class NoLegBarrier:
    kind: ClassVar[str] = "none"

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NoLegBarrier":
        return cls()


# === NEW:
@dataclass(frozen=True)
class EuropeanKnockInLegBarrier:
    kind: ClassVar[str] = "european_knock_in"

    trigger_level: Term[float]
    observation_schedule: ObservationSchedule
    breach_condition: str  # spot_lte_level / spot_gte_level

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


# ============================================================
# === NEW: Leg specs for structured FX payoff
# ============================================================

class FXLegSpec(Protocol):
    kind: ClassVar[str]

    def to_dict(self) -> dict[str, Any]:
        ...


# === NEW:
@dataclass(frozen=True)
class FXForwardLegSpec:
    """
    レシオフォワード等の forward-like payoff leg。
    """
    kind: ClassVar[str] = "fx_forward_leg"

    position: str  # buy_base / sell_base / long / short
    strike: Term[float]
    quantity_multiplier: Term[float]

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


# === NEW:
@dataclass(frozen=True)
class FXOptionLegSpec:
    """
    call / put の個別 leg。
    put にのみ KI を付ける等を自然に表現できる。
    """
    kind: ClassVar[str] = "fx_option_leg"

    option_type: str  # call / put
    position: str  # buy / sell
    strike: Term[float]
    quantity_multiplier: Term[float]
    barrier: LegBarrierSpec = field(default_factory=NoLegBarrier)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "option_type": self.option_type,
            "position": self.position,
            "strike": self.strike.to_dict(),
            "quantity_multiplier": self.quantity_multiplier.to_dict(),
            "barrier": self.barrier.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FXOptionLegSpec":
        return cls(
            option_type=data["option_type"],
            position=data["position"],
            strike=term_from_dict(data["strike"]),
            quantity_multiplier=term_from_dict(data["quantity_multiplier"]),
            barrier=leg_barrier_from_dict(data["barrier"]),
        )


def fx_leg_from_dict(data: dict[str, Any]) -> FXLegSpec:
    kind = data["kind"]
    if kind == "fx_forward_leg":
        return FXForwardLegSpec.from_dict(data)
    if kind == "fx_option_leg":
        return FXOptionLegSpec.from_dict(data)
    raise ValueError(f"unknown FX leg kind: {kind}")


# ============================================================
# Payoff components
# ============================================================

# === UPDATED:
@dataclass(frozen=True)
class FXStructuredPayoff:
    """
    前回の粗い payoff を差し替えた中核。
    FX payoff を leg の束として持つ。
    ノーマル / GAP / レンジGAP / カラー / ２段階 を同じ型で表現できる。
    """
    component_type: ClassVar[str] = "payoff"
    kind: ClassVar[str] = "fx_structured"

    underlying: UnderlyingRef
    payoff_style: str  # normal / gap / range_gap / collar / two_stage / custom
    schedule: IndexedSchedule
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

        # === NEW: style-specific validation
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
                if call_leg.position != "buy":
                    raise ValueError(f"{self.payoff_style} call leg must be buy")
                if put_leg.position != "sell":
                    raise ValueError(f"{self.payoff_style} put leg must be sell")
                if not isinstance(put_leg.barrier, EuropeanKnockInLegBarrier):
                    raise ValueError(f"{self.payoff_style} put leg must have European KI")
                if not isinstance(call_leg.barrier, NoLegBarrier):
                    raise ValueError(f"{self.payoff_style} call leg must not have barrier")

            if self.payoff_style == "collar":
                if call_leg.position != "buy":
                    raise ValueError("collar call leg must be buy")
                if put_leg.position != "sell":
                    raise ValueError("collar put leg must be sell")
                if not isinstance(call_leg.barrier, NoLegBarrier):
                    raise ValueError("collar call leg must not have barrier")
                if not isinstance(put_leg.barrier, NoLegBarrier):
                    raise ValueError("collar put leg must not have barrier")

            # strike relation は評価器なしでは完全判定できない。
            # === NEW:
            # ただし constant 同士のときは整合チェックする。
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
            "schedule": self.schedule.to_dict(),
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
            schedule=IndexedSchedule.from_dict(data["schedule"]),
            settlement_currency=data["settlement_currency"],
            base_notional=term_from_dict(data["base_notional"]),
            legs=tuple(fx_leg_from_dict(leg) for leg in data["legs"]),
            netting_method=data.get("netting_method", "per_event"),
        )
        obj.validate()
        return obj


# === 기존/CORE:
@dataclass(frozen=True)
class RangeCouponPayoff:
    """
    より伝統的な coupon payoff 用。
    今回、AKOCS では FXStructuredPayoff も使えるようにするため残すが、
    必須ではない。
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
        aft = data.get("accrual_factor_term")
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
            accrual_factor_term=None if aft is None else term_from_dict(aft),
        )


# ============================================================
# Product-level barrier components
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
    breach_condition: str

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


# ============================================================
# === CORE: ProductSpec composed from components
# ============================================================

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

        # === UPDATED:
        # family ごとの自然な組み合わせを検証
        if family == "TARF":
            if not isinstance(self.payoff, FXStructuredPayoff):
                raise ValueError("TARF payoff must be FXStructuredPayoff")
            self.payoff.validate()
            if self.payoff.payoff_style not in {"normal", "gap", "range_gap", "collar", "two_stage", "custom"}:
                raise ValueError("unsupported TARF payoff_style")

            if not isinstance(self.accrual, PositivePnLAccrual):
                raise ValueError("TARF accrual must be PositivePnLAccrual")
            if not isinstance(self.redemption, TargetHitRedemption):
                raise ValueError("TARF redemption must be TargetHitRedemption")
            if not isinstance(self.settlement, (StandardSettlement, FinalFixingSettlement)):
                raise ValueError("TARF settlement must be settlement component")
            if isinstance(self.barrier, AKOBarrier):
                raise ValueError("AKOBarrier is not valid for TARF family")

        elif family == "AKO_COUPON_SWAP":
            # === UPDATED:
            # AKOCS は FXStructuredPayoff も RangeCouponPayoff も許可。
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


# ============================================================
# === NEW: Factory helpers for FXStructuredPayoff styles
# ============================================================

def make_normal_payoff(
    *,
    underlying: UnderlyingRef,
    schedule: IndexedSchedule,
    settlement_currency: str,
    base_notional: Term[float],
    strike: Term[float],
    ratio: Term[float],
    forward_position: str = "sell_base",
) -> FXStructuredPayoff:
    payoff = FXStructuredPayoff(
        underlying=underlying,
        payoff_style="normal",
        schedule=schedule,
        settlement_currency=settlement_currency,
        base_notional=base_notional,
        legs=(
            FXForwardLegSpec(
                position=forward_position,
                strike=strike,
                quantity_multiplier=ratio,
            ),
        ),
    )
    payoff.validate()
    return payoff


def make_two_stage_payoff(
    *,
    underlying: UnderlyingRef,
    schedule: IndexedSchedule,
    settlement_currency: str,
    base_notional: Term[float],
    strike_steps: StepByIndexTerm[float],
    ratio: Term[float],
    forward_position: str = "sell_base",
) -> FXStructuredPayoff:
    payoff = FXStructuredPayoff(
        underlying=underlying,
        payoff_style="two_stage",
        schedule=schedule,
        settlement_currency=settlement_currency,
        base_notional=base_notional,
        legs=(
            FXForwardLegSpec(
                position=forward_position,
                strike=strike_steps,
                quantity_multiplier=ratio,
            ),
        ),
    )
    payoff.validate()
    return payoff


def make_gap_payoff(
    *,
    underlying: UnderlyingRef,
    schedule: IndexedSchedule,
    settlement_currency: str,
    base_notional: Term[float],
    call_strike: Term[float],
    put_strike: Term[float],
    call_ratio: Term[float],
    put_ratio: Term[float],
    put_ki_trigger: Term[float],
    put_ki_observation_schedule: ObservationSchedule,
    put_ki_breach_condition: str = "spot_lte_level",
) -> FXStructuredPayoff:
    payoff = FXStructuredPayoff(
        underlying=underlying,
        payoff_style="gap",
        schedule=schedule,
        settlement_currency=settlement_currency,
        base_notional=base_notional,
        legs=(
            FXOptionLegSpec(
                option_type="call",
                position="buy",
                strike=call_strike,
                quantity_multiplier=call_ratio,
                barrier=NoLegBarrier(),
            ),
            FXOptionLegSpec(
                option_type="put",
                position="sell",
                strike=put_strike,
                quantity_multiplier=put_ratio,
                barrier=EuropeanKnockInLegBarrier(
                    trigger_level=put_ki_trigger,
                    observation_schedule=put_ki_observation_schedule,
                    breach_condition=put_ki_breach_condition,
                ),
            ),
        ),
    )
    payoff.validate()
    return payoff


def make_range_gap_payoff(
    *,
    underlying: UnderlyingRef,
    schedule: IndexedSchedule,
    settlement_currency: str,
    base_notional: Term[float],
    shared_strike: Term[float],
    call_ratio: Term[float],
    put_ratio: Term[float],
    put_ki_trigger: Term[float],
    put_ki_observation_schedule: ObservationSchedule,
    put_ki_breach_condition: str = "spot_lte_level",
) -> FXStructuredPayoff:
    payoff = FXStructuredPayoff(
        underlying=underlying,
        payoff_style="range_gap",
        schedule=schedule,
        settlement_currency=settlement_currency,
        base_notional=base_notional,
        legs=(
            FXOptionLegSpec(
                option_type="call",
                position="buy",
                strike=shared_strike,
                quantity_multiplier=call_ratio,
                barrier=NoLegBarrier(),
            ),
            FXOptionLegSpec(
                option_type="put",
                position="sell",
                strike=shared_strike,
                quantity_multiplier=put_ratio,
                barrier=EuropeanKnockInLegBarrier(
                    trigger_level=put_ki_trigger,
                    observation_schedule=put_ki_observation_schedule,
                    breach_condition=put_ki_breach_condition,
                ),
            ),
        ),
    )
    payoff.validate()
    return payoff


def make_collar_payoff(
    *,
    underlying: UnderlyingRef,
    schedule: IndexedSchedule,
    settlement_currency: str,
    base_notional: Term[float],
    call_strike: Term[float],
    put_strike: Term[float],
    call_ratio: Term[float],
    put_ratio: Term[float],
) -> FXStructuredPayoff:
    payoff = FXStructuredPayoff(
        underlying=underlying,
        payoff_style="collar",
        schedule=schedule,
        settlement_currency=settlement_currency,
        base_notional=base_notional,
        legs=(
            FXOptionLegSpec(
                option_type="call",
                position="buy",
                strike=call_strike,
                quantity_multiplier=call_ratio,
                barrier=NoLegBarrier(),
            ),
            FXOptionLegSpec(
                option_type="put",
                position="sell",
                strike=put_strike,
                quantity_multiplier=put_ratio,
                barrier=NoLegBarrier(),
            ),
        ),
    )
    payoff.validate()
    return payoff


# ============================================================
# Typed facades
# ============================================================

# === UPDATED:
@dataclass(frozen=True)
class TARFSpec:
    """
    TARF family facade。
    payoff は normal/gap/range_gap/collar/two_stage/custom の
    いずれの FXStructuredPayoff でもよい。
    """
    identity: ProductIdentity
    payoff: FXStructuredPayoff
    target: Term[float]
    final_fixing_treatment: str = "full"
    product_barrier: BarrierComponent = field(default_factory=NoBarrier)

    def __post_init__(self) -> None:
        if self.identity.family != "TARF":
            raise ValueError("TARFSpec.identity.family must be 'TARF'")

    def to_product_spec(self) -> ProductSpec:
        spec = ProductSpec(
            identity=self.identity,
            payoff=self.payoff,
            barrier=self.product_barrier,
            accrual=PositivePnLAccrual(
                accrual_currency=self.payoff.settlement_currency,
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
                settlement_currency=self.payoff.settlement_currency,
            ),
            tags=("fx", "target_redemption", "tarf", self.payoff.payoff_style),
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
        if not isinstance(spec.payoff, FXStructuredPayoff):
            raise ValueError("unexpected payoff for TARF")
        if not isinstance(spec.redemption, TargetHitRedemption):
            raise ValueError("unexpected redemption for TARF")
        if not isinstance(spec.settlement, FinalFixingSettlement):
            raise ValueError("unexpected settlement for TARF")

        return cls(
            identity=spec.identity,
            payoff=spec.payoff,
            target=spec.redemption.target,
            final_fixing_treatment=spec.settlement.final_fixing_treatment,
            product_barrier=spec.barrier,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TARFSpec":
        return cls.from_product_spec(ProductSpec.from_dict(data))


# === UPDATED:
@dataclass(frozen=True)
class AKOCouponSwapSpec:
    """
    AKOCS family facade。
    payoff は FXStructuredPayoff も RangeCouponPayoff も許容する。
    今回の要件に合わせ、FXStructuredPayoff を coupon determination payoff
    として使うケースを自然に表せる。
    """
    identity: ProductIdentity
    payoff: PayoffComponent
    ako_trigger_level: Term[float]
    ako_observation_schedule: ObservationSchedule
    ako_breach_condition: str = "spot_lte_level"
    ako_action_on_breach: str = "cancel_remaining"
    redemption_on_ako: bool = True
    settlement_currency: str | None = None
    accrual_factor_term: Term[float] | None = None

    def __post_init__(self) -> None:
        if self.identity.family != "AKO_COUPON_SWAP":
            raise ValueError("AKOCouponSwapSpec.identity.family must be 'AKO_COUPON_SWAP'")
        if not isinstance(self.payoff, (FXStructuredPayoff, RangeCouponPayoff)):
            raise ValueError("AKOCouponSwapSpec.payoff must be FXStructuredPayoff or RangeCouponPayoff")

    def _infer_currency(self) -> str | None:
        if self.settlement_currency is not None:
            return self.settlement_currency
        if isinstance(self.payoff, FXStructuredPayoff):
            return self.payoff.settlement_currency
        if isinstance(self.payoff, RangeCouponPayoff):
            return self.payoff.coupon_currency
        return None

    def to_product_spec(self) -> ProductSpec:
        barrier = AKOBarrier(
            underlying=self.payoff.underlying,
            trigger_level=self.ako_trigger_level,
            observation_schedule=self.ako_observation_schedule,
            breach_condition=self.ako_breach_condition,
            action_on_breach=self.ako_action_on_breach,
        )

        spec = ProductSpec(
            identity=self.identity,
            payoff=self.payoff,
            barrier=barrier,
            accrual=CouponAccrual(
                observation_basis="formula_based",
                accrual_factor_term=self.accrual_factor_term,
            ),
            redemption=(
                BarrierTriggeredRedemption(action_on_barrier=self.ako_action_on_breach)
                if self.redemption_on_ako
                else NoRedemption()
            ),
            settlement=StandardSettlement(
                settlement_mode="cash",
                settlement_currency=self._infer_currency(),
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
        if not isinstance(spec.barrier, AKOBarrier):
            raise ValueError("unexpected barrier for AKO_COUPON_SWAP")

        settlement_currency = None
        if isinstance(spec.settlement, StandardSettlement):
            settlement_currency = spec.settlement.settlement_currency

        accrual_factor_term = None
        if isinstance(spec.accrual, CouponAccrual):
            accrual_factor_term = spec.accrual.accrual_factor_term

        return cls(
            identity=spec.identity,
            payoff=spec.payoff,
            ako_trigger_level=spec.barrier.trigger_level,
            ako_observation_schedule=spec.barrier.observation_schedule,
            ako_breach_condition=spec.barrier.breach_condition,
            ako_action_on_breach=spec.barrier.action_on_breach,
            redemption_on_ako=isinstance(spec.redemption, BarrierTriggeredRedemption),
            settlement_currency=settlement_currency,
            accrual_factor_term=accrual_factor_term,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AKOCouponSwapSpec":
        return cls.from_product_spec(ProductSpec.from_dict(data))


# ============================================================
# === EXAMPLE: TARF payoff examples
# ============================================================

def example_tarf_normal() -> TARFSpec:
    payoff = make_normal_payoff(
        underlying=UnderlyingRef("USDJPY", "FX"),
        schedule=IndexedSchedule(
            items=(
                (date(2026, 1, 10), date(2026, 1, 12)),
                (date(2026, 2, 10), date(2026, 2, 12)),
                (date(2026, 3, 10), date(2026, 3, 12)),
            ),
            role="tarf_fixing",
        ),
        settlement_currency="JPY",
        base_notional=ConstantTerm(1_000_000.0),
        strike=ConstantTerm(145.0),
        ratio=ConstantTerm(2.0),
        forward_position="sell_base",
    )
    return TARFSpec(
        identity=ProductIdentity("TARF", "TargetRedemptionForward", "1.0"),
        payoff=payoff,
        target=ConstantTerm(5_000_000.0),
        final_fixing_treatment="full",
    )


def example_tarf_two_stage() -> TARFSpec:
    payoff = make_two_stage_payoff(
        underlying=UnderlyingRef("USDJPY", "FX"),
        schedule=IndexedSchedule(
            items=(
                (date(2026, 1, 10), date(2026, 1, 12)),
                (date(2026, 2, 10), date(2026, 2, 12)),
                (date(2026, 3, 10), date(2026, 3, 12)),
                (date(2026, 4, 10), date(2026, 4, 14)),
                (date(2026, 5, 10), date(2026, 5, 12)),
                (date(2026, 6, 10), date(2026, 6, 12)),
            ),
            role="tarf_fixing",
        ),
        settlement_currency="JPY",
        base_notional=ConstantTerm(1_000_000.0),
        strike_steps=StepByIndexTerm(((0, 145.0), (3, 147.0))),
        ratio=ConstantTerm(2.0),
    )
    return TARFSpec(
        identity=ProductIdentity("TARF", "TargetRedemptionForward", "1.0"),
        payoff=payoff,
        target=ConstantTerm(5_000_000.0),
        final_fixing_treatment="full",
    )


def example_tarf_gap() -> TARFSpec:
    obs_schedule = ObservationSchedule(
        dates=(
            date(2026, 1, 10),
            date(2026, 2, 10),
            date(2026, 3, 10),
        ),
        role="put_ki_observation",
    )
    payoff = make_gap_payoff(
        underlying=UnderlyingRef("USDJPY", "FX"),
        schedule=IndexedSchedule(
            items=(
                (date(2026, 1, 10), date(2026, 1, 12)),
                (date(2026, 2, 10), date(2026, 2, 12)),
                (date(2026, 3, 10), date(2026, 3, 12)),
            ),
            role="tarf_fixing",
        ),
        settlement_currency="JPY",
        base_notional=ConstantTerm(1_000_000.0),
        call_strike=ConstantTerm(145.0),
        put_strike=ConstantTerm(150.0),
        call_ratio=ConstantTerm(1.0),
        put_ratio=ConstantTerm(2.0),
        put_ki_trigger=ConstantTerm(130.0),
        put_ki_observation_schedule=obs_schedule,
    )
    return TARFSpec(
        identity=ProductIdentity("TARF", "TargetRedemptionForward", "1.0"),
        payoff=payoff,
        target=ConstantTerm(5_000_000.0),
        final_fixing_treatment="partial",
    )


def example_tarf_range_gap() -> TARFSpec:
    obs_schedule = ObservationSchedule(
        dates=(
            date(2026, 1, 10),
            date(2026, 2, 10),
            date(2026, 3, 10),
        ),
        role="put_ki_observation",
    )
    payoff = make_range_gap_payoff(
        underlying=UnderlyingRef("USDJPY", "FX"),
        schedule=IndexedSchedule(
            items=(
                (date(2026, 1, 10), date(2026, 1, 12)),
                (date(2026, 2, 10), date(2026, 2, 12)),
                (date(2026, 3, 10), date(2026, 3, 12)),
            ),
            role="tarf_fixing",
        ),
        settlement_currency="JPY",
        base_notional=ConstantTerm(1_000_000.0),
        shared_strike=ConstantTerm(145.0),
        call_ratio=ConstantTerm(1.0),
        put_ratio=ConstantTerm(2.0),
        put_ki_trigger=ConstantTerm(130.0),
        put_ki_observation_schedule=obs_schedule,
    )
    return TARFSpec(
        identity=ProductIdentity("TARF", "TargetRedemptionForward", "1.0"),
        payoff=payoff,
        target=ConstantTerm(5_000_000.0),
        final_fixing_treatment="full",
    )


def example_tarf_collar() -> TARFSpec:
    payoff = make_collar_payoff(
        underlying=UnderlyingRef("USDJPY", "FX"),
        schedule=IndexedSchedule(
            items=(
                (date(2026, 1, 10), date(2026, 1, 12)),
                (date(2026, 2, 10), date(2026, 2, 12)),
                (date(2026, 3, 10), date(2026, 3, 12)),
            ),
            role="tarf_fixing",
        ),
        settlement_currency="JPY",
        base_notional=ConstantTerm(1_000_000.0),
        call_strike=ConstantTerm(150.0),
        put_strike=ConstantTerm(145.0),
        call_ratio=ConstantTerm(1.0),
        put_ratio=ConstantTerm(2.0),
    )
    return TARFSpec(
        identity=ProductIdentity("TARF", "TargetRedemptionForward", "1.0"),
        payoff=payoff,
        target=ConstantTerm(5_000_000.0),
        final_fixing_treatment="full",
    )


# ============================================================
# === EXAMPLE: AKO coupon swap examples
# ============================================================

def example_ako_coupon_swap_with_gap_payoff() -> AKOCouponSwapSpec:
    put_ki_obs = ObservationSchedule(
        dates=(
            date(2026, 1, 15),
            date(2026, 4, 15),
            date(2026, 7, 15),
            date(2026, 10, 15),
        ),
        role="put_ki_observation",
    )
    payoff = make_gap_payoff(
        underlying=UnderlyingRef("USDJPY", "FX"),
        schedule=IndexedSchedule(
            items=(
                (date(2026, 1, 15), date(2026, 1, 20)),
                (date(2026, 4, 15), date(2026, 4, 20)),
                (date(2026, 7, 15), date(2026, 7, 21)),
                (date(2026, 10, 15), date(2026, 10, 20)),
            ),
            role="coupon_fixing",
        ),
        settlement_currency="JPY",
        base_notional=StepByIndexTerm(((0, 10_000_000.0), (2, 8_000_000.0))),
        call_strike=ConstantTerm(145.0),
        put_strike=ConstantTerm(150.0),
        call_ratio=ConstantTerm(1.0),
        put_ratio=ConstantTerm(2.0),
        put_ki_trigger=ConstantTerm(130.0),
        put_ki_observation_schedule=put_ki_obs,
    )
    return AKOCouponSwapSpec(
        identity=ProductIdentity("AKO_COUPON_SWAP", "StructuredPayoffCouponSwapWithAKO", "1.0"),
        payoff=payoff,
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
        redemption_on_ako=True,
        settlement_currency="JPY",
        accrual_factor_term=ConstantTerm(0.25),
    )


# ============================================================
# === EXAMPLE: round-trip demo
# ============================================================

if __name__ == "__main__":
    products = [
        example_tarf_normal().to_product_spec(),
        example_tarf_two_stage().to_product_spec(),
        example_tarf_gap().to_product_spec(),
        example_tarf_range_gap().to_product_spec(),
        example_tarf_collar().to_product_spec(),
        example_ako_coupon_swap_with_gap_payoff().to_product_spec(),
    ]

    for i, spec in enumerate(products, start=1):
        data = spec.to_dict()
        restored = ProductSpec.from_dict(data)
        print(f"--- Product {i} ---")
        print("family:", restored.identity.family)
        print("type:", restored.identity.type_name)
        print("payoff kind:", restored.payoff.kind)
        if isinstance(restored.payoff, FXStructuredPayoff):
            print("payoff style:", restored.payoff.payoff_style)
        print("tags:", restored.tags)
        print()