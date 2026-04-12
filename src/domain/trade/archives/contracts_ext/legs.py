from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Protocol

from .barriers import LegBarrier, NoLegBarrier, leg_barrier_from_dict
from .identity import CmsIndexRef, RateIndexRef
from .terms import AnyTerm, term_from_dict


class LegSpec(Protocol):
    kind: ClassVar[str]

    def to_dict(self) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class FXForwardLegSpec:
    kind: ClassVar[str] = "fx_forward_leg"
    position: str
    strike: AnyTerm
    quantity_multiplier: AnyTerm

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


@dataclass(frozen=True)
class FXOptionLegSpec:
    kind: ClassVar[str] = "fx_option_leg"
    option_type: str
    position: str
    strike: AnyTerm
    quantity_multiplier: AnyTerm
    barrier: LegBarrier = field(default_factory=NoLegBarrier)

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


@dataclass(frozen=True)
class FixedRateLegSpec:
    kind: ClassVar[str] = "fixed_rate_leg"
    pay_receive: str
    currency: str
    notional: AnyTerm
    fixed_rate: AnyTerm
    day_count: str
    accrual_factor_term: AnyTerm | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "pay_receive": self.pay_receive,
            "currency": self.currency,
            "notional": self.notional.to_dict(),
            "fixed_rate": self.fixed_rate.to_dict(),
            "day_count": self.day_count,
            "accrual_factor_term": None if self.accrual_factor_term is None else self.accrual_factor_term.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FixedRateLegSpec":
        raw = data.get("accrual_factor_term")
        return cls(
            pay_receive=data["pay_receive"],
            currency=data["currency"],
            notional=term_from_dict(data["notional"]),
            fixed_rate=term_from_dict(data["fixed_rate"]),
            day_count=data["day_count"],
            accrual_factor_term=None if raw is None else term_from_dict(raw),
        )


@dataclass(frozen=True)
class FloatingRateLegSpec:
    kind: ClassVar[str] = "floating_rate_leg"
    pay_receive: str
    currency: str
    notional: AnyTerm
    index: RateIndexRef | CmsIndexRef
    spread: AnyTerm
    leverage: AnyTerm
    day_count: str
    reset_timing: str = "in_advance"
    cap: AnyTerm | None = None
    floor: AnyTerm | None = None
    accrual_factor_term: AnyTerm | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "pay_receive": self.pay_receive,
            "currency": self.currency,
            "notional": self.notional.to_dict(),
            "index": self.index.to_dict(),
            "spread": self.spread.to_dict(),
            "leverage": self.leverage.to_dict(),
            "day_count": self.day_count,
            "reset_timing": self.reset_timing,
            "cap": None if self.cap is None else self.cap.to_dict(),
            "floor": None if self.floor is None else self.floor.to_dict(),
            "accrual_factor_term": None if self.accrual_factor_term is None else self.accrual_factor_term.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FloatingRateLegSpec":
        raw_index = data["index"]
        if raw_index.get("kind") == "rate_index":
            index = RateIndexRef.from_dict(raw_index)
        elif raw_index.get("kind") == "cms_index":
            index = CmsIndexRef.from_dict(raw_index)
        else:
            raise ValueError("unsupported index kind")
        raw_cap = data.get("cap")
        raw_floor = data.get("floor")
        raw_aft = data.get("accrual_factor_term")
        return cls(
            pay_receive=data["pay_receive"],
            currency=data["currency"],
            notional=term_from_dict(data["notional"]),
            index=index,
            spread=term_from_dict(data["spread"]),
            leverage=term_from_dict(data["leverage"]),
            day_count=data["day_count"],
            reset_timing=data.get("reset_timing", "in_advance"),
            cap=None if raw_cap is None else term_from_dict(raw_cap),
            floor=None if raw_floor is None else term_from_dict(raw_floor),
            accrual_factor_term=None if raw_aft is None else term_from_dict(raw_aft),
        )


@dataclass(frozen=True)
class FormulaLegSpec:
    kind: ClassVar[str] = "formula_leg"
    leg_role: str
    pay_receive: str
    currency: str
    notional: AnyTerm
    formula_name: str
    formula_inputs: dict[str, Any]
    day_count: str | None = None
    accrual_factor_term: AnyTerm | None = None
    cap: AnyTerm | None = None
    floor: AnyTerm | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "leg_role": self.leg_role,
            "pay_receive": self.pay_receive,
            "currency": self.currency,
            "notional": self.notional.to_dict(),
            "formula_name": self.formula_name,
            "formula_inputs": self.formula_inputs,
            "day_count": self.day_count,
            "accrual_factor_term": None if self.accrual_factor_term is None else self.accrual_factor_term.to_dict(),
            "cap": None if self.cap is None else self.cap.to_dict(),
            "floor": None if self.floor is None else self.floor.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FormulaLegSpec":
        raw_aft = data.get("accrual_factor_term")
        raw_cap = data.get("cap")
        raw_floor = data.get("floor")
        return cls(
            leg_role=data["leg_role"],
            pay_receive=data["pay_receive"],
            currency=data["currency"],
            notional=term_from_dict(data["notional"]),
            formula_name=data["formula_name"],
            formula_inputs=dict(data.get("formula_inputs", {})),
            day_count=data.get("day_count"),
            accrual_factor_term=None if raw_aft is None else term_from_dict(raw_aft),
            cap=None if raw_cap is None else term_from_dict(raw_cap),
            floor=None if raw_floor is None else term_from_dict(raw_floor),
        )


KnownLeg = FXForwardLegSpec | FXOptionLegSpec | FixedRateLegSpec | FloatingRateLegSpec | FormulaLegSpec


def leg_from_dict(data: dict[str, Any]) -> KnownLeg:
    kind = data["kind"]
    if kind == "fx_forward_leg":
        return FXForwardLegSpec.from_dict(data)
    if kind == "fx_option_leg":
        return FXOptionLegSpec.from_dict(data)
    if kind == "fixed_rate_leg":
        return FixedRateLegSpec.from_dict(data)
    if kind == "floating_rate_leg":
        return FloatingRateLegSpec.from_dict(data)
    if kind == "formula_leg":
        return FormulaLegSpec.from_dict(data)
    raise ValueError(f"unknown leg kind: {kind}")
