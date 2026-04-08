from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProductIdentity:
    family: str
    type_name: str
    version: str = "2.0"

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
            version=data.get("version", "2.0"),
        )


@dataclass(frozen=True)
class UnderlyingRef:
    name: str
    asset_class: str
    quote_convention: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "asset_class": self.asset_class,
            "quote_convention": self.quote_convention,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UnderlyingRef":
        return cls(
            name=data["name"],
            asset_class=data["asset_class"],
            quote_convention=data.get("quote_convention"),
        )


@dataclass(frozen=True)
class RateIndexRef:
    name: str
    currency: str
    tenor: str
    day_count: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "rate_index",
            "name": self.name,
            "currency": self.currency,
            "tenor": self.tenor,
            "day_count": self.day_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RateIndexRef":
        return cls(
            name=data["name"],
            currency=data["currency"],
            tenor=data["tenor"],
            day_count=data.get("day_count"),
        )


@dataclass(frozen=True)
class CmsIndexRef:
    name: str
    currency: str
    tenor: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "cms_index",
            "name": self.name,
            "currency": self.currency,
            "tenor": self.tenor,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CmsIndexRef":
        return cls(
            name=data["name"],
            currency=data["currency"],
            tenor=data["tenor"],
        )
