import dataclasses


@dataclasses.dataclass(frozen=True):
class CouponSwapPayoffTerms:
    knock_out_scheme: 