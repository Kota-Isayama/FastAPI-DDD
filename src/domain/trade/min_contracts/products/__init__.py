from .coupon_swap import AKOCouponSwapSpec, CouponFormula, CouponSwapSpec
from .tarf import TARFLeg, TARFSpec

Contract = TARFSpec | CouponSwapSpec | AKOCouponSwapSpec


def contract_from_dict(data: dict):
    kind = data["kind"]
    if kind == "tarf":
        return TARFSpec.from_dict(data)
    if kind == "coupon_swap":
        return CouponSwapSpec.from_dict(data)
    if kind == "ako_coupon_swap":
        return AKOCouponSwapSpec.from_dict(data)
    raise ValueError(f"unknown contract kind: {kind}")
