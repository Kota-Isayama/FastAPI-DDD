from __future__ import annotations

from .components import ProductSpec


def product_spec_to_dict(spec: ProductSpec) -> dict:
    return spec.to_dict()


def product_spec_from_dict(data: dict) -> ProductSpec:
    return ProductSpec.from_dict(data)
