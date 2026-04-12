from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class CouponSwapRepresentation:
    kind: Literal["coupon_swap"] = "coupon_swap"
    settlement_style: str = "net_cash"
    booking_family: str = "COUPON_SWAP"

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "settlement_style": self.settlement_style, "booking_family": self.booking_family}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CouponSwapRepresentation":
        return cls(
            settlement_style=data.get("settlement_style", "net_cash"),
            booking_family=data.get("booking_family", "COUPON_SWAP"),
        )


@dataclass(frozen=True)
class OptionBundleRepresentation:
    kind: Literal["option_bundle"] = "option_bundle"
    booking_method: str = "grouped"
    premium_style: str = "zero_cost"

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "booking_method": self.booking_method, "premium_style": self.premium_style}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OptionBundleRepresentation":
        return cls(
            booking_method=data.get("booking_method", "grouped"),
            premium_style=data.get("premium_style", "zero_cost"),
        )


TradeRepresentation = CouponSwapRepresentation | OptionBundleRepresentation


def representation_from_dict(data: dict[str, Any]) -> TradeRepresentation:
    kind = data["kind"]
    if kind == "coupon_swap":
        return CouponSwapRepresentation.from_dict(data)
    if kind == "option_bundle":
        return OptionBundleRepresentation.from_dict(data)
    raise ValueError(f"unknown representation kind: {kind}")
