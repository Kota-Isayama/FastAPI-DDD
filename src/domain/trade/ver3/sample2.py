from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, ClassVar, Generic, Protocol, TypeVar, runtime_checkable


T = TypeVar("T")


# ============================================
# Serializable base
# ============================================

@runtime_checkable
class Serializable(Protocol):
    def to_dict(self) -> dict[str, Any]:
        ...


# ============================================
# Event / runtime context
# ============================================

@dataclass(frozen=True)
class EventContext:
    event_date: date
    event_index: int
    leg_id: str | None = None


@dataclass
class RuntimeState:
    alive: bool = True
    knocked_out: bool = False
    knocked_in: bool = False
    accrued_amount: float = 0.0
    memory: dict[str, Any] = field(default_factory=dict)

    def copy(self) -> "RuntimeState":
        return RuntimeState(
            alive=self.alive,
            knocked_out=self.knocked_out,
            knocked_in=self.knocked_in,
            accrued_amount=self.accrued_amount,
            memory=dict(self.memory),
        )


@dataclass(frozen=True)
class Cashflow:
    payment_date: date
    currency: str
    amount: float
    direction: str  # "pay" / "receive"
    label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "payment_date": self.payment_date.isoformat(),
            "currency": self.currency,
            "amount": self.amount,
            "direction": self.direction,
            "label": self.label,
        }


# ============================================
# Market data abstraction
# ============================================

class MarketData(Protocol):
    def get_spot(self, underlying: str, on_date: date) -> float:
        ...


@dataclass(frozen=True)
class DictMarketData:
    """
    spot[(underlying, date)] = value
    """
    spots: dict[tuple[str, date], float]

    def get_spot(self, underlying: str, on_date: date) -> float:
        key = (underlying, on_date)
        if key not in self.spots:
            raise KeyError(f"missing spot for {underlying} on {on_date.isoformat()}")
        return self.spots[key]


# ============================================
# Term abstraction
# ============================================

class Term(Generic[T], Serializable, Protocol):
    def resolve(self, ctx: EventContext, state: RuntimeState | None = None) -> T:
        ...


@dataclass(frozen=True)
class ConstantTerm(Generic[T]):
    kind: ClassVar[str] = "constant"
    value: T

    def resolve(self, ctx: EventContext, state: RuntimeState | None = None) -> T:
        return self.value

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "value": self.value}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConstantTerm[Any]":
        return cls(value=data["value"])


@dataclass(frozen=True)
class StepByIndexTerm(Generic[T]):
    kind: ClassVar[str] = "step_by_index"
    steps: tuple[tuple[int, T], ...]

    def __post_init__(self) -> None:
        if not self.steps:
            raise ValueError("steps must not be empty")
        starts = [start for start, _ in self.steps]
        if starts != sorted(starts):
            raise ValueError("steps must be sorted ascending")

    def resolve(self, ctx: EventContext, state: RuntimeState | None = None) -> T:
        value = self.steps[0][1]
        for start, v in self.steps:
            if ctx.event_index >= start:
                value = v
            else:
                break
        return value

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "steps": [[i, v] for i, v in self.steps]}

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
                raise ValueError("start must be <= end")

    def resolve(self, ctx: EventContext, state: RuntimeState | None = None) -> T:
        for start, end, value in self.ranges:
            if start <= ctx.event_date <= end:
                return value
        raise ValueError(f"no range matched {ctx.event_date.isoformat()}")

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
                    date.fromisoformat(x["start"]),
                    date.fromisoformat(x["end"]),
                    x["value"],
                )
                for x in data["ranges"]
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


# ============================================
# Schedules
# ============================================

@dataclass(frozen=True)
class Schedule:
    dates: tuple[date, ...]

    def __post_init__(self) -> None:
        if not self.dates:
            raise ValueError("schedule dates must not be empty")
        if tuple(sorted(self.dates)) != self.dates:
            raise ValueError("schedule dates must be sorted")

    def to_dict(self) -> dict[str, Any]:
        return {"dates": [d.isoformat() for d in self.dates]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Schedule":
        return cls(dates=tuple(date.fromisoformat(x) for x in data["dates"]))


@dataclass(frozen=True)
class IndexedSchedule:
    items: tuple[tuple[date, date], ...]  # (fixing_date, settlement_date)

    def __post_init__(self) -> None:
        if not self.items:
            raise ValueError("items must not be empty")
        fixing_dates = [fix for fix, _ in self.items]
        if fixing_dates != sorted(fixing_dates):
            raise ValueError("fixing dates must be sorted")

    def contexts(self, leg_id: str | None = None) -> tuple[EventContext, ...]:
        return tuple(
            EventContext(event_date=fixing_date, event_index=i, leg_id=leg_id)
            for i, (fixing_date, _) in enumerate(self.items)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [
                {
                    "fixing_date": fixing.isoformat(),
                    "settlement_date": settlement.isoformat(),
                }
                for fixing, settlement in self.items
            ]
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IndexedSchedule":
        return cls(
            items=tuple(
                (
                    date.fromisoformat(x["fixing_date"]),
                    date.fromisoformat(x["settlement_date"]),
                )
                for x in data["items"]
            )
        )


# ============================================
# Product identity
# ============================================

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


# ============================================
# Contract program / clause IR
# ============================================

class Clause(Protocol, Serializable):
    def execute(self, market: MarketData, state: RuntimeState) -> tuple[RuntimeState, list[Cashflow]]:
        ...


@dataclass(frozen=True)
class ContractProgram:
    identity: ProductIdentity
    clauses: tuple[Clause, ...]

    def run(self, market: MarketData) -> tuple[RuntimeState, list[Cashflow]]:
        state = RuntimeState()
        all_cashflows: list[Cashflow] = []

        for clause in self.clauses:
            if not state.alive:
                break
            state, cfs = clause.execute(market=market, state=state)
            all_cashflows.extend(cfs)

        return state, all_cashflows

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "clauses": [clause.to_dict() for clause in self.clauses],
        }


# ============================================
# TARF clause
# ============================================

@dataclass(frozen=True)
class TarfFixingClause:
    kind: ClassVar[str] = "tarf_fixing"

    underlying: str
    direction: str
    ctx: EventContext
    settlement_date: date

    strike: Term[float]
    target: Term[float]
    notional: Term[float]
    leverage_multiplier: Term[float]
    settlement_currency: str
    full_final_fixing: bool = False

    def execute(self, market: MarketData, state: RuntimeState) -> tuple[RuntimeState, list[Cashflow]]:
        next_state = state.copy()
        if not next_state.alive:
            return next_state, []

        spot = market.get_spot(self.underlying, self.ctx.event_date)
        strike = self.strike.resolve(self.ctx, next_state)
        target = self.target.resolve(self.ctx, next_state)
        notional = self.notional.resolve(self.ctx, next_state)
        leverage = self.leverage_multiplier.resolve(self.ctx, next_state)

        # ここは単純化した payoff の例。
        # exporter と importer の厳密な sign は実務仕様に合わせて調整する。
        raw_unit_pnl = spot - strike

        if raw_unit_pnl >= 0:
            effective_amount = raw_unit_pnl * notional
            direction = "receive"
        else:
            effective_amount = abs(raw_unit_pnl) * notional * leverage
            direction = "pay"

        positive_pnl = max(raw_unit_pnl, 0.0) * notional
        next_state.accrued_amount += positive_pnl

        label = (
            f"TARF fixing #{self.ctx.event_index} "
            f"(spot={spot}, strike={strike}, target={target}, accrued={next_state.accrued_amount})"
        )

        cashflow = Cashflow(
            payment_date=self.settlement_date,
            currency=self.settlement_currency,
            amount=effective_amount,
            direction=direction,
            label=label,
        )

        if next_state.accrued_amount >= target:
            next_state.knocked_out = True
            next_state.alive = False

            if not self.full_final_fixing:
                # simplest partial handling:
                # target 到達 fixing は支払を消す/別処理にする代わりの簡略版
                return next_state, []

        return next_state, [cashflow]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "underlying": self.underlying,
            "direction": self.direction,
            "ctx": {
                "event_date": self.ctx.event_date.isoformat(),
                "event_index": self.ctx.event_index,
                "leg_id": self.ctx.leg_id,
            },
            "settlement_date": self.settlement_date.isoformat(),
            "strike": self.strike.to_dict(),
            "target": self.target.to_dict(),
            "notional": self.notional.to_dict(),
            "leverage_multiplier": self.leverage_multiplier.to_dict(),
            "settlement_currency": self.settlement_currency,
            "full_final_fixing": self.full_final_fixing,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TarfFixingClause":
        ctx_data = data["ctx"]
        return cls(
            underlying=data["underlying"],
            direction=data["direction"],
            ctx=EventContext(
                event_date=date.fromisoformat(ctx_data["event_date"]),
                event_index=ctx_data["event_index"],
                leg_id=ctx_data.get("leg_id"),
            ),
            settlement_date=date.fromisoformat(data["settlement_date"]),
            strike=term_from_dict(data["strike"]),
            target=term_from_dict(data["target"]),
            notional=term_from_dict(data["notional"]),
            leverage_multiplier=term_from_dict(data["leverage_multiplier"]),
            settlement_currency=data["settlement_currency"],
            full_final_fixing=data.get("full_final_fixing", False),
        )


# ============================================
# AKO swap clauses
# ============================================

@dataclass(frozen=True)
class AKOObservationClause:
    kind: ClassVar[str] = "ako_observation"

    underlying: str
    ctx: EventContext
    trigger_level: Term[float]
    mode: str  # "cancel_remaining", "cancel_next_coupon"

    def execute(self, market: MarketData, state: RuntimeState) -> tuple[RuntimeState, list[Cashflow]]:
        next_state = state.copy()
        if not next_state.alive:
            return next_state, []

        spot = market.get_spot(self.underlying, self.ctx.event_date)
        trigger = self.trigger_level.resolve(self.ctx, next_state)

        # ここも簡略化。spot <= trigger で AKO 発火の例。
        if spot <= trigger:
            if self.mode == "cancel_remaining":
                next_state.knocked_out = True
                next_state.alive = False
            elif self.mode == "cancel_next_coupon":
                next_state.memory["skip_next_coupon"] = True
            else:
                raise ValueError(f"unsupported AKO mode: {self.mode}")

        return next_state, []

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "underlying": self.underlying,
            "ctx": {
                "event_date": self.ctx.event_date.isoformat(),
                "event_index": self.ctx.event_index,
                "leg_id": self.ctx.leg_id,
            },
            "trigger_level": self.trigger_level.to_dict(),
            "mode": self.mode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AKOObservationClause":
        ctx_data = data["ctx"]
        return cls(
            underlying=data["underlying"],
            ctx=EventContext(
                event_date=date.fromisoformat(ctx_data["event_date"]),
                event_index=ctx_data["event_index"],
                leg_id=ctx_data.get("leg_id"),
            ),
            trigger_level=term_from_dict(data["trigger_level"]),
            mode=data["mode"],
        )


@dataclass(frozen=True)
class CouponPaymentClause:
    kind: ClassVar[str] = "coupon_payment"

    ctx: EventContext
    settlement_date: date
    notional: Term[float]
    base_rate: Term[float]
    spread: Term[float]
    leverage: Term[float]
    currency: str
    pay_receive: str  # "pay" / "receive"

    def execute(self, market: MarketData, state: RuntimeState) -> tuple[RuntimeState, list[Cashflow]]:
        next_state = state.copy()
        if not next_state.alive:
            return next_state, []

        if next_state.memory.pop("skip_next_coupon", False):
            return next_state, []

        notional = self.notional.resolve(self.ctx, next_state)
        base_rate = self.base_rate.resolve(self.ctx, next_state)
        spread = self.spread.resolve(self.ctx, next_state)
        leverage = self.leverage.resolve(self.ctx, next_state)

        coupon_rate = base_rate + spread * leverage
        amount = notional * coupon_rate

        cf = Cashflow(
            payment_date=self.settlement_date,
            currency=self.currency,
            amount=amount,
            direction=self.pay_receive,
            label=f"Coupon #{self.ctx.event_index} (rate={coupon_rate})",
        )
        return next_state, [cf]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "ctx": {
                "event_date": self.ctx.event_date.isoformat(),
                "event_index": self.ctx.event_index,
                "leg_id": self.ctx.leg_id,
            },
            "settlement_date": self.settlement_date.isoformat(),
            "notional": self.notional.to_dict(),
            "base_rate": self.base_rate.to_dict(),
            "spread": self.spread.to_dict(),
            "leverage": self.leverage.to_dict(),
            "currency": self.currency,
            "pay_receive": self.pay_receive,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CouponPaymentClause":
        ctx_data = data["ctx"]
        return cls(
            ctx=EventContext(
                event_date=date.fromisoformat(ctx_data["event_date"]),
                event_index=ctx_data["event_index"],
                leg_id=ctx_data.get("leg_id"),
            ),
            settlement_date=date.fromisoformat(data["settlement_date"]),
            notional=term_from_dict(data["notional"]),
            base_rate=term_from_dict(data["base_rate"]),
            spread=term_from_dict(data["spread"]),
            leverage=term_from_dict(data["leverage"]),
            currency=data["currency"],
            pay_receive=data["pay_receive"],
        )


def clause_from_dict(data: dict[str, Any]) -> Clause:
    kind = data["kind"]
    if kind == "tarf_fixing":
        return TarfFixingClause.from_dict(data)
    if kind == "ako_observation":
        return AKOObservationClause.from_dict(data)
    if kind == "coupon_payment":
        return CouponPaymentClause.from_dict(data)
    raise ValueError(f"unknown clause kind: {kind}")


# ============================================
# Product models
# ============================================

@dataclass(frozen=True)
class AKORule:
    trigger_level: Term[float]
    observation_schedule: Schedule
    mode: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger_level": self.trigger_level.to_dict(),
            "observation_schedule": self.observation_schedule.to_dict(),
            "mode": self.mode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AKORule":
        return cls(
            trigger_level=term_from_dict(data["trigger_level"]),
            observation_schedule=Schedule.from_dict(data["observation_schedule"]),
            mode=data["mode"],
        )


@dataclass(frozen=True)
class RangeCouponFormula:
    base_rate: Term[float]
    spread: Term[float]
    leverage: Term[float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "range_coupon_formula",
            "base_rate": self.base_rate.to_dict(),
            "spread": self.spread.to_dict(),
            "leverage": self.leverage.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RangeCouponFormula":
        return cls(
            base_rate=term_from_dict(data["base_rate"]),
            spread=term_from_dict(data["spread"]),
            leverage=term_from_dict(data["leverage"]),
        )


@dataclass(frozen=True)
class TARF:
    identity: ProductIdentity
    underlying: str
    direction: str
    schedule: IndexedSchedule
    strike: Term[float]
    target: Term[float]
    notional: Term[float]
    leverage_multiplier: Term[float]
    settlement_currency: str
    full_final_fixing: bool = False

    def __post_init__(self) -> None:
        if self.identity.family != "TARF":
            raise ValueError("identity.family must be TARF")

    def compile(self) -> ContractProgram:
        clauses: list[Clause] = []

        for (fixing_date, settlement_date), ctx in zip(
            self.schedule.items,
            self.schedule.contexts(leg_id="tarf"),
        ):
            clauses.append(
                TarfFixingClause(
                    underlying=self.underlying,
                    direction=self.direction,
                    ctx=ctx,
                    settlement_date=settlement_date,
                    strike=self.strike,
                    target=self.target,
                    notional=self.notional,
                    leverage_multiplier=self.leverage_multiplier,
                    settlement_currency=self.settlement_currency,
                    full_final_fixing=self.full_final_fixing,
                )
            )

        return ContractProgram(identity=self.identity, clauses=tuple(clauses))

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "underlying": self.underlying,
            "direction": self.direction,
            "schedule": self.schedule.to_dict(),
            "terms": {
                "strike": self.strike.to_dict(),
                "target": self.target.to_dict(),
                "notional": self.notional.to_dict(),
                "leverage_multiplier": self.leverage_multiplier.to_dict(),
            },
            "settlement_currency": self.settlement_currency,
            "full_final_fixing": self.full_final_fixing,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TARF":
        return cls(
            identity=ProductIdentity.from_dict(data["identity"]),
            underlying=data["underlying"],
            direction=data["direction"],
            schedule=IndexedSchedule.from_dict(data["schedule"]),
            strike=term_from_dict(data["terms"]["strike"]),
            target=term_from_dict(data["terms"]["target"]),
            notional=term_from_dict(data["terms"]["notional"]),
            leverage_multiplier=term_from_dict(data["terms"]["leverage_multiplier"]),
            settlement_currency=data["settlement_currency"],
            full_final_fixing=data.get("full_final_fixing", False),
        )


@dataclass(frozen=True)
class AKOCouponSwap:
    identity: ProductIdentity
    underlying: str
    pay_receive: str
    notional: Term[float]
    coupon_currency: str
    coupon_schedule: IndexedSchedule
    coupon_formula: RangeCouponFormula
    ako_rule: AKORule | None = None

    def __post_init__(self) -> None:
        if self.identity.family != "AKO_COUPON_SWAP":
            raise ValueError("identity.family must be AKO_COUPON_SWAP")

    def compile(self) -> ContractProgram:
        clauses: list[Clause] = []

        if self.ako_rule is not None:
            obs_dates = list(self.ako_rule.observation_schedule.dates)
            for i, obs_date in enumerate(obs_dates):
                clauses.append(
                    AKOObservationClause(
                        underlying=self.underlying,
                        ctx=EventContext(
                            event_date=obs_date,
                            event_index=i,
                            leg_id="ako_obs",
                        ),
                        trigger_level=self.ako_rule.trigger_level,
                        mode=self.ako_rule.mode,
                    )
                )

        for (fixing_date, settlement_date), ctx in zip(
            self.coupon_schedule.items,
            self.coupon_schedule.contexts(leg_id="coupon"),
        ):
            clauses.append(
                CouponPaymentClause(
                    ctx=ctx,
                    settlement_date=settlement_date,
                    notional=self.notional,
                    base_rate=self.coupon_formula.base_rate,
                    spread=self.coupon_formula.spread,
                    leverage=self.coupon_formula.leverage,
                    currency=self.coupon_currency,
                    pay_receive=self.pay_receive,
                )
            )

        clauses_sorted = tuple(sorted(clauses, key=lambda c: _clause_event_date(c)))
        return ContractProgram(identity=self.identity, clauses=clauses_sorted)

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "underlying": self.underlying,
            "pay_receive": self.pay_receive,
            "notional": self.notional.to_dict(),
            "coupon_currency": self.coupon_currency,
            "coupon_schedule": self.coupon_schedule.to_dict(),
            "coupon_formula": self.coupon_formula.to_dict(),
            "ako_rule": None if self.ako_rule is None else self.ako_rule.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AKOCouponSwap":
        ako = data.get("ako_rule")
        return cls(
            identity=ProductIdentity.from_dict(data["identity"]),
            underlying=data["underlying"],
            pay_receive=data["pay_receive"],
            notional=term_from_dict(data["notional"]),
            coupon_currency=data["coupon_currency"],
            coupon_schedule=IndexedSchedule.from_dict(data["coupon_schedule"]),
            coupon_formula=RangeCouponFormula.from_dict(data["coupon_formula"]),
            ako_rule=None if ako is None else AKORule.from_dict(ako),
        )


def _clause_event_date(clause: Clause) -> date:
    if isinstance(clause, TarfFixingClause):
        return clause.ctx.event_date
    if isinstance(clause, AKOObservationClause):
        return clause.ctx.event_date
    if isinstance(clause, CouponPaymentClause):
        return clause.ctx.event_date
    raise TypeError(f"unsupported clause type: {type(clause)!r}")


# ============================================
# Example usage
# ============================================

def example_tarf() -> TARF:
    return TARF(
        identity=ProductIdentity("TARF", "TargetRedemptionForward", "1.0"),
        underlying="USDJPY",
        direction="exporter",
        schedule=IndexedSchedule(
            items=(
                (date(2026, 1, 10), date(2026, 1, 12)),
                (date(2026, 2, 10), date(2026, 2, 12)),
                (date(2026, 3, 10), date(2026, 3, 12)),
                (date(2026, 4, 10), date(2026, 4, 14)),
                (date(2026, 5, 10), date(2026, 5, 12)),
                (date(2026, 6, 10), date(2026, 6, 12)),
            )
        ),
        strike=StepByIndexTerm(
            steps=(
                (0, 145.0),
                (3, 147.0),
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
        full_final_fixing=True,
    )


def example_ako_swap() -> AKOCouponSwap:
    return AKOCouponSwap(
        identity=ProductIdentity("AKO_COUPON_SWAP", "RangeCouponSwapWithAKO", "1.0"),
        underlying="USDJPY",
        pay_receive="receive",
        notional=StepByIndexTerm(
            steps=(
                (0, 10_000_000.0),
                (2, 8_000_000.0),
            )
        ),
        coupon_currency="JPY",
        coupon_schedule=IndexedSchedule(
            items=(
                (date(2026, 1, 15), date(2026, 1, 20)),
                (date(2026, 4, 15), date(2026, 4, 20)),
                (date(2026, 7, 15), date(2026, 7, 21)),
                (date(2026, 10, 15), date(2026, 10, 20)),
            )
        ),
        coupon_formula=RangeCouponFormula(
            base_rate=ConstantTerm(0.015),
            spread=StepByIndexTerm(
                steps=(
                    (0, 0.0020),
                    (2, 0.0035),
                )
            ),
            leverage=ConstantTerm(1.0),
        ),
        ako_rule=AKORule(
            trigger_level=ConstantTerm(130.0),
            observation_schedule=Schedule(
                dates=(
                    date(2026, 1, 15),
                    date(2026, 4, 15),
                    date(2026, 7, 15),
                    date(2026, 10, 15),
                )
            ),
            mode="cancel_remaining",
        ),
    )


if __name__ == "__main__":
    market = DictMarketData(
        spots={
            ("USDJPY", date(2026, 1, 10)): 146.0,
            ("USDJPY", date(2026, 2, 10)): 144.0,
            ("USDJPY", date(2026, 3, 10)): 148.0,
            ("USDJPY", date(2026, 4, 10)): 149.0,
            ("USDJPY", date(2026, 5, 10)): 143.0,
            ("USDJPY", date(2026, 6, 10)): 150.0,
            ("USDJPY", date(2026, 1, 15)): 135.0,
            ("USDJPY", date(2026, 4, 15)): 132.0,
            ("USDJPY", date(2026, 7, 15)): 129.0,
            ("USDJPY", date(2026, 10, 15)): 128.0,
        }
    )

    tarf = example_tarf()
    tarf_program = tarf.compile()
    tarf_state, tarf_cfs = tarf_program.run(market)

    print("=== TARF cashflows ===")
    for cf in tarf_cfs:
        print(cf.to_dict())
    print("TARF final state:", tarf_state)

    swap = example_ako_swap()
    swap_program = swap.compile()
    swap_state, swap_cfs = swap_program.run(market)

    print("\n=== AKO swap cashflows ===")
    for cf in swap_cfs:
        print(cf.to_dict())
    print("AKO final state:", swap_state)