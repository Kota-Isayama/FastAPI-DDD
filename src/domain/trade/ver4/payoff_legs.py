from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Protocol

from .barriers import LegBarrierSpec, NoLegBarrier, leg_barrier_from_dict
from .terms import Term, term_from_dict


class FXLegSpec(Protocol):
    kind: ClassVar[str]

    def to_dict(self) -> dict[str, Any]:
        ...


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