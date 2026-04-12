from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, ClassVar, Generic, Protocol, TypeVar, runtime_checkable


T = TypeVar("T")


# =========
# Base serialization
# =========

@runtime_checkable
class Serializable(Protocol):
    def to_dict(self) -> dict[str, Any]:
        ...


# =========
# Context
# =========

@dataclass(frozen=True)
class EventContext:
    event_date: date
    event_index: int
    leg_id: str | None = None
    state_snapshot: dict[str, Any] | None = None


# =========
# Term abstraction
# =========

class Term(Generic[T], Serializable, Protocol):
    def resolve(self, ctx: EventContext) -> T:
        ...


@dataclass(frozen=True)
class ConstantTerm(Generic[T]):
    kind: ClassVar[str] = "constant"
    value: T

    def resolve(self, ctx: EventContext) -> T:
        return self.value

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "value": self.value}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConstantTerm[Any]":
        return cls(value=data["value"])


@dataclass(frozen=True)
class StepByIndexTerm(Generic[T]):
    """
    start_index 以上で value が有効になる step term
    例:
      [(0, 145.0), (6, 147.0)]
      -> 0~5回目は145, 6回目以降は147
    """
    kind: ClassVar[str] = "step_by_index"
    steps: tuple[tuple[int, T], ...]

    def __post_init__(self) -> None:
        if not self.steps:
            raise ValueError("steps must not be empty")
        starts = [s for s, _ in self.steps]
        if starts != sorted(starts):
            raise ValueError("steps must be sorted by start index ascending")

    def resolve(self, ctx: EventContext) -> T:
        current = self.steps[0][1]
        for start, value in self.steps:
            if ctx.event_index >= start:
                current = value
            else:
                break
        return current

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "steps": [[i, v] for i, v in self.steps]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StepByIndexTerm[Any]":
        return cls(steps=tuple((int(i), v) for i, v in data["steps"]))


@dataclass(frozen=True)
class DateRangeTerm(Generic[T]):
    """
    start <= event_date <= end の範囲で値を切り替える
    """
    kind: ClassVar[str] = "date_range"
    ranges: tuple[tuple[date, date, T], ...]

    def __post_init__(self) -> None:
        if not self.ranges:
            raise ValueError("ranges must not be empty")
        for start, end, _ in self.ranges:
            if start > end:
                raise ValueError("range start must be <= end")

    def resolve(self, ctx: EventContext) -> T:
        for start, end, value in self.ranges:
            if start <= ctx.event_date <= end:
                return value
        raise ValueError(f"no matching range for {ctx.event_date.isoformat()}")

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
                (date.fromisoformat(r["start"]), date.fromisoformat(r["end"]), r["value"])
                for r in data["ranges"]
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


# =========
# Schedule
# =========

@dataclass(frozen=True)
class Schedule:
    dates: tuple[date, ...]

    def __post_init__(self) -> None:
        if not self.dates:
            raise ValueError("schedule dates must not be empty")
        if tuple(sorted(self.dates)) != self.dates:
            raise ValueError("schedule dates must be sorted ascending")

    def to_dict(self) -> dict[str, Any]:
        return {"dates": [d.isoformat() for d in self.dates]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Schedule":
        return cls(dates=tuple(date.fromisoformat(x) for x in data["dates"]))


@dataclass(frozen=True)
class IndexedSchedule:
    """
    fixing date と settlement date のペア列
    変則 schedule を素直に表したいので tuple のまま持つ
    """
    items: tuple[tuple[date, date], ...]

    def __post_init__(self) -> None:
        if not self.items:
            raise ValueError("items must not be empty")
        fixing_dates = [fix for fix, _ in self.items]
        if fixing_dates != sorted(fixing_dates):
            raise ValueError("fixing dates must be sorted ascending")

    def __len__(self) -> int:
        return len(self.items)

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


# =========
# Product identity
# =========

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


# =========
# IR-ish cashflow output
# =========

@dataclass(frozen=True)
class Cashflow:
    payment_date: date
    currency: str
    amount: float
    direction: str  # "pay" or "receive"
    label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "payment_date": self.payment_date.isoformat(),
            "currency": self.currency,
            "amount": self.amount,
            "direction": self.direction,
            "label": self.label,
        }


# =========
# TARF
# =========

@dataclass(frozen=True)
class TARF:
    """
    family identity は TARF のまま保ちつつ、
    strike / notional / leverage / target は time-varying term にできる。
    """
    identity: ProductIdentity
    underlying: str
    direction: str  # "exporter" / "importer" など
    schedule: IndexedSchedule

    strike: Term[float]
    target: Term[float]
    notional: Term[float]
    leverage_multiplier: Term[float]

    settlement_currency: str
    full_final_fixing: bool = False

    def __post_init__(self) -> None:
        if self.identity.family != "TARF":
            raise ValueError("TARF.identity.family must be 'TARF'")

    def resolved_fixings(self) -> list[dict[str, Any]]:
        """
        各 fixing 時点で term を resolve した結果。
        compile 前の確認や監査表示向け。
        """
        out: list[dict[str, Any]] = []
        for i, ((fixing_date, settlement_date), ctx) in enumerate(
            zip(self.schedule.items, self.schedule.contexts())
        ):
            out.append(
                {
                    "fixing_index": i,
                    "fixing_date": fixing_date.isoformat(),
                    "settlement_date": settlement_date.isoformat(),
                    "strike": self.strike.resolve(ctx),
                    "target": self.target.resolve(ctx),
                    "notional": self.notional.resolve(ctx),
                    "leverage_multiplier": self.leverage_multiplier.resolve(ctx),
                }
            )
        return out

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


# =========
# AKO Coupon Swap
# =========

@dataclass(frozen=True)
class AKORule:
    """
    ここでは最小限にしている。
    実務では trigger の向きや monitoring、AKO 後の扱いなどを増やす。
    """
    trigger_level: Term[float]
    observation_schedule: Schedule
    mode: str  # 例: "cancel_remaining", "cancel_next_coupon"

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
    """
    例として、coupon rate を time-varying にする。
    必要なら lower/upper bound も Term にできる。
    """
    base_rate: Term[float]
    spread: Term[float]
    leverage: Term[float]

    def rate_at(self, ctx: EventContext) -> float:
        return (
            self.base_rate.resolve(ctx)
            + self.spread.resolve(ctx) * self.leverage.resolve(ctx)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "range_coupon_formula",
            "base_rate": self.base_rate.to_dict(),
            "spread": self.spread.to_dict(),
            "leverage": self.leverage.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RangeCouponFormula":
        if data["kind"] != "range_coupon_formula":
            raise ValueError(f"unsupported coupon formula kind: {data['kind']}")
        return cls(
            base_rate=term_from_dict(data["base_rate"]),
            spread=term_from_dict(data["spread"]),
            leverage=term_from_dict(data["leverage"]),
        )


@dataclass(frozen=True)
class AKOCouponSwap:
    identity: ProductIdentity
    underlying: str
    pay_receive: str  # "pay" / "receive"
    notional: Term[float]
    coupon_currency: str
    coupon_schedule: IndexedSchedule
    coupon_formula: RangeCouponFormula
    ako_rule: AKORule | None = None

    def __post_init__(self) -> None:
        if self.identity.family != "AKO_COUPON_SWAP":
            raise ValueError("AKOCouponSwap.identity.family must be 'AKO_COUPON_SWAP'")

    def resolved_coupons(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for i, ((fixing_date, settlement_date), ctx) in enumerate(
            zip(self.coupon_schedule.items, self.coupon_schedule.contexts(leg_id="coupon"))
        ):
            out.append(
                {
                    "coupon_index": i,
                    "fixing_date": fixing_date.isoformat(),
                    "settlement_date": settlement_date.isoformat(),
                    "notional": self.notional.resolve(ctx),
                    "coupon_rate": self.coupon_formula.rate_at(ctx),
                }
            )
        return out

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
        ako_data = data.get("ako_rule")
        return cls(
            identity=ProductIdentity.from_dict(data["identity"]),
            underlying=data["underlying"],
            pay_receive=data["pay_receive"],
            notional=term_from_dict(data["notional"]),
            coupon_currency=data["coupon_currency"],
            coupon_schedule=IndexedSchedule.from_dict(data["coupon_schedule"]),
            coupon_formula=RangeCouponFormula.from_dict(data["coupon_formula"]),
            ako_rule=None if ako_data is None else AKORule.from_dict(ako_data),
        )


# =========
# Example usage
# =========

def example_tarf() -> TARF:
    return TARF(
        identity=ProductIdentity(
            family="TARF",
            type_name="TargetRedemptionForward",
            version="1.0",
        ),
        underlying="USDJPY",
        direction="exporter",
        schedule=IndexedSchedule(
            items=(
                (date(2026, 1, 10), date(2026, 1, 12)),
                (date(2026, 2, 10), date(2026, 2, 12)),
                (date(2026, 3, 10), date(2026, 3, 12)),
                (date(2026, 4, 10), date(2026, 4, 14)),  # 変則 settlement
                (date(2026, 5, 10), date(2026, 5, 12)),
                (date(2026, 6, 10), date(2026, 6, 12)),
                (date(2026, 7, 10), date(2026, 7, 14)),
            )
        ),
        strike=StepByIndexTerm(
            steps=(
                (0, 145.00),
                (4, 147.00),  # 4回目 fixing から strike 変更
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


def example_ako_coupon_swap() -> AKOCouponSwap:
    return AKOCouponSwap(
        identity=ProductIdentity(
            family="AKO_COUPON_SWAP",
            type_name="RangeCouponSwapWithAKO",
            version="1.0",
        ),
        underlying="USDJPY",
        pay_receive="receive",
        notional=StepByIndexTerm(
            steps=(
                (0, 10_000_000.0),
                (3, 8_000_000.0),  # 途中から notional 変更
            )
        ),
        coupon_currency="JPY",
        coupon_schedule=IndexedSchedule(
            items=(
                (date(2026, 1, 15), date(2026, 1, 20)),
                (date(2026, 4, 15), date(2026, 4, 20)),
                (date(2026, 7, 15), date(2026, 7, 21)),  # 変則 settlement
                (date(2026, 10, 15), date(2026, 10, 20)),
            )
        ),
        coupon_formula=RangeCouponFormula(
            base_rate=ConstantTerm(0.015),
            spread=StepByIndexTerm(
                steps=(
                    (0, 0.0020),
                    (2, 0.0035),  # 後半だけ spread 変更
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
    tarf = example_tarf()
    print("=== TARF resolved fixings ===")
    for row in tarf.resolved_fixings():
        print(row)

    tarf_data = tarf.to_dict()
    tarf_restored = TARF.from_dict(tarf_data)
    print("\n=== TARF restored ===")
    print(tarf_restored.to_dict())

    swap = example_ako_coupon_swap()
    print("\n=== AKO coupon swap resolved coupons ===")
    for row in swap.resolved_coupons():
        print(row)

    swap_data = swap.to_dict()
    swap_restored = AKOCouponSwap.from_dict(swap_data)
    print("\n=== AKO coupon swap restored ===")
    print(swap_restored.to_dict())