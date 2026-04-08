from __future__ import annotations

from .components import ProductSpec
from .products import AKOCouponSwapSpec, TARFSpec


def product_spec_to_dict(spec: ProductSpec) -> dict:
    return spec.to_dict()


def product_spec_from_dict(data: dict) -> ProductSpec:
    return ProductSpec.from_dict(data)


def tarf_to_dict(spec: TARFSpec) -> dict:
    return spec.to_dict()


def tarf_from_dict(data: dict) -> TARFSpec:
    return TARFSpec.from_dict(data)


def ako_coupon_swap_to_dict(spec: AKOCouponSwapSpec) -> dict:
    return spec.to_dict()


def ako_coupon_swap_from_dict(data: dict) -> AKOCouponSwapSpec:
    return AKOCouponSwapSpec.from_dict(data)